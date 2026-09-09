from recall.ingestion.pdf import load


def test_loads_every_page_including_the_one_without_text(deck_path):
    document = load(deck_path)
    assert len(document.pages) == 9
    assert document.empty_pages == (5,)
    assert len(document.text_pages) == 8


def test_slide_pages_are_landscape(deck_path):
    assert all(page.is_landscape for page in load(deck_path).pages)


def test_largest_span_is_the_slide_title(deck_path):
    pages = {p.number: p for p in load(deck_path).pages}
    assert pages[2].largest_span_text() == "Web caching"
    assert pages[4].largest_span_text() == "Web caching (cont.)"
    assert pages[5].largest_span_text() is None


def test_page_footers_are_dropped_even_though_they_differ_per_page(problem_sheet_path):
    # "Page 1 of 2" / "Page 2 of 2" cannot be caught by repeated-line detection.
    text = load(problem_sheet_path).pages[0].text
    assert "Page 1 of 2" not in text
    assert "Homework 9" in text


def test_source_hash_is_recorded(deck_path):
    assert len(load(deck_path).sha256) == 64


def test_the_slide_number_is_removed_from_the_end_of_a_footer_line(deck_path):
    pages = {p.number: p for p in load(deck_path).pages}
    assert "(c) Example Course, Networks 101" in pages[8].lines
    assert not any(line.endswith(" 8") for line in pages[8].lines)


def test_a_number_that_is_not_the_page_number_is_left_alone(deck_path):
    # On page 2 the footer reads "... Networks 101 2": the trailing 2 is the
    # page number and goes, the 101 is content and stays.
    lines = {p.number: p.lines for p in load(deck_path).pages}[2]
    assert any(line.endswith("Networks 101") for line in lines)


def test_a_title_rendered_twice_for_a_shadow_effect_is_not_doubled(deck_path):
    pages = {p.number: p for p in load(deck_path).pages}
    assert pages[3].largest_span_text() == "Web caching"
