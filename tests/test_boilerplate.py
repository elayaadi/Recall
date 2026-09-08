from recall.ingestion.boilerplate import find_boilerplate, strip_boilerplate
from recall.ingestion.pdf import load


def test_finds_the_line_repeated_across_the_deck(deck_path):
    assert find_boilerplate(load(deck_path)) == frozenset({"(c) Example Course, Networks 101"})


def test_short_documents_are_exempt(problem_sheet_path):
    # With two pages any shared line would trip a 50% threshold.
    assert find_boilerplate(load(problem_sheet_path)) == frozenset()


def test_strip_removes_boilerplate_and_blank_lines():
    lines = ("keep this", "footer", "", "  ", "keep that")
    assert strip_boilerplate(lines, frozenset({"footer"})) == ["keep this", "keep that"]
