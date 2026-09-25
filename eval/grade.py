"""Grading for the Tribunal evaluation.

Scores a produced ruling against the answer key at ``eval/answers/``. The grader
is written **before** the benchmark runner on purpose: a grader that has never
been checked against the key can turn a wrong grader into a wrong accuracy
number, and finding that out costs a paid run. ``tests/test_grade.py`` feeds the
key back in as though a perfect judge had produced it and requires 29/29.

Two things this module refuses to do.

**It never grades on two fields.** A ruling is correct only when all four of
``ruling``, ``amount_sgd``, ``driver_compensation_sgd`` and ``referrals`` agree
with the key. Case 207 is ``ESCALATE`` with both money fields ``null`` and a
referral instructing the reviewer to refund the rider's SGD 4.00 in full. A
grader looking only at ``ruling`` and ``amount_sgd`` awards that case full
marks, and a real rider does not get their money back. The two-field figure is
still printed, in one clearly labelled line, because a reader who has been
warned about the trap should be able to see how much it flatters a run.

**It never computes money in binary floating point.** Every amount is converted
with ``Decimal(str(value))`` -- the path ``loader.py`` takes when it parses a
JSON number with ``parse_float=Decimal``. Comparing in binary floating point
would call 4.80 and 4.800000000000001 unequal, and the key's own case 202
stores 4.8, for which ``Decimal("4.8") == 4.8`` is already ``False`` in Python:
the naive comparison is wrong on the key itself. ``null`` and ``0`` are
different answers and never compare equal.

Two rules about what a number means, added 2026-09-22 after both were found to
mislead on real results.

**Referrals are graded by recall, not by set equality.** Every clause the key
names must appear on the produced side; clause references offered beyond those
are reported, not failed. Exact equality scored a correct answer to case 207 as
a failure, because the model named POL-NS-07 as the key requires *and*
POL-NS-09(d), which the key's own rationale for that case names. ``ruling``,
``amount_sgd`` and ``driver_compensation_sgd`` keep exact comparison: they are
single values rather than sets, and nothing relaxes them.

**A rate is not printed beside the corpus target unless the whole corpus was
graded.** Every rate in the calibration block -- precision and recall included --
moves with the base rate of whatever set was graded, so a hand-picked subset's
rate cannot be compared to the corpus base rate. On a subset the report prints
the raw counts, labels its rates as computed on that subset, and withholds the
target. On the whole corpus the block is as it always was.

The five ruling values are read from POL-GEN-03's own ``licenses`` list rather
than written here, the way ``facts.py`` and ``money.py`` take every threshold
from the loaded policy. ``tribunal/`` is imported; nothing under ``tribunal/``
may import this module, and the answer key reaches the grader only after a
ruling already exists -- it must never reach a brief, a prompt or a transcript.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from tribunal import loader

__all__ = [
    "GRADED_FIELDS",
    "TWO_FIELD_SUBSET",
    "ANSWER_KEY_PATH",
    "DEFAULT_REPORT_PATH",
    "GradeError",
    "ReferralKey",
    "ReferralMatch",
    "Ruling",
    "FieldOutcome",
    "CaseScore",
    "Calibration",
    "GradeReport",
    "ruling_values",
    "money_or_none",
    "compare_money",
    "referral_keys",
    "referral_keys_of",
    "match_referrals",
    "load_answer_key",
    "answer_key_sha256",
    "expected_from_key",
    "key_as_produced",
    "produced_from_mapping",
    "produced_from_document",
    "score_case",
    "calibrate",
    "grade",
    "render_report",
    "main",
]


# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------
EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
ANSWER_KEY_PATH = EVAL_DIR / "answers" / "ground_truth.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "notes" / "2026-09-21-grader-self-test.md"

# The title the committed self-test report carries. A constant so the test that
# pins the committed file and the code that writes it cannot drift apart.
SELF_TEST_TITLE = "Grader self-test"
DEFAULT_TITLE = "Grading report"


# --------------------------------------------------------------------------
# What is graded
#
# The four fields are the whole of the ruling's verdict. ``confidence`` and
# ``explanation`` are part of the POL-GEN-03 object but are not scored: a
# written explanation is judged by a person, not by a string comparison.
# --------------------------------------------------------------------------
GRADED_FIELDS = ("ruling", "amount_sgd", "driver_compensation_sgd", "referrals")

# Reported as a contrast only. This subset is the mistake, not the metric.
TWO_FIELD_SUBSET = ("ruling", "amount_sgd")

# The clause that fixes the ruling vocabulary, located by id the way
# ``brief.py`` locates POL-RD-01. The five values themselves are read from it.
RULING_CLAUSE_ID = "POL-GEN-03"

# ``loader.load_policies`` requires a category. The general policy is the same
# document for both supported categories -- asserted in the tests -- so either
# will do when the only thing wanted is the general policy's ruling vocabulary.
CATEGORY_FOR_POLICY_LOOKUP = "ROUTE_DEVIATION"

# The published calibration target, and the one ruling value the calibration
# block is about. Both are declared here rather than derived from the key: a
# target read out of the key would compare the key with itself.
ESCALATE = "ESCALATE"
TARGET_ESCALATION_RATE = Decimal("0.172")
INDETERMINATE = "INDETERMINATE"

ONE_DECIMAL = Decimal("0.1")
THREE_DECIMALS = Decimal("0.001")


class GradeError(Exception):
    """A grading input is not the shape the contract requires."""


# --------------------------------------------------------------------------
# The ruling vocabulary, read from the policy
# --------------------------------------------------------------------------
def _general_policy() -> Dict[str, Any]:
    """The general policy, through the loader's own public API."""
    return loader.load_policies(CATEGORY_FOR_POLICY_LOOKUP)["general"]


def ruling_values() -> Tuple[str, ...]:
    """The five POL-GEN-03 ruling values, in the order the clause lists them.

    Read from the policy, not written here. A vocabulary hardcoded in the
    grader would keep accepting a value the policy had dropped, and the first
    symptom would be an accuracy figure nobody could reproduce.
    """
    for clause in _general_policy().get("clauses", []):
        if clause.get("id") != RULING_CLAUSE_ID:
            continue
        licenses = clause.get("licenses")
        if not isinstance(licenses, list) or not licenses:
            raise GradeError(
                "clause {0} carries no licence list, so the ruling vocabulary "
                "cannot be read from the policy".format(RULING_CLAUSE_ID)
            )
        return tuple(licenses)
    raise GradeError(
        "clause {0} is not in the general policy, so the ruling vocabulary "
        "cannot be read".format(RULING_CLAUSE_ID)
    )


# --------------------------------------------------------------------------
# Money
#
# One conversion path, ``Decimal(str(value))``, and no binary floating point
# arithmetic anywhere. ``None`` is carried through as ``None`` rather than
# folded to zero, because ``null`` and ``0`` are different answers.
# --------------------------------------------------------------------------
class _Unparseable:
    """Sentinel for a value that is not a number. Compares equal to nothing."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<not a number>"


UNPARSEABLE = _Unparseable()


def money_or_none(value: Any) -> Any:
    """Return ``None``, a ``Decimal``, or ``UNPARSEABLE`` for ``value``.

    ``None`` stays ``None``: a key that says ``null`` and a key that says ``0``
    are different answers and must not collapse into each other, which is why
    ``money._dec`` -- where ``None`` becomes zero, correctly, for a sum -- is
    not used here.

    Everything else goes through ``str`` first, so the conversion never touches
    the value's binary representation. That is also what makes a caller's
    ``json.load`` output safe: the decimal literal ``4.8`` survives as
    ``Decimal("4.8")`` rather than arriving as the nearest binary approximation
    of it. A ``bool`` is rejected, because ``True`` is not the number one.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else UNPARSEABLE
    if isinstance(value, bool):
        return UNPARSEABLE
    if isinstance(value, int):
        return Decimal(value)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return UNPARSEABLE
    return parsed if parsed.is_finite() else UNPARSEABLE


def money_type_note(value: Any) -> Optional[str]:
    """A note when a produced money value is not a JSON number.

    A produced amount should arrive as a JSON number. Anything else is a
    contract violation worth showing the reader, even when the value itself
    compares equal -- a run whose amounts all arrived as strings or as binary
    approximations is a run whose transport needs looking at.
    """
    if value is None or isinstance(value, Decimal):
        return None
    # ``bool`` is checked before ``int``: in Python ``True`` is an ``int``, so
    # the order of these two branches decides whether a boolean is reported.
    if isinstance(value, bool):
        return "arrived as a boolean, not a JSON number"
    if isinstance(value, int):
        return None
    if isinstance(value, str):
        return "arrived as a string, not a JSON number"
    return "arrived as {0}, not a JSON number".format(type(value).__name__)


