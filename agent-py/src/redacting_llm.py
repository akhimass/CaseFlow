"""Wrap LiveKit Inference LLM — redact prompts, unredact streamed replies."""

from __future__ import annotations

import copy
from typing import Any

from livekit.agents import inference, llm
from livekit.agents.llm.chat_context import ChatMessage, Instructions
from livekit.agents.llm.llm import LLMStream
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr

from pii_redaction import RedactionSession, Redactor


class RedactingLLM(llm.LLM):
    def __init__(
        self,
        *,
        inner: llm.LLM,
        session: RedactionSession,
        language: str = "en",
    ) -> None:
        super().__init__()
        self._inner = inner
        self._session = session
        self._language = language

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def provider(self) -> str:
        return self._inner.provider

    def set_language(self, language: str) -> None:
        self._language = language

    def _redact_chat_ctx(self, chat_ctx: llm.ChatContext) -> llm.ChatContext:
        copied = chat_ctx.copy()
        redactor = Redactor(self._session)
        for item in copied.items:
            if not isinstance(item, ChatMessage):
                continue
            new_content: list[Any] = []
            for block in item.content:
                if isinstance(block, str):
                    redacted, _ = redactor.redact(block, self._language)
                    new_content.append(redacted)
                elif isinstance(block, Instructions):
                    new_content.append(
                        Instructions(
                            audio=redactor.redact(block.audio, self._language)[0],
                            text=redactor.redact(block.text, self._language)[0],
                        )
                    )
                else:
                    new_content.append(block)
            item.content = new_content
        return copied

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options=DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> LLMStream:
        redacted_ctx = self._redact_chat_ctx(chat_ctx)
        inner_stream = self._inner.chat(
            chat_ctx=redacted_ctx,
            tools=tools,
            conn_options=conn_options,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        )
        return _UnredactingLLMStream(
            llm=self,
            inner=inner_stream,
            session=self._session,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )

    def prewarm(self) -> None:
        self._inner.prewarm()

    async def aclose(self) -> None:
        await self._inner.aclose()


class _UnredactingLLMStream(LLMStream):
    def __init__(
        self,
        *,
        llm: RedactingLLM,
        inner: LLMStream,
        session: RedactionSession,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool],
        conn_options,
    ) -> None:
        super().__init__(llm, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._inner = inner
        self._redactor = Redactor(session)

    async def _run(self) -> None:
        async for chunk in self._inner:
            if chunk.delta and chunk.delta.content:
                chunk = copy.copy(chunk)
                chunk.delta = copy.copy(chunk.delta)
                chunk.delta.content = self._redactor.unredact(chunk.delta.content)
            self._event_ch.send_nowait(chunk)
