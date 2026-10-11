"""What the early-majority rule would have saved, replayed from the record.

The judge's panel is asked together -- ``--parallel-calls`` -- and a case waits
for the slowest draft. A majority of a panel of four is three, and three drafts
that have already agreed cannot be changed by a fourth that has not answered, so
waiting for it costs time and buys nothing. ``--early-majority`` publishes at the
third agreeing draft. This module asks **what that rule would have saved** on the
runs that were actually made.

It answers four things, over every version-6 case with four judge drafts in the
**two development runs** -- ``runs/policy-v6/`` and
``runs/dev-v2-ext/policy-v6/``:

* how many cases the rule would have stopped early;
* whether the published ruling would have been the same, **asserted** rather
  than assumed: the four graded fields of the ruling the panel would have
  published at three are compared with the four the whole panel published;
* the judge stage's time with and without the rule -- median, 90th percentile
  and maximum; and
* the whole case's, which is the slower advocate's call plus the judge stage.

**The third sealed set's run is not read.** It was measured once, in
``runs/sealed-v1/``, and the README promises that nothing after that run
re-reads it; a figure over it here would break that promise and a pooled total
would be worse still. The sealed run is therefore neither read nor printed by
this module, and the figures below are over the two development runs alone.

**The rule is the pipeline's own.** The floor on the sampled drafts is
:data:`tribunal.pipeline.EARLY_MAJORITY_MIN_SAMPLED`, the two draft kinds are the
pipeline's own names for them, and a draft's four graded fields are reduced by
:func:`tribunal.pipeline.vote_key` -- the reduction the judge's vote is taken
with. What is *not* the pipeline's is the order the drafts came back in: the run
recorded each draft's own duration and not the order the answers arrived in, so
the replay returns them in increasing duration and stops at the first draft at
which the rule's three conditions hold.

**These are replayed timings and a live run may differ.** The durations are the
ones the provider reported for calls that were all made together; a live run's
panel is rate-limited by the same client, its drafts contend with the other
cases' calls, and the draft the rule stops waiting for may in a live run be the
fast one. The published ruling is the part of this that is not a timing: it is
asserted over every case.

No model call is made and no browser is launched. The module reads the committed
runs and writes nothing.

Run from the project root with::

    python3 -m eval.early_majority --report
"""

from __future__ import annotations

import argparse
import collections
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from eval import fairness, v6_runs
from tribunal import pipeline, transcript as transcript_module

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The two runs measured. Both are the version-6 development runs
# ``eval.v6_runs`` names. The third sealed set's run is deliberately absent:
# it is read once by its own report and nothing after that run re-reads it, so
# no figure here may include it.
CORPUS = "corpus"
DEV_V2_EXT = "dev-v2-ext"
MEASURED_SETS: Tuple[str, ...] = (CORPUS, DEV_V2_EXT)

# The panel the rule is replayed at. Every measured run was made with four
# judge drafts, and the rule's own floor is stated for four; a case that
# recorded another number is counted and not replayed.
VOTES = pipeline.DEFAULT_JUDGE_VOTES

# The rule's own floor, read from the pipeline rather than copied, so this
# module cannot disagree with the code it is measuring.
MIN_SAMPLED = pipeline.EARLY_MAJORITY_MIN_SAMPLED

SAMPLED = pipeline.DRAFT_SAMPLED
POSITION_SWAPPED = pipeline.DRAFT_POSITION_SWAPPED

# The two advocate roles, as the transcript records them. The advocate stage's
# own time is the slower of the two, because the two are asked together.
ADVOCATE_ROLES: Tuple[str, ...] = (
    transcript_module.ROLE_RIDER_ADVOCATE,
    transcript_module.ROLE_DRIVER_ADVOCATE,
)


class EarlyMajorityError(Exception):
    """The measurement could not be made, or the rule changed a ruling."""


# --------------------------------------------------------------------------
# Reading the record
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MeasuredRun:
    """One run of the version-6 batch: its name and where it lives."""

    name: str
    run_dir: Path


