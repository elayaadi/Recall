import json

from recall.ingestion.models import DECK, PROBLEM_SHEET, STRUCTURAL, SYLLABUS, WINDOW
from recall.ingestion.pipeline import ingest_directory, ingest_file, read_jsonl, write_jsonl


def test_ingest_reports_what_it_did_and_what_it_skipped(deck_path):
    chunks, report = ingest_file(deck_path)
    assert report.doc_type == DECK
    assert report.pages == 9
    assert report.empty_pages == (5,)
    # Page 9 has a title but no body, so it is reported rather than indexed.
    assert report.uncovered_pages == (5, 9)
    assert report.chunks == len(chunks) == 5
    assert report.boilerplate_lines == 1


def test_every_document_type_is_routed_to_its_chunker(corpus):
    _, reports = ingest_directory(next(iter(corpus.values())).parent)
    assert sorted(r.doc_type for r in reports) == sorted([DECK, PROBLEM_SHEET, SYLLABUS])


def test_the_baseline_chunker_runs_over_the_same_corpus(corpus):
    chunks, _ = ingest_directory(next(iter(corpus.values())).parent, chunker=WINDOW)
    assert chunks and all(c.chunker == WINDOW for c in chunks)


def test_structural_and_baseline_chunkers_coexist_in_one_file(corpus, tmp_path):
    directory = next(iter(corpus.values())).parent
    structural, _ = ingest_directory(directory)
    windows, _ = ingest_directory(directory, chunker=WINDOW)
    destination = tmp_path / "chunks.jsonl"
    write_jsonl(structural + windows, destination)
    reloaded = read_jsonl(destination)
    assert {c.chunker for c in reloaded} == {STRUCTURAL, WINDOW}
    assert len({c.chunk_id for c in reloaded}) == len(reloaded)


def test_jsonl_roundtrips_chunks_unchanged(corpus, tmp_path):
    chunks, _ = ingest_directory(next(iter(corpus.values())).parent)
    destination = tmp_path / "chunks.jsonl"
    write_jsonl(chunks, destination)
    assert read_jsonl(destination) == chunks


def test_jsonl_is_one_json_object_per_line(corpus, tmp_path):
    chunks, _ = ingest_directory(next(iter(corpus.values())).parent)
    destination = tmp_path / "chunks.jsonl"
    write_jsonl(chunks, destination)
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(chunks)
    assert all(json.loads(line)["chunk_id"] for line in lines)
