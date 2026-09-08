# Recall — specification

A retrieval-augmented generation system that answers questions from personal
study notes and course materials, with citations back to the source, and a
hand-built evaluation harness that proves retrieval quality with real numbers.

**Status:** module 2 (ingestion) fully decided, implementation not started.
Modules 3–8 are `decision pending`.

Each section is filled in as we settle it: the options considered, the choice,
and the reasoning. This file is the answer to "why this and not X?" — it should
let a technical reviewer follow the architecture without me present.

---

## 0. Goals and non-goals

**Goal.** Given a natural-language question, find the most relevant passages
from my own notes and produce a grounded answer that cites them — or say it
does not know, rather than inventing an answer.

**Success criteria for v1**

- Ingests markdown, PDF, and PPTX into one chunk format with usable metadata.
  (PDF first; markdown and PPTX chunkers land when files of those types exist.)
- Retrieval quality measured on a hand-written question set with standard
  metrics, recorded before and after any tuning.
- Abstains rather than answering when retrieval finds nothing relevant.
- Every answer carries citations resolvable to a source file and location.
- A reviewer can clone it, read the README, and understand each decision.

**Non-goals for v1.** OCR for scanned documents. A real UI beyond a minimal
demo. Multi-user auth. Fine-tuning any model.

**Language/runtime.** Not formally decided, but the decision list below
(Ollama, LangChain/LlamaIndex, PDF and PPTX parsing, Python web frameworks)
assumes Python. Flag it now if you want otherwise.

---

## 1. Repo setup — **done**

Module folders, `SPEC.md`, `CLAUDE.md`, git, GitHub remote, initial commit.

---

## 2. Ingestion — **decided; implementation pending**

Parse markdown, PDF, and PowerPoint into a common chunked format carrying
source file, section/heading, and page or slide number.

**Corpus.** Measured, not assumed — see [docs/corpus-profile.md](docs/corpus-profile.md).
29 PDFs from one course: 22 slide decks, 6 problem sheets, 1 syllabus; 578
pages, ~43k words, English. **No scans**, so OCR being out of scope costs
nothing. 25 of 578 pages produce no chunk — a few with no text layer, the rest
title-only divider slides over a diagram — and every one is reported by page
number at ingest rather than indexed as a chunk that matches a query and then
answers nothing.

### 2a. Parsing libraries — decided

- **Markdown: `markdown-it-py`** (AST). Rejected a regex heading-splitter: it
  breaks on `#` lines inside fenced code blocks, which these notes contain.
- **PPTX: `python-pptx`.** Effectively the only maintained reader; the real
  work is in what we extract (title placeholder vs. body, speaker notes,
  tables, reading order), not in the library choice.
- **PDF: `pdfplumber`** — for span-level font sizes, not for heading recovery.

  *This reverses an earlier rationale.* The first version of this decision
  justified a font-aware parser by font-size clustering to reconstruct heading
  levels. Profiling killed that: no document in the corpus has a multi-level
  heading hierarchy, so the clustering would have been built for a document
  type we do not have.

  Font data is still required, for one much simpler job — the slide title is
  the largest-font span on the page. Measured against the plain-text
  alternative ("first line after boilerplate"), the two agree on only **44%**
  of 566 slides, and the disagreements are systematic: in PDF reading order the
  page number often comes first, so a plain-text parser titles slides "1", "2",
  "3". That rules out `pypdf` on evidence rather than taste.

  Chosen pdfplumber over PyMuPDF: same capability for this job, MIT rather than
  AGPL. PyMuPDF is ~10× faster, but 578 pages makes speed irrelevant, and AGPL
  is a licence some employers' legal teams flag on sight — a poor thing to
  carry in a repo whose purpose is being read by employers.

  Rejected: ML layout models (`docling`, `marker`) — best fidelity, but heavy
  dependencies, and they make the pipeline someone else's model rather than a
  hand-built one.

### 2b. Chunking — decided: structure-aware, with uniform windowing kept as a measured baseline

Two chunkers are built and both stay in the repo.

**Primary — structure-aware per format.** The author already segmented the
document; headings, pages, and slides are human-authored topic boundaries, and
uniform windowing discards that information then approximates it with
arithmetic. A size guard sits on top of the native units, since they are not
uniformly sized: oversized units split at paragraph breaks, undersized units
merge with siblings under the same parent.

- *Markdown:* split at heading boundaries.
- *PDF — decks:* one slide (page) per chunk, merged across same-title runs; see
  "Slide grouping" below.
