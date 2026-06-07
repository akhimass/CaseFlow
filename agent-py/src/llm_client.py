from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any

import httpx
import openai
from livekit.agents import inference, llm
from livekit.agents.llm.chat_context import FunctionCall, FunctionCallOutput
from livekit.agents.llm.fallback_adapter import FallbackAdapter, FallbackLLMStream
from livekit.agents.llm.llm import LLMStream
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)

from bedrock_llm import (
    bedrock_chat_openai_compat,
    bedrock_configured,
    bedrock_model_id,
)

logger = logging.getLogger("agent.llm_client")

DEFAULT_TIMEOUT_SECONDS = 8.0


def openai_direct_configured() -> bool:
    return os.getenv("OPENAI_DIRECT_API_KEY", "").strip().startswith("sk-")


def minimax_llm_configured() -> bool:
    return bool(os.getenv("MINIMAX_API_KEY", "").strip())


def livekit_inference_configured() -> bool:
    key = _get_env("LIVEKIT_INFERENCE_API_KEY", "LIVEKIT_API_KEY")
    secret = _get_env("LIVEKIT_INFERENCE_API_SECRET", "LIVEKIT_API_SECRET")
    return bool(key and secret)


def _livekit_inference_llm() -> llm.LLM | None:
    if not livekit_inference_configured():
        return None
    return inference.LLM(
        model=_get_env("LIVEKIT_INFERENCE_MODEL", default="openai/gpt-4.1-mini")
    )


def _tfy_guardrails_header() -> str | None:
    """``X-TFY-GUARDRAILS`` payload for TF-routed dialogue clients, from env.

    Note: TrueFoundry output guardrails do not run on streamed responses, but
    *input* guardrails always run — so dialogue prompts still get gateway-side
    PII screening on top of our app-level RedactingLLM.
    """
    inp = [
        g.strip() for g in os.getenv("TFY_INPUT_GUARDRAILS", "").split(",") if g.strip()
    ]
    out = [
        g.strip()
        for g in os.getenv("TFY_OUTPUT_GUARDRAILS", "").split(",")
        if g.strip()
    ]
    if not inp and not out:
        return None
    return json.dumps(
        {
            "llm_input_guardrails": inp,
            "llm_output_guardrails": out,
            "mcp_tool_pre_invoke_guardrails": [],
            "mcp_tool_post_invoke_guardrails": [],
        }
    )


def _tfy_virtual_dialogue_llm(
    *, case_id: str | None, temperature: float, max_tokens: int
) -> llm.LLM | None:
    """TrueFoundry virtual-model dialogue LLM (the front door for conversation).

    When ``TFY_DIALOGUE_VIRTUAL_MODEL`` is set (e.g. ``caseflow/dialogue``) and
    the gateway is configured, conversation is routed through one TF virtual model
    that owns load balancing + failover across MiniMax/OpenAI/Bedrock. The Python
    chain below stays as a deeper safety net. Unset → no behaviour change.
    """
    vm = os.getenv("TFY_DIALOGUE_VIRTUAL_MODEL", "").strip()
    gateway_ready = bool(
        _get_env("TRUEFOUNDRY_GATEWAY_URL") and _get_env("TRUEFOUNDRY_API_KEY")
    )
    if not vm or not gateway_ready:
        return None
    return OpenAIChatLLM(
        api_key=_get_env("TRUEFOUNDRY_API_KEY"),
        model=vm,
        provider="truefoundry",
        default_temperature=temperature,
        case_id=case_id,
        max_tokens=max_tokens,
        label="truefoundry-virtual-dialogue",
        base_url=_get_env(
            "OPENAI_BASE_URL",
            "TRUEFOUNDRY_GATEWAY_URL",
            default="https://gateway.truefoundry.ai",
        ),
    )


