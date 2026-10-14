"""The version-8 measurements, held to the values the committed runs give.

``eval/v8_report.py`` measures the position swap, the calibration, the automatic
share, the clock and the cost off the two committed version-8 runs. This module
holds it to four things:

* **The table's values.** Every figure the report states is recomputed here from
  the committed runs and asserted, so a run that changed under the reader is a
  failure rather than a new number in a note.
* **The cases behind the swap.** The cases that qualify, the case that differs,
  and the cases that do not qualify with their reason -- a swap count without
  its denominator is not a measurement.
* **The version-6 figures unchanged.** ``calibrate`` gained a ``floor`` keyword;
  with no keyword it must give exactly what it gave, and the bins and the error
  must not move whatever floor is passed, because only the **split** is taken at
  a floor.
* **The check can fail.** A temporary copy of the ``dev-v8`` run with case
  5009's swapped draft given its sampled majority's own four fields moves the
  swap count, which is what shows the count is read off the drafts rather than
  written down.

No model call is made and no network is reached: every reading is a committed
run, a committed key or a committed transcript. Run from the project root
with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import fairness, v6_runs, v8_report  # noqa: E402
from tests import portability  # noqa: E402

# The case the control rewrites, and the four-field value it is given: case
# 5009's sampled majority is two ``PARTIAL_REFUND`` drafts at 1.08 SGD, so a
# swapped draft given the same three values agrees on all four fields.
CONTROL_CASE = 5009
CONTROL_MAJORITY = {
    "ruling": "PARTIAL_REFUND",
    "amount_sgd": 1.08,
    "driver_compensation_sgd": None,
    "referrals": [],
}


def _seconds(value):
    return v6_runs._seconds(value)


class TheMeasuredValuesTests(unittest.TestCase):
    """Every figure in the report's table, from the committed runs."""

    @classmethod
    def setUpClass(cls) -> None:
        portability.require_the_same_libm()
        cls.dev = v8_report.measure("dev-v8")
        cls.ryde = v8_report.measure("ryde-v8")

    def test_dev_v8_states_the_table_s_values(self):
        dev = self.dev
        self.assertEqual(40, dev.cases)
        self.assertEqual(39, dev.exact)
        self.assertEqual(
            (12, 13, 12),
            (dev.escalated_produced, dev.escalated_expected, dev.true_positives),
        )
        self.assertEqual(28, dev.decided_with_no_person)
        self.assertEqual("153.1", _seconds(dev.wall_median))
        self.assertEqual("299.4", _seconds(dev.wall_p90))
        self.assertEqual("0.0390", "{0:.4f}".format(dev.cost_median))
        self.assertEqual("1.823", "{0:.3f}".format(dev.cost_total))
        self.assertEqual((33, 34), (dev.swap.agree_all_four, dev.swap.total))
        self.assertEqual((33, 34), (dev.swap.agree_ruling, dev.swap.total))
        self.assertEqual(139, dev.calibration.total)
        self.assertEqual("0.097", fairness.render_ece(dev.calibration.ece))
        self.assertEqual((14, 14), dev.calibration.below_floor)
        self.assertEqual((118, 125), dev.calibration.at_or_above_floor)
        self.assertEqual(14, dev.below_escalations)
        self.assertEqual((5017,), tuple(m.case_no for m in dev.lean.differing))
        self.assertEqual(
            fairness.AWAY_FROM_ESCALATION, dev.lean.differing[0].direction
        )

    def test_ryde_v8_states_the_table_s_values(self):
        ryde = self.ryde
        self.assertEqual(2, ryde.cases)
        self.assertEqual(1, ryde.exact)
        self.assertEqual(
            (2, 1, 1),
            (ryde.escalated_produced, ryde.escalated_expected, ryde.true_positives),
        )
        self.assertEqual(0, ryde.decided_with_no_person)
        self.assertEqual("0.0632", "{0:.4f}".format(ryde.cost_median))
        self.assertEqual("0.126", "{0:.3f}".format(ryde.cost_total))
        self.assertEqual((0, 0), (ryde.swap.agree_all_four, ryde.swap.total))
        self.assertEqual(3, ryde.calibration.total)
        self.assertEqual((903,), tuple(m.case_no for m in ryde.lean.differing))
        self.assertEqual(
            fairness.TO_ESCALATION, ryde.lean.differing[0].direction
        )

    def test_the_calibration_split_is_taken_at_the_version_eight_bar(self):
        """The split is at 0.80; the bins are the sheet's and do not move."""
        dev = self.dev
        self.assertEqual(Decimal("0.80"), v8_report.V8_FLOOR)
        self.assertEqual(
            [Decimal("0.0"), Decimal("0.5"), Decimal("0.7"), Decimal("0.8"),
             Decimal("0.9"), Decimal("1.0")],
            [bin_.low for bin_ in dev.calibration.bins]
            + [dev.calibration.bins[-1].high],
        )
        # Every draft below the bar is an escalation, which is what the table's
        # parenthetical states.
        self.assertEqual(dev.calibration.below_floor[1], dev.below_escalations)

    def test_the_swap_names_the_cases_that_do_not_qualify(self):
        """A count without its denominator and its reasons is not a measurement."""
        self.assertEqual((5009,), self.dev.swap.disagreements())
        self.assertEqual(
            (
                (5006, v8_report.NO_VALID_SWAPPED),
                (5010, v8_report.NO_JUDGE_ASKED),
                (5012, v8_report.NO_JUDGE_ASKED),
                (5013, v8_report.NO_JUDGE_ASKED),
                (5015, v8_report.NO_JUDGE_ASKED),
                (5068, v8_report.NO_JUDGE_ASKED),
            ),
            self.dev.absent,
        )
        self.assertEqual(
            (
                (902, v8_report.NO_JUDGE_ASKED),
                (903, v8_report.NO_VALID_SWAPPED),
            ),
            self.ryde.absent,
        )

    def test_the_two_sets_are_never_pooled(self):
        """Each set is its own section, and no figure sums the two."""
        text = v8_report.report()
        self.assertEqual(2, len(v8_report.measurements()))
        self.assertEqual(1, text.count("== dev-v8 =="))
        self.assertEqual(1, text.count("== ryde-v8 =="))
        self.assertNotIn("== both", text)

    def test_the_figures_are_the_ones_the_note_states(self):
        self.assertEqual(
            {
                "dev-v8 decided with no person": "28 of 40",
                "dev-v8 position swap": "33 of 34",
                "dev-v8 ECE": "0.097",
                "dev-v8 drafts": "139",
            },
            v8_report.figures(),
        )

    def test_the_two_runs_are_not_in_the_version_six_batch(self):
        """A version-8 set added to ``v6_runs.RUNS`` would change the v6 figures."""
        names = {run.name for run in v6_runs.RUNS}
        self.assertNotIn("dev-v8", names)
        self.assertNotIn("ryde-v8", names)
        run = v8_report.measured_run("dev-v8")
        self.assertEqual("dev-v8", run.name)
        self.assertEqual(
            "runs/dev-v8/policy-v8/deepseek-deepseek-flash",
            str(run.run_dir.relative_to(PROJECT_ROOT)),
        )
        self.assertEqual(40, len(run.cases))
        self.assertEqual(
            "eval/answers/dev-v8/ground_truth.json",
            str(run.key_path.relative_to(PROJECT_ROOT)),
        )

    def test_an_unknown_set_is_refused(self):
        with self.assertRaises(v8_report.V8ReportError):
            v8_report.measured_run("dev-v7")


