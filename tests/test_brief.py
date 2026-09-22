"""Tests for ``tribunal.brief``.

Every test asserts against the real files under ``data/`` and ``policy/``. Run
from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, facts, loader  # noqa: E402

INDEX_PATH = PROJECT_ROOT / "data" / "index.json"

# Facts that can only be computed once a zone class selects the thresholds.
ZONE_DEPENDENT_KEYS = (
    "thresholds",
    "qualifying_fix_count",
    "longest_qualifying_run",
    "dwell_start_offset_sec",
    "rider_qualifying_fix_count",
)

FORBIDDEN_KEYS = (
    "ground_truth",
    "expected_ruling",
    "expected_amount_sgd",
    "expected_driver_compensation_sgd",
    "expected_referrals",
)


def manifest():
    """The real manifest."""
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def case_numbers():
    return [entry["case_no"] for entry in manifest()]


def gps_artifact(brief_obj):
    """The GPS_TRACE artifact inside a brief."""
    for artifact in brief_obj["case"]["evidence"]:
        if artifact["evidence_type"] == "GPS_TRACE":
            return artifact
    raise AssertionError("brief has no GPS_TRACE artifact")


def derived(brief_obj):
    return gps_artifact(brief_obj)["payload"]["derived"]


def coordinate_arrays(node, path="root", out=None):
    """Every list whose elements are dicts all carrying both ``lat`` and ``lng``."""
    if out is None:
        out = []
    if isinstance(node, dict):
        for key, value in node.items():
            coordinate_arrays(value, "{0}.{1}".format(path, key), out)
    elif isinstance(node, list):
        if node and all(isinstance(e, dict) and "lat" in e and "lng" in e for e in node):
            out.append((path, len(node)))
        for position, value in enumerate(node):
            coordinate_arrays(value, "{0}[{1}]".format(path, position), out)
    return out


def walk_keys(node):
    """Yield every key found anywhere inside nested dicts and lists."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_keys(value)


class RawCoordinateRemovalTests(unittest.TestCase):
    """Requirement 1 and test 1: raw point arrays are gone."""

    def test_1a_no_gps_payload_keeps_a_raw_coordinate_array(self):
        """No brief's GPS payload retains a `points` or `rider_track` array."""
        for case_no in case_numbers():
            b = brief.build_brief(case_no)
            for artifact in b["case"]["evidence"]:
                payload = artifact.get("payload")
                if not isinstance(payload, dict):
                    continue
                if artifact["evidence_type"] == "GPS_TRACE":
                    for field in ("points", "rider_track"):
                        self.assertNotIn(
                            field, payload, "case {0} kept {1}".format(case_no, field)
                        )

    def test_1b_no_coordinate_array_survives_except_the_erp_gantries(self):
        """Structurally: the only coordinate lists left are the small ERP gantry lists."""
        for case_no in case_numbers():
            b = brief.build_brief(case_no)
            for path, size in coordinate_arrays(b):
                self.assertTrue(
                    path.endswith("erp_gantries"),
                    "case {0}: unexpected coordinate array at {1} ({2} points)".format(
                        case_no, path, size
                    ),
                )


