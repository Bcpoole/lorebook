from __future__ import annotations

from typing import Any


_PAGE_AGENT_FIELDS: dict[str, frozenset[str]] = {
    "world": frozenset({"world_setting", "characters", "critique_notes", "passed_inspection"}),
    "story": frozenset(
        {
            "title",
            "description",
            "plot",
            "setting",
            "style",
            "history",
            "tags",
            "characters_artifact",
            "locations",
            "objects",
            "openings",
        }
    ),
    "character": frozenset({"world_setting", "characters", "critique_notes", "passed_inspection"}),
}


_PAGE_AGENT_SYSTEM = (
    "You are Lorebook's page-level creative orchestrator. Answer the user's request using the current "
    "page context. You may coordinate the concerns of world-building, character, and editorial specialists, "
    "but return one concise response. When an edit would help, propose semantic edits to the editable "
    "components listed in the request. Never claim an edit was saved; the user reviews proposals. "
    "Return ONLY valid JSON with this schema: "
    '{"reply":"brief explanation","changes":[{"field":"allowed_field","label":"Human label",'
    '"entity_name":"optional existing entity name","value":<new field or entity value>}]}. '
    "Use an empty changes array for discussion, questions, or pages without editable content. Preserve all "
    "unmentioned content. For a named entity inside characters_artifact, locations, or objects, set entity_name "
    "and return only that updated entity as value. For an ordinary field, return the new field value."
)


def _page_agent_role(page: str) -> str:
    if page == "character":
        return "character"
    if page == "story":
        return "editor"
    return "loremaster"


def _compact_page_agent_context(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _compact_page_agent_context(item)
            for key, item in value.items()
            if key not in {"image_data", "image_prompt_styled"}
        }
    if isinstance(value, list):
        return [_compact_page_agent_context(item) for item in value]
    if isinstance(value, str) and len(value) > 12_000:
        return f"{value[:12_000]}\n[content truncated for agent context]"
    return value


def _page_agent_entity_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("name") or value.get("label") or "").strip()


def _page_agent_candidate_changes(
    field: str,
    before: Any,
    after: Any,
    label: str,
    entity_name: str = "",
) -> list[dict[str, Any]]:
    if not isinstance(before, list):
        if before is not None and type(after) is not type(before):
            return []
        if after == before:
            return []
        return [{"field": field, "label": label, "before": before, "after": after}]

    entity_collection = (
        any(isinstance(item, dict) for item in before)
        or isinstance(after, dict)
        or (isinstance(after, list) and any(isinstance(item, dict) for item in after))
    )
    if not entity_collection:
        if not isinstance(after, list) or after == before:
            return []
        return [{"field": field, "label": label, "before": before, "after": after}]

    if isinstance(after, dict):
        requested_name = (
            str(entity_name or _page_agent_entity_name(after) or label).strip().casefold()
        )
        indexes = [
            index
            for index, item in enumerate(before)
            if requested_name and _page_agent_entity_name(item).casefold() == requested_name
        ]
        if len(indexes) != 1:
            if len(before) != 1:
                return []
            indexes = [0]
        index = indexes[0]
        if after == before[index]:
            return []
        return [
            {
                "field": field,
                "label": label or _page_agent_entity_name(after),
                "entity_index": index,
                "entity_name": _page_agent_entity_name(before[index])
                or _page_agent_entity_name(after),
                "before": before[index],
                "after": after,
            }
        ]

    if not isinstance(after, list):
        return []

    changes: list[dict[str, Any]] = []
    max_length = max(len(before), len(after))
    for index in range(max_length):
        old_item = before[index] if index < len(before) else None
        new_item = after[index] if index < len(after) else None
        if old_item == new_item:
            continue
        item_label = _page_agent_entity_name(new_item) or _page_agent_entity_name(old_item) or label
        changes.append(
            {
                "field": field,
                "label": item_label,
                "entity_index": index,
                "entity_name": _page_agent_entity_name(old_item)
                or _page_agent_entity_name(new_item),
                "before": old_item,
                "after": new_item,
            }
        )
    return changes
