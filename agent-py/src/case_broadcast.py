"""Broadcast live case updates to the firm dashboard."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("agent")


async def publish_case_update(room, case_id: str, event: str, payload: dict[str, Any]) -> None:
    """Publish caseflow_update over LiveKit data channel."""
    if room is None:
        return
    try:
        message = {
            "type": "caseflow_update",
            "data": {
                "case_id": case_id,
                "event": event,
                "payload": payload,
                "timestamp": datetime.now(timezone.utc).timestamp(),
            },
        }
        await room.local_participant.publish_data(
            payload=json.dumps(message, default=str).encode("utf-8"),
            reliable=True,
        )
    except Exception:
        logger.exception("Failed to publish caseflow_update")


async def post_case_update(case_id: str, event: str, payload: dict[str, Any]) -> None:
    """POST case update to the Next.js API for SSE fan-out."""
    base = os.getenv("CASEFLOW_API_URL", "http://localhost:3000").rstrip("/")
    url = f"{base}/api/cases"
    body = {"case_id": case_id, "event": event, "payload": payload}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=body)
    except Exception:
        logger.exception("Failed to POST case update to %s", url)


async def broadcast(room, case_id: str, event: str, payload: dict[str, Any]) -> None:
    await publish_case_update(room, case_id, event, payload)
    await post_case_update(case_id, event, payload)
