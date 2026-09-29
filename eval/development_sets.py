"""The development sets the judge prompt is measured on.

There are two of them, and they are not the same kind of thing:

* **the corpus** -- the 29 cases listed in ``data/index.json``, keyed by
  ``eval/answers/ground_truth.json``. This is the set the submission's headline
  figure is computed on, and it stays exactly 29 cases.
* **the second development set** -- fifteen cases drafted by OpenAI Codex on
  2026-09-24, copied in by the owner under ``data/external/codex/``, keyed by
  ``eval/answers/codex/ground_truth.json``. It is deliberately absent from
  ``data/index.json``, because adding it there would change the corpus.

Both are **development data**. Neither is a test set. A test set has to be
drafted without access to this repository and seen beforehand by nobody who
works on the prompt, and the sealed set that meets that description does not
exist yet: it is run exactly once, after the 10 October freeze, and that single
run is the only figure the submission reports as generalisation. Nothing here
produces that figure.

What this module is for
-----------------------
Running either set through the *same* runner the corpus goes through --
:func:`eval.run_benchmark.run_benchmark` -- so the caching, the provenance, both
deadlines, the token budget and the advocate replay are not reimplemented for
the second set and cannot drift from the corpus's. The four graded fields are
compared against each set's own key, and the two sets are reported separately
and then combined.

Nothing here makes a model call. ``--report`` reads cached runs only.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / "runs"
ANSWER_DIR = EVAL_DIR / "answers"
CORPUS_KEY_PATH = ANSWER_DIR / "ground_truth.json"

# Imported after the paths, and only for the runner the sets are run through.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade, run_benchmark  # noqa: E402
from tribunal import loader  # noqa: E402


@dataclass(frozen=True)
class DevelopmentSet:
    """One set of development cases, its key, and where its results live.

    ``runs_subdir`` is the directory the set's runs go under, and it is ``None``
    for the corpus because the corpus's run directory *is*
    ``runs/<model>/``. A second set is never given ``None``: its results must
    not land in a model's corpus run directory, and a distinct subdirectory is
    what makes that checkable rather than merely intended.
    """

    name: str
    cases: Tuple[int, ...]
    key_path: Path
    runs_subdir: Optional[str]
    case_root: Optional[Path]
    summary: str

    def key(self) -> Dict[int, grade.Ruling]:
        """This set's own answer key. Never the corpus key."""
        return grade.load_answer_key(self.key_path)

    def load_case(self, case_no: int) -> Mapping[str, Any]:
        """One of this set's cases, by number.

        The corpus is loaded through the manifest. A second set is loaded
        through its own index, which is what
        :func:`tribunal.loader.load_external_set_case` is for; the manifest
        cannot name a case it does not list.
        """
        if self.case_root is None:
            return loader.load_case(case_no)
        return loader.load_external_set_case(self.case_root, case_no)

    def runs_dir(self, runs_dir: Path = RUNS_DIR) -> Path:
        """Where this set's run directories live, under ``runs_dir``."""
        base = Path(runs_dir)
        return base if self.runs_subdir is None else base / self.runs_subdir

    def run_dir(self, model: str, runs_dir: Path = RUNS_DIR) -> Path:
        """This set's run directory for one model."""
        return run_benchmark.run_directory(self.runs_dir(runs_dir), model)


CORPUS = DevelopmentSet(
    name="corpus",
    cases=tuple(
        entry["case_no"] for entry in loader._read_json(PROJECT_ROOT / "data" / "index.json")
    ),
    key_path=CORPUS_KEY_PATH,
    runs_subdir=None,
    case_root=None,
    summary="the 29-case corpus the submission's headline figure is computed on",
)

SECOND_SET = DevelopmentSet(
    name="codex",
    cases=tuple(
        entry["case_no"]
        for entry in loader.load_external_index(loader.EXTERNAL_DIR / "codex")
    ),
    key_path=ANSWER_DIR / "codex" / "ground_truth.json",
    runs_subdir="codex",
    case_root=loader.EXTERNAL_DIR / "codex",
    summary=(
        "fifteen cases drafted by OpenAI Codex on 2026-09-24, copied in by the "
        "owner; development data, not a test set"
    ),
)

