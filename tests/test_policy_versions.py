"""Tests for policy versions.

A policy version is an integer. Version 1 is the three files in ``policy/``
exactly as committed, and it is what every run before this switch used, so
**version 1 is byte-identical** and the first thing this file proves is that:
version 1 rebuilds every one of the 44 recorded ``brief_sha256`` values exactly.

The rest is about the two things an amendment may not do, and both are enforced
rather than asked for. The top-level key set is exact, so an ``edits`` or a
``removes`` key has nowhere to go; and the clause's id must be the next free
number for its prefix, so an id already in use cannot be re-declared. That
matters because ``brief.py`` parses the prose of several existing clauses: an
amendment that rewrote one would change what a brief means while leaving every
id where it was.

Nothing here reaches a real model.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets, run_benchmark as runner  # noqa: E402
from tests import test_run_benchmark as rig  # noqa: E402
from tribunal import loader, policy_versions, precedents  # noqa: E402
from tribunal.model import resolve_model  # noqa: E402

# The id the rig runs its scripted transports under. It is deliberately not the
# headline model, so it must not be used to name a recorded run directory.
MODEL = rig.MODEL
PROMPTS_DIR = rig.PROMPTS_DIR
POLICY_DIR = PROJECT_ROOT / "policy"

# The model the headline runs were made under, read from the one place that
# declares it rather than repeated here.
HEADLINE_MODEL = resolve_model(None)

# The two recorded sets, whose briefs version 1 has to rebuild exactly. The
# corpus is run unlabelled into ``runs/<model>/`` and the second development set
# into ``runs/codex/<model>/``.
CORPUS_RUN_DIR = PROJECT_ROOT / "runs" / runner.model_slug(HEADLINE_MODEL)
CODEX_RUN_DIR = PROJECT_ROOT / "runs" / "codex" / runner.model_slug(HEADLINE_MODEL)
CASE_FILE_RE = re.compile(r"^case-\d{5}\.json$")

CORPUS_CASES = 29
CODEX_CASES = 15

# The next free clause number per prefix, as the three files stand. The numbers
# are pinned here rather than derived, so an amendment added to the repository
# moves this test rather than silently changing what "next free" means.
NEXT_FREE = {"GEN": 4, "NS": 10, "RD": 13}

CATEGORY = "ROUTE_DEVIATION"
PREFIX = "RD"


def amendment_document(clause_id, category="ROUTE_DEVIATION", **overrides):
    """One amendment, valid unless a test makes it otherwise."""
    document = {
        "base_version": 1,
        "proposal_file": "policy/proposals/0001-example.json",
        "proposal_sha256": "a" * 64,
        "report_file": "runs/policy-gaps/report.json",
        "report_sha256": "b" * 64,
        "cluster_id": "C1",
        "cases": [101],
        "approved_by": "Zhou Hanwei",
        "approved_at": "2026-09-29T00:00:00+00:00",
        "clause": {
            "id": clause_id,
            "title": "An added clause",
            "category": category,
            "rule": "A rule that says something.",
            "requires": [],
            "licenses": [],
            "favours": "RIDER",
            "notes": "Added by an amendment.",
        },
    }
    document.update(overrides)
    return document


def write_amendment(root, name, document):
    directory = Path(root) / policy_versions.AMENDMENTS_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def policies_for(category=CATEGORY):
    return loader.load_policies(category, policy_versions.BASE_VERSION)


def files_for(category=CATEGORY):
    return {
        "general": "general.json",
        "category": loader.CATEGORY_POLICY_FILES[category],
    }


def recorded_digests(run_dir, case_loader=None):
    """``{case_no: brief_sha256}`` as a recorded run directory holds it."""
    found = {}
    for path in sorted(Path(run_dir).iterdir()):
        if not CASE_FILE_RE.match(path.name):
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        found[document["case_no"]] = document.get("brief_sha256")
    return found


# --------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------
class PolicyVocabularyTests(unittest.TestCase):
    def test_the_repository_is_at_version_1_and_has_no_amendments(self):
        self.assertEqual(1, policy_versions.BASE_VERSION)
        self.assertEqual(1, policy_versions.current_version())
        self.assertEqual([], policy_versions.amendment_files())

    def test_the_prefix_maps_agree_with_each_other_and_with_the_id_pattern(self):
        self.assertEqual(
            set(policy_versions.PREFIX_FILES), set(policy_versions.PREFIX_CATEGORY)
        )
        for prefix in policy_versions.PREFIX_FILES:
            with self.subTest(prefix=prefix):
                self.assertIsNotNone(
                    policy_versions.CLAUSE_ID_RE.match("POL-{0}-01".format(prefix))
                )
        for prefix in ("XX", "GENX", "gen", "", "NS-"):
            with self.subTest(prefix=prefix):
                self.assertIsNone(
                    policy_versions.CLAUSE_ID_RE.match("POL-{0}-01".format(prefix))
                )

    def test_each_prefix_names_a_real_file_whose_category_it_declares(self):
        for prefix, filename in policy_versions.PREFIX_FILES.items():
            with self.subTest(prefix=prefix):
                document = json.loads(
                    (POLICY_DIR / filename).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    policy_versions.PREFIX_CATEGORY[prefix], document["category"]
                )

    def test_the_next_free_number_for_each_prefix_is_where_the_files_stop(self):
        for prefix, expected in NEXT_FREE.items():
            with self.subTest(prefix=prefix):
                document = json.loads(
                    (
                        POLICY_DIR / policy_versions.PREFIX_FILES[prefix]
                    ).read_text(encoding="utf-8")
                )
                numbers = sorted(
                    int(clause["id"].rsplit("-", 1)[1]) for clause in document["clauses"]
                )
                self.assertEqual(expected, numbers[-1] + 1)

    def test_each_shipped_store_holds_only_a_readme(self):
        # Rule 7 asks for **one** test over the three stores the repository
        # ships, so it is made here rather than split by whichever task added
        # which directory. The precedent store belongs to task 4; the other two
        # are this task's, and they ship empty for the same reason: an amendment
        # is written by a human through ``approve``, which task 6 builds.
        stores = (
            PROJECT_ROOT / "precedents",
            POLICY_DIR / policy_versions.AMENDMENTS_DIRNAME,
            POLICY_DIR / "proposals",
        )
        for directory in stores:
            with self.subTest(directory=str(directory.relative_to(PROJECT_ROOT))):
                self.assertTrue(directory.is_dir())
                self.assertEqual(
                    [policy_versions.README_FILE],
                    sorted(path.name for path in directory.iterdir()),
                )


# --------------------------------------------------------------------------
# Version 1 is byte-identical
# --------------------------------------------------------------------------
class VersionOneIsUnchangedTests(unittest.TestCase):
    def test_version_1_returns_the_files_as_read(self):
        for category in sorted(loader.CATEGORY_POLICY_FILES):
            with self.subTest(category=category):
                self.assertEqual(
                    loader.load_policies(category),
                    loader.load_policies(category, policy_versions.BASE_VERSION),
                )

    def test_version_1_does_not_read_the_amendments_directory(self):
        # A broken amendment must not be able to stop the version-1 measurement,
        # so version 1 returns before the directory is looked at. The fixture is
        # a directory that cannot be listed, and version 1 still builds.
        with mock.patch.object(
            policy_versions,
            "amendment_files",
            side_effect=AssertionError("the amendments directory was read"),
        ):
            policies = loader.load_policies(CATEGORY, policy_versions.BASE_VERSION)
        self.assertIn("clauses", policies["category"])

    def test_version_1_rebuilds_every_recorded_brief_digest_exactly(self):
        corpus = recorded_digests(CORPUS_RUN_DIR)
        self.assertEqual(CORPUS_CASES, len(corpus))

        second_set = development_sets.named("codex")
        codex = recorded_digests(CODEX_RUN_DIR)
        self.assertEqual(CODEX_CASES, len(codex))

        for case_no, recorded in sorted(corpus.items()):
            with self.subTest(set_name="corpus", case_no=case_no):
                self.assertEqual(
                    recorded, runner.current_brief_sha256(case_no)
                )
        for case_no, recorded in sorted(codex.items()):
            with self.subTest(set_name="codex", case_no=case_no):
                self.assertEqual(
                    recorded,
                    runner.current_brief_sha256(
                        case_no, case_loader=second_set.load_case
                    ),
                )

    def test_the_whole_point_is_that_all_forty_four_agree(self):
        # Stated on its own so the count is visible in the test list and not only
        # inside a loop over two dictionaries.
        self.assertEqual(CORPUS_CASES + CODEX_CASES, 44)


# --------------------------------------------------------------------------
# What an amendment may not be
# --------------------------------------------------------------------------
class AmendmentRefusalTests(unittest.TestCase):
    def refusal(self, document, name="0001-example.json", root=None):
        with tempfile.TemporaryDirectory() as tmp:
            where = tmp if root is None else root
            path = write_amendment(where, name, document)
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.load_amendment(path)
        return str(caught.exception)

    def test_an_amendment_that_could_express_an_edit_is_refused(self):
        # There is no key an edit could be written in, which is the mechanism by
        # which "adds one clause" is true rather than intended.
        for extra in ({"edits": [{"id": "POL-RD-01"}]}, {"removes": ["POL-RD-02"]}):
            with self.subTest(extra=sorted(extra)):
                message = self.refusal(
                    amendment_document("POL-RD-13", **extra)
                )
                self.assertIn("unexpected", message)
                self.assertIn(sorted(extra)[0], message)

    def test_an_amendment_that_drops_a_provenance_field_is_refused(self):
        document = amendment_document("POL-RD-13")
        document.pop("approved_by")
        message = self.refusal(document)
        self.assertIn("missing", message)
        self.assertIn("approved_by", message)

    def test_a_clause_that_drops_one_of_its_eight_fields_is_refused(self):
        document = amendment_document("POL-RD-13")
        document["clause"].pop("notes")
        message = self.refusal(document)
        self.assertIn("missing", message)
        self.assertIn("notes", message)

    def test_a_clause_with_a_ninth_field_is_refused(self):
        document = amendment_document("POL-RD-13")
        document["clause"]["replaces"] = "POL-RD-01"
        message = self.refusal(document)
        self.assertIn("unexpected", message)
        self.assertIn("replaces", message)

    def test_an_unknown_prefix_is_refused(self):
        message = self.refusal(amendment_document("POL-XX-01"))
        self.assertIn("POL-XX-01", message)
        self.assertIn("prefix", message)

    def test_an_id_that_is_not_the_right_shape_is_refused(self):
        for clause_id in ("RD-13", "POL-RD-1", "POL-RD-131", "POL-RD-AA", ""):
            with self.subTest(clause_id=clause_id):
                message = self.refusal(amendment_document(clause_id))
                self.assertIn("prefix", message)

    def test_a_category_that_disagrees_with_the_prefix_is_refused(self):
        message = self.refusal(
            amendment_document("POL-RD-13", category="NO_SHOW_CHARGE")
        )
        self.assertIn("NO_SHOW_CHARGE", message)
        self.assertIn("ROUTE_DEVIATION", message)

    def test_an_amendment_that_is_not_an_object_is_refused(self):
        message = self.refusal(["POL-RD-13"])
        self.assertIn("one amendment object", message)

    def test_a_file_that_is_not_named_for_its_number_is_refused(self):
        for name in ("1-example.json", "0001_example.json", "0001-Example.json", "example.json"):
            with self.subTest(name=name):
                document = amendment_document("POL-RD-13")
                with tempfile.TemporaryDirectory() as tmp:
                    write_amendment(tmp, name, document)
                    with self.assertRaises(policy_versions.AmendmentError) as caught:
                        policy_versions.amendment_files(tmp)
                self.assertIn("NNNN-<slug>.json", str(caught.exception))

    def test_a_hole_in_the_sequence_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            write_amendment(tmp, "0003-three.json", amendment_document("POL-RD-14"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.amendment_files(tmp)
        self.assertIn("no holes", str(caught.exception))

    def test_a_number_used_twice_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            write_amendment(tmp, "0001-two.json", amendment_document("POL-RD-14"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.amendment_files(tmp)
        self.assertIn("more than once", str(caught.exception))

    def test_a_directory_under_the_amendments_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / policy_versions.AMENDMENTS_DIRNAME / "0001-dir").mkdir(
                parents=True
            )
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.amendment_files(tmp)
        self.assertIn("must be an amendment", str(caught.exception))

    def test_the_readme_is_not_an_amendment_and_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, policy_versions.README_FILE, {"anything": True})
            self.assertEqual([], policy_versions.amendment_files(tmp))


# --------------------------------------------------------------------------
# Applying them
# --------------------------------------------------------------------------
class ApplyingAmendmentsTests(unittest.TestCase):
    def test_an_amendment_is_appended_and_its_file_gains_the_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-13"))
            applied = policy_versions.apply_amendments(
                policies_for(), 2, files=files_for(), root=tmp
            )
        ids = [clause["id"] for clause in applied["category"]["clauses"]]
        self.assertIn("POL-RD-13", ids)
        self.assertEqual(
            "1.1.0{0}0001".format(policy_versions.AMENDMENT_MARKER),
            applied["category"]["version"],
        )
        # The general policy received nothing, so its version is untouched.
        self.assertEqual("1.0.1", applied["general"]["version"])

    def test_the_input_is_not_modified(self):
        before = policies_for()
        version_before = before["category"]["version"]
        count_before = len(before["category"]["clauses"])
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-13"))
            policy_versions.apply_amendments(before, 2, files=files_for(), root=tmp)
        self.assertEqual(version_before, before["category"]["version"])
        self.assertEqual(count_before, len(before["category"]["clauses"]))

    def test_a_colliding_id_is_refused(self):
        # POL-RD-01 is already there, so an amendment that declares it would be
        # rewriting an existing clause rather than adding one.
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-01"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    policies_for(), 2, files=files_for(), root=tmp
                )
        self.assertIn("next free", str(caught.exception))
        self.assertIn("never edits or replaces", str(caught.exception))

    def test_an_id_past_the_next_free_number_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-15"))
            with self.assertRaises(policy_versions.AmendmentError) as caught:
                policy_versions.apply_amendments(
                    policies_for(), 2, files=files_for(), root=tmp
                )
        self.assertIn("next free", str(caught.exception))

    def test_two_amendments_must_be_ordered(self):
        # 0001 takes RD-13, so 0002 must take RD-14 and not RD-15.
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            write_amendment(tmp, "0002-two.json", amendment_document("POL-RD-15"))
            with self.assertRaises(policy_versions.AmendmentError):
                policy_versions.apply_amendments(
                    policies_for(), 3, files=files_for(), root=tmp
                )

    def test_two_amendments_apply_in_order_and_name_the_highest(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(tmp, "0001-one.json", amendment_document("POL-RD-13"))
            write_amendment(tmp, "0002-two.json", amendment_document("POL-RD-14"))
            applied = policy_versions.apply_amendments(
                policies_for(), 3, files=files_for(), root=tmp
            )
        ids = [clause["id"] for clause in applied["category"]["clauses"]]
        self.assertEqual(["POL-RD-13", "POL-RD-14"], ids[-2:])
        self.assertTrue(applied["category"]["version"].endswith("0002"))

    def test_an_amendment_to_a_policy_the_brief_does_not_carry_is_skipped(self):
        # A no-show clause has no business in a route-deviation brief, and one
        # run briefs cases of both categories.
        with tempfile.TemporaryDirectory() as tmp:
            write_amendment(
                tmp,
                "0001-example.json",
                amendment_document("POL-NS-10", category="NO_SHOW_CHARGE"),
            )
            applied = policy_versions.apply_amendments(
                policies_for(CATEGORY), 2, files=files_for(CATEGORY), root=tmp
            )
        self.assertEqual("1.1.0", applied["category"]["version"])

    def test_a_version_above_the_repository_is_refused(self):
        with self.assertRaises(policy_versions.AmendmentError) as caught:
            policy_versions.apply_amendments(
                policies_for(), 2, files=files_for(), root=tempfile.mkdtemp()
            )
        self.assertIn("there is no policy version 2", str(caught.exception))

    def test_a_version_below_one_is_refused(self):
        for version in (0, -1):
            with self.subTest(version=version):
                with self.assertRaises(policy_versions.AmendmentError) as caught:
                    policy_versions.apply_amendments(
                        policies_for(), version, files=files_for()
                    )
                self.assertIn("lowest policy version", str(caught.exception))

    def test_a_version_that_is_not_an_integer_is_refused(self):
        for version in ("2", 2.0, True, None):
            with self.subTest(version=version):
                with self.assertRaises(policy_versions.AmendmentError) as caught:
                    policy_versions.apply_amendments(
                        policies_for(), version, files=files_for()
                    )
                self.assertIn("is an integer", str(caught.exception))

    def test_applying_twice_does_not_stack_the_suffix(self):
        once = policy_versions._version_with_suffix("1.1.0", 1)
        self.assertEqual(
            "1.1.0{0}0001".format(policy_versions.AMENDMENT_MARKER), once
        )
        self.assertEqual(
            "1.1.0{0}0002".format(policy_versions.AMENDMENT_MARKER),
            policy_versions._version_with_suffix(once, 2),
        )

    def test_the_amendments_directory_may_be_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], policy_versions.amendment_files(tmp))
            self.assertEqual(1, policy_versions.current_version(tmp))


# --------------------------------------------------------------------------
# Where a later version writes
# --------------------------------------------------------------------------
class PolicyVersionDestinationTests(unittest.TestCase):
    def test_a_later_version_has_a_directory_of_its_own(self):
        runs = Path("/tmp/runs")
        self.assertEqual(
            runs / "policy-v2" / runner.model_slug(MODEL),
            runner.policy_v_run_directory(runs, 2, MODEL),
        )
        self.assertEqual("policy-v3", runner.policy_v_directory_name(3))

    def test_a_later_version_cannot_land_in_the_headline_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with self.assertRaises(runner.BenchmarkError) as caught:
                runner.assert_policy_v_destination(runs / runner.model_slug(MODEL), runs, 2)
        self.assertIn("may only be written under", str(caught.exception))

    def test_one_version_cannot_land_in_another_versions_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            version2 = runner.policy_v_run_directory(runs, 2, MODEL)
            self.assertEqual(
                version2, runner.assert_policy_v_destination(version2, runs, 2)
            )
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_policy_v_destination(version2, runs, 3)

    def test_a_dot_dot_name_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            escaped = runs / "policy-v2" / ".." / runner.model_slug(MODEL)
            with self.assertRaises(runner.BenchmarkError):
                runner.assert_policy_v_destination(escaped, runs, 2)


# --------------------------------------------------------------------------
# Staleness at a version
# --------------------------------------------------------------------------
class StalenessAtAVersionTests(unittest.TestCase):
    def test_the_checker_asks_for_the_version_it_was_given(self):
        seen = []

        def fake(case_no, case_loader=None, ablate=None, policy_version=1):
            seen.append(policy_version)
            return "e" * 64

        with mock.patch.object(runner, "current_brief_sha256", side_effect=fake):
            checker = runner.BriefStaleness(policy_version=3)
            self.assertEqual("e" * 64, checker.current_digest(101))
        self.assertEqual([3], seen)

    def test_the_memo_is_keyed_by_case_and_version_together(self):
        calls = []

        def digest(case_no):
            calls.append(case_no)
            return "f" * 64

        checker = runner.BriefStaleness(digest=digest, policy_version=2)
        self.assertEqual("f" * 64, checker.current_digest(101))
        self.assertEqual("f" * 64, checker.current_digest(101))
        self.assertEqual([101], calls)
        self.assertEqual([(101, 2)], list(checker._current))

    def test_an_injected_digest_is_used_as_it_stands(self):
        # ``brief_digest_for`` closes the version over the callable it returns,
        # so a checker built with one must not re-bind a version on top of it.
        checker = runner.BriefStaleness(
            digest=lambda case_no: "g" * 64, policy_version=2
        )
        self.assertEqual("g" * 64, checker.current_digest(101))

    def test_brief_digest_for_still_returns_none_for_the_all_defaults_case(self):
        self.assertIsNone(runner.brief_digest_for())
        self.assertIsNotNone(runner.brief_digest_for(policy_version=2))


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

    def test_a_later_version_is_refused_with_every_replay_flag(self):
        for arguments in (
            ["--policy-version", "2", "--compare"],
            ["--policy-version", "2", "--replay-advocates", "runs/x"],
            ["--policy-version", "2", "--replay-check", "runs/x"],
            ["--policy-version", "2", "--verify-recorded-drafts", "runs/x"],
            ["--policy-version", "2", "--external", "data/external/ryde/case-901.json"],
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("policy-version", message)
                self.assertIn(arguments[-2], message)

    def test_a_later_version_is_refused_beside_the_other_two_switches(self):
        for arguments in (
            ["--policy-version", "2", "--ablate", "clause-notes"],
            ["--policy-version", "2", "--precedents"],
        ):
            with self.subTest(arguments=arguments):
                message = self.refuse(arguments)
                self.assertIn("at most one of", message)

    def test_version_1_is_not_a_switch_and_is_not_refused_with_them(self):
        # Version 1 is the default, so naming it changes nothing and must not
        # count as one of the switches that change what an agent is given. With
        # it named, ``--ablate`` and ``--compare`` are still refused for their
        # own reason and not for the mutual exclusion.
        message = self.refuse(
            ["--policy-version", "1", "--ablate", "clause-notes", "--compare"]
        )
        self.assertNotIn("at most one of", message)
        self.assertIn("--ablate", message)
        self.assertIn("--compare", message)

    def test_a_version_the_repository_does_not_have_is_refused_before_a_client(self):
        # The same shape as the development-set test below: the runs root is a
        # scratch one, so nothing here resolves a destination under the
        # repository's own runs/.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                runner,
                "_default_client_factory",
                side_effect=AssertionError("a client was built"),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()) as errors:
                        code = runner.main(
                            [
                                "--model", MODEL,
                                "--cases", "101",
                                "--policy-version", "2",
                                "--runs-dir", str(Path(tmp) / "runs"),
                            ]
                        )
        self.assertEqual(1, code)
        self.assertIn("there is no policy version 2", errors.getvalue())

    def test_version_1_is_accepted_and_writes_to_the_ordinary_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = rig.ScriptedTransport(
                rig.produced_from_key(rig.answer_key())
            )
            with mock.patch.object(
                runner,
                "_default_client_factory",
                return_value=rig.client_factory(MODEL, transport),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = runner.main(
                        [
                            "--model", MODEL,
                            "--cases", "101",
                            "--policy-version", "1",
                            "--runs-dir", str(Path(tmp) / "runs"),
                        ]
                    )
            self.assertEqual(0, code)
            self.assertTrue(transport.calls() > 0)
            runs = Path(tmp) / "runs"
            self.assertTrue(
                (runs / runner.model_slug(MODEL) / "case-00101.json").is_file()
            )
            self.assertFalse((runs / "policy-v1").exists())


class DevelopmentSetsCommandLineTests(unittest.TestCase):
    def refuse(self, arguments):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                with contextlib.redirect_stderr(io.StringIO()) as errors:
                    code = development_sets.main(arguments)
        return code, errors.getvalue()

    def test_a_later_version_is_refused_with_every_mode_that_reads_a_run(self):
        for arguments in (
            ["--policy-version", "2", "--report"],
            ["--policy-version", "2", "--replay-advocates", "runs/x"],
            ["--policy-version", "2", "--replay-check", "runs/x"],
            ["--policy-version", "2", "--verify-recorded-drafts", "runs/x"],
        ):
            with self.subTest(arguments=arguments):
                code, message = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("--policy-version", message)
                self.assertIn(arguments[-2], message)

    def test_a_later_version_is_refused_beside_the_other_two_switches(self):
        for arguments in (
            ["--policy-version", "2", "--ablate", "clause-notes"],
            ["--policy-version", "2", "--precedents"],
        ):
            with self.subTest(arguments=arguments):
                code, message = self.refuse(arguments)
                self.assertEqual(1, code)
                self.assertIn("at most one of", message)

    def test_an_unknown_version_is_reachable_and_says_so(self):
        # The flag is a plain integer, so a version that does not exist is not a
        # parser error: it is refused by the runner with a message naming the
        # version the repository is actually at. The runs root is a scratch one,
        # so the refusal is about the version and this test never resolves a
        # destination under the repository's own runs/.
        with tempfile.TemporaryDirectory() as tmp:
            code, message = self.refuse(
                [
                    "--set",
                    "codex",
                    "--policy-version",
                    "2",
                    "--cases",
                    "9101",
                    "--runs-dir",
                    str(Path(tmp) / "runs"),
                ]
            )
        self.assertEqual(1, code)
        self.assertIn("there is no policy version 2", message)


# --------------------------------------------------------------------------
# Nothing may glob the policy directory
# --------------------------------------------------------------------------
class NothingGlobsThePolicyDirectoryTests(unittest.TestCase):
    """``policy/`` gained two subdirectories, and a glob would now find them.

    ``policy/amendments/README.md`` and ``policy/proposals/README.md`` are not
    policy files. A module that listed ``policy/`` to find the three files would
    start reading them, so every read has to name its file.
    """

    GLOB_CALLS = re.compile(r"\.(glob|rglob|iterdir|listdir)\(")

    def source_files(self):
        for directory in ("tribunal", "eval", "ui", "tests"):
            for path in sorted((PROJECT_ROOT / directory).glob("*.py")):
                yield path

    def test_no_module_lists_the_policy_directory(self):
        offenders = []
        for path in self.source_files():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if not self.GLOB_CALLS.search(line):
                    continue
                # ``POLICY_DIR / <subdirectory>`` is a listing of one of the two
                # subdirectories, which is what this file's own README check
                # does. The hazard is a listing of ``policy/`` itself, so that is
                # what is looked for.
                if "policy" in line.lower() and "POLICY_DIR / " not in line:
                    offenders.append(
                        "{0}:{1}: {2}".format(
                            path.relative_to(PROJECT_ROOT), number, line.strip()
                        )
                    )
        self.assertEqual([], offenders)

    def test_the_three_policy_files_are_read_by_name(self):
        # The positive half: the loader names all three, so there is nothing for
        # a listing to find.
        source = (PROJECT_ROOT / "tribunal" / "loader.py").read_text(encoding="utf-8")
        self.assertIn("GENERAL_POLICY_FILE", source)
        self.assertIn("CATEGORY_POLICY_FILES", source)
        for filename in policy_versions.PREFIX_FILES.values():
            with self.subTest(filename=filename):
                self.assertIn(filename, source)


# --------------------------------------------------------------------------
# A replay may not mix two policy versions
# --------------------------------------------------------------------------
CLAUSE_NOTES = "clause-notes"


def version_two_amendments(tmp):
    """One real amendment under ``<tmp>/amendments``, and the patch that finds it.

    ``loader.load_policies`` calls ``apply_amendments`` with no root, so the
    amendments directory is resolved from the repository -- which is at version
    1 and holds none. This points that one lookup at a temporary directory
    holding one valid amendment, which is what makes a *genuine* version-2 run
    possible without adding an amendment to the repository or weakening the
    refusal that a version with no amendments behind it gets.
    """
    write_amendment(tmp, "0001-example.json", amendment_document("POL-RD-13"))
    directory = Path(tmp) / policy_versions.AMENDMENTS_DIRNAME
    return mock.patch.object(
        policy_versions, "amendments_dir", lambda root=None: directory
    )


def version_two_run(tmp, cases=(101,)):
    """A genuine version-2 run of ``cases`` under ``<tmp>/runs``.

    Returns ``(run directory, summary)``. Every case's brief is built from
    policy version 2, so the run's own artifacts record version 2 and its
    destination is ``runs/policy-v2/<model>/``.
    """
    transport = rig.ScriptedTransport(rig.produced_from_key(rig.answer_key()))
    with version_two_amendments(tmp):
        summary = runner.run_benchmark(
            MODEL,
            list(cases),
            runs_dir=Path(tmp) / "runs",
            prompts_dir=PROMPTS_DIR,
            client_factory=rig.client_factory(MODEL, transport),
            key=rig.answer_key(),
            git_runner=rig.git_runner(),
            progress=lambda text: None,
            judge_votes=1,
            policy_version=2,
        )
    landed = (
        Path(tmp)
        / "runs"
        / runner.policy_v_directory_name(2)
        / runner.model_slug(MODEL)
    )
    return landed, summary


class ReplayAcrossVersionsTests(unittest.TestCase):
    """A replay may not hand the judge one version's brief and record another.

    ``replay_verdict`` rebuilds each case's brief at the version the **source**
    run recorded and hands the judge that brief. The only refusal was about the
    version this run was *given*, so a plain run pointed at a version-2 source
    handed the judge a version-2 brief, wrote ``policy_version: 1`` into every
    artifact, and -- because a plain run's destination is ``runs/<model>/`` --
    put the result in the headline directory. The two halves of every case would
    then have been produced under different policy while the run said they had
    not.
    """

    def test_a_version_2_source_replayed_into_a_plain_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, summary = version_two_run(tmp)
            self.assertEqual([101], summary.completed_cases)
            self.assertTrue((source / "case-00101.json").is_file())
            self.assertEqual(
                2,
                runner.configuration_of(
                    runner.read_json(runner.case_cache_path(source, 101))
                )["policy_version"],
            )

            # ``LLMClient`` patched to raise, not the factory: the factory only
            # closes over the model, and what must not happen is a *client*.
            with mock.patch.object(
                runner.llm,
                "LLMClient",
                side_effect=AssertionError("a model was called"),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()) as errors:
                        code = runner.main(
                            [
                                "--model", MODEL,
                                "--cases", "101",
                                "--runs-dir", str(Path(tmp) / "runs"),
                                "--replay-advocates", str(source),
                            ]
                        )
            self.assertEqual(1, code)
            message = errors.getvalue()
            self.assertIn("policy version 2", message)
            self.assertIn("version 1", message)
            # Refused before anything was written: no headline directory, and no
            # model called -- the patch above would have raised.
            self.assertFalse((Path(tmp) / "runs" / runner.model_slug(MODEL)).exists())

    def test_the_check_refuses_it_without_a_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, _summary = version_two_run(tmp)
            with self.assertRaises(runner.BenchmarkError) as caught:
                runner.check_replay(
                    source,
                    (101,),
                    model=MODEL,
                    prompts_dir=PROMPTS_DIR,
                    policy_version=policy_versions.BASE_VERSION,
                )
        self.assertIn("policy version 2", str(caught.exception))

    def test_a_check_with_no_version_of_its_own_is_left_alone(self):
        """The two read-only analyses pass no version, and must keep working.

        ``eval.baselines`` and ``eval.verify_drafts`` read a recorded run rather
        than producing one, so they have no version of their own to compare the
        source against -- and a version-2 source has to stay analysable by them.
        """
        with tempfile.TemporaryDirectory() as tmp:
            source, _summary = version_two_run(tmp)
            with version_two_amendments(tmp):
                check = runner.check_replay(
                    source, (101,), model=MODEL, prompts_dir=PROMPTS_DIR
                )
        self.assertEqual([101], check.accepted_cases)


# --------------------------------------------------------------------------
# The switches the command line accepts are the switches it honours
# --------------------------------------------------------------------------
class SwitchForwardingTests(unittest.TestCase):
    """Every switch the command line accepts has to reach the runner.

    ``--ablate`` and ``--precedents`` were parsed, refused in combination with
    the modes they cannot be combined with, and then never passed to
    :func:`run_benchmark` at all. ``--ablate clause-notes`` therefore ran an
    *unablated* set and wrote it into ``runs/<model>/`` -- the opposite of what
    the flag's own help text and ``runs/README.md`` say. The forwarding was
    fixed and nothing held it, so removing one keyword would put the defect back
    with the suite still green. The first test below is what holds it, at the
    boundary where the keyword would be lost; the second makes the same claim
    from the outside, in where the files land.
    """

    SWITCHES = (
        (["--ablate", CLAUSE_NOTES], "ablation", CLAUSE_NOTES),
        (["--precedents"], "precedents", runner.PRECEDENTS_STORE),
        (["--policy-version", "2"], "policy_version", 2),
    )

    def test_each_switch_reaches_the_runner(self):
        for switch, keyword, value in self.SWITCHES:
            with self.subTest(switch=switch):
                seen = {}

                def stub(model, cases, **kwargs):
                    seen.update(kwargs)
                    return mock.Mock(ok=True)

                with mock.patch.object(runner, "run_benchmark", side_effect=stub):
                    with mock.patch.object(runner, "print_summary"):
                        with contextlib.redirect_stdout(io.StringIO()):
                            runner.main(
                                ["--model", MODEL, "--cases", "101"] + switch
                            )
                self.assertIn(keyword, seen)
                self.assertEqual(value, seen[keyword])

    def test_each_switch_writes_under_the_directory_its_help_text_names(self):
        for switch, expected in (
            (["--ablate", CLAUSE_NOTES], ("ablation", CLAUSE_NOTES)),
            (["--precedents"], ("precedents",)),
            (["--policy-version", "2"], ("policy-v2",)),
        ):
            with self.subTest(switch=switch):
                with tempfile.TemporaryDirectory() as tmp:
                    runs = Path(tmp) / "runs"
                    transport = rig.ScriptedTransport(
                        rig.produced_from_key(rig.answer_key())
                    )
                    with version_two_amendments(tmp):
                        with mock.patch.object(
                            runner,
                            "_default_client_factory",
                            return_value=rig.client_factory(MODEL, transport),
                        ):
                            with contextlib.redirect_stdout(io.StringIO()):
                                code = runner.main(
                                    [
                                        "--model", MODEL,
                                        "--cases", "101",
                                        "--judge-votes", "1",
                                        "--runs-dir", str(runs),
                                    ] + switch
                                )
                    self.assertEqual(0, code)
                    landed = runs.joinpath(*expected, runner.model_slug(MODEL))
                    self.assertTrue((landed / "case-00101.json").is_file())
                    self.assertTrue((landed / runner.METADATA_FILE).is_file())
                    # And nothing at all in the headline directory.
                    self.assertFalse((runs / runner.model_slug(MODEL)).exists())


# --------------------------------------------------------------------------
# A closure of a case from a later-version run
# --------------------------------------------------------------------------
class ClosingAtARecordedVersionTests(unittest.TestCase):
    """``precedents close`` rebuilds the brief at the version the case records.

    ``close`` checks the rebuilt brief's digest against the one the case file
    records, and it rebuilt at version 1 unconditionally. A case from a run
    briefed at version 2 therefore rebuilt to a different digest and was
    refused -- so no case of a later-version run could be closed at all, which
    is the one thing the library exists to collect.
    """

    def test_a_case_of_a_version_two_run_can_be_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, summary = version_two_run(tmp, cases=(101,))
            self.assertEqual([101], summary.completed_cases)
            store = Path(tmp) / precedents.PRECEDENTS_DIRNAME
            # The patch is held open across the closure: ``close`` rebuilds the
            # brief, so it resolves the amendments directory the way the run
            # that wrote the case file did.
            with version_two_amendments(tmp):
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    code = precedents.main(
                        [
                            "--store", str(store),
                            "close",
                            "--run-dir", str(run_dir),
                            "--case", "101",
                            "--ruling", "PARTIAL_REFUND",
                            "--clause", "POL-RD-02",
                            "--closed-by", "A Reviewer",
                            "--summary", "A reviewer closed this case.",
                        ]
                    )
            self.assertEqual(0, code)
            self.assertIn("P-0001", out.getvalue())
            entries = precedents.read_entries(precedents.store_path(store))
            self.assertEqual(1, len(entries))
            self.assertEqual(2, entries[0]["policy_version"])


# --------------------------------------------------------------------------
# A policy version below the lowest one
# --------------------------------------------------------------------------
class PolicyVersionArgumentTests(unittest.TestCase):
    """A version below 1 is refused while the command line is read.

    The refusal used to come from the runner, after the value had been parsed
    and carried on the namespace: 0 or -1 was a namespace field like any other
    until something asked the policy for it. It is refused at parse time now, in
    both runners, so no client is built and no destination is named for a
    version that names nothing.
    """

    def test_the_validator_accepts_the_versions_the_repository_has(self):
        self.assertEqual(1, runner.policy_version_argument("1"))
        self.assertEqual(2, runner.policy_version_argument("2"))

    def test_the_validator_refuses_a_version_below_one(self):
        for text in ("0", "-1", "-99"):
            with self.subTest(text=text):
                with self.assertRaises(argparse.ArgumentTypeError) as caught:
                    runner.policy_version_argument(text)
                self.assertIn("lowest policy version is 1", str(caught.exception))

    def test_the_validator_refuses_something_that_is_not_an_integer(self):
        with self.assertRaises(argparse.ArgumentTypeError) as caught:
            runner.policy_version_argument("banana")
        self.assertIn("is an integer", str(caught.exception))

    def test_the_run_benchmark_command_line_refuses_it_before_a_client(self):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as caught:
                    runner.main(
                        ["--model", MODEL, "--cases", "101", "--policy-version", "0"]
                    )
        self.assertEqual(2, caught.exception.code)
        self.assertIn("lowest policy version is 1", errors.getvalue())

    def test_the_development_sets_command_line_refuses_it_too(self):
        with mock.patch.object(
            runner.llm, "LLMClient", side_effect=AssertionError("a model was called")
        ):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as caught:
                    development_sets.main(
                        ["--set", "corpus", "--cases", "101", "--policy-version", "0"]
                    )
        self.assertEqual(2, caught.exception.code)
        self.assertIn("lowest policy version is 1", errors.getvalue())


# --------------------------------------------------------------------------
# A number in an amendment file
# --------------------------------------------------------------------------
class AmendmentNumberTests(unittest.TestCase):
    """A number in an amendment file arrives as a ``Decimal``.

    The amendment's clause is copied straight into the brief the agents are
    handed, so a float here would be the one place a policy number reached the
    brief as a binary float. Every field a clause carries is a string or a list
    of strings today, so there is no amount for the schema to hold; the read is
    pinned on a number inside ``requires``, which is the list a structured
    requirement would go in.
    """

    def test_a_number_in_an_amendment_is_read_as_a_decimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = amendment_document("POL-RD-13")
            document["clause"]["requires"] = [
                {"clause": "POL-RD-02", "threshold": 250.0}
            ]
            path = write_amendment(tmp, "0001-example.json", document)
            # The file itself carries a float: the point is how it is read.
            self.assertIn("250.0", path.read_text(encoding="utf-8"))
            loaded = policy_versions.load_amendment(path)
        value = loaded["clause"]["requires"][0]["threshold"]
        self.assertIsInstance(value, Decimal)
        self.assertNotIsInstance(value, float)
        self.assertEqual(Decimal("250.0"), value)


if __name__ == "__main__":
    unittest.main()
