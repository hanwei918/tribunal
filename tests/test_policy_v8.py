"""Policy version 8: version 7 with Ryde's answers of 2026-10-14 applied.

Version 8 is a **separate base**, like versions 3 and 7: ``policy/v8/`` holds
``general.json``, ``route_deviation.json`` and ``no_show.json``, copied byte for
byte from ``policy/v7/`` and edited at fifteen JSON paths and nowhere else. This
module pins that: it walks both trees and asserts the differing paths are exactly
the ones the version-8 text names, with the value each one carries.

**The one rule this module holds the change to: versions 1 to 7 do not move.**
Version 7 still reads ``policy/v7/``, its files are untouched, and the version-8
files are reached only when a version of 8 or above is asked for. Version 8 is a
separate base, so its three files are read whole and ``policy/v8/`` *is* version
8.

The last three classes read the two version-8 sets rather than the policy files:
the registration reuses the version-7 case files and moves only the key, so they
assert the counts, the version and the base each set is fixed at, that a
version-8 run is refused with ``prompts/v1``, that every set registered before
them lists the same cases it always did, and that the two version-8 keys are the
version-7 keys with exactly the entries the 2 km limb moves.

No model is called, nothing is written and no sealed root is read.
"""

from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets as sets, run_benchmark  # noqa: E402
from tools import derive_v8_keys  # noqa: E402
from tribunal import loader, policy_versions  # noqa: E402

POLICY_DIR = PROJECT_ROOT / "policy"
POLICY_V7_DIR = POLICY_DIR / "v7"
POLICY_V8_DIR = POLICY_DIR / "v8"

VERSION_SEVEN = 7
VERSION_EIGHT = 8

# The three files version 8 carries, and the four files it is made of: the same
# three plus the amendments README that records that no amendment is approved.
V8_FILES = ("general.json", "no_show.json", "route_deviation.json")

# Every JSON path at which ``policy/v8/`` differs from ``policy/v7/``, with the
# value version 8 states there. The keys are the paths a reader would follow into
# the document -- ``clauses[3]`` is the fourth clause of the file's own list --
# and the values are the whole of what version 8 says. Anything else differing is
# a failure, and so is any of these not differing.
#
# Fifteen paths: two in ``general.json``, six in ``no_show.json`` and seven in
# ``route_deviation.json``.
V8_DIFFERENCES = {
    "general.json": {
        "version": "8.0.0",
        "last_reviewed": "2026-10-14",
    },
    "no_show.json": {
        "version": "8.0.0",
        "last_reviewed": "2026-10-14",
        "thresholds.free_wait_starts": (
            "trip_record.arrived_at (C2, settled by Ryde on 2026-10-14)"
        ),
        "thresholds.free_wait_starts_from": "arrived_at",
        "clauses[0].rule": (
            "The driver waits a free wait time of 5 minutes (300 s) from the "
            "driver's arrival at the pickup; after it, the driver may cancel the "
            "trip as a rider no-show."
        ),
        "clauses[0].notes": (
            "v2.1's free wait, with its start settled by Ryde on 2026-10-14 (C2): "
            "the clock runs from the driver's arrival, scheduled trip or not."
        ),
    },
    "route_deviation.json": {
        "version": "8.0.0",
        "last_reviewed": "2026-10-14",
        "thresholds.ai_ruling_max_deviation_applied": True,
        "thresholds.ai_ruling_max_deviation_note": (
            "C1, settled by Ryde on 2026-10-14: v2.1 6.2's 2 km limb applies; a "
            "route deviation over 2 km is escalated (DISP-001's 4.3 km included)."
        ),
        "clauses[3].notes": (
            "Tribunal's reading where v2.1 is silent or ambiguous; to be confirmed "
            "with Ryde. C3, confirmed by Ryde on 2026-10-14: the excess distance "
            "fare is at the base per-km rate, without surge (DISP-001: 4.3 x 0.80 "
            "= 3.44). C5: rows (b) and (d) both pay the whole excess distance "
            "fare; 'partial' and 'full' in v2.1 1.3 are read as describing the "
            "trip fare and the excess distance fare respectively. Ruling label "
            "PARTIAL_REFUND, because neither returns the whole trip fare."
        ),
        "clauses[4].rule": (
            "The AI ruling on a route deviation stands only where POL-GEN-22 "
            "allows it, its confidence is 0.80 or more, and the deviation is 2 km "
            "or less (v2.1 6.2); otherwise the case is escalated."
        ),
        "clauses[4].notes": (
            "v2.1 6.2. The 2 km limb was confirmed by Ryde on 2026-10-14 (C1): "
            "DISP-001's 4.3 km deviation is escalated, not ruled."
        ),
    },
}

