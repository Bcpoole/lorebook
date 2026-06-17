"""Shared types for the persona/prompt system."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PersonaMeta:
    id: str
    name: str
    description: str  # kept < 128 chars for UI display
    tags: list[str]   # 3–5 descriptive tags
    avatar: str = ""  # relative path inside avatars/ dir; empty = show initials placeholder
