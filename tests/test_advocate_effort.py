"""The advocate-effort switch: ``--advocate-effort {default,none}``.

The two advocates are the slowest part of a case: over the 171 version-6 cases
with four drafts, the slower advocate call has median 91 s and 90th percentile
140 s, against the whole case's 160 s and 290 s. ``tribunal.llm`` already
supports ``reasoning_effort`` -- omitted leaves reasoning on, and the explicit
string ``"none"`` suppresses it -- so ``--advocate-effort none`` makes the **two
advocate requests** carry ``"reasoning_effort": "none"`` and leaves the judge's
drafts and the verifier untouched.

Two properties carry the whole switch and both are asserted here:

* with the switch at ``default`` every request body is byte-identical to the
  body it was before the switch existed -- the offline replay's claim, checked
  here for one case; and
* with the switch at ``none`` the two advocate bodies gain that one key and no
  other body changes at all.

The switch changes what a run measures, so a run under it goes to a root of its
own, ``runs/advocate-effort-<effort>/<set>/[policy-v<N>/]<model>/``; it is
refused for every sealed set, whose single run is one measurement; and
:mod:`eval.advocate_effort` compares a switched run against the baseline it is
measured against.

Every test drives the real :func:`tribunal.pipeline.run_loaded_case` and the
real runner over the rig's scripted transport. **No test reads anything under
``runs/``**: the two run directories the report is measured over are built in a
temporary directory, and the repository's ``runs/`` is neither read nor written.

No network, no credential, no model call, no browser. Run from the project root
with::

    python -m unittest tests.test_advocate_effort -v
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    advocate_effort,
    development_sets,
    run_benchmark as runner,
    sealed_roots,
)
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import llm, loader, money, pipeline, transcript  # noqa: E402

CASE = 101
VERSION_SIX = 6
PINNED_NOW = "2026-10-10T00:00:00+00:00"

ADVOCATE_ROLES = (transcript.ROLE_RIDER_ADVOCATE, transcript.ROLE_DRIVER_ADVOCATE)

# Every key a request body carried before the switch existed. The client omits
# each optional key it was not given, so this is the whole of the body.
BODY_KEYS = frozenset({"model", "messages", "temperature", "seed", "response_format"})


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
# The pipeline, over the rig's scripted transport
# --------------------------------------------------------------------------
def run_the_case(*, advocate_effort, judge_votes=4):
    """Drive one real case through the real pipeline, over the rig's transport."""
    transport = rig.ScriptedTransport(rig.produced_from_key(rig.answer_key()))
    client = rig.client_factory(rig.MODEL, transport)(None)
    result = pipeline.run_loaded_case(
        loader.load_case(CASE),
        client,
        prompts_dir=rig.PROMPTS_DIR,
        now=lambda: PINNED_NOW,
        judge_votes=judge_votes,
        policy_version=VERSION_SIX,
        advocate_effort=advocate_effort,
    )
    return result, transport


def advocate_requests(transport):
    """The bodies the two advocate calls were handed, and nothing else."""
    return [
        request
        for request, (_case_no, role) in zip(transport.requests, transport.roles)
        if role in ADVOCATE_ROLES
    ]


def other_requests(transport):
    """The bodies every other call was handed -- the judge's drafts, the verifier."""
    return [
        request
        for request, (_case_no, role) in zip(transport.requests, transport.roles)
        if role not in ADVOCATE_ROLES
    ]


