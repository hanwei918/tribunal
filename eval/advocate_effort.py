"""What turning the advocates' reasoning off changes, read from two runs.

The two advocates are the slowest part of a case. Over the 171 version-6 cases
with four drafts, the slower advocate call has median 91 s and 90th percentile
140 s, against the whole case's 160 s and 290 s -- so if the rulings survive it,
``--advocate-effort none`` is where the time is. The switch makes the two
advocate requests carry ``"reasoning_effort": "none"`` and leaves the judge's
drafts and the verifier untouched; a run made with it goes to a root of its own,
``runs/advocate-effort-none/<set>/[policy-v<N>/]<model>/``.

This module answers the question the owner's paid run will raise: **what did the
switch change, and what did it save**. It reads two run directories of one set --
the committed version-6 run as the baseline and the switched run as the candidate
-- and prints, for the cases both runs have:

* the four-field exact figure against the key for each run, with Wilson 95%
  intervals, and each of the four fields separately;
* the cases whose ruling changed, with both sides' four graded fields and the
  direction the change went in;
* the claims each advocate produced and the claims the referee discarded, per
  run;
* the advocate stage's time (the slower of the two calls), the judge stage's and
  the whole case's wall clock, as a median and a 90th percentile, per run; and
* the tokens and the cost per case at the owner's prices, per run.

**Both runs are read, and nothing is written.** The module makes no model call
and launches no browser, and it opens no file outside the two run directories it
was given and the answer key belonging to the set they are of.

The key is the **baseline's** set's key, resolved from where the baseline sits
under ``runs/``; ``--key`` names one explicitly, which is what a run directory
outside ``runs/`` -- a synthetic one, or a scratch root -- needs.

Run from the project root with::

    python3 -m eval.advocate_effort --report \\
        --baseline runs/policy-v6/deepseek-deepseek-flash \\
        --candidate runs/advocate-effort-none/policy-v6/deepseek-deepseek-flash
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from eval import development_sets, early_majority, fairness, grade, v6_runs
from tribunal import referee, transcript as transcript_module

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The owner's prices, read from the module that already states them rather than
# repeated here, so the two cannot drift apart. USD per million tokens, off-peak;
# a cached prompt token is a cheaper input token and is not added a second time.
PRICE_INPUT = v6_runs.PRICE_INPUT
PRICE_CACHED_INPUT = v6_runs.PRICE_CACHED_INPUT
PRICE_OUTPUT = v6_runs.PRICE_OUTPUT
MILLION = v6_runs.MILLION

# The two advocate roles, as the transcript records them. The advocate stage's
# own time is the slower of the two, because the two are asked together.
ADVOCATE_ROLES: Tuple[str, ...] = (
    transcript_module.ROLE_RIDER_ADVOCATE,
    transcript_module.ROLE_DRIVER_ADVOCATE,
)

# What a case's four-field verdict did between the two runs. ``UNCHANGED`` is the
# four graded fields agreeing between the runs; the other three are read off the
# two verdicts against the key, which is the only thing "improved" can mean here.
UNCHANGED = "unchanged"
IMPROVED = "improved"
REGRESSED = "regressed"
MOVED = "moved"

DIRECTIONS: Tuple[str, ...] = (UNCHANGED, IMPROVED, REGRESSED, MOVED)

# The direction a *case* moved, as the report counts them. ``MOVED`` covers a
# case that was a miss on both runs and whose four fields nevertheless changed,
# which is a change a reader has to be able to see even though neither verdict
# was ever right.
BASELINE_LABEL = "baseline"
CANDIDATE_LABEL = "candidate"


class AdvocateEffortError(Exception):
    """The comparison could not be made."""


# --------------------------------------------------------------------------
# Reading one run
# --------------------------------------------------------------------------
def case_numbers(run_dir: Path) -> Tuple[int, ...]:
    """Every case a run directory holds, by number.

    Read off the directory rather than off a set's index: what this module
    compares is what the two runs wrote.
    """
    return tuple(sorted(v6_runs.case_files(Path(run_dir))))


def document_of(run_dir: Path, case_no: int) -> Optional[Mapping[str, Any]]:
    """One case's file, or ``None`` when the run does not hold that case."""
    path = v6_runs.case_path(Path(run_dir), case_no)
    if not path.is_file():
        return None
    return v6_runs.read_json(path)


