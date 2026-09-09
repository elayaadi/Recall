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


def test_a_footer_carrying_the_slide_number_is_still_detected(deck_path):
    # The fixture prints "(c) Example Course, Networks 101 <n>" on each slide.
    # Without removing the number the footer is unique per page and invisible
    # to repeated-line detection, which is how it survived into chunk bodies.
    document = load(deck_path)
    assert find_boilerplate(document) == frozenset({"(c) Example Course, Networks 101"})