def _minimax_llm(
    *, case_id: str | None, temperature: float, max_tokens: int
) -> llm.LLM | None:
    """MiniMax LLM via its OpenAI-compatible endpoint (same key as MiniMax TTS).

    Defaults to MiniMax-Text-01 — it supports tool calling and, unlike the M-series
    reasoning models, does not emit ``<think>`` tokens that would be spoken by TTS.
    """
    key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not key:
        return None
    return OpenAIChatLLM(
        api_key=key,
        model=os.getenv("MINIMAX_LLM_MODEL", "MiniMax-Text-01"),
        provider="minimax",
        default_temperature=temperature,
        case_id=case_id,
        max_tokens=max_tokens,
        label="minimax",
        base_url=os.getenv("MINIMAX_LLM_BASE_URL", "https://api.minimax.io/v1"),
    )


async def _record_dialogue_provider(
    active_llm: llm.LLM,
    *,
    case_id: str | None,
    turn_index: int | None = None,
) -> None:
    provider = getattr(active_llm, "provider", "unknown")
    model = getattr(active_llm, "model", "unknown")
    record = {
        "audit_id": str(uuid.uuid4()),
        "event_type": "dialogue_llm_turn",
        "provider": provider,
        "model_id": model,
        "resolved_model": model,
        "case_id": case_id or "",
        "turn": turn_index or 0,
        "timestamp": time.time(),
        "note": f"Active dialogue LLM: {provider} {model}",
    }
    logger.info(
        "DIALOGUE_LLM provider=%s model=%s case_id=%s turn=%s",
        provider,
        model,
        case_id,
        turn_index,
    )
    base = os.getenv("CASEFLOW_API_URL", "http://localhost:3000").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{base}/api/audit", json=record)
    except Exception:
        logger.debug("Dialogue provider audit POST skipped (API unavailable)")


