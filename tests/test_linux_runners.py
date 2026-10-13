"""The suite on a machine that cannot rebuild a recorded brief.

Case 111's brief rebuilds to the recorded digest on every platform
(``tests/test_case_111_on_this_platform.py``), but glibc and macOS libm round its
``driver_track.mean_distance_m`` one unit in the last place apart, so a machine
whose libm is not the one that recorded the runs cannot rebuild **that digest**
at all (``tests/portability.py``). The builder is right to refuse a brief that
hashes differently, so what has to change is who asks it to build: a test that
needs only the paths a builder writes must not build a page to learn them, and a
test that truly needs every case must say so and skip where the platform differs.
This module holds the three parts of that to their word.

* **The path list is cheap.** ``ui.site.build.written_paths()`` returns the same
  set it always returned, computed from the sources rather than from a build.
  With ``ui.v2.build.read_every_case`` replaced by a function that raises, it
  still answers and the set is non-empty; the control beside it shows the same
  patch makes the build itself raise, so the first test cannot pass because the
  patch missed.
* **The import does not build the site.** Reloading ``tests.test_language`` and
  ``tests.test_ui_v2`` with ``read_every_case`` raising does not raise, which is
  what those two modules need: each asks the builder for its path list while it
  is being imported.
* **``tools.verify`` skips rather than fails.** The four steps that read every
  case are reported as ``SKIP``, with ``tests.portability``'s reason, when the
  platform helper the command asks answers true; the other five run; the exit
  status is 0, and a step that ran and failed still makes it 1. With the helper
  answering false nothing is skipped, which is every run on macOS.

**The sheet says to run no test for this part.** The owner runs the suite
outside the sandbox; every call here is stubbed -- no builder is run, no report
is run, and no case is read -- so the checks below are what the owner's run
should find green. Run from the project root with::

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import importlib
import io
import sys
import unittest
from pathlib import Path
from typing import Callable, List, Sequence, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402
from tools import verify  # noqa: E402
from ui.site import build as site_build  # noqa: E402
from ui.v2 import build as v2  # noqa: E402

# The two modules that ask the site builder for its path list while they are
# being imported: each held the list at module level, so on a platform that
# cannot rebuild a recorded brief the import itself failed.
RELOADED_MODULES = ("tests.test_language", "tests.test_ui_v2")


def refuse_to_read_a_case():
    """A stand-in for ``ui.v2.build.read_every_case``: being called is the failure."""
    raise AssertionError("this call reads every case of the four runs")


def steps_that_run() -> List[verify.Step]:
    """The steps the command still runs when the platform difference is present."""
    return [
        step for step in verify.STEPS if step.name not in verify.CASE_READING_STEPS
    ]


class TheWrittenPathsTests(unittest.TestCase):
    """``written_paths()`` lists the paths without building anything."""

    def test_it_answers_with_the_case_reader_made_to_fail(self):
        """With ``read_every_case`` replaced by a raising stub, it still returns."""
        with mock.patch.object(v2, "read_every_case", refuse_to_read_a_case):
            with mock.patch.object(site_build, "_QUEUE_TABLE_BODIES", None):
                paths = site_build.written_paths()
        self.assertTrue(paths, "written_paths() returned nothing")
        self.assertTrue(
            all(isinstance(name, str) for name in paths), sorted(paths)
        )

    def test_the_stub_is_the_one_the_build_calls(self):
        """The control: the same patch makes the build raise rather than answer."""
        with mock.patch.object(v2, "read_every_case", refuse_to_read_a_case):
            with mock.patch.object(site_build, "_QUEUE_TABLE_BODIES", None):
                with self.assertRaises(AssertionError):
                    site_build.pages()

    def test_the_cheap_list_is_the_list_the_build_writes(self):
        """It is the set ``pages()`` and ``assets()`` give, and this builds them."""
        portability.require_the_same_libm()
        expected = frozenset(
            [
                path.relative_to(site_build.DIST_DIR).as_posix()
                for path, _text in site_build.pages()
            ]
            + [
                path.relative_to(site_build.DIST_DIR).as_posix()
                for path, _data in site_build.assets()
            ]
        )
        self.assertEqual(expected, site_build.written_paths())


class TheImportTests(unittest.TestCase):
    """A module that needs only the paths no longer builds the site to import."""

    def test_reloading_the_two_modules_reads_no_case(self):
        for name in RELOADED_MODULES:
            with self.subTest(module=name):
                module = importlib.import_module(name)
                with mock.patch.object(v2, "read_every_case", refuse_to_read_a_case):
                    importlib.reload(module)


class TheVerifySkipTests(unittest.TestCase):
    """``tools.verify`` reports SKIP, not FAIL, for the platform difference."""

    def run_with(
        self, helper: bool, run_step: Callable[[Sequence[str]], int]
    ) -> Tuple[int, str, List[List[str]]]:
        """Every step through a stub, with the platform helper forced to ``helper``."""
        seen: List[List[str]] = []

        def recording(command: Sequence[str]) -> int:
            seen.append(list(command))
            return run_step(command)

        buffer = io.StringIO()
        with mock.patch.object(
            verify, "the_platform_moves_a_recorded_brief", return_value=helper
        ):
            code = verify.run(verify.STEPS, run_step=recording, stream=buffer)
        return code, buffer.getvalue(), seen

    def test_the_case_reading_steps_skip_and_the_others_run(self):
        code, printed, seen = self.run_with(True, lambda command: 0)
        self.assertEqual(0, code)
        self.assertEqual(len(verify.CASE_READING_STEPS), printed.count("SKIP"))
        for name in verify.CASE_READING_STEPS:
            self.assertIn("SKIP  " + name, printed)
        self.assertIn(portability.PLATFORM_REASON, printed)
        self.assertEqual([list(step.command) for step in steps_that_run()], seen)
        self.assertEqual(len(steps_that_run()), printed.count("PASS"))
        self.assertIn(
            "{0} step(s) skipped".format(len(verify.CASE_READING_STEPS)), printed
        )

    def test_a_step_that_ran_and_failed_still_fails_the_command(self):
        failing = verify.STEPS[1].command
        code, printed, _seen = self.run_with(
            True, lambda command: 1 if command == failing else 0
        )
        self.assertEqual(1, code)
        self.assertIn(verify.STEPS[1].name, printed)
        self.assertIn("FAIL", printed)
        self.assertIn("1 of {0} step(s) failed".format(len(verify.STEPS)), printed)

    def test_nothing_is_skipped_when_the_platform_recorded_the_briefs(self):
        code, printed, seen = self.run_with(False, lambda command: 0)
        self.assertEqual(0, code)
        self.assertNotIn("SKIP", printed)
        self.assertEqual(len(verify.STEPS), len(seen))
        self.assertEqual(len(verify.STEPS), printed.count("PASS"))
        self.assertIn("all {0} step(s) passed".format(len(verify.STEPS)), printed)


if __name__ == "__main__":
    unittest.main()
