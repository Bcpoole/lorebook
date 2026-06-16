"""Stable Diffusion style templates.

Copy this file to ``styles.py`` and customize locally.
"""
from __future__ import annotations

from typing import Final


SD_STYLES: Final[dict[str, dict[str, str]]] = {
    "balanced": {
        "prompt": "{prompt}, detailed environment, coherent composition, cinematic color grading, sharp focus, high detail",
        "negative_prompt": "{negative_prompt}, low quality, blurry, bad anatomy, extra limbs, deformed hands, text, watermark, logo, jpeg artifacts",
    },
    "illustrative": {
        "prompt": "{prompt}, stylized illustration, concept art, painterly texture, dramatic lighting, artstation quality, high detail",
        "negative_prompt": "{negative_prompt}, photorealistic skin pores, noisy background, low detail, bad anatomy, malformed hands, text, watermark",
    },
    "photo": {
        "prompt": "{prompt}, photorealistic, realistic skin texture, 85mm lens, depth of field, cinematic lighting, ultra detailed",
        "negative_prompt": "{negative_prompt}, cartoon, anime, cgi look, overprocessed, low quality, bad anatomy, extra fingers, text, watermark",
    },
}

DEFAULT_SD_STYLE: Final[str] = "balanced"
