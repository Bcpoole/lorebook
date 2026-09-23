from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from lorebook.config.prompts import get_persona_prompts
from lorebook.config.sd import DEFAULT_SD_STYLE, SD_STYLES
from lorebook.errors import GenerationUnavailableError
from lorebook.llm import call_local_llm
from lorebook.workflow.state import CharacterState, WizardState


def _outputs_images_dir() -> Path:
    directory = Path(__file__).resolve().parents[4] / "outputs" / "images"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _make_sd_prompt(
    state: WizardState,
    character: CharacterState,
    prompt_override: str | None = None,
    persona_id: str = "blank",
) -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()

    prompt_input = (
        f"World setting:\n{state.get('world_setting', '')}\n\n"
        f"Character name: {character.get('name', 'Companion')}\n"
        f"Character details:\n{character.get('details', '')}"
    )
    generated = call_local_llm(
        get_persona_prompts(persona_id).SD_PROMPT_SYSTEM, prompt_input, max_length=256
    )
    return generated.strip().replace("\n", " ")


def _style_sd_prompts(
    prompt: str,
    style_name: str | None = None,
    negative_user: str | None = None,
) -> tuple[str, str, str]:
    style_key = (style_name or "").strip().lower() or DEFAULT_SD_STYLE
    style = SD_STYLES.get(style_key, SD_STYLES[DEFAULT_SD_STYLE])

    prompt_template = str(style.get("prompt", "{prompt}"))
    negative_template = str(style.get("negative_prompt", ""))

    if "{prompt}" not in prompt_template:
        prompt_template = f"{prompt_template}, {{prompt}}"

    styled_prompt = prompt_template.format(prompt=prompt)

    negative_substituted = str(negative_user or "").strip()
    if "{negative_prompt}" in negative_template:
        styled_negative = negative_template.format(negative_prompt=negative_substituted)
        # strip leading comma/space if the user value was empty
        styled_negative = re.sub(r"^[,\s]+", "", styled_negative)
    else:
        # no token in template — append user value when present
        styled_negative = negative_template
        if negative_substituted:
            styled_negative = (
                f"{styled_negative}, {negative_substituted}"
                if styled_negative
                else negative_substituted
            )

    return styled_prompt, styled_negative, style_key


def _render_sd_image(
    prompt: str, style_name: str | None = None, sd_config: dict[str, Any] | None = None
) -> tuple[str, str, str, str]:
    config = sd_config or {}
    styled_prompt, styled_negative, resolved_style = _style_sd_prompts(
        prompt,
        style_name=style_name,
        negative_user=str(config.get("negativePrompt", "")),
    )
    endpoint = str(
        config.get("endpoint") or os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860")
    ).rstrip("/")
    steps = int(config.get("steps", 30))
    width = int(config.get("width", 768))
    height = int(config.get("height", 768))
    cfg_scale = float(config.get("cfgScale", 3))
    sampler_name = str(config.get("samplerName", "DPM++ 2M"))

    response = requests.post(
        f"{endpoint}/sdapi/v1/txt2img",
        json={
            "prompt": styled_prompt,
            "negative_prompt": styled_negative,
            "steps": steps,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
        },
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    images = payload.get("images") or []
    if not images:
        raise RuntimeError("Stable Diffusion response did not include image data")

    encoded = images[0]
    if "," in encoded:
        encoded = encoded.split(",", maxsplit=1)[1]
    image_bytes = base64.b64decode(encoded)

    image_name = f"{uuid4().hex}.png"
    image_path = _outputs_images_dir() / image_name
    image_path.write_bytes(image_bytes)

    return str(image_path), f"data:image/png;base64,{encoded}", styled_prompt, resolved_style


def _assert_sd_available(endpoint_override: str | None = None) -> None:
    endpoint = str(
        endpoint_override or os.getenv("LOREBOOK_SD_ENDPOINT", "http://127.0.0.1:7860")
    ).rstrip("/")
    try:
        response = requests.get(f"{endpoint}/sdapi/v1/progress", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GenerationUnavailableError(
            "Stable Diffusion AUTOMATIC1111 API is unavailable. "
            "Start it before generating an image."
        ) from exc
