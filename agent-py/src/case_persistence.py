"""Unified case persistence — Supabase + AWS S3."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aws_s3 import (
    S3TranscriptBuffer,
    save_case_snapshot,
    save_consistency_audit,
    save_firm_brief,
    save_match_result,
    save_parsed_document,
    save_sensitive_case_blob,
    s3_configured,
    s3_uri,
)
from pii_redaction import RedactionSession, redact_json_values
from privacy_ops import build_operational_case, build_sensitive_payload
from supabase_store import TranscriptBuffer as SupabaseTranscriptBuffer
from supabase_store import (
    save_document,
    save_generated_document_meta,
    upsert_case,
    write_audit,
)

logger = logging.getLogger("case_persistence")


class CasePersistence:
    def __init__(
        self,
        case_id: str,
        caller_id: str,
        *,
        redaction_session: RedactionSession | None = None,
        language: str = "en",
        consent_given_at: str | None = None,
    ) -> None:
        self.case_id = case_id
        self.caller_id = caller_id
        self._session = redaction_session or RedactionSession()
        self._language = language
        self._consent_given_at = consent_given_at
        self._sensitive_blob_url: str | None = None
        self._s3_buffer = S3TranscriptBuffer(case_id) if s3_configured() else None
        self._sb_buffer = SupabaseTranscriptBuffer(case_id)

    def set_language(self, language: str) -> None:
        self._language = language

    def _operational(self, fields: dict[str, Any]) -> dict[str, Any]:
        return build_operational_case(
            fields,
            session=self._session,
            language=self._language,
            consent_given_at=self._consent_given_at,
        )

    async def _persist_sensitive(self, full_fields: dict[str, Any]) -> str | None:
        if not s3_configured():
            return self._sensitive_blob_url
        payload = build_sensitive_payload(self.case_id, full_fields, self._session)
        url = await save_sensitive_case_blob(self.case_id, payload)
        if url:
            self._sensitive_blob_url = url
        return url

    async def on_case_update(
        self, event: str, fields: dict[str, Any], *, full_fields: dict[str, Any] | None = None
    ) -> dict[str, str]:
        """Persist redacted operational data + sensitive blob."""
        artifacts: dict[str, str] = {}
        operational = self._operational(full_fields or fields)
        sensitive_url = await self._persist_sensitive(full_fields or fields)

        async def _work() -> None:
            await upsert_case(
                self.case_id,
                operational,
                caller_id=self.caller_id,
                sensitive_blob_url=sensitive_url,
            )
            await write_audit(
                case_id=self.case_id,
                event_type=event,
                actor="agent",
                payload=operational,
            )
            if s3_configured():
                key = await save_case_snapshot(
                    self.case_id, {**operational, "event": event}
                )
                if key:
                    artifacts["snapshot"] = s3_uri(key)

        asyncio.create_task(_work())
        return artifacts

    async def on_transcript_line(
        self, speaker: str, text: str, language: str, turn: int
    ) -> None:
        from pii_redaction import Redactor

        redactor = Redactor(self._session)
        redacted_text, _ = redactor.redact(text, language or self._language)

        self._sb_buffer.add(speaker, redacted_text, language)
        if self._s3_buffer:
            self._s3_buffer.add(speaker, redacted_text, language, turn=turn)

        async def _flush() -> None:
            await self._sb_buffer.maybe_flush()
            if self._s3_buffer:
                await self._s3_buffer.maybe_flush()

        asyncio.create_task(_flush())

    async def on_document_parsed(self, doc_type: str, parsed: dict[str, Any]) -> None:
        redacted = redact_json_values(
            parsed, session=self._session, language=self._language
        )

        async def _work() -> None:
            await save_document(self.case_id, doc_type, redacted)
            if s3_configured():
                await save_parsed_document(self.case_id, doc_type, redacted)

        asyncio.create_task(_work())

    async def on_consistency_audit(self, audit: dict[str, Any]) -> None:
        redacted = redact_json_values(
            audit, session=self._session, language=self._language
        )

        async def _work() -> None:
            await write_audit(
                case_id=self.case_id,
                event_type="consistency_audit",
                actor=audit.get("llm_model", "qwen-max"),
                payload=redacted,
            )
            if s3_configured():
                await save_consistency_audit(self.case_id, redacted)

        asyncio.create_task(_work())

    async def on_firms_matched(self, result: dict[str, Any]) -> None:
        async def _work() -> None:
            from supabase_store import save_firm_matches

            await save_firm_matches(self.case_id, result)
            if s3_configured():
                redacted = redact_json_values(
                    result, session=self._session, language=self._language
                )
                await save_match_result(self.case_id, redacted)

        asyncio.create_task(_work())

    async def on_firm_brief(self, brief: str) -> None:
        from pii_redaction import Redactor

        redacted, _ = Redactor(self._session).redact(brief, self._language)

        async def _work() -> None:
            if s3_configured():
                await save_firm_brief(self.case_id, redacted)

        asyncio.create_task(_work())

    async def on_generated_document(self, meta: dict[str, Any]) -> None:
        async def _work() -> None:
            await save_generated_document_meta(
                self.case_id,
                doc_type=str(meta.get("doc_type") or ""),
                s3_path_md=meta.get("s3_path_md"),
                s3_path_pdf=meta.get("s3_path_pdf"),
                generated_at=str(meta.get("generated_at") or ""),
                audit_status=str(meta.get("audit_status") or "pending"),
                page_count=meta.get("page_count"),
                audit_confidence=meta.get("audit_confidence"),
                flagged_claims=meta.get("flagged_claims"),
            )
            await write_audit(
                case_id=self.case_id,
                event_type="document_generated",
                actor="document_generator",
                payload={
                    k: meta.get(k)
                    for k in (
                        "doc_type",
                        "title",
                        "audit_status",
                        "page_count",
                        "s3_path_md",
                        "s3_path_pdf",
                    )
                },
            )

        asyncio.create_task(_work())

    async def flush_all(self) -> None:
        await self._sb_buffer.flush()
        if self._s3_buffer:
            await self._s3_buffer.flush()
