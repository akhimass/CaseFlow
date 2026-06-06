"""Caseflow intake helpers: parsing, consistency, scoring, matching."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
from typing import Any

import httpx

from sol_lookup import check_sol

UNSILOED_BASE = "https://prod.visionapi.unsiloed.ai"

FIRM_RULES = [
    {
        "firm_id": "martinez",
        "name": "Martinez & Associates",
        "phone": "(714) 555-0142",
        "jurisdictions": {"CA"},
        "languages": {"en", "es"},
        "specialties": {"auto", "rear_end", "mva"},
        "min_strength": 40,
    },
    {
        "firm_id": "brennan",
        "name": "Brennan Law",
        "phone": "(310) 555-0198",
        "jurisdictions": {"CA"},
        "languages": {"en"},
        "specialties": {"motorcycle", "auto", "mva"},
        "min_strength": 55,
    },
    {
        "firm_id": "reyes",
        "name": "Reyes Injury Law",
        "phone": "(619) 555-0167",
        "jurisdictions": {"CA"},
        "languages": {"en", "es"},
        "specialties": {"slip_fall", "premises", "auto", "mva"},
        "min_strength": 45,
    },
    {
        "firm_id": "patel",
        "name": "Patel Personal Injury",
        "phone": "(415) 555-0133",
        "jurisdictions": {"CA"},
        "languages": {"en", "es", "hi"},
        "specialties": {"general_pi", "auto", "mva", "pedestrian"},
        "min_strength": 35,
    },
    {
        "firm_id": "cohen",
        "name": "Cohen Law Group",
        "phone": "(800) 555-0171",
        "jurisdictions": {"CA"},
        "languages": {"en"},
        "specialties": {"high_value"},
        "min_strength": 75,
    },
]


def _normalize_case_type(case_type: str) -> str:
    value = (case_type or "mva").lower().replace(" ", "_")
    if "rear" in value or "auto" in value or "mva" in value:
        return "mva"
    if "slip" in value or "fall" in value or "premises" in value:
        return "slip_fall"
    if "motorcycle" in value:
        return "motorcycle"
    return value


async def parse_document_unsiloed(
    image_base64: str, doc_type: str
) -> dict[str, Any]:
    """Parse a held-up document via Unsiloed, with demo fallback."""
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
                text = json.dumps(body)
                return _extract_fields_from_text(text, doc_type)
        return _demo_parse(doc_type)


def _demo_parse(doc_type: str) -> dict[str, Any]:
    """Deterministic demo fields for Maria Delgado scenario."""
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
    return {"doc_type": doc_type, "parsed_summary": "Document received; manual review needed."}


def _extract_fields_from_text(text: str, doc_type: str) -> dict[str, Any]:
    lowered = text.lower()
    fields: dict[str, Any] = {"doc_type": doc_type, "raw_excerpt": text[:1200]}
    if "undetermined" in lowered or "fault" in lowered:
        match = re.search(r"fault[^a-z]{0,20}(\w+)", lowered)
        fields["fault_determination"] = match.group(1) if match else "undetermined"
    if "whiplash" in lowered or "cervical" in lowered:
        fields["primary_diagnosis"] = "whiplash / cervical strain"
    if "mri" in lowered:
        fields["imaging_ordered"] = "MRI ordered"
    if not fields.get("fault_determination") and doc_type == "police_report":
        fields["fault_determination"] = "undetermined"
    return fields


def check_consistency(
    field_name: str,
    verbal_claim: str,
    parsed_value: str,
    language: str = "en",
) -> dict[str, Any]:
    """Detect verbal vs document conflicts and return a clarifying question."""
    verbal = verbal_claim.lower()
    parsed = parsed_value.lower()
    conflict = False
    reason = ""

    if field_name == "fault_claim":
        if ("red light" in verbal or "semáforo" in verbal or "luz roja" in verbal) and (
            "undetermined" in parsed or "undetermin" in parsed
        ):
            conflict = True
            reason = "Caller claims clear fault; police report lists fault as undetermined."

    if not conflict and verbal and parsed and verbal not in parsed and parsed not in verbal:
        if field_name in {"fault_claim", "incident_description"}:
            conflict = True
            reason = f"Verbal account differs from parsed {field_name}."

    if not conflict:
        return {"conflict": False, "clarifying_question": None, "reason": None}

    if language.startswith("es"):
        question = (
            "Gracias por explicarme lo que pasó. En el reporte policial aparece que "
            "la culpa quedó sin determinar, aunque usted mencionó que el otro conductor "
            "pasó en rojo. ¿Pudo ver usted directamente que se pasó el semáforo, o lo "
            "supone por cómo ocurrió el choque?"
        )
    else:
        question = (
            "Thank you for explaining what happened. The police report lists fault as "
            "undetermined, though you mentioned the other driver ran the red light. "
            "Did you personally see them run the light, or are you inferring that from "
            "how the crash happened?"
        )

    return {"conflict": True, "clarifying_question": question, "reason": reason}


def compute_case_strength(case_data: dict[str, Any]) -> dict[str, Any]:
    """Score case strength 0-100 from intake fields."""
    score = 50
    factors: list[str] = []

    state = (case_data.get("state") or case_data.get("jurisdiction") or "").upper()
    accident_date = case_data.get("accident_date") or case_data.get("incident_date")
    if state and accident_date:
        sol = check_sol(state, str(accident_date)[:10])
        if sol["viable"]:
            if sol["days_remaining"] < 90:
                score += 5
                factors.append("SOL window closing — urgency")
            else:
                score += 10
                factors.append("SOL viable")
        else:
            score -= 40
            factors.append("SOL expired")

    fault = str(case_data.get("fault_determination") or case_data.get("fault_claim") or "")
    if "undetermined" in fault.lower():
        score -= 10
        factors.append("Liability unclear on police report")
    elif fault:
        score += 10
        factors.append("Liability indicators present")

    injuries = str(case_data.get("injuries") or case_data.get("primary_diagnosis") or "")
    if injuries and injuries.lower() not in {"none", "none reported", ""}:
        score += 15
        factors.append("Documented injuries")
    if case_data.get("imaging_ordered") or "mri" in injuries.lower():
        score += 10
        factors.append("Imaging ordered or completed")

    if case_data.get("has_prior_representation"):
        score -= 50
        factors.append("Prior representation — conflict")

    score = max(0, min(100, score))
    return {"score": score, "factors": factors}


def match_firm(case_data: dict[str, Any], caller_location: str = "") -> dict[str, Any]:
    """Rules-based firm matching — top 3 with reasoning."""
    strength = compute_case_strength(case_data)["score"]
    state = (case_data.get("state") or caller_location or "CA").upper()[:2]
    language = (case_data.get("language") or "en").lower()
    lang_code = "es" if language.startswith("es") else "en"
    case_type = _normalize_case_type(str(case_data.get("accident_type") or "mva"))

    ranked: list[dict[str, Any]] = []
    for firm in FIRM_RULES:
        if state not in firm["jurisdictions"]:
            continue
        if strength < firm["min_strength"] and firm["firm_id"] == "cohen":
            continue
        if lang_code not in firm["languages"] and firm["firm_id"] != "patel":
            continue
        match_score = strength
        reasons: list[str] = []
        if case_type in firm["specialties"] or "general_pi" in firm["specialties"]:
            match_score += 15
            reasons.append(f"Specialty fit for {case_type}")
        if lang_code in firm["languages"]:
            reasons.append(f"Supports caller language ({lang_code})")
        if firm["firm_id"] == "martinez" and "orange" in caller_location.lower():
            match_score += 10
            reasons.append("Local Orange County presence")
        ranked.append(
            {
                "firm_id": firm["firm_id"],
                "name": firm["name"],
                "phone": firm["phone"],
                "score": min(100, match_score),
                "reasoning": "; ".join(reasons) or "General PI coverage",
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {"matches": ranked[:3], "case_strength": strength}


def mock_call_firm(firm_id: str, case_summary: str) -> dict[str, Any]:
    firm = next((f for f in FIRM_RULES if f["firm_id"] == firm_id), None)
    name = firm["name"] if firm else firm_id
    return {
        "status": "booked",
        "firm_id": firm_id,
        "firm_name": name,
        "consultation_time": "tomorrow at 10:00 AM",
        "message": f"[MOCK] Would dial {name} and brief receptionist: {case_summary[:200]}",
    }


def mock_sms_confirmation(consumer_phone: str, consultation_time: str) -> dict[str, Any]:
    return {
        "status": "sent",
        "to": consumer_phone,
        "body": (
            f"Caseflow: Your consultation is confirmed for {consultation_time}. "
            "A matched firm will call you. Reply STOP to opt out."
        ),
        "message": f"[MOCK] Would SMS {consumer_phone} confirming {consultation_time}",
    }
