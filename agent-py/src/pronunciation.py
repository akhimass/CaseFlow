"""Dynamic MiniMax pronunciation terms from parsed documents."""

from __future__ import annotations

from typing import Any

from livekit.plugins import minimax

from minimax_voice import VoiceSessionState, apply_tts_options, syllabify_phrase


def terms_from_parsed(doc_type: str, parsed: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for value in parsed.values():
        if not isinstance(value, str) or len(value) < 4:
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in terms:
            terms.append(cleaned)

    if doc_type == "er_discharge":
        for hint in ("whiplash", "latigazo cervical", "resonancia magnética", "MRI"):
            if hint not in terms:
                terms.append(hint)
    if doc_type == "police_report":
        for hint in ("statute of limitations", "fault determination"):
            if hint not in terms:
                terms.append(hint)
    return terms[:12]


def register_pronunciation_terms(
    state: VoiceSessionState,
    terms: list[str],
    *,
    tts: minimax.TTS | None = None,
) -> None:
    for term in terms:
        normalized = term.strip().lower()
        if not normalized or normalized in state.extra_pronunciations:
            continue
        state.extra_pronunciations[normalized] = term.strip()
    if tts is not None:
        apply_tts_options(tts, state)
