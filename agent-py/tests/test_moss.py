"""Unit tests for the agent's three Moss-backed tools.

Unlike the LLM-judged evals in `test_agent.py`, these are deterministic unit
tests that exercise the tool methods directly. They stub `MossClient` via
monkeypatch so they run with no Moss credentials and no network access — the
live, credentialed behavior is validated in the live-test task.
"""

import json

import pytest

import agent as agent_module
from agent import Assistant

USER_ID = "user_42"


class _FakeDoc:
    """Stand-in for a Moss query-result document (`.text/.score/.metadata`)."""

    def __init__(self, text: str, score=None, metadata=None) -> None:
        self.text = text
        self.score = score
        self.metadata = metadata


class _FakeSearchResult:
    """Stand-in for a Moss `SearchResult` (`.docs/.time_taken_ms`)."""

    def __init__(self, docs, time_taken_ms: float = 12.5) -> None:
        self.docs = docs
        self.time_taken_ms = time_taken_ms


class _FakeMossClient:
    """Records calls instead of contacting Moss. Substituted for `MossClient`.

    `MossClient(project_id, project_key)` is constructed inside
    `Assistant.__init__`, so each Assistant gets its own instance, reachable in
    tests as `assistant._moss`.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.load_index_calls: list[str] = []
        self.query_calls: list[tuple] = []
        self.add_docs_calls: list[tuple] = []
        # Default empty result; tests override before invoking a tool.
        self.query_result = _FakeSearchResult([])

    async def load_index(self, name, *args, **kwargs):
        self.load_index_calls.append(name)

    async def query(self, index, query, options=None):
        self.query_calls.append((index, query, options))
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
    """Replace the agent's `MossClient` with the recording fake."""
    monkeypatch.setattr(agent_module, "MossClient", _FakeMossClient)


async def test_search_legal_knowledge_returns_joined_text_and_publishes_context(
    stub_moss, monkeypatch
) -> None:
    """search_legal_knowledge joins snippets and publishes a well-formed payload."""
    async def noop_broadcast(*_args, **_kwargs):
        return None

    monkeypatch.setattr(agent_module, "broadcast", noop_broadcast)

    room = _FakeRoom()
    assistant = Assistant(room=room, user_id=USER_ID)
    assistant._moss.query_result = _FakeSearchResult(
        [
            _FakeDoc("First snippet.", score=0.9, metadata={"source": "docs"}),
            _FakeDoc("Second snippet.", score=0.8),
        ],
        time_taken_ms=7.0,
    )

    result = await assistant.search_legal_knowledge(None, "California statute of limitations")

    # Returns the snippets joined as plain text.
    assert result == "First snippet.\n\nSecond snippet."

    # Queried the knowledge (RAG) index with the user's query.
    assert len(assistant._moss.query_calls) == 1
    index, query, options = assistant._moss.query_calls[0]
    assert index == agent_module.KNOWLEDGE_INDEX
    assert query == "California statute of limitations"
    assert options.top_k == 3

    # Published exactly one moss_context message, reliably.
    assert len(room.local_participant.published) == 1
    payload_bytes, reliable = room.local_participant.published[0]
    assert reliable is True

    payload = json.loads(payload_bytes.decode("utf-8"))
    assert payload["type"] == "moss_context"
    data = payload["data"]
    # Contractual keys consumed by the frontend parser.
    assert set(data) == {"query", "matches", "time_taken_ms", "timestamp"}
    assert data["query"] == "California statute of limitations"
    assert data["time_taken_ms"] == 7.0
    assert isinstance(data["timestamp"], (int, float))

    matches = data["matches"]
    assert len(matches) == 2
    assert matches[0]["text"] == "First snippet."
    assert matches[0]["score"] == 0.9
    assert matches[0]["metadata"] == {"source": "docs"}
    assert matches[1]["text"] == "Second snippet."


async def test_save_case_field_adds_doc_with_user_metadata(stub_moss, monkeypatch) -> None:
    """save_case_field upserts a memory doc tagged with the caller's user_id."""
    async def noop_broadcast(*_args, **_kwargs):
        return None

    monkeypatch.setattr(agent_module, "broadcast", noop_broadcast)

    assistant = Assistant(user_id=USER_ID)

    fact = "rear-end collision"
    result = await assistant.save_case_field(None, "accident_type", fact)
    assert isinstance(result, str) and result

    assert len(assistant._moss.add_docs_calls) == 1
    index, docs, _options = assistant._moss.add_docs_calls[0]
    assert index == agent_module.MEMORY_INDEX
    assert len(docs) == 1

    doc = docs[0]
    assert doc.text == "accident_type=rear-end collision"
    assert doc.metadata == {"user_id": USER_ID, "field": "accident_type"}
    # Document ids are namespaced by user so writes never collide across users.
    assert doc.id.startswith(f"{USER_ID}-")


async def test_recall_case_data_filters_by_user_id(stub_moss, monkeypatch) -> None:
    """recall_case_data scopes the memory query to the caller via a metadata filter."""
    async def noop_broadcast(*_args, **_kwargs):
        return None

    monkeypatch.setattr(agent_module, "broadcast", noop_broadcast)

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

    assert len(assistant._moss.query_calls) == 1
    index, query, options = assistant._moss.query_calls[0]
    assert index == agent_module.MEMORY_INDEX
    assert query == "what is the accident type?"
    assert options.top_k == 8
    # Per-user isolation: the filter must pin user_id to this caller.
    assert options.filter == {
        "field": "user_id",
        "condition": {"$eq": USER_ID},
    }

    # recall_case_data does not publish moss_context (no recall panel push).
    assert len(room.local_participant.published) == 0
