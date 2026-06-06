"""Statute-of-limitations lookup for PI intake."""

from __future__ import annotations

from datetime import date

SOL_TABLE: dict[str, dict[str, float | int]] = {
    "CA": {"sol_years": 2.0, "govt_notice_days": 180},
    "TX": {"sol_years": 2.0, "govt_notice_days": 180},
    "FL": {"sol_years": 4.0, "govt_notice_days": 180},
    "NY": {"sol_years": 3.0, "govt_notice_days": 90},
}
DEFAULT_SOL = {"sol_years": 2.0, "govt_notice_days": 180}


def _add_years(base_date: date, years: float) -> date:
    months = int(round(years * 12))
    year = base_date.year + months // 12
    month = base_date.month + months % 12
    while month > 12:
        year += 1
        month -= 12
    day = min(base_date.day, 28)
    return date(year, month, day)


def check_sol(
    state: str,
    accident_date: str,
    plaintiff_age: int = 30,
    defendant_type: str = "private",
) -> dict:
    """Return SoL viability for a PI matter."""
    accident = date.fromisoformat(accident_date)
    today = date.today()
    state_code = state.strip().upper()
    entry = SOL_TABLE.get(state_code, DEFAULT_SOL)
    sol_years = float(entry["sol_years"])

    if plaintiff_age < 18:
        deadline = _add_years(accident, sol_years + (18 - plaintiff_age))
        tolling_applied = True
    else:
        deadline = _add_years(accident, sol_years)
        tolling_applied = False

    days_remaining = (deadline - today).days
    viable = days_remaining >= 0

    return {
        "viable": viable,
        "sol_deadline": deadline.isoformat(),
        "days_remaining": days_remaining,
        "tolling_applied": tolling_applied,
        "rag_source": "fallback_table",
        "notes": (
            f"{state_code} PI filing window: {sol_years} years. "
            f"{days_remaining} days remaining."
        ),
    }
