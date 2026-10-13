"""The ops layer at policy version 7: v2.1's own signals, and the queue.

Policy version 7 is Ryde's own Dispute Resolution Policy v2.1, a separate base
whose clause ids start at 21. ``ops/risk.py`` read five version-6 sentences
(POL-RD-06, RD-08, NS-07, NS-09) and raised without them, which is a refusal
``ops/queue.py`` inherited: a version-7 run directory could not be routed at
all. This module holds the layer to v2.1:

* **the two signals.** At version 7 the layer reports a fraud flag on either
  party (POL-GEN-22, read off both profiles and reported against ``PAIR``) and a
  rider with three or more no-show cancellations in the trailing thirty days
  (POL-NS-25). The threshold is matched out of the clause's own sentence, as
  every threshold in this layer is, so a sentence that has moved is a refusal.
* **the queue.** ``POL-GEN-05``'s execution hold does not exist at version 7, so
  there is no threshold to read and no case held for release: the human lane is
  the ruling's own ``ESCALATE``, which already covers a value above 50.00 SGD and
  a safety flag.
* **the packet.** ``ops/escalation.build_packet`` reads the run's recorded policy
  version and hands it to the risk layer, so a version-7 packet builds without
  reading a version-6 clause by id.

**Version 6 is unmoved.** The five version-6 sentences are read by the same code
they were read by, ``signals_for``'s version parameter defaults to them, and the
queue's output over a committed version-6 run directory is pinned here by digest.

No model call is made and no test writes under ``runs/``: the version-7 run
directory is built in a temporary root. Run from the project root with::

    python -m unittest tests.test_ops_v7 -v
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import escalation, queue, risk  # noqa: E402
from tribunal import loader  # noqa: E402

VERSION_SEVEN = 7
VERSION_SIX = 6

MODEL_SLUG = "hy4-preview"

# The committed version-6 run this module pins. It is the corpus at policy
# version 6, and its queue output is the output the version-7 work must not
# move. The digest was taken from the command's own output **before** any of
# this part's changes:
#
#     python3 -m ops.queue --run-dir runs/policy-v6/deepseek-deepseek-flash
#
# over everything but the first line, which names the run directory and so
# renders the path the caller happened to pass. The first line is asserted
# separately, against the absolute path this test reads the run from.
VERSION_SIX_RUN = PROJECT_ROOT / "runs" / "policy-v6" / "deepseek-deepseek-flash"
VERSION_SIX_QUEUE_SHA256 = (
    "de549b59a5c3f260c3f32d1b0d1069944fec81b34e3b19a74e7c8add7fdbb1d3"
)

# The two corpus cases the stub run holds: a route deviation inside POL-GEN-22's
# middle band, and one above its second band edge.
AUTO_CASE = 104
ESCALATED_CASE = 105


def stub_case_file(
    case_no: int, value: str, version: int, amount: Optional[str] = None
) -> Dict[str, Any]:
    """One case file, with the fields the queue and the packet read.

    ``amount`` is the ruling's ``amount_sgd``. It is ``None`` for an escalation,
    which carries no amount, and a figure for a refund -- the queue's own
    ``POL-GEN-05`` hold is read off the ruling's monetary effect, so a control
    for the hold needs a ruling that moves money.
    """
    return {
        "schema_version": "1.2.0",
        "case_no": case_no,
        "model": MODEL_SLUG,
        "ruling": {
            "ruling": {
                "ruling": value,
                "amount_sgd": amount,
                "driver_compensation_sgd": None,
                "referrals": [],
                "confidence": 0.0,
                "explanation": "The case was escalated to a human reviewer.",
            },
            "discarded_claims": [],
        },
        "ruling_findings": [],
        "referee": {},
        "configuration": {"policy_version": version},
        "wall_seconds": 12.5,
        "transcript_file": "case-{0:05d}.transcript.json".format(case_no),
    }


def stub_transcript() -> Dict[str, Any]:
    """A transcript with no call in it, which is what a gated case's is."""
    return {"entries": [], "referee": {"ledger": [], "flags": []}, "vote": {}}


# What each stub case is ruled: ``case_no -> (ruling value, amount_sgd)``. The
# version-7 pair escalates the case above POL-GEN-22's second band, which is
# what a version-7 run does with it; the version-6 control rules it on its
# merits, because the hold this module is about is read off the ruling's money.
DEFAULT_RULINGS = {
    AUTO_CASE: ("PARTIAL_REFUND", None),
    ESCALATED_CASE: ("ESCALATE", None),
}


