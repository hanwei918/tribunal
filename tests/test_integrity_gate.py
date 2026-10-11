"""The record-integrity gate: ``POL-RD-10(2)`` and ``(4)``, off by default.

``POL-RD-10`` says the judge must not issue a final ruling, and must escalate,
whenever "(2) the trip identifiers on trip_record, gps_trace and fare_breakdown
do not all match, or the trip_record is absent from the pool", or "(4) pickup or
dropoff timestamps on two admitted artifacts disagree by more than 10 minutes,
or any artifact's timestamps run backwards". Both are conditions code can test
with no model, and the judge read past both at version 6 -- case 2858's fare
ledger is filed under ``TRP-02758`` while the trip record and the trace are
``TRP-02858``, and case 112's trace begins 13 minutes 30 seconds before the trip
record says the trip started.

``--integrity-gate`` makes the pipeline obey them literally: the record is
assembled, the limbs are tested, and a record that trips either is escalated
with the reason code ``RD10_RECORD_INTEGRITY`` and **no** advocate, judge or
verifier call. The switch is off by default, so every run before it is the run
it was, and it is refused for every sealed set, whose single run is one
measurement.

Every test here drives the real :func:`tribunal.pipeline.run_loaded_case` over
the rig's scripted transport: a corpus route-deviation case whose three
artifacts carry the same identifier and whose trace begins and ends at the trip
record's own timestamps, mutated one way at a time.

No network, no credential, no model call, no browser. Run from the project root
with::

    python -m unittest tests.test_integrity_gate -v
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, integrity_gate, run_benchmark as runner  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import brief, loader, money, pipeline  # noqa: E402

VERSION_SIX = 6
VERSION_ONE = 1

# The corpus case every fixture is built from. Its three artifacts carry the
# same trip identifier and its trace begins and ends at the trip record's own
# timestamps, so unaltered it trips neither limb and reaches the model.
CASE = 101
NO_SHOW_CASE = 201

TRIP = "TRIP_RECORD"
TRACE = "GPS_TRACE"
FARE = "FARE_BREAKDOWN"

PINNED_NOW = "2026-10-10T00:00:00+00:00"


class _Writer:
    """A file-like sink for ``redirect_stdout``/``redirect_stderr``."""

    def __init__(self) -> None:
        self.text = []

    def write(self, text: str) -> int:
        self.text.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    def __str__(self) -> str:
        return "".join(self.text)


# --------------------------------------------------------------------------
# The fixtures
# --------------------------------------------------------------------------
def _case(case_no: int = CASE) -> Dict[str, Any]:
    """A real corpus case, deep-copied so a fixture can be mutated safely."""
    return copy.deepcopy(loader.load_case(case_no))


def _payload(case: Dict[str, Any], evidence_type: str) -> Dict[str, Any]:
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == evidence_type:
            return artifact["payload"]
    raise AssertionError("no {0} artifact in case {1}".format(evidence_type, case["case_no"]))


def different_fare_identifier(case_no: int = CASE) -> Dict[str, Any]:
    """The case with a fare ledger filed under another trip's identifier."""
    case = _case(case_no)
    _payload(case, FARE)["trip_id"] = "TRP-00999"
    return case


def disagreement(minutes: int, case_no: int = CASE) -> Dict[str, Any]:
    """The case with the trace's first fix ``minutes`` before the trip's start."""
    case = _case(case_no)
    trip = _payload(case, TRIP)
    trace = _payload(case, TRACE)
    started = datetime.datetime.fromisoformat(trip["started_at"])
    trace["first_fix_at"] = (started - datetime.timedelta(minutes=minutes)).isoformat()
    return case


def _recorded_answers() -> Dict[int, Any]:
    """The rig's stand-in for the recorded answers: the key's own ruling."""
    return rig.produced_from_key(rig.answer_key())