@dataclass(frozen=True)
class Draft:
    """One recorded judge draft: what it was, whether it voted, and how long."""

    index: int
    kind: str
    valid: bool
    key: Optional[Tuple[Any, ...]]
    seconds: Decimal


def measured_runs() -> Tuple[MeasuredRun, ...]:
    """The two development runs, by the paths ``eval.v6_runs`` names them."""
    runs = {
        CORPUS: v6_runs.run_by_name(CORPUS).run_dir,
        DEV_V2_EXT: v6_runs.run_by_name(DEV_V2_EXT).run_dir,
    }
    return tuple(MeasuredRun(name, runs[name]) for name in MEASURED_SETS)


def case_numbers(run_dir: Path) -> Tuple[int, ...]:
    """Every case the run directory holds, by number.

    Read off the directory rather than off a set's index: the index is a
    registration, and what this module measures is what the run wrote.
    """
    return tuple(sorted(v6_runs.case_files(Path(run_dir))))


def transcript_for(run_dir: Path, case_no: int) -> Mapping[str, Any]:
    """One case's transcript, by the name the case's own file records."""
    document = v6_runs.read_json(v6_runs.case_path(run_dir, case_no))
    path = fairness.transcript_path(Path(run_dir), document, case_no)
    return v6_runs.read_json(path)


def _entry_seconds(transcript: Mapping[str, Any], index: Any) -> Decimal:
    """One transcript entry's own duration, or zero for an entry that is absent."""
    entries = transcript.get("entries")
    if not isinstance(entries, list) or not isinstance(index, int):
        return Decimal(0)
    if index < 0 or index >= len(entries):
        return Decimal(0)
    entry = entries[index]
    value = entry.get("duration_seconds") if isinstance(entry, Mapping) else None
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def drafts_of(transcript: Mapping[str, Any]) -> Tuple[Draft, ...]:
    """Every judge draft a transcript records, with its own duration.

    A draft's duration is the sum of the durations of the transcript entries it
    occupies, because a draft whose first answer was unusable made two calls one
    after the other. Its four graded fields are the pipeline's own reading of the
    last ruling it parsed to, through :func:`tribunal.pipeline.vote_key`.
    """
    vote = transcript.get("vote")
    vote = vote if isinstance(vote, Mapping) else {}
    found: List[Draft] = []
    for record in vote.get("drafts") or []:
        if not isinstance(record, Mapping):
            continue
        entries = [index for index in record.get("entries") or [] if isinstance(index, int)]
        seconds = sum(
            (_entry_seconds(transcript, index) for index in entries), Decimal(0)
        )
        found.append(
            Draft(
                index=int(record.get("draft") or 0),
                kind=str(record.get("kind")),
                valid=bool(record.get("valid")),
                key=fairness.draft_key(transcript, record),
                seconds=seconds,
            )
        )
    return tuple(found)


def advocate_stage(transcript: Mapping[str, Any]) -> Decimal:
    """The slower advocate's own call, which is what the two of them cost.

    The two advocates are asked together, so the stage's time is the slower of
    the two; each role's time is the sum of its entries' durations, for the same
    reason a draft's is.
    """
    entries = transcript.get("entries")
    if not isinstance(entries, list):
        return Decimal(0)
    totals: Dict[str, Decimal] = {role: Decimal(0) for role in ADVOCATE_ROLES}
    for position, entry in enumerate(entries):
        role = entry.get("role") if isinstance(entry, Mapping) else None
        if role in totals:
            totals[role] += _entry_seconds(transcript, position)
    return max(totals.values()) if totals else Decimal(0)


# --------------------------------------------------------------------------
# The rule, replayed
# --------------------------------------------------------------------------
def enough(returned: Sequence[Draft], threshold: int) -> bool:
    """Whether the panel may publish with the drafts that have returned.

    The rule's three conditions, in the order they can be answered: the
    position-swapped draft is back, at least :data:`MIN_SAMPLED` sampled drafts
    are back, and a majority of the returned drafts are valid and agree on all
    four graded fields together.
    """
    if not any(draft.kind == POSITION_SWAPPED for draft in returned):
        return False
    if sum(1 for draft in returned if draft.kind == SAMPLED) < MIN_SAMPLED:
        return False
    keys = [draft.key for draft in returned if draft.valid and draft.key is not None]
    if len(keys) < threshold:
        return False
    return collections.Counter(keys).most_common(1)[0][1] >= threshold


