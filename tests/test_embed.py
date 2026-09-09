"""Vector hygiene: normalisation, and the bge query/document asymmetry.

SPEC.md 3c accepted that hand-building makes these this repo's bugs to have.
Both failures here are silent — a skipped normalisation still returns numbers,
and a misapplied query prefix still returns results — so they are tested
directly rather than through retrieval quality.
"""

from __future__ import annotations

import numpy as np
import pytest

from recall.indexing.embed import (
    BGE_QUERY_PREFIX,
    Embedder,
    LocalEmbedder,
    apply_query_prefix,
    l2_normalise,
)


def test_normalise_gives_unit_rows():
    matrix = np.array([[3.0, 4.0], [1.0, 0.0], [-2.0, 0.0]])
    norms = np.linalg.norm(l2_normalise(matrix), axis=1)
    assert np.allclose(norms, 1.0)


def test_normalise_preserves_direction():
    vector = np.array([3.0, 4.0])
    assert np.allclose(l2_normalise(vector), [0.6, 0.8])


def test_normalise_leaves_a_zero_row_alone():
    """A zero row must not become NaN and poison every later comparison."""
    out = l2_normalise(np.array([[0.0, 0.0], [3.0, 4.0]]))
    assert not np.isnan(out).any()
    assert np.allclose(out[0], [0.0, 0.0])


def test_normalise_accepts_a_single_vector():
    assert l2_normalise(np.array([0.0, 2.0])).shape == (2,)


def test_query_prefix_is_applied_once_and_only_to_queries():
    assert apply_query_prefix("what is a router") == (
        BGE_QUERY_PREFIX + "what is a router"
    )
    assert not apply_query_prefix("x").endswith(BGE_QUERY_PREFIX)


def test_local_embedder_reports_itself_without_loading_a_model():
    """Importing and describing the embedder must not touch torch or the network."""
    embedder = LocalEmbedder()
    assert embedder.name == "bge-base-en-v1.5"
    assert embedder.dim == 768
    assert embedder._model is None


def test_local_embedder_returns_an_empty_matrix_for_no_texts():
    assert LocalEmbedder().embed_documents([]).shape == (0, 768)


def test_the_fake_embedder_satisfies_the_protocol(fake_embedder):
    assert isinstance(fake_embedder, Embedder)


def test_the_fake_embedder_is_deterministic(fake_embedder):
    first = fake_embedder.embed_documents(["a", "b"])
    second = fake_embedder.embed_documents(["a", "b"])
    assert np.array_equal(first, second)
    assert not np.array_equal(first[0], first[1])


@pytest.mark.slow
def test_the_real_model_produces_normalised_vectors_of_the_declared_size():
    """Deselected by default: downloads ~440 MB. Run with `-m slow`."""
    embedder = LocalEmbedder()
    vectors = embedder.embed_documents(["routers queue packets", "TCP congestion"])
    assert vectors.shape == (2, embedder.dim)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
