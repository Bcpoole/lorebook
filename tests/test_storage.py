import json
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
    snapshot = storage.load_draft_state(draft_id=storage.DRAFT_SNAPSHOT_ID)
    assert snapshot is not None
    assert snapshot["raw_idea"] == "draft idea"


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


def test_artifact_types_save_to_separate_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    world_saved = storage.save_run_result(
        {"raw_idea": "world idea", "state": {"world_setting": "setting"}, "meta": {}},
        filename="world_run",
    )
    story_saved = storage.save_run_result(
        {"raw_idea": "story idea", "state": {"story_artifact": {"title": "Story"}}, "meta": {"source": "story"}},
        filename="story_run",
    )
    character_saved = storage.save_run_result(
        {"raw_idea": "char idea", "state": {"characters": [{"name": "A", "details": "d"}]}, "meta": {"source": "character-page"}},
        filename="character_run",
    )
    location_saved = storage.save_run_result(
        {
            "raw_idea": "location idea",
            "state": {
                "story_artifact": {
                    "title": "Sky Dock",
                    "description": "A floating dock.",
                    "locations": [{"name": "Sky Dock", "description": "A floating dock."}],
                }
            },
            "meta": {"source": "location"},
        },
        filename="location_run",
        artifact_type="location",
    )
    object_saved = storage.save_run_result(
        {
            "raw_idea": "object idea",
            "state": {
                "story_artifact": {
                    "title": "Aether Compass",
                    "description": "An arcane compass.",
                    "objects": [{"name": "Aether Compass", "description": "An arcane compass."}],
                }
            },
            "meta": {"source": "object"},
        },
        filename="object_run",
        artifact_type="object",
    )

    assert Path(world_saved["run_path"]).name == "artifact.json"
    assert Path(world_saved["run_path"]).parent.parent.name == "world"
    assert Path(story_saved["run_path"]).parent.parent.name == "story"
    assert Path(character_saved["run_path"]).parent.parent.name == "character"
    assert Path(location_saved["run_path"]).parent.parent.name == "location"
    assert Path(object_saved["run_path"]).parent.parent.name == "object"

    story_loaded = storage.load_run(story_saved["run_id"], artifact_type="story")
    assert story_loaded is not None
    assert story_loaded["artifact_type"] == "story"

    gallery = storage.list_run_previews()
    by_id = {item["run_id"]: item for item in gallery["items"]}
    assert by_id[world_saved["run_id"]]["artifact_type"] == "world"
    assert by_id[story_saved["run_id"]]["artifact_type"] == "story"
    assert by_id[character_saved["run_id"]]["artifact_type"] == "character"
    assert by_id[location_saved["run_id"]]["artifact_type"] == "location"
    assert by_id[object_saved["run_id"]]["artifact_type"] == "object"


def test_gallery_listing_filters_by_artifact_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    world_saved = storage.save_run_result(
        {"raw_idea": "world idea", "state": {"world_setting": "setting"}, "meta": {}},
        filename="world_filter",
    )
    location_saved = storage.save_run_result(
        {
            "raw_idea": "location idea",
            "state": {
                "story_artifact": {
                    "title": "Sky Dock",
                    "description": "A floating dock.",
                    "locations": [{"name": "Sky Dock", "description": "A floating dock."}],
                }
            },
            "meta": {"source": "location"},
        },
        filename="location_filter",
        artifact_type="location",
    )

    world_listing = storage.list_run_previews(artifact_type="world")
    location_listing = storage.list_run_previews(artifact_type="location")

    assert [item["run_id"] for item in world_listing["items"]] == [world_saved["run_id"]]
    assert [item["run_id"] for item in location_listing["items"]] == [location_saved["run_id"]]


def test_drafts_are_separated_by_artifact_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    storage.save_draft_state(
        {"raw_idea": "world draft", "state": {"world_setting": "x"}, "meta": {}, "save_pending": True},
        artifact_type="world",
    )
    storage.save_draft_state(
        {"raw_idea": "story draft", "state": {"story_artifact": {"title": "T"}}, "meta": {}, "save_pending": True},
        artifact_type="story",
    )

    world_draft = storage.load_draft_state(artifact_type="world")
    story_draft = storage.load_draft_state(artifact_type="story")
    all_drafts = storage.load_latest_drafts()

    assert world_draft is not None
    assert world_draft["raw_idea"] == "world draft"
    assert story_draft is not None
    assert story_draft["raw_idea"] == "story draft"
    assert all_drafts["world"]["raw_idea"] == "world draft"
    assert all_drafts["story"]["raw_idea"] == "story draft"


