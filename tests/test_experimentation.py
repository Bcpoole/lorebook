"""Tests for experimentation configuration persistence."""

import json
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
        with mock.patch('lorebook.api.storage.get_outputs_root', return_value=Path(tmpdir)):
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
    
    assert data["temperature"] == 0.7
    assert data["topP"] == 0.9
    assert data["topK"] == 40
    assert data["repetitionPenalty"] == 1.1
    assert data["maxLength"] == 512
    assert data["contextSize"] == 2048
    assert data["outputFormat"] == "markdown"
    assert data["multilineReplies"] is True
    assert data["minP"] == 0
    assert data["presencePenalty"] == 0
    assert data["samplerSeed"] == -1


def test_save_experimentation_config(client):
    """Test that save persists configuration to file."""
    config = {
        "temperature": 0.9,
        "topP": 0.8,
        "topK": 50,
        "repetitionPenalty": 1.2,
        "maxLength": 1024,
        "contextSize": 4096,
        "outputFormat": "json",
        "multilineReplies": False,
        "minP": 0.05,
        "presencePenalty": 0.2,
        "samplerSeed": 42,
    }
    
    response = client.post("/api/experimentation/save", json=config)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_save_and_load_round_trip(client):
    """Test that saved config can be loaded back."""
    config = {
        "temperature": 0.85,
        "topP": 0.85,
        "topK": 60,
        "repetitionPenalty": 1.15,
        "maxLength": 768,
        "contextSize": 3072,
        "outputFormat": "plain",
        "multilineReplies": True,
        "minP": 0.02,
        "presencePenalty": -0.5,
        "samplerSeed": 999,
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
        "temperature": 0.5,
        "topP": 0.9,
        "topK": 40,
        "repetitionPenalty": 1.1,
        "maxLength": 512,
        "contextSize": 2048,
        "outputFormat": "markdown",
        "multilineReplies": True,
        "minP": 0,
        "presencePenalty": 0,
        "samplerSeed": -1,
    }
    
    config2 = {
        "temperature": 1.5,
        "topP": 0.7,
        "topK": 80,
        "repetitionPenalty": 1.5,
        "maxLength": 2048,
        "contextSize": 8192,
        "outputFormat": "json",
        "multilineReplies": False,
        "minP": 0.1,
        "presencePenalty": 0.5,
        "samplerSeed": 123,
    }
    
    # Save first config
    client.post("/api/experimentation/save", json=config1)
    
    # Save second config
    client.post("/api/experimentation/save", json=config2)
    
    # Load and verify we get the second config
    load_response = client.get("/api/experimentation/load")
    assert load_response.json() == config2
