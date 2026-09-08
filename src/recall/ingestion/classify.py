"""Decide which structural chunker a document needs.

Classification is driven by measured signals rather than filenames. Filenames
happen to be reliable for the 29 files in hand, and would break the moment a
file is named differently; they are used only to break a tie the signals leave
open. The chosen type and the evidence for it are reported by the pipeline so
a wrong call is visible rather than silent.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from .models import DECK, PROBLEM_SHEET, SYLLABUS, UNKNOWN
from .pdf import Document
from .structure import all_caps_headings, numbered_items

_SPARSE_WORDS_PER_PAGE = 130
_MIN_CAPS_HEADINGS = 4
_MIN_NUMBERED_ITEMS = 3

_FILENAME_HINTS = (
    ("syllabus", SYLLABUS),
    ("homework", PROBLEM_SHEET),
    ("assignment", PROBLEM_SHEET),
    ("lecture", DECK),
    ("week", DECK),
    ("slides", DECK),
)


@dataclass(frozen=True)
class Classification:
    doc_type: str
    reason: str


def classify(document: Document) -> Classification:
    pages = document.text_pages
    if not pages:
        return Classification(UNKNOWN, "no page carried a text layer")

    landscape = sum(1 for p in pages if p.is_landscape)
    landscape_majority = landscape > len(pages) * 0.6
    median_words = statistics.median(p.n_words for p in pages)

    all_lines = [line for page in pages for line in page.lines]
    headings = all_caps_headings(all_lines)
    numbered = numbered_items(all_lines)

    if not landscape_majority and len(headings) >= _MIN_CAPS_HEADINGS:
        return Classification(
            SYLLABUS, f"{len(headings)} ALL-CAPS section headings, portrait"
        )

    if not landscape_majority and len(numbered) >= _MIN_NUMBERED_ITEMS:
        return Classification(
            PROBLEM_SHEET,
            f"sequential numbered items 1-{len(numbered)}, portrait",
        )

    if landscape_majority:
        return Classification(DECK, f"{landscape}/{len(pages)} pages landscape")

    if median_words < _SPARSE_WORDS_PER_PAGE:
        return Classification(DECK, f"median {median_words:.0f} words/page")

    hinted = _filename_hint(document.name)
    if hinted:
        return Classification(hinted, f"signals inconclusive; filename hint '{document.name}'")

    return Classification(UNKNOWN, f"median {median_words:.0f} words/page, no structural signal")


def _filename_hint(name: str) -> str | None:
    lowered = name.lower()
    for needle, doc_type in _FILENAME_HINTS:
        if needle in lowered:
            return doc_type
    return None
