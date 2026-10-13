"""Write the case set from build/cases_rd.py and build/cases_ns.py.

usage: python3 build/generate.py --out DIR [--only rd|ns] [--strict] [--no-check]

Each case module exposes build() -> list of (case_dict, key_record). A module that does not exist yet is
treated as empty. Output:
  DIR/cases/case-0NNNN.json, index.json, CANARY.txt, README.md
  DIR/answers/ground_truth.json   (plus check logs; nothing answer-bearing is printed to stdout)
--strict additionally requires all 30 cases and the BRIEF section 2 / 3 set targets (details of any miss go to
DIR/answers/targets_check.json, never to stdout).
"""
import argparse
import glob
import hashlib
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys

BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BUILD_DIR)
if BUILD_DIR not in sys.path:
    sys.path.insert(0, BUILD_DIR)

import common as C  # noqa: E402

MARKER_VALUE = "1d037756-aad8-411b-96ea-3a2f5c0dc497"  # fixed at authoring time; written to cases/CANARY.txt

MODULES = (("rd", "cases_rd", C.RD, C.RD_RANGE), ("ns", "cases_ns", C.NS, C.NS_RANGE))

README = """\
# Ride-hail dispute cases, schema 1.2.0

This directory holds 30 ride-hail dispute cases for an automated arbitration
system on a Singapore ride-hail platform.

- 15 ROUTE_DEVIATION cases: case numbers 4001 to 4015.
- 15 NO_SHOW_CHARGE cases: case numbers 4051 to 4065.
- One file per case, `case-0NNNN.json`, with top-level keys `schema_version`
  ("1.2.0"), `case_no`, `dispute` and `evidence`. `index.json` lists every case
  with its dispute id, trip id, category, file name and the SHA-256 of the file
  bytes.
- A plain-text marker file in this directory holds one random identifier
  string; it marks this material so that its reappearance elsewhere can be
  detected.

## Policy in force

Policy version 6: the three base files `general.json`, `no_show.json` and
`route_deviation.json`, with the amendments `0001-pol-ns-11.json`,
`0002-pol-rd-14.json` and `0003-pol-ns-12.json` applied on top of them.

## Format check

    python3 check_set.py <this directory> --range 4001 4065

The checker tests format only. The answers are kept separately and are not part
of this directory.

## Protocol

One run from the 2026-10-11 freeze; any tuning on this set afterwards turns it
into a development set.
"""

# Static determinism lint: clocks, unseeded randomness, entropy sources.
_BAD_CALLS = [
    re.compile(r"\bdatetime\.(now|utcnow|today)\("),
    re.compile(r"\bdate\.today\("),
    re.compile(r"\btime\.(time|time_ns|monotonic|perf_counter|localtime|gmtime|ctime)\("),
    re.compile(r"\buuid\.uuid[1-5]\("),
    re.compile(r"\bos\.urandom\("),
    re.compile(r"\bsecrets\."),
    re.compile(r"\bSystemRandom\b"),
    re.compile(r"(?<![\w.])random\.(random|randint|uniform|choice|choices|shuffle|gauss|sample|randrange|seed|"
               r"getrandbits|triangular|normalvariate|betavariate|expovariate)\("),
    re.compile(r"\bfrom\s+random\s+import\s+(?!Random\b)"),
    re.compile(r"random\.Random\(\s*\)"),
]


def static_lint():
    probs = []
    for path in sorted(glob.glob(os.path.join(BUILD_DIR, "*.py"))):
        base = os.path.basename(path)
        if base.startswith("test_"):
            continue
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                code = line.split("#", 1)[0] if "lint-ok" not in line else ""
                for rx in _BAD_CALLS:
                    if rx.search(code):
                        probs.append("{0}:{1}: nondeterministic call {2!r}".format(base, i, rx.search(code).group(0)))
    return probs


def load_module(name):
    if importlib.util.find_spec(name) is None:
        return None
    return importlib.import_module(name)


def collect(only):
    """[(case, key)] from the case modules, checked for range / category / shape."""
    items, seen = [], set()
    for tag, name, cat, (lo, hi) in MODULES:
        if only and only != tag:
            continue
        mod = load_module(name)
        if mod is None:
            continue
        built = mod.build()
        assert isinstance(built, list), "{0}.build() must return a list".format(name)
        for pair in built:
            assert isinstance(pair, tuple) and len(pair) == 2, "{0}.build() items are (case, key) pairs".format(name)
            case, key = pair
            n = case.get("case_no")
            assert isinstance(n, int) and lo <= n <= hi, "{0}: case_no {1} outside {2}-{3}".format(name, n, lo, hi)
            assert case["dispute"]["category"] == cat, "{0}: case {1} category".format(name, n)
            assert n not in seen, "duplicate case_no {0}".format(n)
            assert key.get("case_no") == n, "{0}: key record case_no does not match case {1}".format(name, n)
            seen.add(n)
            items.append((case, key))
    items.sort(key=lambda p: p[0]["case_no"])
    return items


