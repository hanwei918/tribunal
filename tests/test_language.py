"""Every tracked text file outside ``runs/`` is written in English.

The repository's standing language rule is that no tracked text file holds a
Chinese character. Until 2026-09-30 two did: a note that quoted a macOS path, and
the held-out set's own README, which arrived from its author in Chinese. The note
now writes the one character as ``U+7684`` and the README has been translated, so
the rule holds for every document the repository writes or carries.

**``runs/`` is the one exemption, and it is named rather than silently skipped.**
Nine tracked files under it quote the same macOS path with the same character in
it, because that is the path the machine recorded. Those files are records
produced by a run, and rewriting one so that a scan comes back clean would be
editing the evidence. The exemption is asserted below rather than assumed: the
walk is checked to cover the rest of the repository and to exclude exactly
``runs/``.

A failure here names the file and the code points, never the characters, so that
the test's own output stays free of them.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The CJK blocks, as inclusive code-point ranges: CJK symbols and punctuation,
# the two Han ranges, compatibility ideographs, and full-width forms.
CJK_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x3000, 0x303F),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFFEF),
)

# Directories that are not repository content: version control, the agent's own
# local state (which is gitignored and holds the user's notes), caches, and the
# gitignored scratch roots.
NOT_REPOSITORY_CONTENT = frozenset(
    {".git", ".workbuddy-ai", "__pycache__", ".venv", "tmp", "output"}
)

# The one directory that is repository content and is nevertheless exempt.
EXEMPT_DIRECTORIES = frozenset({"runs"})


def is_cjk(character: str) -> bool:
    """Whether one character falls in any CJK block."""
    return any(low <= ord(character) <= high for low, high in CJK_RANGES)


def _directories_to_skip() -> frozenset:
    """The directory names the walk never descends into.

    A frozenset and not an iterator: ``any(name in skip for ...)`` consumes an
    iterator, so an iterator here would answer the first path correctly and every
    later one wrongly -- which is exactly how the first cut of this module let
    ``runs/`` through. ``test_the_run_directory_is_exempt_and_nothing_else_is``
    is the fixture that caught it.
    """
    return NOT_REPOSITORY_CONTENT | EXEMPT_DIRECTORIES


def text_files(root: Path) -> List[Path]:
    """Every text file under ``root`` that the language rule governs.

    A file is text if it decodes as UTF-8; anything that does not is a binary
    artifact and carries no prose. ``runs/`` is skipped, so the recorded run
    files are never read by this module at all.
    """
    found: List[Path] = []
    skip = _directories_to_skip()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in skip for part in relative.parts[:-1]):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found.append(path)
    return found


def violations(root: Path) -> Dict[str, List[str]]:
    """``{repository-relative path: ["U+7684", ...]}`` for every offending file.

    The code points are reported as text, so the result never carries the
    characters themselves.
    """
    offences: Dict[str, List[str]] = {}
    for path in text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found = ["U+{0:04X}".format(ord(character)) for character in text if is_cjk(character)]
        if found:
            offences[str(path.relative_to(root))] = sorted(set(found))
    return offences


class TheDetectorTests(unittest.TestCase):
    """The check is shown on a dirty fixture first, then on a clean one."""

    def test_it_finds_a_cjk_character_and_reports_its_code_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dirty.md").write_text("the folder HANWEI\u7684MacBook\n", encoding="utf-8")

            self.assertEqual(
                {"dirty.md": ["U+7684"]}, violations(root), "the dirty fixture was not reported"
            )

    def test_a_clean_tree_reports_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "clean.md").write_text("the folder HANWEI U+7684 MacBook\n", encoding="utf-8")

            self.assertEqual({}, violations(root), "a clean fixture was reported")

    def test_a_binary_file_is_not_read_as_text(self):
        """A PNG holds arbitrary bytes and is not prose."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x80")

            self.assertEqual({}, violations(root), "a binary file was read as text")

    def test_the_run_directory_is_exempt_and_nothing_else_is(self):
        """The exemption is one directory wide, and it is the one that was named."""
        self.assertEqual(frozenset({"runs"}), EXEMPT_DIRECTORIES)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("runs", "docs", "eval"):
                (root / name).mkdir()
                (root / name / "note.md").write_text("HANWEI\u7684MacBook\n", encoding="utf-8")

            self.assertEqual(
                {"docs/note.md": ["U+7684"], "eval/note.md": ["U+7684"]},
                violations(root),
                "the exemption is wider or narrower than runs/ alone",
            )


class TheRepositoryTests(unittest.TestCase):
    """The repository itself, under the rule."""

    def test_the_walk_covers_the_repository(self):
        """The scan is shown to be walking the tree, not silently finding nothing."""
        found = {
            str(path.relative_to(PROJECT_ROOT))
            for path in text_files(PROJECT_ROOT)
        }
        for required in (
            "README.md",
            "WORKBUDDY-SCOPE.md",
            "eval/development_sets.py",
            "tests/test_language.py",
            "ui/dist/index.html",
            # One file from each of the three directories the second sealed
            # set's files sit in: the rule covers its cases, its key and its
            # answer-bearing authoring bundle as much as any other file.
            "data/external/wild-v2/index.json",
            "eval/answers/wild-v2/ground_truth.json",
            "eval/external/wild-v2/README.md",
        ):
            self.assertIn(required, found, "{0} was not walked".format(required))
        self.assertFalse(
            [name for name in found if name.startswith("runs/")],
            "the walk entered runs/, which holds the recorded run files",
        )

    def test_no_tracked_text_file_outside_runs_holds_a_cjk_character(self):
        offences = violations(PROJECT_ROOT)
        self.assertEqual(
            {},
            offences,
            "a file outside runs/ holds CJK characters: {0}".format(
                ", ".join("{0} ({1})".format(name, " ".join(points))
                          for name, points in sorted(offences.items()))
            ),
        )


if __name__ == "__main__":
    unittest.main()
