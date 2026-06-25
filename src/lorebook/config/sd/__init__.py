"""Stable Diffusion style configuration.

Load behavior:
1. ``user/configs/sd/styles.json`` (optional user-curated styles)
2. ``styles.py`` (built-in baseline styles)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from .styles import DEFAULT_SD_STYLE as BUILTIN_DEFAULT_SD_STYLE
from .styles import SD_STYLES as BUILTIN_SD_STYLES


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


def resolve_sd_styles(include_builtin_defaults: bool = True) -> tuple[dict[str, dict[str, str]], str]:
    """Resolve available SD styles with optional built-in fallback inclusion.

    When user styles are missing, built-ins are always returned.
    """
    user = _load_user_styles_json()
    if user is None:
        return dict(BUILTIN_SD_STYLES), BUILTIN_DEFAULT_SD_STYLE

    user_styles, user_default = user
    if not include_builtin_defaults:
        return dict(user_styles), user_default

    merged: dict[str, dict[str, str]] = dict(user_styles)
    for name, style in BUILTIN_SD_STYLES.items():
        if name not in merged:
            merged[name] = style
    return merged, user_default


SD_STYLES: Final[dict[str, dict[str, str]]]
DEFAULT_SD_STYLE: Final[str]

SD_STYLES, DEFAULT_SD_STYLE = resolve_sd_styles(include_builtin_defaults=True)

__all__ = ["SD_STYLES", "DEFAULT_SD_STYLE", "resolve_sd_styles"]