def transcript_of(
    run_dir: Path, case_no: int, document: Mapping[str, Any]
) -> Mapping[str, Any]:
    """One case's transcript, by the name the case's own file records."""
    path = fairness.transcript_path(Path(run_dir), document, case_no)
    return v6_runs.read_json(path)


def set_name_for_run_directory(
    run_dir: Path, runs_root: Path = v6_runs.RUNS_DIR
) -> str:
    """Which registered set a run directory belongs to.

    A development set's runs live one component below the runs root and name it;
    the corpus's live at the root itself, so anything that is not under a set's
    own subdirectory is the corpus. The longest match wins, so ``dev-v2-ext`` is
    not read as ``dev-v2``.
    """
    resolved = Path(run_dir).resolve()
    root = Path(runs_root).resolve()
    best = ""
    for name in sorted(development_sets.BY_NAME):
        development_set = development_sets.BY_NAME[name]
        if development_set.runs_subdir is None:
            continue
        candidate = (root / development_set.runs_subdir).resolve()
        if resolved == candidate or resolved.is_relative_to(candidate):
            if len(development_set.runs_subdir) > len(best):
                best = development_set.runs_subdir
    return best if best else development_sets.CORPUS.name


def key_path_for_run_directory(
    run_dir: Path, runs_root: Path = v6_runs.RUNS_DIR
) -> Path:
    """The answer key belonging to the set a run directory is of."""
    name = set_name_for_run_directory(run_dir, runs_root)
    development_set = development_sets.BY_NAME.get(name)
    if development_set is None:
        return development_sets.CORPUS.key_path
    return development_set.key_path


def load_key(
    run_dir: Path,
    key: Optional[Any] = None,
    runs_root: Path = v6_runs.RUNS_DIR,
) -> Tuple[Dict[int, grade.Ruling], Path]:
    """The key the two runs are graded against, and where it came from.

    ``key`` names one explicitly -- a path, or a mapping of case number to
    :class:`eval.grade.Ruling` for a caller that already holds one -- and
    otherwise the key is the one belonging to the set the run directory is of,
    which is what makes ``--baseline runs/policy-v6/<slug>`` grade against the
    corpus key and ``--baseline runs/codex/<slug>`` against the second set's.
    """
    if isinstance(key, Mapping):
        if not key:
            raise AdvocateEffortError("the key given carries no cases")
        return dict(key), Path("<given>")
    path = key_path_for_run_directory(run_dir, runs_root) if key is None else Path(key)
    if not path.is_file():
        raise AdvocateEffortError(
            "no answer key at {0}; name one with --key".format(path)
        )
    return grade.load_answer_key(path), path


def claims_of(document: Mapping[str, Any]) -> Tuple[Dict[str, int], int]:
    """The claims each advocate produced, and the claims the referee discarded.

    Read off the case's own ``referee`` block, which is the code-assembled ledger
    of every claim the two advocates filed: one entry per claim, tagged with the
    side that filed it and with whether the referee kept it. A case no agent was
    asked -- one the scope gate or the record-integrity gate escalated -- carries
    an empty ledger, and zero is the right answer for it.
    """
    block = document.get("referee")
    ledger = block.get("ledger") if isinstance(block, Mapping) else None
    counts: Dict[str, int] = {referee.SIDE_RIDER: 0, referee.SIDE_DRIVER: 0}
    discarded = 0
    for entry in ledger or []:
        if not isinstance(entry, Mapping):
            continue
        side = entry.get("side")
        if side in counts:
            counts[side] += 1
        if entry.get("status") == referee.STATUS_DISCARDED:
            discarded += 1
    return counts, discarded


def advocate_seconds(transcript: Mapping[str, Any]) -> Decimal:
    """The advocate stage's time: the slower of the two calls.

    The two are asked together, so the stage costs the slower one. Reused from
    :mod:`eval.early_majority`, which reads the same field off the same record,
    so the two measurements cannot come to read it differently.
    """
    return early_majority.advocate_stage(transcript)


def judge_seconds(transcript: Mapping[str, Any]) -> Decimal:
    """The judge stage's time: the slowest draft the panel waited for.

    A panel of four is four calls, and the stage costs the slowest of them. A
    case with no panel at all -- a single-draft run, or a case no agent was asked
    -- is zero.
    """
    drafts = early_majority.drafts_of(transcript)
    return max((draft.seconds for draft in drafts), default=Decimal(0))


