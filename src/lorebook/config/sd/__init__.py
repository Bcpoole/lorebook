"""Stable Diffusion style configuration.

Load behavior:
1. ``user/configs/sd/*.json`` (optional user-curated styles; files starting with
   ``_`` are ignored — they are treated as reference/example files)
2. ``styles.py`` (built-in baseline styles)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from .styles import DEFAULT_SD_STYLE as BUILTIN_DEFAULT_SD_STYLE
from .styles import SD_STYLES as BUILTIN_SD_STYLES


def _load_user_styles_json() -> tuple[dict[str, dict[str, str]], str] | None:
    """Load and merge styles from all non-underscore-prefixed JSON files in user/configs/sd/.

    Files whose names start with ``_`` (e.g. ``_example.json``) are skipped —
    they are considered reference/template files, not active style definitions.
    """
    sd_dir = Path(__file__).resolve().parents[4] / "user" / "configs" / "sd"
    if not sd_dir.is_dir():
        return None

    merged_styles: dict[str, dict[str, str]] = {}
    first_default: str = ""

    for json_path in sorted(sd_dir.glob("*.json")):
        if json_path.name.startswith("_"):
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            styles = data.get("styles")
            if not isinstance(styles, dict) or not styles:
                continue
            default = str(data.get("default") or "").strip()
            for name, style in styles.items():
                if name not in merged_styles:
                    merged_styles[name] = style
            if not first_default and default in styles:
                first_default = default
        except (OSError, json.JSONDecodeError, ValueError):
            continue

    if not merged_styles:
        return None

    if not first_default:
        first_default = next(iter(merged_styles))
    return merged_styles, first_default


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
