"""Spec-driven case builder for the wild set (cases 501+ RD, 601+ NS). Reuses core.py invariants."""
import random, math
from datetime import timedelta
from core import *
from places import pt, lab, P

BOX = (1.20, 103.60, 1.50, 104.10)

def off(p, north_m=0.0, east_m=0.0):
    return (p[0] + north_m/111_000, p[1] + east_m/(111_000*math.cos(math.radians(p[0]))))

def G(k):
    return pt(k) if isinstance(k, str) else k

def GL(k):
    return geo(lab(k), *pt(k)) if isinstance(k, str) else geo(k[2], k[0], k[1])

def missing_adv(road, assessed):
    return adm("MISSING", "Artifact absent. The identifier is minted so that the absence itself is citable.", assessed,
               [{"code":"MISSING_ARTIFACT","detail":f"No advisory covers {road} in this window."}])

def check_box(pts):
    for p in pts:
        assert BOX[0] <= p["lat"] <= BOX[2] and BOX[1] <= p["lng"] <= BOX[3], ("out of box", p["lat"], p["lng"])

# ---------------------------------------------------------------- path from legs
def stretch(wps, target_km):
    """Scale interior waypoints away from the chord midpoint until the polyline is target_km long; endpoints fixed."""
    if len(wps) < 3: return wps
    mid = ((wps[0][0]+wps[-1][0])/2, (wps[0][1]+wps[-1][1])/2)
    lo, hi = 0.05, 12.0
    def L(k): return polyline_km([wps[0]] + [(mid[0]+(p[0]-mid[0])*k, mid[1]+(p[1]-mid[1])*k) for p in wps[1:-1]] + [wps[-1]])
    for _ in range(60):
        k = (lo+hi)/2
        if L(k) < target_km: lo = k
        else: hi = k
    k = (lo+hi)/2
    return [wps[0]] + [(round(mid[0]+(p[0]-mid[0])*k,6), round(mid[1]+(p[1]-mid[1])*k,6)) for p in wps[1:-1]] + [wps[-1]]

def build_path(legs, t0, rng, acc=(4.0,12.0)):
    """legs: list of ('drive', [wps...], minutes) | ('dwell', pt, seconds). Continuous timeline from t0."""
    pts = []; t = t0
    for leg in legs:
        if leg[0] == "drive":
            wps = [G(w) for w in leg[1]]; mins = leg[2]
            if len(leg) > 3 and leg[3]: wps = stretch(wps, leg[3])
            t1 = t + timedelta(minutes=mins)
            seg = interp_path(wps, t, t1, rng=rng, acc=acc)
            if pts: seg = seg[1:]  # avoid duplicate timestamp
            pts += seg; t = t1
        else:
            _, c, secs = leg
            t1 = t + timedelta(seconds=secs)
            seg = dwell_points(G(c), t + timedelta(seconds=10), t1, rng=rng)
            pts += seg; t = t1
    return pts, t

def cut_gap(pts, t_from, t_to):
    return [p for p in pts if not (t_from <= p["ts"] <= t_to)]

def gantry(name, p, amount, at, on_opt=True):
    return {"gantry_name": name, "charged_at": fmt(at), "amount_sgd": amount, "on_optimal_route": on_opt,
            "lat": round(p[0], 6), "lng": round(p[1], 6)}

def frac_pt(pts, f):
    p = pts[min(len(pts)-1, int(len(pts)*f))]
    return (p["lat"], p["lng"]), p["ts"]

