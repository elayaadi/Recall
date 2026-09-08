"""Chunk a problem sheet: one chunk per numbered problem, sub-parts attached.

Splitting a problem from its (a)/(b) parts would produce chunks that cannot
answer anything, so the parent keeps them. Problem numbers are validated as a
sequential run, which is what distinguishes them from incidental digits in the
prose of these sheets ("3 MB", "Layer 4"). See SPEC.md 2b.
"""

from __future__ import annotations

from ..boilerplate import strip_boilerplate
from ..models import PROBLEM_SHEET, STRUCTURAL, Chunk, Locator
from ..pdf import Document
from ..structure import numbered_items, subpart_labels


def chunk_problem_sheet(document: Document, boilerplate: frozenset[str]) -> list[Chunk]:
    numbered_lines: list[tuple[int, str]] = []
    for page in document.pages:
        if not page.has_text:
            continue
        for line in strip_boilerplate(page.lines, boilerplate):
            numbered_lines.append((page.number, line))

    lines = [line for _, line in numbered_lines]
    items = numbered_items(lines)
    if not items:
        return []

    # Anything before problem 1 is the sheet's header, not part of a problem.
    chunks: list[Chunk] = []
    for position, (line_index, number) in enumerate(items):
        end = items[position + 1][0] if position + 1 < len(items) else len(lines)
        block = lines[line_index:end]
        page = numbered_lines[line_index][0]
        parts = tuple(dict.fromkeys(subpart_labels(block)))
        body = "\n".join(block).strip()
        prefix = f"{document.path.stem} — Problem {number}"
        chunks.append(
            Chunk.make(
                source_file=document.name,
                source_sha256=document.sha256,
                doc_type=PROBLEM_SHEET,
                chunker=STRUCTURAL,
                locator=Locator(
                    kind=PROBLEM_SHEET, pages=(page,), problem=str(number), parts=parts
                ),
                text=f"{prefix}\n\n{body}".strip(),
                raw_text=body,
            )
        )
    return chunks
