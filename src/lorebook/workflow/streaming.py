from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import AsyncIterator, Dict

from lorebook.api.storage import save_draft_state
from lorebook.config.prompts import get_persona_prompts
from lorebook.errors import InvalidRequestError
from lorebook.llm import stream_local_llm
from lorebook.workflow.service import (
    _clean_continued_output,
    _continuation_addition,
    _continuation_prompt,
    _editor_prompt,
    _is_meta_response,
    _next_stage_from_editor,
    _stage_max_tokens,
    _upsert_character,
)
from lorebook.workflow.state import WizardState


async def _run_stage_stream(
    state: WizardState,
    stage: str,
    is_disconnected: Callable[[], Awaitable[bool]],
    continue_output: bool = False,
    directive: str = "",
    character_index: int = 0,
    experimentation_config: dict | None = None,
) -> AsyncIterator[Dict[str, str]]:
    start = time.monotonic()

    if experimentation_config is None:
        experimentation_config = {}

    max_length = int(experimentation_config.get("maxLength", _stage_max_tokens(stage)))
    llm_endpoint = experimentation_config.get("llmEndpoint") or None
    prompts = get_persona_prompts(experimentation_config.get("persona_id", "blank"))

    if await is_disconnected():
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
        for chunk in stream_local_llm(
            prompts.LOREMASTER_SYSTEM, prompt, max_length=max_length, endpoint=llm_endpoint
        ):
            if await is_disconnected():
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
            raise InvalidRequestError("world_setting is required for character_designer")

        characters = state.get("characters", [])
        prior_details = ""
        if 0 <= character_index < len(characters):
            prior_details = characters[character_index].get("details", "")

        if continue_output:
            prompt = _continuation_prompt(
                stage, state, directive=directive, character_index=character_index
            )
        else:
            prompt = state["world_setting"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = ""
        for chunk in stream_local_llm(
            prompts.CHARACTER_SYSTEM, prompt, max_length=max_length, endpoint=llm_endpoint
        ):
            if await is_disconnected():
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
            for chunk in stream_local_llm(
                prompts.CHARACTER_SYSTEM, retry_prompt, max_length=max_length, endpoint=llm_endpoint
            ):
                if await is_disconnected():
                    return
                generated += chunk
                yield {
                    "event": "node-token",
                    "data": json.dumps({"node": stage, "chunk": chunk}),
                }

        addition = (
            _continuation_addition(prior_details, generated) if continue_output else generated
        )
        details = f"{prior_details}{addition}" if continue_output else addition
        details = _clean_continued_output(details)
        state["characters"] = _upsert_character(state, character_index, details)
        next_stage = "editor"
        output = {"characters": state["characters"]}

    elif stage == "editor":
        if not state.get("world_setting"):
            raise InvalidRequestError("world_setting is required for editor")
        if not state.get("characters"):
            raise InvalidRequestError("characters are required for editor")
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
                },
                artifact_type="world",
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
        for chunk in stream_local_llm(
            prompts.EDITOR_SYSTEM, prompt, max_length=max_length, endpoint=llm_endpoint
        ):
            if await is_disconnected():
                return
            generated += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        addition = (
            _continuation_addition(prior_critique, generated) if continue_output else generated
        )
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
        raise InvalidRequestError(f"Unsupported stage: {stage}")

    yield {"event": "node-complete", "data": json.dumps({"node": stage, "output": output})}
    elapsed_ms = round((time.monotonic() - start) * 1000)
    save_pending = stage == "editor" and state.get("passed_inspection")
    save_draft_state(
        {
            "raw_idea": state.get("raw_idea", ""),
            "state": state,
            "meta": {"elapsed_ms": elapsed_ms, "next_stage": next_stage, "stage": stage},
            "save_pending": save_pending,
        },
        artifact_type="world",
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
