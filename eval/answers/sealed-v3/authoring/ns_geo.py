"""GPS synthesis and no-show measurements for build/cases_ns.py (NO_SHOW_CHARGE, 4051-4065).

Synthesis: the blueprint's `gps_trace.design` gives timed legs (routes with per-segment speed weights, and stays),
emission windows (seeded uniform accuracy, seeded gaussian jitter, speed noise, venue ids, field overrides) and the
rider fix specs. Fixes are produced here by linear interpolation along the timed legs, then jittered and given an
accuracy from the seeded generators common.rng(case_no, 'drv') / common.rng(case_no, 'rdr'); 4062's urban-canyon
drift uses common.rng(4062, 'approach-drift') and common.rng(4062, 'drift') with the constants below.

Measurements: POL-NS-02 qualifying fixes and runs, in-radius intervals, dwell from the first qualifying fix,
window statistics, rider presence (POL-NS-04(c)), position-derived speeds. All distances use common.hav_m
(check_set's haversine, R = 6371.0088 km).
"""
from datetime import datetime

import common as C


# ---------------------------------------------------------------------------
# time helpers (epoch seconds <-> +08:00 strings)
# ---------------------------------------------------------------------------
def sec(t):
    return C.parse_ts(t).timestamp()


def iso(s):
    return C.fmt_ts(datetime.fromtimestamp(s, tz=C.SGT))


def in_window(s, a, b):
    return sec(a) <= s <= sec(b)


def pt(d):
    """{lat, lng} dict -> (lat, lng)."""
    return (d["lat"], d["lng"])


