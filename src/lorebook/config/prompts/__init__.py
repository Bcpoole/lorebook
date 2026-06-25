"""Persona/prompt registry with local override support.

Each persona is a Python module that exposes:
  META              – PersonaMeta instance
  LOREMASTER_SYSTEM – str
  CHARACTER_SYSTEM  – str
  EDITOR_SYSTEM     – str
  SD_PROMPT_SYSTEM  – str
  REVIEW_SUMMARY_SYSTEM – str

The built-in baseline is ``default.py``. For local customization, create
``blank.py`` beside this file; it will be preferred over ``default.py``.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from typing import Dict, List

from ._types import PersonaMeta, PersonaPrompt, PersonaPrompts


def _load_blank_module() -> ModuleType:
    try:
        return import_module(".blank", __name__)
    except ModuleNotFoundError as exc:
        if exc.name != f"{__name__}.blank":
            raise
        return import_module(".default", __name__)


_blank_module = _load_blank_module()

# ---------------------------------------------------------------------------
# Registry – add new persona modules here
# ---------------------------------------------------------------------------
_PERSONA_MODULES: Dict[str, ModuleType] = {
    "blank": _blank_module,
}

AVATARS_DIR = Path(__file__).parent / "avatars"

_FALLBACK_ID = "blank"


def list_personas() -> List[PersonaMeta]:
    """Return metadata for built-in plus persisted personas."""
    from lorebook.config.personas import list_personas as list_persisted_personas

    builtins = [m.META for m in _PERSONA_MODULES.values()]
    persisted = [p for p in list_persisted_personas() if p.id not in {m.id for m in builtins}]
    return builtins + persisted


def get_persona_prompts(persona_id: str) -> ModuleType:
    """Return prompts for *persona_id* with persisted overrides and template fallback."""
    from lorebook.config.personas import load_persona

    module = _PERSONA_MODULES.get(persona_id)
    if module is not None:
        return module

    persisted = load_persona(persona_id)
    if persisted is None:
        return _blank_module

    template = get_template_persona().prompts
    return SimpleNamespace(
        META=persisted,
        LOREMASTER_SYSTEM=persisted.prompts.loremaster_system.strip() or template.loremaster_system,
        CHARACTER_SYSTEM=persisted.prompts.character_system.strip() or template.character_system,
        EDITOR_SYSTEM=persisted.prompts.editor_system.strip() or template.editor_system,
        SD_PROMPT_SYSTEM=persisted.prompts.sd_prompt_system.strip() or template.sd_prompt_system,
        REVIEW_SUMMARY_SYSTEM=persisted.prompts.review_summary_system.strip() or template.review_summary_system,
        CHARACTER_SUMMARY_SYSTEM=persisted.prompts.character_summary_system.strip() or template.character_summary_system,
        CHARACTER_RELATED_SYSTEM=persisted.prompts.character_related_system.strip() or template.character_related_system,
    )


def get_template_persona() -> PersonaMeta:
    """Return the template persona with all default PersonaPrompt objects.
    
    This is the baseline used for creating new personas or as fallback
    when a prompt is empty in a custom persona.
    """
    template_module = _blank_module
    return PersonaMeta(
        id="blank",
        name="Blank",
        description="Template prompts for local customization.",
        tags=["template", "neutral", "structured"],
        avatar="",
        prompts=PersonaPrompts(
            loremaster_system=template_module.LOREMASTER_SYSTEM,
            character_system=template_module.CHARACTER_SYSTEM,
            editor_system=template_module.EDITOR_SYSTEM,
            sd_prompt_system=template_module.SD_PROMPT_SYSTEM,
            review_summary_system=template_module.REVIEW_SUMMARY_SYSTEM,
            character_summary_system=getattr(template_module, "CHARACTER_SUMMARY_SYSTEM", ""),
            character_related_system=getattr(template_module, "CHARACTER_RELATED_SYSTEM", ""),
        ),
    )


# ---------------------------------------------------------------------------
# Package-level re-exports (backward-compat with existing imports)
# ---------------------------------------------------------------------------
LOREMASTER_SYSTEM = _blank_module.LOREMASTER_SYSTEM
CHARACTER_SYSTEM = _blank_module.CHARACTER_SYSTEM
EDITOR_SYSTEM = _blank_module.EDITOR_SYSTEM
SD_PROMPT_SYSTEM = _blank_module.SD_PROMPT_SYSTEM
REVIEW_SUMMARY_SYSTEM = _blank_module.REVIEW_SUMMARY_SYSTEM
CHARACTER_SUMMARY_SYSTEM = getattr(_blank_module, "CHARACTER_SUMMARY_SYSTEM", "")
CHARACTER_RELATED_SYSTEM = getattr(_blank_module, "CHARACTER_RELATED_SYSTEM", "")

__all__ = [
    "PersonaMeta",
    "PersonaPrompt",
    "PersonaPrompts",
    "list_personas",
    "get_persona_prompts",
    "get_template_persona",
    "AVATARS_DIR",
    "LOREMASTER_SYSTEM",
    "CHARACTER_SYSTEM",
    "EDITOR_SYSTEM",
    "SD_PROMPT_SYSTEM",
    "REVIEW_SUMMARY_SYSTEM",
    "CHARACTER_SUMMARY_SYSTEM",
    "CHARACTER_RELATED_SYSTEM",
]
