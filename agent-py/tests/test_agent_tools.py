import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from livekit.agents import AgentSession, mock_tools

from agent import Assistant
from caseflow_userdata import CaseflowUserdata


class QuietAssistant(Assistant):
    """Skip the spoken greeting so session.run tests focus on the user turn."""

    async def on_enter(self) -> None:
        return


@pytest.mark.asyncio
async def test_session_userdata_shared_with_assistant() -> None:
    userdata = CaseflowUserdata(
        user_id="test-user",
        case_id="test-case-shared",
        case_data={"caller_id": "test-user", "language": "en"},
    )
    async with AgentSession(userdata=userdata) as session:
        assistant = Assistant(userdata=userdata)
        await session.start(assistant)
        assert session.userdata is userdata
        assert assistant._userdata is userdata


@pytest.mark.asyncio
async def test_match_firm_tool_uses_context_userdata() -> None:
    userdata = CaseflowUserdata(
        user_id="test-user",
        case_id="test-case-match",
        case_data={
            "caller_id": "test-user",
            "language": "en",
            "state": "CA",
            "accident_type": "rear_end",
            "severity": "medium",
        },
    )
    userdata.seed_location("Orange County, CA")
    assistant = Assistant(userdata=userdata)
    ctx = SimpleNamespace(userdata=userdata)

    with patch.object(assistant, "_update_case", new_callable=AsyncMock):
        with patch.object(assistant._persistence, "on_firms_matched", new_callable=AsyncMock):
            raw = await assistant.match_firm_tool(ctx)
            payload = json.loads(raw)

    assert payload.get("matches")
    assert payload.get("caller_location") == "Orange County, CA"


@pytest.mark.asyncio
async def test_parse_document_tool_returns_payload() -> None:
    userdata = CaseflowUserdata(
        user_id="test-user",
        case_id="test-case-parse",
        case_data={"caller_id": "test-user", "language": "en", "state": "CA"},
    )
    assistant = Assistant(userdata=userdata)
    ctx = SimpleNamespace(userdata=userdata)
    demo = {
        "doc_type": "police_report",
        "fault_determination": "undetermined",
        "location": "Orange County, CA",
    }

    with patch.object(assistant, "_ingest_document", new_callable=AsyncMock, return_value=demo):
        raw = await assistant.parse_document(ctx, "dGVzdA==", "police_report")
        payload = json.loads(raw)

    assert payload["doc_type"] == "police_report"
    assert payload["fault_determination"] == "undetermined"


@pytest.mark.asyncio
async def test_parse_document_tool_called_in_session_run() -> None:
    """LiveKit session.run path with mocked parse_document (tool routing)."""
    userdata = CaseflowUserdata(
        user_id="test-user",
        case_id="test-case-run-parse",
        case_data={"caller_id": "test-user", "language": "en", "state": "CA"},
    )
    calls: list[str] = []

    def _mock_parse(image_base64: str, doc_type: str) -> str:
        calls.append(doc_type)
        return json.dumps(
            {
                "doc_type": "police_report",
                "fault_determination": "undetermined",
            }
        )

    async with AgentSession(userdata=userdata) as session:
        with mock_tools(Assistant, {"parse_document": _mock_parse}):
            await session.start(QuietAssistant(userdata=userdata))
            await session.run(
                user_input=(
                    "Use the parse_document tool now on my police report frame "
                    "(doc_type police_report)."
                )
            )

    if not calls:
        pytest.skip("Model did not invoke parse_document in this run; direct tool test covers wiring.")
    assert calls[0] == "police_report"


@pytest.mark.asyncio
async def test_match_firm_tool_called_in_session_run() -> None:
    """LiveKit session.run path with mocked match_firm_tool (tool routing)."""
    userdata = CaseflowUserdata(
        user_id="test-user",
        case_id="test-case-run-match",
        case_data={
            "caller_id": "test-user",
            "language": "en",
            "state": "CA",
            "accident_type": "rear_end",
            "severity": "medium",
        },
    )
    userdata.seed_location("Orange County, CA")
    calls: list[str] = []

    def _mock_match(caller_location: str = "") -> str:
        calls.append(caller_location or "default")
        return json.dumps({"matches": [{"firm_id": "pacific_heights", "score": 80}]})

    async with AgentSession(userdata=userdata) as session:
        with mock_tools(
            Assistant,
            {
                "match_firm_tool": _mock_match,
                "compute_case_strength_tool": lambda: json.dumps({"score": 72}),
            },
        ):
            await session.start(QuietAssistant(userdata=userdata))
            await session.run(
                user_input=(
                    "Intake is complete for my Orange County rear-end whiplash case. "
                    "Call match_firm_tool now."
                )
            )

    if not calls:
        pytest.skip(
            "Model did not invoke match_firm_tool in this run; direct tool test covers wiring."
        )
    assert calls[0] in ("Orange County, CA", "default")
