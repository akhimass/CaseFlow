"""Citation markers — extraction and streaming strip for live source grounding.

Aria emits inline ``[cite:<namespace>:<docid>]`` markers in her spoken text when a
statement is grounded in a Moss retrieval result. These markers must be:

* stripped from the text before it reaches MiniMax TTS (the caller never hears them), and
* surfaced as ``cited_source`` events so the firm dashboard can pulse the card that
  grounded the fact.

The streaming filter is the tricky part: LLM output arrives in arbitrary chunks, so a
marker like ``[cite:settlements:ca-rear-end-med-contested]`` can be split across
several chunks. :func:`filter_citation_stream` buffers just enough to never emit a
partial marker, while keeping latency low (it flushes everything up to the last
unclosed ``[``).
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable

logger = logging.getLogger("citations")

# A citation id is namespace:docid, e.g. settlements:ca-rear-end-med-contested.
CITE_RE = re.compile(r"\[cite:\s*([a-z0-9][a-z0-9_\-]*:[a-z0-9][a-z0-9_\-]*)\s*\]", re.I)

# Recognized namespaces — used to warn on malformed ids without breaking the call.
KNOWN_NAMESPACES = {"state-law", "settlements", "firms", "procedures"}

OnCite = Callable[[str], Awaitable[None]]


def strip_citations(text: str) -> tuple[str, list[str]]:
    """Strip all citation markers from a full string.

    Returns the cleaned text (whitespace tidied around removed markers) and the list
    of citation ids in order of appearance (duplicates preserved).
    """
    ids: list[str] = []

    def _take(match: re.Match[str]) -> str:
        ids.append(match.group(1).strip())
        return ""

    cleaned = CITE_RE.sub(_take, text)
    # Collapse doubled spaces / space-before-punctuation left by removed markers.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip(), ids


def validate_citation_id(citation_id: str) -> bool:
    """True if the id is well-formed and uses a known namespace."""
    namespace, _, docid = citation_id.partition(":")
    if not docid:
        return False
    if namespace not in KNOWN_NAMESPACES:
        logger.warning("citation id has unknown namespace: %r", citation_id)
        return False
    return True


async def filter_citation_stream(
    source: AsyncIterable[str],
    on_cite: OnCite,
) -> AsyncIterator[str]:
    """Yield text with citation markers removed, invoking ``on_cite`` per marker.

    Buffers across chunk boundaries so a marker split over multiple chunks is still
    caught. Flushes everything up to the last unclosed ``[`` as soon as it arrives,
    so audio is never delayed waiting for more text.
    """
    buffer = ""
    prev_space = False  # did the last emitted text end on a space?

    def _normalize(piece: str) -> str:
        """Collapse whitespace a removed marker leaves, across yield boundaries."""
        nonlocal prev_space
        piece = re.sub(r"[ \t]{2,}", " ", piece)
        if prev_space:
            piece = piece.lstrip(" \t")
        if piece:
            prev_space = piece[-1] in " \t"
        return piece

    async for chunk in source:
        if not chunk:
            continue
        buffer += chunk

        # Remove every complete marker currently in the buffer, firing callbacks.
        while True:
            match = CITE_RE.search(buffer)
            if not match:
                break
            await _safe_on_cite(on_cite, match.group(1).strip())
            before, after = buffer[: match.start()], buffer[match.end() :]
            if before.endswith(" ") and after[:1] in ",.;:!?":
                before = before[:-1]  # drop space orphaned before punctuation
            buffer = before + after

        # Flush everything up to the last '[' (a possible partial marker start).
        cut = buffer.rfind("[")
        if cut == -1:
            piece = _normalize(buffer)
            if piece:
                yield piece
            buffer = ""
        elif cut > 0:
            piece = _normalize(buffer[:cut])
            if piece:
                yield piece
            buffer = buffer[cut:]
        # cut == 0: the buffer begins with a possible partial marker; hold it.

    # End of stream: a leftover '[...' that never closed is literal text — emit it,
    # but run a final strip in case a complete marker is sitting in the tail.
    if buffer:
        cleaned, ids = strip_citations(buffer)
        for citation_id in ids:
            await _safe_on_cite(on_cite, citation_id)
        piece = _normalize(cleaned)
        if piece:
            yield piece


async def _safe_on_cite(on_cite: OnCite, citation_id: str) -> None:
    validate_citation_id(citation_id)  # logs a warning on malformed ids
    try:
        await on_cite(citation_id)
    except Exception:
        logger.exception("cited_source emit failed for %r", citation_id)
