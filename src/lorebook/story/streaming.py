from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterator, Dict

from lorebook.api.storage import save_draft_state
from lorebook.llm import stream_local_llm
from lorebook.story.service import (
    _STORY_ORCHESTRATOR_SYSTEM,
    _STORY_SECTION_SPECS,
    _parse_story_section,
    _persona_layered_system_prompt,
    _story_artifact_from_sections,
    _story_prompt,
    _story_token_budget,
)
from lorebook.workflow.normalization import _normalize_state


async def _story_event_generator(
    raw_idea: str,
    is_disconnected: Callable[[], Awaitable[bool]],
    persona_id: str,
    max_length: int,
    story_setup: dict[str, Any] | None,
    instruction: str,
    save_pending: bool,
) -> AsyncIterator[Dict[str, str]]:
    """Stream orchestrator and specialist output while publishing assembled Story snapshots."""
    prompt = _story_prompt(raw_idea, story_setup, instruction)
    sections: dict[str, Any] = {}
    quality = "full"

    async def generate_section(
        key: str,
        system_prompt: str,
        user_prompt: str,
        minimum_tokens: int,
    ) -> AsyncIterator[Dict[str, str]]:
        if await is_disconnected():
            return
        token_budget = _story_token_budget(max_length, minimum_tokens)
        yield {
            "event": "story-stage-start",
            "data": json.dumps({"section": key, "token_budget": token_budget}),
        }
        generated = ""
        try:
            for chunk in stream_local_llm(system_prompt, user_prompt, max_length=token_budget):
                if await is_disconnected():
                    return
                generated += chunk
        except RuntimeError as exc:
            yield {"event": "story-error", "data": json.dumps({"section": key, "detail": str(exc)})}
            return
        yield {"event": "story-stage-raw", "data": generated}

    coordination_notes = ""
    orchestrator_system = _persona_layered_system_prompt(
        _STORY_ORCHESTRATOR_SYSTEM, persona_id, "loremaster"
    )
    async for event in generate_section("orchestrator", orchestrator_system, prompt, 220):
        if event["event"] == "story-stage-raw":
            coordination_notes = event["data"]
        else:
            yield event
    if not coordination_notes:
        yield {
            "event": "story-error",
            "data": json.dumps(
                {"section": "orchestrator", "detail": "The story orchestrator returned no output."}
            ),
        }
        return
    yield {
        "event": "story-section-complete",
        "data": json.dumps(
            {
                "section": "orchestrator",
                "output": {"orchestrator": coordination_notes},
                "story_artifact": _story_artifact_from_sections(sections, persona_id),
            }
        ),
    }

    specialist_context = f"{prompt}\n\nOrchestrator coordination notes:\n{coordination_notes}"
    for spec in _STORY_SECTION_SPECS:
        role = "character" if spec.section == "characters_artifact" else "loremaster"
        layered_system = _persona_layered_system_prompt(spec.system_prompt, persona_id, role)
        generated = ""
        async for event in generate_section(
            spec.section,
            layered_system,
            specialist_context,
            spec.minimum_tokens,
        ):
            if event["event"] == "story-stage-raw":
                generated = event["data"]
            else:
                yield event
        if not generated:
            yield {
                "event": "story-error",
                "data": json.dumps(
                    {
                        "section": spec.section,
                        "detail": f"The {spec.section} specialist returned no output.",
                    }
                ),
            }
            return
        parsed = _parse_story_section(generated, spec.section)
        if parsed is None:
            quality = "partial"
            parsed = {
                spec.section: []
                if spec.section
                in {"tags", "characters_artifact", "locations", "objects", "openings"}
                else ""
            }
        sections[spec.section] = parsed
        if spec.section == "brief" and parsed.get("brief"):
            specialist_context = f"{specialist_context}\n\nStory brief:\n{parsed['brief']}"
        yield {
            "event": "story-section-complete",
            "data": json.dumps(
                {
                    "section": spec.section,
                    "output": parsed,
                    "story_artifact": _story_artifact_from_sections(sections, persona_id),
                }
            ),
        }

    artifact = _story_artifact_from_sections(sections, persona_id)
    state = _normalize_state(raw_idea, None)
    state["story_artifact"] = artifact
    if story_setup is not None:
        state["story_setup"] = story_setup
    if instruction:
        state["story_instruction"] = instruction
    save_draft_state(
        {
            "raw_idea": raw_idea,
            "state": state,
            "generation_quality": quality,
            "meta": {"mode": "story", "streaming": True},
            "save_pending": save_pending,
        },
        "latest",
        artifact_type="story",
    )
    yield {
        "event": "story-complete",
        "data": json.dumps(
            {
                "state": state,
                "story_artifact": artifact,
                "generation_quality": quality,
                "story_setup": story_setup,
                "story_instruction": instruction,
            }
        ),
    }
    yield {"event": "done", "data": "{}"}
