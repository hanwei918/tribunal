"""Tests for ``tribunal.brief``.

Every test asserts against the real files under ``data/`` and ``policy/``. Run
from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, facts, loader, money, pipeline, prepass  # noqa: E402

INDEX_PATH = PROJECT_ROOT / "data" / "index.json"

# The two development sets' case directories, for the version-3 readings below.
DEV_V2_DIR = loader.EXTERNAL_DIR / "dev-v2"


def dev_v2_case(case_no):
    """One case of the revised ``dev-v2`` development set."""
    return loader.load_external_set_case(DEV_V2_DIR, case_no)


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

        # Limb (i) is available here, so the sum is the lawful basis and the
        # shortfall is measured against it.
        self.assertEqual(block["shortfall_sec"]["value"], -55.0)
        self.assertEqual(block["shortfall_basis"]["value"], brief.BASIS_ACCUMULATED)

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

        # The refused sum stays visible, and the shortfall is not measured off it.
        minimum = block["thresholds"]["minimum_dwell_sec"]["value"]
        self.assertEqual(block["longest_run_sec"]["value"], 220.0)
        self.assertEqual(block["shortfall_sec"]["value"], 80.0)
        self.assertEqual(block["shortfall_basis"]["value"], brief.BASIS_LONGEST_RUN)
        self.assertNotEqual(
            block["shortfall_sec"]["value"],
            minimum - block["accumulated_sec"]["value"],
            "the shortfall was measured off the sum limb (i) refuses",
        )

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
            "shortfall_basis",
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

    def test_9_the_shortfall_is_measured_on_the_basis_the_limb_permits(self):
        """The invariant whose absence let a negative shortfall sit on a refused sum.

        Where limb (i) is available the intervals may be summed and the shortfall
        is measured against the sum; where it is not, the operative dwell is the
        longest continuous run and the shortfall is measured against that. Both
        dwell figures stay in the block either way, so a refused sum remains
        visible to argue about.
        """
        checked = 0

        for case_no in case_numbers():
            b = brief.build_brief(case_no)
            gps = gps_artifact(b)
            if not isinstance(gps["payload"], dict):
                # Case 213's GPS artifact is MISSING, so it has no derived block.
                self.assertIsNone(gps["payload"])
                continue

            arrival = derived(b)["arrival"]
            if brief.ACCUMULATED_DWELL_KEY not in arrival:
                # A ROUTE_DEVIATION case has no POL-NS-06 clause and no such block.
                continue

            block = arrival[brief.ACCUMULATED_DWELL_KEY]
            minimum = block["thresholds"]["minimum_dwell_sec"]["value"]
            available = block["limb"]["available"]

            expected = brief.BASIS_ACCUMULATED if available else brief.BASIS_LONGEST_RUN
            self.assertEqual(
                block["shortfall_basis"]["value"],
                expected,
                "case {0}: limb available={1}".format(case_no, available),
            )

            source = block["accumulated_sec" if available else "longest_run_sec"]["value"]
            self.assertEqual(
                block["shortfall_sec"]["value"],
                minimum - source,
                "case {0}: the shortfall is not measured off the basis it names".format(case_no),
            )
            checked += 1

        self.assertEqual(checked, 13, "every NO_SHOW case but 213 carries the block")


def money_artifact(brief_obj):
    """The FARE_BREAKDOWN artifact, which carries the money block."""
    for artifact in brief_obj["case"]["evidence"]:
        if artifact["evidence_type"] == "FARE_BREAKDOWN":
            return artifact
    raise AssertionError("brief has no FARE_BREAKDOWN artifact")


def money_block(brief_obj):
    """The money block the brief publishes, attached to the fare breakdown."""
    return money_artifact(brief_obj)["payload"]["derived"][brief.MONEY_KEY]


def walk_nodes(node):
    """Yield every node found anywhere inside nested dicts and lists."""
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk_nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_nodes(value)


def figure(block, *path):
    """One money figure's value, by its path inside the block."""
    node = block
    for key in path:
        node = node[key]
    return node["value"]


