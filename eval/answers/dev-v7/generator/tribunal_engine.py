"""Shared engine for the Tribunal version-7 test-set generator.

Standard library only. Money is decimal.Decimal throughout and becomes a JSON number
only when a file is written. Randomness comes from random.Random seeded per case with
a fixed string, so the same specs always give byte-identical case files.

This module holds no case. Each set's cases live in that set's own specs module,
so one set's B zip never carries another set's cases.
The expected answer of every case is derived here, from the case's own facts, by the
version-7 rules written out in derive_rd() and derive_ns().
"""
import hashlib
import itertools
import json
import math
import os
import random
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

D = Decimal
SGT = timezone(timedelta(hours=8))
SEED = "tribunal-v7-20261013"

# ---------------------------------------------------------------- version-7 numbers
TOLERANCE_KM = D("1.0")                 # route_deviation.thresholds.tolerance_km
AI_MAX_DEV_KM = D("2.0")                # ai_ruling_max_deviation_km
AI_MAX_DEV_APPLIED = False              # ai_ruling_max_deviation_applied
FREE_WAIT_SEC = 300                     # no_show.thresholds.free_wait_sec
NS_FEE = D("5.00")                      # no_show_fee_sgd
GOODWILL = D("5.00")                    # goodwill_credit_sgd
DRIVER_LATE_SEC = 300                   # driver_late_after_scheduled_sec
REPEAT_COUNT = 3                        # repeat_no_show_count
RADIUS_M = {"STANDARD": 50, "LARGE_VENUE": 120, "TRANSPORT_HUB": 150, "AIRPORT": 150}
AI_FINAL_BELOW = D("10.00")
HUMAN_ABOVE = D("50.00")
CONF_ROUTE = D("0.80")
CONF_FRAUD = D("0.95")
WEIGHTS = {  # integrity.weights (identical in route_deviation.json and no_show.json)
    "MISSING_ARTIFACT": 0.0, "CROSS_SOURCE_CONFLICT": 0.4, "TRUNCATED_LOG": 0.6, "PARTIAL_RECORD": 0.75,
    "STALE_SNAPSHOT": 0.75, "CONTENT_REDACTED": 0.8, "LOW_SAMPLE_RATE": 0.8, "LANGUAGE_AMBIGUITY": 0.85,
    "UNREAD_MESSAGE": 0.85, "SCHEMA_VERSION_MISMATCH": 0.9, "GPS_GAP_SHORT_OR_OUTSIDE_WINDOW": 0.85,
    "GPS_GAP_LONG_INSIDE_WINDOW": 0.6, "GPS_GAP_STRADDLING_CANCELLATION": 0.6, "LOW_COVERAGE": 0.65,
    "GPS_DRIFT": 0.5, "IMPLAUSIBLE_SPEED": 0.6, "ADVISORY_UNCORROBORATED": 0.5, "UNVERIFIED_SOURCE": 0.5,
    "CLOCK_SKEW": 0.5}
SECTION = {  # the v2.1 section(s) each clause carries (from each clause's "sources")
    "POL-GEN-01": "2.5 and 6.3", "POL-GEN-02": "6.3", "POL-GEN-03": "1.3, 2.2-2.4 and 6",
    "POL-GEN-21": "5.1-5.3 and 6.2", "POL-GEN-22": "6.1-6.3", "POL-GEN-23": "7", "POL-GEN-24": "3 and 4",
    "POL-GEN-25": "closing line", "POL-GEN-26": "6.3",
    "POL-RD-21": "1.1, 1.2 and 1.4", "POL-RD-22": "1.3 and 1.4", "POL-RD-23": "1.4", "POL-RD-24": "1.3",
    "POL-RD-25": "6.2",
    "POL-NS-21": "2.1", "POL-NS-22": "2.2", "POL-NS-23": "2.3", "POL-NS-24": "2.4", "POL-NS-25": "2.5",
    "POL-NS-26": "6.2 and 6.3"}
FORBIDDEN = ("ground_truth", "expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd",
             "expected_referrals", "governing_clauses", "difficulty", "rationale", "canary", "sealed")

RATE_CARDS = {
    "RYDE_X": dict(id="RC-SG-RYDEX-2026Q3", base=D("2.80"), per_km=D("0.72"), per_min=D("0.18"), platform=D("0.90")),
    "RYDE_XL": dict(id="RC-SG-RYDEXL-2026Q3", base=D("3.80"), per_km=D("0.92"), per_min=D("0.24"), platform=D("0.90")),
    "RYDE_PREMIUM": dict(id="RC-SG-PREM-2026Q3", base=D("4.50"), per_km=D("1.05"), per_min=D("0.30"), platform=D("0.90")),
}
CARS = {"RYDE_X": ["Toyota Corolla Altis", "Toyota Prius", "Hyundai Ioniq 5", "BYD Atto 3", "Kia Niro EV", "Honda Vezel"],
        "RYDE_XL": ["Toyota Noah", "Toyota Sienta", "Honda Freed", "Kia Carnival"],
        "RYDE_PREMIUM": ["Toyota Camry Hybrid", "Mercedes-Benz E 200", "Lexus ES 300h"]}


def m2(x):
    return D(str(x)).quantize(D("0.01"), ROUND_HALF_UP)


def money(x):
    return float(m2(x))


def T(date, hms):
    return datetime.strptime("{0} {1}".format(date, hms), "%Y-%m-%d %H:%M:%S").replace(tzinfo=SGT)


def iso(dt):
    return dt.isoformat()


def hms(dt):
    return dt.strftime("%H:%M:%S")


def secs(a, b):
    return int((b - a).total_seconds())


def mmss(s):
    s = int(s)
    return "{0} min {1:02d} s".format(s // 60, s % 60)


# ---------------------------------------------------------------- geometry (same metric as the checker)
R_EARTH = 6371.0088


def hav(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(h))


def metres(a, b):
    return hav(a, b) * 1000.0


def path_cum(path):
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + hav(path[i - 1], path[i]))
    return cum


def along(path, cum, d):
    if d >= cum[-1]:
        return path[-1][0], path[-1][1], len(path) - 1
    for i in range(1, len(path)):
        if d <= cum[i]:
            seg = cum[i] - cum[i - 1]
            f = 0.0 if seg == 0 else (d - cum[i - 1]) / seg
            return (path[i - 1][0] + f * (path[i][0] - path[i - 1][0]),
                    path[i - 1][1] + f * (path[i][1] - path[i - 1][1]), i - 1)
    return path[-1][0], path[-1][1], len(path) - 1


def offset(pt, north_m, east_m):
    lat = pt[0] + north_m / 111195.0
    lng = pt[1] + east_m / (111195.0 * math.cos(math.radians(pt[0])))
    return (lat, lng)


def bulge(J, R, extra_km, side):
    """A point B such that |JB| + |BR| - |JR| is about extra_km, on one side of JR."""
    c = hav(J, R)
    h = math.sqrt(max(((extra_km + c) / 2) ** 2 - (c / 2) ** 2, 0.0))
    mid = ((J[0] + R[0]) / 2, (J[1] + R[1]) / 2)
    dy = (R[0] - J[0]) * 111.195
    dx = (R[1] - J[1]) * 111.195 * math.cos(math.radians(mid[0]))
    norm = math.hypot(dx, dy) or 1.0
    px, py = -dy / norm * side, dx / norm * side
    return offset(mid, py * h * 1000.0, px * h * 1000.0)


def sg_plate(rng):
    prefix = rng.choice(["SLA", "SLB", "SLC", "SLD", "SLE", "SLF", "SLG", "SLH", "SLJ", "SLK", "SLM", "SLP", "SLR", "SLS", "SLT"])
    num = rng.randint(100, 9999)
    vals = [ord(prefix[1]) - 64, ord(prefix[2]) - 64] + [int(c) for c in "{0:04d}".format(num)]
    s = sum(a * b for a, b in zip(vals, [9, 4, 5, 4, 3, 2])) % 19
    return "{0} {1} {2}".format(prefix, num, "AZYXUTSRPMLKJHGEDCB"[s])


