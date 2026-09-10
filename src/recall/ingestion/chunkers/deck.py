"""Chunk a slide deck: one slide per chunk, merging consecutive same-title runs.

A title change closes a chunk, so a new topic can never be silently absorbed
into the previous one. Adjacency is load-bearing: the same title recurring
non-adjacently (20 cases in the corpus) stays separate, because a merged chunk
spanning intervening material would have no honest citation. See SPEC.md 2b.
"""

from __future__ import annotations

from ..boilerplate import strip_boilerplate
from ..models import DECK, STRUCTURAL, Chunk, Locator
from ..pdf import Document, Page
from ..structure import comparable, normalise_title
from .bound import UNCALIBRATED_MAX_CHARS, bounded_blocks

DEFAULT_MAX_WORDS = 1200  # guard only; the longest real run is 9 slides, ~800 words


def _title_and_body(page: Page, boilerplate: frozenset[str]) -> tuple[str | None, list[str]]:
    title = page.title(exclude=boilerplate)
    lines = strip_boilerplate(page.lines, boilerplate)
    if not title:
        return None, lines
    comparable_title = comparable(title)
    body = [
        line
        for line in lines
        if not (comparable(line) and comparable(line) in comparable_title)
    ]
    return title, body


def chunk_deck(
    document: Document,
    boilerplate: frozenset[str],
    *,
    max_words: int = DEFAULT_MAX_WORDS,
    max_chars: int = UNCALIBRATED_MAX_CHARS,
) -> list[Chunk]:
    slides: list[tuple[Page, str | None, list[str]]] = []
    for page in document.pages:
        if not page.has_text:
            continue  # reported by the pipeline, not silently folded into a neighbour
        title, body = _title_and_body(page, boilerplate)
        slides.append((page, title, body))

    chunks: list[Chunk] = []
    index = 0
    while index < len(slides):
        page, title, body = slides[index]
        key = normalise_title(title)
        run = [slides[index]]
        # An untitled slide cannot be shown to continue anything, so it stands alone.
        if key:
            while index + 1 < len(slides):
                next_page, next_title, next_body = slides[index + 1]
                if normalise_title(next_title) != key:
                    break
                words = sum(len(" ".join(b).split()) for _, _, b in run)
                if words + len(" ".join(next_body).split()) > max_words:
                    break
                run.append(slides[index + 1])
                index += 1
        for chunk in _build(document, run, title, max_chars):
            # A divider slide carrying only a title over a diagram has nothing
            # to retrieve. Dropped here and reported by the pipeline as an
            # uncovered page, rather than indexed as a chunk that can match a
            # query and then answer nothing.
            if chunk.raw_text.strip():
                chunks.append(chunk)
        index += 1
    return chunks


def _build(
    document: Document,
    run: list[tuple[Page, str | None, list[str]]],
    title: str | None,
    max_chars: int,
) -> list[Chunk]:
    """One chunk per slide run — or more, if the run exceeds the window.

    §2b amended. A dense slide, or a merged run of same-titled slides, can pass
    the embedder's 512-token window, past which its text is not represented at
    all. Every piece keeps the run's title, so the topic prefix that makes a
    bare bullet retrievable survives the split.
    """
    located = [(page.number, line) for page, _, lines in run for line in lines]
    prefix = f"{document.path.stem} — {title}" if title else document.path.stem
    out: list[Chunk] = []
    for piece in bounded_blocks(located, max_chars=max_chars) or [[]]:
        body = "\n".join(line for _, line in piece)
        pages = tuple(dict.fromkeys(p for p, _ in piece)) or tuple(
            page.number for page, _, _ in run
        )
        out.append(
            Chunk.make(
                source_file=document.name,
                source_sha256=document.sha256,
                doc_type=DECK,
                chunker=STRUCTURAL,
                locator=Locator(kind=DECK, pages=pages, title=title),
                text=f"{prefix}\n\n{body}".strip(),
                raw_text=body.strip(),
            )
        )
    return out