class MoneyBlockTests(unittest.TestCase):
    """The policy's arithmetic, computed by code and published in the brief.

    The first principle is that money comes from a calculator. These tests hold
    the brief to it: the figures are published, each carries the artifact and
    the policy it came from, the payable figures are decimal strings with two
    places, the figures agree with ``tribunal.money`` recomputed here, and the
    two figures the policy states only in prose are read from the clause text
    rather than typed into the code.
    """

    NO_SHOW = "NO_SHOW_CHARGE"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"

    # The figures a ruling states in currency form: a charge, a payable, a fee
    # or a compensation. The intermediate fare arithmetic is not one of these,
    # because POL-RD-02 says intermediate values are not rounded.
    CURRENCY = re.compile(r"^-?\d+\.\d{2}$")

    def test_every_case_publishes_a_money_block(self):
        for case_no in case_numbers():
            b = brief.build_brief(case_no)
            block = money_block(b)
            self.assertIs(block["available"], True, "case {0}".format(case_no))
            self.assertEqual(
                block["policy_id"],
                b["policies"]["category"]["policy_id"],
                "case {0}".format(case_no),
            )

    def test_every_figure_carries_its_evidence_and_its_policy(self):
        """A figure with no source is a figure an advocate cannot cite."""
        checked = 0
        for case_no in case_numbers():
            for node in walk_nodes(money_block(brief.build_brief(case_no))):
                if not (isinstance(node, dict) and "value" in node):
                    continue
                self.assertIn("evidence_id", node, "case {0}".format(case_no))
                self.assertIn("policy_id", node, "case {0}".format(case_no))
                checked += 1
        self.assertGreater(checked, 0)

    def test_the_recomputed_fare_is_the_calculator_s_total(self):
        """The brief's figure is what ``money`` computes from the brief's own figures."""
        checked = 0
        for case_no in case_numbers():
            block = money_block(brief.build_brief(case_no))
            if "recomputed_fare" not in block:
                continue
            recomputed = money.recompute_metered_fare(
                base_fare=figure(block, "constants", "base_fare"),
                per_km=figure(block, "constants", "per_km"),
                per_min=figure(block, "constants", "per_min"),
                optimal_distance_km=figure(block, "optimal_distance_km"),
                optimal_duration_min=figure(block, "optimal_duration_min"),
                surge_multiplier=figure(block, "surge_multiplier"),
                platform_fee=figure(block, "constants", "platform_fee"),
                optimal_route_erp=figure(block, "erp_lines", "on_optimal_route_total"),
                fixed_surcharges=figure(block, "components", "fixed_surcharges"),
                waiting_time_fee=figure(block, "components", "waiting_time_fee"),
                promo_discount=figure(block, "components", "promo_discount"),
            )
            self.assertEqual(
                recomputed, figure(block, "recomputed_fare"), "case {0}".format(case_no)
            )
            checked += 1
        self.assertGreater(checked, 0)

    def test_the_refund_figures_are_the_calculator_s(self):
        for case_no in case_numbers():
            block = money_block(brief.build_brief(case_no))
            if "refund" not in block:
                continue
            working = money.refund_working(
                figure(block, "charged_total"),
                figure(block, "recomputed_fare"),
                figure(block, "constants", "de_minimis_refund"),
            )
            refund = block["refund"]
            self.assertEqual(
                refund["refund_before_rounding"]["value"],
                working["refund_before_rounding"],
                "case {0}".format(case_no),
            )
            self.assertEqual(
                refund["below_de_minimis"]["value"],
                working["below_de_minimis"],
                "case {0}".format(case_no),
            )
            self.assertEqual(
                refund["payable"]["value"],
                money.payable_string(working["payable"]),
                "case {0}".format(case_no),
            )
            self.assertEqual(
                refund["full_refund"]["value"],
                money.payable_string(working["full_refund"]),
                "case {0}".format(case_no),
            )

    def test_each_erp_line_carries_the_trace_s_own_proximity_figures(self):
        """A line's amount and the geometry that decides its match sit together.

        POL-RD-09(4) matches a gantry to the trace by distance, so the amount a
        line was charged at is not enough to decide it: a reader needs how close
        the trace came. The money block carries that beside the amount, read out
        of the trace's own published record rather than recomputed, and this
        holds every figure equal to the trace's for the same line so the two
        cannot drift apart. The trace's artifact stays the figure's source; the
        policy is added because every figure in this block carries one.
        """
        checked = 0
        for case_no in case_numbers():
            b = brief.build_brief(case_no)
            block = money_block(b)
            lines = (block.get("erp_lines") or {}).get("lines") or []
            if not lines:
                continue

            payload = gps_artifact(b)["payload"]
            published = (
                derived(b).get(brief.ERP_GANTRY_PROXIMITY_KEY)
                if isinstance(payload, dict)
                else None
            )
            for index, line in enumerate(lines):
                proximity = line["trace_proximity"]
                if published is None:
                    self.assertIsNone(
                        proximity,
                        "case {0}: the trace published no proximity".format(case_no),
                    )
                    continue

                record = published["lines"][index]
                self.assertEqual(
                    line["gantry_name"],
                    record["gantry_name"],
                    "case {0}: line {1} is not the trace's line".format(case_no, index),
                )
                self.assertIs(
                    proximity["available"],
                    record["available"],
                    "case {0}: line {1} disagrees about availability".format(case_no, index),
                )
                if not record["available"]:
                    self.assertEqual(proximity["reason"], record["reason"])
                    continue

                nearest = record["nearest_fix"]
                self.assertEqual(
                    {
                        "index": proximity["nearest_fix"]["index"]["value"],
                        "ts": proximity["nearest_fix"]["ts"]["value"],
                        "distance_m": proximity["nearest_fix"]["distance_m"]["value"],
                        "gap_brackets_closest_approach": proximity[
                            "gap_brackets_closest_approach"
                        ]["value"],
                        "across_gap_distance_m": proximity["across_gap_distance_m"]["value"],
                    },
                    {
                        "index": nearest["index"]["value"],
                        "ts": nearest["ts"]["value"],
                        "distance_m": nearest["distance_m"]["value"],
                        "gap_brackets_closest_approach": record[
                            "gap_brackets_closest_approach"
                        ]["value"],
                        "across_gap_distance_m": record["across_gap_distance_m"]["value"],
                    },
                    "case {0}: line {1} is not the trace's geometry".format(case_no, index),
                )
                self.assertEqual(
                    proximity["nearest_fix"]["distance_m"]["evidence_id"],
                    nearest["distance_m"]["evidence_id"],
                    "case {0}: line {1} lost the trace as its source".format(case_no, index),
                )
                self.assertEqual(
                    proximity["nearest_fix"]["distance_m"]["policy_id"],
                    block["policy_id"],
                    "case {0}: line {1} is not tagged with its policy".format(case_no, index),
                )
                checked += 1

        self.assertEqual(
            8, checked, "the corpus carries eight ERP lines across four cases"
        )

    def test_payable_figures_are_decimal_strings_with_two_places(self):
        checked = 0
        for case_no in case_numbers():
            block = money_block(brief.build_brief(case_no))
            paths = [("charged_total",)] if "charged_total" in block else []
            if "refund" in block:
                paths += [("refund", "payable"), ("refund", "full_refund")]
            for position in range(len(block.get("closure") or [])):
                paths += [
                    ("closure", position, "refund", "payable"),
                    ("closure", position, "refund", "full_refund"),
                ]
            for key in ("quoted_fare", "charged_over_quote", "schedule_fee", "fee_charged",
                        "difference", "driver_compensation", "goodwill"):
                if key in block:
                    paths.append((key,))
            for path in paths:
                value = figure(block, *path)
                self.assertIsInstance(value, str, "case {0}: {1}".format(case_no, path))
                self.assertRegex(value, self.CURRENCY, "case {0}: {1}".format(case_no, path))
                checked += 1
        self.assertGreater(checked, 0)

    def test_case_104_caps_the_excess_at_the_clause_s_cap(self):
        """POL-RD-03: min(7.07 measured, 1.30 x (30.10 - 27.10) + 1.00) = 4.90."""
        block = money_block(brief.build_brief(104))
        closure = block["closure"][0]
        self.assertEqual(figure(closure, "measured_excess_km"), Decimal("7.07"))
        self.assertEqual(figure(closure, "cap_km"), Decimal("4.9"))
        self.assertEqual(figure(closure, "justified_excess_km"), Decimal("4.9"))
        self.assertEqual(figure(closure, "adjusted_optimal_distance_km"), Decimal("32.00"))
        self.assertEqual(figure(closure, "adjusted_optimal_duration_min"), Decimal("40.1"))
        self.assertEqual(figure(closure, "refund", "payable"), "3.60")

    def test_case_9113_caps_the_excess_and_adjusts_the_route(self):
        """POL-RD-03: min(8.00 measured, 1.30 x (12.00 - 10.00) + 1.00) = 3.60."""
        case = loader.load_external_set_case(
            PROJECT_ROOT / "data" / "external" / "codex", 9113
        )
        block = money_block(brief.build_brief_for_case(case))
        closure = block["closure"][0]
        self.assertEqual(figure(closure, "cap_km"), Decimal("3.6"))
        self.assertEqual(figure(closure, "justified_excess_km"), Decimal("3.6"))
        self.assertEqual(figure(closure, "adjusted_optimal_distance_km"), Decimal("13.60"))
        self.assertEqual(figure(closure, "adjusted_optimal_duration_min"), Decimal("27.2"))
        self.assertEqual(figure(closure, "refund", "payable"), "8.05")

    def test_an_upfront_quote_is_compared_with_the_charge_and_no_refund_is_computed(self):
        """POL-RD-11: the quote against the charge, and no distance refund at all."""
        block = money_block(brief.build_brief(115))
        self.assertEqual(block["fare_model"]["value"], brief.UPFRONT_QUOTE_MODEL)
        self.assertEqual(figure(block, "quoted_fare"), "34.50")
        self.assertEqual(figure(block, "charged_total"), "39.00")
        self.assertEqual(figure(block, "charged_over_quote"), "4.50")
        self.assertNotIn("refund", block)
        self.assertNotIn("recomputed_fare", block)

    def test_the_no_show_fee_is_the_greater_fee_and_names_its_dimension(self):
        cases = {
            201: ("4.00", brief.money.DIMENSION_TIE),
            202: ("6.00", brief.money.DIMENSION_ZONE_CLASS),
            208: ("8.00", brief.money.DIMENSION_VEHICLE_TIER),
        }
        for case_no, (amount, dimension) in cases.items():
            block = money_block(brief.build_brief(case_no))
            self.assertEqual(figure(block, "schedule_fee"), amount, "case {0}".format(case_no))
            self.assertEqual(
                figure(block, "schedule_fee_dimension"), dimension, "case {0}".format(case_no)
            )

    def test_the_no_show_payments_are_computed_on_the_charged_figure(self):
        cases = {206: ("3.20", "2.00"), 208: ("6.40", "4.00")}
        for case_no, (compensation, goodwill) in cases.items():
            block = money_block(brief.build_brief(case_no))
            self.assertEqual(
                figure(block, "driver_compensation"), compensation, "case {0}".format(case_no)
            )
            self.assertEqual(figure(block, "goodwill"), goodwill, "case {0}".format(case_no))
            self.assertEqual(
                figure(block, "driver_compensation"),
                money.payable_string(
                    money._dec(figure(block, "constants", "driver_compensation_rate"))
                    * money._dec(figure(block, "fee_charged"))
                ),
                "case {0}".format(case_no),
            )

    def test_the_prose_constants_are_marked_not_structured(self):
        """A figure the policy states only in prose says so, and names its clause."""
        block = money_block(brief.build_brief(104))
        constants = block["constants"]
        self.assertIs(constants[brief.FULL_REFUND_SHARE]["structured"], False)
        self.assertEqual(constants[brief.FULL_REFUND_SHARE]["clause_id"], brief.POL_RD_02)
        self.assertIs(constants[brief.CAP_RATIO]["structured"], False)
        self.assertEqual(constants[brief.CAP_RATIO]["clause_id"], brief.POL_RD_03)
        self.assertIs(constants[brief.TOLERANCE_KM]["structured"], False)
        # The structured fare constants are marked as such, not lumped in with them.
        self.assertIs(constants["base_fare"]["structured"], True)
        self.assertIs(constants["de_minimis_refund"]["structured"], True)

    def test_the_block_names_the_prose_only_figures_it_does_not_compute(self):
        """POL-RD-04's rate, POL-RD-09's cap and radius, POL-RD-10's ceiling."""
        block = money_block(brief.build_brief(104))
        named = {entry["clause_id"]: entry for entry in block["not_structured"]}
        self.assertIn(brief.POL_RD_04, named)
        self.assertIn(brief.POL_RD_09, named)
        self.assertIn(brief.POL_RD_10, named)
        for entry in block["not_structured"]:
            self.assertIn("not a structured field", entry["note"])

    def test_the_prose_constants_are_read_from_the_clause_text(self):
        """A figure that came from a clause must move when the clause moves."""
        with (PROJECT_ROOT / "policy" / "route_deviation.json").open("r", encoding="utf-8") as handle:
            policy = json.load(handle)
        for clause in policy["clauses"]:
            if clause["id"] == brief.POL_RD_03:
                clause["rule"] = clause["rule"].replace("130%", "140%")
        constants = brief._money_prose_constants(policy)
        self.assertEqual(str(constants[brief.CAP_RATIO]), "1.4")

    def test_a_missing_prose_line_raises_rather_than_defaulting(self):
        with (PROJECT_ROOT / "policy" / "route_deviation.json").open("r", encoding="utf-8") as handle:
            policy = json.load(handle)
        for clause in policy["clauses"]:
            if clause["id"] == brief.POL_RD_03:
                clause["rule"] = "the cap is stated nowhere in this sentence"
        with self.assertRaises(loader.LoaderError):
            brief._money_prose_constants(policy)


