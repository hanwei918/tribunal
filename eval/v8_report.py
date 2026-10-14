"""The version-8 measurements, read off the committed version-8 runs.

The front page and the README still lead with figures measured on the
version-6 runs: the position swap ``136/141``, the expected calibration error
``0.088``, and ``112 of 151`` decided with no person. Those cannot be turned
into version-8 figures by editing, because the 151 cases were keyed by the
team's version-6 rules. But the version-8 runs already hold everything the same
measurements need, so they are measured **there**, by the same functions, with
**no model call**: this module reads the two committed runs, the two committed
keys and the two sets' own public case files, and it writes nothing.

**The two sets, separately and never pooled.** ``dev-v8`` is the 40-case
development set and ``ryde-v8`` the organisers' two samples, both registered for
policy version 8, so each run sits one level down at
``runs/<set>/policy-v8/<model>/``. Nothing here is added to the other, to the
version-6 figures, or to any sealed set's: a figure over 40 cases plus another
over 2 is not a measurement of 42.

**What each measurement is.**

* **Four-field agreement** -- the share of cases whose produced ruling equals
  the key on all four graded fields, through the same grader
  :func:`eval.fairness.graded_report` uses, so "agrees on all four graded
  fields" means what it means in the pipeline rather than a second reading.
* **Escalation** -- the cases the run sent to a person, the cases the key sends,
  the cases both do, and the precision and recall of the first against the
  second.
* **Decided with no person** -- the cases whose published ruling is not
  ``ESCALATE``, over the cases. A case sent to a person is one the system did
  not decide, which is why the escalation count is its complement.
* **The clock and the cost** -- the wall clock's median and 90th percentile
  (:func:`eval.v6_runs._median`, :func:`eval.v6_runs._percentile`) and the model
  cost's median and total at the repository's prices, by the formula
  :func:`eval.business_value.costs_per_case` uses.
* **The position swap** -- each case's swapped draft held against its sampled
  majority, on all four graded fields and on the ruling alone, through
  :func:`eval.fairness.position_swap`. The cases it cannot hold are named with
  the reason: no judge was asked, or no valid swapped draft.
* **Calibration** -- the valid judge drafts, binned, with the expected
  calibration error to three decimals (:func:`eval.fairness.render_ece`), and
  the split taken at the **version-8 bar** of ``0.80`` (POL-RD-25 and
  POL-GEN-22's middle band) rather than at version 6's ``0.70``. The bins are
  the sheet's and do not move; only the bar the split is taken at does, which is
  what the ``floor`` keyword :func:`eval.fairness.calibrate` gained is for.
* **Which way the errors lean** -- every case that differs from its key, by the
  direction its ruling moved, through :func:`eval.fairness.error_lean`.

**The note the report ends with, and why.** ``dev-v8`` is development data the
team tuned against, so no figure from it is a generalisation figure. The drafts
of one case answer the same brief and are not independent draws, so the valid
drafts are panels rather than independent samples. And ``ryde-v8`` holds three
valid judge drafts, which is too few for a calibration figure to mean anything;
the report says so where it prints one.

Run from the project root with::

    python3 -m eval.v8_report --report
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from eval import development_sets, fairness, grade, run_benchmark, v6_runs

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The model every run was made on, resolved the way ``tools/check_figures.py``
# resolves it so the run directory is named by the same slug.
MODEL = run_benchmark.resolve_model(None)

# The two version-8 sets, in the order the report prints them.
V8_SET_NAMES: Tuple[str, ...] = ("dev-v8", "ryde-v8")

# The version-8 confidence bar: POL-RD-25 and POL-GEN-22's middle band, rather
# than the 0.70 the version-6 bins are built around. The bins themselves are
# unchanged -- this is where the floor **split** is taken, not a second bin edge.
V8_FLOOR = Decimal("0.80")

# The reason a case cannot be held against a sampled majority, in the words the
# report prints. The first is a case nobody asked a judge about; the second is a
# case the judge saw but whose swapped draft is not valid.
NO_JUDGE_ASKED = "no judge was asked"
NO_VALID_SWAPPED = "no valid swapped draft"
NO_VALID_SAMPLED = "no valid sampled draft"

# The two kinds of draft a case's vote holds.
SAMPLED = "sampled"
POSITION_SWAPPED = "position_swapped"


class V8ReportError(Exception):
    """A measurement could not be made, or a value it depends on has moved."""


# --------------------------------------------------------------------------
# Reading the two runs
# --------------------------------------------------------------------------
def measured_run(name: str) -> v6_runs.V6Run:
    """One version-8 set as the record the fairness reads take.

    The set is read through its own registration, and the run directory is the
    one the run was **written to** --
    :func:`eval.development_sets.run_dir_at_its_version`, which is
    ``runs/<set>/policy-v8/<model>/`` for a set registered for a policy base.
    The record is built here and is deliberately **not** added to
    :data:`eval.v6_runs.RUNS`, because that tuple is the version-6 batch and a
    version-8 set in it would change what every version-6 figure covers.
    """
    if name not in V8_SET_NAMES:
        raise V8ReportError(
            "{0!r} is not one of the version-8 sets: {1}".format(
                name, ", ".join(V8_SET_NAMES)
            )
        )
    development_set = development_sets.named(name)
    return v6_runs.V6Run(
        name=development_set.name,
        run_dir=development_sets.run_dir_at_its_version(development_set, MODEL),
        cases=development_set.cases,
        key_path=development_set.key_path,
        registered_size=len(development_set.cases),
        summary=development_set.summary,
    )


def case_documents(run: v6_runs.V6Run) -> Dict[int, Dict[str, Any]]:
    """Every case file of one run, by case number."""
    return v6_runs.documents(run.run_dir, run.cases)


def wall_seconds(documents: Mapping[int, Mapping[str, Any]]) -> List[Any]:
    """Every case's wall clock, in case-number order."""
    return [
        documents[case_no].get("wall_seconds") for case_no in sorted(documents)
    ]


