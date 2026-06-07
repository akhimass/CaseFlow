"""Tests for city/county → state resolution (geo.state_from_location)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from geo import state_from_location
from slot_extraction import _rules_extract


def test_bare_city_resolves_to_state():
    assert state_from_location("Anaheim") == "CA"
    assert state_from_location("Houston") == "TX"
    assert state_from_location("Miami") == "FL"


def test_county_resolves_to_state():
    assert state_from_location("Orange County") == "CA"
    assert state_from_location("rear-ended in Harris County") == "TX"


def test_explicit_trailing_code_wins():
    assert state_from_location("Anaheim, CA") == "CA"
    assert state_from_location("Springfield, TX") == "TX"


def test_full_state_name():
    assert state_from_location("somewhere in California") == "CA"


def test_unknown_location_returns_none():
    assert state_from_location("") is None
    assert state_from_location("Atlantis") is None


def test_city_in_sentence_is_found():
    assert state_from_location("It happened in Santa Ana near the freeway") == "CA"


def test_slot_extraction_derives_state_from_city():
    slots = _rules_extract("Me chocaron por atrás en Anaheim", "es")
    state_slots = [s for s in slots if s.field_name == "state"]
    assert state_slots, "expected a state slot derived from the city"
    assert state_slots[0].value == "CA"
