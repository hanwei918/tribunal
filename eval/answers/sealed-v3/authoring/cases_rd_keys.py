"""Answer keys for the ROUTE_DEVIATION cases 4001-4015.

Every deciding figure is computed from the case AS WRITTEN (a JSON round trip of the built case dict): the
3-dp trace_distance_km, the cent-rounded fare lines, the stored trip fields, the fixes themselves. Money is
Decimal; the POL-RD-02 recomputation keeps intermediates unrounded and rounds only the payable UP to 0.05. Each
rationale is assembled from those computed values; the ruling, amounts, referrals, clauses and difficulty are
asserted against the blueprint's intent, and the assembled rationale is asserted equal to the blueprint's text.
"""
import json
from decimal import Decimal, ROUND_HALF_UP

import common as C

D = C.D


class KeyMismatch(C.BuildError):
    pass


def need(cond, msg):
    if not cond:
        raise KeyMismatch(msg)


# ---------------------------------------------------------------------------
# reading the written case
# ---------------------------------------------------------------------------
class View:
    def __init__(self, case):
        c = json.loads(C.dumps_case(case))     # exactly what is written to the file
        self.c = c
        self.n = c["case_no"]
        self.d = c["dispute"]
        self.by = {}
        self.ids = {}
        for e in c["evidence"]:
            self.by[e["evidence_id"]] = e
            self.ids.setdefault(e["evidence_type"], []).append(e["evidence_id"])
        self.trip = self.payload("TRIP_RECORD")
        self.gps = self.payload("GPS_TRACE")
        self.chat = self.payload("CHAT_LOG")
        self.fare = self.payload("FARE_BREAKDOWN")
        self.rprof = self.payload("RIDER_PROFILE")
        self.dprof = self.payload("DRIVER_PROFILE")
        self.pts = self.gps["points"] if self.gps else []

    def eid(self, et, k=0):
        return self.ids[et][k]

    def payload(self, et, k=0):
        return self.by[self.ids[et][k]]["payload"]

    def adm(self, et, k=0):
        return self.by[self.ids[et][k]]["admissibility"]

    # figures as written
    @property
    def trace(self):
        return D(self.gps["trace_distance_km"])

    @property
    def opt(self):
        return D(self.trip["optimal_distance_km"])

    @property
    def total(self):
        return D(self.fare["total_charged"])

    @property
    def contested(self):
        return D(self.d["amount_contested_sgd"])

    def msg(self, k):
        return [m for m in self.chat["messages"] if m["msg_id"] == C.msg_id(self.n, k)][0]


# ---------------------------------------------------------------------------
# arithmetic
# ---------------------------------------------------------------------------
RATES = C.rd_fare_constants()
DE_MINIMIS = RATES["de_minimis_refund"]
with open(C.os.path.join(C.REF_DIR, "general.json"), encoding="utf-8") as _f:
    EXEC_THRESHOLD = D(json.load(_f)["execution_threshold_sgd"])


