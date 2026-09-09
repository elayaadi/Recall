"""The five outcomes, each reached on purpose.

SPEC.md 5d requires a retrieval miss and a generation refusal to stay
distinguishable so module 6 can score them separately, and 5b requires
malformed output to be neither an answer nor a refusal. Both are properties of
`outcome`, so every branch is asserted on the outcome rather than on a boolean.
"""

from __future__ import annotations

import json

import pytest
from conftest import FakeGenerator, generation_response, make_chunk

from recall.generation.answerer import Answerer
from recall.generation.models import (
    ANSWERED,
    FAILED,
    MODEL_ABSTAINED,
    NO_PASSAGES,
    UNVERIFIED,
)
from recall.generation.generate import GenerationError
from recall.indexing.build import build_index
from recall.retrieval.retriever import Retriever

PASSAGE = "Routers drop packets when the output queue is full, which is called queueing loss."
GROUNDED = "Routers drop packets when the output queue is full"


@pytest.fixture
def store(fake_embedder):
    return build_index(
        [
            make_chunk(text=PASSAGE, pages=(1,)),
            make_chunk(text="TCP halves its congestion window on loss", pages=(2,)),
        ],
        fake_embedder,
    )


@pytest.fixture
def chunk_id(store):
    return next(e.chunk_id for e in store.entries if e.chunk.text == PASSAGE)


def answerer_for(store, fake_embedder, *responses, threshold=0.0, **kwargs):
    retriever = Retriever(store, fake_embedder, abstain_threshold=threshold)
    return Answerer(retriever, FakeGenerator(list(responses)), **kwargs)


def test_a_grounded_answer_is_returned_with_its_citations(store, fake_embedder, chunk_id):
    a = answerer_for(
        store, fake_embedder,
        generation_response(answer="They queue.", claims=[(GROUNDED, [chunk_id])]),
    ).answer("why do routers drop packets")

    assert a.outcome == ANSWERED
    assert a
    assert a.text == GROUNDED  # composed from the claim, not the model's prose
    assert len(a.claims) == 1
    assert a.claims[0].citations
    assert a.citations() == list(a.claims[0].citations)


def test_the_answer_records_which_generator_produced_it(store, fake_embedder, chunk_id):
    """5e: a module 6 number must never be attributable to the wrong model."""
    a = answerer_for(
        store, fake_embedder,
        generation_response(claims=[(GROUNDED, [chunk_id])]),
    ).answer("q")
    assert a.generator == "fake-generator"


def test_retrieval_abstention_never_reaches_the_model(store, fake_embedder):
    generator = FakeGenerator([generation_response()])
    retriever = Retriever(store, fake_embedder, abstain_threshold=1.01)
    a = Answerer(retriever, generator).answer("something unrelated")

    assert a.outcome == NO_PASSAGES
    assert not a
    assert generator.prompts == []


def test_the_model_may_abstain_when_retrieval_did_not(store, fake_embedder):
    """5d: the gap 4b's threshold structurally cannot see."""
    a = answerer_for(
        store, fake_embedder,
        generation_response(abstained=True, reason="the passages do not cover this"),
    ).answer("explain the three way handshake")

    assert a.outcome == MODEL_ABSTAINED
    assert a.reason == "the passages do not cover this"
    assert a.claims == ()


def test_an_unverifiable_answer_abstains_rather_than_shipping(store, fake_embedder, chunk_id):
    a = answerer_for(
        store, fake_embedder,
        generation_response(claims=[("sourdough needs a long autolyse", [chunk_id])]),
    ).answer("q")

    assert a.outcome == UNVERIFIED
    assert a.text == ""
    assert len(a.dropped) == 1


def test_a_fabricated_id_cannot_survive_into_an_answer(store, fake_embedder):
    a = answerer_for(
        store, fake_embedder,
        generation_response(claims=[(GROUNDED, ["deadbeefdeadbeef"])]),
    ).answer("q")

    assert a.outcome == UNVERIFIED
    assert "not in this query's context" in a.reason


def test_a_partly_verified_answer_keeps_what_passed_and_reports_what_did_not(
    store, fake_embedder, chunk_id
):
    a = answerer_for(
        store, fake_embedder,
        generation_response(
            answer="Two things.",
            claims=[(GROUNDED, [chunk_id]), ("sourdough needs a long autolyse", [chunk_id])],
        ),
    ).answer("q")

    assert a.outcome == ANSWERED
    assert [c.text for c in a.claims] == [GROUNDED]
    assert [c.text for c in a.dropped] == ["sourdough needs a long autolyse"]


