from recall.ingestion.boilerplate import find_boilerplate
from recall.ingestion.chunkers.problem_sheet import chunk_problem_sheet
from recall.ingestion.pdf import load


def _chunks(path):
    document = load(path)
    return chunk_problem_sheet(document, find_boilerplate(document))


def test_one_chunk_per_numbered_problem(problem_sheet_path):
    assert [c.locator.problem for c in _chunks(problem_sheet_path)] == ["1", "2", "3"]


def test_sub_parts_stay_with_their_parent_problem(problem_sheet_path):
    second = _chunks(problem_sheet_path)[1]
    assert second.locator.parts == ("a", "b")
    assert "What policy does each operator choose?" in second.raw_text
    assert "Which operator loses more" in second.raw_text


def test_a_line_that_breaks_the_sequence_does_not_open_a_problem(problem_sheet_path):
    second = _chunks(problem_sheet_path)[1]
    assert "breaks the sequence" in second.raw_text


def test_digits_in_prose_do_not_split_a_problem(problem_sheet_path):
    first = _chunks(problem_sheet_path)[0]
    assert "3 MB" in first.raw_text


def test_the_page_recorded_is_where_the_problem_starts(problem_sheet_path):
    chunks = _chunks(problem_sheet_path)
    assert chunks[0].locator.pages == (1,)
    assert chunks[2].locator.pages == (2,)


def test_the_problem_number_prefixes_the_text(problem_sheet_path):
    assert _chunks(problem_sheet_path)[2].text.startswith("homework 9 — Problem 3")
