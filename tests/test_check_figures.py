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
  that returned nothing would pass the first test. Two figures are shown failing
  that way: the version-6 median time in ``docs/record.md``, and the version-7
  sealed set's agreement in ``README.md``.
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

from tests import portability  # noqa: E402
from tools import check_figures  # noqa: E402

MODULE = PROJECT_ROOT / "tools" / "check_figures.py"

# The document and the figure the control alters, and the two spellings it moves
# between. ``160.4 s`` is the median time's own spelling in ``docs/record.md``.
CONTROL_DOCUMENT = "docs/record.md"
CONTROL_BEFORE = "160.4 s"
CONTROL_AFTER = "160.5 s"
CONTROL_FIGURE = "median time to a decision"

# The version-7 figures, and the second control: the sixth sealed set's own
# agreement, in the README's version-7 table. Altered to 29 of 30, the agreement
# pattern captures a value that is not one of the figure's spellings.
VERSION_SEVEN_FIGURES = (
    "sealed-v4, four-field agreement",
    "sealed-v4, Wilson 95% interval",
    "ryde-v7, samples matching Ryde's stated outcomes",
    "dev-v7, four-field agreement",
    "version-7 sealed run, median time to a decision",
    "version-7 sealed run, median model cost",
)
VERSION_SEVEN_CONTROL_DOCUMENT = "README.md"
VERSION_SEVEN_CONTROL_BEFORE = "| 30/30 | [88.6%, 100.0%] |"
VERSION_SEVEN_CONTROL_AFTER = "| 29/30 | [88.6%, 100.0%] |"
VERSION_SEVEN_CONTROL_FIGURE = "sealed-v4, four-field agreement"


class TheCommittedTreeTests(unittest.TestCase):
    """Every figure, against every document, over the real repository."""

    @classmethod
    def setUpClass(cls) -> None:
        portability.require_the_same_libm()
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

    def test_the_version_seven_figures_are_computed_stated_and_matching(self):
        """Policy version 7's figures, from the committed runs.

        Each is stated in at least one document and every pattern that finds it
        matched something, which the class's own two tests above already assert
        over the whole table; this names the version-7 rows so a table that lost
        one fails here rather than passing on the rows that remain.
        """
        rows = {row.figure: row for row in self.found.rows}
        for name in VERSION_SEVEN_FIGURES:
            with self.subTest(figure=name):
                self.assertIn(name, check_figures.BY_NAME)
                self.assertIn(name, rows)
                self.assertTrue(rows[name].value, "no computed value")
                self.assertTrue(rows[name].documents, "stated in no document")
                self.assertTrue(rows[name].ok, "a document states another value")


class TheControlTests(unittest.TestCase):
    """The check is shown capable of failing, and of noticing a dead pattern."""

    def test_an_altered_figure_is_reported_as_a_mismatch(self):
        portability.require_the_same_libm()
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
        portability.require_the_same_libm()
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

    def test_an_altered_version_seven_figure_is_reported(self):
        """The version-7 rows are shown capable of failing too.

        The copy holds the README alone, so the other documents are skipped and
        the version-7 patterns that read them go dead -- which is a finding of
        its own and not what this test is about. What it asserts is the
        mismatch: ``29/30`` is not one of the agreement figure's spellings.
        """
        portability.require_the_same_libm()
        source = (PROJECT_ROOT / VERSION_SEVEN_CONTROL_DOCUMENT).read_text(
            encoding="utf-8"
        )
        altered = source.replace(
            VERSION_SEVEN_CONTROL_BEFORE, VERSION_SEVEN_CONTROL_AFTER
        )
        self.assertNotEqual(
            source,
            altered,
            "the control changed nothing in {0}".format(VERSION_SEVEN_CONTROL_DOCUMENT),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / VERSION_SEVEN_CONTROL_DOCUMENT
            target.write_text(altered, encoding="utf-8")
            found = check_figures.check(root)
        named = [mismatch for mismatch in found.mismatches if mismatch.value == "29/30"]
        self.assertTrue(
            named,
            "the altered version-7 figure was not reported: {0}".format(
                found.mismatches
            ),
        )
        for mismatch in named:
            with self.subTest(document=mismatch.document):
                self.assertEqual(VERSION_SEVEN_CONTROL_FIGURE, mismatch.figure)
                self.assertEqual("30/30", mismatch.expected)
        self.assertFalse(found.ok, "an altered figure left the check OK")


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
