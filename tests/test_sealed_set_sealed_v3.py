"""The fifth sealed set: registering it, the guards around its single run, and the
bundle it was imported from.

``sealed-v3`` is 30 cases under ``data/external/sealed-v3/``, keyed by
``eval/answers/sealed-v3/ground_truth.json``. Like the four sealed sets before
it, it is **not** a development set: it was made by Claude (Opus 5.5) in a fresh
Claude Code session with no project folder or repository access, from the owner's
prompt, the version-6 policy text, the public contract, a format checker and the
organisers' public sample case, and nobody on the development side has seen its
answers; it was imported on 2026-10-13, it is run exactly once, from a commit
whose ``tribunal/``, ``prompts/`` and ``policy/`` trees equal those at
``freeze-2026-10-11``, and that single run is the submission's fifth sealed
generalisation figure. Its registration fixes policy version 6, so it is run at
version 6 with no flag and ``--policy-version`` is refused for it. Its single run
has **not** been made, so its root is open to exactly one thing -- the plain
sealed run -- and every other destination under it is refused.

What is asserted here:

* **It is registered, and it is apart.** Its own cases, its own key, its own
  loader and its own runs root; it is absent from ``DEVELOPMENT_SETS``, so
  ``--set all`` does not run it and the combined figure does not include it.
* **The key and the case files are the ones the archive shipped.** The set's own
  ``MANIFEST.json`` -- the one file of archive B this repository reads -- states
  the key's sha256 and a sha256 for each case file; both are held to it. No file
  of archive B beyond the manifest is read by this module, and nothing of it is
  printed: what is compared is a digest.
* **Its switches are refused.** ``--force`` and each of the frozen arguments are
  refused for it, and the frozen invocation's arguments are accepted through the
  refusal function rather than by running it.
* **Its root is open to one thing.** Its single run has not been made, so the
  permit opens its plain run directory and refuses everything else under it.
* **The sealed run is the owner's.** Without ``TRIBUNAL_SEALED_RUN=sealed-v3``
  the invocation is refused before a client is built and writes nothing.
* **Its structure holds.** All 30 cases load by path and by number, their briefs
  build at version 6, no case number, dispute id or trip id collides with another
  registered set or the corpus manifest, and no answer field appears anywhere in a
  case file. These assert on counts and on keys, never on a value.

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
SEALED_V3 = sets.SEALED_V3

# The set's own directories, named here so a test can say which one it means.
SEALED_V3_CASES_DIR = PROJECT_ROOT / "data" / "external" / "sealed-v3"
SEALED_V3_KEY_PATH = PROJECT_ROOT / "eval" / "answers" / "sealed-v3" / "ground_truth.json"
SEALED_V3_ANSWERS_DIR = PROJECT_ROOT / "eval" / "answers" / "sealed-v3"
SEALED_V3_MANIFEST_PATH = SEALED_V3_ANSWERS_DIR / "MANIFEST.json"
SEALED_V3_EXTERNAL_DIR = PROJECT_ROOT / "eval" / "external" / "sealed-v3"

# 4001-4015 and 4051-4065: two fifteen-wide ranges, so the count and the ranges
# are written down rather than assumed from the files that happen to be there.
ALL_SEALED_V3_CASES = tuple(range(4001, 4016)) + tuple(range(4051, 4066))

# The first case of the set, used as the case a scratch fixture "has a result"
# for. It is a number, never a value.
SENTINEL_CASE = 4001

# The import note, whose digest table is the record of the two archives.
IMPORT_NOTE = PROJECT_ROOT / "docs" / "notes" / "2026-10-13-sealed-v3-imported.md"

# The key's sha256, as the archive's own ``MANIFEST.json`` states it and as the
# imported file hashes. A digest, never the key and never a value of it.
KEY_SHA256 = "c58d5610574a5341dffa2f64108dd4f1eb0712db585853f01ba976de344a4117"

# The two archives this set was imported from, as ``(name, sha256)``, checked
# against ``SHA256SUMS`` before anything was copied out.
ARCHIVES = (
    ("tribunal-sealed-v3-A-cases.zip", "af21c7568192af27ef98a95f70e99790193b3f643f89475874770b1dfe9d2f3a"),
    ("tribunal-sealed-v3-B-answers.zip", "cf7e68b72a363eb0930994f0cdd371568d2308b4a7320ab3b07cf9b60214ced4"),
)


def _run_cli(arguments):
    """``sets.main``, with both streams captured and no client buildable.

    Every invocation of the command line for ``sealed-v3`` is refused before a
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


