from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..storage import get_outputs_root

router = APIRouter(prefix="/experimentation", tags=["experimentation"])


DEFAULT_EXPERIMENTATION_CONFIG = {
    "general": {
        "outputFormat": "markdown",
        "multilineReplies": True,
    },
    "experimentation": {
        "temperature": 0.7,
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


def get_experimentation_config_path():
    """Get the path to the experimentation config file."""
    base_dir = get_outputs_root()
    return base_dir / "experimentation.json"


@router.post("/save")
async def save_experimentation_config(config: dict) -> dict:
    """Save the experimentation configuration to a local file."""
    try:
        import json

        config_path = get_experimentation_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        return {"status": "success", "path": str(config_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@router.get("/load")
async def load_experimentation_config() -> dict:
    """Load the experimentation configuration from the local file."""
    try:
        import json

        config_path = get_experimentation_config_path()

        if not config_path.exists():
            return DEFAULT_EXPERIMENTATION_CONFIG

        with open(config_path, "r") as f:
            saved = json.load(f)

        # Backward compatibility for older flat experimentation schema.
        if isinstance(saved, dict) and "experimentation" not in saved and (
            "temperature" in saved or "topP" in saved
        ):
            return {
                "general": {
                    "outputFormat": saved.get("outputFormat", DEFAULT_EXPERIMENTATION_CONFIG["general"]["outputFormat"]),
                    "multilineReplies": saved.get(
                        "multilineReplies", DEFAULT_EXPERIMENTATION_CONFIG["general"]["multilineReplies"]
                    ),
                },
                "experimentation": {
                    "temperature": saved.get("temperature", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["temperature"]),
                    "topP": saved.get("topP", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["topP"]),
                    "topK": saved.get("topK", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["topK"]),
                    "repetitionPenalty": saved.get(
                        "repetitionPenalty", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["repetitionPenalty"]
                    ),
                    "maxLength": saved.get("maxLength", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["maxLength"]),
                    "contextSize": saved.get(
                        "contextSize", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["contextSize"]
                    ),
                    "minP": saved.get("minP", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["minP"]),
                    "presencePenalty": saved.get(
                        "presencePenalty", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["presencePenalty"]
                    ),
                    "samplerSeed": saved.get("samplerSeed", DEFAULT_EXPERIMENTATION_CONFIG["experimentation"]["samplerSeed"]),
                },
                "sd": {
                    **DEFAULT_EXPERIMENTATION_CONFIG["sd"],
                    **saved.get("sd", {}),
                },
            }

        return {
            "general": {
                **DEFAULT_EXPERIMENTATION_CONFIG["general"],
                **(saved.get("general", {}) if isinstance(saved, dict) else {}),
            },
            "experimentation": {
                **DEFAULT_EXPERIMENTATION_CONFIG["experimentation"],
                **(saved.get("experimentation", {}) if isinstance(saved, dict) else {}),
            },
            "sd": {
                **DEFAULT_EXPERIMENTATION_CONFIG["sd"],
                **(saved.get("sd", {}) if isinstance(saved, dict) else {}),
            },
        }
    except Exception:
        # Return defaults on error
        return DEFAULT_EXPERIMENTATION_CONFIG
