"""The note that reads the third sealed set's single run, and its interval.

``docs/notes/2026-10-10-the-third-sealed-run.md`` states three sealed figures
with an interval each -- ``sealed-v1``'s 21/24, ``wild-v2``'s 18/20 and
``wild-v1``'s 55/64 -- and says the three are never summed or pooled. A
hand-computed interval is a number nobody can check, so this module recomputes
all three from the committed runs and compares them with what the note states:
**no bound in the note is typed into this module**, and a bound that drifts fails
here rather than reading as a measurement.

The denominator is the set's own case list, not the count that produced a ruling.
That is the honest denominator for a generalisation figure -- a case the system
could not decide is not a case it decided correctly -- and it is what makes
``wild-v1``'s 55/62 into the 55/64 the note reports.

The note's ``sealed_report`` block is compared with the command's own output, and
its three misses are read out of the run and the key: each miss's key ruling, its
produced ruling, and the four draft rows the note states.

Prose is compared as whitespace-normalised text -- the note wraps its lines, and a
sentence that reads the same at any column is the same sentence -- while the table
rows are compared whole, because a table row is one line by construction.

**No model call is made.** Every reading is a committed run and a frozen key.
"""

from __future__ import annotations

import json
import math
import re
import sys
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark, sealed_report  # noqa: E402

NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-10-the-third-sealed-run.md"

MODEL = run_benchmark.resolve_model(None)
SET = development_sets.named("sealed-v1")

# The two-sided 95% normal quantile. It is a literal because it *is* the "95%",
# not a measurement: what is measured is the interval it produces.
Z_95 = 1.959963984540054

# Every "N.NNN to N.NNN" interval string the note states must be one of the three
# this module computes.
INTERVAL_PATTERN = re.compile(r"\d+\.\d{3} to \d+\.\d{3}")

# The three sealed sets the note's interval table states, in the note's own order.
INTERVAL_SETS = (
    ("sealed-v1", "`sealed-v1` (this run)"),
    ("wild-v2", "`wild-v2` (the second sealed set)"),
    ("wild", "`wild-v1` (the held-out set)"),
)

# The three misses, and the cause the note gives each, as the note's own
# sentence. The words are the version-6 note's vocabulary: split, no valid draft
# and missed trigger.
MISSES = ((304, "a split"), (312, "no valid draft"), (410, "a missed trigger"))


def prose(text: str) -> str:
    """The note's text with every run of whitespace collapsed to one space."""
    return " ".join(text.split())


def wilson_interval(successes: int, total: int, z: float = Z_95) -> Tuple[float, float]:
    """The Wilson score interval for a binomial proportion, as ``(low, high)``.

    The score interval rather than the normal approximation, because at n = 20
    the normal approximation runs outside the unit interval at the edges and is
    not what a figure this small should be quoted with.

    **Both bounds are clamped, to the unit interval and to the estimate.** The
    interval always contains the estimate and always lies in ``[0, 1]``, but the
    arithmetic leaves a rounding residue at the two edges: ``0 of 24`` computes a
    lower bound of about 1.4e-17 rather than 0, and ``24 of 24`` an upper bound
    just under 1. A bound outside the range a proportion can take, or on the
    wrong side of the estimate, is a rounding artefact rather than a finding, so
    the clamp is what makes the edge cases exact.
    """
    if total <= 0:
        raise ValueError("a proportion needs a positive denominator")
    if not 0 <= successes <= total:
        raise ValueError("a count outside 0..total is not a proportion")
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    half = (z / denominator) * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return (
        max(0.0, min(centre - half, proportion)),
        min(1.0, max(centre + half, proportion)),
    )


def three_places(value: float) -> str:
    """A bound as the note states it: three decimal places."""
    return "{0:.3f}".format(value)


def interval_string(successes: int, total: int) -> str:
    """The interval exactly as the note states it: ``0.690 to 0.957``."""
    low, high = wilson_interval(successes, total)
    return "{0} to {1}".format(three_places(low), three_places(high))


