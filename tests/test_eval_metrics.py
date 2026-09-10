"""Metrics, asserted against arithmetic worked out by hand.

This is the one place in the repo where tests must check numbers rather than
behaviour. A metric that is subtly wrong — off by one in a rank, dividing by the
relevant items *found* instead of the relevant items that *exist* — produces
plausible figures forever, and every downstream comparison inherits the error
without ever looking wrong.
"""

from __future__ import annotations

import pytest

from eval.metrics import (
    Case,
    abstention,
    average_precision,
    citation_correctness,
    mean_average_precision,
    outcome_mix,
    recall_at_k,
    score,
)

R = frozenset


class TestRecallAtK:
    def test_all_relevant_inside_k(self):
        assert recall_at_k(R({"a", "b"}), ("a", "b", "c"), 5) == 1.0

    def test_half_the_relevant_inside_k(self):
        assert recall_at_k(R({"a", "b"}), ("a", "x", "y"), 5) == 0.5

    def test_k_truncates_the_list(self):
        """b sits at rank 3, so recall@2 must not see it."""
        assert recall_at_k(R({"a", "b"}), ("a", "x", "b"), 2) == 0.5
        assert recall_at_k(R({"a", "b"}), ("a", "x", "b"), 3) == 1.0

    def test_nothing_relevant_retrieved(self):
        assert recall_at_k(R({"a"}), ("x", "y"), 5) == 0.0

    def test_no_relevant_set_is_unmeasured_not_zero(self):
        """An unanswerable question has no recall; averaging a 0 in would lie."""
        assert recall_at_k(R(), ("a", "b"), 5) is None


class TestAveragePrecision:
    def test_both_relevant_at_the_top(self):
        # hits at ranks 1 and 2: (1/1 + 2/2) / 2 = 1.0
        assert average_precision(R({"a", "b"}), ("a", "b", "c")) == 1.0

    def test_rank_matters(self):
        # relevant {a,b}; a at rank 1, b at rank 3: (1/1 + 2/3) / 2 = 0.8333...
        assert average_precision(R({"a", "b"}), ("a", "x", "b")) == pytest.approx(5 / 6)

    def test_one_relevant_at_rank_two(self):
        # (1/2) / 1 = 0.5
        assert average_precision(R({"a"}), ("x", "a", "y")) == 0.5

    def test_a_missed_relevant_chunk_costs_the_score(self):
        """Divided by |relevant|, not by how many were found.

        Found-only division would score this 1.0 and reward a system that
        retrieves one of three right answers perfectly.
        """
        assert average_precision(R({"a", "b", "c"}), ("a",)) == pytest.approx(1 / 3)

    def test_nothing_retrieved(self):
        assert average_precision(R({"a"}), ()) == 0.0

    def test_no_relevant_set_is_unmeasured(self):
        assert average_precision(R(), ("a",)) is None


class TestMeanAveragePrecision:
    def test_unanswerable_cases_are_excluded_not_zeroed(self):
        cases = [
            Case("q1", R({"a"}), ("a",)),                       # AP 1.0
            Case("q2", R(), (), abstained=True, answerable=False),  # excluded
        ]
        assert mean_average_precision(cases) == 1.0

    def test_the_mean_is_over_answerable_questions_only(self):
        cases = [
            Case("q1", R({"a"}), ("a",)),        # 1.0
            Case("q2", R({"b"}), ("x", "b")),    # 0.5
            Case("q3", R(), (), answerable=False),
        ]
        assert mean_average_precision(cases) == 0.75


class TestAbstention:
    def test_a_perfect_split(self):
        cases = [
            Case("a1", R({"x"}), ("x",), abstained=False, answerable=True),
            Case("u1", R(), (), abstained=True, answerable=False),
        ]
        a = abstention(cases)
        assert (a.true_positive, a.false_positive, a.false_negative, a.true_negative) == (1, 0, 0, 1)
        assert a.precision == 1.0 and a.recall == 1.0

    def test_refusing_an_answerable_question_is_a_false_positive(self):
        a = abstention([Case("a1", R({"x"}), (), abstained=True, answerable=True)])
        assert a.false_positive == 1
        assert a.precision == 0.0
        assert a.recall is None  # nothing unanswerable to recall

    def test_answering_an_unanswerable_question_is_a_false_negative(self):
        a = abstention([Case("u1", R(), ("x",), abstained=False, answerable=False)])
        assert a.false_negative == 1
        assert a.recall == 0.0
        assert a.precision is None  # it never abstained

    def test_precision_and_recall_over_a_mixed_run(self):
        cases = (
            [Case(f"u{i}", R(), (), abstained=True, answerable=False) for i in range(3)]
            + [Case("u3", R(), ("x",), abstained=False, answerable=False)]
            + [Case("a0", R({"x"}), (), abstained=True, answerable=True)]
            + [Case(f"a{i}", R({"x"}), ("x",), abstained=False) for i in range(1, 3)]
        )
        a = abstention(cases)
        assert (a.true_positive, a.false_positive, a.false_negative) == (3, 1, 1)
        assert a.precision == 0.75          # 3 of 4 refusals were right
        assert a.recall == 0.75             # 3 of 4 unanswerable were refused


class TestCitationCorrectness:
    def test_every_cited_chunk_is_relevant(self):
        assert citation_correctness([Case("q", R({"a", "b"}), cited=R({"a"}))]) == 1.0

    def test_a_cited_chunk_outside_the_gold_set(self):
        assert citation_correctness([Case("q", R({"a"}), cited=R({"a", "z"}))]) == 0.5

    def test_runs_with_no_citations_are_unmeasured(self):
        assert citation_correctness([Case("q", R({"a"}))]) is None


def test_outcome_mix_counts_each_outcome():
    cases = [Case("1", outcome="answered"), Case("2", outcome="answered"),
             Case("3", outcome="no_passages")]
    assert outcome_mix(cases) == {"answered": 2, "no_passages": 1}


class TestReport:
    def test_the_per_format_breakdown_separates_a_weak_branch(self):
        """6b's reason for the breakdown: a weak format must not hide in the mean."""
        cases = [
            Case("d1", R({"a"}), ("a",)),
            Case("d2", R({"b"}), ("b",)),
            Case("p1", R({"c"}), ("x",)),
        ]
        formats = {"d1": "deck", "d2": "deck", "p1": "problem_sheet"}
        report = score(cases, formats, k_values=(1,))

        assert report.recall[1] == pytest.approx(2 / 3)     # headline hides it
        assert report.by_format["deck"]["recall@1"] == 1.0
        assert report.by_format["problem_sheet"]["recall@1"] == 0.0

    def test_the_report_serialises_every_figure(self):
        d = score([Case("q", R({"a"}), ("a",))], k_values=(1,)).to_dict()
        assert d["recall"]["@1"] == 1.0
        assert d["questions"] == 1
        assert set(d["abstention"]) >= {"precision", "recall", "tp", "fp", "fn", "tn"}
