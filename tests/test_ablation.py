"""Tests for the ablation switch.

An ablation builds one case's brief with one thing removed, so a run with it on
measures the pipeline without that thing. Two exist: ``clause-notes``, which is
the ``include_clause_notes`` flag that already existed given a name, and
``admissibility``, which removes the ``admissibility`` object from every artifact
in the brief.

The switch is off by default and **off is byte-identical**, so most of this file
is about two things: that each ablation changes exactly what it says it changes
and nothing else, and that naming it changes where a run writes, what it
records, and which brief its staleness check rebuilds.

Nothing here reaches a real model. Every test that runs a runner or the pipeline
either injects the scripted transport from ``tests.test_run_benchmark`` or
patches ``tribunal.llm.LLMClient`` to raise, and a real key sits in the
repository's ``.env``.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark as runner  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import brief, loader, money, pipeline, referee  # noqa: E402

MODEL = rig.MODEL
PROMPTS_DIR = rig.PROMPTS_DIR

# Case 114 carries an impaired artifact, EV-ADVIS-00114-01, whose admissibility
# object records a MISSING_ARTIFACT issue. Case 201's brief derives the text
# "EV-ADVIS-00201-01 is MISSING" from a null payload, so it is the case that
# shows what an ablated brief still says.
IMPAIRED_CASE = 114
IMPAIRED_ARTIFACT = "EV-ADVIS-00114-01"
MISSING_CASE = 201
MISSING_ARTIFACT = "EV-ADVIS-00201-01"

CLAUSE_NOTES = brief.ABLATION_CLAUSE_NOTES
ADMISSIBILITY = brief.ABLATION_ADMISSIBILITY

# A fixed clock reading, so two pipeline runs over the same case produce the same
# transcript bytes and "byte-identical" can be asserted rather than described.
FIXED_NOW = "2026-09-28T00:00:00+00:00"

# A sentinel distinct from ``None``: it says "this caller never named the
# parameter at all", which is the case the byte-identity tests are about.
OMIT = object()


def canonical(document):
    return money.dumps_canonical(document)


def artifacts(brief_object):
    return list(brief_object["case"]["evidence"])


def walk(node, path=""):
    """Every leaf of a parsed document, with its path."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, path + "." + str(key))
    elif isinstance(node, list):
        for position, value in enumerate(node):
            yield from walk(value, path + "[{0}]".format(position))
    else:
        yield path, node


def strings(node):
    return [value for _path, value in walk(node) if isinstance(value, str)]


def transport_for(key=None):
    key = rig.answer_key() if key is None else key
    return rig.ScriptedTransport(rig.produced_from_key(key))


def run_pipeline_once(case, ablate_sentinel=OMIT, transport=None):
    """One ``run_loaded_case`` over the scripted transport, at a fixed clock."""
    transport = transport_for() if transport is None else transport
    client = rig.client_factory(MODEL, transport)(lambda record: None)
    arguments = dict(
        prompts_dir=PROMPTS_DIR,
        now=lambda: FIXED_NOW,
        judge_votes=1,
    )
    if ablate_sentinel is not OMIT:
        arguments["ablate"] = ablate_sentinel
    return pipeline.run_loaded_case(case, client, **arguments)


def ablated_run_dir(root, name, model=MODEL, subdir=None):
    base = Path(root) / "runs" if subdir is None else Path(root) / "runs" / subdir
    return base / runner.ABLATION_DIRNAME / name / runner.model_slug(model)


