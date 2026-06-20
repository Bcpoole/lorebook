from __future__ import annotations

import json
import os
import time
from typing import AsyncIterator, Dict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from lorebook.characters import infer_character_name, should_replace_character_name
from lorebook.api.storage import save_draft_state, save_run_result
from lorebook.llm import stream_local_llm
from lorebook.config.prompts import get_persona_prompts
from lorebook.state import WizardState

router = APIRouter()



def _empty_state(raw_idea: str) -> WizardState:
    return {
        "raw_idea": raw_idea,
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }


def _upsert_first_character(state: WizardState, details: str) -> None:
    existing = list(state.get("characters", []))
    if existing:
        first = {**existing[0], "details": details}
        if should_replace_character_name(first.get("name", "")):
            first["name"] = infer_character_name(details, fallback="Character 1")
        state["characters"] = [first, *existing[1:]]
        return
    state["characters"] = [{"name": infer_character_name(details, fallback="Character 1"), "details": details}]


def _editor_prompt(state: WizardState) -> str:
    sections = []
    for index, character in enumerate(state.get("characters", []), start=1):
        name = character.get("name") or f"Companion {index}"
        details = character.get("details", "")
        sections.append(f"Character {index} - {name}:\n{details}")
    characters_block = "\n\n".join(sections)
    return f"Setting:\n{state['world_setting']}\n\nCharacters:\n{characters_block}"


def _tokens(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, default))
    except ValueError:
        return default


LOREMASTER_MAX_TOKENS = _tokens("LOREBOOK_LOREMASTER_MAX_TOKENS", 2048)
CHARACTER_MAX_TOKENS = _tokens("LOREBOOK_CHARACTER_MAX_TOKENS", 2048)
EDITOR_MAX_TOKENS = _tokens("LOREBOOK_EDITOR_MAX_TOKENS", 512)


async def _event_generator(raw_idea: str, request: Request, auto_save: bool = True, experimentation_config: dict | None = None, persona_id: str = "blank") -> AsyncIterator[Dict[str, str]]:
    if experimentation_config is None:
        experimentation_config = {}
    prompts = get_persona_prompts(persona_id)
    
    state = _empty_state(raw_idea)
    start = time.monotonic()
    
    # Extract max_length from experimentation config, fallback to stage defaults
    max_length = experimentation_config.get("maxLength", 512)
    llm_endpoint = experimentation_config.get("llmEndpoint") or None

    async def ensure_connected() -> bool:
        return not await request.is_disconnected()

    for _cycle in range(3):
        if not await ensure_connected():
            return

        # loremaster
        yield {"event": "node-start", "data": json.dumps({"node": "loremaster"})}
        world_setting = ""
        for chunk in stream_local_llm(prompts.LOREMASTER_SYSTEM, state["raw_idea"], max_length=max_length, endpoint=llm_endpoint):
            if not await ensure_connected():
                return
            world_setting += chunk
            yield {"event": "node-token", "data": json.dumps({"node": "loremaster", "chunk": chunk})}
        state["world_setting"] = world_setting
        yield {
            "event": "node-complete",
            "data": json.dumps({"node": "loremaster", "output": {"world_setting": world_setting}}),
        }

        if not await ensure_connected():
            return

        # character designer
        yield {"event": "node-start", "data": json.dumps({"node": "character_designer"})}
        character_details = ""
        for chunk in stream_local_llm(prompts.CHARACTER_SYSTEM, state["world_setting"], max_length=max_length, endpoint=llm_endpoint):
            if not await ensure_connected():
                return
            character_details += chunk
            yield {
                "event": "node-token",
                "data": json.dumps({"node": "character_designer", "chunk": chunk}),
            }
        _upsert_first_character(state, character_details)
        yield {
            "event": "node-complete",
            "data": json.dumps(
                {
                    "node": "character_designer",
                    "output": {"characters": state["characters"]},
                }
            ),
        }

        save_draft_state(
            {
                "raw_idea": raw_idea,
                "state": state,
                "meta": {"streaming": True, "stage": "character_designer"},
                "save_pending": False,
            },
            artifact_type="world",
        )

        if not await ensure_connected():
            return

        # editor
        yield {"event": "node-start", "data": json.dumps({"node": "editor"})}
        critique_notes = ""
        prompt = _editor_prompt(state)
        for chunk in stream_local_llm(prompts.EDITOR_SYSTEM, prompt, max_length=max_length, endpoint=llm_endpoint):
            if not await ensure_connected():
                return
            critique_notes += chunk
            yield {"event": "node-token", "data": json.dumps({"node": "editor", "chunk": chunk})}

        passed = "PASSED" in critique_notes
        state["passed_inspection"] = passed
        state["critique_notes"] = critique_notes
        yield {
            "event": "node-complete",
            "data": json.dumps(
                {
                    "node": "editor",
                    "output": {
                        "passed_inspection": passed,
                        "critique_notes": critique_notes,
                    },
                }
            ),
        }

        save_draft_state(
            {
                "raw_idea": raw_idea,
                "state": state,
                "meta": {"streaming": True, "stage": "editor"},
                "save_pending": bool(passed),
            },
            artifact_type="world",
        )

        if passed:
            break

    elapsed_ms = round((time.monotonic() - start) * 1000)

    if auto_save:
        saved = save_run_result(
            {
                "raw_idea": raw_idea,
                "state": state,
                "meta": {"elapsed_ms": elapsed_ms, "streaming": True},
            },
            artifact_type="world",
        )
        save_draft_state(
            {
                "raw_idea": raw_idea,
                "state": state,
                "meta": {"elapsed_ms": elapsed_ms, "streaming": True},
                "save_pending": False,
            },
            artifact_type="world",
        )
        yield {
            "event": "run-complete",
            "data": json.dumps(
                {
                    "run_id": saved["run_id"],
                    "run_path": saved["run_path"],
                    "filename": saved["filename"],
                    "state": state,
                    "meta": {"elapsed_ms": elapsed_ms},
                }
            ),
        }
    else:
        save_draft_state(
            {
                "raw_idea": raw_idea,
                "state": state,
                "meta": {"elapsed_ms": elapsed_ms, "streaming": True},
                "save_pending": True,
            },
            artifact_type="world",
        )
        yield {
            "event": "save-pending",
            "data": json.dumps(
                {
                    "state": state,
                    "meta": {"elapsed_ms": elapsed_ms},
                }
            ),
        }

    yield {"event": "done", "data": "{}"}


@router.get("/stream")
async def stream_workflow(raw_idea: str, request: Request, auto_save: bool = True, experimentation_config: str = "{}", persona_id: str = "blank") -> EventSourceResponse:
    try:
        config = json.loads(experimentation_config) if experimentation_config else {}
    except json.JSONDecodeError:
        config = {}
    return EventSourceResponse(_event_generator(raw_idea, request, auto_save=auto_save, experimentation_config=config, persona_id=persona_id))
