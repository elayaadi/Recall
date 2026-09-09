"""The BM25 baseline. Kept so module 6 can measure §4a rather than assert it."""

from __future__ import annotations

from conftest import make_chunk

from recall.indexing.store import IndexEntry
from recall.ingestion.models import PROBLEM_SHEET
from recall.retrieval.lexical import BM25Index, tokenize


def entries(*texts: str) -> list[IndexEntry]:
    return [IndexEntry(chunk=make_chunk(text=t, source_file=f"{i}.pdf"))
            for i, t in enumerate(texts)]


def test_identifiers_stay_one_token():
    # rdt_send is a single searchable thing, not "rdt" beside "send".
    assert tokenize("call rdt_send(data) now") == ["call", "rdt_send", "data", "now"]


def test_tokenizing_lowercases_and_drops_punctuation():
    assert tokenize("HTTP/1.1: keep-alive!") == ["http", "1", "1", "keep", "alive"]


def test_the_document_containing_the_term_ranks_first():
    index = BM25Index(entries(
        "the sender calls rdt_send to pass data down",
        "a web cache serves repeated requests locally",
        "routers hold packets in an output queue",
    ))
    assert index.search("rdt_send", k=3)[0].text.startswith("the sender calls")


def test_a_term_in_no_document_returns_nothing():
    index = BM25Index(entries("routers queue packets", "a web cache"))
    assert index.search("sourdough", k=5) == []


def test_an_empty_query_returns_nothing():
    assert BM25Index(entries("anything at all")).search("", k=5) == []


def test_an_empty_index_returns_nothing():
    assert BM25Index([]).search("anything", k=5) == []


def test_rarer_terms_outrank_common_ones():
    index = BM25Index(entries(
        "the network the network the network hot potato routing",
        "the network the network the network the network the network",
    ))
    hits = index.search("hot potato", k=2)
    assert len(hits) == 1
    assert "hot potato" in hits[0].text


def test_results_come_back_in_descending_score_order():
    index = BM25Index(entries(
        "congestion congestion congestion window",
        "congestion window",
        "an unrelated passage",
    ))
    scores = [h.score for h in index.search("congestion", k=3)]
    assert scores == sorted(scores, reverse=True)


def test_filters_narrow_the_candidates():
    index = BM25Index([
        IndexEntry(chunk=make_chunk(text="compute the delay", doc_type=PROBLEM_SHEET,
                                    source_file="homework 1.pdf")),
        IndexEntry(chunk=make_chunk(text="the delay of a link", source_file="deck.pdf")),
    ])
    assert len(index.search("delay", k=5)) == 2
    assert len(index.search("delay", k=5, doc_type=PROBLEM_SHEET)) == 1
    assert len(index.search("delay", k=5, source_file="deck.pdf")) == 1


def test_k_bounds_the_result_list():
    index = BM25Index(entries(*[f"queue packets {i}" for i in range(6)]))
    assert len(index.search("queue", k=3)) == 3
