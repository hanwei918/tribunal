"""Fraud and bad-faith signals, read off the profile counters the policy names.

This is the operations layer's part-1 module. It runs **before and beside the
debate**: its signals go to the human reviewer and to the queue, and never to
the judge. The judge already receives the counters these tests read, in the
brief, and applies the same tests through the policy; a signal produced here is
a second reading of the same fields for a person to look at, not an input to a
ruling.

**POL-GEN-01 forbids a profile from establishing a fact about the trip.** So
nothing here rules on anything. It reports which of five named tests a case
trips, quotes the threshold sentence the policy states for each, and leaves the
judgement to the clause the test belongs to.

**The five tests, and only these five.** Each reads exactly the profile fields
its clause names and no other profile field, and the module is tested twice for
that: once against the declaration below, and once against profile payloads that
record every key they are asked for.

**Version 7 has two tests of its own.** Policy version 7 is Ryde's own Dispute
Resolution Policy v2.1, a separate base whose clause ids start at 21, so none of
the five clauses above exists there and reading a version-7 case with the
version-6 patterns is a refusal. :func:`signals_for` therefore takes the policy
version, and at version 7 reports v2.1's two signals: a fraud flag on either
party (POL-GEN-22, read off both profiles and reported against ``PAIR``) and a
rider with three or more no-show cancellations in the trailing thirty days
(POL-NS-25). The version is a parameter whose default is the version-6 five, so
every caller written before it reads exactly what it read before.

**The reading of POL-NS-09(c).** The clause says the two counters "together
show" the no-show disputes between the same rider and driver in the trailing 90
days. Both counters count the **same disputes**, one from each side, so the
reading taken here is the **larger** of the two: a sum would count every dispute
twice and would trip on a pair that has one dispute from each side. When the two
counters differ, a ``counters_disagree`` note is recorded, because two counts of
one set of events that disagree are themselves worth a reviewer's attention; the
larger is still the figure the test runs on.

The **side** this test is reported against is ``PAIR``. It reads a counter on
each profile, and the clause is about the two parties together rather than about
either one of them, so naming the side that supplied the larger figure would say
the signal is about one party when it is not. The other four tests name a counter
on one profile and are reported against that profile's side.

**The lifetime counters are never read.** ``prior_no_show_flags`` and
``prior_deviation_flags`` are lifetime counters, and the policy names them as
near-synonyms that must not be substituted for the trailing-window counters the
clauses actually name. Reading one where a clause names the other is the
commonest way an adverse finding gets built on reputation without anyone
noticing, and case 208 is the trap in this corpus: its rider carries three
lifetime flags and one trailing-30-day dispute, so the substitution would trip
POL-NS-09(d) where the field the clause names does not.

**Where the thresholds come from.** Each threshold is read out of the loaded
policy: the module matches the sentence the clause states and takes the numbers
out of the match. The sentence is matched as the policy states it, number
included, so a sentence that has moved or whose number has been edited is a
**refusal** rather than a threshold nobody reviewed -- which is the reading
``tribunal.pipeline.confidence_floor`` takes of the confidence floor, tightened
for a layer whose output is a claim about a party rather than a re-read
parameter.

**One flag is not a policy test.** ``repeat_party`` is for a reviewer's
attention only, is labelled as such in the output, and is never presented as a
policy finding. It reads the trip records' party ids, not a profile: the same
``rider_id`` or ``driver_id`` appearing in another dispute of the same case root
within 30 days of this dispute's ``filed_at``. That window is the flag's own and
is not read from the policy, because the flag is not a policy test.

**One case, or a whole root, and text or JSON.** ``--case`` and ``--case-file``
read one case; ``--case-root`` reads every case file in one directory, in
case-number order. ``--json`` prints the same readings as a JSON document
instead of as text -- sorted keys, a fixed key order, and a ``Decimal`` written
as its own literal -- so a caller that is not allowed to import this package can
run it and read its answer rather than restating it. Nothing here opens an
answer key, whichever mode is used.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from tribunal import loader

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class RiskError(Exception):
    """Base class for every failure this module reports."""


class RiskPolicyError(RiskError):
    """A threshold could not be read out of the loaded policy text.

    Raised rather than resolved against a number written here: a threshold that
    fell back to a constant would be a claim about a party built on a figure
    nobody reviewed, which is the failure this layer exists to prevent.
    """


# --------------------------------------------------------------------------
# The thresholds, as the policy states them
# --------------------------------------------------------------------------
# Each pattern matches the **sentence** the clause states, with the numbers
# captured out of it. The number is therefore read from the loaded policy and
# never applied from a constant here; the literal in the pattern is what makes
# the sentence have to be the sentence the policy was reviewed with, so an edit
# to the figure is refused instead of silently changing what trips.
THRESHOLD_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    "POL-RD-06": re.compile(
        r"A pattern is ESTABLISHED when "
        r"driver_profile\.deviation_flags_90d is (?P<min_flags>3) or more, or "
        r"driver_profile\.deviation_flags_90d divided by "
        r"driver_profile\.completed_trips_90d is (?P<min_rate>0\.05) or more with "
        r"completed_trips_90d of at least (?P<min_trips>40)"
    ),
    "POL-RD-08": re.compile(
        r"Where rider_profile\.deviation_claims_60d is (?P<min_claims>4) or more and "
        r"rider_profile\.deviation_claims_60d_substantiated is "
        r"(?P<max_substantiated>1) or fewer"
    ),
    "POL-NS-07": re.compile(
        r"where driver_profile\.no_show_terminations_30d is "
        r"(?P<min_terminations>4) or more AND "
        r"driver_profile\.no_show_terminations_30d divided by "
        r"driver_profile\.completed_trips_30d is greater than (?P<max_rate>0\.08)"
    ),
    "POL-NS-09(c)": re.compile(
        r"rider_profile\.disputes_with_counterparty_90d and "
        r"driver_profile\.disputes_with_counterparty_90d together show "
        r"(?P<min_disputes>2) or more no-show disputes between the same rider and "
        r"driver in the trailing (?P<window_days>90) days"
    ),
    "POL-NS-09(d)": re.compile(
        r"rider_profile\.no_show_disputes_30d is (?P<min_disputes>3) or more"
    ),
}


# The side a signal is reported against. Four of the five clauses name a counter
# on one profile, and the side is that profile's. ``POL-NS-09(c)`` names a
# counter on **each** profile -- the same disputes counted from both sides -- so
# it is reported as ``PAIR``: reporting one of the two would say the signal is
# about a party when the clause is about the two of them.
SIDE_RIDER = "RIDER"
SIDE_DRIVER = "DRIVER"
SIDE_PAIR = "PAIR"
SIDES: Tuple[str, ...] = (SIDE_RIDER, SIDE_DRIVER, SIDE_PAIR)

# The category a clause that belongs to no one category carries. POL-GEN-22 is
# a general clause, and a general test applies to every dispute whatever its
# category; the signal it produces is reported under the case's own category, so
# a reader of the output sees the same word they see on every other line.
GENERAL_CATEGORY = "GENERAL"


class PolicyTest(NamedTuple):
    """One of the five policy tests, as the clause states it."""

    clause: str
    category: str
    side: str
    fields: Tuple[str, ...]


# The five tests, in clause order, each with the side it is reported against --
# ``PAIR`` for the one clause that names a counter on each profile.
POLICY_TESTS: Tuple[PolicyTest, ...] = (
    PolicyTest(
        clause="POL-RD-06",
        category="ROUTE_DEVIATION",
        side=SIDE_DRIVER,
        fields=(
            "driver_profile.deviation_flags_90d",
            "driver_profile.completed_trips_90d",
        ),
    ),
    PolicyTest(
        clause="POL-RD-08",
        category="ROUTE_DEVIATION",
        side=SIDE_RIDER,
        fields=(
            "rider_profile.deviation_claims_60d",
            "rider_profile.deviation_claims_60d_substantiated",
        ),
    ),
    PolicyTest(
        clause="POL-NS-07",
        category="NO_SHOW_CHARGE",
        side=SIDE_DRIVER,
        fields=(
            "driver_profile.no_show_terminations_30d",
            "driver_profile.completed_trips_30d",
        ),
    ),
    PolicyTest(
        clause="POL-NS-09(c)",
        category="NO_SHOW_CHARGE",
        side=SIDE_PAIR,
        fields=(
            "rider_profile.disputes_with_counterparty_90d",
            "driver_profile.disputes_with_counterparty_90d",
        ),
    ),
    PolicyTest(
        clause="POL-NS-09(d)",
        category="NO_SHOW_CHARGE",
        side=SIDE_RIDER,
        fields=("rider_profile.no_show_disputes_30d",),
    ),
)

# The clause that names a counter on each profile and reads the larger of them.
PAIR_CLAUSE = "POL-NS-09(c)"

# --------------------------------------------------------------------------
# The version-7 tests, which are v2.1's own
# --------------------------------------------------------------------------
# Policy version 7 is Ryde's own Dispute Resolution Policy v2.1, a separate base
# whose clause ids start at 21. None of the five version-6 clauses above exists
# there, so a version-7 case read with the version-6 patterns is a refusal --
# which is what ``POL-RD-06``'s absence produced before this table existed, and
# what broke ``ops.queue``. v2.1 has two signals of its own, and they are read
# here the way the five are: the sentence is matched as the clause states it,
# number included, and a sentence that has moved is a refusal rather than a
# threshold nobody reviewed.
V7_SIGNALS_VERSION = 7

V7_THRESHOLD_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    "POL-GEN-22": re.compile(
        r"Where either party's profile carries fraud_flags of "
        r"(?P<min_flags>1) or more"
    ),
    "POL-NS-25": re.compile(
        r"rider_profile\.no_show_cancellations_30d, counting this trip if its fee "
        r"stands, is (?P<min_cancellations>3) or more"
    ),
}

# The two tests, in clause order. POL-GEN-22 is general -- it applies to a
# dispute of either category, and the counter it reads is on each profile, so it
# is reported against ``PAIR`` as POL-NS-09(c) is. POL-NS-25 names one counter
# on the rider's profile.
V7_FRAUD_CLAUSE = "POL-GEN-22"
V7_REPEAT_NO_SHOW_CLAUSE = "POL-NS-25"

V7_POLICY_TESTS: Tuple[PolicyTest, ...] = (
    PolicyTest(
        clause=V7_FRAUD_CLAUSE,
        category=GENERAL_CATEGORY,
        side=SIDE_PAIR,
        fields=(
            "rider_profile.fraud_flags",
            "driver_profile.fraud_flags",
        ),
    ),
    PolicyTest(
        clause=V7_REPEAT_NO_SHOW_CLAUSE,
        category="NO_SHOW_CHARGE",
        side=SIDE_RIDER,
        fields=("rider_profile.no_show_cancellations_30d",),
    ),
)

# Which clause a test's sentence lives in. Four tests are a whole clause; the two
# limbs of POL-NS-09 are limbs of one clause, and the sentence each reads is a
# span of that clause's single rule text. The test id is what the output names --
# it is the limb a reviewer is being pointed at -- and the clause id is what the
# loaded policy is keyed by.
THRESHOLD_SOURCES: Dict[str, str] = {
    "POL-NS-09(c)": "POL-NS-09",
    "POL-NS-09(d)": "POL-NS-09",
}

# The two profile artifacts, by the prefix a field path carries.
PROFILE_TYPES: Dict[str, str] = {
    "rider_profile": "RIDER_PROFILE",
    "driver_profile": "DRIVER_PROFILE",
}

# The attention flag. Not a policy test, and labelled so wherever it is printed.
REPEAT_PARTY_FLAG = "repeat_party"
REPEAT_PARTY_LABEL = "for a reviewer's attention only, and not a policy test"
REPEAT_PARTY_WINDOW_DAYS = 30
TRIP_EVIDENCE_TYPE = "TRIP_RECORD"


# --------------------------------------------------------------------------
# Reading the policy
# --------------------------------------------------------------------------
def policy_clauses(policies: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    """Every clause the loaded policies carry, by clause id."""
    found: Dict[str, Mapping[str, Any]] = {}
    for policy in policies.values():
        if not isinstance(policy, Mapping):
            continue
        for clause in policy.get("clauses") or []:
            if isinstance(clause, Mapping) and isinstance(clause.get("id"), str):
                found[clause["id"]] = clause
    return found


def source_clause(test_clause: str) -> str:
    """The clause id the loaded policy carries a test's sentence under."""
    return THRESHOLD_SOURCES.get(test_clause, test_clause)


