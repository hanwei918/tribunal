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
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, llm, money, pipeline, transcript as transcript_module  # noqa: E402
from tribunal.model import RUNTIME_MODEL  # noqa: E402

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
    return pipeline.run_case(CASE, client_for(*responses), now=lambda: PINNED_NOW, judge_votes=1)


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
        """A text check, and one of only four in this file.

        Everything above asserts on parsed structure. This one cannot: the thing
        under test is prose, and there is no structural way to ask what a
        paragraph instructs a model to do. So it is kept as narrow as it can be —
        it looks for the phrase "JSON array" in a prompt whose request forces an
        object, which is the exact instruction that was wrong. The other text
        checks, ``DecidingFactCarrierTests``, ``ExplanationAnswersTheSurvivingClaimsTests``
        and ``ReferralContractTests``, cannot assert on structure for the same
        reason, and each is confined to one subsection for the same narrowness.

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
    """The Step 2 subsection, from its heading up to the escalation floor.

    Whitespace is collapsed to single spaces, as in ``referral_section``. The
    assertion is about what the prompt instructs a model to do, and a re-wrapped
    line is not a change of instruction; collapsing is what lets a check span a
    line break without also pinning the wrapping.
    """
    if text is None:
        text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
    start = text.index(_CARRIER_HEADING)
    section = text[start : text.index(_CARRIER_ENDS_AT, start)]
    return " ".join(section.split())


class DecidingFactCarrierTests(unittest.TestCase):
    """Step 2 must say what kind of artifact can carry a deciding fact.

    A text check, and one of only four in this file, for the same reason as the
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

    The second amendment is the converse of the first, and it is what most of
    the checks below are for. Saying a message can carry a fact left open
    whether it can *meet a limb*, and a real run read it as yes: a driver's own
    "I've arrived" messages were taken as satisfying a proximity test whose
    clause names the GPS trace, on a trace where no fix qualified at all.

    A read-only review of that amendment then found wording that could move
    cases the key has right today, and wording that did not compel what the note
    claimed for it. It is now an ordered procedure rather than paragraphs of
    principle, because the failures were all of one shape: a sentence true of
    the confidence cap, read as a rule about the limb. The checks below pin each
    step, and both halves of each step, so that neither direction can be read
    out of it — impairment judged on the part of the artifact the test reads and
    over the stretch the defect covers; an undecided limb that moves no money
    either way; an account standing in for a test only where the policy names
    it; and an uncited excuse that is a discarded assertion, not an untested
    limb.
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


    # -- the second amendment: carrying a fact is not meeting a limb --------
    def test_meeting_a_limb_is_not_carrying_a_fact(self):
        """(a) The two questions are separated, and the limb's own test decides."""
        self.assertIn("Deciding a limb is not carrying a fact", self.section)
        self.assertIn("the test its own clause states for it", self.section)
        self.assertIn("in either direction", self.section)
        self.assertIn("or the policy names it as what may stand in", self.section)

    def test_the_stated_test_includes_a_counting_rule_from_another_clause(self):
        """(a) The limb's quantity may be counted by a rule stated elsewhere.

        The draft said a test "taken from another clause", which reads as the
        limb borrowing a test rather than as another clause saying how the
        limb's own quantity is counted. One case's dwell is a sum of separate
        holds that another clause permits to be added, and the rule is about
        counting, not about which test applies.
        """
        self.assertIn("plus any rule another clause gives about that limb", self.section)
        self.assertIn("where the measurement starts", self.section)
        self.assertIn("whether separate stretches are summed", self.section)
        self.assertIn("how an early or false arrival marker is treated", self.section)
        self.assertIn("what follows from the result", self.section)

    def test_an_account_is_not_a_measurement_and_both_halves_survive(self):
        """(b) An account carries facts; it does not run a measurement test.

        Both halves are required, and after the account sentence was removed
        they are carried by two places rather than one. Saying a message never
        records where anyone was would remove the admissions against interest
        the subsection above depends on, so the carrier half is that
        subsection's own grant that what a party said can carry the deciding
        fact; saying nothing leaves the judge free to let a message satisfy a
        proximity test its clause never gave it, so the limb half is that an
        account decides a limb only where the clause reads the log or the
        statement as its own test. The sentence that used to say both in one
        breath — "it may carry a fact for the cap" — was removed, because that
        clause read as "it may carry the limb" and lifted the cap on an impaired
        trace; both halves are asserted present here so the removal cannot take
        one of them with it.
        """
        self.assertIn("can carry the deciding fact", self.section)
        self.assertIn("reads the log or the statement as its own test", self.section)
        self.assertNotIn("not a measurement", self.section)
        self.assertNotIn("it may carry a fact for the cap", self.section)

    def test_a_status_a_party_sets_is_read_for_what_the_clause_reads_it_as(self):
        """(b) An arrival tap and a reason code are what two limbs read.

        "Records only that the party set it" is true and, left alone, makes the
        limbs that read one look unproven. The sentence has to say what decides
        them as well as what does not.
        """
        self.assertIn("records only that the party set it", self.section)
        self.assertIn("a record the platform generates is the platform's", self.section)
        self.assertIn("decides a limb where the clause reads it as its test", self.section)

    def test_an_account_decides_a_limb_only_where_the_policy_says_so(self):
        """(d) The admission exception was too strong, and is gone.

        "An account decides a limb where it concedes against interest" lets an
        admission replace a measured test, and the proximity test is written
        "only where". What the cases need is the policy naming the account,
        which it does for the corroboration list.
        """
        self.assertIn("reads the log or the statement as its own test", self.section)
        self.assertNotIn("concedes against the speaker's own interest", self.section)

    def test_an_impaired_test_is_undecided_over_the_stretch_it_covers(self):
        """(c) A test that cannot run is not a test that failed.

        Two things the draft left open are pinned here. Impairment is judged on
        the part of the artifact the test reads, over the stretch the defect
        covers, and it is the policy's own integrity limbs that count rather
        than a pre-pass tag. And an undecided limb is not a licence to refund:
        it moves no money either way, which is what stops it becoming one.
        """
        self.assertIn("impaired over the stretch the defect covers", self.section)
        self.assertIn("Absent is the limiting case", self.section)
        self.assertIn("under the category's own integrity limbs", self.section)
        self.assertIn("not merely flagged by the pre-pass", self.section)
        self.assertIn("the limb is undecided over that stretch", self.section)
        self.assertIn("neither a payment that needs the clause to hold", self.section)
        self.assertIn("nor a refund that needs it to fail", self.section)

    def test_a_test_that_ran_and_found_nothing_has_run(self):
        """(c) The converse, and the half the draft got wrong.

        Without it a trace whose fixes are all filtered out reads as untested
        and the fee stands on nothing. With it, the one clause that makes that
        result undecidable is an exception, and it is named as one.
        """
        self.assertIn("finds nothing qualifying has run", self.section)
        self.assertIn("unless its own clause makes that result undecidable", self.section)
        self.assertIn("passed the clause's own filters", self.section)

    def test_a_missing_artifact_is_not_an_uncited_excuse(self):
        """(e) The draft's "the artifact is missing, so the test has not run".

        Read literally that turns a driver's uncited traffic excuse into an
        untested limb and then into an escalation, where the key discards it and
        decides on the clause that carries the burden. It would also stop a
        clause invoked against a genuinely absent artifact from escalating on
        its own terms, which several clauses require.
        """
        self.assertIn("invoked with nothing behind it is not an untested limb", self.section)
        self.assertIn(
            "citing no evidence is discarded under the clause that places the burden",
            self.section,
        )
        self.assertIn("escalates on that clause's own terms", self.section)

    def test_bridging_is_not_substituting(self):
        """(d) A record from inside an unobserved stretch is not a stand-in."""
        self.assertIn("Bridging is not substituting", self.section)
        self.assertIn("inside a stretch the test left unobserved", self.section)
        self.assertIn("between readings the test admitted", self.section)
        self.assertIn("whether something is the only evidence", self.section)

    def test_a_stand_in_neither_lifts_the_cap_nor_is_the_only_evidence(self):
        """(d) The half the draft left open, and the one that moves a case.

        Where the test admitted no reading at all, the driver's own account was
        still allowed to lift the cap, which defeats the clause that makes an
        impaired trace the only evidence. Standing in for the test is not
        bridging it.
        """
        self.assertIn("admitted no reading at all", self.section)
        self.assertIn("standing in for the test", self.section)
        self.assertIn("neither lifts the cap", self.section)
        self.assertIn("nor stops the impaired artifact being the only evidence", self.section)

    def test_a_contradiction_the_policy_escalates_on_stays_one(self):
        """(f) The amendment does not resolve a contradiction the policy names.

        Unqualified, the sentence blocks the clause that resolves the conflict —
        and the escalation ground itself asks whether a clause resolves it, so
        the answer has to come from the clause.
        """
        self.assertIn("stays one", self.section)
        self.assertIn("does not dissolve it", self.section)
        self.assertIn(
            "unless the ground itself asks whether a clause resolves the conflict",
            self.section,
        )

    def test_the_counterparty_statement_is_placed_where_it_lives(self):
        """(g) It is in `case.dispute`, and it is still evidence.

        The prompt said its weight was its own `weight_multiplier`, which is not
        a field it has. Saying "this is not one of them" then read as "it does
        not carry the fact", which is wrong the other way: it is evidence, and a
        corroboration list names it.
        """
        self.assertIn("sits in `case.dispute` rather than `case.evidence`", self.section)
        self.assertIn("carries no `weight_multiplier`", self.section)
        self.assertIn("enters neither the minimum nor the maximum of the cap", self.section)
        self.assertIn("meets any limb whose clause names a counterparty statement", self.section)
        self.assertNotIn("so is a counterparty statement", self.section)

    def test_the_readings_the_review_found_defective_are_gone(self):
        """Five readings that could move a case the key has right today.

        Each is asserted absent rather than merely superseded: each reads well
        and decides wrongly, and a later edit could put one back without
        noticing that it had been taken out. The fifth is the middle clause of
        the account sentence, which read as "it may carry the limb" and lifted
        the cap on an impaired trace. Only that clause is pinned absent: the
        sentence's other half — that an account does not run a measurement test
        — is still required, and is asserted present above.
        """
        for phrase in (
            "is neither met nor failed",
            "the test has not run",
            "concedes against the speaker's own interest",
            "including a test the clause takes from another clause",
            "it may carry a fact for the cap",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.section)

    def test_the_section_contains_no_digit(self):
        """A digit is a figure the policy owns, and the prompt owns none.

        The floor is the one that matters: it is read from the loaded policy,
        and a threshold or a count written here would go stale against the
        policy the judge is actually handed.
        """
        self.assertEqual([], re.findall(r"[0-9]", self.section))

    def test_the_section_names_nothing_from_the_organisers_sample(self):
        """The sample is what prompted the amendment; it is not the rule."""
        for term in (
            "RydeResolve", "DISP-002", "Tiong Bahru", "VivoCity", "Michael Wong",
            "Lim Wei Ming", "Honda", "SGP 4521", "R-7823", "D-2398",
            "TRIP-2026-09945", "no_show_charge",
        ):
            with self.subTest(term=term):
                self.assertNotIn(term, self.section)

    def test_the_section_collapses_whitespace_the_way_the_referral_one_does(self):
        """So a re-wrapped line is not read as a change of instruction."""
        self.assertNotIn("\n", self.section)
        self.assertNotIn("  ", self.section)
        self.assertEqual(self.section, " ".join(self.section.split()))


