"""ROUTE_DEVIATION wild cases 501+. Each spec pulls its statements from the English briefs (en/cases.jsonl)."""
import json, os
from datetime import timedelta
from core import ts, m2, round_up_05
from places import pt
from wild import off

EN = {r["id"]: r for r in (json.loads(l) for l in open(next(p for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "en", "cases.jsonl"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "xhs", "en", "cases.jsonl")] if os.path.exists(p))))}
def st(eid, by="RIDER"):
    r = EN[eid]; return (r["rider_statement"], r["driver_statement"]) if by == "RIDER" else (r["driver_statement"], r["rider_statement"])

# ---- ruling helpers
def rd02(F):
    if not (F["excess"] > 0.20*F["opt"] and F["excess"] > 0.8): return "NO_ACTION", None, None
    if F["refund"] < 0.50: return "NO_ACTION", None, None
    if F["refund"] >= 0.90*F["charged"]: return "FULL_REFUND", m2(F["charged"]), None
    return "PARTIAL_REFUND", F["refund"], None
def rd11(F):
    if F["refund"] < 0.50: return "NO_ACTION", None, None
    return "PARTIAL_REFUND", F["refund"], None
def noact(F): return "NO_ACTION", None, None
def esc(F): return "ESCALATE", None, None
def comp(amt): return lambda F: ("DRIVER_COMPENSATION", amt, amt)

def C(n): return f"{n:05d}"

RD = []
def add(**s): RD.append(s)

# 501 <- EN-RD-01  upfront quote, verbal route change, ECP ERP
claim, cp = st("EN-RD-01")
add(no=501, seed="EN-RD-01", req=ts(2026,8,20,14,5,0), rider="RDR-20501", driver="DRV-20118", tier="RYDE_X", region="East (Changi / Tampines)",
    pickup="changi_t3", dropoff="bugis_hotel",
    legs=[("drive", ["changi_t3", (1.3400,103.9750), (1.3050,103.9300), (1.2950,103.8800), (1.2990,103.8600), "bugis_hotel"], 27)],
    opt_km=19.6, opt_min=24.0, quote=24.50, uplift=8.50, uplift_line="distance_fare",
    gantries=[{"name":"ECP (Fort Rd towards City)","frac":0.62,"amount":3.00,"on_opt":False},{"name":"ECP (Rochor towards City)","frac":0.80,"amount":3.00,"on_opt":False}],
    src="routing-engine-v3.2 (LTA traffic snapshot 14:05; optimal is PIE to Kallang then Nicoll Hwy, no ERP)",
    claim=claim, cp=cp, contested=None,
    rule=rd11, clauses=["POL-RD-11","POL-RD-05","POL-RD-09"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} is UPFRONT_QUOTE with quoted_fare_sgd 24.50 and total_charged {T['charged']}, so POL-RD-11 governs and POL-RD-02 does not run. "
        f"The driver's verbal route change is not an amendment: EV-TRIP-{T['c']:05d} has dropoff_amended_at and pickup_amended_at null, so POL-RD-05 cannot be invoked and the quote stands as booked. "
        f"The two ECP gantries (3.00 + 3.00) sit on the driven route but EV-TRIP-{T['c']:05d}.optimal_route_erp_sgd is 0.00: they are off the optimal corridor and were incurred only because of the unauthorised routing, "
        f"so they are not 'properly chargeable' pass-throughs under POL-RD-11(a)/POL-RD-09. Refund under POL-RD-11(a)+(b) = charged_total {T['charged']} minus quoted 24.50 minus properly chargeable pass-throughs 0.00 = {F['charged']-24.50:.3f}, rounded up to {T['refund']}; that figure contains the 6.00 of off-route ERP as the POL-RD-11(b) correction and it is itemised, not added twice. "
        f"EV-GPS-{T['c']:05d} trace {T['dist']} km vs optimal {T['opt']} km ({T['pct']}%) confirms the deviation but is not needed for the money. PARTIAL_REFUND {T['refund']}."))

