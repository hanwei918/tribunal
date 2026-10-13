"""What the suite needs from the machine it runs on, in one place.

Two things a machine other than the author's may not have, and what the suite
does about each. Neither is a defect, and neither may be papered over with a
weaker check: a skip is allowed only where the thing it needs is truly absent,
and it says which thing that is.

**The repository's git history.** A judge may download the repository as a zip
(no ``.git``) or run it where ``git`` is not installed. Twenty-seven tests read
the history: ``git check-ignore`` for the stray-document rules, and ``git
ls-tree``/``git cat-file`` for the held-out run's manifest. Each skips when
``git rev-parse --show-toplevel`` fails from the repository root, naming the
reason, and runs exactly as it did when the history is there.

**The platform's last-place arithmetic.** ``driver_track.mean_distance_m`` is a
mean of distances computed with a trigonometric function, and glibc and macOS
libm disagree in the last bit of it: case 111's brief hashes to a different
digest on Linux than the digest its run recorded on macOS, and the recorded
digests cannot be rebuilt on Linux at all. Every test that rebuilds that brief
and compares the two goes red for a reason that is not a defect, so the tests
that depend on the digest skip, naming case 111 and the one unit in the last
place; the tests that *count* a set of cases count the set the platform can
rebuild and say which case they left out. Anything else -- a difference of two
units, a difference in another field, a rebuilt digest that is not the recorded
one for any other reason -- still fails.

Nothing here changes what a test asserts when its condition holds: the guards
are conditional on exactly the state they name, and a machine that has the
history and the same libm runs the whole suite as it always ran.
"""

from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Callable, Iterator, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# The repository's git history
# --------------------------------------------------------------------------
GIT_HISTORY_REASON = "needs the repository's git history; a zip download has none"


def git_history_available() -> bool:
    """Whether ``git rev-parse --show-toplevel`` works from the repository root.

    ``False`` when there is no ``.git`` -- a zip download -- and ``False`` when
    there is no ``git`` at all, because the command cannot be run either way.
    """
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return done.returncode == 0


def require_git_history() -> None:
    """Skip, naming why, when the repository's history is not there to read.

    The one helper the three modules that read the history share, so the
    condition is asked in one place and the reason is written once.
    """
    if not git_history_available():
        raise unittest.SkipTest(GIT_HISTORY_REASON)


# --------------------------------------------------------------------------
# The platform's last-place arithmetic
# --------------------------------------------------------------------------
PLATFORM_REASON = (
    "case 111's mean_distance_m differs by one unit in the last place between "
    "glibc and macOS libm; the recorded digest was made on macOS"
)

# Where the brief carries the mean distance. It is ``{"value": <float>, ...}``,
# inside the driver's track summary, so the number can be replaced in place
# without rebuilding anything else.
MEAN_DISTANCE_BLOCK = "driver_track"
MEAN_DISTANCE_FIELD = "mean_distance_m"
MEAN_DISTANCE_VALUE = "value"


def _brief_module():
    """``tribunal.brief``, imported on use so the git helper stays light."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from tribunal import brief  # noqa: PLC0415 - imported on use, see above

    return brief


def _loader_module():
    """``tribunal.loader``, imported on use for the same reason."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from tribunal import loader  # noqa: PLC0415 - imported on use, see above

    return loader


def _mean_distance_paths(node: Any, path: Tuple[Any, ...] = ()) -> Iterator[Tuple[Any, ...]]:
    """The path of every ``driver_track.mean_distance_m.value`` in a brief.

    Found by shape rather than by an index typed in here, because a brief's
    evidence list is the case's own and its order is not ours to assume.
    """
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key == MEAN_DISTANCE_BLOCK and isinstance(value, Mapping):
                field = value.get(MEAN_DISTANCE_FIELD)
                if (
                    isinstance(field, Mapping)
                    and isinstance(field.get(MEAN_DISTANCE_VALUE), float)
                ):
                    yield path + (key, MEAN_DISTANCE_FIELD, MEAN_DISTANCE_VALUE)
            yield from _mean_distance_paths(value, path + (key,))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from _mean_distance_paths(value, path + (index,))


