"""Shared generator foundation for the tribunal-sealed-v3 case set.

Python 3 standard library only. Money is decimal.Decimal throughout and is only
turned into a JSON number (float with 2 dp) at the moment it is written into a
payload. Geometry uses the same haversine (R = 6371.0088 km) as ref/check_set.py.

See build/FOUNDATION.md for the API description and a minimal case module.
"""
import json
import math
import os
import random
import re
import statistics
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# paths, constants
# ---------------------------------------------------------------------------
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BUILD_DIR)
REF_DIR = os.path.join(ROOT_DIR, "ref")

SCHEMA_VERSION = "1.2.0"
ASSESSOR_VERSION = "prepass-1.0.0"
SEED = "tsv3-gen-2026-10"          # fixed seed root; combine with case number via rng()

RD = "ROUTE_DEVIATION"
NS = "NO_SHOW_CHARGE"
CATEGORIES = (RD, NS)
RD_RANGE = (4001, 4015)
NS_RANGE = (4051, 4065)

TOK = {"TRIP_RECORD": "TRIP", "GPS_TRACE": "GPS", "CHAT_LOG": "CHAT", "FARE_BREAKDOWN": "FARE",
       "RIDER_PROFILE": "RPROF", "DRIVER_PROFILE": "DPROF", "TRAFFIC_ADVISORY": "ADVIS"}
EVIDENCE_ORDER = list(TOK)
SOURCES = ("PLATFORM_TELEMETRY", "PAYMENTS_LEDGER", "THIRD_PARTY_LTA", "DRIVER_DEVICE", "USER_SUBMITTED")
ISSUE_CODES = ("MISSING_ARTIFACT", "CROSS_SOURCE_CONFLICT", "TRUNCATED_LOG", "PARTIAL_RECORD", "STALE_SNAPSHOT",
               "CONTENT_REDACTED", "LOW_SAMPLE_RATE", "LANGUAGE_AMBIGUITY", "UNREAD_MESSAGE",
               "SCHEMA_VERSION_MISMATCH", "GPS_GAP", "LOW_COVERAGE", "GPS_DRIFT", "IMPLAUSIBLE_SPEED",
               "ADVISORY_UNCORROBORATED", "UNVERIFIED_SOURCE", "CLOCK_SKEW")
GPS_GAP_GRADES = ("SHORT_OR_OUTSIDE_WINDOW", "LONG_INSIDE_WINDOW", "STRADDLING_CANCELLATION")
PRODUCTS = ("RYDE_X", "RYDE_XL", "RYDE_POOL", "RYDE_TAXI", "RYDE_PLUS")
CHANNELS = ("IN_APP_SUPPORT", "EMAIL")
PARTIES = ("RIDER", "DRIVER")
SENDERS = ("RIDER", "DRIVER", "SYSTEM")
ADVISORY_TYPES = ("CLOSURE", "ACCIDENT", "KERB_RESTRICTION", "ENFORCEMENT", "ROADWORKS", "CONGESTION")
RULINGS = ("FULL_REFUND", "PARTIAL_REFUND", "NO_ACTION", "DRIVER_COMPENSATION", "ESCALATE")
DIFFICULTIES = ("EASY", "HARD", "REVERSAL", "INDETERMINATE")
FORBIDDEN = ("ground_truth", "expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd",
             "expected_referrals", "governing_clauses", "difficulty", "rationale", "canary", "sealed")

# Payload key sets, in the order of the organisers' sample (ref/case-00901.json).
TRIP_KEYS = ("trip_id", "rider_id", "driver_id", "requested_at", "accepted_at", "arrived_at", "started_at",
             "ended_at", "cancelled_at", "status", "cancelled_by", "cancellation_reason_code", "pickup", "dropoff",
             "vehicle_type", "pickup_zone_class", "chat_message_count", "registered_pickup_points", "in_app_calls",
             "optimal_distance_km", "optimal_duration_min", "optimal_route_source", "optimal_route_erp_sgd",
             "actual_distance_km", "actual_duration_min", "deviation_pct", "amended_optimal_distance_km",
             "amended_optimal_duration_min", "solo_optimal_distance_km", "pickup_amended_at", "dropoff_amended_at",
             "original_pickup", "original_dropoff", "scheduled_at", "platform_policy", "events")
PLACE_KEYS = ("label", "lat", "lng", "venue_id")
CALL_KEYS = ("call_id", "initiated_at", "initiated_by", "answered", "duration_sec")
EVENT_KEYS = ("event_type", "at", "detail", "source")
PP_KEYS = ("grace_after_match_sec", "advance_grace_before_scheduled_sec", "free_wait_sec", "no_show_threshold_sec",
           "cancellation_fee_sgd", "rider_gross_cancellation_fee_sgd", "waiting_fee_sgd", "fee_goes_to",
           "arrival_marker", "source")
GPS_KEYS = ("trip_id", "points", "point_count", "first_fix_at", "last_fix_at", "sample_interval_sec",
            "expected_interval_sec", "gaps", "max_gap_sec", "coverage_pct", "trace_distance_km", "rider_track")
POINT_KEYS = ("lat", "lng", "ts", "speed_kph", "accuracy_m")          # + optional venue_id
RIDER_POINT_KEYS = ("lat", "lng", "ts", "accuracy_m")
GAP_KEYS = ("from", "to", "gap_sec")
CHAT_KEYS = ("trip_id", "messages", "message_count", "first_message_at", "last_message_at", "truncated")
MSG_KEYS = ("msg_id", "sender", "text", "sent_at", "read_at", "delivered_at", "channel", "language", "redacted",
            "waypoint_hint")
FARE_KEYS = ("trip_id", "currency", "fare_model", "cancellation_fee", "total_charged", "payment_status",
             "refund_issued_sgd", "charged_at", "surge_multiplier", "rate_card_id", "base_fare", "distance_fare",
             "time_fare", "surge_amount", "tolls_erp", "airport_surcharge", "platform_fee", "promo_discount",
             "waiting_time_fee", "quoted_fare_sgd", "distance_charged_km", "time_charged_min", "per_km_rate_sgd",
             "per_min_rate_sgd", "erp_gantries")
FARE_LINES = ("base_fare", "distance_fare", "time_fare", "surge_amount", "tolls_erp", "airport_surcharge",
              "platform_fee", "cancellation_fee", "waiting_time_fee")
ERP_KEYS = ("gantry_id", "name", "lat", "lng", "charged_at", "amount_sgd")
RPROF_KEYS = ("party_id", "party_role", "snapshot_at", "account_age_days", "lifetime_trips", "rating",
              "prior_disputes_filed", "prior_disputes_upheld", "prior_no_show_flags", "cancellation_rate",
              "no_show_disputes_30d", "deviation_claims_60d", "deviation_claims_60d_substantiated",
              "disputes_with_counterparty_90d")
DPROF_KEYS = ("party_id", "party_role", "snapshot_at", "account_age_days", "lifetime_trips", "rating",
              "prior_disputes_filed", "prior_disputes_upheld", "prior_no_show_flags", "vehicle_type",
              "cancellation_rate", "prior_deviation_flags", "acceptance_rate", "active_region",
              "deviation_flags_90d", "completed_trips_90d", "no_show_terminations_30d", "completed_trips_30d",
              "disputes_with_counterparty_90d")
ADVIS_KEYS = ("advisory_id", "type", "road", "segment", "geometry", "valid_from", "valid_to", "issued_at",
              "shortest_lawful_alternative_km", "source_ref")
ARTIFACT_KEYS = ("evidence_id", "evidence_type", "trip_id", "source", "generated_at", "schema_version",
                 "admissibility", "payload")
DISPUTE_KEYS = ("dispute_id", "trip_id", "case_no", "category", "filed_by", "filed_at", "claim_text",
                "amount_contested_sgd", "counterparty_statement", "channel", "evidence_ids")
KEY_GT_KEYS = ("expected_ruling", "expected_amount_sgd", "expected_driver_compensation_sgd", "expected_referrals",
               "governing_clauses", "difficulty", "rationale")


class BuildError(ValueError):
    """Raised by a builder when its inputs would produce an invalid case."""


def _need(cond, msg):
    if not cond:
        raise BuildError(msg)


