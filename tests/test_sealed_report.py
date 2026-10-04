"""The one command that prints a sealed set's figures, and what it prints.

Two sealed sets, two things to check. The held-out set has been run and its
figures are written down in ``docs/notes/2026-09-30-the-sealed-run.md``: this
reproduces every one of them from the committed files, so the note's numbers are
a measurement rather than a hand computation nobody can repeat. The second
sealed set has been run too -- once, on 2026-10-04 -- and its figures are written
down in ``docs/notes/2026-10-04-the-second-sealed-run.md``: the whole of what
the command prints for it is reproduced below, and the two sets are never summed
or pooled.

The second of those is also where the sealed-content rule became checkable before
the run: the not-run test patched the key to raise, so a command that read it on
the not-run path would have failed there rather than quietly doing what the rule
forbids. That test went red the moment the run was committed, as it was written
to, and is replaced here by the figures test beside the held-out set's.

What "not run" means is a third thing, and it is not "no case files". A run in
which every case failed leaves the event log and ``run.json`` and no result, and
the last classes below write such a run by hand -- under a temporary root, on a
set shaped like a sealed one -- to check that the command reports it as a run
with a no-ruling list rather than as a set that has never been run. Nothing
there runs a set, calls a model or writes under ``runs/``.
"""

from __future__ import annotations

import dataclasses
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, grade, run_benchmark, sealed_report  # noqa: E402
from tribunal import events, loader, model  # noqa: E402

MODEL = "deepseek/deepseek-flash"

