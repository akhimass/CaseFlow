import pytest

from consistency import (
    audit_utterance,
    check_against_comparables,
    check_against_state_law,
    check_consistency,
)


@pytest.fixture(autouse=True)
def _no_gateway(monkeypatch):
    """Force the rules/heuristic path so tests are deterministic and offline."""
    monkeypatch.delenv("TRUEFOUNDRY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("TRUEFOUNDRY_API_KEY", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    monkeypatch.delenv("AWS_BEDROCK_API_KEY", raising=False)


@pytest.mark.asyncio
async def test_maria_discrepancy_rules_fallback() -> None:
    result = await check_consistency(
        "fault_claim",
        "el otro conductor pasó la luz roja",
        "fault determination: undetermined",
        "es",
    )
    assert result["conflict"] is True
    assert result["source"] == "rules"
    assert result["clarifying_question"]
    assert "semáforo" in result["clarifying_question"]


# Part 5 — Moss-backed checks


_CA_SOL_LAW = [
    {"text": "California statute of limitations for personal injury is 2 years (CCP §335.1)."}
]


def test_state_law_check_flags_filing_window_overestimate() -> None:
    claims = [{"claim_type": "filing_window", "claim_value": "5 years", "confidence": 0.85}]
    conflict = check_against_state_law(claims, _CA_SOL_LAW, "en", state="CA")
    assert conflict and conflict["conflict_type"] == "claim_vs_state_law"
    assert "2 years" in conflict["clarifying_question"]


def test_state_law_check_no_conflict_when_within_window() -> None:
    claims = [{"claim_type": "filing_window", "claim_value": "2 years", "confidence": 0.85}]
    assert check_against_state_law(claims, _CA_SOL_LAW, "en", state="CA") is None


def test_comparables_check_flags_unrealistic_expectation() -> None:
    claims = [{"claim_type": "expected_amount", "claim_value": "$500,000", "confidence": 0.8}]
    comparables = [{"amount_high": 80000}, {"amount_high": 35000}]
    conflict = check_against_comparables(claims, comparables, "es")
    assert conflict and conflict["conflict_type"] == "expectation_vs_comparables"
    assert "$500,000" in conflict["clarifying_question"]


@pytest.mark.asyncio
async def test_audit_utterance_catches_sol_overestimate_in_spanish() -> None:
    result = await audit_utterance(
        "creo que tengo cinco años para presentar la demanda",
        language="es",
        law_snippets=_CA_SOL_LAW,
        state="CA",
    )
    assert result["conflict"] is True
    assert result["conflict_type"] == "claim_vs_state_law"
    assert result["confidence"] > 0.7


@pytest.mark.asyncio
async def test_audit_utterance_no_conflict_when_consistent() -> None:
    result = await audit_utterance(
        "the other car rear-ended me and the police came",
        language="en",
        law_snippets=_CA_SOL_LAW,
        comparables=[{"amount_high": 80000}],
        state="CA",
    )
    assert result["conflict"] is False
