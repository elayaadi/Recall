# Corpus profile

Measured before designing the chunker, so module 2 is built against facts about
these documents rather than assumptions about documents in general. Produced by
a throwaway diagnostic over `data/raw/` (PyMuPDF); the notes themselves are
gitignored.

**Snapshot: 2026-09-08 — 29 files, 578 pages, ~43,000 words.**

All 29 files are PDFs from a single course (CS447, Computer Networks). One
course keeps the eval question set coherent and makes "not found" questions easy
to construct from adjacent-but-absent topics.

## What the corpus actually is

| Type | Files | Pages | Median words/page |
|---|---|---|---|
| Slide decks (lectures + weekly online sets) | 22 | 570 | 41–111 |
| Problem sheets (homework) | 6 | 8 | 192–410 |
| Syllabus | 1 | 3 | 390 |

## Findings that shaped the design

**No scanned documents.** Nothing in this corpus needs OCR, so the v1
out-of-scope decision on OCR costs nothing here.

*Corrected after implementation:* this section first reported "14 pages with no
text layer", from a diagnostic that treated any page under 20 characters as
empty. Those pages are not empty — they are **divider slides carrying a title
and a bare slide number over a diagram**, e.g. "Turkish Internet" on page 29 of
Lecture 3. The real figure is that **32 of 578 pages produce no chunk**: a
handful with no text at all, the rest title-only diagram slides whose body
cannot be read without OCR. Ingestion reports every one of them by page number
rather than indexing a chunk that would match a query and then answer nothing.

**No multi-level heading hierarchy anywhere.** 22 of 29 files are slide decks,
where the structural unit is the slide, not a heading path. The 6 problem sheets
use 1–2 font sizes and carry no font-based structure at all. Font-size
*clustering* to reconstruct heading levels would therefore be machinery built
for a document type this corpus does not contain.

**But font size is still needed, for one simple job.** The largest-font span on
a slide is reliably the slide title (verified across sampled decks). Titles can
be split across sibling spans at the same size and must be joined in reading
order. This is a one-line heuristic, not a clustering model — and it is the
reason the parser still needs span-level font data rather than plain text.

**Every deck carries one boilerplate line** — a copyright/course line repeated
on 29–40 of every deck's pages. Left in, it lands in every chunk and every
embedding. Stripped by detecting lines that repeat on more than half a
document's pages.

**Consecutive slides share a title when they continue one topic.** In the
sample, slides 7–9 of one lecture all carry "Internet delays and routes". Runs
of same-titled slides are a document-provided signal for which slides belong in
one chunk — an answer to slide sparsity that comes from the author rather than
from a token count.

**Problem sheets number cleanly.** Top-level items are `1.`–`8.` at line start,
sequential with no gaps, with sub-parts `a)`–`d)`. Sequential validation (each
number increments by one) separates real problem numbers from incidental digits
in prose such as "3 MB". Verified across all 6 files.

**The syllabus uses ALL-CAPS section headings** — 11 across 3 pages
(`INSTRUCTOR`, `ASSESSMENT METHODS, WEIGHTS AND RULES`, …) — a clean and
document-specific heading signal. Its content is heavily tabular; table
structure flattens to a readable but row-ambiguous stream in plain extraction.

**Language: English.** Turkish-specific characters appear at ≤0.2% of alphabetic
characters, i.e. noise. No multilingual handling needed in v1.

**Scale.** At slide- and problem-level granularity the corpus yields roughly
400–450 chunks. That is small enough that index choice in module 3 is an
engineering decision about honesty rather than one about scale.

## Caveats

Table detection reported 10–16 sampled pages per deck, which is almost certainly
over-detection: aligned text boxes in slide layouts resemble table grids. Deck
table counts are not trusted. The syllabus table counts are real.

Word counts are estimated from character counts at 5.5 characters per word.

## Per-file measurements

| file | type | pages | median words/page | pages w/o text | distinct font sizes |
|---|---|---|---|---|---|
| homework 1.pdf | problem sheet | 2 | 350 | 0 | 1 |
| homework 2.pdf | problem sheet | 2 | 240 | 0 | 2 |
| homework 3.pdf | problem sheet | 1 | 240 | 0 | 1 |
| homework 4.pdf | problem sheet | 1 | 234 | 0 | 1 |
| homework 5.pdf | problem sheet | 1 | 410 | 0 | 1 |
| homework 6.pdf | problem sheet | 1 | 192 | 0 | 1 |
| Week 4 On-line.pdf | slide deck | 37 | 88 | 0 | 7 |
| Week 5 On-line.pdf | slide deck | 40 | 84 | 0 | 8 |
| Week 6 On-line.pdf | slide deck | 30 | 63 | 0 | 8 |
| cs447 Lecture 1.pdf | slide deck | 17 | 41 | 1 | 7 |
| cs447 Lecture 10.pdf | slide deck | 16 | 111 | 0 | 4 |
| cs447 Lecture 11.pdf | slide deck | 21 | 84 | 0 | 7 |
| cs447 Lecture 12.pdf | slide deck | 39 | 72 | 0 | 6 |
| cs447 Lecture 13.pdf | slide deck | 35 | 87 | 0 | 6 |
| cs447 Lecture 14.pdf | slide deck | 20 | 85 | 0 | 8 |
| cs447 Lecture 15.pdf | slide deck | 16 | 79 | 0 | 8 |
| cs447 Lecture 16.pdf | slide deck | 13 | 68 | 0 | 7 |
| cs447 Lecture 2.pdf | slide deck | 21 | 57 | 1 | 9 |
| cs447 Lecture 3.pdf | slide deck | 29 | 71 | 1 | 8 |
| cs447 Lecture 4.pdf | slide deck | 32 | 60 | 0 | 8 |
| cs447 Lecture 5.pdf | slide deck | 27 | 81 | 1 | 6 |
| cs447 Lecture 6.pdf | slide deck | 23 | 62 | 2 | 7 |
| cs447 Lecture 7.pdf | slide deck | 17 | 85 | 0 | 5 |
| cs447 Lecture 8.pdf | slide deck | 23 | 79 | 0 | 7 |
| cs447 Lecture 9.pdf | slide deck | 14 | 102 | 0 | 6 |
| cs447 Week 1 On-line.pdf | slide deck | 29 | 62 | 3 | 10 |
| cs447 Week 2 On-line.pdf | slide deck | 38 | 53 | 5 | 8 |
| cs447 Week 3 On-line.pdf | slide deck | 30 | 76 | 0 | 9 |
| Syllabus_2025_Fall_ENG.pdf | syllabus | 3 | 390 | 0 | 2 |