class TheVersionSixFiguresTests(unittest.TestCase):
    """The version-6 figures do not move when the floor keyword is added."""

    @classmethod
    def setUpClass(cls) -> None:
        portability.require_the_same_libm()

    def test_the_version_six_figures_are_unchanged(self):
        _lean, swap, calibration = fairness.combined_measurements()
        self.assertEqual((136, 141), (swap.agree_all_four, swap.total))
        self.assertEqual("136/141 = 96.5%", fairness.swap_agreement_cell(swap))
        self.assertEqual("0.088", fairness.render_ece(calibration.ece))
        self.assertEqual("0.088", fairness.calibration_error_cell(calibration))

    def test_calibrate_with_no_keyword_is_exactly_what_it_gave(self):
        """The default floor is the version-6 one, and the split is where it was."""
        run = fairness.measured_run(fairness.CORPUS)
        outcomes = fairness.draft_outcomes(run)
        default = fairness.calibrate(outcomes)
        self.assertEqual(fairness.FLOOR, Decimal("0.70"))
        self.assertEqual(default, fairness.calibrate(outcomes, floor=fairness.FLOOR))
        self.assertEqual(
            default.below_floor,
            fairness.calibrate(outcomes, floor=fairness.FLOOR).below_floor,
        )
        self.assertEqual(
            default.at_or_above_floor,
            fairness.calibrate(outcomes, floor=fairness.FLOOR).at_or_above_floor,
        )

    def test_the_bins_and_the_error_do_not_move_with_the_floor(self):
        """Only the **split** is taken at the floor; the bins are the sheet's."""
        run = fairness.measured_run(fairness.CORPUS)
        outcomes = fairness.draft_outcomes(run)
        default = fairness.calibrate(outcomes)
        moved = fairness.calibrate(outcomes, floor=Decimal("0.80"))
        self.assertEqual(default.bins, moved.bins)
        self.assertEqual(default.ece, moved.ece)
        self.assertEqual(default.total, moved.total)
        # The split itself does move, which is what the keyword is for.
        self.assertNotEqual(default.below_floor, moved.below_floor)


