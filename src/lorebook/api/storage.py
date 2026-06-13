from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def get_outputs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "outputs"


def get_runs_dir() -> Path:
    runs_dir = get_outputs_root() / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def get_drafts_dir() -> Path:
    drafts_dir = get_runs_dir() / "_drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    return drafts_dir


def _normalize_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    cleaned: list[str] = []
    for entry in raw_tags:
        if not isinstance(entry, str):
            continue
        tag = entry.strip().lower()
        if not tag:
            continue
        if tag not in cleaned:
            cleaned.append(tag)
    return cleaned


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def _preview_from_record(record: dict[str, Any]) -> dict[str, Any]:
    state = record.get("state") if isinstance(record.get("state"), dict) else {}
    story = state.get("story_artifact") if isinstance(state.get("story_artifact"), dict) else {}
    characters = state.get("characters") if isinstance(state.get("characters"), list) else []

    title = str(story.get("title") or record.get("raw_idea") or "Untitled run").strip()
    description = str(story.get("description") or state.get("world_setting") or "").strip()
    description = _trim_words(description, 128)

    story_tags = _normalize_tags(story.get("tags"))
    character_tags: list[str] = []
    avatar_data = ""
    avatar_name = ""
    for character in characters:
        if not isinstance(character, dict):
            continue
        if not avatar_data:
            avatar_data = str(character.get("image_data") or "")
            avatar_name = str(character.get("name") or "")
        character_tags.extend(_normalize_tags(character.get("tags")))
    tags = list(dict.fromkeys([*story_tags, *character_tags]))
    roles = [
        str(character.get("role") or "character")
        for character in characters
        if isinstance(character, dict)
    ]

    return {
        "run_id": str(record.get("run_id") or ""),
        "saved_at": str(record.get("saved_at") or ""),
        "title": title,
        "description": description,
        "tags": tags,
        "avatar_data": avatar_data,
        "avatar_name": avatar_name,
        "character_count": len([c for c in characters if isinstance(c, dict)]),
        "roles": roles,
        "story_present": bool(story),
    }


def save_run_result(payload: dict[str, Any], filename: str | None = None) -> dict[str, str]:
    if filename:
        safe = re.sub(r"[^\w\-]", "_", filename.strip())
        file_stem = safe if safe else uuid4().hex
    else:
        file_stem = uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    record = {
        "run_id": file_stem,
        "saved_at": started_at,
        "saved_at_ns": time.time_ns(),
        **payload,
    }
    record["preview"] = _preview_from_record(record)

    run_path = get_runs_dir() / f"{file_stem}.json"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return {
        "run_id": file_stem,
        "run_path": str(run_path),
        "filename": file_stem,
    }


def save_draft_state(payload: dict[str, Any], draft_id: str = "latest") -> dict[str, str]:
    record = {
        "draft_id": draft_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    draft_path = get_drafts_dir() / f"{draft_id}.json"
    draft_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {
        "draft_id": draft_id,
        "draft_path": str(draft_path),
    }


def load_run(run_id: str) -> dict[str, Any] | None:
    run_path = get_runs_dir() / f"{run_id}.json"
    if not run_path.exists():
        return None
    record = json.loads(run_path.read_text(encoding="utf-8"))
    if not isinstance(record.get("preview"), dict):
        record["preview"] = _preview_from_record(record)
    return record


def load_latest_run() -> dict[str, Any] | None:
    latest_record: dict[str, Any] | None = None
    latest_sort_key: tuple[str, int, str] | None = None
    for run_path in get_runs_dir().glob("*.json"):
        record = json.loads(run_path.read_text(encoding="utf-8"))
        if not isinstance(record.get("preview"), dict):
            record["preview"] = _preview_from_record(record)
        saved_at = str(record.get("saved_at", ""))
        saved_at_ns = int(record.get("saved_at_ns", 0))
        sort_key = (saved_at_ns, saved_at, run_path.stat().st_mtime_ns, run_path.name)
        if latest_record is None or latest_sort_key is None or sort_key > latest_sort_key:
            latest_record = record
            latest_sort_key = sort_key
    return latest_record


def load_draft_state(draft_id: str = "latest") -> dict[str, Any] | None:
    draft_path = get_drafts_dir() / f"{draft_id}.json"
    if not draft_path.exists():
        return None
    return json.loads(draft_path.read_text(encoding="utf-8"))


def delete_draft_state(draft_id: str = "latest") -> bool:
    draft_path = get_drafts_dir() / f"{draft_id}.json"
    if not draft_path.exists():
        return False
    draft_path.unlink()
    return True


def list_run_previews(search: str = "", tag: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    normalized_search = search.strip().lower()
    normalized_tag = tag.strip().lower()
    entries: list[dict[str, Any]] = []

    for run_path in get_runs_dir().glob("*.json"):
        if run_path.name.startswith("_"):
            continue
        record = json.loads(run_path.read_text(encoding="utf-8"))
        preview = record.get("preview") if isinstance(record.get("preview"), dict) else _preview_from_record(record)
        searchable = " ".join(
            [
                str(preview.get("title", "")),
                str(preview.get("description", "")),
                " ".join(str(t) for t in preview.get("tags", []) if isinstance(t, str)),
            ]
        ).lower()
        tags = [str(t).lower() for t in preview.get("tags", []) if isinstance(t, str)]
        if normalized_tag and normalized_tag not in tags:
            continue
        if normalized_search and normalized_search not in searchable:
            continue
        entries.append(preview)

    entries.sort(key=lambda item: str(item.get("saved_at", "")), reverse=True)
    total = len(entries)
    start = max(offset, 0)
    end = start + max(limit, 1)
    return {"total": total, "items": entries[start:end]}


def update_character_role(run_id: str, character_index: int, role: str) -> dict[str, Any] | None:
    run_path = get_runs_dir() / f"{run_id}.json"
    if not run_path.exists():
        return None

    record = json.loads(run_path.read_text(encoding="utf-8"))
    state = record.get("state")
    if not isinstance(state, dict):
        return None
    characters = state.get("characters")
    if not isinstance(characters, list):
        return None
    if character_index < 0 or character_index >= len(characters):
        return None
    if not isinstance(characters[character_index], dict):
        return None

    updated_character = dict(characters[character_index])
    updated_character["role"] = role
    characters[character_index] = updated_character
    state["characters"] = characters
    record["state"] = state
    record["preview"] = _preview_from_record(record)
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record
