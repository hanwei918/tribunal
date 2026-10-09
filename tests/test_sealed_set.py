"""The held-out set: registering it, and the guards around its single run.

The held-out set is 64 cases under ``data/external/wild/``, keyed by
``eval/answers/wild/ground_truth.json``. It is **not** a third development set:
it was drafted without access to this repository, it is run exactly once from
the commit tagged ``freeze-2026-09-30``, and that single run is one of the two
generalisation figures the submission reports. Everything here follows from
those four facts.

What is asserted, in the order it matters:

* **It is registered, and it is apart.** Its own cases, its own key, its own
  loader and its own runs root; it is absent from ``DEVELOPMENT_SETS``, so
  ``--set all`` does not run it and the combined figure does not include it.
* **Its switches are refused.** ``--force`` and the three recorded-run switches
  are refused for it, each shown on a dirty fixture first -- a scratch runs root
  that already holds its result, which is what the switch would replace -- and
  the fixture is compared byte for byte afterwards, so a refusal that quietly
  wrote something is caught rather than assumed away.
* **Its structure holds.** All 64 cases load through the set's own loader and
  their briefs build; the key loads through ``eval.grade.load_answer_key`` and
  holds 64 records each carrying all four graded fields. These assert on counts
  and on keys, never on a value.
* **Its run directory is a headline directory.** All six destinations that must
  not write into a reported result -- the ablation, the precedents block, a
  later policy version, the baselines, the policy-gap report and the
  recorded-drafts measurement -- refuse ``runs/wild/<model>/``, and each is
  shown refusing it on a dirty fixture first and accepting its own directory
  after.

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
SEALED = sets.SEALED_SET

# The set's own directories, named here so a test can say which one it means.
WILD_CASES_DIR = PROJECT_ROOT / "data" / "external" / "wild"
WILD_KEY_PATH = PROJECT_ROOT / "eval" / "answers" / "wild" / "ground_truth.json"
WILD_EXTERNAL_DIR = PROJECT_ROOT / "eval" / "external" / "wild"

# 501-537 and 601-627: 64 cases over a 127-wide range, so the count is not the
# range and the numbering is not contiguous. Asserted rather than assumed.
ROUTE_DEVIATION_CASES = tuple(range(501, 538))
NO_SHOW_CHARGE_CASES = tuple(range(601, 628))
ALL_SEALED_CASES = ROUTE_DEVIATION_CASES + NO_SHOW_CHARGE_CASES

# The first case of the set, used as the case a scratch fixture "has a result"
# for. It is a number, never a value.
SENTINEL_CASE = 501


def _run_cli(arguments):
    """``sets.main``, with both streams captured. Returns ``(code, out, err)``."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = sets.main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()


