"""Stable Diffusion style configuration.

Load order:
1. ``user/configs/sd/styles.json`` — user-curated styles in the persistent user directory
2. ``styles.py`` in this package directory — local Python override (kept for backward compat)
3. ``_template.py`` — built-in defaults
"""
from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Final


def _load_user_styles_json() -> tuple[dict[str, dict[str, str]], str] | None:
    """Load styles from user/configs/sd/styles.json if it exists."""
    json_path = Path(__file__).resolve().parents[4] / "user" / "configs" / "sd" / "styles.json"
    if not json_path.is_file():
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        styles = data.get("styles")
        default = str(data.get("default") or "").strip()
        if not isinstance(styles, dict) or not styles:
            return None
        if default not in styles:
            default = next(iter(styles))
        return styles, default
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _load_styles_module() -> ModuleType:
    try:
        return import_module(".styles", __name__)
    except ModuleNotFoundError as exc:
        if exc.name != f"{__name__}.styles":
            raise
        return import_module("._template", __name__)


def _resolve() -> tuple[dict[str, dict[str, str]], str]:
    user = _load_user_styles_json()
    if user is not None:
        return user
    mod = _load_styles_module()
    return mod.SD_STYLES, mod.DEFAULT_SD_STYLE


SD_STYLES: Final[dict[str, dict[str, str]]]
DEFAULT_SD_STYLE: Final[str]

SD_STYLES, DEFAULT_SD_STYLE = _resolve()

__all__ = ["SD_STYLES", "DEFAULT_SD_STYLE"]
