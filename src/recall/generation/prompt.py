"""The context, the instruction, and the response schema — in one place.

SPEC.md 5e keeps the instruction text singular because it is the whole grounding
mechanism before 5c's check runs, and no test can assert that it works — only
that it exists and that there is one of it. Whether it works is a module 6
measurement, not a claim made here.

The schema constrains `chunk_ids` to an enum of exactly the ids in this query's
context. On a backend that enforces the schema, a fabricated id is impossible;
on one that does not, `verify.py` catches it. SPEC.md 5b records that the
default backend is the one least able to enforce this, so both halves are
needed — the schema is not a substitute for the check.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..indexing.store import SearchHit

INSTRUCTION = """\
You answer questions using only the passages provided below. You have no other \
source of knowledge for this task: if something is not in the passages, you do \
not know it, however familiar the topic is.

Rules:
- Break your answer into claims. Every claim must be supported by at least one \
passage, and must name the id of each passage that supports it.
- Never state anything the passages do not support, and never fill a gap from \
your own knowledge of the subject.
- If the passages do not answer the question, set "abstained" to true and say \
briefly what is missing. Passages that are on the same topic but do not answer \
the question are not an answer.
- Quote or closely paraphrase the wording of the passage a claim cites.
- Write "answer" as continuous prose saying the same thing as the claims. The \
claims are what is shown to a reader, so put your care into them.
"""


def response_schema(chunk_ids: Sequence[str]) -> dict[str, Any]:
    """The JSON schema for one query's response, pinned to its own passages."""
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "chunk_ids": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(chunk_ids)},
                            "minItems": 1,
                        },
                    },
                    "required": ["text", "chunk_ids"],
                },
            },
            "abstained": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["answer", "claims", "abstained", "reason"],
    }


def render_passages(hits: Sequence[SearchHit]) -> str:
    """The passages, each labelled with the id the model must cite it by.

    A hit that collapsed several locations (4d) appears once, as one passage.
    Its other locations are attached afterwards when citations are expanded —
    showing them here would invite the model to cite a location rather than a
    passage, which is the distinction 4d turns on.
    """
    return "\n\n".join(
        f"[id: {hit.chunk_id}]\n{hit.entry.chunk.text}" for hit in hits
    )


def build_prompt(query: str, hits: Sequence[SearchHit]) -> str:
    return (
        f"{INSTRUCTION}\n"
        f"--- passages ---\n\n{render_passages(hits)}\n\n"
        f"--- question ---\n\n{query}\n"
    )
