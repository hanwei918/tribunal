"""The third sealed set: registering it, the guards around its single run, and the
bundle it was imported from.

``sealed-v1`` is 24 cases under ``data/external/sealed-v1/``, keyed by
``eval/answers/sealed-v1/ground_truth.json``. Like the held-out set and the
second sealed set it is **not** a development set: it was prepared by
Claude, independent of prompt tuning, and opened by the policy owner's assistant
before the freeze (see README), it was imported on 2026-10-09, it was run exactly
once, on 2026-10-10, from the commit ``feb7174``, whose ``tribunal/``, ``prompts/``
and ``policy/`` trees equal those at ``freeze-2026-10-09``, and that single run is
the submission's third generalisation figure. Its registration fixes policy
version 6, so it was run at version 6 with no flag and ``--policy-version`` is
refused for it. Its single run **has** been made, so its root is closed outright:
nothing is created under it again, the plain sealed run included.

What is asserted here:

* **It is registered, and it is apart.** Its own cases, its own key, its own
  loader and its own runs root; it is absent from ``DEVELOPMENT_SETS``, so
  ``--set all`` does not run it and the combined figure does not include it.
* **The bundle digest table.** Every file the archive shipped is listed with its
  sha256: the files imported into the repository are held to it, and the two kept
  outside the repository are held to their absence and to the marker the note and
  this module both carry.
* **Its switches are refused.** ``--force`` and each of the frozen arguments are
  refused for it, and the frozen invocation's arguments are accepted through the
  refusal function rather than by running it.
* **Its root is closed.** Its single run has been made, so no permit opens it and
  every destination under it -- the plain sealed run's own directory included --
  is refused.
* **The sealed run is the owner's.** Without ``TRIBUNAL_SEALED_RUN=sealed-v1``
  the invocation is refused before a client is built and writes nothing.
* **Its structure holds.** All 24 cases load through the set's own loader and
  their briefs build at version 6; the key loads through
  ``eval.grade.load_answer_key`` and holds 24 records each carrying all four
  graded fields; and no answer field appears anywhere in a case file. These
  assert on counts and on keys, never on a value.

No model is called anywhere in this module. Every invocation of the command line
here is refused before a client is built, and ``LLMClient`` is patched to raise so
that a guard which let a run start fails the test instead of reaching the network.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets as sets, grade, run_benchmark  # noqa: E402
from tribunal import brief, loader  # noqa: E402

MODEL = "deepseek/deepseek-flash"
SEALED_V1 = sets.SEALED_V1

# The set's own directories, named here so a test can say which one it means.
SEALED_V1_CASES_DIR = PROJECT_ROOT / "data" / "external" / "sealed-v1"
SEALED_V1_KEY_PATH = PROJECT_ROOT / "eval" / "answers" / "sealed-v1" / "ground_truth.json"
SEALED_V1_EXTERNAL_DIR = PROJECT_ROOT / "eval" / "external" / "sealed-v1"

# 301-312 and 401-412: two twelve-wide ranges, so the count and the ranges are
# written down rather than assumed from the files that happen to be there.
ALL_SEALED_V1_CASES = tuple(range(301, 313)) + tuple(range(401, 413))

# The first case of the set, used as the case a scratch fixture "has a result"
# for. It is a number, never a value.
SENTINEL_CASE = 301

# The import note, whose digest table is the record of every file the archive
# shipped. Reading it is reading a document this repository wrote, not the set.
IMPORT_NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-09-sealed-v1-imported.md"

# The marker both the note and this module carry against the two files the archive
# shipped that are **not** imported.
KEPT_OUTSIDE_MARKER = (
    "kept outside the repository: written in Chinese; an English translation is "
    "committed at"
)

# Every file the archive shipped, as `(path, sha256)`. The path is the
# repository path for a file that was imported and the **archive** path for one
# that was kept outside. The digests are the archive's own -- an imported file is
# byte-identical to its archive entry, and a kept-outside file is only ever
# hashed, never read. The two kept-outside rows are the archive's `README.md` and
# `DESIGN.md`, both written in Chinese and both answer-bearing at case level.
BUNDLE_FILES = (
    ("data/external/sealed-v1/case-00301.json", "de57a0981fa9e9f81469d8bb3de185f9afe50deb5d56568dff0956ee1753b951"),
    ("data/external/sealed-v1/case-00302.json", "dccd462dd75773c95bab65aa19409b3b29f66916c3b1cd84c4efc8c561f7cd56"),
    ("data/external/sealed-v1/case-00303.json", "cd1b48fd3e421ed24e684fc1ef2563dc8f00dbbb9f39a8d83847fcfd7cbedde1"),
    ("data/external/sealed-v1/case-00304.json", "bad5591a87c127c553e481f7d35ec2b4508b6d762f03364a841d80af57cb03ee"),
    ("data/external/sealed-v1/case-00305.json", "165d53bf117e349b34d619137875437e0c37a4520492e52affc4895101d76c29"),
    ("data/external/sealed-v1/case-00306.json", "08adf9263f2124db4a02fb6b47e781fbd7a5a86bd8c6982a6d6b7a4e6ee3ceac"),
    ("data/external/sealed-v1/case-00307.json", "696ab2f360089afd167e2946a7b88d50a58be39d8ddd34a2b9a01b651dfc05f1"),
    ("data/external/sealed-v1/case-00308.json", "1c79116c9f86dd54e214787768a604d15deaa040920d490a7d9dfddbfb44e359"),
    ("data/external/sealed-v1/case-00309.json", "eeb710c09c2b2f3687f8ef0ac240f11c85d710b471ba31217873f6f6a136a231"),
    ("data/external/sealed-v1/case-00310.json", "78731f6c0c35fc3017b2a567c8b1c1f1d5686a49f20b686feabb95ac0f2def47"),
    ("data/external/sealed-v1/case-00311.json", "d3c07949861631f38ae390fbe51227a035e3a89b2b14742a537e18f067a5acd3"),
    ("data/external/sealed-v1/case-00312.json", "9ddbf9945e9430a9bba9f312b55f96b68d372b55853421ed132e789ba5336e82"),
    ("data/external/sealed-v1/case-00401.json", "36a16e50f91a867fda1a6a4022c3692bab6596fa4a76b2dac93dcd523e54a5ee"),
    ("data/external/sealed-v1/case-00402.json", "2cd70620fd0ae6a025e5ee31e935acdf0957f167a1249837f84d3bb804726e77"),
    ("data/external/sealed-v1/case-00403.json", "d761ebc64a3dc6f0e83f8b412b6644daae157aa544106ee3593905b8f3baec45"),
    ("data/external/sealed-v1/case-00404.json", "e28ba333bfe7afddd66fd764e5070b55c1543793b80276673d84f2588103b3cf"),
    ("data/external/sealed-v1/case-00405.json", "8a862fc7deec769fc533dfe00bc82dff3ab24a0d279d217d773aa5f47aab2e15"),
    ("data/external/sealed-v1/case-00406.json", "e1ea97954f51a533c7fc1c1c736425ca1e66f37d8c071b4a6c62c58c24c888f2"),
    ("data/external/sealed-v1/case-00407.json", "ab6a81440edd629c3585fa0af699cee2e5bbacc0f6a7fde860f72fd26bc4f482"),
    ("data/external/sealed-v1/case-00408.json", "50907cce41674cdf8ba4ffb098682d4ad5fda99a369731ecf049649e5c737dc4"),
    ("data/external/sealed-v1/case-00409.json", "d164f606046bcac553e50ff2f9ba5eaee6b3f531e95abd3237f00d285ee555df"),
    ("data/external/sealed-v1/case-00410.json", "237a8a9dd6f3e8dfc6767dc172bbc79fe4667f6d104890532dad631440d710b4"),
    ("data/external/sealed-v1/case-00411.json", "82b0c90a3868ed444b331ec5df6fcc70e6a933165d7d453bcbbb4adc731b4eaf"),
    ("data/external/sealed-v1/case-00412.json", "9172a6fffea5fe8e302775a8751beae9259e1058b71b4447774325e309d04781"),
    ("data/external/sealed-v1/index.json", "d55b706f1898786a4c48013c3de7de84e0be94f4a8b93aa12f334ee69e1de71e"),
    ("eval/answers/sealed-v1/ground_truth.json", "f430f6c017e109bd0feee86e3eac611dab7b087dee51ec5f644eb2eb9880b353"),
    ("eval/external/sealed-v1/eval_index.json", "989bbf5f8d61efe32d6545c4aea4ce48379a44edd192db1c5cdaf233ad49b3ee"),
    ("eval/external/sealed-v1/MANIFEST.json", "f4eb7a4ffc1841b927e98dd7782faa1f160bd7f0cb9db21ec3c91ad31b43b12d"),
    ("eval/external/sealed-v1/gen/build.py", "d508efba157b7b2123f49c97d0bb779f7c27936365f6a4b529d725aca2758293"),
    ("eval/external/sealed-v1/gen/core.py", "0793379e73091aba1093bd1b034744fa569e632cad0feaedfb06d0a4af0d8ae4"),
    ("eval/external/sealed-v1/gen/ns_cases.py", "2766364e74ec02e0be8531a1b793324bee1a023531e8cc68b7f1fee231cdac19"),
    ("eval/external/sealed-v1/gen/places.py", "d5b10bf1af2d3009953d58e23c801f8cdfdccedf65086c1cb748d4b0a8f9c21b"),
    ("eval/external/sealed-v1/gen/rd_cases.py", "43641e912bf2b910c14f0e07c6b1fede61e84a6a8a1e9f6137efd89d829d5ded"),
    ("eval/external/sealed-v1/gen/validate.py", "564db1e458ccfbb172bb85ebfb5b94a464555c5b382811868fd9231da0ddd1e3"),
    ("README.md", "ad4826f9bd81c6a0997d8fd2c7d5e44739b9d69ce37db021a540b4484c50a7dd"),
    ("DESIGN.md", "3341b4423fa45e9198c347e9db4723d1548789c012638ae6190e2adf9f8e24a4"),
)

# The two files of the archive that are not imported, by their archive path. Both
# are written in Chinese, which the standing language rule forbids in any tracked
# text file outside ``runs/``, and both are answer-bearing at case level, so
# neither is opened, translated or summarised before the sealed run is committed.
KEPT_OUTSIDE_THE_REPOSITORY = ("README.md", "DESIGN.md")

# The two files of the archive this repository re-serialised on import, and the
# digest of the archive's own bytes. A digest of a file cannot survive that file
# being re-serialised, so neither matches the committed file -- which is why the
# committed digests are in the table above and these are recorded here.
RESERIALISED_ON_IMPORT = {
    "data/external/sealed-v1/index.json": "d96b0d7f26c3a62ce5437f4980fecf17915dcfd3602b06308d0f280790552647",
    "eval/answers/sealed-v1/ground_truth.json": "412d60bdf207b2be7f66986f40dc4d517b084df7e45dc4c12b566686cddd7f6d",
}


def _run_cli(arguments):
    """``sets.main``, with both streams captured and no client buildable.

    Every invocation of the command line for ``sealed-v1`` is refused before a
    client is built, so no test here may be able to build one: the class is
    patched to raise for the duration of the call, and a guard that let a run
    start fails the test instead of reaching the network. Returns
    ``(code, out, err)``.
    """
    stdout, stderr = io.StringIO(), io.StringIO()
    original, refuse = _refuse_to_build_a_client()
    run_benchmark.llm.LLMClient = refuse
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = sets.main(arguments)
    finally:
        run_benchmark.llm.LLMClient = original
    return code, stdout.getvalue(), stderr.getvalue()


def _run_cli_over(runs, arguments):
    """``_run_cli`` with both modules' ``RUNS_DIR`` moved to ``runs``.

    The sealed set's run root is fixed at the repository's own ``runs/``, so a
    test that wants a scratch root moves the constant rather than passing the
    flag: ``--runs-dir`` is refused for this set. Both modules are moved, because
    the command line reads one and the runner reads the other.
    """
    with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
        run_benchmark, "RUNS_DIR", runs
    ):
        return _run_cli(arguments)


def _refuse_to_build_a_client():
    """Patch ``LLMClient`` to raise, so a guard that let a run start fails.

    A switch that got past its refusal would build a client and start running
    cases against the real key in the repository's ``.env``. Patching the class
    is what turns that into a test failure instead of a paid call.
    """
    original = run_benchmark.llm.LLMClient

    def refuse(*arguments, **keywords):
        raise AssertionError(
            "a client was built, so a switch was accepted that must have been refused"
        )

    return original, refuse


def _state(directory):
    """Every file under a directory, with its bytes."""
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(Path(directory).rglob("*"))
        if path.is_file()
    }


def _frozen_arguments(**overrides):
    """The arguments the owner's command gives, with one of them replaced.

    The values are the ones the freeze note fixes; the three the note fixes as
    "the default" are given here as the default itself, because that is what the
    command line gives when the flag is absent.
    """
    arguments = dict(
        model="deepseek/deepseek-flash",
        prompts_dir=run_benchmark.PROMPTS_DIR,
        judge_votes=4,
        verify_drafts=False,
        timeout_seconds=900.0,
        concurrency=2,
        case_deadline_seconds=run_benchmark.pipeline.DEFAULT_CASE_DEADLINE_SECONDS,
        token_budget=None,
    )
    arguments.update(overrides)
    return arguments


# One row per frozen setting: the switch, the keyword that differs from the
# freeze, and the two values the refusal must name.
FROZEN_ARGUMENT_DIFFERENCES = (
    ("--model", {"model": "deepseek/deepseek-chat"}, "deepseek/deepseek-chat", "deepseek/deepseek-flash"),
    ("--judge-votes", {"judge_votes": 1}, "1", "4"),
    ("--verify-drafts", {"verify_drafts": True}, "on", "off"),
    ("--timeout", {"timeout_seconds": 300.0}, "300.0", "900.0"),
    ("--concurrency", {"concurrency": 3}, "3", "2"),
    ("--prompts-dir", {"prompts_dir": PROJECT_ROOT / "prompts"}, str(PROJECT_ROOT / "prompts"), "the default"),
    ("--case-deadline", {"case_deadline_seconds": 1200.0}, "1200.0", "the default"),
    ("--token-budget", {"token_budget": 100000}, "100000", "the default"),
)


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------
class SealedV1RegistryTests(unittest.TestCase):
    """The third sealed set is registered, and it is not a development set."""

    def test_it_is_registered_by_name_and_marked_sealed(self):
        self.assertIn("sealed-v1", sets.BY_NAME)
        self.assertIs(SEALED_V1, sets.BY_NAME["sealed-v1"])
        self.assertTrue(SEALED_V1.sealed, "the third sealed set is not marked sealed")
        self.assertEqual("sealed-v1", SEALED_V1.runs_subdir)

    def test_it_is_not_one_of_the_development_sets(self):
        """``--set all`` and the combined figure both read ``DEVELOPMENT_SETS``."""
        self.assertEqual(["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn(SEALED_V1, sets.DEVELOPMENT_SETS)
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1"),
            tuple(item.name for item in sets.SEALED_SETS),
        )
        self.assertIn(SEALED_V1, sets.SEALED_SETS)
        self.assertNotIn("sealed-v1", [item.name for item in sets.ALL_SETS])
        self.assertNotIn("sealed-v1", [item.name for item in sets.RERUN_SETS])
        self.assertFalse(
            any(item.sealed for item in sets.DEVELOPMENT_SETS),
            "a development set is marked sealed",
        )
        self.assertEqual(
            {
                item.name
                for item in (
                    sets.DEVELOPMENT_SETS
                    + sets.SEALED_SETS
                    + sets.RERUN_SETS
                    + sets.NAMED_SETS
                )
            },
            set(sets.BY_NAME),
            "the name table is not exactly the registered sets",
        )

    def test_its_registration_fixes_policy_version_6(self):
        self.assertEqual(6, SEALED_V1.policy_version)
        self.assertIsNone(SEALED_V1.policy_base)
        self.assertEqual(6, sets.resolved_policy_version(SEALED_V1, None))
        # A set that fixes its version keeps its own directory; the version does
        # not move its run one level down.
        self.assertFalse(sets.version_moves_the_run(SEALED_V1, None))

    def test_its_cases_are_the_24_it_was_imported_with(self):
        self.assertEqual(ALL_SEALED_V1_CASES, tuple(SEALED_V1.cases))

    def test_it_has_its_own_case_root_key_and_loader(self):
        self.assertEqual(SEALED_V1_CASES_DIR, SEALED_V1.case_root)
        self.assertEqual(SEALED_V1_KEY_PATH, SEALED_V1.key_path)
        for other in (sets.CORPUS, sets.SEALED_SET, sets.WILD_V2):
            with self.subTest(other=other.name):
                self.assertNotEqual(other.case_root, SEALED_V1.case_root)
                self.assertNotEqual(other.key_path, SEALED_V1.key_path)

    def test_its_runs_go_to_its_own_root(self):
        runs = Path("/tmp/sealed-v1-registry-runs")
        self.assertEqual(runs / "sealed-v1", SEALED_V1.runs_dir(runs))
        self.assertEqual(
            runs / "sealed-v1" / run_benchmark.model_slug(MODEL),
            SEALED_V1.run_dir(MODEL, runs),
        )

    def test_its_summary_names_it_the_third_sealed_set_run_once(self):
        summary = SEALED_V1.summary
        self.assertIn("third sealed set", summary)
        self.assertIn("sealed-v1", summary)
        self.assertIn("freeze-2026-10-09", summary)

    def test_its_cases_are_not_in_the_corpus_manifest(self):
        with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
            manifest = {entry["case_no"] for entry in json.load(handle)}
        self.assertEqual(set(), manifest & set(ALL_SEALED_V1_CASES))

    def test_its_run_directory_is_a_headline_directory(self):
        runs = Path("/tmp/sealed-v1-registry-runs")
        headline = [path.resolve() for path in run_benchmark.headline_run_directories(runs, MODEL)]
        self.assertIn((runs / "sealed-v1" / run_benchmark.model_slug(MODEL)).resolve(), headline)
        self.assertEqual(5, len(headline), "the headline directories are not five")

    def test_its_root_is_closed_and_no_permit_opens_it(self):
        """The set has been run, so nothing is created under its root again."""
        self.assertTrue(sets.sealed_root_is_closed(SEALED_V1))
        self.assertEqual((), run_benchmark.UNRUN_SEALED_RUNS_SUBDIRS)
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1"),
            run_benchmark.MADE_SEALED_RUNS_SUBDIRS,
        )
        self.assertIn(run_benchmark.SEALED_V1_SET_RUNS_SUBDIR, run_benchmark.SET_RUNS_SUBDIRS)
        # And the guard itself: the plain sealed run's own directory is refused,
        # permit or no permit -- the permit machinery is written for a root whose
        # run has not been made, and this one's has.
        runs = Path("/tmp/sealed-v1-closed-runs")
        destination = runs / "sealed-v1" / run_benchmark.model_slug(MODEL)
        for permit in (None, destination):
            with self.subTest(permit=permit is not None):
                with self.assertRaises(run_benchmark.BenchmarkError) as caught:
                    run_benchmark.assert_not_under_the_held_out_root(
                        destination, runs, permit=permit
                    )
                self.assertIn("nothing is created under it again", str(caught.exception))


# --------------------------------------------------------------------------
# The bundle digest table
# --------------------------------------------------------------------------
class SealedV1BundleDigestTests(unittest.TestCase):
    """Every file the archive shipped is accounted for, by digest."""

    def test_the_table_is_the_whole_archive(self):
        self.assertEqual(36, len(BUNDLE_FILES), "the archive did not ship 36 files")
        self.assertEqual(
            34, len(BUNDLE_FILES) - len(KEPT_OUTSIDE_THE_REPOSITORY),
            "the imported file count is not 34",
        )

    def test_every_imported_file_hashes_to_the_digest_the_table_states(self):
        for relative, digest in sorted(BUNDLE_FILES):
            if relative in KEPT_OUTSIDE_THE_REPOSITORY:
                continue
            path = PROJECT_ROOT / relative
            with self.subTest(path=relative):
                self.assertTrue(path.is_file(), "{0} was not imported".format(relative))
                self.assertEqual(
                    digest,
                    run_benchmark.file_sha256(path),
                    "{0} does not hash to the digest the bundle table states".format(relative),
                )

    def test_the_two_kept_outside_are_absent_and_marked(self):
        """No Chinese may enter the repository, so neither file is imported.

        The two are named by their **archive** path, and one of those names --
        ``README.md`` -- is also the repository's own root file's name. The
        absence is therefore asserted at the destination the archive's file would
        have gone to, and not at the repository root, where a different
        ``README.md`` belongs.
        """
        for relative in KEPT_OUTSIDE_THE_REPOSITORY:
            with self.subTest(path=relative):
                self.assertFalse(
                    (SEALED_V1_EXTERNAL_DIR / relative).exists(),
                    "{0} was imported into the set's own bundle".format(relative),
                )
        self.assertIn(KEPT_OUTSIDE_MARKER, IMPORT_NOTE.read_text(encoding="utf-8"))

    def test_the_note_lists_every_file_the_table_does(self):
        text = IMPORT_NOTE.read_text(encoding="utf-8")
        for relative, digest in BUNDLE_FILES:
            with self.subTest(path=relative):
                self.assertIn(relative, text)
                self.assertIn(digest, text)

    def test_the_two_re_serialised_files_are_the_only_ones_that_moved(self):
        for relative, archive_digest in RESERIALISED_ON_IMPORT.items():
            with self.subTest(path=relative):
                self.assertNotEqual(
                    archive_digest,
                    run_benchmark.file_sha256(PROJECT_ROOT / relative),
                    "{0} is byte-identical to the archive, so it was not re-serialised".format(
                        relative
                    ),
                )

    def test_the_manifests_own_case_digests_reproduce(self):
        """The archive's manifest states a digest for each case file."""
        with (SEALED_V1_EXTERNAL_DIR / "MANIFEST.json").open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        stated = manifest["case_file_sha256"]
        self.assertEqual(24, len(stated), "the manifest does not state 24 case digests")
        for name, digest in sorted(stated.items()):
            with self.subTest(case=name):
                self.assertEqual(
                    digest,
                    run_benchmark.file_sha256(SEALED_V1_CASES_DIR / name),
                    "{0} does not match the digest the archive's manifest states".format(name),
                )

    def test_the_manifest_records_the_set_as_the_third_sealed_one(self):
        with (SEALED_V1_EXTERNAL_DIR / "MANIFEST.json").open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual("tribunal-sealed-v1", manifest["sealed_set"])
        self.assertEqual(24, manifest["case_count"])
        self.assertEqual(list(ALL_SEALED_V1_CASES), manifest["case_numbers"])
        # "run once, k=3": the set does not define k, so the run is made once with
        # the frozen configuration -- the configuration of the two earlier sealed
        # runs -- and not k times.
        self.assertEqual(1, manifest["protocol"]["runs_allowed"])
        self.assertEqual(3, manifest["protocol"]["k"])


