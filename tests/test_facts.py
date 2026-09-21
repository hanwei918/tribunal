"""Tests for ``tribunal.facts``.

Every test asserts against the real files under ``data/`` and ``policy/``. The
policy numbers are read from the policy files, never typed in. Run from the
project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import json
import sys
import tokenize
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, facts, loader  # noqa: E402

FACTS_SOURCE = PROJECT_ROOT / "tribunal" / "facts.py"


def policy_file(name: str) -> dict:
    """One real policy file, read straight from policy/."""
    with (PROJECT_ROOT / "policy" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def artifact_payload(case_no: int, evidence_type: str):
    """The payload of one artifact of a given type, straight from the corpus."""
    case = loader.load_case(case_no)
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == evidence_type:
            return artifact["payload"]
    raise AssertionError("case {0} has no {1} artifact".format(case_no, evidence_type))


class Case208Tests(unittest.TestCase):
    """Case 208 is a NO_SHOW_CHARGE case at a LARGE_VENUE pickup."""

    @classmethod
    def setUpClass(cls):
        cls.trip = artifact_payload(208, "TRIP_RECORD")
        cls.gps = artifact_payload(208, "GPS_TRACE")

        cls.pickup = cls.trip["pickup"]
        cls.lat = cls.pickup["lat"]
        cls.lng = cls.pickup["lng"]

        cls.driver = facts.driver_points(cls.gps)
        cls.rider = facts.rider_points(cls.gps)

        # Every threshold below is read from the loaded policy, keyed by the
        # zone class the trip record itself declares. None is typed in.
        cls.zone = cls.trip["pickup_zone_class"]
        fee_schedule = policy_file("no_show.json")["fee_schedule"]
        cls.arrival_radius_m = fee_schedule["arrival_radius_m"][cls.zone]
        cls.rider_presence_radius_m = fee_schedule["rider_presence_radius_m"][cls.zone]
        cls.accuracy_max_m = fee_schedule["gps_accuracy_filter_m"]

    # 1
    def test_1_closest_driver_fix_is_28_8_metres(self):
        """The closest driver fix to the pickup point is 28.8 m to one decimal place."""
        distances = facts.distances_to_point(self.driver, self.lat, self.lng)
        self.assertEqual(len(distances), 120)
        self.assertEqual(round(min(distances), 1), 28.8)

    # 2
    def test_2_sixty_qualifying_driver_fixes(self):
        """Exactly 60 of the 120 driver fixes qualify inside the arrival radius."""
        qualifying = facts.qualifying_fixes(
            self.driver, self.lat, self.lng, self.arrival_radius_m, self.accuracy_max_m
        )
        self.assertEqual(len(self.driver), 120)
        self.assertEqual(len(qualifying), 60)

    # 3
    def test_3_longest_qualifying_run(self):
        """The longest consecutive run is 60 fixes, 16:02:10 to 16:11:55, 585.0 s."""
        run = facts.longest_qualifying_run(
            self.driver, self.lat, self.lng, self.arrival_radius_m, self.accuracy_max_m
        )
        self.assertEqual(run["fix_count"], 60)
        self.assertEqual(run["first_ts"], "2026-07-30T16:02:10+08:00")
        self.assertEqual(run["last_ts"], "2026-07-30T16:11:55+08:00")
        self.assertEqual(run["duration_sec"], 585.0)

    # 4
    def test_4_dwell_clock_starts_before_arrived_at(self):
        """The first qualifying fix is 15 s earlier than the trip record's arrived_at."""
        run = facts.longest_qualifying_run(
            self.driver, self.lat, self.lng, self.arrival_radius_m, self.accuracy_max_m
        )
        self.assertEqual(run["first_ts"], "2026-07-30T16:02:10+08:00")
        self.assertEqual(self.trip["arrived_at"], "2026-07-30T16:02:25+08:00")
        self.assertEqual(facts.elapsed_seconds(run["first_ts"], self.trip["arrived_at"]), 15.0)

    # 5
    def test_5_rider_track_shape_and_distances(self):
        """141 rider fixes, every one at 0.0 kph, between 633.9 m and 646.4 m."""
        self.assertEqual(len(self.rider), 141)
        self.assertTrue(all(fix["speed_kph"] == 0.0 for fix in self.rider))

        summary = facts.track_summary(self.rider, self.lat, self.lng)
        self.assertEqual(summary["fix_count"], 141)
        self.assertEqual(summary["distinct_speeds_kph"], [0.0])
        self.assertEqual(round(summary["min_distance_m"], 1), 633.9)
        self.assertEqual(round(summary["max_distance_m"], 1), 646.4)

    # 6
    def test_6_no_rider_fix_is_inside_the_presence_radius(self):
        """With the rider presence radius, 0 of the 141 rider fixes are inside."""
        distances = facts.distances_to_point(self.rider, self.lat, self.lng)
        inside = [d for d in distances if d <= self.rider_presence_radius_m]
        self.assertEqual(len(distances), 141)
        self.assertEqual(len(inside), 0)

        qualifying = facts.qualifying_fixes(
            self.rider, self.lat, self.lng, self.rider_presence_radius_m, self.accuracy_max_m
        )
        self.assertEqual(qualifying, [])

    # 7
    def test_7_case_without_a_rider_track_returns_an_empty_summary(self):
        """Case 101 has rider_track null; the summary is empty and nothing raises."""
        gps = artifact_payload(101, "GPS_TRACE")
        self.assertIsNone(gps["rider_track"])

        rider = facts.rider_points(gps)
        self.assertEqual(rider, [])

        trip = artifact_payload(101, "TRIP_RECORD")
        summary = facts.track_summary(rider, trip["pickup"]["lat"], trip["pickup"]["lng"])
        self.assertEqual(summary["fix_count"], 0)
        self.assertIsNone(summary["min_distance_m"])
        self.assertIsNone(summary["max_distance_m"])
        self.assertIsNone(summary["mean_distance_m"])
        self.assertEqual(summary["distinct_speeds_kph"], [])
        self.assertIsNone(summary["first_ts"])
        self.assertIsNone(summary["last_ts"])

    # 8
    def test_8_no_policy_number_appears_as_a_literal(self):
        """facts.py must not carry any of the policy numbers as a numeric literal."""
        source = FACTS_SOURCE.read_text(encoding="utf-8")
        forbidden_text = {"120", "150", "300", "480", "25", "50"}
        forbidden_values = {float(text) for text in forbidden_text}

        literals = [
            token.string
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.NUMBER
        ]
        self.assertTrue(literals, "expected the module to contain some numeric literals")

        by_text = sorted(set(literals) & forbidden_text)
        by_value = sorted(
            {text for text in literals if _as_float(text) in forbidden_values},
            key=_as_float,
        )
        self.assertEqual(by_text, [], "policy numbers used as literals: {0}".format(by_text))
        self.assertEqual(by_value, [], "policy numbers used as literals: {0}".format(by_value))


