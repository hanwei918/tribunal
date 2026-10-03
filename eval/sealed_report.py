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

**A set that has not been run prints one line and nothing else.** Its key is not
read either -- there is nothing to grade with it -- so this command is safe to
run before the sealed run is committed, and safe on a set whose key is under the
sealed-content rule.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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
    if not run_benchmark.cached_case_numbers(run_dir):
        return not_run_line(development_set, model, runs_dir) + "\n"

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
        raise run_benchmark.BenchmarkError(
            "{0!r} is not a sealed set; the sealed sets are {1}".format(
                args.set_name, ", ".join(sorted(sealed_names))
            )
        )
    development_set = development_sets.named(args.set_name)
    model = model_for(development_set, args.model)
    sys.stdout.write(render(development_set, model, args.runs_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
