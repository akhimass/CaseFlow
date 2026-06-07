"""Map a free-text location ("Anaheim", "Orange County, CA") to a US state code.

The intake agent often hears a city or county without the state — Maria says she
was rear-ended in Anaheim, not "Anaheim, California." This resolver lets the agent
fire Moss state-law retrieval the moment a location is mentioned, instead of
waiting for the caller to spell out the state.
"""

from __future__ import annotations

import re

# Two-letter codes Caseflow has jurisdictional Moss coverage for.
COVERED_STATES: frozenset[str] = frozenset({"CA", "TX", "FL", "AZ", "NV", "NY"})

# Full state names + a few aliases → two-letter code. Extend as coverage grows.
STATE_NAMES: dict[str, str] = {
    "california": "CA",
    "texas": "TX",
    "florida": "FL",
    "arizona": "AZ",
    "nevada": "NV",
    "new york": "NY",
}

# County → state. Counties are common in police reports ("Orange County").
COUNTIES: dict[str, str] = {
    "orange county": "CA",
    "los angeles county": "CA",
    "san diego county": "CA",
    "riverside county": "CA",
    "san bernardino county": "CA",
    "alameda county": "CA",
    "santa clara county": "CA",
    "sacramento county": "CA",
    "harris county": "TX",
    "dallas county": "TX",
    "travis county": "TX",
    "bexar county": "TX",
    "miami-dade county": "FL",
    "broward county": "FL",
    "orange county fl": "FL",  # disambiguate FL's Orange County when spelled out
}

# City → state. Demo-weighted toward California (Orange County rear-end), plus the
# largest cities of the other covered jurisdictions.
CITIES: dict[str, str] = {
    # California
    "anaheim": "CA",
    "santa ana": "CA",
    "irvine": "CA",
    "huntington beach": "CA",
    "fullerton": "CA",
    "garden grove": "CA",
    "costa mesa": "CA",
    "newport beach": "CA",
    "los angeles": "CA",
    "san diego": "CA",
    "san francisco": "CA",
    "san jose": "CA",
    "sacramento": "CA",
    "fresno": "CA",
    "long beach": "CA",
    "oakland": "CA",
    "bakersfield": "CA",
    "riverside": "CA",
    "stockton": "CA",
    "chula vista": "CA",
    # Texas
    "houston": "TX",
    "dallas": "TX",
    "austin": "TX",
    "san antonio": "TX",
    "fort worth": "TX",
    "el paso": "TX",
    "arlington": "TX",
    # Florida
    "miami": "FL",
    "orlando": "FL",
    "tampa": "FL",
    "jacksonville": "FL",
    "fort lauderdale": "FL",
    "st. petersburg": "FL",
    "st petersburg": "FL",
}


def state_from_location(location: str) -> str | None:
    """Best-effort two-letter state code from a free-text location string.

    Resolution order, most specific first:
    1. An explicit ", CA"-style trailing code.
    2. A county name.
    3. A city name.
    4. A full state name or alias.
    """
    text = (location or "").strip()
    if not text:
        return None

    # 1. Explicit trailing two-letter code: "Anaheim, CA".
    match = re.search(r",\s*([A-Za-z]{2})\b", text)
    if match:
        code = match.group(1).upper()
        if code in COVERED_STATES:
            return code

    lowered = text.lower()

    # 2. Counties (check before cities so "Orange County" wins over a city map).
    for county, code in COUNTIES.items():
        if county in lowered:
            return code

    # 3. Cities — word-boundary match so "san jose" doesn't match inside a longer token.
    for city, code in CITIES.items():
        if re.search(rf"\b{re.escape(city)}\b", lowered):
            return code

    # 4. Full state names / aliases.
    for name, code in STATE_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            return code

    return None