def clause_rule_text(test_clause: str, policies: Mapping[str, Any]) -> str:
    """The ``rule`` text a test's threshold sentence is quoted from.

    ``test_clause`` is a test id -- ``POL-NS-09(c)`` names a limb of
    ``POL-NS-09`` -- and the clause it resolves to is what the policy is keyed
    by. A test whose clause the policy does not carry is refused here.
    """
    clause_id = source_clause(test_clause)
    clause = policy_clauses(policies).get(clause_id)
    if clause is None:
        raise RiskPolicyError(
            "{0} is not in the loaded policy, so the threshold {1} states cannot be "
            "read".format(clause_id, test_clause)
        )
    text = clause.get("rule")
    if not isinstance(text, str):
        raise RiskPolicyError(
            "{0} carries no rule text, so the threshold {1} states cannot be "
            "read".format(clause_id, test_clause)
        )
    return text


def read_threshold_sentence(
    clause_id: str, policies: Mapping[str, Any], patterns: Optional[Mapping[str, Any]] = None
) -> Tuple[str, Dict[str, Decimal]]:
    """The threshold sentence and its numbers, read out of the loaded policy.

    ``clause_id`` is a test id. Returns the sentence as the policy states it --
    which is what the output quotes -- and the numbers captured out of it.
    Raises :class:`RiskPolicyError` when the clause is absent, carries no rule
    text, or states no sentence this code can read, because a sentence that has
    moved is a refusal and not a default.

    ``patterns`` is the table the sentence is matched against, and it defaults
    to the five version-6 clauses': a caller reading a version-7 case passes
    :data:`V7_THRESHOLD_PATTERNS` instead, because the sentences v2.1 states are
    not the sentences version 6 states.
    """
    pattern = (THRESHOLD_PATTERNS if patterns is None else patterns).get(clause_id)
    if pattern is None:
        raise RiskPolicyError(
            "{0} is not one of the tests this module reads at this policy "
            "version".format(clause_id)
        )
    text = clause_rule_text(clause_id, policies)
    match = pattern.search(text)
    if match is None:
        raise RiskPolicyError(
            "{0} states no threshold this code can read, so its text has moved or "
            "changed and the numbers can no longer be taken from it".format(clause_id)
        )
    numbers = {name: Decimal(value) for name, value in match.groupdict().items()}
    return match.group(0), numbers


