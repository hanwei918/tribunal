"""Tests for ``tribunal.pipeline``.

No network: ``LLMClient`` is driven through its injected transport with recorded
response bodies. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import hashlib
import io
import json
import re
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


def worked_example(filename: str, prompts_dir: Path = pipeline.PROMPTS_DIR):
    """The one worked JSON example a prompt ships, parsed.

    A prompt's example is the shape it asks for, stated in the form a model is
    most likely to copy verbatim. Parsing it is what makes the prompt's request
    checkable without reading its prose, and requiring exactly one keeps the
    question "which example is the contract" from having two answers.
    """
    text = (Path(prompts_dir) / filename).read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, re.S)
    if len(blocks) != 1:
        raise AssertionError(
            "{0} must carry exactly one ```json example of what the agent returns; "
            "found {1}".format(filename, len(blocks))
        )
    return json.loads(blocks[0])


class PromptContractTests(unittest.TestCase):
    """The shape a prompt asks for must be one the request can produce.

    A prompt that asks for a bare JSON array while the request carries
    ``response_format: json_object`` states a contract no model can satisfy. The
    API-level constraint wins, every answer is rejected as the wrong shape, and
    the failures look like a model problem: they were recorded as SHAPE failures
    against the advocate, twice per case, and a paid benchmark run was spent
    before anyone read what the models had actually returned. These tests are
    the check whose absence let that happen.
    """

    def test_every_agent_is_sent_a_format_this_module_declares(self):
        for role in (RIDER, DRIVER, JUDGE):
            with self.subTest(role=role):
                self.assertIn(role, pipeline.AGENT_RESPONSE_FORMAT)
                self.assertIn(role, pipeline.AGENT_PROMPT_FILES)
                fmt = pipeline.AGENT_RESPONSE_FORMAT[role]["type"]
                self.assertIn(
                    fmt,
                    pipeline.RESPONSE_FORMAT_SHAPES,
                    "the format sent to {0} has no declared top-level shape".format(role),
                )

    def test_json_object_permits_an_object_and_nothing_else(self):
        """A guard on the guard: if this widens, the checks below stop meaning anything."""
        self.assertEqual(
            pipeline.RESPONSE_FORMAT_SHAPES["json_object"], (pipeline.SHAPE_OBJECT,)
        )

    def test_the_worked_example_matches_the_shape_the_request_permits(self):
        """The primary check, and it is structural: the prompt's own example is parsed."""
        for role, filename in pipeline.AGENT_PROMPT_FILES.items():
            with self.subTest(role=role):
                example = worked_example(filename)
                asked = pipeline.json_shape(example)
                permitted = pipeline.RESPONSE_FORMAT_SHAPES[
                    pipeline.AGENT_RESPONSE_FORMAT[role]["type"]
                ]
                self.assertIn(
                    asked,
                    permitted,
                    "{0}'s prompt asks for the shape {1!r} while its request forces "
                    "{2!r}".format(role, asked, pipeline.AGENT_RESPONSE_FORMAT[role]["type"]),
                )

    def test_the_pipeline_accepts_the_example_its_own_prompt_ships(self):
        """Prompt and validator cannot disagree either.

        The example is a fixture here, not documentation: if what the prompt
        tells the model to copy is something the validator refuses, the two have
        drifted and every model that obeys the prompt fails.
        """
        for role in (RIDER, DRIVER):
            with self.subTest(role=role):
                example = worked_example(pipeline.AGENT_PROMPT_FILES[role])
                claims, shape, reason = pipeline.normalise_claims(example)
                self.assertEqual(reason, "", "the validator refuses the prompt's own example")
                self.assertEqual(shape, pipeline.SHAPE_OBJECT)
                self.assertTrue(claims, "the example carries no claims")

        example = worked_example(pipeline.AGENT_PROMPT_FILES[JUDGE])
        value, shape, reason = pipeline.normalise_judge_result(example)
        self.assertEqual(reason, "", "the validator refuses the judge prompt's own example")
        self.assertEqual(shape, pipeline.SHAPE_OBJECT)
        self.assertIsNotNone(value)

    def test_the_advocate_example_uses_the_key_the_validator_reads(self):
        example = worked_example(pipeline.AGENT_PROMPT_FILES[RIDER])
        self.assertIn(pipeline.ADVOCATE_CLAIMS_KEY, example)

    def test_no_prompt_asks_for_a_json_array_under_json_object(self):
        """A text check, and the only one in this file.

        Everything above asserts on parsed structure. This one cannot: the thing
        under test is prose, and there is no structural way to ask what a
        paragraph instructs a model to do. So it is kept as narrow as it can be —
        it looks for the phrase "JSON array" in a prompt whose request forces an
        object, which is the exact instruction that was wrong.

        It is a backstop, not the guard. A prompt that asked for an array in
        other words but shipped an array example is caught above by the example
        check. A prompt that asked for an array in other words and shipped an
        object example would be contradicting itself, and no test settles that
        for a model.
        """
        for role, filename in pipeline.AGENT_PROMPT_FILES.items():
            with self.subTest(role=role):
                text = (pipeline.PROMPTS_DIR / filename).read_text(encoding="utf-8")
                self.assertNotIn(
                    "json array",
                    text.lower(),
                    "{0}'s prompt asks for a JSON array while its request forces an "
                    "object".format(role),
                )

    def test_the_format_check_catches_the_prompt_that_was_actually_shipped(self):
        """Falsifiability, on the real thing rather than an invented one.

        The prompt this project shipped until 2026-09-22 is reconstructed here,
        and the format check must reject it. Note what does *not* reject it: the
        validator accepts a bare array, because that is one of the two shapes a
        model is allowed to answer with. Tolerating the array in the validator
        does not make a prompt that asks for one consistent with a request that
        forces an object, and only the format check sees the difference.
        """
        shipped = (
            "## What you return\n\n"
            "A JSON array of claim objects. Each claim is one point.\n\n"
            "```json\n[{\"text\": \"x\", \"evidence_ids\": [\"EV-1\"]}]\n```\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / pipeline.ADVOCATE_TEMPLATE).write_text(shipped, encoding="utf-8")
            example = worked_example(pipeline.ADVOCATE_TEMPLATE, base)

        asked = pipeline.json_shape(example)
        permitted = pipeline.RESPONSE_FORMAT_SHAPES["json_object"]

        self.assertEqual(asked, pipeline.SHAPE_ARRAY)
        self.assertNotIn(asked, permitted, "the format check failed to catch it")
        # ...and the validator is deliberately blind to this, which is why the
        # format check has to exist.
        claims, _shape, _reason = pipeline.normalise_claims(example)
        self.assertIsNotNone(claims, "a bare array is still an accepted shape")

    def test_a_prompt_with_two_examples_is_refused_rather_than_guessed_at(self):
        """With two examples, "which shape is asked for" has no single answer."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / pipeline.ADVOCATE_TEMPLATE).write_text(
                '```json\n{"claims": []}\n```\n\n```json\n[]\n```\n', encoding="utf-8"
            )
            with self.assertRaises(AssertionError):
                worked_example(pipeline.ADVOCATE_TEMPLATE, base)


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
    """A model that answers with the wrong shape is retried once, then reported.

    Two shapes are *usable* for an advocate — an object carrying ``claims``, and
    a bare array — so a wrong shape here means something genuinely unusable: an
    object with no ``claims`` key, a ``claims`` value that is not an array, a
    claim that is not an object, or a body that never parsed at all.
    """

    def test_an_object_carrying_claims_is_accepted_without_a_retry(self):
        """The shape the prompt asks for, and the one ``json_object`` can produce.

        This is the case the defect turned into a failure: the hy4-preview driver
        advocate on case 207 returned eleven claims, every one of them cited and
        every clause id well formed, inside exactly this wrapper, and the run
        discarded them for the wrapper.
        """
        transport = FakeTransport(
            envelope('{"claims": ' + RIDER_CLAIMS + "}"),
            envelope(DRIVER_CLAIMS),
            envelope(GOOD_RULING),
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertTrue(result.ok)
        self.assertEqual(roles_of(result), [RIDER, DRIVER, JUDGE])
        self.assertIsNone(result.transcript.entries[0].note, "the object shape was retried")
        self.assertEqual(result.transcript.entries[0].shape, pipeline.SHAPE_OBJECT)

    def test_a_bare_array_is_accepted_too(self):
        """A model that returns the array directly has answered the question."""
        result = run(envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS), envelope(GOOD_RULING))

        self.assertTrue(result.ok)
        self.assertEqual(roles_of(result), [RIDER, DRIVER, JUDGE])
        self.assertEqual(result.transcript.entries[0].shape, pipeline.SHAPE_ARRAY)
        self.assertIsNone(result.transcript.entries[0].note)

    def test_the_wrapper_is_unwrapped_before_the_judge_sees_it(self):
        """Normalising is not cosmetic: the judge gets the claims, not the wrapper."""
        transport = FakeTransport(
            envelope('{"claims": ' + RIDER_CLAIMS + "}"),
            envelope(DRIVER_CLAIMS),
            envelope(GOOD_RULING),
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        judge_user = json.loads(
            json.loads(transport.calls[2]["body"].decode("utf-8"))["messages"][1]["content"]
        )
        self.assertEqual(judge_user["claims"][RIDER], json.loads(RIDER_CLAIMS))

    def test_an_object_with_no_claims_key_is_retried_once_then_fails(self):
        transport = FakeTransport(
            envelope('{"arguments": []}'), envelope('{"arguments": []}')
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertFalse(result.ok)
        self.assertEqual(result.failed_agent, RIDER)
        self.assertIn("claims", result.failure_reason)
        self.assertEqual(roles_of(result), [RIDER, RIDER])
        self.assertEqual(result.transcript.entries[0].shape, pipeline.SHAPE_OBJECT)

    def test_the_shape_is_recorded_per_attempt_so_a_switch_is_visible(self):
        """A model can answer with one shape and the other on the retry.

        Recorded per attempt rather than per case, because "which shape does this
        model choose" is the question, and a per-case field would average the two
        answers into one.
        """
        transport = FakeTransport(
            envelope('{"claims": {}}'),
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(GOOD_RULING),
        )
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        shapes = [entry.shape for entry in result.transcript.entries]
        self.assertEqual(shapes[0], pipeline.SHAPE_OBJECT)
        self.assertEqual(shapes[1], pipeline.SHAPE_ARRAY)
        self.assertTrue(result.ok, "the retry was accepted")

    def test_an_advocate_failing_twice_gives_a_failed_result_not_an_exception(self):
        bad = '{"claims": "not an array"}'
        transport = FakeTransport(envelope(bad), envelope(bad))
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertFalse(result.ok)
        self.assertEqual(result.failed_agent, RIDER)
        self.assertIn("not a JSON array", result.failure_reason)
        self.assertIsNone(result.ruling)
        # the run stopped at the failure: no driver call, no judge call
        self.assertEqual(roles_of(result), [RIDER, RIDER])
        self.assertEqual(len(transport.calls), 2)
        # both raw bodies preserved, and no empty claim list was substituted
        self.assertEqual(result.transcript.entries[0].response_text, bad)
        self.assertEqual(result.transcript.entries[1].response_text, bad)

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


class ClaimShapeTests(unittest.TestCase):
    """The advocate normaliser: two accepted shapes in, one list of claims out.

    Tested directly rather than only through a run, because the interesting cases
    are the refusals — and a refusal that says the wrong thing sends the next
    reader looking in the wrong place, which is how the wrapper came to be read
    as a model failure in the first place.
    """

    CLAIMS = [{"text": "a point", "evidence_ids": ["EV-1"], "clause_ids": ["POL-NS-01"]}]

    def test_an_object_carrying_claims_normalises_to_the_array(self):
        claims, shape, reason = pipeline.normalise_claims({"claims": self.CLAIMS})
        self.assertEqual(claims, self.CLAIMS)
        self.assertEqual(shape, pipeline.SHAPE_OBJECT)
        self.assertEqual(reason, "")

    def test_a_bare_array_normalises_to_itself(self):
        claims, shape, reason = pipeline.normalise_claims(self.CLAIMS)
        self.assertEqual(claims, self.CLAIMS)
        self.assertEqual(shape, pipeline.SHAPE_ARRAY)
        self.assertEqual(reason, "")

    def test_an_empty_claim_array_is_a_usable_answer(self):
        """Zero claims is a poor answer, but it is an answer and not a wrong shape."""
        for value in ([], {"claims": []}):
            with self.subTest(value=value):
                claims, _shape, reason = pipeline.normalise_claims(value)
                self.assertEqual(claims, [])
                self.assertEqual(reason, "")

    def test_extra_keys_beside_claims_are_tolerated_rather_than_policed(self):
        """The prompt states "exactly one key"; the validator does not enforce it.

        Enforcing one contract in two places is how the two places come to
        disagree, and that is the defect this change exists to fix. The raw body
        is on the transcript in full, so a stray key is still visible to a reader
        without the validator having to be the thing that catches it.
        """
        claims, shape, reason = pipeline.normalise_claims(
            {"claims": self.CLAIMS, "notes": "an extra key"}
        )
        self.assertEqual(claims, self.CLAIMS)
        self.assertEqual(shape, pipeline.SHAPE_OBJECT)
        self.assertEqual(reason, "")

    def test_an_object_with_no_claims_key_is_refused_and_says_so(self):
        claims, shape, reason = pipeline.normalise_claims({"arguments": self.CLAIMS})
        self.assertIsNone(claims)
        self.assertEqual(shape, pipeline.SHAPE_OBJECT)
        self.assertIn("claims", reason)

    def test_a_claims_value_that_is_not_an_array_is_refused(self):
        claims, _shape, reason = pipeline.normalise_claims({"claims": "a string"})
        self.assertIsNone(claims)
        self.assertIn("not a JSON array", reason)

    def test_a_claim_that_is_not_an_object_is_refused(self):
        claims, _shape, reason = pipeline.normalise_claims([{"text": "fine"}, "not an object"])
        self.assertIsNone(claims)
        self.assertIn("claim 1", reason)

    def test_a_body_that_never_parsed_is_neither_shape(self):
        """A malformed body is its own outcome, not a wrong wrapper.

        Folding it into one of the two shapes would make a model that returned
        nonsense indistinguishable in the record from a model that returned a
        well-formed answer in the other wrapper.
        """
        claims, shape, reason = pipeline.normalise_claims(None)
        self.assertIsNone(claims)
        self.assertEqual(shape, "NoneType")
        self.assertNotIn(shape, (pipeline.SHAPE_OBJECT, pipeline.SHAPE_ARRAY))
        self.assertIn("NoneType", reason)

    def test_the_judge_normaliser_names_the_object_shape(self):
        value, shape, reason = pipeline.normalise_judge_result(
            {"ruling": {"ruling": "NO_ACTION"}, "discarded_claims": []}
        )
        self.assertIsNotNone(value)
        self.assertEqual(shape, pipeline.SHAPE_OBJECT)
        self.assertEqual(reason, "")

    def test_the_judge_normaliser_still_requires_both_fields(self):
        """The judge's contract is unchanged by this fix, and still enforced."""
        value, _shape, reason = pipeline.normalise_judge_result({"ruling": {}})
        self.assertIsNone(value)
        self.assertIn("discarded_claims", reason)


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
        bad = '{"claims": "not an array"}'
        transport = FakeTransport(envelope(bad), envelope(bad))
        client = llm.LLMClient(
            model="hy4-preview", api_key=FAKE_KEY, transport=transport,
            sleep=lambda seconds: None, clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)
        text = result.transcript_json
        parsed = json.loads(text)

        self.assertEqual(len(parsed["entries"]), 2)
        for entry in parsed["entries"]:
            self.assertEqual(entry["response_text"], bad)
            self.assertIsNotNone(entry["note"])
            self.assertEqual(entry["shape"], pipeline.SHAPE_OBJECT)
        self.assertNotIn(FAKE_KEY, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
