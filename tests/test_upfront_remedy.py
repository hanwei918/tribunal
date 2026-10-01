"""POL-RD-11's remedy, published from policy version 2 (part B).

``wild-v1`` was run once from ``freeze-2026-09-30`` and its answers were read on
2026-10-01. Two of its cases -- 517 and 533 -- produced no ruling at all: three
of 517's four drafts reached the key's 33.50 and all of 533's reached 19.30, and
every draft was refused because the money block published no figure the amount
could be read off. Part B publishes that figure, as POL-RD-11(a)'s own
arithmetic, and gates it on the policy version so that every brief built at
version 1 stays byte-identical and every recorded result stays current.

Four things are checked here:

* every recorded ``brief_sha256`` in all three sets rebuilds unchanged at
  version 1;
* at version 2 every one of the 13 upfront cases publishes a remedy, and it
  equals the answer key's amount -- 0.00 where the key's amount is null;
* the remedy is rounded UP to the next 0.05: a charge of 25.83 against a 22.00
  quote is 3.85;
* at version 2 a brief that is not an upfront one differs from version 1 only by
  the amendment's own clause.

The version-2 briefs are built against a **temporary** amendments directory, so
the repository's own policy version stays 1 and the committed runs stay
readable. ``loader.load_policies`` takes no root, so the directory is patched in
rather than passed.
"""

from __future__ import annotations

import contextlib
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval import development_sets  # noqa: E402
from tribunal import brief, policy_versions  # noqa: E402

# The three runs whose recorded briefs must keep rebuilding, and the key each
# set is answered by.
RUN_DIRECTORIES = (
    ("corpus", PROJECT_ROOT / "runs" / "deepseek-deepseek-flash"),
    ("codex", PROJECT_ROOT / "runs" / "codex" / "deepseek-deepseek-flash"),
    ("wild", PROJECT_ROOT / "runs" / "wild" / "deepseek-deepseek-flash"),
)

KEY_PATHS = {
    "corpus": PROJECT_ROOT / "eval" / "answers" / "ground_truth.json",
    "codex": PROJECT_ROOT / "eval" / "answers" / "codex" / "ground_truth.json",
    "wild": PROJECT_ROOT / "eval" / "answers" / "wild" / "ground_truth.json",
}

# The 13 cases whose fare model is UPFRONT_QUOTE, in the three sets.
UPFRONT_CASES = (
    ("corpus", 115),
    ("codex", 9114),
    ("wild", 501),
    ("wild", 506),
    ("wild", 510),
    ("wild", 516),
    ("wild", 517),
    ("wild", 521),
    ("wild", 524),
    ("wild", 525),
    ("wild", 531),
    ("wild", 532),
    ("wild", 533),
)

# The 106 briefs the three runs record: 29 corpus, 15 codex and 62 wild.
RECORDED_BRIEFS = 106

# One amendment, written into a temporary directory and never committed. It adds
# the next free POL-RD clause, which is what makes policy version 2 exist.
AMENDMENT_NUMBER = 1
AMENDMENT_CLAUSE = {
    "id": "POL-RD-13",
    "title": "Temporary Clause for the Version-2 Tests",
    "category": "ROUTE_DEVIATION",
    "rule": "A clause a test writes into a temporary amendments directory so that "
            "policy version 2 has an amendment to apply. It is never committed.",
    "requires": ["trip_record"],
    "licenses": ["NO_ACTION"],
    "favours": "NEUTRAL",
    "notes": "Not a real clause and not part of the repository's policy.",
}
AMENDMENT = {
    "base_version": policy_versions.BASE_VERSION,
    "proposal_file": "policy/proposals/0001-temporary.json",
    "proposal_sha256": "0" * 64,
    "report_file": "runs/policy-v2/report.md",
    "report_sha256": "0" * 64,
    "cluster_id": "C-0001",
    "cases": [508, 530],
    "approved_by": "test",
    "approved_at": "2026-10-01T00:00:00+08:00",
    "clause": AMENDMENT_CLAUSE,
}

ALL_CASES = tuple(
    (set_name, case_no)
    for set_name in ("corpus", "codex", "wild")
    for case_no in development_sets.named(set_name).cases
)


@contextlib.contextmanager
def version_two_amendments():
    """A temporary amendments directory holding exactly one amendment.

    ``loader.load_policies`` takes no root, so the directory is patched in
    rather than passed. The patch is on ``policy_versions.amendments_dir``,
    which is the one place ``amendment_files`` looks, so ``current_version`` and
    ``apply_amendments`` both see it and neither the repository's own version
    nor a committed run is touched.
    """
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / "0001-temporary.json").write_text(
            json.dumps(AMENDMENT), encoding="utf-8"
        )
        with unittest.mock.patch.object(
            policy_versions, "amendments_dir", lambda root=None: directory
        ):
            yield directory


