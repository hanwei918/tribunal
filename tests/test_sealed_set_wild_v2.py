"""The second sealed set: registering it, and the guards around its single run.

``wild-v2`` is 20 cases under ``data/external/wild-v2/``, keyed by
``eval/answers/wild-v2/ground_truth.json``. Like the held-out set it is **not**
a third development set: it was prepared by OpenAI Codex for the owner, it is
run exactly once from a commit whose ``tribunal/``, ``prompts/`` and ``policy/``
trees equal those at ``freeze-2026-10-03``, and that single run is the
submission's generalisation figure. Its registration fixes policy
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
* **Its root is closed outright.** The component-wise path guard refuses every
  destination under ``runs/wild-v2/`` -- the plain sealed run's own directory
  included, now that its single run has been made -- and a scratch runs root is
  no exception, because the guard compares components and not one absolute path.
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
import dataclasses
import io
import json
import os
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
from tests import test_development_sets as dev_rig  # noqa: E402
from tribunal import brief, events, llm, loader, money, transcript  # noqa: E402

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

# The import note, whose digest table is the record of every imported file as
# committed. Reading it is reading a document this repository wrote, not the set.
IMPORT_NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-03-wild-v2-imported.md"


def _digests_the_import_note_states():
    """``{repository path: sha256}`` from the import note's digest table.

    The table is a Markdown table of ``| ``path`` | ``digest`` |`` rows under one
    heading. It is parsed rather than hard-coded here, so the test reads the
    same record a reader does; the test that uses it asserts the count, so a
    parse that silently found nothing fails there rather than passing.
    """
    text = IMPORT_NOTE.read_text(encoding="utf-8")
    heading = "## The digest of every imported file"
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    stated = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) != 4:
            continue
        path_cell, digest_cell = cells[1], cells[2]
        if not (path_cell.startswith("`") and path_cell.endswith("`")):
            continue
        if not (digest_cell.startswith("`") and digest_cell.endswith("`")):
            continue
        path, digest = path_cell[1:-1], digest_cell[1:-1]
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            continue
        stated[path] = digest
    return stated


def _run_cli(arguments):
    """``sets.main``, with both streams captured and no client buildable.

    Every invocation of the command line for ``wild-v2`` is refused before a
    client is built, so no test here may be able to build one: the class is
    patched to raise for the duration of the call, and a guard that let a run
    start fails the test instead of reaching the network. Returns
    ``(code, out, err)``.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    original, refuse = _refuse_to_build_a_client()
    run_benchmark.llm.LLMClient = refuse
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = sets.main(arguments)
    finally:
        run_benchmark.llm.LLMClient = original
    return code, stdout.getvalue(), stderr.getvalue()


def _run_cli_over(runs, arguments):
    """``_run_cli`` with both modules' ``RUNS_DIR`` moved to ``runs``.

    The sealed set's run root is fixed at the repository's own ``runs/``, so a
    test that wants a scratch root moves the constant rather than passing the
    flag: ``--runs-dir`` is refused for this set, and that refusal is what
    ``WildV2RunsRootLockTests`` shows. Both modules are moved, because the
    command line reads one and the runner reads the other.
    """
    with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
        run_benchmark, "RUNS_DIR", runs
    ):
        return _run_cli(arguments)


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
        shown not running a case only that set holds -- by refusing the
        selection, because a selection that names no case of any selected set
        runs nothing and an empty run is not a result.

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
            self.assertEqual(1, code, "a selection that runs nothing was accepted")
            # Case 701 is a wild-v2 case and nothing else in the selection holds
            # it, so the selection names no case of any selected set. That is an
            # error about the selection rather than a run that produced nothing,
            # and it is refused before a client exists.
            self.assertIn("--cases names case(s) {0}".format(SENTINEL_CASE), err)
            self.assertIn("does not hold", err)
            self.assertEqual("", out, "the refused invocation printed a summary")
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

            code, _, err = _run_cli_over(runs, ["--set", "wild-v2", "--force"])

            self.assertEqual(1, code, "a sealed run accepted --force")
            self.assertIn("the sealed set {0} is run once".format(WILD_V2.name), err)
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
                    code, _, err = _run_cli_over(
                        runs, ["--set", "wild-v2", flag, str(run_dir)]
                    )
                    self.assertEqual(1, code, "{0} was accepted for the sealed set".format(flag))
                    self.assertIn("the sealed set {0} is run once".format(WILD_V2.name), err)
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
                        code, _out, err = _run_cli_over(
                            runs, ["--set", "wild-v2"] + arguments
                        )
                        self.assertEqual(
                            1, code, "{0} was accepted for --set wild-v2".format(arguments)
                        )
                        self.assertIn("wild-v2", err)
                        self.assertIn("nothing is created under it again", err)
                        self.assertNotIn(
                            "wild-dev",
                            err,
                            "the second sealed set's refusal carried the "
                            "held-out set's remedy",
                        )
                        self.assertEqual(
                            before,
                            sentinel.read_bytes(),
                            "{0} rewrote the sealed result".format(arguments),
                        )
                        self.assertEqual({sentinel.name: before}, _state(run_dir))
            finally:
                run_benchmark.llm.LLMClient = original

    def test_the_policy_version_flag_is_refused(self):
        """Its version is fixed by registration, so the flag is not its to take.

        Version 1 is in the list with the others. A parser default of
        ``DEFAULT_POLICY_VERSION`` would make ``--policy-version 1``
        indistinguishable from no flag at all, and that is exactly the flag this
        set must refuse, so the case is named here rather than left out.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_wild_v2_result(tmp)

            for version in ("1", "2", "3"):
                with self.subTest(version=version):
                    code, _out, err = _run_cli_over(
                        runs, ["--set", "wild-v2", "--policy-version", version]
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
                    self.assertIn(
                        "the sealed set {0} is run once".format(development_set.name),
                        str(caught.exception),
                    )
                    self.assertIn(switch, str(caught.exception))


# --------------------------------------------------------------------------
# The lock on the sealed run
# --------------------------------------------------------------------------
def _scripted_events_log(runs):
    """A scratch ``events.jsonl`` with three interesting cases and no others.

    One case whose only attempt is a judge ``SHAPE`` with every call answered
    200, one whose two attempts are both ``TRANSPORT``, and one whose single
    attempt ended with no terminal event. Written with the real event log, so the
    protocol reads the file a run would have written. Only case numbers, event
    names and failure kinds appear -- no case content and no answer value.
    """
    run_dir = (
        runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR / run_benchmark.model_slug(MODEL)
    )
    run_dir.mkdir(parents=True)

    first = events.EventLog(run_dir / events.EVENTS_FILE, invocation_id="invocation-1")
    first.record(events.EVENT_CASE_START, case_no=CASE_JUDGE_SHAPE, position=1, total=3)
    first.record(
        events.EVENT_AGENT_CALL,
        case_no=CASE_JUDGE_SHAPE,
        role=transcript.ROLE_JUDGE,
        status=200,
    )
    first.record(
        events.EVENT_CASE_FAILED,
        case_no=CASE_JUDGE_SHAPE,
        failure_kind=run_benchmark.FAILURE_SHAPE,
    )
    first.record(events.EVENT_CASE_START, case_no=CASE_TRANSPORT, position=2, total=3)
    first.record(
        events.EVENT_CASE_FAILED,
        case_no=CASE_TRANSPORT,
        failure_kind=run_benchmark.FAILURE_TRANSPORT,
    )
    first.record(events.EVENT_CASE_START, case_no=CASE_KILLED, position=3, total=3)
    first.record(
        events.EVENT_AGENT_CALL,
        case_no=CASE_KILLED,
        role=transcript.ROLE_JUDGE,
        status=200,
    )

    second = events.EventLog(run_dir / events.EVENTS_FILE, invocation_id="invocation-2")
    second.record(events.EVENT_CASE_START, case_no=CASE_TRANSPORT, position=1, total=1)
    second.record(
        events.EVENT_CASE_FAILED,
        case_no=CASE_TRANSPORT,
        failure_kind=run_benchmark.FAILURE_TRANSPORT,
    )


# The plan ``--check`` prints for the log above, written out rather than computed
# here, so a change to the rendering is a failing test and not a test that agrees
# with itself. Cases 701 and 704 are the two the log decides; 705 has an attempt
# that does not count, so it is still run; 702, 703 and 706 to 720 have no events.
EXPECTED_CHECK_PLAN = (
    "sealed set wild-v2 -- what one plain invocation would run\n"
    "  would run (18): 702, 703, 705, 706, 707, 708, 709, 710, 711, 712, 713, "
    "714, 715, 716, 717, 718, 719, 720\n"
    "  would not run (2):\n"
    "    not retried under the sealed protocol: 701 (SHAPE, every call answered 200)\n"
    "    not retried under the sealed protocol: 704 (two attempts)\n"
    "  attempts that do not count (1):\n"
    "    attempt with no terminal event, so it does not count under the sealed "
    "protocol: 705\n"
)


class WildV2SealedRunLockTests(unittest.TestCase):
    """The sealed run is the owner's, and only the owner's.

    Two locks. An opt-in the owner sets in the environment for the one command,
    and ``--check``, which runs every refusal and every frozen-argument check and
    then prints the plan without running anything. No test here can build a
    client -- ``_run_cli`` patches the class to raise -- and none of them writes:
    the runs root is a temporary directory, and both modules are made to believe
    it is the repository's own, so the default ``--runs-dir`` is the scratch one.
    """

    def _invocation(self, tmp, *extra):
        runs = Path(tmp) / "runs"
        with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
            run_benchmark, "RUNS_DIR", runs
        ):
            code, out, err = _run_cli(
                ["--set", "wild-v2", "--concurrency", "2", "--timeout", "900"]
                + list(extra)
            )
        return runs, code, out, err

    def test_without_the_opt_in_the_invocation_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ):
                os.environ.pop(sets.SEALED_RUN_ENV_VAR, None)
                runs, code, _out, err = self._invocation(tmp)

            self.assertEqual(1, code, "the sealed run was not locked")
            self.assertIn(sets.SEALED_RUN_ENV_VAR, err)
            self.assertIn("owner only", err)
            self.assertFalse(runs.exists(), "the refused invocation created the runs root")

    def test_the_opt_in_set_to_any_other_value_is_refused(self):
        for value in ("wild", "wild-dev", "", "1", "wild-v2x", "WILD-V2"):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    with mock.patch.dict(os.environ, {sets.SEALED_RUN_ENV_VAR: value}):
                        runs, code, _out, err = self._invocation(tmp)
                    self.assertEqual(
                        1, code, "{0!r} unlocked the sealed run".format(value)
                    )
                    self.assertIn(sets.SEALED_RUN_ENV_VAR, err)
                    self.assertFalse(runs.exists())

    def test_check_creates_nothing_even_when_the_runs_root_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, code, out, err = self._invocation(tmp, "--check")

            self.assertEqual(0, code, err)
            self.assertFalse(runs.exists(), "--check created the runs root")
            self.assertIn("would run (20): 701", out)

    def test_check_prints_exactly_the_plan_for_a_scripted_events_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            _scripted_events_log(runs)
            before = _state(runs)

            with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                code, out, err = _run_cli(
                    [
                        "--set",
                        "wild-v2",
                        "--concurrency",
                        "2",
                        "--timeout",
                        "900",
                        "--check",
                    ]
                )

            self.assertEqual(0, code, err)
            self.assertEqual(EXPECTED_CHECK_PLAN, out)
            self.assertEqual(before, _state(runs), "--check wrote under the runs root")

    def test_check_does_not_need_the_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ):
                os.environ.pop(sets.SEALED_RUN_ENV_VAR, None)
                runs, code, _out, err = self._invocation(tmp, "--check")

            self.assertEqual(0, code, err)
            self.assertFalse(runs.exists())


class WildV2RunsRootLockTests(unittest.TestCase):
    """``--runs-dir`` is fixed at the repository's own ``runs/``.

    The single run has to land in the directory the six destinations read, so a
    scratch root is refused rather than accepted: an invocation that pointed it
    somewhere else would produce a run nothing reads while looking exactly like
    the sealed run. The comparison is case-folded, because this volume is
    case-insensitive and ``runs/`` and ``RUNS/`` are one directory here.
    """

    def test_a_scratch_runs_dir_is_refused_and_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "elsewhere"
            with mock.patch.dict(os.environ, {sets.SEALED_RUN_ENV_VAR: "wild-v2"}):
                code, out, err = _run_cli(
                    [
                        "--set",
                        "wild-v2",
                        "--concurrency",
                        "2",
                        "--timeout",
                        "900",
                        "--runs-dir",
                        str(scratch),
                    ]
                )

            self.assertEqual(1, code, "a scratch runs root was accepted for the sealed run")
            self.assertIn("--runs-dir", err)
            self.assertIn(str(scratch), err)
            self.assertIn("is not the repository's own", err)
            self.assertEqual("", out, "the refused invocation printed something")
            self.assertFalse(scratch.exists(), "the refused invocation created the root")

    def test_the_runs_root_is_accepted_whatever_its_case(self):
        """``RUNS/`` is ``runs/`` here, so the flag is not refused for its case.

        Both modules' ``RUNS_DIR`` are moved to a scratch root, which is what
        makes that root *the repository's own* for the duration of the call. The
        flag then names the same path in another case, and the invocation gets
        past the lock: the refusal it meets is the root guard's, which is what
        says the case-folded comparison accepted the flag. Were the lock still to
        refuse it, the message would be the lock's -- and the two are asserted
        apart here so one cannot stand in for the other.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            other_case = Path(str(runs).replace("/runs", "/RUNS"))
            self.assertNotEqual(str(runs), str(other_case))
            with mock.patch.dict(
                os.environ, {sets.SEALED_RUN_ENV_VAR: "wild-v2"}
            ), mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ), mock.patch.object(
                run_benchmark.llm, "load_api_key", return_value="a-key"
            ):
                code, _out, err = _run_cli(
                    [
                        "--set",
                        "wild-v2",
                        "--concurrency",
                        "2",
                        "--timeout",
                        "900",
                        "--runs-dir",
                        str(other_case),
                    ]
                )
            self.assertEqual(
                1, code, "the case-folded runs root was accepted for the sealed run"
            )
            self.assertNotIn(
                "is not the repository's own",
                err,
                "the lock refused a runs root that differs only in case",
            )
            self.assertIn("nothing is created under it again", err)

    def test_a_set_that_registers_no_arguments_keeps_the_flag(self):
        """The lock is the registration's, so a development set is not caught.

        The runner is replaced by a stub that raises, so the invocation is shown
        reaching it with the scratch root rather than being refused before it.
        """
        sentinel = "the development run was reached"
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"

            def stub(*arguments, **keywords):
                raise AssertionError(sentinel)

            with mock.patch.object(sets, "run_set", stub):
                with self.assertRaises(AssertionError) as caught:
                    _run_cli(
                        [
                            "--set",
                            "codex",
                            "--cases",
                            str(sets.BY_NAME["codex"].cases[0]),
                            "--runs-dir",
                            str(runs),
                        ]
                    )
            self.assertEqual(sentinel, str(caught.exception))


