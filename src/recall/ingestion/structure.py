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
# "Problem 3:" / "Problem 3." / "Question 3 -". An explicit label cannot be
# confused with a sub-question, which is what makes it worth preferring.
_LABELLED_RE = re.compile(
    r"^\s{0,4}(?:problem|question|exercise)\s+(\d{1,2})\s*(?:[:.)\-\u2014]|\s|$)", re.I
)
_SUBPART_RE = re.compile(r"^\s{0,6}([a-h])\s*[\.\)]\s+\S")
_WHITESPACE_RE = re.compile(r"\s+")
_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def comparable(text: str) -> str:
    """Punctuation- and case-insensitive form, for matching text the PDF renders
    differently in two places — a title reading `Cookies: keeping state` appears
    in the body as `Cookies: keeping " state "`."""
    return _ALNUM_RE.sub("", text.lower())


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


def _ascending_run(candidates: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep only the items numbered 1, 2, 3, … in order.

    Requiring the run to increment by one from 1 is what separates real problem
    numbers from incidental digits in prose — "3 MB" and "Layer 4" appear in
    these sheets and must not be read as problem headers.
    """
    run: list[tuple[int, int]] = []
    expected = 1
    for index, number in candidates:
        if number == expected:
            run.append((index, number))
            expected += 1
    return run


def _increasing(candidates: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep labelled items whose numbers only ever increase.

    Looser than `_ascending_run` on purpose. That rule exists to stop a bare
    "3." in prose being read as a problem header, and an explicit "Problem 3."
    needs no such protection. Real sheets are not tidy: MIT 6.02's `ps9` starts
    at Problem 0 and skips 7, and demanding an exact 1..N run rejected the whole
    sheet over it. Strictly increasing still discards a repeated header and a
    back-reference to an earlier problem.
    """
    kept: list[tuple[int, int]] = []
    for index, number in candidates:
        if not kept or number > kept[-1][1]:
            kept.append((index, number))
    return kept


def numbered_items(lines: tuple[str, ...] | list[str]) -> list[tuple[int, int]]:
    """Where each problem starts, as (line_index, number) pairs.

    Two conventions, and the explicit one wins where both appear. A sheet that
    writes "Problem 3:" is unambiguous; a sheet that writes a bare "3." is not,
    because a numbered *sub-question* inside a problem looks identical.

    The §8a corpus swap is what surfaced this. CS447's sheets use the bare form
    exclusively and were the only evidence when this was written. MIT 6.02's use
    both — an explicit "Problem N" heading, with bare "1. 2. 3." lists of
    sub-questions inside the problems. Reading the bare form first matched the
    sub-questions of problem 1, put every boundary in the wrong place, and swept
    the rest of the sheet into one chunk of 21,531 characters. Preferring the
    explicit label costs nothing on a sheet that has none.
    """
    labelled = _increasing([
        (i, int(m.group(1)))
        for i, line in enumerate(lines)
        if (m := _LABELLED_RE.match(line))
    ])
    if len(labelled) >= 2:
        return labelled

    return _ascending_run([
        (i, int(m.group(1)))
        for i, line in enumerate(lines)
        if (m := _NUMBERED_RE.match(line))
    ])


def subpart_labels(lines: tuple[str, ...] | list[str]) -> list[str]:
    """Sub-part letters, a) b) c), inside one problem."""
    return [m.group(1) for line in lines if (m := _SUBPART_RE.match(line))]


def sub_item_indices(lines: tuple[str, ...] | list[str]) -> list[int]:
    """Line indices where a sub-item starts, in either convention.

    Used by the size bound in §2b rather than by a chunker's own boundaries, so
    it deliberately does not require a run: inside one problem a stray "(c)" is
    a reasonable place to break, and a wrong break costs a slightly odd split
    rather than a mis-numbered problem.
    """
    return [
        i
        for i, line in enumerate(lines)
        if _NUMBERED_RE.match(line) or _SUBPART_RE.match(line)
    ]
