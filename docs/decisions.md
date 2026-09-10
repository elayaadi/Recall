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

- **2026-09-10 — §2b amended: chunks get a size bound, because the embedder
  has one.** `bge-base-en-v1.5` truncates at 512 tokens silently; measured on
  the §8a corpus, 29 of 471 chunks exceed it and **29% of all tokens are never
  embedded**, the worst chunk having 9% of itself represented. §2b's rule that a
  problem keeps its sub-parts holds at CS447's couple-hundred words and inverts
  at 22,097 characters. Oversized chunks are split on internal structure first,
  then windowed. A structural split alone was rejected on measurement: 19 of the
  29 have no internal structure to split on. The bound is a constructor argument
  with an uncalibrated default, per §4e, because it is a property of the
  embedder and dies at any embedder change — §2b.

## Indexing — module 3

- **2026-09-09 — Hand-built pipeline, not LangChain or LlamaIndex.** The
  frameworks' central abstraction is the chunker, and §2b's is structure-aware
  in ways a generic recursive splitter is not; adopting one means discarding
  that work or teaching the framework not to redo it. §2c's gold labels anchor
  to a location and snippet rather than a framework node type, so every eval
  run would carry a translation layer. Reversibility settled the close call:
  hand-built to framework later is an adapter, the reverse is an unpicking.
  The cost — top-k, normalisation, persistence and query/document asymmetry
  become this repo's bugs — is stated in §3c rather than left implicit.

- **2026-09-09 — Embedding behind an `Embedder` protocol, `bge-base-en-v1.5`
  as the local default, hosted written to the same protocol and measured in
  module 6.** Cost decides nothing at this size: the whole corpus is ~60k
  tokens, about a tenth of a cent to embed through a hosted model. What
  differs is that a hosted-only embedder narrows §6's clone-and-re-run promise
  to readers with an API key, and that hosted endpoints are deprecated while
  pinned local weights are not. Recorded explicitly as a default rather than a
  measured winner, because the harness that would settle it is module 6 — §3a.

- **2026-09-09 — Vector storage: numpy with exact search, plus an embedding
  cache.** 528 vectors at 768 dimensions is a 1.6 MB matrix and one
  matrix–vector product. FAISS's exact mode is the same exhaustive search, and
  its approximate indexes need 10⁴–10⁵ vectors before the recall they give up
  is repaid — enabling them here would cost quality for nothing observable. A
  vector database buys upsert, a filter language and concurrency, which are a
  boolean mask and a cache at this size. The reopening thresholds are written
  down rather than left to be rediscovered — §3b.

- **2026-09-09 — Duplicate chunks: deduplicate on the byte-identical raw
  body, keeping every location as a citation.** Which field defines identity
  is the whole decision: 123 chunks duplicate by `raw_text`, but only 12 by
  the embedded `text`, because the `Week N` decks re-release `Lecture N`
  bodies under different titles. Deduplicating on the embedded field would
  have looked correct and left the problem standing — §3d.

- **2026-09-09 — Near-duplicate handling stays deferred, now on a measurement
  rather than a guess.** Exact deduplication leaves 10 entry pairs above 0.99
  cosine and 58 above 0.95, and a real query returns the same assignment at
  ranks 3 and 4 from two decks. The cost is real and recorded; the threshold
  that would fix it is the kind of knob module 6 should measure rather than one
  to guess at now — §3, measured result.

## Retrieval — module 4

Settled on a probe of eight to ten queries against the real 457-entry index —
enough to rule options out, not enough to tune one. Each entry names what would
reopen it; §6 is where the thresholds get set.

- **2026-09-09 — Dense-only retrieval, with BM25 built as a measured baseline.**
  The case for hybrid was that dense embeddings fail on exact tokens, and the
  probe refuted it: `rdt_send` scores 0.759 onto the right slides and "RFC 2616"
  retrieves one of the two chunks containing that string. `CIDR` scores low
  because the term appears in the corpus **zero times** — correct behaviour, and
  nearly recorded as evidence of failure before it was checked. BM25 therefore
  ships as a §6 baseline rather than a second production path, the same shape as
  the window chunker in §2b — §4a.

- **2026-09-09 — Abstention by an absolute threshold on the top-1 score,
  calibrated in module 6.** Answerable queries land at or above 0.666 and absent
  ones at or below 0.594, an empty gap of 0.072. A margin rule was ruled out by
  measurement rather than taste: margins run 0.000–0.039 and do not track
  answerability, with `rdt_send` (answerable) and "capital of Peru" (absent)
  both at 0.000. θ ships uncalibrated and is a config value, not a constant,
  because it is a property of the embedder and dies at any embedder or corpus
  change — §4b.

