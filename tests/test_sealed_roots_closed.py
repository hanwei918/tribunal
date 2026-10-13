"""The last ways into a sealed root are closed, for every sealed root.

``runs/wild/`` holds the held-out set's single run, ``runs/wild-v2/`` the second
sealed set's, ``runs/sealed-v1/`` the third's, ``runs/sealed-v2/`` the fourth's
and ``runs/sealed-v3/`` the fifth's. All five runs have been made -- the fifth's
was started once on 2026-10-13 and stopped after 8 of its 30 cases -- and all five
roots are closed outright, so every command that would write
under one of them has to refuse the whole of the root -- not only the run
directory, and not only the spelling the path happens to be given in.

Each test here is one of those commands, and each is run for **every** root: the
five are named by their registrations rather than restated, so a further sealed
set would be covered by the same loops.

**Every test runs against a scratch root.** Nothing reads or writes a committed
run: the runs root is a temporary directory, the modules are made to believe it
is the repository's own, and no client can be built -- the class is patched to
raise, so a guard that let a run start fails the test rather than reaching the
network.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    amount_rule,
    baselines,
    development_sets as sets,
    grade,
    policy_gaps,
    run_benchmark,
    sealed_roots,
    verify_drafts,
)
from ui import build as ui_build  # noqa: E402

MODEL = "deepseek/deepseek-flash"

# The two sealed sets, in registration order. Their roots and their names are
# read off the registrations, so a name and the directory it writes into cannot
# drift apart here.
SEALED_SETS = sets.SEALED_SETS

# What ``--check`` prints for a set whose root is closed, written out rather than
# computed from the renderer, so a change to the rendering is a failing test and
# not a test that agrees with itself.
CLOSED_ROOT_OUTPUT = (
    "sealed set {0} -- its root is closed: the single run is committed\n"
    "  would run (0): nothing\n"
    "  would not run (0):\n"
    "    nothing\n"
    "  attempts that do not count (0):\n"
    "    nothing\n"
)

# And the header it prints for a root that is not closed, so the branch is shown
# to be about the run's presence rather than about the command.
OPEN_ROOT_HEADER = "sealed set {0} -- what one plain invocation would run\n"


class ScratchRunsRootTestCase(unittest.TestCase):
    """A runs root of its own, believed to be the repository's by every module.

    ``--runs-dir`` is refused for a sealed set, so a scratch root is put in
    place by moving the constants: the command line reads ``sets.RUNS_DIR``, the
    runner reads ``run_benchmark.RUNS_DIR`` -- which is also what
    :func:`eval.sealed_roots.refuse_a_sealed_destination` reads for the
    repository's own root -- and the two ``--out-dir`` guards read their own.
    Nothing here touches a committed run.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.scratch = Path(self._tmp.name) / "runs"
        self.scratch.mkdir(parents=True)
        for module in (run_benchmark, sets, baselines, amount_rule):
            patcher = mock.patch.object(module, "RUNS_DIR", self.scratch)
            patcher.start()
            self.addCleanup(patcher.stop)


def _run_main(entry, arguments):
    """One command's ``main``, with both streams captured and no client buildable.

    Every invocation here is refused before a client is built, so no test may be
    able to build one: the class is patched to raise for the duration of the
    call, and a guard that let a run start fails the test instead of reaching
    the network. Returns ``(code, out, err)``.
    """

    def refuse_to_build_a_client(*_args, **_kwargs):
        raise AssertionError("a client was built for a command that must not run")

    stdout, stderr = io.StringIO(), io.StringIO()
    original = run_benchmark.llm.LLMClient
    run_benchmark.llm.LLMClient = refuse_to_build_a_client
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entry(arguments)
    finally:
        run_benchmark.llm.LLMClient = original
    return code, stdout.getvalue(), stderr.getvalue()


def _run_cli(arguments):
    """``sets.main``, with both streams captured and no client buildable."""
    return _run_main(sets.main, arguments)


