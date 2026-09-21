"""Part A of the rationale audit, as tests: a rationale checked against itself.

These are real tests. A stated sum that does not add up is wrong regardless of
what the case data says, so a failure here is unambiguous and must never be
worked around by weakening the assertion.

The checks themselves live in ``eval/verify_rationales.py``, which reads the
package. The dependency runs one way only: ``eval/`` may import ``tribunal/``,
and nothing under ``tribunal/`` may read ``eval/``. ``test_answer_isolation.py``
enforces that boundary; ``DependencyDirectionTests`` below records this half of
it.

Part B of the audit — the external reconciliation — is a report, not a test,
and is deliberately absent here. See ``docs/notes/2026-09-21-rationale-audit.md``.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import tokenize
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import verify_rationales as audit  # noqa: E402

AUDIT_SOURCE = PROJECT_ROOT / "eval" / "verify_rationales.py"

# The rationales the audit is known to cover. Recorded so a change in coverage
# is a visible change rather than a silently emptier check.
CASES_WITH_A_STATED_SUM = (101, 103, 104, 105, 106, 107, 111, 114)
STATED_SUM_COUNT = 13
CASES_WITH_A_STATED_ROUND_UP = (101, 104, 105, 106, 107, 109, 114)
STATED_ROUND_UP_COUNT = 7


def records():
    return audit.load_answer_key()


def rationale_of(case_no):
    return audit.answer_key_by_case()[case_no]["ground_truth"]["rationale"]


class SumClaimTests(unittest.TestCase):
    """A stated sum must add up."""

    def test_every_stated_sum_in_the_key_adds_up(self):
        checked = 0
        failures = []
        for record in records():
            for claim in audit.sum_claims(record["ground_truth"]["rationale"]):
                checked += 1
                if not claim.agrees:
                    failures.append(
                        "case {0}: `{1}` — exact {2}, stated {3}".format(
                            record["case_no"], claim.text, claim.exact, claim.right
                        )
                    )
        self.assertEqual(STATED_SUM_COUNT, checked, "the set of stated sums changed")
        self.assertEqual([], failures, "a stated sum does not add up")

    def test_the_extractor_finds_the_stated_sums_it_is_meant_to(self):
        """A extractor that found nothing would make the test above vacuous."""
        found = {}
        for record in records():
            claims = audit.sum_claims(record["ground_truth"]["rationale"])
            if claims:
                found[record["case_no"]] = len(claims)
        self.assertEqual(
            list(CASES_WITH_A_STATED_SUM), sorted(found), "the covered case set changed"
        )
        self.assertEqual(STATED_SUM_COUNT, sum(found.values()))

    def test_the_min_form_is_read_as_a_claim_about_its_expression(self):
        """``min(5.98, EXPR) = min(5.98, 7.76)`` states that EXPR is 7.76."""
        claims = audit.sum_claims(
            "the justified excess is min(5.98, 1.30 x (29.20 - 24.00) + 1.00) = "
            "min(5.98, 7.76) = 5.98 km, the whole of it."
        )
        self.assertEqual(1, len(claims), "the min-wrapped claim was not extracted")
        self.assertEqual(Decimal("7.76"), claims[0].right)
        self.assertEqual(Decimal("7.76"), claims[0].exact)

    def test_a_sum_that_does_not_add_up_is_caught(self):
        """The check must be capable of failing, or it proves nothing."""
        claims = audit.sum_claims("the fare is 3.80 + 15.75 + 7.28 + 0.80 = 27.83.")
        self.assertEqual(1, len(claims))
        self.assertFalse(claims[0].agrees, "a wrong total was accepted")
        self.assertEqual(Decimal("27.63"), claims[0].exact)

    def test_a_figure_stated_at_its_own_precision_is_accepted(self):
        """The prose rounds intermediates; the tolerance is half a unit in the last place."""
        claim = audit.sum_claims("34.0 x 32.00 / 27.10 = 40.1")[0]
        self.assertTrue(claim.agrees)
        self.assertEqual(Decimal("40.14760147601476014760147601"), claim.exact)


class DecimalArithmeticTests(unittest.TestCase):
    """This module's own arithmetic must never introduce a false discrepancy."""

    def test_evaluation_is_exact_decimal(self):
        self.assertEqual(Decimal("0.3"), audit.evaluate("0.1 + 0.2"))
        self.assertEqual(Decimal("27.63"), audit.evaluate("3.80 + 15.75 + 7.28 + 0.80"))
        self.assertEqual(Decimal("29.1770"), audit.evaluate("(3.80 + 10.50 + 6.72) x 1.35 + 0.80"))

    def test_the_float_route_would_have_been_wrong(self):
        """Why the module converts through ``str`` and never computes in float."""
        self.assertNotEqual(0.1 + 0.2, Decimal("0.3"))
        self.assertEqual(Decimal("0.3"), audit.evaluate("0.1 + 0.2"))

    def test_the_module_never_calls_float(self):
        """``float`` must not be used as a name, checked on NAME tokens.

        The module docstring is free to explain that ``facts.py`` returns
        floats, while the code is not allowed to call ``float``.
        """
        source = AUDIT_SOURCE.read_text(encoding="utf-8")
        names = [
            token.string
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.NAME
        ]
        self.assertNotIn("float", names)