# --------------------------------------------------------------------------
# The sealed run is the owner's
# --------------------------------------------------------------------------
class SealedV1SealedRunLockTests(unittest.TestCase):
    """The sealed run is the owner's, and only the owner's.

    The set has been run, so the gate's message is the one that says the root is
    closed rather than the one that explains the opt-in: there is nothing left to
    opt in to. No test here can build a client -- ``_run_cli`` patches the class
    to raise -- and none of them writes: the runs root is a temporary directory,
    and both modules are made to believe it is the repository's own.
    """

    def _invocation(self, tmp, *extra):
        runs = Path(tmp) / "runs"
        with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
            run_benchmark, "RUNS_DIR", runs
        ):
            code, out, err = _run_cli(
                ["--set", "sealed-v1", "--concurrency", "2", "--timeout", "900"]
                + list(extra)
            )
        return runs, code, out, err

    def test_without_the_opt_in_the_invocation_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ):
                os.environ.pop(sets.SEALED_RUN_ENV_VAR, None)
                runs, code, _out, err = self._invocation(tmp)

            self.assertEqual(1, code, "the sealed run was not locked")
            # The run has been made, so the refusal is the closure's: there is
            # nothing left to opt in to, and the message says so rather than
            # explaining an opt-in that could no longer open anything.
            self.assertIn("its single run has been made", err)
            self.assertIn("root is closed", err)
            self.assertIn(sets.SEALED_RUN_ENV_VAR, err)
            self.assertIn("sealed-v1", err)
            self.assertFalse(runs.exists(), "the refused invocation created the runs root")

    def test_the_opt_in_set_to_any_other_value_is_refused(self):
        for value in ("wild", "wild-v2", "sealed-v2", "", "1", "SEALED-V1"):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    with mock.patch.dict(os.environ, {sets.SEALED_RUN_ENV_VAR: value}):
                        runs, code, _out, err = self._invocation(tmp)
                    self.assertEqual(1, code, "{0!r} unlocked the sealed run".format(value))
                    self.assertIn(sets.SEALED_RUN_ENV_VAR, err)
                    self.assertFalse(runs.exists())


