"""The cache must be invisible: a hit and a miss produce the same vectors.

If cached and freshly embedded rows ever differ, retrieval quality would drift
with cache state rather than with any change made on purpose — a difference
that would show up as noise in module 6's numbers and be very hard to trace.
"""

from __future__ import annotations

import numpy as np
from conftest import FakeEmbedder

from recall.indexing.cache import EmbeddingCache, cache_path, embed_texts


def test_a_cache_hit_matches_a_cache_miss_exactly(fake_embedder, tmp_path):
    ids, texts = ["a", "b", "c"], ["first", "second", "third"]

    uncached = embed_texts(fake_embedder, ids, texts)

    cache = EmbeddingCache.load(tmp_path, fake_embedder)
    embed_texts(fake_embedder, ids, texts, cache=cache)
    cache.save()

    reloaded = EmbeddingCache.load(tmp_path, fake_embedder)
    cached = embed_texts(fake_embedder, ids, texts, cache=reloaded)

    assert np.array_equal(uncached, cached)
    assert reloaded.hits == 3
    assert reloaded.misses == 0


def test_only_the_unseen_chunks_are_embedded_again(fake_embedder, tmp_path):
    cache = EmbeddingCache.load(tmp_path, fake_embedder)
    embed_texts(fake_embedder, ["a", "b"], ["first", "second"], cache=cache)
    cache.save()

    second_run = EmbeddingCache.load(tmp_path, fake_embedder)
    embed_texts(
        fake_embedder, ["a", "b", "c"], ["first", "second", "third"], cache=second_run
    )
    assert (second_run.hits, second_run.misses) == (2, 1)


def test_rows_stay_in_the_order_asked_for_whatever_their_source(fake_embedder, tmp_path):
    cache = EmbeddingCache.load(tmp_path, fake_embedder)
    embed_texts(fake_embedder, ["b"], ["second"], cache=cache)

    mixed = embed_texts(
        fake_embedder, ["a", "b", "c"], ["first", "second", "third"], cache=cache
    )
    assert np.array_equal(mixed, fake_embedder.embed_documents(["first", "second", "third"]))


def test_two_embedders_never_share_a_cache_file(fake_embedder, tmp_path):
    other = FakeEmbedder(name="fake-other", dim=16)
    assert cache_path(tmp_path, fake_embedder.name) != cache_path(tmp_path, other.name)

    cache = EmbeddingCache.load(tmp_path, fake_embedder)
    embed_texts(fake_embedder, ["a"], ["first"], cache=cache)
    cache.save()

    fresh = EmbeddingCache.load(tmp_path, other)
    assert len(fresh) == 0


def test_a_cache_of_the_wrong_width_is_discarded_not_used(fake_embedder, tmp_path):
    """Derived data: rebuilding costs one run, using it wrongly costs the numbers."""
    cache = EmbeddingCache.load(tmp_path, fake_embedder)
    embed_texts(fake_embedder, ["a"], ["first"], cache=cache)
    cache.save()

    widened = FakeEmbedder(name=fake_embedder.name, dim=32)
    assert len(EmbeddingCache.load(tmp_path, widened)) == 0


def test_an_empty_cache_saves_and_reloads(fake_embedder, tmp_path):
    EmbeddingCache.load(tmp_path, fake_embedder).save()
    assert len(EmbeddingCache.load(tmp_path, fake_embedder)) == 0
