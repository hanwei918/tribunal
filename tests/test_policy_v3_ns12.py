"""Policy version 6: ``POL-NS-12`` and the registration mask ``POL-GEN-08(4)``.

Two changes ride on base 3's third amendment, ``POL-NS-12`` ("Platform-confirmed
arrival and waiting"), which makes **policy version 6**:

* **The clause's facts.** ``POL-NS-12`` treats a platform-confirmed arrival
  (``trip_record.platform_policy.arrival_marker`` is ``GPS_AUTO``) and the
  platform's own wait-timer events as a carrier independent of the exported
  ``gps_trace``. The three events it reads -- ``driver_arrived``,
  ``wait_timer_started`` and ``wait_timer_expired`` -- are the trip record's own
  ``events[]`` entries, and a version-6 no-show brief already passes that array
  through, so no new block is added: this module **confirms** the pass-through
  with a test for case 901, the only case in the repository that carries the full
  trigger.

* **The registration mask.** ``POL-GEN-08(4)`` says the record shown to advocates,
  judge and reviewers "carries party identifiers, not names, telephone numbers or
  vehicle registration marks; those are masked before display". From **version 6
  only** the brief replaces every match of the Singapore registration pattern
  ``S[A-Z]{1,2}\\s?\\d{1,4}\\s?[A-Z]`` with a fixed placeholder in a chat message's
  ``text``, a trip record's ``events[].detail``, and the dispute's ``claim_text``
  and ``counterparty_statement``. Ids, numbers and every other string are
  untouched, and no case file is changed -- the mask is applied to the brief only.

Versions 1 to 5 keep the bytes they had; ``tests/test_policy_versions.py`` holds
the numbering and the pinned brief digests, and this module holds the facts the
two changes make visible.

No model call is made.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, loader, money  # noqa: E402

VERSION_SIX = 6
VERSION_FIVE = 5

# The three platform events ``POL-NS-12`` reads, in the order the trip records
# them.
PLATFORM_EVENT_TYPES = (
    "driver_arrived",
    "wait_timer_started",
    "wait_timer_expired",
)

# The pattern the brief masks from version 6 (POL-GEN-08(4)). It is written here
# rather than imported, so a test that fails to see a mark is looking for the
# mark itself and not for whatever the module happens to hold.
REGISTRATION_RE = re.compile(r"\bS[A-Z]{1,2}\s?\d{1,4}\s?[A-Z]\b")

# The sets the trigger is checked over: the 200 ``dev-v2`` and ``dev-v2-ext``
# cases the sheet names, and the corpus and the second set, which carry no
# ``events`` at all.
TRIGGER_SET_ROOTS = (
    loader.EXTERNAL_DIR / "dev-v2",
    loader.EXTERNAL_DIR / "dev-v2-ext",
    loader.EXTERNAL_DIR / "codex",
)

# The organisers' sample converted for base 3: the one case with the trigger.
SAMPLE_SET_ROOT = loader.EXTERNAL_DIR / "ryde-v3"
SAMPLE_CASE = 901

# The corpus cases whose chat text carries a Singapore registration mark.
CORPUS_MASKED_CASES = (202, 208, 212)

# The provenance strings the policy text must not carry. ``DISP-002`` is the
# organisers' own dispute id and ``organiser`` names them; ``901`` is the sample's
# case number. They live in the proposal's ``source`` field, which is not copied
# into the clause and so cannot reach a brief.
PROVENANCE_STRINGS = ("DISP-002", "organiser", "901")

# The ids the mask must leave alone.
UNTOUCHED_IDS = ("EV-CHAT-00208", "TRP-00001", "DSP-00001")

# The sets the 2026-10-10 masking disclosure covers, minus the sealed one: the
# corpus (read through the manifest, below) and these three external sets, loaded
# through their own indexes. ``sealed-v1`` is named in the same disclosure and is
# deliberately absent here -- no test in this module opens a sealed case.
DISCLOSURE_SET_ROOTS = (
    loader.EXTERNAL_DIR / "dev-v2",
    loader.EXTERNAL_DIR / "dev-v2-ext",
    loader.EXTERNAL_DIR / "ryde-v3",
)


def trigger_of(case: Any) -> Any:
    """``"GPS_AUTO"`` where a case carries the whole ``POL-NS-12`` trigger, else ``None``.

    The full trigger is three things at once: a platform-confirmed arrival
    marker, an arrival event and an expired wait timer. Any one alone is not the
    clause's case.
    """
    for artifact in case.get("evidence", []):
        if artifact.get("evidence_type") != "TRIP_RECORD":
            continue
        payload = artifact.get("payload") or {}
        platform = payload.get("platform_policy")
        marker = platform.get("arrival_marker") if isinstance(platform, dict) else None
        events = payload.get("events")
        if not isinstance(events, list):
            return None
        types = {
            event.get("event_type")
            for event in events
            if isinstance(event, dict)
        }
        if (
            marker == "GPS_AUTO"
            and "driver_arrived" in types
            and "wait_timer_expired" in types
        ):
            return marker
    return None


def trip_artifact(briefed: Any) -> Any:
    """The trip record artifact of a built brief."""
    for artifact in briefed["case"]["evidence"]:
        if artifact["evidence_type"] == "TRIP_RECORD":
            return artifact
    return None


def registration_marks(node: Any) -> List[str]:
    """Every registration mark in a built brief, found over its canonical bytes."""
    return REGISTRATION_RE.findall(money.dumps_canonical(node))


def keys_named(node: Any, name: str) -> List[str]:
    """Every **key** called ``name`` in a parsed document, by path."""
    found: List[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == name:
                found.append(key)
            found.extend(keys_named(value, name))
    elif isinstance(node, (list, tuple)):
        for value in node:
            found.extend(keys_named(value, name))
    return found


def message_fixture(case_no: int = 208) -> Any:
    """A corpus case whose first chat message carries two registration marks.

    The marks are ``SBA1234X`` (no spaces) and ``SGP 4521 M`` (spaced), and the
    same message carries three ids the mask must not touch. Nothing else about
    the case changes.
    """
    case = loader.load_case(case_no)
    text = "Vehicle SBA1234X and SGP 4521 M; ids {0}.".format(" ".join(UNTOUCHED_IDS))
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == "CHAT_LOG":
            messages = artifact["payload"]["messages"]
            messages[0] = dict(messages[0], text=text)
            break
    return case


def dispute_fixture(case_no: int = 208) -> Any:
    """A corpus case whose dispute free text carries a registration mark."""
    case = loader.load_case(case_no)
    dispute = dict(case["dispute"])
    dispute["claim_text"] = "I was there; the car was SBA1234X at the lobby."
    dispute["counterparty_statement"] = "Their car SJK8842P never came down."
    case["dispute"] = dispute
    return case


def chat_texts(briefed: Any) -> List[str]:
    """Every chat message's text in a built brief."""
    texts = []
    for artifact in briefed["case"]["evidence"]:
        if artifact["evidence_type"] != "CHAT_LOG":
            continue
        for message in artifact["payload"]["messages"]:
            texts.append(message["text"])
    return texts


