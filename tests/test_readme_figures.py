"""Every figure the README states, recomputed from the committed runs and keys.

The README is the first thing a reader sees, and a figure in it that has drifted
away from the file it came from is worse than no figure at all. This module
parses the results tables in ``README.md`` and recomputes each figure from the
committed runs and the frozen answer keys, so a figure that disagrees fails here
rather than misleading a reader.

The README carries **six** tables under this header -- the business value of a
run, the frozen system's at policy version 6, the third and fourth sealed sets'
at the same version, the functional sets added after the sealed run, and the
earlier blocks' -- and all six are parsed, so a figure stated in any of them is
checked and none can be dropped from the check by another appearing above it.

The tables are parsed rather than restated, so the check is against the README a
reader actually reads. The labels are matched exactly and in both directions: a
figure the README states and this module does not know about fails, and so does a
figure this module knows about that the README has dropped. Both are failures for
the same reason -- an unchecked figure is a figure that can drift.

**No model call is made.** Every reading is a cached result, a committed
measurement or a frozen key. The ``model call`` column is asserted too, because
the README claims every command in the table is read-only and a claim in prose is
not a check.
"""

from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    baselines,
    business_value,
    development_sets,
    fairness,
    func_sets,
    grade,
    run_benchmark,
    sealed_report,
    v6_runs,
)
from tests import portability  # noqa: E402

# The results tables moved, whole, from README.md to docs/record.md on 2026-10-13,
# when the README became a short front page; the tables are checked where they now live.
README = PROJECT_ROOT / "docs" / "record.md"
MODEL = run_benchmark.resolve_model(None)
MODEL_SLUG = run_benchmark.model_slug(MODEL)

# The header of the results table, as it reads in the README.
TABLE_HEADER = ("figure", "value", "read from", "recompute with", "model call")

VERIFIER_DIRS = (
    PROJECT_ROOT / "runs" / "verify-recorded-drafts" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "codex" / "verify-recorded-drafts" / MODEL_SLUG,
)

# Every run directory a figure in the README is graded from. Named here so the
# verifier-switch row can be checked against the same list the scores come from.
SCORED_RUN_DIRS = (
    PROJECT_ROOT / "runs" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "codex" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "wild" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "wild-v2" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "ablation" / "admissibility" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "codex" / "ablation" / "admissibility" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "ablation" / "clause-notes" / MODEL_SLUG,
    PROJECT_ROOT / "runs" / "codex" / "ablation" / "clause-notes" / MODEL_SLUG,
)

ABLATION_RUN_DIRS = {
    ("admissibility", "corpus"): PROJECT_ROOT / "runs" / "ablation" / "admissibility" / MODEL_SLUG,
    ("admissibility", "codex"): PROJECT_ROOT / "runs" / "codex" / "ablation" / "admissibility" / MODEL_SLUG,
    ("clause-notes", "corpus"): PROJECT_ROOT / "runs" / "ablation" / "clause-notes" / MODEL_SLUG,
    ("clause-notes", "codex"): PROJECT_ROOT / "runs" / "codex" / "ablation" / "clause-notes" / MODEL_SLUG,
}


# --------------------------------------------------------------------------
# Reading the README
# --------------------------------------------------------------------------
def _cells(line: str) -> List[str]:
    """The cells of one markdown table row, or ``[]`` when it is not a row."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _plain(cell: str) -> str:
    """A cell with its markdown emphasis and code spans removed."""
    text = cell.replace("**", "").replace("*", "").replace("`", "")
    return " ".join(text.split())


def _table_rows(text: str) -> List[List[str]]:
    """The results tables' data rows, as lists of cells.

    Located by their header rather than by position, and each table is read
    until the first line that is not a table row. The README states the figures
    in six tables under this header -- the business value of a run, the frozen
    system's at policy version 6, the third and fourth sealed sets', the
    functional sets added after the sealed run, and the earlier blocks' -- and
    all six are read, so none is left unchecked by another sitting above it.
    """
    lines = text.splitlines()
    rows: List[List[str]] = []
    found = False
    index = 0
    while index < len(lines):
        cells = _cells(lines[index])
        if cells and tuple(_plain(cell).lower() for cell in cells) == TABLE_HEADER:
            found = True
            index += 2  # skip the header and its alignment row
            while index < len(lines):
                row = _cells(lines[index])
                if not row:
                    break
                if len(row) != len(TABLE_HEADER):
                    raise AssertionError(
                        "README.md has a results row with {0} cells, not {1}: {2!r}".format(
                            len(row), len(TABLE_HEADER), lines[index]
                        )
                    )
                rows.append(row)
                index += 1
            continue
        index += 1
    if not found:
        raise AssertionError(
            "README.md has no results table headed {0}".format(" | ".join(TABLE_HEADER))
        )
    if not rows:
        raise AssertionError("README.md's results table has no rows")
    return rows


def read_table(text: str) -> Dict[str, str]:
    """The README's results table, as ``{figure label: value}``."""
    rows: Dict[str, str] = {}
    for cells in _table_rows(text):
        label = _plain(cells[0])
        if label in rows:
            raise AssertionError("README.md states the figure {0!r} twice".format(label))
        rows[label] = _plain(cells[1])
    return rows


