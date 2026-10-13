"""The version-7 development set: ``dev-v7``, 40 cases written for Ryde's policy.

``dev-v7`` is the development set for policy version 7 -- Ryde's own Dispute
Resolution Policy v2.1 -- and it is **not** a sealed set: it is development data
that is tuned against, so no figure from it is ever a generalisation figure. Its
40 cases are 5001-5020 (``ROUTE_DEVIATION``) and 5051-5070
(``NO_SHOW_CHARGE``), under ``data/external/dev-v7/``, keyed by
``eval/answers/dev-v7/answers/ground_truth.json``.

The set's own archive-B tree was extracted into ``eval/answers/dev-v7/`` byte
for byte, so the key, its ``MANIFEST.json``, the author's ``generator/`` and the
second reading under ``notes/`` all sit under the physically isolated answers
root -- the ``answers/``, ``generator/`` and ``notes/`` folders are the archive's
own, one level below the set's answers directory. ``MANIFEST.json`` is the one
file of that tree this module reads for its digests and its counts; nothing here
prints a value from the key.

What is asserted:

* **the import.** Every one of the 40 case files hashes to the digest its own
  ``index.json`` states and to the digest the manifest states, and the key
  hashes to the manifest's ``answer_key_sha256``;
* **the structure.** 40 of 40 load by path and by number, every brief builds at
  policy version 7, and no case number, dispute id or trip id collides with
  another registered set or the corpus manifest;
* **the isolation.** No answer-field name appears anywhere in a case file, and
  the brief built from each case carries none either;
* **the registration.** It is registered by name, marked not sealed, fixes
  policy version 7 and the ``prompts/v2`` prompt set, and is in none of the
  tuples ``--set all``, the combined figure and the recorded-drafts measurement
  read;
* **the prompt channel.** Its committed run reads current on both staleness
  channels, and so do the other two version-7 runs: the checker
  ``currency_for`` builds is handed the prompts directory the run used --
  ``prompts/v2`` -- rather than the ``prompts/v1`` default, which would compare
  every case's recorded digests with a prompt set no call of that run was given.
  The control puts the default back and shows the 30 cases read
  ``stale_prompts``.

No model is called anywhere in this module, and nothing is written.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets as sets, grade, run_benchmark  # noqa: E402
from tests import test_answer_isolation as isolation  # noqa: E402
from tribunal import brief, loader  # noqa: E402

SET_NAME = "dev-v7"

# The declared constant and the registration. ``DEV_V7`` is what part 72 wrote
# down -- the name, the root, the key and the arguments -- with no case numbers,
# because a set with no data has no index to read them from; the registry holds
# the same set with its 40 case numbers filled in, and that is the one a run
# uses.
DECLARATION = sets.DEV_V7
SET = sets.BY_NAME[SET_NAME]

# The set's own directories, named here so a test can say which one it means.
SET_DIR = PROJECT_ROOT / "data" / "external" / SET_NAME
ANSWERS_DIR = PROJECT_ROOT / "eval" / "answers" / SET_NAME
KEY_PATH = ANSWERS_DIR / "answers" / "ground_truth.json"
MANIFEST_PATH = ANSWERS_DIR / "answers" / "MANIFEST.json"
EXTERNAL_DIR = PROJECT_ROOT / "eval" / "external" / SET_NAME

# 5001-5020 and 5051-5070: two twenty-wide ranges, so the count and the ranges
# are written down rather than assumed from the files that happen to be there.
ALL_CASES = tuple(range(5001, 5021)) + tuple(range(5051, 5071))

# The first case of the set, used as the case a scratch fixture "has a result"
# for. It is a number, never a value.
SENTINEL_CASE = 5001

# The answer-field names, the same needles the sealed sets are held to.
ANSWER_FIELD_NAMES = (
    "expected_ruling",
    "expected_amount_sgd",
    "expected_driver_compensation_sgd",
    "expected_referrals",
    "ground_truth",
)


def manifest():
    """The set's own ``MANIFEST.json``, parsed.

    It holds counts, digests and provenance and no answer, and it is read for
    its digests and its counts -- never for a value, and nothing of it is
    printed.
    """
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def index_entries():
    with (SET_DIR / "index.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------
# The import: the files are the ones the archive shipped
# --------------------------------------------------------------------------
class DevV7BundleDigestTests(unittest.TestCase):
    """The imported files are the ones the archive shipped, by digest."""

    def test_the_manifest_states_the_key_digest_the_imported_key_hashes_to(self):
        stated = manifest()["answer_key_sha256"]
        self.assertEqual(stated, run_benchmark.file_sha256(KEY_PATH))

    def test_every_case_file_hashes_to_the_digest_the_manifest_states(self):
        stated = manifest()["case_file_sha256"]
        self.assertEqual(40, len(stated), "the manifest does not state 40 case digests")
        for case_no in ALL_CASES:
            name = "case-{0:05d}.json".format(case_no)
            with self.subTest(case=name):
                self.assertIn(name, stated)
                self.assertEqual(
                    stated[name],
                    run_benchmark.file_sha256(SET_DIR / name),
                    "{0} does not hash to the digest the manifest states".format(name),
                )

    def test_the_sets_own_index_states_the_same_digests(self):
        """The archive's index, read here, is a second statement of one fact."""
        stated = {entry["file"]: entry["sha256"] for entry in index_entries()}
        self.assertEqual(40, len(stated), "the index does not state 40 case digests")
        for name, digest in sorted(stated.items()):
            with self.subTest(case=name):
                self.assertEqual(
                    digest,
                    run_benchmark.file_sha256(SET_DIR / name),
                    "{0} does not match the digest the set's own index states".format(name),
                )

    def test_the_manifest_counts_the_40_cases_in_two_categories(self):
        document = manifest()
        self.assertEqual(40, document["case_count"])
        self.assertEqual(list(ALL_CASES), list(document["case_numbers"]))
        self.assertEqual(
            {"NO_SHOW_CHARGE": 20, "ROUTE_DEVIATION": 20}, document["categories"]
        )

    def test_the_manifest_says_the_author_received_the_earlier_policy_files(self):
        """The version-7 policy gained two structured fields after the set was made.

        The manifest's ``reference_file_sha256`` names the files the author was
        given, and the two that changed are the two the fields were added to. The
        clause text did not change, so this is recorded rather than reconciled:
        the digests differ, and the files the set is briefed against are the
        current ones.
        """
        references = manifest()["reference_file_sha256"]
        self.assertEqual(
            "ddb3dcf3c6c3d8cb296900a323df5fa18c4aad660e19e1b7787db5db0787c8ca",
            references["route_deviation.json"],
        )
        self.assertEqual(
            "d638a3b68a6b7bc7655dd984dccafa2f541b448c29c2af18355eb10eefc80d3b",
            references["no_show.json"],
        )
        for name in ("route_deviation.json", "no_show.json"):
            with self.subTest(file=name):
                self.assertNotEqual(
                    references[name],
                    run_benchmark.file_sha256(PROJECT_ROOT / "policy" / "v7" / name),
                )
        self.assertEqual(
            references["general.json"],
            run_benchmark.file_sha256(PROJECT_ROOT / "policy" / "v7" / "general.json"),
            "general.json is the one version-7 file that did not move",
        )

    def test_the_cases_directory_is_40_cases_and_an_index(self):
        names = sorted(path.name for path in SET_DIR.iterdir() if path.is_file())
        self.assertEqual(
            sorted(["index.json"] + ["case-{0:05d}.json".format(n) for n in ALL_CASES]),
            names,
        )

    def test_the_external_root_holds_the_readme_and_the_canary(self):
        self.assertEqual(
            ["CANARY.txt", "README.md"],
            sorted(path.name for path in EXTERNAL_DIR.iterdir() if path.is_file()),
        )

    def test_the_answers_root_holds_the_archives_own_three_folders(self):
        self.assertEqual(
            ["answers", "generator", "notes"],
            sorted(path.name for path in ANSWERS_DIR.iterdir() if path.is_dir()),
        )
        self.assertTrue(KEY_PATH.is_file(), "the version-7 development key is missing")
        self.assertTrue(MANIFEST_PATH.is_file(), "the set's manifest is missing")


