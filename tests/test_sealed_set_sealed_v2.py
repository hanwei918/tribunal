"""The fourth sealed set: registering it, the guards around its single run, and the
bundle it was imported from.

``sealed-v2`` is 12 cases under ``data/external/sealed-v2/``, keyed by
``eval/answers/sealed-v2/ground_truth.json``. Like the three sealed sets before
it, it is **not** a development set: it was made with GPT-6 by the policy owner
from a written brief, the version-6 policy text and the public contract, with no
repository code, prompts or run results, and nobody on the development side has
seen its answers; it was imported on 2026-10-11, it was run exactly once, on
2026-10-11, from the commit ``19c7e5a``, whose ``tribunal/``, ``prompts/`` and
``policy/`` trees equal those at
``freeze-2026-10-11``, and that single run is the submission's fourth sealed
generalisation figure. Its registration fixes policy
version 6, so it was run at version 6 with no flag and ``--policy-version`` is
refused for it. Its single run **has** been made, so its root is closed outright:
nothing is created under it again, the plain sealed run included.

What is asserted here:

* **It is registered, and it is apart.** Its own cases, its own key, its own
  loader and its own runs root; it is absent from ``DEVELOPMENT_SETS``, so
  ``--set all`` does not run it and the combined figure does not include it.
* **The bundle digest table.** Every file the two archives shipped is listed with
  its sha256, and the files imported into the repository are held to it. No file
  of either archive is opened by this module beyond hashing: the answers rule
  forbids it, and a digest is all this module asks for.
* **Its switches are refused.** ``--force`` and each of the frozen arguments are
  refused for it, and the frozen invocation's arguments are accepted through the
  refusal function rather than by running it.
* **Its root is closed.** Its single run has been made, so no permit opens it and
  every destination under it -- the plain sealed run's own directory included --
  is refused.
* **The sealed run is the owner's.** Without ``TRIBUNAL_SEALED_RUN=sealed-v2``
  the invocation is refused before a client is built and writes nothing.
* **Its structure holds.** All 12 cases load through the set's own loader and
  their briefs build at version 6; the key loads through
  ``eval.grade.load_answer_key`` and holds 12 records each carrying all four
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

from eval import development_sets as sets, grade, run_benchmark, sealed_roots  # noqa: E402
from tribunal import brief, loader  # noqa: E402

MODEL = "deepseek/deepseek-flash"
SEALED_V2 = sets.SEALED_V2

# The set's own directories, named here so a test can say which one it means.
SEALED_V2_CASES_DIR = PROJECT_ROOT / "data" / "external" / "sealed-v2"
SEALED_V2_KEY_PATH = PROJECT_ROOT / "eval" / "answers" / "sealed-v2" / "ground_truth.json"
SEALED_V2_ANSWERS_DIR = PROJECT_ROOT / "eval" / "answers" / "sealed-v2"
SEALED_V2_EXTERNAL_DIR = PROJECT_ROOT / "eval" / "external" / "sealed-v2"

# 801-806 and 851-856: two six-wide ranges, so the count and the ranges are
# written down rather than assumed from the files that happen to be there.
ALL_SEALED_V2_CASES = tuple(range(801, 807)) + tuple(range(851, 857))

# The first case of the set, used as the case a scratch fixture "has a result"
# for. It is a number, never a value.
SENTINEL_CASE = 801

# The import note, whose digest table is the record of every file the two
# archives shipped. Reading it is reading a document this repository wrote, not
# the set.
IMPORT_NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-11-sealed-v2-imported.md"

# Every file the two archives shipped, as `(repository path, sha256)`. Nothing is
# kept outside the repository this time: archive A's `README.md` and `CANARY.txt`
# are English and answer-free, and every file of archive B is answer-bearing and
# sits under the physically isolated answers root. The digests are the archives'
# own, and every imported file is byte-identical to its archive entry -- the key
# included, because it arrived in the array form `eval.grade.load_answer_key`
# reads and was extracted as it stands.
BUNDLE_FILES = (
    ("data/external/sealed-v2/case-00801.json", "92b15dbf2f67d08b48e07740e44f19836b12692a0340ebcae4660c72c4fe83c7"),
    ("data/external/sealed-v2/case-00802.json", "acc474352c4fc45844d745c4efcb91053e52aff828e09018ee30e36e5bd04038"),
    ("data/external/sealed-v2/case-00803.json", "66e5d51b11102f672e92a65576a9e5f5e62a8cb6f140fcdef89f80223ad44aa0"),
    ("data/external/sealed-v2/case-00804.json", "f7d9f1c97bff814a3d3db7de96d4f2966279d1bd664b3c1b04a8eba771f9ad1f"),
    ("data/external/sealed-v2/case-00805.json", "9f104d7efad66bafac56d1250e4d84699c4ce8a4439ea65583a5d6878803355f"),
    ("data/external/sealed-v2/case-00806.json", "0c7f685a92a65bc5268909ed39e90b71033421b635f876342831de88f3c814a5"),
    ("data/external/sealed-v2/case-00851.json", "c7bea25126e5e8bd21b8aaf9486b82480209717dfa043dbbd48337916205f7a3"),
    ("data/external/sealed-v2/case-00852.json", "5496839a5a2daf222239b86acca9a471ac37450479d7ec4dc7336f401dba44a7"),
    ("data/external/sealed-v2/case-00853.json", "37cfbcada425bec584ae563ad4d55607f8019cb4ec4792d30fecfe6fabbfcb0a"),
    ("data/external/sealed-v2/case-00854.json", "644203c02f2b25a45a206fd5b4710e69edf2f7714e818cbece0d23f31cf2fb99"),
    ("data/external/sealed-v2/case-00855.json", "b89410fc4da5ed3b81bde3c7b01e23685d829109a856bad0f7a06b31ca9541cf"),
    ("data/external/sealed-v2/case-00856.json", "3d90ebb95bdcec7cbc1a8493885fbab249b4c99bf3158b0c8808301fdcc03b02"),
    ("data/external/sealed-v2/index.json", "b1c218091eebb654d606cf36f4718967881cc068b86aa29ba98f65f2bc9d591e"),
    ("eval/answers/sealed-v2/MANIFEST.json", "0fa3dfb62f0d8fc0200ed1223127d896eac97b1c5b48b10ad9c99372ed1764ea"),
    ("eval/answers/sealed-v2/REVIEW_GUIDE.md", "f8a87710086dda04020e74a4c6d31b14f0a754e8ba76441ed5df9f7342195c82"),
    ("eval/answers/sealed-v2/additional_audit_output.txt", "bc3eed2bf7d6bf2a796b8fd4a2b0b2f5099f7d7b1c25e10e8c11e8b2b22baa97"),
    ("eval/answers/sealed-v2/check_set.py", "c61ed3571e318c2edf7702e16c3ada2fff352822396e8b30af3b02bcf7776463"),
    ("eval/answers/sealed-v2/check_set_output.txt", "77177ad44f2a727f9f3d4b41ffecbeca9117f8a2880796171d5bf319ae603871"),
    ("eval/answers/sealed-v2/ground_truth.json", "d3a09c08f06c8eb328e251e618cba7b035fdb54c7614b041781fd6d564fe3e6f"),
    ("eval/answers/sealed-v2/review_checklist.json", "dd1b277b5d82d3e5caa57bbb832e5dcb0d00440898c3c2ef895256cb8a311ab0"),
    ("eval/external/sealed-v2/CANARY.txt", "4d6805ec7f0bcdbef11ed03b19ea8ae170dc78247a43ebd3689458220d409c2b"),
    ("eval/external/sealed-v2/README.md", "a4306e183563b3bfe309216bd726cc5fea942aa9014f75a859136e6678ccadfe"),
)

# The two archives this set was imported from, as `(name, sha256)`, checked
# against `SHA256SUMS` before anything was copied out.
ARCHIVES = (
    ("tribunal-sealed-v2-A-cases.zip", "ad89652fbba601c02aa6d16272d44a3dfaf2fb6ec430d8b9b720dac81ce88bbd"),
    ("tribunal-sealed-v2-B-answers.zip", "988e21e0e6f9f1f080cedfd3c2893d02f21dece180f0bf1f6b7ca73d0e1a2c00"),
)


def _run_cli(arguments):
    """``sets.main``, with both streams captured and no client buildable.

    Every invocation of the command line for ``sealed-v2`` is refused before a
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

    The values are the ones the registration fixes; the three the registration
    fixes as "the default" are given here as the default itself, because that is
    what the command line gives when the flag is absent.
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
# registration, and the two values the refusal must name.
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
class SealedV2RegistryTests(unittest.TestCase):
    """The fourth sealed set is registered, and it is not a development set."""

    def test_it_is_registered_by_name_and_marked_sealed(self):
        self.assertIn("sealed-v2", sets.BY_NAME)
        self.assertIs(SEALED_V2, sets.BY_NAME["sealed-v2"])
        self.assertTrue(SEALED_V2.sealed, "the fourth sealed set is not marked sealed")
        self.assertEqual("sealed-v2", SEALED_V2.runs_subdir)

    def test_it_is_not_one_of_the_development_sets(self):
        """``--set all`` and the combined figure both read ``DEVELOPMENT_SETS``."""
        self.assertEqual(["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn(SEALED_V2, sets.DEVELOPMENT_SETS)
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1", "sealed-v2", "sealed-v3"),
            tuple(item.name for item in sets.SEALED_SETS),
        )
        self.assertIn(SEALED_V2, sets.SEALED_SETS)
        self.assertNotIn("sealed-v2", [item.name for item in sets.ALL_SETS])
        self.assertNotIn("sealed-v2", [item.name for item in sets.RERUN_SETS])
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
        self.assertEqual(6, SEALED_V2.policy_version)
        self.assertIsNone(SEALED_V2.policy_base)
        self.assertEqual(6, sets.resolved_policy_version(SEALED_V2, None))
        # A set that fixes its version keeps its own directory; the version does
        # not move its run one level down.
        self.assertFalse(sets.version_moves_the_run(SEALED_V2, None))

    def test_its_cases_are_the_12_it_was_imported_with(self):
        self.assertEqual(ALL_SEALED_V2_CASES, tuple(SEALED_V2.cases))

    def test_it_has_its_own_case_root_key_and_loader(self):
        self.assertEqual(SEALED_V2_CASES_DIR, SEALED_V2.case_root)
        self.assertEqual(SEALED_V2_KEY_PATH, SEALED_V2.key_path)
        for other in (sets.CORPUS, sets.SEALED_SET, sets.WILD_V2, sets.SEALED_V1):
            with self.subTest(other=other.name):
                self.assertNotEqual(other.case_root, SEALED_V2.case_root)
                self.assertNotEqual(other.key_path, SEALED_V2.key_path)

    def test_its_runs_go_to_its_own_root(self):
        runs = Path("/tmp/sealed-v2-registry-runs")
        self.assertEqual(runs / "sealed-v2", SEALED_V2.runs_dir(runs))
        self.assertEqual(
            runs / "sealed-v2" / run_benchmark.model_slug(MODEL),
            SEALED_V2.run_dir(MODEL, runs),
        )

    def test_its_summary_names_it_the_fourth_sealed_set_run_once(self):
        summary = SEALED_V2.summary
        self.assertIn("fourth sealed set", summary)
        self.assertIn("sealed-v2", summary)
        self.assertIn("freeze-2026-10-11", summary)

    def test_its_cases_are_not_in_the_corpus_manifest(self):
        with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
            manifest = {entry["case_no"] for entry in json.load(handle)}
        self.assertEqual(set(), manifest & set(ALL_SEALED_V2_CASES))

    def test_its_run_directory_is_a_headline_directory(self):
        runs = Path("/tmp/sealed-v2-registry-runs")
        headline = [path.resolve() for path in run_benchmark.headline_run_directories(runs, MODEL)]
        self.assertIn((runs / "sealed-v2" / run_benchmark.model_slug(MODEL)).resolve(), headline)
        self.assertEqual(7, len(headline), "the headline directories are not seven")

    def test_its_root_is_closed_and_no_permit_opens_it(self):
        """The set has been run, so nothing is created under its root again."""
        self.assertTrue(sets.sealed_root_is_closed(SEALED_V2))
        # The un-run list names the fifth sealed set, imported on 2026-10-13 and
        # not yet run; this set's own run has been made, so no permit opens its
        # root. Both lists are pinned, so neither can pass by being empty.
        self.assertEqual(
            ("sealed-v3",), run_benchmark.UNRUN_SEALED_RUNS_SUBDIRS
        )
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1", "sealed-v2"),
            run_benchmark.MADE_SEALED_RUNS_SUBDIRS,
        )
        self.assertIn(run_benchmark.SEALED_V2_SET_RUNS_SUBDIR, run_benchmark.SET_RUNS_SUBDIRS)
        # And the guard itself: the plain sealed run's own directory is refused,
        # permit or no permit -- the permit machinery is written for a root whose
        # run has not been made, and this one's has.
        runs = Path("/tmp/sealed-v2-closed-runs")
        destination = runs / "sealed-v2" / run_benchmark.model_slug(MODEL)
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
class SealedV2BundleDigestTests(unittest.TestCase):
    """Every file the two archives shipped is accounted for, by digest."""

    def test_the_table_is_the_whole_bundle(self):
        self.assertEqual(22, len(BUNDLE_FILES), "the two archives did not ship 22 files")
        self.assertEqual(
            13,
            len([name for name, _digest in BUNDLE_FILES if name.startswith("data/external/")]),
            "the set's own directory is not 12 cases and an index",
        )
        self.assertEqual(
            7,
            len([name for name, _digest in BUNDLE_FILES if "/answers/" in name]),
            "the answers root is not the key and the six answer-bearing companions",
        )
        self.assertEqual(
            2,
            len([name for name, _digest in BUNDLE_FILES if name.startswith("eval/external/")]),
            "the set's own bundle is not the archive's README and CANARY",
        )

    def test_every_imported_file_hashes_to_the_digest_the_table_states(self):
        for relative, digest in sorted(BUNDLE_FILES):
            path = PROJECT_ROOT / relative
            with self.subTest(path=relative):
                self.assertTrue(path.is_file(), "{0} was not imported".format(relative))
                self.assertEqual(
                    digest,
                    run_benchmark.file_sha256(path),
                    "{0} does not hash to the digest the bundle table states".format(relative),
                )

    def test_the_note_lists_every_file_the_table_does(self):
        text = IMPORT_NOTE.read_text(encoding="utf-8")
        for relative, digest in BUNDLE_FILES:
            with self.subTest(path=relative):
                self.assertIn(relative, text)
                self.assertIn(digest, text)
        for name, digest in ARCHIVES:
            with self.subTest(archive=name):
                self.assertIn(name, text)
                self.assertIn(digest, text)

    def test_every_answers_file_sits_under_the_physically_isolated_root(self):
        """Nothing answer-bearing is left anywhere else.

        The answers root holds the key and the six files archive B shipped
        beside it; the set's own case directory holds none of them.
        """
        answers = sorted(
            path.name for path in SEALED_V2_ANSWERS_DIR.iterdir() if path.is_file()
        )
        self.assertEqual(
            [
                "MANIFEST.json",
                "REVIEW_GUIDE.md",
                "additional_audit_output.txt",
                "check_set.py",
                "check_set_output.txt",
                "ground_truth.json",
                "review_checklist.json",
            ],
            answers,
        )
        cases = sorted(
            path.name for path in SEALED_V2_CASES_DIR.iterdir() if path.is_file()
        )
        self.assertEqual(
            sorted(["index.json"] + ["case-{0:05d}.json".format(n) for n in ALL_SEALED_V2_CASES]),
            cases,
        )

    def test_the_archives_own_index_digests_reproduce(self):
        """The archive's index states a digest for each case file."""
        with (SEALED_V2_CASES_DIR / "index.json").open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
        stated = {entry["file"]: entry["sha256"] for entry in entries}
        self.assertEqual(12, len(stated), "the index does not state 12 case digests")
        for name, digest in sorted(stated.items()):
            with self.subTest(case=name):
                self.assertEqual(
                    digest,
                    run_benchmark.file_sha256(SEALED_V2_CASES_DIR / name),
                    "{0} does not match the digest the set's own index states".format(name),
                )


