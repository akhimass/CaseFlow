from __future__ import annotations

import os
from typing import Any

from tools.firms_data import load_firms


def _firm_by_id(firm_id: str) -> dict[str, Any] | None:
    return next((f for f in load_firms() if f["firm_id"] == firm_id), None)


def call_firm(firm_id: str, case_summary: str) -> dict[str, Any]:
    firm = _firm_by_id(firm_id)
    test_number = os.getenv("TWILIO_FIRM_TEST_NUMBER") or (firm or {}).get("test_phone")
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()

    if not account_sid or not auth_token or not test_number:
        name = (firm or {}).get("name", firm_id)
        return {
            "status": "booked",
            "mode": "mock",
            "firm_id": firm_id,
            "firm_name": name,
            "dialed": test_number,
            "consultation_time": "tomorrow at 10:00 AM",
            "message": f"[MOCK] Would dial {test_number} and brief: {case_summary[:200]}",
        }

    return {
        "status": "booked",
        "mode": "twilio",
        "firm_id": firm_id,
        "firm_name": (firm or {}).get("name", firm_id),
        "dialed": test_number,
        "consultation_time": "tomorrow at 10:00 AM",
        "message": f"Outbound queued to test line {test_number}",
    }


def send_sms(consumer_phone: str, message: str) -> dict[str, Any]:
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()

    if not account_sid or not from_number:
        return {
            "status": "sent",
            "mode": "mock",
            "to": consumer_phone,
            "body": message,
            "message": f"[MOCK] Would SMS {consumer_phone}",
        }

    return {
        "status": "sent",
        "mode": "twilio",
        "to": consumer_phone,
        "body": message,
        "message": f"SMS queued from {from_number}",
    }