def compare_money(expected: Any, produced: Any) -> bool:
    """True when both sides are the same amount, or both are ``null``.

    Equality is ``Decimal`` equality: ``0`` and ``0.00`` are the same number and
    compare equal, while ``null`` and ``0`` never do.
    """
    left = money_or_none(expected)
    right = money_or_none(produced)
    if left is UNPARSEABLE or right is UNPARSEABLE:
        return False
    if left is None or right is None:
        return left is None and right is None
    return left == right


def render_money(value: Any) -> str:
    """Render a money value for the report, without binary floating point."""
    if value is None:
        return "null"
    if value is UNPARSEABLE:
        return "<not a number>"
    return str(value)


# --------------------------------------------------------------------------
# Referrals
#
# A referral is free prose, so it is not graded by string equality. What it
# carries that a machine can check is the set of clause references, limb
# included where the expected referral states one. Whether the substance
# matches is a judgement for a person, which is why the report prints both
# texts side by side next to the automatic signal.
#
# The clause test is RECALL against the expected clauses, not set equality.
# It was set equality until 2026-09-22, when it scored a correct answer as a
# failure: deepseek-flash on case 207 named POL-NS-07, which the key requires,
# and also named POL-NS-09(d) -- the fuller legal path the key's own rationale
# for that case describes ("Compensation is withheld and the case escalates
# under POL-NS-09(d)"). Exact set equality called that extra clause spurious.
# A model that reaches the expected clause and adds another is answering a
# question about the case, not failing the grader, so the addition is reported
# and a person judges it.
#
# The loosening is one-directional. A referral invented where the key expects
# none is still a failure: a referral sends a case to a human, so manufacturing
# one is a defect in the same way that dropping one is.
#
# ``ruling``, ``amount_sgd`` and ``driver_compensation_sgd`` keep exact
# comparison and are untouched by any of this. They are single values rather
# than sets, and nothing here relaxes them.
# --------------------------------------------------------------------------
_CLAUSE_RE = re.compile(r"POL-[A-Z]{2,4}-[0-9]{2}")

# A limb is parenthesised and adjacent to the clause reference it belongs to.
# ``(c)``, ``(ii)`` and ``(4)`` are all limbs; ``(see also ...)`` is not.
_LIMB_RE = re.compile(r"\s*\(([A-Za-z]{1,3}|[0-9]{1,2})\)")


@dataclass(frozen=True)
class ReferralKey:
    """A clause reference a referral carries, with its limb when it states one."""

    clause: str
    limb: Optional[str] = None

    def render(self) -> str:
        """``POL-RD-06(c)`` where a limb is stated, ``POL-NS-07`` where it is not."""
        if self.limb is None:
            return self.clause
        return "{0}({1})".format(self.clause, self.limb)

    @property
    def sort_key(self) -> Tuple[str, str]:
        return (self.clause, self.limb or "")


def referral_keys(text: Any) -> Tuple[ReferralKey, ...]:
    """Every clause reference ``text`` carries, each with its own limb.

    A referral string may name more than one clause, so all of them are
    collected. A limb is only attached when it is written immediately after the
    clause it qualifies.
    """
    if not isinstance(text, str):
        return ()
    keys: List[ReferralKey] = []
    for match in _CLAUSE_RE.finditer(text):
        limb_match = _LIMB_RE.match(text, match.end())
        limb = limb_match.group(1).lower() if limb_match else None
        keys.append(ReferralKey(match.group(0), limb))
    return tuple(keys)


def referral_keys_of(referrals: Any) -> Tuple[ReferralKey, ...]:
    """Every clause reference across a list of referral strings."""
    if not isinstance(referrals, (list, tuple)):
        return ()
    keys: List[ReferralKey] = []
    for item in referrals:
        keys.extend(referral_keys(item))
    return tuple(keys)


def referral_strings_without_a_clause(referrals: Any) -> Tuple[str, ...]:
    """Referral entries that name no clause at all, so nothing can be matched.

    An entry with no clause reference is unmatchable, which means it can never
    satisfy an expected referral and can never be justified as a counterpart to
    one. It is reported rather than dropped.
    """
    if not isinstance(referrals, (list, tuple)):
        return ()
    out: List[str] = []
    for item in referrals:
        if not isinstance(item, str):
            out.append(repr(item))
        elif not referral_keys(item):
            out.append(item)
    return tuple(out)


def key_matches(expected: ReferralKey, produced: ReferralKey) -> bool:
    """Whether a produced clause reference satisfies an expected one.

    The expected side sets the precision. Where the expected referral states a
    limb -- ``POL-RD-06(c)`` -- the produced one must state the same limb; a
    referral to the right clause with the wrong limb is a different referral.
    Where the expected referral states no limb -- ``POL-NS-07`` -- the limb is
    not part of the key, so a produced limb neither helps nor hurts.
    """
    if expected.clause != produced.clause:
        return False
    if expected.limb is None:
        return True
    return expected.limb == produced.limb


@dataclass(frozen=True)
class ReferralMatch:
    """The outcome of comparing two referral lists by clause reference.

    ``unmatched_produced`` holds the clause references the produced side offered
    beyond the expected ones. Under the recall rule they are **additional**, not
    spurious: they are reported so a person can judge them, and they do not by
    themselves make the field fail. ``expected_matched`` and
    ``additional_clauses`` are the two counts the report prints per case.
    """

    matched: bool
    expected_keys: Tuple[ReferralKey, ...]
    produced_keys: Tuple[ReferralKey, ...]
    unmatched_expected: Tuple[ReferralKey, ...]
    unmatched_produced: Tuple[ReferralKey, ...]
    keyless_expected: Tuple[str, ...]
    keyless_produced: Tuple[str, ...]
    # True when the key expects no referral at all. This is the one case in
    # which anything produced is a defect rather than an addition, so it is
    # carried on the result rather than re-derived by every reader.
    expected_side_empty: bool = False

    @property
    def expected_matched(self) -> int:
        """How many of the expected clause references the produced side reached."""
        return len(self.expected_keys) - len(self.unmatched_expected)

    @property
    def additional_clauses(self) -> Tuple[ReferralKey, ...]:
        """Clauses offered that the key does not name at all.

        Not the same thing as the references left over after matching. A model
        that names an expected clause twice -- deepseek-flash did exactly that
        on case 207 -- leaves a leftover that is not an addition: it is the same
        clause again. Reporting it as one would tell a reader the model raised
        something the key had not, which is precisely the distinction the report
        exists to make.
        """
        seen: Dict[str, ReferralKey] = {}
        for produced in self.unmatched_produced:
            if any(key_matches(expected, produced) for expected in self.expected_keys):
                continue
            seen.setdefault(produced.render(), produced)
        return tuple(seen[key] for key in sorted(seen))

    @property
    def additions(self) -> str:
        """The additions, rendered whether or not the field passed.

        A passing case still has something to say here, which is the whole
        point of the recall rule: the reader is told what was offered beyond
        the key so they can decide whether it was noise or a better account.
        """
        parts: List[str] = []
        if self.additional_clauses:
            parts.append(
                "additional clause(s) offered: {0}".format(
                    ", ".join(key.render() for key in self.additional_clauses)
                )
            )
        if self.keyless_produced and not self.expected_side_empty:
            parts.append(
                "referral names no clause reference, so no clause of it was "
                "checked: {0}".format("; ".join(self.keyless_produced))
            )
        return "; ".join(parts)

    @property
    def detail(self) -> str:
        """Why the field failed, in the terms a reader needs."""
        if self.matched:
            return ""
        parts: List[str] = []

        if self.expected_side_empty:
            offered = sorted(key.render() for key in self.produced_keys)
            if offered:
                parts.append(
                    "a referral was produced where the key expects none: {0}".format(
                        ", ".join(offered)
                    )
                )
            if self.keyless_produced:
                parts.append(
                    "a referral was produced where the key expects none, and it "
                    "names no clause reference: {0}".format(
                        "; ".join(self.keyless_produced)
                    )
                )
            return "; ".join(parts)

        if self.unmatched_expected:
            parts.append(
                "expected referral not produced: {0}".format(
                    ", ".join(sorted(key.render() for key in self.unmatched_expected))
                )
            )
        if self.keyless_expected:
            parts.append(
                "the key's own referral names no clause, so no clause reference "
                "can be matched against it: {0}".format("; ".join(self.keyless_expected))
            )
        return "; ".join(parts)


