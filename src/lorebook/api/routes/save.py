from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict

from fastapi import APIRouter

from lorebook.api.storage import save_run_result
from lorebook.llm import call_local_llm

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


@router.post("/save")
async def save_run(body: Dict[str, Any]) -> Dict[str, Any]:
    filename: str | None = body.get("filename") or None
    payload = {
        "raw_idea": body.get("raw_idea", ""),
        "state": body.get("state", {}),
        "meta": body.get("meta", {}),
    }
    return save_run_result(payload, filename=filename)


@router.post("/suggest-name")
async def suggest_name(body: Dict[str, Any]) -> Dict[str, str]:
    raw_idea: str = body.get("raw_idea", "")
    try:
        result = call_local_llm(SUGGEST_NAME_SYSTEM, raw_idea, max_length=32)
        name = _sanitize(result.strip().splitlines()[0])
    except Exception:
        name = "lorebook_run"
    return {"name": name}