def test_malformed_output_is_a_failure_not_an_answer_and_not_a_refusal(store, fake_embedder):
    """5b: never coerced into an answer, never reported as a refusal."""
    a = answerer_for(store, fake_embedder, "not json at all").answer("q")

    assert a.outcome == FAILED
    assert a.outcome != MODEL_ABSTAINED
    assert not a
    assert "not JSON" in a.reason


def test_a_response_missing_a_field_is_a_failure(store, fake_embedder):
    raw = json.dumps({"answer": "x", "abstained": False, "reason": ""})
    a = answerer_for(store, fake_embedder, raw).answer("q")
    assert a.outcome == FAILED
    assert "claims" in a.reason


def test_a_claim_with_no_ids_is_a_failure_of_shape_not_of_grounding(store, fake_embedder):
    raw = json.dumps(
        {"answer": "x", "claims": [{"text": "y"}], "abstained": False, "reason": ""}
    )
    a = answerer_for(store, fake_embedder, raw).answer("q")
    assert a.outcome == FAILED
    assert "chunk_ids" in a.reason


def test_a_generator_that_cannot_be_reached_is_a_failure(store, fake_embedder):
    class Unreachable:
        name = "unreachable"

        def complete(self, prompt, schema):
            raise GenerationError("could not reach Ollama at http://127.0.0.1:11434")

    retriever = Retriever(store, fake_embedder, abstain_threshold=0.0)
    a = Answerer(retriever, Unreachable()).answer("q")
    assert a.outcome == FAILED
    assert "Ollama" in a.reason


def test_the_minimum_claim_count_is_a_constructor_argument(store, fake_embedder, chunk_id):
    """4e's rule, applied to 5d's threshold: never a module constant."""
    response = generation_response(claims=[(GROUNDED, [chunk_id])])

    lenient = answerer_for(store, fake_embedder, response, min_verified_claims=1)
    assert lenient.answer("q").outcome == ANSWERED

    strict = answerer_for(store, fake_embedder, response, min_verified_claims=2)
    assert strict.answer("q").outcome == UNVERIFIED


def test_thresholds_are_instance_state_not_shared(store, fake_embedder):
    a = answerer_for(store, fake_embedder, generation_response(), min_verified_claims=1)
    b = answerer_for(store, fake_embedder, generation_response(), min_verified_claims=9)
    assert (a.min_verified_claims, b.min_verified_claims) == (1, 9)


def test_the_model_is_asked_with_this_querys_ids_in_its_schema(store, fake_embedder, chunk_id):
    generator = FakeGenerator([generation_response(claims=[(GROUNDED, [chunk_id])])])
    retriever = Retriever(store, fake_embedder, abstain_threshold=0.0)
    Answerer(retriever, generator).answer("why do routers drop packets")

    schema = generator.schemas[0]
    enum = schema["properties"]["claims"]["items"]["properties"]["chunk_ids"]["items"]
    assert chunk_id in enum["enum"]
    assert "why do routers drop packets" in generator.prompts[0]


def test_the_prose_is_composed_from_the_verified_claims(store, fake_embedder, chunk_id):
    """5b amended: what a reader sees is grounded by construction, not patched."""
    a = answerer_for(
        store, fake_embedder,
        generation_response(
            answer="Ignore me [id: deadbeef]. }",
            claims=[(GROUNDED, [chunk_id]), ("which is called queueing loss", [chunk_id])],
        ),
    ).answer("q")

    assert a.outcome == ANSWERED
    assert a.text == f"{GROUNDED} which is called queueing loss"
    assert "[id:" not in a.text
    assert "}" not in a.text


def test_the_models_own_prose_is_kept_as_an_unused_draft(store, fake_embedder, chunk_id):
    """Kept so 6 can compare the two without a second run."""
    a = answerer_for(
        store, fake_embedder,
        generation_response(answer="the model's wording", claims=[(GROUNDED, [chunk_id])]),
    ).answer("q")

    assert a.draft == "the model's wording"
    assert a.text != a.draft


def test_a_dropped_claim_never_reaches_the_prose(store, fake_embedder, chunk_id):
    """The whole point: unverified text cannot appear in what a reader sees."""
    a = answerer_for(
        store, fake_embedder,
        generation_response(
            claims=[(GROUNDED, [chunk_id]), ("sourdough needs a long autolyse", [chunk_id])],
        ),
    ).answer("q")

    assert a.text == GROUNDED
    assert "sourdough" not in a.text
    assert [c.text for c in a.dropped] == ["sourdough needs a long autolyse"]
