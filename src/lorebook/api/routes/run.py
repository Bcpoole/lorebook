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
from lorebook.config.prompts import get_persona_prompts
from lorebook.config.sd_styles import DEFAULT_SD_STYLE, SD_STYLES
from lorebook.api.storage import (
    delete_draft_state,
    load_draft_state,
    load_run,
    save_draft_state,
    save_run_result,
)
from lorebook.llm import call_local_llm, is_local_llm_available, stream_local_llm
from lorebook.state import CharacterState, WizardState

router = APIRouter()


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


def _stage_max_tokens(stage: str) -> int:
    if stage == "loremaster":
        return LOREMASTER_MAX_TOKENS
    if stage == "character_designer":
        return CHARACTER_MAX_TOKENS
    if stage == "editor":
        return EDITOR_MAX_TOKENS
    return LOREMASTER_MAX_TOKENS


def _is_meta_response(text: str) -> bool:
    """Detect if response is meta/instruction rather than content (e.g., 'I understand...')."""
    if not text or len(text) < 10:
        return False
    lower = text.lower()
    meta_markers = [
        "i understand",
        "i'm ready",
        "please provide",
        "please give",
        "please specify",
        "what would",
        "how should",
        "would you like",
        "i need",
        "can you",
    ]
    return any(lower.startswith(marker) for marker in meta_markers)


def _clean_continued_output(text: str) -> str:
    """Clean up output from continuations: remove (Continued) markers and duplicate headers."""
    if not text:
        return ""
    
    import re
    
    # Remove "(Continued)" markers (with variations)
    text = re.sub(r'\s*\(Continued\)\s*', '', text, flags=re.IGNORECASE)
    
    # Fix headers that got mashed together (e.g., "bond## World Rules" -> "bond\n\n## World Rules")
    # Match: word/punctuation followed directly by # (markdown header)
    text = re.sub(r'([a-zA-Z0-9.,;:\'\"])\s*(#{1,6}\s+)', r'\1\n\n\2', text)
    
    # Remove duplicate headers within the same text
    # Split into lines and track headers we've seen
    lines = text.split('\n')
    seen_headers = set()
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Check if this is a header line
        if stripped.startswith('#'):
            # Extract header content (ignore leading #'s and trailing spaces)
            header_content = stripped.lstrip('#').strip()
            # Only keep if we haven't seen this exact header before
            if header_content not in seen_headers:
                seen_headers.add(header_content)
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    # Rejoin and clean up excessive blank lines
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n{4,}', '\n\n\n', text)  # Max 3 newlines
    
    return text.strip()