def pct(num, den):
    return (D(num) / D(den) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def established(excess, base):
    return excess > Decimal("0.8") and excess / base > Decimal("0.20")


def material(excess, base):
    return excess > Decimal("8.0") or excess / base > Decimal("0.50")


def rd02_parts(opt_km, opt_min, fare, erp_on_route):
    """POL-RD-02 recomputed fare, unrounded, with its displayed parts."""
    b = RATES["base_fare"]
    dist = RATES["per_km"] * D(opt_km)
    tim = RATES["per_min"] * D(opt_min)
    surge = D(fare["surge_multiplier"])
    rec = (b + dist + tim) * surge + RATES["platform_fee"] + D(erp_on_route) + D(fare["airport_surcharge"]) + \
        D(fare["waiting_time_fee"]) - D(fare["promo_discount"])
    return {"base": b, "dist": dist, "time": tim, "surge": surge, "sub": b + dist + tim, "rec": rec}


def rd02(v, opt_km=None, opt_min=None):
    p = rd02_parts(v.opt if opt_km is None else opt_km,
                   v.trip["optimal_duration_min"] if opt_min is None else opt_min,
                   v.fare, v.trip["optimal_route_erp_sgd"])
    raw = max(v.total - p["rec"], Decimal(0))
    p["raw"] = raw
    p["pay"] = C.up005(raw)
    return p


def t(x):
    """Decimal text: trailing zeros dropped, at least 2 dp (3.80, 12.645, 27.3005)."""
    x = D(x)
    s = format(x.normalize(), "f")
    if "." not in s:
        s += ".00"
    elif len(s.split(".")[1]) < 2:
        s += "0" * (2 - len(s.split(".")[1]))
    return s


def k3(x):
    return "{0:.3f}".format(D(x))


def m1(x):
    return "{0:,.1f}".format(x)


def hms(ts):
    return ts[11:19]


def hm(ts):
    return ts[11:16]


def num_txt(x):
    """A JSON number as the record shows it (7.4, 13.0, 15)."""
    return repr(x) if isinstance(x, float) else str(x)


def ll_txt(p):
    return "({0}, {1})".format(p["lat"], p["lng"])


# ---------------------------------------------------------------------------
# geometry on the written fixes
# ---------------------------------------------------------------------------
def min_to_fixes_m(coord, pts):
    return min(C.hav_m(coord, p) for p in pts)


def seg_samples(frm, to, steps):
    return [(frm["lat"] + (to["lat"] - frm["lat"]) * i / steps, frm["lng"] + (to["lng"] - frm["lng"]) * i / steps)
            for i in range(steps + 1)]


def seg_to_fixes_m(frm, to, pts, steps=400):
    return min(min_to_fixes_m(s, pts) for s in seg_samples(frm, to, steps))


def seg_to_point_m(frm, to, coord, steps=2000):
    return min(C.hav_m(s, coord) for s in seg_samples(frm, to, steps))


def fixes_at(pts, coord, tol_m=0.5):
    return [i for i, p in enumerate(pts) if C.hav_m(p, coord) <= tol_m]


def path_km(pts, i, j):
    return sum(C.hav_km(pts[k - 1], pts[k]) for k in range(i + 1, j + 1))


def stop_run(pts):
    """The stop: the place of the longest run of speed-0 fixes; returns (first index, last index) of the
    consecutive fixes at that place (the arrival fix included)."""
    best, cur = (None, None, 0), None
    for i, p in enumerate(pts):
        if p["speed_kph"] == 0:
            cur = i if cur is None else cur
            if i - cur + 1 > best[2]:
                best = (cur, i, i - cur + 1)
        else:
            cur = None
    a, b = best[0], best[1]
    while a > 0 and C.hav_m(pts[a - 1], pts[a]) <= 0.5:
        a -= 1
    return a, b


def rd07_limbs(pts, t_from=None, t_to=None):
    """(max interval s, max straight-line jump m, median interval s) over the disputed segment."""
    sel = [i for i in range(1, len(pts)) if (t_from is None or pts[i]["ts"] >= t_from) and
           (t_to is None or pts[i - 1]["ts"] <= t_to)]
    iv = [C.diff_s(pts[i - 1]["ts"], pts[i]["ts"]) for i in sel]
    jm = [C.hav_m(pts[i - 1], pts[i]) for i in sel]
    return max(iv), max(jm), sorted(iv)[len(iv) // 2]


def gantry_nearest(g, pts):
    return min_to_fixes_m(g, pts)


# ---------------------------------------------------------------------------
# per-case keys
# ---------------------------------------------------------------------------
def k4001(v, I, X):
    J = {"lat": X["junction_J"][0], "lng": X["junction_J"][1]}
    at_j = fixes_at(v.pts, J)
    need(len(at_j) == 2, "4001 junction fixes {0}".format(at_j))
    i_in, i_out = at_j
    spur = D(repr(round(path_km(v.pts, i_in, i_out), 3)))
    a, b = stop_run(v.pts)
    stop = v.pts[a]
    stop_s = int(C.diff_s(v.pts[a]["ts"], v.pts[b]["ts"]))
    m = v.msg(2)
    need(m["sender"] == "RIDER", "4001 sender")
    hint = m["waypoint_hint"]
    d_hint = round(C.hav_m(stop, hint), 1)
    d_min = round(min_to_fixes_m(hint, v.pts), 1)
    need(d_hint <= 200 and d_min == d_hint, "4001 corroboration")
    lead = int(C.diff_s(m["sent_at"], v.pts[i_in]["ts"]))
    need(m["sent_at"] < v.trip["started_at"] and lead >= 0, "4001 timing")
    raw = v.trace - v.opt
    need(established(raw, v.opt), "4001 raw excess establishes")
    rem = raw - spur
    adj = v.opt + spur                       # POL-RD-04 adjusted optimal: the base POL-RD-01 tests against
    need(not established(rem, adj), "4001 remaining excess fails on the adjusted optimal")
    need(not established(rem, v.opt), "4001 remaining excess fails even on the booked optimal")
    need(D(repr(v.fare["distance_charged_km"])) == C.q2(v.trace), "4001 no unbilled shortfall")
    w = v.adm("CHAT_LOG")
    need(w["weight_multiplier"] >= 0.70, "4001 chat weight")
    r = ("NO_ACTION. {gps} (COMPLETE) measures {trace} km against optimal_distance_km {opt} on {trip}, a raw excess of "
         "{raw} km ({rawp} %), so the burden shifts. POL-RD-04 then excludes the detour: {mid} on {chat} is from the "
         "rider, sent {sent} before boarding, {lead} s before the trace leaves the corridor at junction {J} at "
         "{tin}, and names {label} with waypoint_hint {hint}; the trace stops {stop_s} s at {stop}, {dh} m from the "
         "hint. {chat} is IMPAIRED ({codes}, weight {w}) for the Malay words singgah and kejap, but the place is "
         "fixed by waypoint_hint and {w} is above the 0.70 floor (POL-GEN-02). The out-and-back spur between the "
         "junction fixes measures {spur} km and is excluded: the POL-RD-04 adjusted optimal is {opt} + {spur} = {adj} "
         "km, and the remaining excess {trace} - {adj} = {rem} km is {adjp} % of {adj} km ({remp} % even against the "
         "booked {opt} km), below both 20 % and 0.8 km, failing both POL-RD-01 tests, so no deviation exists. POL-RD-09(3) bars an ERP refund on a "
         "rider-caused detour and the fare billed the full {billed} km, so no compensation arises. The rider's claim "
         "of a roundabout route is contradicted by her own instruction.").format(
        gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]), trip=v.eid("TRIP_RECORD"),
        raw=k3(raw), rawp=pct(raw, v.opt), mid=m["msg_id"], chat=v.eid("CHAT_LOG"), sent=hms(m["sent_at"]),
        lead=lead, J=ll_txt(J), tin=hms(v.pts[i_in]["ts"]), label=hint["label"], hint=ll_txt(hint),
        stop_s=stop_s, stop=ll_txt(stop), dh=d_hint, codes=", ".join(w["issues"]), w=w["weight_multiplier"],
        spur=k3(spur), rem=k3(rem), remp=pct(rem, v.opt), adj=k3(adj), adjp=pct(rem, adj), billed="{0:.2f}".format(v.fare["distance_charged_km"]))
    return "NO_ACTION", None, None, r


def k4002(v, I, X):
    adv_id = v.eid("TRAFFIC_ADVISORY")
    adv = v.payload("TRAFFIC_ADVISORY")
    raw = v.trace - v.opt
    need(established(raw, v.opt), "4002 established")
    # (b) validity with 15-minute buffers covers the trip window
    need(C.add_min(adv["valid_from"], -15) <= v.trip["started_at"] and v.trip["ended_at"] <= C.add_min(
        adv["valid_to"], 15), "4002 window")
    near = round(seg_to_fixes_m(adv["geometry"]["from"], adv["geometry"]["to"], v.pts), 1)
    need(near == X["min_trace_distance_to_closed_segment_m"], "4002 segment distance {0}".format(near))
    cap = Decimal("1.30") * (D(adv["shortest_lawful_alternative_km"]) - v.opt) + Decimal("1.00")
    just = min(raw, cap)
    adj = v.opt + just
    need(v.trip["amended_optimal_duration_min"] is None, "4002 amended duration")
    adj_min = (D(v.trip["optimal_duration_min"]) * adj / v.opt).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    rem = v.trace - adj
    need(established(rem, adj) and not material(rem, adj), "4002 remaining")
    p = rd02(v, adj, adj_min)
    need(p["pay"] >= DE_MINIMIS and p["pay"] < v.total * Decimal("0.9"), "4002 partial")
    need(not v.fare["erp_gantries"], "4002 no ERP")
    r = ("PARTIAL_REFUND {pay}. {gps} (COMPLETE) measures {trace} km against optimal_distance_km {opt} on {trip}, an "
         "excess of {raw} km. The driver's closure is real: {adv} is a {typ} of the CTE city tunnel, which the booked "
         "route uses (POL-RD-03(a)); it is valid {vf} to {vt} and the trip began {start} (b); the trace leaves the "
         "CTE at the PIE interchange before the segment, stays {near} m from it and rejoins at Outram Rd after it "
         "(c). The exoneration is capped: min({raw}, 1.30 x ({sla} - {opt}) + 1.00) = {cap} km, adjusted optimal "
         "{adj} km, duration {dur} x {adj} / {opt} = {adjmin} min (amended duration null). Remaining excess {trace} "
         "- {adj} = {rem} km = {remp} % still establishes a deviation under POL-RD-01 and is not material. POL-RD-02 "
         "with surge {surge} from {fare} and {erp} on-route ERP: recomputed {b} + {dist} + {time} + {plat} = {rec}; "
         "charged_total {total}; refund {rawref} rounded up to {pay} of the {con} contested. No ERP lines, so "
         "POL-RD-09 has nothing to settle.").format(
        pay=t(p["pay"]), gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), adv=adv_id, typ=adv["type"], vf=hm(adv["valid_from"]),
        vt=hm(adv["valid_to"]), start=hms(v.trip["started_at"]), near=near, sla=adv["shortest_lawful_alternative_km"],
        cap=k3(cap), adj=t(adj), dur=v.trip["optimal_duration_min"], adjmin=adjmin_txt(adj_min), rem=k3(rem),
        remp=pct(rem, adj), surge=v.fare["surge_multiplier"], fare=v.eid("FARE_BREAKDOWN"),
        erp=t(v.trip["optimal_route_erp_sgd"]), b=t(p["base"]), dist=t(p["dist"]), time=t(p["time"]),
        plat=t(RATES["platform_fee"]), rec=t(p["rec"]), total=t(v.total), rawref=t(p["raw"]), con=t(v.contested))
    return "PARTIAL_REFUND", p["pay"], None, r