def awaited_drafts(drafts: Sequence[Draft], threshold: int) -> Tuple[Draft, ...]:
    """The drafts the panel waits for, in the order the answers arrived.

    The recorded durations are the only arrival information the run kept, so the
    replay returns the drafts in increasing duration and stops at the first one
    at which the rule's conditions hold. A rule that never holds waits for every
    draft, exactly as the pipeline does.
    """
    ordered = sorted(drafts, key=lambda draft: draft.seconds)
    returned: List[Draft] = []
    for draft in ordered:
        returned.append(draft)
        if enough(returned, threshold):
            return tuple(returned)
    return tuple(drafts)


def published(drafts: Sequence[Draft], votes: int) -> Optional[Tuple[Any, ...]]:
    """The four graded fields a set of drafts would publish, or ``None``.

    The reduction is :func:`tribunal.pipeline._reduce_vote`'s, applied to the
    drafts that counted: the largest group of valid drafts wins, a tie going to
    the group whose first draft came earliest, and nothing is published unless
    the group and the valid drafts both reach the threshold. ``None`` is an
    escalation -- the panel carried nothing.
    """
    threshold = votes // 2 + 1
    valid = [draft for draft in drafts if draft.valid and draft.key is not None]
    if not valid:
        return None
    groups: Dict[Tuple[Any, ...], List[Draft]] = {}
    for draft in valid:
        groups.setdefault(draft.key, []).append(draft)
    winner_key, winner = max(
        groups.items(), key=lambda item: (len(item[1]), -item[1][0].index)
    )
    if len(winner) >= threshold and len(valid) >= threshold:
        return winner_key
    return None


# --------------------------------------------------------------------------
# The measurement
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Case:
    """One case with four judge drafts, and what the rule would have made of it."""

    case_no: int
    votes: int
    threshold: int
    drafts: Tuple[Draft, ...]
    awaited: Tuple[Draft, ...]
    advocates: Decimal
    # The four graded fields the whole panel published and the four the panel
    # would have published at three. Equal in every case the rule stops early,
    # which is the assertion below.
    published_all: Optional[Tuple[Any, ...]]
    published_early: Optional[Tuple[Any, ...]]

    @property
    def stopped_early(self) -> bool:
        return len(self.awaited) < len(self.drafts)

    @property
    def not_awaited(self) -> Tuple[int, ...]:
        awaited = {draft.index for draft in self.awaited}
        return tuple(draft.index for draft in self.drafts if draft.index not in awaited)

    @property
    def judge_with(self) -> Decimal:
        return max((draft.seconds for draft in self.awaited), default=Decimal(0))

    @property
    def judge_without(self) -> Decimal:
        return max((draft.seconds for draft in self.drafts), default=Decimal(0))

    @property
    def case_with(self) -> Decimal:
        return self.advocates + self.judge_with

    @property
    def case_without(self) -> Decimal:
        return self.advocates + self.judge_without

    @property
    def vote_sentence_moves(self) -> bool:
        """Whether the explanation's own vote sentence would have read differently.

        The four graded fields are the same either way. The sentence is not: a
        panel that stopped at three reports three of four agreeing, and the whole
        panel reports the same -- unless the draft the rule did not wait for
        would have agreed too, in which case the whole panel reports four of
        four. The ruling a reader acts on is the four fields; this says how often
        the prose around it would have moved.
        """
        if not self.stopped_early or self.published_early is None:
            return False
        skipped = {draft.index for draft in self.drafts} - {
            draft.index for draft in self.awaited
        }
        return any(
            draft.valid and draft.key == self.published_early
            for draft in self.drafts
            if draft.index in skipped
        )