def rng(case_no, salt=""):
    """The only sanctioned source of randomness: seeded from SEED, the case number and a salt."""
    return random.Random("{0}:{1}:{2}".format(SEED, int(case_no), salt))


# ---------------------------------------------------------------------------
# ids
# ---------------------------------------------------------------------------
def dsp_id(n):
    return "DSP-{0:05d}".format(n)


def trp_id(n):
    return "TRP-{0:05d}".format(n)


def ev_id(n, evidence_type, seq=None):
    """EV-<TOK>-0NNNN; advisories take seq 1 or 2 -> EV-ADVIS-0NNNN-01."""
    _need(evidence_type in TOK, "unknown evidence_type {0}".format(evidence_type))
    base = "EV-{0}-{1:05d}".format(TOK[evidence_type], n)
    if evidence_type == "TRAFFIC_ADVISORY":
        _need(seq in (1, 2), "advisory needs seq 1 or 2")
        return base + "-{0:02d}".format(seq)
    _need(seq is None, "only TRAFFIC_ADVISORY takes a seq")
    return base


def msg_id(n, k):
    return "MSG-{0:05d}-{1:03d}".format(n, k)


def call_id(n, k):
    return "CALL-{0:05d}-{1:03d}".format(n, k)


# ---------------------------------------------------------------------------
# money (Decimal)
# ---------------------------------------------------------------------------
CENT = Decimal("0.01")
FIVE_CENTS = Decimal("0.05")


def D(x):
    """Decimal from Decimal / int / str; a float goes through str() so 3.12 -> Decimal('3.12')."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise BuildError("bool is not money")
    if isinstance(x, float):
        return Decimal(repr(x))
    return Decimal(x)


def q2(x):
    """Quantise to cents, ROUND_HALF_UP."""
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def up005(x):
    """Round UP to the next multiple of 0.05 (exact multiples stay)."""
    d = D(x)
    return ((d / FIVE_CENTS).to_integral_value(rounding=ROUND_CEILING) * FIVE_CENTS).quantize(CENT)


def num(x):
    """JSON number with 2 dp (a float holding q2(x)); None passes through."""
    if x is None:
        return None
    return float(q2(x))


def money_str(x):
    """'5.00' style text for claim / chat strings."""
    return "{0:.2f}".format(q2(x))


def is_mult005(x):
    return D(x) % FIVE_CENTS == 0


def dec_of(v):
    """Decimal of a JSON number as written (float -> repr)."""
    return D(v)


# ---------------------------------------------------------------------------
# time (+08:00)
# ---------------------------------------------------------------------------
SGT = timezone(timedelta(hours=8))
TS_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+08:00$")


def parse_ts(s):
    if isinstance(s, datetime):
        dt = s
    else:
        dt = datetime.fromisoformat(s)
    _need(dt.tzinfo is not None, "timestamp without offset: {0}".format(s))
    return dt.astimezone(SGT)


def fmt_ts(dt):
    dt = parse_ts(dt)
    _need(dt.microsecond == 0, "sub-second timestamp {0}".format(dt))
    return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def ts(date, hms):
    """ts('2026-09-02', '08:15:00') -> '2026-09-02T08:15:00+08:00'."""
    return fmt_ts(datetime.fromisoformat("{0}T{1}+08:00".format(date, hms)))


def add_s(t, seconds):
    """Add (integer) seconds to an ISO timestamp; returns the formatted string."""
    _need(float(seconds) == int(seconds), "add_s takes whole seconds")
    return fmt_ts(parse_ts(t) + timedelta(seconds=int(seconds)))


def add_min(t, minutes):
    return add_s(t, int(round(minutes * 60)))


def diff_s(a, b):
    """Seconds from a to b (b - a), float."""
    return (parse_ts(b) - parse_ts(a)).total_seconds()


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
R_KM = 6371.0088


def _ll(p):
    if isinstance(p, dict):
        return float(p["lat"]), float(p["lng"])
    return float(p[0]), float(p[1])


def hav_km(a, b):
    """Same formula and radius as km() in ref/check_set.py; a, b are {lat,lng} dicts or (lat,lng) tuples."""
    la, lo = _ll(a)
    lb, mo = _ll(b)
    r = R_KM
    p1, p2 = math.radians(la), math.radians(lb)
    dp, dl = p2 - p1, math.radians(mo - lo)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def hav_m(a, b):
    return hav_km(a, b) * 1000.0


def ll(lat, lng):
    return {"lat": round(float(lat), 6), "lng": round(float(lng), 6)}


def offset_m(lat, lng, north_m, east_m):
    """Move a coordinate by metres north / east (small offsets)."""
    dlat = north_m / (R_KM * 1000.0) * 180.0 / math.pi
    dlng = east_m / (R_KM * 1000.0 * math.cos(math.radians(lat))) * 180.0 / math.pi
    return lat + dlat, lng + dlng


def polyline_km(waypoints):
    pts = [_ll(w) for w in waypoints]
    return sum(hav_km(pts[i - 1], pts[i]) for i in range(1, len(pts)))


# ---------------------------------------------------------------------------
# GPS synthesis
# ---------------------------------------------------------------------------
def _acc(accuracy_m, r):
    if accuracy_m is None:
        return None
    if isinstance(accuracy_m, (tuple, list)):
        _need(r is not None, "an accuracy range needs an rng")
        return round(r.uniform(float(accuracy_m[0]), float(accuracy_m[1])), 1)
    return round(float(accuracy_m), 1)


def _jit(lat, lng, jitter_m, r):
    if not jitter_m:
        return lat, lng
    _need(r is not None, "jitter needs an rng")
    return offset_m(lat, lng, r.gauss(0.0, jitter_m), r.gauss(0.0, jitter_m))


def gps_point(lat, lng, at, speed_kph, accuracy_m, venue_id=None):
    p = {"lat": round(float(lat), 6), "lng": round(float(lng), 6), "ts": fmt_ts(at),
         "speed_kph": speed_kph, "accuracy_m": accuracy_m}
    if venue_id is not None:
        p["venue_id"] = venue_id
    return p


def rider_point(lat, lng, at, accuracy_m):
    return {"lat": round(float(lat), 6), "lng": round(float(lng), 6), "ts": fmt_ts(at), "accuracy_m": accuracy_m}


def drive(waypoints, t0, speed_kph, cadence_s, *, rng=None, jitter_m=0.0, accuracy_m=5.0, speed_noise_kph=0.0,
          include_start=True, include_end=True, venue_id=None):
    """Fixes along a polyline.

    waypoints: [(lat, lng), ...] or [{lat, lng}, ...] (>= 2).
    t0: ISO timestamp of the first fix (at waypoint 0).
    speed_kph: a number, a list with one speed per segment, or a callable f(km_along, total_km) -> kph.
    cadence_s: whole seconds between fixes. The vehicle is integrated in 1 s steps; a fix is emitted every
    cadence_s seconds, plus a final fix exactly at the last waypoint (include_end) when the trip ends between
    two cadence ticks. jitter_m (gaussian, metres), an accuracy range (lo, hi) and speed_noise_kph need an rng
    (use common.rng(case_no, salt)). Coordinates are rounded to 6 dp; measure distance on the returned points
    with trace_distance(), never on the waypoints.
    """
    pts = [_ll(w) for w in waypoints]
    _need(len(pts) >= 2, "drive needs >= 2 waypoints")
    _need(int(cadence_s) == cadence_s and cadence_s >= 1, "cadence_s must be whole seconds >= 1")
    cadence_s = int(cadence_s)
    seg = [hav_km(pts[i - 1], pts[i]) for i in range(1, len(pts))]
    total = sum(seg)
    _need(total > 0, "zero-length route")
    cum = [0.0]
    for s in seg:
        cum.append(cum[-1] + s)

    if callable(speed_kph):
        def v_at(d):
            return float(speed_kph(d, total))
    elif isinstance(speed_kph, (list, tuple)):
        _need(len(speed_kph) == len(seg), "one speed per segment ({0})".format(len(seg)))

        def v_at(d):
            for i in range(len(seg)):
                if d < cum[i + 1] or i == len(seg) - 1:
                    return float(speed_kph[i])
    else:
        def v_at(d):
            return float(speed_kph)

    def pos(d):
        d = min(max(d, 0.0), total)
        for i in range(len(seg)):
            if d <= cum[i + 1] or i == len(seg) - 1:
                f = 0.0 if seg[i] == 0 else (d - cum[i]) / seg[i]
                return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f,
                        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f)

    def emit(t, d):
        lat, lng = pos(d)
        lat, lng = _jit(lat, lng, jitter_m, rng)
        sp = v_at(d)
        if speed_noise_kph:
            _need(rng is not None, "speed noise needs an rng")
            sp += rng.gauss(0.0, speed_noise_kph)
        out.append(gps_point(lat, lng, add_s(t0, t), max(0, int(round(sp))), _acc(accuracy_m, rng), venue_id))

    out = []
    t, d = 0, 0.0
    if include_start:
        emit(0, 0.0)
    last_emit = 0
    while d < total:
        v = v_at(d)
        _need(v > 0, "speed must be > 0 while driving")
        d += v / 3600.0
        t += 1
        _need(t < 86400, "drive longer than a day")
        if d >= total:
            break
        if t % cadence_s == 0:
            emit(t, d)
            last_emit = t
    if include_end and last_emit != t:
        emit(t, total)
    return out


def dwell(lat, lng, t0, duration_s, cadence_s, *, rng=None, jitter_m=0.0, accuracy_m=5.0, include_start=True,
          venue_id=None):
    """Stationary fixes (speed 0) at one spot from t0 to t0 + duration_s inclusive."""
    _need(int(cadence_s) == cadence_s and cadence_s >= 1, "cadence_s must be whole seconds >= 1")
    _need(int(duration_s) == duration_s and duration_s >= 0, "duration_s must be whole seconds >= 0")
    ticks = list(range(0 if include_start else int(cadence_s), int(duration_s) + 1, int(cadence_s)))
    if ticks and ticks[-1] != int(duration_s) or (not ticks and duration_s > 0):
        ticks.append(int(duration_s))
    out = []
    for k in ticks:
        la, lo = _jit(float(lat), float(lng), jitter_m, rng)
        out.append(gps_point(la, lo, add_s(t0, k), 0, _acc(accuracy_m, rng), venue_id))
    return out


def walk(waypoints, t0, speed_kph, cadence_s, **kw):
    """Rider-track fixes ({lat, lng, ts, accuracy_m}) along a polyline at walking speed."""
    return to_rider_track(drive(waypoints, t0, speed_kph, cadence_s, **kw))


def to_rider_track(points):
    return [{"lat": p["lat"], "lng": p["lng"], "ts": p["ts"], "accuracy_m": p.get("accuracy_m")} for p in points]


def concat(*segments):
    """Join point lists; a point whose ts equals the previous point's ts is dropped. Must end strictly increasing."""
    out = []
    for segpts in segments:
        for p in segpts:
            if out and p["ts"] == out[-1]["ts"]:
                continue
            out.append(p)
    for i in range(1, len(out)):
        _need(parse_ts(out[i]["ts"]) > parse_ts(out[i - 1]["ts"]),
              "points not strictly increasing at {0}".format(out[i]["ts"]))
    return out


