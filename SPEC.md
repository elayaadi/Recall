# Recall — specification

A retrieval-augmented generation system that answers questions from personal
study notes and course materials, with citations back to the source, and a
hand-built evaluation harness that proves retrieval quality with real numbers.

**Status:** modules 1–2 done — ingestion is decided, implemented, tested, and
measured against the real corpus. Module 3 is decided and awaiting
implementation. Modules 4–8 are `decision pending`, except §8a (publication
corpus), settled early because it constrains §6.

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

**Duplication across files — settled in §3d.** The `Week N On-line` decks
re-release material from the `Lecture N` decks, so **123 of 528 chunks (23%)
have byte-identical body text to another chunk**, across 52 distinct bodies;
normalising to alphanumeric characters only raises that to 139 across 59, which
is the figure this section first reported as byte-identical. A further set of
chunks share a title with a chunk in another file but carry genuinely different
text, which is ordinary and needs no handling. Duplicates do need handling:
they consume two slots in a top-k retrieval for one passage, and a gold label
anchored to one file's copy scores as a miss when the other copy is retrieved.
§3d deduplicates on the byte-identical raw body, keeping one chunk that carries
every location as a citation, and defers near-duplicate handling until §6
measures whether it is needed.

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

## 3. Indexing — **decided; implementation pending**

Turn chunks into a searchable index.

**Scale sets the terms of every decision below.** The structural chunker
produces 528 chunks — 35,797 words, 238,074 characters of embedded text, about
60k tokens. Most published guidance on vector infrastructure is written for
corpora three to six orders of magnitude larger, and at this size parts of it
inverts: approximate nearest-neighbour search gives up recall for a speed gain
too small to observe. Each decision is made against 528 and records the point
at which it should be reopened.

### 3c. Hand-built pipeline, not LangChain or LlamaIndex — decided

Settled first, because it constrains both the embedding model and the store.

**Hand-built, behind two protocols** — `Embedder` and `VectorStore`. Roughly
300 lines across modules 3–5, adding `numpy` and one embedding library.

The deciding argument is that the frameworks' central abstraction is the one
piece this repo already has and has fitted to the corpus. LlamaIndex and
LangChain both organise a pipeline around a node type they split themselves,
and §2b's chunker is structure-aware — same-title slide runs, validated problem
numbering, boilerplate stripping, prepended title paths. None of that survives
a generic recursive character splitter. Adopting a framework means either
discarding that work or spending the integration effort teaching the framework
not to redo it.

The second argument is the eval harness. §2c anchors gold labels to a location
plus a verbatim snippet, deliberately not to a chunk id. A framework retriever
returns its own scored-node type, so every eval run would pass through a
translation layer back onto the locator scheme — a layer maintained on top of
the framework rather than instead of it.

**What this costs, stated plainly.** Top-k selection, score normalisation, the
persistence format and the query/document asymmetry all become this repo's bugs
to have. The failure class is specific and predictable: skipping normalisation
before a dot product, an off-by-one in top-k, silently comparing vectors that
came from two different models. Each gets a test in §3e.

Reversibility settled the close call. Hand-built to framework later is an
adapter, because the protocols are narrow and the eval harness never referenced
framework types. Framework to hand-built means unpicking abstractions that
would by then have spread through modules 3, 4 and 5.

Rejected: **LlamaIndex** — the better fit of the two, RAG-native, and it would
supply much of module 5's response synthesis for free. Rejected on the two
arguments above, not on any defect. Rejected: **LangChain** — the heaviest
transitive dependency tree of the three options and the most API churn to pin
against, while being the least RAG-shaped, so the fraction actually used would
be small.

### 3a. Embedding model — decided: a protocol, local by default, both measured in module 6

**Cost is not a differentiator at this size and no part of this decision rests
on it.** The whole corpus is about 60k tokens: $0.0012 through OpenAI's
`text-embedding-3-small`, $0.0078 through `text-embedding-3-large`. It could be
re-embedded eight hundred times for a dollar. Latency is equally irrelevant
over 528 chunks. What actually differs:

- **Reproducibility on a fresh clone.** §6 and §8a promise a reader can clone
  the repo and re-run the eval harness. A hosted-only embedder narrows that to
  readers holding an API key and a billing account.
- **Stability of the recorded numbers.** Hosted embedding endpoints get
  deprecated and are occasionally updated in place; a pinned local model
  produces the same vectors indefinitely. Metrics recorded in §6 should outlast
  a vendor's deprecation cycle.
- **Quality.** On public retrieval benchmarks `text-embedding-3-large` leads,
  with `text-embedding-3-small`, `bge-base-en-v1.5` and `nomic-embed-text`
  close together and task-dependent. Whether that ordering survives on 528
  chunks of one course's slide decks is precisely the kind of claim this
  project measures instead of repeating.

**Decision.** Embedding sits behind an `Embedder` protocol
(`embed_documents`, `embed_query`, `name`, `dim`). The default implementation
is local: **`bge-base-en-v1.5`**, 768 dimensions, MIT-licensed weights — the
same licence reasoning as §2a. A hosted implementation is written to the same
protocol. Module 6 runs the eval set against both and reports the delta.

**This is a default, not a measured winner, and it is recorded as one.** The
harness that would settle it does not exist until module 6. Choosing the local
model now buys a fresh-clone path needing no credentials, and the protocol
keeps the question open rather than closing it early on a guess.

Two implementation details this decision carries. `bge` is asymmetric: queries
take the prefix `Represent this sentence for searching relevant passages:` and
documents do not, and applying it in both places or neither degrades retrieval
silently. And vectors are L2-normalised once at embed time, so cosine
similarity downstream is a plain dot product that cannot be skipped by
accident.

