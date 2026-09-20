"""Tests for ``tribunal.loader``.

Every test asserts against the real files under ``data/`` and ``policy/``.
There are no fixtures: no case content, policy content or expected values are
copied into this file. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import loader  # noqa: E402

INDEX_PATH = PROJECT_ROOT / "data" / "index.json"


def manifest_entries():
    """The real manifest, read straight from data/index.json."""
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def policy_file(name):
    """One real policy file, read straight from policy/."""
    with (PROJECT_ROOT / "policy" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def walk(node):
    """Yield every key found anywhere inside nested dicts and lists."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


class RequiredContractTests(unittest.TestCase):
    """The nine tests named in the task brief."""

    # 1. case 104
    def test_case_104_keeps_both_traffic_advisories(self):
        """Case 104 holds two TRAFFIC_ADVISORY artifacts, so it has 8, not 7."""
        case = loader.load_case(104)
        self.assertEqual(len(case["evidence"]), 8)

        advisories = [
            artifact["evidence_id"]
            for artifact in case["evidence"]
            if artifact["evidence_type"] == "TRAFFIC_ADVISORY"
        ]
        self.assertEqual(len(advisories), 2)
        self.assertIn("EV-ADVIS-00104-01", advisories)
        self.assertIn("EV-ADVIS-00104-02", advisories)

        ids = [artifact["evidence_id"] for artifact in case["evidence"]]
        self.assertEqual(len(ids), len(set(ids)), "artifact ids must stay distinct")

    # 2. case 213
    def test_case_213_has_three_artifacts_without_payload(self):
        """Case 213 has exactly 3 null-payload artifacts, each keeping its id."""
        case = loader.load_case(213)

        missing = [a["evidence_id"] for a in case["evidence"] if a["payload"] is None]
        self.assertEqual(len(missing), 3)
        self.assertEqual(
            sorted(missing),
            ["EV-ADVIS-00213-01", "EV-CHAT-00213", "EV-GPS-00213"],
        )

        for artifact in case["evidence"]:
            self.assertIn("payload", artifact)
            self.assertTrue(artifact["evidence_id"])

        self.assertEqual(
            sorted(loader.missing_payload_ids(case)),
            ["EV-ADVIS-00213-01", "EV-CHAT-00213", "EV-GPS-00213"],
        )

    # 3. case 103
    def test_case_103_null_counterparty_statement_loads(self):
        """Case 103 has a null counterparty_statement and still loads."""
        case = loader.load_case(103)
        self.assertIsNone(case["dispute"]["counterparty_statement"])
        self.assertEqual(case["case_no"], 103)
        self.assertEqual(len(case["evidence"]), 7)

    # 4. all 29 cases
    def test_all_29_cases_load_to_204_artifacts(self):
        """All 29 manifest cases load; the artifact total across them is 204."""
        entries = manifest_entries()
        self.assertEqual(len(entries), 29)

        total = 0
        for entry in entries:
            case = loader.load_case(entry["case_no"])
            self.assertEqual(case["case_no"], entry["case_no"])
            self.assertEqual(set(loader.CASE_KEYS).issubset(case), True)
            total += len(case["evidence"])
        self.assertEqual(total, 204)

    # 5. no real case; a case number that does not exist
    def test_unknown_case_no_raises(self):
        """A case number that is not in the manifest raises, not returns None."""
        with self.assertRaises(loader.CaseNotFoundError):
            loader.load_case(99999)
        with self.assertRaises(loader.LoaderError):
            loader.load_case(99999)

    # 6. no real case; an unsupported category value
    def test_unsupported_category_raises(self):
        """An unsupported category raises instead of defaulting to a policy."""
        with self.assertRaises(loader.UnsupportedCategoryError):
            loader.load_policies("FARE_DISPUTE")
        with self.assertRaises(loader.LoaderError):
            loader.load_policies("ROUTE_DEVIATION_EXTRA")

        # The two real categories still resolve.
        self.assertIn("general", loader.load_policies("ROUTE_DEVIATION"))
        self.assertIn("general", loader.load_policies("NO_SHOW_CHARGE"))

    # 7. case 104
    def test_bundle_is_byte_identical_across_runs(self):
        """Building the same bundle twice yields identical bytes and digest."""
        canonical_a, digest_a = loader.bundle_digest(loader.build_bundle(104))
        canonical_b, digest_b = loader.bundle_digest(loader.build_bundle(104))

        self.assertEqual(canonical_a, canonical_b)
        self.assertEqual(digest_a, digest_b)
        self.assertEqual(len(digest_a), 64)

    # 8. all 29 cases
    def test_no_bundle_contains_forbidden_keys(self):
        """No bundle for any of the 29 cases contains a forbidden key, at any depth."""
        for entry in manifest_entries():
            bundle = loader.build_bundle(entry["case_no"])
            present = sorted(set(walk(bundle)) & set(loader.FORBIDDEN_KEYS))
            self.assertEqual(
                present, [], "case {0} leaked {1}".format(entry["case_no"], present)
            )

    # 9. case 101 (ROUTE_DEVIATION) and case 201 (NO_SHOW_CHARGE)
    def test_bundle_carries_the_arithmetic_constants(self):
        """A route-deviation bundle carries fare_model; a no-show bundle carries fee_schedule."""
        route_bundle = loader.build_bundle(101)
        self.assertEqual(route_bundle["case"]["dispute"]["category"], "ROUTE_DEVIATION")
        self.assertEqual(
            route_bundle["policies"]["category"]["fare_model"],
            policy_file("route_deviation.json")["fare_model"],
        )

        no_show_bundle = loader.build_bundle(201)
        self.assertEqual(no_show_bundle["case"]["dispute"]["category"], "NO_SHOW_CHARGE")
        self.assertEqual(
            no_show_bundle["policies"]["category"]["fee_schedule"],
            policy_file("no_show.json")["fee_schedule"],
        )

        # Whole policy files travel, not just the clauses.
        self.assertEqual(
            route_bundle["policies"]["general"], policy_file("general.json")
        )
        self.assertEqual(
            no_show_bundle["policies"]["general"]["policy_id"],
            policy_file("general.json")["policy_id"],
        )