def case_costs(documents: Mapping[int, Mapping[str, Any]]) -> List[Decimal]:
    """Every case's model cost, at the prices the repository bills at.

    The arithmetic is :func:`eval.business_value.costs_per_case`'s own: prompt
    minus cached at the input price, cached at the cached-input price and
    completion at the output price, over a million. The same three prices are
    read from :mod:`eval.v6_runs`, so a version-8 cost figure is the one that
    module would print for those tokens rather than a second reading of them.
    """
    costs: List[Decimal] = []
    for case_no in sorted(documents):
        tokens = documents[case_no].get("tokens") or {}
        prompt = Decimal(tokens.get("prompt_tokens", 0))
        cached = Decimal(tokens.get("cached_tokens", 0))
        completion = Decimal(tokens.get("completion_tokens", 0))
        costs.append(
            (
                (prompt - cached) * v6_runs.PRICE_INPUT
                + cached * v6_runs.PRICE_CACHED_INPUT
                + completion * v6_runs.PRICE_OUTPUT
            )
            / v6_runs.MILLION
        )
    return costs


# --------------------------------------------------------------------------
# The position swap's absent cases, and why
# --------------------------------------------------------------------------
def _valid_keys(
    transcript: Mapping[str, Any],
    drafts: Sequence[Mapping[str, Any]],
    kind: str,
) -> List[Tuple[Any, ...]]:
    """The four-field keys of one kind's valid drafts, a draft with no ruling out.

    The same reading :func:`eval.fairness.position_swap` takes: a draft counts
    when its kind matches, its ``valid`` flag is set, and it parsed to a ruling
    -- so a valid draft carrying no readable ruling is not a key and is not a
    majority of one.
    """
    found = [
        fairness.draft_key(transcript, draft)
        for draft in drafts
        if draft.get("kind") == kind and draft.get("valid")
    ]
    return [key for key in found if key is not None]


