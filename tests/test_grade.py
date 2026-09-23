"""Tests for ``eval/grade.py``.

No network, no model call, no credential. The grader is validated the way the
grader validates a run: by feeding it the answer key itself, which is by
definition a perfect set of rulings, and requiring a perfect score. Every check
that follows either confirms that, or proves one specific way of getting the
grading wrong.

Three of those ways are the point of the module, and each has its own group
below:

* grading on ``ruling`` and ``amount_sgd`` alone, which passes case 207 while a
  rider goes unreimbursed;
* comparing money in binary floating point, which calls the key's own 4.8
  unequal to 4.8;
* treating ``null`` and ``0`` as the same answer.
"""

import ast
import json
import re
import tokenize
import unittest
from decimal import Decimal
from pathlib import Path

from eval import grade
from tribunal import loader, money

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRADE_SOURCE = PROJECT_ROOT / "eval" / "grade.py"
TRIBUNAL_DIR = PROJECT_ROOT / "tribunal"

# The four cases whose rulings carry a referral, and the clause reference each
# leads with. Recorded here as facts about the corpus, not as a specification of
# the grader: the grader reads them out of the key.
REFERRAL_CASES = (105, 115, 201, 207)
REFERRAL_CLAUSES = {
    105: "POL-RD-06",
    115: "POL-RD-09",
    201: "POL-NS-05",
    207: "POL-NS-07",
}

# The perturbation target. Case 101 is a PARTIAL_REFUND carrying money and no
# referral, so a single-field change to it cannot disturb the escalation counts.
PERTURBATION_CASE = 101

# A referral that is well formed but that case 101 does not carry.
SPURIOUS_REFERRAL = "POL-RD-09(4) billing integrity"


def _key():
    return grade.load_answer_key()


def _produced_from_key(key):
    return grade.key_as_produced(key)


def _perturbed(key, case_no, field, value):
    """The key's own rulings with exactly one field of one case replaced."""
    produced = grade.key_as_produced(key)
    produced[case_no]["ruling"][field] = value
    return produced


class VocabularyTests(unittest.TestCase):
    """The ruling vocabulary comes from the policy, not from this repository."""

    def test_the_five_values_come_from_pol_gen_03(self):
        values = grade.ruling_values()
        self.assertEqual(len(values), 5)
        self.assertEqual(
            set(values),
            {
                "NO_ACTION",
                "PARTIAL_REFUND",
                "FULL_REFUND",
                "DRIVER_COMPENSATION",
                "ESCALATE",
            },
        )

    def test_the_general_policy_is_the_same_for_both_categories(self):
        # ``grade.py`` loads the general policy through one category. That is
        # only sound while the general document is category-independent, which
        # is a fact about the policy rather than an assumption to be trusted.
        first = loader.load_policies("ROUTE_DEVIATION")["general"]
        second = loader.load_policies("NO_SHOW_CHARGE")["general"]
        self.assertEqual(
            money.dumps_canonical(first), money.dumps_canonical(second)
        )

    def test_every_expected_ruling_is_in_the_vocabulary(self):
        vocabulary = set(grade.ruling_values())
        for case_no, expected in _key().items():
            with self.subTest(case=case_no):
                self.assertIn(expected.ruling, vocabulary)


class MoneyComparisonTests(unittest.TestCase):
    """Money compares as ``Decimal``, and ``null`` is not zero."""

    def test_the_four_eighty_case(self):
        """The key's own 4.8 is already unequal to the Python literal 4.8.

        This is the trap the whole money path exists to avoid, asserted rather
        than described: a grader comparing ``Decimal`` with the float a plain
        ``json.load`` would hand it is wrong on the key itself.
        """
        key = _key()
        self.assertEqual(key[202].amount_sgd, Decimal("4.8"))
        self.assertNotEqual(Decimal("4.8"), 4.8)
        # Through the grader's conversion the same comparison is correct.
        self.assertTrue(grade.compare_money(Decimal("4.8"), 4.8))
        self.assertEqual(grade.money_or_none(4.8), Decimal("4.8"))

    def test_a_binary_artefact_is_still_a_different_amount(self):
        # 4.800000000000001 is not 4.8. Converting through ``str`` must not
        # round it into agreement.
        self.assertFalse(
            grade.compare_money(Decimal("4.8"), Decimal("4.800000000000001"))
        )

    def test_null_and_zero_are_different_answers(self):
        self.assertFalse(grade.compare_money(None, Decimal("0")))
        self.assertFalse(grade.compare_money(None, 0))
        self.assertFalse(grade.compare_money(Decimal("0"), None))
        self.assertFalse(grade.compare_money(0, None))

    def test_null_matches_only_null(self):
        self.assertTrue(grade.compare_money(None, None))

    def test_zero_and_zero_point_zero_zero_are_the_same_number(self):
        self.assertTrue(grade.compare_money(Decimal("0"), Decimal("0.00")))

    def test_an_integer_and_a_decimal_are_the_same_amount(self):
        self.assertTrue(grade.compare_money(Decimal("4.0"), 4))
        self.assertTrue(grade.compare_money(4, Decimal("4.00")))

    def test_a_boolean_is_not_the_number_one(self):
        self.assertFalse(grade.compare_money(Decimal("1"), True))
        self.assertIs(grade.money_or_none(True), grade.UNPARSEABLE)

    def test_an_unparseable_value_never_compares_equal(self):
        self.assertFalse(grade.compare_money(Decimal("4.0"), "four"))
        self.assertFalse(grade.compare_money(Decimal("4.0"), [4]))
        self.assertFalse(grade.compare_money(Decimal("4.0"), ""))
        self.assertFalse(grade.compare_money(None, "four"))

    def test_a_non_finite_decimal_is_not_an_amount(self):
        self.assertIs(grade.money_or_none(Decimal("NaN")), grade.UNPARSEABLE)
        self.assertIs(grade.money_or_none(Decimal("Infinity")), grade.UNPARSEABLE)

    def test_the_module_never_names_float(self):
        """``float`` must not appear as a name anywhere in the grader.

        Not as a call and not as a type test. Everything goes through
        ``Decimal(str(value))``, which is also how a caller's plain ``json.load``
        output stays correct without the grader ever touching a binary value.
        """
        with GRADE_SOURCE.open("rb") as handle:
            names = {
                token.string
                for token in tokenize.tokenize(handle.readline)
                if token.type == tokenize.NAME
            }
        self.assertNotIn("float", names)

    def test_money_conversion_is_reported_when_the_type_is_wrong(self):
        # A string amount compares on its value, but the type violation is
        # surfaced rather than hidden.
        self.assertIsNone(grade.money_type_note(Decimal("4.0")))
        self.assertIsNone(grade.money_type_note(None))
        self.assertIn("string", grade.money_type_note("4.0"))
        self.assertIn("boolean", grade.money_type_note(True))


