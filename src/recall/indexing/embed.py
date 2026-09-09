"""Turning chunk text into vectors, behind one interface.

The `Embedder` protocol exists because SPEC.md 3a deliberately did not pick a
winner: a local model is the default so the eval harness runs on a fresh clone
with no credentials, and a hosted model is written to the same interface so
module 6 can measure the difference rather than assert it.

Two details here are easy to get wrong and silent when wrong. `bge` is an
asymmetric model — queries carry a prefix and documents do not — so the prefix
lives in one place and is applied by `embed_query` alone. And every vector is
L2-normalised at embed time, which makes cosine similarity a plain dot product
downstream and removes the chance of forgetting it there.
"""

from __future__ import annotations

import os
from typing import Protocol, Sequence, runtime_checkable

import numpy as np

# bge is trained with an instruction on the query side only. Embedding
# documents with this prefix, or queries without it, degrades retrieval
# without raising anything.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

LOCAL_MODEL = "BAAI/bge-base-en-v1.5"
LOCAL_NAME = "bge-base-en-v1.5"
LOCAL_DIM = 768

HOSTED_MODEL = "text-embedding-3-small"
HOSTED_DIM = 1536


def l2_normalise(vectors: np.ndarray) -> np.ndarray:
    """Scale each row to unit length, leaving zero rows alone.

    A zero row would otherwise divide by zero and poison the whole matrix with
    NaN, which scores as neither a hit nor a miss and is hard to trace back.
    """
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        return l2_normalise(vectors.reshape(1, -1))[0]
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def apply_query_prefix(text: str) -> str:
    """The one place the bge query instruction is added."""
    return BGE_QUERY_PREFIX + text


@runtime_checkable
class Embedder(Protocol):
    """What the index and the retriever are allowed to assume about a model."""

    @property
    def name(self) -> str:
        """Identifies the model in the index header and the cache filename."""

    @property
    def dim(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        """Return an (len(texts), dim) L2-normalised float32 matrix."""

    def embed_query(self, text: str) -> np.ndarray:
        """Return one L2-normalised float32 vector of length `dim`."""


class LocalEmbedder:
    """`bge-base-en-v1.5` through sentence-transformers, run on this machine.

    The model is loaded lazily so importing this module — which the CLI and the
    tests both do — never pulls in torch or touches the network.
    """

    def __init__(self, model: str = LOCAL_MODEL, *, batch_size: int = 32) -> None:
        self._model_id = model
        self._batch_size = batch_size
        self._model = None

    @property
    def name(self) -> str:
        return LOCAL_NAME

    @property
    def dim(self) -> int:
        return LOCAL_DIM

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on install
                raise ImportError(
                    "LocalEmbedder needs sentence-transformers. "
                    "Install it with: uv sync --extra local"
                ) from exc
            self._model = SentenceTransformer(self._model_id)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        raw = self._load().encode(
            list(texts), batch_size=self._batch_size, show_progress_bar=False
        )
        return l2_normalise(np.asarray(raw, dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([apply_query_prefix(text)])[0]


class HostedEmbedder:
    """OpenAI embeddings through the same interface, for the module 6 comparison.

    Written now rather than at module 6 so that 3a's claim — that the choice is
    open and measurable — is backed by code instead of an intention.
    """

    def __init__(self, model: str = HOSTED_MODEL, *, batch_size: int = 128) -> None:
        self._model_id = model
        self._batch_size = batch_size
        self._client = None

    @property
    def name(self) -> str:
        return self._model_id

    @property
    def dim(self) -> int:
        return HOSTED_DIM

    def _load(self):
        if self._client is None:
            if not os.environ.get("OPENAI_API_KEY"):
                raise RuntimeError(
                    "HostedEmbedder needs OPENAI_API_KEY. The local embedder is "
                    "the default precisely so this is never required."
                )
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - depends on install
                raise ImportError(
                    "HostedEmbedder needs the openai package. "
                    "Install it with: uv sync --extra hosted-embed"
                ) from exc
            self._client = OpenAI()
        return self._client

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        client = self._load()
        out: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = client.embeddings.create(model=self._model_id, input=batch)
            out.extend(item.embedding for item in response.data)
        return l2_normalise(np.asarray(out, dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        # Symmetric model: no query instruction, unlike bge.
        return self.embed_documents([text])[0]
