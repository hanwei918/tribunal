"""The chat threat lane of ``ops/chat_signals.py`` and ``ops/queue.py``.

Four things are asserted here, each over the real fixture or a real case rather
than over a restatement of it:

* **The rule table.** Every threat rule id carries the ``THREAT-`` prefix and
  every exclusion rule id the ``EXCL-`` prefix, the two id sets are disjoint and
  sorted, and together they are exactly the table's ids.
* **The detector.** ``detect`` returns ``{"threat": bool, "matched": [rule ids]}``;
  a clean message is not a threat; an exclusion clears a message a threat word
  would otherwise flag; and the 32-message fixture is scored exactly -- 6 true
  positives, 0 false positives, 0 false negatives.
* **The command.** ``python3 -m ops.chat_signals`` reads a JSON array of texts
  from standard input, answers one verdict per message in input order, and two
  runs are byte-identical.
* **The lane.** ``ops/queue.lane_for`` fast-tracks a dispute whose chat carries a
  threat to ``SAFETY_FAST_TRACK`` with the reason ``CHAT_THREAT``, ahead of the
  ``POL-GEN-08(1)`` flags and the kill switch; and ``chat_log_has_threat`` reads
  the signal off a case's own ``CHAT_LOG`` artifact. No case of the corpus trips
  it, so the lane changes no case in the repository.

The rules that bind every module of the layer -- the import graph, the answer
keys, the write guard and the determinism -- are asserted once, over every
``ops`` command, in ``tests/test_ops_layer.py``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import chat_signals, queue  # noqa: E402
from tribunal import loader  # noqa: E402

# The labelled fixture, and the 29-case corpus in manifest order.
CHAT_FIXTURE = PROJECT_ROOT / "eval" / "fixtures" / "chat-signals-v1.json"
CORPUS_CASE_NUMBERS: Tuple[int, ...] = tuple(
    entry["case_no"]
    for entry in json.loads((PROJECT_ROOT / "data" / "index.json").read_text())
)


def fixture() -> Mapping[str, Any]:
    return json.loads(CHAT_FIXTURE.read_text(encoding="utf-8"))


def run_command(arguments: List[str], stdin: str = "") -> Tuple[int, str, str]:
    """The command, as a subprocess, with its stdin and both streams captured."""
    completed = subprocess.run(
        [sys.executable, "-m", "ops.chat_signals"] + arguments,
        cwd=str(PROJECT_ROOT),
        input=stdin,
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout, completed.stderr


def dispute(chat_threat: bool, **overrides: Any) -> queue.Dispute:
    """One dispute fixture, with only the fields the lane reads."""
    fields: Dict[str, Any] = {
        "case_no": 101,
        "category": "NO_SHOW_CHARGE",
        "filed_at": "2026-07-01T10:00:00+08:00",
        "amount_contested_sgd": None,
        "ruling": "NO_ACTION",
        "wall_seconds": None,
        "risk_tripped": False,
        "chat_threat": chat_threat,
    }
    fields.update(overrides)
    return queue.Dispute(**fields)


def chat_case(messages: List[str]) -> Mapping[str, Any]:
    """One case carrying a chat log whose messages are ``messages``."""
    return {
        "case_no": 1,
        "dispute": {"category": "NO_SHOW_CHARGE"},
        "evidence": [
            {
                "evidence_id": "EV-CHAT-1",
                "evidence_type": "CHAT_LOG",
                "payload": {
                    "messages": [{"msg_id": "M", "text": text} for text in messages]
                },
            }
        ],
    }


# --------------------------------------------------------------------------
# The rule table
# --------------------------------------------------------------------------
class TheRuleTableTests(unittest.TestCase):
    """The two kinds of rule, and the ids that name them."""

    def test_every_id_carries_the_prefix_of_its_kind(self):
        for rule in chat_signals.RULES:
            with self.subTest(rule=rule.rule_id):
                if rule.kind == chat_signals.THREAT:
                    self.assertTrue(rule.rule_id.startswith(chat_signals.THREAT_PREFIX))
                else:
                    self.assertEqual(chat_signals.EXCLUSION, rule.kind)
                    self.assertTrue(
                        rule.rule_id.startswith(chat_signals.EXCLUSION_PREFIX)
                    )

    def test_the_two_id_sets_are_sorted_disjoint_and_complete(self):
        every = sorted(rule.rule_id for rule in chat_signals.RULES)
        self.assertEqual(every, sorted(chat_signals.THREAT_RULE_IDS + chat_signals.EXCLUSION_RULE_IDS))
        self.assertEqual(
            [], sorted(set(chat_signals.THREAT_RULE_IDS) & set(chat_signals.EXCLUSION_RULE_IDS))
        )
        self.assertEqual(sorted(chat_signals.THREAT_RULE_IDS), list(chat_signals.THREAT_RULE_IDS))
        self.assertEqual(
            sorted(chat_signals.EXCLUSION_RULE_IDS), list(chat_signals.EXCLUSION_RULE_IDS)
        )
        self.assertTrue(chat_signals.THREAT_RULE_IDS)
        self.assertTrue(chat_signals.EXCLUSION_RULE_IDS)

    def test_every_rule_carries_a_description(self):
        for rule in chat_signals.RULES:
            with self.subTest(rule=rule.rule_id):
                self.assertTrue(rule.description.strip())


# --------------------------------------------------------------------------
# The detector
# --------------------------------------------------------------------------
class TheDetectorTests(unittest.TestCase):
    """``detect`` on the messages the fixture labels."""

    def test_a_clean_message_is_not_a_threat_and_matches_nothing(self):
        self.assertEqual(
            {"threat": False, "matched": []}, chat_signals.detect("ok, on my way")
        )

    def test_a_null_message_is_not_a_threat(self):
        self.assertEqual({"threat": False, "matched": []}, chat_signals.detect(None))

    def test_an_explicit_threat_matches_and_is_a_threat(self):
        verdict = chat_signals.detect("you touch my bag again and I will hurt you")
        self.assertTrue(verdict["threat"])
        self.assertIn("THREAT-HARM", verdict["matched"])

    def test_a_complaint_is_not_a_threat_even_with_a_threat_word(self):
        verdict = chat_signals.detect("I will report this and I will hurt your rating")
        self.assertFalse(verdict["threat"])
        self.assertIn("EXCL-COMPLAINT", verdict["matched"])
        self.assertIn("THREAT-HARM", verdict["matched"])

    def test_the_fixture_is_scored_exactly(self):
        document = fixture()
        true_positives = false_positives = false_negatives = 0
        for item in document["items"]:
            produced = chat_signals.detect(item["text"])["threat"]
            expected = bool(item["labels"]["threat"])
            true_positives += produced and expected
            false_positives += produced and not expected
            false_negatives += expected and not produced
        self.assertEqual(6, true_positives)
        self.assertEqual(0, false_positives)
        self.assertEqual(0, false_negatives)


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
class TheCommandTests(unittest.TestCase):
    """``python3 -m ops.chat_signals``, as ``eval/func_sets.py`` runs it."""

    def test_the_json_array_on_stdin_is_read_in_order(self):
        texts = [item["text"] for item in fixture()["items"]]
        code, out, err = run_command([], stdin=json.dumps(texts))
        self.assertEqual(0, code, err)
        payload = json.loads(out)
        self.assertEqual(len(texts), payload["count"])
        self.assertEqual(
            [index for index, _ in enumerate(texts)],
            [row["index"] for row in payload["results"]],
        )

    def test_the_verdicts_agree_with_detect(self):
        texts = [item["text"] for item in fixture()["items"]]
        code, out, err = run_command([], stdin=json.dumps(texts))
        self.assertEqual(0, code, err)
        payload = json.loads(out)
        for text, row in zip(texts, payload["results"]):
            self.assertEqual(chat_signals.detect(text)["threat"], row["threat"])
            self.assertEqual(chat_signals.detect(text)["matched"], row["matched"])

    def test_two_runs_are_byte_identical(self):
        texts = [item["text"] for item in fixture()["items"]]
        self.assertEqual(
            run_command([], stdin=json.dumps(texts)),
            run_command([], stdin=json.dumps(texts)),
        )

    def test_a_blank_input_is_no_messages(self):
        code, out, err = run_command([], stdin="")
        self.assertEqual(0, code, err)
        self.assertEqual({"count": 0, "results": []}, json.loads(out))


# --------------------------------------------------------------------------
# The lane
# --------------------------------------------------------------------------
class TheLaneTests(unittest.TestCase):
    """``ops/queue`` fast-tracks a dispute whose chat carries a threat."""

    def setUp(self):
        self.config = queue.load_config()

    def test_a_chat_threat_is_fast_tracked_with_its_own_reason(self):
        lane, reasons = queue.lane_for(dispute(True), self.config)
        self.assertEqual(queue.LANE_SAFETY, lane)
        self.assertEqual((queue.REASON_CHAT_THREAT,), reasons)

    def test_it_outranks_the_flags_and_the_kill_switch(self):
        paused = queue.load_config()
        paused = paused._replace(auto_rulings_enabled=False)
        lane, reasons = queue.lane_for(
            dispute(True, safety_flag=True, complaint_flag=True), paused
        )
        self.assertEqual(queue.LANE_SAFETY, lane)
        self.assertEqual((queue.REASON_CHAT_THREAT,), reasons)

    def test_a_dispute_without_a_chat_threat_is_unchanged(self):
        lane, reasons = queue.lane_for(dispute(False), self.config)
        self.assertEqual(queue.LANE_AUTO, lane)
        self.assertEqual((queue.REASON_RULED,), reasons)

    def test_the_signal_is_read_off_the_case_s_chat_log(self):
        self.assertTrue(
            queue.chat_log_has_threat(chat_case(["watch your back, I know where you live"]))
        )
        self.assertFalse(
            queue.chat_log_has_threat(chat_case(["I will report this to support"]))
        )

    def test_a_case_with_no_chat_log_carries_no_signal(self):
        self.assertFalse(queue.chat_log_has_threat({"case_no": 1, "evidence": []}))

    def test_no_corpus_case_carries_a_threat(self):
        """The lane changes no case in the repository."""
        for case_no in CORPUS_CASE_NUMBERS:
            with self.subTest(case_no=case_no):
                self.assertFalse(queue.chat_log_has_threat(loader.load_case(case_no)))


if __name__ == "__main__":
    unittest.main()
