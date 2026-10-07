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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, facts, loader, money  # noqa: E402

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