# --------------------------------------------------------------------------
# With the switch at default, nothing moves
# --------------------------------------------------------------------------
class TheSwitchOffTests(unittest.TestCase):
    """``default`` is the state every run before the switch was made in."""

    def test_the_switch_off_sends_no_reasoning_effort_key_at_all(self):
        _result, transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_DEFAULT
        )

        self.assertGreater(transport.calls(), 0)
        for request in transport.requests:
            self.assertNotIn("reasoning_effort", request)

    def test_the_switch_off_sends_the_body_it_always_sent(self):
        """The keys are the keys a request had before the switch existed.

        The offline replay's claim, stated for one case: a body that had gained
        or lost a key would be a different body, and the committed runs'
        ``calls.json`` digests pin the bodies this run sends.
        """
        _result, transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_DEFAULT
        )

        self.assertGreater(transport.calls(), 0)
        for request in transport.requests:
            self.assertEqual(BODY_KEYS, frozenset(request))

    def test_the_default_effort_is_the_effort_not_named(self):
        """The keyword's default is the behaviour, so naming it changes no byte."""
        named_result, named_transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_DEFAULT
        )
        _plain_result, plain_transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_DEFAULT
        )

        self.assertEqual(plain_transport.requests, named_transport.requests)
        self.assertEqual(
            rig.answer_key()[CASE].ruling, named_result.ruling["ruling"]["ruling"]
        )

    def test_the_runner_writes_no_advocate_effort_with_the_switch_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _transport = rig.bench(tmp)

            document = runner.load_cached(summary.run_dir, CASE)
            self.assertNotIn("advocate_effort", document["configuration"])
            metadata = runner.read_json(Path(summary.run_dir) / runner.METADATA_FILE)
            self.assertNotIn("advocate_effort", metadata)
            self.assertNotIn("advocate_effort", rig.invocation_start(summary.run_dir))

    def test_a_switched_run_is_not_the_plain_one(self):
        """The control: the same run with the switch on does write the key."""
        with tempfile.TemporaryDirectory() as tmp:
            plain, _transport = rig.bench(tmp)
            switched, _transport = rig.bench(
                tmp,
                runs_dir=Path(tmp) / "switched",
                advocate_effort=pipeline.ADVOCATE_EFFORT_NONE,
            )

            self.assertNotEqual(
                Path(plain.run_dir).resolve(), Path(switched.run_dir).resolve()
            )


# --------------------------------------------------------------------------
# With the switch at none, exactly two bodies move
# --------------------------------------------------------------------------
class TheSwitchOnTests(unittest.TestCase):
    """``none`` turns reasoning off for the advocates and for nothing else."""

    def test_only_the_two_advocate_bodies_gain_the_key(self):
        _result, transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_NONE
        )

        advocates = advocate_requests(transport)
        self.assertEqual(2, len(advocates))
        for request in advocates:
            self.assertEqual("none", request.get("reasoning_effort"))
            self.assertEqual(BODY_KEYS | {"reasoning_effort"}, frozenset(request))

        others = other_requests(transport)
        self.assertEqual(4, len(others), "the panel is four drafts")
        for request in others:
            self.assertNotIn("reasoning_effort", request)
            self.assertEqual(BODY_KEYS, frozenset(request))

    def test_the_switched_bodies_are_the_default_bodies_plus_one_key(self):
        _off_result, off_transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_DEFAULT
        )
        _on_result, on_transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_NONE
        )

        self.assertEqual(len(off_transport.requests), len(on_transport.requests))
        for before, after in zip(off_transport.requests, on_transport.requests):
            stripped = dict(after)
            stripped.pop("reasoning_effort", None)
            self.assertEqual(before, stripped)

    def test_the_switch_changes_no_answer_of_this_case(self):
        """The switch moves the advocates' reasoning; here it moves no ruling."""
        off_result, _off_transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_DEFAULT
        )
        on_result, _on_transport = run_the_case(
            advocate_effort=pipeline.ADVOCATE_EFFORT_NONE
        )

        self.assertEqual(off_result.ruling, on_result.ruling)

    def test_an_unknown_effort_is_refused(self):
        with self.assertRaises(pipeline.PipelineError) as caught:
            run_the_case(advocate_effort="reasoning")

        self.assertIn("advocate effort", str(caught.exception))


