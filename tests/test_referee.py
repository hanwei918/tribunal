"""Tests for the deterministic mechanical citation referee."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import brief, loader, referee  # noqa: E402


class RefereeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = loader.load_case(114)
        cls.brief = brief.build_brief_for_case(cls.case)
        cls.evidence_id = "EV-GPS-00114"
        cls.clause_id = "POL-RD-01"

    def clean_claim(self):
        return {
            "text": "The trace supports this point.",
            "evidence_ids": [self.evidence_id],
            "clause_ids": [self.clause_id],
            "relies_on": "derived.deviation.excess_km",
        }

    def decision(self, claim):
        result = referee.referee(self.brief, [claim], [])
        self.assertEqual(1, len(result.ledger))
        return result.ledger[0], result

    def assert_reason(self, claim, code):
        entry, result = self.decision(claim)
        self.assertEqual(referee.STATUS_DISCARDED, entry["status"])
        self.assertEqual(code, entry["reason_code"])
        self.assertEqual(1, len(result.discards))
        return entry

    def test_clean_claim_is_kept_with_the_kept_code(self):
        entry, result = self.decision(self.clean_claim())
        self.assertEqual(referee.STATUS_KEPT, entry["status"])
        self.assertEqual(referee.REASON_KEPT, entry["reason_code"])
        self.assertEqual((), result.discards)

    def test_no_evidence_id_poisoning(self):
        claim = self.clean_claim()
        claim.pop("evidence_ids")
        self.assert_reason(claim, referee.NO_EVIDENCE_ID)

    def test_no_clause_id_poisoning(self):
        claim = self.clean_claim()
        claim.pop("clause_ids")
        self.assert_reason(claim, referee.NO_CLAUSE_ID)

    def test_unresolved_evidence_poisoning(self):
        claim = self.clean_claim()
        claim["evidence_ids"] = ["EV-NOT-IN-THIS-CASE"]
        self.assert_reason(claim, referee.EVIDENCE_UNRESOLVED)

    def test_unresolved_and_malformed_clause_ids_poisoning(self):
        for clause_id in ("POL-RD-99", "POL-RD-01(4)"):
            with self.subTest(clause_id=clause_id):
                claim = self.clean_claim()
                claim["clause_ids"] = [clause_id]
                self.assert_reason(claim, referee.CLAUSE_UNRESOLVED)

    def test_undisclosed_impairment_poisoning(self):
        disclosed = self.clean_claim()
        disclosed["evidence_ids"] = ["EV-ADVIS-00114-01"]
        disclosed["clause_ids"] = ["POL-RD-08"]
        disclosed["text"] = "The advisory is MISSING_ARTIFACT and cannot carry this fact."
        kept, _result = self.decision(disclosed)
        self.assertEqual(referee.STATUS_KEPT, kept["status"])

        broken = dict(disclosed)
        broken["text"] = "The advisory supports this fact."
        self.assert_reason(broken, referee.IMPAIRMENT_UNDISCLOSED)

    def test_context_only_profile_ground_poisoning(self):
        permitted = self.clean_claim()
        permitted["relies_on"] = "driver_profile.deviation_flags_90d"
        kept, _result = self.decision(permitted)
        self.assertEqual(referee.STATUS_KEPT, kept["status"])

        broken = dict(permitted)
        broken["relies_on"] = "driver_profile.prior_deviation_flags"
        self.assert_reason(broken, referee.PROFILE_FIELD_AS_GROUND)

    def test_context_only_profile_text_mention_is_a_flag_not_a_discard(self):
        claim = self.clean_claim()
        claim["text"] = "The rating is context only and cannot carry this finding."
        entry, result = self.decision(claim)
        self.assertEqual(referee.STATUS_KEPT, entry["status"])
        self.assertEqual(1, len(result.flags))
        self.assertIn("rating", result.flags[0]["flags"][0])

    def test_context_only_fields_are_read_from_pol_gen_01(self):
        self.assertEqual(
            (
                "rating",
                "account_age_days",
                "lifetime_trips",
                "cancellation_rate",
                "prior_disputes_filed",
                "prior_disputes_upheld",
                "prior_no_show_flags",
                "prior_deviation_flags",
                "acceptance_rate",
                "active_region",
            ),
            referee.context_only_profile_fields(self.brief),
        )

    def test_reason_codes_are_closed_and_the_ledger_is_deterministic(self):
        claims = [self.clean_claim(), {"text": "bad", "evidence_ids": [], "clause_ids": []}]
        first = referee.referee(self.brief, claims, claims).as_dict()
        second = referee.referee(self.brief, claims, claims).as_dict()
        self.assertEqual(first, second)
        self.assertTrue(all(entry["reason_code"] in referee.REASON_CODES for entry in first["ledger"]))
        self.assertEqual(4, len(first["ledger"]))
        self.assertEqual(2, len(first["discards"]))


if __name__ == "__main__":
    unittest.main()