# --------------------------------------------------------------------------
# The switches that would replace or re-take the single run
# --------------------------------------------------------------------------
class SealedV1SwitchGuardTests(unittest.TestCase):
    """``--force`` is refused for this set, and for this set only."""

    def test_force_is_refused_and_leaves_the_result_it_would_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_dir = runs / "sealed-v1" / run_benchmark.model_slug(MODEL)
            run_dir.mkdir(parents=True)
            sentinel = run_dir / "case-{0:05d}.json".format(SENTINEL_CASE)
            sentinel.write_text(
                json.dumps({"case_no": SENTINEL_CASE, "sentinel": "the sealed result"}, indent=2),
                encoding="utf-8",
            )
            before = sentinel.read_bytes()

            code, _, err = _run_cli_over(runs, ["--set", "sealed-v1", "--force"])

            self.assertEqual(1, code, "a sealed run accepted --force")
            self.assertIn("the sealed set {0} is run once".format(SEALED_V1.name), err)
            self.assertIn("--force", err)
            self.assertEqual(before, sentinel.read_bytes(), "the sealed result was rewritten")
            self.assertEqual(
                {sentinel.name: before}, _state(run_dir), "the run directory gained a file"
            )

    def test_the_refusal_is_for_this_set_and_not_for_the_others(self):
        for development_set in sets.DEVELOPMENT_SETS + sets.RERUN_SETS:
            with self.subTest(development_set=development_set.name):
                self.assertIsNone(sets.assert_not_sealed(development_set, "--force"))

    def test_the_frozen_arguments_are_accepted_though_the_root_is_closed(self):
        """A guard that refused everything would pass the test above.

        The argument check and the destination check are separate rules. This
        pins the first: the owner's own invocation differs in no argument, so
        ``run_argument_differences`` is empty. The second now refuses that same
        invocation, because the set's root is closed --
        ``test_its_root_is_closed_and_no_permit_opens_it`` is where that is
        asserted, not here.
        """
        self.assertEqual([], sets.run_argument_differences(SEALED_V1, **_frozen_arguments()))


