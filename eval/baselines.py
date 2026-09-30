"""Baselines from recorded data, with no model call.

A baseline is a rule that answers every case without reading it, and it exists to
say what a score is worth: a figure no better than "always ESCALATE" is not
evidence that the panel is doing anything. Every row here is computed from what a
run already recorded -- the judge drafts on its transcripts and the rulings it
published -- so producing this file costs nothing and calls nothing.

The rows:

* **Always ESCALATE** -- null amounts, no referrals.
* **Majority ruling** -- the ruling the section's cases most often require, with
  null amounts and no referrals. It is chosen on the set it is scored on, which
  is exactly what makes it an in-sample baseline rather than a prediction.
* **Single draft** -- each of the four recorded drafts scored alone, and their
  mean. An abstained or invalid draft counts as a miss.
* **At least one draft right** -- an upper bound for any rule that publishes one
  of the drafts' answers; a no-majority escalation can exceed it.
* **The carried vote** -- what the run actually published, for comparison.

The drafts are rebuilt through
:func:`eval.verify_drafts.recorded_drafts_for_case` followed by
:func:`tribunal.pipeline.recorded_judge_drafts`, which is the same
reconstruction the recorded-drafts measurement uses, so a row here and a row
there count the same drafts. This module reads the answer key, which is why it
lives under ``eval/``.

Nothing here calls a model, and nothing here builds a client. The module does
not name ``LLMClient``, ``_default_client_factory``, ``verify_recorded_case`` or
``verify_recorded_run`` at all, and a test drives :func:`main` with
``tribunal.llm.LLMClient`` patched to raise.

The two development sets are development data, not test sets, and the caveat
that says so is carried from :mod:`eval.development_sets` rather than written a
second time here. Neither a section below nor the combined section is a
generalisation figure; the only one the submission reports belongs to the
held-out set, run once from the commit tagged ``freeze-2026-09-30``.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / "runs"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark, verify_drafts  # noqa: E402
from tribunal import pipeline  # noqa: E402

# The directory this module writes, under the runs root. Named apart from a
# model's own run directory on purpose: "never the headline directory" is then a
# property of the path rather than a promise.
BASELINES_DIRNAME = "baselines"
REPORT_FILE = "report.md"
DATA_FILE = "baselines.json"

# The three sampled drafts, by the seed each was asked under. The fourth is the
# position-swapped draft, which runs at the client's own settings.
SEEDED_DRAFTS: Tuple[int, ...] = (101, 202, 303)

# The label the upper-bound row carries, in the words the queue states it.
AT_LEAST_ONE_LABEL = (
    "an upper bound for any rule that publishes one of the drafts' answers; a "
    "no-majority escalation can exceed it"
)

# The column that counts a case only when all four graded fields agree, followed
# by one column per field. "Ruling alone" is the first of those.
EXACT_COLUMN = "exact (four fields)"
COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("exact", EXACT_COLUMN),
    ("ruling", "ruling alone"),
    ("amount_sgd", "amount"),
    ("driver_compensation_sgd", "driver"),
    ("referrals", "referrals"),
)

# The mean of the four single-draft rows is reported to two places.
MEAN_PLACES = Decimal("0.01")

COMBINED_NAME = "combined"


class BaselineError(Exception):
    """The baselines were asked for something they cannot do."""


# --------------------------------------------------------------------------
# Where the output may go
# --------------------------------------------------------------------------
def assert_not_a_run_directory(
    destination: Path, runs_dir: Path, model: str
) -> Path:
    """Refuse a destination that is a run directory, or lies inside one.

    ``runs/<model-slug>/`` holds the corpus result the submission reports,
    ``runs/codex/<model-slug>/`` the second development set's and
    ``runs/wild/<model-slug>/`` the held-out set's; everything under
    ``runs/external/`` is a headline directory too. Baselines are not a run, and
    a reader who found these figures there would read them as that run's, so the
    destination is refused before anything is written.

    The check is structural rather than a list of names: a directory that holds
    a run's own ``run.json``, or its case files, is a run directory whichever
    model it belongs to. Every headline directory for this model is refused by
    name as well -- the corpus's, the second development set's and the held-out
    set's -- so the refusal is the same whether or not those runs have been
    made yet.

    **Two roots are walked, not one.** ``--runs-dir`` and ``--out-dir`` are
    separate arguments, so a caller who points ``--runs-dir`` at a scratch root
    has not thereby made the repository's own run directories safe to write
    into -- and asking only about the given root accepted a destination under
    ``runs/<model-slug>/`` for exactly that reason. Every headline directory
    under either root is refused, so the guard no longer depends on the two
    arguments agreeing about where the runs are.
    """
    resolved = Path(destination).resolve()
    roots = [Path(runs_dir).resolve()]
    repository = Path(RUNS_DIR).resolve()
    if repository not in roots:
        roots.append(repository)

    for root in roots:
        for headline in run_benchmark.headline_run_directories(root, model):
            if resolved == headline.resolve():
                raise BaselineError(
                    "the baselines may not be written to the headline run "
                    "directory {0}; they are not that run's figures".format(resolved)
                )

        external = (root / run_benchmark.EXTERNAL_RUNS_SUBDIR).resolve()
        if resolved == external or external in resolved.parents:
            raise BaselineError(
                "the baselines may not be written under {0}; every directory "
                "there is a headline directory".format(external)
            )

        # Every directory from the destination up to this runs root, so a
        # destination *inside* a run directory is refused as well as the
        # directory itself.
        candidate = resolved
        while candidate != root and root in candidate.parents:
            if (candidate / run_benchmark.METADATA_FILE).is_file() or any(
                candidate.glob("case-*.json")
            ):
                raise BaselineError(
                    "the baselines may not be written to {0}, which holds a run's "
                    "own results".format(candidate)
                )
            candidate = candidate.parent
    return resolved


def baselines_directory(runs_dir: Path = RUNS_DIR) -> Path:
    """Where the baselines live: ``runs/baselines/``."""
    return Path(runs_dir) / BASELINES_DIRNAME


# --------------------------------------------------------------------------
# One section of the report
# --------------------------------------------------------------------------
@dataclass
class Section:
    """One set's analysed cases, its drafts and its refusals.

    ``analysed`` is the cases a row is scored over, and it is not the set: a
    case that is stale, unknown, or holds no panel of drafts is refused with its
    reason and left out of every figure rather than counted as a miss.
    """

    name: str
    run_dir: Path
    key: Dict[int, grade.Ruling]
    expected: int
    analysed: Tuple[int, ...] = ()
    drafts: Dict[int, Tuple[Any, ...]] = field(default_factory=dict)
    carried: Dict[int, Any] = field(default_factory=dict)
    refusals: Tuple[Tuple[int, str], ...] = ()

    @property
    def produced(self) -> int:
        return len(self.analysed)


def _refusal_reason(
    checker: Any, case_no: int, document: Mapping[str, Any]
) -> Optional[str]:
    """Why a cached case cannot be scored here, or ``None`` when it can.

    Checked with the set's own loader: a development set handed the corpus
    loader cannot rebuild a single brief, so every one of its cases would read
    ``unknown`` and be refused for the wrong reason.
    """
    status = checker.status_of(case_no, document)
    if status == grade.STALENESS_STALE:
        moved = ", ".join(checker.moved_for(case_no, document))
        return "stale: {0} moved".format(moved or "a recorded digest")
    if status == grade.STALENESS_UNKNOWN:
        return (
            "unknown: this code cannot establish that the result still belongs "
            "to it"
        )
    return None


def build_section(
    development_set: development_sets.DevelopmentSet,
    model: str,
    runs_dir: Path = RUNS_DIR,
    prompts_dir: Path = run_benchmark.PROMPTS_DIR,
) -> Section:
    """Read one set's cached run and rebuild every case's panel of drafts."""
    run_dir = development_set.run_dir(model, runs_dir)
    key = development_set.key()
    cases = development_sets.cached_cases(development_set, model, runs_dir)
    checker = run_benchmark.BriefStaleness(
        run_benchmark.brief_digest_for(development_set.load_case),
        run_dir=run_dir,
        prompts_dir=prompts_dir,
    )
    check = None
    if cases:
        check = run_benchmark.check_replay(
            run_dir,
            cases,
            model=model,
            prompts_dir=prompts_dir,
            case_loader=development_set.load_case,
        )

    analysed: List[int] = []
    drafts: Dict[int, Tuple[Any, ...]] = {}
    carried: Dict[int, Any] = {}
    refusals: List[Tuple[int, str]] = []
    for case_no in cases:
        document = run_benchmark.load_cached(run_dir, case_no)
        if document is None:
            refusals.append((case_no, "the run holds no cached result for it"))
            continue
        reason = _refusal_reason(checker, case_no, document)
        if reason is not None:
            refusals.append((case_no, reason))
            continue
        if check is None or case_no not in check.accepted:
            refusals.append(
                (
                    case_no,
                    (check.refused.get(case_no) if check is not None else None)
                    or "the run records no advocates this code can rebuild for it",
                )
            )
            continue
        found, reason = verify_drafts.recorded_drafts_for_case(
            case_no,
            check.accepted[case_no],
            source_dir=run_dir,
            prompts_dir=prompts_dir,
        )
        if found is None:
            refusals.append((case_no, reason))
            continue
        rebuilt = pipeline.recorded_judge_drafts(
            found["vote"],
            found["entries"],
            found["referee_result"],
            found["brief_object"],
        )
        analysed.append(case_no)
        drafts[case_no] = tuple(rebuilt)
        carried[case_no] = document.get("ruling")

    return Section(
        name=development_set.name,
        run_dir=run_dir,
        key=key,
        expected=len(development_set.cases),
        analysed=tuple(analysed),
        drafts=drafts,
        carried=carried,
        refusals=tuple(refusals),
    )


def combine_sections(
    sections: Sequence[Section], model: str, runs_dir: Path = RUNS_DIR
) -> Section:
    """One section over every set, each case scored against the key it belongs to.

    A case number is in exactly one set's key, so the merge is a union and no
    case is counted twice.
    """
    key: Dict[int, grade.Ruling] = {}
    analysed: List[int] = []
    drafts: Dict[int, Tuple[Any, ...]] = {}
    carried: Dict[int, Any] = {}
    refusals: List[Tuple[int, str]] = []
    for section in sections:
        key.update(section.key)
        analysed.extend(section.analysed)
        drafts.update(section.drafts)
        carried.update(section.carried)
        refusals.extend(section.refusals)
    return Section(
        name=COMBINED_NAME,
        run_dir=Path(runs_dir),
        key=key,
        expected=sum(section.expected for section in sections),
        analysed=tuple(sorted(analysed)),
        drafts=drafts,
        carried=carried,
        refusals=tuple(sorted(refusals)),
    )


# --------------------------------------------------------------------------
# The answers each row publishes
# --------------------------------------------------------------------------
def _answer(ruling: str) -> Dict[str, Any]:
    """A POL-GEN-03 ruling object: one ruling, no money, no referrals."""
    return {
        "ruling": ruling,
        "amount_sgd": None,
        "driver_compensation_sgd": None,
        "referrals": [],
    }


def _draft_answer(draft: Any) -> Optional[Any]:
    """One draft's own answer, or ``None`` when it abstained.

    An abstained or invalid draft answers nothing, and a row that scored it as
    anything else would be inventing an answer it did not give. ``None`` scores
    as a miss, which is what an abstention is.
    """
    if draft is None or not getattr(draft, "valid", False):
        return None
    return draft.ruling


def _by_seed(drafts: Sequence[Any], seed: int) -> Optional[Any]:
    for draft in drafts:
        if draft.seed == seed:
            return draft
    return None


def _by_kind(drafts: Sequence[Any], kind: str) -> Optional[Any]:
    for draft in drafts:
        if draft.kind == kind:
            return draft
    return None


def majority_ruling(section: Section) -> str:
    """The ruling the section's cases most often require.

    The modal class, and the answer a rule that reads no case can give: it is
    the ruling the section's own key carries most often, over the cases that
    were analysed, which is the set every row here is scored on. A tie goes to
    the ruling that sorts first, which is a rule rather than a preference: two
    runs of the same data have to pick the same one.
    """
    counts: Dict[str, int] = {}
    for case_no in section.analysed:
        value = getattr(section.key.get(case_no), "ruling", None)
        if isinstance(value, str):
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        # No case was analysed, so there is no modal ruling to publish. The
        # policy's own default is the only answer left that is not invented.
        return grade.ESCALATE
    return max(sorted(counts), key=lambda name: counts[name])


def best_draft_answer(section: Section) -> Dict[int, Any]:
    """Per case, the draft that gets the most right, or ``None`` for none.

    The row it feeds asks whether *any* draft was right, so the answer published
    for a case is the best of its drafts: an exact one if it has one, else one
    whose ruling alone matches, else the first valid draft, else nothing. That
    makes the row's exact count the number of cases at least one draft got
    entirely right, and its ruling-only count the number at least one draft got
    the ruling right on.
    """
    chosen: Dict[int, Any] = {}
    for case_no in section.analysed:
        best = None
        best_rank = -1
        for draft in section.drafts.get(case_no, ()):
            if not getattr(draft, "valid", False):
                continue
            score = grade.score_case(
                case_no,
                section.key[case_no],
                grade.produced_from_mapping(draft.ruling, case_no),
            )
            rank = 2 if score.exact else (1 if score.correct_on("ruling") else 0)
            if rank > best_rank:
                best_rank = rank
                best = draft.ruling
            if best_rank == 2:
                break
        chosen[case_no] = best
    return chosen


# --------------------------------------------------------------------------
# Scoring a row
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Row:
    """One baseline, scored on the section it belongs to.

    A row is either a report over the section's analysed cases or, for the mean
    of the single-draft rows, a mean of four of them. The two are the same shape
    of figure and are rendered in the same columns, so the mean row carries
    means rather than a report of its own.
    """

    key: str
    label: str
    note: str
    total: int
    report: Optional[grade.GradeReport] = None
    means: Optional[Mapping[str, Decimal]] = None

    def cell(self, which: str) -> str:
        """The rendered cell for one column, as ``n/total``."""
        if self.total == 0:
            # Nothing was analysed, so every count would be a zero out of zero.
            # A dash says "not measured"; "0/0" says "measured, and zero".
            return "-"
        if self.means is not None:
            value = self.means[which].quantize(MEAN_PLACES, rounding=ROUND_HALF_UP)
            return "{0}/{1}".format(value, self.total)
        if self.report is None:
            return "-"
        if which == "exact":
            return "{0}/{1}".format(self.report.exact_matches, self.total)
        return "{0}/{1}".format(self.report.field_tally(which)[0], self.total)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "row": self.key,
            "label": self.label,
            "note": self.note,
            "cases": self.total,
            "exact": None if self.report is None else self.report.exact_matches,
            "fields": {
                name: None if self.report is None else self.report.field_tally(name)[0]
                for name in grade.GRADED_FIELDS
            },
            "means": (
                None
                if self.means is None
                else {name: str(value) for name, value in self.means.items()}
            ),
        }


def grade_row(section: Section, produced: Mapping[int, Any]) -> grade.GradeReport:
    """Grade one row's answers, on the cases the section analysed.

    The key is the analysed subset, so a refused case is left out rather than
    counted as a miss, and ``corpus`` is the whole key so the report can say the
    rate was computed on a selected set.
    """
    subset = {case_no: section.key[case_no] for case_no in section.analysed}
    return grade.grade(produced, key=subset, corpus=section.key)


def rows_for(section: Section) -> List[Row]:
    """Every baseline row, scored on this section."""
    total = section.produced
    rows: List[Row] = []

    report = grade_row(
        section, {case_no: _answer(grade.ESCALATE) for case_no in section.analysed}
    )
    rows.append(
        Row(
            key="always_escalate",
            label="Always ESCALATE",
            note="Null amounts and no referrals, on every case.",
            total=total,
            report=report,
        )
    )

    modal = majority_ruling(section)
    report = grade_row(
        section, {case_no: _answer(modal) for case_no in section.analysed}
    )
    rows.append(
        Row(
            key="majority_ruling",
            label="Majority ruling: {0}".format(modal),
            note=(
                "The ruling this section's cases most often require, with null "
                "amounts and no referrals. Chosen on the set it is scored on, so "
                "it is an in-sample figure and not a prediction."
            ),
            total=total,
            report=report,
        )
    )

    singles: List[Tuple[str, grade.GradeReport]] = []
    for seed in SEEDED_DRAFTS:
        produced = {
            case_no: _draft_answer(_by_seed(section.drafts.get(case_no, ()), seed))
            for case_no in section.analysed
        }
        singles.append(("seed {0}".format(seed), grade_row(section, produced)))
    produced = {
        case_no: _draft_answer(
            _by_kind(section.drafts.get(case_no, ()), pipeline.DRAFT_POSITION_SWAPPED)
        )
        for case_no in section.analysed
    }
    singles.append(("position-swapped", grade_row(section, produced)))
    for name, report in singles:
        rows.append(
            Row(
                key="single_draft:{0}".format(name),
                label="Single draft: {0}".format(name),
                note=(
                    "That one draft's answer on every analysed case. An "
                    "abstained or invalid draft counts as a miss."
                ),
                total=total,
                report=report,
            )
        )

    divisor = Decimal(len(singles))
    if divisor and total:
        rows.append(
            Row(
                key="single_draft:mean",
                label="Single draft: mean of the four",
                note="The arithmetic mean of the four rows above.",
                total=total,
                means={
                    name: Decimal(
                        sum(
                            report.exact_matches
                            if name == "exact"
                            else report.field_tally(name)[0]
                            for _, report in singles
                        )
                    )
                    / divisor
                    for name in ["exact"] + list(grade.GRADED_FIELDS)
                },
            )
        )

    report = grade_row(section, best_draft_answer(section))
    rows.append(
        Row(
            key="at_least_one_draft_right",
            label="At least one draft right",
            note=AT_LEAST_ONE_LABEL,
            total=total,
            report=report,
        )
    )

    report = grade_row(
        section, {case_no: section.carried.get(case_no) for case_no in section.analysed}
    )
    rows.append(
        Row(
            key="carried_vote",
            label="The carried vote",
            note="What the run published for each case, for comparison.",
            total=total,
            report=report,
        )
    )
    return rows


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _section_lines(section: Section, rows: Sequence[Row]) -> List[str]:
    lines = [
        "## {0} — {1}".format(section.name, _relative(section.run_dir)),
        "",
        "Scored over {0} of the {1} cases in the set; {2} refused.".format(
            section.produced, section.expected, len(section.refusals)
        ),
        "",
        "| row | {0} |".format(" | ".join(header for _, header in COLUMNS)),
        "|{0}|".format("|".join("---" for _ in range(len(COLUMNS) + 1))),
    ]
    for row in rows:
        lines.append(
            "| {0} |".format(
                " | ".join([row.label] + [row.cell(name) for name, _ in COLUMNS])
            )
        )
    lines.append("")
    for row in rows:
        if row.note:
            lines.append("- **{0}** — {1}".format(row.label, row.note))
    lines.append("")
    if section.refusals:
        lines.append("Refused cases, and why:")
        lines.append("")
        for case_no, reason in section.refusals:
            lines.append("- `{0}` — {1}".format(case_no, reason))
        lines.append("")
    else:
        lines.append("No case was refused.")
        lines.append("")
    return lines


def _relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def render_report(
    model: str, sections: Sequence[Section], rows: Mapping[str, Sequence[Row]]
) -> str:
    lines = [
        "# Baselines from recorded data",
        "",
        "Model: {0}. **No model call was made.** Every figure is computed from "
        "what each run already recorded: the judge drafts on its transcripts and "
        "the rulings it published.".format(model),
        "",
        development_sets.DEVELOPMENT_DATA_CAVEAT,
        "",
        "A row is scored over the cases its section analysed. A case that is "
        "stale, unknown, or holds no panel of drafts is refused with its reason "
        "and left out of every figure rather than counted as a miss, so a "
        "section's denominators are the cases that could be scored and not the "
        "size of the set.",
        "",
        "`exact (four fields)` counts a case only when the ruling, both amounts "
        "and the sorted referral clause references all agree. The four columns "
        "after it count one field each, `ruling alone` first.",
        "",
    ]
    for section in sections:
        lines.extend(_section_lines(section, rows[section.name]))
    lines.append(
        "The single-draft rows are the same four drafts the vote counts: three "
        "sampled at temperature 0.7 under seeds 101, 202 and 303, and one "
        "position-swapped. The mean of the four is an arithmetic mean of the "
        "four rows above it and not a measurement of its own."
    )
    return "\n".join(lines)


def data_document(
    model: str, sections: Sequence[Section], rows: Mapping[str, Sequence[Row]]
) -> Dict[str, Any]:
    return {
        "model": model,
        "sets": [section.name for section in sections],
        "note": (
            "Computed from recorded runs. No model call was made. A refused case "
            "is excluded from every figure rather than counted as a miss."
        ),
        "caveat": development_sets.DEVELOPMENT_DATA_CAVEAT,
        "sections": [
            {
                "name": section.name,
                "run_dir": _relative(section.run_dir),
                "expected": section.expected,
                "analysed": section.produced,
                "analysed_cases": list(section.analysed),
                "refused": [
                    {"case_no": case_no, "reason": reason}
                    for case_no, reason in section.refusals
                ],
                "rows": [row.as_dict() for row in rows[section.name]],
            }
            for section in sections
        ],
    }


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m eval.baselines",
        description=(
            "Score the baselines on the recorded runs: always ESCALATE, the "
            "majority ruling, each single draft, the best single draft and the "
            "carried vote. Reads the answer key and makes no model call."
        ),
    )
    parser.add_argument(
        "--model", default=None, help="the model id; defaults to tribunal/model.py"
    )
    parser.add_argument(
        "--set",
        dest="set_name",
        default="all",
        help="which development set: {0}, or all".format(
            ", ".join(sorted(development_sets.BY_NAME))
        ),
    )
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="where report.md and baselines.json go; defaults to runs/baselines/",
    )
    parser.add_argument("--prompts-dir", type=Path, default=run_benchmark.PROMPTS_DIR)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    model = run_benchmark.resolve_model(args.model)
    try:
        selected = (
            [development_sets.named(args.set_name)]
            if args.set_name != "all"
            else list(development_sets.DEVELOPMENT_SETS)
        )
    except run_benchmark.BenchmarkError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    runs_dir = Path(args.runs_dir)
    out_dir = baselines_directory(runs_dir) if args.out_dir is None else Path(args.out_dir)
    try:
        assert_not_a_run_directory(out_dir, runs_dir, model)
    except BaselineError as exc:
        print("FATAL: {0}".format(exc), file=sys.stderr)
        return 1

    sections = [
        build_section(development_set, model, runs_dir, Path(args.prompts_dir))
        for development_set in selected
    ]
    if len(selected) > 1:
        sections.append(combine_sections(sections, model, runs_dir))
    rows = {section.name: rows_for(section) for section in sections}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / REPORT_FILE).write_text(
        render_report(model, sections, rows), encoding="utf-8"
    )
    run_benchmark.write_json(out_dir / DATA_FILE, data_document(model, sections, rows))

    print("Baselines — {0}".format(model))
    print("")
    for section in sections:
        print(
            "  {0:<10} {1}/{2} cases scored, {3} refused".format(
                section.name, section.produced, section.expected, len(section.refusals)
            )
        )
        for row in rows[section.name]:
            print(
                "      {0:<46} {1}".format(
                    row.label,
                    "  ".join(
                        "{0} {1}".format(header, row.cell(name))
                        for name, header in COLUMNS
                    ),
                )
            )
    print("")
    print("Wrote {0}".format(_relative(out_dir / REPORT_FILE)))
    print("Wrote {0}".format(_relative(out_dir / DATA_FILE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