DEVELOPMENT_SETS: Tuple[DevelopmentSet, ...] = (CORPUS, SECOND_SET)
BY_NAME = {development_set.name: development_set for development_set in DEVELOPMENT_SETS}


def named(name: str) -> DevelopmentSet:
    """One set by name. An unknown name raises rather than defaulting."""
    try:
        return BY_NAME[name]
    except KeyError:
        raise run_benchmark.BenchmarkError(
            "unknown development set {0!r}; known sets: {1}".format(
                name, ", ".join(sorted(BY_NAME))
            )
        ) from None


# The development-data caveat, in one place because two reports print it: this
# module's own and the baselines'. It is a paragraph rather than two sentences
# because it has to read correctly wherever it lands, and it names the corpus
# figure as the reported one and denies that either figure is the generalisation
# number. A reader who took a combined or a baseline figure for the submission's
# generalisation figure would be reading a number the submission does not make.
DEVELOPMENT_DATA_CAVEAT = (
    "Both development sets are development data, and neither is a test set. The "
    "corpus figure is the figure the submission reports; the combined figure is "
    "a sum over two sets that were drafted differently and share one template, "
    "so it is not a generalisation figure and does not replace the corpus "
    "number. The only generalisation figure the submission reports belongs to "
    "the sealed set, drafted without access to this repository and run exactly "
    "once after the 10 October freeze. Neither figure here is that figure."
)


def assert_set_run_directory(
    run_dir: Path, development_set: DevelopmentSet, runs_dir: Path = RUNS_DIR
) -> Path:
    """Refuse a set's run directory that is not the set's own.

    ``runs/deepseek-deepseek-flash/`` holds the 29-case corpus result the
    submission reports. A second set's results are not corpus results, and a
    case written there would change what that directory means while leaving
    every file a reader would look at apparently intact. The check is made
    rather than intended, so a caller cannot ask for the headline directory by
    accident and get it.

    The corpus's own set is exempt because ``runs/<model>/`` *is* its
    directory; only a set with a subdirectory of its own is constrained.
    """
    resolved = Path(run_dir).resolve()
    if development_set.runs_subdir is None:
        return resolved
    root = development_set.runs_dir(runs_dir).resolve()
    if not resolved.is_relative_to(root):
        raise run_benchmark.BenchmarkError(
            "development set {0!r} may only be written under {1}, and this one "
            "would go to {2}".format(development_set.name, root, resolved)
        )
    return resolved


def run_set(
    development_set: DevelopmentSet,
    model: str,
    *,
    runs_dir: Path = RUNS_DIR,
    cases: Optional[Sequence[int]] = None,
    **kwargs: Any,
) -> "run_benchmark.RunSummary":
    """Run one development set through the corpus runner.

    Everything the corpus runner does, it does here, because this *is* the
    corpus runner: the cache, the provenance, both deadlines, the token budget
    and the replay check all come from :func:`run_benchmark.run_benchmark` and
    are not reimplemented. Four things are supplied that the corpus run does not
    supply -- the set's cases, its own key, its own loader and its own runs
    directory -- and, for a set with a subdirectory of its own, a label, so the
    metadata names the set. The corpus carries none: ``runs/<model>/`` *is* its
    directory, and the runner refuses a labelled run aimed there.

    The destination is checked before anything is written.
    """
    selected = list(development_set.cases if cases is None else cases)
    unknown = [case_no for case_no in selected if case_no not in set(development_set.cases)]
    if unknown:
        raise run_benchmark.BenchmarkError(
            "case(s) {0} are not in development set {1!r}".format(
                ", ".join(str(case_no) for case_no in unknown), development_set.name
            )
        )

    set_runs_dir = development_set.runs_dir(runs_dir)
    assert_set_run_directory(
        development_set.run_dir(model, runs_dir), development_set, runs_dir
    )
    return run_benchmark.run_benchmark(
        model,
        selected,
        runs_dir=set_runs_dir,
        key=development_set.key(),
        key_path=development_set.key_path,
        case_loader=development_set.load_case,
        # The corpus is run unlabelled, exactly as ``python -m
        # eval.run_benchmark`` runs it, and its case files record
        # ``development_set: null``. Labelling it "corpus" made the set that
        # owns ``runs/<model>/`` the one set that could not run into it: the
        # runner refuses a labelled run whose destination is the corpus
        # directory, and that refusal is right for every other set.
        label=None if development_set.runs_subdir is None else development_set.name,
        **kwargs,
    )


