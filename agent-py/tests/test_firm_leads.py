"""Tests for Moss multi-index firm lead-gen (Retriever.firm_leads)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from retrieval import Retriever


class _Doc:
    def __init__(self, text, score, meta, doc_id, index_name):
        self.text = text
        self.score = score
        self.metadata = meta
        self.id = doc_id
        self.index_name = index_name


class _Result:
    def __init__(self, docs):
        self.docs = docs
        self.time_taken_ms = 6.0


class _FakeMoss:
    """Returns a blended multi-index result like Moss query_multi_index."""

    def __init__(self):
        self.multi_calls = []

    async def query_multi_index(self, indexes, query, options=None):
        self.multi_calls.append((tuple(indexes), query))
        return _Result(
            [
                # Firm: CA bilingual rear-end specialist (should win).
                _Doc(
                    "Pacific Heights handles contested rear-end whiplash in CA.",
                    0.94,
                    {
                        "firm_id": "pacific_heights",
                        "name": "Pacific Heights Injury Law",
                        "jurisdictions": "CA",
                        "specialties": "general_pi,auto,mva,rear_end",
                        "languages": "en,es",
                        "min_case_value": "0",
                        "phone": "(415) 555-0101",
                        "rating": "4.9",
                        "years_experience": "18",
                        "response_time_hours": "2",
                        "track_settlement_low": "30000",
                        "track_settlement_high": "95000",
                    },
                    "pacific_heights",
                    "firms",
                ),
                # Firm: out-of-jurisdiction (should be gated out).
                _Doc(
                    "Lone Star Texas firm.",
                    0.6,
                    {
                        "firm_id": "lone_star",
                        "name": "Lone Star Injury",
                        "jurisdictions": "TX",
                        "specialties": "auto",
                        "languages": "en",
                        "min_case_value": "0",
                        "phone": "(512) 555-0000",
                    },
                    "lone_star",
                    "firms",
                ),
                # Settlement evidence (correlated).
                _Doc(
                    "CA rear-end medium contested.",
                    0.9,
                    {
                        "accident_type": "rear_end",
                        "jurisdiction": "CA",
                        "severity": "medium",
                        "fault": "contested",
                        "amount_low": "45000",
                        "amount_high": "80000",
                    },
                    "ca-rear-end-med",
                    "settlements",
                ),
                # State-law evidence (correlated).
                _Doc(
                    "California gives two years to file a personal injury claim.",
                    0.92,
                    {"state": "CA", "topic": "sol", "citation": "CCP §335.1"},
                    "ca-sol",
                    "state-law",
                ),
            ]
        )


@pytest.mark.asyncio
async def test_firm_leads_correlates_and_gates():
    retriever = Retriever(_FakeMoss())
    case = {
        "state": "CA",
        "language": "es",
        "accident_type": "rear_end",
        "severity": "medium",
        "fault": "contested",
        "injuries": "whiplash",
    }
    leads = await retriever.firm_leads(case, caller_location="Anaheim, CA")

    # One multi-index call over all three indexes.
    assert retriever._moss.multi_calls
    indexes, _q = retriever._moss.multi_calls[0]
    assert set(indexes) == {"firms", "settlements", "state-law"}

    # The TX firm is gated out; the CA bilingual rear-end firm wins.
    assert leads, "expected at least one lead"
    assert all(ld.firm_id != "lone_star" for ld in leads)
    top = leads[0]
    assert top.firm_id == "pacific_heights"
    assert top.score >= 80

    # Evidence correlated from the same retrieval is attached.
    assert top.comparable_range == "$45,000-$80,000"
    assert "two years" in top.jurisdiction_note
    assert top.rating == "4.9"
    reasons = " ".join(top.match_reasons).lower()
    assert "rear end" in reasons or "rear_end" in reasons
    assert "spanish" in reasons


@pytest.mark.asyncio
async def test_firm_leads_summary_mentions_comparables():
    retriever = Retriever(_FakeMoss())
    leads = await retriever.firm_leads(
        {"state": "CA", "language": "en", "accident_type": "rear_end"}
    )
    assert "Comparable outcomes" in leads[0].summary()
