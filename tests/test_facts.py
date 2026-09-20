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
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import facts, loader  # noqa: E402

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
