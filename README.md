# Recall

A retrieval-augmented generation system that answers questions from my own
study notes and course materials — markdown, PDF, and PowerPoint — with
citations back to the source passage, and a hand-built evaluation harness that
measures retrieval quality with real numbers.

**Status: in progress.** Ingestion is built, tested, and measured against a real
578-page corpus. Indexing, retrieval, generation, and evaluation are not started
yet. Architecture decisions are made one module at a time and recorded with the
alternatives they beat.

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
