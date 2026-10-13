"""Independent audit of the generated NO_SHOW_CHARGE cases 4051-4065.

usage: python3 build/audit_ns.py <DIR>      (reads DIR/cases/case-04051.json ... and DIR/answers/ground_truth.json)

Reads only the generated files, ref/no_show.json (radii, accuracy filter, integrity weights, rates, fee tables) and,
for what each case is meant to show, build/blueprint_ns.json (intent and the designed measurements). It does not
import common.py, cases_ns.py or ns_geo.py: every measurement is re-derived here from the written files with its own
haversine (R = 6371.0088 km) and Decimal money, and a decision is re-derived from the version-6 clauses:

  - file arithmetic: point_count, trace_distance_km (3 dp), fare lines sum to total_charged, tolls = gantries,
    refund = total when REFUNDED, 0 < contested <= total, chat counts, IMPAIRED weight = integrity product (GPS_GAP
    graded from the measured gap), MISSING / COMPLETE blocks, waypoint_hint distances and ERP gantry crossings (none
    expected in this category, checked if present);
  - POL-NS-02 qualifying fixes (>= 3 consecutive, accuracy <= 25 m, inside the zone radius), the first qualifying
    fix, the dwell from it to the termination and its continuity; the 15-minute look-back; POL-NS-03's 400 m band;
  - POL-NS-04 limbs (locating messages from a content table, replies within 120 s, calls, rider presence majority over
    accuracy-qualifying rider fixes; undecidable when none qualify);
  - POL-NS-05 at the arrived event (> 300 m or >= 15 km/h) with the clock recomputed from the first qualifying fix;
  - POL-NS-06 runs, the advisory summation and the generous run brackets (capped at the termination); POL-NS-07
    anti-farming and the 80 % net payout; POL-NS-03(ii) 50 %;
  - POL-NS-08 limbs (a) to (d); POL-NS-10 grace, (d), (f) exceptions, (g); POL-NS-12 events; POL-GEN-02(2) floor;
and asserts the derived ruling, amount, compensation and referrals equal both the blueprint's intent and the key,
that the designed measurements equal the re-derived ones, and that the rationale states the deciding figures.
Prints one line per finding and a summary; exit status 1 when anything fails.
"""
import glob
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R_KM = 6371.0088

with open(os.path.join(ROOT, "ref", "no_show.json"), encoding="utf-8") as _f:
    NSP = json.load(_f)
FS = NSP["fee_schedule"]
WEIGHTS = NSP["integrity"]["weights"]
FLOOR = Decimal(str(NSP["confidence_floor"]))
RADIUS = FS["arrival_radius_m"]
PRESENCE = FS["rider_presence_radius_m"]
ACC = FS["gps_accuracy_filter_m"]
CEILING = FS["wrong_entrance_ceiling_m"]
COMP = Decimal(str(FS["driver_compensation_rate"]))
GOODWILL = Decimal(str(FS["pin_ambiguity_goodwill_rate"]))
GAP_POLICY = NSP["integrity"]["gps_gap_policy_threshold_sec"]

# Clause figures (version 6 text).
REPLY_S, FALSE_D, FALSE_V, SKEW_S, MIN_FIXES, CHAT_GAP_S = 120, 300, 15, 90, 6, 300
FARM_N, FARM_RATE, LEASH, LOOKBACK, ETA_SLACK = 4, Decimal("0.08"), 300, 900, 180
NS06_TYPES = ("KERB_RESTRICTION", "ENFORCEMENT", "CLOSURE", "ACCIDENT")

