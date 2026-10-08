"""Tests for ``tribunal.prepass``.

Every test asserts against the real files under ``data/``. Run from the
project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import loader, prepass  # noqa: E402

INDEX_PATH = PROJECT_ROOT / "data" / "index.json"


def manifest_case_numbers():
    """Every case number in the real manifest."""
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return [entry["case_no"] for entry in json.load(handle)]


def all_artifacts():
    """(case_no, artifact) for every artifact in the corpus."""
    for case_no in manifest_case_numbers():
        case = loader.load_case(case_no)
        for artifact in case["evidence"]:
            yield case_no, artifact


class WeightForTests(unittest.TestCase):
    """Part 1: the derived weight arithmetic, checked against the corpus."""

    def test_weight_for_reproduces_all_non_complete_weights(self):
        """weight_for must reproduce the declared weight of all 45 artifacts."""
        checked, matched, mismatches = 0, 0, []
        for case_no, artifact in all_artifacts():
            admissibility = artifact["admissibility"]
            if admissibility["status"] == "COMPLETE":
                continue
            checked += 1
            declared = admissibility["weight_multiplier"]
            derived = prepass.weight_for(admissibility["issues"])
            # The declared weight now arrives as a Decimal, because the loader
            # parses every JSON number written with a decimal point that way.
            # weight_for computes a float, so compare in Decimal: a float
            # comparison against Decimal("0.3") is exact and would fail.
            if Decimal(str(derived)) == declared:
                matched += 1
            else:
                mismatches.append(
                    (case_no, artifact["evidence_id"], admissibility["issues"], declared, derived)
                )

        self.assertEqual(checked, 45, "expected 45 non-COMPLETE artifacts")
        self.assertEqual(
            mismatches, [], "weight_for disagreed with the corpus on: {0}".format(mismatches)
        )
        self.assertEqual(matched, 45, "matched {0} of 45".format(matched))

    def test_weight_for_reproduces_every_declared_corpus_weight(self):
        """All 204 artifacts, in one place, with the count.

        The two tests around this one cover the 45 non-COMPLETE artifacts and
        the 159 COMPLETE ones separately. This states the whole-corpus claim
        once, because 204 is the figure the Decimal change had to leave exactly
        where it was: if it moved, the corpus's own arithmetic would have been
        rewritten rather than reproduced.
        """
        checked, mismatches = 0, []
        for case_no, artifact in all_artifacts():
            admissibility = artifact["admissibility"]
            checked += 1
            declared = admissibility["weight_multiplier"]
            derived = prepass.weight_for(admissibility["issues"])
            if Decimal(str(derived)) != declared:
                mismatches.append(
                    (
                        case_no,
                        artifact["evidence_id"],
                        admissibility["issues"],
                        declared,
                        derived,
                    )
                )

        self.assertEqual(204, checked, "the corpus is not the expected 204 artifacts")
        self.assertEqual(
            [],
            mismatches,
            "weight_for disagreed with the corpus on: {0}".format(mismatches),
        )

    def test_a_dirty_binary_product_is_quantised_to_the_corpus_convention(self):
        """The combination that exposed the floating-point residue.

        ``0.8 * 0.75`` is ``0.6000000000000001`` in binary floating point. Every
        multi-code weight the corpus declares is a clean two-decimal figure --
        0.39, 0.3, 0.25 -- and the float product reproduced them only because
        none of those particular combinations happens to leave a residue. The
        corpus carries no artifact with this pair, so none of the 45 caught it;
        the first converted external case to use it did.
        """
        derived = prepass.weight_for(["LOW_SAMPLE_RATE", "PARTIAL_RECORD"])
        self.assertEqual(0.6, derived)
        self.assertNotEqual(
            0.8 * 0.75,
            derived,
            "the raw binary product is not the number the corpus would write",
        )

    def test_every_derived_weight_is_a_two_decimal_figure(self):
        """No combination of codes may produce a weight carrying a residue.

        Exhaustive over every one-, two- and three-code combination, which is
        what a spot check on the one combination that was known to be dirty
        would not have covered.
        """
        from itertools import combinations  # noqa: PLC0415 - used once, here

        codes = sorted(prepass.CODE_WEIGHTS)
        checked = 0
        for size in (1, 2, 3):
            for combo in combinations(codes, size):
                with self.subTest(codes=combo):
                    value = prepass.weight_for(combo)
                    checked += 1
                    self.assertEqual(
                        Decimal(str(value)),
                        Decimal(str(value)).quantize(prepass.TWO_PLACES),
                        "a derived weight carries a floating-point residue",
                    )
        self.assertGreater(checked, 800, "too few combinations checked to be a proof")

    def test_weight_for_is_full_weight_for_no_issues(self):
        """An empty issue list weighs 1.0, matching all 159 COMPLETE artifacts."""
        self.assertEqual(prepass.weight_for([]), 1.0)

        complete = 0
        for _case_no, artifact in all_artifacts():
            admissibility = artifact["admissibility"]
            if admissibility["status"] != "COMPLETE":
                continue
            complete += 1
            self.assertEqual(admissibility["issues"], [])
            self.assertEqual(prepass.weight_for(admissibility["issues"]), 1.0)
            self.assertEqual(admissibility["weight_multiplier"], 1.0)
        self.assertEqual(complete, 159)

    def test_missing_artifacts_weigh_zero(self):
        """All 27 MISSING artifacts weigh 0.0 under weight_for."""
        missing = 0
        for _case_no, artifact in all_artifacts():
            admissibility = artifact["admissibility"]
            if admissibility["status"] != "MISSING":
                continue
            missing += 1
            self.assertIsNone(artifact["payload"])
            self.assertEqual(prepass.weight_for(admissibility["issues"]), 0.0)
            self.assertEqual(admissibility["weight_multiplier"], 0.0)
        self.assertEqual(missing, 27)


class SchemaVersionDetectorTests(unittest.TestCase):
    """Part 2: the one detector the workspace can justify."""

    def test_case_202_reports_the_single_outlier(self):
        """Case 202 has exactly one artifact whose schema_version differs."""
        case = loader.load_case(202)
        self.assertEqual(prepass.detect_schema_version_mismatch(case), ["EV-DPROF-00202"])

    def test_every_other_case_reports_nothing(self):
        """No other case has an artifact whose schema_version differs."""
        offenders = {}
        for case_no in manifest_case_numbers():
            case = loader.load_case(case_no)
            found = prepass.detect_schema_version_mismatch(case)
            if case_no == 202:
                self.assertEqual(found, ["EV-DPROF-00202"])
            elif found:
                offenders[case_no] = found
        self.assertEqual(offenders, {})


def policy_weights():
    """The weight table the version-3 policy states."""
    document = json.loads(
        (PROJECT_ROOT / "policy" / "v3" / "no_show.json").read_text(encoding="utf-8"),
        parse_float=Decimal,
    )
    return prepass.weights_from_policy(document)


def policy_threshold():
    """POL-NS-08(b)'s gap threshold, as the version-3 policy states it."""
    document = json.loads(
        (PROJECT_ROOT / "policy" / "v3" / "no_show.json").read_text(encoding="utf-8")
    )
    return prepass.gps_gap_threshold_from_policy(document)


