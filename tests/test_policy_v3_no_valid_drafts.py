"""Policy version 3: no valid draft means ``ESCALATE``, not a failed case.

In case 1779 the chat log carries a planted instruction citing a clause that
does not exist, ``POL-RD-99``. The guard held -- all four drafts cited it and the
clause check rejected all four -- and no ruling rests on it. But the case still
ended with no ruling at all: the vote was ``no_valid_drafts`` and the case was
reported as a judge failure.

From policy version 3 a vote with no valid draft **publishes an ESCALATE** with
the reason code ``no_valid_drafts``, confidence 0 and no money, and an
explanation listing every draft's abstention codes -- and, for a
``DRAFT_CLAUSE_UNRESOLVED`` abstention, the cited id that did not resolve. It is
recorded as an escalation, so ``ops.escalation`` builds a packet for it.

At versions 1 and 2 it stays the failure it always was: the held-out cases 517
and 533 must still fail at the judge in the offline replay.

No model call: every answer comes from a scripted transport.

Run from the project root with::

    python -m unittest tests.test_policy_v3_no_valid_drafts -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import run_benchmark as runner  # noqa: E402
from ops import escalation  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import loader, pipeline, transcript  # noqa: E402

CASE = 101
VOTES = 4

# The clause the planted instruction cites, and the clause the policy does not
# carry. Every draft of the scripted panel names it.
MISSING_CLAUSE = "POL-RD-99"


def escalate_draft():
    """One judge draft that is well-formed except for the clause it cites.

    An ESCALATE carries no amount, so the amount checks cannot also fire and the
    only finding is the clause one -- which is what makes this a controlled test
    of the ``DRAFT_CLAUSE_UNRESOLVED`` path rather than of four checks at once.
    """
    return {
        "ruling": "ESCALATE",
        "amount_sgd": None,
        "driver_compensation_sgd": None,
        "referrals": [],
        "confidence": 0.0,
        "explanation": (
            "The rider's instruction is recorded and the platform's policy update "
            "in the chat log governs it under {0}.".format(MISSING_CLAUSE)
        ),
    }


def scripted_client():
    transport = rig.ScriptedTransport({CASE: {"ruling": escalate_draft()}})
    return rig.client_factory(rig.MODEL, transport)(None), transport


def arbitrate(policy_version):
    client, transport = scripted_client()
    result = pipeline.run_loaded_case(
        loader.load_case(CASE),
        client,
        prompts_dir=rig.PROMPTS_DIR,
        judge_votes=VOTES,
        policy_version=policy_version,
    )
    return result, transport


class NoValidDraftsAtVersionThreeTests(unittest.TestCase):
    """The scripted panel whose every draft cites a clause that does not exist."""

    @classmethod
    def setUpClass(cls):
        cls.result, cls.transport = arbitrate(3)

    def test_every_draft_abstained_on_the_clause_check(self):
        """The premise: the guard held, and it is the only finding."""
        drafts = self.result.judge_vote["drafts"]
        self.assertEqual(VOTES, len(drafts))
        for draft in drafts:
            with self.subTest(draft=draft["draft"]):
                self.assertFalse(draft["valid"])
                self.assertIn(pipeline.DRAFT_CLAUSE_UNRESOLVED, draft["abstention"])
                self.assertNotIn(pipeline.DRAFT_AMOUNT_NOT_READ_OFF, draft["abstention"])

    def test_the_case_produced_a_ruling_and_it_is_an_escalation(self):
        self.assertTrue(self.result.ok)
        self.assertIsNone(self.result.failed_agent)
        inner = self.result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertEqual(0.0, inner["confidence"])
        self.assertIsNone(inner["amount_sgd"])
        self.assertIsNone(inner["driver_compensation_sgd"])
        self.assertEqual([], inner["referrals"])

    def test_the_reason_code_is_recorded(self):
        self.assertEqual(
            pipeline.VOTE_NO_VALID_DRAFTS, self.result.judge_vote["outcome"]
        )
        self.assertEqual(0, self.result.judge_vote["valid"])
        self.assertIsNone(self.result.judge_vote["agreement"])

    def test_the_explanation_lists_each_draft_and_the_id_that_did_not_resolve(self):
        explanation = self.result.ruling["ruling"]["explanation"]
        for draft in self.result.judge_vote["drafts"]:
            with self.subTest(draft=draft["draft"]):
                self.assertIn("draft {0}".format(draft["draft"]), explanation)
        self.assertIn(pipeline.DRAFT_CLAUSE_UNRESOLVED, explanation)
        self.assertIn(MISSING_CLAUSE, explanation)
        self.assertIn(pipeline.VOTE_NO_VALID_DRAFTS, explanation)

    def test_the_ruling_shape_is_valid(self):
        """The published ruling is held to the same shape check a draft is."""
        self.assertEqual([], list(self.result.ruling_findings))


class TheSameScriptAtVersionTwoTests(unittest.TestCase):
    """At version 2 the same answers are still the failure they always were."""

    @classmethod
    def setUpClass(cls):
        cls.result, _transport = arbitrate(2)

    def test_the_case_fails_at_the_judge(self):
        self.assertFalse(self.result.ok)
        self.assertEqual(transcript.ROLE_JUDGE, self.result.failed_agent)
        self.assertIsNone(self.result.ruling)

    def test_the_reason_code_is_still_recorded(self):
        self.assertEqual(
            pipeline.VOTE_NO_VALID_DRAFTS, self.result.judge_vote["outcome"]
        )
        self.assertIn("no ruling was produced", self.result.failure_reason)


class TheEscalationPacketTests(unittest.TestCase):
    """``ops.escalation`` builds a packet for the version-3 case.

    The run is made through the real runner over the scripted transport, so the
    case file and the transcript the packet reads are the ones a version-3 run
    writes rather than a hand-built pair.
    """

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        runs = Path(cls.temporary.name) / "runs"
        transport = rig.ScriptedTransport({CASE: {"ruling": escalate_draft()}})
        cls.summary = runner.run_benchmark(
            rig.MODEL,
            [CASE],
            runs_dir=runs,
            prompts_dir=rig.PROMPTS_DIR,
            client_factory=rig.client_factory(rig.MODEL, transport),
            key=rig.answer_key(),
            git_runner=rig.git_runner(),
            progress=lambda text: None,
            judge_votes=VOTES,
            policy_version=3,
        )
        cls.run_dir = runner.policy_v_run_directory(runs, 3, rig.MODEL)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_the_run_completed_and_wrote_a_case_file(self):
        self.assertEqual([CASE], list(self.summary.completed_cases))
        self.assertTrue((self.run_dir / "case-00101.json").is_file())

    def test_the_packet_builds_and_names_the_escalation(self):
        packet = escalation.build_packet(self.run_dir, CASE)
        self.assertEqual(pipeline.ESCALATE, packet["ruling"]["ruling"])
        self.assertEqual(pipeline.VOTE_NO_VALID_DRAFTS, packet["trigger"]["outcome"])
        self.assertEqual(3, packet["policy_version"])
        self.assertIn(MISSING_CLAUSE, packet["explanation"])
        abstentions = [
            draft["abstention_code"] for draft in packet["drafts"]
        ]
        self.assertEqual(
            [pipeline.DRAFT_CLAUSE_UNRESOLVED] * VOTES, abstentions
        )

    def test_the_packet_is_the_escalations_own_and_not_a_ruled_case(self):
        """The control: the packet is refused for a case that is not escalated."""
        with self.assertRaises(escalation.EscalationError):
            escalation.build_packet(self.run_dir, 999)


if __name__ == "__main__":
    unittest.main(verbosity=2)