def build_stub_run(
    root: Path,
    version: int = VERSION_SEVEN,
    subdir: str = "policy-v7",
    rulings: Optional[Mapping[int, Any]] = None,
) -> Path:
    """A run directory under a temporary root, in the corpus's own layout.

    ``<root>/runs/<subdir>/<model>/`` is what a corpus run at that version would
    be, and the registry reads it back as the corpus -- the path component after
    ``runs`` is not a registered set's own subdirectory. The cases are the real
    corpus cases, loaded through the manifest as the queue loads them.
    """
    values = dict(DEFAULT_RULINGS if rulings is None else rulings)
    run_dir = Path(root) / "runs" / subdir / MODEL_SLUG
    run_dir.mkdir(parents=True, exist_ok=True)
    for case_no, (value, amount) in sorted(values.items()):
        (run_dir / "case-{0:05d}.json".format(case_no)).write_text(
            json.dumps(stub_case_file(case_no, value, version, amount), indent=2) + "\n",
            encoding="utf-8",
        )
        (run_dir / "case-{0:05d}.transcript.json".format(case_no)).write_text(
            json.dumps(stub_transcript(), indent=2) + "\n", encoding="utf-8"
        )
    return run_dir


def flagged_case(case_no: int = AUTO_CASE) -> Dict[str, Any]:
    """A corpus case whose rider profile carries one fraud flag."""
    case = dict(loader.load_case(case_no))
    evidence = []
    for artifact in case["evidence"]:
        artifact = dict(artifact)
        if artifact.get("evidence_type") == "RIDER_PROFILE":
            payload = dict(artifact.get("payload") or {})
            payload["fraud_flags"] = 1
            artifact["payload"] = payload
        evidence.append(artifact)
    case["evidence"] = evidence
    return case


def repeat_canceller_case(count: int) -> Dict[str, Any]:
    """A corpus no-show case whose rider has ``count`` recent cancellations."""
    case = dict(loader.load_case(201))
    evidence = []
    for artifact in case["evidence"]:
        artifact = dict(artifact)
        if artifact.get("evidence_type") == "RIDER_PROFILE":
            payload = dict(artifact.get("payload") or {})
            payload["no_show_cancellations_30d"] = count
            artifact["payload"] = payload
        evidence.append(artifact)
    case["evidence"] = evidence
    return case


def signals(case: Mapping[str, Any], version: int):
    """The signals one case produces at one policy version."""
    policies = loader.load_policies(case["dispute"]["category"], version)
    return risk.signals_for(case, policies, version)


# --------------------------------------------------------------------------
# The two version-7 signals
# --------------------------------------------------------------------------
class TheVersionSevenSignalTests(unittest.TestCase):
    """v2.1's own tests, read out of the loaded policy."""

    def test_a_route_deviation_reports_the_fraud_test_alone(self):
        found = signals(loader.load_case(AUTO_CASE), VERSION_SEVEN)
        self.assertEqual([risk.V7_FRAUD_CLAUSE], [signal.clause for signal in found])

    def test_a_no_show_reports_both(self):
        found = signals(loader.load_case(201), VERSION_SEVEN)
        self.assertEqual(
            [risk.V7_FRAUD_CLAUSE, risk.V7_REPEAT_NO_SHOW_CLAUSE],
            [signal.clause for signal in found],
        )

    def test_a_fraud_flag_on_either_party_trips_the_fraud_test(self):
        found = signals(flagged_case(), VERSION_SEVEN)
        self.assertEqual(1, len(found))
        self.assertEqual(risk.SIDE_PAIR, found[0].side)
        self.assertTrue(found[0].tripped)

    def test_a_fraud_flag_of_zero_does_not_trip_it(self):
        found = signals(loader.load_case(AUTO_CASE), VERSION_SEVEN)
        self.assertFalse(found[0].tripped)

    def test_three_no_show_cancellations_trip_the_repeat_test(self):
        found = signals(repeat_canceller_case(3), VERSION_SEVEN)
        tripped = [signal for signal in found if signal.tripped]
        self.assertEqual([risk.V7_REPEAT_NO_SHOW_CLAUSE], [s.clause for s in tripped])

    def test_two_no_show_cancellations_do_not(self):
        found = signals(repeat_canceller_case(2), VERSION_SEVEN)
        self.assertEqual([], [signal.clause for signal in found if signal.tripped])

    def test_the_threshold_sentence_is_quoted_from_the_clause(self):
        found = signals(loader.load_case(AUTO_CASE), VERSION_SEVEN)
        self.assertIn("fraud_flags of 1 or more", found[0].threshold)

    def test_a_version_seven_case_is_not_read_with_the_version_six_patterns(self):
        """The control: the version is what makes the reading possible."""
        policies = loader.load_policies("ROUTE_DEVIATION", VERSION_SEVEN)
        with self.assertRaises(risk.RiskPolicyError):
            risk.signals_for(loader.load_case(AUTO_CASE), policies, None)


