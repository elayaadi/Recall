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
uv sync --extra local                            # the local embedding model
uv run recall-index                              # chunks -> data/index/
uv run recall-search "why do routers drop packets"   # query the index by hand
uv run recall-search "..." --lexical              # the BM25 baseline (SPEC.md §4a)
uv run recall-answer "why do routers drop packets"   # retrieve, then answer with citations
uv run recall-answer "..." --show-prompt          # the assembled prompt, no model call
uv run python eval/harness.py                    # score the question set, write a run record
uv run python eval/calibrate.py                  # sweep theta against the question set
uv run python eval/compare.py A.json B.json      # diff two run records
uv run python scripts/profile_corpus.py data/raw > docs/corpus-profile.md
uv run pytest -q                                 # no corpus, no model, no network
uv run pytest -q -m slow                         # the tests that need the model
```

## Repo layout

```
src/recall/{ingestion,indexing,retrieval,generation,api}/  module code
eval/         evaluation harness; eval/questions/ holds the hand-written set
tests/        tests, mirroring the module layout
scripts/      one-off inspection tools (e.g. reading chunks by hand)
data/raw/     the working corpus — gitignored, never committed
data/index/   the built vector index — gitignored, rebuilt by recall-index
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
  `scripts/inspect_index.py` exists for the same reason on the index side.
- Tests use a fake embedder, so `uv run pytest -q` needs neither the model nor
  a network. The tests that load the real model are marked `slow` and
  deselected by default — run them with `-m slow` after touching `embed.py`.
- The index records the embedder that built it and refuses to be queried by a
  different one. After changing the embedder, rebuild rather than expecting the
  mismatch to surface as bad results.
- `recall-answer` needs a running Ollama (`ollama serve`) and the model pulled.
  Nothing else does — the local generator adds no Python dependency, and the
  tests use a fake generator, so `uv run pytest -q` needs neither.
- Generation has **three** ways of not answering and they are not the same
  thing: `no_passages` is §4b's retrieval threshold, `model_abstained` is the
  model's own judgement, `unverified` is §5c's check failing. `failed` is a
  fourth outcome and is not an abstention — it means the model's output could
  not be used. Never collapse them into a boolean; §6 scores them separately.
- Retrieval's two thresholds are constructor arguments, never constants. θ is
  now **calibrated** (0.62, module 6); the collapse threshold was swept and
  left at 0.95 deliberately — see §6. Both die at any embedder or corpus
  change, so recalibrate rather than assuming they carry over.
- Reported eval figures are **in-sample**: the thresholds were calibrated on
  the same 35 questions the scores come from. Every run record says so in its
  own `caveat` field. Do not quote a number without it.
- Before calling a low retrieval score a miss, check the term is in the corpus
  at all. Twice in module 4 an absent term was nearly recorded as a retrieval
  failure — `grep` the chunks first.
