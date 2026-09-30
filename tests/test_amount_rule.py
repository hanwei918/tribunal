"""The amount read-off rule, and the measurement that asks what it would change.

``published`` is the rule every run so far was judged by: a draft's amount is a
figure the brief's money block publishes, or the **sum** of two or three of
them, and never a difference. Two of the held-out set's cases died on exactly
that -- 517 and 533 published no ruling because every one of their four drafts
computed a difference, and the drafts were right about the money.

``--amount-rule signed`` adds a difference. It is off by default, and the first
thing this file proves is that **off is byte-identical**: a run that names the
default and a run that names nothing write the same bytes.

The rest is the three things that make the switch safe to have. It is refused
beside every other switch that changes what a run measures, and beside every
mode that reads or reports a run judged by the published rule. A run under it
cannot be written into a headline run directory. And the measurement in
:mod:`eval.amount_rule` re-reduces the drafts three runs already recorded, so
the comparison is between two readings of one panel rather than between two
samplings of the judge -- which is why 501 can be named, from the committed
held-out run, as a case the signed rule would have decided wrongly.

Nothing here reaches a model.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import amount_rule, development_sets  # noqa: E402
from eval import run_benchmark as runner  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import brief, llm, pipeline, transcript  # noqa: E402
from tribunal.model import resolve_model  # noqa: E402

# The rig's model, which is deliberately not the headline one: a fixture run
# must never be able to land in a directory a recorded run lives in.
MODEL = rig.MODEL
PROMPTS_DIR = rig.PROMPTS_DIR

# The model the recorded runs were made under, read from the one place that
# declares it rather than repeated here.
HEADLINE_MODEL = resolve_model(None)
CORPUS_RUN_DIR = runner.RUNS_DIR / runner.model_slug(HEADLINE_MODEL)
CODEX_RUN_DIR = runner.RUNS_DIR / "codex" / runner.model_slug(HEADLINE_MODEL)
WILD_RUN_DIR = runner.RUNS_DIR / "wild" / runner.model_slug(HEADLINE_MODEL)

# The three held-out cases this rule is about. 501 and 533 are the two the
# sealed run's README names as dying on ``SHAPE``; 517 is the one neither rule
# can read, and it is here so that "the signed rule fixes everything" is not
# the claim a reader takes away.
TURNED_UNSAFE_CASE = 501
TURNED_MATCHING_CASE = 533
UNREADABLE_BOTH_WAYS_CASE = 517
# A case of the same run that nothing changes, for the agreement check.
UNCHANGED_CASE = 502

# A case whose money block publishes two figures whose difference is not a
# figure and not a sum: ``schedule_fee.value 4.00 - driver_compensation.value
# 3.20 = 0.80``. The premise is asserted in the test that uses it, so a case
# that stops publishing those two moves the test rather than passing it.
DIFFERENCE_CASE = 201
DIFFERENCE_AMOUNT = Decimal("0.80")

# The fixture's pinned clock: two runs of the same cases are byte-identical
# only if the timestamps are the same ones.
FIXED_NOW = "2026-09-30T00:00:00+00:00"

# The figures a money block publishes, as ``amount_reads_off`` receives them.
# The numbers are 533's own shape -- a charge, the pass-through inside it, and
# the fare -- so the readings below are the readings that case needed.
FIGURES = (
    ("charged_over_quote.value", Decimal("51.30")),
    ("erp_lines.off_optimal_route_total.value", Decimal("29.00")),
    ("erp_lines.lines[0].amount_sgd.value", Decimal("3.00")),
    ("schedule_fee.value", Decimal("4.00")),
)


def quiet(call):
    """A call with both of its streams suppressed, for a test asserting a code."""
    with contextlib.redirect_stdout(io.StringIO()):
        with contextlib.redirect_stderr(io.StringIO()):
            return call()


class PinnedDatetime:
    """``datetime`` with ``now`` pinned.

    Three modules stamp a wall clock into what a run writes and none of them
    takes the ``now`` callable the rest of the run takes: ``eval.run_benchmark``
    writes ``recorded_at`` with ``datetime.now``, ``tribunal.llm`` stamps every
    call it records the same way, and ``tribunal.transcript`` stamps every entry
    the same way again. This is that clock, pinned -- the same pinning the
    transcript tests do, applied to the three places the modules stamp their own
    time.
    """

    @staticmethod
    def now(tz=None):
        return datetime(2026, 9, 30, tzinfo=timezone.utc)


@contextlib.contextmanager
def pinned_clocks():
    """Every clock a fixture run stamps into its artifacts, pinned at once.

    The runner's ``now`` callable reaches the metadata, the event log and the
    invocation history, but not the three wall clocks above, and not
    ``wall_seconds``, which ``run_one_case`` measures with ``time.monotonic``.
    A byte-identity claim about a run has to pin all four; without them the two
    runs differ in the clock and in nothing else, and the test would be
    asserting a claim it could not make.
    """
    with mock.patch.object(llm, "datetime", PinnedDatetime):
        with mock.patch.object(runner, "datetime", PinnedDatetime):
            with mock.patch.object(transcript, "datetime", PinnedDatetime):
                with mock.patch.object(runner.time, "monotonic", lambda: 0.0):
                    yield


def digests(root):
    """``{relative path: sha256}`` for every file under one directory."""
    root = Path(root)
    return {
        str(path.relative_to(root)): runner.file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def a_brief(*, money=None):
    """A brief object with a money block, and nothing else a check needs."""
    payload = {}
    if money is not None:
        payload[brief.DERIVED_KEY] = {brief.MONEY_KEY: money}
    return {
        "case": {
            "evidence": [
                {"evidence_type": brief.FARE_EVIDENCE_TYPE, "payload": payload}
            ]
        }
    }


def a_draft(ruling, *, amount=None, compensation=None, referrals=()):
    """One judge draft's ruling object, in the shape POL-GEN-03 asks for."""
    return {
        "ruling": {
            "ruling": ruling,
            "amount_sgd": amount,
            "driver_compensation_sgd": compensation,
            "referrals": list(referrals),
        }
    }