class TheVersionSixSignalsAreUnmovedTests(unittest.TestCase):
    """The five version-6 sentences are read by the code that read them."""

    def test_a_route_deviation_still_reports_pol_rd_06_and_pol_rd_08(self):
        found = signals(loader.load_case(AUTO_CASE), VERSION_SIX)
        self.assertEqual(
            ["POL-RD-06", "POL-RD-08"], [signal.clause for signal in found]
        )

    def test_a_no_show_still_reports_its_own_three(self):
        found = signals(loader.load_case(201), VERSION_SIX)
        self.assertEqual(
            ["POL-NS-07", "POL-NS-09(c)", "POL-NS-09(d)"],
            [signal.clause for signal in found],
        )

    def test_the_default_version_is_the_version_six_five(self):
        case = loader.load_case(AUTO_CASE)
        policies = loader.load_policies("ROUTE_DEVIATION", VERSION_SIX)
        named = risk.signals_for(case, policies, VERSION_SIX)
        defaulted = risk.signals_for(case, policies)
        self.assertEqual(named, defaulted)

    def test_a_fraud_flag_is_not_read_at_version_six(self):
        """The counter is not one of the five version-6 clauses' own fields."""
        found = signals(flagged_case(), VERSION_SIX)
        self.assertEqual(
            [], [signal.clause for signal in found if signal.tripped]
        )


# --------------------------------------------------------------------------
# The queue
# --------------------------------------------------------------------------
class TheVersionSevenQueueTests(unittest.TestCase):
    """A version-7 run directory routes, and its human lane is the ESCALATE."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.run_dir = build_stub_run(cls.temporary.name)
        cls.config = queue.load_config()
        cls.disputes = queue.disputes_from_run(cls.run_dir)
        cls.entries = queue.build_queue(cls.disputes, cls.config)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def entry_for(self, case_no: int):
        for entry in self.entries:
            if entry.case_no == case_no:
                return entry
        raise AssertionError("case {0} is not in the queue".format(case_no))

    def test_the_run_routes_without_a_refusal(self):
        self.assertEqual([AUTO_CASE, ESCALATED_CASE], sorted(d.case_no for d in self.disputes))

    def test_an_escalated_case_is_in_the_human_lane(self):
        entry = self.entry_for(ESCALATED_CASE)
        self.assertEqual(queue.LANE_HUMAN, entry.lane)
        self.assertIn(queue.REASON_ESCALATED, entry.reasons)

    def test_a_decided_case_is_in_the_auto_lane(self):
        entry = self.entry_for(AUTO_CASE)
        self.assertEqual(queue.LANE_AUTO, entry.lane)
        self.assertEqual((queue.REASON_RULED,), entry.reasons)

    def test_no_case_is_held_for_release_at_version_seven(self):
        """POL-GEN-05 does not exist there, so there is no hold to apply."""
        for entry in self.entries:
            with self.subTest(case=entry.case_no):
                self.assertNotIn(queue.REASON_GEN05_RELEASE, entry.reasons)

    def test_the_same_case_at_version_six_is_held(self):
        """The control: 65.13 is above the version-6 execution threshold.

        The version-6 stub rules 105 on its merits rather than escalating it,
        because the hold is checked after the ruling and an ``ESCALATE`` is a
        human-lane case for its own reason: the hold is what the version-7
        change removes, so it is the version-6 case with a ruling that shows it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            six_dir = build_stub_run(
                tmp,
                VERSION_SIX,
                "policy-v6",
                {AUTO_CASE: ("PARTIAL_REFUND", None), ESCALATED_CASE: ("FULL_REFUND", "65.13")},
            )
            disputes = queue.disputes_from_run(six_dir)
            entries = queue.build_queue(disputes, self.config)
        held = [entry for entry in entries if entry.case_no == ESCALATED_CASE]
        self.assertEqual(1, len(held))
        self.assertIn(queue.REASON_GEN05_RELEASE, held[0].reasons)

    def test_the_output_renders(self):
        text = queue.render(self.entries, self.config, self.run_dir, self.disputes)
        self.assertIn("queue: 2 case(s)", text)
        self.assertIn("measured auto-ruling SLA:", text)


