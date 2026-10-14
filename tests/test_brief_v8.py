"""Tests for the version-8 brief -- the two answers of 2026-10-14, as a brief reads them.

Version 8 is version 7 with Ryde's answers of 2026-10-14 applied, and both of the
answers reach the brief through ``policy/v8/`` rather than through a second
builder:

* **the 2 km limb.** ``route_deviation.thresholds.ai_ruling_max_deviation_applied``
  is now true, so ``case.authority.ai_limit_applied`` is true on a route
  deviation whose deviation crosses the ceiling, and the pipeline's authority gate
  escalates the case citing POL-RD-25 before the judge is asked.
* **the free wait.** ``no_show.thresholds.free_wait_starts_from`` is
  ``"arrived_at"``, so the clock starts at the driver's arrival even where the
  trip is scheduled and the driver arrived early.

**The one rule this module holds the change to: version 7 does not move.** Every
reading below is asserted twice, once at version 8 and once at version 7, and the
version-7 reading is the one the committed version-7 run recorded.

The last class is the control: with the ceiling's switch put back to false in a
temporary copy of ``policy/v8/route_deviation.json``, the version-8 reading of
902's brief is the version-7 one -- so the assertions above are capable of
failing, and it is the policy file rather than the code that decides them.

No model is called and nothing is written.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, facts, loader, pipeline, policy_versions  # noqa: E402

VERSION_SEVEN = 7
VERSION_EIGHT = 8

# The organisers' two samples, converted for policy version 7 and briefed here at
# version 8: 902 is DISP-001 (a route deviation, 4.3 km) and 903 is DISP-002 (a
# no-show whose driver arrived at 08:43 for an 08:45 schedule).
RYDE_V7_DIR = loader.EXTERNAL_DIR / "ryde-v7"
ROUTE_DEVIATION_SAMPLE = 902
NO_SHOW_SAMPLE = 903

# The artifact that carries the trip record both readings hang off.
TRIP_RECORD_TYPE = "TRIP_RECORD"

# What version 8 reads on 903's free wait, and what version 7 read instead.
ARRIVED_AT = "2026-09-13T08:43:00+08:00"
SCHEDULED_AT = "2026-09-13T08:45:00+08:00"
V8_ENDS_AT = "2026-09-13T08:48:00+08:00"
V7_ENDS_AT = "2026-09-13T08:50:00+08:00"

# The one field the control flips, and the value version 7 states there.
APPLIED_KEY = "ai_ruling_max_deviation_applied"
APPLIED_PATH = ("thresholds", APPLIED_KEY)

# The two files the control's temporary copy needs, and the three version-8 files
# that make up the base.
POLICY_FILES = ("general.json", "no_show.json", "route_deviation.json")


def sample(case_no):
    """One organisers' sample, loaded from the set's own directory."""
    return loader.load_external_set_case(RYDE_V7_DIR, case_no)


def built(case_no, policy_version):
    """One sample's brief at one policy version."""
    return brief.build_brief_for_case(sample(case_no), policy_version=policy_version)


def unwrap(leaf):
    """One brief leaf's value, with its wrapper taken off.

    A brief wraps every scalar a clause supplies or a record fixes, so a reading
    is read as ``{"value": ..., "policy_id": ..., "clause_id": ...}``; a leaf that
    carries no wrapper is returned as it stands.
    """
    return leaf["value"] if isinstance(leaf, dict) and "value" in leaf else leaf


def authority_of(brief_object, key):
    """One ``case.authority`` reading of a built brief, unwrapped."""
    return unwrap(brief_object["case"]["authority"][key])


def trip_block(brief_object, key):
    """One block of the trip record's version-7 derived facts, every leaf unwrapped."""
    for artifact in brief_object["case"]["evidence"]:
        if artifact.get("evidence_type") != TRIP_RECORD_TYPE:
            continue
        block = (artifact.get("payload") or {}).get("derived", {}).get("v7", {})[key]
        return {name: unwrap(value) for name, value in block.items()}
    raise AssertionError("the brief carries no trip record")