def read_model_call_column(text: str) -> Dict[str, str]:
    """The ``model call`` cell of every results row, keyed by figure label."""
    column = len(TABLE_HEADER) - 1
    return {_plain(cells[0]): _plain(cells[column]) for cells in _table_rows(text)}


# --------------------------------------------------------------------------
# Recomputing the figures
# --------------------------------------------------------------------------
def fraction(matched: Any, total: int) -> str:
    """``55/62 = 88.7%``, through the grader's own rounding.

    The percentage is ``eval.grade``'s -- one decimal place, half up -- so the
    README and the grader cannot come to round the same figure differently.
    """
    percent = grade.render_percent(grade._percent(matched, total))
    return "{0}/{1} = {2}".format(matched, total, percent)


def ratio(matched: int, total: int) -> str:
    """``3/7 = 0.429``, through the grader's own ratio rendering."""
    return "{0}/{1} = {2}".format(
        matched, total, grade.render_ratio(grade._ratio(matched, total))
    )


def case_list(cases: Sequence[int]) -> str:
    return ", ".join(str(case_no) for case_no in cases)


def money(value: Any) -> str:
    """A money figure to two decimals, as the README states money.

    ``eval.grade.render_money`` prints the literal that was recorded, so a run
    that wrote ``1.8`` reads back as ``1.8``; the README states amounts to two
    decimals throughout, and that is what this checks against.
    """
    return "{0:.2f}".format(value)


def cases_with_no_ruling(
    development_set: development_sets.DevelopmentSet, report: grade.GradeReport
) -> List[int]:
    """The set's cases the run produced no ruling for.

    ``GradeReport.unproduced`` cannot answer this: a case with no cached result
    is not graded at all, so it never reaches the report. The set's own case list
    is the only thing that knows the case exists.
    """
    return sorted(set(development_set.cases) - set(report.graded_cases))


def graded(development_set: development_sets.DevelopmentSet, run_dir: Path) -> grade.GradeReport:
    return run_benchmark.grade_run(
        run_dir, development_set.key(), case_loader=development_set.load_case
    )


def sealed_figures(name: str) -> grade.GradeReport:
    """One sealed set's committed run, graded against its own frozen key."""
    development_set = development_sets.named(name)
    return graded(development_set, development_set.run_dir(MODEL))


def sealed_categories(name: str) -> Dict[int, str]:
    """Each case's category, from the set's own ``index.json``.

    Read through the sealed report's own helper, so a category figure in the
    README is the one ``python3 -m eval.sealed_report --set <name>`` prints
    rather than a second reading of the same index that could come to differ
    from it.
    """
    return sealed_report._categories(development_sets.named(name))


def category_four_field(
    report: grade.GradeReport, categories: Mapping[int, str], name: str
) -> Tuple[int, int]:
    """Four-field exact over every case of one category, a miss counted as one."""
    in_set = sorted(
        case_no for case_no, category in categories.items() if category == name
    )
    return sealed_report._exact_among(report, in_set)


def ablation_figures(name: str) -> Tuple[int, int]:
    """The four-field exact count over both development sets, and the total."""
    exact = 0
    total = 0
    for set_name in ("corpus", "codex"):
        development_set = development_sets.named(set_name)
        report = graded(development_set, ABLATION_RUN_DIRS[(name, set_name)])
        exact += report.exact_matches
        total += report.total
    return exact, total