def a_difference_transport(case_no, amount):
    """A scripted transport whose judge answers ``case_no`` with a difference.

    Every other case is answered from the key, so the fixture is one run with
    one case perturbed -- and the perturbation is the whole point: the amount is
    a difference of two published figures, which the published rule cannot read.
    """
    def mutate(number, ruling):
        if number != case_no:
            return ruling
        return {
            "ruling": "FULL_REFUND",
            "amount_sgd": str(amount),
            "driver_compensation_sgd": None,
            "referrals": [],
        }

    return rig.ScriptedTransport(
        rig.produced_from_key(rig.answer_key()), mutate=mutate
    )


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------
class TheRuleTests(unittest.TestCase):
    """``published`` and ``signed``, on figures and amounts built by hand."""

    def test_the_default_rule_is_the_published_one(self):
        self.assertEqual(
            pipeline.AMOUNT_RULE_PUBLISHED, pipeline.DEFAULT_AMOUNT_RULE
        )
        self.assertEqual(
            (pipeline.AMOUNT_RULE_PUBLISHED, pipeline.AMOUNT_RULE_SIGNED),
            pipeline.AMOUNT_RULES,
        )

    def test_a_published_figure_is_read_off_under_both_rules(self):
        for rule in pipeline.AMOUNT_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(
                    "schedule_fee.value",
                    pipeline.amount_reads_off(Decimal("4.00"), FIGURES, rule),
                )

    def test_a_sum_of_two_and_of_three_is_read_off_under_both_rules(self):
        for rule in pipeline.AMOUNT_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(
                    "erp_lines.off_optimal_route_total.value + "
                    "schedule_fee.value",
                    pipeline.amount_reads_off(Decimal("33.00"), FIGURES, rule),
                )
                self.assertEqual(
                    "charged_over_quote.value + "
                    "erp_lines.off_optimal_route_total.value + "
                    "erp_lines.lines[0].amount_sgd.value",
                    pipeline.amount_reads_off(Decimal("83.30"), FIGURES, rule),
                )

    def test_a_difference_is_read_off_under_signed_and_not_under_published(self):
        for amount, expected in (
            (
                Decimal("22.30"),
                "charged_over_quote.value - "
                "erp_lines.off_optimal_route_total.value",
            ),
            (
                Decimal("48.30"),
                "charged_over_quote.value - "
                "erp_lines.lines[0].amount_sgd.value",
            ),
        ):
            with self.subTest(amount=str(amount)):
                self.assertIsNone(
                    pipeline.amount_reads_off(
                        amount, FIGURES, pipeline.AMOUNT_RULE_PUBLISHED
                    )
                )
                self.assertEqual(
                    expected,
                    pipeline.amount_reads_off(
                        amount, FIGURES, pipeline.AMOUNT_RULE_SIGNED
                    ),
                )

    def test_the_three_term_signed_forms_are_read_off(self):
        # 533's own 19.30, and the same three figures with the middle sign
        # flipped, so both of the three-term shapes are exercised.
        for amount, expected in (
            (
                Decimal("19.30"),
                "charged_over_quote.value - "
                "erp_lines.off_optimal_route_total.value - "
                "erp_lines.lines[0].amount_sgd.value",
            ),
            (
                Decimal("25.30"),
                "charged_over_quote.value - "
                "erp_lines.off_optimal_route_total.value + "
                "erp_lines.lines[0].amount_sgd.value",
            ),
        ):
            with self.subTest(amount=str(amount)):
                self.assertIsNone(
                    pipeline.amount_reads_off(
                        amount, FIGURES, pipeline.AMOUNT_RULE_PUBLISHED
                    )
                )
                self.assertEqual(
                    expected,
                    pipeline.amount_reads_off(
                        amount, FIGURES, pipeline.AMOUNT_RULE_SIGNED
                    ),
                )

    def test_the_leading_term_of_a_difference_is_the_positive_one(self):
        figures = (("a.value", Decimal("3.00")), ("b.value", Decimal("8.00")))
        self.assertEqual(
            "b.value - a.value",
            pipeline.amount_reads_off(
                Decimal("5.00"), figures, pipeline.AMOUNT_RULE_SIGNED
            ),
        )
        self.assertIsNone(
            pipeline.amount_reads_off(
                Decimal("-5.00"), figures, pipeline.AMOUNT_RULE_SIGNED
            )
        )

    def test_an_amount_at_or_below_zero_is_never_read_off(self):
        # A block publishes no figure a zero or a negative amount could be, and
        # a rule that read one off would be reading a refund out of nothing.
        for amount in (Decimal("0"), Decimal("0.00"), Decimal("-0.01")):
            with self.subTest(amount=str(amount)):
                self.assertIsNone(
                    pipeline.amount_reads_off(
                        amount, FIGURES, pipeline.AMOUNT_RULE_SIGNED
                    )
                )

    def test_the_sum_is_searched_before_the_difference(self):
        # 8.00 is ``a + b`` and also ``c - d``. The sum is the simpler reading
        # and the one the record should name, so both rules report the same
        # path for an amount they both accept.
        figures = (
            ("a.value", Decimal("5.00")),
            ("b.value", Decimal("3.00")),
            ("c.value", Decimal("10.00")),
            ("d.value", Decimal("2.00")),
        )
        for rule in pipeline.AMOUNT_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(
                    "a.value + b.value",
                    pipeline.amount_reads_off(Decimal("8.00"), figures, rule),
                )

    def test_an_unknown_rule_is_refused_rather_than_defaulted(self):
        with self.assertRaises(pipeline.PipelineError) as caught:
            pipeline.amount_reads_off(
                Decimal("4.00"), FIGURES, "signed-ish"
            )
        message = str(caught.exception)
        self.assertIn("signed-ish", message)
        self.assertIn(pipeline.AMOUNT_RULE_PUBLISHED, message)
        self.assertIn(pipeline.AMOUNT_RULE_SIGNED, message)


