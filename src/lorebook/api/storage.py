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
_STORY_ENTITY_STRIP_KEYS = frozenset({"image_prompt", "image_prompt_styled", "image_style", "image_data"})
# Rename image_path → image_file on disk
_CHAR_RENAME_KEYS = {"image_path": "image_file"}
# State-level keys to strip before saving to disk
_STATE_STRIP_KEYS = frozenset({"critique_notes", "passed_inspection", "_lastNode"})
ARTIFACT_TYPES = ("world", "character", "story", "location", "object")
DEFAULT_ARTIFACT_TYPE = "world"
_SOURCE_TO_ARTIFACT = {
    "story": "story",
    "character": "character",
    "character-page": "character",
    "location": "location",
    "object": "object",
    "location-page": "location",
    "object-page": "object",
}
_MODE_TO_ARTIFACT = {
    "story": "story",
    "character": "character",
    "world": "world",
    "location": "location",
    "object": "object",
}
DRAFT_SNAPSHOT_ID = "snapshot"


def get_outputs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "outputs"


def get_user_root() -> Path:
    """Persistent user-curated artefact directory (gitignored, never auto-written by the app).

    Lives at ``user/artefacts/`` beside ``outputs/`` and mirrors its subdirectory
    structure.  Derived from :func:`get_outputs_root` so that test monkeypatches of
    ``get_outputs_root`` automatically isolate the user root too.
    """
    return get_outputs_root().parent / "user" / "artefacts"


def _normalize_artifact_type(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in ARTIFACT_TYPES:
        return candidate
    return DEFAULT_ARTIFACT_TYPE


def _artifact_type_from_meta(meta: Any) -> str:
    if isinstance(meta, dict):
        explicit_raw = str(meta.get("artifact_type") or "").strip().lower()
        if explicit_raw in ARTIFACT_TYPES:
            return explicit_raw
        source = str(meta.get("source") or "").strip().lower()
        if source in _SOURCE_TO_ARTIFACT:
            return _SOURCE_TO_ARTIFACT[source]
        mode = str(meta.get("mode") or "").strip().lower()
        if mode in _MODE_TO_ARTIFACT:
            return _MODE_TO_ARTIFACT[mode]
    return DEFAULT_ARTIFACT_TYPE


def _artifact_type_from_payload(payload: dict[str, Any], explicit_artifact_type: str | None = None) -> str:
    if explicit_artifact_type is not None:
        return _normalize_artifact_type(explicit_artifact_type)
    if "artifact_type" in payload:
        payload_raw = str(payload.get("artifact_type") or "").strip().lower()
        if payload_raw in ARTIFACT_TYPES:
            return payload_raw
    return _artifact_type_from_meta(payload.get("meta"))


def get_runs_dir(artifact_type: str | None = None) -> Path:
    artifact_dir = get_outputs_root() / _normalize_artifact_type(artifact_type)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def get_drafts_dir(artifact_type: str | None = None) -> Path:
    drafts_dir = get_runs_dir(artifact_type) / "_drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    return drafts_dir


def _artifact_dir(run_id: str, artifact_type: str) -> Path:
    return get_runs_dir(artifact_type) / run_id


def _artifact_record_path(run_id: str, artifact_type: str) -> Path:
    return _artifact_dir(run_id, artifact_type) / "artifact.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp.{uuid4().hex}")
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _story_section_payloads(story: dict[str, Any]) -> dict[str, Any]:
    return {
        "overview": {
            "title": str(story.get("title") or ""),
            "description": str(story.get("description") or ""),
            "setting": str(story.get("setting") or ""),
            "style": str(story.get("style") or ""),
            "tags": story.get("tags") if isinstance(story.get("tags"), list) else [],
        },
        "plot": story.get("plot") if isinstance(story.get("plot"), list) else [],
        "characters_artifact": story.get("characters_artifact") if isinstance(story.get("characters_artifact"), list) else [],
        "locations": story.get("locations") if isinstance(story.get("locations"), list) else [],
        "objects": story.get("objects") if isinstance(story.get("objects"), list) else [],
        "opening": {"opening": str(story.get("opening") or "")},
        "examples": story.get("examples") if isinstance(story.get("examples"), list) else [],
    }


def _story_item_slug(section_name: str, item: Any, index: int) -> str:
    if not isinstance(item, dict):
        return f"{section_name}_{index + 1}"
    base = ""
    if section_name == "examples":
        base = str(item.get("label") or item.get("text") or "")
    else:
        base = str(item.get("name") or "")
    cleaned = re.sub(r"[^\w\-]+", "_", base.strip().lower()).strip("_")
    if not cleaned:
        cleaned = f"{section_name}_{index + 1}"
    return cleaned


def _world_character_slug(character: Any, index: int) -> str:
    if not isinstance(character, dict):
        return f"character_{index + 1}"
    base = str(character.get("name") or f"character_{index + 1}")
    cleaned = re.sub(r"[^\w\-]+", "_", base.strip().lower()).strip("_")
    if not cleaned:
        cleaned = f"character_{index + 1}"
    return cleaned