class TheTwoKilometreLimbReachesTheBriefTests(unittest.TestCase):
    """902's authority block, at version 8 and at version 7."""

    def test_version_eight_reads_the_limb_as_applied(self):
        brief_object = built(ROUTE_DEVIATION_SAMPLE, VERSION_EIGHT)
        self.assertIs(True, authority_of(brief_object, "ai_limit_applied"))
        self.assertIs(True, authority_of(brief_object, "over_ai_limit"))

    def test_version_seven_still_reads_the_limb_as_held(self):
        brief_object = built(ROUTE_DEVIATION_SAMPLE, VERSION_SEVEN)
        self.assertIs(False, authority_of(brief_object, "ai_limit_applied"))
        self.assertIs(True, authority_of(brief_object, "over_ai_limit"))

    def test_both_readings_name_the_clause_they_rest_on(self):
        authority = built(ROUTE_DEVIATION_SAMPLE, VERSION_EIGHT)["case"]["authority"]
        self.assertEqual("POL-RD-25", authority["ai_limit_applied"]["clause_id"])
        self.assertEqual("POL-RD-25", authority["over_ai_limit"]["clause_id"])

    def test_the_ceiling_the_brief_was_built_against_is_the_version_eight_policys(self):
        thresholds = built(ROUTE_DEVIATION_SAMPLE, VERSION_EIGHT)["policies"]["category"][
            "thresholds"
        ]
        self.assertEqual(Decimal("2.0"), Decimal(str(thresholds["ai_ruling_max_deviation_km"])))
        self.assertIs(True, thresholds["ai_ruling_max_deviation_applied"])

    def test_the_version_eight_brief_is_briefed_from_policy_v8(self):
        self.assertEqual(
            "8.0.0",
            built(ROUTE_DEVIATION_SAMPLE, VERSION_EIGHT)["policies"]["category"]["version"],
        )
        self.assertEqual(
            "7.0.0",
            built(ROUTE_DEVIATION_SAMPLE, VERSION_SEVEN)["policies"]["category"]["version"],
        )

    def test_the_deviation_itself_is_the_same_reading_at_both_versions(self):
        """Only the switch moved: 4.3 km is over 2.0 km either way."""
        for version in (VERSION_SEVEN, VERSION_EIGHT):
            with self.subTest(version=version):
                block = trip_block(built(ROUTE_DEVIATION_SAMPLE, version), "deviation")
                self.assertEqual(Decimal("4.3"), Decimal(str(block["deviation_km"])))
                self.assertIs(True, block["over_ai_limit"])


class TheFreeWaitStartsAtTheArrivalTests(unittest.TestCase):
    """903's free wait, at version 8 and at version 7."""

    def test_version_eight_starts_the_clock_at_the_drivers_arrival(self):
        block = trip_block(built(NO_SHOW_SAMPLE, VERSION_EIGHT), "free_wait")
        self.assertEqual(ARRIVED_AT, block["starts_at"])
        self.assertEqual(facts.FREE_WAIT_FROM_ARRIVAL, block["starts_from"])
        self.assertEqual(V8_ENDS_AT, block["ends_at"])
        self.assertIs(True, block["cancelled_after_free_wait"])

    def test_version_seven_still_starts_it_at_the_scheduled_time(self):
        block = trip_block(built(NO_SHOW_SAMPLE, VERSION_SEVEN), "free_wait")
        self.assertEqual(SCHEDULED_AT, block["starts_at"])
        self.assertEqual(facts.FREE_WAIT_FROM_SCHEDULE, block["starts_from"])
        self.assertEqual(V7_ENDS_AT, block["ends_at"])
        self.assertIs(True, block["cancelled_after_free_wait"])

    def test_the_driver_did_arrive_before_the_scheduled_time(self):
        """Which is what makes the two versions differ at all."""
        block = trip_block(built(NO_SHOW_SAMPLE, VERSION_EIGHT), "free_wait")
        self.assertEqual(ARRIVED_AT, block["arrived_at"])
        self.assertEqual(SCHEDULED_AT, block["scheduled_at"])
        self.assertEqual(300, block["free_wait_sec"])

    def test_the_field_the_reading_comes_from_is_the_version_eight_policys(self):
        eight = loader.load_policies("NO_SHOW_CHARGE", VERSION_EIGHT)["category"]["thresholds"]
        seven = loader.load_policies("NO_SHOW_CHARGE", VERSION_SEVEN)["category"]["thresholds"]
        self.assertEqual("arrived_at", eight["free_wait_starts_from"])
        self.assertNotIn("free_wait_starts_from", seven)

    def test_the_free_wait_moves_no_answer(self):
        """Both versions find the cancellation after the wait, so 903 keeps its ruling."""
        for version in (VERSION_SEVEN, VERSION_EIGHT):
            with self.subTest(version=version):
                block = trip_block(built(NO_SHOW_SAMPLE, version), "free_wait")
                self.assertIs(True, block["cancelled_after_free_wait"])


