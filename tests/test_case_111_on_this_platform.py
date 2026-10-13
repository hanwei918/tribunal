"""Case 111 on every platform: the digest rebuilt here, and nothing else moved.

On Linux the tests that rebuild case 111's brief skip (``tests/portability.py``,
``require_the_same_libm``), because glibc and macOS libm round
``driver_track.mean_distance_m`` one unit in the last place apart. A skip says the
difference is the known one only by way of the guard, and nothing **passes** on
Linux to show that this is the *only* difference. This module passes on both
platforms and skips nothing:

* on macOS the rebuilt digest equals the recorded one, exactly;
* elsewhere it either equals it, or the rebuilt brief differs from the recorded
  digest only in ``driver_track.mean_distance_m``, one unit in the last place, and
  the neighbour that reproduces the recorded digest is shown to differ from the
  rebuilt brief at that one path and nowhere else;
* a recorded digest that is missing fails rather than passes;
* the control, on every platform: a *different* float moved by ``1.0`` is accepted
  by neither the exact comparison nor ``known_platform_difference``.

It uses ``tests/portability.py`` as it is and reads the two runs it names. No
model call, no network, no browser.
"""

from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path
from typing import Any, Iterator, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402
from tribunal import brief  # noqa: E402

# The three components of the one path the platform may move, as the helper names
# them, so the test does not restate ``driver_track.mean_distance_m.value``.
MEAN_PATH_TAIL = (
    portability.MEAN_DISTANCE_BLOCK,
    portability.MEAN_DISTANCE_FIELD,
    portability.MEAN_DISTANCE_VALUE,
)


def digest(brief_object: Mapping[str, Any]) -> str:
    """The sha256 a brief digests to, as the contract serialises it."""
    return brief.brief_digest(brief_object)[1]


