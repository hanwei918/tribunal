"""NO_SHOW_CHARGE cases 4051-4065, generated from build/blueprint_ns.json.

Every number written to a case file is computed here from the blueprint's parameters:
  - GPS fixes and rider fixes from each case's timed legs and emission blocks (ns_geo.synthesize, seeded
    common.rng); counts, first / last fix, gaps, max gap and trace_distance_km from the fixes (common.gps_trace);
  - platform_policy figures (the AUTHORED-V1 greater-of rule from no_show.json, the gross figure at the published
    gross / net ratio where the record states a non-default net), fare lines (the fee line from the policy figure in
    force; 4063's metered lines from the trip's own fixes and the route_deviation.json rate card), totals, refunds,
    the contested amount, chat_message_count and the trip-level distances of 4063;
  - admissibility weights (the integrity product rule);
  - every figure quoted in a text (admissibility notes, issue details, event details, SYSTEM chat lines, party
    statements, the rationale): each text is a template in ns_texts.py filled from values measured on the case AS
    WRITTEN (a JSON round trip of the built case), see values().
Each computed value is asserted against the figure the blueprint states, so the files are exactly the blueprint.
The answer key is decided by decide() from the written case (the rounded trace figures, the cent-rounded fare
lines, the stored trip fields) and asserted against the blueprint's intent.
"""
import json
import os
import re
from decimal import Decimal

import common as C
import ns_geo as G
import ns_texts as TX

_BP_PATH = os.path.join(C.BUILD_DIR, "blueprint_ns.json")
with open(_BP_PATH, encoding="utf-8") as _f:
    BLUEPRINT = {rec["case_no"]: rec for rec in json.load(_f)}

NSP = C._load_json("no_show.json")
FS = NSP["fee_schedule"]
DEFAULTS = FS["defaults"]
RADIUS = FS["arrival_radius_m"]
PRESENCE = FS["rider_presence_radius_m"]
ACC_FILTER = FS["gps_accuracy_filter_m"]
CEILING_M = FS["wrong_entrance_ceiling_m"]
COMP_RATE = C.D(FS["driver_compensation_rate"])
GOODWILL_RATE = C.D(FS["pin_ambiguity_goodwill_rate"])
FLOOR = NSP["confidence_floor"]
GAP_POLICY_S = NSP["integrity"]["gps_gap_policy_threshold_sec"]
if ACC_FILTER != G.ACC_FILTER_M:
    raise C.BuildError("accuracy filter differs between no_show.json and ns_geo")

# Figures written in the clause texts themselves (version 6), named by clause.
REPLY_S = 120          # POL-NS-04(b): reply within 120 seconds
FALSE_D_M = 300        # POL-NS-05: more than 300 m from the pin at the arrived event
FALSE_V_KPH = 15       # POL-NS-05: travelling at 15 km/h or above
LEASH_M = 300          # POL-NS-06(i): never more than 300 m from the pin
SKEW_S = 90            # POL-NS-08(a)
MIN_WIN_FIXES = 6      # POL-NS-08(b)
CHAT_GAP_S = 300       # POL-NS-08(c): a gap of more than 5 minutes spanning the arrival marker
FARM_N = 4             # POL-NS-07 anti-farming: no_show_terminations_30d 4 or more
FARM_RATE = Decimal("0.08")   # POL-NS-07 anti-farming: rate greater than 0.08
RIDER_ABUSE_N = 3      # POL-NS-09(d)
PAIR_N = 2             # POL-NS-09(c)
LOOKBACK_S = 900       # POL-NS-02: the 15 minutes preceding the cancellation
ETA_SLACK_S = 180      # POL-NS-10(f): arrival within 180 s of the first ETA


class Mismatch(C.BuildError):
    pass


def need(cond, msg):
    if not cond:
        raise Mismatch(msg)


def same(got, want, what):
    need(got == want, "{0}: computed {1!r} but blueprint says {2!r}".format(what, got, want))
    return got


def jrt(x):
    """JSON round trip (tuples -> lists, the form the blueprint and the written files hold)."""
    return json.loads(json.dumps(x))


def hms(t):
    return t[11:19] if t else None


def money(x):
    return C.money_str(x)


def fnum(x):
    """10.0 -> '10', 67.9 -> '67.9'."""
    x = float(x)
    return str(int(x)) if x == int(x) else repr(x)


# ---------------------------------------------------------------------------
# text keys
# ---------------------------------------------------------------------------
def blueprint_texts(e):
    """{text key: text} for every free text of the case that can carry a figure."""
    f = e["facts"]
    d = f["dispute"]
    out = {"claim": d["claim_text"]}
    if d["counterparty_statement"]:
        out["cp"] = d["counterparty_statement"]["text"]
    for i, ev in enumerate(f["trip_record"]["fields"]["events"]):
        out["ev:{0}".format(i)] = ev["detail"]
    for m in f["chat_log"]["messages"] or []:
        out["msg:{0}".format(m["k"])] = m["text"]
    for k, a in f["admissibility"].items():
        out["adm:" + k] = a["notes"]
        for i, x in enumerate(a.get("issue_details") or []):
            out["det:{0}:{1}".format(k, i)] = x["detail"]
    out["rationale"] = e["intent"]["key_rationale"]
    return out


# Corrections to blueprint texts found when the figures were recomputed from the case as written. Each entry
# replaces a literal in the blueprint text; the generated text must equal the corrected blueprint text.
TEXT_FIXES = {
    # The chat's largest interval is 13:06:15 -> 13:14:10 (the SYSTEM cancellation line), 475 s, not the 330 s
    # between the first two messages; the interval spanning the arrival event (135 s) is unchanged.
    (4061, "adm:CHAT_LOG"): [("Largest interval 330 s (12:58:30 to 13:04:00)",
                              "Largest interval 475 s (13:06:15 to 13:14:10)")],
    # The rider's four device fixes report 35.4-44.8 m accuracy; "35-50 m" was the design band, not the record.
    (4057, "rationale"): [("filtered at 35-50 m accuracy", "filtered at 35.4-44.8 m accuracy")],
}


def expected_texts(e):
    """The blueprint texts with the TEXT_FIXES corrections applied."""
    out = blueprint_texts(e)
    for (n, key), fixes in TEXT_FIXES.items():
        if n != e["case_no"]:
            continue
        for old, new in fixes:
            need(out[key].count(old) == 1, "{0} {1}: text fix target not found once".format(n, key))
            out[key] = out[key].replace(old, new)
    return out


# ---------------------------------------------------------------------------
# computed figures
# ---------------------------------------------------------------------------
def policy_block(e):
    """trip_record.platform_policy, with its computed money figures asserted against the blueprint."""
    f = e["facts"]
    want = f["trip_record"]["fields"]["platform_policy"]
    over = {k: want[k] for k in C.PP_KEYS if k != "source" and want[k] != DEFAULTS[k]}
    tr = f["trip_record"]["fields"]
    if want["source"] == "AUTHORED-V1":
        # fee_schedule.resolution_rule: a version-1 record's backfilled figure is the GREATER of zone class and
        # vehicle tier.
        fee = max(C.D(FS["zone_class_fee_sgd"][tr["pickup_zone_class"]]),
                  C.D(FS["vehicle_tier_fee_sgd"][tr["vehicle_type"]]))
        over["cancellation_fee_sgd"] = C.q2(fee)
    if want["rider_gross_cancellation_fee_sgd"] is not None and \
            C.D(want["cancellation_fee_sgd"]) != C.D(DEFAULTS["cancellation_fee_sgd"]):
        # a non-default net figure carries the gross at the published gross / net ratio (6.61 / 4.50)
        ratio = C.D(DEFAULTS["rider_gross_cancellation_fee_sgd"]) / C.D(DEFAULTS["cancellation_fee_sgd"])
        over["rider_gross_cancellation_fee_sgd"] = C.q2(C.D(want["cancellation_fee_sgd"]) * ratio)
    pp = C.platform_policy(source=want["source"], **over)
    return same(pp, want, "{0} platform_policy".format(e["case_no"]))


def fee_line_basis(e):
    """Which policy figure the ledger's cancellation-fee line carries: 'gross', 'net' or None (no fee line)."""
    fb = e["facts"]["fare_breakdown"]["fields"]
    pp = e["facts"]["trip_record"]["fields"]["platform_policy"]
    line = C.D(fb["cancellation_fee"])
    if line == 0:
        return None
    if pp["rider_gross_cancellation_fee_sgd"] is not None and line == C.D(pp["rider_gross_cancellation_fee_sgd"]):
        return "gross"
    need(line == C.D(pp["cancellation_fee_sgd"]), "{0}: fee line is neither net nor gross".format(e["case_no"]))
    return "net"


def trip_fixes(points, trip):
    return [p for p in points if C.parse_ts(trip["started_at"]) <= C.parse_ts(p["ts"]) <=
            C.parse_ts(trip["ended_at"])]


