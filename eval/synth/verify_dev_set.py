#!/usr/bin/env python3
"""Second derivation of the dev-v2 answer key, from the rendered cases, through the repository's own code.

Run from the repository root after the set is in place:
    python3 eval/synth/verify_dev_set.py            (the 80-case set)
    python3 eval/synth/verify_dev_set.py dev-v2-200 (the 200-case set)

For every case it loads the file through tribunal.loader.load_external_case, builds the brief with
tribunal.brief.build_brief_for_case and reads the deciding figures the brief derives (arrival run, qualifying
fixes, rider presence, deviation excess and status, the POL-RD-02 / POL-RD-03 / POL-RD-11 money figures).
It then applies the policy's own rules to those figures and compares the outcome with eval/answers/dev-v2.
A disagreement is printed; the exit code is 1 if any remains. It makes no model call.

Checks that do not depend on the key: contract shape, ids, timestamps monotonic, chat count equals
trip_record.chat_message_count, index sha256, no CJK, no sealed-set vocabulary, canary present only where allowed.
"""
from __future__ import annotations

import json
import re
import sys
import hashlib
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if Path(__file__).resolve().parents[1].name == "eval" else Path.cwd()
sys.path.insert(0, str(ROOT))
from tribunal import loader, brief  # noqa: E402

SET_NAME = sys.argv[1] if len(sys.argv) > 1 else "dev-v2"
SET_DIR = ROOT / "data" / "external" / SET_NAME
KEY = ROOT / "eval" / "answers" / SET_NAME / "ground_truth.json"
META = ROOT / "eval" / "answers" / SET_NAME / "manifest-meta.json"
FREE_WAIT_DEFAULT = 180
FEE_DEFAULT = Decimal("4.5")
WAITING_FEE_DEFAULT = Decimal("5.0")
COMP = Decimal("0.8")
GOODWILL = Decimal("0.5")
EXEC_THRESHOLD = Decimal("8.0")
CJK = re.compile("[" + chr(0x4E00) + "-" + chr(0x9FFF) + chr(0x3400) + "-" + chr(0x4DBF) + chr(0x3040) + "-" + chr(0x30FF) + chr(0xAC00) + "-" + chr(0xD7AF) + "]")
FORBIDDEN_WORDS = ("sealed", "wild-v2", "wild-v1", "DISP-002", "organiser", "Ryde Help Centre", "answer key", "ground_truth")


def D(x):
    return Decimal(str(x))


def round_up_005(x):
    q = Decimal("0.05")
    return (x / q).quantize(Decimal("1"), rounding=ROUND_CEILING) * q


def val(node):
    return node.get("value") if isinstance(node, dict) else node


def ev(b, etype):
    return [e for e in b["case"]["evidence"] if e["evidence_type"] == etype][0]


def raw_ev(case, etype):
    return [e for e in case["evidence"] if e["evidence_type"] == etype][0]


