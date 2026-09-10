"""What the app loads once, and never per request. SPEC.md 7.

Cold start is 23 seconds — importing torch, loading 419 MB of embedder weights,
and reading the index. Paying that per request is the difference between a demo
and a timeout, so the store, the embedder and the retriever are process-wide and
built at startup.

The generator is the exception: it is constructed but never contacted until a
request needs it, so the API starts and `/search` works whether or not Ollama is
running. A generator that cannot be reached surfaces as a 502 on `/answer`
(§7b), not as a server that will not boot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..generation.answerer import UNCALIBRATED_MIN_CLAIMS, Answerer
from ..generation.generate import Generator, make_generator
from ..indexing.build import make_embedder
from ..indexing.store import NumpyStore
from ..retrieval.retriever import (
    UNCALIBRATED_ABSTAIN,
    UNCALIBRATED_COLLAPSE,
    Retriever,
)

DEFAULT_INDEX = Path("data/index")

# Served publicly or not, the corpus is CC BY-NC-SA and attribution travels with
# it. §7c chose a local deployment, so this is the notice a reader of the API
# sees rather than one buried in the repo.
CORPUS_NOTICE = (
    "Corpus: MIT OpenCourseWare 6.02 (Fall 2012), CC BY-NC-SA 4.0. "
    "See data/CORPUS.md."
)


@dataclass
class Services:
    """Everything a request needs, built once."""

    store: NumpyStore
    retriever: Retriever
    answerer: Answerer
    generator_name: str

    @classmethod
    def build(
        cls,
        index: Path = DEFAULT_INDEX,
        *,
        k: int = 5,
        abstain: float = UNCALIBRATED_ABSTAIN,
        collapse: float = UNCALIBRATED_COLLAPSE,
        min_claims: int = UNCALIBRATED_MIN_CLAIMS,
        embedder=None,
        generator: Generator | None = None,
    ) -> "Services":
        store = NumpyStore.load(index)
        embedder = embedder if embedder is not None else make_embedder("local")
        retriever = Retriever(
            store, embedder, k=k, abstain_threshold=abstain, collapse_threshold=collapse
        )
        # Force the embedder to load *now*. It is lazy by design -- §3a keeps
        # importing `embed.py` free of torch -- which meant the app booted
        # reporting ok while being unable to serve a single search: the 23 s
        # cold start landed on the first request, and a missing
        # sentence-transformers surfaced as a 500 to whoever asked first rather
        # than as a server that refused to start. Found by running it.
        embedder.embed_query("warm up")

        gen = generator if generator is not None else make_generator()
        return cls(
            store=store,
            retriever=retriever,
            answerer=Answerer(retriever, gen, min_verified_claims=min_claims),
            generator_name=gen.name,
        )