# --------------------------------------------------------------------------
# The registration
# --------------------------------------------------------------------------
class DevV7RegistrationTests(unittest.TestCase):
    """The set is registered, it is not sealed, and it fixes version 7."""

    def test_it_is_registered_by_name_and_not_marked_sealed(self):
        self.assertIn(SET_NAME, sets.BY_NAME)
        self.assertEqual(SET_NAME, SET.name)
        self.assertFalse(SET.sealed, "the version-7 development set is marked sealed")
        self.assertEqual(SET_NAME, SET.runs_subdir)
        self.assertEqual(SET_DIR, SET.case_root)
        self.assertEqual(KEY_PATH, SET.key_path)
        self.assertEqual(DECLARATION.summary, SET.summary)

    def test_its_cases_are_the_40_it_was_imported_with(self):
        self.assertEqual((), DECLARATION.cases, "the declaration lists case numbers")
        self.assertEqual(ALL_CASES, tuple(SET.cases))

    def test_it_is_a_named_set_and_never_a_development_one(self):
        """``--set all``, the combined figure and the measurements never read it."""
        self.assertEqual(
            ["corpus", "codex"], [item.name for item in sets.DEVELOPMENT_SETS]
        )
        self.assertIn(SET_NAME, [item.name for item in sets.NAMED_SETS])
        self.assertNotIn(SET_NAME, [item.name for item in sets.DEVELOPMENT_SETS])
        self.assertNotIn(SET_NAME, [item.name for item in sets.ALL_SETS])
        self.assertNotIn(SET_NAME, [item.name for item in sets.SEALED_SETS])
        self.assertNotIn(SET_NAME, [item.name for item in sets.RERUN_SETS])
        self.assertNotIn(SET_NAME, sets.DECLARED_SETS)

    def test_it_fixes_policy_version_seven(self):
        self.assertEqual(7, SET.policy_version)
        self.assertEqual(7, SET.policy_base)
        self.assertEqual(7, sets.resolved_policy_version(SET, None))

    def test_its_run_arguments_are_sealed_v2s_with_the_version_seven_prompts(self):
        frozen = SET.run_arguments
        self.assertIsNotNone(frozen, "dev-v7 fixes no run arguments")
        sealed_v2 = sets.SEALED_V2.run_arguments
        self.assertEqual(sealed_v2.model, frozen.model)
        self.assertEqual(sealed_v2.judge_votes, frozen.judge_votes)
        self.assertEqual(sealed_v2.verify_drafts, frozen.verify_drafts)
        self.assertEqual(sealed_v2.timeout_seconds, frozen.timeout_seconds)
        self.assertEqual(sealed_v2.concurrency, frozen.concurrency)
        self.assertEqual(Path("prompts/v2"), frozen.prompts_dir)

    def test_its_runs_go_to_its_own_root(self):
        runs = Path("/tmp/dev-v7-registry-runs")
        self.assertEqual(runs / SET_NAME, SET.runs_dir(runs))
        self.assertEqual(
            runs / SET_NAME / run_benchmark.model_slug("deepseek/deepseek-flash"),
            SET.run_dir("deepseek/deepseek-flash", runs),
        )

    def test_its_cases_are_not_in_the_corpus_manifest(self):
        with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
            corpus = {entry["case_no"] for entry in json.load(handle)}
        self.assertEqual(set(), corpus & set(ALL_CASES))


