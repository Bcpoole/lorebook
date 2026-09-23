from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse


from copy import deepcopy
from pathlib import Path

from lorebook.api.storage import save_draft_state
from lorebook.imaging.service import _assert_sd_available, _render_sd_image
from lorebook.story.service import _build_story_action, _build_story_artifact, _story_item_sd_prompt
from lorebook.story.streaming import _story_event_generator
from lorebook.workflow.normalization import _normalize_state

_STORY_ITEM_SECTIONS = frozenset({"characters_artifact", "locations", "objects"})


router = APIRouter()


@router.post("/story")
async def generate_story_artifact(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    if not raw_idea:
        raise HTTPException(status_code=400, detail="raw_idea is required")

    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    max_length = int(experimentation_config.get("maxLength", 1200))
    story_setup: dict[str, Any] | None = (
        body.get("story_setup") if isinstance(body.get("story_setup"), dict) else None
    )
    instruction: str = str(body.get("instruction") or "").strip()
    action: str = str(body.get("action") or "").strip()

    state = _normalize_state(raw_idea, body.get("state"))
    existing_story = (
        state.get("story_artifact") if isinstance(state.get("story_artifact"), dict) else None
    )

    if action and existing_story:
        artifact, generation_quality = _build_story_action(
            raw_idea, existing_story, action, persona_id=persona_id, max_length=max_length
        )
    else:
        artifact, generation_quality = _build_story_artifact(
            raw_idea,
            persona_id=persona_id,
            max_length=max_length,
            story_setup=story_setup,
            instruction=instruction,
        )

    state["story_artifact"] = artifact

    payload = {
        "raw_idea": raw_idea,
        "state": state,
        "generation_quality": generation_quality,
        "meta": {"mode": "story"},
        "save_pending": bool(body.get("save_pending", False)),
    }
    save_draft_state(payload, "latest", artifact_type="story")

    response: Dict[str, Any] = {
        "state": state,
        "story_artifact": artifact,
        "generation_quality": generation_quality,
    }
    if action:
        response["action"] = action
    if story_setup is not None:
        response["story_setup"] = story_setup
    if instruction:
        response["story_instruction"] = instruction
    return response


@router.post("/story/stream")
async def stream_story_artifact(body: Dict[str, Any], request: Request) -> EventSourceResponse:
    raw_idea = str(body.get("raw_idea") or "").strip()
    if not raw_idea:
        raise HTTPException(status_code=400, detail="raw_idea is required")

    experimentation_config = body.get("experimentation_config", {})
    if not isinstance(experimentation_config, dict):
        raise HTTPException(status_code=400, detail="experimentation_config must be an object")

    story_setup = body.get("story_setup")
    if story_setup is not None and not isinstance(story_setup, dict):
        raise HTTPException(status_code=400, detail="story_setup must be an object")

    return EventSourceResponse(
        _story_event_generator(
            raw_idea=raw_idea,
            is_disconnected=request.is_disconnected,
            persona_id=str(body.get("persona_id") or "blank"),
            max_length=int(experimentation_config.get("maxLength", 1200)),
            story_setup=story_setup,
            instruction=str(body.get("instruction") or "").strip(),
            save_pending=bool(body.get("save_pending", False)),
        )
    )


@router.post("/story-item")
async def story_item_operation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Update, delete, or generate an image for a single item within a story artifact."""
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    section: str = str(body.get("section") or "")
    operation: str = str(body.get("operation") or "")
    item_index: int = int(body.get("item_index", 0))

    if section not in _STORY_ITEM_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section '{section}'. Must be one of {sorted(_STORY_ITEM_SECTIONS)}",
        )

    state = _normalize_state(raw_idea, body.get("state"))
    incoming_state = body.get("state") if isinstance(body.get("state"), dict) else {}
    artifact = state.get("story_artifact")
    if not isinstance(artifact, dict):
        raise HTTPException(status_code=400, detail="state.story_artifact is required")

    artifact = deepcopy(artifact)
    items: list[Any] = list(artifact.get(section) or [])

    if operation == "update":
        item = body.get("item")
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="item is required for update operation")
        if 0 <= item_index < len(items):
            items[item_index] = item
        else:
            items.append(item)

    elif operation == "delete":
        if 0 <= item_index < len(items):
            items.pop(item_index)

    elif operation == "image":
        if item_index < 0 or item_index >= len(items) or not isinstance(items[item_index], dict):
            raise HTTPException(status_code=400, detail="Invalid item_index")
        mode: str = str(body.get("mode") or "prompt")
        sd_config: dict[str, Any] = (
            body.get("sd_config") if isinstance(body.get("sd_config"), dict) else {}
        )
        persona_id: str = str(body.get("persona_id") or "blank")
        item = dict(items[item_index])

        image_prompt = _story_item_sd_prompt(
            item, artifact, section, sd_config=sd_config, persona_id=persona_id
        )
        item["image_prompt"] = image_prompt

        if mode == "full":
            _assert_sd_available(sd_config.get("endpoint"))
            style_name = str(sd_config.get("style") or "") or None
            full_path, data_uri, _styled, _style = _render_sd_image(
                image_prompt, style_name=style_name, sd_config=sd_config
            )
            item["image_name"] = Path(full_path).name
            item["image_data"] = data_uri
            item.pop("image_path", None)

        items[item_index] = item

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operation '{operation}'. Must be update, delete, or image",
        )

    artifact[section] = items
    state["story_artifact"] = artifact
    if isinstance(incoming_state.get("story_setup"), dict):
        state["story_setup"] = incoming_state["story_setup"]
    if isinstance(incoming_state.get("story_instruction"), str):
        state["story_instruction"] = incoming_state["story_instruction"]

    save_draft_state(
        {
            "raw_idea": raw_idea,
            "state": state,
            "meta": {"mode": "story"},
            "save_pending": bool(body.get("save_pending", False)),
        },
        "latest",
        artifact_type="story",
    )
    return {"story_artifact": artifact, "state": state}
