"""The note that reads the second sealed set's single run, and its two intervals.

``docs/notes/2026-10-04-the-second-sealed-run.md`` states two figures with an
interval each -- ``wild-v2``'s 18/20 and ``wild-v1``'s 55/64 -- and says the two
are never summed or pooled. A hand-computed interval is a number nobody can
check, so this module recomputes both from the committed runs and compares them
with what the note states: **no bound in the note is typed into this module**, and
a bound that drifts fails here rather than reading as a measurement.

The denominator is the set's own case list, not the count that produced a ruling.
That is the honest denominator for a generalisation figure -- a case the system
could not decide is not a case it decided correctly -- and it is what makes
``wild-v1``'s 55/62 into the 55/64 the note reports.

The Wilson formula itself is checked here too, on properties a wrong formula
would not have, because a formula that is quietly wrong would produce two
plausible intervals and no failure.

**No model call is made.** Every reading is a committed run and a frozen key.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark  # noqa: E402

NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-04-the-second-sealed-run.md"
MODEL = run_benchmark.resolve_model(None)

# The two-sided 95% normal quantile. It is a literal because it *is* the "95%",
# not a measurement: what is measured is the interval it produces.
Z_95 = 1.959963984540054


def wilson_interval(successes, total, z=Z_95):
    """The Wilson score interval for a binomial proportion, as ``(low, high)``.

    The score interval rather than the normal approximation, because at n = 20
    the normal approximation runs outside the unit interval at the edges and is
    not what a figure this small should be quoted with.
    """
    if total <= 0:
        raise ValueError("a proportion needs a positive denominator")
    if not 0 <= successes <= total:
        raise ValueError("a count outside 0..total is not a proportion")
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    half = (z / denominator) * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return centre - half, centre + half


def three_places(value):
    """A bound as the note states it: three decimal places, rounded half up."""
    return "{0:.3f}".format(value)


def graded(set_name):
    """One committed sealed run, graded against its own frozen key."""
    development_set = development_sets.named(set_name)
    return run_benchmark.grade_run(
        development_set.run_dir(MODEL),
        development_set.key(),
        case_loader=development_set.load_case,
    )


class WilsonFormulaTests(unittest.TestCase):
    """The formula, on facts a wrong one would get wrong.

    None of these asserts an interval for a figure in the note: they pin the
    function the note's intervals come from, so that the interval tests below
    cannot pass on a formula that happens to be wrong in a compensating way.
    """

    def test_the_interval_contains_the_estimate(self):
        """Including at the edges, where the estimate sits on a bound."""
        for successes, total in ((18, 20), (55, 64), (0, 20), (20, 20), (1, 3)):
            with self.subTest(successes=successes, total=total):
                low, high = wilson_interval(successes, total)
                self.assertLessEqual(low, successes / total)
                self.assertGreaterEqual(high, successes / total)

    def test_the_interval_stays_inside_the_unit_interval(self):
        """At n = 20 the normal approximation leaves (0, 1); this one does not.

        The cases are one and two successes out of twenty and their mirrors,
        because that is where the two intervals come apart: the score interval
        stays strictly inside the unit interval there while the normal
        approximation's bound is outside it, which is why the figure in the note
        is quoted with this interval and not with that one. At zero and at
        twenty out of twenty both intervals touch the bound, so neither case
        says anything about the difference.
        """
        for successes, total in ((1, 20), (2, 20), (18, 20), (19, 20)):
            with self.subTest(successes=successes, total=total):
                proportion = successes / total
                half = Z_95 * math.sqrt(proportion * (1 - proportion) / total)
                self.assertTrue(
                    proportion - half < 0.0 or proportion + half > 1.0,
                    "the normal approximation stays inside (0, 1) here, so this "
                    "case does not show what the score interval is for",
                )
                low, high = wilson_interval(successes, total)
                self.assertGreater(low, 0.0)
                self.assertLess(high, 1.0)

    def test_a_half_estimate_gives_a_symmetric_interval(self):
        low, high = wilson_interval(10, 20)
        self.assertAlmostEqual(0.5, (low + high) / 2, places=12)
        self.assertAlmostEqual(0.5 - low, high - 0.5, places=12)

    def test_more_cases_narrow_the_interval_at_the_same_proportion(self):
        narrow = wilson_interval(900, 1000)
        wide = wilson_interval(9, 10)
        self.assertLess(narrow[1] - narrow[0], wide[1] - wide[0])

    def test_it_approaches_the_normal_approximation_as_the_sample_grows(self):
        """The one external check: at a large n the two must agree.

        A formula that returned, say, the estimate plus and minus a fixed amount
        would satisfy every property above and fail here.
        """
        successes, total = 900_000, 1_000_000
        proportion = successes / total
        half = Z_95 * math.sqrt(proportion * (1 - proportion) / total)
        low, high = wilson_interval(successes, total)
        self.assertAlmostEqual(proportion - half, low, places=5)
        self.assertAlmostEqual(proportion + half, high, places=5)


class TheNotesIntervalsTests(unittest.TestCase):
    """The note's two intervals, recomputed from the committed runs.

    Each figure is read out of its own committed run and its own frozen key, so
    the note's numbers are a measurement of the files rather than a transcription
    of them. A disagreement here is a finding to report, not a number to adjust.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.wild_v2 = graded("wild-v2")
        cls.wild = graded("wild")

    def test_the_second_sets_two_figures_are_the_committed_runs(self):
        self.assertEqual(18, self.wild_v2.exact_matches)
        self.assertEqual(
            20,
            len(development_sets.named("wild-v2").cases),
            "the second sealed set no longer holds 20 cases",
        )

    def test_the_held_out_sets_two_figures_are_the_committed_runs(self):
        self.assertEqual(55, self.wild.exact_matches)
        self.assertEqual(
            64,
            len(development_sets.named("wild").cases),
            "the held-out set no longer holds 64 cases",
        )

    def test_the_note_states_the_second_sets_interval_and_it_is_the_computed_one(self):
        low, high = wilson_interval(18, 20)
        self.assertIn(
            "{0} to {1}".format(three_places(low), three_places(high)),
            self.text,
            "the note does not state the interval this run's 18/20 computes to",
        )

    def test_the_note_states_the_held_out_sets_interval_and_it_is_the_computed_one(self):
        low, high = wilson_interval(55, 64)
        self.assertIn(
            "{0} to {1}".format(three_places(low), three_places(high)),
            self.text,
            "the note does not state the interval wild-v1's 55/64 computes to",
        )

    def test_the_two_intervals_are_not_the_same_number(self):
        """A copy-paste that left one interval in both places would pass above."""
        self.assertNotEqual(
            three_places(wilson_interval(18, 20)[0]),
            three_places(wilson_interval(55, 64)[0]),
        )

    def test_the_note_says_the_two_figures_are_never_summed_or_pooled(self):
        self.assertIn("never summed or pooled", self.text)
        # And says what pooling them would be, rather than only forbidding it.
        self.assertIn("not a measurement of 84 cases", self.text)

    def test_the_note_names_both_freezes_beside_the_two_figures(self):
        self.assertIn("freeze-2026-10-03", self.text)
        self.assertIn("freeze-2026-09-30", self.text)


class TheNotesTwoMissesTests(unittest.TestCase):
    """The two misses the note reads, against the committed run and the key.

    The note calls 702 an over-escalation and 716 an under-escalation. Both are
    facts about the run and the key, so both are checked rather than described:
    a note that had the two the wrong way round would read as a different finding.
    """

    @classmethod
    def setUpClass(cls):
        cls.key = development_sets.named("wild-v2").key()

    def test_702_is_the_over_escalation(self):
        self.assertEqual("NO_ACTION", self.key[702].ruling)
        document = run_benchmark.load_cached(
            development_sets.named("wild-v2").run_dir(MODEL), 702
        )
        self.assertEqual("ESCALATE", document["ruling"]["ruling"]["ruling"])

    def test_716_is_the_under_escalation(self):
        self.assertEqual("ESCALATE", self.key[716].ruling)
        document = run_benchmark.load_cached(
            development_sets.named("wild-v2").run_dir(MODEL), 716
        )
        self.assertEqual("NO_ACTION", document["ruling"]["ruling"]["ruling"])

    def test_the_note_names_both_cases(self):
        text = NOTE.read_text(encoding="utf-8")
        self.assertIn("**702**", text)
        self.assertIn("**716**", text)


if __name__ == "__main__":
    unittest.main()
