"""Structural signals shared by the classifier and the chunkers.

Every pattern here was verified against the real corpus before being written;
the measurements are in docs/corpus-profile.md.
"""

from __future__ import annotations

import re

# Authors mark a continued topic in several spellings; all seen in the corpus.
CONTINUATION_RE = re.compile(
    r"\s*[\(\[]?\s*(cont(inued|\.|'d|d)?|ctd\.?)\s*[\)\]]?\s*$", re.I
)
_TRAILING_INDEX_RE = re.compile(r"\s*[-–—]?\s*(\d+|[IVX]+)\s*$")
_NUMBERED_RE = re.compile(r"^\s{0,4}(\d{1,2})\s*[\.\)]\s+\S")
_SUBPART_RE = re.compile(r"^\s{0,6}([a-h])\s*[\.\)]\s+\S")
_WHITESPACE_RE = re.compile(r"\s+")


def normalise_title(title: str | None) -> str:
    """Comparison form of a slide title.

    Used only to decide whether two consecutive slides continue one topic; the
    chunk keeps the original title for display and citation. Stripping
    "(cont.)" honours a boundary the author marked explicitly — ignoring it
    while treating the rest of the title as authoritative would be
    inconsistent. See SPEC.md 2b.
    """
    if not title:
        return ""
    text = CONTINUATION_RE.sub("", title.strip())
    text = _TRAILING_INDEX_RE.sub("", text.strip())
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


def all_caps_headings(lines: tuple[str, ...] | list[str]) -> list[str]:
    """Lines that read as ALL-CAPS section headings (the syllabus signal)."""
    out = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 8 and stripped == stripped.upper():
            if sum(c.isalpha() for c in stripped) > 6:
                out.append(stripped)
    return out


def numbered_items(lines: tuple[str, ...] | list[str]) -> list[tuple[int, int]]:
    """Line-start numbered items that form a run 1, 2, 3, ...

    Returns (line_index, number) pairs. Requiring the numbers to increment by
    one from 1 is what separates real problem numbers from incidental digits in
    prose — "3 MB" and "Layer 4" appear in these sheets and must not be read as
    problem headers.
    """
    candidates = [
        (i, int(m.group(1)))
        for i, line in enumerate(lines)
        if (m := _NUMBERED_RE.match(line))
    ]
    run: list[tuple[int, int]] = []
    expected = 1
    for index, number in candidates:
        if number == expected:
            run.append((index, number))
            expected += 1
    return run


def subpart_labels(lines: tuple[str, ...] | list[str]) -> list[str]:
    """Sub-part letters, a) b) c), inside one problem."""
    return [m.group(1) for line in lines if (m := _SUBPART_RE.match(line))]
