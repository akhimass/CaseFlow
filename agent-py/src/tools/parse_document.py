from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
from typing import Any

import httpx

UNSILOED_BASE = "https://prod.visionapi.unsiloed.ai"
VALID_DOC_TYPES = {"police_report", "er_discharge", "insurance"}


async def parse_document(image_base64: str, doc_type: str) -> dict[str, Any]:
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError(f"doc_type must be one of {sorted(VALID_DOC_TYPES)}")

    api_key = os.getenv("UNSILOED_API_KEY", "").strip()
    raw = image_base64.split(",", 1)[-1]
    try:
        image_bytes = base64.b64decode(raw)
    except Exception as exc:
        raise ValueError("Invalid image_base64 payload") from exc

    if not api_key:
        return _demo_parse(doc_type)

    headers = {"api-key": api_key}
    files = {"file": (f"{doc_type}.jpg", io.BytesIO(image_bytes), "image/jpeg")}

    async with httpx.AsyncClient(timeout=60.0) as client:
        submit = await client.post(f"{UNSILOED_BASE}/parse", headers=headers, files=files)
        submit.raise_for_status()
        job_id = submit.json().get("job_id")
        if not job_id:
            return _demo_parse(doc_type)

        for _ in range(20):
            await asyncio.sleep(1.5)
            status = await client.get(f"{UNSILOED_BASE}/parse/{job_id}", headers=headers)
            status.raise_for_status()
            body = status.json()
            if body.get("status") == "completed":
                return _extract_fields(json.dumps(body), doc_type)
        return _demo_parse(doc_type)


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


def _extract_fields(text: str, doc_type: str) -> dict[str, Any]:
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
    return fields
