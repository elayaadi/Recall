# Recall — working conventions

Recall answers questions from a personal collection of study notes and course
material (markdown, PDF, PowerPoint) with retrieval-augmented generation,
citing the passage each answer came from.

This file holds the conventions a linter cannot enforce. Architecture decisions
live in [docs/decisions.md](docs/decisions.md); the reasoning behind each one,
including the rejected alternatives, is in [SPEC.md](SPEC.md).

## Self-contained

Recall shares no code, configuration, or infrastructure with any other
repository. Nothing is imported, vendored, or linked in from elsewhere.

## Nothing is adopted by default

Every item marked `decision pending` in SPEC.md is settled by first laying out
two or three realistic options with honest trade-offs — implementation effort,
cost in money and latency, and how well the choice survives scrutiny. No
library, model, framework, or storage engine is adopted because it is popular
or because it is the obvious choice. The maintainer picks; implementation of
that part does not begin beforehand.

When a decision is settled it gets one line in `docs/decisions.md` and its full
reasoning in the matching SPEC.md section. Settled decisions are not
re-litigated. If new evidence contradicts one, say so explicitly and propose
the change — never revise the record quietly to match the outcome.

## How work proceeds

- **One module at a time**, in SPEC.md order. The next module is not started
  early because the current one finished ahead of schedule.
- **Approach before code.** Within a module, the implementation approach is
  proposed and the open questions asked before anything is written, even when
  that module's architecture decision is already settled.
- **Tests per module**, passing, before the module is called done.
- **One meaningful commit per verified module** — never a single large commit
  at the end. Commit messages say what changed and why.
- **Real numbers only.** Every metric comes from an actual run. Nothing is
  estimated, illustrated, or left as a placeholder.
- **Report honestly.** Failing tests, skipped steps, and known gaps are stated
  plainly, in the repo as much as in conversation.

## Scope, v1

In scope, in order: ingestion → indexing → retrieval → generation → evaluation
→ API → docs.

Out of scope: OCR for scanned documents, any UI beyond a minimal demo,
multi-user auth, fine-tuning any model.

## Commands

```bash
uv run recall-ingest data/raw                    # PDFs -> data/chunks.jsonl
uv run recall-ingest data/raw --chunker window   # the measured baseline chunker
uv run pytest -q                                 # no corpus needed
```

## Repo layout

```
src/recall/{ingestion,indexing,retrieval,generation,api}/  module code
eval/         evaluation harness; eval/questions/ holds the hand-written set
tests/        tests, mirroring the module layout
scripts/      one-off inspection tools (e.g. reading chunks by hand)
data/raw/     the working corpus — gitignored, never committed
data/sample/  small committed fixtures for tests
docs/         decision record, corpus profile, architecture notes
```

## Gotchas

- `data/raw/` holds real course material and is gitignored. It is never
  committed; what ships with the public repo is decided in SPEC.md §8a.
- Tests build their own synthetic PDFs (`tests/fixtures/make_pdfs.py`) and
  never read `data/raw/`, so they pass on a fresh clone with no corpus present.
- The ingestion figures quoted in SPEC.md §2 come from the ingest command
  above. Regenerate them after any chunker change rather than editing them by
  hand — a stale number here is indistinguishable from a fabricated one.
- Chunk quality is not fully covered by the tests. Defects have been found by
  reading `data/chunks.jsonl` directly that the suite passed straight over.