def baseline_rows() -> Dict[str, baselines.Row]:
    """Every combined baseline row, built once.

    Building a section rebuilds every case's panel of drafts, which is the most
    expensive thing this module does, so the rows are built once and read three
    times rather than rebuilt per figure.
    """
    sections = [
        baselines.build_section(development_sets.named(name), MODEL)
        for name in ("corpus", "codex")
    ]
    combined = baselines.combine_sections(sections, MODEL)
    return {row.key: row for row in baselines.rows_for(combined)}


def verifier_documents() -> List[Mapping[str, Any]]:
    return [json.loads((directory / "verify-recorded.json").read_text()) for directory in VERIFIER_DIRS]


def verifier_cases() -> List[Mapping[str, Any]]:
    return [case for document in verifier_documents() for case in document["cases"]]


def material_contradiction_cases() -> List[int]:
    return sorted(
        {
            case["case_no"]
            for case in verifier_cases()
            for statement in case["contradicted"]
            if statement["material"]
        }
    )


def case_112_unanimous() -> str:
    """112's ruling under the admissibility ablation, with its panel agreement."""
    run_dir = ABLATION_RUN_DIRS[("admissibility", "corpus")]
    document = run_benchmark.load_cached(run_dir, 112)
    ruling = document["ruling"]["ruling"]
    transcript = json.loads(
        (run_dir / "case-00112.transcript.json").read_text(encoding="utf-8")
    )
    vote = transcript["vote"]
    if vote["agreement"] != 1.0 or vote["outcome"] != "carried":
        raise AssertionError(
            "112's admissibility panel is not unanimous: {0!r}".format(vote)
        )
    return "{0} {1}, unanimous".format(ruling["ruling"], money(ruling["amount_sgd"]))


def sample_case_ruling() -> str:
    """901's ruling under the current pipeline, beside its confidence."""
    document = json.loads(
        (
            PROJECT_ROOT
            / "runs"
            / "rerun-2026-09-29"
            / "external"
            / "ryde"
            / "case-00901.json"
        ).read_text(encoding="utf-8")
    )
    ruling = document["ruling"]["ruling"]
    return "{0}, confidence {1}".format(ruling["ruling"], ruling["confidence"])


def sample_case_expectation() -> str:
    """The organisers' own stated outcome for their sample case.

    Read so the README's row is a quotation of the committed file rather than a
    transcription of it. The file says in its own text that it is not part of the
    key and not an input to any agent, which is why the README labels the row a
    stated expectation and not an answer.
    """
    document = json.loads(
        (PROJECT_ROOT / "eval" / "external" / "ryde" / "expected.json").read_text(
            encoding="utf-8"
        )
    )
    return document["expected_outcome_as_stated"]


# --------------------------------------------------------------------------
# The frozen system, at policy version 6
# --------------------------------------------------------------------------
def v6_documents(run: "v6_runs.V6Run") -> Dict[int, Any]:
    """The cases a version-6 run covers, read through the module that reads them."""
    return v6_runs.documents(run.run_dir, run.cases)


def v6_key(run: "v6_runs.V6Run") -> Dict[int, Any]:
    """A version-6 run's own key, or nothing where the run is not scored."""
    return grade.load_answer_key(run.key_path) if run.key_path is not None else {}


def v6_report(run: "v6_runs.V6Run") -> grade.GradeReport:
    """One version-6 run graded, through the grader ``eval.v6_runs`` itself uses."""
    return v6_runs._grade_run(run, v6_documents(run), v6_key(run))


def v6_rate(matched: int, total: int) -> str:
    return v6_runs._rate_text(matched, total)


def v6_wilson(matched: int, total: int) -> str:
    return v6_runs.wilson_text(matched, total)


def v6_split(run: "v6_runs.V6Run") -> str:
    """``dev-v2-ext``'s two splits, graded separately, as ``--report`` prints them."""
    documents = v6_documents(run)
    key = v6_key(run)
    split = v6_runs.read_json(
        PROJECT_ROOT / "data" / "external" / "dev-v2-ext" / "split.json"
    )
    parts = []
    for label in ("calibration", "holdout"):
        members = [case_no for case_no in split[label] if case_no in documents]
        part = {case_no: documents[case_no] for case_no in members}
        report = v6_runs._grade_run(run, part, key)
        parts.append("{0} {1}".format(label, v6_rate(report.exact_matches, report.total)))
    return "; ".join(parts)


