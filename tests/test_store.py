"""Top-k, persistence, filtering, and refusing a mismatched model.

Vectors here are hand-constructed at known angles rather than embedded, so an
ordering failure means the search is wrong rather than the model being weak.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import make_chunk

from recall.indexing.store import (
    Duplicate,
    IndexEntry,
    IndexMismatch,
    NumpyStore,
    index_size_bytes,
)
from recall.ingestion.models import DECK, PROBLEM_SHEET, Locator


def unit(degrees: float) -> np.ndarray:
    radians = math.radians(degrees)
    return np.array([math.cos(radians), math.sin(radians)], dtype=np.float32)


@pytest.fixture
def angled_store() -> NumpyStore:
    """Four entries at known angles from the query direction at 0 degrees."""
    labels = [("near", 10.0), ("mid", 40.0), ("far", 80.0), ("opposite", 175.0)]
    entries = [
        IndexEntry(chunk=make_chunk(text=name, pages=(i + 1,)))
        for i, (name, _) in enumerate(labels)
    ]
    vectors = np.stack([unit(angle) for _, angle in labels])
    return NumpyStore(entries, vectors, embedder_name="angles-2")


def test_results_come_back_closest_first(angled_store):
    hits = angled_store.search(unit(0.0), k=4)
    assert [h.text for h in hits] == ["near", "mid", "far", "opposite"]
    assert hits[0].score > hits[-1].score


def test_scores_are_cosine_of_the_known_angle(angled_store):
    hits = angled_store.search(unit(0.0), k=1)
    assert hits[0].score == pytest.approx(math.cos(math.radians(10.0)), abs=1e-6)


def test_k_larger_than_the_index_returns_everything_once(angled_store):
    hits = angled_store.search(unit(0.0), k=99)
    assert len(hits) == 4
    assert len({h.chunk_id for h in hits}) == 4


def test_k_of_zero_returns_nothing(angled_store):
    assert angled_store.search(unit(0.0), k=0) == []


def test_hits_are_addressed_by_chunk_id_and_citation_never_by_row(angled_store):
    hit = angled_store.search(unit(0.0), k=1)[0]
    assert hit.chunk_id == angled_store.entries[0].chunk_id
    assert "slide 1" in hit.citations()[0]


def test_a_filter_narrows_the_candidates():
    entries = [
        IndexEntry(chunk=make_chunk(text="slide", doc_type=DECK)),
        IndexEntry(
            chunk=make_chunk(
                text="problem", doc_type=PROBLEM_SHEET, source_file="hw1.pdf"
            )
        ),
    ]
    store = NumpyStore(entries, np.stack([unit(0.0), unit(1.0)]), embedder_name="a-2")

    assert len(store.search(unit(0.0), k=5)) == 2
    assert [h.text for h in store.search(unit(0.0), k=5, doc_type=PROBLEM_SHEET)] == [
        "problem"
    ]
    assert [
        h.text for h in store.search(unit(0.0), k=5, source_file="hw1.pdf")
    ] == ["problem"]


def test_a_filter_matching_nothing_returns_empty_not_an_error(angled_store):
    """Module 6's not-found questions depend on this path being clean."""
    assert angled_store.search(unit(0.0), k=5, doc_type="no_such_type") == []


def test_an_empty_index_returns_empty():
    store = NumpyStore([], np.zeros((0, 4), dtype=np.float32), embedder_name="a-4")
    assert store.search(np.zeros(4, dtype=np.float32)) == []


def test_round_trip_through_disk_is_identical(angled_store, tmp_path):
    angled_store.save(tmp_path)
    loaded = NumpyStore.load(tmp_path)

    assert loaded.embedder_name == angled_store.embedder_name
    assert loaded.dim == angled_store.dim
    assert len(loaded) == len(angled_store)
    before = angled_store.search(unit(0.0), k=4)
    after = loaded.search(unit(0.0), k=4)
    assert [h.chunk_id for h in before] == [h.chunk_id for h in after]
    assert [h.score for h in before] == [h.score for h in after]
    assert index_size_bytes(tmp_path) > 0


def test_duplicate_locations_survive_the_round_trip(tmp_path):
    entry = IndexEntry(
        chunk=make_chunk(text="shared", source_file="lecture.pdf"),
        duplicates=(
            Duplicate(
                source_file="week.pdf",
                locator=Locator(kind=DECK, pages=(7,), title="Elsewhere"),
            ),
        ),
    )
    NumpyStore([entry], unit(0.0).reshape(1, 2), embedder_name="a-2").save(tmp_path)
    citations = NumpyStore.load(tmp_path).entries[0].citations()

    assert len(citations) == 2
    assert "lecture.pdf" in citations[0]
    assert "week.pdf" in citations[1]


def test_a_different_model_is_refused_rather_than_scored(angled_store, fake_embedder):
    with pytest.raises(IndexMismatch, match="angles-2"):
        angled_store.check_embedder(fake_embedder)


def test_a_dimension_mismatch_is_refused(angled_store):
    class SameNameWiderModel:
        name = "angles-2"
        dim = 99

    with pytest.raises(IndexMismatch, match="dimensions"):
        angled_store.check_embedder(SameNameWiderModel())


def test_a_query_of_the_wrong_width_is_refused(angled_store):
    with pytest.raises(IndexMismatch, match="dimensions"):
        angled_store.search(np.zeros(7, dtype=np.float32))


def test_loading_checks_the_embedder_when_given_one(angled_store, tmp_path, fake_embedder):
    angled_store.save(tmp_path)
    with pytest.raises(IndexMismatch):
        NumpyStore.load(tmp_path, embedder=fake_embedder)


def test_entries_and_vectors_must_line_up():
    with pytest.raises(ValueError, match="1 entries but 2 vectors"):
        NumpyStore(
            [IndexEntry(chunk=make_chunk(text="one"))],
            np.stack([unit(0.0), unit(1.0)]),
            embedder_name="a-2",
        )