def disclosure_cases():
    """Every **non-sealed** case the 2026-10-10 disclosure is about, by set name.

    The corpus is read through the manifest -- numbers only -- and the three
    external sets through their own indexes. ``sealed-v1`` is named in the same
    disclosure and is not opened: no sealed case is read here.
    """
    with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
        corpus = json.load(handle)
    for entry in corpus:
        yield "corpus", loader.load_case(entry["case_no"])
    for root in DISCLOSURE_SET_ROOTS:
        for entry in loader.load_external_index(root):
            yield root.name, loader.load_external_set_case(root, entry["case_no"])


# --------------------------------------------------------------------------
# The clause's facts: the trigger, and the events the brief carries
# --------------------------------------------------------------------------
class VersionSixTriggerTests(unittest.TestCase):
    """``POL-NS-12``'s trigger, and the one case that carries it.

    The clause reads three facts at once, so a case with any one of them alone
    is not in its scope. The 200 development cases carry none of the three
    together; the organisers' sample is the only case that carries all three.
    """

    def test_no_development_case_carries_the_trigger(self):
        for root in TRIGGER_SET_ROOTS:
            entries = loader.load_external_index(root)
            with self.subTest(set=root.name, cases=len(entries)):
                for entry in entries:
                    case = loader.load_external_set_case(root, entry["case_no"])
                    self.assertIsNone(
                        trigger_of(case),
                        "case {0} of {1} carries the POL-NS-12 trigger".format(
                            entry["case_no"], root.name
                        ),
                    )

    def test_the_sample_is_the_only_case_with_the_trigger(self):
        case = loader.load_external_set_case(SAMPLE_SET_ROOT, SAMPLE_CASE)
        self.assertEqual("GPS_AUTO", trigger_of(case))