# Content readings of the chat (what a message says cannot be measured): rider messages that are locating or
# coordinating (POL-NS-04(a)); whether either party named an entrance, block, tower or bay (POL-NS-03(i)); driver
# requests to cancel and vehicle / driver mismatches (POL-NS-10(f)).
LOCATING = {4051: (2, 3), 4055: (4,), 4056: (2, 4), 4058: (3,), 4059: (5,), 4062: (3, 5), 4064: (3,), 4065: (2, 5)}
SUBLOCATION_NAMED = {4056: False}
CANCEL_REQUEST, VEHICLE_MISMATCH = {}, {}
# Party statements that must not assert a late or delayed arrival the record disproves (r1 second reading, 4052: the
# rider's statement is not meant to be a story the record contradicts). Checked as a content reading of the words.
NO_LATENESS_CLAIM = {4052: ("counterparty_statement",)}
LATENESS_WORDS = ("late", "took very long", "took long", "stuck", "delay", "slow", "jam")

FAILS = []
CHECKS = [0]


def check(cond, n, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append("FAIL {0}: {1}".format(n, what))
    return cond


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def T(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z").timestamp()


SGT = timezone(timedelta(hours=8))


def hms(s):
    return s[11:19]


def iso(sec):
    return datetime.fromtimestamp(sec, tz=SGT).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R_KM * math.asin(math.sqrt(h))


def m_(a, b):
    return km(a, b) * 1000.0


def r1(x):
    return round(x + 0.0, 1)


def D(x):
    return Decimal(str(x))


def cents(x):
    return D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def between(pts, a, b):
    return [p for p in pts if (a is None or T(p["ts"]) >= T(a)) and (b is None or T(p["ts"]) <= T(b))]


def ok_acc(p):
    return p.get("accuracy_m") is not None and p["accuracy_m"] <= ACC


def first_qualifying(pts, pin, rad, upto):
    run = []
    for p in between(pts, None, upto):
        if ok_acc(p) and m_(p, pin) <= rad:
            run.append(p)
            if len(run) >= 3:
                return run[0]
        else:
            run = []
    return None


def runs_inside(pts, pin, rad, a, b):
    out, run = [], []
    for p in between(pts, a, b):
        if ok_acc(p) and m_(p, pin) <= rad:
            run.append(p)
        else:
            if run:
                out.append(run)
            run = []
    if run:
        out.append(run)
    return out


def weight_product(issues, grade=None):
    prod = Decimal(1)
    for c in issues:
        prod *= D(WEIGHTS["GPS_GAP_" + grade] if c == "GPS_GAP" else WEIGHTS[c])
    return prod


def art(case, etype, seq=None):
    for a in case["evidence"]:
        if a["evidence_type"] == etype and (seq is None or a["evidence_id"].endswith("-{0:02d}".format(seq))):
            return a
    return None


# ---------------------------------------------------------------------------
# file arithmetic
# ---------------------------------------------------------------------------
def file_checks(n, case):
    trip = art(case, "TRIP_RECORD")["payload"]
    gps_a = art(case, "GPS_TRACE")
    gps = gps_a["payload"]
    pts = gps["points"]
    check(gps["point_count"] == len(pts), n, "point_count")
    check(all(T(pts[i]["ts"]) > T(pts[i - 1]["ts"]) for i in range(1, len(pts))), n, "fix order")
    dist = round(sum(km(pts[i - 1], pts[i]) for i in range(1, len(pts))), 3)
    check(dist == gps["trace_distance_km"], n, "trace_distance_km {0} vs recomputed {1}".format(
        gps["trace_distance_km"], dist))
    fare = art(case, "FARE_BREAKDOWN")["payload"]
    lines = ("base_fare", "distance_fare", "time_fare", "surge_amount", "tolls_erp", "airport_surcharge",
             "platform_fee", "cancellation_fee", "waiting_time_fee")
    total = sum((D(fare[k] or 0) for k in lines), Decimal(0)) - D(fare["promo_discount"] or 0)
    check(cents(total) == cents(fare["total_charged"]), n, "fare lines sum {0} vs total {1}".format(
        total, fare["total_charged"]))
    gsum = sum((D(g["amount_sgd"]) for g in fare["erp_gantries"]), Decimal(0))
    check(cents(gsum) == cents(fare["tolls_erp"] or 0), n, "tolls_erp = gantries")
    for g in fare["erp_gantries"]:
        near = min(m_(g, p) for p in pts)
        check(near <= 250, n, "ERP gantry {0} crossed within 250 m ({1:.1f} m)".format(g["gantry_id"], near))
    if fare["payment_status"] == "REFUNDED":
        check(cents(fare["refund_issued_sgd"]) == cents(fare["total_charged"]), n, "refund = total when REFUNDED")
    else:
        check(cents(fare["refund_issued_sgd"] or 0) == 0, n, "no refund unless REFUNDED")
    c = D(case["dispute"]["amount_contested_sgd"])
    check(Decimal(0) < c <= D(fare["total_charged"]), n, "0 < contested <= total_charged")
    chat_a = art(case, "CHAT_LOG")
    if chat_a["payload"] is not None:
        ch = chat_a["payload"]
        check(ch["message_count"] == len(ch["messages"]), n, "message_count")
        for msg in ch["messages"]:
            if msg.get("waypoint_hint"):
                wh = msg["waypoint_hint"]
                near = min(m_(wh, p) for p in pts)
                check(near <= 250, n, "waypoint_hint near the trace")
    # admissibility
    for a in case["evidence"]:
        adm = a["admissibility"]
        if adm["status"] == "COMPLETE":
            check(adm["issues"] == [] and adm["weight_multiplier"] == 1.0 and a["payload"] is not None, n,
                  "{0} COMPLETE block".format(a["evidence_id"]))
        elif adm["status"] == "MISSING":
            check(adm["issues"] == ["MISSING_ARTIFACT"] and adm["weight_multiplier"] == 0.0 and a["payload"] is None,
                  n, "{0} MISSING block".format(a["evidence_id"]))
        else:
            grade = gap_grade(trip, pts) if "GPS_GAP" in adm["issues"] else None
            w = float(weight_product(adm["issues"], grade).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            check(w == adm["weight_multiplier"], n, "{0} weight {1} vs product {2}".format(
                a["evidence_id"], adm["weight_multiplier"], w))
    for a in case["evidence"]:
        if a["evidence_type"] in ("TRIP_RECORD", "FARE_BREAKDOWN"):
            check(a["payload"] is not None, n, "{0} present".format(a["evidence_type"]))


def termination(trip):
    return trip["cancelled_at"] or trip["started_at"]


def gap_grade(trip, pts):
    """Grade of the largest gap: straddling the termination, long inside the waiting window, or short / outside."""
    term = termination(trip)
    w0 = trip["arrived_at"] or trip["accepted_at"]
    worst = None
    for i in range(1, len(pts)):
        a, b = T(pts[i - 1]["ts"]), T(pts[i]["ts"])
        if b - a <= GAP_POLICY:
            continue
        if a < T(term) < b:
            return "STRADDLING_CANCELLATION"
        if a >= T(w0) and b <= T(term):
            worst = "LONG_INSIDE_WINDOW"
    return worst or "SHORT_OR_OUTSIDE_WINDOW"


# ---------------------------------------------------------------------------
# measurements and the decision
# ---------------------------------------------------------------------------
def ns08(trip, gps, chat, fare, w0, term):
    pts = gps["points"]
    pp = trip["platform_policy"]
    out = set()
    if trip["arrived_at"]:
        dt = min(abs(T(p["ts"]) - T(trip["arrived_at"])) for p in pts)
        if dt > SKEW_S:
            out.add("a")
    if T(pts[0]["ts"]) - T(trip["accepted_at"]) > SKEW_S or T(term) - T(pts[-1]["ts"]) > SKEW_S:
        out.add("a")
    win = between(pts, w0, term)
    iv = [T(pts[i]["ts"]) - T(pts[i - 1]["ts"]) for i in range(1, len(pts))
          if T(pts[i]["ts"]) >= T(w0) and T(pts[i - 1]["ts"]) <= T(term)]
    if (iv and max(iv) > GAP_POLICY) or len(win) < MIN_FIXES:
        out.add("b")
    if chat is not None:
        ks = [int(x["msg_id"][-3:]) for x in chat["messages"]]
        if ks != list(range(1, len(ks) + 1)) or len(ks) < trip["chat_message_count"]:
            out.add("c")
        ms = chat["messages"]
        for i in range(1, len(ms)):
            a, b = T(ms[i - 1]["sent_at"]), T(ms[i]["sent_at"])
            if trip["arrived_at"] and a < T(trip["arrived_at"]) < b and b - a > CHAT_GAP_S:
                out.add("c")
    line = D(fare["cancellation_fee"])
    if line != 0:
        allowed = {D(pp["cancellation_fee_sgd"])}
        if pp["rider_gross_cancellation_fee_sgd"] is not None:
            allowed.add(D(pp["rider_gross_cancellation_fee_sgd"]))
        if line not in allowed:
            out.add("d")
    return out


def ns04(n, trip, gps, chat, w0, term, pin, pres):
    ms = chat["messages"] if chat else []
    loc = [x for x in ms if x["sender"] == "RIDER" and int(x["msg_id"][-3:]) in LOCATING.get(n, ()) and
           T(w0) <= T(x["sent_at"]) <= T(term)]
    replied = any(any(y["sender"] == "DRIVER" and 0 <= T(y["sent_at"]) - T(x["sent_at"]) <= REPLY_S for y in ms)
                  for x in loc)
    calls = [c for c in trip["in_app_calls"] if T(c["initiated_at"]) <= T(term)]
    rt = between(gps["rider_track"], w0, term)
    qual = [p for p in rt if ok_acc(p)]
    within = [p for p in qual if m_(p, pin) <= pres]
    c = None if not qual else 2 * len(within) > len(qual)
    return {"a": bool(loc), "b": bool(loc) and not replied and not calls, "c": c, "replied": replied,
            "calls": len(calls), "qual": len(qual), "within": len(within)}


def farm(dp):
    k, done = dp["no_show_terminations_30d"], dp["completed_trips_30d"]
    return k >= FARM_N and Decimal(k) / Decimal(done) > FARM_RATE, k, done


def payout_of(pp):
    return cents(COMP * D(pp["cancellation_fee_sgd"]))


def eta_minutes(trip):
    for e in trip["events"]:
        if e["event_type"] == "driver_assigned":
            w = e["detail"].split()
            return int(w[w.index("ETA") + 1])
    return None


def advisory_covers(case, pin, a, b, rad):
    """A populated NS-06(i) advisory whose geometry passes within the radius of the pin and whose window covers
    [a, b]."""
    for x in case["evidence"]:
        if x["evidence_type"] != "TRAFFIC_ADVISORY" or x["payload"] is None:
            continue
        p = x["payload"]
        if p["type"] not in NS06_TYPES or not (T(p["valid_from"]) <= T(a) and T(b) <= T(p["valid_to"])):
            continue
        f, t = p["geometry"]["from"], p["geometry"]["to"]
        lat0 = math.radians(pin["lat"])

        def xy(q):
            return ((q["lng"] - pin["lng"]) * 111320 * math.cos(lat0), (q["lat"] - pin["lat"]) * 110574)
        fx, fy = xy(f)
        tx, ty = xy(t)
        u = ((0 - fx) * (tx - fx) + (0 - fy) * (ty - fy)) / ((tx - fx) ** 2 + (ty - fy) ** 2)
        off = math.hypot(fx + u * (tx - fx), fy + u * (ty - fy))
        if 0 <= u <= 1 and off <= rad:
            return True
    return False


def derive(n, case):
    """(ruling, amount, dc, referrals, figures) from the written case alone (plus the content table)."""
    trip = art(case, "TRIP_RECORD")["payload"]
    gps_a = art(case, "GPS_TRACE")
    gps = gps_a["payload"]
    chat = art(case, "CHAT_LOG")["payload"]
    fare = art(case, "FARE_BREAKDOWN")["payload"]
    dp = art(case, "DRIVER_PROFILE")["payload"]
    pp = trip["platform_policy"]
    pts = gps["points"]
    pin = trip["pickup"]
    zone = trip["pickup_zone_class"]
    rad, pres = RADIUS[zone], PRESENCE[zone]
    fw, thr, grace = pp["free_wait_sec"], pp["no_show_threshold_sec"], pp["grace_after_match_sec"]
    term = termination(trip)
    w0 = trip["arrived_at"] or trip["accepted_at"]
    filer = case["dispute"]["filed_by"]
    contested = cents(case["dispute"]["amount_contested_sgd"])
    line = cents(fare["cancellation_fee"])
    F = {"ns08": "".join(sorted(ns08(trip, gps, chat, fare, w0, term)))}
    fq = first_qualifying(pts, pin, rad, term)
    F["fq_ts"] = fq["ts"] if fq else None
    if fq:
        sel = between(pts, fq["ts"], term)
        F["dwell"] = int(T(term) - T(fq["ts"]))
        F["continuous"] = all(ok_acc(p) and m_(p, pin) <= rad for p in sel) and \
            max(T(sel[i]["ts"]) - T(sel[i - 1]["ts"]) for i in range(1, len(sel))) <= GAP_POLICY
        F["fq_d"] = r1(m_(fq, pin))
    gw = gps_a["admissibility"]["weight_multiplier"]

    def compensation(refs=()):
        tripped, k, done = farm(dp)
        F["farm"] = (k, done)
        if tripped:
            return "ESCALATE", None, None, list(refs)
        p = payout_of(pp)
        return "DRIVER_COMPENSATION", p, p, list(refs)

    def refund_outcome(dc=None, refs=()):
        # the fee is not chargeable: a rider filer gets the line back; a driver filer's claim fails (party-relative)
        if filer == "RIDER":
            return "FULL_REFUND", contested, dc, list(refs)
        return "NO_ACTION", None, None, list(refs)

    # completed trip with a waiting line: POL-NS-10(d) / (e)
    if trip["status"] == "COMPLETED":
        wline = cents(fare["waiting_time_fee"] or 0)
        F["dwell_before_boarding"] = F.get("dwell")
        if wline > 0 and fq and F["continuous"] and F["dwell"] > fw:
            return ("NO_ACTION" if filer == "RIDER" else "DRIVER_COMPENSATION", None, None, []), F
        return ("FULL_REFUND", wline, None, []), F
    # rider's own cancellation: POL-NS-10
    if trip["cancelled_by"] == "RIDER":
        F["after_accept"] = int(T(term) - T(trip["accepted_at"]))
        if F["after_accept"] <= grace:
            return refund_outcome(), F
        arrived_ok = fq is not None and trip["arrived_at"] and T(fq["ts"]) <= T(trip["arrived_at"])
        if arrived_ok and F["continuous"] and F["dwell"] > fw:
            return compensation(), F
        en_route = [e["at"] for e in trip["events"] if e["event_type"] == "driver_en_route"]
        moving = bool(en_route) and T(en_route[0]) <= T(trip["accepted_at"]) + grace
        eta = eta_minutes(trip)
        F["eta_at"] = hms(iso(T(trip["accepted_at"]) + 60 * eta))
        late = trip["arrived_at"] is None and T(term) >= T(trip["accepted_at"]) + 60 * eta + ETA_SLACK or \
            (trip["arrived_at"] is not None and T(trip["arrived_at"]) > T(trip["accepted_at"]) + 60 * eta + ETA_SLACK)
        if not moving or late or CANCEL_REQUEST.get(n) or VEHICLE_MISMATCH.get(n):
            return refund_outcome(), F
        return ("NO_ACTION" if filer == "RIDER" else "DRIVER_COMPENSATION", None, None, []), F
    # driver termination for a no-show
    if pp["arrival_marker"] == "GPS_AUTO":
        ev = {e["event_type"]: e["at"] for e in trip["events"]}
        timer_ok = "wait_timer_started" in ev and "wait_timer_expired" in ev and \
            int(T(ev["wait_timer_expired"]) - T(ev["wait_timer_started"])) == fw and \
            T(ev["wait_timer_expired"]) < T(term)
        win = between(pts, trip["arrived_at"], term)
        contradiction = any(m_(p, pin) > rad or p["speed_kph"] >= FALSE_V for p in win)
        F["since_arrival"] = int(T(term) - T(trip["arrived_at"]))
        if timer_ok and not contradiction and (thr is None or F["since_arrival"] >= thr):
            return compensation(), F
        return ("ESCALATE", None, None, []), F
    # BUTTON: the trace is the only carrier of the driver's position
    if D(gw) < FLOOR:
        F["cap"] = gw
        return ("ESCALATE", None, None, []), F
    if "b" in F["ns08"]:
        return ("ESCALATE", None, None, []), F
    refs = []
    tap = min(pts, key=lambda p: abs(T(p["ts"]) - T(trip["arrived_at"])))
    F["tap_d"], F["tap_v"] = r1(m_(tap, pin)), tap["speed_kph"]
    if F["tap_d"] > FALSE_D or tap["speed_kph"] >= FALSE_V:
        if fq is None:
            return refund_outcome(refs=["POL-NS-05(ii): false-arrival event recorded against the driver"]), F
        refs = ["POL-NS-05(iii): false-arrival event recorded against the driver"]
        if F["dwell"] < fw:
            return refund_outcome(), F
    look = between(pts, iso(T(term) - LOOKBACK), term)
    if fq is None or not any(ok_acc(p) and m_(p, pin) <= rad for p in look):
        stat = [p for p in between(pts, trip["arrived_at"], term) if p["speed_kph"] == 0]
        F["stat_band"] = (r1(min(m_(p, pin) for p in stat)), r1(max(m_(p, pin) for p in stat))) if stat else None
        if stat and rad < F["stat_band"][0] and F["stat_band"][1] <= CEILING and \
                T(term) - T(stat[0]["ts"]) >= fw:
            named = SUBLOCATION_NAMED.get(n, True)
            dc = cents(GOODWILL * D(pp["cancellation_fee_sgd"])) if not named and trip["registered_pickup_points"] >= 2 \
                else None
            F["goodwill"] = dc
            return refund_outcome(dc=dc), F
        return refund_outcome(), F
    l4 = ns04(n, trip, gps, chat, w0, term, pin, pres)
    F["ns04"] = l4
    if l4["a"] and l4["b"] and l4["c"] is True:
        return refund_outcome(), F
    runs = runs_inside(pts, pin, rad, fq["ts"], term)
    if len(runs) > 1:
        lens = [int(T(r[-1]["ts"]) - T(r[0]["ts"])) for r in runs[:-1]] + [int(T(term) - T(runs[-1][0]["ts"]))]
        F["runs"] = lens
        loop = [p for p in between(pts, runs[0][-1]["ts"], runs[-1][0]["ts"])]
        F["loop_max"] = r1(max(m_(p, pin) for p in loop))
        summable = F["loop_max"] <= LEASH and advisory_covers(case, pin, fq["ts"], term, rad)
        eff = sum(lens) if summable else max(lens)
        F["effective"] = eff
        # generous bracket of each run: from the last fix before it (outside) to the first outside fix after it or
        # the termination, whichever comes first; fixes after the termination are never waiting
        F["brackets"] = []
        for r in runs:
            before = [p for p in pts if T(p["ts"]) < T(r[0]["ts"])][-1]
            after = [p for p in pts if T(p["ts"]) > T(r[-1]["ts"])]
            end = min(T(after[0]["ts"]), T(term)) if after else T(term)
            F["brackets"].append((hms(before["ts"]), hms(iso(end)), int(end - T(before["ts"]))))
        if eff < fw:
            return refund_outcome(refs=refs), F
        return compensation(refs), F
    if not F["continuous"] or F["dwell"] < fw:
        return refund_outcome(refs=refs), F
    if thr is not None and T(term) - T(trip["arrived_at"]) < thr and T(term) - T(fq["ts"]) < thr:
        return refund_outcome(refs=refs), F
    if T(fq["ts"]) > T(trip["arrived_at"]) and not refs:
        return refund_outcome(), F
    return compensation(refs), F


# ---------------------------------------------------------------------------
def money(x):
    return None if x is None else str(cents(x))


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    d = argv[1]
    with open(os.path.join(ROOT, "build", "blueprint_ns.json"), encoding="utf-8") as f:
        bp = {e["case_no"]: e for e in json.load(f)}
    with open(os.path.join(d, "answers", "ground_truth.json"), encoding="utf-8") as f:
        keys = {k["case_no"]: k for k in json.load(f)}
    files = sorted(glob.glob(os.path.join(d, "cases", "case-040[5-6]*.json")))
    cases = {}
    for path in files:
        with open(path, encoding="ascii") as f:
            c = json.load(f)
        if 4051 <= c["case_no"] <= 4065:
            cases[c["case_no"]] = c
    check(sorted(cases) == list(range(4051, 4066)), 0, "cases 4051-4065 present")
    for n in sorted(cases):
        case, e = cases[n], bp[n]
        it, gt = e["intent"], keys[n]["ground_truth"]
        file_checks(n, case)
        (ruling, amount, dc, refs), F = derive(n, case)
        check(ruling == it["expected_ruling"] == gt["expected_ruling"], n, "ruling: derived {0}, intent {1}, key {2}"
              .format(ruling, it["expected_ruling"], gt["expected_ruling"]))
        check(money(amount) == it["amount_sgd"] == money(gt["expected_amount_sgd"]), n,
              "amount: derived {0}, intent {1}, key {2}".format(money(amount), it["amount_sgd"],
                                                                gt["expected_amount_sgd"]))
        check(money(dc) == it["driver_compensation_sgd"] == money(gt["expected_driver_compensation_sgd"]), n,
              "compensation: derived {0}, intent {1}, key {2}".format(money(dc), it["driver_compensation_sgd"],
                                                                      gt["expected_driver_compensation_sgd"]))
        check(refs == it["referrals"] == gt["expected_referrals"], n, "referrals {0} / {1} / {2}".format(
            refs, it["referrals"], gt["expected_referrals"]))
        check(sorted(F["ns08"]) == sorted(it["ns08_limbs_engaged"]), n, "NS-08 limbs {0} vs intent {1}".format(
            F["ns08"], it["ns08_limbs_engaged"]))
        check(gt["governing_clauses"] == it["governing_clauses"] and gt["difficulty"] == it["difficulty"], n,
              "clauses / difficulty as intended")
        # designed measurements re-derived
        mz = e["facts"]["gps_trace"]["measurements"]
        if "fq_ts" in mz:
            check(F["fq_ts"] == mz["fq_ts"], n, "first qualifying fix {0} vs designed {1}".format(F["fq_ts"],
                                                                                              mz["fq_ts"]))
        if "dwell_fq_s" in mz:
            check(F.get("dwell") == mz["dwell_fq_s"], n, "dwell from first qualifying fix {0} vs designed {1}".format(
                F.get("dwell"), mz["dwell_fq_s"]))
        if "fq_d" in mz:
            check(F.get("fq_d") == mz["fq_d"], n, "first qualifying fix distance")
        if "runs" in F and "i1" in mz:
            check(F["runs"] == [mz["i1"], mz["i2"]], n, "in-radius runs {0} vs designed".format(F["runs"]))
        if "brackets" in F and "i1_generous" in mz:
            gen = [b[2] for b in F["brackets"]]
            check(gen == [mz["i1_generous"], mz["i2_generous"]], n, "generous brackets {0} vs designed".format(gen))
            check(sum(gen) < art(case, "TRIP_RECORD")["payload"]["platform_policy"]["free_wait_sec"], n,
                  "generous bracket total {0} s short of the free wait".format(sum(gen)))
            for b in F["brackets"]:
                check("{0}-{1} = {2} s".format(*b) in gt["rationale"], n,
                      "rationale states the bracket {0}-{1} = {2} s".format(*b))
            check("{0} s".format(sum(gen)) in gt["rationale"], n, "rationale states the bracket total")
        for field in NO_LATENESS_CLAIM.get(n, ()):
            st = case["dispute"][field]
            txt = (st["text"] if isinstance(st, dict) else st or "").lower()
            hit = [w for w in LATENESS_WORDS if re.search(r"\b" + re.escape(w) + r"\b", txt)]
            check(not hit, n, "{0} asserts no late arrival (found {1})".format(field, hit))
        if "tap_d" in F and "arr_d" in mz:
            check(F["tap_d"] == mz["arr_d"] and F["tap_v"] == mz["arr_v"], n, "fix at the arrived event")
        if "r_qualifying" in mz:
            trip = art(case, "TRIP_RECORD")["payload"]
            rt = between(art(case, "GPS_TRACE")["payload"]["rider_track"], mz["window_from"], mz["window_to"])
            qual = [p for p in rt if ok_acc(p)]
            within = [p for p in qual if m_(p, trip["pickup"]) <= PRESENCE[trip["pickup_zone_class"]]]
            check(len(qual) == mz["r_qualifying"] and len(within) == mz["r_qualifying_within_presence_radius"], n,
                  "rider presence counts over the designed window: {0} of {1}".format(len(within), len(qual)))
        # the rationale names this case's evidence and states the deciding figures
        rat = gt["rationale"]
        check(120 <= len(rat) <= 2500, n, "rationale length")
        check(any(a["evidence_id"] in rat for a in case["evidence"]), n, "rationale names evidence ids")
        check(any(c in rat for c in it["governing_clauses"]), n, "rationale names a governing clause")
        figs = []
        if amount is not None:
            figs.append(money(amount))
        if dc is not None:
            figs.append(money(dc))
        if ruling == "DRIVER_COMPENSATION" or (ruling == "ESCALATE" and "farm" in F):
            figs.append(money(payout_of(art(case, "TRIP_RECORD")["payload"]["platform_policy"])))
        for k in ("dwell", "effective", "after_accept"):
            if k == "dwell" and "runs" in F:
                continue
            if k in F and F[k] is not None and ruling != "ESCALATE":
                if k == "dwell" and art(case, "TRIP_RECORD")["payload"]["platform_policy"]["arrival_marker"] == \
                        "GPS_AUTO":
                    continue
                figs.append("{0} s".format(F[k]))
        if "farm" in F:
            figs.append(str(F["farm"][0]))
            figs.append(str(F["farm"][1]))
        if "cap" in F:
            figs.append(str(F["cap"]))
        for fig in figs:
            check(fig in rat, n, "rationale states {0}".format(fig))
        for word in ("ground_truth", "expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd",
                     "expected_referrals", "governing_clauses", "difficulty", "rationale", "canary", "sealed"):
            check(word not in json.dumps(case).lower(), n, "forbidden word {0}".format(word))
        check(all(ord(ch) < 128 for ch in json.dumps(case, ensure_ascii=False)), n, "ASCII")
    for line in FAILS:
        print(line)
    print("audit_ns: {0} cases, {1} checks, {2} failures".format(len(cases), CHECKS[0], len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