def swap_absent(
    run: v6_runs.V6Run, transcript_map: Mapping[int, Mapping[str, Any]]
) -> Tuple[Tuple[int, str], ...]:
    """Every case the position swap cannot hold, and the reason it cannot.

    A case is in the measurement when its swapped draft is valid **and** at
    least one sampled draft is valid, which is the swap's own denominator. The
    complement is reported rather than left as a gap: a case nobody asked a
    judge about is not a case the swap passed, and a case whose swapped draft
    was voided is not one it failed.
    """
    absent: List[Tuple[int, str]] = []
    for case_no in sorted(run.cases):
        transcript = transcript_map.get(case_no)
        if transcript is None:
            absent.append((case_no, NO_JUDGE_ASKED))
            continue
        vote = transcript.get("vote")
        vote = vote if isinstance(vote, Mapping) else {}
        drafts = [
            draft for draft in vote.get("drafts") or [] if isinstance(draft, Mapping)
        ]
        if not drafts:
            absent.append((case_no, NO_JUDGE_ASKED))
            continue
        sampled = _valid_keys(transcript, drafts, SAMPLED)
        swapped = _valid_keys(transcript, drafts, POSITION_SWAPPED)
        if not swapped:
            absent.append((case_no, NO_VALID_SWAPPED))
        elif not sampled:
            absent.append((case_no, NO_VALID_SAMPLED))
    return tuple(absent)


# --------------------------------------------------------------------------
# One set's measurements
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Measurements:
    """Everything one version-8 set's measurement reads, computed once."""

    name: str
    run_dir: Path
    key_path: Optional[Path]
    cases: int
    exact: int
    escalated_produced: int
    escalated_expected: int
    true_positives: int
    false_positives: int
    false_negatives: int
    decided_with_no_person: int
    wall_median: Optional[Decimal]
    wall_p90: Optional[Decimal]
    cost_median: Optional[Decimal]
    cost_total: Decimal
    swap: fairness.PositionSwap
    absent: Tuple[Tuple[int, str], ...]
    calibration: fairness.Calibration
    outcomes: Tuple[fairness.DraftOutcome, ...]
    below_escalations: int
    lean: fairness.ErrorLean

    @property
    def precision(self) -> Optional[Decimal]:
        return grade._ratio(
            self.true_positives, self.true_positives + self.false_positives
        )

    @property
    def recall(self) -> Optional[Decimal]:
        return grade._ratio(
            self.true_positives, self.true_positives + self.false_negatives
        )


def measure(name: str) -> Measurements:
    """One version-8 set's whole measurement, from the committed run."""
    run = measured_run(name)
    report = fairness.graded_report(run)
    transcript_map = fairness.transcripts(run)
    documents = case_documents(run)
    outcomes = fairness.draft_outcomes(run, transcript_map)
    calibration = fairness.calibrate(outcomes, floor=V8_FLOOR)
    calibration_block = report.calibration
    walls = wall_seconds(documents)
    costs = case_costs(documents)
    return Measurements(
        name=run.name,
        run_dir=run.run_dir,
        key_path=run.key_path,
        cases=report.total,
        exact=report.exact_matches,
        escalated_produced=len(calibration_block.produced_escalations),
        escalated_expected=len(calibration_block.expected_escalations),
        true_positives=len(calibration_block.true_positives),
        false_positives=len(calibration_block.false_positives),
        false_negatives=len(calibration_block.false_negatives),
        decided_with_no_person=report.total - len(calibration_block.produced_escalations),
        wall_median=v6_runs._median(walls),
        wall_p90=v6_runs._percentile(walls, Decimal("0.9")),
        cost_median=v6_runs._median(costs),
        cost_total=sum(costs, Decimal(0)),
        swap=fairness.position_swap(transcript_map),
        absent=swap_absent(run, transcript_map),
        calibration=calibration,
        outcomes=outcomes,
        below_escalations=sum(
            1
            for outcome in outcomes
            if outcome.confidence < V8_FLOOR and outcome.ruling == fairness.ESCALATE
        ),
        lean=fairness.error_lean(report),
    )


