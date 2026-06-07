import json

import pytest

from livekit.agents import llm

import llm_client


class _FakeStream(llm.LLMStream):
    def __init__(self, owner, *, chunks=None, error=None, chat_ctx=None, tools=None, conn_options=None):
        super().__init__(owner, chat_ctx=chat_ctx or llm.ChatContext(), tools=tools or [], conn_options=conn_options or llm_client.APIConnectOptions())
        self._chunks = chunks or []
        self._error = error

    async def _run(self) -> None:
        for chunk in self._chunks:
            self._event_ch.send_nowait(chunk)
        if self._error is not None:
            raise self._error


class _FakeLLM(llm.LLM):
    def __init__(self, *, model: str, provider: str, chunks=None, error=None):
        super().__init__()
        self._model = model
        self._provider = provider
        self._chunks = chunks or []
        self._error = error
        self.calls: list[dict] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return self._provider

    def chat(self, *, chat_ctx, tools=None, conn_options=llm_client.APIConnectOptions(), parallel_tool_calls=llm_client.NOT_GIVEN, tool_choice=llm_client.NOT_GIVEN, extra_kwargs=llm_client.NOT_GIVEN):
        self.calls.append(
            {
                "chat_ctx": chat_ctx,
                "tools": tools or [],
                "conn_options": conn_options,
                "parallel_tool_calls": parallel_tool_calls,
                "tool_choice": tool_choice,
                "extra_kwargs": {} if extra_kwargs is llm_client.NOT_GIVEN else dict(extra_kwargs),
            }
        )
        return _FakeStream(self, chunks=self._chunks, error=self._error, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)


@pytest.mark.asyncio
async def test_converse_streams_incremental_tokens() -> None:
    client = llm_client.TrueFoundryLLM(
        case_id="case_123",
        primary_llm=_FakeLLM(
            model="tf-model",
            provider="truefoundry",
            chunks=[
                llm.ChatChunk(id="1", delta=llm.ChoiceDelta(role="assistant", content="Hel")),
                llm.ChatChunk(id="1", delta=llm.ChoiceDelta(role="assistant", content="lo")),
            ],
        ),
        fallback_llm=_FakeLLM(model="fallback", provider="openai", chunks=[]),
    )

    stream = client.converse(llm.ChatContext(), [])
    tokens = []
    async for token in stream.to_str_iterable():
        tokens.append(token)

    assert tokens == ["Hel", "lo"]
    assert client._primary_llm.calls[0]["extra_kwargs"]["metadata"]["case_id"] == "case_123"


@pytest.mark.asyncio
async def test_converse_preserves_tool_calls() -> None:
    tool_call = llm.FunctionToolCall(
        name="search_legal_knowledge",
        arguments=json.dumps({"query": "California SoL"}),
        call_id="call_1",
    )
    client = llm_client.TrueFoundryLLM(
        primary_llm=_FakeLLM(
            model="tf-model",
            provider="truefoundry",
            chunks=[
                llm.ChatChunk(
                    id="1",
                    delta=llm.ChoiceDelta(role="assistant", tool_calls=[tool_call]),
                )
            ],
        ),
        fallback_llm=_FakeLLM(model="fallback", provider="openai"),
    )

    response = await client.converse(llm.ChatContext(), []).collect()

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "search_legal_knowledge"
    assert json.loads(response.tool_calls[0].arguments) == {"query": "California SoL"}


@pytest.mark.asyncio
async def test_converse_falls_back_silently() -> None:
    client = llm_client.TrueFoundryLLM(
        primary_llm=_FakeLLM(
            model="tf-model",
            provider="truefoundry",
            error=RuntimeError("primary failed"),
        ),
        fallback_llm=_FakeLLM(
            model="fallback-model",
            provider="openai",
            chunks=[
                llm.ChatChunk(id="2", delta=llm.ChoiceDelta(role="assistant", content="fallback ok")),
            ],
        ),
    )

    response = await client.converse(llm.ChatContext(), []).collect()

    assert response.text == "fallback ok"
    assert len(client._primary_llm.calls) >= 1
    assert len(client._fallback_llm.calls) == 1


@pytest.mark.asyncio
async def test_extract_and_score_default_temperature(monkeypatch) -> None:
    client = llm_client.TrueFoundryLLM(
        primary_llm=_FakeLLM(model="tf-model", provider="truefoundry"),
        fallback_llm=_FakeLLM(model="fallback-model", provider="openai"),
    )

    recorded: list[float] = []

    async def fake_complete_text(messages, *, temperature):
        recorded.append(temperature)
        return json.dumps({"ok": True})

    monkeypatch.setattr(client, "_complete_text", fake_complete_text)

    await client.extract_fields("chunk", "state")
    await client.score_case("case data")

    assert recorded == [0.0, 0.0]
