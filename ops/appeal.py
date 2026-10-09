"""The appeal command: check an appeal against ``POL-GEN-04`` and assign a reviewer.

Policy version 6 carries an appeal clause, ``POL-GEN-04`` in the general policy,
and until this module nothing executed it. This is the operations-layer command
that reads that clause, checks an appeal against each of its limbs, and -- when
the appeal is admissible -- names the reviewer who will hear it. **It decides
nothing about the merits.** An appeal is a route to human review, not a ruling:
the clause licenses no ruling value, and neither does this command.

**What it reads, and only this.** The ruling, its issue time and the trip are
read from two files, and the module docstring says which fields:

* the **run's case file** (``runs/.../case-NNNNN.json``) for ``case_no``, the
  ``ruling`` block's ``ruling``, ``amount_sgd`` and ``driver_compensation_sgd``,
  the ``configuration.policy_version`` the run recorded, and ``recorded_at`` --
  which is the instant the ruling was issued, because it is the instant the run
  that made it wrote the ruling down;
* the **public case record** (through the set's own loader) for
  ``dispute.trip_id``, ``dispute.category`` and ``dispute.filed_by``, and the
  trip record artifact's ``rider_id``, ``driver_id`` and its own time -- the
  first present of ``started_at``, ``ended_at``, ``cancelled_at`` and
  ``requested_at``, which is when the trip happened (a trip cancelled before it
  started carries ``cancelled_at`` and no ``started_at``).

Nothing else is read. No answer key is opened, no transcript is read and no
model is called: the run's case file carries the ruling the vote produced, and
that is the whole of what an appeal is checked against.

**The six checks, each a named result.**

1. ``once`` -- a second appeal on the same trip is refused. The trip's earlier
   appeals are read from ``--earlier-appeals``, which lists ``case`` and
   ``trip_id``; absent means none.
2. ``in_time`` -- the appeal is lodged within the clause's number of days (30)
   of the trip or of the ruling's issue, whichever is later. The number is read
   out of the clause's own sentence, and the boundary is inclusive.
3. ``ruling_exists`` -- an appeal is lodged after a ruling has issued. A case
   sent to a reviewer (``ESCALATE``) has no ruling to appeal, and so has a case
   file that records no ruling at all.
4. ``evidence`` -- the appeal may add only record-type evidence of the kinds the
   clause lists, and may not add or amend a party statement. An appeal that adds
   only statements, or none of the listed kinds, is refused.
5. ``reviewer`` -- the reviewer did not take part in any earlier review of the
   same trip (limb (a)), read from ``--earlier-reviews``, which lists ``case``,
   ``trip_id`` and ``reviewer``; and is not a party: their id equals neither the
   rider's nor the driver's id on the trip record.
6. ``execution`` -- whether the ruling's money is suspended (not yet executed)
   or, having been executed under ``POL-GEN-05``, is reversed by a successful
   appeal. The execution threshold is read from ``POL-GEN-05``.

**Every threshold is read from the loaded policy text.** The appeal window is
matched as the clause states it, the number included, so a sentence that has
moved or whose number has been edited is a **refusal** rather than a figure
nobody reviewed -- the reading ``ops.risk`` takes of its own thresholds. The
execution threshold is the figure ``POL-GEN-05`` names as
``execution_threshold_sgd``, and the sentence that names it is matched the same
way. A clause the loaded policy does not carry is refused.

**No wall clock unless ``--now`` is given.** ``--lodged-at`` is when the appeal
was lodged, and it is what the in-time check compares against the deadline;
``--now`` is the only clock this module ever reads, and it is used for nothing
but reporting the window's status at that instant. Without it, no clock is read.
The output is sorted and byte-identical across two runs of one command.

**What it does not do.** It writes nothing unless given ``--out``, and an
``--out`` inside ``runs/``, ``data/``, ``policy/``, ``prompts/``, ``tribunal/``,
``eval/answers/`` or a sealed root is refused through :mod:`ops`' own guard. It
records no closure: a successful appeal is recorded as a human closure under
``POL-GEN-06`` by ``ops.review``, not here. It changes nothing in ``tribunal/``,
``prompts/``, ``policy/``, ``runs/`` or ``data/``.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from ops import (
    OpsError,
    OpsWriteError,
    development_set_for,
    read_json_document,
    refuse_a_forbidden_destination,
)
from tribunal import loader, money, precedents

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class AppealError(OpsError):
    """Base class for every failure this module reports."""


class AppealInputError(AppealError):
    """An argument, a file or a run the command cannot use.

    Reported with exit status 2: the command could not be run, which is a
    different thing from an appeal that was run and refused (exit status 3).
    """


class AppealPolicyError(AppealInputError):
    """A clause the appeal is checked against is absent, or has moved.

    Raised rather than resolved against a constant: a threshold that fell back
    to a number written in Python would be an appeal decided on a figure nobody
    reviewed, which is the failure the layer exists to prevent.
    """


# --------------------------------------------------------------------------
# The clause, as the policy states it
# --------------------------------------------------------------------------
# The two clauses the appeal is checked against. Both live in the general
# policy, which every category's loaded policy carries.
CLAUSE_APPEAL = "POL-GEN-04"
CLAUSE_EXECUTION = "POL-GEN-05"

# The appeal window, matched as the clause states it. Both numbers are literals
# in the pattern, so a sentence that has moved -- or whose ``30`` has been
# edited -- does not match and the module refuses rather than applying a figure
# nobody reviewed. The same shape ``ui/v2/build.py`` reads the clause with.
APPEAL_WINDOW_RE = re.compile(
    r"may appeal it (?P<times>once), within (?P<days>30) days of the trip or of "
    r"the ruling's issue, whichever is later"
)

# The evidence limb, as the clause states it: the list of record kinds the
# appeal may add, and the bar on a party statement.
APPEAL_EVIDENCE_RE = re.compile(
    r"may add only record-type evidence - .*? - and may not add or amend a "
    r"party statement"
)

# The sentence each of the other limbs is quoted from. They are matched as the
# clause states them, so a limb that has moved is a refusal.
ONCE_SENTENCE = "A second appeal on the same trip"
RULING_SENTENCE = "it is lodged after a ruling has issued"
REVIEWER_SENTENCE = (
    "is heard by a human reviewer who did not take part in any earlier review "
    "of the same trip"
)

# The execution sentence ``POL-GEN-05`` states, matched the same way. The figure
# itself is the field the sentence names.
EXECUTION_SENTENCE_RE = re.compile(
    r"does not exceed execution_threshold_sgd is executed automatically on issue"
)

# The field ``POL-GEN-05`` names as the execution threshold.
EXECUTION_THRESHOLD_FIELD = "execution_threshold_sgd"

# --------------------------------------------------------------------------
# The kinds of evidence the clause lists, and the one it bars
# --------------------------------------------------------------------------
# Each token is one of the kinds ``POL-GEN-04`` limb (b) lists, and the comment
# is the clause's own words for it. They are a fixed vocabulary -- a list, not a
# threshold -- and the clause's sentence is matched to confirm it still states
# them before any of them is applied.
RECORD_EVIDENCE_KINDS: Tuple[str, ...] = (
    "GPS_EXPORT",  # a GPS export
    "FARE_STATEMENT",  # a fare statement
    "PAYMENT_STATEMENT",  # a payment statement
    "ERP_GANTRY_RECORD",  # an ERP gantry record with gantry name, entry time ...
    "CALL_LOG",  # a call log
    "PHOTOGRAPH",  # a photograph with its capture time
)

# The kind limb (b) bars: a party statement, which an appeal may not add or
# amend.
STATEMENT_EVIDENCE_KINDS: Tuple[str, ...] = ("STATEMENT",)

# --------------------------------------------------------------------------
# The rulings and the execution states
# --------------------------------------------------------------------------
# The ruling value that means a case went to a reviewer and no monetary outcome
# issued. Named here rather than read from the policy, because it is a *value*
# of the ruling vocabulary and not a policy number.
ESCALATE = "ESCALATE"

# The exception ``POL-GEN-03`` states: on a ``DRIVER_COMPENSATION`` ruling the
# two money fields carry the same figure and it is counted once. Named here for
# the same reason as ``ESCALATE``.
DRIVER_COMPENSATION = "DRIVER_COMPENSATION"

# The three execution states.
STATE_SUSPENDED = "SUSPENDED"  # issued but not executed: the appeal freezes it
STATE_EXECUTED = "EXECUTED_REVERSIBLE"  # executed on issue: a granted appeal reverses it
STATE_NOT_APPLICABLE = "NOT_APPLICABLE"  # no monetary ruling to execute

# The two sides a party may appeal from, as ``--filed-by`` spells them.
SIDES: Tuple[str, ...] = ("rider", "driver")

# The check names, in the order the task lists them.
CHECK_ONCE = "once"
CHECK_IN_TIME = "in_time"
CHECK_RULING_EXISTS = "ruling_exists"
CHECK_EVIDENCE = "evidence"
CHECK_REVIEWER = "reviewer"
CHECK_EXECUTION = "execution"
CHECKS: Tuple[str, ...] = (
    CHECK_ONCE,
    CHECK_IN_TIME,
    CHECK_RULING_EXISTS,
    CHECK_EVIDENCE,
    CHECK_REVIEWER,
    CHECK_EXECUTION,
)


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


def clause_rule_text(clause_id: str, policies: Mapping[str, Any]) -> str:
    """The ``rule`` text of one clause, refused when the policy carries none."""
    clause = policy_clauses(policies).get(clause_id)
    if clause is None:
        raise AppealPolicyError(
            "{0} is not in the loaded policy, so an appeal cannot be checked "
            "against it".format(clause_id)
        )
    text = clause.get("rule")
    if not isinstance(text, str):
        raise AppealPolicyError(
            "{0} carries no rule text, so an appeal cannot be checked against "
            "it".format(clause_id)
        )
    return text


def _matched_sentence(
    pattern: "re.Pattern[str]", clause_id: str, policies: Mapping[str, Any]
) -> Tuple[str, Dict[str, str]]:
    """The sentence a pattern matches in one clause, with its captured numbers.

    The sentence is returned as the policy states it -- which is what the output
    quotes -- and so are the numbers captured out of it. A clause whose sentence
    has moved is a refusal rather than a default.
    """
    text = clause_rule_text(clause_id, policies)
    match = pattern.search(text)
    if match is None:
        raise AppealPolicyError(
            "{0} states no sentence this code can read, so its text has moved or "
            "changed and the numbers can no longer be taken from it".format(clause_id)
        )
    return match.group(0), match.groupdict()


def read_appeal_window(policies: Mapping[str, Any]) -> Tuple[str, int]:
    """The appeal-window sentence and the number of days, from ``POL-GEN-04``.

    The number is read out of the clause's own sentence, and the sentence is
    matched as the clause states it, so an edit to the figure is refused.
    """
    sentence, numbers = _matched_sentence(APPEAL_WINDOW_RE, CLAUSE_APPEAL, policies)
    return sentence, int(numbers["days"])


def read_execution_threshold(policies: Mapping[str, Any]) -> Tuple[str, Decimal]:
    """The execution sentence and the threshold, from ``POL-GEN-05``.

    The sentence ``POL-GEN-05`` states is matched as the clause states it, and
    the figure is the policy field the sentence names -- which is what the
    clause calls it: "The threshold is a field of this policy file".
    """
    sentence, _numbers = _matched_sentence(
        EXECUTION_SENTENCE_RE, CLAUSE_EXECUTION, policies
    )
    general = policies.get("general")
    if not isinstance(general, Mapping):
        raise AppealPolicyError("the loaded policy carries no general policy file")
    raw = general.get(EXECUTION_THRESHOLD_FIELD)
    if raw is None or isinstance(raw, bool):
        raise AppealPolicyError(
            "the general policy states no {0}, so the execution state cannot be "
            "read".format(EXECUTION_THRESHOLD_FIELD)
        )
    try:
        threshold = Decimal(str(raw))
    except Exception as exc:  # pragma: no cover - a malformed policy file
        raise AppealPolicyError(
            "the general policy's {0} is not a number: {1!r}".format(
                EXECUTION_THRESHOLD_FIELD, raw
            )
        ) from exc
    return sentence, threshold


def read_sentences(policies: Mapping[str, Any]) -> Dict[str, str]:
    """The clause text each check quotes, refused when a limb has moved."""
    text = clause_rule_text(CLAUSE_APPEAL, policies)
    evidence = APPEAL_EVIDENCE_RE.search(text)
    if evidence is None:
        raise AppealPolicyError(
            "{0} no longer states which evidence an appeal may add".format(CLAUSE_APPEAL)
        )
    found = {
        CHECK_ONCE: ONCE_SENTENCE,
        CHECK_RULING_EXISTS: RULING_SENTENCE,
        CHECK_EVIDENCE: evidence.group(0),
        CHECK_REVIEWER: REVIEWER_SENTENCE,
    }
    for name, sentence in found.items():
        if name == CHECK_EVIDENCE:
            continue
        if sentence not in text:
            raise AppealPolicyError(
                "{0} no longer states the sentence the {1} check reads".format(
                    CLAUSE_APPEAL, name
                )
            )
    return found


# --------------------------------------------------------------------------
# Reading the run and the case
# --------------------------------------------------------------------------
def _parse_instant(text: Any, where: str) -> datetime:
    """One ISO 8601 instant, refused unless it names an instant with an offset.

    A wall time without an offset does not name an instant, and two of them
    cannot be ordered; so an offset is required, exactly as ``ops.queue``
    requires one for ``--now``.
    """
    if not isinstance(text, str):
        raise AppealInputError("{0} is not an ISO 8601 instant: {1!r}".format(where, text))
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AppealInputError(
            "{0} is not an ISO 8601 instant: {1!r}".format(where, text)
        ) from exc
    if parsed.tzinfo is None:
        raise AppealInputError(
            "{0} carries no UTC offset, so it names a wall time rather than an "
            "instant: {1!r}".format(where, text)
        )
    return parsed


def _trip_record(case: Mapping[str, Any]) -> Mapping[str, Any]:
    """The case's trip record payload, or an empty mapping."""
    for artifact in case.get("evidence") or []:
        if not isinstance(artifact, Mapping):
            continue
        if artifact.get("evidence_type") != "TRIP_RECORD":
            continue
        payload = artifact.get("payload")
        if isinstance(payload, Mapping):
            return payload
    return {}