# The clause each index of the two lists above must be, so that a file whose
# clauses were reordered fails here rather than silently pinning another clause.
THE_CLAUSE_AT_EACH_INDEX = {
    "no_show.json": {0: "POL-NS-21"},
    "route_deviation.json": {3: "POL-RD-24", 4: "POL-RD-25"},
}

# The version-8 sets, as ``(name, cases, version-7 set whose key it replaces)``.
# Both are development data the team tunes against, and both reuse the version-7
# case files: there is no ``data/external/dev-v8/`` and no
# ``data/external/ryde-v8/``.
V8_SETS = (
    ("dev-v8", 40, "dev-v7"),
    ("ryde-v8", 2, "ryde-v7"),
)

# The entries the 2 km limb moves, per set, with the deviation each one's trip
# record records. Written down rather than read off the keys, so a derivation
# that moved one entry too many or too few fails here instead of agreeing with
# itself.
V8_MOVED = {
    "dev-v8": {5010: "2.3", 5015: "2.6"},
    "ryde-v8": {902: "4.3"},
}

# Every other registered set's case count, as it stood before version 8 existed.
# ``registered()`` reads the set's own ``case_root`` now, and for every one of
# these the root is the directory named after the set, so not one count moves.
EXISTING_SET_COUNTS = {
    "corpus": 29,
    "codex": 15,
    "dev-v2": 80,
    "dev-v2-ext": 120,
    "ryde-v3": 1,
    "inject-v1": 12,
    "pii-v1": 8,
    "collusion-v1": 8,
    "wild": 64,
    "wild-v2": 20,
    "sealed-v1": 24,
    "sealed-v2": 12,
    "sealed-v3": 30,
    "sealed-v4": 30,
    "dev-v7": 40,
    "ryde-v7": 2,
}

# The four graded fields of an escalated entry, and the clause it gains.
ESCALATE = "ESCALATE"
AI_LIMIT_CLAUSE = "POL-RD-25"


def read(name, version):
    """One policy file of one version, parsed."""
    directory = POLICY_V7_DIR if version == VERSION_SEVEN else POLICY_V8_DIR
    return json.loads((directory / name).read_text(encoding="utf-8"))


def differing_paths(left, right, path=""):
    """Every path at which two parsed documents differ, with both values.

    Descends into mappings by key and into lists of equal length by index, so a
    difference inside a clause is reported as ``clauses[4].rule`` rather than as
    the whole ``clauses`` list. A list that changed length is reported as the
    list itself, because there is no index pair to compare.
    """
    found = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in list(left) + [key for key in right if key not in left]:
            here = "{0}.{1}".format(path, key) if path else key
            if key not in left:
                found.append((here, "<absent>", right[key]))
            elif key not in right:
                found.append((here, left[key], "<absent>"))
            else:
                found += differing_paths(left[key], right[key], here)
    elif (
        isinstance(left, list)
        and isinstance(right, list)
        and len(left) == len(right)
    ):
        for index, (one, other) in enumerate(zip(left, right)):
            found += differing_paths(one, other, "{0}[{1}]".format(path, index))
    elif left != right:
        found.append((path, left, right))
    return found


def the_entry(key, case_no):
    """One entry of a loaded key, by case number."""
    for entry in key:
        if entry["case_no"] == case_no:
            return entry
    raise AssertionError("case {0} is not in this key".format(case_no))


