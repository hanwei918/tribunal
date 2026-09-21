"""Tests for ``tribunal.pipeline``.

No network: ``LLMClient`` is driven through its injected transport with recorded
response bodies. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, llm, money, pipeline, transcript as transcript_module  # noqa: E402

FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"
PINNED_NOW = "2026-09-21T12:00:00+00:00"
CASE = 208

RIDER = transcript_module.ROLE_RIDER_ADVOCATE
DRIVER = transcript_module.ROLE_DRIVER_ADVOCATE
JUDGE = transcript_module.ROLE_JUDGE


def envelope(
    answer: str,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    reasoning_tokens: int = 0,
    cached_tokens: int = 0,
) -> llm.HttpResult:
    body = json.dumps(
        {
            "choices": [{"message": {"content": answer}}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
                "prompt_tokens_details": {"cached_tokens": cached_tokens},
            },
        }
    )
    return llm.HttpResult(status=200, body=body.encode("utf-8"))


RIDER_CLAIMS = json.dumps(
    [{"text": "rider point", "evidence_ids": ["EV-GPS-00208"], "clause_ids": ["POL-NS-01"]}]
)
DRIVER_CLAIMS = json.dumps(
    [{"text": "driver point", "evidence_ids": ["EV-GPS-00208"], "clause_ids": ["POL-NS-02"]}]
)
GOOD_RULING = json.dumps(
    {
        "ruling": {
            "ruling": "PARTIAL_REFUND",
            "amount_sgd": 4.35,
            "driver_compensation_sgd": None,
            "referrals": [],
            "confidence": 0.85,
            "explanation": "because",
        },
        "discarded_claims": [],
    }
)


class FakeTransport:
    """Scripted responses, and a record of every request body."""

    def __init__(self, *responses: llm.HttpResult) -> None:
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": body})
        if not self.responses:
            raise AssertionError("FakeTransport ran out of scripted responses")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def client_for(*responses: llm.HttpResult) -> llm.LLMClient:
    return llm.LLMClient(
        model="hy4-preview",
        api_key=FAKE_KEY,
        transport=FakeTransport(*responses),
        sleep=lambda seconds: None,
        clock=lambda: 0.0,
    )


def run(*responses: llm.HttpResult) -> pipeline.PipelineResult:
    return pipeline.run_case(CASE, client_for(*responses), now=lambda: PINNED_NOW)


def roles_of(result) -> list:
    return [entry.role for entry in result.transcript.entries]


class StanceOnlyDifferenceTests(unittest.TestCase):
    """The project's central claim, checked rather than asserted."""

    def test_the_shipped_prompts_differ_only_inside_the_stance_block(self):
        ranges = pipeline.check_stance_only_difference()
        self.assertTrue(ranges, "expected the two stances to differ somewhere")
        _rider, _driver, (start, end) = pipeline.render_advocate_prompts()
        for low, high in ranges:
            self.assertGreaterEqual(low, start, "a difference starts before the stance block")
            self.assertLessEqual(high, end, "a difference ends after the stance block")

    def test_the_rendered_prompts_are_otherwise_identical(self):
        rider, driver, (start, end) = pipeline.render_advocate_prompts()
        self.assertEqual(rider.splitlines()[:start], driver.splitlines()[:start])
        self.assertEqual(rider.splitlines()[end:], driver.splitlines()[end:])

    def test_an_altered_pair_is_caught(self):
        """A difference outside the block must raise, not pass quietly."""
        rider, driver, region = pipeline.render_advocate_prompts()
        altered = rider.replace("## Your role", "## Your ROLE", 1)
        self.assertNotEqual(altered, rider)

        with self.assertRaises(pipeline.StanceLeakError) as caught:
            pipeline.assert_stance_only(altered, driver, region)
        self.assertIn("outside the stance block", str(caught.exception))

    def test_a_template_with_two_placeholders_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name in pipeline.STANCE_FILES.values():
                (base / name).write_text("stance\n", encoding="utf-8")
            (base / pipeline.ADVOCATE_TEMPLATE).write_text(
                "a\n{{STANCE}}\nb\n{{STANCE}}\n", encoding="utf-8"
            )
            with self.assertRaises(pipeline.PipelineError):
                pipeline.render_advocate_prompts(base)