def _value_at(node: Any, path: Sequence[Any]) -> Any:
    for step in path:
        node = node[step]
    return node


def _replace(node: Any, path: Sequence[Any], value: Any) -> None:
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value


def known_platform_difference(
    built: Mapping[str, Any],
    recorded_digest: str,
    digest_of: Optional[Callable[[Mapping[str, Any]], Tuple[str, str]]] = None,
) -> bool:
    """Whether ``built`` differs from ``recorded_digest`` by one unit in the last place.

    The question is asked only of a brief whose rebuilt digest is *not* the
    recorded one -- the caller checks that -- and it is answered in two steps:

    * the platform is not macOS (``sys.platform != "darwin"``). On macOS the
      recorded digests were made by this code, so there is nothing to explain
      and the answer is always ``False``;
    * rebuilding the brief with ``driver_track.mean_distance_m`` replaced by the
      value one unit in the last place away -- up or down, since which way the
      two libraries round is not something to assume -- reproduces the recorded
      digest.

    Only when both hold is the difference the known one. A difference of two
    units, or in another field, reproduces nothing and is still a failure.
    """
    if sys.platform == "darwin":
        return False
    if digest_of is None:
        digest_of = _brief_module().brief_digest
    for path in _mean_distance_paths(built):
        value = _value_at(built, path)
        for neighbour in (
            math.nextafter(value, math.inf),
            math.nextafter(value, -math.inf),
        ):
            candidate = copy.deepcopy(built)
            _replace(candidate, path, neighbour)
            if digest_of(candidate)[1] == recorded_digest:
                return True
    return False


def which_float_moved(
    built: Mapping[str, Any],
    recorded_digest: str,
    digest_of: Optional[Callable[[Mapping[str, Any]], Tuple[str, str]]] = None,
    max_ulps: int = 2,
) -> List[Tuple[Tuple[Any, ...], int]]:
    """The float a single last-place move of which reproduces ``recorded_digest``.

    Every float leaf of ``built`` is tried in turn -- the walk is
    :func:`_mean_distance_paths`'s, but for every float rather than the one
    field -- and for each leaf the values up to ``max_ulps`` units in the last
    place away, up and down, are tried one leaf at a time. Each ``(path, ulps)``
    whose single move reproduces the recorded digest is returned, the path as
    the tuple of keys and indices a reader can follow into the JSON; the list is
    empty when no single move does, which is what a difference of two values at
    once, or a change that is not a float, looks like.

    **It decides nothing.** It is a diagnosis written for a failure message and
    is never consulted by a guard or an assertion: the one bounded check is
    :func:`known_platform_difference`, and a caller that wants a decision asks
    that one. A machine whose library arithmetic is the one that recorded the
    digests never needs this at all, and a caller that runs it anyway is asking
    a question for a reader, not for the suite.
    """
    if digest_of is None:
        digest_of = _brief_module().brief_digest

    def float_leaves(
        node: Any, path: Tuple[Any, ...] = ()
    ) -> Iterator[Tuple[Any, ...]]:
        """The path of every float leaf, in ``_mean_distance_paths``'s order."""
        if isinstance(node, Mapping):
            for key, value in node.items():
                yield from float_leaves(value, path + (key,))
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                yield from float_leaves(value, path + (index,))
        elif isinstance(node, float):
            yield path

    moved: List[Tuple[Tuple[Any, ...], int]] = []
    for path in float_leaves(built):
        value = _value_at(built, path)
        for ulps in range(1, max_ulps + 1):
            for direction in (math.inf, -math.inf):
                neighbour = value
                for _step in range(ulps):
                    neighbour = math.nextafter(neighbour, direction)
                candidate = copy.deepcopy(built)
                _replace(candidate, path, neighbour)
                if digest_of(candidate)[1] == recorded_digest:
                    moved.append((path, ulps))
    return moved


def recorded_brief_digest(run_dir: Path, case_no: int) -> Optional[str]:
    """The ``brief_sha256`` a run's own result file records, or ``None``.

    A case whose judge drafts all abstained wrote no result file, so it has no
    recorded digest and no staleness to be read.
    """
    path = Path(run_dir) / "case-{0:05d}.json".format(case_no)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("brief_sha256")