# ---------------------------------------------------------------- profiles
def profiles(rid, did, snap, region, tier, **kw):
    r = rider_profile(rid, snap, kw.get("r_age",800), kw.get("r_trips",260), kw.get("r_rating",4.80), kw.get("r_filed",1), kw.get("r_upheld",0),
                      kw.get("r_cancel",0.04), kw.get("r_ns",0), dev60=kw.get("r_dev60",0), dev60_sub=kw.get("r_dev60_sub",0),
                      ns30=kw.get("r_ns30",0), cp90=kw.get("cp90",0))
    d = driver_profile(did, snap, kw.get("d_age",1000), kw.get("d_trips",1700), kw.get("d_rating",4.86), kw.get("d_filed",1), kw.get("d_upheld",0),
                       kw.get("d_cancel",0.03), kw.get("d_ns",0), kw.get("d_devlife",0), kw.get("d_accept",0.91), tier, region,
                       dev90=kw.get("d_dev90",0), trips90=kw.get("d_trips90",250), ns30=kw.get("d_ns30",1), trips30=kw.get("d_trips30",110), cp90=kw.get("cp90",0))
    return r, d

# ---------------------------------------------------------------- assembly
def assemble(c, category, disp_kw, trip, gps, chatp, fare, rp, dp, advs, gen, assessed, adm_over=None, notes=None):
    tid = f"TRP-{c:05d}"; adm_over = adm_over or {}; notes = notes or {}
    def A(tok, default):
        return adm_over.get(tok) or adm("COMPLETE", notes.get(tok, default), assessed)
    ev = [envelope(evid(c,"TRIP"),"TRIP_RECORD",tid,"PLATFORM_TELEMETRY",gen,A("TRIP","Trip record, causally ordered."),trip),
          envelope(evid(c,"GPS"),"GPS_TRACE",tid,"PLATFORM_TELEMETRY",gen,A("GPS","Driver device telemetry at 10 s cadence."),gps),
          envelope(evid(c,"CHAT"),"CHAT_LOG",tid,"PLATFORM_TELEMETRY",gen,A("CHAT","In-app chat export for the trip."),chatp),
          envelope(evid(c,"FARE"),"FARE_BREAKDOWN",tid,"PAYMENTS_LEDGER",gen,A("FARE","Ledger line items for the trip."),fare),
          envelope(evid(c,"RPROF"),"RIDER_PROFILE",tid,"PLATFORM_TELEMETRY",gen,A("RPROF",""),rp),
          envelope(evid(c,"DPROF"),"DRIVER_PROFILE",tid,"PLATFORM_TELEMETRY",gen,A("DPROF",""),dp)]
    for k,(src,a,payload) in enumerate(advs,1):
        ev.append(envelope(evid(c,"ADVIS",k),"TRAFFIC_ADVISORY",tid,src,gen,a,payload))
    ids = [e["evidence_id"] for e in ev]
    disp = dispute(c, category, disp_kw["by"], disp_kw["at"], disp_kw["claim"], disp_kw["contested"], ids, disp_kw.get("cp"))
    return case_file(c, disp, ev)

