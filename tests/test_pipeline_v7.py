"""Policy version 7: v2.1's decision gates, in the pipeline.

Part 71 gave the version-7 brief ``case.authority`` -- the value band, the bar a
ruling needs, whether the dispute is a person's whatever the drafts say, and a
route deviation's own ceiling. This module holds the pipeline to it.

Three things are checked here, and each is checked **at version 6 as well**:

* **the bar.** ``confidence_floor`` reads POL-RD-10(1) and POL-NS-09(a), which
  version 7 does not carry. At version 7 :func:`tribunal.pipeline.required_confidence`
  reads ``case.authority.required_confidence`` instead -- 0.80 from 10.00 to
  50.00 SGD, 0.95 where a party carries a fraud flag, 0.80 for a route deviation,
  and none below the first band -- and a draft under it is voided exactly as
  ``DRAFT_BELOW_FLOOR`` voids one. A panel whose every draft is below it
  escalates citing POL-GEN-26.
* **the human-only gate.** Where ``case.authority.human_only`` is true -- a value
  above POL-GEN-22's second band edge, or a safety flag -- the ruling is an
  ``ESCALATE`` whatever a draft would have said, citing POL-GEN-21 or POL-GEN-22.
  The advocates still run: v2.1 6.1's "AI agent prepares case file only" is a
  statement about who decides, not about who is asked.
* **the 2 km limb.** POL-RD-25's ceiling fires only where the policy's own
  switch says it applies; while ``ai_ruling_max_deviation_applied`` is false it
  never does, and the reading travels in the brief instead.

No model call is made: every answer comes from a scripted transport. No test
writes under ``runs/``. Run from the project root with::

    python -m unittest tests.test_pipeline_v7 -v
"""

from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import brief as brief_module  # noqa: E402
from tribunal import llm, loader, money, pipeline, transcript  # noqa: E402

VERSION_SEVEN = 7
VERSION_SIX = 6

# ``prompts/v2`` is the version-7 prompt set; a version-7 invocation is held to
# it by ``eval.run_benchmark``'s guard. The pipeline itself takes a directory,
# and these tests pass the set a version-7 run would be given.
PROMPTS_V2 = PROJECT_ROOT / "prompts" / "v2"

# The cases these tests are built on, and why each one.
#
# * 104 is a route deviation with a contested value of 14.00 -- POL-GEN-22's
#   middle band -- so its bar is POL-RD-25's 0.80.
# * 105 is a route deviation with a contested value of 65.13, above POL-GEN-22's
#   second band edge, so ``human_only`` is true on the value alone.
# * 201 is a no-show with a contested value of 4.00, below the first band, where
#   POL-NS-26 makes the AI ruling final and the bar is none at all.
MIDDLE_BAND_CASE = 104
HUMAN_ONLY_CASE = 105
FINAL_BAND_CASE = 201

# The per-kilometre rate and the deviation distance case 104's own money block
# carries. Neither is an amount: POL-RD-24 multiplies one by the other to get
# the excess distance fare, and a draft that read either off as its amount would
# be claiming the multiplier as its product. Both are read out of the built
# brief rather than typed here -- see :func:`money_figures`.
EXCESS_FARE_CASE = 104