# 502 <- EN-RD-02  material detour + driver pattern -> RD-06(b) FULL + referral
claim, cp = st("EN-RD-02")
add(no=502, seed="EN-RD-02", req=ts(2026,8,21,20,40,0), rider="RDR-20502", driver="DRV-20334", tier="RYDE_PLUS", card="RC-SG-2026Q3-RYDEPLUS", region="South (Sentosa / Bukit Merah)",
    pickup="sentosa_gw", dropoff="tiong_bahru",
    legs=[("drive", ["sentosa_gw", (1.2620,103.8200), "telok_blangah", (1.2800,103.8050), (1.2870,103.8180), "tiong_bahru"], 24)],
    pct_target=55.0, prof={"d_dev90":4,"d_trips90":210,"d_devlife":6},
    claim=claim, cp=cp, contested=None,
    rule=lambda F: ("FULL_REFUND", m2(F["charged"]), None), clauses=["POL-RD-01","POL-RD-02","POL-RD-06","POL-GEN-01"], difficulty="HARD", referrals=["POL-RD-06(c) driver-conduct review"],
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace_distance_km {T['dist']} against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km, {T['pct']}%, which passes both POL-RD-01 limbs and exceeds 50%, so the deviation is MATERIAL. "
        f"No advisory (EV-ADVIS-{T['c']:05d}-01 MISSING) and no chat, so POL-RD-03/04 give nothing. POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, partial figure {T['refund']}. "
        f"POL-RD-06 is engaged by materiality: EV-DPROF-{T['c']:05d} deviation_flags_90d 4 with completed_trips_90d 210 establishes a pattern (4 >= 3). Limb (b) uplifts the remedy to FULL_REFUND of charged_total {T['charged']} "
        f"(no pass-through lines on this fare, so nothing is carved out); the POL-RD-02 figure {T['refund']} and the uplifted figure {T['charged']} are stated side by side as the clause requires. Limb (c) adds a driver-conduct referral. "
        f"The rider's other trips and the lifetime prior_deviation_flags counter are not evidence for this trip (POL-GEN-01). FULL_REFUND {T['charged']}."))

# 503 <- EN-RD-03  'navigation told me' with no advisory
claim, cp = st("EN-RD-03")
add(no=503, seed="EN-RD-03", req=ts(2026,8,22,16,20,0), rider="RDR-20503", driver="DRV-20077", region="North-East (Serangoon / Ang Mo Kio)",
    pickup="serangoon_gdn", dropoff="bishan_mrt",
    legs=[("drive", ["serangoon_gdn", (1.3700,103.8640), "amk_ind", (1.3760,103.8500), (1.3600,103.8480), "bishan_mrt"], 29)],
    pct_target=58.0, adv_road="Serangoon Garden Way or Ang Mo Kio Ave 3",
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-RD-03","POL-RD-08"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km vs optimal {T['opt']} km (EV-TRIP-{T['c']:05d}): excess {T['excess']} km, {T['pct']}%, deviation established under POL-RD-01 and MATERIAL. "
        f"The driver says the navigation routed him through the industrial estate. POL-RD-03 exoneration needs a traffic_advisory naming a road on the optimal route with an overlapping window; EV-ADVIS-{T['c']:05d}-01 is MISSING, "
        f"so there is nothing to cite and POL-RD-08 discards the bare assertion. POL-RD-06: EV-DPROF-{T['c']:05d} deviation_flags_90d 0, no pattern, so no uplift and no referral. "
        f"POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}. The rider's 'sixteen minutes every Tuesday' is not a figure the policy uses. PARTIAL_REFUND {T['refund']}."))

# 504 <- EN-RD-04  huge loop, ≥90% -> FULL under RD-02
claim, cp = st("EN-RD-04")
add(no=504, seed="EN-RD-04", req=ts(2026,8,23,18,10,0), rider="RDR-20504", driver="DRV-20291", region="East (Paya Lebar / Tampines)",
    pickup="paya_lebar_sq", dropoff="tampines_mrt",
    legs=[("drive", ["paya_lebar_sq", (1.3230,103.8850), "kallang_pie", (1.3300,103.8900), (1.3420,103.9200), (1.3500,103.9400), "tampines_mrt"], 38)],
    pct_target=250.0, adv_road="the PIE eastbound between Paya Lebar and Tampines",
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-RD-03"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km ({T['pct']}%), established and MATERIAL under POL-RD-01. "
        f"The 'car flashing me' story is not an advisory: EV-ADVIS-{T['c']:05d}-01 is MISSING, so POL-RD-03 cannot be run. POL-RD-06: EV-DPROF-{T['c']:05d} deviation_flags_90d 0, no pattern. "
        f"POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}, which is {F['refund']/F['charged']*100:.1f}% of charged_total - below the 90% line at which POL-RD-02 would convert to FULL_REFUND, so the partial figure stands. PARTIAL_REFUND {T['refund']}."))

