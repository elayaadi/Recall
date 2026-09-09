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
from typing import Sequence

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


def compose(claims: Sequence[Claim]) -> str:
    """Build the prose a reader sees out of the claims that passed 5c's check.

    SPEC.md 5b originally made this the model's own `answer` string. Three
    separate defects on the first real runs came from that: the model wrote
    passage ids into it, and it emitted a stray `}` inside the string. Removing
    the ids left sentences referring to something deleted — "this is stated in
    passage, which says" — which no amount of cleaning up can repair, because
    the sentence was built around a reference that is now gone.

    Composing instead makes the reader-facing text grounded by construction: it
    contains exactly the claims that were checked against the passages they
    cite, so there is nothing to strip and nothing that can drift from what was
    verified. The cost is the model's connective wording, which is why the
    model's own prose is kept as `Answer.draft` rather than discarded.
    """
    return " ".join(claim.text.strip() for claim in claims if claim.text.strip())


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
    # The model's own prose. Not shown as the answer — it is unverified, and 5b
    # is now explicit that what a reader sees is composed from checked claims.
    # Kept because the model's task is unchanged by this decision, so module 6
    # can compare the two without a second run.
    draft: str = ""

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
