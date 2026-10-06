"""The screenshots the buddy log lists are the ones on disk, byte for byte.

The twelve images under ``docs/buddy-log/`` are captures of WorkBuddy's own
window, and the section they live in records each one's sha256. A digest written
into a document is a claim about a file, and a claim nobody checks is a claim
that can drift: a screenshot that was resized or re-encoded keeps its name and
stops matching the number printed beside it, and nothing would say so.

The section is parsed out of the buddy log rather than restated here, for the
reason ``tests/test_readme_figures.py`` parses the README -- a second copy of the
digests would agree with itself while disagreeing with the file a reader
actually reads. The table is located by its heading and its own header row
rather than by position, so a second table added elsewhere in the file cannot be
mistaken for it.

Every failure names the file and nothing else, so the message says which image
moved without making a reader compare two digests by eye.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUDDY_LOG = PROJECT_ROOT / "docs" / "buddy-log"
BUDDY_LOG_README = BUDDY_LOG / "README.md"

# The heading the screenshots live under, and the header row of its table.
SECTION_HEADING = "## WorkBuddy sessions, in screenshots"
TABLE_HEADER = ("file", "session", "what it shows", "sha256")


def _cells(line: str) -> List[str]:
    """The cells of one markdown table row, with the outer pipes dropped."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def screenshot_rows(text: str) -> List[Tuple[str, str]]:
    """``[(file name, sha256), ...]`` from the screenshots section.

    An empty list means the section, or its table, was not found -- which the
    tests below treat as a failure rather than as nothing to check.
    """
    lines = text.split("\n")
    if SECTION_HEADING not in lines:
        return []
    start = lines.index(SECTION_HEADING)
    header = None
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("|") and tuple(_cells(lines[index])) == TABLE_HEADER:
            header = index
            break
    if header is None:
        return []
    rows: List[Tuple[str, str]] = []
    for line in lines[header + 2:]:
        if not line.strip().startswith("|"):
            break
        cells = _cells(line)
        if len(cells) != len(TABLE_HEADER):
            continue
        rows.append((cells[0].strip("`"), cells[3].strip("`")))
    return rows


class TheScreenshotDigestsTests(unittest.TestCase):
    """Every file the section lists is there, and is the file it was."""

    def setUp(self):
        self.rows = screenshot_rows(BUDDY_LOG_README.read_text(encoding="utf-8"))

    def test_the_section_lists_its_screenshots(self):
        """The check below cannot pass by finding nothing to check."""
        self.assertTrue(
            self.rows,
            "the buddy log lists no screenshots under {0!r}".format(SECTION_HEADING),
        )

    def test_every_listed_screenshot_exists_and_matches_its_sha256(self):
        for name, digest in self.rows:
            with self.subTest(file=name):
                path = BUDDY_LOG / name
                self.assertTrue(path.is_file(), name)
                self.assertEqual(
                    digest,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    name,
                )


if __name__ == "__main__":
    unittest.main()
