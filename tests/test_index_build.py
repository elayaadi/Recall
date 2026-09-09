"""Deduplication, and building an index end to end without a model.

SPEC.md 3d settled that identity is the byte-identical `raw_text` rather than
the embedded `text`. The distinction is the whole decision, so it is pinned
here: the same body under two different titles is one entry, and a different
body under one title is two.
"""

from __future__ import annotations

import numpy as np
from conftest import make_chunk

from recall.indexing.build import build_index, deduplicate
from recall.indexing.cache import EmbeddingCache
from recall.indexing.store import NumpyStore
from recall.ingestion.models import DECK, PROBLEM_SHEET


def test_distinct_bodies_are_kept_apart():
    chunks = [make_chunk(text="one"), make_chunk(text="two")]
    assert len(deduplicate(chunks)) == 2


def test_the_same_body_under_two_titles_is_one_entry():
    """The Week/Lecture case from SPEC.md 3d, in miniature."""
    body = "A CDN redirects the client to a nearby replica."
    chunks = [
        make_chunk(
            text=f"CDN content access: a closer look\n\n{body}",
            raw_text=body,
            source_file="cs447 Lecture 13.pdf",
            pages=(4,),
            title="CDN content access: a closer look",
        ),
        make_chunk(
            text=f"CDN content access: DNS redirection\n\n{body}",
            raw_text=body,
            source_file="Week 5 On-line.pdf",
            pages=(9,),
            title="CDN content access: DNS redirection",
        ),
    ]
    entries = deduplicate(chunks)

    assert len(entries) == 1
    assert entries[0].chunk.source_file == "cs447 Lecture 13.pdf"
    assert len(entries[0].duplicates) == 1


def test_deduplicating_on_the_embedded_text_would_have_missed_it():
    """Guards the decision itself, not just its implementation."""
    body = "shared body"
    chunks = [
        make_chunk(text=f"Title A\n\n{body}", raw_text=body, source_file="a.pdf"),
        make_chunk(text=f"Title B\n\n{body}", raw_text=body, source_file="b.pdf"),
    ]
    assert len({c.text for c in chunks}) == 2
    assert len(deduplicate(chunks)) == 1


def test_every_location_survives_as_a_citation():
    body = "queueing delay grows with the arrival rate"
    chunks = [
        make_chunk(text=body, source_file="lecture.pdf", pages=(6,)),
        make_chunk(text=body, source_file="week.pdf", pages=(11,)),
        make_chunk(text=body, source_file="review.pdf", pages=(2,)),
    ]
    citations = deduplicate(chunks)[0].citations()

    assert len(citations) == 3
    assert [c.split(",")[0] for c in citations] == [
        "lecture.pdf",
        "week.pdf",
        "review.pdf",
    ]


def test_the_first_copy_in_corpus_order_survives():
    body = "shared"
    forward = deduplicate(
        [
            make_chunk(text=body, source_file="a.pdf"),
            make_chunk(text=body, source_file="b.pdf"),
        ]
    )
    reverse = deduplicate(
        [
            make_chunk(text=body, source_file="b.pdf"),
            make_chunk(text=body, source_file="a.pdf"),
        ]
    )
    assert forward[0].chunk.source_file == "a.pdf"
    assert reverse[0].chunk.source_file == "b.pdf"


def test_deduplication_is_stable_across_runs():
    chunks = [make_chunk(text=f"body {i % 3}") for i in range(9)]
    assert [e.chunk_id for e in deduplicate(chunks)] == [
        e.chunk_id for e in deduplicate(chunks)
    ]


def test_building_and_searching_an_index_with_no_model(fake_embedder, tmp_path):
    chunks = [
        make_chunk(text="routers hold packets in an output queue", pages=(1,)),
        make_chunk(text="TCP halves its window on loss", pages=(2,)),
        make_chunk(
            text="compute the propagation delay",
            doc_type=PROBLEM_SHEET,
            source_file="homework 1.pdf",
        ),
    ]
    store = build_index(chunks, fake_embedder)
    store.save(tmp_path)

    loaded = NumpyStore.load(tmp_path, embedder=fake_embedder)
    assert len(loaded) == 3
    assert loaded.embedder_name == fake_embedder.name
    assert loaded.dim == fake_embedder.dim

    hits = loaded.search(fake_embedder.embed_query("TCP halves its window on loss"))
    assert hits[0].text == "TCP halves its window on loss"
    assert hits[0].score > 0.99
    deck_only = loaded.search(fake_embedder.embed_query("delay"), k=5, doc_type=DECK)
    assert len(deck_only) == 2


def test_an_index_built_through_the_cache_matches_one_built_without(
    fake_embedder, tmp_path
):
    chunks = [make_chunk(text=f"body {i}") for i in range(5)]
    direct = build_index(chunks, fake_embedder)

    cache = EmbeddingCache.load(tmp_path, fake_embedder)
    build_index(chunks, fake_embedder, cache=cache)
    cache.save()
    through_cache = build_index(
        chunks, fake_embedder, cache=EmbeddingCache.load(tmp_path, fake_embedder)
    )

    probe = fake_embedder.embed_query("body 3")
    assert [h.chunk_id for h in direct.search(probe, k=5)] == [
        h.chunk_id for h in through_cache.search(probe, k=5)
    ]


def test_an_empty_chunk_list_builds_an_empty_index(fake_embedder, tmp_path):
    store = build_index([], fake_embedder)
    store.save(tmp_path)
    assert len(NumpyStore.load(tmp_path)) == 0
    assert NumpyStore.load(tmp_path).search(np.zeros(fake_embedder.dim)) == []
