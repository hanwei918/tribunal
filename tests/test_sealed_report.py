"""The one command that prints a sealed set's figures, and what it prints.

Two sealed sets, two things to check. The held-out set has been run and its
figures are written down in ``docs/notes/2026-09-30-the-sealed-run.md``: this
reproduces every one of them from the committed files, so the note's numbers are
a measurement rather than a hand computation nobody can repeat. The second
sealed set has **not** been run, and against it the command prints one line and
nothing else.

The second of those is also the sealed-content rule made checkable: the key is
patched to raise, so a command that read it on the not-run path would fail here
rather than quietly doing what the rule forbids.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import grade, run_benchmark, sealed_report  # noqa: E402

MODEL = "deepseek/deepseek-flash"

# The not-run line, whole. It is asserted as one string rather than searched
# for, because the claim is that the command says this and says nothing else.
NOT_RUN_WILD_V2 = (
    "sealed set wild-v2 has not been run: "
    "nothing under runs/wild-v2/deepseek-deepseek-flash\n"
)


def run_report(*arguments):
    """One invocation of the command, and everything it printed."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = sealed_report.main(list(arguments))
    return code, buffer.getvalue()


class HeldOutFiguresTests(unittest.TestCase):
    """The committed ``runs/wild/`` record, reproduced.

    Every line below is a figure from ``docs/notes/2026-09-30-the-sealed-run.md``
    and the note is not changed by this: if one of these fails, the note and the
    command disagree about the same committed files, and that is a finding to
    report rather than a number to adjust.
    """

    def test_it_reproduces_the_figures_the_sealed_run_note_states(self):
        code, text = run_report("--set", "wild")
        self.assertEqual(0, code)

        for line in (
            # Four-field exact, both bases.
            "  over the 62 cases that produced a ruling: 55/62",
            "  over the 64 cases in the set, a case with no ruling as a miss: 55/64",
            # The ruling field alone, both bases.
            "  over the 62 cases that produced a ruling: 56/62",
            "  over the 64 cases in the set: 56/64",
            # Per category, both bases, from the set's own index.json.
            "  ROUTE_DEVIATION: 37 in the set, 35 produced; four-field 30/35 over "
            "produced and 30/37 over all",
            "  NO_SHOW_CHARGE: 27 in the set, 27 produced; four-field 25/27 over "
            "produced and 25/27 over all",
            # Escalation, both bases.
            "  over the 62 cases that produced a ruling: 7 produced, 4 expected, "
            "3 true positives; precision 3/7, recall 3/4",
            "  over the 64 cases in the set: 7 produced, 4 expected, "
            "3 true positives; precision 3/7, recall 3/4",
        ):
            with self.subTest(line=line):
                self.assertIn(line, text)

    def test_it_names_the_two_cases_that_produced_no_ruling_and_why(self):
        _, text = run_report("--set", "wild")
        self.assertIn("No ruling (2)", text)
        self.assertIn("  517: last failure kind SHAPE", text)
        self.assertIn("  533: last failure kind SHAPE", text)

    def test_it_prints_no_corpus_target_beside_a_sealed_set(self):
        """``TARGET_ESCALATION_RATE`` is the corpus's, and the set is not."""
        _, text = run_report("--set", "wild")
        self.assertNotIn("TARGET_ESCALATION_RATE", text)
        self.assertNotIn("target", text.lower())


class UnRunSealedSetTests(unittest.TestCase):
    """The second sealed set, before its run."""

    def test_the_un_run_second_sealed_set_prints_one_line_and_nothing_else(self):
        # The key is patched to raise, so the whole-output assertion below is
        # also the proof that the not-run path reads no key: a command that
        # loaded it would fail here rather than print this line.
        with mock.patch.object(
            grade, "load_answer_key", side_effect=AssertionError("the key was read")
        ):
            code, text = run_report("--set", "wild-v2")
        self.assertEqual(0, code)
        self.assertEqual(NOT_RUN_WILD_V2, text)

    def test_a_development_set_is_refused_rather_than_reported(self):
        """The command prints no corpus target, so it is sealed sets only."""
        with self.assertRaises(run_benchmark.BenchmarkError) as caught:
            sealed_report.main(["--set", "codex"])
        self.assertIn("not a sealed set", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
