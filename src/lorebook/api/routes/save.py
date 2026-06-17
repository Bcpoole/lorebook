from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict

from fastapi import APIRouter

from lorebook.api.storage import save_run_result
from lorebook.characters import infer_character_name, should_replace_character_name
from lorebook.config.prompts import get_persona_prompts
from lorebook.llm import call_local_llm, is_local_llm_available

router = APIRouter()

SUGGEST_NAME_SYSTEM = (
    "You are a file naming assistant. Given a creative world-building idea, "
    "reply with ONLY a short snake_case filename: 2-5 words, lowercase, underscores, "
    "no extension, no punctuation. Example output: floating_storm_city"
)


def _sanitize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^\w\s-]", "", name.lower().strip())
    name = re.sub(r"[\s-]+", "_", name).strip("_")
    return name or "lorebook_run"


def _story_item_filename(base_name: str, section: str, index: int, item: dict[str, Any]) -> str:
    candidate = _sanitize(str(item.get("name") or item.get("label") or f"{section}_{index + 1}"))
    return f"{base_name}_{section}_{index + 1}_{candidate}"


def _story_item_tags(item: dict[str, Any]) -> list[str]:
    raw_tags = item.get("tags")
    if not isinstance(raw_tags, list):
        return []
    cleaned: list[str] = []
    for tag in raw_tags:
        value = str(tag).strip().lower()
        if value:
            cleaned.append(value)
    return cleaned


def _save_story_sub_artifacts(
    *,
    base_filename: str,
    raw_idea: str,
    story_artifact: dict[str, Any],
) -> None:
    characters = story_artifact.get("characters_artifact")
    if isinstance(characters, list):
        for index, entry in enumerate(characters):
            if not isinstance(entry, dict):
                continue
            details = str(entry.get("summary") or entry.get("description") or "").strip()
            if not details:
                continue
            character_state = {
                "characters": [
                    {
                        "name": str(entry.get("name") or f"Character {index + 1}").strip(),
                        "details": details,
                        "role": str(entry.get("role") or "character").strip().lower() or "character",
                        "tags": _story_item_tags(entry),
                    }
                ]
            }
            save_run_result(
                {
                    "raw_idea": raw_idea,
                    "state": character_state,
                    "meta": {"source": "story"},
                },
                filename=_story_item_filename(base_filename, "character", index, entry),
                artifact_type="character",
            )

    for section, artifact_type in (("locations", "location"), ("objects", "object")):
        entries = story_artifact.get(section)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            description = str(entry.get("description") or entry.get("summary") or "").strip()
            if not name and not description:
                continue
            partial_story = {
                "title": name or str(story_artifact.get("title") or f"{artifact_type.title()} {index + 1}"),
                "description": description or str(story_artifact.get("description") or ""),
                "plot": [],
                "setting": str(story_artifact.get("setting") or ""),
                "style": str(story_artifact.get("style") or ""),
                "tags": _story_item_tags(entry),
                "characters_artifact": [],
                "locations": [entry] if section == "locations" else [],
                "objects": [entry] if section == "objects" else [],
                "opening": "",
                "examples": [],
            }
            save_run_result(
                {
                    "raw_idea": raw_idea,
                    "state": {"story_artifact": partial_story},
                    "meta": {"source": "story"},
                },
                filename=_story_item_filename(base_filename, artifact_type, index, entry),
                artifact_type=artifact_type,
            )


def _generate_summaries(state: dict[str, Any], persona_id: str = "blank") -> dict[str, Any]:
    """Add LLM-generated summary to each character that doesn't already have one."""
    if not is_local_llm_available():
        return state
    characters = state.get("characters")
    if not isinstance(characters, list):
        return state
    prompts = get_persona_prompts(persona_id)
    summary_system = getattr(prompts, "CHARACTER_SUMMARY_SYSTEM", None)
    if not summary_system:
        return state
    updated_chars = []
    for char in characters:
        if not isinstance(char, dict):
            updated_chars.append(char)
            continue
        if char.get("summary"):
            updated_chars.append(char)
            continue
        details = str(char.get("details") or "").strip()
        if not details:
            updated_chars.append(char)
            continue
        try:
            summary = call_local_llm(summary_system, details, max_length=80).strip()
        except Exception:
            summary = ""
        updated_chars.append({**char, "summary": summary} if summary else char)
    return {**state, "characters": updated_chars}


@router.post("/save")
async def save_run(body: Dict[str, Any]) -> Dict[str, Any]:
    filename: str | None = body.get("filename") or None
    persona_id: str = str(body.get("persona_id") or "blank")
    state = body.get("state") or {}

    # Ensure character names are properly extracted
    if isinstance(state.get("characters"), list):
        fixed_chars = []
        for i, char in enumerate(state["characters"]):
            if not isinstance(char, dict):
                fixed_chars.append(char)
                continue
            raw_name = str(char.get("name") or "")
            details = str(char.get("details") or "")
            if should_replace_character_name(raw_name):
                raw_name = infer_character_name(details, fallback=f"Character {i + 1}")
            fixed_chars.append({**char, "name": raw_name})
        state = {**state, "characters": fixed_chars}

    # Generate LLM summaries for characters
    state = _generate_summaries(state, persona_id=persona_id)

    payload = {
        "raw_idea": body.get("raw_idea", ""),
        "state": state,
        "meta": body.get("meta", {}),
    }
    saved = save_run_result(payload, filename=filename)

    source = str((payload.get("meta") or {}).get("source") or "").strip().lower()
    story_artifact = state.get("story_artifact")
    if source == "story" and isinstance(story_artifact, dict):
        _save_story_sub_artifacts(
            base_filename=str(saved.get("filename") or "story"),
            raw_idea=str(payload.get("raw_idea") or ""),
            story_artifact=story_artifact,
        )

    return saved


@router.post("/suggest-name")
async def suggest_name(body: Dict[str, Any]) -> Dict[str, str]:
    raw_idea: str = body.get("raw_idea", "")
    try:
        result = call_local_llm(SUGGEST_NAME_SYSTEM, raw_idea, max_length=32)
        name = _sanitize(result.strip().splitlines()[0])
    except Exception:
        name = "lorebook_run"
    return {"name": name}