# --------------------------------------------------------------------------
# The run arguments, frozen in the registration
# --------------------------------------------------------------------------
class SealedV1RunArgumentsTests(unittest.TestCase):
    """``--set sealed-v1`` runs at the arguments its registration fixes, or not at all."""

    def test_the_registered_model_is_the_one_the_freeze_note_states(self):
        """The registration and the note are two records of one decision."""
        text = (PROJECT_ROOT / "docs" / "notes" / "2026-10-09-the-third-freeze.md").read_text(
            encoding="utf-8"
        )
        stated = None
        for line in text.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) == 2 and cells[0] == "model":
                # The value is a code span followed by a gloss: read what is
                # between the backticks, so the closing backtick is not read as
                # part of the model.
                span = cells[1].split("`")
                if len(span) >= 3:
                    stated = span[1].strip()
                break
        self.assertIsNotNone(stated, "the freeze note's configuration table states no model")
        self.assertEqual(stated, SEALED_V1.run_arguments.model)

    def test_the_registration_records_the_freezes_eight_settings(self):
        frozen = SEALED_V1.run_arguments
        self.assertIsNotNone(frozen, "sealed-v1 fixes no run arguments")
        self.assertEqual("deepseek/deepseek-flash", frozen.model)
        self.assertEqual(4, frozen.judge_votes)
        self.assertFalse(frozen.verify_drafts)
        self.assertEqual(900.0, frozen.timeout_seconds)
        self.assertEqual(2, frozen.concurrency)
        # "The default" is recorded as the default rather than as today's number.
        self.assertIsNone(frozen.prompts_dir)
        self.assertIsNone(frozen.case_deadline_seconds)
        self.assertIsNone(frozen.token_budget)

    def test_the_judge_vote_default_agrees_with_the_freezes_four(self):
        self.assertEqual(4, SEALED_V1.run_arguments.judge_votes)
        self.assertEqual(
            4,
            run_benchmark.pipeline.DEFAULT_JUDGE_VOTES,
            "the judge vote default no longer agrees with the freeze note's 4, so "
            "the owner's command would now be refused",
        )

    def test_the_invocation_the_owner_will_run_differs_in_nothing(self):
        self.assertEqual(
            [],
            sets.run_argument_differences(SEALED_V1, **_frozen_arguments()),
            "the frozen invocation is refused",
        )

    def test_each_differing_argument_is_named_with_its_registered_value(self):
        for switch, overrides, asked_text, registered_text in FROZEN_ARGUMENT_DIFFERENCES:
            with self.subTest(switch=switch):
                differences = sets.run_argument_differences(
                    SEALED_V1, **_frozen_arguments(**overrides)
                )
                self.assertEqual(
                    1,
                    len(differences),
                    "{0} did not give exactly one difference: {1}".format(switch, differences),
                )
                self.assertIn(switch, differences[0])
                self.assertIn(asked_text, differences[0])
                self.assertIn(
                    "sealed-v1 is registered at {0}".format(registered_text),
                    differences[0],
                )

    def test_the_policy_version_flag_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                code, _out, err = _run_cli(
                    ["--set", "sealed-v1", "--policy-version", "3"]
                )
            self.assertEqual(1, code, "--policy-version was accepted for the sealed set")
            self.assertIn("fixes policy version 6", err)
            self.assertFalse(runs.exists())


