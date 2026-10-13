"""Compare second-reading answers (one answer.json per case folder) with a set's key.

usage: python3 compare_second_reading.py <ground_truth.json> <second_reading_dir> [--detail N ...]

Prints counts and the case numbers that differ on ruling, amount, driver compensation or the
set of clauses named in referrals. With --detail, prints both answers for the listed cases.
"""
import json
import os
import re
import sys


def ref_clauses(refs):
    return sorted({m for r in refs for m in re.findall(r"POL-[A-Z]{2,4}-\d\d", r)})


def main(argv):
    key = {r["case_no"]: r["ground_truth"] for r in json.load(open(argv[0]))}
    root = argv[1]
    detail = [int(x) for x in argv[argv.index("--detail") + 1:]] if "--detail" in argv else []
    diffs, missing = {}, []
    for n, g in sorted(key.items()):
        p = os.path.join(root, str(n), "answer.json")
        if not os.path.isfile(p):
            missing.append(n)
            continue
        a = json.load(open(p))
        why = []
        if a.get("expected_ruling") != g["expected_ruling"]:
            why.append("ruling")
        if a.get("expected_amount_sgd") != g["expected_amount_sgd"]:
            why.append("amount")
        if a.get("expected_driver_compensation_sgd") != g["expected_driver_compensation_sgd"]:
            why.append("driver_comp")
        if ref_clauses(a.get("expected_referrals") or []) != ref_clauses(g["expected_referrals"]):
            why.append("referrals")
        if why:
            diffs[n] = why
        if n in detail:
            print("=== {0}\nKEY   : {1} {2} {3} {4}\nSECOND: {5} {6} {7} {8}\nSECOND reasoning: {9}\n".format(
                n, g["expected_ruling"], g["expected_amount_sgd"], g["expected_driver_compensation_sgd"], g["expected_referrals"],
                a.get("expected_ruling"), a.get("expected_amount_sgd"), a.get("expected_driver_compensation_sgd"),
                a.get("expected_referrals"), a.get("reasoning")))
    print("compared {0}, missing {1}, differing {2}".format(len(key) - len(missing), missing, len(diffs)))
    for n, why in diffs.items():
        print("  {0}: {1}".format(n, ",".join(why)))


if __name__ == "__main__":
    main(sys.argv[1:])
