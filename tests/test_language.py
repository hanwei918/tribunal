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

**The product site is the second exemption, and it is named file by file.** The
policy owner, Ji Guofang, designed the product site outside WorkBuddy and wrote
its text in two languages: eleven of its 22 pages are Chinese, every English
page carries the language switch's own two characters, and the Chinese pages
share a script that carries ten more. ``tools/site_import.py`` transcribed her
files unchanged and ``ui/site/build.py`` builds them back out, so the rule --
which is about what **this repository writes** -- exempts her site rather than
rewriting it, exactly as it exempts ``runs/``. The set is derived from the two
builders rather than typed, and a test below holds it to being the site's own
files and no wider.

A failure here names the file and the code points, never the characters, so that
the test's own output stays free of them.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.site import build as site_build  # noqa: E402

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


def imported_files() -> frozenset:
    """The product site's own files: her sources, and the copies built from them.

    Asked of the two builders rather than typed here, so the set cannot drift
    from what is imported and built: ``ui/site/src/`` and ``ui/site/static/``
    are what ``tools/site_import.py`` wrote, and ``ui.site.build``'s own path
    list is what is published under ``ui/dist/``.
    """
    sources = {
        path.relative_to(PROJECT_ROOT).as_posix()
        for directory in (site_build.SRC_DIR, site_build.STATIC_DIR)
        for path in directory.rglob("*")
        if path.is_file()
    }
    built = {"ui/dist/" + name for name in site_build.written_paths()}
    return frozenset(sources | built)


# The exemption itself, named once. It is a set of paths rather than a
# directory because the product site shares ``ui/dist/`` with two other
# builders: the queue, the case pages and the replay are this repository's own
# writing and stay under the rule.
IMPORTED_PAGES = imported_files()


def is_cjk(character: str) -> bool:
    """Whether one character falls in any CJK block."""
    return any(low <= ord(character) <= high for low, high in CJK_RANGES)


def holds_cjk(text: str) -> bool:
    """Whether any character of a whole text falls in a CJK block.

    The whole-text check the per-character one is for: ``is_cjk`` takes exactly
    one character, so a caller that hands it a page gets ``TypeError`` from
    ``ord`` rather than an answer, and the check it meant to make never runs.
    """
    return any(is_cjk(character) for character in text)


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
    files are never read by this module at all, and so is the product site --
    the policy owner's design, imported unchanged, which carries Chinese by
    design and is named file by file in ``IMPORTED_PAGES``.
    """
    found: List[Path] = []
    skip = _directories_to_skip()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in skip for part in relative.parts[:-1]):
            continue
        if relative.as_posix() in IMPORTED_PAGES:
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


class TheProductSiteTests(unittest.TestCase):
    """The second exemption: the site's own files, and nothing wider than them."""

    def test_the_exemption_is_the_sites_own_files(self):
        """Asked of the builders, so it cannot drift from what is imported."""
        sources = {
            path.relative_to(PROJECT_ROOT).as_posix()
            for directory in (site_build.SRC_DIR, site_build.STATIC_DIR)
            for path in directory.rglob("*")
            if path.is_file()
        }
        built = {"ui/dist/" + name for name in site_build.written_paths()}
        self.assertEqual(sources | built, set(IMPORTED_PAGES))

    def test_the_exemption_is_not_wider_than_the_site(self):
        """This repository's own writing is still under the rule."""
        for name in (
            "ui/dist/queue.html",
            "ui/dist/404.html",
            "ui/dist/case-00208.html",
            "ui/dist/replay/index.html",
            "ui/site/build.py",
            "README.md",
            "tests/test_language.py",
        ):
            with self.subTest(path=name):
                self.assertNotIn(name, IMPORTED_PAGES)

    def test_the_exemption_covers_every_chinese_page(self):
        """Eleven Chinese pages, as her sources and as the copies built from them."""
        chinese = sorted(name for name in IMPORTED_PAGES if name.endswith(".zh.html"))
        self.assertEqual(2 * 11, len(chinese), chinese)
        self.assertIn("ui/site/src/pages/index.zh.html", IMPORTED_PAGES)
        self.assertIn("ui/dist/index.zh.html", IMPORTED_PAGES)

    def test_the_exemption_is_doing_something(self):
        """The page really does carry the characters the rule looks for."""
        page = PROJECT_ROOT / "ui/site/src/pages/index.zh.html"
        self.assertTrue(holds_cjk(page.read_text(encoding="utf-8")))
        self.assertNotIn(
            "ui/site/src/pages/index.zh.html",
            {str(path.relative_to(PROJECT_ROOT)) for path in text_files(PROJECT_ROOT)},
        )

    def test_the_same_bytes_outside_the_site_are_still_reported(self):
        """The control: the exemption is the file's path, not its contents."""
        page = (PROJECT_ROOT / "ui/site/src/pages/index.zh.html").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text(page, encoding="utf-8")
            self.assertIn("page.html", violations(root))


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
            "ui/dist/queue.html",
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
