"""Format check for a Tribunal sealed set. Checks format only, never whether an answer is right.

usage: python3 check_set.py <case_dir> [<ground_truth.json>] [--range 801 899]
"""
import glob, hashlib, json, math, os, re, sys
from datetime import datetime

LIC = {"POL-GEN-01": "", "POL-GEN-02": "E", "POL-GEN-03": "FPNDE", "POL-GEN-04": "", "POL-GEN-05": "",
       "POL-GEN-06": "", "POL-GEN-07": "E", "POL-GEN-08": "", "POL-NS-01": "NDF", "POL-NS-02": "FN",
       "POL-NS-03": "FD", "POL-NS-04": "FN", "POL-NS-05": "FN", "POL-NS-06": "FN", "POL-NS-07": "DNE",
       "POL-NS-08": "PE", "POL-NS-09": "E", "POL-NS-10": "FND", "POL-NS-11": "", "POL-NS-12": "",
       "POL-RD-01": "NP", "POL-RD-02": "PFN", "POL-RD-03": "NP", "POL-RD-04": "NPD", "POL-RD-05": "NP",
       "POL-RD-06": "FP", "POL-RD-07": "EPN", "POL-RD-08": "NPE", "POL-RD-09": "PN", "POL-RD-10": "E",
       "POL-RD-11": "NPFE", "POL-RD-12": "NP", "POL-RD-13": "FPN", "POL-RD-14": "PFN"}
RUL = {"FULL_REFUND": "F", "PARTIAL_REFUND": "P", "NO_ACTION": "N", "DRIVER_COMPENSATION": "D", "ESCALATE": "E"}
CODES = {"MISSING_ARTIFACT", "CROSS_SOURCE_CONFLICT", "TRUNCATED_LOG", "PARTIAL_RECORD", "STALE_SNAPSHOT",
         "CONTENT_REDACTED", "LOW_SAMPLE_RATE", "LANGUAGE_AMBIGUITY", "UNREAD_MESSAGE", "SCHEMA_VERSION_MISMATCH",
         "GPS_GAP", "LOW_COVERAGE", "GPS_DRIFT", "IMPLAUSIBLE_SPEED", "ADVISORY_UNCORROBORATED",
         "UNVERIFIED_SOURCE", "CLOCK_SKEW"}
TOK = {"TRIP_RECORD": "TRIP", "GPS_TRACE": "GPS", "CHAT_LOG": "CHAT", "FARE_BREAKDOWN": "FARE",
       "RIDER_PROFILE": "RPROF", "DRIVER_PROFILE": "DPROF", "TRAFFIC_ADVISORY": "ADVIS"}
SOURCES = {"PLATFORM_TELEMETRY", "PAYMENTS_LEDGER", "THIRD_PARTY_LTA", "DRIVER_DEVICE", "USER_SUBMITTED"}
DISPUTE = {"case_no", "dispute_id", "trip_id", "category", "filed_at", "filed_by", "channel",
           "amount_contested_sgd", "claim_text", "counterparty_statement", "evidence_ids"}
PP = {"grace_after_match_sec", "advance_grace_before_scheduled_sec", "free_wait_sec", "no_show_threshold_sec",
      "cancellation_fee_sgd", "rider_gross_cancellation_fee_sgd", "waiting_fee_sgd", "fee_goes_to",
      "arrival_marker", "source"}
FORBIDDEN = ("ground_truth", "expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd",
             "expected_referrals", "governing_clauses", "difficulty", "rationale", "canary", "sealed")
CJK = re.compile("[" + "".join(chr(a) + "-" + chr(b) for a, b in ((0x3000, 0x303F), (0x3040, 0x30FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF))) + "]")
fails = []


def F(where, msg):
    fails.append("{0}: {1}".format(where, msg))


def ts(s):
    return datetime.fromisoformat(s)


def km(a, b):
    r = 6371.0088
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lng"] - a["lng"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def text_rules(where, text, extra=()):
    if CJK.search(text):
        F(where, "CJK or full-width character present")
    for w in FORBIDDEN + tuple(extra):
        if w in text.lower():
            F(where, "forbidden word {0!r}".format(w))


