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
        """A text check, and one of only two in this file.

        Everything above asserts on parsed structure. This one cannot: the thing
        under test is prose, and there is no structural way to ask what a
        paragraph instructs a model to do. So it is kept as narrow as it can be —
        it looks for the phrase "JSON array" in a prompt whose request forces an
        object, which is the exact instruction that was wrong. The other text
        check, ``DecidingFactCarrierTests``, cannot assert on structure for the
        same reason, and is confined to one subsection for the same narrowness.

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


# --------------------------------------------------------------------------
# What can carry a deciding fact
# --------------------------------------------------------------------------
JUDGE_PROMPT_FILE = pipeline.AGENT_PROMPT_FILES[JUDGE]

# The Step 2 subsection that says what kind of artifact can carry a fact, and the
# sentence that ends it. Both are read out of the prompt rather than assumed, so
# a reordering shows up as a failure rather than as a check that stopped looking.
_CARRIER_HEADING = "### What can carry a deciding fact"
_CARRIER_ENDS_AT = "The escalation floor is the"


def carrier_section(text=None):
    """The Step 2 subsection, from its heading up to the escalation floor."""
    if text is None:
        text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
    start = text.index(_CARRIER_HEADING)
    return text[start : text.index(_CARRIER_ENDS_AT, start)]


class DecidingFactCarrierTests(unittest.TestCase):
    """Step 2 must say what kind of artifact can carry a deciding fact.

    A text check, and one of only two in this file, for the same reason as the
    other: what is under test is prose that instructs a model, and there is no
    structural way to ask what a paragraph tells a model to do. It is kept to the
    one subsection, so a sentence elsewhere in the prompt cannot satisfy it.

    Step 2 stated the MINIMUM and MAXIMUM rules but never said what could carry a
    fact, and a real run shows the judge reading that as instrument evidence
    only — GPS traces, trip records, fare breakdowns — excluding what the parties
    said. It cost two cases. Case 211 capped on an impaired trace alone and
    escalated at 0.39 where a complete chat artifact at weight 1.00 carried the
    fact and cleared the floor; case 107 escalated at 0.30 with two independent
    admissions in the record and nothing else to look at.

    The other direction is the harder one to test and the one that matters more.
    Loosening Step 2 carelessly trades the safe failure — over-escalation — for
    the dangerous one: a confident ruling on a fact that nothing independent
    supports. So the removal test that bounds the principle is required, the
    independence rule is required to survive, and the prompt is required *not*
    to become a list of cases to match against.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
        cls.section = carrier_section(cls.text)

    def test_step_two_carries_the_subsection_at_all(self):
        self.assertIn(_CARRIER_HEADING, self.text)

    def test_every_artifact_is_a_candidate_carrier_not_only_the_instruments(self):
        self.assertIn("case.evidence", self.section)
        self.assertIn("chat log", self.section)
        self.assertIn("counterparty", self.section)

    def test_the_admission_against_the_speakers_own_interest_is_stated(self):
        self.assertIn("against the speaker's own interest", self.section)

    def test_the_contemporaneous_record_from_inside_the_window_is_stated(self):
        self.assertIn("from inside the disputed window", self.section)

    def test_a_message_that_merely_exists_is_not_a_carrier(self):
        self.assertIn("merely exists", self.section)
        self.assertIn("only repeats what the", self.section)

    def test_the_removal_test_bounds_the_principle(self):
        """Without this sentence the subsection licenses counting any message."""
        self.assertIn(
            "would still support the finding if the instrument", self.section
        )

    def test_the_independence_rule_survives_unchanged(self):
        """Two records from one measurement are one carrier, however they arrive."""
        self.assertIn("derived from the same", self.section)
        self.assertIn("one carrier, not two", self.section)
        self.assertIn("trip record and a fare", self.section)

    def test_the_patterns_are_stated_as_illustrations_and_not_a_list(self):
        self.assertIn("illustrations of one principle", self.section)
        self.assertIn("not a list to match against", self.section)

    def test_the_prompt_does_not_name_the_two_cases_it_was_written_for(self):
        """A prompt that listed them would be a checklist rather than a principle.

        The cases are what produced the change; they are not the rule. A model
        handed the case numbers would match on those and stop, and the next case
        shaped like them would escalate exactly as before.
        """
        for case_no in ("211", "107"):
            with self.subTest(case=case_no):
                self.assertNotIn(case_no, self.section)
        # And no floor: it is read from the policy, never restated in a prompt.
        self.assertNotIn("0.70", self.section)

    def test_the_amended_prompt_keeps_the_output_contract(self):
        """Change 1 edits prose; it must not disturb the shape the prompt asks for."""
        example = worked_example(JUDGE_PROMPT_FILE)
        self.assertIn(
            pipeline.json_shape(example),
            pipeline.RESPONSE_FORMAT_SHAPES[
                pipeline.AGENT_RESPONSE_FORMAT[JUDGE]["type"]
            ],
        )
        value, shape, reason = pipeline.normalise_judge_result(example)
        self.assertEqual("", reason, "the validator refuses the amended prompt's example")
        self.assertEqual(pipeline.SHAPE_OBJECT, shape)
        self.assertIsNotNone(value)

    def test_the_prompt_contract_holds_for_every_agent_after_the_edit(self):
        """Stated here as well as in ``PromptContractTests``, because this edit is
        the reason to look: a prose change to one prompt must leave every agent's
        declared shape and its shipped example in agreement."""
        for role, filename in pipeline.AGENT_PROMPT_FILES.items():
            with self.subTest(role=role):
                example = worked_example(filename)
                self.assertIn(
                    pipeline.json_shape(example),
                    pipeline.RESPONSE_FORMAT_SHAPES[
                        pipeline.AGENT_RESPONSE_FORMAT[role]["type"]
                    ],
                )


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


