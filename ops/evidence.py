"""The collector: one dispute's evidence, fetched from the mocked source systems.

The stretch goal is an "Evidence Collection Agent" that "autonomously
orchestrates multi-modal data retrieval across all tools and APIs, feeding
structured evidence to the advocate agents". This module is the deterministic
half of that: it is given **only the dispute object**, asks the adapters in
:mod:`ops.sources` for what the trip and the parties have, and returns the
artifacts in the order every case file files them.

**What it reads, and what it must not.** It reads the dispute's ``trip_id`` and
nothing else from the dispute. It does **not** read ``dispute.evidence_ids``:
the list of artifacts a case is supposed to have is not an instruction to the
collector, it is the thing the collector is checked against, and a collector that
read it would be fetching what it was told to fetch rather than what the sources
hold. :func:`check` is the only place the list is read, and it runs afterwards.

**The order of the lookups.** The trip first, because the rider and driver ids
come off the trip record; then the telemetry, the chat, the payments, the two
profiles and the advisories. The order of the *result* is the order every case
file uses -- trip record, GPS trace, chat log, fare breakdown, rider profile,
driver profile, traffic advisories -- with the artifacts of one type sorted by
``evidence_id``. That is not a convention this module chose: it is the order the
129 committed case files are written in, and it is what makes the collection
equal to the ``evidence`` array it came from.

**Every call carries the trip.** The two profile lookups are keyed by party id,
and a party id is not unique across a case root: three disputes of the collusion
set are between the same rider and the same driver. Every call therefore passes
the dispute's ``trip_id`` to the adapter, which keeps a party answer to that
trip's artifacts. Without it a case would collect the other cases' profiles as
well as its own, which is a collection that is not the case's.

**The retrieval log.** One entry per call, in the order the calls were made: the
service, the key, and the artifact ids it returned. A call that found nothing is
in the log with an empty answer, because "the advisory feed holds nothing for
this trip" is a fact about the collection and not an absence of one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from ops import OpsError
from ops.sources import EVIDENCE_ORDER, SourceError, SourceSystems
from tribunal import loader

# Where a case is read from when the caller names a number rather than a file.
DEFAULT_CASE_ROOT = Path(loader.CASES_DIR)


class EvidenceError(OpsError):
    """A collection could not be made: no trip, no parties, or no case."""


class Retrieval(NamedTuple):
    """One call to one source system."""

    service: str
    key: Optional[str]
    artifact_ids: Tuple[str, ...]


class Collection(NamedTuple):
    """What the collector found, and how it found it."""

    artifacts: Tuple[Mapping[str, Any], ...]
    log: Tuple[Retrieval, ...]

    @property
    def artifact_ids(self) -> Tuple[str, ...]:
        return tuple(_evidence_id(artifact) for artifact in self.artifacts)


class Check(NamedTuple):
    """What the collector found against what the dispute lists."""

    listed: Tuple[str, ...]
    found: Tuple[str, ...]
    missing: Tuple[str, ...]
    unlisted: Tuple[str, ...]
    same_order: bool

    @property
    def agrees(self) -> bool:
        return not self.missing and not self.unlisted and self.same_order


def _evidence_id(artifact: Mapping[str, Any]) -> str:
    return str(artifact.get("evidence_id"))


def _rank(artifact: Mapping[str, Any]) -> int:
    evidence_type = artifact.get("evidence_type")
    if evidence_type in EVIDENCE_ORDER:
        return EVIDENCE_ORDER.index(evidence_type)
    # An artifact of a type this module does not know sorts last rather than
    # being dropped: a collection that silently lost one would compare equal to
    # a case that had lost it too.
    return len(EVIDENCE_ORDER)


def order(artifacts: Sequence[Mapping[str, Any]]) -> Tuple[Mapping[str, Any], ...]:
    """The artifacts in the order every case file files them."""
    return tuple(sorted(artifacts, key=lambda artifact: (_rank(artifact), _evidence_id(artifact))))


def _party_ids(trip_records: Sequence[Mapping[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """The rider and driver ids off the trip record.

    The trip record is where they are: a profile carries its own ``party_id``,
    but which parties this trip is about is a fact about the trip.
    """
    for artifact in trip_records:
        payload = artifact.get("payload")
        if isinstance(payload, Mapping):
            return payload.get("rider_id"), payload.get("driver_id")
    return None, None


def collect(dispute: Mapping[str, Any], systems: SourceSystems) -> Collection:
    """Fetch one dispute's evidence from the source systems.

    ``dispute`` is read for its ``trip_id`` and nothing else -- in particular
    ``evidence_ids`` is never read here, and a test asserts it by making the
    dispute refuse that key.

    Every call is scoped to ``trip_id``, which is what keeps the two
    party-keyed profile lookups from answering with another case's profiles
    when two cases share a party.

    Raises:
        EvidenceError: the dispute names no trip, the trip record is not in the
            index, or the trip record names no party to look a profile up by.
    """
    trip_id = dispute.get("trip_id")
    if not isinstance(trip_id, str) or not trip_id:
        raise EvidenceError("the dispute names no trip_id to look the trip up by")

    log: List[Retrieval] = []
    found: List[Mapping[str, Any]] = []

    trip = systems.trip.fetch(trip_id, trip_id)  # the key and the scope are one trip
    log.append(Retrieval(systems.trip.name, trip_id, tuple(_evidence_id(a) for a in trip)))
    if not trip:
        raise EvidenceError(
            "no trip record for {0} in the index the {1} reads".format(
                trip_id, systems.trip.name
            )
        )
    found.extend(trip)
    rider_id, driver_id = _party_ids(trip)

    calls = (
        (systems.telemetry, trip_id),
        (systems.chat, trip_id),
        (systems.payments, trip_id),
        (systems.profiles, rider_id),
        (systems.profiles, driver_id),
        (systems.advisories, trip_id),
    )
    for adapter, key in calls:
        if not isinstance(key, str) or not key:
            raise EvidenceError(
                "the {0} is looked up by {1}, and the trip record names none".format(
                    adapter.name, adapter.key_kind
                )
            )
        answer = adapter.fetch(key, trip_id)
        log.append(Retrieval(adapter.name, key, tuple(_evidence_id(a) for a in answer)))
        found.extend(answer)

    return Collection(artifacts=order(found), log=tuple(log))


def check(collection: Collection, dispute: Mapping[str, Any]) -> Check:
    """What was found against what the dispute lists.

    This is the only place ``dispute.evidence_ids`` is read. It runs after the
    collection, so the list cannot have decided what was fetched.
    """
    listed = tuple(str(item) for item in (dispute.get("evidence_ids") or []))
    found = collection.artifact_ids
    return Check(
        listed=listed,
        found=found,
        missing=tuple(item for item in listed if item not in found),
        unlisted=tuple(item for item in found if item not in listed),
        same_order=listed == found,
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render(collection: Collection, result: Check, case_root: Path) -> str:
    """The retrieval log, then the found-versus-listed check."""
    lines: List[str] = [
        "case root: {0}".format(case_root),
        "retrieval log: {0} call(s), {1} artifact(s)".format(
            len(collection.log), len(collection.artifacts)
        ),
    ]
    for entry in collection.log:
        lines.append(
            "  {0:<18} key={1:<14} -> {2}".format(
                entry.service,
                entry.key if entry.key is not None else "-",
                ", ".join(entry.artifact_ids) if entry.artifact_ids else "(nothing)",
            )
        )
    lines.append("collected: {0}".format(", ".join(collection.artifact_ids) or "(nothing)"))
    if result.agrees:
        lines.append(
            "found-versus-listed: agree ({0} listed, {1} found, same order)".format(
                len(result.listed), len(result.found)
            )
        )
        return "\n".join(lines) + "\n"

    lines.append("found-versus-listed: DISAGREE")
    if result.missing:
        lines.append("  listed but not found: {0}".format(", ".join(result.missing)))
    if result.unlisted:
        lines.append("  found but not listed: {0}".format(", ".join(result.unlisted)))
    if not result.same_order and not result.missing and not result.unlisted:
        lines.append("  the same artifacts in a different order")
        lines.append("    found:  {0}".format(", ".join(result.found)))
        lines.append("    listed: {0}".format(", ".join(result.listed)))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def _load(case: Optional[int], case_file: Optional[Path]) -> Tuple[Mapping[str, Any], Path]:
    """``(case, case root)`` for one invocation.

    ``--case`` reads the corpus through the manifest and indexes
    ``data/cases/``; ``--case-file`` reads one converted case and indexes the
    directory it sits in, which is the set's own root.
    """
    if case is not None:
        return loader.load_case(case), DEFAULT_CASE_ROOT
    path = Path(case_file).resolve()
    return loader.load_external_case(path), path.parent


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Collect one case's evidence and print how it was collected."""
    parser = argparse.ArgumentParser(
        prog="python -m ops.evidence",
        description=(
            "Collect one case's evidence from the mocked source systems over an "
            "index of its case root, print the retrieval log and the "
            "found-versus-listed check. Reads only; makes no model call and "
            "writes nothing."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--case", type=int, help="a corpus case number")
    source.add_argument("--case-file", type=Path, help="one converted case file")
    args = parser.parse_args(argv)

    try:
        case, case_root = _load(args.case, args.case_file)
        systems = SourceSystems.over(case_root)
        collection = collect(case["dispute"], systems)
        result = check(collection, case["dispute"])
    except (EvidenceError, SourceError, loader.LoaderError) as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    sys.stdout.write(render(collection, result, case_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
