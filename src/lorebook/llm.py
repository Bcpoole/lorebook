from __future__ import annotations

import os
import time

import requests

DEFAULT_ENDPOINT = "http://localhost:5001/api/v1/generate"


def call_local_llm(
    system_prompt: str,
    user_prompt: str,
    endpoint: str | None = None,
    max_context_length: int = 8192,
    max_length: int = 1024,
    temperature: float = 0.7,
    max_retries: int = 2,
) -> str:
    target_endpoint = endpoint or os.getenv("LOREBOOK_LLM_ENDPOINT", DEFAULT_ENDPOINT)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                target_endpoint,
                json={
                    "prompt": (
                        f"<|im_start|>system\\n{system_prompt}<|im_end|>\\n"
                        f"<|im_start|>user\\n{user_prompt}<|im_end|>\\n"
                        "<|im_start|>assistant\\n"
                    ),
                    "max_context_length": max_context_length,
                    "max_length": max_length,
                    "temperature": temperature,
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            return payload["results"][0]["text"]
        except requests.exceptions.RequestException as error:
            last_error = error
            if attempt >= max_retries:
                break
            # Brief backoff helps with transient local server disconnects.
            time.sleep(1 + attempt)

    raise RuntimeError("Failed to get response from local LLM endpoint") from last_error
