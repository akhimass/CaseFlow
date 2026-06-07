"""Adaptive retrieval — refine Moss cards as the case state evolves (Part 4).

As new facts emerge mid-call (ER visit, imaging, jurisdiction correction, language,
prior representation), only the *affected* Moss streams re-query. Identical queries
are absorbed by the Retriever's per-session cache, so a re-fire that changes nothing
costs nothing and produces no visual churn; a re-fire that changes the top result
cross-fades the card and triggers re-synthesis of the Caseflow Decision.

Concurrency model: changes within a debounce window batch into one cycle; cycles run
under a lock so a new cycle queues behind an in-flight one rather than cancelling it
(the most recent result wins because the Retriever stamps every event with a
monotonic ``seq`` the UI uses to discard stale cards).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from orchestrator import infer_fault, infer_severity
from retrieval import Retriever

logger = logging.getLogger("adaptive")

# Which Moss streams must re-retrieve when a given case field changes.
FIELD_NAMESPACES: dict[str, set[str]] = {
    "jurisdiction": {"state-law", "settlements", "firms", "procedures"},
    "state": {"state-law", "settlements", "firms", "procedures"},
    "accident_type": {"settlements", "firms", "procedures"},
    "severity": {"settlements"},
    "fault": {"settlements"},
    "er_visited": {"settlements"},
    "imaging_ordered": {"settlements"},
    "injuries": {"settlements"},
    "treatment": {"settlements"},
    "language": {"firms"},
    "prior_representation": {"procedures"},
}

Resynthesize = Callable[[], Awaitable[None]]


def namespaces_for_diff(diff: list[str]) -> set[str]:
    """Union of streams that should re-retrieve for the changed field names."""
    out: set[str] = set()
    for field in diff:
        out |= FIELD_NAMESPACES.get(field, set())
    return out


def _procedure_scenario(state: dict[str, Any]) -> str:
    """Pick the procedural checklist most relevant to the current case stage."""
    prior = str(state.get("prior_representation") or "").lower()
    if prior in ("", "no", "none", "false", "not yet", "no one"):
        return "recorded_statement"
    return "post_accident_72h"


class AdaptiveRetriever:
    """Debounced, deduplicated incremental re-retrieval keyed on case-state diffs."""

    def __init__(
        self,
        retriever: Retriever,
        *,
        resynthesize: Resynthesize | None = None,
        debounce_s: float = 0.5,
    ) -> None:
        self._retriever = retriever
        self._resynthesize = resynthesize
        self._debounce_s = debounce_s
        self._pending: set[str] = set()
        self._last_state: dict[str, Any] = {}
        self._deadline = 0.0
        self._timer: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        # Last top-3 ids per namespace, to gate re-synthesis on real changes.
        self._last_tops: dict[str, tuple[str, ...]] = {}

    async def on_case_state_change(
        self, diff: list[str], current_state: dict[str, Any]
    ) -> None:
        """Queue a debounced refresh cycle for the streams affected by ``diff``."""
        namespaces = namespaces_for_diff(diff)
        if not namespaces:
            return
        self._pending |= namespaces
        self._last_state = dict(current_state)
        self._deadline = asyncio.get_event_loop().time() + self._debounce_s
        logger.info("adaptive.queue diff=%s -> namespaces=%s", diff, sorted(namespaces))
        if self._timer is None or self._timer.done():
            self._timer = asyncio.create_task(self._debounce_runner())

    async def _debounce_runner(self) -> None:
        # Wait until the deadline stops moving (batches rapid changes into one cycle).
        while True:
            now = asyncio.get_event_loop().time()
            if now >= self._deadline:
                break
            await asyncio.sleep(self._deadline - now)
        await self._run_cycle()

    async def _run_cycle(self) -> None:
        namespaces = self._pending
        self._pending = set()
        if not namespaces:
            return
        state = self._last_state
        async with self._lock:  # queue behind any in-flight cycle, don't cancel
            try:
                rows_by_ns = await self._fire(namespaces, state)
            except Exception:
                logger.exception("adaptive retrieval cycle failed; cards unchanged")
                return

        changed = self._tops_changed(rows_by_ns)
        if changed and self._resynthesize is not None:
            logger.info("adaptive.resynthesize (top results changed in %s)", sorted(changed))
            try:
                await self._resynthesize()
            except Exception:
                logger.exception("adaptive re-synthesis failed")

    async def _fire(
        self, namespaces: set[str], state: dict[str, Any]
    ) -> dict[str, list[Any]]:
        jurisdiction = (state.get("state") or "CA").strip().upper()[:2]
        accident_type = str(state.get("accident_type") or "auto")
        severity = infer_severity(state)
        fault = infer_fault(state)
        location = str(state.get("location") or "")

        tasks: dict[str, Any] = {}
        if "state-law" in namespaces:
            tasks["state-law"] = self._retriever.state_law(jurisdiction, "sol")
        if "settlements" in namespaces:
            tasks["settlements"] = self._retriever.comparables(
                accident_type, jurisdiction, severity, fault
            )
        if "firms" in namespaces:
            tasks["firms"] = self._retriever.firms(state, location)
        if "procedures" in namespaces:
            tasks["procedures"] = self._retriever.procedures(_procedure_scenario(state))

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        out: dict[str, list[Any]] = {}
        for ns, result in zip(tasks.keys(), results, strict=True):
            out[ns] = [] if isinstance(result, Exception) else result
        return out

    def _tops_changed(self, rows_by_ns: dict[str, list[Any]]) -> set[str]:
        """Namespaces whose top-3 ids differ from the previous fire (dedup gate)."""
        changed: set[str] = set()
        for ns, rows in rows_by_ns.items():
            top = tuple(getattr(r, "id", "") for r in rows[:3])
            if self._last_tops.get(ns) != top:
                changed.add(ns)
            self._last_tops[ns] = top
        return changed
