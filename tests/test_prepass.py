"""Tests for ``tribunal.prepass``.

Every test asserts against the real files under ``data/``. Run from the
project root with::

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

from tribunal import loader, prepass  # noqa: E402

INDEX_PATH = PROJECT_ROOT / "data" / "index.json"


def manifest_case_numbers():
    """Every case number in the real manifest."""
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return [entry["case_no"] for entry in json.load(handle)]


def all_artifacts():
    """(case_no, artifact) for every artifact in the corpus."""
    for case_no in manifest_case_numbers():
        case = loader.load_case(case_no)
        for artifact in case["evidence"]:
            yield case_no, artifact


class WeightForTests(unittest.TestCase):
    """Part 1: the derived weight arithmetic, checked against the corpus."""

    def test_weight_for_reproduces_all_non_complete_weights(self):
        """weight_for must reproduce the declared weight of all 45 artifacts."""
        checked, matched, mismatches = 0, 0, []
        for case_no, artifact in all_artifacts():
            admissibility = artifact["admissibility"]
            if admissibility["status"] == "COMPLETE":
                continue
            checked += 1
            declared = admissibility["weight_multiplier"]
            derived = prepass.weight_for(admissibility["issues"])
            if derived == declared:
                matched += 1
            else:
                mismatches.append(
                    (case_no, artifact["evidence_id"], admissibility["issues"], declared, derived)
                )

        self.assertEqual(checked, 45, "expected 45 non-COMPLETE artifacts")
        self.assertEqual(
            mismatches, [], "weight_for disagreed with the corpus on: {0}".format(mismatches)
        )
        self.assertEqual(matched, 45, "matched {0} of 45".format(matched))

    def test_weight_for_is_full_weight_for_no_issues(self):
        """An empty issue list weighs 1.0, matching all 159 COMPLETE artifacts."""
        self.assertEqual(prepass.weight_for([]), 1.0)

        complete = 0
        for _case_no, artifact in all_artifacts():
            admissibility = artifact["admissibility"]
            if admissibility["status"] != "COMPLETE":
                continue
            complete += 1
            self.assertEqual(admissibility["issues"], [])
            self.assertEqual(prepass.weight_for(admissibility["issues"]), 1.0)
            self.assertEqual(admissibility["weight_multiplier"], 1.0)
        self.assertEqual(complete, 159)

    def test_missing_artifacts_weigh_zero(self):
        """All 27 MISSING artifacts weigh 0.0 under weight_for."""
        missing = 0
        for _case_no, artifact in all_artifacts():
            admissibility = artifact["admissibility"]
            if admissibility["status"] != "MISSING":
                continue
            missing += 1
            self.assertIsNone(artifact["payload"])
            self.assertEqual(prepass.weight_for(admissibility["issues"]), 0.0)
            self.assertEqual(admissibility["weight_multiplier"], 0.0)
        self.assertEqual(missing, 27)


class SchemaVersionDetectorTests(unittest.TestCase):
    """Part 2: the one detector the workspace can justify."""

    def test_case_202_reports_the_single_outlier(self):
        """Case 202 has exactly one artifact whose schema_version differs."""
        case = loader.load_case(202)
        self.assertEqual(prepass.detect_schema_version_mismatch(case), ["EV-DPROF-00202"])

    def test_every_other_case_reports_nothing(self):
        """No other case has an artifact whose schema_version differs."""
        offenders = {}
        for case_no in manifest_case_numbers():
            case = loader.load_case(case_no)
            found = prepass.detect_schema_version_mismatch(case)
            if case_no == 202:
                self.assertEqual(found, ["EV-DPROF-00202"])
            elif found:
                offenders[case_no] = found
        self.assertEqual(offenders, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
