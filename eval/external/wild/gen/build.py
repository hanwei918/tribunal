"""Emit the wild set: cases (no answers), answer key (separate), index, manifest."""
import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from core import dumps, sha
from wild import build_rd, build_ns
from specs_rd import RD
import specs_bill
try:
    from specs_ns import NS
except ImportError:
    NS = []
OUT = os.environ.get("WILD_ROOT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
CASES = os.path.join(OUT, "data", "wild", "cases"); ANS = os.path.join(OUT, "eval", "wild")
os.makedirs(CASES, exist_ok=True); os.makedirs(ANS, exist_ok=True)
for f in os.listdir(CASES): os.remove(os.path.join(CASES, f))
index, key, eval_index, seeds = [], {}, [], {}
for s, fn in [(s, build_rd) for s in RD] + [(s, build_ns) for s in NS]:
    cf, g, F = fn(s); c = cf["case_no"]
    open(os.path.join(CASES, f"case-{c:05d}.json"), "w", encoding="utf-8").write(dumps(cf))
    d = cf["dispute"]
    index.append({"case_no": c, "dispute_id": d["dispute_id"], "trip_id": d["trip_id"], "category": d["category"], "file": f"cases/case-{c:05d}.json"})
    key[str(c)] = g; seeds[str(c)] = s["seed"]
    eval_index.append({"case_no": c, "category": d["category"], "expected_ruling": g["expected_ruling"], "expected_amount_sgd": g["expected_amount_sgd"],
                       "expected_driver_compensation_sgd": g["expected_driver_compensation_sgd"], "expected_referrals": g["expected_referrals"], "difficulty": g["difficulty"]})
open(os.path.join(OUT,"data","wild","index.json"),"w").write(dumps(index))
open(os.path.join(ANS,"ground_truth.json"),"w").write(dumps(key))
open(os.path.join(ANS,"eval_index.json"),"w").write(dumps(eval_index))
open(os.path.join(ANS,"seed_map.json"),"w").write(dumps(seeds))
print(f"wrote {len(index)} cases")
