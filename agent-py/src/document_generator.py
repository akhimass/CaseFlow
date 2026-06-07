"""Real-time legal document generation during intake."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aws_s3 import save_generated_document, s3_uri
from document_auditor import audit_document
from gateway import GATEWAY_MODEL, GatewayMetadata, chat, llm_configured
from pdf_render import estimate_page_count, render_pdf_bytes
from pii_redaction import Redactor, RedactionSession

logger = logging.getLogger("document_generator")

DOC_TIMEOUT_S = float(os.getenv("DOC_GEN_TIMEOUT_S", "60"))
DEMAND_MODEL = os.getenv("OPENAI_DEMAND_MODEL", os.getenv("OPENAI_MODEL_LARGE", "gpt-4.1"))

OnDocument = Callable[[dict[str, Any]], Awaitable[None]]

INTAKE_SUMMARY_PROMPT = """\
Write an Intake Summary (~600 words) in structured markdown for a personal injury case.

Sections (use ## headings):
- Caller Information
- Accident Summary
- Documented Evidence
- Liability Assessment
- Damages and Injuries
- Statute of Limitations Status
- Comparable Settlement Range
- Recommended Next Steps

Ground every factual claim in the provided case state, parsed documents, law snippets,
and comparable settlements. Cite Moss retrieval IDs inline as [cite:<id>] exactly as given.
Do not invent facts. Use professional legal-intake tone."""

DEMAND_LETTER_PROMPT = """\
Write a Demand Letter Draft (~800 words) in legal-format markdown.

Start with a prominent blockquote:
> **DRAFT — FOR ATTORNEY REVIEW**
> This draft is for attorney review only. Do NOT send to any insurance carrier.

Structure:
- Re: line with parties
- Statement of facts (grounded in case state + parsed documents)
- Liability section
- Damages section
- Demand amount anchored to the UPPER QUARTILE of the comparable settlement range shown
- Settlement timeline (30 days standard)
- Signature block drafted as if from the matched firm

Cite Moss IDs as [cite:<id>]. Never promise outcomes. Never address an insurer directly."""

ACTION_SHEET_PROMPT = """\
Write a 24-Hour Action Sheet (~300 words) for the CALLER (not the lawyer).

Primary language: {primary_lang}. Mirror the full sheet in English below a horizontal rule.

Sections:
- What to do in the next 7 days
- What NOT to do
- Important deadlines
- Your case number: {case_id}
- How to contact your matched firm

Friendly plain language, no legal jargon. The caller's name may appear when provided.
Include [cite:<id>] only when referencing a specific law or procedure snippet."""

DOC_TYPES = {
    "intake_summary": {
        "title": "Intake Summary",
        "filename": "intake_summary",
        "model": GATEWAY_MODEL,
        "prompt": INTAKE_SUMMARY_PROMPT,
    },
    "demand_letter": {
        "title": "Demand Letter Draft",
        "filename": "demand_letter",
        "model": DEMAND_MODEL,
        "prompt": DEMAND_LETTER_PROMPT,
    },
    "action_sheet": {
        "title": "24-Hour Action Sheet",
        "filename": "action_sheet",
        "model": GATEWAY_MODEL,
        "prompt": ACTION_SHEET_PROMPT,
    },
}


def _retrieval_context(case_data: dict[str, Any]) -> dict[str, Any]:
    retrievals = case_data.get("moss_retrievals") or []
    law, comps, procs = [], [], []
    for ev in retrievals:
        ns = ev.get("namespace", "")
        snippets = ev.get("snippets") or []
        if ns == "state-law":
            law.extend(snippets)
        elif ns == "settlements":
            comps.extend(snippets)
        elif ns == "procedures":
            procs.extend(snippets)
    return {"law_snippets": law, "comparables": comps, "procedures": procs}


def _matched_firm_name(case_data: dict[str, Any]) -> str:
    matches = case_data.get("matches") or []
    if isinstance(matches, list) and matches:
        top = matches[0]
        if isinstance(top, dict):
            return str(top.get("name") or top.get("firm_id") or "Matched Firm")
    moss = case_data.get("moss_firm_matches") or []
    if moss and isinstance(moss[0], dict):
        return str(moss[0].get("name") or "Matched Firm")
    return "Matched Firm"


def _build_user_payload(case_data: dict[str, Any], *, doc_type: str) -> str:
    ctx = _retrieval_context(case_data)
    payload = {
        "case_state": {
            k: v
            for k, v in case_data.items()
            if k
            not in {
                "transcript_lines",
                "transcript_line",
                "generated_documents",
                "s3_prefix",
            }
        },
        "parsed_documents": case_data.get("documents") or {},
        "jurisdictional_law": ctx["law_snippets"],
        "comparable_settlements": ctx["comparables"],
        "procedural_guidance": ctx["procedures"],
    }
    if doc_type in {"demand_letter", "action_sheet"}:
        payload["matched_firm"] = _matched_firm_name(case_data)
    return json.dumps(payload, default=str, ensure_ascii=False)


def _unredact_for_pdf(
    markdown: str, session: RedactionSession | None, language: str
) -> str:
    if not session or not session.mapping:
        return markdown
    return Redactor(session).unredact(markdown)


async def generate_document(
    *,
    case_id: str,
    caller_id: str,
    doc_type: str,
    case_data: dict[str, Any],
    language: str = "en",
    redaction_session: RedactionSession | None = None,
    on_complete: OnDocument | None = None,
) -> dict[str, Any] | None:
    """Generate one document type; fire-and-forget safe."""
    spec = DOC_TYPES.get(doc_type)
    if not spec:
        return None

    started = datetime.now(timezone.utc)
    meta: dict[str, Any] = {
        "doc_type": doc_type,
        "title": spec["title"],
        "generated_at": started.isoformat(),
        "audit_status": "pending",
        "page_count": 0,
        "s3_path_md": None,
        "s3_path_pdf": None,
    }

    try:
        if not llm_configured():
            raise RuntimeError("No LLM configured for document generation")

        system = spec["prompt"]
        if doc_type == "action_sheet":
            primary = "Spanish" if language.startswith("es") else "English"
            system = system.format(
                primary_lang=primary, case_id=case_id
            )

        response = await asyncio.wait_for(
            chat(
                spec["model"],
                [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": _build_user_payload(case_data, doc_type=doc_type),
                    },
                ],
                temperature=0.2,
                metadata=GatewayMetadata(case_id=case_id, caller_id=caller_id),
                timeout_s=DOC_TIMEOUT_S,
                language=language,
                redaction_session=redaction_session,
            ),
            timeout=DOC_TIMEOUT_S,
        )
        markdown = response.content.strip()
        if not markdown:
            raise RuntimeError("Empty document from LLM")

        pdf_markdown = (
            _unredact_for_pdf(markdown, redaction_session, language)
            if doc_type == "action_sheet"
            else markdown
        )
        pdf_bytes = render_pdf_bytes(pdf_markdown)
        page_count = estimate_page_count(markdown)

        keys = await save_generated_document(
            case_id, spec["filename"], markdown, pdf_bytes=pdf_bytes
        )
        if keys.get("md"):
            meta["s3_path_md"] = s3_uri(str(keys["md"]))
        if keys.get("pdf"):
            meta["s3_path_pdf"] = s3_uri(str(keys["pdf"]))
        meta["page_count"] = page_count
        meta["model"] = response.model_id
        meta["provider"] = response.provider

        audit = await audit_document(
            doc_type=doc_type,
            markdown=markdown,
            case_data=case_data,
            case_id=case_id,
            caller_id=caller_id,
        )
        meta["audit_status"] = audit.get("audit_status", "pending")
        meta["audit_confidence"] = audit.get("confidence")
        meta["flagged_claims"] = audit.get("flagged_claims", [])

        if on_complete:
            await on_complete(meta)

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "Generated %s for %s in %.1fs (audit=%s)",
            doc_type,
            case_id,
            elapsed,
            meta["audit_status"],
        )
        return meta
    except asyncio.TimeoutError:
        logger.warning("Document generation timed out: %s %s", doc_type, case_id)
        meta["audit_status"] = "timeout"
        if on_complete:
            await on_complete(meta)
        return meta
    except Exception:
        logger.exception("Document generation failed: %s %s", doc_type, case_id)
        meta["audit_status"] = "error"
        if on_complete:
            await on_complete(meta)
        return None


async def generate_intake_summary(**kwargs: Any) -> dict[str, Any] | None:
    return await generate_document(doc_type="intake_summary", **kwargs)


async def generate_demand_letter(**kwargs: Any) -> dict[str, Any] | None:
    return await generate_document(doc_type="demand_letter", **kwargs)


async def generate_action_sheet(**kwargs: Any) -> dict[str, Any] | None:
    return await generate_document(doc_type="action_sheet", **kwargs)


async def generate_post_match_documents(**kwargs: Any) -> list[dict[str, Any]]:
    results = await asyncio.gather(
        generate_demand_letter(**kwargs),
        generate_action_sheet(**kwargs),
        return_exceptions=True,
    )
    out: list[dict[str, Any]] = []
    for item in results:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, Exception):
            logger.exception("Post-match doc failed", exc_info=item)
    return out
