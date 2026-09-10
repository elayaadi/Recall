"""Resolve gold labels to chunks. SPEC.md 2c, 6b.

A label anchors to a source file, a human-readable location, and a **verbatim
snippet**. The snippet is what binds: chunk ids change whenever chunking
changes, and §2c chose this anchoring precisely so that tuning the chunker does
not mean re-writing thirty-five hand-written labels.

Matching is whitespace- and case-normalised, because a snippet copied from a PDF
carries whatever line breaks the extractor produced. Several chunks may match
one label and all of them count as relevant — which is why §6a's metrics are the
ones that handle multi-target binary relevance.

**A label matching zero chunks raises.** §2c is explicit that this is a hard
error and never a silent score of 0: a stale label scoring 0 is indistinguishable
from a retrieval regression, and the whole point of the harness is to tell those
two apart.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

QUESTIONS = Path("eval/questions/questions.toml")
CHUNKS = Path("data/chunks.jsonl")


class UnresolvedLabel(RuntimeError):
    """A gold label matched no chunk. Never downgraded to a score of 0."""


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


@dataclass(frozen=True)
class Label:
    file: str
    where: str
    snippet: str


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    kind: str
    labels: tuple[Label, ...]
    note: str = ""

    @property
    def answerable(self) -> bool:
        return self.kind != "unanswerable"


def load_questions(path: Path = QUESTIONS) -> list[Question]:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    out: list[Question] = []
    for raw in data["question"]:
        labels = tuple(
            Label(file=l["file"], where=l["where"], snippet=l["snippet"])
            for l in raw.get("labels", ())
        )
        q = Question(
            id=raw["id"], text=raw["text"], kind=raw["kind"],
            labels=labels, note=raw.get("note", ""),
        )
        if q.answerable and not q.labels:
            raise UnresolvedLabel(f"{q.id}: answerable question carries no label")
        if not q.answerable and q.labels:
            raise UnresolvedLabel(f"{q.id}: unanswerable question carries a label")
        out.append(q)
    return out


def load_chunks(path: Path = CHUNKS) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def resolve(label: Label, chunks: list[dict]) -> list[str]:
    """Chunk ids whose text contains the snippet. Raises if none do."""
    needle = normalise(label.snippet)
    hits = [
        c["chunk_id"]
        for c in chunks
        if c["source_file"] == label.file and needle in normalise(c["raw_text"])
    ]
    if not hits:
        raise UnresolvedLabel(
            f"no chunk in {label.file} contains {label.snippet!r} "
            f"(label points at {label.where})"
        )
    return hits


def relevant_ids(question: Question, chunks: list[dict]) -> set[str]:
    """Every chunk any of the question's labels resolves to."""
    ids: set[str] = set()
    for label in question.labels:
        ids.update(resolve(label, chunks))
    return ids
