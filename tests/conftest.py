from __future__ import annotations

import hashlib
import json
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


@dataclass
class FakeGenerator:
    """A generator that returns scripted output and never opens a socket.

    Generation tests are about the outcome a given response produces —
    abstention, verification, malformed output — none of which need a real
    model, and CLAUDE.md requires the suite to pass on a fresh clone with no
    network and no credentials.

    Responses are returned in order and the last one repeats, so a judge called
    once per claim needs only one. Prompts and schemas are recorded, because
    what reaches the model is as much a subject of the tests as what comes back.
    """

    responses: list[str]
    name: str = "fake-generator"

    def __post_init__(self) -> None:
        self.prompts: list[str] = []
        self.schemas: list[dict] = []

    def complete(self, prompt: str, schema: dict) -> str:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        if not self.responses:
            raise AssertionError("FakeGenerator was called with no responses left")
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


def generation_response(
    *,
    answer: str = "an answer",
    claims: list[tuple[str, list[str]]] | None = None,
    abstained: bool = False,
    reason: str = "",
) -> str:
    """A well-formed model response, built the way the schema asks for one."""
    return json.dumps(
        {
            "answer": answer,
            "claims": [{"text": t, "chunk_ids": ids} for t, ids in (claims or [])],
            "abstained": abstained,
            "reason": reason,
        }
    )
