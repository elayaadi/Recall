# Recall — specification

A retrieval-augmented generation system that answers questions from personal
study notes and course materials, with citations back to the source, and a
hand-built evaluation harness that proves retrieval quality with real numbers.

**Status:** scaffolding only. Every module below is `decision pending`.

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

## 2. Ingestion — **2a, 2b decided; 2c pending**

Parse markdown, PDF, and PowerPoint into a common chunked format carrying
source file, section/heading, and page or slide number.

**Corpus.** Mixed PDFs: some prose documents with real heading hierarchy, some
slide decks exported to PDF, and some scanned. OCR is out of scope for v1, so
scanned pages must be *detected and reported* at ingest — never silently
emitted as empty chunks.

### 2a. Parsing libraries — decided

- **Markdown: `markdown-it-py`** (AST). Rejected a regex heading-splitter: it
  breaks on `#` lines inside fenced code blocks, which these notes contain.
- **PPTX: `python-pptx`.** Effectively the only maintained reader; the real
  work is in what we extract (title placeholder vs. body, speaker notes,
  tables, reading order), not in the library choice.
- **PDF: `pdfplumber` / `PyMuPDF`** — text spans with font size and position,
  clustered to infer heading levels. Gives section-level citations
  ("§3.2, p.14") and lets prose PDFs use the same structure-aware path as
  markdown. Because the corpus is mixed, the PDF path needs a document-type
  check: recover headings where structure exists, fall back to page-scoped
  chunking for deck-style PDFs, and flag scanned pages as unindexable.

  Rejected: `pypdf` (~1h, page-granularity citations only — too coarse for the
  prose half of the corpus). Rejected: ML layout models (`docling`, `marker`) —
  best fidelity, but heavy dependencies and it makes the pipeline someone
  else's model rather than a hand-built one.

  Open sub-choice: pdfplumber (MIT, ~10× slower) vs. PyMuPDF (fast, AGPL).

### 2b. Chunking — decided: structure-aware, with uniform windowing kept as a measured baseline

Two chunkers are built and both stay in the repo.

**Primary — structure-aware per format.** The author already segmented the
document; headings, pages, and slides are human-authored topic boundaries, and
uniform windowing discards that information then approximates it with
arithmetic. A size guard sits on top of the native units, since they are not
uniformly sized: oversized units split at paragraph breaks, undersized units
merge with siblings under the same parent.

- *Markdown:* split at heading boundaries.
- *PDF:* heading-based where structure is recoverable, else page-scoped. Chunks
  never cross a page boundary, so page citations stay exact. Known wart:
  paragraphs continuing across pages get cut.
- *PPTX:* one slide = one chunk, always. Carries the slide title, the deck
  section header, and the speaker notes — in lecture decks the notes are often
  the only real prose.

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

### 2c. Chunk schema and citation anchoring — **decision pending**

What metadata every chunk carries, and how eval gold labels anchor so they
survive re-chunking. See §6b — the two are the same decision.

Options and reasoning: _to be filled in._

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
  (factual lookup, multi-hop, unanswerable), and how gold chunks are labelled
  so labels survive re-chunking.
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
