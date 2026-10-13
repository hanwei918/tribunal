"""Fairness and calibration, measured from the version-6 development runs.

The judging includes responsible AI, fairness and transparency, and the
version-6 runs already hold everything three such measurements need. This module
reads them and prints the measurements; it makes **no model call** and launches
no browser, and it writes nothing but the one chart its ``--chart`` names.

Three things are measured, over the corpus run (``runs/policy-v6/``) and the
``dev-v2-ext`` run (``runs/dev-v2-ext/policy-v6/``), separately and together:

1. **Which way the errors lean.** Every ruling value and every key value is
   classified as rider-favouring (``FULL_REFUND``, ``PARTIAL_REFUND``),
   driver-favouring (``NO_ACTION``, ``DRIVER_COMPENSATION``) or neither
   (``ESCALATE``). Every case that differs from its key is reported by the
   direction its ruling moved: towards the rider, towards the driver, to an
   escalation, or away from one. Where both the key and the ruling are a refund
   of different sizes, the direction the amount moved is stated.
2. **The position swap.** Each case's four judge drafts hold three sampled
   drafts and one asked with the parties' positions swapped. Over every case
   whose swapped draft and at least one sampled draft are valid, the swapped
   draft is held against the sampled majority on all four graded fields together
   and on the ruling alone.
3. **Calibration.** Every valid judge draft carries a confidence. Each draft is
   marked correct when its four fields equal the case's key, and the drafts are
   grouped into the five confidence bins, with each bin's count, mean confidence
   and share correct, a Wilson 95% interval, and the expected calibration error
   over all drafts. The share correct below the 0.70 floor and at or above it is
   reported too.

4. **What the low bins hold.** A draft that proposes ``ESCALATE`` decides
   nothing -- it sends the case to a person -- and the key often says
   ``ESCALATE`` too, so a below-floor bin can look well-calibrated while holding
   only escalations. Each side of the floor is therefore split again: how many
   of its drafts propose ``ESCALATE``, and how often the drafts that propose
   something else are right.

**What is read, and what is not.** The runs under ``runs/``, the two committed
keys (``eval/answers/ground_truth.json`` and
``eval/answers/dev-v2-ext/ground_truth.json``), the two runs' transcripts, and
the two sets' own public, answer-free case files under ``data/cases/`` and
``data/external/dev-v2-ext/`` -- read for the three facts the runs do not
record: which party filed each dispute, its category, and the amount it
contests. No other answer path is opened, and nothing under a sealed root is
opened at all.

**The draft readings are the pipeline's own.** A draft's four graded fields are
reduced by :func:`tribunal.pipeline.vote_key`, the same reduction the judge's
vote is taken with, so "agrees on all four graded fields" means what it means in
the pipeline rather than a second, private reading of the same fields. The
drafts are read out of the transcripts the way ``ops.escalation`` reads them --
the last ruling a draft parsed to, so a retried draft is read as it stood -- and
that reading is **reproduced here rather than imported**: importing the ops layer
executes ``eval.development_sets``, which opens every registered set's
``index.json`` at import, ``sealed-v1``'s among them, and this module opens no
sealed path.

**Drafts of one case are not independent.** A case's four drafts answer the same
brief, so the 567 valid drafts are 141 panels rather than 567 independent
draws, and every rate here is reported as a count over drafts with that said in
the note. The bins are the sheet's, and the 0.70 boundary is the confidence
floor read out of the loaded policy: a floor that has moved refuses rather than
being silently honoured at its old value.

**Two more readings of the same errors, appended as sections 4 and 5.** Section
4 splits each run's cases -- and both runs together -- by
``dispute.category`` (``ROUTE_DEVIATION``, ``NO_SHOW_CHARGE``) and section 5 by
``dispute.amount_contested_sgd`` read as a ``Decimal``, in three bands
(``<= 5.00``, ``5.01 to 15.00``, ``> 15.00``). Each block is section 1's own
block for that group's cases -- the same :func:`error_lean`, never a second
classifier -- followed by the two escalation rates the key and the system give,
each with a Wilson 95% interval. The two facts come from the same public case
files the filed-by split reads, because no run records either. The groups are
small, so each section ends by naming the smallest of them: read the rows as
counts.

Run from the project root with::

    python3 -m eval.fairness --report
    python3 -m eval.fairness --chart docs/calibration-v6.svg
"""

from __future__ import annotations

import argparse
import collections
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from eval import grade, sealed_roots, v6_runs
from tribunal import loader, pipeline, precedents

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The two runs measured, by the name ``eval.v6_runs`` gives them.
CORPUS = "corpus"
DEV_V2_EXT = "dev-v2-ext"
MEASURED_SETS: Tuple[str, ...] = (CORPUS, DEV_V2_EXT)

# Where each set's public, answer-free case files live. The runs do not record
# which party filed a dispute, and the note's "why not by who filed" paragraph
# needs the counts, so the public case files are read for that one field. They
# are agent-visible under the same contract as ``data/cases/``: no expected
# ruling, no answer field and no argument for either side.
CASE_ROOTS: Mapping[str, Path] = {
    CORPUS: PROJECT_ROOT / "data" / "cases",
    DEV_V2_EXT: PROJECT_ROOT / "data" / "external" / "dev-v2-ext",
}

# The category whose policy states the confidence floor. ``loader.load_policies``
# returns the general policy beside it, and the general policy states the floor
# too; the two are required to agree, as the pipeline requires.
CATEGORY_FOR_POLICY_LOOKUP = "ROUTE_DEVIATION"

# --------------------------------------------------------------------------
# The classification of a ruling value
# --------------------------------------------------------------------------
# The five POL-GEN-03 values, grouped by which party they favour. The
# vocabulary itself is read from the policy by ``eval.grade``; these are the
# three groups, and a test asserts that together they are exactly that
# vocabulary, so a value the policy adds later fails here rather than being
# silently unclassified.
RIDER_FAVOURING: Tuple[str, ...] = ("FULL_REFUND", "PARTIAL_REFUND")
DRIVER_FAVOURING: Tuple[str, ...] = ("NO_ACTION", "DRIVER_COMPENSATION")
NEITHER_SIDE: Tuple[str, ...] = ("ESCALATE",)

# The one ruling value that decides nothing: a draft that proposes it sends the
# case to a person rather than ruling on it. The calibration split below reads
# this value apart from the four that decide, because a draft that escalates
# agrees with an escalating key without having decided anything.
ESCALATE = NEITHER_SIDE[0]

RIDER = "RIDER"
DRIVER = "DRIVER"
NEITHER = "NEITHER"

# The directions a differing case's ruling can move.
TOWARDS_RIDER = "towards the rider"
TOWARDS_DRIVER = "towards the driver"
TO_ESCALATION = "to an escalation"
AWAY_FROM_ESCALATION = "away from an escalation"
WITHIN_SIDE = "within a side"
NO_RULING = "no ruling"

