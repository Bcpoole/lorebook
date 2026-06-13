from pathlib import Path
import time

from lorebook.api import storage


def test_save_and_load_latest_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    first = storage.save_run_result({"raw_idea": "a", "state": {}, "meta": {}}, filename="first")
    time.sleep(0.005)
    second = storage.save_run_result({"raw_idea": "b", "state": {"world_setting": "x"}, "meta": {}}, filename="second")

    loaded_second = storage.load_run(second["run_id"])
    assert loaded_second is not None
    assert loaded_second["raw_idea"] == "b"

    latest = storage.load_latest_run()
    assert latest is not None
    assert latest["run_id"] == second["run_id"]

    loaded_first = storage.load_run(first["run_id"])
    assert loaded_first is not None
    assert loaded_first["raw_idea"] == "a"


def test_save_and_load_draft(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    saved = storage.save_draft_state(
        {
            "raw_idea": "draft idea",
            "state": {"world_setting": "draft world"},
            "meta": {"elapsed_ms": 12},
            "save_pending": True,
        }
    )
    assert saved["draft_id"] == "latest"

    loaded = storage.load_draft_state()
    assert loaded is not None
    assert loaded["raw_idea"] == "draft idea"
    assert loaded["save_pending"] is True


def test_save_run_precomputes_preview_and_gallery_listing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    storage.save_run_result(
        {
            "raw_idea": "storm city",
            "state": {
                "story_artifact": {
                    "title": "Storm City",
                    "description": "A city above the clouds with arcane weather engines.",
                    "plot": ["engine fails"],
                    "setting": "Cloud belts",
                    "style": "grim",
                    "tags": ["fantasy", "storm"],
                    "characters_artifact": [],
                    "locations": [],
                    "objects": [],
                    "opening": "",
                    "examples": [],
                },
                "characters": [{"name": "Ari", "details": "Pilot", "role": "character", "tags": ["pilot"]}],
            },
            "meta": {},
        },
        filename="storm_city",
    )

    listing = storage.list_run_previews(search="clouds", tag="storm")
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["title"] == "Storm City"
    assert "storm" in item["tags"]
    assert "pilot" in item["tags"]


def test_update_character_role_persists_to_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    saved = storage.save_run_result(
        {
            "raw_idea": "idea",
            "state": {"characters": [{"name": "Ari", "details": "Pilot", "role": "character"}]},
            "meta": {},
        },
        filename="role_run",
    )

    updated = storage.update_character_role(saved["run_id"], 0, "persona")
    assert updated is not None
    assert updated["state"]["characters"][0]["role"] == "persona"

    loaded = storage.load_run(saved["run_id"])
    assert loaded is not None
    assert loaded["state"]["characters"][0]["role"] == "persona"