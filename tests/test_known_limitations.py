"""The last gaps: what the code does not do, and the page that reads it.

Part 43 changes documents only -- ``tribunal/``, ``prompts/`` and ``policy/``
are frozen for the submission -- so the four weaknesses an independent review
confirmed on 2026-10-11 are written down rather than fixed. Writing them down is
worth something only if a later edit cannot quietly drop one, so this module
holds the writing down to what it claims:

* **the same four limitations are in both documents they must be in** -- the
  README's *Limitations and disclosures* and the threat model's *Known
  limitations of the code* -- each pinned by the sentence it opens with;
* **the README opens with a Start here list**, it is short, it sits above the
  results, and it names the live demo, the two case pages, the submission texts,
  the architecture, the results, the build page and the limitations;
* **``docs/submission/how-we-built-it.md`` exists** and carries the workflow and
  the four tips, and the session and commit counts it states are the
  repository's own at the commit it names them at;
* **the four labels the diagram moved are where the fix put them**, and the two
  that moved clear of the middle column are outside it.

**The limitation check is shown to be capable of failing**, on a copy of the
README with one limitation taken out, for the reason ``START-HERE.md`` gives: a
guard nobody has seen fail is not evidence of anything.

No test here makes a model call, opens a run directory, or reads a sealed set.
The counts are read from the repository's own git history and skip, naming why,
when there is none -- a zip download has no history to read.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402

README = PROJECT_ROOT / "README.md"
THREAT_MODEL = PROJECT_ROOT / "docs" / "governance" / "threat-model.md"
HOW_WE_BUILT_IT = PROJECT_ROOT / "docs" / "submission" / "how-we-built-it.md"
DIAGRAM = PROJECT_ROOT / "docs" / "architecture.svg"

# The four weaknesses the review confirmed. Each is disclosed in both documents,
# and the phrase below is the opening of its own sentence there, so a bullet that
# is dropped -- or reworded away from the point it makes -- is reported instead
# of passing on a neighbouring word.
LIMITATIONS: Tuple[str, ...] = (
    "The confidence floor fails open",
    "No retry on a transport error",
    "A case whose pipeline fails is not queued for a person",
    "The default policy version is 1",
)

# The commit the how-we-built-it page states its counts at, and the two numbers
# it states. Both are recomputed below from the history itself.
COUNTS_COMMIT = "2731adc"
STATED_COMMITS = 324
STATED_SESSIONS = 187

# The four labels the diagram moved, and where the fix put them. Each number was
# chosen against a rendering: "same artifacts" and "case file" were crossed by a
# box border, "yes" by the step-10 box's bottom edge, and "approved" by the
# Policy versions cylinder's top. The two right-hand ones are now outside the
# middle column, whose borders span x 400 to 910.
MOVED_LABELS: Dict[str, Tuple[float, float]] = {
    "same artifacts": (916.0, 192.0),
    "yes": (364.0, 861.0),
    "case file": (916.0, 910.0),
    "approved": (1500.0, 310.0),
}

# The x range every box of the middle column spans.
MIDDLE_COLUMN_LEFT = 400.0
MIDDLE_COLUMN_RIGHT = 910.0


def read(path: Path) -> str:
    """A document's bytes, read as text."""
    return path.read_text(encoding="utf-8")


def prose(path: Path) -> str:
    """A document's prose with every run of whitespace collapsed to one space.

    The phrases below are pinned against the sentences a reader reads, and not
    against where a line happens to break: a later rewrapping of a paragraph
    must not be reported as a limitation that has gone.
    """
    return " ".join(read(path).split())


def missing_limitations(text: str) -> List[str]:
    """The limitations a document does not disclose, in the order above."""
    return [phrase for phrase in LIMITATIONS if phrase not in text]


def svg_texts(text: str) -> List[Tuple[str, float, float]]:
    """``[(content, x, y), ...]`` for every placed ``<text>`` in the diagram."""
    root = ET.fromstring(text)
    found: List[Tuple[str, float, float]] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() != "text":
            continue
        content = (element.text or "").strip()
        x, y = element.get("x"), element.get("y")
        if content and x is not None and y is not None:
            found.append((content, float(x), float(y)))
    return found


