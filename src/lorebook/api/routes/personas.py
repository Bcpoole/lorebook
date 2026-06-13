"""API routes for listing personas and serving their avatars."""
from __future__ import annotations

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

    meta = next((persona for persona in list_personas() if persona.id == persona_id), None)
    if meta is None or not meta.avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")

    candidate = (AVATARS_DIR / meta.avatar).resolve()
    avatars_root = AVATARS_DIR.resolve()
    if avatars_root not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")

    return FileResponse(
        str(candidate),
        headers={
            # Personas can be edited during local dev, so avoid stale browser caching.
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