class ReferralKeyTests(unittest.TestCase):
    """A referral is read for the clause reference it carries."""

    def test_the_key_leads_with_a_clause_and_its_limb(self):
        self.assertEqual(
            grade.referral_keys("POL-RD-06(c) driver-conduct review"),
            (grade.ReferralKey("POL-RD-06", "c"),),
        )
        self.assertEqual(
            grade.referral_keys("POL-NS-05(ii) false-arrival event recorded"),
            (grade.ReferralKey("POL-NS-05", "ii"),),
        )

    def test_a_referral_without_a_limb_has_none(self):
        self.assertEqual(
            grade.referral_keys(
                "POL-NS-07 escalation packet: instruct the reviewer to refund "
                "the rider's SGD 4.00 cancellation fee in full"
            ),
            (grade.ReferralKey("POL-NS-07", None),),
        )

    def test_a_limb_is_only_read_when_it_is_adjacent(self):
        # "(see also ...)" is prose, not a limb, and must not be read as one.
        self.assertEqual(
            grade.referral_keys("POL-NS-07 (see also POL-NS-09(d))"),
            (grade.ReferralKey("POL-NS-07", None), grade.ReferralKey("POL-NS-09", "d")),
        )

    def test_a_limb_is_normalised_to_lower_case(self):
        self.assertEqual(grade.referral_keys("POL-RD-06(C)")[0].limb, "c")

    def test_a_referral_naming_no_clause_yields_no_keys(self):
        self.assertEqual(grade.referral_keys("refer to a human reviewer"), ())

    def test_a_referral_naming_two_clauses_yields_two_keys(self):
        keys = grade.referral_keys("POL-RD-06(c) and POL-RD-09(4)")
        self.assertEqual(len(keys), 2)
        self.assertEqual(keys[0], grade.ReferralKey("POL-RD-06", "c"))
        self.assertEqual(keys[1], grade.ReferralKey("POL-RD-09", "4"))

    def test_every_referral_in_the_key_carries_a_clause(self):
        for case_no, expected in _key().items():
            for referral in expected.referrals:
                with self.subTest(case=case_no):
                    self.assertTrue(grade.referral_keys(referral))

    def test_the_key_leads_with_the_expected_clause(self):
        key = _key()
        for case_no, clause in REFERRAL_CLAUSES.items():
            with self.subTest(case=case_no):
                keys = grade.referral_keys_of(key[case_no].referrals)
                self.assertTrue(keys)
                self.assertEqual(keys[0].clause, clause)


class ReferralMatchingTests(unittest.TestCase):
    """Referrals are graded by clause reference, and a spurious one fails too."""

    def test_the_limb_must_match_where_the_key_states_one(self):
        match = grade.match_referrals(
            ["POL-RD-06(c) driver-conduct review"],
            ["POL-RD-06(b) driver-conduct review"],
        )
        self.assertFalse(match.matched)
        self.assertEqual(
            match.unmatched_expected, (grade.ReferralKey("POL-RD-06", "c"),)
        )

    def test_a_limb_is_ignored_where_the_key_states_none(self):
        match = grade.match_referrals(
            ["POL-NS-07 escalation packet"],
            ["POL-NS-07(d) escalation packet"],
        )
        self.assertTrue(match.matched)

    def test_order_does_not_matter(self):
        match = grade.match_referrals(
            ["POL-RD-06(c) first", "POL-RD-09(4) second"],
            ["POL-RD-09(4) second", "POL-RD-06(c) first"],
        )
        self.assertTrue(match.matched)

    def test_an_empty_expected_set_requires_an_empty_produced_set(self):
        # The one direction that stays strict under the recall rule. A referral
        # sends a case to a human, so manufacturing one where the key expects
        # none is a defect in the same way that dropping one is.
        self.assertTrue(grade.match_referrals([], []).matched)
        spurious = grade.match_referrals([], [SPURIOUS_REFERRAL])
        self.assertFalse(spurious.matched)
        self.assertEqual(
            spurious.unmatched_produced, (grade.ReferralKey("POL-RD-09", "4"),)
        )
        self.assertEqual(spurious.expected_matched, 0)
        self.assertIn("where the key expects none", spurious.detail)

    def test_a_missing_referral_fails(self):
        match = grade.match_referrals(["POL-NS-07 escalation packet"], [])
        self.assertFalse(match.matched)
        self.assertEqual(
            match.unmatched_expected, (grade.ReferralKey("POL-NS-07", None),)
        )
        # The two counts the report prints per case: none of the expected
        # clauses were reached, and nothing was offered beyond them.
        self.assertEqual(match.expected_matched, 0)
        self.assertEqual(match.additional_clauses, ())
        self.assertIn("expected referral not produced", match.detail)

    def test_a_repeated_produced_clause_is_a_repeat_not_an_addition(self):
        # Every expected clause was reached, so the field passes: the test is
        # whether the key's clauses were reached, not whether the produced set
        # is the same size. Until 2026-09-22 this was a failure, which is what
        # made a correct answer to case 207 score as a MISS.
        match = grade.match_referrals(
            ["POL-RD-06(c) review"],
            ["POL-RD-06(c) review", "POL-RD-06(c) review again"],
        )
        self.assertTrue(match.matched)
        self.assertEqual(match.expected_matched, 1)
        # One reference is left over after matching ...
        self.assertEqual(len(match.unmatched_produced), 1)
        # ... but it is the same clause again, not a clause the key omits, so
        # it is not reported as an addition. Calling it one would tell a reader
        # the model raised something the key had not.
        self.assertEqual(match.additional_clauses, ())
        self.assertEqual(match.additions, "")

    def test_an_expected_clause_reached_with_an_extra_clause_matches(self):
        match = grade.match_referrals(
            ["POL-NS-07 escalation packet"],
            ["POL-NS-07 escalation packet", "POL-NS-09(d) anti-farming review"],
        )
        self.assertTrue(match.matched)
        self.assertEqual(match.expected_matched, 1)
        self.assertEqual(
            match.additional_clauses, (grade.ReferralKey("POL-NS-09", "d"),)
        )
        # A passing case still has something to say: the addition is named.
        self.assertIn("additional clause(s) offered", match.additions)
        self.assertIn("POL-NS-09(d)", match.additions)
        # ... and a passing case has no failure detail to print.
        self.assertEqual(match.detail, "")

    def test_the_extra_clause_does_not_make_a_missing_expected_clause_pass(self):
        # The loosening is one-directional: an addition cannot stand in for a
        # clause the key asked for and did not get.
        match = grade.match_referrals(
            ["POL-NS-07 escalation packet"],
            ["POL-NS-09(d) anti-farming review"],
        )
        self.assertFalse(match.matched)
        self.assertEqual(match.expected_matched, 0)
        self.assertIn("expected referral not produced", match.detail)
        self.assertIn("POL-NS-07", match.detail)

    def test_the_answer_that_was_scored_a_miss_on_case_207_now_matches(self):
        # The defect, as a regression test. This is what deepseek-flash
        # returned on case 207 -- the quote elides the middle of the second
        # sentence, so the clause references shown are the ones to check.
        # It names POL-NS-07, which the key requires, and POL-NS-09(d), the
        # fuller legal path the key's own rationale for that case describes.
        # Exact set equality scored it a MISS on referrals; recall does not.
        produced = (
            "Escalation packet (POL-NS-09(d), reached via the POL-NS-07 "
            "anti-farming check): direct the human reviewer to refund the "
            "rider's SGD 4.00 cancellation fee in full, per POL-NS-07; ... "
            "Human review should also examine DRV-01948's trailing-30-day "
            "no-show termination pattern (7 terminations across 61 completed "
            "trips, 11.5%)."
        )
        key = _key()
        match = grade.match_referrals(key[207].referrals, [produced])
        self.assertTrue(match.matched)
        self.assertEqual(match.expected_matched, 1)
        self.assertEqual(
            match.additional_clauses, (grade.ReferralKey("POL-NS-09", "d"),)
        )

    def test_a_referral_naming_no_clause_cannot_be_matched(self):
        match = grade.match_referrals([], ["send this to a human reviewer"])
        self.assertFalse(match.matched)
        self.assertTrue(match.keyless_produced)

    def test_the_substance_may_differ_while_the_clause_matches(self):
        # The clause match is the automatic signal. Whether the substance
        # matches is a judgement a person makes from the two texts, which the
        # report prints side by side.
        match = grade.match_referrals(
            ["POL-NS-05(ii) false-arrival event recorded against the driver"],
            ["POL-NS-05(ii) please log a false arrival against the driver now"],
        )
        self.assertTrue(match.matched)