# ---------------------------------------------------------------- RD builder
def build_rd(s):
    """s: spec dict. Returns (case_file, gt, facts)."""
    c = s["no"]; rng = random.Random(c)
    req = s["req"]; acc = req + timedelta(seconds=s.get("acc_s",40)); arr = acc + timedelta(minutes=s.get("arr_min",5))
    start = arr + timedelta(seconds=s.get("board_s",60))
    pts, end = build_path(s["legs"], start, rng)
    for g in s.get("gaps", []):
        pts = cut_gap(pts, start+timedelta(seconds=g[0]), start+timedelta(seconds=g[1]))
    check_box(pts)
    tid = f"TRP-{c:05d}"
    # rider track (optional)
    rtrack = None
    if s.get("rider_track"):
        rtrack = dwell_points(G(s["rider_track"][0]), start+timedelta(seconds=s["rider_track"][1]), start+timedelta(seconds=s["rider_track"][2]), cadence=9, rng=rng, jitter_m=4.0)
    gps, dist, gaps, cov = build_gps(tid, pts, start, end, rider_track=rtrack)
    actual = round(dist, 1) if s.get("trip_actual") is None else s["trip_actual"]
    if s.get("pct_target") is not None:
        opt_km = round(dist/(1+s["pct_target"]/100), 1); opt_min = round(opt_km*s.get("min_per_km",1.45), 1)
    else:
        opt_km, opt_min = s["opt_km"], s["opt_min"]
    direct = haversine_km(G(s["pickup"]), G(s["dropoff_actual"] if s.get("dropoff_actual") else s["dropoff"]))
    assert opt_km >= direct*1.02, ("opt_km below straight line", c, opt_km, direct)
    # gantries
    gl = []
    for gsp in s.get("gantries", []):
        if gsp.get("phantom"):
            p = G(gsp["at"]); t = start + timedelta(minutes=gsp.get("min", 5))
        else:
            p, t = frac_pt(pts, gsp["frac"])
        gl.append(gantry(gsp["name"], p, gsp["amount"], t, gsp.get("on_opt", False)))
    erp_opt = m2(sum(g["amount_sgd"] for g in gl if g["on_optimal_route"]))
    # chat & calls
    msgs = []
    for k, m in enumerate(s.get("msgs", []), 1):
        sender, text, t_off = m[0], m[1], m[2]
        wp = m[3] if len(m) > 3 else None
        chan = m[4] if len(m) > 4 else "IN_APP"
        t = start + timedelta(seconds=t_off)
        msgs.append(msg(c, k, sender, text, t, read=t+timedelta(seconds=25) if sender != "SYSTEM" else t+timedelta(seconds=5), channel=chan, wp=wp))
    chatp = chat(tid, msgs)
    amend = s.get("amend")
    trip = trip_rd(c, s["rider"], s["driver"], req, acc, arr, start, end, GL(s["pickup"]), GL(s["dropoff"]), opt_km, opt_min, actual,
                   vehicle=s.get("tier","RYDE_X"), src=s.get("src","routing-engine-v3.2"), chat_count=len(msgs), erp_opt=erp_opt,
                   drop_amended=(start+timedelta(seconds=amend["at_s"])) if amend else None,
                   orig_drop=GL(amend["orig"]) if amend else None,
                   amend_km=amend.get("km") if amend else None, amend_min=amend.get("min") if amend else None,
                   solo_km=s.get("solo_km"))
    if s.get("calls"):
        trip["in_app_calls"] = [{"placed_by": x[0], "placed_at": fmt(start+timedelta(seconds=x[1])), "duration_sec": x[2], "answered": x[3]} for x in s["calls"]]
    if s.get("dropoff_actual"):  # trip ended short: record actual dropoff coordinates
        trip["dropoff"] = GL(s["dropoff_actual"])
    dur = trip["actual_duration_min"]
    surge = s.get("surge", 1.0)
    fare = fare_metered(tid, s.get("bill_km", actual), dur, surge=surge, gantries=gl, airport=s.get("airport",0.0), waiting=s.get("waiting",0.0),
                        charged_at=end+timedelta(seconds=20), rate_card=s.get("card","RC-SG-2026Q3-RYDEX"))
    if s.get("quote") is not None:
        q = s["quote"]
        fare["fare_model"] = "UPFRONT_QUOTE"; fare["quoted_fare_sgd"] = q
        # lock distance/time lines so base+dist+time+surge+platform == quote (+ uplift on the named line)
        fare["surge_amount"] = 0.0; fare["surge_multiplier"] = 1.0
        fare["time_fare"] = m2(q*0.25); fare["distance_fare"] = m2(q - RD_BASE - RD_PLAT - fare["time_fare"])
        up = s.get("uplift", 0.0)
        if up: fare[s.get("uplift_line","time_fare")] = m2(fare[s.get("uplift_line","time_fare")] + up)
        fare["total_charged"] = m2(fare["base_fare"]+fare["distance_fare"]+fare["time_fare"]+fare["tolls_erp"]+fare["airport_surcharge"]+fare["platform_fee"]+fare["waiting_time_fee"])
    if s.get("fare_override"):
        fare.update(s["fare_override"])
    gen = end + timedelta(hours=s.get("gen_h", 20)); ass = gen + timedelta(seconds=9); snap = gen
    rp, dp = profiles(s["rider"], s["driver"], snap, s.get("region","Central"), s.get("tier","RYDE_X"), **s.get("prof", {}))
    # advisories
    advs = []
    if s.get("advisory"):
        a = s["advisory"]
        if a.get("missing"):
            advs.append(("THIRD_PARTY_LTA", missing_adv(a["road"], ass), None))
        else:
            p0, _ = frac_pt(pts, a["box"][0]); p1, _ = frac_pt(pts, a["box"][1])
            if a.get("box_off"):
                p0 = off(p0, *a["box_off"]); p1 = off(p1, *a["box_off"])
            box = (min(p0[0],p1[0])-a.get("pad",0.002), min(p0[1],p1[1])-a.get("pad",0.002), max(p0[0],p1[0])+a.get("pad",0.002), max(p0[1],p1[1])+a.get("pad",0.002))
            pay = advisory(f"ADV-{20260900+c:08d}-001", a["road"], a["type"], start+timedelta(minutes=a.get("from_min",-60)), start+timedelta(minutes=a.get("to_min",120)),
                           box, a.get("sev","MODERATE"), a["desc"], a.get("src","LTA_DATAMALL"), pts, start, end, alt_km=a.get("alt_km"))
            advs.append(("THIRD_PARTY_LTA", adm("COMPLETE", "LTA DataMall advisory covering the trip window.", ass), pay))
    else:
        advs.append(("THIRD_PARTY_LTA", missing_adv(s.get("adv_road","the optimal corridor"), ass), None))
    # admissibility overrides
    adm_over = {}
    gps_details = []
    if gaps:
        gps_details.append({"code":"GPS_GAP","detail":f"{len(gaps)} gap(s) above 30 s; longest {max(g['duration_sec'] for g in gaps):.0f} s."})
    if cov is not None and cov < 90:
        gps_details.append({"code":"LOW_COVERAGE","detail":f"coverage_pct {cov} across the active window."})
    if abs(dist-actual)/dist > 0.10:
        gps_details.append({"code":"DISTANCE_MISMATCH","detail":f"trace_distance_km {dist:.2f} vs trip_record.actual_distance_km {actual}.","related_evidence_ids":[evid(c,"TRIP")]})
    if gps_details:
        adm_over["GPS"] = adm("IMPAIRED", s.get("gps_note","Driver device telemetry with defects listed."), ass, gps_details)
    for tok, spec in s.get("adm", {}).items():
        adm_over[tok] = adm(spec[0], spec[1], ass, spec[2])
    contested = s["contested"] if s.get("contested") is not None else fare["total_charged"]
    contested = m2(min(contested, fare["total_charged"]))
    cp = (s["cp"], "DRIVER" if s.get("by","RIDER")=="RIDER" else "RIDER", gen - timedelta(hours=2)) if s.get("cp") else None
    cf = assemble(c, "ROUTE_DEVIATION", {"by": s.get("by","RIDER"), "at": end+timedelta(hours=s.get("filed_h",3)), "claim": s["claim"], "contested": contested, "cp": cp},
                  trip, gps, chatp, fare, rp, dp, advs, gen, ass, adm_over, s.get("notes"))
    # ---- facts for the rationale
    F = {"dist": dist, "opt": opt_km, "opt_min": opt_min, "excess": dist-opt_km, "pct": (dist-opt_km)/opt_km*100 if opt_km else 0,
         "charged": fare["total_charged"], "erp_opt": erp_opt, "erp_all": fare["tolls_erp"], "surge": surge, "quote": s.get("quote"),
         "gaps": gaps, "cov": cov, "actual": actual, "cancel": None}
    if s.get("quote") is None:
        F["rec"] = recomputed_fare(opt_km, opt_min, surge, erp_opt, airport_ok=s.get("airport",0.0) if s.get("airport_ok",True) else 0.0, waiting=s.get("waiting",0.0))
        F["refund"] = round_up_05(max(0.0, fare["total_charged"]-F["rec"]))
    else:
        proper = m2(sum(g["amount_sgd"] for g in gl if g["on_optimal_route"] and not (s.get("phantom_ids") and g["gantry_name"] in s["phantom_ids"])) + (s.get("airport",0.0) if s.get("airport_ok",True) else 0.0) + s.get("waiting",0.0))
        F["proper"] = proper
        F["refund"] = round_up_05(max(0.0, fare["total_charged"] - s["quote"] - proper))
    F["phantom"] = m2(sum(g["amount_sgd"] for g in gl if s.get("phantom_ids") and g["gantry_name"] in s["phantom_ids"]))
    F["bill_km"] = s.get("bill_km", actual)
    if s.get("bill_km") is not None:
        F["comp"] = min(15.0, round_up_05(0.75*(dist-s["bill_km"])))
    if s["rule"] is None:  # RD-04 driver compensation
        ruling, amount, comp = "DRIVER_COMPENSATION", F["comp"], F["comp"]
        cf["dispute"]["amount_contested_sgd"] = F["comp"]
    else:
        ruling, amount, comp = s["rule"](F)
    if ruling == "FULL_REFUND":
        cf["dispute"]["amount_contested_sgd"] = amount
    rat = s["rationale"](F, {"c": c, "dist": f"{dist:.2f}", "pct": f"{F['pct']:.1f}", "excess": f"{F['excess']:.2f}", "charged": f"{fare['total_charged']:.2f}",
                              "rec": f"{F.get('rec',0):.3f}", "refund": f"{F['refund']:.2f}", "opt": opt_km, "opt_min": opt_min})
    g = gt(ruling, amount, s["clauses"], s["difficulty"], rat, driver_comp=comp, referrals=s.get("referrals", []))
    return cf, g, F