def interval_row(label: str, successes: int, total: int) -> str:
    """The whole table row, built from the counts rather than transcribed."""
    return "| {0} | {1}/{2} = {3}% | **{4}** |".format(
        label,
        successes,
        total,
        "{0:.1f}".format(100.0 * successes / total),
        interval_string(successes, total),
    )


def graded(set_name: str):
    """One committed sealed run, graded against its own frozen key."""
    development_set = development_sets.named(set_name)
    return run_benchmark.grade_run(
        development_set.run_dir(MODEL),
        development_set.key(),
        case_loader=development_set.load_case,
    )


def transcript_of(case_no: int) -> Mapping[str, Any]:
    return json.loads(
        Path(run_benchmark.transcript_path(SET.run_dir(MODEL), case_no)).read_text(
            encoding="utf-8"
        )
    )


def vote_of(case_no: int) -> Mapping[str, Any]:
    return transcript_of(case_no)["vote"]


def drafts_of(case_no: int) -> Dict[int, Mapping[str, Any]]:
    return {draft["draft"]: draft for draft in vote_of(case_no)["drafts"]}


def produced_ruling(case_no: int) -> Any:
    document = run_benchmark.load_cached(SET.run_dir(MODEL), case_no)
    return document["ruling"]["ruling"]["ruling"]


def vote_row(draft: Mapping[str, Any]) -> str:
    """One row of the note's draft tables, built from the vote.

    A valid draft renders its ruling and, when it proposed money, the amount to
    two decimals; an abstaining draft renders the figure its abstention names, or
    a dash where the abstention names none.
    """
    if draft["valid"]:
        inner = draft["proposal"]
        amount = inner.get("amount_sgd")
        proposed = (
            "`{0}`".format(inner["ruling"])
            if amount is None
            else "`{0}` {1:.2f}".format(inner["ruling"], Decimal(str(amount)))
        )
        abstention = "\u2014"
    else:
        match = re.search(r"amount_sgd=(\S+)", draft["abstention"])
        proposed = "\u2014" if match is None else "`amount_sgd` {0}".format(match.group(1))
        abstention = "`{0}`".format(draft["abstention"].split(":")[0])
    return "| {0} | {1} | {2} | {3} |".format(
        draft["draft"], draft["kind"].replace("_", "-"), proposed, abstention
    )


def the_notes_report_block(text: str) -> List[str]:
    """The note's one fenced block, as its non-blank lines."""
    blocks = re.findall(r"```\n(.*?)```", text, re.DOTALL)
    if len(blocks) != 1:
        raise AssertionError(
            "the note carries {0} fenced blocks, not one".format(len(blocks))
        )
    return [line for line in blocks[0].splitlines() if line.strip()]


def sealed_report_lines() -> List[str]:
    """The sealed report's own output, as its non-blank lines."""
    return [
        line for line in sealed_report.render(SET, MODEL).splitlines() if line.strip()
    ]


class WilsonFormulaTests(unittest.TestCase):
    """The formula, on facts a wrong one would get wrong."""

    def test_the_interval_contains_the_estimate(self):
        for successes, total in ((21, 24), (18, 20), (55, 64), (0, 24), (24, 24)):
            with self.subTest(successes=successes, total=total):
                low, high = wilson_interval(successes, total)
                self.assertLessEqual(low, successes / total)
                self.assertGreaterEqual(high, successes / total)

    def test_the_interval_stays_inside_the_unit_interval(self):
        for successes, total in ((1, 20), (2, 20), (18, 20), (19, 20)):
            with self.subTest(successes=successes, total=total):
                low, high = wilson_interval(successes, total)
                self.assertGreater(low, 0.0)
                self.assertLess(high, 1.0)

    def test_more_cases_narrow_the_interval_at_the_same_proportion(self):
        narrow = wilson_interval(900, 1000)
        wide = wilson_interval(9, 10)
        self.assertLess(narrow[1] - narrow[0], wide[1] - wide[0])

    def test_it_approaches_the_normal_approximation_as_the_sample_grows(self):
        successes, total = 900_000, 1_000_000
        proportion = successes / total
        half = Z_95 * math.sqrt(proportion * (1 - proportion) / total)
        low, high = wilson_interval(successes, total)
        self.assertAlmostEqual(proportion - half, low, places=5)
        self.assertAlmostEqual(proportion + half, high, places=5)