# In the order the report prints them, so a reader counts the same six rows
# whichever set they are reading.
DIRECTIONS: Tuple[str, ...] = (
    TOWARDS_RIDER,
    TOWARDS_DRIVER,
    TO_ESCALATION,
    AWAY_FROM_ESCALATION,
    WITHIN_SIDE,
    NO_RULING,
)

# The confidence floor, as the policy states it. The sheet's bins put a boundary
# here; a policy floor that is not this number refuses rather than being
# honoured at a boundary the bins no longer name.
FLOOR = Decimal("0.70")

# The other four bin edges, which the sheet fixes.
BIN_EDGES: Tuple[Decimal, ...] = (
    Decimal("0.0"),
    Decimal("0.5"),
    FLOOR,
    Decimal("0.8"),
    Decimal("0.9"),
    Decimal("1.0"),
)

# --------------------------------------------------------------------------
# The two breakdowns: by category, and by the amount contested
# --------------------------------------------------------------------------
# The two categories the measured sets carry. Every case of both sets carries
# exactly one of them, so the category blocks partition a run's cases; a case
# carrying a third category would fall into no block and the partition would
# fail rather than the case being silently dropped.
CATEGORIES: Tuple[str, ...] = ("ROUTE_DEVIATION", "NO_SHOW_CHARGE")

# The three bands of ``dispute.amount_contested_sgd``. The boundaries are read
# as ``Decimal`` and never as floats, so ``5.00`` is in the first band and
# ``15.00`` in the second, exactly as the bands are written.
BAND_LOW = "<= 5.00"
BAND_MIDDLE = "5.01 to 15.00"
BAND_HIGH = "> 15.00"
BANDS: Tuple[str, ...] = (BAND_LOW, BAND_MIDDLE, BAND_HIGH)
BAND_LOW_MAX = Decimal("5.00")
BAND_MIDDLE_MAX = Decimal("15.00")


class FairnessError(Exception):
    """A measurement could not be made, or a value it depends on has moved."""


def side_of(ruling: Any) -> Optional[str]:
    """Which side a ruling value favours, or ``None`` for a value outside them.

    ``ESCALATE`` is a side of its own -- neither party is favoured by a case
    sent to a person -- and it is a value rather than an absence, so it never
    reads as "no ruling".
    """
    if ruling in RIDER_FAVOURING:
        return RIDER
    if ruling in DRIVER_FAVOURING:
        return DRIVER
    if ruling in NEITHER_SIDE:
        return NEITHER
    return None


def classify_vocabulary() -> Tuple[Tuple[str, str], ...]:
    """Every POL-GEN-03 value beside the side it is classified into.

    The vocabulary comes from the policy through ``eval.grade.ruling_values``,
    so this answers for the policy the runs were made at rather than for a list
    copied here. A value with no side raises, because an unclassified value
    would be counted in no row of the error-lean table.
    """
    pairs: List[Tuple[str, str]] = []
    for value in grade.ruling_values():
        side = side_of(value)
        if side is None:
            raise FairnessError(
                "the policy licenses the ruling value {0!r} and it is in none of "
                "the three sides, so an error on it would be counted nowhere".format(
                    value
                )
            )
        pairs.append((value, side))
    return tuple(pairs)


# --------------------------------------------------------------------------
# 1. Which way the errors lean
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Movement:
    """One case that differs from its key, and the direction its ruling moved."""

    case_no: int
    expected: Any
    produced: Any
    direction: str
    amount_note: Optional[str] = None


def _money_of(ruling: grade.Ruling, field: str) -> Decimal:
    """One side's money as a number, ``null`` counting as zero for an ordering."""
    value = grade.money_or_none(ruling.field(field))
    if isinstance(value, Decimal):
        return value
    return Decimal(0)


def movement_for(
    case_no: int, expected: grade.Ruling, produced: Optional[grade.Ruling]
) -> Movement:
    """The direction a differing case's ruling moved, and why.

    A case with no ruling at all moved nowhere and is reported as its own
    direction rather than folded into one of the four. Where the key and the
    ruling are on the same side, the money that side receives decides the
    direction: a larger refund moves towards the rider and a smaller one towards
    the driver, and the same holds for a driver's compensation.
    """
    if produced is None:
        return Movement(case_no, expected.ruling, None, NO_RULING)

    expected_side = side_of(expected.ruling)
    produced_side = side_of(produced.ruling)

    if produced_side == NEITHER and expected_side != NEITHER:
        return Movement(case_no, expected.ruling, produced.ruling, TO_ESCALATION)
    if expected_side == NEITHER and produced_side != NEITHER:
        return Movement(
            case_no, expected.ruling, produced.ruling, AWAY_FROM_ESCALATION
        )
    if produced_side == RIDER and expected_side == DRIVER:
        return Movement(case_no, expected.ruling, produced.ruling, TOWARDS_RIDER)
    if produced_side == DRIVER and expected_side == RIDER:
        return Movement(case_no, expected.ruling, produced.ruling, TOWARDS_DRIVER)

    # The same side, so the label moved or the money did. The money is what a
    # reader wants to see move, and it is stated whichever way it went.
    if expected_side == RIDER:
        field, pays = "amount_sgd", "the refund"
    else:
        field, pays = "driver_compensation_sgd", "the driver compensation"
    before = _money_of(expected, field)
    after = _money_of(produced, field)
    if before == after:
        return Movement(case_no, expected.ruling, produced.ruling, WITHIN_SIDE)
    note = "{0} moved from {1} to {2}".format(
        pays, grade.render_money(before), grade.render_money(after)
    )
    direction = TOWARDS_RIDER if (
        (expected_side == RIDER and after > before)
        or (expected_side == DRIVER and after < before)
    ) else TOWARDS_DRIVER
    return Movement(case_no, expected.ruling, produced.ruling, direction, note)


@dataclass(frozen=True)
class ErrorLean:
    """Every differing case of one graded set, by the direction it moved."""

    total: int
    differing: Tuple[Movement, ...]

    def cases(self, direction: str) -> Tuple[int, ...]:
        return tuple(
            movement.case_no
            for movement in self.differing
            if movement.direction == direction
        )

    def count(self, direction: str) -> int:
        return len(self.cases(direction))

    @property
    def amount_moves(self) -> Tuple[Movement, ...]:
        """The cases where both sides are money of the same kind, moved."""
        return tuple(
            movement for movement in self.differing if movement.amount_note is not None
        )


def error_lean(report: grade.GradeReport) -> ErrorLean:
    """The direction every case that differs from its key moved in."""
    differing = tuple(
        movement_for(score.case_no, score.expected, score.produced)
        for score in report.cases
        if not score.exact
    )
    return ErrorLean(report.total, differing)


# --------------------------------------------------------------------------
# 2. The position swap
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SwapCase:
    """One case whose swapped draft could be held against a sampled majority."""

    case_no: int
    agrees_on_all_four: bool
    agrees_on_ruling: bool


