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

# Unsiloed schema-based extraction (POST /v2/extract). When enabled, we hand
# Unsiloed a JSON Schema per document type and get back typed fields with real
# per-field confidence + citations — replacing regex-over-OCR. Gated + fail-safe:
# defaults OFF, and any failure/empty falls back to the proven /parse path so the
# working demo is never at risk. Flip on with UNSILOED_EXTRACT=on (or =auto).
_EXTRACT_DOC_TYPE_PROP = {
    "type": "string",
    "description": (
        "What this document actually is, one of: police_report, er_discharge, "
        "driver_license, insurance, registration, or other."
    ),
}
_EXTRACT_SCHEMAS: dict[str, dict[str, Any]] = {
    "police_report": {
        "type": "object",
        "properties": {
            "document_type": _EXTRACT_DOC_TYPE_PROP,
            "fault_determination": {
                "type": "string",
                "description": "Who was found at fault, or 'undetermined'.",
            },
            "other_driver_claim": {
                "type": "string",
                "description": "What the other driver claimed (e.g. right of way).",
            },
            "location": {"type": "string", "description": "Crash location."},
            "incident_date": {"type": "string", "description": "Date of the incident."},
            "report_number": {"type": "string", "description": "Report/case number."},
        },
    },
    "er_discharge": {
        "type": "object",
        "properties": {
            "document_type": _EXTRACT_DOC_TYPE_PROP,
            "primary_diagnosis": {
                "type": "string",
                "description": "Primary diagnosis.",
            },
            "imaging_ordered": {
                "type": "string",
                "description": "Imaging ordered (MRI, X-ray, CT).",
            },
            "discharge_instructions": {
                "type": "string",
                "description": "Discharge / follow-up instructions.",
            },
            "visit_date": {"type": "string", "description": "Visit or discharge date."},
        },
    },
    "insurance": {
        "type": "object",
        "properties": {
            "document_type": _EXTRACT_DOC_TYPE_PROP,
            "policy_number": {"type": "string", "description": "Policy number."},
            "insurer": {"type": "string", "description": "Insurance carrier name."},
            "claim_number": {"type": "string", "description": "Claim number, if any."},
        },
    },
}


def _extract_enabled() -> bool:
    val = os.getenv("UNSILOED_EXTRACT", "off").strip().lower()
    return val in {"1", "on", "true", "yes", "auto"}


# Full-page paper documents need the WHOLE sheet — on a small camera window the
# caller often can't fit it all, so the agent must ask to show the rest. Cards
# (license, registration, insurance card) fit in a single frame.
_FULL_PAGE_DOCS = {"police_report", "er_discharge", "insurance"}
_CARD_DOCS = {"driver_license", "registration", "insurance_card"}


def _form_factor(doc_type: str) -> str:
    if doc_type in _CARD_DOCS:
        return "card"
    if doc_type in _FULL_PAGE_DOCS:
        return "full_page"
    return "unknown"