class CleanRunTests(unittest.TestCase):
    """A clean run, end to end."""

    def setUp(self):
        self.transport = FakeTransport(
            envelope(RIDER_CLAIMS, prompt_tokens=100, completion_tokens=20, reasoning_tokens=7),
            envelope(DRIVER_CLAIMS, prompt_tokens=110, completion_tokens=30),
            envelope(GOOD_RULING, prompt_tokens=200, completion_tokens=40, cached_tokens=3),
        )
        self.client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=self.transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        self.result = pipeline.run_case(CASE, self.client, now=lambda: PINNED_NOW)

    def test_the_run_succeeds_and_returns_the_ruling(self):
        self.assertTrue(self.result.ok)
        self.assertIsNone(self.result.failed_agent)
        self.assertIsNone(self.result.failure_reason)
        self.assertEqual(self.result.case_no, CASE)
        self.assertEqual(self.result.model, "hy4-preview")
        self.assertEqual(self.result.ruling["ruling"]["ruling"], "PARTIAL_REFUND")
        self.assertEqual(self.result.ruling_findings, [])

    def test_the_calls_happen_in_the_fixed_order(self):
        self.assertEqual(roles_of(self.result), [RIDER, DRIVER, JUDGE])
        self.assertEqual(len(self.transport.calls), 3)

        bodies = [json.loads(call["body"].decode("utf-8")) for call in self.transport.calls]
        self.assertEqual([b["model"] for b in bodies], ["hy4-preview"] * 3)
        # the rider's system prompt carries the rider stance, the driver's the driver's
        self.assertIn("**RIDER**", bodies[0]["messages"][0]["content"])
        self.assertIn("**DRIVER**", bodies[1]["messages"][0]["content"])
        self.assertIn("arbitrator", bodies[2]["messages"][0]["content"])

    def test_the_totals_cover_the_whole_run(self):
        self.assertEqual(self.result.prompt_tokens, 410)
        self.assertEqual(self.result.completion_tokens, 90)
        self.assertEqual(self.result.reasoning_tokens, 7)
        self.assertEqual(self.result.cached_tokens, 3)
        self.assertEqual(self.result.transcript.totals()["calls"], 3)

    def test_money_fields_are_decimal_never_float(self):
        amount = self.result.ruling["ruling"]["amount_sgd"]
        self.assertIsInstance(amount, Decimal)
        self.assertNotIsInstance(amount, float)
        self.assertEqual(amount, Decimal("4.35"))

    def test_a_money_field_written_as_a_string_is_still_a_decimal(self):
        ruling = json.dumps(
            {
                "ruling": {
                    "ruling": "PARTIAL_REFUND", "amount_sgd": "4.35",
                    "driver_compensation_sgd": None, "referrals": [],
                    "confidence": 0.9, "explanation": "x",
                },
                "discarded_claims": [],
            }
        )
        result = run(envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(ruling))
        self.assertIsInstance(result.ruling["ruling"]["amount_sgd"], Decimal)
        self.assertEqual(result.ruling["ruling"]["amount_sgd"], Decimal("4.35"))

    def test_the_printer_produces_a_readable_summary(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            pipeline._print_result(self.result, None)
        text = buffer.getvalue()
        self.assertIn("case 208", text)
        self.assertIn("RIDER_ADVOCATE", text)
        self.assertIn("DRIVER_ADVOCATE", text)
        self.assertIn("JUDGE", text)
        self.assertIn("PARTIAL_REFUND", text)
        self.assertIn("totals", text)
        self.assertIn("transcript sha256", text)
        self.assertNotIn(FAKE_KEY, text)


class BriefIdentityTests(unittest.TestCase):
    """One brief, byte-identical for all three agents."""

    def setUp(self):
        self.transport = FakeTransport(
            envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(GOOD_RULING)
        )
        self.client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=self.transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        self.result = pipeline.run_case(CASE, self.client, now=lambda: PINNED_NOW)
        self.brief_json = money.dumps_canonical(brief.build_brief(CASE))
        self.brief_sha = hashlib.sha256(self.brief_json.encode("utf-8")).hexdigest()

    def entry(self, role):
        return next(e for e in self.result.transcript.entries if e.role == role)

    def test_both_advocates_were_handed_the_same_brief_bytes(self):
        self.assertEqual(self.entry(RIDER).user_sha256, self.entry(DRIVER).user_sha256)

    def test_the_brief_the_advocates_got_is_the_canonical_brief(self):
        self.assertEqual(self.entry(RIDER).user_sha256, self.brief_sha)

    def test_the_result_exposes_the_brief_digest(self):
        self.assertEqual(self.result.brief_sha256, self.brief_sha)
        self.assertEqual(self.result.brief_sha256, brief.brief_digest(brief.build_brief(CASE))[1])

    def test_the_judge_message_embeds_those_same_bytes(self):
        judge_user = json.loads(self.transport.calls[2]["body"].decode("utf-8"))["messages"][1]["content"]
        self.assertEqual(money.dumps_canonical(json.loads(judge_user)["brief"]), self.brief_json)
        self.assertEqual(self.entry(JUDGE).user_sha256,
                         hashlib.sha256(judge_user.encode("utf-8")).hexdigest())

    def test_the_judge_message_carries_both_claim_arrays(self):
        judge_user = json.loads(self.transport.calls[2]["body"].decode("utf-8"))["messages"][1]["content"]
        parsed = json.loads(judge_user)
        self.assertEqual(parsed["claims"][RIDER], json.loads(RIDER_CLAIMS))
        self.assertEqual(parsed["claims"][DRIVER], json.loads(DRIVER_CLAIMS))


class UnusableResponseTests(unittest.TestCase):
    """A model that answers with the wrong shape is retried once, then reported."""

    def test_an_advocate_returning_an_object_is_retried_once_then_succeeds(self):
        transport = FakeTransport(
            envelope('{"claims": []}'),
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(GOOD_RULING),
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertTrue(result.ok)
        self.assertEqual(roles_of(result), [RIDER, RIDER, DRIVER, JUDGE])
        # both raw bodies are on the record
        self.assertEqual(result.transcript.entries[0].response_text, '{"claims": []}')
        self.assertIsNotNone(result.transcript.entries[0].note)
        self.assertEqual(result.transcript.entries[1].response_text, RIDER_CLAIMS)

    def test_an_advocate_failing_twice_gives_a_failed_result_not_an_exception(self):
        transport = FakeTransport(envelope('{"claims": []}'), envelope('{"claims": []}'))
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertFalse(result.ok)
        self.assertEqual(result.failed_agent, RIDER)
        self.assertIn("JSON array", result.failure_reason)
        self.assertIsNone(result.ruling)
        # the run stopped at the failure: no driver call, no judge call
        self.assertEqual(roles_of(result), [RIDER, RIDER])
        self.assertEqual(len(transport.calls), 2)
        # both raw bodies preserved, and no empty claim list was substituted
        self.assertEqual(result.transcript.entries[0].response_text, '{"claims": []}')
        self.assertEqual(result.transcript.entries[1].response_text, '{"claims": []}')

    def test_a_judge_missing_a_required_field_is_retried_then_fails(self):
        incomplete = json.dumps({"ruling": {"ruling": "NO_ACTION"}})
        transport = FakeTransport(
            envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS),
            envelope(incomplete), envelope(incomplete),
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertFalse(result.ok)
        self.assertEqual(result.failed_agent, JUDGE)
        self.assertIn("discarded_claims", result.failure_reason)
        self.assertIsNone(result.ruling)
        self.assertEqual(roles_of(result), [RIDER, DRIVER, JUDGE, JUDGE])
        self.assertEqual(result.transcript.entries[2].response_text, incomplete)

    def test_a_malformed_judge_answer_is_retried_too(self):
        transport = FakeTransport(
            envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS),
            envelope('{"ruling\\":\\"ALLOW"'), envelope(GOOD_RULING),
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertTrue(result.ok)
        self.assertEqual(roles_of(result), [RIDER, DRIVER, JUDGE, JUDGE])
        self.assertEqual(result.transcript.entries[2].parse_outcome, "MALFORMED")


class RulingShapeTests(unittest.TestCase):
    """Invariants are recorded, never corrected."""

    def run_with_ruling(self, ruling: str):
        return run(envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(ruling))

    def test_an_escalate_ruling_with_money_is_recorded_and_left_alone(self):
        bad = json.dumps(
            {
                "ruling": {
                    "ruling": "ESCALATE", "amount_sgd": 4.35, "driver_compensation_sgd": None,
                    "referrals": [], "confidence": 0.5, "explanation": "escalating",
                },
                "discarded_claims": [],
            }
        )
        result = self.run_with_ruling(bad)

        self.assertTrue(result.ok, "a broken contract is a finding, not a failed run")
        names = [finding["invariant"] for finding in result.ruling_findings]
        self.assertIn("escalate_has_null_money_fields", names)
        # NOT corrected: the money field is exactly where the model put it
        self.assertEqual(result.ruling["ruling"]["ruling"], "ESCALATE")
        self.assertEqual(result.ruling["ruling"]["amount_sgd"], Decimal("4.35"))

    def test_a_driver_compensation_ruling_that_does_not_mirror_amount(self):
        bad = json.dumps(
            {
                "ruling": {
                    "ruling": "DRIVER_COMPENSATION", "amount_sgd": 6.40,
                    "driver_compensation_sgd": 3.20, "referrals": [], "confidence": 0.8,
                    "explanation": "x",
                },
                "discarded_claims": [],
            }
        )
        result = self.run_with_ruling(bad)

        names = [finding["invariant"] for finding in result.ruling_findings]
        self.assertIn("driver_compensation_mirrors_amount", names)
        self.assertEqual(result.ruling["ruling"]["amount_sgd"], Decimal("6.40"))
        self.assertEqual(result.ruling["ruling"]["driver_compensation_sgd"], Decimal("3.20"))

    def test_a_driver_compensation_ruling_that_mirrors_correctly_has_no_finding(self):
        good = json.dumps(
            {
                "ruling": {
                    "ruling": "DRIVER_COMPENSATION", "amount_sgd": 6.40,
                    "driver_compensation_sgd": 6.40, "referrals": [], "confidence": 0.8,
                    "explanation": "x",
                },
                "discarded_claims": [],
            }
        )
        result = self.run_with_ruling(good)
        self.assertEqual(result.ruling_findings, [])

    def test_extra_top_level_fields_are_recorded(self):
        bad = json.dumps(
            {
                "ruling": {
                    "ruling": "NO_ACTION", "amount_sgd": None, "driver_compensation_sgd": None,
                    "referrals": [], "confidence": 0.9, "explanation": "x",
                },
                "discarded_claims": [],
                "notes": "an extra field the contract does not allow",
            }
        )
        result = self.run_with_ruling(bad)
        names = [finding["invariant"] for finding in result.ruling_findings]
        self.assertIn("exactly_two_top_level_fields", names)
        self.assertIn("notes", result.ruling)

    def test_an_unknown_ruling_value_is_recorded(self):
        bad = json.dumps(
            {
                "ruling": {
                    "ruling": "ALLOW", "amount_sgd": None, "driver_compensation_sgd": None,
                    "referrals": [], "confidence": 0.9, "explanation": "x",
                },
                "discarded_claims": [],
            }
        )
        result = self.run_with_ruling(bad)
        names = [finding["invariant"] for finding in result.ruling_findings]
        self.assertIn("ruling_value_is_known", names)
        self.assertEqual(result.ruling["ruling"]["ruling"], "ALLOW")

    def test_a_ruling_missing_a_pol_gen_03_field_is_recorded(self):
        bad = json.dumps(
            {
                "ruling": {"ruling": "NO_ACTION", "referrals": [], "confidence": 0.9,
                           "explanation": "x"},
                "discarded_claims": [],
            }
        )
        result = self.run_with_ruling(bad)
        names = [finding["invariant"] for finding in result.ruling_findings]
        self.assertIn("six_pol_gen_03_fields", names)


class TranscriptAndSecretTests(unittest.TestCase):
    """The record the track requires, and what it must not contain."""

    def test_the_transcript_is_deterministic_with_the_clock_pinned(self):
        first = run(envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(GOOD_RULING))
        second = run(envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(GOOD_RULING))
        self.assertEqual(first.transcript_json, second.transcript_json)
        self.assertEqual(first.transcript_sha256, second.transcript_sha256)

    def test_the_transcript_digests_the_brief_instead_of_inlining_it(self):
        """The brief is large; inlining it three times would be unreadable."""
        result = run(envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(GOOD_RULING))
        brief_json = money.dumps_canonical(brief.build_brief(CASE))

        self.assertGreater(len(brief_json), 10000)
        self.assertNotIn(brief_json, result.transcript_json)
        # the brief's digest is on the record, once per advocate
        digests = [entry.user_sha256 for entry in result.transcript.entries]
        self.assertEqual(digests[0], result.brief_sha256)
        self.assertEqual(digests[1], result.brief_sha256)
        self.assertLess(len(result.transcript_json), len(brief_json))

    def test_no_api_key_reaches_the_result_or_the_transcript(self):
        result = run(envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(GOOD_RULING))
        text = result.transcript_json + repr(result) + str(result.ruling)
        self.assertNotIn(FAKE_KEY, text)
        self.assertNotIn("sk-", text)

    def test_the_transcript_carries_every_call_including_the_failed_ones(self):
        transport = FakeTransport(envelope('{"claims": []}'), envelope('{"claims": []}'))
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)
        text = result.transcript_json
        parsed = json.loads(text)

        self.assertEqual(len(parsed["entries"]), 2)
        for entry in parsed["entries"]:
            self.assertEqual(entry["response_text"], '{"claims": []}')
            self.assertIsNotNone(entry["note"])
        self.assertNotIn(FAKE_KEY, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
