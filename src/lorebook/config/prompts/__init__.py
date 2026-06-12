"""Persona/prompt registry.

Each persona is a Python module that exposes:
  META              – PersonaMeta instance
  LOREMASTER_SYSTEM – str
  CHARACTER_SYSTEM  – str
  EDITOR_SYSTEM     – str
  SD_PROMPT_SYSTEM  – str
  REVIEW_SUMMARY_SYSTEM – str

Re-exports the *blank* persona's constants at package level so existing
``from lorebook.config.prompts import LOREMASTER_SYSTEM`` imports keep working.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Dict, List

from ._types import PersonaMeta
from . import blank as _blank_module

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
from .blank import (  # noqa: E402, F401
    CHARACTER_SYSTEM,
    EDITOR_SYSTEM,
    LOREMASTER_SYSTEM,
    REVIEW_SUMMARY_SYSTEM,
    SD_PROMPT_SYSTEM,
)

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