# --------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------
class AblationVocabularyTests(unittest.TestCase):
    def test_the_two_ablations_are_named(self):
        self.assertEqual((CLAUSE_NOTES, ADMISSIBILITY), brief.ABLATIONS)

    def test_a_known_name_is_known_and_nothing_else_is(self):
        for name in brief.ABLATIONS:
            with self.subTest(name=name):
                self.assertTrue(brief.ablation_known(name))
        for value in (None, "", "Clause-Notes", "notes", "admissibility ", "..", 1, [CLAUSE_NOTES]):
            with self.subTest(value=value):
                self.assertFalse(brief.ablation_known(value))

    def test_every_ablation_has_a_note_and_an_unknown_one_raises(self):
        for name in brief.ABLATIONS:
            with self.subTest(name=name):
                self.assertTrue(brief.ablation_note(name).strip())
        with self.assertRaises(brief.AblationError):
            brief.ablation_note("no-such-ablation")

    def test_an_ablation_error_is_a_value_error(self):
        # So a caller that only knows about ``ValueError`` still catches it, and
        # so the CLI's own refusals are the only refusals that reach a user.
        self.assertTrue(issubclass(brief.AblationError, ValueError))

    def test_the_admissibility_note_does_not_claim_the_brief_lost_its_information(self):
        # The queue is explicit about this: the ablated brief carries no
        # admissibility OBJECT, which is not the same as carrying no
        # admissibility information, and the note has to say so rather than
        # claim the brief was emptied.
        note = brief.ablation_note(ADMISSIBILITY)
        self.assertIn("MISSING", note)
        self.assertNotIn("carries no admissibility information", note)
        self.assertIn("not the same as", note)


# --------------------------------------------------------------------------
# What each ablation changes
# --------------------------------------------------------------------------
class ClauseNotesAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = loader.load_case(IMPAIRED_CASE)
        cls.plain = brief.build_brief_for_case(cls.case)
        cls.ablated = brief.build_brief_for_case(cls.case, ablate=CLAUSE_NOTES)
        cls.flagged = brief.build_brief_for_case(cls.case, include_clause_notes=False)

    def test_clause_notes_is_the_flag_that_already_existed(self):
        self.assertEqual(canonical(self.flagged), canonical(self.ablated))

    def test_it_changes_the_brief(self):
        self.assertNotEqual(canonical(self.plain), canonical(self.ablated))

    def test_every_clause_loses_its_notes_and_keeps_everything_else(self):
        for policy in ("general", "category"):
            clauses = self.ablated["policies"][policy]["clauses"]
            self.assertTrue(clauses)
            for clause in clauses:
                with self.subTest(policy=policy, clause=clause["id"]):
                    self.assertNotIn("notes", clause)
                    original = [
                        item
                        for item in self.plain["policies"][policy]["clauses"]
                        if item["id"] == clause["id"]
                    ][0]
                    for key in original:
                        if key == "notes":
                            continue
                        self.assertIn(key, clause)

    def test_the_rest_of_the_brief_is_untouched(self):
        # The evidence, the dispute and the derived blocks are the same bytes:
        # the ablation is about the commentary around the rules, not the facts.
        self.assertEqual(canonical(self.plain["case"]), canonical(self.ablated["case"]))


class AdmissibilityAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = loader.load_case(IMPAIRED_CASE)
        cls.plain = brief.build_brief_for_case(cls.case)
        cls.ablated = brief.build_brief_for_case(cls.case, ablate=ADMISSIBILITY)

    def test_the_plain_brief_carries_admissibility_objects(self):
        self.assertTrue(any("admissibility" in artifact for artifact in artifacts(self.plain)))

    def test_every_artifact_loses_its_object(self):
        stripped = artifacts(self.ablated)
        self.assertTrue(stripped)
        for artifact in stripped:
            with self.subTest(evidence_id=artifact.get("evidence_id")):
                self.assertNotIn("admissibility", artifact)

    def test_it_removes_nothing_but_that_object(self):
        for before, after in zip(artifacts(self.plain), artifacts(self.ablated)):
            with self.subTest(evidence_id=before.get("evidence_id")):
                expected = {
                    key: value for key, value in before.items() if key != "admissibility"
                }
                self.assertEqual(canonical(expected), canonical(after))

    def test_the_evidence_ids_are_unchanged_and_in_order(self):
        self.assertEqual(
            [artifact["evidence_id"] for artifact in artifacts(self.plain)],
            [artifact["evidence_id"] for artifact in artifacts(self.ablated)],
        )

    def test_a_missing_artifact_keeps_its_id_and_its_null_payload(self):
        missing = [
            artifact
            for artifact in artifacts(self.ablated)
            if artifact["evidence_id"] == IMPAIRED_ARTIFACT
        ]
        self.assertEqual(1, len(missing), "the MISSING artifact left the brief")
        self.assertIsNone(missing[0]["payload"])
        self.assertNotIn("admissibility", missing[0])

    def test_the_rest_of_the_brief_is_untouched(self):
        self.assertEqual(
            canonical(self.plain["policies"]), canonical(self.ablated["policies"])
        )
        self.assertEqual(
            canonical(self.plain["case"]["dispute"]),
            canonical(self.ablated["case"]["dispute"]),
        )

    def test_the_referee_reads_a_stripped_artifact_as_unimpaired(self):
        # The referee already accepts an artifact with no ``admissibility``
        # object -- it checks with ``isinstance``. This is the consequence: a
        # claim that cites an impaired artifact without disclosing the impairment
        # is discarded on the plain brief and kept on the ablated one.
        claim = {
            "text": "The advisory supports this fact.",
            "evidence_ids": [IMPAIRED_ARTIFACT],
            "clause_ids": ["POL-RD-08"],
        }
        plain_result = referee.referee(self.plain, [claim], [])
        ablated_result = referee.referee(self.ablated, [claim], [])
        self.assertEqual(referee.STATUS_DISCARDED, plain_result.ledger[0]["status"])
        self.assertEqual(
            referee.IMPAIRMENT_UNDISCLOSED, plain_result.ledger[0]["reason_code"]
        )
        self.assertEqual(1, len(plain_result.discards))
        self.assertEqual(referee.STATUS_KEPT, ablated_result.ledger[0]["status"])
        self.assertEqual(0, len(ablated_result.discards))

    def test_the_derived_text_still_says_missing(self):
        # Computed from a null payload before the strip, and it survives it. This
        # is the fact the note and the report have to state: the ablated brief
        # carries no admissibility OBJECT and still says an artifact is MISSING.
        case = loader.load_case(MISSING_CASE)
        ablated = brief.build_brief_for_case(case, ablate=ADMISSIBILITY)
        said = [text for text in strings(ablated) if "is MISSING" in text]
        self.assertTrue(said, "the derived MISSING text did not survive the ablation")
        self.assertTrue(any(MISSING_ARTIFACT in text for text in said))
        stripped = [
            artifact
            for artifact in artifacts(ablated)
            if artifact["evidence_id"] == MISSING_ARTIFACT
        ]
        self.assertEqual(1, len(stripped))
        self.assertIsNone(stripped[0]["payload"])
        self.assertNotIn("admissibility", stripped[0])

    def test_the_three_briefs_are_three_briefs(self):
        digests = {
            "plain": brief.brief_digest(self.plain)[1],
            CLAUSE_NOTES: brief.brief_digest(
                brief.build_brief_for_case(self.case, ablate=CLAUSE_NOTES)
            )[1],
            ADMISSIBILITY: brief.brief_digest(self.ablated)[1],
        }
        self.assertEqual(3, len(set(digests.values())), digests)

    def test_the_ablated_digest_is_a_sha256(self):
        digest = brief.brief_digest(self.ablated)[1]
        self.assertEqual(64, len(digest))
        int(digest, 16)


