# The corpus

`data/raw/` holds the documents Recall ingests. It is gitignored: the files are
not this project's to redistribute, and derived artefacts (`data/chunks.jsonl`,
`data/index/`) are gitignored for the same reason — a chunked derivative of
share-alike source inherits the share-alike term.

## What is in it

**MIT OpenCourseWare 6.02 — Introduction to EECS II: Digital Communication
Systems, Fall 2012.** Prof. Hari Balakrishnan and Prof. George Verghese, MIT
Department of Electrical Engineering and Computer Science.

<https://ocw.mit.edu/courses/6-02-introduction-to-eecs-ii-digital-communication-systems-fall-2012/>

| Shape | Files | Source |
|---|---|---|
| lecture slide decks | 23 | course *Lecture Slides* page |
| problem sets | 9 | course *Assignments* page |
| syllabus | 1 | see the note below |

## Licence

MIT OpenCourseWare material is licensed **CC BY-NC-SA 4.0**
(<https://creativecommons.org/licenses/by-nc-sa/4.0/>). It is not relicensed by
this repository, which is MIT-licensed for its *code* only (see `LICENSE`).

## The syllabus is a format conversion, not an OCW-published file

OCW publishes syllabi as web pages; no networking course checked publishes one
as a PDF. `syllabus.pdf` was rendered from the course's syllabus page by
`reportlab`, preserving the text and heading structure as published — headings
keep OCW's capitalisation rather than being reshaped to suit this project's
syllabus chunker.

It is a derivative of CC BY-NC-SA material and carries the same terms. It is
recorded here rather than left to be inferred, because a generated PDF sitting
among 32 downloaded ones is otherwise indistinguishable from them.

## Why this corpus

SPEC.md §8a: development ran against private course notes that cannot be
published, so retrieval metrics computed over them could not be re-run or
checked by anyone else. The replacement was chosen to match the *shape* of the
original — slide decks, problem sets, a syllabus — because every §2 chunking
decision is an argument about those specific document types.

The private corpus is not kept as a second baseline — it served as the
development stage. The pipeline takes a directory argument and hard-codes
nothing, so any corpus can be ingested by pointing `recall-ingest` at it.