class VersionEightIsVersionSevenPlusTwoAnswersTests(unittest.TestCase):
    """The three version-8 files differ from version 7's at fifteen paths, and nowhere else."""

    def test_the_differing_paths_are_exactly_the_ones_version_8_names(self):
        total = 0
        for name in V8_FILES:
            with self.subTest(file=name):
                found = differing_paths(read(name, VERSION_SEVEN), read(name, VERSION_EIGHT))
                expected = V8_DIFFERENCES[name]
                self.assertEqual(sorted(expected), sorted(path for path, _o, _n in found))
                for path, _old, new in found:
                    self.assertEqual(expected[path], new, path)
                total += len(found)
        self.assertEqual(15, total, "the version-8 diff is not fifteen paths")

    def test_the_clause_at_each_pinned_index_is_the_clause_version_8_names(self):
        for name, by_index in sorted(THE_CLAUSE_AT_EACH_INDEX.items()):
            clauses = read(name, VERSION_EIGHT)["clauses"]
            for index, clause_id in sorted(by_index.items()):
                with self.subTest(file=name, index=index):
                    self.assertEqual(clause_id, clauses[index]["id"])

    def test_the_key_order_of_every_object_is_unchanged(self):
        """No key was added, removed or moved, but the one version 8 adds.

        A JSON object's order is part of the file a reader reviews, so a
        re-serialisation that happened to sort the keys would be a change to the
        policy text. The one difference allowed is
        ``thresholds.free_wait_starts_from``, which version 8 places right after
        ``thresholds.free_wait_starts`` as its own text says.
        """
        added = ("no_show.json", "thresholds", "free_wait_starts_from")

        def expected_keys(name, path, left):
            keys = list(left)
            if (name, path) == (added[0], "." + added[1]):
                keys.insert(keys.index("free_wait_starts") + 1, added[2])
            return keys

        def walk(left, right, name, path=""):
            if isinstance(left, dict) and isinstance(right, dict):
                self.assertEqual(
                    expected_keys(name, path, left),
                    list(right),
                    "{0}{1}".format(name, path),
                )
                for key in left:
                    walk(left[key], right[key], name, path + "." + key)
            elif isinstance(left, list) and isinstance(right, list):
                self.assertEqual(len(left), len(right), "{0}{1}".format(name, path))
                for index, (one, other) in enumerate(zip(left, right)):
                    walk(one, other, name, "{0}[{1}]".format(path, index))

        for name in V8_FILES:
            with self.subTest(file=name):
                walk(read(name, VERSION_SEVEN), read(name, VERSION_EIGHT), name)

    def test_the_amendments_readme_is_version_sevens(self):
        self.assertEqual(
            (POLICY_V7_DIR / "amendments" / "README.md").read_bytes(),
            (POLICY_V8_DIR / "amendments" / "README.md").read_bytes(),
        )

    def test_the_three_files_carry_the_version_eight_metadata(self):
        for name in V8_FILES:
            document = read(name, VERSION_EIGHT)
            with self.subTest(file=name):
                self.assertEqual("8.0.0", document["version"])
                self.assertEqual("2026-10-14", document["last_reviewed"])