class ReferralFieldScoringTests(unittest.TestCase):
    """The recall rule as it reaches the graded field, not just the matcher.

    Four behaviours, each named because each is a way of getting the field
    wrong: reaching every expected clause and adding one must pass, missing an
    expected clause must fail, producing one where none is expected must fail,
    and the answer that was scored a MISS on case 207 must pass.
    """

    def setUp(self):
        self.key = _key()

    def _report_with(self, case_no, referrals):
        """The key graded against itself, with one case's referrals replaced."""
        produced = grade.key_as_produced(self.key)
        produced[case_no]["ruling"]["referrals"] = list(referrals)
        return grade.grade(produced, self.key)

    def _score(self, report, case_no):
        return next(score for score in report.cases if score.case_no == case_no)

    def test_every_expected_clause_plus_one_extra_is_a_correct_field(self):
        report = self._report_with(
            207,
            [
                "POL-NS-07 escalation packet: refund the rider's SGD 4.00 "
                "cancellation fee in full; POL-NS-09(d) is the fuller path"
            ],
        )
        score = self._score(report, 207)
        self.assertTrue(score.correct_on("referrals"))
        self.assertEqual(score.failed_fields, ())
        # An addition is not a defect, so the run is still perfect.
        self.assertEqual(report.exact_matches, report.total)

    def test_the_extra_clause_is_named_even_though_the_field_passed(self):
        report = self._report_with(
            207,
            [
                "POL-NS-07 escalation packet: refund the rider's SGD 4.00 "
                "cancellation fee in full; POL-NS-09(d) is the fuller path"
            ],
        )
        text = grade.render_report(report)
        self.assertIn("expected clauses matched: 1 of 1", text)
        self.assertIn("additional clauses offered: POL-NS-09(d)", text)

    def test_a_referral_missing_an_expected_clause_still_fails(self):
        report = self._report_with(207, ["POL-NS-09(d) anti-farming review"])
        score = self._score(report, 207)
        self.assertFalse(score.correct_on("referrals"))
        self.assertEqual(score.failed_fields, ("referrals",))
        self.assertIn(
            "expected referral not produced: POL-NS-07",
            score.by_field["referrals"].detail,
        )
        self.assertEqual(report.exact_matches, report.total - 1)

    def test_a_referral_produced_where_none_is_expected_still_fails(self):
        report = self._report_with(PERTURBATION_CASE, [SPURIOUS_REFERRAL])
        score = self._score(report, PERTURBATION_CASE)
        self.assertFalse(score.correct_on("referrals"))
        self.assertEqual(score.failed_fields, ("referrals",))
        self.assertIn("where the key expects none", score.by_field["referrals"].detail)
        self.assertEqual(report.exact_matches, report.total - 1)

    def test_the_case_207_answer_that_was_scored_a_miss_is_now_correct(self):
        produced_text = (
            "Escalation packet (POL-NS-09(d), reached via the POL-NS-07 "
            "anti-farming check): direct the human reviewer to refund the "
            "rider's SGD 4.00 cancellation fee in full, per POL-NS-07; ... "
            "Human review should also examine DRV-01948's trailing-30-day "
            "no-show termination pattern (7 terminations across 61 completed "
            "trips, 11.5%)."
        )
        report = self._report_with(207, [produced_text])
        self.assertTrue(self._score(report, 207).correct_on("referrals"))
        self.assertEqual(report.exact_matches, report.total)


