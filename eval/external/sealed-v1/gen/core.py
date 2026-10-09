"""Tribunal sealed-set generator — core helpers.
Schema 1.2.0 invariants are enforced here so every emitted case passes validate_dataset.py.
"""
import math, json, hashlib, random
from datetime import datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8))
SCHEMA_VERSION = "1.2.0"
ASSESSOR = "prepass-1.0.0"

# ---------- time ----------
def ts(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=SGT)

def fmt(dt):
    return None if dt is None else dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")

# ---------- money ----------
def m2(x):
    return float(round(x + 1e-9, 2))

def round_up_05(x):
    return m2(math.ceil(x * 20 - 1e-9) / 20)

# ---------- geo ----------
def haversine_km(a, b):
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

def bearing(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    y = math.sin(lo2-lo1)*math.cos(la2)
    x = math.cos(la1)*math.sin(la2) - math.sin(la1)*math.cos(la2)*math.cos(lo2-lo1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def polyline_km(wps):
    return sum(haversine_km(wps[i], wps[i+1]) for i in range(len(wps)-1))

def fit_path(wps, target_km):
    """Scale waypoint offsets from wps[0] so polyline length == target_km (keeps shape)."""
    d = polyline_km(wps)
    s = target_km / d
    o = wps[0]
    return [(o[0] + (p[0]-o[0])*s, o[1] + (p[1]-o[1])*s) for p in wps]

def interp_path(wps, t0, t1, cadence=10, rng=None, acc=(4.0, 12.0), jitter_m=2.5):
    """Constant-speed traversal of polyline between t0 and t1 at `cadence` seconds."""
    rng = rng or random.Random(0)
    total = polyline_km(wps)
    n = int((t1 - t0).total_seconds() // cadence)
    seg = [(wps[i], wps[i+1], haversine_km(wps[i], wps[i+1])) for i in range(len(wps)-1)]
    pts = []
    for k in range(n + 1):
        frac = k / n if n else 0.0
        dist = frac * total
        acc_d = 0.0
        for a, b, L in seg:
            if dist <= acc_d + L or (a, b, L) is seg[-1]:
                f = 0.0 if L == 0 else min(1.0, max(0.0, (dist - acc_d) / L))
                lat = a[0] + (b[0]-a[0])*f
                lng = a[1] + (b[1]-a[1])*f
                break
            acc_d += L
        # jitter
        lat += rng.uniform(-jitter_m, jitter_m) / 111_000
        lng += rng.uniform(-jitter_m, jitter_m) / (111_000 * math.cos(math.radians(lat)))
        pts.append({"lat": round(lat, 6), "lng": round(lng, 6),
                    "ts": t0 + timedelta(seconds=k*cadence),
                    "accuracy_m": round(rng.uniform(*acc), 1)})
    # speed & heading from consecutive
    for i, p in enumerate(pts):
        if i == 0:
            p["speed_kph"] = 0.0 if n == 0 else round(haversine_km((p["lat"],p["lng"]),(pts[1]["lat"],pts[1]["lng"]))/(cadence/3600), 1)
            p["heading_deg"] = None if n == 0 else round(bearing((p["lat"],p["lng"]),(pts[1]["lat"],pts[1]["lng"])), 1)
        else:
            q = pts[i-1]
            dk = haversine_km((q["lat"],q["lng"]),(p["lat"],p["lng"]))
            p["speed_kph"] = round(dk/(cadence/3600), 1)
            p["heading_deg"] = round(bearing((q["lat"],q["lng"]),(p["lat"],p["lng"])), 1) if dk > 0.003 else None
    return pts

def dwell_points(center, t0, t1, cadence=10, rng=None, acc=(5.0, 14.0), jitter_m=3.0, venue_id=None):
    rng = rng or random.Random(1)
    n = int((t1 - t0).total_seconds() // cadence)
    out = []
    for k in range(n + 1):
        lat = center[0] + rng.uniform(-jitter_m, jitter_m)/111_000
        lng = center[1] + rng.uniform(-jitter_m, jitter_m)/(111_000*math.cos(math.radians(center[0])))
        p = {"lat": round(lat,6), "lng": round(lng,6), "ts": t0 + timedelta(seconds=k*cadence),
             "speed_kph": 0.0, "heading_deg": None, "accuracy_m": round(rng.uniform(*acc),1)}
        if venue_id: p["venue_id"] = venue_id
        out.append(p)
    return out

def serialize_points(pts):
    out = []
    for p in pts:
        q = {"lat": p["lat"], "lng": p["lng"], "ts": fmt(p["ts"]), "speed_kph": p["speed_kph"]}
        if "heading_deg" in p: q["heading_deg"] = p["heading_deg"]
        if "accuracy_m" in p: q["accuracy_m"] = p["accuracy_m"]
        if p.get("venue_id"): q["venue_id"] = p["venue_id"]
        out.append(q)
    return out

# ---------- gps_trace payload (derived fields per SCHEMA §5.2) ----------
def build_gps(trip_id, pts, anchor, terminal, rider_track=None, gap_threshold=30):
    pts = sorted(pts, key=lambda p: p["ts"])
    gaps = []
    ivals = []
    for i in range(1, len(pts)):
        dt = (pts[i]["ts"] - pts[i-1]["ts"]).total_seconds()
        ivals.append(dt)
        if dt > gap_threshold:
            gaps.append({"from_ts": fmt(pts[i-1]["ts"]), "to_ts": fmt(pts[i]["ts"]),
                         "duration_sec": round(dt, 1),
                         "straight_line_km": round(haversine_km((pts[i-1]["lat"],pts[i-1]["lng"]),(pts[i]["lat"],pts[i]["lng"])), 2)})
    active = (terminal - anchor).total_seconds()
    cov = None
    if active > 0 and len(pts) >= 2:
        cov = round(max(0.0, min(100.0, 100.0*(active - sum(g["duration_sec"] for g in gaps))/active)), 1)
    dist = round(sum(haversine_km((pts[i-1]["lat"],pts[i-1]["lng"]),(pts[i]["lat"],pts[i]["lng"])) for i in range(1,len(pts))), 2) if len(pts)>=2 else None
    med = None
    if ivals:
        s = sorted(ivals); k = len(s)//2
        med = round(s[k] if len(s)%2 else (s[k-1]+s[k])/2, 1)
    return {
        "trip_id": trip_id,
        "points": serialize_points(pts),
        "point_count": len(pts),
        "first_fix_at": fmt(pts[0]["ts"]) if pts else None,
        "last_fix_at": fmt(pts[-1]["ts"]) if pts else None,
        "expected_interval_sec": 10.0,
        "sample_interval_sec": med,
        "gaps": gaps,
        "max_gap_sec": (max(g["duration_sec"] for g in gaps) if gaps else 0.0) if len(pts)>=2 else None,
        "coverage_pct": cov,
        "trace_distance_km": dist,
        "rider_track": serialize_points(sorted(rider_track, key=lambda p: p["ts"])) if rider_track else None,
    }, dist, gaps, cov

# ---------- admissibility (SCHEMA §3) ----------
W = {"MISSING_ARTIFACT":0.0,"TRUNCATED_LOG":0.60,"PARTIAL_RECORD":0.75,
     "CLOCK_SKEW":0.70,"TIMESTAMP_INCONSISTENT":0.50,"TIMESTAMP_OUT_OF_RANGE":0.60,"OUT_OF_ORDER_SEQUENCE":0.70,
     "GPS_GAP":0.65,"LOW_SAMPLE_RATE":0.80,"LOW_COVERAGE":0.60,"GPS_DRIFT":0.55,"IMPLAUSIBLE_SPEED":0.55,
     "UNREAD_MESSAGE":0.85,"CONTENT_REDACTED":0.80,"LANGUAGE_AMBIGUITY":0.85,
     "CROSS_SOURCE_CONFLICT":0.40,"FARE_RECOMPUTE_MISMATCH":0.45,"DISTANCE_MISMATCH":0.50,"ADVISORY_UNCORROBORATED":0.35,
     "STALE_SNAPSHOT":0.75,"UNVERIFIED_SOURCE":0.60,"SCHEMA_VERSION_MISMATCH":0.90}
SEV = {"MISSING_ARTIFACT":"BLOCKING",
       "TRUNCATED_LOG":"MAJOR","CLOCK_SKEW":"MAJOR","TIMESTAMP_INCONSISTENT":"MAJOR","TIMESTAMP_OUT_OF_RANGE":"MAJOR",
       "GPS_GAP":"MAJOR","LOW_COVERAGE":"MAJOR","GPS_DRIFT":"MAJOR","IMPLAUSIBLE_SPEED":"MAJOR",
       "CROSS_SOURCE_CONFLICT":"MAJOR","FARE_RECOMPUTE_MISMATCH":"MAJOR","DISTANCE_MISMATCH":"MAJOR","ADVISORY_UNCORROBORATED":"MAJOR","UNVERIFIED_SOURCE":"MAJOR",
       "PARTIAL_RECORD":"MINOR","OUT_OF_ORDER_SEQUENCE":"MINOR","LOW_SAMPLE_RATE":"MINOR","UNREAD_MESSAGE":"MINOR","CONTENT_REDACTED":"MINOR",
       "LANGUAGE_AMBIGUITY":"MINOR","STALE_SNAPSHOT":"MINOR","SCHEMA_VERSION_MISMATCH":"MINOR"}
SEV_RANK = {"BLOCKING":0,"MAJOR":1,"MINOR":2}

def adm(status, notes, assessed_at, details=None):
    """details: list of {code, detail, related_evidence_ids?}. Computes issues order + weight."""
    details = details or []
    codes = sorted({d["code"] for d in details}, key=lambda c: (SEV_RANK[SEV[c]], c))
    if status == "MISSING":
        assert codes == ["MISSING_ARTIFACT"], codes
        w = 0.0
    elif status == "COMPLETE":
        assert not codes
        w = 1.0
    else:
        assert codes and "MISSING_ARTIFACT" not in codes
        prod = 1.0
        for c in codes: prod *= W[c]
        w = max(0.25, round(prod, 2))
    out = {"status": status, "issues": codes}
    if details:
        dd = []
        for d in sorted(details, key=lambda d: (SEV_RANK[SEV[d["code"]]], d["code"])):
            e = {"code": d["code"], "severity": SEV[d["code"]], "detail": d["detail"]}
            if "related_evidence_ids" in d: e["related_evidence_ids"] = d["related_evidence_ids"]
            if "clock_skew_sec" in d: e["clock_skew_sec"] = d["clock_skew_sec"]
            dd.append(e)
        out["issue_details"] = dd
    out["weight_multiplier"] = w
    out["notes"] = notes
    out["assessed_at"] = fmt(assessed_at)
    out["assessor_version"] = ASSESSOR
    return out

def envelope(ev_id, ev_type, trip_id, source, generated_at, admissibility, payload):
    return {"evidence_id": ev_id, "evidence_type": ev_type, "trip_id": trip_id, "source": source,
            "generated_at": fmt(generated_at), "schema_version": SCHEMA_VERSION,
            "admissibility": admissibility, "payload": payload}

# ---------- fares ----------
RD_BASE, RD_KM, RD_MIN, RD_PLAT = 3.80, 0.75, 0.28, 0.80

def fare_metered(trip_id, dist_km, time_min, surge=1.0, gantries=None, platform=RD_PLAT, promo=0.0,
                 waiting=0.0, airport=0.0, charged_at=None, rate_card="RC-SG-2026Q3-RYDEX"):
    gantries = gantries or []
    d = m2(dist_km*RD_KM); t = m2(time_min*RD_MIN)
    sub = RD_BASE + d + t
    surge_amt = m2(sub*(surge-1.0))
    tolls = m2(sum(g["amount_sgd"] for g in gantries))
    total = m2(RD_BASE + d + t + surge_amt + tolls + airport + platform + 0.0 + waiting - promo)
    return {"trip_id": trip_id, "currency": "SGD", "fare_model": "METERED", "quoted_fare_sgd": None,
            "base_fare": RD_BASE, "distance_fare": d, "time_fare": t,
            "distance_charged_km": round(dist_km,2), "time_charged_min": round(time_min,1),
            "per_km_rate_sgd": RD_KM, "per_min_rate_sgd": RD_MIN,
            "surge_multiplier": surge, "surge_amount": surge_amt, "tolls_erp": tolls,
            "erp_gantries": gantries, "airport_surcharge": airport, "platform_fee": platform,
            "promo_discount": promo, "cancellation_fee": 0.0, "waiting_time_fee": waiting,
            "total_charged": total, "payment_status": "CHARGED", "refund_issued_sgd": 0.0,
            "rate_card_id": rate_card, "charged_at": fmt(charged_at)}

def recomputed_fare(opt_km, opt_min, surge, on_route_erp, platform=RD_PLAT, airport_ok=0.0, waiting=0.0, promo=0.0):
    return (RD_BASE + RD_KM*opt_km + RD_MIN*opt_min)*surge + platform + on_route_erp + airport_ok + waiting - promo

def fare_cancel(trip_id, fee, charged_at, tier_card, status="CHARGED", refunded=0.0):
    return {"trip_id": trip_id, "currency": "SGD", "fare_model": "METERED", "quoted_fare_sgd": None,
            "base_fare": 0.0, "distance_fare": 0.0, "time_fare": 0.0, "distance_charged_km": None,
            "time_charged_min": None, "per_km_rate_sgd": None, "per_min_rate_sgd": None,
            "surge_multiplier": 1.0, "surge_amount": 0.0, "tolls_erp": 0.0, "erp_gantries": [],
            "airport_surcharge": 0.0, "platform_fee": 0.0, "promo_discount": 0.0,
            "cancellation_fee": m2(fee), "waiting_time_fee": 0.0, "total_charged": m2(fee),
            "payment_status": status, "refund_issued_sgd": m2(refunded),
            "rate_card_id": tier_card, "charged_at": fmt(charged_at)}

NS_ZONE_FEE = {"STANDARD":4.0,"LARGE_VENUE":4.0,"TRANSPORT_HUB":6.0,"AIRPORT":6.0}
NS_TIER_FEE = {"RYDE_X":4.0,"RYDE_POOL":4.0,"RYDE_TAXI":4.0,"RYDE_PLUS":6.0,"RYDE_XL":8.0}
NS_MIN_DWELL = {"STANDARD":300,"LARGE_VENUE":300,"TRANSPORT_HUB":300,"AIRPORT":480}
NS_ARR_R = {"STANDARD":50,"LARGE_VENUE":120,"TRANSPORT_HUB":150,"AIRPORT":150}

def ns_fee(zone, tier):
    return max(NS_ZONE_FEE[zone], NS_TIER_FEE[tier])

# ---------- profiles ----------
def rider_profile(pid, snap, age, trips, rating, filed, upheld, cancel_rate, ns_flags,
                  dev60=0, dev60_sub=0, ns30=0, cp90=0):
    return {"party_id": pid, "party_role": "RIDER", "snapshot_at": fmt(snap), "account_age_days": age,
            "lifetime_trips": trips, "rating": rating, "prior_disputes_filed": filed,
            "prior_disputes_upheld": upheld, "cancellation_rate": cancel_rate, "prior_no_show_flags": ns_flags,
            "deviation_claims_60d": dev60, "deviation_claims_60d_substantiated": dev60_sub,
            "no_show_disputes_30d": ns30, "disputes_with_counterparty_90d": cp90}

def driver_profile(pid, snap, age, trips, rating, filed, upheld, cancel_rate, ns_flags, dev_flags,
                   accept, vehicle, region, dev90=0, trips90=200, ns30=0, trips30=70, cp90=0):
    return {"party_id": pid, "party_role": "DRIVER", "snapshot_at": fmt(snap), "account_age_days": age,
            "lifetime_trips": trips, "rating": rating, "prior_disputes_filed": filed,
            "prior_disputes_upheld": upheld, "cancellation_rate": cancel_rate, "prior_no_show_flags": ns_flags,
            "prior_deviation_flags": dev_flags, "acceptance_rate": accept, "vehicle_type": vehicle,
            "active_region": region, "deviation_flags_90d": dev90, "completed_trips_90d": trips90,
            "no_show_terminations_30d": ns30, "completed_trips_30d": trips30, "disputes_with_counterparty_90d": cp90}

# ---------- chat ----------
def msg(case, k, sender, text, sent, read=None, delivered=None, channel="IN_APP", lang="en", wp=None):
    return {"msg_id": f"MSG-{case:05d}-{k:03d}", "sender": sender, "text": text, "sent_at": fmt(sent),
            "read_at": fmt(read), "delivered_at": fmt(delivered if delivered is not None else sent + timedelta(seconds=1)),
            "channel": channel, "language": lang, "redacted": False, "waypoint_hint": wp}

def chat(trip_id, messages):
    return {"trip_id": trip_id, "messages": messages, "message_count": len(messages),
            "first_message_at": messages[0]["sent_at"] if messages else None,
            "last_message_at": messages[-1]["sent_at"] if messages else None, "truncated": False}

def geo(label, lat, lng, venue=None):
    return {"label": label, "lat": lat, "lng": lng, "venue_id": venue}

# ---------- trip ----------
def trip_rd(case, rider, driver, req, acc, arr, start, end, pickup, dropoff, opt_km, opt_min,
            actual_km, vehicle="RYDE_X", src="routing-engine-v3.2", chat_count=0, erp_opt=0.0,
            drop_amended=None, orig_drop=None, amend_km=None, amend_min=None, solo_km=None):
    tid = f"TRP-{case:05d}"
    dur = round((end-start).total_seconds()/60, 1)
    return {"trip_id": tid, "rider_id": rider, "driver_id": driver, "requested_at": fmt(req), "accepted_at": fmt(acc),
            "arrived_at": fmt(arr), "started_at": fmt(start), "ended_at": fmt(end), "cancelled_at": None,
            "status": "COMPLETED", "cancelled_by": None, "cancellation_reason_code": None,
            "pickup": pickup, "dropoff": dropoff, "optimal_distance_km": opt_km, "optimal_duration_min": opt_min,
            "actual_distance_km": actual_km, "actual_duration_min": dur, "vehicle_type": vehicle,
            "optimal_route_source": src, "deviation_pct": round((actual_km-opt_km)/opt_km*100, 1),
            "wait_time_min": round((start-arr).total_seconds()/60, 1), "time_to_arrival_min": round((arr-acc).total_seconds()/60, 1),
            "pickup_zone_class": None, "registered_pickup_points": None, "in_app_calls": [],
            "pickup_amended_at": None, "dropoff_amended_at": fmt(drop_amended), "original_pickup": None,
            "original_dropoff": orig_drop, "optimal_route_erp_sgd": erp_opt,
            "amended_optimal_distance_km": amend_km, "amended_optimal_duration_min": amend_min,
            "solo_optimal_distance_km": solo_km, "chat_message_count": chat_count}

def trip_ns(case, rider, driver, req, acc, arr, cancel, pickup, dropoff, opt_km, opt_min, zone, tier,
            reason="RIDER_NO_SHOW", cancelled_by="DRIVER", reg_points=1, calls=None, chat_count=0):
    tid = f"TRP-{case:05d}"
    st = {"DRIVER":"CANCELLED_BY_DRIVER","RIDER":"CANCELLED_BY_RIDER","SYSTEM":"CANCELLED_BY_SYSTEM"}[cancelled_by]
    return {"trip_id": tid, "rider_id": rider, "driver_id": driver, "requested_at": fmt(req), "accepted_at": fmt(acc),
            "arrived_at": fmt(arr), "started_at": None, "ended_at": None, "cancelled_at": fmt(cancel),
            "status": st, "cancelled_by": cancelled_by, "cancellation_reason_code": reason,
            "pickup": pickup, "dropoff": dropoff, "optimal_distance_km": opt_km, "optimal_duration_min": opt_min,
            "actual_distance_km": None, "actual_duration_min": None, "vehicle_type": tier,
            "optimal_route_source": "routing-engine-v3.2 (LTA traffic snapshot " + req.strftime("%H:%M") + ")",
            "deviation_pct": None, "wait_time_min": round((cancel-arr).total_seconds()/60, 1) if arr else None,
            "time_to_arrival_min": round((arr-acc).total_seconds()/60, 1) if arr else None,
            "pickup_zone_class": zone, "registered_pickup_points": reg_points,
            "in_app_calls": [{"placed_by": c[0], "placed_at": fmt(c[1]), "duration_sec": c[2], "answered": c[3]} for c in (calls or [])],
            "pickup_amended_at": None, "dropoff_amended_at": None, "original_pickup": None, "original_dropoff": None,
            "optimal_route_erp_sgd": 0.0, "amended_optimal_distance_km": None, "amended_optimal_duration_min": None,
            "solo_optimal_distance_km": None, "chat_message_count": chat_count}

# ---------- advisory ----------
def advisory(adv_id, road, typ, a_from, a_to, box, sev, desc, src, trace_pts, win_from, win_to, alt_km=None):
    inter = any(box[0] <= p["lat"] <= box[2] and box[1] <= p["lng"] <= box[3] for p in trace_pts) if trace_pts else None
    ov_from = max(a_from, win_from); ov_to = min(a_to if a_to else win_to, win_to)
    ov = max(0.0, (ov_to - ov_from).total_seconds()/60)
    return {"advisory_id": adv_id, "road_name": road, "type": typ, "active_from": fmt(a_from), "active_to": fmt(a_to),
            "geometry": {"min_lat": box[0], "min_lng": box[1], "max_lat": box[2], "max_lng": box[3]},
            "severity": sev, "description": desc, "advisory_source": src,
            "intersects_route": inter, "overlaps_trip_window": ov > 0, "overlap_minutes": round(ov, 1),
            "shortest_lawful_alternative_km": alt_km}

# ---------- assembly ----------
EV_ORDER = ["TRIP","GPS","CHAT","FARE","RPROF","DPROF"]
def evid(case, tok, k=None):
    b = f"EV-{tok}-{case:05d}"
    return b if k is None else f"{b}-{k:02d}"

def dispute(case, category, filed_by, filed_at, claim, contested, ev_ids, cp=None, channel="IN_APP_SUPPORT"):
    d = {"dispute_id": f"DSP-{case:05d}", "trip_id": f"TRP-{case:05d}", "case_no": case, "category": category,
         "filed_by": filed_by, "filed_at": fmt(filed_at), "claim_text": claim, "amount_contested_sgd": m2(contested),
         "evidence_ids": ev_ids, "counterparty_statement": None, "channel": channel}
    if cp: d["counterparty_statement"] = {"text": cp[0], "submitted_by": cp[1], "submitted_at": fmt(cp[2])}
    return d

def case_file(case, disp, evidence):
    return {"schema_version": SCHEMA_VERSION, "case_no": case, "dispute": disp, "evidence": evidence}

def gt(ruling, amount, clauses, difficulty, rationale, driver_comp=None, referrals=None):
    assert 120 <= len(rationale) <= 2500, (len(rationale), rationale[:60])
    return {"expected_ruling": ruling, "expected_amount_sgd": amount, "expected_driver_compensation_sgd": driver_comp,
            "expected_referrals": referrals or [], "governing_clauses": clauses, "difficulty": difficulty, "rationale": rationale}

def dumps(o):
    return json.dumps(o, ensure_ascii=False, indent=2) + "\n"

def sha(b): return hashlib.sha256(b).hexdigest()

# ---------- NS helpers shared by generator + validator ----------
def first_qualifying(pts, pick, radius_m, acc_max=25.0):
    """First fix that starts 3 consecutive fixes, each acc<=25 m and within radius. pts: dicts with lat/lng/ts(datetime)/accuracy_m."""
    for i in range(len(pts)-2):
        if all(pts[j].get("accuracy_m", 99) <= acc_max and haversine_km((pts[j]["lat"], pts[j]["lng"]), pick)*1000 <= radius_m for j in (i, i+1, i+2)):
            return pts[i]
    return None

def dwell_sec(pts, pick, radius_m, cancel):
    q = first_qualifying(pts, pick, radius_m)
    return None if q is None else (cancel - q["ts"]).total_seconds(), q