class VersionSixBriefTests(unittest.TestCase):
    """A version-6 brief for the sample: the clause, its events, and no provenance."""

    @classmethod
    def setUpClass(cls):
        cls.case = loader.load_external_set_case(SAMPLE_SET_ROOT, SAMPLE_CASE)
        cls.six = brief.build_brief_for_case(cls.case, policy_version=VERSION_SIX)
        cls.five = brief.build_brief_for_case(cls.case, policy_version=VERSION_FIVE)

    def test_the_brief_carries_pol_ns_12(self):
        ids = [clause["id"] for clause in self.six["policies"]["category"]["clauses"]]
        self.assertIn("POL-NS-12", ids)
        # And version 5 does not, so the assertion is about the new clause rather
        # than about a clause that was always there.
        five_ids = [clause["id"] for clause in self.five["policies"]["category"]["clauses"]]
        self.assertNotIn("POL-NS-12", five_ids)

    def test_the_brief_carries_the_three_platform_events_as_facts(self):
        artifact = trip_artifact(self.six)
        self.assertIsNotNone(artifact)
        # Each event carries its own time, and the artifact carries the evidence
        # id the judge can cite them by.
        self.assertEqual("EV-TRIP-00901", artifact["evidence_id"])
        events = artifact["payload"]["events"]
        by_type = {
            event["event_type"]: event
            for event in events
            if isinstance(event, dict) and "event_type" in event
        }
        for event_type in PLATFORM_EVENT_TYPES:
            with self.subTest(event_type=event_type):
                self.assertIn(event_type, by_type)
                self.assertTrue(by_type[event_type].get("at"))

    def test_the_policy_text_names_no_case_and_carries_no_provenance_key(self):
        """The provenance stays in the proposal's ``source`` field, not the clause."""
        text = money.dumps_canonical(self.six["policies"]).lower()
        for needle in PROVENANCE_STRINGS:
            with self.subTest(needle=needle):
                self.assertNotIn(needle.lower(), text)
        self.assertEqual([], keys_named(self.six["policies"], "sources"))


# --------------------------------------------------------------------------
# The revised wording: the clause states its test in general terms
# --------------------------------------------------------------------------
class VersionSixClauseWordingTests(unittest.TestCase):
    """``POL-NS-12`` states the geofence test in general terms, not the sample's words.

    The first draft quoted the organisers' sample's own arrival-event text as its
    example, which read as fitted to that one case. At the policy owner's request
    the rule now names what the platform's event states -- the distance to the
    pickup point and the speed at the arrival time -- and neither the rule nor the
    notes may carry any of the sample's own words.
    """

    # The sample's own wording and figures: ``Auto-arrival`` and ``Driver GPS
    # within`` are its arrival-event text, ``10m`` and ``0 km/h`` the figures
    # inside it, ``901`` its case number, ``DISP-002`` its dispute id, and
    # ``organiser`` names its authors. Written here rather than imported, so a
    # test that fails to see one is looking for the word itself.
    QUOTED_SAMPLE_STRINGS = (
        "Auto-arrival",
        "Driver GPS within",
        "10m",
        "0 km/h",
        "901",
        "DISP-002",
        "organiser",
    )

    def test_the_clause_rule_and_notes_do_not_quote_the_sample(self):
        loaded = loader.load_policies("NO_SHOW_CHARGE", VERSION_SIX)
        clause = next(
            clause
            for clause in loaded["category"]["clauses"]
            if clause["id"] == "POL-NS-12"
        )
        text = "{0}\n{1}".format(clause["rule"], clause["notes"])
        for needle in self.QUOTED_SAMPLE_STRINGS:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