# --------------------------------------------------------------------------
# What produces a referral
# --------------------------------------------------------------------------
# The judge prompt's referral paragraphs, read out of the prompt rather than
# assumed, so a reordering shows up as a failure rather than as a check that
# stopped looking.
_REFERRAL_HEADING = "**A REFERRAL is not an escalation.**"
_REFERRAL_ENDS_AT = "**On a `DRIVER_COMPENSATION` ruling"


def referral_section(text=None):
    """The referral paragraphs, from the ESCALATE sentence to the next paragraph.

    Whitespace is collapsed to single spaces on purpose: the assertion is about
    what the prompt instructs a model to do, and a re-wrapped line is not a
    change of instruction.
    """
    if text is None:
        text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
    start = text.index(_REFERRAL_HEADING)
    section = text[start : text.index(_REFERRAL_ENDS_AT, start)]
    return " ".join(section.split())


class ReferralContractTests(unittest.TestCase):
    """The prompt must say a referral is clause-produced, and nothing looser.

    The prompt said a referral instructs the human reviewer what to do and
    stopped there, which invites free-form reviewer instructions. On case 213 the
    judge wrote one -- asking the reviewer to recover the driver-device trace and
    the chat log -- and the answer key expects none. The prompt and the key
    disagreed, and POL-GEN-03 settles it: a referral is something a CLAUSE
    produces.

    The other direction matters as much. A referral rides on an ESCALATE ruling
    on case 207, and that sentence is what makes it legal, so it is required to
    survive here. And the prompt must not become a list of case numbers: the
    clauses are named because they are the policy, the cases are not.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
        cls.section = referral_section(cls.text)

    def test_the_referral_paragraph_is_present_at_all(self):
        self.assertIn(_REFERRAL_HEADING, self.text)

    def test_a_referral_exists_only_where_a_clause_produces_one(self):
        self.assertIn("A referral exists only where a clause produces one.", self.section)

    def test_every_referral_leads_with_the_clause_that_produces_it(self):
        self.assertIn(
            "Every referral leads with the clause reference that produces it.", self.section
        )

    def test_the_three_clauses_pol_gen_03_names_are_stated(self):
        """The policy's own list, not a list of cases to match against."""
        for clause in ("POL-RD-06(c)", "POL-RD-09(4)", "POL-NS-05(ii)"):
            with self.subTest(clause=clause):
                self.assertIn(clause, self.section)

    def test_pol_ns_07_is_named_as_a_fourth(self):
        """It directs its own escalation packet, so the clause produces it too."""
        self.assertIn("POL-NS-07 is a fourth", self.section)

    def test_the_prompt_says_to_read_the_clause_text(self):
        self.assertIn(
            "Read the governing clause text to decide whether one fires.", self.section
        )

    def test_the_prompt_forbids_inferring_a_referral_from_helpfulness(self):
        self.assertIn(
            "Do not infer a referral from a desire to be helpful", self.section
        )

    def test_an_open_question_goes_in_the_explanation(self):
        self.assertIn("belongs in `explanation`", self.section)
        self.assertIn(
            "clause-mandated instructions that a platform acts on", self.section
        )

    def test_the_sentence_that_a_referral_can_ride_on_an_escalate_survives(self):
        """Case 207 is exactly that, and it must keep working."""
        self.assertIn(
            "A case can be `ESCALATE` and still carry a non-empty referral "
            "instructing the human reviewer what to do.",
            self.section,
        )

    def test_the_prompt_does_not_name_the_cases_it_was_written_for(self):
        """Case numbers would make it a checklist rather than a principle.

        The two cases behind this edit are 213, where the judge invented a
        referral, and 207, where the referral is real. Neither belongs in the
        prompt: a model handed the numbers would match on those and stop.
        """
        for case_no in ("213", "207"):
            with self.subTest(case=case_no):
                self.assertNotIn(case_no, self.section)

    def test_the_amended_prompt_keeps_the_output_contract(self):
        """Change 2 edits prose; it must not disturb the shape the prompt asks for."""
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


# --------------------------------------------------------------------------
# What the explanation owes the claims that survived
# --------------------------------------------------------------------------
# Read out of the prompt rather than assumed, as above, so a reordering shows up
# as a failure rather than as a check that stopped looking.
_STEP_THREE_HEADING = "## Step 3 — the result object"
_STEP_THREE_ENDS_AT = "## Three things that decide real cases"


def step_three_section(text=None):
    """The Step 3 section, whitespace collapsed as in ``referral_section``."""
    if text is None:
        text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
    start = text.index(_STEP_THREE_HEADING)
    section = text[start : text.index(_STEP_THREE_ENDS_AT, start)]
    return " ".join(section.split())


