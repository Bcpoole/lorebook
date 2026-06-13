"""Tests for experimentation configuration persistence."""

import tempfile
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from lorebook.api.app import create_app


@pytest.fixture
def app_with_temp_storage():
    """Create an app with temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with mock.patch("lorebook.api.storage.get_outputs_root", return_value=Path(tmpdir)):
            app = create_app()
            yield app


@pytest.fixture
def client(app_with_temp_storage):
    """Create a test client."""
    return TestClient(app_with_temp_storage)


def test_load_experimentation_returns_defaults_when_not_saved(client):
    """Test that load returns default values when no config exists."""
    response = client.get("/api/experimentation/load")
    assert response.status_code == 200
    data = response.json()

    assert data["general"]["outputFormat"] == "markdown"
    assert data["general"]["multilineReplies"] is True
    assert data["experimentation"]["temperature"] == 0.7
    assert data["experimentation"]["topP"] == 0.9
    assert data["experimentation"]["topK"] == 40
    assert data["experimentation"]["repetitionPenalty"] == 1.1
    assert data["experimentation"]["maxLength"] == 512
    assert data["experimentation"]["contextSize"] == 2048
    assert data["experimentation"]["minP"] == 0
    assert data["experimentation"]["presencePenalty"] == 0
    assert data["experimentation"]["samplerSeed"] == -1
    assert data["sd"]["style"] == "balanced"
    assert data["sd"]["endpoint"] == "http://127.0.0.1:7860"


def test_save_experimentation_config(client):
    """Test that save persists configuration to file."""
    config = {
        "general": {
            "outputFormat": "json",
            "multilineReplies": False,
        },
        "experimentation": {
            "temperature": 0.9,
            "topP": 0.8,
            "topK": 50,
            "repetitionPenalty": 1.2,
            "maxLength": 1024,
            "contextSize": 4096,
            "minP": 0.05,
            "presencePenalty": 0.2,
            "samplerSeed": 42,
        },
        "sd": {
            "style": "illustrative",
            "endpoint": "http://127.0.0.1:7860",
            "steps": 32,
            "width": 768,
            "height": 768,
            "cfgScale": 4,
            "samplerName": "DPM++ 2M",
            "negativePromptExtra": "blurry, lowres",
        },
    }
    
    response = client.post("/api/experimentation/save", json=config)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_save_and_load_round_trip(client):
    """Test that saved config can be loaded back."""
    config = {
        "general": {
            "outputFormat": "plain",
            "multilineReplies": True,
        },
        "experimentation": {
            "temperature": 0.85,
            "topP": 0.85,
            "topK": 60,
            "repetitionPenalty": 1.15,
            "maxLength": 768,
            "contextSize": 3072,
            "minP": 0.02,
            "presencePenalty": -0.5,
            "samplerSeed": 999,
        },
        "sd": {
            "style": "photo",
            "endpoint": "http://127.0.0.1:7860",
            "steps": 28,
            "width": 832,
            "height": 832,
            "cfgScale": 4.5,
            "samplerName": "Euler a",
            "negativePromptExtra": "watermark",
        },
    }
    
    # Save the config
    save_response = client.post("/api/experimentation/save", json=config)
    assert save_response.status_code == 200
    
    # Load it back
    load_response = client.get("/api/experimentation/load")
    assert load_response.status_code == 200
    
    loaded_config = load_response.json()
    assert loaded_config == config


def test_save_multiple_times_overwrites(client):
    """Test that saving multiple times overwrites previous config."""
    config1 = {
        "general": {
            "outputFormat": "markdown",
            "multilineReplies": True,
        },
        "experimentation": {
            "temperature": 0.5,
            "topP": 0.9,
            "topK": 40,
            "repetitionPenalty": 1.1,
            "maxLength": 512,
            "contextSize": 2048,
            "minP": 0,
            "presencePenalty": 0,
            "samplerSeed": -1,
        },
        "sd": {
            "style": "balanced",
            "endpoint": "http://127.0.0.1:7860",
            "steps": 30,
            "width": 768,
            "height": 768,
            "cfgScale": 3,
            "samplerName": "DPM++ 2M",
            "negativePromptExtra": "",
        },
    }
    
    config2 = {
        "general": {
            "outputFormat": "json",
            "multilineReplies": False,
        },
        "experimentation": {
            "temperature": 1.5,
            "topP": 0.7,
            "topK": 80,
            "repetitionPenalty": 1.5,
            "maxLength": 2048,
            "contextSize": 8192,
            "minP": 0.1,
            "presencePenalty": 0.5,
            "samplerSeed": 123,
        },
        "sd": {
            "style": "illustrative",
            "endpoint": "http://127.0.0.1:7860",
            "steps": 42,
            "width": 1024,
            "height": 1024,
            "cfgScale": 6,
            "samplerName": "Euler a",
            "negativePromptExtra": "jpeg artifacts",
        },
    }
    
    # Save first config
    client.post("/api/experimentation/save", json=config1)
    
    # Save second config
    client.post("/api/experimentation/save", json=config2)
    
    # Load and verify we get the second config
    load_response = client.get("/api/experimentation/load")
    assert load_response.json() == config2


def test_load_legacy_flat_config_is_normalized(client):
    """Legacy flat configs are still accepted and normalized on load."""
    legacy_config = {
        "temperature": 0.95,
        "topP": 0.75,
        "topK": 55,
        "repetitionPenalty": 1.3,
        "maxLength": 900,
        "contextSize": 4096,
        "outputFormat": "json",
        "multilineReplies": False,
        "minP": 0.03,
        "presencePenalty": -0.2,
        "samplerSeed": 777,
    }

    save_response = client.post("/api/experimentation/save", json=legacy_config)
    assert save_response.status_code == 200

    load_response = client.get("/api/experimentation/load")
    assert load_response.status_code == 200
    loaded = load_response.json()

    assert loaded["general"]["outputFormat"] == "json"
    assert loaded["general"]["multilineReplies"] is False
    assert loaded["experimentation"]["temperature"] == 0.95
    assert loaded["experimentation"]["topP"] == 0.75
    assert loaded["experimentation"]["samplerSeed"] == 777
    assert loaded["sd"]["style"] == "balanced"