class RoundingClaimTests(unittest.TestCase):
    """A stated round-up must satisfy the rule ``money.py`` implements."""

    def test_every_stated_round_up_satisfies_the_money_rule(self):
        checked = 0
        failures = []
        for record in records():
            for claim in audit.rounding_claims(record["ground_truth"]["rationale"]):
                checked += 1
                if not claim.agrees:
                    failures.append(
                        "case {0}: `{1}` — round_up_005 gives {2}".format(
                            record["case_no"],
                            claim.text,
                            audit.money.round_up_005(claim.before),
                        )
                    )
        self.assertEqual(STATED_ROUND_UP_COUNT, checked, "the set of stated round-ups changed")
        self.assertEqual([], failures, "a stated round-up does not satisfy the money rule")

    def test_the_extractor_finds_the_round_ups_it_is_meant_to(self):
        found = {}
        for record in records():
            claims = audit.rounding_claims(record["ground_truth"]["rationale"])
            if claims:
                found[record["case_no"]] = len(claims)
        self.assertEqual(
            list(CASES_WITH_A_STATED_ROUND_UP), sorted(found), "the covered case set changed"
        )
        self.assertEqual(STATED_ROUND_UP_COUNT, sum(found.values()))

    def test_a_round_up_that_is_wrong_is_caught(self):
        claim = audit.rounding_claims("a refund of 8.01 rounded up to 8.10")[0]
        self.assertFalse(claim.agrees, "a wrong round-up target was accepted")
        self.assertEqual(Decimal("8.05"), audit.money.round_up_005(claim.before))

    def test_a_rounded_copy_is_not_read_as_a_round_up(self):
        """A one-decimal restatement of a trace figure is a different operation."""
        self.assertEqual(
            [],
            audit.rounding_claims(
                "the trip record's rounded actual_distance_km of 10.8 makes the excess 50.0%"
            ),
        )


