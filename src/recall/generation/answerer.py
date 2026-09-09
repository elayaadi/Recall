"""Retrieval, generation and verification composed into one answer.

This is where SPEC.md 5d's decision lives: generation may refuse on its own,
independently of 4b's threshold. 4b measures similarity to the query and
structurally cannot see five well-scoring passages that do not answer it, so no
threshold on a similarity score closes that gap. Two mechanisms close it, and
they are different in kind — the model's own judgement, and a count of claims
surviving 5c's deterministic check.

The minimum-verified-claims threshold is a constructor argument with an
uncalibrated default, for the reason 4e gives for the retrieval thresholds: it
is a property of the generator and the corpus, module 6 sets it, and the 8a
corpus swap resets it. A module constant here would make a placeholder
indistinguishable from a measured value.
"""

from __future__ import annotations

from ..retrieval.retriever import Retriever
from .generate import GenerationError, Generator, parse_response
from .models import (
    ANSWERED,
    FAILED,
    MODEL_ABSTAINED,
    NO_PASSAGES,
    UNVERIFIED,
    Answer,
    compose,
)
from .prompt import build_prompt, response_schema
from .verify import NGRAM_WORDS, verify

# Uncalibrated. One verified claim is the weakest non-zero bar — it asks that
# the answer rest on something checkable, not that it rest on much. Module 6
# sets it from the question set.
UNCALIBRATED_MIN_CLAIMS = 1


class Answerer:
    """Query in, grounded answer out — or one of four ways of not answering."""

    def __init__(
        self,
        retriever: Retriever,
        generator: Generator,
        *,
        min_verified_claims: int = UNCALIBRATED_MIN_CLAIMS,
        ngram: int = NGRAM_WORDS,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self.min_verified_claims = min_verified_claims
        self.ngram = ngram

    def answer(
        self,
        query: str,
        *,
        doc_type: str | None = None,
        source_file: str | None = None,
    ) -> Answer:
        name = self._generator.name

        retrieved = self._retriever.retrieve(
            query, doc_type=doc_type, source_file=source_file
        )
        if retrieved.abstained:
            return Answer(query, "", (), NO_PASSAGES, retrieved.reason, name)

        context = {hit.chunk_id: hit.entry for hit in retrieved.hits}
        prompt = build_prompt(query, retrieved.hits)

        try:
            raw = self._generator.complete(prompt, response_schema(list(context)))
            text, claims, abstained, reason = parse_response(raw)
        except GenerationError as exc:
            return Answer(query, "", (), FAILED, str(exc), name)

        if abstained:
            return Answer(
                query, "", (), MODEL_ABSTAINED, reason or "the model abstained", name
            )

        kept, checks = verify(claims, context, ngram=self.ngram)
        dropped = tuple(c.claim for c in checks if not c.ok)

        if len(kept) < self.min_verified_claims:
            failures = "; ".join(c.reason for c in checks if not c.ok)
            return Answer(
                query, "", (), UNVERIFIED,
                f"{len(kept)} of {len(claims)} claims verified, "
                f"below the minimum of {self.min_verified_claims}"
                + (f" — {failures}" if failures else ""),
                name, dropped=dropped,
            )

        return Answer(
            query, compose(kept), tuple(kept), ANSWERED, "", name,
            dropped=dropped, draft=text,
        )
