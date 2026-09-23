from __future__ import annotations

from lorebook.characters import infer_character_name
from lorebook.characters.relationships import _make_character_urn
from lorebook.config.prompts import get_persona_prompts
from lorebook.llm import call_local_llm
from lorebook.workflow.state import CharacterState


def _generate_character_only(
    raw_idea: str, persona_id: str, max_length: int = 700
) -> CharacterState:
    prompts = get_persona_prompts(persona_id)
    generated = call_local_llm(prompts.CHARACTER_SYSTEM, raw_idea, max_length=max_length)
    name = infer_character_name(generated, fallback="Companion")
    return {
        "id": _make_character_urn(),
        "name": name,
        "details": generated.strip(),
        "role": "character",
        "tags": [],
        "relationships": {},
    }
