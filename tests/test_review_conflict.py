"""A closer who is a party to the case is refused, as a reviewer of an appeal is.

``ops/appeal.py``'s ``check_reviewer`` already refuses an appeal heard by a
reviewer who reviewed the trip before, or who is its rider or driver
(``POL-GEN-04``). ``ops/review.py`` -- the command that records a closure of an
escalated case -- checked the packet digest but not **who** closes, so a rider or
a driver could close its own dispute.

This module holds the new check to four things, over a temporary store that is
never the repository's own ``precedents/``:

* a closer whose id is the case's rider is refused with exit 1, and the message
  names the rider and cites ``POL-GEN-04``;
* the same for a closer whose id is the driver;
* the store is unchanged after each refusal;
* a closer who is neither is **not** refused by this check -- it may still fail
  on ``close``'s own rules, so only the party message is asserted absent.

The second-review rule the appeal layer already enforces is covered by
``tests/test_ops_appeal.py``'s
``TheReviewerTests.test_a_reviewer_who_reviewed_the_trip_before_is_refused``;
this module is only about the party limb.

**What it reads.** The corpus run under ``runs/policy-v6/``, the public case file
behind it, and a temporary directory. No model call is made, no network is
reached, and nothing here writes outside the temporary store.

Run from the project root with::

    python -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import development_set_for, escalation, review  # noqa: E402

RUN_DIR = PROJECT_ROOT / "runs" / "policy-v6" / "deepseek-deepseek-flash"

# The corpus case the other review tests use: it escalated, so a packet is built
# for it, and its two profile artifacts name its rider and its driver.
CASE = 207

# The two evidence types that name the case's parties.
PROFILE_TYPES: Tuple[str, ...] = ("RIDER_PROFILE", "DRIVER_PROFILE")

# The closure's own arguments, which are ``tribunal.precedents close``'s. The
# reason cites this case's own evidence id and a clause its policy carries.
RULING = "NO_ACTION"
CLAUSE = "POL-NS-01"
SUMMARY = "The fee stands on the record as it is."
REASON = "Reviewed the packet; the fee stands under POL-NS-01 on EV-FARE-00207."

# The party message's own words, and the two the sheet names.
PARTY_PHRASE = "may not close its own dispute"


def run_command(arguments: Sequence[str]) -> Tuple[int, str, str]:
    """One command's ``main``, with both streams captured."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = review.main(list(arguments))
    return code, stdout.getvalue(), stderr.getvalue()


def case_parties(case_no: int) -> Mapping[str, Any]:
    """The case's profile payloads, read off its own evidence.

    Read here rather than asked of ``ops.review``, so the ids the test refuses
    are the case file's own and not the module's reading of it.
    """
    case = development_set_for(RUN_DIR).load_case(case_no)
    found: dict = {}
    for artifact in case.get("evidence") or []:
        kind = artifact.get("evidence_type")
        if kind in PROFILE_TYPES:
            found[kind] = (artifact.get("payload") or {}).get("party_id")
    return found


def arguments(digest: str, store: Path, closed_by: str) -> List[str]:
    """A review command for the case, with the closer named."""
    return [
        "--run-dir", str(RUN_DIR),
        "--case", str(CASE),
        "--packet-sha256", digest,
        "--store", str(store),
        "--ruling", RULING,
        "--clause", CLAUSE,
        "--closed-by", closed_by,
        "--summary", SUMMARY,
        "--reason", REASON,
    ]


class ThePartyCloserIsRefusedTests(unittest.TestCase):
    """A rider or a driver may not close its own dispute (POL-GEN-04)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Path(self._tmp.name) / "precedents"
        parties = case_parties(CASE)
        self.rider = parties["RIDER_PROFILE"]
        self.driver = parties["DRIVER_PROFILE"]
        self.assertTrue(self.rider and self.driver, "the case names no parties")
        self.digest = escalation.packet_sha256(escalation.build_packet(RUN_DIR, CASE))

    def test_a_closer_who_is_the_rider_is_refused(self):
        code, _out, err = run_command(arguments(self.digest, self.store, self.rider))
        self.assertEqual(1, code)
        self.assertIn("the closer {0} is the rider of this case".format(self.rider), err)
        self.assertIn(PARTY_PHRASE, err)
        self.assertIn("POL-GEN-04", err)
        self.assertFalse((self.store / "precedents.jsonl").exists())

    def test_a_closer_who_is_the_driver_is_refused(self):
        code, _out, err = run_command(arguments(self.digest, self.store, self.driver))
        self.assertEqual(1, code)
        self.assertIn(
            "the closer {0} is the driver of this case".format(self.driver), err
        )
        self.assertIn(PARTY_PHRASE, err)
        self.assertIn("POL-GEN-04", err)
        self.assertFalse((self.store / "precedents.jsonl").exists())

    def test_the_store_is_unchanged_after_each_refusal(self):
        code, _out, err = run_command(arguments(self.digest, self.store, "a reviewer"))
        self.assertEqual(0, code, err)
        stored = self.store / "precedents.jsonl"
        self.assertTrue(stored.is_file(), "the closure was not stored")
        committed = stored.read_bytes()
        for closer in (self.rider, self.driver):
            with self.subTest(closer=closer):
                code, _out, err = run_command(
                    arguments(self.digest, self.store, closer)
                )
                self.assertEqual(1, code)
                self.assertIn(PARTY_PHRASE, err)
                self.assertEqual(committed, stored.read_bytes())

    def test_a_closer_who_is_not_a_party_is_not_refused_by_this_check(self):
        """It may then succeed or fail on ``close``'s own rules; only the party
        message is asserted absent."""
        _code, _out, err = run_command(arguments(self.digest, self.store, "a reviewer"))
        self.assertNotIn(PARTY_PHRASE, err)
        self.assertNotIn("is the rider of this case", err)
        self.assertNotIn("is the driver of this case", err)


if __name__ == "__main__":
    unittest.main()
