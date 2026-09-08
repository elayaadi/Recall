"""Chunk a syllabus on its ALL-CAPS section headings.

The corpus syllabus uses 11 of them across 3 pages. Its content is heavily
tabular, and plain extraction flattens a table into a readable but
row-ambiguous stream; that is accepted for v1 and recorded in SPEC.md 2b as a
known limitation rather than papered over.
"""

from __future__ import annotations

from ..boilerplate import strip_boilerplate
from ..models import STRUCTURAL, SYLLABUS, Chunk, Locator
from ..pdf import Document
from ..structure import all_caps_headings


def chunk_syllabus(document: Document, boilerplate: frozenset[str]) -> list[Chunk]:
    located: list[tuple[int, str]] = []
    for page in document.pages:
        if not page.has_text:
            continue
        for line in strip_boilerplate(page.lines, boilerplate):
            located.append((page.number, line))

    lines = [line for _, line in located]
    headings = set(all_caps_headings(lines))
    boundaries = [i for i, line in enumerate(lines) if line.strip() in headings]
    if not boundaries:
        return []

    sections: list[tuple[int, int, str | None]] = []
    if boundaries[0] > 0:
        sections.append((0, boundaries[0], None))  # preamble before the first heading
    for position, start in enumerate(boundaries):
        end = boundaries[position + 1] if position + 1 < len(boundaries) else len(lines)
        sections.append((start, end, lines[start].strip()))

    chunks: list[Chunk] = []
    for start, end, title in sections:
        block = lines[start:end] if title is None else lines[start + 1 : end]
        body = "\n".join(block).strip()
        if not body:
            continue
        page = located[start][0]
        prefix = f"{document.path.stem} — {title}" if title else document.path.stem
        chunks.append(
            Chunk.make(
                source_file=document.name,
                source_sha256=document.sha256,
                doc_type=SYLLABUS,
                chunker=STRUCTURAL,
                locator=Locator(kind=SYLLABUS, pages=(page,), title=title),
                text=f"{prefix}\n\n{body}".strip(),
                raw_text=body,
            )
        )
    return chunks