@dataclass(frozen=True)
class PositionSwap:
    """The cases with a valid swapped draft and at least one valid sampled one."""

    cases: Tuple[SwapCase, ...]

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def agree_all_four(self) -> int:
        return sum(1 for case in self.cases if case.agrees_on_all_four)

    @property
    def agree_ruling(self) -> int:
        return sum(1 for case in self.cases if case.agrees_on_ruling)

    def disagreements(self) -> Tuple[int, ...]:
        """The cases whose swapped draft did not agree on all four fields."""
        return tuple(case.case_no for case in self.cases if not case.agrees_on_all_four)

    def ruling_disagreements(self) -> Tuple[int, ...]:
        """The cases whose swapped draft did not agree on the ruling alone."""
        return tuple(case.case_no for case in self.cases if not case.agrees_on_ruling)


# --------------------------------------------------------------------------
# Reading a draft's ruling out of a transcript
#
# The reading is ``ops.escalation``'s own -- the last ruling a draft parsed to,
# so a retried draft is read as it stood -- reproduced here rather than imported
# from it. Importing the ops layer executes ``eval.development_sets``, which
# opens every registered set's ``index.json`` at import, ``sealed-v1``'s among
# them; this module opens no sealed path, so the few lines are written out
# instead of reached for. The transcript's file name is still the one
# ``tribunal.precedents`` spells, which is the helper ``ops.escalation`` uses
# for the same purpose.
# --------------------------------------------------------------------------
def transcript_path(run_dir: Path, document: Mapping[str, Any], case_no: int) -> Path:
    """The case's transcript, by the name the run recorded for it."""
    recorded = document.get("transcript_file")
    if isinstance(recorded, str) and recorded:
        return Path(run_dir) / recorded
    return precedents.transcript_file_for(run_dir, case_no)


def _parsed_ruling(
    transcript: Mapping[str, Any], entry_index: Any
) -> Optional[Mapping[str, Any]]:
    """The ruling a transcript entry parsed to, or ``None``."""
    entries = transcript.get("entries")
    if not isinstance(entries, list) or not isinstance(entry_index, int):
        return None
    if entry_index < 0 or entry_index >= len(entries):
        return None
    entry = entries[entry_index]
    parsed = entry.get("parsed") if isinstance(entry, Mapping) else None
    ruling = parsed.get("ruling") if isinstance(parsed, Mapping) else None
    return ruling if isinstance(ruling, Mapping) else None


def draft_ruling(
    transcript: Mapping[str, Any], draft: Mapping[str, Any]
) -> Optional[Mapping[str, Any]]:
    """The last ruling a draft parsed to, so a retried draft is read as it stood."""
    for index in reversed(list(draft.get("entries") or [])):
        ruling = _parsed_ruling(transcript, index)
        if ruling is not None:
            return ruling
    return None


def transcript_for(run: v6_runs.V6Run, case_no: int) -> Mapping[str, Any]:
    """One case's transcript, by the name the run's own case file records."""
    document = v6_runs.read_json(v6_runs.case_path(run.run_dir, case_no))
    path = transcript_path(run.run_dir, document, case_no)
    return v6_runs.read_json(path)


def draft_key(transcript: Mapping[str, Any], draft: Mapping[str, Any]) -> Optional[Tuple[Any, ...]]:
    """One draft's four graded fields, as the pipeline's own vote key.

    The draft's ruling is read the way ``ops.escalation`` reads it -- the last
    ruling the draft parsed to -- and then reduced by
    :func:`tribunal.pipeline.vote_key`, which is the reduction the judge's vote
    is taken with. ``None`` for a draft that parsed to no ruling at all.
    """
    inner = draft_ruling(transcript, draft)
    if inner is None:
        return None
    return pipeline.vote_key({"ruling": inner})


def _majority(keys: Sequence[Tuple[Any, ...]]) -> Tuple[Any, ...]:
    """The most common key, ties going to the one the earliest draft proposed."""
    return collections.Counter(keys).most_common(1)[0][0]


def position_swap(transcripts: Mapping[int, Mapping[str, Any]]) -> PositionSwap:
    """Hold each case's swapped draft against its sampled majority.

    A case is in the measurement when its swapped draft is valid and at least
    one sampled draft is valid, which is the sheet's own denominator. The
    sampled majority is the most common four-field key among the valid sampled
    drafts; the ruling majority is the most common ruling value among them.
    """
    cases: List[SwapCase] = []
    for case_no in sorted(transcripts):
        vote = transcripts[case_no].get("vote")
        vote = vote if isinstance(vote, Mapping) else {}
        drafts = [draft for draft in vote.get("drafts") or [] if isinstance(draft, Mapping)]

        def keys(kind: str) -> List[Tuple[Any, ...]]:
            found = [
                draft_key(transcripts[case_no], draft)
                for draft in drafts
                if draft.get("kind") == kind and draft.get("valid")
            ]
            return [key for key in found if key is not None]

        sampled = keys("sampled")
        swapped = keys("position_swapped")
        if not sampled or not swapped:
            continue
        majority = _majority(sampled)
        majority_ruling = _majority([key[0] for key in sampled])
        chosen = swapped[0]
        cases.append(
            SwapCase(
                case_no,
                chosen == majority,
                chosen[0] == majority_ruling,
            )
        )
    return PositionSwap(tuple(cases))


# --------------------------------------------------------------------------
# 3. Calibration
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DraftOutcome:
    """One valid judge draft: its confidence, its value, and its verdict.

    ``ruling`` is the value the draft proposed -- one of the five POL-GEN-03
    values -- and ``correct`` is whether the draft's four graded fields equal
    the case's key. The value is carried beside the verdict so the calibration
    can tell a draft that decided a case from one that sent it to a person.
    """

    case_no: int
    kind: str
    confidence: Decimal
    correct: bool
    ruling: str


@dataclass(frozen=True)
class Bin:
    """One confidence bin: how many drafts, how confident, how often right."""

    low: Decimal
    high: Decimal
    count: int
    correct: int
    mean_confidence: Optional[Decimal]

    @property
    def share_correct(self) -> Optional[Decimal]:
        if self.count == 0:
            return None
        return Decimal(self.correct) / Decimal(self.count)

    @property
    def wilson(self) -> Optional[Tuple[float, float]]:
        return v6_runs.wilson(self.correct, self.count)


@dataclass(frozen=True)
class Calibration:
    """The bins, the expected calibration error, and the floor split."""

    total: int
    bins: Tuple[Bin, ...]
    ece: Decimal
    below_floor: Tuple[int, int]
    at_or_above_floor: Tuple[int, int]