# --------------------------------------------------------------------------
# The run root the switch moves the run to
# --------------------------------------------------------------------------
class TheRunRootTests(unittest.TestCase):
    """A switched run goes to a root of its own and can never be a default one."""

    def _run(self, runs, argv):
        transport = rig.ScriptedTransport(rig.produced_from_key(rig.answer_key()))
        with mock.patch.object(
            runner,
            "_default_client_factory",
            return_value=rig.client_factory(rig.MODEL, transport),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                code = runner.main(
                    [
                        "--model", rig.MODEL,
                        "--cases", str(CASE),
                        "--judge-votes", "4",
                        "--runs-dir", str(runs),
                    ]
                    + argv
                )
        self.assertEqual(0, code)
        return transport

    def test_the_switched_run_lands_under_its_own_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            self._run(runs, ["--advocate-effort", "none"])

            landed = runs / "advocate-effort-none" / runner.model_slug(rig.MODEL)
            self.assertTrue((landed / "case-00101.json").is_file())
            self.assertTrue((landed / runner.METADATA_FILE).is_file())

            document = runner.read_json(landed / "case-00101.json")
            self.assertEqual("none", document["configuration"]["advocate_effort"])
            metadata = runner.read_json(landed / runner.METADATA_FILE)
            self.assertEqual("none", metadata["advocate_effort"])
            self.assertEqual("none", rig.invocation_start(landed)["advocate_effort"])

    def test_the_default_run_lands_where_it_always_did(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            self._run(runs, [])

            landed = runs / runner.model_slug(rig.MODEL)
            self.assertTrue((landed / "case-00101.json").is_file())
            self.assertFalse((runs / "advocate-effort-none").exists())

    def test_the_switch_combines_with_the_policy_version(self):
        """The version's directory sits under the switch's own root."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            self._run(
                runs,
                ["--policy-version", str(VERSION_SIX), "--advocate-effort", "none"],
            )

            landed = (
                runs
                / "advocate-effort-none"
                / runner.policy_v_directory_name(VERSION_SIX)
                / runner.model_slug(rig.MODEL)
            )
            self.assertTrue((landed / "case-00101.json").is_file())
            document = runner.read_json(landed / "case-00101.json")
            self.assertEqual(VERSION_SIX, document["configuration"]["policy_version"])
            self.assertEqual("none", document["configuration"]["advocate_effort"])

    def test_the_switch_is_refused_beside_the_other_switches_that_change_a_run(self):
        for switch in (
            ["--ablate", "clause-notes"],
            ["--precedents"],
            ["--amount-rule", "signed"],
        ):
            with self.subTest(switch=switch):
                out, err = _Writer(), _Writer()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    with self.assertRaises(SystemExit) as caught:
                        runner.main(
                            ["--model", rig.MODEL, "--advocate-effort", "none"] + switch
                        )

                self.assertEqual(2, caught.exception.code)
                self.assertIn("--advocate-effort", str(err))

    def test_the_runner_refuses_a_switched_replay(self):
        with self.assertRaises(runner.BenchmarkError) as caught:
            runner.run_benchmark(
                rig.MODEL,
                [CASE],
                runs_dir=Path("/nonexistent-tribunal-runs"),
                replay_dir=Path("/nonexistent-source-run"),
                advocate_effort=pipeline.ADVOCATE_EFFORT_NONE,
            )

        self.assertIn("cannot replay", str(caught.exception))

    def test_the_runner_refuses_an_unknown_effort(self):
        with self.assertRaises(runner.BenchmarkError) as caught:
            runner.run_benchmark(
                rig.MODEL,
                [CASE],
                runs_dir=Path("/nonexistent-tribunal-runs"),
                advocate_effort="reasoning",
            )

        self.assertIn("advocate effort", str(caught.exception))

    def test_a_sealed_destination_is_still_refused(self):
        """The new root is not sealed, and the sealed ones are still refused."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            switched = runs / "advocate-effort-none" / runner.model_slug(rig.MODEL)
            self.assertEqual(
                switched, sealed_roots.refuse_a_sealed_destination(switched, runs)
            )
            for sealed in runner.MADE_SEALED_RUNS_SUBDIRS:
                with self.subTest(root=sealed):
                    with self.assertRaises(sealed_roots.SealedDestinationError):
                        sealed_roots.refuse_a_sealed_destination(
                            runs / sealed / runner.model_slug(rig.MODEL), runs
                        )


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
                        development_set,
                        "some-model",
                        advocate_effort=pipeline.ADVOCATE_EFFORT_NONE,
                    )

                self.assertIn(name, str(caught.exception))
                self.assertIn("--advocate-effort", str(caught.exception))

    def test_the_command_line_refuses_it_for_a_sealed_set(self):
        for name in ("wild-v2", "sealed-v1"):
            with self.subTest(set=name):
                out, err = _Writer(), _Writer()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    status = development_sets.main(
                        ["--set", name, "--advocate-effort", "none", "--check"]
                    )

                self.assertEqual(1, status)
                self.assertIn("--advocate-effort", str(err))
                self.assertIn(name, str(err))
                self.assertEqual("", str(out))

    def test_the_sealed_set_still_runs_its_read_only_plan_without_the_switch(self):
        """The control: the same invocation without the switch is not refused."""
        out, err = _Writer(), _Writer()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = development_sets.main(["--set", "wild-v2", "--check"])

        self.assertEqual(1, status)
        self.assertNotIn("--advocate-effort", str(err))

    def test_a_development_set_is_not_refused_and_the_switch_reaches_the_runner(self):
        """The control the other way: the switch is for the development sets."""
        seen = {}

        def stub(model, cases, **kwargs):
            seen.update(kwargs)
            return mock.Mock(ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(runner, "run_benchmark", side_effect=stub):
                development_sets.run_set(
                    development_sets.named("codex"),
                    rig.MODEL,
                    runs_dir=Path(tmp) / "runs",
                    cases=[9111],
                    advocate_effort=pipeline.ADVOCATE_EFFORT_NONE,
                )

        self.assertEqual("none", seen.get("advocate_effort"))


# --------------------------------------------------------------------------
# The comparison report
# --------------------------------------------------------------------------
def two_runs(tmp):
    """A baseline run and a candidate whose case 101 rules differently.

    Built over the rig's transport, in a temporary directory: the candidate is a
    copy of the baseline with one case file's ruling changed, so the two differ
    in exactly one graded field and in nothing else. Nothing under the
    repository's ``runs/`` is read or written.
    """
    root = Path(tmp)
    baseline, _transport = rig.bench(root, runs_dir=root / "baseline", judge_votes=4)
    candidate = root / "candidate"
    shutil.copytree(Path(baseline.run_dir), candidate)

    document = runner.read_json(candidate / "case-00101.json")
    document["ruling"]["ruling"]["ruling"] = "NO_ACTION"
    (candidate / "case-00101.json").write_text(
        money.dumps_canonical(document), encoding="utf-8"
    )
    return Path(baseline.run_dir), candidate


class TheReportTests(unittest.TestCase):
    """The report's figures, over two run directories built for it."""

    def test_the_report_computes_known_figures(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, candidate = two_runs(tmp)
            comparison = advocate_effort.compare(
                baseline, candidate, key=rig.answer_key()
            )

            self.assertEqual(3, len(comparison.cases))
            self.assertEqual(3, comparison.baseline.exact)
            self.assertEqual(3, comparison.baseline.total)
            self.assertEqual(2, comparison.candidate.exact)

            counts = {direction: 0 for direction in advocate_effort.DIRECTIONS}
            for case in comparison.cases:
                counts[case.direction] += 1
            self.assertEqual(1, counts[advocate_effort.REGRESSED])
            self.assertEqual(2, counts[advocate_effort.UNCHANGED])
            self.assertEqual(0, counts[advocate_effort.IMPROVED])
            self.assertEqual(0, counts[advocate_effort.MOVED])

            moved = [
                case
                for case in comparison.cases
                if case.direction == advocate_effort.REGRESSED
            ]
            self.assertEqual([CASE], [case.case_no for case in moved])
            self.assertTrue(moved[0].baseline_exact)
            self.assertFalse(moved[0].candidate_exact)
            self.assertTrue(moved[0].four_fields_changed)

    def test_the_report_reads_the_cost_off_the_case_file_at_the_owner_s_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, candidate = two_runs(tmp)
            comparison = advocate_effort.compare(
                baseline, candidate, key=rig.answer_key()
            )

            tokens = runner.load_cached(baseline, CASE)["tokens"]
            expected = (
                Decimal(tokens["prompt_tokens"] - tokens["cached_tokens"])
                * advocate_effort.PRICE_INPUT
                + Decimal(tokens["cached_tokens"])
                * advocate_effort.PRICE_CACHED_INPUT
                + Decimal(tokens["completion_tokens"]) * advocate_effort.PRICE_OUTPUT
            ) / advocate_effort.MILLION

            case = next(item for item in comparison.cases if item.case_no == CASE)
            self.assertEqual(expected, case.baseline.cost)
            self.assertEqual(
                tokens["prompt_tokens"], case.baseline.tokens["prompt_tokens"]
            )
            self.assertEqual(
                tokens["completion_tokens"], case.baseline.tokens["completion_tokens"]
            )

    def test_the_report_reads_the_claims_off_the_referee_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, candidate = two_runs(tmp)
            comparison = advocate_effort.compare(
                baseline, candidate, key=rig.answer_key()
            )

            case = next(item for item in comparison.cases if item.case_no == CASE)
            # The rig's advocates file one claim each, and case 101's claim
            # resolves against its own evidence and clause, so the referee keeps
            # both.
            self.assertEqual(1, case.baseline.rider_claims)
            self.assertEqual(1, case.baseline.driver_claims)
            self.assertEqual(0, case.baseline.discarded)

    def test_the_report_prints_the_sections_it_promises(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, candidate = two_runs(tmp)
            text = advocate_effort.report(baseline, candidate, key=rig.answer_key())

            for needle in (
                "Four-field exact against the key",
                "Wilson 95%",
                "The cases whose ruling changed",
                advocate_effort.REGRESSED,
                str(CASE),
                "Claims",
                "Time, seconds",
                "Tokens and cost",
            ):
                with self.subTest(needle=needle):
                    self.assertIn(needle, text)

    def test_the_report_prints_the_same_figures_twice(self):
        """A reader can reproduce every figure from the two directories."""
        with tempfile.TemporaryDirectory() as tmp:
            baseline, candidate = two_runs(tmp)
            first = advocate_effort.report(baseline, candidate, key=rig.answer_key())
            second = advocate_effort.report(baseline, candidate, key=rig.answer_key())

            self.assertEqual(first, second)

    def test_a_run_directory_that_is_not_there_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(advocate_effort.AdvocateEffortError):
                advocate_effort.compare(
                    Path(tmp) / "nowhere",
                    Path(tmp) / "nowhere-either",
                    key=rig.answer_key(),
                )

    def test_two_runs_with_no_case_in_common_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            only_101, _transport = rig.bench(
                root, runs_dir=root / "a", cases=(CASE,), judge_votes=1
            )
            other, _transport = rig.bench(
                root, runs_dir=root / "b", cases=(102,), judge_votes=1
            )

            with self.assertRaises(advocate_effort.AdvocateEffortError):
                advocate_effort.compare(
                    Path(only_101.run_dir), Path(other.run_dir), key=rig.answer_key()
                )


# --------------------------------------------------------------------------
# The transport, at the level the switch actually reaches
# --------------------------------------------------------------------------
class TheClientTests(unittest.TestCase):
    """The per-call override the switch is built on, in the client itself."""

    def _client(self):
        return llm.LLMClient(model=rig.MODEL, api_key="not-a-credential")

    def test_an_unset_override_leaves_the_body_alone(self):
        client = self._client()

        self.assertEqual(
            client._request_body("system", "user", pipeline.JSON_OBJECT_FORMAT),
            client._request_body(
                "system",
                "user",
                pipeline.JSON_OBJECT_FORMAT,
                llm._UNSET,
                llm._UNSET,
                llm._UNSET,
            ),
        )

    def test_the_override_adds_the_key_and_the_client_is_not_changed(self):
        client = self._client()

        body = client._request_body(
            "system", "user", pipeline.JSON_OBJECT_FORMAT, llm._UNSET, llm._UNSET, "none"
        )
        self.assertEqual("none", body["reasoning_effort"])

        after = client._request_body("system", "user", pipeline.JSON_OBJECT_FORMAT)
        self.assertNotIn("reasoning_effort", after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
