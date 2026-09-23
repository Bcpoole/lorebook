from lorebook.workflow.graph import app
from lorebook.workflow.nodes import route_after_critique


def test_app_compiles() -> None:
    assert app is not None


def test_route_after_critique_to_save_assets() -> None:
    state = {
        "raw_idea": "",
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": True,
    }
    assert route_after_critique(state) == "save_assets"


def test_route_after_critique_to_loremaster() -> None:
    state = {
        "raw_idea": "",
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }
    assert route_after_critique(state) == "loremaster"
