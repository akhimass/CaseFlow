import pytest

from gateway import GatewayMetadata, _provider_chain, get_recent_audit, resolve_model


def test_resolve_model_aliases() -> None:
    assert resolve_model("qwen-max")  # legacy alias maps to OpenAI model id
    assert resolve_model("gpt-4.1-mini")


def test_audit_buffer() -> None:
    from gateway import _audit_buffer

    _audit_buffer.clear()
    assert get_recent_audit() == []


def test_metadata_header() -> None:
    header = GatewayMetadata(case_id="abc", turn=3, caller_id="user_1").as_header()
    assert "case_id" in header
    assert "abc" in header


def test_provider_chain_openai_first(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("TRUEFOUNDRY_GATEWAY_URL", "https://gateway.truefoundry.ai")
    monkeypatch.setenv("TRUEFOUNDRY_API_KEY", "tfy-key")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert _provider_chain(allow_failover=True) == [
        "openai",
        "truefoundry",
        "bedrock",
        "livekit-inference",
    ]


def test_provider_chain_truefoundry_then_bedrock(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("TRUEFOUNDRY_GATEWAY_URL", "https://gateway.truefoundry.ai")
    monkeypatch.setenv("TRUEFOUNDRY_API_KEY", "tfy-key")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert _provider_chain(allow_failover=True) == [
        "truefoundry",
        "bedrock",
        "livekit-inference",
    ]


def test_provider_chain_bedrock_only(monkeypatch) -> None:
    monkeypatch.delenv("TRUEFOUNDRY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("TRUEFOUNDRY_API_KEY", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert _provider_chain(allow_failover=False) == ["bedrock"]


@pytest.mark.asyncio
async def test_chat_uses_bedrock_when_truefoundry_missing(monkeypatch) -> None:
    from gateway import chat

    monkeypatch.delenv("TRUEFOUNDRY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("TRUEFOUNDRY_API_KEY", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")

    async def fake_bedrock(_messages, **_kwargs):
        return {
            "content": '{"conflict": false}',
            "model": "us.amazon.nova-lite-v1:0",
            "provider": "bedrock",
        }

    monkeypatch.setattr("gateway.bedrock_chat_openai_compat", fake_bedrock)

    response = await chat(
        "qwen-max",
        [
            {"role": "system", "content": "Return JSON"},
            {"role": "user", "content": "test"},
        ],
        allow_failover=False,
    )
    assert response.provider == "bedrock"
    assert response.failover is False
    assert "conflict" in response.content