def confidence_floor() -> Decimal:
    """The confidence floor, read from the loaded version-6 policy.

    Both policy documents state it, as a top-level ``confidence_floor``; they
    are required to agree, as :func:`tribunal.pipeline.confidence_floor`
    requires, and the one number is required to be the boundary the bins name.
    A policy that disagreed with itself, or a floor that moved, refuses here.
    """
    policies = loader.load_policies(CATEGORY_FOR_POLICY_LOOKUP, v6_runs.POLICY_VERSION)
    found: Dict[Decimal, List[str]] = {}
    for name, policy in sorted(policies.items()):
        if not isinstance(policy, Mapping):
            continue
        stated = grade.money_or_none(policy.get("confidence_floor"))
        if isinstance(stated, Decimal):
            found.setdefault(stated, []).append(name)
    if len(found) != 1:
        raise FairnessError(
            "the loaded policy states no single confidence floor: {0}".format(
                ", ".join(
                    "{0} in {1}".format(floor, "/".join(where))
                    for floor, where in sorted(found.items())
                )
                or "none"
            )
        )
    floor = next(iter(found))
    if floor != FLOOR:
        raise FairnessError(
            "the confidence floor is {0} and the bins are built around {1}".format(
                floor, FLOOR
            )
        )
    return floor


def bin_edges() -> Tuple[Decimal, ...]:
    """The five bins' six edges, the 0.70 boundary taken from the policy."""
    return (BIN_EDGES[0], BIN_EDGES[1], confidence_floor()) + BIN_EDGES[3:]


def _produced_from_draft(case_no: int, inner: Mapping[str, Any]) -> grade.Ruling:
    """A draft's ruling as the grader's produced side, so it is graded as a run is."""
    return grade.produced_from_mapping(
        {
            "ruling": {
                "ruling": inner.get("ruling"),
                "amount_sgd": inner.get("amount_sgd"),
                "driver_compensation_sgd": inner.get("driver_compensation_sgd"),
                "referrals": list(inner.get("referrals") or []),
                "confidence": inner.get("confidence"),
            }
        },
        case_no,
    )


def draft_outcomes(
    run: v6_runs.V6Run, transcript_map: Optional[Mapping[int, Mapping[str, Any]]] = None
) -> Tuple[DraftOutcome, ...]:
    """Every valid judge draft of one run, with its confidence and its verdict.

    A draft is correct when its four fields equal the case's key, decided by the
    grader's own :func:`eval.grade.score_case` rather than by a second reading of
    the same four fields. A valid draft that carries no readable confidence is a
    finding rather than a draft to drop silently, so it raises.

    ``transcript_map`` lets a caller that already holds the transcripts pass them
    in, so a report that measures both the swap and the calibration reads each
    transcript once rather than twice.
    """
    key = grade.load_answer_key(run.key_path)
    if transcript_map is None:
        transcript_map = transcripts(run)
    outcomes: List[DraftOutcome] = []
    for case_no in sorted(transcript_map):
        transcript = transcript_map[case_no]
        vote = transcript.get("vote")
        vote = vote if isinstance(vote, Mapping) else {}
        for draft in vote.get("drafts") or []:
            if not isinstance(draft, Mapping) or not draft.get("valid"):
                continue
            inner = draft_ruling(transcript, draft)
            if inner is None:
                continue
            confidence = grade.money_or_none(inner.get("confidence"))
            if not isinstance(confidence, Decimal):
                raise FairnessError(
                    "case {0} of {1} has a valid draft carrying no readable "
                    "confidence: {2!r}".format(case_no, run.name, inner.get("confidence"))
                )
            score = grade.score_case(case_no, key[case_no], _produced_from_draft(case_no, inner))
            outcomes.append(
                DraftOutcome(
                    case_no,
                    str(draft.get("kind")),
                    confidence,
                    score.exact,
                    str(inner.get("ruling")),
                )
            )
    return tuple(outcomes)


def calibrate(outcomes: Sequence[DraftOutcome]) -> Calibration:
    """The bins, the expected calibration error and the floor split.

    The expected calibration error is the count-weighted mean of each bin's
    absolute gap between its mean stated confidence and its share correct --
    ``sum over bins of (count / total) * |mean confidence - share correct|`` --
    and it is ``0`` for no drafts rather than undefined, because a set with no
    drafts has no error to report and not a missing one.
    """
    edges = bin_edges()
    total = len(outcomes)
    bins: List[Bin] = []
    ece = Decimal(0)
    for low, high in zip(edges, edges[1:]):
        if high == Decimal("1.0"):
            members = [o for o in outcomes if low <= o.confidence <= high]
        else:
            members = [o for o in outcomes if low <= o.confidence < high]
        count = len(members)
        correct = sum(1 for o in members if o.correct)
        mean = (
            sum((o.confidence for o in members), Decimal(0)) / Decimal(count)
            if count
            else None
        )
        bins.append(Bin(low, high, count, correct, mean))
        if count and mean is not None:
            share = Decimal(correct) / Decimal(count)
            ece += (Decimal(count) / Decimal(total)) * abs(mean - share)
    below = [o for o in outcomes if o.confidence < FLOOR]
    at_or_above = [o for o in outcomes if o.confidence >= FLOOR]
    return Calibration(
        total=total,
        bins=tuple(bins),
        ece=ece,
        below_floor=(sum(1 for o in below if o.correct), len(below)),
        at_or_above_floor=(sum(1 for o in at_or_above if o.correct), len(at_or_above)),
    )


@dataclass(frozen=True)
class EscalateSplit:
    """The drafts that propose ``ESCALATE``, below the floor and at or above it.

    Each side of the floor is split again, because the floor split above counts
    every draft: a below-floor bin that holds only escalations reads as
    well-calibrated while deciding nothing. ``below_other`` and ``above_other``
    are ``(correct, total)`` among the drafts in that group whose value is not
    ``ESCALATE``; the total is 0 when every draft in the group escalates, and
    the share is then undefined rather than zero.
    """

    below_escalate: int
    below_total: int
    below_other: Tuple[int, int]
    above_escalate: int
    above_total: int
    above_other: Tuple[int, int]


def escalate_split(outcomes: Sequence[DraftOutcome]) -> EscalateSplit:
    """How many drafts propose ``ESCALATE``, and how often the rest are right.

    The two groups are the same two the floor split uses -- drafts below the
    0.70 floor and drafts at or above it -- so the two splits are read off one
    pass and cannot disagree about which draft is in which group.
    """
    below = [o for o in outcomes if o.confidence < FLOOR]
    above = [o for o in outcomes if o.confidence >= FLOOR]

    def split(group: Sequence[DraftOutcome]) -> Tuple[int, Tuple[int, int]]:
        escalating = [o for o in group if o.ruling == ESCALATE]
        rest = [o for o in group if o.ruling != ESCALATE]
        return len(escalating), (sum(1 for o in rest if o.correct), len(rest))

    below_escalate, below_other = split(below)
    above_escalate, above_other = split(above)
    return EscalateSplit(
        below_escalate=below_escalate,
        below_total=len(below),
        below_other=below_other,
        above_escalate=above_escalate,
        above_total=len(above),
        above_other=above_other,
    )