# --------------------------------------------------------------------------
# The recorded-drafts measurement
# --------------------------------------------------------------------------
class RecordedDraftsDestinationTests(ScratchRunsRootTestCase):
    """``--runs-dir runs/wild-v2`` used to put this measurement inside it.

    The destination is always ``<runs-dir>/verify-recorded-drafts/<model>/``, so
    the way it lands under a sealed root is by being given the sealed root as its
    runs root. The headline walk cannot see that -- a sealed root is named after
    the set, and the destination goes through ``verify-recorded-drafts/`` -- so
    the sealed-root guard is what refuses it.
    """

    def test_either_sealed_root_is_refused_as_a_runs_root(self):
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                runs_dir = self.scratch / development_set.runs_subdir
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    verify_drafts.assert_recorded_drafts_destination(runs_dir, MODEL)
                message = str(caught.exception)
                self.assertIn(str(runs_dir.resolve()), message)
                self.assertIn("directory of its own", message)

    def test_the_destination_of_its_own_is_still_taken(self):
        """A guard that refused everything would pass the test above."""
        accepted = verify_drafts.assert_recorded_drafts_destination(self.scratch, MODEL)
        self.assertEqual(
            self.scratch / "verify-recorded-drafts" / run_benchmark.model_slug(MODEL),
            accepted,
        )


# --------------------------------------------------------------------------
# The two --out-dir guards
# --------------------------------------------------------------------------
class OutDirectoryGuardsTests(ScratchRunsRootTestCase):
    """The derived ``--out-dir`` guards refuse a sealed root.

    ``runs/wild/``, ``runs/wild-v2/``, ``runs/sealed-v1/``, ``runs/sealed-v2/``
    and ``runs/sealed-v3/`` are not run
    directories with a name a reader could mistake these figures for: they are
    sealed roots, and nothing is created under any of them again. The structural
    walk catches a destination inside a run directory; the sealed-root guard
    catches one inside a root whose single run is committed.

    Three commands derive a destination of their own and refuse a sealed root
    through :func:`eval.sealed_roots.refuse_a_sealed_destination`: the baselines,
    the amount-rule measurement and the policy-gap report. All three are tested
    here, each for every sealed root.
    """

    def test_the_baselines_destination_refuses_either_sealed_root(self):
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                destination = (
                    self.scratch
                    / development_set.runs_subdir
                    / baselines.BASELINES_DIRNAME
                )
                with self.assertRaises(baselines.BaselineError) as caught:
                    baselines.assert_not_a_run_directory(destination, self.scratch, MODEL)
                message = str(caught.exception)
                self.assertIn(str((self.scratch / development_set.runs_subdir).resolve()), message)
                self.assertIn("directory of their own", message)

    def test_the_baselines_destination_of_its_own_is_still_taken(self):
        clean = baselines.baselines_directory(self.scratch)
        self.assertEqual(
            clean.resolve(),
            baselines.assert_not_a_run_directory(clean, self.scratch, MODEL),
        )

    def test_the_amount_rule_destination_refuses_either_sealed_root(self):
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                destination = (
                    self.scratch
                    / development_set.runs_subdir
                    / amount_rule.AMOUNT_RULE_DIRNAME
                )
                with self.assertRaises(amount_rule.AmountRuleError) as caught:
                    amount_rule.assert_not_a_run_directory(destination, self.scratch, MODEL)
                message = str(caught.exception)
                self.assertIn(str((self.scratch / development_set.runs_subdir).resolve()), message)
                self.assertIn("directory of its own", message)

    def test_the_amount_rule_destination_of_its_own_is_still_taken(self):
        clean = amount_rule.amount_rule_directory(self.scratch)
        self.assertEqual(
            clean.resolve(),
            amount_rule.assert_not_a_run_directory(clean, self.scratch, MODEL),
        )

    def test_the_policy_gap_report_destination_refuses_either_sealed_root(self):
        """The report's own guard routes through the sealed-root helper.

        ``policy_gaps.assert_not_a_run_directory`` refuses a headline directory
        by name and a run directory structurally, and it also calls
        :func:`eval.sealed_roots.refuse_a_sealed_destination`. Nothing else in
        the guard sees a destination under a sealed root whose run directory the
        name does not match, so without that call the report would be written
        under a root whose single run is committed. The closing sentence is the
        report's own, which is why the message is asserted and not only the
        exception type.
        """
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                runs_dir = self.scratch / development_set.runs_subdir
                destination = runs_dir / policy_gaps.POLICY_GAPS_DIRNAME
                with self.assertRaises(policy_gaps.PolicyGapError) as caught:
                    policy_gaps.assert_not_a_run_directory(destination, runs_dir, MODEL)
                message = str(caught.exception)
                self.assertIn(str(runs_dir.resolve()), message)
                self.assertIn("directory of its own", message)
                self.assertFalse(destination.exists())


