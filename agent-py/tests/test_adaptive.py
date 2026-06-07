"""Tests for adaptive retrieval — incremental refresh on case-state diffs (Part 4)."""

import asyncio

import pytest

from adaptive_retrieval import AdaptiveRetriever, namespaces_for_diff


class _Row:
    def __init__(self, rid: str) -> None:
        self.id = rid


class _FakeRetriever:
    """Records which streams re-queried, returns controllable top ids."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.comparable_id = "settlements:ca-rear-end-low-contested"

    async def state_law(self, state, topic):
        self.calls.append("state-law")
        return [_Row("state-law:ca-sol")]

    async def comparables(self, accident_type, jurisdiction, severity, fault):
        self.calls.append("settlements")
        return [_Row(self.comparable_id)]

    async def firms(self, case_data, caller_location=""):
        self.calls.append("firms")
        return [_Row("firms:martinez")]

    async def procedures(self, scenario):
        self.calls.append("procedures")
        return [_Row(f"procedures:{scenario}")]


def test_namespaces_for_diff_mapping() -> None:
    assert namespaces_for_diff(["severity"]) == {"settlements"}
    assert namespaces_for_diff(["fault"]) == {"settlements"}
    assert namespaces_for_diff(["prior_representation"]) == {"procedures"}
    assert namespaces_for_diff(["language"]) == {"firms"}
    assert namespaces_for_diff(["state"]) == {
        "state-law",
        "settlements",
        "firms",
        "procedures",
    }
    assert namespaces_for_diff(["accident_type"]) == {"settlements", "firms", "procedures"}
    assert namespaces_for_diff(["unknown_field"]) == set()


async def _settle(adaptive: AdaptiveRetriever) -> None:
    # Let the debounce timer fire and the cycle complete.
    for _ in range(20):
        await asyncio.sleep(0.02)
        if adaptive._timer and adaptive._timer.done() and not adaptive._lock.locked():
            break


@pytest.mark.asyncio
async def test_severity_change_refreshes_comparables_only() -> None:
    fake = _FakeRetriever()
    resynth: list[int] = []

    async def on_resynth():
        resynth.append(1)

    adaptive = AdaptiveRetriever(fake, resynthesize=on_resynth, debounce_s=0.02)
    await adaptive.on_case_state_change(
        ["severity"], {"state": "CA", "accident_type": "rear_end", "severity": "medium"}
    )
    await _settle(adaptive)

    assert fake.calls == ["settlements"]
    assert resynth == [1]  # top changed (first fire) -> re-synthesis


@pytest.mark.asyncio
async def test_jurisdiction_change_refires_all_four() -> None:
    fake = _FakeRetriever()
    adaptive = AdaptiveRetriever(fake, debounce_s=0.02)
    await adaptive.on_case_state_change(["state"], {"state": "TX", "accident_type": "rear_end"})
    await _settle(adaptive)
    assert set(fake.calls) == {"state-law", "settlements", "firms", "procedures"}


@pytest.mark.asyncio
async def test_prior_representation_refreshes_procedures_only() -> None:
    fake = _FakeRetriever()
    adaptive = AdaptiveRetriever(fake, debounce_s=0.02)
    await adaptive.on_case_state_change(
        ["prior_representation"], {"state": "CA", "prior_representation": "no"}
    )
    await _settle(adaptive)
    assert fake.calls == ["procedures"]


@pytest.mark.asyncio
async def test_debounce_batches_rapid_changes() -> None:
    fake = _FakeRetriever()
    adaptive = AdaptiveRetriever(fake, debounce_s=0.05)
    state = {"state": "CA", "accident_type": "rear_end", "severity": "medium"}
    # Two settlement-affecting changes in quick succession -> one cycle.
    await adaptive.on_case_state_change(["severity"], state)
    await adaptive.on_case_state_change(["injuries"], state)
    await _settle(adaptive)
    assert fake.calls == ["settlements"]  # batched, fired once


@pytest.mark.asyncio
async def test_dedup_skips_resynthesis_when_top_unchanged() -> None:
    fake = _FakeRetriever()
    resynth: list[int] = []

    async def on_resynth():
        resynth.append(1)

    adaptive = AdaptiveRetriever(fake, resynthesize=on_resynth, debounce_s=0.02)
    state = {"state": "CA", "accident_type": "rear_end", "severity": "medium"}

    await adaptive.on_case_state_change(["severity"], state)
    await _settle(adaptive)
    # Second cycle returns the same top comparable id -> no re-synthesis.
    await adaptive.on_case_state_change(["fault"], state)
    await _settle(adaptive)
    assert resynth == [1]  # only the first (changed) fire re-synthesized

    # Now the comparable top changes -> re-synthesis fires again.
    fake.comparable_id = "settlements:ca-rear-end-med-contested"
    await adaptive.on_case_state_change(["severity"], state)
    await _settle(adaptive)
    assert resynth == [1, 1]
