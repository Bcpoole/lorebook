from __future__ import annotations

import base64
import json
import os
import re
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from lorebook.characters import clean_character_name, infer_character_name, should_replace_character_name
from lorebook.config.prompts import get_persona_prompts
from lorebook.config.sd import DEFAULT_SD_STYLE, SD_STYLES, resolve_sd_styles
from lorebook.api.storage import (
    delete_draft_state,
    find_character_by_urn,
    list_run_previews,
    load_latest_drafts,
    load_run,
    save_draft_state,
    save_run_result,
    toggle_favorite,
    update_character_role,
)
from lorebook.llm import call_local_llm, is_local_llm_available, stream_local_llm
from lorebook.state import CharacterState, StoryArtifact, WizardState

router = APIRouter()


def _tokens(env_var: str, default: int) -> int:
    try:
        return int(os.getenv(env_var, default))
    except ValueError:
        return default


LOREMASTER_MAX_TOKENS = _tokens("LOREBOOK_LOREMASTER_MAX_TOKENS", 2048)
CHARACTER_MAX_TOKENS = _tokens("LOREBOOK_CHARACTER_MAX_TOKENS", 2048)
EDITOR_MAX_TOKENS = _tokens("LOREBOOK_EDITOR_MAX_TOKENS", 512)
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


def _coerce_characters(value: Any) -> list[CharacterState]:
    if not isinstance(value, list):
        return []

    normalized: list[CharacterState] = []
    for index, entry in enumerate(value, start=1):
        if not isinstance(entry, dict):
            continue
        raw_name = str(entry.get("name") or "")
        details = str(entry.get("details") or "")
        # Re-infer from details when the stored name is a known placeholder/generic header
        if should_replace_character_name(raw_name):
            raw_name = infer_character_name(details, fallback=f"Companion {index}")
        normalized_entry: CharacterState = {
            "id": str(entry.get("id") or "").strip() or _make_character_urn(),
            "name": raw_name or f"Companion {index}",
            "details": details,
            "relationships": _coerce_relationships(entry.get("relationships")),
        }
        role_value = str(entry.get("role") or "").strip().lower()
        if role_value in {"character", "persona"}:
            normalized_entry["role"] = role_value

        tags_value = entry.get("tags")
        if isinstance(tags_value, list):
            cleaned_tags = [str(tag).strip().lower() for tag in tags_value if str(tag).strip()]
            if cleaned_tags:
                normalized_entry["tags"] = cleaned_tags

        for optional_key in ("image_path", "image_prompt", "image_data", "summary"):
            optional_value = entry.get(optional_key)
            if isinstance(optional_value, str) and optional_value:
                normalized_entry[optional_key] = optional_value

        normalized.append(normalized_entry)
    return normalized


