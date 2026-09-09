# Recall — specification

A retrieval-augmented generation system that answers questions from personal
study notes and course materials, with citations back to the source, and a
hand-built evaluation harness that proves retrieval quality with real numbers.

**Status:** modules 1–2 done — ingestion is decided, implemented, tested, and
measured against the real corpus. Modules 3–8 are `decision pending`, except
§8a (publication corpus), settled early because it constrains §6.

Each section is filled in as we settle it: the options considered, the choice,
and the reasoning — including the alternatives that were rejected, so they are
not quietly reconsidered later. The architecture should be followable from this
file alone.

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
- Every decision is recorded with the alternatives it beat, so the design can
  be understood from the repo without asking the author.

**Non-goals for v1.** OCR for scanned documents. A real UI beyond a minimal
demo. Multi-user auth. Fine-tuning any model.

**Language/runtime.** Not formally decided, but the decision list below
(Ollama, LangChain/LlamaIndex, PDF and PPTX parsing, Python web frameworks)
assumes Python. Flag it now if you want otherwise.

---

## 1. Repo setup — **done**

Module folders, `SPEC.md`, `CLAUDE.md`, git, GitHub remote, initial commit.

---

## 2. Ingestion — **done: decided, implemented, tested, measured**

Parse markdown, PDF, and PowerPoint into a common chunked format carrying
source file, section/heading, and page or slide number.

**Corpus.** Measured, not assumed — see [docs/corpus-profile.md](docs/corpus-profile.md).
This is the private development corpus; what ships with the public repo is
decided in §8a.
29 PDFs from one course: 22 slide decks, 6 problem sheets, 1 syllabus; 578
pages, ~43k words, English. **No scans**, so OCR being out of scope costs
nothing. 1 of 578 pages produces no chunk, and it is reported by page number at
ingest rather than passed over silently.

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
  AGPL. PyMuPDF is ~10× faster, which 578 pages makes irrelevant. AGPL's
  copyleft reaches anything that links the library, constraining how this code
  could later be reused, relicensed, or vendored into something else; MIT costs
  nothing here and forecloses nothing.

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
| chunks (structural) | 528 |
| words | 35,797 |
| mean / median words per chunk | 68 / 57 |
| shortest / longest chunk | 1 / 742 words |
| multi-slide merged chunks | 45 |
| pages producing no chunk | 1, reported by page number |

All 29 files were routed to the right chunker by structural signal alone, with
no filename fallback. Problem-sheet chunk counts match the numbering found
independently during profiling (6, 8, 5, 3, 7, 4).

**Four defects found by reading the chunks, not by the tests.** Inspecting the
shortest chunks after the first run (`scripts/inspect_chunks.py --shortest`)
found each of these, and each is now fixed with a regression test:

- The footer often carries the slide number on the same visual line
  (`(c) Course, Networks: 7`), which makes it unique per page and therefore
  invisible to repeated-line detection. It was surviving into chunk bodies —
  on some slides it *was* the whole body. Removing it cut 2,720 words of pure
  boilerplate, about 7% of the corpus text.
- Some decks render a title twice, offset, for a shadow effect. Both copies sit
  at the title font size, so the title read as
  `HTTPS - Certificates HTTPS - Certificates`.
- The title was not always stripped from its own chunk body, because the same
  characters render differently in the two places (`Cookies: keeping state` in
  the title, `Cookies: keeping " state "` in the body). Comparison is now
  punctuation- and case-insensitive.
- **The worst one: pages with no distinct title.** Many slides put all their
  text at a single font size, so nothing on them is a heading. Taking the
  largest span as the title anyway moved the *entire slide* into the title field
  and then stripped it out of the body — Week 3 slide 12 has nine lines of real
  content and was reduced to a 1-word chunk. The content was not merely
  mislabelled, it was deleted from `raw_text`, which is the field the eval
  harness matches gold snippets against and the generator quotes from. A page
  now has a title only when its content spans carry more than one font size.
  This alone changed 494 chunks to 528 and cut pages producing no chunk from 32
  to 1.

This is the argument for writing chunks to JSONL rather than passing them
straight to the indexer: all three were obvious on sight and none would have
failed a test written before the corpus was read.

