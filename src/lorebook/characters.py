from __future__ import annotations

import re

_PLACEHOLDER_NAME_PATTERN = re.compile(r"^companion(?:\s+\d+)?$", re.IGNORECASE)
_GENERIC_HEADER_PATTERN = re.compile(
    r"^(character\s+card\s+profile|character\s+card|character\s+profile|character\s+\d+)$",
    re.IGNORECASE,
)
_NAME_FIELD_PATTERN = re.compile(
    r"^(?:[-*]\s*)?(?:\*\*|__)?name(?:\*\*|__)?:?(?:\*\*|__)?\s*(.+?)\s*$",
    re.IGNORECASE,
)
_HEADER_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_MARKDOWN_DECORATION_PATTERN = re.compile(r"^[*_`#\-\s]+|[*_`\s]+$")
_NAME_NICKNAME_PATTERN = re.compile(r'\s+(?:"[^"]+"|“[^”]+”|\([^)]*\))')
_NAME_TITLE_PREFIX_PATTERN = re.compile(
    r"^(?:dr|mr|mrs|ms|sir|dame|lord|lady|capt|captain|commander|prof)\.?\s+",
    re.IGNORECASE,
)


def infer_character_name(details: str, fallback: str = "") -> str:
    # First pass: prefer explicit Name fields (e.g. **Name:** ...)
    for raw_line in details.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        field_match = _NAME_FIELD_PATTERN.match(line)
        if field_match:
            return _clean_name(field_match.group(1), fallback)

    # Second pass: fall back to markdown headers if no Name field exists
    for raw_line in details.splitlines():
        line = raw_line.strip()
        if not line:
            continue

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
    return clean_character_name(value, fallback)


def clean_character_name(value: str, fallback: str = "") -> str:
    cleaned = _MARKDOWN_DECORATION_PATTERN.sub("", value).strip()
    cleaned = _NAME_NICKNAME_PATTERN.sub("", cleaned)
    cleaned = _NAME_TITLE_PREFIX_PATTERN.sub("", cleaned)
    return cleaned or fallback.strip()
