"""SPEC.md 5c's eval-time judge: what it counts, and what it refuses to count.

Two properties matter more than the score itself. A judge that errors has not
found a claim unsupported, so an error must not land in the numerator. And a
report must carry its caveat, because 5c records that the judge's own agreement
with a human is unmeasured and a bare rate would assert more than was measured.
"""

from __future__ import annotations

import json

import pytest
from conftest import FakeGenerator, make_chunk

from recall.generation.generate import GenerationError
from recall.generation.models import Claim
from recall.indexing.store import IndexEntry

from eval.grounding import CAVEAT, judge_claim, judge_claims

PASSAGE = "Routers drop packets when the output queue is full."


def verdict(supported: bool, reason: str = "") -> str:
    return json.dumps({"supported": supported, "reason": reason})


@pytest.fixture
def chunk():
    return make_chunk(text=PASSAGE)


@pytest.fixture
def context(chunk):
    return {chunk.chunk_id: IndexEntry(chunk=chunk)}


def test_a_supported_claim_is_recorded_as_supported(chunk, context):
    claim = Claim("routers drop packets", (chunk.chunk_id,))
    v = judge_claim(FakeGenerator([verdict(True, "stated directly")]), claim, context)
    assert v.supported
    assert v.reason == "stated directly"


def test_an_unsupported_claim_is_recorded_as_unsupported(chunk, context):
    claim = Claim("routers use a token bucket", (chunk.chunk_id,))
    assert not judge_claim(FakeGenerator([verdict(False, "not stated")]), claim, context).supported


def test_one_supporting_passage_is_enough(chunk, context):
    """A claim citing two passages asserts they jointly bear on it."""
    other = make_chunk(text="An unrelated passage.", source_file="b.pdf")
    context = context | {other.chunk_id: IndexEntry(chunk=other)}
    claim = Claim("routers drop packets", (other.chunk_id, chunk.chunk_id))

    generator = FakeGenerator([verdict(False), verdict(True)])
    assert judge_claim(generator, claim, context).supported


def test_a_claim_citing_nothing_in_the_context_is_unsupported_without_a_call(context):
    generator = FakeGenerator([verdict(True)])
    v = judge_claim(generator, Claim("x", ("deadbeef",)), context)
    assert not v.supported
    assert generator.prompts == []


def test_the_judges_own_malformed_output_raises_rather_than_scoring(chunk, context):
    claim = Claim("routers drop packets", (chunk.chunk_id,))
    with pytest.raises(GenerationError):
        judge_claim(FakeGenerator(["not json"]), claim, context)


def test_a_non_boolean_verdict_raises(chunk, context):
    claim = Claim("routers drop packets", (chunk.chunk_id,))
    raw = json.dumps({"supported": "yes", "reason": ""})
    with pytest.raises(GenerationError):
        judge_claim(FakeGenerator([raw]), claim, context)


def test_a_failed_judgement_is_an_error_not_a_failure(chunk, context):
    """A flaky judge must not look like an ungrounded system."""
    claims = [Claim("routers drop packets", (chunk.chunk_id,))]
    report = judge_claims(FakeGenerator(["not json"]), claims, context)

    assert report.judged == 0
    assert report.supported == 0
    assert report.rate is None
    assert len(report.errors) == 1


def test_the_rate_counts_only_what_was_judged(chunk, context):
    claims = [
        Claim("routers drop packets", (chunk.chunk_id,)),
        Claim("the output queue is full", (chunk.chunk_id,)),
    ]
    report = judge_claims(FakeGenerator([verdict(True), verdict(False)]), claims, context)

    assert (report.judged, report.supported) == (2, 1)
    assert report.rate == 0.5


def test_no_claims_gives_no_rate_rather_than_zero(context):
    """2c's rule: an empty measurement is not a score of 0."""
    report = judge_claims(FakeGenerator([verdict(True)]), [], context)
    assert report.judged == 0
    assert report.rate is None


def test_every_report_carries_the_caveat(chunk, context):
    claims = [Claim("routers drop packets", (chunk.chunk_id,))]
    report = judge_claims(FakeGenerator([verdict(True)]), claims, context)
    assert report.caveat == CAVEAT
    assert "unvalidated" in report.caveat