def _manifest():
    """The set's own ``MANIFEST.json``, parsed.

    The one file of archive B this module reads: it holds counts, digests and
    provenance, and no answer. It is read for its digests and its counts, never
    for a value, and nothing of it is printed.
    """
    with SEALED_V3_MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
class SealedV3RegistryTests(unittest.TestCase):
    """The fifth sealed set is registered, and it is not a development set."""

    def test_it_is_registered_by_name_and_marked_sealed(self):
        self.assertIn("sealed-v3", sets.BY_NAME)
        self.assertIs(SEALED_V3, sets.BY_NAME["sealed-v3"])
        self.assertTrue(SEALED_V3.sealed, "the fifth sealed set is not marked sealed")
        self.assertEqual("sealed-v3", SEALED_V3.runs_subdir)

    def test_it_is_not_one_of_the_development_sets(self):
        """``--set all`` and the combined figure both read ``DEVELOPMENT_SETS``."""
        self.assertEqual(["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn(SEALED_V3, sets.DEVELOPMENT_SETS)
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1", "sealed-v2", "sealed-v3"),
            tuple(item.name for item in sets.SEALED_SETS),
        )
        self.assertIn(SEALED_V3, sets.SEALED_SETS)
        self.assertNotIn("sealed-v3", [item.name for item in sets.ALL_SETS])
        self.assertNotIn("sealed-v3", [item.name for item in sets.RERUN_SETS])
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
        self.assertEqual(6, SEALED_V3.policy_version)
        self.assertIsNone(SEALED_V3.policy_base)
        self.assertEqual(6, sets.resolved_policy_version(SEALED_V3, None))
        # A set that fixes its version keeps its own directory; the version does
        # not move its run one level down.
        self.assertFalse(sets.version_moves_the_run(SEALED_V3, None))

    def test_its_cases_are_the_30_it_was_imported_with(self):
        self.assertEqual(ALL_SEALED_V3_CASES, tuple(SEALED_V3.cases))

    def test_it_has_its_own_case_root_key_and_loader(self):
        self.assertEqual(SEALED_V3_CASES_DIR, SEALED_V3.case_root)
        self.assertEqual(SEALED_V3_KEY_PATH, SEALED_V3.key_path)
        for other in (
            sets.CORPUS,
            sets.SEALED_SET,
            sets.WILD_V2,
            sets.SEALED_V1,
            sets.SEALED_V2,
        ):
            with self.subTest(other=other.name):
                self.assertNotEqual(other.case_root, SEALED_V3.case_root)
                self.assertNotEqual(other.key_path, SEALED_V3.key_path)

    def test_its_runs_go_to_its_own_root(self):
        runs = Path("/tmp/sealed-v3-registry-runs")
        self.assertEqual(runs / "sealed-v3", SEALED_V3.runs_dir(runs))
        self.assertEqual(
            runs / "sealed-v3" / run_benchmark.model_slug(MODEL),
            SEALED_V3.run_dir(MODEL, runs),
        )

    def test_its_summary_names_it_the_fifth_sealed_set_run_once(self):
        summary = SEALED_V3.summary
        self.assertIn("fifth sealed set", summary)
        self.assertIn("sealed-v3", summary)
        self.assertIn("freeze-2026-10-11", summary)

    def test_its_cases_are_not_in_the_corpus_manifest(self):
        with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
            manifest = {entry["case_no"] for entry in json.load(handle)}
        self.assertEqual(set(), manifest & set(ALL_SEALED_V3_CASES))

    def test_its_run_directory_is_a_headline_directory(self):
        runs = Path("/tmp/sealed-v3-registry-runs")
        headline = [path.resolve() for path in run_benchmark.headline_run_directories(runs, MODEL)]
        self.assertIn((runs / "sealed-v3" / run_benchmark.model_slug(MODEL)).resolve(), headline)
        self.assertEqual(7, len(headline), "the headline directories are not seven")


# --------------------------------------------------------------------------
# Its root is open to exactly one thing
# --------------------------------------------------------------------------
class SealedV3RootIsOpenToItsSingleRunTests(unittest.TestCase):
    """Its single run has not been made, so its root accepts one destination."""

    def test_its_root_is_not_closed_and_the_un_run_list_names_it(self):
        self.assertFalse(sets.sealed_root_is_closed(SEALED_V3))
        self.assertEqual(("sealed-v3",), run_benchmark.UNRUN_SEALED_RUNS_SUBDIRS)
        self.assertEqual(
            ("wild", "wild-v2", "sealed-v1", "sealed-v2"),
            run_benchmark.MADE_SEALED_RUNS_SUBDIRS,
        )
        self.assertIn(
            run_benchmark.SEALED_V3_SET_RUNS_SUBDIR, run_benchmark.SET_RUNS_SUBDIRS
        )
        self.assertIn(
            run_benchmark.SEALED_V3_SET_RUNS_SUBDIR, run_benchmark.SEALED_RUNS_SUBDIRS
        )

    def test_the_permit_opens_exactly_the_plain_run_directory(self):
        """The one destination an un-run sealed root still accepts.

        The permit names the plain sealed run's own directory and is honoured for
        that path alone. Without it -- which is what a direct invocation of the
        runner gives -- the run directory is refused like anything else under the
        root, and so is every other destination even with the permit.
        """
        runs = Path("/tmp/sealed-v3-open-runs")
        run_dir = runs / "sealed-v3" / run_benchmark.model_slug(MODEL)
        self.assertEqual(
            run_dir.resolve(),
            run_benchmark.assert_not_under_the_held_out_root(
                run_dir, runs, permit=run_dir
            ).resolve(),
        )
        for destination, permit in (
            (run_dir, None),
            (run_dir / "case-04001.json", run_dir),
            (runs / "sealed-v3" / run_benchmark.ABLATION_DIRNAME / run_benchmark.model_slug(MODEL), run_dir),
        ):
            with self.subTest(destination=str(destination), permit=permit is not None):
                with self.assertRaises(run_benchmark.BenchmarkError):
                    run_benchmark.assert_not_under_the_held_out_root(
                        destination, runs, permit=permit
                    )


# --------------------------------------------------------------------------
# The key and the case files the archive shipped
# --------------------------------------------------------------------------
class SealedV3BundleDigestTests(unittest.TestCase):
    """The imported files are the ones the archive shipped, by digest.

    ``MANIFEST.json`` is the one file of archive B this module reads. It states
    the key's sha256 and a sha256 for each case file; both are held to it. No
    other file of archive B is read here, and nothing of it is printed.
    """

    def test_the_manifest_states_the_key_digest_the_imported_key_hashes_to(self):
        manifest = _manifest()
        self.assertEqual(KEY_SHA256, manifest["answer_key_sha256"])
        self.assertEqual(KEY_SHA256, run_benchmark.file_sha256(SEALED_V3_KEY_PATH))

    def test_every_case_file_hashes_to_the_digest_the_manifest_states(self):
        stated = _manifest()["case_file_sha256"]
        self.assertEqual(30, len(stated), "the manifest does not state 30 case digests")
        for case_no in ALL_SEALED_V3_CASES:
            name = "case-{0:05d}.json".format(case_no)
            with self.subTest(case=name):
                self.assertIn(name, stated)
                self.assertEqual(
                    stated[name],
                    run_benchmark.file_sha256(SEALED_V3_CASES_DIR / name),
                    "{0} does not hash to the digest the manifest states".format(name),
                )

    def test_the_sets_own_index_states_the_same_digests(self):
        """The archive's index, read here, is a second statement of one fact."""
        with (SEALED_V3_CASES_DIR / "index.json").open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
        stated = {entry["file"]: entry["sha256"] for entry in entries}
        self.assertEqual(30, len(stated), "the index does not state 30 case digests")
        for name, digest in sorted(stated.items()):
            with self.subTest(case=name):
                self.assertEqual(
                    digest,
                    run_benchmark.file_sha256(SEALED_V3_CASES_DIR / name),
                    "{0} does not match the digest the set's own index states".format(name),
                )

    def test_the_manifest_counts_the_30_cases_in_two_categories(self):
        manifest = _manifest()
        self.assertEqual(30, manifest["case_count"])
        self.assertEqual(list(ALL_SEALED_V3_CASES), list(manifest["case_numbers"]))
        self.assertEqual(
            {"NO_SHOW_CHARGE": 15, "ROUTE_DEVIATION": 15}, manifest["categories"]
        )

    def test_the_cases_directory_is_30_cases_and_an_index(self):
        names = sorted(
            path.name for path in SEALED_V3_CASES_DIR.iterdir() if path.is_file()
        )
        self.assertEqual(
            sorted(["index.json"] + ["case-{0:05d}.json".format(n) for n in ALL_SEALED_V3_CASES]),
            names,
        )

    def test_the_answers_root_holds_the_key_and_the_manifest(self):
        self.assertTrue(SEALED_V3_KEY_PATH.is_file(), "the fifth sealed key is missing")
        self.assertTrue(
            SEALED_V3_MANIFEST_PATH.is_file(), "the fifth sealed manifest is missing"
        )

    def test_the_note_records_the_two_archives_and_their_digests(self):
        text = IMPORT_NOTE.read_text(encoding="utf-8")
        for name, digest in ARCHIVES:
            with self.subTest(archive=name):
                self.assertIn(name, text)
                self.assertIn(digest, text)


# --------------------------------------------------------------------------
# The sealed run is the owner's
# --------------------------------------------------------------------------
class SealedV3SealedRunLockTests(unittest.TestCase):
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
                ["--set", "sealed-v3", "--concurrency", "2", "--timeout", "900"]
                + list(extra)
            )
        return runs, code, out, err

    def test_without_the_opt_in_the_invocation_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ):
                os.environ.pop(sets.SEALED_RUN_ENV_VAR, None)
                runs, code, _out, err = self._invocation(tmp)

            self.assertEqual(1, code, "the sealed run was not locked")
            # The run has not been made, so the refusal is the opt-in's: the
            # variable is what makes this run the owner's.
            self.assertIn("is made by the owner only", err)
            self.assertIn(sets.SEALED_RUN_ENV_VAR, err)
            self.assertIn("sealed-v3", err)
            self.assertFalse(runs.exists(), "the refused invocation created the runs root")

    def test_the_opt_in_set_to_any_other_value_is_refused(self):
        for value in ("wild", "wild-v2", "sealed-v1", "sealed-v2", "", "1", "SEALED-V3"):
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
class SealedV3SwitchGuardTests(unittest.TestCase):
    """``--force`` is refused for this set, and for this set only."""

    def test_force_is_refused_and_leaves_the_result_it_would_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            run_dir = runs / "sealed-v3" / run_benchmark.model_slug(MODEL)
            run_dir.mkdir(parents=True)
            sentinel = run_dir / "case-{0:05d}.json".format(SENTINEL_CASE)
            sentinel.write_text(
                json.dumps({"case_no": SENTINEL_CASE, "sentinel": "the sealed result"}, indent=2),
                encoding="utf-8",
            )
            before = sentinel.read_bytes()

            code, _, err = _run_cli_over(runs, ["--set", "sealed-v3", "--force"])

            self.assertEqual(1, code, "a sealed run accepted --force")
            self.assertIn("the sealed set {0} is run once".format(SEALED_V3.name), err)
            self.assertIn("--force", err)
            self.assertEqual(before, sentinel.read_bytes(), "the sealed result was rewritten")
            self.assertEqual(
                {sentinel.name: before}, _state(run_dir), "the run directory gained a file"
            )

    def test_the_refusal_is_for_this_set_and_not_for_the_others(self):
        for development_set in sets.DEVELOPMENT_SETS + sets.RERUN_SETS:
            with self.subTest(development_set=development_set.name):
                self.assertIsNone(sets.assert_not_sealed(development_set, "--force"))

    def test_the_frozen_arguments_are_accepted_though_the_root_is_not_open_yet(self):
        """A guard that refused everything would pass the test above.

        The argument check and the destination check are separate rules. This
        pins the first: the owner's own invocation differs in no argument, so
        ``run_argument_differences`` is empty. The second opens that same
        invocation's own destination and refuses every other --
        ``SealedV3RootIsOpenToItsSingleRunTests`` is where that is asserted.
        """
        self.assertEqual([], sets.run_argument_differences(SEALED_V3, **_frozen_arguments()))


