"""Policy version 3: ``POL-GEN-08(1)`` -- a flagged dispute is never ruled automatically.

``POL-GEN-08(1)`` (version 3 and later) says a dispute carrying
``dispute.safety_flag`` or ``dispute.complaint_flag`` "is never adjudicated
automatically: it is routed to human review under POL-GEN-06 with the record
assembled but no draft ruling issued".

From version 3 the pipeline obeys that clause literally: when either flag is
set it **builds the brief** -- "the record assembled" -- makes **no** advocate,
judge or verifier call, and publishes an ``ESCALATE`` with confidence 0, no
money, the reason code ``GEN08_SCOPE`` and **no referral**, with an explanation
naming the flag and the clause. A ``scope_gate`` event records it, and the case
file shows that no model call was made.

The three flagged development cases are ``dev-v2`` 1735 and ``dev-v2-ext`` 2735
and 2759. The revised keys (bundle rev3) expect ``ESCALATE`` with an empty
referral list for all three.

At versions 1 and 2 the gate never applies: a flagged case is asked of the model
exactly as it always was.

No model call: every answer comes from a scripted transport.

Run from the project root with::

    python -m unittest tests.test_policy_v3_scope_gate -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import run_benchmark as runner  # noqa: E402
from eval import development_sets as sets  # noqa: E402
from ops import escalation, queue  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import events, loader, pipeline  # noqa: E402

VERSION_THREE = 3
VERSION_TWO = 2

# The three flagged development cases, by set root and number.
FLAGGED_CASES = (
    (loader.EXTERNAL_DIR / "dev-v2", 1735),
    (loader.EXTERNAL_DIR / "dev-v2-ext", 2735),
    (loader.EXTERNAL_DIR / "dev-v2-ext", 2759),
)

# The sets whose registration is older than version 3. None of them carries a
# flagged case: the gate is a version-3 behaviour and these sets never reach it.
OLDER_SET_ROOTS = {
    "corpus": PROJECT_ROOT / "data" / "cases",
    "codex": loader.EXTERNAL_DIR / "codex",
    "wild": loader.EXTERNAL_DIR / "wild",
    "wild-v2": loader.EXTERNAL_DIR / "wild-v2",
    "ryde-v3": loader.EXTERNAL_DIR / "ryde-v3",
}


def complaint_fixture(case_no=101):
    """A real corpus case with ``dispute.complaint_flag`` set.

    The flag is the only thing added, so the case is otherwise the case the
    corpus carries and the pipeline briefs it exactly as it always did.
    """
    case = dict(loader.load_case(case_no))
    dispute = dict(case["dispute"])
    dispute["complaint_flag"] = True
    dispute.setdefault("safety_flag", False)
    case["dispute"] = dispute
    return case


def counting_client():
    """A client over a transport that records every request it is handed."""
    transport = rig.ScriptedTransport({})
    return rig.client_factory(rig.MODEL, transport)(None), transport


class TheGateAtVersionThreeTests(unittest.TestCase):
    """Each flagged development case is gated: no call, an ESCALATE, no referral."""

    @classmethod
    def setUpClass(cls):
        cls.runs = {}
        for root, case_no in FLAGGED_CASES:
            case = loader.load_external_set_case(root, case_no)
            client, transport = counting_client()
            result = pipeline.run_loaded_case(
                case,
                client,
                prompts_dir=rig.PROMPTS_DIR,
                judge_votes=4,
                policy_version=VERSION_THREE,
            )
            cls.runs[case_no] = (case, result, transport)

    def test_every_flagged_case_sent_no_request(self):
        for _root, case_no in FLAGGED_CASES:
            with self.subTest(case=case_no):
                _case, _result, transport = self.runs[case_no]
                self.assertEqual(0, transport.calls(), "a request was sent")

    def test_every_flagged_case_produced_an_escalation(self):
        for _root, case_no in FLAGGED_CASES:
            with self.subTest(case=case_no):
                _case, result, _transport = self.runs[case_no]
                self.assertTrue(result.ok)
                self.assertIsNone(result.failed_agent)
                inner = result.ruling["ruling"]
                self.assertEqual(pipeline.ESCALATE, inner["ruling"])
                self.assertEqual(0.0, inner["confidence"])
                self.assertIsNone(inner["amount_sgd"])
                self.assertIsNone(inner["driver_compensation_sgd"])

    def test_every_flagged_case_carries_no_referral(self):
        for _root, case_no in FLAGGED_CASES:
            with self.subTest(case=case_no):
                _case, result, _transport = self.runs[case_no]
                self.assertEqual([], result.ruling["ruling"]["referrals"])

    def test_the_reason_code_and_the_flags_are_recorded(self):
        for _root, case_no in FLAGGED_CASES:
            with self.subTest(case=case_no):
                _case, result, _transport = self.runs[case_no]
                self.assertIsNotNone(result.scope_gate)
                self.assertEqual(pipeline.GEN08_SCOPE, result.scope_gate["reason_code"])
                self.assertEqual(["safety_flag"], result.scope_gate["flags"])
                self.assertEqual(0, result.scope_gate["calls"])

    def test_the_explanation_names_the_flag_and_the_clause(self):
        for _root, case_no in FLAGGED_CASES:
            with self.subTest(case=case_no):
                _case, result, _transport = self.runs[case_no]
                explanation = result.ruling["ruling"]["explanation"]
                self.assertIn("safety_flag", explanation)
                self.assertIn("POL-GEN-08(1)", explanation)
                self.assertIn(pipeline.GEN08_SCOPE, explanation)

    def test_the_ruling_shape_is_valid(self):
        for _root, case_no in FLAGGED_CASES:
            with self.subTest(case=case_no):
                _case, result, _transport = self.runs[case_no]
                self.assertEqual([], list(result.ruling_findings))

    def test_the_transcript_holds_no_call(self):
        for _root, case_no in FLAGGED_CASES:
            with self.subTest(case=case_no):
                _case, result, _transport = self.runs[case_no]
                self.assertEqual(0, len(result.transcript.entries))


class TheComplaintFlagTests(unittest.TestCase):
    """A ``complaint_flag`` fixture: gated at version 3, asked of the model at 2."""

    def test_a_complaint_flag_is_gated_and_named(self):
        case = complaint_fixture()
        client, transport = counting_client()
        result = pipeline.run_loaded_case(
            case,
            client,
            prompts_dir=rig.PROMPTS_DIR,
            judge_votes=4,
            policy_version=VERSION_THREE,
        )
        self.assertEqual(0, transport.calls(), "a request was sent")
        inner = result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertEqual([], inner["referrals"])
        self.assertEqual(["complaint_flag"], result.scope_gate["flags"])
        self.assertIn("complaint_flag", inner["explanation"])
        self.assertIn("POL-GEN-08(1)", inner["explanation"])

    def test_a_complaint_flag_at_version_two_goes_to_the_model(self):
        case = complaint_fixture()
        produced = rig.produced_from_key(rig.answer_key())
        transport = rig.ScriptedTransport(produced)
        client = rig.client_factory(rig.MODEL, transport)(None)
        result = pipeline.run_loaded_case(
            case,
            client,
            prompts_dir=rig.PROMPTS_DIR,
            judge_votes=4,
            policy_version=VERSION_TWO,
        )
        self.assertGreater(transport.calls(), 0, "the gate fired at version 2")
        self.assertIsNone(result.scope_gate)
        self.assertEqual(
            produced[101]["ruling"]["ruling"], result.ruling["ruling"]["ruling"]
        )


class TheEventAndCaseFileTests(unittest.TestCase):
    """The gate is recorded, and the case file shows no call was made."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        runs = Path(cls.temporary.name) / "runs"
        development_set = sets.named("dev-v2")
        case_no = 1735
        transport = rig.ScriptedTransport({})
        cls.summary = runner.run_benchmark(
            rig.MODEL,
            [case_no],
            runs_dir=development_set.runs_dir(runs),
            prompts_dir=rig.PROMPTS_DIR,
            client_factory=rig.client_factory(rig.MODEL, transport),
            key=development_set.key(),
            key_path=development_set.key_path,
            case_loader=development_set.load_case,
            label=development_set.name,
            git_runner=rig.git_runner(),
            progress=lambda text: None,
            judge_votes=4,
            policy_version=VERSION_THREE,
        )
        cls.transport = transport
        cls.run_dir = runner.policy_v_run_directory(
            development_set.runs_dir(runs), VERSION_THREE, rig.MODEL
        )
        cls.case_no = case_no

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_no_request_was_made(self):
        self.assertEqual(0, self.transport.calls())

    def test_the_case_file_shows_no_model_call(self):
        document = json.loads(
            (self.run_dir / "case-{0:05d}.json".format(self.case_no)).read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("scope_gate", document)
        self.assertEqual(0, document["scope_gate"]["calls"])
        self.assertEqual(pipeline.GEN08_SCOPE, document["scope_gate"]["reason_code"])
        self.assertEqual(
            {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
             "cached_tokens": 0},
            {key: document["tokens"][key] for key in (
                "prompt_tokens", "completion_tokens", "reasoning_tokens", "cached_tokens"
            )},
        )

    def test_the_event_log_carries_a_scope_gate_event(self):
        log = self.run_dir / events.EVENTS_FILE
        recorded = [
            event
            for event in events.events_for_case(log, self.case_no)
            if event.get("event") == events.EVENT_SCOPE_GATE
        ]
        self.assertEqual(1, len(recorded))
        self.assertEqual(pipeline.GEN08_SCOPE, recorded[0]["reason_code"])
        self.assertEqual(0, recorded[0]["calls"])
        calls = [
            event
            for event in events.events_for_case(log, self.case_no)
            if event.get("event") == events.EVENT_AGENT_CALL
        ]
        self.assertEqual([], calls)

    def test_the_escalation_packet_builds_and_shows_no_call(self):
        packet = escalation.build_packet(self.run_dir, self.case_no)
        self.assertEqual(pipeline.ESCALATE, packet["ruling"]["ruling"])
        self.assertEqual([], packet["ruling"]["referrals"])
        self.assertEqual(
            [], [row for row in packet["timeline"] if row["event"] == events.EVENT_AGENT_CALL]
        )


class TheQueueRoutesTheFlagsTests(unittest.TestCase):
    """``ops.queue`` routes both flags, whatever the category."""

    def setUp(self):
        self.config = queue.load_config()

    def test_a_safety_flag_is_fast_tracked(self):
        lane, reasons = queue.lane_for(
            queue.Dispute(
                case_no=1735,
                category="NO_SHOW_CHARGE",
                filed_at="2026-07-01T10:00:00+08:00",
                amount_contested_sgd=None,
                ruling="ESCALATE",
                wall_seconds=None,
                risk_tripped=False,
                safety_flag=True,
            ),
            self.config,
        )
        self.assertEqual(queue.LANE_SAFETY, lane)
        self.assertIn(queue.REASON_SAFETY_FLAG, reasons)

    def test_a_complaint_flag_goes_to_human_review(self):
        lane, reasons = queue.lane_for(
            queue.Dispute(
                case_no=101,
                category="ROUTE_DEVIATION",
                filed_at="2026-07-01T10:00:00+08:00",
                amount_contested_sgd=None,
                ruling="ESCALATE",
                wall_seconds=None,
                risk_tripped=False,
                complaint_flag=True,
            ),
            self.config,
        )
        self.assertEqual(queue.LANE_HUMAN, lane)
        self.assertIn(queue.REASON_GEN08_COMPLAINT, reasons)


class TheOlderSetsCarryNeitherFlagTests(unittest.TestCase):
    """Versions 1 and 2 never apply the gate, and their sets carry no flag."""

    def test_no_case_of_an_older_set_carries_either_flag(self):
        for name, root in sorted(OLDER_SET_ROOTS.items()):
            for path in sorted(root.glob("case-*.json")):
                document = json.loads(path.read_text(encoding="utf-8"))
                dispute = document.get("dispute") or {}
                with self.subTest(set=name, case=path.name):
                    self.assertFalse(dispute.get("safety_flag"))
                    self.assertFalse(dispute.get("complaint_flag"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
