# Decision record

Recall's architecture is settled one decision at a time. Each is chosen by
comparing two or three realistic options on implementation effort, cost in
money and latency, and how well the choice holds up under scrutiny — never by
adopting the popular or obvious option by default.

This file is the index. The full reasoning for each entry, including the
options rejected and why, is in the linked [SPEC.md](../SPEC.md) section.

## Ingestion — module 2

- **2026-09-08 — The corpus was profiled before the chunker was designed.**
  Module 2 is built on measurements of the real documents rather than
  assumptions about documents in general — see
  [corpus-profile.md](corpus-profile.md).

- **2026-09-08 — PDF parsing: `pdfplumber`** (MIT). Span-level font data is
  used for exactly one job — detecting the slide title — not for heading
  recovery. `pypdf` was ruled out by measurement rather than taste: the
  font-based and plain-text title heuristics agree on only 44% of 566 slides,
  and the disagreements are systematic. PyMuPDF matches pdfplumber's capability
  here and is ~10× faster, which is irrelevant at 578 pages, and is AGPL, which
  is not — §2a.

- **2026-09-08 — Markdown parsing: `markdown-it-py` AST**, not a regex heading
  splitter, which breaks on `#` lines inside fenced code blocks — §2a.

- **2026-09-08 — PPTX parsing: `python-pptx`** — §2a.

- **2026-09-08 — Chunking: structure-aware per format**, with the heading or
  title path prepended to the chunk text so a bare bullet carries its own
  topic. Uniform token windowing is kept in the repo as a committed baseline,
  so module 6 can *measure* the difference between the two rather than assert
  it — §2b.

- **2026-09-08 — Deck chunking: one slide per chunk, merging consecutive
  same-title runs.** Adjacency is load-bearing — the same title recurring
  non-adjacently stays separate, because merging across intervening material
  would leave the chunk with no honest citation. Titles are normalised for
  `(cont.)` variants when comparing only — §2b.

- **2026-09-08 — Markdown and PPTX chunkers deferred** until real files of
  those types exist. The chunk schema and the ingest interface stay
  format-agnostic, so adding them later is additive rather than a rewrite.

- **2026-09-08 — Eval gold labels anchor to a location plus a verbatim
  snippet, not to chunk ids**, so labels survive re-chunking and retrieval
  tuning does not mean re-labelling. A label matching zero chunks is a hard
  error that fails the run, never a silent score of 0 — §2c.

## Publication — module 8

- **2026-09-09 — Corpus: build on the private notes, publish on MIT
  OpenCourseWare.** Development runs against real course material that is
  gitignored and never committed. Before the module 6 question set is written,
  it is replaced with openly licensed material of the same shape — slide decks,
  problem sheets, a syllabus — so that published retrieval metrics are
  reproducible by a reader instead of asserted. The timing is the decision:
  gold labels are hand-written and corpus-bound, so the swap is free before
  module 6 and expensive after it — §8a.

- **2026-09-09 — Licence: MIT for the code.** Permissive, one file, and it
  forecloses nothing downstream — the same reasoning that ruled out an AGPL
  dependency in §2a, applied to what this project imposes on anyone reusing it.
  Recorded in `LICENSE` and as `license = "MIT"` in `pyproject.toml`, so the
  built wheel carries `License-Expression: MIT`.

  The corpus is licensed separately and is not the project's to relicense: MIT
  OpenCourseWare material is CC BY-NC-SA. When it lands it carries its own
  attribution and licence note under `data/`, and derived artefacts such as
  `data/chunks.jsonl` stay gitignored — a chunked derivative would inherit the
  share-alike term.

## Reversals and corrections

Kept visible rather than edited away, because the reasoning is the point.

- **The PDF parser decision was reversed on its own evidence.** It originally
  justified a font-aware library by font-size *clustering* to reconstruct
  heading levels. Profiling killed that rationale outright — no document in the
  corpus has a multi-level heading hierarchy, so the clustering would have been
  machinery built for a document type that is not present. The library survived
  for a different and far simpler reason, and §2a says so plainly rather than
  presenting the outcome as the original plan.

- **A reported metric was wrong and was corrected in public.** The corpus
  profile first said 14 pages had no text layer, from a diagnostic that treated
  any page under 20 characters as empty. The commit *Record ingestion results
  and correct the text-less page count* fixed both the figure and the
  diagnostic's description of what those pages actually are.

- **Reading the output found what the tests did not.** Inspecting real chunks
  surfaced a content-loss bug: on slides where every span shares one font size,
  the largest-span heuristic moved the whole slide into the title field and
  dropped it from the body text that eval snippets match against. Fixed in
  *Fix three chunk-quality defects found by reading the chunks* and *Fix
  content loss on slides that have no distinct title*, with the measured
  before-and-after recorded in §2 rather than the fix landing quietly.