class VersionEightIsItsOwnBaseTests(unittest.TestCase):
    """Version 8 is a separate base, and versions 1 to 7 read what they read."""

    def test_the_registry_names_base_eight(self):
        self.assertEqual({3: "v3", 7: "v7", 8: "v8"}, policy_versions.SEPARATE_BASE_VERSIONS)

    def test_base_eight_owns_version_eight_and_up(self):
        for version in (8, 9, 12):
            with self.subTest(version=version):
                self.assertEqual(8, policy_versions.separate_base_of(version))
                self.assertEqual(8, policy_versions.owner_of_version(version))
        self.assertEqual(7, policy_versions.separate_base_of(7))
        self.assertEqual(7, policy_versions.owner_of_version(7))

    def test_the_highest_available_version_is_eight(self):
        self.assertEqual(8, policy_versions.highest_available_version())

    def test_each_base_reads_its_own_directory(self):
        self.assertEqual(POLICY_V8_DIR, policy_versions.base_directory(8))
        self.assertEqual(POLICY_V7_DIR, policy_versions.base_directory(7))
        self.assertEqual(PROJECT_ROOT / "policy" / "v3", policy_versions.base_directory(3))

    def test_the_loaded_version_seven_pair_still_reads_policy_v7(self):
        for category in ("ROUTE_DEVIATION", "NO_SHOW_CHARGE"):
            with self.subTest(category=category):
                loaded = loader.load_policies(category, VERSION_SEVEN)
                self.assertEqual("7.0.0", loaded["general"]["version"])
                self.assertEqual("7.0.0", loaded["category"]["version"])

    def test_the_loaded_version_eight_pair_reads_policy_v8(self):
        for category in ("ROUTE_DEVIATION", "NO_SHOW_CHARGE"):
            with self.subTest(category=category):
                loaded = loader.load_policies(category, VERSION_EIGHT)
                self.assertEqual("8.0.0", loaded["general"]["version"])
                self.assertEqual("8.0.0", loaded["category"]["version"])

    def test_a_version_eight_ceiling_is_the_policys_own(self):
        thresholds = loader.load_policies("ROUTE_DEVIATION", VERSION_EIGHT)["category"][
            "thresholds"
        ]
        self.assertIs(True, thresholds["ai_ruling_max_deviation_applied"])
        self.assertEqual(Decimal("2.0"), Decimal(thresholds["ai_ruling_max_deviation_km"]))