def v6_word(document: Mapping[str, Any]) -> Any:
    """A case document's ruling value, the way ``eval.v6_runs`` reads it."""
    inner = (document.get("ruling") or {}).get("ruling")
    return inner.get("ruling") if isinstance(inner, Mapping) else None


def v6_precedent_figures() -> Tuple[str, str]:
    """The 15 route-deviation cases with the precedents block on, and without it."""
    corpus = v6_runs.run_by_name("corpus")
    key = grade.load_answer_key(corpus.key_path)
    subset = {case_no: key[case_no] for case_no in v6_runs.ROUTE_DEVIATION_CASES}
    with_precedents = v6_runs._grade_run(
        v6_runs.PRECEDENTS_RUN, v6_documents(v6_runs.PRECEDENTS_RUN), key
    )
    corpus_documents = v6_documents(corpus)
    without_precedents = grade.grade(
        {
            case_no: corpus_documents[case_no].get("ruling")
            for case_no in v6_runs.ROUTE_DEVIATION_CASES
        },
        subset,
        corpus=subset,
    )
    return (
        v6_rate(with_precedents.exact_matches, with_precedents.total),
        v6_rate(without_precedents.exact_matches, without_precedents.total),
    )


def v6_precedent_changed() -> str:
    """The route-deviation cases whose ruling value moved when the block was shown."""
    corpus_documents = v6_documents(v6_runs.run_by_name("corpus"))
    precedent_documents = v6_documents(v6_runs.PRECEDENTS_RUN)
    return case_list(
        [
            case_no
            for case_no in v6_runs.ROUTE_DEVIATION_CASES
            if v6_word(precedent_documents[case_no]) != v6_word(corpus_documents[case_no])
        ]
    )


def v6_sample_901() -> str:
    """901 at version 6: its ruling, its amount, its confidence and its agreement."""
    document = v6_documents(v6_runs.run_by_name("ryde-v3"))[901]
    ruling = (document.get("ruling") or {}).get("ruling") or {}
    return "{0} {1:.2f}, confidence {2}, {3}".format(
        ruling.get("ruling"),
        ruling.get("amount_sgd"),
        ruling.get("confidence"),
        "unanimous" if document.get("vote_agreement") == 1.0 else "split",
    )


def v6_case_1779() -> str:
    """The prompt-injection case at version 6: its ruling value."""
    document = v6_documents(v6_runs.run_by_name("dev-v2"))[1779]
    return v6_word(document)


def v6_cost(run: "v6_runs.V6Run") -> str:
    """One run's cost in USD, at the prices ``eval.v6_runs`` bills at."""
    documents = v6_documents(run)
    prompt = sum(
        document.get("tokens", {}).get("prompt_tokens", 0) for document in documents.values()
    )
    cached = sum(
        document.get("tokens", {}).get("cached_tokens", 0) for document in documents.values()
    )
    completion = sum(
        document.get("tokens", {}).get("completion_tokens", 0)
        for document in documents.values()
    )
    cost = (
        Decimal(prompt - cached) * v6_runs.PRICE_INPUT
        + Decimal(cached) * v6_runs.PRICE_CACHED_INPUT
        + Decimal(completion) * v6_runs.PRICE_OUTPUT
    ) / v6_runs.MILLION
    return "{0} {1:.4f} USD".format(run.name, cost)


def v6_costs() -> str:
    """Every run the freeze names, the precedents run among them.

    Five, not four: the cost row is read off ``python3 -m eval.v6_runs --report``
    and that report bills the precedents run beside the other four, so a test
    that summed only ``v6_runs.RUNS`` would check a figure the report no longer
    prints.
    """
    return "; ".join(
        v6_cost(run) for run in v6_runs.RUNS + (v6_runs.PRECEDENTS_RUN,)
    )


# The three fairness figures are the only ones that read the runs' transcripts,
# which is the most expensive thing this module does, so they are computed once
# and read twice: ``expected()`` is called by two tests.
_FAIRNESS_FIGURES: Dict[str, str] = {}


def fairness_figures() -> Dict[str, str]:
    """The three fairness rows, over both version-6 development runs together.

    Read through ``eval.fairness`` rather than re-derived here, so the README
    and ``python3 -m eval.fairness --report`` cannot come to print the same
    figure two ways.
    """
    if not _FAIRNESS_FIGURES:
        lean, swap, calibration = fairness.combined_measurements()
        _FAIRNESS_FIGURES.update(
            {
                "Fairness, both version-6 runs — errors towards the rider / towards the driver / to an escalation": fairness.error_lean_cell(
                    lean
                ),
                "Fairness, both version-6 runs — position-swap agreement on all four graded fields": fairness.swap_agreement_cell(
                    swap
                ),
                "Fairness, both version-6 runs — expected calibration error": fairness.calibration_error_cell(
                    calibration
                ),
            }
        )
    return dict(_FAIRNESS_FIGURES)


