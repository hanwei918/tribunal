"""No test and no builder names a path under the repository's ``tmp/``.

``tmp/`` is gitignored scratch: it holds the owner's working material, the
sheets a part is written from, and the originals of files that were later
committed. It is therefore **absent from a clean clone**, and anything that
reads a path under it works on the machine that wrote the file and fails
everywhere else -- which is what happened until part 48, when
``ui/v2/build.py`` copied the link-preview image out of ``tmp/`` and the two
tests that hold the site to its own bytes went red on a fresh clone.

**What this module reads.** The source of every module under ``tests/``, every
module under ``ui/`` -- the tests and the three builders -- every module under
``tools/`` and every module under ``tryit/``, parsed with ``ast``, so a mention
of ``tmp`` in a **comment** is not a hit. Two shapes are reported, and they are
the two ways this repository names a path:

* a **string literal** whose first path component is ``tmp`` and which has at
  least one more component, such as ``"tmp/og-image.png"``. An **absolute** path
  is not one of these: ``/tmp/runs`` is the operating system's temporary
  directory, not this repository's, and the suite uses it deliberately for
  scratch roots;
* a **``/`` join** whose right-hand operand is the literal ``"tmp"``, such as
  ``PROJECT_ROOT / "tmp" / "og-image.png"``. A bare ``"tmp"`` that is an element
  of a set of directory names -- which several tests keep, to skip the
  gitignored roots while walking the repository -- is not a path and is not
  reported.

**The check is shown to fire, and to stay quiet.** A fixture is parsed for each
shape and is required to be reported, and a system ``/tmp`` path and a bare
``"tmp"`` in a set are required **not** to be. The fixture is assembled from
pieces, so this module's own source is not one of the things it reports.

No model call is made and no browser is launched. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = PROJECT_ROOT / "tests"
UI_DIR = PROJECT_ROOT / "ui"
TOOLS_DIR = PROJECT_ROOT / "tools"
TRYIT_DIR = PROJECT_ROOT / "tryit"

# The directory this module is about, assembled from pieces so that this file
# does not itself carry the literal its own check looks for.
SCRATCH_DIR_NAME = "tm" + "p"


def sources() -> List[Path]:
    """Every module the check reads: the tests, the builders, and the tools.

    ``tools/site_import.py`` transcribes the policy owner's product site and
    ``tryit/`` is her try-it service, so both are under the rule the tests and
    the builders are under: a module that named a path under the gitignored
    scratch directory would work on the machine that wrote it and nowhere else.
    """
    found: List[Path] = []
    for directory in (TESTS_DIR, UI_DIR, TOOLS_DIR, TRYIT_DIR):
        found += sorted(directory.rglob("*.py"))
    return [path for path in found if path.is_file()]


def _literal_names_a_path_under_tmp(value: str) -> bool:
    """Whether a string literal is a **relative** path whose first part is ``tmp``.

    ``"tmp"`` alone is a name and not a path, ``"/tmp/runs"`` is the operating
    system's directory, and ``"somewhere/tmp/x"`` is a path under another
    directory; none of the three is a path under this repository's ``tmp/``.
    """
    if not value or value.startswith(("/", "~")):
        return False
    parts = [part for part in value.split("/") if part not in ("", ".")]
    return len(parts) > 1 and parts[0] == SCRATCH_DIR_NAME


def _join_names_tmp(node: ast.AST) -> bool:
    """Whether a node is ``<something> / "tmp"``, the join this repository uses."""
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
        return False
    right = node.right
    return isinstance(right, ast.Constant) and right.value == SCRATCH_DIR_NAME


def offences_in_source(text: str, filename: str = "<fixture>") -> List[str]:
    """Every literal or join in one module's source that names ``tmp/``.

    The module is parsed rather than searched, so a comment, a docstring or a
    test's own description of the rule is not reported as a breach of it.
    """
    tree = ast.parse(text, filename=filename)
    found: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _literal_names_a_path_under_tmp(node.value):
                found.append(node.value)
        elif _join_names_tmp(node):
            found.append(SCRATCH_DIR_NAME)
    return sorted(set(found))


class TheCheckTests(unittest.TestCase):
    """The check itself, on fixtures it must catch and on ones it must not."""

    def test_it_finds_a_literal_path_under_tmp(self):
        source = "OG = {0!r}\n".format(SCRATCH_DIR_NAME + "/og-image.png")
        self.assertEqual(
            [SCRATCH_DIR_NAME + "/og-image.png"], offences_in_source(source)
        )

    def test_it_finds_the_join_this_repository_writes(self):
        """The shape the builder used: ``PROJECT_ROOT / "tmp" / "og-image.png"``."""
        source = "OG = PROJECT_ROOT / {0!r} / 'og-image.png'\n".format(SCRATCH_DIR_NAME)
        self.assertEqual([SCRATCH_DIR_NAME], offences_in_source(source))

    def test_it_does_not_find_a_system_tmp_path(self):
        """``/tmp/runs`` is the operating system's directory, not this one's."""
        self.assertEqual([], offences_in_source("RUNS = '/tmp/runs'\n"))
        self.assertEqual([], offences_in_source("RUNS = Path('/tmp') / 'runs'\n"))

    def test_it_does_not_find_a_bare_name_in_a_set(self):
        """Several tests skip the gitignored roots by name; that is not a read."""
        source = "SKIP = {{'.git', {0!r}, 'output'}}\n".format(SCRATCH_DIR_NAME)
        self.assertEqual([], offences_in_source(source))

    def test_it_does_not_find_a_mention_in_a_comment(self):
        source = "# the owner's original sits in {0}/\nX = 1\n".format(SCRATCH_DIR_NAME)
        self.assertEqual([], offences_in_source(source))


class TheRepositoryTests(unittest.TestCase):
    """The tests and the builders, under the rule."""

    def test_the_walk_covers_the_tests_and_the_builders(self):
        """A walk that silently found nothing would otherwise pass."""
        found = {path.name for path in sources()}
        for required in (
            "build.py",
            "portability.py",
            "test_ui_v2.py",
            "test_ui_build.py",
            "site_import.py",
            "server.py",
        ):
            self.assertIn(required, found, "{0} was not walked".format(required))
        self.assertTrue(
            (UI_DIR / "v2" / "build.py") in sources(),
            "the product view's builder is not in the walk",
        )
        self.assertTrue(
            (UI_DIR / "site" / "build.py") in sources(),
            "the product site's builder is not in the walk",
        )
        self.assertTrue(
            (TRYIT_DIR / "case.py") in sources(),
            "the try-it service is not in the walk",
        )
        self.assertTrue(
            (TOOLS_DIR / "site_import.py") in sources(),
            "the importer is not in the walk",
        )

    def test_no_test_and_no_builder_names_a_path_under_tmp(self):
        offences: Dict[str, List[str]] = {}
        for path in sources():
            found = offences_in_source(
                path.read_text(encoding="utf-8"), str(path.relative_to(PROJECT_ROOT))
            )
            if found:
                offences[str(path.relative_to(PROJECT_ROOT))] = found
        self.assertEqual(
            {},
            offences,
            "a path under tmp/ is named by a test or a builder, and tmp/ is not in "
            "a clean clone: {0}".format(
                "; ".join(
                    "{0}: {1}".format(name, ", ".join(values))
                    for name, values in sorted(offences.items())
                )
            ),
        )


if __name__ == "__main__":
    unittest.main()