# --------------------------------------------------------------------------
# The run arguments, frozen in the registration
# --------------------------------------------------------------------------
class SealedV3RunArgumentsTests(unittest.TestCase):
    """``--set sealed-v3`` runs at the arguments its registration fixes, or not at all."""

    def test_the_registration_records_the_eight_settings(self):
        frozen = SEALED_V3.run_arguments
        self.assertIsNotNone(frozen, "sealed-v3 fixes no run arguments")
        self.assertEqual("deepseek/deepseek-flash", frozen.model)
        self.assertEqual(4, frozen.judge_votes)
        self.assertFalse(frozen.verify_drafts)
        self.assertEqual(900.0, frozen.timeout_seconds)
        self.assertEqual(2, frozen.concurrency)
        # "The default" is recorded as the default rather than as today's number.
        self.assertIsNone(frozen.prompts_dir)
        self.assertIsNone(frozen.case_deadline_seconds)
        self.assertIsNone(frozen.token_budget)

    def test_its_arguments_are_sealed_v2s(self):
        """The fifth set's run is fixed at the same configuration as the fourth's."""
        self.assertEqual(sets.SEALED_V2.run_arguments, SEALED_V3.run_arguments)

    def test_the_invocation_the_owner_will_run_differs_in_nothing(self):
        self.assertEqual(
            [],
            sets.run_argument_differences(SEALED_V3, **_frozen_arguments()),
            "the frozen invocation is refused",
        )

    def test_each_differing_argument_is_named_with_its_registered_value(self):
        for switch, overrides, asked_text, registered_text in FROZEN_ARGUMENT_DIFFERENCES:
            with self.subTest(switch=switch):
                differences = sets.run_argument_differences(
                    SEALED_V3, **_frozen_arguments(**overrides)
                )
                self.assertEqual(
                    1,
                    len(differences),
                    "{0} did not give exactly one difference: {1}".format(switch, differences),
                )
                self.assertIn(switch, differences[0])
                self.assertIn(asked_text, differences[0])
                self.assertIn(
                    "sealed-v3 is registered at {0}".format(registered_text),
                    differences[0],
                )

    def test_the_policy_version_flag_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            with mock.patch.object(sets, "RUNS_DIR", runs), mock.patch.object(
                run_benchmark, "RUNS_DIR", runs
            ):
                code, _out, err = _run_cli(
                    ["--set", "sealed-v3", "--policy-version", "3"]
                )
            self.assertEqual(1, code, "--policy-version was accepted for the sealed set")
            self.assertIn("fixes policy version 6", err)
            self.assertFalse(runs.exists())