def check_case(path, lo, hi):
    raw = open(path, encoding="utf-8").read()
    text_rules(os.path.basename(path), raw)
    c = json.loads(raw)
    n = c.get("case_no")
    w = "case {0}".format(n)
    if set(c) != {"schema_version", "case_no", "dispute", "evidence"}:
        F(w, "top-level keys {0}".format(sorted(c)))
    if c.get("schema_version") != "1.2.0":
        F(w, "schema_version must be 1.2.0")
    if not (isinstance(n, int) and lo <= n <= hi):
        F(w, "case_no outside {0}-{1}".format(lo, hi))
    if os.path.basename(path) != "case-{0:05d}.json".format(n):
        F(w, "filename does not match case_no")
    d = c["dispute"]
    if not DISPUTE <= set(d) or set(d) - DISPUTE - {"safety_flag", "complaint_flag"}:
        F(w, "dispute keys {0}".format(sorted(d)))
    if d.get("case_no") != n or d.get("dispute_id") != "DSP-{0:05d}".format(n) or d.get("trip_id") != "TRP-{0:05d}".format(n):
        F(w, "dispute case_no / DSP- / TRP- ids")
    if d.get("category") not in ("ROUTE_DEVIATION", "NO_SHOW_CHARGE"):
        F(w, "category")
    if d.get("filed_by") not in ("RIDER", "DRIVER"):
        F(w, "filed_by")
    cs = d.get("counterparty_statement")
    if cs is not None and set(cs) != {"text", "submitted_by", "submitted_at"}:
        F(w, "counterparty_statement must be null or {text, submitted_by, submitted_at}")
    ev = c["evidence"]
    ids = [e["evidence_id"] for e in ev]
    if d.get("evidence_ids") != ids:
        F(w, "dispute.evidence_ids must list every evidence_id in file order")
    types = [e["evidence_type"] for e in ev]
    order = list(TOK)
    if [order.index(t) for t in types] != sorted(order.index(t) for t in types):
        F(w, "evidence not in canonical order")
    for t in order[:6]:
        if types.count(t) != 1:
            F(w, "{0} must appear exactly once".format(t))
    if types.count("TRAFFIC_ADVISORY") not in (1, 2):
        F(w, "one or two TRAFFIC_ADVISORY")
    by = {}
    adv = 0
    for e in ev:
        eid = e["evidence_id"]
        by[e["evidence_type"]] = e
        if set(e) != {"evidence_id", "evidence_type", "admissibility", "payload", "schema_version", "source", "trip_id", "generated_at"}:
            F(eid, "artifact keys {0}".format(sorted(e)))
        want = "EV-{0}-{1:05d}".format(TOK[e["evidence_type"]], n)
        if e["evidence_type"] == "TRAFFIC_ADVISORY":
            adv += 1
            want += "-{0:02d}".format(adv)
        if eid != want:
            F(eid, "evidence_id should be {0}".format(want))
        if e["trip_id"] != "TRP-{0:05d}".format(n):
            F(eid, "trip_id")
        if e["source"] not in SOURCES:
            F(eid, "source")
        a = e["admissibility"]
        for k in ("status", "issues", "weight_multiplier", "notes", "assessed_at", "assessor_version"):
            if k not in a:
                F(eid, "admissibility lacks {0}".format(k))
        st, iss = a.get("status"), a.get("issues", [])
        for code in iss:
            if code not in CODES:
                F(eid, "issue code {0} is not in the version-6 table".format(code))
        if st == "COMPLETE" and (iss or a.get("weight_multiplier") != 1.0 or e["payload"] is None):
            F(eid, "COMPLETE needs issues [], weight 1.0, a payload")
        if st == "MISSING" and (iss != ["MISSING_ARTIFACT"] or a.get("weight_multiplier") != 0.0 or e["payload"] is not None):
            F(eid, "MISSING needs issues [MISSING_ARTIFACT], weight 0.0, payload null")
        if st == "IMPAIRED" and (not iss or "MISSING_ARTIFACT" in iss or e["payload"] is None):
            F(eid, "IMPAIRED needs at least one non-missing code and a payload")
        if st not in ("COMPLETE", "IMPAIRED", "MISSING"):
            F(eid, "status")
        for dd in a.get("issue_details", []):
            if set(dd) < {"code", "severity", "detail"} or dd["code"] not in iss:
                F(eid, "issue_details entry")
    trip = by["TRIP_RECORD"]["payload"]
    fare = by["FARE_BREAKDOWN"]["payload"]
    gps = by["GPS_TRACE"]["payload"]
    chat = by["CHAT_LOG"]["payload"]
    if trip is None or fare is None:
        F(w, "TRIP_RECORD and FARE_BREAKDOWN must not be missing in a sealed case (RD-10(2) aside, write it on purpose)")
        return n, d
    if d["category"] == "NO_SHOW_CHARGE":
        pp = trip.get("platform_policy")
        if not isinstance(pp, dict) or set(pp) != PP:
            F(w, "a no-show trip_record carries platform_policy with exactly its ten keys")
    seq = [trip.get(k) for k in ("requested_at", "accepted_at", "arrived_at", "started_at", "ended_at", "cancelled_at")]
    seq = [s for s in seq if s]
    if any(ts(seq[i]) > ts(seq[i + 1]) for i in range(len(seq) - 1)) and "CLOCK_SKEW" not in by["TRIP_RECORD"]["admissibility"]["issues"]:
        F(w, "trip timestamps run backwards")
    tot = sum(fare[k] for k in ("base_fare", "distance_fare", "time_fare", "surge_amount", "tolls_erp", "airport_surcharge",
                                 "platform_fee", "cancellation_fee", "waiting_time_fee")) - fare["promo_discount"]
    if abs(tot - fare["total_charged"]) > 0.05:
        F(w, "fare lines sum to {0:.2f}, total_charged {1}".format(tot, fare["total_charged"]))
    if abs(fare["tolls_erp"] - sum(g["amount_sgd"] for g in fare.get("erp_gantries") or [])) > 0.005:
        F(w, "tolls_erp != sum of erp_gantries")
    if not (0 < d["amount_contested_sgd"] <= fare["total_charged"]):
        F(w, "amount_contested_sgd must be > 0 and <= total_charged")
    if gps:
        pts = gps["points"]
        if gps["point_count"] != len(pts):
            F(w, "point_count")
        if any(ts(pts[i]["ts"]) >= ts(pts[i + 1]["ts"]) for i in range(len(pts) - 1)):
            F(w, "gps ts not strictly increasing")
        dist = sum(km(pts[i - 1], pts[i]) for i in range(1, len(pts)))
        if abs(dist - gps["trace_distance_km"]) > 0.02:
            F(w, "trace_distance_km {0} but points measure {1:.2f}".format(gps["trace_distance_km"], dist))
    if chat:
        msgs = chat["messages"]
        if chat["message_count"] != len(msgs):
            F(w, "chat message_count")
        for k, m in enumerate(msgs, 1):
            if m["msg_id"] != "MSG-{0:05d}-{1:03d}".format(n, k) and "TRUNCATED_LOG" not in by["CHAT_LOG"]["admissibility"]["issues"]:
                F(w, "msg_id sequence at {0}".format(m["msg_id"]))
    return n, d


