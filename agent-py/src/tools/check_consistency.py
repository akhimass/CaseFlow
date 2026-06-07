from __future__ import annotations

from typing import Any

from consistency import check_consistency as run_consistency_check

__all__ = ["check_consistency"]


async def check_consistency(
    field_name: str,
    verbal_claim: str,
    parsed_value: str,
    language: str = "en",
    *,
    case_id: str = "",
    turn: int = 0,
    caller_id: str = "",
    case_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await run_consistency_check(
        field_name,
        verbal_claim,
        parsed_value,
        language,
        case_id=case_id,
        turn=turn,
        caller_id=caller_id,
        case_state=case_state,
    )
