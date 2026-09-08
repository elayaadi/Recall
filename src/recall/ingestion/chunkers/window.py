"""Baseline chunker: fixed-size token windows with overlap, ignoring structure.

Kept deliberately, not as legacy. Run against the same eval set as the
structural chunker in module 6, it turns "structure-aware chunking suits slide
decks better" from a plausible claim into a measured delta per document type.

Two notes on making that comparison fair. Boilerplate is stripped for both
chunkers, so the delta cannot be an artefact of one of them carrying a
repeated footer. But the structural chunker also prepends a title prefix, which
this one has no structure to produce — so the measured delta covers boundaries
and prefixing together, which is the pair of choices actually made. Isolating
them would need a third variant, and module 6 can add one if the numbers make
it interesting.
"""

from __future__ import annotations

from ..boilerplate import strip_boilerplate
from ..models import UNKNOWN, WINDOW, Chunk, Locator
from ..pdf import Document

DEFAULT_WINDOW_WORDS = 150
DEFAULT_OVERLAP_WORDS = 30


def chunk_windows(
    document: Document,
    boilerplate: frozenset[str],
    doc_type: str = UNKNOWN,
    *,
    window_words: int = DEFAULT_WINDOW_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[Chunk]:
    if overlap_words >= window_words:
        raise ValueError("overlap must be smaller than the window")

    words: list[tuple[int, str]] = []
    for page in document.pages:
        if not page.has_text:
            continue
        for line in strip_boilerplate(page.lines, boilerplate):
            words.extend((page.number, word) for word in line.split())
    if not words:
        return []

    step = window_words - overlap_words
    chunks: list[Chunk] = []
    for start in range(0, len(words), step):
        window = words[start : start + window_words]
        if not window:
            break
        body = " ".join(word for _, word in window)
        pages = tuple(sorted({page for page, _ in window}))
        chunks.append(
            Chunk.make(
                source_file=document.name,
                source_sha256=document.sha256,
                doc_type=doc_type,
                chunker=WINDOW,
                locator=Locator(kind=WINDOW, pages=pages),
                text=body,
                raw_text=body,
            )
        )
        if start + window_words >= len(words):
            break
    return chunks