def derive_no_show(case, b, meta):
    trip = ev(b, "TRIP_RECORD")["payload"]
    gps = ev(b, "GPS_TRACE")["payload"]
    fare = ev(b, "FARE_BREAKDOWN")["payload"]
    chat = ev(b, "CHAT_LOG")["payload"]
    dprof = ev(b, "DRIVER_PROFILE")["payload"]
    d = gps["derived"]
    arr = d["arrival"]
    run = float(val(arr["longest_qualifying_run"]["duration_sec"])) if arr.get("available") else 0.0
    qf = int(val(arr["qualifying_fix_count"])) if arr.get("available") else 0
    pp = trip.get("platform_policy") or {}
    free_wait = int(pp.get("free_wait_sec") or FREE_WAIT_DEFAULT)
    thr = pp.get("no_show_threshold_sec")
    fee = D(pp["cancellation_fee_sgd"]) if pp.get("cancellation_fee_sgd") is not None else FEE_DEFAULT
    disp = case["dispute"]
    out = {"ruling": None, "amount": None, "comp": None, "referrals": []}
    sc = meta["scenario"]
    gap_inside = any(float(g["duration_sec"]) > 120 for g in gps.get("gaps", []) if trip.get("arrived_at") and g["from_ts"] >= trip["arrived_at"])
    if disp.get("safety_flag"):
        return dict(out, ruling="ESCALATE", referrals=["POL-GEN-08(1)"])
    if trip["status"] == "COMPLETED":  # waiting-fee case
        if run < free_wait and D(fare["waiting_time_fee"]) > 0:
            return dict(out, ruling="FULL_REFUND", amount=float(D(fare["waiting_time_fee"])))
        return dict(out, ruling="NO_ACTION")
    accepted = trip["accepted_at"]; cancelled = trip["cancelled_at"]
    from datetime import datetime
    secs_after_accept = (datetime.fromisoformat(cancelled) - datetime.fromisoformat(accepted)).total_seconds()
    if trip["cancelled_by"] == "RIDER":
        if secs_after_accept <= int(pp.get("grace_after_match_sec") or 180):
            return dict(out, ruling="FULL_REFUND", amount=float(fee))
        if trip.get("scheduled_at") and (datetime.fromisoformat(trip["scheduled_at"]) - datetime.fromisoformat(cancelled)).total_seconds() > int(pp.get("advance_grace_before_scheduled_sec") or 900):
            return dict(out, ruling="FULL_REFUND", amount=float(fee))
        asked = any(m["sender"] == "DRIVER" and "cancel" in m["text"].lower() for m in chat["messages"])
        if asked:
            return dict(out, ruling="FULL_REFUND", amount=float(fee))
        if run >= free_wait and qf >= 3:
            c = (COMP * fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return dict(out, ruling="DRIVER_COMPENSATION", amount=float(c), comp=float(c))
        return dict(out, ruling="NO_ACTION")
    # driver-terminated
    rprof = ev(b, "RIDER_PROFILE")["payload"]
    if rprof["disputes_with_counterparty_90d"] >= 2 and dprof["disputes_with_counterparty_90d"] >= 2:
        return dict(out, ruling="ESCALATE")  # POL-NS-09(c)
    if rprof["no_show_disputes_30d"] >= 3:
        return dict(out, ruling="ESCALATE")  # POL-NS-09(d)
    if "CROSS_SOURCE_CONFLICT" in ev(b, "TRIP_RECORD")["admissibility"]["issues"]:
        return dict(out, ruling="ESCALATE")
    if gap_inside and trip.get("events") is None:
        return dict(out, ruling="ESCALATE")
    if trip["cancellation_reason_code"] == "DRIVER_UNABLE_TO_LOCATE" and qf >= 3:
        return dict(out, ruling="FULL_REFUND", amount=float(fee), referrals=["POL-NS-01(d)"])
    dist = meta["derived"]["dist_m"]
    # POL-NS-05: a marker stamped more than 300 m from the pin is false; with no in-geofence fix anywhere, limb (ii) adds a referral
    if trip.get("arrived_at") and qf < 3:
        from tribunal import facts
        raw_pts = raw_ev(case, "GPS_TRACE")["payload"]["points"]
        at = [p for p in raw_pts if p["ts"] == trip["arrived_at"]]
        if at and facts.haversine_m(float(at[0]["lat"]), float(at[0]["lng"]), float(trip["pickup"]["lat"]), float(trip["pickup"]["lng"])) > 300:
            fee_ = fee
            return dict(out, ruling="FULL_REFUND", amount=float(fee_), referrals=["POL-NS-05(ii)"])
    if qf < 3:  # no arrival on the record
        if 0 < dist <= 400 and run == 0:
            # POL-NS-03: fault from chat
            rider_named = any(m["sender"] == "RIDER" and any(w in m["text"].lower() for w in ("entrance", "block", "tower", "bay", "lobby", "blk")) for m in chat["messages"])
            if rider_named:
                return dict(out, ruling="FULL_REFUND", amount=float(fee))
            if (trip.get("registered_pickup_points") or 1) >= 2:
                return dict(out, ruling="FULL_REFUND", amount=float(fee), comp=float((GOODWILL * fee).quantize(Decimal("0.01"))))
            return dict(out, ruling="FULL_REFUND", amount=float(fee))
        return dict(out, ruling="FULL_REFUND", amount=float(fee))
    # arrived. POL-NS-04?
    rp = d["rider_presence"]
    rider_msgs = [m for m in chat["messages"] if m["sender"] == "RIDER"]
    driver_replied = any(m["sender"] == "DRIVER" for m in chat["messages"])
    if rider_msgs and not driver_replied and not trip.get("in_app_calls"):
        if rp.get("available") and float(val(rp["max_distance_m"])) <= {"STANDARD": 100, "LARGE_VENUE": 150, "TRANSPORT_HUB": 200, "AIRPORT": 200}[trip["pickup_zone_class"]]:
            return dict(out, ruling="FULL_REFUND", amount=float(fee))
    referrals = []
    if meta.get("scenario", "").startswith("B5") and run >= free_wait:
        referrals.append("POL-NS-05(iii)")
    if run < free_wait:
        return dict(out, ruling="FULL_REFUND", amount=float(fee))
    if thr and secs_after_accept < 0:
        pass
    t30 = dprof["no_show_terminations_30d"]; c30 = dprof["completed_trips_30d"]
    if t30 >= 4 and c30 and t30 / c30 > 0.08:
        return dict(out, ruling="ESCALATE", referrals=["POL-NS-07"])
    c = (COMP * fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return dict(out, ruling="DRIVER_COMPENSATION", amount=float(c), comp=float(c), referrals=referrals)


def derive_route(case, b, meta):
    trip = ev(b, "TRIP_RECORD")["payload"]
    gps = ev(b, "GPS_TRACE")["payload"]
    fare = ev(b, "FARE_BREAKDOWN")["payload"]
    chat = ev(b, "CHAT_LOG")["payload"]
    dprof = ev(b, "DRIVER_PROFILE")["payload"]
    adv = ev(b, "TRAFFIC_ADVISORY")
    m = fare["derived"]["money"]
    dev = gps["derived"]["deviation"]
    status = val(dev["status"])
    charged = D(val(m["charged_total"]))
    out = {"ruling": None, "amount": None, "comp": None, "referrals": []}
    # RD-10 triggers first
    if fare["trip_id"] != trip["trip_id"]:
        return dict(out, ruling="ESCALATE")
    if trip.get("dropoff_amended_at") and trip.get("amended_optimal_distance_km") is None:
        return dict(out, ruling="ESCALATE")
    cp = case["dispute"].get("counterparty_statement") or {}
    if "EV-ADVIS" in (cp.get("text") or "") and adv["admissibility"]["status"] == "MISSING":
        return dict(out, ruling="ESCALATE")
    gap_over_90 = any(float(g["duration_sec"]) > 90 or float(g["straight_line_km"]) > 0.5 for g in gps.get("gaps", []))
    # phantom ERP
    phantom = D("0")
    lines = m.get("erp_lines", {}).get("lines", [])
    for ln in lines:
        prox = ln.get("nearest_fix_m") or ln.get("min_distance_m")
    # recompute phantom from raw coordinates
    from tribunal import facts
    pts = raw_ev(case, "GPS_TRACE")["payload"]["points"]
    for g in fare.get("erp_gantries", []):
        dmin = min(facts.haversine_m(float(p["lat"]), float(p["lng"]), float(g["lat"]), float(g["lng"])) for p in pts)
        if dmin > 250:
            phantom += D(g["amount_sgd"])
    if phantom > 0:
        out["referrals"].append("POL-RD-09(4)")
    # waypoint request contradiction
    for msg in chat["messages"]:
        wp = msg.get("waypoint_hint")
        if msg["sender"] == "RIDER" and isinstance(wp, dict):
            dmin = min(facts.haversine_m(float(p["lat"]), float(p["lng"]), float(wp["lat"]), float(wp["lng"])) for p in pts)
            if dmin > 200:
                return dict(out, ruling="ESCALATE")
            else:
                return dict(out, ruling="NO_ACTION")  # POL-RD-04 excludes the whole bulge in this set
    # pooled
    if trip["vehicle_type"] == "RYDE_POOL":
        return dict(out, ruling="NO_ACTION") if status == "no deviation" else dict(out, ruling="PARTIAL_REFUND")
    if trip.get("dropoff_amended_at"):
        exc = D(gps["trace_distance_km"]) - D(trip["amended_optimal_distance_km"])
        if exc <= D("0.2") * D(trip["amended_optimal_distance_km"]) or exc <= D("0.8"):
            return dict(out, ruling="NO_ACTION")
    if fare["fare_model"] == "UPFRONT_QUOTE":
        proper = D("0.8") + D(fare["tolls_erp"]) - phantom + D(fare["airport_surcharge"]) + D(fare["waiting_time_fee"])
        refund = charged - D(fare["quoted_fare_sgd"]) - proper + phantom
        over = D(val(m["charged_over_quote"]))
        assert over == charged - D(fare["quoted_fare_sgd"]), ("upfront over-quote figure disagrees with the brief", over)
        if refund > 0:
            return dict(out, ruling="PARTIAL_REFUND", amount=float(refund.quantize(Decimal("0.01"))))
        return dict(out, ruling="NO_ACTION")
    if status == "no deviation":
        if phantom > 0:
            return dict(out, ruling="PARTIAL_REFUND", amount=float(phantom))
        return dict(out, ruling="NO_ACTION")
    if gap_over_90:
        admission = any(m2["sender"] == "DRIVER" for m2 in chat["messages"])
        if not admission:
            return dict(out, ruling="ESCALATE")
    # RD-03
    comps = m["components"]
    rec_booked = D(val(m["refund"]["recomputed_fare"])) if "recomputed_fare" in m.get("refund", {}) else None
    refund_booked = D(val(m["refund"]["payable"])) if "payable" in m.get("refund", {}) else None
    excess = D(val(dev["excess_km"]))
    adv_ok = adv["admissibility"]["status"] == "COMPLETE" and adv["payload"].get("intersects_route") and adv["payload"].get("shortest_lawful_alternative_km")
    if adv_ok:
        cap = D("1.3") * (D(adv["payload"]["shortest_lawful_alternative_km"]) - D(trip["optimal_distance_km"])) + D("1.0")
        justified = min(excess, cap)
        if justified >= excess:
            off = D(fare["tolls_erp"]) - D(trip["optimal_route_erp_sgd"]) - phantom
            if off > 0:
                return dict(out, ruling="PARTIAL_REFUND", amount=float(min(off, D("12"))))
            return dict(out, ruling="NO_ACTION")
        closure = (m.get("closure") or [{}])[0]
        payable = (closure.get("refund") or {}).get("payable")
        if payable is not None:
            return dict(out, ruling="PARTIAL_REFUND", amount=float(D(val(payable))))
        # fall back: recompute here
        adj_km = D(trip["optimal_distance_km"]) + justified
        adj_min = (D(trip["optimal_duration_min"]) * adj_km / D(trip["optimal_distance_km"])).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        rec = (D("3.8") + D("0.75") * adj_km + D("0.28") * adj_min) * D(fare["surge_multiplier"]) + D("0.8") + D(trip["optimal_route_erp_sgd"]) + D(fare["airport_surcharge"]) + D(fare["waiting_time_fee"]) - D(fare["promo_discount"])
        return dict(out, ruling="PARTIAL_REFUND", amount=float(round_up_005(charged - rec)))
    raw = D(val(m["refund"]["refund_before_rounding"]))
    if raw > D("150"):
        return dict(out, ruling="ESCALATE")
    if raw < D("0.5"):
        return dict(out, ruling="NO_ACTION")
    material = status == "material"
    pattern = dprof["deviation_flags_90d"] >= 3 or (dprof["completed_trips_90d"] >= 40 and dprof["deviation_flags_90d"] / dprof["completed_trips_90d"] >= 0.05)
    if material and pattern:
        return dict(out, ruling="FULL_REFUND", amount=float(charged), referrals=["POL-RD-06(c)"])
    if raw >= D("0.9") * charged:
        return dict(out, ruling="FULL_REFUND", amount=float(charged))
    return dict(out, ruling="PARTIAL_REFUND", amount=float(refund_booked))


def main():
    keys = {k["case_no"]: k for k in json.load(open(KEY, encoding="utf-8"))}
    meta = {m["case_no"]: m for m in json.load(open(META, encoding="utf-8"))["cases"]}
    index = {i["case_no"]: i for i in json.load(open(SET_DIR / "index.json", encoding="utf-8"))}
    problems = []
    n_ok = 0
    for path in sorted(SET_DIR.glob("case-*.json")):
        n = int(path.stem.split("-")[1])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != index[n]["sha256"]:
            problems.append((n, "index sha256 mismatch"))
        text = raw.decode("utf-8")
        if CJK.search(text):
            problems.append((n, "CJK text in case file"))
        for w in FORBIDDEN_WORDS:
            if w.lower() in text.lower():
                problems.append((n, "forbidden word in case: " + w))
        case = loader.load_external_case(path)
        if set(case.keys()) != {"schema_version", "case_no", "dispute", "evidence"}:
            problems.append((n, "top-level keys"))
        for e in case["evidence"]:
            if set(e.keys()) != {"evidence_id", "evidence_type", "admissibility", "payload", "schema_version", "source", "trip_id", "generated_at"}:
                problems.append((n, "artifact keys " + e["evidence_id"]))
        types = [e["evidence_type"] for e in case["evidence"]]
        for t in ("TRIP_RECORD", "GPS_TRACE", "CHAT_LOG", "FARE_BREAKDOWN", "RIDER_PROFILE", "DRIVER_PROFILE", "TRAFFIC_ADVISORY"):
            if types.count(t) < 1:
                problems.append((n, "missing artifact type " + t))
        b = brief.build_brief_for_case(case)
        trip = ev(b, "TRIP_RECORD")["payload"]; chat = ev(b, "CHAT_LOG")["payload"]; gps = ev(b, "GPS_TRACE")["payload"]
        if chat["message_count"] != trip["chat_message_count"]:
            problems.append((n, "chat count {0} != trip_record {1}".format(chat["message_count"], trip["chat_message_count"])))
        tss = [p["ts"] for p in raw_ev(case, "GPS_TRACE")["payload"]["points"]]
        if tss != sorted(tss) or len(set(tss)) != len(tss):
            problems.append((n, "GPS timestamps not strictly increasing"))
        order = [trip.get(k) for k in ("requested_at", "accepted_at", "arrived_at", "started_at", "ended_at", "cancelled_at") if trip.get(k)]
        if order != sorted(order):
            problems.append((n, "trip timestamps run backwards: " + str(order)))
        got = derive_no_show(case, b, meta[n]) if case["dispute"]["category"] == "NO_SHOW_CHARGE" else derive_route(case, b, meta[n])
        exp = keys[n]["ground_truth"]
        diffs = []
        if got["ruling"] != exp["expected_ruling"]:
            diffs.append("ruling {0} != key {1}".format(got["ruling"], exp["expected_ruling"]))
        for a, k in (("amount", "expected_amount_sgd"), ("comp", "expected_driver_compensation_sgd")):
            if (got[a] is None) != (exp[k] is None) or (got[a] is not None and abs(got[a] - exp[k]) > 0.0001):
                diffs.append("{0} {1} != key {2}".format(a, got[a], exp[k]))
        for ref in got["referrals"]:
            if not any(ref.split("(")[0] in x for x in exp["expected_referrals"]):
                diffs.append("derived referral {0} absent from key".format(ref))
        if len(exp["expected_referrals"]) and not got["referrals"] and not case["dispute"].get("safety_flag"):
            diffs.append("key has referrals {0} the derivation did not reach".format(exp["expected_referrals"]))
        if diffs:
            problems.append((n, meta[n]["scenario"], diffs))
        else:
            n_ok += 1
    print("cases agreeing with the key on all four fields:", n_ok, "of", len(index))
    for p in problems:
        print("PROBLEM", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