class SubsetCalibrationTests(unittest.TestCase):
    """A rate on a hand-picked subset is not comparable to the corpus base rate.

    Every rate in the calibration block moves with the base rate of whatever set
    was graded, precision and recall included. Only the raw counts survive
    subsetting intact, so on a subset the target is withheld and the counts are
    printed instead. On the whole corpus the block is as it always was.
    """

    def setUp(self):
        self.key = _key()

    def _subset_report(self, cases):
        produced = grade.key_as_produced(self.key)
        subset = {case_no: self.key[case_no] for case_no in cases}
        return grade.grade(
            {case_no: produced[case_no] for case_no in cases},
            subset,
            corpus=self.key,
        )

    def _full_report(self):
        return grade.grade(grade.key_as_produced(self.key), self.key)

    def test_the_whole_corpus_is_recognised_as_the_whole_corpus(self):
        report = self._full_report()
        self.assertTrue(report.grades_full_corpus)
        self.assertEqual(report.corpus_size, 29)
        self.assertEqual(report.graded_cases, tuple(sorted(self.key)))

    def test_a_subset_is_not_the_whole_corpus(self):
        report = self._subset_report((110, 207, 213))
        self.assertFalse(report.grades_full_corpus)
        self.assertEqual(report.total, 3)
        self.assertEqual(report.corpus_size, 29)
        self.assertEqual(report.graded_cases, (110, 207, 213))

    def test_an_unknown_corpus_never_reads_as_the_whole_corpus(self):
        # A comparability claim that cannot be established must not read as
        # established -- the same rule the runner applies to a working tree it
        # could not read.
        report = grade.GradeReport((), grade.calibrate(()))
        self.assertEqual(report.corpus_cases, ())
        self.assertFalse(report.grades_full_corpus)

    @staticmethod
    def _calibration_section(text):
        """The escalation block alone, so a check cannot hit unrelated prose.

        The closing "How this was checked" paragraph mentions the self-test's
        own 17.2% rate, which is a fact about the test suite rather than a
        target printed beside a run's rate. Slicing the block keeps that
        paragraph out of the assertion.
        """
        start = text.index("## Escalation calibration")
        end = text.index("## How this was checked")
        return text[start:end]

    def test_a_full_grading_prints_the_target_and_a_subset_does_not(self):
        full = self._calibration_section(grade.render_report(self._full_report()))
        self.assertIn("| Target | 17.2% |", full)
        self.assertNotIn("not comparable to the corpus base rate", full)

        subset = self._calibration_section(
            grade.render_report(self._subset_report((110, 207, 213)))
        )
        self.assertNotIn("17.2%", subset)
        self.assertNotIn("| Target |", subset)
        self.assertIn("not comparable to the corpus base rate", subset)

    def test_a_subset_states_which_cases_were_graded(self):
        text = grade.render_report(self._subset_report((110, 207, 213)))
        self.assertIn("Cases graded, by number | 110, 207, 213", text)
        self.assertIn("Whole corpus graded | no — 3 of 29 cases", text)

    def test_a_subset_prints_the_raw_counts_with_the_cases_behind_them(self):
        text = grade.render_report(self._subset_report((110, 207, 213)))
        for label in (
            "True positives (key and run both ESCALATE)",
            "False positives (run ESCALATE, key does not)",
            "False negatives (key ESCALATE, run does not)",
            "Over-escalations (= false positives)",
            "Under-escalations (= false negatives)",
        ):
            with self.subTest(label=label):
                self.assertIn(label, text)
        self.assertIn(
            "| True positives (key and run both ESCALATE) | 3 | 110, 207, 213 |", text
        )

    def test_a_subset_labels_its_rates_as_computed_on_that_subset(self):
        text = grade.render_report(self._subset_report((110, 207, 213)))
        self.assertIn("**Escalation rate (on these 3 cases)**", text)
        self.assertIn("Precision on ESCALATE (on these 3 cases)", text)
        self.assertIn("Recall on ESCALATE (on these 3 cases)", text)

    def test_the_full_corpus_block_keeps_the_target_comparison(self):
        text = grade.render_report(self._full_report())
        self.assertIn("| **Escalation rate** | **17.2%** |", text)
        self.assertIn("| Off target | no |", text)
        self.assertIn("Precision on ESCALATE |", text)
        self.assertIn("Whole corpus graded | yes — all 29 cases |", text)
        self.assertNotIn("(on these", text)
        self.assertNotIn("Raw counts", text)


class KeySelfTestTests(unittest.TestCase):
    """The grader must score the key itself perfectly, or it is wrong."""

    def setUp(self):
        self.key = _key()
        self.report = grade.grade(_produced_from_key(self.key), self.key)

    def test_the_key_carries_twenty_nine_cases(self):
        self.assertEqual(len(self.key), 29)

    def test_every_case_matches_on_every_field(self):
        for field in grade.GRADED_FIELDS:
            correct, total = self.report.field_tally(field)
            with self.subTest(field=field):
                self.assertEqual(correct, 29)
                self.assertEqual(total, 29)

    def test_the_four_field_exact_match_is_perfect(self):
        self.assertEqual(self.report.exact_matches, 29)
        self.assertEqual(self.report.total, 29)
        self.assertEqual(self.report.failures, ())

    def test_the_calibration_block_is_exactly_as_specified(self):
        calibration = self.report.calibration
        self.assertEqual(len(calibration.produced_escalations), 5)
        self.assertEqual(calibration.rate, Decimal("17.2"))
        self.assertEqual(calibration.target_rate, Decimal("17.2"))
        self.assertFalse(calibration.rate_off_target)
        self.assertEqual(calibration.precision, Decimal("1.0"))
        self.assertEqual(calibration.recall, Decimal("1.0"))

    def test_nothing_is_over_or_under_escalated(self):
        calibration = self.report.calibration
        self.assertEqual(calibration.over_escalations, ())
        self.assertEqual(calibration.under_escalations, ())

    def test_the_escalations_are_the_five_the_key_names(self):
        self.assertEqual(
            self.report.calibration.produced_escalations, (110, 112, 207, 210, 213)
        )

    def test_four_escalations_are_indeterminate_and_one_is_substantive(self):
        calibration = self.report.calibration
        self.assertEqual(calibration.indeterminate_expected, (110, 112, 210, 213))
        self.assertEqual(calibration.substantive_expected, (207,))
        self.assertEqual(calibration.indeterminate_ruled_confidently, ())
        self.assertEqual(calibration.substantive_escalated, (207,))

    def test_the_self_test_survives_a_json_round_trip(self):
        """The Decimal path is real, not an artefact of sharing objects.

        The produced rulings are serialised to JSON text and parsed back with
        ``parse_float=Decimal`` -- the same hook ``loader.py`` uses -- so the
        amounts reaching the grader are the literals that were written.
        """
        text = money.dumps_canonical(_produced_from_key(self.key))
        reloaded = grade.produced_from_document(json.loads(text, parse_float=Decimal))
        report = grade.grade(reloaded, self.key)
        self.assertEqual(report.exact_matches, 29)
        for field in grade.GRADED_FIELDS:
            self.assertEqual(report.field_tally(field), (29, 29))

    def test_the_key_is_loaded_with_the_loaders_decimal_hook(self):
        # A float anywhere in the key's money would show up as an inequality
        # between the parsed value and its own literal.
        for case_no, expected in self.key.items():
            for field in ("amount_sgd", "driver_compensation_sgd"):
                value = expected.field(field)
                with self.subTest(case=case_no, field=field):
                    if value is not None:
                        self.assertIsInstance(value, Decimal)

    def test_a_produced_side_parsed_without_the_decimal_hook_still_scores_29(self):
        """A caller who used plain ``json.load`` is not punished for it.

        The produced amounts then arrive as binary approximations, and a grader
        comparing them directly with the key's ``Decimal`` would mark the key's
        own case 202 wrong -- ``Decimal("4.8") == 4.8`` is ``False``. Converting
        through ``str`` first is what makes this run score 29/29, and the second
        assertion is the naive comparison it protects against.
        """
        key = _key()
        text = money.dumps_canonical(grade.key_as_produced(key))
        # A plain ``json.load`` gives binary approximations for the money and
        # string keys for the case numbers; ``produced_from_document`` is the
        # entry point that puts the keys back.
        naive = grade.produced_from_document(json.loads(text))

        report = grade.grade(naive, key)
        self.assertEqual(report.exact_matches, 29)
        for field in grade.GRADED_FIELDS:
            self.assertEqual(report.field_tally(field), (29, 29))

        # How much the conversion is actually worth: comparing the key's
        # ``Decimal`` directly against the float a plain ``json.load`` returns
        # marks 13 of the 24 money values in the key wrong, while every one of
        # them is the right number. The count is pinned because the key is
        # frozen; if the key ever moves, this figure moves with it.
        naive_mismatches = [
            (case_no, field)
            for case_no, expected in key.items()
            for field in ("amount_sgd", "driver_compensation_sgd")
            if expected.field(field) is not None
            and expected.field(field) != naive[case_no]["ruling"][field]
        ]
        self.assertEqual(len(naive_mismatches), 13)
        self.assertIn((202, "amount_sgd"), naive_mismatches)
        self.assertIn((105, "amount_sgd"), naive_mismatches)

        # The trap, on the key's own data, with the value that trips it.
        self.assertNotEqual(key[202].amount_sgd, naive[202]["ruling"]["amount_sgd"])
        self.assertTrue(grade.compare_money(key[202].amount_sgd, naive[202]["ruling"]["amount_sgd"]))

    def test_every_case_in_the_key_loads_from_the_corpus(self):
        for case_no in sorted(self.key):
            with self.subTest(case=case_no):
                case = loader.load_case(case_no)
                self.assertEqual(case["case_no"], case_no)

    def test_the_escalation_target_is_not_derived_from_the_key(self):
        # The target is a published figure. A target read out of the key would
        # compare the key with itself and could never be missed.
        self.assertEqual(grade.TARGET_ESCALATION_RATE, Decimal("0.172"))
        key_share = Decimal(5) / Decimal(29)
        self.assertEqual(key_share.quantize(Decimal("0.001")), Decimal("0.172"))
        self.assertNotEqual(key_share, grade.TARGET_ESCALATION_RATE)