# --------------------------------------------------------------------------
# The loop's refusal, and the one sealed root it does read
# --------------------------------------------------------------------------
class LoopRefusalTests(ScratchRunsRootTestCase):
    """This volume is case-insensitive, so the refusal has to be too.

    ``runs/WILD-V2/<slug>/`` names the same directory as
    ``runs/wild-v2/<slug>/``. The comparison is component by component on the
    folded components, so the refusal answers about the directory rather than
    about the spelling, and the message names the set rather than the case the
    caller typed.
    """

    def test_the_sealed_record_is_refused_however_it_is_spelled(self):
        for spelling in ("wild-v2", "WILD-V2", "Wild-V2"):
            with self.subTest(spelling=spelling):
                run_dir = self.scratch / spelling / run_benchmark.model_slug(MODEL)
                with self.assertRaises(policy_gaps.PolicyGapError) as caught:
                    policy_gaps.assert_not_a_sealed_record_the_loop_does_not_read(run_dir)
                self.assertIn("sealed set wild-v2", str(caught.exception))

    def test_the_held_out_set_is_not_refused_because_the_loop_reads_it(self):
        """``runs/wild/`` is the loop's own source, through ``wild-dev``.

        The held-out set's 64 cases have been development data since
        2026-10-01, so the loop does read them -- re-run as ``wild-dev`` -- and a
        guard that refused the held-out root would refuse the loop's own input.
        The refusal is by the component, so ``wild`` is a different component
        from ``wild-v2`` whichever case it is written in.
        """
        for spelling in ("wild", "WILD", "Wild"):
            with self.subTest(spelling=spelling):
                run_dir = self.scratch / spelling / run_benchmark.model_slug(MODEL)
                self.assertEqual(
                    run_dir.resolve(),
                    policy_gaps.assert_not_a_sealed_record_the_loop_does_not_read(
                        run_dir
                    ),
                )