LOW_CONFIDENCE_THRESHOLD = 0.75
POLL_INTERVAL_S = 1.5
# Real documents (a printed form photographed on camera) take longer to parse
# than a sparse test image — give Unsiloed enough headroom that a legitimate
# parse never hard-errors as "stuck". ~45s ceiling; most finish well under it.
MAX_POLLS = int(os.getenv("UNSILOED_MAX_POLLS", "30"))
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
        k
        for k, v in confidence.items()
        if k in data_fields and v < LOW_CONFIDENCE_THRESHOLD
    )
    meta: dict[str, Any] = {
        "source": source,
        "status": status,
        "confidence": {
            k: round(v, 2) for k, v in confidence.items() if k in data_fields
        },
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

    # Schema-based extraction (opt-in). Try Unsiloed /v2/extract for typed fields
    # with real per-field confidence; on ANY failure fall through to /parse so the
    # proven path always backs it up.
    if _extract_enabled() and doc_type in _EXTRACT_SCHEMAS:
        try:
            return await extract_document_schema(image_base64, doc_type)
        except Exception as exc:
            logger.warning(
                "unsiloed.extract fell back to /parse doc_type=%s: %s", doc_type, exc
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


def _extract_score(obj: dict[str, Any]) -> float:
    """Per-field confidence from an Unsiloed extract result entry.

    Unsiloed returns ``score: {grounding_score, extraction_score}``. We take the
    stronger of the two; when a value was extracted we floor it at 0.6 so a
    correctly-pulled field isn't shown as low-confidence purely because the
    absolute score scale runs conservative.
    """
    score = obj.get("score") if isinstance(obj, dict) else None
    grounding = extraction = 0.0
    if isinstance(score, dict):
        grounding = float(score.get("grounding_score") or 0.0)
        extraction = float(score.get("extraction_score") or 0.0)
    elif isinstance(score, (int, float)):
        extraction = float(score)
    conf = max(grounding, extraction)
    has_value = (
        bool(str(obj.get("value") or "").strip()) if isinstance(obj, dict) else False
    )
    if has_value and conf < 0.6:
        conf = 0.6
    return round(min(conf, 1.0), 2)


def _map_extract_result(
    result: dict[str, Any], doc_type: str
) -> tuple[dict[str, Any], dict[str, float]]:
    """Map an Unsiloed /v2/extract result into (fields, confidence)."""
    detected_raw = ""
    dt = result.get("document_type")
    if isinstance(dt, dict):
        detected_raw = str(dt.get("value") or "").strip().lower().replace(" ", "_")

    effective = doc_type
    unexpected = False
    known = set(VALID_DOC_TYPES) | _CARD_DOCS | {"other"}
    if detected_raw in known and detected_raw not in {"other", doc_type}:
        effective = detected_raw
        unexpected = True

    fields: dict[str, Any] = {"doc_type": effective}
    confidence: dict[str, float] = {}
    value_parts: list[str] = []
    for key, obj in result.items():
        if key == "document_type" or not isinstance(obj, dict):
            continue
        value = str(obj.get("value") or "").strip()
        if not value:
            continue
        fields[key] = value
        confidence[key] = _extract_score(obj)
        value_parts.append(f"{key}: {value}")

    if unexpected:
        fields["unexpected_document"] = True
        fields["requested_doc_type"] = doc_type
        if effective == "driver_license" and "parsed_summary" not in fields:
            fields["parsed_summary"] = "Driver's license (identity document)"

    full_text = "\n".join(value_parts)
    fields["raw_excerpt"] = full_text[:1200]
    fields["form_factor"] = _form_factor(effective)
    complete = _capture_complete(effective, full_text, fields)
    fields["capture_complete"] = complete
    if not complete:
        fields["capture_guidance"] = (
            "Only part of this full-page document was captured — ask the caller to "
            "show the rest of the page, holding it steady and filling the frame."
        )
    return fields, confidence


async def extract_document_schema(image_base64: str, doc_type: str) -> dict[str, Any]:
    """Schema-based extraction via Unsiloed /v2/extract. Returns the _with_meta dict.

    Raises on any failure so the caller can fall back to the /parse path.
    """
    api_key = os.getenv("UNSILOED_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("UNSILOED_API_KEY not set")
    schema = _EXTRACT_SCHEMAS.get(doc_type)
    if not schema:
        raise ValueError(f"No extract schema for {doc_type}")

    raw = image_base64.split(",", 1)[-1]
    image_bytes = base64.b64decode(raw)
    headers = {"api-key": api_key}
    files = {"pdf_file": (f"{doc_type}.jpg", io.BytesIO(image_bytes), "image/jpeg")}
    data = {"schema_data": json.dumps(schema), "enable_citations": "true"}

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=60.0) as client:
        submit = await client.post(
            f"{UNSILOED_BASE}/v2/extract", headers=headers, files=files, data=data
        )
        submit.raise_for_status()
        submit_ms = (time.perf_counter() - t0) * 1000.0
        job_id = submit.json().get("job_id")
        if not job_id:
            raise RuntimeError("Unsiloed extract returned no job_id")

        poll_start = time.perf_counter()
        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL_S)
            status = await client.get(
                f"{UNSILOED_BASE}/extract/{job_id}", headers=headers
            )
            status.raise_for_status()
            body = status.json()
            state = str(body.get("status", "")).lower()
            if state in _FAILED_STATES:
                raise RuntimeError(f"Unsiloed extract failed: {state}")
            result = body.get("result")
            if state in _SUCCESS_STATES or result:
                if not isinstance(result, dict) or not result:
                    raise RuntimeError("Unsiloed extract returned no result")
                fields, confidence = _map_extract_result(result, doc_type)
                if len([k for k in fields if k not in _NON_FIELD_KEYS]) == 0:
                    raise RuntimeError("Unsiloed extract returned no usable fields")
                logger.info(
                    "unsiloed.extract source=unsiloed_extract doc_type=%s total_ms=%.0f fields=%d",
                    doc_type,
                    (time.perf_counter() - t0) * 1000.0,
                    len(confidence),
                )
                return _with_meta(
                    fields,
                    doc_type=fields.get("doc_type", doc_type),
                    source="unsiloed_extract",
                    status="parsed",
                    confidence=confidence,
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                    submit_ms=submit_ms,
                    poll_ms=(time.perf_counter() - poll_start) * 1000.0,
                )
        raise TimeoutError(f"Unsiloed extract did not complete in {MAX_POLLS} polls")


# Keys present in a fields dict that are not extracted document fields.
_NON_FIELD_KEYS = {
    "doc_type",
    "raw_excerpt",
    "markdown",
    "unexpected_document",
    "requested_doc_type",
    "form_factor",
    "capture_complete",
    "capture_guidance",
    "parsed_summary",
}


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


# Keyword signals to detect what the caller ACTUALLY held up, so a driver's
# license isn't mislabeled as the police report the agent happened to ask for.
_DOC_SIGNALS: dict[str, tuple[str, ...]] = {
    "driver_license": (
        "driver license",
        "driver's license",
        "drivers license",
        "driver licence",
        "dmv",
        "department of motor vehicles",
        "class c",
        "class d",
        "donor",
        "veteran",
        "dl no",
        "lic#",
        "endorsements",
        "restrictions",
        "hgt",
        "wgt",
        "eyes",
        "hair",
        "date of birth",
        "issued",
        "expires",
    ),
    "police_report": (
        "collision",
        "traffic collision",
        "police",
        "officer",
        "incident report",
        "accident report",
        "case number",
        "report number",
        "party 1",
        "party 2",
        "vehicle 1",
        "vehicle 2",
        "fault",
        "citation",
        "at fault",
        "right of way",
    ),
    "er_discharge": (
        "discharge",
        "diagnosis",
        "patient",
        "hospital",
        "emergency department",
        "discharge instructions",
        "mrn",
        "physician",
        "chief complaint",
        "triage",
        "whiplash",
    ),
    "insurance": (
        "policy number",
        "insurance",
        "claim number",
        "coverage",
        "declarations",
        "premium",
        "insured",
        "adjuster",
        "policyholder",
    ),
    "registration": (
        "registration",
        "vehicle registration",
        "registered owner",
        "license plate",
        "plate no",
        "vin",
        "make/model",
        "reg exp",
    ),
}


def _capture_complete(doc_type: str, full_text: str, fields: dict[str, Any]) -> bool:
    """Heuristic: did we likely capture the WHOLE document?

    Cards are small and fit in one frame. Full-page docs (police report, ER
    discharge) on a small camera window are often shown only in part — flag that
    so the agent asks the caller to show the rest of the page.
    """
    if _form_factor(doc_type) != "full_page":
        return True
    if len(full_text) < 250:
        return False
    ignore = {
        "doc_type",
        "markdown",
        "raw_excerpt",
        "parsed_summary",
        "unexpected_document",
        "requested_doc_type",
        "form_factor",
        "capture_complete",
        "capture_guidance",
    }
    substantive = [k for k in fields if k not in ignore]
    return len(substantive) >= 2


def _doc_scores(lowered: str) -> dict[str, int]:
    return {t: sum(1 for s in sigs if s in lowered) for t, sigs in _DOC_SIGNALS.items()}


def _extract_fields(
    body: dict[str, Any], doc_type: str
) -> tuple[dict[str, Any], dict[str, float]]:
    full_text = _chunk_text(body) or json.dumps(body)
    lowered = full_text.lower()

    # Detect the document the caller actually showed. Only override the requested
    # type when the detected type clearly dominates (>=2 hits and beats the
    # requested type by 2+), so a genuine police report is never relabeled.
    scores = _doc_scores(lowered)
    detected = max(scores, key=lambda t: scores[t])
    effective = doc_type
    unexpected = False
    if (
        detected != doc_type
        and scores[detected] >= 2
        and scores[detected] > scores.get(doc_type, 0) + 1
    ):
        effective = detected
        unexpected = True

    fields: dict[str, Any] = {
        "doc_type": effective,
        "markdown": full_text[:4000],
        "raw_excerpt": full_text[:1200],
    }
    if unexpected:
        fields["unexpected_document"] = True
        fields["requested_doc_type"] = doc_type

    if effective == "driver_license":
        fields["parsed_summary"] = "Driver's license (identity document)"
    elif effective == "police_report":
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
        rep = re.search(
            r"(?:report|case)\s*(?:number|no\.?|#)?[:\s]*([A-Z]{1,4}-?\d[\w\-]+)",
            full_text,
            re.I,
        )
        if rep:
            fields["report_number"] = rep.group(1)
        claim = re.search(
            r"(right of way|ran the(?: red)? light|claimed[^\n]{0,40})", lowered
        )
        if claim:
            fields["other_driver_claim"] = claim.group(0).strip()[:80]
    elif effective == "er_discharge":
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
        di = re.search(
            r"(?:discharge instructions?|follow[- ]?up)[:\s]+([^\n]+)", full_text, re.I
        )
        if di:
            fields["discharge_instructions"] = di.group(1).strip()[:160]
        date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", full_text)
        if date:
            fields["visit_date"] = date.group(1)
    else:
        fields["parsed_summary"] = full_text[:300] or "Insurance document received."

    # Form factor + completeness so the agent knows full-page paper docs may need
    # the caller to show the rest of the sheet on a small camera window.
    fields["form_factor"] = _form_factor(effective)
    complete = _capture_complete(effective, full_text, fields)
    fields["capture_complete"] = complete
    if not complete:
        fields["capture_guidance"] = (
            "Only part of this full-page document was captured — ask the caller to "
            "show the rest of the page (e.g. the lower half), holding it steady and "
            "filling the camera frame."
        )

    base = _segment_confidence(body)
    _skip = (
        "doc_type",
        "raw_excerpt",
        "markdown",
        "unexpected_document",
        "requested_doc_type",
        "form_factor",
        "capture_complete",
        "capture_guidance",
    )
    confidence = {k: base for k in fields if k not in _skip}
    return fields, confidence