def test_character_image_is_saved_inside_artifact_folder(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    source_image = tmp_path / "images" / "temp.png"
    source_image.parent.mkdir(parents=True, exist_ok=True)
    source_image.write_bytes(b"fake-png-bytes")

    saved = storage.save_run_result(
        {
            "raw_idea": "char image",
            "state": {
                "characters": [
                    {
                        "name": "Ari",
                        "details": "Pilot",
                        "image_path": str(source_image),
                    }
                ]
            },
            "meta": {"source": "character-page"},
        },
        filename="character_with_image",
    )

    run_path = Path(saved["run_path"])
    run_id = saved["run_id"]
    expected_image = run_path.parent / f"{run_id}.png"
    assert expected_image.exists()

    loaded = storage.load_run(run_id, artifact_type="character")
    assert loaded is not None
    image_file = loaded["state"]["characters"][0]["image_file"]
    assert image_file == f"{run_id}.png"


def test_load_latest_draft_falls_back_to_snapshot_if_latest_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    storage.save_draft_state(
        {"raw_idea": "recover me", "state": {"world_setting": "x"}, "meta": {}, "save_pending": True},
        artifact_type="world",
    )
    latest_path = storage.get_drafts_dir("world") / "latest.json"
    latest_path.unlink()

    recovered = storage.load_draft_state(artifact_type="world")
    assert recovered is not None
    assert recovered["raw_idea"] == "recover me"


def test_resave_prunes_stale_files_in_artifact_folder(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    saved = storage.save_run_result(
        {"raw_idea": "idea", "state": {"world_setting": "v1"}, "meta": {}},
        filename="cleanup_case",
    )
    run_dir = Path(saved["run_path"]).parent
    stale = run_dir / "stale.tmp"
    stale.write_text("old", encoding="utf-8")
    assert stale.exists()

    storage.save_run_result(
        {"raw_idea": "idea2", "state": {"world_setting": "v2"}, "meta": {}},
        filename="cleanup_case",
    )
    assert not stale.exists()


def test_loader_rejects_non_local_image_file_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    saved = storage.save_run_result(
        {
            "raw_idea": "idea",
            "state": {"characters": [{"id": "urn:lorebook:character:x", "name": "Ari", "details": "Pilot"}]},
            "meta": {"source": "character-page"},
        },
        filename="path_hardening",
    )
    run_path = Path(saved["run_path"])
    record = storage.load_run(saved["run_id"], artifact_type="character")
    assert record is not None
    record["state"]["characters"][0]["image_file"] = "..\\outside.png"
    run_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    resolved = storage.find_character_by_urn("urn:lorebook:character:x")
    assert resolved is not None
    assert resolved["character"]["image_data"] == ""


def test_story_location_image_is_saved_inside_artifact_folder(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "get_outputs_root", lambda: tmp_path)

    source_image = tmp_path / "images" / "dock.png"
    source_image.parent.mkdir(parents=True, exist_ok=True)
    source_image.write_bytes(b"fake-location-bytes")

    saved = storage.save_run_result(
        {
            "raw_idea": "location image",
            "state": {
                "story_artifact": {
                    "title": "Sky Dock",
                    "description": "A floating dock.",
                    "locations": [
                        {
                            "name": "Sky Dock",
                            "description": "A floating dock.",
                            "image_path": str(source_image),
                        }
                    ],
                }
            },
            "meta": {"source": "location"},
        },
        filename="location_with_image",
        artifact_type="location",
    )

    run_path = Path(saved["run_path"])
    record = storage.load_run(saved["run_id"], artifact_type="location")
    assert record is not None
    location = record["state"]["story_artifact"]["locations"][0]
    image_name = location["image_name"]
    assert image_name.startswith(saved["run_id"])
    assert (run_path.parent / image_name).exists()