def leaf_paths(node: Any, path: Tuple[Any, ...] = ()) -> Iterator[Tuple[Any, ...]]:
    """The path of every leaf in a brief, in a fixed walk order."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield from leaf_paths(value, path + (key,))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from leaf_paths(value, path + (index,))
    else:
        yield path


def value_at(node: Any, path: Sequence[Any]) -> Any:
    for step in path:
        node = node[step]
    return node


def replace(node: Any, path: Sequence[Any], value: Any) -> None:
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value


def differences(
    left: Any, right: Any, path: Tuple[Any, ...] = ()
) -> List[Tuple[Any, ...]]:
    """Every path at which two briefs differ, key by key and index by index."""
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        out: List[Tuple[Any, ...]] = []
        for key in set(left) | set(right):
            if key not in left or key not in right:
                out.append(path + (key,))
            else:
                out.extend(differences(left[key], right[key], path + (key,)))
        return out
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        if len(left) != len(right):
            return [path]
        out = []
        for index, (a, b) in enumerate(zip(left, right)):
            out.extend(differences(a, b, path + (index,)))
        return out
    return [] if left == right else [path]


def neighbour_that_reproduces(built: Mapping[str, Any], recorded: str) -> Any:
    """The brief with the mean distance one last place away that digests to ``recorded``.

    ``None`` when no neighbour does, which is the case a caller must not read as
    the known platform difference. Which way the two libraries round is not
    something to assume, so both neighbours are tried.
    """
    for path in portability._mean_distance_paths(built):
        value = value_at(built, path)
        for neighbour in (
            math.nextafter(value, math.inf),
            math.nextafter(value, -math.inf),
        ):
            candidate = copy.deepcopy(built)
            replace(candidate, path, neighbour)
            if digest(candidate) == recorded:
                return candidate
    return None


def first_float_path_not_mean_distance(built: Mapping[str, Any]) -> Any:
    """The path of the first float that is not ``driver_track.mean_distance_m``.

    A float large enough that ``1.0`` is below its last place would leave the
    control's digest unchanged and the control vacuous, so the first float the
    change actually moves is the one taken.
    """
    for path in leaf_paths(built):
        if portability.MEAN_DISTANCE_FIELD in path:
            continue
        value = value_at(built, path)
        if isinstance(value, float) and value + 1.0 != value:
            return path
    return None


class TheCase111DigestTests(unittest.TestCase):
    """The brief rebuilds as its run recorded it, or by the one known last place."""

    def test_a_recorded_digest_exists_for_both_runs(self):
        """A missing result file must fail here, not pass by finding nothing."""
        for run_dir, policy_version in portability.CASE_111_RUNS:
            with self.subTest(run=run_dir.name, policy_version=policy_version):
                self.assertIsNotNone(
                    portability.recorded_brief_digest(run_dir, portability.CASE_111),
                    "{0} records no brief digest for case {1}".format(
                        run_dir, portability.CASE_111
                    ),
                )

    def test_the_rebuilt_brief_matches_or_is_the_known_difference(self):
        for run_dir, policy_version in portability.CASE_111_RUNS:
            with self.subTest(run=run_dir.name, policy_version=policy_version):
                recorded = portability.recorded_brief_digest(
                    run_dir, portability.CASE_111
                )
                self.assertIsNotNone(
                    recorded,
                    "{0} records no brief digest for case {1}".format(
                        run_dir, portability.CASE_111
                    ),
                )
                built = portability._rebuild_at(policy_version)(portability.CASE_111)
                rebuilt = digest(built)
                if sys.platform == "darwin":
                    # The recorded digests were made on macOS, by this code, so
                    # there is nothing to explain: the two are equal.
                    self.assertEqual(
                        recorded,
                        rebuilt,
                        "the brief rebuilt from {0} does not digest to the "
                        "digest its run recorded".format(run_dir),
                    )
                    continue
                if rebuilt == recorded:
                    continue
                self.assertTrue(
                    portability.known_platform_difference(built, recorded),
                    "the brief rebuilt from {0} differs from the recorded digest "
                    "by more than the one known last place".format(run_dir),
                )
                candidate = neighbour_that_reproduces(built, recorded)
                self.assertIsNotNone(
                    candidate,
                    "no one-unit neighbour of {0}'s mean distance reproduces the "
                    "recorded digest".format(run_dir),
                )
                assert candidate is not None
                moved = differences(built, candidate)
                self.assertEqual(
                    1,
                    len(moved),
                    "the platform difference moved more than one value: "
                    "{0}".format(moved),
                )
                self.assertEqual(
                    MEAN_PATH_TAIL,
                    tuple(moved[0][-len(MEAN_PATH_TAIL):]),
                    "the one value the platform moved is not the mean distance's",
                )


class TheControlTests(unittest.TestCase):
    """A different float is accepted by neither comparison, on every platform."""

    def test_a_different_float_is_not_the_platform_difference(self):
        for run_dir, policy_version in portability.CASE_111_RUNS:
            with self.subTest(run=run_dir.name, policy_version=policy_version):
                recorded = portability.recorded_brief_digest(
                    run_dir, portability.CASE_111
                )
                self.assertIsNotNone(
                    recorded,
                    "{0} records no brief digest for case {1}".format(
                        run_dir, portability.CASE_111
                    ),
                )
                built = portability._rebuild_at(policy_version)(portability.CASE_111)
                # A copy: the brief the test above used is never edited.
                changed = copy.deepcopy(built)
                path = first_float_path_not_mean_distance(changed)
                self.assertIsNotNone(
                    path, "the brief carries no float outside the mean distance"
                )
                assert path is not None
                replace(changed, path, value_at(changed, path) + 1.0)
                self.assertNotEqual(
                    recorded,
                    digest(changed),
                    "moving a float that is not the mean distance left the digest "
                    "unchanged, so the control proves nothing",
                )
                self.assertFalse(
                    portability.known_platform_difference(changed, recorded),
                    "a difference outside the mean distance was accepted as the "
                    "platform's",
                )


if __name__ == "__main__":
    unittest.main()