def fare_fields(e, pp, points, trip_fields):
    """fare_breakdown arguments computed from the policy block, the basis and (completed trips) the trip's fixes."""
    want = dict(e["facts"]["fare_breakdown"]["fields"])
    out = {k: want[k] for k in ("fare_model", "payment_status", "charged_at", "surge_multiplier")}
    basis = fee_line_basis(e)
    if basis is not None:
        line = C.D(pp["rider_gross_cancellation_fee_sgd"] if basis == "gross" else pp["cancellation_fee_sgd"])
        out["cancellation_fee"] = C.q2(line)
    else:
        # completed trip: metered lines from the trip's own fixes and the rate card, plus the waiting-time line
        rates = C.rd_fare_constants()
        tp = trip_fixes(points, trip_fields)
        billed_km = C.D(str(round(C.trace_distance(tp), 2)))
        mins = C.D(str(C.diff_s(trip_fields["started_at"], trip_fields["ended_at"]) / 60))
        out.update({"base_fare": C.q2(rates["base_fare"]), "distance_fare": C.q2(billed_km * rates["per_km"]),
                    "time_fare": C.q2(mins * rates["per_min"]), "platform_fee": C.q2(rates["platform_fee"]),
                    "waiting_time_fee": C.q2(C.D(pp["waiting_fee_sgd"])),
                    "distance_charged_km": float(billed_km), "time_charged_min": float(mins),
                    "per_km_rate_sgd": rates["per_km"], "per_min_rate_sgd": rates["per_min"],
                    "surge_amount": 0, "airport_surcharge": 0, "cancellation_fee": 0, "promo_discount": 0,
                    "erp_gantries": []})
    total = sum((C.D(out.get(k, 0)) for k in ("base_fare", "distance_fare", "time_fare", "surge_amount",
                                                "airport_surcharge", "platform_fee", "cancellation_fee",
                                                "waiting_time_fee")), Decimal(0)) - C.D(out.get("promo_discount", 0))
    out["total_charged"] = C.q2(total)
    out["refund_issued_sgd"] = C.q2(total) if out["payment_status"] == "REFUNDED" else C.q2(0)
    for k, v in want.items():
        if k in out:
            got = out[k]
            if isinstance(v, str) and k not in ("fare_model", "payment_status", "charged_at"):
                need(C.D(got) == C.D(v), "{0} fare {1}: computed {2} but blueprint says {3}".format(
                    e["case_no"], k, got, v))
            else:
                same(jrt(got) if not isinstance(got, Decimal) else str(got), v if not isinstance(got, Decimal)
                     else str(C.D(v)), "{0} fare {1}".format(e["case_no"], k))
    need(set(want) <= set(out), "{0}: fare fields not computed: {1}".format(e["case_no"], sorted(set(want) - set(out))))
    return out


def contested_amount(e, fare, pp):
    """The contested figure: the whole fee line, the net fee, or the waiting-time line (by what the filer disputes)."""
    want = C.D(e["facts"]["dispute"]["amount_contested_sgd"])
    options = [("line", C.D(fare["cancellation_fee"])), ("net", C.D(pp["cancellation_fee_sgd"])),
               ("waiting", C.D(fare.get("waiting_time_fee", 0)))]
    for name, v in options:
        if v > 0 and v == want:
            return C.q2(v)
    raise Mismatch("{0}: contested {1} is none of {2}".format(e["case_no"], want, options))


def trip_fields(e, pp, points, chat_count):
    want = e["facts"]["trip_record"]["fields"]
    out = dict(want)
    out["platform_policy"] = pp
    out["chat_message_count"] = chat_count
    if want.get("status") == "COMPLETED":
        km = C.trace_distance(trip_fixes(points, want))
        out["actual_distance_km"] = round(km, 1)
        out["actual_duration_min"] = C.diff_s(want["started_at"], want["ended_at"]) / 60
        opt = C.D(str(want["optimal_distance_km"]))
        out["deviation_pct"] = round(float((C.D(str(out["actual_distance_km"])) - opt) / opt * 100), 1)
        for k in ("actual_distance_km", "actual_duration_min", "deviation_pct"):
            same(out[k], want[k], "{0} trip {1}".format(e["case_no"], k))
    same(out["chat_message_count"], want["chat_message_count"], "{0} chat_message_count".format(e["case_no"]))
    return out


# ---------------------------------------------------------------------------
# case assembly
# ---------------------------------------------------------------------------
def build_case(e, texts):
    n = e["case_no"]
    f = e["facts"]
    meta = f["artifact_meta"]
    gen, assessed = meta["generated_at"], meta["assessed_at"]
    same(assessed, C.add_s(gen, 5), "{0} assessed_at".format(n))
    same(gen, f["dispute"]["filed_at"], "{0} generated_at".format(n))
    src = meta["sources"]
    g = f["gps_trace"]
    day = f["trip_record"]["fields"]["requested_at"][:10]
    em = [x for x in g["design"]["emission"] if x["kind"] == "driver_fixes"][0]
    schedule = [p["ts"] for p in g["points"][:em["times"]["count"]]]
    pts, rider = G.synthesize(n, g["design"], schedule, day)
    same(pts, g["points"], "{0} driver fixes".format(n))
    same(rider, g["rider_track"], "{0} rider fixes".format(n))
    b = g["build"]
    gps = C.gps_trace(n, pts, rider_track=rider, expected_interval_sec=b["expected_interval_sec"],
                      gap_threshold_s=b["gap_threshold_s"], coverage_pct=b["coverage_pct"])
    for k, v in g["payload_summary"].items():
        same(jrt(gps[k]), v, "{0} gps_trace {1}".format(n, k))

    ch = f["chat_log"]
    chat, chat_count = None, 0
    if not ch["missing"]:
        msgs = [C.msg(x["sender"], texts["msg:{0}".format(x["k"])], x["sent_at"], read_at=x["read_at"],
                      delivered_at=x["delivered_at"], channel=x["channel"], language=x["language"],
                      redacted=x["redacted"], waypoint_hint=x["waypoint_hint"], k=x["k"]) for x in ch["messages"]]
        chat = C.chat_log(n, msgs, truncated=ch["truncated"])
        chat_count = max(x["k"] for x in ch["messages"])      # the highest sequence number the platform issued
        if not ch["truncated"]:
            same([x["k"] for x in ch["messages"]], list(range(1, chat_count + 1)), "{0} message numbering".format(n))

    pp = policy_block(e)
    tf = trip_fields(e, pp, pts, chat_count)
    tf["events"] = [dict(ev, detail=texts["ev:{0}".format(i)]) for i, ev in enumerate(tf["events"])]
    trip = C.trip_record(n, **tf)
    fare = C.fare_breakdown(n, **fare_fields(e, pp, pts, tf))
    rp = C.rider_profile(f["rider_profile"]["party_id"], f["rider_profile"]["snapshot_at"],
                         **f["rider_profile"]["fields"])
    dp = C.driver_profile(f["driver_profile"]["party_id"], f["driver_profile"]["snapshot_at"],
                          **f["driver_profile"]["fields"])
    adm = f["admissibility"]

    def blk(key):
        a = adm[key]
        notes = texts["adm:" + key]
        if a["status"] == "COMPLETE":
            out = C.adm_complete(notes, assessed)
        elif a["status"] == "MISSING":
            out = C.adm_missing(notes, assessed)
        else:
            dets = [C.issue_detail(x["code"], x["severity"], texts["det:{0}:{1}".format(key, i)])
                    for i, x in enumerate(a.get("issue_details") or [])] or None
            out = C.adm_impaired(a["issues"], notes, assessed, gps_gap_grade=a["gps_gap_grade"], issue_details=dets)
        same(out["weight_multiplier"], a["weight_multiplier"], "{0} {1} weight".format(n, key))
        same(out["issues"], a["issues"], "{0} {1} issues".format(n, key))
        return out

    ev = [C.artifact(n, "TRIP_RECORD", trip, blk("TRIP_RECORD"), source=src["TRIP_RECORD"], generated_at=gen),
          C.artifact(n, "GPS_TRACE", gps, blk("GPS_TRACE"), source=src["GPS_TRACE"], generated_at=gen),
          C.artifact(n, "CHAT_LOG", chat, blk("CHAT_LOG"), source=src["CHAT_LOG"], generated_at=gen),
          C.artifact(n, "FARE_BREAKDOWN", fare, blk("FARE_BREAKDOWN"), source=src["FARE_BREAKDOWN"],
                     generated_at=gen),
          C.artifact(n, "RIDER_PROFILE", rp, blk("RIDER_PROFILE"), source=src["RIDER_PROFILE"], generated_at=gen),
          C.artifact(n, "DRIVER_PROFILE", dp, blk("DRIVER_PROFILE"), source=src["DRIVER_PROFILE"], generated_at=gen)]
    for a in f["traffic_advisories"]:
        key = "TRAFFIC_ADVISORY-{0:02d}".format(a["seq"])
        if a["missing"]:
            ev.append(C.artifact(n, "TRAFFIC_ADVISORY", None, blk(key), source=src["TRAFFIC_ADVISORY"],
                                 generated_at=gen, seq=a["seq"]))
        else:
            p = a["payload"]
            ev.append(C.artifact(n, "TRAFFIC_ADVISORY",
                                 C.advisory(p["advisory_id"], p["type"], p["road"], p["segment"], p["frm"], p["to"],
                                            p["valid_from"], p["valid_to"], p["issued_at"], p["source_ref"],
                                            p["shortest_lawful_alternative_km"]),
                                 blk(key), source=a["source"], generated_at=gen, seq=a["seq"]))
    d = f["dispute"]
    cs = d["counterparty_statement"]
    contested = contested_amount(e, fare, pp)
    case = C.make_case(n, C.NS, ev, filed_at=d["filed_at"], filed_by=d["filed_by"], channel=d["channel"],
                       amount_contested_sgd=contested, claim_text=texts["claim"],
                       counterparty_statement=C.counterparty(texts["cp"], cs["submitted_by"], cs["submitted_at"])
                       if cs else None,
                       safety_flag=d.get("safety_flag"), complaint_flag=d.get("complaint_flag"))
    return case


