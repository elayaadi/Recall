"""Retrieval end to end: abstention, collapse, filters — with no model.

SPEC.md 4b makes abstention an outcome rather than an empty list, so both the
refusal and the reason it gives are asserted here.
"""

from __future__ import annotations

import numpy as np
import pytest
from conftest import FakeEmbedder, make_chunk

from recall.indexing.build import build_index
from recall.indexing.store import IndexMismatch
from recall.ingestion.models import DECK, PROBLEM_SHEET
from recall.retrieval.retriever import Retriever


@pytest.fixture
def store(fake_embedder):
    chunks = [
        make_chunk(text="routers hold packets in an output queue", pages=(1,)),
        make_chunk(text="TCP halves its congestion window on loss", pages=(2,)),
        make_chunk(text="a web cache serves repeated requests locally", pages=(3,)),
        make_chunk(
            text="compute the propagation delay of the link",
            doc_type=PROBLEM_SHEET, source_file="homework 1.pdf",
        ),
    ]
    return build_index(chunks, fake_embedder)


def test_an_exact_query_returns_its_own_chunk_first(store, fake_embedder):
    r = Retriever(store, fake_embedder, abstain_threshold=0.5)
    result = r.retrieve("TCP halves its congestion window on loss")

    assert result
    assert not result.abstained
    assert result.hits[0].text == "TCP halves its congestion window on loss"
    assert result.best_score == pytest.approx(1.0, abs=1e-5)


def test_a_low_scoring_query_abstains_with_a_reason(store, fake_embedder):
    r = Retriever(store, fake_embedder, abstain_threshold=0.99)
    result = r.retrieve("something entirely unrelated to this corpus")

    assert result.abstained
    assert not result
    assert result.hits == []
    assert "below threshold" in result.reason
    assert result.best_score is not None


def test_the_threshold_is_the_only_thing_separating_the_two(store, fake_embedder):
    """Same query, two thresholds — abstention is a decision, not a lack of results."""
    query = "routers hold packets in an output queue"
    assert not Retriever(store, fake_embedder, abstain_threshold=0.5).retrieve(query).abstained
    assert Retriever(store, fake_embedder, abstain_threshold=1.01).retrieve(query).abstained


def test_an_empty_query_abstains_without_searching(store, fake_embedder):
    result = Retriever(store, fake_embedder).retrieve("   ")
    assert result.abstained
    assert result.reason == "empty query"


def test_a_filter_matching_nothing_abstains_cleanly(store, fake_embedder):
    result = Retriever(store, fake_embedder, abstain_threshold=0.0).retrieve(
        "anything", doc_type="no_such_type"
    )
    assert result.abstained
    assert "filter" in result.reason


def test_filters_are_passed_through(store, fake_embedder):
    r = Retriever(store, fake_embedder, abstain_threshold=0.0, k=5)
    hits = r.retrieve("delay", doc_type=PROBLEM_SHEET).hits
    assert [h.entry.chunk.doc_type for h in hits] == [PROBLEM_SHEET]


def test_k_bounds_the_returned_list(store, fake_embedder):
    r = Retriever(store, fake_embedder, abstain_threshold=0.0, k=2)
    assert len(r.retrieve("routers").hits) == 2


def test_near_duplicates_are_collapsed_and_counted(fake_embedder):
    """The Week/Lecture case: one body, two titles, one slot."""
    body = "a CDN redirects the client to a nearby replica"
    chunks = [
        make_chunk(text=f"A\n\n{body}", raw_text=body, source_file="lecture.pdf"),
        make_chunk(text=f"A\n\n{body}", raw_text=body, source_file="week.pdf"),
        make_chunk(text="an unrelated passage about queueing", source_file="other.pdf"),
    ]
    store = build_index(chunks, fake_embedder)
    # §3d already collapses the identical bodies at index time.
    assert len(store) == 2

    result = Retriever(store, fake_embedder, abstain_threshold=0.0).retrieve(f"A\n\n{body}")
    assert len(result.hits[0].citations()) == 2


def test_collapse_can_be_switched_off_by_its_threshold(fake_embedder):
    chunks = [make_chunk(text=f"passage {i}", source_file=f"{i}.pdf") for i in range(3)]
    store = build_index(chunks, fake_embedder)

    loose = Retriever(store, fake_embedder, abstain_threshold=0.0, collapse_threshold=-1.0)
    assert len(loose.retrieve("passage 0").hits) == 1
    assert loose.retrieve("passage 0").collapsed == 2

    strict = Retriever(store, fake_embedder, abstain_threshold=0.0, collapse_threshold=1.01)
    assert strict.retrieve("passage 0").collapsed == 0


def test_a_retriever_refuses_a_store_built_by_another_model(store):
    with pytest.raises(IndexMismatch):
        Retriever(store, FakeEmbedder(name="different", dim=16))


def test_thresholds_are_instance_state_not_shared(store, fake_embedder):
    """They are calibrated per corpus and embedder, so they cannot be global."""
    a = Retriever(store, fake_embedder, abstain_threshold=0.1)
    b = Retriever(store, fake_embedder, abstain_threshold=0.9)
    assert (a.abstain_threshold, b.abstain_threshold) == (0.1, 0.9)
