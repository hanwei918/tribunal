"""The two breakdowns part 59 appends to the fairness report, read off the report.

``python3 -m eval.fairness --report`` printed sections 0 to 3; part 59 appends a
fourth and a fifth, splitting the same errors by ``dispute.category`` and by
``dispute.amount_contested_sgd`` in three bands. This module reads the report's
own text and holds it to four things:

* the categories partition each run's cases, and so do the bands: the blocks of
  a run cover its cases once each, and their sizes sum to its case count;
* per run, the blocks' error counts sum to section 1's totals for that run,
  direction by direction -- the two readings cannot disagree, because both go
  through ``error_lean``;
* a case that differs from the key appears in exactly one category block and in
  exactly one band block;
* sections 0 to 3 are unchanged and still in order, with 4 and 5 after them.

The control changes one case's produced ruling in a copy of the graded report
and shows that case's category block gains exactly one error.

**What it reads.** The report is computed once (``fairness.report()``), the way
``--report`` computes it, and parsed as text. No model call is made and no
network is reached, and nothing here writes.

Run from the project root with::

    python -m unittest discover -s tests
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import fairness, grade  # noqa: E402

# The report's headings, in the order it prints them. The first is not numbered.
HEADINGS: Tuple[str, ...] = (
    "== Why not by who filed ==",
    "== 1. Which way the errors lean ==",
    "== 2. The position swap ==",
    "== 3. Calibration ==",
    "== 4. By category ==",
    "== 5. By the contested amount ==",
)
LEAN_HEADING = "== 1. Which way the errors lean =="
CATEGORY_HEADING = "== 4. By category =="
BAND_HEADING = "== 5. By the contested amount =="

# A group header and a direction row, exactly as ``_error_lean_block`` writes
# them. The amount-move lines under a direction row are indented five spaces and
# so match neither pattern.
GROUP_RE = re.compile(
    r"^-- (?P<label>.+): (?P<differing>\d+) of (?P<total>\d+) differ from the key$"
)
DIRECTION_RE = re.compile(
    r"^   (?P<direction>{0})\s+(?P<count>\d+)\s+(?P<cases>.*)$".format(
        "|".join(sorted(fairness.DIRECTIONS, key=len, reverse=True))
    )
)


def sections(text: str) -> List[Tuple[str, List[str]]]:
    """The report split into its headings and the lines under each, in order."""
    found: List[Tuple[str, List[str]]] = []
    for line in text.splitlines():
        if line.startswith("== ") and line.endswith(" =="):
            found.append((line, []))
        elif found:
            found[-1][1].append(line)
    return found


def section(text: str, heading: str) -> List[str]:
    """One section's lines, refused when the report carries no such section."""
    for name, body in sections(text):
        if name == heading:
            return body
    raise AssertionError("the report carries no {0!r} section".format(heading))


def cases_named(text: str) -> Tuple[int, ...]:
    """The case numbers a direction row names, as ``_named`` writes them."""
    stripped = text.strip()
    if stripped == "none":
        return ()
    parts = [part.strip() for part in stripped.split(",")]
    numbers: List[str] = []
    for index, part in enumerate(parts):
        if index == len(parts) - 1 and " and " in part:
            numbers.extend(part.split(" and "))
        else:
            numbers.append(part)
    return tuple(int(number) for number in numbers if number)


def blocks(body: Sequence[str]) -> List[Dict[str, Any]]:
    """One section's group blocks: its label, its counts and each direction's cases."""
    found: List[Dict[str, Any]] = []
    for line in body:
        header = GROUP_RE.match(line)
        if header:
            found.append(
                {
                    "label": header.group("label"),
                    "differing": int(header.group("differing")),
                    "total": int(header.group("total")),
                    "directions": {},
                }
            )
            continue
        row = DIRECTION_RE.match(line)
        if row is not None and found:
            found[-1]["directions"][row.group("direction")] = (
                int(row.group("count")),
                cases_named(row.group("cases")),
            )
    return found


def blocks_for(found: Sequence[Dict[str, Any]], run: str) -> List[Dict[str, Any]]:
    """The blocks of one run, which a breakdown labels ``<run>, <value>``."""
    prefix = run + ", "
    return [block for block in found if block["label"].startswith(prefix)]


