import pytest

from recall.ingestion.boilerplate import find_boilerplate
from recall.ingestion.chunkers.window import chunk_windows
from recall.ingestion.models import WINDOW
from recall.ingestion.pdf import load


def _chunks(path, **kwargs):
    document = load(path)
    return chunk_windows(document, find_boilerplate(document), **kwargs)


def test_windows_overlap_by_the_requested_number_of_words(deck_path):
    chunks = _chunks(deck_path, window_words=10, overlap_words=4)
    first, second = chunks[0].raw_text.split(), chunks[1].raw_text.split()
    assert first[-4:] == second[:4]


def test_windows_ignore_structure_and_span_pages(deck_path):
    chunks = _chunks(deck_path, window_words=40, overlap_words=5)
    assert any(len(c.locator.pages) > 1 for c in chunks)


def test_windows_are_marked_as_the_baseline_chunker(deck_path):
    assert all(c.chunker == WINDOW for c in _chunks(deck_path))


def test_windows_carry_no_title_prefix(deck_path):
    assert all(c.text == c.raw_text for c in _chunks(deck_path))


def test_boilerplate_is_stripped_for_the_baseline_too(deck_path):
    # Otherwise a measured delta could be an artefact of the footer, not chunking.
    assert all("Example Course" not in c.text for c in _chunks(deck_path))


def test_overlap_must_be_smaller_than_the_window(deck_path):
    with pytest.raises(ValueError):
        _chunks(deck_path, window_words=10, overlap_words=10)
