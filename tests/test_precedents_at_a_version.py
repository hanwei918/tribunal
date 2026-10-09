"""Precedents at a policy version: the one pairing that is allowed.

The precedent library was a stretch goal that could be measured only at version
1, because ``eval.run_benchmark`` allowed at most one of ``--ablate``,
``--precedents``, ``--policy-version N>=2`` and ``--amount-rule``.

The rule relaxes for exactly one pairing: the precedents block is the same
whatever the policy version, so ``--precedents`` may be given **together with**
``--policy-version``. Their run writes to ``runs/precedents/policy-vN/<model>/``,
a root of its own that collides with neither the plain precedents root nor the
plain version-N root. Every other pairing keeps its refusal, and
``eval.sealed_roots`` still refuses a sealed destination.

No model call: every answer comes from a scripted transport.

Run from the project root with::

    python -m unittest tests.test_precedents_at_a_version -v
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import run_benchmark as runner  # noqa: E402
from eval import sealed_roots  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import brief, loader  # noqa: E402

MODEL = rig.MODEL
CASE = 101
VERSION_THREE = 3


def scripted():
    return rig.ScriptedTransport(rig.produced_from_key(rig.answer_key()))


class TheCombinedRunTests(unittest.TestCase):
    """``--precedents`` with ``--policy-version`` is accepted, and files itself apart."""

    def test_the_combination_is_accepted_and_goes_to_its_own_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = scripted()
            summary = runner.run_benchmark(
                MODEL,
                [CASE],
                runs_dir=runs,
                prompts_dir=rig.PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, transport),
                key=rig.answer_key(),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
                precedents=runner.PRECEDENTS_STORE,
                policy_version=VERSION_THREE,
            )
            self.assertEqual([CASE], list(summary.completed_cases))
            expected = runner.precedents_policy_v_run_directory(
                runs, VERSION_THREE, MODEL
            )
            self.assertEqual(expected, Path(summary.run_dir))
            self.assertTrue((expected / "case-00101.json").is_file())

    def test_the_run_records_the_version_it_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            runner.run_benchmark(
                MODEL,
                [CASE],
                runs_dir=runs,
                prompts_dir=rig.PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, scripted()),
                key=rig.answer_key(),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
                precedents=runner.PRECEDENTS_STORE,
                policy_version=VERSION_THREE,
            )
            run_dir = runner.precedents_policy_v_run_directory(
                runs, VERSION_THREE, MODEL
            )
            document = json.loads(
                (run_dir / "case-00101.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                VERSION_THREE, document["configuration"]["policy_version"]
            )
            # The precedents switch was on, so the case file carries the ids the
            # judge was shown -- an empty list is a finding, not an absence.
            self.assertIn("precedents_shown", document)

    def test_the_brief_is_the_version_n_brief(self):
        """The brief the agents were given is the version-3 brief, not version 1's."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            runner.run_benchmark(
                MODEL,
                [CASE],
                runs_dir=runs,
                prompts_dir=rig.PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, scripted()),
                key=rig.answer_key(),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
                precedents=runner.PRECEDENTS_STORE,
                policy_version=VERSION_THREE,
            )
            run_dir = runner.precedents_policy_v_run_directory(
                runs, VERSION_THREE, MODEL
            )
            document = json.loads(
                (run_dir / "case-00101.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                runner.current_brief_sha256(CASE, policy_version=VERSION_THREE),
                document["brief_sha256"],
            )
            self.assertNotEqual(
                runner.current_brief_sha256(CASE, policy_version=1),
                document["brief_sha256"],
            )


class TheRootsDoNotCollideTests(unittest.TestCase):
    """The combined root is its own, and the guards say so."""

    def setUp(self):
        self.runs = Path("/tmp/part7-roots/runs")

    def test_the_three_roots_are_three_different_directories(self):
        combined = runner.precedents_policy_v_run_directory(
            self.runs, VERSION_THREE, MODEL
        )
        self.assertNotEqual(
            runner.precedents_run_directory(self.runs, MODEL), combined
        )
        self.assertNotEqual(
            runner.policy_v_run_directory(self.runs, VERSION_THREE, MODEL), combined
        )
        self.assertEqual(
            self.runs
            / "precedents"
            / "policy-v3"
            / runner.model_slug(MODEL),
            combined,
        )

    def test_the_guard_accepts_only_the_combined_root(self):
        combined = runner.precedents_policy_v_run_directory(
            self.runs, VERSION_THREE, MODEL
        )
        self.assertEqual(
            combined,
            runner.assert_precedents_policy_v_destination(
                combined, self.runs, VERSION_THREE, MODEL
            ),
        )
        for dirty in (
            runner.precedents_run_directory(self.runs, MODEL),
            runner.policy_v_run_directory(self.runs, VERSION_THREE, MODEL),
            runner.run_directory(self.runs, MODEL),
        ):
            with self.subTest(path=dirty):
                with self.assertRaises(runner.BenchmarkError):
                    runner.assert_precedents_policy_v_destination(
                        dirty, self.runs, VERSION_THREE, MODEL
                    )

    def test_a_sealed_destination_is_still_refused(self):
        for sealed in (
            self.runs / "wild" / runner.model_slug(MODEL),
            self.runs / "wild-v2" / runner.model_slug(MODEL),
        ):
            with self.subTest(path=sealed):
                with self.assertRaises(sealed_roots.SealedDestinationError):
                    sealed_roots.refuse_a_sealed_destination(sealed, self.runs)


class WhatStaysExclusiveTests(unittest.TestCase):
    """Every other pairing keeps its refusal, and the plain runs are untouched."""

    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    runner.main(arguments)
        return errors.getvalue()

    def test_ablate_with_a_policy_version_is_still_refused(self):
        message = self.refuse(
            ["--ablate", brief.ABLATION_CLAUSE_NOTES, "--policy-version", "3"]
        )
        self.assertIn("ablate", message)
        self.assertIn("policy-version", message)

    def test_precedents_with_an_ablation_is_still_refused(self):
        message = self.refuse(
            ["--precedents", "--ablate", brief.ABLATION_CLAUSE_NOTES]
        )
        self.assertIn("precedents", message)

    def test_amount_rule_with_a_policy_version_is_still_refused(self):
        message = self.refuse(
            ["--amount-rule", "signed", "--policy-version", "3"]
        )
        self.assertIn("amount-rule", message)

    def test_versions_one_and_two_without_precedents_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            for version, expected in (
                (1, runner.run_directory(runs, MODEL)),
                (2, runner.policy_v_run_directory(runs, 2, MODEL)),
            ):
                with self.subTest(version=version):
                    summary = runner.run_benchmark(
                        MODEL,
                        [CASE],
                        runs_dir=runs,
                        prompts_dir=rig.PROMPTS_DIR,
                        client_factory=rig.client_factory(MODEL, scripted()),
                        key=rig.answer_key(),
                        git_runner=rig.git_runner(),
                        progress=lambda text: None,
                        judge_votes=1,
                        policy_version=version,
                    )
                    self.assertEqual(expected, Path(summary.run_dir))
                    document = json.loads(
                        (Path(summary.run_dir) / "case-00101.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertNotIn("precedents_shown", document)


if __name__ == "__main__":
    unittest.main(verbosity=2)