class TheLimitationsAreDisclosedTests(unittest.TestCase):
    """The same four weaknesses are in both documents, and the check can fail."""

    def test_the_readme_discloses_all_four(self):
        self.assertEqual([], missing_limitations(prose(README)))

    def test_the_threat_model_discloses_all_four(self):
        self.assertEqual([], missing_limitations(prose(THREAT_MODEL)))

    def test_a_document_with_one_taken_out_is_reported(self):
        """The check above is shown capable of failing."""
        dropped = LIMITATIONS[2]
        doctored = prose(README).replace(dropped, "a different sentence")
        self.assertEqual([dropped], missing_limitations(doctored))

    def test_the_documents_really_carry_the_phrases(self):
        """A control: the search is against prose that is there, not against a blank."""
        for path in (README, THREAT_MODEL):
            with self.subTest(document=path.name):
                self.assertGreater(len(prose(path)), 1000)


class TheStartHereListTests(unittest.TestCase):
    """The README opens with a short list that points where it must."""

    def _block(self) -> List[str]:
        """The Start here list's own lines, blanks dropped."""
        lines = read(README).split("\n")
        start = lines.index("**Start here.**")
        block: List[str] = []
        for line in lines[start:]:
            if line == "**Start here.**" or line.startswith("- ") or not line.strip():
                block.append(line)
                continue
            break
        return [line for line in block if line.strip()]

    def test_it_is_at_the_top_and_is_short(self):
        text = read(README)
        self.assertLess(
            text.index("**Start here.**"),
            text.index("## Results"),
            "the Start here list is not above the results",
        )
        self.assertLessEqual(
            len(self._block()), 10, "the Start here list is longer than ten lines"
        )

    def test_it_names_the_demo_the_two_cases_and_the_five_documents(self):
        block = "\n".join(self._block())
        for required in (
            "https://tribunal.edgeone.dev/",
            "/case-00208.html",
            "/case-00901.html",
            "docs/submission/",
            "docs/architecture.md",
            "how-we-built-it.md",
            "#limitations-and-disclosures",
        ):
            with self.subTest(required=required):
                self.assertIn(required, block)


class TheHowWeBuiltItPageTests(unittest.TestCase):
    """The one page the sheet asks for, and what it must carry."""

    def test_it_exists_and_holds_no_non_ascii_character(self):
        text = read(HOW_WE_BUILT_IT)
        self.assertTrue(text.isascii(), "the page holds a non-ASCII character")

    def test_it_carries_the_workflow_and_the_four_tips(self):
        text = prose(HOW_WE_BUILT_IT)
        for required in (
            "One task specification per part, one session per part, one row per session",
            "outside WorkBuddy's sandbox",
            "Run the tests outside the agent's sandbox",
            "One task per session keeps the context small",
            "checked against the real output",
            "Import a sealed set without reading its answers",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_the_counts_it_states_are_the_repositorys_own(self):
        portability.require_git_history()
        text = prose(HOW_WE_BUILT_IT)
        self.assertIn("`{0}`".format(COUNTS_COMMIT), text)
        self.assertIn("**{0} commits**".format(STATED_COMMITS), text)
        self.assertIn("**{0} dated rows**".format(STATED_SESSIONS), text)

        commits = subprocess.run(
            ["git", "rev-list", "--count", COUNTS_COMMIT],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(str(STATED_COMMITS), commits)

        log = subprocess.run(
            ["git", "show", "{0}:docs/buddy-log/README.md".format(COUNTS_COMMIT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        rows = [line for line in log.split("\n") if line.startswith("| 2026-")]
        self.assertEqual(STATED_SESSIONS, len(rows))


class TheDiagramLabelsTests(unittest.TestCase):
    """The four labels the diagram moved sit where the fix put them."""

    def setUp(self):
        self.found = {
            content: (x, y) for content, x, y in svg_texts(read(DIAGRAM))
        }

    def test_the_four_labels_are_where_the_fix_put_them(self):
        for label, position in MOVED_LABELS.items():
            with self.subTest(label=label):
                self.assertIn(label, self.found, "{0} is not in the diagram".format(label))
                self.assertEqual(position, self.found[label])

    def test_the_two_that_moved_right_are_outside_the_middle_column(self):
        """Outside the column, no box border can cross them.

        Every box of the middle column spans the same x range, so a label placed
        wholly to the right of it cannot be touched by any of their borders --
        which is what these two used to be.
        """
        for label in ("same artifacts", "case file"):
            with self.subTest(label=label):
                x, _y = self.found[label]
                self.assertGreaterEqual(x, MIDDLE_COLUMN_RIGHT)

    def test_the_one_that_moved_left_starts_outside_the_column(self):
        """A three-character label whose x is left of the column cannot reach it."""
        x, _y = self.found["yes"]
        self.assertLess(x, MIDDLE_COLUMN_LEFT)


if __name__ == "__main__":
    unittest.main()
