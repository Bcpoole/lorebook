from __future__ import annotations

from typing import Dict

from .llm import call_local_llm
from .state import WizardState


def loremaster_node(state: WizardState) -> Dict[str, str]:
    system_prompt = (
        "You are an expert world builder. Expand the user's idea into a "
        "structured setting with 3 distinct world rules."
    )
    result = call_local_llm(system_prompt, state["raw_idea"])
    return {"world_setting": result}


def character_designer_node(state: WizardState) -> Dict[str, list[Dict[str, str]]]:
    system_prompt = (
        "You are a SillyTavern character designer. Create 1 main companion "
        "character based on this world setting. Format as clean text."
    )
    result = call_local_llm(system_prompt, state["world_setting"])
    return {"characters": [{"name": "Companion", "details": result}]}


def editor_node(state: WizardState) -> Dict[str, str | bool]:
    system_prompt = (
        "You are a critical editor. Review the character design against the "
        "world setting. If it feels generic or breaks the world rules, write "
        "critique. If it is excellent, reply exactly with: PASSED."
    )
    prompt = (
        f"Setting:\n{state['world_setting']}\n\n"
        f"Character:\n{state['characters'][0]['details']}"
    )
    result = call_local_llm(system_prompt, prompt)

    if "PASSED" in result:
        return {"passed_inspection": True, "critique_notes": result}
    return {"passed_inspection": False, "critique_notes": result}


def save_assets_node(state: WizardState) -> WizardState:
    print("--- Wizard Complete! Exporting SillyTavern Assets ---")
    return state


def route_after_critique(state: WizardState) -> str:
    if state["passed_inspection"]:
        return "save_assets"
    return "loremaster"
