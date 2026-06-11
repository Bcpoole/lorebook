from __future__ import annotations

import json
import os
import time
from typing import AsyncIterator, Dict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from lorebook.api.storage import save_run_result
from lorebook.llm import stream_local_llm
from lorebook.state import WizardState

router = APIRouter()


LOREMASTER_SYSTEM = (
    "You are an expert world builder. Expand the user's idea into a structured "
    "setting with 3 distinct world rules."
)

CHARACTER_SYSTEM = (
    "You are a SillyTavern character designer. Create 1 main companion character "
    "based on this world setting. Format as clean text."
)

EDITOR_SYSTEM = (
    "You are a critical editor. Review the character design against the world "
    "setting. If it feels generic or breaks the world rules, write critique. If "
    "it is excellent, reply exactly with: PASSED."
)


def _empty_state(raw_idea: str) -> WizardState:
    return {
        "raw_idea": raw_idea,
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }


def _tokens(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, default))
    except ValueError:
        return default


LOREMASTER_MAX_TOKENS = _tokens("LOREBOOK_LOREMASTER_MAX_TOKENS", 2048)
CHARACTER_MAX_TOKENS = _tokens("LOREBOOK_CHARACTER_MAX_TOKENS", 2048)
EDITOR_MAX_TOKENS = _tokens("LOREBOOK_EDITOR_MAX_TOKENS", 512)


async def _event_generator(raw_idea: str, request: Request, auto_save: bool = True) -> AsyncIterator[Dict[str, str]]:
    state = _empty_state(raw_idea)
    start = time.monotonic()

    async def ensure_connected() -> bool:
        return not await request.is_disconnected()

    for _cycle in range(3):
        if not await ensure_connected():
            return

        # loremaster
        yield {"event": "node-start", "data": json.dumps({"node": "loremaster"})}
        world_setting = ""
        for chunk in stream_local_llm(LOREMASTER_SYSTEM, state["raw_idea"], max_length=LOREMASTER_MAX_TOKENS):
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
        for chunk in stream_local_llm(CHARACTER_SYSTEM, state["world_setting"], max_length=CHARACTER_MAX_TOKENS):
            if not await ensure_connected():
                return
            character_details += chunk
            yield {
                "event": "node-token",
                "data": json.dumps({"node": "character_designer", "chunk": chunk}),
            }
        state["characters"] = [{"name": "Companion", "details": character_details}]
        yield {
            "event": "node-complete",
            "data": json.dumps(
                {
                    "node": "character_designer",
                    "output": {"characters": [{"name": "Companion", "details": character_details}]},
                }
            ),
        }

        if not await ensure_connected():
            return

        # editor
        yield {"event": "node-start", "data": json.dumps({"node": "editor"})}
        critique_notes = ""
        prompt = f"Setting:\n{state['world_setting']}\n\nCharacter:\n{character_details}"
        for chunk in stream_local_llm(EDITOR_SYSTEM, prompt, max_length=EDITOR_MAX_TOKENS):
            if not await ensure_connected():
                return
            critique_notes += chunk
            yield {"event": "node-token", "data": json.dumps({"node": "editor", "chunk": chunk})}

        passed = "PASSED" in critique_notes
        state["passed_inspection"] = passed
        state["critique_notes"] = "" if passed else critique_notes
        yield {
            "event": "node-complete",
            "data": json.dumps(
                {
                    "node": "editor",
                    "output": {
                        "passed_inspection": passed,
                        "critique_notes": "" if passed else critique_notes,
                    },
                }
            ),
        }

        if passed:
            break

    elapsed_ms = round((time.monotonic() - start) * 1000)

    if auto_save:
        saved = save_run_result(
            {
                "raw_idea": raw_idea,
                "state": state,
                "meta": {"elapsed_ms": elapsed_ms, "streaming": True},
            }
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
async def stream_workflow(raw_idea: str, request: Request, auto_save: bool = True) -> EventSourceResponse:
    return EventSourceResponse(_event_generator(raw_idea, request, auto_save=auto_save))
