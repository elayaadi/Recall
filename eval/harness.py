"""Run the question set against one configuration, and record what produced it.

SPEC.md 6c's requirement is precise: *"so 'before and after tuning' is a real
comparison, not a memory."* That is a statement about what a run record must
contain. Four thresholds, two chunkers, two embedders, a generator and a corpus
can all vary, so a score without its configuration cannot be compared to
anything — the same rule the index already applies one level down by refusing to
be queried by an embedder that did not build it.

Retrieval-only by default. 6a decided that answers are scored too, and the
harness will do it, but generation on the local model takes minutes per question
on CPU: over 35 questions that is hours, not a command you run while tuning a
threshold. `--answers` opts in.

    uv run python eval/harness.py                    # retrieval, one run record
    uv run python eval/harness.py --answers          # also score answers
    uv run python eval/harness.py --sweep-abstain 0.55 0.70
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.labels import load_chunks, load_questions, relevant_ids  # noqa: E402
from eval.metrics import Case, score  # noqa: E402
from recall.indexing.build import make_embedder  # noqa: E402
from recall.indexing.store import NumpyStore  # noqa: E402
from recall.retrieval.retriever import (  # noqa: E402
    UNCALIBRATED_ABSTAIN,
    UNCALIBRATED_COLLAPSE,
    Retriever,
)

RUNS = Path("eval/runs")

# The depths 6a reports. recall@20 is the one 4c's trigger is phrased in.
K_VALUES = (1, 5, 20)


def corpus_fingerprint(chunks: list[dict]) -> dict:
    """Identify the corpus a run scored, so two runs can be told apart.

    Hashes the chunk ids rather than the files: a run is comparable to another
    only if the same passages existed, and re-chunking changes ids even when the
    PDFs do not.
    """
    digest = hashlib.sha256(
        "\x1f".join(sorted(c["chunk_id"] for c in chunks)).encode()
    ).hexdigest()[:16]
    files = sorted({c["source_file"] for c in chunks})
    return {"files": len(files), "chunks": len(chunks), "chunk_id_sha256": digest}


def run(
    *,
    index: Path,
    k: int,
    abstain: float,
    collapse: float,
    with_answers: bool = False,
    min_claims: int = 1,
    generator_model: str | None = None,
) -> dict:
    questions = load_questions()
    chunks = load_chunks()
    store = NumpyStore.load(index)
    embedder = make_embedder("local")
    # Ranking metrics are measured over a deeper list than the system returns.
    # Measuring recall@20 against a top-5 list makes it identical to recall@5 by
    # construction, which would leave §4c's reranker trigger -- "adopt one when
    # recall@20 is materially above recall@5" -- unable to fire whatever the
    # data said. The first baseline run reported exactly that before it was
    # caught. `k` still governs what a user of the system would see.
    depth = max(max(K_VALUES), k)
    scoring = Retriever(
        store, embedder, k=depth, abstain_threshold=abstain, collapse_threshold=collapse
    )
    retriever = Retriever(
        store, embedder, k=k, abstain_threshold=abstain, collapse_threshold=collapse
    )

    answerer = None
    if with_answers:
        from recall.generation.answerer import Answerer
        from recall.generation.generate import make_generator

        answerer = Answerer(
            retriever,
            make_generator(model=generator_model) if generator_model else make_generator(),
            min_verified_claims=min_claims,
        )

    formats = {}
    by_file = {c["source_file"]: c["doc_type"] for c in chunks}
    cases: list[Case] = []
    for q in questions:
        relevant = frozenset(relevant_ids(q, chunks)) if q.answerable else frozenset()
        if q.answerable:
            formats[q.id] = by_file.get(q.labels[0].file, "unknown")

        deep = scoring.retrieve(q.text)
        if answerer is None:
            shallow = retriever.retrieve(q.text)
            cases.append(
                Case(
                    question_id=q.id,
                    relevant=relevant,
                    retrieved=tuple(h.chunk_id for h in deep.hits),
                    # Abstention is the decision the system actually makes, at
                    # the k a user would run, not at the scoring depth.
                    abstained=shallow.abstained,
                    answerable=q.answerable,
                )
            )
            continue

        answer = answerer.answer(q.text)
        cited = frozenset(cid for cl in answer.claims for cid in cl.chunk_ids)
        cases.append(
            Case(
                question_id=q.id,
                relevant=relevant,
                retrieved=tuple(h.chunk_id for h in deep.hits),
                abstained=not answer.answered,
                answerable=q.answerable,
                cited=cited,
                outcome=answer.outcome,
            )
        )

    report = score(cases, formats, k_values=K_VALUES)
    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": corpus_fingerprint(chunks),
        "questions": {"file": "eval/questions/questions.toml", "count": len(questions)},
        "config": {
            "chunker": sorted({c["chunker"] for c in chunks}),
            "embedder": store.embedder_name,
            "retriever": {"k": k, "scoring_depth": depth,
                          "abstain": abstain, "collapse": collapse},
            "generation": (
                {"model": answerer._generator.name, "min_verified_claims": min_claims}
                if answerer
                else None
            ),
        },
        "metrics": report.to_dict(),
        # 6c: the reported figures are in-sample and say so, because a held-out
        # split of 35 questions leaves too few points to calibrate against.
        "caveat": "in-sample: thresholds are calibrated on this same question set",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the question set.")
    parser.add_argument("--index", type=Path, default=Path("data/index"))
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--abstain", type=float, default=UNCALIBRATED_ABSTAIN)
    parser.add_argument("--collapse", type=float, default=UNCALIBRATED_COLLAPSE)
    parser.add_argument("--answers", action="store_true", help="also run generation")
    parser.add_argument("--model", default=None, help="Ollama model for --answers")
    parser.add_argument("--min-claims", type=int, default=1)
    parser.add_argument("--label", default="", help="a name for this run record")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)

    record = run(
        index=args.index, k=args.k, abstain=args.abstain, collapse=args.collapse,
        with_answers=args.answers, min_claims=args.min_claims,
        generator_model=args.model,
    )
    if args.label:
        record["label"] = args.label

    m = record["metrics"]
    print(f"{record['questions']['count']} questions over {record['corpus']['chunks']} chunks")
    print(f"  recall@1  {_f(m['recall']['@1'])}   recall@5  {_f(m['recall']['@5'])}"
          f"   recall@20 {_f(m['recall']['@20'])}")
    print(f"  MAP       {_f(m['map'])}")
    a = m["abstention"]
    print(f"  abstention  precision {_f(a['precision'])}  recall {_f(a['recall'])}"
          f"   (tp {a['tp']} fp {a['fp']} fn {a['fn']} tn {a['tn']})")
    if m["outcomes"]:
        print(f"  outcomes  {m['outcomes']}")
    print("  by format:")
    for fmt, figures in m["by_format"].items():
        print(f"    {fmt:<15} n={figures['questions']:<3} "
              f"recall@5 {_f(figures['recall@5'])}  MAP {_f(figures['map'])}")

    if not args.no_save:
        RUNS.mkdir(parents=True, exist_ok=True)
        path = RUNS / f"{record['run_id'].replace(':', '')}.json"
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"\n  written to {path}")
    return 0


def _f(value: float | None) -> str:
    return "  —  " if value is None else f"{value:.3f}"


if __name__ == "__main__":
    sys.exit(main())