class TheDraftCheckTests(unittest.TestCase):
    """What the rule does to a draft, which is where the defect was."""

    MONEY = {
        "charged_over_quote": {"value": "14.50"},
        "erp_lines": {"off_optimal_route_total": {"value": "6.00"}},
    }

    def test_the_block_publishes_the_two_figures_the_difference_is_between(self):
        # The premise of every test below, asserted rather than assumed.
        figures = pipeline.published_money_figures(
            pipeline.money_block(a_brief(money=self.MONEY))
        )
        self.assertEqual(
            [
                ("charged_over_quote.value", Decimal("14.50")),
                ("erp_lines.off_optimal_route_total.value", Decimal("6.00")),
            ],
            list(figures),
        )

    def test_a_difference_abstains_under_published_and_votes_under_signed(self):
        draft = a_draft("FULL_REFUND", amount="8.50")
        brief_object = a_brief(money=self.MONEY)

        published, _ = pipeline.check_judge_draft(
            draft, brief_object, pipeline.AMOUNT_RULE_PUBLISHED
        )
        self.assertEqual(1, len(published))
        self.assertIn(pipeline.DRAFT_AMOUNT_NOT_READ_OFF, published[0])

        signed, unverifiable = pipeline.check_judge_draft(
            draft, brief_object, pipeline.AMOUNT_RULE_SIGNED
        )
        self.assertEqual((), signed)
        self.assertEqual((), unverifiable)

    def test_the_refusal_names_the_rule_it_was_made_under(self):
        # An amount neither rule can read, so both refuse it and the two
        # refusals can be compared: a record has to say which rule rejected a
        # draft rather than leave a reader to infer it from a directory name.
        draft = a_draft("FULL_REFUND", amount="31.50")
        brief_object = a_brief(money=self.MONEY)
        published, _ = pipeline.check_judge_draft(
            draft, brief_object, pipeline.AMOUNT_RULE_PUBLISHED
        )
        signed, _ = pipeline.check_judge_draft(
            draft, brief_object, pipeline.AMOUNT_RULE_SIGNED
        )
        self.assertEqual(1, len(published))
        self.assertEqual(1, len(signed))
        self.assertIn("the sum of two or three of them", published[0])
        self.assertNotIn("a signed combination", published[0])
        self.assertIn("a signed combination of two or three of them", signed[0])

    def test_an_amount_neither_rule_can_read_is_refused_by_both(self):
        # The drafts invented this number; no combination of the block's two
        # figures produces it, so it is not a reading under either rule.
        draft = a_draft("FULL_REFUND", amount="31.50")
        brief_object = a_brief(money=self.MONEY)
        for rule in pipeline.AMOUNT_RULES:
            with self.subTest(rule=rule):
                failures, _ = pipeline.check_judge_draft(
                    draft, brief_object, rule
                )
                self.assertEqual(1, len(failures))
                self.assertIn(pipeline.DRAFT_AMOUNT_NOT_READ_OFF, failures[0])


