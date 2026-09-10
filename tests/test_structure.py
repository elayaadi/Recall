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


class TestLabelledProblems:
    """SPEC.md 2b, amended after the 8a swap: an explicit label beats a bare digit.

    CS447's sheets number problems as a bare "1."; MIT 6.02's write "Problem 1."
    *and* use bare "1. 2. 3." for sub-questions inside a problem. Reading the
    bare form first put every boundary inside problem 1.
    """

    def test_an_explicit_label_wins_over_bare_sub_questions(self):
        lines = [
            "Problem 1. Information",
            "Answer each of the following:",
            "1. The Bofa alone?",
            "2. Yertle alone?",
            "3. All of them together?",
            "Problem 2. Huffman coding",
            "Explain your reasoning.",
        ]
        assert numbered_items(lines) == [(0, 1), (5, 2)]

    def test_a_heading_may_end_the_line(self):
        """Most 6.02 headings are a bare 'Problem 3.' with nothing after it."""
        assert numbered_items(["Problem 1.", "text", "Problem 2.", "more"]) == [(0, 1), (2, 2)]

    def test_labelled_numbering_need_not_start_at_one_or_be_contiguous(self):
        """ps9 starts at Problem 0 and skips 7; demanding 1..N rejected the sheet."""
        lines = ["Problem 0.", "a", "Problem 1.", "b", "Problem 6.", "c", "Problem 8.", "d"]
        assert numbered_items(lines) == [(0, 0), (2, 1), (4, 6), (6, 8)]

    def test_a_repeated_header_is_not_a_second_problem(self):
        lines = ["Problem 1.", "body", "Problem 1.", "continued", "Problem 2.", "next"]
        assert numbered_items(lines) == [(0, 1), (4, 2)]

    def test_the_bare_form_still_works_when_there_is_no_label(self):
        """CS447's sheets carry no 'Problem N' heading at all — 0 across 6 files."""
        lines = ["1. Compute the delay", "2. Compute the loss", "3. Explain why"]
        assert numbered_items(lines) == [(0, 1), (1, 2), (2, 3)]

    def test_a_single_label_does_not_override_the_bare_form(self):
        """One stray match is not a numbering convention."""
        lines = ["See Problem 4 for context", "1. First", "2. Second", "3. Third"]
        assert [n for _, n in numbered_items(lines)] == [1, 2, 3]

    def test_prose_digits_are_still_not_problem_headers(self):
        assert numbered_items(["The link carries 3 MB", "Layer 4 handles this"]) == []
