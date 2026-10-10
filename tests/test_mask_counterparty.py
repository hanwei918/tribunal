"""POL-GEN-08(4): a registration mark in the counterparty statement is masked at policy version 6.

The dispute schema carries counterparty_statement as an object {text, submitted_by, submitted_at}; the version-6 mask
read it only when it was a string, so a mark in a statement reached the model. Found by pii-v1 case 3202.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tribunal import brief, loader, money  # noqa: E402

CASE = ROOT / "data" / "external" / "pii-v1" / "case-03202.json"


class CounterpartyMaskTests(unittest.TestCase):
    def test_statement_object_is_masked_at_version_6(self):
        case = loader.load_external_case(CASE)
        self.assertIn("SZZ 4821 K", case["dispute"]["counterparty_statement"]["text"])
        text = money.dumps_canonical(brief.build_brief_for_case(case, policy_version=6))
        self.assertNotIn("SZZ 4821 K", text)
        self.assertIn(brief.VEHICLE_MASK, text)

    def test_case_file_is_not_changed(self):
        case = loader.load_external_case(CASE)
        brief.build_brief_for_case(case, policy_version=6)
        self.assertIn("SZZ 4821 K", case["dispute"]["counterparty_statement"]["text"])

    def test_before_version_6_nothing_is_masked(self):
        case = loader.load_external_case(CASE)
        text = money.dumps_canonical(brief.build_brief_for_case(case, policy_version=5))
        self.assertIn("SZZ 4821 K", text)


if __name__ == "__main__":
    unittest.main()
