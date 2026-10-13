"""Tests for policy version 7, Ryde's own Dispute Resolution Policy v2.1.

Version 7 is a **separate base**, like version 3: ``policy/v7/`` holds Ryde's
``general.json``, ``route_deviation.json`` and ``no_show.json``, byte for byte as
the policy owner reviews them, and version 7 is those three files and nothing
else. Nothing at versions 1-6 may move -- version 6's own loaded pair and
``prompts/v1/`` are pinned here, and the two sealed runs made at version 6 must
stay reproducible byte for byte.

The clauses are version 7's own. Their ids start at **21**, so that no version-6
id is reused for a different rule; the three exceptions keep the ids and the
roles they had (**POL-GEN-01** party profiles are context, **POL-GEN-02**
admissibility and disclosure, **POL-GEN-03** the five rulings). The structured
thresholds are v2.1's numbers, and each of the three files is pinned by sha256.

Nothing here reaches a real model, and nothing here reads a sealed root.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import run_benchmark as runner  # noqa: E402
from tribunal import loader, money  # noqa: E402

POLICY_V7_DIR = PROJECT_ROOT / "policy" / "v7"
PROMPTS_V1 = PROJECT_ROOT / "prompts" / "v1"
PROMPTS_V2 = PROJECT_ROOT / "prompts" / "v2"

CATEGORIES = ("ROUTE_DEVIATION", "NO_SHOW_CHARGE")

# The nine keys every version-7 clause carries: the eight fields every clause
# carries, plus ``sources`` -- the provenance key the version-7 files keep, which
# ``brief.py`` drops before the policies reach an agent.
CLAUSE_KEYS = {
    "id",
    "title",
    "category",
    "rule",
    "requires",
    "licenses",
    "favours",
    "notes",
    "sources",
}

# The five ruling values POL-GEN-03 licenses, and the whole vocabulary a
# ``licenses`` list may draw on.
RULINGS = {
    "FULL_REFUND",
    "PARTIAL_REFUND",
    "NO_ACTION",
    "DRIVER_COMPENSATION",
    "ESCALATE",
}

# The three clause ids version 7 keeps from version 6, with the roles they had.
KEPT_IDS = {"POL-GEN-01", "POL-GEN-02", "POL-GEN-03"}

# The three version-7 policy files, by sha256, exactly as ``tmp/v7/policy/``
# shipped them. They are the policy text the policy owner reviews, so a
# reformat, a re-key or a re-word moves one of these.
#
# ``route_deviation.json`` and ``no_show.json`` were re-copied byte for byte on
# 2026-10-13 in the evening, each gaining one structured field and no clause
# text: C18's ``thresholds.traffic_justification_types`` (which recorded
# advisory types each of POL-RD-23's three kinds admits) and C16's amended
# ``arrival_test.accuracy_filter_applies`` (the accuracy filter reaches only a
# fix that reports an accuracy). ``general.json`` is unchanged.
V7_FILE_SHA256 = {
    "general.json": "767f01d69f0bac8ac0cdb9f834d149f048d6b2b68fc54419461db06665b85d93",
    "route_deviation.json": "63436dd217750304087185f752f8fef4c1dae43e32522fcd25bc2c17eb8d9315",
    "no_show.json": "e4f02dba531cdd759e3d5acbe611864c90e7c2ee4c80b6f59522b18d18e9e021",
}

# The canonical digest of ``load_policies(category, 6)`` for both categories,
# computed **before** anything in this part changed. Version 6 is what the two
# sealed runs were made at, so its loaded documents must not move.
V6_LOADED_SHA256 = {
    "ROUTE_DEVIATION": "377742d8ef9c0d0fc53da47ce687c8460dc4756f2c8282160265ee34fe6dec1c",
    "NO_SHOW_CHARGE": "1b5c4780690404e114b615a7a2d5d3a496b3ea5013e41f2fc976be3cbd1412b2",
}

# The digest of ``prompts/v1/`` as ``eval/run_benchmark.py`` computes it, which
# is the value a version-6 run records as ``prompts_sha256``. Version 6 runs
# record it over ``prompts/v1/``, so ``v1`` must not change by a byte.
PROMPTS_V1_SHA256 = "5b8510cd900aa9da58e06fd2a865f94df5ede1bdb3c73006077576411858ea61"

# The five prompt files a run reads from its prompts directory.
RUN_PROMPT_FILES = (
    "advocate.system.md",
    "judge.system.md",
    "stance.driver.md",
    "stance.rider.md",
    "verifier.system.md",
)

# A clause id, bare, as every prompt and policy spells one.
CLAUSE_ID_RE = re.compile(r"POL-[A-Z]{2,4}-\d{2}")


def version_six_ids():
    """Every clause id of version 6, over both categories."""
    ids = set()
    for category in CATEGORIES:
        loaded = loader.load_policies(category, 6)
        for part in ("general", "category"):
            for clause in loaded[part]["clauses"]:
                ids.add(clause["id"])
    return ids


def licences_outside_the_vocabulary(policies):
    """Every ``(clause id, licence)`` whose licence is not one of the five rulings.

    ``policies`` is a loaded pair, as :func:`tribunal.loader.load_policies`
    returns one -- so the control below can hand it an altered copy and the
    property below can hand it the real files, through the same check.
    """
    found = []
    for part in ("general", "category"):
        for clause in policies[part]["clauses"]:
            for licence in clause["licenses"]:
                if licence not in RULINGS:
                    found.append((clause["id"], licence))
    return sorted(found)


class VersionSevenPolicyTests(unittest.TestCase):
    """The version-7 files, their clauses, their ids and their thresholds."""

    def test_both_categories_load_at_version_seven(self):
        for category in CATEGORIES:
            with self.subTest(category=category):
                loaded = loader.load_policies(category, 7)
                self.assertEqual("7.0.0", loaded["general"]["version"])
                self.assertEqual("7.0.0", loaded["category"]["version"])
                self.assertTrue(loaded["general"]["clauses"])
                self.assertTrue(loaded["category"]["clauses"])

    def test_every_clause_carries_the_nine_keys(self):
        for category in CATEGORIES:
            loaded = loader.load_policies(category, 7)
            for part in ("general", "category"):
                for clause in loaded[part]["clauses"]:
                    with self.subTest(category=category, clause=clause.get("id")):
                        self.assertEqual(CLAUSE_KEYS, set(clause))

    def test_the_clause_ids_are_unique(self):
        for category in CATEGORIES:
            loaded = loader.load_policies(category, 7)
            ids = [clause["id"] for clause in loaded["general"]["clauses"]]
            ids += [clause["id"] for clause in loaded["category"]["clauses"]]
            with self.subTest(category=category):
                self.assertEqual(len(ids), len(set(ids)))

    def test_every_licence_is_one_of_the_five_rulings(self):
        for category in CATEGORIES:
            with self.subTest(category=category):
                self.assertEqual(
                    [],
                    licences_outside_the_vocabulary(
                        loader.load_policies(category, 7)
                    ),
                )

    def test_no_version_six_clause_id_survives_but_the_three(self):
        forbidden = version_six_ids() - KEPT_IDS
        seen = set()
        for category in CATEGORIES:
            loaded = loader.load_policies(category, 7)
            for part in ("general", "category"):
                for clause in loaded[part]["clauses"]:
                    seen.add(clause["id"])
        self.assertEqual([], sorted(seen & forbidden))
        for clause_id in sorted(KEPT_IDS):
            with self.subTest(clause=clause_id):
                self.assertIn(clause_id, seen)

    def test_every_new_clause_id_is_numbered_twenty_one_or_above(self):
        for category in CATEGORIES:
            loaded = loader.load_policies(category, 7)
            for part in ("general", "category"):
                for clause in loaded[part]["clauses"]:
                    if clause["id"] in KEPT_IDS:
                        continue
                    number = int(clause["id"].rsplit("-", 1)[1])
                    with self.subTest(clause=clause["id"]):
                        self.assertGreaterEqual(number, 21)

    def test_the_thresholds_are_v21s_numbers(self):
        general = loader.load_policies("ROUTE_DEVIATION", 7)["general"]["thresholds"]
        deviation = loader.load_policies("ROUTE_DEVIATION", 7)["category"]["thresholds"]
        no_show = loader.load_policies("NO_SHOW_CHARGE", 7)["category"]["thresholds"]

        # The value bands and the two confidence bars (v2.1 6.1, 6.3).
        self.assertEqual(Decimal("10.00"), Decimal(general["ai_final_below_sgd"]))
        self.assertEqual(Decimal("50.00"), Decimal(general["human_above_sgd"]))
        self.assertEqual(
            Decimal("0.80"), Decimal(general["confidence_required_between_sgd"])
        )
        self.assertEqual(
            Decimal("0.95"),
            Decimal(general["confidence_required_with_fraud_flag"]),
        )
        self.assertEqual(1, general["fraud_flag_minimum"])

        # The deviation tolerance and the 2 km limb (v2.1 1.3, 6.2). The limb is
        # present but **not applied**, pending Ryde's answer to C1.
        self.assertEqual(Decimal("1.0"), Decimal(deviation["tolerance_km"]))
        self.assertEqual(
            Decimal("2.0"), Decimal(deviation["ai_ruling_max_deviation_km"])
        )
        self.assertIs(False, deviation["ai_ruling_max_deviation_applied"])

        # The free wait, the fee, the goodwill credit and the repeat flag
        # (v2.1 2.1, 2.2, 2.4, 2.5).
        self.assertEqual(300, no_show["free_wait_sec"])
        self.assertIsInstance(no_show["free_wait_sec"], int)
        self.assertEqual(Decimal("5.00"), Decimal(no_show["no_show_fee_sgd"]))
        self.assertEqual(Decimal("5.00"), Decimal(no_show["goodwill_credit_sgd"]))
        self.assertEqual(3, no_show["repeat_no_show_count"])
        self.assertEqual(30, no_show["repeat_no_show_window_days"])

    def test_the_two_structured_additions_of_2026_10_13_evening_are_pinned(self):
        """C18's type map and C16's accuracy rule, read off the loaded policy.

        Both are **structured fields**, not clause prose: the type map is where
        ``brief.py`` reads POL-RD-23's kinds and the recorded types each admits,
        and the accuracy rule is where the arrival test's filter is read. Pinning
        their values here is what makes a re-worded or re-mapped file a failing
        test rather than a silent change of reading. No clause text changed.
        """
        deviation = loader.load_policies("ROUTE_DEVIATION", 7)["category"]["thresholds"]
        no_show = loader.load_policies("NO_SHOW_CHARGE", 7)["category"]

        mapped = deviation["traffic_justification_types"]
        self.assertEqual(
            ["congestion", "incident", "closure", "note"],
            list(mapped),
        )
        self.assertEqual(
            {
                "congestion": ["CONGESTION", "HEAVY_CONGESTION"],
                "incident": ["ACCIDENT", "VEHICLE_FIRE", "BREAKDOWN", "INCIDENT"],
                "closure": ["CLOSURE", "ROADWORKS"],
            },
            {
                kind: types
                for kind, types in mapped.items()
                if isinstance(types, list)
            },
        )
        self.assertEqual(
            "C18: the TRAFFIC_ADVISORY types the schema uses, mapped onto v2.1 "
            "1.1's 'traffic conditions, road closures, or congestion'. Any other "
            "type (for example KERB_RESTRICTION, TRAFFIC_FLOW) does not justify a "
            "reroute. ROADWORKS counts as a closure.",
            mapped["note"],
        )

        self.assertEqual(25, no_show["arrival_test"]["gps_accuracy_filter_m"])
        self.assertEqual(
            "only to a fix that reports an accuracy; a fix with no reported "
            "accuracy is used at its reported position (v2.1 states no accuracy "
            "rule; C16)",
            no_show["arrival_test"]["accuracy_filter_applies"],
        )

    def test_the_three_files_are_byte_for_byte_the_ones_imported(self):
        for name, digest in sorted(V7_FILE_SHA256.items()):
            with self.subTest(file=name):
                self.assertEqual(
                    digest,
                    hashlib.sha256((POLICY_V7_DIR / name).read_bytes()).hexdigest(),
                )


class VersionSixIsUntouchedTests(unittest.TestCase):
    """Version 6 is what the sealed runs were made at, so its loaded pair is pinned."""

    def test_the_loaded_version_six_pair_does_not_move(self):
        for category, digest in sorted(V6_LOADED_SHA256.items()):
            with self.subTest(category=category):
                self.assertEqual(
                    digest,
                    money.canonical_sha256(loader.load_policies(category, 6)),
                )


class VersionSevenPromptsTests(unittest.TestCase):
    """``prompts/v2/`` is the version-7 prompt set; ``prompts/v1/`` must not move."""

    def test_prompts_v1_is_byte_identical_to_mains(self):
        self.assertEqual(PROMPTS_V1_SHA256, runner.hash_directory(PROMPTS_V1))

    def test_prompts_v2_holds_the_same_prompt_files(self):
        names = sorted(path.name for path in PROMPTS_V2.iterdir() if path.is_file())
        self.assertEqual(
            sorted(path.name for path in PROMPTS_V1.iterdir() if path.is_file()),
            names,
        )
        for name in RUN_PROMPT_FILES:
            with self.subTest(file=name):
                self.assertIn(name, names)

    def test_prompts_v2_names_no_version_six_clause_but_the_three(self):
        forbidden = version_six_ids() - KEPT_IDS
        for path in sorted(PROMPTS_V2.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            found = sorted(set(CLAUSE_ID_RE.findall(text)) & forbidden)
            with self.subTest(file=path.name):
                self.assertEqual([], found)


class TheLicenceControlTests(unittest.TestCase):
    """The licences assertion is shown to fire, on a copy with one changed.

    A guard nobody has seen fail is not evidence of anything, so the same check
    the property above runs is handed a copy of ``general.json`` whose
    ``POL-GEN-21`` licenses ``REFUND`` -- a value outside the five rulings.
    """

    def test_a_copy_of_general_json_with_one_licence_changed_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "general.json"
            copy.write_bytes((POLICY_V7_DIR / "general.json").read_bytes())
            document = json.loads(copy.read_text(encoding="utf-8"))
            target = next(
                clause for clause in document["clauses"] if clause["id"] == "POL-GEN-21"
            )
            target["licenses"] = ["REFUND"]
            copy.write_text(json.dumps(document), encoding="utf-8")
            altered = json.loads(copy.read_text(encoding="utf-8"))

        loaded = {
            "general": altered,
            "category": loader.load_policies("ROUTE_DEVIATION", 7)["category"],
        }
        self.assertEqual([("POL-GEN-21", "REFUND")], licences_outside_the_vocabulary(loaded))


if __name__ == "__main__":
    unittest.main(verbosity=2)
