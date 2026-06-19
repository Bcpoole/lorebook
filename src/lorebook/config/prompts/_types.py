"""Shared types for the persona/prompt system."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping

PROMPT_KEYS: tuple[str, ...] = (
    "loremaster_system",
    "character_system",
    "editor_system",
    "sd_prompt_system",
    "review_summary_system",
    "character_summary_system",
    "character_related_system",
)

PROMPT_KEY_TO_CONST: dict[str, str] = {
    "loremaster_system": "LOREMASTER_SYSTEM",
    "character_system": "CHARACTER_SYSTEM",
    "editor_system": "EDITOR_SYSTEM",
    "sd_prompt_system": "SD_PROMPT_SYSTEM",
    "review_summary_system": "REVIEW_SUMMARY_SYSTEM",
    "character_summary_system": "CHARACTER_SUMMARY_SYSTEM",
    "character_related_system": "CHARACTER_RELATED_SYSTEM",
}

PROMPT_LABELS: dict[str, str] = {
    "loremaster_system": "Loremaster System",
    "character_system": "Character System",
    "editor_system": "Editor System",
    "sd_prompt_system": "SD Prompt System",
    "review_summary_system": "Review Summary System",
    "character_summary_system": "Character Summary System",
    "character_related_system": "Character Related System",
}

PROMPT_DESCRIPTIONS: dict[str, str] = {
    "loremaster_system": "Prompt for world-building and setting generation",
    "character_system": "Prompt for character design",
    "editor_system": "Prompt for quality review and critique",
    "sd_prompt_system": "Prompt for generating Stable Diffusion image prompts",
    "review_summary_system": "Prompt for summarizing review changes",
    "character_summary_system": "Prompt for generating one-line character summaries",
    "character_related_system": "Prompt for generating related characters",
}

_SYSTEM_PROMPT_WRAPPER_RE = re.compile(
    r"^\s*(?:here(?:'s| is)\s+)?(?:an?\s+)?(?:focused|refined|improved|updated|final)?\s*"
    r"system\s+prompt(?:\s+text)?(?:\s+for\s+.+?)?\s*:\s*$",
    re.IGNORECASE,
)


def clean_system_prompt_text(value: str, prompt_key: str | None = None) -> str:
    """Strip common LLM wrapper text around a generated system prompt."""
    text = str(value or "").strip()
    if not text:
        return ""

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)

    if not lines:
        return ""

    while lines and _SYSTEM_PROMPT_WRAPPER_RE.match(lines[0].strip()):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)

    if prompt_key in PROMPT_KEYS and lines:
        expected_heads = {
            prompt_key.lower(),
            PROMPT_KEY_TO_CONST[prompt_key].lower(),
            PROMPT_LABELS[prompt_key].lower(),
        }
        first = lines[0].strip()
        first = re.sub(r"^[#>*\-\s`]+", "", first).strip()
        first = first.rstrip(":").strip().lower()
        if first in expected_heads:
            lines.pop(0)
            while lines and not lines[0].strip():
                lines.pop(0)

    return "\n".join(lines).strip()


@dataclass
class PersonaPrompt:
    """Transport shape for prompt editor APIs."""

    key: str
    name: str
    system_prompt: str
    description: str = ""

    def get_effective_prompt(self, template_value: str) -> str:
        return self.system_prompt if self.system_prompt.strip() else template_value


@dataclass
class PersonaPrompts:
    loremaster_system: str = ""
    character_system: str = ""
    editor_system: str = ""
    sd_prompt_system: str = ""
    review_summary_system: str = ""
    character_summary_system: str = ""
    character_related_system: str = ""

    def get(self, key: str) -> str:
        if key not in PROMPT_KEYS:
            raise KeyError(f"Unknown prompt key: {key}")
        return getattr(self, key)

    def set(self, key: str, value: str) -> None:
        if key not in PROMPT_KEYS:
            raise KeyError(f"Unknown prompt key: {key}")
        cleaned = clean_system_prompt_text(value if isinstance(value, str) else str(value or ""), key)
        setattr(self, key, cleaned)

    def to_dict(self) -> dict[str, str]:
        return {key: self.get(key) for key in PROMPT_KEYS}

    def to_prompt_items(self) -> list[PersonaPrompt]:
        return [
            PersonaPrompt(
                key=key,
                name=PROMPT_LABELS[key],
                system_prompt=self.get(key),
                description=PROMPT_DESCRIPTIONS[key],
            )
            for key in PROMPT_KEYS
        ]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> PersonaPrompts:
        if not data:
            return cls()

        values: dict[str, str] = {}
        for key in PROMPT_KEYS:
            const_name = PROMPT_KEY_TO_CONST[key]
            raw = data.get(key, data.get(const_name, ""))
            values[key] = clean_system_prompt_text(raw if isinstance(raw, str) else str(raw or ""), key)
        return cls(**values)

    @classmethod
    def from_prompt_items(cls, items: list[PersonaPrompt] | list[Mapping[str, Any]] | None) -> PersonaPrompts:
        prompts = cls()
        if not items:
            return prompts
        for item in items:
            if isinstance(item, PersonaPrompt):
                key = item.key
                value = item.system_prompt
            else:
                key = str(item.get("key", ""))
                value = item.get("system_prompt", "")
            if key in PROMPT_KEYS:
                prompts.set(key, value if isinstance(value, str) else str(value or ""))
        return prompts


@dataclass
class PersonaMeta:
    id: str
    name: str
    description: str
    tags: list[str]
    favorite: bool = False
    avatar: str = ""
    created: str = ""
    modified: str = ""
    prompts: PersonaPrompts = field(default_factory=PersonaPrompts)