# --------------------------------------------------------------------------
# Structure: the cases, the briefs and the key
# --------------------------------------------------------------------------
class SealedV1StructureTests(unittest.TestCase):
    """Counts, keys and briefs. Never a value."""

    def test_all_24_cases_load_through_the_sets_own_loader(self):
        loaded = [SEALED_V1.load_case(case_no) for case_no in ALL_SEALED_V1_CASES]
        self.assertEqual(24, len(loaded))
        self.assertEqual(
            list(ALL_SEALED_V1_CASES), [case["case_no"] for case in loaded]
        )

    def test_all_24_briefs_build_at_version_6(self):
        for case_no in ALL_SEALED_V1_CASES:
            with self.subTest(case_no=case_no):
                built = brief.build_brief_for_case(
                    SEALED_V1.load_case(case_no), policy_version=6
                )
                self.assertIn("policies", built)

    def test_the_index_names_24_cases_and_the_key_agrees_with_it(self):
        with (SEALED_V1_CASES_DIR / "index.json").open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
        self.assertEqual(list(ALL_SEALED_V1_CASES), [entry["case_no"] for entry in entries])
        key = grade.load_answer_key(SEALED_V1_KEY_PATH)
        self.assertEqual(set(ALL_SEALED_V1_CASES), set(key))

    def test_every_record_of_the_key_carries_all_four_graded_fields(self):
        with SEALED_V1_KEY_PATH.open("r", encoding="utf-8") as handle:
            records = json.load(handle)
        self.assertEqual(24, len(records))
        for record in records:
            with self.subTest(case_no=record["case_no"]):
                truth = record["ground_truth"]
                for field in (
                    "expected_ruling",
                    "expected_amount_sgd",
                    "expected_driver_compensation_sgd",
                    "expected_referrals",
                ):
                    self.assertIn(field, truth)

    def test_no_answer_field_appears_in_any_case_file(self):
        answer_fields = (
            "expected_ruling",
            "expected_amount_sgd",
            "expected_driver_compensation_sgd",
            "expected_referrals",
            "ground_truth",
        )
        for path in sorted(SEALED_V1_CASES_DIR.glob("case-*.json")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(case=path.name):
                for field in answer_fields:
                    self.assertNotIn(field, text)

    def test_the_key_file_is_the_only_thing_in_the_sets_answer_directory(self):
        directory = SEALED_V1_KEY_PATH.parent
        self.assertEqual(
            ["ground_truth.json"],
            sorted(path.name for path in directory.iterdir() if path.is_file()),
        )

    def test_no_case_carries_a_platform_policy_of_its_own(self):
        """The cases were authored under version-1 parameters, so a version-6
        brief derives the ``AUTHORED-V1`` block for them."""
        derived = 0
        for case_no in ALL_SEALED_V1_CASES:
            case = SEALED_V1.load_case(case_no)
            for artifact in case["evidence"]:
                if artifact["evidence_type"] != "TRIP_RECORD":
                    continue
                self.assertNotIn("platform_policy", artifact.get("payload") or {})
        # A no-show case gets the derived block; a route-deviation case has none.
        no_show = brief.build_brief_for_case(SEALED_V1.load_case(401), policy_version=6)
        for artifact in no_show["case"]["evidence"]:
            if artifact["evidence_type"] == "TRIP_RECORD":
                block = (artifact.get("payload") or {}).get("platform_policy_in_force")
                if isinstance(block, dict):
                    derived += 1
                    self.assertEqual(brief.AUTHORED_V1_SOURCE, block["source"])
        self.assertEqual(1, derived, "the no-show brief did not derive the AUTHORED-V1 block")

    def test_the_loader_the_set_is_run_with_is_the_external_one(self):
        """The cases are absent from the corpus manifest on purpose."""
        case = loader.load_external_set_case(SEALED_V1_CASES_DIR, SENTINEL_CASE)
        self.assertEqual(SENTINEL_CASE, case["case_no"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
