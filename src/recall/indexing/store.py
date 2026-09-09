"""The vector index: entries, exhaustive search, and a file on disk.

SPEC.md 3b chose exhaustive numpy search over FAISS and over a vector database
on the arithmetic: 528 vectors at 768 dimensions is a 1.6 MB matrix and one
matrix-vector product, so approximate search would give up recall for a speed
gain too small to observe. The thresholds for revisiting that are recorded in
3b, not here, so this file stays about mechanism.

Two invariants this module is responsible for. Search results carry chunk ids
and locators, never row offsets, because a row offset is invalidated by any
re-index and would silently point at the wrong passage. And an index records
the embedder that built it, so loading one under a different model fails loudly
instead of returning similarities computed between unrelated vector spaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np

from ..ingestion.models import Chunk, Locator

VECTORS_FILE = "vectors.npy"
INDEX_FILE = "index.json"
FORMAT_VERSION = 1


class IndexMismatch(RuntimeError):
    """An index was loaded or queried with a model that did not build it."""


@dataclass(frozen=True)
class Duplicate:
    """Another place the same passage appears, kept so a citation can name it."""

    source_file: str
    locator: Locator

    def cite(self) -> str:
        return f"{self.source_file}, {self.locator.cite()}"

    def to_dict(self) -> dict[str, Any]:
        return {"source_file": self.source_file, "locator": self.locator.to_dict()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Duplicate:
        return cls(source_file=d["source_file"], locator=Locator.from_dict(d["locator"]))


@dataclass(frozen=True)
class IndexEntry:
    """One embedded passage, plus every other location it was found at.

    SPEC.md 3d deduplicates on the byte-identical raw body, so one entry can
    stand for several chunks. The alternates are kept rather than dropped: the
    passage genuinely appears in both decks and a citation should be able to
    say so.
    """

    chunk: Chunk
    duplicates: tuple[Duplicate, ...] = ()

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id

    def citations(self) -> list[str]:
        return [self.chunk.citation()] + [d.cite() for d in self.duplicates]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "duplicates": [d.to_dict() for d in self.duplicates],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IndexEntry:
        return cls(
            chunk=Chunk.from_dict(d["chunk"]),
            duplicates=tuple(Duplicate.from_dict(x) for x in d.get("duplicates", ())),
        )


@dataclass(frozen=True)
class SearchHit:
    """A retrieved passage. Addressed by chunk id and locator, never by row."""

    entry: IndexEntry
    score: float

    @property
    def chunk_id(self) -> str:
        return self.entry.chunk_id

    @property
    def text(self) -> str:
        return self.entry.chunk.text

    def citations(self) -> list[str]:
        return self.entry.citations()


class VectorStore(Protocol):
    """What retrieval (module 4) is allowed to assume about storage."""

    @property
    def embedder_name(self) -> str: ...

    @property
    def dim(self) -> int: ...

    def search(
        self,
        query: np.ndarray,
        k: int = 5,
        *,
        doc_type: str | None = None,
        source_file: str | None = None,
    ) -> list[SearchHit]: ...

    def save(self, directory: Path) -> None: ...


class NumpyStore:
    """Exhaustive cosine search over an in-memory float32 matrix.

    Vectors are L2-normalised on the way in (see `embed.l2_normalise`), so
    cosine similarity is `matrix @ query` and there is no separate
    normalisation step to omit.
    """

    def __init__(
        self,
        entries: Sequence[IndexEntry],
        vectors: np.ndarray,
        *,
        embedder_name: str,
    ) -> None:
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2:
            raise ValueError(f"vectors must be 2-D, got shape {vectors.shape}")
        if len(entries) != vectors.shape[0]:
            raise ValueError(
                f"{len(entries)} entries but {vectors.shape[0]} vectors"
            )
        self._entries = list(entries)
        self._vectors = vectors
        self._embedder_name = embedder_name

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list[IndexEntry]:
        return list(self._entries)

    @property
    def embedder_name(self) -> str:
        return self._embedder_name

    @property
    def dim(self) -> int:
        return int(self._vectors.shape[1])

    def check_embedder(self, embedder: Any) -> None:
        """Refuse a model that did not build this index.

        Querying an index with vectors from another model returns plausible
        numbers computed between unrelated spaces — the failure this raises
        instead of.
        """
        if embedder.name != self._embedder_name:
            raise IndexMismatch(
                f"index was built with {self._embedder_name!r}, "
                f"queried with {embedder.name!r}; rebuild it with recall-index"
            )
        if embedder.dim != self.dim:
            raise IndexMismatch(
                f"index has {self.dim} dimensions, {embedder.name!r} produces "
                f"{embedder.dim}"
            )

    def _mask(self, doc_type: str | None, source_file: str | None) -> np.ndarray:
        mask = np.ones(len(self._entries), dtype=bool)
        if doc_type is not None:
            mask &= np.array(
                [e.chunk.doc_type == doc_type for e in self._entries], dtype=bool
            )
        if source_file is not None:
            mask &= np.array(
                [e.chunk.source_file == source_file for e in self._entries], dtype=bool
            )
        return mask

    def search(
        self,
        query: np.ndarray,
        k: int = 5,
        *,
        doc_type: str | None = None,
        source_file: str | None = None,
    ) -> list[SearchHit]:
        query = np.asarray(query, dtype=np.float32).reshape(-1)
        if len(self._entries) == 0:
            return []
        if query.shape[0] != self.dim:
            raise IndexMismatch(
                f"query has {query.shape[0]} dimensions, index has {self.dim}"
            )
        if k <= 0:
            return []

        scores = self._vectors @ query
        candidates = np.flatnonzero(self._mask(doc_type, source_file))
        if candidates.size == 0:
            return []

        candidate_scores = scores[candidates]
        take = min(k, candidates.size)
        # argpartition finds the top `take` without sorting the rest; the
        # partition itself is unordered, so the slice is sorted afterwards.
        top = np.argpartition(-candidate_scores, take - 1)[:take]
        top = top[np.argsort(-candidate_scores[top], kind="stable")]
        return [
            SearchHit(entry=self._entries[candidates[i]], score=float(candidate_scores[i]))
            for i in top
        ]

    def vectors_for(self, chunk_ids: Sequence[str]) -> np.ndarray:
        """The stored vectors for these entries, in the order asked for.

        Retrieval needs them to compare results against each other rather than
        against the query — SPEC.md 4d collapses near-duplicate results, and
        re-embedding text that is already embedded here would be absurd.
        """
        rows = {entry.chunk_id: i for i, entry in enumerate(self._entries)}
        missing = [c for c in chunk_ids if c not in rows]
        if missing:
            raise KeyError(f"not in this index: {missing[0]}")
        return self._vectors[[rows[c] for c in chunk_ids]]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / VECTORS_FILE, self._vectors)
        header = {
            "format_version": FORMAT_VERSION,
            "embedder": self._embedder_name,
            "dim": self.dim,
            "count": len(self._entries),
            "entries": [e.to_dict() for e in self._entries],
        }
        with (directory / INDEX_FILE).open("w", encoding="utf-8") as fh:
            json.dump(header, fh, ensure_ascii=False)

    @classmethod
    def load(cls, directory: Path, *, embedder: Any | None = None) -> NumpyStore:
        with (directory / INDEX_FILE).open(encoding="utf-8") as fh:
            header = json.load(fh)
        if header.get("format_version") != FORMAT_VERSION:
            raise IndexMismatch(
                f"index format version {header.get('format_version')}, "
                f"this build reads {FORMAT_VERSION}; rebuild it with recall-index"
            )
        vectors = np.load(directory / VECTORS_FILE)
        store = cls(
            [IndexEntry.from_dict(e) for e in header["entries"]],
            vectors,
            embedder_name=header["embedder"],
        )
        if store.dim != header["dim"]:
            raise IndexMismatch(
                f"header says {header['dim']} dimensions, matrix has {store.dim}"
            )
        if embedder is not None:
            store.check_embedder(embedder)
        return store


def index_size_bytes(directory: Path) -> int:
    return sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
