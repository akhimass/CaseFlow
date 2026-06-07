"""Async continuous validation — grades agent turns every N turns."""

from __future__ import annotations

import json
import logging
from typing import Any

from gateway import GatewayMetadata, chat, gateway_configured
from supabase_store import write_audit

logger = logging.getLogger("validator")

from gateway import GATEWAY_MODEL

VALIDATOR_MODEL = GATEWAY_MODEL
TURN_INTERVAL = 5


async def maybe_validate_turn(
    *,
    turn: int,
    case_id: str,
    caller_id: str,
    last_user_utterance: str,
    last_agent_utterance: str,
    case_state: dict[str, Any],
    language: str,
) -> dict[str, Any] | None:
    if turn < TURN_INTERVAL or turn % TURN_INTERVAL != 0:
        return None

    rubric = (
        "Grade the agent's last turn for a PI video intake. Return JSON only with "
        "scores 1-5 for: language_match, document_accuracy, follow_up_relevance, "
        "and overall. Include brief notes."
    )
    context = json.dumps(
        {
            "turn": turn,
            "language": language,
            "user": last_user_utterance,
            "agent": last_agent_utterance,
            "case_state": case_state,
        }
    )

    if not gateway_configured():
        logger.debug("Validator skipped — gateway not configured")
        return None

    try:
        response = await chat(
            VALIDATOR_MODEL,
            [
                {"role": "system", "content": rubric},
                {"role": "user", "content": context},
            ],
            temperature=0.0,
            metadata=GatewayMetadata(case_id=case_id, turn=turn, caller_id=caller_id),
            allow_failover=True,
        )
        result = {"raw": response.content, "turn": turn, "model": response.model_id}
        await write_audit(
            case_id=case_id,
            event_type="validator_score",
            actor=VALIDATOR_MODEL,
            model_id=response.model_id,
            payload=result,
            latency_ms=response.latency_ms,
        )
        return result
    except Exception:
        logger.exception("Validator turn %s failed", turn)
        return None