def drop_between(points, t_from, t_to):
    """Remove fixes strictly between two timestamps (to cut a gap)."""
    a, b = parse_ts(t_from), parse_ts(t_to)
    return [p for p in points if not (a < parse_ts(p["ts"]) < b)]


def shift_points(points, seconds):
    """Copy of points with every ts moved by whole seconds (device clock skew)."""
    return [dict(p, ts=add_s(p["ts"], seconds)) for p in points]


def set_field(points, key, value, t_from=None, t_to=None):
    """Copy of points with key=value on fixes in [t_from, t_to] (inclusive; None = open)."""
    a = parse_ts(t_from) if t_from else None
    b = parse_ts(t_to) if t_to else None
    out = []
    for p in points:
        t = parse_ts(p["ts"])
        if (a is None or t >= a) and (b is None or t <= b):
            p = dict(p)
            p[key] = value
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# GPS measurement
# ---------------------------------------------------------------------------
def trace_distance(points):
    """Haversine sum over all consecutive points, rounded to 3 dp (what goes into trace_distance_km)."""
    return round(sum(hav_km(points[i - 1], points[i]) for i in range(1, len(points))), 3)


def intervals(points):
    return [diff_s(points[i - 1]["ts"], points[i]["ts"]) for i in range(1, len(points))]


def gap_list(points, threshold_s):
    """[{from, to, gap_sec}] for consecutive intervals strictly greater than threshold_s."""
    out = []
    for i in range(1, len(points)):
        g = diff_s(points[i - 1]["ts"], points[i]["ts"])
        if g > threshold_s:
            out.append({"from": points[i - 1]["ts"], "to": points[i]["ts"], "gap_sec": float(g)})
    return out


def max_gap(points):
    iv = intervals(points)
    return float(max(iv)) if iv else None


def sample_interval(points):
    """Median interval between fixes (s), 1 dp."""
    iv = intervals(points)
    return round(float(statistics.median(iv)), 1) if iv else None


def max_jump_m(points):
    """Largest straight-line distance between consecutive fixes, metres."""
    return max((hav_m(points[i - 1], points[i]) for i in range(1, len(points))), default=0.0)


def max_implied_kph(points):
    best = 0.0
    for i in range(1, len(points)):
        dt = diff_s(points[i - 1]["ts"], points[i]["ts"])
        if dt > 0:
            best = max(best, hav_km(points[i - 1], points[i]) / (dt / 3600.0))
    return best


def min_dist_m(coord, points):
    """Smallest distance (m) from coord to any fix of the trace."""
    return min((hav_m(coord, p) for p in points), default=None)


def nearest_fix(points, at):
    """(fix, |seconds|) of the fix whose ts is closest to `at`."""
    t = parse_ts(at)
    best = min(points, key=lambda p: abs((parse_ts(p["ts"]) - t).total_seconds()))
    return best, abs((parse_ts(best["ts"]) - t).total_seconds())


def points_between(points, t_from, t_to):
    a, b = parse_ts(t_from), parse_ts(t_to)
    return [p for p in points if a <= parse_ts(p["ts"]) <= b]


def window_stats(points, t_from, t_to):
    """Measurements for a time window [t_from, t_to] (inclusive).

    fixes: count of fixes inside; max_gap_s / max_jump_m: over consecutive pairs whose interval overlaps the
    window (a pair straddling a boundary counts); median_interval_s: inside the window; lead_s / tail_s: from
    t_from to the first fix inside, and from the last fix inside to t_to (None when no fix inside).
    """
    a, b = parse_ts(t_from), parse_ts(t_to)
    inside = points_between(points, t_from, t_to)
    gaps, jumps = [], []
    for i in range(1, len(points)):
        p, q = parse_ts(points[i - 1]["ts"]), parse_ts(points[i]["ts"])
        if q >= a and p <= b:
            gaps.append((q - p).total_seconds())
            jumps.append(hav_m(points[i - 1], points[i]))
    return {
        "fixes": len(inside),
        "max_gap_s": max(gaps) if gaps else None,
        "max_jump_m": max(jumps) if jumps else None,
        "median_interval_s": sample_interval(inside),
        "lead_s": (parse_ts(inside[0]["ts"]) - a).total_seconds() if inside else None,
        "tail_s": (b - parse_ts(inside[-1]["ts"])).total_seconds() if inside else None,
    }


def longest_run_within(points, center, radius_m, max_accuracy_m=None):
    """Longest run of consecutive fixes within radius_m of center; with max_accuracy_m, a fix whose accuracy is
    null or worse than the limit breaks the run. Returns (run_length, first_ts, last_ts)."""
    best = (0, None, None)
    run = []
    for p in points:
        ok = hav_m(center, p) <= radius_m
        if max_accuracy_m is not None:
            ok = ok and p.get("accuracy_m") is not None and p["accuracy_m"] <= max_accuracy_m
        if ok:
            run.append(p)
            if len(run) > best[0]:
                best = (len(run), run[0]["ts"], run[-1]["ts"])
        else:
            run = []
    return best


# ---------------------------------------------------------------------------
# admissibility weights
# ---------------------------------------------------------------------------
def _load_json(name):
    with open(os.path.join(REF_DIR, name), encoding="utf-8") as f:
        return json.load(f)


_INTEGRITY = None


def integrity_weights():
    global _INTEGRITY
    if _INTEGRITY is None:
        _INTEGRITY = _load_json("no_show.json")["integrity"]["weights"]
    return _INTEGRITY


