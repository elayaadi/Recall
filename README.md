# Recall

A retrieval-augmented generation system that answers questions from my own
study notes and course materials — markdown, PDF, and PowerPoint — with
citations back to the source passage, and a hand-built evaluation harness that
measures retrieval quality with real numbers.

**Status: in progress.** Ingestion, indexing, retrieval and generation are
built, tested, and measured against a 564-page corpus of MIT OpenCourseWare
material that ships with the repo's instructions to fetch it. The evaluation
harness is decided but not started, so no quality metric is claimed yet.
Architecture decisions are made one module at a time and recorded with the
alternatives they beat — including the ones later evidence overturned.

- [docs/decisions.md](docs/decisions.md) — every architecture decision, plus the
  ones that were reversed or corrected on evidence
- [SPEC.md](SPEC.md) — module-by-module specification and the full reasoning
- [docs/corpus-profile.md](docs/corpus-profile.md) — what the source documents
  actually are, measured before anything was designed around them
- [CLAUDE.md](CLAUDE.md) — working conventions for the repo

## How this was built

Written with agentic coding assistance (Claude Code), directed and reviewed by
me. Every architecture decision was made by comparing real alternatives before
choosing one, and the reasoning — including what was rejected and why — is in
the documents above rather than reconstructed afterwards. Every number reported
anywhere in this repo comes from an actual run; none are estimated or
illustrative.

This README is a placeholder. It gets written properly in module 8, once there
are evaluation results to report.