class _AuditedFallbackLLMStream(FallbackLLMStream):
    def __init__(
        self,
        adapter: FallbackAdapter,
        *,
        case_id: str | None,
        turn_index: int | None,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options: APIConnectOptions,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> None:
        super().__init__(
            adapter,
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        )
        self._case_id = case_id
        self._turn_index = turn_index
        self._provider_logged = False

    async def _try_generate(self, *, llm: llm.LLM, check_recovery: bool = False):
        async for chunk in super()._try_generate(
            llm=llm, check_recovery=check_recovery
        ):
            if not check_recovery and not self._provider_logged:
                self._provider_logged = True
                asyncio.create_task(
                    _record_dialogue_provider(
                        llm,
                        case_id=self._case_id,
                        turn_index=self._turn_index,
                    )
                )
            yield chunk


class CaseflowFallbackAdapter(FallbackAdapter):
    def __init__(
        self,
        llm_chain: list[llm.LLM],
        *,
        case_id: str | None = None,
        attempt_timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retry_per_llm: int = 0,
        retry_interval: float = 0.2,
        retry_on_chunk_sent: bool = True,
    ) -> None:
        super().__init__(
            llm_chain,
            attempt_timeout=attempt_timeout,
            max_retry_per_llm=max_retry_per_llm,
            retry_interval=retry_interval,
            retry_on_chunk_sent=retry_on_chunk_sent,
        )
        self._case_id = case_id

    def _turn_index(self, chat_ctx: llm.ChatContext) -> int | None:
        user_messages = 0
        for item in getattr(chat_ctx, "items", []) or []:
            if getattr(item, "role", None) == "user":
                user_messages += 1
        return user_messages or None

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> LLMStream:
        return _AuditedFallbackLLMStream(
            self,
            case_id=self._case_id,
            turn_index=self._turn_index(chat_ctx),
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        )


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value
    return default


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name, "")
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _build_metadata(case_id: str | None, turn_index: int | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if case_id:
        metadata["case_id"] = case_id
    if turn_index is not None:
        metadata["turn_index"] = turn_index
    return metadata


def _is_retryable_status(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    return isinstance(status_code, int) and 500 <= status_code < 600


def _balance_tool_calls(chat_ctx: llm.ChatContext) -> llm.ChatContext:
    """Drop orphaned tool calls/outputs so strict providers don't 400.

    MiniMax rejects requests whose assistant tool_calls aren't 1:1 matched with
    their tool results ("invalid params, invalid tool calls count"). Barge-in
    interruptions and preemptive generation can leave a FunctionCall without its
    FunctionCallOutput (or vice-versa) in the running history; we drop those
    unmatched items before sending, preserving order. Returns the original
    context untouched when nothing needs repair.
    """
    items = list(chat_ctx.items)
    call_ids = {it.call_id for it in items if isinstance(it, FunctionCall)}
    output_ids = {it.call_id for it in items if isinstance(it, FunctionCallOutput)}
    if call_ids == output_ids:
        return chat_ctx

    repaired = chat_ctx.copy()
    kept = [
        it
        for it in repaired.items
        if not (
            (isinstance(it, FunctionCall) and it.call_id not in output_ids)
            or (isinstance(it, FunctionCallOutput) and it.call_id not in call_ids)
        )
    ]
    repaired.items[:] = kept
    return repaired


class OpenAIChatLLM(llm.LLM):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        provider: str,
        default_temperature: float,
        case_id: str | None,
        max_tokens: int,
        label: str,
        base_url: str | None = None,
    ) -> None:
        super().__init__()
        self._client: openai.AsyncClient | None = None
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._provider = provider
        self._default_temperature = default_temperature
        self._case_id = case_id
        self._max_tokens = max_tokens
        self._label = label

    def _ensure_client(self) -> openai.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {
                "X-TFY-METADATA": "{}",
                "X-TFY-LOGGING-CONFIG": '{"enabled": true}',
            }
            if self._provider == "truefoundry":
                guardrails = _tfy_guardrails_header()
                if guardrails:
                    headers["X-TFY-GUARDRAILS"] = guardrails
            client_kwargs: dict[str, Any] = {
                "api_key": self._api_key or "placeholder",
                "default_headers": headers,
            }
            if self._base_url:
                client_kwargs["base_url"] = self._base_url
            self._client = openai.AsyncClient(**client_kwargs)
        return self._client

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return self._provider

    def _merge_extra_kwargs(
        self,
        extra_kwargs: dict[str, Any] | None,
        *,
        temperature: float | None = None,
        turn_index: int | None = None,
    ) -> dict[str, Any]:
        merged = dict(extra_kwargs or {})
        merged.setdefault(
            "temperature",
            self._default_temperature if temperature is None else temperature,
        )
        if (
            self._max_tokens
            and "max_completion_tokens" not in merged
            and "max_tokens" not in merged
        ):
            merged["max_completion_tokens"] = self._max_tokens
        return merged

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = APIConnectOptions(),
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> inference.LLMStream:
        merged = self._merge_extra_kwargs(
            None if extra_kwargs is NOT_GIVEN else extra_kwargs,
        )
        if parallel_tool_calls is not NOT_GIVEN:
            merged["parallel_tool_calls"] = parallel_tool_calls
        if tool_choice is not NOT_GIVEN:
            merged["tool_choice"] = tool_choice

        # MiniMax strictly validates tool-call/result pairing; repair the history
        # so an interrupted, unanswered tool call can't 400 the whole turn.
        if self._provider == "minimax":
            chat_ctx = _balance_tool_calls(chat_ctx)

        return inference.LLMStream(
            self,
            model=self._model,
            provider=self._provider,
            inference_class=None,
            strict_tool_schema=True,
            client=self._ensure_client(),
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            extra_kwargs=merged,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()


def _sanitize_for_bedrock(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten provider messages to plain {role, content:str} Bedrock accepts.

    ``to_provider_format('openai')`` can emit list/multimodal content (video
    frames, image parts) and tool-call/tool-result messages that the Bedrock
    OpenAI-compat shim can't parse; we keep only text and guarantee a trailing
    user turn so Bedrock always has something to answer.
    """
    out: list[dict[str, Any]] = []
    for msg in raw:
        role = msg.get("role")
        if role not in ("system", "user", "assistant"):
            continue  # drop tool / function messages
        content = msg.get("content")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ).strip()
        if isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content})
    if not out or out[-1]["role"] != "user":
        out.append({"role": "user", "content": "Please continue."})
    return out


class _BedrockLLMStream(LLMStream):
    """One-shot Bedrock completion exposed as a LiveKit LLM stream.

    A reliable, uncapped dialogue provider (and last-resort fallback). It is
    non-streaming and does not invoke tools — the goal is to keep Aria talking;
    the OpenAI primaries handle tool-calling when they are available.
    """

    def __init__(
        self,
        llm_: llm.LLM,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options: APIConnectOptions,
        temperature: float,
        max_tokens: int,
    ) -> None:
        super().__init__(
            llm_, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options
        )
        self._cc = chat_ctx
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def _run(self) -> None:
        raw, _ = self._cc.to_provider_format("openai")
        messages = _sanitize_for_bedrock(raw)
        try:
            data = await bedrock_chat_openai_compat(
                messages, temperature=self._temperature, max_tokens=self._max_tokens
            )
        except Exception:
            logger.exception("BedrockLLM stream failed (messages=%d)", len(messages))
            raise
        content = (
            (data or {}).get("content", "") if isinstance(data, dict) else str(data)
        )
        self._event_ch.send_nowait(
            llm.ChatChunk(
                id="bedrock-fallback",
                delta=llm.ChoiceDelta(role="assistant", content=content or ""),
            )
        )


class BedrockLLM(llm.LLM):
    """Minimal Bedrock-backed dialogue LLM (failover only)."""

    def __init__(self, *, temperature: float = 0.4, max_tokens: int = 400) -> None:
        super().__init__()
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return bedrock_model_id()

    @property
    def provider(self) -> str:
        return "bedrock"

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions | None = None,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> LLMStream:
        return _BedrockLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options or APIConnectOptions(),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )


class TrueFoundryLLM(llm.LLM):
    def __init__(
        self,
        *,
        case_id: str | None = None,
        primary_llm: llm.LLM | None = None,
        fallback_llm: llm.LLM | None = None,
    ) -> None:
        super().__init__()
        self._case_id = case_id
        # Slightly warmer than 0.4 so intake feels human and varied (not robotic),
        # while staying controlled enough to avoid rambling. Env-tunable.
        self._primary_temperature = float(os.getenv("DIALOGUE_TEMPERATURE", "0.5"))
        self._extract_temperature = 0.0
        self._score_temperature = 0.0
        self._max_tokens = _get_int_env("LLM_MAX_TOKENS", 400)

        if primary_llm is None:
            primary_llm = OpenAIChatLLM(
                api_key=_get_env("OPENAI_API_KEY", "TRUEFOUNDRY_API_KEY"),
                model=_get_env(
                    "OPENAI_MODEL",
                    "TRUEFOUNDRY_MODEL",
                    default="virtual-models/prod-model",
                ),
                provider="truefoundry",
                default_temperature=self._primary_temperature,
                case_id=case_id,
                max_tokens=self._max_tokens,
                label="truefoundry-virtual",
                base_url=_get_env(
                    "OPENAI_BASE_URL",
                    "TRUEFOUNDRY_GATEWAY_URL",
                    default="https://gateway.truefoundry.ai",
                ),
            )

        # Virtual model owns primary/Bedrock routing at the gateway level.
        # Python chain adds LiveKit Inference and native Bedrock as deeper safety nets.
        self._primary_llm = primary_llm
        self._fallback_llm = primary_llm  # alias for _complete_text compat

        direct_llm: llm.LLM | None = None
        if openai_direct_configured():
            direct_llm = OpenAIChatLLM(
                api_key=os.getenv("OPENAI_DIRECT_API_KEY", ""),
                model=os.getenv("OPENAI_DIRECT_MODEL", "gpt-4.1-mini"),
                provider="openai-direct",
                default_temperature=self._primary_temperature,
                case_id=case_id,
                max_tokens=self._max_tokens,
                label="openai-direct",
                base_url="https://api.openai.com/v1",
            )

        # MiniMax LLM (OpenAI-compatible, supports tool calling) using the same
        # key as MiniMax TTS. MiniMax-Text-01 is the default: no <think> reasoning
        # tokens to leak into speech, fast, and the user's key already works — so
        # it's the best dialogue primary, sidestepping the OpenAI free-tier cap.
        minimax_llm = _minimax_llm(
            case_id=case_id,
            temperature=self._primary_temperature,
            max_tokens=self._max_tokens,
        )
        # Front door: a single TrueFoundry virtual model that owns provider
        # routing/failover. Preferred first when configured; otherwise None.
        tfy_virtual_dialogue = _tfy_virtual_dialogue_llm(
            case_id=case_id,
            temperature=self._primary_temperature,
            max_tokens=self._max_tokens,
        )
        bedrock_llm: llm.LLM | None = (
            BedrockLLM(
                temperature=self._primary_temperature, max_tokens=self._max_tokens
            )
            if bedrock_configured()
            else None
        )
        livekit_llm = _livekit_inference_llm()

        # Build the failover chain, honoring DIALOGUE_PRIMARY for the first slot.
        # OpenAI is daily-capped on the free tier (credits don't lift it), so the
        # default primary is MiniMax (works + tool calls), then Bedrock, then the
        # OpenAI paths once the org has a payment method. Set DIALOGUE_PRIMARY to
        # minimax | bedrock | openai | truefoundry to change the preferred provider.
        by_pref = {
            "minimax": minimax_llm,
            "bedrock": bedrock_llm,
            "openai": direct_llm,
            "openai-direct": direct_llm,
            "truefoundry": self._primary_llm,
        }
        primary_pref = os.getenv("DIALOGUE_PRIMARY", "minimax").strip().lower()

        chain: list[llm.LLM] = []

        def _add(candidate: llm.LLM | None) -> None:
            if candidate is not None and candidate not in chain:
                chain.append(candidate)

        # TrueFoundry virtual model leads the chain when configured (front door),
        # unless DIALOGUE_PRIMARY explicitly pins a different provider first.
        if primary_pref in {"truefoundry", "tfy", "virtual"}:
            _add(tfy_virtual_dialogue)
        _add(by_pref.get(primary_pref))
        _add(tfy_virtual_dialogue)
        # Reliability-ordered remainder (deduped against the preferred primary).
        _add(minimax_llm)
        _add(bedrock_llm)
        _add(direct_llm)
        _add(self._primary_llm)
        if self._fallback_llm is not self._primary_llm:
            _add(self._fallback_llm)
        _add(livekit_llm)

        self._router = CaseflowFallbackAdapter(
            chain,
            case_id=case_id,
            attempt_timeout=DEFAULT_TIMEOUT_SECONDS,
            max_retry_per_llm=0,
            retry_interval=0.2,
            retry_on_chunk_sent=True,
        )

    @property
    def model(self) -> str:
        return self._primary_llm.model

    @property
    def provider(self) -> str:
        return "truefoundry"

    def _turn_index(self, chat_ctx: llm.ChatContext) -> int | None:
        user_messages = 0
        for item in getattr(chat_ctx, "items", []) or []:
            if getattr(item, "role", None) == "user":
                user_messages += 1
        return user_messages or None

    def converse(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        *,
        case_id: str | None = None,
        turn_index: int | None = None,
        temperature: float | None = None,
        conn_options: APIConnectOptions | None = None,
        parallel_tool_calls: bool | None = None,
        tool_choice: llm.ToolChoice | None = None,
    ) -> llm.LLMStream:
        merged_extra: dict[str, Any] = {
            "temperature": self._primary_temperature
            if temperature is None
            else temperature,
            "max_completion_tokens": self._max_tokens,
        }
        if parallel_tool_calls is not None:
            merged_extra["parallel_tool_calls"] = parallel_tool_calls
        if tool_choice is not None:
            merged_extra["tool_choice"] = tool_choice

        return self._primary_llm.chat(
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options
            or APIConnectOptions(timeout=DEFAULT_TIMEOUT_SECONDS, max_retry=0),
            extra_kwargs=merged_extra,
        )

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = APIConnectOptions(),
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> llm.LLMStream:
        merged = dict({} if extra_kwargs is NOT_GIVEN else extra_kwargs)
        merged.setdefault("temperature", self._primary_temperature)
        merged.setdefault("max_completion_tokens", self._max_tokens)

        if parallel_tool_calls is not NOT_GIVEN:
            merged["parallel_tool_calls"] = parallel_tool_calls
        if tool_choice is not NOT_GIVEN:
            merged["tool_choice"] = tool_choice

        return self._router.chat(
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            extra_kwargs=merged,
        )

    async def extract_fields(self, transcript_chunk: str, current_state: str) -> str:
        prompt = [
            {
                "role": "system",
                "content": "Extract structured PI intake fields as compact JSON only.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "transcript_chunk": transcript_chunk,
                        "current_state": current_state,
                    }
                ),
            },
        ]
        return await self._complete_text(prompt, temperature=self._extract_temperature)

    async def score_case(self, case_data: str) -> str:
        prompt = [
            {
                "role": "system",
                "content": "Score the case from 0-100 and explain briefly in JSON only.",
            },
            {"role": "user", "content": case_data},
        ]
        return await self._complete_text(prompt, temperature=self._score_temperature)

    async def _complete_text(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
    ) -> str:
        attempts: list[tuple[openai.AsyncClient, str, str]] = []
        if openai_direct_configured():
            attempts.append(
                (
                    openai.AsyncClient(
                        api_key=os.getenv("OPENAI_DIRECT_API_KEY", ""),
                        base_url="https://api.openai.com/v1",
                    ),
                    os.getenv("OPENAI_DIRECT_MODEL", "gpt-4.1-mini"),
                    "openai-direct",
                )
            )
        attempts.extend(
            [
                (
                    self._primary_llm._ensure_client(),
                    self._primary_llm.model,
                    "truefoundry",
                ),  # noqa: SLF001
            ]
        )
        for client, model, provider in attempts:
            try:
                response = await client.chat.completions.create(  # type: ignore[union-attr]
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_completion_tokens=self._max_tokens,
                    timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS),
                )
                content = response.choices[0].message.content or ""
                return content
            except (openai.APITimeoutError, openai.APIConnectionError) as error:
                logger.warning("LLM failover to %s due to %s", provider, error)
                continue
            except openai.APIStatusError as error:
                if _is_retryable_status(error):
                    logger.warning("LLM failover to %s due to %s", provider, error)
                    continue
                raise

        raise RuntimeError("All dialogue LLM completions failed")

    async def aclose(self) -> None:
        await self._router.aclose()


def dialogue_llm_configured() -> bool:
    return openai_direct_configured() or bool(
        _get_env("TRUEFOUNDRY_API_KEY", "OPENAI_API_KEY")
    )


def build_caseflow_llm(*, case_id: str | None = None) -> TrueFoundryLLM:
    return TrueFoundryLLM(case_id=case_id)


def build_dialogue_llm(*, case_id: str | None = None) -> llm.LLM:
    """Intake dialogue LLM — OpenAI direct → TrueFoundry virtual model → LiveKit Inference."""
    if dialogue_llm_configured():
        return build_caseflow_llm(case_id=case_id)
    livekit_llm = _livekit_inference_llm()
    if livekit_llm is not None:
        return livekit_llm
    raise RuntimeError(
        "No dialogue LLM configured (set OPENAI_DIRECT_API_KEY, TrueFoundry, or LiveKit keys)"
    )