def weight_for(issues, gps_gap_grade=None):
    """Product of no_show.json integrity.weights over the codes, rounded to 2 dp (float).

    GPS_GAP is graded: gps_gap_grade in SHORT_OR_OUTSIDE_WINDOW, LONG_INSIDE_WINDOW, STRADDLING_CANCELLATION.
    [] -> 1.0; ['MISSING_ARTIFACT'] -> 0.0.
    """
    w = integrity_weights()
    _need(len(set(issues)) == len(issues), "duplicate issue code")
    prod = Decimal(1)
    for code in issues:
        _need(code in ISSUE_CODES, "unknown issue code {0}".format(code))
        if code == "GPS_GAP":
            _need(gps_gap_grade in GPS_GAP_GRADES, "GPS_GAP needs gps_gap_grade in {0}".format(GPS_GAP_GRADES))
            prod *= D(w["GPS_GAP_" + gps_gap_grade])
        else:
            prod *= D(w[code])
    if "GPS_GAP" not in issues:
        _need(gps_gap_grade is None, "gps_gap_grade given without GPS_GAP")
    return float(q2(prod))


def allowed_weights(issues):
    """Every weight weight_for could give these issues (all GPS_GAP grades)."""
    if "GPS_GAP" in issues:
        return {weight_for(issues, g) for g in GPS_GAP_GRADES}
    return {weight_for(issues)}


# ---------------------------------------------------------------------------
# admissibility blocks and artifacts
# ---------------------------------------------------------------------------
def issue_detail(code, severity, detail):
    return {"code": code, "severity": severity, "detail": detail}


def adm_complete(notes, assessed_at, assessor_version=ASSESSOR_VERSION):
    return {"status": "COMPLETE", "issues": [], "weight_multiplier": 1.0, "notes": notes,
            "assessed_at": fmt_ts(assessed_at), "assessor_version": assessor_version}


def adm_impaired(issues, notes, assessed_at, gps_gap_grade=None, issue_details=None,
                 assessor_version=ASSESSOR_VERSION):
    issues = list(issues)
    _need(issues and "MISSING_ARTIFACT" not in issues, "IMPAIRED needs >= 1 non-missing code")
    a = {"status": "IMPAIRED", "issues": issues, "weight_multiplier": weight_for(issues, gps_gap_grade),
         "notes": notes, "assessed_at": fmt_ts(assessed_at), "assessor_version": assessor_version}
    if issue_details is not None:
        for dd in issue_details:
            _need(set(dd) == {"code", "severity", "detail"} and dd["code"] in issues, "bad issue_details entry")
        a["issue_details"] = list(issue_details)
    return a


def adm_missing(notes, assessed_at, assessor_version=ASSESSOR_VERSION):
    return {"status": "MISSING", "issues": ["MISSING_ARTIFACT"], "weight_multiplier": 0.0, "notes": notes,
            "assessed_at": fmt_ts(assessed_at), "assessor_version": assessor_version}


def artifact(case_no, evidence_type, payload, admissibility, *, source, generated_at, seq=None,
             schema_version=SCHEMA_VERSION):
    """One eight-key evidence artifact. A MISSING block requires payload None and vice versa."""
    _need(source in SOURCES, "source {0}".format(source))
    st = admissibility["status"]
    _need((payload is None) == (st == "MISSING"), "payload None <=> status MISSING ({0})".format(evidence_type))
    if evidence_type in ("TRIP_RECORD", "FARE_BREAKDOWN"):
        _need(payload is not None, "{0} is never MISSING".format(evidence_type))
    if schema_version != SCHEMA_VERSION:
        _need("SCHEMA_VERSION_MISMATCH" in admissibility["issues"], "schema_version differs without the code")
    return {"evidence_id": ev_id(case_no, evidence_type, seq), "evidence_type": evidence_type,
            "trip_id": trp_id(case_no), "source": source, "generated_at": fmt_ts(generated_at),
            "schema_version": schema_version, "admissibility": admissibility, "payload": payload}


# ---------------------------------------------------------------------------
# payload builders
# ---------------------------------------------------------------------------
def place(label, lat, lng, venue_id=None):
    return {"label": label, "lat": round(float(lat), 6), "lng": round(float(lng), 6), "venue_id": venue_id}


def in_app_call(case_no, k, initiated_at, initiated_by, answered, duration_sec):
    _need(initiated_by in PARTIES, "initiated_by")
    return {"call_id": call_id(case_no, k), "initiated_at": fmt_ts(initiated_at), "initiated_by": initiated_by,
            "answered": bool(answered), "duration_sec": duration_sec}


def event(event_type, at, detail, source="PLATFORM_TELEMETRY"):
    _need(source in SOURCES, "event source")
    return {"event_type": event_type, "at": fmt_ts(at), "detail": detail, "source": source}


def platform_policy(source="RECORD-PLATFORM", **overrides):
    """The ten-key trip_record.platform_policy, starting from no_show.json fee_schedule.defaults (read at runtime).
    Money values may be Decimal/str; they are written as 2-dp numbers."""
    base = dict(_load_json("no_show.json")["fee_schedule"]["defaults"])
    for k in overrides:
        _need(k in PP_KEYS and k != "source", "unknown platform_policy key {0}".format(k))
    base.update(overrides)
    base["source"] = source
    for k in ("cancellation_fee_sgd", "rider_gross_cancellation_fee_sgd", "waiting_fee_sgd"):
        base[k] = num(base[k]) if base[k] is not None else None
    _need(base["fee_goes_to"] in ("DRIVER", "PLATFORM"), "fee_goes_to")
    _need(base["arrival_marker"] in ("BUTTON", "GPS_AUTO"), "arrival_marker")
    return {k: base[k] for k in PP_KEYS}


_TRIP_MONEY = ("optimal_route_erp_sgd",)
_TRIP_TS = ("requested_at", "accepted_at", "arrived_at", "started_at", "ended_at", "cancelled_at",
            "pickup_amended_at", "dropoff_amended_at", "scheduled_at")


def trip_record(case_no, **kw):
    """Full trip_record key set (sample order); every key not given is null (lists: in_app_calls / events -> [])."""
    for k in kw:
        _need(k in TRIP_KEYS and k != "trip_id", "unknown trip_record key {0}".format(k))
    out = {}
    for k in TRIP_KEYS:
        v = kw.get(k)
        if k == "trip_id":
            v = trp_id(case_no)
        elif k in ("in_app_calls", "events") and v is None:
            v = []
        elif k in _TRIP_TS and v is not None:
            v = fmt_ts(v)
        elif k in _TRIP_MONEY and v is not None:
            v = num(v)
        out[k] = v
    for k in ("rider_id", "driver_id", "requested_at", "status", "pickup", "dropoff", "vehicle_type"):
        _need(out[k] is not None, "trip_record needs {0}".format(k))
    _need(out["vehicle_type"] in PRODUCTS, "vehicle_type {0}".format(out["vehicle_type"]))
    return out


def gps_trace(case_no, points, *, rider_track=None, expected_interval_sec=None, coverage_pct=None,
              gap_threshold_s=None):
    """Full gps_trace payload; counts, first/last fix, sample interval, gaps, max gap and trace_distance_km are
    computed from the points. gaps lists intervals > gap_threshold_s (default: 2 x expected_interval_sec, or 2 x
    the median interval when no expected interval is stated)."""
    points = list(points)
    for i in range(1, len(points)):
        _need(parse_ts(points[i]["ts"]) > parse_ts(points[i - 1]["ts"]), "gps ts not strictly increasing")
    si = sample_interval(points)
    if gap_threshold_s is None:
        base = expected_interval_sec if expected_interval_sec is not None else si
        gap_threshold_s = 2 * base if base is not None else 0
    return {
        "trip_id": trp_id(case_no),
        "points": points,
        "point_count": len(points),
        "first_fix_at": points[0]["ts"] if points else None,
        "last_fix_at": points[-1]["ts"] if points else None,
        "sample_interval_sec": si,
        "expected_interval_sec": float(expected_interval_sec) if expected_interval_sec is not None else None,
        "gaps": gap_list(points, gap_threshold_s) if points else [],
        "max_gap_sec": max_gap(points),
        "coverage_pct": coverage_pct,
        "trace_distance_km": trace_distance(points),
        "rider_track": list(rider_track) if rider_track is not None else [],
    }