class CorrectedKeyTests(unittest.TestCase):
    """Case 115's referral, and the proof that nothing else in the key moved.

    The key is frozen, and a correction to it is a separate commit that states
    its evidence. Case 115's own rationale says twice that the answer includes a
    referral -- "refunded in full under POL-RD-09(4) as a standalone correction
    with a billing-integrity referral recorded in the ruling", and "The answer is
    2.00 and a referral" -- and POL-GEN-03 names POL-RD-09(4) among the clauses
    that PRODUCES one. The key carried an empty list, so it contradicted both its
    own rationale and the policy.

    The digest test is what makes the correction safe to make. It pins every
    other case, so an edit that moved a second thing fails here instead of
    passing as a one-entry change -- and the rationales, which nothing else
    pins, are inside that figure too.
    """

    # ``eval/answers/ground_truth.json`` with case 115's ``expected_referrals``
    # put back to the empty list it held before the correction, canonically
    # serialised. Every other field of every other case is in this figure.
    KEY_WITHOUT_THE_CORRECTION = (
        "a49234f9ab7bd02e2e4973372e3ed14bd62747b54860536cb0d916b25431a690"
    )

    def test_case_115_carries_exactly_one_referral(self):
        self.assertEqual(len(_key()[115].referrals), 1)

    def test_the_referral_leads_with_the_clause_that_produces_it(self):
        """Structural: the clause reference is parsed out, not searched for."""
        keys = grade.referral_keys_of(_key()[115].referrals)
        self.assertEqual(keys, (grade.ReferralKey("POL-RD-09", "4"),))

    def test_the_referral_names_the_phantom_line_it_records(self):
        """A text check, because what is under test is a sentence.

        There is no structural way to ask what a referral says, so this asserts
        the facts a human reviewer acts on: the gantry, its amount, the artifact
        that itemises it, and that the finding is a billing-integrity one.
        """
        referral = _key()[115].referrals[0]
        self.assertTrue(referral.startswith("POL-RD-09(4) "), referral)
        self.assertIn("billing-integrity", referral)
        for fact in ("AYE", "Alexandra Road", "2.00", "EV-FARE-00115"):
            with self.subTest(fact=fact):
                self.assertIn(fact, referral)

    def test_no_other_case_gained_or_lost_a_referral(self):
        key = _key()
        carrying = tuple(
            sorted(case_no for case_no, entry in key.items() if entry.referrals)
        )
        self.assertEqual(carrying, REFERRAL_CASES)
        self.assertEqual(
            {
                case_no: grade.referral_keys_of(key[case_no].referrals)[0].clause
                for case_no in carrying
            },
            REFERRAL_CLAUSES,
        )

    def test_nothing_else_in_the_key_moved(self):
        raw = grade.ANSWER_KEY_PATH.read_bytes()
        restored = []
        for entry in json.loads(raw, parse_float=Decimal):
            inner = dict(entry["ground_truth"])
            if entry["case_no"] == 115:
                inner["expected_referrals"] = []
            restored.append(
                {
                    "case_no": entry["case_no"],
                    "dispute_id": entry["dispute_id"],
                    "ground_truth": inner,
                }
            )
        self.assertEqual(
            money.canonical_sha256(restored),
            self.KEY_WITHOUT_THE_CORRECTION,
            "the correction disturbed something other than case 115's referrals",
        )

    def test_the_corrected_key_still_grades_itself_perfectly(self):
        key = _key()
        report = grade.grade(grade.key_as_produced(key), key)
        self.assertEqual(report.field_tally("referrals"), (29, 29))
        self.assertEqual(report.exact_matches, 29)
        self.assertEqual(report.total, 29)
        self.assertEqual(report.failures, ())


