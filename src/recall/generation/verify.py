"""SPEC.md 5c's deterministic check: no model call, no latency, no cost.

Two questions, both answerable from the text alone:

1. Does every id a claim names belong to a passage that was actually in this
   query's context? This catches a fabricated id, and it is the half the
   response schema already prevents on a backend that enforces it — but 5b
   records that the default backend is the one least able to do so, so it is
   checked here rather than assumed.
2. Does the claim share an n-word phrase with a passage it cites? This catches
   citation drift: a real id attached to a claim that passage does not support.

What this cannot catch is a fluent claim that no passage supports and that
happens to reuse the vocabulary of the one it cites. That is the failure 5c's
eval-time judge exists to measure, and it is why this check is not described as
proving groundedness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from ..indexing.store import IndexEntry
from .models import Claim

# Four words is long enough that ordinary shared vocabulary does not clear it
# and short enough that a close paraphrase still does. It is a starting value,
# not a measured one, and it is an argument rather than a constant for the same
# reason 4e gives for the retrieval thresholds.
NGRAM_WORDS = 4

_WORD = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _ngrams(words: Sequence[str], n: int) -> set[tuple[str, ...]]:
    if len(words) < n:
        return set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def shares_phrase(claim_text: str, passage_text: str, *, n: int = NGRAM_WORDS) -> bool:
    """Whether the claim and the passage share a run of `n` words.

    A claim shorter than `n` words has no n-gram to share, so it falls back to
    requiring that all of its words appear in the passage. Without that, a
    correct three-word claim would fail the check for being short.
    """
    claim_words = _words(claim_text)
    passage_words = _words(passage_text)
    if not claim_words:
        return False
    if len(claim_words) < n:
        return set(claim_words) <= set(passage_words)
    return bool(_ngrams(claim_words, n) & _ngrams(passage_words, n))


def strip_passage_ids(text: str, chunk_ids: Sequence[str]) -> str:
    """Remove passage ids the model wrote into the prose a reader sees.

    The instruction asks for an answer with no ids in it, and the first real run
    against the corpus produced three of them anyway — `(id: 2bf65592e5adecb9)`
    inline — which is the instruction-following weakness 5a records about the
    default backend, showing up on the first query rather than in the abstract.

    This is formatting, not coercion: it removes the id token and nothing else,
    so what the answer asserts is unchanged and 5c still checks the claims
    rather than this text. The citations remain, attached to the claims where
    they can be verified, which is where 5b decided they belong.
    """
    if not chunk_ids:
        return text
    ids = "|".join(re.escape(cid) for cid in chunk_ids)
    text = re.sub(rf"[\[(]\s*id:\s*(?:{ids})\s*[\])]", "", text)
    text = re.sub(rf"\b(?:{ids})\b", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\s+([.,;:])", r"\1", text).strip()


@dataclass(frozen=True)
class ClaimCheck:
    """One claim's verdict, carrying the reason so a failure can be read."""

    claim: Claim
    ok: bool
    reason: str = ""


def check_claim(
    claim: Claim,
    context: Mapping[str, IndexEntry],
    *,
    ngram: int = NGRAM_WORDS,
) -> ClaimCheck:
    if not claim.chunk_ids:
        return ClaimCheck(claim, False, "cites no passage")

    unknown = [cid for cid in claim.chunk_ids if cid not in context]
    if unknown:
        return ClaimCheck(
            claim, False, f"cites {', '.join(unknown)}, not in this query's context"
        )

    cited = [context[cid].chunk.text for cid in claim.chunk_ids]
    if not any(shares_phrase(claim.text, text, n=ngram) for text in cited):
        return ClaimCheck(
            claim, False, f"shares no {ngram}-word phrase with the passage it cites"
        )
    return ClaimCheck(claim, True)


def expand_citations(claim: Claim, context: Mapping[str, IndexEntry]) -> Claim:
    """Attach every location each cited passage appears at (SPEC.md 4d).

    The model cites a passage; this repo turns that into locations. Doing it
    after the model rather than before is what keeps the merged citations of a
    collapsed near-duplicate — the same passage re-released in two decks — from
    being silently reduced to whichever copy happened to survive collapse.
    """
    seen: dict[str, None] = {}
    for cid in claim.chunk_ids:
        entry = context.get(cid)
        if entry is None:
            continue
        for citation in entry.citations():
            seen.setdefault(citation, None)
    return Claim(text=claim.text, chunk_ids=claim.chunk_ids, citations=tuple(seen))


def verify(
    claims: Sequence[Claim],
    context: Mapping[str, IndexEntry],
    *,
    ngram: int = NGRAM_WORDS,
) -> tuple[list[Claim], list[ClaimCheck]]:
    """Return the claims that passed, with citations expanded, and every verdict.

    Both halves are returned because the failures are not noise to be discarded:
    a dropped claim is the most direct evidence there is of the model answering
    past its context, and `recall-answer` prints them for that reason.
    """
    checks = [check_claim(claim, context, ngram=ngram) for claim in claims]
    kept = [expand_citations(c.claim, context) for c in checks if c.ok]
    return kept, checks