def match_referrals(expected_referrals: Any, produced_referrals: Any) -> ReferralMatch:
    """Compare two referral lists by the clause references they carry.

    The test is **recall against the expected clauses**: every clause reference
    the key names must appear on the produced side, each met by a distinct
    produced reference. Clause references offered beyond those are recorded as
    additions and do not fail the field.

    The one direction that stays strict is the empty one. Where the key expects
    no referral at all, anything produced is an invented referral and fails.

    A key whose own referral names no clause cannot be confirmed automatically,
    so it does not pass silently. It is a limitation of the grader and is
    reported as one rather than charged to the model.
    """
    expected_keys = referral_keys_of(expected_referrals)
    produced_keys = referral_keys_of(produced_referrals)

    remaining = list(produced_keys)
    unmatched_expected: List[ReferralKey] = []
    for expected in expected_keys:
        for position, produced in enumerate(remaining):
            if key_matches(expected, produced):
                del remaining[position]
                break
        else:
            unmatched_expected.append(expected)

    keyless_expected = referral_strings_without_a_clause(expected_referrals)
    keyless_produced = referral_strings_without_a_clause(produced_referrals)

    expected_side_empty = not expected_keys and not keyless_expected
    produced_side_empty = not produced_keys and not keyless_produced

    if expected_side_empty:
        # Nothing was expected, so anything at all is invented.
        matched = produced_side_empty
    elif keyless_expected:
        # The key expects a referral but states no clause to check it against.
        matched = False
    else:
        matched = not unmatched_expected

    return ReferralMatch(
        matched=matched,
        expected_keys=expected_keys,
        produced_keys=produced_keys,
        unmatched_expected=tuple(unmatched_expected),
        unmatched_produced=tuple(remaining),
        keyless_expected=keyless_expected,
        keyless_produced=keyless_produced,
        expected_side_empty=expected_side_empty,
    )


# --------------------------------------------------------------------------
# Ruling objects
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Ruling:
    """A POL-GEN-03 ruling object reduced to what grading needs.

    The same shape carries the expected side and the produced side, so a case's
    two rulings can be printed beside each other. ``difficulty`` is carried on
    the expected side only; ``contract_notes`` is filled on the produced side
    only, when a produced record violates the ruling contract.
    """

    case_no: int
    ruling: Any
    amount_sgd: Any
    driver_compensation_sgd: Any
    referrals: Tuple[Any, ...] = ()
    difficulty: Optional[str] = None
    confidence: Any = None
    explanation: Any = None
    contract_notes: Tuple[Tuple[str, str], ...] = ()

    def field(self, name: str) -> Any:
        if name not in GRADED_FIELDS:
            raise GradeError("{0!r} is not a graded field".format(name))
        return getattr(self, name)

    def notes_for(self, name: str) -> Tuple[str, ...]:
        return tuple(note for field, note in self.contract_notes if field == name)


def expected_from_key(record: Mapping[str, Any]) -> Ruling:
    """One expected ruling, from a record of ``eval/answers/ground_truth.json``."""
    truth = record.get("ground_truth")
    if not isinstance(truth, Mapping):
        raise GradeError(
            "key record for case {0!r} carries no ground_truth object".format(
                record.get("case_no")
            )
        )
    referrals = truth.get("expected_referrals")
    return Ruling(
        case_no=int(record["case_no"]),
        ruling=truth.get("expected_ruling"),
        amount_sgd=truth.get("expected_amount_sgd"),
        driver_compensation_sgd=truth.get("expected_driver_compensation_sgd"),
        referrals=tuple(referrals) if isinstance(referrals, (list, tuple)) else (),
        difficulty=truth.get("difficulty"),
    )


def produced_from_mapping(record: Any, case_no: Optional[int] = None) -> Ruling:
    """One produced ruling, from whatever shape a caller hands over.

    A produced record is the judge's result object -- ``{"ruling": {...},
    "discarded_claims": [...]}`` -- or the bare POL-GEN-03 ruling object. The
    two are told apart by the type of the ``ruling`` key, which is an object in
    the first case and one of the five values in the second.

    Contract violations are recorded rather than raised: a run that produced a
    malformed ruling is a run to be graded and reported, not one to abort.
    """
    if not isinstance(record, Mapping):
        raise GradeError(
            "produced record for case {0!r} is {1}, not an object".format(
                case_no, type(record).__name__
            )
        )

    body = record.get("ruling")
    inner: Mapping[str, Any] = body if isinstance(body, Mapping) else record

    resolved_case_no = case_no
    if resolved_case_no is None:
        declared = record.get("case_no", inner.get("case_no"))
        if not isinstance(declared, int) or isinstance(declared, bool):
            raise GradeError(
                "produced record declares no usable case_no: {0!r}".format(declared)
            )
        resolved_case_no = declared

    notes: List[Tuple[str, str]] = []
    if "referrals" not in inner:
        notes.append(("referrals", "referrals is absent; treated as an empty array"))
    elif inner["referrals"] is not None and not isinstance(inner["referrals"], list):
        notes.append(
            (
                "referrals",
                "referrals arrived as {0}, not an array".format(
                    type(inner["referrals"]).__name__
                ),
            )
        )
    for name in ("amount_sgd", "driver_compensation_sgd"):
        if name in inner:
            note = money_type_note(inner[name])
            if note is not None:
                notes.append((name, "{0} {1}".format(name, note)))

    referrals = inner.get("referrals")
    return Ruling(
        case_no=resolved_case_no,
        ruling=inner.get("ruling"),
        amount_sgd=inner.get("amount_sgd"),
        driver_compensation_sgd=inner.get("driver_compensation_sgd"),
        referrals=tuple(referrals) if isinstance(referrals, list) else (),
        confidence=inner.get("confidence"),
        explanation=inner.get("explanation"),
        contract_notes=tuple(notes),
    )


def key_as_produced(key: Mapping[int, Ruling]) -> Dict[int, Dict[str, Any]]:
    """Feed each case's own ground truth back in as though a judge had produced it.

    This is the validation the grader is built around: the key is by definition
    a perfect answer, so grading it against itself must score every case on
    every field. Any other result means the grader is wrong.
    """
    produced: Dict[int, Dict[str, Any]] = {}
    for case_no, expected in key.items():
        produced[case_no] = {
            "case_no": case_no,
            "ruling": {
                "ruling": expected.ruling,
                "amount_sgd": expected.amount_sgd,
                "driver_compensation_sgd": expected.driver_compensation_sgd,
                "referrals": list(expected.referrals),
            },
        }
    return produced


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldOutcome:
    """Whether one field of one case agreed with the key."""

    field: str
    correct: bool
    detail: str = ""


@dataclass(frozen=True)
class CaseScore:
    """Every graded field of one case, plus the four-field verdict."""

    case_no: int
    expected: Ruling
    produced: Optional[Ruling]
    outcomes: Tuple[FieldOutcome, ...]

    @property
    def by_field(self) -> Dict[str, FieldOutcome]:
        return {outcome.field: outcome for outcome in self.outcomes}

    def correct_on(self, field: str) -> bool:
        return self.by_field[field].correct

    @property
    def exact(self) -> bool:
        """The metric that matters: all four fields agree."""
        return all(outcome.correct for outcome in self.outcomes)

    @property
    def two_field(self) -> bool:
        """The metric this project must not report. Printed only as a contrast."""
        return all(self.by_field[name].correct for name in TWO_FIELD_SUBSET)

    @property
    def failed_fields(self) -> Tuple[str, ...]:
        return tuple(
            outcome.field for outcome in self.outcomes if not outcome.correct
        )

    @property
    def correct_fields(self) -> Tuple[str, ...]:
        return tuple(
            outcome.field for outcome in self.outcomes if outcome.correct
        )

    @property
    def expected_escalates(self) -> bool:
        return self.expected.ruling == ESCALATE

    @property
    def produced_escalates(self) -> bool:
        return self.produced is not None and self.produced.ruling == ESCALATE


