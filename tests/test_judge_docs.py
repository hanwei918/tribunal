"""The documents a judge asks for, and where every figure in them comes from.

Part 55 adds six documents that answer questions a judging panel asks rather
than questions the repository asks itself: why a debate at all, where the build
departs from the brief, what one account can carry and what a month costs, how
Ryde would plug the system in, what is synthetic and how real data may differ,
and a three-minute demo script. A document like that is worth something only if
its figures can be traced, so this module holds the four things that would
otherwise go unchecked:

* **Every new document exists, and the README's Documentation table links it.**
  A document nothing points at is a document nobody reads.
* **Every relative link inside them resolves.** A path that resolves nowhere
  reads as a citation and is not one.
* **Every number in the demo script, in ``scale.md``'s 1,000-case paragraph and
  in the description's new pain-point table is in a report command's output or
  in ``docs/record.md``.** The four commands are run here and their output is
  read, rather than the figures being restated in this module: a second copy of
  a figure is a copy that can agree with itself while disagreeing with the
  repository. ``scale.md``'s monthly cost table is deliberately **not** covered
  -- it is arithmetic over three assumed volumes and says so -- and neither is
  the rest of the new documents, whose figures are read from the run directories
  and named beside them.
* **``why-debate.md`` names one paper and no other**, and **no new document
  calls the corpus "official"**.

**The number check is shown capable of failing**, on a fabricated figure, for the
reason ``START-HERE.md`` gives: a guard nobody has seen fail is not evidence of
anything.

No model call is made and no network is reached. The four report commands are
read-only, and each of them says so in its own output. Run from the project root
with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

README = PROJECT_ROOT / "README.md"
RECORD = PROJECT_ROOT / "docs" / "record.md"
DESCRIPTION = PROJECT_ROOT / "docs" / "submission" / "description.md"

# The six documents part 55 adds, each named by the path the README links.
NEW_DOCUMENTS: Tuple[str, ...] = (
    "docs/why-debate.md",
    "docs/design-choices.md",
    "docs/scale.md",
    "docs/integration.md",
    "docs/data.md",
    "docs/submission/demo-script.md",
)

# The report commands a figure may be read from, in the order the sheet names
# them. Each is run with ``--report`` and makes no model call.
REPORT_COMMANDS: Tuple[Tuple[str, ...], ...] = (
    ("eval.business_value", "--report"),
    ("eval.v6_runs", "--report"),
    ("eval.fairness", "--report"),
    ("eval.func_sets", "--report"),
)

# The README's Documentation table, located by its header rather than by
# position, so a table that moves is still found.
DOCUMENTATION_HEADER: Tuple[str, str] = ("document", "what's covered")

# The heading that opens ``scale.md``'s 1,000-case paragraph, and the line that
# opens the description's new table and the one that closes it.
THOUSAND_CASE_HEADING = "## 1,000 cases in figures"
PAIN_POINT_OPENING = "**The brief's four pain points"
PAIN_POINT_CLOSING = "**The sealed sets.**"

LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
DIGITS = re.compile(r"\d+")
ARXIV = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})")

# A figure that appears in no report and in no line of the record, for the
# control below.
FABRICATED = "424242"


# --------------------------------------------------------------------------
# Reading the documents
# --------------------------------------------------------------------------
def text_of(relative: str) -> str:
    """One repository-relative file, read as text."""
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def relative_links(text: str) -> List[str]:
    """Every markdown link target in a document that is not an absolute URL."""
    targets: List[str] = []
    for _label, target in LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:")) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if path:
            targets.append(target)
    return targets


def documentation_rows() -> List[List[str]]:
    """The README's Documentation table, as lists of cells.

    Located by its header rather than by position, and read until the first line
    that is not a table row, so a row added above or below it is still found.
    """
    lines = README.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if tuple(cell.lower() for cell in cells) == DOCUMENTATION_HEADER:
            rows: List[List[str]] = []
            for row in lines[index + 2 :]:
                if not row.strip().startswith("|"):
                    break
                rows.append([cell.strip() for cell in row.strip().strip("|").split("|")])
            return rows
    raise AssertionError(
        "README.md has no Documentation table headed {0}".format(" | ".join(DOCUMENTATION_HEADER))
    )


def thousand_case_paragraph() -> str:
    """``scale.md``'s 1,000-case section, heading included, to the next heading."""
    text = text_of("docs/scale.md")
    start = text.index(THOUSAND_CASE_HEADING)
    rest = text[start:]
    following = rest.find("\n## ", 1)
    return rest if following == -1 else rest[:following]


def pain_point_table() -> str:
    """The description's new table, from its opening line to the sealed sets."""
    text = text_of("docs/submission/description.md")
    start = text.index(PAIN_POINT_OPENING)
    return text[start : text.index(PAIN_POINT_CLOSING, start)]


# --------------------------------------------------------------------------
# Where a figure may come from
# --------------------------------------------------------------------------
_REPORT_OUTPUT: List[str] = []


