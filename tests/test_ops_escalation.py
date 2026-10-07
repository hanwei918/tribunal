"""The escalation packet and the review step: ``ops/escalation.py``, ``ops/review.py``.

The policy says what an escalation packet holds -- ``POL-RD-10`` names the case
summary, both advocate briefs and the admissibility report; ``POL-NS-09`` adds
every clause ID relied on and the Judge's draft reasoning, and says the Judge
states the trigger and the open question. This module checks that the packet the
command builds is that, case by case, over the two runs that hold escalated
cases: the corpus run and the second sealed set's.

Five things are asserted, and each is asserted over real recorded runs rather
than over a fixture invented here:

* **Every escalated case builds one.** The set of ``ESCALATE`` cases is read off
  the run directory, so a run that changed would change what this covers, and
  each of them is built.
* **The parts are the parts the policy names**, each traced back to the record it
  came from -- the explanation is the Judge's own bytes, the briefs' verdicts are
  the referee's, the admissibility report is the pre-pass's, the timeline is the
  event log's.
* **Two builds are byte-identical**, because a digest a reviewer is asked to
  compare against is worth nothing if the packet moves under it.
* **No packet carries an answer.** No ``expected`` and no ``matched`` field
  reaches one, the ``grade`` events the log holds are left out of the timeline by
  name, and every packet builds with the answer keys unreadable.
* **The review step refuses a stale digest**, and otherwise does exactly what
  ``tribunal.precedents close`` does. Its tests use a temporary ``--store`` and
  never write ``precedents/precedents.jsonl``.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import escalation, review  # noqa: E402
from tribunal import events, loader, precedents  # noqa: E402

CORPUS_RUN = PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"
WILD_V2_RUN = PROJECT_ROOT / "runs" / "wild-v2" / "deepseek-deepseek-flash"

# The escalated cases the task names, per run. Asserted against the run rather
# than assumed, so a run whose escalations changed would fail here.
EXPECTED_ESCALATIONS = {
    "corpus": (110, 112, 207, 210, 213),
    "wild-v2": (702, 708, 711, 714, 719),
}

# The keys no packet may carry as a field.
FORBIDDEN_FIELDS = ("expected", "matched")

# The CJK blocks, as ``tests/test_language.py`` defines them: the standing
# language rule is about Chinese characters, and an em dash is not one.
CJK_RE = re.compile(
    "[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)


def run_command(entry, arguments: Sequence[str]) -> Tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = entry(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def recorded_case(run_dir: Path, case_no: int) -> Mapping[str, Any]:
    path = run_dir / "case-{0:05d}.json".format(case_no)
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)


def recorded_transcript(run_dir: Path, case_no: int) -> Mapping[str, Any]:
    document = recorded_case(run_dir, case_no)
    name = document.get("transcript_file") or "case-{0:05d}.transcript.json".format(case_no)
    return json.loads((run_dir / name).read_text(encoding="utf-8"), parse_float=Decimal)


def escalated_cases(run_dir: Path) -> Tuple[int, ...]:
    """Every case of a run whose recorded ruling is ``ESCALATE``."""
    found = []
    for path in sorted(run_dir.glob("case-*.json")):
        if path.name.endswith(".transcript.json"):
            continue
        document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
        ruling = (document.get("ruling") or {}).get("ruling") or {}
        if ruling.get("ruling") == "ESCALATE":
            found.append(document["case_no"])
    return tuple(found)


def keys_of(node: Any) -> set:
    found = set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            found |= keys_of(value)
    elif isinstance(node, list):
        for value in node:
            found |= keys_of(value)
    return found


class PacketTestCase(unittest.TestCase):
    """One packet per case, built once for the class."""

    RUN = CORPUS_RUN
    NAME = "corpus"

    @classmethod
    def setUpClass(cls):
        cls.packets: Dict[int, Mapping[str, Any]] = {
            case_no: escalation.build_packet(cls.RUN, case_no)
            for case_no in EXPECTED_ESCALATIONS[cls.NAME]
        }


# --------------------------------------------------------------------------
# The two runs
# --------------------------------------------------------------------------
class TheCorpusPacketsTests(PacketTestCase):
    """A packet builds for every ``ESCALATE`` in the corpus run."""

    def test_the_escalated_set_is_the_one_the_task_names(self):
        self.assertEqual(EXPECTED_ESCALATIONS["corpus"], escalated_cases(CORPUS_RUN))

    def test_a_packet_builds_for_every_escalated_case(self):
        self.assertEqual(
            sorted(EXPECTED_ESCALATIONS["corpus"]), sorted(self.packets)
        )
        for case_no, packet in self.packets.items():
            with self.subTest(case=case_no):
                self.assertEqual("corpus", packet["set"])
                self.assertEqual(case_no, packet["case_no"])
                self.assertEqual("ESCALATE", packet["ruling"]["ruling"])

    def test_every_packet_renders_as_json_and_as_markdown(self):
        for case_no, packet in self.packets.items():
            with self.subTest(case=case_no):
                as_json = escalation.render(packet, "json")
                as_md = escalation.render(packet, "md")
                self.assertEqual(packet, json.loads(as_json, parse_float=Decimal))
                self.assertIn("# Escalation packet", as_md)
                self.assertIn(escalation.packet_sha256(packet), as_md)
                # The judge's prose is carried verbatim, so an em dash is
                # expected; a Chinese character is not, under the standing
                # language rule.
                for rendering in (as_json, as_md):
                    self.assertIsNone(CJK_RE.search(rendering), rendering[:200])

    def test_an_unknown_format_is_refused(self):
        with self.assertRaises(escalation.EscalationError):
            escalation.render(self.packets[207], "yaml")


class TheHeldOutPacketsTests(PacketTestCase):
    """A packet builds for every ``ESCALATE`` in the second sealed set's run."""

    RUN = WILD_V2_RUN
    NAME = "wild-v2"

    def test_the_escalated_set_is_the_one_the_task_names(self):
        self.assertEqual(EXPECTED_ESCALATIONS["wild-v2"], escalated_cases(WILD_V2_RUN))

    def test_a_packet_builds_for_every_escalated_case(self):
        self.assertEqual(
            sorted(EXPECTED_ESCALATIONS["wild-v2"]), sorted(self.packets)
        )
        for case_no, packet in self.packets.items():
            with self.subTest(case=case_no):
                self.assertEqual("wild-v2", packet["set"])
                self.assertEqual("ESCALATE", packet["ruling"]["ruling"])

    def test_the_set_is_briefed_at_the_policy_version_its_registration_fixes(self):
        for case_no, packet in self.packets.items():
            with self.subTest(case=case_no):
                self.assertEqual(2, packet["policy_version"])

    def test_the_two_abstained_drafts_carry_their_reason_codes(self):
        """Case 702 is the one case in either run whose panel abstained."""
        codes = {
            draft["draft"]: draft["abstention_code"]
            for draft in self.packets[702]["drafts"]
        }
        self.assertEqual(
            {1: "DRAFT_AMOUNT_NOT_READ_OFF", 2: "DRAFT_AMOUNT_NOT_READ_OFF", 3: None, 4: None},
            codes,
        )
        self.assertEqual(
            [{"draft": 1, "code": "DRAFT_AMOUNT_NOT_READ_OFF"},
             {"draft": 2, "code": "DRAFT_AMOUNT_NOT_READ_OFF"},
             {"draft": 3, "code": None},
             {"draft": 4, "code": None}],
            self.packets[702]["trigger"]["abstentions"],
        )


