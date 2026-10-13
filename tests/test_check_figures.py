"""One figure, one value everywhere -- and the check shown capable of failing.

``tools/check_figures.py`` computes each headline figure from the committed runs
and reads every document and built page that states it. This module holds it to
three things:

* **The committed tree passes.** No document states a figure with a value the
  runs do not give, and no pattern in the table has died -- a pattern that
  matches nothing is a place nobody is checking, so a dead pattern is a failure
  rather than a quiet no-op.
* **The check can fail.** A copy of one document with one figure altered, in a
  temporary directory, is reported as a mismatch; without that control a check
  that returned nothing would pass the first test.
* **The module is ASCII.** The sheet's rule is that the pattern table is written
  in ASCII, with the Chinese patterns as ``\\uXXXX`` escapes, so the module is
  read as bytes and every one is asserted below 128.

No model call is made and no network is reached: every reading is a committed
run, a committed key or a built page. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import check_figures  # noqa: E402

MODULE = PROJECT_ROOT / "tools" / "check_figures.py"

# The document and the figure the control alters, and the two spellings it moves
# between. ``160.4 s`` is the median time's own spelling in ``docs/record.md``.
CONTROL_DOCUMENT = "docs/record.md"
CONTROL_BEFORE = "160.4 s"
CONTROL_AFTER = "160.5 s"
CONTROL_FIGURE = "median time to a decision"


class TheCommittedTreeTests(unittest.TestCase):
    """Every figure, against every document, over the real repository."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.found = check_figures.check()

    def test_the_committed_tree_passes(self):
        self.assertTrue(
            self.found.ok,
            "the committed tree fails: {0} mismatch(es), {1} dead pattern(s)".format(
                len(self.found.mismatches), len(self.found.dead)
            ),
        )

    def test_no_document_states_a_figure_with_the_wrong_value(self):
        self.assertEqual(
            (),
            self.found.mismatches,
            "\n".join(
                "{0}: {1} says {2!r}, the runs say {3!r}".format(
                    mismatch.figure, mismatch.document, mismatch.value, mismatch.expected
                )
                for mismatch in self.found.mismatches
            ),
        )

    def test_every_pattern_matches_at_least_one_document(self):
        """A dead pattern is a place nobody is checking."""
        self.assertEqual(
            (),
            self.found.dead,
            "\n".join(
                "{0}: {1}".format(pattern.figure, pattern.pattern)
                for pattern in self.found.dead
            ),
        )

    def test_every_figure_is_reported_once_and_appears_somewhere(self):
        """A figure nothing states is a figure the table is wrong about."""
        names = [row.figure for row in self.found.rows]
        self.assertEqual(sorted(names), sorted(set(names)), "a figure is reported twice")
        self.assertEqual(
            sorted(name for name in check_figures.BY_NAME),
            sorted(names),
            "the report and the figure table name different figures",
        )
        for row in self.found.rows:
            with self.subTest(figure=row.figure):
                self.assertTrue(
                    row.documents,
                    "{0} is stated in no document".format(row.figure),
                )

    def test_every_figure_has_a_computed_value(self):
        values = check_figures.computed()
        for figure in check_figures.FIGURES:
            with self.subTest(figure=figure.name):
                self.assertIn(figure.name, values)
                self.assertTrue(values[figure.name])

    def test_the_report_prints_a_row_per_figure(self):
        text = check_figures.report()
        self.assertEqual(
            len(check_figures.FIGURES), text.count("\n    in: ")
        )
        self.assertIn("Every occurrence matches the computed value.", text)


class TheControlTests(unittest.TestCase):
    """The check is shown capable of failing, and of noticing a dead pattern."""

    def test_an_altered_figure_is_reported_as_a_mismatch(self):
        source = (PROJECT_ROOT / CONTROL_DOCUMENT).read_text(encoding="utf-8")
        altered = source.replace(CONTROL_BEFORE, CONTROL_AFTER)
        self.assertNotEqual(
            source, altered, "the control changed nothing in {0}".format(CONTROL_DOCUMENT)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / CONTROL_DOCUMENT
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(altered, encoding="utf-8")
            found = check_figures.check(root)
        named = [mismatch for mismatch in found.mismatches if mismatch.value == "160.5"]
        self.assertTrue(
            named,
            "the altered figure was not reported: {0}".format(found.mismatches),
        )
        for mismatch in named:
            with self.subTest(document=mismatch.document):
                self.assertEqual(CONTROL_FIGURE, mismatch.figure)
                self.assertEqual("160.4", mismatch.expected)
        self.assertFalse(found.ok, "an altered figure left the check OK")

    def test_a_pattern_that_matches_nothing_is_reported(self):
        """The dead-pattern check is shown capable of firing."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / CONTROL_DOCUMENT
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("this copy states no figure at all\n", encoding="utf-8")
            found = check_figures.check(root)
        self.assertTrue(found.dead, "no dead pattern was reported")
        self.assertIn(
            CONTROL_FIGURE, {pattern.figure for pattern in found.dead}
        )
        self.assertFalse(found.ok)


class TheModuleTests(unittest.TestCase):
    """The pattern table's own rules."""

    def test_the_module_is_ascii(self):
        raw = MODULE.read_bytes()
        offenders = [byte for byte in raw if byte >= 128]
        self.assertEqual([], offenders, "the module carries a non-ASCII byte")

    def test_every_figure_has_spellings_and_patterns(self):
        for figure in check_figures.FIGURES:
            with self.subTest(figure=figure.name):
                self.assertTrue(figure.spellings)
                self.assertTrue(figure.patterns)

    def test_every_pattern_has_a_capture_group(self):
        """A pattern with no group would check nothing about the value."""
        for figure in check_figures.FIGURES:
            for pattern in figure.patterns:
                with self.subTest(figure=figure.name, pattern=pattern):
                    self.assertGreaterEqual(
                        re.compile(pattern).groups,
                        1,
                        "{0} has no capture group".format(pattern),
                    )


if __name__ == "__main__":
    unittest.main()