# ---------------------------------------------------------------- NS builder
def build_ns(s):
    c = s["no"]; rng = random.Random(c); zone, tier = s["zone"], s["tier"]; fee = ns_fee(zone, tier)
    pick = G(s["pick"]); req = s["req"]; acc = req + timedelta(seconds=s.get("acc_s",40))
    tid = f"TRP-{c:05d}"
    # driver path: legs relative to acc
    pts, tend = build_path(s["legs"], acc, rng, acc=s.get("acc_range",(28.0,48.0)))
    if s.get("dwell_acc_fix"):  # ensure dwell fixes good accuracy (build_path uses dwell_points default 5-14 already)
        pass
    cancel = tend if s.get("completed") else acc + timedelta(seconds=s["cancel_s"])
    pts = [p for p in pts if p["ts"] <= cancel]
    for g in s.get("gaps", []):
        pts = cut_gap(pts, acc+timedelta(seconds=g[0]), acc+timedelta(seconds=g[1]))
    check_box(pts)
    arr = acc + timedelta(seconds=s["arr_s"]) if s.get("arr_s") is not None else None
    rtrack = None
    if s.get("rider_track"):
        rt = s["rider_track"]
        rtrack = dwell_points(off(pick, rt[0], rt[1]), acc+timedelta(seconds=rt[2]), acc+timedelta(seconds=rt[3]), cadence=9, rng=rng, jitter_m=4.0)
    if s.get("gps_missing"):
        gps = None; dist = None; gaps = []; cov = None
    else:
        gps, dist, gaps, cov = build_gps(tid, pts, acc, cancel, rider_track=rtrack)
    calls = [(x[0], acc+timedelta(seconds=x[1]), x[2], x[3]) for x in s.get("calls", [])]
    msgs = []
    for k, m in enumerate(s.get("msgs", []), 1):
        sender, text, t_off = m[0], m[1], m[2]
        chan = m[3] if len(m) > 3 else "IN_APP"
        t = acc + timedelta(seconds=t_off)
        read = None if (len(m) > 4 and m[4] is None) else t + timedelta(seconds=(5 if sender=="SYSTEM" else 30))
        msgs.append(msg(c, k, sender, text, t, read=read, channel=chan))
    chatp = chat(tid, msgs)
    if s.get("completed"):
        start = acc + timedelta(seconds=s["completed"]["board_s"]); end = tend
        trip = trip_rd(c, s["rider"], s["driver"], req, acc, arr, start, end, GL(s["pick"]), GL(s["drop"]), s.get("opt_km",9.0), s.get("opt_min",14.0),
                       round(dist,1), vehicle=tier, chat_count=len(msgs))
        trip["pickup_zone_class"] = zone; trip["registered_pickup_points"] = s.get("reg_points",1)
        trip["in_app_calls"] = [{"placed_by": x[0], "placed_at": fmt(x[1]), "duration_sec": x[2], "answered": x[3]} for x in calls]
        fare = fare_metered(tid, round(dist,1), trip["actual_duration_min"], airport=s.get("airport",0.0), charged_at=end+timedelta(seconds=20),
                            rate_card={"RYDE_X":"RC-SG-2026Q3-RYDEX","RYDE_PLUS":"RC-SG-2026Q3-RYDEPLUS","RYDE_XL":"RC-SG-2026Q3-RYDEXL","RYDE_POOL":"RC-SG-2026Q3-RYDEPOOL","RYDE_TAXI":"RC-SG-2026Q3-RYDETAXI"}[tier])
    else:
        trip = trip_ns(c, s["rider"], s["driver"], req, acc, arr, cancel, GL(s["pick"]), GL(s["drop"]), s.get("opt_km",9.0), s.get("opt_min",14.0), zone, tier,
                   reason=s.get("reason","RIDER_NO_SHOW"), cancelled_by=s.get("by_cancel","DRIVER"), reg_points=s.get("reg_points",1), calls=calls, chat_count=len(msgs))
    if s.get("trip_override"): trip.update(s["trip_override"])
    if not s.get("completed"): fare = fare_cancel(tid, fee if s.get("fee") is None else s["fee"], cancel+timedelta(seconds=20), s.get("card") or {"RYDE_X":"RC-SG-2026Q3-RYDEX","RYDE_PLUS":"RC-SG-2026Q3-RYDEPLUS","RYDE_XL":"RC-SG-2026Q3-RYDEXL","RYDE_POOL":"RC-SG-2026Q3-RYDEPOOL","RYDE_TAXI":"RC-SG-2026Q3-RYDETAXI"}[tier],
                       status=s.get("fee_status","CHARGED"), refunded=s.get("refunded",0.0))
    gen = cancel + timedelta(hours=s.get("gen_h", 20)); ass = gen + timedelta(seconds=8); snap = gen
    rp, dp = profiles(s["rider"], s["driver"], snap, s.get("region","Central"), tier, **s.get("prof", {}))
    advs = [("THIRD_PARTY_LTA", missing_adv(s.get("adv_road","the pickup road"), ass), None)]
    adm_over = {}
    if s.get("gps_missing"):
        adm_over["GPS"] = adm("MISSING", "Artifact absent. The identifier is minted so that the absence itself is citable.", ass, [{"code":"MISSING_ARTIFACT","detail":"No driver telemetry was retained for this trip."}])
    else:
        det = []
        if gaps: det.append({"code":"GPS_GAP","detail":f"{len(gaps)} gap(s) above 30 s; longest {max(g['duration_sec'] for g in gaps):.0f} s."})
        if cov is not None and cov < 90: det.append({"code":"LOW_COVERAGE","detail":f"coverage_pct {cov} across the active window."})
        if det: adm_over["GPS"] = adm("IMPAIRED", "Driver device telemetry with defects listed.", ass, det)
    for tok, spec in s.get("adm", {}).items():
        adm_over[tok] = adm(spec[0], spec[1], ass, spec[2])
    contested = fee if s.get("contested") is None else s["contested"]
    cp = (s["cp"], "DRIVER" if s.get("by","RIDER")=="RIDER" else "RIDER", gen - timedelta(hours=2)) if s.get("cp") else None
    cf = assemble(c, "NO_SHOW_CHARGE", {"by": s.get("by","RIDER"), "at": cancel+timedelta(hours=s.get("filed_h",2)), "claim": s["claim"], "contested": contested, "cp": cp},
                  trip, gps, chatp, fare, rp, dp, advs, gen, ass, adm_over, s.get("notes"))
    # facts
    R = NS_ARR_R[zone]
    F = {"fee": fee, "zone": zone, "tier": tier, "R": R, "min_dwell": NS_MIN_DWELL[zone], "cancel": cancel, "arr": arr, "pts": pts}
    if pts:
        dw, q = dwell_sec(pts, pick, R, cancel)
        F["dwell"] = dw; F["q"] = q
        F["dwellc"] = None
        if q is not None:
            after = [p for p in pts if p["ts"] > q["ts"]]
            leave = next((p for p in after if haversine_km((p["lat"],p["lng"]), pick)*1000 > R), None)
            F["dwellc"] = ((leave["ts"] if leave else cancel) - q["ts"]).total_seconds()
        if arr:
            near = min(pts, key=lambda p: abs((p["ts"]-arr).total_seconds()))
            F["d_at_arr"] = haversine_km((near["lat"],near["lng"]), pick)*1000; F["v_at_arr"] = near["speed_kph"]
        # stationary distance: median distance of last 60 s fixes before cancel
        tail = [p for p in pts if (cancel - p["ts"]).total_seconds() <= 60]
        F["d_tail"] = sorted(haversine_km((p["lat"],p["lng"]), pick)*1000 for p in tail)[len(tail)//2] if tail else None
        F["d_min"] = min(haversine_km((p["lat"],p["lng"]), pick)*1000 for p in pts)
    if rtrack:
        good = [p for p in rtrack if p["accuracy_m"] <= 25]
        inside = [p for p in good if haversine_km((p["lat"],p["lng"]), pick)*1000 <= {"STANDARD":100,"LARGE_VENUE":150,"TRANSPORT_HUB":200,"AIRPORT":200}[zone]]
        F["rider_in_frac"] = len(inside)/len(good) if good else None
        F["rider_d"] = sum(haversine_km((p["lat"],p["lng"]), pick) for p in rtrack)/len(rtrack)*1000
    ruling, amount, comp = s["rule"](F)
    rat = s["rationale"](F, {"c": c, "fee": f"{fee:.2f}", "dwell": (f"{F['dwell']:.0f}" if F.get("dwell") is not None else "none"),
                              "q": (F["q"]["ts"].strftime("%H:%M:%S") if F.get("q") else "none"), "R": R, "min": NS_MIN_DWELL[zone],
                              "d_at_arr": (f"{F['d_at_arr']:.0f}" if F.get("d_at_arr") is not None else "n/a"), "v_at_arr": (f"{F['v_at_arr']}" if F.get("v_at_arr") is not None else "n/a"),
                              "d_tail": (f"{F['d_tail']:.0f}" if F.get("d_tail") is not None else "n/a"), "d_min": (f"{F['d_min']:.0f}" if F.get("d_min") is not None else "n/a"),
                              "rider_d": (f"{F['rider_d']:.0f}" if F.get("rider_d") is not None else "n/a"), "cancel": cancel.strftime("%H:%M:%S"),
                              "arr": arr.strftime("%H:%M:%S") if arr else "none", "comp": f"{fee*0.8:.2f}", "dwellc": (f"{F['dwellc']:.0f}" if F.get("dwellc") is not None else "none")})
    g = gt(ruling, amount, s["clauses"], s["difficulty"], rat, driver_comp=comp, referrals=s.get("referrals", []))
    return cf, g, F
