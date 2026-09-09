"""Read chunks by eye. The reason ingestion writes JSONL instead of handing
chunks straight to the indexer.

    uv run python scripts/inspect_chunks.py                    # summary
    uv run python scripts/inspect_chunks.py --shortest 15      # likely junk
    uv run python scripts/inspect_chunks.py --file "Lecture 5" # one document
    uv run python scripts/inspect_chunks.py --grep "hot potato"
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

DEFAULT_PATH = Path("data/chunks.jsonl")


def load(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"{path} not found — run: uv run recall-ingest data/raw")
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def cite(chunk: dict) -> str:
    loc = chunk["locator"]
    pages = loc["pages"]
    span = str(pages[0]) if len(pages) == 1 else f"{pages[0]}-{pages[-1]}"
    if loc["kind"] == "deck":
        return f"slide {span}"
    if loc["kind"] == "problem_sheet":
        return f"p.{span} prob {loc.get('problem')}"
    return f"p.{span}"


def show(chunks: list[dict], preview: int) -> None:
    for chunk in chunks:
        title = (chunk["locator"].get("title") or "").strip()
        body = " ".join(chunk["raw_text"].split())
        print(
            f"{chunk['n_words']:>4}w  {chunk['source_file'][:26]:<27} "
            f"{cite(chunk):<16} {title[:26]:<27} {body[:preview]}"
        )


def summarise(chunks: list[dict]) -> None:
    words = [c["n_words"] for c in chunks]
    print(f"{len(chunks)} chunks, {sum(words):,} words")
    print(
        f"words/chunk: mean {statistics.mean(words):.0f}  "
        f"median {statistics.median(words):.0f}  "
        f"min {min(words)}  max {max(words)}"
    )
    print("by type: " + ", ".join(f"{k}={v}" for k, v in Counter(c["doc_type"] for c in chunks).most_common()))
    print(f"merged multi-page chunks: {sum(1 for c in chunks if len(c['locator']['pages']) > 1)}")
    tiny = sum(1 for w in words if w < 15)
    print(f"chunks under 15 words: {tiny} ({tiny / len(chunks):.1%}) — inspect with --shortest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--shortest", type=int, metavar="N", help="the N smallest chunks")
    parser.add_argument("--longest", type=int, metavar="N", help="the N largest chunks")
    parser.add_argument("--file", help="only chunks whose source file contains this")
    parser.add_argument("--type", dest="doc_type", help="deck | problem_sheet | syllabus")
    parser.add_argument("--grep", help="only chunks whose text contains this (case-insensitive)")
    parser.add_argument("--preview", type=int, default=60, help="body characters to show")
    args = parser.parse_args()

    chunks = load(args.path)
    if args.file:
        chunks = [c for c in chunks if args.file.lower() in c["source_file"].lower()]
    if args.doc_type:
        chunks = [c for c in chunks if c["doc_type"] == args.doc_type]
    if args.grep:
        chunks = [c for c in chunks if args.grep.lower() in c["text"].lower()]
    if not chunks:
        raise SystemExit("no chunks matched")

    if args.shortest:
        show(sorted(chunks, key=lambda c: c["n_words"])[: args.shortest], args.preview)
    elif args.longest:
        show(sorted(chunks, key=lambda c: -c["n_words"])[: args.longest], args.preview)
    elif args.file or args.doc_type or args.grep:
        show(chunks, args.preview)
    else:
        summarise(chunks)


if __name__ == "__main__":
    main()