def adjmin_txt(x):
    return format(x, "f")


def k4003(v, I, X):
    mg, mj, med = rd07_limbs(v.pts)
    need(mg > 90 and mj > 500, "4003 RD-07 limbs")
    gap = [g for g in v.gps["gaps"] if g["gap_sec"] > 90][0]
    i = [k for k, p in enumerate(v.pts) if p["ts"] == gap["from"]][0]
    jump = C.hav_m(v.pts[i], v.pts[i + 1])
    raw = v.trace - v.opt
    w = v.adm("GPS_TRACE")
    need(w["weight_multiplier"] < 0.70, "4003 weight below floor")
    # no independent corroborator
    need(not v.fare["erp_gantries"] and v.d["counterparty_statement"] is None, "4003 corroborators")
    need(all(m["sender"] != "DRIVER" or "route" not in m["text"].lower() for m in v.chat["messages"]), "4003 chat")
    r = ("ESCALATE under POL-RD-10(3) via POL-RD-07(iii). {gps} is IMPAIRED ({codes}, weight {w}): one {gs} s interval "
         "from {gf} to {gt} with bounding fixes {jump} m apart sits in the KPE/MCE stretch the rider disputes, so "
         "POL-RD-07 limbs (a) (> 90 s) and (b) (> 500 m) fire. Read across the gap as a straight line (RD-07(i)) the "
         "trace gives {trace} km against optimal_distance_km {opt} on {trip}, {rawp} %, but RD-07(ii) forbids "
         "establishing a deviation on the trace alone. No independent corroborator exists: {chat} holds only pickup "
         "messages, {fare} charges no ERP gantry, the counterparty_statement is null, and actual_distance_km {act} "
         "and distance_charged_km {billed} are copies of the same trace (trip_completed event; RD-01). The claim is "
         "not sustained and RD-07(iii) requires ESCALATE rather than NO_ACTION; the sole carrier's {w} weight also "
         "caps confidence below the 0.70 floor (POL-GEN-02, RD-10(1)). The {con} is held; a full-resolution location "
         "export for {gf} to {gt} would resolve it.").format(
        gps=v.eid("GPS_TRACE"), codes=", ".join(w["issues"]), w=w["weight_multiplier"], gs=int(gap["gap_sec"]),
        gf=hms(gap["from"]), gt=hms(gap["to"]), jump=m1(jump), trace=k3(v.trace),
        opt=num_txt(v.trip["optimal_distance_km"]), trip=v.eid("TRIP_RECORD"), rawp=pct(raw, v.opt),
        chat=v.eid("CHAT_LOG"), fare=v.eid("FARE_BREAKDOWN"), act=num_txt(v.trip["actual_distance_km"]),
        billed="{0:.2f}".format(v.fare["distance_charged_km"]), con=t(v.contested))
    r = r.replace("export for {0} to {1}".format(hms(gap["from"]), hms(gap["to"])),
                  "export for {0}-{1}".format(hms(gap["from"]), hms(gap["to"])))
    return "ESCALATE", None, None, r


def k4004(v, I, X):
    f = v.fare
    need(f["fare_model"] == "UPFRONT_QUOTE" and f["quoted_fare_sgd"] is not None, "4004 upfront")
    passthru = D(f["tolls_erp"]) + D(f["airport_surcharge"]) + D(f["waiting_time_fee"])
    over = v.total - (D(f["quoted_fare_sgd"]) + passthru)
    pay = C.up005(over)
    need(pay == v.contested, "4004 full")
    raw = v.trace - v.opt
    need(established(raw, v.opt) and not material(raw, v.opt), "4004 not material")
    careless = rd02(v)
    r = ("FULL_REFUND {pay}. {fare} shows fare_model UPFRONT_QUOTE with quoted_fare_sgd {q}, but the trip was re-rated "
         "to {total} after the longer route (fare_rerated event on {trip}). POL-RD-11 governs and POL-RD-02 does not "
         "run. Under POL-RD-11(a) the rider recovers in full any amount by which charged_total exceeds the quote plus "
         "properly chargeable pass-through lines; there are none (no ERP, airport or waiting line), so {total} - {q} "
         "= {over}, already a multiple of 0.05, which is exactly the {con} contested. The deviation on {gps} "
         "({trace} km against {opt} km, {rawp} %) is not material, so no POL-RD-06 check or referral arises. A "
         "POL-RD-02 recomputation ({careless}) would be the wrong clause.").format(
        pay=t(pay), fare=v.eid("FARE_BREAKDOWN"), q=t(f["quoted_fare_sgd"]), total=t(v.total),
        trip=v.eid("TRIP_RECORD"), over=t(over), con=t(v.contested), gps=v.eid("GPS_TRACE"), trace=k3(v.trace),
        opt=num_txt(v.trip["optimal_distance_km"]), rawp=pct(raw, v.opt), careless=t(careless["pay"]))
    return "FULL_REFUND", pay, None, r


