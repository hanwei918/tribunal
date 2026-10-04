"""The last ways into a sealed root are closed, for both sealed roots.

``runs/wild/`` holds the held-out set's single run and ``runs/wild-v2/`` the
second sealed set's. Both runs have been made and both roots are closed
outright, so every command that would write under one of them has to refuse the
whole of the root -- not only the run directory, and not only the spelling the
path happens to be given in.

Each test here is one of those commands, and each is run for **both** roots: the
two are named by their registrations rather than restated, so a third sealed set
would be covered by the same loops.

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
    policy_gaps,
    run_benchmark,
    verify_drafts,
)

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
    runner reads ``run_benchmark.RUNS_DIR``, and the two ``--out-dir`` guards
    read their own. Nothing here touches a committed run.
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

    def sealed_run_directory(self, development_set):
        """``<scratch>/<root>/<slug>/``, holding a run's own record.

        ``run.json`` is what a run leaves behind when it ends, so its presence
        is what makes the root closed. An empty directory, or one holding only
        an event log, is not the same thing and is the fixture the open-root
        control uses.
        """
        run_dir = development_set.run_dir(MODEL, self.scratch)
        run_dir.mkdir(parents=True)
        (run_dir / run_benchmark.METADATA_FILE).write_text("{}\n", encoding="utf-8")
        return run_dir


def _run_cli(arguments):
    """``sets.main``, with both streams captured and no client buildable.

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
            code = sets.main(arguments)
    finally:
        run_benchmark.llm.LLMClient = original
    return code, stdout.getvalue(), stderr.getvalue()


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
    """``--out-dir`` under a sealed root is refused, as the policy-gap loop's is.

    ``runs/wild/`` and ``runs/wild-v2/`` are not run directories with a name a
    reader could mistake these figures for: they are sealed roots, and nothing
    is created under either again. The structural walk catches a destination
    inside a run directory; the sealed-root guard catches one inside a root
    whose run is not there yet.
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
    single run is already there, no case will be run again, so a list of cases
    that "would run" would describe an invocation that cannot happen. The
    closure is printed instead, and the whole output is asserted -- the header,
    the empty counts and the absent plan.
    """

    # ``wild`` fixes no arguments; ``wild-v2`` fixes the owner's command.
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
    }

    def test_a_closed_root_prints_the_closure_and_lists_no_cases(self):
        for development_set in SEALED_SETS:
            with self.subTest(sealed_set=development_set.name):
                self.sealed_run_directory(development_set)
                code, out, err = _run_cli(self.ARGUMENTS[development_set.name])
                self.assertEqual(0, code, err)
                self.assertEqual(CLOSED_ROOT_OUTPUT.format(development_set.name), out)
                self.assertNotIn("would run (1", out)

    def test_a_root_with_no_run_still_prints_the_plan(self):
        """The control: the branch is about the run, not about the command.

        The same command over the same scratch root, with the run's own
        ``run.json`` not yet written, prints the plan for every case.
        """
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


if __name__ == "__main__":
    unittest.main()
