"""MiniMax STT/TTS helpers, emotion routing, and logging wrappers."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Literal

from livekit.agents import APIConnectOptions, inference, stt, tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr
from livekit.plugins import deepgram, minimax

from metrics import MetricsTracker

logger = logging.getLogger("caseflow.minimax")

MessageType = Literal["default", "empathetic", "reassuring"]
CallerLanguage = Literal["en", "es"]
MULTILINGUAL_STT_LANGUAGE = "multi"


def pronunciation_tone_entries(state: VoiceSessionState | None = None) -> list[str]:
    merged = dict(PI_PRONUNCIATION)
    if state:
        for key, phrase in state.extra_pronunciations.items():
            merged.setdefault(phrase.lower(), [syllabify_phrase(phrase)])
    return [f"{phrase}/{' '.join(parts)}" for phrase, parts in merged.items()]


def syllabify_phrase(phrase: str) -> str:
    words = re.findall(r"[a-zA-Záéíóúñü]+", phrase)
    return "/".join(words) if words else phrase


PI_PRONUNCIATION: dict[str, list[str]] = {
    "latigazo cervical": ["latigazo/la-ti-ga-zo", "cervical/ser-vi-cal"],
    "resonancia magnética": ["resonancia/re-so-nan-cia", "magnética/mag-ne-ti-ca"],
    "whiplash": ["whiplash/whip-lash"],
    "semáforo": ["semáforo/se-má-fo-ro"],
    "luz roja": ["luz/roja"],
    "rear-ended": ["rear-ended/rear-end-ed"],
    "subrogation": ["subrogation/sub-ro-ga-tion"],
    "statute of limitations": ["statute/sta-tute", "limitations/li-mi-ta-tions"],
    "demand letter": ["demand/de-mand", "letter/let-ter"],
}

# Deepgram nova-3 keyterms tuned for the Maria Delgado PI demo. The accident
# vocabulary up top biases recognition toward how callers actually open ("I got
# into a car wreck") so it stops mishearing them ("car bench").
CASEFLOW_PI_KEYTERMS: tuple[str, ...] = (
    # Accident vocabulary (English) — the most common opening phrases.
    "car accident",
    "car crash",
    "car wreck",
    "wreck",
    "crash",
    "collision",
    "accident",
    "fender bender",
    "T-bone",
    "sideswiped",
    "hit from behind",
    "got rear-ended",
    "hit and run",
    # Accident vocabulary (Spanish).
    "accidente",
    "choque",
    "me chocaron",
    "atropello",
    # Injuries / treatment.
    "whiplash",
    "latigazo cervical",
    "neck pain",
    "back pain",
    "concussion",
    "MRI",
    "resonancia magnética",
    # Demo-specific terms.
    "semáforo",
    "luz roja",
    "rear-ended",
    "rear ended",
    "personal injury",
    "Orange County",
    "police report",
    "statute of limitations",
    "red light",
    "intersection",
    "Maria Delgado",
    "abogado",
    "seguro",
    "fault undetermined",
)


def select_emotion(message_type: MessageType) -> str:
    if message_type == "empathetic":
        return "calm"
    if message_type == "reassuring":
        return "calm"
    # Baseline is calm/relaxed for the whole intake — not just empathetic moments.
    return os.getenv("MINIMAX_EMOTION", "calm") or "calm"


def select_speed(message_type: MessageType) -> float:
    if message_type == "empathetic":
        return float(os.getenv("MINIMAX_EMPATHY_SPEED", "0.85"))
    if message_type == "reassuring":
        return float(os.getenv("MINIMAX_REASSURE_SPEED", "0.96"))
    # Slightly under 1.0 reads as relaxed and easy to follow without sounding slow.
    return float(os.getenv("MINIMAX_SPEED", "0.94"))


def select_intensity(message_type: MessageType) -> int | None:
    if message_type == "empathetic":
        return int(os.getenv("MINIMAX_EMPATHY_INTENSITY", "-20"))
    if message_type == "reassuring":
        return int(os.getenv("MINIMAX_REASSURE_INTENSITY", "10"))
    return None


def language_boost_for(code: str, *, confirmed: bool) -> str | None:
    """Pin MiniMax to an explicit language — never ``auto`` (mis-detects as Chinese)."""
    del confirmed
    if code.startswith("es"):
        return "Spanish"
    return "English"


def normalize_lang(code: str | None) -> CallerLanguage | None:
    if not code:
        return None
    base = str(code).lower().split("-")[0]
    if base in ("en", "es"):
        return base  # type: ignore[return-value]
    return None


_ES_MARKERS = (
    "hola", "gracias", "accidente", "abogado", "seguro", "me chocaron", "choque",
    "señor", "señora", "dolor", "cuello", "espalda", "policía", "reporte", "carro",
    "el ", "la ", "que ", "por ", "una ", "estoy", "tengo", "fue ",
)
_EN_MARKERS = (
    "the ", "and ", "i ", "my ", "was ", "rear", "accident", "police", "report",
    "neck", "back", "pain", "insurance", "lawyer", "hit ", "car ", "fault",
)


def _language_scores(text: str) -> tuple[int, int]:
    lower = text.lower()
    es = len(re.findall(r"[áéíóúñ¿¡]", lower)) + sum(1 for w in _ES_MARKERS if w in lower)
    en = sum(1 for w in _EN_MARKERS if w in lower)
    return es, en


def detect_language_from_text(text: str) -> CallerLanguage | None:
    """Dominant language by marker count. Returns None when it's a tie/mixed
    (code-switching) so the caller keeps their current language instead of
    whipsawing the voice on a single mixed utterance."""
    es, en = _language_scores(text)
    if es == 0 and en == 0:
        return "en" if re.search(r"[a-z]", text.lower()) else None
    if es > en:
        return "es"
    if en > es:
        return "en"
    return None  # mixed / ambiguous → caller keeps current language


def resolve_caller_language(
    *,
    stt_language: str | None = None,
    transcript: str | None = None,
    current: str = "en",
) -> CallerLanguage:
    return (
        normalize_lang(stt_language)
        or (detect_language_from_text(transcript) if transcript else None)
        or normalize_lang(current)
        or "en"
    )


def sync_caller_language(
    state: VoiceSessionState,
    lang: CallerLanguage,
    *,
    tts: minimax.TTS | None = None,
) -> bool:
    """Update session language and TTS voice/boost. Returns True when language changed."""
    previous = state.caller_language
    changed = lang != previous or not state.language_confirmed
    state.caller_language = lang
    state.language_confirmed = True
    if tts is not None:
        apply_tts_options(tts, state)
    if changed:
        logger.info(
            "CASEFLOW_LANGUAGE %s",
            json.dumps(
                {
                    "language": lang,
                    "voice_id": state.voice_id_for(lang),
                    "language_boost": language_boost_for(lang, confirmed=True),
                    "previous": previous if previous != lang else None,
                },
                ensure_ascii=False,
            ),
        )
    return changed


def inference_model_name(env_value: str, *, prefix: str = "minimax") -> str:
    value = env_value.strip()
    if not value:
        return f"{prefix}/speech-2.8-hd"
    if "/" in value:
        return value
    return f"{prefix}/{value}"


@dataclass
class VoiceSessionState:
    caller_language: CallerLanguage = "en"
    language_confirmed: bool = False
    message_type: MessageType = "default"
    metrics: MetricsTracker | None = None
    extra_pronunciations: dict[str, str] = field(default_factory=dict)

    def voice_id_for(self, lang: str | None = None) -> str:
        code = normalize_lang(lang) or self.caller_language
        if code == "es":
            return os.getenv("MINIMAX_VOICE_ID_ES", "Spanish_SereneWoman")
        return os.getenv("MINIMAX_VOICE_ID_EN", "English_SereneWoman")


def apply_tts_options(
    tts_engine: minimax.TTS | "LoggingTTS", state: VoiceSessionState
) -> None:
    tts_engine.update_options(
        voice=state.voice_id_for(),
        emotion=select_emotion(state.message_type),
        speed=select_speed(state.message_type),
        intensity=select_intensity(state.message_type),
        language_boost=language_boost_for(
            state.caller_language, confirmed=state.language_confirmed
        ),
        pronunciation_dict={"tone": pronunciation_tone_entries(state)},
    )


def caseflow_stt_keyterms() -> list[str]:
    """PI vocabulary for Deepgram nova-3; extend via CASEFLOW_STT_KEYTERMS env."""
    extra = os.getenv("CASEFLOW_STT_KEYTERMS", "")
    terms = list(CASEFLOW_PI_KEYTERMS)
    for raw in extra.split(","):
        term = raw.strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def build_minimax_tts(*, state: VoiceSessionState) -> minimax.TTS:
    return minimax.TTS(
        model=os.getenv("MINIMAX_TTS_MODEL", "speech-2.8-hd"),
        voice=state.voice_id_for(),
        speed=select_speed(state.message_type),
        vol=float(os.getenv("MINIMAX_VOLUME", "1.0")),
        pitch=int(os.getenv("MINIMAX_PITCH", "0")),
        emotion=select_emotion(state.message_type),
        intensity=select_intensity(state.message_type),
        language_boost=language_boost_for(
            state.caller_language, confirmed=state.language_confirmed
        ),
        pronunciation_dict={"tone": pronunciation_tone_entries(state)},
        audio_format="pcm",
        sample_rate=24000,
        # Pacing holds sentences back to time them against playback; with network
        # latency that starves the emitter and makes speech choppy. Let MiniMax
        # generate continuously instead (plugin default).
        text_pacing=False,
    )


def deepgram_configured() -> bool:
    return bool(os.getenv("DEEPGRAM_API_KEY", "").strip())


def caseflow_stt_model() -> str:
    """STT model id for LiveKit Inference fallback when DEEPGRAM_API_KEY is unset."""
    return os.getenv("CASEFLOW_STT_MODEL", "deepgram/nova-3")


def build_caseflow_stt() -> stt.STT:
    """Deepgram nova-3 direct API when keyed; else LiveKit Inference deepgram/nova-3.

    MiniMax is TTS-only — transcription is always Deepgram; synthesis stays MiniMax.
    """
    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if api_key:
        model = os.getenv("DEEPGRAM_MODEL", "nova-3")
        language = os.getenv("DEEPGRAM_LANGUAGE", "multi")
        # Streaming STT cannot use Deepgram auto-detect; we resolve language from
        # transcript text in LoggingSTT instead (resolve_caller_language).
        detect = os.getenv("DEEPGRAM_DETECT_LANGUAGE", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        return deepgram.STT(
            model=model,
            language=language,
            detect_language=detect,
            interim_results=True,
            punctuate=True,
            smart_format=True,
            filler_words=True,
            keyterms=caseflow_stt_keyterms(),
            api_key=api_key,
        )
    logger.warning(
        "DEEPGRAM_API_KEY not set — falling back to LiveKit Inference %s",
        caseflow_stt_model(),
    )
    return inference.STT(model=caseflow_stt_model(), language=MULTILINGUAL_STT_LANGUAGE)


def _is_mostly_latin(text: str) -> bool:
    """True if the alphabetic characters are predominantly Latin script.

    en/es (incl. accents áéíóúñ, which sit below U+0250) are Latin; Devanagari,
    Arabic, CJK, Cyrillic, etc. are not. Used to drop STT mis-transcriptions.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    latin = sum(1 for c in letters if ord(c) < 0x250)
    return latin / len(letters) >= 0.6