# 505 <- EN-RD-05  detour + consequential loss claimed
claim, cp = st("EN-RD-05")
add(no=505, seed="EN-RD-05", req=ts(2026,8,24,5,40,0), rider="RDR-20505", driver="DRV-20160", tier="RYDE_PLUS", card="RC-SG-2026Q3-RYDEPLUS", region="North (Yishun / Sembawang)",
    pickup="yishun_blk", dropoff="changi_t1_arr",
    legs=[("drive", ["yishun_blk", (1.4150,103.8600), "seletar", (1.3900,103.9000), (1.3700,103.9500), (1.3600,103.9800), "changi_t1_arr"], 36)],
    pct_target=40.0, contested=110.0, adv_road="the SLE or TPE",
    claim=claim, cp=cp, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-RD-03","POL-GEN-03"], difficulty="HARD",
    rationale=lambda F,T: (f"amount_contested on DSP-{T['c']:05d} bundles the fare with a rebooking fee that no artifact in the pool evidences; the tribunal rules only on the fare. "
        f"EV-GPS-{T['c']:05d} trace {T['dist']} km vs optimal {T['opt']} km (EV-TRIP-{T['c']:05d}): excess {T['excess']} km, {T['pct']}%, established under POL-RD-01, not MATERIAL. "
        f"The driver's fog explanation has no traffic_advisory behind it (EV-ADVIS-{T['c']:05d}-01 MISSING), so POL-RD-03 is unavailable. POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}. "
        f"Under POL-GEN-03 a PARTIAL_REFUND returns part of the contested amount; the balance of the contested figure (the airline rebooking) is not a fare line and is outside every clause in this corpus. PARTIAL_REFUND {T['refund']}."))

# 506 <- EN-RD-07  upfront quote exceeded, zero deviation, unexplained uplift
claim, cp = st("EN-RD-07")
add(no=506, seed="EN-RD-07", req=ts(2026,8,25,4,30,0), rider="RDR-20506", driver="DRV-20402", tier="RYDE_XL", card="RC-SG-2026Q3-RYDEXL", region="Central (Bishan / Toa Payoh)",
    pickup="toa_payoh_blk", dropoff="changi_t3",
    legs=[("drive", ["toa_payoh_blk", (1.3330,103.8700), (1.3320,103.9100), (1.3400,103.9500), (1.3500,103.9800), "changi_t3"], 24)],
    pct_target=1.5, quote=45.00, uplift=10.20, uplift_line="time_fare", adv_road="the PIE eastbound",
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-11","POL-RD-01"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km: excess {T['excess']} km, {T['pct']}%, so POL-RD-01 establishes NO deviation and a route-based reading ends in NO_ACTION. "
        f"That is the trap. EV-FARE-{T['c']:05d} is UPFRONT_QUOTE with quoted_fare_sgd 45.00 and total_charged {T['charged']}; POL-RD-11(a) refunds any amount by which charged_total exceeds the quote plus properly chargeable pass-throughs, "
        f"and it does so however the route was driven. tolls_erp 0.00, airport_surcharge 0.00 (the trip ends at the airport, it does not originate there), waiting_time_fee 0.00. Refund = {T['charged']} - 45.00 - 0.00 = {F['charged']-45.0:.3f}, rounded up to {T['refund']}. "
        f"The driver is not at fault and no referral is available under POL-RD-06 (no pattern). PARTIAL_REFUND {T['refund']}."))

# 507 <- EN-RD-08  3 km trip driven 11 km, dropped short  (≥90% FULL)
claim, cp = st("EN-RD-08")
add(no=507, seed="EN-RD-08", req=ts(2026,8,26,12,15,0), rider="RDR-20507", driver="DRV-20511", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="East (Changi)",
    pickup="changi_t3", dropoff="changi_beach", dropoff_actual="nicoll_dr",
    legs=[("drive", ["changi_t3", (1.3480,103.9820), (1.3560,103.9700), (1.3700,103.9720), (1.3800,103.9800), "nicoll_dr"], 21)],
    opt_km=3.6, opt_min=7.0, adv_road="Airport Boulevard or Changi Coast Rd", airport=6.0,
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-RD-09"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km, {T['pct']}%, established and MATERIAL under POL-RD-01. No advisory, no chat, no amendment. "
        f"EV-DPROF-{T['c']:05d} deviation_flags_90d 0 so POL-RD-06 gives no uplift. The trip ORIGINATES at Changi Airport, so the 6.00 airport surcharge on EV-FARE-{T['c']:05d} is properly chargeable and stays inside recomputed_fare under POL-RD-02 and POL-RD-09. "
        f"recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']} = {F['refund']/F['charged']*100:.1f}% of charged_total, below the 90% line for FULL_REFUND, so PARTIAL_REFUND {T['refund']}. "
        f"The drop-off 1.1 km short of the pin is recorded on the trip_record but no clause prices it separately."))

