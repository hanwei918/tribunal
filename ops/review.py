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

**No model call, and no answer key.** The packet is rebuilt from the run's own
record and the public case; nothing here reads an answer.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

from ops import escalation
from tribunal import precedents

# A SHA-256 hex digest, as ``hashlib`` writes one.
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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

    forwarded = ["--store", str(args.store)] if args.store is not None else []
    forwarded += ["close", "--run-dir", str(args.run_dir), "--case", str(args.case)]
    forwarded += list(rest)
    return precedents.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
