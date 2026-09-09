"""SPEC.md 5c's second check: is a claim actually supported by what it cites?

The deterministic check in `generation/verify.py` catches fabricated ids and
citation drift and costs nothing. It cannot catch a fluent claim that no passage
supports and that reuses the vocabulary of the one it cites. That failure is
what this measures.

**This is not a gate and must not become one.** 5c rejected putting a judge in
the answer path: it doubles latency and cost on every query to catch a failure
whose rate has not been measured, and a gate deciding on the verdict of an
unvalidated judge is worse than no gate. It runs here, over an eval set, and
produces a number.

**The judge's own accuracy is unmeasured, and that is a property of this file,
not a caveat about it.** Reporting this rate as a grounding metric asserts more
than has been measured. Module 6 either hand-labels a sample and reports
judge-versus-human agreement alongside it, or reports it as a diagnostic. The
`caveat` on every report says so, so a number cannot travel without it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from recall.generation.generate import GenerationError, Generator
from recall.generation.models import Answer, Claim
from recall.indexing.store import IndexEntry

CAVEAT = (
    "unvalidated judge — agreement with a human is unmeasured (SPEC.md 5c)"
)

JUDGE_INSTRUCTION = """\
You are checking whether a claim is supported by a passage.

Answer "supported": true only if the passage states or directly implies the \
claim. If the passage is merely on the same topic, or supports something \
similar but not this claim, answer false. Do not use any knowledge beyond the \
passage.
"""

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["supported", "reason"],
}


@dataclass(frozen=True)
class Verdict:
    claim: Claim
    supported: bool
    reason: str


@dataclass(frozen=True)
class GroundingReport:
    """How many claims the judge considered supported, and the caveat with it."""

    verdicts: tuple[Verdict, ...]
    errors: tuple[str, ...] = ()
    caveat: str = CAVEAT

    @property
    def judged(self) -> int:
        return len(self.verdicts)

    @property
    def supported(self) -> int:
        return sum(1 for v in self.verdicts if v.supported)

    @property
    def rate(self) -> float | None:
        """Supported fraction, or None when nothing was judged.

        None rather than 0.0, so an answer with no claims cannot be recorded as
        perfectly ungrounded — the same reasoning 2c applies to a gold label
        matching zero chunks.
        """
        return self.supported / self.judged if self.judged else None


def build_judge_prompt(claim: Claim, passage: str) -> str:
    return (
        f"{JUDGE_INSTRUCTION}\n"
        f"--- passage ---\n\n{passage}\n\n"
        f"--- claim ---\n\n{claim.text}\n"
    )


def judge_claim(
    generator: Generator, claim: Claim, context: Mapping[str, IndexEntry]
) -> Verdict:
    """Supported if any single cited passage supports the claim.

    Any rather than all: a claim citing two passages is asserting that they
    jointly bear on it, and requiring every one to support it alone would score
    a correct multi-source citation as a failure.
    """
    passages = [context[cid].chunk.text for cid in claim.chunk_ids if cid in context]
    if not passages:
        return Verdict(claim, False, "cites nothing that was in the context")

    reasons: list[str] = []
    for passage in passages:
        raw = generator.complete(build_judge_prompt(claim, passage), JUDGE_SCHEMA)
        try:
            data = json.loads(raw)
            supported = data["supported"]
            reason = data.get("reason", "")
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise GenerationError(f"judge returned unusable output: {exc}") from exc
        if not isinstance(supported, bool):
            raise GenerationError("judge's 'supported' was not a boolean")
        if supported:
            return Verdict(claim, True, str(reason))
        reasons.append(str(reason))
    return Verdict(claim, False, "; ".join(r for r in reasons if r))


def judge_claims(
    generator: Generator,
    claims: Sequence[Claim],
    context: Mapping[str, IndexEntry],
) -> GroundingReport:
    """Judge every claim, keeping a failed judgement out of the numerator.

    A judge that errors on a claim has not found it unsupported, so it is
    recorded as an error rather than counted as a failure. Folding the two
    together would make a flaky judge look like an ungrounded system.
    """
    verdicts: list[Verdict] = []
    errors: list[str] = []
    for claim in claims:
        try:
            verdicts.append(judge_claim(generator, claim, context))
        except GenerationError as exc:
            errors.append(str(exc))
    return GroundingReport(tuple(verdicts), tuple(errors))


def judge_answer(
    generator: Generator, answer: Answer, context: Mapping[str, IndexEntry]
) -> GroundingReport:
    return judge_claims(generator, answer.claims, context)
