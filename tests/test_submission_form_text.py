"""The description as plain text for the submission form.

``docs/submission/description.md`` is written for a reader of the repository: it
carries an HTML comment naming each sentence's source, and the form's own four
headings are written as Markdown. The submission form takes plain text, so
``docs/submission/description-form.txt`` is the same description with the
comments, the emphasis and the heading markers taken out and every URL written
in full. This module holds the two files to that relationship, because a form
text that has drifted from the description is a claim nothing checks.

Three things are asserted, and each is something that would show in the form as
a symbol or as a stale figure:

* **No HTML comment.** ``<!--`` is markup, and the form would print it.
* **No placeholder URL.** The description used to carry the address as
  ``<repository URL>``; the form must carry the address itself.
* **No number the description does not also carry.** This is the strongest of
  the three -- a number that appears in the form and nowhere in the description
  came from somewhere other than the description -- and it is checked over every
  run of digits, so a figure that was retyped rather than copied fails here.

The third check is shown capable of failing, on a copy of the description with
one figure taken out of it, for the reason ``START-HERE.md`` gives: a guard
nobody has seen fail is not evidence of anything.

No model call is made, no browser is launched, and nothing is written. Run from
the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = PROJECT_ROOT / "docs" / "submission" / "description.md"
FORM_TEXT = PROJECT_ROOT / "docs" / "submission" / "description-form.txt"

# The placeholder the description carried until the repository's address was
# known. The form must carry the address itself, not this.
PLACEHOLDER = "<" + "repository URL>"

# The address the description and the form both carry.
REPOSITORY_URL = "https://github.com/hanwei918/tribunal"

# Every run of digits in a document, which is the unit a figure is compared in:
# ``0.0579`` is the two runs ``0`` and ``0579``, and each must be findable in the
# description rather than only in the form.
DIGITS = re.compile(r"\d+")


def numbers(text: str) -> List[str]:
    """Every run of digits in a document, in the order it appears."""
    return DIGITS.findall(text)


def missing_from_description(form: str, description: str) -> List[str]:
    """The digit runs the form carries that the description does not.

    A run is present when it appears **anywhere** in the description, so this is
    a containment check over the whole document and not a figure-by-figure
    comparison: the form is a re-rendering of the description, not a second
    measurement of it, and a figure that moved to a different sentence is still
    the description's figure.
    """
    return sorted({value for value in numbers(form) if value not in description})


class TheFormTextTests(unittest.TestCase):
    """The plain-text form of the description, and what it must not carry."""

    def setUp(self):
        self.form = FORM_TEXT.read_text(encoding="utf-8")
        self.description = DESCRIPTION.read_text(encoding="utf-8")

    def test_it_carries_no_html_comment(self):
        self.assertNotIn("<!--", self.form)

    def test_it_carries_the_repository_url_and_not_the_placeholder(self):
        self.assertNotIn(PLACEHOLDER, self.form)
        self.assertIn(REPOSITORY_URL, self.form)

    def test_every_number_in_it_also_appears_in_the_description(self):
        self.assertEqual([], missing_from_description(self.form, self.description))

    # Part 55 adds one table to the description: the brief's four pain points,
    # each against the figure the record holds for it. The form carries the same
    # four rows, because a form that dropped one would be a claim the description
    # makes and the submitted text does not.
    def test_it_carries_the_pain_point_table_the_description_carries(self):
        for pain_point in ("Cost", "Speed", "Inconsistency", "User churn"):
            with self.subTest(pain_point=pain_point):
                self.assertIn(pain_point, self.description)
                self.assertIn(pain_point, self.form)

    def test_the_documents_really_carry_the_numbers_it_checks(self):
        """A control: the search is against text that is there, not a blank."""
        self.assertTrue(numbers(self.form))
        self.assertTrue(numbers(self.description))
        self.assertIn("0579", self.form)

    def test_a_number_taken_out_of_the_description_is_reported(self):
        """The check above is shown capable of failing."""
        doctored = self.description.replace("0.0579", "a few cents")
        self.assertEqual(["0579"], missing_from_description(self.form, doctored))


if __name__ == "__main__":
    unittest.main()
