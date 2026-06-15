from __future__ import annotations

import base64
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from lorebook.characters import infer_character_name, should_replace_character_name

# Fields that are volatile / large and must never be written to disk for characters
_CHAR_STRIP_KEYS = frozenset({"image_prompt", "image_prompt_styled", "image_style", "image_data"})
# Rename image_path → image_file on disk
_CHAR_RENAME_KEYS = {"image_path": "image_file"}
# State-level keys to strip before saving to disk
_STATE_STRIP_KEYS = frozenset({"critique_notes", "passed_inspection", "_lastNode"})


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


def _image_data_from_file(image_file: str) -> str:
    """Load image bytes from disk and return a data URI."""
    raw = (image_file or "").strip()
    if not raw:
        return ""

    outputs_root = get_outputs_root()
    candidates: list[Path] = []
    source = Path(raw)
    if source.is_absolute():
        candidates.append(source)
    else:
        candidates.append(outputs_root / source)
        candidates.append(outputs_root / "images" / source)

    image_path: Path | None = None
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            image_path = candidate
            break
    if image_path is None:
        return ""

    try:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    except OSError:
        return ""

    suffix = image_path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/png")
    return f"data:{mime};base64,{encoded}"


def _make_character_urn() -> str:
    return f"urn:lorebook:character:{uuid4().hex}"


def _make_run_urn() -> str:
    return f"urn:lorebook:run:{uuid4().hex}"


def _clean_character_for_disk(char: dict[str, Any]) -> dict[str, Any]:
    """Strip volatile fields and rename image_path → image_file for disk storage."""
    out: dict[str, Any] = {}
    for key, value in char.items():
        if key in _CHAR_STRIP_KEYS:
            continue
        disk_key = _CHAR_RENAME_KEYS.get(key, key)
        out[disk_key] = value
    # Ensure every saved character has a URN id
    if not out.get("id"):
        out["id"] = _make_character_urn()
    relationships = char.get("relationships")
    cleaned_relationships: dict[str, str] = {}
    if isinstance(relationships, dict):
        for raw_target, raw_relationship in relationships.items():
            target = str(raw_target).strip()
            label = _trim_words(str(raw_relationship).strip(), 7)
            if not target or not label:
                continue
            cleaned_relationships[target] = label
    out["relationships"] = cleaned_relationships
    return out


def _clean_state_for_disk(state: dict[str, Any]) -> dict[str, Any]:
    """Strip ephemeral state fields before writing to disk."""
    out = {k: v for k, v in state.items() if k not in _STATE_STRIP_KEYS}
    raw_chars = out.get("characters")
    if isinstance(raw_chars, list):
        out["characters"] = [
            _clean_character_for_disk(c) if isinstance(c, dict) else c
            for c in raw_chars
        ]
    return out