def version_seven_brief(case_no: int, case: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """One case's version-7 brief, from the corpus or from a fixture."""
    loaded = loader.load_case(case_no) if case is None else case
    return brief_module.build_brief_for_case(loaded, policy_version=VERSION_SEVEN)


def version_six_brief(case_no: int) -> Dict[str, Any]:
    """The same case at version 6, which is what the floor is read from there."""
    return brief_module.build_brief_for_case(
        loader.load_case(case_no), policy_version=VERSION_SIX
    )


def with_rider_fraud_flag(case_no: int) -> Dict[str, Any]:
    """A corpus case with ``fraud_flags`` set on the rider's profile.

    The counter is the only thing added. POL-GEN-22 raises the bar to 0.95
    "where either party's profile carries fraud_flags of 1 or more", so this is
    the input that decides whether the raised bar is read at all.
    """
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


def with_safety_flag(case_no: int) -> Dict[str, Any]:
    """A corpus case whose dispute carries ``safety_flag``."""
    case = dict(loader.load_case(case_no))
    dispute = dict(case["dispute"])
    dispute["safety_flag"] = True
    case["dispute"] = dispute
    return case


def with_ai_limit_applied(brief_object: Dict[str, Any]) -> Dict[str, Any]:
    """A version-7 brief whose authority block says the 2 km limb applies.

    The policy ships ``ai_ruling_max_deviation_applied`` false -- v2.1 6.2's
    ceiling is held pending Ryde's answer to C1 -- so the gate it guards cannot
    fire on a case built from the shipped files. This flips the two leaves the
    gate reads, and nothing else, so the gate itself is what is under test.
    """
    authority = dict(brief_object["case"]["authority"])
    for key in ("ai_limit_applied", "over_ai_limit"):
        leaf = dict(authority[key])
        leaf["value"] = True
        authority[key] = leaf
    case = dict(brief_object["case"])
    case["authority"] = authority
    amended = dict(brief_object)
    amended["case"] = case
    return amended


def ruling_object(
    value: str = "NO_ACTION",
    amount: Optional[str] = None,
    compensation: Optional[str] = None,
    confidence: Optional[str] = None,
    referrals: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """One judge draft, in the shape the judge is held to.

    ``NO_ACTION`` is used by default because it is the one ruling that requires
    no amount and forbids none, so a draft built here fails on its confidence or
    on nothing at all -- which is what makes the bar's own effect readable.
    """
    return {
        "ruling": value,
        "amount_sgd": None if amount is None else Decimal(amount),
        "driver_compensation_sgd": None if compensation is None else Decimal(compensation),
        "referrals": list(referrals or []),
        "confidence": None if confidence is None else Decimal(confidence),
        "explanation": "The draft states its reasoning without citing a clause.",
    }


def draft(ruling: Mapping[str, Any]) -> Dict[str, Any]:
    """One draft in the shape :func:`check_judge_draft` is handed."""
    return {"ruling": dict(ruling), "discarded_claims": []}


def failures_for(ruling: Mapping[str, Any], brief_object: Any, version: int) -> Tuple[str, ...]:
    """The codes one draft abstains on, under one version's bar."""
    found, _unverifiable = pipeline.check_judge_draft(
        draft(ruling), brief_object, pipeline.DEFAULT_AMOUNT_RULE, version
    )
    return found


def money_figures(brief_object: Mapping[str, Any]) -> Dict[str, Decimal]:
    """The money block's numeric leaves by name, for the values a test needs.

    Read out of the block rather than typed here, so a test that says "a draft
    whose amount equals the per-kilometre rate" is naming the figure the brief
    actually publishes.
    """
    block = pipeline.money_block(brief_object)
    found: Dict[str, Decimal] = {}
    for path, amount in pipeline._money_leaves(block):
        found[pipeline._figure_name(path)] = amount
    return found


class GateTransport:
    """A transport that answers the advocates and scripts the judge.

    The advocates get the rig's bare claim array; the judge gets one ruling from
    ``rulings`` per call, in order. Every request is recorded, so a test can say
    which agents were asked as well as what came back. No network, no model.
    """

    def __init__(self, rulings: Sequence[Mapping[str, Any]] = ()) -> None:
        self.rulings = [dict(item) for item in rulings]
        self.roles: List[Tuple[int, str]] = []
        self.requests: List[Dict[str, Any]] = []

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        case_no, role = rig.role_of(request)
        self.requests.append(request)
        self.roles.append((case_no, role))
        if role == transcript.ROLE_JUDGE:
            index = len(self.roles_for(case_no, transcript.ROLE_JUDGE)) - 1
            ruling = self.rulings[min(index, len(self.rulings) - 1)]
            content = money.dumps_canonical({"ruling": ruling, "discarded_claims": []})
        else:
            content = rig.CLAIM_ARRAY
        payload = {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": rig.PROMPT_TOKENS,
                "completion_tokens": rig.COMPLETION_TOKENS,
                "completion_tokens_details": {"reasoning_tokens": rig.REASONING_TOKENS},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
        return llm.HttpResult(status=200, body=json.dumps(payload).encode("utf-8"))

    def roles_for(self, case_no: int, role: Optional[str] = None) -> List[str]:
        return [
            name
            for number, name in self.roles
            if number == case_no and (role is None or name == role)
        ]

    def calls(self) -> int:
        return len(self.requests)


def run_case(
    case_no: int,
    transport: GateTransport,
    *,
    version: int,
    case: Optional[Mapping[str, Any]] = None,
    brief_patch: Optional[Any] = None,
) -> Any:
    """One full arbitration over the scripted transport, and nothing else.

    ``brief_patch`` replaces the brief builder for the duration of the call,
    which is how the 2 km limb -- held behind a switch in the policy file -- is
    exercised without editing the policy. It is ``None`` for every test that
    asks the shipped files.
    """
    loaded = loader.load_case(case_no) if case is None else case
    client = rig.client_factory(rig.MODEL, transport)(None)
    if brief_patch is None:
        return pipeline.run_loaded_case(
            loaded,
            client,
            prompts_dir=PROMPTS_V2,
            judge_votes=4,
            policy_version=version,
        )
    with mock.patch.object(brief_module, "build_brief_for_case", brief_patch):
        return pipeline.run_loaded_case(
            loaded,
            client,
            prompts_dir=PROMPTS_V2,
            judge_votes=4,
            policy_version=version,
        )


# --------------------------------------------------------------------------
# 1. The bar
# --------------------------------------------------------------------------
class TheVersionSevenBarTests(unittest.TestCase):
    """``case.authority.required_confidence`` is the bar at version 7."""

    def test_the_bar_is_read_from_the_brief_at_version_seven(self):
        middle = version_seven_brief(MIDDLE_BAND_CASE)
        bar, references = pipeline.required_confidence(middle, VERSION_SEVEN)
        self.assertEqual(Decimal("0.80"), bar)
        self.assertEqual(("POL-RD-25",), references)

    def test_the_final_band_carries_no_bar(self):
        """Below POL-GEN-22's first band POL-NS-26 makes the AI ruling final."""
        final = version_seven_brief(FINAL_BAND_CASE)
        bar, references = pipeline.required_confidence(final, VERSION_SEVEN)
        self.assertEqual(Decimal("0.0"), bar)
        self.assertEqual(("POL-NS-26",), references)

    def test_the_fraud_flag_raises_the_bar_to_ninety_five(self):
        flagged = version_seven_brief(
            MIDDLE_BAND_CASE, with_rider_fraud_flag(MIDDLE_BAND_CASE)
        )
        bar, _references = pipeline.required_confidence(flagged, VERSION_SEVEN)
        self.assertEqual(Decimal("0.95"), bar)

    def test_a_version_seven_brief_with_no_authority_block_is_refused(self):
        """A bar that fell back to a number written in the code is not a bar."""
        bare = dict(version_seven_brief(MIDDLE_BAND_CASE))
        case = dict(bare["case"])
        case.pop("authority")
        bare["case"] = case
        with self.assertRaises(pipeline.PipelineError):
            pipeline.required_confidence(bare, VERSION_SEVEN)

    def test_a_draft_under_the_bar_is_voided_and_one_at_it_stands(self):
        middle = version_seven_brief(MIDDLE_BAND_CASE)
        below = failures_for(ruling_object(confidence="0.79"), middle, VERSION_SEVEN)
        at = failures_for(ruling_object(confidence="0.80"), middle, VERSION_SEVEN)
        self.assertEqual(1, len(below), below)
        self.assertTrue(below[0].startswith(pipeline.DRAFT_BELOW_FLOOR), below)
        self.assertIn("POL-RD-25", below[0])
        self.assertEqual((), at)

    def test_a_draft_under_the_raised_bar_is_voided_and_one_at_it_stands(self):
        flagged = version_seven_brief(
            MIDDLE_BAND_CASE, with_rider_fraud_flag(MIDDLE_BAND_CASE)
        )
        below = failures_for(ruling_object(confidence="0.94"), flagged, VERSION_SEVEN)
        at = failures_for(ruling_object(confidence="0.95"), flagged, VERSION_SEVEN)
        self.assertEqual(1, len(below), below)
        self.assertTrue(below[0].startswith(pipeline.DRAFT_BELOW_FLOOR), below)
        self.assertEqual((), at)

    def test_a_below_ten_case_stands_at_a_tenth(self):
        final = version_seven_brief(FINAL_BAND_CASE)
        self.assertEqual(
            (), failures_for(ruling_object(confidence="0.10"), final, VERSION_SEVEN)
        )

    def test_a_draft_amount_equal_to_the_per_km_rate_is_not_read_off(self):
        """A rate is context for a fare, not a fare."""
        middle = version_seven_brief(EXCESS_FARE_CASE)
        figures = money_figures(middle)
        rate = figures["per_km_rate_sgd"]
        found = failures_for(
            ruling_object(value="PARTIAL_REFUND", amount=str(rate), confidence="0.90"),
            middle,
            VERSION_SEVEN,
        )
        self.assertEqual(1, len(found), found)
        self.assertTrue(found[0].startswith(pipeline.DRAFT_AMOUNT_NOT_READ_OFF), found)

    def test_a_draft_amount_equal_to_the_deviation_distance_is_not_read_off(self):
        middle = version_seven_brief(EXCESS_FARE_CASE)
        distance = money_figures(middle)["deviation_km"]
        found = failures_for(
            ruling_object(value="PARTIAL_REFUND", amount=str(distance), confidence="0.90"),
            middle,
            VERSION_SEVEN,
        )
        self.assertEqual(1, len(found), found)
        self.assertTrue(found[0].startswith(pipeline.DRAFT_AMOUNT_NOT_READ_OFF), found)

    def test_the_published_amounts_are_still_read_off(self):
        """The four the policy does publish are untouched by the exclusion."""
        middle = version_seven_brief(EXCESS_FARE_CASE)
        excess = money_figures(middle)["excess_distance_fare_sgd"]
        self.assertEqual(
            (),
            failures_for(
                ruling_object(
                    value="PARTIAL_REFUND", amount=str(excess), confidence="0.90"
                ),
                middle,
                VERSION_SEVEN,
            ),
        )


class TheVersionSixBarIsUntouchedTests(unittest.TestCase):
    """Every input above behaves at version 6 exactly as it did before."""

    def test_the_bar_is_still_the_version_six_floor(self):
        middle = version_six_brief(MIDDLE_BAND_CASE)
        bar, references = pipeline.required_confidence(middle, VERSION_SIX)
        self.assertEqual(Decimal("0.70"), bar)
        self.assertEqual(("POL-RD-10(1)",), references)

    def test_a_draft_under_the_version_six_floor_is_voided_and_one_at_it_stands(self):
        middle = version_six_brief(MIDDLE_BAND_CASE)
        below = failures_for(ruling_object(confidence="0.69"), middle, VERSION_SIX)
        at = failures_for(ruling_object(confidence="0.70"), middle, VERSION_SIX)
        self.assertEqual(1, len(below), below)
        self.assertTrue(below[0].startswith(pipeline.DRAFT_BELOW_FLOOR), below)
        self.assertEqual((), at)

    def test_a_seventy_nine_draft_stands_at_version_six(self):
        """The same draft the version-7 bar voids, at the floor it always had."""
        middle = version_six_brief(MIDDLE_BAND_CASE)
        self.assertEqual(
            (), failures_for(ruling_object(confidence="0.79"), middle, VERSION_SIX)
        )

    def test_a_fraud_flag_does_not_raise_the_version_six_bar(self):
        flagged = brief_module.build_brief_for_case(
            with_rider_fraud_flag(MIDDLE_BAND_CASE), policy_version=VERSION_SIX
        )
        self.assertEqual(
            (), failures_for(ruling_object(confidence="0.80"), flagged, VERSION_SIX)
        )

    def test_the_version_six_money_block_is_unmoved(self):
        """The five names added to NOT_MONEY_FIGURES are not version-6 leaves."""
        figures = money_figures(version_six_brief(EXCESS_FARE_CASE))
        for name in ("per_km_rate_sgd", "deviation_km", "ai_limit_km"):
            with self.subTest(name=name):
                self.assertNotIn(name, figures)


# --------------------------------------------------------------------------
# 2. The human-only gate and the 2 km limb
# --------------------------------------------------------------------------
class TheAuthorityGateTests(unittest.TestCase):
    """The gate itself, on the brief it reads."""

    def test_a_value_above_the_second_band_is_human_only(self):
        case = loader.load_case(HUMAN_ONLY_CASE)
        gate = pipeline.authority_gate(case, version_seven_brief(HUMAN_ONLY_CASE))
        self.assertIsNotNone(gate)
        self.assertEqual(pipeline.V7_HUMAN_ONLY, gate["reason_code"])
        self.assertEqual(pipeline.V7_HUMAN_ONLY_CLAUSE, gate["clause"])

    def test_a_safety_flag_is_human_only_and_cites_pol_gen_21(self):
        case = with_safety_flag(MIDDLE_BAND_CASE)
        gate = pipeline.authority_gate(case, version_seven_brief(MIDDLE_BAND_CASE, case))
        self.assertIsNotNone(gate)
        self.assertEqual(pipeline.V7_HUMAN_ONLY, gate["reason_code"])
        self.assertEqual(pipeline.V7_SCOPE_GATE_CLAUSE, gate["clause"])
        self.assertEqual(["safety_flag"], gate["flags"])

    def test_a_middle_band_case_with_no_flag_trips_nothing(self):
        case = loader.load_case(MIDDLE_BAND_CASE)
        self.assertIsNone(
            pipeline.authority_gate(case, version_seven_brief(MIDDLE_BAND_CASE))
        )

    def test_the_two_km_limb_does_not_fire_while_the_policy_switch_is_false(self):
        case = loader.load_case(MIDDLE_BAND_CASE)
        self.assertIsNone(
            pipeline.authority_gate(case, version_seven_brief(MIDDLE_BAND_CASE))
        )

    def test_the_two_km_limb_fires_when_the_switch_is_true(self):
        case = loader.load_case(MIDDLE_BAND_CASE)
        applied = with_ai_limit_applied(version_seven_brief(MIDDLE_BAND_CASE))
        gate = pipeline.authority_gate(case, applied)
        self.assertIsNotNone(gate)
        self.assertEqual(pipeline.V7_AI_LIMIT, gate["reason_code"])
        self.assertEqual(pipeline.V7_AI_LIMIT_CLAUSE, gate["clause"])


class TheGateInThePipelineTests(unittest.TestCase):
    """What a gated case records, and which agents it asks."""

    def test_a_value_above_fifty_escalates_whatever_the_drafts_say(self):
        transport = GateTransport([ruling_object(confidence="0.99")])
        result = run_case(HUMAN_ONLY_CASE, transport, version=VERSION_SEVEN)
        self.assertTrue(result.ok)
        inner = result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertEqual(0.0, inner["confidence"])
        self.assertIsNone(inner["amount_sgd"])
        self.assertIsNone(inner["driver_compensation_sgd"])
        self.assertEqual([], inner["referrals"])
        self.assertEqual(pipeline.V7_HUMAN_ONLY_CLAUSE, result.scope_gate["clause"])
        self.assertEqual(pipeline.V7_HUMAN_ONLY, result.scope_gate["reason_code"])

    def test_a_safety_flagged_case_escalates_citing_pol_gen_21(self):
        case = with_safety_flag(MIDDLE_BAND_CASE)
        transport = GateTransport([ruling_object(confidence="0.99")])
        result = run_case(MIDDLE_BAND_CASE, transport, version=VERSION_SEVEN, case=case)
        inner = result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertIn("POL-GEN-21", inner["explanation"])
        self.assertEqual(pipeline.V7_SCOPE_GATE_CLAUSE, result.scope_gate["clause"])
        self.assertEqual(["safety_flag"], result.scope_gate["flags"])

    def test_the_advocates_run_and_the_judge_is_not_asked(self):
        transport = GateTransport([ruling_object(confidence="0.99")])
        run_case(HUMAN_ONLY_CASE, transport, version=VERSION_SEVEN)
        asked = transport.roles_for(HUMAN_ONLY_CASE)
        self.assertEqual(2, len(asked), asked)
        self.assertNotIn(transcript.ROLE_JUDGE, asked)

    def test_the_record_says_how_many_calls_were_made(self):
        transport = GateTransport([ruling_object(confidence="0.99")])
        result = run_case(HUMAN_ONLY_CASE, transport, version=VERSION_SEVEN)
        self.assertEqual(2, result.scope_gate["calls"])
        self.assertEqual(2, len(result.transcript.entries))
        self.assertGreater(result.prompt_tokens, 0)

    def test_the_two_km_gate_escalates_when_the_switch_is_on(self):
        transport = GateTransport([ruling_object(confidence="0.99")])
        # The real builder is captured before the patch, so the replacement
        # wraps it rather than calling itself.
        real = brief_module.build_brief_for_case

        def patched(case, *args, **kwargs):
            return with_ai_limit_applied(real(case, *args, **kwargs))

        result = run_case(
            MIDDLE_BAND_CASE, transport, version=VERSION_SEVEN, brief_patch=patched
        )
        inner = result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertIn(pipeline.V7_AI_LIMIT_CLAUSE, inner["explanation"])
        self.assertEqual(pipeline.V7_AI_LIMIT, result.scope_gate["reason_code"])
        self.assertNotIn(
            transcript.ROLE_JUDGE, transport.roles_for(MIDDLE_BAND_CASE)
        )

    def test_the_two_km_gate_does_not_fire_with_the_shipped_policy(self):
        """The switch is false, so the case reaches the judge and is decided."""
        transport = GateTransport([ruling_object(confidence="0.90")])
        result = run_case(MIDDLE_BAND_CASE, transport, version=VERSION_SEVEN)
        self.assertIsNone(result.scope_gate)
        self.assertIn(
            transcript.ROLE_JUDGE, transport.roles_for(MIDDLE_BAND_CASE)
        )
        self.assertEqual("NO_ACTION", result.ruling["ruling"]["ruling"])

    def test_a_version_six_case_above_fifty_reaches_the_judge(self):
        """No version-6 clause makes a value above 50.00 a person's."""
        transport = GateTransport([ruling_object(confidence="0.90")])
        result = run_case(HUMAN_ONLY_CASE, transport, version=VERSION_SIX)
        self.assertIsNone(result.scope_gate)
        self.assertIn(transcript.ROLE_JUDGE, transport.roles_for(HUMAN_ONLY_CASE))
        self.assertEqual("NO_ACTION", result.ruling["ruling"]["ruling"])

    def test_the_version_six_scope_gate_still_refuses_every_call(self):
        """A flagged case at version 6 makes no call at all, as it always did."""
        case = with_safety_flag(MIDDLE_BAND_CASE)
        transport = GateTransport([ruling_object(confidence="0.99")])
        result = run_case(MIDDLE_BAND_CASE, transport, version=VERSION_SIX, case=case)
        self.assertEqual(0, transport.calls(), "the version-6 gate let a call out")
        self.assertEqual(pipeline.GEN08_SCOPE, result.scope_gate["reason_code"])
        self.assertEqual(0, result.scope_gate["calls"])
        self.assertEqual(0, len(result.transcript.entries))


# --------------------------------------------------------------------------
# 3. The no-valid-drafts escalation
# --------------------------------------------------------------------------
class TheNoValidDraftsEscalationTests(unittest.TestCase):
    """A panel every one of whose drafts is below the bar."""

    def test_every_draft_below_the_bar_escalates_citing_pol_gen_26(self):
        transport = GateTransport([ruling_object(confidence="0.50")])
        result = run_case(MIDDLE_BAND_CASE, transport, version=VERSION_SEVEN)
        inner = result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertEqual([], inner["referrals"])
        self.assertIn(pipeline.V7_NO_VALID_DRAFTS_CLAUSE, inner["explanation"])
        self.assertIn(pipeline.VOTE_NO_VALID_DRAFTS, inner["explanation"])
        self.assertEqual(
            pipeline.VOTE_NO_VALID_DRAFTS, result.judge_vote["outcome"]
        )

    def test_a_version_six_panel_below_its_floor_cites_no_version_seven_clause(self):
        transport = GateTransport([ruling_object(confidence="0.50")])
        result = run_case(MIDDLE_BAND_CASE, transport, version=VERSION_SIX)
        inner = result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertNotIn(
            pipeline.V7_NO_VALID_DRAFTS_CLAUSE, inner["explanation"]
        )
        self.assertEqual(
            pipeline.VOTE_NO_VALID_DRAFTS, result.judge_vote["outcome"]
        )

    def test_a_panel_at_the_bar_carries_its_ruling(self):
        transport = GateTransport([ruling_object(confidence="0.90")])
        result = run_case(MIDDLE_BAND_CASE, transport, version=VERSION_SEVEN)
        self.assertEqual("NO_ACTION", result.ruling["ruling"]["ruling"])
        self.assertEqual(pipeline.VOTE_CARRIED, result.judge_vote["outcome"])

    def test_a_carried_ruling_below_the_bar_is_escalated_after_the_vote(self):
        """The post-vote guard, at the version-7 bar.

        The panel's drafts are held to the bar individually, so this guard is
        unreachable through the checks in front of it. It is asked directly, as
        the version-6 one is, because what it protects is the thing published.
        """
        middle = version_seven_brief(MIDDLE_BAND_CASE)
        carried = {
            "ruling": ruling_object(confidence="0.50"),
            "discarded_claims": [],
        }
        escalated = pipeline._below_floor_escalation(carried, middle, VERSION_SEVEN)
        self.assertIsNotNone(escalated)
        self.assertEqual(pipeline.ESCALATE, escalated["ruling"]["ruling"])
        self.assertIn("POL-RD-25", escalated["ruling"]["explanation"])

    def test_the_same_guard_at_version_six_uses_the_version_six_floor(self):
        middle = version_six_brief(MIDDLE_BAND_CASE)
        carried = {
            "ruling": ruling_object(confidence="0.50"),
            "discarded_claims": [],
        }
        escalated = pipeline._below_floor_escalation(carried, middle, VERSION_SIX)
        self.assertIsNotNone(escalated)
        self.assertIn("POL-RD-10(1)", escalated["ruling"]["explanation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