# --------------------------------------------------------------------------
# Off by default, and off is byte-identical
# --------------------------------------------------------------------------
class SwitchOffTests(unittest.TestCase):
    def test_a_run_that_names_the_default_writes_the_same_bytes(self):
        """The whole claim the switch has to earn: nothing moves when it is off.

        Two runs of the same case into the same path, the first naming no rule
        and the second naming the default, with every clock the run stamps
        pinned -- see :func:`pinned_clocks`. Every file the run writes is
        therefore comparable byte for byte: the cache entry, the transcript, the
        metadata, the event log, the invocation history, the report and the
        client's own call ledger.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with pinned_clocks():
                rig.bench(tmp, cases=(101,), judge_votes=4, now=lambda: FIXED_NOW)
                omitted = digests(rig.run_dir_of(tmp))
                self.assertTrue(omitted)

                shutil.rmtree(rig.run_dir_of(tmp))
                rig.bench(
                    tmp,
                    cases=(101,),
                    judge_votes=4,
                    now=lambda: FIXED_NOW,
                    amount_rule=pipeline.AMOUNT_RULE_PUBLISHED,
                )
                self.assertEqual(omitted, digests(rig.run_dir_of(tmp)))

    def test_a_plain_run_records_no_amount_rule_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101,), judge_votes=4)
            run_dir = rig.run_dir_of(tmp)
            document = runner.read_json(runner.case_cache_path(run_dir, 101))
            self.assertNotIn("amount_rule", document["configuration"])
            lines = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            start = [
                line
                for line in lines.splitlines()
                if line.strip() and '"invocation_start"' in line
            ]
            self.assertEqual(1, len(start))
            self.assertNotIn('"amount_rule"', start[0])
            self.assertFalse(
                (Path(tmp) / "runs" / runner.AMOUNT_RULE_DIRNAME).exists()
            )

    def test_a_signed_run_goes_to_its_own_directory_and_records_the_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(
                tmp,
                cases=(101,),
                judge_votes=4,
                amount_rule=pipeline.AMOUNT_RULE_SIGNED,
            )
            runs = Path(tmp) / "runs"
            run_dir = runner.amount_rule_run_directory(
                runs, pipeline.AMOUNT_RULE_SIGNED, MODEL
            )
            self.assertTrue((run_dir / "case-00101.json").is_file())
            # Not the plain directory, which is the whole point of the rule
            # being a path component rather than a flag.
            self.assertFalse((runner.run_directory(runs, MODEL)).exists())

            document = runner.read_json(runner.case_cache_path(run_dir, 101))
            self.assertEqual(
                pipeline.AMOUNT_RULE_SIGNED,
                document["configuration"]["amount_rule"],
            )
            start = [
                line
                for line in (run_dir / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip() and '"invocation_start"' in line
            ]
            self.assertEqual(1, len(start))
            self.assertIn('"amount_rule":"signed"', start[0])


# --------------------------------------------------------------------------
# The measurement's assembly, on a run this file makes
# --------------------------------------------------------------------------
class MeasurementAssemblyTests(unittest.TestCase):
    """A recorded panel, read twice. The published reading is the run's own."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.runs = self.root / "runs"
        self.key = rig.answer_key()

    def measure(self, case_no, amount=DIFFERENCE_AMOUNT):
        transport = a_difference_transport(case_no, amount)
        rig.bench(
            self.root,
            cases=(case_no,),
            transport=transport,
            judge_votes=4,
        )
        reading, reason = amount_rule.read_set_case(
            development_sets.CORPUS,
            case_no,
            MODEL,
            run_dir=runner.run_directory(self.runs, MODEL),
            key=self.key.get(case_no),
        )
        self.assertEqual("", reason)
        self.assertIsNotNone(reading)
        return reading

    def test_the_premise_holds_on_the_case_this_fixture_uses(self):
        # 0.80 is ``schedule_fee.value - driver_compensation.value`` and is not
        # a figure, a sum of two or a sum of three. Asserted here so that a
        # changed money block moves the fixture rather than quietly making it
        # measure nothing.
        case = development_sets.CORPUS.load_case(DIFFERENCE_CASE)
        figures = pipeline.published_money_figures(
            pipeline.money_block(brief.build_brief_for_case(case))
        )
        self.assertIsNone(
            pipeline.amount_reads_off(
                DIFFERENCE_AMOUNT, figures, pipeline.AMOUNT_RULE_PUBLISHED
            )
        )
        self.assertEqual(
            "schedule_fee.value - driver_compensation.value",
            pipeline.amount_reads_off(
                DIFFERENCE_AMOUNT, figures, pipeline.AMOUNT_RULE_SIGNED
            ),
        )

    def test_the_panel_that_computed_a_difference_publishes_nothing(self):
        reading = self.measure(DIFFERENCE_CASE)
        self.assertEqual(4, reading.drafts)
        self.assertIsNone(reading.published)
        self.assertEqual(0, reading.published_voting)
        # And the run recorded no result for it, which is what "the run
        # published nothing" means on disk.
        self.assertFalse(reading.recorded)

    def test_the_same_panel_publishes_the_difference_under_the_signed_rule(self):
        reading = self.measure(DIFFERENCE_CASE)
        self.assertEqual(4, reading.signed_voting)
        self.assertEqual("FULL_REFUND", reading.signed_ruling)
        self.assertEqual(DIFFERENCE_AMOUNT, reading.signed_amount)

    def test_a_case_that_was_left_alone_and_is_now_decided_wrongly(self):
        reading = self.measure(DIFFERENCE_CASE)
        self.assertFalse(reading.published_moves_money)
        self.assertTrue(reading.signed_moves_money)
        self.assertFalse(reading.signed_exact)
        self.assertTrue(reading.turned_unsafe)
        self.assertEqual(
            amount_rule.MOVEMENT_BOTH_MISSING, reading.movement
        )

    def test_the_measurement_writes_only_its_own_two_files(self):
        transport = a_difference_transport(DIFFERENCE_CASE, DIFFERENCE_AMOUNT)
        rig.bench(
            self.root, cases=(DIFFERENCE_CASE,), transport=transport, judge_votes=4
        )
        run_dir = runner.run_directory(self.runs, MODEL)
        before = digests(run_dir)
        out = self.root / "out"
        code = quiet(
            lambda: amount_rule.main(
                [
                    "--model",
                    MODEL,
                    "--runs-dir",
                    str(self.runs),
                    "--out-dir",
                    str(out),
                ]
            )
        )
        self.assertEqual(0, code)
        self.assertEqual(
            sorted([amount_rule.DATA_FILE, amount_rule.REPORT_FILE]),
            sorted(path.name for path in out.iterdir()),
        )
        # And the run it read is untouched, byte for byte: these figures are a
        # measurement *about* a run and not one of its own.
        self.assertEqual(before, digests(run_dir))

    def test_the_report_names_the_case_and_the_rules_it_compares(self):
        transport = a_difference_transport(DIFFERENCE_CASE, DIFFERENCE_AMOUNT)
        rig.bench(
            self.root, cases=(DIFFERENCE_CASE,), transport=transport, judge_votes=4
        )
        out = self.root / "out"
        quiet(
            lambda: amount_rule.main(
                [
                    "--model",
                    MODEL,
                    "--runs-dir",
                    str(self.runs),
                    "--out-dir",
                    str(out),
                ]
            )
        )
        text = (out / amount_rule.REPORT_FILE).read_text(encoding="utf-8")
        self.assertIn("No model call was made", text)
        self.assertIn("**The default is unchanged.**", text)
        self.assertIn("| {0} |".format(DIFFERENCE_CASE), text)
        self.assertIn("no ruling", text)
        self.assertIn("FULL_REFUND", text)

        data = json.loads((out / amount_rule.DATA_FILE).read_text(encoding="utf-8"))
        self.assertEqual(
            pipeline.AMOUNT_RULE_PUBLISHED, data["default_rule"]
        )
        self.assertIn("No model call was made", data["note"])
        self.assertEqual(
            [DIFFERENCE_CASE], data["totals"]["turned_unsafe"]
        )