# --------------------------------------------------------------------------
# The parts of a packet
# --------------------------------------------------------------------------
class ThePacketPartsTests(PacketTestCase):
    """Each part is the record it claims to be, traced back to it."""

    def test_the_case_is_the_dispute_the_pipeline_was_given(self):
        case = loader.load_case(207)
        dispute = case["dispute"]
        packet_case = self.packets[207]["case"]
        self.assertEqual(case["case_no"], packet_case["case_no"])
        self.assertEqual(dispute["dispute_id"], packet_case["dispute_id"])
        self.assertEqual(dispute["category"], packet_case["category"])
        self.assertEqual(dispute["filed_by"], packet_case["filed_by"])
        self.assertEqual(dispute["filed_at"], packet_case["filed_at"])
        self.assertEqual(dispute["channel"], packet_case["channel"])
        self.assertEqual(dispute["amount_contested_sgd"], packet_case["amount_contested_sgd"])
        self.assertEqual(dispute["claim_text"], packet_case["claim_text"])
        self.assertEqual(dispute["counterparty_statement"], packet_case["counterparty_statement"])

    def test_the_trigger_is_the_vote_the_run_recorded(self):
        transcript = recorded_transcript(CORPUS_RUN, 207)
        vote = transcript["vote"]
        trigger = self.packets[207]["trigger"]
        self.assertEqual(vote["outcome"], trigger["outcome"])
        self.assertEqual(vote["threshold"], trigger["threshold"])
        self.assertEqual(vote["valid"], trigger["valid"])
        self.assertEqual(vote["votes"], trigger["votes"])
        self.assertEqual(vote["agreement"], trigger["agreement"])

    def test_the_explanation_is_the_judge_s_own_bytes(self):
        recorded = recorded_case(CORPUS_RUN, 207)["ruling"]["ruling"]["explanation"]
        self.assertEqual(recorded, self.packets[207]["explanation"])

    def test_the_drafts_carry_their_proposal_confidence_validity_kind_seed_and_temperature(self):
        transcript = recorded_transcript(CORPUS_RUN, 207)
        by_number = {draft["draft"]: draft for draft in transcript["vote"]["drafts"]}
        for draft in self.packets[207]["drafts"]:
            source = by_number[draft["draft"]]
            with self.subTest(draft=draft["draft"]):
                self.assertEqual(source["proposal"], draft["proposal"])
                self.assertEqual(source["valid"], draft["valid"])
                self.assertEqual(source["kind"], draft["kind"])
                self.assertEqual(source["seed"], draft["seed"])
                self.assertEqual(source["temperature"], draft["temperature"])
                self.assertIn(draft["kind"], ("sampled", "position_swapped"))
                # Read with ``parse_float=Decimal``, so a confidence arrives as
                # a Decimal and is written back as the literal it was read as.
                self.assertIsInstance(draft["confidence"], Decimal)

    def test_every_draft_confidence_is_the_one_the_draft_parsed_to(self):
        """The last entry the draft owns that parsed to a ruling, and its own."""
        transcript = recorded_transcript(CORPUS_RUN, 207)
        by_number = {draft["draft"]: draft for draft in transcript["vote"]["drafts"]}
        for draft in self.packets[207]["drafts"]:
            source = by_number[draft["draft"]]
            parsed = [
                transcript["entries"][index]["parsed"]["ruling"]
                for index in source["entries"]
                if isinstance(transcript["entries"][index].get("parsed"), Mapping)
                and isinstance(transcript["entries"][index]["parsed"].get("ruling"), Mapping)
            ]
            with self.subTest(draft=draft["draft"]):
                self.assertTrue(parsed, "the draft parsed to no ruling at all")
                self.assertEqual(parsed[-1]["confidence"], draft["confidence"])

    def test_the_briefs_are_the_advocates_claims_with_the_referee_s_verdicts(self):
        transcript = recorded_transcript(CORPUS_RUN, 207)
        ledger = transcript["referee"]["ledger"]
        for side, role in (("RIDER", "RIDER_ADVOCATE"), ("DRIVER", "DRIVER_ADVOCATE")):
            parsed = [
                entry for entry in transcript["entries"] if entry.get("role") == role
            ][0]["parsed"]["claims"]
            packet_claims = self.packets[207]["briefs"][side]
            with self.subTest(side=side):
                self.assertEqual([claim["text"] for claim in parsed],
                                 [claim["text"] for claim in packet_claims])
                self.assertEqual([claim.get("evidence_ids") for claim in parsed],
                                 [claim["evidence_ids"] for claim in packet_claims])
                self.assertEqual([claim.get("clause_ids") for claim in parsed],
                                 [claim["clause_ids"] for claim in packet_claims])
            for claim, source in zip(packet_claims, parsed):
                verdict = claim["verdict"]
                self.assertIsNotNone(verdict)
                self.assertIn(verdict["status"], ("KEPT", "DISCARDED"))
                self.assertTrue(verdict["reason_code"])
                self.assertTrue(verdict["detail"])

    def test_a_discarded_claim_carries_its_discard_code_and_detail(self):
        """Case 101 is not escalated, so it is built with ``--any``.

        It is the corpus case with a discarded claim, and the discard code is
        what the reviewer would otherwise have to reconstruct.
        """
        packet = escalation.build_packet(CORPUS_RUN, 101, any_ruling=True)
        discards = [
            claim["verdict"]
            for side in ("RIDER", "DRIVER")
            for claim in packet["briefs"][side]
            if claim["verdict"] and claim["verdict"]["status"] == "DISCARDED"
        ]
        self.assertTrue(discards)
        self.assertEqual("IMPAIRMENT_UNDISCLOSED", discards[0]["reason_code"])
        self.assertIn("does not name its issue code", discards[0]["detail"])

    def test_the_admissibility_report_is_the_pre_pass_s_own(self):
        case = loader.load_case(207)
        report = self.packets[207]["admissibility"]
        self.assertEqual(
            [artifact["evidence_id"] for artifact in case["evidence"]],
            [artifact["evidence_id"] for artifact in report],
        )
        for source, entry in zip(case["evidence"], report):
            admitted = source["admissibility"]
            with self.subTest(artifact=entry["evidence_id"]):
                self.assertEqual(source["evidence_type"], entry["evidence_type"])
                self.assertEqual(source["source"], entry["source"])
                self.assertEqual(admitted["status"], entry["status"])
                self.assertEqual(admitted["issues"], entry["issues"])
                self.assertEqual(admitted["weight_multiplier"], entry["weight_multiplier"])
                self.assertEqual(admitted["notes"], entry["notes"])

    def test_the_clause_ids_are_the_union_of_the_kept_claims_the_drafts_and_the_explanation(self):
        packet = self.packets[207]
        found = set(packet["clause_ids"])
        self.assertEqual(sorted(found), list(packet["clause_ids"]), "not sorted or unique")
        for side in ("RIDER", "DRIVER"):
            for claim in packet["briefs"][side]:
                if claim["verdict"] and claim["verdict"]["status"] == "KEPT":
                    for clause_id in claim["clause_ids"]:
                        base = precedents.base_clause_id(clause_id)
                        self.assertIn(base, found, clause_id)
        for clause_id in packet["trigger"]["explanation_clause_ids"]:
            self.assertIn(precedents.base_clause_id(clause_id), found, clause_id)

    def test_the_risk_signals_are_part_1_s_reading_of_the_same_case(self):
        packet = self.packets[207]
        self.assertEqual(["POL-NS-07"], packet["risk"]["tripped"])
        self.assertEqual(
            ["POL-NS-07", "POL-NS-09(c)", "POL-NS-09(d)"],
            [signal["clause"] for signal in packet["risk"]["signals"]],
        )
        self.assertEqual([], packet["risk"]["attention_flags"])

    def test_the_fare_lines_are_the_fare_breakdown_s_lines(self):
        case = loader.load_case(207)
        payload = [
            artifact["payload"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "FARE_BREAKDOWN"
        ][0]
        self.assertEqual(sorted(payload), [line["line"] for line in self.packets[207]["fare_lines"]])
        lines = {line["line"]: line["value"] for line in self.packets[207]["fare_lines"]}
        self.assertEqual(payload["cancellation_fee"], lines["cancellation_fee"])
        self.assertEqual(payload["total_charged"], lines["total_charged"])

    def test_the_timeline_is_the_log_s_events_for_the_case_without_a_grade_event(self):
        log = CORPUS_RUN / events.EVENTS_FILE
        recorded = events.events_for_case(log, 207)
        without_grades = [
            event for event in recorded if event.get("event") != events.EVENT_GRADE
        ]
        rows = self.packets[207]["timeline"]
        self.assertEqual(len(without_grades), len(rows))
        for event, row in zip(without_grades, rows):
            with self.subTest(seq=event.get("seq")):
                self.assertEqual(event.get("ts"), row["ts"])
                self.assertEqual(event.get("event"), row["event"])
                self.assertEqual(event.get("status"), row["status"])
                self.assertEqual(event.get("total_tokens"), row["tokens"])
                self.assertEqual(event.get("seconds"), row["seconds"])
                self.assertEqual(event.get("parse_outcome"), row["parse_outcome"])

    def test_the_timeline_names_a_role_or_a_draft(self):
        rows = self.packets[207]["timeline"]
        roles = {row["role_or_draft"] for row in rows}
        self.assertIn("RIDER_ADVOCATE", roles)
        self.assertIn("DRIVER_ADVOCATE", roles)
        self.assertIn("draft 1", roles)


# --------------------------------------------------------------------------
# The digest, the determinism and the answers
# --------------------------------------------------------------------------
class TheDigestAndDeterminismTests(PacketTestCase):
    """The digest is a function of the packet, and the packet does not move."""

    def test_two_builds_are_byte_identical(self):
        for case_no in EXPECTED_ESCALATIONS["corpus"]:
            with self.subTest(case=case_no):
                first = escalation.build_packet(CORPUS_RUN, case_no)
                second = escalation.build_packet(CORPUS_RUN, case_no)
                self.assertEqual(escalation.render_json(first), escalation.render_json(second))
                self.assertEqual(escalation.packet_sha256(first), escalation.packet_sha256(second))

    def test_the_digest_is_the_sha256_of_the_json_the_command_prints(self):
        code, out, err = run_command(
            escalation.main, ["--run-dir", str(CORPUS_RUN), "--case", "207"]
        )
        self.assertEqual(0, code, err)
        digest = [line for line in err.splitlines() if line.startswith("packet sha256: ")][0]
        self.assertEqual(
            escalation.packet_sha256(json.loads(out, parse_float=Decimal)),
            digest.split(": ", 1)[1],
        )

    def test_the_digest_moves_when_the_packet_moves(self):
        """A digest that did not move would be a digest worth nothing."""
        packet = self.packets[207]
        moved = dict(packet, case_no=999)
        self.assertNotEqual(escalation.packet_sha256(packet), escalation.packet_sha256(moved))


class ThePacketHoldsNoAnswerTests(PacketTestCase):
    """No packet carries an answer field, and none is built from a key."""

    def test_no_packet_carries_an_expected_or_matched_field(self):
        for case_no, packet in self.packets.items():
            with self.subTest(case=case_no):
                self.assertEqual(set(), keys_of(packet) & set(FORBIDDEN_FIELDS))

    def test_no_timeline_row_is_a_grade_event(self):
        for case_no, packet in self.packets.items():
            with self.subTest(case=case_no):
                self.assertNotIn("grade", {row["event"] for row in packet["timeline"]})

    def test_the_run_does_hold_grade_events_that_were_left_out(self):
        """The control: the events exist, so leaving them out is a choice."""
        log = CORPUS_RUN / events.EVENTS_FILE
        grades = [
            event for event in events.events_for_case(log, 207)
            if event.get("event") == events.EVENT_GRADE
        ]
        self.assertTrue(grades, "case 207 has no grade event, so nothing was filtered")
        self.assertIn("matched", grades[0])

    def test_every_packet_builds_with_the_answer_keys_unreadable(self):
        def guard():
            real_open = io.open

            def guarded(file, *args, **kwargs):
                text = str(file).replace(os.sep, "/")
                if "/answers/" in text:
                    raise AssertionError("an ops command opened {0}".format(text))
                return real_open(file, *args, **kwargs)

            return guarded

        with mock.patch("io.open", guard()), mock.patch("builtins.open", guard()):
            for case_no in EXPECTED_ESCALATIONS["corpus"]:
                packet = escalation.build_packet(CORPUS_RUN, case_no)
                self.assertEqual(set(), keys_of(packet) & set(FORBIDDEN_FIELDS))
            for case_no in EXPECTED_ESCALATIONS["wild-v2"]:
                packet = escalation.build_packet(WILD_V2_RUN, case_no)
                self.assertEqual(set(), keys_of(packet) & set(FORBIDDEN_FIELDS))


# --------------------------------------------------------------------------
# The trigger and the directive
# --------------------------------------------------------------------------
class TheTriggerAndDirectiveTests(PacketTestCase):
    """A packet is built for an escalation, and carries what it directs."""

    def test_a_case_that_did_not_escalate_is_refused(self):
        for case_no in (101, 208, 214):
            with self.subTest(case=case_no):
                with self.assertRaises(escalation.EscalationError) as caught:
                    escalation.build_packet(CORPUS_RUN, case_no)
                self.assertIn("not ESCALATE", str(caught.exception))

    def test_any_builds_one_for_a_case_that_did_not_escalate(self):
        packet = escalation.build_packet(CORPUS_RUN, 101, any_ruling=True)
        self.assertEqual("PARTIAL_REFUND", packet["ruling"]["ruling"])

    def test_the_command_refuses_a_case_that_did_not_escalate(self):
        code, out, err = run_command(
            escalation.main, ["--run-dir", str(CORPUS_RUN), "--case", "101"]
        )
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)
        self.assertEqual("", out)

    def test_case_207_carries_its_instruction_to_refund_the_rider(self):
        referrals = self.packets[207]["ruling"]["referrals"]
        self.assertTrue(referrals)
        refund = [referral for referral in referrals if "refund" in referral]
        self.assertTrue(refund, referrals)
        self.assertIn("SGD 4.00", refund[0])
        self.assertIn("POL-NS-07", refund[0])

    def test_the_referrals_are_the_ruling_s_own(self):
        recorded = recorded_case(CORPUS_RUN, 207)["ruling"]["ruling"]["referrals"]
        self.assertEqual(recorded, self.packets[207]["ruling"]["referrals"])