def _repair_character_names(state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Repair placeholder character names from details content."""
    characters = state.get("characters")
    if not isinstance(characters, list):
        return state, False

    changed = False
    repaired: list[Any] = []
    for idx, character in enumerate(characters, start=1):
        if not isinstance(character, dict):
            repaired.append(character)
            continue
        updated = dict(character)
        current_name = str(updated.get("name") or "")
        if should_replace_character_name(current_name):
            inferred = infer_character_name(str(updated.get("details") or ""), fallback=f"Character {idx}")
            if inferred and inferred != current_name:
                updated["name"] = inferred
                changed = True
        repaired.append(updated)

    if not changed:
        return state, False
    return {**state, "characters": repaired}, True


def _preview_from_record(record: dict[str, Any]) -> dict[str, Any]:
    state = record.get("state") if isinstance(record.get("state"), dict) else {}
    story = state.get("story_artifact") if isinstance(state.get("story_artifact"), dict) else {}
    characters = state.get("characters") if isinstance(state.get("characters"), list) else []

    title = str(story.get("title") or record.get("raw_idea") or "Untitled run").strip()
    description = str(story.get("description") or state.get("world_setting") or "").strip()
    description = _trim_words(description, 128)

    story_tags = _normalize_tags(story.get("tags"))
    character_tags: list[str] = []
    # Use the first character for identity text, and first available image_data for avatar
    avatar_data = ""
    avatar_name = ""
    avatar_summary = ""
    avatar_identity_selected = False
    for character in characters:
        if not isinstance(character, dict):
            continue
        if not avatar_identity_selected:
            raw_name = str(character.get("name") or "")
            if should_replace_character_name(raw_name):
                raw_name = infer_character_name(str(character.get("details") or ""), fallback="")
            avatar_name = raw_name
            avatar_summary = str(character.get("summary") or "")
            avatar_identity_selected = True
        if not avatar_data:
            # image_data is present in live state; image_file is on disk path
            avatar_data = str(character.get("image_data") or "")
            if not avatar_data:
                avatar_data = _image_data_from_file(str(character.get("image_file") or ""))
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
        "avatar_summary": avatar_summary,
        "character_count": len([c for c in characters if isinstance(c, dict)]),
        "roles": roles,
        "favorite": bool(record.get("favorite", False)),
    }


def save_run_result(payload: dict[str, Any], filename: str | None = None) -> dict[str, str]:
    if filename:
        safe = re.sub(r"[^\w\-]", "_", filename.strip())
        file_stem = safe if safe else uuid4().hex
    else:
        file_stem = uuid4().hex

    # Carry forward any existing favorite flag
    existing_favorite = bool(payload.get("favorite", False))

    started_at = datetime.now(timezone.utc).isoformat()
    # Clean state before writing to disk
    clean_state = _clean_state_for_disk(payload.get("state") or {})
    meta = payload.get("meta") or {}
    # Only keep meta.source
    meta_disk = {k: v for k, v in meta.items() if k == "source"}

    record: dict[str, Any] = {
        "run_id": file_stem,
        "saved_at": started_at,
        "saved_at_ns": time.time_ns(),
        "raw_idea": payload.get("raw_idea", ""),
        "state": clean_state,
        "meta": meta_disk,
        "favorite": existing_favorite,
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
    state = record.get("state")
    if isinstance(state, dict):
        repaired_state, changed = _repair_character_names(state)
        if changed:
            record["state"] = repaired_state
            record["preview"] = _preview_from_record(record)
            run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            return record
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


def list_run_previews(
    search: str = "",
    tag: str = "",
    favorites_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    normalized_search = search.strip().lower()
    normalized_tag = tag.strip().lower()
    entries: list[dict[str, Any]] = []

    for run_path in get_runs_dir().glob("*.json"):
        if run_path.name.startswith("_"):
            continue
        record = json.loads(run_path.read_text(encoding="utf-8"))
        state = record.get("state")
        if isinstance(state, dict):
            repaired_state, changed = _repair_character_names(state)
            if changed:
                record["state"] = repaired_state
        preview = _preview_from_record(record)
        # Merge run-level favorite into preview (in case preview was built before favorite was set)
        preview["favorite"] = bool(record.get("favorite", preview.get("favorite", False)))
        if favorites_only and not preview.get("favorite"):
            continue
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


def find_character_by_urn(character_urn: str) -> dict[str, Any] | None:
    target = str(character_urn or "").strip()
    if not target:
        return None

    for run_path in get_runs_dir().glob("*.json"):
        if run_path.name.startswith("_"):
            continue
        record = json.loads(run_path.read_text(encoding="utf-8"))
        state = record.get("state")
        if not isinstance(state, dict):
            continue
        characters = state.get("characters")
        if not isinstance(characters, list):
            continue

        run_id = str(record.get("run_id") or run_path.stem)
        for index, character in enumerate(characters):
            if not isinstance(character, dict):
                continue
            current_id = str(character.get("id") or "").strip()
            if current_id != target:
                continue

            name = str(character.get("name") or "").strip()
            if should_replace_character_name(name):
                name = infer_character_name(str(character.get("details") or ""), fallback=f"Character {index + 1}")

            relationships = character.get("relationships")
            cleaned_relationships: dict[str, str] = {}
            if isinstance(relationships, dict):
                for raw_target, raw_relationship in relationships.items():
                    target_id = str(raw_target).strip()
                    label = _trim_words(str(raw_relationship).strip(), 7)
                    if not target_id or not label:
                        continue
                    cleaned_relationships[target_id] = label

            image_data = str(character.get("image_data") or "")
            if not image_data:
                image_data = _image_data_from_file(str(character.get("image_file") or ""))

            return {
                "run_id": run_id,
                "character_index": index,
                "character": {
                    "id": current_id,
                    "name": name,
                    "details": str(character.get("details") or ""),
                    "summary": str(character.get("summary") or ""),
                    "role": str(character.get("role") or ""),
                    "tags": _normalize_tags(character.get("tags")),
                    "relationships": cleaned_relationships,
                    "image_data": image_data,
                },
            }
    return None


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


def toggle_favorite(run_id: str) -> dict[str, Any] | None:
    """Toggle the favorite flag on a run and return the updated record."""
    run_path = get_runs_dir() / f"{run_id}.json"
    if not run_path.exists():
        return None
    record = json.loads(run_path.read_text(encoding="utf-8"))
    record["favorite"] = not bool(record.get("favorite", False))
    record["preview"] = _preview_from_record(record)
    # Sync favorite into preview so it persists
    record["preview"]["favorite"] = record["favorite"]
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record