class ExplanationAnswersTheSurvivingClaimsTests(unittest.TestCase):
    """Step 3 must say what the explanation owes the claims that survived.

    A text check, and the fourth in this file. The gap it closes is the other
    half of the one above it: Step 1 discards a claim and records why, and Step 2
    says how a fact may be carried, but nothing said what becomes of a claim that
    passes the citation check and is then outweighed, or rejected on its merits.
    Those claims went unanswered, which reads to the party who made them as
    though the arbitrator never considered them.

    The distinction the prompt has to keep is that a merits rejection is not a
    Step 1 discard. ``discarded_claims`` is the citation audit, and filing a
    weighed-and-rejected claim there would misreport the audit. So the prompt
    says where the answer goes, and says the claim does not go in that field.
    It adds no field of its own: the answer goes in `ruling.explanation`.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
        cls.section = step_three_section(cls.text)

    def test_the_step_three_section_is_present_at_all(self):
        self.assertIn(_STEP_THREE_HEADING, self.text)

    def test_it_sits_beside_the_explanation_field(self):
        """It is about `ruling.explanation`, so it belongs in that list."""
        field = "- `ruling.explanation` — addressed to both parties"
        self.assertIn(field, self.section)
        self.assertLess(
            self.section.index(field),
            self.section.index("is answered in `ruling.explanation`"),
            "the instruction does not follow the field it is about",
        )

    def test_a_surviving_claim_that_would_change_the_outcome_is_answered(self):
        self.assertIn("survived Step 1", self.section)
        self.assertIn("is answered in `ruling.explanation`", self.section)
        self.assertIn("change the ruling, an amount, the driver's compensation", self.section)

    def test_the_two_ways_of_answering_are_stated(self):
        self.assertIn("accepted but outweighed", self.section)
        self.assertIn("saying by what", self.section)
        self.assertIn("rejected, saying why", self.section)

    def test_claims_on_the_same_point_are_answered_together(self):
        self.assertIn("Claims on the same point are answered together", self.section)

    def test_a_merits_rejection_is_not_a_step_one_discard(self):
        self.assertIn("is not a Step 1 discard", self.section)
        self.assertIn("does not go in `discarded_claims`", self.section)

    def test_it_adds_no_field(self):
        """The answer goes in a field that already exists, not in a new one."""
        self.assertIn("Do not add any other top-level field.", self.section)

    def test_the_section_collapses_whitespace(self):
        self.assertNotIn("\n", self.section)
        self.assertEqual(self.section, " ".join(self.section.split()))


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
        self.result = pipeline.run_case(CASE, self.client, now=lambda: PINNED_NOW, judge_votes=1)

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
        self.result = pipeline.run_case(CASE, self.client, now=lambda: PINNED_NOW, judge_votes=1)
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
        self.assertEqual(parsed["referee"]["ledger"], [])
        self.assertEqual(parsed["referee"]["flags"], [])
        self.assertEqual(self.result.referee["discards"], [])
        self.assertEqual(self.result.referee["discards"], [])


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
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)

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
        pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)

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
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)

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
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)

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
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)

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
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)

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
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)

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
            judge_votes=1,
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
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=1)
        text = result.transcript_json
        parsed = json.loads(text)

        self.assertEqual(len(parsed["entries"]), 2)
        for entry in parsed["entries"]:
            self.assertEqual(entry["response_text"], bad)
            self.assertIsNotNone(entry["note"])
            self.assertEqual(entry["shape"], pipeline.SHAPE_OBJECT)
        self.assertNotIn(FAKE_KEY, text)


class RuntimeModelWiringTests(unittest.TestCase):
    """The CLI reads the decided model; the transport still keeps no default.

    Two separate claims, and they are separate on purpose. ``--model`` is an
    override rather than a demand, so the decision recorded in
    ``tribunal/model.py`` is load-bearing; and ``LLMClient`` still refuses to
    invent a model of its own, so the decision cannot drift into the transport.
    """

    def _model_the_cli_built_a_client_with(self, argv):
        """Run the CLI with the client and the case both stubbed out.

        The stubs are the point: this asserts what the command line decides, and
        a test that reached a real model to find out would be measuring
        something else, slowly and at a price.
        """
        captured = []

        def fake_client(*args, **kwargs):
            captured.append(kwargs.get("model"))
            return object()

        result = pipeline.PipelineResult(
            case_no=CASE,
            model=RUNTIME_MODEL,
            ok=True,
            brief_sha256="0" * 64,
            transcript=transcript_module.Transcript(now=lambda: PINNED_NOW),
        )

        with mock.patch.object(llm, "LLMClient", fake_client):
            with mock.patch.object(pipeline, "run_case", lambda *a, **k: result):
                with redirect_stdout(io.StringIO()):
                    status = pipeline.main(argv)

        self.assertEqual(1, len(captured), "the CLI did not build exactly one client")
        return captured[0], status

    def test_the_cli_without_a_model_uses_the_decided_one(self):
        model, status = self._model_the_cli_built_a_client_with(["--case", str(CASE)])

        self.assertEqual(RUNTIME_MODEL, model)
        self.assertEqual(0, status)

    def test_a_named_model_overrides_the_decision(self):
        model, status = self._model_the_cli_built_a_client_with(
            ["--case", str(CASE), "--model", "hy4-preview"]
        )

        self.assertEqual("hy4-preview", model)
        self.assertNotEqual(RUNTIME_MODEL, model)
        self.assertEqual(0, status)

    def test_the_transport_still_refuses_to_invent_a_model(self):
        """The decision lives in one module, not as a convenience in the client."""
        with self.assertRaises(llm.LLMError):
            llm.LLMClient(model="")
        with self.assertRaises(TypeError):
            llm.LLMClient()


# --------------------------------------------------------------------------
# The judge's vote
# --------------------------------------------------------------------------
def vote_ruling(
    ruling_value="PARTIAL_REFUND",
    amount=4.0,
    compensation=None,
    referrals=(),
    confidence=0.85,
    explanation="because",
) -> str:
    """One judge answer, as the scripted transport should hand it back.

    ``amount`` defaults to ``4.0`` because that is a figure the brief for
    :data:`CASE` publishes -- the POL-NS-03(ii) pin-ambiguity goodwill of 4.00 --
    and a draft is now held to the brief's own calculator before it may vote.
    The fixture has to be a draft that can vote, or every vote test would be
    measuring the check instead of the vote. One test holds the fixture's amount
    and the brief's own published figures together.
    """
    return json.dumps(
        {
            "ruling": {
                "ruling": ruling_value,
                "amount_sgd": amount,
                "driver_compensation_sgd": compensation,
                "referrals": list(referrals),
                "confidence": confidence,
                "explanation": explanation,
            },
            "discarded_claims": [],
        }
    )


def run_vote(*responses, votes=4):
    """A full run at a named number of judge drafts, with the transport returned."""
    transport = FakeTransport(*responses)
    client = llm.LLMClient(
        model="hy4-preview",
        api_key=FAKE_KEY,
        transport=transport,
        sleep=lambda seconds: None,
        clock=lambda: 0.0,
    )
    return pipeline.run_case(CASE, client, now=lambda: PINNED_NOW, judge_votes=votes), transport


def judge_messages(transport) -> list:
    """Every judge request the transport received, in order, as request bodies.

    Identified by its user message rather than by counting calls, because a
    draft whose answer is unusable makes two calls and a counter would misalign.
    """
    found = []
    for call in transport.calls:
        body = json.loads(call["body"].decode("utf-8"))
        try:
            parsed = json.loads(body["messages"][1]["content"])
        except ValueError:
            continue
        if isinstance(parsed, dict) and "brief" in parsed and "claims" in parsed:
            found.append(body)
    return found


class JudgeVoteTests(unittest.TestCase):
    """The judge is asked K times on the same inputs and the majority decides.

    The judge is sampled, so one call is one sample and cannot report that about
    itself. Three corpus cases (105, 107 and 211) each flipped between runs whose
    prompts differed in ways unrelated to those cases, which is the measurement
    this exists to make visible. Every test here scripts the transport: no
    network, and no model call.
    """

    ADVOCATES = (envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS))

    def drafts(self, *answers):
        return (*self.ADVOCATES, *answers)

    # -- the vote ----------------------------------------------------------
    def test_four_drafts_in_agreement_carry_the_ruling(self):
        result, _ = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))

        self.assertTrue(result.ok)
        self.assertEqual("PARTIAL_REFUND", result.ruling["ruling"]["ruling"])
        self.assertEqual(Decimal("4.0"), result.ruling["ruling"]["amount_sgd"])
        self.assertEqual(1.0, result.vote_agreement)
        self.assertEqual("carried", result.judge_vote["outcome"])
        self.assertTrue(result.judge_vote["unanimous"])
        self.assertEqual(4, result.judge_vote["valid"])

    def test_three_of_four_carries_it_and_is_not_unanimous(self):
        result, _ = run_vote(
            *self.drafts(
                envelope(vote_ruling()),
                envelope(vote_ruling()),
                envelope(vote_ruling()),
                envelope(vote_ruling("NO_ACTION", amount=None)),
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual("PARTIAL_REFUND", result.ruling["ruling"]["ruling"])
        self.assertEqual(0.75, result.vote_agreement)
        self.assertEqual("carried_not_unanimous", result.judge_vote["outcome"])
        self.assertFalse(result.judge_vote["unanimous"])
        # The published explanation is the first majority draft's, with the
        # vote result stated at its end.
        explanation = result.ruling["ruling"]["explanation"]
        self.assertTrue(explanation.startswith("because"))
        self.assertIn("carried, not unanimous", explanation)
        self.assertIn("3 of the 4 drafts", explanation)

    def test_a_four_way_unanimous_vote_says_so_at_the_end(self):
        result, _ = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))

        explanation = result.ruling["ruling"]["explanation"]
        self.assertTrue(explanation.startswith("because"))
        self.assertIn("carried unanimously", explanation)

    def test_two_and_two_escalates_with_both_amounts_null(self):
        result, _ = run_vote(
            *self.drafts(
                envelope(vote_ruling()),
                envelope(vote_ruling()),
                envelope(vote_ruling("NO_ACTION", amount=None)),
                envelope(vote_ruling("NO_ACTION", amount=None)),
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual("ESCALATE", result.ruling["ruling"]["ruling"])
        self.assertIsNone(result.ruling["ruling"]["amount_sgd"])
        self.assertIsNone(result.ruling["ruling"]["driver_compensation_sgd"])
        self.assertEqual(0.5, result.vote_agreement)
        self.assertEqual("escalated", result.judge_vote["outcome"])
        # The explanation says they disagreed, and shows what each proposed.
        explanation = result.ruling["ruling"]["explanation"]
        self.assertIn("did not agree", explanation)
        self.assertIn("PARTIAL_REFUND, amount_sgd 4.0", explanation)
        self.assertIn("NO_ACTION", explanation)

    def test_a_split_between_escalate_and_money_still_escalates(self):
        result, _ = run_vote(
            *self.drafts(
                envelope(vote_ruling("ESCALATE", amount=None, confidence=0.2)),
                envelope(vote_ruling("ESCALATE", amount=None, confidence=0.2)),
                envelope(vote_ruling()),
                envelope(vote_ruling()),
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual("ESCALATE", result.ruling["ruling"]["ruling"])
        self.assertIsNone(result.ruling["ruling"]["amount_sgd"])
        self.assertEqual("escalated", result.judge_vote["outcome"])

    def test_one_unparseable_draft_abstains_and_the_other_three_carry(self):
        result, _ = run_vote(
            *self.drafts(
                envelope("not JSON at all"),
                envelope("not JSON at all"),
                envelope(vote_ruling()),
                envelope(vote_ruling()),
                envelope(vote_ruling()),
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual("PARTIAL_REFUND", result.ruling["ruling"]["ruling"])
        vote = result.judge_vote
        self.assertEqual(3, vote["valid"])
        abstained = [draft for draft in vote["drafts"] if not draft["valid"]]
        self.assertEqual(1, len(abstained))
        self.assertIsNotNone(abstained[0]["abstention"])
        self.assertIsNone(abstained[0]["agrees"])
        self.assertIsNone(abstained[0]["proposal"])
        # Both attempts are the draft's, so an unusable draft occupies two
        # transcript entries and the record says which.
        self.assertEqual([2, 3], abstained[0]["entries"])
        self.assertFalse(vote["unanimous"])
        self.assertEqual(0.75, vote["agreement"])

    def test_two_unparseable_drafts_leave_too_few_votes_and_escalate(self):
        result, _ = run_vote(
            *self.drafts(
                envelope("nope"),
                envelope("nope"),
                envelope("nope"),
                envelope("nope"),
                envelope(vote_ruling()),
                envelope(vote_ruling()),
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual("ESCALATE", result.ruling["ruling"]["ruling"])
        self.assertEqual(2, result.judge_vote["valid"])
        self.assertEqual("escalated", result.judge_vote["outcome"])
        self.assertIsNone(result.ruling["ruling"]["amount_sgd"])

    def test_no_usable_draft_at_all_is_the_failure_it_has_always_been(self):
        """Nothing was answered, so nothing disagreed: the judge failed.

        Publishing an ESCALATE here would invent a ruling the judge never gave.
        """
        result, _ = run_vote(*self.drafts(*[envelope("nope")] * 8))

        self.assertFalse(result.ok)
        self.assertEqual(JUDGE, result.failed_agent)
        self.assertIsNone(result.ruling)
        self.assertEqual("no_valid_drafts", result.judge_vote["outcome"])
        self.assertEqual(0, result.judge_vote["valid"])
        self.assertIsNone(result.vote_agreement)

    def test_a_k_larger_than_the_declared_seeds_is_refused(self):
        with self.assertRaises(pipeline.PipelineError):
            run_vote(*self.ADVOCATES, votes=len(pipeline.JUDGE_VOTE_SEEDS) + 2)

    def test_a_single_draft_is_refused_as_a_vote(self):
        with self.assertRaises(pipeline.PipelineError):
            run_vote(*self.ADVOCATES, votes=0)

    def test_k_is_configurable(self):
        result, _ = run_vote(
            *self.drafts(envelope(vote_ruling()), envelope(vote_ruling())), votes=2
        )

        self.assertTrue(result.ok)
        self.assertEqual(2, result.judge_vote["votes"])
        self.assertEqual(2, result.judge_vote["threshold"])
        self.assertEqual(1.0, result.vote_agreement)

    # -- the four graded fields, together ----------------------------------
    def test_the_vote_selects_an_answer_rather_than_averaging_one(self):
        """Both amounts are figures the brief publishes, so both drafts vote.

        The dissenting amount has to be a real figure too: a draft whose money
        does not read off the brief abstains rather than dissents, and a test
        about selecting between answers would then be measuring the check.
        """
        result, _ = run_vote(
            *self.drafts(
                envelope(vote_ruling(amount=4.0)),
                envelope(vote_ruling(amount=4.0)),
                envelope(vote_ruling(amount=4.0)),
                envelope(vote_ruling(amount=6.4)),
            )
        )

        self.assertEqual(Decimal("4.0"), result.ruling["ruling"]["amount_sgd"])
        self.assertEqual("carried_not_unanimous", result.judge_vote["outcome"])
        self.assertEqual(4, result.judge_vote["valid"])

    def test_a_referral_difference_is_a_difference(self):
        """The four fields are voted on together, so a referral splits a vote.

        Both clauses are ones the policy loaded for :data:`CASE` carries: a
        referral to a clause the loaded policy does not carry abstains before
        the vote, which is a different test.
        """
        result, _ = run_vote(
            *self.drafts(
                envelope(vote_ruling(referrals=["POL-NS-05(ii): flag the record"])),
                envelope(vote_ruling(referrals=["POL-NS-05(ii): flag the record"])),
                envelope(vote_ruling(referrals=["POL-NS-07: direct the reviewer"])),
                envelope(vote_ruling(referrals=["POL-NS-07: direct the reviewer"])),
            )
        )

        self.assertEqual("ESCALATE", result.ruling["ruling"]["ruling"])

    def test_the_same_clause_referred_to_in_different_prose_is_the_same_referral(self):
        result, _ = run_vote(
            *self.drafts(
                envelope(vote_ruling(referrals=["POL-NS-07: refund the rider"])),
                envelope(vote_ruling(referrals=["refer the billing question to POL-NS-07"])),
                envelope(vote_ruling(referrals=["POL-NS-07: check the fare again"])),
                envelope(vote_ruling(referrals=["POL-NS-07: check the fare again"])),
            )
        )

        self.assertTrue(result.ok)
        self.assertEqual("carried", result.judge_vote["outcome"])
        self.assertTrue(result.judge_vote["unanimous"])

    def test_the_vote_does_not_change_what_confidence_means(self):
        result, _ = run_vote(*self.drafts(*[envelope(vote_ruling(confidence=0.42))] * 4))

        self.assertEqual(Decimal("0.42"), result.ruling["ruling"]["confidence"])
        self.assertEqual(1.0, result.vote_agreement)

    # -- the drafts --------------------------------------------------------
    def test_the_swapped_draft_differs_from_a_normal_one_only_in_side_order(self):
        """The three sampled drafts read DRIVER first; the swapped one does not.

        Canonical JSON sorts an object's keys, and it sorts ``DRIVER_ADVOCATE``
        before ``RIDER_ADVOCATE``, so the object shape the single-draft run uses
        cannot express a swap at all: it would serialise straight back to the
        bytes it started from. The vote therefore carries the two sides as an
        ordered array, and this is what makes the swap a real difference.
        """
        _, transport = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))
        bodies = judge_messages(transport)
        self.assertEqual(4, len(bodies))
        parsed = [json.loads(body["messages"][1]["content"]) for body in bodies]

        for body in parsed[:-1]:
            self.assertIsInstance(body["claims"], list)
            self.assertEqual(
                [DRIVER, RIDER], [entry["side"] for entry in body["claims"]]
            )
        self.assertEqual([RIDER, DRIVER], [entry["side"] for entry in parsed[-1]["claims"]])
        # Only the order differs: the same two entries, byte for byte.
        self.assertEqual(
            sorted(json.dumps(entry, sort_keys=True) for entry in parsed[0]["claims"]),
            sorted(json.dumps(entry, sort_keys=True) for entry in parsed[-1]["claims"]),
        )
        # And every other part of the message is identical across the drafts.
        for body in parsed[1:]:
            self.assertEqual(parsed[0]["brief"], body["brief"])
            self.assertEqual(parsed[0]["referee"], body["referee"])

    def test_the_swapped_draft_runs_at_the_clients_own_settings(self):
        result, _ = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))
        drafts = result.judge_vote["drafts"]

        self.assertEqual(
            [pipeline.DRAFT_SAMPLED] * 3 + [pipeline.DRAFT_POSITION_SWAPPED],
            [draft["kind"] for draft in drafts],
        )
        self.assertEqual(list(pipeline.DRIVER_FIRST), drafts[0]["sides"])
        self.assertEqual(list(pipeline.RIDER_FIRST), drafts[-1]["sides"])
        # The swap is the only thing that differs about it, so it is not sampled.
        self.assertEqual(llm.DEFAULT_TEMPERATURE, drafts[-1]["temperature"])
        self.assertEqual(llm.DEFAULT_SEED, drafts[-1]["seed"])

    def test_the_drafts_carry_different_seeds_and_both_are_recorded(self):
        result, transport = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))
        bodies = judge_messages(transport)

        seeds = [body["seed"] for body in bodies]
        self.assertEqual(len(seeds), len(set(seeds)), "two drafts shared a seed")
        recorded = [draft["seed"] for draft in result.judge_vote["drafts"]]
        self.assertEqual(seeds, recorded)
        for draft, body in zip(result.judge_vote["drafts"], bodies):
            self.assertEqual(body["temperature"], draft["temperature"])
        # The three sampled drafts are sampled; the swapped one is not, so it
        # runs at the client's own temperature and its seed is the client's.
        for draft in result.judge_vote["drafts"][:3]:
            self.assertGreater(draft["temperature"], 0)
        self.assertEqual(llm.DEFAULT_TEMPERATURE, result.judge_vote["drafts"][-1]["temperature"])

    def test_every_draft_is_on_the_transcript_in_full(self):
        result, _ = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))
        entries = result.transcript.entries

        self.assertEqual([RIDER, DRIVER, JUDGE, JUDGE, JUDGE, JUDGE], roles_of(result))
        for draft in result.judge_vote["drafts"]:
            self.assertEqual(1, len(draft["entries"]))
            recorded = entries[draft["entries"][0]]
            self.assertEqual(JUDGE, recorded.role)
            self.assertEqual(vote_ruling(), recorded.response_text)

    def test_every_draft_is_billed(self):
        """Four drafts are four calls, and the totals say so.

        The judge is asked more than once, so it costs more than once. A record
        that charged a single draft would understate what the vote costs.
        """
        result, _ = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))

        # Two advocates and four drafts, each envelope reporting 10 and 5.
        self.assertEqual(6, len(result.transcript.entries))
        self.assertEqual(60, result.prompt_tokens)
        self.assertEqual(30, result.completion_tokens)

    def test_the_vote_is_written_into_the_transcript(self):
        result, _ = run_vote(*self.drafts(*[envelope(vote_ruling())] * 4))

        payload = json.loads(result.transcript_json)
        self.assertIn("vote", payload)
        self.assertEqual(4, payload["vote"]["votes"])
        self.assertEqual(1.0, payload["vote"]["agreement"])
        self.assertEqual(4, len(payload["vote"]["drafts"]))
        # The amount stays a JSON number, not a string.
        self.assertIn('"amount_sgd":4.0', result.transcript_json)

    # -- K = 1 is today ----------------------------------------------------
    def test_the_default_is_four_drafts(self):
        """A caller who names nothing gets the vote, not one sample."""
        transport = FakeTransport(*self.drafts(*[envelope(vote_ruling())] * 4))
        client = llm.LLMClient(
            model="hy4-preview",
            api_key=FAKE_KEY,
            transport=transport,
            sleep=lambda seconds: None,
            clock=lambda: 0.0,
        )
        result = pipeline.run_case(CASE, client, now=lambda: PINNED_NOW)

        self.assertEqual(4, pipeline.DEFAULT_JUDGE_VOTES)
        self.assertEqual([RIDER, DRIVER, JUDGE, JUDGE, JUDGE, JUDGE], roles_of(result))

    def test_a_single_draft_behaves_exactly_as_it_did_before(self):
        """One call, the object shape, no vote, and nothing added to the record."""
        result, transport = run_vote(*self.drafts(envelope(GOOD_RULING)), votes=1)

        self.assertTrue(result.ok)
        self.assertEqual([RIDER, DRIVER, JUDGE], roles_of(result))
        self.assertIsNone(result.judge_vote)
        self.assertIsNone(result.vote_agreement)
        self.assertEqual(GOOD_RULING, result.transcript.entries[2].response_text)
        # The explanation is the judge's own, with no vote sentence appended.
        self.assertEqual("because", result.ruling["ruling"]["explanation"])

        # The message is the object shape it has always been, not the array.
        body = json.loads(transport.calls[2]["body"].decode("utf-8"))
        parsed = json.loads(body["messages"][1]["content"])
        self.assertIsInstance(parsed["claims"], dict)
        self.assertEqual([DRIVER, RIDER], sorted(parsed["claims"]))
        self.assertEqual(json.loads(RIDER_CLAIMS), parsed["claims"][RIDER])
        self.assertEqual(json.loads(DRIVER_CLAIMS), parsed["claims"][DRIVER])

        # The request carries the client's own settings, unmodified.
        self.assertEqual(llm.DEFAULT_TEMPERATURE, body["temperature"])
        self.assertEqual(llm.DEFAULT_SEED, body["seed"])

        # And no vote is written into the transcript.
        self.assertNotIn("vote", json.loads(result.transcript_json))

    def test_a_single_draft_still_reports_an_unusable_answer_as_a_failure(self):
        result, _ = run_vote(*self.drafts(envelope("nope"), envelope("nope")), votes=1)

        self.assertFalse(result.ok)
        self.assertEqual(JUDGE, result.failed_agent)
        self.assertIsNone(result.judge_vote)


# --------------------------------------------------------------------------
# What the vote compares, and what a draft must pass first
# --------------------------------------------------------------------------
# The four referrals case 9111's judge drafts actually wrote, as the run
# recorded them. Each proposes one referral, the same one, led by POL-RD-09(4);
# two of the four mention POL-RD-02 in passing.
_RECORDED_9111_REFERRALS = (
    "POL-RD-09(4) billing integrity: review the SGD 2.00 'Tuas South Avenue 8 loop' ERP line charged on TRP-09111 — the GPS trace never passes that gantry (nearest fix 1,645.7 m, outside the 250 m match radius, with no gap bracketing the closest approach), so the line is recorded as a billing-integrity finding.",
    "POL-RD-09(4) billing integrity: the SGD 2.00 Tuas South Avenue 8 loop ERP line is charged for a gantry the GPS trace never passes (nearest fix 1,645.7 m; no fix within the 250 m match radius, no gap bracketing the closest approach), so the line is recorded as a billing-integrity finding and referred for correction; the amount is returned once, inside the POL-RD-02 figure, and is not added on top of it.",
    "POL-RD-09(4) billing-integrity finding: the SGD 2.00 'Tuas South Avenue 8 loop' ERP line on fare breakdown EV-FARE-09111 is unmatched — the nearest GPS fix on EV-GPS-09111 is about 1,646 m away, outside POL-RD-09's 250 m crossing radius, so no fix shows the vehicle crossing that gantry. The amount is already comprehended in the POL-RD-02 refund below and is not paid a second time.",
    "POL-RD-09(4) billing integrity: the fare_breakdown ERP line 'Tuas South Avenue 8 loop' (SGD 2.00) is charged for a gantry the trip never passed - the nearest GPS fix is 1,645.7 m away, far outside the 250 m match radius POL-RD-09 sets for a crossing, and no GPS gap brackets the closest approach. Record this as a billing-integrity finding. The SGD 2.00 is returned to the rider inside the POL-RD-02 refund and is not added again.",
)


class ReferralComparisonTests(unittest.TestCase):
    """The vote compares a referral by the clause it leads with.

    A referral is free prose, so the vote has always compared the clause
    references in it rather than the string. It compared the **union** of every
    clause reference the prose carries, which counted a clause named in passing
    as part of the referral. 9111's four drafts each propose exactly one
    referral, the same one, and the vote split them 2-2 because two of the four
    write "inside the POL-RD-02 figure". A referral's subject is the clause it
    leads with -- the one the judge prompt already requires it to lead with --
    and that is what is compared now.
    """

    def test_the_four_recorded_9111_drafts_now_agree(self):
        keys = {
            pipeline.referral_clause_references([item])
            for item in _RECORDED_9111_REFERRALS
        }

        self.assertEqual({("POL-RD-09(4)",)}, keys)

    def test_the_union_of_every_clause_in_the_prose_is_what_split_them(self):
        """The old reading, computed here so the finding is not just prose."""
        unioned = {
            tuple(sorted(set(pipeline.REFERRAL_CLAUSE_RE.findall(item))))
            for item in _RECORDED_9111_REFERRALS
        }

        self.assertEqual(3, len(unioned), "the record no longer shows the split")
        self.assertIn(("POL-RD-02", "POL-RD-09(4)"), unioned)

    def test_two_drafts_whose_referrals_lead_with_different_clauses_do_not_agree(self):
        result, _ = run_vote(
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(vote_ruling(referrals=["POL-NS-05(ii): flag the record"])),
            envelope(vote_ruling(referrals=["POL-NS-05(ii): flag the record"])),
            envelope(vote_ruling(referrals=["POL-NS-07: direct the reviewer"])),
            envelope(vote_ruling(referrals=["POL-NS-07: direct the reviewer"])),
        )

        self.assertTrue(result.ok)
        self.assertEqual("ESCALATE", result.ruling["ruling"]["ruling"])
        self.assertEqual("escalated", result.judge_vote["outcome"])

    def test_a_clause_mentioned_in_passing_does_not_split_the_vote(self):
        """The 9111 shape, on the test case's own policy."""
        result, _ = run_vote(
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(vote_ruling(referrals=["POL-NS-07: refund the rider"])),
            envelope(vote_ruling(referrals=["POL-NS-07: refund the rider"])),
            envelope(
                vote_ruling(
                    referrals=[
                        "POL-NS-07: refund the rider; the fee is held under POL-NS-05 "
                        "pending that review"
                    ]
                )
            ),
            envelope(
                vote_ruling(
                    referrals=[
                        "POL-NS-07: refund the rider; the fee is held under POL-NS-05 "
                        "pending that review"
                    ]
                )
            ),
        )

        self.assertTrue(result.ok)
        self.assertEqual("carried", result.judge_vote["outcome"])
        self.assertTrue(result.judge_vote["unanimous"])

    def test_a_referral_that_leads_with_no_clause_is_its_own_value(self):
        """It never silently matches a referral that does lead with one."""
        bare = pipeline.referral_clause_references(["refund the rider in full"])
        cited = pipeline.referral_clause_references(["POL-NS-07: refund the rider in full"])

        self.assertNotEqual(bare, cited)
        self.assertEqual(bare, pipeline.referral_clause_references(["a different instruction"]))
        self.assertIsNone(pipeline.REFERRAL_CLAUSE_RE.fullmatch(pipeline.NO_LEADING_CLAUSE))

    def test_the_limb_is_part_of_the_referral(self):
        self.assertNotEqual(
            pipeline.referral_clause_references(["POL-NS-05(ii): flag the record"]),
            pipeline.referral_clause_references(["POL-NS-05: flag the record"]),
        )

    def test_an_empty_referral_list_is_no_referral_at_all(self):
        self.assertEqual((), pipeline.referral_clause_references([]))
        self.assertEqual((), pipeline.referral_clause_references(None))