# 508 <- EN-RD-09  small detour; usual price is not evidence
claim, cp = st("EN-RD-09")
add(no=508, seed="EN-RD-09", req=ts(2026,8,27,8,15,0), rider="RDR-20508", driver="DRV-20623", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="North (Woodlands)",
    pickup="woodlands_mrt", dropoff="novena_sq",
    legs=[("drive", ["woodlands_mrt", (1.4100,103.7800), (1.3850,103.7900), (1.3600,103.8050), (1.3400,103.8300), "novena_sq"], 34)],
    pct_target=24.0, adv_road="the CTE southbound", prof={"r_filed":3,"r_upheld":1},
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-GEN-01"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km (EV-TRIP-{T['c']:05d}): excess {T['excess']} km, {T['pct']}%; both POL-RD-01 limbs pass (>20% and >0.8 km), deviation established, not MATERIAL. "
        f"The driver's 'CTE queue' has no advisory (EV-ADVIS-{T['c']:05d}-01 MISSING). The rider's 'always under 40' and her prior trips on this pair are context only under POL-GEN-01 and play no part in the arithmetic. "
        f"POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}, above the 0.50 de minimis. PARTIAL_REFUND {T['refund']}."))

# 509 <- EN-RD-10  lost driver, wrong drop-off, consequential loss
claim, cp = st("EN-RD-10")
add(no=509, seed="EN-RD-10", req=ts(2026,8,28,15,10,0), rider="RDR-20509", driver="DRV-20705", region="North (Woodlands)",
    pickup="yew_tee_blk", dropoff="woodlands_cp", dropoff_actual="woodlands_wf",
    legs=[("drive", ["yew_tee_blk", (1.4100,103.7500), (1.4300,103.7600), "woodlands_wf", (1.4500,103.7750), (1.4450,103.7700), "woodlands_wf"], 32)],
    pct_target=75.0, contested=100.0, prof={"d_age":90,"d_trips":210,"d_trips90":150},
    claim=claim, cp=cp, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-RD-06","POL-GEN-03"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km vs optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km, {T['pct']}%, established and MATERIAL. Intent is irrelevant to POL-RD-01: a lost driver deviates exactly as a dishonest one does. "
        f"POL-RD-06: EV-DPROF-{T['c']:05d} deviation_flags_90d 0 of 150 completed, no pattern, so no uplift and no referral. No advisory, no chat. POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}. "
        f"amount_contested includes a bus ticket that no artifact evidences; under POL-GEN-03 the tribunal returns part of the contested amount, and the ticket is outside every clause. PARTIAL_REFUND {T['refund']}."))

# 510 <- EN-RD-11  upfront, wrong turn, silent overcharge
claim, cp = st("EN-RD-11")
add(no=510, seed="EN-RD-11", req=ts(2026,8,29,9,5,0), rider="RDR-20510", driver="DRV-20812", region="Central (Toa Payoh)",
    pickup="toa_payoh_blk", dropoff="kallang_mrt",
    legs=[("drive", ["toa_payoh_blk", (1.3300,103.8600), (1.3220,103.8750), (1.3180,103.8640), "kallang_mrt"], 19)],
    pct_target=42.0, quote=15.80, uplift=10.00, uplift_line="distance_fare",
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-11"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} fare_model UPFRONT_QUOTE, quoted_fare_sgd 15.80, total_charged {T['charged']}, no ERP, no surcharge, no waiting fee. POL-RD-11(a): refund = {T['charged']} - 15.80 = {F['charged']-15.8:.3f}, rounded up to {T['refund']}. "
        f"POL-RD-02 does not run on an upfront trip, so the trace figure on EV-GPS-{T['c']:05d} ({T['dist']} km vs {T['opt']} km) changes nothing about the money. PARTIAL_REFUND {T['refund']}."))

# 511 <- EN-RD-12  estimate not quote, taxi dispatched, rider exonerates driver -> NO_ACTION
claim, cp = st("EN-RD-12")
add(no=511, seed="EN-RD-12", req=ts(2026,8,30,7,50,0), rider="RDR-20511", driver="DRV-20930", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="West (Bukit Batok)",
    pickup="bukit_batok_mrt", dropoff="raffles_place",
    legs=[("drive", ["bukit_batok_mrt", (1.3405,103.7620), (1.3260,103.7900), (1.3050,103.8300), (1.2900,103.8470), "raffles_place"], 31)],
    pct_target=2.0, src="routing-engine-v3.2 (LTA traffic snapshot 07:50; rider requested RYDE_X, dispatched RYDE_TAXI; estimate 22-26 shown at booking)",
    claim=claim, cp=cp, contested=None, rule=noact, clauses=["POL-RD-01","POL-RD-11","POL-GEN-03"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km: excess {T['excess']} km, {T['pct']}%, so POL-RD-01 establishes no deviation, and the rider's own claim_text says the driver followed navigation. "
        f"EV-FARE-{T['c']:05d} is METERED with quoted_fare_sgd null: the 22-26 figure the rider saw was an estimate, not an upfront quote, so POL-RD-11 has no quote to enforce. "
        f"The tier mismatch (RYDE_TAXI dispatched on a RYDE_X request, recorded in optimal_route_source on EV-TRIP-{T['c']:05d}) is not a charge line without a counterpart - every line reconciles to the trace - so POL-RD-10(8) does not fire and POL-RD-09(4) has no phantom line to refund. "
        f"Under POL-GEN-03 the present state stands. NO_ACTION."))

