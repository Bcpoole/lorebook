from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query


import requests

from lorebook.api.storage import save_draft_state
from lorebook.config.sd import resolve_sd_styles
from lorebook.imaging.service import _assert_sd_available, _make_sd_prompt, _render_sd_image
from lorebook.workflow.normalization import _normalize_state


router = APIRouter()


@router.post("/character-image")
async def generate_character_image(body: Dict[str, Any]) -> Dict[str, Any]:
    raw_idea: str = body.get("raw_idea", "")
    state = _normalize_state(raw_idea, body.get("state"))
    character_index = max(0, int(body.get("character_index", 0)))
    mode = str(body.get("mode", "full")).strip().lower()
    style_name = str(body.get("style", "")).strip().lower() or None
    sd_config = body.get("sd_config") if isinstance(body.get("sd_config"), dict) else {}

    if mode not in {"full", "prompt", "image"}:
        raise HTTPException(status_code=400, detail="mode must be one of: full, prompt, image")

    if character_index >= len(state.get("characters", [])):
        raise HTTPException(status_code=400, detail="character_index is out of range")

    character = state["characters"][character_index]
    prompt_override = body.get("prompt_override")

    if mode == "prompt":
        prompt = _make_sd_prompt(state, character, prompt_override=prompt_override)
        updated_character = {
            **character,
            "image_prompt": prompt,
        }
    else:
        _assert_sd_available(sd_config.get("endpoint") if isinstance(sd_config, dict) else None)
        if mode == "image":
            prompt = (prompt_override or "").strip() or str(
                character.get("image_prompt") or ""
            ).strip()
            if not prompt:
                raise HTTPException(
                    status_code=400,
                    detail="No existing image prompt found. Regenerate prompt first or provide prompt_override.",
                )
        else:
            prompt = _make_sd_prompt(state, character, prompt_override=prompt_override)

        try:
            image_path, image_data, styled_prompt, resolved_style = _render_sd_image(
                prompt,
                style_name=style_name,
                sd_config=sd_config,
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=502, detail="Failed to render image from Stable Diffusion endpoint"
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        updated_character = {
            **character,
            "image_prompt": prompt,
            "image_prompt_styled": styled_prompt,
            "image_style": resolved_style,
            "image_path": image_path,
            "image_data": image_data,
        }

    updated_characters = list(state["characters"])
    updated_characters[character_index] = updated_character
    state["characters"] = updated_characters

    save_draft_state(
        {
            "raw_idea": state.get("raw_idea", ""),
            "state": state,
            "meta": body.get("meta", {}),
            "save_pending": bool(body.get("save_pending", False)),
        },
        "latest",
        artifact_type="character",
    )

    return {
        "state": state,
        "character_index": character_index,
        "character": updated_character,
    }


@router.get("/sd-styles")
async def get_sd_styles(include_defaults: bool = Query(True)) -> Dict[str, Any]:
    resolved_styles, resolved_default = resolve_sd_styles(include_builtin_defaults=include_defaults)
    return {
        "default_style": resolved_default,
        "styles": list(resolved_styles.keys()),
        "style_data": {
            k: {"prompt": v.get("prompt", ""), "negative_prompt": v.get("negative_prompt", "")}
            for k, v in resolved_styles.items()
        },
    }
