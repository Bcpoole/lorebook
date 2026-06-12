from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

import requests
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from lorebook.characters import infer_character_name, should_replace_character_name
from lorebook.api.storage import (
    delete_draft_state,
    load_draft_state,
    load_run,
    save_draft_state,
    save_run_result,
)
from lorebook.graph import build_app
from lorebook.llm import call_local_llm, is_local_llm_available, stream_local_llm
from lorebook.state import CharacterState, WizardState

router = APIRouter()

LOREMASTER_SYSTEM = (
    "You are an expert world builder. Expand the user's idea into a structured "
    "setting with 3 distinct world rules."
)

CHARACTER_SYSTEM = (
    "You are a SillyTavern character designer. Create or refine exactly one companion "
    "character based on this world setting and the provided instruction. "
    "Output only the character details content."
)

EDITOR_SYSTEM = (
    "You are a critical editor. Review the character design against the world "
    "setting. If it feels generic or breaks the world rules, write critique. If "
    "it is excellent, reply exactly with: PASSED."
)

SD_PROMPT_SYSTEM = (
    "You generate Stable Diffusion prompts for character portraits. Return one line only, "
    "focused on visual style, composition, lighting, clothing, and mood. "
    "No markdown, no explanations."
)


def _tokens(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, default))
    except ValueError:
        return default


LOREMASTER_MAX_TOKENS = _tokens("LOREBOOK_LOREMASTER_MAX_TOKENS", 2048)
CHARACTER_MAX_TOKENS = _tokens("LOREBOOK_CHARACTER_MAX_TOKENS", 2048)
EDITOR_MAX_TOKENS = _tokens("LOREBOOK_EDITOR_MAX_TOKENS", 512)


def _coerce_characters(value: Any) -> list[CharacterState]:
    if not isinstance(value, list):
        return []

    normalized: list[CharacterState] = []
    for index, entry in enumerate(value, start=1):
        if not isinstance(entry, dict):
            continue
        normalized_entry: CharacterState = {
            "name": str(entry.get("name") or f"Companion {index}"),
            "details": str(entry.get("details") or ""),
        }
        for optional_key in ("image_path", "image_prompt", "image_data"):
            optional_value = entry.get(optional_key)
            if isinstance(optional_value, str) and optional_value:
                normalized_entry[optional_key] = optional_value
        normalized.append(normalized_entry)
    return normalized


def _normalize_state(raw_idea: str, state: Dict[str, Any] | None = None) -> WizardState:
    incoming = state or {}
    return {
        "raw_idea": raw_idea,
        "world_setting": str(incoming.get("world_setting", "")),
        "characters": _coerce_characters(incoming.get("characters", [])),
        "critique_notes": str(incoming.get("critique_notes", "")),
        "passed_inspection": bool(incoming.get("passed_inspection", False)),
    }


def _all_character_sections(state: WizardState) -> str:
    sections: list[str] = []
    for index, character in enumerate(state.get("characters", []), start=1):
        name = character.get("name") or f"Companion {index}"
        details = character.get("details", "")
        sections.append(f"Character {index} - {name}:\n{details}")
    return "\n\n".join(sections)


def _editor_prompt(state: WizardState) -> str:
    return f"Setting:\n{state['world_setting']}\n\nCharacters:\n{_all_character_sections(state)}"


def _continuation_prompt(stage: str, state: WizardState, directive: str = "", character_index: int = 0) -> str:
    directive_block = f"\n\nInstruction:\n{directive}" if directive.strip() else ""

    if stage == "loremaster":
        return (
            f"Idea:\n{state['raw_idea']}\n\n"
            f"Current draft:\n{state.get('world_setting', '')}"
            f"{directive_block}\n\n"
            "Continue writing from the exact cutoff point. Do not restart or summarize."
        )

    if stage == "character_designer":
        current_details = ""
        characters = state.get("characters", [])
        if 0 <= character_index < len(characters):
            current_details = characters[character_index].get("details", "")
        return (
            f"World setting:\n{state.get('world_setting', '')}\n\n"
            f"Current character draft:\n{current_details}"
            f"{directive_block}\n\n"
            "Continue the same character sheet from the exact cutoff point. Do not restart."
        )

    if stage == "editor":
        return (
            f"{_editor_prompt(state)}"
            f"\n\nCurrent critique draft:\n{state.get('critique_notes', '')}"
            f"{directive_block}\n\n"
            "Continue the critique from the exact cutoff point. Do not restart or summarize."
        )

    return ""