def msg(sender, text, sent_at, *, read_at=None, delivered_at=None, channel="IN_APP", language="en",
        redacted=False, waypoint_hint=None, k=None):
    """One chat message (msg_id assigned by chat_log; pass k= to pin its sequence number, e.g. for a
    TRUNCATED_LOG that skips numbers)."""
    _need(sender in SENDERS, "sender {0}".format(sender))
    m = {"msg_id": k, "sender": sender, "text": text, "sent_at": fmt_ts(sent_at),
         "read_at": fmt_ts(read_at) if read_at else None,
         "delivered_at": fmt_ts(delivered_at) if delivered_at else None,
         "channel": channel, "language": language, "redacted": bool(redacted), "waypoint_hint": waypoint_hint}
    return m


def chat_log(case_no, messages, *, truncated=False):
    """Full chat_log payload. Messages without k get the next number; ids MSG-0NNNN-00k."""
    out, k = [], 0
    for m in messages:
        m = dict(m)
        k = m["msg_id"] if isinstance(m["msg_id"], int) else k + 1
        m["msg_id"] = msg_id(case_no, k)
        out.append(m)
    return {"trip_id": trp_id(case_no), "messages": out, "message_count": len(out),
            "first_message_at": out[0]["sent_at"] if out else None,
            "last_message_at": out[-1]["sent_at"] if out else None, "truncated": bool(truncated)}


def erp_gantry(gantry_id, name, lat, lng, charged_at, amount_sgd):
    return {"gantry_id": gantry_id, "name": name, "lat": round(float(lat), 6), "lng": round(float(lng), 6),
            "charged_at": fmt_ts(charged_at), "amount_sgd": num(amount_sgd)}


def fare_breakdown(case_no, *, fare_model="METERED", base_fare=0, distance_fare=0, time_fare=0, surge_amount=0,
                   airport_surcharge=0, platform_fee=0, cancellation_fee=0, waiting_time_fee=0, promo_discount=0,
                   erp_gantries=(), total_charged=None, payment_status="CHARGED", refund_issued_sgd=0,
                   charged_at=None, surge_multiplier=1, rate_card_id=None, quoted_fare_sgd=None,
                   distance_charged_km=None, time_charged_min=None, per_km_rate_sgd=None, per_min_rate_sgd=None,
                   currency="SGD"):
    """Full fare_breakdown payload. tolls_erp = sum of gantries; total_charged is computed from the lines (if
    given it must match to the cent)."""
    gantries = list(erp_gantries)
    tolls = sum((D(g["amount_sgd"]) for g in gantries), Decimal(0))
    lines = {"base_fare": base_fare, "distance_fare": distance_fare, "time_fare": time_fare,
             "surge_amount": surge_amount, "tolls_erp": tolls, "airport_surcharge": airport_surcharge,
             "platform_fee": platform_fee, "cancellation_fee": cancellation_fee,
             "waiting_time_fee": waiting_time_fee}
    lines = {k: q2(v) for k, v in lines.items()}
    total = sum(lines.values(), Decimal(0)) - q2(promo_discount)
    if total_charged is not None:
        _need(q2(total_charged) == total, "total_charged {0} != lines {1}".format(total_charged, total))
    _need(total > 0, "total_charged must be > 0")
    out = {"trip_id": trp_id(case_no), "currency": currency, "fare_model": fare_model,
           "cancellation_fee": num(lines["cancellation_fee"]), "total_charged": num(total),
           "payment_status": payment_status, "refund_issued_sgd": num(refund_issued_sgd),
           "charged_at": fmt_ts(charged_at) if charged_at else None,
           "surge_multiplier": float(D(surge_multiplier)), "rate_card_id": rate_card_id}
    for k in ("base_fare", "distance_fare", "time_fare", "surge_amount", "tolls_erp", "airport_surcharge",
              "platform_fee"):
        out[k] = num(lines[k])
    out["promo_discount"] = num(promo_discount)
    out["waiting_time_fee"] = num(lines["waiting_time_fee"])
    out["quoted_fare_sgd"] = num(quoted_fare_sgd)
    out["distance_charged_km"] = distance_charged_km
    out["time_charged_min"] = time_charged_min
    out["per_km_rate_sgd"] = num(per_km_rate_sgd)
    out["per_min_rate_sgd"] = num(per_min_rate_sgd)
    out["erp_gantries"] = gantries
    return {k: out[k] for k in FARE_KEYS}


def rd_fare_constants():
    """route_deviation.json fare_model constants as Decimals (read at runtime)."""
    fm = _load_json("route_deviation.json")["fare_model"]
    return {"base_fare": D(fm["base_fare"]), "per_km": D(fm["per_km"]), "per_min": D(fm["per_min"]),
            "platform_fee": D(fm["platform_fee"]), "de_minimis_refund": D(fm["de_minimis_refund"])}


def metered_lines(distance_km, duration_min, surge_multiplier=1, rates=None):
    """Billed metered fare lines in cents (Decimal): base, distance, time, surge on (base+distance+time),
    platform fee. These are what the ledger charged; a policy recomputation is the case author's own arithmetic."""
    r = rates or rd_fare_constants()
    base = q2(r["base_fare"])
    dist = q2(D(distance_km) * r["per_km"])
    tim = q2(D(duration_min) * r["per_min"])
    surge = q2((base + dist + tim) * (D(surge_multiplier) - 1))
    return {"base_fare": base, "distance_fare": dist, "time_fare": tim, "surge_amount": surge,
            "platform_fee": q2(r["platform_fee"])}


def _profile(keys, role, party_id, snapshot_at, kw):
    for k in kw:
        _need(k in keys and k not in ("party_id", "party_role", "snapshot_at"), "unknown profile key {0}".format(k))
    out = {k: kw.get(k) for k in keys}
    out["party_id"], out["party_role"], out["snapshot_at"] = party_id, role, fmt_ts(snapshot_at)
    return out


def rider_profile(party_id, snapshot_at, **kw):
    _need(re.match(r"^R-\d{4}$", party_id), "rider id R-xxxx")
    return _profile(RPROF_KEYS, "RIDER", party_id, snapshot_at, kw)


def driver_profile(party_id, snapshot_at, **kw):
    _need(re.match(r"^D-\d{4}$", party_id), "driver id D-xxxx")
    out = _profile(DPROF_KEYS, "DRIVER", party_id, snapshot_at, kw)
    _need(out["vehicle_type"] is None or out["vehicle_type"] in PRODUCTS, "driver vehicle_type")
    return out


def advisory(advisory_id, type, road, segment, frm, to, valid_from, valid_to, issued_at, source_ref,
             shortest_lawful_alternative_km=None):
    """Traffic advisory payload of BRIEF section 4. frm / to are (lat, lng) or {lat, lng}."""
    _need(type in ADVISORY_TYPES, "advisory type {0}".format(type))
    return {"advisory_id": advisory_id, "type": type, "road": road, "segment": segment,
            "geometry": {"from": ll(*_ll(frm)), "to": ll(*_ll(to))},
            "valid_from": fmt_ts(valid_from), "valid_to": fmt_ts(valid_to), "issued_at": fmt_ts(issued_at),
            "shortest_lawful_alternative_km": shortest_lawful_alternative_km, "source_ref": source_ref}


# ---------------------------------------------------------------------------
# dispute and case
# ---------------------------------------------------------------------------
def counterparty(text, submitted_by, submitted_at):
    _need(submitted_by in PARTIES, "submitted_by")
    return {"text": text, "submitted_by": submitted_by, "submitted_at": fmt_ts(submitted_at)}


def dispute(case_no, category, *, filed_at, filed_by, channel, amount_contested_sgd, claim_text,
            counterparty_statement=None, evidence_ids=(), safety_flag=None, complaint_flag=None):
    _need(category in CATEGORIES, "category")
    _need(filed_by in PARTIES, "filed_by")
    _need(channel in CHANNELS, "channel")
    d = {"dispute_id": dsp_id(case_no), "trip_id": trp_id(case_no), "case_no": case_no, "category": category,
         "filed_by": filed_by, "filed_at": fmt_ts(filed_at), "claim_text": claim_text,
         "amount_contested_sgd": num(amount_contested_sgd), "counterparty_statement": counterparty_statement,
         "channel": channel, "evidence_ids": list(evidence_ids)}
    if safety_flag is not None:
        d["safety_flag"] = bool(safety_flag)
    if complaint_flag is not None:
        d["complaint_flag"] = bool(complaint_flag)
    return d