# --------------------------------------------------------------------------
# The review step
# --------------------------------------------------------------------------
class TheReviewTests(unittest.TestCase):
    """``ops.review`` adds one requirement to ``tribunal.precedents close``."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Path(self._tmp.name) / "precedents"

    def arguments(self, digest: str, store: Path = None) -> List[str]:
        return [
            "--run-dir", str(CORPUS_RUN),
            "--case", "207",
            "--packet-sha256", digest,
            "--store", str(store or self.store),
            "--ruling", "NO_ACTION",
            "--clause", "POL-NS-01",
            "--closed-by", "a reviewer",
            "--summary", "The fee stands on the record as it is.",
            "--reason", "Reviewed the packet; the fee stands under POL-NS-01 on EV-FARE-00207.",
        ]

    def test_the_digest_of_the_packet_is_the_one_the_command_requires(self):
        digest = escalation.packet_sha256(escalation.build_packet(CORPUS_RUN, 207))
        code, out, err = run_command(review.main, self.arguments(digest))
        self.assertEqual(0, code, err)
        self.assertIn("stored P-0001 for case 207 of the corpus set", out)
        self.assertTrue((self.store / "precedents.jsonl").is_file())

    def test_a_stale_digest_is_refused_and_nothing_is_stored(self):
        stale = "0" * 64
        code, out, err = run_command(review.main, self.arguments(stale))
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)
        self.assertIn("not the packet that was read", err)
        self.assertIn(stale, err)
        self.assertFalse((self.store / "precedents.jsonl").exists())

    def test_a_digest_that_is_not_a_digest_is_refused(self):
        for value in ("", "abc", "z" * 64, "A" * 63):
            with self.subTest(value=value):
                code, out, err = run_command(review.main, self.arguments(value))
                self.assertEqual(1, code)
                self.assertIn("not a SHA-256 hex digest", err)

    def test_a_digest_in_upper_case_is_the_same_digest(self):
        digest = escalation.packet_sha256(escalation.build_packet(CORPUS_RUN, 207))
        code, out, err = run_command(review.main, self.arguments(digest.upper()))
        self.assertEqual(0, code, err)

    def test_the_closure_rules_are_the_ones_precedents_already_enforces(self):
        """Everything else passes through, so its refusals are still its own."""
        digest = escalation.packet_sha256(escalation.build_packet(CORPUS_RUN, 207))
        arguments = self.arguments(digest)
        arguments[arguments.index("--reason") + 1] = "too short"
        code, out, err = run_command(review.main, arguments)
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)
        self.assertFalse((self.store / "precedents.jsonl").exists())

    def test_the_override_flag_is_the_one_precedents_derives(self):
        """The panel proposed ESCALATE, so a monetary closure overrides it."""
        digest = escalation.packet_sha256(escalation.build_packet(CORPUS_RUN, 207))
        code, out, err = run_command(review.main, self.arguments(digest))
        self.assertEqual(0, code, err)
        entry = json.loads(
            (self.store / "precedents.jsonl").read_text(encoding="utf-8").splitlines()[0],
            parse_float=Decimal,
        )
        self.assertTrue(entry["override"])
        self.assertEqual("NO_ACTION", entry["decision"]["ruling"])

    def test_the_human_decision_event_is_written(self):
        """The closure and the decision share one chained store."""
        digest = escalation.packet_sha256(escalation.build_packet(CORPUS_RUN, 207))
        run_command(review.main, self.arguments(digest))
        log = (self.store / "precedents.jsonl").read_text(encoding="utf-8")
        self.assertIn("human_decision", log)
        self.assertIn("closure", log)

    def test_the_repository_s_own_store_is_never_written(self):
        committed = (PROJECT_ROOT / "precedents" / "precedents.jsonl").read_bytes()
        digest = escalation.packet_sha256(escalation.build_packet(CORPUS_RUN, 207))
        run_command(review.main, self.arguments(digest))
        self.assertEqual(
            committed, (PROJECT_ROOT / "precedents" / "precedents.jsonl").read_bytes()
        )

    def test_a_case_that_did_not_escalate_is_refused_before_the_store_is_opened(self):
        code, out, err = run_command(
            review.main,
            [
                "--run-dir", str(CORPUS_RUN),
                "--case", "101",
                "--packet-sha256", "0" * 64,
                "--store", str(self.store),
            ],
        )
        self.assertEqual(1, code)
        self.assertIn("FATAL", err)
        self.assertFalse((self.store / "precedents.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
