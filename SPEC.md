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

## 2. Ingestion — **decision pending**

Parse markdown, PDF, and PowerPoint into a common chunked format carrying
source file, section/heading, and page or slide number.

Open decisions:

- **2a. Parsing library per format.** Markdown, PDF, and PPTX each need a
  parser; PDF in particular has very different options with very different
  fidelity/effort trade-offs.
- **2b. Chunking strategy per format.** The three formats have genuinely
  different structure. PPTX especially is sparse and fragmentary — bullet
  fragments, not prose — and a chunker tuned for prose will produce useless
  chunks from it. This gets its own decision, not a default.
- **2c. Chunk schema.** What metadata every chunk carries, and how a chunk id
  is formed so citations stay stable across re-ingestion.

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