class Case208DerivedFactsTests(unittest.TestCase):
    """Test 2: the derived facts are present and each carries its source."""

    @classmethod
    def setUpClass(cls):
        cls.brief = brief.build_brief(208)
        cls.derived = derived(cls.brief)

    def test_2_dwell_duration_is_585_seconds(self):
        run = self.derived["arrival"]["longest_qualifying_run"]
        self.assertEqual(run["duration_sec"]["value"], 585.0)
        self.assertEqual(run["duration_sec"]["evidence_id"], "EV-GPS-00208")
        self.assertEqual(run["fix_count"]["value"], 60)
        self.assertEqual(run["first_ts"]["value"], "2026-07-30T16:02:10+08:00")
        self.assertEqual(run["last_ts"]["value"], "2026-07-30T16:11:55+08:00")

    def test_2_closest_approach_is_28_8_metres(self):
        closest = self.derived["driver_track"]["min_distance_m"]
        self.assertEqual(round(closest["value"], 1), 28.8)
        self.assertEqual(closest["evidence_id"], "EV-GPS-00208")

    def test_2_rider_track_summary_is_141_fixes_633_9_to_646_4(self):
        rider = self.derived["rider_presence"]
        self.assertTrue(rider["available"])
        self.assertEqual(rider["fix_count"]["value"], 141)
        self.assertEqual(rider["fix_count"]["evidence_id"], "EV-GPS-00208")
        self.assertEqual(round(rider["min_distance_m"]["value"], 1), 633.9)
        self.assertEqual(round(rider["max_distance_m"]["value"], 1), 646.4)
        self.assertEqual(rider["min_distance_m"]["evidence_id"], "EV-GPS-00208")
        self.assertEqual(rider["max_distance_m"]["evidence_id"], "EV-GPS-00208")

    def test_2_every_derived_value_carries_a_source(self):
        """No derived value is left without an evidence_id."""
        def check(node, path):
            if isinstance(node, dict):
                if set(node) == {"value", "evidence_id"}:
                    self.assertTrue(node["evidence_id"], "unsourced derived value at " + path)
                    return
                for key, value in node.items():
                    check(value, "{0}.{1}".format(path, key))
            elif isinstance(node, list):
                for position, value in enumerate(node):
                    check(value, "{0}[{1}]".format(path, position))

        for block in ("driver_track", "rider_presence"):
            check(self.derived[block], block)

    def test_2_zone_dependent_thresholds_came_from_the_policy(self):
        thresholds = self.derived["arrival"]["thresholds"]
        for name, entry in thresholds.items():
            self.assertEqual(entry["policy_id"], "POLICY-NO-SHOW", name)
        self.assertEqual(self.derived["arrival"]["pickup_zone_class"]["value"], "LARGE_VENUE")
        self.assertEqual(self.derived["arrival"]["pickup_zone_class"]["evidence_id"], "EV-TRIP-00208")


class CaseSpecificTests(unittest.TestCase):
    """Tests 3 and 4."""

    def test_3_case_104_keeps_both_advisories_and_eight_artifacts(self):
        b = brief.build_brief(104)
        artifacts = b["case"]["evidence"]
        self.assertEqual(len(artifacts), 8)

        advisories = [
            a["evidence_id"] for a in artifacts if a["evidence_type"] == "TRAFFIC_ADVISORY"
        ]
        self.assertEqual(len(advisories), 2)
        self.assertIn("EV-ADVIS-00104-01", advisories)
        self.assertIn("EV-ADVIS-00104-02", advisories)

    def test_4_case_213_missing_artifacts_remain_citable(self):
        b = brief.build_brief(213)
        by_id = {a["evidence_id"]: a for a in b["case"]["evidence"]}

        for evidence_id in ("EV-GPS-00213", "EV-CHAT-00213", "EV-ADVIS-00213-01"):
            self.assertIn(evidence_id, by_id)
            artifact = by_id[evidence_id]
            self.assertIsNone(artifact["payload"])
            self.assertEqual(artifact["admissibility"]["status"], "MISSING")
            self.assertEqual(artifact["admissibility"]["weight_multiplier"], 0.0)


