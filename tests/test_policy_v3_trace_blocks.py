"""Policy version 3's two new GPS-trace derived blocks. No model call.

Version 3 adds two readings to a route-deviation trace's ``derived`` facts:

* ``waypoint_approach`` -- POL-RD-04 says the trace "must corroborate" a
  rider-requested stop, which means the vehicle passes within a distance of the
  requested waypoint. The brief computed nothing about it, so the judge had to
  work it out from raw fixes and three calibration cases missed.
* ``advisory_area`` -- POL-RD-03(c) asks whether the deviation "is matched by an
  actual route that leaves the optimal corridor before the affected segment and
  rejoins it after". The record carries no optimal-route polyline, only the
  advisory's bounding box, so how the trace stands against that box is the
  closest test of the limb the record allows.

Both are gated to version 3 and both live in ``route_deviation.json``, so a
no-show brief carries neither and versions 1 and 2 are byte-identical. The
threshold the first block compares against is **read from POL-RD-04's own
sentence**, the way ``pipeline.confidence_floor`` reads the floor, and a clause
whose sentence has moved is a refusal rather than a default.

Run from the project root with::

    python -m unittest tests.test_policy_v3_trace_blocks -v
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, facts, loader, money  # noqa: E402

DEV_V2 = loader.EXTERNAL_DIR / "dev-v2"

# The three calibration cases the first block was written for: two where the
# trace passes the requested waypoint and one where it never comes near it.
WITHIN_CASES = (1761, 1762)
NOT_WITHIN_CASE = 1782
# The closure case the second block was written for: the trace never enters the
# advisory's box.
CLOSURE_CASE = 1758

# The two versions that must carry neither block.
EARLIER_VERSIONS = (1, 2)


def dev_case(case_no):
    return loader.load_external_set_case(DEV_V2, case_no)


def derived_of(briefed):
    """The GPS trace's ``derived`` facts."""
    artifact = next(
        artifact
        for artifact in briefed["case"]["evidence"]
        if artifact["evidence_type"] == "GPS_TRACE"
    )
    return artifact["payload"]["derived"]


def canonical(node):
    """The project's canonical JSON, which reads a ``Decimal`` as a number."""
    return money.dumps_canonical(node)


def chat_payload(case):
    return next(
        artifact["payload"]
        for artifact in case["evidence"]
        if artifact["evidence_type"] == "CHAT_LOG"
    )


def advisory_artifact(case):
    return next(
        artifact
        for artifact in case["evidence"]
        if artifact["evidence_type"] == "TRAFFIC_ADVISORY"
    )