# --------------------------------------------------------------------------
# Off by default, and off is byte-identical
# --------------------------------------------------------------------------
class SwitchOffTests(unittest.TestCase):
    def test_the_builder_with_no_ablation_is_byte_identical(self):
        case = loader.load_case(IMPAIRED_CASE)
        self.assertEqual(
            canonical(brief.build_brief_for_case(case)),
            canonical(brief.build_brief_for_case(case, ablate=None)),
        )

    def test_build_brief_and_the_for_case_builder_agree(self):
        # ``build_brief``'s signature is pinned by a test and takes no ablation,
        # so it must still build the bytes the plain path builds.
        self.assertEqual(
            canonical(brief.build_brief(IMPAIRED_CASE)),
            canonical(brief.build_brief_for_case(loader.load_case(IMPAIRED_CASE))),
        )

    def test_the_pipeline_with_no_ablation_is_byte_identical(self):
        case = loader.load_case(IMPAIRED_CASE)
        omitted = run_pipeline_once(case)
        explicit_none = run_pipeline_once(case, ablate_sentinel=None)
        self.assertEqual(omitted.brief_sha256, explicit_none.brief_sha256)
        self.assertEqual(omitted.transcript_json, explicit_none.transcript_json)
        self.assertEqual(omitted.ruling, explicit_none.ruling)

    def test_the_pipeline_with_an_ablation_is_not(self):
        case = loader.load_case(IMPAIRED_CASE)
        plain = run_pipeline_once(case)
        transport = transport_for()
        ablated = run_pipeline_once(case, ablate_sentinel=ADMISSIBILITY, transport=transport)
        self.assertNotEqual(plain.brief_sha256, ablated.brief_sha256)
        self.assertNotEqual(plain.transcript_json, ablated.transcript_json)
        # And the advocates really were handed the ablated brief: the brief is
        # the second message of the first request, and it no longer carries an
        # admissibility object on any artifact.
        handed = json.loads(transport.requests[0]["messages"][1]["content"])
        self.assertTrue(handed["case"]["evidence"])
        self.assertFalse(
            any("admissibility" in artifact for artifact in handed["case"]["evidence"])
        )

    def test_the_digest_helpers_default_to_the_plain_brief(self):
        # ``brief_digest_for`` returning ``None`` is what tells
        # :class:`BriefStaleness` to use its own corpus digest, so a caller who
        # names neither a loader nor an ablation gets the path it always got.
        self.assertIsNone(runner.brief_digest_for())
        self.assertIsNone(runner.brief_digest_for(None, None))
        self.assertEqual(
            runner.current_brief_sha256(IMPAIRED_CASE),
            runner.current_brief_sha256(IMPAIRED_CASE, ablate=None),
        )

    def test_a_plain_run_writes_where_it_always_wrote_and_records_no_ablation(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _transport = rig.bench(tmp, cases=(101,))
            self.assertEqual([101], summary.completed_cases)
            plain = rig.run_dir_of(tmp)
            self.assertTrue((plain / "case-00101.json").is_file())
            self.assertFalse((Path(tmp) / "runs" / runner.ABLATION_DIRNAME).exists())

            document = runner.read_json(runner.case_cache_path(plain, 101))
            self.assertIsNone(runner.configuration_of(document)["ablation"])
            self.assertEqual(
                runner.configuration_document(judge_votes=1, verify_drafts=False),
                runner.configuration_document(
                    judge_votes=1, verify_drafts=False, ablation=None
                ),
            )

    def test_a_plain_run_appends_the_line_it_always_appended(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101,))
            lines = (rig.run_dir_of(tmp) / "events.jsonl").read_text(encoding="utf-8")
            start = [
                line
                for line in lines.splitlines()
                if line.strip() and '"invocation_start"' in line
            ]
            self.assertEqual(1, len(start))
            self.assertNotIn('"ablation"', start[0])

    def test_an_ablated_run_names_the_ablation_on_the_invocation_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101,), ablation=ADMISSIBILITY)
            lines = (
                ablated_run_dir(tmp, ADMISSIBILITY) / "events.jsonl"
            ).read_text(encoding="utf-8")
            start = [
                line
                for line in lines.splitlines()
                if line.strip() and '"invocation_start"' in line
            ]
            self.assertEqual(1, len(start))
            self.assertIn('"ablation":"{0}"'.format(ADMISSIBILITY), start[0])