def trace_stats(points, step):
    tl = [datetime.fromisoformat(p["ts"]) for p in points]
    gaps, ints = [], []
    for i in range(1, len(tl)):
        g = (tl[i] - tl[i - 1]).total_seconds()
        ints.append(g)
        if g > 120:
            gaps.append({"from": iso(tl[i - 1]), "to": iso(tl[i]), "gap_sec": float(g)})
    dist = sum(hav((points[i - 1]["lat"], points[i - 1]["lng"]), (points[i]["lat"], points[i]["lng"])) for i in range(1, len(points)))
    span = (tl[-1] - tl[0]).total_seconds()
    expected = int(span // step) + 1
    ints_sorted = sorted(ints)
    return {
        "point_count": len(points),
        "first_fix_at": iso(tl[0]), "last_fix_at": iso(tl[-1]),
        "sample_interval_sec": float(ints_sorted[len(ints_sorted) // 2]) if ints else None,
        "expected_interval_sec": float(step),
        "gaps": gaps,
        "max_gap_sec": float(max(ints)) if ints else 0.0,
        "coverage_pct": round(100.0 * len(points) / expected, 1),
        "trace_distance_km": round(dist, 3),
    }


# ---------------------------------------------------------------- admissibility
def admissibility(status, assessed_at, notes, issues=None, grades=None, details=None):
    issues = list(issues or [])
    if status == "COMPLETE":
        w = 1.0
    elif status == "MISSING":
        w = 0.0
        issues = ["MISSING_ARTIFACT"]
    else:
        w = 1.0
        for c in issues:
            w *= WEIGHTS[(grades or {}).get(c, c)]
        w = round(w, 4)
    a = {"status": status, "issues": issues, "weight_multiplier": w, "notes": notes,
         "assessed_at": iso(assessed_at), "assessor_version": "prepass-1.0.0"}
    if details:
        a["issue_details"] = [{"code": c, "severity": s, "detail": t} for c, s, t in details]
    return a


def artifact(eid, etype, trip_id, source, generated_at, adm, payload, schema="1.2.0"):
    return {"evidence_id": eid, "evidence_type": etype, "admissibility": adm, "payload": payload,
            "schema_version": schema, "source": source, "trip_id": trip_id, "generated_at": iso(generated_at)}


class Case:
    def __init__(self, setname, n):
        self.n = n
        self.rng = random.Random("{0}-{1}-{2}".format(SEED, setname, n))
        self.trip_id = "TRP-{0:05d}".format(n)
        self.dispute_id = "DSP-{0:05d}".format(n)

    def eid(self, tok, k=None):
        s = "EV-{0}-{1:05d}".format(tok, self.n)
        return s if k is None else "{0}-{1:02d}".format(s, k)


def impaired(spec, key, default_status="COMPLETE"):
    imp = (spec.get("impair") or {}).get(key)
    return imp


def build_adm(spec, key, assessed_at, complete_notes):
    imp = impaired(spec, key)
    if not imp:
        return admissibility("COMPLETE", assessed_at, complete_notes), 1.0
    a = admissibility("IMPAIRED", assessed_at, imp["notes"], imp["issues"], imp.get("grades"), imp.get("details"))
    return a, a["weight_multiplier"]


def profile(case, role, party_id, snapshot, rng, over, vehicle=None):
    if role == "RIDER":
        filed = rng.randint(0, 5)
        p = {"party_id": party_id, "party_role": "RIDER", "snapshot_at": iso(snapshot),
             "account_age_days": rng.randint(60, 2400), "lifetime_trips": rng.randint(20, 900),
             "rating": round(rng.uniform(4.3, 4.95), 2), "prior_disputes_filed": filed,
             "prior_disputes_upheld": rng.randint(0, filed), "prior_no_show_flags": rng.randint(0, 1),
             "cancellation_rate": round(rng.uniform(0.01, 0.09), 3), "no_show_disputes_30d": rng.randint(0, 1),
             "deviation_claims_60d": rng.randint(0, 1), "deviation_claims_60d_substantiated": 0,
             "disputes_with_counterparty_90d": 0}
    else:
        filed = rng.randint(0, 4)
        p = {"party_id": party_id, "party_role": "DRIVER", "snapshot_at": iso(snapshot),
             "account_age_days": rng.randint(200, 3000), "lifetime_trips": rng.randint(800, 14000),
             "rating": round(rng.uniform(4.6, 4.97), 2), "prior_disputes_filed": filed,
             "prior_disputes_upheld": rng.randint(0, filed), "prior_no_show_flags": rng.randint(0, 2),
             "vehicle_type": vehicle, "cancellation_rate": round(rng.uniform(0.01, 0.06), 3),
             "prior_deviation_flags": rng.randint(0, 2), "acceptance_rate": round(rng.uniform(0.82, 0.98), 2),
             "active_region": rng.choice(["NORTH", "NORTH_EAST", "EAST", "WEST", "CENTRAL"]),
             "deviation_flags_90d": rng.randint(0, 1), "completed_trips_90d": rng.randint(250, 900),
             "no_show_terminations_30d": rng.randint(0, 3), "completed_trips_30d": rng.randint(80, 320),
             "disputes_with_counterparty_90d": 0}
        if p["prior_disputes_filed"] < p["prior_disputes_upheld"]:
            p["prior_disputes_upheld"] = p["prior_disputes_filed"]
    if rng.random() < 0.5:
        p["fraud_flags"] = 0
    for k, v in (over or {}).items():
        if v is None:
            p.pop(k, None)
        else:
            p[k] = v
    if "prior_disputes_upheld" in p and p["prior_disputes_upheld"] > p["prior_disputes_filed"]:
        p["prior_disputes_upheld"] = p["prior_disputes_filed"]
    return p


def chat_messages(case, entries):
    """entries: list of (dt, sender, text, extra) sorted by dt; returns message dicts."""
    rng = case.rng
    out = []
    for k, (t, sender, text, ex) in enumerate(sorted(entries, key=lambda e: e[0]), 1):
        ex = ex or {}
        delivered = ex.get("delivered_at", t + timedelta(seconds=rng.randint(1, 3)))
        read = ex.get("read_at", "auto")
        if read == "auto":
            read = None if sender in ("SYSTEM",) else t + timedelta(seconds=rng.randint(6, 50))
        out.append({"msg_id": "MSG-{0:05d}-{1:03d}".format(case.n, k), "sender": sender, "text": text,
                    "sent_at": iso(t), "read_at": iso(read) if read else None,
                    "delivered_at": iso(delivered) if delivered else None,
                    "channel": ex.get("channel", "IN_APP"), "language": ex.get("language", "en"),
                    "redacted": ex.get("redacted", False), "waypoint_hint": ex.get("waypoint_hint")})
    return out


def check_text(where, s):
    for ch in s:
        if ord(ch) > 126 and ch not in "\n":
            raise ValueError("{0}: non-ASCII character {1!r}".format(where, ch))
    low = s.lower()
    for w in FORBIDDEN:
        if w in low:
            raise ValueError("{0}: forbidden word {1!r}".format(where, w))


def dispute_block(case, spec, cat, filed_at, contested, ev_ids):
    d = {"case_no": case.n, "dispute_id": case.dispute_id, "trip_id": case.trip_id, "category": cat,
         "filed_at": iso(filed_at), "filed_by": spec["filed_by"], "channel": spec.get("channel", "IN_APP_SUPPORT"),
         "amount_contested_sgd": money(contested), "claim_text": spec["claim"]}
    cs = spec.get("counter")
    if cs:
        by = "DRIVER" if spec["filed_by"] == "RIDER" else "RIDER"
        d["counterparty_statement"] = {"text": cs, "submitted_by": by,
                                       "submitted_at": iso(filed_at + timedelta(minutes=spec.get("counter_after_min", case.rng.randint(40, 900))))}
    else:
        d["counterparty_statement"] = None
    d["evidence_ids"] = ev_ids
    if spec.get("safety_flag") is not None:
        d["safety_flag"] = spec["safety_flag"]
    return d


def stamp_message(msg, vf):
    """LTA incident messages open with '(d/m)HH:MM '; keep that stamp equal to valid_from."""
    m = re.match(r"^\(\d+/\d+\)\d\d:\d\d ", msg)
    if not m:
        return msg
    return "({0}/{1}){2} ".format(vf.day, vf.month, vf.strftime("%H:%M")) + msg[m.end():]


def advisory_artifacts(case, spec, t_start, t_end, gen_at, ass_at, default_missing_notes):
    """Returns (artifacts, adv_facts) ; adv_facts: list of dict(weight, justifies, payload_present)."""
    advs = spec.get("advisories") or ["MISSING"]
    arts, facts = [], []
    for k, a in enumerate(advs, 1):
        eid = case.eid("ADVIS", k)
        key = "TRAFFIC_ADVISORY-{0:02d}".format(k)
        if a == "MISSING":
            notes = spec.get("advisory_missing_notes", default_missing_notes)
            arts.append(artifact(eid, "TRAFFIC_ADVISORY", case.trip_id, "THIRD_PARTY_LTA", gen_at,
                                 admissibility("MISSING", ass_at, notes), None))
            facts.append({"eid": eid, "weight": 0.0, "justifies": None, "missing": True})
            continue
        base = a.get("anchor", t_start)
        vf = a["valid_from"] if isinstance(a["valid_from"], datetime) else base + timedelta(seconds=a["valid_from"])
        vt = a["valid_to"] if isinstance(a["valid_to"], datetime) else base + timedelta(seconds=a["valid_to"])
        payload = {
            "advisory_id": a.get("advisory_id", "LTA-TI-{0}-{1:04d}".format(vf.strftime("%y%m%d"), case.rng.randint(100, 9999))),
            "provider": a.get("provider", "LTA_DATAMALL_TRAFFIC_INCIDENTS"),
            "advisory_type": a["type"],
            "road": a["road"],
            "direction": a.get("direction"),
            "location_desc": a.get("where"),
            "lat": a.get("lat"), "lng": a.get("lng"),
            "message": stamp_message(a["message"], vf),
            "valid_from": iso(vf), "valid_to": iso(vt),
            "speed_band_min": a.get("band"),
            "retrieved_at": iso(gen_at - timedelta(minutes=2)),
        }
        src = a.get("source", "THIRD_PARTY_LTA")
        adm, w = build_adm(spec, key, ass_at, a.get("notes", "LTA historical traffic record for the queried road segment and window; retrieved by the platform, not supplied by a party."))
        arts.append(artifact(eid, "TRAFFIC_ADVISORY", case.trip_id, src, gen_at, adm, payload))
        overlaps = vf < t_end and vt > t_start
        just = a["type"] != "NONE" and a.get("on_recommended", False) and overlaps
        facts.append({"eid": eid, "weight": w, "justifies": just, "missing": False, "spec": a, "vf": vf, "vt": vt,
                      "overlaps": overlaps})
    return arts, facts


# ================================================================ ROUTE DEVIATION
def expand_path(spec):
    raw = spec["path"]
    out = []
    j_idx = r_idx = None
    for k, w in enumerate(raw):
        if w == "BULGE":
            J = out[-1]
            R = raw[k + 1]
            extra = float(D(spec["dev"]) / D(spec.get("factor", "1.18")))
            B = bulge((J[0], J[1]), (R[0], R[1]), extra, spec["bulge"]["side"])
            j_idx = len(out) - 1
            out.append((B[0], B[1], spec["bulge"]["road"]))
            r_idx = len(out)
        else:
            out.append(w)
    return out, j_idx, r_idx


def build_rd(setname, spec):
    case = Case(setname, spec["n"])
    rng = case.rng
    date = spec["date"]
    rc = RATE_CARDS[spec["vehicle"]]
    car = spec.get("car") or rng.choice(CARS[spec["vehicle"]])
    plate = sg_plate(rng)
    rider_id = "R-{0:05d}".format(rng.randint(10000, 99999))
    driver_id = "D-{0:05d}".format(rng.randint(10000, 99999))
    t_req = T(date, spec["t_req"])
    t_acc = t_req + timedelta(seconds=rng.randint(9, 40))
    t_arr = t_acc + timedelta(seconds=spec.get("approach_s", rng.choice([240, 285, 330, 375, 420, 465])))
    t_start = t_arr + timedelta(seconds=spec.get("board_s", rng.choice([45, 60, 75, 90, 105, 120])))
    path, j_idx, r_idx = expand_path(spec)
    pts_ll = [(p[0], p[1]) for p in path]
    cum = path_cum(pts_ll)
    L = cum[-1]
    factor = D(spec.get("factor", "1.18"))
    actual = (D(repr(L)) * factor).quantize(D("0.1"), ROUND_HALF_UP)
    dev = D(spec["dev"])
    opt = actual - dev
    P, Dd = spec["P"], spec["D"]
    crow = hav((P[1], P[2]), (Dd[1], Dd[2]))
    assert float(opt) >= crow * 1.05, (spec["n"], float(opt), crow)
    dur = int(round(float(actual) / spec["avg_kph"] * 3600 / 30.0)) * 30
    t_end = t_start + timedelta(seconds=dur)
    t_dev = t_start + timedelta(seconds=round(dur * cum[j_idx] / L))
    t_rej = t_start + timedelta(seconds=round(dur * cum[r_idx] / L))
    opt_min = (D(dur) / 60 * (opt / actual)).quantize(D("0.1"), ROUND_HALF_UP)
    filed_at = t_end + timedelta(minutes=spec.get("filed_after_min", rng.randint(35, 600)))
    gen_at = filed_at + timedelta(minutes=12)
    ass_at = gen_at + timedelta(seconds=5)

    # ---------------- GPS
    step = 30
    pts = []
    k = 0
    speed = L / dur * 3600.0
    while True:
        t = t_start + timedelta(seconds=k * step)
        if t > t_end:
            break
        d = L * (k * step) / dur
        lat, lng, seg = along(pts_ll, cum, d)
        if 0 < k * step < dur:
            lat += rng.gauss(0, 2.0) / 111195.0
            lng += rng.gauss(0, 2.0) / 111195.0
            sp = int(round(speed * float(factor) * rng.uniform(0.7, 1.25)))
        else:
            sp = 0
        pts.append({"lat": round(lat, 6), "lng": round(lng, 6), "ts": iso(t), "speed_kph": sp,
                    "accuracy_m": rng.choice([3, 4, 4, 5, 5, 6, 7, 8]), "road": path[seg][2]})
        k += 1
    gps_payload = {"trip_id": case.trip_id, "points": pts}
    gps_payload.update(trace_stats(pts, step))
    gps_payload["rider_track"] = []

    # ---------------- chat
    entries = []
    for (rel, sender, text, *ex) in spec.get("chat", []):
        if isinstance(rel, tuple):
            at = t_dev + timedelta(seconds=rel[1])
        else:
            at = t_start + timedelta(seconds=rel)
        entries.append((at, sender, text, ex[0] if ex else None))
    notice_t = None
    if spec.get("notice"):
        nt = spec["notice"]
        notice_t = t_dev + timedelta(seconds=nt["dt"])
        assert t_start < notice_t < t_end
        nex = dict(nt.get("ex") or {})
        if "delivered_dt" in nt:
            nex["delivered_at"] = t_dev + timedelta(seconds=nt["delivered_dt"])
        entries.append((notice_t, "DRIVER", nt["text"], nex))
        if spec.get("reply"):
            rp = spec["reply"]
            entries.append((notice_t + timedelta(seconds=rp["dt"]), "RIDER", rp["text"], rp.get("ex")))
    for e in entries:
        if abs((e[0] - t_dev).total_seconds()) < 45:
            raise ValueError("case {0}: a chat entry sits within 45 s of the deviation point".format(spec["n"]))
    msgs = chat_messages(case, entries)
    chat_full = len(msgs)
    if spec.get("truncate_chat_to") is not None:
        msgs = msgs[:spec["truncate_chat_to"]]
    chat_payload = {"trip_id": case.trip_id, "messages": msgs, "message_count": len(msgs),
                    "first_message_at": msgs[0]["sent_at"] if msgs else None,
                    "last_message_at": msgs[-1]["sent_at"] if msgs else None,
                    "truncated": spec.get("truncate_chat_to") is not None}

    # ---------------- fare
    surge = D(spec.get("surge", "1.0"))
    dist_fare = m2(actual * rc["per_km"])
    tmin = (D(dur) / 60)
    time_fare = m2(tmin * rc["per_min"])
    surge_amt = m2((rc["base"] + dist_fare + time_fare) * (surge - 1))
    gantries = []
    for (name, amt, frac) in spec.get("erp", []):
        gantries.append({"gantry_id": "ERP-{0}".format(rng.randint(10, 99)), "location": name,
                         "passed_at": iso(t_start + timedelta(seconds=round(dur * frac))), "amount_sgd": money(amt)})
    tolls = sum((m2(g["amount_sgd"]) for g in gantries), D("0.00"))
    airport = m2(spec.get("airport", "0.00"))
    promo = m2(spec.get("promo", "0.00"))
    total = rc["base"] + dist_fare + time_fare + surge_amt + tolls + airport + rc["platform"] - promo
    excess = m2(dev * rc["per_km"])
    driver_filed = spec["filed_by"] == "DRIVER"
    refund = excess if driver_filed else D("0.00")
    fare_payload = {
        "trip_id": case.trip_id, "currency": "SGD", "fare_model": "METERED", "cancellation_fee": 0.0,
        "total_charged": money(total), "payment_status": "PARTIALLY_REFUNDED" if driver_filed else "CHARGED",
        "refund_issued_sgd": money(refund), "charged_at": iso(t_end + timedelta(seconds=6)),
        "surge_multiplier": float(surge), "rate_card_id": rc["id"], "base_fare": money(rc["base"]),
        "distance_fare": money(dist_fare), "time_fare": money(time_fare), "surge_amount": money(surge_amt),
        "tolls_erp": money(tolls), "airport_surcharge": money(airport), "platform_fee": money(rc["platform"]),
        "promo_discount": money(promo), "waiting_time_fee": 0.0, "quoted_fare_sgd": None,
        "distance_charged_km": float(actual), "time_charged_min": float(tmin), "per_km_rate_sgd": money(rc["per_km"]),
        "per_min_rate_sgd": money(rc["per_min"]), "erp_gantries": gantries}
    contested = spec["contested"]
    if contested == "TOTAL":
        contested = m2(total)
    elif contested == "CLAWBACK":
        contested = excess
    contested = m2(contested)
    assert D("0") < contested <= m2(total), (spec["n"], contested, total)

    # ---------------- trip record
    events = [
        ("booking_confirmed", t_req, "Rider {0} booked {1} from {2} to {3}. On-demand, metered fare.".format(rider_id, case.trip_id, P[0], Dd[0])),
        ("driver_assigned", t_acc, "Driver {0} ({1}, {2}) assigned. ETA {3} min.".format(driver_id, car, plate, max(1, secs(t_acc, t_arr) // 60))),
        ("driver_arrived", t_arr, "Driver marked arrived at pickup (button)."),
        ("trip_started", t_start, "Rider on board. Recommended route via {0}, {1} km.".format(", ".join(spec["opt_via"]), opt)),
        ("route_deviation_detected", t_dev + timedelta(seconds=20), "Vehicle left the recommended route at {0}: recommended {1}, vehicle took {2}.".format(spec["junction"], spec["opt_next"], path[j_idx][2])),
        ("route_rejoined", t_rej, "Vehicle rejoined the recommended route at {0}.".format(spec["rejoin"])),
        ("trip_completed", t_end, "Trip ended at {0}. Recorded distance {1} km, duration {2}.".format(Dd[0], actual, mmss(dur))),
        ("fare_finalised", t_end + timedelta(seconds=6), "Metered fare SGD {0} charged to rider payment method.".format(m2(total))),
    ]
    if driver_filed:
        t_adj = filed_at - timedelta(minutes=spec.get("adjust_before_min", 95))
        events.append(("fare_adjusted", t_adj, "Interim adjustment after a rider route complaint: SGD {0} refunded to rider and recovered from driver earnings pending review.".format(excess)))
    events.sort(key=lambda e: e[1])
    trip = {
        "trip_id": case.trip_id, "rider_id": rider_id, "driver_id": driver_id,
        "requested_at": iso(t_req), "accepted_at": iso(t_acc), "arrived_at": iso(t_arr), "started_at": iso(t_start),
        "ended_at": iso(t_end), "cancelled_at": None, "status": "COMPLETED", "cancelled_by": None,
        "cancellation_reason_code": None,
        "pickup": {"label": P[0], "lat": P[1], "lng": P[2], "venue_id": spec.get("venue_id")},
        "dropoff": {"label": Dd[0], "lat": Dd[1], "lng": Dd[2], "venue_id": None},
        "vehicle_type": spec["vehicle"], "pickup_zone_class": spec.get("zone", "STANDARD"),
        "chat_message_count": chat_full, "registered_pickup_points": None, "in_app_calls": [],
        "optimal_distance_km": float(opt), "optimal_duration_min": float(opt_min), "optimal_route_source": "PLATFORM_ROUTER",
        "optimal_route_erp_sgd": money(spec.get("opt_erp", "0.00")), "actual_distance_km": float(actual),
        "actual_duration_min": float(tmin), "deviation_pct": float((dev / opt * 100).quantize(D("0.1"), ROUND_HALF_UP)),
        "amended_optimal_distance_km": None, "amended_optimal_duration_min": None, "solo_optimal_distance_km": None,
        "pickup_amended_at": None, "dropoff_amended_at": None, "original_pickup": None, "original_dropoff": None,
        "scheduled_at": None,
        "optimal_route_via": spec["opt_via"], "actual_route_via": spec["act_via"],
        "events": [{"event_type": a, "at": iso(b), "detail": c, "source": "PLATFORM_TELEMETRY"} for a, b, c in events],
    }
    for k in spec.get("trip_null", []):
        trip[k] = None

    # ---------------- artifacts
    arts = []
    a_trip, w_trip = build_adm(spec, "TRIP_RECORD", ass_at, "Platform trip record; timestamps causally ordered; recorded optimal and actual distances present; deviation and rejoin events carried in events[].")
    arts.append(artifact(case.eid("TRIP"), "TRIP_RECORD", case.trip_id, "PLATFORM_TELEMETRY", gen_at, a_trip, trip))
    a_gps, w_gps = build_adm(spec, "GPS_TRACE", ass_at, "Driver-device trace, {0} fixes at {1} s from trip start to trip end; every fix reports horizontal accuracy (max {2} m) and a map-matched road; no interval exceeds 120 s.".format(len(pts), step, max(p["accuracy_m"] for p in pts)))
    arts.append(artifact(case.eid("GPS"), "GPS_TRACE", case.trip_id, "DRIVER_DEVICE", gen_at, a_gps, gps_payload))
    a_chat, w_chat = build_adm(spec, "CHAT_LOG", ass_at, "Platform chat log, {0} entries, contiguous; matches trip_record.chat_message_count.".format(len(msgs)))
    arts.append(artifact(case.eid("CHAT"), "CHAT_LOG", case.trip_id, "PLATFORM_TELEMETRY", gen_at, a_chat, chat_payload,
                         schema=spec.get("chat_schema", "1.2.0")))
    a_fare, w_fare = build_adm(spec, "FARE_BREAKDOWN", ass_at, "Payments ledger; itemised lines reconcile to total_charged; tolls_erp equals the gantry list.")
    arts.append(artifact(case.eid("FARE"), "FARE_BREAKDOWN", case.trip_id, "PAYMENTS_LEDGER", gen_at, a_fare, fare_payload))
    rp = profile(case, "RIDER", rider_id, filed_at, rng, spec.get("rider_prof"))
    dp = profile(case, "DRIVER", driver_id, filed_at, rng, spec.get("driver_prof"), vehicle=spec["vehicle"])
    arts.append(artifact(case.eid("RPROF"), "RIDER_PROFILE", case.trip_id, "PLATFORM_TELEMETRY", gen_at,
                         admissibility("COMPLETE", ass_at, "Rider profile snapshot at filing."), rp))
    arts.append(artifact(case.eid("DPROF"), "DRIVER_PROFILE", case.trip_id, "PLATFORM_TELEMETRY", gen_at,
                         admissibility("COMPLETE", ass_at, "Driver profile snapshot at filing."), dp))
    adv_arts, adv_facts = advisory_artifacts(case, spec, t_start, t_end, gen_at, ass_at,
                                             "Artifact absent: the platform's request to the LTA historical traffic feed for this trip window failed (feed timeout) and was not retried, so no traffic record was retrieved. The record is silent on traffic on the recommended route; this is not a finding of no traffic. The identifier is minted so that the absence can be cited.")
    arts.extend(adv_arts)
    dispute = dispute_block(case, spec, "ROUTE_DEVIATION", filed_at, contested, [a["evidence_id"] for a in arts])
    doc = {"schema_version": "1.2.0", "case_no": case.n, "dispute": dispute, "evidence": arts}

    # ---------------- facts for the answer
    if any(not f["missing"] for f in adv_facts):
        present = [f for f in adv_facts if not f["missing"]]
        jus = [f for f in present if f["justifies"]]
        if jus:
            J, w_J, j_eids = True, max(f["weight"] for f in jus), [f["eid"] for f in jus]
        else:
            J, w_J, j_eids = False, min(f["weight"] for f in present), [f["eid"] for f in present]
    else:
        J, w_J, j_eids = None, 0.0, [f["eid"] for f in adv_facts]
    if spec.get("notice"):
        notice = "before" if spec["notice"]["dt"] <= 0 else "after"
    else:
        notice = "none"
    rk = (spec.get("reply") or {}).get("kind")
    agree = {"agreed": "agreed", "objected": "not", "ambiguous": None, None: "not"}[rk]
    facts = {"dev_gt1": dev > TOLERANCE_KM, "J": J, "notice": notice, "agree": agree}
    facts.update(spec.get("facts", {}))
    w_notice = w_chat if notice == "none" else min(w_chat, max(w_trip, w_gps))
    weights = {"dev_gt1": w_trip, "J": w_J, "notice": w_notice, "agree": w_chat}
    info = dict(case=case, spec=spec, dev=dev, opt=opt, actual=actual, rate=rc["per_km"], excess=excess,
                contested=contested, total=m2(total), surge=surge, t_dev=t_dev, notice_t=notice_t, J=J,
                j_eids=j_eids, adv_facts=adv_facts, weights=weights, w_fare=w_fare, w_chat=w_chat, w_gps=w_gps,
                w_trip=w_trip, rider_prof=rp, driver_prof=dp, facts=facts, junction=spec["junction"],
                refund=refund, rider_id=rider_id)
    answer = derive_rd(info)
    return doc, answer


RD_DOMS = {"dev_gt1": [True, False], "J": [True, False], "notice": ["before", "none"], "agree": ["agreed", "not"]}


def rd_label(dev_gt1, J, notice, agree):
    if J is False:
        return "d" if dev_gt1 else "e"
    if notice in ("none", "after"):
        return "b" if dev_gt1 else "c"
    if dev_gt1 and agree == "agreed":
        return "a"
    return "none"


RD_RULING = {"a": "NO_ACTION", "b": "PARTIAL_REFUND", "c": "NO_ACTION", "d": "PARTIAL_REFUND", "e": "NO_ACTION", "none": "NOROW"}


def rd_outcomes(f):
    keys = list(RD_DOMS)
    vals = [[f[k]] if f[k] is not None else RD_DOMS[k] for k in keys]
    return {RD_RULING[rd_label(*c)] for c in itertools.product(*vals)}


def fraud_of(info):
    return max(int(info["rider_prof"].get("fraud_flags") or 0), int(info["driver_prof"].get("fraud_flags") or 0))


def clause_list(cs):
    out = []
    for c in cs:
        if c not in out:
            out.append(c)
    return out


def cite(cs):
    return "; ".join("{0} (v2.1 {1})".format(c, SECTION[c]) for c in cs)


def derive_rd(info):
    spec, case = info["spec"], info["case"]
    n = case.n
    E = lambda tok, k=None: case.eid(tok, k)
    f = info["facts"]
    fraud = fraud_of(info)
    contested = info["contested"]
    driver_filed = spec["filed_by"] == "DRIVER"
    parts = []
    who = "driver" if driver_filed else "rider"
    band = "below 10.00" if contested < AI_FINAL_BELOW else ("10.00-50.00" if contested <= HUMAN_ABOVE else "above 50.00")
    parts.append("Filed by the {0}; dispute value (amount_contested_sgd) SGD {1}, band {2} (POL-GEN-22).".format(who, contested, band))
    if driver_filed:
        parts.append("The driver contests the interim SGD {0} recovered from earnings and refunded to the rider ({1}: refund_issued_sgd; {2}: fare_adjusted).".format(info["refund"], E("FARE"), E("TRIP")))
    if fraud:
        side = "rider" if int(info["rider_prof"].get("fraud_flags") or 0) else "driver"
        parts.append("{0} carries {1}_profile.fraud_flags = {2}, so a ruling needs confidence 0.95 (POL-GEN-22, v2.1 6.3); the flag is cited only for that threshold and decides nothing (POL-GEN-01).".format(E("RPROF") if side == "rider" else E("DPROF"), side, fraud))
    note = spec.get("note")
    referrals = []

    def esc(clauses, why):
        parts.append(why)
        if note:
            parts.append(note)
        return {"ruling": "ESCALATE", "amount": None, "dc": None, "referrals": [], "clauses": clause_list(clauses), "parts": parts}

    if spec.get("safety_flag") or spec.get("safety_indicator"):
        return finish(info, esc(["POL-GEN-21"], "Safety: the dispute is flagged safety-related ({0}) and the record carries a safety indicator ({1}); POL-GEN-21 sends it to human review whatever category was chosen, and the AI issues no ruling, fault finding or recommendation on it. Escalate.".format("dispute.safety_flag = true" if spec.get("safety_flag") else "no flag set", spec.get("safety_where", E("CHAT")))))
    if contested > HUMAN_ABOVE:
        return finish(info, esc(["POL-GEN-22", "POL-RD-25"], "The value SGD {0} (the whole metered fare, {1} total_charged) is above 50.00, so the case always goes to human review and the AI prepares the case file only (POL-GEN-22, POL-RD-25). Escalate.".format(contested, E("FARE"))))

    # describe facts
    dev = info["dev"]
    if f["dev_gt1"] is None:
        parts.append("The deviation cannot be established: {0} (POL-RD-22).".format(spec.get("dev_unknown_why", "a recorded distance is missing or impaired")))
    else:
        parts.append("{0} records actual_distance_km {1} against optimal_distance_km {2}: deviation {3} km (POL-RD-22, v2.1 1.4), {4} the 1 km tolerance.".format(
            E("TRIP"), info["actual"], info["opt"], dev, "over" if dev > TOLERANCE_KM else "within"))
    if f["J"] is None:
        parts.append("Traffic justification cannot be established: {0} (POL-RD-23).".format(spec.get("J_unknown_why", "{0} is MISSING (weight 0.0)".format(", ".join(info["j_eids"])))))
    elif f["J"]:
        parts.append("{0} reports {1} on {2}, a road of the recommended route, overlapping the trip window: the reroute is traffic-justified (POL-RD-23, v2.1 1.4).".format(
            ", ".join(info["j_eids"]), spec.get("J_desc", "an incident"), spec.get("J_road", "the recommended route")))
    else:
        parts.append("Not traffic-justified (POL-RD-23, v2.1 1.4): {0}.".format(spec.get("J_no_why", "the traffic record shows no congestion, incident or closure on the recommended route in the trip window")))
    t_dev = info["t_dev"]
    if f["notice"] is None:
        parts.append("Whether the rider was informed before the deviation cannot be established: {0} (POL-RD-21).".format(spec.get("notice_unknown_why", "")))
    elif f["notice"] == "none":
        parts.append("{0} holds no notice of the reroute before or at the deviation at {1} ({2} route_deviation_detected; {3}) (POL-RD-21, v2.1 1.2).".format(E("CHAT"), hms(t_dev), E("TRIP"), E("GPS")))
    else:
        nt = info["notice_t"]
        parts.append("The driver's notice in {0} is at {1}, {2} the deviation at {3} ({4} route_deviation_detected; {5} fixes) (POL-RD-21, v2.1 1.2){6}.".format(
            E("CHAT"), hms(nt), "before" if f["notice"] == "before" else "after", hms(t_dev), E("TRIP"), E("GPS"),
            "; a notice after the point of deviation does not count as informing the rider" if f["notice"] == "after" else ""))
        if f["notice"] == "before":
            parts.append({"agreed": "The rider acknowledged it in chat, so the deviation is agreed.",
                          "not": spec.get("agree_not_desc", "The rider did not agree."),
                          None: spec.get("agree_unknown_why", "Whether the rider agreed cannot be read from the reply.")}[f["agree"]])
    for extra in spec.get("fact_notes", []):
        parts.append(extra)

    outs = rd_outcomes(f)
    unknown = [k for k in RD_DOMS if f[k] is None]
    if len(outs) > 1:
        cl = ["POL-GEN-26", "POL-RD-24"]
        if f["J"] is None:
            cl.append("POL-RD-23")
        if f["notice"] is None or f["agree"] is None:
            cl.append("POL-RD-21")
        if f["dev_gt1"] is None:
            cl.append("POL-RD-22")
        if any(w < 1.0 for w in info["weights"].values()):
            cl.append("POL-GEN-02")
        if fraud:
            cl += ["POL-GEN-22", "POL-GEN-01"]
        return finish(info, esc(cl, "The open fact decides between rows of POL-RD-24 that give different outcomes, so the case cannot be decided on this record: escalate under POL-GEN-26 with the open question stated."))
    out = outs.pop()
    if out == "NOROW":
        return finish(info, esc(["POL-RD-24", "POL-GEN-26", "POL-RD-21", "POL-RD-23"], "Traffic-justified, rider informed in time but did not agree, deviation over 1 km: the case fits no row of POL-RD-24 (v2.1 1.3 has no row for an informed rider who objects), so it is escalated under POL-GEN-26."))

    # deciding facts and the confidence cap
    deciding = []
    for k in RD_DOMS:
        if f[k] is None:
            continue
        for alt in RD_DOMS[k]:
            if alt == f[k]:
                continue
            g = dict(f)
            g[k] = alt
            if rd_outcomes(g) != {out}:
                deciding.append(k)
                break
    caps = {k: info["weights"][k] for k in deciding}
    if out == "PARTIAL_REFUND":
        caps["rate"] = info["w_fare"]
    cap = min(caps.values()) if caps else 1.0
    need = CONF_FRAUD if fraud else CONF_ROUTE
    label = rd_label(**{k: (f[k] if f[k] is not None else RD_DOMS[k][0]) for k in RD_DOMS})
    if D(repr(cap)) < need:
        low = [k for k, v in caps.items() if v == cap]
        cl = ["POL-GEN-02", "POL-RD-25"]
        if fraud:
            cl += ["POL-GEN-22", "POL-GEN-01"]
        if contested >= AI_FINAL_BELOW:
            cl.append("POL-GEN-22")
        return finish(info, esc(cl, "The facts point to row ({0}) of POL-RD-24, but the deciding fact rests on an artifact of weight {1} ({2}); under POL-GEN-02(2) confidence cannot exceed {1}, below the {3} this ruling needs (POL-RD-25{4}). Escalate.".format(
            label, cap, spec.get("cap_desc", ", ".join(low)), need, ", POL-GEN-22" if fraud else "")))

    row_text = {"a": "row (a): traffic-justified, informed and agreed, over 1 km - no refund",
                "b": "row (b): traffic-justified, rider not informed, over 1 km - refund of the excess distance fare",
                "c": "row (c): traffic-justified, rider not informed, 1 km or less - within tolerance, no refund",
                "d": "row (d): not traffic-justified, over 1 km - refund of the excess distance fare in full",
                "e": "row (e): not traffic-justified, 1 km or less - within tolerance, no refund"}[label]
    parts.append("POL-RD-24 (v2.1 1.3) {0}.".format(row_text))
    clauses = ["POL-RD-24", "POL-RD-22"]
    if f["J"] is not None:
        clauses.append("POL-RD-23")
    if "notice" in deciding or "agree" in deciding or f["notice"] in ("before", "after"):
        clauses.append("POL-RD-21")
    if label == "b":
        clauses.append("POL-GEN-23")
        parts.append("Consistent with precedent 7.1 (DISP-2026-0089), an unnotified traffic reroute (POL-GEN-23).")
    if cap < 1.0:
        clauses.append("POL-GEN-02")
    if out == "PARTIAL_REFUND":
        parts.append("Excess distance fare = {0} km x per_km_rate_sgd {1} ({2}) = SGD {3}, no surge (surge_multiplier {4} not applied), rounded to the cent.".format(
            dev, info["rate"], E("FARE"), info["excess"], info["surge"]))
    if dev > AI_MAX_DEV_KM:
        clauses.append("POL-RD-25")
        parts.append("The deviation exceeds 2 km: this answer depends on route_deviation.thresholds.ai_ruling_max_deviation_applied, which is false, so the 2 km limb of POL-RD-25 (v2.1 6.2) is not applied and the AI ruling stands; were it true, the case would be escalated.")
    need_txt = "0.95 (fraud flag)" if fraud else "0.80 (POL-RD-25)"
    parts.append("Confidence cap from the deciding artifacts: {0}; required {1}: met.".format(cap, need_txt))
    if fraud:
        clauses += ["POL-GEN-22", "POL-GEN-01"]
    elif contested >= AI_FINAL_BELOW:
        clauses.append("POL-GEN-22")
    if spec.get("context_cited"):
        clauses.append("POL-GEN-01")
    if driver_filed:
        assert out == "PARTIAL_REFUND", "driver-filed route cases are built only where the rider is owed the excess"
        assert info["refund"] == info["excess"], (n, info["refund"], info["excess"])
        clauses.append("POL-GEN-03")
        parts.append("The rider is owed exactly the SGD {0} already recovered from the driver, so the driver's claim is not supported and the present state stands: NO_ACTION, which is party-relative (POL-GEN-03).".format(info["excess"]))
        if note:
            parts.append(note)
        return finish(info, {"ruling": "NO_ACTION", "amount": None, "dc": None, "referrals": [], "clauses": clause_list(clauses), "parts": parts})
    if note:
        parts.append(note)
    if out == "PARTIAL_REFUND":
        return finish(info, {"ruling": "PARTIAL_REFUND", "amount": info["excess"], "dc": None, "referrals": [], "clauses": clause_list(clauses), "parts": parts})
    return finish(info, {"ruling": "NO_ACTION", "amount": None, "dc": None, "referrals": [], "clauses": clause_list(clauses), "parts": parts})


def finish(info, r):
    spec, case = info["spec"], info["case"]
    imp = spec.get("impair") or {}
    if imp:
        bits = []
        for key, v in imp.items():
            etok = {"TRIP_RECORD": "TRIP", "GPS_TRACE": "GPS", "CHAT_LOG": "CHAT", "FARE_BREAKDOWN": "FARE"}.get(key)
            eid = case.eid(etok) if etok else case.eid("ADVIS", int(key.split("-")[-1]))
            w = 1.0
            for c in v["issues"]:
                w *= WEIGHTS[(v.get("grades") or {}).get(c, c)]
            bits.append("{0} is IMPAIRED ({1}; weight {2})".format(eid, ", ".join(v["issues"]), round(w, 4)))
        r["parts"].append("Admissibility (POL-GEN-02): " + "; ".join(bits) + ".")
        if "POL-GEN-02" not in r["clauses"] and r["ruling"] != "ESCALATE":
            r["parts"].append(spec.get("impair_irrelevant", "The impaired artifact does not carry the deciding fact."))
    if spec.get("context_note"):
        r["parts"].append(spec["context_note"])
    r["parts"].append("Governing: {0}.".format(cite(r["clauses"])))
    text = " ".join(p for p in r["parts"] if p)
    amt = None if r["amount"] is None else money(r["amount"])
    dc = None if r["dc"] is None else money(r["dc"])
    return {"case_no": case.n, "dispute_id": case.dispute_id,
            "ground_truth": {"expected_ruling": r["ruling"], "expected_amount_sgd": amt,
                             "expected_driver_compensation_sgd": dc, "expected_referrals": r["referrals"],
                             "governing_clauses": r["clauses"], "difficulty": spec["difficulty"],
                             "rationale": text}}


# ================================================================ NO-SHOW
def build_ns(setname, spec):
    case = Case(setname, spec["n"])
    rng = case.rng
    date = spec["date"]
    P, Dd = spec["P"], spec["D"]
    pick = (P[1], P[2])
    zone = spec.get("zone", "STANDARD")
    radius = RADIUS_M[zone]
    vehicle = spec.get("vehicle", "RYDE_X")
    car = spec.get("car") or rng.choice(CARS[vehicle])
    plate = sg_plate(rng)
    rider_id = "R-{0:05d}".format(rng.randint(10000, 99999))
    driver_id = "D-{0:05d}".format(rng.randint(10000, 99999))
    sched = T(date, spec["sched"]) if spec.get("sched") else None
    t_req = T(spec.get("req_date", date), spec["t_req"])
    t_acc = T(date, spec["t_acc"])
    t_stop = T(date, spec["t_stop"])
    stop = offset(pick, *spec["stop_off"]) if spec.get("stop_off") else offset(pick, rng.uniform(-6, 6), rng.uniform(-6, 6))
    start = offset(pick, *spec["start_off"])
    via = [offset(pick, *v) for v in spec.get("via_off", [])]
    t_cancel = T(date, spec["cancel"][0])
    cancelled_by, reason = spec["cancel"][1], spec["cancel"][2]
    arrive = spec.get("arrive")  # (hms, marker) or None
    t_mark = T(date, arrive[0]) if arrive else None
    filed_at = t_cancel + timedelta(minutes=spec.get("filed_after_min", rng.randint(25, 400)))
    gen_at = filed_at + timedelta(minutes=12)
    ass_at = gen_at + timedelta(seconds=5)

    # ---------------- GPS: approach then stationary
    step = spec.get("gps_step", 30)
    path = [start] + via + [stop]
    cum = path_cum(path)
    L = cum[-1]
    t0 = t_acc + timedelta(seconds=step)
    t_end_gps = t_cancel + timedelta(seconds=spec.get("gps_tail_s", 0))
    pts = []
    t = t0
    drift = spec.get("gps_drift_m")
    while t <= t_end_gps:
        if t < t_stop:
            d = L * secs(t0, t) / max(secs(t0, t_stop), 1)
            lat, lng, _ = along(path, cum, d)
            lat += rng.gauss(0, 2.5) / 111195.0
            lng += rng.gauss(0, 2.5) / 111195.0
            sp = int(round(L / max(secs(t0, t_stop), 1) * 3600 * 1.2 * rng.uniform(0.6, 1.3)))
            acc = rng.choice([4, 5, 5, 6, 7, 8, 9])
        else:
            if drift:
                ang = rng.uniform(0, 2 * math.pi)
                r = rng.uniform(drift[0], drift[1])
                lat, lng = offset(stop, r * math.sin(ang), r * math.cos(ang))
                acc = rng.choice([18, 22, 24])
            else:
                lat, lng = offset(stop, rng.gauss(0, 2.0), rng.gauss(0, 2.0))
                acc = rng.choice([3, 4, 4, 5, 6])
            sp = 0
        gap = spec.get("gps_gap")
        if not (gap and T(date, gap[0]) < t < T(date, gap[1])):
            pts.append({"lat": round(lat, 6), "lng": round(lng, 6), "ts": iso(t), "speed_kph": sp, "accuracy_m": acc})
        t += timedelta(seconds=step)
    for (h, off_ne, sp) in spec.get("gps_extra", []):
        ll = offset(pick, *off_ne)
        pts.append({"lat": round(ll[0], 6), "lng": round(ll[1], 6), "ts": iso(T(date, h)), "speed_kph": sp, "accuracy_m": 5})
    pts.sort(key=lambda p: p["ts"])
    gps_payload = {"trip_id": case.trip_id, "points": pts}
    gps_payload.update(trace_stats(pts, step))
    gps_payload["rider_track"] = []
    stop_dist = metres(stop, pick)

    # ---------------- chat and calls
    entries = []
    for (h, sender, text, *ex) in spec.get("msgs", []):
        entries.append((T(date, h), sender, text, ex[0] if ex else None))
    msgs = chat_messages(case, entries)
    chat_full = len(msgs)
    if spec.get("truncate_chat_to") is not None:
        msgs = msgs[:spec["truncate_chat_to"]]
    chat_payload = {"trip_id": case.trip_id, "messages": msgs, "message_count": len(msgs),
                    "first_message_at": msgs[0]["sent_at"] if msgs else None,
                    "last_message_at": msgs[-1]["sent_at"] if msgs else None,
                    "truncated": spec.get("truncate_chat_to") is not None}
    calls = [{"placed_by": by, "placed_at": iso(T(date, h)), "duration_sec": dsec, "answered": ans}
             for (by, h, dsec, ans) in spec.get("calls", [])]

    # ---------------- fare
    fee = m2(spec.get("fee", "5.00"))
    driver_filed = spec["filed_by"] == "DRIVER"
    t_rev = filed_at - timedelta(minutes=spec.get("reverse_before_min", 80)) if driver_filed else None
    fare_payload = {
        "trip_id": case.trip_id, "currency": "SGD", "fare_model": "METERED", "cancellation_fee": money(fee),
        "total_charged": money(fee), "payment_status": "REFUNDED" if driver_filed else "CHARGED",
        "refund_issued_sgd": money(fee) if driver_filed else 0.0, "charged_at": iso(t_cancel + timedelta(seconds=4)),
        "surge_multiplier": 1.0, "rate_card_id": None, "base_fare": 0.0, "distance_fare": 0.0, "time_fare": 0.0,
        "surge_amount": 0.0, "tolls_erp": 0.0, "airport_surcharge": 0.0, "platform_fee": 0.0, "promo_discount": 0.0,
        "waiting_time_fee": 0.0, "quoted_fare_sgd": None, "distance_charged_km": None, "time_charged_min": None,
        "per_km_rate_sgd": None, "per_min_rate_sgd": None, "erp_gantries": []}
    contested = fee

    # ---------------- trip record
    ev = []
    ev.append(("booking_confirmed", t_req, "Rider {0} booked {1} from {2} to {3}.{4}".format(
        rider_id, case.trip_id, P[0], Dd[0], " Scheduled pickup {0}.".format(sched.strftime("%H:%M")) if sched else " On-demand.")))
    ev.append(("driver_assigned", t_acc, "Driver {0} ({1}, {2}) assigned.".format(driver_id, car, plate)))
    ev.append(("driver_en_route", t_acc + timedelta(seconds=6), "Driver started navigating to the pickup. Live tracking enabled."))
    if t_mark:
        mk = arrive[1]
        ev.append(("driver_arrived", t_mark, "Driver marked arrived (button)." if mk == "BUTTON" else "Auto-arrival from driver GPS near the pickup point."))
        ev.append(("rider_notified", t_mark + timedelta(seconds=4), "Push notification sent to rider: 'Your driver has arrived.'"))
        ev.append(("wait_timer_started", t_mark + timedelta(seconds=5), "Free wait timer started."))
        if t_mark + timedelta(seconds=305) < t_cancel:
            ev.append(("wait_timer_expired", t_mark + timedelta(seconds=305), "Free wait period expired; rider not on board."))
    for c in spec.get("calls", []):
        by, h, dsec, ans = c
        ev.append(("driver_called_rider" if by == "DRIVER" else "rider_called_driver", T(date, h),
                   "In-app call placed by the {0}; {1}.".format(by.lower(), "answered, {0} s".format(dsec) if ans else "not answered, rang {0} s".format(dsec))))
    ev.append(("trip_cancelled", t_cancel, "Trip cancelled by {0}. Reason: {1}.".format(cancelled_by.lower(), reason)))
    ev.append(("cancellation_fee_applied", t_cancel + timedelta(seconds=4), "SGD {0} cancellation fee charged to rider payment method.".format(fee)))
    if driver_filed:
        ev.append(("fee_reversed", t_rev, "Interim reversal after a rider complaint: SGD {0} refunded to rider and withheld from driver pending review.".format(fee)))
    ev.sort(key=lambda e: e[1])
    trip = {
        "trip_id": case.trip_id, "rider_id": rider_id, "driver_id": driver_id,
        "requested_at": iso(t_req), "accepted_at": iso(t_acc), "arrived_at": iso(t_mark) if t_mark else None,
        "started_at": None, "ended_at": None, "cancelled_at": iso(t_cancel),
        "status": "CANCELLED_BY_DRIVER" if cancelled_by == "DRIVER" else "CANCELLED_BY_RIDER",
        "cancelled_by": cancelled_by, "cancellation_reason_code": reason,
        "pickup": {"label": P[0], "lat": P[1], "lng": P[2], "venue_id": spec.get("venue_id")},
        "dropoff": {"label": Dd[0], "lat": Dd[1], "lng": Dd[2], "venue_id": None},
        "vehicle_type": vehicle, "pickup_zone_class": zone, "chat_message_count": chat_full,
        "registered_pickup_points": None, "in_app_calls": calls,
        "optimal_distance_km": None, "optimal_duration_min": None, "optimal_route_source": None,
        "optimal_route_erp_sgd": None, "actual_distance_km": None, "actual_duration_min": None, "deviation_pct": None,
        "amended_optimal_distance_km": None, "amended_optimal_duration_min": None, "solo_optimal_distance_km": None,
        "pickup_amended_at": None, "dropoff_amended_at": None, "original_pickup": None, "original_dropoff": None,
        "scheduled_at": iso(sched) if sched else None,
        "events": [{"event_type": a, "at": iso(b), "detail": c, "source": "PLATFORM_TELEMETRY"} for a, b, c in ev],
    }

    arts = []
    a_trip, w_trip = build_adm(spec, "TRIP_RECORD", ass_at, "Platform trip record; timestamps causally ordered; in-app call records carried in in_app_calls.")
    arts.append(artifact(case.eid("TRIP"), "TRIP_RECORD", case.trip_id, "PLATFORM_TELEMETRY", gen_at, a_trip, trip))
    a_gps, w_gps = build_adm(spec, "GPS_TRACE", ass_at, "Driver-device trace, {0} fixes at {1} s from acceptance to cancellation; every fix reports horizontal accuracy (max {2} m); no interval exceeds 120 s.".format(len(pts), step, max(p["accuracy_m"] for p in pts)))
    arts.append(artifact(case.eid("GPS"), "GPS_TRACE", case.trip_id, "DRIVER_DEVICE", gen_at, a_gps, gps_payload))
    a_chat, w_chat = build_adm(spec, "CHAT_LOG", ass_at, "Platform chat log, {0} entries, contiguous; matches trip_record.chat_message_count.".format(len(msgs)))
    arts.append(artifact(case.eid("CHAT"), "CHAT_LOG", case.trip_id, "PLATFORM_TELEMETRY", gen_at, a_chat, chat_payload,
                         schema=spec.get("chat_schema", "1.2.0")))
    a_fare, w_fare = build_adm(spec, "FARE_BREAKDOWN", ass_at, "Payments ledger: one cancellation-fee line; lines reconcile to total_charged.")
    arts.append(artifact(case.eid("FARE"), "FARE_BREAKDOWN", case.trip_id, "PAYMENTS_LEDGER", gen_at, a_fare, fare_payload))
    rp = profile(case, "RIDER", rider_id, filed_at, rng, spec.get("rider_prof"))
    dp = profile(case, "DRIVER", driver_id, filed_at, rng, spec.get("driver_prof"), vehicle=vehicle)
    arts.append(artifact(case.eid("RPROF"), "RIDER_PROFILE", case.trip_id, "PLATFORM_TELEMETRY", gen_at,
                         admissibility("COMPLETE", ass_at, "Rider profile snapshot at filing."), rp))
    arts.append(artifact(case.eid("DPROF"), "DRIVER_PROFILE", case.trip_id, "PLATFORM_TELEMETRY", gen_at,
                         admissibility("COMPLETE", ass_at, "Driver profile snapshot at filing."), dp))
    adv_arts, _ = advisory_artifacts(case, spec, t_acc, t_cancel, gen_at, ass_at,
                                     "Artifact absent: no traffic-data record was attached for this trip. The identifier is minted so that the absence can be cited.")
    arts.extend(adv_arts)
    dispute = dispute_block(case, spec, "NO_SHOW_CHARGE", filed_at, contested, [a["evidence_id"] for a in arts])
    doc = {"schema_version": "1.2.0", "case_no": case.n, "dispute": dispute, "evidence": arts}

    # ---------------- facts
    in_radius = [p for p in pts if metres((p["lat"], p["lng"]), pick) <= radius and p["accuracy_m"] <= 25]
    arrived = stop_dist <= radius
    t_arr = None
    if arrived:
        assert t_mark is not None and t_mark >= t_stop, spec["n"]
        t_arr = t_mark
        if sched is not None:
            assert t_arr <= sched + timedelta(seconds=DRIVER_LATE_SEC), ("late scheduled arrival is not built", spec["n"])
    msg_times = [T(date, h) for (h, s, txt, *ex) in spec.get("msgs", [])
                 if s == "DRIVER" and (not ex or (ex[0] or {}).get("channel", "IN_APP") == "IN_APP")]
    vlog_times = [T(date, h) for (h, s, txt, *ex) in spec.get("msgs", [])
                  if s == "DRIVER" and ex and (ex[0] or {}).get("channel") == "VOICE_CALL_LOG"]
    call_times = [T(date, h) for (by, h, dsec, ans) in spec.get("calls", []) if by == "DRIVER"]
    msg = any(t < t_cancel for t in msg_times)
    call_tr = any(t < t_cancel for t in call_times)
    call_ch = any(t < t_cancel for t in vlog_times)
    call = call_tr or call_ch
    if call and call_tr and call_ch:
        w_call = max(w_trip, w_chat)
    elif call:
        w_call = w_trip if call_tr else w_chat
    else:
        w_call = min(w_trip, w_chat)
    wait_a = wait_b = None
    if arrived and cancelled_by == "DRIVER":
        wait_a = secs(t_arr, t_cancel)                      # free wait from arrival (C2)
        start_b = sched if (sched and t_arr < sched) else t_arr  # free wait from the scheduled time when early (rule text)
        wait_b = secs(start_b, t_cancel)
        assert (wait_a >= FREE_WAIT_SEC) == (wait_b >= FREE_WAIT_SEC), ("free-wait readings disagree", spec["n"])
    facts = {"arrived": arrived, "wait_ok": (wait_a >= FREE_WAIT_SEC) if wait_a is not None else True,
             "msg": msg, "call": call}
    facts.update(spec.get("facts", {}))
    info = dict(case=case, spec=spec, sched=sched, t_arr=t_arr, t_mark=t_mark, t_cancel=t_cancel, cancelled_by=cancelled_by,
                arrived=arrived, stop_dist=stop_dist, radius=radius, zone=zone, in_radius=in_radius, wait_a=wait_a,
                wait_b=wait_b, msg_times=[t for t in msg_times if t < t_cancel], call_times=[t for t in call_times if t < t_cancel],
                vlog_times=[t for t in vlog_times if t < t_cancel], late_msgs=[t for t in msg_times if t >= t_cancel],
                fee=fee, contested=contested, facts=facts, weights={"arrived": w_gps, "wait_ok": min(w_trip, w_gps),
                                                                    "msg": w_chat, "call": w_call},
                w_fare=w_fare, rider_prof=rp, driver_prof=dp, rider_id=rider_id, date=date)
    answer = derive_ns(info)
    return doc, answer


NS_DOMS = {"arrived": [True, False], "wait_ok": [True, False], "msg": [True, False], "call": [True, False]}


def ns_label(sched_case, cancelled_by, arrived, wait_ok, msg, call):
    if not arrived:
        return "NS24" if sched_case else "UNDET"
    if cancelled_by != "DRIVER":
        return "OTHER"
    if not wait_ok:
        return "NS21"
    if not (msg and call):
        return "NS23"
    return "FEE"


def ns_norm(lbl):
    return {"NS24": "RIDER", "NS21": "RIDER", "NS23": "RIDER", "FEE": "FEE", "UNDET": "UNDET", "OTHER": "OTHER"}[lbl]


def ns_outcomes(info, f):
    keys = list(NS_DOMS)
    vals = [[f[k]] if f[k] is not None else NS_DOMS[k] for k in keys]
    return {ns_norm(ns_label(info["sched"] is not None, info["cancelled_by"], *c)) for c in itertools.product(*vals)}


def derive_ns(info):
    spec, case = info["spec"], info["case"]
    E = lambda tok, k=None: case.eid(tok, k)
    f = info["facts"]
    fraud = fraud_of(info)
    driver_filed = spec["filed_by"] == "DRIVER"
    fee = info["fee"]
    parts = []
    parts.append("Filed by the {0}; SGD {1} no-show/cancellation fee on {2}{3}.".format(
        "driver" if driver_filed else "rider", fee, E("FARE"),
        ", already reversed to the rider on an interim basis (refund_issued_sgd; {0} fee_reversed)".format(E("TRIP")) if driver_filed else ", charged to the rider"))
    if fraud:
        side = "rider" if int(info["rider_prof"].get("fraud_flags") or 0) else "driver"
        parts.append("{0} carries {1}_profile.fraud_flags = {2}: a ruling needs confidence 0.95 (POL-GEN-22, POL-NS-26, v2.1 6.3); the flag decides nothing about this trip (POL-GEN-01).".format(
            E("RPROF") if side == "rider" else E("DPROF"), side, fraud))
    note = spec.get("note")

    def esc(clauses, why):
        parts.append(why)
        if note:
            parts.append(note)
        return {"ruling": "ESCALATE", "amount": None, "dc": None, "referrals": [], "clauses": clause_list(clauses), "parts": parts}

    if spec.get("safety_flag") or spec.get("safety_indicator"):
        return finish(info, esc(["POL-GEN-21", "POL-NS-26"], "Safety: {0}; the record carries a safety indicator ({1}). POL-GEN-21 sends the dispute to human review whatever category was chosen (POL-NS-26 is subject to it); the AI issues no ruling, fault finding or recommendation. Escalate.".format(
            "dispute.safety_flag = true" if spec.get("safety_flag") else "no flag set", spec.get("safety_where", E("CHAT")))))

    sched = info["sched"]
    # arrival narrative
    if sched:
        parts.append("Scheduled pickup {0} ({1} scheduled_at); the driver-no-show deadline is {2} (POL-NS-24, v2.1 2.4).".format(
            hms(sched), E("TRIP"), hms(sched + timedelta(seconds=DRIVER_LATE_SEC))))
    else:
        parts.append("On-demand trip ({0} scheduled_at null).".format(E("TRIP")))
    if f["arrived"] is None:
        parts.append("Arrival cannot be established: {0}.".format(spec.get("arr_unknown_why", "")))
    elif info["arrived"]:
        parts.append("{0} marks arrival at {1}; {2} fixes sit {3:.0f} m from the pickup pin, inside the {4} radius of {5} m, with accuracy within 25 m, so the arrival is corroborated (no_show.json arrival_test).".format(
            E("TRIP"), hms(info["t_mark"]), E("GPS"), info["stop_dist"], info["zone"], info["radius"]))
    else:
        if info["t_mark"]:
            parts.append("{0} marks arrival at {1}, but {2} places the vehicle {3:.0f} m from the pickup pin at that time and up to cancellation, outside the {4} radius of {5} m: the arrival is not corroborated and the driver never reached the pickup (arrival_test).".format(
                E("TRIP"), hms(info["t_mark"]), E("GPS"), info["stop_dist"], info["zone"], info["radius"]))
        else:
            parts.append("{0} has no arrival; {1} places the vehicle {2:.0f} m from the pickup pin at the last fix before cancellation at {3}, outside the {4} m radius: the driver did not reach the pickup.".format(
                E("TRIP"), E("GPS"), info["stop_dist"], hms(info["t_cancel"]), info["radius"]))
    if f["arrived"] and info["arrived"] and info["cancelled_by"] == "DRIVER" and f["wait_ok"] is not None:
        if sched and info["t_arr"] < sched:
            parts.append("The driver arrived before the scheduled time; the free wait is met or missed alike whether it runs from arrival (C2, {0} elapsed) or from the scheduled time ({1} elapsed) (POL-NS-21, v2.1 2.1).".format(
                mmss(info["wait_a"]), mmss(info["wait_b"])))
        else:
            parts.append("Driver cancelled at {0}, {1} after arrival: the 300 s free wait {2} (POL-NS-21, v2.1 2.1).".format(
                hms(info["t_cancel"]), mmss(info["wait_a"]), "had run" if info["wait_a"] >= FREE_WAIT_SEC else "had NOT run"))
    if info["cancelled_by"] == "RIDER":
        parts.append("The rider cancelled at {0} ({1}).".format(hms(info["t_cancel"]), E("TRIP")))
    # contact narrative
    mt, ct, vt = info["msg_times"], info["call_times"], info["vlog_times"]
    if f["msg"] is None:
        parts.append("Whether the driver sent a chat message before cancellation cannot be established: {0}.".format(spec.get("msg_unknown_why", "")))
    else:
        if mt:
            parts.append("{0} shows {1} driver chat message(s) before cancellation (first at {2}).".format(E("CHAT"), len(mt), hms(mt[0])))
        else:
            parts.append("{0} shows no driver chat message before cancellation{1}.".format(
                E("CHAT"), spec.get("msg_none_extra", "")))
    if f["call"] is None:
        parts.append("Whether the driver placed a call before cancellation cannot be established.")
    elif ct or vt:
        where = []
        if ct:
            where.append("{0} in_app_calls placed_by DRIVER at {1}".format(E("TRIP"), ", ".join(hms(t) for t in ct)))
        if vt:
            where.append("a VOICE_CALL_LOG entry in {0} at {1}".format(E("CHAT"), ", ".join(hms(t) for t in vt)))
        parts.append("Driver call(s) before cancellation: {0}; an unanswered call still counts as placed.".format("; ".join(where)))
    else:
        parts.append("No call placed by the driver before cancellation in {0} in_app_calls or as a VOICE_CALL_LOG entry in {1}{2}.".format(
            E("TRIP"), E("CHAT"), spec.get("call_none_extra", "")))
    for extra in spec.get("fact_notes", []):
        parts.append(extra)

    outs = ns_outcomes(info, f)
    if len(outs) > 1 or outs == {"UNDET"}:
        cl = ["POL-GEN-26", "POL-NS-26"]
        if f["arrived"] is None or "UNDET" in outs:
            cl.append("POL-NS-21")
        if f["msg"] is None or f["call"] is None:
            cl.append("POL-NS-23")
        cl.append("POL-GEN-02")
        if fraud:
            cl += ["POL-GEN-22", "POL-GEN-01"]
        return finish(info, esc(cl, "The open fact decides the outcome (the fee stands on one reading and is voided on the other), so the case cannot be decided on this record: escalate under POL-GEN-26 with the open question stated."))
    out = outs.pop()
    assert out in ("RIDER", "FEE"), (case.n, out)
    lbl = ns_label(sched is not None, info["cancelled_by"], *[f[k] for k in NS_DOMS])
    deciding = []
    for k in NS_DOMS:
        if f[k] is None:
            continue
        for alt in NS_DOMS[k]:
            if alt == f[k]:
                continue
            g = dict(f)
            g[k] = alt
            if ns_outcomes(info, g) != {out}:
                deciding.append(k)
                break
    caps = {k: info["weights"][k] for k in deciding}
    caps["fee"] = info["w_fare"]
    cap = min(caps.values())
    if fraud and D(repr(cap)) < CONF_FRAUD:
        low = [k for k, v in caps.items() if v == cap]
        return finish(info, esc(["POL-GEN-22", "POL-NS-26", "POL-GEN-02", "POL-GEN-01"],
                                "On the record the fee would {0}, but the deciding fact rests on an artifact of weight {1} ({2}); POL-GEN-02(2) caps confidence at {1}, below the 0.95 a fraud flag requires (POL-GEN-22, POL-NS-26). The evidence is not unequivocal: escalate.".format(
                                    "stand" if out == "FEE" else "be voided", cap, spec.get("cap_desc", ", ".join(low)))))

    referrals = []
    clauses = []
    goodwill = False
    if lbl == "NS24":
        contact = bool(mt or ct or vt)
        clauses += ["POL-NS-24"]
        parts.append("The driver failed to reach the pickup by the scheduled time + 5 minutes, so the rider is not charged: any fee charged is refunded in full (POL-NS-24, v2.1 2.4).")
        if not contact:
            goodwill = True
            parts.append("The driver also made no contact attempt (no driver message, no driver call), so the rider is due the 5.00 goodwill credit, recorded as a referral (POL-NS-24; POL-GEN-03).")
            referrals.append("POL-NS-24: credit the rider SGD 5.00 goodwill (driver did not reach the pickup by the scheduled time + 5 min and made no contact attempt)")
        else:
            parts.append("The driver did attempt contact, so no goodwill credit is due.")
    elif lbl == "NS21":
        clauses += ["POL-NS-21", "POL-NS-22", "POL-GEN-03"]
        parts.append("A no-show cancellation is open to the driver only after the free wait; cancelling before it, the fee does not stand (POL-NS-21, POL-NS-22, v2.1 2.1-2.2).")
    elif lbl == "NS23":
        clauses += ["POL-NS-23", "POL-GEN-23"]
        missing = "an in-app call" if f["msg"] else "an in-app chat message"
        if not f["msg"] and not f["call"]:
            missing = "both a chat message and a call"
        parts.append("The contact obligation needs a driver chat message AND a driver call before cancelled_at; {0} is missing, so the fee is voided and the rider is not charged (POL-NS-23, v2.1 2.3; precedent 7.3, DISP-2026-0211, POL-GEN-23).".format(missing))
    else:
        clauses += ["POL-NS-22", "POL-NS-21", "POL-NS-23"]
        parts.append("Arrival corroborated, free wait run, chat message and call both before cancellation: the fee stands and goes to the driver, so the ruling is DRIVER_COMPENSATION of the fee charged (POL-NS-22, v2.1 2.2).")
    if fee != NS_FEE:
        clauses.append("POL-NS-22")
        referrals.append("POL-NS-22: fee-amount check - the record charged SGD {0}, not the 5.00 no-show fee".format(fee))
        parts.append("The record charged SGD {0}, not 5.00: the ruling acts on the amount charged and a POL-NS-22 referral is added.".format(fee))
    nsc = info["rider_prof"].get("no_show_cancellations_30d")
    if nsc is not None:
        if out == "FEE":
            assert nsc >= 3 or nsc <= 1, ("NS-25 count ambiguous", case.n)
            flag = nsc >= 3
            parts.append("{0} no_show_cancellations_30d = {1}; counting this trip, whose fee stands, the 30-day count is {2} 3 (POL-NS-25, v2.1 2.5).".format(
                E("RPROF"), nsc, "at least" if flag else "below"))
        else:
            assert nsc >= 4 or nsc <= 2, ("NS-25 count ambiguous", case.n)
            flag = nsc >= 4
            parts.append("{0} no_show_cancellations_30d = {1}; this trip's fee does not stand, so it is not counted, and the count is {2} 3 (POL-NS-25, v2.1 2.5).".format(
                E("RPROF"), nsc, "at least" if flag else "below"))
        if flag:
            clauses += ["POL-NS-25", "POL-GEN-01"]
            referrals.append("POL-NS-25: flag rider account {0} for Trust & Safety review (3 or more no-show cancellations in 30 days); the ruling on this trip is unchanged".format(info["rider_id"]))
    if cap < 1.0:
        clauses.append("POL-GEN-02")
    if fraud:
        clauses += ["POL-GEN-22", "POL-NS-26", "POL-GEN-01"]
        parts.append("Every deciding artifact is COMPLETE (cap {0}), so the 0.95 confidence the fraud flag requires is reachable and the ruling stands (POL-NS-26).".format(cap))
    else:
        parts.append("The AI ruling on a no-show is final (POL-NS-26, v2.1 6.2); confidence cap {0}.".format(cap))
    clauses.append("POL-NS-26")
    if spec.get("context_cited"):
        clauses.append("POL-GEN-01")
    if note:
        parts.append(note)
    if out == "FEE":
        return finish(info, {"ruling": "DRIVER_COMPENSATION", "amount": fee, "dc": fee, "referrals": referrals,
                             "clauses": clause_list(clauses), "parts": parts})
    if driver_filed:
        clauses += ["POL-NS-22", "POL-GEN-03"]
        parts.append("The fee does not stand and has already been returned to the rider, so the driver's claim is not supported and the present state stands: NO_ACTION, party-relative (POL-GEN-03).")
        return finish(info, {"ruling": "NO_ACTION", "amount": None, "dc": None, "referrals": referrals,
                             "clauses": clause_list(clauses), "parts": parts})
    parts.append("FULL_REFUND of the SGD {0} contested, with no driver compensation.".format(info["contested"]))
    return finish(info, {"ruling": "FULL_REFUND", "amount": info["contested"], "dc": None, "referrals": referrals,
                         "clauses": clause_list(clauses), "parts": parts})


# ================================================================ set writer
def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def build_set(setname, specs, out_dir, canary, readme):
    cases_dir = os.path.join(out_dir, "cases")
    ans_dir = os.path.join(out_dir, "answers")
    os.makedirs(cases_dir, exist_ok=True)
    os.makedirs(ans_dir, exist_ok=True)
    key, index = [], []
    seen = set()
    for spec in specs:
        assert spec["n"] not in seen
        seen.add(spec["n"])
        doc, ans = (build_rd if spec["cat"] == "RD" else build_ns)(setname, spec)
        raw = dump(doc)
        check_text("case {0}".format(spec["n"]), raw)
        fn = "case-{0:05d}.json".format(spec["n"])
        with open(os.path.join(cases_dir, fn), "w", encoding="utf-8") as fh:
            fh.write(raw)
        key.append(ans)
        index.append({"case_no": spec["n"], "dispute_id": doc["dispute"]["dispute_id"], "trip_id": doc["dispute"]["trip_id"],
                      "category": doc["dispute"]["category"], "file": fn, "sha256": sha256_file(os.path.join(cases_dir, fn))})
    key.sort(key=lambda r: r["case_no"])
    index.sort(key=lambda r: r["case_no"])
    raw_index = dump(index)
    check_text("index.json", raw_index)
    with open(os.path.join(cases_dir, "index.json"), "w", encoding="utf-8") as fh:
        fh.write(raw_index)
    with open(os.path.join(cases_dir, "CANARY.txt"), "w", encoding="utf-8") as fh:
        fh.write(canary + "\n")
    with open(os.path.join(cases_dir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(readme)
    raw_key = dump(key)
    for ch in raw_key:
        if ord(ch) > 126 and ch != "\n":
            raise ValueError("non-ASCII in key")
    with open(os.path.join(ans_dir, "ground_truth.json"), "w", encoding="utf-8") as fh:
        fh.write(raw_key)
    return key, index
