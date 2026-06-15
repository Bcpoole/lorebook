"""Persona/prompt registry with local override support.

Each persona is a Python module that exposes:
  META              – PersonaMeta instance
  LOREMASTER_SYSTEM – str
  CHARACTER_SYSTEM  – str
  EDITOR_SYSTEM     – str
  SD_PROMPT_SYSTEM  – str
  REVIEW_SUMMARY_SYSTEM – str

The repository tracks only underscore-prefixed template modules. For local
customization, create ``blank.py`` beside this file; it will be preferred over
``_template.py``.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Dict, List

from ._types import PersonaMeta


def _load_blank_module() -> ModuleType:
    try:
        return import_module(".blank", __name__)
    except ModuleNotFoundError as exc:
        if exc.name != f"{__name__}.blank":
            raise
        return import_module("._template", __name__)


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
    """Return metadata for all registered personas."""
    return [m.META for m in _PERSONA_MODULES.values()]


def get_persona_prompts(persona_id: str) -> ModuleType:
    """Return the prompt module for *persona_id*, falling back to blank."""
    return _PERSONA_MODULES.get(persona_id, _blank_module)


# ---------------------------------------------------------------------------
# Package-level re-exports (backward-compat with existing imports)
# ---------------------------------------------------------------------------
LOREMASTER_SYSTEM = _blank_module.LOREMASTER_SYSTEM
CHARACTER_SYSTEM = _blank_module.CHARACTER_SYSTEM
EDITOR_SYSTEM = _blank_module.EDITOR_SYSTEM
SD_PROMPT_SYSTEM = _blank_module.SD_PROMPT_SYSTEM
REVIEW_SUMMARY_SYSTEM = _blank_module.REVIEW_SUMMARY_SYSTEM

__all__ = [
    "PersonaMeta",
    "list_personas",
    "get_persona_prompts",
    "AVATARS_DIR",
    "LOREMASTER_SYSTEM",
    "CHARACTER_SYSTEM",
    "EDITOR_SYSTEM",
    "SD_PROMPT_SYSTEM",
    "REVIEW_SUMMARY_SYSTEM",
]
