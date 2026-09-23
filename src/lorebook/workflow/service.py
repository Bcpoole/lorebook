from __future__ import annotations

import os
from typing import Any

from lorebook.characters import infer_character_name, should_replace_character_name
from lorebook.characters.relationships import _coerce_relationships, _make_character_urn
from lorebook.config.prompts import get_persona_prompts
from lorebook.errors import InvalidRequestError
from lorebook.llm import call_local_llm
from lorebook.workflow.state import CharacterState, WizardState
from lorebook.workflow.text import (
    _clean_continued_output,
    _continuation_addition,
    _is_meta_response,
)


def _tokens(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, default))
    except ValueError:
        return default


LOREMASTER_MAX_TOKENS = _tokens("LOREBOOK_LOREMASTER_MAX_TOKENS", 2048)


CHARACTER_MAX_TOKENS = _tokens("LOREBOOK_CHARACTER_MAX_TOKENS", 2048)


EDITOR_MAX_TOKENS = _tokens("LOREBOOK_EDITOR_MAX_TOKENS", 512)


def _all_character_sections(state: WizardState) -> str:
    sections: list[str] = []
    for index, character in enumerate(state.get("characters", []), start=1):
        name = character.get("name") or f"Companion {index}"
        details = character.get("details", "")
        sections.append(f"Character {index} - {name}:\n{details}")
    return "\n\n".join(sections)


def _editor_prompt(state: WizardState) -> str:
    return f"Setting:\n{state['world_setting']}\n\nCharacters:\n{_all_character_sections(state)}"


def _continuation_prompt(
    stage: str, state: WizardState, directive: str = "", character_index: int = 0
) -> str:
    directive_block = f"\n\nInstruction:\n{directive}" if directive.strip() else ""

    if stage == "loremaster":
        return (
            f"Idea:\n{state['raw_idea']}\n\n"
            f"Current draft:\n{state.get('world_setting', '')}"
            f"{directive_block}\n\n"
            "Continue writing from the exact cutoff point. Do not restart or summarize."
        )

    if stage == "character_designer":
        current_details = ""
        characters = state.get("characters", [])
        if 0 <= character_index < len(characters):
            current_details = characters[character_index].get("details", "")
        return (
            f"World setting:\n{state.get('world_setting', '')}\n\n"
            f"Current character draft:\n{current_details}"
            f"{directive_block}\n\n"
            "Continue the same character sheet from the exact cutoff point. Do not restart."
        )

    if stage == "editor":
        return (
            f"{_editor_prompt(state)}"
            f"\n\nCurrent critique draft:\n{state.get('critique_notes', '')}"
            f"{directive_block}\n\n"
            "Continue the critique from the exact cutoff point. Do not restart or summarize."
        )

    return ""


def _stage_max_tokens(stage: str) -> int:
    if stage == "loremaster":
        return LOREMASTER_MAX_TOKENS
    if stage == "character_designer":
        return CHARACTER_MAX_TOKENS
    if stage == "editor":
        return EDITOR_MAX_TOKENS
    return LOREMASTER_MAX_TOKENS


def _next_stage_from_editor(state: WizardState) -> str:
    return "save_assets" if state.get("passed_inspection") else "loremaster"


def _upsert_character(state: WizardState, index: int, details: str) -> list[CharacterState]:
    characters = [dict(character) for character in state.get("characters", [])]
    while len(characters) <= index:
        characters.append(
            {"id": _make_character_urn(), "name": "", "details": "", "relationships": {}}
        )

    base = characters[index]
    if not str(base.get("id") or "").strip():
        base["id"] = _make_character_urn()
    base["relationships"] = _coerce_relationships(base.get("relationships"))
    base["details"] = details
    inferred_name = infer_character_name(details, fallback=base.get("name", ""))
    if should_replace_character_name(base.get("name", "")):
        base["name"] = inferred_name or f"Character {index + 1}"
    characters[index] = base
    return characters


def _run_stage_sync(
    state: WizardState,
    stage: str,
    continue_output: bool = False,
    directive: str = "",
    character_index: int = 0,
    experimentation_config: dict[str, Any] | None = None,
) -> str:
    config = experimentation_config or {}
    max_length = int(config.get("maxLength", _stage_max_tokens(stage)))
    llm_endpoint = config.get("llmEndpoint") or None
    prompts = get_persona_prompts(config.get("persona_id", "blank"))

    if stage == "loremaster":
        prior_text = state.get("world_setting", "")
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = state["raw_idea"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"
        generated = call_local_llm(
            prompts.LOREMASTER_SYSTEM,
            prompt,
            max_length=max_length,
            endpoint=llm_endpoint,
        )
        addition = _continuation_addition(prior_text, generated) if continue_output else generated
        output = f"{prior_text}{addition}" if continue_output else addition
        state["world_setting"] = _clean_continued_output(output)
        return "character_designer"

    if stage == "character_designer":
        if not state.get("world_setting"):
            raise InvalidRequestError("world_setting is required for character_designer")

        characters = state.get("characters", [])
        current_details = ""
        if 0 <= character_index < len(characters):
            current_details = characters[character_index].get("details", "")

        if continue_output:
            prompt = _continuation_prompt(
                stage, state, directive=directive, character_index=character_index
            )
        else:
            prompt = state["world_setting"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = call_local_llm(
            prompts.CHARACTER_SYSTEM,
            prompt,
            max_length=max_length,
            endpoint=llm_endpoint,
        )

        # Guardrail: reject meta responses and retry with stronger instruction
        if not continue_output and _is_meta_response(generated):
            retry_prompt = (
                f"{state['world_setting']}\n\n"
                f"Create a detailed character card for a companion in this world. "
                f"Include: name, physical description, personality, background, skills, and role."
            )
            generated = call_local_llm(
                prompts.CHARACTER_SYSTEM,
                retry_prompt,
                max_length=max_length,
                endpoint=llm_endpoint,
            )

        addition = (
            _continuation_addition(current_details, generated) if continue_output else generated
        )
        details = f"{current_details}{addition}" if continue_output else addition
        details = _clean_continued_output(details)
        state["characters"] = _upsert_character(state, character_index, details)
        return "editor"

    if stage == "editor":
        if not state.get("world_setting"):
            raise InvalidRequestError("world_setting is required for editor")
        if not state.get("characters"):
            raise InvalidRequestError("characters are required for editor")
        if continue_output and state.get("passed_inspection"):
            return _next_stage_from_editor(state)

        prior_critique = state.get("critique_notes", "")

        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = _editor_prompt(state)
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = call_local_llm(
            prompts.EDITOR_SYSTEM,
            prompt,
            max_length=max_length,
            endpoint=llm_endpoint,
        )
        addition = (
            _continuation_addition(prior_critique, generated) if continue_output else generated
        )
        critique = f"{state.get('critique_notes', '')}{addition}" if continue_output else addition
        critique = _clean_continued_output(critique)
        passed = "PASSED" in critique
        state["passed_inspection"] = passed
        state["critique_notes"] = critique
        return _next_stage_from_editor(state)

    raise InvalidRequestError(f"Unsupported stage: {stage}")
