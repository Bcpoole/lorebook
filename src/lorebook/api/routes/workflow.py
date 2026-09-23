from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse


import time

from lorebook.api.storage import save_draft_state, save_run_result
from lorebook.config.prompts import get_persona_prompts
from lorebook.llm import call_local_llm
from lorebook.workflow.normalization import _normalize_state
from lorebook.workflow.service import _run_stage_sync
from lorebook.workflow.state import WizardState
from lorebook.workflow.streaming import _run_stage_stream


router = APIRouter()


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

    save_draft_state({**payload, "save_pending": not auto_save}, "latest", artifact_type="world")

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
        artifact_type="world",
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
            request.is_disconnected,
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

    summary = call_local_llm(
        get_persona_prompts(persona_id).REVIEW_SUMMARY_SYSTEM, prompt, max_length=360
    )
    return {"summary": summary.strip()}