def score_case(
    case_no: int, expected: Ruling, produced: Optional[Ruling]
) -> CaseScore:
    """Score one produced ruling against one expected ruling.

    A case with no produced ruling fails every field: an absent ruling is not a
    blank to be skipped, it is four wrong answers.
    """
    vocabulary = set(ruling_values())

    if produced is None:
        outcomes = tuple(
            FieldOutcome(name, False, "no ruling produced") for name in GRADED_FIELDS
        )
        return CaseScore(case_no, expected, None, outcomes)

    # ruling -- exact string, one of the five POL-GEN-03 values.
    produced_ruling = produced.ruling
    ruling_correct = isinstance(produced_ruling, str) and produced_ruling == expected.ruling
    if ruling_correct:
        ruling_detail = ""
    else:
        ruling_detail = "expected {0!r}, produced {1!r}".format(
            expected.ruling, produced_ruling
        )
        if isinstance(produced_ruling, str) and produced_ruling not in vocabulary:
            ruling_detail += " (not a POL-GEN-03 value)"
    ruling_detail = _with_notes(ruling_detail, produced.notes_for("ruling"))

    # amount_sgd and driver_compensation_sgd -- Decimal, and null is not zero.
    money_outcomes: List[FieldOutcome] = []
    for name in ("amount_sgd", "driver_compensation_sgd"):
        correct = compare_money(expected.field(name), produced.field(name))
        if correct:
            detail = ""
        else:
            detail = "expected {0}, produced {1}".format(
                render_money(money_or_none(expected.field(name))),
                render_money(money_or_none(produced.field(name))),
            )
        money_outcomes.append(
            FieldOutcome(name, correct, _with_notes(detail, produced.notes_for(name)))
        )

    # referrals -- by clause reference, limb included where the key states one.
    match = match_referrals(expected.referrals, produced.referrals)
    referral_detail = _with_notes(match.detail, produced.notes_for("referrals"))

    outcomes = (
        FieldOutcome("ruling", ruling_correct, ruling_detail),
        money_outcomes[0],
        money_outcomes[1],
        FieldOutcome("referrals", match.matched, referral_detail),
    )
    return CaseScore(case_no, expected, produced, outcomes)


def _with_notes(detail: str, notes: Sequence[str]) -> str:
    """Join a failure detail with any contract notes, without inventing one."""
    parts = [part for part in [detail, *notes] if part]
    return "; ".join(parts)


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------
def _percent(numerator: int, denominator: int) -> Optional[Decimal]:
    """A percentage to one decimal place, or ``None`` when the divisor is zero."""
    if denominator == 0:
        return None
    return (Decimal(numerator) / Decimal(denominator) * 100).quantize(
        ONE_DECIMAL, rounding=ROUND_HALF_UP
    )


def _ratio(numerator: int, denominator: int) -> Optional[Decimal]:
    """A ratio to three decimal places, or ``None`` when the divisor is zero."""
    if denominator == 0:
        return None
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        THREE_DECIMALS, rounding=ROUND_HALF_UP
    )


def render_percent(value: Optional[Decimal]) -> str:
    """``17.2%``, or a plain statement that there is nothing to divide by."""
    if value is None:
        return "n/a"
    return "{0}%".format(value)


def render_ratio(value: Optional[Decimal]) -> str:
    """``1.0``, ``0.8``, ``0.172`` -- at least one decimal, no trailing noise."""
    if value is None:
        return "n/a"
    text = str(value.normalize())
    if "." not in text:
        text += ".0"
    return text


@dataclass(frozen=True)
class Calibration:
    """How the run handles escalation, reported apart from the accuracy score.

    Over-escalation and under-escalation are kept as separate counts because
    they are different failures with different costs. A system that escalates
    everything scores perfectly on recall and is useless; a system that is
    confident on the INDETERMINATE cases is wrong in the way that matters most.
    Averaging either into a single rate would hide both.
    """

    total: int
    expected_escalations: Tuple[int, ...]
    produced_escalations: Tuple[int, ...]
    true_positives: Tuple[int, ...]
    false_positives: Tuple[int, ...]
    false_negatives: Tuple[int, ...]
    target: Decimal
    indeterminate_expected: Tuple[int, ...]
    indeterminate_escalated: Tuple[int, ...]
    substantive_expected: Tuple[int, ...]
    substantive_escalated: Tuple[int, ...]

    @property
    def rate(self) -> Optional[Decimal]:
        """The escalation rate as a percentage, against ``target``."""
        return _percent(len(self.produced_escalations), self.total)

    @property
    def target_rate(self) -> Decimal:
        return (self.target * 100).quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)

    @property
    def rate_off_target(self) -> bool:
        return self.rate != self.target_rate

    @property
    def precision(self) -> Optional[Decimal]:
        """Of the cases the run escalated, how many the key escalates."""
        predicted = len(self.true_positives) + len(self.false_positives)
        return _ratio(len(self.true_positives), predicted)

    @property
    def recall(self) -> Optional[Decimal]:
        """Of the cases the key escalates, how many the run escalated."""
        actual = len(self.true_positives) + len(self.false_negatives)
        return _ratio(len(self.true_positives), actual)

    @property
    def over_escalations(self) -> Tuple[int, ...]:
        return self.false_positives

    @property
    def under_escalations(self) -> Tuple[int, ...]:
        return self.false_negatives

    @property
    def indeterminate_ruled_confidently(self) -> Tuple[int, ...]:
        """INDETERMINATE cases the run ruled on rather than escalating.

        The record does not settle these four. A run that answers them anyway
        is not being decisive, it is inventing an answer, and that is the
        failure this block exists to keep visible.
        """
        escalated = set(self.indeterminate_escalated)
        return tuple(
            case_no for case_no in self.indeterminate_expected if case_no not in escalated
        )


def calibrate(scores: Sequence[CaseScore]) -> Calibration:
    """Compute the escalation block for a graded set of cases."""
    expected_escalations = tuple(
        score.case_no for score in scores if score.expected_escalates
    )
    produced_escalations = tuple(
        score.case_no for score in scores if score.produced_escalates
    )

    expected_set = set(expected_escalations)
    produced_set = set(produced_escalations)

    indeterminate_expected = tuple(
        score.case_no
        for score in scores
        if score.expected_escalates and score.expected.difficulty == INDETERMINATE
    )
    substantive_expected = tuple(
        score.case_no
        for score in scores
        if score.expected_escalates and score.expected.difficulty != INDETERMINATE
    )

    return Calibration(
        total=len(scores),
        expected_escalations=expected_escalations,
        produced_escalations=produced_escalations,
        true_positives=tuple(sorted(expected_set & produced_set)),
        false_positives=tuple(sorted(produced_set - expected_set)),
        false_negatives=tuple(sorted(expected_set - produced_set)),
        target=TARGET_ESCALATION_RATE,
        indeterminate_expected=indeterminate_expected,
        indeterminate_escalated=tuple(
            case_no for case_no in indeterminate_expected if case_no in produced_set
        ),
        substantive_expected=substantive_expected,
        substantive_escalated=tuple(
            case_no for case_no in substantive_expected if case_no in produced_set
        ),
    )


