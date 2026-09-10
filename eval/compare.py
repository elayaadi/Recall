"""Diff two run records. SPEC.md 6c.

The point of committing run records is that "before and after tuning" is a real
comparison rather than a memory. That only holds if the comparison refuses to
compare runs that are not comparable, so this prints the configuration delta
first and says plainly when the corpus itself changed underneath.

    uv run python eval/compare.py eval/runs/A.json eval/runs/B.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def flatten(metrics: dict) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for k, v in metrics.get("recall", {}).items():
        out[f"recall{k}"] = v
    out["map"] = metrics.get("map")
    a = metrics.get("abstention", {})
    out["abstain_precision"] = a.get("precision")
    out["abstain_recall"] = a.get("recall")
    out["citation_correctness"] = metrics.get("citation_correctness")
    for fmt, figures in metrics.get("by_format", {}).items():
        out[f"{fmt}/recall@5"] = figures.get("recall@5")
        out[f"{fmt}/map"] = figures.get("map")
    return out


def config_delta(a: dict, b: dict) -> list[str]:
    lines = []
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key):
            lines.append(f"    {key}: {a.get(key)!r} -> {b.get(key)!r}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two eval run records.")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args(argv)

    a = json.loads(args.before.read_text())
    b = json.loads(args.after.read_text())

    print(f"before  {a['run_id']}  {a.get('label','')}")
    print(f"after   {b['run_id']}  {b.get('label','')}\n")

    if a["corpus"]["chunk_id_sha256"] != b["corpus"]["chunk_id_sha256"]:
        print("  !! the corpus differs between these runs — the delta below mixes")
        print("     a corpus change with whatever else changed, and separates neither.")
        print(f"     {a['corpus']['chunks']} chunks -> {b['corpus']['chunks']} chunks\n")

    changes = config_delta(
        {**a["config"], **a["config"].get("retriever", {})},
        {**b["config"], **b["config"].get("retriever", {})},
    )
    print("  configuration:" if changes else "  configuration: identical")
    for line in changes:
        print(line)

    fa, fb = flatten(a["metrics"]), flatten(b["metrics"])
    print(f"\n  {'metric':<26}{'before':>9}{'after':>9}{'delta':>9}")
    for key in sorted(set(fa) | set(fb)):
        x, y = fa.get(key), fb.get(key)
        f = lambda v: "  —  " if v is None else f"{v:.3f}"
        d = "  —  " if x is None or y is None else f"{y - x:+.3f}"
        print(f"  {key:<26}{f(x):>9}{f(y):>9}{d:>9}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