def render(items):
    """{relative path: bytes} for every output file."""
    out = {}
    index = []
    for case, _ in items:
        n = case["case_no"]
        fname = "case-{0:05d}.json".format(n)
        data = C.dumps_case(case).encode("ascii")
        out["cases/" + fname] = data
        index.append({"case_no": n, "dispute_id": case["dispute"]["dispute_id"],
                      "trip_id": case["dispute"]["trip_id"], "category": case["dispute"]["category"],
                      "file": fname, "sha256": hashlib.sha256(data).hexdigest()})
    out["cases/index.json"] = (json.dumps(index, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    out["cases/CANARY.txt"] = MARKER_VALUE.encode("ascii")
    out["cases/README.md"] = README.encode("ascii")
    keys = sorted((k for _, k in items), key=lambda r: r["case_no"])
    out["answers/ground_truth.json"] = (json.dumps(keys, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    return out


def digest(files):
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(k.encode("ascii") + b"\0" + files[k] + b"\0")
    return h.hexdigest()


def validate(items):
    """(case_problems, key_problems) - key problems may reveal answers and are never printed."""
    case_probs, key_probs = [], []
    ev_seen = set()
    for case, key in items:
        case_probs += C.validate_case(case) + C.lint_case(case)
        for e in case["evidence"]:
            if e["evidence_id"] in ev_seen:
                case_probs.append("duplicate evidence id {0}".format(e["evidence_id"]))
            ev_seen.add(e["evidence_id"])
        key_probs += C.validate_key(key, case)
    return case_probs, key_probs


def targets(items):
    """BRIEF section 2 / 3 targets; returns {name: ok?} plus detail (kept out of stdout)."""
    gts = [k["ground_truth"] for _, k in items]
    cases = [c for c, _ in items]
    rul = {r: sum(1 for g in gts if g["expected_ruling"] == r) for r in C.RULINGS}
    dif = {x: sum(1 for g in gts if g["difficulty"] == x) for x in C.DIFFICULTIES}
    issues = set()
    missing_chat = False
    for c in cases:
        for e in c["evidence"]:
            issues.update(e["admissibility"]["issues"])
            if e["evidence_type"] == "CHAT_LOG" and e["payload"] is None:
                missing_chat = True
    need_codes = ["GPS_GAP", "LOW_SAMPLE_RATE", "GPS_DRIFT", "CLOCK_SKEW", "TRUNCATED_LOG", "STALE_SNAPSHOT",
                  "CROSS_SOURCE_CONFLICT", "ADVISORY_UNCORROBORATED"]
    esc_indet = sum(1 for g in gts if g["expected_ruling"] == "ESCALATE" and g["difficulty"] == "INDETERMINATE")
    detail = {
        "count_30": len(items) == 30,
        "rd_15": sum(1 for c in cases if c["dispute"]["category"] == C.RD) == 15,
        "ns_15": sum(1 for c in cases if c["dispute"]["category"] == C.NS) == 15,
        "driver_filed_at_least_10": sum(1 for c in cases if c["dispute"]["filed_by"] == "DRIVER") >= 10,
        "rulings": rul == {"FULL_REFUND": 6, "PARTIAL_REFUND": 5, "NO_ACTION": 6, "DRIVER_COMPENSATION": 6,
                           "ESCALATE": 7},
        "difficulties": dif == {"EASY": 7, "HARD": 11, "REVERSAL": 7, "INDETERMINATE": 5},
        "escalate_split_5_2": esc_indet == 5 and rul["ESCALATE"] - esc_indet == 2,
        "issue_codes_covered": all(code in issues for code in need_codes),
        "missing_chat_log_present": missing_chat,
        "both_categories_vary": all(
            len({k["ground_truth"]["expected_ruling"] for c, k in items if c["dispute"]["category"] == cat}) >= 3
            and len({c["dispute"]["filed_by"] for c, k in items if c["dispute"]["category"] == cat}) == 2
            and len({k["ground_truth"]["difficulty"] for c, k in items if c["dispute"]["category"] == cat}) >= 3
            for cat in C.CATEGORIES),
    }
    info = {"ok": detail, "rulings": rul, "difficulties": dif, "escalate_indeterminate": esc_indet,
            "issue_codes_missing": [code for code in need_codes if code not in issues]}
    return detail, info


def run_check_set(out_dir, cats_present):
    cases_dir = os.path.join(out_dir, "cases")
    gt = os.path.join(out_dir, "answers", "ground_truth.json")
    res = subprocess.run([sys.executable, os.path.join(ROOT_DIR, "ref", "check_set.py"), cases_dir, gt,
                          "--range", "4001", "4065"], capture_output=True, text=True)
    log = os.path.join(out_dir, "answers", "check_set.log")
    with open(log, "w", encoding="ascii", errors="replace") as f:
        f.write(res.stdout + res.stderr)
    fails = [l for l in res.stdout.splitlines() if l.startswith("FAIL") or l.startswith("WARN")]
    if res.returncode not in (0, 1) or res.stderr.strip():
        fails.append("FAIL check_set crashed (see log)")
    if cats_present < 2:
        fails = [l for l in fails if l != "FAIL set: both categories are required"]
    case_fails = [l for l in fails if not l.startswith(("FAIL key", "WARN"))]
    key_fails = [l for l in fails if l.startswith(("FAIL key", "WARN"))]
    return case_fails, key_fails, log


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=False)
    ap.add_argument("--only", choices=("rd", "ns"))
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--no-check", action="store_true", help="skip the check_set run and the subprocess rebuild")
    ap.add_argument("--digest-only", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    if a.digest_only:
        print(digest(render(collect(a.only))))
        return 0
    if not a.out:
        ap.error("--out DIR is required")

    probs = static_lint()
    assert not probs, "determinism lint:\n" + "\n".join(probs)

    items = collect(a.only)
    files = render(items)
    # determinism 1: a second in-process build gives identical bytes
    files2 = render(collect(a.only))
    assert files == files2, "build() is not deterministic within one process"
    # determinism 2: a fresh interpreter with another hash seed gives identical bytes
    if not a.no_check:
        env = dict(os.environ, PYTHONHASHSEED="4242")
        cmd = [sys.executable, os.path.abspath(__file__), "--digest-only"] + (["--only", a.only] if a.only else [])
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT_DIR)
        assert res.returncode == 0, "subprocess rebuild failed:\n" + res.stderr[-2000:]
        assert res.stdout.strip() == digest(files), "build differs across interpreters / hash seeds"

    # ASCII + forbidden words on everything shipped in cases/; ASCII on the answers
    for path, data in files.items():
        text = data.decode("ascii")  # raises on any non-ASCII byte
        if path.startswith("cases/"):
            hits = C.forbidden_hits(text)
            assert not hits, "{0}: forbidden word(s) {1}".format(path, hits)

    case_probs, key_probs = validate(items)
    out_dir = os.path.abspath(a.out)
    os.makedirs(os.path.join(out_dir, "cases"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "answers"), exist_ok=True)
    key_log = os.path.join(out_dir, "answers", "key_problems.log")
    if key_probs:
        with open(key_log, "w", encoding="ascii", errors="replace") as f:
            f.write("\n".join(key_probs) + "\n")
    elif os.path.exists(key_log):
        os.remove(key_log)
    if case_probs or key_probs:
        for p in case_probs:
            print("CASE PROBLEM", p)
        if key_probs:
            print("KEY PROBLEMS: {0}, details in {1}".format(len(key_probs), key_log))
        return 1

    # write (stale case files from an earlier run are removed first)
    for old in glob.glob(os.path.join(out_dir, "cases", "case-*.json")):
        os.remove(old)
    for rel, data in files.items():
        with open(os.path.join(out_dir, rel), "wb") as f:
            f.write(data)
    print("wrote {0} case(s) to {1}".format(len(items), os.path.join(out_dir, "cases")))

    rc = 0
    if items and not a.no_check:
        cats = len({c["dispute"]["category"] for c, _ in items})
        case_fails, key_fails, log = run_check_set(out_dir, cats)
        for l in case_fails:
            print("check_set:", l)
        if key_fails:
            print("check_set: {0} answer-key finding(s), details in {1}".format(len(key_fails), log))
        print("check_set: {0} case failure(s), {1} key finding(s)".format(len(case_fails), len(key_fails)))
        rc = 1 if case_fails or key_fails else 0

    if a.strict:
        ok, info = targets(items)
        tpath = os.path.join(out_dir, "answers", "targets_check.json")
        with open(tpath, "w", encoding="ascii") as f:
            f.write(json.dumps(info, indent=2) + "\n")
        bad = [k for k, v in ok.items() if not v]
        print("targets: {0}".format("ok" if not bad else "NOT MET ({0}), details in {1}".format(", ".join(bad),
                                                                                              tpath)))
        rc = rc or (1 if bad else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