class TheBreakdownSectionsTests(unittest.TestCase):
    """Sections 4 and 5, read out of the report the command prints."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = fairness.report()
        cls.lean = blocks(section(cls.text, LEAN_HEADING))
        cls.category = blocks(section(cls.text, CATEGORY_HEADING))
        cls.band = blocks(section(cls.text, BAND_HEADING))
        cls.runs = tuple(fairness.MEASURED_SETS) + ("both runs",)

    def lean_block(self, run: str) -> Dict[str, Any]:
        """Section 1's own block for one run."""
        found = [block for block in self.lean if block["label"] == run]
        self.assertEqual(1, len(found), "section 1 has no single {0} block".format(run))
        return found[0]

    def test_the_five_sections_are_there_in_order_and_sections_0_to_3_did_not_move(self):
        self.assertEqual(list(HEADINGS), [name for name, _body in sections(self.text)])
        self.assertLess(
            self.text.index("== 3. Calibration =="),
            self.text.index("== 4. By category =="),
        )
        self.assertLess(
            self.text.index("== 4. By category =="),
            self.text.index("== 5. By the contested amount =="),
        )

    def test_the_categories_partition_every_runs_cases(self):
        for run in self.runs:
            with self.subTest(run=run):
                chosen = blocks_for(self.category, run)
                self.assertEqual(
                    len(fairness.CATEGORIES),
                    len(chosen),
                    "the {0} blocks are not one per category".format(run),
                )
                self.assertEqual(
                    self.lean_block(run)["total"],
                    sum(block["total"] for block in chosen),
                    "the {0} category blocks do not sum to its case count".format(run),
                )

    def test_the_bands_partition_every_runs_cases(self):
        for run in self.runs:
            with self.subTest(run=run):
                chosen = blocks_for(self.band, run)
                self.assertEqual(
                    len(fairness.BANDS),
                    len(chosen),
                    "the {0} blocks are not one per band".format(run),
                )
                self.assertEqual(
                    self.lean_block(run)["total"],
                    sum(block["total"] for block in chosen),
                    "the {0} band blocks do not sum to its case count".format(run),
                )

    def test_the_blocks_error_counts_sum_to_section_1_direction_by_direction(self):
        for label, found in (("category", self.category), ("band", self.band)):
            for run in self.runs:
                reference = self.lean_block(run)
                chosen = blocks_for(found, run)
                with self.subTest(breakdown=label, run=run):
                    self.assertEqual(
                        reference["differing"],
                        sum(block["differing"] for block in chosen),
                        "the {0} blocks of {1} do not sum to section 1".format(
                            label, run
                        ),
                    )
                    for direction in fairness.DIRECTIONS:
                        self.assertEqual(
                            reference["directions"][direction][0],
                            sum(
                                block["directions"][direction][0] for block in chosen
                            ),
                            "{0} of {1} does not sum to section 1".format(
                                direction, run
                            ),
                        )

    def test_a_differing_case_is_in_exactly_one_category_block_and_one_band_block(self):
        for run in self.runs:
            reference = self.lean_block(run)
            expected = {
                case_no
                for direction in fairness.DIRECTIONS
                for case_no in reference["directions"][direction][1]
            }
            for label, found in (("category", self.category), ("band", self.band)):
                seen: List[int] = [
                    case_no
                    for block in blocks_for(found, run)
                    for direction in fairness.DIRECTIONS
                    for case_no in block["directions"][direction][1]
                ]
                with self.subTest(breakdown=label, run=run):
                    self.assertEqual(
                        sorted(expected),
                        sorted(seen),
                        "the {0} blocks of {1} do not carry each differing case".format(
                            label, run
                        ),
                    )
                    self.assertEqual(
                        len(seen),
                        len(set(seen)),
                        "a differing case of {0} is in more than one {1} block".format(
                            run, label
                        ),
                    )


class TheControlTests(unittest.TestCase):
    """One changed ruling moves one category block's error count by exactly one."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = fairness.graded_report(fairness.measured_run(fairness.CORPUS))
        facts = fairness.case_facts(fairness.CORPUS)
        cls.categories = {
            case_no: category for case_no, (category, _amount) in facts.items()
        }

    def _counts(self, report: grade.GradeReport) -> Dict[str, int]:
        return {
            group.label: group.lean.count(fairness.TO_ESCALATION)
            for group in fairness.groups_over(
                report, self.categories, fairness.CATEGORIES, fairness.CORPUS
            )
        }

    def test_one_changed_ruling_moves_its_category_by_one(self):
        matching = [
            score
            for score in self.report.cases
            if score.exact and not score.expected_escalates
        ]
        self.assertTrue(
            matching,
            "the corpus has no exactly-matched non-escalation case to change",
        )
        score = matching[0]
        produced = grade.produced_from_mapping(
            {
                "ruling": {
                    "ruling": grade.ESCALATE,
                    "amount_sgd": None,
                    "driver_compensation_sgd": None,
                    "confidence": None,
                    "referrals": [],
                }
            },
            score.case_no,
        )
        changed_score = grade.score_case(
            score.case_no, score.expected, produced, facts=score.facts
        )
        changed_cases = tuple(
            changed_score if item.case_no == score.case_no else item
            for item in self.report.cases
        )
        changed = grade.GradeReport(
            cases=changed_cases, calibration=grade.calibrate(changed_cases)
        )

        before = self._counts(self.report)
        after = self._counts(changed)
        label = "{0}, {1}".format(fairness.CORPUS, self.categories[score.case_no])
        self.assertEqual(
            before[label] + 1,
            after[label],
            "case {0}'s own category block did not gain exactly one error".format(
                score.case_no
            ),
        )
        for other, count in before.items():
            if other == label:
                continue
            self.assertEqual(
                count,
                after[other],
                "{0} moved when only one case of {1} changed".format(other, label),
            )


if __name__ == "__main__":
    unittest.main()