class ExpectedFigureTests(unittest.TestCase):
    """The block's own figure must be a figure its rationale arrives at."""

    def test_every_expected_figure_appears_in_its_rationale(self):
        checked = 0
        failures = []
        for record in records():
            figure = audit.expected_figure(record)
            if figure is None:
                continue
            checked += 1
            if figure not in audit.prose_numbers(record["ground_truth"]["rationale"]):
                failures.append("case {0}: {1} is not in the rationale".format(
                    record["case_no"], figure))
        self.assertEqual(19, checked, "the set of cases carrying money changed")
        self.assertEqual([], failures, "an expected figure is absent from its rationale")

    def test_a_partial_refund_round_up_target_is_the_expected_figure(self):
        """Where the ruling is not a full refund, the arrived-at figure must match.

        A FULL_REFUND rationale arrives at two figures on purpose — the computed
        partial and the ordered full refund — so it is exempt.
        """
        checked = 0
        for record in records():
            block = record["ground_truth"]
            if block["expected_ruling"] not in ("PARTIAL_REFUND", "DRIVER_COMPENSATION"):
                continue
            targets = [claim.after for claim in audit.rounding_claims(block["rationale"])]
            if not targets:
                continue
            checked += 1
            with self.subTest(case_no=record["case_no"]):
                self.assertIn(audit.expected_figure(record), targets)
        self.assertEqual(6, checked, "the set of round-up cases changed")

    def test_a_mismatched_expected_figure_is_caught(self):
        """The check must be capable of failing."""
        self.assertNotIn(Decimal("8.05"), audit.prose_numbers("the refund is 8.06."))
        self.assertIn(Decimal("8.05"), audit.prose_numbers("the refund is 8.05."))


class InternalConsistencyTests(unittest.TestCase):
    """The three checks, taken together over the whole key."""

    def test_the_whole_key_is_internally_consistent(self):
        failures = audit.internal_failures()
        self.assertEqual(
            [],
            [
                "case {0} {1}: {2} ({3})".format(
                    finding.case_no, finding.check, finding.subject, finding.detail
                )
                for finding in failures
            ],
            "the key is not internally consistent",
        )

    def test_every_check_kind_actually_ran(self):
        """A check that ran on nothing would pass for the wrong reason."""
        kinds = {finding.check for finding in audit.check_internal_consistency()}
        self.assertEqual({"sum", "rounding", "expected"}, kinds)


class ReportTests(unittest.TestCase):
    """Part B renders, and says what it must say."""

    def test_the_report_renders_and_is_deterministic(self):
        first = audit.render_report()
        second = audit.render_report()
        self.assertEqual(first, second, "the report is not reproducible")
        self.assertEqual(29, first.count("\n### Case "), "not every case is covered")

    def test_the_report_keeps_the_two_kinds_of_check_apart(self):
        report = audit.render_report()
        self.assertIn("Part A — internal consistency", report)
        self.assertIn("Part B — external reconciliation", report)

    def test_the_report_states_that_a_mismatch_proves_nothing(self):
        """The most important sentence in the report, asserted rather than assumed."""
        report = audit.render_report()
        self.assertIn("does **not** establish which side is wrong", report)
        self.assertIn("may be wrong, or this", report)

    def test_the_report_carries_both_directions_of_the_reconciliation(self):
        report = audit.render_report()
        self.assertIn("no counterpart", report)
        self.assertIn("accounts for", report)
        self.assertIn("## Cases needing a human", report)

    def test_the_report_was_not_written_by_hand(self):
        """The committed report must be what the module renders today."""
        committed = (PROJECT_ROOT / "docs" / "notes" / "2026-09-21-rationale-audit.md")
        self.assertTrue(committed.is_file(), "the audit report is missing")
        self.assertEqual(
            audit.render_report(),
            committed.read_text(encoding="utf-8"),
            "the committed report has drifted from the module that produces it",
        )


class DependencyDirectionTests(unittest.TestCase):
    """``eval/`` reads the package; the package never reads ``eval/``."""

    def test_the_audit_imports_the_package(self):
        source = AUDIT_SOURCE.read_text(encoding="utf-8")
        self.assertIn("from tribunal import", source)

    def test_no_package_module_imports_the_audit(self):
        offenders = []
        for path in sorted((PROJECT_ROOT / "tribunal").rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if "verify_rationales" in source or "ground_truth.json" in source:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))
        self.assertEqual([], offenders, "a package module reaches into eval/")


if __name__ == "__main__":
    unittest.main()