- **2026-09-09 — No reranker in v1, with a measured trigger.** Adopt one when
  module 6 shows recall@20 materially above recall@5 — that gap is exactly the
  headroom a reranker recovers, and its absence would mean the problem is
  upstream in chunking or embedding instead. Deferral with a condition rather
  than avoidance — §4c.

- **2026-09-09 — Near-duplicate results are collapsed and their citations
  merged.** Promoted out of §3d's deferral because the cost stopped being
  hypothetical: 3 of 10 realistic queries return a near-duplicate pair inside
  top-5, and the index holds 58 pairs above 0.95 covering 97 of 457 entries.
  This is §3d's rule applied one level out — one passage, every location it
  appears at — and it is why search returns locators rather than row
  offsets — §4d.

- **2026-09-09 — Both retrieval thresholds are constructor arguments with
  uncalibrated defaults, never module constants.** They are properties of the
  embedder and the corpus, not of the system: module 6 sets them from the
  question set and the §8a corpus swap resets them. Shipping them as constants
  would make a placeholder indistinguishable from a measured value — §4b, §4e.

## Generation — module 5

Settled without a probe. Module 4's decisions rested on eight to ten real
queries; these rest on the shape of the problem and on what §6 can measure
afterwards. Each entry says which part is unmeasured.

- **2026-09-09 — A `Generator` protocol, local by default, both measured in
  module 6.** The same shape as §3a and, deliberately, not the same argument.
  For embedding the candidates were close and the local default cost little;
  for grounded answering the gap is expected to be wide, and the protocol's job
  is to keep §6's clone-and-re-run path credential-free while turning the gap
  into a measured number. Cost decides nothing and this time it is measured:
  528 chunks, mean 450 characters, so a k=5 context is about 2,250 characters —
  every candidate holds that with orders of magnitude to spare, and context
  window constrains nothing. Reusing the OpenAI dependency already present for
  the hosted embedder was rejected as a *rationale*: the shared thing is a
  package and an environment variable, not a design — §5a.

- **2026-09-09 — Citations as structured output: claims mapped to chunk ids.**
  The criterion is what can be verified afterwards, which makes this one
  decision with §5c rather than two. Inline numbered markers were rejected
  despite working identically on every backend — a marker binds a citation to a
  position, not to a claim, so the check §5c wants cannot be expressed over it.
  Provider-native citations were rejected despite being the strongest mechanism
  by a wide margin: available only on the hosted path, so adopting them as the
  format would decide §5a by the back door and turn §6's comparison into one of
  citation mechanisms rather than models — §5b.

- **2026-09-09 — The default backend is the one least able to enforce the
  chosen format, and that is recorded rather than resolved.** Ollama accepts a
  JSON-schema `format` parameter so the surface exists on both paths; whether a
  7–8B model honours it over a whole question set is unmeasured and is a §6
  number. Malformed output is a defined failure mode, never silently coerced
  into an answer — §5b.

- **2026-09-09 — Amended the same day on evidence: the prose a reader sees is
  composed from the verified claims, not taken from the model's own `answer`
  string.** As first written, §5b left the reader-facing text as the one part of
  the response §5c never checked. Three defects on the first two real runs came
  from it — ids written into the prose, a stray `}` inside a valid JSON string,
  and, decisively, sentences left pointing at nothing once the ids were removed
  (*"…is stated in passage, which says…"*). The first two are cleanable and the
  third is not. Composing makes the text grounded by construction and stops a
  dropped claim from reaching the answer at all. The model is still asked for
  prose and it is kept as `Answer.draft`, so its task is unchanged and §6 can
  compare the two without another run — §5b.

- **2026-09-09 — Grounding: deterministic in the answer path, entailment judge
  at eval time.** Ids resolving to chunks that were in the context, plus an
  n-gram overlap with the cited chunk — no model call, so it costs nothing to
  always run. A judge as a gate was rejected: it doubles latency and cost on
  every query to catch a failure whose rate is unmeasured, and a gate deciding
  on an unvalidated judge is worse than no gate. The judge's own agreement with
  a human is itself unmeasured, so §6 reports that agreement or reports the
  judge as a diagnostic rather than as a metric — §5c.

- **2026-09-09 — Generation abstains independently of §4b.** §4b measures
  similarity to the query and structurally cannot see five well-scoring
  passages that do not answer it, so no threshold on a similarity score closes
  that gap. Two mechanisms of different kinds: the model's own judgement in the
  output object, and a minimum count of claims surviving §5c's check — the
  latter a constructor argument with an uncalibrated default, per §4e. The two
  abstention paths are reported separately in §6, because a retrieval miss and
  a generation refusal are different defects with different fixes — §5d.

