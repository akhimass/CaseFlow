"""Extract structured PI intake slots from caller transcripts."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

from bedrock_llm import parse_json_object
from gateway import GATEWAY_MODEL, GatewayMetadata, chat, llm_configured
from geo import state_from_location

logger = logging.getLogger("slot_extraction")

SLOT_MODEL = GATEWAY_MODEL
CONFIDENCE_THRESHOLD = float(os.getenv("SLOT_EXTRACTION_CONFIDENCE", "0.75"))

ALLOWED_FIELDS = frozenset(
    {
        "accident_type",
        "accident_date",
        "state",
        "location",
        "injuries",
        "fault_claim",
        "treatment",
        "prior_representation",
        "caller_name",
        # Identity + vehicle + financials for case valuation (intake build-out).
        "vehicle",
        "medical_bills",
        "lost_wages",
        "police_involved",
        "ongoing_treatment",
        "employment_status",
    }
)


@dataclass(frozen=True)
class ExtractedSlot:
    field_name: str
    value: str
    confidence: float
    source: str


def _rules_extract(transcript: str, language: str) -> list[ExtractedSlot]:
    text = transcript.strip()
    lower = text.lower()
    slots: list[ExtractedSlot] = []

    if any(
        p in lower
        for p in (
            "rear-end",
            "rear ended",
            "me chocaron por atrás",
            "por detrás",
            "golpearon por atrás",
        )
    ):
        slots.append(
            ExtractedSlot("accident_type", "rear-end collision", 0.9, "rules")
        )
    elif any(p in lower for p in ("t-bone", "side impact", "de lado")):
        slots.append(ExtractedSlot("accident_type", "side-impact collision", 0.85, "rules"))
    elif any(p in lower for p in ("slip and fall", "resbalé", "caí en")):
        slots.append(ExtractedSlot("accident_type", "slip and fall", 0.85, "rules"))

    state_match = re.search(
        r"\b(california|texas|florida|arizona|nevada|new york|orange county)\b",
        lower,
    )
    if state_match:
        value = state_match.group(1)
        field = "location" if "county" in value else "state"
        slots.append(ExtractedSlot(field, value.title(), 0.82, "rules"))

    # Resolve a bare city/county to its state ("Anaheim" → CA) so the agent can
    # fire state-law retrieval before the caller names the state explicitly.
    derived_state = state_from_location(text)
    if derived_state and not any(s.field_name == "state" for s in slots):
        slots.append(ExtractedSlot("state", derived_state, 0.8, "rules"))

    date_match = re.search(
        r"\b(\d{4}-\d{2}-\d{2}|june\s+\d{1,2}(?:,\s*\d{4})?|"
        r"\d{1,2}/\d{1,2}/\d{2,4}|"
        r"\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|octubre|noviembre|diciembre)(?:\s+de\s+\d{4})?)\b",
        lower,
    )
    if date_match:
        slots.append(
            ExtractedSlot("accident_date", date_match.group(1), 0.78, "rules")
        )

    if any(
        p in lower
        for p in (
            "whiplash",
            "latigazo",
            "cervical",
            "neck pain",
            "dolor de cuello",
            "mri",
            "resonancia",
        )
    ):
        injury = (
            "whiplash / cervical strain"
            if language.startswith("es") or "latigazo" in lower or "cervical" in lower
            else "whiplash / neck pain"
        )
        slots.append(ExtractedSlot("injuries", injury, 0.84, "rules"))

    if any(
        p in lower
        for p in (
            "red light",
            "luz roja",
            "pasó el semáforo",
            "paso la luz",
            "ran the light",
        )
    ):
        claim = (
            "other driver ran the red light"
            if not language.startswith("es")
            else "el otro conductor pasó la luz roja"
        )
        slots.append(ExtractedSlot("fault_claim", claim, 0.88, "rules"))

    if any(p in lower for p in ("er ", "emergency room", "urgencias", "hospital")):
        slots.append(
            ExtractedSlot("treatment", "emergency room visit", 0.8, "rules")
        )

    if any(
        p in lower
        for p in ("already have a lawyer", "ya tengo abogado", "otro abogado")
    ):
        slots.append(ExtractedSlot("prior_representation", "yes", 0.85, "rules"))

    # Police involvement.
    if any(
        p in lower
        for p in ("police", "officer", "filed a report", "policía", "policia", "patrulla")
    ):
        slots.append(ExtractedSlot("police_involved", "yes", 0.8, "rules"))

    # Lost wages / missed work.
    if any(
        p in lower
        for p in ("missed work", "lost wages", "couldn't work", "could not work",
                  "out of work", "falté al trabajo", "no pude trabajar", "perdí trabajo")
    ):
        slots.append(ExtractedSlot("lost_wages", "reported missed work", 0.78, "rules"))

    # Medical bills — a dollar amount mentioned near medical/bill/hospital terms.
    bill = re.search(
        r"(?:bill|medical|hospital|cuenta|factura|cost)[^$]{0,40}(\$?\s?[\d,]{3,})",
        lower,
    )
    if bill:
        slots.append(ExtractedSlot("medical_bills", bill.group(1).strip(), 0.76, "rules"))

    return [s for s in slots if s.field_name in ALLOWED_FIELDS]


async def _gateway_extract(
    transcript: str,
    language: str,
    *,
    case_id: str,
    turn: int,
    caller_id: str,
) -> list[ExtractedSlot]:
    system = (
        "Extract personal-injury intake slots from the caller utterance. "
        "Return JSON only: {\"slots\": [{\"field_name\": string, \"value\": string, "
        "\"confidence\": number}]}. "
        f"Allowed field_name values: {', '.join(sorted(ALLOWED_FIELDS))}. "
        "Only include slots explicitly stated or strongly implied. "
        "confidence 0-1."
    )
    response = await chat(
        SLOT_MODEL,
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {"utterance": transcript, "language": language},
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.0,
        metadata=GatewayMetadata(case_id=case_id, turn=turn, caller_id=caller_id),
    )
    parsed = parse_json_object(response.content) or {}
    raw_slots = parsed.get("slots") if isinstance(parsed.get("slots"), list) else []
    results: list[ExtractedSlot] = []
    for item in raw_slots:
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name", "")).strip()
        value = str(item.get("value", "")).strip()
        if not field_name or not value or field_name not in ALLOWED_FIELDS:
            continue
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        results.append(
            ExtractedSlot(field_name, value, confidence, response.provider)
        )
    return results


async def extract_slots(
    transcript: str,
    language: str,
    *,
    case_id: str = "",
    turn: int = 0,
    caller_id: str = "",
) -> list[ExtractedSlot]:
    """Rules first; enrich with gateway when configured."""
    slots = _rules_extract(transcript, language)
    if not llm_configured():
        return slots

    try:
        gateway_slots = await _gateway_extract(
            transcript,
            language,
            case_id=case_id,
            turn=turn,
            caller_id=caller_id,
        )
    except Exception:
        logger.exception("Gateway slot extraction failed; using rules only")
        return slots

    merged: dict[str, ExtractedSlot] = {s.field_name: s for s in slots}
    for slot in gateway_slots:
        prior = merged.get(slot.field_name)
        if prior is None or slot.confidence > prior.confidence:
            merged[slot.field_name] = slot
    return list(merged.values())


def slots_above_threshold(slots: list[ExtractedSlot]) -> list[ExtractedSlot]:
    return [s for s in slots if s.confidence >= CONFIDENCE_THRESHOLD]
