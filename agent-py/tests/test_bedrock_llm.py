from bedrock_llm import bedrock_configured, split_openai_messages


def test_bedrock_configured_with_iam(monkeypatch) -> None:
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    monkeypatch.delenv("AWS_BEDROCK_API_KEY", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert bedrock_configured() is True


def test_split_openai_messages_extracts_system() -> None:
    system, messages = split_openai_messages(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hola"},
            {"role": "assistant", "content": "Bienvenido"},
        ]
    )
    assert system == "You are helpful."
    assert len(messages) == 2
    assert messages[0]["content"] == [{"text": "Hola"}]