def _scratch_runs_with_the_sealed_result(tmp):
    """A dirty fixture: a runs root that already holds the held-out set's result.

    This is what ``--force`` would overwrite and what a recorded-run switch
    would re-take, so it is the fixture each refusal is shown on. The file's
    bytes are returned with it so the caller can prove nothing rewrote it.
    """
    runs = Path(tmp) / "runs"
    run_dir = runs / run_benchmark.SEALED_SET_RUNS_SUBDIR / run_benchmark.model_slug(MODEL)
    run_dir.mkdir(parents=True)
    sentinel = run_dir / "case-{0:05d}.json".format(SENTINEL_CASE)
    sentinel.write_text(
        json.dumps({"case_no": SENTINEL_CASE, "sentinel": "the held-out result"}, indent=2),
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


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------
class SealedSetRegistryTests(unittest.TestCase):
    """The held-out set is registered, and it is not a development set."""

    def test_it_is_registered_by_name_and_marked_sealed(self):
        self.assertIn("wild", sets.BY_NAME)
        self.assertIs(SEALED, sets.BY_NAME["wild"])
        self.assertTrue(SEALED.sealed, "the held-out set is not marked sealed")
        self.assertEqual("wild", SEALED.runs_subdir)
        self.assertIsNone(sets.CORPUS.runs_subdir)

    def test_it_is_not_one_of_the_development_sets(self):
        """``--set all`` and the combined figure both read ``DEVELOPMENT_SETS``."""
        self.assertEqual(["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn(SEALED, sets.DEVELOPMENT_SETS)
        # Three sets are sealed now, and each is printed in a section of its own:
        # the held-out set, the second sealed set imported on 2026-10-03, and the
        # third imported on 2026-10-09.
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1"),
            tuple(item.name for item in sets.SEALED_SETS),
        )
        self.assertIn(SEALED, sets.SEALED_SETS)
        # ``ALL_SETS`` is what the measurements read -- the sets whose recorded
        # runs there are to read -- so the second sealed set, which has not been
        # run, is deliberately not in it.
        self.assertEqual(
            tuple(sets.DEVELOPMENT_SETS) + (SEALED,), sets.ALL_SETS
        )
        self.assertNotIn("wild-v2", [item.name for item in sets.ALL_SETS])
        self.assertFalse(
            any(item.sealed for item in sets.DEVELOPMENT_SETS),
            "a development set is marked sealed",
        )
        # ``wild-dev`` holds the held-out set's own cases as development data,
        # and it is in **neither** tuple above. Being in ``RERUN_SETS`` is what
        # makes it reachable by name while keeping it out of ``--set all``, the
        # combined figure and the recorded-drafts measurement, each of which
        # reads one of those tuples rather than the name table.
        self.assertEqual(("wild-dev",), tuple(item.name for item in sets.RERUN_SETS))
        self.assertIs(sets.WILD_DEV, sets.BY_NAME["wild-dev"])
        self.assertNotIn("wild-dev", [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn("wild-dev", [item.name for item in sets.ALL_SETS])
        self.assertNotIn("wild-dev", [item.name for item in sets.SEALED_SETS])
        self.assertEqual(
            {
                item.name
                for item in (
                    sets.DEVELOPMENT_SETS
                    + sets.SEALED_SETS
                    + sets.RERUN_SETS
                    + sets.NAMED_SETS
                )
            },
            set(sets.BY_NAME),
            "the name table is not exactly the registered sets",
        )

    def test_wild_dev_is_excluded_from_the_combined_figure_and_from_set_all(self):
        """Registered and reachable by name, and outside both aggregated readings.

        Two readings aggregate sets: :func:`sets.combined_figures` sums
        ``DEVELOPMENT_SETS``, and ``--set all`` runs them. A set holding the
        held-out set's own cases must be in neither, so the combined figure is
        shown not reading a ``runs/wild-dev/`` directory that does hold a case,
        and ``--set all`` is shown not running a case only that set holds -- by
        refusing the selection, because a selection that names no case of any
        selected set runs nothing and an empty run is not a result.

        ``LLMClient`` is patched to raise, so a ``--set all`` that did select
        the set fails here instead of making a paid call.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            dev_dir = runs / "wild-dev" / run_benchmark.model_slug(MODEL)
            dev_dir.mkdir(parents=True)
            (dev_dir / "case-{0:05d}.json".format(SENTINEL_CASE)).write_text(
                "{}", encoding="utf-8"
            )

            # The set's own reading sees the case...
            self.assertEqual(
                [SENTINEL_CASE], sets.cached_cases(sets.WILD_DEV, MODEL, runs)
            )
            # ...and the combined figure does not, because it reads only the two
            # development sets, neither of which has been run in this root.
            self.assertEqual((0, None), sets.combined_figures(MODEL, runs))

            original = run_benchmark.llm.LLMClient

            def refuse(*arguments, **keywords):
                raise AssertionError(
                    "--set all built a client, so it ran a case it must not"
                )

            run_benchmark.llm.LLMClient = refuse
            try:
                code, out, err = _run_cli(
                    [
                        "--set",
                        "all",
                        "--cases",
                        str(SENTINEL_CASE),
                        "--runs-dir",
                        str(runs),
                    ]
                )
            finally:
                run_benchmark.llm.LLMClient = original
            self.assertEqual(1, code, "a selection that runs nothing was accepted")
            # Case 501 is a held-out case and nothing else in the selection
            # holds it, so the selection names no case of any selected set. That
            # is an error about the selection rather than a run that produced
            # nothing, and it is refused before a client exists.
            self.assertIn("--cases names case(s) {0}".format(SENTINEL_CASE), err)
            self.assertIn("does not hold", err)
            self.assertEqual("", out, "the refused invocation printed a summary")
            self.assertEqual(
                ["case-{0:05d}.json".format(SENTINEL_CASE)],
                sorted(path.name for path in dev_dir.iterdir()),
            )
            self.assertFalse(
                (runs / run_benchmark.SEALED_SET_RUNS_SUBDIR).exists(),
                "--set all wrote into the held-out set's own run root",
            )

    def test_its_cases_are_the_64_it_was_imported_with(self):
        self.assertEqual(64, len(SEALED.cases))
        self.assertEqual(ALL_SEALED_CASES, tuple(SEALED.cases))
        self.assertEqual(64, len(set(SEALED.cases)))
        self.assertEqual(37, len(ROUTE_DEVIATION_CASES))
        self.assertEqual(27, len(NO_SHOW_CHARGE_CASES))

    def test_it_has_its_own_case_root_key_and_loader(self):
        """Its own loader is what loads it, and its own key is what grades it."""
        self.assertEqual(WILD_CASES_DIR, SEALED.case_root)
        self.assertEqual(WILD_KEY_PATH, SEALED.key_path)
        for other in sets.DEVELOPMENT_SETS:
            with self.subTest(other=other.name):
                self.assertNotEqual(other.key_path, SEALED.key_path)
                self.assertNotEqual(other.case_root, SEALED.case_root)
                self.assertNotEqual(other.runs_subdir, SEALED.runs_subdir)
                self.assertEqual(
                    set(),
                    set(other.cases) & set(SEALED.cases),
                    "the held-out set shares a case number with a development set",
                )
        # ``wild-dev`` is the one registered set that deliberately **shares** the
        # held-out set's key and case root: it is those 64 cases read as
        # development data, and grading them against anything else would grade a
        # reading of one set against another's answers. What it must not share is
        # the run directory, which is what leaves the single run under
        # ``runs/wild/`` unread.
        self.assertEqual(SEALED.key_path, sets.WILD_DEV.key_path)
        self.assertEqual(SEALED.case_root, sets.WILD_DEV.case_root)
        self.assertEqual(SEALED.cases, sets.WILD_DEV.cases)
        self.assertNotEqual(SEALED.runs_subdir, sets.WILD_DEV.runs_subdir)
        self.assertNotEqual(SEALED.run_dir(MODEL), sets.WILD_DEV.run_dir(MODEL))

    def test_its_runs_go_to_its_own_root(self):
        self.assertEqual(
            run_benchmark.RUNS_DIR / "wild" / run_benchmark.model_slug(MODEL),
            SEALED.run_dir(MODEL),
        )
        self.assertEqual(
            run_benchmark.RUNS_DIR / "wild", SEALED.runs_dir()
        )
        self.assertNotEqual(sets.CORPUS.run_dir(MODEL), SEALED.run_dir(MODEL))
        self.assertNotEqual(sets.SECOND_SET.run_dir(MODEL), SEALED.run_dir(MODEL))

    def test_its_summary_names_it_the_held_out_set_run_once(self):
        summary = SEALED.summary
        self.assertIn("held-out set", summary)
        self.assertIn("wild-v1", summary)
        self.assertIn("run once", summary)
        self.assertIn("generalisation figure", summary)

    def test_its_cases_are_not_in_the_corpus_manifest(self):
        """Adding them to ``data/index.json`` would change the 29-case corpus."""
        manifest = {
            entry["case_no"] for entry in loader._read_json(PROJECT_ROOT / "data" / "index.json")
        }
        self.assertEqual(29, len(manifest))
        self.assertEqual(set(), manifest & set(SEALED.cases))


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
class SealedSetReportTests(unittest.TestCase):
    """It is shown on its own, and never inside the combined figure."""

    def test_a_sealed_run_is_never_counted_in_the_combined_figure(self):
        """A cached sealed case must not move the combined figure at all."""
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, _ = _scratch_runs_with_the_sealed_result(tmp)
            self.assertTrue(sentinel.is_file(), "the fixture was not built")

            produced, combined = sets.combined_figures(MODEL, runs)

            self.assertEqual(0, produced, "the combined figure counted a sealed case")
            self.assertIsNone(combined)

            # And the set itself is read off the same cache, so the assertion
            # above is about the combination rather than about the file being
            # invisible to this code.
            self.assertEqual([SENTINEL_CASE], sets.cached_cases(SEALED, MODEL, runs))

    def test_the_report_prints_it_in_a_section_of_its_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            text = sets.render_development_sets(MODEL, runs)

            self.assertIn(
                "The held-out set (wild-v1), on its own and never in the combined figure:", text
            )
            self.assertIn("wild", text)
            self.assertIn("0/64", text)
            self.assertIn("not run", text)
            self.assertIn(sets.SEALED_SET_CAVEAT, text)

    def test_the_combined_line_names_no_sealed_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, _, _, _ = _scratch_runs_with_the_sealed_result(tmp)
            text = sets.render_development_sets(MODEL, runs)

            combined = text.split(
                "Combined, every case graded against the key it belongs to:", 1
            )[1]
            combined = combined.split(
                "The held-out set (wild-v1), on its own and never in the combined figure:", 1
            )[0]
            self.assertIn("no case of any development set has been run", combined)
            self.assertNotIn("wild", combined)
            self.assertNotIn("64", combined)


# --------------------------------------------------------------------------
# The switches
# --------------------------------------------------------------------------
class SealedSetSwitchGuardTests(unittest.TestCase):
    """``--force`` and the three recorded-run switches are refused for this set.

    Each refusal is shown on a dirty fixture first: a scratch runs root that
    already holds the held-out set's result, which is exactly what the switch
    would replace or re-take. The fixture is compared byte for byte afterwards.
    """

    def test_force_is_refused_and_leaves_the_result_it_would_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_sealed_result(tmp)

            code, _, err = _run_cli(["--set", "wild", "--force", "--runs-dir", str(runs)])

            self.assertEqual(1, code, "a held-out run accepted --force")
            self.assertIn("the sealed set {0} is run once".format(SEALED.name), err)
            self.assertIn("--force", err)
            self.assertEqual(before, sentinel.read_bytes(), "the held-out result was rewritten")
            self.assertEqual(
                {sentinel.name: before}, _state(run_dir), "the run directory gained a file"
            )

    def test_the_other_three_switches_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_sealed_result(tmp)
            source = run_dir

            for flag, value in (
                ("--replay-advocates", str(source)),
                ("--replay-check", str(source)),
                ("--verify-recorded-drafts", str(source)),
            ):
                with self.subTest(flag=flag):
                    code, _, err = _run_cli(
                        ["--set", "wild", flag, value, "--runs-dir", str(runs)]
                    )
                    self.assertEqual(1, code, "{0} was accepted for the held-out set".format(flag))
                    self.assertIn("the sealed set {0} is run once".format(SEALED.name), err)
                    self.assertIn(flag, err)
                    self.assertEqual(
                        before, sentinel.read_bytes(), "{0} rewrote the held-out result".format(flag)
                    )
                    self.assertEqual({sentinel.name: before}, _state(run_dir))

    def test_the_refusal_is_for_this_set_and_not_for_the_others(self):
        """The same switches are not refused by this guard for a development set."""
        for development_set in sets.DEVELOPMENT_SETS:
            with self.subTest(development_set=development_set.name):
                self.assertIsNone(sets.assert_not_sealed(development_set, "--force"))

    def test_the_guard_goes_red_on_the_sealed_set(self):
        for switch in ("--force", "--replay-advocates", "--replay-check"):
            with self.subTest(switch=switch):
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    sets.assert_not_sealed(SEALED, switch)
                self.assertIn("the sealed set {0} is run once".format(SEALED.name), str(caught.exception))
                self.assertIn(switch, str(caught.exception))


# --------------------------------------------------------------------------
# The structure
# --------------------------------------------------------------------------
class SealedSetStructureTests(unittest.TestCase):
    """64 cases load and brief; the key loads and holds 64 complete records.

    Counts and keys only. No expected ruling, amount, compensation or referral
    is read, compared or printed anywhere in this class -- the key is asserted
    to be *well formed*, not to say anything in particular.
    """

    def test_all_64_cases_load_through_the_sets_own_loader(self):
        self.assertEqual(64, len(SEALED.cases))
        for case_no in SEALED.cases:
            with self.subTest(case_no=case_no):
                case = SEALED.load_case(case_no)
                self.assertEqual(case_no, case["case_no"])
                self.assertEqual(case_no, case["dispute"]["case_no"])
                self.assertEqual(
                    {"case_no", "dispute", "evidence", "schema_version"}, set(case)
                )

    def test_all_64_briefs_build(self):
        for case_no in SEALED.cases:
            with self.subTest(case_no=case_no):
                built = brief.build_brief_for_case(SEALED.load_case(case_no))
                self.assertIsInstance(built, dict)
                self.assertTrue(built)

    def test_the_index_names_64_cases_and_the_key_agrees_with_it(self):
        entries = loader.load_external_index(SEALED.case_root)
        self.assertEqual(64, len(entries))
        self.assertEqual([case_no for case_no in SEALED.cases], [e["case_no"] for e in entries])
        self.assertEqual(
            {("ROUTE_DEVIATION"): 37, ("NO_SHOW_CHARGE"): 27},
            {
                category: sum(1 for entry in entries if entry["category"] == category)
                for category in sorted({entry["category"] for entry in entries})
            },
        )
        self.assertEqual(set(SEALED.cases), set(SEALED.key()))

    def test_the_key_loads_and_each_record_carries_all_four_graded_fields(self):
        key = grade.load_answer_key(SEALED.key_path)
        self.assertEqual(64, len(key))
        self.assertEqual(set(SEALED.cases), set(key))
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

    def test_the_key_file_is_the_only_thing_in_the_sets_answer_directory(self):
        """One key, not a key and a second copy of it that can drift."""
        directory = WILD_KEY_PATH.parent
        self.assertEqual(
            ["ground_truth.json"],
            sorted(path.name for path in directory.iterdir() if path.is_file()),
        )


# --------------------------------------------------------------------------
# The headline directories
# --------------------------------------------------------------------------
class SealedRunDirectoryIsHeadlineTests(unittest.TestCase):
    """Every destination that must not write into a reported result refuses it.

    Six of them: the ablation, the precedents block, a later policy version, the
    baselines, the policy-gap report and the recorded-drafts measurement. Each
    is shown refusing ``runs/wild/<model>/`` on that dirty fixture first, and
    accepting the directory of its own after -- so a check that refused
    everything would fail the second half.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.runs = Path(self._tmp.name) / "runs"
        self.sealed_run_dir = (
            self.runs / run_benchmark.SEALED_SET_RUNS_SUBDIR / run_benchmark.model_slug(MODEL)
        )
        self.sealed_run_dir.mkdir(parents=True)

    def test_it_is_one_of_the_headline_directories(self):
        """The precondition every check below depends on."""
        headline = [
            path.resolve() for path in run_benchmark.headline_run_directories(self.runs, MODEL)
        ]
        self.assertIn(self.sealed_run_dir.resolve(), headline)
        self.assertEqual(5, len(headline), "the headline directories are not five")
        self.assertEqual(
            {
                (self.runs / run_benchmark.model_slug(MODEL)).resolve(),
                (self.runs / "codex" / run_benchmark.model_slug(MODEL)).resolve(),
                self.sealed_run_dir.resolve(),
                (
                    self.runs
                    / run_benchmark.WILD_V2_SET_RUNS_SUBDIR
                    / run_benchmark.model_slug(MODEL)
                ).resolve(),
                (
                    self.runs
                    / run_benchmark.SEALED_V1_SET_RUNS_SUBDIR
                    / run_benchmark.model_slug(MODEL)
                ).resolve(),
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
        self.assertEqual(
            self.runs / "precedents" / run_benchmark.model_slug(MODEL), accepted
        )

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
        """Pointed at the held-out run directory, the measurement is refused.

        The destination is always ``<runs-dir>/verify-recorded-drafts/<model>/``,
        so the way it lands inside a reported result is by being given a run
        directory as its runs root -- the held-out set's own, here. Nothing is
        read before the refusal, so no source run has to exist.
        """
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            verify_drafts.verify_recorded_run(
                self.sealed_run_dir,
                [SENTINEL_CASE],
                model=MODEL,
                runs_dir=self.sealed_run_dir,
                progress=lambda text: None,
            )
        self.assertIn("headline run directory", str(caught.exception))
        self.assertIn(str(self.sealed_run_dir.resolve()), str(caught.exception))
        self.assertEqual(
            {},
            _state(self.sealed_run_dir),
            "a refused recorded-drafts run wrote into the held-out run directory",
        )

        # And the same guard takes the destination of its own, so a check that
        # refused everything would fail here rather than pass quietly.
        accepted = verify_drafts.assert_recorded_drafts_destination(self.runs, MODEL)
        self.assertEqual(
            self.runs / "verify-recorded-drafts" / run_benchmark.model_slug(MODEL),
            accepted,
        )


# --------------------------------------------------------------------------
# Nothing is created under the held-out set's root again
# --------------------------------------------------------------------------
class HeldOutRootGuardTests(unittest.TestCase):
    """One guard refuses every destination that lies under ``runs/wild/``.

    The held-out set's single run is one of the two generalisation figures the
    submission reports -- the second sealed set's single run is the other -- and
    it was made once, so nothing may be created under its root again: not a
    case, not an ablated run, not a run at a later policy version, not a report.
    The re-runnable set's own root, ``runs/wild-dev/``, is a **different path
    component** and is deliberately not caught -- a prefix test on the string
    would refuse it -- so the half that matters is asserted rather than
    described.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.runs = Path(self._tmp.name) / "runs"
        self.slug = run_benchmark.model_slug(MODEL)
        self.held_out = self.runs / run_benchmark.SEALED_SET_RUNS_SUBDIR

    def test_every_destination_under_the_held_out_root_is_refused(self):
        for relative in (
            (),
            (self.slug,),
            (run_benchmark.ABLATION_DIRNAME, "clause-notes", self.slug),
            (run_benchmark.PRECEDENTS_DIRNAME, self.slug),
            (run_benchmark.policy_v_directory_name(2), self.slug),
            (run_benchmark.AMOUNT_RULE_DIRNAME, "signed", self.slug),
            ("verify-recorded-drafts", self.slug),
            ("anything", "at", "all"),
        ):
            destination = self.held_out.joinpath(*relative)
            with self.subTest(destination=str(destination)):
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    run_benchmark.assert_not_under_the_held_out_root(
                        destination, self.runs
                    )
                self.assertIn("nothing is created under it again", str(caught.exception))
                self.assertIn("--set wild-dev", str(caught.exception))

    def test_the_re_runnable_sets_root_is_not_caught(self):
        """``runs/wild-dev`` is a different component from ``runs/wild``.

        The same 64 cases are runnable as development data and their runs root is
        one character away from the one that is closed, so a guard that compared
        the paths as strings would refuse the only place a re-run may go.
        """
        for relative in (
            (),
            (self.slug,),
            (run_benchmark.policy_v_directory_name(2), self.slug),
        ):
            destination = (self.runs / run_benchmark.WILD_DEV_RUNS_SUBDIR).joinpath(
                *relative
            )
            with self.subTest(destination=str(destination)):
                self.assertEqual(
                    destination,
                    run_benchmark.assert_not_under_the_held_out_root(
                        destination, self.runs
                    ),
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
                    run_benchmark.assert_not_under_the_held_out_root(
                        destination, self.runs
                    ),
                )

    def test_the_run_refuses_a_destination_under_the_held_out_root(self):
        """A run aimed at the held-out set's own root is refused before it writes.

        Shown on the dirty fixture: a scratch runs root that already holds the
        held-out set's result. The client factory fails the test if it is ever
        called, so a refusal that came after a call would be caught rather than
        assumed away, and the fixture is compared byte for byte afterwards.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_sealed_result(tmp)

            def must_not_be_built(sink):
                raise AssertionError(
                    "a client was built for a run that should have been refused"
                )

            with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                sets.run_set(
                    SEALED,
                    MODEL,
                    runs_dir=runs,
                    cases=(SENTINEL_CASE,),
                    client_factory=must_not_be_built,
                    progress=lambda text: None,
                )
            self.assertIn("nothing is created under it again", str(caught.exception))
            self.assertEqual(
                before, sentinel.read_bytes(), "the held-out result was rewritten"
            )
            self.assertEqual(
                {sentinel.name: before}, _state(run_dir), "the run directory gained a file"
            )

    def test_the_command_line_refuses_set_wild_with_each_switch(self):
        """``--set wild`` plus any of the four switches, refused, naming wild-dev.

        Each of the four moves a set's run one level down under the set's own
        root, so each of them would write under ``runs/wild/``. The refusal names
        the set to use instead of it, and the dirty fixture is byte-identical
        after each one.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_sealed_result(tmp)

            # A switch that got past the refusal would build a client and start
            # running cases, so the client is patched to fail the test instead.
            # Without this the test would make a real call on the tree the guard
            # is meant to be added to.
            original = run_benchmark.llm.LLMClient

            def refuse(*arguments, **keywords):
                raise AssertionError(
                    "--set wild built a client, so it accepted a switch it must not"
                )

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
                            ["--set", "wild", "--runs-dir", str(runs)] + arguments
                        )
                        self.assertEqual(
                            1, code, "{0} was accepted for --set wild".format(arguments)
                        )
                        # The command-line layer's own sentence rather than the
                        # shared guard's: the guard names ``--set wild-dev`` too,
                        # so that phrase alone would also be satisfied by a
                        # message that never came through this layer.
                        self.assertIn("Name --set wild-dev instead", err)
                        self.assertEqual(
                            before,
                            sentinel.read_bytes(),
                            "{0} rewrote the held-out result".format(arguments),
                        )
                        self.assertEqual({sentinel.name: before}, _state(run_dir))
            finally:
                run_benchmark.llm.LLMClient = original


if __name__ == "__main__":
    unittest.main()
