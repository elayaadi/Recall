from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from recall.ingestion.models import DECK, STRUCTURAL, Chunk, Locator

sys.path.insert(0, str(Path(__file__).parent))
from fixtures.make_pdfs import make_all  # noqa: E402


@pytest.fixture(scope="session")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Synthetic PDFs, built once per test session."""
    return make_all(tmp_path_factory.mktemp("corpus"))


@pytest.fixture(scope="session")
def deck_path(corpus: dict[str, Path]) -> Path:
    return corpus["deck"]


@pytest.fixture(scope="session")
def problem_sheet_path(corpus: dict[str, Path]) -> Path:
    return corpus["problem_sheet"]


@pytest.fixture(scope="session")
def syllabus_path(corpus: dict[str, Path]) -> Path:
    return corpus["syllabus"]


@dataclass(frozen=True)
class FakeEmbedder:
    """A deterministic embedder that never downloads a model or opens a socket.

    The index tests are about top-k, persistence, filtering and caching, none
    of which need real semantics — and CLAUDE.md requires the suite to pass on
    a fresh clone with no corpus and no network. Vectors come from a hash of
    the text, so the same text always produces the same vector and different
    texts almost never collide.
    """

    name: str = "fake-16"
    dim: int = 16

    def _vector(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = np.frombuffer(digest * 2, dtype=np.uint8)[: self.dim]
        vector = raw.astype(np.float32) - 127.5
        return vector / np.linalg.norm(vector)

    def embed_documents(self, texts) -> np.ndarray:
        if not len(texts):
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._vector(t) for t in texts]).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vector(text)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


def make_chunk(
    *,
    text: str,
    raw_text: str | None = None,
    source_file: str = "deck.pdf",
    doc_type: str = DECK,
    pages: tuple[int, ...] = (1,),
    title: str | None = "A title",
) -> Chunk:
    """A chunk built the same way ingestion builds one, for index tests."""
    return Chunk.make(
        source_file=source_file,
        source_sha256="0" * 64,
        doc_type=doc_type,
        chunker=STRUCTURAL,
        locator=Locator(kind=doc_type, pages=pages, title=title),
        text=text,
        raw_text=raw_text if raw_text is not None else text,
    )
