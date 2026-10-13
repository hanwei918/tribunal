"""The sealed sets' figures, read off their committed runs. Writes nothing.

Each sealed set is run exactly once and that single run is a generalisation
figure. ``wild-v1``'s figures were computed by hand when its run was written up,
and a figure computed by hand is a figure no test can check. This is the command
that prints them, for both sealed sets, from the artifacts the runs left:

    python3 -m eval.sealed_report --set wild
    python3 -m eval.sealed_report --set wild-v2

It reads three things and writes none: the set's run directory, the set's own
key, and the set's own ``index.json`` for each case's category. No model is
called and no case content is printed -- the output is case numbers, counts and
ratios.

**Which run directory it reads** is decided by :func:`model_for`: a sealed set
that registers the arguments its run is fixed at names the model that run was
made with, and that is the default here, because the run directory is named after
it. ``--model`` overrides it, and a set that registers no arguments -- ``wild-v1``
-- falls back to the runtime model.

**It prints no corpus target beside a sealed set.** ``TARGET_ESCALATION_RATE``
is a property of the 29-case corpus, the set the policy was drafted against. A
sealed set's escalation figures printed beside it would invite a comparison the
set cannot support: the sealed sets are what the policy was *measured* on, and
the corpus target is not a figure they are answerable to.

**It reports only sealed sets.** ``--set`` naming anything else -- the corpus, a
development set -- prints one ``FATAL:`` line to standard error and exits 1
without writing anything. What is wrong there is what the caller typed, so it is
answered with a status rather than with a traceback.

**A set that has not been run prints one line and nothing else.** "Has not been
run" means the run directory holds none of the three things a run leaves -- no
cached case file, no ``events.jsonl`` and no ``run.json``. A run in which every
case failed left the log and the metadata and no result, and it is reported as
what it is: a run with a no-ruling list and not a set that has never been run.
Its key is not read on the not-run path either -- there is nothing to grade with
it -- so this command is safe to run before the sealed run is committed, and
safe on a set whose key is under the sealed-content rule.

**A run that did not finish the set prints its counts and no rate.** When a run
directory holds a log and some of the set's cases were neither ruled on nor
recorded as failed, the run stopped before it reached them. The command then
prints how many cases have a ruling, how many failed and how many were not run,
and no agreement rate and no interval: the few answers a stopped run left are
not the whole set the figure would be about, so a rate over them is not a figure
the set can support. The key is not read on this path either -- the counts come
from the run directory and its own log -- so the command reports a stopped run
without opening an answer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark  # noqa: E402
from tribunal import events, loader  # noqa: E402

# What a set that has no results says, and all it says. The run directory is
# named so a reader knows which directory the command looked in rather than
# being told only that something is absent.
NOT_RUN = "sealed set {0} has not been run: nothing under {1}"


def not_run_line(
    development_set: development_sets.DevelopmentSet,
    model: str,
    runs_dir: Path = run_benchmark.RUNS_DIR,
) -> str:
    """The one line a sealed set with no results prints."""
    return NOT_RUN.format(
        development_set.name,
        _relative(development_set.run_dir(model, runs_dir)),
    )


def _has_a_run(run_dir: Path) -> bool:
    """Whether anything at all was left under this run directory.

    Three artifacts, and any one of them is a run: a cached case file, the
    invocation's event log, and the metadata file. Deciding on the case files
    alone reads a run in which every case failed -- which writes the log and
    ``run.json`` and no result -- as a set that has never been run, and that is
    the opposite of what such a directory records.
    """
    run_dir = Path(run_dir)
    if run_benchmark.cached_case_numbers(run_dir):
        return True
    if (run_dir / events.EVENTS_FILE).exists():
        return True
    return (run_dir / run_benchmark.METADATA_FILE).exists()


# What a run that did not finish the set prints instead of an agreement rate. A
# stopped run's few answers are not the whole set, so a rate over them would be a
# figure the set cannot support: the counts are printed and no rate is.
STOPPED_COUNTS = "Stopped: {0} of {1} with a ruling, {2} failed, {3} not run."
STOPPED_REASON = (
    "No agreement rate and no interval are reported: this run was stopped before "
    "it finished the set."
)


def _failed_cases(path: Path) -> Set[int]:
    """Every case number the log records a failure for.

    A case may have been attempted more than once and may carry more than one
    failure; what a reader wants is which cases the run left with no ruling and a
    recorded reason, so the set is what is returned and not the count.
    """
    failed: Set[int] = set()
    for event in events.read_events(path):
        if event.get("event") != events.EVENT_CASE_FAILED:
            continue
        case_no = event.get("case")
        if isinstance(case_no, int):
            failed.add(case_no)
    return failed


def _stopped_counts(
    development_set: development_sets.DevelopmentSet, run_dir: Path
) -> Optional[Tuple[int, int, int, int]]:
    """The counts of a run that did not finish the set, or ``None``.

    A run of a sealed set is asked for every case in the set. A case that left a
    ruling, or that the run's own log records as failed, was reached; a case with
    neither was never attempted, because the run stopped before it got there.
    When there is at least one such case the run did not finish the set, and the
    four counts are returned -- with a ruling, in the set, failed, not run.

    ``None`` when every case was reached, which is a run reported in full, and
    ``None`` when the run directory holds no log: without one there is no record
    of what was attempted, and the run is reported the way it always was.
    """
    log = Path(run_dir) / events.EVENTS_FILE
    if not log.exists():
        return None
    requested = list(development_set.cases)
    ruled = {
        case_no
        for case_no in run_benchmark.cached_case_numbers(run_dir)
        if run_benchmark.load_cached(run_dir, case_no) is not None
    }
    failed = _failed_cases(log)
    wanted = set(requested)
    not_run = [
        case_no
        for case_no in requested
        if case_no not in ruled and case_no not in failed
    ]
    if not not_run:
        return None
    return (len(ruled & wanted), len(requested), len(failed & wanted), len(not_run))


def _stopped_report(
    development_set: development_sets.DevelopmentSet,
    model: str,
    run_dir: Path,
    counts: Tuple[int, int, int, int],
) -> str:
    """The whole of what a stopped run prints: the counts, and no rate."""
    ruled, requested, failed, not_run = counts
    return "\n".join(
        [
            "Sealed set {0} — {1}".format(development_set.name, model),
            "Run: {0}".format(_relative(run_dir)),
            "",
            STOPPED_COUNTS.format(ruled, requested, failed, not_run),
            STOPPED_REASON,
            "",
        ]
    )


def _relative(path: Path) -> str:
    """A path as it reads from the project root, where that is shorter."""
    resolved = Path(path)
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _produced(run_dir: Path, key: Mapping[int, grade.Ruling]) -> Dict[int, Any]:
    """Every cached ruling in the run directory, by case number.

    A cache entry with no ruling is not a result, which is
    :func:`run_benchmark.load_cached`'s own reading and is kept here: a case
    that produced nothing is a case with no ruling, and counting it as one would
    be inventing the figure this command exists to report.
    """
    produced: Dict[int, Any] = {}
    for case_no in run_benchmark.cached_case_numbers(run_dir):
        if case_no not in key:
            continue
        document = run_benchmark.load_cached(run_dir, case_no)
        if document is None:
            continue
        produced[case_no] = document.get("ruling")
    return produced


def _categories(development_set: development_sets.DevelopmentSet) -> Dict[int, str]:
    """Each case's category, from the set's own ``index.json``.

    The set's index is where a case's category is recorded, and it is the same
    file the loader reads to find the case. Taking it from anywhere else -- the
    case file's own ``dispute.category``, or the key -- would be a second source
    for one fact.
    """
    if development_set.case_root is None:
        return {}
    return {
        int(entry["case_no"]): str(entry.get("category"))
        for entry in loader.load_external_index(development_set.case_root)
    }


def _tally(correct: int, total: int) -> str:
    """A count as ``n/of``, or ``n/a`` where there is nothing to divide by."""
    return "{0}/{1}".format(correct, total) if total else "n/a"


def _ratio(true_positives: int, predicted: int, actual: int) -> Tuple[str, str]:
    """Precision and recall as counts, not as decimals.

    Counts because a rate hides how few cases it is over: 3/7 and 3/4 say both
    what happened and how little of it there was, and a sealed set is 64 cases
    or 20.
    """
    return _tally(true_positives, predicted), _tally(true_positives, actual)


def _exact_among(
    report: grade.GradeReport, cases: Sequence[int]
) -> Tuple[int, int]:
    """Four-field exact over a subset of the graded cases."""
    wanted = set(cases)
    scored = [score for score in report.cases if score.case_no in wanted]
    return sum(1 for score in scored if score.exact), len(scored)


def _ruling_among(
    report: grade.GradeReport, cases: Sequence[int]
) -> Tuple[int, int]:
    """The ruling field alone over a subset of the graded cases."""
    wanted = set(cases)
    scored = [score for score in report.cases if score.case_no in wanted]
    return sum(1 for score in scored if score.correct_on("ruling")), len(scored)


def _last_failure_kind(path: Path, case_no: int) -> Optional[str]:
    """The failure kind of one case's last ``case_failed`` event.

    The last one, because a case may have been attempted more than once and what
    a reader wants to know is why it has no ruling now. ``None`` when the log
    records no failure for it, which is a different finding from a failure with
    no kind and is printed as one.
    """
    kind: Optional[str] = None
    for event in events.read_events(path):
        if event.get("case") != case_no:
            continue
        if event.get("event") != events.EVENT_CASE_FAILED:
            continue
        recorded = event.get("failure_kind")
        kind = recorded if isinstance(recorded, str) else None
    return kind


def render(
    development_set: development_sets.DevelopmentSet,
    model: str,
    runs_dir: Path = run_benchmark.RUNS_DIR,
) -> str:
    """Every figure the sealed run reports, as text. Reads only.

    The two bases are printed everywhere and neither is offered as the one to
    quote. Over the cases that produced a ruling is what the system did where it
    answered; over every case in the set, with a case that produced no ruling
    counted as a miss, is what it did on the set. The second is the honest one
    to report, and printing both is what keeps a reader from having to choose
    between them without knowing it.
    """
    run_dir = development_set.run_dir(model, runs_dir)
    # Decided before the key is loaded, so a set that has not been run costs
    # nothing and, for a sealed set under the sealed-content rule, reads nothing
    # it is not allowed to read.
    if not _has_a_run(run_dir):
        return not_run_line(development_set, model, runs_dir) + "\n"

    # Decided before the key is loaded, for the same reason the not-run check is:
    # a stopped run is reported from its own counts, so the sealed key is not
    # opened to say what it did not finish.
    stopped = _stopped_counts(development_set, run_dir)
    if stopped is not None:
        return _stopped_report(development_set, model, run_dir, stopped)

    key = development_set.key()
    produced = _produced(run_dir, key)
    over_produced = grade.grade(
        produced, {case_no: key[case_no] for case_no in produced}, corpus=key
    )
    over_all = grade.grade(produced, key, corpus=key)
    categories = _categories(development_set)

    lines: List[str] = []
    lines.append("Sealed set {0} — {1}".format(development_set.name, model))
    lines.append("Run: {0}".format(_relative(run_dir)))
    lines.append("")

    lines.append("Four-field exact")
    lines.append(
        "  over the {0} cases that produced a ruling: {1}".format(
            over_produced.total,
            _tally(over_produced.exact_matches, over_produced.total),
        )
    )
    lines.append(
        "  over the {0} cases in the set, a case with no ruling as a miss: {1}".format(
            over_all.total, _tally(over_all.exact_matches, over_all.total)
        )
    )
    lines.append("")

    lines.append("Ruling alone")
    for label, report in (
        ("over the {0} cases that produced a ruling".format(over_produced.total), over_produced),
        ("over the {0} cases in the set".format(over_all.total), over_all),
    ):
        correct, total = _ruling_among(report, report.graded_cases)
        lines.append("  {0}: {1}".format(label, _tally(correct, total)))
    lines.append("")

    lines.append("Per category, from the set's own index.json")
    for category in sorted({name for name in categories.values()}):
        in_set = sorted(
            case_no for case_no, name in categories.items() if name == category
        )
        has_ruling = [case_no for case_no in in_set if case_no in produced]
        exact_produced = _exact_among(over_produced, has_ruling)
        exact_all = _exact_among(over_all, in_set)
        ruling_produced = _ruling_among(over_produced, has_ruling)
        ruling_all = _ruling_among(over_all, in_set)
        lines.append(
            "  {0}: {1} in the set, {2} produced; "
            "four-field {3} over produced and {4} over all; "
            "ruling {5} over produced and {6} over all".format(
                category,
                len(in_set),
                len(has_ruling),
                _tally(*exact_produced),
                _tally(*exact_all),
                _tally(*ruling_produced),
                _tally(*ruling_all),
            )
        )
    lines.append("")

    lines.append("Escalation")
    for label, report in (
        ("over the {0} cases that produced a ruling".format(over_produced.total), over_produced),
        ("over the {0} cases in the set".format(over_all.total), over_all),
    ):
        calibration = report.calibration
        true_positives = len(calibration.true_positives)
        precision, recall = _ratio(
            true_positives,
            true_positives + len(calibration.false_positives),
            true_positives + len(calibration.false_negatives),
        )
        lines.append(
            "  {0}: {1} produced, {2} expected, {3} true positives; "
            "precision {4}, recall {5}".format(
                label,
                len(calibration.produced_escalations),
                len(calibration.expected_escalations),
                true_positives,
                precision,
                recall,
            )
        )
    lines.append("")

    no_ruling = sorted(set(key) - set(produced))
    log = Path(run_dir) / events.EVENTS_FILE
    lines.append("No ruling ({0})".format(len(no_ruling)))
    for case_no in no_ruling:
        kind = _last_failure_kind(log, case_no)
        lines.append(
            "  {0}: last failure kind {1}".format(
                case_no, "not recorded" if kind is None else kind
            )
        )

    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.sealed_report",
        description=(
            "Print a sealed set's figures from its committed run. Reads only: "
            "no model is called and nothing is written. A set that has not been "
            "run prints one line and nothing else, so this is safe to run "
            "before the sealed run is committed."
        ),
    )
    parser.add_argument(
        "--set",
        dest="set_name",
        required=True,
        help="which sealed set: {0}".format(
            ", ".join(sorted(sealed.name for sealed in development_sets.SEALED_SETS))
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "the model id; defaults to the model the set registers, or to "
            "tribunal/model.py for a set that registers none"
        ),
    )
    parser.add_argument("--runs-dir", type=Path, default=run_benchmark.RUNS_DIR)
    return parser


def model_for(
    development_set: development_sets.DevelopmentSet, requested: Optional[str]
) -> str:
    """The model to report on: the one asked for, else the set's own.

    A sealed set that registers the arguments its run is fixed at names the model
    its single run was made with, and its run directory is named after that model.
    Reading the runtime default instead would look in a directory named after a
    model the set never ran, which is how a sealed report would print "has not
    been run" for a set that has been. An explicit ``--model`` still wins, so the
    command can be pointed at another model's directory deliberately.
    """
    chosen = (requested or "").strip()
    if not chosen and development_set.run_arguments is not None:
        chosen = development_set.run_arguments.model
    return run_benchmark.resolve_model(chosen)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    sealed_names = {sealed.name for sealed in development_sets.SEALED_SETS}
    if args.set_name not in sealed_names:
        # Printed and returned rather than raised: what is wrong here is what the
        # caller typed, and the command's contract is a status. A traceback is
        # not an answer to a bad argument.
        print(
            "FATAL: {0!r} is not a sealed set; the sealed sets are {1}".format(
                args.set_name, ", ".join(sorted(sealed_names))
            ),
            file=sys.stderr,
        )
        return 1
    development_set = development_sets.named(args.set_name)
    model = model_for(development_set, args.model)
    sys.stdout.write(render(development_set, model, args.runs_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
