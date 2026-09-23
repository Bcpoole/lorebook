from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter


from lorebook.api.storage import delete_draft_state, load_latest_drafts, save_draft_state
from lorebook.llm import is_local_llm_available


router = APIRouter()


@router.get("/restore-latest")
async def restore_latest() -> Dict[str, Any]:
    drafts = load_latest_drafts("latest")
    return {
        "draft": drafts.get("world"),
        "story_draft": drafts.get("story"),
        "character_draft": drafts.get("character"),
    }


@router.get("/health")
async def app_health() -> Dict[str, Any]:
    return {
        "status": "ok",
    }


@router.get("/health/llm")
async def llm_health() -> Dict[str, Any]:
    return {
        "connected": is_local_llm_available(),
    }


@router.post("/draft")
async def save_draft(body: Dict[str, Any]) -> Dict[str, Any]:
    artifact_type = str(body.get("artifact_type") or "world").strip().lower()
    if bool(body.get("clear", False)):
        deleted = delete_draft_state("latest", artifact_type=artifact_type)
        return {
            "ok": True,
            "cleared": True,
            "deleted": deleted,
        }

    payload = {
        "raw_idea": body.get("raw_idea", ""),
        "state": body.get("state", {}),
        "meta": body.get("meta", {}),
        "save_pending": bool(body.get("save_pending", False)),
    }
    saved = save_draft_state(payload, "latest", artifact_type=artifact_type)
    return {
        **saved,
        "ok": True,
    }
