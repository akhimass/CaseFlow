from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger("bedrock")

BEDROCK_BEARER_ENV = "AWS_BEARER_TOKEN_BEDROCK"
DEFAULT_REGION = "us-east-1"
DEFAULT_MODEL = "us.amazon.nova-lite-v1:0"


def bedrock_api_key() -> str | None:
    return os.getenv(BEDROCK_BEARER_ENV) or os.getenv("AWS_BEDROCK_API_KEY")


def bedrock_iam_configured() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    )


def bedrock_configured() -> bool:
    return bool(bedrock_api_key() or bedrock_iam_configured())


def bedrock_region() -> str:
    return (
        os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or DEFAULT_REGION
    )


def bedrock_model_id() -> str:
    return os.getenv("BEDROCK_FALLBACK_MODEL", DEFAULT_MODEL)


def _converse_url(region: str, model_id: str) -> str:
    encoded = quote(model_id, safe="")
    return f"https://bedrock-runtime.{region}.amazonaws.com/model/{encoded}/converse"


def split_openai_messages(
    messages: list[dict[str, str]],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    bedrock_messages: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            if content:
                system_parts.append(content)
        elif role in {"user", "assistant"}:
            bedrock_messages.append(
                {"role": role, "content": [{"text": content}]}
            )

    system = "\n\n".join(system_parts) if system_parts else None
    return system, bedrock_messages


def _parse_converse_response(data: dict[str, Any], model_id: str) -> dict[str, Any]:
    blocks = data.get("output", {}).get("message", {}).get("content", [])
    text = next((block.get("text", "") for block in blocks if block.get("text")), "")
    if not text:
        raise RuntimeError("Bedrock returned empty content")

    return {
        "content": text,
        "model": model_id,
        "provider": "bedrock",
        "usage": data.get("usage"),
    }


def _bearer_converse_sync(
    *,
    messages: list[dict[str, Any]],
    system: str | None,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
) -> dict[str, Any]:
    api_key = bedrock_api_key()
    if not api_key:
        raise RuntimeError(f"{BEDROCK_BEARER_ENV} is not configured")

    region = bedrock_region()
    model_id = bedrock_model_id()
    payload: dict[str, Any] = {
        "messages": messages,
        "inferenceConfig": {
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
    }
    if system:
        payload["system"] = [{"text": system}]

    with httpx.Client(timeout=timeout_s) as client:
        response = client.post(
            _converse_url(region, model_id),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=payload,
        )

    if response.status_code >= 500:
        raise RuntimeError(f"Bedrock server error: {response.status_code}")
    if response.status_code >= 400:
        raise RuntimeError(
            f"Bedrock request failed ({response.status_code}): {response.text[:500]}"
        )

    return _parse_converse_response(response.json(), model_id)


def _iam_converse_sync(
    *,
    messages: list[dict[str, Any]],
    system: str | None,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    import boto3

    region = bedrock_region()
    model_id = bedrock_model_id()
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    kwargs: dict[str, Any] = {
        "modelId": model_id,
        "messages": messages,
        "inferenceConfig": {
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
    }
    if system:
        kwargs["system"] = [{"text": system}]

    response = client.converse(**kwargs)
    return _parse_converse_response(response, model_id)


async def bedrock_converse(
    messages: list[dict[str, Any]],
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Call Bedrock Converse via bearer token or IAM access keys."""
    if not bedrock_configured():
        raise RuntimeError("Bedrock is not configured")

    if bedrock_api_key():
        return await asyncio.to_thread(
            _bearer_converse_sync,
            messages=messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

    return await asyncio.to_thread(
        _iam_converse_sync,
        messages=messages,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def bedrock_chat_openai_compat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """OpenAI-style chat messages → Bedrock Converse."""
    system, bedrock_messages = split_openai_messages(messages)
    if not bedrock_messages:
        raise RuntimeError("Bedrock chat requires at least one user/assistant message")

    return await bedrock_converse(
        bedrock_messages,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
    )


async def bedrock_reason(prompt: str, context: str = "") -> dict[str, Any]:
    user_content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
    return await bedrock_converse(
        messages=[{"role": "user", "content": [{"text": user_content}]}],
        system="You are a PI intake reasoning assistant. Reply concisely.",
        temperature=0.2,
    )


def parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None
