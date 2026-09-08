import pytest

from recall.ingestion.structure import all_caps_headings, normalise_title, numbered_items, subpart_labels


@pytest.mark.parametrize(
    "title",
    [
        "Cookies: keeping state (cont.)",
        "Cookies: keeping state (cont)",
        "Cookies: keeping state (continued)",
        "Cookies: keeping state cont.",
        "COOKIES: KEEPING STATE",
        "Cookies:   keeping  state",
    ],
)
def test_continuation_and_case_variants_normalise_together(title):
    assert normalise_title(title) == normalise_title("Cookies: keeping state")


def test_distinct_titles_stay_distinct():
    assert normalise_title("Web caching") != normalise_title("Routing")


def test_missing_title_normalises_to_empty():
    assert normalise_title(None) == ""


def test_numbered_items_requires_a_sequential_run():
    lines = ["1. first", "2. second", "7. out of sequence", "3. third"]
    assert numbered_items(lines) == [(0, 1), (1, 2), (3, 3)]


def test_incidental_digits_in_prose_are_not_problem_numbers():
    # "3 MB" and "Layer 4" appear in the real sheets; neither opens a problem.
    lines = ["1. A link carries 3 MB of data", "Layer 4 is the transport layer", "2. next"]
    assert numbered_items(lines) == [(0, 1), (2, 2)]


def test_numbering_that_never_starts_at_one_yields_nothing():
    assert numbered_items(["4. four", "5. five"]) == []


def test_all_caps_headings_ignores_short_and_mixed_case_lines():
    lines = ["INSTRUCTOR", "Office hours", "OK", "COURSE ORGANIZATION", "2025"]
    assert all_caps_headings(lines) == ["INSTRUCTOR", "COURSE ORGANIZATION"]


def test_subpart_labels_reads_letter_parts():
    assert subpart_labels(["a) first part", "b) second part", "text"]) == ["a", "b"]
