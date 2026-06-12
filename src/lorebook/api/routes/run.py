from __future__ import annotations

import json
import os
import time
from typing import Any, AsyncIterator, Dict

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from lorebook.llm import call_local_llm, stream_local_llm
from lorebook.graph import build_app
from lorebook.state import WizardState
from lorebook.api.storage import save_run_result

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


def _tokens(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, default))
    except ValueError:
        return default


LOREMASTER_MAX_TOKENS = _tokens("LOREBOOK_LOREMASTER_MAX_TOKENS", 2048)
CHARACTER_MAX_TOKENS = _tokens("LOREBOOK_CHARACTER_MAX_TOKENS", 2048)
EDITOR_MAX_TOKENS = _tokens("LOREBOOK_EDITOR_MAX_TOKENS", 512)


def _normalize_state(raw_idea: str, state: Dict[str, Any] | None = None) -> WizardState:
    incoming = state or {}
    return {
        "raw_idea": raw_idea,
        "world_setting": incoming.get("world_setting", ""),
        "characters": incoming.get("characters", []),
        "critique_notes": incoming.get("critique_notes", ""),
        "passed_inspection": bool(incoming.get("passed_inspection", False)),
    }


def _editor_prompt(state: WizardState) -> str:
    character_details = ""
    if state.get("characters"):
        character_details = state["characters"][0].get("details", "")
    return f"Setting:\n{state['world_setting']}\n\nCharacter:\n{character_details}"


def _continuation_prompt(stage: str, state: WizardState) -> str:
    if stage == "loremaster":
        return (
            f"Idea:\n{state['raw_idea']}\n\n"
            f"Current draft:\n{state.get('world_setting', '')}\n\n"
            "Continue writing from the exact cutoff point. Do not restart or summarize."
        )

    if stage == "character_designer":
        current_details = ""
        if state.get("characters"):
            current_details = state["characters"][0].get("details", "")
        return (
            f"World setting:\n{state.get('world_setting', '')}\n\n"
            f"Current character draft:\n{current_details}\n\n"
            "Continue the same character sheet from the exact cutoff point. Do not restart."
        )

    if stage == "editor":
        return (
            f"{_editor_prompt(state)}\n\n"
            f"Current critique draft:\n{state.get('critique_notes', '')}\n\n"
            "Continue the critique from the exact cutoff point. Do not restart or summarize."
        )

    return ""


def _next_stage_from_editor(state: WizardState) -> str:
    return "save_assets" if state.get("passed_inspection") else "loremaster"


def _run_stage_sync(state: WizardState, stage: str, continue_output: bool = False) -> str:
    if stage == "loremaster":
        prompt = _continuation_prompt(stage, state) if continue_output and state.get("world_setting") else state["raw_idea"]
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
        current_details = state["characters"][0].get("details", "") if state.get("characters") else ""
        prompt = _continuation_prompt(stage, state) if continue_output and current_details else state["world_setting"]
        addition = call_local_llm(
            CHARACTER_SYSTEM,
            prompt,
            max_length=CHARACTER_MAX_TOKENS,
        )
        details = f"{current_details}{addition}" if continue_output else addition
        state["characters"] = [{"name": "Companion", "details": details}]
        return "editor"

    if stage == "editor":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for editor")
        if not state.get("characters"):
            raise HTTPException(status_code=400, detail="characters are required for editor")
        if continue_output and state.get("passed_inspection"):
            return _next_stage_from_editor(state)

        prompt = _continuation_prompt(stage, state) if continue_output and state.get("critique_notes") else _editor_prompt(state)
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
    state: WizardState, stage: str, request: Request, continue_output: bool = False
) -> AsyncIterator[Dict[str, str]]:
    start = time.monotonic()

    if await request.is_disconnected():
        return

    yield {"event": "node-start", "data": json.dumps({"node": stage})}

    if stage == "loremaster":
        prior_text = state.get("world_setting", "")
        prompt = _continuation_prompt(stage, state) if continue_output and prior_text else state["raw_idea"]
        text = prior_text if continue_output else ""
        for chunk in stream_local_llm(LOREMASTER_SYSTEM, prompt, max_length=LOREMASTER_MAX_TOKENS):
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
        prior_details = state["characters"][0].get("details", "") if state.get("characters") else ""
        prompt = _continuation_prompt(stage, state) if continue_output and prior_details else state["world_setting"]
        details = prior_details if continue_output else ""
        for chunk in stream_local_llm(CHARACTER_SYSTEM, prompt, max_length=CHARACTER_MAX_TOKENS):
            if await request.is_disconnected():
                return
            details += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        state["characters"] = [{"name": "Companion", "details": details}]
        next_stage = "editor"
        output = {"characters": [{"name": "Companion", "details": details}]}

    elif stage == "editor":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for editor")
        if not state.get("characters"):
            raise HTTPException(status_code=400, detail="characters are required for editor")
        if continue_output and state.get("passed_inspection"):
            next_stage = _next_stage_from_editor(state)
            output = {"passed_inspection": True, "critique_notes": state.get("critique_notes", "")}
            yield {"event": "node-complete", "data": json.dumps({"node": stage, "output": output})}
            yield {
                "event": "step-complete",
                "data": json.dumps(
                    {
                        "state": state,
                        "meta": {"elapsed_ms": round((time.monotonic() - start) * 1000)},
                        "next_stage": next_stage,
                        "save_pending": True,
                    }
                ),
            }
            yield {"event": "done", "data": "{}"}
            return

        prior_critique = state.get("critique_notes", "")
        prompt = _continuation_prompt(stage, state) if continue_output and prior_critique else _editor_prompt(state)
        critique = prior_critique if continue_output else ""
        for chunk in stream_local_llm(EDITOR_SYSTEM, prompt, max_length=EDITOR_MAX_TOKENS):
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
    yield {
        "event": "step-complete",
        "data": json.dumps(
            {
                "state": state,
                "meta": {"elapsed_ms": round((time.monotonic() - start) * 1000)},
                "next_stage": next_stage,
                "save_pending": stage == "editor" and state.get("passed_inspection"),
            }
        ),
    }
    yield {"event": "done", "data": "{}"}


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

    if auto_save:
        saved = save_run_result(
            {
                "raw_idea": raw_idea,
                "state": dict(result),
                "meta": {"elapsed_ms": elapsed_ms},
            }
        )
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
    state = _normalize_state(raw_idea, body.get("state"))

    start = time.monotonic()

    next_stage = _run_stage_sync(state, stage, continue_output=continue_output)

    elapsed_ms = round((time.monotonic() - start) * 1000)
    response: Dict[str, Any] = {
        "state": state,
        "meta": {"elapsed_ms": elapsed_ms},
        "next_stage": next_stage,
    }

    if stage == "editor" and state.get("passed_inspection"):
        response["save_pending"] = True

    return response


@router.post("/step-stream")
async def run_single_step_stream(body: Dict[str, Any], request: Request) -> EventSourceResponse:
    raw_idea: str = body.get("raw_idea", "")
    stage: str = body.get("stage", "loremaster")
    continue_output: bool = bool(body.get("continue_output", False))
    state = _normalize_state(raw_idea, body.get("state"))
    return EventSourceResponse(_run_stage_stream(state, stage, request, continue_output=continue_output))