def money_block(brief_object):
    """The money block the brief publishes, attached to the fare breakdown."""
    for artifact in brief_object["case"]["evidence"]:
        if artifact["evidence_type"] != brief.FARE_EVIDENCE_TYPE:
            continue
        return artifact["payload"][brief.DERIVED_KEY][brief.MONEY_KEY]
    raise AssertionError("the brief publishes no money block")


def figure(block, *path):
    """One money figure's value, by its path inside the block."""
    node = block
    for key in path:
        node = node[key]
    return node["value"]


def key_amounts(path):
    """Every case's expected amount in one key, as a decimal string."""
    with path.open("r", encoding="utf-8") as handle:
        entries = json.load(handle)
    amounts = {}
    for entry in entries:
        amount = entry["ground_truth"].get("expected_amount_sgd")
        amounts[entry["case_no"]] = "0.00" if amount is None else "{0:.2f}".format(amount)
    return amounts


def synthetic_upfront_case(quoted, charged="25.83"):
    """A case carrying one fare breakdown and nothing else.

    The remedy is POL-RD-11(a)'s own expression over four figures, so the
    fixture carries only the artifact those figures live on: a fare breakdown
    whose model is UPFRONT_QUOTE, whose quote is ``quoted`` and whose charge is
    ``charged``. Nothing else about the case enters the arithmetic, which is why
    the fixture is built rather than borrowed.
    """
    return {
        "schema_version": "1.0.0",
        "case_no": 9901,
        "dispute": {
            "dispute_id": "DSP-09901",
            "trip_id": "TRP-09901",
            "case_no": 9901,
            "category": "ROUTE_DEVIATION",
            "filed_by": "RIDER",
            "filed_at": "2026-10-01T00:00:00+08:00",
            "claim_text": "a synthetic case built for the arithmetic",
            "amount_contested_sgd": "0.00",
            "evidence_ids": ["EV-FARE-09901"],
            "counterparty_statement": None,
            "channel": "APP",
        },
        "evidence": [
            {
                "evidence_id": "EV-FARE-09901",
                "evidence_type": "FARE_BREAKDOWN",
                "trip_id": "TRP-09901",
                "source": "synthetic",
                "generated_at": "2026-10-01T00:00:00+08:00",
                "schema_version": "1.0.0",
                "admissibility": {"status": "COMPLETE", "coverage_pct": 100.0, "notes": []},
                "payload": {
                    "trip_id": "TRP-09901",
                    "currency": "SGD",
                    "fare_model": brief.UPFRONT_QUOTE_MODEL,
                    "quoted_fare_sgd": quoted,
                    "airport_surcharge": "0.00",
                    "waiting_time_fee": "0.00",
                    "promo_discount": "0.00",
                    "total_charged": charged,
                    "payment_status": "CHARGED",
                },
            }
        ],
    }


def case_for(set_name, case_no):
    """One case, loaded from its own set's case root."""
    return development_sets.named(set_name).load_case(case_no)


class VersionOneIsUnchangedTests(unittest.TestCase):
    """Every recorded brief rebuilds at version 1, byte for byte.

    This is the test that says the gate holds: the remedy changes what a brief
    means, so it may not change a brief that was already built and recorded.
    """

    def test_every_recorded_brief_digest_rebuilds_at_version_one(self):
        checked = 0
        for set_name, run_dir in RUN_DIRECTORIES:
            for path in sorted(run_dir.glob("case-*.json")):
                if path.name.endswith(".transcript.json"):
                    continue
                recorded = json.loads(path.read_text(encoding="utf-8"))
                case = case_for(set_name, recorded["case_no"])
                _, digest = brief.brief_digest(brief.build_brief_for_case(case))
                self.assertEqual(
                    recorded["brief_sha256"],
                    digest,
                    "{0} case {1} no longer rebuilds at version 1".format(
                        set_name, recorded["case_no"]
                    ),
                )
                checked += 1
        self.assertEqual(
            RECORDED_BRIEFS,
            checked,
            "the three runs record {0} briefs".format(RECORDED_BRIEFS),
        )

    def test_version_one_publishes_no_remedy(self):
        """The upfront block at version 1 is the quote comparison and nothing more."""
        block = money_block(brief.build_brief(115))
        self.assertNotIn(brief.UPFRONT_REMEDY_KEY, block)
        self.assertNotIn(brief.PROPERLY_CHARGEABLE_KEY, block)
        self.assertNotIn(brief.GANTRY_MATCH_RADIUS_KEY, block)
        self.assertEqual(brief.UPFRONT_QUOTE_NOTE, block["note"])


