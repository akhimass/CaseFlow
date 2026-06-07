"""TrueFoundry AI Gateway — single entry point for gateway-routed model calls."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from bedrock_llm import bedrock_chat_openai_compat, bedrock_configured, bedrock_model_id
from openai_llm import (
    openai_chat,
    openai_configured,
    openai_direct_configured,
    openai_model_id,
)
from pii_redaction import RedactionSession, Redactor, redact_messages
from privacy_context import get_redaction_session

logger = logging.getLogger("gateway")

ProviderName = Literal[
    "openai", "openai-direct", "truefoundry", "bedrock", "livekit-inference"
]

# Primary reasoning / document model — OpenAI gpt-4.1-mini (cost-efficient).
GATEWAY_MODEL = os.getenv("GATEWAY_MODEL", "gpt-4.1-mini")

MODEL_ALIASES: dict[str, str] = {
    "qwen-max": GATEWAY_MODEL,  # legacy alias → OpenAI
    "gpt-4.1-mini": openai_model_id(),
    "gpt-4.1": os.getenv("OPENAI_MODEL_LARGE", "gpt-4.1"),
    "bedrock-claude-3-5-sonnet": os.getenv(
        "BEDROCK_AUDIT_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"
    ),
    "livekit-inference": os.getenv(
        "LIVEKIT_INFERENCE_MODEL", "openai/gpt-4.1-mini"
    ),
}

CHAT_TIMEOUT_S = float(os.getenv("GATEWAY_CHAT_TIMEOUT_S", "8"))
TTS_TTFT_TIMEOUT_S = float(os.getenv("GATEWAY_TTS_TTFT_TIMEOUT_S", "2"))


@dataclass
class GatewayMetadata:
    case_id: str = ""
    turn: int = 0
    caller_id: str = ""

    def as_header(self) -> str:
        payload = {
            k: str(v)
            for k, v in {
                "case_id": self.case_id,
                "turn": self.turn,
                "caller_id": self.caller_id,
                "application": "caseflow",
            }.items()
            if v
        }
        return json.dumps(payload)


@dataclass
class GatewayResponse:
    content: str
    model_id: str
    provider: str
    latency_ms: int
    input_chars: int
    output_chars: int
    failover: bool = False
    failover_from: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


_audit_buffer: list[dict[str, Any]] = []


def gateway_configured() -> bool:
    return bool(os.getenv("TRUEFOUNDRY_GATEWAY_URL") and os.getenv("TRUEFOUNDRY_API_KEY"))


def llm_configured() -> bool:
    return openai_configured() or gateway_configured() or bedrock_configured()


def resolve_model(model_id: str) -> str:
    return MODEL_ALIASES.get(model_id, model_id)


def _gateway_base() -> str:
    return (os.getenv("TRUEFOUNDRY_GATEWAY_URL") or "").rstrip("/")


def _auth_headers(metadata: GatewayMetadata | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('TRUEFOUNDRY_API_KEY', '')}",
        "X-TFY-LOGGING-CONFIG": '{"enabled": true}',
    }
    if metadata:
        headers["X-TFY-METADATA"] = metadata.as_header()
    headers["x-tfy-request-timeout"] = str(int(CHAT_TIMEOUT_S * 1000))
    return headers


def _chat_paths(base: str) -> list[str]:
    return [f"{base}/openai/chat/completions", f"{base}/v1/chat/completions"]


def _provider_chain(*, allow_failover: bool) -> list[ProviderName]:
    chain: list[ProviderName] = []
    if openai_direct_configured():
        chain.append("openai-direct")
    elif openai_configured():
        chain.append("openai")
    if gateway_configured():
        chain.append("truefoundry")
    if bedrock_configured():
        chain.append("bedrock")
    if allow_failover:
        chain.append("livekit-inference")
    return chain


async def _post_chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    metadata: GatewayMetadata | None,
    timeout_s: float,
) -> dict[str, Any]:
    base = _gateway_base()
    if not base:
        raise RuntimeError("TRUEFOUNDRY_GATEWAY_URL is not configured")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = _auth_headers(metadata)
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for path in _chat_paths(base):
            try:
                response = await client.post(path, headers=headers, json=payload)
                if response.status_code >= 500:
                    raise RuntimeError(f"Gateway server error {response.status_code}")
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Gateway error {response.status_code}: {response.text[:300]}"
                    )
                data = response.json()
                data["_provider"] = "truefoundry"
                return data
            except Exception as exc:
                last_error = exc
                logger.warning("Gateway chat failed at %s: %s", path, exc)

    raise last_error or RuntimeError("Gateway chat failed")


async def _bedrock_chat(
    *,
    messages: list[dict[str, str]],
    temperature: float,
) -> dict[str, Any]:
    result = await bedrock_chat_openai_compat(
        messages,
        temperature=temperature,
        timeout_s=CHAT_TIMEOUT_S,
    )
    return {
        "choices": [{"message": {"content": result["content"]}}],
        "model": result["model"],
        "_provider": "bedrock",
        "usage": result.get("usage"),
    }


async def _livekit_inference_chat(
    *,
    messages: list[dict[str, str]],
    temperature: float,
) -> dict[str, Any]:
    """Last-resort failover when TrueFoundry and Bedrock are unavailable."""
    from livekit.agents import inference, llm

    model = resolve_model("livekit-inference")
    ctx = llm.ChatContext()
    for msg in messages:
        role = msg.get("role", "user")
        if role in {"system", "user", "assistant"}:
            ctx.add_message(role=role, content=msg.get("content", ""))

    content = ""
    async with inference.LLM(model=model) as llm_inst:
        stream = llm_inst.chat(chat_ctx=ctx, temperature=temperature)
        async for chunk in stream:
            if chunk.delta and chunk.delta.content:
                content += chunk.delta.content

    return {
        "choices": [{"message": {"content": content}}],
        "model": model,
        "_provider": "livekit-inference",
    }


async def _openai_provider_chat(
    *,
    resolved_model: str,
    messages: list[dict[str, str]],
    temperature: float,
    timeout_s: float,
) -> dict[str, Any]:
    return await openai_chat(
        messages,
        model=resolved_model,
        temperature=temperature,
        timeout_s=timeout_s,
    )


async def _invoke_provider(
    provider: ProviderName,
    *,
    model_id: str,
    resolved_model: str,
    messages: list[dict[str, str]],
    temperature: float,
    metadata: GatewayMetadata | None,
    timeout_s: float = CHAT_TIMEOUT_S,
) -> tuple[dict[str, Any], str]:
    if provider in {"openai", "openai-direct"}:
        data = await _openai_provider_chat(
            resolved_model=resolved_model,
            messages=messages,
            temperature=temperature,
            timeout_s=timeout_s,
        )
        return data, resolved_model

    if provider == "truefoundry":
        data = await _post_chat(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            metadata=metadata,
            timeout_s=CHAT_TIMEOUT_S,
        )
        return data, resolved_model

    if provider == "bedrock":
        data = await _bedrock_chat(messages=messages, temperature=temperature)
        return data, bedrock_model_id()

    data = await _livekit_inference_chat(messages=messages, temperature=temperature)
    return data, resolve_model("livekit-inference")


def _parse_chat_response(data: dict[str, Any], model_id: str) -> GatewayResponse:
    content = (
        data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    )
    usage = data.get("usage") or {}
    provider = data.get("_provider") or "unknown"
    return GatewayResponse(
        content=content,
        model_id=model_id,
        provider=provider,
        latency_ms=0,
        input_chars=0,
        output_chars=len(content),
        usage=usage,
    )


async def _record_audit(record: dict[str, Any]) -> None:
    _audit_buffer.append(record)
    if len(_audit_buffer) > 500:
        del _audit_buffer[: len(_audit_buffer) - 500]

    base = os.getenv("CASEFLOW_API_URL", "http://localhost:3000").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{base}/api/audit", json=record)
    except Exception:
        logger.debug("Audit POST skipped (API unavailable)")


async def chat(
    model_id: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    metadata: GatewayMetadata | None = None,
    allow_failover: bool = True,
    redaction_session: RedactionSession | None = None,
    language: str = "en",
    timeout_s: float | None = None,
    **kwargs: Any,
) -> GatewayResponse:
    """OpenAI primary → TrueFoundry → Bedrock → LiveKit Inference."""
    del kwargs
    session = redaction_session or get_redaction_session()
    redacted_messages = messages
    redactions_before = session.total_redactions if session else 0
    if session:
        redacted_messages = redact_messages(
            messages,
            session=session,
            language=language,
            model=model_id,
        )

    resolved = resolve_model(model_id)
    input_chars = sum(len(m.get("content", "")) for m in redacted_messages)
    started = time.perf_counter()

    effective_timeout = timeout_s if timeout_s is not None else CHAT_TIMEOUT_S
    providers = _provider_chain(allow_failover=allow_failover)
    if not providers:
        raise RuntimeError(
            "No LLM configured (OpenAI, TrueFoundry, Bedrock, or LiveKit Inference)"
        )

    last_error: Exception | None = None
    for index, provider in enumerate(providers):
        try:
            data, effective_model = await _invoke_provider(
                provider,
                model_id=model_id,
                resolved_model=resolved,
                messages=redacted_messages,
                temperature=temperature,
                metadata=metadata,
                timeout_s=effective_timeout,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            response = _parse_chat_response(data, effective_model)
            response.latency_ms = latency_ms
            response.input_chars = input_chars
            response.failover = index > 0
            response.failover_from = model_id if index > 0 else None

            if session and response.content:
                response.content = Redactor(session).unredact(response.content)

            if session and session.total_redactions > redactions_before:
                await _record_audit(
                    {
                        "audit_id": str(uuid.uuid4()),
                        "event_type": "pii_redaction",
                        "case_id": metadata.case_id if metadata else "",
                        "model_id": model_id,
                        "provider": response.provider,
                        "redaction_count": session.total_redactions - redactions_before,
                        "categories": dict(session.counts_by_category),
                        "timestamp": time.time(),
                    }
                )

            await _record_audit(
                {
                    "audit_id": str(uuid.uuid4()),
                    "event_type": "gateway_call",
                    "model_id": model_id,
                    "resolved_model": response.model_id,
                    "provider": response.provider,
                    "case_id": metadata.case_id if metadata else "",
                    "turn": metadata.turn if metadata else 0,
                    "caller_id": metadata.caller_id if metadata else "",
                    "input_chars": input_chars,
                    "output_chars": response.output_chars,
                    "latency_ms": latency_ms,
                    "failover": response.failover,
                    "failover_reason": str(last_error) if last_error else None,
                    "timestamp": time.time(),
                }
            )
            if response.failover:
                logger.warning(
                    "Gateway used failover provider=%s after primary failure: %s",
                    provider,
                    last_error,
                )
            return response
        except Exception as exc:
            last_error = exc
            logger.warning("Gateway provider %s failed: %s", provider, exc)

    raise last_error or RuntimeError("Gateway chat failed")


async def embed(model_id: str, texts: list[str], **kwargs: Any) -> dict[str, Any]:
    """Embedding call via TrueFoundry gateway."""
    del kwargs
    base = _gateway_base()
    if not base:
        raise RuntimeError("TRUEFOUNDRY_GATEWAY_URL is not configured")

    resolved = resolve_model(model_id)
    payload = {"model": resolved, "input": texts}
    headers = _auth_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for path in [f"{base}/openai/embeddings", f"{base}/v1/embeddings"]:
            try:
                response = await client.post(path, headers=headers, json=payload)
                if response.is_success:
                    return response.json()
            except Exception:
                continue
    raise RuntimeError("Gateway embeddings failed")


async def tts(
    model_id: str,
    text: str,
    voice_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """MiniMax TTS pass-through — logged to audit, not routed via TrueFoundry."""
    del model_id, voice_id, kwargs
    started = time.perf_counter()
    record = {
        "audit_id": str(uuid.uuid4()),
        "event_type": "tts_pass_through",
        "model_id": "minimax-speech-2.8-hd",
        "provider": "minimax",
        "input_chars": len(text),
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "timestamp": time.time(),
        "note": "MiniMax TTS via LiveKit plugin; audit only",
    }
    await _record_audit(record)
    return {"status": "logged", "text_len": len(text)}


def get_recent_audit(limit: int = 50) -> list[dict[str, Any]]:
    return list(_audit_buffer[-limit:])
