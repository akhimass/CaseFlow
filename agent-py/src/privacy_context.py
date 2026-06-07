"""Per-session redaction binding for gateway and persistence helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pii_redaction import RedactionSession

_bound: RedactionSession | None = None


def bind_redaction_session(session: RedactionSession) -> None:
    global _bound
    _bound = session


def get_redaction_session() -> RedactionSession | None:
    return _bound


def clear_redaction_session() -> None:
    global _bound
    _bound = None
