"""The second sealed set: registering it, and the guards around its single run.

``wild-v2`` is 20 cases under ``data/external/wild-v2/``, keyed by
``eval/answers/wild-v2/ground_truth.json``. Like the held-out set it is **not**
a third development set: it was prepared by OpenAI Codex for the owner, it is
run exactly once from the commit tagged ``freeze-2026-10-03``, and that single
run is the submission's generalisation figure. Its registration fixes policy
version 2 -- ``POL-RD-13`` and the ``POL-RD-11`` upfront remedy are what the
submission now stands behind -- so it is run at version 2 with no flag, and
``--policy-version`` is refused for it.

What is asserted here is the same list of guards the held-out set has, in the
same order:

* **It is registered, and it is apart.** Its own cases, its own key, its own
  loader and its own runs root; it is absent from ``DEVELOPMENT_SETS``, so
  ``--set all`` does not run it and the combined figure does not include it.
* **Its switches are refused.** ``--force``, the three recorded-run switches,
  the three input switches and ``--policy-version`` are all refused for it, each
  shown on a dirty fixture first -- a scratch runs root that already holds its
  result, which is what the switch would replace -- and the fixture is compared
  byte for byte afterwards, so a refusal that quietly wrote something is caught
  rather than assumed away.
* **Its root is closed to everything but its own run.** The component-wise path
  guard refuses every switched destination under ``runs/wild-v2/`` and accepts
  exactly one: the plain sealed run's own directory.
* **Its structure holds.** All 20 cases load through the set's own loader and
  their briefs build at version 2; the key loads through
  ``eval.grade.load_answer_key`` and holds 20 records each carrying all four
  graded fields; and no answer field appears anywhere in a case file. These
  assert on counts and on keys, never on a value.

No model is called anywhere in this module.

Run from the project root with::

    python -m unittest discover -s tests -v
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

from eval import (  # noqa: E402
    baselines,
    development_sets as sets,
    grade,
    policy_gaps,
    run_benchmark,
    verify_drafts,
)
from tribunal import brief, loader  # noqa: E402

MODEL = "deepseek/deepseek-flash"
HELD_OUT = sets.SEALED_SET
WILD_V2 = sets.WILD_V2

# The set's own directories, named here so a test can say which one it means.
WILD_V2_CASES_DIR = PROJECT_ROOT / "data" / "external" / "wild-v2"
WILD_V2_KEY_PATH = PROJECT_ROOT / "eval" / "answers" / "wild-v2" / "ground_truth.json"
WILD_V2_EXTERNAL_DIR = PROJECT_ROOT / "eval" / "external" / "wild-v2"

# 701-720: twenty cases over a twenty-wide range, so the count and the range are
# the same number here and the assertion below says so rather than assuming it.
ALL_WILD_V2_CASES = tuple(range(701, 721))

# The first case of the set, used as the case a scratch fixture "has a result"
# for. It is a number, never a value.
SENTINEL_CASE = 701


def _run_cli(arguments):
    """``sets.main``, with both streams captured. Returns ``(code, out, err)``."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = sets.main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()


def _scratch_runs_with_the_wild_v2_result(tmp):
    """A dirty fixture: a runs root that already holds wild-v2's result.

    This is what ``--force`` would overwrite and what a recorded-run switch
    would re-take, so it is the fixture each refusal is shown on. The file's
    bytes are returned with it so the caller can prove nothing rewrote it.
    """
    runs = Path(tmp) / "runs"
    run_dir = runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR / run_benchmark.model_slug(MODEL)
    run_dir.mkdir(parents=True)
    sentinel = run_dir / "case-{0:05d}.json".format(SENTINEL_CASE)
    sentinel.write_text(
        json.dumps({"case_no": SENTINEL_CASE, "sentinel": "the sealed result"}, indent=2),
        encoding="utf-8",
    )
    return runs, run_dir, sentinel, sentinel.read_bytes()


def _state(directory):
    """Every file under a directory, with its bytes."""
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(Path(directory).rglob("*"))
        if path.is_file()
    }


