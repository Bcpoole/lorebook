from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException


import json

from lorebook.llm import call_local_llm
from lorebook.page_agent.service import (
    _PAGE_AGENT_FIELDS,
    _PAGE_AGENT_SYSTEM,
    _compact_page_agent_context,
    _page_agent_candidate_changes,
    _page_agent_role,
)
from lorebook.story.service import _persona_layered_system_prompt
from lorebook.workflow.text import _extract_first_json_block


router = APIRouter()


@router.post("/agent/chat")
async def chat_with_page_agent(body: Dict[str, Any]) -> Dict[str, Any]:
    page = str(body.get("page") or "").strip().lower()
    message = str(body.get("message") or "").strip()
    persona_id = str(body.get("persona_id") or "blank").strip()
    context = body.get("context")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="context must be an object")

    editable = context.get("editable")
    if not isinstance(editable, dict):
        editable = {}
    allowed_fields = _PAGE_AGENT_FIELDS.get(page, frozenset())
    available_fields = sorted(field for field in allowed_fields if field in editable)
    system_prompt = _persona_layered_system_prompt(
        _PAGE_AGENT_SYSTEM,
        persona_id,
        _page_agent_role(page),
    )
    prompt_context = _compact_page_agent_context(context)
    prompt = (
        f"Active page: {page or 'unknown'}\n"
        f"Editable top-level components: {json.dumps(available_fields)}\n"
        f"Current page context:\n{json.dumps(prompt_context, ensure_ascii=False)}\n\n"
        f"User message:\n{message}"
    )
    generated = call_local_llm(system_prompt, prompt, max_length=900)
    parsed = _extract_first_json_block(generated)
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="The page agent returned an invalid response")

    reply = str(parsed.get("reply") or "").strip()
    raw_changes = parsed.get("changes")
    if not isinstance(raw_changes, list):
        raw_changes = []

    changes: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, int | None]] = set()
    for candidate in raw_changes:
        if not isinstance(candidate, dict):
            continue
        field = str(candidate.get("field") or "").strip()
        if field not in available_fields or "value" not in candidate:
            continue
        before = editable[field]
        label = str(candidate.get("label") or field.replace("_", " ").title()).strip()
        normalized_changes = _page_agent_candidate_changes(
            field,
            before,
            candidate["value"],
            label,
            str(candidate.get("entity_name") or ""),
        )
        for change in normalized_changes:
            target = (field, change.get("entity_index"))
            if target in seen_targets:
                continue
            seen_targets.add(target)
            changes.append(change)

    return {
        "reply": reply or ("I prepared changes for review." if changes else "No changes proposed."),
        "changes": changes,
        "page": page,
        "persona_id": persona_id,
    }