# --------------------------------------------------------------------------
# Reporting the sets separately and combined
# --------------------------------------------------------------------------
def cached_cases(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> List[int]:
    """The set's cases this model has a cached ruling for, in set order."""
    present = set(run_benchmark.cached_case_numbers(development_set.run_dir(model, runs_dir)))
    return [case_no for case_no in development_set.cases if case_no in present]


def _rulings(run_dir: Path, case_nos: Sequence[int]) -> Dict[int, Any]:
    produced: Dict[int, Any] = {}
    for case_no in case_nos:
        document = run_benchmark.load_cached(run_dir, case_no)
        if document is not None:
            produced[case_no] = document.get("ruling")
    return produced


@dataclass(frozen=True)
class SetFigures:
    """One set's numbers, read off disk, graded against that set's own key."""

    name: str
    run_dir: Path
    expected: int
    produced: int
    report: Optional[grade.GradeReport]

    @property
    def exact(self) -> Optional[int]:
        return None if self.report is None else self.report.exact_matches

    @property
    def graded(self) -> int:
        return 0 if self.report is None else self.report.total

    def field(self, name: str) -> Optional[Tuple[int, int]]:
        return None if self.report is None else self.report.field_tally(name)


def figures_for(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> SetFigures:
    """Grade one set over the cases it has produced, against its own key.

    Over the cases the set has actually produced a ruling for, so a set that has
    not been run reports nothing rather than reporting every case as a miss.
    """
    run_dir = development_set.run_dir(model, runs_dir)
    produced_cases = cached_cases(development_set, model, runs_dir)
    if not produced_cases:
        return SetFigures(
            name=development_set.name,
            run_dir=run_dir,
            expected=len(development_set.cases),
            produced=0,
            report=None,
        )
    report = run_benchmark.grade_run(
        run_dir,
        development_set.key(),
        produced_cases,
        # The set's own loader, so each case's brief can be rebuilt for the
        # amount provenance the report prints. Without it every case of this set
        # would report an unavailable brief, because the corpus manifest cannot
        # name a case it does not list.
        case_loader=development_set.load_case,
    )
    return SetFigures(
        name=development_set.name,
        run_dir=run_dir,
        expected=len(development_set.cases),
        produced=len(produced_cases),
        report=report,
    )


def combined_figures(
    model: str,
    runs_dir: Path = RUNS_DIR,
    sets: Sequence[DevelopmentSet] = DEVELOPMENT_SETS,
) -> Tuple[int, Optional[grade.GradeReport]]:
    """Every case of every set, each graded against the key it belongs to.

    One produced mapping and one key, built by merging the sets: a case number
    is in exactly one set's key, so the merge is a union and no case is counted
    twice. Cases no set has produced a ruling for are left out, so a combined
    figure is over what has actually been run.

    ``staleness`` and ``replay`` are deliberately not carried here. Both are
    properties of a *run directory* rather than of a case, and two sets live in
    two directories; folding them into one report would either drop one set's or
    claim a uniformity that does not exist. The per-set reports carry both.
    """
    produced: Dict[int, Any] = {}
    key: Dict[int, grade.Ruling] = {}
    for development_set in sets:
        run_dir = development_set.run_dir(model, runs_dir)
        for case_no in cached_cases(development_set, model, runs_dir):
            document = run_benchmark.load_cached(run_dir, case_no)
            if document is not None:
                produced[case_no] = document.get("ruling")
        key.update(development_set.key())
    if not produced:
        return 0, None
    # Scored over the cases that were produced, so a combined figure is over
    # what has actually been run rather than counting an unrun set's cases as
    # misses. ``corpus`` is the union of both keys, so the report can still say
    # whether the whole of both was covered.
    subset = {case_no: key[case_no] for case_no in produced}
    return len(produced), grade.grade(produced, subset, corpus=key)


def currency_for(
    development_set: DevelopmentSet,
    model: str,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> grade.Staleness:
    """Whether one set's cached results still belong to this code.

    Checked with **this set's own loader**, because a development set handed the
    corpus loader reads ``unknown`` on every one of its cases: the manifest
    cannot name a case it does not list, so no brief is rebuilt and nothing is
    established. The prompt channel is answered from each case's own transcript
    by :class:`run_benchmark.BriefStaleness`, the same checker the runner builds
    for a set it is about to run.
    """
    run_dir = development_set.run_dir(model, runs_dir)
    checker = run_benchmark.BriefStaleness(
        run_benchmark.brief_digest_for(development_set.load_case),
        run_dir=run_dir,
        prompts_dir=prompts_dir,
    )
    return run_benchmark.brief_staleness(
        run_dir, cached_cases(development_set, model, runs_dir), checker
    )


def currency_line(
    development_set: DevelopmentSet, model: str, runs_dir: Path = RUNS_DIR
) -> str:
    """One set's currency, as the four counts the report prints.

    ``current`` is the rest of what the set has produced. The two stale counts
    are the two channels and are never merged, and ``unknown`` is a result this
    code could not answer for -- which is not a result it agrees with.
    """
    produced = len(cached_cases(development_set, model, runs_dir))
    staleness = currency_for(development_set, model, runs_dir)
    current = produced - len(staleness.stale) - len(staleness.unknown)
    return "  {0:<8} current {1:>3}, stale_brief {2:>3}, stale_prompts {3:>3}, unknown {4:>3}".format(
        development_set.name,
        current,
        len(staleness.stale_brief),
        len(staleness.stale_prompts),
        len(staleness.unknown),
    )


def _render_row(figures: SetFigures) -> str:
    if figures.report is None:
        return "  {0:<8} {1:<40} {2:>5}  {3:>9}".format(
            figures.name,
            _relative(figures.run_dir),
            "{0}/{1}".format(0, figures.expected),
            "not run",
        )
    cells = []
    for name in grade.GRADED_FIELDS:
        tally = figures.field(name)
        cells.append("{0}/{1}".format(tally[0], tally[1]) if tally else "-")
    return "  {0:<8} {1:<40} {2:>5}  {3:>9}  {4:>6} {5:>6} {6:>6} {7:>6}".format(
        figures.name,
        _relative(figures.run_dir),
        "{0}/{1}".format(figures.produced, figures.expected),
        "{0}/{1}".format(figures.exact, figures.graded),
        cells[0],
        cells[1],
        cells[2],
        cells[3],
    )


def _relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def _render_case_facts_section(figures: Sequence[SetFigures]) -> List[str]:
    """The per-case cost, provenance and tag table, one per set that has one.

    The same columns a run report prints, filled from the same rows:
    :func:`eval.grade.case_fact_rows` is the one place the values are computed,
    so the two reports cannot come to show different figures under the same
    heading. Every value is code's -- a token split summed off a transcript, a
    wall clock and a vote read off a cache entry, a provenance computed from the
    brief this code builds, and four pattern matches over an explanation.

    A set that has not been run has no report and contributes nothing, which is
    what keeps an unrun set from printing a table of dashes that a reader could
    mistake for a run that produced nothing.
    """
    populated = [
        item
        for item in figures
        if item.report is not None and item.report.facts_checked
    ]
    if not populated:
        return []
    lines = [
        "",
        "Per case — cost, provenance and explanation tags",
        "",
        "Computed by code from each case's own artifacts: the token split summed "
        "off its transcript by role, the wall clock and the vote agreement read "
        "off its cache entry, the amount provenance computed from the brief this "
        "code builds, and the four tags matched over the ruling's explanation by "
        "regular expression and keyword. No model is involved. A dash means the "
        "artifact does not record the figure. `vote agreement` is the share of "
        "the judge's drafts that agreed on the published ruling, and it is not "
        "the judge's own `confidence`. The patterns, and what each is known to "
        "miss and to mistake, are documented in "
        "`docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.",
    ]
    for item in populated:
        lines.append("")
        lines.append("{0} — {1}".format(item.name, _relative(item.run_dir)))
        lines.append("")
        lines.append("| {0} |".format(" | ".join(grade.CASE_FACTS_COLUMNS)))
        lines.append("|{0}|".format("|".join("---" for _ in grade.CASE_FACTS_COLUMNS)))
        for row in grade.case_fact_rows(item.report):
            lines.append("| {0} |".format(" | ".join(row)))
    return lines


def render_development_sets(model: str, runs_dir: Path = RUNS_DIR) -> str:
    """The two sets separately, then combined, then per case. Reads cached runs only.

    The corpus figure and the combined figure are different claims and the text
    says so. The combined figure sums two sets that were drafted differently and
    share one template; it is not a generalisation figure and it does not
    replace the corpus number. The only generalisation figure belongs to the
    sealed set, which is run once after the 10 October freeze.

    The per-case block at the end carries the same cost, provenance and
    explanation columns a run's own ``report.md`` carries, for every case of
    every set that has been run, so a figure in the summary can be traced to the
    case it came from without opening a cache entry.
    """
    lines = [
        "Development sets — {0}".format(model),
        "",
        "Separately, each set graded against its own key:",
        "",
        "  {0:<8} {1:<40} {2:>5}  {3:>9}  {4:>6} {5:>6} {6:>6} {7:>6}".format(
            "set", "run directory", "cases", "exact", "ruling", "amount", "driver", "refs"
        ),
    ]
    figures = [figures_for(development_set, model, runs_dir) for development_set in DEVELOPMENT_SETS]
    for item in figures:
        lines.append(_render_row(item))

    lines.append("")
    lines.append("Currency, each set checked with its own loader and its own briefs:")
    lines.append("")
    for development_set in DEVELOPMENT_SETS:
        lines.append(currency_line(development_set, model, runs_dir))

    total_expected = sum(item.expected for item in figures)
    produced_total, combined = combined_figures(model, runs_dir)
    lines.append("")
    lines.append("Combined, every case graded against the key it belongs to:")
    lines.append("")
    if combined is None:
        lines.append("  no case of any development set has been run for this model")
    else:
        per_set = "; ".join(
            "{0} {1} of {2}".format(item.name, item.produced, item.expected) for item in figures
        )
        lines.append(
            "  produced  {0} of {1} cases  ({2})".format(
                produced_total, total_expected, per_set
            )
        )
        lines.append(
            "  exact     {0}/{1} over the cases produced".format(
                combined.exact_matches, combined.total
            )
        )
    lines.extend(_render_case_facts_section(figures))
    lines.append("")
    lines.append(DEVELOPMENT_DATA_CAVEAT)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.development_sets",
        description=(
            "Run a development set through the corpus runner, or report the sets "
            "from their cached runs. The second development set is the fifteen "
            "cases under data/external/codex/, keyed separately from the corpus."
        ),
    )
    parser.add_argument("--model", default=None, help="the model id; defaults to tribunal/model.py")
    parser.add_argument(
        "--set",
        dest="set_name",
        default="all",
        help="which development set: {0}, or all".format(", ".join(sorted(BY_NAME))),
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="comma-separated case numbers within the set; default is the whole set",
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--prompts-dir", type=Path, default=run_benchmark.PROMPTS_DIR)
    parser.add_argument("--force", action="store_true", help="re-run cases that are already cached")
    parser.add_argument("--token-budget", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=run_benchmark.DEFAULT_CONCURRENCY)
    parser.add_argument("--timeout", type=float, default=run_benchmark.llm.DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--case-deadline",
        type=float,
        default=run_benchmark.pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
    )
    parser.add_argument(
        "--judge-votes",
        type=int,
        default=run_benchmark.pipeline.DEFAULT_JUDGE_VOTES,
        metavar="K",
        help=(
            "how many times to ask each case's judge on the same inputs; the "
            "majority decides, and 1 is the single-draft behaviour"
        ),
    )
    parser.add_argument(
        "--replay-advocates",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help="reuse the advocates recorded in RUN_DIR and call only the judge",
    )
    parser.add_argument(
        "--replay-check",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help="report whether --replay-advocates RUN_DIR would accept each case; reads only",
    )
    parser.add_argument(
        "--verify-drafts",
        action="store_true",
        help=(
            "after each case's drafts pass the code checks, ask a verifier once per "
            "case whether the brief supports every factual statement the drafts "
            "state; only a material contradiction makes a draft abstain"
        ),
    )
    parser.add_argument(
        "--ablate",
        choices=list(run_benchmark.brief.ABLATIONS),
        default=None,
        metavar="NAME",
        help=(
            "build every case's brief with one thing removed, so the run measures "
            "the pipeline without it: {0}. Off by default. The run writes to "
            "runs/ablation/<name>/<model>/ -- under the set's own root, so the "
            "second set's go to runs/codex/ablation/<name>/<model>/ -- and never "
            "into a run directory holding an unablated result".format(
                ", ".join(run_benchmark.brief.ABLATIONS)
            )
        ),
    )
    parser.add_argument(
        "--precedents",
        action="store_true",
        help=(
            "show the judge up to three earlier human closures from the "
            "precedent library, chosen because they share clauses with the case. "
            "Off by default. Results go to runs/precedents/<model>/ -- under the "
            "set's own root, so the second set's go to "
            "runs/codex/precedents/<model>/ -- and never into a run directory "
            "holding a run whose judge saw no block. Figures with precedents on "
            "are not comparable to the headline: the library is built by people "
            "who have seen these sets"
        ),
    )
    parser.add_argument(
        "--verify-recorded-drafts",
        type=Path,
        default=None,
        metavar="RUN_DIR",
        help=(
            "reuse RUN_DIR's recorded judge drafts and call only the verifier, so on "
            "and off are compared on the same drafts. The set's results go to "
            "runs/<set>/verify-recorded-drafts/<model>/, never into the set's own "
            "run directory"
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print the sets separately and combined from cached runs; makes no model call",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    model = run_benchmark.resolve_model(args.model)

    if args.ablate is not None:
        # An ablation changes what every agent is given, so it cannot be
        # combined with a mode that reads a recorded run or reports one: those
        # modes would be describing results produced without the ablation, and
        # naming the switch beside them would look as though it had been
        # applied. Refused before any of them runs, and before any call.
        for present, name in (
            (args.report, "--report"),
            (args.replay_advocates is not None, "--replay-advocates"),
            (args.replay_check is not None, "--replay-check"),
            (args.verify_recorded_drafts is not None, "--verify-recorded-drafts"),
        ):
            if present:
                print(
                    "FATAL: --ablate builds an ablated brief and takes no {0}".format(name),
                    file=sys.stderr,
                )
                return 1

    if args.precedents:
        # The same rule the ablation follows: a run that shows the judge earlier
        # closures cannot be combined with a mode that reads a run recorded
        # without them or that reports one, because each of those would look as
        # though the block had been shown when it had not. Refused before any of
        # them runs, and before any call.
        if args.ablate is not None:
            print(
                "FATAL: at most one of --ablate and --precedents may be given per "
                "invocation: each changes what the agents are given, and a run "
                "with both on measures neither",
                file=sys.stderr,
            )
            return 1
        for present, name in (
            (args.report, "--report"),
            (args.replay_advocates is not None, "--replay-advocates"),
            (args.replay_check is not None, "--replay-check"),
            (args.verify_recorded_drafts is not None, "--verify-recorded-drafts"),
        ):
            if present:
                print(
                    "FATAL: --precedents shows the judge earlier closures and "
                    "takes no {0}".format(name),
                    file=sys.stderr,
                )
                return 1

    if args.report:
        if args.replay_advocates is not None or args.replay_check is not None:
            print("FATAL: --report reads cached runs and takes no replay arguments", file=sys.stderr)
            return 1
        if args.verify_drafts or args.verify_recorded_drafts is not None:
            print(
                "FATAL: --report reads cached runs and takes no verification argument",
                file=sys.stderr,
            )
            return 1
        print(render_development_sets(model, args.runs_dir))
        return 0

    selected = [named(args.set_name)] if args.set_name != "all" else list(DEVELOPMENT_SETS)

    try:
        cases = run_benchmark.parse_cases(args.cases)
    except run_benchmark.BenchmarkError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    if args.verify_recorded_drafts is not None:
        if args.replay_advocates is not None or args.replay_check is not None:
            print(
                "FATAL: --verify-recorded-drafts reuses recorded drafts and takes "
                "no replay arguments",
                file=sys.stderr,
            )
            return 1
        from eval import verify_drafts

        status = 0
        for development_set in selected:
            subset = [
                case_no
                for case_no in development_set.cases
                if not cases or case_no in cases
            ]
            if not subset:
                continue
            try:
                report = verify_drafts.verify_recorded_run(
                    args.verify_recorded_drafts,
                    subset,
                    model=model,
                    runs_dir=development_set.runs_dir(args.runs_dir),
                    prompts_dir=args.prompts_dir,
                    timeout_seconds=args.timeout,
                    case_loader=development_set.load_case,
                    label=development_set.name,
                )
            except run_benchmark.llm.ModelNotProvisionedError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            except run_benchmark.llm.MissingAPIKeyError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            except run_benchmark.BenchmarkError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            print("development set {0}".format(development_set.name))
            print(verify_drafts.render_report(report))
            if not report.ok:
                status = 1
        return status

    if args.replay_check is not None:
        if args.verify_drafts:
            print("FATAL: --replay-check reads a run and takes no --verify-drafts", file=sys.stderr)
            return 1
        # One check per set, because the cases of two sets are loaded by two
        # different loaders and a replay is only replayable if this code builds
        # the same brief for the case.
        status = 0
        for development_set in selected:
            subset = [case_no for case_no in development_set.cases if not cases or case_no in cases]
            if not subset:
                continue
            try:
                check = run_benchmark.check_replay(
                    args.replay_check,
                    subset,
                    model=model,
                    prompts_dir=args.prompts_dir,
                    case_loader=development_set.load_case,
                )
            except run_benchmark.BenchmarkError as exc:
                print("FATAL: {0}".format(exc), file=sys.stderr)
                return 1
            print("development set {0}".format(development_set.name))
            print(run_benchmark.render_replay_check(check))
            if check.refused:
                status = 1
        return status

    summaries = []
    for development_set in selected:
        subset = [case_no for case_no in development_set.cases if not cases or case_no in cases]
        if not subset:
            continue
        try:
            summary = run_set(
                development_set,
                model,
                runs_dir=args.runs_dir,
                cases=subset,
                prompts_dir=args.prompts_dir,
                force=args.force,
                token_budget=args.token_budget,
                concurrency=args.concurrency,
                timeout_seconds=args.timeout,
                case_deadline_seconds=args.case_deadline,
                judge_votes=args.judge_votes,
                replay_dir=args.replay_advocates,
                verify_drafts=args.verify_drafts,
                ablation=args.ablate,
                precedents=(
                    run_benchmark.PRECEDENTS_STORE if args.precedents else None
                ),
            )
        except run_benchmark.llm.ModelNotProvisionedError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except run_benchmark.llm.MissingAPIKeyError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        except run_benchmark.BenchmarkError as exc:
            print("FATAL: {0}".format(exc), file=sys.stderr)
            return 1
        run_benchmark.print_summary(summary)
        summaries.append(summary)

    if summaries:
        print("")
        print(render_development_sets(model, args.runs_dir))
    return 0 if all(summary.ok for summary in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
