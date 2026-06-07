"""Intake field completeness — triggers real-time document generation."""

from __future__ import annotations

import os
from typing import Any

from slot_extraction import ALLOWED_FIELDS

DEFAULT_THRESHOLD = float(os.getenv("CASE_COMPLETENESS_THRESHOLD", "0.7"))


def case_completeness(case_data: dict[str, Any]) -> float:
    if not ALLOWED_FIELDS:
        return 0.0
    filled = sum(
        1
        for field in ALLOWED_FIELDS
        if _has_value(case_data.get(field))
    )
    return filled / len(ALLOWED_FIELDS)


def completeness_crossed(
    case_data: dict[str, Any], *, threshold: float = DEFAULT_THRESHOLD
) -> bool:
    return case_completeness(case_data) >= threshold


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"unknown", "n/a", "none"}