# --------------------------------------------------------------------------
# The answer key
# --------------------------------------------------------------------------
def answer_key_sha256(path: Path = ANSWER_KEY_PATH) -> str:
    """The SHA-256 of the answer key file's bytes.

    A run's provenance records which key it was scored against. Reading the key
    is this module's business and nobody else's, so a caller that wants the
    digest asks for it here rather than opening the file itself — the runner
    records the digest without ever touching the key.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_answer_key(path: Path = ANSWER_KEY_PATH) -> Dict[int, Ruling]:
    """Load the answer key, keyed by case number.

    Parsed with ``parse_float=Decimal``, the same hook ``loader._read_json``
    uses, so every money value in the key arrives as the decimal literal that
    was written rather than as the nearest binary approximation of it.
    """
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            document = json.load(handle, parse_float=Decimal)
    except FileNotFoundError as exc:
        raise GradeError("answer key not found: {0}".format(path)) from exc
    except json.JSONDecodeError as exc:
        raise GradeError("invalid JSON in {0}: {1}".format(path, exc)) from exc

    if not isinstance(document, list):
        raise GradeError("the answer key must be a JSON array, got {0}".format(
            type(document).__name__
        ))

    key: Dict[int, Ruling] = {}
    for record in document:
        if not isinstance(record, Mapping):
            raise GradeError("an answer-key record is not an object: {0!r}".format(record))
        expected = expected_from_key(record)
        if expected.case_no in key:
            raise GradeError("case {0} appears twice in the answer key".format(expected.case_no))
        key[expected.case_no] = expected
    if not key:
        raise GradeError("the answer key carries no cases")
    return key


# --------------------------------------------------------------------------
# Staleness
# --------------------------------------------------------------------------
# A cached result is evidence about the code that produced it and about nothing
# else. These are the three answers to "does this result still belong to the
# code running now", and the third is not a synonym for the first.
STALENESS_CURRENT = "current"
STALENESS_STALE = "stale"
STALENESS_UNKNOWN = "unknown"

# A result can be stale because the facts its agents were given changed or
# because the instructions they were given changed, and those are not the same
# finding. The first means the brief moved, the second that the prompts did.
# They are named apart everywhere they are reported, because they call for
# different responses: a moved brief is answered by re-reading the case, a moved
# prompt by re-reading what the agents were told to do with it.
MOVED_BRIEF = "brief"
MOVED_PROMPTS = "prompt"


@dataclass(frozen=True)
class Staleness:
    """Which graded cases were produced by code this code is no longer.

    Supplied by the caller, because only the caller knows what a cached result
    was produced from: the grader scores rulings and never sees a cache. A
    cached result carries the digest of the exact brief bytes its agents were
    handed and the digest of the prompts they were given, so rebuilding both and
    comparing establishes whether the result still belongs to this code -- a
    fact about the cache, not about the ruling.

    ``checked`` is False when nobody looked, and that is **not** the same as
    having looked and found nothing. A report printing "0 stale" without having
    rebuilt a single brief would be inventing evidence. A case whose brief
    cannot be rebuilt at all is ``unknown`` rather than current, for the same
    reason an unreadable working tree is not clean.

    ``stale`` is the union of ``stale_brief`` and ``stale_prompts``, so a caller
    that only asks "has this result been moved past" need not know there are two
    channels. A caller that *reports* must use the two rather than the union:
    merging them into one word is the thing those fields exist to prevent.
    """

    checked: bool = False
    stale: Tuple[int, ...] = ()
    unknown: Tuple[int, ...] = ()
    # Recorded, and no longer matching.
    stale_brief: Tuple[int, ...] = ()
    stale_prompts: Tuple[int, ...] = ()
    # No prompts digest was recorded, so the prompt half of the check could not
    # be made for this case at all. A result written before the field was kept
    # is not a result whose prompts are known to match.
    unchecked_prompts: Tuple[int, ...] = ()

    @property
    def mixed(self) -> bool:
        """Whether the graded set is not one run.

        A stale result and a result whose staleness could not be established
        both break the set's claim to be a single measurement, and neither is
        folded away into a score.
        """
        return bool(self.stale) or bool(self.unknown)

    def status_of(self, case_no: int) -> str:
        """``current``, ``stale`` or ``unknown`` for one graded case.

        Stale wins over unknown, deliberately: a digest that was recorded and no
        longer matches is a finding, and reporting it as merely unestablished
        would hide it.
        """
        if case_no in self.stale:
            return STALENESS_STALE
        if case_no in self.unknown:
            return STALENESS_UNKNOWN
        return STALENESS_CURRENT

    def moved_for(self, case_no: int) -> Tuple[str, ...]:
        """Which recorded digests moved for one case, named, in a fixed order.

        Empty unless the case is stale. Both may be present: a result produced
        by an older brief under older prompts is stale for both reasons, and a
        report that said only "stale" would leave the reader unable to tell
        which response the result calls for.
        """
        moved: List[str] = []
        if case_no in self.stale_brief:
            moved.append(MOVED_BRIEF)
        if case_no in self.stale_prompts:
            moved.append(MOVED_PROMPTS)
        return tuple(moved)


# A graded result's advocates were either asked by the run that reports it or
# borrowed from another run, and those are the only two answers. Named rather
# than written as literals in the two places that render them, so the table cell
# and the block below it cannot come to disagree.
ADVOCATES_CALLED_HERE = "called here"
ADVOCATES_REPLAYED = "replayed"


@dataclass(frozen=True)
class ReplayFacts:
    """Which graded results came from a run that reused another run's advocates.

    Not a synonym for staleness, and not a weaker version of it. Staleness asks
    whether a result still belongs to this code. This says that part of the
    arbitration was not performed by the run that reports it: the rider and
    driver outputs are another run's, so the figure is the judge's behaviour on
    fixed inputs rather than the whole pipeline's, and a reader who takes it for
    a pipeline number has the wrong model of what was measured.

    ``sources`` is every run directory the advocates came from, as the cache
    entries recorded it, and ``cases`` is which graded cases reused them. Both,
    because a reader needs to know how much of the figure is affected *and* where
    the borrowed half came from.

    ``checked`` is False when nobody looked, which is not the same as having
    looked and found none: a report built straight from rulings must render
    nothing about a question it was never asked.
    """

    checked: bool = False
    sources: Tuple[str, ...] = ()
    cases: Tuple[int, ...] = ()
    # What the borrowed calls cost the run that made them. Reported because a
    # reader comparing runs needs it, and added to nothing: this is not part of
    # what the run being reported spent.
    tokens: int = 0

    @property
    def any(self) -> bool:
        """Whether any graded result reused another run's advocates."""
        return bool(self.cases)

    def status_of(self, case_no: int) -> str:
        """``replayed`` or ``called here`` for one graded case."""
        return ADVOCATES_REPLAYED if case_no in self.cases else ADVOCATES_CALLED_HERE


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class GradeReport:
    """Everything a reader needs to see which field a model actually fails on.

    ``corpus_cases`` is the whole answer key's case set, which is not the same
    as the graded set whenever a caller grades a subset. It is carried so the
    report can say whether the numbers it prints may be compared to the corpus
    base rate, rather than printing the comparison and hoping.

    ``staleness`` is carried for the same reason and is the stronger claim of
    the two: a set whose cases were produced by different versions of the brief
    is not one run at all, so its exact-match figure measures no single thing.

    ``replay`` is carried because it changes what the figures are figures *of*.
    A graded set whose advocates were reused from another run measures the judge
    on fixed inputs; the report says so wherever it prints a number, and it says
    nothing at all when nobody asked.
    """

    cases: Tuple[CaseScore, ...]
    calibration: Calibration
    unexpected_cases: Tuple[int, ...] = ()
    corpus_cases: Tuple[int, ...] = ()
    staleness: Staleness = Staleness()
    replay: ReplayFacts = ReplayFacts()

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def graded_cases(self) -> Tuple[int, ...]:
        """The case numbers actually graded, in the order they were scored."""
        return tuple(score.case_no for score in self.cases)

    @property
    def corpus_size(self) -> int:
        return len(self.corpus_cases)

    @property
    def grades_full_corpus(self) -> bool:
        """Whether the graded set is the whole key.

        ``False`` when the corpus is unknown, because a comparability claim that
        cannot be established must never read as established -- the same rule
        the runner applies to a working tree it could not read.
        """
        if not self.corpus_cases:
            return False
        return set(self.graded_cases) == set(self.corpus_cases)

    @property
    def unproduced(self) -> Tuple[int, ...]:
        return tuple(score.case_no for score in self.cases if score.produced is None)

    def field_tally(self, field: str) -> Tuple[int, int]:
        correct = sum(1 for score in self.cases if score.correct_on(field))
        return correct, self.total

    @property
    def exact_matches(self) -> int:
        return sum(1 for score in self.cases if score.exact)

    @property
    def two_field_matches(self) -> int:
        return sum(1 for score in self.cases if score.two_field)

    @property
    def failures(self) -> Tuple[CaseScore, ...]:
        return tuple(score for score in self.cases if not score.exact)

    @property
    def referral_cases(self) -> Tuple[CaseScore, ...]:
        """Cases where either side carries a referral, so both texts are shown."""
        return tuple(
            score
            for score in self.cases
            if score.expected.referrals or (score.produced and score.produced.referrals)
        )

    @property
    def encoding_notes(self) -> Tuple[Tuple[int, str, str], ...]:
        """Produced fields whose JSON type was not what the contract requires."""
        out: List[Tuple[int, str, str]] = []
        for score in self.cases:
            if score.produced is None:
                continue
            for field, note in score.produced.contract_notes:
                out.append((score.case_no, field, note))
        return tuple(out)


def grade(
    produced: Mapping[int, Any],
    key: Optional[Mapping[int, Ruling]] = None,
    corpus: Optional[Mapping[int, Ruling]] = None,
    staleness: Optional[Staleness] = None,
    replay: Optional[ReplayFacts] = None,
) -> GradeReport:
    """Grade a produced-ruling mapping against the key.

    ``produced`` maps a case number to the judge's result object, the bare
    POL-GEN-03 ruling object, or ``None`` where no ruling was produced. Cases
    the key does not carry are reported as unexpected rather than scored.

    ``key`` may be a subset of the answer key, which is what grading a partial
    run wants: a run that answered three cases should report an accuracy over
    three rather than over twenty-nine of which it answered three. When it is a
    subset, ``corpus`` must be the whole key, so the report can tell a reader
    that the rates it prints were computed on a selected set and are not
    comparable to the corpus base rate. Omitting ``corpus`` says the graded set
    *is* the key, which is true for every caller that loads the key itself.

    ``staleness`` is the caller's answer to whether each cached result still
    belongs to the code running now. It is not the grader's to work out, and it
    defaults to "nobody looked" rather than to "all current", because a report
    must not claim a check that was never made.

    ``replay`` is the caller's answer to whether the advocates were asked by the
    run that produced these results. It is not the grader's to work out either,
    and it defaults to "nobody looked", which renders nothing -- so a report
    built straight from rulings, as the grader's own self-test is, is unchanged
    by its existence.
    """
    resolved_key = load_answer_key() if key is None else dict(key)
    resolved_corpus = resolved_key if corpus is None else dict(corpus)

    cases: List[CaseScore] = []
    for case_no in sorted(resolved_key):
        raw = produced.get(case_no)
        ruling = None if raw is None else produced_from_mapping(raw, case_no)
        cases.append(score_case(case_no, resolved_key[case_no], ruling))

    unexpected = tuple(sorted(set(produced) - set(resolved_key)))
    return GradeReport(
        tuple(cases),
        calibrate(cases),
        unexpected,
        corpus_cases=tuple(sorted(resolved_corpus)),
        staleness=Staleness() if staleness is None else staleness,
        replay=ReplayFacts() if replay is None else replay,
    )


