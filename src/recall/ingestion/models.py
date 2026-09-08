"""Chunk and locator types shared by every ingestion path.

A chunk is the unit of retrieval, of citation, and of generation context, so
these types are deliberately explicit: a structured locator per document type
rather than a formatted string, so citations render correctly for slides,
problems and syllabus sections without anything having to parse them back.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

DECK = "deck"
PROBLEM_SHEET = "problem_sheet"
SYLLABUS = "syllabus"
UNKNOWN = "unknown"

STRUCTURAL = "structural"
WINDOW = "window"


def _format_pages(pages: tuple[int, ...]) -> str:
    if not pages:
        return ""
    if len(pages) == 1:
        return str(pages[0])
    if pages == tuple(range(pages[0], pages[-1] + 1)):
        return f"{pages[0]}–{pages[-1]}"
    return ", ".join(str(p) for p in pages)


@dataclass(frozen=True)
class Locator:
    """Where a chunk came from, in terms native to its document type."""

    kind: str
    pages: tuple[int, ...]
    title: str | None = None
    problem: str | None = None
    parts: tuple[str, ...] = ()

    def cite(self) -> str:
        pages = _format_pages(self.pages)
        if self.kind == DECK:
            label = f"slide {pages}" if len(self.pages) == 1 else f"slides {pages}"
            return f'{label} — "{self.title}"' if self.title else label
        if self.kind == PROBLEM_SHEET:
            parts = f"({', '.join(self.parts)})" if self.parts else ""
            return f"p.{pages}, problem {self.problem}{parts}"
        if self.kind == SYLLABUS:
            return f"p.{pages} — {self.title}" if self.title else f"p.{pages}"
        return f"p.{pages}" if len(self.pages) == 1 else f"pp.{pages}"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "pages": list(self.pages)}
        if self.title is not None:
            d["title"] = self.title
        if self.problem is not None:
            d["problem"] = self.problem
        if self.parts:
            d["parts"] = list(self.parts)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Locator:
        return cls(
            kind=d["kind"],
            pages=tuple(d["pages"]),
            title=d.get("title"),
            problem=d.get("problem"),
            parts=tuple(d.get("parts", ())),
        )


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage.

    `text` carries the title/section prefix that gives an otherwise contextless
    slide bullet its topic; `raw_text` is what was actually on the page. Both
    are kept so the eval harness can match gold snippets against the source
    text without the prefix creating false positives.
    """

    chunk_id: str
    source_file: str
    source_sha256: str
    doc_type: str
    chunker: str
    locator: Locator
    text: str
    raw_text: str
    n_words: int
    n_chars: int

    @classmethod
    def make(
        cls,
        *,
        source_file: str,
        source_sha256: str,
        doc_type: str,
        chunker: str,
        locator: Locator,
        text: str,
        raw_text: str,
    ) -> Chunk:
        digest = hashlib.sha256(
            "\x1f".join(
                [source_file, chunker, repr(locator.to_dict()), raw_text]
            ).encode("utf-8")
        ).hexdigest()[:16]
        return cls(
            chunk_id=digest,
            source_file=source_file,
            source_sha256=source_sha256,
            doc_type=doc_type,
            chunker=chunker,
            locator=locator,
            text=text,
            raw_text=raw_text,
            n_words=len(raw_text.split()),
            n_chars=len(raw_text),
        )

    def citation(self) -> str:
        return f"{self.source_file}, {self.locator.cite()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
            "doc_type": self.doc_type,
            "chunker": self.chunker,
            "locator": self.locator.to_dict(),
            "text": self.text,
            "raw_text": self.raw_text,
            "n_words": self.n_words,
            "n_chars": self.n_chars,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Chunk:
        return cls(
            chunk_id=d["chunk_id"],
            source_file=d["source_file"],
            source_sha256=d["source_sha256"],
            doc_type=d["doc_type"],
            chunker=d["chunker"],
            locator=Locator.from_dict(d["locator"]),
            text=d["text"],
            raw_text=d["raw_text"],
            n_words=d["n_words"],
            n_chars=d["n_chars"],
        )