def k4005(v, I, X):
    J = {"lat": X["junction_J"][0], "lng": X["junction_J"][1]}
    at_j = fixes_at(v.pts, J)
    need(len(at_j) == 2, "4005 junction fixes")
    i_in, i_out = at_j
    spur = D(repr(round(path_km(v.pts, i_in, i_out), 3)))
    a, b = stop_run(v.pts)
    stop = v.pts[a]
    stop_s = int(C.diff_s(v.pts[a]["ts"], v.pts[b]["ts"]))
    m = v.msg(3)
    hint = m["waypoint_hint"]
    need(m["sender"] == "RIDER" and m["sent_at"] < v.trip["started_at"], "4005 instruction")
    d_hint = round(C.hav_m(stop, hint), 1)
    need(d_hint <= 200, "4005 corroboration")
    lead = int(C.diff_s(m["sent_at"], v.pts[i_in]["ts"]))
    f = v.fare
    need(f["fare_model"] == "UPFRONT_QUOTE" and D(f["quoted_fare_sgd"]) == v.total, "4005 charged at quote")
    billed = D(repr(f["distance_charged_km"]))
    short = v.trace - billed
    need(short > Decimal("1.0"), "4005 shortfall")
    comp_raw = Decimal("0.75") * short
    comp = min(C.up005(comp_raw), Decimal("15.00"))
    rem = v.trace - spur - v.opt
    need(not established(rem, v.opt), "4005 no fault deviation")
    r = ("DRIVER_COMPENSATION {comp} (amount_sgd mirrors it, POL-GEN-03). {chat} holds {mid} from the rider at {sent}, "
         "before boarding, asking to stop at Northpoint, waypoint_hint {hint}, sent {lead} s before the trace leaves "
         "the SLE corridor at {tin}; {gps} stops {stop_s} s at {stop}, {dh} m from the hint, so POL-RD-04 (a) to (c) "
         "and corroboration hold and the {spur} km spur is the rider's detour. {fare} is UPFRONT_QUOTE, quoted and "
         "charged {total}, so the rider has nothing to recover and POL-RD-11 sends the driver's unrecovered cost on "
         "a rider-requested detour to POL-RD-04's compensation limb: billed distance_charged_km {billed} against "
         "trace_distance_km {trace} is a shortfall of {short} km (> 1.0); 0.75 x {short} = {raw}, rounded up to "
         "{comp}, under the 15.00 cap. The {con} claimed is the driver's estimate.").format(
        comp=t(comp), chat=v.eid("CHAT_LOG"), mid=m["msg_id"], sent=hms(m["sent_at"]), hint=ll_txt(hint), lead=lead,
        tin=hms(v.pts[i_in]["ts"]), gps=v.eid("GPS_TRACE"), stop_s=stop_s, stop=ll_txt(stop), dh=d_hint,
        spur=k3(spur), fare=v.eid("FARE_BREAKDOWN"), total=t(v.total), billed="{0:.2f}".format(billed),
        trace=k3(v.trace), short=k3(short), raw=t(comp_raw), con=t(v.contested))
    return "DRIVER_COMPENSATION", comp, comp, r


def k4006(v, I, X):
    raw = v.trace - v.opt
    need(raw > Decimal("0.8") and not established(raw, v.opt), "4006 RD-01 fails on 20 % only")
    phantom = [(g, gantry_nearest(g, v.pts)) for g in v.fare["erp_gantries"]]
    need(len(phantom) == 1 and phantom[0][1] > 250, "4006 phantom gantry")
    g, dist = phantom[0]
    pay = C.up005(D(g["amount_sgd"]))
    need(pay < v.contested, "4006 partial")
    r = ("PARTIAL_REFUND {pay} with a POL-RD-09(4) billing-integrity referral. {gps} (COMPLETE) measures {trace} km "
         "against optimal_distance_km {opt} on {trip}: excess {raw} km is above 0.8 km but only {rawp} %, so "
         "POL-RD-01's 20 % test fails, no deviation exists and the distance claim fails; the rider's claim of 4-5 km "
         "extra via Yio Chu Kang is contradicted by the trace, which does use Yio Chu Kang Rd and Upper Thomson Rd but "
         "measures only {raw} km over the booked route. {fare} nevertheless charges ERP line {gid} '{gname}' {gamt} "
         "at {gll}; the nearest fix is {gd} m away, so the trace never passes within 250 m. Under POL-RD-09(4) that "
         "line is refunded in full as a standalone correction, whether or not a deviation exists, and recorded as a "
         "billing-integrity finding; POL-RD-10(8) is not engaged because the only unmatched line is the one "
         "refunded. {pay} of the {con} contested is returned.").format(
        pay=t(pay), gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), rawp=pct(raw, v.opt), fare=v.eid("FARE_BREAKDOWN"),
        gid=g["gantry_id"], gname=g["name"], gamt=t(g["amount_sgd"]), gll=ll_txt(g), gd=m1(dist),
        con=t(v.contested))
    return "PARTIAL_REFUND", pay, None, r, [
        "POL-RD-09(4): billing-integrity finding - ERP line {0} '{1}' {2} for a gantry the gps_trace never passes"
        .format(g["gantry_id"], g["name"], t(g["amount_sgd"]))]


def k4007(v, I, X):
    tr = v.trip
    need(D(v.fare["cancellation_fee"]) > 0, "4007 cancellation line")
    need(tr["status"] == "COMPLETED" and tr["cancelled_at"] is None and tr["cancelled_by"] is None and
         tr["cancellation_reason_code"] is None, "4007 no cancellation on the record")
    need(not any("cancel" in e["event_type"] for e in tr["events"]), "4007 no cancellation event")
    mg, mj, med = rd07_limbs(v.pts)
    need(mg <= 90 and mj <= 500, "4007 continuous trace")
    raw = v.trace - v.opt
    need(established(raw, v.opt) and not material(raw, v.opt), "4007 context deviation")
    careless = rd02(v)
    r = ("ESCALATE under POL-RD-10(8). {fare} bills a cancellation_fee line of {cf} on a completed metered trip (total "
         "{total}), but {trip} records status COMPLETED with cancelled_at, cancelled_by and cancellation_reason_code "
         "null and no cancellation event, and {gps} shows a continuous completed trip: the line has no counterpart "
         "anywhere in the gps_trace or trip_record. POL-RD-09(4) refunds only a gantry line the trace never passes "
         "or an airport surcharge on a non-airport trip, so this line is not refunded under it and the RD-10(8) "
         "carve-out does not apply. RD-10 is terminal: no final ruling issues, no money moves and the {con} "
         "contested is held. The deviation itself is clear ({trace} km against {opt} km, {rawp} %, not material; "
         "POL-RD-02 would give {careless}), so this is the policy requiring a person rather than missing evidence; "
         "the ledger entry behind the {cf} line would resolve it.").format(
        fare=v.eid("FARE_BREAKDOWN"), cf=t(v.fare["cancellation_fee"]), total=t(v.total), trip=v.eid("TRIP_RECORD"),
        gps=v.eid("GPS_TRACE"), con=t(v.contested), trace=k3(v.trace), opt=num_txt(tr["optimal_distance_km"]),
        rawp=pct(raw, v.opt), careless=t(careless["pay"]))
    return "ESCALATE", None, None, r