class JudgeDraftCheckTests(unittest.TestCase):
    """A draft must pass code checks before it may vote.

    The vote counts answers, and a draft whose ruling value is unknown, whose
    money is not a figure the brief's own calculator publishes, or whose
    referrals send the reviewer to a clause the loaded policy does not carry is
    not an answer a panel can be asked to agree with. It abstains with a reason
    code, exactly as an unparseable one does, and the quorum is taken over the
    drafts that remain. Every test here scripts the transport: no network, and
    no model call.
    """

    @classmethod
    def setUpClass(cls):
        cls.brief = brief.build_brief(CASE)
        cls.figures = pipeline.published_money_figures(pipeline.money_block(cls.brief))

    def check(self, **overrides):
        """The checks, run on the vote fixture as the vote would run them."""
        return pipeline.check_judge_draft(json.loads(vote_ruling(**overrides)), self.brief)

    # -- the block ---------------------------------------------------------
    def test_the_money_block_is_found_on_the_fare_breakdown(self):
        block = pipeline.money_block(self.brief)

        self.assertEqual("NO_SHOW_CHARGE", block["category"])
        self.assertIsNone(pipeline.money_block({"case": {"evidence": []}}))

    def test_the_fixture_amount_is_one_the_brief_publishes(self):
        """The fixture has to be a draft that can vote, or the vote tests lie."""
        self.assertIsNotNone(
            pipeline.amount_reads_off(Decimal("4.0"), self.figures),
            "the vote fixture's amount is not a figure case 208 publishes",
        )

    def test_the_published_figures_exclude_the_policy_constants(self):
        paths = [path for path, _ in self.figures]

        self.assertIn("goodwill.value", paths)
        self.assertFalse([path for path in paths if path.startswith("constants.")])

    def test_the_required_amounts_cover_every_ruling_value(self):
        self.assertEqual(set(pipeline.RULING_VALUES), set(pipeline.REQUIRED_AMOUNTS))

    # -- the checks --------------------------------------------------------
    def test_a_well_formed_draft_passes(self):
        self.assertEqual(((), ()), self.check())

    def test_a_ruling_that_is_not_an_object_fails(self):
        failures, _ = pipeline.check_judge_draft(
            {"ruling": "PARTIAL_REFUND", "discarded_claims": []}, self.brief
        )

        self.assertEqual(1, len(failures))
        self.assertTrue(failures[0].startswith(pipeline.DRAFT_RULING_NOT_AN_OBJECT))

    def test_an_unknown_ruling_value_fails(self):
        failures, _ = self.check(ruling_value="REFUND")

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_UNKNOWN_RULING))

    def test_escalate_carrying_money_fails(self):
        failures, _ = self.check(ruling_value="ESCALATE", amount=4.0)

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_ESCALATE_WITH_MONEY))

    def test_a_money_ruling_with_a_null_amount_fails(self):
        failures, _ = self.check(amount=None)

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_AMOUNT_REQUIRED_MISSING))

    def test_a_driver_compensation_that_does_not_mirror_its_amount_fails(self):
        """POL-GEN-03's one exception is a requirement on an amount field."""
        failures, _ = self.check(
            ruling_value="DRIVER_COMPENSATION", amount=None, compensation=6.4
        )

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_AMOUNT_DOES_NOT_MIRROR))

    def test_a_ruling_missing_a_pol_gen_03_money_field_fails(self):
        payload = json.loads(vote_ruling())
        del payload["ruling"]["driver_compensation_sgd"]

        failures, _ = pipeline.check_judge_draft(payload, self.brief)

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_AMOUNT_FIELD_ABSENT))

    def test_a_malformed_clause_reference_fails(self):
        failures, _ = self.check(referrals=["POL-NS-7: refund the rider"])

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_CLAUSE_MALFORMED))

    def test_a_clause_reference_the_loaded_policy_does_not_carry_fails(self):
        """A referral sends a reviewer to a clause; a clause it was not given
        is nowhere to send them. Case 208 is a no-show dispute, so POL-RD-09 is
        not in its loaded policy."""
        failures, _ = self.check(referrals=["POL-RD-09(4): review the billing"])

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_CLAUSE_UNRESOLVED))

    def test_an_amount_the_block_does_not_publish_fails(self):
        failures, unverifiable = self.check(amount=9.99)

        self.assertEqual((), unverifiable)
        self.assertTrue(failures[0].startswith(pipeline.DRAFT_AMOUNT_NOT_READ_OFF))

    def test_an_amount_that_is_a_sum_of_two_published_figures_passes(self):
        # 6.40 driver compensation + 4.00 goodwill.
        self.assertEqual(((), ()), self.check(amount=10.4))
        self.assertEqual(
            "driver_compensation.value + goodwill.value",
            pipeline.amount_reads_off(Decimal("10.4"), self.figures),
        )

    def test_an_amount_that_is_a_sum_of_three_published_figures_passes(self):
        # 8.00 schedule fee + 6.40 driver compensation + 4.00 goodwill.
        self.assertEqual(((), ()), self.check(amount=18.4))

    def test_an_amount_that_needs_four_figures_does_not_read_off(self):
        """Three is the bound, and it is the bound the answer-key check used."""
        failures, _ = self.check(amount=26.4)

        self.assertTrue(failures[0].startswith(pipeline.DRAFT_AMOUNT_NOT_READ_OFF))

    def test_every_failure_names_a_code_from_the_closed_set(self):
        probes = (
            {"ruling_value": "REFUND"},
            {"ruling_value": "ESCALATE", "amount": 4.0},
            {"amount": None},
            {"ruling_value": "DRIVER_COMPENSATION", "amount": None, "compensation": 6.4},
            {"referrals": ["POL-NS-7: refund the rider"]},
            {"referrals": ["POL-RD-09(4): review the billing"]},
            {"amount": 9.99},
        )

        for probe in probes:
            failures, _ = self.check(**probe)
            self.assertTrue(failures, probe)
            for failure in failures:
                self.assertIn(failure.split(":", 1)[0], pipeline.DRAFT_CHECK_CODES)

    # -- the prose-only figure ---------------------------------------------
    def test_a_prose_only_governing_figure_is_recorded_and_the_draft_still_votes(self):
        """Case 109's driver compensation, which POL-RD-04 states only in prose.

        The block publishes no figure for it and says so in ``not_structured``,
        so there is nothing to hold the amount against. The draft is recorded as
        unverifiable and still votes: rejecting it would be measuring the brief.
        """
        draft = json.loads(
            vote_ruling(ruling_value="DRIVER_COMPENSATION", amount=3.15, compensation=3.15)
        )

        failures, unverifiable = pipeline.check_judge_draft(draft, brief.build_brief(109))

        self.assertEqual((), failures)
        self.assertEqual(
            (
                "amount_sgd=3.15 (unverifiable: not structured)",
                "driver_compensation_sgd=3.15 (unverifiable: not structured)",
            ),
            unverifiable,
        )

    def test_the_same_draft_fails_on_a_case_whose_block_publishes_the_figure(self):
        """The exemption is narrow: it is the block's silence, not the ruling."""
        draft = json.loads(
            vote_ruling(ruling_value="DRIVER_COMPENSATION", amount=3.15, compensation=3.15)
        )

        failures, unverifiable = pipeline.check_judge_draft(draft, self.brief)

        self.assertEqual((), unverifiable)
        self.assertTrue(failures[0].startswith(pipeline.DRAFT_AMOUNT_NOT_READ_OFF))

    def test_the_record_carries_the_note_and_the_draft_still_votes(self):
        ruling = json.loads(vote_ruling())
        draft = pipeline.JudgeDraft(
            index=1,
            kind=pipeline.DRAFT_SAMPLED,
            temperature=0.7,
            seed=101,
            sides=pipeline.DRIVER_FIRST,
            entries=(0,),
            ruling=ruling,
            key=pipeline.vote_key(ruling),
            unverifiable=("amount_sgd=4.0 (unverifiable: not structured)",),
        )

        written = draft.as_dict(agreeing=True)

        self.assertTrue(written["valid"])
        self.assertEqual(
            ["amount_sgd=4.0 (unverifiable: not structured)"], written["unverifiable"]
        )
        self.assertIsNotNone(written["proposal"])

    # -- the vote it feeds -------------------------------------------------
    def test_a_draft_that_fails_a_check_abstains_and_the_others_carry(self):
        result, _ = run_vote(
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(vote_ruling()),
            envelope(vote_ruling()),
            envelope(vote_ruling()),
            envelope(vote_ruling(amount=9.99)),
        )

        self.assertTrue(result.ok)
        self.assertEqual("PARTIAL_REFUND", result.ruling["ruling"]["ruling"])
        vote = result.judge_vote
        self.assertEqual(3, vote["valid"])
        self.assertEqual("carried_not_unanimous", vote["outcome"])
        abstained = [draft for draft in vote["drafts"] if not draft["valid"]]
        self.assertEqual(1, len(abstained))
        self.assertTrue(
            abstained[0]["abstention"].startswith(pipeline.DRAFT_AMOUNT_NOT_READ_OFF)
        )
        self.assertEqual([], abstained[0]["unverifiable"])
        self.assertIsNone(abstained[0]["proposal"])
        self.assertIsNone(abstained[0]["agrees"])
        # It is a real call, so it is still on the transcript and still billed.
        self.assertEqual(1, len(abstained[0]["entries"]))

    def test_two_failing_drafts_leave_too_few_and_escalate(self):
        result, _ = run_vote(
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            envelope(vote_ruling()),
            envelope(vote_ruling()),
            envelope(vote_ruling(amount=9.99)),
            envelope(vote_ruling(amount=9.99)),
        )

        self.assertTrue(result.ok)
        self.assertEqual("ESCALATE", result.ruling["ruling"]["ruling"])
        self.assertEqual(2, result.judge_vote["valid"])
        self.assertEqual("escalated", result.judge_vote["outcome"])

    def test_four_failing_drafts_are_the_failure_they_have_always_been(self):
        """Nothing was answered, so nothing disagreed: the judge failed."""
        result, _ = run_vote(
            envelope(RIDER_CLAIMS),
            envelope(DRIVER_CLAIMS),
            *[envelope(vote_ruling(amount=9.99))] * 4,
        )

        self.assertFalse(result.ok)
        self.assertEqual(JUDGE, result.failed_agent)
        self.assertIsNone(result.ruling)
        self.assertEqual("no_valid_drafts", result.judge_vote["outcome"])


