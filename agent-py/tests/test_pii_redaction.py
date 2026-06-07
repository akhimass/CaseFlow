import pytest

from pii_redaction import RedactionSession, Redactor, moss_field_value, redact_json_values


def test_redact_phone_and_unredact():
    session = RedactionSession()
    redactor = Redactor(session)
    text = "Call me at (714) 555-0142 tomorrow."
    redacted, mapping = redactor.redact(text, "en")
    assert "(714)" not in redacted
    assert "[CF_PHONE_" in redacted
    restored = redactor.unredact(redacted)
    assert "714" in restored


def test_redact_spanish_name():
    session = RedactionSession()
    redactor = Redactor(session)
    text = "Me llamo Maria Delgado y vivo en Anaheim."
    redacted, _ = redactor.redact(text, "es")
    assert "Maria" not in redacted
    assert "Delgado" not in redacted


def test_moss_field_redacts_caller_name():
    session = RedactionSession()
    value = moss_field_value("caller_name", "Maria Delgado", session=session, language="es")
    assert "Maria" not in value
    assert "[CF_NAME_" in value


def test_redact_json_nested():
    session = RedactionSession()
    payload = {
        "police_report": {
            "driver_name": "John Smith",
            "plate": "ABC1234",
        }
    }
    out = redact_json_values(payload, session=session, language="en")
    blob = str(out)
    assert "John Smith" not in blob


def test_embedded_phone_redacts_in_free_text():
    session = RedactionSession()
    redactor = Redactor(session)
    text = "rear_end contact 555-123-4567"
    redacted, _ = redactor.redact(text, "en")
    assert "[CF_PHONE_" in redacted
    assert "555-123" not in redacted
