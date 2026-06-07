"""Intake field completeness — triggers real-time document generation."""

from __future__ import annotations

import os
from typing import Any

DEFAULT_THRESHOLD = float(os.getenv("CASE_COMPLETENESS_THRESHOLD", "0.7"))

# The essential lead. Completeness (which gates intake-summary generation) is
# measured over these core facts only — the financial / enrichment fields
# (medical_bills, lost_wages, vehicle, police_involved, ...) sharpen a lead but
# must not delay the summary by raising the bar.
CORE_FIELDS = frozenset(
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
    }
)


def case_completeness(case_data: dict[str, Any]) -> float:
    if not CORE_FIELDS:
        return 0.0
    filled = sum(1 for field in CORE_FIELDS if _has_value(case_data.get(field)))
    return filled / len(CORE_FIELDS)


def completeness_crossed(
    case_data: dict[str, Any], *, threshold: float = DEFAULT_THRESHOLD
) -> bool:
    return case_completeness(case_data) >= threshold


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"unknown", "n/a", "none"}
