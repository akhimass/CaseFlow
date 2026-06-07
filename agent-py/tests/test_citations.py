"""Tests for citation extraction + the streaming TTS strip (Part 2)."""

from citations import (
    CITE_RE,
    filter_citation_stream,
    strip_citations,
    validate_citation_id,
)


async def _drain(chunks: list[str]) -> tuple[str, list[str]]:
    """Run chunks through the streaming filter; return (clean_text, cited_ids)."""

    async def source():
        for chunk in chunks:
            yield chunk

    ids: list[str] = []

    async def on_cite(citation_id: str) -> None:
        ids.append(citation_id)

    out = ""
    async for piece in filter_citation_stream(source(), on_cite):
        out += piece
    return out, ids


def test_strip_citations_removes_markers_and_collects_ids() -> None:
    text = (
        "En California tiene dos años [cite:state-law:ca-sol] y casos similares "
        "rondan los $45,000 [cite:settlements:ca-rear-end-med-contested]."
    )
    clean, ids = strip_citations(text)
    assert "[cite:" not in clean
    assert ids == ["state-law:ca-sol", "settlements:ca-rear-end-med-contested"]
    # No doubled spaces or space-before-period left behind.
    assert "  " not in clean
    assert " ." not in clean


def test_validate_citation_id() -> None:
    assert validate_citation_id("settlements:ca-rear-end-med-contested") is True
    assert validate_citation_id("firms:martinez") is True
    assert validate_citation_id("bogus:x") is False  # unknown namespace
    assert validate_citation_id("no-namespace") is False


async def test_stream_strips_inline_markers() -> None:
    clean, ids = await _drain(
        ["Le conecto con Martinez ", "[cite:firms:martinez]", " hoy mismo."]
    )
    assert clean == "Le conecto con Martinez hoy mismo."
    assert ids == ["firms:martinez"]


async def test_stream_marker_split_across_chunks() -> None:
    # The marker is fragmented across four chunks — must still be caught + stripped.
    clean, ids = await _drain(
        [
            "Acuerdos entre $45,000 y $80,000 [cite:set",
            "tlements:ca-rear-",
            "end-med-contested",
            "] segun casos comparables.",
        ]
    )
    assert "[cite:" not in clean
    assert "tlements" not in clean  # no partial leakage
    assert ids == ["settlements:ca-rear-end-med-contested"]
    assert clean.startswith("Acuerdos entre $45,000 y $80,000")
    assert clean.endswith("segun casos comparables.")


async def test_stream_multiple_citations_one_response() -> None:
    clean, ids = await _drain(
        [
            "Dos años para demandar [cite:state-law:ca-sol]. ",
            "Casos similares $45k-$80k [cite:settlements:ca-rear-end-med-contested]. ",
            "Le conecto con Martinez [cite:firms:martinez].",
        ]
    )
    assert "[cite:" not in clean
    assert ids == [
        "state-law:ca-sol",
        "settlements:ca-rear-end-med-contested",
        "firms:martinez",
    ]


async def test_response_with_no_citations_passes_through() -> None:
    clean, ids = await _drain(["Hola, ", "cuenteme ", "que paso."])
    assert clean == "Hola, cuenteme que paso."
    assert ids == []


def test_tool_summary_emits_copyable_marker() -> None:
    """The retrieval tool summaries embed a [cite:<id>] the LLM can copy verbatim."""
    from retrieval import Settlement

    row = Settlement(
        accident_type="rear_end",
        jurisdiction="CA",
        severity="medium",
        fault="contested",
        amount_low=45000,
        amount_high=80000,
        text="OC rear-end MRI disc bulge.",
        score=0.9,
        id="settlements:ca-rear-end-med-contested",
    )
    summary = row.summary()
    match = CITE_RE.search(summary)
    assert match and match.group(1) == "settlements:ca-rear-end-med-contested"
