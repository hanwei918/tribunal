"""``ryde-v7``: the organisers' two samples, converted for policy version 7.

Policy version 7 is Ryde's own Dispute Resolution Policy v2.1. The organisers
supplied three samples and only two of them can be carried: DISP-001, a route
deviation, becomes case 902 and DISP-002, a no-show, becomes case 903, and
DISP-003, a fare dispute, is not converted at all because this repository's case
format carries no ``FARE_DISPUTE`` category for it to declare -- which is also
what POL-GEN-24 says about it, since v2.1 routes a fare dispute to a person
rather than adjudicating it.

This module holds the set to the four things the conversion is for:

* the two cases load through the set's own index, and each one is **answer-free**
  under the same control the corpus is held to;
* both version-7 briefs build, and each carries the facts its policy reads: 902's
  money block publishes the excess distance fare POL-RD-24 computes (3.44) and
  its authority block puts it in POL-GEN-22's first band, and 903's free wait
  runs from the scheduled time to 08:50 with POL-NS-23's contact obligation met;
* the registration is a **declaration** for the two sets whose data is not here
  yet, and a registration for the one whose data is;
* the version and the prompt set are one pair, refused in both directions.

No model call is made. Run from the project root with::

    python -m unittest tests.test_ryde_v7 -v
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets as sets  # noqa: E402
from eval import run_benchmark as runner  # noqa: E402
from tests import test_answer_isolation as isolation  # noqa: E402
from tribunal import brief, loader, pipeline  # noqa: E402

VERSION_SEVEN = 7
VERSION_SIX = 6

# The runtime model, so a command-line test names a real one.
MODEL = "deepseek/deepseek-flash"

SET_NAME = "ryde-v7"
SET_ROOT = loader.EXTERNAL_DIR / SET_NAME
KEY_PATH = PROJECT_ROOT / "eval" / "answers" / SET_NAME / "ground_truth.json"

# The two cases, by the document they came from.
ROUTE_DEVIATION_CASE = 902
NO_SHOW_CASE = 903

# The declarations parts 73 and 74 will register.
DECLARED_NAMES = ("dev-v7", "sealed-v4")


def case(case_no: int) -> Mapping[str, Any]:
    return loader.load_external_set_case(SET_ROOT, case_no)


def version_seven_brief(case_no: int) -> Dict[str, Any]:
    return brief.build_brief_for_case(case(case_no), policy_version=VERSION_SEVEN)


def v7_blocks(brief_object: Mapping[str, Any], evidence_type: str) -> List[Dict[str, Any]]:
    """Every ``derived.v7`` block on the artifacts of one evidence type."""
    found = []
    for artifact in brief_object["case"]["evidence"]:
        if artifact["evidence_type"] != evidence_type:
            continue
        payload = artifact.get("payload")
        derived = payload.get(brief.DERIVED_KEY) if isinstance(payload, Mapping) else None
        if isinstance(derived, Mapping) and brief.V7_KEY in derived:
            found.append(derived[brief.V7_KEY])
    return found


def leaf(block: Mapping[str, Any], *path: str) -> Any:
    """One wrapped leaf's value, following a path of keys."""
    node: Any = block
    for key in path:
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    return node.get("value") if isinstance(node, Mapping) else node