def _write_world_sections(sections_dir: Path, state: dict[str, Any]) -> None:
    sections_dir.mkdir(parents=True, exist_ok=True)
    _clear_artifact_dir(sections_dir)

    _write_json_atomic(
        sections_dir / "world_setting.json",
        {"section": "world_setting", "data": str(state.get("world_setting") or "")},
    )

    characters_dir = sections_dir / "characters"
    characters_dir.mkdir(parents=True, exist_ok=True)
    used_slugs: set[str] = set()
    characters = state.get("characters") if isinstance(state.get("characters"), list) else []
    for index, character in enumerate(characters):
        slug_base = _world_character_slug(character, index)
        slug = slug_base
        suffix = 2
        while slug in used_slugs:
            slug = f"{slug_base}_{suffix}"
            suffix += 1
        used_slugs.add(slug)
        payload = _clean_character_for_disk(character) if isinstance(character, dict) else {}
        _write_json_atomic(
            characters_dir / f"{slug}.json",
            {"section": "characters", "index": index, "slug": slug, "data": payload},
        )


def _load_world_sections(sections_dir: Path) -> dict[str, Any] | None:
    if not sections_dir.exists() or not sections_dir.is_dir():
        return None

    world_state: dict[str, Any] = {}
    setting_record = _read_json(sections_dir / "world_setting.json")
    if isinstance(setting_record, dict):
        world_state["world_setting"] = str(setting_record.get("data") or "")

    characters_dir = sections_dir / "characters"
    if characters_dir.exists() and characters_dir.is_dir():
        records: list[tuple[int, str, Any]] = []
        for item_path in characters_dir.glob("*.json"):
            record = _read_json(item_path)
            if not isinstance(record, dict):
                continue
            index = int(record.get("index", 10_000))
            slug = str(record.get("slug") or item_path.stem)
            records.append((index, slug, record.get("data")))
        records.sort(key=lambda entry: (entry[0], entry[1]))
        world_state["characters"] = [
            entry[2] if isinstance(entry[2], dict) else {}
            for entry in records
        ]

    return world_state if world_state else None


def _story_item_image_source(item: dict[str, Any]) -> tuple[bytes, str] | None:
    data_uri = _decode_image_data_uri(str(item.get("image_data") or ""))
    if data_uri is not None:
        return data_uri

    for key in ("image_path", "image_name", "image_file"):
        source_path = _source_image_path(str(item.get(key) or ""))
        if source_path is None:
            continue
        try:
            return source_path.read_bytes(), source_path.suffix.lower() or ".png"
        except OSError:
            continue
    return None


