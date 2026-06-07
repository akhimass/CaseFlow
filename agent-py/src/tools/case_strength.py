from __future__ import annotations

import re
from typing import Any

from tools.sol_lookup import check_sol

# Base pain-and-suffering multiplier on economic damages (the "specials"), by
# severity. Adjusted upward for imaging, surgery, permanency, and ongoing care.
_SEVERITY_MULTIPLIER = {"low": 1.5, "medium": 2.5, "high": 4.0}
# Fallback point estimate when no financials are known yet, by severity.
_SEVERITY_BASELINE = {"low": 20_000, "medium": 55_000, "high": 160_000}
# Liability factor — CA pure comparative negligence haircut on recoverable value.
_LIABILITY_FACTOR = {
    "clear": 1.0,
    "admitted": 1.0,
    "rear_end": 0.95,
    "contested": 0.8,
    "disputed": 0.8,
    "undetermined": 0.75,
    "shared": 0.55,
    "comparative": 0.55,
}


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


def _liability_factor(case_data: dict[str, Any]) -> tuple[float, str]:
    fault = str(
        case_data.get("fault") or case_data.get("fault_determination") or case_data.get("fault_claim") or ""
    ).lower()
    for key, factor in _LIABILITY_FACTOR.items():
        if key in fault:
            return factor, key
    # Caller blaming the other driver, no contradiction yet → lean favorable.
    if any(p in fault for p in ("other driver", "their fault", "ran the", "red light")):
        return 0.9, "other-party fault asserted"
    return 0.85, "liability not yet established"


def _comparable_anchor(case_data: dict[str, Any]) -> int | None:
    """Average midpoint of the comparable settlements Moss retrieved this call —
    the market anchor that grounds the formula estimate in real outcomes."""
    mids: list[float] = []
    for event in case_data.get("moss_retrievals") or []:
        if not isinstance(event, dict) or event.get("namespace") != "settlements":
            continue
        for snip in event.get("snippets") or []:
            lo, hi = snip.get("amount_low"), snip.get("amount_high")
            try:
                lo_i, hi_i = int(lo), int(hi)
            except (TypeError, ValueError):
                continue
            if lo_i and hi_i:
                mids.append((lo_i + hi_i) / 2)
    if not mids:
        return None
    return int(sum(mids) / len(mids))


def compute_case_value(case_data: dict[str, Any]) -> dict[str, Any]:
    """Estimate personal-injury case value with a defensible damages model:

    economic (specials) = past + estimated future medical + past + future lost
    wages + property/out-of-pocket; non-economic (general) = specials x a
    severity multiplier adjusted for imaging/surgery/permanency/ongoing care;
    a comparative-negligence liability factor haircuts the recoverable amount;
    and the formula is blended with the midpoint of the comparable settlements
    Moss retrieved this call. Returns a point estimate, a low/high range, and a
    transparent breakdown.
    """
    severity = str(case_data.get("severity") or "medium").lower()
    injuries = str(
        case_data.get("injuries") or case_data.get("primary_diagnosis") or ""
    ).lower()
    treatment = str(case_data.get("treatment") or "").lower()
    ongoing = str(case_data.get("ongoing_treatment") or "").lower() in {"yes", "true", "ongoing"}

    # --- Economic damages (specials) ---
    med_past = _to_amount(case_data.get("medical_bills"))
    wages_past = _to_amount(case_data.get("lost_wages"))
    out_of_pocket = _to_amount(case_data.get("out_of_pocket"))
    property_dmg = _to_amount(case_data.get("property_damage"))
    # Future care: ongoing treatment or surgery implies continued medical cost.
    has_surgery = any(w in injuries or w in treatment for w in ("surgery", "surgical", "orif", "microdiscectomy", "fusion"))
    med_future = int(med_past * (0.6 if has_surgery else 0.3)) if (ongoing or has_surgery) else 0
    # Future lost earning capacity for serious/permanent injury.
    permanent = any(w in injuries for w in ("permanent", "disab", "fracture", "herniat", "tbi", "traumatic brain"))
    wages_future = int(wages_past * (1.0 if permanent else 0.4)) if (permanent or severity == "high") and wages_past else 0
    economic = med_past + med_future + wages_past + wages_future + out_of_pocket + property_dmg

    # --- Non-economic (general) multiplier ---
    mult = _SEVERITY_MULTIPLIER.get(severity, 2.5)
    if case_data.get("imaging_ordered") or "mri" in injuries:
        mult += 0.5
    if has_surgery:
        mult += 1.0
    if permanent:
        mult += 0.5
    if ongoing:
        mult += 0.3
    mult = min(mult, 5.0)
    non_economic = int(economic * mult)

    # --- Liability haircut (comparative negligence) ---
    liability, liability_basis = _liability_factor(case_data)

    if economic > 0:
        formula = int((economic + non_economic) * liability)
    else:
        formula = int(_SEVERITY_BASELINE.get(severity, 55_000) * liability)

    # --- Anchor to comparable settlements Moss retrieved this call ---
    anchor = _comparable_anchor(case_data)
    if anchor:
        # Blend formula with market comps; lean on comps when we have no specials.
        weight = 0.6 if economic > 0 else 0.35
        point = int(weight * formula + (1 - weight) * anchor)
        method = "damages model blended with Moss comparable settlements"
    else:
        point = formula
        method = "damages model (no comparable anchor yet)"

    breakdown = [
        f"Economic damages ${economic:,} (medical ${med_past + med_future:,}, wages ${wages_past + wages_future:,})",
        f"Non-economic ${non_economic:,} at {mult:.1f}x ({severity} severity)",
        f"Liability factor {liability:.2f} — {liability_basis}",
    ]
    if anchor:
        breakdown.append(f"Moss comparable anchor ${anchor:,}")

    return {
        "estimated_value": point,
        "value_low": int(point * 0.7),
        "value_high": int(point * 1.35),
        "economic_damages": economic,
        "non_economic_damages": non_economic,
        "medical_bills": med_past,
        "lost_wages": wages_past,
        "multiplier": round(mult, 2),
        "liability_factor": liability,
        "comparable_anchor": anchor or 0,
        "method": method,
        "value_breakdown": breakdown,
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