# --------------------------------------------------------------------------
# The set
# --------------------------------------------------------------------------
class TheSetTests(unittest.TestCase):
    """Two cases, loaded by number through the set's own index."""

    def test_it_loads_two_of_two(self):
        registered = sets.RYDE_V7
        self.assertEqual((ROUTE_DEVIATION_CASE, NO_SHOW_CASE), tuple(registered.cases))
        for case_no in registered.cases:
            with self.subTest(case=case_no):
                loaded = registered.load_case(case_no)
                self.assertEqual(case_no, loaded["case_no"])

    def test_the_index_holds_the_two_cases_and_their_digests(self):
        entries = loader.load_external_index(SET_ROOT)
        self.assertEqual(
            [ROUTE_DEVIATION_CASE, NO_SHOW_CASE],
            sorted(entry["case_no"] for entry in entries),
        )
        for entry in entries:
            with self.subTest(case=entry["case_no"]):
                self.assertEqual(
                    "case-{0:05d}.json".format(entry["case_no"]), entry["file"]
                )
                self.assertTrue(entry["sha256"])

    def test_the_two_categories_are_the_two_the_schema_carries(self):
        self.assertEqual("ROUTE_DEVIATION", case(ROUTE_DEVIATION_CASE)["dispute"]["category"])
        self.assertEqual("NO_SHOW_CHARGE", case(NO_SHOW_CASE)["dispute"]["category"])

    def test_each_case_is_answer_free(self):
        """The same control the corpus is held to, over this set's two cases."""
        for case_no in (ROUTE_DEVIATION_CASE, NO_SHOW_CASE):
            with self.subTest(case=case_no):
                self.assertEqual(
                    {}, isolation._brief_violations_for_case(case(case_no), VERSION_SEVEN)
                )

    def test_the_set_carries_no_third_case(self):
        """DISP-003 is not converted: there is no category for it to declare."""
        files = sorted(path.name for path in SET_ROOT.glob("case-*.json"))
        self.assertEqual(["case-00902.json", "case-00903.json"], files)


