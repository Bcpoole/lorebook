from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes import (
    character_designer_node,
    editor_node,
    loremaster_node,
    route_after_critique,
    save_assets_node,
)
from .state import WizardState


def build_app():
    workflow = StateGraph(WizardState)

    workflow.add_node("loremaster", loremaster_node)
    workflow.add_node("character_designer", character_designer_node)
    workflow.add_node("editor", editor_node)
    workflow.add_node("save_assets", save_assets_node)

    workflow.set_entry_point("loremaster")
    workflow.add_edge("loremaster", "character_designer")
    workflow.add_edge("character_designer", "editor")
    workflow.add_conditional_edges(
        "editor",
        route_after_critique,
        {
            "loremaster": "loremaster",
            "save_assets": "save_assets",
        },
    )
    workflow.add_edge("save_assets", END)

    return workflow.compile()


app = build_app()
