"""Parseable per-turn voice pipeline metrics (stdout; TrueFoundry later)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field

logger = logging.getLogger("caseflow.metrics")


@dataclass
class TurnMetrics:
    turn_id: str
    stt_final_ms: float | None = None
    llm_first_token_ms: float | None = None
    tts_first_audio_ms: float | None = None
    round_trip_ms: float | None = None
    stt_model: str | None = None
    stt_language: str | None = None
    stt_transcript: str | None = None
    tts_voice_id: str | None = None
    tts_emotion: str | None = None
    extra: dict = field(default_factory=dict)
    _user_speech_end: float | None = field(default=None, repr=False)
    _llm_start: float | None = field(default=None, repr=False)

    def mark_user_speech_end(self) -> None:
        self._user_speech_end = time.perf_counter()

    def mark_stt_final(self, *, model: str, language: str, transcript: str) -> None:
        now = time.perf_counter()
        if self._user_speech_end is not None:
            self.stt_final_ms = (now - self._user_speech_end) * 1000
        self.stt_model = model
        self.stt_language = language
        self.stt_transcript = transcript

    def mark_llm_start(self) -> None:
        self._llm_start = time.perf_counter()

    def mark_llm_first_token(self) -> None:
        if self._llm_start is not None and self.llm_first_token_ms is None:
            self.llm_first_token_ms = (time.perf_counter() - self._llm_start) * 1000

    def mark_tts_first_audio(self, *, voice_id: str, emotion: str) -> None:
        now = time.perf_counter()
        if self._llm_start is not None and self.tts_first_audio_ms is None:
            self.tts_first_audio_ms = (now - self._llm_start) * 1000
        self.tts_voice_id = voice_id
        self.tts_emotion = emotion

    def finalize(self) -> None:
        if self._user_speech_end is not None:
            self.round_trip_ms = (time.perf_counter() - self._user_speech_end) * 1000
        payload = {
            k: v
            for k, v in asdict(self).items()
            if not k.startswith("_") and v is not None
        }
        logger.info("CASEFLOW_TURN_METRICS %s", json.dumps(payload, ensure_ascii=False))


class MetricsTracker:
    def __init__(self) -> None:
        self._current: TurnMetrics | None = None
        self._counter = 0

    @property
    def current(self) -> TurnMetrics | None:
        return self._current

    def begin_turn(self) -> TurnMetrics:
        self._counter += 1
        self._current = TurnMetrics(turn_id=f"turn-{self._counter}")
        return self._current

    def end_turn(self) -> None:
        if self._current is not None:
            self._current.finalize()
            self._current = None