def _render_referral_list(referrals: Sequence[Any]) -> str:
    """Render a referral list so both texts can be read side by side."""
    if not referrals:
        return "_(none)_"
    return "; ".join(
        "{0!r}".format(item) if not isinstance(item, str) else '"' + item + '"'
        for item in referrals
    )


def _render_brief_status(staleness: Staleness, case_no: int) -> str:
    """The ``cached`` cell for one case: does its result belong to this code?

    ``not checked`` is a third answer and is deliberately not spelled ``ok``.

    A stale cell names which digest moved rather than saying only "stale". The
    two are different findings -- the facts changed, or the instructions did --
    and a reader who cannot tell them apart cannot tell which one to go and look
    at.
    """
    if not staleness.checked:
        return "not checked"
    status = staleness.status_of(case_no)
    if status == STALENESS_STALE:
        moved = staleness.moved_for(case_no)
        if not moved:
            return "**STALE**"
        return "**STALE ({0})**".format(", ".join(moved))
    if status == STALENESS_UNKNOWN:
        return "unknown"
    return "current"


def _render_case_table(report: GradeReport) -> List[str]:
    """One row per case: which fields agreed, and whether the four-field test passed.

    A ``cached`` column is added only when somebody checked whether each cached
    result still belongs to this code. That column is about the cache rather
    than the ruling: a stale row is a result earlier code produced, so its
    agreement with the key says what that earlier code did — which is worth
    knowing, and is not the same as knowing what the code does now. A report
    built straight from rulings gets no such column, because it has nothing to
    put in one.

    The column is not headed ``brief`` any more. It answers for the prompt
    digest as well, and a heading naming one of the two would be the merge this
    report is required not to make.

    An ``advocates`` column is added only when some result reused another run's
    advocates, and it says which. It is a third question again -- not whether the
    result belongs to this code, but whether this code asked the agents -- and it
    is answered per row so a reader can see how much of the table is affected
    without counting a sentence above it.
    """
    checked = report.staleness.checked
    replayed = report.replay.any
    headers = ["case", *GRADED_FIELDS, "exact"]
    if checked:
        headers.append("cached")
    if replayed:
        headers.append("advocates")
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
    ]
    for score in report.cases:
        cells = [
            "ok" if score.correct_on(name) else "**FAIL**" for name in GRADED_FIELDS
        ]
        row = [str(score.case_no), *cells, "ok" if score.exact else "**FAIL**"]
        if checked:
            row.append(_render_brief_status(report.staleness, score.case_no))
        if replayed:
            row.append(report.replay.status_of(score.case_no))
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _render_staleness(report: GradeReport) -> List[str]:
    """The cached-results block, and the caveat that follows from a mixed set.

    Empty when nobody looked, because the honest output of a report built
    straight from rulings is silence about a check that was never made.

    The brief and the prompt are reported as two separate findings. They are not
    interchangeable -- one means the facts the agents were given changed, the
    other that their instructions did -- and a reader deciding what to do next
    needs to know which of the two happened.
    """
    staleness = report.staleness
    if not staleness.checked:
        return []

    # The leading blank separates this block from the table above it; the
    # trailing separation is supplied by whatever the caller renders next.
    lines: List[str] = [""]
    if not staleness.mixed:
        lines.append(
            "Every graded case was produced by the brief and the prompts this "
            "code builds now, so the exact-match figure above is one measurement."
        )
        return lines

    lines.append("### Cached results")
    lines.append("")
    lines.append(
        "A cached result is evidence about the code that produced it and about "
        "nothing else. Each result records the digest of the exact brief bytes "
        "its agents were handed and the digest of the prompts they were given, "
        "so both are rebuilt now and compared with what was recorded. This does "
        "not say a stale result is wrong; it says it is not a measurement of "
        "this code."
    )
    lines.append("")
    if staleness.stale_brief:
        lines.append(
            "The brief has moved for {0} of {1}: {2}. The facts these agents were "
            "handed are not the facts this code builds.".format(
                len(staleness.stale_brief),
                report.total,
                ", ".join(str(case_no) for case_no in staleness.stale_brief),
            )
        )
        lines.append("")
    if staleness.stale_prompts:
        lines.append(
            "The prompts have moved for {0} of {1}: {2}. These agents were told "
            "to do something other than what this code now asks of them.".format(
                len(staleness.stale_prompts),
                report.total,
                ", ".join(str(case_no) for case_no in staleness.stale_prompts),
            )
        )
        lines.append("")
    if staleness.unchecked_prompts:
        lines.append(
            "The prompts digest was not recorded for {0} of {1} results, so "
            "whether the prompts they were given are the ones this code ships "
            "cannot be established for them at all.".format(
                len(staleness.unchecked_prompts), report.total
            )
        )
        lines.append("")
    if staleness.unknown:
        lines.append(
            "Staleness could not be established for: {0}. A brief that cannot be "
            "rebuilt is not a brief that still matches.".format(
                ", ".join(str(case_no) for case_no in staleness.unknown)
            )
        )
        lines.append("")
    lines.append(
        "**A mixed set is not one run.** The {0}/{1} exact-match figure above "
        "spans results produced by more than one version of the brief or the "
        "prompts, so it is not a single measurement of any one version of this "
        "code.".format(report.exact_matches, report.total)
    )
    return lines


def _render_replay(report: GradeReport) -> List[str]:
    """The advocates-replayed block, and what it makes the figures measure.

    Empty when nobody looked, for the same reason the staleness block is: the
    honest output of a report built straight from rulings is silence about a
    question it was never asked.

    A replayed run is not a stale run and must not be reported as one. Staleness
    says a result came from older code; this says the run reporting it did not
    perform part of the arbitration at all. Both change what a figure measures,
    which is why both are printed beside the figures, and neither is a reason to
    withhold the number.
    """
    replay = report.replay
    if not replay.checked or not replay.any:
        return []

    sources = ", ".join("`{0}`".format(source) for source in replay.sources)
    return [
        "",
        "### Advocates replayed",
        "",
        "For {0} of {1} graded cases the rider and driver outputs were **reused "
        "from another run** and were not regenerated by the run that produced "
        "these results: only the judge was called for those cases. Every figure "
        "in this report is therefore the judge's behaviour on fixed inputs rather "
        "than a measurement of the whole pipeline. The brief and both advocate "
        "prompts were checked against what that run recorded, and against the "
        "model, before any case was accepted.".format(len(replay.cases), report.total),
        "",
        "The advocates came from {0}.".format(sources or "an unrecorded source"),
        "",
        "Those calls cost {0:,} tokens, billed to the run that made them and not "
        "to this one. No figure in this report includes them.".format(replay.tokens),
    ]


def _render_failures(report: GradeReport) -> List[str]:
    """The failures in full, so no reader has to go looking for them."""
    failures = report.failures
    if not failures:
        return ["No case failed. Every graded field of every case agrees with the key.", ""]

    lines: List[str] = []
    for score in failures:
        lines.append("### Case {0}".format(score.case_no))
        lines.append("")
        lines.append("Failed on: {0}".format(", ".join(score.failed_fields)))
        lines.append("")
        for outcome in score.outcomes:
            if outcome.correct:
                continue
            lines.append("- **{0}** — {1}".format(outcome.field, outcome.detail))
        lines.append("")
    return lines


