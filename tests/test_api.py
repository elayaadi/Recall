"""The HTTP surface, against the fakes the rest of the suite already uses.

SPEC.md 7 is the first module with no eval behind it: module 6 measures
retrieval and generation, and nothing measures serialisation. A bug that dropped
citations on the way out would pass every other test in this repo, so the
property most worth asserting here is that a collapsed hit's locations survive
the round trip.
"""

from __future__ import annotations

import pytest
from conftest import FakeGenerator, generation_response, make_chunk
from fastapi.testclient import TestClient

from recall.api.app import create_app
from recall.api.deps import Services
from recall.generation.answerer import Answerer
from recall.indexing.build import build_index
from recall.retrieval.retriever import Retriever

PASSAGE = "Routers drop packets when the output queue is full, which is called queueing loss."
GROUNDED = "Routers drop packets when the output queue is full"


def services(fake_embedder, responses=None, *, threshold=0.0, chunks=None):
    chunks = chunks or [
        make_chunk(text=PASSAGE, pages=(1,)),
        make_chunk(text="TCP halves its congestion window on loss", pages=(2,)),
    ]
    store = build_index(chunks, fake_embedder)
    retriever = Retriever(store, fake_embedder, k=5, abstain_threshold=threshold)
    generator = FakeGenerator(list(responses or [generation_response()]))
    return Services(
        store=store,
        retriever=retriever,
        answerer=Answerer(retriever, generator),
        generator_name=generator.name,
    )


def client(svc) -> TestClient:
    return TestClient(create_app(services=svc))


@pytest.fixture
def chunk_id(fake_embedder):
    store = build_index([make_chunk(text=PASSAGE, pages=(1,))], fake_embedder)
    return next(iter(store.entries)).chunk_id


class TestHealth:
    def test_health_reports_the_live_configuration(self, fake_embedder):
        with client(services(fake_embedder)) as c:
            body = c.get("/health").json()
        assert body["status"] == "ok"
        assert body["entries"] == 2
        assert body["retriever"]["abstain_threshold"] == 0.0

    def test_health_carries_the_corpus_licence_notice(self, fake_embedder):
        """§7c serves locally, but attribution still travels with the corpus."""
        with client(services(fake_embedder)) as c:
            assert "CC BY-NC-SA" in c.get("/health").json()["corpus_notice"]


class TestSearch:
    def test_a_query_returns_hits_with_citations(self, fake_embedder):
        with client(services(fake_embedder)) as c:
            body = c.post("/search", json={"query": PASSAGE}).json()
        assert body["abstained"] is False
        assert body["hits"][0]["citations"]

    def test_a_collapsed_hit_keeps_every_location(self, fake_embedder):
        """§4d's merged citations must survive serialisation.

        The bug this guards against loses a location silently: the response is
        well-formed, the answer is right, and one of the two places the passage
        appears has quietly gone.
        """
        body = "a CDN redirects the client to a nearby replica"
        chunks = [
            make_chunk(text=f"A\n\n{body}", raw_text=body, source_file="lecture.pdf"),
            make_chunk(text=f"A\n\n{body}", raw_text=body, source_file="week.pdf"),
        ]
        with client(services(fake_embedder, chunks=chunks)) as c:
            hits = c.post("/search", json={"query": f"A\n\n{body}"}).json()["hits"]
        assert len(hits[0]["citations"]) == 2

    def test_retrieval_abstention_is_a_200_not_an_error(self, fake_embedder):
        with client(services(fake_embedder, threshold=1.01)) as c:
            response = c.post("/search", json={"query": "anything at all"})
        assert response.status_code == 200
        assert response.json()["abstained"] is True
        assert response.json()["reason"]

    def test_an_empty_query_is_rejected_by_validation(self, fake_embedder):
        with client(services(fake_embedder)) as c:
            assert c.post("/search", json={"query": ""}).status_code == 422

    def test_k_is_bounded(self, fake_embedder):
        with client(services(fake_embedder)) as c:
            assert c.post("/search", json={"query": "x", "k": 0}).status_code == 422
            assert c.post("/search", json={"query": "x", "k": 999}).status_code == 422


class TestAnswer:
    def test_a_grounded_answer_carries_its_claims_and_citations(self, fake_embedder, chunk_id):
        svc = services(
            fake_embedder,
            [generation_response(answer="They queue.", claims=[(GROUNDED, [chunk_id])])],
        )
        with client(svc) as c:
            body = c.post("/answer", json={"question": "why do routers drop packets"}).json()
        assert body["outcome"] == "answered"
        assert body["claims"][0]["citations"]
        assert body["generator"] == "fake-generator"

    @pytest.mark.parametrize(
        "responses, threshold, outcome",
        [
            ([generation_response()], 1.01, "no_passages"),
            ([generation_response(abstained=True, reason="not covered")], 0.0, "model_abstained"),
            ([generation_response(claims=[("sourdough needs a long autolyse", ["nope"])])],
             0.0, "unverified"),
        ],
    )
    def test_every_refusal_is_a_200_with_its_own_discriminator(
        self, fake_embedder, responses, threshold, outcome
    ):
        """§7b: a refusal is a successful response, and the three stay distinct.

        CLAUDE.md forbids collapsing them, and a client needs the distinction as
        much as module 6 does.
        """
        with client(services(fake_embedder, responses, threshold=threshold)) as c:
            response = c.post("/answer", json={"question": "a question"})
        assert response.status_code == 200
        assert response.json()["outcome"] == outcome
        assert response.json()["reason"]

    def test_an_unusable_generator_is_a_502_not_a_refusal(self, fake_embedder):
        """`failed` is a server problem, and a client's retries should see it."""
        with client(services(fake_embedder, ["not json at all"])) as c:
            response = c.post("/answer", json={"question": "a question"})
        assert response.status_code == 502
        assert "not JSON" in response.json()["detail"]

    def test_dropped_claims_are_reported_not_hidden(self, fake_embedder, chunk_id):
        svc = services(
            fake_embedder,
            [generation_response(claims=[(GROUNDED, [chunk_id]),
                                         ("sourdough needs a long autolyse", [chunk_id])])],
        )
        with client(svc) as c:
            body = c.post("/answer", json={"question": "q"}).json()
        assert body["dropped"] == 1
        assert len(body["claims"]) == 1


def test_there_is_no_ingest_endpoint(fake_embedder):
    """§7b narrowed §7 deliberately: ingestion stays a CLI, and that is recorded."""
    with client(services(fake_embedder)) as c:
        assert c.post("/ingest", json={}).status_code == 404
