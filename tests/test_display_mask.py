"""The reviewer's packet is masked as the brief is, and the check can fail.

``POL-GEN-08(4)`` says telephone numbers and vehicle registration marks are
"masked before display". At policy version 6 the brief masks them -- and e-mail
addresses -- through ``tribunal.brief._mask_personal_data``, and the case pages
read the brief, so the site shows none. But the escalation packet a human
reviewer reads is built from the public case file, and until part 59 it copied
``claim_text`` and the counterparty statement's ``text`` through **unmasked**:
built for ``pii-v1`` case 3201 with ``--any``, its claim read "... you can call
me on 9912 3456.", and case 3203 showed an e-mail address and a telephone number.

This module holds ``ops.escalation`` to the mask over the eight ``pii-v1`` cases
-- the one case set that carries personal data on purpose, none of it
identifying a real person -- in both renderings the command can produce, and
shows the check is capable of failing.

**What it reads.** The run at
``runs/pii-v1/policy-v6/deepseek-deepseek-flash``, the public case files through
the set's own loader, and the spans the key marks at
``eval/answers/pii-v1/pii_spans.json``. No model call is made, no network is
reached, and nothing here writes.

Run from the project root with::

    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any, List, Mapping, Tuple
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ops import development_set_for, escalation  # noqa: E402

RUN_DIR = PROJECT_ROOT / "runs" / "pii-v1" / "policy-v6" / "deepseek-deepseek-flash"
SPANS_PATH = PROJECT_ROOT / "eval" / "answers" / "pii-v1" / "pii_spans.json"

# The eight cases of the set, and the three span types the mask replaces. The
# key marks eight spans of other types too -- the names -- and those are
# deliberately not masked, so they are not read here.
CASE_NUMBERS: Tuple[int, ...] = tuple(range(3201, 3209))
MASKED_TYPES: Tuple[str, ...] = ("PHONE", "EMAIL", "PLATE")


def span_records() -> Tuple[Mapping[str, Any], ...]:
    """The key's per-case span records. Its last entry names no case."""
    document = json.loads(SPANS_PATH.read_text(encoding="utf-8"))
    return tuple(entry for entry in document if "case_no" in entry)


def spans_for(case_no: int) -> Mapping[str, Any]:
    """One case's ``mask`` and ``do_not_mask`` spans, as the key states them."""
    for entry in span_records():
        if entry["case_no"] == case_no:
            return entry
    raise AssertionError("the key carries no span record for case {0}".format(case_no))


def public_case(case_no: int) -> Mapping[str, Any]:
    """The public case the packet is built from, through the set's own loader."""
    return development_set_for(RUN_DIR).load_case(case_no)


def statement_text(dispute: Mapping[str, Any]) -> str:
    """The counterparty statement's text, whether it is a string or an object."""
    statement = dispute.get("counterparty_statement")
    if isinstance(statement, str):
        return statement
    if isinstance(statement, Mapping):
        return str(statement.get("text") or "")
    return ""


def rendered(case_no: int) -> Tuple[str, str]:
    """One case's packet as its canonical JSON and as its Markdown."""
    packet = escalation.build_packet(RUN_DIR, case_no, any_ruling=True)
    return escalation.render_json(packet), escalation.render_md(packet)


class ThePacketIsMaskedTests(unittest.TestCase):
    """Every span the key marks to mask is gone from the packet."""

    def test_no_masked_phone_email_or_plate_survives(self):
        for case_no in CASE_NUMBERS:
            entry = spans_for(case_no)
            as_json, as_md = rendered(case_no)
            for span in entry["mask"]:
                if span["type"] not in MASKED_TYPES:
                    continue
                with self.subTest(case=case_no, span=span["text"]):
                    self.assertNotIn(
                        span["text"],
                        as_json,
                        "case {0}'s packet JSON still carries the {1} {2!r}".format(
                            case_no, span["type"], span["text"]
                        ),
                    )
                    self.assertNotIn(
                        span["text"],
                        as_md,
                        "case {0}'s packet Markdown still carries the {1} {2!r}".format(
                            case_no, span["type"], span["text"]
                        ),
                    )

    def test_every_kept_span_of_the_claim_and_statement_is_still_there(self):
        for case_no in CASE_NUMBERS:
            entry = spans_for(case_no)
            dispute = public_case(case_no)["dispute"]
            source = "{0}\n{1}".format(
                dispute.get("claim_text") or "", statement_text(dispute)
            )
            as_json, as_md = rendered(case_no)
            for span in entry["do_not_mask"]:
                if span["text"] not in source:
                    continue
                with self.subTest(case=case_no, span=span["text"]):
                    self.assertIn(
                        span["text"],
                        as_json,
                        "case {0}'s packet JSON dropped the kept span {1!r}".format(
                            case_no, span["text"]
                        ),
                    )
                    self.assertIn(
                        span["text"],
                        as_md,
                        "case {0}'s packet Markdown dropped the kept span {1!r}".format(
                            case_no, span["text"]
                        ),
                    )


class TheControlTests(unittest.TestCase):
    """With the mask replaced by the identity, the check above fails."""

    def test_without_the_mask_a_telephone_number_is_found(self):
        found: List[Tuple[int, str]] = []
        with mock.patch.object(escalation, "_mask_personal_data", lambda text: text):
            for case_no in CASE_NUMBERS:
                entry = spans_for(case_no)
                as_json, _as_md = rendered(case_no)
                for span in entry["mask"]:
                    if span["type"] == "PHONE" and span["text"] in as_json:
                        found.append((case_no, span["text"]))
        self.assertTrue(
            found,
            "with the mask replaced by the identity no telephone number was "
            "found, so the check above could not have failed",
        )


if __name__ == "__main__":
    unittest.main()