class PerturbationTests(unittest.TestCase):
    """Each single-field change must fail on its own field, and only there.

    The point of the group is the second half of each assertion: a perturbation
    that also moved another field's count would mean the four checks are not
    independent, and the per-field report could not be read as written.
    """

    def setUp(self):
        self.key = _key()
        self.baseline = grade.grade(_produced_from_key(self.key), self.key)

    def _assert_one_field_fails(self, report, field, case_no):
        for name in grade.GRADED_FIELDS:
            correct, total = report.field_tally(name)
            with self.subTest(field=name):
                self.assertEqual(total, 29)
                if name == field:
                    self.assertEqual(correct, 28)
                else:
                    self.assertEqual(correct, 29)

        self.assertEqual(report.exact_matches, 28)
        self.assertEqual(len(report.failures), 1)

        score = next(item for item in report.cases if item.case_no == case_no)
        self.assertFalse(score.exact)
        self.assertEqual(score.failed_fields, (field,))
        self.assertTrue(score.correct_on(field) is False)

    def test_changing_a_ruling_fails_the_ruling_field_only(self):
        produced = _perturbed(self.key, PERTURBATION_CASE, "ruling", "FULL_REFUND")
        report = grade.grade(produced, self.key)
        self._assert_one_field_fails(report, "ruling", PERTURBATION_CASE)

    def test_changing_an_amount_by_five_cents_fails_the_amount_field_only(self):
        original = self.key[PERTURBATION_CASE].amount_sgd
        produced = _perturbed(
            self.key, PERTURBATION_CASE, "amount_sgd", original + Decimal("0.05")
        )
        report = grade.grade(produced, self.key)
        self._assert_one_field_fails(report, "amount_sgd", PERTURBATION_CASE)

    def test_zero_where_the_key_says_null_fails_driver_compensation_only(self):
        self.assertIsNone(self.key[PERTURBATION_CASE].driver_compensation_sgd)
        produced = _perturbed(
            self.key, PERTURBATION_CASE, "driver_compensation_sgd", Decimal("0")
        )
        report = grade.grade(produced, self.key)
        self._assert_one_field_fails(report, "driver_compensation_sgd", PERTURBATION_CASE)

        score = next(item for item in report.cases if item.case_no == PERTURBATION_CASE)
        self.assertIn("null", score.by_field["driver_compensation_sgd"].detail)

    def test_dropping_case_207s_referral_fails_the_referral_field_only(self):
        produced = _perturbed(self.key, 207, "referrals", [])
        report = grade.grade(produced, self.key)
        self._assert_one_field_fails(report, "referrals", 207)

    def test_adding_a_referral_where_the_key_expects_none_fails_too(self):
        self.assertEqual(self.key[PERTURBATION_CASE].referrals, ())
        produced = _perturbed(
            self.key, PERTURBATION_CASE, "referrals", [SPURIOUS_REFERRAL]
        )
        report = grade.grade(produced, self.key)
        self._assert_one_field_fails(report, "referrals", PERTURBATION_CASE)

    def test_each_perturbation_fails_the_four_field_match(self):
        """The five perturbations, each on the case it actually changes.

        Dropping a referral only means anything on a case that carries one, and
        case 207 is the one whose referral is the whole point: it is the case a
        two-field grader passes while the rider goes unreimbursed.
        """
        amount = self.key[PERTURBATION_CASE].amount_sgd
        perturbations = (
            (PERTURBATION_CASE, "ruling", "FULL_REFUND"),
            (PERTURBATION_CASE, "amount_sgd", amount + Decimal("0.05")),
            (PERTURBATION_CASE, "driver_compensation_sgd", Decimal("0")),
            (207, "referrals", []),
            (PERTURBATION_CASE, "referrals", [SPURIOUS_REFERRAL]),
        )
        for case_no, field, value in perturbations:
            with self.subTest(case=case_no, field=field):
                produced = _perturbed(self.key, case_no, field, value)
                report = grade.grade(produced, self.key)
                self.assertEqual(report.exact_matches, 28)
                self.assertEqual(report.field_tally(field), (28, 29))
                score = next(item for item in report.cases if item.case_no == case_no)
                self.assertEqual(score.failed_fields, (field,))
        self.assertEqual(self.baseline.exact_matches, 29)

    def test_the_baseline_is_unchanged_by_the_perturbations(self):
        # ``_perturbed`` builds a fresh mapping each time, so the key and the
        # baseline report are untouched by any of the above.
        self.assertEqual(self.baseline.exact_matches, 29)
        self.assertEqual(self.key[PERTURBATION_CASE].ruling, "PARTIAL_REFUND")
        self.assertEqual(self.key[PERTURBATION_CASE].referrals, ())
        self.assertEqual(len(self.key[207].referrals), 1)


class TwoFieldTrapTests(unittest.TestCase):
    """The mistake this project must not make, demonstrated on case 207."""

    def setUp(self):
        self.key = _key()
        self.produced = _perturbed(self.key, 207, "referrals", [])
        self.report = grade.grade(self.produced, self.key)

    def test_case_207_is_correct_on_ruling_and_amount_yet_still_wrong(self):
        score = next(item for item in self.report.cases if item.case_no == 207)
        self.assertTrue(score.correct_on("ruling"))
        self.assertTrue(score.correct_on("amount_sgd"))
        self.assertTrue(score.two_field)
        self.assertFalse(score.exact)
        self.assertEqual(score.failed_fields, ("referrals",))

    def test_a_two_field_grader_would_score_this_run_perfectly(self):
        self.assertEqual(self.report.two_field_matches, 29)
        self.assertEqual(self.report.exact_matches, 28)

    def test_case_207_is_escalate_with_both_money_fields_null(self):
        # Why the two-field subset is so flattering here: on this case two of
        # its four fields are null on both sides, so they cannot fail.
        expected = self.key[207]
        self.assertEqual(expected.ruling, "ESCALATE")
        self.assertIsNone(expected.amount_sgd)
        self.assertIsNone(expected.driver_compensation_sgd)
        self.assertTrue(expected.referrals)

    def test_the_report_names_case_207_as_the_reason(self):
        text = grade.render_report(self.report)
        self.assertIn("Case 207", text)
        self.assertIn("SGD 4.00", text)


