"""Load a PDF into pages of lines and font-sized spans.

pdfplumber rather than a plain-text extractor because the slide title is the
largest-font span on a page, and plain text loses that: measured over 566
slides, "largest font" and "first line" agree only 44% of the time, because in
reading order the page number frequently comes first. See SPEC.md 2a.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

# Footers like "Page 1 of 2" differ per page, so repeated-line detection cannot
# catch them, but they are boilerplate all the same.
PAGE_FOOTER_RE = re.compile(r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$", re.I)
# Decks also print a bare slide number. Dropped only when it equals the page's
# own index, so a numeric line that is real content is never mistaken for one.
BARE_NUMBER_RE = re.compile(r"^\s*(\d{1,4})\s*$")

_LINE_TOLERANCE = 2.5  # points; words within this vertical distance are one line


@dataclass(frozen=True)
class Span:
    """A run of words sharing a font size on one line."""

    text: str
    size: float
    top: float
    x0: float


@dataclass(frozen=True)
class Page:
    number: int  # 1-based, as a human would cite it
    width: float
    height: float
    lines: tuple[str, ...]
    spans: tuple[Span, ...]
    has_images: bool

    @property
    def is_landscape(self) -> bool:
        return self.width > self.height

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())

    @property
    def n_words(self) -> int:
        return len(self.text.split())

    def largest_span_text(self, exclude: frozenset[str] = frozenset()) -> str | None:
        """The page's largest-font text, joined in reading order.

        A title is often split across sibling spans at the same size, so every
        span at the maximum size is joined rather than just the first.
        """
        spans = [s for s in self.spans if s.text.strip() and s.text.strip() not in exclude]
        if not spans:
            return None
        largest = max(s.size for s in spans)
        winners = sorted(
            (s for s in spans if abs(s.size - largest) < 0.01),
            key=lambda s: (round(s.top, 1), s.x0),
        )
        title = " ".join(s.text.strip() for s in winners).strip()
        return title or None


@dataclass(frozen=True)
class Document:
    path: Path
    sha256: str
    pages: tuple[Page, ...]

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def text_pages(self) -> tuple[Page, ...]:
        return tuple(p for p in self.pages if p.has_text)

    @property
    def empty_pages(self) -> tuple[int, ...]:
        return tuple(p.number for p in self.pages if not p.has_text)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _words_to_lines(words: list[dict]) -> tuple[tuple[str, ...], tuple[Span, ...]]:
    """Group pdfplumber words into visual lines, and lines into same-size spans."""
    if not words:
        return (), ()

    ordered = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines: list[list[dict]] = []
    for word in ordered:
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= _LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])

    line_texts: list[str] = []
    spans: list[Span] = []
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in line).strip()
        if text:
            line_texts.append(text)
        current: list[dict] = []
        for word in line:
            size = round(float(word.get("size", 0.0)), 1)
            if current and round(float(current[-1].get("size", 0.0)), 1) == size:
                current.append(word)
            else:
                if current:
                    spans.append(_span(current))
                current = [word]
        if current:
            spans.append(_span(current))

    return tuple(line_texts), tuple(spans)


def _span(words: list[dict]) -> Span:
    return Span(
        text=" ".join(w["text"] for w in words),
        size=round(float(words[0].get("size", 0.0)), 1),
        top=float(words[0]["top"]),
        x0=float(words[0]["x0"]),
    )


def load(path: str | Path) -> Document:
    """Read a PDF into pages. Text-less pages are kept, not dropped.

    Keeping them lets the pipeline report which pages produced nothing, instead
    of silently shrinking the corpus. See SPEC.md 2.
    """
    path = Path(path)
    pages: list[Page] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(extra_attrs=["size"], use_text_flow=False)
            lines, spans = _words_to_lines(words)
            lines = tuple(
                l
                for l in lines
                if not PAGE_FOOTER_RE.match(l)
                and not ((m := BARE_NUMBER_RE.match(l)) and int(m.group(1)) == index)
            )
            pages.append(
                Page(
                    number=index,
                    width=float(page.width),
                    height=float(page.height),
                    lines=lines,
                    spans=spans,
                    has_images=bool(page.images),
                )
            )
    return Document(path=path, sha256=_sha256(path), pages=tuple(pages))
