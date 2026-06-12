import base64
from pathlib import Path

from fastapi.testclient import TestClient

from lorebook.api import storage
from lorebook.api.app import create_app


def test_restore_latest_returns_draft_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    storage.save_draft_state(
        {
            "raw_idea": "draft idea",
            "state": {"world_setting": "draft world"},
            "meta": {"elapsed_ms": 5},
            "save_pending": True,
        }
    )

    client = TestClient(create_app())
    res = client.get("/api/restore-latest")

    assert res.status_code == 200
    payload = res.json()
    assert payload["draft"]["raw_idea"] == "draft idea"
    assert "latest_run" not in payload


def test_draft_endpoint_persists_latest_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    client = TestClient(create_app())
    res = client.post(
        "/api/draft",
        json={
            "raw_idea": "draft input",
            "state": {"world_setting": "v1"},
            "meta": {"elapsed_ms": 17},
            "save_pending": True,
        },
    )

    assert res.status_code == 200
    loaded = storage.load_draft_state()
    assert loaded is not None
    assert loaded["raw_idea"] == "draft input"
    assert loaded["save_pending"] is True


def test_character_image_endpoint_updates_state(tmp_path: Path, monkeypatch) -> None:
    from lorebook.api.routes import run as run_routes

    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(run_routes, "_outputs_images_dir", lambda: images_dir)

    encoded = base64.b64encode(b"fake-png-bytes").decode("ascii")

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"images": [encoded]}

    monkeypatch.setattr(run_routes.requests, "get", lambda *args, **kwargs: _FakeResponse())
    monkeypatch.setattr(run_routes.requests, "post", lambda *args, **kwargs: _FakeResponse())

    client = TestClient(create_app())
    res = client.post(
        "/api/character-image",
        json={
            "raw_idea": "idea",
            "state": {
                "raw_idea": "idea",
                "world_setting": "setting",
                "characters": [{"name": "Companion", "details": "desc"}],
                "critique_notes": "",
                "passed_inspection": False,
            },
            "character_index": 0,
            "prompt_override": "manual prompt",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    character = payload["state"]["characters"][0]
    assert character["image_prompt"] == "manual prompt"
    assert character["image_data"].startswith("data:image/png;base64,")
    assert Path(character["image_path"]).exists()


def test_character_image_endpoint_fails_before_prompt_generation_when_sd_unavailable(monkeypatch) -> None:
    from lorebook.api.routes import run as run_routes

    calls = {"llm": 0}

    class _FailingResponse:
        def raise_for_status(self) -> None:
            raise run_routes.requests.RequestException("offline")

    def fake_llm(*args, **kwargs):
        calls["llm"] += 1
        return "should not be called"

    monkeypatch.setattr(run_routes.requests, "get", lambda *args, **kwargs: _FailingResponse())
    monkeypatch.setattr(run_routes, "call_local_llm", fake_llm)

    client = TestClient(create_app())
    res = client.post(
        "/api/character-image",
        json={
            "raw_idea": "idea",
            "state": {
                "raw_idea": "idea",
                "world_setting": "setting",
                "characters": [{"name": "", "details": "desc"}],
                "critique_notes": "",
                "passed_inspection": False,
            },
            "character_index": 0,
        },
    )

    assert res.status_code == 503
    assert res.json()["detail"] == "Stable Diffusion AUTOMATIC1111 API is unavailable. Start it before generating an image."
    assert calls["llm"] == 0


def test_step_with_directive_overwrites_not_appends(monkeypatch) -> None:
    from lorebook.api.routes import run as run_routes

    calls = {"count": 0}

    def fake_llm(system_prompt: str, user_prompt: str, **kwargs) -> str:
        _ = system_prompt
        _ = user_prompt
        _ = kwargs
        calls["count"] += 1
        return f"generated_{calls['count']}"

    monkeypatch.setattr(run_routes, "call_local_llm", fake_llm)

    client = TestClient(create_app())

    initial_state = {
        "raw_idea": "idea",
        "world_setting": "old_text",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }

    res = client.post(
        "/api/step",
        json={
            "raw_idea": "idea",
            "state": initial_state,
            "stage": "loremaster",
            "continue_output": False,
            "directive": "refine this",
        },
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["state"]["world_setting"] == "generated_1"
    assert payload["state"]["world_setting"] != "old_textgenerated_1"