def _continuation_addition(prior: str, generated: str) -> str:
    """Strip duplicated leading text when a continuation restarts from the top."""
    if not prior or not generated:
        return generated

    # Case 1: model restarted from the beginning of the previous draft.
    if generated.startswith(prior):
        return generated[len(prior) :]

    # Case 2: model started near the prior cutoff; remove suffix/prefix overlap.
    max_overlap = min(len(prior), len(generated))
    for size in range(max_overlap, 0, -1):
        if prior.endswith(generated[:size]):
            return generated[size:]

    # Case 3: model restarted from an early prefix of the prior draft.
    for size in range(max_overlap, 0, -1):
        if prior.startswith(generated[:size]):
            return generated[size:]

    return generated


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
    experimentation_config: dict[str, Any] | None = None,
) -> str:
    config = experimentation_config or {}
    max_length = int(config.get("maxLength", _stage_max_tokens(stage)))
    prompts = get_persona_prompts(config.get("persona_id", "blank"))

    if stage == "loremaster":
        prior_text = state.get("world_setting", "")
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = state["raw_idea"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"
        generated = call_local_llm(
            prompts.LOREMASTER_SYSTEM,
            prompt,
            max_length=max_length,
        )
        addition = _continuation_addition(prior_text, generated) if continue_output else generated
        output = f"{prior_text}{addition}" if continue_output else addition
        state["world_setting"] = _clean_continued_output(output)
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

        generated = call_local_llm(
            prompts.CHARACTER_SYSTEM,
            prompt,
            max_length=max_length,
        )
        
        # Guardrail: reject meta responses and retry with stronger instruction
        if not continue_output and _is_meta_response(generated):
            retry_prompt = (
                f"{state['world_setting']}\n\n"
                f"Create a detailed character card for a companion in this world. "
                f"Include: name, physical description, personality, background, skills, and role."
            )
            generated = call_local_llm(
                prompts.CHARACTER_SYSTEM,
                retry_prompt,
                max_length=max_length,
            )
        
        addition = _continuation_addition(current_details, generated) if continue_output else generated
        details = f"{current_details}{addition}" if continue_output else addition
        details = _clean_continued_output(details)
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

        generated = call_local_llm(
            prompts.EDITOR_SYSTEM,
            prompt,
            max_length=max_length,
        )
        prior_critique = state.get("critique_notes", "")
        addition = _continuation_addition(prior_critique, generated) if continue_output else generated
        critique = f"{state.get('critique_notes', '')}{addition}" if continue_output else addition
        critique = _clean_continued_output(critique)
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
    
    max_length = int(experimentation_config.get("maxLength", _stage_max_tokens(stage)))
    prompts = get_persona_prompts(experimentation_config.get("persona_id", "blank"))

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

        generated = ""
        for chunk in stream_local_llm(prompts.LOREMASTER_SYSTEM, prompt, max_length=max_length):
            if await request.is_disconnected():
                return
            generated += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        addition = _continuation_addition(prior_text, generated) if continue_output else generated
        text = f"{prior_text}{addition}" if continue_output else addition
        state["world_setting"] = _clean_continued_output(text)
        next_stage = "character_designer"
        output = {"world_setting": state["world_setting"]}

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

        generated = ""
        for chunk in stream_local_llm(prompts.CHARACTER_SYSTEM, prompt, max_length=max_length):
            if await request.is_disconnected():
                return
            generated += chunk
            yield {
                "event": "node-token",
                "data": json.dumps({"node": stage, "chunk": chunk}),
            }
        
        # Guardrail: reject meta responses and retry with stronger instruction
        if not continue_output and _is_meta_response(generated):
            retry_prompt = (
                f"{state['world_setting']}\n\n"
                f"Create a detailed character card for a companion in this world. "
                f"Include: name, physical description, personality, background, skills, and role."
            )
            generated = ""
            for chunk in stream_local_llm(prompts.CHARACTER_SYSTEM, retry_prompt, max_length=max_length):
                if await request.is_disconnected():
                    return
                generated += chunk
                yield {
                    "event": "node-token",
                    "data": json.dumps({"node": stage, "chunk": chunk}),
                }
        
        addition = _continuation_addition(prior_details, generated) if continue_output else generated
        details = f"{prior_details}{addition}" if continue_output else addition
        details = _clean_continued_output(details)
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

        generated = ""
        for chunk in stream_local_llm(prompts.EDITOR_SYSTEM, prompt, max_length=max_length):
            if await request.is_disconnected():
                return
            generated += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        addition = _continuation_addition(prior_critique, generated) if continue_output else generated
        critique = f"{prior_critique}{addition}" if continue_output else addition
        critique = _clean_continued_output(critique)
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


def _make_sd_prompt(state: WizardState, character: CharacterState, prompt_override: str | None = None, persona_id: str = "blank") -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()

    prompt_input = (
        f"World setting:\n{state.get('world_setting', '')}\n\n"
        f"Character name: {character.get('name', 'Companion')}\n"
        f"Character details:\n{character.get('details', '')}"
    )
    generated = call_local_llm(get_persona_prompts(persona_id).SD_PROMPT_SYSTEM, prompt_input, max_length=256)
    return generated.strip().replace("\n", " ")


def _style_sd_prompts(prompt: str, style_name: str | None = None, negative_extra: str | None = None) -> tuple[str, str, str]:
    style_key = (style_name or "").strip().lower() or DEFAULT_SD_STYLE
    style = SD_STYLES.get(style_key, SD_STYLES[DEFAULT_SD_STYLE])

    prompt_template = str(style.get("prompt", "{prompt}"))
    negative_template = str(style.get("negative_prompt", "{prompt}"))

    if "{prompt}" not in prompt_template:
        prompt_template = f"{prompt_template}, {{prompt}}"
    if "{prompt}" not in negative_template:
        negative_template = f"{negative_template}, {{prompt}}"

    styled_prompt = prompt_template.format(prompt=prompt)
    styled_negative = negative_template.format(prompt=prompt)
    if negative_extra and negative_extra.strip():
        styled_negative = f"{styled_negative}, {negative_extra.strip()}"
    return styled_prompt, styled_negative, style_key


def _render_sd_image(prompt: str, style_name: str | None = None, sd_config: dict[str, Any] | None = None) -> tuple[str, str, str, str]:
    config = sd_config or {}
    styled_prompt, styled_negative, resolved_style = _style_sd_prompts(
        prompt,
        style_name=style_name,
        negative_extra=str(config.get("negativePromptExtra", "")),
    )
    endpoint = str(config.get("endpoint") or os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860")).rstrip("/")
    steps = int(config.get("steps", 30))
    width = int(config.get("width", 768))
    height = int(config.get("height", 768))
    cfg_scale = float(config.get("cfgScale", 3))
    sampler_name = str(config.get("samplerName", "DPM++ 2M"))

    response = requests.post(
        f"{endpoint}/sdapi/v1/txt2img",
        json={
            "prompt": styled_prompt,
            "negative_prompt": styled_negative,
            "steps": steps,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
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

    return str(image_path), f"data:image/png;base64,{encoded}", styled_prompt, resolved_style


def _assert_sd_available(endpoint_override: str | None = None) -> None:
    endpoint = str(endpoint_override or os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860")).rstrip("/")
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
    mode = str(body.get("mode", "full")).strip().lower()
    style_name = str(body.get("style", "")).strip().lower() or None
    sd_config = body.get("sd_config") if isinstance(body.get("sd_config"), dict) else {}

    if mode not in {"full", "prompt", "image"}:
        raise HTTPException(status_code=400, detail="mode must be one of: full, prompt, image")

    if character_index >= len(state.get("characters", [])):
        raise HTTPException(status_code=400, detail="character_index is out of range")

    character = state["characters"][character_index]
    prompt_override = body.get("prompt_override")

    if mode == "prompt":
        prompt = _make_sd_prompt(state, character, prompt_override=prompt_override)
        updated_character = {
            **character,
            "image_prompt": prompt,
        }
    else:
        if mode == "image":
            prompt = (prompt_override or "").strip() or str(character.get("image_prompt") or "").strip()
            if not prompt:
                raise HTTPException(
                    status_code=400,
                    detail="No existing image prompt found. Regenerate prompt first or provide prompt_override.",
                )
        else:
            prompt = _make_sd_prompt(state, character, prompt_override=prompt_override)

        _assert_sd_available(sd_config.get("endpoint") if isinstance(sd_config, dict) else None)
        try:
            image_path, image_data, styled_prompt, resolved_style = _render_sd_image(
                prompt,
                style_name=style_name,
                sd_config=sd_config,
            )
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail="Failed to render image from Stable Diffusion endpoint") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        updated_character = {
            **character,
            "image_prompt": prompt,
            "image_prompt_styled": styled_prompt,
            "image_style": resolved_style,
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


@router.get("/sd-styles")
async def get_sd_styles() -> Dict[str, Any]:
    return {
        "default_style": DEFAULT_SD_STYLE,
        "styles": sorted(SD_STYLES.keys()),
    }


@router.post("/run")
async def run_workflow(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    auto_save: bool = body.get("auto_save", True)
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config = {**experimentation_config, "persona_id": persona_id}
    initial_state: WizardState = {
        "raw_idea": raw_idea,
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }

    state = dict(initial_state)
    next_stage = "loremaster"
    start = time.monotonic()
    # Run staged pipeline so persona-aware prompts are respected.
    for _ in range(8):
        if next_stage == "save_assets":
            break
        next_stage = _run_stage_sync(
            state,
            next_stage,
            experimentation_config=experimentation_config,
        )
        if state.get("passed_inspection") and next_stage == "save_assets":
            break
    elapsed_ms = round((time.monotonic() - start) * 1000)

    payload = {
        "raw_idea": raw_idea,
        "state": dict(state),
        "meta": {"elapsed_ms": elapsed_ms},
    }

    save_draft_state({**payload, "save_pending": not auto_save}, "latest")

    if auto_save:
        saved = save_run_result(payload)
        return {
            "run_id": saved["run_id"],
            "run_path": saved["run_path"],
            "filename": saved["filename"],
            "state": dict(state),
            "meta": {"elapsed_ms": elapsed_ms},
        }

    return {
        "pending_save": True,
        "state": dict(state),
        "meta": {"elapsed_ms": elapsed_ms},
    }


@router.post("/step")
async def run_single_step(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    stage: str = body.get("stage", "loremaster")
    continue_output: bool = bool(body.get("continue_output", False))
    directive: str = str(body.get("directive", ""))
    character_index: int = max(0, int(body.get("character_index", 0)))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config = {**experimentation_config, "persona_id": persona_id}
    state = _normalize_state(raw_idea, body.get("state"))

    start = time.monotonic()

    next_stage = _run_stage_sync(
        state,
        stage,
        continue_output=continue_output,
        directive=directive,
        character_index=character_index,
        experimentation_config=experimentation_config,
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
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config = {**experimentation_config, "persona_id": persona_id}
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


@router.post("/review-summary")
async def generate_review_summary(body: Dict[str, Any]) -> Dict[str, Any]:
    original: str = str(body.get("original", ""))
    revised: str = str(body.get("revised", ""))
    stage: str = str(body.get("stage", ""))
    persona_id: str = str(body.get("persona_id", "blank"))

    if not revised.strip():
        return {
            "summary": "- Modified: Waiting for generated output.\n- Added: Waiting for generated output.\n- Removed: Waiting for generated output.",
        }

    stage_hint = stage.replace("_", " ").strip() or "draft"
    prompt = (
        f"Stage: {stage_hint}\n\n"
        "Write a human narrative summary of how the revised draft differs from the original.\n"
        "Use exactly this structure and keep each bullet to 1-2 sentences:\n"
        "- Modified: describe the major shifts in focus, tone, structure, or framing.\n"
        "- Added: describe the most meaningful new ideas or details.\n"
        "- Removed: describe what emphasis, constraints, or details were dropped.\n\n"
        "Rules:\n"
        "- No numeric estimates or counts.\n"
        "- No mention of tokens, sentences, or statistics.\n"
        "- Be specific enough to guide an approve/reject decision.\n\n"
        f"Original:\n{original}\n\n"
        f"Revised:\n{revised}\n"
    )

    summary = call_local_llm(get_persona_prompts(persona_id).REVIEW_SUMMARY_SYSTEM, prompt, max_length=360)
    return {"summary": summary.strip()}
