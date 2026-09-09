"""The `recall-search` command — retrieval exercised by hand.

Modules 2 and 3 both had defects that the test suite passed over and reading
real output caught. This is the same affordance one level further on: run a
query against the built index and look at what comes back, including what was
collapsed and why something was refused.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..indexing.build import make_embedder
from ..indexing.store import NumpyStore
from .lexical import BM25Index
from .retriever import UNCALIBRATED_ABSTAIN, UNCALIBRATED_COLLAPSE, Retriever

DEFAULT_INDEX = Path("data/index")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the index.")
    parser.add_argument("query", nargs="+", help="the question to ask")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--type", dest="doc_type", help="deck | problem_sheet | syllabus")
    parser.add_argument("--file", dest="source_file", help="restrict to one source file")
    parser.add_argument(
        "--threshold", type=float, default=UNCALIBRATED_ABSTAIN,
        help=f"abstain below this score (uncalibrated default {UNCALIBRATED_ABSTAIN})",
    )
    parser.add_argument(
        "--collapse", type=float, default=UNCALIBRATED_COLLAPSE,
        help=f"collapse results this similar (uncalibrated default {UNCALIBRATED_COLLAPSE})",
    )
    parser.add_argument(
        "--lexical", action="store_true",
        help="run the BM25 baseline instead of dense retrieval (SPEC.md 4a)",
    )
    args = parser.parse_args(argv)

    if not (args.index / "index.json").exists():
        parser.error(f"no index at {args.index} — run: uv run recall-index")

    query = " ".join(args.query)
    store = NumpyStore.load(args.index)

    if args.lexical:
        hits = BM25Index(store.entries).search(
            query, k=args.k, doc_type=args.doc_type, source_file=args.source_file
        )
        print(f'"{query}"  —  BM25 baseline, {len(store)} entries\n')
        if not hits:
            print("  no results")
            return 0
        for hit in hits:
            _show(hit)
        return 0

    embedder = make_embedder("local")
    retriever = Retriever(
        store, embedder, k=args.k,
        abstain_threshold=args.threshold, collapse_threshold=args.collapse,
    )
    result = retriever.retrieve(
        query, doc_type=args.doc_type, source_file=args.source_file
    )

    print(f'"{query}"  —  {store.embedder_name}, {len(store)} entries\n')
    if result.abstained:
        print(f"  ABSTAINED: {result.reason}")
        print("  (threshold is uncalibrated until module 6 — see SPEC.md 4b)")
        return 0
    for hit in result.hits:
        _show(hit)
    if result.collapsed:
        print(f"\n  {result.collapsed} near-duplicate result(s) collapsed (SPEC.md 4d)")
    return 0


def _show(hit) -> None:
    body = " ".join(hit.entry.chunk.raw_text.split())
    citations = hit.citations()
    print(f"  {hit.score:.3f}  {citations[0]}")
    for extra in citations[1:]:
        print(f"         also at: {extra}")
    print(f"         {body[:120]}\n")


if __name__ == "__main__":
    sys.exit(main())