# --------------------------------------------------------------------------
# Reading the two runs
# --------------------------------------------------------------------------
def measured_run(name: str) -> v6_runs.V6Run:
    if name not in MEASURED_SETS:
        raise FairnessError(
            "{0!r} is not one of the measured sets: {1}".format(
                name, ", ".join(MEASURED_SETS)
            )
        )
    return v6_runs.run_by_name(name)


def graded_report(run: v6_runs.V6Run) -> grade.GradeReport:
    """One run graded, through the grader ``eval.v6_runs`` itself uses."""
    documents = v6_runs.documents(run.run_dir, run.cases)
    key = grade.load_answer_key(run.key_path)
    return v6_runs._grade_run(run, documents, key)


def transcripts(run: v6_runs.V6Run) -> Dict[int, Mapping[str, Any]]:
    """Every case's transcript of one run, by case number."""
    found: Dict[int, Mapping[str, Any]] = {}
    for case_no in run.cases:
        if v6_runs.case_path(run.run_dir, case_no).is_file():
            found[case_no] = transcript_for(run, case_no)
    return found


def filed_by_counts(set_name: str) -> Dict[str, int]:
    """How many of one set's disputes each party filed.

    Read from the set's own public case files, because no run records this. The
    counts are what the note's "why not by who filed" paragraph rests on.
    """
    root = CASE_ROOTS[set_name]
    counts: Dict[str, int] = {}
    for path in sorted(root.glob("case-*.json")):
        if v6_runs.CASE_FILE_RE.match(path.name) is None:
            continue
        dispute = v6_runs.read_json(path).get("dispute") or {}
        filer = dispute.get("filed_by")
        counts[filer] = counts.get(filer, 0) + 1
    return counts


def case_count(set_name: str) -> int:
    """How many public case files one set carries."""
    return sum(1 for path in CASE_ROOTS[set_name].glob("case-*.json"))


def case_facts(set_name: str) -> Dict[int, Tuple[str, Decimal]]:
    """Each of one set's cases: its category, and the amount it contests.

    Read from the set's own public case files, because neither fact is recorded
    in a run. The amount is read as the ``Decimal`` the file states -- never as
    a float -- so the band boundaries are exact rather than nearly exact, which
    is the reading ``ops.appeal`` takes of the same field.
    """
    root = CASE_ROOTS[set_name]
    found: Dict[int, Tuple[str, Decimal]] = {}
    for path in sorted(root.glob("case-*.json")):
        match = v6_runs.CASE_FILE_RE.match(path.name)
        if match is None:
            continue
        dispute = v6_runs.read_json(path).get("dispute") or {}
        amount = dispute.get("amount_contested_sgd")
        if isinstance(amount, bool) or not isinstance(amount, (int, Decimal)):
            raise FairnessError(
                "case {0} of the {1} set states no amount_contested_sgd as a "
                "number: {2!r}".format(match.group(1), set_name, amount)
            )
        found[int(match.group(1))] = (
            str(dispute.get("category")),
            amount if isinstance(amount, Decimal) else Decimal(amount),
        )
    return found


def band_of(amount: Decimal) -> str:
    """Which of the three bands an amount falls in, each boundary inclusive below."""
    if amount <= BAND_LOW_MAX:
        return BAND_LOW
    if amount <= BAND_MIDDLE_MAX:
        return BAND_MIDDLE
    return BAND_HIGH


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _named(cases: Sequence[int]) -> str:
    items = [str(case_no) for case_no in cases]
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    return "{0} and {1}".format(", ".join(items[:-1]), items[-1])


def _rate(k: int, n: int) -> str:
    return "{0}/{1} = {2}".format(k, n, grade.render_percent(grade._percent(k, n)))


def _other_rate(pair: Tuple[int, int]) -> str:
    """The share correct among the drafts that do not propose ``ESCALATE``.

    ``none`` rather than a zero rate when the group holds no such draft: a group
    that is all escalations has no share correct to state, and printing ``0/0``
    would read as a rate of nothing rather than an absence.
    """
    correct, total = pair
    if total == 0:
        return "none (0 drafts)"
    return _rate(correct, total)


def _edge(value: Decimal) -> str:
    return "{0:.1f}".format(value)


def _floor_text() -> str:
    """The confidence floor as the policy states it, to two decimals."""
    return "{0:.2f}".format(FLOOR)


def render_ece(value: Decimal) -> str:
    """The expected calibration error, to three decimals."""
    return "{0:.3f}".format(value)


def _error_lean_block(label: str, lean: ErrorLean) -> List[str]:
    lines = [
        "-- {0}: {1} of {2} differ from the key".format(
            label, len(lean.differing), lean.total
        )
    ]
    for direction in DIRECTIONS:
        lines.append(
            "   {0:<24}{1:<4}{2}".format(
                direction, lean.count(direction), _named(lean.cases(direction))
            )
        )
    for movement in lean.amount_moves:
        lines.append(
            "     {0}: {1}".format(movement.case_no, movement.amount_note)
        )
    return lines


def _swap_block(label: str, swap: PositionSwap) -> List[str]:
    return [
        "-- {0}: {1} cases have a valid swapped draft and a valid sampled one".format(
            label, swap.total
        ),
        "   agrees on all four graded fields   {0}   Wilson 95% {1}".format(
            _rate(swap.agree_all_four, swap.total),
            v6_runs.wilson_text(swap.agree_all_four, swap.total),
        ),
        "   agrees on the ruling alone         {0}   Wilson 95% {1}".format(
            _rate(swap.agree_ruling, swap.total),
            v6_runs.wilson_text(swap.agree_ruling, swap.total),
        ),
        "   disagrees on all four     {0}".format(_named(swap.disagreements())),
        "   disagrees on the ruling   {0}".format(_named(swap.ruling_disagreements())),
    ]


def _calibration_block(
    label: str, calibration: Calibration, split: EscalateSplit
) -> List[str]:
    lines = [
        "-- {0}: {1} valid judge drafts".format(label, calibration.total),
        "   {0:<14}{1:>6}{2:>12}{3:>16}{4:>20}".format(
            "bin", "count", "mean conf", "share correct", "Wilson 95%"
        ),
    ]
    for bin_ in calibration.bins:
        lines.append(
            "   {0:<14}{1:>6}{2:>12}{3:>16}{4:>20}".format(
                "[{0}, {1})".format(_edge(bin_.low), _edge(bin_.high)),
                bin_.count,
                "-" if bin_.mean_confidence is None else "{0:.3f}".format(bin_.mean_confidence),
                "-"
                if bin_.share_correct is None
                else grade.render_percent(
                    grade._percent(bin_.correct, bin_.count)
                ),
                v6_runs.wilson_text(bin_.correct, bin_.count),
            )
        )
    below_correct, below_total = calibration.below_floor
    at_correct, at_total = calibration.at_or_above_floor
    lines.append(
        "   expected calibration error   {0}".format(render_ece(calibration.ece))
    )
    lines.append(
        "   below the {0} floor   {1}".format(
            _floor_text(), _rate(below_correct, below_total)
        )
    )
    lines.append(
        "   at or above it        {0}".format(_rate(at_correct, at_total))
    )
    lines.append(
        "   drafts proposing ESCALATE, below the {0} floor   {1}".format(
            _floor_text(), _rate(split.below_escalate, split.below_total)
        )
    )
    lines.append(
        "   drafts proposing ESCALATE, at or above it        {0}".format(
            _rate(split.above_escalate, split.above_total)
        )
    )
    lines.append(
        "   share correct among the drafts that do not propose ESCALATE"
    )
    lines.append(
        "     below the floor   {0}".format(_other_rate(split.below_other))
    )
    lines.append(
        "     at or above it    {0}".format(_other_rate(split.above_other))
    )
    return lines