def written(case):
    """The case as written to disk (the generator's own serialisation, read back)."""
    return json.loads(C.dumps_case(case))


# ---------------------------------------------------------------------------
# measurement of the written case
# ---------------------------------------------------------------------------
def art(cw, evidence_type, seq=None):
    eid = C.ev_id(cw["case_no"], evidence_type, seq)
    for a in cw["evidence"]:
        if a["evidence_id"] == eid:
            return a
    raise Mismatch("no artifact {0}".format(eid))


def pl(cw, evidence_type, seq=None):
    return art(cw, evidence_type, seq)["payload"]


def window_summary(points, pin, t_from, t_to):
    sel = G.select(points, t_from, t_to)
    ws = C.window_stats(points, t_from, t_to)
    ds = [G.d_m(p, pin) for p in sel]
    accs = [p["accuracy_m"] for p in sel if p["accuracy_m"] is not None]
    return {"fixes": len(sel), "max_interval_s": ws["max_gap_s"], "lead_s": ws["lead_s"], "tail_s": ws["tail_s"],
            "dist_to_pin_m_min": round(min(ds), 1) if ds else None,
            "dist_to_pin_m_max": round(max(ds), 1) if ds else None,
            "accuracy_m_min": min(accs) if accs else None, "accuracy_m_max": max(accs) if accs else None,
            "speed_kph_max": max((p["speed_kph"] for p in sel), default=None),
            "fixes_with_null_accuracy": sum(1 for p in sel if p["accuracy_m"] is None)}


# Cases whose window statistics are taken from the first qualifying fix rather than the arrival marker (4065: the
# car was inside the hub radius 20 s before the tap).
WINDOW_FROM_FIRST_QUALIFYING = (4065,)


def measure(cw):
    """Every measured figure of the written case (keys as in the blueprint's gps_trace.measurements, plus more)."""
    n = cw["case_no"]
    trip, gps = pl(cw, "TRIP_RECORD"), pl(cw, "GPS_TRACE")
    pts, rt = gps["points"], gps["rider_track"]
    pin = (trip["pickup"]["lat"], trip["pickup"]["lng"])
    zone = trip["pickup_zone_class"]
    rad, pres = RADIUS[zone], PRESENCE[zone]
    arrival = trip["arrived_at"]
    term = trip["cancelled_at"] or trip["started_at"]
    w0, w1 = arrival or trip["accepted_at"], term
    if n in WINDOW_FROM_FIRST_QUALIFYING:
        w0 = G.first_qualifying(pts, pin, RADIUS[zone], t_to=term)["ts"]
    m = {"radius_m": rad, "presence_radius_m": pres, "zone": zone, "pin": pin, "arrival": arrival, "term": term}
    m["n_fixes"] = len(pts)
    m["trace_km"] = gps["trace_distance_km"]
    same(C.trace_distance(pts), m["trace_km"], "{0} trace_distance_km as written".format(n))
    m["first_fix"], m["last_fix"] = pts[0]["ts"], pts[-1]["ts"]
    m["median_s"] = C.sample_interval(pts)
    m["max_gap"] = C.max_gap(pts)
    accs = [p["accuracy_m"] for p in pts if p["accuracy_m"] is not None]
    m["acc_min"] = min(accs) if accs else None
    m["acc_max"] = max(accs) if accs else None
    m["max_implied_kph"] = round(C.max_implied_kph(pts), 1)
    m["max_jump_m"] = round(C.max_jump_m(pts), 1)
    m["window_from"], m["window_to"] = w0, w1
    m.update({"w_" + k: v for k, v in window_summary(pts, pin, w0, w1).items()})
    if arrival:
        p, dt = C.nearest_fix(pts, arrival)
        m["arr_fix_ts"], m["arr_dt"], m["arr_d"], m["arr_v"] = p["ts"], dt, round(G.d_m(p, pin), 1), p["speed_kph"]
        m["arr_acc"] = p["accuracy_m"]
    fq = G.first_qualifying(pts, pin, rad, t_to=term)
    m["fq_ts"] = fq["ts"] if fq else None
    if fq is not None:
        m["fq_d"], m["fq_v"], m["fq_acc"] = round(G.d_m(fq, pin), 1), fq["speed_kph"], fq["accuracy_m"]
        sel = G.select(pts, fq["ts"], term)
        m["dwell_fq_s"] = int(C.diff_s(fq["ts"], term))
        m["dwell_all_in_radius"] = all(G.qualifies(p, pin, rad) for p in sel)
        m["dwell_fixes"] = len(sel)
        iv = [C.diff_s(sel[i - 1]["ts"], sel[i]["ts"]) for i in range(1, len(sel))]
        m["dwell_max_interval_s"] = max(iv) if iv else None
        m["dwell_tail_s"] = int(C.diff_s(sel[-1]["ts"], term)) if sel else None
        dw = window_summary(pts, pin, fq["ts"], term)
        m["dw_dmin"], m["dw_dmax"] = dw["dist_to_pin_m_min"], dw["dist_to_pin_m_max"]
        m["dw_acc_min"], m["dw_acc_max"], m["dw_fixes"] = dw["accuracy_m_min"], dw["accuracy_m_max"], dw["fixes"]
        pfq = G.prev_fix(pts, fq["ts"])
        if pfq is not None:
            m["pre_fq_ts"], m["pre_fq_d"] = pfq["ts"], round(G.d_m(pfq, pin), 1)
    if arrival:
        m["dwell_tap_s"] = int(C.diff_s(arrival, term))
        tapfix = G.fix_at(pts, arrival)
        pre = G.prev_fix(pts, arrival)
        if pre is not None:
            m["pre_tap_ts"], m["pre_tap_d"], m["pre_tap_v"] = pre["ts"], round(G.d_m(pre, pin), 1), pre["speed_kph"]
            if tapfix is not None:
                m["fd_into_tap_kph"] = round(G.fd_kph(pre, tapfix), 1)
            pre2 = G.prev_fix(pts, pre["ts"])
            if pre2 is not None:
                m["fd_into_pre_kph"] = round(G.fd_kph(pre2, pre), 1)
    m["in_radius_intervals"] = [list(x) for x in G.in_radius_runs(pts, pin, rad, w0, term)]
    sel15 = G.select(pts, G.iso(G.sec(term) - LOOKBACK_S), term)
    m["min_d_15min_before_termination"] = round(min(G.d_m(p, pin) for p in sel15), 1) if sel15 else None
    m["qualifying_in_radius_15min"] = sum(1 for p in sel15 if G.qualifies(p, pin, rad))
    m["r_n"] = len(rt)
    if rt:
        rp = G.rider_presence(rt, pin, pres, w0, w1)
        m["r_fixes_in_window"], m["r_filtered_over_25m"] = rp["n"], len(rp["filtered"])
        m["r_qualifying"], m["r_qualifying_within_presence_radius"] = rp["qualifying"], rp["within"]
        m["r_qualifying_dist_m"], m["r_filtered_accuracy_m"] = rp["dist"], rp["filtered"]
        m["r_first"], m["r_last"] = rt[0]["ts"], rt[-1]["ts"]
        m["r_all_dist"] = [round(G.d_m(p, pin), 1) for p in rt]
        m["r_acc_all"] = [p["accuracy_m"] for p in rt]
    # largest interval and the fix after it
    iv = C.intervals(pts)
    i_big = max(range(len(iv)), key=lambda i: iv[i])
    m["gap_from"], m["gap_to"], m["gap_s"] = pts[i_big]["ts"], pts[i_big + 1]["ts"], iv[i_big]
    m["post_gap_d"] = round(G.d_m(pts[i_big + 1], pin), 1)
    m["post_gap_v"] = pts[i_big + 1]["speed_kph"]
    m["intervals"] = [int(x) for x in iv]
    m["first_after_accept_s"] = int(C.diff_s(trip["accepted_at"], pts[0]["ts"]))
    m["last_after_term_s"] = int(C.diff_s(term, pts[-1]["ts"]))
    win = G.select(pts, arrival or trip["accepted_at"], term)
    m["win_fixes_detail"] = [[hms(p["ts"]), round(G.d_m(p, pin), 1), p["speed_kph"], p["accuracy_m"]] for p in win]
    EXTRA.get(n, lambda cw_, m_: None)(cw, m)
    return m