def the_platform_shifted_cases(
    run_dir: Path,
    cases: Sequence[int],
    rebuild: Callable[[int], Mapping[str, Any]],
    digest_of: Optional[Callable[[Mapping[str, Any]], Tuple[str, str]]] = None,
) -> List[int]:
    """The cases of a run whose recorded digest differs only by the last place.

    ``rebuild(case_no)`` builds the brief this code builds now. A case whose
    rebuilt digest already matches is not shifted -- it is not a difference at
    all -- and neither is one whose difference is anything but the one unit in
    the last place of ``driver_track.mean_distance_m``.
    """
    if sys.platform == "darwin":
        return []
    if digest_of is None:
        digest_of = _brief_module().brief_digest
    shifted: List[int] = []
    for case_no in cases:
        recorded = recorded_brief_digest(run_dir, case_no)
        if recorded is None:
            continue
        built = rebuild(case_no)
        if digest_of(built)[1] == recorded:
            continue
        if known_platform_difference(built, recorded, digest_of):
            shifted.append(case_no)
    return shifted


def skip_for_the_platform_difference(shifted: Sequence[int]) -> None:
    """Skip, naming the reason, when the platform difference is present."""
    if shifted:
        raise unittest.SkipTest(PLATFORM_REASON)


# --------------------------------------------------------------------------
# The case the platform moves, as the suite meets it
# --------------------------------------------------------------------------
# The case whose mean distance the two libraries round differently, and the two
# runs that recorded its brief: the version-1 corpus run the viewer draws, and
# the version-6 corpus run the product view draws. Both were made on macOS, so
# on Linux neither digest can be rebuilt -- which is what the guard below asks.
CASE_111 = 111
CASE_111_RUNS = (
    (PROJECT_ROOT / "runs" / "deepseek-deepseek-flash", 1),
    (PROJECT_ROOT / "runs" / "policy-v6" / "deepseek-deepseek-flash", 6),
)


def _rebuild_at(policy_version: int) -> Callable[[int], Mapping[str, Any]]:
    """How to rebuild one case's brief at a policy version, from the repository."""
    brief_module = _brief_module()
    if policy_version == 1:
        return lambda case_no: brief_module.build_brief(case_no)
    loader_module = _loader_module()
    return lambda case_no: brief_module.build_brief_for_case(
        loader_module.load_case(case_no), policy_version=policy_version
    )


def the_case_111_platform_difference() -> bool:
    """Whether case 111's brief cannot be rebuilt as its run recorded it here.

    ``False`` on macOS, where the recorded digests are this code's own, and
    ``False`` when both runs rebuild exactly -- so a machine that can read the
    whole record is never told to skip anything. ``True`` only when a run's
    rebuilt digest differs and the difference is the one unit in the last place
    of ``driver_track.mean_distance_m``.
    """
    if sys.platform == "darwin":
        return False
    for run_dir, policy_version in CASE_111_RUNS:
        recorded = recorded_brief_digest(run_dir, CASE_111)
        if recorded is None:
            continue
        built = _rebuild_at(policy_version)(CASE_111)
        if _brief_module().brief_digest(built)[1] == recorded:
            continue
        if known_platform_difference(built, recorded):
            return True
    return False


def the_cases_the_platform_moves() -> List[int]:
    """The cases a platform difference leaves out of a run's results, by number.

    Empty on a machine that can rebuild every recorded brief, and ``[111]`` on
    one whose ``libm`` rounds case 111's mean distance one unit in the last
    place away from the recorded one. It is read from the same guard that
    decides whether to skip, so a comparison that drops a case drops exactly the
    cases this names: a test that left out anything else would be hiding a case
    it could not explain, and the assertion beside the call is what says so.
    """
    return [CASE_111] if the_case_111_platform_difference() else []


def require_the_same_libm() -> None:
    """Skip, naming the reason, when case 111's brief cannot be rebuilt as recorded.

    The guard the tests that rebuild case 111's brief call. It is conditional on
    exactly the platform difference: a difference in another case, or in another
    field, does not reach it and still fails the test that found it.
    """
    if the_case_111_platform_difference():
        raise unittest.SkipTest(PLATFORM_REASON)