def _refuse_to_build_a_client():
    """Patch ``LLMClient`` to raise, so a guard that let a run start fails.

    A switch that got past its refusal would build a client and start running
    cases against the real key in the repository's ``.env``. Patching the class
    is what turns that into a test failure instead of a paid call.
    """
    original = run_benchmark.llm.LLMClient

    def refuse(*arguments, **keywords):
        raise AssertionError(
            "a client was built, so a switch was accepted that must have been refused"
        )

    return original, refuse


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------
class WildV2RegistryTests(unittest.TestCase):
    """The second sealed set is registered, and it is not a development set."""

    def test_it_is_registered_by_name_and_marked_sealed(self):
        self.assertIn("wild-v2", sets.BY_NAME)
        self.assertIs(WILD_V2, sets.BY_NAME["wild-v2"])
        self.assertTrue(WILD_V2.sealed, "the second sealed set is not marked sealed")
        self.assertEqual("wild-v2", WILD_V2.runs_subdir)

    def test_it_is_not_one_of_the_development_sets(self):
        """``--set all`` and the combined figure both read ``DEVELOPMENT_SETS``."""
        self.assertEqual(["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn(WILD_V2, sets.DEVELOPMENT_SETS)
        self.assertEqual(("wild", "wild-v2"), tuple(item.name for item in sets.SEALED_SETS))
        self.assertIn(WILD_V2, sets.SEALED_SETS)
        self.assertNotIn("wild-v2", [item.name for item in sets.ALL_SETS])
        self.assertNotIn("wild-v2", [item.name for item in sets.RERUN_SETS])
        self.assertFalse(
            any(item.sealed for item in sets.DEVELOPMENT_SETS),
            "a development set is marked sealed",
        )
        self.assertEqual(
            {item.name for item in sets.DEVELOPMENT_SETS + sets.SEALED_SETS + sets.RERUN_SETS},
            set(sets.BY_NAME),
            "the name table is not exactly the registered sets",
        )

    def test_it_is_excluded_from_the_combined_figure_and_from_set_all(self):
        """Registered and reachable by name, and outside both aggregated readings.

        Two readings aggregate sets: :func:`sets.combined_figures` sums
        ``DEVELOPMENT_SETS``, and ``--set all`` runs them. A sealed set must be
        in neither, so the combined figure is shown not reading a
        ``runs/wild-v2/`` directory that does hold a case, and ``--set all`` is
        shown not running a case only that set holds.

        ``LLMClient`` is patched to raise, so a ``--set all`` that did select the
        set fails here instead of making a paid call.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            set_dir = runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR / run_benchmark.model_slug(MODEL)
            set_dir.mkdir(parents=True)
            (set_dir / "case-{0:05d}.json".format(SENTINEL_CASE)).write_text(
                "{}", encoding="utf-8"
            )

            # The set's own reading sees the case...
            self.assertEqual([SENTINEL_CASE], sets.cached_cases(WILD_V2, MODEL, runs))
            # ...and the combined figure does not, because it reads only the two
            # development sets, neither of which has been run in this root.
            self.assertEqual((0, None), sets.combined_figures(MODEL, runs))

            original, refuse = _refuse_to_build_a_client()
            run_benchmark.llm.LLMClient = refuse
            try:
                code, out, err = _run_cli(
                    ["--set", "all", "--cases", str(SENTINEL_CASE), "--runs-dir", str(runs)]
                )
            finally:
                run_benchmark.llm.LLMClient = original
            self.assertEqual(0, code, err)
            self.assertEqual("", err)
            # Case 701 is a wild-v2 case and nothing else in the selection holds
            # it, so no case ran and the scratch root is as it was.
            self.assertEqual(
                ["case-{0:05d}.json".format(SENTINEL_CASE)],
                sorted(path.name for path in set_dir.iterdir()),
            )

    def test_its_registration_fixes_policy_version_2(self):
        """The version is part of what the set is, not a switch on the run."""
        self.assertEqual(2, WILD_V2.policy_version)
        for other in sets.DEVELOPMENT_SETS + (HELD_OUT,) + sets.RERUN_SETS:
            with self.subTest(other=other.name):
                self.assertEqual(
                    run_benchmark.DEFAULT_POLICY_VERSION,
                    other.policy_version,
                    "a set whose version the command line chooses does not fix one",
                )

    def test_a_run_of_it_briefs_at_version_2_and_keeps_its_own_directory(self):
        """What ``run_set`` hands the runner, without running anything.

        The two facts that keep the sealed run where it belongs: the policy
        version is the registration's and not the command line's, and the version
        does **not** move the run one level down into a ``policy-v2`` directory.
        The runner is replaced by a recorder, so nothing is written and no client
        is built.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            recorded = {}

            def record(*arguments, **keywords):
                recorded["arguments"] = arguments
                recorded["keywords"] = keywords
                raise AssertionError("the recorder was reached")

            with mock.patch.object(run_benchmark, "run_benchmark", record):
                with self.assertRaises(AssertionError):
                    sets.run_set(
                        WILD_V2,
                        MODEL,
                        runs_dir=runs,
                        cases=(SENTINEL_CASE,),
                        policy_version=run_benchmark.DEFAULT_POLICY_VERSION,
                    )

            keywords = recorded["keywords"]
            self.assertEqual(2, keywords["policy_version"])
            self.assertFalse(keywords["policy_version_moves_the_run"])
            self.assertEqual(runs / "wild-v2", keywords["runs_dir"])
            self.assertEqual(runs, keywords["held_out_root"])
            self.assertEqual("wild-v2", keywords["label"])
            self.assertFalse(
                (runs / "wild-v2" / "policy-v2").exists(),
                "the registration moved the run into a policy-v2 directory",
            )

    def test_its_cases_are_the_20_it_was_imported_with(self):
        self.assertEqual(20, len(WILD_V2.cases))
        self.assertEqual(ALL_WILD_V2_CASES, tuple(WILD_V2.cases))
        self.assertEqual(20, len(set(WILD_V2.cases)))

    def test_it_has_its_own_case_root_key_and_loader(self):
        """Its own loader is what loads it, and its own key is what grades it."""
        self.assertEqual(WILD_V2_CASES_DIR, WILD_V2.case_root)
        self.assertEqual(WILD_V2_KEY_PATH, WILD_V2.key_path)
        for other in sets.DEVELOPMENT_SETS + (HELD_OUT,) + sets.RERUN_SETS:
            with self.subTest(other=other.name):
                self.assertNotEqual(other.key_path, WILD_V2.key_path)
                self.assertNotEqual(other.case_root, WILD_V2.case_root)
                self.assertNotEqual(other.runs_subdir, WILD_V2.runs_subdir)
                self.assertEqual(
                    set(),
                    set(other.cases) & set(WILD_V2.cases),
                    "the second sealed set shares a case number with another set",
                )

    def test_its_runs_go_to_its_own_root(self):
        self.assertEqual(
            run_benchmark.RUNS_DIR / "wild-v2" / run_benchmark.model_slug(MODEL),
            WILD_V2.run_dir(MODEL),
        )
        self.assertEqual(run_benchmark.RUNS_DIR / "wild-v2", WILD_V2.runs_dir())
        self.assertNotEqual(HELD_OUT.run_dir(MODEL), WILD_V2.run_dir(MODEL))
        self.assertNotEqual(sets.WILD_DEV.run_dir(MODEL), WILD_V2.run_dir(MODEL))

    def test_its_summary_names_it_the_second_sealed_set_run_once(self):
        summary = WILD_V2.summary
        self.assertIn("second sealed set", summary)
        self.assertIn("wild-v2", summary)
        self.assertIn("run once", summary)
        self.assertIn("generalisation figure", summary)
        self.assertIn("policy version 2", summary)

    def test_its_cases_are_not_in_the_corpus_manifest(self):
        """Adding them to ``data/index.json`` would change the 29-case corpus."""
        manifest = {
            entry["case_no"] for entry in loader._read_json(PROJECT_ROOT / "data" / "index.json")
        }
        self.assertEqual(29, len(manifest))
        self.assertEqual(set(), manifest & set(WILD_V2.cases))


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
class WildV2ReportTests(unittest.TestCase):
    """It is shown on its own, and never inside the combined figure."""

    def test_a_sealed_run_is_never_counted_in_the_combined_figure(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, _ = _scratch_runs_with_the_wild_v2_result(tmp)
            self.assertTrue(sentinel.is_file(), "the fixture was not built")

            produced, combined = sets.combined_figures(MODEL, runs)

            self.assertEqual(0, produced, "the combined figure counted a sealed case")
            self.assertIsNone(combined)
            self.assertEqual([SENTINEL_CASE], sets.cached_cases(WILD_V2, MODEL, runs))

    def test_the_report_prints_it_in_a_section_of_its_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            text = sets.render_development_sets(MODEL, runs)

            self.assertIn(
                "The second sealed set (wild-v2), on its own and never in the "
                "combined figure:",
                text,
            )
            self.assertIn(sets.WILD_V2_CAVEAT, text)
            self.assertIn("0/20", text)

    def test_the_two_sealed_sets_are_two_sections_not_one_table(self):
        """One table under one heading would read as one set measured twice."""
        with tempfile.TemporaryDirectory() as tmp:
            text = sets.render_development_sets(MODEL, Path(tmp) / "runs")

            held_out_at = text.index("The held-out set (wild-v1), on its own")
            second_at = text.index("The second sealed set (wild-v2), on its own")
            self.assertLess(held_out_at, second_at)
            self.assertIn(sets.SEALED_SET_CAVEAT, text)
            self.assertIn(sets.WILD_V2_CAVEAT, text)

    def test_the_combined_line_names_no_sealed_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, _, _, _ = _scratch_runs_with_the_wild_v2_result(tmp)
            text = sets.render_development_sets(MODEL, runs)

            combined = text.split(
                "Combined, every case graded against the key it belongs to:", 1
            )[1]
            combined = combined.split(
                "The held-out set (wild-v1), on its own and never in the combined figure:", 1
            )[0]
            self.assertIn("no case of any development set has been run", combined)
            self.assertNotIn("wild", combined)
            self.assertNotIn("20", combined)


# --------------------------------------------------------------------------
# The switches
# --------------------------------------------------------------------------
class WildV2SwitchGuardTests(unittest.TestCase):
    """Every switch the held-out set refuses, this set refuses too.

    Each refusal is shown on a dirty fixture first: a scratch runs root that
    already holds the sealed set's result, which is exactly what the switch
    would replace or re-take. The fixture is compared byte for byte afterwards.
    """

    def test_force_is_refused_and_leaves_the_result_it_would_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_wild_v2_result(tmp)

            code, _, err = _run_cli(
                ["--set", "wild-v2", "--force", "--runs-dir", str(runs)]
            )

            self.assertEqual(1, code, "a sealed run accepted --force")
            self.assertIn("held-out set", err)
            self.assertIn("--force", err)
            self.assertEqual(before, sentinel.read_bytes(), "the sealed result was rewritten")
            self.assertEqual(
                {sentinel.name: before}, _state(run_dir), "the run directory gained a file"
            )

    def test_the_three_recorded_run_switches_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_wild_v2_result(tmp)

            for flag in ("--replay-advocates", "--replay-check", "--verify-recorded-drafts"):
                with self.subTest(flag=flag):
                    code, _, err = _run_cli(
                        ["--set", "wild-v2", flag, str(run_dir), "--runs-dir", str(runs)]
                    )
                    self.assertEqual(1, code, "{0} was accepted for the sealed set".format(flag))
                    self.assertIn("held-out set", err)
                    self.assertIn(flag, err)
                    self.assertEqual(
                        before, sentinel.read_bytes(), "{0} rewrote the sealed result".format(flag)
                    )
                    self.assertEqual({sentinel.name: before}, _state(run_dir))

    def test_the_three_input_switches_are_refused(self):
        """``--ablate``, ``--precedents`` and ``--amount-rule``, each refused.

        Each of the three moves a set's run one level down under the set's own
        root, so each of them would write under ``runs/wild-v2/``. ``LLMClient``
        is patched to raise, so a switch that got past the refusal fails here
        rather than starting a paid run.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_wild_v2_result(tmp)
            original, refuse = _refuse_to_build_a_client()
            run_benchmark.llm.LLMClient = refuse
            try:
                for arguments in (
                    ["--ablate", "clause-notes"],
                    ["--precedents"],
                    ["--amount-rule", "signed"],
                ):
                    with self.subTest(arguments=arguments):
                        code, _out, err = _run_cli(
                            ["--set", "wild-v2", "--runs-dir", str(runs)] + arguments
                        )
                        self.assertEqual(
                            1, code, "{0} was accepted for --set wild-v2".format(arguments)
                        )
                        self.assertIn("wild-v2", err)
                        self.assertIn("nothing else is created under it", err)
                        self.assertEqual(
                            before,
                            sentinel.read_bytes(),
                            "{0} rewrote the sealed result".format(arguments),
                        )
                        self.assertEqual({sentinel.name: before}, _state(run_dir))
            finally:
                run_benchmark.llm.LLMClient = original

    def test_the_policy_version_flag_is_refused(self):
        """Its version is fixed by registration, so the flag is not its to take."""
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_wild_v2_result(tmp)

            for version in ("2", "3"):
                with self.subTest(version=version):
                    code, _out, err = _run_cli(
                        [
                            "--set",
                            "wild-v2",
                            "--policy-version",
                            version,
                            "--runs-dir",
                            str(runs),
                        ]
                    )
                    self.assertEqual(
                        1, code, "--policy-version {0} was accepted for wild-v2".format(version)
                    )
                    self.assertIn("fixes policy version 2", err)
                    self.assertIn("--policy-version is refused", err)
                    self.assertEqual(before, sentinel.read_bytes())
                    self.assertEqual({sentinel.name: before}, _state(run_dir))

    def test_the_refusal_is_for_this_set_and_not_for_the_others(self):
        """The same guard is silent for every set whose switches are allowed."""
        for development_set in sets.DEVELOPMENT_SETS + sets.RERUN_SETS:
            with self.subTest(development_set=development_set.name):
                self.assertIsNone(sets.assert_not_sealed(development_set, "--force"))

    def test_the_guard_goes_red_on_both_sealed_sets(self):
        for development_set in sets.SEALED_SETS:
            for switch in ("--force", "--replay-advocates", "--replay-check"):
                with self.subTest(development_set=development_set.name, switch=switch):
                    with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                        sets.assert_not_sealed(development_set, switch)
                    self.assertIn("held-out set", str(caught.exception))
                    self.assertIn(switch, str(caught.exception))


# --------------------------------------------------------------------------
# The headline directories
# --------------------------------------------------------------------------
class WildV2RunDirectoryIsHeadlineTests(unittest.TestCase):
    """Every destination that must not write into a reported result refuses it.

    Six of them, the same six the held-out set's directory is refused by: the
    ablation, the precedents block, a later policy version, the baselines, the
    policy-gap report and the recorded-drafts measurement. Each is shown
    refusing ``runs/wild-v2/<model>/`` on a dirty fixture first, and accepting
    the directory of its own after -- so a check that refused everything would
    fail the second half.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.runs = Path(self._tmp.name) / "runs"
        self.sealed_run_dir = (
            self.runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR / run_benchmark.model_slug(MODEL)
        )
        self.sealed_run_dir.mkdir(parents=True)

    def test_it_is_one_of_the_headline_directories(self):
        """The precondition every check below depends on."""
        headline = [
            path.resolve() for path in run_benchmark.headline_run_directories(self.runs, MODEL)
        ]
        self.assertIn(self.sealed_run_dir.resolve(), headline)
        self.assertEqual(4, len(headline), "the headline directories are not four")
        self.assertEqual(
            {
                (self.runs / run_benchmark.model_slug(MODEL)).resolve(),
                (self.runs / "codex" / run_benchmark.model_slug(MODEL)).resolve(),
                (self.runs / "wild" / run_benchmark.model_slug(MODEL)).resolve(),
                self.sealed_run_dir.resolve(),
            },
            set(headline),
        )

    def test_the_ablation_destination_refuses_it_and_takes_its_own(self):
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            run_benchmark.assert_ablation_destination(self.sealed_run_dir, self.runs, MODEL)
        self.assertIn("headline run directory", str(caught.exception))

        accepted = run_benchmark.assert_ablation_destination(
            run_benchmark.ablation_run_directory(self.runs, "clause-notes", MODEL),
            self.runs,
            MODEL,
        )
        self.assertEqual(
            self.runs / "ablation" / "clause-notes" / run_benchmark.model_slug(MODEL), accepted
        )

    def test_the_precedents_destination_refuses_it_and_takes_its_own(self):
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            run_benchmark.assert_precedents_destination(self.sealed_run_dir, self.runs, MODEL)
        self.assertIn("headline run directory", str(caught.exception))

        accepted = run_benchmark.assert_precedents_destination(
            run_benchmark.precedents_run_directory(self.runs, MODEL), self.runs, MODEL
        )
        self.assertEqual(self.runs / "precedents" / run_benchmark.model_slug(MODEL), accepted)

    def test_the_policy_version_destination_refuses_it_and_takes_its_own(self):
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            run_benchmark.assert_policy_v_destination(self.sealed_run_dir, self.runs, 2, MODEL)
        self.assertIn("headline run directory", str(caught.exception))

        accepted = run_benchmark.assert_policy_v_destination(
            run_benchmark.policy_v_run_directory(self.runs, 2, MODEL), self.runs, 2, MODEL
        )
        self.assertEqual(self.runs / "policy-v2" / run_benchmark.model_slug(MODEL), accepted)

    def test_the_baselines_destination_refuses_it_and_takes_its_own(self):
        with self.assertRaises(baselines.BaselineError) as caught:
            baselines.assert_not_a_run_directory(self.sealed_run_dir, self.runs, MODEL)
        self.assertIn("headline run directory", str(caught.exception))

        accepted = baselines.assert_not_a_run_directory(
            baselines.baselines_directory(self.runs), self.runs, MODEL
        )
        self.assertEqual((self.runs / "baselines").resolve(), accepted)

    def test_the_policy_gap_destination_refuses_it_and_takes_its_own(self):
        with self.assertRaises(policy_gaps.PolicyGapError) as caught:
            policy_gaps.assert_not_a_run_directory(self.sealed_run_dir, self.runs, MODEL)
        self.assertIn("headline run directory", str(caught.exception))

        accepted = policy_gaps.assert_not_a_run_directory(
            policy_gaps.policy_gaps_directory(self.runs), self.runs, MODEL
        )
        self.assertEqual((self.runs / "policy-gaps").resolve(), accepted)

    def test_the_recorded_drafts_destination_refuses_it_and_takes_its_own(self):
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            verify_drafts.verify_recorded_run(
                self.sealed_run_dir,
                [SENTINEL_CASE],
                model=MODEL,
                runs_dir=self.sealed_run_dir,
                progress=lambda text: None,
            )
        self.assertIn("headline run directory", str(caught.exception))
        self.assertEqual(
            {},
            _state(self.sealed_run_dir),
            "a refused recorded-drafts run wrote into the sealed run directory",
        )

        accepted = verify_drafts.assert_recorded_drafts_destination(self.runs, MODEL)
        self.assertEqual(
            self.runs / "verify-recorded-drafts" / run_benchmark.model_slug(MODEL), accepted
        )


# --------------------------------------------------------------------------
# Nothing but the plain sealed run writes under runs/wild-v2/
# --------------------------------------------------------------------------
class WildV2RootGuardTests(unittest.TestCase):
    """The component-wise guard closes both sealed roots, and only one is opened.

    ``runs/wild/`` is closed outright: its single run was made once and nothing
    is created under it again. ``runs/wild-v2/`` has not been run, so it accepts
    exactly one destination -- the plain sealed run's own directory, one
    component below the root -- and refuses everything deeper, which is every
    switched destination there is.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.runs = Path(self._tmp.name) / "runs"
        self.slug = run_benchmark.model_slug(MODEL)
        self.wild_v2 = self.runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR
        self.held_out = self.runs / run_benchmark.SEALED_SET_RUNS_SUBDIR

    def test_every_switched_destination_under_the_wild_v2_root_is_refused(self):
        for relative in (
            (),
            (run_benchmark.ABLATION_DIRNAME, "clause-notes", self.slug),
            (run_benchmark.PRECEDENTS_DIRNAME, self.slug),
            (run_benchmark.policy_v_directory_name(2), self.slug),
            (run_benchmark.AMOUNT_RULE_DIRNAME, "signed", self.slug),
            ("verify-recorded-drafts", self.slug),
            ("anything", "at", "all"),
        ):
            destination = self.wild_v2.joinpath(*relative)
            with self.subTest(destination=str(destination)):
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    run_benchmark.assert_not_under_the_held_out_root(destination, self.runs)
                self.assertIn("nothing else is created under it", str(caught.exception))
                self.assertIn(str(self.wild_v2.resolve()), str(caught.exception))

    def test_the_plain_sealed_run_directory_is_the_one_destination_it_takes(self):
        """The half that matters: a guard that refused everything would pass above."""
        destination = self.wild_v2 / self.slug
        self.assertEqual(
            destination,
            run_benchmark.assert_not_under_the_held_out_root(
                destination, self.runs, permit=destination
            ),
        )

    def test_the_permit_does_not_open_the_held_out_root(self):
        """``wild`` has been run; nothing opens it, not even its own directory."""
        destination = self.held_out / self.slug
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            run_benchmark.assert_not_under_the_held_out_root(
                destination, self.runs, permit=destination
            )
        self.assertIn("nothing is created under it again", str(caught.exception))
        self.assertIn("--set wild-dev", str(caught.exception))

    def test_the_re_runnable_sets_root_is_not_caught(self):
        """``runs/wild-dev`` is a different component from ``runs/wild-v2``."""
        for relative in ((), (self.slug,), (run_benchmark.policy_v_directory_name(2), self.slug)):
            destination = (self.runs / run_benchmark.WILD_DEV_RUNS_SUBDIR).joinpath(*relative)
            with self.subTest(destination=str(destination)):
                self.assertEqual(
                    destination,
                    run_benchmark.assert_not_under_the_held_out_root(destination, self.runs),
                )

    def test_every_other_destination_is_not_caught(self):
        for relative in (
            (self.slug,),
            ("codex", self.slug),
            (run_benchmark.ABLATION_DIRNAME, "clause-notes", self.slug),
            (run_benchmark.PRECEDENTS_DIRNAME, self.slug),
            (run_benchmark.policy_v_directory_name(2), self.slug),
            (run_benchmark.AMOUNT_RULE_DIRNAME, "signed", self.slug),
            ("policy-gaps",),
        ):
            destination = self.runs.joinpath(*relative)
            with self.subTest(destination=str(destination)):
                self.assertEqual(
                    destination,
                    run_benchmark.assert_not_under_the_held_out_root(destination, self.runs),
                )

    def test_the_command_line_refuses_set_wild_v2_with_each_switch(self):
        """``--set wild-v2`` plus any of the three input switches, refused."""
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_wild_v2_result(tmp)
            original, refuse = _refuse_to_build_a_client()
            run_benchmark.llm.LLMClient = refuse
            try:
                for arguments in (
                    ["--ablate", "clause-notes"],
                    ["--precedents"],
                    ["--policy-version", "2"],
                    ["--amount-rule", "signed"],
                ):
                    with self.subTest(arguments=arguments):
                        code, _out, err = _run_cli(
                            ["--set", "wild-v2", "--runs-dir", str(runs)] + arguments
                        )
                        self.assertEqual(
                            1, code, "{0} was accepted for --set wild-v2".format(arguments)
                        )
                        self.assertEqual(
                            before,
                            sentinel.read_bytes(),
                            "{0} rewrote the sealed result".format(arguments),
                        )
                        self.assertEqual({sentinel.name: before}, _state(run_dir))
            finally:
                run_benchmark.llm.LLMClient = original


# --------------------------------------------------------------------------
# The structure
# --------------------------------------------------------------------------
class WildV2StructureTests(unittest.TestCase):
    """20 cases load and brief at version 2; the key holds 20 complete records.

    Counts and keys only. No expected ruling, amount, compensation or referral
    is read, compared or printed anywhere in this class -- the key is asserted
    to be *well formed*, not to say anything in particular.
    """

    def test_all_20_cases_load_through_the_sets_own_loader(self):
        self.assertEqual(20, len(WILD_V2.cases))
        for case_no in WILD_V2.cases:
            with self.subTest(case_no=case_no):
                case = WILD_V2.load_case(case_no)
                self.assertEqual(case_no, case["case_no"])
                self.assertEqual(case_no, case["dispute"]["case_no"])
                self.assertEqual(
                    {"case_no", "dispute", "evidence", "schema_version"}, set(case)
                )

    def test_all_20_briefs_build_at_version_2(self):
        for case_no in WILD_V2.cases:
            with self.subTest(case_no=case_no):
                built = brief.build_brief_for_case(
                    WILD_V2.load_case(case_no), policy_version=WILD_V2.policy_version
                )
                self.assertIsInstance(built, dict)
                self.assertTrue(built)

    def test_the_index_names_20_cases_and_the_key_agrees_with_it(self):
        entries = loader.load_external_index(WILD_V2.case_root)
        self.assertEqual(20, len(entries))
        self.assertEqual([case_no for case_no in WILD_V2.cases], [e["case_no"] for e in entries])
        self.assertEqual(set(WILD_V2.cases), set(WILD_V2.key()))

    def test_the_key_loads_and_each_record_carries_all_four_graded_fields(self):
        key = grade.load_answer_key(WILD_V2.key_path)
        self.assertEqual(20, len(key))
        self.assertEqual(set(WILD_V2.cases), set(key))
        self.assertEqual(
            ("ruling", "amount_sgd", "driver_compensation_sgd", "referrals"),
            tuple(grade.GRADED_FIELDS),
        )
        for case_no, expected in sorted(key.items()):
            with self.subTest(case_no=case_no):
                for field in grade.GRADED_FIELDS:
                    # The field exists and can be read; its value is never
                    # compared here, and never printed.
                    expected.field(field)
                self.assertIsNotNone(expected.field("ruling"))

    def test_no_answer_field_appears_in_any_case_file(self):
        """The needles, walked recursively over every case, never a value."""
        needles = set(loader.FORBIDDEN_KEYS)

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIn(key, needles)
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        for case_no in WILD_V2.cases:
            with self.subTest(case_no=case_no):
                walk(WILD_V2.load_case(case_no))

    def test_the_key_file_is_the_only_thing_in_the_sets_answer_directory(self):
        """One key, not a key and a second copy of it that can drift."""
        directory = WILD_V2_KEY_PATH.parent
        self.assertEqual(
            ["ground_truth.json"],
            sorted(path.name for path in directory.iterdir() if path.is_file()),
        )

    def test_the_imported_bundle_is_the_one_the_archive_shipped(self):
        """The authoring bundle's own files are where the import put them."""
        for name in (
            "README.md",
            "MANIFEST.json",
            "seed_map.json",
            "semantic_check.json",
            "validation.txt",
        ):
            with self.subTest(name=name):
                self.assertTrue((WILD_V2_EXTERNAL_DIR / name).is_file())
        for name in ("validate.py", "semcheck.py", "build_v2.py"):
            with self.subTest(name=name):
                self.assertTrue((WILD_V2_EXTERNAL_DIR / "gen" / name).is_file())


if __name__ == "__main__":
    unittest.main()