def _render_referrals(report: GradeReport) -> List[str]:
    """Expected and produced referral text side by side, with the clause signal.

    The clause match is the automatic part. Whether the substance matches is a
    judgement a person makes, and they cannot make it from a boolean.

    Two counts are printed per case, because the recall rule turns on both: how
    many of the expected clauses were reached, and how many clauses were offered
    beyond them. A case that reached every expected clause and added one is a
    pass with something to look at, which is exactly the case the old set
    equality scored as a failure.
    """
    lines: List[str] = []
    cases = report.referral_cases
    if not cases:
        return ["No case carries a referral on either side.", ""]

    for score in cases:
        expected_referrals = score.expected.referrals
        produced_referrals = score.produced.referrals if score.produced else ()
        match = match_referrals(expected_referrals, produced_referrals)

        lines.append("### Case {0} — {1}".format(score.case_no, "clause match" if match.matched else "**no clause match**"))
        lines.append("")
        lines.append("- expected: {0}".format(_render_referral_list(expected_referrals)))
        lines.append("- produced: {0}".format(_render_referral_list(produced_referrals)))
        lines.append(
            "- clause keys, expected: {0}".format(
                ", ".join(sorted(key.render() for key in match.expected_keys)) or "_(none)_"
            )
        )
        lines.append(
            "- clause keys, produced: {0}".format(
                ", ".join(sorted(key.render() for key in match.produced_keys)) or "_(none)_"
            )
        )
        lines.append(
            "- expected clauses matched: {0} of {1}".format(
                match.expected_matched, len(match.expected_keys)
            )
        )
        lines.append(
            "- additional clauses offered: {0}".format(
                ", ".join(sorted(key.render() for key in match.additional_clauses))
                or "_(none)_"
            )
        )
        if match.additions:
            lines.append("- {0}".format(match.additions))
        if not match.matched:
            lines.append("- {0}".format(match.detail))
        lines.append("")
    return lines


def _plural(count: int, noun: str) -> str:
    """``1 case`` / ``2 cases``, so a count of one does not read as a typo.

    The full corpus always has four INDETERMINATE escalations, so this never
    showed there; a subset can have one, and "1 cases" reads like a bug.
    """
    return "{0} {1}".format(count, noun if count == 1 else noun + "s")


def _render_raw_counts(calibration: Calibration) -> List[str]:
    """The counts a selected subset can be judged on, with the cases behind each.

    Printed only when the graded set is not the whole corpus. Rates move with
    the base rate of the set they are computed on; counts do not, so these are
    the figures that survive subsetting intact.
    """
    rows = [
        (
            "True positives (key and run both ESCALATE)",
            calibration.true_positives,
        ),
        (
            "False positives (run ESCALATE, key does not)",
            calibration.false_positives,
        ),
        (
            "False negatives (key ESCALATE, run does not)",
            calibration.false_negatives,
        ),
        ("Over-escalations (= false positives)", calibration.over_escalations),
        ("Under-escalations (= false negatives)", calibration.under_escalations),
        ("Expected escalations in this set", calibration.expected_escalations),
        ("Produced escalations in this set", calibration.produced_escalations),
    ]

    lines = [
        "### Raw counts — these are what survive subsetting",
        "",
        "Rates move with the base rate of the set they were computed on, "
        "precision and recall included. On a selected subset they are not "
        "comparable to the corpus base rate. The counts below do not move.",
        "",
        "| | count | cases |",
        "|---|---|---|",
    ]
    for label, case_numbers in rows:
        lines.append(
            "| {0} | {1} | {2} |".format(
                label,
                len(case_numbers),
                ", ".join(str(case_no) for case_no in case_numbers) or "_none_",
            )
        )
    lines.append("")
    lines.append(
        "Rates on a selected subset are not comparable to the corpus base rate, "
        "so the corpus target is deliberately not printed beside them."
    )
    lines.append("")
    return lines


def _render_calibration(report: GradeReport) -> List[str]:
    """The escalation block, with over- and under-escalation counted separately.

    The block knows what set it is describing. On the whole corpus the rates may
    be compared to the published target, so the target is printed beside them as
    it always was. On a selected subset they may not: every rate here --
    precision and recall included -- moves with the base rate of whatever set
    was graded, and only the raw counts survive subsetting intact. Printing a
    hand-picked subset's 66.7% beside the corpus's 17.2% invites the conclusion
    that the system over-escalates, when the subset was selected to contain
    escalations. So on a subset the target is withheld, the counts are printed,
    and the reader is told in one line why.
    """
    calibration = report.calibration
    full = report.grades_full_corpus
    on_these = "" if full else " (on these {0} cases)".format(calibration.total)

    lines = [
        "| | |",
        "|---|---|",
        "| Cases graded | {0} |".format(calibration.total),
        "| Cases graded, by number | {0} |".format(
            ", ".join(str(case_no) for case_no in report.graded_cases) or "_none_"
        ),
        "| Whole corpus graded | {0} |".format(
            "yes — all {0} cases".format(report.corpus_size)
            if full
            else "no — {0} of {1} cases".format(calibration.total, report.corpus_size)
        ),
        "| Expected escalations | {0} |".format(len(calibration.expected_escalations)),
        "| Produced escalations | {0} |".format(len(calibration.produced_escalations)),
    ]

    if full:
        lines.extend(
            [
                "| **Escalation rate** | **{0}** |".format(
                    render_percent(calibration.rate)
                ),
                "| Target | {0} |".format(render_percent(calibration.target_rate)),
                "| Off target | {0} |".format(
                    "yes" if calibration.rate_off_target else "no"
                ),
            ]
        )
    else:
        lines.append(
            "| **Escalation rate{0}** | **{1}** |".format(
                on_these, render_percent(calibration.rate)
            )
        )

    lines.extend(
        [
            "| Precision on ESCALATE{0} | {1} |".format(
                on_these,
                "{0} of {1} = {2}".format(
                    len(calibration.true_positives),
                    len(calibration.true_positives) + len(calibration.false_positives),
                    render_ratio(calibration.precision),
                ),
            ),
            "| Recall on ESCALATE{0} | {1} |".format(
                on_these,
                "{0} of {1} = {2}".format(
                    len(calibration.true_positives),
                    len(calibration.true_positives) + len(calibration.false_negatives),
                    render_ratio(calibration.recall),
                ),
            ),
            "",
        ]
    )

    if not full:
        lines.extend(_render_raw_counts(calibration))

    lines.extend(
        [
            "### Over-escalation and under-escalation, counted separately",
            "",
            "These are different failures and are never summed into one figure. "
            "Over-escalation is a case the run sent to a human that did not need one; "
            "under-escalation is a case it decided that a human should have decided.",
            "",
            "| | count | cases |",
            "|---|---|---|",
            "| Over-escalations (produced ESCALATE, key does not) | {0} | {1} |".format(
                len(calibration.over_escalations),
                ", ".join(str(case_no) for case_no in calibration.over_escalations) or "_none_",
            ),
            "| Under-escalations (key ESCALATE, produced does not) | {0} | {1} |".format(
                len(calibration.under_escalations),
                ", ".join(str(case_no) for case_no in calibration.under_escalations) or "_none_",
            ),
            "",
            "### The INDETERMINATE cases, kept out of the rate",
            "",
            "{0} {1} whose record genuinely does not settle the "
            "question, and {2} on substantive grounds. A run that answers an "
            "INDETERMINATE case instead of escalating it has not been decisive; it "
            "has invented an answer, and that is the failure that matters most. It "
            "is counted here rather than averaged into the escalation rate.".format(
                "The key escalates" if full else "In this set the key escalates",
                _plural(len(calibration.indeterminate_expected), "case"),
                _plural(len(calibration.substantive_expected), "case"),
            ),
            "",
            "| | |",
            "|---|---|",
            "| INDETERMINATE cases the key escalates | {0} |".format(
                ", ".join(str(case_no) for case_no in calibration.indeterminate_expected)
                or "_none_"
            ),
            "| ... the run escalated | {0} of {1} |".format(
                len(calibration.indeterminate_escalated),
                len(calibration.indeterminate_expected),
            ),
            "| **... the run ruled confidently instead** | **{0} of {1}** |".format(
                len(calibration.indeterminate_ruled_confidently),
                len(calibration.indeterminate_expected),
            ),
            "| Substantive escalations the key makes | {0} |".format(
                ", ".join(str(case_no) for case_no in calibration.substantive_expected)
                or "_none_"
            ),
            "| ... the run escalated | {0} of {1} |".format(
                len(calibration.substantive_escalated),
                len(calibration.substantive_expected),
            ),
            "",
        ]
    )
    if calibration.indeterminate_ruled_confidently:
        lines.append(
            "Cases ruled confidently where the record does not settle the "
            "question: {0}.".format(
                ", ".join(
                    str(case_no) for case_no in calibration.indeterminate_ruled_confidently
                )
            )
        )
        lines.append("")
    return lines


def _display_path(path: Path) -> str:
    """A path as this repository names it.

    Relative to the project root, so a rendered report is the same bytes from
    any checkout and carries no absolute path and no user name. A path that is
    not inside the repository is reduced to its final component rather than
    published.
    """
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return resolved.name


