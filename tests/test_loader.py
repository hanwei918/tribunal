"""Tests for ``tribunal.loader``.

Every test asserts against the real files under ``data/`` and ``policy/``.
There are no fixtures: no case content, policy content or expected values are
copied into this file. Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, loader, money  # noqa: E402

INDEX_PATH = PROJECT_ROOT / "data" / "index.json"


def manifest_entries():
    """The real manifest, read straight from data/index.json."""
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def policy_file(name):
    """One real policy file, read straight from policy/.

    Read with ``parse_float=Decimal``, the same way the loader reads the corpus,
    so a policy number compares like for like with the value the loader returns.
    """
    with (PROJECT_ROOT / "policy" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


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
        """Serialisation uses ensure_ascii=False, sort_keys=True, compact separators.

        The bundle now carries ``Decimal`` amounts, which ``json.dumps`` cannot
        write at all. The contract's parameters are therefore asserted on a
        Decimal-free projection, and the canonical bytes are checked by parsing
        them back: the same structure, with the Decimals intact.
        """
        bundle = loader.build_bundle(104)
        canonical, digest = loader.bundle_digest(bundle)

        def without_decimals(node):
            if isinstance(node, Decimal):
                return str(node)
            if isinstance(node, dict):
                return {key: without_decimals(value) for key, value in node.items()}
            if isinstance(node, list):
                return [without_decimals(value) for value in node]
            return node

        projection = without_decimals(bundle)
        expected = json.dumps(
            projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        # With no Decimals left, money.dumps_canonical is exactly that call.
        self.assertEqual(money.dumps_canonical(projection), expected)

        # The canonical bytes parse back to the bundle itself, Decimals intact.
        self.assertEqual(json.loads(canonical, parse_float=Decimal), bundle)
        self.assertEqual(digest, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        self.assertEqual(digest, loader.bundle_digest(loader.build_bundle(104))[1])


class ManifestCrossCheckTests(unittest.TestCase):
    """Defect 1: every manifest field that also lives in the case file must agree."""

    def test_1_all_29_cases_pass_the_extended_cross_check(self):
        entries = manifest_entries()
        self.assertEqual(len(entries), 29)
        for entry in entries:
            case = loader.load_case(entry["case_no"])
            for field in loader.MANIFEST_DISPUTE_FIELDS:
                self.assertEqual(
                    entry[field],
                    case["dispute"][field],
                    "case {0} field {1}".format(entry["case_no"], field),
                )

    def test_2_a_disagreeing_manifest_field_raises_and_names_it(self):
        """The message names the field, the manifest value and the file value."""
        entry = loader._manifest_entry(101)
        case = loader.load_case(101)

        for field in ("dispute_id", "trip_id", "category"):
            disagreeing = "MISMATCH-{0}".format(field)
            broken = dict(entry, **{field: disagreeing})

            with self.assertRaises(loader.ManifestMismatchError) as caught:
                loader._check_manifest_agreement(broken, case, 101)

            message = str(caught.exception)
            self.assertIn(field, message)
            self.assertIn(repr(disagreeing), message)
            self.assertIn(repr(case["dispute"][field]), message)

    def test_2b_the_agreeing_entry_does_not_raise(self):
        entry = loader._manifest_entry(101)
        case = loader.load_case(101)
        loader._check_manifest_agreement(entry, case, 101)


class PathRestrictionTests(unittest.TestCase):
    """Defect 2: a manifest `file` may not resolve outside data/cases/."""

    OUTSIDE = (
        "answers/answers.json",
        "../answers/answers.json",
        "PUBLIC-CONTRACT.md",
        "../PUBLIC-CONTRACT.md",
        "cases/../../policy/no_show.json",
        "index.json",
    )

    def test_3_a_path_reaching_outside_data_cases_raises(self):
        for relative in self.OUTSIDE:
            with self.assertRaises(loader.ManifestMismatchError) as caught:
                loader._case_path({"file": relative}, 101)
            self.assertIn("data/cases/", str(caught.exception))

    def test_3b_the_legitimate_path_is_still_allowed(self):
        path = loader._case_path({"file": "cases/case-00101.json"}, 101)
        self.assertTrue(path.is_relative_to((PROJECT_ROOT / "data" / "cases").resolve()))
        self.assertTrue(path.is_file())

    def test_3c_every_real_manifest_entry_resolves_under_data_cases(self):
        cases_root = (PROJECT_ROOT / "data" / "cases").resolve()
        for entry in manifest_entries():
            path = loader._case_path(entry, entry["case_no"])
            self.assertTrue(path.is_relative_to(cases_root), entry["file"])


class DecimalParseBoundaryTests(unittest.TestCase):
    """Defect 3: money arrives as Decimal; integers stay int."""

    @classmethod
    def setUpClass(cls):
        cls.case = loader.load_case(208)

    def _payload(self, evidence_type):
        return next(
            a["payload"] for a in self.case["evidence"] if a["evidence_type"] == evidence_type
        )

    def test_4_total_charged_is_a_decimal_not_a_float(self):
        total = self._payload("FARE_BREAKDOWN")["total_charged"]
        self.assertIsInstance(total, Decimal)
        self.assertNotIsInstance(total, float)
        self.assertEqual(total, Decimal("8.0"))
        self.assertEqual(str(total), "8.0", "the literal as written must be preserved")

    def test_5_amount_contested_is_a_decimal(self):
        amount = self.case["dispute"]["amount_contested_sgd"]
        self.assertIsInstance(amount, Decimal)
        self.assertNotIsInstance(amount, float)

    def test_5b_every_decimal_written_in_the_case_file_survives_as_a_decimal(self):
        """Nothing with a decimal point comes back as a float anywhere."""
        floats = []

        def visit(node, path):
            if isinstance(node, float):
                floats.append(path)
            elif isinstance(node, dict):
                for key, value in node.items():
                    visit(value, "{0}.{1}".format(path, key))
            elif isinstance(node, list):
                for position, value in enumerate(node):
                    visit(value, "{0}[{1}]".format(path, position))

        visit(self.case, "case")
        self.assertEqual(floats, [], "floats found at: {0}".format(floats[:5]))

    def test_7_an_integer_json_value_stays_an_int(self):
        self.assertIsInstance(self.case["case_no"], int)
        self.assertNotIsInstance(self.case["case_no"], Decimal)

        point_count = self._payload("GPS_TRACE")["point_count"]
        self.assertIsInstance(point_count, int)
        self.assertNotIsInstance(point_count, Decimal)

        account_age = self._payload("RIDER_PROFILE")["account_age_days"]
        self.assertIsInstance(account_age, int)
        self.assertNotIsInstance(account_age, Decimal)


class DecimalSerialisationStabilityTests(unittest.TestCase):
    """Test 6: Decimals present, canonical bytes and digests still reproducible."""

    def test_6_brief_bytes_and_digest_are_stable_with_decimals_present(self):
        first_brief = brief.build_brief(208)
        second_brief = brief.build_brief(208)

        first = brief.brief_digest(first_brief)
        second = brief.brief_digest(second_brief)

        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])
        self.assertEqual(len(first[1]), 64)

        # Decimals really are present in the object being serialised.
        decimals = []

        def visit(node, path):
            if isinstance(node, Decimal):
                decimals.append(path)
            elif isinstance(node, dict):
                for key, value in node.items():
                    visit(value, "{0}.{1}".format(path, key))
            elif isinstance(node, list):
                for position, value in enumerate(node):
                    visit(value, "{0}[{1}]".format(path, position))

        visit(first_brief, "brief")
        self.assertTrue(decimals, "expected the brief to carry Decimals")

        # And they are written as JSON numbers, not strings.
        self.assertIn('"total_charged":8.0', first[0])
        self.assertNotIn('"total_charged":"8.0"', first[0])

    def test_6b_bundle_digest_is_stable_with_decimals_present(self):
        first = loader.bundle_digest(loader.build_bundle(208))
        second = loader.bundle_digest(loader.build_bundle(208))
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])

    def test_6c_every_literal_written_in_the_corpus_is_the_literal_serialised(self):
        """Trailing zeros survive, which is the whole point of the Decimal fix.

        ``route_deviation.json`` writes its constants as 0.70, 3.80, 6.00, 8.00,
        0.50 and 0.80; ``general.json`` writes its own ``confidence_floor`` as
        0.7. Float parsing collapsed the first six onto the seventh — it could
        not tell 0.70 from 0.7.
        """
        bundle = loader.build_bundle(104)
        canonical = loader.bundle_digest(bundle)[0]

        for literal in (
            '"confidence_floor":0.70',
            '"base_fare":3.80',
            '"platform_fee":0.80',
            '"de_minimis_refund":0.50',
            '"peak_sgd":8.00',
            '"off_peak_sgd":6.00',
        ):
            self.assertIn(literal, canonical)
        # The literal with no trailing zero is left exactly as it was written.
        self.assertIn('"confidence_floor":0.7,', canonical)

        def to_float(node):
            if isinstance(node, Decimal):
                return float(node)
            if isinstance(node, dict):
                return {key: to_float(value) for key, value in node.items()}
            if isinstance(node, list):
                return [to_float(value) for value in node]
            return node

        lossy = json.dumps(
            to_float(bundle), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        self.assertNotIn('"confidence_floor":0.70', lossy)
        self.assertNotEqual(lossy, canonical)


if __name__ == "__main__":
    unittest.main(verbosity=2)
