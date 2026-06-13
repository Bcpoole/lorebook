from __future__ import annotations

import re

_PLACEHOLDER_NAME_PATTERN = re.compile(r"^companion(?:\s+\d+)?$", re.IGNORECASE)
_GENERIC_HEADER_PATTERN = re.compile(
    r"^(character\s+card\s+profile|character\s+card|character\s+profile|character\s+\d+)$",
    re.IGNORECASE,
)
_NAME_FIELD_PATTERN = re.compile(
    r"^(?:\*\*|__)?name(?:\*\*|__)?:?\s*(.+?)\s*$",
    re.IGNORECASE,
)
_HEADER_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_MARKDOWN_DECORATION_PATTERN = re.compile(r"^[*_`#\-\s]+|[*_`\s]+$")


def infer_character_name(details: str, fallback: str = "") -> str:
    for raw_line in details.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        field_match = _NAME_FIELD_PATTERN.match(line)
        if field_match:
            return _clean_name(field_match.group(1), fallback)

        header_match = _HEADER_PATTERN.match(line)
        if header_match:
            candidate = header_match.group(1)
            if candidate.lower() not in {"appearance", "personality", "background", "abilities"}:
                return _clean_name(candidate, fallback)

    return fallback.strip()


def should_replace_character_name(current_name: str) -> bool:
    stripped = current_name.strip()
    return (
        not stripped
        or bool(_PLACEHOLDER_NAME_PATTERN.match(stripped))
        or bool(_GENERIC_HEADER_PATTERN.match(stripped))
    )


def _clean_name(value: str, fallback: str) -> str:
    cleaned = _MARKDOWN_DECORATION_PATTERN.sub("", value).strip()
    return cleaned or fallback.strip()