# --------------------------------------------------------------------------
# 4 and 5. The breakdowns, one block per category and one per band
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Group:
    """One row of a breakdown: a label, its cases' lean, and two escalation counts.

    ``escalated_by_system`` counts the cases whose produced ruling is
    ``ESCALATE`` and ``escalated_in_key`` the cases whose key says so; each is
    reported as a rate with a Wilson 95% interval, the formatting section 2
    already uses.
    """

    label: str
    lean: ErrorLean
    escalated_by_system: int
    escalated_in_key: int


def report_over(
    report: grade.GradeReport, cases: Sequence[int]
) -> grade.GradeReport:
    """One report restricted to a set of its own cases.

    ``error_lean`` reads ``cases`` and ``total``. The escalation block is
    recomputed over the subset rather than carried from the whole report, so the
    report handed to the classifier is a report of these cases and not a report
    of all of them wearing a block that belongs to another set.
    """
    wanted = set(cases)
    chosen = tuple(score for score in report.cases if score.case_no in wanted)
    return grade.GradeReport(cases=chosen, calibration=grade.calibrate(chosen))


def combined_report(
    reports: Mapping[str, grade.GradeReport]
) -> grade.GradeReport:
    """One report over every measured run's cases together, for the both-runs rows."""
    cases = tuple(score for report in reports.values() for score in report.cases)
    return grade.GradeReport(cases=cases, calibration=grade.calibrate(cases))


def groups_over(
    report: grade.GradeReport,
    attributes: Mapping[int, Any],
    values: Sequence[Any],
    name: str,
) -> List[Group]:
    """One group per value, over one report's cases.

    The groups partition the report's cases whenever every case carries one of
    the values, which is what the two breakdowns below are of. Each group's lean
    is :func:`error_lean` over that group's cases alone -- the classifier
    section 1 uses, never a second one -- so a direction counted here is the
    direction counted there, and the blocks of a run sum to that run's own block.
    """
    groups: List[Group] = []
    for value in values:
        chosen = tuple(
            score for score in report.cases if attributes.get(score.case_no) == value
        )
        groups.append(
            Group(
                label="{0}, {1}".format(name, value),
                lean=error_lean(report_over(report, [s.case_no for s in chosen])),
                escalated_by_system=sum(
                    1 for score in chosen if score.produced_escalates
                ),
                escalated_in_key=sum(
                    1 for score in chosen if score.expected_escalates
                ),
            )
        )
    return groups


def _group_block(group: Group) -> List[str]:
    """One group: section 1's block for its cases, then its two escalation rates."""
    lines = _error_lean_block(group.label, group.lean)
    total = group.lean.total
    lines.append(
        "   escalated by the system    {0}   Wilson 95% {1}".format(
            _rate(group.escalated_by_system, total),
            v6_runs.wilson_text(group.escalated_by_system, total),
        )
    )
    lines.append(
        "   escalated in the key       {0}   Wilson 95% {1}".format(
            _rate(group.escalated_in_key, total),
            v6_runs.wilson_text(group.escalated_in_key, total),
        )
    )
    return lines


def _breakdown_block(groups: Sequence[Group]) -> List[str]:
    """Every group of one breakdown, then the one line saying how to read them.

    The groups are small, so the line names the smallest of them: a share over
    fourteen cases is a count with a percentage on it, not a rate. The
    filed-by split stays unreported here for the reason section 0 gives.
    """
    lines: List[str] = []
    for group in groups:
        lines.extend(_group_block(group))
    lines.append(
        "   the rows are small -- the smallest group holds {0} case(s) -- so read "
        "them as counts; a split by dispute.filed_by stays unreported for the "
        "reason section 0 gives.".format(min(group.lean.total for group in groups))
    )
    return lines


def _breakdown(
    reports: Mapping[str, grade.GradeReport],
    attributes: Mapping[str, Mapping[int, Any]],
    values: Sequence[Any],
) -> List[Group]:
    """Every measured run's groups, then the both-runs groups, in that order."""
    groups: List[Group] = []
    for name in MEASURED_SETS:
        groups.extend(
            groups_over(reports[name], attributes[name], values, name)
        )
    pooled = combined_report(reports)
    pooled_attributes: Dict[int, Any] = {}
    for name in MEASURED_SETS:
        pooled_attributes.update(attributes[name])
    groups.extend(groups_over(pooled, pooled_attributes, values, "both runs"))
    return groups