# A waiting window for the fixtures below: ten minutes of a trip that was
# cancelled at its end.
WINDOW = ("2026-08-06T12:00:00+08:00", "2026-08-06T12:10:00+08:00")


def gap(from_ts, to_ts, duration):
    """One recorded gap, in the shape the trace carries."""
    return {"from_ts": from_ts, "to_ts": to_ts, "duration_sec": duration}


class PolicyWeightTableTests(unittest.TestCase):
    """The weights the policy states, and the codes they know."""

    def test_the_table_holds_the_three_variants_and_not_the_bare_tag(self):
        weights = policy_weights()
        for variant in prepass.GPS_GAP_VARIANTS:
            with self.subTest(variant=variant):
                self.assertIn(variant, weights)
        self.assertNotIn(
            prepass.GPS_GAP_CODE,
            weights,
            "the policy's table still carries the ungraded GPS_GAP tag",
        )

    def test_the_table_holds_every_code_the_corpus_uses_apart_from_the_tag(self):
        used = set()
        for _case_no, artifact in all_artifacts():
            used.update(prepass.issue_codes_of(artifact))
        used.discard(prepass.GPS_GAP_CODE)
        weights = policy_weights()
        missing = sorted(code for code in used if code not in weights)
        self.assertEqual([], missing, "the policy's table is missing a corpus code")

    def test_the_table_reproduces_every_declared_weight_that_is_not_a_gap(self):
        """With the policy's own table, every non-gap artifact weighs as declared."""
        weights = policy_weights()
        checked = 0
        for case_no, artifact in all_artifacts():
            codes = prepass.issue_codes_of(artifact)
            if not codes or prepass.GPS_GAP_CODE in codes:
                continue
            declared = Decimal(str(artifact["admissibility"]["weight_multiplier"]))
            with self.subTest(case_no=case_no, evidence_id=artifact["evidence_id"]):
                self.assertEqual(
                    declared, Decimal(str(prepass.weight_for(codes, weights=weights)))
                )
            checked += 1
        self.assertGreater(checked, 40)

    def test_the_corpus_gaps_grade_as_the_note_says(self):
        """The corpus's three ``GPS_GAP`` artifacts, pinned: variant and weight.

        The other three live in the development sets; the full table is in
        ``docs/notes/2026-10-08-policy-version-3.md``. These three are pinned
        here because they are the corpus's own, and because two of them are the
        two whose weight does not move.
        """
        weights = policy_weights()
        threshold = policy_threshold()
        expected = {
            110: (prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW, Decimal("0.55")),
            210: (prepass.GPS_GAP_LONG_INSIDE_WINDOW, Decimal("0.25")),
            211: (prepass.GPS_GAP_LONG_INSIDE_WINDOW, Decimal("0.39")),
        }
        seen = {}
        for case_no, artifact in all_artifacts():
            codes = prepass.issue_codes_of(artifact)
            if prepass.GPS_GAP_CODE not in codes:
                continue
            trip = next(
                entry["payload"]
                for entry in loader.load_case(case_no)["evidence"]
                if entry["evidence_type"] == "TRIP_RECORD"
            )
            window = None
            if trip.get("arrived_at") and trip.get("cancelled_at"):
                window = (trip["arrived_at"], trip["cancelled_at"])
            gaps = prepass.gaps_from_points(
                (artifact.get("payload") or {}).get("points")
            )
            variant = prepass.gps_gap_variant(gaps, window, threshold)
            graded = [
                variant if code == prepass.GPS_GAP_CODE else code for code in codes
            ]
            seen[case_no] = (
                variant,
                Decimal(str(prepass.weight_for(graded, weights=weights))),
            )
        self.assertEqual(expected, seen)

    def test_the_threshold_is_the_policys_own(self):
        self.assertEqual(120, policy_threshold())

    def test_a_policy_with_no_integrity_block_is_refused(self):
        with self.assertRaises(prepass.UnknownIssueCodeError):
            prepass.weights_from_policy({"policy_id": "POLICY-NO-SHOW"})


