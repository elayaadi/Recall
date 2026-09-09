"""BM25 over the same entries — the measured baseline, not a second retriever.

SPEC.md 4a chose dense-only after a probe refuted the argument for hybrid
retrieval on this corpus. Rather than assert that result, BM25 lives here so
module 6 can run both from one harness and report the difference — the same
shape as §2b, where uniform windowing stays in the repo so the structural
chunker's advantage is a number rather than a claim.

Hand-written rather than pulled in as a dependency: it is about forty lines,
and §3c's reasoning applies just as well to a scorer this small.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from ..indexing.store import IndexEntry, SearchHit

# Underscores are kept inside tokens so identifiers survive as one term:
# `rdt_send` is a single searchable thing, not "rdt" next to "send".
TOKEN_RE = re.compile(r"[a-z0-9_]+")

K1 = 1.5  # term-frequency saturation
B = 0.75  # length normalisation


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class BM25Index:
    """Okapi BM25 over the indexed entries."""

    def __init__(self, entries: list[IndexEntry], *, k1: float = K1, b: float = B) -> None:
        self._entries = list(entries)
        self.k1 = k1
        self.b = b
        self._docs = [Counter(tokenize(e.chunk.text)) for e in self._entries]
        self._lengths = [sum(d.values()) for d in self._docs]
        n = len(self._docs)
        self._avg_len = (sum(self._lengths) / n) if n else 0.0
        df: Counter[str] = Counter()
        for doc in self._docs:
            df.update(doc.keys())
        # Add-one smoothing keeps the idf of a term present in every document
        # positive rather than zero, so it still contributes a little.
        self._idf = {
            term: math.log(1 + (n - count + 0.5) / (count + 0.5))
            for term, count in df.items()
        }

    def __len__(self) -> int:
        return len(self._entries)

    def search(
        self,
        query: str,
        k: int = 5,
        *,
        doc_type: str | None = None,
        source_file: str | None = None,
    ) -> list[SearchHit]:
        terms = tokenize(query)
        if not terms or not self._entries:
            return []

        scored: list[tuple[float, int]] = []
        for i, doc in enumerate(self._docs):
            entry = self._entries[i]
            if doc_type is not None and entry.chunk.doc_type != doc_type:
                continue
            if source_file is not None and entry.chunk.source_file != source_file:
                continue
            length = self._lengths[i]
            total = 0.0
            for term in terms:
                freq = doc.get(term)
                if not freq:
                    continue
                denominator = freq + self.k1 * (
                    1 - self.b + self.b * length / (self._avg_len or 1)
                )
                total += self._idf.get(term, 0.0) * freq * (self.k1 + 1) / denominator
            if total > 0:
                scored.append((total, i))

        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [
            SearchHit(entry=self._entries[i], score=float(score))
            for score, i in scored[:k]
        ]
