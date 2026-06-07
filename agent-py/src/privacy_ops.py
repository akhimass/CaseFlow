"""Operational vs sensitive case views — redacted persistence contract."""

from __future__ import annotations

import copy
from typing import Any

from pii_redaction import RedactionSession, Redactor, redact_json_values, sensitive_blob

OPERATIONAL_FIELD_KEYS = frozenset(
    {
        "case_id",
        "caller_id",
        "accident_type",
        "jurisdiction",
        "state",
        "language",
        "status",
        "last_event",
        "case_strength",
        "score",
        "turn",
        "doc_type",
        "field_source",
        "s3_prefix",
        "pii_redacted",
        "sensitive_blob_url",
        "consent_given_at",
        "privacy_stats",
        "updated_at",
        "timestamp",
    }
)


def build_operational_case(
    case_data: dict[str, Any],
    *,
    session: RedactionSession,
    language: str,
    consent_given_at: str | None = None,
) -> dict[str, Any]:
    redactor = Redactor(session)
    out = copy.deepcopy(case_data)

    lines = out.get("transcript_lines")
    if isinstance(lines, list):
        redacted_lines: list[dict[str, Any]] = []
        for line in lines:
            if not isinstance(line, dict):
                continue
            text = str(line.get("text") or "")
            redacted_text, _ = redactor.redact(text, language)
            redacted_lines.append({**line, "text": redacted_text})
        out["transcript_lines"] = redacted_lines

    if isinstance(out.get("transcript_line"), dict):
        tl = out["transcript_line"]
        text = str(tl.get("text") or "")
        redacted_text, _ = redactor.redact(text, language)
        out["transcript_line"] = {**tl, "text": redacted_text}

    for key, value in list(out.items()):
        if key in OPERATIONAL_FIELD_KEYS:
            continue
        if isinstance(value, str):
            out[key] = redactor.redact(value, language)[0]
        elif key == "documents" and isinstance(value, dict):
            out[key] = redact_json_values(value, session=session, language=language)

    out["pii_redacted"] = True
    out["consent_given_at"] = consent_given_at or out.get("consent_given_at")
    out["privacy_stats"] = {
        "redaction_count": session.total_redactions,
        "categories": dict(session.counts_by_category),
        "encryption": "SSE-KMS",
        "sensitive_bucket": "caseflow-sensitive",
        "consent_given_at": out.get("consent_given_at"),
        "stt_note": (
            "STT audio is not regex-redacted; production roadmap: on-device redaction "
            "or selective speaker isolation."
        ),
    }
    return out


def build_sensitive_payload(
    case_id: str,
    case_data: dict[str, Any],
    session: RedactionSession,
) -> dict[str, Any]:
    return sensitive_blob(case_id, case_data, session)