# --------------------------------------------------------------------------
# Where an ablated run writes
# --------------------------------------------------------------------------
class DestinationTests(unittest.TestCase):
    def test_the_ablation_directory_is_built_from_the_runs_root_and_the_name(self):
        runs = Path("/tmp/scratch/runs")
        self.assertEqual(
            runs / "ablation" / CLAUSE_NOTES / "deepseek-deepseek-flash",
            runner.ablation_run_directory(runs, CLAUSE_NOTES, "deepseek/deepseek-flash"),
        )

    def test_the_ablation_directory_is_not_the_plain_run_directory(self):
        runs = Path("/tmp/scratch/runs")
        for name in brief.ABLATIONS:
            with self.subTest(name=name):
                self.assertNotEqual(
                    runner.run_directory(runs, MODEL),
                    runner.ablation_run_directory(runs, name, MODEL),
                )

    def test_the_destination_guard_fails_on_a_dirty_fixture(self):
        # The guard is what stops an ablated result landing where an unablated
        # one lives. Seen to fail on a fixture that would do exactly that, then
        # to pass on the real destination.
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            dirty = runner.run_directory(runs, MODEL)
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_ablation_destination(dirty, runs, MODEL)
            # And a name that climbs out of the ablation root, which is what a
            # ``..`` would be if the name were ever allowed to be one. It climbs
            # to a directory that is not a headline one, so what refuses it here
            # is the ablation root rather than the headline check that runs
            # first -- a plain ``..`` lands on the model's own run directory and
            # is refused for being that.
            climbing = runner.ablation_run_directory(runs, "../elsewhere", MODEL)
            with self.assertRaises(runner.BenchmarkError) as caught:
                runner.assert_ablation_destination(climbing, runs, MODEL)
            self.assertIn("may only be written under", str(caught.exception))
            clean = runner.ablation_run_directory(runs, CLAUSE_NOTES, MODEL)
            self.assertEqual(clean, runner.assert_ablation_destination(clean, runs, MODEL))

    def test_an_ablated_corpus_run_writes_under_the_ablation_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, transport = rig.bench(tmp, cases=(101,), ablation=CLAUSE_NOTES)
            self.assertEqual([101], summary.completed_cases)
            self.assertTrue(transport.calls() > 0)
            ablated = ablated_run_dir(tmp, CLAUSE_NOTES)
            self.assertTrue((ablated / "case-00101.json").is_file())
            self.assertTrue((ablated / "run.json").is_file())
            # And nothing at all was written into the plain run directory.
            self.assertFalse(rig.run_dir_of(tmp).exists())

    def test_an_ablated_second_set_run_writes_under_the_sets_own_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = transport_for(development_sets.SECOND_SET.key())
            summary = development_sets.run_set(
                development_sets.SECOND_SET,
                MODEL,
                runs_dir=Path(tmp) / "runs",
                cases=(9101,),
                prompts_dir=PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, transport),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
                ablation=ADMISSIBILITY,
            )
            self.assertEqual([9101], summary.completed_cases)
            ablated = ablated_run_dir(tmp, ADMISSIBILITY, subdir="codex")
            self.assertTrue((ablated / "case-09101.json").is_file())
            # The second set's plain run directory is not the ablated one.
            self.assertFalse((Path(tmp) / "runs" / "codex" / runner.model_slug(MODEL)).exists())

    def test_the_second_set_still_may_not_write_into_the_corpus_directory(self):
        # The ablation moves the destination; it does not weaken the guard that
        # keeps a development set out of the corpus run directory.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(runner.BenchmarkError):
                development_sets.assert_set_run_directory(
                    runner.run_directory(runner.RUNS_DIR, MODEL),
                    development_sets.SECOND_SET,
                    Path(tmp) / "runs",
                )


