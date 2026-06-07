"""Tests for the Unsiloed↔Moss seam upgrades (Gaps 1-5, Enh C/D/E)."""

import pytest

from consistency import check_cross_document, extract_injury_keywords
from retrieval import Retriever
from tools.parse_document import parse_document


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    for var in (
        "TRUEFOUNDRY_GATEWAY_URL",
        "TRUEFOUNDRY_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_DIRECT_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


# -- Enhancement C: injury keyword extraction ------------------------------- #
def test_extract_injury_keywords() -> None:
    kw = extract_injury_keywords("whiplash / cervical strain", "MRI cervical spine")
    assert "whiplash" in kw
    assert "cervical sprain" in kw
    assert extract_injury_keywords("") == []


# -- Enhancement D: cross-document consistency ------------------------------ #
def test_cross_document_region_mismatch() -> None:
    police = {"other_driver_claim": "I hit my head on the wheel", "location": "OC"}
    er = {"primary_diagnosis": "cervical strain (neck)"}
    conflict = check_cross_document(police, er, "en")
    assert conflict and conflict["conflict_type"] == "cross_document"
    assert "head" in conflict["clarifying_question"] or "neck" in conflict["clarifying_question"]


def test_cross_document_consistent_no_conflict() -> None:
    police = {"other_driver_claim": "rear-ended, neck pain"}
    er = {"primary_diagnosis": "whiplash, cervical strain (neck)"}
    assert check_cross_document(police, er, "en") is None  # both neck → consistent


# -- Gap 1 + E: parse result carries source/status/confidence --------------- #
@pytest.mark.asyncio
async def test_parse_demo_has_confidence_and_source(monkeypatch) -> None:
    monkeypatch.delenv("UNSILOED_API_KEY", raising=False)
    result = await parse_document("data:image/jpeg;base64,AAAA", "police_report")
    meta = result["_meta"]
    assert meta["source"] == "demo_no_key"
    assert meta["status"] == "parsed"
    assert "fault_determination" in meta["confidence"]
    # other_driver_claim is intentionally low-confidence → drives the verify badge.
    assert "other_driver_claim" in meta["low_confidence"]


# -- Enhancement C wiring: injury keywords sharpen the comparables query ----- #
class _Doc:
    def __init__(self):
        self.text, self.score, self.metadata, self.id = "x", 0.9, {
            "accident_type": "rear_end",
            "jurisdiction": "CA",
            "severity": "medium",
            "fault": "contested",
            "amount_low": "45000",
            "amount_high": "80000",
        }, "ca-rear-end-med-contested"


class _Result:
    def __init__(self):
        self.docs = [_Doc()]
        self.time_taken_ms = 4.0


class _RecordingMoss:
    def __init__(self):
        self.queries: list[str] = []

    async def query(self, index, query, options=None):
        self.queries.append(query)
        return _Result()


@pytest.mark.asyncio
async def test_comparables_query_includes_injury_keywords() -> None:
    moss = _RecordingMoss()
    r = Retriever(moss, cache={})
    await r.comparables("rear_end", "CA", "medium", "contested", injury_keywords=["whiplash"])
    assert any("whiplash" in q for q in moss.queries)


# -- Gap 2: a Moss query failure surfaces an error event -------------------- #
class _FailingMoss:
    async def query(self, index, query, options=None):
        raise RuntimeError("moss down")


@pytest.mark.asyncio
async def test_query_failure_emits_error_card() -> None:
    events: list[dict] = []

    async def on_result(ev):
        events.append(ev)

    r = Retriever(_FailingMoss(), on_result=on_result, cache={})
    rows = await r.state_law("CA", "sol")
    assert rows == []
    assert events and events[-1]["error"]
    assert events[-1]["namespace"] == "state-law"
    assert events[-1]["results_count"] == 0
