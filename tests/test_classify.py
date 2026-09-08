from recall.ingestion.classify import classify
from recall.ingestion.models import DECK, PROBLEM_SHEET, SYLLABUS
from recall.ingestion.pdf import load


def test_landscape_sparse_pages_classify_as_a_deck(deck_path):
    result = classify(load(deck_path))
    assert result.doc_type == DECK
    assert "landscape" in result.reason


def test_sequential_numbering_classifies_as_a_problem_sheet(problem_sheet_path):
    result = classify(load(problem_sheet_path))
    assert result.doc_type == PROBLEM_SHEET
    assert "numbered" in result.reason


def test_all_caps_headings_classify_as_a_syllabus(syllabus_path):
    result = classify(load(syllabus_path))
    assert result.doc_type == SYLLABUS
    assert "ALL-CAPS" in result.reason


def test_classification_never_relies_on_the_filename_when_signals_are_clear(deck_path, tmp_path):
    misleading = tmp_path / "syllabus.pdf"
    misleading.write_bytes(deck_path.read_bytes())
    assert classify(load(misleading)).doc_type == DECK