def lerp(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


# ---------------------------------------------------------------------------
# timed track
# ---------------------------------------------------------------------------
class Track:
    """Knots (t_seconds, lat, lng); constant speed between consecutive knots."""

    def __init__(self):
        self.knots = []

    def add_route(self, t0, t1, wps, weights=None):
        n = len(wps) - 1
        weights = weights or [1.0] * n
        lens = [C.hav_m(wps[i], wps[i + 1]) for i in range(n)]
        cost = [lens[i] / weights[i] for i in range(n)]
        tot = sum(cost)
        a, b = sec(t0), sec(t1)
        ks = [(a, wps[0][0], wps[0][1])]
        acc = 0.0
        for i in range(n):
            acc += cost[i]
            ks.append((a + (b - a) * acc / tot, wps[i + 1][0], wps[i + 1][1]))
        if self.knots and abs(self.knots[-1][0] - ks[0][0]) < 1e-9:
            ks = ks[1:]
        elif self.knots and not self.knots[-1][0] < ks[0][0]:
            raise C.BuildError("route leg starts before the previous leg ends")
        self.knots.extend(ks)
        return self

    def add_stay(self, t0, t1, p):
        a, b = sec(t0), sec(t1)
        if self.knots and abs(self.knots[-1][0] - a) < 1e-9:
            if C.hav_m((self.knots[-1][1], self.knots[-1][2]), p) >= 0.01:
                raise C.BuildError("stay must start where the route ended")
        else:
            self.knots.append((a, p[0], p[1]))
        self.knots.append((b, p[0], p[1]))
        return self

    def pos(self, s):
        ks = self.knots
        if not ks[0][0] - 1e-9 <= s <= ks[-1][0] + 1e-9:
            raise C.BuildError("time outside track: {0}".format(iso(s)))
        for i in range(1, len(ks)):
            if s <= ks[i][0] + 1e-9:
                a, b = ks[i - 1], ks[i]
                f = 0.0 if b[0] == a[0] else (s - a[0]) / (b[0] - a[0])
                f = min(max(f, 0.0), 1.0)
                return lerp((a[1], a[2]), (b[1], b[2]), f)
        return (ks[-1][1], ks[-1][2])

    def speed_kph(self, s):
        ks = self.knots
        for i in range(1, len(ks)):
            a, b = ks[i - 1], ks[i]
            if a[0] - 1e-9 <= s < b[0] - 1e-9:
                dt = b[0] - a[0]
                return 0.0 if dt <= 0 else C.hav_m((a[1], a[2]), (b[1], b[2])) / dt * 3.6
        if len(ks) >= 2 and abs(s - ks[-1][0]) < 1e-6:
            a, b = ks[-2], ks[-1]
            dt = b[0] - a[0]
            return 0.0 if dt <= 0 else C.hav_m((a[1], a[2]), (b[1], b[2])) / dt * 3.6
        return 0.0


def track_from_legs(legs):
    tr = Track()
    for leg in legs:
        if leg["kind"] == "route":
            wps = [pt(w) for w in leg["waypoints"]]
            plen = round(sum(C.hav_m(wps[i], wps[i + 1]) for i in range(len(wps) - 1)), 1)
            if plen != leg["polyline_m"]:
                raise C.BuildError("leg polyline {0} m, blueprint says {1}".format(plen, leg["polyline_m"]))
            tr.add_route(leg["from"], leg["to"], wps, leg["segment_speed_weights"])
        elif leg["kind"] == "stay":
            tr.add_stay(leg["from"], leg["to"], pt(leg["at"]))
        else:
            raise C.BuildError("unknown leg kind {0}".format(leg["kind"]))
    return tr


# ---------------------------------------------------------------------------
# emission
# ---------------------------------------------------------------------------
def emit(track, times, rng, em):
    """Driver fixes at the epoch-second `times`, from one blueprint `driver_fixes` emission block."""
    pts = []
    for s in times:
        t = iso(s)
        la, lo = track.pos(s)
        sig = 0.0
        for j in em["jitter_sigma_m"]:
            if in_window(s, j["from"], j["to"]):
                sig = j["sigma"]
        if sig:
            la, lo = C.offset_m(la, lo, rng.gauss(0.0, sig), rng.gauss(0.0, sig))
        acc, found = None, False
        for a in em["accuracy_m_uniform"]:
            if in_window(s, a["from"], a["to"]):
                found = True
                acc = None if a["lo"] is None else round(rng.uniform(a["lo"], a["hi"]), 1)
        if not found:
            raise C.BuildError("no accuracy window for {0}".format(t))
        v = track.speed_kph(s)
        if v > 0.5:
            v = max(1, int(round(v + rng.gauss(0.0, em["speed_noise_sigma_kph"]))))
        else:
            v = 0
        p = {"lat": round(la, 6), "lng": round(lo, 6), "ts": t, "speed_kph": v, "accuracy_m": acc}
        for vz in em["venue_id"]:
            if in_window(s, vz["from"], vz["to"]):
                p["venue_id"] = vz["venue_id"]
        if t in em["overrides"]:
            p.update(em["overrides"][t])
        pts.append(p)
    return pts


# Walking riders: the blueprint records each fix centre rounded to 6 dp; the centre actually used is the exact
# position on the rider's timed walk (constant speed between the listed points, offsets in metres from the pin).
RIDER_WALKS = {
    4052: ("19:27:00", "19:31:00", ((18, -14), (120, -40), (205, -215))),
    4064: ("19:06:00", "19:13:00", ((900, -870), (720, -700))),
    4065: ("18:11:30", "18:14:00", ((-330, -285), (-225, -195))),
}


def walk_centres(n, design, spec, day):
    """Exact walk positions for the rider fix specs (None where the case has no walking rider)."""
    if n not in RIDER_WALKS:
        return None
    t0, t1, offs = RIDER_WALKS[n]
    pin = pt(design["pickup_pin"])
    wps = [off6(pin, a, b) for a, b in offs]
    walk = Track().add_route(C.ts(day, t0), C.ts(day, t1), wps)
    end = sec(C.ts(day, t1))
    out = []
    for f in spec:
        s = sec(f["ts"])
        c = walk.pos(s) if s <= end else wps[-1]
        if (round(c[0], 6), round(c[1], 6)) != pt(f["centre"]):
            raise C.BuildError("{0}: walk centre at {1} differs from the blueprint".format(n, f["ts"]))
        out.append(c)
    return out


def rider_fixes(spec, rng, centres=None):
    """Rider-track points from the blueprint's `rider_fixes` emission block."""
    out = []
    for i, f in enumerate(spec):
        la, lo = centres[i] if centres else pt(f["centre"])
        sig = f["jitter_sigma_m"]
        if sig:
            la, lo = C.offset_m(la, lo, rng.gauss(0.0, sig), rng.gauss(0.0, sig))
        lo_acc, hi_acc = f["accuracy_m_uniform"]
        out.append({"lat": round(la, 6), "lng": round(lo, 6), "ts": f["ts"],
                    "accuracy_m": round(rng.uniform(lo_acc, hi_acc), 1)})
    return out


def times_summary(times):
    iv = []
    for i in range(1, len(times)):
        d = int(times[i] - times[i - 1])
        if d not in iv:
            iv.append(d)
    return {"count": len(times), "first": iso(times[0]), "last": iso(times[-1]), "distinct_intervals_s": sorted(iv)}


def off6(p, north_m, east_m):
    la, lo = C.offset_m(p[0], p[1], north_m, east_m)
    return (round(la, 6), round(lo, 6))


# 4062 urban-canyon drift (design constants of the case; positions drawn from the seeded generators).
CANYON_APPROACH_FROM = "12:31:00"          # approach fixes from here on alternate per the approach pattern
CANYON_APPROACH_PATTERN = "ABBABAABBABA"
CANYON_APPROACH_SHIFT_M = ((55, 95), (40, 80))   # north, east uniform ranges for a B approach fix
CANYON_NEAR_BOX_M = ((-22, 28), (-26, 24))       # around the pin (cluster A)
CANYON_FAR_BOX_M = ((-22, 26), (-24, 28))        # around the outlying cluster centre (cluster B)
CANYON_ACCURACY_M = (12.0, 22.0)
CANYON_CADENCE_S = 10


def canyon_drift(n, day, approach_pts, design, stay_from):
    """Apply the approach drift to `approach_pts` (in place) and return the stationary drift fixes."""
    ra = C.rng(n, "approach-drift")
    t_from = sec(C.ts(day, CANYON_APPROACH_FROM))
    k = 0
    for p in approach_pts:
        if sec(p["ts"]) >= t_from:
            if CANYON_APPROACH_PATTERN[k] == "B":
                (n_lo, n_hi), (e_lo, e_hi) = CANYON_APPROACH_SHIFT_M
                la, lo = off6((p["lat"], p["lng"]), ra.uniform(n_lo, n_hi), ra.uniform(e_lo, e_hi))
                p["lat"], p["lng"] = la, lo
            k += 1
    if k != len(CANYON_APPROACH_PATTERN):
        raise C.BuildError("4062 approach pattern length")
    pattern = design["drift_pattern"]
    pin = pt(design["pickup_pin"])
    far = pt(design["named_points"]["outlying_cluster_centre"])
    rd = C.rng(n, "drift")
    out = []
    for k, ch in enumerate(pattern):
        s = sec(stay_from) + CANYON_CADENCE_S * k
        if ch == "A":
            (n_lo, n_hi), (e_lo, e_hi) = CANYON_NEAR_BOX_M
            p = off6(pin, rd.uniform(n_lo, n_hi), rd.uniform(e_lo, e_hi))
        else:
            (n_lo, n_hi), (e_lo, e_hi) = CANYON_FAR_BOX_M
            p = off6(far, rd.uniform(n_lo, n_hi), rd.uniform(e_lo, e_hi))
        out.append({"lat": p[0], "lng": p[1], "ts": iso(s), "speed_kph": 0,
                    "accuracy_m": round(rd.uniform(*CANYON_ACCURACY_M), 1)})
    return out


def synthesize(n, design, driver_times, day):
    """(driver points, rider_track) from the blueprint design. `driver_times` are the emission timestamps."""
    tr = track_from_legs(design["legs"])
    drv = [e for e in design["emission"] if e["kind"] == "driver_fixes"]
    rdr = [e for e in design["emission"] if e["kind"] == "rider_fixes"]
    if len(drv) != 1 or len(rdr) > 1:
        raise C.BuildError("emission blocks")
    em = drv[0]
    times = [sec(t) for t in driver_times]
    summ = times_summary(times)
    if summ != em["times"]:
        raise C.BuildError("emission schedule {0} differs from the blueprint's {1}".format(summ, em["times"]))
    pts = emit(tr, times, C.rng(n, "drv"), em)
    if design.get("drift_pattern"):
        stays = [leg for leg in design["legs"] if leg["kind"] == "stay"]
        pts = pts + canyon_drift(n, day, pts, design, stays[0]["from"])
    rider = []
    if rdr:
        spec = rdr[0]["fixes"]
        rider = rider_fixes(spec, C.rng(n, "rdr"), walk_centres(n, design, spec, day))
    return pts, rider


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------
ACC_FILTER_M = 25.0


def d_m(p, pin):
    return C.hav_m((p["lat"], p["lng"]), pin)


def qualifies(p, pin, radius, acc_max=ACC_FILTER_M):
    return p.get("accuracy_m") is not None and p["accuracy_m"] <= acc_max and d_m(p, pin) <= radius


def select(points, t_from=None, t_to=None):
    return [p for p in points if (t_from is None or sec(p["ts"]) >= sec(t_from)) and
            (t_to is None or sec(p["ts"]) <= sec(t_to))]


def first_qualifying(points, pin, radius, t_from=None, t_to=None, min_run=3):
    """First fix of the first run of >= min_run consecutive qualifying in-radius fixes (POL-NS-02)."""
    run = []
    for p in select(points, t_from, t_to):
        if qualifies(p, pin, radius):
            run.append(p)
            if len(run) >= min_run:
                return run[0]
        else:
            run = []
    return None


def in_radius_runs(points, pin, radius, t_from=None, t_to=None):
    """Maximal runs of consecutive qualifying fixes: [(first_ts, last_ts, n)]."""
    out, run = [], []
    for p in select(points, t_from, t_to):
        if qualifies(p, pin, radius):
            run.append(p)
        else:
            if run:
                out.append((run[0]["ts"], run[-1]["ts"], len(run)))
            run = []
    if run:
        out.append((run[0]["ts"], run[-1]["ts"], len(run)))
    return out


def fix_at(points, t):
    for p in points:
        if p["ts"] == t:
            return p
    return None


def prev_fix(points, t):
    best = None
    for p in points:
        if sec(p["ts"]) < sec(t):
            best = p
    return best


def fd_kph(a, b):
    """Position-derived speed between two fixes, km/h."""
    dt = C.diff_s(a["ts"], b["ts"])
    return C.hav_m((a["lat"], a["lng"]), (b["lat"], b["lng"])) / dt * 3.6


def rider_presence(track, pin, radius, t_from, t_to):
    sel = select(track, t_from, t_to)
    qual = [p for p in sel if p["accuracy_m"] is not None and p["accuracy_m"] <= ACC_FILTER_M]
    within = [p for p in qual if d_m(p, pin) <= radius]
    return {"n": len(sel), "filtered": [p["accuracy_m"] for p in sel if not (p["accuracy_m"] is not None and
                                                                          p["accuracy_m"] <= ACC_FILTER_M)],
            "qualifying": len(qual), "within": len(within),
            "dist": [round(d_m(p, pin), 1) for p in qual]}


def r1(x):
    return round(x + 0.0, 1)


def cross_track(p, a, b):
    """(offset_m, fraction): perpendicular distance of p from the line a-b and the projection's fraction along a-b
    (local flat projection centred on p)."""
    import math
    lat0 = math.radians(p[0])

    def xy(q):
        return ((q[1] - p[1]) * 111320 * math.cos(lat0), (q[0] - p[0]) * 110574)
    fx, fy = xy(a)
    tx, ty = xy(b)
    seglen2 = (tx - fx) ** 2 + (ty - fy) ** 2
    u = ((0.0 - fx) * (tx - fx) + (0.0 - fy) * (ty - fy)) / seglen2
    cx, cy = fx + u * (tx - fx), fy + u * (ty - fy)
    return math.hypot(cx, cy), u