def report_output() -> str:
    """The four report commands' own output, read once per test run.

    A subprocess per command rather than an import, because the sheet names a
    *command's output* and because the output is what a reader would see. No
    model call is made and no network is reached; each command says so itself.
    """
    if not _REPORT_OUTPUT:
        chunks: List[str] = []
        for command in REPORT_COMMANDS:
            result = subprocess.run(
                [sys.executable, "-m", *command],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise AssertionError(
                    "{0} exited {1}: {2}".format(
                        " ".join(command), result.returncode, result.stderr.strip()
                    )
                )
            chunks.append(result.stdout)
        _REPORT_OUTPUT.append("\n".join(chunks))
    return _REPORT_OUTPUT[0]


def digit_runs(text: str) -> Set[str]:
    """Every run of digits in a text, with leading zeros removed.

    ``01779`` is the page for case 1779, and ``0.0579`` is the runs ``0`` and
    ``0579``; a leading zero is padding rather than a figure, so ``01779`` and
    ``1779`` are the same number here and a run that is all zeros stays ``0``.
    """
    return {run.lstrip("0") or "0" for run in DIGITS.findall(text)}


def sourced_numbers() -> Set[str]:
    """Every number a figure in these documents may be read from."""
    return digit_runs(report_output()) | digit_runs(RECORD.read_text(encoding="utf-8"))


def unsourced(text: str, sourced: Set[str]) -> List[str]:
    """The numbers in a text that no report and no line of the record carries."""
    return sorted(run for run in digit_runs(text) if run not in sourced)


# --------------------------------------------------------------------------
# The documents themselves
# --------------------------------------------------------------------------
class TheNewDocumentsTests(unittest.TestCase):
    """The six documents, and what the README must say about each."""

    def test_each_one_exists_and_the_readme_links_it_once(self):
        targets = [
            target
            for row in documentation_rows()
            for target in relative_links(row[0])
        ]
        for name in NEW_DOCUMENTS:
            with self.subTest(document=name):
                self.assertTrue(
                    (PROJECT_ROOT / name).is_file(),
                    "{0} does not exist".format(name),
                )
                self.assertEqual(
                    1,
                    targets.count(name),
                    "the README's Documentation table links {0!r} {1} time(s)".format(
                        name, targets.count(name)
                    ),
                )

    def test_every_relative_link_in_them_resolves(self):
        for name in NEW_DOCUMENTS:
            document = PROJECT_ROOT / name
            for target in relative_links(document.read_text(encoding="utf-8")):
                with self.subTest(document=name, link=target):
                    self.assertTrue(
                        (document.parent / target.split("#", 1)[0]).resolve().exists(),
                        "{0} links {1!r}, which resolves nowhere".format(name, target),
                    )

    def test_no_new_document_calls_the_corpus_official(self):
        """The stronger form of the rule: the word is absent, not qualified.

        The corpus is this team's own work, written against the organisers'
        brief, and calling it "official" anywhere would be a claim about where it
        came from that is not true. The check is the whole word rather than the
        phrase, so a sentence cannot smuggle it in beside the word "corpus".
        """
        for name in NEW_DOCUMENTS:
            with self.subTest(document=name):
                self.assertNotIn(
                    "official",
                    text_of(name).lower(),
                    "{0} calls something official".format(name),
                )


class TheReferenceTests(unittest.TestCase):
    """``why-debate.md``'s one citation, and no second one."""

    def test_it_names_the_paper_and_no_other_arxiv_id(self):
        found = ARXIV.findall(text_of("docs/why-debate.md"))
        self.assertEqual(
            ["2402.06782"],
            found,
            "why-debate.md names {0!r} rather than the one paper".format(found),
        )


class TheSourcedFiguresTests(unittest.TestCase):
    """Every number in the three places the sheet names, traced to its source."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sourced = sourced_numbers()

    def test_the_demo_script_states_only_sourced_numbers(self):
        self.assertEqual(
            [],
            unsourced(text_of("docs/submission/demo-script.md"), self.sourced),
        )

    def test_the_thousand_case_paragraph_states_only_sourced_numbers(self):
        self.assertEqual([], unsourced(thousand_case_paragraph(), self.sourced))

    def test_the_descriptions_new_table_states_only_sourced_numbers(self):
        self.assertEqual([], unsourced(pain_point_table(), self.sourced))

    def test_the_source_really_carries_the_figures_it_is_asked_about(self):
        """The control: the check is against text that is there, not a blank."""
        output = report_output()
        self.assertIn("160.4", output)
        self.assertIn("136/141", output)
        self.assertIn("0.0579", RECORD.read_text(encoding="utf-8"))
        self.assertIn("24 to 72 hours", RECORD.read_text(encoding="utf-8"))

    def test_a_fabricated_number_is_reported(self):
        """The check above is shown capable of failing."""
        self.assertNotIn(FABRICATED, self.sourced)
        self.assertEqual(
            [FABRICATED],
            unsourced("the cost is {0} USD a case".format(FABRICATED), self.sourced),
        )


if __name__ == "__main__":
    unittest.main()