# --------------------------------------------------------------------------
# --check on a set whose root is closed
# --------------------------------------------------------------------------
class CheckOnAClosedRootTests(ScratchRunsRootTestCase):
    """A closed root has no plan to print.

    ``--check`` prints what one plain invocation would run. For a set whose
    single run has been made, no case will be run again, so a list of cases that
    "would run" would describe an invocation that cannot happen. The closure is
    printed instead, and the whole output is asserted -- the header, the empty
    counts and the absent plan.

    **The fact is the registration, not a file under the root.** The closure is
    read from ``run_benchmark.MADE_SEALED_RUNS_SUBDIRS``, the one list that says
    which sealed runs have been made, so these tests patch the list rather than
    writing a ``run.json``: a root whose run was made is closed for every model,
    and a root whose run has not been made is open for every model.
    ``UNRUN_SEALED_RUNS_SUBDIRS`` and the tuple built from the two are patched
    with it, so nothing reads a list that disagrees with the others.
    """

    # ``wild`` fixes no arguments; ``wild-v2``, ``sealed-v1``, ``sealed-v2`` and
    # ``sealed-v3`` fix the owner's command, each at the arguments its own
    # registration names.
    ARGUMENTS = {
        "wild": ["--set", "wild", "--check"],
        "wild-v2": [
            "--set",
            "wild-v2",
            "--concurrency",
            "2",
            "--timeout",
            "900",
            "--check",
        ],
        "sealed-v1": [
            "--set",
            "sealed-v1",
            "--concurrency",
            "2",
            "--timeout",
            "900",
            "--check",
        ],
        "sealed-v2": [
            "--set",
            "sealed-v2",
            "--concurrency",
            "2",
            "--timeout",
            "900",
            "--check",
        ],
        "sealed-v3": [
            "--set",
            "sealed-v3",
            "--concurrency",
            "2",
            "--timeout",
            "900",
            "--check",
        ],
    }

    def _patch_subdir_lists(self, made, unrun=()):
        """Make the two subdirectory lists, and the tuple built from them, say this."""
        for name, value in (
            ("MADE_SEALED_RUNS_SUBDIRS", tuple(made)),
            ("UNRUN_SEALED_RUNS_SUBDIRS", tuple(unrun)),
            ("SEALED_RUNS_SUBDIRS", tuple(made) + tuple(unrun)),
        ):
            patcher = mock.patch.object(run_benchmark, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_closed_root_prints_the_closure_and_lists_no_cases(self):
        # All five sealed sets have been run, so all five roots are closed and
        # the plan branch below is reached only by emptying the lists. The closure
        # is asserted for every root the registration says has been made, and the
        # list of those is pinned here, so a set cannot pass by being skipped.
        closed = [
            development_set
            for development_set in SEALED_SETS
            if sets.sealed_root_is_closed(development_set)
        ]
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1", "sealed-v2", "sealed-v3"),
            tuple(item.name for item in closed),
        )
        for development_set in closed:
            with self.subTest(sealed_set=development_set.name):
                code, out, err = _run_cli(self.ARGUMENTS[development_set.name])
                self.assertEqual(0, code, err)
                self.assertEqual(CLOSED_ROOT_OUTPUT.format(development_set.name), out)
                self.assertNotIn("would run (1", out)

    def test_a_root_whose_run_has_not_been_made_still_prints_the_plan(self):
        """The control: the branch is about the list, not about the command.

        The same command over the same scratch root, with both subdirectory
        lists emptied -- which is what a sealed set that has been drafted,
        imported and not yet run would look like -- prints the plan for every
        case.
        """
        self._patch_subdir_lists(made=(), unrun=())
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                code, out, err = _run_cli(self.ARGUMENTS[development_set.name])
                self.assertEqual(0, code, err)
                self.assertTrue(
                    out.startswith(OPEN_ROOT_HEADER.format(development_set.name)),
                    out,
                )
                self.assertIn(
                    "would run ({0}):".format(len(development_set.cases)), out
                )

    def test_the_closure_does_not_depend_on_which_model_is_named(self):
        """A non-default ``--model`` is looking at the same closed root.

        The root holds one run, made under one model. Asking about another model
        used to look for that model's own ``run.json``, find none, and print a
        plan for an invocation that cannot happen; the closure is the root's, so
        the model named changes nothing.
        """
        for other in ("deepseek/deepseek-v4.1-flash", "some/other-model"):
            with self.subTest(model=other):
                code, out, err = _run_cli(
                    ["--set", "wild", "--model", other, "--check"]
                )
                self.assertEqual(0, code, err)
                self.assertEqual(CLOSED_ROOT_OUTPUT.format("wild"), out)
                self.assertNotIn("would run (1", out)

    def test_the_made_list_is_the_half_that_decides(self):
        """``MADE_SEALED_RUNS_SUBDIRS`` closes a root; the other list does not."""
        self._patch_subdir_lists(made=("wild-v2",), unrun=("wild",))
        code, out, err = _run_cli(self.ARGUMENTS["wild-v2"])
        self.assertEqual(0, code, err)
        self.assertEqual(CLOSED_ROOT_OUTPUT.format("wild-v2"), out)
        code, out, err = _run_cli(self.ARGUMENTS["wild"])
        self.assertEqual(0, code, err)
        self.assertTrue(out.startswith(OPEN_ROOT_HEADER.format("wild")), out)


