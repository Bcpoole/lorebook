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