def run_the_case(
    case: Dict[str, Any], *, integrity_gate: bool, transport=None
) -> Tuple[pipeline.PipelineResult, Any]:
    """Drive one case through the real pipeline over a scripted transport."""
    if transport is None:
        transport = rig.ScriptedTransport(_recorded_answers())
    client = rig.client_factory(rig.MODEL, transport)(None)
    result = pipeline.run_loaded_case(
        case,
        client,
        prompts_dir=rig.PROMPTS_DIR,
        now=lambda: PINNED_NOW,
        judge_votes=4,
        policy_version=VERSION_SIX,
        integrity_gate=integrity_gate,
    )
    return result, transport


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------
class TheGateFiresTests(unittest.TestCase):
    """A record that does not hang together is escalated; one that does is not."""

    def test_matching_identifiers_and_close_timestamps_reach_the_model(self):
        result, transport = run_the_case(_case(), integrity_gate=True)

        self.assertGreater(transport.calls(), 0, "the gate fired on a sound record")
        self.assertIsNone(result.record_integrity)
        self.assertEqual(
            _recorded_answers()[CASE]["ruling"]["ruling"],
            result.ruling["ruling"]["ruling"],
        )

    def test_a_fare_identifier_that_differs_escalates_with_no_request(self):
        result, transport = run_the_case(
            different_fare_identifier(), integrity_gate=True
        )

        self.assertEqual(0, transport.calls(), "a request was sent")
        self.assertEqual(["POL-RD-10(2)"], result.record_integrity["limbs"])
        inner = result.ruling["ruling"]
        self.assertEqual(pipeline.ESCALATE, inner["ruling"])
        self.assertEqual(0.0, inner["confidence"])
        self.assertIsNone(inner["amount_sgd"])
        self.assertIsNone(inner["driver_compensation_sgd"])
        self.assertEqual([], inner["referrals"])
        self.assertEqual([], list(result.ruling_findings))

    def test_an_eleven_minute_disagreement_escalates_with_no_request(self):
        result, transport = run_the_case(disagreement(11), integrity_gate=True)

        self.assertEqual(0, transport.calls(), "a request was sent")
        self.assertEqual(["POL-RD-10(4)"], result.record_integrity["limbs"])
        self.assertEqual(pipeline.ESCALATE, result.ruling["ruling"]["ruling"])

    def test_a_nine_minute_disagreement_reaches_the_model(self):
        result, transport = run_the_case(disagreement(9), integrity_gate=True)

        self.assertGreater(transport.calls(), 0, "the gate fired under its own limb")
        self.assertIsNone(result.record_integrity)

    def test_a_no_show_case_is_not_held_to_these_limbs(self):
        """``POL-NS-09`` carries no limb of the same kind, so the gate is RD only."""
        case = _case(NO_SHOW_CASE)
        _payload(case, FARE)["trip_id"] = "TRP-00999"
        result, transport = run_the_case(case, integrity_gate=True)

        self.assertGreater(transport.calls(), 0, "the gate fired on a no-show dispute")
        self.assertIsNone(result.record_integrity)

    def test_the_reason_code_the_clause_and_the_limb_are_recorded(self):
        result, _transport = run_the_case(
            different_fare_identifier(), integrity_gate=True
        )

        block = result.record_integrity
        self.assertEqual(pipeline.RD10_RECORD_INTEGRITY, block["reason_code"])
        self.assertEqual(pipeline.INTEGRITY_GATE_CLAUSE, block["clause"])
        self.assertEqual(0, block["calls"])
        explanation = result.ruling["ruling"]["explanation"]
        self.assertIn("POL-RD-10(2)", explanation)
        self.assertIn("POL-RD-10", explanation)
        self.assertIn(pipeline.RD10_RECORD_INTEGRITY, explanation)

    def test_a_gated_case_holds_no_call_in_its_transcript(self):
        result, _transport = run_the_case(
            different_fare_identifier(), integrity_gate=True
        )

        self.assertEqual(0, len(result.transcript.entries))


# --------------------------------------------------------------------------
# The clause's own sentence
# --------------------------------------------------------------------------
# Captured before the patch below replaces it, so the replacement can still load
# the real policy it is a variation of.
_LOAD_POLICIES = loader.load_policies


def moved_policy(category: str, policy_version: int = VERSION_ONE) -> Dict[str, Any]:
    """The loaded policy with limb (4)'s sentence moved, for the refusal test."""
    policies = _LOAD_POLICIES(category, policy_version)
    for clause in policies["category"]["clauses"]:
        if clause.get("id") == pipeline.INTEGRITY_GATE_CLAUSE:
            clause["rule"] = clause["rule"].replace(
                "more than 10 minutes", "more than ten minutes"
            )
    return policies


class TheClauseSentenceTests(unittest.TestCase):
    """Limb (4)'s minutes come from the clause, and a moved sentence is refused."""

    def test_the_minutes_are_read_from_the_loaded_clause(self):
        for version in (VERSION_ONE, VERSION_SIX):
            with self.subTest(version=version):
                self.assertEqual(
                    datetime.timedelta(minutes=10),
                    pipeline.record_integrity_minutes(version),
                )

    def test_a_moved_sentence_is_refused(self):
        with mock.patch.object(loader, "load_policies", moved_policy):
            with self.assertRaises(pipeline.PipelineError) as caught:
                pipeline.record_integrity_minutes(VERSION_SIX)

        self.assertIn("POL-RD-10's limb (4) sentence", str(caught.exception))

    def test_the_gate_refuses_rather_than_ruling_on_a_moved_sentence(self):
        with mock.patch.object(loader, "load_policies", moved_policy):
            with self.assertRaises(pipeline.PipelineError):
                run_the_case(_case(), integrity_gate=True)


