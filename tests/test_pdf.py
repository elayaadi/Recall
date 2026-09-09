from recall.ingestion.pdf import load


def test_loads_every_page_including_the_one_without_text(deck_path):
    document = load(deck_path)
    assert len(document.pages) == 10
    assert document.empty_pages == (5,)
    assert len(document.text_pages) == 9


def test_slide_pages_are_landscape(deck_path):
    assert all(page.is_landscape for page in load(deck_path).pages)


def test_largest_span_is_the_slide_title(deck_path):
    pages = {p.number: p for p in load(deck_path).pages}
    assert pages[2].title() == "Web caching"
    assert pages[4].title() == "Web caching (cont.)"
    assert pages[5].title() is None


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
    assert pages[3].title() == "Web caching"


def test_a_page_whose_content_is_all_one_size_has_no_title(deck_path):
    # Slide 10 is three lines at a single font size. Calling the largest span a
    # title there moved the whole slide into the title field and stripped it
    # out of the body.
    from recall.ingestion.boilerplate import find_boilerplate

    document = load(deck_path)
    boilerplate = find_boilerplate(document)
    pages = {p.number: p for p in document.pages}
    assert pages[10].title(boilerplate) is None
    assert pages[2].title(boilerplate) == "Web caching"  # a real title still found
    assert len(pages[10].lines) > 1


def test_content_spans_drop_the_footer_split_across_sizes(deck_path):
    from recall.ingestion.boilerplate import find_boilerplate

    document = load(deck_path)
    spans = document.pages[1].content_spans(find_boilerplate(document))
    assert all("Example Course" not in s.text for s in spans)


def test_unmapped_glyph_markers_become_spaces():
    # (cid:561) stands in for a space inside a run pdfplumber reads as one
    # word, so removing it outright would weld the words together instead.
    from recall.ingestion.pdf import strip_cid_glyphs

    assert (
        strip_cid_glyphs("Example(cid:561)1:(cid:561)Peering(cid:561)and(cid:561)pricing")
        == "Example 1: Peering and pricing"
    )


def test_a_glyph_marker_standing_alone_leaves_nothing_behind():
    from recall.ingestion.pdf import strip_cid_glyphs

    assert strip_cid_glyphs("(cid:12)") == ""
    assert strip_cid_glyphs("CNN (cid:111) eyeballs") == "CNN eyeballs"


def test_ordinary_text_and_real_parentheses_are_untouched():
    from recall.ingestion.pdf import strip_cid_glyphs

    assert strip_cid_glyphs("queue (aka buffer) preceding a link") == (
        "queue (aka buffer) preceding a link"
    )
    assert strip_cid_glyphs("RFC (cid) 2616") == "RFC (cid) 2616"


def test_a_word_that_is_only_a_glyph_marker_is_dropped():
    from recall.ingestion.pdf import _clean_words

    words = [
        {"text": "So", "size": 12.0, "top": 1.0, "x0": 0.0},
        {"text": "(cid:12)", "size": 12.0, "top": 1.0, "x0": 10.0},
        {"text": "both", "size": 12.0, "top": 1.0, "x0": 20.0},
    ]
    assert [w["text"] for w in _clean_words(words)] == ["So", "both"]


def test_cleaning_a_glyph_marker_restores_the_title_body_match():
    """The reason this is cleaned at load rather than at chunk time.

    An uncleaned marker leaves the body copy of a title different from the
    title, so the chunkers' title-stripping stops matching and both survive.
    """
    from recall.ingestion.pdf import _clean_words
    from recall.ingestion.structure import comparable

    title = "Example 1: Peering and pricing"
    body = _clean_words([{"text": "Example(cid:561)1:(cid:561)Peering(cid:561)and(cid:561)pricing"}])
    assert comparable(body[0]["text"]) == comparable(title)