# --------------------------------------------------------------------------
# The briefs
# --------------------------------------------------------------------------
class TheBriefTests(unittest.TestCase):
    """Both version-7 briefs build, and each carries what its policy reads."""

    def test_both_version_seven_briefs_build(self):
        for case_no in (ROUTE_DEVIATION_CASE, NO_SHOW_CASE):
            with self.subTest(case=case_no):
                built = version_seven_brief(case_no)
                self.assertIn("authority", built["case"])
                self.assertTrue(built["policies"]["general"]["clauses"])

    def test_902_money_block_publishes_the_excess_distance_fare(self):
        block = pipeline.money_block(version_seven_brief(ROUTE_DEVIATION_CASE))
        self.assertTrue(block["available"])
        self.assertEqual(Decimal("3.44"), Decimal(str(block["excess_distance_fare_sgd"]["value"])))
        figures = [
            (path, amount)
            for path, amount in pipeline.published_money_figures(block)
        ]
        self.assertEqual([("excess_distance_fare_sgd.value", Decimal("3.44"))], figures)

    def test_902_rate_and_deviation_are_not_published_as_amounts(self):
        """The two context figures POL-RD-24 multiplies together are excluded."""
        block = pipeline.money_block(version_seven_brief(ROUTE_DEVIATION_CASE))
        names = {
            pipeline._figure_name(path)
            for path, _amount in pipeline.published_money_figures(block)
        }
        self.assertNotIn("per_km_rate_sgd", names)
        self.assertNotIn("deviation_km", names)

    def test_902_value_band_is_ai_final(self):
        authority = version_seven_brief(ROUTE_DEVIATION_CASE)["case"]["authority"]
        self.assertEqual(Decimal("6.50"), Decimal(str(authority["dispute_value_sgd"]["value"])))
        self.assertEqual(brief.VALUE_BAND_AI_FINAL, authority["value_band"]["value"])
        self.assertEqual(Decimal("0.80"), Decimal(str(authority["required_confidence"]["value"])))
        self.assertEqual("POL-RD-25", authority["required_confidence"]["clause_id"])
        self.assertIs(False, authority["human_only"]["value"])

    def test_902_deviation_is_the_two_recorded_distances(self):
        blocks = v7_blocks(version_seven_brief(ROUTE_DEVIATION_CASE), "TRIP_RECORD")
        self.assertEqual(1, len(blocks))
        deviation = blocks[0]["deviation"]
        self.assertTrue(deviation["available"])
        self.assertEqual(Decimal("24.8"), Decimal(str(deviation["actual_distance_km"]["value"])))
        self.assertEqual(Decimal("20.5"), Decimal(str(deviation["optimal_distance_km"]["value"])))
        self.assertEqual(Decimal("4.30"), Decimal(str(deviation["deviation_km"]["value"])))
        self.assertIs(False, deviation["within_tolerance"]["value"])

    def test_902_advisories_intersect_the_recommended_route_or_do_not(self):
        blocks = v7_blocks(version_seven_brief(ROUTE_DEVIATION_CASE), "TRAFFIC_ADVISORY")
        self.assertEqual(3, len(blocks))
        readings = {block["type"]["value"]: block["intersects_route"]["value"] for block in blocks}
        self.assertEqual(
            {"VEHICLE_FIRE": True, "HEAVY_CONGESTION": True, "TRAFFIC_FLOW": False},
            readings,
        )

    def test_903_free_wait_starts_at_the_schedule_and_ends_at_0850(self):
        blocks = v7_blocks(version_seven_brief(NO_SHOW_CASE), "TRIP_RECORD")
        self.assertEqual(1, len(blocks))
        free_wait = blocks[0]["free_wait"]
        self.assertEqual(
            "2026-09-13T08:45:00+08:00", free_wait["starts_at"]["value"]
        )
        self.assertEqual("2026-09-13T08:50:00+08:00", free_wait["ends_at"]["value"])
        self.assertEqual("scheduled_at", free_wait["starts_from"]["value"])
        self.assertIs(True, free_wait["cancelled_after_free_wait"]["value"])

    def test_903_contact_obligation_is_met_with_four_messages_and_one_call(self):
        blocks = v7_blocks(version_seven_brief(NO_SHOW_CASE), "TRIP_RECORD")
        contact = blocks[0]["contact_before_cancel"]
        self.assertEqual(4, contact["message_count"]["value"])
        self.assertEqual(1, contact["call_count"]["value"])
        self.assertIs(True, contact["obligation_met"]["value"])
        self.assertIs(True, contact["complete"]["value"])
        for message in contact["messages"]:
            self.assertLess(message["sent_at"], "2026-09-13T08:51:00+08:00")
        for call in contact["calls"]:
            self.assertLess(call["placed_at"], "2026-09-13T08:51:00+08:00")

    def test_903_fraud_flag_raises_the_bar_to_ninety_five(self):
        authority = version_seven_brief(NO_SHOW_CASE)["case"]["authority"]
        self.assertEqual(1, authority["fraud_flags"]["value"])
        self.assertEqual(Decimal("0.95"), Decimal(str(authority["required_confidence"]["value"])))
        self.assertEqual("POL-GEN-22", authority["required_confidence"]["clause_id"])

    def test_903_money_block_publishes_the_fee_and_what_turns_on_it(self):
        block = pipeline.money_block(version_seven_brief(NO_SHOW_CASE))
        self.assertEqual(Decimal("5.00"), Decimal(str(block["fee_charged_sgd"]["value"])))
        self.assertEqual(Decimal("5.00"), Decimal(str(block["driver_compensation_if_upheld_sgd"]["value"])))
        self.assertIs(True, block["fee_matches_policy"]["value"])


# --------------------------------------------------------------------------
# The key
# --------------------------------------------------------------------------
class TheKeyTests(unittest.TestCase):
    """Ryde's own outcomes, in this repository's fields."""

    def setUp(self):
        self.key = runner.grade.load_answer_key(KEY_PATH)

    def test_it_holds_the_two_cases(self):
        self.assertEqual([ROUTE_DEVIATION_CASE, NO_SHOW_CASE], sorted(self.key))

    def test_902_is_a_partial_refund_of_the_excess_distance_fare(self):
        expected = self.key[ROUTE_DEVIATION_CASE]
        self.assertEqual("PARTIAL_REFUND", expected.ruling)
        self.assertEqual(Decimal("3.44"), expected.amount_sgd)
        self.assertIsNone(expected.driver_compensation_sgd)
        self.assertEqual((), expected.referrals)

    def test_903_is_the_driver_s_compensation_at_the_fee(self):
        expected = self.key[NO_SHOW_CASE]
        self.assertEqual("DRIVER_COMPENSATION", expected.ruling)
        self.assertEqual(Decimal("5.00"), expected.amount_sgd)
        self.assertEqual(Decimal("5.00"), expected.driver_compensation_sgd)
        self.assertEqual((), expected.referrals)

    def test_every_record_names_its_sample_and_its_rationale(self):
        records = json.loads(KEY_PATH.read_text(encoding="utf-8"))
        for record in records:
            with self.subTest(case=record["case_no"]):
                self.assertIn("DISP-00", record["ground_truth"]["rationale"])
                self.assertIn("v2.1", record["ground_truth"]["rationale"])

    def test_the_key_is_not_the_corpus_key(self):
        corpus = runner.grade.load_answer_key()
        self.assertEqual(
            [], sorted(set(self.key) & set(corpus)), "a case number is in both keys"
        )


