from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from urllib.parse import urlparse

import requests

DEFAULT_ENDPOINT = "http://localhost:5001"


def _candidate_endpoints(target_endpoint: str) -> list[str]:
    cleaned_endpoint = target_endpoint.rstrip("/")
    parsed = urlparse(cleaned_endpoint)

    # If the caller provided a concrete route, respect it exactly.
    if parsed.path not in ("", "/"):
        return [cleaned_endpoint]

    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else cleaned_endpoint
    return [
        f"{base_url}/api/v1/generate",
        f"{base_url}/v1/completions",
    ]


def _candidate_stream_endpoints(target_endpoint: str) -> list[str]:
    cleaned_endpoint = target_endpoint.rstrip("/")
    parsed = urlparse(cleaned_endpoint)

    if parsed.path not in ("", "/"):
        return [cleaned_endpoint]

    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else cleaned_endpoint
    return [
        f"{base_url}/v1/chat/completions",
        f"{base_url}/v1/completions",
    ]


def _extract_text(payload: dict) -> str:
    if "results" in payload and payload["results"]:
        return payload["results"][0]["text"]

    if "choices" in payload and payload["choices"]:
        choice = payload["choices"][0]
        if "text" in choice:
            return choice["text"]
        if "message" in choice and choice["message"]:
            return choice["message"].get("content", "")

    raise RuntimeError("Unsupported response shape from local LLM endpoint")


def _extract_stream_chunk(line: str) -> str:
    line = line.strip()
    if not line.startswith("data:"):
        return ""

    payload_text = line.removeprefix("data:").strip()
    if not payload_text or payload_text == "[DONE]":
        return ""

    payload = json.loads(payload_text)
    choices = payload.get("choices") or []
    if not choices:
        return ""

    choice = choices[0]
    delta = choice.get("delta") or {}
    if isinstance(delta, dict) and delta.get("content"):
        return delta["content"]
    if choice.get("text"):
        return choice["text"]
    if isinstance(delta, dict) and delta.get("text"):
        return delta["text"]
    return ""


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
    prompt = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

    last_error: Exception | None = None
    for candidate_endpoint in _candidate_endpoints(target_endpoint):
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    candidate_endpoint,
                    json={
                        "prompt": prompt,
                        "max_context_length": max_context_length,
                        "max_length": max_length,
                        "temperature": temperature,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                payload = response.json()
                return _extract_text(payload)
            except requests.exceptions.RequestException as error:
                last_error = error
                if attempt >= max_retries:
                    break
                # Brief backoff helps with transient local server disconnects.
                time.sleep(1 + attempt)

    raise RuntimeError("Failed to get response from local LLM endpoint") from last_error


def stream_local_llm(
    system_prompt: str,
    user_prompt: str,
    endpoint: str | None = None,
    max_context_length: int = 8192,
    max_length: int = 2048,
    temperature: float = 0.7,
    max_retries: int = 2,
) -> Iterator[str]:
    target_endpoint = endpoint or os.getenv("LOREBOOK_LLM_ENDPOINT", DEFAULT_ENDPOINT)
    prompt = (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

    last_error: Exception | None = None
    for candidate_endpoint in _candidate_stream_endpoints(target_endpoint):
        for attempt in range(max_retries + 1):
            try:
                with requests.post(
                    candidate_endpoint,
                    json={
                        "model": "koboldcpp",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "prompt": prompt,
                        "max_context_length": max_context_length,
                        "max_length": max_length,
                        "max_tokens": max_length,
                        "temperature": temperature,
                        "stream": True,
                    },
                    stream=True,
                    timeout=60,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        try:
                            chunk = _extract_stream_chunk(line)
                        except json.JSONDecodeError:
                            continue
                        if chunk:
                            yield chunk
                    return
            except requests.exceptions.RequestException as error:
                last_error = error
                if attempt >= max_retries:
                    break
                time.sleep(1 + attempt)

    raise RuntimeError("Failed to stream response from local LLM endpoint") from last_error


def is_local_llm_available(endpoint: str | None = None, timeout_seconds: float = 3.0) -> bool:
    """Return True when the configured local LLM endpoint is reachable."""
    target_endpoint = endpoint or os.getenv("LOREBOOK_LLM_ENDPOINT", DEFAULT_ENDPOINT)
    cleaned_endpoint = target_endpoint.rstrip("/")
    parsed = urlparse(cleaned_endpoint)

    if parsed.path not in ("", "/"):
        health_candidates = [cleaned_endpoint]
    else:
        base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else cleaned_endpoint
        health_candidates = [
            f"{base_url}/health",
            f"{base_url}/api/v1/model",
            f"{base_url}/v1/models",
            base_url,
        ]

    for candidate_endpoint in health_candidates:
        try:
            response = requests.get(candidate_endpoint, timeout=timeout_seconds)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            continue

    return False