def _story_item_mime_from_suffix(suffix: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(str(suffix).lower(), "image/png")


def _story_item_for_disk(section_name: str, item: Any, section_dir: Path, slug: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    cleaned = dict(item)
    image_payload = _story_item_image_source(cleaned)
    for volatile_key in ("image_prompt", "image_prompt_styled", "image_style", "image_data", "image_path", "image_file"):
        cleaned.pop(volatile_key, None)
    if image_payload is None:
        cleaned.pop("image_name", None)
        return cleaned

    image_bytes, extension = image_payload
    safe_extension = extension if extension in {".png", ".jpg", ".jpeg", ".webp", ".gif"} else ".png"
    image_name = f"{slug}{safe_extension}"
    (section_dir / image_name).write_bytes(image_bytes)
    cleaned["image_name"] = image_name
    return cleaned


def _story_item_with_image_data(item: Any, section_dir: Path) -> Any:
    if not isinstance(item, dict):
        return item
    image_name = _safe_artifact_image_name(str(item.get("image_name") or ""))
    if not image_name:
        return item
    image_path = section_dir / image_name
    if not image_path.exists() or not image_path.is_file():
        return item
    try:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    except OSError:
        return item
    return {
        **item,
        "image_data": f"data:{_story_item_mime_from_suffix(image_path.suffix)};base64,{encoded}",
    }


def _clean_story_item_for_record(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    cleaned = dict(item)
    image_name = _safe_artifact_image_name(str(cleaned.get("image_name") or ""))
    if not image_name:
        image_name = _safe_artifact_image_name(str(cleaned.get("image_path") or ""))
    if not image_name:
        image_name = _safe_artifact_image_name(str(cleaned.get("image_file") or ""))
    for key in ("image_prompt", "image_prompt_styled", "image_style", "image_data", "image_path", "image_file"):
        cleaned.pop(key, None)
    if image_name:
        cleaned["image_name"] = image_name
    else:
        cleaned.pop("image_name", None)
    return cleaned


def _clean_story_artifact_for_record(story: Any) -> Any:
    if not isinstance(story, dict):
        return story
    cleaned = dict(story)
    for list_key in ("characters_artifact", "locations", "objects", "examples"):
        items = cleaned.get(list_key)
        if not isinstance(items, list):
            continue
        cleaned[list_key] = [_clean_story_item_for_record(item) for item in items]
    return cleaned


def _clean_story_state_for_record(state: Any) -> Any:
    if not isinstance(state, dict):
        return state
    cleaned = dict(state)
    cleaned["story_artifact"] = _clean_story_artifact_for_record(cleaned.get("story_artifact"))
    return cleaned


def _write_story_sections(sections_dir: Path, story: dict[str, Any]) -> None:
    sections_dir.mkdir(parents=True, exist_ok=True)
    _clear_artifact_dir(sections_dir)
    section_payloads = _story_section_payloads(story)
    list_sections = {"characters_artifact", "locations", "objects", "examples"}
    for section_name, section_payload in section_payloads.items():
        if section_name in list_sections:
            section_dir = sections_dir / section_name
            section_dir.mkdir(parents=True, exist_ok=True)
            used_slugs: set[str] = set()
            items = section_payload if isinstance(section_payload, list) else []
            for index, item in enumerate(items):
                slug_base = _story_item_slug(section_name, item, index)
                slug = slug_base
                suffix = 2
                while slug in used_slugs:
                    slug = f"{slug_base}_{suffix}"
                    suffix += 1
                used_slugs.add(slug)
                persisted_item = _story_item_for_disk(section_name, item, section_dir, slug)
                section_path = section_dir / f"{slug}.json"
                _write_json_atomic(
                    section_path,
                    {"section": section_name, "index": index, "slug": slug, "data": persisted_item},
                )
            continue
        section_path = sections_dir / f"{section_name}.json"
        _write_json_atomic(section_path, {"section": section_name, "data": section_payload})


def _load_story_sections(sections_dir: Path) -> dict[str, Any] | None:
    if not sections_dir.exists() or not sections_dir.is_dir():
        return None

    section_map: dict[str, Any] = {}
    list_sections = {"characters_artifact", "locations", "objects", "examples"}
    for section_name in ("overview", "plot", "characters_artifact", "locations", "objects", "opening", "examples"):
        if section_name in list_sections:
            section_dir = sections_dir / section_name
            if not section_dir.exists() or not section_dir.is_dir():
                continue
            records: list[tuple[int, str, Any]] = []
            for item_path in section_dir.glob("*.json"):
                record = _read_json(item_path)
                if not isinstance(record, dict):
                    continue
                index = int(record.get("index", 10_000))
                slug = str(record.get("slug") or item_path.stem)
                data = _story_item_with_image_data(record.get("data"), section_dir)
                records.append((index, slug, data))
            records.sort(key=lambda entry: (entry[0], entry[1]))
            section_map[section_name] = [entry[2] for entry in records]
            continue

        record = _read_json(sections_dir / f"{section_name}.json")
        if not isinstance(record, dict):
            continue
        section_map[section_name] = record.get("data")

    if not section_map:
        return None

    story: dict[str, Any] = {}
    overview = section_map.get("overview")
    if isinstance(overview, dict):
        for key in ("title", "description", "setting", "style", "tags"):
            if key in overview:
                story[key] = overview.get(key)
    for list_key in ("plot", "characters_artifact", "locations", "objects", "examples"):
        if isinstance(section_map.get(list_key), list):
            story[list_key] = section_map[list_key]
    opening = section_map.get("opening")
    if isinstance(opening, dict):
        story["opening"] = str(opening.get("opening") or "")
    return story if story else None


def _story_from_state(state: Any) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    story = state.get("story_artifact")
    if not isinstance(story, dict):
        return None
    return story


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _clear_artifact_dir(path: Path) -> None:
    if not path.exists():
        return
    for nested in sorted(path.glob("**/*"), key=lambda entry: len(entry.parts), reverse=True):
        if nested.is_file():
            nested.unlink()
        elif nested.is_dir():
            try:
                nested.rmdir()
            except OSError:
                continue


def _iter_run_files() -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    for artifact_type in ARTIFACT_TYPES:
        # Primary outputs directory (app-written)
        for run_path in get_runs_dir(artifact_type).glob("*/artifact.json"):
            candidates.append((run_path, artifact_type))
        # User-curated directory (manually placed, permanent)
        user_type_dir = get_user_root() / artifact_type
        if user_type_dir.is_dir():
            for run_path in user_type_dir.glob("*/artifact.json"):
                candidates.append((run_path, artifact_type))
    return candidates


def _resolve_run_path(run_id: str, artifact_type: str | None = None) -> tuple[Path, str] | None:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        return None

    if artifact_type:
        normalized_artifact_type = _normalize_artifact_type(artifact_type)
        direct_path = _artifact_record_path(normalized_run_id, normalized_artifact_type)
        if direct_path.exists():
            return direct_path, normalized_artifact_type
        # Also check user/ directory
        user_path = get_user_root() / normalized_artifact_type / normalized_run_id / "artifact.json"
        if user_path.exists():
            return user_path, normalized_artifact_type
        return None

    matches: list[tuple[Path, str]] = []
    for run_path, run_artifact_type in _iter_run_files():
        if run_path.parent.name == normalized_run_id:
            matches.append((run_path, run_artifact_type))
    if not matches:
        return None

    matches.sort(key=lambda item: item[0].stat().st_mtime_ns, reverse=True)
    return matches[0]


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


def _safe_artifact_image_name(image_file: str) -> str | None:
    raw = str(image_file or "").strip()
    if not raw:
        return None
    source = Path(raw)
    if source.is_absolute():
        return None
    parts = source.parts
    if any(part in {"", ".", ".."} for part in parts):
        return None
    if len(parts) > 1:
        source = Path(parts[-1])
    image_name = source.name.strip()
    if not image_name:
        return None
    suffix = Path(image_name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return None
    return image_name


def _image_data_from_file(image_file: str, artifact_type: str, run_id: str) -> str:
    """Load image bytes from disk and return a data URI.

    Checks outputs/{type}/{run_id}/ first, then user/{type}/{run_id}/.
    """
    image_name = _safe_artifact_image_name(image_file)
    if not image_name:
        return ""

    candidates = [
        _artifact_dir(run_id, artifact_type) / image_name,
        get_user_root() / artifact_type / run_id / image_name,
    ]
    image_path = next((p for p in candidates if p.exists() and p.is_file()), None)
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


def _source_image_path(image_ref: str) -> Path | None:
    raw = str(image_ref or "").strip()
    if not raw:
        return None
    source = Path(raw)
    if source.is_absolute():
        return source if source.exists() and source.is_file() else None
    candidate = get_outputs_root() / source
    if candidate.exists() and candidate.is_file():
        return candidate
    images_candidate = get_outputs_root() / "images" / source
    if images_candidate.exists() and images_candidate.is_file():
        return images_candidate
    return None


def _decode_image_data_uri(image_data: str) -> tuple[bytes, str] | None:
    raw = str(image_data or "").strip()
    if not raw or "," not in raw:
        return None
    header, encoded = raw.split(",", maxsplit=1)
    if ";base64" not in header:
        return None
    match = re.match(r"^data:image/(?P<ext>[a-zA-Z0-9]+);base64$", header.strip())
    extension = f".{(match.group('ext') if match else 'png').lower()}"
    if extension == ".jpeg":
        extension = ".jpg"
    try:
        return base64.b64decode(encoded), extension
    except Exception:
        return None


def _read_source_image(raw_character: dict[str, Any], cleaned_character: dict[str, Any]) -> tuple[bytes, str] | None:
    data_uri = _decode_image_data_uri(str(raw_character.get("image_data") or ""))
    if data_uri is not None:
        return data_uri

    for key in ("image_path", "image_file"):
        source_path = _source_image_path(str(raw_character.get(key) or ""))
        if source_path is None:
            continue
        try:
            return source_path.read_bytes(), source_path.suffix.lower() or ".png"
        except OSError:
            continue

    source_path = _source_image_path(str(cleaned_character.get("image_file") or ""))
    if source_path is None:
        return None
    try:
        return source_path.read_bytes(), source_path.suffix.lower() or ".png"
    except OSError:
        return None


def _read_story_entity_source_image(raw_entity: dict[str, Any], cleaned_entity: dict[str, Any]) -> tuple[bytes, str] | None:
    data_uri = _decode_image_data_uri(str(raw_entity.get("image_data") or ""))
    if data_uri is not None:
        return data_uri

    for key in ("image_path", "image_file", "image_name"):
        source_path = _source_image_path(str(raw_entity.get(key) or ""))
        if source_path is None:
            continue
        try:
            return source_path.read_bytes(), source_path.suffix.lower() or ".png"
        except OSError:
            continue

    for key in ("image_name", "image_file"):
        source_path = _source_image_path(str(cleaned_entity.get(key) or ""))
        if source_path is None:
            continue
        try:
            return source_path.read_bytes(), source_path.suffix.lower() or ".png"
        except OSError:
            continue
    return None


def _materialize_character_images(
    raw_state: dict[str, Any],
    cleaned_state: dict[str, Any],
    artifact_type: str,
    run_id: str,
) -> None:
    raw_characters = raw_state.get("characters")
    cleaned_characters = cleaned_state.get("characters")
    if not isinstance(raw_characters, list) or not isinstance(cleaned_characters, list):
        return

    target_dir = _artifact_dir(run_id, artifact_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    for index, raw_character in enumerate(raw_characters):
        if index >= len(cleaned_characters):
            break
        cleaned_character = cleaned_characters[index]
        if not isinstance(raw_character, dict) or not isinstance(cleaned_character, dict):
            continue

        image_payload = _read_source_image(raw_character, cleaned_character)
        if image_payload is None:
            cleaned_character.pop("image_file", None)
            continue

        image_bytes, extension = image_payload
        safe_extension = extension if extension in {".png", ".jpg", ".jpeg", ".webp", ".gif"} else ".png"
        image_name = f"{run_id}{'' if index == 0 else f'_{index + 1}'}{safe_extension}"
        image_path = target_dir / image_name
        image_path.write_bytes(image_bytes)
        cleaned_character["image_file"] = image_name


def _materialize_story_entity_images(
    raw_state: dict[str, Any],
    cleaned_state: dict[str, Any],
    artifact_type: str,
    run_id: str,
) -> None:
    raw_story = raw_state.get("story_artifact")
    cleaned_story = cleaned_state.get("story_artifact")
    if not isinstance(raw_story, dict) or not isinstance(cleaned_story, dict):
        return

    target_dir = _artifact_dir(run_id, artifact_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    for section in ("characters_artifact", "locations", "objects"):
        raw_items = raw_story.get(section)
        cleaned_items = cleaned_story.get(section)
        if not isinstance(raw_items, list) or not isinstance(cleaned_items, list):
            continue

        for index, raw_item in enumerate(raw_items):
            if index >= len(cleaned_items):
                break
            cleaned_item = cleaned_items[index]
            if not isinstance(raw_item, dict) or not isinstance(cleaned_item, dict):
                continue

            image_payload = _read_story_entity_source_image(raw_item, cleaned_item)
            if image_payload is None:
                cleaned_item.pop("image_name", None)
                continue

            image_bytes, extension = image_payload
            safe_extension = extension if extension in {".png", ".jpg", ".jpeg", ".webp", ".gif"} else ".png"
            image_name = f"{run_id}_{section}_{index + 1}{safe_extension}"
            image_path = target_dir / image_name
            image_path.write_bytes(image_bytes)
            cleaned_item["image_name"] = image_name


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


def _clean_story_entity_for_disk(entity: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in entity.items():
        if key in _STORY_ENTITY_STRIP_KEYS:
            continue
        if key == "image_path":
            out["image_name"] = value
            continue
        if key == "image_file":
            out["image_name"] = value
            continue
        out[key] = value
    return out


def _clean_story_artifact_for_disk(story_artifact: dict[str, Any]) -> dict[str, Any]:
    out = dict(story_artifact)
    for section in ("characters_artifact", "locations", "objects"):
        entries = out.get(section)
        if isinstance(entries, list):
            out[section] = [
                _clean_story_entity_for_disk(entry) if isinstance(entry, dict) else entry
                for entry in entries
            ]
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
    story_artifact = out.get("story_artifact")
    if isinstance(story_artifact, dict):
        out["story_artifact"] = _clean_story_artifact_for_disk(story_artifact)
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
    artifact_type = _normalize_artifact_type(record.get("artifact_type"))
    run_id = str(record.get("run_id") or "").strip()
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
    avatar_summary = ""
    roles = [
        str(character.get("role") or "character")
        for character in characters
        if isinstance(character, dict)
    ]

    if artifact_type == "location":
        locations = story.get("locations") if isinstance(story.get("locations"), list) else []
        first_location = locations[0] if locations and isinstance(locations[0], dict) else {}
        title = str(first_location.get("name") or title).strip() or title
        description = _trim_words(
            str(first_location.get("description") or first_location.get("summary") or description).strip(),
            128,
        )
        avatar_name = str(first_location.get("name") or "").strip()
        avatar_summary = str(first_location.get("summary") or first_location.get("description") or "").strip()
        avatar_data = str(first_location.get("image_data") or "")
        if not avatar_data and run_id:
            avatar_data = _image_data_from_file(
                str(first_location.get("image_name") or first_location.get("image_file") or ""),
                artifact_type=artifact_type,
                run_id=run_id,
            )
        tags = list(dict.fromkeys([*story_tags, *_normalize_tags(first_location.get("tags"))]))
    elif artifact_type == "object":
        objects = story.get("objects") if isinstance(story.get("objects"), list) else []
        first_object = objects[0] if objects and isinstance(objects[0], dict) else {}
        title = str(first_object.get("name") or title).strip() or title
        description = _trim_words(
            str(first_object.get("description") or first_object.get("summary") or description).strip(),
            128,
        )
        avatar_name = str(first_object.get("name") or "").strip()
        avatar_summary = str(first_object.get("summary") or first_object.get("description") or "").strip()
        avatar_data = str(first_object.get("image_data") or "")
        if not avatar_data and run_id:
            avatar_data = _image_data_from_file(
                str(first_object.get("image_name") or first_object.get("image_file") or ""),
                artifact_type=artifact_type,
                run_id=run_id,
            )
        tags = list(dict.fromkeys([*story_tags, *_normalize_tags(first_object.get("tags"))]))
    else:
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
                avatar_data = str(character.get("image_data") or "")
                if not avatar_data and run_id:
                    avatar_data = _image_data_from_file(
                        str(character.get("image_file") or ""),
                        artifact_type=artifact_type,
                        run_id=run_id,
                    )
            character_tags.extend(_normalize_tags(character.get("tags")))

        if not avatar_name and artifact_type == "character":
            story_characters = story.get("characters_artifact") if isinstance(story.get("characters_artifact"), list) else []
            first_story_character = (
                story_characters[0]
                if story_characters and isinstance(story_characters[0], dict)
                else {}
            )
            avatar_name = str(first_story_character.get("name") or "").strip()
            avatar_summary = str(first_story_character.get("summary") or "").strip()
            if not avatar_data:
                avatar_data = str(first_story_character.get("image_data") or "")
                if not avatar_data and run_id:
                    avatar_data = _image_data_from_file(
                        str(first_story_character.get("image_name") or first_story_character.get("image_file") or ""),
                        artifact_type=artifact_type,
                        run_id=run_id,
                    )
            character_tags.extend(_normalize_tags(first_story_character.get("tags")))
            if not roles:
                role = str(first_story_character.get("role") or "character")
                roles = [role]

        tags = list(dict.fromkeys([*story_tags, *character_tags]))

    return {
        "run_id": str(record.get("run_id") or ""),
        "artifact_type": _normalize_artifact_type(record.get("artifact_type")),
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


def save_run_result(
    payload: dict[str, Any],
    filename: str | None = None,
    artifact_type: str | None = None,
) -> dict[str, str]:
    if filename:
        safe = re.sub(r"[^\w\-]", "_", filename.strip())
        file_stem = safe if safe else uuid4().hex
    else:
        file_stem = uuid4().hex

    # Carry forward any existing favorite flag
    existing_favorite = bool(payload.get("favorite", False))

    started_at = datetime.now(timezone.utc).isoformat()
    raw_state = payload.get("state") or {}
    resolved_artifact_type = _artifact_type_from_payload(payload, explicit_artifact_type=artifact_type)
    # Clean state before writing to disk
    clean_state = _clean_state_for_disk(raw_state)
    if resolved_artifact_type == "story":
        clean_state = _clean_story_state_for_record(clean_state)
    meta = payload.get("meta") or {}
    # Only keep meta.source
    meta_disk = {k: v for k, v in meta.items() if k == "source"}

    run_dir = _artifact_dir(file_stem, resolved_artifact_type)
    run_dir.mkdir(parents=True, exist_ok=True)
    _clear_artifact_dir(run_dir)

    _materialize_character_images(raw_state, clean_state, resolved_artifact_type, file_stem)
    _materialize_story_entity_images(raw_state, clean_state, resolved_artifact_type, file_stem)

    record: dict[str, Any] = {
        "run_id": file_stem,
        "artifact_type": resolved_artifact_type,
        "saved_at": started_at,
        "saved_at_ns": time.time_ns(),
        "raw_idea": payload.get("raw_idea", ""),
        "state": clean_state,
        "meta": meta_disk,
        "favorite": existing_favorite,
    }
    record["preview"] = _preview_from_record(record)

    run_path = _artifact_record_path(file_stem, resolved_artifact_type)
    _write_json_atomic(run_path, record)
    if resolved_artifact_type == "story":
        story = _story_from_state(raw_state)
        if isinstance(story, dict):
            _write_story_sections(run_dir / "story_sections", story)
    elif resolved_artifact_type == "world":
        if isinstance(clean_state, dict):
            _write_world_sections(run_dir / "world_sections", clean_state)

    return {
        "run_id": file_stem,
        "artifact_type": resolved_artifact_type,
        "run_path": str(run_path),
        "filename": file_stem,
    }


def save_draft_state(
    payload: dict[str, Any],
    draft_id: str = "latest",
    artifact_type: str | None = None,
) -> dict[str, str]:
    resolved_artifact_type = _artifact_type_from_payload(payload, explicit_artifact_type=artifact_type)
    record = {
        "draft_id": draft_id,
        "artifact_type": resolved_artifact_type,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    if resolved_artifact_type == "story":
        record["state"] = _clean_story_state_for_record(record.get("state"))
    draft_path = get_drafts_dir(resolved_artifact_type) / f"{draft_id}.json"
    _write_json_atomic(draft_path, record)
    if resolved_artifact_type == "story":
        story = _story_from_state(payload.get("state"))
        sections_dir = get_drafts_dir(resolved_artifact_type) / f"{draft_id}_story_sections"
        if isinstance(story, dict):
            _write_story_sections(sections_dir, story)
        elif sections_dir.exists():
            _clear_artifact_dir(sections_dir)
            sections_dir.rmdir()
    elif resolved_artifact_type == "world":
        state = record.get("state") if isinstance(record.get("state"), dict) else {}
        sections_dir = get_drafts_dir(resolved_artifact_type) / f"{draft_id}_world_sections"
        _write_world_sections(sections_dir, _clean_state_for_disk(state))

    if draft_id == "latest":
        snapshot_record = {**record, "draft_id": DRAFT_SNAPSHOT_ID}
        snapshot_path = get_drafts_dir(resolved_artifact_type) / f"{DRAFT_SNAPSHOT_ID}.json"
        _write_json_atomic(snapshot_path, snapshot_record)
        if resolved_artifact_type == "story":
            story = _story_from_state(payload.get("state"))
            snapshot_sections_dir = get_drafts_dir(resolved_artifact_type) / f"{DRAFT_SNAPSHOT_ID}_story_sections"
            if isinstance(story, dict):
                _write_story_sections(snapshot_sections_dir, story)
            elif snapshot_sections_dir.exists():
                _clear_artifact_dir(snapshot_sections_dir)
                snapshot_sections_dir.rmdir()
        elif resolved_artifact_type == "world":
            state = snapshot_record.get("state") if isinstance(snapshot_record.get("state"), dict) else {}
            snapshot_sections_dir = get_drafts_dir(resolved_artifact_type) / f"{DRAFT_SNAPSHOT_ID}_world_sections"
            _write_world_sections(snapshot_sections_dir, _clean_state_for_disk(state))
    return {
        "draft_id": draft_id,
        "artifact_type": resolved_artifact_type,
        "draft_path": str(draft_path),
    }


def load_run(run_id: str, artifact_type: str | None = None) -> dict[str, Any] | None:
    resolved = _resolve_run_path(run_id, artifact_type=artifact_type)
    if resolved is None:
        return None
    run_path, resolved_artifact_type = resolved
    record = _read_json(run_path)
    if not isinstance(record, dict):
        return None
    if not str(record.get("artifact_type", "")).strip():
        record["artifact_type"] = resolved_artifact_type
    if resolved_artifact_type == "story":
        story_sections = _load_story_sections(run_path.parent / "story_sections")
        state = record.get("state") if isinstance(record.get("state"), dict) else {}
        state["story_artifact"] = story_sections if isinstance(story_sections, dict) else {}
        record["state"] = state
    elif resolved_artifact_type == "world":
        world_sections = _load_world_sections(run_path.parent / "world_sections")
        state = record.get("state") if isinstance(record.get("state"), dict) else {}
        section_data = world_sections if isinstance(world_sections, dict) else {}
        state["world_setting"] = str(section_data.get("world_setting") or "")
        state["characters"] = (
            section_data.get("characters")
            if isinstance(section_data.get("characters"), list)
            else []
        )
        record["state"] = state
    state = record.get("state")
    if isinstance(state, dict):
        repaired_state, changed = _repair_character_names(state)
        if changed:
            record["state"] = repaired_state
            record["preview"] = _preview_from_record(record)
            _write_json_atomic(run_path, record)
            return record
    if not isinstance(record.get("preview"), dict):
        record["preview"] = _preview_from_record(record)
    return record


def load_latest_run() -> dict[str, Any] | None:
    latest_record: dict[str, Any] | None = None
    latest_sort_key: tuple[str, int, str] | None = None
    for run_path, artifact_type in _iter_run_files():
        record = _read_json(run_path)
        if not isinstance(record, dict):
            continue
        if not str(record.get("artifact_type", "")).strip():
            record["artifact_type"] = artifact_type
        if not isinstance(record.get("preview"), dict):
            record["preview"] = _preview_from_record(record)
        saved_at = str(record.get("saved_at", ""))
        saved_at_ns = int(record.get("saved_at_ns", 0))
        sort_key = (saved_at_ns, saved_at, run_path.stat().st_mtime_ns, run_path.name)
        if latest_record is None or latest_sort_key is None or sort_key > latest_sort_key:
            latest_record = record
            latest_sort_key = sort_key
    return latest_record


def load_draft_state(draft_id: str = "latest", artifact_type: str | None = None) -> dict[str, Any] | None:
    resolved_artifact_type = _normalize_artifact_type(artifact_type)
    draft_path = get_drafts_dir(resolved_artifact_type) / f"{draft_id}.json"
    record = _read_json(draft_path)
    if record is None and draft_id == "latest":
        snapshot_path = get_drafts_dir(resolved_artifact_type) / f"{DRAFT_SNAPSHOT_ID}.json"
        record = _read_json(snapshot_path)
    if not isinstance(record, dict):
        return None
    if not str(record.get("artifact_type", "")).strip():
        record["artifact_type"] = resolved_artifact_type
    if resolved_artifact_type == "story":
        loaded_draft_id = str(record.get("draft_id") or draft_id)
        sections_dir = get_drafts_dir(resolved_artifact_type) / f"{loaded_draft_id}_story_sections"
        story_sections = _load_story_sections(sections_dir)
        state = record.get("state") if isinstance(record.get("state"), dict) else {}
        state["story_artifact"] = story_sections if isinstance(story_sections, dict) else {}
        record["state"] = state
    elif resolved_artifact_type == "world":
        loaded_draft_id = str(record.get("draft_id") or draft_id)
        sections_dir = get_drafts_dir(resolved_artifact_type) / f"{loaded_draft_id}_world_sections"
        world_sections = _load_world_sections(sections_dir)
        state = record.get("state") if isinstance(record.get("state"), dict) else {}
        section_data = world_sections if isinstance(world_sections, dict) else {}
        state["world_setting"] = str(section_data.get("world_setting") or "")
        state["characters"] = (
            section_data.get("characters")
            if isinstance(section_data.get("characters"), list)
            else []
        )
        record["state"] = state
    return record


def delete_draft_state(draft_id: str = "latest", artifact_type: str | None = None) -> bool:
    resolved_artifact_type = _normalize_artifact_type(artifact_type)
    draft_path = get_drafts_dir(resolved_artifact_type) / f"{draft_id}.json"
    deleted = False
    if draft_path.exists():
        draft_path.unlink()
        deleted = True
    story_sections_dir = get_drafts_dir(resolved_artifact_type) / f"{draft_id}_story_sections"
    if story_sections_dir.exists():
        _clear_artifact_dir(story_sections_dir)
        story_sections_dir.rmdir()
        deleted = True
    world_sections_dir = get_drafts_dir(resolved_artifact_type) / f"{draft_id}_world_sections"
    if world_sections_dir.exists():
        _clear_artifact_dir(world_sections_dir)
        world_sections_dir.rmdir()
        deleted = True
    if draft_id == "latest":
        snapshot_path = get_drafts_dir(resolved_artifact_type) / f"{DRAFT_SNAPSHOT_ID}.json"
        if snapshot_path.exists():
            snapshot_path.unlink()
            deleted = True
        snapshot_sections_dir = get_drafts_dir(resolved_artifact_type) / f"{DRAFT_SNAPSHOT_ID}_story_sections"
        if snapshot_sections_dir.exists():
            _clear_artifact_dir(snapshot_sections_dir)
            snapshot_sections_dir.rmdir()
            deleted = True
        snapshot_world_sections_dir = get_drafts_dir(resolved_artifact_type) / f"{DRAFT_SNAPSHOT_ID}_world_sections"
        if snapshot_world_sections_dir.exists():
            _clear_artifact_dir(snapshot_world_sections_dir)
            snapshot_world_sections_dir.rmdir()
            deleted = True
    return deleted


def delete_artifact(artifact_id: str, artifact_type: str | None = None) -> bool:
    """Delete an artifact folder and all its contents by ID."""
    resolved_artifact_type = _normalize_artifact_type(artifact_type)
    run_entry = _resolve_run_path(artifact_id, resolved_artifact_type)
    if not run_entry:
        return False
    run_path, _ = run_entry
    artifact_folder = run_path.parent
    if artifact_folder.exists():
        import shutil

        shutil.rmtree(artifact_folder)
        return True
    return False


def load_latest_drafts(draft_id: str = "latest") -> dict[str, dict[str, Any] | None]:
    return {artifact_type: load_draft_state(draft_id=draft_id, artifact_type=artifact_type) for artifact_type in ARTIFACT_TYPES}


def list_run_previews(
    search: str = "",
    tag: str = "",
    favorites_only: bool = False,
    artifact_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    normalized_search = search.strip().lower()
    normalized_tag = tag.strip().lower()
    normalized_artifact_type = _normalize_artifact_type(artifact_type) if artifact_type else ""
    entries: list[dict[str, Any]] = []

    for run_path, artifact_type in _iter_run_files():
        if run_path.name.startswith("_"):
            continue
        record = _read_json(run_path)
        if not isinstance(record, dict):
            continue
        if not str(record.get("artifact_type", "")).strip():
            record["artifact_type"] = artifact_type
        state = record.get("state")
        if isinstance(state, dict):
            repaired_state, changed = _repair_character_names(state)
            if changed:
                record["state"] = repaired_state
        preview = _preview_from_record(record)
        if normalized_artifact_type and preview.get("artifact_type") != normalized_artifact_type:
            continue
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

    for run_path, artifact_type in _iter_run_files():
        if run_path.name.startswith("_"):
            continue
        record = _read_json(run_path)
        if not isinstance(record, dict):
            continue
        state = record.get("state")
        if not isinstance(state, dict):
            continue
        characters = state.get("characters")
        if not isinstance(characters, list):
            continue

        run_id = str(record.get("run_id") or run_path.parent.name)
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
                image_data = _image_data_from_file(
                    str(character.get("image_file") or ""),
                    artifact_type=_normalize_artifact_type(record.get("artifact_type") or artifact_type),
                    run_id=run_id,
                )

            return {
                "run_id": run_id,
                "artifact_type": _normalize_artifact_type(record.get("artifact_type") or artifact_type),
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


def update_character_role(
    run_id: str,
    character_index: int,
    role: str,
    artifact_type: str | None = None,
) -> dict[str, Any] | None:
    resolved = _resolve_run_path(run_id, artifact_type=artifact_type)
    if resolved is None:
        return None
    run_path, resolved_artifact_type = resolved

    record = _read_json(run_path)
    if not isinstance(record, dict):
        return None
    if not str(record.get("artifact_type", "")).strip():
        record["artifact_type"] = resolved_artifact_type
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
    _write_json_atomic(run_path, record)
    return record


def toggle_favorite(run_id: str, artifact_type: str | None = None) -> dict[str, Any] | None:
    """Toggle the favorite flag on a run and return the updated record."""
    resolved = _resolve_run_path(run_id, artifact_type=artifact_type)
    if resolved is None:
        return None
    run_path, resolved_artifact_type = resolved
    record = _read_json(run_path)
    if not isinstance(record, dict):
        return None
    if not str(record.get("artifact_type", "")).strip():
        record["artifact_type"] = resolved_artifact_type
    record["favorite"] = not bool(record.get("favorite", False))
    record["preview"] = _preview_from_record(record)
    # Sync favorite into preview so it persists
    record["preview"]["favorite"] = record["favorite"]
    _write_json_atomic(run_path, record)
    return record
