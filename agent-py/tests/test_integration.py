"""End-to-end Maria walkthrough across citations + synthesis + adaptive (Part 5).

Drives the real Retriever -> orchestrator -> synthesizer -> AdaptiveRetriever
pipeline against a fake Moss client, asserting the full chain: four streams fire,
the Caseflow Decision synthesizes with one citation per namespace, those citations
are strippable, and later case-state changes refine the right streams and
re-synthesize.
"""

import asyncio

import pytest

from adaptive_retrieval import AdaptiveRetriever
from citations import strip_citations
from orchestrator import run_parallel_retrieval, synthesize_and_emit
from retrieval import Retriever


@pytest.fixture(autouse=True)
def _no_gateway(monkeypatch):
    for var in (
        "TRUEFOUNDRY_GATEWAY_URL",
        "TRUEFOUNDRY_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_BEDROCK_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


class _Doc:
    def __init__(self, text, score, meta, doc_id):
        self.text, self.score, self.metadata, self.id = text, score, meta, doc_id


class _Result:
    def __init__(self, docs):
        self.docs = docs
        self.time_taken_ms = 4.0


class _FakeMoss:
    """Per-index fixtures; comparable result depends on severity to show narrowing."""

    def __init__(self):
        self.calls: list[str] = []

    async def load_index(self, name, *a, **k):
        pass

    async def query(self, index, query, options=None):
        self.calls.append(index)
        if index == "state-law":
            return _Result(
                [_Doc("CA SoL 2 years.", 0.93, {"state": "CA", "topic": "sol",
                      "citation": "CCP §335.1"}, "ca-sol")]
            )
        if index == "settlements":
            # "high" severity surfaces a higher comparable than the default.
            if "high" in query:
                return _Result(
                    [_Doc("CA rear-end high.", 0.9, {"accident_type": "rear_end",
                          "jurisdiction": "CA", "severity": "high", "fault": "contested",
                          "amount_low": "120000", "amount_high": "180000"},
                          "ca-rear-end-high-clear")]
                )
            return _Result(
                [_Doc("CA rear-end medium.", 0.9, {"accident_type": "rear_end",
                      "jurisdiction": "CA", "severity": "medium", "fault": "contested",
                      "amount_low": "45000", "amount_high": "80000"},
                      "ca-rear-end-med-contested")]
            )
        if index == "firms":
            return _Result(
                [_Doc("Martinez OC bilingual.", 0.9, {"firm_id": "martinez",
                      "name": "Martinez & Associates", "jurisdictions": "CA",
                      "county": "Orange County", "specialties": "auto,rear_end,mva",
                      "languages": "en,es", "min_case_value": "0",
                      "phone": "(714) 555-0142"}, "martinez")]
            )
        if index == "procedures":
            return _Result(
                [_Doc("First 72 hours.", 0.88, {"scenario": "post_accident_72h",
                      "urgency": "immediate"}, "first-72-hours")]
            )
        return _Result([])


async def _settle(adaptive):
    for _ in range(25):
        await asyncio.sleep(0.02)
        if adaptive._timer and adaptive._timer.done() and not adaptive._lock.locked():
            break


@pytest.mark.asyncio
async def test_maria_end_to_end() -> None:
    moss = _FakeMoss()
    events: list[dict] = []
    decisions: list[dict] = []

    async def on_result(ev):
        events.append(ev)

    async def on_decision(payload):
        decisions.append(payload)

    retriever = Retriever(moss, on_result=on_result, cache={})
    case = {
        "state": "CA",
        "language": "es",
        "accident_type": "rear_end",
        "severity": "medium",
        "location": "Orange County",
    }

    # 1-3. Initial fan-out -> four streams + a synthesized decision.
    await run_parallel_retrieval(
        retriever, case, caller_location="Orange County", on_decision=on_decision
    )

    fired = {e["namespace"] for e in events}
    assert fired == {"state-law", "settlements", "firms", "procedures"}

    ready = [d for d in decisions if d.get("status") == "ready"]
    assert ready, "a ready Caseflow Decision should be emitted"
    decision = ready[-1]
    assert decision["language"] == "es"
    # Exactly one citation per namespace, and they are strippable.
    assert len(decision["citations"]) == 4
    clean, ids = strip_citations(decision["synthesis"])
    assert "[cite:" not in clean
    assert {i.split(":", 1)[0] for i in ids} == {
        "state-law",
        "settlements",
        "firms",
        "procedures",
    }

    # 4-6. Adaptive refinement: severity rises -> comparables-only refresh + re-synth.
    async def resynth():
        await synthesize_and_emit(retriever.latest_retrievals(), case, on_decision)

    adaptive = AdaptiveRetriever(retriever, resynthesize=resynth, debounce_s=0.02)
    events.clear()
    decisions.clear()
    await adaptive.on_case_state_change(["severity"], {**case, "severity": "high"})
    await _settle(adaptive)

    assert {e["namespace"] for e in events} == {"settlements"}
    # The refined comparable is the higher-severity band.
    top = events[-1]["snippets"][0]
    assert top["amount_high"] == 180000
    assert any(d.get("status") == "ready" for d in decisions), "re-synthesis fired"

    # 7. A jurisdiction correction re-fires all four streams.
    events.clear()
    await adaptive.on_case_state_change(["state"], {**case, "state": "TX"})
    await _settle(adaptive)
    assert {e["namespace"] for e in events} == {
        "state-law",
        "settlements",
        "firms",
        "procedures",
    }
