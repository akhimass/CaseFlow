"""Detect when a caller mentions a document and map to Unsiloed doc types."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

DOC_COOLDOWN_S = 45.0

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "police_report",
        re.compile(
            r"(police report|reporte policial|parte policial|informe policial|"
            r"accident report|reporte de accidente|informe de tránsito|informe de transito)",
            re.I,
        ),
    ),
    (
        "er_discharge",
        re.compile(
            r"(er discharge|discharge papers|hospital discharge|alta del hospital|"
            r"alta médica|alta medica|urgencias|emergency room|er visit|"
            r"papeles del hospital|notas del hospital)",
            re.I,
        ),
    ),
    (
        "insurance",
        re.compile(
            r"(insurance letter|insurance card|carta del seguro|seguro|"
            r"insurance paperwork|tarjeta del seguro|claim letter)",
            re.I,
        ),
    ),
]


@dataclass
class DocumentIntent:
    doc_type: str
    matched_phrase: str


def detect_document_intent(transcript: str) -> DocumentIntent | None:
    text = transcript.strip()
    if not text:
        return None
    for doc_type, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            return DocumentIntent(doc_type=doc_type, matched_phrase=match.group(0))
    return None


class DocumentCaptureCoordinator:
    """Avoid duplicate Unsiloed captures for the same doc type."""

    def __init__(self) -> None:
        self._last_capture: dict[str, float] = {}

    def should_capture(self, doc_type: str) -> bool:
        now = time.monotonic()
        last = self._last_capture.get(doc_type, 0.0)
        if now - last < DOC_COOLDOWN_S:
            return False
        self._last_capture[doc_type] = now
        return True