class ZoneUnavailableTests(unittest.TestCase):
    """Test 5: a ROUTE_DEVIATION brief states that the zone class is unavailable."""

    def test_5_route_deviation_briefs_omit_zone_dependent_facts_and_say_so(self):
        route_cases = [e["case_no"] for e in manifest() if e["category"] == "ROUTE_DEVIATION"]
        self.assertEqual(len(route_cases), 15)

        for case_no in route_cases:
            arrival = derived(brief.build_brief(case_no))["arrival"]
            self.assertIs(arrival["available"], False, "case {0}".format(case_no))
            self.assertIsNone(arrival["pickup_zone_class"]["value"])
            self.assertTrue(arrival["pickup_zone_class"]["evidence_id"])

            reason = arrival.get("reason", "")
            self.assertIn("pickup_zone_class", reason)
            self.assertIn("null", reason)

            for key in ZONE_DEPENDENT_KEYS:
                self.assertNotIn(key, arrival, "case {0} leaked {1}".format(case_no, key))

    def test_5_no_show_charge_briefs_do_have_zone_dependent_facts(self):
        no_show_cases = [e["case_no"] for e in manifest() if e["category"] == "NO_SHOW_CHARGE"]
        self.assertEqual(len(no_show_cases), 14)

        checked = 0
        for case_no in no_show_cases:
            artifact = gps_artifact(brief.build_brief(case_no))
            if artifact["payload"] is None:
                # Case 213's GPS artifact is MISSING, so there is nothing to
                # derive; the absence is stated by its admissibility block.
                self.assertEqual(artifact["admissibility"]["status"], "MISSING")
                continue
            arrival = artifact["payload"]["derived"]["arrival"]
            self.assertIs(arrival["available"], True, "case {0}".format(case_no))
            self.assertIn("thresholds", arrival)
            self.assertIsNotNone(arrival["pickup_zone_class"]["value"])
            checked += 1
        self.assertEqual(checked, 13, "expected 13 NO_SHOW_CHARGE cases with a GPS payload")


class BriefInvariantTests(unittest.TestCase):
    """Tests 6, 7 and 8."""

    def test_6_brief_is_byte_identical_across_runs(self):
        for case_no in (208, 104, 213):
            canonical_a, digest_a = brief.brief_digest(brief.build_brief(case_no))
            canonical_b, digest_b = brief.brief_digest(brief.build_brief(case_no))
            self.assertEqual(canonical_a, canonical_b)
            self.assertEqual(digest_a, digest_b)
            self.assertEqual(len(digest_a), 64)

    def test_7_no_brief_contains_a_forbidden_key(self):
        for case_no in case_numbers():
            b = brief.build_brief(case_no)
            present = sorted(set(walk_keys(b)) & set(FORBIDDEN_KEYS))
            self.assertEqual(present, [], "case {0} leaked {1}".format(case_no, present))

    def test_8_build_brief_takes_no_side_or_stance_parameter(self):
        parameters = list(inspect.signature(brief.build_brief).parameters)
        self.assertEqual(parameters, ["case_no", "include_clause_notes"])
        for forbidden in ("side", "stance", "role", "party", "variant"):
            self.assertNotIn(forbidden, parameters)
        self.assertEqual(len(parameters), 2)


class ClauseNotesFlagTests(unittest.TestCase):
    """Requirement 6: the notes flag works and is the only difference."""

    def test_notes_are_carried_when_requested_and_dropped_when_not(self):
        with_notes = brief.build_brief(208, include_clause_notes=True)
        without_notes = brief.build_brief(208, include_clause_notes=False)

        for clause in with_notes["policies"]["category"]["clauses"]:
            self.assertIn("notes", clause)
        for clause in without_notes["policies"]["category"]["clauses"]:
            self.assertNotIn("notes", clause)

        self.assertEqual(with_notes["case"], without_notes["case"])
        self.assertEqual(
            brief.brief_digest(with_notes)[1] == brief.brief_digest(without_notes)[1], False
        )