# --------------------------------------------------------------------------
# No model call
# --------------------------------------------------------------------------
class NoModelCallTests(unittest.TestCase):
    """The measurement reads what three runs recorded. It asks no model."""

    def test_main_runs_with_the_client_patched_to_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            out = Path(tmp) / "out"
            with mock.patch.object(
                llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                code = quiet(
                    lambda: amount_rule.main(
                        [
                            "--model",
                            MODEL,
                            "--runs-dir",
                            str(runs),
                            "--out-dir",
                            str(out),
                        ]
                    )
                )
            self.assertEqual(0, code)
            self.assertTrue((out / amount_rule.REPORT_FILE).is_file())
            self.assertTrue((out / amount_rule.DATA_FILE).is_file())

    def test_the_module_never_names_a_client_or_a_live_measurement(self):
        """Parsed, not grepped: the names the module actually binds and reads."""
        source = (PROJECT_ROOT / "eval" / "amount_rule.py").read_text(
            encoding="utf-8"
        )
        named = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Name):
                named.add(node.id)
            elif isinstance(node, ast.Attribute):
                named.add(node.attr)
            elif isinstance(node, ast.alias):
                named.add(node.name.split(".")[-1])
                if node.asname:
                    named.add(node.asname)
        for forbidden in (
            "verify_recorded_case",
            "verify_recorded_run",
            "_default_client_factory",
            "LLMClient",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, named)

    def test_the_module_rebuilds_drafts_only_through_the_recorded_path(self):
        source = (PROJECT_ROOT / "eval" / "amount_rule.py").read_text(
            encoding="utf-8"
        )
        named = {
            node.attr
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Attribute)
        }
        self.assertIn("recorded_drafts_for_case", named)
        self.assertIn("recorded_judge_drafts", named)
        self.assertIn("reduce_vote", named)


