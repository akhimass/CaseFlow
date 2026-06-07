"""Shared per-session state for AgentSession userdata and multi-agent handoffs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseflowUserdata:
    """Session-scoped case state surfaced via ``AgentSession(userdata=...)``."""

    user_id: str
    case_id: str
    consent_given_at: str | None = None
    caller_location: str = ""
    language: str = "en"
    turn: int = 0
    last_user_utterance: str = ""
    last_agent_utterance: str = ""
    case_data: dict[str, Any] = field(default_factory=dict)

    def seed_location(self, location: str) -> None:
        value = (location or "").strip()
        self.caller_location = value
        if value:
            self.case_data["location"] = value
            self.case_data["caller_location"] = value
