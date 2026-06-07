"""Post-call case package — summary, firm brief, structured intake."""

from __future__ import annotations

import json
import logging
from typing import Any

from aws_s3 import (
    save_case_snapshot,
    save_firm_brief,
    save_intake_structured,
    save_verbal_summary,
    s3_configured,
)
from gateway import GATEWAY_MODEL, GatewayMetadata, chat, llm_configured

logger = logging.getLogger("post_call")

SUMMARY_MODEL = GATEWAY_MODEL


def _format_transcript(transcript_lines: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for line in transcript_lines:
        speaker = str(line.get("speaker") or "caller")
        text = str(line.get("text") or "").strip()
        if not text:
            continue
        parts.append(f"{speaker}: {text}")
    return "\n".join(parts)


async def _llm_summary(
    *,
    transcript_text: str,
    case_data: dict[str, Any],
    language: str,
    case_id: str,
    caller_id: str,
) -> tuple[str, str]:
    lang_label = "Spanish" if language.startswith("es") else "English"
    system = (
        f"You are a PI intake summarizer. Write in {lang_label}. "
        "Produce two sections separated by a line containing only ---\n"
        "Section 1: verbal_summary (3-6 sentences for the firm). "
        "Section 2: firm_brief (bullet points for a receptionist handoff)."
    )
    payload = {
        "case_data": case_data,
        "transcript": transcript_text,
        "language": language,
    }
    response = await chat(
        SUMMARY_MODEL,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
        metadata=GatewayMetadata(case_id=case_id, turn=0, caller_id=caller_id),
    )
    content = response.content.strip()
    if "---" in content:
        summary, brief = content.split("---", 1)
        return summary.strip(), brief.strip()
    return content, content


def _rules_summary(
    *,
    transcript_text: str,
    case_data: dict[str, Any],
    language: str,
) -> tuple[str, str]:
    accident = case_data.get("accident_type") or "motor vehicle accident"
    injuries = case_data.get("injuries") or "injuries being documented"
    location = case_data.get("location") or case_data.get("state") or "jurisdiction TBD"
    if language.startswith("es"):
        summary = (
            f"Intake completado. Tipo de accidente: {accident}. "
            f"Lesiones reportadas: {injuries}. Ubicación: {location}."
        )
        brief = (
            f"- Caso: {accident}\n- Lesiones: {injuries}\n"
            f"- Ubicación: {location}\n- Revisar transcript completo"
        )
    else:
        summary = (
            f"Intake completed. Accident type: {accident}. "
            f"Reported injuries: {injuries}. Location: {location}."
        )
        brief = (
            f"- Case: {accident}\n- Injuries: {injuries}\n"
            f"- Location: {location}\n- Review full transcript"
        )
    if transcript_text:
        summary += f"\n\nTranscript excerpt:\n{transcript_text[:600]}"
    return summary, brief


async def build_post_call_package(
    *,
    case_id: str,
    caller_id: str,
    case_data: dict[str, Any],
    transcript_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge transcript + fields; write summary artifacts to S3 when configured."""
    language = str(case_data.get("language") or "en")
    transcript_text = _format_transcript(transcript_lines)

    intake_structured = {
        k: v
        for k, v in case_data.items()
        if k
        not in {
            "transcript_lines",
            "transcript_line",
            "moss_retrievals",
            "moss_retrieval",
            "s3_prefix",
        }
    }
    intake_structured["transcript_line_count"] = len(transcript_lines)

    if llm_configured() and transcript_text:
        try:
            verbal_summary, firm_brief = await _llm_summary(
                transcript_text=transcript_text,
                case_data=case_data,
                language=language,
                case_id=case_id,
                caller_id=caller_id,
            )
        except Exception:
            logger.exception("LLM post-call summary failed; using rules template")
            verbal_summary, firm_brief = _rules_summary(
                transcript_text=transcript_text,
                case_data=case_data,
                language=language,
            )
    else:
        verbal_summary, firm_brief = _rules_summary(
            transcript_text=transcript_text,
            case_data=case_data,
            language=language,
        )

    package = {
        "case_id": case_id,
        "language": language,
        "intake_structured": intake_structured,
        "verbal_summary": verbal_summary,
        "firm_brief": firm_brief,
        "transcript_lines": transcript_lines,
        "documents": case_data.get("documents") or {},
    }

    if s3_configured():
        await save_intake_structured(case_id, intake_structured)
        await save_verbal_summary(case_id, verbal_summary)
        await save_firm_brief(case_id, firm_brief)
        await save_case_snapshot(
            case_id,
            {**intake_structured, "post_call": True, "verbal_summary": verbal_summary},
        )

    return package
