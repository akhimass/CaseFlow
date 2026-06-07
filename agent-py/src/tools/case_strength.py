from __future__ import annotations

from typing import Any

from tools.sol_lookup import check_sol


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

    if case_data.get("has_prior_representation"):
        score -= 50
        factors.append("Prior representation — conflict")

    score = max(0, min(100, score))
    return {"score": score, "factors": factors}