class LoggingSTT(stt.STT):
    """Deepgram nova-3 STT with bilingual logging; MiniMax handles TTS."""

    def __init__(
        self, *, state: VoiceSessionState, tts: minimax.TTS | None = None
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=True, interim_results=True)
        )
        self._state = state
        self._tts = tts
        self._inner = build_caseflow_stt()

    @property
    def model(self) -> str:
        if deepgram_configured():
            return os.getenv("DEEPGRAM_MODEL", "nova-3")
        return caseflow_stt_model()

    @property
    def provider(self) -> str:
        return "Deepgram" if deepgram_configured() else "LiveKit-Inference"

    async def _recognize_impl(
        self,
        buffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        return await self._inner.recognize(
            buffer,
            language=MULTILINGUAL_STT_LANGUAGE,
            conn_options=conn_options,
        )

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.RecognizeStream:
        return _LoggingRecognizeStream(
            stt=self,
            inner=self._inner.stream(
                language=MULTILINGUAL_STT_LANGUAGE, conn_options=conn_options
            ),
            state=self._state,
        )


class _LoggingRecognizeStream(stt.RecognizeStream):
    def __init__(
        self,
        *,
        stt: LoggingSTT,
        inner: stt.RecognizeStream,
        state: VoiceSessionState,
    ) -> None:
        super().__init__(stt=stt, conn_options=inner._conn_options, sample_rate=16000)
        self._inner = inner
        self._state = state
        self._speech_start: float | None = None

    async def _run(self) -> None:
        async def pump_input() -> None:
            async for item in self._input_ch:
                if isinstance(item, self._FlushSentinel):
                    self._inner.flush()
                else:
                    self._inner.push_frame(item)

        pump_task = asyncio.create_task(pump_input())
        try:
            async for event in self._inner:
                # Callers only speak English/Spanish (Latin script). Deepgram's
                # multilingual model can mis-transcribe a noisy/accented utterance
                # into another language's script (e.g. Hindi/Devanagari). Drop any
                # transcript that is mostly non-Latin so the garbage never reaches
                # the LLM, the caller's transcript, or the firm dashboard.
                if event.alternatives:
                    _txt = event.alternatives[0].text or ""
                    if _txt and not _is_mostly_latin(_txt):
                        logger.info(
                            "CASEFLOW_STT dropped non-Latin transcript: %r", _txt[:60]
                        )
                        continue
                if event.type == stt.SpeechEventType.START_OF_SPEECH:
                    self._speech_start = time.perf_counter()
                    if self._state.metrics:
                        self._state.metrics.begin_turn()
                if event.type == stt.SpeechEventType.END_OF_SPEECH:
                    if self._state.metrics and self._state.metrics.current:
                        self._state.metrics.current.mark_user_speech_end()
                if (
                    event.type == stt.SpeechEventType.FINAL_TRANSCRIPT
                    and event.alternatives
                ):
                    alt = event.alternatives[0]
                    lang = resolve_caller_language(
                        stt_language=str(alt.language) if alt.language else None,
                        transcript=alt.text,
                        current=self._state.caller_language,
                    )
                    sync_caller_language(self._state, lang, tts=self._stt._tts)
                    latency_ms = (
                        (time.perf_counter() - self._speech_start) * 1000
                        if self._speech_start
                        else None
                    )
                    logger.info(
                        "CASEFLOW_STT %s",
                        json.dumps(
                            {
                                "provider": self._stt.provider,
                                "model": self._stt.model,
                                "language": lang,
                                "latency_ms": round(latency_ms or 0, 1),
                                "transcript": alt.text,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    if self._state.metrics and self._state.metrics.current:
                        self._state.metrics.current.mark_stt_final(
                            model=self._stt.model,
                            language=lang,
                            transcript=alt.text,
                        )
                self._event_ch.send_nowait(event)
        finally:
            pump_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump_task
            await self._inner.aclose()


class LoggingTTS(tts.TTS):
    """MiniMax Speech 2.8 HD with per-turn latency logging and metrics."""

    def __init__(self, *, inner: minimax.TTS, state: VoiceSessionState) -> None:
        super().__init__(
            capabilities=inner.capabilities,
            sample_rate=inner.sample_rate,
            num_channels=inner.num_channels,
        )
        self._inner = inner
        self._state = state

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def provider(self) -> str:
        return "MiniMax"

    def update_options(self, **kwargs) -> None:
        self._inner.update_options(**kwargs)

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> tts.ChunkedStream:
        return self._inner.synthesize(text, conn_options=conn_options)

    def stream(
        self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.SynthesizeStream:
        return _LoggingSynthesizeStream(
            tts=self,
            inner=self._inner.stream(conn_options=conn_options),
            state=self._state,
        )

    def prewarm(self) -> None:
        self._inner.prewarm()

    async def aclose(self) -> None:
        await self._inner.aclose()


def build_caseflow_voice(*, state: VoiceSessionState) -> tuple[LoggingTTS, minimax.TTS]:
    """MiniMax TTS with LoggingTTS observability wrapper."""
    inner = build_minimax_tts(state=state)
    return LoggingTTS(inner=inner, state=state), inner


class _LoggingSynthesizeStream(tts.SynthesizeStream):
    def __init__(
        self,
        *,
        tts: LoggingTTS,
        inner: tts.SynthesizeStream,
        state: VoiceSessionState,
    ) -> None:
        super().__init__(tts=tts, conn_options=inner._conn_options)
        self._inner = inner
        self._state = state
        self._stream_start = time.perf_counter()
        self._emitter_ready = False

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        async def pump_input() -> None:
            async for item in self._input_ch:
                if isinstance(item, self._FlushSentinel):
                    self._inner.flush()
                else:
                    self._inner.push_text(item)
            self._inner.end_input()

        pump_task = asyncio.create_task(pump_input())
        logged = False
        current_segment_id: str | None = None
        try:
            async for audio in self._inner:
                if not self._emitter_ready:
                    output_emitter.initialize(
                        request_id=audio.request_id or "caseflow-tts",
                        sample_rate=self._tts.sample_rate,
                        num_channels=self._tts.num_channels,
                        mime_type="audio/pcm",
                        stream=True,
                    )
                    self._emitter_ready = True
                seg_id = audio.segment_id or audio.request_id or "caseflow-tts"
                if current_segment_id != seg_id:
                    if current_segment_id is not None:
                        output_emitter.end_segment()
                    output_emitter.start_segment(segment_id=seg_id)
                    current_segment_id = seg_id
                if not logged:
                    logged = True
                    first_ms = (time.perf_counter() - self._stream_start) * 1000
                    voice_id = self._state.voice_id_for()
                    emotion = select_emotion(self._state.message_type)
                    if self._state.metrics and self._state.metrics.current:
                        self._state.metrics.current.mark_tts_first_audio(
                            voice_id=voice_id, emotion=emotion
                        )
                    log_tts_request(
                        provider=self._tts.provider,
                        model=self._tts.model,
                        voice_id=voice_id,
                        language=self._state.caller_language,
                        emotion=emotion,
                        text_len=len(self._pushed_text or ""),
                        first_audio_ms=first_ms,
                    )
                output_emitter.push(audio.frame.data.tobytes())
                if audio.is_final:
                    output_emitter.end_segment()
                    current_segment_id = None
        finally:
            pump_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump_task
            await self._inner.aclose()


def log_tts_request(
    *,
    voice_id: str,
    language: str,
    emotion: str,
    text_len: int,
    provider: str = "MiniMax",
    model: str | None = None,
    first_audio_ms: float | None = None,
    total_ms: float | None = None,
) -> None:
    logger.info(
        "CASEFLOW_TTS %s",
        json.dumps(
            {
                "provider": provider,
                "model": model,
                "voice_id": voice_id,
                "language": language,
                "emotion": emotion,
                "text_len": text_len,
                "first_audio_ms": round(first_audio_ms or 0, 1)
                if first_audio_ms
                else None,
                "total_generation_ms": round(total_ms or 0, 1) if total_ms else None,
            },
            ensure_ascii=False,
        ),
    )


def voice_stt_payload(
    *,
    provider: str,
    model: str,
    language: str,
    transcript: str,
    latency_ms: float | None = None,
) -> dict:
    return {
        "provider": provider,
        "model": model,
        "language": language,
        "transcript": transcript,
        "latency_ms": round(latency_ms or 0, 1) if latency_ms is not None else None,
    }


def voice_tts_payload(
    *,
    provider: str,
    model: str,
    voice_id: str,
    language: str,
    emotion: str,
    message_type: MessageType,
) -> dict:
    return {
        "provider": provider,
        "model": model,
        "voice_id": voice_id,
        "language": language,
        "emotion": emotion,
        "message_type": message_type,
    }
