"""Prompt resolution and fallback management.

Handles getting the effective prompt for a persona, with fallback to template
if the persona's prompt is empty.
"""
from __future__ import annotations

from lorebook.config.personas import load_persona
from lorebook.config.prompts import get_template_persona
from lorebook.config.prompts._types import PROMPT_KEYS


def get_prompt(persona_id: str, prompt_key: str) -> str:
    """Get the effective system prompt for a persona and prompt key.
    
    If the persona has a non-empty value for this prompt, returns it.
    Otherwise, falls back to the template value.
    
    Args:
        persona_id: The persona ID (e.g., "blank", "my-custom")
        prompt_key: The prompt key (e.g., "loremaster_system")
    
    Returns:
        The effective system prompt string.
    """
    template = get_template_persona()
    
    # Try to load persisted persona
    persona = load_persona(persona_id)
    
    if prompt_key not in PROMPT_KEYS:
        return ""

    template_value = template.prompts.get(prompt_key)
    if not persona:
        return template_value

    value = persona.prompts.get(prompt_key)
    return value if value.strip() else template_value


# Legacy backward compat - map old string exports to prompt keys
_PROMPT_KEY_MAP = {
    "LOREMASTER_SYSTEM": "loremaster_system",
    "CHARACTER_SYSTEM": "character_system",
    "EDITOR_SYSTEM": "editor_system",
    "SD_PROMPT_SYSTEM": "sd_prompt_system",
    "REVIEW_SUMMARY_SYSTEM": "review_summary_system",
    "CHARACTER_SUMMARY_SYSTEM": "character_summary_system",
    "CHARACTER_RELATED_SYSTEM": "character_related_system",
}


def get_prompt_by_name(persona_id: str, prompt_name: str) -> str:
    """Get prompt by old-style name (backward compat).
    
    Args:
        persona_id: The persona ID
        prompt_name: The prompt constant name (e.g., "LOREMASTER_SYSTEM")
    
    Returns:
        The effective system prompt string.
    """
    prompt_key = _PROMPT_KEY_MAP.get(prompt_name, "")
    if prompt_key:
        return get_prompt(persona_id, prompt_key)
    return ""
