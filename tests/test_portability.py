"""``tests/portability``: the two helpers, and what each one must not do.

The helpers exist so that a machine without the repository's git history, or
with a libm that rounds a trigonometric function differently, reports the gap
rather than a red suite. A guard that answered "yes" for everything would make
the suite green everywhere and prove nothing, so each is shown able to answer
both ways on a brief that is not the repository's own:

* a difference of one unit in the last place of ``driver_track.mean_distance_m``
  is the known platform difference;
* a difference of two units is not, and neither is a difference in another
  field, nor a brief that already matches;
* the second difference is named rather than generalised: the one value of the
  one case ``NAMED_PLATFORM_DIFFERENCES`` records is accepted within its own
  bound and nothing else is, so the same path on another case, another path on
  the same case, and one more unit are all refused, and an empty table accepts
  nothing;
* on macOS neither check ever answers "yes" -- the recorded digests were made
  there, so there is nothing to explain -- and the guards therefore never skip.

No model call, no browser, no credential, and nothing here reads a run.
"""

from __future__ import annotations

import copy
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402
from tribunal import brief  # noqa: E402


def synthetic_brief() -> dict:
    """A brief shaped like the real one, holding one mean distance and a field.

    The shape is what the helper looks for -- ``driver_track.mean_distance_m``
    as ``{"value": <float>, ...}`` -- so a synthetic brief exercises the same
    path the repository's does, without reading a case or a run.
    """
    return {
        "driver_track": {
            "mean_distance_m": {"value": 1234.5, "source": "EV-GPS-00001"},
            "fix_count": {"value": 12, "source": "EV-GPS-00001"},
        },
        "dispute": {"claim_text": "the fare is wrong"},
    }


def shifted(brief_object: dict, units: int) -> dict:
    """A copy of the brief with the mean distance moved ``units`` last places."""
    out = copy.deepcopy(brief_object)
    field = out["driver_track"]["mean_distance_m"]
    value = field["value"]
    for _ in range(abs(units)):
        value = math.nextafter(value, math.inf if units > 0 else -math.inf)
    field["value"] = value
    return out


def digest(brief_object: dict) -> str:
    return brief.brief_digest(brief_object)[1]


# The run directory, case number and value path the named table records, written
# here as the sheet writes them rather than read from the table, so a test can
# empty the table and still ask about the same run, case and value. The first
# test below pins them to the table, so the two cannot drift apart.
NAMED_RUN_DIR = "runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash"
NAMED_CASE_NO = 2745
NAMED_PATH_TAIL = ("rider_presence", "min_distance_m", "value")


def named_brief() -> dict:
    """A brief carrying the named value, and a second float for the control.

    The named value sits where the repository's own brief puts it -- under the
    case's first evidence artifact, beside the driver's track -- so the helper
    finds it by the path's tail, which is what the table records, and not by an
    index typed in here.
    """
    return {
        "case": {
            "evidence": [
                {
                    "payload": {
                        "derived": {
                            "rider_presence": {"min_distance_m": {"value": 784.5}},
                            "driver_track": {"mean_distance_m": {"value": 1234.5}},
                        }
                    }
                }
            ]
        },
        "dispute": {"claim_text": "the fare is wrong"},
    }


def named_shifted(brief_object: dict, units: int) -> dict:
    """A copy of the brief with the named value moved ``units`` last places."""
    out = copy.deepcopy(brief_object)
    field = out["case"]["evidence"][0]["payload"]["derived"]["rider_presence"][
        "min_distance_m"
    ]
    value = field["value"]
    for _step in range(abs(units)):
        value = math.nextafter(value, math.inf if units > 0 else -math.inf)
    field["value"] = value
    return out