class TheVersionEightSetsTests(unittest.TestCase):
    """``dev-v8`` and ``ryde-v8`` reuse the version-7 cases and move only the key."""

    def test_both_are_registered_by_name_and_neither_is_sealed(self):
        for name, count, source in V8_SETS:
            with self.subTest(set=name):
                self.assertIn(name, sets.BY_NAME)
                development_set = sets.BY_NAME[name]
                self.assertEqual(name, development_set.name)
                self.assertFalse(development_set.sealed)
                self.assertEqual(name, development_set.runs_subdir)
                self.assertEqual(count, len(development_set.cases))
                self.assertEqual(sets.BY_NAME[source].case_root, development_set.case_root)

    def test_the_case_root_is_the_version_seven_directory(self):
        self.assertEqual(
            PROJECT_ROOT / "data" / "external" / "dev-v7", sets.DEV_V8.case_root
        )
        self.assertEqual(
            PROJECT_ROOT / "data" / "external" / "ryde-v7", sets.RYDE_V8.case_root
        )
        for name in ("dev-v8", "ryde-v8"):
            with self.subTest(set=name):
                self.assertFalse(
                    (PROJECT_ROOT / "data" / "external" / name).exists(),
                    "{0} should reuse the version-7 case files".format(name),
                )

    def test_the_key_is_the_version_eight_one(self):
        self.assertEqual(
            PROJECT_ROOT / "eval" / "answers" / "dev-v8" / "ground_truth.json",
            sets.DEV_V8.key_path,
        )
        self.assertEqual(
            PROJECT_ROOT / "eval" / "answers" / "ryde-v8" / "ground_truth.json",
            sets.RYDE_V8.key_path,
        )

    def test_both_are_at_version_eight_on_base_eight(self):
        for name, _count, _source in V8_SETS:
            development_set = sets.BY_NAME[name]
            with self.subTest(set=name):
                self.assertEqual(8, development_set.policy_version)
                self.assertEqual(8, development_set.policy_base)
                self.assertEqual(8, sets.resolved_policy_version(development_set, None))
                self.assertTrue(sets.version_moves_the_run(development_set, None))

    def test_they_are_named_sets_and_never_development_ones(self):
        for name, _count, _source in V8_SETS:
            with self.subTest(set=name):
                self.assertIn(name, [item.name for item in sets.NAMED_SETS])
                self.assertNotIn(name, [item.name for item in sets.DEVELOPMENT_SETS])
                self.assertNotIn(name, [item.name for item in sets.ALL_SETS])
                self.assertNotIn(name, [item.name for item in sets.SEALED_SETS])
                self.assertNotIn(name, [item.name for item in sets.RERUN_SETS])
                self.assertNotIn(name, sets.DECLARED_SETS)

    def test_dev_v8_registers_the_forty_cases_dev_v7_lists(self):
        self.assertEqual(sets.BY_NAME["dev-v7"].cases, sets.BY_NAME["dev-v8"].cases)
        self.assertEqual(40, len(sets.BY_NAME["dev-v8"].cases))

    def test_ryde_v8_registers_the_two_samples_ryde_v7_lists(self):
        self.assertEqual((902, 903), tuple(sets.BY_NAME["ryde-v8"].cases))

    def test_a_version_eight_run_is_refused_with_the_version_six_prompts(self):
        self.assertIsNotNone(
            run_benchmark.mismatched_prompts_directory(VERSION_EIGHT, run_benchmark.PROMPTS_DIR)
        )

    def test_a_version_eight_run_is_run_with_the_version_seven_prompts(self):
        for name, _count, _source in V8_SETS:
            with self.subTest(set=name):
                named = sets.registered_prompts_dir(sets.BY_NAME[name])
                if not named.is_absolute():
                    named = run_benchmark.PROJECT_ROOT / named
                self.assertEqual(
                    (run_benchmark.PROJECT_ROOT / "prompts" / "v2").resolve(),
                    named.resolve(),
                )

    def test_registered_gives_every_existing_set_the_cases_it_had(self):
        """The change reads a set's ``case_root``; no other set's count moves."""
        for name, count in sorted(EXISTING_SET_COUNTS.items()):
            with self.subTest(set=name):
                self.assertIn(name, sets.BY_NAME)
                self.assertEqual(count, len(sets.BY_NAME[name].cases))
        # And every one of them still has its own directory as its root.
        for name in sorted(EXISTING_SET_COUNTS):
            development_set = sets.BY_NAME[name]
            with self.subTest(set=name):
                if development_set.case_root is None:
                    continue
                self.assertEqual(name, development_set.case_root.name)


