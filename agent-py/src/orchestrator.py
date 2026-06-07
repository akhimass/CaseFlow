"""Parallel Moss retrieval orchestrator.

Once Unsiloed has parsed the police report, the agent knows enough about the case
(jurisdiction, accident type, fault status, and — from the ER discharge — injury
severity) to fan out all four Moss retrieval streams at once.

:func:`run_parallel_retrieval` fires the four :class:`retrieval.Retriever` calls
concurrently via ``asyncio.gather``. Each call independently pushes its result card
to the firm dashboard the moment it returns, so judges see four Moss streams light
up in parallel — the visual centerpiece of "Moss as the headline sponsor."
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from retrieval import (
    FirmMatch,
    LawSnippet,
    ProcedureSnippet,
    Retriever,
    Settlement,
)
from synthesizer import synthesize_decision

logger = logging.getLogger("orchestrator")

# Debounce after the four streams return, in case a late result is still arriving.
SYNTHESIS_DEBOUNCE_S = 0.3
SYNTHESIS_RETRY_DELAY_S = 2.0

OnDecision = Callable[[dict[str, Any]], Awaitable[None]]

# Procedural checklist to surface for a given case stage.
_STAGE_SCENARIO = {
    "post_accident": "post_accident_72h",
    "intake": "post_accident_72h",
    "insurance": "insurance_adjuster",
    "treatment": "finding_doctor",
    "documentation": "documenting_injuries",
}


def infer_fault(case_data: dict[str, Any]) -> str:
    """Map a parsed police report / verbal account onto clear|contested|shared."""
    documents = case_data.get("documents") or {}
    police = documents.get("police_report") or {}
    determination = str(
        police.get("fault_determination") or case_data.get("fault") or ""
    ).lower()
    if "undetermin" in determination or "dispute" in determination:
        return "contested"
    if (
        "shared" in determination
        or "both" in determination
        or "partial" in determination
    ):
        return "shared"
    if "clear" in determination or "admit" in determination or "cited" in determination:
        return "clear"
    return "contested"  # PI intake default: assume liability must be proven


def infer_severity(case_data: dict[str, Any]) -> str:
    """Map ER discharge / injuries text onto low|medium|high."""
    if case_data.get("severity"):
        return str(case_data["severity"]).lower()
    documents = case_data.get("documents") or {}
    er = documents.get("er_discharge") or {}
    blob = " ".join(
        str(v)
        for v in (
            er.get("primary_diagnosis"),
            er.get("imaging_ordered"),
            er.get("discharge_instructions"),
            case_data.get("injuries"),
        )
        if v
    ).lower()
    if any(k in blob for k in ("surgery", "fracture", "hospital", "herniat", "spinal")):
        return "high"
    if any(
        k in blob for k in ("mri", "whiplash", "disc", "concussion", "sprain", "strain")
    ):
        return "medium"
    return "medium" if blob else "low"


def _profile(case_data: dict[str, Any]) -> dict[str, str]:
    return {
        "jurisdiction": (case_data.get("state") or "CA").strip().upper()[:2],
        "accident_type": str(case_data.get("accident_type") or "auto"),
        "severity": infer_severity(case_data),
        "fault": infer_fault(case_data),
    }


async def synthesize_and_emit(
    retrievals: dict[str, Any],
    case_data: dict[str, Any],
    on_decision: OnDecision,
    *,
    case_id: str = "",
    caller_id: str = "",
) -> Any:
    """Run synthesis and push the Caseflow Decision, with a pending + retry UX.

    Emits a ``synthesizing`` status first so the card shows a quiet placeholder,
    then the finished decision. If synthesis comes back empty, retries once after
    a short delay (Part 5C). The synthesizer itself has a deterministic fallback,
    so a hard failure is rare; we still degrade to an ``error`` status if it raises.
    """
    language = str(case_data.get("language") or "en")
    try:
        await on_decision({"status": "synthesizing"})
        decision = await synthesize_decision(
            case_data, retrievals, language, case_id=case_id, caller_id=caller_id
        )
        if not decision.synthesis:
            await asyncio.sleep(SYNTHESIS_RETRY_DELAY_S)
            decision = await synthesize_decision(
                case_data, retrievals, language, case_id=case_id, caller_id=caller_id
            )
        await on_decision({**decision.to_dict(), "status": "ready"})
        return decision
    except Exception:
        logger.exception("synthesis emit failed")
        with contextlib.suppress(Exception):
            await on_decision({"status": "error"})
        return None


async def run_parallel_retrieval(
    retriever: Retriever,
    case_data: dict[str, Any],
    *,
    caller_location: str = "",
    case_stage: str = "post_accident",
    on_decision: OnDecision | None = None,
    case_id: str = "",
    caller_id: str = "",
) -> dict[str, Any]:
    """Fire all four Moss retrievals concurrently and return the combined result.

    Each retriever call streams its own card to the dashboard as it completes;
    this function simply waits for the full set and returns a structured summary.
    """
    profile = _profile(case_data)
    scenario = _STAGE_SCENARIO.get(case_stage, "post_accident_72h")
    logger.info("orchestrator.fanout profile=%s stage=%s", profile, case_stage)

    results = await asyncio.gather(
        retriever.state_law(profile["jurisdiction"], "sol"),
        retriever.comparables(
            profile["accident_type"],
            profile["jurisdiction"],
            profile["severity"],
            profile["fault"],
        ),
        retriever.firms(case_data, caller_location),
        retriever.procedures(scenario),
        return_exceptions=True,
    )

    labels = ("state_law", "comparables", "firms", "procedures")
    out: dict[str, Any] = {"profile": profile, "stage": case_stage}
    for label, result in zip(labels, results, strict=True):
        if isinstance(result, Exception):
            logger.exception("orchestrator stream %s failed", label, exc_info=result)
            out[label] = []
        else:
            out[label] = result

    # Part 3: after all four streams settle, debounce briefly then synthesize.
    if on_decision is not None:
        await asyncio.sleep(SYNTHESIS_DEBOUNCE_S)
        await synthesize_and_emit(
            out, case_data, on_decision, case_id=case_id, caller_id=caller_id
        )

    return out


def summarize(result: dict[str, Any]) -> str:
    """A compact text summary of a fan-out, for logging or an LLM brief."""
    law: list[LawSnippet] = result.get("state_law") or []
    comps: list[Settlement] = result.get("comparables") or []
    firms: list[FirmMatch] = result.get("firms") or []
    procs: list[ProcedureSnippet] = result.get("procedures") or []
    return (
        f"Moss fan-out [{result.get('profile')}]: "
        f"{len(law)} law, {len(comps)} comparables, "
        f"{len(firms)} firms, {len(procs)} procedures."
    )