# 512 <- EN-RD-13  navigation off, 14-min gap, ended early -> ESCALATE RD-10(3)
claim, cp = st("EN-RD-13")
add(no=512, seed="EN-RD-13", req=ts(2026,8,31,19,10,0), rider="RDR-20512", driver="DRV-21044", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="Central (Novena)",
    pickup="novena_mrt", dropoff="serangoon_blk", dropoff_actual=(1.3490,103.8720,"Serangoon Ave 2, 600 m short of Blk 231"),
    legs=[("drive", ["novena_mrt", (1.3300,103.8500), (1.3400,103.8600), (1.3460,103.8700), (1.3490,103.8720)], 26)],
    gaps=[(420, 1260)], opt_km=6.1, opt_min=11.0, trip_actual=None,
    claim=claim, cp=cp, contested=None, rule=esc, clauses=["POL-RD-07","POL-RD-10","POL-GEN-02"], difficulty="INDETERMINATE",
    gps_note="Driver device telemetry; a 14-minute dropout covers most of the trip.",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} carries a {F['gaps'][0]['duration_sec']:.0f} s gap (coverage_pct {F['cov']}), far above the 90 s limb (a) of POL-RD-07, and the gap spans the disputed segment. "
        f"Under POL-RD-07(i) the excess across the gap is the straight line between bounding fixes, and under (ii) a deviation cannot be established on this trace alone; the corroborating sources named there are absent - "
        f"EV-CHAT-{T['c']:05d} is empty, EV-FARE-{T['c']:05d} has no gantries, the counterparty_statement denies the route, and trip_record.actual_distance_km is a copy of the trace. "
        f"POL-RD-10(3) therefore fires: the trace is impaired and no corroboration exists. Per POL-GEN-02 the deciding fact would rest on an artifact at weight below the 0.70 floor. ESCALATE; the amount is held. "
        f"A reviewer would need the driver's own device log or the rider's device trace to resolve it."))

# 513 <- EN-RD-14  airport run 38 -> 52 km, 'followed navigation', non-intersecting advisory present
claim, cp = st("EN-RD-14")
add(no=513, seed="EN-RD-14", req=ts(2026,9,1,6,40,0), rider="RDR-20513", driver="DRV-21150", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="North (Woodlands)",
    pickup="woodlands_mrt", dropoff="changi_t2",
    legs=[("drive", ["woodlands_mrt", (1.4000,103.8000), (1.3600,103.8300), (1.3200,103.8500), (1.2850,103.8600), "marina_south", (1.2950,103.8900), (1.3200,103.9400), (1.3450,103.9750), "changi_t2"], 52)],
    pct_target=36.0,
    advisory={"road":"Marina Coastal Expressway (MCE) westbound","type":"CONGESTION","box":(0.50,0.56),"box_off":(-1500,0),"pad":0.001,"from_min":-30,"to_min":90,"sev":"LOW",
              "desc":"Slow traffic on MCE westbound towards AYE.","alt_km":None},
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-RD-03"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km, {T['pct']}%, established under POL-RD-01, not MATERIAL. "
        f"The driver invokes navigation. EV-ADVIS-{T['c']:05d}-01 exists and is COMPLETE, but its geometry is the MCE westbound and intersects_route is false: the optimal SLE-TPE corridor never uses it, so POL-RD-03(a) and (c) fail and the advisory exonerates nothing. "
        f"POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}. PARTIAL_REFUND {T['refund']}."))

# 514 <- EN-RD-15  short trip past two malls, partner fleet flag irrelevant
claim, cp = st("EN-RD-15")
add(no=514, seed="EN-RD-15", req=ts(2026,9,2,10,30,0), rider="RDR-20514", driver="DRV-21231", region="North (Ang Mo Kio / Bishan)",
    pickup="yck_blk", dropoff="bishan_mrt",
    legs=[("drive", ["yck_blk", (1.3720,103.8480), "amk_hub", (1.3630,103.8400), "thomson_plaza", (1.3520,103.8420), "bishan_mrt"], 22)],
    pct_target=95.0, src="routing-engine-v3.2 (LTA traffic snapshot 10:30; fulfilled by partner fleet PF-07)",
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km (EV-TRIP-{T['c']:05d}): excess {T['excess']} km, {T['pct']}%, established and MATERIAL under POL-RD-01. "
        f"No advisory, no chat, no amendment; EV-DPROF-{T['c']:05d} deviation_flags_90d 0 so POL-RD-06 does not uplift. The partner-fleet note in optimal_route_source is not a field any clause reads. "
        f"POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']} ({F['refund']/F['charged']*100:.1f}% of charged_total, below the 90% FULL_REFUND line). PARTIAL_REFUND {T['refund']}."))