# --------------------------------------------------------------------------
# The platform parameters in force, at policy version 3
# --------------------------------------------------------------------------
# The corpus, split by category. Every case was authored under version-1
# parameters and none carries `trip_record.platform_policy`, so version 3 has to
# derive the block rather than read it.
NO_SHOW_CASES = tuple(
    entry["case_no"] for entry in manifest() if entry["category"] == "NO_SHOW_CHARGE"
)
ROUTE_DEVIATION_CASES = tuple(
    entry["case_no"] for entry in manifest() if entry["category"] == "ROUTE_DEVIATION"
)

# The version-1 fee table the derivation reads, read here independently so the
# test compares the brief against the file rather than against the derivation.
V1_FEE_SCHEDULE = json.loads(
    (PROJECT_ROOT / "policy" / "no_show.json").read_text(encoding="utf-8"),
    parse_float=Decimal,
)["fee_schedule"]

# The ten fields `trip_record.platform_policy` carries by contract.
PLATFORM_POLICY_FIELDS = {
    "grace_after_match_sec",
    "advance_grace_before_scheduled_sec",
    "free_wait_sec",
    "no_show_threshold_sec",
    "cancellation_fee_sgd",
    "rider_gross_cancellation_fee_sgd",
    "waiting_fee_sgd",
    "fee_goes_to",
    "arrival_marker",
    "source",
}