def measurements() -> Tuple[Measurements, ...]:
    """Both version-8 sets' measurements, in the order the report prints them."""
    return tuple(measure(name) for name in V8_SET_NAMES)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _rate(k: int, n: int) -> str:
    """``33/34 = 97.1%`` -- a count with its share, the fairness module's form."""
    return "{0}/{1} = {2}".format(k, n, grade.render_percent(grade._percent(k, n)))


def _seconds(value: Optional[Decimal]) -> str:
    return v6_runs._seconds(value)


def _cases_text(cases: Sequence[int]) -> str:
    return fairness._named(cases)


def _absent_lines(absent: Sequence[Tuple[int, str]]) -> List[str]:
    """The cases the swap cannot hold, one line per reason."""
    if not absent:
        return ["     every case of this set has a valid swapped draft and a valid sampled one"]
    lines: List[str] = []
    for reason in (NO_JUDGE_ASKED, NO_VALID_SWAPPED, NO_VALID_SAMPLED):
        named = [case_no for case_no, why in absent if why == reason]
        if named:
            lines.append(
                "     does not qualify: {0} ({1})".format(_cases_text(named), reason)
            )
    return lines


def _calibration_lines(measured: Measurements) -> List[str]:
    """The bins, the error and the split at the version-8 bar."""
    calibration = measured.calibration
    lines = [
        "   calibration                     {0} valid judge drafts".format(
            calibration.total
        ),
        "     {0:<14}{1:>6}{2:>12}{3:>16}{4:>20}".format(
            "bin", "count", "mean conf", "share correct", "Wilson 95%"
        ),
    ]
    for bin_ in calibration.bins:
        lines.append(
            "     {0:<14}{1:>6}{2:>12}{3:>16}{4:>20}".format(
                "[{0:.1f}, {1:.1f})".format(bin_.low, bin_.high),
                bin_.count,
                "-"
                if bin_.mean_confidence is None
                else "{0:.3f}".format(bin_.mean_confidence),
                "-"
                if bin_.share_correct is None
                else grade.render_percent(grade._percent(bin_.correct, bin_.count)),
                v6_runs.wilson_text(bin_.correct, bin_.count),
            )
        )
    below_correct, below_total = calibration.below_floor
    at_correct, at_total = calibration.at_or_above_floor
    lines.append(
        "     expected calibration error    {0}".format(
            fairness.render_ece(calibration.ece)
        )
    )
    lines.append(
        "     below the {0} bar             {1}".format(
            _floor_text(), _rate(below_correct, below_total)
        )
    )
    lines.append(
        "     at or above it                {0}".format(_rate(at_correct, at_total))
    )
    lines.append(
        "     drafts proposing ESCALATE below the {0} bar   {1} of {2}".format(
            _floor_text(), measured.below_escalations, below_total
        )
    )
    return lines


def _floor_text() -> str:
    """The version-8 bar, as the policy states it, to two decimals."""
    return "{0:.2f}".format(V8_FLOOR)


def set_lines(measured: Measurements) -> List[str]:
    """One set's whole section, as the report prints it."""
    lines: List[str] = [
        "== {0} ==".format(measured.name),
        "   run  {0}".format(v6_runs._relative(measured.run_dir)),
    ]
    if measured.key_path is not None:
        lines.append("   key  {0}".format(v6_runs._relative(measured.key_path)))
    lines.append(
        "   {0} case(s)".format(measured.cases)
    )
    lines.append(
        "   four-field agreement            {0}   Wilson 95% {1}".format(
            _rate(measured.exact, measured.cases),
            v6_runs.wilson_text(measured.exact, measured.cases),
        )
    )
    lines.append(
        "   escalation   produced {0}   expected {1}   true positives {2}".format(
            measured.escalated_produced,
            measured.escalated_expected,
            measured.true_positives,
        )
    )
    lines.append(
        "     precision  {0}   recall  {1}".format(
            grade.render_ratio(measured.precision),
            grade.render_ratio(measured.recall),
        )
    )
    lines.append(
        "   decided with no person          {0} of {1}".format(
            measured.decided_with_no_person, measured.cases
        )
    )
    lines.append(
        "   wall clock   median {0} s   p90 {1} s".format(
            _seconds(measured.wall_median), _seconds(measured.wall_p90)
        )
    )
    lines.append(
        "   cost         median {0:.4f} USD   total {1:.3f} USD".format(
            measured.cost_median, measured.cost_total
        )
    )
    swap = measured.swap
    lines.append(
        "   position swap                   {0} of {1} agree on all four graded "
        "fields   Wilson 95% {2}".format(
            swap.agree_all_four,
            swap.total,
            v6_runs.wilson_text(swap.agree_all_four, swap.total),
        )
    )
    lines.append(
        "     agrees on the ruling alone    {0} of {1}".format(
            swap.agree_ruling, swap.total
        )
    )
    if swap.disagreements():
        lines.append(
            "     differs on all four           {0}".format(
                _cases_text(swap.disagreements())
            )
        )
    lines.extend(_absent_lines(measured.absent))
    lines.extend(_calibration_lines(measured))
    lines.extend(fairness._error_lean_block("which way the errors lean", measured.lean))
    return lines


