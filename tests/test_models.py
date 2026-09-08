from recall.ingestion.models import DECK, PROBLEM_SHEET, STRUCTURAL, SYLLABUS, WINDOW, Chunk, Locator


def test_cite_renders_a_slide_range_as_a_range():
    assert Locator(DECK, (24, 25, 26, 27), title="Web caching").cite() == 'slides 24–27 — "Web caching"'


def test_cite_renders_a_single_slide_in_the_singular():
    assert Locator(DECK, (6,), title="Queueing").cite() == 'slide 6 — "Queueing"'


def test_cite_lists_non_contiguous_pages_rather_than_implying_a_range():
    # A run merged across a text-less page must not claim the pages between.
    assert Locator(DECK, (2, 4), title="Caching").cite() == 'slides 2, 4 — "Caching"'


def test_cite_renders_problems_and_sections():
    assert Locator(PROBLEM_SHEET, (1,), problem="4", parts=("a", "b")).cite() == "p.1, problem 4(a, b)"
    assert Locator(SYLLABUS, (2,), title="GRADING").cite() == "p.2 — GRADING"
    assert Locator(WINDOW, (3, 4)).cite() == "pp.3–4"


def _chunk(**overrides):
    kwargs = dict(
        source_file="deck.pdf",
        source_sha256="abc",
        doc_type=DECK,
        chunker=STRUCTURAL,
        locator=Locator(DECK, (1,), title="T"),
        text="T\n\nbody text here",
        raw_text="body text here",
    )
    kwargs.update(overrides)
    return Chunk.make(**kwargs)


def test_chunk_id_is_deterministic():
    assert _chunk().chunk_id == _chunk().chunk_id


def test_chunk_id_changes_with_content_and_location():
    base = _chunk()
    assert _chunk(raw_text="different body").chunk_id != base.chunk_id
    assert _chunk(locator=Locator(DECK, (2,), title="T")).chunk_id != base.chunk_id


def test_counts_measure_raw_text_not_the_prefix():
    chunk = _chunk()
    assert chunk.n_words == 3
    assert chunk.n_chars == len("body text here")


def test_roundtrips_through_json_dict():
    chunk = _chunk()
    assert Chunk.from_dict(chunk.to_dict()) == chunk


def test_citation_combines_file_and_locator():
    assert _chunk().citation() == 'deck.pdf, slide 1 — "T"'
