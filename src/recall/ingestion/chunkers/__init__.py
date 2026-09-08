"""Dispatch a loaded document to the chunker its type calls for."""

from __future__ import annotations

from ..models import DECK, PROBLEM_SHEET, STRUCTURAL, SYLLABUS, WINDOW, Chunk
from ..pdf import Document
from .deck import chunk_deck
from .problem_sheet import chunk_problem_sheet
from .syllabus import chunk_syllabus
from .window import chunk_windows

__all__ = [
    "chunk_deck",
    "chunk_problem_sheet",
    "chunk_syllabus",
    "chunk_windows",
    "chunk_document",
]


def chunk_document(
    document: Document,
    doc_type: str,
    boilerplate: frozenset[str],
    *,
    chunker: str = STRUCTURAL,
) -> list[Chunk]:
    if chunker == WINDOW:
        return chunk_windows(document, boilerplate, doc_type)
    if chunker != STRUCTURAL:
        raise ValueError(f"unknown chunker: {chunker!r}")

    if doc_type == DECK:
        return chunk_deck(document, boilerplate)
    if doc_type == PROBLEM_SHEET:
        return chunk_problem_sheet(document, boilerplate)
    if doc_type == SYLLABUS:
        return chunk_syllabus(document, boilerplate)
    # An unclassified document still has to be retrievable; windows are the
    # honest fallback when no structural signal was found.
    return chunk_windows(document, boilerplate, doc_type)