def measure_case(
    case_no: int, transcript: Mapping[str, Any], votes: int = VOTES
) -> Optional[Case]:
    """One case, replayed. ``None`` when it does not hold four judge drafts."""
    drafts = drafts_of(transcript)
    if len(drafts) != votes:
        return None
    threshold = votes // 2 + 1
    awaited = awaited_drafts(drafts, threshold)
    return Case(
        case_no=case_no,
        votes=votes,
        threshold=threshold,
        drafts=drafts,
        awaited=awaited,
        advocates=advocate_stage(transcript),
        published_all=published(drafts, votes),
        published_early=published(awaited, votes),
    )


@dataclass(frozen=True)
class RunMeasurement:
    """One run's cases, and the ones of them that hold four judge drafts."""

    name: str
    cases: int
    measured: Tuple[Case, ...]


def measure_run(run: MeasuredRun) -> RunMeasurement:
    numbers = case_numbers(run.run_dir)
    cases: List[Case] = []
    for case_no in numbers:
        transcript = transcript_for(run.run_dir, case_no)
        case = measure_case(case_no, transcript)
        if case is not None:
            cases.append(case)
    return RunMeasurement(run.name, len(numbers), tuple(cases))


def assert_the_ruling_is_unchanged(cases: Sequence[Case]) -> None:
    """The assertion the whole measurement rests on.

    A rule that stopped at three drafts and published something else would not be
    a saving, it would be a different answer. Every case is checked, not only the
    ones the rule stops early on, so a case that never fires is evidence too.
    """
    for case in cases:
        if case.published_early != case.published_all:
            raise EarlyMajorityError(
                "case {0}: the panel would have published {1} at {2} drafts and "
                "{3} at all {4}, so the rule changes the ruling".format(
                    case.case_no,
                    case.published_early,
                    len(case.awaited),
                    case.published_all,
                    len(case.drafts),
                )
            )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _seconds(value: Decimal) -> str:
    return "{0:.1f}".format(value)


def _named(numbers: Sequence[int]) -> str:
    items = [str(number) for number in numbers]
    if not items:
        return "none"
    if len(items) == 1:
        return items[0]
    return "{0} and {1}".format(", ".join(items[:-1]), items[-1])


def _row(label: str, cases: Sequence[Case], pick) -> str:
    values = [pick(case) for case in cases]
    return "   {0:<20}median {1:>7}   p90 {2:>7}   max {3:>7}".format(
        label,
        _seconds(v6_runs._median(values)),
        _seconds(v6_runs._percentile(values, Decimal("0.9"))),
        _seconds(max(values) if values else Decimal(0)),
    )


