"""Tests for the lawyer-feedback learning loop (aggregate + retrieval re-rank)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from feedback_store import aggregate_scores
from retrieval import Retriever


class _Row:
    def __init__(self, id, score):
        self.id = id
        self.score = score


def test_aggregate_scores_nets_votes():
    rows = [
        {"source_id": "state-law:ca-sol", "helpful": True},
        {"source_id": "state-law:ca-sol", "helpful": True},
        {"source_id": "state-law:ca-sol", "helpful": False},
        {"source_id": "settlements:x", "helpful": False},
    ]
    scores = aggregate_scores(rows)
    assert scores["state-law:ca-sol"] == 1  # +1 +1 -1
    assert scores["settlements:x"] == -1


def test_rerank_promotes_feedback_validated_source():
    # Two rows: B has a slightly higher raw score, but A has strong feedback.
    rows = [_Row("settlements:a", 0.80), _Row("settlements:b", 0.85)]
    r = Retriever(object(), feedback_scores={"settlements:a": 3})
    ranked = r._rerank(rows)
    assert ranked[0].id == "settlements:a"  # feedback boost lifts A above B


def test_rerank_noop_without_feedback():
    rows = [_Row("x", 0.5), _Row("y", 0.9)]
    r = Retriever(object())  # no feedback
    assert r._rerank(rows) == rows  # unchanged order


def test_negative_feedback_demotes():
    rows = [_Row("a", 0.9), _Row("b", 0.85)]
    r = Retriever(object(), feedback_scores={"a": -3})
    ranked = r._rerank(rows)
    assert ranked[0].id == "b"
