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
  that returned nothing would pass the first test. Four figures are shown
  failing that way: the version-6 median time in ``docs/record.md``, the
  version-7 sealed set's agreement in ``README.md``, the version-8 ``dev-v8``
  agreement in ``README.md``, and the version-8 ``decided with no person``
  measurement in ``docs/notes/2026-10-14-version-8-measurements.md``. Two
  **claims** are shown failing the same way, each by putting the corrected
  sentence back: ``split 2-2`` on the version-8 row of ``README.md``, and the
  fare sentence in ``tests/test_ryde_v7.py``.
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

# The version-8 figures, and the third control: ``dev-v8``'s own agreement, in
# the README's version-8 table. Altered to 38 of 40, the agreement pattern
# captures a value that is not one of the figure's spellings.
VERSION_EIGHT_FIGURES = (
    "ryde-v8, samples matching Ryde's stated outcomes",
    "dev-v8, four-field agreement",
    "dev-v8, median time to a decision",
    "dev-v8, median model cost",
    "ryde-v8, 903's drafts counted by outcome",
)
VERSION_EIGHT_CONTROL_DOCUMENT = "README.md"
VERSION_EIGHT_CONTROL_BEFORE = "| `dev-v8` (40 cases) | 39/40 |"
VERSION_EIGHT_CONTROL_AFTER = "| `dev-v8` (40 cases) | 38/40 |"
VERSION_EIGHT_CONTROL_FIGURE = "dev-v8, four-field agreement"

# The four version-8 **measurement** figures part 90 adds, and the fourth
# control: the note states the table ``eval.v8_report --report`` prints, and its
# ``decided with no person`` row altered from 28 to 27 captures a value that is
# not one of the figure's spellings.
VERSION_EIGHT_MEASUREMENT_FIGURES = (
    "dev-v8 decided with no person",
    "dev-v8 position swap",
    "dev-v8 ECE",
    "dev-v8 drafts",
)
MEASUREMENT_CONTROL_DOCUMENT = "docs/notes/2026-10-14-version-8-measurements.md"
MEASUREMENT_CONTROL_BEFORE = "| decided with no person | 28 of 40 |"
MEASUREMENT_CONTROL_AFTER = "| decided with no person | 27 of 40 |"
MEASUREMENT_CONTROL_FIGURE = "dev-v8 decided with no person"

# The version-8 figures the product site states, and the fifth control: the
# front page's position-swap figure, altered. The copy holds ``ui/dist/index.html``
# alone, so the figures that read the other documents go dead -- a finding of its
# own and not what this test is about. What it asserts is the mismatch: the
# front page states 32 where the committed run says 33 of 34.
VERSION_EIGHT_SITE_FIGURES = (
    "dev-v8, median time to a decision",
    "dev-v8, 90th percentile time to a decision",
    "dev-v8, median model cost",
    "dev-v8 decided with no person",
    "dev-v8 position swap",
    "dev-v8 ECE",
    "dev-v8 drafts",
    "dev-v8, cases that went to a person",
    "dev-v8, the gate's three limbs",
    "dev-v8, route deviation limit",
    "dev-v8, the value a person decides above",
    "dev-v8, confidence the policy asks",
    "case 5051, evidence items",
    "case 5051, the rider's and the driver's points",
    "case 5051, claims kept",
    "case 5051, the dropped point",
    "case 5051, the amount to the driver",
    "case 5051, the wall clock",
    "case 5051, the wait and the free wait",
    "version-8 case pages",
    "sealed-v4, cases that needed a person",
)
SWAP_CONTROL_DOCUMENT = "ui/dist/index.html"
SWAP_CONTROL_BEFORE = '<span data-count="33">33</span><small> of 34:</small>'
SWAP_CONTROL_AFTER = '<span data-count="32">32</span><small> of 34:</small>'
SWAP_CONTROL_FIGURE = "dev-v8 position swap"