def _x4054(cw, m):
    pts, pin = pl(cw, "GPS_TRACE")["points"], m["pin"]
    trip = pl(cw, "TRIP_RECORD")
    dd = [(p["ts"], round(G.d_m(p, pin), 1)) for p in pts]
    peak = max(dd, key=lambda x: x[1])
    after = [x for x in dd if G.sec(x[0]) >= G.sec(peak[0])]
    grace_end = C.add_s(trip["accepted_at"], trip["platform_policy"]["grace_after_match_sec"])

    def d_at(t):
        return [x[1] for x in dd if x[0] == t][0]
    m.update({"d_accept": d_at(trip["accepted_at"]), "peak_ts": peak[0], "peak_d": peak[1],
              "d_grace_end": d_at(grace_end), "d_cancel": d_at(trip["cancelled_at"]),
              "monotone_after_peak": all(after[i][1] < after[i - 1][1] for i in range(1, len(after))),
              "grace_end": grace_end})


def _x4056(cw, m):
    pts = pl(cw, "GPS_TRACE")["points"]
    trip = pl(cw, "TRIP_RECORD")
    stat = G.select(pts, trip["arrived_at"], trip["cancelled_at"])
    m["stat_n"] = len(stat)
    m["stat_all_venue"] = all(p.get("venue_id") == trip["pickup"]["venue_id"] for p in stat)
    m["stat_speed0"] = all(p["speed_kph"] == 0 for p in stat)
    m["stat_dwell_s"] = int(C.diff_s(stat[0]["ts"], trip["cancelled_at"]))
    m["stat_dmin"] = round(min(G.d_m(p, m["pin"]) for p in stat), 1)
    m["stat_dmax"] = round(max(G.d_m(p, m["pin"]) for p in stat), 1)


def _x4059(cw, m):
    pts, pin = pl(cw, "GPS_TRACE")["points"], m["pin"]
    trip = pl(cw, "TRIP_RECORD")
    cxl = trip["cancelled_at"]
    iv = G.in_radius_runs(pts, pin, m["radius_m"], m["fq_ts"], cxl)
    m["in_radius_runs_from_fq"] = [list(x) for x in iv]
    m["i1"] = int(C.diff_s(iv[0][0], iv[0][1]))
    m["i2"] = int(C.diff_s(iv[1][0], cxl))
    loop = G.select(pts, iv[0][1], iv[1][0])
    m["loop_max_d"] = round(max(G.d_m(p, pin) for p in loop), 1)
    m["i1_generous"] = int(C.diff_s(G.prev_fix(pts, iv[0][0])["ts"], G.select(pts, C.add_s(iv[0][1], 1))[0]["ts"]))
    m["i2_generous"] = int(C.diff_s(G.prev_fix(pts, iv[1][0])["ts"], cxl))
    adv = pl(cw, "TRAFFIC_ADVISORY", 1)
    a, b = G.pt(adv["geometry"]["from"]), G.pt(adv["geometry"]["to"])
    off, frac = G.cross_track(pin, a, b)
    m["advisory_pin_offset_m"], m["advisory_pin_fraction"] = round(off, 1), round(frac, 3)


def _x4061(cw, m):
    pts, pin = pl(cw, "GPS_TRACE")["points"], m["pin"]
    trip = pl(cw, "TRIP_RECORD")
    before = G.prev_fix(pts, trip["arrived_at"])
    m["approach_1302"] = [round(G.d_m(before, pin), 1), before["speed_kph"]]
    m["approach_ts"] = before["ts"]
    m["after_term"] = [round(G.d_m(pts[-1], pin), 1), pts[-1]["speed_kph"]]
    m["w_gps"] = art(cw, "GPS_TRACE")["admissibility"]["weight_multiplier"]


JUMP_FLOOR_M = 80      # 4062: consecutive stationary readings this far apart count as drift jumps


def _x4062(cw, m):
    pts, pin = pl(cw, "GPS_TRACE")["points"], m["pin"]
    trip = pl(cw, "TRIP_RECORD")
    win = G.select(pts, trip["arrived_at"], trip["cancelled_at"])
    jumps = [round(C.hav_m(win[i - 1], win[i]), 1) for i in range(1, len(win))]
    near = [p for p in win if G.d_m(p, pin) <= m["radius_m"]]
    far = [p for p in win if G.d_m(p, pin) > m["radius_m"]]
    m.update({"win_n": len(win), "win_near": len(near), "win_far": len(far),
              "far_min": round(min(G.d_m(p, pin) for p in far), 1),
              "far_max": round(max(G.d_m(p, pin) for p in far), 1),
              "near_max": round(max(G.d_m(p, pin) for p in near), 1),
              "jumps_ge_80": sum(1 for j in jumps if j >= JUMP_FLOOR_M), "jump_max": max(jumps),
              "jump_pairs": len(jumps), "jumps_ge_80_min": min(j for j in jumps if j >= JUMP_FLOOR_M),
              "longest_near_run": C.longest_run_within(win, pin, m["radius_m"], ACC_FILTER)[0],
              "acc_win": [min(p["accuracy_m"] for p in win), max(p["accuracy_m"] for p in win)],
              "longest_near_run_trace": C.longest_run_within(pts, pin, m["radius_m"], ACC_FILTER)[0]})


def _x4063(cw, m):
    pts = pl(cw, "GPS_TRACE")["points"]
    trip = pl(cw, "TRIP_RECORD")
    fare = pl(cw, "FARE_BREAKDOWN")
    trip_km = C.trace_distance(trip_fixes(pts, trip))
    m.update({"trip_km": trip_km, "billed_km": str(C.D(str(round(trip_km, 2)))), "fare_total": money(fare["total_charged"]),
              "dist_fare": money(fare["distance_fare"]), "optimal_km": str(C.D(str(trip["optimal_distance_km"]))),
              "actual_km": str(C.D(str(trip["actual_distance_km"]))), "dev_pct": trip["deviation_pct"]})


EXTRA = {4054: _x4054, 4056: _x4056, 4059: _x4059, 4061: _x4061, 4062: _x4062, 4063: _x4063}


def check_measurements(e, m):
    """Every figure the blueprint records in gps_trace.measurements equals the one measured on the written case."""
    want = e["facts"]["gps_trace"]["measurements"]
    for k, v in want.items():
        need(k in m, "{0}: measurement {1} not computed".format(e["case_no"], k))
        same(jrt(m[k]), v, "{0} measurement {1}".format(e["case_no"], k))


# ---------------------------------------------------------------------------
# values quoted in the texts
# ---------------------------------------------------------------------------
# 4052: the approach is on Hougang Ave 8 from this fix until the slowing leg into the drop-off point.
AVE8_FROM_4052 = "19:29:30"


class Values:
    """Ordered (name, text) pairs; the first name holding a text is the one templates use."""

    def __init__(self):
        self.items = []
        self.map = {}

    def add(self, name, val):
        if val is None:
            return
        need(name not in self.map, "duplicate value name {0}".format(name))
        self.items.append((name, val))
        self.map[name] = val

    def num(self, name, x):
        """A measured number as the texts print it: floats with their decimal (10.0), ints bare."""
        if x is None or isinstance(x, bool):
            return
        if isinstance(x, float):
            self.add(name, repr(x))
        else:
            self.add(name, str(x))

    def t(self, name, ts_):
        if ts_:
            self.add(name, hms(ts_))


_LIST_ELEMENT = re.compile(r"^m_\w+?_\d+(_\d+)?$")


def _rank(name):
    """Specificity rank of a value name (lower first)."""
    if name.startswith("k_"):
        return 0
    if name.startswith(("t_", "fee_", "contested", "total", "refund", "fare_", "waiting_fee", "free_wait", "grace",
                        "threshold", "billed", "per_", "trip_", "surge_mult")):
        return 1
    if name in ("m_first_after_accept_s", "m_last_after_term_s") or _LIST_ELEMENT.match(name):
        return 6
    if name.startswith(("m_peak", "m_d_", "m_fq_", "m_pre_", "m_arr_", "m_gap", "m_post_gap", "m_dwell", "m_stat",
                        "m_i1", "m_i2", "m_loop", "m_win_", "m_far", "m_near", "m_jump", "m_longest", "m_trip",
                        "m_approach", "m_after")):
        return 1.8
    if name.startswith("m_"):
        return 2
    if name.startswith(("n_events", "chat_count", "rpp")):
        return 4
    if name.startswith("ev") and name.endswith("_at"):
        return 5
    if name in ("radius", "presence", "acc_filter", "ceiling", "comp_rate", "floor", "reply_s", "false_d", "false_v",
                "skew_s", "gap_policy", "min_win_fixes", "farm_n", "farm_rate", "rider_abuse", "leash", "pair_n",
                "lookback_min", "default_free_wait", "eta_slack", "goodwill_pct"):
        return 4
    if name.startswith(("msg", "chat_", "reply_", "call", "rp_", "dp_", "w_", "wf_", "wprod_", "adv")):
        return 3
    return 3.5


def gap_grade(adm):
    """The GPS_GAP grade whose integrity product gives the written weight (the file carries the weight, not the grade)."""
    hits = [g for g in C.GPS_GAP_GRADES if C.weight_for(adm["issues"], g) == adm["weight_multiplier"]]
    need(len(hits) >= 1, "no GPS_GAP grade reproduces the weight")
    return hits[0]


def _flt(x):
    return isinstance(x, float)