# --------------------------------------------------------------------------
# What an ablated run records
# --------------------------------------------------------------------------
class ConfigurationTests(unittest.TestCase):
    def assert_records(self, run_dir, ablation, case_no):
        for label, document in (
            ("run.json", runner.read_json(runner.metadata_path(run_dir))),
            ("case file", runner.read_json(runner.case_cache_path(run_dir, case_no))),
        ):
            with self.subTest(artifact=label):
                self.assertEqual(ablation, runner.configuration_of(document)["ablation"])
        history = runner.read_json(run_dir / runner.INVOCATIONS_FILE)
        self.assertTrue(history)
        self.assertEqual(
            [ablation], [runner.configuration_of(item)["ablation"] for item in history]
        )
        for item in history:
            self.assertEqual(set(runner.CONFIGURATION_FIELDS), set(item["configuration"]))

    def test_an_ablated_corpus_run_records_the_ablation_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101,), ablation=ADMISSIBILITY)
            self.assert_records(ablated_run_dir(tmp, ADMISSIBILITY), ADMISSIBILITY, 101)

    def test_an_ablated_second_set_run_records_the_ablation_and_its_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = transport_for(development_sets.SECOND_SET.key())
            development_sets.run_set(
                development_sets.SECOND_SET,
                MODEL,
                runs_dir=Path(tmp) / "runs",
                cases=(9101,),
                prompts_dir=PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, transport),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
                ablation=CLAUSE_NOTES,
            )
            run_dir = ablated_run_dir(tmp, CLAUSE_NOTES, subdir="codex")
            self.assert_records(run_dir, CLAUSE_NOTES, 9101)
            document = runner.read_json(runner.case_cache_path(run_dir, 9101))
            self.assertEqual("codex", document["development_set"])

    def test_a_plain_run_records_a_null_ablation(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101,))
            self.assert_records(rig.run_dir_of(tmp), None, 101)


# --------------------------------------------------------------------------
# What an ablated run's report says
# --------------------------------------------------------------------------
class AblatedReportTests(unittest.TestCase):
    """An ablated run's report has to say it was ablated, in the brief's words.

    ``report.md`` is what a reader is given, and an ablated run's report was
    indistinguishable from a headline one: the same title, the same tables, and
    no word anywhere that something had been taken out of what the agents were
    given. The only place that said so was the directory name, which is not in
    the report -- so two runs of one model under one set of prompts produced two
    reports that opened identically, and a reader comparing them was comparing
    two different measurements without being told.

    The sentence printed comes from :func:`tribunal.brief.ablation_note`, which
    had no caller at all before this. Taking the words from the module that
    implements the ablation is what stops a report describing an ablation the
    brief module does not have, and for ``admissibility`` it is what carries the
    sentence that derived text from a null payload still says MISSING.
    """

    def report_for(self, tmp, name):
        rig.bench(tmp, cases=(101,), ablation=name)
        run_dir = ablated_run_dir(tmp, name)
        return (run_dir / runner.REPORT_FILE).read_text(encoding="utf-8")

    def test_an_ablated_report_names_the_ablation_and_prints_its_note(self):
        for name in brief.ABLATIONS:
            with self.subTest(ablation=name):
                with tempfile.TemporaryDirectory() as tmp:
                    text = self.report_for(tmp, name)
                self.assertEqual(
                    "# Benchmark report — {0} — ablation {1}".format(MODEL, name),
                    text.splitlines()[0],
                )
                self.assertIn(brief.ablation_note(name), text)
                if name == ADMISSIBILITY:
                    # The sentence the note exists for: the ablated brief
                    # carries no admissibility *object*, which is not the same
                    # as carrying no admissibility *information*.
                    self.assertIn(
                        "derived text computed from a null payload still says MISSING",
                        text,
                    )

    def test_a_plain_run_s_report_says_nothing_about_an_ablation(self):
        """The other half: the heading is for ablated runs, not for every run."""
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101,))
            text = (rig.run_dir_of(tmp) / runner.REPORT_FILE).read_text(
                encoding="utf-8"
            )
        self.assertEqual(
            "# Benchmark report — {0}".format(MODEL), text.splitlines()[0]
        )
        self.assertNotIn("## Ablation", text)