class TheFreeWaitKeywordTests(unittest.TestCase):
    """``facts.free_wait``'s own ``starts_from``, on the policy's two values."""

    def test_from_the_arrival_overrules_an_early_arrival(self):
        reading = facts.free_wait(
            ARRIVED_AT,
            SCHEDULED_AT,
            300,
            "2026-09-13T08:51:00+08:00",
            starts_from=facts.FREE_WAIT_FROM_ARRIVAL,
        )
        self.assertEqual(ARRIVED_AT, reading["starts_at"])
        self.assertEqual(facts.FREE_WAIT_FROM_ARRIVAL, reading["starts_from"])
        self.assertEqual(V8_ENDS_AT, reading["ends_at"])
        self.assertIs(True, reading["cancelled_after_free_wait"])

    def test_no_value_is_the_reading_it_always_was(self):
        reading = facts.free_wait(ARRIVED_AT, SCHEDULED_AT, 300, "2026-09-13T08:51:00+08:00")
        self.assertEqual(SCHEDULED_AT, reading["starts_at"])
        self.assertEqual(facts.FREE_WAIT_FROM_SCHEDULE, reading["starts_from"])
        self.assertEqual(V7_ENDS_AT, reading["ends_at"])

    def test_the_two_readings_agree_on_a_late_arrival(self):
        """Where the driver arrived after the schedule, both start at the arrival."""
        for starts_from in (None, facts.FREE_WAIT_FROM_ARRIVAL):
            with self.subTest(starts_from=starts_from):
                reading = facts.free_wait(
                    "2026-09-13T08:47:00+08:00",
                    SCHEDULED_AT,
                    300,
                    "2026-09-13T08:52:00+08:00",
                    starts_from=starts_from,
                )
                self.assertEqual("2026-09-13T08:47:00+08:00", reading["starts_at"])
                self.assertEqual(facts.FREE_WAIT_FROM_ARRIVAL, reading["starts_from"])

    def test_an_unknown_value_is_refused_and_the_field_is_named(self):
        for value in (facts.FREE_WAIT_FROM_SCHEDULE, "scheduled", "", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    facts.free_wait(ARRIVED_AT, SCHEDULED_AT, 300, None, starts_from=value)
                self.assertIn("free_wait_starts_from", str(raised.exception))


class ThePipelineGateReadsTheVersionEightBriefTests(unittest.TestCase):
    """The gate the pipeline already had, on the brief version 8 produces.

    Nothing in ``tribunal/pipeline.py`` changed for version 8: its version-7 gate
    reads ``case.authority.ai_limit_applied`` and ``over_ai_limit`` and cites
    POL-RD-25, so a policy that applies the limb is escalated before the judge is
    asked. The gate function is called directly, so no model is reached and no
    client is built.
    """

    def test_the_gate_escalates_on_the_version_eight_brief(self):
        case = sample(ROUTE_DEVIATION_SAMPLE)
        gate = pipeline.authority_gate(case, built(ROUTE_DEVIATION_SAMPLE, VERSION_EIGHT))
        self.assertIsNotNone(gate)
        self.assertEqual(pipeline.V7_AI_LIMIT, gate["reason_code"])
        self.assertEqual(pipeline.V7_AI_LIMIT_CLAUSE, gate["clause"])
        self.assertIn(pipeline.V7_AI_LIMIT_CLAUSE, gate["basis"])
        self.assertEqual([], gate["flags"])

    def test_the_gate_returns_nothing_on_the_version_seven_brief(self):
        case = sample(ROUTE_DEVIATION_SAMPLE)
        self.assertIsNone(
            pipeline.authority_gate(case, built(ROUTE_DEVIATION_SAMPLE, VERSION_SEVEN))
        )

    def test_the_gate_names_the_clause_the_policy_does(self):
        self.assertEqual("POL-RD-25", pipeline.V7_AI_LIMIT_CLAUSE)
        self.assertEqual("POL-RD-25", loader.load_policies(
            "ROUTE_DEVIATION", VERSION_EIGHT
        )["category"]["clauses"][-1]["id"])

    def test_the_gate_publishes_an_escalation_with_no_money(self):
        case = sample(ROUTE_DEVIATION_SAMPLE)
        gate = pipeline.authority_gate(case, built(ROUTE_DEVIATION_SAMPLE, VERSION_EIGHT))
        ruling = pipeline.authority_gate_ruling(gate)["ruling"]
        self.assertEqual(pipeline.ESCALATE, ruling["ruling"])
        self.assertIsNone(ruling["amount_sgd"])
        self.assertIsNone(ruling["driver_compensation_sgd"])
        self.assertEqual([], ruling["referrals"])


class TheControlTests(unittest.TestCase):
    """The switch is what decides the reading, not the code.

    A guard nobody has seen fail is not evidence of anything, so the same
    assertion the first class makes is made again over a **temporary copy** of
    ``policy/v8/`` with ``thresholds.ai_ruling_max_deviation_applied`` put back to
    false -- which is exactly what version 7 states. The version-8 brief built
    against that copy reads the limb as held, so the first class's assertion is
    shown to be capable of failing, and the gate that follows it returns nothing.
    """

    def flipped_policy_root(self, temporary):
        """A policy root whose ``v8/`` is version 8's with the one field flipped."""
        root = Path(temporary) / "policy"
        (root / "v8").mkdir(parents=True)
        for name in POLICY_FILES:
            shutil.copyfile(PROJECT_ROOT / "policy" / "v8" / name, root / "v8" / name)
        path = root / "v8" / "route_deviation.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        node: Any = document
        for step in APPLIED_PATH[:-1]:
            node = node[step]
        node[APPLIED_PATH[-1]] = False
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return root

    def test_with_the_switch_put_back_the_version_eight_reading_is_version_sevens(self):
        case = sample(ROUTE_DEVIATION_SAMPLE)
        with tempfile.TemporaryDirectory() as temporary:
            root = self.flipped_policy_root(temporary)
            with mock.patch.object(policy_versions, "POLICY_DIR", root):
                brief_object = brief.build_brief_for_case(case, policy_version=VERSION_EIGHT)
                self.assertIs(False, authority_of(brief_object, "ai_limit_applied"))
                self.assertIs(True, authority_of(brief_object, "over_ai_limit"))
                self.assertIsNone(pipeline.authority_gate(case, brief_object))

    def test_the_temporary_copy_is_only_the_one_field(self):
        """The control would be vacuous if it moved anything else."""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.flipped_policy_root(temporary)
            original = json.loads(
                (PROJECT_ROOT / "policy" / "v8" / "route_deviation.json").read_text(
                    encoding="utf-8"
                )
            )
            flipped = json.loads((root / "v8" / "route_deviation.json").read_text(encoding="utf-8"))
            self.assertIs(True, original["thresholds"][APPLIED_KEY])
            self.assertIs(False, flipped["thresholds"][APPLIED_KEY])
            original["thresholds"][APPLIED_KEY] = False
            self.assertEqual(original, flipped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