# --------------------------------------------------------------------------
# Every command that writes to a path a caller names
# --------------------------------------------------------------------------
class NamedPathDestinationTests(ScratchRunsRootTestCase):
    """Six commands write to a path the caller names, and each refuses a root.

    ``run_benchmark --external``, ``eval.grade --out``, ``ui.build --out``,
    ``policy_gaps draft --proposals-dir``, ``policy_gaps approve
    --amendments-dir`` and ``policy_gaps reject --proposal``. Each of them can be
    pointed at a sealed root, and a file written there would be the first new
    thing under a root whose single run is committed. The refusal is one rule, in
    :func:`eval.sealed_roots.refuse_a_sealed_destination`, and every test here is
    one of those commands, run for **every** sealed root.

    ``tribunal.pipeline --out`` and ``tribunal.precedents --store`` are
    deliberately not among them: ``tribunal/`` imports nothing from ``eval/`` and
    the evaluated system stays byte-identical to the tag it was frozen at, so
    those guards are their callers' own.
    """

    def _in_root(self, development_set, *parts):
        return self.scratch / development_set.runs_subdir / Path(*parts)

    # -- run_benchmark --external ------------------------------------------
    def test_the_external_runner_refuses_either_sealed_root(self):
        """``--runs-dir runs/wild-v2 --external`` is the way in.

        The destination is a well-formed external one -- under the runs root's
        ``external/`` -- so the runner's own rule lets it through and only the
        sealed-root rule refuses it.
        """
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                runs_dir = self.scratch / development_set.runs_subdir
                destination = runs_dir / run_benchmark.EXTERNAL_RUNS_SUBDIR / "ryde"
                with self.assertRaises(sealed_roots.SealedDestinationError) as caught:
                    run_benchmark.assert_external_run_directory(destination, runs_dir)
                self.assertIn(str(destination.resolve()), str(caught.exception))
                self.assertFalse(destination.exists())

    def test_an_external_run_of_its_own_is_still_taken(self):
        """A guard that refused everything would pass the test above."""
        destination = self.scratch / run_benchmark.EXTERNAL_RUNS_SUBDIR / "ryde"
        self.assertEqual(
            destination.resolve(),
            run_benchmark.assert_external_run_directory(destination, self.scratch),
        )

    def test_the_external_command_line_reports_a_refusal_not_a_traceback(self):
        """``--external --runs-dir <sealed root>`` is a FATAL line, not a crash.

        The destination is well-formed for an external case -- under the runs
        root's ``external/`` -- so the runner's own rule lets it through and the
        sealed-root guard is what refuses it. That refusal used to leave ``main``
        as a ``SealedDestinationError`` and print a traceback; the command now
        reports it the way its other refusals are reported.
        """
        case_path = PROJECT_ROOT / "data" / "external" / "ryde" / "case-00901.json"
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                runs_dir = self.scratch / development_set.runs_subdir
                code, out, err = _run_main(
                    run_benchmark.main,
                    ["--external", str(case_path), "--runs-dir", str(runs_dir)],
                )
                self.assertEqual(1, code, err)
                self.assertIn("FATAL", err)
                self.assertIn("is sealed", err)
                self.assertNotIn("Traceback", err)
                self.assertFalse(
                    (runs_dir / run_benchmark.EXTERNAL_RUNS_SUBDIR).exists()
                )

    # -- eval.grade --out ---------------------------------------------------
    def test_grade_out_refuses_either_sealed_root(self):
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                destination = self._in_root(
                    development_set, run_benchmark.model_slug(MODEL), "report.md"
                )
                code, out, err = _run_main(
                    grade.main, ["--self-test", "--out", str(destination)]
                )
                self.assertEqual(1, code, err)
                self.assertIn("FATAL", err)
                self.assertIn(str(destination.resolve()), err)
                self.assertFalse(destination.exists())

    def test_grade_out_leaves_a_committed_report_byte_identical(self):
        """The report already there is neither overwritten nor opened."""
        destination = self._in_root(
            sets.WILD_V2, run_benchmark.model_slug(MODEL), "report.md"
        )
        destination.parent.mkdir(parents=True)
        committed = b"# the report that was committed\n"
        destination.write_bytes(committed)

        code, out, err = _run_main(
            grade.main, ["--self-test", "--out", str(destination)]
        )
        self.assertEqual(1, code, err)
        self.assertEqual(committed, destination.read_bytes())

    def test_grade_out_of_its_own_is_still_taken(self):
        destination = self.scratch / "report.md"
        code, out, err = _run_main(
            grade.main, ["--self-test", "--out", str(destination)]
        )
        self.assertEqual(0, code, err)
        self.assertTrue(destination.is_file())

    # -- ui.build --out -----------------------------------------------------
    def test_ui_build_out_refuses_either_sealed_root(self):
        """``--set corpus --out runs/wild/...`` is the way in.

        ``--out`` on its own is refused by the command's own argument rule --
        a destination is one page's, so the page has to be named -- and that
        refusal comes before the sealed-root guard is reached. ``--set`` names
        the page whose run would be read; the guard runs before any run is read,
        so this refuses without building a page of the corpus either.
        """
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                destination = self._in_root(
                    development_set, run_benchmark.model_slug(MODEL), "index.html"
                )
                code, out, err = _run_main(
                    ui_build.main, ["--set", "corpus", "--out", str(destination)]
                )
                self.assertEqual(1, code, err)
                self.assertIn("FATAL", err)
                self.assertIn(str(destination.resolve()), err)
                self.assertFalse(destination.exists())

    def test_a_page_of_its_own_is_still_taken(self):
        """The control: the same command with a destination of its own.

        ``--check`` writes nothing, so the control is the guard letting the
        command through to its own rule -- here, that there is no page yet. The
        ``--set`` is the one the test above uses, so the only difference between
        the two is where the destination is.
        """
        destination = self.scratch / "index.html"
        code, out, err = _run_main(
            ui_build.main, ["--check", "--set", "corpus", "--out", str(destination)]
        )
        self.assertEqual(1, code)
        self.assertIn("does not exist", out)
        self.assertNotIn("is sealed", out)

    # -- policy_gaps draft --proposals-dir ----------------------------------
    def test_the_draft_proposals_directory_refuses_either_sealed_root(self):
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                root = self.scratch / development_set.runs_subdir
                proposals = root / policy_gaps.PROPOSALS_DIRNAME
                code, out, err = _run_main(
                    policy_gaps.main,
                    [
                        "draft",
                        "--report",
                        str(self.scratch / "nowhere.json"),
                        "--cluster",
                        "C4",
                        "--proposals-dir",
                        str(root),
                    ],
                )
                self.assertEqual(1, code, err)
                self.assertIn("FATAL", err)
                self.assertIn(str(proposals.resolve()), err)
                self.assertFalse(proposals.exists())

    # -- policy_gaps approve --amendments-dir -------------------------------
    def test_the_approve_amendments_directory_refuses_either_sealed_root(self):
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                root = self.scratch / development_set.runs_subdir
                amendments = policy_gaps.amendments_directory(root)
                code, out, err = _run_main(
                    policy_gaps.main,
                    [
                        "approve",
                        "--proposal",
                        str(self.scratch / "nowhere.json"),
                        "--approved-by",
                        "the owner",
                        "--amendments-dir",
                        str(root),
                    ],
                )
                self.assertEqual(1, code, err)
                self.assertIn("FATAL", err)
                self.assertIn(str(amendments.resolve()), err)
                self.assertFalse(amendments.exists())

    # -- policy_gaps reject --proposal --------------------------------------
    def test_the_reject_command_refuses_a_proposal_under_either_sealed_root(self):
        """``reject`` rewrites the file it is given, so it is guarded too.

        The rejection is recorded in the proposal file itself, so a
        ``--proposal`` under a sealed root would rewrite a committed run file.
        The file is written with valid JSON and its bytes are asserted unchanged,
        so a guard that let the command through would be seen to have rewritten
        it. The refusal is asserted to be the sealed-root one and not the
        command's own ``policy/proposals/`` rule, because a proposal under a
        sealed root fails both and only the sealed-root sentence says which.
        """
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                proposal = (
                    self.scratch
                    / development_set.runs_subdir
                    / "0001-a-proposal.json"
                )
                proposal.parent.mkdir(parents=True, exist_ok=True)
                committed = '{"status": "PROPOSED", "clause": {}}\n'
                proposal.write_text(committed, encoding="utf-8")
                code, out, err = _run_main(
                    policy_gaps.main,
                    [
                        "reject",
                        "--proposal",
                        str(proposal),
                        "--by",
                        "the owner",
                        "--reason",
                        "no",
                    ],
                )
                self.assertEqual(1, code, err)
                self.assertIn("FATAL", err)
                self.assertIn("is sealed", err)
                self.assertIn(str(proposal.resolve()), err)
                self.assertEqual(committed, proposal.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
