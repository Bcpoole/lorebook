from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query


from lorebook.api.storage import find_character_by_urn, list_run_previews, load_run, toggle_favorite


router = APIRouter()


@router.get("/runs/{run_id}")
async def get_run_by_id(run_id: str, artifact_type: str = Query("")) -> Dict[str, Any]:
    record = load_run(run_id, artifact_type=artifact_type or None)
    if not record:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return record


@router.get("/characters/by-id")
async def get_character_by_id(urn: str = Query(..., min_length=1)) -> Dict[str, Any]:
    resolved = find_character_by_urn(urn)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"character {urn} not found")
    return resolved


@router.get("/gallery")
async def list_gallery_runs(
    search: str = "",
    tag: str = "",
    favorites_only: bool = False,
    artifact_type: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    listing = list_run_previews(
        search=search,
        tag=tag,
        favorites_only=favorites_only,
        artifact_type=artifact_type or None,
        limit=limit,
        offset=offset,
    )
    return {
        "items": listing["items"],
        "total": listing["total"],
        "limit": limit,
        "offset": offset,
    }


@router.post("/gallery/{run_id}/favorite")
async def toggle_run_favorite(run_id: str, artifact_type: str = Query("")) -> Dict[str, Any]:
    """Toggle the favorite flag on a gallery run."""
    record = toggle_favorite(run_id, artifact_type=artifact_type or None)
    if not record:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return {"ok": True, "run_id": run_id, "favorite": bool(record.get("favorite", False))}
