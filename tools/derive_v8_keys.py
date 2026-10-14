"""Derive a policy-version-8 answer key from the version-7 key it replaces.

Policy version 8 is version 7 with Ryde's answers of 2026-10-14 applied (see
``policy/v8/CHANGES.md``). One of those answers changes outcomes: v2.1 6.2's
2 km limb now applies, so a route deviation of **more than** 2 km is escalated
instead of ruled. That is the whole of this command's work.

**What it reads, and what it writes.** A version-8 set reuses the version-7 case
files -- ``data/external/dev-v8/`` does not exist and neither does
``data/external/ryde-v8/``; each set's ``case_root`` is the version-7 directory
-- so this command reads the version-7 key, that key's case files, and
``policy/v8/route_deviation.json``'s own ceiling, and writes the version-8 key
beside the version-7 one.

**The one rule.** For each entry of the version-7 key: the case is loaded from
the version-7 case root, and where it is a ``ROUTE_DEVIATION`` whose
``TRIP_RECORD`` payload records both distances, the deviation is
``actual_distance_km - optimal_distance_km`` taken in :class:`~decimal.Decimal`
over the recorded figures. Where that is **greater than** the policy's own
``thresholds.ai_ruling_max_deviation_km`` the entry becomes an escalation --
``expected_ruling`` ``"ESCALATE"``, both amount fields ``null``,
``expected_referrals`` ``[]``, ``POL-RD-25`` among its governing clauses -- and
its rationale gains one sentence naming the deviation and the answer. Every other
entry is copied **unchanged**, byte for byte, and no other field of a changed
entry moves either.

The comparison is strict, because the limb is: 6.2 escalates a deviation *over*
2 km, so 2.00 km is still the AI's. The difference is taken in ``Decimal`` so
that a deviation of exactly the ceiling is not turned into an escalation by a
binary floating-point tail.

**The sentence, and the one case it is longer for.** Case 902 is DISP-001, the
organisers' own route-deviation sample. Its case file states an outcome -- an AI
partial refund of 3.44 -- and it is Ryde's answer that supersedes it, so that
one entry's added sentence says so. See :data:`SUPERSEDED_SAMPLE`.

**Standard library only**, and ``Decimal`` for the arithmetic. Nothing here
reaches a model, the network, or a sealed root, and nothing here writes anything
but the two version-8 keys.

Usage::

    python3 -m tools.derive_v8_keys              # write both version-8 keys
    python3 -m tools.derive_v8_keys --check      # compare, write nothing
    python3 -m tools.derive_v8_keys --set dev-v8 --check
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The two version-8 sets, each as ``(name, version-7 key, case root, version-8
# key)``. Every path is the one ``eval/development_sets.py`` registers: ``DEV_V8``
# and ``RYDE_V8`` share the version-7 pair's ``case_root`` and differ from them
# in ``key_path`` alone. ``tests/test_policy_v8.py`` holds this table to those
# registrations, so the two cannot drift apart.
SETS: Tuple[Tuple[str, Path, Path, Path], ...] = (
    (
        "dev-v8",
        PROJECT_ROOT / "eval" / "answers" / "dev-v7" / "answers" / "ground_truth.json",
        PROJECT_ROOT / "data" / "external" / "dev-v7",
        PROJECT_ROOT / "eval" / "answers" / "dev-v8" / "ground_truth.json",
    ),
    (
        "ryde-v8",
        PROJECT_ROOT / "eval" / "answers" / "ryde-v7" / "ground_truth.json",
        PROJECT_ROOT / "data" / "external" / "ryde-v7",
        PROJECT_ROOT / "eval" / "answers" / "ryde-v8" / "ground_truth.json",
    ),
)

# The policy whose ceiling decides which entries move. The file is version 8's
# own, and the ceiling is read out of it rather than typed here: a number in this
# module would be a second copy of the policy's.
LIMIT_POLICY = PROJECT_ROOT / "policy" / "v8" / "route_deviation.json"
LIMIT_PATH: Tuple[str, ...] = ("thresholds", "ai_ruling_max_deviation_km")

# The record's own names, not policy values: the category a case must have for
# the ceiling to reach it, the artifact that carries the distances, and the two
# fields the deviation is taken between.
ROUTE_DEVIATION = "ROUTE_DEVIATION"
TRIP_RECORD = "TRIP_RECORD"
ACTUAL_DISTANCE_KEY = "actual_distance_km"
OPTIMAL_DISTANCE_KEY = "optimal_distance_km"

# The ruling an entry becomes, and the clause the sentence names.
ESCALATE = "ESCALATE"
AI_LIMIT_CLAUSE = "POL-RD-25"

# The key every graded entry hangs its four fields and its rationale under.
GROUND_TRUTH_KEY = "ground_truth"

# One case's added sentence is one sentence longer. 902 is DISP-001, the
# organisers' route-deviation sample: its case file states an outcome -- an AI
# partial refund of 3.44 -- and Ryde's answer of 2026-10-14 is what supersedes
# it. The generic sentence below says the limb applies; this says what that costs
# the outcome the sample itself states. It is the only case in either set whose
# own record states an outcome at all.
SUPERSEDED_SAMPLE: Mapping[int, str] = {
    902: (
        "Ryde's answer supersedes DISP-001's stated outcome (an AI partial "
        "refund of 3.44)."
    ),
}

# The four fields a moved entry's ruling carries, and the clause list it gains.
NULL_AMOUNTS: Mapping[str, Any] = {
    "expected_ruling": ESCALATE,
    "expected_amount_sgd": None,
    "expected_driver_compensation_sgd": None,
    "expected_referrals": [],
}


class DeriveError(Exception):
    """A key this command will not derive from."""


def read_json(path: Path) -> Any:
    """One JSON document, read as text and parsed."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DeriveError("there is no file at {0}".format(path))
    except json.JSONDecodeError as exc:
        raise DeriveError("{0} is not valid JSON: {1}".format(path, exc))


