from __future__ import annotations

from typing import Any

from geo import state_from_location
from tools.case_strength import compute_case_strength
from tools.firms_data import load_firms

_BILINGUAL_FALLBACK_FIRMS = {"pacific_heights", "bay_counsel"}


def _normalize_case_type(case_type: str) -> str:
    value = (case_type or "mva").lower().replace(" ", "_")
    if "rear" in value or "auto" in value or "mva" in value:
        return "mva"
    if "slip" in value or "fall" in value or "premises" in value:
        return "slip_fall"
    if "motorcycle" in value:
        return "motorcycle"
    return value


def _location_boost(
    firm: dict[str, Any], caller_location: str
) -> tuple[int, str | None]:
    loc = (caller_location or "").strip().lower()
    if not loc:
        return 0, None

    tokens: list[str] = []
    for area in firm.get("service_areas") or []:
        if area:
            tokens.append(str(area).lower())
    location = str(firm.get("location") or "").lower()
    if location:
        tokens.append(location)

    for token in tokens:
        if token in loc or loc in token:
            label = token.title() if token else "local area"
            return 12, f"Local San Francisco presence ({label})"

    if any(tok in loc for tok in ("san francisco", "sf", "bay area")) and (
        "san francisco" in location or "sf" in tokens
    ):
        return 8, "Serves San Francisco callers"

    return 0, None


def match_firm(case_data: dict[str, Any], caller_location: str = "") -> dict[str, Any]:
    strength = compute_case_strength(case_data)["score"]
    location = (caller_location or case_data.get("location") or "").strip()
    raw_state = str(case_data.get("state") or "").strip()
    if len(raw_state) == 2 and raw_state.isalpha():
        state = raw_state.upper()
    else:
        state = state_from_location(raw_state) or state_from_location(location) or "CA"
    language = (case_data.get("language") or "en").lower()
    lang_code = "es" if language.startswith("es") else "en"
    case_type = _normalize_case_type(str(case_data.get("accident_type") or "mva"))

    ranked: list[dict[str, Any]] = []
    for firm in load_firms():
        jurisdictions = set(firm.get("jurisdictions") or [])
        languages = set(firm.get("languages") or [])
        specialties = set(firm.get("specialties") or [])
        if state not in jurisdictions:
            continue
        if strength < firm.get("min_strength", 0) and "high_value" in specialties:
            continue
        if (
            lang_code not in languages
            and firm["firm_id"] not in _BILINGUAL_FALLBACK_FIRMS
        ):
            continue

        match_score = strength
        reasons: list[str] = []
        if case_type in specialties or "general_pi" in specialties:
            match_score += 15
            reasons.append(f"Specialty fit for {case_type}")
        if lang_code in languages:
            reasons.append(f"Supports caller language ({lang_code})")

        boost, local_reason = _location_boost(firm, location)
        if boost:
            match_score += boost
            if local_reason:
                reasons.append(local_reason)

        ranked.append(
            {
                "firm_id": firm["firm_id"],
                "name": firm["name"],
                "phone": firm["phone"],
                "test_phone": firm.get("test_phone"),
                "score": min(100, match_score),
                "reasoning": "; ".join(reasons) or "General PI coverage",
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    matches = ranked[:3]
    top = matches[0] if matches else {}
    return {
        "matches": matches,
        "case_strength": strength,
        "caller_location": location,
        "matched_firm_id": top.get("firm_id"),
    }
