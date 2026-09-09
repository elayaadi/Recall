"""Build the vector index from chunks, and the `recall-index` command.

Deduplication happens here rather than at ingest, because it is an indexing
decision and not a fact about the documents: the chunks file stays a faithful
record of what each PDF contains, and the index is where the same passage
appearing in two decks collapses to one retrievable entry. SPEC.md 3d.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import OrderedDict
from pathlib import Path

from ..ingestion.models import Chunk
from ..ingestion.pipeline import read_jsonl
from .cache import EmbeddingCache, embed_texts
from .embed import HostedEmbedder, LocalEmbedder
from .store import Duplicate, IndexEntry, NumpyStore, index_size_bytes

LOCAL = "local"
HOSTED = "hosted"


def deduplicate(chunks: list[Chunk]) -> list[IndexEntry]:
    """One entry per distinct `raw_text`, keeping every location it appeared at.

    Identity is the byte-identical raw body, not the embedded `text`: the
    `text` field carries the prepended title path, and the Week decks re-release
    Lecture bodies under different titles, so identity by embedded text finds
    almost none of these. Measured both ways in SPEC.md 3d.

    Corpus order decides which copy survives, so the result is stable across
    runs and the surviving citation is the first occurrence.
    """
    groups: OrderedDict[str, list[Chunk]] = OrderedDict()
    for chunk in chunks:
        groups.setdefault(chunk.raw_text, []).append(chunk)
    return [
        IndexEntry(
            chunk=members[0],
            duplicates=tuple(
                Duplicate(source_file=m.source_file, locator=m.locator)
                for m in members[1:]
            ),
        )
        for members in groups.values()
    ]


def build_index(
    chunks: list[Chunk],
    embedder,
    *,
    cache: EmbeddingCache | None = None,
) -> NumpyStore:
    entries = deduplicate(chunks)
    vectors = embed_texts(
        embedder,
        [e.chunk_id for e in entries],
        [e.chunk.text for e in entries],
        cache=cache,
    )
    return NumpyStore(entries, vectors, embedder_name=embedder.name)


def make_embedder(kind: str):
    return LocalEmbedder() if kind == LOCAL else HostedEmbedder()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed chunks into a vector index.")
    parser.add_argument(
        "source", type=Path, nargs="?", default=Path("data/chunks.jsonl"),
        help="chunks JSONL written by recall-ingest",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("data/index"))
    parser.add_argument(
        "--embedder", choices=[LOCAL, HOSTED], default=LOCAL,
        help="local (default, no credentials) or hosted; SPEC.md 3a",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="embed every chunk again, ignoring cached vectors",
    )
    args = parser.parse_args(argv)

    if not args.source.is_file():
        parser.error(f"no chunks file: {args.source} (run recall-ingest first)")

    chunks = read_jsonl(args.source)
    embedder = make_embedder(args.embedder)
    cache = None if args.no_cache else EmbeddingCache.load(args.output, embedder)

    started = time.monotonic()
    store = build_index(chunks, embedder, cache=cache)
    elapsed = time.monotonic() - started

    store.save(args.output)
    if cache is not None:
        cache.save()

    collapsed = len(chunks) - len(store)
    groups = sum(1 for e in store.entries if e.duplicates)
    print(f"{len(chunks)} chunks -> {len(store)} entries")
    print(
        f"  deduplicated: {collapsed} chunks collapsed into {groups} groups "
        f"(identity: byte-identical raw_text)"
    )
    print(f"  embedder:     {embedder.name} ({store.dim} dimensions)")
    if cache is not None:
        print(f"  cache:        {cache.hits} hits, {cache.misses} embedded")
    print(f"  index:        {index_size_bytes(args.output) / 1e6:.2f} MB in {args.output}")
    print(f"  elapsed:      {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