- *PDF — problem sheets:* one chunk per numbered problem, sub-parts kept with
  their parent. Items are `1.`–`8.` at line start with `a)`–`d)` sub-parts;
  numbering is validated as sequential, which separates real problem numbers
  from incidental digits in prose ("3 MB"). Verified across all 6 files.
- *PDF — syllabus:* split on ALL-CAPS section headings (11 across 3 pages).
  Content is heavily tabular and flattens to a readable but row-ambiguous
  stream; accepted for v1 and recorded as a known limitation.
- *PPTX:* one slide = one chunk, carrying slide title, deck section header, and
  speaker notes. Deferred until there are real .pptx files to test against.

**Slide grouping (decks).** Consecutive slides sharing a title are merged into
one chunk; a title change closes the chunk. Adjacency is load-bearing — the same
title recurring non-adjacently (20 cases in the corpus, e.g. "Web caching" at
slides 21–22 and again at 24–27) stays separate, because merging across
intervening material would leave the chunk with no honest citation.

Titles are normalised before comparison only — trailing `(cont.)` / `(cont)` /
`(continued)` stripped, whitespace collapsed, case-insensitive — while the
chunk keeps the run's original first title for display and citation. The author
marked continuation explicitly in 11 titles; honouring the title as a topic
boundary while ignoring the author's own "still the same topic" marker would be
inconsistent rather than conservative. Measured effect is small and reported as
such: 480 chunks strict, 472 normalised. Merged runs are size-capped as a guard
(longest actual run is 9 slides, ~600–800 words).

Rejected: merging by token count instead of title (reintroduces the tuned
window the title boundary exists to avoid).

**Boilerplate.** Lines repeating on >50% of a document's pages are stripped
before chunking — every deck carries a copyright line on nearly every page that
would otherwise land in every chunk and every embedding. Two further cases that
repeated-line detection cannot catch, because they differ per page: `Page 1 of
2` footers, and the bare slide number decks print on each slide. The slide
number is dropped only when it equals that page's own index, so a numeric line
that is real content is never mistaken for one.

**Empty-body chunks are dropped, not indexed.** A divider slide carrying only a
title over a diagram yields a chunk that can match a query and then answer
nothing. Those are reported as uncovered pages instead.

The heading path is **prepended to the chunk text**, not merely stored as
metadata. A bare slide bullet ("Requires O(n log n) time") is close to
unretrievable on its own — neither "merge" nor "sort" appears in it — and
unusable by the generator, which cannot resolve "it". Prefixed with
`Algorithms > Sorting > Merge Sort`, the chunk carries its own topic.

**Baseline — uniform token windows with overlap**, one code path across all
three formats. Kept deliberately, not as legacy: run against the same eval set
in module 6, it turns "structure-aware chunking suits slide decks better" from
a plausible claim into a measured delta, and shows where the gain is
concentrated by format. Cheap to build once the chunk schema exists. If it wins
on some format, that gets reported.

Rejected: **semantic chunking** (embed sentences, cut at similarity troughs) —
costs a full embedding pass per ingest, boundaries shift with the embedding
model so it is non-deterministic and awkward to unit-test, and on documents
that already have headings and slides it largely rediscovers boundaries
available for free. Rejected for v1: **parent–child retrieval** (retrieve small,
feed the parent section) — attacks the size tension directly rather than
compromising, but doubles storage and decouples the retrieval unit from the
context unit, complicating the eval harness. Reasonable v2 experiment once
there are baseline numbers.

### Measured result

`uv run recall-ingest data/raw` over the 29-file corpus:

| | |
|---|---|
| chunks (structural) | 499 |
| words | 38,368 |
| mean / median words per chunk | 77 / 66 |
| shortest / longest chunk | 5 / 742 words |
| multi-slide merged chunks | 53 |
| pages producing no chunk | 25, each reported by page number |

All 29 files were routed to the right chunker by structural signal alone, with
no filename fallback. Problem-sheet chunk counts match the numbering found
independently during profiling (6, 8, 5, 3, 7, 4).

**Known limitations, recorded rather than hidden.** Roman-numeral sub-parts
(`i.`, `ii.`) inside a problem are not captured in `parts` metadata; only
`a)`–`h)` are. Syllabus tables flatten to a row-ambiguous stream. A same-title
run merged across a text-less page cites non-contiguous pages ("slides 2, 4"),
which is correct but unusual to read.

### 2c. Chunk schema and citation anchoring — decided: location + snippet