class JudgePromptAmountsTests(unittest.TestCase):
    """Step 3 tells the judge where an amount comes from.

    A draft's money is now checked against the brief's own calculator, so the
    prompt has to say where the calculator publishes its figures. Otherwise the
    judge is held to a standard it was never told about, which is the failure
    mode this repository has already paid for once.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (pipeline.PROMPTS_DIR / JUDGE_PROMPT_FILE).read_text(encoding="utf-8")
        cls.section = step_three_section(cls.text)

    def test_the_money_block_is_named(self):
        self.assertIn("read off the brief's money block", self.section)

    def test_a_stated_sum_of_its_figures_is_allowed(self):
        self.assertIn("a stated sum of its figures", self.section)

    def test_the_explanation_names_the_figures_used(self):
        self.assertIn("names the figures you used", self.section)

    def test_it_sits_inside_step_three_and_adds_no_field(self):
        self.assertIn(_STEP_THREE_HEADING, self.text)
        self.assertIn("exactly two top-level fields", self.section)
        self.assertIn("Do not add any other top-level field", self.section)


# --------------------------------------------------------------------------
# The draft verifier
#
# Off by default, and one call per case when it is on. Every test here scripts
# the transport: no network, and no model call. The verifier is answered from
# the statements it was handed rather than from a fixed script, because which
# statements exist is the extraction's decision -- a test that wants "draft 1's
# fact is contradicted" cannot know that statement's number until it has run.
# --------------------------------------------------------------------------
VERIFIER_EVIDENCE = "EV-GPS-00208"

# One sentence carrying every kind the extractor knows: a money figure, an
# evidence id, a bare number, a distance and a clock time.
FACTUAL_EXPLANATION = "The fare was S$4.35 per EV-GPS-00208, 229 fixes over 250 m at 14:32."
# No number, time, distance, money figure or evidence id: not a statement of
# fact, so it is never sent.
PLAIN_EXPLANATION = "The driver was at fault and no figure settles it."


class VerifierTransport:
    """Scripted advocate and judge answers, and a verifier that answers itself.

    ``verdict_for`` receives one statement as the verifier is shown it -- ``n``,
    ``draft`` and ``text`` -- so a test can contradict one draft's fact without
    knowing its number. ``raw`` scripts a body verbatim and ``numbers`` scripts
    the statement numbers answered, which are the two ways the answer can be
    unusable: a body the prompt's shape does not admit, and a body that does not
    cover every statement exactly once.
    """

    def __init__(self, *responses, verdict_for=None, raw=None, numbers=None):
        self.responses = list(responses)
        self.verdict_for = verdict_for or (lambda item: pipeline.VERDICT_SUPPORTED)
        self.raw = raw
        self.numbers = numbers
        self.calls = []
        self.verifier_requests = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "body": body})
        request = json.loads(body.decode("utf-8"))
        parsed = json.loads(request["messages"][1]["content"])
        if isinstance(parsed, dict) and "brief" in parsed and "statements" in parsed:
            self.verifier_requests.append(parsed)
            return envelope(self._answer(parsed["statements"]))
        if not self.responses:
            raise AssertionError("VerifierTransport ran out of scripted responses")
        return self.responses.pop(0)

    def _answer(self, statements):
        if self.raw is not None:
            return self.raw
        by_number = {item["n"]: item for item in statements}
        numbers = (
            [item["n"] for item in statements] if self.numbers is None else self.numbers
        )
        return json.dumps(
            {
                "verdicts": [
                    {
                        "statement": number,
                        "verdict": self.verdict_for(
                            by_number.get(number, {"n": number, "draft": 0, "text": ""})
                        ),
                        "evidence": VERIFIER_EVIDENCE,
                    }
                    for number in numbers
                ]
            }
        )


def run_verified(*responses, votes=4, **options):
    """A full run with the verifier switched on, and the transport it used."""
    transport = VerifierTransport(*responses, **options)
    client = llm.LLMClient(
        model="hy4-preview",
        api_key=FAKE_KEY,
        transport=transport,
        sleep=lambda seconds: None,
        clock=lambda: 0.0,
    )
    result = pipeline.run_case(
        CASE, client, now=lambda: PINNED_NOW, judge_votes=votes, verify_drafts=True
    )
    return result, transport


def judge_drafts(*explanations):
    """One judge answer per explanation, in the order the drafts are made."""
    return tuple(envelope(vote_ruling(explanation=text)) for text in explanations)


class VerifierCallTests(unittest.TestCase):
    """One call per case, whatever the number of drafts or statements."""

    ADVOCATES = (envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS))

    def test_one_call_covers_four_drafts(self):
        result, transport = run_verified(
            *self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4)
        )

        self.assertTrue(result.ok)
        self.assertEqual(4, result.judge_vote["valid"])
        self.assertEqual(1, len(transport.verifier_requests))
        self.assertEqual(4, len(transport.verifier_requests[0]["statements"]))

    def test_one_call_covers_two_drafts(self):
        result, transport = run_verified(
            *self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 2), votes=2
        )

        self.assertTrue(result.ok)
        self.assertEqual(2, result.judge_vote["valid"])
        self.assertEqual(1, len(transport.verifier_requests))

    def test_one_call_covers_every_statement_the_drafts_state(self):
        rich = (
            "The fare was S$4.35 per EV-GPS-00208. "
            "The trace ran 250 m. The pickup was at 14:32."
        )
        result, transport = run_verified(
            *self.ADVOCATES, *judge_drafts(*[rich] * 3), votes=3
        )

        self.assertEqual(1, len(transport.verifier_requests))
        asked = transport.verifier_requests[0]["statements"]
        self.assertEqual(9, len(asked), "three drafts, three facts each")
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8, 9], [item["n"] for item in asked])
        self.assertEqual([1, 1, 1, 2, 2, 2, 3, 3, 3], [item["draft"] for item in asked])
        # The kinds are this package's own bookkeeping: they stay out of the ask.
        self.assertEqual({"n", "draft", "text"}, set(asked[0]))

    def test_the_verifier_is_asked_once_and_after_every_draft(self):
        result, transport = run_verified(
            *self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4)
        )

        self.assertEqual(
            [RIDER, DRIVER, JUDGE, JUDGE, JUDGE, JUDGE, transcript_module.ROLE_VERIFIER],
            roles_of(result),
        )
        self.assertEqual(1, roles_of(result).count(transcript_module.ROLE_VERIFIER))

    def test_no_call_is_made_when_the_drafts_state_no_checkable_fact(self):
        result, transport = run_verified(
            *self.ADVOCATES, *judge_drafts(*[PLAIN_EXPLANATION] * 4)
        )

        self.assertTrue(result.ok)
        self.assertEqual([], transport.verifier_requests)
        self.assertEqual([RIDER, DRIVER, JUDGE, JUDGE, JUDGE, JUDGE], roles_of(result))
        self.assertFalse(result.verification["called"])
        self.assertEqual([], result.verification["statements"])
        self.assertTrue(result.verification["reason"], "a reason is recorded")

    def test_a_draft_that_already_abstained_is_not_asked_about(self):
        # Three usable drafts, then a fourth whose answer is not a POL-GEN-03
        # object. An unusable answer is retried once, so it takes two scripted
        # responses.
        result, transport = run_verified(
            *self.ADVOCATES,
            *judge_drafts(*[FACTUAL_EXPLANATION] * 3),
            envelope("{}"),
            envelope("{}"),
        )

        self.assertEqual(3, result.judge_vote["valid"])
        self.assertEqual(1, len(transport.verifier_requests))
        asked = transport.verifier_requests[0]["statements"]
        self.assertEqual(3, len(asked), "the abstaining draft states nothing")
        self.assertEqual([1, 2, 3], sorted({item["draft"] for item in asked}))

    def test_the_verifier_is_handed_the_prompt_file(self):
        result, transport = run_verified(
            *self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4)
        )

        request = json.loads(transport.calls[-1]["body"].decode("utf-8"))
        self.assertEqual(
            (pipeline.PROMPTS_DIR / pipeline.VERIFIER_PROMPT_FILE).read_text(
                encoding="utf-8"
            ),
            request["messages"][0]["content"],
        )

    def test_the_verifier_reads_the_same_brief_bytes_the_judge_read(self):
        """The input is the brief the judge saw, not a re-serialisation of it."""
        result, transport = run_verified(
            *self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4)
        )

        bodies = [
            json.loads(call["body"].decode("utf-8"))["messages"][1]["content"]
            for call in transport.calls
        ]
        judge = next(text for text in bodies if ',"claims":' in text)
        verifier = bodies[-1]

        # Both messages are built as '{"brief":' + brief_json + ..., so the brief
        # is the same characters exactly when the two slices are equal.
        self.assertEqual(
            judge[len('{"brief":') : judge.index(',"claims":')],
            verifier[len('{"brief":') : verifier.index(',"statements":')],
        )


class VerifierMessageTests(unittest.TestCase):
    """What the verifier is asked, built by code and checkable as text."""

    STATEMENT = {"n": 1, "draft": 1, "text": "The fare was S$4.35.", "kinds": ["money"]}

    def test_the_brief_is_spliced_rather_than_re_serialised(self):
        brief_json = '{"case":{"case_no":208}}'

        message = pipeline.verifier_user_message(brief_json, [self.STATEMENT])

        self.assertTrue(message.startswith('{"brief":' + brief_json + ',"statements":'))

    def test_only_the_number_the_draft_and_the_text_travel(self):
        sent = json.loads(pipeline.verifier_user_message("{}", [self.STATEMENT]))

        self.assertEqual(
            {"n": 1, "draft": 1, "text": "The fare was S$4.35."},
            sent["statements"][0],
        )
        self.assertNotIn("kinds", sent["statements"][0])


class VerifierVerdictTests(unittest.TestCase):
    """A contradiction stops its draft voting; an absent fact does not."""

    ADVOCATES = (envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS))

    @staticmethod
    def drafts(count=4):
        return judge_drafts(*[FACTUAL_EXPLANATION] * count)

    @staticmethod
    def draft_record(result, index):
        return next(
            draft for draft in result.judge_vote["drafts"] if draft["draft"] == index
        )

    def test_a_contradicted_statement_makes_its_draft_abstain(self):
        result, _ = run_verified(
            *self.ADVOCATES,
            *self.drafts(),
            verdict_for=lambda item: (
                pipeline.VERDICT_CONTRADICTED
                if item["draft"] == 1
                else pipeline.VERDICT_SUPPORTED
            ),
        )

        self.assertTrue(result.ok)
        self.assertEqual([1], result.verification["abstained"])
        self.assertEqual(3, result.judge_vote["valid"])
        self.assertEqual("carried_not_unanimous", result.judge_vote["outcome"])
        self.assertEqual(0.75, result.vote_agreement)
        # The verifier decides no part of the ruling.
        self.assertEqual("PARTIAL_REFUND", result.ruling["ruling"]["ruling"])

        record = self.draft_record(result, 1)
        self.assertFalse(record["valid"])
        self.assertIsNone(record["proposal"])
        self.assertIsNone(record["agrees"])
        # The statement it was charged with is quoted, so a reader can see which
        # fact was rejected.
        self.assertTrue(
            record["abstention"].startswith(
                pipeline.ABSTENTION_CONTRADICTED + ": "
            ),
            record["abstention"],
        )
        self.assertIn(FACTUAL_EXPLANATION, record["abstention"])

    def test_a_contradiction_on_three_drafts_leaves_too_few_and_escalates(self):
        result, _ = run_verified(
            *self.ADVOCATES,
            *self.drafts(),
            verdict_for=lambda item: (
                pipeline.VERDICT_CONTRADICTED
                if item["draft"] <= 3
                else pipeline.VERDICT_SUPPORTED
            ),
        )

        self.assertEqual([1, 2, 3], result.verification["abstained"])
        self.assertEqual(1, result.judge_vote["valid"])
        self.assertEqual("escalated", result.judge_vote["outcome"])
        self.assertEqual("ESCALATE", result.ruling["ruling"]["ruling"])
        self.assertIsNone(result.ruling["ruling"]["amount_sgd"])

    def test_a_contradiction_on_every_draft_leaves_no_ruling_at_all(self):
        result, _ = run_verified(
            *self.ADVOCATES,
            *self.drafts(),
            verdict_for=lambda item: pipeline.VERDICT_CONTRADICTED,
        )

        self.assertEqual([1, 2, 3, 4], result.verification["abstained"])
        self.assertEqual(0, result.judge_vote["valid"])
        self.assertEqual("no_valid_drafts", result.judge_vote["outcome"])
        self.assertIsNone(result.vote_agreement)
        self.assertIsNone(result.ruling)

    def test_a_statement_not_in_evidence_is_recorded_and_the_draft_still_votes(self):
        result, _ = run_verified(
            *self.ADVOCATES,
            *self.drafts(),
            verdict_for=lambda item: pipeline.VERDICT_NOT_IN_EVIDENCE,
        )

        self.assertTrue(result.ok)
        self.assertEqual([], result.verification["abstained"])
        self.assertEqual(4, result.judge_vote["valid"])
        self.assertEqual("carried", result.judge_vote["outcome"])
        self.assertEqual(1.0, result.vote_agreement)
        self.assertEqual(
            {pipeline.VERDICT_NOT_IN_EVIDENCE},
            {item["verdict"] for item in result.verification["judged"]},
        )

        # Recorded and flagged, and nothing else: the draft is still an answer.
        record = self.draft_record(result, 1)
        self.assertTrue(record["valid"])
        self.assertIsNone(record["abstention"])
        self.assertEqual([], record["verification"]["contradicted"])
        self.assertEqual(1, len(record["verification"]["not_in_evidence"]))

    def test_every_verdict_is_charged_to_the_draft_that_stated_it(self):
        result, _ = run_verified(
            *self.ADVOCATES,
            *self.drafts(),
            verdict_for=lambda item: pipeline.VERDICT_SUPPORTED,
        )

        judged = result.verification["judged"]
        self.assertEqual([1, 2, 3, 4], [item["n"] for item in judged])
        self.assertEqual([1, 2, 3, 4], [item["draft"] for item in judged])
        for item in judged:
            with self.subTest(statement=item["n"]):
                self.assertEqual(FACTUAL_EXPLANATION, item["text"])
                self.assertEqual(VERIFIER_EVIDENCE, item["evidence"])


class VerifierUnusableAnswerTests(unittest.TestCase):
    """A verifier that cannot answer is no verification, never a silent change."""

    ADVOCATES = (envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS))

    def unchanged(self, **options):
        """Run with the verifier on, and hold it to changing nothing."""
        result, transport = run_verified(
            *self.ADVOCATES,
            *judge_drafts(*[FACTUAL_EXPLANATION] * 4),
            **options,
        )

        self.assertTrue(result.verification["called"], "the verifier was called")
        self.assertFalse(result.verification["usable"])
        self.assertTrue(result.verification["reason"], "a reason is recorded")
        self.assertEqual([], result.verification["abstained"])
        self.assertEqual([], result.verification["judged"])
        # Every draft keeps its vote.
        self.assertEqual(4, result.judge_vote["valid"])
        self.assertEqual("carried", result.judge_vote["outcome"])
        self.assertEqual(1.0, result.vote_agreement)
        self.assertTrue(result.ok)
        return result, transport

    def test_a_body_that_is_not_json_is_no_verification(self):
        result, transport = self.unchanged(raw="the verifier did not answer in JSON")

        self.assertEqual(1, len(transport.verifier_requests))

    def test_a_json_body_of_the_wrong_shape_is_no_verification(self):
        for raw in ("[]", '{"verdicts": {}}', '{"verdicts": [{"statement": "one"}]}'):
            with self.subTest(raw=raw):
                self.unchanged(raw=raw)

    def test_a_body_that_misses_a_statement_is_no_verification(self):
        # The control: the same body, covering every statement, is usable. Only
        # the coverage differs, so the coverage is what the refusal is about.
        complete, _ = run_verified(
            *self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4)
        )
        self.assertTrue(complete.verification["usable"])

        result, transport = self.unchanged(numbers=[1, 2, 3])

        self.assertEqual(4, len(transport.verifier_requests[0]["statements"]))

    def test_a_body_that_answers_a_statement_twice_is_no_verification(self):
        self.unchanged(numbers=[1, 1, 2, 3])


class StatementExtractionTests(unittest.TestCase):
    """Code, not the model, decides which sentences are checkable facts."""

    def kinds_of(self, sentence):
        found = pipeline.extract_factual_statements(sentence)
        self.assertEqual(1, len(found), "one sentence in, one statement out")
        return found[0][1]

    def test_a_money_figure_is_a_fact(self):
        self.assertIn(
            pipeline.STATEMENT_KIND_MONEY, self.kinds_of("The fare was S$4.35.")
        )

    def test_a_bare_number_is_a_fact(self):
        self.assertIn(
            pipeline.STATEMENT_KIND_NUMBER, self.kinds_of("The trace holds 229 fixes.")
        )

    def test_a_distance_is_a_fact(self):
        self.assertIn(
            pipeline.STATEMENT_KIND_DISTANCE, self.kinds_of("The gantry was 250 m away.")
        )

    def test_a_clock_time_is_a_fact(self):
        self.assertIn(
            pipeline.STATEMENT_KIND_TIME, self.kinds_of("The pickup was at 14:32.")
        )

    def test_a_duration_is_a_fact(self):
        self.assertIn(
            pipeline.STATEMENT_KIND_TIME, self.kinds_of("It sampled every 10 s.")
        )

    def test_a_date_is_a_fact(self):
        self.assertIn(
            pipeline.STATEMENT_KIND_TIME, self.kinds_of("It happened on 2026-09-21.")
        )

    def test_an_evidence_id_is_a_fact(self):
        self.assertIn(
            pipeline.STATEMENT_KIND_EVIDENCE_ID,
            self.kinds_of("The trace is EV-GPS-00101."),
        )

    def test_a_sentence_with_no_fact_is_not_extracted(self):
        text = "The driver was at fault and the rider did nothing wrong."

        self.assertEqual([], pipeline.extract_factual_statements(text))

    def test_the_factless_sentence_between_two_facts_is_dropped(self):
        text = (
            "The fare was S$4.35.\n"
            "The driver was at fault.\n"
            "The trace is EV-GPS-00101."
        )

        found = pipeline.extract_factual_statements(text)

        self.assertEqual(
            ["The fare was S$4.35.", "The trace is EV-GPS-00101."],
            [item[0] for item in found],
        )

    def test_a_passage_that_is_not_text_states_nothing(self):
        self.assertEqual([], pipeline.extract_factual_statements(""))
        self.assertEqual([], pipeline.extract_factual_statements(None))


class StatementNumberingTests(unittest.TestCase):
    """The numbering runs across the drafts, and each entry names its own."""

    @staticmethod
    def draft(index, explanation, usable=True):
        return pipeline.JudgeDraft(
            index=index,
            kind=pipeline.DRAFT_SAMPLED,
            temperature=0.7,
            seed=100 + index,
            sides=pipeline.DRIVER_FIRST,
            entries=(index,),
            ruling={"ruling": {"explanation": explanation}},
            key=("PARTIAL_REFUND", Decimal("4.0"), None, ()) if usable else None,
            abstention=None if usable else "unusable",
        )

    def test_the_numbering_runs_across_drafts_and_names_each_one(self):
        numbered = pipeline.numbered_statements(
            [
                self.draft(1, "The fare was S$4.35."),
                self.draft(2, "The trace is EV-GPS-00101."),
            ]
        )

        self.assertEqual([1, 2], [item["n"] for item in numbered])
        self.assertEqual([1, 2], [item["draft"] for item in numbered])
        self.assertEqual("The fare was S$4.35.", numbered[0]["text"])
        self.assertEqual(["number", "money"], numbered[0]["kinds"])

    def test_a_draft_that_already_abstained_states_nothing(self):
        numbered = pipeline.numbered_statements(
            [
                self.draft(1, "The fare was S$4.35.", usable=False),
                self.draft(2, "The trace is EV-GPS-00101."),
            ]
        )

        self.assertEqual([1], [item["n"] for item in numbered])
        self.assertEqual([2], [item["draft"] for item in numbered])

    def test_a_draft_with_no_explanation_states_nothing(self):
        self.assertEqual([], pipeline.numbered_statements([self.draft(1, None)]))


class VerifierTokenTests(unittest.TestCase):
    """The verifier's usage is its own, on its own entry and under its own role."""

    ADVOCATES = (envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS))

    def test_the_verifier_tokens_are_recorded_apart_from_the_judges(self):
        result, _ = run_verified(
            *self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4)
        )

        entries = result.transcript.entries
        verifier = [e for e in entries if e.role == transcript_module.ROLE_VERIFIER]
        judges = [e for e in entries if e.role == JUDGE]

        self.assertEqual(1, len(verifier))
        self.assertEqual(4, len(judges))
        # The rig scripts 10 prompt and 5 completion tokens per call.
        self.assertEqual(10, verifier[0].prompt_tokens)
        self.assertEqual(5, verifier[0].completion_tokens)
        self.assertEqual(
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "reasoning_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 15,
            },
            result.verification["tokens"],
        )
        # Counted apart: the judges' own total does not carry the verifier's.
        self.assertEqual(40, result.transcript.totals(judges)["prompt_tokens"])
        self.assertEqual(10, result.transcript.totals(verifier)["prompt_tokens"])
        # And it is in the case's bill, because the call was made.
        self.assertEqual(70, result.prompt_tokens)