def check_key(path, disputes):
    raw = open(path, encoding="utf-8").read()
    if CJK.search(raw):
        F("key", "CJK or full-width character present")
    key = json.loads(raw)
    seen = set()
    for r in key:
        n = r["case_no"]
        w = "key {0}".format(n)
        seen.add(n)
        if n not in disputes:
            F(w, "no case file")
            continue
        if set(r) != {"case_no", "dispute_id", "ground_truth"} or r["dispute_id"] != "DSP-{0:05d}".format(n):
            F(w, "record keys / dispute_id")
        g = r["ground_truth"]
        if set(g) != {"expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd", "expected_referrals",
                      "governing_clauses", "difficulty", "rationale"}:
            F(w, "ground_truth keys {0}".format(sorted(g)))
        ru, am, dc = g["expected_ruling"], g["expected_amount_sgd"], g["expected_driver_compensation_sgd"]
        con = disputes[n]["amount_contested_sgd"]
        if ru not in RUL:
            F(w, "ruling")
        if ru == "FULL_REFUND" and am != con:
            F(w, "FULL_REFUND amount must equal amount_contested_sgd {0}".format(con))
        if ru == "PARTIAL_REFUND" and not (am and am > 0):
            F(w, "PARTIAL_REFUND amount must be > 0")
        if ru == "PARTIAL_REFUND" and am and am >= con:
            print("WARN {0}: PARTIAL_REFUND {1} is not below amount_contested_sgd {2}; check the claim".format(w, am, con))
        if ru in ("NO_ACTION", "ESCALATE") and (am is not None or dc is not None):
            F(w, "NO_ACTION / ESCALATE carry null amounts")
        if ru == "DRIVER_COMPENSATION" and (not am or dc != am):
            F(w, "DRIVER_COMPENSATION: amount == driver_compensation > 0")
        if ru in ("FULL_REFUND", "PARTIAL_REFUND") and dc is not None and dc <= 0:
            F(w, "driver_compensation must be null or > 0")
        for v in ((am, dc) if ru != "FULL_REFUND" else (dc,)):
            if v is not None and abs(round(v * 20) - v * 20) > 1e-6:
                F(w, "amount {0} is not a multiple of 0.05".format(v))
        if g["difficulty"] not in ("EASY", "HARD", "REVERSAL", "INDETERMINATE"):
            F(w, "difficulty")
        if g["difficulty"] == "INDETERMINATE" and ru != "ESCALATE":
            F(w, "INDETERMINATE must be ESCALATE")
        cls = g["governing_clauses"]
        if not cls or any(c not in LIC for c in cls):
            F(w, "governing_clauses must be version-6 clause ids")
        elif not any(RUL.get(ru, "?") in LIC[c] for c in cls) and not any(c.startswith("POL-GEN-08") for c in cls):
            F(w, "no governing clause licenses {0}".format(ru))
        for ref in g["expected_referrals"]:
            if not re.search(r"POL-[A-Z]{2,4}-[0-9]{2}", ref):
                F(w, "a referral must name a clause")
        if not (120 <= len(g["rationale"]) <= 2500):
            F(w, "rationale length")
        if not re.search(r"EV-[A-Z]+-{0:05d}".format(n), g["rationale"]) or not re.search(r"POL-[A-Z]+-\d\d", g["rationale"]):
            F(w, "rationale must name an evidence id of this case and a clause")
    if seen != set(disputes):
        F("key", "cases without an answer: {0}".format(sorted(set(disputes) - seen)))