# --------------------------------------------------------------------------
# Structure: the cases, the briefs and the key
# --------------------------------------------------------------------------
class DevV7StructureTests(unittest.TestCase):
    """Counts, keys and briefs. Never a value."""

    def test_all_40_cases_load_by_path_and_by_number(self):
        by_path = [
            loader.load_external_case(SET_DIR / "case-{0:05d}.json".format(n))
            for n in ALL_CASES
        ]
        by_number = [SET.load_case(n) for n in ALL_CASES]
        self.assertEqual(40, len(by_path))
        self.assertEqual(list(ALL_CASES), [case["case_no"] for case in by_path])
        self.assertEqual(list(ALL_CASES), [case["case_no"] for case in by_number])

    def test_all_40_briefs_build_at_version_7(self):
        for case_no in ALL_CASES:
            with self.subTest(case_no=case_no):
                built = brief.build_brief_for_case(SET.load_case(case_no), policy_version=7)
                self.assertIn("policies", built)
                self.assertIn("authority", built["case"])

    def test_the_index_names_40_cases_and_the_key_agrees_with_it(self):
        entries = index_entries()
        self.assertEqual(list(ALL_CASES), [entry["case_no"] for entry in entries])
        key = grade.load_answer_key(KEY_PATH)
        self.assertEqual(set(ALL_CASES), set(key))

    def test_the_key_covers_every_case_and_only_these(self):
        key = grade.load_answer_key(KEY_PATH)
        self.assertEqual(set(ALL_CASES), set(key))
        for case_no, expected in sorted(key.items()):
            with self.subTest(case_no=case_no):
                self.assertIn(
                    expected.difficulty,
                    {"EASY", "HARD", "REVERSAL", "INDETERMINATE"},
                    "a difficulty outside the grader's vocabulary",
                )

    def test_no_case_number_dispute_id_or_trip_id_collides(self):
        """Over every other external set and the corpus manifest.

        Read from each set's own index -- the file that names its cases -- so a
        number, a dispute id or a trip id another set already uses is a failure
        rather than a coincidence nobody checked.
        """

        def identifiers(entries):
            return {
                ("case_no", entry["case_no"]) for entry in entries
            } | {
                ("dispute_id", entry["dispute_id"]) for entry in entries
            } | {
                ("trip_id", entry["trip_id"]) for entry in entries
            }

        mine = identifiers(index_entries())
        others = set()
        with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
            others |= identifiers(json.load(handle))
        for index in sorted((PROJECT_ROOT / "data" / "external").glob("*/index.json")):
            if index.parent == SET_DIR:
                continue
            with index.open("r", encoding="utf-8") as handle:
                others |= identifiers(json.load(handle))
        self.assertEqual(set(), mine & others, sorted(mine & others))

    def test_no_answer_field_name_appears_in_any_case_file(self):
        for path in sorted(SET_DIR.glob("case-*.json")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(case=path.name):
                for field in ANSWER_FIELD_NAMES:
                    self.assertNotIn(field, text)

    def test_no_brief_of_the_set_carries_an_answer_key_name(self):
        """The same control the sealed sets and the corpus are held to.

        Asked through ``tests.test_answer_isolation``'s own function, so the
        question and the answer are the ones every other set is asked and given.
        """
        for case_no in ALL_CASES:
            with self.subTest(case_no=case_no):
                self.assertEqual(
                    {},
                    isolation._brief_violations_for_case(
                        SET.load_case(case_no), policy_version=7
                    ),
                )

    def test_the_loader_the_set_is_run_with_is_the_external_one(self):
        """The cases are absent from the corpus manifest on purpose."""
        case = loader.load_external_set_case(SET_DIR, SENTINEL_CASE)
        self.assertEqual(SENTINEL_CASE, case["case_no"])

    def test_the_canary_reaches_no_brief(self):
        """The canary marks the set; a version-7 brief must never carry it."""
        canary = (EXTERNAL_DIR / "CANARY.txt").read_text(encoding="utf-8").strip()
        self.assertTrue(canary, "the canary is empty")
        for case_no in ALL_CASES:
            with self.subTest(case_no=case_no):
                canonical, _ = brief.brief_digest(
                    brief.build_brief_for_case(SET.load_case(case_no), policy_version=7)
                )
                self.assertNotIn(canary, canonical)


# --------------------------------------------------------------------------
# The prompt channel: the checker reads the prompts the run used
# --------------------------------------------------------------------------
class TheVersionSevenCurrencyTests(unittest.TestCase):
    """The three version-7 runs read current, and the prompt set is why.

    ``currency_for`` builds the same checker the runner builds before a run, and
    its prompt channel is answered against a **directory**: each case's recorded
    prompt digests are compared with what this code renders from that directory
    now. A version-7 run is run with ``prompts/v2`` and records that set's
    digests, so a checker handed ``prompts/v1`` -- which is what
    ``run_benchmark.PROMPTS_DIR`` is -- compares every case against a prompt set
    no call of that run was ever given and reports a correct run as having moved
    its prompts. Every version-7 console log ends with exactly that line, and
    the report's currency line for ``sealed-v4`` printed it too.

    The counts are the committed runs' own, written down rather than read off
    the sets, so a run that lost a case fails here instead of agreeing with
    itself. Nothing is written and no model is called.
    """

    MODEL = "deepseek/deepseek-flash"

    # One row per version-7 set: the cases it has committed a ruling for.
    VERSION_SEVEN = (("sealed-v4", 30), ("dev-v7", 40), ("ryde-v7", 2))

    def test_each_version_seven_run_reads_current_on_both_channels(self):
        for name, produced in self.VERSION_SEVEN:
            development_set = sets.named(name)
            with self.subTest(set=name):
                self.assertEqual(
                    produced,
                    len(sets.cached_cases(development_set, self.MODEL)),
                    "the committed run does not hold the set's cases",
                )
                staleness = sets.currency_for(development_set, self.MODEL)
                self.assertTrue(staleness.checked)
                self.assertEqual((), staleness.stale)
                self.assertEqual((), staleness.stale_brief)
                self.assertEqual((), staleness.stale_prompts)
                self.assertEqual((), staleness.unknown)

    def test_the_checker_is_handed_the_prompts_directory_the_run_used(self):
        # One directory has two spellings here: ``dev-v7`` and ``sealed-v4``
        # register the relative ``Path("prompts/v2")``, and ``ryde-v7``, which
        # registers none, is answered ``run_benchmark.prompts_directory_for(7)``
        # -- the absolute ``PROJECT_ROOT / "prompts" / "v2"``. Both name the same
        # directory, so the answer is compared as a directory: a relative one is
        # resolved against the project root first. A set answering ``prompts/v1``
        # in either spelling still fails.
        for name, _produced in self.VERSION_SEVEN:
            with self.subTest(set=name):
                named = sets.registered_prompts_dir(sets.named(name))
                if not named.is_absolute():
                    named = run_benchmark.PROJECT_ROOT / named
                self.assertEqual(
                    (run_benchmark.PROJECT_ROOT / "prompts" / "v2").resolve(),
                    named.resolve(),
                    "{0} is checked against {1!r}".format(name, named),
                )
        # And the two sets whose registration records the arguments their run is
        # fixed at record it themselves, which is the first answer.
        for name in ("dev-v7", "sealed-v4"):
            with self.subTest(set=name):
                self.assertEqual(
                    Path("prompts/v2"), sets.BY_NAME[name].run_arguments.prompts_dir
                )
        # ``ryde-v7`` is development data and fixes no run arguments, so its
        # answer comes from the pairing the runner enforces instead.
        self.assertIsNone(sets.RYDE_V7.run_arguments)

    def test_a_version_six_set_is_checked_against_the_prompts_it_was_run_with(self):
        """The other half of the pairing: versions 1 to 6 are run with prompts/v1."""
        for name in ("corpus", "codex", "dev-v2"):
            with self.subTest(set=name):
                self.assertEqual(
                    run_benchmark.PROMPTS_DIR,
                    sets.registered_prompts_dir(sets.named(name)),
                )
        staleness = sets.currency_for(sets.named("codex"), self.MODEL)
        self.assertTrue(staleness.checked)
        self.assertEqual((), staleness.stale_brief)
        self.assertEqual((), staleness.unknown)

    def test_the_control_the_version_six_prompts_report_the_cases_as_moved(self):
        """The control: the default is what the change replaced.

        With ``registered_prompts_dir`` answering ``prompts/v1`` -- which is
        what the checker was handed before it read the set -- all 30 of
        ``sealed-v4``'s cases read ``stale_prompts``: their recorded
        ``prompts/v2`` digests are compared with ``prompts/v1``. That is the
        line the run's own console log ends with and the line the report printed
        for this set, so the positive reading above fails if this one comes
        back.
        """
        development_set = sets.named("sealed-v4")
        with mock.patch.object(
            sets, "registered_prompts_dir", return_value=run_benchmark.PROMPTS_DIR
        ):
            staleness = sets.currency_for(development_set, self.MODEL)
        self.assertEqual(30, len(staleness.stale_prompts))
        self.assertEqual(30, len(staleness.stale))
        self.assertEqual((), staleness.stale_brief)
        self.assertEqual((), staleness.unknown)


if __name__ == "__main__":
    unittest.main(verbosity=2)
