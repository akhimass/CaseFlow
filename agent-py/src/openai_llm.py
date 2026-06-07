"""Direct OpenAI chat completions — primary gateway provider."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("openai_llm")

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def openai_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def openai_model_id() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


async def openai_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout_s: float = 60.0,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    effective_model = model or openai_model_id()
    payload: dict[str, Any] = {
        "model": effective_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(
            f"{OPENAI_BASE}/chat/completions",
            headers=headers,
            json=payload,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI error {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        data["_provider"] = "openai"
        return data