class WildV2CaseSelectionTests(unittest.TestCase):
    """``--cases`` is refused for this set, and an empty selection is an error."""

    def test_cases_is_refused_for_this_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.dict(
                os.environ, {sets.SEALED_RUN_ENV_VAR: "wild-v2"}
            ), mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ), mock.patch.object(
                run_benchmark.llm, "load_api_key", return_value="a-key"
            ):
                code, out, err = _run_cli(
                    ["--set", "wild-v2", "--cases", str(WILD_V2.cases[0])]
                )

            self.assertEqual(1, code, "--cases was accepted for the sealed set")
            self.assertIn("--cases is refused for it", err)
            self.assertIn("one command", err)
            self.assertEqual("", out)
            self.assertFalse(runs.exists(), "the refused invocation created the root")

    def test_an_unknown_case_is_an_error_for_every_set(self):
        """Never a silent exit 0, whichever set is named.

        A selection that names no case of any selected set runs nothing, and the
        run loop would then find every subset empty and report success. It is an
        error about the selection instead, refused before a client exists.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            for name in ("all", "corpus", "codex", "wild", "wild-dev"):
                with self.subTest(development_set=name):
                    code, out, err = _run_cli_over(
                        runs, ["--set", name, "--cases", "999999"]
                    )
                    self.assertEqual(
                        1, code, "{0} accepted a case it does not hold".format(name)
                    )
                    self.assertIn("--cases names case(s) 999999", err)
                    self.assertEqual("", out, "a refused selection printed a summary")
            self.assertFalse(runs.exists(), "a refused invocation created the root")


class CaseFoldedSealedRootTests(unittest.TestCase):
    """The sealed-root guard compares path components case-folded.

    This volume is case-insensitive, so ``runs/WILD-V2`` names the same
    directory as ``runs/wild-v2``. A guard that compared the paths as they are
    written would answer about the spelling rather than about the directory: the
    same place refused under one spelling and accepted under the other.
    """

    def test_a_sealed_root_spelled_in_another_case_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            slug = run_benchmark.model_slug(MODEL)
            for destination in (
                runs / "WILD-V2",
                runs / "Wild",
                runs / "WILD" / slug,
                runs / "wild-V2" / slug,
            ):
                with self.subTest(destination=str(destination.relative_to(runs))):
                    with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                        run_benchmark.assert_not_under_the_held_out_root(
                            destination, runs
                        )
                    self.assertIn("lies under", str(caught.exception))

    def test_the_folded_comparison_keeps_wild_dev_distinct(self):
        """Case-folding must not merge two directories that differ by a word."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            slug = run_benchmark.model_slug(MODEL)
            for destination in (runs / "Wild-Dev" / slug, runs / "WILD-DEV"):
                with self.subTest(destination=str(destination.relative_to(runs))):
                    self.assertEqual(
                        destination,
                        run_benchmark.assert_not_under_the_held_out_root(
                            destination, runs
                        ),
                    )


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
        """The refusal, with a client factory that raises behind it.

        ``client_factory`` is the one ``verify_recorded_run`` builds its client
        with, and it is built after the destination check. A factory that raises
        is therefore what turns a refusal that stopped happening into this test's
        failure rather than into a call against the real key.
        """

        def refuse_to_build_a_client(_sink):
            raise AssertionError(
                "a client was built, so the recorded-drafts destination was accepted"
            )

        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            verify_drafts.verify_recorded_run(
                self.sealed_run_dir,
                [SENTINEL_CASE],
                model=MODEL,
                runs_dir=self.sealed_run_dir,
                client_factory=refuse_to_build_a_client,
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
    """The component-wise guard closes both sealed roots outright.

    ``runs/wild/`` is closed: its single run was made once and nothing is
    created under it again. ``runs/wild-v2/`` is closed the same way, now that
    its own single run has been made: it accepts no destination at all -- the
    plain sealed run's own directory included -- and every switched destination
    below it is refused as well.
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
            (self.slug,),
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
                self.assertIn("nothing is created under it again", str(caught.exception))
                self.assertIn("never re-run", str(caught.exception))
                self.assertIn(str(self.wild_v2.resolve()), str(caught.exception))

    def test_the_plain_sealed_run_directory_is_refused_too(self):
        """The root is closed outright, so not even the plain run directory is open.

        This is the change that closes the root: the one destination an un-run
        sealed root accepted is now refused like everything else, and the
        refusal names the set as a sealed record. A permit does not open it --
        the permit machinery is written for a root whose run has not been made.
        """
        destination = self.wild_v2 / self.slug
        for permit in (None, destination):
            with self.subTest(permit=permit is not None):
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    run_benchmark.assert_not_under_the_held_out_root(
                        destination, self.runs, permit=permit
                    )
                self.assertIn("nothing is created under it again", str(caught.exception))

    def test_a_direct_invocation_of_the_runner_issues_no_permit(self):
        """``python3 -m eval.run_benchmark --runs-dir <root>/wild-v2`` is refused.

        The permit is issued by ``eval.development_sets.run_set`` and by nothing
        else, so the runner's own command line -- which is not how the plain
        sealed run is made -- reaches its destination with no permit at all and
        is refused, with and without ``--force``.

        The repository's own runs root is replaced by a scratch one for the
        duration, so what is shown is ``<runs root>/wild-v2`` exactly as
        ``runs/wild-v2`` is, without the test ever naming the real path.
        ``LLMClient`` is patched to raise, so a guard that let this run start
        fails here rather than making a paid call, and the scratch root is
        asserted to have gained nothing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            original_root = run_benchmark.RUNS_DIR
            original, refuse = _refuse_to_build_a_client()
            run_benchmark.RUNS_DIR = runs
            run_benchmark.llm.LLMClient = refuse
            try:
                for extra in ([], ["--force"]):
                    with self.subTest(arguments=extra):
                        stderr = io.StringIO()
                        with contextlib.redirect_stdout(
                            io.StringIO()
                        ), contextlib.redirect_stderr(stderr):
                            code = run_benchmark.main(
                                ["--model", MODEL, "--runs-dir", str(runs / "wild-v2")]
                                + extra
                            )
                        self.assertEqual(
                            1,
                            code,
                            "a direct invocation of the runner was accepted for "
                            "wild-v2 with {0}".format(extra or "no switch"),
                        )
                        self.assertIn(
                            "nothing is created under it again", stderr.getvalue()
                        )
                        self.assertIn(
                            str((runs / "wild-v2").resolve()), stderr.getvalue()
                        )
                        self.assertFalse(
                            (runs / "wild-v2").exists(),
                            "a refused direct invocation created the sealed root",
                        )
            finally:
                run_benchmark.llm.LLMClient = original
                run_benchmark.RUNS_DIR = original_root

    def test_another_set_given_that_runs_root_is_refused(self):
        """The permit names a set, so every other set is refused on that path.

        ``run_set`` puts a set's runs under ``<runs root>/<subdir>``, so pointing
        a set at ``<runs root>/wild-v2`` aims it at the sealed set's own root.
        The repository's own runs root is replaced by a scratch one for the
        duration, so what is shown is ``--runs-dir runs/wild-v2`` exactly as the
        command line spells it. It is the second root that refuses the corpus and
        the second development set -- neither destination is one component below
        the root the caller named -- which is why they are in the list.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            sealed_root = runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR
            original_root = run_benchmark.RUNS_DIR
            run_benchmark.RUNS_DIR = runs
            try:
                for development_set in (
                    sets.CORPUS,
                    sets.SECOND_SET,
                    sets.SEALED_SET,
                ):
                    with self.subTest(development_set=development_set.name):
                        original, refuse = _refuse_to_build_a_client()
                        run_benchmark.llm.LLMClient = refuse
                        try:
                            with self.assertRaises(
                                run_benchmark.BenchmarkError
                            ) as caught:
                                sets.run_set(
                                    development_set,
                                    MODEL,
                                    runs_dir=sealed_root,
                                    cases=(development_set.cases[0],),
                                    progress=lambda text: None,
                                )
                        finally:
                            run_benchmark.llm.LLMClient = original
                        self.assertIn(
                            str(sealed_root.resolve()), str(caught.exception)
                        )
            finally:
                run_benchmark.RUNS_DIR = original_root
            self.assertFalse(
                sealed_root.exists(),
                "a refused set created the un-run sealed root",
            )

    def test_a_runs_root_that_is_itself_a_sealed_root_opens_nothing(self):
        """``--set wild-v2 --runs-dir <root>/wild-v2`` must be refused too.

        The permit opens the plain run directory of a *runs root*. A runs root
        that is itself a sealed root would have the permit open
        ``<root>/wild-v2/wild-v2/<slug>/`` -- a second directory under the
        sealed root, which is the one thing the permit exists to prevent -- so
        the permit is not honoured there and the run is refused before it
        writes. ``<root>/wild`` is the same shape one root over.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            for subdir in run_benchmark.SEALED_RUNS_SUBDIRS:
                with self.subTest(subdir=subdir):
                    original, refuse = _refuse_to_build_a_client()
                    run_benchmark.llm.LLMClient = refuse
                    try:
                        with self.assertRaises(run_benchmark.BenchmarkError):
                            sets.run_set(
                                WILD_V2,
                                MODEL,
                                runs_dir=runs / subdir,
                                cases=(SENTINEL_CASE,),
                                progress=lambda text: None,
                            )
                    finally:
                        run_benchmark.llm.LLMClient = original
            self.assertFalse(
                runs.exists(), "a refused run created a sealed root"
            )

    def test_a_scratch_root_does_not_excuse_the_repositorys_own(self):
        """Both roots are walked, so ``--runs-dir`` cannot move the guard aside.

        ``--runs-dir`` and the repository's own ``runs/`` are separate arguments,
        so a caller who points the first at a scratch root has not thereby made
        the repository's sealed roots safe to write into. Both are walked, as
        :func:`baselines.assert_not_a_run_directory` walks them, and the check is
        on paths alone: nothing is created and nothing is read.
        """
        with tempfile.TemporaryDirectory() as tmp:
            elsewhere = Path(tmp) / "elsewhere"
            for subdir in run_benchmark.SEALED_RUNS_SUBDIRS:
                destination = run_benchmark.RUNS_DIR / subdir / self.slug
                with self.subTest(subdir=subdir):
                    with self.assertRaises(
                        run_benchmark.BenchmarkError
                    ) as caught:
                        run_benchmark.assert_not_under_the_held_out_root(
                            destination, elsewhere
                        )
                    self.assertIn(
                        str((run_benchmark.RUNS_DIR / subdir).resolve()),
                        str(caught.exception),
                    )

    def test_the_plain_sealed_run_of_this_set_is_now_refused(self):
        """The set that owns the root can no longer run into it.

        The permit ``run_set`` issues for ``wild-v2`` used to open the plain run
        directory; now that the set's single run has been made it opens nothing,
        and the run is refused before a client is built. A factory that raises is
        what turns a guard that stopped refusing into this test's failure rather
        than into a paid call, and the scratch runs root is asserted untouched.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            calls = []

            def refuse_to_build_a_client(_sink):
                calls.append(_sink)
                raise AssertionError("a client was built, so the sealed root was open")

            with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                sets.run_set(
                    WILD_V2,
                    MODEL,
                    runs_dir=runs,
                    cases=(SENTINEL_CASE,),
                    client_factory=refuse_to_build_a_client,
                    git_runner=dev_rig.git_runner(),
                    progress=lambda text: None,
                    judge_votes=1,
                )
            self.assertIn("nothing is created under it again", str(caught.exception))
            self.assertEqual([], calls, "the refused run built a client")
            self.assertFalse(runs.exists(), "a refused run created the sealed root")

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
        """``--set wild-v2`` plus any of the four switches, refused, with a message.

        The message asserted is the command-line layer's own. For the three path
        switches that layer asks the guard about the *set's runs directory*, so
        the destination its message names is the sealed root itself, and the
        expected text below is that shape. A refusal raised later, by the runner,
        names a deeper destination -- or the runner's own switch conflict --
        which is what makes this assertion fail if the command-line layer is
        removed. ``--policy-version`` is refused one block earlier, by the
        registration, and its message is that block's.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs, run_dir, sentinel, before = _scratch_runs_with_the_wild_v2_result(tmp)
            sealed_root = (runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR).resolve()
            original, refuse = _refuse_to_build_a_client()
            run_benchmark.llm.LLMClient = refuse
            try:
                for arguments, expected in (
                    (
                        ["--ablate", "clause-notes"],
                        "{0} lies under {0}".format(sealed_root),
                    ),
                    (["--precedents"], "{0} lies under {0}".format(sealed_root)),
                    (
                        ["--policy-version", "2"],
                        "wild-v2 fixes policy version 2 in its registration",
                    ),
                    (
                        ["--amount-rule", "signed"],
                        "{0} lies under {0}".format(sealed_root),
                    ),
                ):
                    with self.subTest(arguments=arguments):
                        code, _out, err = _run_cli_over(
                            runs, ["--set", "wild-v2"] + arguments
                        )
                        self.assertEqual(
                            1, code, "{0} was accepted for --set wild-v2".format(arguments)
                        )
                        self.assertIn("FATAL: ", err)
                        self.assertIn(expected, err)
                        self.assertEqual(
                            before,
                            sentinel.read_bytes(),
                            "{0} rewrote the sealed result".format(arguments),
                        )
                        self.assertEqual({sentinel.name: before}, _state(run_dir))
            finally:
                run_benchmark.llm.LLMClient = original


# --------------------------------------------------------------------------
# The root is closed, and the owner's own command is refused with it
# --------------------------------------------------------------------------
class WildV2RootIsClosedTests(unittest.TestCase):
    """The owner's exact command is refused, because the run has been made.

    The plain sealed run was the one destination an un-run sealed root accepted,
    and it is closed with everything else. This is that closure shown on the
    command the owner actually types: the opt-in set, the two switches the freeze
    fixes, a scratch runs root in place of the repository's own, and
    ``LLMClient`` patched to raise -- so a guard that let the run start fails here
    rather than making a paid call.
    """

    ARGUMENTS = ["--set", "wild-v2", "--concurrency", "2", "--timeout", "900"]

    def test_the_owners_exact_command_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.dict(
                os.environ, {sets.SEALED_RUN_ENV_VAR: "wild-v2"}
            ), mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ), mock.patch.object(
                run_benchmark.llm, "load_api_key", return_value="a-key"
            ):
                code, out, err = _run_cli(self.ARGUMENTS)

            self.assertEqual(
                1, code, "the owner's command was accepted for a closed root"
            )
            self.assertIn("FATAL: ", err)
            self.assertIn("nothing is created under it again", err)
            self.assertIn(
                str((runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR).resolve()), err
            )
            self.assertEqual("", out, "the refused command printed something")
            self.assertFalse(
                runs.exists(), "the refused command created the runs root"
            )

    def test_a_scratch_runs_root_does_not_reopen_it(self):
        """The closure is on the path, not on the repository's own root.

        ``--runs-dir`` is refused for this set, so the scratch root is put in
        place by moving both modules' ``RUNS_DIR``. The destination is then
        ``<scratch>/wild-v2/<slug>/`` and it is refused exactly as the
        repository's own would be, which is what makes the closure a property of
        the directory's shape rather than of one absolute path.

        The guard is asked with ``permit=destination`` -- the one thing that
        could open a sealed root. A root whose single run has **not** been made
        accepts exactly that destination, so passing the permit is what makes
        this test about the closure rather than about the call: with the set
        moved back into ``UNRUN_SEALED_RUNS_SUBDIRS`` the permit would be
        honoured, nothing would be raised, and this test would fail.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            slug = run_benchmark.model_slug(MODEL)
            destination = runs / run_benchmark.WILD_V2_SET_RUNS_SUBDIR / slug
            with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                run_benchmark.assert_not_under_the_held_out_root(
                    destination, runs, permit=destination
                )
            self.assertIn("nothing is created under it again", str(caught.exception))


# --------------------------------------------------------------------------
# The run arguments, frozen in the registration
# --------------------------------------------------------------------------
def _frozen_arguments(**overrides):
    """The arguments the owner's command gives, with one of them replaced.

    The values are the ones the freeze note fixes; the three the note fixes as
    "the default" are given here as the default itself, because that is what
    the command line gives when the flag is absent.
    """
    arguments = dict(
        model="deepseek/deepseek-flash",
        prompts_dir=run_benchmark.PROMPTS_DIR,
        judge_votes=4,
        verify_drafts=False,
        timeout_seconds=900.0,
        concurrency=2,
        case_deadline_seconds=run_benchmark.pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
        token_budget=None,
    )
    arguments.update(overrides)
    return arguments


# One row per frozen setting: the switch, the command line that differs from the
# freeze in that one setting, the same difference as a keyword argument, and the
# two values the refusal must name. A table rather than eight tests, so "test
# each one" is a loop over all eight and not a sentence claiming eight.
# The owner's command line, argument by argument: the switch, the setting's name
# in the registration, and the value the freeze note fixes, as the command line
# spells it. ``None`` is a setting the owner's command line does not carry at
# all -- the verifier is a flag whose presence is the value, and the three the
# note fixes as "the default" are the defaults themselves.
FROZEN_COMMAND_LINE_ARGUMENTS = (
    ("--model", "model", "deepseek/deepseek-flash"),
    ("--judge-votes", "judge_votes", "4"),
    ("--concurrency", "concurrency", "2"),
    ("--timeout", "timeout", "900"),
    ("--verify-drafts", "verify_drafts", None),
    ("--prompts-dir", "prompts_dir", None),
    ("--case-deadline", "case_deadline", None),
    ("--token-budget", "token_budget", None),
)


def _owners_command_line(**replaced):
    """The owner's command line, with the named settings given other values.

    Every argument the registration fixes is on the line, at its frozen value
    unless ``replaced`` names it, so a row built from it differs in the one
    argument it names and in nothing else. ``verify_drafts`` is a flag: ``True``
    puts it on the line and ``False`` leaves it off. A setting the owner's
    command line does not carry -- the three the note fixes as "the default" --
    is added by ``replaced``.
    """
    line = ["--set", "wild-v2"]
    for switch, setting, frozen in FROZEN_COMMAND_LINE_ARGUMENTS:
        asked = replaced.pop(setting, frozen)
        if asked is False or asked is None:
            continue
        line.append(switch)
        if asked is not True:
            line.append(str(asked))
    assert not replaced, "no switch for {0}".format(sorted(replaced))
    return line


FROZEN_ARGUMENT_DIFFERENCES = (
    (
        "--model",
        _owners_command_line(model="deepseek/deepseek-chat"),
        {"model": "deepseek/deepseek-chat"},
        "deepseek/deepseek-chat",
        "deepseek/deepseek-flash",
    ),
    (
        "--judge-votes",
        _owners_command_line(judge_votes=1),
        {"judge_votes": 1},
        "1",
        "4",
    ),
    (
        "--verify-drafts",
        _owners_command_line(verify_drafts=True),
        {"verify_drafts": True},
        "on",
        "off",
    ),
    (
        "--timeout",
        _owners_command_line(timeout=300),
        {"timeout_seconds": 300.0},
        "300.0",
        "900.0",
    ),
    (
        "--concurrency",
        _owners_command_line(concurrency=3),
        {"concurrency": 3},
        "3",
        "2",
    ),
    (
        "--prompts-dir",
        _owners_command_line(prompts_dir=Path("/tmp/not-the-default")),
        {"prompts_dir": Path("/tmp/not-the-default")},
        "/tmp/not-the-default",
        "the default",
    ),
    (
        "--case-deadline",
        _owners_command_line(case_deadline=1200),
        {"case_deadline_seconds": 1200.0},
        "1200.0",
        "the default",
    ),
    (
        "--token-budget",
        _owners_command_line(token_budget=100000),
        {"token_budget": 100000},
        "100000",
        "the default",
    ),
)


FREEZE_NOTE = PROJECT_ROOT / "docs/notes/2026-10-03-the-second-freeze.md"


def _the_freeze_notes_model():
    """The model the freeze note's configuration table states, from its text.

    The table is a two-column markdown table whose rows are ``| setting | value
    |``; the model's row is the one whose first cell is exactly ``model``, and its
    value is written in backticks. Read from the note's text rather than imported
    from the module that decides it, because the note is the statement the owner
    runs against and the point of the test below is to compare the two records.
    """
    for line in FREEZE_NOTE.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] == "model":
            return cells[1].strip().strip("`")
    return None


class WildV2RunArgumentsTests(unittest.TestCase):
    """``--set wild-v2`` runs at the arguments its registration fixes, or not at all.

    The freeze note fixes the model, the judge vote count, the verifier, the
    prompts directory, the case deadline, the token budget, the timeout and the
    concurrency. Each is fixed as a *value* or as "the default", and an
    invocation that differs in one of them would produce a different measurement
    under the same name, so it is refused with the argument and the registered
    value named.

    No model is called anywhere here: every differing invocation is refused
    before the run, and the one invocation that is accepted is asserted through
    the refusal function rather than by running it.
    """

    def test_the_registered_model_is_the_one_the_freeze_note_states(self):
        """The registration and the note are two records of one decision.

        The run is made from a commit whose trees equal the note's tag, and the
        note's configuration table is the statement the owner runs against: a
        registration naming a different model would brief every case with one
        model while the note said another, and nothing would say so. The note is
        read, not imported, so the two records are actually compared.
        """
        stated = _the_freeze_notes_model()
        self.assertIsNotNone(
            stated, "the freeze note's configuration table states no model"
        )
        self.assertEqual(
            stated,
            WILD_V2.run_arguments.model,
            "the model wild-v2 registers is not the model the freeze note states",
        )

    def test_the_registration_records_the_freezes_eight_settings(self):
        frozen = WILD_V2.run_arguments
        self.assertIsNotNone(frozen, "wild-v2 fixes no run arguments")
        self.assertEqual("deepseek/deepseek-flash", frozen.model)
        self.assertEqual(4, frozen.judge_votes)
        self.assertFalse(frozen.verify_drafts)
        self.assertEqual(900.0, frozen.timeout_seconds)
        self.assertEqual(2, frozen.concurrency)
        # "The default" is recorded as the default rather than as today's
        # number, so the registration cannot start refusing the default.
        self.assertIsNone(frozen.prompts_dir)
        self.assertIsNone(frozen.case_deadline_seconds)
        self.assertIsNone(frozen.token_budget)
        for development_set in (
            sets.DEVELOPMENT_SETS + sets.SEALED_SETS + sets.RERUN_SETS
        ):
            if development_set is WILD_V2:
                continue
            with self.subTest(development_set=development_set.name):
                self.assertIsNone(
                    development_set.run_arguments,
                    "a set that is not wild-v2 fixes run arguments",
                )

    def test_the_judge_vote_default_agrees_with_the_freezes_four(self):
        """The note fixes 4 and the command line's default is also 4.

        ``--judge-votes`` is a *value* in the registration and not "the default",
        so a command that omits the flag is accepted only while the default
        agrees with the note. That agreement is asserted here rather than left
        to be discovered on the day the default moves.
        """
        self.assertEqual(4, WILD_V2.run_arguments.judge_votes)
        self.assertEqual(
            4,
            run_benchmark.pipeline.DEFAULT_JUDGE_VOTES,
            "the judge vote default no longer agrees with the freeze note's 4, so "
            "the owner's command would now be refused",
        )

    def test_the_invocation_the_owner_will_run_differs_in_nothing(self):
        self.assertEqual(
            [],
            sets.run_argument_differences(WILD_V2, **_frozen_arguments()),
            "the frozen invocation is refused",
        )

    def test_each_differing_argument_is_named_with_its_registered_value(self):
        for switch, _arguments, overrides, asked_text, registered_text in (
            FROZEN_ARGUMENT_DIFFERENCES
        ):
            with self.subTest(switch=switch):
                differences = sets.run_argument_differences(
                    WILD_V2, **_frozen_arguments(**overrides)
                )
                self.assertEqual(
                    1,
                    len(differences),
                    "{0} did not give exactly one difference: {1}".format(
                        switch, differences
                    ),
                )
                self.assertIn(switch, differences[0])
                self.assertIn(asked_text, differences[0])
                self.assertIn(
                    "wild-v2 is registered at {0}".format(registered_text),
                    differences[0],
                )

    def test_the_command_line_refuses_each_differing_argument(self):
        """Each one on the command line, refused, naming the argument and the value.

        Each row gives every other argument its frozen value, so the invocation
        differs from the registration in the one argument the row names. A row
        that left the others to the parser's defaults would differ wherever a
        default happened to disagree with the note, and the refusal it asserts
        would then be about a different argument than the one it is named for.

        Both modules' ``RUNS_DIR`` are moved to a scratch root, so the assertion
        that nothing was created is made on a directory this test owns rather
        than on the repository's own ``runs/wild-v2/``, which the sealed run is
        going to fill. ``--runs-dir`` is not passed: it is refused for this set.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            for switch, arguments, _overrides, asked_text, registered_text in (
                FROZEN_ARGUMENT_DIFFERENCES
            ):
                with self.subTest(switch=switch):
                    code, _out, err = _run_cli_over(runs, arguments)
                    self.assertEqual(
                        1,
                        code,
                        "{0} was accepted for --set wild-v2".format(switch),
                    )
                    self.assertIn(switch, err)
                    self.assertIn(asked_text, err)
                    self.assertIn(
                        "wild-v2 is registered at {0}".format(registered_text), err
                    )
            self.assertFalse(
                runs.exists(), "a refused invocation created a run directory"
            )

    def test_the_owners_command_reaches_the_runner_with_the_frozen_arguments(self):
        """The whole command line, end to end, against a stub that raises.

        The eight arguments the registration fixes are read off the call ``main``
        makes rather than off a summary: the stub raises a sentinel before
        anything is run, so no client is built, nothing is written, and what the
        test reads is the invocation itself. The opt-in is set, because without
        it the command is refused, and both modules' ``RUNS_DIR`` are moved to a
        scratch root, because the run root is fixed at the repository's own
        ``runs/`` and the sealed run is going to fill it.
        """
        sentinel = "the sealed run's arguments"
        recorded = {}

        def stub(development_set, model, **keywords):
            recorded["set"] = development_set
            recorded["model"] = model
            recorded["keywords"] = keywords
            raise AssertionError(sentinel)

        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.dict(
                os.environ, {sets.SEALED_RUN_ENV_VAR: "wild-v2"}
            ), mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ), mock.patch.object(
                run_benchmark.llm, "load_api_key", return_value="a-key"
            ), mock.patch.object(
                sets, "run_set", stub
            ):
                with self.assertRaises(AssertionError) as caught:
                    _run_cli(_owners_command_line())

        self.assertEqual(sentinel, str(caught.exception), "the runner was not reached")
        self.assertIs(WILD_V2, recorded["set"])
        keywords = recorded["keywords"]
        frozen = WILD_V2.run_arguments
        # The eight the registration fixes, each against the registration.
        self.assertEqual(frozen.model, recorded["model"])
        self.assertEqual(frozen.judge_votes, keywords["judge_votes"])
        self.assertEqual(frozen.verify_drafts, keywords["verify_drafts"])
        self.assertEqual(frozen.timeout_seconds, keywords["timeout_seconds"])
        self.assertEqual(frozen.concurrency, keywords["concurrency"])
        self.assertEqual(run_benchmark.PROMPTS_DIR, keywords["prompts_dir"])
        self.assertEqual(
            run_benchmark.pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
            keywords["case_deadline_seconds"],
        )
        self.assertIsNone(keywords["token_budget"])
        # And the run is the set's whole case list, at the version the
        # registration fixes, in the run root the command line was given, with
        # nothing switched on beside it.
        self.assertEqual(list(WILD_V2.cases), keywords["cases"])
        # The command line's own version, which is ``run_set``'s to replace with
        # the registration's 2 before the runner sees it: the version is part of
        # what the set is, and the layer that applies it is the one that knows
        # the registration. ``test_a_run_of_it_briefs_at_version_2...`` is where
        # that half is asserted.
        self.assertEqual(
            run_benchmark.DEFAULT_POLICY_VERSION, keywords["policy_version"]
        )
        self.assertEqual(runs, keywords["runs_dir"])
        self.assertIs(False, keywords["force"])
        self.assertIsNone(keywords["replay_dir"])
        self.assertIsNone(keywords["ablation"])
        self.assertIsNone(keywords["precedents"])
        self.assertEqual(
            run_benchmark.pipeline.DEFAULT_AMOUNT_RULE, keywords["amount_rule"]
        )

    def test_the_read_only_report_is_not_a_run_and_is_not_refused(self):
        """``--report`` judges nothing, so the frozen arguments are not its business.

        The sealed figures are printed by a read-only command that makes no
        model call and writes nothing, and that command takes no run arguments:
        a check that refused it would make the figures unreadable.
        """
        code, out, err = _run_cli(["--set", "wild-v2", "--report"])
        self.assertEqual(0, code, err)
        self.assertNotIn("is registered at", err)


