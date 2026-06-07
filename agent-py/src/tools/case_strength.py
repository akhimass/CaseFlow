from __future__ import annotations

import re
from typing import Any

from tools.sol_lookup import check_sol

# Rough non-economic multiplier on top of economic damages (specials) by severity.
_SEVERITY_MULTIPLIER = {"low": 1.5, "medium": 2.5, "high": 4.0}
_SEVERITY_BASELINE = {"low": 20_000, "medium": 55_000, "high": 160_000}


def _to_amount(value: Any) -> int:
    """Best-effort dollar amount from text like '$45,000', '45000', '12k'."""
    if value is None:
        return 0
    text = str(value).lower().replace(",", "").strip()
    m = re.search(r"\$?\s?(\d+(?:\.\d+)?)\s?(k|thousand)?", text)
    if not m:
        return 0
    try:
        amount = float(m.group(1))
    except ValueError:
        return 0
    if m.group(2):  # "12k" / "12 thousand"
        amount *= 1000
    return int(amount)


def compute_case_value(case_data: dict[str, Any]) -> dict[str, Any]:
    """Estimate case value from economic damages (medical bills + lost wages)
    plus a severity multiplier for pain-and-suffering. Returns a low/high range
    and a point estimate used by firm matching's value floor."""
    medical = _to_amount(case_data.get("medical_bills"))
    wages = _to_amount(case_data.get("lost_wages"))
    specials = medical + wages
    severity = str(case_data.get("severity") or "medium").lower()
    mult = _SEVERITY_MULTIPLIER.get(severity, 2.5)
    if specials > 0:
        point = int(specials * (1 + mult))
    else:
        point = _SEVERITY_BASELINE.get(severity, 55_000)
    return {
        "estimated_value": point,
        "value_low": int(point * 0.7),
        "value_high": int(point * 1.4),
        "economic_damages": specials,
        "medical_bills": medical,
        "lost_wages": wages,
    }


def compute_case_strength(case_data: dict[str, Any]) -> dict[str, Any]:
    score = 50
    factors: list[str] = []

    state = (case_data.get("state") or case_data.get("jurisdiction") or "").upper()
    accident_date = case_data.get("accident_date") or case_data.get("incident_date")
    if state and accident_date:
        sol = check_sol(state, str(accident_date)[:10])
        if sol["viable"]:
            score += 10 if sol["days_remaining"] >= 90 else 5
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

    if case_data.get("has_prior_representation") or str(
        case_data.get("prior_representation") or ""
    ).lower() in {"yes", "true"}:
        score -= 50
        factors.append("Prior representation — conflict")

    # Financials / quantified value lift the strength of a viable claim.
    value = compute_case_value(case_data)
    if value["economic_damages"] > 0:
        score += 8
        factors.append(f"Documented economic damages ${value['economic_damages']:,}")
    if value["estimated_value"] >= 100_000:
        score += 7
        factors.append("High estimated case value")
    if str(case_data.get("police_involved") or "").lower() in {"yes", "true"}:
        score += 5
        factors.append("Police responded / report filed")

    score = max(0, min(100, score))
    return {
        "score": score,
        "factors": factors,
        "estimated_value": value["estimated_value"],
        "value_range": f"${value['value_low']:,}-${value['value_high']:,}",
        **value,
    }