# --------------------------------------------------------------------------
# POL-GEN-08(4): the registration mask, from version 6 only
# --------------------------------------------------------------------------
class VehicleRegistrationMaskTests(unittest.TestCase):
    """The mask is applied at version 6 and nowhere else, and to nothing else.

    ``POL-GEN-08(4)`` is a general clause, and the brief it governs is the same
    one at every version -- so the mask is gated on the version rather than run
    always, and versions 1 to 5 keep the bytes they had.
    """

    def test_a_version_six_brief_carries_no_registration_mark(self):
        cases = [
            ("corpus", loader.load_case(case_no))
            for case_no in CORPUS_MASKED_CASES
        ]
        cases.append(
            (
                "ryde-v3",
                loader.load_external_set_case(SAMPLE_SET_ROOT, SAMPLE_CASE),
            )
        )
        for name, case in cases:
            with self.subTest(set=name, case_no=case["case_no"]):
                briefed = brief.build_brief_for_case(case, policy_version=VERSION_SIX)
                self.assertEqual([], registration_marks(briefed))

    def test_a_version_five_brief_still_carries_the_mark(self):
        case = loader.load_case(208)
        briefed = brief.build_brief_for_case(case, policy_version=VERSION_FIVE)
        self.assertEqual(["SJK8842P"], registration_marks(briefed))

    def test_the_mask_is_applied_to_a_chat_message(self):
        briefed = brief.build_brief_for_case(
            message_fixture(), policy_version=VERSION_SIX
        )
        text = chat_texts(briefed)[0]
        self.assertNotIn("SBA1234X", text)
        self.assertNotIn("SGP 4521 M", text)
        self.assertIn(brief.VEHICLE_MASK, text)
        # The mask is not applied to the same message at version 5.
        five = brief.build_brief_for_case(message_fixture(), policy_version=VERSION_FIVE)
        self.assertIn("SBA1234X", chat_texts(five)[0])

    def test_the_mask_is_applied_to_the_dispute_free_text(self):
        briefed = brief.build_brief_for_case(
            dispute_fixture(), policy_version=VERSION_SIX
        )
        dispute = briefed["case"]["dispute"]
        self.assertNotIn("SBA1234X", dispute["claim_text"])
        self.assertNotIn("SJK8842P", dispute["counterparty_statement"])
        self.assertIn(brief.VEHICLE_MASK, dispute["claim_text"])

    def test_the_mask_leaves_ids_and_numbers_alone(self):
        briefed = brief.build_brief_for_case(
            message_fixture(), policy_version=VERSION_SIX
        )
        text = chat_texts(briefed)[0]
        for token in UNTOUCHED_IDS:
            with self.subTest(token=token):
                self.assertIn(token, text)
        # The evidence ids of the brief are the case's own, unmasked.
        ids = [artifact["evidence_id"] for artifact in briefed["case"]["evidence"]]
        self.assertEqual(
            [artifact["evidence_id"] for artifact in loader.load_case(208)["evidence"]],
            ids,
        )


# --------------------------------------------------------------------------
# The 2026-10-10 disclosure: the counterparty_statement masking gap
# --------------------------------------------------------------------------
class CounterpartyStatementMaskingDisclosureTests(unittest.TestCase):
    """The masking gap the policy owner reported on 2026-10-10.

    ``POL-GEN-08(4)``'s mask reaches ``dispute.counterparty_statement`` only when
    the field is a **string**, and in every case of this repository that carries
    one it is an **object** (``text``, ``submitted_by``, ``submitted_at``), so its
    ``text`` is never masked. The disclosure says no brief built at version 6 is
    affected, because no case in the corpus, ``dev-v2``, ``dev-v2-ext``, 901 or
    ``sealed-v1`` carries a registration mark there. This class checks that claim
    over every **non-sealed** case; ``sealed-v1`` is named in the same disclosure
    and no sealed case is opened here.
    """

    def test_counterparty_statement_is_an_object_in_every_case_that_has_one(self):
        seen = 0
        for name, case in disclosure_cases():
            statement = case["dispute"].get("counterparty_statement")
            if statement is None:
                continue
            seen += 1
            with self.subTest(set=name, case_no=case["case_no"]):
                self.assertIsInstance(
                    statement,
                    dict,
                    "case {0} of {1} carries a counterparty_statement that is not "
                    "an object".format(case["case_no"], name),
                )
        self.assertGreater(seen, 0, "no case carried a counterparty_statement to check")

    def test_no_version_six_brief_of_the_non_sealed_sets_carries_a_mark(self):
        for name, case in disclosure_cases():
            with self.subTest(set=name, case_no=case["case_no"]):
                briefed = brief.build_brief_for_case(case, policy_version=VERSION_SIX)
                self.assertEqual(
                    [],
                    registration_marks(briefed),
                    "a registration mark survives in the version-6 brief of case "
                    "{0} of {1}".format(case["case_no"], name),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
