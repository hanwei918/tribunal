"""The fairness and calibration measurements, held against the committed runs.

``eval/fairness.py`` computes three measurements over the version-6 development
runs and draws one chart. A figure that a module computes and nobody checks is a
figure that can drift, so this module checks the four things the measurement
rests on:

* every POL-GEN-03 ruling value is classified into exactly one side, read from
  the policy rather than from a list copied here;
* the position swap reads a pair of synthetic drafts and reports the one that
  disagrees, on the ruling alone and on all four fields;
* the calibration's expected error is the known value of a synthetic set of
  drafts whose bins and gaps are arithmetic a reader can do by hand;
* the escalate split counts the drafts that propose ``ESCALATE`` below the floor
  and at or above it, and the share correct among the rest, on a synthetic set
  whose counts are known by hand;
* the committed chart ``docs/calibration-v6.svg`` equals a fresh build, byte for
  byte.

It also checks what the report **reads**: that the only path under
``eval/answers/`` it opens is one of the corpus and ``dev-v2-ext`` keys, and that
it opens nothing under a sealed root at all.

**No model call is made.** Every reading is a committed run, a committed key or a
committed case file, and the two synthetic tests build their own objects.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import fairness, grade  # noqa: E402

CHART_PATH = PROJECT_ROOT / "docs" / "calibration-v6.svg"

# The two answer keys the report is allowed to open, resolved.
PERMITTED_KEYS = frozenset(
    {
        (PROJECT_ROOT / "eval" / "answers" / "ground_truth.json").resolve(),
        (PROJECT_ROOT / "eval" / "answers" / "dev-v2-ext" / "ground_truth.json").resolve(),
    }
)

# The three sides, as the report prints them.
EXPECTED_SIDES: Mapping[str, str] = {
    "FULL_REFUND": fairness.RIDER,
    "PARTIAL_REFUND": fairness.RIDER,
    "NO_ACTION": fairness.DRIVER,
    "DRIVER_COMPENSATION": fairness.DRIVER,
    "ESCALATE": fairness.NEITHER,
}

# The chart's own fixed frame.
CHART_SIZE = (800, 600)


# --------------------------------------------------------------------------
# Synthetic pieces
# --------------------------------------------------------------------------
def _ruling(
    ruling: str,
    amount: Any = None,
    driver: Any = None,
    referrals: Sequence[str] = (),
) -> Dict[str, Any]:
    """A judge result object, as a transcript entry's ``parsed`` holds it."""
    return {
        "ruling": {
            "ruling": ruling,
            "amount_sgd": amount,
            "driver_compensation_sgd": driver,
            "referrals": list(referrals),
            "confidence": "0.9",
        }
    }


def _draft(index: int, kind: str, valid: bool = True) -> Dict[str, Any]:
    return {"draft": index, "kind": kind, "valid": valid, "entries": [index]}