def v6_expected() -> Dict[str, str]:
    """Every figure the README's first block states, recomputed from the runs."""
    dev = v6_runs.run_by_name("dev-v2-ext")
    dev_report = v6_report(dev)
    dev_calibration = dev_report.calibration
    true_positives = len(dev_calibration.true_positives)
    corpus_report = v6_report(v6_runs.run_by_name("corpus"))
    with_precedents, without_precedents = v6_precedent_figures()
    figures = {
        "dev-v2-ext — four-field exact": v6_rate(
            dev_report.exact_matches, dev_report.total
        ),
        "dev-v2-ext — Wilson 95% interval": v6_wilson(
            dev_report.exact_matches, dev_report.total
        ),
        "dev-v2-ext — escalation precision": ratio(
            true_positives, true_positives + len(dev_calibration.false_positives)
        ),
        "dev-v2-ext — escalation recall": ratio(
            true_positives, true_positives + len(dev_calibration.false_negatives)
        ),
        "dev-v2-ext — over-escalations": case_list(dev_calibration.over_escalations),
        "dev-v2-ext — under-escalation": case_list(dev_calibration.under_escalations),
        "dev-v2-ext — calibration and holdout splits, four-field exact": v6_split(dev),
        "Corpus at version 6 — four-field exact": v6_rate(
            corpus_report.exact_matches, corpus_report.total
        ),
        "Corpus at version 6 — cases that differ from the key": case_list(
            sorted(score.case_no for score in corpus_report.cases if not score.exact)
        ),
        "Precedent arm — the 15 route-deviation cases, with precedents": with_precedents,
        "Precedent arm — the same 15, without precedents": without_precedents,
        "Precedent arm — rulings that changed": v6_precedent_changed(),
        "Sample case 901 at version 6": v6_sample_901(),
        "dev-v2 case 1779 (prompt injection in the chat) at version 6 — the model refused the planted clause, the draft check escalated": v6_case_1779(),
        "Cost of the version-6 runs, from the transcripts": v6_costs(),
    }
    figures.update(fairness_figures())
    return figures


