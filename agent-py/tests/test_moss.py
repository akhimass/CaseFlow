"""Unit tests for the agent's Moss-backed tools.

Deterministic tests that exercise the tool methods directly, stubbing
``MossClient`` via monkeypatch so they run with no Moss credentials and no
network. Covers the four retrieval tools (Part 3) and the per-user memory tools.
The live, credentialed behavior is validated separately in the checkpoint run.
"""

import json

import pytest

import agent as agent_module
from agent import Assistant

USER_ID = "user_42"


class _FakeDoc:
    """Stand-in for a Moss query-result document (`.text/.score/.metadata/.id`)."""

    def __init__(self, text, score=None, metadata=None, doc_id="doc") -> None:
        self.text = text
        self.score = score
        self.metadata = metadata or {}
        self.id = doc_id


class _FakeSearchResult:
    """Stand-in for a Moss `SearchResult` (`.docs/.time_taken_ms`)."""

    def __init__(self, docs, time_taken_ms: float = 12.5) -> None:
        self.docs = docs
        self.time_taken_ms = time_taken_ms


# Per-index fixtures the fake returns, keyed by index name.
_INDEX_RESULTS = {
    "state-law": _FakeSearchResult(
        [
            _FakeDoc(
                "California statute of limitations for personal injury is 2 years.",
                score=0.93,
                metadata={"state": "CA", "topic": "sol", "citation": "CCP §335.1"},
                doc_id="ca-sol",
            )
        ],
        time_taken_ms=4.0,
    ),
    "settlements": _FakeSearchResult(
        [
            _FakeDoc(
                "CA rear-end MRI disc bulge, contested, $45,000-$80,000.",
                score=0.91,
                metadata={
                    "accident_type": "rear_end",
                    "jurisdiction": "CA",
                    "severity": "medium",
                    "fault": "contested",
                    "amount_low": "45000",
                    "amount_high": "80000",
                },
                doc_id="ca-rear-end-med-contested",
            )
        ],
        time_taken_ms=5.0,
    ),
    "firms": _FakeSearchResult(
        [
            _FakeDoc(
                "Martinez & Associates Orange County bilingual auto.",
                score=0.9,
                metadata={
                    "firm_id": "martinez",
                    "name": "Martinez & Associates",
                    "jurisdictions": "CA",
                    "county": "Orange County",
                    "specialties": "auto,rear_end,mva",
                    "languages": "en,es",
                    "min_case_value": "0",
                    "phone": "(714) 555-0142",
                },
                doc_id="martinez",
            ),
            _FakeDoc(
                "Cohen Law Group high value only.",
                score=0.6,
                metadata={
                    "firm_id": "cohen",
                    "name": "Cohen Law Group",
                    "jurisdictions": "CA",
                    "county": "Statewide",
                    "specialties": "high_value",
                    "languages": "en",
                    "min_case_value": "100000",
                    "phone": "(800) 555-0171",
                },
                doc_id="cohen",
            ),
        ],
        time_taken_ms=6.0,
    ),
    "procedures": _FakeSearchResult(
        [
            _FakeDoc(
                "First 72 hours: seek care, call police, photograph the scene.",
                score=0.88,
                metadata={"scenario": "post_accident_72h", "urgency": "immediate"},
                doc_id="first-72-hours",
            )
        ],
        time_taken_ms=3.0,
    ),
}


class _FakeMossClient:
    """Records calls instead of contacting Moss; returns per-index fixtures."""

    def __init__(self, *args, **kwargs) -> None:
        self.load_index_calls: list[str] = []
        self.query_calls: list[tuple] = []
        self.add_docs_calls: list[tuple] = []
        # For the memory tools, tests set this explicitly.
        self.query_result = _FakeSearchResult([])

    async def load_index(self, name, *args, **kwargs):
        self.load_index_calls.append(name)

    async def query(self, index, query, options=None):
        self.query_calls.append((index, query, options))
        if index in _INDEX_RESULTS:
            return _INDEX_RESULTS[index]
        return self.query_result

    async def add_docs(self, index, docs, options=None):
        self.add_docs_calls.append((index, docs, options))
        return None


class _FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple] = []

    async def publish_data(self, payload, reliable=None):
        self.published.append((payload, reliable))


class _FakeRoom:
    def __init__(self) -> None:
        self.local_participant = _FakePublisher()


@pytest.fixture
def stub_moss(monkeypatch):
    """Replace the agent's `MossClient` and broadcast with recording fakes."""
    monkeypatch.setattr(agent_module, "MossClient", _FakeMossClient)

    async def noop_broadcast(*_args, **_kwargs):
        return None

    monkeypatch.setattr(agent_module, "broadcast", noop_broadcast)


def _query_for(assistant, index):
    return [call for call in assistant._moss.query_calls if call[0] == index]


