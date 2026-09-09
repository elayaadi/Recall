"""What reaches the model: the passages, their ids, and the schema.

SPEC.md 5b pins the response schema to the ids in one query's context, so a
backend that enforces schemas cannot emit a fabricated id at all. That is worth
asserting directly — it is the half of the grounding story that `verify.py`
does not cover.
"""

from __future__ import annotations

import pytest
from conftest import make_chunk

from recall.indexing.build import build_index
from recall.generation.prompt import (
    INSTRUCTION,
    build_prompt,
    render_passages,
    response_schema,
)
from recall.retrieval.retriever import Retriever


@pytest.fixture
def hits(fake_embedder):
    chunks = [
        make_chunk(text="routers hold packets in an output queue", pages=(1,)),
        make_chunk(text="TCP halves its congestion window on loss", pages=(2,)),
    ]
    store = build_index(chunks, fake_embedder)
    return Retriever(store, fake_embedder, abstain_threshold=0.0, k=2).retrieve(
        "routers"
    ).hits


def test_every_passage_carries_the_id_the_model_must_cite(hits):
    rendered = render_passages(hits)
    for hit in hits:
        assert f"[id: {hit.chunk_id}]" in rendered
        assert hit.entry.chunk.text in rendered


def test_the_schema_allows_only_this_querys_ids(hits):
    ids = [h.chunk_id for h in hits]
    schema = response_schema(ids)
    enum = schema["properties"]["claims"]["items"]["properties"]["chunk_ids"]["items"]
    assert enum["enum"] == ids


def test_the_schema_requires_the_fields_the_parser_reads(hits):
    schema = response_schema([h.chunk_id for h in hits])
    assert set(schema["required"]) == {"answer", "claims", "abstained", "reason"}
    item = schema["properties"]["claims"]["items"]
    assert set(item["required"]) == {"text", "chunk_ids"}


def test_a_claim_must_cite_at_least_one_passage(hits):
    schema = response_schema([h.chunk_id for h in hits])
    ids = schema["properties"]["claims"]["items"]["properties"]["chunk_ids"]
    assert ids["minItems"] == 1


def test_the_prompt_carries_the_instruction_the_question_and_the_passages(hits):
    prompt = build_prompt("why do routers drop packets", hits)
    assert INSTRUCTION in prompt
    assert "why do routers drop packets" in prompt
    assert render_passages(hits) in prompt


def test_the_instruction_appears_once(hits):
    """SPEC.md 5e keeps it singular: it is the whole mechanism before 5c runs."""
    assert build_prompt("q", hits).count(INSTRUCTION) == 1


def test_a_collapsed_passage_is_shown_once_not_once_per_location(fake_embedder):
    """4d's merged locations are citations, not separate passages to cite."""
    body = "a CDN redirects the client to a nearby replica"
    chunks = [
        make_chunk(text=f"A\n\n{body}", raw_text=body, source_file="lecture.pdf"),
        make_chunk(text=f"A\n\n{body}", raw_text=body, source_file="week.pdf"),
    ]
    store = build_index(chunks, fake_embedder)
    hits = Retriever(store, fake_embedder, abstain_threshold=0.0).retrieve(
        f"A\n\n{body}"
    ).hits

    assert len(hits[0].citations()) == 2
    assert render_passages(hits).count(body) == 1
