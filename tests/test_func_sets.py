"""The four functional sets: inject-v1, pii-v1, collusion-v1 and the chat-signals-v1 fixture.

Checks that need no model call: the files are where the contract says, the index hashes match, every key is well formed,
the injection pairs share their four fields, every PII span is present and every telephone number is outside the allocated
mobile blocks, the collusion root's repeat_party flags are the ones ops/risk.py raises, and the chat fixture has at least
three positives and three negatives per label.
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETS = ("inject-v1", "pii-v1", "collusion-v1")
CJK = re.compile("[" + chr(0x4E00) + "-" + chr(0x9FFF) + chr(0x3400) + "-" + chr(0x4DBF) + chr(0x3040) + "-" + chr(0x30FF) + chr(0xAC00) + "-" + chr(0xD7AF) + "]")
RULINGS = {"FULL_REFUND", "PARTIAL_REFUND", "NO_ACTION", "DRIVER_COMPENSATION", "ESCALATE"}
DATA_FILES = {"index.json", "CANARY.txt", "README.md"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class LayoutTests(unittest.TestCase):
    def test_each_set_holds_only_cases_and_its_metadata(self):
        for name in SETS:
            d = ROOT / "data" / "external" / name
            for f in d.iterdir():
                self.assertTrue(f.name in DATA_FILES or re.fullmatch(r"case-\d{5}\.json", f.name), (name, f.name))

    def test_index_hashes_match(self):
        for name in SETS:
            d = ROOT / "data" / "external" / name
            for row in load(d / "index.json"):
                self.assertEqual(row["sha256"], hashlib.sha256((d / row["file"]).read_bytes()).hexdigest(), (name, row["file"]))

    def test_no_cjk_and_no_answer_words_in_case_files(self):
        for name in SETS:
            for f in (ROOT / "data" / "external" / name).glob("case-*.json"):
                text = f.read_text(encoding="utf-8")
                self.assertIsNone(CJK.search(text), f)
                for word in ("ground_truth", "expected_ruling", "governing_clauses", "rationale", "canary"):
                    self.assertNotIn(word, text.lower(), (f, word))

    def test_canary_only_in_its_own_places(self):
        for name in SETS:
            canary = (ROOT / "data" / "external" / name / "CANARY.txt").read_text(encoding="utf-8").splitlines()[0]
            for tree in ("tribunal", "prompts", "policy"):
                for f in (ROOT / tree).rglob("*"):
                    if f.is_file() and f.suffix in (".py", ".md", ".json", ".txt"):
                        self.assertNotIn(canary, f.read_text(encoding="utf-8", errors="ignore"), f)

    def test_keys_are_well_formed_and_cover_every_case(self):
        for name in SETS:
            idx = {r["case_no"] for r in load(ROOT / "data" / "external" / name / "index.json")}
            keys = load(ROOT / "eval" / "answers" / name / "ground_truth.json")
            self.assertEqual(idx, {k["case_no"] for k in keys}, name)
            for k in keys:
                g = k["ground_truth"]
                self.assertIn(g["expected_ruling"], RULINGS)
                if g["expected_ruling"] in ("ESCALATE", "NO_ACTION"):
                    self.assertIsNone(g["expected_amount_sgd"], k["case_no"])
                if g["expected_ruling"] == "DRIVER_COMPENSATION":
                    self.assertEqual(g["expected_amount_sgd"], g["expected_driver_compensation_sgd"], k["case_no"])
                self.assertTrue(g["governing_clauses"] and g["rationale"])


class InjectionTests(unittest.TestCase):
    def test_every_pair_shares_its_four_fields(self):
        keys = {k["case_no"]: k["ground_truth"] for k in load(ROOT / "eval" / "answers" / "inject-v1" / "ground_truth.json")}
        pairs = load(ROOT / "eval" / "answers" / "inject-v1" / "pairs.json")
        self.assertEqual(len(pairs), 6)
        for p in pairs:
            a, b = (keys[n] for n in p["cases"])
            for f in ("expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd"):
                self.assertEqual(a[f], b[f], (p["pair_id"], f))
            # a referral names the case's own evidence id, so it is compared with the case number taken out
            norm = lambda refs, n: [r.replace("{0:05d}".format(n), "N") for r in refs]
            self.assertEqual(norm(a["expected_referrals"], p["cases"][0]), norm(b["expected_referrals"], p["cases"][1]), p["pair_id"])

    def test_injected_copy_differs_from_its_twin_only_in_party_text(self):
        d = ROOT / "data" / "external" / "inject-v1"
        for p in load(ROOT / "eval" / "answers" / "inject-v1" / "pairs.json"):
            clean, inj = (load(d / "case-{0:05d}.json".format(n)) for n in p["cases"])
            gps = lambda c: [e for e in c["evidence"] if e["evidence_type"] == "GPS_TRACE"][0]["payload"]["points"]
            fare = lambda c: [e for e in c["evidence"] if e["evidence_type"] == "FARE_BREAKDOWN"][0]["payload"]["total_charged"]
            self.assertEqual([(x["lat"], x["lng"], x["ts"]) for x in gps(clean)], [(x["lat"], x["lng"], x["ts"]) for x in gps(inj)], p["pair_id"])
            self.assertEqual(fare(clean), fare(inj), p["pair_id"])


class PiiTests(unittest.TestCase):
    def test_every_span_is_present_and_every_number_is_unallocated(self):
        d = ROOT / "data" / "external" / "pii-v1"
        for row in load(ROOT / "eval" / "answers" / "pii-v1" / "pii_spans.json"):
            if "case_no" not in row:
                continue
            text = (d / "case-{0:05d}.json".format(row["case_no"])).read_text(encoding="utf-8")
            for s in row["mask"] + row["do_not_mask"]:
                self.assertIn(s["text"], text, (row["case_no"], s["text"]))
                if s["type"] == "PHONE":
                    digits = re.sub(r"\D", "", s["text"])[-8:]
                    self.assertTrue(digits.startswith("99"), s["text"])
                if s["type"] == "EMAIL":
                    self.assertRegex(s["text"], r"@example\.(com|org)$")


class CollusionTests(unittest.TestCase):
    def test_repeat_party_flags_are_the_ones_ops_raises(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from tribunal import loader
        from ops import risk
        root = ROOT / "data" / "external" / "collusion-v1"
        expected = {x["case_no"]: sorted(h["other_case"] for h in x["flags"]) for x in load(ROOT / "eval" / "answers" / "collusion-v1" / "cross_case.json")["expected_repeat_party"]}
        for f in sorted(root.glob("case-*.json")):
            case = loader.load_external_case(f)
            got = sorted({flag.other_case_no for flag in risk.repeat_party_flags(case, root)})
            self.assertEqual(expected[case["case_no"]], got, case["case_no"])


class ChatSignalTests(unittest.TestCase):
    def test_three_positives_and_three_negatives_per_label(self):
        doc = load(ROOT / "eval" / "fixtures" / "chat-signals-v1.json")
        for lab in ("threat", "agreement", "disagreement"):
            pos = sum(1 for x in doc["items"] if x["labels"][lab])
            self.assertGreaterEqual(pos, 3, lab)
            self.assertGreaterEqual(len(doc["items"]) - pos, 3, lab)
        for s in ("NEG", "NEU", "POS"):
            self.assertGreaterEqual(sum(1 for x in doc["items"] if x["labels"]["sentiment"] == s), 3, s)
        self.assertIsNone(CJK.search(json.dumps(doc, ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()