class VirtualClock:
    """A clock that only moves when a call spends time.

    The pipeline reads it before each agent call and the client reads it for the
    call's own duration, so one clock serves both. Advancing it inside the
    transport is what makes a case "take" minutes without the test waiting for
    them.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def spend(self, seconds: float) -> None:
        self.now += seconds


class SpendingTransport:
    """A transport that spends wall time on each call, then answers.

    It exists so a case can be driven past its deadline in virtual time. Every
    request is recorded, which is how a test shows that a call the deadline had
    no room for was never made.
    """

    def __init__(self, clock: VirtualClock, per_call_seconds: float, *responses) -> None:
        self.clock = clock
        self.per_call_seconds = per_call_seconds
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": body})
        self.clock.spend(self.per_call_seconds)
        if not self.responses:
            raise AssertionError("SpendingTransport ran out of scripted responses")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def client_on(clock: VirtualClock, transport) -> llm.LLMClient:
    """A client wired to the same clock as the case, so both see one timeline."""
    return llm.LLMClient(
        model="hy4-preview",
        api_key=FAKE_KEY,
        transport=transport,
        sleep=lambda seconds: None,
        clock=clock,
    )


class CaseDeadlineTests(unittest.TestCase):
    """The bound on one whole case: three agent calls and any shape retry.

    The client's own deadline bounds one call. Nothing bounded the case, and on
    2026-09-22 that is exactly what happened: a run wrote its last case at 07:25
    and was still alive at 09:13 with no output, 1 h 48 m with nothing on the
    terminal, while the provider answered a direct probe in 0.95 s. These tests
    drive the case through an injected clock, so the budget is spent without
    anything waiting.
    """

    DEADLINE_SECONDS = 100.0
    PER_CALL_SECONDS = 60.0

    def case_over(self, per_call_seconds, *responses, deadline=None):
        clock = VirtualClock()
        transport = SpendingTransport(clock, per_call_seconds, *responses)
        kwargs = {}
        if deadline is not None:
            kwargs["case_deadline_seconds"] = deadline
        return transport, lambda: pipeline.run_case(
            CASE,
            client_on(clock, transport),
            now=lambda: PINNED_NOW,
            clock=clock,
            **kwargs
        )

    def test_a_spent_budget_stops_the_case_before_the_call_it_cannot_finish(self):
        """The third call is never made, though the case is not yet over.

        Two 60-second calls inside a 100-second budget leave 40 s, so the judge
        call cannot finish. Refusing it here is what makes the deadline a
        deadline rather than a post-mortem: an after-the-fact check would have
        made the third call and only noticed when it was done.
        """
        transport, run = self.case_over(
            self.PER_CALL_SECONDS,
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(GOOD_RULING),
            deadline=self.DEADLINE_SECONDS,
        )

        with self.assertRaises(pipeline.CaseDeadlineExceeded) as caught:
            run()

        self.assertEqual(2, len(transport.calls), "the judge call must not start")
        self.assertEqual(2 * self.PER_CALL_SECONDS, caught.exception.elapsed_seconds)
        self.assertEqual(CASE, caught.exception.case_no)
        self.assertIsInstance(caught.exception, pipeline.PipelineError)
        self.assertNotIsInstance(caught.exception, TimeoutError)
        # Named, with the elapsed time, so the record carries the figure the
        # limit was measured against and not only the limit.
        self.assertIn(str(CASE), str(caught.exception))
        self.assertIn("100", str(caught.exception))

    def test_the_shape_retry_is_inside_the_budget_too(self):
        """An unusable answer is retried, but not with time the case does not have.

        The rider's first answer is unusable, so the retry would normally be
        made. The budget is exactly one call, so the retry is refused — and the
        transport shows it was never sent.
        """
        transport, run = self.case_over(
            self.PER_CALL_SECONDS,
            envelope('{"no_claims_key": []}'),
            envelope(RIDER_CLAIMS),
            deadline=self.PER_CALL_SECONDS,
        )

        with self.assertRaises(pipeline.CaseDeadlineExceeded):
            run()

        self.assertEqual(1, len(transport.calls), "the retry must not be sent")

    def test_an_unusable_answer_within_the_budget_is_still_a_failed_result(self):
        """The contrast: without a spent budget the same script does not raise.

        A deadline is not a rename of "the model answered badly". The two are
        different events, so the one must not be reported as the other.
        """
        transport, run = self.case_over(
            self.PER_CALL_SECONDS,
            envelope('{"no_claims_key": []}'),
            envelope('{"no_claims_key": []}'),
            deadline=self.DEADLINE_SECONDS,
        )

        result = run()

        self.assertFalse(result.ok)
        self.assertEqual(RIDER, result.failed_agent)
        self.assertEqual(2, len(transport.calls), "the retry is made when there is time")

    def test_a_budget_of_zero_stops_the_case_before_any_call(self):
        """The boundary, stated: a case with no budget makes no call at all."""
        transport, run = self.case_over(
            self.PER_CALL_SECONDS,
            envelope(RIDER_CLAIMS),
            deadline=0.0,
        )

        with self.assertRaises(pipeline.CaseDeadlineExceeded):
            run()

        self.assertEqual([], transport.calls)

    def test_a_budget_that_is_never_spent_changes_nothing(self):
        """A case inside its deadline behaves exactly as it did before."""
        transport, run = self.case_over(
            0.0,
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(GOOD_RULING),
            deadline=self.DEADLINE_SECONDS,
        )

        result = run()

        self.assertTrue(result.ok)
        self.assertEqual([RIDER, DRIVER, JUDGE], roles_of(result))
        self.assertEqual(3, len(transport.calls))

    def test_the_default_is_a_bound_and_still_clears_the_slowest_case(self):
        """Derived from measurement, so the derivation is asserted, not the number.

        Three things have to hold at once, and each one has bitten. The limit
        must clear the slowest case actually seen (978.8 s) or it fails the
        thing it is meant to protect. It must accommodate three calls each
        running into the per-attempt timeout (3 x 606 s = 1818 s, from the
        605.8-second TIMEOUT failure recorded on 2026-09-22). And it must be a
        bound on the 241-minute worst case it was added to remove.
        """
        self.assertGreater(pipeline.DEFAULT_CASE_DEADLINE_SECONDS, 978.8)
        self.assertGreaterEqual(
            pipeline.DEFAULT_CASE_DEADLINE_SECONDS, 3 * llm.DEFAULT_TIMEOUT_SECONDS
        )
        self.assertLess(pipeline.DEFAULT_CASE_DEADLINE_SECONDS, 241 * 60)

    def test_the_default_spans_a_shape_retry_on_every_agent(self):
        """Six calls is the worst case the limit has to be able to bound.

        Three agents, each retried once, at the per-call deadline each: the case
        limit has to be tighter than that product or it bounds nothing.
        """
        worst_case_of_calls = 6 * llm.DEFAULT_TOTAL_DEADLINE_SECONDS
        self.assertLess(pipeline.DEFAULT_CASE_DEADLINE_SECONDS, worst_case_of_calls)


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