- **2026-09-09 — Blocking generation interface, not streaming.** §5c's check
  needs the whole answer before it can verify anything, so a streaming
  interface would buffer to the same place. Streaming is additive to a blocking
  protocol if §7 wants it; the reverse is an unpicking — §5e.

- **2026-09-09 — The hosted generator is deferred to the end of the project,
  with the trigger written into §8.** The `Generator` protocol is built and the
  local implementation runs; the second one behind it does not exist yet.
  Deferral with a named trigger, the shape §4c used for the reranker, rather
  than a reversal of §5a. Two free providers needing no payment method were
  checked first — Groq, OpenAI-compatible and so needing no new dependency, and
  Google AI Studio, a stronger model needing `google-genai` for reliable schema
  enforcement — so the deferral is recorded as a choice and not as the option
  being unavailable. `make_generator` raises on any kind but `local` and the
  `hosted-gen` extra does not exist, so the gap stays visible in the code.

  **The cost lands on §6 and is stated there rather than discovered later:
  module 6 measures the local path alone and reports no delta.** §5a's argument
  for the protocol was that it turns an expected gap into a measured number;
  until the second implementation exists that number does not, and §6 says so
  instead of reporting a comparison it did not run — §5a, §5e, §8.

- **2026-09-09 — The `hosted` extra is split into `hosted-embed` and
  `hosted-gen`.** `hosted = ["openai"]` meant "hosted *embedder*"; a second
  provider makes the name inaccurate and would install an embedding dependency
  for anyone wanting a generator. A small edit now, a breaking change to a
  published install command later — §5e.


## Evaluation — module 6

The module that pays off every deferral in §2–§5. Each entry is a measurement,
not a position.

- **2026-09-10 — Metrics: Recall@k, MAP, abstention precision/recall, plus
  answer-level figures.** §2c's labels are binary and possibly multi-target, so
  nDCG was rejected for needing graded relevance this project does not have, and
  MRR for reading only the first relevant result and discarding exactly the
  multi-match information §2c chose to keep — §6a.

- **2026-09-10 — θ calibrated to 0.62, and §4b's evidence for 0.63 did not
  survive the larger set.** §4's eight-query probe found an empty gap of 0.072
  between answerable and absent queries. Over 35 questions the bands **overlap**:
  4 of 9 unanswerable score at or above the lowest answerable, so no threshold
  separates them. 0.62 is the highest θ that refuses no answerable question,
  catching 5 of 9 unanswerable. Abstention recall of 0.556 is the honest figure
  and is a property of the overlap, not of the threshold — §4b, §6.

- **2026-09-10 — No reranker in v1, now on the measurement rather than the
  deferral.** §4c wrote the trigger down in advance: adopt one when recall@20 is
  materially above recall@5. They are identical, and no relevant chunk sits at
  ranks 6–20 for any question — there is no headroom a reranker could recover.
  §4c also said what that implies: the problem is upstream — §4c, §6.

- **2026-09-10 — The collapse threshold was swept and deliberately left alone.**
  Turning collapse off raises recall@5 from 0.923 to 0.962, traced to one
  question where §4d correctly merges an identical slide appearing in two
  lectures and the metric scores it 0 for comparing chunk ids. Tuning the
  threshold to that would be tuning to a measurement artefact. Recorded as the
  metric under-crediting §4d, with the fix — a collapsed hit reporting the ids
  it absorbed — named rather than made — §4d, §6.

- **2026-09-10 — Run records are committed JSON carrying their full
  configuration, and reported figures are in-sample.** A score without the
  thresholds, chunker, embedder and corpus that produced it cannot be compared
  to anything; `compare.py` refuses to compare quietly and says when the corpus
  changed underneath. A held-out split of 35 questions leaves too few points to
  calibrate against, so every run record carries an in-sample caveat in its own
  field — §6c.

- **2026-09-10 — A harness defect found by reading its output.** The first
  baseline reported recall@20 exactly equal to recall@5 because the harness
  retrieved 5 results and measured @20 over that same list, so §4c's trigger
  could not fire whatever the data said. Ranking is now scored at depth 20 while
  `k` governs what the system returns. The fourth time in this project that
  reading real output caught what a green suite did not — §6.

## API — module 7