class UpfrontRemedyTests(unittest.TestCase):
    """POL-RD-11(a) at version 2, against the key on all 13 upfront cases."""

    def test_the_remedy_is_the_key_s_amount_on_every_upfront_case(self):
        checked = 0
        with version_two_amendments():
            for set_name, case_no in UPFRONT_CASES:
                block = money_block(
                    brief.build_brief_for_case(case_for(set_name, case_no), policy_version=2)
                )
                self.assertIs(
                    True,
                    block[brief.UPFRONT_REMEDY_AVAILABLE_KEY],
                    "{0} case {1} published no remedy".format(set_name, case_no),
                )
                self.assertEqual(
                    key_amounts(KEY_PATHS[set_name])[case_no],
                    figure(block, brief.UPFRONT_REMEDY_KEY),
                    "{0} case {1}".format(set_name, case_no),
                )
                checked += 1
        self.assertEqual(13, checked, "there are 13 upfront cases")

    def test_the_crossing_radius_is_read_out_of_the_clause(self):
        """POL-RD-09(4)'s 250 m is the clause's own prose, not a literal here."""
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(case_for("wild", 533), policy_version=2)
            )
        radius = block[brief.GANTRY_MATCH_RADIUS_KEY]
        self.assertEqual(brief.POL_RD_09, radius["clause_id"])
        self.assertEqual(brief.money._dec("250"), radius["distance_m"]["value"])
        self.assertIs(False, radius["distance_m"]["structured"])

    def test_an_on_route_line_the_trace_crossed_is_chargeable(self):
        """533's 3.00 CTE line is on the optimal route and the trace passes it."""
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(case_for("wild", 533), policy_version=2)
            )
        lines = block[brief.PROPERLY_CHARGEABLE_KEY]["erp_lines"]
        self.assertEqual(1, len(lines))
        self.assertIs(True, lines[0]["on_optimal_route"]["value"])
        self.assertIs(True, lines[0]["crossed"])
        self.assertEqual(
            "3.00", figure(block, brief.PROPERLY_CHARGEABLE_KEY, "erp_total")
        )
        self.assertEqual(
            "19.30", figure(block, brief.UPFRONT_REMEDY_KEY)
        )

    def test_an_on_route_line_the_trace_never_crossed_is_not_chargeable(self):
        """532's 6.00 CTE line is on the optimal route and 1,159 m away: a phantom."""
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(case_for("wild", 532), policy_version=2)
            )
        lines = block[brief.PROPERLY_CHARGEABLE_KEY]["erp_lines"]
        self.assertEqual(1, len(lines))
        self.assertIs(True, lines[0]["on_optimal_route"]["value"])
        self.assertIs(False, lines[0]["crossed"])
        self.assertGreater(lines[0]["distance_m"]["value"], brief.money._dec("250"))
        self.assertEqual(brief.NO_CROSSING_REASON, lines[0]["reason"])
        self.assertEqual(
            "0.00", figure(block, brief.PROPERLY_CHARGEABLE_KEY, "erp_total")
        )
        self.assertEqual("6.00", figure(block, brief.UPFRONT_REMEDY_KEY))

    def test_an_off_route_line_is_not_chargeable(self):
        """501's two 3.00 ECP lines are off the optimal route: both excluded.

        Both lines are *crossed* -- the trace passes each of them at 0 m -- so
        this is the case that separates the two tests the clause applies. A line
        the trace crossed but that is not on the optimal route is still not
        properly chargeable, and excluding it on the route flag alone is what
        keeps a crossed off-route line out of the remedy.
        """
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(case_for("wild", 501), policy_version=2)
            )
        lines = block[brief.PROPERLY_CHARGEABLE_KEY]["erp_lines"]
        self.assertEqual(2, len(lines))
        for line in lines:
            self.assertIs(False, line["on_optimal_route"]["value"])
            self.assertIs(True, line["crossed"])
        self.assertEqual(
            "0.00", figure(block, brief.PROPERLY_CHARGEABLE_KEY, "erp_total")
        )
        self.assertEqual("14.50", figure(block, brief.UPFRONT_REMEDY_KEY))

    def test_the_airport_surcharge_is_counted_at_the_amount_charged(self):
        """517 originates at Changi and is charged 6.00: the itemised 6.00 counts."""
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(case_for("wild", 517), policy_version=2)
            )
        self.assertEqual(
            "6.00", figure(block, brief.PROPERLY_CHARGEABLE_KEY, "airport_surcharge")
        )
        self.assertEqual("33.50", figure(block, brief.UPFRONT_REMEDY_KEY))

    def test_a_surcharge_not_charged_is_not_recomputed(self):
        """531 also originates at Changi and is charged no surcharge: it adds 0.00.

        The clause surcharges a trip that originates at the airport, and the
        figure counted is the amount the fare itemised. Recomputing it from the
        peak or off-peak rate would publish a surcharge the rider was never
        charged, which is what this test forbids.
        """
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(case_for("wild", 531), policy_version=2)
            )
        self.assertEqual(
            "0.00", figure(block, brief.PROPERLY_CHARGEABLE_KEY, "airport_surcharge")
        )
        self.assertEqual("0.00", figure(block, brief.UPFRONT_REMEDY_KEY))

    def test_a_null_quote_publishes_no_remedy_and_the_reason(self):
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(synthetic_upfront_case(None), policy_version=2)
            )
        self.assertIs(False, block[brief.UPFRONT_REMEDY_AVAILABLE_KEY])
        self.assertNotIn(brief.UPFRONT_REMEDY_KEY, block)
        self.assertEqual(
            brief.NO_QUOTED_FARE_REASON, block[brief.UPFRONT_REMEDY_REASON_KEY]
        )

    def test_no_key_in_the_remedy_contains_the_word_refund(self):
        """POL-RD-11(a) is an overcharge, not a fare handed back."""
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(case_for("wild", 517), policy_version=2)
            )
        stack = [block]
        keys = []
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                keys.extend(node)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        offenders = sorted(key for key in keys if "refund" in key)
        self.assertEqual([], offenders)