def k4008(v, I, X):
    tr = v.trip
    need(tr["vehicle_type"] == "RYDE_POOL" and tr["optimal_route_source"] == "MATCHED_POOL_ITINERARY", "4008 pool")
    need(any(e["event_type"] == "pool_matched" for e in tr["events"]), "4008 itinerary identified")
    raw = v.trace - v.opt
    need(not established(raw, v.opt), "4008 fails RD-01")
    solo = D(tr["solo_optimal_distance_km"])
    wrong = v.trace - solo
    need(established(wrong, solo), "4008 solo reading would establish")
    w = v.adm("CHAT_LOG")
    # skew between SYSTEM chat messages and the mirrored trip events, from the file
    ev = {e["event_type"]: e["at"] for e in tr["events"]}
    sk = int(C.diff_s(ev["driver_arrived"], [m for m in v.chat["messages"]
                                             if m["text"].startswith("Your driver has arrived")][0]["sent_at"]))
    need(sk < 600, "4008 skew below RD-10(4)")
    r = ("NO_ACTION. {trip} is a RYDE_POOL trip whose record identifies the matched itinerary (optimal_route_source "
         "MATCHED_POOL_ITINERARY; pool_matched event naming the co-rider pick-up at Hougang Ave 1 and set-down at "
         "Sengkang General Hospital), so under POL-RD-12 the baseline is optimal_distance_km {opt}, not "
         "solo_optimal_distance_km {solo}. {gps} (COMPLETE) measures {trace} km: excess {raw} km = {rawp} %, failing "
         "both POL-RD-01 tests, so no deviation exists. The rider's {wrong} km is measured against the solo figure, "
         "the wrong field, and fails on that ground; both figures must be named. {chat} is IMPAIRED ({codes}, weight "
         "{w}; chat clock +{sk} s) but decides nothing, and {sk} s is far below POL-RD-10(4)'s 10 minutes.").format(
        trip=v.eid("TRIP_RECORD"), opt=num_txt(tr["optimal_distance_km"]), solo=num_txt(tr["solo_optimal_distance_km"]),
        gps=v.eid("GPS_TRACE"), trace=k3(v.trace), raw=k3(raw), rawp=pct(raw, v.opt),
        wrong=t(wrong.quantize(Decimal("0.01"))), chat=v.eid("CHAT_LOG"), codes=", ".join(w["issues"]),
        w=w["weight_multiplier"], sk=sk)
    return "NO_ACTION", None, None, r


def k4009(v, I, X):
    raw = v.trace - v.opt
    need(established(raw, v.opt) and raw > Decimal("8.0") and raw / v.opt > Decimal("0.50"),
         "4009 established and material on both tests")
    mg, mj, med = rd07_limbs(v.pts)
    need(mg <= 90 and mj <= 500 and med <= 30, "4009 policy-clean trace")
    gap = v.gps["gaps"][0]
    need(len(v.gps["gaps"]) == 1, "4009 one gap")
    i = [k for k, p in enumerate(v.pts) if p["ts"] == gap["from"]][0]
    jump = C.hav_m(v.pts[i], v.pts[i + 1])
    need(round(jump, 1) == round(mj, 1), "4009 the largest step is the gap step")
    others = [C.diff_s(v.pts[k - 1]["ts"], v.pts[k]["ts"]) for k in range(1, len(v.pts)) if k != i + 1]
    other_max = int(max(others))
    need(other_max <= 30 and int(med) <= 30 and int(gap["gap_sec"]) > other_max, "4009 cadence")
    w = v.adm("GPS_TRACE")
    need(w["weight_multiplier"] >= 0.70, "4009 weight")
    need(v.adm("CHAT_LOG")["status"] == "MISSING" and v.adm("TRAFFIC_ADVISORY")["status"] == "MISSING",
         "4009 chat and advisory missing")
    cited = v.d["claim_text"] + " " + (v.d["counterparty_statement"] or {}).get("text", "")
    need(v.eid("CHAT_LOG") not in cited and v.eid("TRAFFIC_ADVISORY") not in cited and "EV-" not in cited,
         "4009 no party cites an artifact")
    quote = v.d["counterparty_statement"]["text"].split(".")[0]
    need(v.d["counterparty_statement"]["submitted_by"] == "DRIVER", "4009 driver statement")
    need(v.fare["fare_model"] == "METERED", "4009 metered")
    flags, trips = v.dprof["deviation_flags_90d"], v.dprof["completed_trips_90d"]
    need(flags >= 3, "4009 pattern")
    p = rd02(v)
    passthru = D(v.fare["tolls_erp"]) + D(v.fare["airport_surcharge"])
    need(passthru == 0, "4009 nothing to carve out")
    full = v.total - passthru
    need(full == v.contested, "4009 full refund equals contested")
    need(full > EXEC_THRESHOLD, "4009 above execution threshold")
    need(p["pay"] >= DE_MINIMIS and p["pay"] < v.total * Decimal("0.9"), "4009 RD-02 figure is a partial")
    r = ("FULL_REFUND {full} with a POL-RD-06(c) driver-conduct referral. {gps} trace_distance_km {trace} against "
         "optimal_distance_km {opt} on {trip} (booked optimal; no POL-RD-03, -04, -05 or -12 adjustment): excess "
         "{raw} km = {rawp} %, above 20 % and 0.8 km, so established, and above 50 % and 8.0 km, so MATERIAL under "
         "POL-RD-01. {gps} is IMPAIRED ({codes}, weight {w}): one {gs} s gap {gfrom}-{gto} at the start, bounding "
         "fixes {jump} m apart, every other interval {omax} s or less. No POL-RD-07 limb fires: (a) {gs} s is not "
         "over 90 s; (b) {jump} m is not over 500 m; (c) the sustained cadence is {med} s, not over 30 s, and one "
         "isolated interval is not a sustained one. The trace therefore establishes the deviation on its own; the "
         "cap is {w}, above the 0.70 floor, and the finding survives the discount because the gap spans only "
         "{jkm} km (POL-GEN-02). The driver's statement ('{quote}') cites no evidence id and invokes no exculpatory "
         "clause, so it is discarded (POL-RD-08). {chat} and {adv} are MISSING (weight 0.0) and no party cites "
         "either for POL-RD-04 or POL-RD-03, so POL-RD-10(5) is not engaged (for the advisory, POL-RD-13(1)). "
         "Because the deviation is material, {dprof} is consulted: deviation_flags_90d {flags} (3 or more) "
         "establishes a pattern under POL-RD-06; lifetime prior_deviation_flags {pdf} is not read (POL-GEN-01). "
         "POL-RD-02 figure ({model}, surge_multiplier {surge} on {fare}): recomputed = ({b} + {pkm} x {opt} + {pmin} "
         "x {omin}) x {surge} + {plat} + {erp} on-route ERP = {rec}; {total} - {rec} = {rawref}, rounded up to "
         "{pay}. POL-RD-06(b): a material deviation substantiated on this trip's own trace licenses FULL_REFUND of "
         "charged_total {total} in place of the {pay} partial; {fare} carries no ERP, toll or airport line to "
         "settle under POL-RD-09. {full} equals the contested amount. It exceeds the {thr} execution threshold, so "
         "it is issued and held for release (POL-GEN-05), not escalated.").format(
        full=t(full), gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), rawp=pct(raw, v.opt), codes=", ".join(w["issues"]),
        w=w["weight_multiplier"], gs=int(gap["gap_sec"]), gfrom=hms(gap["from"]), gto=hms(gap["to"]),
        jump=m1(jump), omax=other_max, med=int(med), jkm="{0:.2f}".format(jump / 1000), quote=quote,
        chat=v.eid("CHAT_LOG"), adv=v.eid("TRAFFIC_ADVISORY"), dprof=v.eid("DRIVER_PROFILE"), flags=flags,
        pdf=v.dprof["prior_deviation_flags"], model=v.fare["fare_model"], surge=num_txt(v.fare["surge_multiplier"]),
        fare=v.eid("FARE_BREAKDOWN"), b=t(RATES["base_fare"]), pkm=t(RATES["per_km"]), pmin=t(RATES["per_min"]),
        omin=num_txt(v.trip["optimal_duration_min"]), plat=t(RATES["platform_fee"]),
        erp=t(v.trip["optimal_route_erp_sgd"]), rec=t(p["rec"]), total=t(v.total), rawref=t(p["raw"]),
        pay=t(p["pay"]), thr=t(EXEC_THRESHOLD))
    return "FULL_REFUND", full, None, r, ["POL-RD-06(c): driver-conduct review"]