Rejected: **hosted only** — marginally better quality at negligible cost, but
it makes the eval harness unreproducible without credentials, contradicting §6.
Rejected: **local only** — simpler, but it forecloses the comparison rather
than deferring it, and the comparison is cheap to keep open.

### 3b. Vector storage — decided: numpy with exact search, plus an embedding cache

528 vectors at 768 dimensions is a 1.6 MB float32 matrix. A search is one
matrix–vector product, roughly 400k floating-point operations. Exhaustive
search is therefore exact, immediate, and about 60 lines.

**Decision.** A `VectorStore` protocol with a numpy implementation: a `.npy`
matrix plus a JSON sidecar of chunk metadata, written to `data/index/`. The
sidecar records the embedder name and dimension, so loading an index built by a
different model fails loudly instead of returning meaningless similarities.
Search returns chunk ids, scores and locators — never a bare row offset, which
any re-index would invalidate. Metadata filtering by `doc_type` or
`source_file` is a boolean mask over the sidecar; §6 needs it to construct the
not-found questions.

**An embedding cache keyed on `(chunk_id, embedder name)`** sits alongside the
store. §2 established that chunk defects are found by reading output and
re-running, so the chunker will keep changing; the cache means a chunker change
re-embeds only the chunks that changed. It is independent of the store choice
and survives a later move to a database.

Rejected: **FAISS.** Its exact mode (`IndexFlatIP`) is the same exhaustive
search, so at this scale the dependency buys a faster inner loop on an
operation already under a millisecond. Its approximate indexes are the reason
to adopt it at all, and they need roughly 10⁴–10⁵ vectors before the recall
they give up is repaid in speed; enabling them here would cost retrieval
quality for nothing observable. Rejected: **a vector database** (Chroma,
Qdrant, LanceDB) — buys incremental upsert, a filtering query language, and
concurrent access for §7, at the cost of a service or embedded engine, a
schema, and a migration story, in exchange for capabilities that are a boolean
mask and a cache at this size.

**Reopen when** the index passes roughly 50k chunks, or §7's API needs
concurrent multi-process reads, or §4 adopts a hybrid retriever whose lexical
half would be better served by a store that ships one. The last is the nearest:
BM25 over the same sidecar is `rank_bm25` or about 40 lines, and that cost
belongs to this decision rather than being discovered in §4.

### 3d. Duplicate chunks — decided: deduplicate on the byte-identical raw body

§2 recorded this as open. Re-measured against the current 528-chunk output:

| Identity defined by | chunks involved | groups | distinct after |
|---|---|---|---|
| `raw_text`, byte-identical | 123 | 52 | 457 |
| `raw_text`, alphanumeric-normalised | 139 | 59 | 448 |
| `text`, title prefix included, exact | 12 | 5 | 521 |

*Correction to §2.* That section reported "139 of 528 chunks byte-identical,
across 59 distinct bodies". The figure is reproducible but the description was
wrong: 139/59 is the count after normalising to alphanumeric characters only.
Byte-identical is 123/52. §2 now carries both figures rather than the
mislabelled one.

The third row is what changes the decision. Identity depends on which field
defines it, and the field actually embedded is `text`, which carries the title
path prepended in §2b. The `Week N On-line` decks re-release `Lecture N` slide
bodies under different titles — the same content appears as "CDN content
access: DNS redirection" in one deck and "CDN content access: a closer look" in
another — so most byte-identical bodies are not duplicates by embedded text at
all. Deduplicating on the embedded field would collapse 12 chunks and leave the
problem standing.

**Decision: identity is `raw_text`, byte-identical.** One chunk per distinct
body enters the index, carrying every location it was found at, and a citation
can name all of them. 51 of the 52 groups span more than one file, the pattern
§2 predicted. The surviving chunk keeps the first location in corpus order and
its title; the others are retained in the index entry so nothing about where
the passage appears is lost.

Rejected: **no deduplication** — two slots of a top-5 spent on one passage, and
a §2c gold label anchored to one file's copy scores as a miss when the other is
retrieved. Rejected: **deduplicating on `text`** — 12 chunks, which leaves the
problem essentially unaddressed. Rejected: **normalised matching** — 16 further
chunks collapsed, but it merges bodies differing in punctuation and case, and
§2's own defects showed those can be a real difference rather than noise.
Near-duplicate deduplication by embedding similarity stays deferred until §6
measures whether exact matching leaves a gap.

### 3e. Implementation plan

- `indexing/embed.py` — the `Embedder` protocol and `LocalEmbedder`: bge query
  prefix, batching, L2-normalisation at embed time.
- `indexing/cache.py` — `(chunk_id, embedder name) → vector`.
- `indexing/store.py` — the `VectorStore` protocol and `NumpyStore`: `.npy`
  plus JSON sidecar, embedder name and dimension checked on load, metadata
  filter, exact top-k.
- `indexing/build.py` — `recall-index`, mirroring `recall-ingest`:
  `data/chunks.jsonl` → `data/index/`. `data/index/` is gitignored on the same
  reasoning as `chunks.jsonl` in §8a.
- **Tests use a deterministic fake embedder and neither download a model nor
  open a socket**, so the suite still passes on a fresh clone with no corpus;
  the real embedder is exercised in one test marked slow and deselected by
  default. Covered: top-k ordering against hand-constructed vectors of known
  angle, save/load round-trip identity, a model or dimension mismatch raising
  rather than scoring, filtering narrowing the candidate set, the empty-result
  path §6 depends on, and a cache hit matching a cache miss exactly.
- `scripts/inspect_index.py`, on the §2 precedent that reading real output
  found defects the suite passed over. The 76 chunks under 15 words are where
  to look first.

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
