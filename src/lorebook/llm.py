from __future__ import annotations

import os

import requests

DEFAULT_ENDPOINT = "http://localhost:5001/api/v1/generate"


def call_local_llm(system_prompt: str, user_prompt: str, endpoint: str | None = None) -> str:
    target_endpoint = endpoint or os.getenv("LOREBOOK_LLM_ENDPOINT", DEFAULT_ENDPOINT)

    response = requests.post(
        target_endpoint,
        json={
            "prompt": (
                f"<|im_start|>system\\n{system_prompt}<|im_end|>\\n"
                f"<|im_start|>user\\n{user_prompt}<|im_end|>\\n"
                "<|im_start|>assistant\\n"
            ),
            "max_context_length": 8192,
            "max_length": 1024,
            "temperature": 0.7,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["results"][0]["text"]