def values(cw, m, K, design=None):
    """Every figure a text of this case may quote, computed from the written case (cw), its measurements (m) and
    the key figures (K, from decide())."""
    n = cw["case_no"]
    V = Values()
    trip, gps = pl(cw, "TRIP_RECORD"), pl(cw, "GPS_TRACE")
    chat, fare = pl(cw, "CHAT_LOG"), pl(cw, "FARE_BREAKDOWN")
    rp, dp = pl(cw, "RIDER_PROFILE"), pl(cw, "DRIVER_PROFILE")
    pp = trip["platform_policy"]
    pts, rt = gps["points"], gps["rider_track"]
    pin = m["pin"]

    # key figures first (money and ratios the rationale states)
    for k, v in K.items():
        if isinstance(v, Decimal):
            V.add("k_" + k, money(v))
        elif isinstance(v, str) and len(v) == 25 and v[10] == "T":
            V.t("k_" + k, v)
        elif isinstance(v, str):
            V.add("k_" + k, v)
        else:
            V.num("k_" + k, v)

    # trip record
    for k in ("requested_at", "accepted_at", "arrived_at", "started_at", "ended_at", "cancelled_at", "scheduled_at"):
        V.t("t_" + k[:-3], trip[k])
    V.num("free_wait", pp["free_wait_sec"])
    V.num("grace", pp["grace_after_match_sec"])
    V.num("threshold", pp["no_show_threshold_sec"])
    V.add("fee_net", money(pp["cancellation_fee_sgd"]))
    if pp["rider_gross_cancellation_fee_sgd"] is not None:
        V.add("fee_gross", money(pp["rider_gross_cancellation_fee_sgd"]))
    if pp["waiting_fee_sgd"] is not None:
        V.add("waiting_fee", money(pp["waiting_fee_sgd"]))
    V.add("contested", money(cw["dispute"]["amount_contested_sgd"]))
    V.add("fee_line", money(fare["cancellation_fee"]))
    V.add("total", money(fare["total_charged"]))
    V.add("refund", money(fare["refund_issued_sgd"]))
    for k in ("base_fare", "distance_fare", "time_fare", "platform_fee", "waiting_time_fee"):
        if fare[k]:
            V.add("fare_" + k, money(fare[k]))
    if fare["distance_charged_km"] is not None:
        V.add("billed_km", "{0:.2f}".format(fare["distance_charged_km"]))
        V.add("billed_min", fnum(fare["time_charged_min"]))
        V.add("per_km", money(fare["per_km_rate_sgd"]))
        V.add("per_min", money(fare["per_min_rate_sgd"]))
        V.add("surge_mult", str(float(fare["surge_multiplier"])))
    for k in ("optimal_distance_km", "actual_distance_km", "deviation_pct"):
        V.num("trip_" + k, trip[k])
    for i, c in enumerate(trip["in_app_calls"], 1):
        V.t("call{0}_at".format(i), c["initiated_at"])
        V.num("call{0}_dur".format(i), c["duration_sec"])
    V.num("n_events", len(trip["events"]))
    V.num("chat_count", trip["chat_message_count"])
    V.num("rpp", trip["registered_pickup_points"])
    for i, ev in enumerate(trip["events"]):
        V.t("ev{0}_at".format(i), ev["at"])
        if "ev_" + ev["event_type"] not in V.map:
            V.t("ev_" + ev["event_type"], ev["at"])

    # measurements (scalars, then list elements)
    skip = ("radius_m", "presence_radius_m", "zone", "pin", "arrival", "term")
    for k, v in m.items():
        if k in skip:
            continue
        if isinstance(v, str) and len(v) == 25 and v[10] == "T":
            V.t("m_" + k, v)
        elif isinstance(v, str):
            V.add("m_" + k, v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            V.num("m_" + k, v)
    for k, v in m.items():
        if isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, list):
                    for j, y in enumerate(x):
                        if isinstance(y, str) and len(y) == 25 and y[10] == "T":
                            V.t("m_{0}_{1}_{2}".format(k, i, j), y)
                        elif isinstance(y, str):
                            V.add("m_{0}_{1}_{2}".format(k, i, j), y)
                        else:
                            V.num("m_{0}_{1}_{2}".format(k, i, j), y)
                elif isinstance(x, str) and len(x) == 25 and x[10] == "T":
                    V.t("m_{0}_{1}".format(k, i), x)
                else:
                    V.num("m_{0}_{1}".format(k, i), x)
    for k in ("r_qualifying_dist_m", "r_all_dist", "r_acc_all"):
        if m.get(k):
            V.num("m_{0}_min".format(k), min(m[k]))
            V.num("m_{0}_max".format(k), max(m[k]))
    if rt:
        V.num("r_from_arrival_dmin", round(min(G.d_m(p, pin) for p in G.select(rt, m["arrival"] or trip["accepted_at"])), 1))
        V.num("r_from_arrival_dmax", round(max(G.d_m(p, pin) for p in G.select(rt, m["arrival"] or trip["accepted_at"])), 1))
        qual = [p for p in rt if p["accuracy_m"] <= ACC_FILTER]
        bad = [p for p in rt if p["accuracy_m"] > ACC_FILTER]
        V.num("r_bad_n", len(bad))
        if m.get("r_qualifying"):
            V.num("r_outside_n", m["r_qualifying"] - m["r_qualifying_within_presence_radius"])
            inside = [d for d in m["r_qualifying_dist_m"] if d <= m["presence_radius_m"]]
            if inside:
                V.num("r_within_dmin", min(inside))
                V.num("r_within_dmax", max(inside))
        V.num("r_qual_all_n", len(qual))
        for i, p in enumerate(qual):
            V.t("r_qual{0}_ts".format(i), p["ts"])
            V.num("r_qual{0}_acc".format(i), p["accuracy_m"])
            V.num("r_qual{0}_d".format(i), round(G.d_m(p, pin), 1))
        if bad:
            V.t("r_bad_last_ts", bad[-1]["ts"])
    # fixes named by time in a note (arrival window, approach, departure)
    win = G.select(pts, m["window_from"], m["window_to"])
    if win:
        V.num("win_speed_max", max(p["speed_kph"] for p in win))
        V.t("win_first", win[0]["ts"])
        V.t("win_last", win[-1]["ts"])
    if m.get("fq_ts"):
        fixes_fq = G.select(pts, m["fq_ts"], m["term"])
        V.num("fq_to_term_fixes", len(fixes_fq))
        nxt = G.select(pts, C.add_s(m["fq_ts"], 1))[0]
        V.t("fq_next_ts", nxt["ts"])
        V.num("fq_next_d", round(G.d_m(nxt, pin), 1))
    if m.get("arrival") and G.fix_at(pts, m["arrival"]) is not None:
        nxt = G.select(pts, C.add_s(m["arrival"], 1))[0]
        V.t("tap_next_ts", nxt["ts"])
        V.num("tap_next_d", round(G.d_m(nxt, pin), 1))
    # chat
    if chat:
        ms = chat["messages"]
        V.num("chat_held", len(ms))
        for x in ms:
            k = int(x["msg_id"][-3:])
            V.t("msg{0}_sent".format(k), x["sent_at"])
            V.t("msg{0}_deliv".format(k), x["delivered_at"])
            V.t("msg{0}_read".format(k), x["read_at"])
        iv = [(ms[i - 1], ms[i], int(C.diff_s(ms[i - 1]["sent_at"], ms[i]["sent_at"]))) for i in range(1, len(ms))]
        if iv:
            big = max(iv, key=lambda x: x[2])
            V.num("chat_big_s", big[2])
            V.t("chat_big_from", big[0]["sent_at"])
            V.t("chat_big_to", big[1]["sent_at"])
            marker = trip["arrived_at"]
            for a, b, s in iv:
                if marker and C.parse_ts(a["sent_at"]) < C.parse_ts(marker) < C.parse_ts(b["sent_at"]):
                    V.num("chat_span_s", s)
                    V.t("chat_span_from", a["sent_at"])
                    V.t("chat_span_to", b["sent_at"])
        for i, x in enumerate(ms):
            if x["sender"] == "RIDER":
                later = [y for y in ms[i + 1:] if y["sender"] == "DRIVER"]
                if later:
                    V.num("reply_after_{0}".format(int(x["msg_id"][-3:])),
                          int(C.diff_s(x["sent_at"], later[0]["sent_at"])))
    # profiles
    for k, v in rp.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            V.num("rp_" + k, v)
    for k, v in dp.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            V.num("dp_" + k, v)
    # admissibility weights and their factors
    wtab = C.integrity_weights()
    for a in cw["evidence"]:
        tag = a["evidence_id"].split("-")[1] + ("-" + a["evidence_id"].split("-")[3]
                                               if a["evidence_type"] == "TRAFFIC_ADVISORY" else "")
        V.num("w_" + tag, a["admissibility"]["weight_multiplier"])
        prod = Decimal(1)
        grade = gap_grade(a["admissibility"]) if "GPS_GAP" in a["admissibility"]["issues"] else None
        for code in a["admissibility"]["issues"]:
            key = "GPS_GAP_" + grade if code == "GPS_GAP" else code
            V.num("wf_{0}_{1}".format(tag, code), wtab[key])
            prod *= C.D(wtab[key])
        if len(a["admissibility"]["issues"]) > 1:
            V.add("wprod_" + tag, str(prod.normalize()))
    # advisories
    for a in cw["evidence"]:
        if a["evidence_type"] == "TRAFFIC_ADVISORY" and a["payload"]:
            p = a["payload"]
            seq = a["evidence_id"][-2:]
            V.add("adv{0}_from".format(seq), p["valid_from"][11:16])
            V.add("adv{0}_to".format(seq), p["valid_to"][11:16])
            V.add("adv{0}_issued".format(seq), p["issued_at"][11:16])
            ln = C.hav_m(p["geometry"]["from"], p["geometry"]["to"])
            V.num("adv{0}_len10".format(seq), int(round(ln / 10.0)) * 10)
    if n == 4052:
        sel = [p for p in pts if G.sec(C.ts(trip["requested_at"][:10], AVE8_FROM_4052)) <= G.sec(p["ts"]) <
               G.sec(C.add_s(trip["arrived_at"], -20))]
        V.t("ave8_from", sel[0]["ts"])
        V.t("ave8_to", sel[-1]["ts"])
        V.num("ave8_vmin", min(p["speed_kph"] for p in sel))
        V.num("ave8_vmax", max(p["speed_kph"] for p in sel))
    # dispute
    V.t("filed", cw["dispute"]["filed_at"])
    # figures named by the narrative
    V.num("cadence", int(m["median_s"]))
    if m.get("fq_ts") and m.get("arrival"):
        V.num("fq_lead_s", int(C.diff_s(m["fq_ts"], m["arrival"])))
    V.num("eta_min", eta_min(trip))
    if n == 4061:
        # the platform's own geofence measurement at the arrival event: the distance of the hold point
        V.num("platform_geofence_m", int(round(C.hav_m(pin, G.pt(design["hold_point"])))))
    V.num("acc_ceil", int(-(-Decimal(str(m["acc_max"])) // 1)) if m["acc_max"] is not None else None)
    if n == 4059:
        loop = [p for p in G.select(pts, m["in_radius_intervals"][0][1], m["in_radius_intervals"][1][0])
                if G.d_m(p, pin) > m["radius_m"]]
        V.t("loop_first", loop[0]["ts"])
        V.t("loop_last", loop[-1]["ts"])
        # The generous bracket of each NS-06 run: from the last outside fix before it to the first outside fix after
        # it or the termination, whichever comes first (r1 second reading: run 2's next outside fix, 18:26:30, falls
        # after the termination because two in-radius fixes follow it; bracketing to it would give 190 s).
        cxl = trip["cancelled_at"]
        runs = m["in_radius_runs_from_fq"]
        g1_from, g2_from = G.prev_fix(pts, runs[0][0]), G.prev_fix(pts, runs[1][0])
        g1_to = G.select(pts, C.add_s(runs[0][1], 1))[0]
        after = G.select(pts, C.add_s(cxl, 1))
        post_in = []
        for p in after:
            if not G.qualifies(p, pin, m["radius_m"]):
                break
            post_in.append(p)
        next_out = after[len(post_in)]
        need(G.sec(g1_to["ts"]) < G.sec(cxl) and not G.qualifies(g1_to, pin, m["radius_m"]), "4059: run 1 bracket")
        need(not G.qualifies(g1_from, pin, m["radius_m"]) and not G.qualifies(g2_from, pin, m["radius_m"]),
             "4059: brackets open on outside fixes")
        need(int(C.diff_s(g1_from["ts"], g1_to["ts"])) == m["i1_generous"] and
             int(C.diff_s(g2_from["ts"], cxl)) == m["i2_generous"], "4059: bracket figures")
        uncapped = m["i1_generous"] + int(C.diff_s(g2_from["ts"], next_out["ts"]))
        need(len(post_in) == 2 and uncapped >= trip["platform_policy"]["free_wait_sec"],
             "4059: the uncapped bracket to the next outside fix is the reading the rationale must not state")
        V.t("gen1_from", g1_from["ts"])
        V.t("gen1_to", g1_to["ts"])
        V.t("gen2_from", g2_from["ts"])
        V.t("post_in0", post_in[0]["ts"])
        V.t("post_in1", post_in[1]["ts"])
    if n == 4062:
        # the approach fixes from the point where the canyon drift begins (the design's approach-drift start)
        t0 = C.ts(trip["requested_at"][:10], G.CANYON_APPROACH_FROM)
        appr = G.select(pts, t0, C.add_s(m["arrival"], -1))
        V.t("canyon_from", t0)
        V.num("canyon_acc_min_r0", int(round(min(p["accuracy_m"] for p in appr))))
        V.num("canyon_acc_max_r0", int(round(max(p["accuracy_m"] for p in appr))))
        V.num("jump_floor_m", JUMP_FLOOR_M)
        V.num("jump_max_r10", int(round(m["jump_max"] / 10.0)) * 10)
    if n == 4063:
        V.add("claimed_arrival_dot", "{0}.{1}".format(int(CLAIMED_ARRIVAL_4063[:2]), CLAIMED_ARRIVAL_4063[3:5]))
        V.add("claimed_arrival_hm", CLAIMED_ARRIVAL_4063[:5])
    # policy figures
    V.num("radius", m["radius_m"])
    V.num("presence", m["presence_radius_m"])
    V.num("acc_filter", ACC_FILTER)
    V.num("ceiling", CEILING_M)
    V.add("comp_rate", "{0:.2f}".format(COMP_RATE))
    V.add("floor", "{0:.2f}".format(FLOOR))
    V.num("reply_s", REPLY_S)
    V.num("false_d", FALSE_D_M)
    V.num("false_v", FALSE_V_KPH)
    V.num("skew_s", SKEW_S)
    V.num("gap_policy", GAP_POLICY_S)
    V.num("min_win_fixes", MIN_WIN_FIXES)
    V.num("farm_n", FARM_N)
    V.add("farm_rate", str(FARM_RATE))
    V.num("rider_abuse", RIDER_ABUSE_N)
    V.num("leash", LEASH_M)
    V.num("pair_n", PAIR_N)
    V.num("lookback_min", LOOKBACK_S // 60)
    V.num("default_free_wait", DEFAULTS["free_wait_sec"])
    V.num("eta_slack", ETA_SLACK_S)
    V.num("goodwill_pct", int(GOODWILL_RATE * 100))
    # order by how specific a name is, so that a figure is named by its most specific holder
    real_gap = m["gap_s"] > 2 * m["median_s"]
    drop = ("m_w_fixes_with_null_accuracy", "m_w_lead_s", "m_w_tail_s", "m_arr_dt")
    if not real_gap:
        drop += ("m_gap_from", "m_gap_to", "m_gap_s", "m_post_gap_d", "m_post_gap_v")
    V.items = [(k, v) for k, v in V.items if k not in drop]
    V.map = dict(V.items)
    V.num("m_arr_dt", int(m["arr_dt"]) if m.get("arr_dt") is not None else None)
    if real_gap:
        V.items = [(k, v) for k, v in V.items if k != "m_gap_s"]
        V.map = dict(V.items)
        V.num("m_gap_s", int(m["gap_s"]))
    V.items.sort(key=lambda kv: _rank(kv[0]))
    # lower-priority print forms: HH:MM, integral floats without .0, floats rounded to whole units
    base = list(V.items)
    for name, val in base:
        if len(val) == 8 and val[2] == ":" and val[5] == ":":
            V.add(name + "_hm", val[:5])
    for name, val in base:
        try:
            x = float(val)
        except ValueError:
            continue
        if "." in val and x == int(x) and not name.startswith(("fee", "k_", "contested", "total", "refund", "fare",
                                                                 "waiting", "per_", "comp_rate", "floor")):
            V.add(name + "_i", str(int(x)))
        if "." in val and x != int(x) and name.startswith("m_"):
            V.add(name + "_r0", str(int(Decimal(val).quantize(Decimal(1), rounding="ROUND_HALF_UP"))))
    return V


def fill(template, V):
    return template.format_map(V.map)


# ---------------------------------------------------------------------------
# decision (the answer key, from the written case)
# ---------------------------------------------------------------------------
# Content readings a program cannot make from figures; each is a reading of the chat text as written.
# LOCATING: RIDER messages whose content is locating or coordinating (POL-NS-04(a)).
LOCATING = {4051: (2, 3), 4055: (4,), 4056: (2, 4), 4058: (3,), 4059: (5,), 4062: (3, 5), 4064: (3,), 4065: (2, 5)}
# Messages in which a party names an entrance, block, tower, wing or bay (POL-NS-03(i)); 4056 has none.
SUBLOCATION_NAMED = {4056: ()}
# Chat requests by the driver that the rider cancel, and vehicle / driver mismatches (POL-NS-10(f)); none anywhere.
CANCEL_REQUEST = {4054: ()}
VEHICLE_MISMATCH = {4052: False, 4054: False}
# 4063: the rider's claim puts the driver's arrival at "about 8.06am".
CLAIMED_ARRIVAL_4063 = "08:06:00"


def eta_min(trip):
    """The first ETA shown to the rider, read from the driver_assigned event ('ETA <n> min')."""
    ev = [e for e in trip["events"] if e["event_type"] == "driver_assigned"][0]
    words = ev["detail"].split()
    i = words.index("ETA")
    need(words[i + 2].startswith("min"), "ETA format")
    return int(words[i + 1])


def event_at(trip, event_type):
    evs = [e for e in trip["events"] if e["event_type"] == event_type]
    return evs[0]["at"] if evs else None


def ns04(cw, m):
    """POL-NS-04 limbs: (a) locating rider messages in the window, (b) no reply within 120 s and no call before
    termination, (c) rider presence majority (None = undecidable)."""
    n = cw["case_no"]
    trip, chat = pl(cw, "TRIP_RECORD"), pl(cw, "CHAT_LOG")
    w0, w1 = m["window_from"], m["window_to"]
    ms = chat["messages"] if chat else []
    loc = [x for x in ms if int(x["msg_id"][-3:]) in LOCATING.get(n, ()) and x["sender"] == "RIDER" and
           G.sec(w0) <= G.sec(x["sent_at"]) <= G.sec(w1)]
    a = bool(loc)
    replied = any(any(y["sender"] == "DRIVER" and 0 <= C.diff_s(x["sent_at"], y["sent_at"]) <= REPLY_S for y in ms)
                  for x in loc)
    calls = [c for c in trip["in_app_calls"] if G.sec(c["initiated_at"]) <= G.sec(m["term"])]
    b = a and not replied and not calls
    if not m.get("r_qualifying"):
        c = None
    else:
        c = 2 * m["r_qualifying_within_presence_radius"] > m["r_qualifying"]
    return {"a": a, "b": b, "c": c, "replied": replied, "calls": len(calls), "loc": loc}


def ns07(cw):
    dp = pl(cw, "DRIVER_PROFILE")
    k, done = dp["no_show_terminations_30d"], dp["completed_trips_30d"]
    rate = Decimal(k) / Decimal(done)
    return {"trips": k >= FARM_N and rate > FARM_RATE, "n": k, "of": done, "rate": rate}


def payout(cw):
    fee = C.D(pl(cw, "TRIP_RECORD")["platform_policy"]["cancellation_fee_sgd"])
    p = C.q2(COMP_RATE * fee)
    need(C.is_mult005(p), "payout {0} is not a multiple of 0.05".format(p))
    return p


def ns08(cw, m):
    """POL-NS-08 limbs engaged on the written case: {'a','b','c','d'} subset."""
    trip, gps, chat, fare = pl(cw, "TRIP_RECORD"), pl(cw, "GPS_TRACE"), pl(cw, "CHAT_LOG"), pl(cw, "FARE_BREAKDOWN")
    pp = trip["platform_policy"]
    pts = gps["points"]
    out = set()
    if m.get("arrival") and m["arr_dt"] > SKEW_S:
        out.add("a")
    if abs(C.diff_s(trip["accepted_at"], pts[0]["ts"])) > SKEW_S + 0 and G.sec(pts[0]["ts"]) > G.sec(trip["accepted_at"]):
        out.add("a")
    if abs(C.diff_s(m["term"], pts[-1]["ts"])) > SKEW_S and G.sec(pts[-1]["ts"]) < G.sec(m["term"]):
        out.add("a")
    if m["w_max_interval_s"] is not None and m["w_max_interval_s"] > GAP_POLICY_S:
        out.add("b")
    if m["w_fixes"] < MIN_WIN_FIXES:
        out.add("b")
    if chat is not None:
        ks = [int(x["msg_id"][-3:]) for x in chat["messages"]]
        if ks != list(range(1, len(ks) + 1)) or len(ks) < trip["chat_message_count"]:
            out.add("c")
        ms = chat["messages"]
        for i in range(1, len(ms)):
            if trip["arrived_at"] and G.sec(ms[i - 1]["sent_at"]) < G.sec(trip["arrived_at"]) < G.sec(ms[i]["sent_at"]) \
                    and C.diff_s(ms[i - 1]["sent_at"], ms[i]["sent_at"]) > CHAT_GAP_S:
                out.add("c")
    line = C.D(fare["cancellation_fee"])
    if line != 0:
        ok = {C.D(pp["cancellation_fee_sgd"])}
        if pp["rider_gross_cancellation_fee_sgd"] is not None:
            ok.add(C.D(pp["rider_gross_cancellation_fee_sgd"]))
        if line not in ok:
            out.add("d")
    return out


def ns01_holds(m, free_wait, threshold=None):
    """POL-NS-01 (b) and (c) on the driver's trace: arrival by the marker and a continuous dwell from the first
    qualifying fix."""
    b = m.get("fq_ts") is not None and G.sec(m["fq_ts"]) <= G.sec(m["arrival"])
    c = bool(m.get("dwell_all_in_radius")) and m["dwell_fq_s"] >= free_wait and m["dwell_max_interval_s"] <= 2 * m["median_s"]
    if threshold:
        c = c and m["dwell_tap_s"] >= threshold
    return b and c


def decide(cw, m):
    """(K) the ruling, money, referrals and the figures the rationale states, decided on the written case."""
    n = cw["case_no"]
    trip, fare = pl(cw, "TRIP_RECORD"), pl(cw, "FARE_BREAKDOWN")
    pp = trip["platform_policy"]
    fw, thr = pp["free_wait_sec"], pp["no_show_threshold_sec"]
    contested = C.D(cw["dispute"]["amount_contested_sgd"])
    K = {"engaged": "".join(sorted(ns08(cw, m)))}
    term_code = trip["cancellation_reason_code"]
    after_accept = int(C.diff_s(trip["accepted_at"], m["term"]))
    K["after_accept"] = after_accept

    def comp(k_extra=None):
        f7 = ns07(cw)
        need(not f7["trips"], "{0}: anti-farming trips".format(n))
        p = payout(cw)
        K.update({"ruling": "DRIVER_COMPENSATION", "amount": p, "dc": p, "referrals": [], "payout": p,
                  "farm_n": f7["n"], "farm_of": f7["of"]})
        return K

    if n == 4051:
        need(term_code == "RIDER_NO_SHOW" and ns01_holds(m, fw), "4051: NS-01 should hold on the trace")
        l4 = ns04(cw, m)
        need(l4["a"] and l4["b"] and l4["c"] is True, "4051: NS-04 limbs")
        need(not K["engaged"], "4051: NS-08")
        K.update({"ruling": "FULL_REFUND", "amount": C.q2(fare["cancellation_fee"]), "dc": None, "referrals": []})
        need(K["amount"] == contested, "4051: refund = contested")
        K["last_driver_post"] = [x for x in pl(cw, "CHAT_LOG")["messages"] if x["sender"] == "DRIVER"][-1]["sent_at"]
        return K
    if n in (4052,):
        need(trip["status"] == "CANCELLED_BY_RIDER" and after_accept > pp["grace_after_match_sec"], "4052: grace")
        need(m["fq_ts"] and G.sec(m["fq_ts"]) <= G.sec(m["arrival"]) and m["dwell_all_in_radius"], "4052: arrival")
        need(m["dwell_fq_s"] > fw, "4052: NS-10(g) dwell")
        return comp()
    if n == 4053:
        need("b" in K["engaged"], "4053: NS-08(b)")
        need(m["gap_s"] > GAP_POLICY_S and G.sec(m["gap_from"]) < G.sec(m["term"]) < G.sec(m["gap_to"]), "4053: gap")
        K.update({"ruling": "ESCALATE", "amount": None, "dc": None, "referrals": [], "hypo_payout": payout(cw),
                  "observed_s": int(C.diff_s(m["fq_ts"], m["gap_from"])),
                  "unobserved_s": int(C.diff_s(m["gap_from"], m["term"])),
                  "observed_fixes": len(G.select(pl(cw, "GPS_TRACE")["points"], m["fq_ts"], m["gap_from"]))})
        need(K["observed_s"] < fw, "4053: observed span short of the free wait")
        return K
    if n == 4054:
        grace = pp["grace_after_match_sec"]
        need(trip["status"] == "CANCELLED_BY_RIDER" and after_accept > grace and trip["arrived_at"] is None, "4054")
        en_route = event_at(trip, "driver_en_route")
        need(G.sec(en_route) <= G.sec(trip["accepted_at"]) + grace, "4054: moving within the grace")
        need(m["monotone_after_peak"] and m["d_grace_end"] < m["d_accept"], "4054: closing in")
        eta_at = C.add_s(trip["accepted_at"], 60 * eta_min(trip))
        need(G.sec(trip["cancelled_at"]) < G.sec(eta_at) + ETA_SLACK_S, "4054: ETA exception not shown")
        need(not CANCEL_REQUEST[n] and not VEHICLE_MISMATCH[n], "4054: other exceptions")
        K.update({"ruling": "NO_ACTION", "amount": None, "dc": None, "referrals": [], "eta_at": hms(eta_at),
                  "eta_min": eta_min(trip), "away_s": int(C.diff_s(trip["accepted_at"], m["peak_ts"]))})
        return K
    if n == 4055:
        l4 = ns04(cw, m)
        need(l4["a"] and l4["b"] and l4["c"] is None, "4055: NS-04 (a)(b) hold, (c) undecidable")
        need(term_code == "RIDER_NO_SHOW" and ns01_holds(m, fw), "4055: NS-01")
        return comp()
    if n == 4056:
        need(m.get("fq_ts") is None and m["qualifying_in_radius_15min"] == 0, "4056: no arrival in radius")
        need(m["stat_dmin"] > m["radius_m"] and m["stat_dmax"] <= CEILING_M and m["stat_speed0"], "4056: NS-03 band")
        need(m["stat_dwell_s"] >= fw and m["stat_all_venue"], "4056: stationary dwell")
        l4 = ns04(cw, m)
        need(l4["replied"], "4056: rider messages answered")
        need(not SUBLOCATION_NAMED[n] and trip["registered_pickup_points"] >= 2, "4056: NS-03(ii)")
        g = C.q2(GOODWILL_RATE * C.D(pp["cancellation_fee_sgd"]))
        need(C.is_mult005(g), "goodwill multiple of 0.05")
        K.update({"ruling": "FULL_REFUND", "amount": C.q2(fare["cancellation_fee"]), "dc": g, "referrals": [],
                  "goodwill": g})
        need(K["amount"] == contested, "4056: refund = contested")
        return K
    if n == 4057:
        need(term_code == "RIDER_NO_SHOW" and ns01_holds(m, fw), "4057: NS-01")
        need(not ns04(cw, m)["a"], "4057: no rider message")
        return comp()
    if n == 4058:
        need(term_code == "RIDER_NO_SHOW" and ns01_holds(m, fw, thr), "4058: NS-01")
        need(not ns04(cw, m)["b"], "4058: NS-04 fails")
        f7 = ns07(cw)
        need(f7["trips"], "4058: anti-farming must trip")
        K.update({"ruling": "ESCALATE", "amount": None, "dc": None, "referrals": [], "farm_n": f7["n"],
                  "farm_of": f7["of"], "farm_rate": str(f7["rate"].quantize(Decimal("0.0001"))),
                  "withheld": payout(cw)})
        return K
    if n == 4059:
        need(m["i1"] + m["i2"] < fw and m["i1_generous"] + m["i2_generous"] < fw, "4059: dwell short")
        need(m["loop_max_d"] <= LEASH_M, "4059: leash")
        adv = art(cw, "TRAFFIC_ADVISORY", 1)
        p = adv["payload"]
        need(p["type"] == "KERB_RESTRICTION" and G.sec(p["valid_from"]) <= G.sec(m["fq_ts"]) and
             G.sec(m["term"]) <= G.sec(p["valid_to"]) and 0 <= m["advisory_pin_fraction"] <= 1 and
             m["advisory_pin_offset_m"] <= m["radius_m"], "4059: advisory covers the pickup and the wait")
        K.update({"ruling": "NO_ACTION", "amount": None, "dc": None, "referrals": [],
                  "sum_s": m["i1"] + m["i2"], "short_s": fw - m["i1"] - m["i2"],
                  "generous_s": m["i1_generous"] + m["i2_generous"],
                  "elapsed_min": m["dwell_tap_s"] // 60, "elapsed_sec": "{0:02d}".format(m["dwell_tap_s"] % 60)})
        need(cw["dispute"]["filed_by"] == "DRIVER" and fare["payment_status"] == "REFUNDED", "4059: party-relative")
        return K
    if n == 4060:
        need(trip["status"] == "CANCELLED_BY_RIDER" and after_accept <= pp["grace_after_match_sec"], "4060: grace")
        need(m["dwell_fq_s"] <= fw, "4060: NS-10(g) not reached")
        K.update({"ruling": "FULL_REFUND", "amount": C.q2(fare["cancellation_fee"]), "dc": None, "referrals": [],
                  "after_request": int(C.diff_s(trip["requested_at"], m["term"]))})
        need(K["amount"] == contested, "4060: refund = contested")
        return K
    if n == 4061:
        need(pp["arrival_marker"] == "GPS_AUTO", "4061: GPS_AUTO")
        started, expired = event_at(trip, "wait_timer_started"), event_at(trip, "wait_timer_expired")
        need(int(C.diff_s(started, expired)) == fw and G.sec(expired) < G.sec(m["term"]), "4061: timer")
        need(m["dwell_tap_s"] >= thr, "4061: threshold")
        win = G.select(pl(cw, "GPS_TRACE")["points"], m["arrival"], m["term"])
        need(all(G.d_m(p, m["pin"]) <= m["radius_m"] and p["speed_kph"] < FALSE_V_KPH for p in win),
             "4061: no contradiction in the export")
        need("b" in K["engaged"] and "a" not in K["engaged"], "4061: NS-08 limbs")
        need(not ns04(cw, m)["a"], "4061: no rider message")
        return comp()
    if n == 4062:
        w = art(cw, "GPS_TRACE")["admissibility"]["weight_multiplier"]
        need(w < FLOOR and not K["engaged"], "4062: cap below the floor, no NS-08 limb")
        need(m["win_near"] >= 10 and m["win_far"] >= 10 and m["far_max"] < CEILING_M, "4062: split readings")
        need(ns04(cw, m)["replied"], "4062: NS-04 fails")
        K.update({"ruling": "ESCALATE", "amount": None, "dc": None, "referrals": [], "hypo_payout": payout(cw)})
        return K
    if n == 4063:
        need(trip["status"] == "COMPLETED" and C.D(fare["cancellation_fee"]) == 0, "4063: completed, no fee")
        need(m["dwell_all_in_radius"] and m["dwell_fq_s"] > fw, "4063: NS-10(d) dwell")
        K.update({"ruling": "NO_ACTION", "amount": None, "dc": None, "referrals": [],
                  "claimed_wait_s": int(C.diff_s(C.ts(trip["arrived_at"][:10], CLAIMED_ARRIVAL_4063),
                                                 trip["started_at"]))})
        return K
    if n == 4064:
        tap = G.fix_at(pl(cw, "GPS_TRACE")["points"], m["arrival"])
        need(m["arr_d"] > FALSE_D_M and tap["speed_kph"] >= FALSE_V_KPH, "4064: false marker")
        need(m["dwell_all_in_radius"] and m["dwell_fq_s"] >= fw and term_code == "RIDER_NO_SHOW", "4064: NS-05(iii)")
        l4 = ns04(cw, m)
        need(l4["calls"] > 0 and l4["c"] is False, "4064: NS-04 fails")
        comp()
        K["referrals"] = ["POL-NS-05(iii): false-arrival event recorded against the driver"]
        K["rt_min_km"] = "{0:.1f}".format(min(m["r_all_dist"]) / 1000)
        K["rt_max_km"] = "{0:.2f}".format(max(m["r_all_dist"]) / 1000)
        return K
    if n == 4065:
        need(pp["source"] == "AUTHORED-V1", "4065: AUTHORED-V1")
        need(m["dwell_fq_s"] < fw and term_code == "RIDER_NO_SHOW", "4065: NS-06 shortfall")
        K.update({"ruling": "FULL_REFUND", "amount": C.q2(fare["cancellation_fee"]), "dc": None, "referrals": [],
                  "zone_fee": C.q2(C.D(FS["zone_class_fee_sgd"][trip["pickup_zone_class"]])),
                  "tier_fee": C.q2(C.D(FS["vehicle_tier_fee_sgd"][trip["vehicle_type"]]))})
        need(K["amount"] == contested, "4065: refund = contested")
        return K
    raise Mismatch("no decision for {0}".format(n))


def check_intent(e, K):
    it = e["intent"]
    n = e["case_no"]
    same(K["ruling"], it["expected_ruling"], "{0} ruling".format(n))
    same(None if K["amount"] is None else money(K["amount"]), it["amount_sgd"], "{0} amount".format(n))
    same(None if K["dc"] is None else money(K["dc"]), it["driver_compensation_sgd"], "{0} compensation".format(n))
    same(K["referrals"], it["referrals"], "{0} referrals".format(n))
    same(sorted(K["engaged"]), sorted(it["ns08_limbs_engaged"]), "{0} NS-08 limbs".format(n))


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def build_one(e):
    n = e["case_no"]
    want = expected_texts(e)
    # 1. the case with every payload figure computed; its texts are the (corrected) blueprint texts
    first = build_case(e, want)
    cw = written(first)
    m = measure(cw)
    check_measurements(e, m)
    # 2. the decision on the case as written
    K = decide(cw, m)
    check_intent(e, K)
    # 3. every text assembled from its template and the values measured on the written case
    V = values(cw, m, K, e["facts"]["gps_trace"]["design"])
    T = TX.TEMPLATES[n]
    same(sorted(T), sorted(want), "{0} text keys".format(n))
    texts = {k: fill(T[k], V) for k in T}
    for k in T:
        same(texts[k], want[k], "{0} text {1}".format(n, k))
    case = build_case(e, texts)
    need(C.dumps_case(case) == C.dumps_case(first), "{0}: assembled texts changed the case".format(n))
    it = e["intent"]
    key = C.key_record(n, K["ruling"], K["amount"], K["dc"], K["referrals"], it["governing_clauses"],
                       it["difficulty"], texts["rationale"])
    probs = C.validate_key(key, case)
    need(not probs, "{0}: key problems {1}".format(n, probs))
    return case, key


def build():
    return [build_one(BLUEPRINT[n]) for n in sorted(BLUEPRINT)]
