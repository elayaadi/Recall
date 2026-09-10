"""Label resolution, and the one behaviour SPEC.md 2c makes non-negotiable.

A label matching zero chunks is a hard error. If it were scored 0 instead, a
stale label would be indistinguishable from a retrieval regression — and telling
those apart is the reason the harness exists.
"""

from __future__ import annotations

import textwrap

import pytest

from eval.labels import (
    Label,
    Question,
    UnresolvedLabel,
    load_questions,
    normalise,
    relevant_ids,
    resolve,
)

CHUNKS = [
    {"chunk_id": "a1", "source_file": "deck.pdf",
     "raw_text": "Routers drop packets when\nthe output queue is full."},
    {"chunk_id": "a2", "source_file": "deck.pdf",
     "raw_text": "THE OUTPUT QUEUE IS FULL in another slide too."},
    {"chunk_id": "b1", "source_file": "other.pdf",
     "raw_text": "the output queue is full, but in a different file."},
]


def label(snippet, file="deck.pdf"):
    return Label(file=file, where="slide 1", snippet=snippet)


def test_a_snippet_resolves_to_the_chunk_containing_it():
    assert resolve(label("the output queue is full"), CHUNKS) == ["a1", "a2"]


def test_matching_ignores_whitespace_and_case():
    """A snippet copied from a PDF carries the extractor's line breaks."""
    assert resolve(label("packets when the output   QUEUE"), CHUNKS) == ["a1"]


def test_every_matching_chunk_counts_as_relevant():
    """2c: multiple matching chunks all count. 6a's metrics are chosen for it."""
    assert len(resolve(label("the output queue is full"), CHUNKS)) == 2


def test_a_label_is_scoped_to_its_source_file():
    assert "b1" not in resolve(label("the output queue is full"), CHUNKS)


def test_a_label_matching_nothing_raises_rather_than_scoring_zero():
    with pytest.raises(UnresolvedLabel) as exc:
        resolve(label("a passage that is simply not there"), CHUNKS)
    assert "no chunk in deck.pdf" in str(exc.value)


def test_a_label_naming_a_missing_file_raises():
    with pytest.raises(UnresolvedLabel):
        resolve(label("the output queue is full", file="gone.pdf"), CHUNKS)


def test_relevant_ids_unions_every_label_of_a_multi_hop_question():
    q = Question(id="m", text="?", kind="multi-hop",
                 labels=(label("Routers drop packets"), label("in another slide")))
    assert relevant_ids(q, CHUNKS) == {"a1", "a2"}


def test_an_answerable_question_without_a_label_is_rejected(tmp_path):
    path = tmp_path / "q.toml"
    path.write_text(textwrap.dedent("""
        [[question]]
        id = "x"
        kind = "factual"
        text = "unlabelled"
    """))
    with pytest.raises(UnresolvedLabel, match="carries no label"):
        load_questions(path)


def test_an_unanswerable_question_with_a_label_is_rejected(tmp_path):
    path = tmp_path / "q.toml"
    path.write_text(textwrap.dedent("""
        [[question]]
        id = "x"
        kind = "unanswerable"
        text = "labelled but unanswerable"
        [[question.labels]]
        file = "deck.pdf"
        where = "slide 1"
        snippet = "anything"
    """))
    with pytest.raises(UnresolvedLabel, match="carries a label"):
        load_questions(path)


def test_normalise_collapses_runs_of_whitespace():
    assert normalise("  a \n b\tc ") == "a b c"


class TestTheRealQuestionSet:
    """The shipped set, checked against the shipped corpus.

    Marked slow because it needs data/chunks.jsonl, which a fresh clone has to
    build first — the rest of this file runs on hand-written chunks.
    """

    @pytest.mark.slow
    def test_every_label_resolves(self):
        from eval.labels import load_chunks

        chunks = load_chunks()
        for q in load_questions():
            if q.answerable:
                assert relevant_ids(q, chunks), q.id

    def test_the_set_is_composed_as_6b_decided(self):
        qs = load_questions()
        unanswerable = [q for q in qs if not q.answerable]
        assert len(qs) == 35
        # 6b: about a quarter unanswerable.
        assert 0.2 <= len(unanswerable) / len(qs) <= 0.33
        assert all(q.note for q in unanswerable), "each records why it is absent"

    def test_question_ids_are_unique(self):
        ids = [q.id for q in load_questions()]
        assert len(ids) == len(set(ids))
