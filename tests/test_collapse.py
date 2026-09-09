"""Collapsing near-duplicate results without losing where they came from.

Vectors are hand-constructed at known angles, so a failure here means the
collapse rule is wrong rather than the embedding model being weak.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import make_chunk

from recall.indexing.store import Duplicate, IndexEntry, SearchHit
from recall.ingestion.models import DECK, Locator
from recall.retrieval.collapse import collapse_near_duplicates


def unit(degrees: float) -> np.ndarray:
    r = math.radians(degrees)
    return np.array([math.cos(r), math.sin(r)], dtype=np.float32)


def hit(name: str, score: float, source: str = "a.pdf", page: int = 1) -> SearchHit:
    return SearchHit(
        entry=IndexEntry(chunk=make_chunk(text=name, source_file=source, pages=(page,))),
        score=score,
    )


def test_distinct_results_are_all_kept():
    hits = [hit("one", 0.9), hit("two", 0.8), hit("three", 0.7)]
    vectors = np.stack([unit(0), unit(60), unit(120)])
    assert len(collapse_near_duplicates(hits, vectors, 0.95)) == 3


def test_a_near_duplicate_is_absorbed_by_the_higher_scoring_result():
    hits = [hit("keep", 0.9, "lecture.pdf", 6), hit("dupe", 0.88, "week.pdf", 11)]
    vectors = np.stack([unit(0), unit(2)])  # cos 2 degrees ~ 0.999
    out = collapse_near_duplicates(hits, vectors, 0.95)

    assert len(out) == 1
    assert out[0].text == "keep"
    assert out[0].score == 0.9


def test_the_absorbed_location_survives_as_a_citation():
    """Merging, not dropping — the passage really is in both decks."""
    hits = [hit("shared", 0.9, "lecture.pdf", 6), hit("shared", 0.88, "week.pdf", 11)]
    citations = collapse_near_duplicates(hits, np.stack([unit(0), unit(1)]), 0.95)[0].citations()

    assert len(citations) == 2
    assert "lecture.pdf" in citations[0]
    assert "week.pdf" in citations[1]


def test_duplicates_the_absorbed_result_already_carried_are_kept_too():
    """A collapsed entry can already stand for several locations, from §3d."""
    second = SearchHit(
        entry=IndexEntry(
            chunk=make_chunk(text="shared", source_file="week.pdf"),
            duplicates=(
                Duplicate("review.pdf", Locator(kind=DECK, pages=(3,), title="t")),
            ),
        ),
        score=0.88,
    )
    hits = [hit("shared", 0.9, "lecture.pdf"), second]
    citations = collapse_near_duplicates(hits, np.stack([unit(0), unit(1)]), 0.95)[0].citations()

    assert [c.split(",")[0] for c in citations] == ["lecture.pdf", "week.pdf", "review.pdf"]


def test_the_threshold_is_respected():
    hits = [hit("a", 0.9), hit("b", 0.8)]
    vectors = np.stack([unit(0), unit(25)])  # cos 25 degrees ~ 0.906
    assert len(collapse_near_duplicates(hits, vectors, 0.95)) == 2
    assert len(collapse_near_duplicates(hits, vectors, 0.90)) == 1


def test_rank_order_is_never_changed():
    hits = [hit("a", 0.9), hit("b", 0.7), hit("c", 0.5)]
    vectors = np.stack([unit(0), unit(90), unit(45)])
    assert [h.text for h in collapse_near_duplicates(hits, vectors, 0.99)] == ["a", "b", "c"]


def test_three_copies_collapse_into_one_carrying_all_three():
    hits = [hit("x", 0.9, "a.pdf"), hit("x", 0.8, "b.pdf"), hit("x", 0.7, "c.pdf")]
    vectors = np.stack([unit(0), unit(1), unit(2)])
    out = collapse_near_duplicates(hits, vectors, 0.95)

    assert len(out) == 1
    assert len(out[0].citations()) == 3


def test_an_empty_result_list_collapses_to_nothing():
    assert collapse_near_duplicates([], np.zeros((0, 2), dtype=np.float32), 0.95) == []


def test_hits_and_vectors_must_line_up():
    with pytest.raises(ValueError, match="1 hits but 2 vectors"):
        collapse_near_duplicates([hit("a", 0.9)], np.stack([unit(0), unit(1)]), 0.95)