def make_case(case_no, category, evidence, **dispute_kw):
    """Assemble a case: evidence sorted into canonical order (advisories by their seq), evidence_ids filled in,
    then validate_case + lint_case; raises BuildError listing every problem."""
    ev = sorted(evidence, key=lambda e: (EVIDENCE_ORDER.index(e["evidence_type"]), e["evidence_id"]))
    d = dispute(case_no, category, evidence_ids=[e["evidence_id"] for e in ev], **dispute_kw)
    c = {"schema_version": SCHEMA_VERSION, "case_no": case_no, "dispute": d, "evidence": ev}
    problems = validate_case(c) + lint_case(c)
    if problems:
        raise BuildError("case {0}:\n  ".format(case_no) + "\n  ".join(problems))
    return c


def dumps_case(case):
    return json.dumps(case, indent=2, ensure_ascii=True) + "\n"


# ---------------------------------------------------------------------------
# text rules
# ---------------------------------------------------------------------------
def walk_strings(obj):
    """Yield every string (keys and values) in a JSON-like object."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from walk_strings(v)


def non_ascii(text):
    return [ch for ch in text if ord(ch) > 127]


def forbidden_hits(text, extra=()):
    low = text.lower()
    return [w for w in FORBIDDEN + tuple(extra) if w in low]


def text_problems(where, obj, extra=()):
    """ASCII + forbidden-word check on every string of obj and on its serialisation (check_set reads the raw
    file, so a word split across keys and values is still caught there)."""
    out = []
    for s in walk_strings(obj):
        if non_ascii(s):
            out.append("{0}: non-ASCII text {1!r}".format(where, s[:60]))
    raw = obj if isinstance(obj, str) else json.dumps(obj, indent=2, ensure_ascii=True)
    for w in forbidden_hits(raw, extra):
        out.append("{0}: forbidden word {1!r}".format(where, w))
    return out


# ---------------------------------------------------------------------------
# case validation (mirror of check_set.check_case, in memory, exact where check_set is tolerant)
# ---------------------------------------------------------------------------
PP_SET = set(PP_KEYS)


def validate_case(c):
    F = []
    n = c.get("case_no")
    w = "case {0}".format(n)
    F += text_problems(w, c)
    if set(c) != {"schema_version", "case_no", "dispute", "evidence"}:
        F.append(w + ": top-level keys")
    if c.get("schema_version") != SCHEMA_VERSION:
        F.append(w + ": schema_version")
    if not (isinstance(n, int) and (RD_RANGE[0] <= n <= RD_RANGE[1] or NS_RANGE[0] <= n <= NS_RANGE[1])):
        F.append(w + ": case_no outside 4001-4015 / 4051-4065")
        return F
    d = c["dispute"]
    if not set(DISPUTE_KEYS) <= set(d) or set(d) - set(DISPUTE_KEYS) - {"safety_flag", "complaint_flag"}:
        F.append(w + ": dispute keys")
    if d.get("case_no") != n or d.get("dispute_id") != dsp_id(n) or d.get("trip_id") != trp_id(n):
        F.append(w + ": dispute ids")
    cat = d.get("category")
    if cat not in CATEGORIES:
        F.append(w + ": category")
    elif (cat == RD) != (RD_RANGE[0] <= n <= RD_RANGE[1]):
        F.append(w + ": category does not match the case-number range")
    if d.get("filed_by") not in PARTIES:
        F.append(w + ": filed_by")
    if d.get("channel") not in CHANNELS:
        F.append(w + ": channel")
    cs = d.get("counterparty_statement")
    if cs is not None and set(cs) != {"text", "submitted_by", "submitted_at"}:
        F.append(w + ": counterparty_statement shape")
    ev = c["evidence"]
    ids = [e.get("evidence_id") for e in ev]
    if d.get("evidence_ids") != ids:
        F.append(w + ": evidence_ids must list every evidence_id in file order")
    if len(set(ids)) != len(ids):
        F.append(w + ": duplicate evidence ids")
    types = [e.get("evidence_type") for e in ev]
    if any(t not in TOK for t in types):
        F.append(w + ": unknown evidence_type")
        return F
    if [EVIDENCE_ORDER.index(t) for t in types] != sorted(EVIDENCE_ORDER.index(t) for t in types):
        F.append(w + ": evidence not in canonical order")
    for t in EVIDENCE_ORDER[:6]:
        if types.count(t) != 1:
            F.append(w + ": {0} must appear exactly once".format(t))
    if types.count("TRAFFIC_ADVISORY") not in (1, 2):
        F.append(w + ": one or two TRAFFIC_ADVISORY")
    by, adv = {}, 0
    for e in ev:
        eid = e["evidence_id"]
        by.setdefault(e["evidence_type"], e)
        if set(e) != set(ARTIFACT_KEYS):
            F.append(eid + ": artifact keys")
        want = "EV-{0}-{1:05d}".format(TOK[e["evidence_type"]], n)
        if e["evidence_type"] == "TRAFFIC_ADVISORY":
            adv += 1
            want += "-{0:02d}".format(adv)
        if eid != want:
            F.append(eid + ": evidence_id should be " + want)
        if e.get("trip_id") != trp_id(n):
            F.append(eid + ": trip_id")
        if e.get("source") not in SOURCES:
            F.append(eid + ": source")
        a = e["admissibility"]
        for k in ("status", "issues", "weight_multiplier", "notes", "assessed_at", "assessor_version"):
            if k not in a:
                F.append(eid + ": admissibility lacks " + k)
        if set(a) - {"status", "issues", "weight_multiplier", "notes", "assessed_at", "assessor_version",
                     "issue_details"}:
            F.append(eid + ": extra admissibility keys")
        st, iss = a.get("status"), a.get("issues", [])
        for code in iss:
            if code not in ISSUE_CODES:
                F.append(eid + ": issue code " + code)
        if st == "COMPLETE" and (iss or a.get("weight_multiplier") != 1.0 or e["payload"] is None):
            F.append(eid + ": COMPLETE needs issues [], weight 1.0, a payload")
        if st == "MISSING" and (iss != ["MISSING_ARTIFACT"] or a.get("weight_multiplier") != 0.0
                                or e["payload"] is not None):
            F.append(eid + ": MISSING needs issues [MISSING_ARTIFACT], weight 0.0, payload null")
        if st == "IMPAIRED":
            if not iss or "MISSING_ARTIFACT" in iss or e["payload"] is None:
                F.append(eid + ": IMPAIRED needs at least one non-missing code and a payload")
            elif all(code in ISSUE_CODES for code in iss) and a.get("weight_multiplier") not in allowed_weights(iss):
                F.append(eid + ": weight {0} is not the integrity product for {1}".format(
                    a.get("weight_multiplier"), iss))
        if st not in ("COMPLETE", "IMPAIRED", "MISSING"):
            F.append(eid + ": status")
        for dd in a.get("issue_details", []):
            if set(dd) != {"code", "severity", "detail"} or dd["code"] not in iss:
                F.append(eid + ": issue_details entry")
        if e.get("schema_version") != SCHEMA_VERSION and "SCHEMA_VERSION_MISMATCH" not in iss:
            F.append(eid + ": artifact schema_version differs without SCHEMA_VERSION_MISMATCH")
    trip = by["TRIP_RECORD"]["payload"]
    fare = by["FARE_BREAKDOWN"]["payload"]
    gps = by["GPS_TRACE"]["payload"]
    chat = by["CHAT_LOG"]["payload"]
    if trip is None or fare is None:
        F.append(w + ": TRIP_RECORD and FARE_BREAKDOWN must not be missing")
        return F
    if cat == NS:
        pp = trip.get("platform_policy")
        if not isinstance(pp, dict) or set(pp) != PP_SET:
            F.append(w + ": a no-show trip_record carries platform_policy with exactly its ten keys")
    seq = [trip.get(k) for k in ("requested_at", "accepted_at", "arrived_at", "started_at", "ended_at",
                                 "cancelled_at")]
    seq = [s for s in seq if s]
    if any(parse_ts(seq[i]) > parse_ts(seq[i + 1]) for i in range(len(seq) - 1)) and \
            "CLOCK_SKEW" not in by["TRIP_RECORD"]["admissibility"]["issues"]:
        F.append(w + ": trip timestamps run backwards")
    try:
        tot = sum((dec_of(fare[k]) for k in FARE_LINES), Decimal(0)) - dec_of(fare["promo_discount"])
        if tot != dec_of(fare["total_charged"]):
            F.append(w + ": fare lines sum to {0}, total_charged {1}".format(tot, fare["total_charged"]))
        for k in FARE_LINES + ("promo_discount", "total_charged"):
            if dec_of(fare[k]) != q2(fare[k]):
                F.append(w + ": fare {0} has more than 2 dp".format(k))
        gsum = sum((dec_of(g["amount_sgd"]) for g in fare.get("erp_gantries") or []), Decimal(0))
        if dec_of(fare["tolls_erp"]) != gsum:
            F.append(w + ": tolls_erp != sum of erp_gantries")
        con = dec_of(d["amount_contested_sgd"])
        if not (0 < con <= dec_of(fare["total_charged"])):
            F.append(w + ": amount_contested_sgd must be > 0 and <= total_charged")
        if con != q2(con):
            F.append(w + ": amount_contested_sgd has more than 2 dp")
    except (TypeError, KeyError) as ex:
        F.append(w + ": fare lines not numeric ({0})".format(ex))
    if gps:
        pts = gps["points"]
        if gps["point_count"] != len(pts):
            F.append(w + ": point_count")
        if any(parse_ts(pts[i]["ts"]) >= parse_ts(pts[i + 1]["ts"]) for i in range(len(pts) - 1)):
            F.append(w + ": gps ts not strictly increasing")
        tdk = gps.get("trace_distance_km")
        if not isinstance(tdk, (int, float)) or isinstance(tdk, bool):
            F.append(w + ": trace_distance_km must be numeric")
        elif tdk != trace_distance(pts):
            F.append(w + ": trace_distance_km {0} but points measure {1}".format(tdk, trace_distance(pts)))
    if chat:
        msgs = chat["messages"]
        if chat["message_count"] != len(msgs):
            F.append(w + ": chat message_count")
        for k, m in enumerate(msgs, 1):
            if m["msg_id"] != msg_id(n, k) and "TRUNCATED_LOG" not in by["CHAT_LOG"]["admissibility"]["issues"]:
                F.append(w + ": msg_id sequence at " + m["msg_id"])
    return F


# ---------------------------------------------------------------------------
# lint (BRIEF shape and realism rules beyond check_set)
# ---------------------------------------------------------------------------
PHONE_RE = re.compile(r"(?<![\w.])(\+?65[\s-]?)?[689]\d{3}[\s-]?\d{4}(?![\w.])")
PLATE_RE = re.compile(r"\bS[A-Z]{1,2}\s?\d{1,4}\s?[A-Z]\b")
TRIP_FROM = datetime(2026, 8, 1, tzinfo=SGT)
TRIP_TO = datetime(2026, 10, 6, tzinfo=SGT)
LAT_RANGE = (1.22, 1.48)
LNG_RANGE = (103.60, 104.05)


def _walk_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v)


def lint_case(c):
    F = []
    n = c.get("case_no")
    w = "case {0}".format(n)
    ev = c.get("evidence", [])
    by = {}
    for e in ev:
        by.setdefault(e.get("evidence_type"), e)
    d = c.get("dispute", {})
    # timestamps, coordinates, data minimisation
    for s in walk_strings(c):
        if re.match(r"^\d{4}-\d\d-\d\dT", s) and not TS_RE.match(s):
            F.append(w + ": timestamp not second-precision +08:00: " + s)
        if PHONE_RE.search(s):
            F.append(w + ": looks like a phone number: {0!r}".format(PHONE_RE.search(s).group(0)))
        if PLATE_RE.search(s):
            F.append(w + ": looks like a registration plate: {0!r}".format(PLATE_RE.search(s).group(0)))
    for o in _walk_dicts(c):
        if "lat" in o and "lng" in o and isinstance(o["lat"], (int, float)):
            if not (LAT_RANGE[0] <= o["lat"] <= LAT_RANGE[1] and LNG_RANGE[0] <= o["lng"] <= LNG_RANGE[1]):
                F.append(w + ": coordinate outside Singapore {0},{1}".format(o["lat"], o["lng"]))
    shapes = {"TRIP_RECORD": TRIP_KEYS, "GPS_TRACE": GPS_KEYS, "CHAT_LOG": CHAT_KEYS, "FARE_BREAKDOWN": FARE_KEYS,
              "RIDER_PROFILE": RPROF_KEYS, "DRIVER_PROFILE": DPROF_KEYS, "TRAFFIC_ADVISORY": ADVIS_KEYS}
    for e in ev:
        p = e.get("payload")
        if p is not None and e.get("evidence_type") in shapes and set(p) != set(shapes[e["evidence_type"]]):
            F.append("{0}: payload keys differ from the shared shape: +{1} -{2}".format(
                e["evidence_id"], sorted(set(p) - set(shapes[e["evidence_type"]])),
                sorted(set(shapes[e["evidence_type"]]) - set(p))))
    trip = (by.get("TRIP_RECORD") or {}).get("payload")
    if trip:
        if trip.get("trip_id") != trp_id(n):
            F.append(w + ": trip_record.trip_id")
        if trip.get("vehicle_type") not in PRODUCTS:
            F.append(w + ": vehicle_type")
        if not re.match(r"^R-\d{4}$", str(trip.get("rider_id"))) or not re.match(r"^D-\d{4}$",
                                                                                 str(trip.get("driver_id"))):
            F.append(w + ": party ids R-xxxx / D-xxxx")
        for k in ("pickup", "dropoff", "original_pickup", "original_dropoff"):
            if trip.get(k) is not None and set(trip[k]) != set(PLACE_KEYS):
                F.append(w + ": trip_record.{0} shape".format(k))
        for call in trip.get("in_app_calls") or []:
            if set(call) != set(CALL_KEYS):
                F.append(w + ": in_app_call shape")
        for evn in trip.get("events") or []:
            if set(evn) != set(EVENT_KEYS):
                F.append(w + ": event shape")
        if d.get("category") == RD and trip.get("platform_policy") is not None and \
                set(trip["platform_policy"]) != PP_SET:
            F.append(w + ": platform_policy shape")
        try:
            req = parse_ts(trip["requested_at"])
            if not (TRIP_FROM <= req < TRIP_TO):
                F.append(w + ": trip outside 2026-08-01 .. 2026-10-05")
            last = max(parse_ts(trip[k]) for k in ("requested_at", "accepted_at", "arrived_at", "started_at",
                                                   "ended_at", "cancelled_at") if trip.get(k))
            fa = parse_ts(d["filed_at"])
            if not (last < fa <= last + timedelta(days=30)):
                F.append(w + ": dispute not filed within 30 days after the trip")
        except (KeyError, ValueError, BuildError) as ex:
            F.append(w + ": trip timing unreadable ({0})".format(ex))
        for k, role in (("RIDER_PROFILE", "rider_id"), ("DRIVER_PROFILE", "driver_id")):
            prof = (by.get(k) or {}).get("payload")
            if prof and prof.get("party_id") != trip.get(role):
                F.append(w + ": {0}.party_id != trip_record.{1}".format(k, role))
    cs = d.get("counterparty_statement")
    if cs and cs.get("submitted_by") == d.get("filed_by"):
        F.append(w + ": counterparty_statement submitted by the filer")
    gps_e = by.get("GPS_TRACE") or {}
    gps = gps_e.get("payload")
    if gps:
        if gps.get("trip_id") != trp_id(n):
            F.append(w + ": gps_trace.trip_id")
        for p in gps.get("points", []):
            if not (set(POINT_KEYS) <= set(p) <= set(POINT_KEYS) | {"venue_id"}):
                F.append(w + ": gps point keys {0}".format(sorted(p)))
                break
        for p in gps.get("rider_track") or []:
            if set(p) != set(RIDER_POINT_KEYS):
                F.append(w + ": rider_track point keys {0}".format(sorted(p)))
                break
        for g in gps.get("gaps") or []:
            if set(g) != set(GAP_KEYS):
                F.append(w + ": gap entry keys")
                break
        iss = gps_e["admissibility"]["issues"]
        if not ({"IMPLAUSIBLE_SPEED", "GPS_DRIFT"} & set(iss)):
            for track in (gps.get("points", []), gps.get("rider_track") or []):
                if len(track) > 1 and max_implied_kph(track) > 130:
                    F.append(w + ": implied speed {0:.0f} km/h between fixes without IMPLAUSIBLE_SPEED/GPS_DRIFT"
                             .format(max_implied_kph(track)))
    chat = (by.get("CHAT_LOG") or {}).get("payload")
    if chat:
        for m in chat.get("messages", []):
            if set(m) != set(MSG_KEYS) or m.get("sender") not in SENDERS:
                F.append(w + ": chat message shape / sender")
                break
    fare = (by.get("FARE_BREAKDOWN") or {}).get("payload")
    if fare:
        for g in fare.get("erp_gantries") or []:
            if set(g) != set(ERP_KEYS):
                F.append(w + ": erp gantry shape")
                break
    for e in ev:
        if e.get("evidence_type") == "TRAFFIC_ADVISORY" and e.get("payload"):
            p = e["payload"]
            if p.get("type") not in ADVISORY_TYPES:
                F.append(e["evidence_id"] + ": advisory type")
            geo = p.get("geometry") or {}
            if set(geo) != {"from", "to"} or any(set(geo.get(k) or {}) != {"lat", "lng"} for k in ("from", "to")):
                F.append(e["evidence_id"] + ": advisory geometry shape")
    for kk in ("RIDER_PROFILE", "DRIVER_PROFILE"):
        prof = (by.get(kk) or {}).get("payload")
        if kk == "DRIVER_PROFILE" and prof and prof.get("vehicle_type") not in PRODUCTS + (None,):
            F.append(w + ": driver_profile.vehicle_type")
    return F


# ---------------------------------------------------------------------------
# policy clause table (version 6) and the answer key record
# ---------------------------------------------------------------------------
_LIC = None
_RUL_LETTER = {"FULL_REFUND": "F", "PARTIAL_REFUND": "P", "NO_ACTION": "N", "DRIVER_COMPENSATION": "D",
               "ESCALATE": "E"}


def clause_table():
    """{clause_id: set(licensed rulings)} for policy version 6: the three base files plus the three amendments,
    read at runtime."""
    global _LIC
    if _LIC is None:
        lic = {}
        for f in ("general.json", "no_show.json", "route_deviation.json"):
            for cl in _load_json(f)["clauses"]:
                lic[cl["id"]] = set(cl["licenses"])
        for f in ("0001-pol-ns-11.json", "0002-pol-rd-14.json", "0003-pol-ns-12.json"):
            cl = _load_json(f)["clause"]
            lic[cl["id"]] = set(cl["licenses"])
        _LIC = lic
    return _LIC


def key_record(case_no, ruling, amount, dc, referrals, clauses, difficulty, rationale):
    """The exact answer-key record of BRIEF section 5. amount / dc: Decimal, str, int or None."""
    return {"case_no": case_no, "dispute_id": dsp_id(case_no),
            "ground_truth": {"expected_ruling": ruling,
                             "expected_amount_sgd": num(amount),
                             "expected_driver_compensation_sgd": num(dc),
                             "expected_referrals": list(referrals),
                             "governing_clauses": list(clauses),
                             "difficulty": difficulty,
                             "rationale": rationale}}


def validate_key(r, case=None):
    """Mirror of check_set.check_key for one record (plus the BRIEF's stricter rules). With the case, the
    contested amount and the cited evidence ids are checked too. Returns a list of problems."""
    F = []
    n = r.get("case_no")
    w = "key {0}".format(n)
    if set(r) != {"case_no", "dispute_id", "ground_truth"} or r.get("dispute_id") != dsp_id(n):
        F.append(w + ": record keys / dispute_id")
        return F
    g = r["ground_truth"]
    if set(g) != set(KEY_GT_KEYS):
        F.append(w + ": ground_truth keys")
        return F
    ru, am, dc = g["expected_ruling"], g["expected_amount_sgd"], g["expected_driver_compensation_sgd"]
    if ru not in RULINGS:
        F.append(w + ": ruling")
    for v in (am, dc):
        if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or dec_of(v) != q2(v)):
            F.append(w + ": amounts are numbers with at most 2 dp")
            return F
    con = None
    if case is not None:
        con = case["dispute"]["amount_contested_sgd"]
        if case["case_no"] != n:
            F.append(w + ": case mismatch")
    if ru == "FULL_REFUND":
        if am is None or (con is not None and am != con):
            F.append(w + ": FULL_REFUND amount must equal amount_contested_sgd")
    if ru == "PARTIAL_REFUND":
        if not (am and am > 0):
            F.append(w + ": PARTIAL_REFUND amount must be > 0")
        elif con is not None and dec_of(am) >= dec_of(con):
            F.append(w + ": PARTIAL_REFUND must be below amount_contested_sgd")
    if ru in ("NO_ACTION", "ESCALATE") and (am is not None or dc is not None):
        F.append(w + ": NO_ACTION / ESCALATE carry null amounts")
    if ru == "DRIVER_COMPENSATION" and (not am or dc != am or am <= 0):
        F.append(w + ": DRIVER_COMPENSATION: amount == driver_compensation > 0")
    if ru in ("FULL_REFUND", "PARTIAL_REFUND") and dc is not None and dc <= 0:
        F.append(w + ": driver_compensation must be null or > 0")
    for v in ((am, dc) if ru != "FULL_REFUND" else (dc,)):
        if v is not None and not is_mult005(v):
            F.append(w + ": amount {0} is not a multiple of 0.05".format(v))
    if g["difficulty"] not in DIFFICULTIES:
        F.append(w + ": difficulty")
    if g["difficulty"] == "INDETERMINATE" and ru != "ESCALATE":
        F.append(w + ": INDETERMINATE must be ESCALATE")
    lic = clause_table()
    cls = g["governing_clauses"]
    if not isinstance(cls, list) or not cls or any(c not in lic for c in cls):
        F.append(w + ": governing_clauses must be bare version-6 clause ids")
    elif len(set(cls)) != len(cls):
        F.append(w + ": duplicate governing clause")
    else:
        prefix = "POL-RD-" if (case and case["dispute"]["category"] == RD) else "POL-NS-" if case else None
        if prefix and any(not (c.startswith(prefix) or c.startswith("POL-GEN-")) for c in cls):
            F.append(w + ": governing clause from the other category")
        licensing = [c for c in cls if ru in lic[c]]
        if not licensing and "POL-GEN-08" not in cls:
            F.append(w + ": no governing clause licenses " + str(ru))
        elif licensing == ["POL-GEN-03"] and "POL-GEN-08" not in cls:
            F.append(w + ": only POL-GEN-03's universal licence carries the ruling; list the deciding clause")
    refs = g["expected_referrals"]
    if not isinstance(refs, list):
        F.append(w + ": referrals must be a list")
    else:
        for ref in refs:
            if not isinstance(ref, str) or not re.search(r"POL-[A-Z]{2,4}-[0-9]{2}", ref):
                F.append(w + ": a referral must name a clause")
    ra = g["rationale"]
    if not isinstance(ra, str) or not (120 <= len(ra) <= 2500):
        F.append(w + ": rationale length 120-2500")
    else:
        if non_ascii(ra):
            F.append(w + ": rationale not ASCII")
        named = set(re.findall(r"EV-[A-Z]+-{0:05d}(?:-\d\d)?".format(n), ra))
        if not named or not re.search(r"POL-[A-Z]+-\d\d", ra):
            F.append(w + ": rationale must name an evidence id of this case and a clause")
        if case is not None:
            have = set(case["dispute"]["evidence_ids"])
            other = [x for x in named if x not in have]
            if other:
                F.append(w + ": rationale names evidence ids not in the case: {0}".format(sorted(other)))
        for cid in set(re.findall(r"POL-[A-Z]+-\d\d", ra)):
            if cid not in lic:
                F.append(w + ": rationale names a clause outside version 6: " + cid)
    for s in walk_strings(r):
        if non_ascii(s):
            F.append(w + ": non-ASCII text")
            break
    return F