def render(key: Any) -> str:
    """One key written the way the source key is written.

    ``json.dumps`` with a two-space indent and a trailing newline, which is what
    both version-7 keys are: re-rendering an unmodified key through this function
    gives back its own bytes, so a key that changed nothing comes out identical
    and only a moved entry differs.
    """
    return json.dumps(key, indent=2, ensure_ascii=False) + "\n"


def the_ceiling() -> Decimal:
    """``policy/v8/route_deviation.json``'s own ``ai_ruling_max_deviation_km``."""
    node: Any = read_json(LIMIT_POLICY)
    for step in LIMIT_PATH:
        if not isinstance(node, Mapping) or step not in node:
            raise DeriveError(
                "{0} carries no {1}".format(LIMIT_POLICY, ".".join(LIMIT_PATH))
            )
        node = node[step]
    try:
        return Decimal(str(node))
    except Exception as exc:  # noqa: BLE001 - a policy value that is not a number
        raise DeriveError(
            "{0}.{1} is {2!r}, which is not a distance".format(
                LIMIT_POLICY, ".".join(LIMIT_PATH), node
            )
        ) from exc


def the_trip_record(case: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """The case's ``TRIP_RECORD`` payload, or ``None`` where it carries none."""
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("evidence_type") == TRIP_RECORD:
            payload = artifact.get("payload")
            return payload if isinstance(payload, Mapping) else None
    return None


def the_deviation(case_root: Path, case_no: int) -> Optional[Decimal]:
    """``actual_distance_km - optimal_distance_km`` for one case, or ``None``.

    ``None`` where the case is not a route deviation, where its trip record is
    absent, or where either recorded distance is -- which is exactly the set of
    entries that do not move. The two figures are taken as ``Decimal`` of the
    recorded values, so the subtraction is the one POL-RD-22 states rather than a
    binary-float approximation of it.
    """
    path = Path(case_root) / "case-{0:05d}.json".format(case_no)
    case = read_json(path)
    if not isinstance(case, Mapping):
        raise DeriveError("{0} does not hold one case object".format(path))
    dispute = case.get("dispute")
    if not isinstance(dispute, Mapping) or dispute.get("category") != ROUTE_DEVIATION:
        return None
    payload = the_trip_record(case)
    if payload is None:
        return None
    actual = payload.get(ACTUAL_DISTANCE_KEY)
    optimal = payload.get(OPTIMAL_DISTANCE_KEY)
    if actual is None or optimal is None:
        return None
    return Decimal(str(actual)) - Decimal(str(optimal))


def the_sentence(case_no: int, deviation: Decimal) -> str:
    """The sentence one escalated entry's rationale gains."""
    sentence = (
        "Version 8: Ryde answered on 2026-10-14 that v2.1 6.2's 2 km limb "
        "applies; the deviation is {0} km, over 2 km, so the case is escalated "
        "(POL-RD-25).".format(deviation)
    )
    extra = SUPERSEDED_SAMPLE.get(case_no)
    return sentence if extra is None else sentence + " " + extra


def escalate(entry: Mapping[str, Any], deviation: Decimal) -> Dict[str, Any]:
    """One entry as version 8 states it.

    The entry's own keys and their order are kept: each of the four graded fields
    is replaced where it already is, ``governing_clauses`` gains ``POL-RD-25``
    only if it is absent, and the rationale gains its sentence at the end. No key
    is added and none is removed.
    """
    truth = dict(entry[GROUND_TRUTH_KEY])
    truth.update(NULL_AMOUNTS)
    clauses: List[str] = list(truth.get("governing_clauses") or [])
    if AI_LIMIT_CLAUSE not in clauses:
        clauses.append(AI_LIMIT_CLAUSE)
    truth["governing_clauses"] = clauses
    rationale = truth.get("rationale") or ""
    sentence = the_sentence(entry["case_no"], deviation)
    truth["rationale"] = sentence if not rationale else rationale + " " + sentence
    return {**entry, GROUND_TRUTH_KEY: truth}


def derived_key(
    source_key: Sequence[Mapping[str, Any]], case_root: Path, ceiling: Decimal
) -> Tuple[List[Dict[str, Any]], List[Tuple[int, Any, Any]]]:
    """The version-8 key, and the entries that moved.

    Each moved entry is reported as ``(case_no, old ruling, new ruling)`` so a
    caller can print what changed rather than only that something did.
    """
    entries: List[Dict[str, Any]] = []
    moved: List[Tuple[int, Any, Any]] = []
    for entry in source_key:
        case_no = entry["case_no"]
        deviation = the_deviation(case_root, case_no)
        if deviation is None or deviation <= ceiling:
            entries.append(dict(entry))
            continue
        old = (entry[GROUND_TRUTH_KEY] or {}).get("expected_ruling")
        entries.append(escalate(entry, deviation))
        moved.append((case_no, old, ESCALATE))
    return entries, moved


def run_one(name: str, source: Path, case_root: Path, destination: Path, check: bool) -> int:
    """Derive one set's key. Returns 0 when nothing needs writing."""
    ceiling = the_ceiling()
    source_key = read_json(source)
    if not isinstance(source_key, list):
        raise DeriveError("{0} does not hold a list of entries".format(source))
    entries, moved = derived_key(source_key, case_root, ceiling)
    written = render(entries)

    print("{0}: {1} entries from {2}".format(name, len(entries), source))
    for case_no, old, new in moved:
        print("  case {0}: {1} -> {2}".format(case_no, old, new))
    if not moved:
        print("  no entry moves")

    if check:
        committed = destination.read_text(encoding="utf-8") if destination.is_file() else None
        if committed == written:
            print("  {0}: identical".format(destination))
            return 0
        print("  {0}: differs".format(destination))
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(written, encoding="utf-8")
    print("  {0}: written".format(destination))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Derive a policy-version-8 answer key from its version-7 key: a route "
            "deviation over 2 km becomes an escalation."
        )
    )
    parser.add_argument(
        "--set",
        dest="name",
        choices=[name for name, _s, _r, _d in SETS],
        default=None,
        help="one version-8 set; both are derived when none is named",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the written key with what this command would write",
    )
    args = parser.parse_args(argv)

    selected = [row for row in SETS if args.name is None or row[0] == args.name]
    status = 0
    for name, source, case_root, destination in selected:
        status |= run_one(name, source, case_root, destination, args.check)
    return status


if __name__ == "__main__":
    sys.exit(main())