def report() -> str:
    """The whole measurement, printed. Reads; writes nothing."""
    runs = measured_runs()
    measurements = [measure_run(run) for run in runs]
    everything: List[Case] = []
    for measurement in measurements:
        everything.extend(measurement.measured)
    assert_the_ruling_is_unchanged(everything)

    lines: List[str] = [
        "Early majority, replayed from the version-6 record",
        "read from the committed runs under runs/; no model call, no browser",
        "",
        "the rule: the position-swapped draft plus {0} sampled drafts back, and "
        "{1} of the returned drafts valid and agreeing on all four graded "
        "fields".format(MIN_SAMPLED, VOTES // 2 + 1),
        "",
        "== The cases ==",
    ]
    for measurement in measurements:
        lines.append(
            "   {0:<12}{1} cases, {2} with four judge drafts".format(
                measurement.name, measurement.cases, len(measurement.measured)
            )
        )
    lines.append(
        "   {0:<12}{1} cases, {2} with four judge drafts".format(
            "all",
            sum(measurement.cases for measurement in measurements),
            len(everything),
        )
    )

    early = [case for case in everything if case.stopped_early]
    lines.append("")
    lines.append("== The rule ==")
    lines.append(
        "   would stop early        {0} of {1}".format(len(early), len(everything))
    )
    lines.append(
        "   would wait for all four {0} of {1}".format(
            len(everything) - len(early), len(everything)
        )
    )
    lines.append(
        "   the published ruling is identical in every case: asserted over all "
        "{0} (the four graded fields; {1} would have stopped early)".format(
            len(everything), len(early)
        )
    )
    moved = [case for case in everything if case.vote_sentence_moves]
    lines.append(
        "   the explanation's vote sentence would differ in {0} of them: {1}".format(
            len(moved), _named([case.case_no for case in moved])
        )
    )
    lines.append(
        "     the four graded fields are the same either way; the sentence reads "
        "'3 of the 4 agreed' where the whole panel would have read 'every draft "
        "agreed', because the draft the rule did not wait for would have agreed"
    )

    lines.append("")
    lines.append("== The judge stage, seconds (the slowest draft the panel waited for) ==")
    lines.append(_row("with the rule", everything, lambda case: case.judge_with))
    lines.append(_row("without it", everything, lambda case: case.judge_without))
    saved = [case.judge_without - case.judge_with for case in everything]
    lines.append(
        "   {0:<20}median {1:>7}   p90 {2:>7}   max {3:>7}".format(
            "saved",
            _seconds(v6_runs._median(saved)),
            _seconds(v6_runs._percentile(saved, Decimal("0.9"))),
            _seconds(max(saved) if saved else Decimal(0)),
        )
    )
    lines.append(
        "   over the {0} the rule stops early on: median {1}   p90 {2}   "
        "max {3}".format(
            len(early),
            _seconds(v6_runs._median([case.judge_without - case.judge_with for case in early])),
            _seconds(
                v6_runs._percentile(
                    [case.judge_without - case.judge_with for case in early],
                    Decimal("0.9"),
                )
            ),
            _seconds(
                max(
                    [case.judge_without - case.judge_with for case in early],
                    default=Decimal(0),
                )
            ),
        )
    )
    # The bound the switch is motivated by, for comparison: always stopping at
    # the third-fastest draft. The rule is above it because the position-swapped
    # draft is always waited for -- a panel whose three fastest drafts are all
    # sampled waits for the swapped one -- and because the first three do not
    # always agree.
    third = [sorted((draft.seconds for draft in case.drafts))[2] for case in everything]
    lines.append(
        "   the ideal bound -- always stopping at the third-fastest draft -- is "
        "median {0}   p90 {1}   max {2}".format(
            _seconds(v6_runs._median(third)),
            _seconds(v6_runs._percentile(third, Decimal("0.9"))),
            _seconds(max(third) if third else Decimal(0)),
        )
    )

    lines.append("")
    lines.append("== The whole case, seconds (the slower advocate plus the judge stage) ==")
    lines.append(_row("with the rule", everything, lambda case: case.case_with))
    lines.append(_row("without it", everything, lambda case: case.case_without))
    case_saved = [case.case_without - case.case_with for case in everything]
    lines.append(
        "   {0:<20}median {1:>7}   p90 {2:>7}   max {3:>7}".format(
            "saved",
            _seconds(v6_runs._median(case_saved)),
            _seconds(v6_runs._percentile(case_saved, Decimal("0.9"))),
            _seconds(max(case_saved) if case_saved else Decimal(0)),
        )
    )

    lines.append("")
    lines.append("== These are replayed timings ==")
    lines.append(
        "   the durations are the ones the provider reported for calls that were "
        "all made together; a live run's panel is rate-limited by the same "
        "client and contends with the other cases' calls, and the draft the rule "
        "stops waiting for may in a live run be the fast one. A live run may "
        "differ."
    )
    lines.append(
        "   what is not a timing is the published ruling: it is asserted "
        "identical over every case above."
    )
    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.early_majority",
        description=(
            "Replay the early-majority rule over the version-6 runs' recorded "
            "drafts and durations, and print what it would have saved. "
            "Read-only; no model call is made."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--report",
        action="store_true",
        help="print the replay, computed from the committed runs under runs/",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.report:
        sys.stdout.write(report())
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