class WaypointApproachTests(unittest.TestCase):
    """POL-RD-04: how close the trace came to each rider-requested waypoint."""

    @classmethod
    def setUpClass(cls):
        cls.briefs = {
            case_no: brief.build_brief_for_case(dev_case(case_no), policy_version=3)
            for case_no in WITHIN_CASES + (NOT_WITHIN_CASE,)
        }

    def block(self, case_no):
        return derived_of(self.briefs[case_no])[brief.WAYPOINT_APPROACH_KEY]

    def test_the_block_is_on_the_trace_and_names_the_clause(self):
        block = self.block(1761)
        self.assertEqual(brief.POL_RD_04, block["clause_id"])
        self.assertEqual(200.0, float(block["threshold_m"]["value"]))
        self.assertEqual(brief.POL_RD_04, block["threshold_m"]["clause_id"])

    def test_1761_and_1762_pass_within_the_threshold(self):
        for case_no in WITHIN_CASES:
            with self.subTest(case_no=case_no):
                messages = self.block(case_no)["messages"]
                self.assertEqual(1, len(messages))
                entry = messages[0]
                self.assertIs(True, entry["within_threshold"]["value"])
                self.assertLessEqual(
                    float(entry["nearest_fix"]["distance_m"]["value"]), 200.0
                )

    def test_1782_never_comes_near_the_waypoint(self):
        entry = self.block(NOT_WITHIN_CASE)["messages"][0]
        self.assertIs(False, entry["within_threshold"]["value"])
        self.assertGreater(float(entry["nearest_fix"]["distance_m"]["value"]), 200.0)

    def test_the_distance_is_the_haversine_to_the_nearest_fix(self):
        """The figure is the trace's own, computed with ``facts.haversine_m``."""
        case = dev_case(1761)
        points = next(
            artifact["payload"]["points"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "GPS_TRACE"
        )
        hint = chat_payload(case)["messages"][0]["waypoint_hint"]
        expected = min(
            facts.distances_to_point(points, hint["lat"], hint["lng"])
        )
        entry = self.block(1761)["messages"][0]
        self.assertAlmostEqual(
            expected, float(entry["nearest_fix"]["distance_m"]["value"]), places=6
        )

    def test_the_entry_names_the_message_its_sender_and_its_hint(self):
        case = dev_case(1761)
        message = chat_payload(case)["messages"][0]
        chat_id = next(
            artifact["evidence_id"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "CHAT_LOG"
        )
        entry = self.block(1761)["messages"][0]
        self.assertEqual(chat_id, entry["evidence_id"])
        self.assertEqual(message["msg_id"], entry["message_id"])
        self.assertEqual(message["sent_at"], entry["sent_at"]["value"])
        self.assertEqual("RIDER", entry["sender"]["value"])
        self.assertEqual("Jurong Point", entry["label"]["value"])
        self.assertEqual(hint_of(message), entry["coordinates"]["value"])

    def test_a_case_with_no_hint_produces_no_entries(self):
        case = copy.deepcopy(dev_case(1761))
        for message in chat_payload(case)["messages"]:
            message["waypoint_hint"] = None
        block = derived_of(
            brief.build_brief_for_case(case, policy_version=3)
        )[brief.WAYPOINT_APPROACH_KEY]
        self.assertEqual([], block["messages"])

    def test_versions_one_and_two_carry_no_block(self):
        for case_no in WITHIN_CASES:
            for version in EARLIER_VERSIONS:
                with self.subTest(case_no=case_no, version=version):
                    briefed = brief.build_brief_for_case(
                        dev_case(case_no), policy_version=version
                    )
                    self.assertNotIn(
                        brief.WAYPOINT_APPROACH_KEY, derived_of(briefed)
                    )

    def test_the_threshold_is_read_from_the_clause_and_a_moved_sentence_refuses(self):
        """The 200 is never typed: a clause that does not state it is a refusal."""
        real = loader.load_policies

        def moved(category, policy_version=1):
            policies = real(category, policy_version)
            for clause in policies["category"]["clauses"]:
                if clause["id"] == brief.POL_RD_04:
                    clause["rule"] = "The gps_trace must corroborate it, somehow."
            return policies

        with mock.patch.object(brief.loader, "load_policies", side_effect=moved):
            with self.assertRaises(loader.LoaderError) as caught:
                brief.build_brief_for_case(dev_case(1761), policy_version=3)
        self.assertIn(brief.POL_RD_04, str(caught.exception))

    def test_the_block_states_a_fact_and_not_a_ruling(self):
        """Nothing in it says the instruction was corroborated or contradicted."""
        text = canonical(self.block(1761)).lower()
        for word in ("corroborat", "contradict"):
            with self.subTest(word=word):
                self.assertNotIn(word, text)


class AdvisoryAreaTests(unittest.TestCase):
    """POL-RD-03(c): how the trace stands against an advisory's own box."""

    @classmethod
    def setUpClass(cls):
        cls.briefs = {
            case_no: brief.build_brief_for_case(dev_case(case_no), policy_version=3)
            for case_no in (CLOSURE_CASE,)
        }

    def block(self, briefed):
        return derived_of(briefed)[brief.ADVISORY_AREA_KEY]

    def test_1758_never_enters_the_advisory_box(self):
        block = self.block(self.briefs[CLOSURE_CASE])
        self.assertEqual(brief.POL_RD_03, block["clause_id"])
        self.assertEqual(1, len(block["advisories"]))
        entry = block["advisories"][0]
        self.assertIs(True, entry["computed"])
        self.assertEqual(0, entry["fixes_inside"]["value"])
        self.assertIs(False, entry["trace_enters_area"]["value"])
        self.assertGreater(float(entry["minimum_distance_m"]["value"]), 0.0)

    def test_the_basis_says_what_the_test_is_for_and_that_it_decides_nothing(self):
        entry = self.block(self.briefs[CLOSURE_CASE])["advisories"][0]
        basis = entry["basis"]
        self.assertIn(brief.POL_RD_03, basis)
        self.assertIn("limb (c)", basis)
        self.assertIn("decides nothing by itself", basis)
        self.assertIn("optimal", basis)

    def test_a_trace_that_crosses_the_box_enters_it(self):
        case = copy.deepcopy(dev_case(CLOSURE_CASE))
        artifact = advisory_artifact(case)
        geometry = artifact["payload"]["geometry"]
        trace = next(
            artifact
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "GPS_TRACE"
        )
        trace["payload"]["points"][0]["lat"] = (geometry["min_lat"] + geometry["max_lat"]) / 2
        trace["payload"]["points"][0]["lng"] = (geometry["min_lng"] + geometry["max_lng"]) / 2
        entry = self.block(
            brief.build_brief_for_case(case, policy_version=3)
        )["advisories"][0]
        self.assertGreaterEqual(entry["fixes_inside"]["value"], 1)
        self.assertIs(True, entry["trace_enters_area"]["value"])
        self.assertEqual(0.0, float(entry["minimum_distance_m"]["value"]))

    def test_a_geometry_that_is_not_a_box_is_not_computed(self):
        case = copy.deepcopy(dev_case(CLOSURE_CASE))
        advisory_artifact(case)["payload"]["geometry"] = {
            "type": "polyline",
            "coordinates": [[1.36, 103.81], [1.37, 103.82]],
        }
        entry = self.block(
            brief.build_brief_for_case(case, policy_version=3)
        )["advisories"][0]
        self.assertIs(False, entry["computed"])
        self.assertIn("box", entry["reason"])
        self.assertNotIn("trace_enters_area", entry)

    def test_an_advisory_that_does_not_intersect_the_route_is_not_listed(self):
        case = copy.deepcopy(dev_case(CLOSURE_CASE))
        advisory_artifact(case)["payload"]["intersects_route"] = False
        block = self.block(brief.build_brief_for_case(case, policy_version=3))
        self.assertEqual([], block["advisories"])

    def test_versions_one_and_two_carry_no_block(self):
        for version in EARLIER_VERSIONS:
            with self.subTest(version=version):
                briefed = brief.build_brief_for_case(
                    dev_case(CLOSURE_CASE), policy_version=version
                )
                self.assertNotIn(brief.ADVISORY_AREA_KEY, derived_of(briefed))


class NoShowCarriesNeitherBlockTests(unittest.TestCase):
    """Both clauses are route-deviation clauses, so a no-show brief has neither."""

    def test_a_no_show_case_briefed_at_three_carries_neither_block(self):
        case = loader.load_external_set_case(DEV_V2, 1701)
        self.assertEqual("NO_SHOW_CHARGE", case["dispute"]["category"])
        derived = derived_of(
            brief.build_brief_for_case(case, policy_version=3)
        )
        self.assertNotIn(brief.WAYPOINT_APPROACH_KEY, derived)
        self.assertNotIn(brief.ADVISORY_AREA_KEY, derived)


def hint_of(message):
    return {
        "lat": message["waypoint_hint"]["lat"],
        "lng": message["waypoint_hint"]["lng"],
    }


if __name__ == "__main__":
    unittest.main(verbosity=2)