class TheVersionEightKeysTests(unittest.TestCase):
    """The two keys are the version-7 keys with exactly the entries the 2 km limb moves."""

    def test_the_derivation_is_clean_for_both_sets(self):
        """What ``--check`` compares, compared here without printing a report."""
        ceiling = derive_v8_keys.the_ceiling()
        for name, _count, _source in V8_SETS:
            source_key, case_root, destination = next(
                row[1:] for row in derive_v8_keys.SETS if row[0] == name
            )
            with self.subTest(set=name):
                entries, _moved = derive_v8_keys.derived_key(
                    json.loads(source_key.read_text(encoding="utf-8")), case_root, ceiling
                )
                self.assertEqual(
                    destination.read_text(encoding="utf-8"),
                    derive_v8_keys.render(entries),
                )

    def test_the_derivation_reports_the_moved_entries(self):
        ceiling = derive_v8_keys.the_ceiling()
        for name, _count, _source in V8_SETS:
            source_key, case_root, _destination = next(
                row[1:] for row in derive_v8_keys.SETS if row[0] == name
            )
            with self.subTest(set=name):
                _entries, moved = derive_v8_keys.derived_key(
                    json.loads(source_key.read_text(encoding="utf-8")), case_root, ceiling
                )
                self.assertEqual(
                    sorted(V8_MOVED[name]), sorted(case_no for case_no, _o, _n in moved)
                )
                for _case_no, old, new in moved:
                    self.assertEqual("PARTIAL_REFUND", old)
                    self.assertEqual(ESCALATE, new)

    def test_the_derivations_table_is_the_registration(self):
        """The tool's own paths are the ones ``eval/development_sets.py`` registers."""
        table = {row[0]: row[1:] for row in derive_v8_keys.SETS}
        self.assertEqual({"dev-v8", "ryde-v8"}, set(table))
        for name, count, source in V8_SETS:
            source_key, case_root, destination = table[name]
            with self.subTest(set=name):
                self.assertEqual(count, len(sets.BY_NAME[name].cases))
                self.assertEqual(sets.BY_NAME[name].case_root, case_root)
                self.assertEqual(sets.BY_NAME[name].key_path, destination)
                self.assertEqual(sets.BY_NAME[source].key_path, source_key)

    def test_each_key_moves_exactly_the_entries_the_limb_moves(self):
        for name, _count, source in V8_SETS:
            with self.subTest(set=name):
                source_key = json.loads(
                    sets.BY_NAME[source].key_path.read_text(encoding="utf-8")
                )
                version_eight = json.loads(
                    sets.BY_NAME[name].key_path.read_text(encoding="utf-8")
                )
                self.assertEqual(len(source_key), len(version_eight))
                moved = [
                    other["case_no"]
                    for one, other in zip(source_key, version_eight)
                    if one != other
                ]
                self.assertEqual(sorted(V8_MOVED[name]), sorted(moved))

    def test_each_moved_entry_is_an_escalation_with_no_amount(self):
        for name, _count, _source in V8_SETS:
            key = json.loads(sets.BY_NAME[name].key_path.read_text(encoding="utf-8"))
            for case_no, deviation in sorted(V8_MOVED[name].items()):
                with self.subTest(set=name, case=case_no):
                    truth = the_entry(key, case_no)["ground_truth"]
                    self.assertEqual(ESCALATE, truth["expected_ruling"])
                    self.assertIsNone(truth["expected_amount_sgd"])
                    self.assertIsNone(truth["expected_driver_compensation_sgd"])
                    self.assertEqual([], truth["expected_referrals"])
                    self.assertIn(AI_LIMIT_CLAUSE, truth["governing_clauses"])
                    self.assertIn(
                        "the deviation is {0} km, over 2 km".format(deviation),
                        truth["rationale"],
                    )

    def test_every_unmoved_entry_is_copied_byte_for_byte(self):
        for name, _count, source in V8_SETS:
            source_key = json.loads(
                sets.BY_NAME[source].key_path.read_text(encoding="utf-8")
            )
            version_eight = json.loads(
                sets.BY_NAME[name].key_path.read_text(encoding="utf-8")
            )
            moved = set(V8_MOVED[name])
            for one, other in zip(source_key, version_eight):
                if one["case_no"] in moved:
                    continue
                with self.subTest(set=name, case=one["case_no"]):
                    self.assertEqual(one, other)

    def test_the_no_show_sample_is_unchanged(self):
        """903's answer never depended on either limb, so it is the version-7 one."""
        key = json.loads(sets.BY_NAME["ryde-v8"].key_path.read_text(encoding="utf-8"))
        truth = the_entry(key, 903)["ground_truth"]
        self.assertEqual("DRIVER_COMPENSATION", truth["expected_ruling"])
        self.assertEqual(Decimal("5.00"), Decimal(str(truth["expected_amount_sgd"])))
        self.assertEqual(
            Decimal("5.00"), Decimal(str(truth["expected_driver_compensation_sgd"]))
        )

    def test_the_two_km_limb_is_strict(self):
        """A deviation of exactly the ceiling is still the AI's.

        The comparison is taken in ``Decimal`` over the recorded figures, so the
        test is on the rule rather than on a float: 2.0 is not over 2.0, and 2.0001
        is. Nothing in either set sits on the line, which is why the counts above
        are what they are.
        """
        ceiling = derive_v8_keys.the_ceiling()
        self.assertEqual(Decimal("2.0"), ceiling)
        self.assertFalse(Decimal("2.0") > ceiling)
        self.assertTrue(Decimal("2.0001") > ceiling)


if __name__ == "__main__":
    unittest.main(verbosity=2)
