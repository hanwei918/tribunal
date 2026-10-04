"""Every figure the README states, recomputed from the committed runs and keys.

The README is the first thing a reader sees, and a figure in it that has drifted
away from the file it came from is worse than no figure at all. This module
parses the results table in ``README.md`` and recomputes each figure from the
committed runs and the frozen answer keys, so a figure that disagrees fails here
rather than misleading a reader.

The table is parsed rather than restated, so the check is against the README a
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
from typing import Any, Dict, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import (  # noqa: E402
    baselines,
    development_sets,
    grade,
    run_benchmark,
    sealed_report,
)

README = PROJECT_ROOT / "README.md"
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
    """The results table's data rows, as lists of cells.

    Located by its header rather than by position, and read until the first line
    that is not a table row, so a second table added elsewhere cannot be mistaken
    for this one.
    """
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        cells = _cells(line)
        if cells and tuple(_plain(cell).lower() for cell in cells) == TABLE_HEADER:
            start = index
            break
    if start is None:
        raise AssertionError(
            "README.md has no results table headed {0}".format(" | ".join(TABLE_HEADER))
        )

    rows: List[List[str]] = []
    for line in lines[start + 2 :]:  # skip the header and its alignment row
        cells = _cells(line)
        if not cells:
            break
        if len(cells) != len(TABLE_HEADER):
            raise AssertionError(
                "README.md has a results row with {0} cells, not {1}: {2!r}".format(
                    len(cells), len(TABLE_HEADER), line
                )
            )
        rows.append(cells)
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
        return {
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
            "Corpus — four-field exact (development)": fraction(
                self.corpus.exact_matches, self.corpus.total
            ),
            "Second set — four-field exact (development)": fraction(
                self.codex.exact_matches, self.codex.total
            ),
            "Ablation — admissibility precheck removed, both sets": fraction(*self.admissibility),
            "Ablation — admissibility removed, case 112": self.case_112,
            "Ablation — clause notes removed, both sets": fraction(*self.clause_notes),
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
            "Sample case 901 — under the current pipeline": self.sample_ruling,
            "Sample case 901 — the organisers' stated expectation": self.sample_expectation,
        }

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

    def _verifier_switch(self) -> str:
        for run_dir in SCORED_RUN_DIRS:
            run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            configuration = run.get("configuration")
            if isinstance(configuration, Mapping) and configuration.get("verify_drafts"):
                raise AssertionError(
                    "{0} ran with the draft verifier on".format(
                        run_dir.relative_to(PROJECT_ROOT)
                    )
                )
        return "off, in all {0}".format(len(SCORED_RUN_DIRS))

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
