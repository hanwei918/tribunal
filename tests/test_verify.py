"""One command for a judge -- the eleven steps, and a stub that fails one of them.

``tools/verify.py`` runs the test suite, the four reports, the figure check and
the five builders' currency checks, and prints one line each. This module holds
it to two things:

* **The step list is exactly the eleven the sheet names**, in order, and
  ``--quick`` drops the test suite and nothing else. A step added or dropped is a
  step a judge is not told about.
* **A failing step is reported and makes the command fail.** Each step is
  replaced by a stub -- no test suite, no report and no builder is run -- and a
  stub that fails one step must make the command exit 1 and print that step's
  name. Without that control a command that returned 0 whatever happened would
  pass the passing test.

No model call is made and no network is reached, and no step is really run: every
call in this module passes a stub. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from typing import Callable, List, Sequence
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import verify  # noqa: E402

MODULE = PROJECT_ROOT / "tools" / "verify.py"

# The eleven steps, by the name the report gives each, in order. Stated here once
# so the command's own list and this one cannot drift apart silently.
EXPECTED_STEPS = (
    "tests",
    "eval.v6_runs",
    "eval.business_value",
    "eval.fairness",
    "eval.func_sets",
    "tools.check_figures",
    "ui.v2.build",
    "ui.build",
    "ui.site.build",
    "ui.v8.build",
    "ui.v6.build",
)


def stub_failing_at(index: int) -> Callable[[Sequence[str]], int]:
    """A runner that fails the step at ``index`` and passes every other."""

    def run_step(command: Sequence[str]) -> int:
        return 1 if command == verify.STEPS[index].command else 0

    return run_step


class TheStepListTests(unittest.TestCase):
    """The eleven steps, in order, and what ``--quick`` drops."""

    def test_the_step_list_is_exactly_the_eleven(self):
        self.assertEqual(EXPECTED_STEPS, tuple(step.name for step in verify.STEPS))

    def test_the_suite_is_the_first_step(self):
        self.assertEqual(verify.SUITE_STEP, verify.STEPS[0].name)
        self.assertEqual("tests", verify.STEPS[0].name)

    def test_quick_drops_the_test_suite_and_nothing_else(self):
        self.assertEqual(
            EXPECTED_STEPS[1:], tuple(step.name for step in verify.steps_for(True))
        )
        self.assertEqual(
            EXPECTED_STEPS, tuple(step.name for step in verify.steps_for(False))
        )

    def test_every_step_has_a_command(self):
        for step in verify.STEPS:
            with self.subTest(step=step.name):
                self.assertTrue(step.command)
                self.assertTrue(all(isinstance(part, str) for part in step.command))

    def test_the_module_is_ascii(self):
        offenders = [byte for byte in MODULE.read_bytes() if byte >= 128]
        self.assertEqual([], offenders, "the module carries a non-ASCII byte")


class TheStubTests(unittest.TestCase):
    """A failing step, with every step replaced by a stub."""

    def setUp(self):
        # These tests are about the step list and the exit code, not the
        # platform: on Linux the platform skip reports the six case-reading
        # steps as SKIP before any stub is reached, so it is forced off here.
        patcher = mock.patch.object(
            verify, "the_platform_moves_a_recorded_brief", lambda: False
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_step_passing_exits_zero(self):
        buffer = io.StringIO()
        code = verify.run(verify.STEPS, run_step=lambda command: 0, stream=buffer)
        self.assertEqual(0, code)
        self.assertEqual(len(verify.STEPS), buffer.getvalue().count("PASS"))
        self.assertIn(
            "all {0} step(s) passed".format(len(verify.STEPS)), buffer.getvalue()
        )

    def test_a_failing_step_makes_the_command_exit_one_and_names_it(self):
        for index in range(len(verify.STEPS)):
            name = verify.STEPS[index].name
            with self.subTest(step=name):
                buffer = io.StringIO()
                code = verify.run(
                    verify.STEPS, run_step=stub_failing_at(index), stream=buffer
                )
                printed = buffer.getvalue()
                self.assertEqual(1, code)
                self.assertIn(name, printed)
                self.assertIn("1 of {0} step(s) failed".format(len(verify.STEPS)), printed)

    def test_a_quick_run_reports_nine_steps(self):
        """``--quick``'s list, run through the same stub."""
        steps = verify.steps_for(True)
        buffer = io.StringIO()
        code = verify.run(steps, run_step=lambda command: 0, stream=buffer)
        self.assertEqual(0, code)
        self.assertEqual(len(steps), buffer.getvalue().count("PASS"))
        self.assertNotIn("PASS  " + verify.SUITE_STEP, buffer.getvalue())

    def test_the_stub_is_the_only_thing_called(self):
        """No step's real command is run: the stub sees every command once."""
        seen: List[List[str]] = []

        def run_step(command: Sequence[str]) -> int:
            seen.append(list(command))
            return 0

        verify.run(verify.STEPS, run_step=run_step, stream=io.StringIO())
        self.assertEqual(
            [list(step.command) for step in verify.STEPS], seen
        )


if __name__ == "__main__":
    unittest.main()