# The claim controls. Each copy puts back one sentence the part corrected and
# shows the claim check reporting it. ``split 2-2`` goes back on the version-8
# row of the README, which names ``ryde-v8`` and 903 on one line; the fare
# sentence goes back into the ``tests/test_ryde_v7.py`` docstring.
CLAIM_CONTROL_DOCUMENT = "README.md"
CLAIM_CONTROL_BEFORE = "and it escalated on the 0.95 bar Tribunal reads"
CLAIM_CONTROL_AFTER = (
    "and the panel split 2-2 and escalated on the 0.95 bar Tribunal reads"
)
CLAIM_CONTROL_NAME = "version-8 903 is not a 2-2 split"

FARE_CLAIM_CONTROL_DOCUMENT = "tests/test_ryde_v7.py"
FARE_CLAIM_CONTROL_BEFORE = (
    "this prototype's scope, stated in Tribunal's own POL-GEN-24; v2.1 itself "
    "lets\nthe AI rule a fare dispute (Section 6.2), and fare disputes are on the "
    "roadmap."
)
FARE_CLAIM_CONTROL_AFTER = (
    "what POL-GEN-24 says about it, since v2.1 routes a fare dispute to a person\n"
    "rather than adjudicating it."
)
FARE_CLAIM_CONTROL_NAME = "v2.1 does not route a fare dispute to a person"


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

    def test_no_document_makes_a_forbidden_claim(self):
        """No line a claim reads says what the claim forbids."""
        self.assertEqual(
            (),
            self.found.claims,
            "\n".join(
                "{0}: {1} says {2!r}".format(hit.claim, hit.document, hit.line)
                for hit in self.found.claims
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

    def test_the_version_eight_figures_are_computed_stated_and_matching(self):
        """Policy version 8's figures, from the committed runs.

        The same check the version-7 rows get: each is stated in at least one
        document, every pattern that finds it matched something, and the value
        the documents state is the computed one. This names the version-8 rows
        so a table that lost one fails here rather than passing on the rows
        that remain.
        """
        rows = {row.figure: row for row in self.found.rows}
        for name in VERSION_EIGHT_FIGURES:
            with self.subTest(figure=name):
                self.assertIn(name, check_figures.BY_NAME)
                self.assertIn(name, rows)
                self.assertTrue(rows[name].value, "no computed value")
                self.assertTrue(rows[name].documents, "stated in no document")
                self.assertTrue(rows[name].ok, "a document states another value")

    def test_the_version_eight_site_figures_are_computed_stated_and_matching(self):
        """The version-8 figures the product site states, from the committed runs.

        The same check the other version-8 rows get: each is stated in at least
        one document -- one of them is a built page -- every pattern that finds
        it matched something, and the value the documents state is the computed
        one. This names the rows so a table that lost one fails here rather than
        passing on the rows that remain.
        """
        rows = {row.figure: row for row in self.found.rows}
        for name in VERSION_EIGHT_SITE_FIGURES:
            with self.subTest(figure=name):
                self.assertIn(name, check_figures.BY_NAME)
                self.assertIn(name, rows)
                self.assertTrue(rows[name].value, "no computed value")
                self.assertTrue(rows[name].documents, "stated in no document")
                self.assertTrue(rows[name].ok, "a document states another value")

    def test_the_version_eight_measurement_figures_are_computed_stated_and_matching(
        self,
    ):
        """The version-8 measurements, read out of the note that states them.

        The same check the version-7 and version-8 rows get: each is stated in
        at least one document, its patterns matched, and the value the note
        states is the computed one. ``docs/notes/2026-10-14-version-8-measurements.md``
        is the document that states the table ``eval.v8_report --report`` prints,
        and it is named in ``DOCUMENTS`` for these four rows.
        """
        rows = {row.figure: row for row in self.found.rows}
        for name in VERSION_EIGHT_MEASUREMENT_FIGURES:
            with self.subTest(figure=name):
                self.assertIn(name, check_figures.BY_NAME)
                self.assertIn(name, rows)
                self.assertTrue(rows[name].value, "no computed value")
                self.assertTrue(rows[name].documents, "stated in no document")
                self.assertIn(
                    MEASUREMENT_CONTROL_DOCUMENT,
                    rows[name].documents,
                    "the note does not state this figure",
                )
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

    def test_an_altered_version_eight_figure_is_reported(self):
        """The version-8 rows are shown capable of failing too.

        The copy holds the README alone, so the other documents are skipped and
        the version-8 patterns that read them go dead -- which is a finding of
        its own and not what this test is about. What it asserts is the
        mismatch: ``38/40`` is not one of the agreement figure's spellings.
        """
        portability.require_the_same_libm()
        source = (PROJECT_ROOT / VERSION_EIGHT_CONTROL_DOCUMENT).read_text(
            encoding="utf-8"
        )
        altered = source.replace(
            VERSION_EIGHT_CONTROL_BEFORE, VERSION_EIGHT_CONTROL_AFTER
        )
        self.assertNotEqual(
            source,
            altered,
            "the control changed nothing in {0}".format(VERSION_EIGHT_CONTROL_DOCUMENT),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / VERSION_EIGHT_CONTROL_DOCUMENT
            target.write_text(altered, encoding="utf-8")
            found = check_figures.check(root)
        named = [mismatch for mismatch in found.mismatches if mismatch.value == "38/40"]
        self.assertTrue(
            named,
            "the altered version-8 figure was not reported: {0}".format(
                found.mismatches
            ),
        )
        for mismatch in named:
            with self.subTest(document=mismatch.document):
                self.assertEqual(VERSION_EIGHT_CONTROL_FIGURE, mismatch.figure)
                self.assertEqual("39/40", mismatch.expected)
        self.assertFalse(found.ok, "an altered figure left the check OK")

    def test_an_altered_version_eight_measurement_is_reported(self):
        """The version-8 measurement rows are shown capable of failing too.

        The copy holds the note alone, so the other documents are skipped and
        the figures that read them go dead -- a finding of its own and not what
        this test is about. What it asserts is the mismatch: ``27 of 40`` is not
        one of the ``decided with no person`` figure's spellings.
        """
        portability.require_the_same_libm()
        source = (PROJECT_ROOT / MEASUREMENT_CONTROL_DOCUMENT).read_text(
            encoding="utf-8"
        )
        altered = source.replace(
            MEASUREMENT_CONTROL_BEFORE, MEASUREMENT_CONTROL_AFTER
        )
        self.assertNotEqual(
            source,
            altered,
            "the control changed nothing in {0}".format(MEASUREMENT_CONTROL_DOCUMENT),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / MEASUREMENT_CONTROL_DOCUMENT
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(altered, encoding="utf-8")
            found = check_figures.check(root)
        named = [mismatch for mismatch in found.mismatches if mismatch.value == "27 of 40"]
        self.assertTrue(
            named,
            "the altered version-8 measurement was not reported: {0}".format(
                found.mismatches
            ),
        )
        for mismatch in named:
            with self.subTest(document=mismatch.document):
                self.assertEqual(MEASUREMENT_CONTROL_FIGURE, mismatch.figure)
                self.assertEqual("28 of 40", mismatch.expected)
        self.assertFalse(found.ok, "an altered figure left the check OK")

    def test_an_altered_version_eight_swap_on_the_front_page_is_reported(self):
        """The front page's version-8 swap figure is shown capable of failing.

        The copy holds ``ui/dist/index.html`` alone, so the figures that read the
        other documents go dead -- a finding of its own and not what this test is
        about. What it asserts is the mismatch: the page states 32 where the
        committed run's position swap says 33 of 34.
        """
        portability.require_the_same_libm()
        source = (PROJECT_ROOT / SWAP_CONTROL_DOCUMENT).read_text(encoding="utf-8")
        altered = source.replace(SWAP_CONTROL_BEFORE, SWAP_CONTROL_AFTER)
        self.assertNotEqual(
            source,
            altered,
            "the control changed nothing in {0}".format(SWAP_CONTROL_DOCUMENT),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / SWAP_CONTROL_DOCUMENT
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(altered, encoding="utf-8")
            found = check_figures.check(root)
        named = [mismatch for mismatch in found.mismatches if mismatch.value == "32"]
        self.assertTrue(
            named,
            "the altered version-8 swap was not reported: {0}".format(
                found.mismatches
            ),
        )
        for mismatch in named:
            with self.subTest(document=mismatch.document):
                self.assertEqual(SWAP_CONTROL_FIGURE, mismatch.figure)
                self.assertEqual("33 of 34", mismatch.expected)
        self.assertFalse(found.ok, "an altered figure left the check OK")

    def test_a_two_two_split_put_back_on_the_version_eight_row_is_reported(self):
        """The 2-2 claim is shown capable of firing on the version-8 row.

        The copy holds the README alone, so the figures that read other
        documents go dead -- a finding of its own and not what this test is
        about. What it asserts is the claim: a line naming ``ryde-v8`` and 903
        that says ``2-2`` is reported.
        """
        portability.require_the_same_libm()
        source = (PROJECT_ROOT / CLAIM_CONTROL_DOCUMENT).read_text(encoding="utf-8")
        altered = source.replace(CLAIM_CONTROL_BEFORE, CLAIM_CONTROL_AFTER)
        self.assertNotEqual(
            source,
            altered,
            "the control changed nothing in {0}".format(CLAIM_CONTROL_DOCUMENT),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / CLAIM_CONTROL_DOCUMENT
            target.write_text(altered, encoding="utf-8")
            found = check_figures.check(root)
        named = [hit for hit in found.claims if hit.claim == CLAIM_CONTROL_NAME]
        self.assertTrue(
            named,
            "the put-back claim was not reported: {0}".format(found.claims),
        )
        for hit in named:
            with self.subTest(document=hit.document):
                self.assertEqual(CLAIM_CONTROL_DOCUMENT, hit.document)
                self.assertIn("2-2", hit.line)
        self.assertFalse(found.ok, "a forbidden claim left the check OK")

    def test_the_fare_sentence_put_back_is_reported(self):
        """The fare claim is shown capable of firing.

        The copy holds ``tests/test_ryde_v7.py`` alone, so the figures that read
        other documents go dead -- a finding of its own and not what this test is
        about. What it asserts is the claim: a line that says v2.1 routes a fare
        dispute to a person is reported.
        """
        portability.require_the_same_libm()
        source = (PROJECT_ROOT / FARE_CLAIM_CONTROL_DOCUMENT).read_text(
            encoding="utf-8"
        )
        altered = source.replace(FARE_CLAIM_CONTROL_BEFORE, FARE_CLAIM_CONTROL_AFTER)
        self.assertNotEqual(
            source,
            altered,
            "the control changed nothing in {0}".format(FARE_CLAIM_CONTROL_DOCUMENT),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / FARE_CLAIM_CONTROL_DOCUMENT
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(altered, encoding="utf-8")
            found = check_figures.check(root)
        named = [hit for hit in found.claims if hit.claim == FARE_CLAIM_CONTROL_NAME]
        self.assertTrue(
            named,
            "the put-back fare claim was not reported: {0}".format(found.claims),
        )
        for hit in named:
            with self.subTest(document=hit.document):
                self.assertEqual(FARE_CLAIM_CONTROL_DOCUMENT, hit.document)
                self.assertIn("routes a fare dispute to a person", hit.line)
        self.assertFalse(found.ok, "a forbidden claim left the check OK")


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

    def test_every_claim_names_documents_and_a_forbidden_pattern(self):
        """A claim that reads nothing or forbids nothing checks nothing."""
        for claim in check_figures.CLAIMS:
            with self.subTest(claim=claim.name):
                self.assertTrue(claim.files, "the claim names no document")
                self.assertTrue(claim.forbidden, "the claim forbids nothing")
                for pattern in claim.forbidden:
                    re.compile(pattern)


if __name__ == "__main__":
    unittest.main()