def k4010(v, I, X):
    tr = v.trip
    need(tr["dropoff_amended_at"] is not None and tr["amended_optimal_distance_km"] is None and
         tr["amended_optimal_duration_min"] is None, "4010 missing re-quote")
    need(any(e["event_type"] == "route_requote_failed" for e in tr["events"]), "4010 requote event")
    m = v.msg(3)
    need(m["sender"] == "RIDER" and m["waypoint_hint"] is None, "4010 destination message")
    w = v.adm("TRIP_RECORD")
    r = ("ESCALATE under POL-RD-10(5) via POL-RD-05. {trip} records dropoff_amended_at {amd} (original_dropoff {od}, "
         "dropoff {nd}, matching {mid} on {chat}), but amended_optimal_distance_km and amended_optimal_duration_min "
         "are null (event route_requote_failed); the record is IMPAIRED ({codes}, weight {w}). The driver relies on "
         "the relocation to explain the {trace} km on {gps} against the booked {opt} km. POL-RD-05 says that where an "
         "amendment timestamp is present and the re-quote is null the clause cannot be run, POL-RD-10(5) applies and "
         "no substitute figure may be derived; RD-10(5) gives exactly this as its example. The deciding fact, the "
         "optimal distance between the amended endpoints, is not in the record, and measuring against the booked "
         "{opt} km would count post-amendment distance against the driver. No money moves; the platform's re-quote "
         "for the amended destination would resolve the case.").format(
        trip=v.eid("TRIP_RECORD"), amd=hms(tr["dropoff_amended_at"]), od=tr["original_dropoff"]["label"].split(" (")[0],
        nd=tr["dropoff"]["label"].split(" (")[0], mid=m["msg_id"], chat=v.eid("CHAT_LOG"),
        codes=", ".join(w["issues"]), w=w["weight_multiplier"], trace=k3(v.trace), gps=v.eid("GPS_TRACE"),
        opt=num_txt(tr["optimal_distance_km"]))
    return "ESCALATE", None, None, r


def k4011(v, I, X):
    raw = v.trace - v.opt
    need(established(raw, v.opt) and not material(raw, v.opt), "4011 established")
    p = rd02(v)
    need(p["pay"] >= DE_MINIMIS and p["pay"] < v.total * Decimal("0.9") and p["pay"] < v.contested, "4011 partial")
    r = ("PARTIAL_REFUND {pay}. {gps} (COMPLETE) measures {trace} km against optimal_distance_km {opt} on {trip}: "
         "excess {raw} km = {rawp} %, established under POL-RD-01 and not material. Under POL-RD-08 the burden shifts "
         "and the driver's 'followed the navigation app' cites no artifact or clause, so it is discarded; no traffic "
         "cause, chat instruction or amendment is in play. POL-RD-02 with surge_multiplier {surge} from {fare} and "
         "{erp} on-route ERP: recomputed {b} + {dist} + {time} + {plat} = {rec}; charged_total {total}; refund {pay}, "
         "already a multiple of 0.05, of the {con} contested.").format(
        pay=t(p["pay"]), gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), rawp=pct(raw, v.opt), surge=v.fare["surge_multiplier"],
        fare=v.eid("FARE_BREAKDOWN"), erp=t(v.trip["optimal_route_erp_sgd"]), b=t(p["base"]), dist=t(p["dist"]),
        time=t(p["time"]), plat=t(RATES["platform_fee"]), rec=t(p["rec"]), total=t(v.total), con=t(v.contested))
    need(p["raw"] == p["pay"], "4011 already a multiple of 0.05")
    return "PARTIAL_REFUND", p["pay"], None, r


