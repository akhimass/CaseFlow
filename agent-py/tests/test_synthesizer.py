"""Tests for the cross-namespace synthesizer (Part 3)."""

import pytest

from retrieval import FirmMatch, LawSnippet, ProcedureSnippet, Settlement
from synthesizer import synthesize_decision, token_count


@pytest.fixture(autouse=True)
def _no_gateway(monkeypatch):
    """Force the deterministic fallback so tests are offline + stable."""
    for var in (
        "TRUEFOUNDRY_GATEWAY_URL",
        "TRUEFOUNDRY_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_BEDROCK_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def _retrievals():
    return {
        "state_law": [
            LawSnippet(
                state="CA",
                topic="sol",
                citation="Cal. Code Civ. Proc. §335.1",
                text="Two years from the date of injury.",
                score=0.93,
                id="state-law:ca-sol",
            )
        ],
        "comparables": [
            Settlement(
                accident_type="rear_end",
                jurisdiction="CA",
                severity="medium",
                fault="contested",
                amount_low=45000,
                amount_high=80000,
                text="OC rear-end MRI disc bulge.",
                score=0.91,
                id="settlements:ca-rear-end-med-contested",
            )
        ],
        "firms": [
            FirmMatch(
                firm_id="martinez",
                name="Martinez & Associates",
                phone="(714) 555-0142",
                languages=["en", "es"],
                specialties=["auto", "rear_end"],
                jurisdictions=["CA"],
                min_case_value=0,
                score=97,
                match_reasons=["specialty match for rear end", "Spanish-speaking intake"],
                text="OC bilingual auto firm.",
                id="firms:martinez",
            )
        ],
        "procedures": [
            ProcedureSnippet(
                scenario="post_accident_72h",
                urgency="immediate",
                text="Seek care, call police, photograph the scene.",
                score=0.88,
                id="procedures:first-72-hours",
            )
        ],
    }


@pytest.mark.asyncio
async def test_synthesis_has_one_citation_per_namespace() -> None:
    decision = await synthesize_decision(
        {"state": "CA", "accident_type": "rear_end", "severity": "medium"},
        _retrievals(),
        "en",
    )
    assert decision.source == "fallback"
    # Exactly four citations, one per namespace.
    assert len(decision.citations) == 4
    namespaces = {c.split(":", 1)[0] for c in decision.citations}
    assert namespaces == {"state-law", "settlements", "firms", "procedures"}
    assert "settlements:ca-rear-end-med-contested" in decision.citations


@pytest.mark.asyncio
async def test_synthesis_matches_caller_language() -> None:
    decision = await synthesize_decision({"state": "CA"}, _retrievals(), "es")
    assert decision.language == "es"
    # Spanish fallback uses Spanish connective words.
    assert "Próximo paso" in decision.synthesis or "Conforme" in decision.synthesis


@pytest.mark.asyncio
async def test_synthesis_stays_under_token_budget() -> None:
    decision = await synthesize_decision({"state": "CA"}, _retrievals(), "en")
    assert token_count(decision.synthesis) < 250
    assert 0 <= decision.confidence <= 100
    # High coverage + strong firm score → a confident memo.
    assert decision.confidence >= 60