# 515 <- EN-RD-16  phone use, missed split, off-route ERP inside RD-02 (anti double count), pattern -> referral
claim, cp = st("EN-RD-16")
add(no=515, seed="EN-RD-16", req=ts(2026,9,3,17,30,0), rider="RDR-20515", driver="DRV-21377", tier="RYDE_PLUS", card="RC-SG-2026Q3-RYDEPLUS", region="West (Jurong)",
    pickup="jurong_blk", dropoff="punggol_blk",
    legs=[("drive", ["jurong_blk", (1.3400,103.7700), (1.3380,103.8100), (1.3400,103.8500), (1.3600,103.8700), "tpe_seletar", (1.4000,103.8950), "punggol_blk"], 61)],
    pct_target=44.0, prof={"d_dev90":3,"d_trips90":180,"d_devlife":5},
    gantries=[{"name":"TPE (Seletar Link towards Punggol)","frac":0.70,"amount":2.00,"on_opt":False},{"name":"TPE (Punggol Rd towards Tampines)","frac":0.82,"amount":2.00,"on_opt":False}],
    msgs=[("RIDER","can you please put the phone down and drive",720)],
    claim=claim, cp=cp, contested=None, rule=lambda F: ("FULL_REFUND", m2(F["charged"]), None), clauses=["POL-RD-01","POL-RD-02","POL-RD-09","POL-RD-06"], difficulty="HARD", referrals=["POL-RD-06(c) driver-conduct review"],
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km vs optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km ({T['pct']}%), established under POL-RD-01 and MATERIAL (over 8.0 km absolute). "
        f"EV-FARE-{T['c']:05d} carries two TPE gantries totalling 4.00 with on_optimal_route false and optimal_route_erp_sgd 0.00. POL-RD-02: recomputed_fare {T['rec']} (no on-route ERP), charged_total {T['charged']}, partial figure {T['refund']}. "
        f"Under POL-RD-09(1) the 4.00 of off-route ERP is ALREADY inside that figure and must not be added again; the wrong partial is {F['refund']+4.0:.2f}. "
        f"POL-RD-06: EV-DPROF-{T['c']:05d} deviation_flags_90d 3 of 180 completed establishes a pattern (3 >= 3). The deviation is MATERIAL and substantiated on this trip's own trace, so limb (b) uplifts the remedy to FULL_REFUND of charged_total: pass-through lines are settled under POL-RD-09 and both gantries are off-route, so nothing is carved out and the uplifted figure is {T['charged']}, stated beside the POL-RD-02 figure {T['refund']}. "
        f"Limb (c) adds the driver-conduct referral; the rider's chat line about the phone is context. FULL_REFUND {T['charged']}."))

# 516 <- EN-RD-17  in-app amendment honoured; phantom ERP refunded
claim, cp = st("EN-RD-17")
add(no=516, seed="EN-RD-17", req=ts(2026,9,4,13,0,0), rider="RDR-20516", driver="DRV-21402", region="West (Clementi)",
    pickup="clementi_blk", dropoff="harbourfront",
    legs=[("drive", ["clementi_blk", (1.3080,103.7700), (1.2950,103.7850), (1.2800,103.8050), (1.2700,103.8150), "harbourfront"], 28)],
    opt_km=11.2, opt_min=17.0, quote=43.10,
    amend={"at_s":240,"orig":"harbourfront","km":11.6,"min":17.5},
    gantries=[{"name":"AYE (Alexandra Rd towards City)","phantom":True,"at":(1.2960,103.8220),"amount":3.00,"min":16,"on_opt":False}], phantom_ids=["AYE (Alexandra Rd towards City)"],
    msgs=[("DRIVER","too many traffic lights this way, can accept the new route?",60),("DRIVER","press accept pls, faster for you",120),("DRIVER","accept the route change",170),("DRIVER","??",200),("RIDER","ok fine",235)],
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-05","POL-RD-09","POL-RD-11"], difficulty="HARD", referrals=["POL-RD-09(4) billing integrity"],
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d} shows dropoff_amended_at 4 minutes into the trip with amended_optimal_distance_km 11.6, so POL-RD-05 is available and the amended route is the baseline; the chat pressure that preceded the rider's 'ok fine' is not a ground the policy prices. "
        f"EV-FARE-{T['c']:05d} is UPFRONT_QUOTE, total_charged {T['charged']}, tolls_erp 3.00 for an AYE gantry. That gantry's coordinates on EV-FARE-{T['c']:05d} lie more than 250 m from every fix on EV-GPS-{T['c']:05d}, so under POL-RD-09(4) it is a phantom line, refundable in full whether or not a deviation exists, and it is not a properly chargeable pass-through under POL-RD-11(a). "
        f"quoted_fare_sgd on EV-FARE-{T['c']:05d} is the re-quote issued on the amendment, 43.10. Refund = charged_total {T['charged']} - quote 43.10 - properly chargeable lines 0.00 = {F['charged']-43.1:.3f}, rounded up to {T['refund']}, which is exactly the phantom line. POL-RD-10(8) is not triggered because the only unmatched line is one refunded under POL-RD-09(4). PARTIAL_REFUND {T['refund']}, referral billing integrity."))