# --------------------------------------------------------------------------
# The table, which the note quotes
# --------------------------------------------------------------------------
def _reason_text(reason: str) -> str:
    """A reason as the report states it, the voided draft named as one."""
    return (
        "its swapped draft was voided"
        if reason == NO_VALID_SWAPPED
        else reason
    )


def _swap_cell(measured: Measurements) -> str:
    """``33 of 34 (5009 differs; 5006, ... do not qualify)`` -- value and why.

    A set with a case that differed lists the differing case and then the cases
    that do not qualify, because the two are different findings. A set with
    none -- ``ryde-v8``, whose two cases both fall out -- names each absent case
    with its own reason instead, which is the only place that set's swap says
    anything at all.
    """
    swap = measured.swap
    cell = "{0} of {1}".format(swap.agree_all_four, swap.total)
    detail: List[str] = []
    if swap.disagreements():
        detail.append("{0} differs".format(_cases_text(swap.disagreements())))
    if measured.absent:
        if swap.disagreements():
            detail.append(
                "{0} do not qualify".format(
                    _cases_text([case_no for case_no, _reason in measured.absent])
                )
            )
        else:
            detail.append(
                "; ".join(
                    "{0}: {1}".format(case_no, _reason_text(reason))
                    for case_no, reason in measured.absent
                )
            )
    if detail:
        cell += " ({0})".format("; ".join(detail))
    return cell


def _error_cell(measured: Measurements) -> str:
    differing = measured.lean.differing
    if not differing:
        return "none"
    if len(differing) == 1:
        movement = differing[0]
        return "one: {0}, {1}".format(movement.case_no, movement.direction)
    return "{0}: {1}".format(
        len(differing),
        "; ".join(
            "{0} {1}".format(movement.case_no, movement.direction)
            for movement in differing
        ),
    )


def _below_above_cell(measured: Measurements) -> str:
    below_correct, below_total = measured.calibration.below_floor
    at_correct, at_total = measured.calibration.at_or_above_floor
    return "{0} of {1} (all {2} propose ESCALATE) / {3} of {4}".format(
        below_correct, below_total, measured.below_escalations, at_correct, at_total
    )