def report() -> str:
    """The whole measurement, printed. Reads; writes nothing."""
    runs = {name: measured_run(name) for name in MEASURED_SETS}
    transcript_maps = {name: transcripts(runs[name]) for name in MEASURED_SETS}
    graded = {name: graded_report(runs[name]) for name in MEASURED_SETS}
    leans = {name: error_lean(graded[name]) for name in MEASURED_SETS}
    swaps = {
        name: position_swap(transcript_maps[name]) for name in MEASURED_SETS
    }
    outcomes = {
        name: draft_outcomes(runs[name], transcript_maps[name])
        for name in MEASURED_SETS
    }
    calibrations = {name: calibrate(outcomes[name]) for name in MEASURED_SETS}
    splits = {name: escalate_split(outcomes[name]) for name in MEASURED_SETS}

    lines: List[str] = [
        "Version 6 fairness and calibration -- report",
        "read from the committed version-6 runs under runs/ and the committed "
        "keys; no model call",
        "",
    ]
    for name in MEASURED_SETS:
        lines.append("{0:<12}{1}".format(name, v6_runs._relative(runs[name].run_dir)))
    lines.append("")

    # -- Why not by who filed ---------------------------------------------
    lines.append("== Why not by who filed ==")
    for name in MEASURED_SETS:
        counts = filed_by_counts(name)
        lines.append(
            "   {0:<12}{1} cases, filed by the rider {2}, by the driver {3}".format(
                name,
                case_count(name),
                counts.get("RIDER", 0),
                counts.get("DRIVER", 0),
            )
        )
    lines.append(
        "   a split by dispute.filed_by has one case on one side (the corpus's "
        "single driver-filed dispute), so it is not reported; the three "
        "measurements below are."
    )
    lines.append("")

    # -- 1. Which way the errors lean -------------------------------------
    lines.append("== 1. Which way the errors lean ==")
    for name in MEASURED_SETS:
        lines.extend(_error_lean_block(name, leans[name]))
    combined = _combine_leans(leans)
    lines.extend(_error_lean_block("both runs", combined))
    amount_moves = [m for m in combined.amount_moves]
    lines.append(
        "   cases where both sides are a refund of different sizes: {0}".format(
            _named([m.case_no for m in amount_moves])
        )
    )
    lines.append("")

    # -- 2. The position swap ---------------------------------------------
    lines.append("== 2. The position swap ==")
    for name in MEASURED_SETS:
        lines.extend(_swap_block(name, swaps[name]))
    lines.extend(_swap_block("both runs", _combine_swaps(swaps)))
    lines.append("")

    # -- 3. Calibration ---------------------------------------------------
    lines.append("== 3. Calibration ==")
    for name in MEASURED_SETS:
        lines.extend(_calibration_block(name, calibrations[name], splits[name]))
    pooled_outcomes = outcomes[CORPUS] + outcomes[DEV_V2_EXT]
    lines.extend(
        _calibration_block(
            "both runs",
            calibrate(pooled_outcomes),
            escalate_split(pooled_outcomes),
        )
    )
    lines.append(
        "   drafts of one case are not independent: a case's four drafts answer "
        "the same brief, so the {0} valid drafts are {1} panels rather than {0} "
        "independent draws.".format(
            len(outcomes[CORPUS]) + len(outcomes[DEV_V2_EXT]),
            swaps[CORPUS].total + swaps[DEV_V2_EXT].total,
        )
    )
    lines.append(
        "   the chart is written by: python3 -m eval.fairness --chart "
        "docs/calibration-v6.svg"
    )

    # -- 4. By category ---------------------------------------------------
    # The two breakdowns read the two facts a run does not record -- the
    # category and the amount contested -- from the sets' own public case
    # files, and lean on section 1's classifier for the directions.
    facts = {name: case_facts(name) for name in MEASURED_SETS}
    categories = {
        name: {case_no: category for case_no, (category, _amount) in facts[name].items()}
        for name in MEASURED_SETS
    }
    bands = {
        name: {case_no: band_of(amount) for case_no, (_category, amount) in facts[name].items()}
        for name in MEASURED_SETS
    }
    lines.append("")
    lines.append("== 4. By category ==")
    lines.extend(_breakdown_block(_breakdown(graded, categories, CATEGORIES)))
    lines.append("")
    lines.append("== 5. By the contested amount ==")
    lines.extend(_breakdown_block(_breakdown(graded, bands, BANDS)))
    return "\n".join(lines).rstrip("\n") + "\n"


def _combine_leans(leans: Mapping[str, ErrorLean]) -> ErrorLean:
    total = sum(lean.total for lean in leans.values())
    differing: List[Movement] = []
    for lean in leans.values():
        differing.extend(lean.differing)
    return ErrorLean(total, tuple(sorted(differing, key=lambda m: m.case_no)))


def _combine_swaps(swaps: Mapping[str, PositionSwap]) -> PositionSwap:
    cases: List[SwapCase] = []
    for swap in swaps.values():
        cases.extend(swap.cases)
    return PositionSwap(tuple(sorted(cases, key=lambda c: c.case_no)))


def combined_measurements() -> Tuple[ErrorLean, PositionSwap, Calibration]:
    """The three measurements over both runs together.

    A second entry point beside :func:`report`, for a caller that wants only the
    three combined figures -- the README's rows do -- so it reads the runs once
    and does not re-derive the combination itself.
    """
    runs = {name: measured_run(name) for name in MEASURED_SETS}
    transcript_maps = {name: transcripts(runs[name]) for name in MEASURED_SETS}
    leans = {name: error_lean(graded_report(runs[name])) for name in MEASURED_SETS}
    swaps = {name: position_swap(transcript_maps[name]) for name in MEASURED_SETS}
    pooled: List[DraftOutcome] = []
    for name in MEASURED_SETS:
        pooled.extend(draft_outcomes(runs[name], transcript_maps[name]))
    return _combine_leans(leans), _combine_swaps(swaps), calibrate(pooled)


def error_lean_cell(lean: ErrorLean) -> str:
    """``0 / 1 / 5``: errors towards the rider, the driver and an escalation."""
    return "{0} / {1} / {2}".format(
        lean.count(TOWARDS_RIDER), lean.count(TOWARDS_DRIVER), lean.count(TO_ESCALATION)
    )


def swap_agreement_cell(swap: PositionSwap) -> str:
    """``136/141 = 96.5%``: the swapped draft against the sampled majority."""
    return _rate(swap.agree_all_four, swap.total)


def calibration_error_cell(calibration: Calibration) -> str:
    """``0.088``: the expected calibration error over every valid draft."""
    return render_ece(calibration.ece)


# --------------------------------------------------------------------------
# The chart
# --------------------------------------------------------------------------
# A reliability diagram, drawn by code and deterministic: the same calibration
# gives the same bytes. 800 x 600, white background, ASCII text, no script.
CHART_WIDTH = 800
CHART_HEIGHT = 600
PLOT_LEFT = 90.0
PLOT_RIGHT = 720.0
PLOT_TOP = 80.0
PLOT_BOTTOM = 500.0
TICKS: Tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def _x(value: float) -> float:
    return PLOT_LEFT + value * (PLOT_RIGHT - PLOT_LEFT)


def _y(value: float) -> float:
    return PLOT_BOTTOM - value * (PLOT_BOTTOM - PLOT_TOP)


def _num(value: float) -> str:
    return "{0:.2f}".format(value)


def _text(x: float, y: float, content: str, **attributes: str) -> str:
    rendered = "".join(
        ' {0}="{1}"'.format(name.replace("_", "-"), attributes[name])
        for name in sorted(attributes)
    )
    return '<text x="{0}" y="{1}"{2}>{3}</text>'.format(
        _num(x), _num(y), rendered, content
    )