# --------------------------------------------------------------------------
# Reading a case
# --------------------------------------------------------------------------
def profile_value(case: Mapping[str, Any], path: str) -> Optional[Any]:
    """The value of one profile field, or ``None`` when it is not carried.

    The payload is asked for the one field named, by name. Nothing else on the
    profile is read, so a counter the clause does not name -- a lifetime counter
    above all -- cannot reach a signal through this function.
    """
    prefix, _, name = path.partition(".")
    evidence_type = PROFILE_TYPES.get(prefix)
    if evidence_type is None or not name:
        raise RiskError("{0} is not a profile field path".format(path))
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("evidence_type") != evidence_type:
            continue
        payload = artifact.get("payload")
        if not isinstance(payload, Mapping):
            return None
        return payload.get(name)
    return None


def _as_number(value: Any) -> Optional[Decimal]:
    """A counter as a ``Decimal``, or ``None`` when it is absent or not one."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


class Signal(NamedTuple):
    """One policy test's reading of one case."""

    clause: str
    category: str
    side: str
    fields: Tuple[Tuple[str, Optional[Any]], ...]
    threshold: str
    tripped: bool
    notes: Tuple[str, ...]


def _trips(clause: str, values: Mapping[str, Optional[Any]], numbers: Mapping[str, Decimal]) -> bool:
    """Whether the clause's test trips on these values.

    The tests are the five the policy states, in the policy's own arithmetic.
    An absent counter cannot establish a pattern, so it does not trip.
    """
    if clause == "POL-RD-06":
        flags = _as_number(values["driver_profile.deviation_flags_90d"])
        trips = _as_number(values["driver_profile.completed_trips_90d"])
        if flags is None:
            return False
        if flags >= numbers["min_flags"]:
            return True
        if trips is None or trips <= 0:
            return False
        return trips >= numbers["min_trips"] and flags / trips >= numbers["min_rate"]

    if clause == "POL-RD-08":
        claims = _as_number(values["rider_profile.deviation_claims_60d"])
        substantiated = _as_number(
            values["rider_profile.deviation_claims_60d_substantiated"]
        )
        if claims is None or substantiated is None:
            return False
        return claims >= numbers["min_claims"] and substantiated <= numbers["max_substantiated"]

    if clause == "POL-NS-07":
        terminations = _as_number(values["driver_profile.no_show_terminations_30d"])
        trips = _as_number(values["driver_profile.completed_trips_30d"])
        if terminations is None:
            return False
        if terminations < numbers["min_terminations"]:
            return False
        if trips is None or trips <= 0:
            return False
        return terminations / trips > numbers["max_rate"]

    if clause == "POL-NS-09(c)":
        counters = [
            _as_number(values["rider_profile.disputes_with_counterparty_90d"]),
            _as_number(values["driver_profile.disputes_with_counterparty_90d"]),
        ]
        present = [counter for counter in counters if counter is not None]
        if not present:
            return False
        return max(present) >= numbers["min_disputes"]

    if clause == "POL-NS-09(d)":
        disputes = _as_number(values["rider_profile.no_show_disputes_30d"])
        if disputes is None:
            return False
        return disputes >= numbers["min_disputes"]

    if clause == V7_FRAUD_CLAUSE:
        counters = [
            _as_number(values["rider_profile.fraud_flags"]),
            _as_number(values["driver_profile.fraud_flags"]),
        ]
        present = [counter for counter in counters if counter is not None]
        if not present:
            return False
        return max(present) >= numbers["min_flags"]

    if clause == V7_REPEAT_NO_SHOW_CLAUSE:
        cancellations = _as_number(values["rider_profile.no_show_cancellations_30d"])
        if cancellations is None:
            return False
        return cancellations >= numbers["min_cancellations"]

    raise RiskError("{0} is not one of the tests this module reads".format(clause))