def trip_record(brief_obj):
    """The TRIP_RECORD artifact inside a brief."""
    for artifact in brief_obj["case"]["evidence"]:
        if artifact["evidence_type"] == "TRIP_RECORD":
            return artifact
    raise AssertionError("brief has no TRIP_RECORD artifact")


def in_force_block(case_no, policy_version=3):
    """``platform_policy_in_force`` as a brief of ``case_no`` carries it."""
    return trip_record(
        brief.build_brief_for_case(
            loader.load_case(case_no), policy_version=policy_version
        )
    )["payload"].get(brief.PLATFORM_POLICY_IN_FORCE_KEY)


def artifact_of(brief_obj, evidence_type):
    """One artifact of a brief, or ``None`` where the case carries none."""
    for artifact in brief_obj["case"]["evidence"]:
        if artifact["evidence_type"] == evidence_type:
            return artifact
    return None


def derived_of(brief_obj, evidence_type, key):
    """One derived block of one artifact, or ``{}``."""
    artifact = artifact_of(brief_obj, evidence_type)
    payload = artifact.get("payload") if artifact else None
    payload = payload if isinstance(payload, dict) else {}
    derived = payload.get("derived")
    derived = derived if isinstance(derived, dict) else {}
    block = derived.get(key)
    return block if isinstance(block, dict) else {}


def money_block_at(case_no, policy_version):
    """The money block a brief of ``case_no`` publishes at one version.

    Named apart from :func:`money_block`, which takes a brief already in hand.
    """
    return derived_of(
        brief.build_brief_for_case(
            loader.load_case(case_no), policy_version=policy_version
        ),
        "FARE_BREAKDOWN",
        "money",
    )


def dwell_figure(case_no, policy_version):
    arrival = derived_of(
        brief.build_brief_for_case(
            loader.load_case(case_no), policy_version=policy_version
        ),
        "GPS_TRACE",
        "arrival",
    )
    return (arrival.get("thresholds") or {}).get("minimum_dwell_sec", {}).get("value")


# The money figures both versions publish, and that must not move between them.
MONEY_FIGURE_KEYS = (
    "schedule_fee",
    "fee_charged",
    "difference",
    "driver_compensation",
    "goodwill",
)

# The two policy rates the money block carries, which are read from the loaded
# policy's fee_schedule at both versions.
MONEY_RATE_KEYS = ("driver_compensation_rate", "pin_ambiguity_goodwill_rate")


def money_figures(case_no, policy_version):
    """Every money figure a brief publishes, by name."""
    block = money_block_at(case_no, policy_version)
    figures = {
        key: block[key]["value"] for key in MONEY_FIGURE_KEYS if key in block
    }
    for key in MONEY_RATE_KEYS:
        value = (block.get("constants") or {}).get(key)
        if isinstance(value, dict):
            figures["constants." + key] = value["value"]
    return figures


# The trip-record fields POL-GEN-08 and POL-NS-10 may read and that no case in
# this repository carries. Absent means false or null, so a case without them
# must brief at version 3 without error.
OPTIONAL_SCOPE_FIELDS = ("safety_flag", "complaint_flag")
OPTIONAL_TRIP_FIELDS = ("scheduled_at", "events")