def chart_svg(calibration: Calibration, label: str) -> str:
    """The reliability diagram for one calibration, as SVG.

    Mean stated confidence runs along x and the share of drafts correct along y;
    one point is drawn per bin, its radius growing with the bin's count; the
    diagonal is perfect calibration and the vertical line is the confidence
    floor the bins are built around.
    """
    counts = [bin_.count for bin_ in calibration.bins]
    largest = max(counts) if counts else 0
    parts: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" '
        'viewBox="0 0 {0} {1}">'.format(CHART_WIDTH, CHART_HEIGHT),
        '<rect x="0" y="0" width="{0}" height="{1}" fill="#ffffff"/>'.format(
            CHART_WIDTH, CHART_HEIGHT
        ),
        _text(
            400.0,
            34.0,
            "Calibration of the version-6 judge drafts",
            **{
                "font-family": "Helvetica, Arial, sans-serif",
                "font-size": "19",
                "text-anchor": "middle",
                "fill": "#111111",
            }
        ),
        _text(
            400.0,
            56.0,
            "{0}; one point per bin, sized by the number of drafts".format(label),
            **{
                "font-family": "Helvetica, Arial, sans-serif",
                "font-size": "12",
                "text-anchor": "middle",
                "fill": "#444444",
            }
        ),
    ]

    # Gridlines, then the plot border.
    for tick in TICKS:
        parts.append(
            '<line x1="{0}" y1="{1}" x2="{2}" y2="{3}" stroke="#e6e6e6" '
            'stroke-width="1"/>'.format(
                _num(_x(tick)), _num(PLOT_TOP), _num(_x(tick)), _num(PLOT_BOTTOM)
            )
        )
        parts.append(
            '<line x1="{0}" y1="{1}" x2="{2}" y2="{3}" stroke="#e6e6e6" '
            'stroke-width="1"/>'.format(
                _num(PLOT_LEFT), _num(_y(tick)), _num(PLOT_RIGHT), _num(_y(tick))
            )
        )
    parts.append(
        '<rect x="{0}" y="{1}" width="{2}" height="{3}" fill="none" '
        'stroke="#333333" stroke-width="1.5"/>'.format(
            _num(PLOT_LEFT),
            _num(PLOT_TOP),
            _num(PLOT_RIGHT - PLOT_LEFT),
            _num(PLOT_BOTTOM - PLOT_TOP),
        )
    )

    # The diagonal, then the floor.
    parts.append(
        '<line x1="{0}" y1="{1}" x2="{2}" y2="{3}" stroke="#999999" '
        'stroke-width="1.5" stroke-dasharray="6,4"/>'.format(
            _num(_x(0.0)), _num(_y(0.0)), _num(_x(1.0)), _num(_y(1.0))
        )
    )
    parts.append(
        _text(
            _x(1.0) - 6.0,
            _y(1.0) + 18.0,
            "perfect calibration",
            **{
                "font-family": "Helvetica, Arial, sans-serif",
                "font-size": "11",
                "text-anchor": "end",
                "fill": "#777777",
            }
        )
    )
    floor_x = _x(float(FLOOR))
    parts.append(
        '<line x1="{0}" y1="{1}" x2="{2}" y2="{3}" stroke="#c0392b" '
        'stroke-width="1.5" stroke-dasharray="4,3"/>'.format(
            _num(floor_x), _num(PLOT_TOP), _num(floor_x), _num(PLOT_BOTTOM)
        )
    )
    parts.append(
        _text(
            floor_x + 6.0,
            PLOT_TOP + 16.0,
            "{0} floor".format(_floor_text()),
            **{
                "font-family": "Helvetica, Arial, sans-serif",
                "font-size": "11",
                "fill": "#c0392b",
            }
        )
    )

    # The bins.
    for bin_ in calibration.bins:
        if bin_.count == 0 or bin_.mean_confidence is None:
            continue
        share = bin_.share_correct
        if share is None:
            continue
        radius = 4.0 + 14.0 * (float(bin_.count) / float(largest)) ** 0.5
        parts.append(
            '<circle cx="{0}" cy="{1}" r="{2}" fill="#2c7fb8" fill-opacity="0.55" '
            'stroke="#1f5f8b" stroke-width="1.5"/>'.format(
                _num(_x(float(bin_.mean_confidence))),
                _num(_y(float(share))),
                _num(radius),
            )
        )

    # Tick labels and axis titles.
    for tick in TICKS:
        parts.append(
            _text(
                _x(tick),
                PLOT_BOTTOM + 20.0,
                "{0:.1f}".format(tick),
                **{
                    "font-family": "Helvetica, Arial, sans-serif",
                    "font-size": "12",
                    "text-anchor": "middle",
                    "fill": "#333333",
                }
            )
        )
        parts.append(
            _text(
                PLOT_LEFT - 10.0,
                _y(tick) + 4.0,
                "{0:.1f}".format(tick),
                **{
                    "font-family": "Helvetica, Arial, sans-serif",
                    "font-size": "12",
                    "text-anchor": "end",
                    "fill": "#333333",
                }
            )
        )
    parts.append(
        _text(
            (PLOT_LEFT + PLOT_RIGHT) / 2.0,
            PLOT_BOTTOM + 48.0,
            "mean stated confidence",
            **{
                "font-family": "Helvetica, Arial, sans-serif",
                "font-size": "13",
                "text-anchor": "middle",
                "fill": "#333333",
            }
        )
    )
    parts.append(
        '<text x="26.00" y="{0}" font-family="Helvetica, Arial, sans-serif" '
        'font-size="13" text-anchor="middle" fill="#333333" '
        'transform="rotate(-90 26.00 {0})">share of drafts correct</text>'.format(
            _num((PLOT_TOP + PLOT_BOTTOM) / 2.0)
        )
    )
    parts.append(
        _text(
            PLOT_LEFT,
            PLOT_BOTTOM + 76.0,
            "point size: {0} drafts (smallest bin) to {1} (largest)".format(
                min(counts) if counts else 0, largest
            ),
            **{
                "font-family": "Helvetica, Arial, sans-serif",
                "font-size": "11",
                "fill": "#666666",
            }
        )
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def chart_path_from(
    runs: Mapping[str, v6_runs.V6Run],
    transcript_maps: Optional[Mapping[str, Mapping[int, Mapping[str, Any]]]] = None,
) -> Calibration:
    """The calibration the committed chart is drawn from: both runs, pooled."""
    outcomes: List[DraftOutcome] = []
    for name in MEASURED_SETS:
        held = None if transcript_maps is None else transcript_maps[name]
        outcomes.extend(draft_outcomes(runs[name], held))
    return calibrate(outcomes)


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.fairness",
        description=(
            "Measure fairness and calibration over the version-6 development "
            "runs, or write the reliability diagram. Read-only; no model call."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--report",
        action="store_true",
        help="print the three measurements, computed from the committed runs and keys",
    )
    group.add_argument(
        "--chart",
        type=Path,
        metavar="PATH",
        help="write the reliability diagram to PATH",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.report:
        sys.stdout.write(report())
        return 0

    # The destination is the caller's to name, so it is refused before anything
    # is written. The rule is the repository's one helper for it.
    try:
        destination = sealed_roots.refuse_a_sealed_destination(arguments.chart)
    except sealed_roots.SealedDestinationError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1
    runs = {name: measured_run(name) for name in MEASURED_SETS}
    svg = chart_svg(chart_path_from(runs), "both development runs pooled")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg, encoding="utf-8")
    print("wrote {0}".format(destination), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