class CalibrationTests(unittest.TestCase):
    """Over-escalation and under-escalation are different failures."""

    def setUp(self):
        self.key = _key()

    def _grade_with_escalations(self, escalating):
        produced = grade.key_as_produced(self.key)
        escalating = set(escalating)
        for case_no in produced:
            produced[case_no]["ruling"]["ruling"] = (
                "ESCALATE" if case_no in escalating else "NO_ACTION"
            )
        return grade.grade(produced, self.key)

    def test_an_over_escalating_run_scores_well_on_recall_and_is_useless(self):
        report = self._grade_with_escalations(self.key)
        calibration = report.calibration
        self.assertEqual(len(calibration.produced_escalations), 29)
        self.assertEqual(calibration.rate, Decimal("100.0"))
        self.assertEqual(calibration.recall, Decimal("1.0"))
        # Every case escalated: precision is the key's own share, 5 of 29.
        self.assertEqual(calibration.precision, Decimal("0.172"))
        self.assertEqual(len(calibration.over_escalations), 24)
        self.assertEqual(len(calibration.under_escalations), 0)

    def test_an_under_escalating_run_is_wrong_in_the_other_direction(self):
        report = self._grade_with_escalations(())
        calibration = report.calibration
        self.assertEqual(calibration.produced_escalations, ())
        self.assertEqual(calibration.rate, Decimal("0.0"))
        # Nothing was escalated, so precision has no denominator.
        self.assertIsNone(calibration.precision)
        self.assertEqual(calibration.recall, Decimal("0.0"))
        self.assertEqual(len(calibration.over_escalations), 0)
        self.assertEqual(len(calibration.under_escalations), 5)

    def test_the_two_counts_are_never_summed(self):
        report = self._grade_with_escalations(self.key)
        calibration = report.calibration
        self.assertEqual(
            len(calibration.over_escalations), len(calibration.false_positives)
        )
        self.assertEqual(
            len(calibration.under_escalations), len(calibration.false_negatives)
        )
        # Both are exposed, and neither is folded into the other or the rate.
        self.assertNotEqual(calibration.over_escalations, calibration.under_escalations)

    def test_a_run_confident_on_indeterminate_cases_is_shown_as_such(self):
        # Escalating only two of the four INDETERMINATE cases: recall is
        # partial, and the two it answered are named rather than averaged in.
        report = self._grade_with_escalations((110, 210))
        calibration = report.calibration
        self.assertEqual(calibration.true_positives, (110, 210))
        self.assertEqual(calibration.false_negatives, (112, 207, 213))
        self.assertEqual(calibration.precision, Decimal("1.0"))
        self.assertEqual(calibration.recall, Decimal("0.4"))
        self.assertEqual(calibration.indeterminate_escalated, (110, 210))
        self.assertEqual(calibration.indeterminate_ruled_confidently, (112, 213))
        self.assertEqual(calibration.substantive_escalated, ())

    def test_answering_every_indeterminate_case_is_reported_as_the_worst_failure(self):
        report = self._grade_with_escalations(())
        calibration = report.calibration
        self.assertEqual(len(calibration.indeterminate_ruled_confidently), 4)
        text = grade.render_report(report)
        self.assertIn("ruled confidently", text)
        self.assertIn("110, 112, 210, 213", text)

    def test_a_partial_escalation_rate_is_reported_against_the_target(self):
        report = self._grade_with_escalations((110, 210))
        calibration = report.calibration
        self.assertEqual(calibration.rate, Decimal("6.9"))
        self.assertEqual(calibration.target_rate, Decimal("17.2"))
        self.assertTrue(calibration.rate_off_target)

    def test_the_rate_is_a_percentage_not_a_fraction(self):
        report = self._grade_with_escalations((110, 112, 207, 210, 213))
        self.assertEqual(report.calibration.rate, Decimal("17.2"))
        self.assertFalse(report.calibration.rate_off_target)


class ProducedRecordShapeTests(unittest.TestCase):
    """Whatever a caller hands over, the four graded fields are found."""

    def setUp(self):
        self.key = _key()

    def test_the_bare_ruling_object_is_accepted(self):
        ruling = grade.produced_from_mapping(
            {
                "ruling": "PARTIAL_REFUND",
                "amount_sgd": Decimal("8.05"),
                "driver_compensation_sgd": None,
                "referrals": [],
            },
            case_no=101,
        )
        self.assertEqual(ruling.ruling, "PARTIAL_REFUND")
        self.assertEqual(ruling.amount_sgd, Decimal("8.05"))

    def test_the_judges_result_object_is_accepted(self):
        ruling = grade.produced_from_mapping(
            {
                "ruling": {
                    "ruling": "PARTIAL_REFUND",
                    "amount_sgd": Decimal("8.05"),
                    "driver_compensation_sgd": None,
                    "referrals": [],
                    "confidence": Decimal("0.9"),
                    "explanation": "Addressed to both parties.",
                },
                "discarded_claims": [{"claim": "x", "side": "RIDER", "reason": "y"}],
            },
            case_no=101,
        )
        self.assertEqual(ruling.ruling, "PARTIAL_REFUND")
        self.assertEqual(ruling.confidence, Decimal("0.9"))
        self.assertEqual(ruling.contract_notes, ())

    def test_a_record_with_no_case_number_is_rejected(self):
        with self.assertRaises(grade.GradeError):
            grade.produced_from_mapping({"ruling": "NO_ACTION"}, case_no=None)

    def test_a_case_number_can_come_from_the_record(self):
        ruling = grade.produced_from_mapping({"case_no": 209, "ruling": "NO_ACTION"})
        self.assertEqual(ruling.case_no, 209)

    def test_a_missing_ruling_fails_every_field(self):
        report = grade.grade({}, self.key)
        self.assertEqual(report.exact_matches, 0)
        self.assertEqual(len(report.unproduced), 29)
        for field in grade.GRADED_FIELDS:
            self.assertEqual(report.field_tally(field), (0, 29))
        self.assertTrue(
            all("no ruling produced" in outcome.detail
                for outcome in report.cases[0].outcomes)
        )

    def test_referrals_arriving_as_a_string_fail_and_are_noted(self):
        produced = grade.key_as_produced(self.key)
        produced[207]["ruling"]["referrals"] = (
            "POL-NS-07 escalation packet: instruct the reviewer to refund"
        )
        report = grade.grade(produced, self.key)
        self.assertEqual(report.field_tally("referrals"), (28, 29))
        score = next(item for item in report.cases if item.case_no == 207)
        self.assertFalse(score.correct_on("referrals"))
        self.assertIn("not an array", score.by_field["referrals"].detail)

    def test_a_ruling_outside_the_vocabulary_is_named_as_such(self):
        produced = _perturbed(self.key, PERTURBATION_CASE, "ruling", "REVERSED")
        report = grade.grade(produced, self.key)
        score = next(
            item for item in report.cases if item.case_no == PERTURBATION_CASE
        )
        self.assertIn("not a POL-GEN-03 value", score.by_field["ruling"].detail)

    def test_a_string_amount_compares_on_its_value_and_is_noted(self):
        produced = grade.key_as_produced(self.key)
        produced[PERTURBATION_CASE]["ruling"]["amount_sgd"] = "8.05"
        report = grade.grade(produced, self.key)
        self.assertEqual(report.field_tally("amount_sgd"), (29, 29))
        self.assertTrue(
            any(
                case_no == PERTURBATION_CASE and field == "amount_sgd"
                for case_no, field, _ in report.encoding_notes
            )
        )

    def test_an_unexpected_case_is_reported_rather_than_scored(self):
        produced = grade.key_as_produced(self.key)
        produced[999] = {"case_no": 999, "ruling": "NO_ACTION"}
        report = grade.grade(produced, self.key)
        self.assertEqual(report.total, 29)
        self.assertEqual(report.unexpected_cases, (999,))