- **2026-09-10 — Framework: FastAPI, in an optional extra.** This repo
  hand-built where it was cheap and instructive — numpy over FAISS (§3b), a
  `urllib` Ollama client over a package (§5e) — and an HTTP server is where that
  reasoning runs out: `http.server` documents itself as unfit for production and
  hand-rolling concurrency teaches nothing about retrieval. What FastAPI buys
  here specifically is validating §5d's four-outcome union **at the boundary**,
  a generated OpenAPI document §8 owes anyway, and an async model that matters
  because generation is minutes long. Starlette was the close call, rejected
  because the outcome union is exactly the shape worth validating mechanically.
  The dependency sits in an `api` extra, not the base install — §7a.

- **2026-09-10 — A refusal is a 200, and only an unusable generator is a 5xx.**
  The request was understood and processed; the answer is that the corpus does
  not answer it. §5d's three refusals carry an `outcome` discriminator in the
  body, and `failed` returns 502 so a client's retry logic can see a generator
  outage as one. 404 was rejected for conflating "no such route" with "no
  answer", leaving a client unable to tell a typo'd URL from an honest
  refusal — §7b.

- **2026-09-10 — No ingest endpoint, which narrows §7 as written.** That text
  promised endpoints to ingest documents; a full ingest plus index is about
  three minutes, and the alternatives are a job runner built for a corpus
  rebuilt by one command. Recorded as a scope change rather than a quiet
  omission — §7b.

- **2026-09-10 — No streaming, inherited rather than chosen.** §5e made the
  generator blocking because §5c needs the whole answer before it can verify
  anything; streaming tokens would mean streaming unverified text, which is the
  property §5c exists to provide — §7b.

- **2026-09-10 — Deployment: local only, and this narrows §7c as written.**
  Measured, `/answer` needs 5.1 GB of model resident and minutes of CPU per
  request, which is not a free tier, and a 23-second cold start rules out
  scale-to-zero regardless. A public `/search` alone would fit a small
  always-on instance, at a running cost for an API whose headline endpoint
  returns 501. §0 already caps this module at a minimal demo, and the property
  §8a spent a corpus swap to protect — that anyone can clone and reproduce the
  numbers — is served by a documented local run. §5a's hosted generator stays
  parked until §8 — §7c.

- **2026-09-10 — Running it found the app reporting healthy while unable to
  serve.** `deps.py` claimed the embedder was loaded at startup; it is lazy by
  design, so the 23-second cold start landed on the first request and a missing
  `sentence-transformers` surfaced as a 500 to whoever asked first rather than
  as a server that refused to start. The embedder is now forced to load at boot.
  The fifth time in this project that reading real output caught what a green
  suite did not — §7.

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

- **A figure was right and its description was wrong.** §2 reported "139 of
  528 chunks byte-identical, across 59 distinct bodies". Re-measuring while
  settling §3d reproduced 139/59 only after normalising to alphanumeric
  characters; byte-identical is 123/52. Both figures now appear in §2, and the
  distinction turned out to matter — the dedup decision in §3d turns on
  exactly which normalisation defines identity.

- **An absent term was twice nearly recorded as a retrieval failure.** `CIDR`
  scored 0.480 and *explain the three way handshake* was refused at 0.574. Both
  looked like misses and neither was: the terms appear in the corpus zero
  times, so the low scores were correct. Checking the corpus before calling a
  low score a defect is now a stated convention in CLAUDE.md rather than a
  lesson learned twice — §4a, §4 measured result.

- **Reading the output found what the tests did not, a second time.**
  Inspecting the built index surfaced a module 2 defect that the chunk-level
  inspection had passed over: 14 chunks carried `(cid:N)` sequences from glyphs
  the PDF font maps to no Unicode code point, which corrupt embedded text and
  defeated the title-stripping fix, leaving both copies of a title in the
  chunk. Now fixed at load time — the markers become spaces, which is correct
  both for the 66 occurrences standing in for a space inside a word and for the
  2 dingbats carrying no text. Kept as a separate change from the indexing
  commit, because it alters chunk ids and invalidates an index; that separation
  is also what let the embedding cache re-embed exactly the 14 changed chunks
  and reuse the other 443 — §2, §3.

- **Reading the output found what the tests did not, a third time.** Module 5's
  suite was green and `recall-answer` failed twice on its first real runs. A
  read timeout is a `TimeoutError`, not a `urllib.error.URLError`, so it escaped
  as a traceback rather than the `GenerationError` §5b requires — no test
  reached the transport. And the model wrote passage ids into the prose the
  instruction forbids them in, which is §5a's recorded instruction-following
  weakness arriving on the first query. Both fixed with tests; the pattern is
  now three modules old and is why each module ships a command that prints what
  it did — §5, measured result.
