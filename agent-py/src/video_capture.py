"""Request and receive document camera frames for Unsiloed parsing."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger("video_capture")


async def request_enable_video(
    room,
    *,
    case_id: str,
    doc_type: str,
    turn: int,
) -> None:
    """Ask the client UI to turn on camera before document capture."""
    if room is None:
        return
    payload = {
        "type": "enable_video",
        "data": {
            "case_id": case_id,
            "doc_type": doc_type,
            "turn": turn,
            "timestamp": datetime.now(timezone.utc).timestamp(),
        },
    }
    try:
        await room.local_participant.publish_data(
            payload=json.dumps(payload).encode("utf-8"),
            reliable=True,
        )
    except Exception:
        logger.exception("Failed to publish enable_video request")


async def request_document_capture(
    room,
    *,
    case_id: str,
    doc_type: str,
    turn: int,
    matched_phrase: str,
) -> None:
    if room is None:
        return
    payload = {
        "type": "capture_document",
        "data": {
            "case_id": case_id,
            "doc_type": doc_type,
            "turn": turn,
            "matched_phrase": matched_phrase,
            "timestamp": datetime.now(timezone.utc).timestamp(),
        },
    }
    try:
        await room.local_participant.publish_data(
            payload=json.dumps(payload).encode("utf-8"),
            reliable=True,
        )
    except Exception:
        logger.exception("Failed to publish capture_document request")


def parse_data_message(raw: bytes | str) -> dict[str, Any] | None:
    try:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        message = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(message, dict):
        return None
    return message


def setup_document_frame_handler(
    room,
    *,
    on_frame: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    if room is None:
        return

    def _on_data(data_packet) -> None:
        raw = getattr(data_packet, "data", data_packet)
        message = parse_data_message(raw)
        if not message or message.get("type") != "document_frame":
            return
        frame_data = message.get("data")
        if not isinstance(frame_data, dict):
            return
        import asyncio

        asyncio.create_task(on_frame(frame_data))

    room.on("data_received", _on_data)
