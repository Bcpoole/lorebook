from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from lorebook.characters import clean_character_name
from lorebook.config.prompts import get_persona_prompts
from lorebook.errors import ArtifactAssemblyError
from lorebook.llm import call_local_llm
from lorebook.workflow.normalization import _clean_story_label, _coerce_story_artifact
from lorebook.workflow.state import StoryArtifact
from lorebook.workflow.text import _extract_first_json_block


_STORY_ORCHESTRATOR_SYSTEM = (
    "You are the story-generation orchestrator. Coordinate the specialist writers by identifying "
    "dependencies, consistency constraints, and how their sections should fit together. Return only "
    "concise coordination notes for the specialists. Do not author any story artifact field, including "
    "the title, description, setting, style, tags, brief, plot, history, characters, locations, objects, "
    "or openings. Do not use JSON or markdown."
)


@dataclass(frozen=True, slots=True)
class StorySectionSpec:
    section: str
    system_prompt: str
    minimum_tokens: int


_STORY_SECTION_SPECS: tuple[StorySectionSpec, ...] = (
    StorySectionSpec(
        section="brief",
        system_prompt=(
            "You are the story-brief specialist. Using the user's concept and the orchestrator's coordination "
            "notes, state the premise, conflict, stakes, and tone in a compact creative brief. "
            "Return only the brief."
        ),
        minimum_tokens=160,
    ),
    StorySectionSpec(
        section="description",
        system_prompt=(
            "You are the story-description specialist. Using the story brief, write a concise description of "
            "the story in 128 words or fewer. Return only the description."
        ),
        minimum_tokens=160,
    ),
    StorySectionSpec(
        section="setting",
        system_prompt=(
            "You are the story-setting specialist. Using the story brief, write a rich 2-3 paragraph world "
            "description covering place, atmosphere, relevant rules, and sensory details. "
            "Return only the setting as prose paragraphs."
        ),
        minimum_tokens=120,
    ),
    StorySectionSpec(
        section="style",
        system_prompt=(
            "You are the story-style specialist. Using the story brief, name the story's genre, tone, and "
            "narrative style in one concise phrase. Return only the style phrase."
        ),
        minimum_tokens=80,
    ),
    StorySectionSpec(
        section="tags",
        system_prompt=(
            "You are the story-tag specialist. Using the story brief, provide 3-6 concise discovery tags as "
            "a comma-separated list without a label."
        ),
        minimum_tokens=80,
    ),
    StorySectionSpec(
        section="title",
        system_prompt=(
            "You are the title specialist. Using the story brief, create one evocative, specific title. "
            "Return only the title on one line."
        ),
        minimum_tokens=80,
    ),
    StorySectionSpec(
        section="plot",
        system_prompt=(
            "You are the plot specialist. Using the story brief, write one cohesive plot or premise section. "
            "Return only the plot or premise."
        ),
        minimum_tokens=400,
    ),
    StorySectionSpec(
        section="history",
        system_prompt=(
            "You are the story-history specialist. Summarize the important events immediately before the "
            "story begins, emphasizing causes and unresolved consequences. "
            "Return only the history as concise prose or bullets, without repeating the plot."
        ),
        minimum_tokens=220,
    ),
    StorySectionSpec(
        section="characters_artifact",
        system_prompt=(
            "You are the character specialist. Using the story brief, create 2-4 story-relevant characters. "
            "For each character, use exactly these labeled lines, separated by a blank line:\n"
            "Name: <name>\nRole: <role>\nSummary: <concise summary>\nTags: <comma-separated tags>\n"
            "The Name value must be a plain personal name only: no ranks, titles, nicknames, quoted aliases, "
            "parenthetical epithets, or descriptive monikers."
        ),
        minimum_tokens=320,
    ),
    StorySectionSpec(
        section="locations",
        system_prompt=(
            "You are the location specialist. Using the story brief, create 2-3 locations that matter to the plot. "
            "For each location, use exactly these labeled lines, separated by a blank line:\n"
            "Name: <name>\nDescription: <concise description>\nTags: <comma-separated tags>"
        ),
        minimum_tokens=280,
    ),
    StorySectionSpec(
        section="objects",
        system_prompt=(
            "You are the story-object specialist. Using the story brief, create 1-3 meaningful objects that "
            "advance, complicate, or symbolize the story. For each object, use exactly these labeled lines, "
            "separated by a blank line:\nName: <name>\nDescription: <concise description>\n"
            "Tags: <comma-separated tags>"
        ),
        minimum_tokens=120,
    ),
    StorySectionSpec(
        section="openings",
        system_prompt=(
            "You are the opening-scene specialist. Using the story brief, write a compelling, self-contained "
            "opening of 2-4 paragraphs that establishes the protagonist, setting, and immediate tension. "
            "Return only the opening as prose paragraphs."
        ),
        minimum_tokens=360,
    ),
)


