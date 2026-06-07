from minimax_voice import (
    CASEFLOW_PI_KEYTERMS,
    VoiceSessionState,
    apply_tts_options,
    build_caseflow_stt,
    build_caseflow_voice,
    caseflow_stt_keyterms,
    caseflow_stt_model,
    deepgram_configured,
    detect_language_from_text,
    language_boost_for,
    pronunciation_tone_entries,
    resolve_caller_language,
    sync_caller_language,
)


def test_detect_language_from_text() -> None:
    assert detect_language_from_text("Hola, me chocaron en un semáforo") == "es"
    assert detect_language_from_text("Hello, I was rear-ended yesterday") == "en"


def test_resolve_caller_language_prefers_stt_tag() -> None:
    assert (
        resolve_caller_language(
            stt_language="es-MX",
            transcript="Hello there",
            current="en",
        )
        == "es"
    )


def test_resolve_caller_language_falls_back_to_transcript() -> None:
    assert (
        resolve_caller_language(
            stt_language=None,
            transcript="Gracias por ayudarme",
            current="en",
        )
        == "es"
    )


def test_language_boost_auto_until_confirmed() -> None:
    assert language_boost_for("en", confirmed=False) == "auto"
    assert language_boost_for("es", confirmed=True) == "Spanish"
    assert language_boost_for("en", confirmed=True) == "English"


def test_sync_caller_language_switches_voice(monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_VOICE_ID_ES", "Spanish_Test")
    monkeypatch.setenv("MINIMAX_VOICE_ID_EN", "English_Test")

    state = VoiceSessionState()
    updates: list[dict] = []

    class FakeTTS:
        def update_options(self, **kwargs) -> None:
            updates.append(kwargs)

    changed = sync_caller_language(state, "es", tts=FakeTTS())  # type: ignore[arg-type]
    assert changed is True
    assert state.caller_language == "es"
    assert state.language_confirmed is True
    assert updates[-1]["voice"] == "Spanish_Test"
    assert updates[-1]["language_boost"] == "Spanish"

    changed_again = sync_caller_language(state, "es", tts=FakeTTS())  # type: ignore[arg-type]
    assert changed_again is False


def test_deepgram_configured(monkeypatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    assert deepgram_configured() is False
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    assert deepgram_configured() is True


def test_build_caseflow_stt_uses_deepgram_when_keyed(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    stt_instance = build_caseflow_stt()
    assert stt_instance.__class__.__module__.startswith("livekit.plugins.deepgram")


def test_caseflow_stt_model_defaults_to_deepgram_nova3(monkeypatch) -> None:
    monkeypatch.delenv("CASEFLOW_STT_MODEL", raising=False)
    assert caseflow_stt_model() == "deepgram/nova-3"


def test_apply_tts_options_uses_confirmed_boost() -> None:
    state = VoiceSessionState(caller_language="es", language_confirmed=True)
    captured: dict = {}

    class FakeTTS:
        def update_options(self, **kwargs) -> None:
            captured.update(kwargs)

    apply_tts_options(FakeTTS(), state)  # type: ignore[arg-type]
    assert captured["language_boost"] == "Spanish"
    assert captured["voice"] == state.voice_id_for("es")


def test_caseflow_stt_keyterms_include_demo_vocabulary() -> None:
    terms = caseflow_stt_keyterms()
    assert "semáforo" in terms
    assert "luz roja" in terms
    assert "whiplash" in terms
    assert len(terms) >= len(CASEFLOW_PI_KEYTERMS)


def test_caseflow_stt_keyterms_env_extension(monkeypatch) -> None:
    monkeypatch.setenv("CASEFLOW_STT_KEYTERMS", "T-bone, concussión")
    terms = caseflow_stt_keyterms()
    assert "T-bone" in terms
    assert "concussión" in terms


def test_build_caseflow_voice_wraps_minimax(monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    state = VoiceSessionState()
    logging_tts, inner = build_caseflow_voice(state=state)
    assert logging_tts.provider == "MiniMax"
    assert logging_tts is not inner
    assert logging_tts.sample_rate == inner.sample_rate


def test_pronunciation_includes_pi_demo_terms() -> None:
    state = VoiceSessionState()
    tone = pronunciation_tone_entries(state)
    joined = " ".join(tone)
    assert "whiplash" in joined
    assert "semáforo" in joined