# --------------------------------------------------------------------------
# Where the output may go
# --------------------------------------------------------------------------
class DestinationTests(unittest.TestCase):
    def test_the_default_destination_is_the_amount_rule_directory(self):
        runs = Path("/nowhere") / "runs"
        self.assertEqual(
            runs / amount_rule.AMOUNT_RULE_DIRNAME,
            amount_rule.amount_rule_directory(runs),
        )

    def test_a_run_under_a_rule_is_refused_by_the_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            clean = amount_rule.amount_rule_directory(runs)
            self.assertEqual(
                clean.resolve(),
                amount_rule.assert_not_a_run_directory(clean, runs, MODEL),
            )

            for rule in pipeline.AMOUNT_RULES:
                with self.subTest(rule=rule):
                    dirty = runner.amount_rule_run_directory(runs, rule, MODEL)
                    dirty.mkdir(parents=True, exist_ok=True)
                    (dirty / runner.METADATA_FILE).write_text(
                        "{}", encoding="utf-8"
                    )
                    with self.assertRaises(amount_rule.AmountRuleError):
                        amount_rule.assert_not_a_run_directory(dirty, runs, MODEL)
                    # And a destination inside one, which would land these
                    # figures beside that run's own.
                    with self.assertRaises(amount_rule.AmountRuleError):
                        amount_rule.assert_not_a_run_directory(
                            dirty / "report", runs, MODEL
                        )
                    shutil.rmtree(dirty)

    def test_every_headline_run_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            for headline in runner.headline_run_directories(runs, MODEL):
                with self.subTest(headline=str(headline)):
                    with self.assertRaises(amount_rule.AmountRuleError):
                        amount_rule.assert_not_a_run_directory(
                            headline, runs, MODEL
                        )

    def test_a_destination_under_the_external_runs_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            external = runs / runner.EXTERNAL_RUNS_SUBDIR / "ryde"
            with self.assertRaises(amount_rule.AmountRuleError):
                amount_rule.assert_not_a_run_directory(external, runs, MODEL)

    def test_a_scratch_runs_root_does_not_make_another_root_safe(self):
        """``--runs-dir`` and ``--out-dir`` are separate arguments.

        Pointing the runs root at a scratch directory must not make a headline
        directory under the repository's own ``runs/`` writable. The second
        root here is a temporary one rather than the repository's, so the guard
        is shown to be about the *other* root and nothing in this test reads or
        writes a committed run.
        """
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            repository = Path(tmp) / "repository-runs"
            headline = runner.run_directory(repository, MODEL)
            headline.mkdir(parents=True)
            (headline / runner.METADATA_FILE).write_text("{}", encoding="utf-8")

            with mock.patch.object(amount_rule, "RUNS_DIR", repository):
                with self.assertRaises(amount_rule.AmountRuleError):
                    amount_rule.assert_not_a_run_directory(headline, scratch, MODEL)
                with self.assertRaises(amount_rule.AmountRuleError):
                    amount_rule.assert_not_a_run_directory(
                        headline / "amount-rule", scratch, MODEL
                    )
                clean = amount_rule.amount_rule_directory(scratch)
                self.assertEqual(
                    clean.resolve(),
                    amount_rule.assert_not_a_run_directory(clean, scratch, MODEL),
                )

    def test_a_refused_destination_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            dirty = runner.run_directory(runs, MODEL)
            dirty.mkdir(parents=True)
            (dirty / runner.METADATA_FILE).write_text("{}", encoding="utf-8")
            with mock.patch.object(
                llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                code = quiet(
                    lambda: amount_rule.main(
                        [
                            "--model",
                            MODEL,
                            "--runs-dir",
                            str(runs),
                            "--out-dir",
                            str(dirty),
                        ]
                    )
                )
            self.assertEqual(1, code)
            self.assertEqual(
                [runner.METADATA_FILE], sorted(path.name for path in dirty.iterdir())
            )


# --------------------------------------------------------------------------
# The command lines
# --------------------------------------------------------------------------
class RunBenchmarkCommandLineTests(unittest.TestCase):
    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    runner.main(arguments)
        return errors.getvalue()

    def test_the_rule_is_refused_beside_the_other_three_switches(self):
        for arguments in (
            ["--amount-rule", "signed", "--ablate", "clause-notes"],
            ["--amount-rule", "signed", "--precedents"],
            ["--amount-rule", "signed", "--policy-version", "2"],
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("at most one of", message)
                self.assertIn("--amount-rule", message)

    def test_the_rule_is_refused_with_every_mode_that_reads_a_run(self):
        for arguments, named in (
            (["--amount-rule", "signed", "--compare"], "--compare"),
            (["--amount-rule", "signed", "--replay-check", "runs/x"], "--replay-check"),
            (
                ["--amount-rule", "signed", "--verify-recorded-drafts", "runs/x"],
                "--verify-recorded-drafts",
            ),
            (
                [
                    "--amount-rule",
                    "signed",
                    "--external",
                    "data/external/ryde/case-901.json",
                ],
                "--external",
            ),
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("--amount-rule", message)
                self.assertIn(named, message)

    def test_the_published_rule_is_not_a_switch_and_is_not_refused(self):
        # Naming the default changes nothing, so it must not count as one of the
        # switches that change what a run measures. With it named, ``--ablate``
        # and ``--compare`` are still refused for their own reasons.
        message = self.refuse(
            [
                "--amount-rule",
                "published",
                "--ablate",
                "clause-notes",
                "--compare",
            ]
        )
        self.assertNotIn("at most one of", message)
        self.assertIn("--ablate", message)
        self.assertIn("--compare", message)

    def test_a_rule_that_does_not_exist_is_a_parser_error(self):
        message = self.refuse(["--amount-rule", "signed-ish"])
        self.assertIn("invalid choice", message)
        self.assertIn(pipeline.AMOUNT_RULE_SIGNED, message)


class DevelopmentSetsCommandLineTests(unittest.TestCase):
    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()) as errors:
                    code = development_sets.main(arguments)
        return code, errors.getvalue()

    def test_the_rule_is_refused_beside_the_other_three_switches(self):
        for arguments in (
            ["--amount-rule", "signed", "--ablate", "clause-notes"],
            ["--amount-rule", "signed", "--precedents"],
            ["--amount-rule", "signed", "--policy-version", "2"],
        ):
            with self.subTest(arguments=arguments):
                code, message = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("at most one of", message)
                self.assertIn("--amount-rule", message)

    def test_the_rule_is_refused_with_every_mode_that_reads_a_run(self):
        for arguments, named in (
            (["--amount-rule", "signed", "--report"], "--report"),
            (["--amount-rule", "signed", "--replay-check", "runs/x"], "--replay-check"),
            (
                ["--amount-rule", "signed", "--verify-recorded-drafts", "runs/x"],
                "--verify-recorded-drafts",
            ),
        ):
            with self.subTest(arguments=arguments):
                code, message = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("--amount-rule", message)
                self.assertIn(named, message)

    def test_the_rule_reaches_a_replay_and_is_not_refused_beside_it(self):
        """``--replay-advocates`` is deliberately not in the refusal list.

        A replay calls only the judge, and the rule is what a draft's amount is
        held to, so naming the rule there is a request the pipeline can honour.
        Refusing it would make the one switch that changes what the judge
        accepts unavailable to the one mode that calls nobody but the judge.
        """
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            transport = rig.ScriptedTransport(
                rig.produced_from_key(rig.answer_key())
            )
            rig.bench(
                tmp, cases=(101,), runs_dir=runs, transport=transport, judge_votes=4
            )
            source = runner.run_directory(runs, MODEL)
            self.assertTrue((source / "case-00101.json").is_file())

            replay_runs = Path(tmp) / "replay-runs"
            replay_transport = rig.ScriptedTransport(
                rig.produced_from_key(rig.answer_key())
            )
            with mock.patch.object(
                runner,
                "_default_client_factory",
                return_value=rig.client_factory(MODEL, replay_transport),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = development_sets.main(
                        [
                            "--model",
                            MODEL,
                            "--set",
                            "corpus",
                            "--cases",
                            "101",
                            "--amount-rule",
                            "signed",
                            "--replay-advocates",
                            str(source),
                            "--runs-dir",
                            str(replay_runs),
                        ]
                    )
            self.assertEqual(0, code)
            landed = runner.amount_rule_run_directory(
                replay_runs, pipeline.AMOUNT_RULE_SIGNED, MODEL
            )
            self.assertTrue((landed / "case-00101.json").is_file())
            document = runner.read_json(runner.case_cache_path(landed, 101))
            self.assertEqual(
                pipeline.AMOUNT_RULE_SIGNED,
                document["configuration"]["amount_rule"],
            )
            # Only the judge was called again: the two advocates came off the
            # recorded run.
            self.assertEqual(4, replay_transport.calls())


# --------------------------------------------------------------------------
# The measurement of the three recorded runs
# --------------------------------------------------------------------------
class RecordedRunTests(unittest.TestCase):
    """One case at a time, off the committed runs. Nothing here writes."""

    def read(self, development_set, case_no, run_dir):
        key = development_set.key()
        reading, reason = amount_rule.read_set_case(
            development_set,
            case_no,
            HEADLINE_MODEL,
            run_dir=run_dir,
            key=key.get(case_no),
        )
        self.assertEqual("", reason, "case {0} was refused".format(case_no))
        self.assertIsNotNone(reading)
        return reading

    def test_the_held_out_run_is_the_one_the_measurement_is_about(self):
        self.assertTrue(
            (WILD_RUN_DIR / "case-00501.json").is_file()
            or (WILD_RUN_DIR / "transcript-00501.jsonl").is_file()
        )
        self.assertEqual(
            WILD_RUN_DIR,
            development_sets.SEALED_SET.run_dir(HEADLINE_MODEL, runner.RUNS_DIR),
        )

    def test_the_published_reading_is_the_ruling_the_run_published(self):
        reading = self.read(
            development_sets.SEALED_SET, UNCHANGED_CASE, WILD_RUN_DIR
        )
        self.assertTrue(reading.recorded)
        self.assertTrue(reading.published_matches_recorded)
        self.assertEqual("FULL_REFUND", reading.published_ruling)
        self.assertEqual(reading.published_ruling, reading.signed_ruling)
        self.assertEqual(reading.published_amount, reading.signed_amount)
        self.assertEqual(
            amount_rule.MOVEMENT_BOTH_MATCHING, reading.movement
        )
        self.assertFalse(reading.turned_unsafe)

    def test_501_is_turned_from_a_safe_escalation_into_a_wrong_ruling(self):
        """The case the switch would cost, named from the run's own panel."""
        reading = self.read(
            development_sets.SEALED_SET, TURNED_UNSAFE_CASE, WILD_RUN_DIR
        )
        self.assertEqual("ESCALATE", reading.published_ruling)
        self.assertFalse(reading.published_moves_money)
        self.assertEqual("PARTIAL_REFUND", reading.signed_ruling)
        self.assertEqual(Decimal("8.50"), reading.signed_amount)
        self.assertEqual("PARTIAL_REFUND", reading.key_ruling)
        self.assertEqual(Decimal("14.50"), reading.key_amount)
        self.assertFalse(reading.signed_exact)
        self.assertTrue(reading.turned_unsafe)
        self.assertTrue(reading.published_matches_recorded)

    def test_533_is_turned_from_no_ruling_into_the_keys_own_amount(self):
        reading = self.read(
            development_sets.SEALED_SET, TURNED_MATCHING_CASE, WILD_RUN_DIR
        )
        self.assertIsNone(reading.published_ruling)
        self.assertFalse(reading.recorded)
        self.assertEqual("PARTIAL_REFUND", reading.signed_ruling)
        self.assertEqual(Decimal("19.30"), reading.signed_amount)
        self.assertEqual(Decimal("19.30"), reading.key_amount)
        self.assertTrue(reading.signed_exact)
        self.assertEqual(
            amount_rule.MOVEMENT_MISSING_TO_MATCHING, reading.movement
        )

    def test_517_is_read_off_by_neither_rule(self):
        # The drafts invented 31.50; no combination of the block's figures
        # produces it, so the signed rule does not rescue every case the
        # published one lost.
        reading = self.read(
            development_sets.SEALED_SET, UNREADABLE_BOTH_WAYS_CASE, WILD_RUN_DIR
        )
        self.assertIsNone(reading.published_ruling)
        self.assertIsNone(reading.signed_ruling)
        self.assertEqual("PARTIAL_REFUND", reading.key_ruling)
        self.assertEqual(
            amount_rule.MOVEMENT_BOTH_MISSING, reading.movement
        )
        self.assertFalse(reading.turned_unsafe)

    def test_the_two_development_sets_are_measured_from_their_own_directories(self):
        self.assertEqual(
            CORPUS_RUN_DIR,
            development_sets.CORPUS.run_dir(HEADLINE_MODEL, runner.RUNS_DIR),
        )
        self.assertEqual(
            CODEX_RUN_DIR,
            development_sets.SECOND_SET.run_dir(HEADLINE_MODEL, runner.RUNS_DIR),
        )
        self.assertEqual(
            (CORPUS_RUN_DIR, CODEX_RUN_DIR, WILD_RUN_DIR),
            tuple(
                item.run_dir(HEADLINE_MODEL, runner.RUNS_DIR)
                for item in amount_rule.MEASURED_SETS
            ),
        )


if __name__ == "__main__":
    unittest.main()