def _persona_layered_system_prompt(base_prompt: str, persona_id: str, role: str) -> str:
    """Layer persona direction under a task's structural contract."""
    if not persona_id or persona_id == "blank":
        return base_prompt

    prompts = get_persona_prompts(persona_id)
    guidance = (
        prompts.CHARACTER_SYSTEM
        if role == "character"
        else prompts.EDITOR_SYSTEM
        if role == "editor"
        else prompts.LOREMASTER_SYSTEM
    )
    if not guidance.strip():
        return base_prompt
    return (
        f"{base_prompt}\n\n"
        "PERSONA LAYER:\n"
        "Use the following persona guidance for creative priorities, voice, tone, and taste. "
        "The task instructions and output format above take precedence over any conflicting format "
        f"instructions in this layer.\n{guidance}"
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
    artifact = _coerce_story_artifact(
        {
            "title": (sections.get("title") or {}).get("title", ""),
            "description": (sections.get("description") or {}).get("description", ""),
            "plot": (sections.get("plot") or {}).get("plot", ""),
            "setting": (sections.get("setting") or {}).get("setting", ""),
            "style": (sections.get("style") or {}).get("style", "") or persona_id,
            "history": (sections.get("history") or {}).get("history", ""),
            "tags": (sections.get("tags") or {}).get("tags", []),
            "characters_artifact": (sections.get("characters_artifact") or {}).get(
                "characters_artifact", []
            ),
            "locations": (sections.get("locations") or {}).get("locations", []),
            "objects": (sections.get("objects") or {}).get("objects", []),
            "openings": (sections.get("openings") or {}).get("openings", []),
        }
    )
    if artifact is None:
        raise ArtifactAssemblyError("Failed to assemble story artifact")
    return artifact


def _parse_story_section(generated: str, key: str) -> dict[str, Any] | None:
    loaded = _extract_first_json_block(generated)
    if isinstance(loaded, dict):
        value = loaded.get(key)
        if key in {"title", "description", "setting", "style", "brief", "plot", "history"}:
            cleaned = _clean_story_label(value) if key == "title" else str(value or "").strip()
            return {key: cleaned} if cleaned else None
        if isinstance(value, list):
            return {key: value}

    text = generated.strip()
    if not text:
        return None
    if key == "title":
        return {"title": _clean_story_label(text.splitlines()[0].strip().strip("\"'"))}
    if key in {"description", "setting", "style", "brief"}:
        return {key: text}
    if key == "tags":
        tags = [
            _clean_story_label(tag).lower() for tag in text.split(",") if _clean_story_label(tag)
        ]
        return {"tags": tags} if tags else None
    if key == "openings":
        return {
            "openings": [{"description": "", "messages": [{"role": "assistant", "content": text}]}]
        }
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
                match = re.match(
                    r"^(Name|Role|Summary|Description|Tags):\s*(.*)$", line.strip(), re.IGNORECASE
                )
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
                "tags": [
                    tag.strip().lower() for tag in fields.get("tags", "").split(",") if tag.strip()
                ],
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

    coordination_notes = call_local_llm(
        _persona_layered_system_prompt(_STORY_ORCHESTRATOR_SYSTEM, persona_id, "loremaster"),
        prompt,
        max_length=_story_token_budget(max_length, 220),
    )
    if not coordination_notes.strip():
        quality = "partial"
        coordination_notes = "Keep all specialist outputs consistent with the user's concept."
    specialist_context = (
        f"{prompt}\n\nOrchestrator coordination notes:\n{coordination_notes.strip()}"
    )

    for spec in _STORY_SECTION_SPECS:
        role = "character" if spec.section == "characters_artifact" else "loremaster"
        generated = call_local_llm(
            _persona_layered_system_prompt(spec.system_prompt, persona_id, role),
            specialist_context,
            max_length=_story_token_budget(max_length, spec.minimum_tokens),
        )
        parsed = _parse_story_section(generated, spec.section)
        if parsed is None:
            quality = "partial"
            parsed = {
                spec.section: []
                if spec.section
                in {"tags", "characters_artifact", "locations", "objects", "openings"}
                else ""
            }
        sections[spec.section] = parsed
        if spec.section == "brief" and parsed.get("brief"):
            specialist_context = f"{specialist_context}\n\nStory brief:\n{parsed['brief']}"

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
        _persona_layered_system_prompt(
            "You are a story editor. Return ONLY valid JSON that preserves the supplied story schema and applies the requested action.",
            persona_id,
            "editor",
        ),
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
