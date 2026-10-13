"""Independent audit of the generated ROUTE_DEVIATION cases 4001-4015.

usage: python3 build/audit_rd.py <DIR>      (DIR holds cases/ and answers/ground_truth.json)

Reads only the GENERATED files (DIR/cases/case-04001.json ... case-04015.json, DIR/answers/ground_truth.json),
the reference policy files in ref/ and the blueprint's intent (build/blueprint_rd.json). It does not import
common.py or the case modules: haversine, Decimal money, the POL-RD-02 recomputation and every policy test are
re-implemented here. For each case it re-derives the deciding measurements from the file, derives the outcome
the version-6 text gives on them, and asserts that this equals what the blueprint intends AND what the key states.

Exit 0 and "AUDIT PASS" when every check holds; otherwise every failed check is listed and the exit code is 1.
Output names checks and case numbers only; it prints no ruling, amount or clause.
"""
import glob
import hashlib
import json
import math
import os
import statistics
import sys
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "ref")
R_KM = 6371.0088
FAILS = []
CHECKS = [0]


def check(cond, n, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append("case {0}: {1}".format(n, what))
    return cond


# ---------------------------------------------------------------------------
# primitives (re-implemented)
# ---------------------------------------------------------------------------
def dec(x):
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(str(x))


def q2(x):
    return dec(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def up05(x):
    return ((dec(x) / Decimal("0.05")).to_integral_value(rounding=ROUND_CEILING) * Decimal("0.05")).quantize(
        Decimal("0.01"))


def hav_km(a, b):
    la, lo = (a["lat"], a["lng"]) if isinstance(a, dict) else a
    lb, mo = (b["lat"], b["lng"]) if isinstance(b, dict) else b
    p1, p2 = math.radians(la), math.radians(lb)
    dp, dl = p2 - p1, math.radians(mo - lo)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_KM * math.asin(math.sqrt(h))


def hav_m(a, b):
    return hav_km(a, b) * 1000.0


def ts(s):
    return datetime.fromisoformat(s)


def secs(a, b):
    return (ts(b) - ts(a)).total_seconds()


def plus_min(s, m):
    return ts(s) + timedelta(minutes=m)


def pct2(num, den):
    return (dec(num) / dec(den) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def established(excess, base):
    return excess > Decimal("0.8") and excess / base > Decimal("0.20")


def material(excess, base):
    return excess > Decimal("8.0") or excess / base > Decimal("0.50")


def seg_pts(frm, to, steps):
    return [(frm["lat"] + (to["lat"] - frm["lat"]) * i / steps, frm["lng"] + (to["lng"] - frm["lng"]) * i / steps)
            for i in range(steps + 1)]


def min_fix_m(coord, pts):
    return min(hav_m(coord, p) for p in pts)


# ---------------------------------------------------------------------------
# policy constants read from ref/
# ---------------------------------------------------------------------------
def load(name):
    with open(os.path.join(REF, name), encoding="utf-8") as f:
        return json.load(f)


RDP = load("route_deviation.json")
FM = RDP["fare_model"]
BASE, PER_KM, PER_MIN, PLATFORM = dec(FM["base_fare"]), dec(FM["per_km"]), dec(FM["per_min"]), dec(FM["platform_fee"])
DE_MIN = dec(FM["de_minimis_refund"])
EXEC_THR = dec(load("general.json")["execution_threshold_sgd"])
WEIGHTS = load("no_show.json")["integrity"]["weights"]
LIC = {}
for _f in ("general.json", "no_show.json", "route_deviation.json"):
    for _c in load(_f)["clauses"]:
        LIC[_c["id"]] = set(_c["licenses"])
for _f in ("0001-pol-ns-11.json", "0002-pol-rd-14.json", "0003-pol-ns-12.json"):
    _c = load(_f)["clause"]
    LIC[_c["id"]] = set(_c["licenses"])


def weight(issues, grade):
    p = Decimal(1)
    for c in issues:
        p *= dec(WEIGHTS["GPS_GAP_" + grade] if c == "GPS_GAP" else WEIGHTS[c])
    return float(q2(p))


def rd02(opt_km, opt_min, fare, erp_on_route):
    """POL-RD-02 as written; intermediates unrounded."""
    sub = BASE + PER_KM * dec(opt_km) + PER_MIN * dec(opt_min)
    rec = sub * dec(fare["surge_multiplier"]) + PLATFORM + dec(erp_on_route) + dec(fare["airport_surcharge"]) + \
        dec(fare["waiting_time_fee"]) - dec(fare["promo_discount"])
    refund = max(dec(fare["total_charged"]) - rec, Decimal(0))
    return rec, refund, up05(refund)


def rd02_outcome(pay, total):
    if pay < DE_MIN:
        return "NO_ACTION"
    if pay >= Decimal("0.9") * total:
        return "FULL_REFUND"
    return "PARTIAL_REFUND"


# ---------------------------------------------------------------------------
# reading a case
# ---------------------------------------------------------------------------
class Case:
    def __init__(self, c):
        self.c = c
        self.n = c["case_no"]
        self.d = c["dispute"]
        self.ev = c["evidence"]
        self.by_type = {}
        for e in self.ev:
            self.by_type.setdefault(e["evidence_type"], []).append(e)
        self.trip = self.p("TRIP_RECORD")
        self.gps = self.p("GPS_TRACE")
        self.chat = self.p("CHAT_LOG")
        self.fare = self.p("FARE_BREAKDOWN")
        self.rprof = self.p("RIDER_PROFILE")
        self.dprof = self.p("DRIVER_PROFILE")
        self.pts = self.gps["points"] if self.gps else []
        self.trace = dec(self.gps["trace_distance_km"]) if self.gps else None
        self.opt = dec(self.trip["optimal_distance_km"])
        self.total = dec(self.fare["total_charged"])
        self.contested = dec(self.d["amount_contested_sgd"])

    def p(self, et, k=0):
        return self.by_type[et][k]["payload"]

    def a(self, et, k=0):
        return self.by_type[et][k]

    def eid(self, et, k=0):
        return self.by_type[et][k]["evidence_id"]


# ---------------------------------------------------------------------------
# generic re-derivations (every case)
# ---------------------------------------------------------------------------
def generic(cs, bp):
    n, F = cs.n, bp["facts"]
    g, pts, fare, trip = cs.gps, cs.pts, cs.fare, cs.trip
    # GPS: distance, counts, gaps, first/last fix
    dist = sum(hav_km(pts[i - 1], pts[i]) for i in range(1, len(pts)))
    check(round(dist, 3) == g["trace_distance_km"], n, "trace_distance_km re-summed from the fixes")
    check(g["trace_distance_km"] == F["gps_trace"]["measurements"]["trace_distance_km"], n,
          "trace_distance_km equals the blueprint")
    check(g["point_count"] == len(pts) == F["gps_trace"]["measurements"]["point_count"], n, "point_count")
    check(all(ts(pts[i]["ts"]) > ts(pts[i - 1]["ts"]) for i in range(1, len(pts))), n, "fix times increase")
    iv = [secs(pts[i - 1]["ts"], pts[i]["ts"]) for i in range(1, len(pts))]
    thr = 2 * g["expected_interval_sec"]
    gaps = [{"from": pts[i - 1]["ts"], "to": pts[i]["ts"], "gap_sec": iv[i - 1]} for i in range(1, len(pts))
            if iv[i - 1] > thr]
    check(gaps == g["gaps"], n, "gaps list re-derived")
    check(max(iv) == g["max_gap_sec"], n, "max_gap_sec")
    check(round(statistics.median(iv), 1) == g["sample_interval_sec"], n, "median interval")
    check(trip["started_at"] == pts[0]["ts"] == g["first_fix_at"] and trip["ended_at"] == pts[-1]["ts"] ==
          g["last_fix_at"], n, "trip start/end equal first/last fix")
    # trip convenience copies
    act = float(Decimal(g["trace_distance_km"]).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    check(act == trip["actual_distance_km"], n, "actual_distance_km is the 1-dp copy of the trace")
    # fare lines sum, tolls, rate card, meter
    lines = ("base_fare", "distance_fare", "time_fare", "surge_amount", "tolls_erp", "airport_surcharge",
             "platform_fee", "cancellation_fee", "waiting_time_fee")
    s = sum(dec(fare[k]) for k in lines) - dec(fare["promo_discount"])
    check(s == cs.total, n, "fare lines sum to total_charged to the cent")
    check(dec(fare["tolls_erp"]) == sum((dec(x["amount_sgd"]) for x in fare["erp_gantries"]), Decimal(0)), n,
          "tolls_erp = sum of gantries")
    km, mins = dec(fare["distance_charged_km"]), dec(fare["time_charged_min"])
    b, dd, tt = q2(BASE), q2(PER_KM * km), q2(PER_MIN * mins)
    sg = q2((b + dd + tt) * (dec(fare["surge_multiplier"]) - 1))
    check((b, dd, tt, sg, q2(PLATFORM)) == (dec(fare["base_fare"]), dec(fare["distance_fare"]), dec(fare["time_fare"]),
                                            dec(fare["surge_amount"]), dec(fare["platform_fee"])), n,
          "fare lines recomputed from distance_charged_km / time_charged_min / rate card / surge")
    for k in lines + ("promo_discount", "total_charged"):
        check(dec(fare[k]) == dec(F["fare_breakdown"][k]), n, "fare line {0} equals the blueprint".format(k))
    if fare["fare_model"] == "METERED":
        check(km == q2(cs.trace), n, "metered distance is the 2-dp copy of the trace")
    # contested bounds
    check(Decimal(0) < cs.contested <= cs.total, n, "0 < contested <= total_charged")
    check(cs.contested == dec(F["dispute"]["amount_contested_sgd"]), n, "contested equals the blueprint")
    # admissibility: weights by the product rule
    for e in cs.ev:
        a = e["admissibility"]
        bpa = F["admissibility"][e["evidence_id"]]
        if a["status"] == "COMPLETE":
            check(a["issues"] == [] and a["weight_multiplier"] == 1.0 and e["payload"] is not None, n,
                  "COMPLETE block " + e["evidence_id"])
        elif a["status"] == "MISSING":
            check(a["issues"] == ["MISSING_ARTIFACT"] and a["weight_multiplier"] == 0.0 and e["payload"] is None, n,
                  "MISSING block " + e["evidence_id"])
        else:
            grade = bpa.get("gps_gap_grade")
            if "GPS_GAP" in a["issues"]:
                big = max(iv)
                want = "LONG_INSIDE_WINDOW" if big > 90 else "SHORT_OR_OUTSIDE_WINDOW"
                check(grade == want, n, "GPS_GAP grade follows the measured gap")
            check(a["weight_multiplier"] == weight(a["issues"], grade), n, "weight = product rule " + e["evidence_id"])
        check(a["status"] == bpa["status"] and a["issues"] == bpa["issues"] and
              a["weight_multiplier"] == bpa["weight_multiplier"], n, "admissibility equals blueprint " +
              e["evidence_id"])
    # chat
    if cs.chat is not None:
        check(cs.chat["message_count"] == len(cs.chat["messages"]) == trip["chat_message_count"], n, "chat counts")
    # timestamps causally ordered
    seq = [trip[k] for k in ("requested_at", "accepted_at", "arrived_at", "started_at", "ended_at") if trip[k]]
    check(all(ts(seq[i]) <= ts(seq[i + 1]) for i in range(len(seq) - 1)), n, "trip timestamps ordered")
    # RD-07 limbs over the whole trip (the disputed segment in every RD case here is the whole trip)
    jumps = [hav_m(pts[i - 1], pts[i]) for i in range(1, len(pts))]
    limbs = {"a": max(iv) > 90, "b": max(jumps) > 500, "c": statistics.median(iv) > 30}
    check(round(max(jumps), 1) == F["gps_trace"]["measurements"]["largest_step_m"], n, "largest step equals blueprint")
    # gantries: crossing = some fix within 250 m
    gant = []
    for x in fare["erp_gantries"]:
        dm = min_fix_m(x, pts)
        gant.append((x, dm, dm <= 250))
    # waypoint hints
    hints = []
    for m in (cs.chat or {}).get("messages", []):
        if m["waypoint_hint"] is not None:
            hints.append((m, min_fix_m(m["waypoint_hint"], pts)))
    return {"iv": iv, "jumps": jumps, "limbs": limbs, "gantries": gant, "hints": hints}


# ---------------------------------------------------------------------------
# per-case derivations: (ruling, amount, driver compensation, referrals, [strings the rationale must state])
# ---------------------------------------------------------------------------
def k3(x):
    return "{0:.3f}".format(dec(x))


def junction_spur(cs, X):
    J = {"lat": X["junction_J"][0], "lng": X["junction_J"][1]}
    idx = [i for i, p in enumerate(cs.pts) if hav_m(p, J) <= 0.5]
    check(len(idx) == 2, cs.n, "two fixes at the corridor junction")
    i, j = idx[0], idx[-1]
    spur = sum(hav_km(cs.pts[k - 1], cs.pts[k]) for k in range(i + 1, j + 1))
    return i, j, dec(round(spur, 3))


def stop_at(cs):
    """Stationary stop: fixes sharing the position of the speed-0 run."""
    zero = [i for i, p in enumerate(cs.pts) if p["speed_kph"] == 0]
    c0 = cs.pts[zero[len(zero) // 2]]
    at = [i for i, p in enumerate(cs.pts) if hav_m(p, c0) <= 0.5]
    return c0, at, secs(cs.pts[at[0]]["ts"], cs.pts[at[-1]]["ts"])


def d4001(cs, G, X):
    n = cs.n
    raw = cs.trace - cs.opt
    check(established(raw, cs.opt), n, "raw excess meets RD-01 (burden shifts)")
    check(not any(G["limbs"].values()), n, "RD-07 limbs do not fire")
    (m, dmin), = G["hints"]
    check(m["sender"] == "RIDER" and ts(m["sent_at"]) < ts(cs.trip["started_at"]), n, "RD-04(a),(b) rider, before")
    i, j, spur = junction_spur(cs, X)
    check(ts(m["sent_at"]) <= ts(cs.pts[i]["ts"]), n, "instruction precedes leaving the corridor")
    c0, at, dur = stop_at(cs)
    check(round(hav_m(c0, m["waypoint_hint"]), 1) == X["stop_to_waypoint_hint_m"] and dmin <= 200, n,
          "stop within 200 m of waypoint_hint (blueprint figure)")
    check(abs(float(spur) - X["spur_trace_km_between_J_fixes"]) < 0.0005, n, "spur equals blueprint")
    check(dur == 180, n, "stop duration")
    rem = raw - spur
    adj = cs.opt + spur                      # RD-01 tests against the RD-04 adjusted optimal
    check(not established(rem, adj), n, "remaining excess fails RD-01 on the adjusted optimal")
    check(not established(rem, cs.opt), n, "remaining excess fails RD-01 even on the booked optimal")
    check(dec(cs.fare["distance_charged_km"]) == q2(cs.trace), n, "no unbilled shortfall")
    check(cs.a("CHAT_LOG")["admissibility"]["weight_multiplier"] >= 0.70, n, "deciding chat >= floor")
    return "NO_ACTION", None, None, [], [k3(cs.trace), k3(raw), k3(spur), k3(rem), k3(adj),
                                         "{0} % of {1} km".format(pct2(rem, adj), k3(adj)),
                                         str(pct2(rem, cs.opt)), str(round(dmin, 1))]


def d4002(cs, G, X):
    n = cs.n
    adv = cs.p("TRAFFIC_ADVISORY")
    raw = cs.trace - cs.opt
    check(not any(G["limbs"].values()), n, "RD-07 clean")
    check(established(raw, cs.opt), n, "deviation first measured")
    check(plus_min(adv["valid_from"], -15) <= ts(cs.trip["started_at"]) and
          ts(cs.trip["ended_at"]) <= plus_min(adv["valid_to"], 15), n, "RD-03(b) window covers the trip")
    rp = [e for e in cs.trip["events"] if e["event_type"] == "route_planned"][0]["detail"]
    check(adv["road"] in rp and "city tunnel" in rp and "city tunnel" in adv["segment"], n,
          "RD-03(a) booked route uses the closed segment")
    near = min(min_fix_m(s, cs.pts) for s in seg_pts(adv["geometry"]["from"], adv["geometry"]["to"], 400))
    check(round(near, 1) == X["min_trace_distance_to_closed_segment_m"] and near > 250, n,
          "RD-03(c) the trace avoids the closed segment")
    cap = Decimal("1.30") * (dec(adv["shortest_lawful_alternative_km"]) - cs.opt) + Decimal("1.00")
    just = min(raw, cap)
    adj = cs.opt + just
    adj_min = (dec(cs.trip["optimal_duration_min"]) * adj / cs.opt).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) \
        if cs.trip["amended_optimal_duration_min"] is None else dec(cs.trip["amended_optimal_duration_min"])
    rem = cs.trace - adj
    check(established(rem, adj) and not material(rem, adj), n, "remaining excess established, not material")
    rec, refund, pay = rd02(adj, adj_min, cs.fare, cs.trip["optimal_route_erp_sgd"])
    return rd02_outcome(pay, cs.total), pay, None, [], [k3(raw), k3(cap), k3(rem), str(rec.normalize()),
                                                        str(pct2(rem, adj))]


def d4003(cs, G, X):
    n = cs.n
    check(G["limbs"]["a"] and G["limbs"]["b"], n, "RD-07(a),(b) fire")
    gap = cs.gps["gaps"][0]
    i = [k for k, p in enumerate(cs.pts) if p["ts"] == gap["from"]][0]
    jump = hav_m(cs.pts[i], cs.pts[i + 1])
    check(round(jump, 1) == X["gap"]["straight_line_m"], n, "gap straight line equals blueprint")
    corr = bool(cs.fare["erp_gantries"]) or cs.d["counterparty_statement"] is not None or \
        any(m["sender"] == "DRIVER" and ("route" in m["text"].lower() or "kpe" in m["text"].lower())
            for m in cs.chat["messages"])
    tc = [e for e in cs.trip["events"] if e["event_type"] == "trip_completed"][0]["detail"]
    check("GPS trace" in tc and cs.a("GPS_TRACE")["source"] == "DRIVER_DEVICE", n,
          "trip distance derived from the same trace (not independent)")
    check(not corr, n, "no independent corroborator (RD-07(ii))")
    check(cs.a("GPS_TRACE")["admissibility"]["weight_multiplier"] < 0.70, n, "sole carrier below the floor")
    return "ESCALATE", None, None, [], [str(int(gap["gap_sec"])), "{0:,.1f}".format(jump), k3(cs.trace)]


def d4004(cs, G, X):
    n = cs.n
    f = cs.fare
    check(f["fare_model"] == "UPFRONT_QUOTE" and f["quoted_fare_sgd"] is not None, n, "RD-11 governs")
    over = cs.total - (dec(f["quoted_fare_sgd"]) + dec(f["tolls_erp"]) + dec(f["airport_surcharge"]) +
                       dec(f["waiting_time_fee"]))
    pay = up05(over)
    raw = cs.trace - cs.opt
    check(not material(raw, cs.opt), n, "not material: no RD-06 referral")
    ruling = "FULL_REFUND" if pay == cs.contested else ("PARTIAL_REFUND" if pay > 0 else "NO_ACTION")
    return ruling, pay, None, [], [str(q2(over)), k3(cs.trace), str(pct2(raw, cs.opt))]


def d4005(cs, G, X):
    n = cs.n
    (m, dmin), = G["hints"]
    check(m["sender"] == "RIDER" and ts(m["sent_at"]) < ts(cs.trip["started_at"]), n, "rider instruction before")
    i, j, spur = junction_spur(cs, X)
    c0, at, dur = stop_at(cs)
    check(round(hav_m(c0, m["waypoint_hint"]), 1) == X["stop_to_waypoint_hint_m"] and dmin <= 200, n,
          "stop within 200 m of the hint")
    check(dur == 360, n, "stop duration")
    check(abs(float(spur) - X["spur_trace_km_between_J_fixes"]) < 0.0005, n, "spur equals blueprint")
    f = cs.fare
    check(f["fare_model"] == "UPFRONT_QUOTE" and dec(f["quoted_fare_sgd"]) == cs.total, n, "charged at the quote")
    short = cs.trace - dec(f["distance_charged_km"])
    check(short > Decimal("1.0"), n, "unbilled shortfall > 1.0 km")
    comp = min(up05(Decimal("0.75") * short), Decimal("15.00"))
    check(not established(cs.trace - spur - cs.opt, cs.opt), n, "no driver-fault deviation outside the spur")
    return "DRIVER_COMPENSATION", comp, comp, [], [k3(short), str(Decimal("0.75") * short), k3(spur)]


def d4006(cs, G, X):
    n = cs.n
    raw = cs.trace - cs.opt
    check(not established(raw, cs.opt), n, "RD-01 fails")
    phantom = [(x, dm) for x, dm, crossed in G["gantries"] if not crossed]
    check(len(phantom) == 1, n, "one phantom gantry line")
    if not phantom:
        return "NO_ACTION", None, None, [], [k3(raw)]
    x, dm = phantom[0]
    check(round(dm, 1) == X["nearest_fix_to_gantry_m"], n, "gantry distance equals blueprint")
    pay = up05(dec(x["amount_sgd"]))
    ref = ["POL-RD-09(4): billing-integrity finding - ERP line {0} '{1}' {2} for a gantry the gps_trace never passes"
           .format(x["gantry_id"], x["name"], q2(x["amount_sgd"]))]
    return "PARTIAL_REFUND", pay, None, ref, [k3(raw), str(pct2(raw, cs.opt)), "{0:,.1f}".format(dm)]


def d4007(cs, G, X):
    n = cs.n
    t = cs.trip
    unmatched = dec(cs.fare["cancellation_fee"]) > 0 and t["status"] == "COMPLETED" and t["cancelled_at"] is None \
        and not any("cancel" in e["event_type"] for e in t["events"])
    check(unmatched, n, "cancellation line has no counterpart (RD-10(8))")
    check(not any(G["limbs"].values()), n, "continuous trace")
    rec, refund, pay = rd02(cs.opt, t["optimal_duration_min"], cs.fare, t["optimal_route_erp_sgd"])
    return "ESCALATE", None, None, [], [str(q2(cs.fare["cancellation_fee"])), str(pay), k3(cs.trace)]


def d4008(cs, G, X):
    n = cs.n
    t = cs.trip
    check(t["vehicle_type"] == "RYDE_POOL" and t["optimal_route_source"] == "MATCHED_POOL_ITINERARY" and
          any(e["event_type"] == "pool_matched" for e in t["events"]), n, "RD-12 matched itinerary on record")
    raw = cs.trace - cs.opt
    check(not established(raw, cs.opt), n, "RD-01 fails against matched itinerary")
    wrong = cs.trace - dec(t["solo_optimal_distance_km"])
    check(established(wrong, dec(t["solo_optimal_distance_km"])), n, "solo reading is the trap")
    ev = {e["event_type"]: e["at"] for e in t["events"]}
    sysm = [m for m in cs.chat["messages"] if m["sender"] == "SYSTEM"]
    offs = set()
    for m in sysm:
        for pre, et in (("Your driver has arrived", "driver_arrived"), ("Trip started", "trip_started"),
                        ("Trip completed", "trip_completed"), ("You are on a pool ride", "pool_matched"),
                        ("Picking up", "pool_pickup"), ("Your co-rider has been", "pool_dropoff")):
            if m["text"].startswith(pre):
                offs.add(secs(ev[et], m["sent_at"]))
    check(len(offs) == 1 and list(offs)[0] < 600, n, "constant chat skew below RD-10(4)")
    return "NO_ACTION", None, None, [], [k3(raw), str(pct2(raw, cs.opt)), str(int(list(offs)[0]))]


def d4009(cs, G, X):
    n = cs.n
    raw = cs.trace - cs.opt
    check(established(raw, cs.opt) and material(raw, cs.opt), n, "material deviation")
    check(not any(G["limbs"].values()), n, "tagged gap below every RD-07 limb")
    gap = cs.gps["gaps"][0]
    check(gap["gap_sec"] <= 90 and gap["gap_sec"] == X["gap"]["gap_sec"], n, "gap length")
    # RD-07 limb (c) is the sustained cadence, not the isolated gap: each limb against its own figure
    cadence = statistics.median(G["iv"])
    others = sorted(G["iv"])[:-1]
    check(max(G["iv"]) == gap["gap_sec"] and max(others) <= 30 and cadence <= 30, n,
          "only the tagged gap is above 30 s; sustained cadence under limb (c)")
    lim = ["(a) {0} s is not over 90 s".format(int(gap["gap_sec"])),
           "(b) {0:.1f} m is not over 500 m".format(max(G["jumps"])),
           "(c) the sustained cadence is {0} s, not over 30 s".format(int(cadence))]
    flags, trips = cs.dprof["deviation_flags_90d"], cs.dprof["completed_trips_90d"]
    pattern = flags >= 3 or (trips >= 40 and Decimal(flags) / Decimal(trips) >= Decimal("0.05"))
    check(pattern, n, "RD-06 pattern on the 90-day counters")
    rec, refund, pay = rd02(cs.opt, cs.trip["optimal_duration_min"], cs.fare, cs.trip["optimal_route_erp_sgd"])
    full = cs.total - dec(cs.fare["tolls_erp"]) - dec(cs.fare["airport_surcharge"])
    ruling = "FULL_REFUND" if full == cs.contested else "PARTIAL_REFUND"
    return ruling, full, None, ["POL-RD-06(c): driver-conduct review"], [k3(raw), str(pct2(raw, cs.opt)),
                                                                          str(rec.normalize()), str(pay)] + lim


def d4010(cs, G, X):
    n = cs.n
    t = cs.trip
    check(t["dropoff_amended_at"] is not None and t["amended_optimal_distance_km"] is None, n,
          "RD-05 re-quote missing (RD-10(5))")
    check(cs.d["filed_by"] == "DRIVER" and "changed her destination" in cs.d["claim_text"], n,
          "the filer invokes the relocation")
    return "ESCALATE", None, None, [], [k3(cs.trace)]


def d4011(cs, G, X):
    raw = cs.trace - cs.opt
    check(established(raw, cs.opt) and not material(raw, cs.opt), cs.n, "established, not material")
    check(not any(G["limbs"].values()), cs.n, "RD-07 clean")
    rec, refund, pay = rd02(cs.opt, cs.trip["optimal_duration_min"], cs.fare, cs.trip["optimal_route_erp_sgd"])
    return rd02_outcome(pay, cs.total), pay, None, [], [k3(raw), str(pct2(raw, cs.opt)), str(q2(rec))]


def d4012(cs, G, X):
    n = cs.n
    raw = cs.trace - cs.opt
    check(established(raw, cs.opt) and not material(raw, cs.opt), n, "established, not material")
    a1, a2 = cs.p("TRAFFIC_ADVISORY", 0), cs.p("TRAFFIC_ADVISORY", 1)
    s1 = seg_pts(a1["geometry"]["from"], a1["geometry"]["to"], 400)
    near1 = min(min_fix_m(s, cs.pts) for s in s1)
    drop1 = min(hav_m(s, cs.trip["dropoff"]) for s in seg_pts(a1["geometry"]["from"], a1["geometry"]["to"], 2000))
    check(round(near1, 1) == X["advisory_01_segment_min_distance_to_trace_m"] and
          round(drop1, 1) == X["advisory_01_segment_min_distance_to_dropoff_m"], n, "advisory 01 geometry")
    check(max(a1["geometry"]["from"]["lng"], a1["geometry"]["to"]["lng"]) < min(p["lng"] for p in cs.pts) and
          max(a1["geometry"]["from"]["lng"], a1["geometry"]["to"]["lng"]) < cs.trip["dropoff"]["lng"], n,
          "RD-03(a) fails: closed section beyond the booked route")
    near2 = min(min_fix_m(s, cs.pts) for s in seg_pts(a2["geometry"]["from"], a2["geometry"]["to"], 400))
    check(round(near2, 1) == X["advisory_02_segment_min_distance_to_trace_m"], n, "advisory 02 on the driver's route")
    for a in (a1, a2):
        check(plus_min(a["valid_from"], -15) <= ts(cs.trip["started_at"]) and
              ts(cs.trip["ended_at"]) <= plus_min(a["valid_to"], 15) and
              a["shortest_lawful_alternative_km"] is not None, n, "RD-10(5) has nothing to act on")
    rec, refund, pay = rd02(cs.opt, cs.trip["optimal_duration_min"], cs.fare, cs.trip["optimal_route_erp_sgd"])
    check(pay == dec(cs.fare["refund_issued_sgd"]) == cs.contested, n, "platform refund equals RD-02")
    return "NO_ACTION", None, None, [], [k3(raw), str(pct2(raw, cs.opt)), str(q2(rec)), "{0:,.1f}".format(near1),
                                         "{0:,.1f}".format(drop1)]


def d4013(cs, G, X):
    n = cs.n
    raw = cs.trace - cs.opt
    check(established(raw, cs.opt) and not material(raw, cs.opt), n, "established, not material")
    (m, dmin), = G["hints"]
    check(m["sender"] == "RIDER" and ts(m["sent_at"]) < ts(cs.trip["started_at"]), n, "RD-04(a)-(c) met")
    check(dmin > 200 and round(dmin, 1) == X["min_trace_to_waypoint_hint_m"], n, "RD-14: never within 200 m")
    check(cs.rprof["deviation_claims_60d"] < 4, n, "RD-08 rider factor not engaged")
    rec, refund, pay = rd02(cs.opt, cs.trip["optimal_duration_min"], cs.fare, cs.trip["optimal_route_erp_sgd"])
    return rd02_outcome(pay, cs.total), pay, None, [], [k3(raw), str(pct2(raw, cs.opt)), str(q2(rec)),
                                                        str(q2(refund)), "{0:,.1f}".format(dmin)]


def d4014(cs, G, X):
    n = cs.n
    raw = cs.trace - cs.opt
    check(established(raw, cs.opt), n, "deviation shown")
    aid = cs.eid("TRAFFIC_ADVISORY")
    check(cs.p("TRAFFIC_ADVISORY") is None and aid in cs.d["claim_text"] and cs.d["filed_by"] == "DRIVER", n,
          "the filer cites the MISSING advisory (RD-10(5), RD-13(1) carve-out)")
    return "ESCALATE", None, None, [], [k3(raw), str(pct2(raw, cs.opt))]


def d4015(cs, G, X):
    n = cs.n
    raw = cs.trace - cs.opt
    check(established(raw, cs.opt) and material(raw, cs.opt), n, "material deviation")
    flags, trips = cs.dprof["deviation_flags_90d"], cs.dprof["completed_trips_90d"]
    check(not (flags >= 3 or (trips >= 40 and Decimal(flags) / Decimal(trips) >= Decimal("0.05"))), n,
          "no RD-06 pattern on the 90-day counters")
    aid = cs.eid("TRAFFIC_ADVISORY")
    cp = (cs.d["counterparty_statement"] or {}).get("text", "")
    check(cs.p("TRAFFIC_ADVISORY") is None and aid not in cs.d["claim_text"] and aid not in cp, n,
          "uncited traffic assertion (RD-13(1)-(2))")
    check(all(crossed for _, _, crossed in G["gantries"]), n, "every gantry crossed (no RD-09(4) line)")
    for x, dm, _ in G["gantries"]:
        want = float(X["gantry_{0}_nearest_fix".format(x["gantry_id"])].split(" m")[0])
        check(round(dm, 1) == want, n, "gantry distance equals blueprint")
    rec, refund, pay = rd02(cs.opt, cs.trip["optimal_duration_min"], cs.fare, cs.trip["optimal_route_erp_sgd"])
    check(pay <= Decimal("150") and pay <= cs.total, n, "RD-10(6) not triggered")
    return rd02_outcome(pay, cs.total), pay, None, [], [k3(raw), str(pct2(raw, cs.opt)), str(rec.normalize()),
                                                        str(refund.normalize())]


DERIVE = {4001: d4001, 4002: d4002, 4003: d4003, 4004: d4004, 4005: d4005, 4006: d4006, 4007: d4007, 4008: d4008,
          4009: d4009, 4010: d4010, 4011: d4011, 4012: d4012, 4013: d4013, 4014: d4014, 4015: d4015}


def num_or_none(x):
    return None if x is None else q2(x)


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    out = argv[0]
    with open(os.path.join(ROOT, "build", "blueprint_rd.json"), encoding="utf-8") as f:
        bp = {r["case_no"]: r for r in json.load(f)}
    with open(os.path.join(out, "answers", "ground_truth.json"), encoding="utf-8") as f:
        key = {r["case_no"]: r for r in json.load(f)}
    idx_path = os.path.join(out, "cases", "index.json")
    index = {e["case_no"]: e for e in json.load(open(idx_path, encoding="utf-8"))} if os.path.exists(idx_path) else {}
    files = sorted(glob.glob(os.path.join(out, "cases", "case-040[01]*.json")))
    seen = []
    for path in files:
        raw_bytes = open(path, "rb").read()
        c = json.loads(raw_bytes)
        n = c["case_no"]
        if not (4001 <= n <= 4015):
            continue
        seen.append(n)
        if n in index:
            check(index[n]["sha256"] == hashlib.sha256(raw_bytes).hexdigest(), n, "index sha256 matches the file")
        cs = Case(c)
        rec = bp[n]
        I = rec["intent"]
        X = rec["facts"]["gps_trace"]["extra_measurements"]
        try:
            G = generic(cs, rec)
            ruling, amount, dc, refs, figures = DERIVE[n](cs, G, X)
        except (KeyError, IndexError, ValueError, TypeError, ZeroDivisionError) as ex:
            check(False, n, "derivation could not run on the file ({0})".format(type(ex).__name__))
            continue
        k = key.get(n, {}).get("ground_truth")
        if not check(k is not None, n, "key record present"):
            continue
        # derived outcome == blueprint intent == key
        check(ruling == I["expected_ruling"] == k["expected_ruling"], n, "ruling: derived / blueprint / key agree")
        want_amt = num_or_none(I["amount_sgd"])
        check(num_or_none(amount) == want_amt == num_or_none(k["expected_amount_sgd"]), n,
              "amount: derived / blueprint / key agree")
        check(num_or_none(dc) == num_or_none(I["driver_compensation_sgd"]) ==
              num_or_none(k["expected_driver_compensation_sgd"]), n, "driver compensation agrees")
        check(refs == I["referrals"] == k["expected_referrals"], n, "referrals agree")
        check(I["governing_clauses"] == k["governing_clauses"] and I["difficulty"] == k["difficulty"], n,
              "clauses / difficulty equal the blueprint")
        check(any(ruling in LIC[cl] for cl in k["governing_clauses"] if cl != "POL-GEN-03"), n,
              "a governing clause licenses the ruling")
        # money-shape rules
        if ruling == "FULL_REFUND":
            check(dec(k["expected_amount_sgd"]) == cs.contested, n, "FULL_REFUND equals contested")
        if ruling == "PARTIAL_REFUND":
            a = dec(k["expected_amount_sgd"])
            check(Decimal(0) < a < cs.contested and a % Decimal("0.05") == 0, n, "PARTIAL bounds and 0.05 step")
        if ruling in ("NO_ACTION", "ESCALATE"):
            check(k["expected_amount_sgd"] is None and k["expected_driver_compensation_sgd"] is None, n,
                  "null money")
        if ruling == "DRIVER_COMPENSATION":
            check(k["expected_amount_sgd"] == k["expected_driver_compensation_sgd"] and
                  dec(k["expected_amount_sgd"]) % Decimal("0.05") == 0, n, "compensation mirrored")
        # rationale states this case's ids, the deciding clauses and the deciding numbers computed here
        ra = k["rationale"]
        check(120 <= len(ra) <= 2500, n, "rationale length")
        check(cs.eid("GPS_TRACE") in ra or cs.eid("FARE_BREAKDOWN") in ra, n, "rationale names evidence ids")
        check(all(cl in ra for cl in k["governing_clauses"]), n, "rationale names every governing clause")
        for fig in figures:
            check(fig in ra, n, "rationale states the deciding figure")
        if amount is not None:
            check("{0:.2f}".format(amount) in ra, n, "rationale states the amount")
    check(sorted(seen) == list(range(4001, 4016)), 0, "all 15 RD case files present")
    if FAILS:
        for f in FAILS:
            print("AUDIT FAIL", f)
        print("AUDIT FAILED: {0} of {1} checks".format(len(FAILS), CHECKS[0]))
        return 1
    print("AUDIT PASS: {0} checks over {1} cases".format(CHECKS[0], len(seen)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
