from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterable
from typing import Any

import httpx
import openai
from livekit.agents import inference, llm
from livekit.agents.llm.fallback_adapter import FallbackAdapter
from livekit.agents.types import APIConnectOptions, NOT_GIVEN, NotGivenOr

logger = logging.getLogger("agent.llm_client")

DEFAULT_TIMEOUT_SECONDS = 8.0


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


class OpenAIChatLLM(llm.LLM):
    def __init__(
        self,
        *,
        client: openai.AsyncClient,
        model: str,
        provider: str,
        default_temperature: float,
        case_id: str | None,
        max_tokens: int,
        label: str,
    ) -> None:
        super().__init__()
        self._client = client
        self._model = model
        self._provider = provider
        self._default_temperature = default_temperature
        self._case_id = case_id
        self._max_tokens = max_tokens
        self._label = label

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
        merged.setdefault("temperature", self._default_temperature if temperature is None else temperature)
        if self._max_tokens and "max_completion_tokens" not in merged and "max_tokens" not in merged:
            merged["max_completion_tokens"] = self._max_tokens
        metadata = _build_metadata(self._case_id, turn_index)
        if metadata:
            merged["metadata"] = metadata
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

        return inference.LLMStream(
            self,
            model=self._model,
            provider=self._provider,
            inference_class=None,
            strict_tool_schema=True,
            client=self._client,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            extra_kwargs=merged,
        )

    async def aclose(self) -> None:
        await self._client.close()


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
        self._primary_temperature = 0.4
        self._extract_temperature = 0.0
        self._score_temperature = 0.0
        self._max_tokens = _get_int_env("LLM_MAX_TOKENS", 400)

        if primary_llm is None:
            primary_llm = OpenAIChatLLM(
                client=openai.AsyncClient(
                    api_key=os.getenv("TRUEFOUNDRY_API_KEY", ""),
                    base_url=os.getenv("TRUEFOUNDRY_GATEWAY_URL", ""),
                ),
                model=os.getenv("TRUEFOUNDRY_MODEL", "openai/gpt-4o"),
                provider="truefoundry",
                default_temperature=self._primary_temperature,
                case_id=case_id,
                max_tokens=self._max_tokens,
                label="truefoundry",
            )

        if fallback_llm is None:
            fallback_llm = OpenAIChatLLM(
                client=openai.AsyncClient(
                    api_key=os.getenv("OPENAI_API_KEY", ""),
                ),
                model=os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4o"),
                provider="openai",
                default_temperature=self._primary_temperature,
                case_id=case_id,
                max_tokens=self._max_tokens,
                label="openai-fallback",
            )

        self._primary_llm = primary_llm
        self._fallback_llm = fallback_llm
        self._router = FallbackAdapter(
            [self._primary_llm, self._fallback_llm],
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
            "temperature": self._primary_temperature if temperature is None else temperature,
            "max_completion_tokens": self._max_tokens,
        }
        metadata = _build_metadata(case_id or self._case_id, turn_index or self._turn_index(chat_ctx))
        if metadata:
            merged_extra["metadata"] = metadata

        if parallel_tool_calls is not None:
            merged_extra["parallel_tool_calls"] = parallel_tool_calls
        if tool_choice is not None:
            merged_extra["tool_choice"] = tool_choice

        return self._router.chat(
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options or APIConnectOptions(timeout=DEFAULT_TIMEOUT_SECONDS, max_retry=0),
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

        metadata = _build_metadata(self._case_id, self._turn_index(chat_ctx))
        if metadata:
            merged.setdefault("metadata", metadata)

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
            {"role": "system", "content": "Extract structured PI intake fields as compact JSON only."},
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
            {"role": "system", "content": "Score the case from 0-100 and explain briefly in JSON only."},
            {"role": "user", "content": case_data},
        ]
        return await self._complete_text(prompt, temperature=self._score_temperature)

    async def _complete_text(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
    ) -> str:
        primary_client = self._primary_llm._client  # noqa: SLF001
        fallback_client = self._fallback_llm._client  # noqa: SLF001
        primary_model = self._primary_llm.model
        fallback_model = self._fallback_llm.model
        metadata = _build_metadata(self._case_id, None)

        for client, model, provider in (
            (primary_client, primary_model, "truefoundry"),
            (fallback_client, fallback_model, "openai"),
        ):
            try:
                response = await client.chat.completions.create(  # type: ignore[union-attr]
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_completion_tokens=self._max_tokens,
                    metadata=metadata or None,
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

        raise RuntimeError("Both TrueFoundry and OpenAI fallback completions failed")

    async def aclose(self) -> None:
        await self._router.aclose()


def build_caseflow_llm(*, case_id: str | None = None) -> TrueFoundryLLM:
    return TrueFoundryLLM(case_id=case_id)