**Chunk schema.** Every chunk carries: the source file and its content hash;
`doc_type` (`deck` / `problem_sheet` / `syllabus` / later `markdown`, `pptx`);
a format-specific `locator`; the chunk text with its title prefix, plus the raw
text without it; a token count; and `chunker` (`structural` or `window`) so the
primary and baseline chunkers can coexist in one store and be compared in
module 6.

Locators are structured, not stringly-typed, so citations render per format:

```
deck          {pages: [24,25,26,27], title: "Web caching"}
problem_sheet {page: 1, problem: "4", parts: ["a","b"]}
syllabus      {page: 2, section: "ASSESSMENT METHODS, WEIGHTS AND RULES"}
```

`chunk_id` is a deterministic hash of source + locator + text, used for
citations and index keys at runtime.

**Gold labels do not reference `chunk_id`.** They anchor to a location plus a
verbatim snippet:

```
cs447 Lecture 5.pdf, slide 6, "waiting in the router's queue"
```

and are resolved to whatever chunk contains that snippet at eval time.

Rejected: **labelling by `chunk_id`** — simplest schema, but every change to
chunk size or chunker invalidates all ~35 labels, so tuning would mean
re-labelling and the before/after comparison in §6 could never actually be run.
Rejected: **content-hash ids** — stable under reordering, still broken by any
chunking change; it delays the problem rather than solving it.

**Resolution rules.** Snippet matching is whitespace- and case-normalised.
Multiple matching chunks all count as relevant. A label matching **zero** chunks
is a hard error that fails the eval run — never a silent score of 0, which would
make a stale label look like a quality regression.

---

## 3. Indexing — **decision pending**

Turn chunks into a searchable index.

Open decisions:

- **3a. Embedding model** — local (e.g. via Ollama) vs. hosted API; which
  specific model; dimensionality and cost implications.
- **3b. Vector storage** — in-memory index (e.g. numpy/FAISS) vs. a real vector
  database; what persistence and incremental re-indexing need to look like.
- **3c. Hand-built pipeline vs. framework** (LangChain / LlamaIndex). This
  decision spans modules 2–5 and should be made once, deliberately.

Options and reasoning: _to be filled in._

---

## 4. Retrieval — **decision pending**

Given a query, return the most relevant chunks — or nothing.

Open decisions:

- **4a. Dense-only vs. hybrid** (dense + keyword/BM25), and if hybrid, how
  scores are combined.
- **4b. Abstention.** How the system decides it has *not* found an answer:
  score threshold, margin, a reranker, or an LLM check. Calibrated against the
  eval set, not guessed.
- **4c. Reranking** — whether a second-stage reranker earns its cost.

Options and reasoning: _to be filled in._

---

## 5. Generation — **decision pending**

Produce a grounded answer with citations back to source chunks.

Open decisions:

- **5a. Generation model** — local vs. hosted; which specific model.
- **5b. Prompt and citation format** — how the model is constrained to the
  retrieved context, and how citations are emitted and verified.
- **5c. Grounding check** — whether and how we verify the answer is actually
  supported by the cited chunks.

Options and reasoning: _to be filled in._

---

## 6. Evaluation — **decision pending**

A hand-written set of ~30–40 question / expected-chunk pairs, scored with real
retrieval metrics, run before and after any tuning.

Open decisions:

- **6a. Metrics** — likely Recall@k, MRR, nDCG; plus abstention precision/
  recall for the "not found" path. Which ones, and why those.
- **6b. Question set design** — coverage across formats and question types
  (factual lookup, multi-hop, unanswerable). Label anchoring is already settled
  in §2c: location + verbatim snippet, resolved to chunks at eval time.
- **6c. Harness mechanics** — how runs are recorded and compared over time so
  "before and after tuning" is a real comparison, not a memory.

Options and reasoning: _to be filled in._

---

## 7. API — **decision pending**

Endpoints to ingest documents and query the system.

Open decisions:

- **7a. Web framework.**
- **7b. Surface** — endpoint shape, sync vs. async ingestion, error and
  abstention responses, streaming or not.
- **7c. Deployment** — where and how it is hosted publicly, and what that costs.

Options and reasoning: _to be filled in._

---

## 8. Docs — **decision pending**

README covering architecture, evaluation results with real numbers, known
limitations, and a short "how this was built" note: agentic-coding-assisted,
human-reviewed, tested, with decisions made deliberately rather than defaulted
to.

Options and reasoning: _to be filled in._