def _notes_for(
    test: PolicyTest, values: Mapping[str, Optional[Any]]
) -> Tuple[str, ...]:
    """The notes a signal carries beyond its verdict."""
    notes: List[str] = []
    for path in test.fields:
        if values[path] is None:
            notes.append("field_absent: {0}".format(path))
    if test.clause == PAIR_CLAUSE:
        rider = values["rider_profile.disputes_with_counterparty_90d"]
        driver = values["driver_profile.disputes_with_counterparty_90d"]
        if rider is not None and driver is not None and rider != driver:
            notes.append(
                "counters_disagree: rider={0} driver={1}; the larger is the figure "
                "the test runs on".format(rider, driver)
            )
    return tuple(sorted(notes))


def _as_version(value: Any) -> Optional[int]:
    """A recorded policy version as an ``int``, or ``None`` when it is not one.

    A run records its version as a number, but a caller may hand this layer a
    string from a document it read itself, and ``"7" >= 7`` is a ``TypeError``
    rather than an answer. A value that is not a version is read as "no version
    named", which is the version-6 five -- the reading every caller before this
    parameter got.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def signals_for(
    case: Mapping[str, Any],
    policies: Mapping[str, Any],
    policy_version: Optional[int] = None,
) -> Tuple[Signal, ...]:
    """Every test of this case's category, tripped or not, sorted by clause.

    ``policy_version`` selects which tests are the policy's own. ``None`` -- and
    every version below 7 -- is the five version-6 clauses, so every caller
    written before this parameter existed reads exactly what it read before. At
    version 7 the two tests are v2.1's: a fraud flag on either party
    (POL-GEN-22) and a rider with three or more no-show cancellations in the
    trailing thirty days (POL-NS-25).

    A general test -- POL-GEN-22 belongs to no one category -- applies to a
    dispute of either category, and its signal is reported under the case's own
    category so that every line of one case names the same one.
    """
    version = _as_version(policy_version)
    version_seven = version is not None and version >= V7_SIGNALS_VERSION
    tests = V7_POLICY_TESTS if version_seven else POLICY_TESTS
    patterns = V7_THRESHOLD_PATTERNS if version_seven else THRESHOLD_PATTERNS

    category = case["dispute"]["category"]
    found: List[Signal] = []
    for test in tests:
        if test.category not in (category, GENERAL_CATEGORY):
            continue
        sentence, numbers = read_threshold_sentence(test.clause, policies, patterns)
        values = {path: profile_value(case, path) for path in test.fields}
        found.append(
            Signal(
                clause=test.clause,
                category=category,
                side=test.side,
                fields=tuple(sorted(values.items())),
                threshold=sentence,
                tripped=_trips(test.clause, values, numbers),
                notes=_notes_for(test, values),
            )
        )
    return tuple(sorted(found, key=lambda signal: signal.clause))


# --------------------------------------------------------------------------
# The attention flag
# --------------------------------------------------------------------------
class RepeatPartyFlag(NamedTuple):
    """A party id this dispute shares with another dispute of the same root."""

    party_role: str
    party_id: str
    other_case_no: int
    other_filed_at: str
    days_apart: str


def _filed_at(case: Mapping[str, Any]) -> str:
    return str(case["dispute"]["filed_at"])


def _trip_party_ids(case: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """``(rider_id, driver_id)`` off the trip record, which is where they are.

    The trip record is read rather than the profiles: a profile is a snapshot of
    a party's history and POL-GEN-01 forbids it from establishing a fact about
    the trip, while the trip record's ids are the trip's own.
    """
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("evidence_type") != TRIP_EVIDENCE_TYPE:
            continue
        payload = artifact.get("payload")
        if not isinstance(payload, Mapping):
            continue
        return payload.get("rider_id"), payload.get("driver_id")
    return None, None


def _parse_instant(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise RiskError("filed_at is not an ISO 8601 instant: {0!r}".format(text)) from exc


def _cases_in_root(case_root: Path) -> List[Mapping[str, Any]]:
    """Every case file in one root, in file-name order."""
    found: List[Mapping[str, Any]] = []
    for path in sorted(Path(case_root).glob("case-*.json")):
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise RiskError("invalid JSON in {0}: {1}".format(path, exc)) from exc
    return found


def repeat_party_flags(
    case: Mapping[str, Any], case_root: Path
) -> Tuple[RepeatPartyFlag, ...]:
    """The same party id in another dispute of this root, within 30 days.

    An attention flag and nothing more: it says a reviewer may want to look at
    two disputes together, and it is never a finding. Sorted by role, party id
    and the other case number, so two runs give the same order.
    """
    this_no = case["case_no"]
    this_at = _parse_instant(_filed_at(case))
    this_rider, this_driver = _trip_party_ids(case)
    wanted = {"RIDER": this_rider, "DRIVER": this_driver}

    found: List[RepeatPartyFlag] = []
    for other in _cases_in_root(case_root):
        if other.get("case_no") == this_no:
            continue
        other_at = _parse_instant(_filed_at(other))
        seconds = abs((other_at - this_at).total_seconds())
        if seconds > REPEAT_PARTY_WINDOW_DAYS * 86400:
            continue
        other_rider, other_driver = _trip_party_ids(other)
        for role, other_id in (("RIDER", other_rider), ("DRIVER", other_driver)):
            party_id = wanted[role]
            if party_id is None or other_id != party_id:
                continue
            found.append(
                RepeatPartyFlag(
                    party_role=role,
                    party_id=str(party_id),
                    other_case_no=int(other["case_no"]),
                    other_filed_at=_filed_at(other),
                    days_apart="{0:g}".format(seconds / 86400.0),
                )
            )
    return tuple(sorted(found, key=lambda flag: (flag.party_role, flag.party_id, flag.other_case_no)))


# --------------------------------------------------------------------------
# The assessment and its rendering
# --------------------------------------------------------------------------
class Assessment(NamedTuple):
    """One case's signals and attention flags."""

    case_no: int
    category: str
    filed_by: str
    filed_at: str
    signals: Tuple[Signal, ...]
    attention: Tuple[RepeatPartyFlag, ...]


