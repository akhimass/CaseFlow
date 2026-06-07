"""Supabase persistence — cases, documents, audit logs, transcript storage."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("supabase_store")


def _configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _base() -> str:
    return f"{os.getenv('SUPABASE_URL', '').rstrip('/')}/rest/v1"


async def upsert_case(
    case_id: str,
    fields: dict[str, Any],
    *,
    caller_id: str,
    sensitive_blob_url: str | None = None,
) -> None:
    if not _configured():
        logger.debug("Supabase not configured — skipping case upsert")
        return

    if not _is_uuid(case_id):
        logger.warning("Skipping Supabase case upsert — case_id is not a UUID: %s", case_id)
        return

    intake_json = {k: v for k, v in fields.items() if k not in {"transcript_lines"}}
    privacy_stats = fields.get("privacy_stats") if isinstance(fields.get("privacy_stats"), dict) else {}
    row = {
        "id": case_id,
        "caller_id": caller_id,
        "language": fields.get("language"),
        "accident_type": fields.get("accident_type"),
        "jurisdiction": fields.get("state") or fields.get("jurisdiction"),
        "case_strength": fields.get("score") or fields.get("case_strength"),
        "status": fields.get("status", "intake"),
        "intake_json": intake_json,
        "pii_redacted": fields.get("pii_redacted", True),
        "sensitive_blob_url": sensitive_blob_url or fields.get("sensitive_blob_url"),
        "consent_given_at": fields.get("consent_given_at"),
        "caller_location": fields.get("caller_location") or fields.get("location"),
        "matched_firm_id": fields.get("matched_firm_id"),
        "privacy_stats": privacy_stats,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    headers = {
        **_headers(),
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{_base()}/cases?on_conflict=id",
                headers=headers,
                json=row,
            )
    except Exception:
        logger.exception("Supabase case upsert failed")


async def append_transcript_line(
    case_id: str,
    *,
    speaker: str,
    text: str,
    language: str = "en",
) -> None:
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "speaker": speaker,
        "text": text,
        "language": language,
    }
    await write_audit(
        case_id=case_id,
        event_type="transcript_line",
        actor="livekit",
        payload=line,
    )


async def save_generated_document_meta(
    case_id: str,
    *,
    doc_type: str,
    s3_path_md: str | None,
    s3_path_pdf: str | None,
    generated_at: str,
    audit_status: str = "pending",
    page_count: int | None = None,
    audit_confidence: int | None = None,
    flagged_claims: list[dict[str, Any]] | None = None,
) -> None:
    if not _configured() or not _is_uuid(case_id):
        return
    row = {
        "case_id": case_id,
        "doc_type": doc_type,
        "parsed_fields": {},
        "s3_path_md": s3_path_md,
        "s3_path_pdf": s3_path_pdf,
        "generated_at": generated_at,
        "audit_status": audit_status,
        "page_count": page_count,
        "audit_confidence": audit_confidence,
        "flagged_claims": flagged_claims or [],
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{_base()}/documents", headers=_headers(), json=row)
    except Exception:
        logger.exception("Supabase generated document save failed")


async def save_firm_matches(case_id: str, result: dict[str, Any]) -> None:
    if not _configured() or not _is_uuid(case_id):
        return
    matches = result.get("matches") or []
    matched_firm_id = result.get("matched_firm_id")
    rows = [
        {
            "case_id": case_id,
            "firm_id": match.get("firm_id"),
            "score": match.get("score"),
            "reasoning": match.get("reasoning"),
            "status": "matched",
        }
        for match in matches
        if match.get("firm_id")
    ]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if rows:
                await client.post(f"{_base()}/matches", headers=_headers(), json=rows)
            if matched_firm_id:
                await client.patch(
                    f"{_base()}/cases?id=eq.{case_id}",
                    headers=_headers(),
                    json={"matched_firm_id": matched_firm_id},
                )
    except Exception:
        logger.exception("Supabase firm match save failed")


async def save_document(
    case_id: str,
    doc_type: str,
    parsed_fields: dict[str, Any],
) -> None:
    if not _configured() or not _is_uuid(case_id):
        return
    row = {
        "case_id": case_id,
        "doc_type": doc_type,
        "parsed_fields": parsed_fields,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{_base()}/documents", headers=_headers(), json=row)
    except Exception:
        logger.exception("Supabase document save failed")


async def delete_case_rows(case_id: str) -> None:
    if not _configured() or not _is_uuid(case_id):
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.delete(
                f"{_base()}/audit_log?case_id=eq.{case_id}",
                headers=_headers(),
            )
            await client.delete(
                f"{_base()}/documents?case_id=eq.{case_id}",
                headers=_headers(),
            )
            await client.delete(
                f"{_base()}/matches?case_id=eq.{case_id}",
                headers=_headers(),
            )
            await client.delete(
                f"{_base()}/cases?id=eq.{case_id}",
                headers=_headers(),
            )
    except Exception:
        logger.exception("Supabase case delete failed for %s", case_id)


async def set_consent(case_id: str, *, caller_id: str, consent_given_at: str) -> None:
    if not _configured() or not _is_uuid(case_id):
        return
    row = {
        "id": case_id,
        "caller_id": caller_id,
        "consent_given_at": consent_given_at,
        "status": "consent",
        "intake_json": {},
    }
    headers = {**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{_base()}/cases?on_conflict=id", headers=headers, json=row)
            await write_audit(
                case_id=case_id,
                event_type="consent_given",
                actor="caller",
                payload={"consent_given_at": consent_given_at},
            )
    except Exception:
        logger.exception("Supabase consent write failed")


async def write_audit(
    *,
    case_id: str = "",
    event_type: str,
    actor: str = "",
    model_id: str = "",
    payload: dict[str, Any] | None = None,
    latency_ms: int | None = None,
    cost_usd: float | None = None,
) -> None:
    if not _configured():
        return
    row = {
        "case_id": case_id or None,
        "event_type": event_type,
        "actor": actor or None,
        "model_id": model_id or None,
        "payload": payload or {},
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{_base()}/audit_log", headers=_headers(), json=row)
    except Exception:
        logger.debug("Supabase audit write skipped")


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


class TranscriptBuffer:
    """Buffer transcript lines; flush every N seconds or on call end."""

    def __init__(self, case_id: str, flush_interval_s: float = 5.0) -> None:
        self.case_id = case_id
        self.flush_interval_s = flush_interval_s
        self._lines: list[dict[str, Any]] = []
        self._last_flush = datetime.now(timezone.utc).timestamp()

    def add(self, speaker: str, text: str, language: str = "en") -> None:
        self._lines.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "speaker": speaker,
                "text": text,
                "language": language,
            }
        )

    async def maybe_flush(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        if now - self._last_flush < self.flush_interval_s:
            return
        await self.flush()

    async def flush(self) -> None:
        if not self._lines:
            return
        payload = {"lines": self._lines, "case_id": self.case_id}
        await write_audit(
            case_id=self.case_id,
            event_type="transcript_flush",
            actor="caseflow",
            payload=payload,
        )
        self._lines = []
        self._last_flush = datetime.now(timezone.utc).timestamp()