class VerifierSwitchTests(unittest.TestCase):
    """Off is the default, and off adds nothing to a run's own record."""

    ADVOCATES = (envelope(RIDER_CLAIMS), envelope(DRIVER_CLAIMS))

    def off(self):
        return run_vote(*self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4))

    def on(self):
        return run_verified(*self.ADVOCATES, *judge_drafts(*[FACTUAL_EXPLANATION] * 4))

    def test_the_switch_off_asks_no_verifier_and_records_none(self):
        result, transport = self.off()

        self.assertIsNone(result.verification)
        self.assertEqual([RIDER, DRIVER, JUDGE, JUDGE, JUDGE, JUDGE], roles_of(result))
        self.assertEqual(6, len(transport.calls))

    def test_the_switch_off_puts_no_verification_key_anywhere(self):
        result, _ = self.off()
        payload = json.loads(result.transcript_json)

        self.assertNotIn("verification", payload)
        self.assertNotIn("verification", payload["vote"])
        for draft in payload["vote"]["drafts"]:
            with self.subTest(draft=draft["draft"]):
                self.assertNotIn("verification", draft)

    def test_the_switch_off_writes_the_keys_the_record_had_before_it_existed(self):
        """The draft record is the one the committed transcripts carry.

        These key sets are read off the transcripts under ``runs/``, which were
        written before the verifier existed. A key added here would move every
        recorded transcript digest, so a new one has to be a deliberate act.
        """
        result, _ = self.off()
        payload = json.loads(result.transcript_json)

        self.assertEqual(
            {"entries", "referee", "vote"},
            set(payload),
        )
        self.assertEqual(
            {
                "abstention",
                "agrees",
                "draft",
                "entries",
                "kind",
                "proposal",
                "seed",
                "sides",
                "temperature",
                "unverifiable",
                "valid",
            },
            set(payload["vote"]["drafts"][0]),
        )

    def test_the_switch_on_adds_exactly_one_key_and_one_entry(self):
        off_result, _ = self.off()
        on_result, _ = self.on()
        off_payload = json.loads(off_result.transcript_json)
        on_payload = json.loads(on_result.transcript_json)

        self.assertEqual({"verification"}, set(on_payload) - set(off_payload))
        self.assertEqual(set(), set(off_payload) - set(on_payload))
        self.assertEqual(
            {"verification"}, set(on_payload["vote"]) - set(off_payload["vote"])
        )
        self.assertEqual(
            {"verification"},
            set(on_payload["vote"]["drafts"][0]) - set(off_payload["vote"]["drafts"][0]),
        )
        # The verifier's entry is appended, so the run's own entries are byte for
        # byte what they were.
        self.assertEqual(
            off_payload["entries"],
            on_payload["entries"][: len(off_payload["entries"])],
        )
        self.assertEqual(len(off_payload["entries"]) + 1, len(on_payload["entries"]))

    def test_the_switch_off_reaches_the_same_ruling_and_agreement(self):
        off_result, _ = self.off()
        on_result, _ = self.on()

        self.assertEqual(off_result.ruling, on_result.ruling)
        self.assertEqual(off_result.vote_agreement, on_result.vote_agreement)
        # The one difference in the bill is the verifier's own call.
        self.assertEqual(off_result.prompt_tokens, on_result.prompt_tokens - 10)

    def test_the_switch_needs_a_panel_to_verify(self):
        transport = VerifierTransport(*self.ADVOCATES, envelope(vote_ruling()))
        client = llm.LLMClient(
            model="hy4-preview",
            api_key=FAKE_KEY,
            transport=transport,
            sleep=lambda seconds: None,
            clock=lambda: 0.0,
        )

        with self.assertRaises(pipeline.PipelineError):
            pipeline.run_case(
                CASE,
                client,
                now=lambda: PINNED_NOW,
                judge_votes=1,
                verify_drafts=True,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