def _transcript(
    parsed: Sequence[Mapping[str, Any]], drafts: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    return {"entries": [{"parsed": entry} for entry in parsed], "vote": {"drafts": list(drafts)}}


def _key_ruling(
    ruling: str, amount: Any = None, driver: Any = None
) -> grade.Ruling:
    return grade.Ruling(
        case_no=1,
        ruling=ruling,
        amount_sgd=amount,
        driver_compensation_sgd=driver,
    )


def _outcome(
    confidence: str, correct: bool, case_no: int = 1, ruling: str = "PARTIAL_REFUND"
) -> fairness.DraftOutcome:
    return fairness.DraftOutcome(
        case_no, "sampled", Decimal(confidence), correct, ruling
    )


# --------------------------------------------------------------------------
# 1. The classification of each ruling value
# --------------------------------------------------------------------------
class TheRulingVocabularyTests(unittest.TestCase):
    """Every value the policy licenses falls in exactly one side."""

    def test_every_licensed_value_is_classified(self) -> None:
        vocabulary = grade.ruling_values()
        self.assertTrue(vocabulary, "the policy licenses no ruling value at all")
        classified = {value: side for value, side in fairness.classify_vocabulary()}
        self.assertEqual(
            sorted(classified), sorted(vocabulary), "a licensed value is unclassified"
        )

    def test_each_value_falls_in_the_side_the_sheet_names(self) -> None:
        for value, expected in EXPECTED_SIDES.items():
            with self.subTest(ruling=value):
                self.assertEqual(fairness.side_of(value), expected)

    def test_the_three_groups_are_the_whole_vocabulary(self) -> None:
        grouped = (
            set(fairness.RIDER_FAVOURING)
            | set(fairness.DRIVER_FAVOURING)
            | set(fairness.NEITHER_SIDE)
        )
        self.assertEqual(grouped, set(grade.ruling_values()))
        self.assertEqual(
            len(fairness.RIDER_FAVOURING)
            + len(fairness.DRIVER_FAVOURING)
            + len(fairness.NEITHER_SIDE),
            len(grouped),
            "a ruling value is in more than one group",
        )

    def test_a_value_outside_the_vocabulary_has_no_side(self) -> None:
        self.assertIsNone(fairness.side_of("MADE_UP"))
        self.assertIsNone(fairness.side_of(None))


# --------------------------------------------------------------------------
# 2. The directions a differing case can move
# --------------------------------------------------------------------------
class TheErrorDirectionTests(unittest.TestCase):
    """The direction a case moved, on rulings built for the purpose."""

    def test_a_decided_case_escalated_moved_to_an_escalation(self) -> None:
        movement = fairness.movement_for(
            1, _key_ruling("PARTIAL_REFUND", Decimal("7.45")), _key_ruling("ESCALATE")
        )
        self.assertEqual(movement.direction, fairness.TO_ESCALATION)

    def test_an_escalation_decided_moved_away_from_one(self) -> None:
        movement = fairness.movement_for(
            2, _key_ruling("ESCALATE"), _key_ruling("NO_ACTION")
        )
        self.assertEqual(movement.direction, fairness.AWAY_FROM_ESCALATION)

    def test_a_rider_key_ruled_for_the_driver_moved_towards_the_driver(self) -> None:
        movement = fairness.movement_for(
            3,
            _key_ruling("PARTIAL_REFUND", Decimal("2.00")),
            _key_ruling("DRIVER_COMPENSATION", Decimal("3.20"), Decimal("3.20")),
        )
        self.assertEqual(movement.direction, fairness.TOWARDS_DRIVER)

    def test_a_bigger_refund_moved_towards_the_rider(self) -> None:
        movement = fairness.movement_for(
            4,
            _key_ruling("PARTIAL_REFUND", Decimal("7.45")),
            _key_ruling("FULL_REFUND", Decimal("9.00")),
        )
        self.assertEqual(movement.direction, fairness.TOWARDS_RIDER)
        self.assertEqual(movement.amount_note, "the refund moved from 7.45 to 9.00")

    def test_a_smaller_refund_moved_towards_the_driver(self) -> None:
        movement = fairness.movement_for(
            5,
            _key_ruling("PARTIAL_REFUND", Decimal("7.45")),
            _key_ruling("PARTIAL_REFUND", Decimal("3.00")),
        )
        self.assertEqual(movement.direction, fairness.TOWARDS_DRIVER)

    def test_a_case_with_no_ruling_moved_nowhere(self) -> None:
        movement = fairness.movement_for(6, _key_ruling("ESCALATE"), None)
        self.assertEqual(movement.direction, fairness.NO_RULING)
        self.assertIsNone(movement.produced)


# --------------------------------------------------------------------------
# 3. The position swap, on synthetic drafts
# --------------------------------------------------------------------------
class ThePositionSwapTests(unittest.TestCase):
    """The swapped draft against the sampled majority, on drafts built here."""

    def _three_sampled_and_one_swapped(self, swapped: Mapping[str, Any]) -> Dict[str, Any]:
        agreeing = _ruling("PARTIAL_REFUND", "7.45")
        return _transcript(
            [agreeing, agreeing, agreeing, swapped],
            [
                _draft(0, "sampled"),
                _draft(1, "sampled"),
                _draft(2, "sampled"),
                _draft(3, "position_swapped"),
            ],
        )

    def test_a_swapped_draft_that_agrees_is_counted_as_agreeing(self) -> None:
        transcript = self._three_sampled_and_one_swapped(
            _ruling("PARTIAL_REFUND", "7.45")
        )
        swap = fairness.position_swap({10: transcript})
        self.assertEqual(swap.total, 1)
        self.assertEqual(swap.agree_all_four, 1)
        self.assertEqual(swap.agree_ruling, 1)
        self.assertEqual(swap.disagreements(), ())
        self.assertEqual(swap.ruling_disagreements(), ())

    def test_a_swapped_draft_that_disagrees_on_the_ruling_is_listed(self) -> None:
        transcript = self._three_sampled_and_one_swapped(_ruling("ESCALATE"))
        swap = fairness.position_swap({11: transcript})
        self.assertEqual(swap.total, 1)
        self.assertEqual(swap.agree_all_four, 0)
        self.assertEqual(swap.agree_ruling, 0)
        self.assertEqual(swap.disagreements(), (11,))
        self.assertEqual(swap.ruling_disagreements(), (11,))

    def test_a_swapped_draft_that_agrees_on_the_label_but_not_the_money(self) -> None:
        transcript = self._three_sampled_and_one_swapped(
            _ruling("PARTIAL_REFUND", "9.00")
        )
        swap = fairness.position_swap({12: transcript})
        self.assertEqual(swap.agree_ruling, 1, "the label is the same label")
        self.assertEqual(swap.agree_all_four, 0, "the money is not the same money")
        self.assertEqual(swap.disagreements(), (12,))
        self.assertEqual(swap.ruling_disagreements(), ())

    def test_a_case_with_no_valid_swapped_draft_is_out_of_the_denominator(self) -> None:
        agreeing = _ruling("PARTIAL_REFUND", "7.45")
        transcript = _transcript(
            [agreeing, agreeing, agreeing, agreeing],
            [
                _draft(0, "sampled"),
                _draft(1, "sampled"),
                _draft(2, "sampled"),
                _draft(3, "position_swapped", valid=False),
            ],
        )
        swap = fairness.position_swap({13: transcript})
        self.assertEqual(swap.total, 0)

    def test_the_two_synthetic_cases_are_counted_apart(self) -> None:
        agreeing = self._three_sampled_and_one_swapped(_ruling("PARTIAL_REFUND", "7.45"))
        disagreeing = self._three_sampled_and_one_swapped(_ruling("ESCALATE"))
        swap = fairness.position_swap({20: agreeing, 21: disagreeing})
        self.assertEqual(swap.total, 2)
        self.assertEqual(swap.agree_all_four, 1)
        self.assertEqual(swap.agree_ruling, 1)
        self.assertEqual(swap.disagreements(), (21,))
        self.assertEqual(swap.ruling_disagreements(), (21,))


# --------------------------------------------------------------------------
# 4. Calibration, on a set whose error is known by hand
# --------------------------------------------------------------------------
class TheCalibrationTests(unittest.TestCase):
    """The expected error of a synthetic set, and the bins it is summed over."""

    def setUp(self) -> None:
        # 10 drafts at 0.60, 5 of them right; 4 at 0.85, 2 right; 6 at 0.95,
        # all 6 right. ECE = (10/20)*0.10 + (4/20)*0.35 + (6/20)*0.05 = 0.135.
        self.outcomes: Tuple[fairness.DraftOutcome, ...] = tuple(
            [_outcome("0.6", i < 5, case_no=1) for i in range(10)]
            + [_outcome("0.85", i < 2, case_no=2) for i in range(4)]
            + [_outcome("0.95", True, case_no=3) for i in range(6)]
        )
        self.calibration = fairness.calibrate(self.outcomes)

    def test_the_expected_calibration_error_is_the_known_value(self) -> None:
        self.assertEqual(self.calibration.ece, Decimal("0.135"))

    def test_the_counts_land_in_the_bins_the_edges_name(self) -> None:
        self.assertEqual(
            [bin_.count for bin_ in self.calibration.bins], [0, 10, 0, 4, 6]
        )

    def test_each_bins_mean_confidence_and_share_correct(self) -> None:
        by_count = {bin_.count: bin_ for bin_ in self.calibration.bins if bin_.count}
        self.assertEqual(by_count[10].mean_confidence, Decimal("0.6"))
        self.assertEqual(by_count[10].correct, 5)
        self.assertEqual(by_count[4].mean_confidence, Decimal("0.85"))
        self.assertEqual(by_count[4].share_correct, Decimal("0.5"))
        self.assertEqual(by_count[6].share_correct, Decimal("1"))

    def test_the_floor_splits_the_drafts(self) -> None:
        self.assertEqual(self.calibration.below_floor, (5, 10))
        self.assertEqual(self.calibration.at_or_above_floor, (8, 10))

    def test_an_empty_set_has_no_error_rather_than_a_missing_one(self) -> None:
        empty = fairness.calibrate(())
        self.assertEqual(empty.total, 0)
        self.assertEqual(empty.ece, Decimal(0))
        self.assertEqual(empty.below_floor, (0, 0))

    def test_the_error_grows_when_a_confident_bin_is_wrong(self) -> None:
        worse = tuple(
            [_outcome("0.95", False, case_no=1) for _ in range(6)]
        )
        self.assertGreater(fairness.calibrate(worse).ece, Decimal(0))


# --------------------------------------------------------------------------
# 4b. What the low bins hold, on a set built for the purpose
# --------------------------------------------------------------------------
class TheEscalateSplitTests(unittest.TestCase):
    """How many drafts escalate, and how often the rest are right.

    The split is the one ``--report`` prints beside the floor split, and it
    exists because a draft that proposes ``ESCALATE`` decides nothing: a
    below-floor group that is all escalations has a share correct that says
    nothing about whether the judge can decide a case.
    """

    def setUp(self) -> None:
        # Below the floor: two escalate, one decides and is right, one decides
        # and is wrong. At or above it: one escalates, two decide and are right,
        # one decides and is wrong.
        self.outcomes: Tuple[fairness.DraftOutcome, ...] = tuple(
            [
                _outcome("0.3", True, case_no=1, ruling="ESCALATE"),
                _outcome("0.4", True, case_no=2, ruling="ESCALATE"),
                _outcome("0.6", True, case_no=3, ruling="PARTIAL_REFUND"),
                _outcome("0.6", False, case_no=4, ruling="NO_ACTION"),
                _outcome("0.9", True, case_no=5, ruling="ESCALATE"),
                _outcome("0.9", True, case_no=6, ruling="PARTIAL_REFUND"),
                _outcome("0.8", True, case_no=7, ruling="FULL_REFUND"),
                _outcome("0.85", False, case_no=8, ruling="NO_ACTION"),
            ]
        )
        self.split = fairness.escalate_split(self.outcomes)

    def test_below_the_floor_escalations_and_the_rest(self) -> None:
        self.assertEqual(self.split.below_escalate, 2)
        self.assertEqual(self.split.below_total, 4)
        self.assertEqual(self.split.below_other, (1, 2))

    def test_at_or_above_the_floor_escalations_and_the_rest(self) -> None:
        self.assertEqual(self.split.above_escalate, 1)
        self.assertEqual(self.split.above_total, 4)
        self.assertEqual(self.split.above_other, (2, 3))

    def test_a_group_that_only_escalates_has_no_share_correct(self) -> None:
        split = fairness.escalate_split(
            (_outcome("0.3", True, case_no=1, ruling="ESCALATE"),)
        )
        self.assertEqual(split.below_escalate, 1)
        self.assertEqual(split.below_total, 1)
        self.assertEqual(split.below_other, (0, 0))
        self.assertEqual(split.above_total, 0)

    def test_the_share_correct_among_the_rest_is_rendered(self) -> None:
        self.assertEqual(
            fairness._other_rate(self.split.below_other), "1/2 = 50.0%"
        )
        self.assertEqual(
            fairness._other_rate(self.split.above_other), "2/3 = 66.7%"
        )

    def test_a_group_with_no_non_escalating_draft_reads_none(self) -> None:
        self.assertEqual(fairness._other_rate((0, 0)), "none (0 drafts)")

    def test_the_floor_split_and_the_escalate_split_agree_on_the_groups(self) -> None:
        calibration = fairness.calibrate(self.outcomes)
        self.assertEqual(
            self.split.below_total, calibration.below_floor[1]
        )
        self.assertEqual(
            self.split.above_total, calibration.at_or_above_floor[1]
        )


# --------------------------------------------------------------------------
# 5. The committed chart, and what the report reads
# --------------------------------------------------------------------------
def _report_recording_opens() -> Tuple[str, List[str]]:
    """Run the report with every file it opens recorded."""
    opened: List[str] = []
    real_open = pathlib.Path.open

    def spy(self, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(self))
        return real_open(self, *args, **kwargs)

    with mock.patch.object(pathlib.Path, "open", spy):
        text = fairness.report()
    return text, opened


class TheCommittedChartAndTheReportTests(unittest.TestCase):
    """The chart equals a fresh build, and the report opens only what it may."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.runs = {name: fairness.measured_run(name) for name in fairness.MEASURED_SETS}
        cls.transcripts = {
            name: fairness.transcripts(cls.runs[name]) for name in fairness.MEASURED_SETS
        }
        cls.calibration = fairness.chart_path_from(cls.runs, cls.transcripts)
        cls.report_text, cls.opened = _report_recording_opens()

    def test_the_chart_is_a_file_that_parses(self) -> None:
        import xml.etree.ElementTree as ET

        self.assertTrue(CHART_PATH.is_file(), "docs/calibration-v6.svg is missing")
        root = ET.fromstring(CHART_PATH.read_text(encoding="utf-8"))
        self.assertEqual(root.get("width"), str(CHART_SIZE[0]))
        self.assertEqual(root.get("height"), str(CHART_SIZE[1]))
        self.assertEqual(
            root.get("viewBox"), "0 0 {0} {1}".format(*CHART_SIZE)
        )

    def test_the_committed_chart_equals_a_fresh_build(self) -> None:
        fresh = fairness.chart_svg(self.calibration, "both development runs pooled")
        self.assertEqual(
            CHART_PATH.read_text(encoding="utf-8"),
            fresh,
            "docs/calibration-v6.svg differs from a fresh build",
        )

    def test_the_chart_is_ascii_and_carries_no_script(self) -> None:
        data = CHART_PATH.read_bytes()
        offenders = sorted({byte for byte in data if byte > 127})
        self.assertEqual(offenders, [], "the chart holds non-ASCII bytes")
        self.assertNotIn(b"<script", data)
        self.assertNotIn(b"onload", data)

    def test_the_chart_draws_the_floor_and_the_diagonal(self) -> None:
        text = CHART_PATH.read_text(encoding="utf-8")
        self.assertIn("{0} floor".format(fairness._floor_text()), text)
        self.assertIn("perfect calibration", text)
        # One point per non-empty bin.
        drawn = text.count("<circle ")
        non_empty = sum(1 for bin_ in self.calibration.bins if bin_.count)
        self.assertEqual(drawn, non_empty)

    def test_the_report_opens_no_answer_path_but_the_two_keys(self) -> None:
        opened = {Path(path).resolve() for path in self.opened}
        under_answers = {
            path for path in opened if "eval" in path.parts and "answers" in path.parts
        }
        self.assertEqual(
            under_answers,
            set(PERMITTED_KEYS),
            "the report opened an answer path other than the two keys",
        )

    def test_the_report_opens_nothing_under_a_sealed_root(self) -> None:
        sealed = sorted(
            path for path in self.opened if "sealed-v1" in path or "sealed_v1" in path
        )
        self.assertEqual(sealed, [], "the report opened a sealed path")

    def test_the_report_states_the_three_measurements(self) -> None:
        for heading in (
            "== 1. Which way the errors lean ==",
            "== 2. The position swap ==",
            "== 3. Calibration ==",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.report_text)
        self.assertIn("drafts of one case are not independent", self.report_text)
        self.assertIn("drafts proposing ESCALATE", self.report_text)
        self.assertIn(
            "share correct among the drafts that do not propose ESCALATE",
            self.report_text,
        )

    def test_the_chart_command_refuses_a_sealed_destination(self) -> None:
        target = PROJECT_ROOT / "runs" / "wild-v2" / "calibration.svg"
        self.assertFalse(target.exists(), "the test would overwrite a committed file")
        code = fairness.main(["--chart", str(target)])
        self.assertEqual(code, 1, "a sealed destination was not refused")
        self.assertFalse(target.exists(), "a file was written into a sealed root")


# --------------------------------------------------------------------------
# 6. Importing the module opens no sealed path
# --------------------------------------------------------------------------
# The probe records every file opened, at import as well as at run time. It
# patches ``pathlib.Path.open`` and ``io.open`` rather than ``builtins.open``:
# ``pathlib`` calls ``io.open`` directly, so a probe that patched only
# ``builtins.open`` would record nothing and pass for the wrong reason.
_PROBE = (
    "import io, pathlib, sys\n"
    "opened = []\n"
    "_path_open = pathlib.Path.open\n"
    "_io_open = io.open\n"
    "def _record(value):\n"
    "    opened.append(str(value))\n"
    "def spy_path_open(self, *a, **k):\n"
    "    _record(self)\n"
    "    return _path_open(self, *a, **k)\n"
    "def spy_io_open(file, *a, **k):\n"
    "    _record(file)\n"
    "    return _io_open(file, *a, **k)\n"
    "pathlib.Path.open = spy_path_open\n"
    "io.open = spy_io_open\n"
    "{body}\n"
    "sys.stdout.write('\\n'.join(opened))\n"
)


def _run_probe(body: str) -> List[str]:
    """Run ``body`` in a fresh interpreter with every file it opens recorded."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(body=body)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError("the probe failed: {0}".format(result.stderr))
    return [line for line in result.stdout.splitlines() if line]


class TheModuleOpensNoSealedPathTests(unittest.TestCase):
    """``eval.fairness`` opens no sealed path, at import or at run time.

    This is the reason the draft reading is written out in the module rather
    than imported from ``ops``: importing the ops layer executes
    ``eval.development_sets``, which opens every registered set's ``index.json``
    at import. The control below shows the probe is capable of reporting a path
    that carries the marker, so a clean answer is not a probe that stopped
    working.
    """

    def test_the_probe_reports_a_path_that_carries_the_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sealed-v1" / "probe.json"
            target.parent.mkdir(parents=True)
            target.write_text("{}", encoding="utf-8")
            opened = _run_probe(
                "pathlib.Path({0!r}).read_text()\n".format(str(target))
            )
        self.assertTrue(
            [path for path in opened if "sealed-v1" in path],
            "the probe reported no path carrying the marker: {0}".format(opened),
        )

    def test_importing_the_module_opens_no_sealed_path(self) -> None:
        opened = _run_probe("import eval.fairness\n")
        sealed = sorted(path for path in opened if "sealed" in path)
        self.assertEqual(
            sealed, [], "importing eval.fairness opened a sealed path"
        )


if __name__ == "__main__":
    unittest.main()
