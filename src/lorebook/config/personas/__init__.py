"""Persona persistence and CRUD management.

Personas can be stored locally as JSON files in outputs/personas/{persona_id}/
This module handles loading, saving, and listing persisted personas.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from lorebook.config.prompts._types import PersonaMeta, PersonaPrompts


def get_personas_dir() -> Path:
    """Get the primary (app-written) personas storage directory."""
    outputs = Path(__file__).resolve().parents[4] / "outputs" / "personas"
    outputs.mkdir(parents=True, exist_ok=True)
    return outputs


def get_user_personas_dir() -> Path:
    """Get the user-curated personas directory (read-only for the app)."""
    return Path(__file__).resolve().parents[4] / "user" / "personas"


def _decode_image_data_uri(image_data: str) -> tuple[bytes, str] | None:
    raw = str(image_data or "").strip()
    if not raw.startswith("data:image/") or "," not in raw:
        return None
    header, encoded = raw.split(",", 1)
    if ";base64" not in header:
        return None
    match = re.match(r"^data:image/(?P<ext>[a-zA-Z0-9]+);base64$", header.strip())
    if not match:
        return None
    extension = match.group("ext").lower()
    try:
        return base64.b64decode(encoded), extension
    except (ValueError, binascii.Error):
        return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_persona_from_dir(persona_id: str, personas_root: Path) -> PersonaMeta | None:
    """Load a persona from a specific root directory."""
    persona_dir = personas_root / persona_id
    meta_file = persona_dir / "meta.json"

    if not meta_file.exists():
        return None

    try:
        with open(meta_file) as f:
            data = json.load(f)

        prompts = PersonaPrompts()
        prompts_file = persona_dir / "prompts.json"
        if prompts_file.exists():
            with open(prompts_file) as f:
                prompts_data = json.load(f)
                if not isinstance(prompts_data, dict):
                    raise ValueError("prompts.json must be a prompt-key dictionary")
                prompts = PersonaPrompts.from_dict(prompts_data)

        return PersonaMeta(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            tags=data.get("tags", []),
            favorite=bool(data.get("favorite", False)),
            avatar=data.get("avatar", ""),
            created=str(data.get("created", "")),
            modified=str(data.get("modified", "")),
            prompts=prompts,
        )
    except (json.JSONDecodeError, KeyError, IOError, ValueError):
        return None


def load_persona(persona_id: str) -> PersonaMeta | None:
    """Load a persona by ID from disk.

    Checks outputs/personas/ first, then user/personas/.
    Returns PersonaMeta with prompts, or None if not found.
    """
    persona = _load_persona_from_dir(persona_id, get_personas_dir())
    if persona is not None:
        return persona
    user_dir = get_user_personas_dir()
    if user_dir.is_dir():
        return _load_persona_from_dir(persona_id, user_dir)
    return None


def save_persona(persona: PersonaMeta) -> bool:
    """Save a persona to disk.
    
    Creates outputs/personas/{persona_id}/ directory structure with meta.json and prompts.json.
    Returns True on success, False on failure.
    """
    persona_dir = get_personas_dir() / persona.id
    persona_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        existing_created = ""
        meta_file = persona_dir / "meta.json"
        if meta_file.exists():
            with open(meta_file) as f:
                existing_meta = json.load(f)
                existing_created = str(existing_meta.get("created", "")).strip()

        now_iso = _utc_now_iso()
        created = str(persona.created or "").strip() or existing_created or now_iso
        modified = now_iso
        persona.created = created
        persona.modified = modified

        avatar_value = str(persona.avatar or "").strip()
        avatar_data = _decode_image_data_uri(avatar_value)
        if avatar_data:
            image_bytes, extension = avatar_data
            avatar_filename = f"avatar.{extension}"
            (persona_dir / avatar_filename).write_bytes(image_bytes)
            persona.avatar = avatar_filename
            # Remove stale avatar files with different extensions.
            for stale in persona_dir.glob("avatar.*"):
                if stale.name != avatar_filename:
                    stale.unlink(missing_ok=True)
        elif avatar_value.startswith("data:"):
            # Unsupported data URI format; do not persist invalid avatar value.
            persona.avatar = ""
        elif not avatar_value:
            for stale in persona_dir.glob("avatar.*"):
                stale.unlink(missing_ok=True)

        # Save meta.json
        meta_data = {
            "id": persona.id,
            "name": persona.name,
            "description": persona.description,
            "tags": persona.tags,
            "favorite": bool(persona.favorite),
            "avatar": persona.avatar,
            "created": created,
            "modified": modified,
        }
        with open(persona_dir / "meta.json", "w") as f:
            json.dump(meta_data, f, indent=2)
        
        # Save prompts.json as prompts-only payload; id is implied by directory name.
        prompts_data = persona.prompts.to_dict()
        with open(persona_dir / "prompts.json", "w") as f:
            json.dump(prompts_data, f, indent=2)

        legacy_persona_file = persona_dir / "persona.json"
        if legacy_persona_file.exists():
            legacy_persona_file.unlink(missing_ok=True)
        
        return True
    except (IOError, json.JSONDecodeError, ValueError, TypeError):
        return False


def list_personas() -> list[PersonaMeta]:
    """List all persisted personas from outputs/personas/ and user/personas/."""
    seen_ids: set[str] = set()
    personas: list[PersonaMeta] = []

    def _collect_from_dir(root: Path) -> None:
        if not root.exists():
            return
        for persona_dir in root.iterdir():
            if not persona_dir.is_dir():
                continue
            pid = persona_dir.name
            if pid in seen_ids:
                continue  # outputs/ takes priority; skip user/ duplicate
            persona = _load_persona_from_dir(pid, root)
            if persona:
                seen_ids.add(pid)
                personas.append(persona)

    _collect_from_dir(get_personas_dir())
    _collect_from_dir(get_user_personas_dir())
    return sorted(personas, key=lambda p: p.name)


def delete_persona(persona_id: str) -> bool:
    """Delete a persona from disk.
    
    Returns True if deletion succeeded or persona didn't exist, False on error.
    """
    persona_dir = get_personas_dir() / persona_id
    if not persona_dir.exists():
        return True
    
    try:
        import shutil
        shutil.rmtree(persona_dir)
        return True
    except IOError:
        return False