# --------------------------------------------------------------------------
# Off by default
# --------------------------------------------------------------------------
class TheSwitchOffTests(unittest.TestCase):
    """With the switch off, nothing changes and the record replays as it did."""

    def test_the_switch_off_asks_the_model_and_records_no_block(self):
        result, transport = run_the_case(_case(), integrity_gate=False)

        self.assertGreater(transport.calls(), 0)
        self.assertIsNone(result.record_integrity)
        self.assertEqual(
            _recorded_answers()[CASE]["ruling"]["ruling"],
            result.ruling["ruling"]["ruling"],
        )

    def test_the_switch_off_sends_the_same_requests_as_an_unfired_gate(self):
        """The offline replay's claim, for one case: the bodies are unchanged."""
        off_result, off_transport = run_the_case(_case(), integrity_gate=False)
        on_result, on_transport = run_the_case(_case(), integrity_gate=True)

        self.assertEqual(off_transport.requests, on_transport.requests)
        self.assertEqual(off_result.ruling, on_result.ruling)

    def test_the_runner_writes_no_block_with_the_switch_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _transport = rig.bench(tmp)

            document = runner.load_cached(summary.run_dir, CASE)
            self.assertNotIn("record_integrity", document)

    def test_the_runner_records_the_switch_where_the_parallel_one_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain, _transport = rig.bench(tmp)
            gated, _transport = rig.bench(
                tmp, runs_dir=Path(tmp) / "gated", integrity_gate=True
            )

            off = runner.read_json(plain.run_dir / runner.METADATA_FILE)
            on = runner.read_json(gated.run_dir / runner.METADATA_FILE)
            self.assertNotIn("integrity_gate", off)
            self.assertIs(True, on["integrity_gate"])

            self.assertNotIn(
                "integrity_gate", rig.invocation_start(plain.run_dir)
            )
            self.assertIs(
                True, rig.invocation_start(gated.run_dir)["integrity_gate"]
            )

            # It changes no request body, so it is not part of a case's
            # configuration and it is not a key a case file is read against.
            document = runner.load_cached(gated.run_dir, CASE)
            self.assertNotIn("integrity_gate", document["configuration"])

    def test_a_recorded_run_still_replays_as_it_did(self):
        """The gate changes no brief, so the committed run's digest still builds."""
        model = runner.resolve_model(None)
        run_dir = runner.RUNS_DIR / "policy-v6" / runner.model_slug(model)
        document = runner.read_json(run_dir / "case-{0:05d}.json".format(CASE))

        case_brief = brief.build_brief_for_case(_case(), policy_version=VERSION_SIX)
        rebuilt = hashlib.sha256(
            money.dumps_canonical(case_brief).encode("utf-8")
        ).hexdigest()

        self.assertEqual(document["brief_sha256"], rebuilt)


# --------------------------------------------------------------------------
# Refused for a sealed set
# --------------------------------------------------------------------------
class TheSealedSetTests(unittest.TestCase):
    """A sealed set's single run is one measurement and is not re-taken."""

    def test_the_set_refuses_it_by_its_own_name(self):
        for name in ("wild", "wild-v2", "sealed-v1"):
            with self.subTest(set=name):
                development_set = development_sets.named(name)
                with self.assertRaises(runner.BenchmarkError) as caught:
                    development_sets.run_set(
                        development_set, "some-model", integrity_gate=True
                    )

                self.assertIn(name, str(caught.exception))
                self.assertIn("--integrity-gate", str(caught.exception))

    def test_the_command_line_refuses_it_for_a_sealed_set(self):
        for name in ("wild-v2", "sealed-v1"):
            with self.subTest(set=name):
                out, err = _Writer(), _Writer()
                with redirect_stdout(out), redirect_stderr(err):
                    status = development_sets.main(
                        ["--set", name, "--integrity-gate", "--check"]
                    )

                self.assertEqual(1, status)
                self.assertIn("--integrity-gate", str(err))
                self.assertIn(name, str(err))
                self.assertEqual("", str(out))

    def test_the_sealed_set_still_runs_its_read_only_plan_without_the_switch(self):
        """The control: the same invocation without the switch is not refused."""
        out, err = _Writer(), _Writer()
        with redirect_stdout(out), redirect_stderr(err):
            status = development_sets.main(["--set", "wild-v2", "--check"])

        self.assertEqual(1, status)
        self.assertNotIn("--integrity-gate", str(err))


# --------------------------------------------------------------------------
# The report's totals
# --------------------------------------------------------------------------
class TheMeasuredRunsTests(unittest.TestCase):
    """Every count is over the non-sealed cases, and the sealed run is not read.

    The third sealed set's single run is read once, by its own report, and the
    README promises that nothing after that run re-reads it. A module that
    measured it would break that promise, and one that pooled it into a total
    would print a figure no single run supports.
    """

    def test_the_sealed_run_is_not_measured(self):
        names = [run.name for run in integrity_gate.measured_runs()]
        self.assertNotIn("sealed-v1", names)

    def test_the_non_sealed_runs_are_measured(self):
        """The control: the list is not empty, so the check above proves something."""
        names = [run.name for run in integrity_gate.measured_runs()]
        self.assertEqual(
            [
                "corpus",
                "dev-v2-ext",
                "dev-v2",
                "ryde-v3",
                "inject-v1",
                "pii-v1",
                "collusion-v1",
            ],
            names,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