class VersionThreePlatformPolicyTests(unittest.TestCase):
    """What a version-3 brief says the platform parameters in force are.

    Every case in this repository was written under version-1 parameters, and
    none carries ``trip_record.platform_policy``. So at version 3 the brief
    derives the block from the version-1 fee table -- exactly the block the
    draft's own backfill script would have written into the case file -- and the
    case file is not touched. That script is not in this repository and nothing
    like it is run.
    """

    def test_every_corpus_no_show_case_gets_the_authored_v1_block(self):
        self.assertTrue(NO_SHOW_CASES)
        for case_no in NO_SHOW_CASES:
            with self.subTest(case_no=case_no):
                block = in_force_block(case_no)
                self.assertIsNotNone(block, "a no-show brief carried no block")
                self.assertEqual(brief.AUTHORED_V1_SOURCE, block["source"])
                self.assertEqual(PLATFORM_POLICY_FIELDS, set(block))

    def test_the_derived_fee_and_free_wait_are_the_version_one_ones(self):
        """The same fee and free wait the case was authored under.

        Read again out of the version-1 file, independently of the derivation,
        and compared: a derivation that had drifted would fail here.
        """
        for case_no in NO_SHOW_CASES:
            with self.subTest(case_no=case_no):
                payload = next(
                    artifact["payload"]
                    for artifact in loader.load_case(case_no)["evidence"]
                    if artifact["evidence_type"] == "TRIP_RECORD"
                )
                zone = payload["pickup_zone_class"]
                tier = payload["vehicle_type"]
                expected_fee, _dimension = money.schedule_fee(
                    V1_FEE_SCHEDULE["zone_class_fee_sgd"][zone],
                    V1_FEE_SCHEDULE["vehicle_tier_fee_sgd"][tier],
                )
                block = in_force_block(case_no)
                self.assertEqual(
                    int(V1_FEE_SCHEDULE["minimum_dwell_sec"][zone]),
                    block["free_wait_sec"],
                )
                self.assertEqual(expected_fee, block["cancellation_fee_sgd"])

    def test_two_named_cases_carry_the_figures_their_zone_and_tier_give(self):
        # 201 is a STANDARD zone and an RYDE_X vehicle: the greater of 4.0 and
        # 4.0. 208 is RYDE_XL, whose tier fee is 8.0 and governs. Both dwell for
        # the STANDARD zone's 300 s.
        self.assertEqual(
            {"free_wait_sec": 300, "cancellation_fee_sgd": Decimal("4.0")},
            {
                key: in_force_block(201)[key]
                for key in ("free_wait_sec", "cancellation_fee_sgd")
            },
        )
        self.assertEqual(
            {"free_wait_sec": 300, "cancellation_fee_sgd": Decimal("8.0")},
            {
                key: in_force_block(208)[key]
                for key in ("free_wait_sec", "cancellation_fee_sgd")
            },
        )

    def test_a_case_that_carries_a_block_uses_its_own(self):
        """A record's own parameters win over anything derived from version 1."""
        case = copy.deepcopy(loader.load_case(201))
        payload = next(
            artifact["payload"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "TRIP_RECORD"
        )
        own = {
            "grace_after_match_sec": 120,
            "advance_grace_before_scheduled_sec": 600,
            "free_wait_sec": 240,
            "no_show_threshold_sec": 480,
            "cancellation_fee_sgd": Decimal("6.5"),
            "rider_gross_cancellation_fee_sgd": Decimal("7.02"),
            "waiting_fee_sgd": Decimal("4.0"),
            "fee_goes_to": "PLATFORM",
            "arrival_marker": "GPS_AUTO",
            "source": "RECORD-PLATFORM",
        }
        payload["platform_policy"] = own

        briefed = brief.build_brief_for_case(case, policy_version=3)
        payload_out = trip_record(briefed)["payload"]
        self.assertEqual(own, payload_out[brief.PLATFORM_POLICY_IN_FORCE_KEY])
        self.assertEqual("RECORD-PLATFORM", payload_out[brief.PLATFORM_POLICY_IN_FORCE_KEY]["source"])
        # The record's own key stays where it was; the brief adds the in-force
        # block beside it rather than moving or rewriting it.
        self.assertEqual(own, payload_out["platform_policy"])

    def test_a_route_deviation_case_gets_no_in_force_block(self):
        """The block is a no-show parameter set; a deviation brief carries none."""
        self.assertTrue(ROUTE_DEVIATION_CASES)
        for case_no in ROUTE_DEVIATION_CASES:
            with self.subTest(case_no=case_no):
                self.assertIsNone(in_force_block(case_no))

    def test_versions_one_and_two_carry_no_in_force_block(self):
        for case_no in (201, 208):
            for version in (1, 2):
                with self.subTest(case_no=case_no, version=version):
                    self.assertIsNone(in_force_block(case_no, version))

    def test_a_full_brief_build_leaves_every_case_file_byte_identical(self):
        """The derivation is at build time: nothing is written into a case file."""
        files = sorted((PROJECT_ROOT / "data" / "cases").glob("case-*.json"))
        self.assertEqual(29, len(files))
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        }
        for case_no in case_numbers():
            brief.build_brief_for_case(
                loader.load_case(case_no), policy_version=3
            )
        after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        }
        self.assertEqual(before, after)

    # -- the money and the dwell, at version 3 ----------------------------
    def test_every_corpus_no_show_case_keeps_its_version_two_figures(self):
        """The block is derived from the version-1 table, so no figure moves.

        Every money figure and the dwell minimum are compared with the same
        figure at version 2. This is the check the sheet asks for, and it is the
        reason the derivation reads the version-1 table rather than the loaded
        version-3 ``fee_schedule.defaults``: the fee and the free wait a
        version-1 case was authored under are what its answer key was written
        against.
        """
        self.assertTrue(NO_SHOW_CASES)
        for case_no in NO_SHOW_CASES:
            with self.subTest(case_no=case_no):
                self.assertEqual(
                    money_figures(case_no, 2), money_figures(case_no, 3)
                )
                self.assertEqual(
                    dwell_figure(case_no, 2), dwell_figure(case_no, 3)
                )

    def test_version_three_publishes_the_waiting_fee_and_drops_the_dimension(self):
        """The two deliberate differences, asserted rather than left implicit."""
        for case_no in (201, 208):
            with self.subTest(case_no=case_no):
                version_two = money_block_at(case_no, 2)
                version_three = money_block_at(case_no, 3)
                self.assertNotIn("waiting_fee_sgd", version_two["constants"])
                self.assertEqual(
                    Decimal("5.00"),
                    money._dec(version_three["constants"]["waiting_fee_sgd"]["value"]),
                )
                self.assertIn("schedule_fee_dimension", version_two)
                self.assertNotIn("schedule_fee_dimension", version_three)

    def test_version_three_reads_the_fee_and_the_free_wait_from_the_block(self):
        """A record whose block states other figures gets those figures."""
        case = copy.deepcopy(loader.load_case(201))
        next(
            artifact["payload"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "TRIP_RECORD"
        )["platform_policy"] = {
            "grace_after_match_sec": 180,
            "advance_grace_before_scheduled_sec": 900,
            "free_wait_sec": 240,
            "no_show_threshold_sec": None,
            "cancellation_fee_sgd": Decimal("7.25"),
            "rider_gross_cancellation_fee_sgd": Decimal("7.83"),
            "waiting_fee_sgd": Decimal("3.50"),
            "fee_goes_to": "DRIVER",
            "arrival_marker": "BUTTON",
            "source": "RECORD-PLATFORM",
        }
        briefed = brief.build_brief_for_case(case, policy_version=3)
        block = derived_of(briefed, "FARE_BREAKDOWN", "money")
        self.assertEqual(Decimal("7.25"), money._dec(block["schedule_fee"]["value"]))
        self.assertEqual(
            Decimal("3.50"),
            money._dec(block["constants"]["waiting_fee_sgd"]["value"]),
        )
        arrival = derived_of(briefed, "GPS_TRACE", "arrival")
        self.assertEqual(
            240, arrival["thresholds"]["minimum_dwell_sec"]["value"]
        )

    def test_a_gross_charged_line_reconciles_at_version_three(self):
        """POL-NS-08(d): the line may equal the net or, where named, the gross."""
        case = copy.deepcopy(loader.load_case(201))
        next(
            artifact["payload"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "TRIP_RECORD"
        )["platform_policy"] = {
            "grace_after_match_sec": 180,
            "advance_grace_before_scheduled_sec": 900,
            "free_wait_sec": 300,
            "no_show_threshold_sec": None,
            "cancellation_fee_sgd": Decimal("4.0"),
            "rider_gross_cancellation_fee_sgd": Decimal("5.28"),
            "waiting_fee_sgd": Decimal("5.0"),
            "fee_goes_to": "DRIVER",
            "arrival_marker": "BUTTON",
            "source": "RECORD-PLATFORM",
        }
        fare = next(
            artifact["payload"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "FARE_BREAKDOWN"
        )
        fare["cancellation_fee"] = Decimal("5.28")

        version_three = derived_of(
            brief.build_brief_for_case(case, policy_version=3),
            "FARE_BREAKDOWN",
            "money",
        )
        self.assertEqual(
            Decimal("5.28"), money._dec(version_three["fee_charged"]["value"])
        )
        self.assertEqual(
            Decimal("0.00"), money._dec(version_three["difference"]["value"])
        )

        # The same line at version 2 is a difference, because version 2 has no
        # gross figure to reconcile it against.
        version_two = derived_of(
            brief.build_brief_for_case(case, policy_version=2),
            "FARE_BREAKDOWN",
            "money",
        )
        self.assertEqual(
            Decimal("1.28"), money._dec(version_two["difference"]["value"])
        )

    def test_the_waiting_time_line_and_the_fee_in_force_are_published(self):
        """POL-NS-10(d) and (e): case 1740, whose fee line was unreadable.

        The block published the waiting-time fee in force as a *constant*, and
        ``constants`` is deliberately not somewhere a draft may read an amount
        from -- so all four drafts of 1740 proposed 5.00 and every one was
        rejected as not read off. Both figures are published from version 3 on,
        each with the artifact it came from.
        """
        case = dev_v2_case(1740)
        block = derived_of(
            brief.build_brief_for_case(case, policy_version=3),
            "FARE_BREAKDOWN",
            "money",
        )
        self.assertEqual(
            Decimal("5.00"), money._dec(block[brief.WAITING_TIME_FEE_KEY]["value"])
        )
        self.assertEqual(
            "EV-FARE-01740", block[brief.WAITING_TIME_FEE_KEY]["evidence_id"]
        )
        self.assertEqual(
            Decimal("5.00"),
            money._dec(block[brief.WAITING_FEE_IN_FORCE_KEY]["value"]),
        )
        self.assertEqual(
            "EV-TRIP-01740", block[brief.WAITING_FEE_IN_FORCE_KEY]["evidence_id"]
        )
        for key in (brief.WAITING_TIME_FEE_KEY, brief.WAITING_FEE_IN_FORCE_KEY):
            with self.subTest(key=key):
                self.assertEqual("POL-NS-10", block[key]["clause_id"])

    def test_a_draft_proposing_the_waiting_fee_reads_it_off(self):
        """The read-off check accepts 5.00 for 1740, and names the figure it read."""
        briefed = brief.build_brief_for_case(dev_v2_case(1740), policy_version=3)
        figures = pipeline.published_money_figures(pipeline.money_block(briefed))
        self.assertEqual(
            "waiting_time_fee.value",
            pipeline.amount_reads_off(Decimal("5.00"), figures),
        )
        draft = {
            "ruling": {
                "ruling": "FULL_REFUND",
                "amount_sgd": "5.00",
                "driver_compensation_sgd": None,
                "referrals": [],
                "confidence": 0.9,
                "explanation": "the waiting-time line POL-NS-10(e) refunds in full",
            }
        }
        failures, unverifiable = pipeline.check_judge_draft(draft, briefed)
        self.assertEqual((), failures)
        self.assertEqual((), unverifiable)

    def test_the_waiting_fee_is_not_published_at_versions_one_and_two(self):
        """The publication is a version-3 reading; the earlier briefs do not move."""
        case = dev_v2_case(1740)
        for version in (1, 2):
            with self.subTest(version=version):
                block = derived_of(
                    brief.build_brief_for_case(case, policy_version=version),
                    "FARE_BREAKDOWN",
                    "money",
                )
                self.assertNotIn(brief.WAITING_TIME_FEE_KEY, block)
                self.assertNotIn(brief.WAITING_FEE_IN_FORCE_KEY, block)
                self.assertIsNone(
                    pipeline.amount_reads_off(
                        Decimal("5.00"), pipeline.published_money_figures(block)
                    )
                )


class VersionThreeGapGradingTests(unittest.TestCase):
    """How version 3 grades a ``GPS_GAP`` tag, by the clause that owns the category.

    Two clauses grade a gap and they belong to two different policies:

    * **POL-NS-08(b)** grades a **no-show** trace's gap by the waiting window --
      the reading part 2 describes, and the one the ``integrity`` block (which
      carries the weights) lives beside in ``no_show.json``;
    * **POL-RD-07**'s own limbs (a) and (b) grade a **route-deviation** trace's
      gap -- the reading the key owner ruled for case 1775. A gap is *short* when
      every gap between consecutive fixes is within limb (a)'s limit and no
      straight-line jump between consecutive fixes exceeds limb (b)'s, and
      *long* otherwise. Both limits are read out of the clause's own sentence,
      never typed, and a clause whose sentence has moved is a refusal.

    Neither reading is the flat 0.6: part 2 graded every gap by the no-show
    window, which turned a route-deviation gap into a short one and raised its
    weight, and part 3 left every route-deviation gap ungraded at version 1's
    0.6. Both were wrong, and the readings below are what replaces them.
    """

    def gps_admissibility(self, case, policy_version=3):
        briefed = brief.build_brief_for_case(case, policy_version=policy_version)
        return artifact_of(briefed, "GPS_TRACE")["admissibility"]

    def gap_variant(self, admissibility):
        """The one ``GPS_GAP_*`` variant the artifact was graded into."""
        return next(
            code for code in admissibility["issues"] if code.startswith("GPS_GAP_")
        )

    def route_deviation_cases(self):
        """The four corpus-and-external route-deviation artifacts carrying the tag."""
        yield "corpus 110", loader.load_case(110)
        for set_name, case_no in (("codex", 9115), ("wild", 512), ("wild", 517)):
            yield "{0} {1}".format(set_name, case_no), loader.load_external_set_case(
                loader.EXTERNAL_DIR / set_name, case_no
            )

    def test_every_case_here_is_a_route_deviation_case(self):
        """The premise, so the tests below are about the right category."""
        for name, case in self.route_deviation_cases():
            with self.subTest(case=name):
                self.assertEqual("ROUTE_DEVIATION", case["dispute"]["category"])

    def test_a_route_deviation_gap_is_graded_by_pol_rd_07(self):
        """The ungraded tag is gone: a variant replaces it and the detail names it."""
        for name, case in self.route_deviation_cases():
            with self.subTest(case=name):
                admissibility = self.gps_admissibility(case)
                self.assertNotIn(prepass.GPS_GAP_CODE, admissibility["issues"])
                variant = self.gap_variant(admissibility)
                self.assertIn(variant, prepass.GPS_GAP_VARIANTS)
                detail = next(
                    detail
                    for detail in admissibility["issue_details"]
                    if detail.get("code") == prepass.GPS_GAP_CODE
                )
                self.assertEqual(variant, detail["variant"])

    def test_all_four_route_deviation_gaps_are_long(self):
        """Every one of their gaps exceeds limb (a)'s 90 s, so all grade long."""
        for name, case in self.route_deviation_cases():
            with self.subTest(case=name):
                self.assertEqual(
                    prepass.GPS_GAP_LONG_INSIDE_WINDOW,
                    self.gap_variant(self.gps_admissibility(case)),
                )

    def test_the_four_route_deviation_weights_are_the_ones_part_three_gave_them(self):
        expected = {
            "corpus 110": Decimal("0.39"),
            "codex 9115": Decimal("0.60"),
            "wild 512": Decimal("0.39"),
            "wild 517": Decimal("0.39"),
        }
        seen = {
            name: Decimal(str(self.gps_admissibility(case)["weight_multiplier"]))
            for name, case in self.route_deviation_cases()
        }
        self.assertEqual(expected, seen)

    def test_a_long_route_deviation_weight_equals_the_declared_one(self):
        """The long reading is version 1's weight, so it equals the case file's own."""
        for name, case in self.route_deviation_cases():
            declared = next(
                artifact["admissibility"]["weight_multiplier"]
                for artifact in case["evidence"]
                if artifact["evidence_type"] == "GPS_TRACE"
            )
            with self.subTest(case=name):
                self.assertEqual(
                    Decimal(str(declared)),
                    Decimal(
                        str(self.gps_admissibility(case)["weight_multiplier"])
                    ),
                )

    def test_a_short_route_deviation_gap_grades_short(self):
        """1775's one 40 s gap and its 0.4 km jump: the short reading, 0.85."""
        admissibility = self.gps_admissibility(dev_v2_case(1775))
        self.assertEqual(
            prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW, self.gap_variant(admissibility)
        )
        self.assertEqual(
            Decimal("0.85"), Decimal(str(admissibility["weight_multiplier"]))
        )

    def test_a_long_route_deviation_gap_grades_long(self):
        """1776's 100 s gap and 1.0 km jump: the long reading, 0.6."""
        admissibility = self.gps_admissibility(dev_v2_case(1776))
        self.assertEqual(
            prepass.GPS_GAP_LONG_INSIDE_WINDOW, self.gap_variant(admissibility)
        )
        self.assertEqual(
            Decimal("0.6"), Decimal(str(admissibility["weight_multiplier"]))
        )

    def test_a_short_gap_with_a_long_jump_grades_long(self):
        """Limb (b) alone decides it: a 40 s gap with a 600 m jump is long.

        The fixture is 1775 with one fix moved 600 m north of the fix before it,
        so every interval between consecutive fixes is still within limb (a)'s
        90 s and only the jump exceeds limb (b)'s 500 m.
        """
        case = copy.deepcopy(dev_v2_case(1775))
        trace = next(
            artifact
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "GPS_TRACE"
        )
        points = trace["payload"]["points"]
        gap_from = trace["payload"]["gaps"][0]["from_ts"]
        index = next(i for i, point in enumerate(points) if point["ts"] == gap_from)
        # The case files are read with ``parse_float=Decimal``, so the moved
        # coordinate is written back as one: a bare float would make the
        # arithmetic below mix the two types.
        moved_lat = float(points[index]["lat"]) + 600 / 111320.0
        points[index + 1]["lat"] = Decimal(str(moved_lat))
        points[index + 1]["lng"] = points[index]["lng"]

        admissibility = self.gps_admissibility(case)
        self.assertEqual(
            prepass.GPS_GAP_LONG_INSIDE_WINDOW, self.gap_variant(admissibility)
        )
        self.assertEqual(
            Decimal("0.6"), Decimal(str(admissibility["weight_multiplier"]))
        )

    def test_the_limits_are_the_ones_pol_rd_07_states(self):
        """90 s and 500 m are the clause's own figures, read from its sentence."""
        clause = brief._clause_of(
            loader.load_policies("ROUTE_DEVIATION", 3)["category"], brief.POL_RD_07
        )
        self.assertEqual((90.0, 500.0), brief._route_deviation_gap_limits(clause))

    def test_the_limits_are_read_from_the_clause_and_a_moved_sentence_refuses(self):
        """Neither limit is typed: a clause that no longer states them is a refusal."""
        real = loader.load_policies

        def moved(category, policy_version=1):
            policies = real(category, policy_version)
            for clause in policies["category"]["clauses"]:
                if clause["id"] == brief.POL_RD_07:
                    clause["rule"] = clause["rule"].replace(
                        "90 seconds", "ninety seconds"
                    )
            return policies

        with mock.patch.object(brief.loader, "load_policies", side_effect=moved):
            with self.assertRaises(loader.LoaderError) as caught:
                brief.build_brief_for_case(dev_v2_case(1775), policy_version=3)
        self.assertIn(brief.POL_RD_07, str(caught.exception))

    def test_the_weights_are_read_from_the_policy_not_typed(self):
        """0.85 and 0.6 are not literals: they are the policy's own entries."""
        weights = prepass.weights_from_policy(
            loader.load_policies("NO_SHOW_CHARGE", 3)["category"]
        )
        self.assertNotIn(prepass.GPS_GAP_CODE, weights)
        self.assertEqual(
            Decimal("0.85"),
            Decimal(str(weights[prepass.GPS_GAP_SHORT_OR_OUTSIDE_WINDOW])),
        )
        self.assertEqual(
            Decimal("0.6"),
            Decimal(str(weights[prepass.GPS_GAP_LONG_INSIDE_WINDOW])),
        )

    def test_the_no_show_gaps_are_still_graded(self):
        """Part 2's behaviour for the two no-show artifacts, unchanged."""
        expected = {
            210: ("GPS_GAP_LONG_INSIDE_WINDOW", Decimal("0.25")),
            211: ("GPS_GAP_LONG_INSIDE_WINDOW", Decimal("0.39")),
        }
        seen = {}
        for case_no in sorted(expected):
            admissibility = self.gps_admissibility(loader.load_case(case_no))
            seen[case_no] = (
                self.gap_variant(admissibility),
                Decimal(str(admissibility["weight_multiplier"])),
            )
        self.assertEqual(expected, seen)


class VersionThreeScopeGateTests(unittest.TestCase):
    """The optional fields POL-GEN-08 and POL-NS-10 read, and their absence.

    ``dispute.safety_flag``, ``dispute.complaint_flag``,
    ``trip_record.scheduled_at`` and ``trip_record.events[]`` are all optional,
    and no case in this repository carries any of them. The rule is that absent
    means false or null, so nothing has to be added for a case that has none:
    what this class holds is that a version-3 brief of such a case is built
    without error, and that the brief invents none of the four.
    """

    def test_no_corpus_case_carries_any_of_the_four(self):
        """The premise, so the test below is not vacuous."""
        for case_no in case_numbers():
            case = loader.load_case(case_no)
            with self.subTest(case_no=case_no):
                for field in OPTIONAL_SCOPE_FIELDS:
                    self.assertNotIn(field, case["dispute"])
                payload = next(
                    artifact["payload"]
                    for artifact in case["evidence"]
                    if artifact["evidence_type"] == "TRIP_RECORD"
                )
                for field in OPTIONAL_TRIP_FIELDS:
                    self.assertNotIn(field, payload)

    def test_every_corpus_case_briefs_at_version_three_without_them(self):
        for case_no in case_numbers():
            with self.subTest(case_no=case_no):
                briefed = brief.build_brief_for_case(
                    loader.load_case(case_no), policy_version=3
                )
                self.assertEqual(case_no, briefed["case"]["case_no"])
                self.assertIn("evidence", briefed["case"])

    def test_the_brief_invents_none_of_the_four(self):
        """Absent means absent: nothing is defaulted into the brief either."""
        for case_no in case_numbers():
            with self.subTest(case_no=case_no):
                briefed = brief.build_brief_for_case(
                    loader.load_case(case_no), policy_version=3
                )
                for field in OPTIONAL_SCOPE_FIELDS:
                    self.assertNotIn(field, briefed["case"]["dispute"])
                payload = trip_record(briefed)["payload"]
                for field in OPTIONAL_TRIP_FIELDS:
                    self.assertNotIn(field, payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