# 517 <- EN-RD-19  app crash, position frozen, auto-complete at double the quote -> RD-11 still decides
claim, cp = st("EN-RD-19")
add(no=517, seed="EN-RD-19", req=ts(2026,9,5,22,5,0), rider="RDR-20517", driver="DRV-21519", region="East (Changi)",
    pickup="changi_t3", dropoff="bugis_hotel",
    legs=[("drive", ["changi_t3", (1.3400,103.9750), (1.3300,103.9300), (1.3200,103.9000), (1.3100,103.8750), "bugis_hotel"], 30)],
    gaps=[(900, 1500)], opt_km=19.6, opt_min=24.0, quote=28.00, uplift=33.50, uplift_line="time_fare", airport=6.0,
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-11","POL-RD-07","POL-RD-09"], difficulty="REVERSAL",
    gps_note="Driver device telemetry; the app stopped reporting mid-trip and resumed at completion.",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} has a {F['gaps'][0]['duration_sec']:.0f} s gap covering the second half of the trip, impaired under POL-RD-07(a), and on a METERED trip POL-RD-10(3) would force ESCALATE. "
        f"But EV-FARE-{T['c']:05d} is UPFRONT_QUOTE with quoted_fare_sgd 28.00: POL-RD-11 needs no trace at all. The trip ORIGINATES at Changi, so the 6.00 airport_surcharge is properly chargeable; tolls 0.00; waiting 0.00. "
        f"Refund = total_charged {T['charged']} - 28.00 - 6.00 = {F['charged']-34.0:.3f}, rounded up to {T['refund']}. The trace defect is named under POL-GEN-02 but the deciding facts (quote and charged_total) sit on EV-FARE-{T['c']:05d} at weight 1.0, so confidence is not capped. PARTIAL_REFUND {T['refund']}."))

# 518 <- EN-RD-20  small excess above de minimis
claim, cp = st("EN-RD-20")
add(no=518, seed="EN-RD-20", req=ts(2026,9,6,8,20,0), rider="RDR-20518", driver="DRV-21633", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="Central (Kallang)",
    pickup="kallang_blk", dropoff="raffles_pl_office",
    legs=[("drive", ["kallang_blk", (1.3120,103.8650), (1.3050,103.8600), (1.2950,103.8580), "raffles_pl_office"], 20)],
    pct_target=26.0, calls=[("DRIVER", 60*60+62*60, 190, True)],
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km (EV-TRIP-{T['c']:05d}): excess {T['excess']} km, {T['pct']}%; both POL-RD-01 limbs pass, deviation established, not MATERIAL. "
        f"No advisory, no rider instruction in EV-CHAT-{T['c']:05d}. POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}, above the 0.50 de minimis. "
        f"The post-trip call on EV-TRIP-{T['c']:05d}.in_app_calls is context: POL-RD-06(c) requires a pattern and EV-DPROF-{T['c']:05d} deviation_flags_90d is 0, so no referral is available. PARTIAL_REFUND {T['refund']}."))

# 519 <- EN-RD-21  followed platform route, rider unhappy -> NO_ACTION
claim, cp = st("EN-RD-21")
add(no=519, seed="EN-RD-21", req=ts(2026,9,7,8,0,0), rider="RDR-20519", driver="DRV-21701", region="West (Clementi / Buona Vista)",
    pickup="clementi_mall", dropoff="one_north", dropoff_actual=(1.3040,103.7860,"Commonwealth Ave W, rider alighted early"),
    legs=[("drive", ["clementi_mall", (1.3120,103.7720), (1.3080,103.7800), (1.3040,103.7860)], 12)],
    opt_km=5.0, opt_min=9.0, msgs=[("RIDER","take Clementi Rd then North Buona Vista, fewer lights",90),("RIDER","hello?",240)],
    claim=claim, cp=cp, contested=None, rule=noact, clauses=["POL-RD-01","POL-RD-04","POL-RD-08"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: the driven portion ends where the rider chose to alight, and the excess is {T['excess']} km, "
        f"which fails POL-RD-01 (a negative or sub-threshold excess is not a deviation). The rider's chat instruction on EV-CHAT-{T['c']:05d} names a road, but POL-RD-04 exonerates a driver who FOLLOWED a rider instruction; it does not oblige a driver to follow one, and a driver on the platform route has nothing to be exonerated from. "
        f"POL-RD-08: the rider carries the initial burden and has not shown an excess; assertions about communication carry no weight. NO_ACTION."))