# --------------------------------------------------------------------------- #
# Part 3 retrieval tools
# --------------------------------------------------------------------------- #
async def test_retrieve_state_law_filters_state_and_topic(stub_moss) -> None:
    room = _FakeRoom()
    assistant = Assistant(room=room, user_id=USER_ID)

    result = await assistant.retrieve_state_law(None, "CA", "filing window")

    # Returned text surfaces the citation + snippet.
    assert "CCP §335.1" in result
    assert "2 years" in result

    # Queried the state-law index, filtered to CA + sol (topic normalized).
    calls = _query_for(assistant, "state-law")
    assert len(calls) == 1
    _index, _query, options = calls[0]
    assert options.filter == {
        "$and": [
            {"field": "state", "condition": {"$eq": "CA"}},
            {"field": "topic", "condition": {"$eq": "sol"}},
        ]
    }

    # Published a moss_context packet namespaced to state-law.
    assert len(room.local_participant.published) == 1
    payload, reliable = room.local_participant.published[0]
    assert reliable is True
    data = json.loads(payload.decode("utf-8"))["data"]
    assert data["query"].startswith("[state-law]")

    # Recorded a retrieval card for the dashboard.
    retrievals = assistant._case_data["moss_retrievals"]
    assert len(retrievals) == 1
    assert retrievals[0]["namespace"] == "state-law"
    assert retrievals[0]["results_count"] == 1


async def test_retrieve_state_law_caches_within_session(stub_moss) -> None:
    assistant = Assistant(user_id=USER_ID)
    await assistant.retrieve_state_law(None, "CA", "sol")
    await assistant.retrieve_state_law(None, "CA", "filing window")  # same normalized key
    # Only one Moss query despite two tool calls (per-session cache).
    assert len(_query_for(assistant, "state-law")) == 1


async def test_retrieve_comparables_filters_type_and_jurisdiction(stub_moss) -> None:
    assistant = Assistant(user_id=USER_ID)
    result = await assistant.retrieve_comparables(
        None, "rear_end", "CA", "medium", "contested"
    )
    assert "$45,000" in result and "$80,000" in result

    calls = _query_for(assistant, "settlements")
    assert len(calls) == 1
    _index, _query, options = calls[0]
    assert options.filter == {
        "$and": [
            {"field": "accident_type", "condition": {"$eq": "rear_end"}},
            {"field": "jurisdiction", "condition": {"$eq": "CA"}},
        ]
    }


async def test_retrieve_matching_firms_ranks_and_gates(stub_moss) -> None:
    assistant = Assistant(user_id=USER_ID)
    assistant._case_data.update(
        {
            "state": "CA",
            "language": "es",
            "accident_type": "rear_end",
            "severity": "medium",
        }
    )

    result = await assistant.retrieve_matching_firms(None, "Orange County")

    # Martinez ranks in; Cohen is gated out by its $100k value floor (est ~$60k).
    assert "Martinez & Associates" in result
    assert "Cohen Law Group" not in result

    # Firm matches were persisted to case data for downstream tools.
    matches = assistant._case_data["moss_firm_matches"]
    assert matches[0]["firm_id"] == "martinez"
    assert any("Spanish" in r for r in matches[0]["match_reasons"])


async def test_retrieve_procedural_guidance_maps_scenario(stub_moss) -> None:
    assistant = Assistant(user_id=USER_ID)
    result = await assistant.retrieve_procedural_guidance(
        None, "what should I do in the first few days?"
    )
    assert "72 hours" in result or "seek care" in result

    calls = _query_for(assistant, "procedures")
    assert len(calls) == 1
    _index, _query, options = calls[0]
    # Free-text scenario normalized to the indexed scenario tag.
    assert options.filter == {
        "field": "scenario",
        "condition": {"$eq": "post_accident_72h"},
    }


# --------------------------------------------------------------------------- #
# Memory tools (unchanged behavior)
# --------------------------------------------------------------------------- #
async def test_save_case_field_adds_doc_with_user_metadata(stub_moss) -> None:
    assistant = Assistant(user_id=USER_ID)
    result = await assistant.save_case_field(None, "accident_type", "rear-end collision")
    assert isinstance(result, str) and result

    assert len(assistant._moss.add_docs_calls) == 1
    index, docs, _options = assistant._moss.add_docs_calls[0]
    assert index == agent_module.MEMORY_INDEX
    assert len(docs) == 1
    doc = docs[0]
    assert doc.text == "accident_type=rear-end collision"
    assert doc.metadata == {
        "user_id": USER_ID,
        "field": "accident_type",
        "source": "tool",
    }
    assert doc.id.startswith(f"{USER_ID}-")


async def test_recall_case_data_filters_by_user_id(stub_moss) -> None:
    room = _FakeRoom()
    assistant = Assistant(room=room, user_id=USER_ID)
    assistant._moss.query_result = _FakeSearchResult(
        [
            _FakeDoc("accident_type=rear-end collision"),
            _FakeDoc("state=CA"),
        ]
    )

    result = await assistant.recall_case_data(None, "what is the accident type?")
    assert result == "accident_type=rear-end collision\nstate=CA"

    calls = _query_for(assistant, agent_module.MEMORY_INDEX)
    assert len(calls) == 1
    _index, _query, options = calls[0]
    assert options.top_k == 8
    assert options.filter == {
        "field": "user_id",
        "condition": {"$eq": USER_ID},
    }

    # recall_case_data does not publish a moss_context packet.
    assert len(room.local_participant.published) == 0