# --------------------------------------------------------------------------
# Every write path refuses the root
# --------------------------------------------------------------------------
class SealedV3WritePathTests(unittest.TestCase):
    """The sealed-root rule refuses this set's root, and the others still work.

    ``tests/test_sealed_roots_closed.py`` runs one test per call site for every
    sealed root, this one included, by looping the registrations. What is
    asserted here is the same property stated over this set alone, so the set's
    own contribution to the boundary is visible: the shared helper refuses every
    destination under ``runs/sealed-v3/`` -- the plain run directory included,
    because the six named-path commands hold no permit -- and a destination of
    its own is still taken.
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
        destination = self.runs / "sealed-v3" / "report.md"
        with self.assertRaises(sealed_roots.SealedDestinationError) as caught:
            sealed_roots.refuse_a_sealed_destination(destination, self.runs)
        self.assertIn(str(destination.resolve()), str(caught.exception))

    def test_the_shared_helper_refuses_the_plain_run_directory_too(self):
        """The six named-path commands hold no permit, so even that is refused."""
        destination = self.runs / "sealed-v3" / run_benchmark.model_slug(MODEL)
        with self.assertRaises(sealed_roots.SealedDestinationError):
            sealed_roots.refuse_a_sealed_destination(destination, self.runs)

    def test_a_destination_of_its_own_is_still_taken(self):
        """A guard that refused everything would pass the test above."""
        destination = self.runs / "a-command-of-its-own" / "report.md"
        self.assertEqual(
            destination.resolve(),
            sealed_roots.refuse_a_sealed_destination(destination, self.runs).resolve(),
        )

    def test_the_external_runner_refuses_the_root(self):
        runs_dir = self.runs / "sealed-v3"
        destination = runs_dir / run_benchmark.EXTERNAL_RUNS_SUBDIR / "ryde"
        with self.assertRaises(sealed_roots.SealedDestinationError):
            run_benchmark.assert_external_run_directory(destination, runs_dir)
        self.assertFalse(destination.exists())


# --------------------------------------------------------------------------
# Structure: the cases, the briefs and the key
# --------------------------------------------------------------------------
class SealedV3StructureTests(unittest.TestCase):
    """Counts, keys and briefs. Never a value."""

    def test_all_30_cases_load_by_path_and_by_number(self):
        by_path = [
            loader.load_external_case(SEALED_V3_CASES_DIR / "case-{0:05d}.json".format(n))
            for n in ALL_SEALED_V3_CASES
        ]
        by_number = [SEALED_V3.load_case(n) for n in ALL_SEALED_V3_CASES]
        self.assertEqual(30, len(by_path))
        self.assertEqual(list(ALL_SEALED_V3_CASES), [case["case_no"] for case in by_path])
        self.assertEqual(list(ALL_SEALED_V3_CASES), [case["case_no"] for case in by_number])

    def test_all_30_briefs_build_at_version_6(self):
        for case_no in ALL_SEALED_V3_CASES:
            with self.subTest(case_no=case_no):
                built = brief.build_brief_for_case(
                    SEALED_V3.load_case(case_no), policy_version=6
                )
                self.assertIn("policies", built)

    def test_the_index_names_30_cases_and_the_key_agrees_with_it(self):
        with (SEALED_V3_CASES_DIR / "index.json").open("r", encoding="utf-8") as handle:
            entries = json.load(handle)
        self.assertEqual(list(ALL_SEALED_V3_CASES), [entry["case_no"] for entry in entries])
        key = grade.load_answer_key(SEALED_V3_KEY_PATH)
        self.assertEqual(set(ALL_SEALED_V3_CASES), set(key))

    def test_no_case_number_dispute_id_or_trip_id_collides(self):
        """Over every other external set and the corpus manifest.

        Read from each set's own index -- the file that names its cases -- so a
        number, a dispute id or a trip id that another set already uses is a
        failure rather than a coincidence nobody checked.
        """
        def identifiers(entries):
            return {
                ("case_no", entry["case_no"]) for entry in entries
            } | {
                ("dispute_id", entry["dispute_id"]) for entry in entries
            } | {
                ("trip_id", entry["trip_id"]) for entry in entries
            }

        with (SEALED_V3_CASES_DIR / "index.json").open("r", encoding="utf-8") as handle:
            mine = json.load(handle)
        others = set()
        with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
            others |= identifiers(json.load(handle))
        for index in sorted((PROJECT_ROOT / "data" / "external").glob("*/index.json")):
            if index.parent == SEALED_V3_CASES_DIR:
                continue
            with index.open("r", encoding="utf-8") as handle:
                others |= identifiers(json.load(handle))
        self.assertEqual(set(), identifiers(mine) & others)

    def test_no_answer_field_appears_in_any_case_file(self):
        answer_fields = (
            "expected_ruling",
            "expected_amount_sgd",
            "expected_driver_compensation_sgd",
            "expected_referrals",
            "ground_truth",
        )
        for path in sorted(SEALED_V3_CASES_DIR.glob("case-*.json")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(case=path.name):
                for field in answer_fields:
                    self.assertNotIn(field, text)

    def test_the_loader_the_set_is_run_with_is_the_external_one(self):
        """The cases are absent from the corpus manifest on purpose."""
        case = loader.load_external_set_case(SEALED_V3_CASES_DIR, SENTINEL_CASE)
        self.assertEqual(SENTINEL_CASE, case["case_no"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