**Duplication across files — open, to be settled in §3/§4.** The `Week N
On-line` decks re-release material from the `Lecture N` decks, so **139 of 528
chunks (26%) have byte-identical body text to another chunk**, across 59
distinct bodies. A further 134 chunks share a title with a chunk in another file
but carry genuinely different text, which is ordinary and needs no handling.
Exact duplicates do need handling: they consume two slots in a top-k retrieval
for one passage, and a gold label anchored to one file's copy scores as a miss
when the other copy is retrieved. The likely answer is exact-hash deduplication
at index time, keeping one chunk that carries both locations as citations, with
near-duplicate handling deferred until measured.

**Known limitations, recorded rather than hidden.** Roman-numeral sub-parts
(`i.`, `ii.`) inside a problem are not captured in `parts` metadata; only
`a)`–`h)` are. Deck cover slides and recurring agenda/roadmap slides survive
as low-value chunks that mention many topics and answer none, as do divider
slides whose text is just a section name. 76 chunks (14.4%) are under 15 words.
No minimum chunk size is enforced: the threshold is exactly the kind of knob
module 6 should measure rather than one to guess at now. 25 chunks contain the instructor's email address,
which matters only for the private development corpus (see §8a). Syllabus tables flatten to a row-ambiguous stream. A same-title
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

## 8. Docs and publication — **8a decided; README pending**

README covering architecture, evaluation results with real numbers, known
limitations, and a short "how this was built" note: agentic-coding-assisted,
human-reviewed, tested, with decisions made deliberately rather than defaulted
to.

Options and reasoning: _to be filled in._

### 8a. Publication corpus — decided: build on the real notes, publish on MIT OCW

Development runs against the real CS447 materials — 29 PDFs in `data/raw/`,
gitignored and never committed. That is the corpus every module-2 decision was
measured against, and the corpus the system actually exists to answer questions
from.

For publication those files are replaced with openly-licensed course material
from **MIT OpenCourseWare** (CC BY-NC-SA), chosen to match the *shape* of the
current corpus: lecture slide decks, problem sets, and a syllabus.

*Why the same shape.* Every §2 decision — the three chunker branches, slide-title
run merging, ALL-CAPS syllabus sections, sequential problem numbering — is an
argument about these specific document types. Swapping in prose documents would
leave the reasoning intact but aimed at documents the repo no longer contains.

*Why publish a corpus at all.* §6 promises retrieval quality "with real
numbers". Numbers computed over files nobody else can obtain are assertions
rather than evidence: they cannot be re-run, re-checked after a change, or
compared against a different approach. With a public corpus the ingest and the
eval harness run anywhere and the numbers reproduce.

**Timing: the swap happens before the §6 question set is written.** Gold labels
anchor to source file, location, and verbatim snippet (§2c). There are ~35 of
them, hand-written, and they are the only genuinely expensive human artifact in
this project. Written against the private corpus they cannot be published, and
if the corpus is swapped afterwards they all have to be written again. Modules
3–5 are indifferent to which documents are in `data/raw/`, so the swap costs
nothing at any point before module 6 and a full re-labelling after it.

What regenerates at swap time, all from a command rather than by hand: the
corpus profile, the measured ingestion table in §2, and the 44% title-heuristic
figure in §2a. The private corpus stays usable locally — the pipeline takes a
directory argument and hard-codes nothing.

**Licensing.** The code is MIT (`LICENSE`). The corpus is not: OCW material is
CC BY-NC-SA, stays under `data/` with its own attribution and licence note, and
is never relicensed by this repo. Derived artefacts stay gitignored, since a
chunked derivative of CC BY-NC-SA source would inherit the share-alike term.

Rejected: **keeping the corpus private permanently and shipping only synthetic
fixtures** — zero exposure and no re-labelling, but the evaluation numbers
become unverifiable claims, which defeats the point of measuring them at all.
Rejected for v1: **maintaining both corpora with two eval sets** — the most
rigorous option, but it doubles the hand labelling, the one step no tooling
makes cheaper. Reasonable to add once the
public set exists.