class DocumentShapeTests(unittest.TestCase):
    """The three shapes a produced-rulings file arrives in."""

    def test_an_array_of_records(self):
        document = [{"case_no": 101, "ruling": "NO_ACTION"}]
        self.assertEqual(
            sorted(grade.produced_from_document(document)), [101]
        )

    def test_an_object_keyed_by_case_number(self):
        document = {"101": {"ruling": "NO_ACTION"}, "207": {"ruling": "ESCALATE"}}
        self.assertEqual(sorted(grade.produced_from_document(document)), [101, 207])

    def test_a_single_record(self):
        document = {"case_no": 101, "ruling": "NO_ACTION"}
        self.assertEqual(sorted(grade.produced_from_document(document)), [101])

    def test_a_document_that_is_neither_is_rejected(self):
        with self.assertRaises(grade.GradeError):
            grade.produced_from_document("not a document")


class ReportTests(unittest.TestCase):
    """The report a reader actually sees."""

    def setUp(self):
        self.key = _key()
        self.report = grade.grade(grade.key_as_produced(self.key), self.key)
        self.text = grade.render_report(self.report, grade.SELF_TEST_TITLE)

    def test_rendering_is_deterministic(self):
        self.assertEqual(self.text, grade.render_report(self.report, grade.SELF_TEST_TITLE))

    def test_it_reports_every_field_separately(self):
        for field in grade.GRADED_FIELDS:
            self.assertIn("`{0}`".format(field), self.text)

    def test_it_reports_the_four_field_match_and_the_two_field_contrast(self):
        self.assertIn("Four-field exact match", self.text)
        self.assertIn("29/29 = 100.0%", self.text)
        self.assertIn("Reported as a contrast only", self.text)

    def test_it_carries_the_expected_and_produced_referral_texts(self):
        for case_no in REFERRAL_CASES:
            expected_text = self.key[case_no].referrals[0]
            with self.subTest(case=case_no):
                self.assertIn("### Case {0}".format(case_no), self.text)
                self.assertIn(expected_text, self.text)
                # Both sides appear, so the reader can compare substance.
                self.assertEqual(self.text.count(expected_text), 2)

    def test_it_reports_the_escalation_rate_against_the_target(self):
        self.assertIn("17.2%", self.text)
        self.assertIn("Target | 17.2%", self.text)
        self.assertIn("Precision on ESCALATE", self.text)
        self.assertIn("Recall on ESCALATE", self.text)

    def test_it_keeps_over_and_under_escalation_apart(self):
        self.assertIn("Over-escalations (produced ESCALATE, key does not)", self.text)
        self.assertIn("Under-escalations (key ESCALATE, produced does not)", self.text)
        self.assertIn("never summed into one figure", self.text)

    def test_it_reports_the_indeterminate_cases_separately(self):
        self.assertIn("The INDETERMINATE cases, kept out of the rate", self.text)
        self.assertIn("110, 112, 210, 213", self.text)
        self.assertIn("ruled confidently", self.text)

    def test_it_states_that_a_ruling_counts_only_when_all_four_agree(self):
        self.assertIn("all four", self.text)

    def test_it_carries_no_binary_float_artefact(self):
        # A float round-trip leaves a run of digits no decimal literal produces.
        self.assertNotIn("4.800000000000001", self.text)
        self.assertNotIn("0000000", self.text)

    def test_money_is_rendered_as_the_decimal_that_was_written(self):
        # The key's 4.0 must not be printed as 4, and 65.13 must stay 65.13.
        self.assertEqual(grade.render_money(Decimal("4.0")), "4.0")
        self.assertEqual(grade.render_money(Decimal("65.13")), "65.13")
        self.assertEqual(grade.render_money(None), "null")

    def test_the_committed_self_test_report_is_what_the_module_renders(self):
        committed = grade.DEFAULT_REPORT_PATH
        self.assertTrue(committed.exists(), "the self-test report is not committed")
        self.assertEqual(
            committed.read_text(encoding="utf-8"),
            grade.render_report(self.report, grade.SELF_TEST_TITLE),
        )


class BoundaryTests(unittest.TestCase):
    """The grader reads the package; the package never reads the grader."""

    def test_the_grader_imports_the_package(self):
        self.assertIn("loader", grade.__dict__)

    def test_no_package_module_imports_the_grader(self):
        # ``tribunal/loader.py`` names ``ground_truth`` on purpose, in its
        # FORBIDDEN_KEYS list, so only the grader's own path is checked here.
        # The broader path control is asserted in test_answer_isolation.py.
        for path in sorted(TRIBUNAL_DIR.glob("*.py")):
            with self.subTest(module=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("eval.grade", source)
                self.assertNotIn("eval/grade", source)

    def test_the_grader_never_imports_the_model_transport(self):
        """A grader that could reach the model could spend money to grade."""
        tree = ast.parse(GRADE_SOURCE.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("tribunal.llm", imported)
        self.assertFalse(
            any(name.endswith(".llm") or name == "llm" for name in imported),
            "the grader imports a model transport: {0}".format(sorted(imported)),
        )

    def test_the_grader_imports_no_network_module(self):
        tree = ast.parse(GRADE_SOURCE.read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        for module in ("socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib"):
            with self.subTest(module=module):
                self.assertNotIn(module, roots)

    def test_the_grader_touches_the_package_in_exactly_one_place(self):
        """The grader's whole dependency on the package is the ruling vocabulary.

        ``load_policies`` is the only loader entry point it calls. It never
        builds a runtime bundle and never loads a case, so there is no path by
        which a key value could be handed to the package that produces a brief,
        a prompt or a transcript. Attribute access is read from the parsed
        source, not from the text, so a docstring naming an entry point does not
        count as using it.
        """
        tree = ast.parse(GRADE_SOURCE.read_text(encoding="utf-8"))
        used = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "loader"
        }
        self.assertEqual(used, {"load_policies"})

        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "tribunal"
            for alias in node.names
        }
        self.assertEqual(imported, {"loader"})

    def test_the_grader_carries_no_credential(self):
        source = GRADE_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("TOKENHUB", source)
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9]{16,}", source))


if __name__ == "__main__":
    unittest.main()
