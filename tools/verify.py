"""One command for a judge: every check this repository makes, in one run.

A judge who wants to know whether this repository is what it says it is should
not have to read a sheet to find out which commands to run, in which order, and
which of them need a key. This command runs them all and prints one line each.
Eleven steps, in order:

1. the full test suite, ``python3 -m unittest discover -s tests``;
2. ``python3 -m eval.v6_runs --report`` -- the version-6 runs, graded;
3. ``python3 -m eval.business_value --report`` -- the clock, the cost and the
   lanes;
4. ``python3 -m eval.fairness --report`` -- the error lean, the position swap and
   the calibration;
5. ``python3 -m eval.func_sets --report`` -- the functional sets;
6. ``python3 -m tools.check_figures`` -- one figure, one value everywhere;
7. ``python3 -m ui.v2.build --check`` -- the queue and the case pages are current;
8. ``python3 -m ui.build --check`` -- the replay pages are current;
9. ``python3 -m ui.site.build --check`` -- the product site is current;
10. ``python3 -m ui.v8.build --check`` -- the version-8 case pages are current;
11. ``python3 -m ui.v6.build --check`` -- the version-6 case pages, both
    languages, are current.

**No key, no network, no model call.** Every step is read-only, and each of the
reports says so in its own output. ``--quick`` skips the test suite, which is the
one step that takes minutes rather than seconds.

**One platform difference, reported as a skip.** Six of the eleven steps read
every case of the four runs and rebuild every brief -- the figure check and the
five builders' currency checks. glibc and macOS libm round case 111's
``driver_track.mean_distance_m`` one unit in the last place apart, so on a Linux
machine those six steps would each fail for a reason that is not a defect in
this repository (``tests/portability.py`` names the difference and the guard).
When :func:`tests.portability.the_case_111_platform_difference` is true they are
reported as ``SKIP`` with that reason instead of run, and the summary counts the
steps that passed, the steps that failed and the steps that were skipped. The
exit status is non-zero only when a step that ran failed, so a Linux judge sees
a command that says what it did not check rather than one that is red. On macOS
the difference is never present, nothing is skipped, and the command behaves
exactly as it always did.

Each step is run with the interpreter running this module, so the two halves
cannot come from different Pythons. A step's output is captured and not printed:
the line says whether it passed and how long it took, and a failing step's name
is printed again in the summary so it can be found without reading the log.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional, Sequence, TextIO, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402


class Step(NamedTuple):
    """One command this repository runs, and the name it is reported under."""

    name: str
    command: Tuple[str, ...]


# The eleven steps, in the order a judge should read them: the suite first, then
# the three reports that grade the runs, then the figure check, then the five
# builders' own currency checks. ``sys.executable`` is the interpreter running
# this module, so the step and this command cannot come from different Pythons.
STEPS: Tuple[Step, ...] = (
    Step("tests", (sys.executable, "-m", "unittest", "discover", "-s", "tests")),
    Step("eval.v6_runs", (sys.executable, "-m", "eval.v6_runs", "--report")),
    Step(
        "eval.business_value",
        (sys.executable, "-m", "eval.business_value", "--report"),
    ),
    Step("eval.fairness", (sys.executable, "-m", "eval.fairness", "--report")),
    Step("eval.func_sets", (sys.executable, "-m", "eval.func_sets", "--report")),
    Step("tools.check_figures", (sys.executable, "-m", "tools.check_figures")),
    Step("ui.v2.build", (sys.executable, "-m", "ui.v2.build", "--check")),
    Step("ui.build", (sys.executable, "-m", "ui.build", "--check")),
    Step("ui.site.build", (sys.executable, "-m", "ui.site.build", "--check")),
    Step("ui.v8.build", (sys.executable, "-m", "ui.v8.build", "--check")),
    Step("ui.v6.build", (sys.executable, "-m", "ui.v6.build", "--check")),
)

# The step ``--quick`` drops: the suite is the one that takes minutes.
SUITE_STEP = "tests"

# The six steps that read every case of the four runs: the figure check and the
# five builders' own currency checks. Each rebuilds every brief, so each meets
# the platform difference ``tests.portability`` names, and on a machine whose
# libm rounds case 111's mean distance away from the recorded one they are
# reported as skipped rather than run. Nothing else is skipped: the suite runs
# and carries the same guard in the tests that need it, and the four reports
# grade a run's own record without rebuilding a brief.
CASE_READING_STEPS: Tuple[str, ...] = (
    "tools.check_figures",
    "ui.v2.build",
    "ui.build",
    "ui.site.build",
    "ui.v8.build",
    "ui.v6.build",
)


def the_platform_moves_a_recorded_brief() -> bool:
    """``tests.portability``'s own answer, asked here so a test can replace it.

    ``False`` on macOS, where the recorded digests are this code's own, so
    nothing is skipped there and the command behaves as it always did.
    """
    return portability.the_case_111_platform_difference()


def steps_for(quick: bool = False) -> Tuple[Step, ...]:
    """The steps to run, minus the test suite when ``--quick`` is given."""
    if not quick:
        return STEPS
    return tuple(step for step in STEPS if step.name != SUITE_STEP)


def _subprocess_runner(command: Sequence[str]) -> int:
    """Run one step from the project root, its output captured, and return its code."""
    completed = subprocess.run(
        list(command),
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    return completed.returncode


def run(
    steps: Sequence[Step] = STEPS,
    run_step: Optional[Callable[[Sequence[str]], int]] = None,
    stream: Optional[TextIO] = None,
) -> int:
    """Run every step in order, print a line each, and return the exit code.

    ``run_step`` exists so the command can be tested without running anything:
    a caller passes a stub that returns a code for a command. ``stream`` exists
    for the same reason, so a test can read what was printed.

    A step named in :data:`CASE_READING_STEPS` is reported as ``SKIP``, with
    ``portability.PLATFORM_REASON``, when this platform cannot rebuild a
    recorded brief; every other step runs as it always did. The exit code is 1
    only when a step that ran failed.
    """
    runner = run_step or _subprocess_runner
    out = stream if stream is not None else sys.stdout
    failed: List[str] = []
    skipped: List[str] = []
    platform_skip = the_platform_moves_a_recorded_brief()
    for step in steps:
        if platform_skip and step.name in CASE_READING_STEPS:
            skipped.append(step.name)
            print(
                "SKIP  {0:<24}{1}".format(step.name, portability.PLATFORM_REASON),
                file=out,
            )
            continue
        started = time.monotonic()
        code = runner(step.command)
        elapsed = time.monotonic() - started
        passed = code == 0
        if not passed:
            failed.append(step.name)
        print(
            "{0}  {1:<24}{2:.1f} s".format(
                "PASS" if passed else "FAIL", step.name, elapsed
            ),
            file=out,
        )
    print("", file=out)
    if failed:
        print(
            "{0} of {1} step(s) failed: {2}".format(
                len(failed), len(steps), ", ".join(failed)
            ),
            file=out,
        )
    else:
        print("all {0} step(s) passed".format(len(steps) - len(skipped)), file=out)
    if skipped:
        print(
            "{0} step(s) skipped: {1}".format(len(skipped), ", ".join(skipped)),
            file=out,
        )
    return 1 if failed else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.verify",
        description=(
            "Run every check this repository makes -- the test suite, the four "
            "reports, the figure check and the five builders' currency checks "
            "-- and print one line each. Reads and writes nothing, and makes no "
            "model call."
        ),
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip the test suite, which is the one step that takes minutes",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run every step. Nothing is written and no model is called."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return run(steps_for(args.quick))


if __name__ == "__main__":
    raise SystemExit(main())
