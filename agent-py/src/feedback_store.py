"""Lawyer feedback → learned retrieval re-ranking (the Caseflow Learning Loop).

Lawyers rate Moss sources (helpful / not helpful) from the firm dashboard; that
feedback lands in the Supabase ``source_feedback`` table. At call start the agent
loads a per-source net score, and the Retriever boosts or penalizes ranking so
validated sources rise and unhelpful ones sink on future calls — a closed
feedback loop layered on top of Moss semantic search.

The source id is the same ``namespace:docid`` used in citations (e.g.
``state-law:ca-sol``), so feedback ties directly to what the agent cited.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from supabase_store import _base, _configured, _headers

logger = logging.getLogger("feedback")

# How strongly net feedback shifts a semantic (0..1) Moss score. A source with
# net +3 helpful votes gains 3 * weight in effective score.
FEEDBACK_WEIGHT = float(os.getenv("FEEDBACK_RANK_WEIGHT", "0.12"))
# Bonus points (on the 0..100 firm fit scale) per net firm feedback vote.
FIRM_FEEDBACK_POINTS = int(os.getenv("FEEDBACK_FIRM_POINTS", "6"))


async def record_feedback(
    *,
    source_id: str,
    namespace: str,
    helpful: bool,
    case_id: str = "",
    firm_id: str = "",
    note: str = "",
) -> bool:
    """Persist a single helpful/not-helpful vote for a Moss source."""
    if not _configured() or not source_id:
        logger.debug("feedback skipped (supabase unconfigured or no source_id)")
        return False
    row = {
        "source_id": source_id,
        "namespace": namespace,
        "helpful": bool(helpful),
        "case_id": case_id or None,
        "firm_id": firm_id or None,
        "note": note or None,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{_base()}/source_feedback", headers=_headers(), json=row
            )
            resp.raise_for_status()
        logger.info(
            "CASEFLOW_FEEDBACK source=%s helpful=%s firm=%s", source_id, helpful, firm_id
        )
        return True
    except Exception:
        logger.exception("feedback write failed for %s", source_id)
        return False


def aggregate_scores(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Net score per source_id: (+1 helpful, -1 not-helpful) summed."""
    scores: dict[str, int] = {}
    for r in rows:
        sid = str(r.get("source_id") or "")
        if not sid:
            continue
        scores[sid] = scores.get(sid, 0) + (1 if r.get("helpful") else -1)
    return scores


async def load_scores() -> dict[str, int]:
    """Load net feedback per source from Supabase (best-effort, empty on failure)."""
    if not _configured():
        return {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{_base()}/source_feedback?select=source_id,helpful",
                headers=_headers(),
            )
            resp.raise_for_status()
            rows = resp.json()
        if not isinstance(rows, list):
            return {}
        scores = aggregate_scores(rows)
        logger.info("feedback scores loaded for %d sources", len(scores))
        return scores
    except Exception:
        logger.warning("feedback score load failed; ranking without feedback")
        return {}