# --------------------------------------------------------------------------
# The structure
# --------------------------------------------------------------------------
class WildV2StructureTests(unittest.TestCase):
    """20 cases load and brief at version 2; the key holds 20 complete records.

    Counts, keys and file names only. No expected ruling, amount, compensation or
    referral is read, compared or printed anywhere in this class -- the key is
    asserted to be *well formed*, not to say anything in particular, and its four
    graded fields are asked for as keys of the raw JSON rather than through a
    reader that would answer ``None`` for a field that is not there.
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

    def test_all_20_briefs_build_at_version_2_and_12_of_them_differ_from_version_1(self):
        """The count the import note records: 12 differ at the two versions, 8 do not.

        The twelve are the twelve route-deviation cases and the eight are the
        no-show ones, because the amendment ``0001-pol-rd-13`` adds a clause to
        ``policy/route_deviation.json`` and to nothing else. Only the count is
        asserted here; which cases they are is a number, never a brief.
        """
        differing = []
        for case_no in WILD_V2.cases:
            with self.subTest(case_no=case_no):
                case = WILD_V2.load_case(case_no)
                built = brief.build_brief_for_case(
                    case, policy_version=WILD_V2.policy_version
                )
                self.assertTrue(
                    isinstance(built, dict),
                    "case {0} did not build a brief object".format(case_no),
                )
                self.assertTrue(built, "case {0} built an empty brief".format(case_no))
                at_version_one, _ = brief.brief_digest(
                    brief.build_brief_for_case(case, policy_version=1)
                )
                at_this_version, _ = brief.brief_digest(built)
                if at_version_one != at_this_version:
                    differing.append(case_no)
        self.assertEqual(
            12,
            len(differing),
            "the number of briefs the amendment moves is not the import note's 12",
        )
        self.assertEqual(8, len(WILD_V2.cases) - len(differing))

    def test_the_index_names_20_cases_and_the_key_agrees_with_it(self):
        entries = loader.load_external_index(WILD_V2.case_root)
        self.assertEqual(20, len(entries))
        self.assertEqual([case_no for case_no in WILD_V2.cases], [e["case_no"] for e in entries])
        self.assertEqual(set(WILD_V2.cases), set(WILD_V2.key()))

    def test_every_record_of_the_key_carries_all_four_graded_fields(self):
        """The four fields, read off the raw JSON rather than through the loader.

        ``grade.load_answer_key`` reads a field with ``.get()``, so a record that
        had lost one would come back with a ``None`` rather than a missing key and
        the property would pass for the wrong reason. The records are read here as
        JSON and each ``ground_truth`` is asked for its keys directly -- the
        ``expected_`` names, which is what the key's own record holds; the four
        graded names are the grader's view of them, and the tie between the two is
        asserted rather than assumed. A failure names the case and the field,
        never a value.
        """
        expected_fields = tuple("expected_" + name for name in grade.GRADED_FIELDS)
        self.assertEqual(
            (
                "expected_ruling",
                "expected_amount_sgd",
                "expected_driver_compensation_sgd",
                "expected_referrals",
            ),
            expected_fields,
        )
        records = json.loads(WILD_V2.key_path.read_text(encoding="utf-8"))
        self.assertEqual(20, len(records), "the second sealed key is not 20 records")
        self.assertEqual(ALL_WILD_V2_CASES, tuple(record["case_no"] for record in records))
        self.assertEqual(
            ("ruling", "amount_sgd", "driver_compensation_sgd", "referrals"),
            tuple(grade.GRADED_FIELDS),
        )
        for record in records:
            case_no = record["case_no"]
            with self.subTest(case_no=case_no):
                truth = record.get("ground_truth")
                self.assertTrue(
                    isinstance(truth, dict),
                    "the record for case {0} carries no ground_truth object".format(case_no),
                )
                for field in expected_fields:
                    self.assertTrue(
                        field in truth,
                        "case {0} is missing {1}".format(case_no, field),
                    )
        # And the loader the run grades with reads the same 20 records, so the
        # raw reading above is of the file that grader actually opens.
        key = grade.load_answer_key(WILD_V2.key_path)
        self.assertEqual(20, len(key))
        self.assertEqual(set(WILD_V2.cases), set(key))

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
        """Every imported file hashes to the digest the import note's table states.

        The table is the note's own record of all 45 files as committed, so
        comparing the two is what makes "imported as shipped" a measurement
        rather than a list of file names. A failure names the file and nothing
        else: a digest of a case file or of the key is a property of sealed
        bytes, and a test's output is not where those belong.
        """
        stated = _digests_the_import_note_states()
        self.assertEqual(45, len(stated), "the import note's table is not 45 files")
        for relative, digest in sorted(stated.items()):
            path = PROJECT_ROOT / relative
            with self.subTest(path=relative):
                self.assertTrue(path.is_file(), "{0} was not imported".format(relative))
                self.assertTrue(
                    run_benchmark.file_sha256(path) == digest,
                    "{0} does not hash to the digest the import note states".format(relative),
                )


# --------------------------------------------------------------------------
# The sealed protocol: what a second invocation retries, and what it does not
# --------------------------------------------------------------------------
# Six cases, one behaviour each. The numbers are the set's own; the behaviour is
# named, never a ruling, and nothing here reads a value out of the key: the
# transport is handed the key's produced mapping so a case it is meant to let
# through produces a real ruling, and the assertions are on call counts and on
# the protocol's own printed lines.
CASE_JUDGE_SHAPE = 701
CASE_ADVOCATE_SHAPE = 702
CASE_GATEWAY = 703
CASE_TRANSPORT = 704
CASE_KILLED = 705
CASE_SUCCEEDS = 706

KILLED_INVOCATION = "an-invocation-that-was-killed"


class ProtocolTransport:
    """Answers by case and role, so each case can be given one failure.

    The behaviour of a case is one of ``ok`` (a real ruling for the judge, a
    claim array for an advocate, HTTP 200), ``judge_shape`` (the judge answers an
    object the contract rejects), ``advocate_shape`` (an advocate does),
    ``gateway`` (every call answers 502, which the client does not retry at
    ``max_attempts`` 1) and ``transport`` (the call raises, so nothing was
    produced).
    """

    def __init__(self, produced, behaviour) -> None:
        self.produced = produced
        self.behaviour = dict(behaviour)
        self.requests = []

    def __call__(self, url, headers, body, timeout):
        request = json.loads(body.decode("utf-8"))
        case_no, role = dev_rig.role_of(request)
        self.requests.append((case_no, role))
        mode = self.behaviour.get(case_no, "ok")

        if mode == "transport":
            raise llm.TransportError("no answer was produced")
        if mode == "not_provisioned":
            # A model that is not provisioned fails every call the same way and
            # nothing reaches a model. The runner records it as a case failure
            # with no agent call and then lets it out of the invocation, which is
            # what makes it a *terminal-only* attempt.
            raise llm.ModelNotProvisionedError("the model is not provisioned")
        if mode == "gateway":
            return llm.HttpResult(status=502, body=b'{"error": "bad gateway"}')

        if mode == "judge_shape" and role == transcript.ROLE_JUDGE:
            content = "{}"
        elif mode == "advocate_shape" and role != transcript.ROLE_JUDGE:
            content = "{}"
        elif role == transcript.ROLE_JUDGE:
            ruling = dict(self.produced[case_no]["ruling"])
            content = money.dumps_canonical({"ruling": ruling, "discarded_claims": []})
        else:
            content = dev_rig.CLAIM_ARRAY

        payload = {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": dev_rig.PROMPT_TOKENS,
                "completion_tokens": dev_rig.COMPLETION_TOKENS,
                "completion_tokens_details": {"reasoning_tokens": 8},
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
        return llm.HttpResult(status=200, body=json.dumps(payload).encode("utf-8"))

    def calls(self) -> int:
        return len(self.requests)


# The fixed placeholder ruling the protocol tests feed the judge.
#
# These tests are about *which invocations call an agent*, not about what an
# agent answered, so the ruling never needs to be the case's own. It is a
# well-formed POL-GEN-03 draft -- ``NO_ACTION`` requires neither amount, so both
# are null, and it names no clause -- which is all ``check_judge_draft`` asks of
# a draft before it may vote. Feeding the real key here would make the suite read
# the sealed key for tests that are not about the key at all.
PLACEHOLDER_RULING = {
    "ruling": "NO_ACTION",
    "amount_sgd": None,
    "driver_compensation_sgd": None,
    "referrals": [],
    "confidence": 0.5,
    "explanation": "A fixed placeholder ruling for the sealed-protocol tests.",
}

# Every case the protocol tests use, so the transport can answer each of them
# without being handed a key.
PROTOCOL_CASES = (
    CASE_JUDGE_SHAPE,
    CASE_ADVOCATE_SHAPE,
    CASE_GATEWAY,
    CASE_TRANSPORT,
    CASE_KILLED,
    CASE_SUCCEEDS,
)

# The set the protocol tests run: the second sealed set, with the two fields the
# root guard reads changed and nothing else.
#
# The sealed protocol is a property of a *sealed set's* re-invocation, and it is
# exercised by running one. The set's own root is closed now that its single run
# has been made -- ``runs/wild-v2/<slug>/`` is refused wherever the runs root is,
# because the guard compares path components and not one absolute path -- so the
# set cannot be run to exercise the protocol. This is that set with a different
# ``name`` and a different ``runs_subdir``, which are the only two things the
# guard and the destination read: its cases, its case loader, its key and its
# registration-fixed policy version are the sealed set's own, and every
# invocation below goes through the real guard over a scratch runs root. The
# protocol is therefore still tested on a set shaped exactly like the sealed one,
# and the guard is not stood down to test it.
PROTOCOL_SET = dataclasses.replace(
    WILD_V2, name="wild-shaped", runs_subdir="wild-shaped"
)


def _protocol_transport(behaviour):
    produced = {
        case_no: {"case_no": case_no, "ruling": dict(PLACEHOLDER_RULING)}
        for case_no in PROTOCOL_CASES
    }
    return ProtocolTransport(produced, behaviour)


def _invoke(runs, cases, transport):
    """One invocation of the same call, with both streams captured.

    The runner's own progress is silenced, so what is captured is the sealed
    protocol's own lines and nothing else. The set is :data:`PROTOCOL_SET`, the
    sealed set's own cases and loader under a subdirectory that is not a sealed
    root -- see there for why the sealed set itself cannot be run.
    """
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        summary = sets.run_set(
            PROTOCOL_SET,
            MODEL,
            runs_dir=runs,
            cases=cases,
            client_factory=dev_rig.client_factory(transport),
            git_runner=dev_rig.git_runner(),
            progress=lambda text: None,
            judge_votes=1,
        )
    return summary, stdout.getvalue()


def _killed_attempt(runs, case_no):
    """An attempt that ended with no terminal event: agent calls, and nothing after.

    A process killed mid-case leaves ``agent_call`` events and neither a
    ``ruling`` nor a ``case_failed``. It is written here with a distinct
    invocation id, so it is an attempt of its own and not this invocation's.
    """
    run_dir = _protocol_run_dir(runs)
    run_dir.mkdir(parents=True, exist_ok=True)
    log = events.EventLog(
        run_dir / events.EVENTS_FILE, invocation_id=KILLED_INVOCATION
    )
    log.record(events.EVENT_CASE_START, case_no=case_no, position=1, total=1)
    log.record(
        events.EVENT_AGENT_CALL,
        case_no=case_no,
        role=transcript.ROLE_RIDER_ADVOCATE,
        status=200,
    )


class SealedProtocolTests(unittest.TestCase):
    """What a second and third invocation of the same sealed call run again.

    The rule: an infrastructure failure is retried once, a failure in which the
    model answered is not, no case gets a third attempt, and an attempt that
    ended with no terminal event does not count. Each is shown by calling the
    same invocation up to three times over a scratch runs root and counting what
    the transport was asked for.
    """

    def test_a_judge_shape_case_with_all_200s_is_not_called_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = _protocol_transport({CASE_JUDGE_SHAPE: "judge_shape"})

            _invoke(runs, [CASE_JUDGE_SHAPE], transport)
            first = transport.calls()
            self.assertGreater(first, 0, "the first invocation made no call")

            _, out = _invoke(runs, [CASE_JUDGE_SHAPE], transport)
            self.assertEqual(first, transport.calls(), "a judge SHAPE case was re-sampled")
            self.assertIn(
                "not retried under the sealed protocol: {0} (SHAPE, every call "
                "answered 200)".format(CASE_JUDGE_SHAPE),
                out,
            )

            _invoke(runs, [CASE_JUDGE_SHAPE], transport)
            self.assertEqual(first, transport.calls(), "a judge SHAPE case was re-sampled")

    def test_an_advocate_shape_case_with_all_200s_is_not_called_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = _protocol_transport({CASE_ADVOCATE_SHAPE: "advocate_shape"})

            _invoke(runs, [CASE_ADVOCATE_SHAPE], transport)
            first = transport.calls()
            self.assertGreater(first, 0, "the first invocation made no call")

            _, out = _invoke(runs, [CASE_ADVOCATE_SHAPE], transport)
            self.assertEqual(first, transport.calls(), "an advocate SHAPE case was re-sampled")
            self.assertIn(
                "not retried under the sealed protocol: {0} (SHAPE, every call "
                "answered 200)".format(CASE_ADVOCATE_SHAPE),
                out,
            )

    def test_a_shape_case_with_an_exhausted_gateway_is_called_once_more(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = _protocol_transport({CASE_GATEWAY: "gateway"})

            _invoke(runs, [CASE_GATEWAY], transport)
            first = transport.calls()
            self.assertGreater(first, 0, "the first invocation made no call")

            # A 5xx that exhausted the client's retries is SHAPE, but a call
            # answered with something other than 200: the server did not answer,
            # so the case is retried once.
            _, out = _invoke(runs, [CASE_GATEWAY], transport)
            self.assertGreater(transport.calls(), first, "a server error was not retried")
            self.assertNotIn("not retried under the sealed protocol", out)
            second = transport.calls()

            # It failed again, so this is its second attempt and there is no
            # third.
            _, out = _invoke(runs, [CASE_GATEWAY], transport)
            self.assertEqual(second, transport.calls(), "a case got a third attempt")
            self.assertIn(
                "not retried under the sealed protocol: {0} (two attempts)".format(
                    CASE_GATEWAY
                ),
                out,
            )

    def test_a_transport_case_is_called_once_more_and_then_not_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = _protocol_transport({CASE_TRANSPORT: "transport"})

            _invoke(runs, [CASE_TRANSPORT], transport)
            first = transport.calls()
            self.assertGreater(first, 0, "the first invocation made no call")

            _invoke(runs, [CASE_TRANSPORT], transport)
            self.assertGreater(transport.calls(), first, "a transport failure was not retried")
            second = transport.calls()

            _, out = _invoke(runs, [CASE_TRANSPORT], transport)
            self.assertEqual(second, transport.calls(), "a case got a third attempt")
            self.assertIn(
                "not retried under the sealed protocol: {0} (two attempts)".format(
                    CASE_TRANSPORT
                ),
                out,
            )

    def test_an_attempt_with_no_terminal_event_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            _killed_attempt(runs, CASE_KILLED)
            transport = _protocol_transport({})

            _, out = _invoke(runs, [CASE_KILLED], transport)

            self.assertGreater(
                transport.calls(), 0, "a killed attempt stopped the case being run"
            )
            self.assertIn(
                "attempt with no terminal event, so it does not count under the "
                "sealed protocol: {0}".format(CASE_KILLED),
                out,
            )
            self.assertNotIn("not retried under the sealed protocol", out)

    def test_a_case_with_a_result_is_never_called_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = _protocol_transport({})

            _invoke(runs, [CASE_SUCCEEDS], transport)
            first = transport.calls()
            self.assertGreater(first, 0, "the first invocation made no call")

            _invoke(runs, [CASE_SUCCEEDS], transport)
            _invoke(runs, [CASE_SUCCEEDS], transport)
            self.assertEqual(first, transport.calls(), "a decided case was run again")

    def test_the_rule_is_stated_once_and_is_the_one_that_runs(self):
        """The predicate the code applies, exercised directly on its own facts."""
        attempt = sets._SealedAttempt(
            invocation="a",
            statuses=(200, 200),
            terminal=events.EVENT_CASE_FAILED,
            failure_kind=run_benchmark.FAILURE_SHAPE,
        )
        self.assertEqual(
            "SHAPE, every call answered 200", sets._sealed_verdict([attempt])
        )
        self.assertIsNone(
            sets._sealed_verdict(
                [
                    sets._SealedAttempt(
                        invocation="a",
                        statuses=(200, 502),
                        terminal=events.EVENT_CASE_FAILED,
                        failure_kind=run_benchmark.FAILURE_SHAPE,
                    )
                ]
            )
        )
        self.assertEqual(
            "two attempts",
            sets._sealed_verdict(
                [
                    attempt,
                    sets._SealedAttempt(
                        invocation="b",
                        statuses=(200,),
                        terminal=events.EVENT_CASE_FAILED,
                        failure_kind=run_benchmark.FAILURE_TRANSPORT,
                    ),
                ]
            ),
        )
        # A killed attempt does not count toward the two, so on its own it is no
        # reason to stop, and it does not overturn the verdict a counted attempt
        # already gave.
        killed = sets._SealedAttempt(
            invocation="c", statuses=(200,), terminal=None, failure_kind=None
        )
        self.assertIsNone(sets._sealed_verdict([killed]))
        self.assertEqual(
            "SHAPE, every call answered 200", sets._sealed_verdict([attempt, killed])
        )
        # A transport failure makes no agent_call; its case_failed is what makes
        # the invocation an attempt, and it is one to retry.
        self.assertIsNone(
            sets._sealed_verdict(
                [
                    sets._SealedAttempt(
                        invocation="d",
                        statuses=(),
                        terminal=events.EVENT_CASE_FAILED,
                        failure_kind=run_benchmark.FAILURE_TRANSPORT,
                    )
                ]
            )
        )
        self.assertEqual(
            "two attempts",
            sets._sealed_verdict(
                [
                    sets._SealedAttempt(
                        invocation="d",
                        statuses=(),
                        terminal=events.EVENT_CASE_FAILED,
                        failure_kind=run_benchmark.FAILURE_TRANSPORT,
                    ),
                    sets._SealedAttempt(
                        invocation="e",
                        statuses=(),
                        terminal=events.EVENT_CASE_FAILED,
                        failure_kind=run_benchmark.FAILURE_TRANSPORT,
                    ),
                ]
            ),
        )


# --------------------------------------------------------------------------
# The sealed protocol, second pass
# --------------------------------------------------------------------------
ADDENDUM_NOTE = PROJECT_ROOT / "docs/notes/2026-10-03-the-sealed-protocol-addendum.md"

# The four rules the addendum note states, each as a phrase the note carries.
# Pairing them here is what makes "the note states them, before the run"
# something a test checks rather than something a reader assumes. The phrases
# are lower-case and the note sets two of them at the head of a sentence, so the
# test compares case-insensitively rather than forbidding the capital.
ADDENDUM_RULES = (
    "a SHAPE failure with zero agent calls is retried once",
    "a `ruling` event with no case file is retried once",
    "an unparseable last line makes that attempt one that does not count",
    "the owner runs at most two invocations, plus as many `--check` runs as needed",
)


def _protocol_run_dir(runs):
    """The scratch run directory every protocol test writes into.

    ``PROTOCOL_SET``'s own run directory, so it is
    ``<runs root>/wild-shaped/<model-slug>/`` -- the shape the sealed set's would
    be, under a subdirectory that is not a sealed root. See :data:`PROTOCOL_SET`.
    """
    return PROTOCOL_SET.run_dir(MODEL, runs)


def _report_text(runs):
    """The invocation's own ``report.md``, as text."""
    return (_protocol_run_dir(runs) / run_benchmark.REPORT_FILE).read_text(
        encoding="utf-8"
    )


