"""Emit the sealed set: cases (no answers), answer key (separate), index, manifest."""
import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from core import dumps, sha
from rd_cases import RD_CASES
from ns_cases import NS_CASES

OUT = os.path.join(os.path.dirname(__file__), "..", "out")
CASES = os.path.join(OUT, "data", "sealed", "cases")
ANS = os.path.join(OUT, "eval", "sealed")
os.makedirs(CASES, exist_ok=True); os.makedirs(ANS, exist_ok=True)

index, key, eval_index = [], {}, []
for fn in RD_CASES + NS_CASES:
    cf, g = fn()
    c = cf["case_no"]
    with open(os.path.join(CASES, f"case-{c:05d}.json"), "w", encoding="utf-8") as f:
        f.write(dumps(cf))
    d = cf["dispute"]
    index.append({"case_no": c, "dispute_id": d["dispute_id"], "trip_id": d["trip_id"], "category": d["category"], "file": f"cases/case-{c:05d}.json"})
    key[str(c)] = g
    eval_index.append({"case_no": c, "category": d["category"], "expected_ruling": g["expected_ruling"],
                       "expected_amount_sgd": g["expected_amount_sgd"], "expected_driver_compensation_sgd": g["expected_driver_compensation_sgd"],
                       "expected_referrals": g["expected_referrals"], "difficulty": g["difficulty"]})

with open(os.path.join(OUT, "data", "sealed", "index.json"), "w", encoding="utf-8") as f: f.write(dumps(index))
with open(os.path.join(ANS, "ground_truth.json"), "w", encoding="utf-8") as f: f.write(dumps(key))
with open(os.path.join(ANS, "eval_index.json"), "w", encoding="utf-8") as f: f.write(dumps(eval_index))
print(f"wrote {len(index)} cases")
