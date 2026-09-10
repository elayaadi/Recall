# Recall

A retrieval-augmented generation system that answers questions from a corpus of
course material — slide decks, problem sets, a syllabus — with a citation for
every claim, or an explicit refusal when the corpus does not answer.

The retrieval quality is measured, not asserted. Every number below comes from a
run you can reproduce from a clone.

```bash
uv sync --extra local                            # the embedding model
uv run python scripts/fetch_corpus.py            # 33 PDFs from MIT OpenCourseWare
uv run recall-ingest data/raw                    # -> data/chunks.jsonl
uv run recall-index                              # -> data/index/
uv run recall-search "how does Huffman coding assign codewords"
```

## What it does

```
$ uv run recall-search "how does Huffman coding assign codewords"

  0.757  problem set MIT6_02F12_ps1.pdf, pp.6–7, problem 4
  0.753  lecture MIT6_02F12_lec01.pdf, slide 18 — "Huffman's Coding Algorithm"

$ uv run recall-search "how does RSA public-key encryption work"

  ABSTAINED: best score 0.565 below threshold 0.620
```

The second case is the point as much as the first. `RSA` appears zero times in
this corpus, and a system that answers anyway is worse than one that says so.

## Measured results

35 hand-written questions, 26 answerable and 9 unanswerable, scored against the
649-chunk corpus. `uv run python eval/harness.py` reproduces this.

| | |
|---|---|
| recall@1 | 0.558 |
| **recall@5** | **0.923** |
| recall@20 | 0.923 |
| MAP | 0.728 |
| abstention precision / recall | 1.000 / 0.556 |

Per document type, reported beside the headline so a weak branch cannot hide
inside an average:

| format | questions | recall@5 | MAP |
|---|---|---|---|
| deck | 17 | 0.941 | 0.672 |
| problem sheet | 7 | 1.000 | 1.000 |
| syllabus | 2 | 0.500 | 0.250 |

**These figures are in-sample.** The four thresholds were calibrated on the same
35 questions the scores come from — a held-out split of a set this size leaves
too few points to calibrate against. Every run record in `eval/runs/` carries
that caveat in its own field.

## What the numbers say that is not flattering

**Abstention recall is 0.556.** Four of nine unanswerable questions get answered
anyway. This is not a tuning failure: the top-1 scores of answerable and
unanswerable questions *overlap*, with 4 of the 9 scoring at or above the lowest
answerable one, so no threshold separates them. An earlier eight-query probe had
found a clean gap and been explicit that eight queries were not a calibration.
They were not.

**recall@20 equals recall@5 exactly.** A relevant chunk is either in the top five
or not retrieved at all. That was written down in advance as the condition for
adopting a reranker — a gap between the two is the headroom a reranker recovers —
so the trigger did not fire, and the remaining errors are upstream in chunking or
embedding rather than in ranking.

**The syllabus row is one question right and one wrong**, over a document type
that is one file and five chunks. Two questions is not a measurement of it.

**No answer-level metrics.** Grounding rate and citation validity are decided,
implemented and unrun: generation on the local model is minutes per question on
CPU, hours across the set.

**Four comparisons the design promised were never run.** Structure-aware
chunking against a uniform-window baseline, the local embedder against a hosted
one, dense retrieval against BM25, and the grounding judge against hand-labelled
agreement. Each baseline exists in the repo — that is what made the promises
credible — but the eval harness varies the retrieval thresholds and nothing
else. A fifth, local against hosted generation, was closed by deciding not to
build the second backend at all.

So what is measured here is **retrieval quality on one configuration**: 
calibrated, with the abstention path scored and the reranker question settled by
a condition written down in advance. That is less than the design set out to
compare, and the difference is written down rather than absorbed.

## How it works

```
PDFs ──▶ ingest ──▶ chunks ──▶ index ──▶ retrieve ──▶ generate ──▶ answer
         parse      one per    embed     top-k,       claims       + citations
         classify   slide /    + dedup   collapse,    mapped to    or a refusal
         chunk      problem              abstain      chunks
```

- **Ingestion** picks a chunker per document type from measured structural
  signals, not filenames. A slide becomes a chunk; a problem keeps its parts.
- **Indexing** embeds with `bge-base-en-v1.5` into a numpy matrix — 626 entries
  is a 1.9 MB array and one matrix–vector product, so exact search is the whole
  algorithm.
- **Retrieval** returns passages or refuses, collapses near-duplicates and merges
  their citations, so one passage carries every location it appears at.
- **Generation** returns claims mapped to chunk ids, checks each claim against
  the passage it cites, and builds the answer text from the claims that pass — so
  what a reader sees is grounded by construction.
- **Evaluation** scores all of it against hand-written gold labels anchored to a
  location and a verbatim snippet, so re-chunking does not mean re-labelling.

`uv run recall-serve` puts `/search` and `/answer` over HTTP. A refusal is a 200
carrying which of the four outcomes it was; only an unusable generator is a 5xx.

## The corpus

MIT OpenCourseWare 6.02, *Introduction to EECS II: Digital Communication
Systems*, Fall 2012 — 23 lecture decks, 9 problem sets, a syllabus.
**CC BY-NC-SA 4.0**, not relicensed here. `data/CORPUS.md` records the source and
the one file that is a format conversion rather than a published artefact.

Development ran against private course notes that could not be published. They
were replaced before the question set was written, because gold labels are
hand-written and corpus-bound: free to swap before, expensive after.

## Reading the repo

- [docs/decisions.md](docs/decisions.md) — every architecture decision, and the
  ones that were reversed or corrected when evidence contradicted them
- [SPEC.md](SPEC.md) — the full reasoning per module, including rejected options
- [docs/corpus-profile.md](docs/corpus-profile.md) — the corpus, measured
- [CLAUDE.md](CLAUDE.md) — working conventions

## Known limitations

- Reported metrics are in-sample, as above, and cover retrieval on one
  configuration — see the four comparisons that were never run.
- Abstention misses four of nine unanswerable questions, and the score bands
  overlap, so no threshold fixes it on this embedder.
- Generation output varies between runs at temperature 0, so answer-level
  comparisons would need repeats to be meaningful.
- The grounding judge is a model scoring another model, and its agreement with a
  human is unmeasured.
- Five chunks still exceed the embedder's 512-token window, holding 0.7% of
  corpus tokens.
- No OCR, no multi-user auth, no UI beyond the CLI and the API.
- `scripts/fetch_corpus.py` scrapes a website and will break when that website
  changes. It fails loudly rather than fetching a partial corpus.

## How this was built

Written with agentic coding assistance (Claude Code), directed and reviewed by
me. Every architecture decision was made by comparing real alternatives before
choosing one, and the reasoning — including what was rejected and why — is in the
documents above rather than reconstructed afterwards. Every number reported
anywhere in this repo comes from an actual run; none are estimated or
illustrative.

Several of the defects those documents record were found by running the system
and reading its output rather than by the test suite, which was green at the
time. Those are written down too, in the same places as the decisions.

## Licence

MIT for the code — see [LICENSE](LICENSE). The corpus is CC BY-NC-SA 4.0 and is
not this project's to relicense; derived artefacts stay gitignored.
