"""The review step: a closure that cannot be recorded against a packet nobody read.

``python3 -m tribunal.precedents close`` records a human reviewer's decision
about a case. It checks a great deal -- that the brief still rebuilds to the
digest the run recorded, that the ruling is one POL-GEN-03 licenses, that the
reason cites this case's own evidence and the policy's own clauses -- and it
cannot check the one thing this module adds: **that the person deciding read the
packet**.

So this command wraps it with one more requirement, ``--packet-sha256``, and
refuses unless that value is the SHA-256 of the packet
:mod:`ops.escalation` builds for the case **now**. A reviewer who read one packet
and a case whose record has since moved is exactly the failure a hash is for: the
digest a reviewer holds is the packet they read, and the packet rebuilt at
decision time is the packet the decision is about.

**Everything else passes through.** The arguments are ``close``'s own, forwarded
unchanged, and so are its rules: ``--reason``, the ``--supersedes`` override of
an earlier closure, and the ``human_decision`` event the store appends. This
module adds one check and changes nothing else, so a closure made through it is
the closure ``tribunal.precedents`` would have made.

**Who closes.** ``POL-GEN-04`` bars a party from hearing its own appeal, and the
same rule has to hold for a closure: a rider or a driver may not close its own
dispute. So ``--closed-by`` is read out of the forwarded arguments, the case's
rider and driver ``party_id`` are read off its own ``RIDER_PROFILE`` and
``DRIVER_PROFILE`` evidence -- the case file ``ops.escalation`` builds the packet
from -- and a closer who is either is **refused**. The party comparison itself is
``ops.appeal.check_reviewer``'s, asked with no earlier reviews so that the only
limb it can fail on is the party one, rather than a second comparison written
here. A case whose profiles cannot be read is refused rather than passed: an
absent profile is not a person who is not a party.

**No model call, and no answer key.** The packet is rebuilt from the run's own
record and the public case; nothing here reads an answer.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ops import appeal, development_set_for, escalation
from tribunal import loader, precedents

# A SHA-256 hex digest, as ``hashlib`` writes one.
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# The two evidence types that name the case's parties, and the field of each
# payload that carries the party's id.
PROFILE_TYPES: Tuple[str, ...] = ("RIDER_PROFILE", "DRIVER_PROFILE")
PARTY_ID_FIELD = "party_id"


class ReviewError(Exception):
    """The closer cannot be checked: the case's own parties cannot be read."""


def closer_from(arguments: Sequence[str]) -> Optional[str]:
    """``--closed-by`` as the forwarded arguments state it, or ``None``.

    ``close`` requires the argument, so a caller that omits it is refused by
    ``close`` itself; there is simply no closer to test here.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--closed-by", default=None)
    parsed, _rest = parser.parse_known_args(arguments)
    return parsed.closed_by


def party_ids(run_dir: Path, case_no: int) -> Tuple[Any, Any]:
    """The case's rider and driver ``party_id``, off its own profile evidence.

    The case is the one ``ops.escalation.build_packet`` builds the packet from --
    the run's own case file names the set, and the set's loader reads the public
    case -- so the person a closure is refused for is a party of the case the
    reviewer read. A profile that is missing, or that names no ``party_id``, is a
    refusal rather than a pass.
    """
    development_set = development_set_for(run_dir)
    try:
        case = development_set.load_case(case_no)
    except loader.LoaderError as exc:
        raise ReviewError(
            "case {0} of the {1} set cannot be loaded, so its parties cannot be "
            "read: {2}".format(case_no, development_set.name, exc)
        ) from exc

    found: Dict[str, Any] = {}
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        kind = artifact.get("evidence_type")
        if kind not in PROFILE_TYPES:
            continue
        payload = artifact.get("payload")
        party_id = payload.get(PARTY_ID_FIELD) if isinstance(payload, Mapping) else None
        if party_id is not None:
            found[kind] = party_id

    missing = [kind for kind in PROFILE_TYPES if kind not in found]
    if missing:
        raise ReviewError(
            "case {0} carries no {1} evidence naming a {2}, so who is a party to "
            "it cannot be established and the closure is refused".format(
                case_no, " and no ".join(missing), PARTY_ID_FIELD
            )
        )
    return found["RIDER_PROFILE"], found["DRIVER_PROFILE"]


def party_role(closer: Any, rider_id: Any, driver_id: Any) -> Optional[str]:
    """Which party the closer is, by ``ops.appeal``'s own party test.

    ``check_reviewer`` is the one place the comparison lives, so it is asked
    rather than restated: once with the rider alone and once with the driver
    alone, each with no earlier reviews, so the only limb either call can fail on
    is the party one. ``None`` when the closer is neither.
    """
    if not appeal.check_reviewer(closer, None, rider_id, None, ()).result:
        return "rider"
    if not appeal.check_reviewer(closer, None, None, driver_id, ()).result:
        return "driver"
    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Record a reviewer's closure, once the packet digest has been checked."""
    parser = argparse.ArgumentParser(
        prog="python -m ops.review",
        description=(
            "Record a human reviewer's decision about an escalated case, "
            "requiring the digest of the packet they read. Every other argument "
            "is tribunal.precedents close's own and is passed through."
        ),
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="the run directory")
    parser.add_argument("--case", type=int, required=True, help="the case number")
    parser.add_argument(
        "--packet-sha256",
        required=True,
        help=(
            "the sha256 of the case's current JSON packet, printed by "
            "python3 -m ops.escalation"
        ),
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="the store directory, defaulting to the repository's own precedents/",
    )
    args, rest = parser.parse_known_args(argv)

    supplied = args.packet_sha256.strip().lower()
    if not SHA256_RE.match(supplied):
        print(
            "FATAL: --packet-sha256 is not a SHA-256 hex digest: {0!r}".format(
                args.packet_sha256
            ),
            file=sys.stderr,
        )
        return 1

    try:
        packet = escalation.build_packet(args.run_dir, args.case)
    except escalation.EscalationError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1
    rebuilt = escalation.packet_sha256(packet)
    if supplied != rebuilt:
        print(
            "FATAL: the packet for case {0} of {1} is not the packet that was "
            "read: the packet rebuilt now hashes to {2} and {3} was given. "
            "Rebuild the packet with python3 -m ops.escalation and read it "
            "before recording a decision.".format(
                args.case, args.run_dir, rebuilt, supplied
            ),
            file=sys.stderr,
        )
        return 1

    # The digest is checked first, so a reviewer who read one packet and a case
    # whose record has since moved is told about that and not about who they
    # are. Only then is the closer tested against the case's own parties.
    closer = closer_from(rest)
    if closer is not None:
        try:
            rider_id, driver_id = party_ids(args.run_dir, args.case)
        except ReviewError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        role = party_role(closer, rider_id, driver_id)
        if role is not None:
            print(
                "FATAL: the closer {0} is the {1} of this case, and a party may "
                "not close its own dispute (POL-GEN-04)".format(closer, role),
                file=sys.stderr,
            )
            return 1

    forwarded = ["--store", str(args.store)] if args.store is not None else []
    forwarded += ["close", "--run-dir", str(args.run_dir), "--case", str(args.case)]
    forwarded += list(rest)
    return precedents.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
