"""Query the index by hand and read what comes back.

Module 2's precedent: reading real output found four defects the test suite
passed straight over. The equivalent here is looking at what a query actually
retrieves — the 76 chunks under 15 words are the first place to look, since a
four-word title slide embeds into something that matches almost any question on
its topic and then answers none of it.

    uv run python scripts/inspect_index.py --query "why do routers drop packets"
    uv run python scripts/inspect_index.py --query "..." --type problem_sheet
    uv run python scripts/inspect_index.py --duplicates    # what 3d collapsed
    uv run python scripts/inspect_index.py --shortest 15   # entries most likely to mislead
"""

from __future__ import annotations

import argparse
from pathlib import Path

from recall.indexing.build import make_embedder
from recall.indexing.store import NumpyStore

DEFAULT_INDEX = Path("data/index")


def load(path: Path) -> NumpyStore:
    if not (path / "index.json").exists():
        raise SystemExit(f"no index at {path} — run: uv run recall-index")
    return NumpyStore.load(path)


def summarise(store: NumpyStore) -> None:
    entries = store.entries
    words = [e.chunk.n_words for e in entries]
    with_dupes = [e for e in entries if e.duplicates]
    print(f"{len(entries)} entries, {store.dim} dimensions, embedder {store.embedder_name}")
    print(f"words/entry: mean {sum(words) / len(words):.0f}  min {min(words)}  max {max(words)}")
    print(f"entries standing for more than one location: {len(with_dupes)}")
    tiny = sum(1 for w in words if w < 15)
    print(f"entries under 15 words: {tiny} ({tiny / len(entries):.1%}) — inspect with --shortest")


def show_hits(store: NumpyStore, query: str, k: int, doc_type: str | None, preview: int) -> None:
    embedder = make_embedder("local")
    store.check_embedder(embedder)
    hits = store.search(embedder.embed_query(query), k=k, doc_type=doc_type)
    if not hits:
        print("no results")
        return
    for hit in hits:
        body = " ".join(hit.entry.chunk.raw_text.split())
        print(f"{hit.score:.3f}  {hit.entry.chunk.n_words:>4}w  {hit.citations()[0]}")
        print(f"        {body[:preview]}")
        for extra in hit.citations()[1:]:
            print(f"        also at: {extra}")


def show_duplicates(store: NumpyStore, preview: int) -> None:
    for entry in store.entries:
        if not entry.duplicates:
            continue
        body = " ".join(entry.chunk.raw_text.split())
        print(f"{entry.chunk.n_words:>4}w  {body[:preview]}")
        for citation in entry.citations():
            print(f"        {citation}")


def show_shortest(store: NumpyStore, n: int, preview: int) -> None:
    for entry in sorted(store.entries, key=lambda e: e.chunk.n_words)[:n]:
        body = " ".join(entry.chunk.raw_text.split())
        print(f"{entry.chunk.n_words:>4}w  {entry.citations()[0]:<52} {body[:preview]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--path", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--query", help="run a search and print the results")
    parser.add_argument("-k", type=int, default=5, help="how many results")
    parser.add_argument("--type", dest="doc_type", help="deck | problem_sheet | syllabus")
    parser.add_argument("--duplicates", action="store_true", help="entries SPEC.md 3d collapsed")
    parser.add_argument("--shortest", type=int, metavar="N", help="the N smallest entries")
    parser.add_argument("--preview", type=int, default=100, help="body characters to show")
    args = parser.parse_args()

    store = load(args.path)
    if args.query:
        show_hits(store, args.query, args.k, args.doc_type, args.preview)
    elif args.duplicates:
        show_duplicates(store, args.preview)
    elif args.shortest:
        show_shortest(store, args.shortest, args.preview)
    else:
        summarise(store)


if __name__ == "__main__":
    main()
