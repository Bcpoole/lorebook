from pathlib import Path

from lorebook.characters import infer_character_name
from lorebook.nodes import character_designer_node, editor_node, loremaster_node

RESOURCES_DIR = Path(__file__).parent / "resources"


def _read_fixture(name: str) -> str:
    return (RESOURCES_DIR / name).read_text(encoding="utf-8")


def test_loremaster_uses_saved_real_output(monkeypatch) -> None:
    expected = _read_fixture("world_setting.txt")

    def fake_llm(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return expected

    monkeypatch.setattr("lorebook.nodes.call_local_llm", fake_llm)

    state = {
        "raw_idea": "test idea",
        "world_setting": "",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }
    out = loremaster_node(state)
    assert out["world_setting"] == expected


def test_character_designer_uses_saved_real_output(monkeypatch) -> None:
    expected = _read_fixture("character.txt")

    def fake_llm(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return expected

    monkeypatch.setattr("lorebook.nodes.call_local_llm", fake_llm)

    state = {
        "raw_idea": "",
        "world_setting": "fixture world",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }
    out = character_designer_node(state)
    assert out["characters"][0]["name"] == infer_character_name(expected, fallback="Character 1")
    assert out["characters"][0]["name"] != "Companion"
    assert out["characters"][0]["details"] == expected


def test_infer_character_name_removes_titles_and_quoted_nicknames() -> None:
    details = '**Name:** Derek "Big Grocery" Thornton\n**Role:** Store manager'
    assert infer_character_name(details, fallback="Character 1") == "Derek Thornton"

    details = '**Name:** Kai "The Aisle Runner" Nakamura\n**Role:** Courier'
    assert infer_character_name(details, fallback="Character 1") == "Kai Nakamura"


def test_editor_node_offline_non_passed(monkeypatch) -> None:
    critique = _read_fixture("editor_critique.txt").replace("PASSED", "REJECTED")

    def fake_llm(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return critique

    monkeypatch.setattr("lorebook.nodes.call_local_llm", fake_llm)

    state = {
        "raw_idea": "",
        "world_setting": "fixture world",
        "characters": [{"name": "Companion", "details": "fixture character"}],
        "critique_notes": "",
        "passed_inspection": False,
    }
    out = editor_node(state)
    assert out["passed_inspection"] is False
    assert out["critique_notes"] == critique


def test_editor_node_offline_passed(monkeypatch) -> None:
    def fake_llm(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        _ = user_prompt
        return "PASSED"

    monkeypatch.setattr("lorebook.nodes.call_local_llm", fake_llm)

    state = {
        "raw_idea": "",
        "world_setting": "fixture world",
        "characters": [{"name": "Companion", "details": "fixture character"}],
        "critique_notes": "",
        "passed_inspection": False,
    }
    out = editor_node(state)
    assert out["passed_inspection"] is True
    assert out["critique_notes"] == "PASSED"


def test_editor_node_uses_all_characters(monkeypatch) -> None:
    captured = {"prompt": ""}

    def fake_llm(system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        captured["prompt"] = user_prompt
        return "PASSED"

    monkeypatch.setattr("lorebook.nodes.call_local_llm", fake_llm)

    state = {
        "raw_idea": "",
        "world_setting": "fixture world",
        "characters": [
            {"name": "A", "details": "first details"},
            {"name": "B", "details": "second details"},
        ],
        "critique_notes": "",
        "passed_inspection": False,
    }
    out = editor_node(state)
    assert out["passed_inspection"] is True
    assert "first details" in captured["prompt"]
    assert "second details" in captured["prompt"]
