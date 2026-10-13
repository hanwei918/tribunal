"""ROUTE_DEVIATION cases 4001-4015, generated from build/blueprint_rd.json.

Every number written to a case file is computed here from the blueprint's parameters:
  - GPS fixes from each record's build_recipe (common.drive / dwell / concat / drop_between, one seeded rng);
    counts, first / last fix, gaps, trace_distance_km from the fixes;
  - trip_record started_at / ended_at (first / last fix), actual_distance_km, actual_duration_min, deviation_pct,
    chat_message_count, the ETA and figure-bearing event details;
  - fare lines from distance_charged_km / time_charged_min / the route_deviation.json rate card / surge
    (Decimal), tolls from the gantries, total_charged from the lines;
  - admissibility weights (product rule) and every measured figure quoted in admissibility notes.
Each computed value is asserted against the figure the blueprint states, so the files are exactly the blueprint.
The answer key is computed from the case AS WRITTEN (a JSON round trip of the built case): the deciding figures
come from the rounded trace_distance_km, the cent-rounded fare lines and the stored trip fields, and each rationale
is assembled from those values.
"""
import json
import os
from decimal import Decimal, ROUND_HALF_UP

import common as C

_BP_PATH = os.path.join(C.BUILD_DIR, "blueprint_rd.json")
with open(_BP_PATH, encoding="utf-8") as _f:
    BLUEPRINT = {rec["case_no"]: rec for rec in json.load(_f)}


class Mismatch(C.BuildError):
    pass


def need(cond, msg):
    if not cond:
        raise Mismatch(msg)


