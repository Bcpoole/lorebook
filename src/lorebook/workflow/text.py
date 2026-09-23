from __future__ import annotations

import json
import re
from typing import Any


def _is_meta_response(text: str) -> bool:
    """Detect if response is meta/instruction rather than content (e.g., 'I understand...')."""
    if not text or len(text) < 10:
        return False
    lower = text.lower()
    meta_markers = [
        "i understand",
        "i'm ready",
        "please provide",
        "please give",
        "please specify",
        "what would",
        "how should",
        "would you like",
        "i need",
        "can you",
    ]
    return any(lower.startswith(marker) for marker in meta_markers)


def _clean_continued_output(text: str) -> str:
    """Clean up output from continuations: remove (Continued) markers and duplicate headers."""
    if not text:
        return ""

    # Remove "(Continued)" markers (with variations)
    text = re.sub(r"\s*\(Continued\)\s*", "", text, flags=re.IGNORECASE)

    # Fix headers that got mashed together (e.g., "bond## World Rules" -> "bond\n\n## World Rules")
    # Match: word/punctuation followed directly by # (markdown header)
    text = re.sub(r"([a-zA-Z0-9.,;:\'\"])\s*(#{1,6}\s+)", r"\1\n\n\2", text)

    # Remove duplicate headers within the same text
    # Split into lines and track headers we've seen
    lines = text.split("\n")
    seen_headers = set()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        # Check if this is a header line
        if stripped.startswith("#"):
            # Extract header content (ignore leading #'s and trailing spaces)
            header_content = stripped.lstrip("#").strip()
            # Only keep if we haven't seen this exact header before
            if header_content not in seen_headers:
                seen_headers.add(header_content)
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    # Rejoin and clean up excessive blank lines
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{4,}", "\n\n\n", text)  # Max 3 newlines

    return text.strip()


def _continuation_addition(prior: str, generated: str) -> str:
    """Strip duplicated leading text when a continuation restarts from the top."""
    if not prior or not generated:
        return generated

    # Case 1: model restarted from the beginning of the previous draft.
    if generated.startswith(prior):
        return generated[len(prior) :]

    # Case 2: model started near the prior cutoff; remove suffix/prefix overlap.
    max_overlap = min(len(prior), len(generated))
    for size in range(max_overlap, 0, -1):
        if prior.endswith(generated[:size]):
            return generated[size:]

    # Case 3: model restarted from an early prefix of the prior draft.
    for size in range(max_overlap, 0, -1):
        if prior.startswith(generated[:size]):
            return generated[size:]

    return generated


def _extract_first_json_block(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            loaded = json.loads(stripped)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        loaded = json.loads(stripped[start : end + 1])
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        return None
    return None