# --------------------------------------------------------------------------
# The sealed run is the owner's
# --------------------------------------------------------------------------
class SealedV2SealedRunLockTests(unittest.TestCase):
    """The sealed run is the owner's, and only the owner's.

    The set has **not** been run, so the gate's message is the one that explains
    the opt-in. No test here can build a client -- ``_run_cli`` patches the class
    to raise -- and none of them writes: the runs root is a temporary directory,
    and both modules are made to believe it is the repository's own.
    """

    def _invocation(self, tmp, *extra):
        runs = Path(tmp) / "runs"
        with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
            run_benchmark, "RUNS_DIR", runs
        ):
            code, out, err = _run_cli(
                ["--set", "sealed-v2", "--concurrency", "2", "--timeout", "900"]
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
            self.assertIn("sealed-v2", err)
            self.assertFalse(runs.exists(), "the refused invocation created the runs root")

    def test_the_opt_in_set_to_any_other_value_is_refused(self):
        for value in ("wild", "wild-v2", "sealed-v1", "", "1", "SEALED-V2"):
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
class SealedV2SwitchGuardTests(unittest.TestCase):
    """``--force`` is refused for this set, and for this set only."""

    def test_force_is_refused_and_leaves_the_result_it_would_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_dir = runs / "sealed-v2" / run_benchmark.model_slug(MODEL)
            run_dir.mkdir(parents=True)
            sentinel = run_dir / "case-{0:05d}.json".format(SENTINEL_CASE)
            sentinel.write_text(
                json.dumps({"case_no": SENTINEL_CASE, "sentinel": "the sealed result"}, indent=2),
                encoding="utf-8",
            )
            before = sentinel.read_bytes()

            code, _, err = _run_cli_over(runs, ["--set", "sealed-v2", "--force"])

            self.assertEqual(1, code, "a sealed run accepted --force")
            self.assertIn("the sealed set {0} is run once".format(SEALED_V2.name), err)
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
        self.assertEqual([], sets.run_argument_differences(SEALED_V2, **_frozen_arguments()))


# --------------------------------------------------------------------------
# The run arguments, frozen in the registration
# --------------------------------------------------------------------------
class SealedV2RunArgumentsTests(unittest.TestCase):
    """``--set sealed-v2`` runs at the arguments its registration fixes, or not at all."""

    def test_the_registered_model_is_the_one_the_import_note_states(self):
        """The registration and the note are two records of one decision."""
        text = IMPORT_NOTE.read_text(encoding="utf-8")
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
        self.assertIsNotNone(stated, "the import note's configuration table states no model")
        self.assertEqual(stated, SEALED_V2.run_arguments.model)

    def test_the_registration_records_the_eight_settings(self):
        frozen = SEALED_V2.run_arguments
        self.assertIsNotNone(frozen, "sealed-v2 fixes no run arguments")
        self.assertEqual("deepseek/deepseek-flash", frozen.model)
        self.assertEqual(4, frozen.judge_votes)
        self.assertFalse(frozen.verify_drafts)
        self.assertEqual(900.0, frozen.timeout_seconds)
        self.assertEqual(2, frozen.concurrency)
        # "The default" is recorded as the default rather than as today's number.
        self.assertIsNone(frozen.prompts_dir)
        self.assertIsNone(frozen.case_deadline_seconds)
        self.assertIsNone(frozen.token_budget)

    def test_the_judge_vote_default_agrees_with_the_registrations_four(self):
        self.assertEqual(4, SEALED_V2.run_arguments.judge_votes)
        self.assertEqual(
            4,
            run_benchmark.pipeline.DEFAULT_JUDGE_VOTES,
            "the judge vote default no longer agrees with the registration's 4, so "
            "the owner's command would now be refused",
        )

    def test_the_invocation_the_owner_will_run_differs_in_nothing(self):
        self.assertEqual(
            [],
            sets.run_argument_differences(SEALED_V2, **_frozen_arguments()),
            "the frozen invocation is refused",
        )

    def test_each_differing_argument_is_named_with_its_registered_value(self):
        for switch, overrides, asked_text, registered_text in FROZEN_ARGUMENT_DIFFERENCES:
            with self.subTest(switch=switch):
                differences = sets.run_argument_differences(
                    SEALED_V2, **_frozen_arguments(**overrides)
                )
                self.assertEqual(
                    1,
                    len(differences),
                    "{0} did not give exactly one difference: {1}".format(switch, differences),
                )
                self.assertIn(switch, differences[0])
                self.assertIn(asked_text, differences[0])
                self.assertIn(
                    "sealed-v2 is registered at {0}".format(registered_text),
                    differences[0],
                )

    def test_the_policy_version_flag_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                code, _out, err = _run_cli(
                    ["--set", "sealed-v2", "--policy-version", "3"]
                )
            self.assertEqual(1, code, "--policy-version was accepted for the sealed set")
            self.assertIn("fixes policy version 6", err)
            self.assertFalse(runs.exists())


# --------------------------------------------------------------------------
# Every write path refuses the root
# --------------------------------------------------------------------------
class SealedV2WritePathTests(unittest.TestCase):
    """The sealed-root rule refuses this set's root, and the others still work.

    ``tests/test_sealed_roots_closed.py`` runs one test per call site for every
    sealed root, this one included, by looping the registrations. What is
    asserted here is the same property stated over this set alone, so the set's
    own contribution to the boundary is visible: the shared helper refuses a
    destination under ``runs/sealed-v2/``, and a destination of its own is still
    taken.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.runs = Path(self._tmp.name) / "runs"
        self.runs.mkdir(parents=True)
        # The helper walks the runs root it was given *and* the repository's own,
        # so the scratch root is put in place by moving the constant rather than
        # by passing the flag -- the same patch ``test_sealed_roots_closed.py``
        # makes, and the reason its refusals fire over a temporary tree.
        for module in (run_benchmark, sets):
            patcher = mock.patch.object(module, "RUNS_DIR", self.runs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_shared_helper_refuses_a_destination_under_the_root(self):
        destination = self.runs / "sealed-v2" / "report.md"
        with self.assertRaises(sealed_roots.SealedDestinationError) as caught:
            sealed_roots.refuse_a_sealed_destination(destination, self.runs)
        self.assertIn(str(destination.resolve()), str(caught.exception))

    def test_a_destination_of_its_own_is_still_taken(self):
        """A guard that refused everything would pass the test above."""
        destination = self.runs / "a-command-of-its-own" / "report.md"
        self.assertEqual(
            destination.resolve(),
            sealed_roots.refuse_a_sealed_destination(destination, self.runs).resolve(),
        )

    def test_the_external_runner_refuses_the_root(self):
        runs_dir = self.runs / "sealed-v2"
        destination = runs_dir / run_benchmark.EXTERNAL_RUNS_SUBDIR / "ryde"
        with self.assertRaises(sealed_roots.SealedDestinationError):
            run_benchmark.assert_external_run_directory(destination, runs_dir)
        self.assertFalse(destination.exists())


# --------------------------------------------------------------------------
# Structure: the cases, the briefs and the key
# --------------------------------------------------------------------------
class SealedV2StructureTests(unittest.TestCase):
    """Counts, keys and briefs. Never a value."""

    def test_all_12_cases_load_through_the_sets_own_loader(self):
        loaded = [SEALED_V2.load_case(case_no) for case_no in ALL_SEALED_V2_CASES]
        self.assertEqual(12, len(loaded))
        self.assertEqual(
            list(ALL_SEALED_V2_CASES), [case["case_no"] for case in loaded]
        )

    def test_all_12_briefs_build_at_version_6(self):
        for case_no in ALL_SEALED_V2_CASES:
            with self.subTest(case_no=case_no):
                built = brief.build_brief_for_case(
                    SEALED_V2.load_case(case_no), policy_version=6
                )
                self.assertIn("policies", built)

    def test_the_index_names_12_cases_and_the_key_agrees_with_it(self):
        with (SEALED_V2_CASES_DIR / "index.json").open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
        self.assertEqual(list(ALL_SEALED_V2_CASES), [entry["case_no"] for entry in entries])
        key = grade.load_answer_key(SEALED_V2_KEY_PATH)
        self.assertEqual(set(ALL_SEALED_V2_CASES), set(key))

    def test_every_record_of_the_key_carries_all_four_graded_fields(self):
        with SEALED_V2_KEY_PATH.open("r", encoding="utf-8") as handle:
            records = json.load(handle)
        self.assertEqual(12, len(records))
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
        for path in sorted(SEALED_V2_CASES_DIR.glob("case-*.json")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(case=path.name):
                for field in answer_fields:
                    self.assertNotIn(field, text)

    def test_the_loader_the_set_is_run_with_is_the_external_one(self):
        """The cases are absent from the corpus manifest on purpose."""
        case = loader.load_external_set_case(SEALED_V2_CASES_DIR, SENTINEL_CASE)
        self.assertEqual(SENTINEL_CASE, case["case_no"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
