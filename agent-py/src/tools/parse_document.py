"""Unsiloed document parsing — structured fields + per-field confidence + latency.

Returns a normalized dict whose top level is the parsed fields (backward compatible
with the rest of the agent) plus a ``_meta`` block carrying:

* ``source``     — unsiloed | demo_no_key | error  (real vs. canned vs. failed)
* ``status``     — parsed | error
* ``confidence`` — {field: 0..1} per-field confidence (drives the dashboard bars)
* ``low_confidence`` — fields below the verify threshold
* ``latency_ms`` / ``submit_ms`` / ``poll_ms`` — Unsiloed timing for the latency chip

Distinguishing a real error from the demo fallback (Gap 1) matters: when a key IS
configured and the call fails, we return ``status=error`` instead of silently
masquerading as demo data.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import time
from typing import Any

import httpx

logger = logging.getLogger("unsiloed")

UNSILOED_BASE = "https://prod.visionapi.unsiloed.ai"
VALID_DOC_TYPES = {"police_report", "er_discharge", "insurance"}
DOC_TYPE_ALIASES = {"insurance_letter": "insurance"}
LOW_CONFIDENCE_THRESHOLD = 0.75
POLL_INTERVAL_S = 1.5
MAX_POLLS = 20
# Unsiloed job states (GET /parse/{job_id} -> status). Real values are
# "Starting" / "Succeeded" / "Failed"; we accept synonyms defensively.
_SUCCESS_STATES = {"succeeded", "completed", "complete", "success", "done"}
_FAILED_STATES = {"failed", "error", "cancelled", "canceled"}

# Per-doc-type field confidences for the demo path. Each doc carries at least one
# intentionally lower field so the "verify with caller" UI is exercised.
_DEMO_CONFIDENCE: dict[str, dict[str, float]] = {
    "police_report": {
        "fault_determination": 0.94,
        "other_driver_claim": 0.61,
        "incident_date": 0.97,
        "location": 0.88,
        "report_number": 0.9,
    },
    "er_discharge": {
        "primary_diagnosis": 0.95,
        "imaging_ordered": 0.91,
        "discharge_instructions": 0.64,
        "visit_date": 0.97,
    },
    "insurance": {"parsed_summary": 0.7},
}


def _with_meta(
    fields: dict[str, Any],
    *,
    doc_type: str,
    source: str,
    status: str,
    confidence: dict[str, float],
    latency_ms: float = 0.0,
    submit_ms: float = 0.0,
    poll_ms: float = 0.0,
    error: str | None = None,
) -> dict[str, Any]:
    data_fields = {k: v for k, v in fields.items() if k != "doc_type"}
    low = sorted(
        k for k, v in confidence.items() if k in data_fields and v < LOW_CONFIDENCE_THRESHOLD
    )
    meta: dict[str, Any] = {
        "source": source,
        "status": status,
        "confidence": {k: round(v, 2) for k, v in confidence.items() if k in data_fields},
        "low_confidence": low,
        "latency_ms": round(latency_ms, 1),
        "submit_ms": round(submit_ms, 1),
        "poll_ms": round(poll_ms, 1),
        "field_count": len(data_fields),
    }
    if error:
        meta["error"] = error
    return {"doc_type": doc_type, **fields, "_meta": meta}


async def parse_document(image_base64: str, doc_type: str) -> dict[str, Any]:
    doc_type = DOC_TYPE_ALIASES.get(doc_type, doc_type)
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError(f"doc_type must be one of {sorted(VALID_DOC_TYPES)}")

    api_key = os.getenv("UNSILOED_API_KEY", "").strip()
    raw = image_base64.split(",", 1)[-1]
    try:
        image_bytes = base64.b64decode(raw)
    except Exception as exc:
        raise ValueError("Invalid image_base64 payload") from exc

    # No key configured: explicit demo mode (NOT an error — this is dev default).
    if not api_key:
        fields = _demo_parse(doc_type)
        logger.info("unsiloed.parse source=demo_no_key doc_type=%s", doc_type)
        return _with_meta(
            fields,
            doc_type=doc_type,
            source="demo_no_key",
            status="parsed",
            confidence=_DEMO_CONFIDENCE.get(doc_type, {}),
        )

    headers = {"api-key": api_key}
    files = {"file": (f"{doc_type}.jpg", io.BytesIO(image_bytes), "image/jpeg")}
    t0 = time.perf_counter()
    submit_ms = 0.0
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            submit = await client.post(
                f"{UNSILOED_BASE}/parse", headers=headers, files=files
            )
            submit.raise_for_status()
            submit_ms = (time.perf_counter() - t0) * 1000.0
            job_id = submit.json().get("job_id")
            if not job_id:
                raise RuntimeError("Unsiloed returned no job_id")

            poll_start = time.perf_counter()
            for _ in range(MAX_POLLS):
                await asyncio.sleep(POLL_INTERVAL_S)
                status = await client.get(
                    f"{UNSILOED_BASE}/parse/{job_id}", headers=headers
                )
                status.raise_for_status()
                body = status.json()
                state = str(body.get("status", "")).lower()
                if state in _FAILED_STATES:
                    raise RuntimeError(
                        f"Unsiloed parse failed: {body.get('message') or body.get('error') or state}"
                    )
                # Unsiloed reports success as "Succeeded"; accept common synonyms too.
                if state in _SUCCESS_STATES or body.get("chunks"):
                    poll_ms = (time.perf_counter() - poll_start) * 1000.0
                    fields, confidence = _extract_fields(body, doc_type)
                    logger.info(
                        "unsiloed.parse source=unsiloed doc_type=%s total_ms=%.0f fields=%d",
                        doc_type,
                        (time.perf_counter() - t0) * 1000.0,
                        len(fields) - 1,
                    )
                    return _with_meta(
                        fields,
                        doc_type=doc_type,
                        source="unsiloed",
                        status="parsed",
                        confidence=confidence,
                        latency_ms=(time.perf_counter() - t0) * 1000.0,
                        submit_ms=submit_ms,
                        poll_ms=poll_ms,
                    )
            raise TimeoutError(f"Unsiloed parse did not complete in {MAX_POLLS} polls")
    except Exception as exc:
        # Key was present but the call failed — surface a real error (Gap 1),
        # do NOT pretend it succeeded with demo data.
        logger.warning("unsiloed.parse FAILED doc_type=%s: %s", doc_type, exc)
        return _with_meta(
            {"doc_type": doc_type},
            doc_type=doc_type,
            source="error",
            status="error",
            confidence={},
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            submit_ms=submit_ms,
            error=str(exc)[:200],
        )


def _demo_parse(doc_type: str) -> dict[str, Any]:
    if doc_type == "police_report":
        return {
            "doc_type": "police_report",
            "fault_determination": "undetermined",
            "other_driver_claim": "claimed right of way",
            "incident_date": "2026-06-01",
            "location": "Orange County, CA",
            "report_number": "OC-2026-44102",
        }
    if doc_type == "er_discharge":
        return {
            "doc_type": "er_discharge",
            "primary_diagnosis": "whiplash / cervical strain",
            "imaging_ordered": "MRI cervical spine",
            "discharge_instructions": "follow up with PCP, rest, NSAIDs",
            "visit_date": "2026-06-01",
        }
    return {"doc_type": doc_type, "parsed_summary": "Insurance letter received."}


def _chunk_text(body: dict[str, Any]) -> str:
    """Reconstruct the document text from Unsiloed chunks/segments.

    Unsiloed returns ``chunks[].embed`` (a ready-to-embed text join) and
    ``chunks[].segments[].content/markdown/html``. Prefer ``embed``; fall back to
    joining segment text.
    """
    parts: list[str] = []
    for chunk in body.get("chunks", []) or []:
        if not isinstance(chunk, dict):
            continue
        embed = chunk.get("embed")
        if embed:
            parts.append(str(embed))
            continue
        for seg in chunk.get("segments", []) or []:
            if not isinstance(seg, dict):
                continue
            text = seg.get("content") or seg.get("markdown") or seg.get("html") or ""
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()


def _segment_confidence(body: dict[str, Any]) -> float:
    """Average segment + OCR confidence from the Unsiloed response (0..1)."""
    vals: list[float] = []
    for chunk in body.get("chunks", []) or []:
        for seg in (chunk.get("segments", []) if isinstance(chunk, dict) else []) or []:
            if not isinstance(seg, dict):
                continue
            c = seg.get("confidence")
            if isinstance(c, (int, float)):
                vals.append(float(c))
            for o in seg.get("ocr", []) or []:
                oc = o.get("confidence") if isinstance(o, dict) else None
                if isinstance(oc, (int, float)):
                    vals.append(float(oc))
    if not vals:
        return 0.8
    avg = sum(vals) / len(vals)
    return avg if avg <= 1 else avg / 100.0


def _extract_fields(
    body: dict[str, Any], doc_type: str
) -> tuple[dict[str, Any], dict[str, float]]:
    full_text = _chunk_text(body) or json.dumps(body)
    lowered = full_text.lower()
    fields: dict[str, Any] = {
        "doc_type": doc_type,
        "markdown": full_text[:4000],
        "raw_excerpt": full_text[:1200],
    }

    if doc_type == "police_report":
        if "undetermin" in lowered:
            fields["fault_determination"] = "undetermined"
        else:
            m = re.search(r"fault[^a-z0-9]{0,20}([a-z0-9 ]{3,30})", lowered)
            fields["fault_determination"] = m.group(1).strip() if m else "undetermined"
        loc = re.search(r"location[:\s]+([^\n]+)", full_text, re.I)
        if loc:
            fields["location"] = loc.group(1).strip()[:80]
        date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", full_text)
        if date:
            fields["incident_date"] = date.group(1)
        rep = re.search(r"(?:report|case)\s*(?:number|no\.?|#)?[:\s]*([A-Z]{1,4}-?\d[\w\-]+)", full_text, re.I)
        if rep:
            fields["report_number"] = rep.group(1)
        claim = re.search(r"(right of way|ran the(?: red)? light|claimed[^\n]{0,40})", lowered)
        if claim:
            fields["other_driver_claim"] = claim.group(0).strip()[:80]
    elif doc_type == "er_discharge":
        if "whiplash" in lowered or "cervical" in lowered:
            fields["primary_diagnosis"] = "whiplash / cervical strain"
        else:
            dx = re.search(r"(?:diagnosis|impression)[:\s]+([^\n]+)", full_text, re.I)
            if dx:
                fields["primary_diagnosis"] = dx.group(1).strip()[:100]
        if "mri" in lowered:
            fields["imaging_ordered"] = "MRI ordered"
        elif "x-ray" in lowered or "xray" in lowered:
            fields["imaging_ordered"] = "X-ray ordered"
        di = re.search(r"(?:discharge instructions?|follow[- ]?up)[:\s]+([^\n]+)", full_text, re.I)
        if di:
            fields["discharge_instructions"] = di.group(1).strip()[:160]
        date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", full_text)
        if date:
            fields["visit_date"] = date.group(1)
    else:
        fields["parsed_summary"] = full_text[:300] or "Insurance document received."

    base = _segment_confidence(body)
    confidence = {
        k: base for k in fields if k not in ("doc_type", "raw_excerpt", "markdown")
    }
    return fields, confidence
