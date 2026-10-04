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

The note's two misses are read out of the run and the key as well: the vote's
proposals, agreements and kinds, the artifact weights, the cancellation and
last-fix times, the published remedy and the dispute's contested amount. Each
corrected sentence in the note is pinned to the record it was corrected against,
so a note that drifted back to the earlier wording fails here.

Prose is compared as whitespace-normalised text -- the note wraps its lines, and
a sentence that reads the same at any column is the same sentence -- while the
table rows are compared whole, because a table row is one line by construction.

The note's own path can be overridden with ``TRIBUNAL_SECOND_SEALED_NOTE``, which
is how these assertions are shown to fail on an edited copy of the note rather
than merely to pass on the note as committed.

**No model call is made.** Every reading is a committed run and a frozen key.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark  # noqa: E402
from tribunal import brief, pipeline  # noqa: E402

# The note under test. The override exists so an edited copy can be checked
# against the same assertions; the committed note is the default.
NOTE_ENV = "TRIBUNAL_SECOND_SEALED_NOTE"
NOTE_DEFAULT = (
    PROJECT_ROOT / "docs" / "notes" / "2026-10-04-the-second-sealed-run.md"
)
NOTE = Path(os.environ.get(NOTE_ENV) or NOTE_DEFAULT)

MODEL = run_benchmark.resolve_model(None)
SET = development_sets.named("wild-v2")

# The two-sided 95% normal quantile. It is a literal because it *is* the "95%",
# not a measurement: what is measured is the interval it produces.
Z_95 = 1.959963984540054

# Every "N.NNN to N.NNN" interval string the note states must be one of the two
# this module computes.
INTERVAL_PATTERN = re.compile(r"\d+\.\d{3} to \d+\.\d{3}")


def prose(text):
    """The note's text with every run of whitespace collapsed to one space.

    The note wraps its prose at about eighty columns, so a sentence that spans
    two lines is one sentence; comparing the wrapped bytes would fail on a line
    break rather than on a wrong statement.
    """
    return " ".join(text.split())


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


def interval_string(successes, total):
    """The interval exactly as the note states it: ``0.699 to 0.972``."""
    low, high = wilson_interval(successes, total)
    return "{0} to {1}".format(three_places(low), three_places(high))


def interval_row(label, successes, total):
    """The whole table row, built from the counts rather than transcribed."""
    return "| {0} | {1}/{2} = {3}% | **{4}** |".format(
        label,
        successes,
        total,
        "{0:.1f}".format(100.0 * successes / total),
        interval_string(successes, total),
    )


def transcript_of(case_no):
    """One case's committed transcript, as the run wrote it."""
    return json.loads(
        Path(run_benchmark.transcript_path(SET.run_dir(MODEL), case_no)).read_text(
            encoding="utf-8"
        )
    )


def document_of(case_no):
    """One case's committed result document, as the run wrote it."""
    return run_benchmark.load_cached(SET.run_dir(MODEL), case_no)


def case_of(case_no):
    return SET.load_case(case_no)


def money_block_of(case_no):
    """The brief's money block for one case, rebuilt from the case and the policy."""
    built = brief.build_brief_for_case(case_of(case_no), policy_version=SET.policy_version)
    return pipeline.money_block(built)


def evidence_of(case_no):
    return {item["evidence_id"]: item for item in case_of(case_no)["evidence"]}