# 520 <- EN-RD-22 (reworked)  driver-filed: rider asked for a stop in chat, trace corroborates, billed km < trace km -> DRIVER_COMPENSATION under RD-04
claim = ("Passenger messaged me to stop at Sheng Siong in Tampines first, I did, waited, then continued to Pasir Ris. The app billed only the booked distance. "
         "I drove 2.4 km more than I was paid for. I am not asking for anything extra, just the distance I actually drove.")
cp = ("I did ask him to stop at the supermarket, that is true. But he took forever and the fare should have been the same as always. I don't see why I should pay more.")
add(no=520, seed="EN-RD-22", req=ts(2026,9,8,11,30,0), by="DRIVER", rider="RDR-20520", driver="DRV-21855", region="East (Tampines / Pasir Ris)",
    pickup="tampines_hub", dropoff="pasir_ris_blk",
    legs=[("drive", ["tampines_hub", "sheng_siong_tamp"], 4), ("dwell", "sheng_siong_tamp", 240), ("drive", ["sheng_siong_tamp", (1.3620,103.9500), (1.3680,103.9520), "pasir_ris_blk"], 12)],
    opt_km=3.1, opt_min=6.0, bill_km=3.1,
    msgs=[("RIDER","can stop at Sheng Siong Blk 501 first? need to grab something",30,{"lat":pt("sheng_siong_tamp")[0],"lng":pt("sheng_siong_tamp")[1],"label":"Sheng Siong Supermarket, Blk 501 Tampines Central 1"}),("DRIVER","ok",50)],
    claim=claim, cp=cp, contested=None, rule=None, clauses=["POL-RD-04","POL-RD-01","POL-GEN-03"], difficulty="HARD",
    rationale=lambda F,T: (f"Driver-filed. EV-CHAT-{T['c']:05d} MSG-{T['c']:05d}-001 is a rider message 30 s after departure naming Sheng Siong Blk 501 with a populated waypoint_hint; EV-GPS-{T['c']:05d} passes within 200 m of that coordinate and dwells there four minutes, so POL-RD-04(a)-(c) are met and the trace corroborates. "
        f"The stop distance is excluded before POL-RD-01 runs, so no deviation is charged against the driver. EV-FARE-{T['c']:05d} bills distance_charged_km {F['bill_km']} while EV-GPS-{T['c']:05d} trace_distance_km is {T['dist']}: an unbilled shortfall of {F['dist']-F['bill_km']:.2f} km, above the 1.0 km floor in POL-RD-04. "
        f"Compensation = 0.75 x {F['dist']-F['bill_km']:.2f} = {0.75*(F['dist']-F['bill_km']):.3f}, rounded UP to {F['comp']:.2f}, within the 15.00 cap. Per POL-GEN-03 the ruling is DRIVER_COMPENSATION {F['comp']:.2f} with amount_sgd mirroring it; the rider's own charge stands."))

# ---- geometry tuning: (trace target km, opt_km, opt_min); opt_min ~ 1.3-1.5 min/km
TUNE = {501:(25.5,19.6,24.0), 502:(8.8,5.6,9.0), 503:(6.8,4.2,7.5), 504:(24.0,9.4,14.0), 505:(31.0,22.1,27.0), 506:(19.9,19.6,24.0),
        507:(11.4,3.6,7.0), 508:(24.7,19.6,26.0), 509:(17.2,9.6,14.0), 510:(8.9,6.2,10.0), 511:(17.5,17.3,23.0), 512:(9.8,6.1,11.0),
        513:(52.0,38.1,42.0), 514:(11.8,5.1,9.0), 515:(49.0,34.2,40.0), 516:(11.9,11.2,17.0), 517:(20.0,19.6,24.0), 518:(7.9,6.2,10.5),
        520:(5.6,3.1,6.0)}
for s in RD:
    if s["no"] in TUNE:
        tk, ok, om = TUNE[s["no"]]
        drives = [i for i,l in enumerate(s["legs"]) if l[0]=="drive"]
        # put the whole target on the longest drive leg (others keep natural length)
        from core import polyline_km as _pl
        from wild import G as _G
        nat = {i: _pl([_G(w) for w in s["legs"][i][1]]) for i in drives}
        big = max(drives, key=lambda i: nat[i])
        rest = sum(v for i,v in nat.items() if i!=big)
        l = s["legs"][big]; s["legs"][big] = ("drive", l[1], l[2], max(nat[big], tk-rest))
        s.pop("pct_target", None); s["opt_km"]=ok; s["opt_min"]=om
