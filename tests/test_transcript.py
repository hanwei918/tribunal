"""Tests for ``tribunal.transcript``.

No network. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import llm, transcript as transcript_module  # noqa: E402

# The same canary technique test_llm.py uses.
FAKE_KEY = "tok-live-FAKEKEY-0123456789abcdef-DO-NOT-LEAK"
PINNED_NOW = "2026-09-21T12:00:00+00:00"

RIDER = transcript_module.ROLE_RIDER_ADVOCATE
DRIVER = transcript_module.ROLE_DRIVER_ADVOCATE
JUDGE = transcript_module.ROLE_JUDGE


def pinned():
    return transcript_module.Transcript(now=lambda: PINNED_NOW)


class TranscriptShapeTests(unittest.TestCase):
    """One entry per call, in order, with the fields the track requires."""

    def test_one_entry_per_call_in_order(self):
        record = pinned()
        record.add(
            role=RIDER, model="m", system_prompt="sys", user_message="brief",
            response_text="[]", parsed=[], parse_outcome="PARSED",
        )
        record.add(
            role=DRIVER, model="m", system_prompt="sys", user_message="brief",
            response_text="[]", parsed=[], parse_outcome="PARSED",
        )
        record.add(
            role=JUDGE, model="m", system_prompt="judge", user_message="payload",
            response_text="{}", parsed={}, parse_outcome="PARSED",
        )

        self.assertEqual([entry.role for entry in record.entries], [RIDER, DRIVER, JUDGE])
        self.assertEqual(len(record), 3)

    def test_every_required_field_is_present(self):
        record = pinned()
        entry = record.add(
            role=RIDER, model="hy4-preview", system_prompt="sys", user_message="brief",
            response_text="[]", parsed=[], parse_outcome="PARSED",
            prompt_tokens=11, completion_tokens=2, reasoning_tokens=1, cached_tokens=0,
            duration_seconds=1.5, attempts=2, status=200,
        )
        self.assertEqual(entry.role, RIDER)
        self.assertEqual(entry.system_sha256, transcript_module.sha256_text("sys"))
        self.assertEqual(entry.user_sha256, transcript_module.sha256_text("brief"))
        self.assertEqual(entry.response_text, "[]")
        self.assertEqual(entry.parsed, [])
        self.assertEqual(entry.prompt_tokens, 11)
        self.assertEqual(entry.completion_tokens, 2)
        self.assertEqual(entry.reasoning_tokens, 1)
        self.assertEqual(entry.cached_tokens, 0)
        self.assertEqual(entry.duration_seconds, 1.5)
        self.assertEqual(entry.attempts, 2)
        self.assertEqual(entry.status, 200)
        self.assertEqual(entry.timestamp, PINNED_NOW)

    def test_the_prompts_are_digested_and_never_inlined(self):
        """A transcript that inlines the brief three times is unreadable."""
        brief_text = "BRIEFMARKER" + ("x" * 40000)
        record = pinned()
        entry = record.add(
            role=RIDER, model="m", system_prompt=brief_text, user_message=brief_text,
            response_text="[]", parsed=[], parse_outcome="PARSED",
        )
        self.assertEqual(entry.system_sha256, transcript_module.sha256_text(brief_text))
        self.assertEqual(entry.user_sha256, transcript_module.sha256_text(brief_text))
        self.assertNotIn("BRIEFMARKER", record.to_json())
        self.assertEqual(len(entry.system_sha256), 64)

    def test_the_response_text_is_kept_in_full(self):
        answer = '{"ruling": {"ruling": "NO_ACTION"}}'
        record = pinned()
        entry = record.add(
            role=JUDGE, model="m", system_prompt="sys", user_message="payload",
            response_text=answer, parsed={"ruling": {"ruling": "NO_ACTION"}},
            parse_outcome="PARSED",
        )
        self.assertEqual(entry.response_text, answer)
        self.assertIn("NO_ACTION", record.to_json())

    def test_totals_sum_every_entry(self):
        record = pinned()
        for role in (RIDER, DRIVER, JUDGE):
            record.add(
                role=role, model="m", system_prompt="s", user_message="u", response_text="[]",
                parsed=[], parse_outcome="PARSED", prompt_tokens=10, completion_tokens=5,
                reasoning_tokens=3, cached_tokens=1, duration_seconds=2.0,
            )
        totals = record.totals()
        self.assertEqual(totals["calls"], 3)
        self.assertEqual(totals["prompt_tokens"], 30)
        self.assertEqual(totals["completion_tokens"], 15)
        self.assertEqual(totals["reasoning_tokens"], 9)
        self.assertEqual(totals["cached_tokens"], 3)
        self.assertAlmostEqual(totals["duration_seconds"], 6.0)

    def test_record_from_an_llm_result(self):
        result = llm.LLMResult(
            text="[]", json_body=[], envelope=None, parse_outcome="PARSED", parse_error=None,
            prompt_tokens=7, completion_tokens=3, reasoning_tokens=2, cached_tokens=0,
            status=200, duration_seconds=0.5, model="hy4-preview", attempts=1,
            request_sha256="0" * 64,
        )
        record = pinned()
        entry = record.record(role=RIDER, system_prompt="s", user_message="u", result=result)
        self.assertEqual(entry.response_text, "[]")
        self.assertEqual(entry.prompt_tokens, 7)
        self.assertEqual(entry.completion_tokens, 3)
        self.assertEqual(entry.attempts, 1)


class TranscriptSerialisationTests(unittest.TestCase):
    """Determinism, and the settings this package already uses."""

    def build(self):
        record = pinned()
        record.add(
            role=RIDER, model="m", system_prompt="s", user_message="u", response_text="[]",
            parsed=[], parse_outcome="PARSED", prompt_tokens=1,
        )
        record.add(
            role=JUDGE, model="m", system_prompt="s", user_message="u", response_text="{}",
            parsed={"a": 1, "b": [True, None, "x"]}, parse_outcome="PARSED",
        )
        return record

    def test_the_same_transcript_serialises_to_the_same_bytes(self):
        first = self.build().to_json()
        second = self.build().to_json()
        self.assertEqual(first, second)
        self.assertEqual(self.build().sha256(), self.build().sha256())
        self.assertEqual(len(self.build().sha256()), 64)

    def test_serialisation_uses_the_package_settings(self):
        """ensure_ascii=False, sort_keys=True, separators=(",", ":")."""
        text = self.build().to_json()
        self.assertNotIn(": ", text)
        self.assertIn('"entries":[', text)
        self.assertNotIn("\\u", text)

    def test_a_decimal_in_a_parsed_value_is_written_as_a_number(self):
        from decimal import Decimal

        record = pinned()
        record.add(
            role=JUDGE, model="m", system_prompt="s", user_message="u", response_text="{}",
            parsed={"amount_sgd": Decimal("8.0")}, parse_outcome="PARSED",
        )
        text = record.to_json()
        self.assertIn('"amount_sgd":8.0', text)
        self.assertNotIn('"amount_sgd":"8.0"', text)
        self.assertEqual(json.loads(text, parse_float=Decimal)["entries"][0]["parsed"]["amount_sgd"],
                         Decimal("8.0"))

    def test_the_timestamp_is_the_only_thing_that_moves(self):
        """With the clock pinned, two runs of the same calls are byte-identical."""
        first = pinned().add(
            role=RIDER, model="m", system_prompt="s", user_message="u", response_text="[]",
            parsed=[], parse_outcome="PARSED",
        )
        second = pinned().add(
            role=RIDER, model="m", system_prompt="s", user_message="u", response_text="[]",
            parsed=[], parse_outcome="PARSED",
        )
        self.assertEqual(first.as_dict(), second.as_dict())


class TranscriptSecretHygieneTests(unittest.TestCase):
    """Requirement: a transcript must contain no API key."""

    @staticmethod
    def envelope(answer):
        return json.dumps(
            {
                "choices": [{"message": {"content": answer}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            }
        ).encode("utf-8")

    class FakeTransport:
        def __init__(self, *responses):
            self.responses = list(responses)
            self.calls = []

        def __call__(self, url, headers, body, timeout):
            self.calls.append({"url": url, "headers": dict(headers), "body": body})
            nxt = self.responses.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt

    def test_no_api_key_ever_reaches_the_transcript(self):
        """The canary technique test_llm.py uses, applied to the record."""
        transport = self.FakeTransport(
            llm.HttpResult(200, self.envelope("[]")),
            llm.HttpResult(200, self.envelope("[]")),
            llm.HttpResult(200, self.envelope('{"ruling": {"ruling": "NO_ACTION"}, "discarded_claims": []}')),
            llm.HttpResult(200, self.envelope("not json at all")),
            llm.HttpResult(402, b'{"error":{"code":"401006"}}'),
            llm.HttpResult(429, b""),
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0, max_attempts=2,
        )
        record = transcript_module.Transcript(now=lambda: PINNED_NOW)

        def drive(role, call):
            try:
                result = call()
            except Exception as exc:  # noqa: BLE001 - every path is being checked
                record.add(
                    role=role, model="hy4-preview", system_prompt="s", user_message="u",
                    response_text="raised: {0}".format(exc), parsed=None, parse_outcome="ERROR",
                    note=str(exc),
                )
                return
            record.record(role=role, system_prompt="s", user_message="u", result=result)

        drive(RIDER, lambda: client.complete("s", "u", response_format=llm.JSON_OBJECT_FORMAT))
        drive(DRIVER, lambda: client.complete("s", "u", response_format=llm.JSON_OBJECT_FORMAT))
        drive(JUDGE, lambda: client.complete("s", "u", response_format=llm.JSON_OBJECT_FORMAT))
        drive(JUDGE, lambda: client.complete("s", "u", response_format=llm.JSON_OBJECT_FORMAT))
        drive(JUDGE, lambda: client.complete("s", "u", response_format=llm.JSON_OBJECT_FORMAT))
        drive(JUDGE, lambda: client.complete("s", "u", response_format=llm.JSON_OBJECT_FORMAT))

        text = record.to_json()
        self.assertNotIn(FAKE_KEY, text)
        self.assertNotIn("sk-", text)
        # The record really did capture the calls, including the failures.
        self.assertGreaterEqual(len(record), 6)
        self.assertTrue(any(entry.note for entry in record.entries))
        # And the wire still carried the credential, which is the one place it belongs.
        self.assertEqual(transport.calls[0]["headers"]["Authorization"], "Bearer " + FAKE_KEY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