def same(got, want, what):
    need(got == want, "{0}: computed {1!r} but blueprint says {2!r}".format(what, got, want))
    return got


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------
def r1(x):
    """1 dp, ROUND_HALF_UP on the exact binary value of the float (the platform's convenience copies)."""
    return float(Decimal(float(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def fnum(x):
    """10.0 -> '10', 67.9 -> '67.9'."""
    x = float(x)
    return str(int(x)) if x == int(x) else repr(x)


def hms(t):
    return t[11:19]


def hm(t):
    return t[11:16]


def m1(x):
    """metres to 1 dp with thousands separator: 8489.6 -> '8,489.6'."""
    return "{0:,.1f}".format(x)


def km3(x):
    return "{0:.3f}".format(x)


def pct2(num, den):
    """percentage to 2 dp, Decimal half-up."""
    return (Decimal(num) / Decimal(den) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def dkm(x):
    """Decimal of a km figure as written (float -> repr)."""
    return C.D(x)


def km_text(d):
    """Decimal km -> 3 dp text."""
    return "{0:.3f}".format(d)


def money(x):
    return C.money_str(x)


# ---------------------------------------------------------------------------
# GPS
# ---------------------------------------------------------------------------
def build_points(n, rec):
    r = C.rng(n, "trace")
    acc = tuple(rec["accuracy_m"])
    pts, t, last = [], rec["t0"], None
    for st in rec["steps"]:
        if st["op"] == "drive":
            wps = [tuple(w) for w in st["waypoints"]]
            seg = C.drive(wps, t, st["speeds_kph"], rec["cadence_s"], rng=r, accuracy_m=acc,
                          speed_noise_kph=rec["speed_noise_kph"], jitter_m=rec["jitter_m"])
            last = wps[-1]
        elif st["op"] == "dwell":
            need(last is not None, "dwell before any drive")
            seg = C.dwell(last[0], last[1], t, st["seconds"], rec["cadence_s"], rng=r, accuracy_m=acc)
        else:
            raise Mismatch("unknown op {0}".format(st["op"]))
        pts = C.concat(pts, seg)
        t = pts[-1]["ts"]
    post = rec.get("post")
    if post:
        need(post["op"] == "drop_between", "unknown post op")
        pts = C.drop_between(pts, post["from"], post["to"])
    return pts


def gps_measure(pts, threshold_s):
    iv = C.intervals(pts)
    accs = [p["accuracy_m"] for p in pts if p["accuracy_m"] is not None]
    big = [(i, g) for i, g in enumerate(iv) if g > threshold_s]
    return {
        "count": len(pts), "first": pts[0]["ts"], "last": pts[-1]["ts"],
        "median": C.sample_interval(pts), "max_gap": C.max_gap(pts),
        "step_m": round(C.max_jump_m(pts), 1), "kph": round(C.max_implied_kph(pts), 1),
        "acc_lo": min(accs), "acc_hi": max(accs), "trace": C.trace_distance(pts),
        "big": big, "other_max": max([g for i, g in enumerate(iv) if g <= threshold_s] or [0]),
        "duration_s": C.diff_s(pts[0]["ts"], pts[-1]["ts"]),
    }


def gps_note(n, pts, m, cadence):
    s = "{0} fixes from {1} to {2}; cadence {3} s (median interval {4} s); ".format(
        m["count"], hms(m["first"]), hms(m["last"]), cadence, m["median"])
    if m["big"]:
        parts = []
        for i, g in m["big"]:
            parts.append("{0} s from {1} to {2}".format(fnum(g), hms(pts[i]["ts"]), hms(pts[i + 1]["ts"])))
        s += "intervals above {0} s: {1}; every other interval {2} s or less; ".format(
            2 * cadence, "; ".join(parts), fnum(m["other_max"]))
    else:
        s += "largest interval {0} s; ".format(fnum(m["max_gap"]))
    s += ("largest straight-line step between consecutive fixes {0} m; highest implied speed {1} km/h; every fix "
          "reports horizontal accuracy between {2} and {3} m; trace_distance_km {4} recomputed from the fixes "
          "(haversine, R 6371.0088 km); rider_track not supplied.").format(
        m["step_m"], m["kph"], m["acc_lo"], m["acc_hi"], km3(m["trace"]))
    return s


def gap_detail(pts, m):
    """(index, seconds, bounding fixes, straight-line metres, implied kph) of the single large interval."""
    need(len(m["big"]) == 1, "expected exactly one large interval")
    i, g = m["big"][0]
    a, b = pts[i], pts[i + 1]
    dist = C.hav_m(a, b)
    return {"i": i, "sec": g, "a": a, "b": b, "m": dist, "kph": dist / 1000.0 / (g / 3600.0)}


# ---------------------------------------------------------------------------
# fare
# ---------------------------------------------------------------------------
def fare_lines(F):
    """Fare lines computed from the blueprint's billing parameters (Decimal)."""
    f = F["fare_breakdown"]
    rates = C.rd_fare_constants()
    same(C.D(f["per_km_rate_sgd"]), rates["per_km"], "per_km_rate_sgd")
    same(C.D(f["per_min_rate_sgd"]), rates["per_min"], "per_min_rate_sgd")
    lines = C.metered_lines(C.D(f["distance_charged_km"]), f["time_charged_min"], C.D(f["surge_multiplier"]))
    for k in ("base_fare", "distance_fare", "time_fare", "surge_amount", "platform_fee"):
        same(lines[k], C.D(f[k]), "fare line " + k)
    return lines


def fare_arith(fare, F):
    """The 'Ledger lines reconcile' arithmetic text, from the written fare payload."""
    D = C.D
    base, dist, tim = D(fare["base_fare"]), D(fare["distance_fare"]), D(fare["time_fare"])
    kmc, mins = fare["distance_charged_km"], fare["time_charged_min"]
    erp, plat = D(fare["tolls_erp"]), D(fare["platform_fee"])
    total = D(fare["total_charged"])
    if D(fare["surge_amount"]) != 0:
        sub = base + dist + tim
        sm = D(fare["surge_multiplier"])
        gl = " + ".join(money(g["amount_sgd"]) for g in fare["erp_gantries"])
        return ("{0} + {1} x {2:.2f} (= {3}) + {4} x {5} (= {6}) = {7}; surge {7} x {8} = {9}; ERP {10} = {11}; "
                "platform {12}; total {7} + {9} + {11} + {12} = {13}").format(
            money(base), money(fare["per_km_rate_sgd"]), kmc, money(dist), money(fare["per_min_rate_sgd"]), mins,
            money(tim), money(sub), str(sm - 1), money(fare["surge_amount"]), gl, money(erp), money(plat),
            money(total))
    core = "{0} + {1} x {2:.2f} (= {3}) + {4} x {5} (= {6}) + 0 surge + {7} ERP + {8}".format(
        money(base), money(fare["per_km_rate_sgd"]), kmc, money(dist), money(fare["per_min_rate_sgd"]), mins,
        money(tim), "0" if erp == 0 else money(erp), money(plat))
    if D(fare["cancellation_fee"]) != 0:
        core += " + cancellation_fee {0}".format(money(fare["cancellation_fee"]))
    if D(fare["promo_discount"]) != 0:
        core += " - promo {0}".format(money(fare["promo_discount"]))
    core += " = {0}".format(money(total))
    if fare["fare_model"] == "UPFRONT_QUOTE":
        q = D(fare["quoted_fare_sgd"])
        if q == total and D(fare["distance_charged_km"]) == D(F["trip_record"]["optimal_distance_km"]):
            core = "quote lines: " + core + " = quoted_fare_sgd"
        else:
            core = "re-rated lines: " + core + "; quoted_fare_sgd {0}".format(money(q))
    if D(fare["refund_issued_sgd"]) != 0:
        core += "; refund_issued_sgd {0} to the rider before filing".format(money(fare["refund_issued_sgd"]))
    return core


def fare_note(fare, F):
    D = C.D
    s = "Ledger lines reconcile to the cent: {0}. fare_model {1}; surge_multiplier {2}; distance_charged_km {3:.2f}, " \
        "time_charged_min {4}; payment_status {5}, refund_issued_sgd {6}; ".format(
            fare_arith(fare, F), fare["fare_model"], fare["surge_multiplier"], fare["distance_charged_km"],
            fare["time_charged_min"], fare["payment_status"], money(fare["refund_issued_sgd"]))
    k = len(fare["erp_gantries"])
    s += "no ERP lines." if k == 0 else \
        "{0} ERP gantry line(s), each with gantry_id, name, coordinates and charged_at.".format(k)
    return s


# ---------------------------------------------------------------------------
# trip record
# ---------------------------------------------------------------------------
def trip_note(trip, n_events):
    s = ("Platform trip record; timestamps causally ordered (requested {0}, accepted {1}, arrived {2}, started {3}, "
         "ended {4}); started_at and ended_at equal the first and last gps_trace fixes to the second; status "
         "COMPLETED with cancelled_at, cancelled_by and cancellation_reason_code null; optimal_distance_km {5} and "
         "optimal_duration_min {6} stored on the record (optimal_route_source {7}, optimal_route_erp_sgd {8}); "
         "actual_distance_km {9} is the trace figure rounded to 1 dp; {10} events; platform_policy null (not a "
         "no-show record).").format(
        hms(trip["requested_at"]), hms(trip["accepted_at"]), hms(trip["arrived_at"]), hms(trip["started_at"]),
        hms(trip["ended_at"]), trip["optimal_distance_km"], trip["optimal_duration_min"],
        trip["optimal_route_source"], money(trip["optimal_route_erp_sgd"]), trip["actual_distance_km"], n_events)
    if trip["solo_optimal_distance_km"] is not None:
        s += " solo_optimal_distance_km {0} is also populated.".format(trip["solo_optimal_distance_km"])
    if trip["dropoff_amended_at"] is not None:
        rq = [e for e in trip["events"] if e["event_type"] == "route_requote_failed"]
        s += (" dropoff_amended_at {0} and original_dropoff ({1}) are set and dropoff is {2}, but "
              "amended_optimal_distance_km and amended_optimal_duration_min are null; event route_requote_failed at "
              "{3}.").format(hms(trip["dropoff_amended_at"]), short_label(trip["original_dropoff"]["label"]),
                             short_label(trip["dropoff"]["label"]), hms(rq[0]["at"]))
    return s


def short_label(label):
    return label.split(" (")[0]


def regen_event(e, ctx):
    """Rebuild the figure-bearing event details from computed values; assert they equal the blueprint text."""
    t, d = e["event_type"], e["detail"]
    if t == "route_planned":
        head, _, _ = d.partition(". ")
        if d.startswith("Solo route at booking"):
            out = "{0}. {1} km, {2} min.".format(head, ctx["solo_km"], ctx["solo_min"])
        elif ctx["fare_model"] == "UPFRONT_QUOTE":
            out = "{0}. {1} km, {2} min. Upfront fare {3}.".format(head, ctx["opt_km"], ctx["opt_min"], ctx["quote"])
        else:
            out = "{0}. {1} km, {2} min. ERP on route {3}.".format(head, ctx["opt_km"], ctx["opt_min"], ctx["erp"])
        return same(out, d, "route_planned detail")
    if t == "driver_assigned":
        head = d.split(" ETA ")[0]
        return same("{0} ETA {1} min.".format(head, ctx["eta"]), d, "driver_assigned detail")
    if t == "trip_completed":
        head = d.split(". ")[0]
        if ctx["fare_model"] == "UPFRONT_QUOTE" and ctx["quote"] == ctx["total"]:
            out = "{0}. Upfront fare {1} charged (quote basis {2} km, {3} min).".format(
                head, ctx["total"], ctx["bill_km"], ctx["bill_min"])
        elif ctx["fare_model"] == "UPFRONT_QUOTE":
            out = "{0}. Trip GPS trace: {1} km, {2} min.".format(head, ctx["bill_km"], ctx["bill_min"])
        elif "driver-app GPS trace" in d:
            out = "{0}. Metered fare from the driver-app GPS trace for this trip (the exported trace): {1} km, " \
                  "{2} min.".format(head, ctx["bill_km"], ctx["bill_min"])
        else:
            out = "{0}. Metered fare from trip GPS trace: {1} km, {2} min.".format(head, ctx["bill_km"],
                                                                                   ctx["bill_min"])
        return same(out, d, "trip_completed detail")
    if t == "booking_confirmed" and "Upfront fare" in d:
        head = d.split(". ")[0]
        return same("{0}. Upfront fare {1} quoted.".format(head, ctx["quote"]), d, "booking_confirmed detail")
    if t == "fare_rerated":
        out = "Upfront fare {0} replaced by metered fare {1} after route change ({2} km, {3} min).".format(
            ctx["quote"], ctx["total"], ctx["bill_km"], ctx["bill_min"])
        return same(out, d, "fare_rerated detail")
    if t == "pool_matched":
        head = d.split(" Matched itinerary route ")[0]
        return same("{0} Matched itinerary route {1} km, {2} min.".format(head, ctx["opt_km"], ctx["opt_min"]), d,
                    "pool_matched detail")
    if t == "pool_discount_applied":
        rid = d.split(" applied to ")[1]
        return same("Pool discount {0} applied to {1}".format(ctx["promo"], rid), d, "pool discount detail")
    return d


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------
def chat_note(n, chat, trip, extra=""):
    ms = chat["messages"]
    gaps = [C.diff_s(ms[i - 1]["sent_at"], ms[i]["sent_at"]) for i in range(1, len(ms))]
    hints = [m["msg_id"] for m in ms if m["waypoint_hint"] is not None]
    s = "{0} messages, ids {1} to {2} contiguous; first {3}, last {4}; trip_record.chat_message_count {5}; ".format(
        len(ms), ms[0]["msg_id"], ms[-1]["msg_id"], hms(ms[0]["sent_at"]), hms(ms[-1]["sent_at"]),
        trip["chat_message_count"])
    if hints:
        s += "waypoint_hint resolved by the platform at ingest on {0}; ".format(", ".join(hints))
    else:
        s += "no message carries a waypoint_hint; "
    s += "largest interval between messages {0} s.".format(fnum(max(gaps)))
    return s + extra


def chat_skew(chat, trip):
    """Constant offset (s) between SYSTEM chat messages and the trip_record events they mirror."""
    pairs = {"You are on a pool ride": "pool_matched", "Your driver has arrived": "driver_arrived",
             "Trip started": "trip_started", "Picking up your co-rider": "pool_pickup",
             "Your co-rider has been dropped off": "pool_dropoff", "Trip completed": "trip_completed"}
    ev = {e["event_type"]: e["at"] for e in trip["events"]}
    offs = []
    for m in chat["messages"]:
        if m["sender"] != "SYSTEM":
            continue
        for prefix, et in pairs.items():
            if m["text"].startswith(prefix):
                offs.append(C.diff_s(ev[et], m["sent_at"]))
    need(offs and len(set(offs)) == 1, "skew not constant: {0}".format(offs))
    return int(offs[0]), len(offs)


# ---------------------------------------------------------------------------
# admissibility notes that carry measured figures (all others are copied verbatim: they carry none)
# ---------------------------------------------------------------------------
def adm_notes_expected(n, F, built):
    """{evidence_id: (notes, issue_details or None)} computed from the built payloads."""
    trip, gps, chat, fare = built["trip"], built["gps"], built["chat"], built["fare"]
    pts, m = built["pts"], built["gm"]
    out = {}
    out[C.ev_id(n, "TRIP_RECORD")] = (trip_note(trip, len(trip["events"])),
                                      [C.issue_detail("PARTIAL_RECORD", "HIGH",
                                                      "amended_optimal_distance_km and amended_optimal_duration_min "
                                                      "null although dropoff_amended_at is set.")]
                                      if trip["dropoff_amended_at"] is not None else None)
    gnote = gps_note(n, pts, m, built["cadence"])
    gdet = None
    if m["big"]:
        g = gap_detail(pts, m)
        sec, a, b = fnum(g["sec"]), g["a"], g["b"]
        lead = C.diff_s(pts[0]["ts"], a["ts"])
        if lead <= 60:
            gnote += (" The {0} s interval begins {1} s after the first fix; its bounding fixes ({2}, {3}) and "
                      "({4}, {5}) are {6} m apart.").format(sec, fnum(lead), a["lat"], a["lng"], b["lat"], b["lng"],
                                                            m1(g["m"]))
            gdet = [C.issue_detail("GPS_GAP", "LOW", "{0} s without fixes {1}-{2} at the start of the trip; bounding "
                                   "fixes {3} m apart.".format(sec, hms(a["ts"]), hms(b["ts"]), m1(g["m"])))]
        else:
            gnote += (" The {0} s interval runs from the fix at {1} ({2}, {3}) to the fix at {4} ({5}, {6}); the two "
                      "fixes are {7} m apart in a straight line (implied {8} km/h) and trace_distance_km includes "
                      "that straight line.").format(sec, hms(a["ts"]), a["lat"], a["lng"], hms(b["ts"]), b["lat"],
                                                    b["lng"], m1(g["m"]), round(g["kph"], 1))
            gdet = [C.issue_detail("GPS_GAP", "HIGH", "{0} s without fixes {1}-{2} in mid-trip; bounding fixes {3} m "
                                   "apart.".format(sec, hms(a["ts"]), hms(b["ts"]), m1(g["m"])))]
    out[C.ev_id(n, "GPS_TRACE")] = (gnote, gdet)
    cid = C.ev_id(n, "CHAT_LOG")
    if chat is None:
        out[cid] = ("No chat log was retrievable for this trip; trip_record.chat_message_count is {0}. The identifier "
                    "is minted so that the absence can be cited.".format(trip["chat_message_count"]), None)
    else:
        extra, det = "", None
        lang = [mm for mm in chat["messages"] if mm["language"] != "en"]
        if lang:
            mm = lang[0]
            words = F["chat_ambiguous_words"]
            extra = (" {0} mixes Malay ('{1}', '{2}') with English and is tagged language {3}; its waypoint_hint is "
                     "{4} ({5}, {6}).").format(mm["msg_id"], words[0], words[1], mm["language"],
                                               mm["waypoint_hint"]["label"], mm["waypoint_hint"]["lat"],
                                               mm["waypoint_hint"]["lng"])
            det = [C.issue_detail("LANGUAGE_AMBIGUITY", "LOW", "{0} is mixed Malay and English ({1}, {2}).".format(
                mm["msg_id"], words[0], words[1]))]
        if F["admissibility"][cid]["issues"] == ["CLOCK_SKEW"]:
            sk, k = chat_skew(chat, trip)
            extra = (" The {0} SYSTEM messages that mirror trip_record events (matched, arrived, started, co-rider "
                     "pick-up, co-rider set-down, completed) are each stamped {1} s after the corresponding "
                     "trip_record event: a constant +{1} s offset between the chat server clock and the trip "
                     "record.").format(["zero", "one", "two", "three", "four", "five", "six"][k], sk)
            det = [C.issue_detail("CLOCK_SKEW", "MEDIUM", "Chat clock +{0} s against trip_record on {1} paired "
                                  "events.".format(sk, k))]
        out[cid] = (chat_note(n, chat, trip, extra), det)
    out[C.ev_id(n, "FARE_BREAKDOWN")] = (fare_note(fare, F), None)
    for et, prof in (("RIDER_PROFILE", built["rprof"]), ("DRIVER_PROFILE", built["dprof"])):
        eid = C.ev_id(n, et)
        if F["admissibility"][eid]["issues"] == ["STALE_SNAPSHOT"]:
            snap = C.parse_ts(prof["snapshot_at"]).date()
            trip_day = C.parse_ts(trip["started_at"]).date()
            gen_day = C.parse_ts(built["generated_at"]).date()
            dt, dg = (trip_day - snap).days, (gen_day - snap).days
            out[eid] = ("snapshot_at {0} is {1} days before the trip ({2}) and {3} days before this bundle was "
                        "generated; counters are as of the snapshot date; every field populated.".format(
                            prof["snapshot_at"], dt, trip_day.isoformat(), dg),
                        [C.issue_detail("STALE_SNAPSHOT", "LOW", "Rider profile snapshot {0} days older than the "
                                        "trip.".format(dt))])
        else:
            out[eid] = ("Snapshot taken {0}; every field populated, none null.".format(prof["snapshot_at"]), None)
    for a in F["traffic_advisories"]:
        p = a["payload"]
        if p is None:
            continue
        kind = {"CLOSURE": "closure", "ROADWORKS": "roadworks"}[p["type"]]
        vf, vt = p["valid_from"], p["valid_to"]
        vt_txt = vt[:16] if vt[:10] != vf[:10] or a["seq"] == 1 else hm(vt)
        note = "LTA {0} notice issued {1}; type {2}; validity {3} to {4}; geometry two points on the {5}; ".format(
            kind, p["issued_at"][:16], p["type"], vf[:16], vt_txt, a["geometry_label"])
        if a.get("all_fields_sentence"):
            note += "shortest_lawful_alternative_km stated as {0}; every payload field populated.".format(
                p["shortest_lawful_alternative_km"])
        else:
            note += "shortest_lawful_alternative_km {0} stated.".format(p["shortest_lawful_alternative_km"])
        out[a["evidence_id"]] = (note, None)
    return out


ADVISORY_TEXT = {
    # evidence id -> (geometry label quoted in the note, note ends with 'every payload field populated')
    "EV-ADVIS-04002-01": ("CTE city tunnel", True),
    "EV-ADVIS-04012-01": ("PIE", False),
    "EV-ADVIS-04012-02": ("TPE", False),
}

CHAT_AMBIGUOUS_WORDS = {4001: ("singgah", "kejap")}


# ---------------------------------------------------------------------------
# case assembly
# ---------------------------------------------------------------------------
def build_case(n):
    rec = BLUEPRINT[n]
    F = rec["facts"]
    F = dict(F)
    F["chat_ambiguous_words"] = CHAT_AMBIGUOUS_WORDS.get(n)
    meta = F["artifact_meta"]
    gen, at = meta["generated_at"], meta["assessed_at"]
    src = meta["sources"]
    adm_bp = F["admissibility"]

    # --- GPS
    g = F["gps_trace"]
    recipe = g["build_recipe"]
    pts = build_points(n, recipe)
    cadence = recipe["cadence_s"]
    gps = C.gps_trace(n, pts, expected_interval_sec=cadence)
    gm = gps_measure(pts, 2 * cadence)
    meas = g["measurements"]
    for k in ("trace_distance_km", "point_count", "first_fix_at", "last_fix_at", "max_gap_sec", "gaps",
              "sample_interval_sec"):
        same(gps[k], meas[k], "gps " + k)
    same(gm["step_m"], meas["largest_step_m"], "largest step")
    same(gm["kph"], meas["max_implied_kph"], "max implied kph")
    same(gm["duration_s"], meas["duration_s"], "duration")
    same([gm["acc_lo"], gm["acc_hi"]], meas["accuracy_m_range"], "accuracy range")
    same(min(C.intervals(pts)), meas["shortest_interval_s"], "shortest interval")
    same(g["source"], src["GPS_TRACE"], "gps source")

    # --- fare (computed lines)
    fb = F["fare_breakdown"]
    lines = fare_lines(F)
    gantries = [C.erp_gantry(x["gantry_id"], x["name"], x["lat"], x["lng"], x["charged_at"], C.D(x["amount_sgd"]))
                for x in fb["erp_gantries"]]
    fare = C.fare_breakdown(
        n, fare_model=fb["fare_model"], airport_surcharge=C.D(fb["airport_surcharge"]),
        cancellation_fee=C.D(fb["cancellation_fee"]), waiting_time_fee=C.D(fb["waiting_time_fee"]),
        promo_discount=C.D(fb["promo_discount"]), erp_gantries=gantries, payment_status=fb["payment_status"],
        refund_issued_sgd=C.D(fb["refund_issued_sgd"]), charged_at=fb["charged_at"],
        surge_multiplier=C.D(fb["surge_multiplier"]), rate_card_id=fb["rate_card_id"],
        quoted_fare_sgd=None if fb["quoted_fare_sgd"] is None else C.D(fb["quoted_fare_sgd"]),
        distance_charged_km=float(C.D(fb["distance_charged_km"])), time_charged_min=fb["time_charged_min"],
        per_km_rate_sgd=C.rd_fare_constants()["per_km"], per_min_rate_sgd=C.rd_fare_constants()["per_min"],
        currency=fb["currency"], **lines)
    same(C.D(fare["total_charged"]), C.D(fb["total_charged"]), "total_charged")
    same(C.D(fare["tolls_erp"]), C.D(fb["tolls_erp"]), "tolls_erp")
    same(fare["charged_at"], gps["last_fix_at"], "charged_at = last fix")
    if fb["fare_model"] == "METERED":
        # the meter bills the trace: distance_charged_km is the 2-dp copy, minutes the whole minutes
        same(C.D(fb["distance_charged_km"]), C.q2(C.D(repr(gps["trace_distance_km"]))), "billed km = trace (2 dp)")
        same(fb["time_charged_min"], int(round(gm["duration_s"] / 60.0)), "billed minutes")
    same(fare_arith(fare, F), fb["line_arithmetic"], "line arithmetic")

    # --- chat
    ch = F["chat_log"]
    if ch["status"] == "PRESENT":
        msgs = [C.msg(mm["sender"], mm["text"], mm["sent_at"], read_at=mm["read_at"],
                      delivered_at=mm["delivered_at"], channel=mm["channel"], language=mm["language"],
                      redacted=mm["redacted"], waypoint_hint=mm["waypoint_hint"]) for mm in ch["messages"]]
        chat = C.chat_log(n, msgs, truncated=ch["truncated"])
        same([mm["msg_id"] for mm in chat["messages"]], [mm["msg_id"] for mm in ch["messages"]], "msg ids")
        same(chat["message_count"], ch["message_count"], "message_count")
        same(chat["first_message_at"], ch["first_message_at"], "first message")
        same(chat["last_message_at"], ch["last_message_at"], "last message")
        n_msgs = chat["message_count"]
    else:
        chat = None
        n_msgs = F["trip_record"]["chat_message_count"]   # count the platform reports; the log itself is absent

    # --- trip record (computed fields)
    t = dict(F["trip_record"])
    bp_events = t.pop("events")
    act_km = r1(gps["trace_distance_km"])
    act_min = r1(gm["duration_s"] / 60.0)
    opt_d = C.D(repr(t["optimal_distance_km"]))
    dev = float(((C.D(repr(act_km)) - opt_d) / opt_d * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    same(act_km, t["actual_distance_km"], "actual_distance_km")
    same(act_min, t["actual_duration_min"], "actual_duration_min")
    same(dev, t["deviation_pct"], "deviation_pct")
    same(n_msgs, t["chat_message_count"], "chat_message_count")
    same(t["started_at"], gps["first_fix_at"], "started_at")
    same(t["ended_at"], gps["last_fix_at"], "ended_at")
    t.update(started_at=gps["first_fix_at"], ended_at=gps["last_fix_at"], actual_distance_km=act_km,
             actual_duration_min=act_min, deviation_pct=dev, chat_message_count=n_msgs)
    t["optimal_route_erp_sgd"] = C.D(t["optimal_route_erp_sgd"])
    solo = None
    for e in bp_events:
        if e["event_type"] == "route_planned" and e["detail"].startswith("Solo route"):
            solo = e["detail"].split(". ")[-2:]
    ctx = {"opt_km": t["optimal_distance_km"], "opt_min": t["optimal_duration_min"],
           "erp": money(t["optimal_route_erp_sgd"]), "fare_model": fare["fare_model"],
           "quote": None if fare["quoted_fare_sgd"] is None else money(fare["quoted_fare_sgd"]),
           "total": money(fare["total_charged"]), "bill_km": "{0:.2f}".format(fare["distance_charged_km"]),
           "bill_min": fare["time_charged_min"], "promo": money(fare["promo_discount"]),
           "eta": int(round(C.diff_s(t["accepted_at"], t["arrived_at"]) / 60.0)),
           "solo_km": t["solo_optimal_distance_km"], "solo_min": SOLO_MIN.get(n)}
    events = []
    for e in bp_events:
        detail = regen_event(e, ctx)
        if e["event_type"] in ("booking_confirmed", "route_planned", "driver_assigned", "driver_arrived",
                               "trip_started", "trip_completed"):
            want = {"booking_confirmed": t["requested_at"], "driver_assigned": t["accepted_at"],
                    "driver_arrived": t["arrived_at"], "trip_started": t["started_at"],
                    "trip_completed": t["ended_at"]}.get(e["event_type"])
            if want is not None:
                same(e["at"], want, "event time " + e["event_type"])
        events.append(C.event(e["event_type"], e["at"], detail, e["source"]))
    trip = C.trip_record(n, events=events, **t)

    # --- profiles
    rp = dict(F["rider_profile"]); rsnap = rp.pop("snapshot_at")
    dp = dict(F["driver_profile"]); dsnap = dp.pop("snapshot_at")
    rprof = C.rider_profile(F["parties"]["rider_id"], rsnap, **rp)
    dprof = C.driver_profile(F["parties"]["driver_id"], dsnap, **dp)
    same(trip["rider_id"], F["parties"]["rider_id"], "rider id")
    same(trip["driver_id"], F["parties"]["driver_id"], "driver id")

    # --- admissibility (weights by the product rule; figure-bearing notes regenerated)
    advs = []
    for a in F["traffic_advisories"]:
        a = dict(a)
        if a["payload"] is not None:
            a["geometry_label"], a["all_fields_sentence"] = ADVISORY_TEXT[a["evidence_id"]]
        advs.append(a)
    Fx = dict(F); Fx["traffic_advisories"] = advs
    built = {"trip": trip, "gps": gps, "chat": chat, "fare": fare, "pts": pts, "gm": gm, "cadence": cadence,
             "rprof": rprof, "dprof": dprof, "generated_at": gen}
    notes = adm_notes_expected(n, Fx, built)

    def adm(eid):
        a = adm_bp[eid]
        txt, det = notes.get(eid, (a["notes"], a.get("issue_details")))
        same(txt, a["notes"], "notes " + eid)
        same(det, a.get("issue_details"), "issue_details " + eid)
        if a["status"] == "COMPLETE":
            blk = C.adm_complete(txt, at)
        elif a["status"] == "MISSING":
            blk = C.adm_missing(txt, at)
        else:
            blk = C.adm_impaired(a["issues"], txt, at, gps_gap_grade=a.get("gps_gap_grade"), issue_details=det)
        same(blk["weight_multiplier"], a["weight_multiplier"], "weight " + eid)
        same(blk["issues"], a["issues"], "issues " + eid)
        same(blk["assessor_version"], meta["assessor_version"], "assessor version")
        return blk

    ev = [
        C.artifact(n, "TRIP_RECORD", trip, adm(C.ev_id(n, "TRIP_RECORD")), source=src["TRIP_RECORD"],
                   generated_at=gen),
        C.artifact(n, "GPS_TRACE", gps, adm(C.ev_id(n, "GPS_TRACE")), source=src["GPS_TRACE"], generated_at=gen),
        C.artifact(n, "CHAT_LOG", chat, adm(C.ev_id(n, "CHAT_LOG")), source=src["CHAT_LOG"], generated_at=gen),
        C.artifact(n, "FARE_BREAKDOWN", fare, adm(C.ev_id(n, "FARE_BREAKDOWN")), source=src["FARE_BREAKDOWN"],
                   generated_at=gen),
        C.artifact(n, "RIDER_PROFILE", rprof, adm(C.ev_id(n, "RIDER_PROFILE")), source=src["RIDER_PROFILE"],
                   generated_at=gen),
        C.artifact(n, "DRIVER_PROFILE", dprof, adm(C.ev_id(n, "DRIVER_PROFILE")), source=src["DRIVER_PROFILE"],
                   generated_at=gen),
    ]
    for a in advs:
        p = a["payload"]
        payload = None if p is None else C.advisory(
            p["advisory_id"], p["type"], p["road"], p["segment"], p["geometry"]["from"], p["geometry"]["to"],
            p["valid_from"], p["valid_to"], p["issued_at"], p["source_ref"], p["shortest_lawful_alternative_km"])
        blk = adm(a["evidence_id"])
        same(blk["notes"], a["admissibility"]["notes"], "advisory note copy")
        ev.append(C.artifact(n, "TRAFFIC_ADVISORY", payload, blk, source=a["source"], generated_at=gen,
                             seq=a["seq"]))

    # --- dispute
    d = F["dispute"]
    check_quoted_figures(n, d, fare, gps, trip)
    cs = d["counterparty_statement"]
    case = C.make_case(n, C.RD, ev, filed_at=d["filed_at"], filed_by=d["filed_by"], channel=d["channel"],
                       amount_contested_sgd=C.D(d["amount_contested_sgd"]), claim_text=d["claim_text"],
                       counterparty_statement=None if cs is None else C.counterparty(cs["text"], cs["submitted_by"],
                                                                                     cs["submitted_at"]),
                       safety_flag=d["safety_flag"], complaint_flag=d["complaint_flag"])
    same(case["dispute"]["evidence_ids"], F["ids"]["evidence_ids_in_order"], "evidence ids")
    same(case["dispute"]["dispute_id"], F["ids"]["dispute_id"], "dispute id")
    return case


SOLO_MIN = {4008: 17}   # the solo route's minutes appear only in the route_planned event text


def check_quoted_figures(n, d, fare, gps, trip):
    """Record figures quoted by the parties must be the record's own figures (computed above)."""
    D = C.D
    total = money(fare["total_charged"])
    contested = money(D(d["amount_contested_sgd"]))
    text = d["claim_text"]
    quoted = QUOTED.get(n, {})
    for key in quoted.get("claim", ()):
        val = {"total": total, "contested": contested,
               "contested_int": str(int(D(d["amount_contested_sgd"]))) if D(d["amount_contested_sgd"]) ==
               int(D(d["amount_contested_sgd"])) else None,
               "quote": None if fare["quoted_fare_sgd"] is None else money(fare["quoted_fare_sgd"]),
               "trace2": "{0:.2f}".format(gps["trace_distance_km"]),
               "refund": money(fare["refund_issued_sgd"]),
               "erp_line": str(int(D(fare["tolls_erp"]))) if fare["tolls_erp"] else None}[key]
        need(val is not None and val in text, "case {0}: claim does not quote {1} = {2}".format(n, key, val))


# figures each claim quotes from the record (checked against the computed values)
QUOTED = {
    4001: {"claim": ("total", "trace2")},
    4002: {"claim": ("total",)},
    4003: {"claim": ("total", "contested")},
    4004: {"claim": ("total", "quote", "contested")},
    4005: {"claim": ("total",)},
    4006: {"claim": ("total", "erp_line")},
    4007: {"claim": ("total",)},
    4008: {"claim": ()},
    4009: {"claim": ("total", "contested")},
    4010: {"claim": ("contested", "refund")},
    4011: {"claim": ("total",)},
    4012: {"claim": ("contested", "refund")},
    4013: {"claim": ("total",)},
    4014: {"claim": ("contested", "refund")},
    4015: {"claim": ("total",)},
}


def build():
    out = []
    for n in sorted(BLUEPRINT):
        case = build_case(n)
        key = build_key(n, case)
        out.append((case, key))
    return out


# ---------------------------------------------------------------------------
# keys (filled in below)
# ---------------------------------------------------------------------------
def build_key(n, case):
    import cases_rd_keys as K
    return K.key_for(n, case, BLUEPRINT[n]["intent"], BLUEPRINT[n]["facts"]["gps_trace"]["extra_measurements"])
