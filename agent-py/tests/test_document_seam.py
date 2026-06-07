"""Tests for the Unsiloed↔Moss seam upgrades (Gaps 1-5, Enh C/D/E)."""

import pytest

from consistency import check_cross_document, extract_injury_keywords
from retrieval import Retriever
from tools.parse_document import (
    _extract_score,
    _map_extract_result,
    parse_document,
)


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
    assert (
        "head" in conflict["clarifying_question"]
        or "neck" in conflict["clarifying_question"]
    )


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


# -- Unsiloed /v2/extract schema mapping (real response shape) -------------- #
def test_extract_score_floors_present_values() -> None:
    # Low absolute extraction score but a present value → floored to 0.6.
    obj = {
        "value": "Orange County, CA",
        "score": {"grounding_score": 0.0, "extraction_score": 0.2},
    }
    assert _extract_score(obj) == 0.6
    # Strong grounding wins.
    strong = {"value": "x", "score": {"grounding_score": 0.95, "extraction_score": 0.2}}
    assert _extract_score(strong) == 0.95
    # No value → no floor.
    empty = {"value": "", "score": {"grounding_score": 0.0, "extraction_score": 0.1}}
    assert _extract_score(empty) == 0.1


def test_map_extract_result_police_report() -> None:
    result = {
        "document_type": {"value": "police_report", "score": {"extraction_score": 0.9}},
        "fault_determination": {
            "value": "undetermined",
            "score": {"extraction_score": 0.88},
        },
        "location": {"value": "Orange County, CA", "score": {"extraction_score": 0.2}},
        "report_number": {"value": "", "score": {"extraction_score": 0.0}},
    }
    fields, confidence = _map_extract_result(result, "police_report")
    assert fields["doc_type"] == "police_report"
    assert fields["fault_determination"] == "undetermined"
    assert "report_number" not in fields  # empty value dropped
    assert confidence["location"] == 0.6  # floored
    assert "unexpected_document" not in fields


def test_map_extract_result_flags_wrong_document() -> None:
    # Caller showed a license but the agent asked for a police report.
    result = {
        "document_type": {
            "value": "driver_license",
            "score": {"extraction_score": 0.95},
        },
        "report_number": {"value": "DL-9981", "score": {"extraction_score": 0.9}},
    }
    fields, _ = _map_extract_result(result, "police_report")
    assert fields["doc_type"] == "driver_license"
    assert fields["unexpected_document"] is True
    assert fields["requested_doc_type"] == "police_report"
    assert "license" in fields["parsed_summary"].lower()


# -- Enhancement C wiring: injury keywords sharpen the comparables query ----- #
class _Doc:
    def __init__(self):
        self.text, self.score, self.metadata, self.id = (
            "x",
            0.9,
            {
                "accident_type": "rear_end",
                "jurisdiction": "CA",
                "severity": "medium",
                "fault": "contested",
                "amount_low": "45000",
                "amount_high": "80000",
            },
            "ca-rear-end-med-contested",
        )


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
    await r.comparables(
        "rear_end", "CA", "medium", "contested", injury_keywords=["whiplash"]
    )
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