def _as_float(text: str):
    """The numeric value of a NUMBER token, or None when it is not a plain number."""
    try:
        return float(text)
    except ValueError:
        return None


class AccuracyFilterTests(unittest.TestCase):
    """The accuracy filter decides presence, not absence."""

    @classmethod
    def setUpClass(cls):
        cls.trip = artifact_payload(208, "TRIP_RECORD")
        cls.gps = artifact_payload(208, "GPS_TRACE")
        cls.lat = cls.trip["pickup"]["lat"]
        cls.lng = cls.trip["pickup"]["lng"]
        cls.driver = facts.driver_points(cls.gps)
        fee_schedule = policy_file("no_show.json")["fee_schedule"]
        cls.radius_m = fee_schedule["arrival_radius_m"][cls.trip["pickup_zone_class"]]
        cls.accuracy_max_m = fee_schedule["gps_accuracy_filter_m"]

    def test_in_radius_fixes_rejected_for_accuracy_are_excluded(self):
        """63 fixes are inside the radius; 3 fail the accuracy filter; 60 qualify."""
        distances = facts.distances_to_point(self.driver, self.lat, self.lng)
        inside = [i for i, d in enumerate(distances) if d <= self.radius_m]
        rejected = [i for i in inside if self.driver[i]["accuracy_m"] > self.accuracy_max_m]

        self.assertEqual(len(inside), 63)
        self.assertEqual(len(rejected), 3)

        qualifying = facts.qualifying_fixes(
            self.driver, self.lat, self.lng, self.radius_m, self.accuracy_max_m
        )
        self.assertEqual(len(qualifying), 60)
        for index in rejected:
            self.assertFalse(
                any(fix is self.driver[index] for fix in qualifying),
                "a fix failing the accuracy filter was counted as presence",
            )

    def test_every_qualifying_fix_passes_both_tests(self):
        """Each qualifying fix is inside the radius and within the accuracy filter."""
        qualifying = facts.qualifying_fixes(
            self.driver, self.lat, self.lng, self.radius_m, self.accuracy_max_m
        )
        for fix in qualifying:
            self.assertLessEqual(fix["accuracy_m"], self.accuracy_max_m)
            self.assertLessEqual(
                facts.haversine_m(fix["lat"], fix["lng"], self.lat, self.lng), self.radius_m
            )

    def test_missing_payload_is_tolerated(self):
        """Case 213's GPS payload is null; every entry point returns empty, not an error."""
        payload = artifact_payload(213, "GPS_TRACE")
        self.assertIsNone(payload)

        self.assertEqual(facts.driver_points(payload), [])
        self.assertEqual(facts.rider_points(payload), [])

        summary = facts.track_summary(None, self.lat, self.lng)
        self.assertEqual(summary["fix_count"], 0)
        self.assertEqual(
            facts.longest_qualifying_run(None, self.lat, self.lng, self.radius_m, self.accuracy_max_m),
            {"first_ts": None, "last_ts": None, "fix_count": 0, "duration_sec": 0.0},
        )

    def test_a_single_disqualifying_fix_breaks_the_run(self):
        """Removing one fix from the middle of the run shortens it, it does not merge."""
        run = facts.longest_qualifying_run(
            self.driver, self.lat, self.lng, self.radius_m, self.accuracy_max_m
        )
        self.assertEqual(run["fix_count"], 60)

        qualifying_indexes = [
            i
            for i, fix in enumerate(self.driver)
            if fix["accuracy_m"] <= self.accuracy_max_m
            and facts.haversine_m(fix["lat"], fix["lng"], self.lat, self.lng) <= self.radius_m
        ]
        first = qualifying_indexes[0]
        middle = qualifying_indexes[len(qualifying_indexes) // 2]

        broken = [dict(fix) for fix in self.driver]
        broken[middle] = dict(broken[middle], accuracy_m=self.accuracy_max_m + 1)
        shorter = facts.longest_qualifying_run(
            broken, self.lat, self.lng, self.radius_m, self.accuracy_max_m
        )
        self.assertLess(shorter["fix_count"], run["fix_count"])
        self.assertGreaterEqual(shorter["fix_count"], 1)
        self.assertEqual(shorter["first_ts"], self.driver[first]["ts"])


class DeviationTests(unittest.TestCase):
    """Item 1: POL-RD-01's excess and status, asserted on the real corpus."""

    MEASURED_EXCESS_KM = {
        101: 6.18, 102: 1.39, 103: 2.98, 104: 7.07, 105: 18.16,
        106: 3.58, 107: 3.57, 108: 5.17, 109: 7.36, 110: 2.80,
        111: 5.98, 112: 4.80, 113: 0.78, 114: 5.97, 115: 5.78,
    }

    @classmethod
    def setUpClass(cls):
        with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
        cls.route = [e["case_no"] for e in entries if e["category"] == "ROUTE_DEVIATION"]
        cls.no_show = [e["case_no"] for e in entries if e["category"] == "NO_SHOW_CHARGE"]
        cls.thresholds = brief._deviation_thresholds(policy_file("route_deviation.json"))

    @staticmethod
    def gps_of(case_no):
        return next(
            a for a in brief.build_brief(case_no)["case"]["evidence"]
            if a["evidence_type"] == "GPS_TRACE"
        )

    @classmethod
    def deviation_of(cls, case_no):
        return cls.gps_of(case_no)["payload"]["derived"]["deviation"]

    @classmethod
    def derived_of(cls, case_no):
        """The whole derived block, so an absent deviation block is visible."""
        return cls.gps_of(case_no)["payload"]["derived"]

    def test_1_excess_matches_the_measured_values(self):
        """All 15 route-deviation excesses reproduce the measured figures to two decimals."""
        self.assertEqual(len(self.route), 15)
        for case_no in sorted(self.route):
            deviation = self.deviation_of(case_no)
            self.assertTrue(deviation["available"], "case {0}".format(case_no))
            self.assertEqual(
                round(deviation["excess_km"]["value"], 2),
                Decimal(str(self.MEASURED_EXCESS_KM[case_no])),
                "case {0}".format(case_no),
            )
            self.assertEqual(
                deviation["excess_km"]["evidence_id"], "EV-GPS-{0:05d}".format(case_no)
            )

    def test_2_case_106_is_established_but_not_material_and_case_105_is_material(self):
        """49.72 % sits under the material line; 50.44 % is over it."""
        six = self.deviation_of(106)
        self.assertEqual(round(six["excess_pct"]["value"], 2), Decimal("49.72"))
        self.assertEqual(six["status"]["value"], facts.ESTABLISHED)
        self.assertNotEqual(six["status"]["value"], facts.MATERIAL)

        five = self.deviation_of(105)
        self.assertEqual(round(five["excess_pct"]["value"], 2), Decimal("50.44"))
        self.assertEqual(five["status"]["value"], facts.MATERIAL)

    def test_3_establishment_needs_both_tests(self):
        """102 clears the km line only, 113 the percentage line only; both are no deviation."""
        pct = self.thresholds["threshold_pct"]
        km = self.thresholds["threshold_km"]

        two = self.deviation_of(102)
        self.assertEqual(round(two["excess_pct"]["value"], 2), Decimal("6.81"))
        self.assertGreater(two["excess_km"]["value"], km)
        self.assertLess(two["excess_pct"]["value"], pct)
        self.assertEqual(two["status"]["value"], facts.NO_DEVIATION)

        thirteen = self.deviation_of(113)
        self.assertEqual(round(thirteen["excess_km"]["value"], 2), Decimal("0.78"))
        self.assertLess(thirteen["excess_km"]["value"], km)
        # 113 does not isolate the absolute test: at 4.02 % it fails the
        # percentage test too. 102 is the case that isolates a single failure.
        self.assertLess(thirteen["excess_pct"]["value"], pct)
        self.assertEqual(thirteen["status"]["value"], facts.NO_DEVIATION)

        # One test passing on its own is never enough.
        material_pct = self.thresholds["material_pct"]
        material_km = self.thresholds["material_km"]
        self.assertEqual(
            facts.deviation_status(0.50, 25.0, pct, km, material_pct, material_km),
            facts.NO_DEVIATION,
            "percentage passed but the absolute line failed",
        )
        self.assertEqual(
            facts.deviation_status(1.00, 10.0, pct, km, material_pct, material_km),
            facts.NO_DEVIATION,
            "absolute line passed but the percentage failed",
        )

    def test_7_every_route_brief_has_a_deviation_block_and_no_no_show_brief_does(self):
        """The block is emitted for ROUTE_DEVIATION only."""
        for case_no in self.route:
            self.assertIn("deviation", self.derived_of(case_no), "case {0}".format(case_no))

        for case_no in self.no_show:
            gps = self.gps_of(case_no)
            if not isinstance(gps["payload"], dict):
                # Case 213's GPS artifact is MISSING, so there is no derived
                # block of any kind to inspect.
                self.assertIsNone(gps["payload"])
                continue
            self.assertNotIn(
                "deviation", gps["payload"]["derived"], "case {0}".format(case_no)
            )

    def test_thresholds_come_from_the_loaded_clause(self):
        """The four lines are read from POL-RD-01's own text, not hardcoded."""
        self.assertEqual(
            self.thresholds,
            {"threshold_pct": 20.0, "threshold_km": 0.8, "material_pct": 50.0, "material_km": 8.0},
        )
        self.assertIsNone(brief._deviation_thresholds(policy_file("no_show.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
