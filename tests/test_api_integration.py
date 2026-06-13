import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lorebook.api import storage
from lorebook.api.app import create_app


@pytest.fixture(autouse=True)
def _isolate_outputs_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)


def test_restore_latest_returns_draft_only(tmp_path: Path, monkeypatch) -> None:
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


def test_llm_health_endpoint_reports_connectivity(monkeypatch) -> None:
    from lorebook.api.routes import run as run_routes

    monkeypatch.setattr(run_routes, "is_local_llm_available", lambda: False)

    client = TestClient(create_app())
    res = client.get("/api/llm-health")

    assert res.status_code == 200
    assert res.json() == {"connected": False}


def test_app_health_endpoint_reports_ok() -> None:
    client = TestClient(create_app())
    res = client.get("/api/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_draft_endpoint_can_clear_latest_draft() -> None:
    storage.save_draft_state(
        {
            "raw_idea": "draft input",
            "state": {"world_setting": "v1"},
            "meta": {"elapsed_ms": 17},
            "save_pending": False,
        }
    )

    client = TestClient(create_app())
    res = client.post("/api/draft", json={"clear": True})

    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload["cleared"] is True
    assert storage.load_draft_state() is None


def test_character_designer_rejects_meta_responses(monkeypatch) -> None:
    """Verify character_designer guardrail retries on meta responses like 'I understand...'."""
    from lorebook.api.routes import run as run_routes

    calls = {"count": 0, "prompts": []}

    def fake_llm(system_prompt: str, user_prompt: str, **kwargs) -> str:
        _ = system_prompt
        calls["count"] += 1
        calls["prompts"].append(user_prompt[:100])
        # First call returns meta response, second call returns real character
        if calls["count"] == 1:
            return "I understand the world rules. Please provide instructions for the character design."
        return "# Character: Test Hero\n\nA brave and noble companion with a strong sense of duty."

    monkeypatch.setattr(run_routes, "call_local_llm", fake_llm)

    client = TestClient(create_app())

    state_with_world = {
        "raw_idea": "test idea",
        "world_setting": "A mystical realm with ancient rules.",
        "characters": [],
        "critique_notes": "",
        "passed_inspection": False,
    }

    res = client.post(
        "/api/step",
        json={
            "raw_idea": "test idea",
            "state": state_with_world,
            "stage": "character_designer",
            "continue_output": False,
            "directive": "",
            "character_index": 0,
        },
    )

    assert res.status_code == 200
    payload = res.json()
    
    # Should have called LLM twice (initial + retry after meta rejection)
    assert calls["count"] == 2
    
    # Character details should be from successful second call, not meta response
    character_details = payload["state"]["characters"][0]["details"]
    assert "I understand" not in character_details
    assert "Character: Test Hero" in character_details or "brave and noble" in character_details


def test_story_endpoint_returns_structured_artifact(monkeypatch) -> None:
    from lorebook.api.routes import run as run_routes

    monkeypatch.setattr(
        run_routes,
        "call_local_llm",
        lambda *args, **kwargs: (
            '{"title":"Skyfall","description":"A compact description.","plot":["A","B"],'
            '"setting":"Sky archipelago","style":"heroic","tags":["sky"],'
            '"characters_artifact":[{"name":"Ari","role":"pilot","summary":"ace","tags":["pilot"]}],'
            '"locations":[{"name":"Dock","description":"windy","tags":["port"]}],'
            '"objects":[{"name":"Compass","description":"arcane","tags":["artifact"]}],'
            '"opening":"Once above the storm.","examples":[{"label":"sample","text":"line"}]}'
        ),
    )

    client = TestClient(create_app())
    res = client.post("/api/story", json={"raw_idea": "flying city"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["story_artifact"]["title"] == "Skyfall"
    assert isinstance(payload["story_artifact"]["characters_artifact"], list)


def test_character_endpoint_returns_single_character(monkeypatch) -> None:
    from lorebook.api.routes import run as run_routes

    monkeypatch.setattr(run_routes, "call_local_llm", lambda *args, **kwargs: "Character: Mira\nA precise navigator.")

    client = TestClient(create_app())
    res = client.post("/api/character", json={"raw_idea": "navigator"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["character"]["details"].startswith("Character:")
    assert payload["character"]["role"] == "character"


def test_gallery_endpoint_lists_saved_runs_and_role_toggle() -> None:
    saved = storage.save_run_result(
        {
            "raw_idea": "idea",
            "state": {"characters": [{"name": "Ari", "details": "pilot", "role": "character"}]},
            "meta": {},
        },
        filename="gallery_case",
    )
    client = TestClient(create_app())

    gallery_res = client.get("/api/gallery")
    assert gallery_res.status_code == 200
    items = gallery_res.json()["items"]
    assert any(item["run_id"] == saved["run_id"] for item in items)

    role_res = client.post(
        "/api/character-role",
        json={"run_id": saved["run_id"], "character_index": 0, "role": "persona"},
    )
    assert role_res.status_code == 200
    assert role_res.json()["run"]["state"]["characters"][0]["role"] == "persona"