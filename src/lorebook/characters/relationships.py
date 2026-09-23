from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from lorebook.config.prompts import get_persona_prompts
from lorebook.llm import call_local_llm


RELATIONSHIP_INVERSE_SYSTEM = (
    "You generate inverse relationship labels for character links. "
    "Given a relationship from source -> target, return only the inverse label from target -> source. "
    "Keep it simple and concise (1-7 words), lowercase, no punctuation, no explanation."
)


_RELATIONSHIP_INVERSE_MAP: dict[str, str] = {
    "mother": "child",
    "father": "child",
    "parent": "child",
    "daughter": "parent",
    "son": "parent",
    "child": "parent",
    "brother": "sibling",
    "sister": "sibling",
    "sibling": "sibling",
    "wife": "husband",
    "husband": "wife",
    "spouse": "spouse",
    "employer": "employee",
    "employee": "employer",
    "boss": "subordinate",
    "manager": "report",
    "subordinate": "boss",
    "mentor": "mentee",
    "mentee": "mentor",
    "teacher": "student",
    "student": "teacher",
    "car dealer": "customer",
    "dealer": "customer",
    "customer": "dealer",
}


def _make_character_urn() -> str:
    return f"urn:lorebook:character:{uuid4().hex}"


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip()


def _clean_relationship_label(text: str) -> str:
    line = str(text).splitlines()[0] if str(text) else ""
    line = re.sub(r"^[\-\*\d\.\)\s]+", "", line.strip())
    line = line.strip("`'\"")
    return _trim_words(line, 7)


def _mapped_inverse_relationship(relationship_label: str) -> str:
    normalized = " ".join(str(relationship_label).strip().lower().split())
    if not normalized:
        return ""
    if normalized in _RELATIONSHIP_INVERSE_MAP:
        return _RELATIONSHIP_INVERSE_MAP[normalized]

    for key, inverse in _RELATIONSHIP_INVERSE_MAP.items():
        if key in normalized:
            return inverse
    return ""


def _inverse_relationship_label(
    relationship_label: str,
    source_name: str,
    related_name: str,
    persona_id: str,
) -> str:
    mapped = _mapped_inverse_relationship(relationship_label)
    if mapped:
        return _trim_words(mapped, 7)

    prompts = get_persona_prompts(persona_id)
    inverse_system = getattr(prompts, "RELATIONSHIP_INVERSE_SYSTEM", RELATIONSHIP_INVERSE_SYSTEM)
    prompt = (
        f"Source character: {source_name}\n"
        f"Related character: {related_name}\n"
        f"Relationship from source to related: {relationship_label}\n\n"
        "Return inverse relationship from related to source."
    )
    generated = call_local_llm(inverse_system, prompt, max_length=40)
    cleaned = _clean_relationship_label(generated)
    if cleaned:
        return cleaned
    return "related to"


def _coerce_relationships(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    cleaned: dict[str, str] = {}
    for raw_key, raw_label in value.items():
        key = str(raw_key).strip()
        label = _clean_relationship_label(str(raw_label))
        if not key or not label:
            continue
        cleaned[key] = label
    return cleaned
