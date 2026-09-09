"""SPEC.md 5c's deterministic check, and the two failures it exists to catch.

The check is asserted here on both sides: that it rejects a fabricated id and a
claim that does not overlap what it cites, and that it does *not* reject an
honest paraphrase — a check that fails everything would pass a test suite
written only around its failures.
"""

from __future__ import annotations

from conftest import make_chunk

from recall.indexing.store import Duplicate, IndexEntry
from recall.generation.models import Claim
from recall.generation.verify import (
    check_claim,
    expand_citations,
    shares_phrase,
    strip_passage_ids,
    verify,
)

PASSAGE = "Routers drop packets when the output queue is full, which is called queueing loss."


def context_of(*chunks) -> dict:
    return {c.chunk_id: IndexEntry(chunk=c) for c in chunks}


def test_a_verbatim_span_shares_a_phrase():
    assert shares_phrase("the output queue is full", PASSAGE)


def test_shared_vocabulary_alone_does_not_count():
    """Same words, no run of four — the case an overlap check has to reject."""
    assert not shares_phrase("queue routers packets loss full", PASSAGE)


def test_a_claim_shorter_than_the_ngram_falls_back_to_its_words():
    assert shares_phrase("queueing loss", PASSAGE)
    assert not shares_phrase("token bucket", PASSAGE)


def test_an_empty_claim_shares_nothing():
    assert not shares_phrase("", PASSAGE)


def test_a_grounded_claim_passes():
    chunk = make_chunk(text=PASSAGE)
    claim = Claim("Routers drop packets when the output queue is full", (chunk.chunk_id,))
    assert check_claim(claim, context_of(chunk)).ok


def test_a_fabricated_id_is_caught():
    chunk = make_chunk(text=PASSAGE)
    claim = Claim("Routers drop packets when the output queue is full", ("deadbeef",))
    check = check_claim(claim, context_of(chunk))
    assert not check.ok
    assert "not in this query's context" in check.reason


def test_citation_drift_is_caught():
    """A real id, attached to a claim that passage does not support."""
    chunk = make_chunk(text=PASSAGE)
    claim = Claim("DNS resolves a hostname by walking the delegation chain", (chunk.chunk_id,))
    check = check_claim(claim, context_of(chunk))
    assert not check.ok
    assert "shares no" in check.reason


def test_a_claim_citing_nothing_is_caught():
    check = check_claim(Claim("something", ()), {})
    assert not check.ok
    assert "cites no passage" in check.reason


def test_one_supporting_passage_among_several_is_enough():
    supported = make_chunk(text=PASSAGE, source_file="a.pdf")
    other = make_chunk(text="An unrelated passage about DNS.", source_file="b.pdf")
    claim = Claim(
        "the output queue is full",
        (other.chunk_id, supported.chunk_id),
    )
    assert check_claim(claim, context_of(supported, other)).ok


def test_the_ngram_length_is_an_argument_not_a_constant():
    """Long enough to have n-grams either way, so the length is what decides."""
    chunk = make_chunk(text=PASSAGE)
    claim = Claim("the output queue is the thing that fills up here", (chunk.chunk_id,))
    ctx = context_of(chunk)
    assert check_claim(claim, ctx, ngram=3).ok
    assert not check_claim(claim, ctx, ngram=8).ok


def test_citations_expand_to_every_location_the_passage_appears_at():
    """4d: the model cites a passage, the repo turns that into locations."""
    chunk = make_chunk(text=PASSAGE, source_file="lecture.pdf")
    entry = IndexEntry(
        chunk=chunk,
        duplicates=(Duplicate(source_file="week.pdf", locator=chunk.locator),),
    )
    claim = Claim("the output queue is full", (chunk.chunk_id,))

    expanded = expand_citations(claim, {chunk.chunk_id: entry})
    assert len(expanded.citations) == 2
    assert any(c.startswith("lecture.pdf") for c in expanded.citations)
    assert any(c.startswith("week.pdf") for c in expanded.citations)


def test_verify_keeps_the_passing_claims_and_reports_every_verdict():
    chunk = make_chunk(text=PASSAGE)
    good = Claim("the output queue is full", (chunk.chunk_id,))
    bad = Claim("sourdough needs a long autolyse", (chunk.chunk_id,))

    kept, checks = verify([good, bad], context_of(chunk))
    assert [c.text for c in kept] == [good.text]
    assert [c.ok for c in checks] == [True, False]


def test_a_kept_claim_comes_back_with_its_citations_filled_in():
    chunk = make_chunk(text=PASSAGE)
    kept, _ = verify([Claim("the output queue is full", (chunk.chunk_id,))], context_of(chunk))
    assert kept[0].citations == (chunk.citation(),)


def test_passage_ids_are_stripped_from_the_prose_a_reader_sees():
    """Found on the first real run: the model wrote ids the instruction forbids."""
    cleaned = strip_passage_ids(
        "Routers queue packets (id: 2bf65592e5adecb9). They then drop them.",
        ["2bf65592e5adecb9"],
    )
    assert cleaned == "Routers queue packets. They then drop them."


def test_a_bare_id_is_stripped_too():
    assert strip_passage_ids("as 2bf65592e5adecb9 says", ["2bf65592e5adecb9"]) == "as says"


def test_stripping_leaves_text_that_has_no_ids_alone():
    text = "Routers drop packets when the output queue is full."
    assert strip_passage_ids(text, ["2bf65592e5adecb9"]) == text


def test_stripping_never_removes_an_id_that_was_not_in_the_context():
    """It is cleanup of this query's labels, not a general scrub of hex strings."""
    text = "the digest deadbeefdeadbeef matters"
    assert strip_passage_ids(text, ["2bf65592e5adecb9"]) == text
