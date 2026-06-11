from typing import Dict, TypedDict, List
from langgraph.graph import StateGraph, END
import requests

# 1. Define the shared state structure
class WizardState(TypedDict):
    raw_idea: str
    world_setting: str
    characters: List[Dict[str, str]]
    critique_notes: str
    passed_inspection: bool

# Helper to call your local GGUF endpoint (e.g., KoboldCPP default port)
def call_local_llm(system_prompt: str, user_prompt: str) -> str:
    response = requests.post(
        "http://localhost:5001/api/v1/generate",
        json={
            "prompt": f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{user_prompt}<|im_end|>\n<|im_start|>assistant\n",
            "max_context_length": 8192,
            "max_length": 1024,
            "temperature": 0.7
        }
    )
    return response.json()['results'][0]['text']

# 2. Define the Agent Nodes
def loremaster_node(state: WizardState) -> Dict:
    sys = "You are an expert world builder. Expand the user's idea into a structured setting with 3 distinct world rules."
    res = call_local_llm(sys, state["raw_idea"])
    return {"world_setting": res}

def character_designer_node(state: WizardState) -> Dict:
    sys = "You are a SillyTavern character designer. Create 1 main companion character based on this world setting. Format as clean text."
    res = call_local_llm(sys, state["world_setting"])
    # In a production script, you'd use structured JSON parsing here
    return {"characters": [{"name": "Companion", "details": res}]}

def editor_node(state: WizardState) -> Dict:
    sys = "You are a critical editor. Review the character design against the world setting. If it feels generic or breaks the world rules, write critique. If it is excellent, reply exactly with: PASSED."
    prompt = f"Setting:\n{state['world_setting']}\n\nCharacter:\n{state['characters'][0]['details']}"
    res = call_local_llm(sys, prompt)
    
    if "PASSED" in res:
        return {"passed_inspection": True, "critique_notes": ""}
    return {"passed_inspection": False, "critique_notes": res}

# 3. Router logic
def route_after_critique(state: WizardState):
    if state["passed_inspection"]:
        return "save_assets"
    return "loremaster" # Loop back to fix it if it fails

def save_assets_node(state: WizardState):
    print("--- Wizard Complete! Exporting SillyTavern Assets ---")
    # File writing logic goes here
    return state

# 4. Build the Graph
workflow = StateGraph(WizardState)

workflow.add_node("loremaster", loremaster_node)
workflow.add_node("character_designer", character_designer_node)
workflow.add_node("editor", editor_node)
workflow.add_node("save_assets", save_assets_node)

workflow.set_entry_point("loremaster")
workflow.add_edge("loremaster", "character_designer")
workflow.add_edge("character_designer", "editor")

# Conditional routing based on the Editor's check
workflow.add_conditional_edges(
    "editor",
    route_after_critique,
    {
        "loremaster": "loremaster",
        "save_assets": "save_assets"
    }
)
workflow.add_edge("save_assets", END)

app = workflow.compile()
# # This tells LangGraph to stop and yield control back to you before executing 'save_assets'
# app = workflow.compile(interrupt_before=["save_assets"])