def key_rationale_of(case_no):
    """The rationale the imported key carries, which the dataclass does not hold."""
    raw = json.loads(
        (PROJECT_ROOT / "eval" / "answers" / "wild-v2" / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in raw:
        if entry.get("case_no") == case_no:
            return entry["ground_truth"]["rationale"]
    raise AssertionError("the key has no case {0}".format(case_no))


def judge_entries(case_no):
    return [e for e in transcript_of(case_no)["entries"] if e.get("role") == "JUDGE"]


def blockquotes(text):
    """Every contiguous ``> `` block in the note, as one whitespace-normalised line."""
    blocks = []
    current = []
    for line in text.splitlines():
        if line.startswith(">"):
            current.append(line.lstrip(">").strip())
        elif current:
            blocks.append(" ".join(" ".join(current).split()))
            current = []
    if current:
        blocks.append(" ".join(" ".join(current).split()))
    return blocks


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
        cls.prose = prose(cls.text)
        cls.wild_v2 = graded("wild-v2")
        cls.wild = graded("wild")
        cls.total_v2 = len(development_sets.named("wild-v2").cases)
        cls.total_wild = len(development_sets.named("wild").cases)
        cls.rows = (
            interval_row(
                "`wild-v2` (this run)", cls.wild_v2.exact_matches, cls.total_v2
            ),
            interval_row(
                "`wild-v1` (the held-out set)", cls.wild.exact_matches, cls.total_wild
            ),
        )
        cls.interval_strings = (
            interval_string(cls.wild_v2.exact_matches, cls.total_v2),
            interval_string(cls.wild.exact_matches, cls.total_wild),
        )

    def test_the_second_sets_two_figures_are_the_committed_runs(self):
        self.assertEqual(18, self.wild_v2.exact_matches)
        self.assertEqual(
            20,
            self.total_v2,
            "the second sealed set no longer holds 20 cases",
        )

    def test_the_held_out_sets_two_figures_are_the_committed_runs(self):
        self.assertEqual(55, self.wild.exact_matches)
        self.assertEqual(
            64,
            self.total_wild,
            "the held-out set no longer holds 64 cases",
        )

    def test_the_note_states_the_second_sets_interval_and_it_is_the_computed_one(self):
        low, high = wilson_interval(18, 20)
        self.assertIn(
            "{0} to {1}".format(three_places(low), three_places(high)),
            self.prose,
            "the note does not state the interval this run's 18/20 computes to",
        )

    def test_the_note_states_the_held_out_sets_interval_and_it_is_the_computed_one(self):
        low, high = wilson_interval(55, 64)
        self.assertIn(
            "{0} to {1}".format(three_places(low), three_places(high)),
            self.prose,
            "the note does not state the interval wild-v1's 55/64 computes to",
        )

    def test_the_note_states_both_interval_rows_exactly(self):
        """The whole row, from the counts: a figure that drifts fails here.

        A table row is one line in the note, so it is compared against the note's
        own bytes rather than against the whitespace-normalised prose.
        """
        for row in self.rows:
            with self.subTest(row=row):
                self.assertIn(
                    row,
                    self.text,
                    "the note does not state this row, built from the counts",
                )
        self.assertNotEqual(self.rows[0], self.rows[1])

    def test_every_interval_string_in_the_note_is_one_of_the_two_computed_intervals(self):
        """No "N to M" in the note that this module does not recompute.

        The note states its interval in the table and again in the prose, and
        both must be the computed one. A third, invented interval fails here.
        """
        found = set(INTERVAL_PATTERN.findall(self.text))
        self.assertTrue(found, "the note states no interval")
        self.assertEqual(
            set(self.interval_strings),
            found,
            "the note states an interval that is not one of the two computed ones",
        )

    def test_the_two_intervals_are_not_the_same_number(self):
        """A copy-paste that left one interval in both places would pass above."""
        self.assertNotEqual(
            three_places(wilson_interval(18, 20)[0]),
            three_places(wilson_interval(55, 64)[0]),
        )

    def test_the_note_says_the_two_figures_are_never_summed_or_pooled(self):
        self.assertIn("never summed or pooled", self.prose)
        # And says what pooling them would be, rather than only forbidding it.
        self.assertIn("not a measurement of 84 cases", self.prose)

    def test_the_note_names_both_freezes_beside_the_two_figures(self):
        self.assertIn("freeze-2026-10-03", self.prose)
        self.assertIn("freeze-2026-09-30", self.prose)


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


class TheNotes702Tests(unittest.TestCase):
    """702's corrected paragraph, pinned to the vote, the money block and the case.

    The note used to say the read-off check kept a wrong refund from being paid
    and that no draft found the right figure. The record says otherwise: the
    money block published the right figure, 8.60 is the dispute's contested
    amount, and the quorum -- not the check -- kept the refund from being paid.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.prose = prose(cls.text)
        cls.vote = transcript_of(702)["vote"]
        cls.drafts = {d["draft"]: d for d in cls.vote["drafts"]}
        cls.document = document_of(702)
        cls.money = money_block_of(702)
        cls.case = case_of(702)

    def test_the_money_block_published_the_remedy_the_note_states(self):
        self.assertEqual("0.00", self.money["pol_rd_11_remedy"]["value"])
        self.assertEqual("22.40", self.money["charged_total"]["value"])
        self.assertEqual("22.40", self.money["quoted_fare"]["value"])
        self.assertEqual("0.00", self.money["charged_over_quote"]["value"])
        self.assertIn("pol_rd_11_remedy", self.prose)
        self.assertIn("published the right figure", self.prose)

    def test_the_rebuilt_brief_matches_the_recorded_sha256(self):
        rebuilt = run_benchmark.current_brief_sha256(
            702, case_loader=SET.load_case, policy_version=SET.policy_version
        )
        self.assertEqual(self.document["brief_sha256"], rebuilt)
        self.assertIsNotNone(rebuilt)
        self.assertIn("brief_sha256", self.prose)

    def test_860_is_the_disputes_contested_amount_not_an_inference(self):
        self.assertEqual(Decimal("8.6"), self.case["dispute"]["amount_contested_sgd"])
        self.assertIn("amount_contested_sgd", self.prose)
        self.assertIn("not an inference", self.prose)

    def test_the_two_rejected_drafts_proposed_a_full_refund_of_8_60(self):
        """The vote abstains, but the drafts behind it proposed 8.60."""
        judges = judge_entries(702)
        for entry in judges[:2]:
            ruling = entry["parsed"]["ruling"]
            self.assertEqual("FULL_REFUND", ruling["ruling"])
            self.assertEqual(Decimal("8.6"), Decimal(str(ruling["amount_sgd"])))

    def test_the_vote_is_the_quorum_and_the_abstentions_the_note_states(self):
        self.assertEqual(3, self.vote["threshold"])
        self.assertEqual(2, self.vote["valid"])
        self.assertEqual(4, self.vote["votes"])
        self.assertEqual("escalated", self.vote["outcome"])
        self.assertFalse(self.vote["unanimous"])

    def test_the_four_drafts_proposed_what_the_note_says(self):
        self.assertEqual("sampled", self.drafts[1]["kind"])
        self.assertEqual("sampled", self.drafts[2]["kind"])
        self.assertEqual("sampled", self.drafts[3]["kind"])
        self.assertEqual("position_swapped", self.drafts[4]["kind"])
        # The two 8.60 drafts abstained, on the read-off check.
        self.assertFalse(self.drafts[1]["valid"])
        self.assertFalse(self.drafts[2]["valid"])
        self.assertIsNone(self.drafts[1]["proposal"])
        self.assertIsNone(self.drafts[2]["proposal"])
        self.assertTrue(
            self.drafts[1]["abstention"].startswith("DRAFT_AMOUNT_NOT_READ_OFF")
        )
        self.assertTrue(
            self.drafts[2]["abstention"].startswith("DRAFT_AMOUNT_NOT_READ_OFF")
        )
        self.assertIn("amount_sgd=8.6", self.drafts[1]["abstention"])
        self.assertIn("amount_sgd=8.60", self.drafts[2]["abstention"])
        # Draft 3 is the correct answer and carried nothing on its own.
        self.assertEqual("NO_ACTION", self.drafts[3]["proposal"]["ruling"])
        self.assertIs(self.drafts[3]["agrees"], True)
        # Draft 4 escalated under POL-RD-10(7).
        self.assertEqual("ESCALATE", self.drafts[4]["proposal"]["ruling"])
        self.assertIs(self.drafts[4]["agrees"], False)

    def test_the_note_says_the_quorum_kept_the_refund(self):
        self.assertIn("The quorum, not the read-off check, kept the refund", self.prose)

    def test_the_note_no_longer_blames_the_read_off_check(self):
        """The three sentences the record contradicted, gone."""
        self.assertNotIn("no draft found the right figure", self.prose)
        self.assertNotIn("This is an inference from the case's own figures", self.prose)
        self.assertNotIn(
            "a draft check that could not express the right figure", self.prose
        )


class TheNotes716Tests(unittest.TestCase):
    """716's corrected section, pinned to the vote, the weights and the key.

    The note used to attribute "decisive proof for a monetary award" to the
    clause. It is the key's rationale. The clause says the confidence cap is the
    minimum weight among the artifacts that carry the deciding fact, and the note
    now quotes it that way.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.prose = prose(cls.text)
        cls.vote = transcript_of(716)["vote"]
        cls.drafts = {d["draft"]: d for d in cls.vote["drafts"]}
        cls.money = money_block_of(716)
        cls.case = case_of(716)
        cls.evidence = evidence_of(716)
        cls.rationale = key_rationale_of(716)

    def test_the_dissent_is_sampled_draft_2(self):
        self.assertEqual("sampled", self.drafts[2]["kind"])
        self.assertEqual("ESCALATE", self.drafts[2]["proposal"]["ruling"])
        self.assertIs(self.drafts[2]["agrees"], False)
        self.assertEqual(
            1,
            sum(1 for d in self.vote["drafts"] if d["agrees"] is False),
            "more than one draft dissented, so 'the dissent was draft 2' is wrong",
        )

    def test_the_position_swapped_draft_voted_with_the_majority(self):
        self.assertEqual("position_swapped", self.drafts[4]["kind"])
        self.assertEqual("NO_ACTION", self.drafts[4]["proposal"]["ruling"])
        self.assertIs(self.drafts[4]["agrees"], True)

    def test_the_vote_is_the_three_to_one_the_note_states(self):
        self.assertEqual(0.75, self.vote["agreement"])
        self.assertEqual("carried_not_unanimous", self.vote["outcome"])
        self.assertEqual(4, self.vote["valid"])
        self.assertEqual(4, self.vote["votes"])
        self.assertEqual(3, self.vote["threshold"])

    def test_the_weights_are_what_the_note_states(self):
        self.assertEqual(
            Decimal("0.30"),
            self.evidence["EV-TRIP-00716"]["admissibility"]["weight_multiplier"],
        )
        self.assertEqual(
            Decimal("0.25"),
            self.evidence["EV-GPS-00716"]["admissibility"]["weight_multiplier"],
        )
        self.assertEqual(
            Decimal("1.0"),
            self.evidence["EV-FARE-00716"]["admissibility"]["weight_multiplier"],
        )
        self.assertIn("0.30", self.prose)
        self.assertIn("0.25", self.prose)

    def test_the_cancellation_and_the_last_fix_are_16_minutes_apart(self):
        """The two timestamps the note reads, and the gap between them."""
        trip = self.evidence["EV-TRIP-00716"]["payload"]
        gps = self.evidence["EV-GPS-00716"]["payload"]
        self.assertEqual("2026-09-25T13:27:40+08:00", trip["cancelled_at"])
        self.assertEqual("2026-09-25T13:43:40+08:00", gps["last_fix_at"])
        self.assertIn("13:27:40", self.prose)
        self.assertIn("13:43:40", self.prose)
        self.assertIn("16 minutes", self.prose)

    def test_the_published_remedy_and_the_contested_amount(self):
        self.assertEqual("0.00", self.money["pol_rd_11_remedy"]["value"])
        self.assertEqual("21.40", self.money["quoted_fare"]["value"])
        self.assertEqual(Decimal("21.4"), self.case["dispute"]["amount_contested_sgd"])

    def test_the_key_rationale_is_where_the_decisive_proof_phrase_lives(self):
        self.assertIn("decisive proof for a monetary award", self.rationale)
        general = json.loads(
            (PROJECT_ROOT / "policy" / "general.json").read_text(encoding="utf-8")
        )
        clause = next(c for c in general["clauses"] if c["id"] == "POL-GEN-02")
        self.assertNotIn("decisive proof for a monetary award", clause["rule"])
        self.assertIn("That phrase is the rationale's, not the clause's.", self.prose)

    def test_the_note_quotes_pol_gen_02_2_as_written(self):
        self.assertIn(
            "the minimum weight_multiplier among the artifacts that carry the deciding fact",
            self.prose,
        )

    def test_the_note_says_the_judge_and_the_key_differ_about_the_deciding_fact(self):
        self.assertIn(
            "The judge and the key differ about what the deciding fact is", self.prose
        )
        self.assertIn("billable trip ran", self.prose)


class TheNotesSentencesTests(unittest.TestCase):
    """The three sentences the sheet corrects, and the record behind each."""

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.prose = prose(cls.text)

    def test_the_note_no_longer_says_no_failure_of_any_kind(self):
        self.assertNotIn("no failure of any kind", self.prose)
        # The record: no case failed.
        run = json.loads((SET.run_dir(MODEL) / "run.json").read_text(encoding="utf-8"))
        self.assertEqual([], run["failures"])
        self.assertIn("failures: []", self.prose)

    def test_the_note_records_the_four_re_asks(self):
        """Four judge answers were unusable and re-asked inside their case."""
        re_asks = {}
        for case_no in SET.cases:
            drafts = transcript_of(case_no)["vote"]["drafts"]
            extra = sum(1 for d in drafts if len(d.get("entries") or []) > 1)
            if extra:
                re_asks[case_no] = extra
        self.assertEqual({701: 2, 708: 1, 718: 1}, re_asks)
        self.assertIn("one in-call retry", self.prose)
        self.assertIn("701 twice", self.prose)
        self.assertIn("708", self.prose)
        self.assertIn("718", self.prose)

    def test_the_note_no_longer_claims_no_model_call_was_made_in_this_repository(self):
        self.assertNotIn("no model call was made in this repository", self.prose)
        self.assertIn("The owner's run made the model calls", self.prose)

    def test_the_owners_record_is_marked_as_such(self):
        """The ping, the --check output and the gate exit are the owner's."""
        self.assertGreaterEqual(self.prose.count("as the owner recorded it"), 3)


class TheNotesBlockquotesTests(unittest.TestCase):
    """Every blockquote is the transcript's own words, apart from whitespace."""

    @classmethod
    def setUpClass(cls):
        cls.text = NOTE.read_text(encoding="utf-8")
        cls.transcript = " ".join(
            " ".join(
                str(e.get("parsed", {}).get("ruling", {}).get("explanation", "")).split()
            )
            for e in judge_entries(716)
        )

    def test_the_note_has_blockquotes(self):
        self.assertTrue(blockquotes(self.text), "the note has no blockquote")

    def test_every_blockquote_is_verbatim_from_the_transcript(self):
        for block in blockquotes(self.text):
            with self.subTest(block=block[:60]):
                self.assertIn(
                    block,
                    self.transcript,
                    "a blockquote is not the transcript's text, apart from whitespace",
                )


if __name__ == "__main__":
    unittest.main()
