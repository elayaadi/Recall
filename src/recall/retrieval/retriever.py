"""Query in, passages out — or an honest refusal.

SPEC.md 4b makes abstention a first-class outcome rather than an empty list:
§0 lists "abstains rather than answering" as a v1 success criterion, and module
6 scores the abstention path separately from ranking quality.

Both thresholds here are **uncalibrated**. They are constructor arguments with
placeholder defaults, never module constants read at the call site, because
they are properties of the embedder and the corpus: module 6 sets them from the
question set, and the §8a corpus swap resets them again.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..indexing.store import SearchHit, VectorStore
from .collapse import collapse_near_duplicates

# Calibrated in module 6 against the 35-question set, replacing the placeholder
# 0.63 that §4's eight-query probe suggested. 0.62 is the highest threshold at
# which no answerable question is refused: it holds abstention precision at
# 1.000 while catching 5 of the 9 unanswerable questions. Raising it to 0.66
# catches one more and costs two real answers.
#
# The §4 probe's clean 0.072 gap did not survive the larger set — see §4b.
# This value is a property of the embedder and the corpus, so it is still a
# constructor argument and still dies at any embedder or corpus change.
CALIBRATED_ABSTAIN = 0.62
UNCALIBRATED_ABSTAIN = CALIBRATED_ABSTAIN  # name kept; call sites unchanged

# Swept in module 6 over 0.90-1.01 and left where it was. Every value that
# collapses anything scores identically; only switching collapse off entirely
# moves the number, and it moves it *up* — because the metric compares chunk
# ids and a collapsed hit carries its twin's location rather than its id. That
# is the metric under-crediting §4d, not §4d costing quality, so the threshold
# is not tuned to it. Recorded in §6's measured result.
UNCALIBRATED_COLLAPSE = 0.95

# Collapsing shortens the list, so more is fetched than returned. 4 is a guess
# with no measurement behind it and is recorded as one.
OVERFETCH = 4


@dataclass(frozen=True)
class RetrievalResult:
    """What retrieval decided, including deciding it found nothing."""

    query: str
    hits: list[SearchHit]
    abstained: bool
    reason: str
    best_score: float | None = None
    collapsed: int = 0

    def __bool__(self) -> bool:
        return not self.abstained


class Retriever:
    """Dense retrieval over the §3 index, with collapse and abstention.

    Deliberately not hybrid: SPEC.md 4a records that the probe refuted the
    argument for adding a lexical path, and keeps BM25 as a module 6 baseline
    (`lexical.py`) rather than a second production path.
    """

    def __init__(
        self,
        store: VectorStore,
        embedder,
        *,
        k: int = 5,
        abstain_threshold: float = UNCALIBRATED_ABSTAIN,
        collapse_threshold: float = UNCALIBRATED_COLLAPSE,
        overfetch: int = OVERFETCH,
    ) -> None:
        store.check_embedder(embedder)
        self._store = store
        self._embedder = embedder
        self.k = k
        self.abstain_threshold = abstain_threshold
        self.collapse_threshold = collapse_threshold
        self.overfetch = overfetch

    def retrieve(
        self,
        query: str,
        *,
        doc_type: str | None = None,
        source_file: str | None = None,
    ) -> RetrievalResult:
        if not query.strip():
            return RetrievalResult(query, [], True, "empty query")

        vector = self._embedder.embed_query(query)
        candidates = self._store.search(
            vector,
            k=self.k * self.overfetch,
            doc_type=doc_type,
            source_file=source_file,
        )
        if not candidates:
            return RetrievalResult(query, [], True, "nothing matched the filter")

        vectors = self._store.vectors_for([h.chunk_id for h in candidates])
        merged = collapse_near_duplicates(candidates, vectors, self.collapse_threshold)
        collapsed = len(candidates) - len(merged)
        hits = merged[: self.k]
        best = hits[0].score

        # Collapsing never reorders, so the best score is the same either way;
        # the check sits here so the reported figure is the returned one.
        if best < self.abstain_threshold:
            return RetrievalResult(
                query, [], True,
                f"best score {best:.3f} below threshold {self.abstain_threshold:.3f}",
                best_score=best, collapsed=collapsed,
            )
        return RetrievalResult(
            query, hits, False, "", best_score=best, collapsed=collapsed
        )