def assess(
    case: Mapping[str, Any],
    policies: Mapping[str, Any],
    case_root: Path,
    policy_version: Optional[int] = None,
) -> Assessment:
    """Every signal and every attention flag for one case.

    ``policy_version`` is the version the case was read at, and it decides which
    tests are the policy's own -- see :func:`signals_for`. It defaults to
    ``None``, which is the version-6 five, so a caller that does not name one
    reads exactly what it read before.
    """
    dispute = case["dispute"]
    return Assessment(
        case_no=case["case_no"],
        category=dispute["category"],
        filed_by=dispute["filed_by"],
        filed_at=_filed_at(case),
        signals=signals_for(case, policies, policy_version),
        attention=repeat_party_flags(case, case_root),
    )


def render(assessment: Assessment) -> str:
    """The assessment as text, deterministic and ASCII."""
    lines: List[str] = [
        "case {0}: {1}, filed by {2} at {3}".format(
            assessment.case_no,
            assessment.category,
            assessment.filed_by,
            assessment.filed_at,
        )
    ]
    for signal in assessment.signals:
        lines.append(
            "  {0}  {1}  side={2}  tripped={3}".format(
                signal.clause,
                signal.category,
                signal.side,
                "true" if signal.tripped else "false",
            )
        )
        for path, value in signal.fields:
            lines.append("    {0} = {1}".format(path, "null" if value is None else value))
        for note in signal.notes:
            lines.append("    note: {0}".format(note))
        lines.append("    threshold: \"{0}\"".format(signal.threshold))

    lines.append("attention flags ({0}):".format(REPEAT_PARTY_LABEL))
    if not assessment.attention:
        lines.append("  {0}: none".format(REPEAT_PARTY_FLAG))
    for flag in assessment.attention:
        lines.append(
            "  {0}: {1} {2} also appears in case {3}, filed {4}, {5} days "
            "apart".format(
                REPEAT_PARTY_FLAG,
                flag.party_role,
                flag.party_id,
                flag.other_case_no,
                flag.other_filed_at,
                flag.days_apart,
            )
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def _load(case: Optional[int], case_file: Optional[Path]) -> Tuple[Mapping[str, Any], Path]:
    """``(case, case root)`` for one invocation.

    ``--case`` reads the corpus through the manifest; ``--case-file`` reads one
    converted case through its own path. The case root is where the other
    disputes a repeat party would be found in: the corpus directory, or the
    directory the named file sits in.
    """
    if case is not None:
        return loader.load_case(case), Path(loader.CASES_DIR)
    path = Path(case_file).resolve()
    return loader.load_external_case(path), path.parent


def _cases_over_root(case_root: Path) -> List[Mapping[str, Any]]:
    """Every case file in one root, by case number.

    A root that is not there is refused rather than read as an empty one: "this
    root holds no case" and "there is no root at this path" are different
    answers, and the second one silently printing nothing would be a reading
    nobody made.
    """
    root = Path(case_root)
    if not root.is_dir():
        raise RiskError("no case root at {0}".format(root))
    return sorted(_cases_in_root(root), key=lambda case: case["case_no"])


def assessments_over_root(case_root: Path) -> Tuple[Assessment, ...]:
    """Every case in one root, assessed, in case-number order."""
    found: List[Assessment] = []
    for case in _cases_over_root(case_root):
        policies = loader.load_policies(case["dispute"]["category"])
        found.append(assess(case, policies, Path(case_root)))
    return tuple(found)


def assessment_json(assessment: Assessment) -> Dict[str, Any]:
    """One assessment as plain data: dicts and lists, no named tuples."""
    return {
        "case_no": assessment.case_no,
        "category": assessment.category,
        "filed_by": assessment.filed_by,
        "filed_at": assessment.filed_at,
        "signals": [
            {
                "clause": signal.clause,
                "category": signal.category,
                "side": signal.side,
                "tripped": signal.tripped,
                "fields": [[path, value] for path, value in signal.fields],
                "threshold": signal.threshold,
                "notes": list(signal.notes),
            }
            for signal in assessment.signals
        ],
        "attention": [
            {
                "party_role": flag.party_role,
                "party_id": flag.party_id,
                "other_case_no": flag.other_case_no,
                "other_filed_at": flag.other_filed_at,
                "days_apart": flag.days_apart,
            }
            for flag in assessment.attention
        ],
    }


def _json_value(value: Any) -> str:
    """A value ``json`` cannot write, as the text the case files write it as.

    The only one is ``Decimal``: a case read through the external loader carries
    its money as a ``Decimal``, and writing it as a binary float would make the
    document depend on the platform's arithmetic. Its own literal text is what
    the case file holds and what a reader of the JSON can compare.
    """
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("{0!r} is not JSON-serialisable".format(value))


def json_document(assessments: Sequence[Assessment]) -> str:
    """``assessments`` as a deterministic JSON document.

    Sorted keys, one element per case in the order they were given, and a fixed
    key order within each -- so two runs produce the same bytes and a caller can
    diff them.
    """
    document = {"cases": [assessment_json(item) for item in assessments]}
    return json.dumps(document, sort_keys=True, indent=2, default=_json_value) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print the fraud and bad-faith signals for one case, or for a whole root."""
    parser = argparse.ArgumentParser(
        prog="python -m ops.risk",
        description=(
            "Report the five policy tests for one case or a whole case root, and "
            "the repeat_party attention flag. Writes nothing, and opens no answer "
            "key."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--case", type=int, help="a corpus case number")
    source.add_argument("--case-file", type=Path, help="one converted case file")
    source.add_argument(
        "--case-root", type=Path, help="every case file in one directory"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the readings as a JSON document rather than as text",
    )
    args = parser.parse_args(argv)

    try:
        if args.case_root is not None:
            assessments: Tuple[Assessment, ...] = assessments_over_root(args.case_root)
        else:
            case, case_root = _load(args.case, args.case_file)
            policies = loader.load_policies(case["dispute"]["category"])
            assessments = (assess(case, policies, case_root),)
    except (RiskError, loader.LoaderError) as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    if args.json:
        sys.stdout.write(json_document(assessments))
        return 0
    for assessment in assessments:
        sys.stdout.write(render(assessment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
