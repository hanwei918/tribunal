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
* **the architecture set makes its own claims**, and the three corrections it was
  drawn to make -- the evidence collector is a standalone CLI the pipeline does
  not call, the precedents are shown to the judge and not to the advocates, and
  the freeze the drawings are made from is the final one -- are each read off the
  drawing that makes it, together with the rule about calls.

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
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402

README = PROJECT_ROOT / "README.md"
# The limitations section moved, whole, to docs/record.md on 2026-10-13.
RECORD = PROJECT_ROOT / "docs" / "record.md"
THREAT_MODEL = PROJECT_ROOT / "docs" / "governance" / "threat-model.md"
HOW_WE_BUILT_IT = PROJECT_ROOT / "docs" / "submission" / "how-we-built-it.md"
ARCHITECTURE_DIR = PROJECT_ROOT / "docs" / "architecture"

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

# The four views of the architecture set the policy owner drew, in the order the
# page walks them, each with the title its own first line carries.
DIAGRAM_VIEWS: Tuple[Tuple[str, str], ...] = (
    ("1-system-context.svg", "System Context diagram for Tribunal"),
    (
        "2a-containers-deciding.svg",
        "Container diagram for Tribunal - 2a. Deciding and measuring",
    ),
    (
        "2b-containers-after-ruling.svg",
        "Container diagram for Tribunal - 2b. After a ruling: operations, "
        "learning loop, publishing",
    ),
    (
        "3-dynamic-one-dispute.svg",
        "Dynamic diagram for Tribunal - how one dispute is decided",
    ),
)

# The claims the set makes, each a phrase one ``<text>`` of that drawing carries
# whole. The first three are the corrections the set was drawn to make, which the
# diagram it replaced got wrong: the evidence collector is a standalone CLI the
# pipeline does not call, the precedents are shown to the judge and not to the
# advocates, and the freeze the drawings are made from is the final one. The
# fourth is the rule about calls, which the diagram it replaced did not state at
# all -- and it is the rule this repository discloses a weakness in, so a drawing
# that stopped stating it would leave the disclosure standing alone.
DIAGRAM_CLAIMS: Tuple[Tuple[str, str], ...] = (
    ("2a-containers-deciding.svg", "Standalone CLI, not wired into the"),
    ("3-dynamic-one-dispute.svg", "shown to the judge"),
    ("1-system-context.svg", "freeze-2026-10-14-v8"),
    (
        "3-dynamic-one-dispute.svg",
        "an unusable answer is retried once, an HTTP 429/5xx up to 4 attempts.",
    ),
)


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


def texts_of(view: str) -> List[str]:
    """Every placed ``<text>`` of one view, stripped, in document order."""
    root = ET.fromstring(read(ARCHITECTURE_DIR / view))
    return [
        (element.text or "").strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1].lower() == "text" and (element.text or "").strip()
    ]


def missing_claims(
    claims: Tuple[Tuple[str, str], ...] = DIAGRAM_CLAIMS,
) -> List[str]:
    """The claims the set does not make, as ``"<view>: <phrase>"``.

    A claim is carried when one ``<text>`` of that view holds the phrase whole,
    which is the strongest reading available: a phrase that only appeared by
    running two labels together would not be a claim the drawing makes.
    """
    return [
        "{0}: {1}".format(view, phrase)
        for view, phrase in claims
        if not any(phrase in text for text in texts_of(view))
    ]


class TheLimitationsAreDisclosedTests(unittest.TestCase):
    """The same four weaknesses are in both documents, and the check can fail."""

    def test_the_readme_discloses_all_four(self):
        self.assertEqual([], missing_limitations(prose(RECORD)))

    def test_the_threat_model_discloses_all_four(self):
        self.assertEqual([], missing_limitations(prose(THREAT_MODEL)))

    def test_a_document_with_one_taken_out_is_reported(self):
        """The check above is shown capable of failing."""
        dropped = LIMITATIONS[2]
        doctored = prose(RECORD).replace(dropped, "a different sentence")
        self.assertEqual([dropped], missing_limitations(doctored))

    def test_the_documents_really_carry_the_phrases(self):
        """A control: the search is against prose that is there, not against a blank."""
        for path in (RECORD, THREAT_MODEL):
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


class TheDiagramClaimsTests(unittest.TestCase):
    """The set's own claims, and the three corrections it was drawn to make."""

    def test_the_set_is_the_four_views_the_page_walks(self):
        for view, title in DIAGRAM_VIEWS:
            with self.subTest(view=view):
                self.assertIn(
                    title,
                    texts_of(view),
                    "the view does not carry the title the page names it by",
                )

    def test_every_claim_the_set_makes_is_in_the_view_that_makes_it(self):
        self.assertEqual([], missing_claims())

    def test_a_claim_taken_out_is_reported(self):
        """The check above is shown capable of failing."""
        doctored = tuple(
            (view, "a phrase this drawing does not carry") if index == 0 else (view, phrase)
            for index, (view, phrase) in enumerate(DIAGRAM_CLAIMS)
        )
        self.assertEqual(1, len(missing_claims(doctored)))

    def test_the_precedents_are_shown_to_the_judge_and_not_to_the_advocates(self):
        """The correction: the arrow the old diagram drew pointed at the advocates."""
        texts = texts_of("3-dynamic-one-dispute.svg")
        self.assertIn("shown to the judge", texts)
        self.assertNotIn("shown to the advocates", texts)


if __name__ == "__main__":
    unittest.main()