# --------------------------------------------------------------------------
# The figures, keyed by the label the README gives them
# --------------------------------------------------------------------------
class ReadmeFigureTests(unittest.TestCase):
    """The README's results table against the committed runs and keys."""

    @classmethod
    def setUpClass(cls) -> None:
        text = README.read_text(encoding="utf-8")
        cls.table = read_table(text)
        cls.model_call = read_model_call_column(text)

        cls.sealed = sealed_figures("wild")
        cls.sealed_v2 = sealed_figures("wild-v2")
        cls.sealed_v2_categories = sealed_categories("wild-v2")
        cls.sealed_v1 = sealed_figures("sealed-v1")
        cls.sealed_v1_categories = sealed_categories("sealed-v1")
        # The fourth sealed set. Its attribute is not called ``sealed_v2``: that
        # name is the second sealed set's here, because the registration is
        # ``wild-v2`` and the two names are not the same thing.
        cls.fourth = sealed_figures("sealed-v2")
        cls.fourth_categories = sealed_categories("sealed-v2")
        cls.corpus = graded(development_sets.named("corpus"), development_sets.named("corpus").run_dir(MODEL))
        cls.codex = graded(development_sets.named("codex"), development_sets.named("codex").run_dir(MODEL))
        cls.admissibility = ablation_figures("admissibility")
        cls.clause_notes = ablation_figures("clause-notes")
        cls.baselines = baseline_rows()
        cls.verifier = verifier_cases()
        cls.material_cases = material_contradiction_cases()
        cls.case_112 = case_112_unanimous()
        cls.sample_ruling = sample_case_ruling()
        cls.sample_expectation = sample_case_expectation()

    def expected(self) -> Dict[str, str]:
        sealed = self.sealed
        calibration = sealed.calibration
        second = self.sealed_v2
        second_calibration = second.calibration
        third = self.sealed_v1
        third_calibration = third.calibration
        fourth = self.fourth
        fourth_calibration = fourth.calibration
        figures = {
            "Held-out set (wild-v1) — four-field exact, of the cases that produced a ruling": fraction(
                sealed.exact_matches, sealed.total
            ),
            "Held-out set (wild-v1) — four-field exact, over all 64 cases": fraction(
                sealed.exact_matches, 64
            ),
            "Held-out set (wild-v1) — ruling alone, of the cases that produced a ruling": fraction(
                sealed.field_tally("ruling")[0], sealed.total
            ),
            "Held-out set (wild-v1) — escalation precision": ratio(
                len(
                    set(calibration.produced_escalations)
                    & set(calibration.expected_escalations)
                ),
                len(calibration.produced_escalations),
            ),
            "Held-out set (wild-v1) — escalation recall": ratio(
                len(
                    set(calibration.produced_escalations)
                    & set(calibration.expected_escalations)
                ),
                len(calibration.expected_escalations),
            ),
            "Held-out set (wild-v1) — over-escalations": case_list(calibration.over_escalations),
            "Held-out set (wild-v1) — under-escalation": case_list(calibration.under_escalations),
            "Held-out set (wild-v1) — cases with no ruling": case_list(
                cases_with_no_ruling(development_sets.named("wild"), sealed)
            ),
            "Held-out set (wild-v1) — cases that differ from the key": case_list(
                sorted(score.case_no for score in sealed.failures)
            ),
            "Second sealed set (wild-v2) — four-field exact, of the cases that produced a ruling": fraction(
                second.exact_matches, second.total
            ),
            "Second sealed set (wild-v2) — four-field exact, over all 20 cases": fraction(
                second.exact_matches, 20
            ),
            "Second sealed set (wild-v2) — ruling alone, of the cases that produced a ruling": fraction(
                second.field_tally("ruling")[0], second.total
            ),
            "Second sealed set (wild-v2) — escalation precision": ratio(
                len(
                    set(second_calibration.produced_escalations)
                    & set(second_calibration.expected_escalations)
                ),
                len(second_calibration.produced_escalations),
            ),
            "Second sealed set (wild-v2) — escalation recall": ratio(
                len(
                    set(second_calibration.produced_escalations)
                    & set(second_calibration.expected_escalations)
                ),
                len(second_calibration.expected_escalations),
            ),
            "Second sealed set (wild-v2) — over-escalation": case_list(
                second_calibration.over_escalations
            ),
            "Second sealed set (wild-v2) — under-escalation": case_list(
                second_calibration.under_escalations
            ),
            "Second sealed set (wild-v2) — ROUTE_DEVIATION four-field exact": fraction(
                *category_four_field(
                    second, self.sealed_v2_categories, "ROUTE_DEVIATION"
                )
            ),
            "Second sealed set (wild-v2) — NO_SHOW_CHARGE four-field exact": fraction(
                *category_four_field(
                    second, self.sealed_v2_categories, "NO_SHOW_CHARGE"
                )
            ),
            "Second sealed set (wild-v2) — cases with no ruling": case_list(
                cases_with_no_ruling(development_sets.named("wild-v2"), second)
            )
            or "none",
            "Third sealed set (sealed-v1) — four-field agreement, of the cases that produced a ruling": fraction(
                third.exact_matches, third.total
            ),
            "Third sealed set (sealed-v1) — four-field agreement, over all 24 cases": fraction(
                third.exact_matches, 24
            ),
            # The key as imported differs from the key as it stands by exactly
            # one record -- case 311, whose key moved to ``PARTIAL_REFUND 7.05``
            # under an amendment the policy owner wrote before the run -- so the
            # imported figure is one below the standing one. Both rows are in
            # the README, side by side, and the imported one is recomputed here
            # rather than transcribed: the run produced ``PARTIAL_REFUND 7.05``
            # on 311, so 311 is a match under the key as it stands and a miss
            # under the key as imported.
            "Third sealed set (sealed-v1) — four-field agreement, over all 24 cases, under the key as imported": fraction(
                third.exact_matches - 1, 24
            ),
            "Third sealed set (sealed-v1) — ruling alone, of the cases that produced a ruling": fraction(
                third.field_tally("ruling")[0], third.total
            ),
            "Third sealed set (sealed-v1) — Wilson 95% interval": v6_wilson(
                third.exact_matches, 24
            ),
            "Third sealed set (sealed-v1) — escalation precision": ratio(
                len(
                    set(third_calibration.produced_escalations)
                    & set(third_calibration.expected_escalations)
                ),
                len(third_calibration.produced_escalations),
            ),
            "Third sealed set (sealed-v1) — escalation recall": ratio(
                len(
                    set(third_calibration.produced_escalations)
                    & set(third_calibration.expected_escalations)
                ),
                len(third_calibration.expected_escalations),
            ),
            "Third sealed set (sealed-v1) — over-escalations": case_list(
                third_calibration.over_escalations
            ),
            "Third sealed set (sealed-v1) — under-escalation": case_list(
                third_calibration.under_escalations
            ),
            "Third sealed set (sealed-v1) — ROUTE_DEVIATION four-field agreement": fraction(
                *category_four_field(
                    third, self.sealed_v1_categories, "ROUTE_DEVIATION"
                )
            ),
            "Third sealed set (sealed-v1) — NO_SHOW_CHARGE four-field agreement": fraction(
                *category_four_field(
                    third, self.sealed_v1_categories, "NO_SHOW_CHARGE"
                )
            ),
            "Third sealed set (sealed-v1) — cases with no ruling": case_list(
                cases_with_no_ruling(development_sets.named("sealed-v1"), third)
            )
            or "none",
            "Fourth sealed set (sealed-v2) — four-field agreement, of the cases that produced a ruling": fraction(
                fourth.exact_matches, fourth.total
            ),
            "Fourth sealed set (sealed-v2) — four-field agreement, over all 12 cases": fraction(
                fourth.exact_matches, 12
            ),
            "Fourth sealed set (sealed-v2) — ruling alone, of the cases that produced a ruling": fraction(
                fourth.field_tally("ruling")[0], fourth.total
            ),
            "Fourth sealed set (sealed-v2) — Wilson 95% interval": v6_wilson(
                fourth.exact_matches, 12
            ),
            "Fourth sealed set (sealed-v2) — escalation precision": ratio(
                len(
                    set(fourth_calibration.produced_escalations)
                    & set(fourth_calibration.expected_escalations)
                ),
                len(fourth_calibration.produced_escalations),
            ),
            "Fourth sealed set (sealed-v2) — escalation recall": ratio(
                len(
                    set(fourth_calibration.produced_escalations)
                    & set(fourth_calibration.expected_escalations)
                ),
                len(fourth_calibration.expected_escalations),
            ),
            "Fourth sealed set (sealed-v2) — over-escalations": case_list(
                fourth_calibration.over_escalations
            )
            or "none",
            "Fourth sealed set (sealed-v2) — under-escalation": case_list(
                fourth_calibration.under_escalations
            )
            or "none",
            "Fourth sealed set (sealed-v2) — ROUTE_DEVIATION four-field agreement": fraction(
                *category_four_field(
                    fourth, self.fourth_categories, "ROUTE_DEVIATION"
                )
            ),
            "Fourth sealed set (sealed-v2) — NO_SHOW_CHARGE four-field agreement": fraction(
                *category_four_field(
                    fourth, self.fourth_categories, "NO_SHOW_CHARGE"
                )
            ),
            "Fourth sealed set (sealed-v2) — cases with no ruling": case_list(
                cases_with_no_ruling(development_sets.named("sealed-v2"), fourth)
            )
            or "none",
            "Corpus — four-field exact (development)": fraction(
                self.corpus.exact_matches, self.corpus.total
            ),
            "Second set — four-field exact (development)": fraction(
                self.codex.exact_matches, self.codex.total
            ),
            "Ablation — admissibility precheck removed, both sets, policy version 1, 2026-09-29": fraction(*self.admissibility),
            "Ablation — admissibility removed, case 112, policy version 1, 2026-09-29": self.case_112,
            "Ablation — clause notes removed, both sets, policy version 1, 2026-09-29": fraction(*self.clause_notes),
            "Baseline — always ESCALATE, both sets": self._baseline("always_escalate"),
            "Baseline — one draft, mean of the four, both sets": self._baseline(
                "single_draft:mean"
            ),
            "Baseline — the carried vote, both sets": self._baseline("carried_vote"),
            "Verifier — rulings the material rule changed": self._rulings_changed(),
            "Verifier — statements judged contradicted": self._contradicted(),
            "Verifier — cases carrying a material contradiction": case_list(
                self.material_cases
            ),
            "Verifier — the switch in every scored run": self._verifier_switch(),
            "Sample case 901 — policy version 1, 2026-09-29": self.sample_ruling,
            "Sample case 901 — the organisers' stated expectation": self.sample_expectation,
        }
        # The README's first block, the frozen system at policy version 6, is a
        # second table under the same header and is checked the same way.
        figures.update(v6_expected())
        # The two post-sealed blocks -- the business value of a run, and the
        # functional sets -- are read from the modules that print them, so the
        # README and the code cannot come to state one of these figures two
        # ways.
        figures.update(business_value.figures())
        figures.update(func_sets.figures())
        return figures

    def _baseline(self, key: str) -> str:
        """One combined baseline row's four-field cell, as ``n/m = p%``.

        The mean row's numerator is fractional -- ``42.25`` -- so the cell is
        parsed as a ``Decimal`` rather than an ``int``.
        """
        matched, total = self.baselines[key].cell("exact").split("/")
        return fraction(Decimal(matched), int(total))

    def _rulings_changed(self) -> str:
        usable = [case for case in self.verifier if case["usable"]]
        changed = [
            case
            for case in usable
            if case["without"].get("ruling") != case["material_only"].get("ruling")
        ]
        return "{0} of {1}".format(len(changed), len(usable))

    def _contradicted(self) -> str:
        contradicted = sum(len(case["contradicted"]) for case in self.verifier)
        material = sum(
            1
            for case in self.verifier
            for statement in case["contradicted"]
            if statement["material"]
        )
        judged = sum(len(case["judged"]) for case in self.verifier)
        return "{0} of {1:,} ({2} material)".format(contradicted, judged, material)

    def _verifier_switch(self, run_dirs: Optional[Sequence[Path]] = None) -> str:
        """The switch, read from the case files the row's source names.

        ``run.json`` records the ``configuration`` of the **last** invocation,
        and two of the scored directories record none there at all, so a check
        that read only ``run.json`` passed those two without reading anything.
        The case files carry the same object per case, and they are what the
        row's ``read from`` cell names. ``run_dirs`` exists so the check can be
        shown to fail on a directory that has the switch on.
        """
        directories = tuple(SCORED_RUN_DIRS if run_dirs is None else run_dirs)
        for run_dir in directories:
            for case_file in sorted(run_dir.glob("case-*.json")):
                case = json.loads(case_file.read_text(encoding="utf-8"))
                configuration = case.get("configuration")
                if isinstance(configuration, Mapping) and configuration.get(
                    "verify_drafts"
                ):
                    try:
                        where = case_file.relative_to(PROJECT_ROOT)
                    except ValueError:
                        where = case_file
                    raise AssertionError(
                        "{0} ran with the draft verifier on".format(where)
                    )
        return "off, in all {0}".format(len(directories))

    # -- the assertions ----------------------------------------------------
    def test_the_readme_states_every_figure_this_module_checks(self) -> None:
        expected = self.expected()
        missing = sorted(set(expected) - set(self.table))
        extra = sorted(set(self.table) - set(expected))
        self.assertEqual(
            missing,
            [],
            "the README has dropped figures this module checks: {0}".format(missing),
        )
        self.assertEqual(
            extra,
            [],
            "the README states figures this module does not check: {0}".format(extra),
        )

    def test_every_figure_in_the_readme_is_what_the_files_say(self) -> None:
        """The figures, recomputed from the committed runs and the frozen keys.

        A platform that cannot rebuild case 111's brief refuses that case in
        ``eval.baselines``, so the baseline rows' denominators move by one and
        the figures the README states -- which were measured on macOS -- cannot
        be recomputed here. The test skips there and says why, rather than
        comparing a macOS figure with a Linux one.
        """
        portability.require_the_same_libm()
        for label, value in self.expected().items():
            with self.subTest(figure=label):
                self.assertIn(label, self.table)
                self.assertEqual(
                    self.table[label],
                    value,
                    "the README says {0!r} for {1!r}; the committed files say {2!r}".format(
                        self.table[label], label, value
                    ),
                )

    def test_every_recompute_command_is_marked_as_making_no_model_call(self) -> None:
        self.assertEqual(
            sorted(set(self.model_call.values())),
            ["no"],
            "the README's results table marks a command as making a model call: {0}".format(
                sorted(set(self.model_call.values()))
            ),
        )


if __name__ == "__main__":
    unittest.main()
