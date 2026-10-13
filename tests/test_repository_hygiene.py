"""The rules that keep a stray document out of the repository.

``.gitignore`` is the only thing standing between a hand-dragged PDF and a public
repository, and a pattern that *reads* as though it matches is not a pattern that
matches: gitignore is case-sensitive on a case-sensitive filesystem, so ``*.pdf``
ignores ``Resume.PDF`` on macOS and does not on Linux. The rules this module
covers were asked for as case-insensitive, so the patterns are bracket
expressions -- and this module asks **git itself** rather than a copy of the
patterns, for the same reason ``tests/test_wild_v2_run_manifest.py`` does: a
check against a second copy of the rules is a check that can agree with itself
while disagreeing with the repository.

Every name is asked with ``--no-index``, so a name is answered whether or not it
exists and whether or not it is tracked.

**The second half is the control.** An ignore rule that is too wide is worse than
no rule at all: ``*resume*`` must not swallow a note about a resume policy, and
``*.pdf`` must not swallow anything the repository carries. The names in
``REPOSITORY_CONTENT`` are files the repository does track, and each is asserted
to be visible to git -- so a pattern that widened would fail here rather than
quietly hide a tracked file from a later ``git add``.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests import portability  # noqa: E402

# Documents a tool drops into the working tree: an exported PDF, a Word
# document, a slide deck, and a file named after a CV. Each is listed in the
# casings a real tool produces -- an export named after a person, a document a
# colleague sent -- because the case is the whole point. A case-sensitive rule
# ignores the lower-case name and lets the upper-case one through.
STRAY_DOCUMENTS = (
    "resume.pdf",
    "Resume.pdf",
    "RESUME.PDF",
    "annual-report.pdf",
    "Annual-Report.PDF",
    "My Resume (final).pdf",
    "notes.docx",
    "Notes.DOCX",
    "handover.docx",
    "deck.pptx",
    "Deck.PPTX",
    "resume",
    "Resume",
    "resume.md",
    "Resume.MD",
    "docs/resume.md",
    "docs/Resume.md",
)

# Paths the repository carries, one from each tree. An ignore rule that matched
# one of these would be hiding repository content, so each is asserted visible.
# The last two are `.zip` files, and they are here on purpose: `*.zip` ignores a
# dropped deploy archive, and the product site ships two archives of its own --
# Pyodide's `python_stdlib.zip` and the bundle `ui/site/build.py` builds -- so
# the two negations in `.gitignore` are what keeps them visible, and this is what
# holds those negations in place.
REPOSITORY_CONTENT = (
    "README.md",
    "START-HERE.md",
    "ui/build.py",
    "ui/dist/index.html",
    "policy/general.json",
    "tests/test_ui_build.py",
    "docs/notes/2026-10-04-the-second-sealed-run.md",
    "docs/buddy-log/README.md",
    "ui/site/static/try/pyodide/python_stdlib.zip",
    "ui/dist/try/tribunal-core.zip",
)


def ignored(path: str) -> bool:
    """Whether the repository's ``.gitignore`` matches a path.

    Asked of git itself rather than of a copy of the patterns, so the check and
    the repository's own rules cannot come to differ. ``--no-index`` so a name is
    answered whether or not it happens to exist or to be tracked.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


class TheStrayDocumentRulesTests(unittest.TestCase):
    """The four documents the rules cover, in the casings they arrive in.

    **A machine without the repository's history cannot be asked.** ``git
    check-ignore`` answers from ``.git``, so with no ``.git`` -- a zip download
    -- or no ``git``, a name comes back unanswered rather than unignored. The
    two tests below that fail without the history skip, naming the reason, and
    run exactly as they did when it is there.
    """

    def test_every_stray_document_is_ignored(self):
        for name in STRAY_DOCUMENTS:
            with self.subTest(name=name):
                portability.require_git_history()
                self.assertTrue(
                    ignored(name),
                    "{0!r} is not ignored, so a drag-and-drop can commit it".format(
                        name
                    ),
                )

    def test_the_helper_answers_both_ways(self):
        """The control for the helper: one name ignored, one not.

        A helper that answered ``False`` for everything would pass the test
        below and fail this one.
        """
        portability.require_git_history()
        self.assertTrue(ignored("__pycache__/anything.pyc"))
        self.assertFalse(ignored("README.md"))

    def test_no_rule_matches_repository_content(self):
        """The rules are about documents that arrive, not about what is here.

        An ignore rule that is too wide hides repository content: the file stays
        tracked, but a later ``git add`` of it is refused and a reader has no way
        to tell why.
        """
        for name in REPOSITORY_CONTENT:
            with self.subTest(name=name):
                self.assertFalse(
                    ignored(name),
                    "{0!r} is ignored, so a rule is wider than it should be".format(
                        name
                    ),
                )

    def test_the_content_control_names_files_that_exist(self):
        """A control over paths that are not there would prove nothing."""
        for name in REPOSITORY_CONTENT:
            with self.subTest(name=name):
                self.assertTrue(
                    (PROJECT_ROOT / name).is_file(),
                    "{0!r} is not a file in this repository".format(name),
                )


class TheLicenceTests(unittest.TestCase):
    """The repository is published, and the file it is published under says so."""

    def test_the_licence_is_the_mit_licence(self):
        self.assertTrue(
            (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
        )


if __name__ == "__main__":
    unittest.main()
