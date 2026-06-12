from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..storage import get_outputs_root

router = APIRouter(prefix="/experimentation", tags=["experimentation"])


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
            return {
                "temperature": 0.7,
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

        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        # Return defaults on error
        return {
            "temperature": 0.7,
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
