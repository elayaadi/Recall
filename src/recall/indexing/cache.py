"""An embedding cache keyed on chunk id and embedder.

Module 2 established that chunk defects surface by reading real output and
re-running, so the chunker will keep changing and most chunks will survive each
change unaltered. `chunk_id` is a hash of the source, locator and raw text, so
an unchanged chunk keeps its id and its vector can be reused; a changed chunk
gets a new id and is embedded again. The cache is therefore correct by
construction rather than by an invalidation rule.

The embedder name is in the filename rather than inside it, so two models never
share a file and a stale cache cannot quietly supply vectors from the wrong
space.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np

CACHE_PREFIX = "cache-"


def cache_path(directory: Path, embedder_name: str) -> Path:
    safe = embedder_name.replace("/", "_")
    return directory / f"{CACHE_PREFIX}{safe}.npz"


class EmbeddingCache:
    """chunk_id -> vector, for one embedder, persisted as a single npz."""

    def __init__(self, path: Path, *, dim: int) -> None:
        self.path = path
        self.dim = dim
        self._vectors: dict[str, np.ndarray] = {}
        self.hits = 0
        self.misses = 0

    @classmethod
    def load(cls, directory: Path, embedder: Any) -> EmbeddingCache:
        path = cache_path(directory, embedder.name)
        cache = cls(path, dim=embedder.dim)
        if not path.exists():
            return cache
        with np.load(path, allow_pickle=False) as data:
            ids = data["ids"]
            vectors = data["vectors"]
        # A cache written by an earlier dimension is discarded rather than
        # repaired: it is derived data, and rebuilding it costs one run.
        if vectors.ndim == 2 and vectors.shape[1] == embedder.dim:
            cache._vectors = {
                str(chunk_id): vectors[i] for i, chunk_id in enumerate(ids)
            }
        return cache

    def __len__(self) -> int:
        return len(self._vectors)

    def get(self, chunk_id: str) -> np.ndarray | None:
        return self._vectors.get(chunk_id)

    def put(self, chunk_id: str, vector: np.ndarray) -> None:
        self._vectors[chunk_id] = np.asarray(vector, dtype=np.float32)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ids = list(self._vectors)
        if ids:
            vectors = np.stack([self._vectors[i] for i in ids])
        else:
            vectors = np.zeros((0, self.dim), dtype=np.float32)
        np.savez(self.path, ids=np.array(ids, dtype=object).astype(str), vectors=vectors)


def embed_texts(
    embedder: Any,
    chunk_ids: Sequence[str],
    texts: Sequence[str],
    cache: EmbeddingCache | None = None,
) -> np.ndarray:
    """Embed `texts`, reusing cached vectors for ids already seen.

    Returns rows in the order given, whether each row came from the cache or
    from the model — the caller cannot tell, which is the point.
    """
    if len(chunk_ids) != len(texts):
        raise ValueError(f"{len(chunk_ids)} ids but {len(texts)} texts")
    if not texts:
        return np.zeros((0, embedder.dim), dtype=np.float32)

    out: list[np.ndarray | None] = []
    pending_positions: list[int] = []
    pending_texts: list[str] = []

    for position, (chunk_id, text) in enumerate(zip(chunk_ids, texts)):
        cached = cache.get(chunk_id) if cache is not None else None
        if cached is None:
            out.append(None)
            pending_positions.append(position)
            pending_texts.append(text)
            if cache is not None:
                cache.misses += 1
        else:
            out.append(cached)
            cache.hits += 1

    if pending_texts:
        fresh = embedder.embed_documents(pending_texts)
        for position, vector in zip(pending_positions, fresh):
            out[position] = vector
            if cache is not None:
                cache.put(chunk_ids[position], vector)

    if any(v is None for v in out):  # pragma: no cover - guards a silent row shift
        raise RuntimeError("embedder returned fewer vectors than texts")
    return np.stack(out).astype(np.float32)