class GpsGapVariantTests(unittest.TestCase):
    """POL-NS-08(b)'s three variants, one fixture each."""

    def classify(self, gaps, window=WINDOW):
        return prepass.gps_gap_variant(gaps, window, policy_threshold())

    def test_a_gap_of_at_most_the_threshold_is_short(self):
        self.assertEqual(
            prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW,
            self.classify([gap("2026-08-06T12:01:00+08:00", "2026-08-06T12:03:00+08:00", 120.0)]),
        )

    def test_a_long_gap_outside_the_window_is_short_or_outside(self):
        self.assertEqual(
            prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW,
            self.classify(
                [gap("2026-08-06T11:00:00+08:00", "2026-08-06T11:30:00+08:00", 1800.0)]
            ),
        )

    def test_a_long_gap_inside_the_window_is_long_inside(self):
        self.assertEqual(
            prepass.GPS_GAP_LONG_INSIDE_WINDOW,
            self.classify(
                [gap("2026-08-06T12:03:00+08:00", "2026-08-06T12:06:00+08:00", 180.0)]
            ),
        )

    def test_a_long_gap_that_contains_the_cancellation_straddles_it(self):
        self.assertEqual(
            prepass.GPS_GAP_STRADDLING_CANCELLATION,
            self.classify(
                [gap("2026-08-06T12:08:00+08:00", "2026-08-06T12:12:00+08:00", 240.0)]
            ),
        )

    def test_a_short_gap_that_contains_the_cancellation_is_still_short(self):
        """POL-NS-08(b) grades by length first: a short gap engages nothing."""
        self.assertEqual(
            prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW,
            self.classify(
                [gap("2026-08-06T12:09:30+08:00", "2026-08-06T12:10:30+08:00", 60.0)]
            ),
        )

    def test_a_record_with_no_waiting_window_has_no_gap_inside_it(self):
        self.assertEqual(
            prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW,
            self.classify(
                [gap("2026-08-06T12:03:00+08:00", "2026-08-06T12:06:00+08:00", 180.0)],
                window=None,
            ),
        )

    def test_a_trace_with_no_readable_gap_is_short_or_outside(self):
        self.assertEqual(
            prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW, self.classify([])
        )

    def test_the_gaps_are_computed_from_the_traces_own_points(self):
        points = [
            {"ts": "2026-08-06T12:00:00+08:00"},
            {"ts": "2026-08-06T12:01:00+08:00"},
            {"ts": "2026-08-06T12:04:00+08:00"},
        ]
        self.assertEqual(
            [
                {
                    "from_ts": "2026-08-06T12:00:00+08:00",
                    "to_ts": "2026-08-06T12:01:00+08:00",
                    "duration_sec": 60.0,
                },
                {
                    "from_ts": "2026-08-06T12:01:00+08:00",
                    "to_ts": "2026-08-06T12:04:00+08:00",
                    "duration_sec": 180.0,
                },
            ],
            prepass.gaps_from_points(points),
        )

    def test_an_unreadable_point_is_skipped_rather_than_guessed_at(self):
        points = [{"ts": "2026-08-06T12:00:00+08:00"}, {"ts": None}, {"ts": "not a stamp"}]
        self.assertEqual([], prepass.gaps_from_points(points))


if __name__ == "__main__":
    unittest.main(verbosity=2)
