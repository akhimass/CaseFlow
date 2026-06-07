"""Moss retrieval layer for Caseflow.

A single :class:`Retriever` backs both the agent's ``@function_tool`` retrieval
tools (``agent.py``) and the parallel fan-out (``orchestrator.py``), so caching,
logging, and dashboard push behave identically no matter who triggers a query.

Design notes
------------
* **Four indexes, not namespaces.** Moss has no namespace concept, so each
  retrieval stream (``state-law``, ``settlements``, ``firms``, ``procedures``) is
  its own index. The index name doubles as the dashboard "namespace" label.
* **Strings only.** Moss stores metadata as strings and compares numerics
  lexically, so money fields (settlement amounts, ``min_case_value``) are parsed
  to ``int`` in Python and filtered/ranked here rather than via Moss ``$lt``.
* **Per-session cache.** Identical queries within one call are served from an
  in-memory dict so the agent never re-queries the same SoL rule three times.
* **Dashboard push.** Every *fresh* retrieval invokes the ``on_result`` callback
  with a JSON-serializable event the firm dashboard renders as a live card.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

from moss import QueryOptions

logger = logging.getLogger("retrieval")

# Index names (overridable via env; default to the knowledge/ subdir names).
STATE_LAW_INDEX = os.getenv("MOSS_STATE_LAW_INDEX", "state-law")
SETTLEMENTS_INDEX = os.getenv("MOSS_SETTLEMENTS_INDEX", "settlements")
FIRMS_INDEX = os.getenv("MOSS_FIRMS_INDEX", "firms")
PROCEDURES_INDEX = os.getenv("MOSS_PROCEDURES_INDEX", "procedures")

ALL_KNOWLEDGE_INDEXES = (
    STATE_LAW_INDEX,
    SETTLEMENTS_INDEX,
    FIRMS_INDEX,
    PROCEDURES_INDEX,
)

# Rough case-value estimate by severity, used to test firm min_case_value gates.
_SEVERITY_VALUE = {"low": 25_000, "medium": 60_000, "high": 175_000}

# Soft per-call rate-limit budget (Part 5B). Exceeding it only logs a warning.
MAX_QUERIES_PER_MIN = 6

# Callback the agent wires to broadcast a retrieval card to the firm dashboard.
OnResult = Callable[[dict[str, Any]], Awaitable[None]]


# --------------------------------------------------------------------------- #
# Typed result rows (Part 3 signatures: LawSnippet, Settlement, FirmMatch, ...)
# --------------------------------------------------------------------------- #
@dataclass
class LawSnippet:
    state: str
    topic: str
    citation: str
    text: str
    score: float | None = None
    id: str = ""  # citation id, namespace:docid

    def summary(self) -> str:
        cite = f" ({self.citation})" if self.citation else ""
        return f"[cite:{self.id}] [{self.state} {self.topic}]{cite} {self.text}"


@dataclass
class Settlement:
    accident_type: str
    jurisdiction: str
    severity: str
    fault: str
    amount_low: int
    amount_high: int
    text: str
    score: float | None = None
    id: str = ""  # citation id, namespace:docid

    def summary(self) -> str:
        return (
            f"[cite:{self.id}] [{self.jurisdiction} {self.accident_type}, "
            f"{self.severity} severity, {self.fault} fault] "
            f"${self.amount_low:,}-${self.amount_high:,}: {self.text}"
        )


@dataclass
class FirmMatch:
    firm_id: str
    name: str
    phone: str
    languages: list[str]
    specialties: list[str]
    jurisdictions: list[str]
    min_case_value: int
    score: int
    match_reasons: list[str] = field(default_factory=list)
    text: str = ""
    id: str = ""  # citation id, namespace:docid

    def summary(self) -> str:
        reasons = "; ".join(self.match_reasons) or "general PI coverage"
        return f"[cite:{self.id}] {self.name} ({self.score}): {reasons}"


@dataclass
class ProcedureSnippet:
    scenario: str
    urgency: str
    text: str
    score: float | None = None
    id: str = ""  # citation id, namespace:docid

    def summary(self) -> str:
        return f"[cite:{self.id}] [{self.scenario} · {self.urgency}] {self.text}"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _norm(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _docs(result: Any) -> list[Any]:
    return list(getattr(result, "docs", None) or [])


def _score(doc: Any) -> float | None:
    raw = getattr(doc, "score", None)
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _meta(doc: Any) -> dict[str, Any]:
    return getattr(doc, "metadata", None) or {}


def _eq(field_name: str, value: str) -> dict[str, Any]:
    return {"field": field_name, "condition": {"$eq": value}}


# --------------------------------------------------------------------------- #
# Retriever
# --------------------------------------------------------------------------- #
class Retriever:
    """Wraps a MossClient with caching, logging, and dashboard push.

    Args:
        moss: a ``MossClient`` (or compatible stub in tests).
        on_result: optional async callback invoked with a serializable card event
            on every fresh (cache-miss) retrieval.
        cache: optional shared dict for per-session query caching. Pass the same
            dict to the tools and the orchestrator so they share a cache.
    """

    def __init__(
        self,
        moss: Any,
        *,
        on_result: OnResult | None = None,
        cache: dict[str, list[Any]] | None = None,
    ) -> None:
        self._moss = moss
        self._on_result = on_result
        self._cache = cache if cache is not None else {}
        # Monotonic sequence per emitted event (lets the UI discard stale results
        # from a slower in-flight query), and the latest rows per namespace (for
        # re-synthesis without re-querying every stream).
        self._seq = 0
        self._latest: dict[str, list[Any]] = {}
        # Rate-limit safety: warn (don't block) if we exceed the per-minute budget.
        self._query_times: list[float] = []

    # Map dashboard namespace -> orchestrator/synthesis result key.
    _NS_TO_KEY: ClassVar[dict[str, str]] = {
        "state-law": "state_law",
        "settlements": "comparables",
        "firms": "firms",
        "procedures": "procedures",
    }

    def latest_retrievals(self) -> dict[str, list[Any]]:
        """The most recent rows per stream, keyed for the synthesizer/orchestrator."""
        return {key: self._latest.get(ns, []) for ns, key in self._NS_TO_KEY.items()}

    # -- internal query plumbing ------------------------------------------- #
    async def _query(
        self, index: str, query: str, *, top_k: int, metadata_filter: dict | None = None
    ) -> tuple[list[Any], float, str | None]:
        options = (
            QueryOptions(top_k=top_k, filter=metadata_filter)
            if metadata_filter
            else QueryOptions(top_k=top_k)
        )
        # Per-minute budget guard (Part 5B). Caching keeps most cycles well under
        # this; we warn rather than block so a busy call never stalls mid-demo.
        now = time.monotonic()
        self._query_times = [t for t in self._query_times if now - t < 60.0]
        self._query_times.append(now)
        if len(self._query_times) > MAX_QUERIES_PER_MIN:
            logger.warning(
                "Moss query budget exceeded: %d queries in the last 60s (soft limit %d)",
                len(self._query_times),
                MAX_QUERIES_PER_MIN,
            )

        start = time.perf_counter()
        try:
            result = await self._moss.query(index, query, options)
        except Exception as exc:
            logger.exception("Moss query failed (index=%s, query=%r)", index, query)
            return [], (time.perf_counter() - start) * 1000.0, str(exc)[:200]
        elapsed_ms = getattr(result, "time_taken_ms", None)
        if elapsed_ms is None:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
        return _docs(result), float(elapsed_ms), None

    def _cache_store(
        self,
        key: str,
        *,
        namespace: str,
        query: str,
        rows: list[Any],
        cards: list[dict[str, Any]],
    ) -> None:
        self._cache[key] = {
            "namespace": namespace,
            "query": query,
            "rows": rows,
            "cards": cards,
        }

    async def _emit_cached(self, key: str) -> list[Any] | None:
        """Re-emit a cached Moss result so the dashboard still shows the card."""
        hit = self._cache.get(key)
        if hit is None:
            return None
        if isinstance(hit, dict) and "rows" in hit:
            await self._emit(
                hit["namespace"],
                hit["query"],
                hit["rows"],
                0.0,
                hit["cards"],
                cached=True,
            )
            return hit["rows"]
        return hit if isinstance(hit, list) else None

    async def _emit(
        self,
        namespace: str,
        query: str,
        rows: list[Any],
        elapsed_ms: float,
        cards: list[dict[str, Any]],
        *,
        cached: bool = False,
        error: str | None = None,
    ) -> None:
        # Remember the latest rows for this stream (used by re-synthesis). Don't
        # clobber a good prior result with an error (the card shows the error but
        # synthesis keeps the last good rows).
        if not error:
            self._latest[namespace] = rows
        top_preview = (cards[0].get("text", "") if cards else "")[:120]
        logger.info(
            "moss.retrieve namespace=%s results=%d latency=%.1fms cached=%s error=%s query=%r top=%r",
            namespace,
            len(rows),
            elapsed_ms,
            cached,
            bool(error),
            query,
            top_preview,
        )
        if self._on_result is None:
            return
        self._seq += 1
        event = {
            "namespace": namespace,
            "query": query,
            "results_count": len(rows),
            "time_taken_ms": round(elapsed_ms, 2),
            "timestamp": time.time(),
            "seq": self._seq,
            "snippets": cards,
            "cached": cached,
            "error": error,
        }
        try:
            await self._on_result(event)
        except Exception:
            logger.exception("on_result callback failed for namespace=%s", namespace)

    def _cache_get(self, key: str) -> list[Any] | None:
        hit = self._cache.get(key)
        if hit is not None:
            logger.info("moss.cache HIT key=%s", key)
        return hit

    # -- A) state law ------------------------------------------------------ #
    async def state_law(self, state: str, topic: str) -> list[LawSnippet]:
        state_code = (state or "CA").strip().upper()[:2]
        topic_norm = _norm(topic) or "general"
        # Map loose topics onto the four indexed topics.
        if any(
            k in topic_norm
            for k in ("sol", "stat", "limitat", "deadline", "filing", "window")
        ):
            topic_norm = "sol"
        elif (
            "neglig" in topic_norm
            or "fault" in topic_norm
            or "comparative" in topic_norm
        ):
            topic_norm = "negligence"
        elif (
            "damage" in topic_norm
            or "cap" in topic_norm
            or "compensation" in topic_norm
        ):
            topic_norm = "damages"
        elif topic_norm not in {"sol", "negligence", "damages", "general"}:
            topic_norm = "general"

        cache_key = f"state-law:{state_code}:{topic_norm}"
        if self._cache_get(cache_key) is not None:
            hit = await self._emit_cached(cache_key)
            if hit is not None:
                return hit

        query = f"{state_code} personal injury {topic_norm.replace('_', ' ')}"
        filt = {"$and": [_eq("state", state_code), _eq("topic", topic_norm)]}
        docs, elapsed, err = await self._query(
            STATE_LAW_INDEX, query, top_k=3, metadata_filter=filt
        )
        if not docs:  # fall back to state-only if the topic pairing missed
            docs, elapsed, err = await self._query(
                STATE_LAW_INDEX, query, top_k=3, metadata_filter=_eq("state", state_code)
            )
        if not docs and err:
            await self._emit("state-law", query, [], elapsed, [], error=err)
            return []

        rows = [
            LawSnippet(
                state=_meta(d).get("state", state_code),
                topic=_meta(d).get("topic", topic_norm),
                citation=_meta(d).get("citation", ""),
                text=(getattr(d, "text", "") or "").strip(),
                score=_score(d),
                id=f"state-law:{getattr(d, 'id', '')}",
            )
            for d in docs
        ]
        cards = [
            {
                "id": r.id,
                "title": r.citation or f"{r.state} {r.topic}",
                "subtitle": f"{r.state} · {r.topic}",
                "text": r.text,
                "score": r.score,
                "citation": r.citation,
            }
            for r in rows
        ]
        await self._emit("state-law", query, rows, elapsed, cards)
        self._cache_store(cache_key, namespace="state-law", query=query, rows=rows, cards=cards)
        return rows

    # -- B) comparable settlements ----------------------------------------- #
    async def comparables(
        self,
        accident_type: str,
        jurisdiction: str,
        severity: str,
        fault: str,
        injury_keywords: list[str] | None = None,
    ) -> list[Settlement]:
        atype = _norm(accident_type)
        juris = (jurisdiction or "CA").strip().upper()[:2]
        sev = _norm(severity)
        flt = _norm(fault)
        # Enhancement C: injury keywords from the parsed ER discharge sharpen the
        # semantic query so the comparable range narrows to matching injuries.
        injuries = " ".join(injury_keywords or [])
        inj_key = ",".join(sorted(injury_keywords or []))

        cache_key = f"settlements:{atype}:{juris}:{sev}:{flt}:{inj_key}"
        if self._cache_get(cache_key) is not None:
            hit = await self._emit_cached(cache_key)
            if hit is not None:
                return hit

        query = (
            f"{atype.replace('_', ' ')} {sev} severity {flt} fault {juris} "
            f"{injuries} settlement"
        ).replace("  ", " ")
        filt = {"$and": [_eq("accident_type", atype), _eq("jurisdiction", juris)]}
        docs, elapsed, err = await self._query(
            SETTLEMENTS_INDEX, query, top_k=6, metadata_filter=filt
        )
        if not docs:  # widen to accident type across jurisdictions
            docs, elapsed, err = await self._query(
                SETTLEMENTS_INDEX, query, top_k=6, metadata_filter=_eq("accident_type", atype)
            )
        if not docs:  # last resort: pure semantic
            docs, elapsed, err = await self._query(SETTLEMENTS_INDEX, query, top_k=6)
        if not docs and err:
            await self._emit("settlements", query, [], elapsed, [], error=err)
            return []

        rows: list[Settlement] = []
        for d in docs:
            m = _meta(d)
            rows.append(
                Settlement(
                    accident_type=m.get("accident_type", atype),
                    jurisdiction=m.get("jurisdiction", juris),
                    severity=m.get("severity", ""),
                    fault=m.get("fault", ""),
                    amount_low=_as_int(m.get("amount_low")),
                    amount_high=_as_int(m.get("amount_high")),
                    text=(getattr(d, "text", "") or "").strip(),
                    score=_score(d),
                    id=f"settlements:{getattr(d, 'id', '')}",
                )
            )

        # Prefer same-severity matches near the top, keep 3-5.
        rows.sort(key=lambda r: (r.severity != sev, -(r.score or 0.0)))
        rows = rows[:5]

        cards = [
            {
                "id": r.id,
                "title": f"{r.jurisdiction} {r.accident_type.replace('_', ' ')}",
                "subtitle": f"{r.severity} severity · {r.fault} fault",
                "amount_range": f"${r.amount_low:,}-${r.amount_high:,}",
                "amount_low": r.amount_low,
                "amount_high": r.amount_high,
                "text": r.text,
                "score": r.score,
            }
            for r in rows
        ]
        await self._emit("settlements", query, rows, elapsed, cards)
        self._cache_store(
            cache_key, namespace="settlements", query=query, rows=rows, cards=cards
        )
        return rows

    # -- C) matching firms ------------------------------------------------- #
    async def firms(
        self, case_data: dict[str, Any], caller_location: str = ""
    ) -> list[FirmMatch]:
        state = (case_data.get("state") or caller_location or "CA").strip().upper()[:2]
        language = (case_data.get("language") or "en").lower()
        lang_code = "es" if language.startswith("es") else "en"
        case_type = _norm(case_data.get("accident_type") or "auto")
        severity = _norm(case_data.get("severity") or "medium")
        est_value = _as_int(case_data.get("estimated_value")) or _SEVERITY_VALUE.get(
            severity, 60_000
        )
        location = caller_location.strip().lower()

        cache_key = f"firms:{state}:{lang_code}:{case_type}:{est_value}:{location}"
        if self._cache_get(cache_key) is not None:
            hit = await self._emit_cached(cache_key)
            if hit is not None:
                return hit

        query = (
            f"{case_type.replace('_', ' ')} personal injury firm {state} "
            f"{lang_code} {caller_location}".strip()
        )
        # Pull the whole (small) firm roster, then rank in Python.
        docs, elapsed, err = await self._query(FIRMS_INDEX, query, top_k=10)
        if not docs and err:
            await self._emit("firms", query, [], elapsed, [], error=err)
            return []

        candidates: list[FirmMatch] = []
        for d in docs:
            m = _meta(d)
            jurisdictions = _split_list(m.get("jurisdictions", ""))
            languages = _split_list(m.get("languages", ""))
            specialties = _split_list(m.get("specialties", ""))
            min_value = _as_int(m.get("min_case_value"))

            # Hard gates: jurisdiction + language + value floor.
            if jurisdictions and state not in jurisdictions:
                continue
            multilingual = len(languages) >= 3
            if languages and lang_code not in languages and not multilingual:
                continue
            if est_value < min_value:
                continue

            score = 50
            reasons: list[str] = []
            if case_type in specialties:
                score += 25
                reasons.append(f"specialty match for {case_type.replace('_', ' ')}")
            elif "general_pi" in specialties:
                score += 12
                reasons.append("handles all PI types")
            if lang_code in languages:
                score += 12
                reasons.append(
                    "Spanish-speaking intake" if lang_code == "es" else "English intake"
                )
            if min_value > 0 and est_value >= min_value:
                score += 8
                reasons.append(f"meets ${min_value:,} case-value floor")
            county = m.get("county", "").lower()
            if location and county and any(tok in county for tok in location.split()):
                score += 10
                reasons.append(f"local presence in {m.get('county')}")

            firm_id = m.get("firm_id", d.id if hasattr(d, "id") else "")
            candidates.append(
                FirmMatch(
                    firm_id=firm_id,
                    name=m.get("name", ""),
                    phone=m.get("phone", ""),
                    languages=languages,
                    specialties=specialties,
                    jurisdictions=jurisdictions,
                    min_case_value=min_value,
                    score=min(100, score),
                    match_reasons=reasons,
                    text=(getattr(d, "text", "") or "").strip(),
                    id=f"firms:{firm_id}",
                )
            )

        candidates.sort(key=lambda f: f.score, reverse=True)
        rows = candidates[:3]

        cards = [
            {
                "id": r.id,
                "title": r.name,
                "subtitle": ", ".join(r.specialties[:3]),
                "score": r.score,
                "phone": r.phone,
                "languages": r.languages,
                "reasons": r.match_reasons,
                "text": r.text,
            }
            for r in rows
        ]
        await self._emit("firms", query, rows, elapsed, cards)
        self._cache_store(cache_key, namespace="firms", query=query, rows=rows, cards=cards)
        return rows

    # -- D) procedural guidance -------------------------------------------- #
    async def procedures(self, scenario: str) -> list[ProcedureSnippet]:
        scen = _norm(scenario) or "post_accident_72h"
        # Map common phrasings to indexed scenarios.
        if (
            "72" in scen
            or "after" in scen
            or "first" in scen
            or "just_happened" in scen
        ):
            scen = "post_accident_72h"
        elif "adjust" in scen or "insur" in scen:
            scen = "insurance_adjuster"
        elif "record" in scen or "statement" in scen:
            scen = "recorded_statement"
        elif "document" in scen or "evidence" in scen:
            scen = "documenting_injuries"
        elif "doctor" in scen or "treat" in scen or "physician" in scen:
            scen = "finding_doctor"

        cache_key = f"procedures:{scen}"
        if self._cache_get(cache_key) is not None:
            hit = await self._emit_cached(cache_key)
            if hit is not None:
                return hit

        query = scenario or scen.replace("_", " ")
        docs, elapsed, err = await self._query(
            PROCEDURES_INDEX, query, top_k=3, metadata_filter=_eq("scenario", scen)
        )
        if not docs:  # semantic fallback if the scenario tag missed
            docs, elapsed, err = await self._query(PROCEDURES_INDEX, query, top_k=3)
        if not docs and err:
            await self._emit("procedures", query, [], elapsed, [], error=err)
            return []

        rows = [
            ProcedureSnippet(
                scenario=_meta(d).get("scenario", scen),
                urgency=_meta(d).get("urgency", ""),
                text=(getattr(d, "text", "") or "").strip(),
                score=_score(d),
                id=f"procedures:{getattr(d, 'id', '')}",
            )
            for d in docs
        ]
        cards = [
            {
                "id": r.id,
                "title": r.scenario.replace("_", " ").title(),
                "subtitle": f"urgency: {r.urgency}" if r.urgency else "",
                "text": r.text,
                "score": r.score,
            }
            for r in rows
        ]
        await self._emit("procedures", query, rows, elapsed, cards)
        self._cache_store(
            cache_key, namespace="procedures", query=query, rows=rows, cards=cards
        )
        return rows


def rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list of dataclass rows for JSON payloads / tests."""
    return [asdict(r) for r in rows]