def tokens_of(document: Mapping[str, Any]) -> Dict[str, int]:
    """The four token figures one case file records, as integers."""
    block = document.get("tokens")
    block = block if isinstance(block, Mapping) else {}

    def count(name: str) -> int:
        value = block.get(name)
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0

    return {
        "prompt_tokens": count("prompt_tokens"),
        "completion_tokens": count("completion_tokens"),
        "reasoning_tokens": count("reasoning_tokens"),
        "cached_tokens": count("cached_tokens"),
    }


def cost_of(tokens: Mapping[str, int]) -> Decimal:
    """One case's cost at the owner's prices, in USD.

    Prompt tokens are split into the cached and uncached parts, because a cached
    prompt token is priced at a twentieth of an uncached one, and the two are
    added once each.
    """
    prompt = int(tokens.get("prompt_tokens") or 0)
    cached = int(tokens.get("cached_tokens") or 0)
    completion = int(tokens.get("completion_tokens") or 0)
    return (
        Decimal(prompt - cached) * PRICE_INPUT
        + Decimal(cached) * PRICE_CACHED_INPUT
        + Decimal(completion) * PRICE_OUTPUT
    ) / MILLION


def wall_seconds_of(document: Mapping[str, Any]) -> Decimal:
    """One case's whole wall clock, as the run recorded it."""
    value = document.get("wall_seconds")
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


# --------------------------------------------------------------------------
# The comparison
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CaseSide:
    """One run's reading of one case: what it ruled, cost and how long it took."""

    ruling: Any
    ruling_word: Any
    tokens: Dict[str, int]
    cost: Decimal
    wall_seconds: Decimal
    advocate_seconds: Decimal
    judge_seconds: Decimal
    rider_claims: int
    driver_claims: int
    discarded: int


@dataclass(frozen=True)
class ComparedCase:
    """One case, as both runs read it, and what the switch did to it."""

    case_no: int
    baseline: CaseSide
    candidate: CaseSide
    baseline_exact: bool
    candidate_exact: bool

    @property
    def four_fields_changed(self) -> bool:
        """Whether the four graded fields differ between the two runs."""
        return (
            self.baseline.ruling_word,
            self.baseline.ruling,
        ) != (
            self.candidate.ruling_word,
            self.candidate.ruling,
        )

    @property
    def direction(self) -> str:
        """Which way the case went, as the report counts it."""
        if not self.four_fields_changed:
            return UNCHANGED
        if self.candidate_exact and not self.baseline_exact:
            return IMPROVED
        if self.baseline_exact and not self.candidate_exact:
            return REGRESSED
        return MOVED


@dataclass(frozen=True)
class RunSide:
    """One run's own figures over the cases the two runs have in common."""

    label: str
    run_dir: Path
    cases: Tuple[int, ...]
    report: grade.GradeReport
    sides: Mapping[int, CaseSide]

    @property
    def exact(self) -> int:
        return self.report.exact_matches

    @property
    def total(self) -> int:
        return self.report.total


@dataclass(frozen=True)
class Comparison:
    """Both runs, the cases they share, and the key they are graded against."""

    set_name: str
    key_path: Path
    baseline: RunSide
    candidate: RunSide
    cases: Tuple[ComparedCase, ...]
    baseline_only: Tuple[int, ...]
    candidate_only: Tuple[int, ...]


def _side(run_dir: Path, case_no: int, document: Mapping[str, Any]) -> CaseSide:
    """One run's reading of one case, off the case file and its transcript."""
    transcript = transcript_of(run_dir, case_no, document)
    counts, discarded = claims_of(document)
    tokens = tokens_of(document)
    ruling = grade.produced_from_mapping(document.get("ruling"), case_no)
    return CaseSide(
        ruling=ruling,
        ruling_word=ruling.ruling,
        tokens=tokens,
        cost=cost_of(tokens),
        wall_seconds=wall_seconds_of(document),
        advocate_seconds=advocate_seconds(transcript),
        judge_seconds=judge_seconds(transcript),
        rider_claims=counts[referee.SIDE_RIDER],
        driver_claims=counts[referee.SIDE_DRIVER],
        discarded=discarded,
    )


