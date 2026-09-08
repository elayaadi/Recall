# Recall — working conventions

Recall answers questions from Mohamed's own study notes and course materials
(markdown, PDF, PowerPoint) using retrieval-augmented generation. It is a
portfolio project for AI/backend roles and a learning project.

**Standalone.** Never import, copy, vendor, or link code from any other project
of Mohamed's. No shared config, no shared infrastructure.

## No stack has been chosen yet

Nothing is settled except what appears under "Decisions" at the bottom of this
file. Do not select libraries, models, frameworks, or storage engines by
default, by popularity, or because they are the obvious choice.

Every item marked `decision pending` in SPEC.md must first be presented as 2–3
realistic options with honest trade-offs:

- implementation effort
- cost (money and latency)
- what it teaches Mohamed
- how defensible it is when an interviewer asks "why this and not X?"

Then wait for Mohamed to choose. Do not write code for that part before he has.

When a decision is settled: append one line under "Decisions" here, and write
the reasoning into the matching SPEC.md section. Settled decisions are not
re-litigated — if new evidence appears, say so explicitly and propose a change.

## How we work

- **One module per session**, in SPEC.md order. Do not run ahead into the next
  module because the current one finished early.
- **Plan mode inside a module**: propose the implementation approach and ask
  clarifying questions before writing code, even when the architecture decision
  for that module is already made.
- **Tests per module**, passing, before the module is called done.
- **One meaningful commit per verified module.** Never a single large commit at
  the end. Commit messages say what changed and why.
- **Real numbers only.** Evaluation metrics must come from an actual run.
  Never estimate, illustrate, or placeholder a metric.
- **Report honestly.** Failing tests, skipped steps, and known gaps get said
  plainly.

## Scope guardrails (v1)

In scope, in order: ingestion → indexing → retrieval → generation → evaluation
→ API → docs.

Out of scope: OCR for scanned documents, any UI beyond a minimal demo,
multi-user auth, fine-tuning any model.

## Repo layout

```
src/recall/{ingestion,indexing,retrieval,generation,api}/  module code
eval/         evaluation harness; eval/questions/ holds the hand-written set
tests/        tests, mirroring the module layout
data/raw/     Mohamed's real notes — gitignored, never committed
data/sample/  small committed fixtures for tests
docs/         architecture notes and diagrams
```

## Decisions

Format: `YYYY-MM-DD — <area>: <choice> — see SPEC.md §<n>`

- 2026-09-08 — Markdown parsing: `markdown-it-py` AST, not regex — see SPEC.md §2a
- 2026-09-08 — PPTX parsing: `python-pptx` — see SPEC.md §2a
- 2026-09-08 — PDF parsing: `pdfplumber`/`PyMuPDF` with font-size heading
  recovery; mixed corpus, so the path branches on document type and flags
  scanned pages as unindexable (no OCR in v1) — see SPEC.md §2a
- 2026-09-08 — Chunking: structure-aware per format (heading path prepended to
  chunk text), with uniform token windowing kept as a committed baseline so
  module 6 can measure the delta — see SPEC.md §2b