class TheKnownPlatformDifferenceTests(unittest.TestCase):
    """One unit in the last place is recognised; anything else is not."""

    def test_one_unit_in_the_last_place_is_recognised(self):
        built = synthetic_brief()
        recorded = digest(shifted(built, 1))
        with mock.patch.object(sys, "platform", "linux"):
            self.assertTrue(
                portability.known_platform_difference(built, recorded),
                "a one-unit difference in the last place was not recognised",
            )

    def test_a_difference_of_two_units_is_not(self):
        built = synthetic_brief()
        recorded = digest(shifted(built, 2))
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(
                portability.known_platform_difference(built, recorded),
                "a two-unit difference was taken for the platform's",
            )

    def test_a_difference_in_another_field_is_not(self):
        built = synthetic_brief()
        other = copy.deepcopy(built)
        other["dispute"]["claim_text"] = "the fare is wrong, and so is the wait"
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(
                portability.known_platform_difference(built, digest(other)),
                "a difference outside mean_distance_m was taken for the platform's",
            )

    def test_a_brief_that_already_matches_is_not_a_difference(self):
        built = synthetic_brief()
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(portability.known_platform_difference(built, digest(built)))

    def test_on_macos_the_helper_never_answers_yes(self):
        """The recorded digests were made on macOS, so nothing needs explaining."""
        built = synthetic_brief()
        recorded = digest(shifted(built, 1))
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertFalse(portability.known_platform_difference(built, recorded))

    def test_the_guard_the_suite_calls_never_skips_on_macos(self):
        """The one guard every case-111 test calls, asked on this platform.

        On macOS it is a no-op: the recorded digests are this code's own, so no
        test is told to skip. On another platform the same call would skip, and
        ``test_the_guard_skips_when_the_difference_is_present`` shows the
        mechanism that decides it.
        """
        with mock.patch.object(sys, "platform", "darwin"):
            portability.require_the_same_libm()


class TheNamedPlatformDifferenceTests(unittest.TestCase):
    """The second difference is one named value of one case, and nothing wider.

    Each test asks about the value the table records, and the refusals are the
    point: the same path on another case, another path on the same case, one
    more unit, and an empty table all reproduce nothing.
    """

    def test_the_table_names_exactly_the_one_case_the_sheet_names(self):
        """The one entry, so a widened table is a failure here and not a shrug."""
        self.assertEqual(
            (
                (
                    "runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash",
                    2745,
                    ("rider_presence", "min_distance_m", "value"),
                    2,
                ),
            ),
            portability.NAMED_PLATFORM_DIFFERENCES,
            "the table of named platform differences is not the one the sheet names",
        )

    def test_two_units_in_the_last_place_of_the_named_value_is_accepted(self):
        built = named_brief()
        recorded = digest(named_shifted(built, 2))
        with mock.patch.object(sys, "platform", "linux"):
            self.assertTrue(
                portability.named_platform_difference(
                    NAMED_RUN_DIR, NAMED_CASE_NO, built, recorded
                ),
                "the named value moved two units in the last place was not accepted",
            )

    def test_three_units_in_the_last_place_is_not_accepted(self):
        built = named_brief()
        recorded = digest(named_shifted(built, 3))
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(
                portability.named_platform_difference(
                    NAMED_RUN_DIR, NAMED_CASE_NO, built, recorded
                ),
                "a three-unit difference was taken for the named one",
            )

    def test_the_same_path_on_another_case_is_not_accepted(self):
        built = named_brief()
        recorded = digest(named_shifted(built, 2))
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(
                portability.named_platform_difference(
                    NAMED_RUN_DIR, NAMED_CASE_NO + 1, built, recorded
                ),
                "a case the table does not name was accepted",
            )

    def test_another_path_on_the_named_case_is_not_accepted(self):
        built = named_brief()
        other = named_shifted(built, 2)
        field = other["case"]["evidence"][0]["payload"]["derived"]["driver_track"][
            "mean_distance_m"
        ]
        field["value"] = math.nextafter(field["value"], math.inf)
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(
                portability.named_platform_difference(
                    NAMED_RUN_DIR, NAMED_CASE_NO, built, digest(other)
                ),
                "a value the table does not name was accepted",
            )

    def test_on_macos_nothing_is_accepted(self):
        built = named_brief()
        recorded = digest(named_shifted(built, 2))
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertFalse(
                portability.named_platform_difference(
                    NAMED_RUN_DIR, NAMED_CASE_NO, built, recorded
                ),
                "the named difference was accepted on the platform that recorded it",
            )

    def test_the_table_is_what_accepts_it(self):
        """The control: with the table emptied, the two-unit acceptance goes."""
        built = named_brief()
        recorded = digest(named_shifted(built, 2))
        with mock.patch.object(portability, "NAMED_PLATFORM_DIFFERENCES", ()):
            with mock.patch.object(sys, "platform", "linux"):
                self.assertFalse(
                    portability.named_platform_difference(
                        NAMED_RUN_DIR, NAMED_CASE_NO, built, recorded
                    ),
                    "the two-unit acceptance survived an empty table, so the "
                    "table is not what accepts it",
                )


