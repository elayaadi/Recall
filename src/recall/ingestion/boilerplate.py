"""Detect lines a document repeats on most of its pages.

Every deck in the corpus carries one such line — a course/copyright footer on
29 to 40 of its pages. Left in, it lands in every chunk and therefore in every
embedding, making chunks look more alike than they are.
"""

from __future__ import annotations

from collections import Counter

from .pdf import Document

DEFAULT_THRESHOLD = 0.5
_MIN_PAGES = 3
_MIN_LENGTH = 3


def find_boilerplate(
    document: Document, threshold: float = DEFAULT_THRESHOLD
) -> frozenset[str]:
    """Lines appearing on more than `threshold` of the document's pages.

    Counted once per page, so a line repeated within a single page does not
    inflate its own count. Short documents are exempt: with two pages, any
    shared line would trip a 50% threshold.
    """
    pages = document.text_pages
    if len(pages) < _MIN_PAGES:
        return frozenset()

    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({line.strip() for line in page.lines if len(line.strip()) >= _MIN_LENGTH})

    cutoff = threshold * len(pages)
    return frozenset(line for line, count in counts.items() if count > cutoff)


def strip_boilerplate(
    lines: tuple[str, ...] | list[str], boilerplate: frozenset[str]
) -> list[str]:
    return [line for line in lines if line.strip() and line.strip() not in boilerplate]
