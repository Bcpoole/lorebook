from __future__ import annotations

import re
from typing import Any, Dict

from lorebook.characters import infer_character_name, should_replace_character_name
from lorebook.characters.relationships import _coerce_relationships, _make_character_urn
from lorebook.workflow.state import CharacterState, StoryArtifact, WizardState


def _coerce_characters(value: Any) -> list[CharacterState]:
    if not isinstance(value, list):
        return []

    normalized: list[CharacterState] = []
    for index, entry in enumerate(value, start=1):
        if not isinstance(entry, dict):
            continue
        raw_name = str(entry.get("name") or "")
        details = str(entry.get("details") or "")
        # Re-infer from details when the stored name is a known placeholder/generic header
        if should_replace_character_name(raw_name):
            raw_name = infer_character_name(details, fallback=f"Companion {index}")
        normalized_entry: CharacterState = {
            "id": str(entry.get("id") or "").strip() or _make_character_urn(),
            "name": raw_name or f"Companion {index}",
            "details": details,
            "relationships": _coerce_relationships(entry.get("relationships")),
        }
        role_value = str(entry.get("role") or "").strip().lower()
        if role_value in {"character", "persona"}:
            normalized_entry["role"] = role_value

        tags_value = entry.get("tags")
        if isinstance(tags_value, list):
            cleaned_tags = [str(tag).strip().lower() for tag in tags_value if str(tag).strip()]
            if cleaned_tags:
                normalized_entry["tags"] = cleaned_tags

        for optional_key in ("image_path", "image_prompt", "image_data", "summary"):
            optional_value = entry.get(optional_key)
            if isinstance(optional_value, str) and optional_value:
                normalized_entry[optional_key] = optional_value

        normalized.append(normalized_entry)
    return normalized


def _coerce_story_artifact(value: Any) -> StoryArtifact | None:
    if not isinstance(value, dict):
        return None

    def _as_string_list(raw: Any) -> list[str]:
        if not isinstance(raw, list):
            return []
        output: list[str] = []
        for entry in raw:
            text = str(entry).strip()
            if text:
                output.append(text)
        return output

    def _as_entity_list(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        output: list[dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = _clean_story_label(entry.get("name"))
            description = str(entry.get("description") or "").strip()
            summary = str(entry.get("summary") or "").strip()
            role = str(entry.get("role") or "").strip()
            label = str(entry.get("label") or "").strip()
            text = str(entry.get("text") or "").strip()
            tags = _as_string_list(entry.get("tags"))
            item: dict[str, Any] = {}
            if name:
                item["name"] = name
            if description:
                item["description"] = description
            if summary:
                item["summary"] = summary
            if role:
                item["role"] = role
            if label:
                item["label"] = label
            if text:
                item["text"] = text
            if tags:
                item["tags"] = tags
            if item:
                output.append(item)
        return output

    def _as_openings(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        openings: list[dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            messages: list[dict[str, str]] = []
            raw_messages = entry.get("messages")
            if isinstance(raw_messages, list):
                for message in raw_messages:
                    if not isinstance(message, dict):
                        continue
                    content = str(message.get("content") or "").strip()
                    if content:
                        messages.append(
                            {
                                "role": str(message.get("role") or "assistant").strip().lower(),
                                "content": content,
                            }
                        )
            openings.append(
                {
                    "description": str(entry.get("description") or "").strip(),
                    "messages": messages,
                }
            )
        return openings

    description = str(value.get("description") or "").strip()
    description_words = description.split()
    if len(description_words) > 128:
        description = " ".join(description_words[:128])

    artifact: StoryArtifact = {
        "title": _clean_story_label(value.get("title") or "Untitled Story"),
        "description": description,
        "plot": str(value.get("plot") or "").strip(),
        "setting": str(value.get("setting") or "").strip(),
        "style": str(value.get("style") or "").strip(),
        "history": str(value.get("history") or "").strip(),
        "tags": _as_string_list(value.get("tags")),
        "characters_artifact": _as_entity_list(value.get("characters_artifact")),
        "locations": _as_entity_list(value.get("locations")),
        "objects": _as_entity_list(value.get("objects")),
        "openings": _as_openings(value.get("openings")),
    }
    return artifact


def _normalize_state(raw_idea: str, state: Dict[str, Any] | None = None) -> WizardState:
    incoming = state or {}
    normalized: WizardState = {
        "raw_idea": raw_idea,
        "world_setting": str(incoming.get("world_setting", "")),
        "characters": _coerce_characters(incoming.get("characters", [])),
        "critique_notes": str(incoming.get("critique_notes", "")),
        "passed_inspection": bool(incoming.get("passed_inspection", False)),
    }
    story_artifact = _coerce_story_artifact(incoming.get("story_artifact"))
    if story_artifact:
        normalized["story_artifact"] = story_artifact
    return normalized


def _clean_story_label(value: Any) -> str:
    label = str(value or "").strip()
    label = re.sub(r"^\s*(?:#{1,6}\s+|[-*]\s+)", "", label)
    label = re.sub(r"^[*_`]+|[*_`]+$", "", label).strip()
    return label
