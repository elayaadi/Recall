"""The `recall-answer` command — generation exercised by hand.

Modules 2 and 3 each shipped a defect the test suite passed straight over and
reading real output caught, which is why `recall-ingest` and `recall-search`
print what they did rather than only what they returned. This is the same
affordance one module further on: it shows the outcome, the claims, the
citations each claim resolved to, and — the part worth looking at — the claims
that were dropped, because a dropped claim is the most direct evidence there is
of the model answering past its context.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..indexing.build import make_embedder
from ..indexing.store import NumpyStore
from ..retrieval.retriever import (
    UNCALIBRATED_ABSTAIN,
    UNCALIBRATED_COLLAPSE,
    Retriever,
)
from .answerer import UNCALIBRATED_MIN_CLAIMS, Answerer
from .generate import (
    LOCAL,
    LOCAL_MODEL,
    TIMEOUT_SECONDS,
    generator_names,
    make_generator,
)
from .models import ANSWERED
from .prompt import build_prompt
from .verify import NGRAM_WORDS

DEFAULT_INDEX = Path("data/index")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Answer a question from the index.")
    parser.add_argument("query", nargs="+", help="the question to ask")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("-k", type=int, default=5, help="passages given to the model")
    parser.add_argument("--type", dest="doc_type", help="deck | problem_sheet | syllabus")
    parser.add_argument("--file", dest="source_file", help="restrict to one source file")
    parser.add_argument(
        "--generator", choices=list(generator_names()), default=LOCAL,
        help=f"only {LOCAL} exists — SPEC.md 5a's hosted provider is unnamed",
    )
    parser.add_argument(
        "--model", default=LOCAL_MODEL,
        help=f"the Ollama model to use (default {LOCAL_MODEL}, not a measured choice)",
    )
    parser.add_argument(
        "--threshold", type=float, default=UNCALIBRATED_ABSTAIN,
        help=f"retrieval abstains below this (uncalibrated {UNCALIBRATED_ABSTAIN})",
    )
    parser.add_argument(
        "--collapse", type=float, default=UNCALIBRATED_COLLAPSE,
        help=f"collapse results this similar (uncalibrated {UNCALIBRATED_COLLAPSE})",
    )
    parser.add_argument(
        "--min-claims", type=int, default=UNCALIBRATED_MIN_CLAIMS,
        help=f"abstain below this many verified claims (uncalibrated {UNCALIBRATED_MIN_CLAIMS})",
    )
    parser.add_argument(
        "--ngram", type=int, default=NGRAM_WORDS,
        help=f"words a claim must share with the passage it cites (default {NGRAM_WORDS})",
    )
    parser.add_argument(
        "--timeout", type=int, default=TIMEOUT_SECONDS,
        help=f"seconds to wait for the model (default {TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--show-prompt", action="store_true",
        help="print the assembled prompt and exit without calling a model",
    )
    args = parser.parse_args(argv)

    if not (args.index / "index.json").exists():
        parser.error(f"no index at {args.index} — run: uv run recall-index")

    query = " ".join(args.query)
    store = NumpyStore.load(args.index)
    embedder = make_embedder("local")
    retriever = Retriever(
        store, embedder, k=args.k,
        abstain_threshold=args.threshold, collapse_threshold=args.collapse,
    )

    if args.show_prompt:
        retrieved = retriever.retrieve(
            query, doc_type=args.doc_type, source_file=args.source_file
        )
        if retrieved.abstained:
            print(f"ABSTAINED before the model ran: {retrieved.reason}")
            return 0
        print(build_prompt(query, retrieved.hits))
        return 0

    answerer = Answerer(
        retriever,
        make_generator(args.generator, model=args.model, timeout=args.timeout),
        min_verified_claims=args.min_claims,
        ngram=args.ngram,
    )
    answer = answerer.answer(
        query, doc_type=args.doc_type, source_file=args.source_file
    )

    print(f'"{query}"  —  {answer.generator} over {len(store)} entries\n')
    if answer.outcome != ANSWERED:
        print(f"  {answer.outcome.upper()}: {answer.reason}")
        _show_dropped(answer)
        print("\n  (both thresholds are uncalibrated until module 6 — SPEC.md 4b, 5d)")
        return 0

    print(f"  {answer.text}\n")
    for i, claim in enumerate(answer.claims, 1):
        print(f"  {i}. {claim.text}")
        for citation in claim.citations:
            print(f"       {citation}")
    _show_dropped(answer)
    return 0


def _show_dropped(answer) -> None:
    if not answer.dropped:
        return
    print(f"\n  {len(answer.dropped)} claim(s) dropped by the 5c check:")
    for claim in answer.dropped:
        body = " ".join(claim.text.split())
        print(f"    - {body[:100]}")
        print(f"      cited: {', '.join(claim.chunk_ids) or '(nothing)'}")


if __name__ == "__main__":
    sys.exit(main())