def table(found: Sequence[Measurements]) -> List[str]:
    """The two sets side by side, in the rows the note quotes."""
    dev, ryde = found
    rows: Tuple[Tuple[str, str, str], ...] = (
        ("four-field agreement", "{0}/{1}".format(dev.exact, dev.cases), "{0}/{1}".format(ryde.exact, ryde.cases)),
        (
            "escalation produced / expected / true positive",
            "{0} / {1} / {2}".format(dev.escalated_produced, dev.escalated_expected, dev.true_positives),
            "{0} / {1} / {2}".format(ryde.escalated_produced, ryde.escalated_expected, ryde.true_positives),
        ),
        (
            "decided with no person",
            "{0} of {1}".format(dev.decided_with_no_person, dev.cases),
            "{0} of {1}".format(ryde.decided_with_no_person, ryde.cases),
        ),
        (
            "wall median, p90",
            "{0} s, {1} s".format(_seconds(dev.wall_median), _seconds(dev.wall_p90)),
            "{0} s, {1} s".format(_seconds(ryde.wall_median), _seconds(ryde.wall_p90)),
        ),
        (
            "cost median, total",
            "{0:.4f} USD, {1:.3f} USD".format(dev.cost_median, dev.cost_total),
            "{0:.4f} USD, {1:.3f} USD".format(ryde.cost_median, ryde.cost_total),
        ),
        (
            "position swap, all four fields",
            _swap_cell(dev),
            _swap_cell(ryde),
        ),
        (
            "valid drafts, ECE",
            "{0}, {1}".format(dev.calibration.total, fairness.render_ece(dev.calibration.ece)),
            "{0} (too few)".format(ryde.calibration.total),
        ),
        (
            "below 0.80 / at or above 0.80, correct",
            _below_above_cell(dev),
            _below_above_cell(ryde),
        ),
        ("errors", _error_cell(dev), _error_cell(ryde)),
    )
    lines = [
        "| | {0} | {1} |".format(dev.name, ryde.name),
        "|---|---|---|",
    ]
    for label, left, right in rows:
        lines.append("| {0} | {1} | {2} |".format(label, left, right))
    return lines


# --------------------------------------------------------------------------
# The figures ``tools/check_figures.py`` reads
# --------------------------------------------------------------------------
def figures() -> Dict[str, str]:
    """The four version-8 measurements a document states, computed here.

    ``tools/check_figures.py`` reads these rather than recomputing them, so a
    figure it checks is the figure this module measures.
    """
    dev = measure("dev-v8")
    return {
        "dev-v8 decided with no person": "{0} of {1}".format(
            dev.decided_with_no_person, dev.cases
        ),
        "dev-v8 position swap": "{0} of {1}".format(
            dev.swap.agree_all_four, dev.swap.total
        ),
        "dev-v8 ECE": fairness.render_ece(dev.calibration.ece),
        "dev-v8 drafts": str(dev.calibration.total),
    }


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def note_lines(found: Sequence[Measurements]) -> List[str]:
    """The three plain sentences the report ends with, and the reason for each.

    Every count in them is the measurement's own, so a note that outlived a
    re-run would state the new figures rather than the old ones.
    """
    dev, ryde = found
    return [
        "Note.",
        "  dev-v8 is development data the team tuned against, and no figure here is a",
        "  generalisation figure; the version-6 figures (136/141, 0.088, 112 of 151) are",
        "  measurements of the version-6 system on version-6 keys and stay as history.",
        "  The drafts of one case answer the same brief and are not independent draws:",
        "  dev-v8's {0} valid drafts are {1} panels rather than {0} independent "
        "draws.".format(dev.calibration.total, dev.swap.total),
        "  ryde-v8 holds {0} valid judge drafts, which is too few for a calibration".format(
            ryde.calibration.total
        ),
        "  figure to mean anything, and the ECE printed above it is not one.",
        "  The injection, PII and collusion sets were not run at version 8.",
    ]


def report() -> str:
    """The whole measurement, printed. Reads; writes nothing."""
    found = measurements()
    lines: List[str] = [
        "Version 8 measurements -- report",
        "read from the committed version-8 runs under runs/ and the committed "
        "keys; no model call",
        "both sets are development data the team tuned against, and neither is a "
        "generalisation figure",
        "",
    ]
    for measured in found:
        lines.append(
            "{0:<12}{1}".format(
                measured.name, v6_runs._relative(measured.run_dir)
            )
        )
    lines.append("")
    lines.extend(table(found))
    lines.append("")
    for measured in found:
        lines.extend(set_lines(measured))
        lines.append("")
    lines.extend(note_lines(found))
    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.v8_report",
        description=(
            "Measure the position swap, the calibration, the automatic share, "
            "the clock and the cost off the committed version-8 runs. "
            "Read-only; no model call."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print both sets' measurements, computed from the committed runs",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if not arguments.report:
        parser.error("nothing to do: pass --report (this module writes nothing)")
    sys.stdout.write(report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