class TokenMeasurementTests(unittest.TestCase):
    """Test 9: the serialised size, measured against the loader baseline."""

    def test_9_report_token_estimates(self):
        def tokens(text):
            return len(text) / 4.0

        baseline = loader.bundle_digest(loader.build_bundle(208))[0]
        with_notes = brief.brief_digest(brief.build_brief(208, include_clause_notes=True))[0]
        without_notes = brief.brief_digest(brief.build_brief(208, include_clause_notes=False))[0]

        print(
            "\ncase 208 serialised size (chars/4 estimate)\n"
            "  loader.build_bundle baseline : {0:>7} chars  ~{1:>7.0f} tokens\n"
            "  brief, include_clause_notes=T: {2:>7} chars  ~{3:>7.0f} tokens\n"
            "  brief, include_clause_notes=F: {4:>7} chars  ~{5:>7.0f} tokens".format(
                len(baseline), tokens(baseline),
                len(with_notes), tokens(with_notes),
                len(without_notes), tokens(without_notes),
            )
        )

        self.assertLess(len(with_notes), len(baseline))
        self.assertLess(len(without_notes), len(with_notes))


class AccumulatedDwellBriefTests(unittest.TestCase):
    """POL-NS-06(i) reaches the agents: the numbers, and the reason they apply.

    Computing the accumulation without publishing it would leave case 214's
    defect exactly where it was, so these tests read the brief the agents
    actually receive rather than the function that computes it.
    """

    NO_SHOW = "NO_SHOW_CHARGE"

    @classmethod
    def setUpClass(cls):
        cls.no_show = [
            case_no
            for case_no in case_numbers()
            if loader.load_case(case_no)["dispute"]["category"] == cls.NO_SHOW
        ]

    @staticmethod
    def arrival_of(case_no):
        """The arrival block of one case's brief, with the accumulated sub-block."""
        return derived(brief.build_brief(case_no))["arrival"]

    def test_1_case_214_publishes_the_two_holds_and_their_sum(self):
        """The fact the case turns on, and the single hold that is not enough."""
        arrival = self.arrival_of(214)
        block = arrival["accumulated_dwell"]

        self.assertEqual([run["duration_sec"]["value"] for run in block["runs"]], [170.0, 185.0])
        self.assertEqual([run["fix_count"]["value"] for run in block["runs"]], [18, 20])
        self.assertEqual(block["accumulated_sec"]["value"], 355.0)
        self.assertAlmostEqual(block["max_excursion_m"]["value"], 179.0, delta=0.05)

        minimum = block["thresholds"]["minimum_dwell_sec"]["value"]
        self.assertEqual(minimum, 300)
        self.assertEqual(arrival["longest_qualifying_run"]["duration_sec"]["value"], 185.0)
        self.assertLess(
            block["longest_run_sec"]["value"],
            minimum,
            "the longest hold alone must fall short, or the limb decides nothing",
        )
        self.assertGreaterEqual(block["accumulated_sec"]["value"], minimum)

    def test_2_case_214_says_why_summing_is_permitted(self):
        """A judge told 355 without the reason cannot cite the clause."""
        block = self.arrival_of(214)["accumulated_dwell"]

        self.assertIs(block["limb"]["available"], True)
        self.assertEqual(block["limb"]["limb"], "i")
        self.assertEqual(block["limb"]["policy_id"], "POLICY-NO-SHOW")
        self.assertEqual(block["limb"]["clause_id"], "POL-NS-06")

        reason = block["limb"]["reason"]
        self.assertIn("EV-ADVIS-00214-01", reason)
        self.assertIn("KERB_RESTRICTION", reason)

    def test_3_case_211_reports_the_sum_and_refuses_to_use_it(self):
        """The falsifier: two holds that would clear the minimum and may not be added."""
        block = self.arrival_of(211)["accumulated_dwell"]

        self.assertEqual([run["duration_sec"]["value"] for run in block["runs"]], [220.0, 112.0])
        self.assertEqual(block["accumulated_sec"]["value"], 332.0)
        self.assertGreaterEqual(
            block["accumulated_sec"]["value"],
            block["thresholds"]["minimum_dwell_sec"]["value"],
        )

        self.assertIs(block["limb"]["available"], False)
        conditions = [entry["condition"] for entry in block["limb"]["unavailable"]]
        self.assertIn(facts.ADVISORY_MISSING, conditions)

        text = " ".join(entry["reason"] for entry in block["limb"]["unavailable"])
        self.assertIn("EV-ADVIS-00211-01", text, "the reason must name the missing advisory")
        self.assertIn("MISSING", text)

    def test_4_case_211_reports_the_hole_between_the_holds(self):
        """The trace's own gap, and the excursion it makes unmeasurable."""
        block = self.arrival_of(211)["accumulated_dwell"]

        self.assertEqual(len(block["excursions"]), 1)
        excursion = block["excursions"][0]
        self.assertIs(excursion["gap_in_interval"]["value"], True)
        self.assertIsNone(excursion["max_distance_m"]["value"])
        self.assertIsNone(block["max_excursion_m"]["value"])

        conditions = [entry["condition"] for entry in block["limb"]["unavailable"]]
        self.assertIn(facts.EXCURSION_UNMEASURABLE, conditions)

    def test_5_every_derived_value_carries_the_evidence_id_it_came_from(self):
        """Each value in the block is tagged, exactly as the facts around it are."""
        block = self.arrival_of(214)["accumulated_dwell"]
        untagged = []

        def check(node, path):
            if isinstance(node, dict):
                if "value" in node:
                    if "evidence_id" not in node:
                        untagged.append(path)
                    return
                for key, value in node.items():
                    check(value, "{0}.{1}".format(path, key))
            elif isinstance(node, list):
                for position, value in enumerate(node):
                    check(value, "{0}[{1}]".format(path, position))

        for name in (
            "accumulated_sec",
            "longest_run_sec",
            "run_count",
            "shortfall_sec",
            "max_excursion_m",
            "runs",
            "excursions",
        ):
            check(block[name], name)

        self.assertEqual(untagged, [], "values without a source: {0}".format(untagged))

    def test_6_every_threshold_carries_the_clause_it_came_from(self):
        """The leash and the types are attributed to POL-NS-06, the motion line to POL-NS-05."""
        block = self.arrival_of(214)["accumulated_dwell"]
        thresholds = block["thresholds"]

        self.assertEqual(thresholds["leash_m"]["clause_id"], "POL-NS-06")
        self.assertEqual(thresholds["admissible_advisory_types"]["clause_id"], "POL-NS-06")
        self.assertEqual(thresholds["motion_speed_kph"]["clause_id"], "POL-NS-05")
        self.assertEqual(thresholds["minimum_dwell_sec"]["zone_class"], "LARGE_VENUE")

        for name, entry in thresholds.items():
            self.assertIn("value", entry, name)
            self.assertIn("policy_id", entry, name)
            self.assertTrue(
                "clause_id" in entry or "zone_class" in entry,
                "{0} does not say where its number came from".format(name),
            )

    def test_7_the_block_is_emitted_for_no_show_cases_only(self):
        """A ROUTE_DEVIATION case has no POL-NS-06 clause, so it has no such block."""
        for case_no in case_numbers():
            b = brief.build_brief(case_no)
            category = b["case"]["dispute"]["category"]
            gps = gps_artifact(b)

            if not isinstance(gps["payload"], dict):
                # Case 213's GPS artifact is MISSING; there is no derived block.
                self.assertIsNone(gps["payload"])
                continue

            arrival = derived(b)["arrival"]
            if category == self.NO_SHOW:
                self.assertIs(arrival.get("available"), True, "case {0}".format(case_no))
                self.assertIn("accumulated_dwell", arrival, "case {0}".format(case_no))
            else:
                self.assertNotIn("accumulated_dwell", arrival, "case {0}".format(case_no))

    def test_8_only_case_214_offers_the_limb(self):
        """The corpus's one clean test of POL-NS-06(i), read from the brief."""
        offered = [
            case_no
            for case_no in self.no_show
            if isinstance(gps_artifact(brief.build_brief(case_no))["payload"], dict)
            and self.arrival_of(case_no)["accumulated_dwell"]["limb"]["available"]
        ]
        self.assertEqual(offered, [214])


if __name__ == "__main__":
    unittest.main(verbosity=2)
