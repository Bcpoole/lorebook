"""Stable Diffusion style configuration with local override support.

The repository tracks ``_template.py``. Create ``styles.py`` in this directory
for local/private styles.
"""
from __future__ import annotations

from importlib import import_module
from types import ModuleType


def _load_styles_module() -> ModuleType:
    try:
        return import_module(".styles", __name__)
    except ModuleNotFoundError as exc:
        if exc.name != f"{__name__}.styles":
            raise
        return import_module("._template", __name__)


_styles = _load_styles_module()

SD_STYLES = _styles.SD_STYLES
DEFAULT_SD_STYLE = _styles.DEFAULT_SD_STYLE

__all__ = ["SD_STYLES", "DEFAULT_SD_STYLE"]