class TheShiftedCasesTests(unittest.TestCase):
    """The entry point the tests use: which cases of a run the platform moved."""

    def a_run(self, root: Path, entries) -> Path:
        run_dir = Path(root) / "run"
        run_dir.mkdir()
        for case_no, recorded in entries:
            (run_dir / "case-{0:05d}.json".format(case_no)).write_text(
                '{{"case_no": {0}, "brief_sha256": "{1}"}}'.format(case_no, recorded),
                encoding="utf-8",
            )
        return run_dir

    def test_a_case_the_platform_moved_is_named(self):
        built = synthetic_brief()
        recorded = digest(shifted(built, 1))
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.a_run(Path(tmp), [(101, digest(built)), (111, recorded)])
            with mock.patch.object(sys, "platform", "linux"):
                shifted_cases = portability.the_platform_shifted_cases(
                    run_dir, [101, 111], lambda case_no: built
                )
        self.assertEqual([111], shifted_cases)

    def test_on_macos_no_case_is_named_and_the_guard_never_skips(self):
        built = synthetic_brief()
        recorded = digest(shifted(built, 1))
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.a_run(Path(tmp), [(111, recorded)])
            with mock.patch.object(sys, "platform", "darwin"):
                shifted_cases = portability.the_platform_shifted_cases(
                    run_dir, [111], lambda case_no: built
                )
                # The guard the tests call is shown not to skip here.
                portability.skip_for_the_platform_difference(shifted_cases)
        self.assertEqual([], shifted_cases)

    def test_the_guard_skips_when_the_difference_is_present(self):
        with self.assertRaises(unittest.SkipTest) as caught:
            portability.skip_for_the_platform_difference([111])
        self.assertIn("case 111", str(caught.exception))


class TheGitHistoryHelperTests(unittest.TestCase):
    """The history is asked for with one command, and its absence is named."""

    def test_a_succeeding_rev_parse_is_read_as_history(self):
        done = mock.Mock(returncode=0, stdout="/somewhere/repo\n", stderr="")
        with mock.patch.object(portability.subprocess, "run", return_value=done):
            self.assertTrue(portability.git_history_available())
            portability.require_git_history()

    def test_a_failing_rev_parse_is_read_as_no_history(self):
        done = mock.Mock(returncode=128, stdout="", stderr="not a git repository")
        with mock.patch.object(portability.subprocess, "run", return_value=done):
            self.assertFalse(portability.git_history_available())
            with self.assertRaises(unittest.SkipTest) as caught:
                portability.require_git_history()
        self.assertEqual(portability.GIT_HISTORY_REASON, str(caught.exception))

    def test_a_missing_git_command_is_read_as_no_history(self):
        with mock.patch.object(
            portability.subprocess, "run", side_effect=FileNotFoundError("git")
        ):
            self.assertFalse(portability.git_history_available())
            with self.assertRaises(unittest.SkipTest):
                portability.require_git_history()


if __name__ == "__main__":
    unittest.main()