def _render_how_checked(key_path: Optional[Path] = None) -> List[str]:
    """The closing note, for the key this report was graded against.

    The corpus paragraph is a set of facts about ``tests/test_grade.py`` and the
    corpus key -- 29/29, five escalations, 17.2% -- and every figure in it is a
    fact about a different key when the report is of a development set. A report
    carrying it would assert the corpus self-test as though it covered a set that
    self-test never touches, so a set gets its own sentence instead.
    """
    if key_path is None:
        return [
            "`tests/test_grade.py` feeds each case's own `ground_truth` block back "
            "in as though a perfect judge had produced it and requires 29/29 on "
            "every field, five escalations, a rate of 17.2%, and precision and "
            "recall of 1.0. It then perturbs one field at a time — a ruling, an "
            "amount by 0.05, a `null` driver compensation replaced by 0, case "
            "207's referral dropped, a referral added where the key expects none "
            "— and requires each perturbation to fail on its own field and on "
            "the four-field match, without disturbing the other fields' counts. "
            "No model is involved at any point.",
            "",
        ]
    return [
        "This report is of the development set `{0}`, whose own answer key is "
        "`{1}`. The grader's self-test is written against the corpus key and does "
        "not cover this set, so the figures above are a measurement against this "
        "set's own key and of nothing else. No model is involved in the grading "
        "at any point.".format(Path(key_path).parent.name, _display_path(key_path)),
        "",
    ]


def render_report(
    report: GradeReport, title: str = DEFAULT_TITLE, key_path: Optional[Path] = None
) -> str:
    """Render the whole report as Markdown.

    Deterministic: the same graded set renders the same bytes, which is what
    lets a committed report be checked against the module rather than trusted.

    ``key_path`` names the key this report is of, and defaults to the corpus
    key. Two passages below are written about the corpus -- the path in the
    header and the closing note on how the grader was checked -- and both are
    false of a second development set, which has its own key and is not covered
    by the corpus self-test. Passing that set's key replaces them, so a report
    never asserts a fact about a key it did not grade against.
    """
    total = report.total

    # Both qualifiers are appended to the headline figure rather than left to the
    # blocks below it. A reader who reads only the summary must still learn that
    # the number is not a single whole-pipeline measurement, and the two reasons
    # it might not be are different findings.
    qualifiers = ""
    if report.staleness.mixed:
        qualifiers += " **(mixed set — not one measurement)**"
    if report.replay.any:
        qualifiers += " **(advocates replayed)**"

    lines: List[str] = [
        "# {0}".format(title),
        "",
        (
            "Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. "
            "The answer key is `{0}`; the five ruling values are read from "
            "POL-GEN-03 on the loaded general policy."
        ).format(_display_path(ANSWER_KEY_PATH if key_path is None else key_path)),
        "",
        "## Summary",
        "",
        "| | |",
        "|---|---|",
        "| Cases graded | {0} |".format(total),
        "| Rulings produced | {0} |".format(total - len(report.unproduced)),
        "| **Four-field exact match** | **{0}/{1} = {2}**{3} |".format(
            report.exact_matches,
            total,
            render_percent(_percent(report.exact_matches, total)),
            qualifiers,
        ),
        "",
    ]

    # Named here as well as in the block below, because this is the table a
    # reader reads when they read only one thing.
    if report.replay.any:
        lines.append(
            "| Advocates | replayed from {0} for {1} of {2} cases |".format(
                ", ".join("`{0}`".format(source) for source in report.replay.sources)
                or "an unrecorded source",
                len(report.replay.cases),
                total,
            )
        )
        lines.append("")

    for field in GRADED_FIELDS:
        correct, field_total = report.field_tally(field)
        lines.append(
            "| `{0}` | {1}/{2} = {3} |".format(
                field, correct, field_total, render_percent(_percent(correct, field_total))
            )
        )

    lines.extend(_render_staleness(report))
    lines.extend(_render_replay(report))

    lines.extend(
        [
            "",
            "A ruling counts only when **all four** fields agree. The per-field "
            "figures above are there so a reader can see which field a model "
            "actually fails on; they are not alternative scores.",
            "",
            "Reported as a contrast only, and not as a result: `ruling` and "
            "`amount_sgd` alone would give **{0}/{1} = {2}**. Case 207 is "
            "`ESCALATE` with both money fields `null` and a referral "
            "instructing the reviewer to refund the rider's SGD 4.00 in full, "
            "so a two-field grader awards it full marks while a real rider does "
            "not get their money back. The gap between this line and the "
            "four-field line is the size of that mistake on this run.".format(
                report.two_field_matches,
                total,
                render_percent(_percent(report.two_field_matches, total)),
            ),
            "",
        ]
    )

    if report.unproduced:
        lines.append(
            "No ruling was produced for: {0}. An absent ruling fails all four "
            "fields of its case.".format(
                ", ".join(str(case_no) for case_no in report.unproduced)
            )
        )
        lines.append("")

    if report.unexpected_cases:
        lines.append(
            "Produced rulings for cases the key does not carry, which were not "
            "scored: {0}.".format(
                ", ".join(str(case_no) for case_no in report.unexpected_cases)
            )
        )
        lines.append("")

    if report.encoding_notes:
        lines.append("### Encoding notes")
        lines.append("")
        lines.append(
            "These fields compared on their value, but did not arrive as the "
            "JSON type the ruling contract requires. A run in which every amount "
            "is listed here was parsed without `parse_float=Decimal`."
        )
        lines.append("")
        for case_no, field, note in report.encoding_notes:
            lines.append("- case {0} — `{1}` {2}".format(case_no, field, note))
        lines.append("")

    lines.extend(["## Per case", ""])
    lines.extend(_render_case_table(report))
    lines.append("")

    lines.extend(["## Failures", ""])
    lines.extend(_render_failures(report))

    lines.extend(["## Referrals — expected against produced", ""])
    lines.extend(_render_referrals(report))

    lines.extend(["## Escalation calibration", ""])
    lines.extend(_render_calibration(report))

    lines.extend(["## How this was checked", ""])
    lines.extend(_render_how_checked(key_path))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def produced_from_document(document: Any) -> Dict[int, Any]:
    """Read a produced-rulings document into ``{case_no: record}``.

    Accepts the three shapes a caller is likely to have: a JSON array of
    records, a single record, or an object keyed by case number.
    """
    if isinstance(document, list):
        produced: Dict[int, Any] = {}
        for record in document:
            if not isinstance(record, Mapping):
                raise GradeError("a produced record is not an object: {0!r}".format(record))
            declared = record.get("case_no")
            if isinstance(declared, Mapping):
                declared = declared.get("case_no")
            if not isinstance(declared, int) or isinstance(declared, bool):
                raise GradeError("a produced record declares no usable case_no: {0!r}".format(record))
            produced[declared] = record
        return produced

    if isinstance(document, Mapping):
        if "case_no" in document:
            return {produced_from_mapping(document).case_no: document}
        produced = {}
        for key, record in document.items():
            try:
                produced[int(key)] = record
            except (TypeError, ValueError) as exc:
                raise GradeError("produced key {0!r} is not a case number".format(key)) from exc
        return produced

    raise GradeError(
        "a produced-rulings document must be an array or an object, got {0}".format(
            type(document).__name__
        )
    )


def _read_produced(path: Path) -> Dict[int, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            document = json.load(handle, parse_float=Decimal)
    except FileNotFoundError as exc:
        raise GradeError("produced rulings not found: {0}".format(path)) from exc
    except json.JSONDecodeError as exc:
        raise GradeError("invalid JSON in {0}: {1}".format(path, exc)) from exc
    return produced_from_document(document)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Grade a produced-rulings file, or the key against itself.

    ``--self-test`` grades the key against itself, which is the check a judge
    can reproduce without a model, a credential or a network. It exits non-zero
    unless every case matches on every field.
    """
    parser = argparse.ArgumentParser(
        prog="python -m eval.grade",
        description="Grade produced rulings against eval/answers/ground_truth.json.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--produced",
        type=Path,
        help="a JSON file of produced rulings, by case number",
    )
    source.add_argument(
        "--self-test",
        action="store_true",
        help="grade the answer key against itself; requires a perfect score",
    )
    parser.add_argument("--out", type=Path, default=None, help="write the report here")
    parser.add_argument("--stdout", action="store_true", help="also print the report")
    parser.add_argument("--title", default=None, help="report title")
    args = parser.parse_args(argv)

    key = load_answer_key()
    if args.self_test:
        produced = key_as_produced(key)
        title = args.title or SELF_TEST_TITLE
    else:
        produced = _read_produced(args.produced)
        title = args.title or DEFAULT_TITLE

    report = grade(produced, key)
    text = render_report(report, title)

    out = args.out
    if out is None and args.self_test:
        out = DEFAULT_REPORT_PATH
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        print("wrote {0}".format(out), file=sys.stderr)

    if args.stdout or args.self_test:
        print(text)

    if args.self_test and report.exact_matches != report.total:
        print(
            "the key does not grade itself: {0}/{1} exact".format(
                report.exact_matches, report.total
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