class TheNotesIntervalsTests(unittest.TestCase):
    """The note's three intervals, recomputed from the committed runs."""

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.prose = prose(cls.text)
        cls.reports = {name: graded(name) for name, _label in INTERVAL_SETS}
        cls.totals = {
            name: len(development_sets.named(name).cases)
            for name, _label in INTERVAL_SETS
        }
        cls.rows = tuple(
            interval_row(
                label, cls.reports[name].exact_matches, cls.totals[name]
            )
            for name, label in INTERVAL_SETS
        )
        cls.interval_strings = tuple(
            interval_string(
                cls.reports[name].exact_matches, cls.totals[name]
            )
            for name, _label in INTERVAL_SETS
        )

    def test_the_three_figures_are_the_committed_runs(self):
        self.assertEqual(21, self.reports["sealed-v1"].exact_matches)
        self.assertEqual(24, self.totals["sealed-v1"])
        self.assertEqual(18, self.reports["wild-v2"].exact_matches)
        self.assertEqual(20, self.totals["wild-v2"])
        self.assertEqual(55, self.reports["wild"].exact_matches)
        self.assertEqual(64, self.totals["wild"])

    def test_the_note_states_all_three_interval_rows_exactly(self):
        """Each whole row, built from the counts rather than transcribed."""
        for row in self.rows:
            with self.subTest(row=row):
                self.assertIn(
                    row,
                    self.text,
                    "the note does not state this row, built from the counts",
                )
        self.assertEqual(3, len(set(self.rows)), "two interval rows are the same row")

    def test_every_interval_string_in_the_note_is_one_of_the_computed_intervals(self):
        found = set(INTERVAL_PATTERN.findall(self.text))
        self.assertTrue(found, "the note states no interval")
        self.assertEqual(
            set(self.interval_strings),
            found,
            "the note states an interval that is not one of the three computed ones",
        )

    def test_the_note_says_the_three_figures_are_never_summed_or_pooled(self):
        self.assertIn("never summed or pooled", self.prose)
        self.assertIn("not a measurement of 108 cases", self.prose)

    def test_the_note_names_all_three_freezes(self):
        self.assertIn("freeze-2026-10-09", self.prose)
        self.assertIn("freeze-2026-10-03", self.prose)
        self.assertIn("freeze-2026-09-30", self.prose)


class TheNotesReportBlockTests(unittest.TestCase):
    """The note's ``sealed_report`` block, against the command's own output."""

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.rendered = sealed_report_lines()

    def test_the_notes_report_block_is_the_commands_output(self):
        """Whole, line for line."""
        self.assertEqual(self.rendered, the_notes_report_block(self.text))


