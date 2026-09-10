"""The metrics SPEC.md 6a chose, and nothing else.

6a picked Recall@k, MAP and abstention precision/recall because §2c's labels are
**binary** and **possibly multi-target** — a snippet either matches or it does
not, and several chunks may match one label. nDCG was rejected for needing
graded relevance this project does not have, and MRR for reading only the first
relevant result and so discarding the multi-match information 2c deliberately
kept.

Every function here is pure arithmetic over ids. Nothing loads a model, an index
or a corpus, so the tests can assert hand-computed values — which is the point:
a metric that is subtly wrong produces plausible numbers forever, and no amount
of behavioural testing catches it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Case:
    """One question's outcome, reduced to what the metrics need.

    `relevant` is empty for an unanswerable question, which is why the ranking
    metrics skip those rather than scoring them 0 — a question with no right
    answer has no recall.
    """

    question_id: str
    relevant: frozenset[str] = frozenset()
    retrieved: tuple[str, ...] = ()
    abstained: bool = False
    answerable: bool = True
    cited: frozenset[str] = frozenset()
    outcome: str = ""


def recall_at_k(relevant: frozenset[str], retrieved: tuple[str, ...], k: int) -> float | None:
    """Fraction of the relevant chunks that appear in the top k.

    None rather than 0.0 when nothing is relevant: an unanswerable question has
    no recall to measure, and averaging a 0 in would report the abstention path
    as a ranking failure.
    """
    if not relevant:
        return None
    return len(relevant & set(retrieved[:k])) / len(relevant)


def average_precision(relevant: frozenset[str], retrieved: tuple[str, ...]) -> float | None:
    """Precision at each relevant hit, averaged over all relevant chunks.

    Divided by |relevant| rather than by the number of relevant items *found*,
    so failing to retrieve one costs the score. That is the choice that makes
    MAP reward finding all of them rather than finding one early.
    """
    if not relevant:
        return None
    hits = 0
    total = 0.0
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in relevant:
            hits += 1
            total += hits / rank
    return total / len(relevant)


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def mean_recall_at_k(cases: list[Case], k: int) -> float | None:
    return _mean([recall_at_k(c.relevant, c.retrieved, k) for c in cases])


def mean_average_precision(cases: list[Case]) -> float | None:
    return _mean([average_precision(c.relevant, c.retrieved) for c in cases])


@dataclass(frozen=True)
class Abstention:
    """How well the system refuses, scored against whether it should have.

    Positive class is "abstained", so precision asks *of the refusals, how many
    were right* and recall asks *of the questions with no answer, how many were
    refused*. Both are None when their denominator is empty, because a rate over
    nothing is not 0 — it is unmeasured, and 2c applies the same rule to a label
    matching no chunks.
    """

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0

    @property
    def precision(self) -> float | None:
        d = self.true_positive + self.false_positive
        return self.true_positive / d if d else None

    @property
    def recall(self) -> float | None:
        d = self.true_positive + self.false_negative
        return self.true_positive / d if d else None


def abstention(cases: list[Case]) -> Abstention:
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for c in cases:
        if c.abstained and not c.answerable:
            counts["tp"] += 1
        elif c.abstained and c.answerable:
            counts["fp"] += 1
        elif not c.abstained and not c.answerable:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return Abstention(counts["tp"], counts["fp"], counts["fn"], counts["tn"])


def citation_correctness(cases: list[Case]) -> float | None:
    """Of the chunks an answer cited, how many were actually relevant.

    §5c's deterministic check already guarantees a citation points at a chunk
    that was *in the context*. This asks the further question it cannot: whether
    that chunk was one the gold labels call relevant. Only answered questions
    carry citations, so the rest are skipped rather than counted as 0.
    """
    cited = sum(len(c.cited) for c in cases if c.cited)
    if not cited:
        return None
    correct = sum(len(c.cited & c.relevant) for c in cases if c.cited)
    return correct / cited


def outcome_mix(cases: list[Case]) -> dict[str, int]:
    """How many questions ended in each of §5's outcomes.

    Reported as a mix rather than folded into one number, because CLAUDE.md and
    5d both insist a retrieval miss, a model refusal and a failed verification
    are different defects with different fixes.
    """
    mix: dict[str, int] = {}
    for c in cases:
        if c.outcome:
            mix[c.outcome] = mix.get(c.outcome, 0) + 1
    return dict(sorted(mix.items()))


@dataclass
class Report:
    """Every figure from one run, plus the per-format breakdown 6b requires."""

    k_values: tuple[int, ...] = (1, 5, 20)
    recall: dict[int, float | None] = field(default_factory=dict)
    map: float | None = None
    abstention: Abstention = field(default_factory=Abstention)
    citation_correctness: float | None = None
    outcomes: dict[str, int] = field(default_factory=dict)
    by_format: dict[str, dict[str, float | None]] = field(default_factory=dict)
    questions: int = 0

    def to_dict(self) -> dict:
        return {
            "questions": self.questions,
            "recall": {f"@{k}": v for k, v in self.recall.items()},
            "map": self.map,
            "abstention": {
                "precision": self.abstention.precision,
                "recall": self.abstention.recall,
                "tp": self.abstention.true_positive,
                "fp": self.abstention.false_positive,
                "fn": self.abstention.false_negative,
                "tn": self.abstention.true_negative,
            },
            "citation_correctness": self.citation_correctness,
            "outcomes": self.outcomes,
            "by_format": self.by_format,
        }


def score(cases: list[Case], formats: dict[str, str] | None = None,
          k_values: tuple[int, ...] = (1, 5, 20)) -> Report:
    """Everything 6a reports, over one run's cases.

    `formats` maps question id to doc_type, so the per-format breakdown 6b
    requires is computed here rather than left for a reader to assemble — 6b's
    whole reason for the breakdown is that a weak branch must not hide inside
    the headline average.
    """
    report = Report(
        k_values=k_values,
        recall={k: mean_recall_at_k(cases, k) for k in k_values},
        map=mean_average_precision(cases),
        abstention=abstention(cases),
        citation_correctness=citation_correctness(cases),
        outcomes=outcome_mix(cases),
        questions=len(cases),
    )
    if formats:
        for fmt in sorted(set(formats.values())):
            subset = [c for c in cases if formats.get(c.question_id) == fmt]
            if subset:
                report.by_format[fmt] = {
                    "questions": len(subset),
                    **{f"recall@{k}": mean_recall_at_k(subset, k) for k in k_values},
                    "map": mean_average_precision(subset),
                }
    return report