def _next_stage_from_editor(state: WizardState) -> str:
    return "save_assets" if state.get("passed_inspection") else "loremaster"


def _upsert_character(state: WizardState, index: int, details: str) -> list[CharacterState]:
    characters = [dict(character) for character in state.get("characters", [])]
    while len(characters) <= index:
        characters.append({"name": "", "details": ""})

    base = characters[index]
    base["details"] = details
    inferred_name = infer_character_name(details, fallback=base.get("name", ""))
    if should_replace_character_name(base.get("name", "")):
        base["name"] = inferred_name or f"Character {index + 1}"
    characters[index] = base
    return characters


def _run_stage_sync(
    state: WizardState,
    stage: str,
    continue_output: bool = False,
    directive: str = "",
    character_index: int = 0,
) -> str:
    if stage == "loremaster":
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = state["raw_idea"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"
        addition = call_local_llm(
            LOREMASTER_SYSTEM,
            prompt,
            max_length=LOREMASTER_MAX_TOKENS,
        )
        state["world_setting"] = f"{state.get('world_setting', '')}{addition}" if continue_output else addition
        return "character_designer"

    if stage == "character_designer":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for character_designer")

        characters = state.get("characters", [])
        current_details = ""
        if 0 <= character_index < len(characters):
            current_details = characters[character_index].get("details", "")

        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive, character_index=character_index)
        else:
            prompt = state["world_setting"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        addition = call_local_llm(
            CHARACTER_SYSTEM,
            prompt,
            max_length=CHARACTER_MAX_TOKENS,
        )
        details = f"{current_details}{addition}" if continue_output else addition
        state["characters"] = _upsert_character(state, character_index, details)
        return "editor"

    if stage == "editor":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for editor")
        if not state.get("characters"):
            raise HTTPException(status_code=400, detail="characters are required for editor")
        if continue_output and state.get("passed_inspection"):
            return _next_stage_from_editor(state)

        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = _editor_prompt(state)
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        addition = call_local_llm(
            EDITOR_SYSTEM,
            prompt,
            max_length=EDITOR_MAX_TOKENS,
        )
        critique = f"{state.get('critique_notes', '')}{addition}" if continue_output else addition
        passed = "PASSED" in critique
        state["passed_inspection"] = passed
        state["critique_notes"] = critique
        return _next_stage_from_editor(state)

    raise HTTPException(status_code=400, detail=f"Unsupported stage: {stage}")


async def _run_stage_stream(
    state: WizardState,
    stage: str,
    request: Request,
    continue_output: bool = False,
    directive: str = "",
    character_index: int = 0,
    experimentation_config: dict | None = None,
) -> AsyncIterator[Dict[str, str]]:
    start = time.monotonic()
    
    if experimentation_config is None:
        experimentation_config = {}
    
    # Extract max_length from experimentation config, fallback to stage defaults
    max_length = experimentation_config.get("maxLength", 512)

    if await request.is_disconnected():
        return

    yield {"event": "node-start", "data": json.dumps({"node": stage})}

    if stage == "loremaster":
        prior_text = state.get("world_setting", "")
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = state["raw_idea"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        text = prior_text if continue_output else ""
        for chunk in stream_local_llm(LOREMASTER_SYSTEM, prompt, max_length=max_length):
            if await request.is_disconnected():
                return
            text += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        state["world_setting"] = text
        next_stage = "character_designer"
        output = {"world_setting": text}

    elif stage == "character_designer":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for character_designer")

        characters = state.get("characters", [])
        prior_details = ""
        if 0 <= character_index < len(characters):
            prior_details = characters[character_index].get("details", "")

        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive, character_index=character_index)
        else:
            prompt = state["world_setting"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        details = prior_details if continue_output else ""
        for chunk in stream_local_llm(CHARACTER_SYSTEM, prompt, max_length=max_length):
            if await request.is_disconnected():
                return
            details += chunk
            yield {
                "event": "node-token",
                "data": json.dumps({"node": stage, "chunk": chunk}),
            }
        state["characters"] = _upsert_character(state, character_index, details)
        next_stage = "editor"
        output = {"characters": state["characters"]}

    elif stage == "editor":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for editor")
        if not state.get("characters"):
            raise HTTPException(status_code=400, detail="characters are required for editor")
        if continue_output and state.get("passed_inspection"):
            next_stage = _next_stage_from_editor(state)
            output = {"passed_inspection": True, "critique_notes": state.get("critique_notes", "")}
            yield {"event": "node-complete", "data": json.dumps({"node": stage, "output": output})}
            elapsed_ms = round((time.monotonic() - start) * 1000)
            save_draft_state(
                {
                    "raw_idea": state.get("raw_idea", ""),
                    "state": state,
                    "meta": {"elapsed_ms": elapsed_ms, "next_stage": next_stage, "stage": stage},
                    "save_pending": True,
                }
            )
            yield {
                "event": "step-complete",
                "data": json.dumps(
                    {
                        "state": state,
                        "meta": {"elapsed_ms": elapsed_ms},
                        "next_stage": next_stage,
                        "save_pending": True,
                    }
                ),
            }
            yield {"event": "done", "data": "{}"}
            return

        prior_critique = state.get("critique_notes", "")
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = _editor_prompt(state)
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        critique = prior_critique if continue_output else ""
        for chunk in stream_local_llm(EDITOR_SYSTEM, prompt, max_length=max_length):
            if await request.is_disconnected():
                return
            critique += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        passed = "PASSED" in critique
        state["passed_inspection"] = passed
        state["critique_notes"] = critique
        next_stage = _next_stage_from_editor(state)
        output = {
            "passed_inspection": passed,
            "critique_notes": critique,
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported stage: {stage}")

    yield {"event": "node-complete", "data": json.dumps({"node": stage, "output": output})}
    elapsed_ms = round((time.monotonic() - start) * 1000)
    save_pending = stage == "editor" and state.get("passed_inspection")
    save_draft_state(
        {
            "raw_idea": state.get("raw_idea", ""),
            "state": state,
            "meta": {"elapsed_ms": elapsed_ms, "next_stage": next_stage, "stage": stage},
            "save_pending": save_pending,
        }
    )
    yield {
        "event": "step-complete",
        "data": json.dumps(
            {
                "state": state,
                "meta": {"elapsed_ms": elapsed_ms},
                "next_stage": next_stage,
                "save_pending": save_pending,
            }
        ),
    }
    yield {"event": "done", "data": "{}"}


def _outputs_images_dir() -> Path:
    directory = Path(__file__).resolve().parents[4] / "outputs" / "images"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _make_sd_prompt(state: WizardState, character: CharacterState, prompt_override: str | None = None) -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()

    prompt_input = (
        f"World setting:\n{state.get('world_setting', '')}\n\n"
        f"Character name: {character.get('name', 'Companion')}\n"
        f"Character details:\n{character.get('details', '')}"
    )
    generated = call_local_llm(SD_PROMPT_SYSTEM, prompt_input, max_length=256)
    return generated.strip().replace("\n", " ")


def _render_sd_image(prompt: str) -> tuple[str, str]:
    endpoint = os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860").rstrip("/")
    response = requests.post(
        f"{endpoint}/sdapi/v1/txt2img",
        json={
            "prompt": prompt,
            "steps": 20,
            "width": 512,
            "height": 512,
            "cfg_scale": 7,
            "sampler_name": "Euler a",
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    images = payload.get("images") or []
    if not images:
        raise RuntimeError("Stable Diffusion response did not include image data")

    encoded = images[0]
    if "," in encoded:
        encoded = encoded.split(",", maxsplit=1)[1]
    image_bytes = base64.b64decode(encoded)

    image_name = f"{uuid4().hex}.png"
    image_path = _outputs_images_dir() / image_name
    image_path.write_bytes(image_bytes)

    return str(image_path), f"data:image/png;base64,{encoded}"


def _assert_sd_available() -> None:
    endpoint = os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860").rstrip("/")
    try:
        response = requests.get(f"{endpoint}/sdapi/v1/progress", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail="Stable Diffusion AUTOMATIC1111 API is unavailable. Start it before generating an image.",
        ) from exc


@router.get("/restore-latest")
async def restore_latest() -> Dict[str, Any]:
    draft = load_draft_state("latest")
    return {
        "draft": draft,
    }


@router.get("/llm-health")
async def llm_health() -> Dict[str, Any]:
    return {
        "connected": is_local_llm_available(),
    }


@router.get("/health")
async def app_health() -> Dict[str, Any]:
    return {
        "status": "ok",
    }


@router.get("/runs/{run_id}")
async def get_run_by_id(run_id: str) -> Dict[str, Any]:
    record = load_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return record


@router.post("/draft")
async def save_draft(body: Dict[str, Any]) -> Dict[str, Any]:
    if bool(body.get("clear", False)):
        deleted = delete_draft_state("latest")
        return {
            "ok": True,
            "cleared": True,
            "deleted": deleted,
        }

    payload = {
        "raw_idea": body.get("raw_idea", ""),
        "state": body.get("state", {}),
        "meta": body.get("meta", {}),
        "save_pending": bool(body.get("save_pending", False)),
    }
    saved = save_draft_state(payload, "latest")
    return {
        **saved,
        "ok": True,
    }


@router.post("/character-image")
async def generate_character_image(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    state = _normalize_state(raw_idea, body.get("state"))
    character_index = max(0, int(body.get("character_index", 0)))

    if character_index >= len(state.get("characters", [])):
        raise HTTPException(status_code=400, detail="character_index is out of range")

    character = state["characters"][character_index]
    _assert_sd_available()
    prompt_override = body.get("prompt_override")
    prompt = _make_sd_prompt(state, character, prompt_override=prompt_override)

    try:
        image_path, image_data = _render_sd_image(prompt)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Failed to render image from Stable Diffusion endpoint") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    updated_character = {
        **character,
        "image_prompt": prompt,
        "image_path": image_path,
        "image_data": image_data,
    }
    updated_characters = list(state["characters"])
    updated_characters[character_index] = updated_character
    state["characters"] = updated_characters

    save_draft_state(
        {
            "raw_idea": state.get("raw_idea", ""),
            "state": state,
            "meta": body.get("meta", {}),
            "save_pending": bool(body.get("save_pending", False)),
        },
        "latest",
    )

    return {
        "state": state,
        "character_index": character_index,
        "character": updated_character,
    }


@router.post("/run")
async def run_workflow(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    auto_save: bool = body.get("auto_save", True)
    initial_state: WizardState = {
        "raw_idea": raw_idea,
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }

    graph = build_app()
    start = time.monotonic()
    result = graph.invoke(initial_state, config={"recursion_limit": 10})
    elapsed_ms = round((time.monotonic() - start) * 1000)

    payload = {
        "raw_idea": raw_idea,
        "state": dict(result),
        "meta": {"elapsed_ms": elapsed_ms},
    }

    save_draft_state({**payload, "save_pending": not auto_save}, "latest")

    if auto_save:
        saved = save_run_result(payload)
        return {
            "run_id": saved["run_id"],
            "run_path": saved["run_path"],
            "filename": saved["filename"],
            "state": dict(result),
            "meta": {"elapsed_ms": elapsed_ms},
        }

    return {
        "pending_save": True,
        "state": dict(result),
        "meta": {"elapsed_ms": elapsed_ms},
    }


@router.post("/step")
async def run_single_step(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    stage: str = body.get("stage", "loremaster")
    continue_output: bool = bool(body.get("continue_output", False))
    directive: str = str(body.get("directive", ""))
    character_index: int = max(0, int(body.get("character_index", 0)))
    state = _normalize_state(raw_idea, body.get("state"))

    start = time.monotonic()

    next_stage = _run_stage_sync(
        state,
        stage,
        continue_output=continue_output,
        directive=directive,
        character_index=character_index,
    )

    elapsed_ms = round((time.monotonic() - start) * 1000)
    save_pending = stage == "editor" and state.get("passed_inspection")
    response: Dict[str, Any] = {
        "state": state,
        "meta": {"elapsed_ms": elapsed_ms},
        "next_stage": next_stage,
    }

    if save_pending:
        response["save_pending"] = True

    save_draft_state(
        {
            "raw_idea": raw_idea,
            "state": state,
            "meta": {"elapsed_ms": elapsed_ms, "next_stage": next_stage, "stage": stage},
            "save_pending": save_pending,
        },
        "latest",
    )

    return response


@router.post("/step-stream")
async def run_single_step_stream(body: Dict[str, Any], request: Request) -> EventSourceResponse:
    raw_idea: str = body.get("raw_idea", "")
    stage: str = body.get("stage", "loremaster")
    continue_output: bool = bool(body.get("continue_output", False))
    directive: str = str(body.get("directive", ""))
    character_index: int = max(0, int(body.get("character_index", 0)))
    experimentation_config: dict = body.get("experimentation_config", {})
    state = _normalize_state(raw_idea, body.get("state"))
    return EventSourceResponse(
        _run_stage_stream(
            state,
            stage,
            request,
            continue_output=continue_output,
            directive=directive,
            character_index=character_index,
            experimentation_config=experimentation_config,
        )
    )