def k4012(v, I, X):
    raw = v.trace - v.opt
    need(established(raw, v.opt) and not material(raw, v.opt), "4012 established")
    a1, a2 = v.payload("TRAFFIC_ADVISORY", 0), v.payload("TRAFFIC_ADVISORY", 1)
    near1 = round(seg_to_fixes_m(a1["geometry"]["from"], a1["geometry"]["to"], v.pts), 1)
    drop1 = round(seg_to_point_m(a1["geometry"]["from"], a1["geometry"]["to"], v.trip["dropoff"]), 1)
    near2 = round(seg_to_fixes_m(a2["geometry"]["from"], a2["geometry"]["to"], v.pts), 1)
    same_ = (near1, drop1, near2) == (X["advisory_01_segment_min_distance_to_trace_m"],
                                      X["advisory_01_segment_min_distance_to_dropoff_m"],
                                      X["advisory_02_segment_min_distance_to_trace_m"])
    need(same_, "4012 advisory geometry {0}".format((near1, drop1, near2)))
    need(max(a1["geometry"]["from"]["lng"], a1["geometry"]["to"]["lng"]) < min(p["lng"] for p in v.pts),
         "4012 closed section west of every fix")
    need(C.add_min(a1["valid_from"], -15) <= v.trip["started_at"] and
         v.trip["ended_at"] <= C.add_min(a1["valid_to"], 15), "4012 window covered")
    for a in (a1, a2):
        need(all(a[k] is not None for k in ("segment", "geometry", "valid_from", "valid_to",
                                            "shortest_lawful_alternative_km")), "4012 advisory fields")
    p = rd02(v)
    need(p["pay"] == D(v.fare["refund_issued_sgd"]) == v.contested, "4012 platform refund equals RD-02")
    r = ("NO_ACTION. {gps} (COMPLETE) measures {trace} km against optimal_distance_km {opt} on {trip}, an established, "
         "non-material deviation of {raw} km ({rawp} %) under POL-RD-01, so the driver must discharge it. He says the "
         "PIE was closed at Eunos. The only PIE notice, {a1id}, closes the PIE (towards Tuas) between the Adam Road and "
         "Eng Neo Avenue exits; it is valid {vf} to {vt} and covers the trip, but the booked route (route_planned on "
         "{trip}) leaves the PIE for Toa Payoh before that section, whose nearest point is {drop1} m west of the "
         "dropoff and {near1} m from every fix. POL-RD-03 fails on limb (a), since an advisory covering a corridor "
         "the optimal route never uses exonerates nothing, and on limb (c); nothing closed the PIE at Eunos, so the "
         "driver's account is contradicted. {a2id} is roadworks on the TPE, the driver's own route, and exonerates "
         "nothing. Both advisories are present, cover the trip window and carry shortest_lawful_alternative_km, so "
         "POL-RD-10(5) is not engaged. POL-RD-02: recomputed {b} + {dist} + {time} + {plat} = {rec}; {total} - {rec} "
         "= {pay}, exactly the refund_issued_sgd {ri} on {fare}. The driver's claim to have the {con} returned is not "
         "supported; under POL-GEN-03 NO_ACTION on this driver-filed dispute leaves the rider refunded.").format(
        gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), rawp=pct(raw, v.opt), a1id=v.eid("TRAFFIC_ADVISORY", 0),
        vf=hm(a1["valid_from"]), vt=hm(a1["valid_to"]), drop1=m1(drop1), near1=m1(near1),
        a2id=v.eid("TRAFFIC_ADVISORY", 1), b=t(p["base"]), dist=t(p["dist"]), time=t(p["time"]),
        plat=t(RATES["platform_fee"]), rec=t(p["rec"]), total=t(v.total), pay=t(p["pay"]),
        ri=t(v.fare["refund_issued_sgd"]), fare=v.eid("FARE_BREAKDOWN"), con=t(v.contested))
    return "NO_ACTION", None, None, r


def k4013(v, I, X):
    raw = v.trace - v.opt
    need(established(raw, v.opt) and not material(raw, v.opt), "4013 established")
    m = v.msg(2)
    hint = m["waypoint_hint"]
    need(m["sender"] == "RIDER" and m["sent_at"] < v.trip["started_at"] and hint is not None, "4013 instruction")
    near = round(min_to_fixes_m(hint, v.pts), 1)
    need(near > 200, "4013 not corroborated")
    p = rd02(v)
    need(p["pay"] >= DE_MINIMIS and p["pay"] < v.contested, "4013 partial")
    rp = v.rprof
    need(rp["deviation_claims_60d"] < 4, "4013 RD-08 rider factor not engaged")
    r = ("PARTIAL_REFUND {pay}. {gps} (COMPLETE) measures {trace} km against optimal_distance_km {opt} on {trip}: "
         "excess {raw} km = {rawp} %, established, not material (POL-RD-01). The driver relies on the rider's request: "
         "{mid} on {chat} is from the rider, sent at {sent} before boarding, and names {label} with waypoint_hint "
         "{hint}, meeting POL-RD-04 (a) to (c). But the nearest trace fix is {near} m from the hint and no road was "
         "named, so under POL-RD-14 the instruction did not cause the excess: it was found and not corroborated, "
         "nothing is excluded, and POL-RD-10(7) is not engaged. POL-RD-02 with surge {surge} from {fare}: recomputed "
         "{b} + {dist} + {time} + {plat} = {rec}; {total} - {rec} = {rawref}, rounded up to {pay} of the {con} "
         "contested. The driver's appeal to the rider's prior_disputes_filed ({pdf}) on {rprof} is context only "
         "(POL-GEN-01); deviation_claims_60d is {dc}.").format(
        pay=t(p["pay"]), gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), rawp=pct(raw, v.opt), mid=m["msg_id"], chat=v.eid("CHAT_LOG"),
        sent=hms(m["sent_at"]), label=hint["label"], hint=ll_txt(hint), near=m1(near),
        surge=v.fare["surge_multiplier"], fare=v.eid("FARE_BREAKDOWN"), b=t(p["base"]), dist=t(p["dist"]),
        time=t(p["time"]), plat=t(RATES["platform_fee"]), rec=t(p["rec"]), total=t(v.total), rawref=t(p["raw"]),
        con=t(v.contested), pdf=rp["prior_disputes_filed"], rprof=v.eid("RIDER_PROFILE"),
        dc=rp["deviation_claims_60d"])
    return "PARTIAL_REFUND", p["pay"], None, r