# --------------------------------------------------------------------------
# The staleness check rebuilds the ablated brief
# --------------------------------------------------------------------------
class StalenessTests(unittest.TestCase):
    def test_the_ablated_runs_own_brief_is_the_one_it_is_checked_against(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101, 102), ablation=ADMISSIBILITY)
            run_dir = ablated_run_dir(tmp, ADMISSIBILITY)

            right = runner.brief_staleness(
                run_dir,
                (101, 102),
                runner.BriefStaleness(
                    runner.brief_digest_for(ablate=ADMISSIBILITY), run_dir=run_dir
                ),
            )
            self.assertTrue(right.checked)
            self.assertEqual((), right.stale_brief)
            self.assertEqual((), right.stale)

            # The dirty fixture: the same results, checked against the brief
            # without the ablation, read as a brief that moved. That is the false
            # finding the ablated digest exists to prevent, and it is the reason
            # the checker has to be built the same ablated way.
            wrong = runner.brief_staleness(
                run_dir, (101, 102), runner.BriefStaleness(run_dir=run_dir)
            )
            self.assertEqual((101, 102), wrong.stale_brief)

    def test_a_second_invocation_reuses_an_ablated_cache_rather_than_staling_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            rig.bench(tmp, cases=(101, 102), ablation=CLAUSE_NOTES)
            summary, transport = rig.bench(tmp, cases=(101, 102), ablation=CLAUSE_NOTES)
            # Nothing was re-run: every case was found cached and current, so the
            # scripted transport was never asked for it a second time.
            self.assertEqual([], summary.completed_cases)
            self.assertEqual([101, 102], sorted(summary.cached_cases))
            self.assertEqual(0, transport.calls())
            run_dir = ablated_run_dir(tmp, CLAUSE_NOTES)
            report = runner.grade_run(
                run_dir,
                cases=(101, 102),
                checker=runner.BriefStaleness(
                    runner.brief_digest_for(ablate=CLAUSE_NOTES), run_dir=run_dir
                ),
            )
            self.assertEqual((), report.staleness.stale)


# --------------------------------------------------------------------------
# Refusals, in the library and on the command line
# --------------------------------------------------------------------------
class LibraryRefusalTests(unittest.TestCase):
    def test_the_runner_refuses_an_unknown_ablation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                with self.assertRaises(runner.BenchmarkError):
                    rig.bench(tmp, cases=(101,), ablation="no-such-ablation")

    def test_the_pipeline_refuses_an_unknown_ablation(self):
        transport = transport_for()
        client = rig.client_factory(MODEL, transport)(lambda record: None)
        with self.assertRaises(pipeline.PipelineError):
            pipeline.run_case(
                101,
                client,
                prompts_dir=PROMPTS_DIR,
                judge_votes=1,
                ablate="no-such-ablation",
            )
        self.assertEqual(0, transport.calls(), "a call was made before the refusal")

    def test_the_builder_refuses_an_unknown_ablation(self):
        case = loader.load_case(IMPAIRED_CASE)
        with self.assertRaises(brief.AblationError):
            brief.build_brief_for_case(case, ablate="no-such-ablation")

    def test_the_runner_refuses_an_ablated_run_that_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
            ):
                with self.assertRaises(runner.BenchmarkError):
                    rig.bench(
                        tmp,
                        cases=(101,),
                        ablation=CLAUSE_NOTES,
                        replay_dir=Path(tmp) / "runs" / runner.model_slug(MODEL),
                    )

    def test_run_one_case_refuses_an_ablated_run_that_replays(self):
        with self.assertRaises(runner.BenchmarkError):
            runner.run_one_case(
                101,
                client=None,
                prompts_dir=PROMPTS_DIR,
                expected=None,
                replay=object(),
                ablate=CLAUSE_NOTES,
            )