def main(argv):
    lo, hi = 801, 899
    if "--range" in argv:
        i = argv.index("--range")
        lo, hi = int(argv[i + 1]), int(argv[i + 2])
        argv = argv[:i] + argv[i + 3:]
    root = argv[0]
    for name in ("index.json", "CANARY.txt", "README.md"):
        if not os.path.isfile(os.path.join(root, name)):
            F("set", "{0} missing".format(name))
    for name in ("CANARY.txt", "README.md"):
        p = os.path.join(root, name)
        if os.path.isfile(p) and CJK.search(open(p, encoding="utf-8").read()):
            F(name, "CJK or full-width character present")
    disputes = {}
    for path in sorted(glob.glob(os.path.join(root, "case-*.json"))):
        n, d = check_case(path, lo, hi)
        disputes[n] = d
    if os.path.isfile(os.path.join(root, "index.json")):
        raw = open(os.path.join(root, "index.json"), encoding="utf-8").read()
        text_rules("index.json", raw)
        idx = json.loads(raw)
        if sorted(e["case_no"] for e in idx) != sorted(disputes):
            F("index.json", "entries do not match the case files")
        for e in idx:
            if set(e) != {"case_no", "dispute_id", "trip_id", "category", "file", "sha256"}:
                F("index.json", "entry keys for {0}".format(e.get("case_no")))
                continue
            p = os.path.join(root, e["file"])
            if e["file"] != "case-{0:05d}.json".format(e["case_no"]) or not os.path.isfile(p):
                F("index.json", "file for {0}".format(e["case_no"]))
            elif hashlib.sha256(open(p, "rb").read()).hexdigest() != e["sha256"]:
                F("index.json", "sha256 for {0} does not match the file".format(e["case_no"]))
            elif disputes[e["case_no"]]["category"] != e["category"]:
                F("index.json", "category for {0}".format(e["case_no"]))
    cats = [d["category"] for d in disputes.values()]
    if len(set(cats)) < 2:
        F("set", "both categories are required")
    if len(argv) > 1:
        check_key(argv[1], disputes)
    for f in fails:
        print("FAIL", f)
    print("{0} case(s), {1} failure(s)".format(len(disputes), len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
