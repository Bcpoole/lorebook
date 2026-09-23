from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException


import re

from lorebook.api.storage import save_draft_state, update_character_role
from lorebook.characters import infer_character_name
from lorebook.characters.relationships import (
    _clean_relationship_label,
    _coerce_relationships,
    _inverse_relationship_label,
    _make_character_urn,
)
from lorebook.characters.service import _generate_character_only
from lorebook.config.prompts import get_persona_prompts
from lorebook.llm import call_local_llm
from lorebook.workflow.normalization import _normalize_state


router = APIRouter()


@router.post("/character")
async def generate_character_only(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    if not raw_idea:
        raise HTTPException(status_code=400, detail="raw_idea is required")

    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    max_length = int(experimentation_config.get("maxLength", 700))
    character = _generate_character_only(raw_idea, persona_id=persona_id, max_length=max_length)

    state = _normalize_state(raw_idea, body.get("state"))
    state["characters"] = [character]
    payload = {
        "raw_idea": raw_idea,
        "state": state,
        "meta": {"mode": "character"},
        "save_pending": bool(body.get("save_pending", False)),
    }
    save_draft_state(payload, "latest", artifact_type="character")
    return {"state": state, "character": character}


@router.post("/character-role")
async def set_character_role(body: Dict[str, Any]) -> Dict[str, Any]:
    run_id = str(body.get("run_id") or "").strip()
    role = str(body.get("role") or "").strip().lower()
    character_index = int(body.get("character_index", 0))
    artifact_type = str(body.get("artifact_type") or "").strip().lower()
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    if role not in {"character", "persona"}:
        raise HTTPException(status_code=400, detail="role must be character or persona")

    updated = update_character_role(
        run_id, character_index, role, artifact_type=artifact_type or None
    )
    if not updated:
        raise HTTPException(status_code=404, detail="run or character not found")
    return {"ok": True, "run": updated}


@router.post("/character-related")
async def generate_related_character(body: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a new character related to an existing one via a described relationship."""
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    max_length = int(experimentation_config.get("maxLength", 700))
    relationship: str = str(body.get("relationship") or "").strip()
    context: str = str(body.get("context") or "").strip()
    source_character_index: int = max(0, int(body.get("source_character_index", 0)))

    state = _normalize_state(raw_idea, body.get("state"))
    source_characters = state.get("characters", [])

    if source_character_index >= len(source_characters):
        raise HTTPException(status_code=400, detail="source_character_index is out of range")

    source_char = source_characters[source_character_index]
    source_name = str(source_char.get("name") or "the existing character")
    source_details = str(source_char.get("details") or "")

    relationship_label = _clean_relationship_label(relationship)
    if not relationship_label:
        raise HTTPException(status_code=400, detail="relationship description is required")

    prompts = get_persona_prompts(persona_id)
    related_system = getattr(prompts, "CHARACTER_RELATED_SYSTEM", prompts.CHARACTER_SYSTEM)

    prompt_parts = []
    if state.get("world_setting"):
        prompt_parts.append(f"World setting:\n{state['world_setting']}")
    prompt_parts.append(f"Existing character ({source_name}):\n{source_details}")
    prompt_parts.append(f"Relationship to create: {relationship}")
    prompt_parts.append(
        "Hard constraints:\n"
        "- Create a NEW, distinct person related to the existing character.\n"
        "- Do NOT rewrite or clone the existing character.\n"
        "- Use a different name, appearance, personality, and backstory.\n"
        "- Explicitly reflect the requested relationship in the new character profile."
    )
    if context:
        prompt_parts.append(f"Additional context:\n{context}")
    if raw_idea:
        prompt_parts.append(f"Original concept: {raw_idea}")
    prompt = "\n\n".join(prompt_parts)

    generated = call_local_llm(related_system, prompt, max_length=max_length)

    def _norm_text(value: str) -> str:
        return re.sub(r"\W+", " ", str(value or "").lower()).strip()

    source_norm = _norm_text(source_details)
    generated_norm = _norm_text(generated)
    if (
        source_norm
        and generated_norm
        and (
            generated_norm == source_norm
            or generated_norm in source_norm
            or source_norm in generated_norm
        )
    ):
        retry_prompt = (
            f"{prompt}\n\n"
            "CRITICAL RETRY: Your previous output repeated the source character.\n"
            "Return a clearly different related character with a unique identity and name."
        )
        generated = call_local_llm(related_system, retry_prompt, max_length=max_length)

    name = infer_character_name(generated, fallback=f"{relationship_label.title()} Ally")
    existing_names = {
        _norm_text(str(character.get("name") or ""))
        for character in source_characters
        if isinstance(character, dict)
    }
    normalized_name = _norm_text(name)
    if (
        not normalized_name
        or normalized_name in existing_names
        or normalized_name == _norm_text(source_name)
    ):
        base_name = f"{relationship_label.title()} Ally".strip()
        if not base_name:
            base_name = "Related Ally"
        candidate = base_name
        suffix = 2
        while _norm_text(candidate) in existing_names:
            candidate = f"{base_name} {suffix}"
            suffix += 1
        name = candidate

    inverse_relationship = _inverse_relationship_label(
        relationship_label=relationship_label,
        source_name=source_name,
        related_name=name,
        persona_id=persona_id,
    )
    new_characters = list(state.get("characters", []))
    updated_source = dict(new_characters[source_character_index])
    source_id = str(updated_source.get("id") or "").strip()
    if not source_id:
        source_id = _make_character_urn()
        updated_source["id"] = source_id

    source_relationships = _coerce_relationships(updated_source.get("relationships"))
    new_id = _make_character_urn()
    new_character: Dict[str, Any] = {
        "id": new_id,
        "name": name,
        "details": generated.strip(),
        "role": "character",
        "tags": [],
        "relationships": {source_id: relationship_label},
    }

    source_relationships[new_id] = inverse_relationship
    updated_source["relationships"] = source_relationships

    new_characters[source_character_index] = updated_source
    new_characters.append(new_character)
    state["characters"] = new_characters

    save_draft_state(
        {"raw_idea": raw_idea, "state": state, "meta": {"mode": "character"}, "save_pending": True},
        "latest",
        artifact_type="character",
    )
    return {"state": state, "character": new_character}