class TheVersionSixQueueIsUnmovedTests(unittest.TestCase):
    """The committed version-6 run's queue is byte for byte what it was."""

    def test_the_version_six_run_still_routes(self):
        self.assertTrue(
            VERSION_SIX_RUN.is_dir(),
            "the committed version-6 run is not where this test reads it",
        )

    def test_its_output_is_byte_identical(self):
        config = queue.load_config()
        disputes = queue.disputes_from_run(VERSION_SIX_RUN)
        entries = queue.build_queue(disputes, config)
        text = queue.render(entries, config, VERSION_SIX_RUN, disputes)
        lines = text.split("\n")
        self.assertEqual(
            "queue: 29 case(s) from {0}".format(VERSION_SIX_RUN), lines[0]
        )
        self.assertEqual(
            VERSION_SIX_QUEUE_SHA256,
            hashlib.sha256("\n".join(lines[1:]).encode("utf-8")).hexdigest(),
        )

    def test_a_version_six_hold_is_still_recorded(self):
        """Case 105 of the corpus is above POL-GEN-05's threshold at version 6."""
        config = queue.load_config()
        disputes = queue.disputes_from_run(VERSION_SIX_RUN)
        entries = queue.build_queue(disputes, config)
        held = [
            entry for entry in entries if queue.REASON_GEN05_RELEASE in entry.reasons
        ]
        self.assertTrue(held, "no version-6 case is held for release any more")


# --------------------------------------------------------------------------
# The packet
# --------------------------------------------------------------------------
class TheVersionSevenPacketTests(unittest.TestCase):
    """An escalation packet builds for a version-7 run, with v2.1's signals."""

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.run_dir = build_stub_run(cls.temporary.name)
        cls.packet = escalation.build_packet(cls.run_dir, ESCALATED_CASE)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_the_packet_builds_and_names_the_version(self):
        self.assertEqual(VERSION_SEVEN, self.packet["policy_version"])
        self.assertEqual(ESCALATED_CASE, self.packet["case_no"])

    def test_it_carries_the_escalation_and_no_amount(self):
        self.assertEqual(escalation.ESCALATE, self.packet["ruling"]["ruling"])
        self.assertIsNone(self.packet["ruling"]["amount_sgd"])
        self.assertIsNone(self.packet["ruling"]["driver_compensation_sgd"])
        self.assertEqual([], self.packet["ruling"]["referrals"])

    def test_its_risk_section_is_v21s_own(self):
        clauses = [signal["clause"] for signal in self.packet["risk"]["signals"]]
        self.assertEqual([risk.V7_FRAUD_CLAUSE], clauses)
        self.assertNotIn("POL-RD-06", clauses)

    def test_it_renders_in_both_formats(self):
        self.assertIn("## 9. Risk signals", escalation.render_md(self.packet))
        self.assertIn(
            "packet_version", escalation.render_json(self.packet)
        )

    def test_the_risk_section_is_handed_the_run_s_version(self):
        """The module reads no version-6 clause itself: it forwards the version.

        ``ops/escalation.py`` reads the brief and the transcript and asks
        ``ops.risk`` for the signals; the clause table the signals come from is
        chosen there, by the version the run recorded. A packet built from a
        version-7 run therefore reads v2.1's two sentences and no version-6 one,
        which is what the test above shows from the packet's own contents.
        """
        source = (PROJECT_ROOT / "ops" / "escalation.py").read_text(encoding="utf-8")
        self.assertIn("risk.assess(case, policies, case_root, policy_version)", source)
        for clause_id in ("POL-RD-06", "POL-RD-08", "POL-NS-07", "POL-NS-09(c)"):
            with self.subTest(clause=clause_id):
                self.assertNotIn(clause_id, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
