"""Sweep the abstention threshold against the question set. SPEC.md 4b, 6.

θ shipped uncalibrated because §4's probe could support the mechanism and not
the number: eight self-written queries separating cleanly is not a calibration.
This is the measurement §4b deferred to here.

Retrieval runs **once**. The threshold changes only whether a result is
returned, never the ranking, so sweeping it by re-querying would embed the same
35 questions at every step and measure nothing new. Each question's top-1 score
is recorded once and every candidate θ is scored against those.

    uv run python eval/calibrate.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.labels import load_chunks, load_questions, relevant_ids  # noqa: E402
from eval.metrics import Case, abstention, mean_average_precision, mean_recall_at_k  # noqa: E402
from recall.indexing.build import make_embedder  # noqa: E402
from recall.indexing.store import NumpyStore  # noqa: E402
from recall.retrieval.retriever import Retriever  # noqa: E402


def probe(index: Path, depth: int = 20, collapse: float = 0.95):
    """Retrieve once per question with abstention off, keeping the top-1 score."""
    questions = load_questions()
    chunks = load_chunks()
    store = NumpyStore.load(index)
    retriever = Retriever(
        store, make_embedder("local"), k=depth,
        abstain_threshold=0.0, collapse_threshold=collapse,
    )
    rows = []
    for q in questions:
        result = retriever.retrieve(q.text)
        rows.append({
            "id": q.id,
            "answerable": q.answerable,
            "relevant": frozenset(relevant_ids(q, chunks)) if q.answerable else frozenset(),
            "retrieved": tuple(h.chunk_id for h in result.hits),
            "top1": result.hits[0].score if result.hits else 0.0,
        })
    return rows


def score_at(rows, theta: float, k: int = 5):
    cases = [
        Case(
            question_id=r["id"],
            relevant=r["relevant"],
            # Below θ the system returns nothing, so nothing is retrieved.
            retrieved=() if r["top1"] < theta else r["retrieved"],
            abstained=r["top1"] < theta,
            answerable=r["answerable"],
        )
        for r in rows
    ]
    a = abstention(cases)
    return {
        "theta": theta,
        "recall@5": mean_recall_at_k(cases, k),
        "map": mean_average_precision(cases),
        "abstain_p": a.precision,
        "abstain_r": a.recall,
        "fp": a.false_positive,
        "fn": a.false_negative,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate the abstention threshold.")
    parser.add_argument("--index", type=Path, default=Path("data/index"))
    parser.add_argument("--low", type=float, default=0.50)
    parser.add_argument("--high", type=float, default=0.75)
    parser.add_argument("--step", type=float, default=0.01)
    args = parser.parse_args(argv)

    rows = probe(args.index)
    ans = sorted(r["top1"] for r in rows if r["answerable"])
    absent = sorted(r["top1"] for r in rows if not r["answerable"])
    print(f"top-1 score, answerable  : min {ans[0]:.3f}  median {ans[len(ans)//2]:.3f}  max {ans[-1]:.3f}")
    print(f"top-1 score, unanswerable: min {absent[0]:.3f}  median {absent[len(absent)//2]:.3f}  max {absent[-1]:.3f}")
    overlap = sum(1 for a in absent if a >= ans[0])
    print(f"unanswerable scoring at or above the lowest answerable: {overlap} of {len(absent)}")
    print(f"\n{'θ':>6}{'recall@5':>10}{'MAP':>8}{'abst P':>9}{'abst R':>9}{'fp':>4}{'fn':>4}")
    theta = args.low
    while theta <= args.high + 1e-9:
        s = score_at(rows, round(theta, 3))
        f = lambda v: "  —  " if v is None else f"{v:.3f}"
        print(f"{s['theta']:>6.2f}{f(s['recall@5']):>10}{f(s['map']):>8}"
              f"{f(s['abstain_p']):>9}{f(s['abstain_r']):>9}{s['fp']:>4}{s['fn']:>4}")
        theta += args.step
    return 0


if __name__ == "__main__":
    sys.exit(main())