class TheNotesFiguresTests(unittest.TestCase):
    """The four-field table, the per-category table and k-consistency."""

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.report = graded("sealed-v1")
        cls.categories = sealed_report._categories(SET)

    def test_the_four_field_rows_are_the_graders_own_counts(self):
        """Each field's cell, built from ``field_tally`` rather than transcribed."""
        rows = [
            "| four-field exact | {0}/{1} |".format(
                self.report.exact_matches, self.report.total
            )
        ]
        for field in ("ruling", "amount_sgd", "driver_compensation_sgd", "referrals"):
            matched, total = self.report.field_tally(field)
            rows.append("| {0} | {1}/{2} |".format(field, matched, total))
        for row in rows:
            with self.subTest(row=row):
                self.assertIn(row, self.text, "the note does not state this row")

    def test_the_per_category_rows_are_the_sets_own_categories(self):
        for name in ("NO_SHOW_CHARGE", "ROUTE_DEVIATION"):
            in_set = sorted(
                case_no for case_no, category in self.categories.items() if category == name
            )
            exact, total = sealed_report._exact_among(self.report, in_set)
            ruling, _ = sealed_report._ruling_among(self.report, in_set)
            row = "| `{0}` | {1} | {2}/{3} | {4}/{3} |".format(
                name, len(in_set), exact, total, ruling
            )
            with self.subTest(row=row):
                self.assertIn(row, self.text, "the note does not state this row")

    def test_the_k_consistency_rows_are_the_votes_own_agreements(self):
        """The agreement among the four votes, bucketed from the transcripts."""
        agreements = {
            case_no: vote_of(case_no).get("agreement") for case_no in SET.cases
        }
        counts = Counter(agreements.values())
        cases = {
            value: sorted(n for n, a in agreements.items() if a == value)
            for value in counts
        }

        def named(numbers: Sequence[int]) -> str:
            return ", ".join(str(number) for number in numbers)

        rows = [
            "| 1.00 \u2014 all four agreed | {0} |".format(counts[1.0]),
            "| 0.75 \u2014 three of four ({0}) | {1} |".format(
                named(cases[0.75]), counts[0.75]
            ),
            "| 0.50 \u2014 two of four ({0}) | {1} |".format(
                named(cases[0.5]), counts[0.5]
            ),
            "| none \u2014 no valid draft ({0}) | {1} |".format(
                named(cases[None]), counts[None]
            ),
        ]
        self.assertEqual({1.0: 21, 0.75: 1, 0.5: 1, None: 1}, dict(counts))
        for row in rows:
            with self.subTest(row=row):
                self.assertIn(row, self.text, "the note does not state this row")


class TheNotesThreeMissesTests(unittest.TestCase):
    """The three misses: the key, the produced ruling, the drafts and the cause."""

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.prose = prose(cls.text)
        cls.key = SET.key()

    def test_each_miss_is_a_case_the_key_and_the_run_disagree_on(self):
        for case_no, _cause in MISSES:
            with self.subTest(case_no=case_no):
                score = next(
                    item for item in graded("sealed-v1").failures if item.case_no == case_no
                )
                self.assertFalse(score.exact, "{0} is not a miss".format(case_no))

    def test_the_key_and_the_produced_rulings_are_what_the_note_states(self):
        produced = {case_no: produced_ruling(case_no) for case_no, _ in MISSES}
        self.assertEqual("PARTIAL_REFUND", self.key[304].ruling)
        self.assertEqual("ESCALATE", produced[304])
        self.assertEqual("PARTIAL_REFUND", self.key[312].ruling)
        self.assertEqual("ESCALATE", produced[312])
        self.assertEqual("ESCALATE", self.key[410].ruling)
        self.assertEqual("FULL_REFUND", produced[410])
        self.assertIn("**Key:** `PARTIAL_REFUND` 1.00. **Produced:** `ESCALATE`", self.prose)
        self.assertIn("**Key:** `PARTIAL_REFUND` 4.10. **Produced:** `ESCALATE`", self.prose)
        self.assertIn("**Key:** `ESCALATE`", self.prose)
        self.assertIn("**Produced:** `FULL_REFUND` 4.00", self.prose)

    def test_each_miss_carries_the_cause_the_note_gives_it(self):
        for case_no, cause in MISSES:
            with self.subTest(case_no=case_no):
                self.assertIn("**The cause is {0}.".format(cause), self.prose)

    def test_the_notes_draft_rows_are_the_votes_rows(self):
        """Each whole row, built from the vote rather than transcribed."""
        for case_no, _cause in MISSES:
            with self.subTest(case_no=case_no):
                rows = [vote_row(draft) for draft in vote_of(case_no)["drafts"]]
                self.assertEqual(4, len(rows))
                self.assertEqual(4, len(set(rows)), "two rows are the same row")
                for row in rows:
                    self.assertIn(
                        row,
                        self.text,
                        "the note does not state this row, built from the vote",
                    )


if __name__ == "__main__":
    unittest.main()