def _coerce_story_artifact(value: Any) -> StoryArtifact | None:
    if not isinstance(value, dict):
        return None

    def _as_string_list(raw: Any) -> list[str]:
        if not isinstance(raw, list):
            return []
        output: list[str] = []
        for entry in raw:
            text = str(entry).strip()
            if text:
                output.append(text)
        return output

    def _as_entity_list(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        output: list[dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = _clean_story_label(entry.get("name"))
            description = str(entry.get("description") or "").strip()
            summary = str(entry.get("summary") or "").strip()
            role = str(entry.get("role") or "").strip()
            label = str(entry.get("label") or "").strip()
            text = str(entry.get("text") or "").strip()
            tags = _as_string_list(entry.get("tags"))
            item: dict[str, Any] = {}
            if name:
                item["name"] = name
            if description:
                item["description"] = description
            if summary:
                item["summary"] = summary
            if role:
                item["role"] = role
            if label:
                item["label"] = label
            if text:
                item["text"] = text
            if tags:
                item["tags"] = tags
            if item:
                output.append(item)
        return output

    def _as_openings(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        openings: list[dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            messages: list[dict[str, str]] = []
            raw_messages = entry.get("messages")
            if isinstance(raw_messages, list):
                for message in raw_messages:
                    if not isinstance(message, dict):
                        continue
                    content = str(message.get("content") or "").strip()
                    if content:
                        messages.append(
                            {
                                "role": str(message.get("role") or "assistant").strip().lower(),
                                "content": content,
                            }
                        )
            openings.append(
                {
                    "description": str(entry.get("description") or "").strip(),
                    "messages": messages,
                }
            )
        return openings

    description = str(value.get("description") or "").strip()
    description_words = description.split()
    if len(description_words) > 128:
        description = " ".join(description_words[:128])

    artifact: StoryArtifact = {
        "title": _clean_story_label(value.get("title") or "Untitled Story"),
        "description": description,
        "plot": str(value.get("plot") or "").strip(),
        "setting": str(value.get("setting") or "").strip(),
        "style": str(value.get("style") or "").strip(),
        "history": str(value.get("history") or "").strip(),
        "tags": _as_string_list(value.get("tags")),
        "characters_artifact": _as_entity_list(value.get("characters_artifact")),
        "locations": _as_entity_list(value.get("locations")),
        "objects": _as_entity_list(value.get("objects")),
        "openings": _as_openings(value.get("openings")),
    }
    return artifact


def _normalize_state(raw_idea: str, state: Dict[str, Any] | None = None) -> WizardState:
    incoming = state or {}
    normalized: WizardState = {
        "raw_idea": raw_idea,
        "world_setting": str(incoming.get("world_setting", "")),
        "characters": _coerce_characters(incoming.get("characters", [])),
        "critique_notes": str(incoming.get("critique_notes", "")),
        "passed_inspection": bool(incoming.get("passed_inspection", False)),
    }
    story_artifact = _coerce_story_artifact(incoming.get("story_artifact"))
    if story_artifact:
        normalized["story_artifact"] = story_artifact
    return normalized


def _all_character_sections(state: WizardState) -> str:
    sections: list[str] = []
    for index, character in enumerate(state.get("characters", []), start=1):
        name = character.get("name") or f"Companion {index}"
        details = character.get("details", "")
        sections.append(f"Character {index} - {name}:\n{details}")
    return "\n\n".join(sections)


def _editor_prompt(state: WizardState) -> str:
    return f"Setting:\n{state['world_setting']}\n\nCharacters:\n{_all_character_sections(state)}"


def _continuation_prompt(stage: str, state: WizardState, directive: str = "", character_index: int = 0) -> str:
    directive_block = f"\n\nInstruction:\n{directive}" if directive.strip() else ""

    if stage == "loremaster":
        return (
            f"Idea:\n{state['raw_idea']}\n\n"
            f"Current draft:\n{state.get('world_setting', '')}"
            f"{directive_block}\n\n"
            "Continue writing from the exact cutoff point. Do not restart or summarize."
        )

    if stage == "character_designer":
        current_details = ""
        characters = state.get("characters", [])
        if 0 <= character_index < len(characters):
            current_details = characters[character_index].get("details", "")
        return (
            f"World setting:\n{state.get('world_setting', '')}\n\n"
            f"Current character draft:\n{current_details}"
            f"{directive_block}\n\n"
            "Continue the same character sheet from the exact cutoff point. Do not restart."
        )

    if stage == "editor":
        return (
            f"{_editor_prompt(state)}"
            f"\n\nCurrent critique draft:\n{state.get('critique_notes', '')}"
            f"{directive_block}\n\n"
            "Continue the critique from the exact cutoff point. Do not restart or summarize."
        )

    return ""


def _stage_max_tokens(stage: str) -> int:
    if stage == "loremaster":
        return LOREMASTER_MAX_TOKENS
    if stage == "character_designer":
        return CHARACTER_MAX_TOKENS
    if stage == "editor":
        return EDITOR_MAX_TOKENS
    return LOREMASTER_MAX_TOKENS


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
    
    import re
    
    # Remove "(Continued)" markers (with variations)
    text = re.sub(r'\s*\(Continued\)\s*', '', text, flags=re.IGNORECASE)
    
    # Fix headers that got mashed together (e.g., "bond## World Rules" -> "bond\n\n## World Rules")
    # Match: word/punctuation followed directly by # (markdown header)
    text = re.sub(r'([a-zA-Z0-9.,;:\'\"])\s*(#{1,6}\s+)', r'\1\n\n\2', text)
    
    # Remove duplicate headers within the same text
    # Split into lines and track headers we've seen
    lines = text.split('\n')
    seen_headers = set()
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        # Check if this is a header line
        if stripped.startswith('#'):
            # Extract header content (ignore leading #'s and trailing spaces)
            header_content = stripped.lstrip('#').strip()
            # Only keep if we haven't seen this exact header before
            if header_content not in seen_headers:
                seen_headers.add(header_content)
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    # Rejoin and clean up excessive blank lines
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n{4,}', '\n\n\n', text)  # Max 3 newlines
    
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


def _next_stage_from_editor(state: WizardState) -> str:
    return "save_assets" if state.get("passed_inspection") else "loremaster"


def _upsert_character(state: WizardState, index: int, details: str) -> list[CharacterState]:
    characters = [dict(character) for character in state.get("characters", [])]
    while len(characters) <= index:
        characters.append({"id": _make_character_urn(), "name": "", "details": "", "relationships": {}})

    base = characters[index]
    if not str(base.get("id") or "").strip():
        base["id"] = _make_character_urn()
    base["relationships"] = _coerce_relationships(base.get("relationships"))
    base["details"] = details
    inferred_name = infer_character_name(details, fallback=base.get("name", ""))
    if should_replace_character_name(base.get("name", "")):
        base["name"] = inferred_name or f"Character {index + 1}"
    characters[index] = base
    return characters


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


_STORY_ORCHESTRATOR_SYSTEM = (
    "You are the story-generation orchestrator. Turn the user's concept into a compact creative "
    "brief for specialist writers. Return ONLY valid JSON with this schema: "
    '{"description":"", "setting":"", "style":"", "tags":[""], "brief":""}. '
    "description must be 128 words max; setting must be a rich 2-3 paragraph world description covering "
    "place, atmosphere, relevant rules, and sensory details; brief must state the premise, conflict, stakes, and tone. "
    "Do not write the title, plot, history, character entries, location entries, object entries, or openings."
)

_STORY_SECTION_SPECS: tuple[tuple[str, str, int], ...] = (
    (
        "title",
        "You are the title specialist. Using the story brief, create one evocative, specific title. "
        "Return only the title on one line; do not use JSON or markdown.",
        80,
    ),
    (
        "plot",
        "You are the plot specialist. Using the story brief, write one cohesive plot or premise section. "
        "Begin the response exactly with '# PLOT / PREMISE', then continue with the plot. Do not use JSON.",
        280,
    ),
    (
        "history",
        "You are the story-history specialist. Summarize the important events immediately before the "
        "story begins, emphasizing causes and unresolved consequences. Begin exactly with '# The Setting' "
        "followed by '## What Came Before', then continue with concise prose or bullets. Do not use JSON. "
        "Do not repeat the plot.",
        220,
    ),
    (
        "characters_artifact",
        "You are the character specialist. Using the story brief, create 2-4 story-relevant characters. "
        "For each character, use exactly these labeled lines, separated by a blank line:\n"
        "Name: <name>\nRole: <role>\nSummary: <concise summary>\nTags: <comma-separated tags>\n"
        "The Name value must be a plain personal name only: no ranks, titles, nicknames, quoted aliases, "
        "parenthetical epithets, or descriptive monikers. Do not use JSON.",
        320,
    ),
    (
        "locations",
        "You are the location specialist. Using the story brief, create 2-3 locations that matter to the plot. "
        "For each location, use exactly these labeled lines, separated by a blank line:\n"
        "Name: <name>\nDescription: <concise description>\nTags: <comma-separated tags>\n"
        "Do not use JSON.",
        280,
    ),
    (
        "objects",
        "You are the story-object specialist. Using the story brief, create 1-3 meaningful objects that "
        "advance, complicate, or symbolize the story. For each object, use exactly these labeled lines, "
        "separated by a blank line:\nName: <name>\nDescription: <concise description>\n"
        "Tags: <comma-separated tags>\nDo not use JSON.",
        240,
    ),
    (
        "openings",
        "You are the opening-scene specialist. Using the story brief, write a compelling, self-contained "
        "opening of 2-4 paragraphs that establishes the protagonist, setting, and immediate tension. "
        "Return only the prose; do not use JSON or markdown headings.",
        360,
    ),
)


def _story_prompt(
    raw_idea: str,
    story_setup: dict[str, Any] | None = None,
    instruction: str = "",
) -> str:
    prompt = raw_idea
    if story_setup and isinstance(story_setup, dict):
        setup_lines = "\n".join(
            f"- {k}: {v}" for k, v in story_setup.items() if str(v or "").strip()
        )
        if setup_lines:
            prompt = f"{prompt}\n\nStory setup preferences:\n{setup_lines}"
    if instruction:
        prompt = f"{prompt}\n\nInstruction:\n{instruction}"
    return prompt


def _story_token_budget(configured_max_length: int, minimum: int) -> int:
    """Keep each small specialist response viable when the global UI limit is tiny."""
    return max(configured_max_length, minimum)


def _story_artifact_from_sections(sections: dict[str, Any], persona_id: str) -> StoryArtifact:
    overview = sections.get("overview") if isinstance(sections.get("overview"), dict) else {}
    artifact = _coerce_story_artifact(
        {
            "title": (sections.get("title") or {}).get("title", ""),
            "description": overview.get("description", ""),
            "plot": (sections.get("plot") or {}).get("plot", ""),
            "setting": overview.get("setting", ""),
            "style": overview.get("style", "") or persona_id,
            "history": (sections.get("history") or {}).get("history", ""),
            "tags": overview.get("tags", []),
            "characters_artifact": (sections.get("characters_artifact") or {}).get("characters_artifact", []),
            "locations": (sections.get("locations") or {}).get("locations", []),
            "objects": (sections.get("objects") or {}).get("objects", []),
            "openings": (sections.get("openings") or {}).get("openings", []),
        }
    )
    if artifact is None:
        raise HTTPException(status_code=500, detail="Failed to assemble story artifact")
    return artifact


def _clean_story_label(value: Any) -> str:
    label = str(value or "").strip()
    label = re.sub(r"^\s*(?:#{1,6}\s+|[-*]\s+)", "", label)
    label = re.sub(r"^[*_`]+|[*_`]+$", "", label).strip()
    return label


def _parse_story_section(generated: str, key: str) -> dict[str, Any] | None:
    loaded = _extract_first_json_block(generated)
    if isinstance(loaded, dict):
        if key == "overview":
            return loaded if str(loaded.get("description") or "").strip() else None
        value = loaded.get(key)
        if key in {"title", "plot", "history"}:
            cleaned = _clean_story_label(value) if key == "title" else str(value or "").strip()
            return {key: cleaned} if cleaned else None
        if isinstance(value, list):
            return {key: value}

    text = generated.strip()
    if not text:
        return None
    if key == "title":
        return {"title": _clean_story_label(text.splitlines()[0].strip().strip("\"'"))}
    if key == "openings":
        return {"openings": [{"description": "", "messages": [{"role": "assistant", "content": text}]}]}
    if key == "plot":
        return {"plot": text}
    if key == "history":
        return {"history": text}
    if key in {"characters_artifact", "locations", "objects"}:
        body_key = "summary" if key == "characters_artifact" else "description"
        entries: list[dict[str, Any]] = []
        for block in re.split(r"\n\s*\n", text):
            fields: dict[str, str] = {}
            current_key = ""
            for line in block.splitlines():
                match = re.match(r"^(Name|Role|Summary|Description|Tags):\s*(.*)$", line.strip(), re.IGNORECASE)
                if match:
                    current_key = match.group(1).lower()
                    fields[current_key] = match.group(2).strip()
                elif current_key and line.strip():
                    fields[current_key] = f"{fields[current_key]} {line.strip()}".strip()
            if not fields.get("name"):
                continue
            entry: dict[str, Any] = {
                "name": _clean_story_label(fields["name"]),
                body_key: fields.get(body_key, ""),
                "tags": [tag.strip().lower() for tag in fields.get("tags", "").split(",") if tag.strip()],
            }
            if key == "characters_artifact":
                entry["name"] = clean_character_name(entry["name"], fallback="Character")
                entry["role"] = fields.get("role", "character")
            entries.append(entry)
        if entries:
            return {key: entries}
        if key == "characters_artifact":
            return {
                key: [
                    {
                        "name": "Character 1",
                        "role": "character",
                        "summary": text,
                        "tags": [],
                    }
                ]
            }
    return None


def _build_story_artifact(
    raw_idea: str,
    persona_id: str,
    max_length: int = 1200,
    story_setup: dict[str, Any] | None = None,
    instruction: str = "",
) -> tuple[StoryArtifact, str]:
    """Generate a story through an orchestrator and small, independently parseable specialists."""
    prompt = _story_prompt(raw_idea, story_setup, instruction)
    sections: dict[str, Any] = {}
    quality = "full"

    overview_raw = call_local_llm(
        _STORY_ORCHESTRATOR_SYSTEM,
        prompt,
        max_length=_story_token_budget(max_length, 220),
    )
    overview = _parse_story_section(overview_raw, "overview")
    if overview is None:
        quality = "partial"
        overview = {
            "description": overview_raw[:800],
            "setting": "",
            "style": persona_id,
            "tags": [],
            "brief": raw_idea,
        }
    sections["overview"] = overview
    specialist_context = f"{prompt}\n\nOrchestrator brief:\n{overview.get('brief') or overview.get('description')}"

    for key, system_prompt, minimum_tokens in _STORY_SECTION_SPECS:
        generated = call_local_llm(
            system_prompt,
            specialist_context,
            max_length=_story_token_budget(max_length, minimum_tokens),
        )
        parsed = _parse_story_section(generated, key)
        if parsed is None:
            quality = "partial"
            parsed = {key: "" if key in {"title", "plot", "history"} else []}
        sections[key] = parsed

    return _story_artifact_from_sections(sections, persona_id), quality


def _build_story_action(
    raw_idea: str,
    existing_story: dict[str, Any],
    action: str,
    persona_id: str,
    max_length: int = 1200,
) -> tuple[StoryArtifact, str]:
    """Apply *action* to *existing_story* by asking the LLM to regenerate it.

    Returns ``(artifact, generation_quality)`` where ``generation_quality`` is
    ``"full"`` on success or ``"fallback"`` when parsing fails (existing story
    is preserved).
    """
    prompt = (
        f"{raw_idea}\n\nCurrent context JSON:\n{json.dumps(existing_story, ensure_ascii=False)}"
        f"\n\nAction: {action}"
    )
    generated = call_local_llm(
        "You are a story editor. Return ONLY valid JSON that preserves the supplied story schema and applies the requested action.",
        prompt,
        max_length=_story_token_budget(max_length, 360),
    )
    loaded = _extract_first_json_block(generated)
    if loaded is None:
        artifact = _coerce_story_artifact(existing_story)
        return (artifact if artifact is not None else existing_story), "fallback"  # type: ignore[return-value]

    artifact = _coerce_story_artifact(loaded)
    if artifact is None:
        artifact = _coerce_story_artifact(existing_story)
        return (artifact if artifact is not None else existing_story), "fallback"  # type: ignore[return-value]
    if not artifact["style"]:
        artifact["style"] = persona_id
    return artifact, "full"


async def _story_event_generator(
    raw_idea: str,
    request: Request,
    persona_id: str,
    max_length: int,
    story_setup: dict[str, Any] | None,
    instruction: str,
    save_pending: bool,
) -> AsyncIterator[Dict[str, str]]:
    """Stream orchestrator and specialist output while publishing assembled Story snapshots."""
    prompt = _story_prompt(raw_idea, story_setup, instruction)
    sections: dict[str, Any] = {}
    quality = "full"

    async def generate_section(
        key: str,
        system_prompt: str,
        user_prompt: str,
        minimum_tokens: int,
    ) -> AsyncIterator[Dict[str, str]]:
        if await request.is_disconnected():
            return
        token_budget = _story_token_budget(max_length, minimum_tokens)
        yield {"event": "story-stage-start", "data": json.dumps({"section": key, "token_budget": token_budget})}
        generated = ""
        try:
            for chunk in stream_local_llm(system_prompt, user_prompt, max_length=token_budget):
                if await request.is_disconnected():
                    return
                generated += chunk
        except RuntimeError as exc:
            yield {"event": "story-error", "data": json.dumps({"section": key, "detail": str(exc)})}
            return
        yield {"event": "story-stage-raw", "data": generated}

    overview_raw = ""
    async for event in generate_section("overview", _STORY_ORCHESTRATOR_SYSTEM, prompt, 220):
        if event["event"] == "story-stage-raw":
            overview_raw = event["data"]
        else:
            yield event
    if not overview_raw:
        yield {
            "event": "story-error",
            "data": json.dumps({"section": "overview", "detail": "The story orchestrator returned no output."}),
        }
        return
    overview = _parse_story_section(overview_raw, "overview")
    if overview is None:
        quality = "partial"
        overview = {
            "description": overview_raw[:800],
            "setting": "",
            "style": persona_id,
            "tags": [],
            "brief": raw_idea,
        }
    sections["overview"] = overview
    yield {
        "event": "story-section-complete",
        "data": json.dumps({"section": "overview", "output": overview, "story_artifact": _story_artifact_from_sections(sections, persona_id)}),
    }

    specialist_context = f"{prompt}\n\nOrchestrator brief:\n{overview.get('brief') or overview.get('description')}"
    for key, system_prompt, minimum_tokens in _STORY_SECTION_SPECS:
        generated = ""
        async for event in generate_section(key, system_prompt, specialist_context, minimum_tokens):
            if event["event"] == "story-stage-raw":
                generated = event["data"]
            else:
                yield event
        if not generated:
            yield {
                "event": "story-error",
                "data": json.dumps({"section": key, "detail": f"The {key} specialist returned no output."}),
            }
            return
        parsed = _parse_story_section(generated, key)
        if parsed is None:
            quality = "partial"
            parsed = {key: "" if key in {"title", "plot", "history"} else []}
        sections[key] = parsed
        yield {
            "event": "story-section-complete",
            "data": json.dumps(
                {
                    "section": key,
                    "output": parsed,
                    "story_artifact": _story_artifact_from_sections(sections, persona_id),
                }
            ),
        }

    artifact = _story_artifact_from_sections(sections, persona_id)
    state = _normalize_state(raw_idea, None)
    state["story_artifact"] = artifact
    if story_setup is not None:
        state["story_setup"] = story_setup
    if instruction:
        state["story_instruction"] = instruction
    save_draft_state(
        {
            "raw_idea": raw_idea,
            "state": state,
            "generation_quality": quality,
            "meta": {"mode": "story", "streaming": True},
            "save_pending": save_pending,
        },
        "latest",
        artifact_type="story",
    )
    yield {
        "event": "story-complete",
        "data": json.dumps(
            {
                "state": state,
                "story_artifact": artifact,
                "generation_quality": quality,
                "story_setup": story_setup,
                "story_instruction": instruction,
            }
        ),
    }
    yield {"event": "done", "data": "{}"}


def _story_item_sd_prompt(
    item: dict[str, Any],
    story: dict[str, Any],
    section: str,
    sd_config: dict[str, Any] | None = None,
    persona_id: str = "blank",
) -> str:
    """Generate an SD image prompt for a story entity item."""
    prompts = get_persona_prompts(persona_id)
    context_parts = [f"Section: {section}"]
    for key in ("name", "description", "summary", "role"):
        val = str(item.get(key) or "").strip()
        if val:
            context_parts.append(f"{key.capitalize()}: {val}")
    for key in ("setting", "style"):
        val = str(story.get(key) or "").strip()
        if val:
            context_parts.append(f"Story {key}: {val}")
    context = "\n".join(context_parts)
    return call_local_llm(prompts.SD_PROMPT_SYSTEM, context, max_length=200)




def _generate_character_only(raw_idea: str, persona_id: str, max_length: int = 700) -> CharacterState:
    prompts = get_persona_prompts(persona_id)
    generated = call_local_llm(prompts.CHARACTER_SYSTEM, raw_idea, max_length=max_length)
    name = infer_character_name(generated, fallback="Companion")
    return {
        "id": _make_character_urn(),
        "name": name,
        "details": generated.strip(),
        "role": "character",
        "tags": [],
        "relationships": {},
    }


def _run_stage_sync(
    state: WizardState,
    stage: str,
    continue_output: bool = False,
    directive: str = "",
    character_index: int = 0,
    experimentation_config: dict[str, Any] | None = None,
) -> str:
    config = experimentation_config or {}
    max_length = int(config.get("maxLength", _stage_max_tokens(stage)))
    llm_endpoint = config.get("llmEndpoint") or None
    prompts = get_persona_prompts(config.get("persona_id", "blank"))

    if stage == "loremaster":
        prior_text = state.get("world_setting", "")
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = state["raw_idea"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"
        generated = call_local_llm(
            prompts.LOREMASTER_SYSTEM,
            prompt,
            max_length=max_length,
            endpoint=llm_endpoint,
        )
        addition = _continuation_addition(prior_text, generated) if continue_output else generated
        output = f"{prior_text}{addition}" if continue_output else addition
        state["world_setting"] = _clean_continued_output(output)
        return "character_designer"

    if stage == "character_designer":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for character_designer")

        characters = state.get("characters", [])
        current_details = ""
        if 0 <= character_index < len(characters):
            current_details = characters[character_index].get("details", "")

        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive, character_index=character_index)
        else:
            prompt = state["world_setting"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = call_local_llm(
            prompts.CHARACTER_SYSTEM,
            prompt,
            max_length=max_length,
            endpoint=llm_endpoint,
        )
        
        # Guardrail: reject meta responses and retry with stronger instruction
        if not continue_output and _is_meta_response(generated):
            retry_prompt = (
                f"{state['world_setting']}\n\n"
                f"Create a detailed character card for a companion in this world. "
                f"Include: name, physical description, personality, background, skills, and role."
            )
            generated = call_local_llm(
                prompts.CHARACTER_SYSTEM,
                retry_prompt,
                max_length=max_length,
                endpoint=llm_endpoint,
            )
        
        addition = _continuation_addition(current_details, generated) if continue_output else generated
        details = f"{current_details}{addition}" if continue_output else addition
        details = _clean_continued_output(details)
        state["characters"] = _upsert_character(state, character_index, details)
        return "editor"

    if stage == "editor":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for editor")
        if not state.get("characters"):
            raise HTTPException(status_code=400, detail="characters are required for editor")
        if continue_output and state.get("passed_inspection"):
            return _next_stage_from_editor(state)

        prior_critique = state.get("critique_notes", "")

        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = _editor_prompt(state)
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = call_local_llm(
            prompts.EDITOR_SYSTEM,
            prompt,
            max_length=max_length,
            endpoint=llm_endpoint,
        )
        addition = _continuation_addition(prior_critique, generated) if continue_output else generated
        critique = f"{state.get('critique_notes', '')}{addition}" if continue_output else addition
        critique = _clean_continued_output(critique)
        passed = "PASSED" in critique
        state["passed_inspection"] = passed
        state["critique_notes"] = critique
        return _next_stage_from_editor(state)

    raise HTTPException(status_code=400, detail=f"Unsupported stage: {stage}")


async def _run_stage_stream(
    state: WizardState,
    stage: str,
    request: Request,
    continue_output: bool = False,
    directive: str = "",
    character_index: int = 0,
    experimentation_config: dict | None = None,
) -> AsyncIterator[Dict[str, str]]:
    start = time.monotonic()
    
    if experimentation_config is None:
        experimentation_config = {}
    
    max_length = int(experimentation_config.get("maxLength", _stage_max_tokens(stage)))
    llm_endpoint = experimentation_config.get("llmEndpoint") or None
    prompts = get_persona_prompts(experimentation_config.get("persona_id", "blank"))

    if await request.is_disconnected():
        return

    yield {"event": "node-start", "data": json.dumps({"node": stage})}

    if stage == "loremaster":
        prior_text = state.get("world_setting", "")
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = state["raw_idea"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = ""
        for chunk in stream_local_llm(prompts.LOREMASTER_SYSTEM, prompt, max_length=max_length, endpoint=llm_endpoint):
            if await request.is_disconnected():
                return
            generated += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        addition = _continuation_addition(prior_text, generated) if continue_output else generated
        text = f"{prior_text}{addition}" if continue_output else addition
        state["world_setting"] = _clean_continued_output(text)
        next_stage = "character_designer"
        output = {"world_setting": state["world_setting"]}

    elif stage == "character_designer":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for character_designer")

        characters = state.get("characters", [])
        prior_details = ""
        if 0 <= character_index < len(characters):
            prior_details = characters[character_index].get("details", "")

        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive, character_index=character_index)
        else:
            prompt = state["world_setting"]
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = ""
        for chunk in stream_local_llm(prompts.CHARACTER_SYSTEM, prompt, max_length=max_length, endpoint=llm_endpoint):
            if await request.is_disconnected():
                return
            generated += chunk
            yield {
                "event": "node-token",
                "data": json.dumps({"node": stage, "chunk": chunk}),
            }
        
        # Guardrail: reject meta responses and retry with stronger instruction
        if not continue_output and _is_meta_response(generated):
            retry_prompt = (
                f"{state['world_setting']}\n\n"
                f"Create a detailed character card for a companion in this world. "
                f"Include: name, physical description, personality, background, skills, and role."
            )
            generated = ""
            for chunk in stream_local_llm(prompts.CHARACTER_SYSTEM, retry_prompt, max_length=max_length, endpoint=llm_endpoint):
                if await request.is_disconnected():
                    return
                generated += chunk
                yield {
                    "event": "node-token",
                    "data": json.dumps({"node": stage, "chunk": chunk}),
                }
        
        addition = _continuation_addition(prior_details, generated) if continue_output else generated
        details = f"{prior_details}{addition}" if continue_output else addition
        details = _clean_continued_output(details)
        state["characters"] = _upsert_character(state, character_index, details)
        next_stage = "editor"
        output = {"characters": state["characters"]}

    elif stage == "editor":
        if not state.get("world_setting"):
            raise HTTPException(status_code=400, detail="world_setting is required for editor")
        if not state.get("characters"):
            raise HTTPException(status_code=400, detail="characters are required for editor")
        if continue_output and state.get("passed_inspection"):
            next_stage = _next_stage_from_editor(state)
            output = {"passed_inspection": True, "critique_notes": state.get("critique_notes", "")}
            yield {"event": "node-complete", "data": json.dumps({"node": stage, "output": output})}
            elapsed_ms = round((time.monotonic() - start) * 1000)
            save_draft_state(
                {
                    "raw_idea": state.get("raw_idea", ""),
                    "state": state,
                    "meta": {"elapsed_ms": elapsed_ms, "next_stage": next_stage, "stage": stage},
                    "save_pending": True,
                },
                artifact_type="world",
            )
            yield {
                "event": "step-complete",
                "data": json.dumps(
                    {
                        "state": state,
                        "meta": {"elapsed_ms": elapsed_ms},
                        "next_stage": next_stage,
                        "save_pending": True,
                    }
                ),
            }
            yield {"event": "done", "data": "{}"}
            return

        prior_critique = state.get("critique_notes", "")
        if continue_output:
            prompt = _continuation_prompt(stage, state, directive=directive)
        else:
            prompt = _editor_prompt(state)
            if directive.strip():
                prompt = f"{prompt}\n\nInstruction:\n{directive}"

        generated = ""
        for chunk in stream_local_llm(prompts.EDITOR_SYSTEM, prompt, max_length=max_length, endpoint=llm_endpoint):
            if await request.is_disconnected():
                return
            generated += chunk
            yield {"event": "node-token", "data": json.dumps({"node": stage, "chunk": chunk})}
        addition = _continuation_addition(prior_critique, generated) if continue_output else generated
        critique = f"{prior_critique}{addition}" if continue_output else addition
        critique = _clean_continued_output(critique)
        passed = "PASSED" in critique
        state["passed_inspection"] = passed
        state["critique_notes"] = critique
        next_stage = _next_stage_from_editor(state)
        output = {
            "passed_inspection": passed,
            "critique_notes": critique,
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported stage: {stage}")

    yield {"event": "node-complete", "data": json.dumps({"node": stage, "output": output})}
    elapsed_ms = round((time.monotonic() - start) * 1000)
    save_pending = stage == "editor" and state.get("passed_inspection")
    save_draft_state(
        {
            "raw_idea": state.get("raw_idea", ""),
            "state": state,
            "meta": {"elapsed_ms": elapsed_ms, "next_stage": next_stage, "stage": stage},
            "save_pending": save_pending,
        },
        artifact_type="world",
    )
    yield {
        "event": "step-complete",
        "data": json.dumps(
            {
                "state": state,
                "meta": {"elapsed_ms": elapsed_ms},
                "next_stage": next_stage,
                "save_pending": save_pending,
            }
        ),
    }
    yield {"event": "done", "data": "{}"}


def _outputs_images_dir() -> Path:
    directory = Path(__file__).resolve().parents[4] / "outputs" / "images"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _make_sd_prompt(state: WizardState, character: CharacterState, prompt_override: str | None = None, persona_id: str = "blank") -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()

    prompt_input = (
        f"World setting:\n{state.get('world_setting', '')}\n\n"
        f"Character name: {character.get('name', 'Companion')}\n"
        f"Character details:\n{character.get('details', '')}"
    )
    generated = call_local_llm(get_persona_prompts(persona_id).SD_PROMPT_SYSTEM, prompt_input, max_length=256)
    return generated.strip().replace("\n", " ")


def _style_sd_prompts(
    prompt: str,
    style_name: str | None = None,
    negative_user: str | None = None,
) -> tuple[str, str, str]:
    style_key = (style_name or "").strip().lower() or DEFAULT_SD_STYLE
    style = SD_STYLES.get(style_key, SD_STYLES[DEFAULT_SD_STYLE])

    prompt_template = str(style.get("prompt", "{prompt}"))
    negative_template = str(style.get("negative_prompt", ""))

    if "{prompt}" not in prompt_template:
        prompt_template = f"{prompt_template}, {{prompt}}"

    styled_prompt = prompt_template.format(prompt=prompt)

    negative_substituted = str(negative_user or "").strip()
    if "{negative_prompt}" in negative_template:
        styled_negative = negative_template.format(negative_prompt=negative_substituted)
        # strip leading comma/space if the user value was empty
        styled_negative = re.sub(r"^[,\s]+", "", styled_negative)
    else:
        # no token in template — append user value when present
        styled_negative = negative_template
        if negative_substituted:
            styled_negative = f"{styled_negative}, {negative_substituted}" if styled_negative else negative_substituted

    return styled_prompt, styled_negative, style_key


def _render_sd_image(prompt: str, style_name: str | None = None, sd_config: dict[str, Any] | None = None) -> tuple[str, str, str, str]:
    config = sd_config or {}
    styled_prompt, styled_negative, resolved_style = _style_sd_prompts(
        prompt,
        style_name=style_name,
        negative_user=str(config.get("negativePrompt", "")),
    )
    endpoint = str(config.get("endpoint") or os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860")).rstrip("/")
    steps = int(config.get("steps", 30))
    width = int(config.get("width", 768))
    height = int(config.get("height", 768))
    cfg_scale = float(config.get("cfgScale", 3))
    sampler_name = str(config.get("samplerName", "DPM++ 2M"))

    response = requests.post(
        f"{endpoint}/sdapi/v1/txt2img",
        json={
            "prompt": styled_prompt,
            "negative_prompt": styled_negative,
            "steps": steps,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    images = payload.get("images") or []
    if not images:
        raise RuntimeError("Stable Diffusion response did not include image data")

    encoded = images[0]
    if "," in encoded:
        encoded = encoded.split(",", maxsplit=1)[1]
    image_bytes = base64.b64decode(encoded)

    image_name = f"{uuid4().hex}.png"
    image_path = _outputs_images_dir() / image_name
    image_path.write_bytes(image_bytes)

    return str(image_path), f"data:image/png;base64,{encoded}", styled_prompt, resolved_style


def _assert_sd_available(endpoint_override: str | None = None) -> None:
    endpoint = str(endpoint_override or os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860")).rstrip("/")
    try:
        response = requests.get(f"{endpoint}/sdapi/v1/progress", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail="Stable Diffusion AUTOMATIC1111 API is unavailable. Start it before generating an image.",
        ) from exc


@router.get("/restore-latest")
async def restore_latest() -> Dict[str, Any]:
    drafts = load_latest_drafts("latest")
    return {
        "draft": drafts.get("world"),
        "story_draft": drafts.get("story"),
        "character_draft": drafts.get("character"),
    }


@router.get("/llm-health")
async def llm_health() -> Dict[str, Any]:
    return {
        "connected": is_local_llm_available(),
    }


@router.get("/health")
async def app_health() -> Dict[str, Any]:
    return {
        "status": "ok",
    }


@router.get("/runs/{run_id}")
async def get_run_by_id(run_id: str, artifact_type: str = Query("")) -> Dict[str, Any]:
    record = load_run(run_id, artifact_type=artifact_type or None)
    if not record:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return record


@router.get("/characters/by-id")
async def get_character_by_id(urn: str = Query(..., min_length=1)) -> Dict[str, Any]:
    resolved = find_character_by_urn(urn)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"character {urn} not found")
    return resolved


@router.get("/gallery")
async def list_gallery_runs(
    search: str = "",
    tag: str = "",
    favorites_only: bool = False,
    artifact_type: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    listing = list_run_previews(
        search=search,
        tag=tag,
        favorites_only=favorites_only,
        artifact_type=artifact_type or None,
        limit=limit,
        offset=offset,
    )
    return {
        "items": listing["items"],
        "total": listing["total"],
        "limit": limit,
        "offset": offset,
    }


@router.post("/gallery/{run_id}/favorite")
async def toggle_run_favorite(run_id: str, artifact_type: str = Query("")) -> Dict[str, Any]:
    """Toggle the favorite flag on a gallery run."""
    record = toggle_favorite(run_id, artifact_type=artifact_type or None)
    if not record:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return {"ok": True, "run_id": run_id, "favorite": bool(record.get("favorite", False))}


@router.post("/story")
async def generate_story_artifact(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    if not raw_idea:
        raise HTTPException(status_code=400, detail="raw_idea is required")

    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    max_length = int(experimentation_config.get("maxLength", 1200))
    story_setup: dict[str, Any] | None = body.get("story_setup") if isinstance(body.get("story_setup"), dict) else None
    instruction: str = str(body.get("instruction") or "").strip()
    action: str = str(body.get("action") or "").strip()

    state = _normalize_state(raw_idea, body.get("state"))
    existing_story = state.get("story_artifact") if isinstance(state.get("story_artifact"), dict) else None

    if action and existing_story:
        artifact, generation_quality = _build_story_action(
            raw_idea, existing_story, action, persona_id=persona_id, max_length=max_length
        )
    else:
        artifact, generation_quality = _build_story_artifact(
            raw_idea, persona_id=persona_id, max_length=max_length,
            story_setup=story_setup, instruction=instruction,
        )

    state["story_artifact"] = artifact

    payload = {
        "raw_idea": raw_idea,
        "state": state,
        "generation_quality": generation_quality,
        "meta": {"mode": "story"},
        "save_pending": bool(body.get("save_pending", False)),
    }
    save_draft_state(payload, "latest", artifact_type="story")

    response: Dict[str, Any] = {
        "state": state,
        "story_artifact": artifact,
        "generation_quality": generation_quality,
    }
    if action:
        response["action"] = action
    if story_setup is not None:
        response["story_setup"] = story_setup
    if instruction:
        response["story_instruction"] = instruction
    return response


@router.post("/story/stream")
async def stream_story_artifact(body: Dict[str, Any], request: Request) -> EventSourceResponse:
    raw_idea = str(body.get("raw_idea") or "").strip()
    if not raw_idea:
        raise HTTPException(status_code=400, detail="raw_idea is required")

    experimentation_config = body.get("experimentation_config", {})
    if not isinstance(experimentation_config, dict):
        raise HTTPException(status_code=400, detail="experimentation_config must be an object")

    story_setup = body.get("story_setup")
    if story_setup is not None and not isinstance(story_setup, dict):
        raise HTTPException(status_code=400, detail="story_setup must be an object")

    return EventSourceResponse(
        _story_event_generator(
            raw_idea=raw_idea,
            request=request,
            persona_id=str(body.get("persona_id") or "blank"),
            max_length=int(experimentation_config.get("maxLength", 1200)),
            story_setup=story_setup,
            instruction=str(body.get("instruction") or "").strip(),
            save_pending=bool(body.get("save_pending", False)),
        )
    )


_STORY_ITEM_SECTIONS = frozenset({"characters_artifact", "locations", "objects"})


@router.post("/story-item")
async def story_item_operation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Update, delete, or generate an image for a single item within a story artifact."""
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    section: str = str(body.get("section") or "")
    operation: str = str(body.get("operation") or "")
    item_index: int = int(body.get("item_index", 0))

    if section not in _STORY_ITEM_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}'. Must be one of {sorted(_STORY_ITEM_SECTIONS)}")

    state = _normalize_state(raw_idea, body.get("state"))
    incoming_state = body.get("state") if isinstance(body.get("state"), dict) else {}
    artifact = state.get("story_artifact")
    if not isinstance(artifact, dict):
        raise HTTPException(status_code=400, detail="state.story_artifact is required")

    artifact = deepcopy(artifact)
    items: list[Any] = list(artifact.get(section) or [])

    if operation == "update":
        item = body.get("item")
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="item is required for update operation")
        if 0 <= item_index < len(items):
            items[item_index] = item
        else:
            items.append(item)

    elif operation == "delete":
        if 0 <= item_index < len(items):
            items.pop(item_index)

    elif operation == "image":
        if item_index < 0 or item_index >= len(items) or not isinstance(items[item_index], dict):
            raise HTTPException(status_code=400, detail="Invalid item_index")
        mode: str = str(body.get("mode") or "prompt")
        sd_config: dict[str, Any] = body.get("sd_config") if isinstance(body.get("sd_config"), dict) else {}
        persona_id: str = str(body.get("persona_id") or "blank")
        item = dict(items[item_index])

        image_prompt = _story_item_sd_prompt(item, artifact, section, sd_config=sd_config, persona_id=persona_id)
        item["image_prompt"] = image_prompt

        if mode == "full":
            _assert_sd_available(sd_config.get("endpoint"))
            style_name = str(sd_config.get("style") or "") or None
            full_path, data_uri, _styled, _style = _render_sd_image(image_prompt, style_name=style_name, sd_config=sd_config)
            item["image_name"] = Path(full_path).name
            item["image_data"] = data_uri
            item.pop("image_path", None)

        items[item_index] = item

    else:
        raise HTTPException(status_code=400, detail=f"Invalid operation '{operation}'. Must be update, delete, or image")

    artifact[section] = items
    state["story_artifact"] = artifact
    if isinstance(incoming_state.get("story_setup"), dict):
        state["story_setup"] = incoming_state["story_setup"]
    if isinstance(incoming_state.get("story_instruction"), str):
        state["story_instruction"] = incoming_state["story_instruction"]

    save_draft_state(
        {
            "raw_idea": raw_idea,
            "state": state,
            "meta": {"mode": "story"},
            "save_pending": bool(body.get("save_pending", False)),
        },
        "latest",
        artifact_type="story",
    )
    return {"story_artifact": artifact, "state": state}




@router.post("/character")
async def generate_character_only(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    if not raw_idea:
        raise HTTPException(status_code=400, detail="raw_idea is required")

    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    max_length = int(experimentation_config.get("maxLength", 700))
    character = _generate_character_only(raw_idea, persona_id=persona_id, max_length=max_length)

    state = _normalize_state(raw_idea, body.get("state"))
    state["characters"] = [character]
    payload = {
        "raw_idea": raw_idea,
        "state": state,
        "meta": {"mode": "character"},
        "save_pending": bool(body.get("save_pending", False)),
    }
    save_draft_state(payload, "latest", artifact_type="character")
    return {"state": state, "character": character}


@router.post("/character-role")
async def set_character_role(body: Dict[str, Any]) -> Dict[str, Any]:
    run_id = str(body.get("run_id") or "").strip()
    role = str(body.get("role") or "").strip().lower()
    character_index = int(body.get("character_index", 0))
    artifact_type = str(body.get("artifact_type") or "").strip().lower()
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    if role not in {"character", "persona"}:
        raise HTTPException(status_code=400, detail="role must be character or persona")

    updated = update_character_role(run_id, character_index, role, artifact_type=artifact_type or None)
    if not updated:
        raise HTTPException(status_code=404, detail="run or character not found")
    return {"ok": True, "run": updated}


@router.post("/character-related")
async def generate_related_character(body: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a new character related to an existing one via a described relationship."""
    raw_idea: str = str(body.get("raw_idea") or "").strip()
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    max_length = int(experimentation_config.get("maxLength", 700))
    relationship: str = str(body.get("relationship") or "").strip()
    context: str = str(body.get("context") or "").strip()
    source_character_index: int = max(0, int(body.get("source_character_index", 0)))

    state = _normalize_state(raw_idea, body.get("state"))
    source_characters = state.get("characters", [])

    if source_character_index >= len(source_characters):
        raise HTTPException(status_code=400, detail="source_character_index is out of range")

    source_char = source_characters[source_character_index]
    source_name = str(source_char.get("name") or "the existing character")
    source_details = str(source_char.get("details") or "")

    relationship_label = _clean_relationship_label(relationship)
    if not relationship_label:
        raise HTTPException(status_code=400, detail="relationship description is required")

    prompts = get_persona_prompts(persona_id)
    related_system = getattr(prompts, "CHARACTER_RELATED_SYSTEM", prompts.CHARACTER_SYSTEM)

    prompt_parts = []
    if state.get("world_setting"):
        prompt_parts.append(f"World setting:\n{state['world_setting']}")
    prompt_parts.append(f"Existing character ({source_name}):\n{source_details}")
    prompt_parts.append(f"Relationship to create: {relationship}")
    prompt_parts.append(
        "Hard constraints:\n"
        "- Create a NEW, distinct person related to the existing character.\n"
        "- Do NOT rewrite or clone the existing character.\n"
        "- Use a different name, appearance, personality, and backstory.\n"
        "- Explicitly reflect the requested relationship in the new character profile."
    )
    if context:
        prompt_parts.append(f"Additional context:\n{context}")
    if raw_idea:
        prompt_parts.append(f"Original concept: {raw_idea}")
    prompt = "\n\n".join(prompt_parts)

    generated = call_local_llm(related_system, prompt, max_length=max_length)

    def _norm_text(value: str) -> str:
        return re.sub(r"\W+", " ", str(value or "").lower()).strip()

    source_norm = _norm_text(source_details)
    generated_norm = _norm_text(generated)
    if source_norm and generated_norm and (
        generated_norm == source_norm or generated_norm in source_norm or source_norm in generated_norm
    ):
        retry_prompt = (
            f"{prompt}\n\n"
            "CRITICAL RETRY: Your previous output repeated the source character.\n"
            "Return a clearly different related character with a unique identity and name."
        )
        generated = call_local_llm(related_system, retry_prompt, max_length=max_length)

    name = infer_character_name(generated, fallback=f"{relationship_label.title()} Ally")
    existing_names = {
        _norm_text(str(character.get("name") or ""))
        for character in source_characters
        if isinstance(character, dict)
    }
    normalized_name = _norm_text(name)
    if not normalized_name or normalized_name in existing_names or normalized_name == _norm_text(source_name):
        base_name = f"{relationship_label.title()} Ally".strip()
        if not base_name:
            base_name = "Related Ally"
        candidate = base_name
        suffix = 2
        while _norm_text(candidate) in existing_names:
            candidate = f"{base_name} {suffix}"
            suffix += 1
        name = candidate

    inverse_relationship = _inverse_relationship_label(
        relationship_label=relationship_label,
        source_name=source_name,
        related_name=name,
        persona_id=persona_id,
    )
    new_characters = list(state.get("characters", []))
    updated_source = dict(new_characters[source_character_index])
    source_id = str(updated_source.get("id") or "").strip()
    if not source_id:
        source_id = _make_character_urn()
        updated_source["id"] = source_id

    source_relationships = _coerce_relationships(updated_source.get("relationships"))
    new_id = _make_character_urn()
    new_character: Dict[str, Any] = {
        "id": new_id,
        "name": name,
        "details": generated.strip(),
        "role": "character",
        "tags": [],
        "relationships": {source_id: relationship_label},
    }

    source_relationships[new_id] = inverse_relationship
    updated_source["relationships"] = source_relationships

    new_characters[source_character_index] = updated_source
    new_characters.append(new_character)
    state["characters"] = new_characters

    save_draft_state(
        {"raw_idea": raw_idea, "state": state, "meta": {"mode": "character"}, "save_pending": True},
        "latest",
        artifact_type="character",
    )
    return {"state": state, "character": new_character}


@router.post("/draft")
async def save_draft(body: Dict[str, Any]) -> Dict[str, Any]:
    artifact_type = str(body.get("artifact_type") or "world").strip().lower()
    if bool(body.get("clear", False)):
        deleted = delete_draft_state("latest", artifact_type=artifact_type)
        return {
            "ok": True,
            "cleared": True,
            "deleted": deleted,
        }

    payload = {
        "raw_idea": body.get("raw_idea", ""),
        "state": body.get("state", {}),
        "meta": body.get("meta", {}),
        "save_pending": bool(body.get("save_pending", False)),
    }
    saved = save_draft_state(payload, "latest", artifact_type=artifact_type)
    return {
        **saved,
        "ok": True,
    }


@router.post("/character-image")
async def generate_character_image(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    state = _normalize_state(raw_idea, body.get("state"))
    character_index = max(0, int(body.get("character_index", 0)))
    mode = str(body.get("mode", "full")).strip().lower()
    style_name = str(body.get("style", "")).strip().lower() or None
    sd_config = body.get("sd_config") if isinstance(body.get("sd_config"), dict) else {}

    if mode not in {"full", "prompt", "image"}:
        raise HTTPException(status_code=400, detail="mode must be one of: full, prompt, image")

    if character_index >= len(state.get("characters", [])):
        raise HTTPException(status_code=400, detail="character_index is out of range")

    character = state["characters"][character_index]
    prompt_override = body.get("prompt_override")

    if mode == "prompt":
        prompt = _make_sd_prompt(state, character, prompt_override=prompt_override)
        updated_character = {
            **character,
            "image_prompt": prompt,
        }
    else:
        _assert_sd_available(sd_config.get("endpoint") if isinstance(sd_config, dict) else None)
        if mode == "image":
            prompt = (prompt_override or "").strip() or str(character.get("image_prompt") or "").strip()
            if not prompt:
                raise HTTPException(
                    status_code=400,
                    detail="No existing image prompt found. Regenerate prompt first or provide prompt_override.",
                )
        else:
            prompt = _make_sd_prompt(state, character, prompt_override=prompt_override)

        try:
            image_path, image_data, styled_prompt, resolved_style = _render_sd_image(
                prompt,
                style_name=style_name,
                sd_config=sd_config,
            )
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail="Failed to render image from Stable Diffusion endpoint") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        updated_character = {
            **character,
            "image_prompt": prompt,
            "image_prompt_styled": styled_prompt,
            "image_style": resolved_style,
            "image_path": image_path,
            "image_data": image_data,
        }

    updated_characters = list(state["characters"])
    updated_characters[character_index] = updated_character
    state["characters"] = updated_characters

    save_draft_state(
        {
            "raw_idea": state.get("raw_idea", ""),
            "state": state,
            "meta": body.get("meta", {}),
            "save_pending": bool(body.get("save_pending", False)),
        },
        "latest",
        artifact_type="character",
    )

    return {
        "state": state,
        "character_index": character_index,
        "character": updated_character,
    }


@router.get("/sd-styles")
async def get_sd_styles(include_defaults: bool = Query(True)) -> Dict[str, Any]:
    resolved_styles, resolved_default = resolve_sd_styles(include_builtin_defaults=include_defaults)
    return {
        "default_style": resolved_default,
        "styles": list(resolved_styles.keys()),
        "style_data": {
            k: {"prompt": v.get("prompt", ""), "negative_prompt": v.get("negative_prompt", "")}
            for k, v in resolved_styles.items()
        },
    }


@router.post("/run")
async def run_workflow(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    auto_save: bool = body.get("auto_save", True)
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config = {**experimentation_config, "persona_id": persona_id}
    initial_state: WizardState = {
        "raw_idea": raw_idea,
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }

    state = dict(initial_state)
    next_stage = "loremaster"
    start = time.monotonic()
    # Run staged pipeline so persona-aware prompts are respected.
    for _ in range(8):
        if next_stage == "save_assets":
            break
        next_stage = _run_stage_sync(
            state,
            next_stage,
            experimentation_config=experimentation_config,
        )
        if state.get("passed_inspection") and next_stage == "save_assets":
            break
    elapsed_ms = round((time.monotonic() - start) * 1000)

    payload = {
        "raw_idea": raw_idea,
        "state": dict(state),
        "meta": {"elapsed_ms": elapsed_ms},
    }

    save_draft_state({**payload, "save_pending": not auto_save}, "latest", artifact_type="world")

    if auto_save:
        saved = save_run_result(payload)
        return {
            "run_id": saved["run_id"],
            "run_path": saved["run_path"],
            "filename": saved["filename"],
            "state": dict(state),
            "meta": {"elapsed_ms": elapsed_ms},
        }

    return {
        "pending_save": True,
        "state": dict(state),
        "meta": {"elapsed_ms": elapsed_ms},
    }


@router.post("/step")
async def run_single_step(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    stage: str = body.get("stage", "loremaster")
    continue_output: bool = bool(body.get("continue_output", False))
    directive: str = str(body.get("directive", ""))
    character_index: int = max(0, int(body.get("character_index", 0)))
    experimentation_config: dict[str, Any] = body.get("experimentation_config", {})
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config = {**experimentation_config, "persona_id": persona_id}
    state = _normalize_state(raw_idea, body.get("state"))

    start = time.monotonic()

    next_stage = _run_stage_sync(
        state,
        stage,
        continue_output=continue_output,
        directive=directive,
        character_index=character_index,
        experimentation_config=experimentation_config,
    )

    elapsed_ms = round((time.monotonic() - start) * 1000)
    save_pending = stage == "editor" and state.get("passed_inspection")
    response: Dict[str, Any] = {
        "state": state,
        "meta": {"elapsed_ms": elapsed_ms},
        "next_stage": next_stage,
    }

    if save_pending:
        response["save_pending"] = True

    save_draft_state(
        {
            "raw_idea": raw_idea,
            "state": state,
            "meta": {"elapsed_ms": elapsed_ms, "next_stage": next_stage, "stage": stage},
            "save_pending": save_pending,
        },
        "latest",
        artifact_type="world",
    )

    return response


@router.post("/step-stream")
async def run_single_step_stream(body: Dict[str, Any], request: Request) -> EventSourceResponse:
    raw_idea: str = body.get("raw_idea", "")
    stage: str = body.get("stage", "loremaster")
    continue_output: bool = bool(body.get("continue_output", False))
    directive: str = str(body.get("directive", ""))
    character_index: int = max(0, int(body.get("character_index", 0)))
    experimentation_config: dict = body.get("experimentation_config", {})
    persona_id: str = str(body.get("persona_id", "blank"))
    experimentation_config = {**experimentation_config, "persona_id": persona_id}
    state = _normalize_state(raw_idea, body.get("state"))
    return EventSourceResponse(
        _run_stage_stream(
            state,
            stage,
            request,
            continue_output=continue_output,
            directive=directive,
            character_index=character_index,
            experimentation_config=experimentation_config,
        )
    )


@router.post("/review-summary")
async def generate_review_summary(body: Dict[str, Any]) -> Dict[str, Any]:
    original: str = str(body.get("original", ""))
    revised: str = str(body.get("revised", ""))
    stage: str = str(body.get("stage", ""))
    persona_id: str = str(body.get("persona_id", "blank"))

    if not revised.strip():
        return {
            "summary": "- Modified: Waiting for generated output.\n- Added: Waiting for generated output.\n- Removed: Waiting for generated output.",
        }

    stage_hint = stage.replace("_", " ").strip() or "draft"
    prompt = (
        f"Stage: {stage_hint}\n\n"
        "Write a human narrative summary of how the revised draft differs from the original.\n"
        "Use exactly this structure and keep each bullet to 1-2 sentences:\n"
        "- Modified: describe the major shifts in focus, tone, structure, or framing.\n"
        "- Added: describe the most meaningful new ideas or details.\n"
        "- Removed: describe what emphasis, constraints, or details were dropped.\n\n"
        "Rules:\n"
        "- No numeric estimates or counts.\n"
        "- No mention of tokens, sentences, or statistics.\n"
        "- Be specific enough to guide an approve/reject decision.\n\n"
        f"Original:\n{original}\n\n"
        f"Revised:\n{revised}\n"
    )

    summary = call_local_llm(get_persona_prompts(persona_id).REVIEW_SUMMARY_SYSTEM, prompt, max_length=360)
    return {"summary": summary.strip()}