class RoundingTests(unittest.TestCase):
    """POL-RD-11(a) is rounded UP to the nearest 0.05, like every payable."""

    def test_a_charge_of_25_83_against_a_22_00_quote_is_3_85(self):
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(synthetic_upfront_case("22.00"), policy_version=2)
            )
        self.assertEqual(
            brief.money._dec("3.83"),
            figure(block, brief.UPFRONT_REMEDY_BEFORE_ROUNDING_KEY),
        )
        self.assertEqual("3.85", figure(block, brief.UPFRONT_REMEDY_KEY))

    def test_a_charge_below_the_quote_is_floored_at_zero(self):
        with version_two_amendments():
            block = money_block(
                brief.build_brief_for_case(
                    synthetic_upfront_case("22.00", charged="20.00"), policy_version=2
                )
            )
        self.assertEqual(
            brief.money._dec("0"), figure(block, brief.UPFRONT_REMEDY_BEFORE_ROUNDING_KEY)
        )
        self.assertEqual("0.00", figure(block, brief.UPFRONT_REMEDY_KEY))


class NonUpfrontTests(unittest.TestCase):
    """At version 2 a brief that is not an upfront one changes only by the clause."""

    def test_every_non_upfront_brief_differs_only_by_the_amendment_s_clause(self):
        upfront = frozenset(UPFRONT_CASES)
        checked = 0
        with version_two_amendments():
            for set_name, case_no in ALL_CASES:
                if (set_name, case_no) in upfront:
                    continue
                case = case_for(set_name, case_no)
                one = brief.build_brief_for_case(case)
                two = brief.build_brief_for_case(case, policy_version=2)

                self.assertEqual(
                    one["case"],
                    two["case"],
                    "{0} case {1}: the evidence changed".format(set_name, case_no),
                )
                self.assertEqual(
                    one["policies"]["general"],
                    two["policies"]["general"],
                    "{0} case {1}: the general policy changed".format(set_name, case_no),
                )

                if case["dispute"]["category"] == "ROUTE_DEVIATION":
                    self.assertEqual(
                        list(one["policies"]["category"]["clauses"]) + [AMENDMENT_CLAUSE],
                        two["policies"]["category"]["clauses"],
                        "{0} case {1}: more than the amendment's clause changed".format(
                            set_name, case_no
                        ),
                    )
                    self.assertEqual(
                        one["policies"]["category"]["version"]
                        + policy_versions.AMENDMENT_SUFFIX.format(AMENDMENT_NUMBER),
                        two["policies"]["category"]["version"],
                        "{0} case {1}: the version marker is wrong".format(set_name, case_no),
                    )
                else:
                    self.assertEqual(
                        one["policies"],
                        two["policies"],
                        "{0} case {1}: a POL-RD amendment reached a no-show brief".format(
                            set_name, case_no
                        ),
                    )
                checked += 1
        self.assertEqual(
            len(ALL_CASES) - len(UPFRONT_CASES),
            checked,
            "every case that is not an upfront one was checked",
        )


if __name__ == "__main__":
    unittest.main()
