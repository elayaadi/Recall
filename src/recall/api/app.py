"""Routes. SPEC.md 7b.

Two things this module is responsible for keeping true.

A **refusal is a successful response**: the request was understood and processed,
and the system's answer is that the corpus does not answer it. Only `failed` —
the model unreachable or its output unusable — is a 5xx, because that is a server
problem a client's retry logic should be able to see.

And a **collapsed hit keeps every citation**. §4d merges duplicates so one
passage carries every location it appears at; flattening that back to a single
location in the response would discard exactly what §4d exists to preserve.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..generation.models import ANSWERED, FAILED
from .deps import CORPUS_NOTICE, DEFAULT_INDEX, Services
from .models import (
    Answered,
    AnswerRequest,
    AnswerResponse,
    Claim,
    Health,
    Hit,
    Refused,
    SearchRequest,
    SearchResponse,
)

DESCRIPTION = """\
Retrieval-augmented question answering over a corpus of course material, with a
citation for every claim — or an explicit refusal.

Refusals are 200 responses carrying an `outcome` discriminator: `no_passages`
when retrieval found nothing above its threshold, `model_abstained` when the
model judged the passages insufficient, `unverified` when the grounding check
rejected the claims. Only an unusable generator is an error.
"""


def create_app(services: Services | None = None, index: Path = DEFAULT_INDEX) -> FastAPI:
    """Build the app. `services` is injected by the tests, which use fakes."""

    state: dict[str, Services] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 23 s of cold start, paid once at boot rather than per request.
        state["services"] = services if services is not None else Services.build(index)
        yield
        state.clear()

    app = FastAPI(
        title="Recall",
        description=DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
    )

    def svc() -> Services:
        return state["services"]

    @app.get("/health", response_model=Health)
    async def health() -> Health:
        s = svc()
        r = s.retriever
        return Health(
            status="ok",
            entries=len(s.store),
            embedder=s.store.embedder_name,
            retriever={
                "k": r.k,
                "abstain_threshold": r.abstain_threshold,
                "collapse_threshold": r.collapse_threshold,
            },
            generation_configured=bool(s.generator_name),
            corpus_notice=CORPUS_NOTICE,
        )

    @app.post("/search", response_model=SearchResponse)
    async def search(request: SearchRequest) -> SearchResponse:
        s = svc()
        retriever = s.retriever
        if request.k != retriever.k:
            from ..retrieval.retriever import Retriever

            retriever = Retriever(
                s.store, retriever._embedder, k=request.k,
                abstain_threshold=retriever.abstain_threshold,
                collapse_threshold=retriever.collapse_threshold,
            )
        result = await run_in_threadpool(
            retriever.retrieve, request.query,
            doc_type=request.doc_type, source_file=request.source_file,
        )
        return SearchResponse(
            query=result.query,
            abstained=result.abstained,
            reason=result.reason,
            collapsed=result.collapsed,
            hits=[
                Hit(
                    score=h.score,
                    chunk_id=h.chunk_id,
                    text=h.entry.chunk.raw_text,
                    citations=h.citations(),
                )
                for h in result.hits
            ],
        )

    @app.post("/answer", response_model=AnswerResponse)
    async def answer(request: AnswerRequest):
        s = svc()
        # Generation is minutes long and blocking (§5e). Off the event loop, so
        # a slow answer cannot stop /search from responding.
        result = await run_in_threadpool(s.answerer.answer, request.question)

        if result.outcome == FAILED:
            # Not a refusal. The model could not be used, which is a server
            # problem and should reach a client's retry logic as one.
            raise HTTPException(status_code=502, detail=result.reason)

        if result.outcome == ANSWERED:
            return Answered(
                outcome="answered",
                text=result.text,
                generator=result.generator,
                dropped=len(result.dropped),
                claims=[
                    Claim(text=c.text, citations=list(c.citations)) for c in result.claims
                ],
            )
        return Refused(
            outcome=result.outcome, reason=result.reason, generator=result.generator
        )

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the Recall API.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    if not (args.index / "index.json").exists():
        parser.error(f"no index at {args.index} — run: uv run recall-index")

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on install
        # The same shape as LocalEmbedder's message: name the extra rather than
        # letting an ImportError traceback be the whole explanation. §7a put the
        # web stack in an extra precisely so it can be absent.
        raise SystemExit(
            "recall-serve needs uvicorn. Install it with: uv sync --extra api"
        ) from exc

    uvicorn.run(create_app(index=args.index), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