class TheControlTests(unittest.TestCase):
    """The swap count is read off the drafts, shown by moving one draft."""

    def test_a_changed_swapped_draft_moves_the_swap_count(self):
        portability.require_the_same_libm()
        committed = v8_report.measure("dev-v8")
        self.assertEqual(33, committed.swap.agree_all_four)
        with tempfile.TemporaryDirectory() as directory:
            control = self._control_run(Path(directory))
            swap = fairness.position_swap(fairness.transcripts(control))
        self.assertEqual(34, swap.total)
        self.assertEqual(
            34,
            swap.agree_all_four,
            "case {0}'s swapped draft was given its sampled majority's own four "
            "fields and the count did not move".format(CONTROL_CASE),
        )
        self.assertEqual(34, swap.agree_ruling)

    @staticmethod
    def _control_run(root: Path) -> v6_runs.V6Run:
        """A copy of the ``dev-v8`` run with case 5009's swapped draft changed.

        The whole run is copied rather than the one case, so the count the
        control moves is the same count the report prints: a swap over a run
        holding one case would say nothing about the 34 the report measures.
        """
        source = v8_report.measured_run("dev-v8")
        run_dir = root / "run"
        shutil.copytree(source.run_dir, run_dir)
        transcript_path = run_dir / "case-{0:05d}.transcript.json".format(CONTROL_CASE)
        document = json.loads(transcript_path.read_text(encoding="utf-8"))
        swapped = next(
            draft
            for draft in document["vote"]["drafts"]
            if draft.get("kind") == v8_report.POSITION_SWAPPED
        )
        entry = document["entries"][swapped["entries"][-1]]
        entry["parsed"]["ruling"].update(CONTROL_MAJORITY)
        transcript_path.write_text(json.dumps(document), encoding="utf-8")
        return v6_runs.V6Run(
            name="control",
            run_dir=run_dir,
            cases=source.cases,
            key_path=source.key_path,
            registered_size=len(source.cases),
            summary="the dev-v8 run with one swapped draft's ruling changed",
        )


if __name__ == "__main__":
    unittest.main()