# --------------------------------------------------------------------------
# The registration
# --------------------------------------------------------------------------
class TheRegistrationTests(unittest.TestCase):
    """One set registered, two declared, and none of them a development set."""

    def test_ryde_v7_is_registered_as_a_development_set(self):
        registered = sets.BY_NAME[SET_NAME]
        self.assertIs(sets.RYDE_V7, registered)
        self.assertFalse(registered.sealed, "the samples are not a sealed set")
        self.assertEqual(SET_NAME, registered.runs_subdir)
        self.assertEqual(SET_ROOT, registered.case_root)
        self.assertEqual(KEY_PATH, registered.key_path)

    def test_it_fixes_policy_version_seven(self):
        registered = sets.RYDE_V7
        self.assertEqual(VERSION_SEVEN, registered.policy_version)
        self.assertEqual(VERSION_SEVEN, registered.policy_base)
        self.assertEqual(VERSION_SEVEN, sets.resolved_policy_version(registered, None))

    def test_it_is_not_a_development_set_and_not_in_all_sets(self):
        self.assertEqual(
            ["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS]
        )
        self.assertNotIn(SET_NAME, [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn(SET_NAME, [item.name for item in sets.ALL_SETS])
        self.assertNotIn(SET_NAME, [item.name for item in sets.SEALED_SETS])
        self.assertIn(SET_NAME, [item.name for item in sets.NAMED_SETS])

    def test_the_name_table_is_exactly_the_registered_sets(self):
        self.assertEqual(
            {
                item.name
                for item in (
                    sets.DEVELOPMENT_SETS
                    + sets.SEALED_SETS
                    + sets.RERUN_SETS
                    + sets.NAMED_SETS
                )
            },
            set(sets.BY_NAME),
            "the name table is not exactly the registered sets",
        )

    def test_the_two_future_sets_are_declared_and_not_registered(self):
        for name in DECLARED_NAMES:
            with self.subTest(set=name):
                self.assertIn(name, sets.DECLARED_SETS)
                self.assertNotIn(name, sets.BY_NAME)
                self.assertFalse(
                    (loader.EXTERNAL_DIR / name).exists(),
                    "a declared set has data, so it should be registered",
                )

    def test_each_declared_set_fixes_version_seven_and_prompts_v2(self):
        for name in DECLARED_NAMES:
            declared = sets.DECLARED_SETS[name]
            with self.subTest(set=name):
                self.assertEqual(VERSION_SEVEN, declared.policy_version)
                self.assertIsNotNone(declared.run_arguments)
                self.assertEqual(
                    Path("prompts/v2"), declared.run_arguments.prompts_dir
                )

    def test_the_declared_sealed_set_is_marked_sealed(self):
        self.assertTrue(sets.DECLARED_SETS["sealed-v4"].sealed)
        self.assertFalse(sets.DECLARED_SETS["dev-v7"].sealed)

    def test_the_run_arguments_are_sealed_v2_s(self):
        frozen = sets.SEALED_V2.run_arguments
        for name in DECLARED_NAMES:
            declared = sets.DECLARED_SETS[name].run_arguments
            with self.subTest(set=name):
                self.assertEqual(frozen.model, declared.model)
                self.assertEqual(frozen.judge_votes, declared.judge_votes)
                self.assertEqual(frozen.verify_drafts, declared.verify_drafts)
                self.assertEqual(frozen.timeout_seconds, declared.timeout_seconds)
                self.assertEqual(frozen.concurrency, declared.concurrency)
                self.assertEqual(Path("prompts/v2"), declared.prompts_dir)

    def test_no_folder_was_created_for_a_declared_set(self):
        for name in DECLARED_NAMES:
            with self.subTest(set=name):
                self.assertFalse((loader.EXTERNAL_DIR / name).exists())


class TheCheckTests(unittest.TestCase):
    """``--check`` on a declared set says its data is not there yet."""

    def check(self, name: str) -> str:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                code = sets.main(["--set", name, "--check"])
        self.assertEqual(1, code)
        self.assertEqual("", out.getvalue())
        return errors.getvalue()

    def test_check_for_sealed_v4_before_its_data_exists(self):
        message = self.check("sealed-v4")
        self.assertIn("sealed-v4", message)
        self.assertIn("declared but not registered", message)
        self.assertIn("index.json", message)

    def test_check_for_dev_v7_before_its_data_exists(self):
        message = self.check("dev-v7")
        self.assertIn("dev-v7", message)
        self.assertIn("declared but not registered", message)

    def test_naming_a_declared_set_raises_rather_than_defaulting(self):
        with self.assertRaises(runner.BenchmarkError) as caught:
            sets.named("sealed-v4")
        self.assertIn("declared but not registered", str(caught.exception))


# --------------------------------------------------------------------------
# The prompts guard
# --------------------------------------------------------------------------
class ThePromptsGuardTests(unittest.TestCase):
    """The version and the prompt set are one pair."""

    def refuse(self, arguments) -> str:
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    runner.main(arguments)
        return errors.getvalue()

    def test_version_seven_with_the_version_six_prompts_is_refused(self):
        message = self.refuse(
            ["--model", MODEL, "--cases", "101", "--policy-version", "7"]
        )
        self.assertIn("prompts/v1", message)
        self.assertIn("prompts/v2", message)
        self.assertIn("7", message)

    def test_version_six_with_the_version_seven_prompts_is_refused(self):
        message = self.refuse(
            [
                "--model",
                MODEL,
                "--cases",
                "101",
                "--policy-version",
                "6",
                "--prompts-dir",
                "prompts/v2",
            ]
        )
        self.assertIn("prompts/v1", message)
        self.assertIn("prompts/v2", message)

    def test_the_pair_that_matches_is_not_refused_for_the_pair(self):
        """Version 6 with version-6 prompts gets past the guard.

        The client factory is what stops the invocation here, and it raises a
        plain ``Exception`` rather than a ``SystemExit``: a refusal by the guard
        would be the latter and would escape this test rather than pass it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner,
                "_default_client_factory",
                side_effect=AssertionError("a client was built"),
            ):
                with contextlib.redirect_stderr(io.StringIO()) as errors:
                    with self.assertRaises(Exception) as caught:
                        runner.main(
                            [
                                "--model",
                                MODEL,
                                "--cases",
                                "101",
                                "--policy-version",
                                "6",
                                "--runs-dir",
                                str(Path(tmp) / "runs"),
                            ]
                        )
        self.assertNotIsInstance(caught.exception, SystemExit)
        self.assertNotIn("prompt set states the clause ids", errors.getvalue())

    def test_the_helper_names_both_directories(self):
        mismatch = runner.mismatched_prompts_directory(
            VERSION_SEVEN, runner.PROMPTS_DIR
        )
        self.assertIsNotNone(mismatch)
        self.assertIn(str(runner.V7_PROMPTS_DIR), mismatch)
        self.assertIn(str(runner.PROMPTS_DIR), mismatch)
        self.assertIsNone(
            runner.mismatched_prompts_directory(VERSION_SEVEN, runner.V7_PROMPTS_DIR)
        )
        self.assertIsNone(
            runner.mismatched_prompts_directory(VERSION_SIX, runner.PROMPTS_DIR)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