class AdditionalContractTests(unittest.TestCase):
    """Extra checks that lock in the remaining binding rules."""

    # case 104
    def test_bundle_contains_only_case_and_policies(self):
        """The bundle is exactly the case plus the policies - nothing else."""
        bundle = loader.build_bundle(104)
        self.assertEqual(set(bundle), {"case", "policies"})
        self.assertEqual(set(bundle["policies"]), {"general", "category"})
        self.assertEqual(set(bundle["case"]), set(loader.CASE_KEYS))

    # case 104
    def test_artifacts_index_by_evidence_id_not_type(self):
        """Case 104's two advisories must be two distinct index entries."""
        case = loader.load_case(104)
        index = loader.index_artifacts(case)

        self.assertEqual(len(index), len(case["evidence"]))
        self.assertIs(index["EV-ADVIS-00104-01"], case["evidence"][6])
        self.assertIs(index["EV-ADVIS-00104-02"], case["evidence"][7])
        self.assertNotEqual(index["EV-ADVIS-00104-01"], index["EV-ADVIS-00104-02"])
        self.assertEqual(
            index["EV-ADVIS-00104-01"]["evidence_type"],
            index["EV-ADVIS-00104-02"]["evidence_type"],
        )

    # all 29 cases
    def test_issue_details_is_never_required(self):
        """issue_details is optional; reading it never raises for any artifact."""
        seen_with, seen_without = 0, 0
        for entry in manifest_entries():
            case = loader.load_case(entry["case_no"])
            for artifact in case["evidence"]:
                details = loader.issue_details_of(artifact)
                self.assertIsInstance(details, list)
                if "issue_details" in artifact["admissibility"]:
                    seen_with += 1
                else:
                    seen_without += 1
        self.assertEqual(seen_with, 45)
        self.assertEqual(seen_without, 159)

    # all 29 cases
    def test_manifest_file_paths_are_relative_to_data(self):
        """Every manifest file resolves under data/ and matches its case number."""
        for entry in manifest_entries():
            resolved = (PROJECT_ROOT / "data" / entry["file"]).resolve()
            self.assertTrue(resolved.is_file(), entry["file"])
            self.assertTrue(resolved.is_relative_to((PROJECT_ROOT / "data").resolve()))
            self.assertEqual(resolved.stem, "case-{0:05d}".format(entry["case_no"]))

    # case 104
    def test_bundle_serialisation_matches_the_contract(self):
        """Serialisation uses ensure_ascii=False, sort_keys=True, compact separators."""
        canonical, digest = loader.bundle_digest(loader.build_bundle(104))
        expected = json.dumps(
            loader.build_bundle(104),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertEqual(canonical, expected)
        self.assertEqual(digest, loader.bundle_digest(loader.build_bundle(104))[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