def trip_time(payload: Mapping[str, Any]) -> Optional[str]:
    """The trip's own time, off the trip record.

    The first present of ``started_at``, ``ended_at``, ``cancelled_at`` and
    ``requested_at``: a completed trip carries its start and end, and a trip
    cancelled before it started carries ``cancelled_at`` and neither of those.
    ``None`` when the record carries none of them.
    """
    for key in ("started_at", "ended_at", "cancelled_at", "requested_at"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


class LoadedRun(NamedTuple):
    """The pieces one appeal is checked against, read off the two files."""

    set_name: str
    case_no: int
    trip_id: Any
    category: str
    filed_by: Any
    policy_version: int
    ruling_block: Mapping[str, Any]
    ruling_value: Any
    amount_sgd: Any
    driver_compensation_sgd: Any
    issue_at: str
    trip_at: Optional[str]
    rider_id: Any
    driver_id: Any


def load_run(run_dir: Path, case_no: int) -> LoadedRun:
    """Read one case of one run, and the public case it was made from.

    The run's case file supplies the ruling, its issue instant and the policy
    version; the public case supplies the trip, the party ids and the trip's
    time. The set is read off the run directory's own path through the registry,
    so a run of a set this layer does not know is refused rather than guessed.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise AppealInputError("no run directory at {0}".format(run_dir))

    case_file = precedents.case_file_for(run_dir, case_no)
    document = read_json_document(case_file, AppealInputError)
    if not isinstance(document, Mapping):
        raise AppealInputError("the case file at {0} is not a JSON object".format(case_file))
    if document.get("case_no") != case_no:
        raise AppealInputError(
            "the case file at {0} declares case_no {1!r}".format(
                case_file, document.get("case_no")
            )
        )

    development_set = development_set_for(run_dir)
    try:
        case = development_set.load_case(case_no)
    except loader.LoaderError as exc:
        raise AppealInputError(
            "case {0} of the {1} set cannot be loaded: {2}".format(
                case_no, development_set.name, exc
            )
        ) from exc

    configuration = document.get("configuration")
    version = configuration.get("policy_version") if isinstance(configuration, Mapping) else None
    policy_version = version or development_set.policy_version

    ruling_block = document.get("ruling")
    inner = ruling_block.get("ruling") if isinstance(ruling_block, Mapping) else None
    inner = inner if isinstance(inner, Mapping) else {}

    trip = _trip_record(case)
    dispute = case["dispute"]
    return LoadedRun(
        set_name=development_set.name,
        case_no=case_no,
        trip_id=dispute.get("trip_id"),
        category=dispute.get("category"),
        filed_by=dispute.get("filed_by"),
        policy_version=policy_version,
        ruling_block=ruling_block if isinstance(ruling_block, Mapping) else {},
        ruling_value=inner.get("ruling"),
        amount_sgd=inner.get("amount_sgd"),
        driver_compensation_sgd=inner.get("driver_compensation_sgd"),
        issue_at=str(document.get("recorded_at") or ""),
        trip_at=trip_time(trip),
        rider_id=trip.get("rider_id"),
        driver_id=trip.get("driver_id"),
    )


# --------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------
class Check(NamedTuple):
    """One named check's result, and the clause text it read."""

    check: str
    result: Any
    clause: str
    sentence: str
    detail: str


def check_once(trip_id: Any, earlier_appeals: Sequence[Mapping[str, Any]]) -> Check:
    """A second appeal on the same trip is refused."""
    same = [
        entry.get("case")
        for entry in earlier_appeals
        if entry.get("trip_id") == trip_id
    ]
    result = not same
    if result:
        detail = "no earlier appeal on trip {0}".format(trip_id)
    else:
        detail = "an appeal is already lodged on trip {0} (case {1}); a second appeal is refused".format(
            trip_id, ", ".join(str(case) for case in same)
        )
    return Check(CHECK_ONCE, result, CLAUSE_APPEAL, ONCE_SENTENCE, detail)


def check_in_time(
    trip_at: Optional[str],
    issue_at: str,
    lodged_at: datetime,
    window_days: int,
    sentence: str,
) -> Check:
    """The appeal is lodged within the window of the trip or the issue, whichever is later."""
    trip_instant = _parse_instant(trip_at, "the trip's time") if trip_at else None
    issue_instant = _parse_instant(issue_at, "the ruling's issue time")
    later = issue_instant
    which = "the ruling's issue"
    if trip_instant is not None and trip_instant > issue_instant:
        later = trip_instant
        which = "the trip"
    deadline = later + timedelta(days=window_days)
    result = lodged_at <= deadline
    detail = (
        "lodged {0} against a deadline of {1} ({2} plus {3} days, from {4})".format(
            lodged_at.isoformat(), deadline.isoformat(), later.isoformat(),
            window_days, which,
        )
    )
    return Check(CHECK_IN_TIME, result, CLAUSE_APPEAL, sentence, detail)


def check_ruling_exists(ruling_value: Any) -> Check:
    """An appeal is lodged after a ruling has issued."""
    if ruling_value == ESCALATE:
        detail = (
            "the ruling is ESCALATE: the case was sent to a reviewer and no "
            "ruling issued, so there is nothing to appeal"
        )
        result = False
    elif not isinstance(ruling_value, str) or not ruling_value:
        detail = "the case file records no ruling, so there is nothing to appeal"
        result = False
    else:
        detail = "the ruling is {0}".format(ruling_value)
        result = True
    return Check(CHECK_RULING_EXISTS, result, CLAUSE_APPEAL, RULING_SENTENCE, detail)


def classify_evidence(kinds: Sequence[str]) -> Tuple[List[str], List[str], List[str]]:
    """``(record, statements, unknown)`` for the evidence kinds one appeal adds."""
    record: List[str] = []
    statements: List[str] = []
    unknown: List[str] = []
    for kind in kinds:
        if kind in RECORD_EVIDENCE_KINDS:
            record.append(kind)
        elif kind in STATEMENT_EVIDENCE_KINDS:
            statements.append(kind)
        else:
            unknown.append(kind)
    return record, statements, unknown


def check_evidence(kinds: Sequence[str], sentence: str) -> Check:
    """The appeal adds only record-type evidence of the listed kinds.

    Refused when it adds a party statement, when it adds a kind the clause does
    not list, or when it adds none of the listed kinds at all.
    """
    record, statements, unknown = classify_evidence(kinds)
    reasons: List[str] = []
    if statements:
        reasons.append(
            "it adds a party statement ({0}), which an appeal may not add or "
            "amend".format(", ".join(statements))
        )
    if unknown:
        reasons.append(
            "it adds {0}, which is not one of the kinds the clause lists".format(
                ", ".join(unknown)
            )
        )
    if not record:
        reasons.append(
            "it adds none of the listed record kinds, so an appeal that adds only "
            "statements (or nothing) is refused"
        )
    result = not reasons
    if result:
        detail = "record-type evidence of the listed kinds: {0}".format(", ".join(record))
    else:
        detail = "; ".join(reasons)
    return Check(CHECK_EVIDENCE, result, CLAUSE_APPEAL, sentence, detail)


def check_reviewer(
    reviewer: Any,
    trip_id: Any,
    rider_id: Any,
    driver_id: Any,
    earlier_reviews: Sequence[Mapping[str, Any]],
) -> Check:
    """The reviewer heard no earlier review of the trip, and is not a party."""
    reasons: List[str] = []
    prior = [
        entry.get("case")
        for entry in earlier_reviews
        if entry.get("trip_id") == trip_id and entry.get("reviewer") == reviewer
    ]
    if prior:
        reasons.append(
            "the reviewer {0} reviewed trip {1} before (case {2})".format(
                reviewer, trip_id, ", ".join(str(case) for case in prior)
            )
        )
    party_of = None
    if reviewer is not None and reviewer == rider_id:
        party_of = "rider"
    elif reviewer is not None and reviewer == driver_id:
        party_of = "driver"
    if party_of is not None:
        reasons.append(
            "the reviewer {0} is the {1} of this trip, and a party may not hear "
            "its own appeal".format(reviewer, party_of)
        )
    result = not reasons
    if result:
        detail = "the reviewer {0} took part in no earlier review of trip {1} and is not a party".format(
            reviewer, trip_id
        )
    else:
        detail = "; ".join(reasons)
    return Check(CHECK_REVIEWER, result, CLAUSE_APPEAL, REVIEWER_SENTENCE, detail)


def monetary_effect(
    ruling_value: Any, amount_sgd: Any, driver_compensation_sgd: Any
) -> Decimal:
    """The money a ruling moves, under ``POL-GEN-05``.

    ``POL-GEN-03`` states the one exception: on a ``DRIVER_COMPENSATION`` ruling
    the two fields carry the same figure, which is the amount of money the
    ruling moves and not a second payment, so it is counted once. On every other
    ruling the two are independent and are added. The reading is
    ``ui/v2/build.py``'s, stated the same way.
    """
    amount = _as_decimal(amount_sgd)
    driver = _as_decimal(driver_compensation_sgd)
    if ruling_value == DRIVER_COMPENSATION:
        return driver if driver else amount
    return amount + driver


def _as_decimal(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        return Decimal(0)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(0)


def check_execution(
    ruling_value: Any,
    amount_sgd: Any,
    driver_compensation_sgd: Any,
    threshold: Decimal,
    sentence: str,
) -> Tuple[Check, Dict[str, Any]]:
    """Whether the money is suspended, or executed and reversible on appeal.

    ``POL-GEN-05`` executes a provisional ruling whose monetary effect does not
    exceed the threshold on issue, and holds one above it. So a ruling at or
    under the threshold has been executed, and a successful appeal reverses it;
    one above the threshold is held, and the appeal freezes it.
    """
    effect = monetary_effect(ruling_value, amount_sgd, driver_compensation_sgd)
    if ruling_value == ESCALATE or not isinstance(ruling_value, str) or not ruling_value:
        state = STATE_NOT_APPLICABLE
        detail = (
            "there is no monetary ruling to execute: POL-GEN-03 makes an "
            "escalation terminal and holds the disputed amount"
        )
    elif effect > threshold:
        state = STATE_SUSPENDED
        detail = (
            "the monetary effect {0} exceeds the threshold {1}, so it was issued "
            "but not executed; the appeal suspends it and it stays frozen until "
            "decided".format(effect, threshold)
        )
    else:
        state = STATE_EXECUTED
        detail = (
            "the monetary effect {0} does not exceed the threshold {1}, so it was "
            "executed automatically on issue; a successful appeal reverses "
            "it".format(effect, threshold)
        )
    execution = {
        "clause": CLAUSE_EXECUTION,
        "sentence": sentence,
        "state": state,
        "monetary_effect_sgd": effect,
        "execution_threshold_sgd": threshold,
        "detail": detail,
    }
    return Check(CHECK_EXECUTION, state, CLAUSE_EXECUTION, sentence, detail), execution


# --------------------------------------------------------------------------
# The assessment
# --------------------------------------------------------------------------
def assess(
    run: LoadedRun,
    policies: Mapping[str, Any],
    *,
    filed_by: str,
    lodged_at: datetime,
    now: Optional[datetime],
    evidence: Sequence[str],
    reviewer: Any,
    earlier_reviews: Sequence[Mapping[str, Any]] = (),
    earlier_appeals: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    """Every check for one appeal, and the outcome the checks give.

    The five decision checks must all pass for the appeal to be accepted; the
    execution check reports the state of the money and never refuses.
    """
    window_sentence, window_days = read_appeal_window(policies)
    execution_sentence, threshold = read_execution_threshold(policies)
    sentences = read_sentences(policies)

    once = check_once(run.trip_id, earlier_appeals)
    in_time = check_in_time(
        run.trip_at, run.issue_at, lodged_at, window_days, window_sentence
    )
    ruling_exists = check_ruling_exists(run.ruling_value)
    evidence_check = check_evidence(evidence, sentences[CHECK_EVIDENCE])
    reviewer_check = check_reviewer(
        reviewer, run.trip_id, run.rider_id, run.driver_id, earlier_reviews
    )
    execution_check, execution = check_execution(
        run.ruling_value,
        run.amount_sgd,
        run.driver_compensation_sgd,
        threshold,
        execution_sentence,
    )

    checks = [once, in_time, ruling_exists, evidence_check, reviewer_check, execution_check]
    accepted = all(
        check.result is True for check in checks if check.check != CHECK_EXECUTION
    )

    # The deadline, restated for the reader, so the window is visible without
    # re-deriving it from the in-time check's detail.
    trip_instant = _parse_instant(run.trip_at, "the trip's time") if run.trip_at else None
    issue_instant = _parse_instant(run.issue_at, "the ruling's issue time")
    later = max([instant for instant in (trip_instant, issue_instant) if instant is not None])
    deadline = later + timedelta(days=window_days)

    return {
        "case_no": run.case_no,
        "set": run.set_name,
        "trip_id": run.trip_id,
        "category": run.category,
        "filed_by": filed_by,
        "lodged_at": lodged_at.isoformat(),
        "now": None if now is None else now.isoformat(),
        "window_open_at_now": None if now is None else (now <= deadline),
        "policy_version": run.policy_version,
        "appeal_window_days": window_days,
        "deadline": deadline.isoformat(),
        "checks": [
            {
                "check": check.check,
                "result": check.result,
                "clause": check.clause,
                "sentence": check.sentence,
                "detail": check.detail,
            }
            for check in checks
        ],
        "accepted": accepted,
        "reviewer": reviewer if accepted else None,
        "execution": execution,
    }


def render(result: Mapping[str, Any]) -> str:
    """The result as canonical JSON, which is what the digest-free output is."""
    return money.dumps_canonical(dict(result))


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def _read_entries(path: Optional[Path], what: str) -> List[Mapping[str, Any]]:
    """One earlier-reviews or earlier-appeals file, or none when not given.

    A file that is not a JSON array of objects is refused: the list is what a
    check reads, and a list that could not be read would silently make the check
    pass.
    """
    if path is None:
        return []
    document = read_json_document(path, AppealInputError)
    if not isinstance(document, list):
        raise AppealInputError("the {0} file at {1} is not a JSON array".format(what, path))
    entries: List[Mapping[str, Any]] = []
    for entry in document:
        if not isinstance(entry, Mapping):
            raise AppealInputError(
                "the {0} file at {1} holds an entry that is not an object".format(what, path)
            )
        entries.append(entry)
    return entries


def _split_evidence(raw: str) -> List[str]:
    """The comma-separated evidence kinds, trimmed and upper-cased."""
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Check one appeal against ``POL-GEN-04`` and print the result.

    Exit 0 when the appeal is accepted, 3 when it is refused, and 2 when the
    command could not be run at all.
    """
    parser = argparse.ArgumentParser(
        prog="python -m ops.appeal",
        description=(
            "Check an appeal against POL-GEN-04 and assign the reviewer who may "
            "hear it, reporting each check by name and the execution state under "
            "POL-GEN-05. Decides nothing about the merits; makes no model call "
            "and reads no answer key."
        ),
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="the run directory")
    parser.add_argument("--case", type=int, required=True, help="the case number")
    parser.add_argument(
        "--filed-by", choices=SIDES, required=True, help="the party lodging the appeal"
    )
    parser.add_argument(
        "--lodged-at",
        required=True,
        help="the ISO 8601 instant the appeal was lodged, e.g. 2026-10-20T12:00:00+08:00",
    )
    parser.add_argument(
        "--now",
        default=None,
        help=(
            "an ISO 8601 instant; the only wall clock this command reads, used "
            "only to report the window's status"
        ),
    )
    parser.add_argument(
        "--evidence",
        required=True,
        help="the evidence kinds the appeal adds, comma-separated",
    )
    parser.add_argument("--reviewer", required=True, help="the reviewer who may hear it")
    parser.add_argument(
        "--earlier-reviews",
        type=Path,
        default=None,
        help="a JSON file listing earlier reviews (case, trip_id, reviewer)",
    )
    parser.add_argument(
        "--earlier-appeals",
        type=Path,
        default=None,
        help="a JSON file listing earlier appeals (case, trip_id)",
    )
    parser.add_argument("--out", type=Path, default=None, help="write the result here")
    args = parser.parse_args(argv)

    try:
        run = load_run(args.run_dir, args.case)
        try:
            policies = loader.load_policies(run.category, run.policy_version)
        except loader.LoaderError as exc:
            raise AppealInputError(
                "the policy for case {0} cannot be loaded: {1}".format(args.case, exc)
            ) from exc
        lodged_at = _parse_instant(args.lodged_at, "--lodged-at")
        now = _parse_instant(args.now, "--now") if args.now is not None else None
        earlier_reviews = _read_entries(args.earlier_reviews, "earlier-reviews")
        earlier_appeals = _read_entries(args.earlier_appeals, "earlier-appeals")
        result = assess(
            run,
            policies,
            filed_by=args.filed_by,
            lodged_at=lodged_at,
            now=now,
            evidence=_split_evidence(args.evidence),
            reviewer=args.reviewer,
            earlier_reviews=earlier_reviews,
            earlier_appeals=earlier_appeals,
        )
    except AppealError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 2

    rendered = render(result)
    if args.out is not None:
        try:
            out = refuse_a_forbidden_destination(args.out)
        except OpsWriteError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 2
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
        print("wrote {0}".format(out), file=sys.stderr)
    else:
        sys.stdout.write(rendered + "\n")

    return 0 if result["accepted"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
