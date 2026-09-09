"""What an answer is, and the five ways a query can end.

SPEC.md 5d makes generation able to refuse on its own, independently of the
retrieval threshold in 4b, and requires the two refusals to stay distinguishable
so module 6 can score them separately: a retrieval miss and a generation refusal
are different defects with different fixes. That is why `outcome` is a
discriminator rather than a boolean — collapsing them would lose exactly the
distinction 5d exists to preserve.

`FAILED` is deliberately not an abstention. SPEC.md 5b requires malformed model
output to surface as a generation failure rather than be coerced into an answer
or reported as a refusal the model did not make.
"""

from __future__ import annotations

from dataclasses import dataclass

ANSWERED = "answered"
NO_PASSAGES = "no_passages"          # 4b: retrieval abstained, nothing reached here
MODEL_ABSTAINED = "model_abstained"  # 5d: the model judged the context insufficient
UNVERIFIED = "unverified"            # 5d: too few claims survived 5c's check
FAILED = "failed"                    # 5b: the model's output could not be used

OUTCOMES = (ANSWERED, NO_PASSAGES, MODEL_ABSTAINED, UNVERIFIED, FAILED)


@dataclass(frozen=True)
class Claim:
    """One assertion, and the passages the model says support it.

    `chunk_ids` is what the model emitted and is checked, never trusted:
    SPEC.md 5b records that the default backend is the one least able to enforce
    the response schema. `citations` is filled in afterwards by expanding each
    id to every location that passage appears at (4d), which is why it is
    separate from what the model said rather than mixed into it.
    """

    text: str
    chunk_ids: tuple[str, ...]
    citations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Answer:
    """What generation decided, including deciding not to answer."""

    query: str
    text: str
    claims: tuple[Claim, ...]
    outcome: str
    reason: str
    generator: str
    dropped: tuple[Claim, ...] = ()

    @property
    def answered(self) -> bool:
        return self.outcome == ANSWERED

    def __bool__(self) -> bool:
        return self.answered

    def citations(self) -> list[str]:
        """Every location cited, in first-mention order, without repeats."""
        seen: dict[str, None] = {}
        for claim in self.claims:
            for citation in claim.citations:
                seen.setdefault(citation, None)
        return list(seen)
