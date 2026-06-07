import pytest

from doc_intent import DocumentCaptureCoordinator, detect_document_intent
from slot_extraction import _rules_extract, slots_above_threshold


def test_rules_extract_maria_spanish_fault() -> None:
    slots = _rules_extract(
        "El otro conductor pasó la luz roja y tengo latigazo cervical",
        "es",
    )
    fields = {slot.field_name: slot.value for slot in slots}
    assert "fault_claim" in fields
    assert "injuries" in fields


def test_detect_police_report_intent() -> None:
    intent = detect_document_intent("Tengo el reporte policial aquí en la mano")
    assert intent is not None
    assert intent.doc_type == "police_report"


def test_document_capture_cooldown() -> None:
    coordinator = DocumentCaptureCoordinator()
    assert coordinator.should_capture("police_report") is True
    assert coordinator.should_capture("police_report") is False


def test_slots_above_threshold() -> None:
    slots = _rules_extract("Rear-ended in California on June 1 2026", "en")
    high = slots_above_threshold(slots)
    assert all(slot.confidence >= 0.75 for slot in high)
