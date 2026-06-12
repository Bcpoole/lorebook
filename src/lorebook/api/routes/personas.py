"""API routes for listing personas and serving their avatars."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from lorebook.config.prompts import AVATARS_DIR, list_personas

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("")
async def get_personas() -> list[dict]:
    """Return metadata for all registered personas."""
    result = []
    for meta in list_personas():
        result.append(
            {
                "id": meta.id,
                "name": meta.name,
                "description": meta.description,
                "tags": meta.tags,
                "avatarUrl": f"/api/personas/{meta.id}/avatar" if meta.avatar else None,
            }
        )
    return result


@router.get("/{persona_id}/avatar")
async def get_persona_avatar(persona_id: str) -> FileResponse:
    """Serve the avatar image for a persona."""
    # Only allow simple alphanumeric + hyphen/underscore ids to prevent path traversal
    if not persona_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid persona id")

    for ext in (".svg", ".png", ".jpg", ".webp"):
        candidate = AVATARS_DIR / f"{persona_id}{ext}"
        if candidate.exists():
            return FileResponse(str(candidate))

    raise HTTPException(status_code=404, detail="Avatar not found")