class RunBenchmarkCommandLineTests(unittest.TestCase):
    """Every refusal happens while the arguments are being parsed."""

    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    runner.main(arguments)
        return errors.getvalue()

    def test_an_unknown_name_is_refused_by_the_choice_list(self):
        message = self.refuse(["--ablate", "no-such-ablation", "--cases", "101"])
        self.assertIn("--ablate", message)

    def test_it_is_refused_with_every_mode_that_reads_a_recorded_run(self):
        for arguments in (
            ["--ablate", CLAUSE_NOTES, "--compare"],
            ["--ablate", CLAUSE_NOTES, "--replay-advocates", "runs/x"],
            ["--ablate", CLAUSE_NOTES, "--replay-check", "runs/x"],
            ["--ablate", CLAUSE_NOTES, "--verify-recorded-drafts", "runs/x"],
            ["--ablate", CLAUSE_NOTES, "--external", "data/external/ryde/case-901.json"],
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("--ablate", message)
                self.assertIn(arguments[2], message)

    def test_the_refusal_is_about_the_combination_and_not_about_the_ablation(self):
        # The dirty fixture's other half: the same switch with no other mode is
        # accepted. Run into a scratch root over the scripted transport, so no
        # model is called.
        with tempfile.TemporaryDirectory() as tmp:
            transport = transport_for()
            summary = runner.run_benchmark(
                MODEL,
                (101,),
                runs_dir=Path(tmp) / "runs",
                prompts_dir=PROMPTS_DIR,
                client_factory=rig.client_factory(MODEL, transport),
                key=rig.answer_key(),
                git_runner=rig.git_runner(),
                progress=lambda text: None,
                judge_votes=1,
                ablation=CLAUSE_NOTES,
            )
            self.assertEqual([101], summary.completed_cases)
            self.assertTrue((ablated_run_dir(tmp, CLAUSE_NOTES) / "case-00101.json").is_file())


class DevelopmentSetsCommandLineTests(unittest.TestCase):
    """The other CLI refuses the same combinations, in its own idiom."""

    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                code = development_sets.main(arguments)
        return code, errors.getvalue()

    def test_it_is_refused_with_every_mode_that_reads_or_reports(self):
        for arguments in (
            ["--ablate", CLAUSE_NOTES, "--report"],
            ["--ablate", CLAUSE_NOTES, "--replay-advocates", "runs/x"],
            ["--ablate", CLAUSE_NOTES, "--replay-check", "runs/x"],
            ["--ablate", CLAUSE_NOTES, "--verify-recorded-drafts", "runs/x"],
        ):
            with self.subTest(arguments=arguments):
                code, errors = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("--ablate", errors)
                self.assertIn(arguments[2], errors)

    def test_an_unknown_name_is_refused_by_the_choice_list(self):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    development_sets.main(["--ablate", "no-such-ablation"])
        self.assertIn("--ablate", errors.getvalue())

    def test_an_ablation_alone_is_accepted_and_writes_under_the_ablation_root(self):
        # The dirty fixture's other half: without a mode that reads a recorded
        # run, the switch reaches the runner. The client factory is replaced so
        # the whole command line runs over the scripted transport.
        with tempfile.TemporaryDirectory() as tmp:
            transport = transport_for()
            with mock.patch.object(
                runner,
                "_default_client_factory",
                return_value=rig.client_factory(MODEL, transport),
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
                            "--ablate",
                            CLAUSE_NOTES,
                            "--runs-dir",
                            str(Path(tmp) / "runs"),
                        ]
                    )
            self.assertEqual(0, code)
            self.assertTrue(transport.calls() > 0)
            self.assertTrue(
                (ablated_run_dir(tmp, CLAUSE_NOTES) / "case-00101.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
