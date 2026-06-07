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
                if body.get("status") == "completed":
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


def _find_confidence(body: Any) -> float | None:
    """Best-effort pull of an overall confidence/score from an Unsiloed response."""
    if isinstance(body, dict):
        for key in ("confidence", "score", "grade", "avg_confidence"):
            val = body.get(key)
            if isinstance(val, (int, float)):
                return float(val) if val <= 1 else float(val) / 100.0
        for v in body.values():
            found = _find_confidence(v)
            if found is not None:
                return found
    elif isinstance(body, list):
        for v in body:
            found = _find_confidence(v)
            if found is not None:
                return found
    return None


def _extract_fields(
    body: dict[str, Any], doc_type: str
) -> tuple[dict[str, Any], dict[str, float]]:
    text = json.dumps(body)
    lowered = text.lower()
    fields: dict[str, Any] = {"doc_type": doc_type, "raw_excerpt": text[:1200]}
    if "undetermined" in lowered or "fault" in lowered:
        match = re.search(r"fault[^a-z]{0,20}(\w+)", lowered)
        fields["fault_determination"] = match.group(1) if match else "undetermined"
    if "whiplash" in lowered or "cervical" in lowered:
        fields["primary_diagnosis"] = "whiplash / cervical strain"
    if "mri" in lowered:
        fields["imaging_ordered"] = "MRI ordered"
    if doc_type == "police_report" and not fields.get("fault_determination"):
        fields["fault_determination"] = "undetermined"

    # Confidence: use Unsiloed's score if present, else a moderate heuristic.
    base = _find_confidence(body) or 0.8
    confidence = {
        k: base for k in fields if k not in ("doc_type", "raw_excerpt")
    }
    return fields, confidence
