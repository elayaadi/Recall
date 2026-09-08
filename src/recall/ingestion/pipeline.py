"""Run ingestion over a directory of PDFs and write chunks to JSONL.

Chunks land on disk rather than being handed to the indexer in memory so that
re-chunking and re-embedding stay separate steps, and so the chunks can be read
by eye when retrieval misses something it should have found. SQLite becomes the
right store once module 7's API needs incremental per-document ingest; the
chunk schema is unchanged by that move. See SPEC.md 2c.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from .boilerplate import find_boilerplate
from .chunkers import chunk_document
from .classify import classify
from .models import STRUCTURAL, WINDOW, Chunk
from .pdf import Document, load


@dataclass(frozen=True)
class FileReport:
    """What ingestion did to one file, and what it could not do."""

    source_file: str
    doc_type: str
    reason: str
    pages: int
    empty_pages: tuple[int, ...]
    uncovered_pages: tuple[int, ...]
    boilerplate_lines: int
    chunks: int
    words: int

    def line(self) -> str:
        uncovered = f"  uncovered:{len(self.uncovered_pages)}" if self.uncovered_pages else ""
        return (
            f"{self.source_file[:34]:<35} {self.doc_type:<14} "
            f"{self.pages:>4}pg {self.chunks:>4} chunks {self.words:>6}w{uncovered}"
        )


def ingest_file(
    path: Path, *, chunker: str = STRUCTURAL
) -> tuple[list[Chunk], FileReport]:
    document = load(path)
    classification = classify(document)
    boilerplate = find_boilerplate(document)
    chunks = chunk_document(
        document, classification.doc_type, boilerplate, chunker=chunker
    )
    covered = {page for chunk in chunks for page in chunk.locator.pages}
    report = FileReport(
        source_file=document.name,
        doc_type=classification.doc_type,
        reason=classification.reason,
        pages=len(document.pages),
        empty_pages=document.empty_pages,
        uncovered_pages=tuple(p.number for p in document.pages if p.number not in covered),
        boilerplate_lines=len(boilerplate),
        chunks=len(chunks),
        words=sum(c.n_words for c in chunks),
    )
    return chunks, report


def ingest_directory(
    directory: Path, *, chunker: str = STRUCTURAL
) -> tuple[list[Chunk], list[FileReport]]:
    all_chunks: list[Chunk] = []
    reports: list[FileReport] = []
    for path in sorted(directory.glob("*.pdf")):
        chunks, report = ingest_file(path, chunker=chunker)
        all_chunks.extend(chunks)
        reports.append(report)
    return all_chunks, reports


def write_jsonl(chunks: list[Chunk], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")


def read_jsonl(source: Path) -> list[Chunk]:
    with source.open(encoding="utf-8") as fh:
        return [Chunk.from_dict(json.loads(line)) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest PDFs into chunks.")
    parser.add_argument("source", type=Path, help="directory of PDFs")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/chunks.jsonl"))
    parser.add_argument(
        "--chunker", choices=[STRUCTURAL, WINDOW], default=STRUCTURAL,
        help="structural (primary) or window (measured baseline)",
    )
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        parser.error(f"not a directory: {args.source}")

    chunks, reports = ingest_directory(args.source, chunker=args.chunker)
    write_jsonl(chunks, args.output)

    for report in reports:
        print(report.line())

    uncovered = sum(len(r.uncovered_pages) for r in reports)
    words = sum(c.n_words for c in chunks)
    print("-" * 78)
    print(
        f"{len(reports)} files, {sum(r.pages for r in reports)} pages -> "
        f"{len(chunks)} chunks ({args.chunker}), {words:,} words, "
        f"mean {words / max(len(chunks), 1):.0f} words/chunk"
    )
    if uncovered:
        print(
            f"{uncovered} pages produced no chunk (no text layer, or a title "
            f"over a diagram with no body text):"
        )
        for report in reports:
            if report.uncovered_pages:
                print(f"  {report.source_file}: pages {list(report.uncovered_pages)}")
    print(f"written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
