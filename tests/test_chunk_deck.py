from recall.ingestion.boilerplate import find_boilerplate
from recall.ingestion.chunkers.deck import chunk_deck
from recall.ingestion.pdf import load


def _chunks(path, **kwargs):
    document = load(path)
    return chunk_deck(document, find_boilerplate(document), **kwargs)


def test_consecutive_same_title_slides_merge_into_one_chunk(deck_path):
    merged = [c for c in _chunks(deck_path) if c.locator.pages == (2, 3, 4)]
    assert len(merged) == 1
    assert merged[0].locator.title == "Web caching"
    assert "Hit ratio" in merged[0].raw_text
    assert "Conditional GET" in merged[0].raw_text


def test_a_continuation_marker_does_not_start_a_new_chunk(deck_path):
    # Slide 4 is titled "Web caching (cont.)" and belongs with slides 2-3.
    assert not any(c.locator.pages == (4,) for c in _chunks(deck_path))


def test_the_same_title_recurring_non_adjacently_stays_separate(deck_path):
    caching = [c for c in _chunks(deck_path) if c.locator.title and "Web caching" in c.locator.title]
    assert sorted(c.locator.pages for c in caching) == [(2, 3, 4), (7,)]


def test_a_title_change_closes_the_chunk(deck_path):
    titles = [c.locator.title for c in _chunks(deck_path)]
    assert titles == ["Introduction", "Web caching", "Routing", "Web caching", "Summary"]


def test_text_less_pages_produce_no_chunk(deck_path):
    assert all(5 not in c.locator.pages for c in _chunks(deck_path))


def test_boilerplate_is_stripped_from_chunk_text(deck_path):
    assert all("Example Course" not in c.text for c in _chunks(deck_path))


def test_the_title_prefixes_text_but_not_raw_text(deck_path):
    chunk = next(c for c in _chunks(deck_path) if c.locator.pages == (2, 3, 4))
    assert chunk.text.startswith("example deck — Web caching")
    assert "Web caching" not in chunk.raw_text
    assert chunk.raw_text in chunk.text


def test_the_size_cap_splits_an_over_long_run(deck_path):
    capped = [c for c in _chunks(deck_path, max_words=4) if c.locator.title == "Web caching"]
    assert len(capped) > 2  # the 3-slide run no longer fits in one chunk


def test_a_title_only_divider_slide_produces_no_chunk(deck_path):
    # Slide 9 is a title over a diagram: it would match a query and answer nothing.
    assert all(9 not in c.locator.pages for c in _chunks(deck_path))


def test_bare_slide_numbers_do_not_reach_chunk_text(deck_path):
    assert all(line.strip() != "2" for c in _chunks(deck_path) for line in c.raw_text.splitlines())


def test_the_title_is_stripped_from_the_body_despite_punctuation_differences(deck_path):
    # The fixture's slide 6 body repeats its title with different quoting.
    routing = next(c for c in _chunks(deck_path) if c.locator.title == "Routing")
    assert "Hot potato routing hands traffic off early" in routing.raw_text