def k4014(v, I, X):
    raw = v.trace - v.opt
    need(established(raw, v.opt) and not material(raw, v.opt), "4014 established")
    aid = v.eid("TRAFFIC_ADVISORY")
    need(v.payload("TRAFFIC_ADVISORY") is None and aid in v.d["claim_text"], "4014 cited missing advisory")
    w = v.adm("TRAFFIC_ADVISORY")
    r = ("ESCALATE under POL-RD-10(5). {gps} (COMPLETE) measures {trace} km against optimal_distance_km {opt} on "
         "{trip}, an established deviation of {raw} km ({rawp} %), so the driver must discharge it. He invokes "
         "POL-RD-03, asserting an accident on the PIE near Kallang on the booked route, and cites the LTA advisory "
         "{aid} by its identifier; that artifact is MISSING (weight {w}, payload null). POL-RD-10(5) forbids a ruling "
         "where an exculpatory clause is invoked against a cited artifact missing from the pool. POL-RD-13 discards "
         "only uncited traffic assertions and states that it does not narrow POL-RD-10(5) where the party cites the "
         "missing identifier, so the case still escalates. The advisory's admissibility note records only that no "
         "payload was retrieved, not that no advisory was issued, so whether the incident existed cannot be settled "
         "on the record; the {con} is held, and the advisory payload would resolve it.").format(
        gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), rawp=pct(raw, v.opt), aid=aid, w=w["weight_multiplier"],
        con=t(v.contested))
    return "ESCALATE", None, None, r


def k4015(v, I, X):
    raw = v.trace - v.opt
    need(established(raw, v.opt) and material(raw, v.opt) and raw <= Decimal("8.0"), "4015 material on %")
    flags, trips = v.dprof["deviation_flags_90d"], v.dprof["completed_trips_90d"]
    need(flags < 3 and not (trips >= 40 and D(flags) / D(trips) >= Decimal("0.05")), "4015 no pattern")
    aid = v.eid("TRAFFIC_ADVISORY")
    need(v.payload("TRAFFIC_ADVISORY") is None and aid not in v.d["claim_text"] and
         aid not in (v.d["counterparty_statement"] or {}).get("text", ""), "4015 uncited missing advisory")
    gm = [(g, gantry_nearest(g, v.pts)) for g in v.fare["erp_gantries"]]
    need(all(dist <= 250 for _, dist in gm), "4015 gantries crossed")
    p = rd02(v)
    need(p["pay"] >= DE_MINIMIS and p["pay"] < v.total * Decimal("0.9") and p["pay"] < v.contested and
         p["pay"] <= Decimal("150"), "4015 partial")
    need(p["pay"] > EXEC_THRESHOLD, "4015 above threshold")
    r = ("PARTIAL_REFUND {pay}. {gps} (COMPLETE) measures {trace} km against optimal_distance_km {opt} on {trip}: "
         "excess {raw} km = {rawp} %, established and MATERIAL under POL-RD-01. POL-RD-06 is therefore consulted on "
         "{dprof}: deviation_flags_90d {flags} of completed_trips_90d {trips} is no pattern, so no uplift; "
         "prior_deviation_flags {pdf} is the lifetime near-synonym and may not be used (POL-GEN-01). The driver's ECP "
         "accident cites no advisory and {aid} is MISSING, so under POL-RD-13(1)-(2) the assertion is discarded, "
         "POL-RD-10(5) is not engaged and the deviation stands at the measured figure. POL-RD-02 with "
         "surge_multiplier {surge} from {fare} and on-route ERP {erp}: recomputed ({b} + {dist} + {time}) x {surge} + "
         "{plat} = {rec}; charged_total {total}; refund {rawref} rounded up to {pay}. The two matched off-route "
         "gantries ({g1} and {g2}) are already inside that figure (POL-RD-09(1)) and are not added. {pay} of the {con} "
         "contested; above {thr} it is held for release (POL-GEN-05).").format(
        pay=t(p["pay"]), gps=v.eid("GPS_TRACE"), trace=k3(v.trace), opt=num_txt(v.trip["optimal_distance_km"]),
        trip=v.eid("TRIP_RECORD"), raw=k3(raw), rawp=pct(raw, v.opt), dprof=v.eid("DRIVER_PROFILE"), flags=flags,
        trips=trips, pdf=v.dprof["prior_deviation_flags"], aid=aid, surge=v.fare["surge_multiplier"],
        fare=v.eid("FARE_BREAKDOWN"), erp=t(v.trip["optimal_route_erp_sgd"]), b=t(p["base"]), dist=t(p["dist"]),
        time=t(p["time"]), plat=t(RATES["platform_fee"]), rec=t(p["rec"]), total=t(v.total), rawref=t(p["raw"]),
        g1=t(gm[0][0]["amount_sgd"]), g2=t(gm[1][0]["amount_sgd"]), con=t(v.contested), thr=t(EXEC_THRESHOLD))
    return "PARTIAL_REFUND", p["pay"], None, r


KEYS = {4001: k4001, 4002: k4002, 4003: k4003, 4004: k4004, 4005: k4005, 4006: k4006, 4007: k4007, 4008: k4008,
        4009: k4009, 4010: k4010, 4011: k4011, 4012: k4012, 4013: k4013, 4014: k4014, 4015: k4015}


def key_for(n, case, intent, extra_measurements):
    v = View(case)
    res = KEYS[n](v, intent, extra_measurements)
    ruling, amount, dc, rationale = res[:4]
    referrals = res[4] if len(res) > 4 else []
    # the computed outcome must be the blueprint's intended outcome
    need(ruling == intent["expected_ruling"], "{0}: ruling {1} vs intent {2}".format(n, ruling,
                                                                                     intent["expected_ruling"]))
    need((amount is None and intent["amount_sgd"] is None) or
         (amount is not None and intent["amount_sgd"] is not None and D(amount) == D(intent["amount_sgd"])),
         "{0}: amount {1} vs intent {2}".format(n, amount, intent["amount_sgd"]))
    need((dc is None and intent["driver_compensation_sgd"] is None) or
         (dc is not None and intent["driver_compensation_sgd"] is not None and
          D(dc) == D(intent["driver_compensation_sgd"])), "{0}: driver compensation".format(n))
    need(referrals == intent["referrals"], "{0}: referrals {1}".format(n, referrals))
    need(rationale == intent["rationale"], "{0}: rationale differs from the blueprint:\n  built: {1}\n  bluep: {2}"
         .format(n, rationale, intent["rationale"]))
    rec = C.key_record(n, ruling, amount, dc, referrals, intent["governing_clauses"], intent["difficulty"], rationale)
    probs = C.validate_key(rec, case)
    need(not probs, "{0}: {1}".format(n, probs))
    return rec
