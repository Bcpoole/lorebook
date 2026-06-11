from __future__ import annotations

import json
from pathlib import Path

from lorebook.llm import call_local_llm

RAW_IDEA = "A city on floating islands above a permanent storm sea."

LOREMASTER_SYSTEM = (
    "You are an expert world builder. Expand the user's idea into a structured "
    "setting with 3 distinct world rules."
)

CHARACTER_SYSTEM = (
    "You are a SillyTavern character designer. Create 1 main companion character "
    "based on this world setting. Format as clean text."
)

EDITOR_SYSTEM = (
    "You are a critical editor. Review the character design against the world "
    "setting. If it feels generic or breaks the world rules, write critique. If "
    "it is excellent, reply exactly with: PASSED."
)


def main() -> None:
    resources_dir = Path(__file__).resolve().parents[1] / "tests" / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    world_setting = call_local_llm(LOREMASTER_SYSTEM, RAW_IDEA, max_length=512)
    character = call_local_llm(CHARACTER_SYSTEM, world_setting, max_length=384)
    editor_prompt = f"Setting:\n{world_setting}\n\nCharacter:\n{character}"
    editor_response = call_local_llm(EDITOR_SYSTEM, editor_prompt, max_length=256)
    critique_prompt = (
        f"Setting:\n{world_setting}\n\n"
        "Character:\nA brave, kind companion with a mysterious past who likes adventure."
    )
    editor_critique = call_local_llm(EDITOR_SYSTEM, critique_prompt, max_length=256)

    (resources_dir / "world_setting.txt").write_text(world_setting, encoding="utf-8")
    (resources_dir / "character.txt").write_text(character, encoding="utf-8")
    (resources_dir / "editor_response.txt").write_text(editor_response, encoding="utf-8")
    (resources_dir / "editor_critique.txt").write_text(editor_critique, encoding="utf-8")

    metadata = {
        "raw_idea": RAW_IDEA,
        "world_setting_file": "world_setting.txt",
        "character_file": "character.txt",
        "editor_response_file": "editor_response.txt",
        "editor_critique_file": "editor_critique.txt",
        "notes": "Fixture captured from a live local LLM run for offline tests.",
    }
    (resources_dir / "fixture_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("Fixture capture complete.")
    print(f"Saved files under: {resources_dir}")


if __name__ == "__main__":
    main()
