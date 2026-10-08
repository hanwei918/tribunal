"""The dev-v2 development set: shape, isolation, canary and key integrity. No model call."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETS = {
    "dev-v2": {"count": 80, "cases": list(range(1701, 1741)) + list(range(1751, 1791)), "split": (50, 30)},
    "dev-v2-ext": {"count": 120, "cases": list(range(2701, 2761)) + list(range(2801, 2861)), "split": (133, 67),
                   "split_universe": list(range(1701, 1741)) + list(range(1751, 1791)) + list(range(2701, 2761)) + list(range(2801, 2861))},
}
SET_NAME = "dev-v2"
SET_DIR = ROOT / "data" / "external" / SET_NAME
KEY = ROOT / "eval" / "answers" / SET_NAME / "ground_truth.json"
CANARY = (SET_DIR / "CANARY.txt").read_text(encoding="utf-8").splitlines()[0].strip()
CJK = re.compile("[" + chr(0x4E00) + "-" + chr(0x9FFF) + chr(0x3400) + "-" + chr(0x4DBF) + chr(0x3040) + "-" + chr(0x30FF) + chr(0xAC00) + "-" + chr(0xD7AF) + "]")
FORBIDDEN_KEYS = {"ground_truth", "expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd", "expected_referrals"}
RULINGS = {"FULL_REFUND", "PARTIAL_REFUND", "NO_ACTION", "DRIVER_COMPENSATION", "ESCALATE"}


def _walk(node, found):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in FORBIDDEN_KEYS:
                found.append(k)
            _walk(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found)


class DevV2SetTests(unittest.TestCase):
    SET_NAME = "dev-v2"

    @classmethod
    def setUpClass(cls):
        cls.set_dir = ROOT / "data" / "external" / cls.SET_NAME
        cls.spec = SETS[cls.SET_NAME]
        if not cls.set_dir.exists():
            raise unittest.SkipTest("{0} is not present".format(cls.SET_NAME))
        cls.index = json.loads((cls.set_dir / "index.json").read_text(encoding="utf-8"))
        cls.cases = {}
        for entry in cls.index:
            path = cls.set_dir / entry["file"]
            cls.cases[entry["case_no"]] = (path.read_bytes(), json.loads(path.read_text(encoding="utf-8")))
        cls.keys = {k["case_no"]: k for k in json.loads((ROOT / "eval" / "answers" / cls.SET_NAME / "ground_truth.json").read_text(encoding="utf-8"))}
        cls.split = json.loads((cls.set_dir / "split.json").read_text(encoding="utf-8"))
        cls.pairs = json.loads((ROOT / "eval" / "answers" / cls.SET_NAME / "pairs.json").read_text(encoding="utf-8"))

    def test_case_count_and_numbering(self):
        self.assertEqual(len(self.index), self.spec["count"])
        cats = [e["category"] for e in self.index]
        self.assertEqual(cats.count("NO_SHOW_CHARGE"), self.spec["count"] // 2)
        self.assertEqual(cats.count("ROUTE_DEVIATION"), self.spec["count"] // 2)
        self.assertEqual(sorted(self.cases), self.spec["cases"])

    def test_index_sha256_matches_files(self):
        for entry in self.index:
            raw, _ = self.cases[entry["case_no"]]
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"], entry["file"])

    def test_contract_shape(self):
        for n, (_, case) in self.cases.items():
            self.assertEqual(set(case), {"schema_version", "case_no", "dispute", "evidence"}, n)
            self.assertEqual(case["schema_version"], "1.2.0")
            self.assertEqual(case["case_no"], n)
            self.assertEqual(case["dispute"]["case_no"], n)
            types = [e["evidence_type"] for e in case["evidence"]]
            for t in ("TRIP_RECORD", "GPS_TRACE", "CHAT_LOG", "FARE_BREAKDOWN", "RIDER_PROFILE", "DRIVER_PROFILE", "TRAFFIC_ADVISORY"):
                self.assertIn(t, types, (n, t))
            for e in case["evidence"]:
                self.assertEqual(set(e), {"evidence_id", "evidence_type", "admissibility", "payload", "schema_version", "source", "trip_id", "generated_at"}, n)
                adm = e["admissibility"]
                self.assertIn(adm["status"], {"COMPLETE", "IMPAIRED", "MISSING"})
                self.assertEqual(adm["status"] == "MISSING", e["payload"] is None, e["evidence_id"])
                self.assertEqual(adm["status"] == "MISSING", adm["weight_multiplier"] == 0.0, e["evidence_id"])
                self.assertEqual(adm["status"] == "COMPLETE", adm["issues"] == [], e["evidence_id"])

    def test_the_data_directory_holds_no_answer_bearing_file(self):
        """Everything that names an expected outcome lives under eval/answers/, never under data/."""
        allowed = {"index.json", "split.json", "README.md", "CANARY.txt"}
        for path in self.set_dir.iterdir():
            if path.name.startswith("case-"):
                continue
            self.assertIn(path.name, allowed, path.name)
            text = path.read_text(encoding="utf-8")
            for word in ("expected_ruling", "FULL_REFUND", "PARTIAL_REFUND", "DRIVER_COMPENSATION", "NO_ACTION", "ESCALATE"):
                self.assertNotIn(word, text, (path.name, word))

    def test_case_numbers_collide_with_no_other_set(self):
        others = set()
        for path in (ROOT / "data").rglob("case-*.json"):
            if self.set_dir.name in path.parts or any(part.startswith("dev-v2") for part in path.parts):
                continue
            others.add(int(path.stem.split("-")[1]))
        self.assertFalse(set(self.cases) & others, sorted(set(self.cases) & others))

    def test_every_no_show_record_carries_its_platform_policy(self):
        for n, (_, case) in self.cases.items():
            if case["dispute"]["category"] != "NO_SHOW_CHARGE":
                continue
            trip = [e for e in case["evidence"] if e["evidence_type"] == "TRIP_RECORD"][0]["payload"]
            pp = trip.get("platform_policy")
            self.assertIsInstance(pp, dict, n)
            self.assertIn(pp["source"], {"PLATFORM-PUBLISHED-2026-10-07", "RECORD-PLATFORM", "AUTHORED-V1"}, n)
            self.assertIsInstance(pp["free_wait_sec"], int, n)

    def test_no_answer_keys_inside_cases(self):
        for n, (_, case) in self.cases.items():
            found = []
            _walk(case, found)
            self.assertEqual(found, [], n)

    def test_no_cjk_and_no_sealed_vocabulary(self):
        for n, (raw, _) in self.cases.items():
            text = raw.decode("utf-8")
            self.assertIsNone(CJK.search(text), n)
            for w in ("sealed", "wild-v1", "wild-v2", "DISP-002", "organiser", "Ryde Help Centre"):
                self.assertNotIn(w.lower(), text.lower(), (n, w))

    def test_canary_stays_out_of_the_pipeline(self):
        for folder in ("tribunal", "prompts", "policy", "precedents"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file() and path.suffix in {".py", ".md", ".json", ".jsonl", ".txt"}:
                    self.assertNotIn(CANARY, path.read_text(encoding="utf-8", errors="ignore"), str(path))
        runs = ROOT / "runs"
        if runs.exists():
            for path in runs.rglob("*.json*"):
                if any(part.startswith("dev-v2") for part in path.parts):
                    continue
                self.assertNotIn(CANARY, path.read_text(encoding="utf-8", errors="ignore"), str(path))

    def test_key_covers_every_case_and_only_these(self):
        self.assertEqual(sorted(self.keys), sorted(self.cases))
        for n, k in self.keys.items():
            gt = k["ground_truth"]
            self.assertIn(gt["expected_ruling"], RULINGS)
            self.assertEqual(k["dispute_id"], self.cases[n][1]["dispute"]["dispute_id"])
            self.assertTrue(gt["governing_clauses"], n)
            for c in gt["governing_clauses"]:
                self.assertRegex(c, r"^POL-(GEN|NS|RD)-\d{2}$")
            self.assertRegex(gt["rationale"], r"EV-[A-Z]+-\d{5}")
            if gt["expected_ruling"] == "ESCALATE":
                self.assertIsNone(gt["expected_amount_sgd"], n)
                self.assertIsNone(gt["expected_driver_compensation_sgd"], n)
            if gt["expected_ruling"] == "DRIVER_COMPENSATION":
                self.assertEqual(gt["expected_amount_sgd"], gt["expected_driver_compensation_sgd"], n)
            if gt["expected_ruling"] == "NO_ACTION":
                self.assertIsNone(gt["expected_amount_sgd"], n)

    def test_split_is_a_partition_that_keeps_pairs_together(self):
        calib, hold = set(self.split["calibration"]), set(self.split["holdout"])
        self.assertEqual((len(calib), len(hold)), self.spec["split"])
        self.assertEqual(calib | hold, set(self.spec.get("split_universe", self.spec["cases"])))
        self.assertEqual(sorted(calib | hold), self.split["covers"])
        self.assertFalse(calib & hold)
        for pair in self.pairs:
            if pair["kind"] == "DIRECTIONAL":
                sides = {("calib" if n in calib else "hold") for n in pair["cases"]}
                self.assertEqual(len(sides), 1, pair["pair_id"])

    def test_pairs_state_their_relation_truthfully(self):
        for pair in self.pairs:
            rulings = {self.keys[n]["ground_truth"]["expected_ruling"] for n in pair["cases"]}
            if pair["kind"] == "INVARIANCE":
                self.assertEqual(len(rulings), 1, pair["pair_id"])
            else:
                self.assertGreater(len(rulings), 1, pair["pair_id"])

    def test_chat_count_matches_trip_record(self):
        for n, (_, case) in self.cases.items():
            trip = [e for e in case["evidence"] if e["evidence_type"] == "TRIP_RECORD"][0]["payload"]
            chat = [e for e in case["evidence"] if e["evidence_type"] == "CHAT_LOG"][0]["payload"]
            self.assertEqual(trip["chat_message_count"], chat["message_count"], n)
            ids = [m["msg_id"] for m in chat["messages"]]
            self.assertEqual(ids, ["MSG-{0:05d}-{1:03d}".format(n, i) for i in range(1, len(ids) + 1)], n)

    def test_loader_accepts_every_case(self):
        from tribunal import loader
        for entry in self.index:
            case = loader.load_external_case(self.set_dir / entry["file"])
            self.assertEqual(case["case_no"], entry["case_no"])


class DevV2ExtSetTests(DevV2SetTests):
    SET_NAME = "dev-v2-ext"

    def test_the_extension_shares_no_identifier_with_dev_v2(self):
        base = ROOT / "data" / "external" / "dev-v2"
        if not base.exists():
            self.skipTest("dev-v2 is not present")
        base_ids = set()
        for path in base.glob("case-*.json"):
            case = json.loads(path.read_text(encoding="utf-8"))
            base_ids.add(case["dispute"]["dispute_id"])
            base_ids.add(case["dispute"]["trip_id"])
            base_ids.update(e["evidence_id"] for e in case["evidence"])
        for n, (_, case) in self.cases.items():
            self.assertNotIn(case["dispute"]["dispute_id"], base_ids, n)
            self.assertNotIn(case["dispute"]["trip_id"], base_ids, n)
            for e in case["evidence"]:
                self.assertNotIn(e["evidence_id"], base_ids, n)


# --------------------------------------------------------------------------
# The guards added when the sets were installed in this repository
# --------------------------------------------------------------------------
# The other sets' case roots, named rather than discovered, so a set added later
# cannot escape the collision check. ``ryde`` and ``ryde-v3`` are the organisers'
# sample converted at policy versions 1 and 3.
OTHER_SET_ROOTS = (
    ("corpus", ROOT / "data" / "cases"),
    ("codex", ROOT / "data" / "external" / "codex"),
    ("wild", ROOT / "data" / "external" / "wild"),
    ("wild-v2", ROOT / "data" / "external" / "wild-v2"),
    ("ryde", ROOT / "data" / "external" / "ryde"),
    ("ryde-v3", ROOT / "data" / "external" / "ryde-v3"),
)

# The first sealed set's own case numbers, known from its manifest and named here
# rather than read: its root is closed and its cases are read exactly once, by
# the run that reported them.
SEALED_V1_NUMBERS = tuple(range(301, 313)) + tuple(range(401, 413))

DEV_V2_SET_NAMES = ("dev-v2", "dev-v2-ext")


def dev_set_dir(name):
    return ROOT / "data" / "external" / name


def dev_set_cases(name):
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(dev_set_dir(name).glob("case-*.json"))
    ]


def trip_payload(case_or_brief):
    """The TRIP_RECORD payload of a case or of a built brief."""
    evidence = case_or_brief.get("evidence")
    if evidence is None:
        evidence = case_or_brief["case"]["evidence"]
    return next(
        artifact["payload"]
        for artifact in evidence
        if artifact["evidence_type"] == "TRIP_RECORD"
    )


class DevV2CollisionTests(unittest.TestCase):
    """Neither set shares a case number or a dispute id with any other set."""

    def other_case_numbers(self):
        numbers = set(SEALED_V1_NUMBERS)
        for _name, root in OTHER_SET_ROOTS:
            for path in root.glob("case-*.json"):
                numbers.add(int(path.stem.split("-")[1]))
        return numbers

    def other_dispute_ids(self):
        found = set()
        for _name, root in OTHER_SET_ROOTS:
            for path in root.glob("case-*.json"):
                found.add(
                    json.loads(path.read_text(encoding="utf-8"))["dispute"]["dispute_id"]
                )
        return found

    def test_the_other_sets_were_found(self):
        """A control: the walk found the sets it names."""
        numbers = self.other_case_numbers()
        for required in (101, 208, 501, 701, 901, 9115, 301, 412):
            with self.subTest(case_no=required):
                self.assertIn(required, numbers)
        self.assertTrue(self.other_dispute_ids(), "no dispute id was harvested")

    def test_neither_set_shares_a_case_number(self):
        others = self.other_case_numbers()
        for name in DEV_V2_SET_NAMES:
            mine = {
                int(path.stem.split("-")[1])
                for path in dev_set_dir(name).glob("case-*.json")
            }
            with self.subTest(set=name):
                self.assertEqual(set(), mine & others, sorted(mine & others))

    def test_neither_set_shares_a_dispute_id(self):
        others = self.other_dispute_ids()
        for name in DEV_V2_SET_NAMES:
            mine = {case["dispute"]["dispute_id"] for case in dev_set_cases(name)}
            with self.subTest(set=name):
                self.assertEqual(set(), mine & others, sorted(mine & others))


class DevV2PlatformPolicyTests(unittest.TestCase):
    """Every record carries the block it should, and a brief uses the record's own.

    A no-show record without a block would silently be briefed under the
    version-1 parameters, and the version-3 derivation would fill in an
    ``AUTHORED-V1`` block that says the case was authored under them. These cases
    were authored under the published version-3 parameters instead, so every
    no-show record states them itself.
    """

    def test_every_no_show_record_carries_a_non_null_block(self):
        checked = 0
        for name in DEV_V2_SET_NAMES:
            for case in dev_set_cases(name):
                if case["dispute"]["category"] != "NO_SHOW_CHARGE":
                    continue
                checked += 1
                with self.subTest(set=name, case=case["case_no"]):
                    self.assertIsInstance(
                        trip_payload(case).get("platform_policy"), dict
                    )
        self.assertGreater(checked, 0)

    def test_every_route_deviation_record_carries_a_null_block(self):
        checked = 0
        for name in DEV_V2_SET_NAMES:
            for case in dev_set_cases(name):
                if case["dispute"]["category"] != "ROUTE_DEVIATION":
                    continue
                checked += 1
                with self.subTest(set=name, case=case["case_no"]):
                    self.assertIsNone(trip_payload(case).get("platform_policy"))
        self.assertGreater(checked, 0)

    def test_a_version_three_brief_of_1718_shows_the_records_own_block(self):
        """180 s, the case's own source, and never the derived ``AUTHORED-V1``."""
        from tribunal import brief, loader

        case = loader.load_external_set_case(dev_set_dir("dev-v2"), 1718)
        self.assertEqual("NO_SHOW_CHARGE", case["dispute"]["category"])
        briefed = brief.build_brief_for_case(case, policy_version=3)
        payload = trip_payload(briefed)
        own = payload["platform_policy"]
        in_force = payload["platform_policy_in_force"]
        self.assertEqual(180, in_force["free_wait_sec"])
        self.assertEqual(own["source"], in_force["source"])
        self.assertEqual(own, in_force)
        self.assertNotEqual("AUTHORED-V1", in_force["source"])

    def test_the_canary_reaches_no_brief(self):
        """The canary marks the set; a version-3 brief must never carry it."""
        from tribunal import brief, loader

        for name, case_numbers in (
            ("dev-v2", (1701, 1751)),
            ("dev-v2-ext", (2701, 2801)),
        ):
            for case_no in case_numbers:
                case = loader.load_external_set_case(dev_set_dir(name), case_no)
                canonical, _ = brief.brief_digest(
                    brief.build_brief_for_case(case, policy_version=3)
                )
                with self.subTest(set=name, case_no=case_no):
                    self.assertNotIn(CANARY, canonical)


if __name__ == "__main__":
    unittest.main()