def _row_for(text, case_no):
    """The one case-table row of a report for a case, or the empty string."""
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == str(case_no):
            return line
    return ""


def _write_a_failure(runs, case_no, kind, detail=None):
    """One terminal-only attempt of a case, in an invocation of its own.

    No ``agent_call``, which is what makes it terminal-only: a call that raised
    before the transcript entry existed records its ``case_failed`` and nothing
    else.
    """
    run_dir = _protocol_run_dir(runs)
    run_dir.mkdir(parents=True, exist_ok=True)
    log = events.EventLog(
        run_dir / events.EVENTS_FILE,
        invocation_id="a-terminal-only-attempt-{0}".format(kind),
    )
    log.record(events.EVENT_CASE_START, case_no=case_no, position=1, total=1)
    log.record(
        events.EVENT_CASE_FAILED, case_no=case_no, failure_kind=kind, detail=detail
    )


class SealedProtocolSecondPassTests(unittest.TestCase):
    """The cases the protocol's first pass did not meet, and the lines it prints.

    The rule is unchanged. What is added here is what the first pass left out: a
    case the run already holds a result for, a failure that never reached a
    model, "last" when a killed attempt is in the way, a failure kind the code
    does not know, a log whose chain does not verify, and what an invocation says
    when there is nothing left for it to do.

    No model is called and no sealed set is run: every invocation goes through
    ``_invoke``, which passes a scripted transport, over a scratch runs root.
    """

    def test_a_case_with_a_result_is_kept_and_reported_as_cached(self):
        """A case the run already holds a result for is never dropped by the rule.

        Two attempts and a result is exactly the shape the rule calls "two
        attempts" and drops. The cache is what says otherwise, and the invocation
        has to keep the case, so that its own record says "cached" rather than
        saying nothing about it at all.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            flaky = _protocol_transport({CASE_TRANSPORT: "transport"})
            _invoke(runs, [CASE_TRANSPORT], flaky)
            self.assertGreater(flaky.calls(), 0, "the first invocation made no call")

            working = _protocol_transport({})
            _invoke(runs, [CASE_TRANSPORT], working)
            calls_after_the_result = working.calls()
            self.assertGreater(calls_after_the_result, 0, "the retry made no call")

            summary, out = _invoke(runs, [CASE_TRANSPORT], working)

            self.assertEqual(
                calls_after_the_result,
                working.calls(),
                "a case the run already has a result for was called again",
            )
            self.assertNotIn(
                "not retried under the sealed protocol",
                out,
                "a case with a result was dropped instead of kept",
            )
            self.assertIn(
                CASE_TRANSPORT,
                summary.cached_cases,
                "the invocation did not report the case as cached",
            )
            row = _row_for(_report_text(runs), CASE_TRANSPORT)
            self.assertNotEqual("", row, "the report has no row for the case")
            self.assertIn("current", row, "the report's cached cell is not current")

    def test_two_configuration_errors_are_not_two_attempts(self):
        """A failure that never reached a model does not use up an attempt."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            broken = _protocol_transport({CASE_SUCCEEDS: "not_provisioned"})

            for number in (1, 2):
                with self.subTest(invocation=number):
                    with self.assertRaises(llm.ModelNotProvisionedError):
                        _invoke(runs, [CASE_SUCCEEDS], broken)

            self.assertEqual(
                [],
                sets._sealed_attempts(_protocol_run_dir(runs), CASE_SUCCEEDS),
                "a configuration error was read as an attempt",
            )

            working = _protocol_transport({})
            _, out = _invoke(runs, [CASE_SUCCEEDS], working)
            self.assertGreater(
                working.calls(), 0, "two configuration errors used up the two"
            )
            self.assertNotIn("not retried under the sealed protocol", out)

    def test_the_command_line_refuses_a_sealed_run_when_no_api_key_loads(self):
        """A keyless sealed run records a configuration error for every case."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            arguments = ["--set", "wild-v2", "--concurrency", "2", "--timeout", "900"]

            with mock.patch.dict(
                os.environ, {sets.SEALED_RUN_ENV_VAR: "wild-v2"}
            ), mock.patch.object(
                run_benchmark.llm, "load_api_key", return_value=None
            ), mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                code, _out, err = _run_cli(arguments)

            self.assertEqual(1, code, "a keyless sealed run was accepted")
            self.assertIn("no API key loads", err)
            self.assertFalse(
                runs.exists(), "the refused invocation created the runs root"
            )

            # It is the key that is missing and not the opt-in, and the keyless
            # check is not the root guard either: with a key the invocation gets
            # past this check and meets the guard, which refuses it because the
            # set's single run has been made. The two messages are asserted apart
            # so neither can stand in for the other.
            with mock.patch.dict(
                os.environ, {sets.SEALED_RUN_ENV_VAR: "wild-v2"}
            ), mock.patch.object(
                run_benchmark.llm, "load_api_key", return_value="a-key"
            ), mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                code, _out, err = _run_cli(arguments)
            self.assertEqual(1, code, "the sealed run was accepted with a key")
            self.assertNotIn(
                "no API key loads",
                err,
                "a key was loaded, so the keyless refusal is the wrong one",
            )
            self.assertIn("nothing is created under it again", err)

    def test_a_killed_attempt_does_not_stop_a_transport_retry(self):
        """TRANSPORT, then a killed attempt: the case is still called."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            flaky = _protocol_transport({CASE_KILLED: "transport"})
            _invoke(runs, [CASE_KILLED], flaky)
            self.assertGreater(flaky.calls(), 0, "the first invocation made no call")

            _killed_attempt(runs, CASE_KILLED)

            working = _protocol_transport({})
            _, out = _invoke(runs, [CASE_KILLED], working)
            self.assertGreater(
                working.calls(), 0, "a killed attempt stopped a transport retry"
            )
            self.assertNotIn("not retried under the sealed protocol", out)

    def test_a_shape_failure_after_a_killed_attempt_is_still_not_retried(self):
        """A killed attempt, then SHAPE with every status 200: not called."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            _killed_attempt(runs, CASE_KILLED)

            shaping = _protocol_transport({CASE_KILLED: "judge_shape"})
            _invoke(runs, [CASE_KILLED], shaping)
            self.assertGreater(shaping.calls(), 0, "the SHAPE invocation made no call")

            working = _protocol_transport({})
            _, out = _invoke(runs, [CASE_KILLED], working)
            self.assertEqual(0, working.calls(), "a SHAPE failure was re-sampled")
            self.assertIn(
                "not retried under the sealed protocol: {0} (SHAPE, every call "
                "answered 200)".format(CASE_KILLED),
                out,
            )

    def test_a_failure_kind_the_code_does_not_retry_names_itself(self):
        """Every kind that is not retried is refused, and the reason says which."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            _write_a_failure(runs, CASE_SUCCEEDS, run_benchmark.FAILURE_REPLAY)
            run_dir = _protocol_run_dir(runs)

            self.assertEqual(
                "{0}, which is not a retried kind".format(run_benchmark.FAILURE_REPLAY),
                sets._sealed_verdict(sets._sealed_attempts(run_dir, CASE_SUCCEEDS)),
            )

            printed = []
            keep = sets.cases_the_sealed_protocol_will_not_retry(
                PROTOCOL_SET, [CASE_SUCCEEDS], MODEL, runs, progress=printed.append
            )
            self.assertEqual([], keep, "a kind that is not retried was retried")
            self.assertEqual(
                [
                    "not retried under the sealed protocol: {0} ({1}, which is not "
                    "a retried kind)".format(
                        CASE_SUCCEEDS, run_benchmark.FAILURE_REPLAY
                    )
                ],
                printed,
            )

    def test_a_broken_chain_refuses_the_protocol_and_names_the_line(self):
        """The protocol reads the record, so a record that does not verify is refused."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            _write_a_failure(runs, CASE_SUCCEEDS, run_benchmark.FAILURE_TRANSPORT)
            path = _protocol_run_dir(runs) / events.EVENTS_FILE
            text = path.read_text(encoding="utf-8")
            # The last line appended a second time: the copy's ``prev`` does not
            # name the line before it, so the chain stops agreeing there.
            path.write_text(text + text.splitlines()[-1] + "\n", encoding="utf-8")

            with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                sets.cases_the_sealed_protocol_will_not_retry(
                    PROTOCOL_SET, [CASE_SUCCEEDS], MODEL, runs
                )
            message = str(caught.exception)
            self.assertIn("does not verify", message)
            self.assertIn("line 3", message)

    def test_a_truncated_last_line_is_not_a_break(self):
        """A killed writer ends the file mid-record; that is not an edited log.

        The partial line is left out of the reading, so the attempt it belonged to
        is one that ended with no terminal event -- printed, and not counted --
        rather than a reason to refuse to apply the protocol at all.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_dir = _protocol_run_dir(runs)
            run_dir.mkdir(parents=True, exist_ok=True)
            log = events.EventLog(
                run_dir / events.EVENTS_FILE, invocation_id=KILLED_INVOCATION
            )
            log.record(events.EVENT_CASE_START, case_no=CASE_KILLED, position=1, total=1)
            log.record(
                events.EVENT_AGENT_CALL,
                case_no=CASE_KILLED,
                role=transcript.ROLE_RIDER_ADVOCATE,
                status=200,
            )
            log.record(
                events.EVENT_AGENT_CALL,
                case_no=CASE_KILLED,
                role=transcript.ROLE_JUDGE,
                status=200,
            )

            path = run_dir / events.EVENTS_FILE
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            path.write_text(
                "".join(lines[:-1]) + lines[-1][: len(lines[-1]) // 2],
                encoding="utf-8",
            )

            printed = []
            keep = sets.cases_the_sealed_protocol_will_not_retry(
                PROTOCOL_SET, [CASE_KILLED], MODEL, runs, progress=printed.append
            )
            self.assertEqual([CASE_KILLED], keep)
            self.assertEqual(
                [
                    "attempt with no terminal event, so it does not count under "
                    "the sealed protocol: {0}".format(CASE_KILLED)
                ],
                printed,
            )

    def test_an_invocation_with_nothing_left_to_run_prints_one_line(self):
        """A no-op sealed invocation says so in one line, not with a summary."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = _protocol_transport({CASE_JUDGE_SHAPE: "judge_shape"})
            _invoke(runs, [CASE_JUDGE_SHAPE], transport)

            # The rule drops the case, so this invocation has nothing to run.
            summary, _ = _invoke(runs, [CASE_JUDGE_SHAPE], transport)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                run_benchmark.print_summary(summary)

            self.assertEqual(run_benchmark.NOTHING_LEFT_TO_RUN + "\n", buffer.getvalue())

    def test_the_failed_cases_header_points_at_the_protocol_for_a_sealed_set(self):
        """A sealed re-run is not a plain cache retry, and the header says so."""
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = _protocol_transport({CASE_TRANSPORT: "transport"})
            summary, _ = _invoke(runs, [CASE_TRANSPORT], transport)

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                run_benchmark.print_summary(summary)

            self.assertIn("the sealed protocol", buffer.getvalue())
            self.assertNotIn("retries exactly these", buffer.getvalue())


class TheAddendumNoteTests(unittest.TestCase):
    """The note states the rules the code applies, before the run."""

    def test_the_note_states_the_four_rules(self):
        self.assertTrue(ADDENDUM_NOTE.is_file(), "the addendum note is not there")
        text = ADDENDUM_NOTE.read_text(encoding="utf-8").lower()
        for rule in ADDENDUM_RULES:
            with self.subTest(rule=rule):
                self.assertIn(rule.lower(), text)


if __name__ == "__main__":
    unittest.main()
