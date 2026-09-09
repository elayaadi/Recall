"""Collapse near-duplicate results, keeping every location as a citation.

SPEC.md 3d deduplicates on the byte-identical raw body. That leaves the cases
where the `Week N On-line` decks re-release `Lecture N` material with small
extraction differences: 58 entry pairs above 0.95 cosine, and measured at the
query, 3 of 10 realistic queries returning such a pair inside top-5. Two of five
slots for one passage.

This is 3d's rule applied one level out — one passage, every location it
appears at — which is why the store returns locators rather than row offsets.
"""

from __future__ import annotations

import numpy as np

from ..indexing.store import Duplicate, IndexEntry, SearchHit


def collapse_near_duplicates(
    hits: list[SearchHit], vectors: np.ndarray, threshold: float
) -> list[SearchHit]:
    """Drop each hit too similar to one already kept, merging its citations.

    The list is walked in rank order, so the survivor of a group is always its
    highest-scoring member and the top result never changes. `vectors` holds one
    row per hit, in the same order.

    Merging rather than dropping is the point: the passage genuinely appears in
    both decks, and the surviving citation should be able to say so.
    """
    if len(hits) != len(vectors):
        raise ValueError(f"{len(hits)} hits but {len(vectors)} vectors")
    if not hits:
        return []

    kept: list[int] = []
    absorbed: dict[int, list[SearchHit]] = {}
    for i, hit in enumerate(hits):
        for k in kept:
            if float(vectors[i] @ vectors[k]) >= threshold:
                absorbed.setdefault(k, []).append(hit)
                break
        else:
            kept.append(i)

    out: list[SearchHit] = []
    for k in kept:
        hit = hits[k]
        merged = absorbed.get(k)
        if not merged:
            out.append(hit)
            continue
        extra = tuple(
            Duplicate(source_file=d.chunk.source_file, locator=d.chunk.locator)
            for other in merged
            for d in (other.entry,)
        ) + tuple(d for other in merged for d in other.entry.duplicates)
        out.append(
            SearchHit(
                entry=IndexEntry(
                    chunk=hit.entry.chunk,
                    duplicates=hit.entry.duplicates + extra,
                ),
                score=hit.score,
            )
        )
    return out
