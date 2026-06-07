"""Direct OpenAI chat completions — primary gateway provider."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("openai_llm")

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_DIRECT_BASE = "https://api.openai.com/v1"


def _direct_api_key() -> str:
    key = os.getenv("OPENAI_DIRECT_API_KEY", "").strip()
    return key if key.startswith("sk-") else ""


def _resolve_api_key() -> str:
    direct = _direct_api_key()
    if direct:
        return direct
    return os.getenv("OPENAI_API_KEY", "").strip()


def openai_direct_configured() -> bool:
    return bool(_direct_api_key())


def openai_configured() -> bool:
    return bool(_resolve_api_key())


def openai_model_id() -> str:
    if openai_direct_configured():
        return os.getenv("OPENAI_DIRECT_MODEL", "gpt-4.1-mini")
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def openai_base_url() -> str:
    if openai_direct_configured():
        return OPENAI_DIRECT_BASE
    return OPENAI_BASE


async def openai_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    timeout_s: float = 60.0,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    api_key = _resolve_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or OPENAI_DIRECT_API_KEY is not configured")

    effective_model = model or openai_model_id()
    base_url = openai_base_url()
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
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenAI error {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        data["_provider"] = "openai-direct" if openai_direct_configured() else "openai"
        return data