# The whole of ``sealed_report --set wild-v2``, as the committed run prints it.
#
# Written out rather than assembled from the figures, so a change to the
# rendering is a failing test and not a test that agrees with itself. It is the
# block ``docs/notes/2026-10-04-the-second-sealed-run.md`` states, and this is
# the command that prints it: the note and this string are two records of one
# run, and a disagreement between them is a finding to report rather than a
# number to adjust.
SECOND_SEALED_RUN_REPORT = (
    "Sealed set wild-v2 \u2014 deepseek/deepseek-flash\n"
    "Run: runs/wild-v2/deepseek-deepseek-flash\n"
    "\n"
    "Four-field exact\n"
    "  over the 20 cases that produced a ruling: 18/20\n"
    "  over the 20 cases in the set, a case with no ruling as a miss: 18/20\n"
    "\n"
    "Ruling alone\n"
    "  over the 20 cases that produced a ruling: 18/20\n"
    "  over the 20 cases in the set: 18/20\n"
    "\n"
    "Per category, from the set's own index.json\n"
    "  NO_SHOW_CHARGE: 8 in the set, 8 produced; four-field 8/8 over produced "
    "and 8/8 over all; ruling 8/8 over produced and 8/8 over all\n"
    "  ROUTE_DEVIATION: 12 in the set, 12 produced; four-field 10/12 over "
    "produced and 10/12 over all; ruling 10/12 over produced and 10/12 over "
    "all\n"
    "\n"
    "Escalation\n"
    "  over the 20 cases that produced a ruling: 5 produced, 5 expected, "
    "4 true positives; precision 4/5, recall 4/5\n"
    "  over the 20 cases in the set: 5 produced, 5 expected, 4 true positives; "
    "precision 4/5, recall 4/5\n"
    "\n"
    "No ruling (0)\n"
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
            # Per category, both bases and both fields, from the set's own
            # index.json. The ruling cells are asserted beside the four-field
            # ones because they are not the same figure: NO_SHOW_CHARGE loses a
            # case on a field other than the ruling, and ROUTE_DEVIATION does
            # not, so a per-category line that printed one cell twice would
            # agree with itself and disagree with the run.
            "  ROUTE_DEVIATION: 37 in the set, 35 produced; four-field 30/35 over "
            "produced and 30/37 over all; ruling 30/35 over produced and 30/37 "
            "over all",
            "  NO_SHOW_CHARGE: 27 in the set, 27 produced; four-field 25/27 over "
            "produced and 25/27 over all; ruling 26/27 over produced and 26/27 "
            "over all",
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


class SecondSealedSetFiguresTests(unittest.TestCase):
    """The committed ``runs/wild-v2/`` record, reproduced whole.

    This is the figures test the not-run test was written to be replaced by. That
    one asserted the whole output was the not-run line, so the committed run made
    it go red rather than pass quietly; this asserts the whole output of the run
    instead -- every line, the blank lines and the ordering included -- so a
    rendering change, a changed figure and an added line all fail here.

    The two sealed sets are never summed or pooled: each is its own
    generalisation figure from its own freeze, and neither of these tests reads
    the other's run.
    """

    def test_it_reproduces_the_whole_report_the_committed_run_prints(self):
        code, text = run_report("--set", "wild-v2")
        self.assertEqual(0, code)
        self.assertEqual(SECOND_SEALED_RUN_REPORT, text)

    def test_the_run_directory_the_report_names_is_the_committed_one(self):
        """The second line of the report above names a run; this says it is there."""
        self.assertTrue(
            (PROJECT_ROOT / "runs" / "wild-v2" / "deepseek-deepseek-flash").is_dir(),
            "the report names a run directory that is not in the repository",
        )

    def test_it_prints_no_corpus_target_beside_the_second_sealed_set(self):
        """``TARGET_ESCALATION_RATE`` is the corpus's, and the set is not."""
        _, text = run_report("--set", "wild-v2")
        self.assertNotIn("TARGET_ESCALATION_RATE", text)
        self.assertNotIn("target", text.lower())

    def test_a_development_set_is_refused_rather_than_reported(self):
        """The command prints no corpus target, so it is sealed sets only.

        Refused at the command-line layer, with a status and nothing on standard
        output: what is wrong is what the caller typed, and a traceback is not an
        answer to it.
        """
        errors = io.StringIO()
        with redirect_stderr(errors):
            code, text = run_report("--set", "codex")

        self.assertEqual(1, code)
        self.assertEqual("", text)
        self.assertIn(
            "FATAL: 'codex' is not a sealed set; the sealed sets are wild, wild-v2",
            errors.getvalue(),
        )


class ModelDefaultTests(unittest.TestCase):
    """Which model's run directory a sealed report reads, when none is named.

    A sealed set that registers the arguments its run is fixed at names the model
    its single run was made with, and its run directory is named after that
    model. The set is given a registration naming a different model below, so the
    test can tell the registration from the runtime default -- which are the same
    string today, and would make a test that only asserted the printed model
    agree with a command that never read the registration at all.
    """

    @staticmethod
    def _registered_as_elsewhere():
        """``wild-v2`` with its registration naming another model."""
        return dataclasses.replace(
            development_sets.WILD_V2,
            run_arguments=dataclasses.replace(
                development_sets.WILD_V2.run_arguments, model="a/registered-model"
            ),
        )

    def test_the_default_model_is_the_one_the_set_registers(self):
        elsewhere = self._registered_as_elsewhere()
        self.assertEqual(
            "a/registered-model",
            sealed_report.model_for(elsewhere, None),
            "the default model is not the one the set registers",
        )

    def test_a_set_that_registers_no_arguments_uses_the_runtime_model(self):
        """``wild-v1`` fixes no run arguments, so the decision is the default."""
        self.assertIsNone(development_sets.SEALED_SET.run_arguments)
        self.assertEqual(
            model.RUNTIME_MODEL,
            sealed_report.model_for(development_sets.SEALED_SET, None),
        )

    def test_a_named_model_still_wins(self):
        elsewhere = self._registered_as_elsewhere()
        for development_set in (development_sets.WILD_V2, elsewhere):
            with self.subTest(development_set=development_set.name):
                self.assertEqual(
                    "asked/for", sealed_report.model_for(development_set, "asked/for")
                )

    def test_the_command_looks_in_the_directory_the_registration_names(self):
        """The end of the same road, through the command line.

        The set's registration names another model, and the command must look in
        *that* model's run directory: reading the runtime default instead would
        look in a directory named after a model the set never ran, which is how a
        sealed report would print "has not been run" for a set that has been.
        Nothing is written -- the not-run path prints one line and this test only
        reads it.
        """
        elsewhere = self._registered_as_elsewhere()
        with mock.patch.object(development_sets, "named", return_value=elsewhere):
            code, text = run_report("--set", "wild-v2")

        self.assertEqual(0, code)
        self.assertIn("runs/wild-v2/a-registered-model", text)


# --------------------------------------------------------------------------
# A sealed-shaped set under a temporary root
# --------------------------------------------------------------------------
# A sealed set is a set with ``sealed=True``, its own case root, its own key and
# its own runs subdirectory. Nothing below runs one: the run directories are
# written by hand, so no client is built, no model is called, and nothing under
# ``runs/`` is read or written.


def _entry(case_no, ruling, amount=None, compensation=None, referrals=(),
           category="ROUTE_DEVIATION"):
    """One case's key entry, in the shape a set's own key is written in."""
    return {
        "case_no": case_no,
        "category": category,
        "ground_truth": {
            "expected_ruling": ruling,
            "expected_amount_sgd": amount,
            "expected_driver_compensation_sgd": compensation,
            "expected_referrals": list(referrals),
        },
    }


def _sealed_shaped(tmp, entries, name="wild-shaped"):
    """A temporary sealed-shaped set, its key and index written, and its runs root.

    The case root is written with an index and no case files: what these tests
    read is a run directory, and no case file is opened on any path they take.
    """
    root = Path(tmp) / "external" / name
    (root / "cases").mkdir(parents=True)
    (root / "index.json").write_text(
        json.dumps(
            [
                {
                    "case_no": entry["case_no"],
                    "dispute_id": "DSP-{0}".format(entry["case_no"]),
                    "trip_id": "TRP-{0}".format(entry["case_no"]),
                    "category": entry["category"],
                    "file": "cases/case-{0:05d}.json".format(entry["case_no"]),
                }
                for entry in entries
            ]
        ),
        encoding="utf-8",
    )
    key_path = Path(tmp) / "{0}-key.json".format(name)
    key_path.write_text(
        json.dumps(
            [
                {
                    "case_no": entry["case_no"],
                    "dispute_id": "DSP-{0}".format(entry["case_no"]),
                    "ground_truth": entry["ground_truth"],
                }
                for entry in entries
            ]
        ),
        encoding="utf-8",
    )
    development_set = development_sets.DevelopmentSet(
        name=name,
        cases=tuple(entry["case_no"] for entry in entries),
        key_path=key_path,
        runs_subdir=name,
        case_root=root,
        summary="a temporary sealed-shaped set",
        sealed=True,
    )
    return development_set, Path(tmp) / "runs"


class RunGateTests(unittest.TestCase):
    """What "has not been run" means.

    Three artifacts and any one of them is a run: a cached case file, the event
    log, and ``run.json``. A run in which every case failed leaves the last two
    and no result, and reporting that directory as a set that has never been run
    would say the opposite of what it holds.
    """

    ENTRIES = (_entry(701, "PARTIAL_REFUND", "12.00"), _entry(702, "ESCALATE"))

    def _empty_run_dir(self, tmp):
        """The set, its runs root, and its run directory, created and empty.

        The loader refuses a case root outside ``data/external/``, so the root
        below is named as the one under the temporary directory -- the same
        patch the version-2 probe uses, and the reason it is needed.
        """
        development_set, runs = _sealed_shaped(tmp, self.ENTRIES)
        run_dir = development_set.run_dir(MODEL, runs)
        run_dir.mkdir(parents=True)
        return development_set, runs, run_dir

    def test_an_empty_run_directory_is_not_a_run(self):
        """A directory with nothing in it is not a run, and says so."""
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs, _ = self._empty_run_dir(tmp)
            text = sealed_report.render(development_set, MODEL, runs)
            self.assertIn("has not been run", text)
            self.assertNotIn("No ruling", text)

    def test_a_run_that_left_only_its_metadata_is_a_run(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs, run_dir = self._empty_run_dir(tmp)
            (run_dir / run_benchmark.METADATA_FILE).write_text("{}", encoding="utf-8")
            text = sealed_report.render(development_set, MODEL, runs)
            self.assertNotIn("has not been run", text)
            self.assertIn("No ruling (2)", text)

    def test_a_run_that_left_only_its_event_log_is_a_run(self):
        """And the failure kind it reports is the one off that log."""
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs, run_dir = self._empty_run_dir(tmp)
            log = events.EventLog(run_dir / events.EVENTS_FILE, invocation_id="a-test")
            log.record(events.EVENT_CASE_FAILED, case_no=701, failure_kind="SHAPE")
            log.record(events.EVENT_CASE_FAILED, case_no=702, failure_kind="TRANSPORT")

            text = sealed_report.render(development_set, MODEL, runs)

            self.assertNotIn("has not been run", text)
            self.assertIn("No ruling (2)", text)
            self.assertIn("  701: last failure kind SHAPE", text)
            self.assertIn("  702: last failure kind TRANSPORT", text)


class EscalationOnBothBasesTests(unittest.TestCase):
    """An expected escalation with no ruling moves one basis and not the other.

    The two bases are printed side by side and neither is offered as the one to
    quote. A case that produced no ruling is a miss over the set and is not part
    of the run's precision at all, so a set with an expected escalation among
    its no-ruling cases is where the two come apart -- and a renderer that
    printed one basis twice would be self-consistent and wrong.
    """

    ENTRIES = (
        _entry(701, "ESCALATE"),
        _entry(702, "ESCALATE"),
        _entry(703, "PARTIAL_REFUND", "12.00"),
    )

    def test_recall_differs_between_the_two_bases(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(loader, "EXTERNAL_DIR", Path(tmp) / "external"):
            development_set, runs = _sealed_shaped(tmp, self.ENTRIES)
            run_dir = development_set.run_dir(MODEL, runs)
            run_dir.mkdir(parents=True)
            # 701 is the expected escalation that produced nothing, so it is a
            # false negative over the set and absent from the produced basis.
            produced = grade.key_as_produced(development_set.key())
            for case_no in (702, 703):
                run_benchmark.write_json(
                    run_benchmark.case_cache_path(run_dir, case_no), produced[case_no]
                )
            (run_dir / run_benchmark.METADATA_FILE).write_text("{}", encoding="utf-8")

            text = sealed_report.render(development_set, MODEL, runs)

            self.assertIn(
                "  over the 2 cases that produced a ruling: 1 produced, 1 expected, "
                "1 true positives; precision 1/1, recall 1/1",
                text,
            )
            self.assertIn(
                "  over the 3 cases in the set: 1 produced, 2 expected, "
                "1 true positives; precision 1/1, recall 1/2",
                text,
            )
            self.assertIn("No ruling (1)", text)
            self.assertIn("  701: last failure kind not recorded", text)


if __name__ == "__main__":
    unittest.main()
