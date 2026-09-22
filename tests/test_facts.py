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
        # The arrival radii, the dwell minimums, the accuracy filter and the
        # leash come from the policy; 15 is POL-NS-05's line between holding
        # position and being in motion, which POL-NS-06(i) borrows.
        forbidden_text = {"120", "150", "300", "480", "25", "50", "15"}
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
        """102 fails the percentage line only; 113 fails both. Either way, no deviation."""
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


class AccumulatedDwellTests(unittest.TestCase):
    """POL-NS-06(i): the separate holds, and whether they may be summed.

    Case 214 is the corpus's one clean test of the limb. The parties agree on
    the facts and disagree only on what they mean, so the case turns on whether
    170 and 185 may be added. Without the limb the driver's longest continuous
    hold is 185 seconds against a 300 second minimum and POL-NS-06 refunds as
    strict liability; with it the sum is 355 and there is no shortfall.

    Case 211 is the falsifier. It has two observed holds of 220 and 112 seconds
    that would sum to 332, and they may not be summed: the intervals are
    separated by a 168 second hole and EV-ADVIS-00211-01 is MISSING. A function
    that always sums passes case 214 and fails this one.
    """

    INDEX_PATH = PROJECT_ROOT / "data" / "index.json"
    ADVISORY = "TRAFFIC_ADVISORY"

    @classmethod
    def setUpClass(cls):
        cls.fee_schedule = policy_file("no_show.json")["fee_schedule"]
        # The three prose-only thresholds are read from the loaded clause text
        # by the brief, which is the only place that knows how to find them.
        cls.thresholds = brief._no_show_thresholds(policy_file("no_show.json"))

        with cls.INDEX_PATH.open("r", encoding="utf-8") as handle:
            case_numbers = [entry["case_no"] for entry in json.load(handle)]
        cls.no_show = [
            case_no
            for case_no in case_numbers
            if loader.load_case(case_no)["dispute"]["category"] == "NO_SHOW_CHARGE"
        ]

    @classmethod
    def inputs(cls, case_no):
        """The real trip record, GPS payload and advisory artifacts of one case."""
        case = loader.load_case(case_no)
        trip = gps = None
        advisories = []
        for artifact in case["evidence"]:
            if artifact["evidence_type"] == "TRIP_RECORD":
                trip = artifact["payload"]
            elif artifact["evidence_type"] == "GPS_TRACE":
                gps = artifact["payload"]
            elif artifact["evidence_type"] == cls.ADVISORY:
                advisories.append({
                    "evidence_id": artifact["evidence_id"],
                    "payload": artifact.get("payload"),
                })
        return trip, gps, advisories

    @classmethod
    def accumulate(cls, case_no, **overrides):
        """``accumulated_dwell`` on a real case, with the policy's own thresholds."""
        trip, gps, advisories = cls.inputs(case_no)
        zone = trip["pickup_zone_class"]
        arguments = {
            "points": facts.driver_points(gps),
            "lat": trip["pickup"]["lat"],
            "lng": trip["pickup"]["lng"],
            "radius_m": cls.fee_schedule["arrival_radius_m"][zone],
            "accuracy_max_m": cls.fee_schedule["gps_accuracy_filter_m"],
            "motion_speed_kph": cls.thresholds["motion_speed_kph"],
            "leash_m": cls.thresholds["leash_m"],
            "admissible_types": cls.thresholds["admissible_types"],
            "advisories": advisories,
            "gaps": gps.get("gaps"),
        }
        arguments.update(overrides)
        return facts.accumulated_dwell(**arguments), zone

    @classmethod
    def geometry(cls, case_no):
        """The real driver fixes and the zone's two radii, for the synthetic tests."""
        trip, gps, _ = cls.inputs(case_no)
        zone = trip["pickup_zone_class"]
        return (
            facts.driver_points(gps),
            trip["pickup"]["lat"],
            trip["pickup"]["lng"],
            cls.fee_schedule["arrival_radius_m"][zone],
            cls.fee_schedule["gps_accuracy_filter_m"],
        )

    def test_1_case_214_has_two_holds_of_170_and_185_seconds(self):
        """Both hold lengths are asserted, not only their sum."""
        result, zone = self.accumulate(214)

        self.assertEqual(zone, "LARGE_VENUE")
        self.assertEqual(result["run_count"], 2)
        self.assertEqual(
            [(run["first_ts"], run["last_ts"]) for run in result["runs"]],
            [
                ("2026-08-07T18:44:45+08:00", "2026-08-07T18:47:35+08:00"),
                ("2026-08-07T18:49:35+08:00", "2026-08-07T18:52:40+08:00"),
            ],
        )
        # A sum can be right while both parts are wrong.
        self.assertEqual([run["duration_sec"] for run in result["runs"]], [170.0, 185.0])
        self.assertEqual([run["fix_count"] for run in result["runs"]], [18, 20])

    def test_2_case_214_accumulates_to_355_against_a_300_second_minimum(self):
        """The deciding number is the sum, and the longest hold alone is short."""
        result, zone = self.accumulate(214)
        minimum = self.fee_schedule["minimum_dwell_sec"][zone]

        self.assertEqual(minimum, 300)
        self.assertEqual(result["accumulated_sec"], 355.0)
        self.assertGreaterEqual(result["accumulated_sec"], minimum)

        self.assertEqual(result["longest_run_sec"], 185.0)
        self.assertLess(
            result["longest_run_sec"],
            minimum,
            "the longest hold alone must fall short, or the limb decides nothing",
        )

    def test_3_case_214_excursion_is_179_metres_and_inside_the_leash(self):
        """The driver's furthest point between the holds, against the leash."""
        result, _ = self.accumulate(214)

        self.assertTrue(result["excursions_measurable"])
        self.assertEqual(len(result["excursions"]), 1)

        excursion = result["excursions"][0]
        self.assertEqual(excursion["from_ts"], "2026-08-07T18:47:35+08:00")
        self.assertEqual(excursion["to_ts"], "2026-08-07T18:49:35+08:00")
        self.assertFalse(excursion["gap_in_interval"])

        self.assertAlmostEqual(result["max_excursion_m"], 179.0, delta=0.05)
        self.assertLess(result["max_excursion_m"], self.thresholds["leash_m"])

    def test_4_case_214_limb_i_is_available_on_the_real_advisory(self):
        """Every condition of the limb is met, and the artifact that meets it is named."""
        result, _ = self.accumulate(214)

        self.assertTrue(result["available"], result["unavailable_reasons"])
        self.assertEqual(result["unavailable_reasons"], [])

        self.assertEqual(len(result["advisory_candidates"]), 1)
        candidate = result["advisory_candidates"][0]
        self.assertEqual(candidate["evidence_id"], "EV-ADVIS-00214-01")
        self.assertEqual(candidate["type"], "KERB_RESTRICTION")
        self.assertEqual(candidate["failed_conditions"], [])

    def test_5_case_214_advisory_covers_the_route_and_the_window(self):
        """The advisory conditions are met by the artifact, not by the code."""
        _, _, advisories = self.inputs(214)

        self.assertEqual(len(advisories), 1)
        payload = advisories[0]["payload"]
        self.assertIs(payload["intersects_route"], True)
        self.assertIs(payload["overlaps_trip_window"], True)
        self.assertGreater(payload["overlap_minutes"], 0)
        self.assertIn(payload["type"], self.thresholds["admissible_types"])

    def test_6_case_214_first_hold_ends_where_the_driver_moves_off(self):
        """The 18:47:35 boundary is a speed boundary, and the trace says so.

        The next fix, at 18:47:45, is 53.6 m from the pin at 22.7 m accuracy:
        it passes the radius test and the accuracy filter both. It is excluded
        because the driver is reported at 42.6 km/h. Without that exclusion the
        first hold would run to 18:47:45 and be 180 seconds.
        """
        driver, lat, lng, radius, accuracy = self.geometry(214)
        motion = self.thresholds["motion_speed_kph"]

        moving = next(fix for fix in driver if fix["ts"] == "2026-08-07T18:47:45+08:00")
        self.assertTrue(
            facts._is_qualifying(moving, lat, lng, radius, accuracy),
            "the fix must pass the radius and accuracy tests, or it pins nothing",
        )
        self.assertGreaterEqual(moving["speed_kph"], motion)
        self.assertFalse(facts._is_holding(moving, lat, lng, radius, accuracy, motion))

    def test_7_case_214_lone_stationary_fix_is_not_an_interval(self):
        """One fix at 18:44:05 is inside the radius and stationary, and is not a hold."""
        driver, lat, lng, radius, accuracy = self.geometry(214)
        motion = self.thresholds["motion_speed_kph"]

        lone = next(fix for fix in driver if fix["ts"] == "2026-08-07T18:44:05+08:00")
        self.assertTrue(facts._is_holding(lone, lat, lng, radius, accuracy, motion))

        result, _ = self.accumulate(214)
        self.assertEqual(result["run_count"], 2)
        self.assertNotIn(
            lone["ts"],
            [run["first_ts"] for run in result["runs"]],
            "a one-fix hold was reported as an interval",
        )
        self.assertEqual(facts.MIN_RUN_FIXES, 2)

    def test_8_case_211_holds_are_220_and_112_seconds(self):
        """Two observed holds, split by the trace's own recorded gap."""
        result, zone = self.accumulate(211)

        self.assertEqual(zone, "STANDARD")
        self.assertEqual(result["run_count"], 2)
        self.assertEqual([run["duration_sec"] for run in result["runs"]], [220.0, 112.0])
        self.assertEqual([run["fix_count"] for run in result["runs"]], [23, 12])
        self.assertEqual(result["accumulated_sec"], 332.0)
        self.assertGreaterEqual(
            result["accumulated_sec"], self.fee_schedule["minimum_dwell_sec"][zone]
        )

    def test_9_case_211_limb_i_is_not_available(self):
        """The sum is refused, and the advisory that is missing is the real one."""
        result, _ = self.accumulate(211)

        self.assertFalse(result["available"])
        self.assertIn(facts.ADVISORY_MISSING, result["unavailable_reasons"])
        self.assertEqual(result["advisory_candidates"], [])

        _, _, advisories = self.inputs(211)
        self.assertEqual(
            [advisory["evidence_id"] for advisory in advisories], ["EV-ADVIS-00211-01"]
        )
        self.assertIsNone(advisories[0]["payload"])

    def test_10_case_211_is_split_by_the_hole_and_not_by_the_radius(self):
        """Remove the recorded gap and the same trace becomes one 500 second hold."""
        driver, lat, lng, radius, accuracy = self.geometry(211)
        _, gps, advisories = self.inputs(211)

        self.assertEqual(len(gps["gaps"]), 1)
        before = next(fix for fix in driver if fix["ts"] == "2026-08-06T12:33:40+08:00")
        resume = next(fix for fix in driver if fix["ts"] == "2026-08-06T12:36:28+08:00")
        self.assertTrue(facts._is_qualifying(before, lat, lng, radius, accuracy))
        self.assertTrue(
            facts._is_qualifying(resume, lat, lng, radius, accuracy),
            "the fix that resumes must be in radius, or the split is a radius fact",
        )

        unsplit, _ = self.accumulate(211, gaps=[])
        self.assertEqual(unsplit["run_count"], 1)
        self.assertEqual(unsplit["accumulated_sec"], 500.0)
        # With the hole gone, the advisory is the only condition still refusing
        # the sum, and there is now no second interval for it to permit either.
        self.assertEqual(
            unsplit["unavailable_reasons"], [facts.NO_SECOND_INTERVAL, facts.ADVISORY_MISSING]
        )

    def test_11_the_leash_bites(self):
        """Pushing the excursion beyond the leash withdraws the limb."""
        driver, lat, lng, radius, accuracy = self.geometry(214)
        _, gps, advisories = self.inputs(214)
        leash = self.thresholds["leash_m"]

        # Move every fix between the two holds beyond the leash, keeping each
        # timestamp so the holds themselves are unchanged. The loader parses
        # JSON decimals as Decimal, so the offset is a Decimal too.
        moved = 0
        for index, fix in enumerate(driver):
            if "2026-08-07T18:47:45+08:00" <= fix["ts"] <= "2026-08-07T18:49:25+08:00":
                driver[index] = dict(fix, lat=lat + Decimal("0.01"))
                moved += 1
        self.assertGreater(moved, 0)

        result = facts.accumulated_dwell(
            driver,
            lat,
            lng,
            radius,
            accuracy,
            self.thresholds["motion_speed_kph"],
            leash,
            self.thresholds["admissible_types"],
            advisories=advisories,
            gaps=gps.get("gaps"),
        )

        self.assertFalse(result["available"])
        self.assertIn(facts.EXCURSION_BEYOND_LEASH, result["unavailable_reasons"])
        self.assertGreater(result["max_excursion_m"], leash)
        # The holds are untouched, so the sum is unchanged.
        self.assertEqual(result["accumulated_sec"], 355.0)

    def test_12_each_advisory_condition_is_checked_independently(self):
        """Break exactly one condition at a time and that one is reported."""
        _, _, advisories = self.inputs(214)
        evidence_id = advisories[0]["evidence_id"]

        broken = (
            (facts.ADVISORY_TYPE_NOT_ADMISSIBLE, {"type": "ROAD_WORKS"}),
            (facts.ADVISORY_ROUTE_NOT_COVERED, {"intersects_route": False}),
            (facts.ADVISORY_WINDOW_NOT_COVERED, {"overlaps_trip_window": False}),
        )
        for condition, change in broken:
            with self.subTest(condition=condition):
                payload = dict(advisories[0]["payload"])
                payload.update(change)
                result, _ = self.accumulate(
                    214, advisories=[{"evidence_id": evidence_id, "payload": payload}]
                )
                self.assertFalse(result["available"])
                self.assertEqual(result["unavailable_reasons"], [condition])

        with self.subTest(condition=facts.ADVISORY_MISSING):
            result, _ = self.accumulate(
                214, advisories=[{"evidence_id": evidence_id, "payload": None}]
            )
            self.assertFalse(result["available"])
            self.assertEqual(result["unavailable_reasons"], [facts.ADVISORY_MISSING])

    def test_13_one_hold_is_reported_as_the_accumulation(self):
        """With nothing to add, the accumulation is the one hold and never absent."""
        result, zone = self.accumulate(202)

        self.assertEqual(result["run_count"], 1)
        self.assertEqual(result["accumulated_sec"], result["longest_run_sec"])
        self.assertEqual(
            result["unavailable_reasons"], [facts.NO_SECOND_INTERVAL, facts.ADVISORY_MISSING]
        )

        driver, lat, lng, radius, accuracy = self.geometry(202)
        longest = facts.longest_qualifying_run(driver, lat, lng, radius, accuracy)
        self.assertEqual(result["accumulated_sec"], longest["duration_sec"])
        self.assertEqual(
            self.fee_schedule["arrival_radius_m"][zone], 150, "202 is an AIRPORT pickup"
        )

    def test_14_every_case_computes_and_only_case_214_offers_the_limb(self):
        """The fact is computable for every case, and the limb is available once."""
        offered = []

        for case_no in self.no_show:
            trip, gps, _ = self.inputs(case_no)
            if not isinstance(gps, dict):
                # Case 213's GPS artifact is MISSING; there is nothing to compute.
                self.assertIsNone(gps)
                continue

            result, _ = self.accumulate(case_no)

            if result["run_count"] <= 1:
                self.assertEqual(
                    result["accumulated_sec"],
                    result["longest_run_sec"],
                    "case {0} has one hold and the accumulation is not it".format(case_no),
                )

            if not gps.get("gaps") and result["run_count"] <= 1:
                driver, lat, lng, radius, accuracy = self.geometry(case_no)
                longest = facts.longest_qualifying_run(driver, lat, lng, radius, accuracy)
                self.assertEqual(
                    result["accumulated_sec"],
                    longest["duration_sec"],
                    "case {0} has no gap and one hold, so the two facts must agree".format(case_no),
                )

            if result["available"]:
                offered.append(case_no)

        self.assertEqual(offered, [214])

    def test_15_the_leash_and_the_types_come_from_the_loaded_clause(self):
        """Read out of POL-NS-06's and POL-NS-05's own text, and absent elsewhere."""
        self.assertEqual(self.thresholds["leash_m"], 300.0)
        self.assertEqual(self.thresholds["motion_speed_kph"], 15.0)
        self.assertEqual(
            self.thresholds["admissible_types"],
            ["KERB_RESTRICTION", "ENFORCEMENT", "CLOSURE", "ACCIDENT"],
        )
        self.assertIsNone(brief._no_show_thresholds(policy_file("route_deviation.json")))

    def test_16_the_extractor_raises_rather_than_defaulting(self):
        """A clause that does not state the lines is an error, not a fallback."""
        policy = policy_file("no_show.json")
        damaged = (
            (brief.POL_NS_06, "more than 300 m from the pin", "from the pin"),
            (brief.POL_NS_06, "traffic_advisory.type of", "traffic_advisory.type"),
            (brief.POL_NS_05, "15 km/h or above", "that speed"),
        )

        for clause_id, removed, replacement in damaged:
            with self.subTest(clause=clause_id, removed=removed):
                clauses = []
                for clause in policy["clauses"]:
                    clause = dict(clause)
                    if clause["id"] == clause_id:
                        self.assertIn(removed, clause["rule"])
                        clause["rule"] = clause["rule"].replace(removed, replacement)
                    clauses.append(clause)
                with self.assertRaises(loader.LoaderError):
                    brief._no_show_thresholds({"clauses": clauses})

    def test_17_the_admissible_types_are_not_retyped_into_the_brief(self):
        """The four type values belong to the clause, not to brief.py."""
        source = (PROJECT_ROOT / "tribunal" / "brief.py").read_text(encoding="utf-8")
        for value in self.thresholds["admissible_types"]:
            self.assertNotIn(value, source, "{0} is hard-coded in brief.py".format(value))


if __name__ == "__main__":
    unittest.main(verbosity=2)