def compare(
    baseline: Path,
    candidate: Path,
    *,
    key: Optional[Any] = None,
    runs_root: Path = v6_runs.RUNS_DIR,
) -> Comparison:
    """Read two runs of one set and compare them over the cases both have."""
    baseline = Path(baseline)
    candidate = Path(candidate)
    for label, run_dir in ((BASELINE_LABEL, baseline), (CANDIDATE_LABEL, candidate)):
        if not run_dir.is_dir():
            raise AdvocateEffortError(
                "the {0} run directory {1} is not there".format(label, run_dir)
            )

    resolved_key, key_path = load_key(baseline, key, runs_root)

    baseline_cases = case_numbers(baseline)
    candidate_cases = case_numbers(candidate)
    shared = tuple(sorted(set(baseline_cases) & set(candidate_cases)))
    if not shared:
        raise AdvocateEffortError(
            "the two runs have no case in common: {0} holds {1} and {2} holds {3}".format(
                baseline, len(baseline_cases), candidate, len(candidate_cases)
            )
        )

    subset = {case_no: resolved_key[case_no] for case_no in shared if case_no in resolved_key}
    if not subset:
        raise AdvocateEffortError(
            "the key {0} carries none of the {1} cases the two runs share".format(
                key_path, len(shared)
            )
        )

    documents: Dict[str, Dict[int, Mapping[str, Any]]] = {
        BASELINE_LABEL: {},
        CANDIDATE_LABEL: {},
    }
    sides: Dict[str, Dict[int, CaseSide]] = {BASELINE_LABEL: {}, CANDIDATE_LABEL: {}}
    for label, run_dir in ((BASELINE_LABEL, baseline), (CANDIDATE_LABEL, candidate)):
        for case_no in shared:
            document = document_of(run_dir, case_no)
            if document is None:
                continue
            documents[label][case_no] = document
            sides[label][case_no] = _side(run_dir, case_no, document)

    graded = tuple(case_no for case_no in shared if case_no in subset)
    reports: Dict[str, grade.GradeReport] = {}
    for label in (BASELINE_LABEL, CANDIDATE_LABEL):
        produced = {
            case_no: documents[label][case_no].get("ruling") for case_no in graded
        }
        part = {case_no: subset[case_no] for case_no in graded}
        reports[label] = grade.grade(produced, part, corpus=part)

    exacts: Dict[str, Dict[int, bool]] = {BASELINE_LABEL: {}, CANDIDATE_LABEL: {}}
    for label in (BASELINE_LABEL, CANDIDATE_LABEL):
        for score in reports[label].cases:
            exacts[label][score.case_no] = score.exact

    compared = tuple(
        ComparedCase(
            case_no=case_no,
            baseline=sides[BASELINE_LABEL][case_no],
            candidate=sides[CANDIDATE_LABEL][case_no],
            baseline_exact=exacts[BASELINE_LABEL][case_no],
            candidate_exact=exacts[CANDIDATE_LABEL][case_no],
        )
        for case_no in graded
    )

    baseline_side = RunSide(
        label=BASELINE_LABEL,
        run_dir=baseline,
        cases=graded,
        report=reports[BASELINE_LABEL],
        sides=sides[BASELINE_LABEL],
    )
    candidate_side = RunSide(
        label=CANDIDATE_LABEL,
        run_dir=candidate,
        cases=graded,
        report=reports[CANDIDATE_LABEL],
        sides=sides[CANDIDATE_LABEL],
    )
    return Comparison(
        set_name=set_name_for_run_directory(baseline, runs_root),
        key_path=key_path,
        baseline=baseline_side,
        candidate=candidate_side,
        cases=compared,
        baseline_only=tuple(sorted(set(baseline_cases) - set(candidate_cases))),
        candidate_only=tuple(sorted(set(candidate_cases) - set(baseline_cases))),
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _seconds(value: Optional[Decimal]) -> str:
    if value is None:
        return "-"
    return "{0:.1f}".format(value)


def _money(value: Optional[Decimal]) -> str:
    if value is None:
        return "-"
    return "{0:.4f}".format(value)


def _count(value: Optional[Decimal]) -> str:
    if value is None:
        return "-"
    return "{0:.0f}".format(value)


def _relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _four_fields(ruling: Any) -> str:
    """One ruling's four graded fields, as the report prints them."""
    return "ruling {0}  amount {1}  driver {2}  referrals {3}".format(
        ruling.ruling,
        v6_runs._money(ruling.amount_sgd),
        v6_runs._money(ruling.driver_compensation_sgd),
        v6_runs._referrals(ruling.referrals),
    )


def _median_of(values: Sequence[Decimal]) -> Optional[Decimal]:
    return v6_runs._median(values)


def _p90_of(values: Sequence[Decimal]) -> Optional[Decimal]:
    return v6_runs._percentile(values, Decimal("0.9"))


def _time_row(label: str, values: Sequence[Decimal]) -> str:
    return "   {0:<16}median {1:>7}   p90 {2:>7}".format(
        label, _seconds(_median_of(values)), _seconds(_p90_of(values))
    )


def _grade_block(side: RunSide) -> List[str]:
    lines = [
        "   {0:<10}{1}   Wilson 95% {2}".format(
            side.label,
            v6_runs._rate_text(side.exact, side.total),
            v6_runs.wilson_text(side.exact, side.total),
        )
    ]
    for field in grade.GRADED_FIELDS:
        matched, total = side.report.field_tally(field)
        lines.append(
            "     {0:<24}{1}   Wilson 95% {2}".format(
                field,
                v6_runs._rate_text(matched, total),
                v6_runs.wilson_text(matched, total),
            )
        )
    return lines


def _movement_counts(cases: Sequence[ComparedCase]) -> Dict[str, int]:
    counts = {direction: 0 for direction in DIRECTIONS}
    for case in cases:
        counts[case.direction] += 1
    return counts


def _claims_block(side: RunSide, cases: Sequence[ComparedCase]) -> List[str]:
    """Claims per advocate and claims the referee discarded, for one run."""
    pick = (lambda case: case.baseline) if side.label == BASELINE_LABEL else (
        lambda case: case.candidate
    )
    rider = [pick(case).rider_claims for case in cases]
    driver = [pick(case).driver_claims for case in cases]
    discarded = [pick(case).discarded for case in cases]
    return [
        "   {0:<10}rider {1:>4}   driver {2:>4}   referee discarded {3:>4}".format(
            side.label, sum(rider), sum(driver), sum(discarded)
        ),
        "     per case: rider median {0}   driver median {1}   discarded median {2}".format(
            _count(_median_of([Decimal(value) for value in rider])),
            _count(_median_of([Decimal(value) for value in driver])),
            _count(_median_of([Decimal(value) for value in discarded])),
        ),
    ]


def _time_block(side: RunSide, cases: Sequence[ComparedCase]) -> List[str]:
    pick = (lambda case: case.baseline) if side.label == BASELINE_LABEL else (
        lambda case: case.candidate
    )
    return [
        "   {0}".format(side.label),
        _time_row(
            "advocates",
            [pick(case).advocate_seconds for case in cases],
        ),
        _time_row("judge", [pick(case).judge_seconds for case in cases]),
        _time_row("whole case", [pick(case).wall_seconds for case in cases]),
    ]


def _cost_block(side: RunSide, cases: Sequence[ComparedCase]) -> List[str]:
    pick = (lambda case: case.baseline) if side.label == BASELINE_LABEL else (
        lambda case: case.candidate
    )
    prompt = [Decimal(pick(case).tokens["prompt_tokens"]) for case in cases]
    completion = [Decimal(pick(case).tokens["completion_tokens"]) for case in cases]
    reasoning = [Decimal(pick(case).tokens["reasoning_tokens"]) for case in cases]
    costs = [pick(case).cost for case in cases]
    total = sum(costs, Decimal(0))
    return [
        "   {0}".format(side.label),
        "     tokens per case   prompt median {0}   completion median {1}   "
        "reasoning median {2}".format(
            _count(_median_of(prompt)),
            _count(_median_of(completion)),
            _count(_median_of(reasoning)),
        ),
        "     cost per case     median {0} USD   total {1} USD over {2}".format(
            _money(_median_of(costs)),
            _money(total),
            v6_runs._plural(len(cases), "case"),
        ),
    ]


def report(
    baseline: Path,
    candidate: Path,
    *,
    key: Optional[Any] = None,
    runs_root: Path = v6_runs.RUNS_DIR,
) -> str:
    """The whole comparison, printed. Reads two runs; writes nothing."""
    comparison = compare(baseline, candidate, key=key, runs_root=runs_root)
    cases = comparison.cases
    counts = _movement_counts(cases)

    lines: List[str] = [
        "Advocate effort, read from two runs of one set",
        "set        {0}".format(comparison.set_name),
        "baseline   {0}".format(_relative(comparison.baseline.run_dir)),
        "candidate  {0}".format(_relative(comparison.candidate.run_dir)),
        "key        {0}".format(_relative(comparison.key_path)),
        "",
        "cases both runs have: {0}".format(len(cases)),
        "  baseline only: {0}".format(
            v6_runs._named(comparison.baseline_only) if comparison.baseline_only else "none"
        ),
        "  candidate only: {0}".format(
            v6_runs._named(comparison.candidate_only)
            if comparison.candidate_only
            else "none"
        ),
        "",
        "== Four-field exact against the key ==",
    ]
    lines.extend(_grade_block(comparison.baseline))
    lines.extend(_grade_block(comparison.candidate))

    lines.append("")
    lines.append("== The cases whose ruling changed ==")
    moved = [case for case in cases if case.direction != UNCHANGED]
    lines.append(
        "   changed            {0} of {1}   {2}".format(
            len(moved), len(cases), v6_runs._named([case.case_no for case in moved])
        )
    )
    lines.append(
        "   direction          improved {0}   regressed {1}   moved between two "
        "misses {2}   unchanged {3}".format(
            counts[IMPROVED], counts[REGRESSED], counts[MOVED], counts[UNCHANGED]
        )
    )
    for case in moved:
        lines.append(
            "   {0}  {1}".format(case.case_no, case.direction)
        )
        lines.append(
            "     {0:<10}{1}".format(BASELINE_LABEL, _four_fields(case.baseline.ruling))
        )
        lines.append(
            "     {0:<10}{1}".format(
                CANDIDATE_LABEL, _four_fields(case.candidate.ruling)
            )
        )
        lines.append(
            "     four-field verdict {0} -> {1}".format(
                "exact" if case.baseline_exact else "miss",
                "exact" if case.candidate_exact else "miss",
            )
        )

    lines.append("")
    lines.append("== Claims ==")
    lines.extend(_claims_block(comparison.baseline, cases))
    lines.extend(_claims_block(comparison.candidate, cases))

    lines.append("")
    lines.append("== Time, seconds ==")
    lines.extend(_time_block(comparison.baseline, cases))
    lines.extend(_time_block(comparison.candidate, cases))
    saved = [
        case.baseline.wall_seconds - case.candidate.wall_seconds for case in cases
    ]
    lines.append(
        _time_row("saved per case", saved)
        + "   (baseline minus candidate; positive is a saving)"
    )

    lines.append("")
    lines.append("== Tokens and cost, at the owner's prices ==")
    lines.append(
        "   prices (USD per million tokens, off-peak): input {0}, cached input {1}, "
        "output {2}".format(PRICE_INPUT, PRICE_CACHED_INPUT, PRICE_OUTPUT)
    )
    lines.extend(_cost_block(comparison.baseline, cases))
    lines.extend(_cost_block(comparison.candidate, cases))
    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m eval.advocate_effort",
        description=(
            "Compare two runs of one set -- a baseline and an --advocate-effort "
            "none candidate -- over the cases both have. Read-only; no model "
            "call is made and nothing is written."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--report",
        action="store_true",
        help="print the comparison, computed from the two run directories",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        metavar="RUN_DIR",
        help=(
            "the run the candidate is compared against; the committed version-6 "
            "run of the same set. Its key is the set's own, resolved from where "
            "it sits under runs/, unless --key names one"
        ),
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        metavar="RUN_DIR",
        help="the run made with --advocate-effort none",
    )
    parser.add_argument(
        "--key",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "the answer key to grade both runs against, for a run directory "
            "outside runs/ -- a synthetic one, or a scratch root"
        ),
    )
    return parser

def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.report:
        try:
            sys.stdout.write(
                report(
                    arguments.baseline,
                    arguments.candidate,
                    key=arguments.key,
                )
            )
        except AdvocateEffortError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
