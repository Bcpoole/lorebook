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