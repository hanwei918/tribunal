"""Billing-flavoured ROUTE_DEVIATION cases 521+ (ERP, upfront quotes, pool, estimates, scope)."""
from core import ts, m2
from places import pt
from specs_rd import RD, add, st, rd02, rd11, noact, esc

# 521 <- EN-BL-01 phantom ERP on upfront taxi trip
claim, cp = st("EN-BL-01")
add(no=521, seed="EN-BL-01", req=ts(2026,9,9,21,30,0), rider="RDR-20521", driver="DRV-22011", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="Central (Tanjong Pagar)",
    pickup="raffles_pl_office", dropoff="tiong_bahru",
    legs=[("drive", ["raffles_pl_office", (1.2790,103.8450), (1.2820,103.8350), "tiong_bahru"], 12, 4.1)],
    opt_km=3.9, opt_min=8.0, quote=10.00,
    gantries=[{"name":"CTE (Braddell Rd towards City)","phantom":True,"at":(1.3420,103.8600),"amount":2.00,"min":11,"on_opt":False}], phantom_ids=["CTE (Braddell Rd towards City)"],
    claim=claim, cp=cp, contested=2.00, rule=lambda F: ("FULL_REFUND", F["refund"], None), clauses=["POL-RD-09","POL-RD-11"], difficulty="EASY", referrals=["POL-RD-09(4) billing integrity"],
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} is UPFRONT_QUOTE, quoted_fare_sgd 10.00, total_charged {T['charged']}, with a single erp_gantry line of 2.00 named for the CTE at Braddell. Its coordinates lie about 7 km from every fix on EV-GPS-{T['c']:05d}, "
        f"far outside the 250 m matching window in POL-RD-09(4), and the trace ({T['dist']} km, Tanjong Pagar to Tiong Bahru) never enters the CTE. The line is a billing-integrity failure and is refunded in full as a standalone correction whether or not a deviation exists; POL-RD-10(8) is not engaged for a line refunded under this limb. "
        f"Under POL-RD-11(b) the same correction applies on an upfront trip. Refund = {T['charged']} - 10.00 - 0.00 properly chargeable = {F['charged']-10.0:.2f} -> {T['refund']}. The contested amount on DSP-{T['c']:05d} is exactly this line, so under POL-GEN-03 the filing party is entirely right on the whole contested sum: FULL_REFUND {T['refund']}; referral billing integrity."))

# 522 <- EN-BL-02 'pay ERP cash' + app also bills ERP on optimal route -> NO_ACTION
claim, cp = st("EN-BL-02")
add(no=522, seed="EN-BL-02", req=ts(2026,9,10,7,55,0), rider="RDR-20522", driver="DRV-22087", region="North (Woodlands)",
    pickup="woodlands_mrt", dropoff="raffles_place",
    legs=[("drive", ["woodlands_mrt", (1.4150,103.7950), (1.3900,103.8100), (1.3550,103.8300), (1.3150,103.8600), (1.2950,103.8620), "raffles_place"], 41, 25.2)],
    opt_km=24.8, opt_min=33.0, gantries=[{"name":"CTE (Braddell Rd towards City)","frac":0.62,"amount":5.00,"on_opt":True}],
    claim=claim, cp=cp, contested=5.00, rule=noact, clauses=["POL-RD-09","POL-RD-01","POL-GEN-03"], difficulty="HARD",
    rationale=lambda F,T: (f"The contested 5.00 is the ERP line on EV-FARE-{T['c']:05d}. EV-GPS-{T['c']:05d} passes within 250 m of that gantry's coordinates and EV-TRIP-{T['c']:05d}.optimal_route_erp_sgd is 5.00: the gantry lies on the optimal route and was actually crossed, so under POL-RD-09 it is a legitimate pass-through, not a phantom line. "
        f"Trace {T['dist']} km vs optimal {T['opt']} km ({T['pct']}%) establishes no deviation under POL-RD-01, so no refund route exists under POL-RD-02 or POL-RD-09(1). The cash the rider says she handed over is recorded nowhere in the pool and cannot be refunded by this tribunal; "
        f"POL-RD-06(c) requires a pattern and EV-DPROF-{T['c']:05d} deviation_flags_90d is 0, so no referral is available. Under POL-GEN-03 the present state stands. NO_ACTION."))

# 523 <- EN-BL-05 driver chose ECP unasked, ERP crossed, distance excess below threshold -> NO_ACTION (policy has no refund route)
claim, cp = st("EN-BL-05")
add(no=523, seed="EN-BL-05", req=ts(2026,9,11,15,20,0), rider="RDR-20523", driver="DRV-22150", region="East (Changi)",
    pickup="changi_t3", dropoff="chinatown",
    legs=[("drive", ["changi_t3", (1.3400,103.9750), (1.3000,103.9200), (1.2900,103.8800), (1.2800,103.8600), "chinatown"], 30, 21.2)],
    opt_km=19.8, opt_min=25.0, airport=6.0, gantries=[{"name":"ECP (Fort Rd towards City)","frac":0.55,"amount":4.00,"on_opt":False}],
    src="routing-engine-v3.2 (LTA traffic snapshot 15:20; optimal is PIE then Nicoll Hwy, no ERP)",
    claim=claim, cp=cp, contested=4.00, rule=noact, clauses=["POL-RD-01","POL-RD-09","POL-RD-11"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km, {T['pct']}%, which fails the 20% limb of POL-RD-01, so no deviation is established. "
        f"The contested 4.00 ERP line is an ECP gantry with on_optimal_route false, and the trace passes within 250 m of it, so it is neither phantom (POL-RD-09(4)) nor rider-caused. POL-RD-09(1) refunds off-route ERP only inside a POL-RD-02 recomputation, and POL-RD-02 runs only on an established deviation; POL-RD-09(2) applies only to a POL-RD-03 exoneration; "
        f"the trip is METERED so POL-RD-11(b) is not available either. The airport_surcharge 6.00 is proper on a trip ORIGINATING at Changi. There is no clause under which this gantry is refundable, and the cash the rider handed over is not in the pool. NO_ACTION; the ruling should say the policy leaves a sub-threshold route choice with the driver."))

# 524 <- EN-BL-06 upfront +3.20 'time overage'
claim, cp = st("EN-BL-06")
add(no=524, seed="EN-BL-06", req=ts(2026,9,12,18,40,0), rider="RDR-20524", driver="DRV-22203", region="Central (Kallang)",
    pickup="kallang_blk", dropoff="farrer_park",
    legs=[("drive", ["kallang_blk", (1.3150,103.8620), (1.3130,103.8570), "farrer_park"], 13, 3.4)],
    opt_km=3.3, opt_min=8.0, quote=12.90, uplift=3.20, uplift_line="time_fare",
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-11"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} fare_model UPFRONT_QUOTE, quoted_fare_sgd 12.90, total_charged {T['charged']}; no ERP, surcharge or waiting fee. POL-RD-11 fixes distance and time at booking, so a 'time overage' line has nothing to attach to. "
        f"Refund = {T['charged']} - 12.90 = {F['charged']-12.9:.2f} -> {T['refund']}. EV-GPS-{T['c']:05d} ({T['dist']} km vs {T['opt']} km) shows the route was optimal, which is irrelevant to the money on an upfront trip. PARTIAL_REFUND {T['refund']}."))

# 525 <- EN-BL-07 taxi driver keyed 17.50 against a 13.00 quote; meter log missing; disputes counter -> referral not licensed w/o pattern
claim, cp = st("EN-BL-07")
add(no=525, seed="EN-BL-07", req=ts(2026,9,13,12,10,0), rider="RDR-20525", driver="DRV-22319", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="East (Bedok)",
    pickup="bedok_mall", dropoff="marine_parade",
    legs=[("drive", ["bedok_mall", (1.3180,103.9250), (1.3080,103.9150), "marine_parade"], 14, 4.6)],
    opt_km=4.4, opt_min=9.0, quote=13.00, uplift=4.50, uplift_line="distance_fare", prof={"d_filed":4,"d_upheld":2},
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-11","POL-GEN-01"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} is UPFRONT_QUOTE with quoted_fare_sgd 13.00 and total_charged {T['charged']}: the driver's manually keyed figure sits in the distance line. POL-RD-11(a) refunds the whole excess over the quote: {T['charged']} - 13.00 = {F['charged']-13.0:.2f} -> {T['refund']}. "
        f"No meter log is in the pool, but none is needed - the quote and the charged total are both on the fare artifact at weight 1.0. EV-DPROF-{T['c']:05d} prior_disputes_filed 4 is a lifetime field that POL-GEN-01 makes context only, and deviation_flags_90d is 0, so no POL-RD-06(c) referral can issue. PARTIAL_REFUND {T['refund']}."))

# 526 <- EN-BL-08 price range shown, taxi dispatched, metered 46.50, route optimal -> NO_ACTION
claim, cp = st("EN-BL-08")
add(no=526, seed="EN-BL-08", req=ts(2026,9,14,23,30,0), rider="RDR-20526", driver="DRV-22440", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="West (Jurong)",
    pickup="jurong_east_mrt", dropoff="great_world",
    legs=[("drive", ["jurong_east_mrt", (1.3300,103.7600), (1.3150,103.7900), (1.3000,103.8150), "great_world"], 28, 15.9)],
    opt_km=15.6, opt_min=22.0, src="routing-engine-v3.2 (LTA traffic snapshot 23:30; rider selected RYDE_X, display 'up to 26.00'; dispatched RYDE_TAXI)",
    claim=claim, cp=cp, contested=None, rule=noact, clauses=["POL-RD-01","POL-RD-11","POL-GEN-03"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km: excess {T['excess']} km ({T['pct']}%), no deviation under POL-RD-01. EV-FARE-{T['c']:05d} is METERED with quoted_fare_sgd null; the 'up to 26.00' the rider saw is a display range recorded only in optimal_route_source on EV-TRIP-{T['c']:05d}, not a quoted_fare_sgd, so POL-RD-11 has nothing to enforce. "
        f"Every metered line reconciles to the trace and rate card, so POL-RD-10(8) does not fire and POL-RD-09(4) has no phantom line. The tier substitution is a platform matter outside every clause in this corpus. Under POL-GEN-03 the charge stands. NO_ACTION."))

# 527 <- EN-BL-09 pool rider measures against solo optimal; matched itinerary governs -> NO_ACTION
claim, cp = st("EN-BL-09")
add(no=527, seed="EN-BL-09", req=ts(2026,9,15,17,15,0), rider="RDR-20527", driver="DRV-22502", tier="RYDE_POOL", card="RC-SG-2026Q3-RYDEPOOL", region="West (Jurong / Clementi)",
    pickup="ntu", dropoff="punggol_mrt",
    legs=[("drive", ["ntu", (1.3450,103.7100), "jurong_condo", (1.3400,103.7500), "clementi_blk", (1.3300,103.8000), (1.3400,103.8500), (1.3700,103.8800), "sengkang_mrt", "punggol_mrt"], 95, 61.0)],
    opt_km=58.4, opt_min=82.0, solo_km=32.4, src="routing-engine-v3.2 (pooled itinerary POOL-7731 matched at 17:16; 4 riders)",
    claim=claim, cp=cp, contested=110.0, rule=noact, clauses=["POL-RD-12","POL-RD-01"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d} vehicle_type is RYDE_POOL, so POL-RD-12 sets the baseline at the MATCHED-ITINERARY optimal_distance_km {T['opt']} km, not solo_optimal_distance_km 32.4 km, which is carried for reference only. "
        f"The rider's claim measures her bill against the solo figure; a claim that cites solo_optimal_distance_km has cited the wrong field and fails on that ground alone. Against the matched itinerary, EV-GPS-{T['c']:05d} trace {T['dist']} km is an excess of {T['excess']} km ({T['pct']}%), which fails POL-RD-01, so POL-RD-02 does not run. "
        f"Both figures are named as the clause requires: matched {T['opt']} km, solo 32.4 km. The fare on EV-FARE-{T['c']:05d} reconciles to the trace. NO_ACTION."))

# 528 <- EN-BL-10 estimate exceeded, optimal route, metered lines reconcile -> NO_ACTION
claim, cp = st("EN-BL-10")
add(no=528, seed="EN-BL-10", req=ts(2026,9,16,8,10,0), rider="RDR-20528", driver="DRV-22611", tier="RYDE_PLUS", card="RC-SG-2026Q3-RYDEPLUS", region="North (Sembawang)",
    pickup="sembawang_mrt", dropoff="suntec",
    legs=[("drive", ["sembawang_mrt", (1.4300,103.8250), (1.3900,103.8350), (1.3500,103.8450), (1.3100,103.8550), "suntec"], 38, 22.4)],
    opt_km=22.1, opt_min=36.0, surge=1.4, src="routing-engine-v3.2 (LTA traffic snapshot 08:10; estimate shown 58-62 before surge)",
    claim=claim, cp=cp, contested=30.0, rule=noact, clauses=["POL-RD-01","POL-RD-02","POL-RD-11"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km vs optimal {T['opt']} km: excess {T['excess']} km, {T['pct']}%, no deviation under POL-RD-01. EV-FARE-{T['c']:05d} is METERED, quoted_fare_sgd null, surge_multiplier 1.4 read from the fare artifact as POL-RD-02 requires; "
        f"the 58-62 figure was a pre-surge estimate recorded only in optimal_route_source. With no deviation POL-RD-02 does not run, and a recomputation would be a discretionary exercise the clause forbids where no deviation exists (for the record: {T['rec']} on the optimal route at surge 1.4 against charged {T['charged']}, the gap being metered time in traffic). No phantom line, no amendment, no advisory. NO_ACTION."))

# 529 <- EN-BL-11 taxi in a jam: waiting-time line stands
claim, cp = st("EN-BL-11")
add(no=529, seed="EN-BL-11", req=ts(2026,9,17,18,25,0), rider="RDR-20529", driver="DRV-22705", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="Central (Orchard)",
    pickup="ion_orchard", dropoff="great_world",
    legs=[("drive", ["ion_orchard", (1.3020,103.8300), (1.2980,103.8320), "great_world"], 24, 2.6)],
    opt_km=2.5, opt_min=9.0, waiting=3.08, calls=[("DRIVER", 24*60+40*60, 100, True)],
    claim=claim, cp=cp, contested=5.40, rule=noact, clauses=["POL-RD-01","POL-RD-02"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km: excess {T['excess']} km, no deviation under POL-RD-01. The contested amount is the time and waiting element of a metered fare in congestion; POL-RD-02 counts fare_breakdown.waiting_time_fee as part of the recomputed fare, "
        f"and with no deviation the clause does not run at all. EV-FARE-{T['c']:05d} reconciles line by line. The driver's post-trip call on EV-TRIP-{T['c']:05d}.in_app_calls is context; POL-RD-06(c) needs a pattern and EV-DPROF-{T['c']:05d} deviation_flags_90d is 0. NO_ACTION."))

# 530 <- EN-BL-12 fixed commute, taxi via Balestier, 22% -> PARTIAL; usual price not evidence
claim, cp = st("EN-BL-12")
add(no=530, seed="EN-BL-12", req=ts(2026,9,18,8,0,0), rider="RDR-20530", driver="DRV-22816", tier="RYDE_TAXI", card="RC-SG-2026Q3-RYDETAXI", region="North-East (Hougang)",
    pickup="hougang_blk", dropoff="raffles_place",
    legs=[("drive", ["hougang_blk", (1.3600,103.8850), (1.3400,103.8600), (1.3250,103.8500), (1.3050,103.8520), "raffles_place"], 34, 17.1)],
    opt_km=13.9, opt_min=22.0, prof={"r_trips":900},
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-GEN-01"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km, {T['pct']}%; both POL-RD-01 limbs pass, deviation established, not MATERIAL. The 'bus breakdown' has no advisory (EV-ADVIS-{T['c']:05d}-01 MISSING). "
        f"The rider's usual fare on RYDE_X is not the benchmark: POL-RD-02 recomputes on the optimal route at the rate card and tier actually billed. recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}. EV-RPROF-{T['c']:05d} lifetime_trips is context only (POL-GEN-01). PARTIAL_REFUND {T['refund']}."))

# 531 <- EN-BL-13 quote honoured exactly, cash 'airport surcharge' demanded off-app -> NO_ACTION
claim, cp = st("EN-BL-13")
add(no=531, seed="EN-BL-13", req=ts(2026,9,19,22,45,0), rider="RDR-20531", driver="DRV-22930", region="East (Changi)",
    pickup="changi_t2", dropoff="paya_lebar_sq",
    legs=[("drive", ["changi_t2", (1.3450,103.9750), (1.3300,103.9400), (1.3220,103.9100), "paya_lebar_sq"], 22, 15.8)],
    opt_km=15.5, opt_min=20.0, quote=27.90, msgs=[("DRIVER","airport surcharge cannot in app, paynow 40 pls",-120),("RIDER","ok sent",-60)],
    claim=claim, cp=cp, contested=27.90, rule=noact, clauses=["POL-RD-11","POL-RD-01","POL-GEN-03"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} is UPFRONT_QUOTE with quoted_fare_sgd 27.90 and total_charged {T['charged']}: charged equals the quote, no ERP, no surcharge line (the trip ORIGINATES at Changi, so a 6.00 surcharge would have been chargeable but none was billed), so POL-RD-11(a) yields zero and (b) has no phantom line. "
        f"EV-GPS-{T['c']:05d} {T['dist']} km vs {T['opt']} km, no deviation. The 40.00 PayNow transfer the rider describes, and the driver's message requesting it on EV-CHAT-{T['c']:05d}, are outside every monetary clause; POL-RD-06(c) requires a pattern and EV-DPROF-{T['c']:05d} deviation_flags_90d is 0. "
        f"Under POL-GEN-03 the platform charge stands. NO_ACTION."))

# 532 <- EN-BL-14 upfront with ERP allowance never crossed (phantom) + detour for an extra passenger -> refund the phantom only
claim, cp = st("EN-BL-14")
add(no=532, seed="EN-BL-14", req=ts(2026,9,20,16,0,0), rider="RDR-20532", driver="DRV-23004", region="North (Woodlands)",
    pickup="woodlands_mrt", dropoff="bedok_blk12",
    legs=[("drive", ["woodlands_mrt", (1.4200,103.8000), (1.3900,103.8400), (1.3600,103.8800), (1.3400,103.9100), (1.3300,103.9250), "bedok_blk12"], 48, 31.5)],
    opt_km=28.0, opt_min=36.0, quote=75.00,
    gantries=[{"name":"CTE (Ang Mo Kio Ave 1 towards City)","phantom":True,"at":(1.3700,103.8470),"amount":6.00,"min":14,"on_opt":True}], phantom_ids=["CTE (Ang Mo Kio Ave 1 towards City)"],
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-11","POL-RD-09","POL-RD-01"], difficulty="HARD", referrals=["POL-RD-09(4) billing integrity"],
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} is UPFRONT_QUOTE, quoted_fare_sgd 75.00, total_charged {T['charged']}, with one ERP line of 6.00 for a CTE gantry flagged on_optimal_route true. EV-GPS-{T['c']:05d} never passes within 250 m of that gantry's coordinates - the driver stayed on local roads - so under POL-RD-09(4) the line is phantom and refundable in full as a billing-integrity correction, which POL-RD-11(b) carries onto an upfront trip. "
        f"The trace {T['dist']} km against optimal {T['opt']} km ({T['pct']}%) does not pass the 20% limb of POL-RD-01, and under POL-RD-11 no distance refund exists anyway, so the extra passenger's leg changes nothing about the money. Refund = {T['charged']} - 75.00 - 0.00 = {F['charged']-75.0:.2f} -> {T['refund']}. PARTIAL_REFUND {T['refund']}, referral billing integrity."))

# 533 <- EN-BL-18 quote + genuine on-route ERP + unexplained 'service adjustment'
claim, cp = st("EN-BL-18")
add(no=533, seed="EN-BL-18", req=ts(2026,9,21,9,20,0), rider="RDR-20533", driver="DRV-23120", tier="RYDE_PLUS", card="RC-SG-2026Q3-RYDEPLUS", region="North (Yishun)",
    pickup="yishun_mrt", dropoff="novena_sq",
    legs=[("drive", ["yishun_mrt", (1.4100,103.8350), (1.3800,103.8400), (1.3500,103.8450), "novena_sq"], 26, 14.6)],
    opt_km=14.2, opt_min=21.0, quote=29.00, uplift=19.30, uplift_line="time_fare",
    gantries=[{"name":"CTE (Ang Mo Kio Ave 1 towards City)","frac":0.55,"amount":3.00,"on_opt":True}],
    claim=claim, cp=cp, contested=None, rule=rd11, clauses=["POL-RD-11","POL-RD-09"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-FARE-{T['c']:05d} is UPFRONT_QUOTE, quoted_fare_sgd 29.00, total_charged {T['charged']}, tolls_erp 3.00. The CTE gantry has on_optimal_route true, EV-TRIP-{T['c']:05d}.optimal_route_erp_sgd is 3.00 and EV-GPS-{T['c']:05d} passes within 250 m of it, so under POL-RD-09 it is an ERP charge actually crossed on the optimal route and a properly chargeable pass-through under POL-RD-11(a). "
        f"Refund = charged_total {T['charged']} - quote 29.00 - proper pass-throughs 3.00 = {F['charged']-32.0:.2f} -> {T['refund']}: the unexplained uplift only. The ERP stays. Route {T['dist']} km vs {T['opt']} km is optimal and irrelevant under POL-RD-11. PARTIAL_REFUND {T['refund']}."))

# 534 <- EN-SC-03 solo scheduled ride drifts 5.6 km to collect another passenger -> RD-02 partial
claim, cp = st("EN-SC-03")
add(no=534, seed="EN-SC-03", req=ts(2026,9,22,17,0,0), rider="RDR-20534", driver="DRV-23255", region="East (Bedok / Tampines)",
    pickup="bedok_blk12", dropoff="pasir_ris_mrt",
    legs=[("drive", ["bedok_blk12", (1.3300,103.9350), (1.3350,103.9450), "bedok_res"], 11, 4.2), ("dwell", "bedok_res", 240), ("drive", ["bedok_res", (1.3500,103.9450), (1.3650,103.9500), "pasir_ris_mrt"], 12, 5.9)],
    opt_km=7.4, opt_min=13.0, msgs=[("DRIVER","setting off now",-300)],
    claim=claim, cp=cp, contested=None, rule=rd02, clauses=["POL-RD-01","POL-RD-02","POL-RD-04"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km on EV-TRIP-{T['c']:05d}: excess {T['excess']} km, {T['pct']}%, established under POL-RD-01, not MATERIAL. The four-minute stop at Bedok Reservoir was not requested by the rider: EV-CHAT-{T['c']:05d} has only the driver's 'setting off now', so POL-RD-04 cannot exonerate. "
        f"vehicle_type is RYDE_X, not RYDE_POOL, so POL-RD-12 does not apply and the co-rider's leg is ordinary excess. POL-RD-02: recomputed_fare {T['rec']}, charged_total {T['charged']}, refund {T['refund']}. PARTIAL_REFUND {T['refund']}."))

# 535 <- EN-SC-06 delay on the optimal route with an intersecting incident advisory -> NO_ACTION
claim, cp = st("EN-SC-06")
add(no=535, seed="EN-SC-06", req=ts(2026,9,23,6,50,0), rider="RDR-20535", driver="DRV-23388", region="North-East (Hougang)",
    pickup="hougang_mall", dropoff="woodlands_cp",
    legs=[("drive", ["hougang_mall", (1.3800,103.8800), (1.4000,103.8500), (1.4200,103.8100), (1.4400,103.7800), "woodlands_cp"], 67, 20.4)],
    opt_km=20.1, opt_min=44.0, contested=30.0,
    advisory={"road":"SLE northbound near Lentor exit","type":"ACCIDENT","box":(0.45,0.55),"pad":0.002,"from_min":-20,"to_min":60,"sev":"HIGH","desc":"Multi-vehicle accident, two lanes closed.","alt_km":22.8},
    claim=claim, cp=cp, rule=noact, clauses=["POL-RD-01","POL-RD-03","POL-GEN-03"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km: excess {T['excess']} km, {T['pct']}%, no deviation under POL-RD-01; the driver stayed on the optimal corridor and EV-ADVIS-{T['c']:05d}-01 (ACCIDENT, intersects_route true, overlapping the trip window) explains the 67-minute duration. "
        f"Delay is not a route breach: POL-RD-02 recomputes distance and time against the optimal route only where a deviation exists, and POL-RD-03 exonerates deviations, it does not create refunds for slow trips. The rebooking costs in the contested amount have no artifact and no clause. Under POL-GEN-03 the fare stands. NO_ACTION."))

# 536 <- EN-SC-07 dropped 210 m short, route optimal -> NO_ACTION
claim, cp = st("EN-SC-07")
add(no=536, seed="EN-SC-07", req=ts(2026,9,24,13,5,0), rider="RDR-20536", driver="DRV-23490", region="Central (Marina)",
    pickup="suntec", dropoff="marina_south", dropoff_actual=(1.2727,103.8628,"Marina Coastal Dr, 210 m short of the pier"),
    legs=[("drive", ["suntec", (1.2900,103.8620), (1.2800,103.8640), (1.2727,103.8628)], 12, 3.1)],
    opt_km=3.2, opt_min=8.0,
    claim=claim, cp=cp, contested=None, rule=noact, clauses=["POL-RD-01","POL-GEN-03"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km: the excess is {T['excess']} km, negative, because the trip ended 210 m before the pin; POL-RD-01 establishes no deviation on a shortfall. "
        f"EV-FARE-{T['c']:05d} bills the distance actually driven, so no line lacks a counterpart and POL-RD-10(8) does not fire. No clause in this corpus prices a drop-off short of the destination pin; under POL-GEN-03 the fare stands. NO_ACTION. (The frozen policy's silence on drop-off shortfall is worth recording for the reviewer.)"))

# 537 <- EN-SG-02 surge, optimal route -> NO_ACTION
claim, cp = st("EN-SG-02")
add(no=537, seed="EN-SG-02", req=ts(2026,9,25,21,0,0), rider="RDR-20537", driver="DRV-23511", region="Central (Novena)",
    pickup="novena_sq", dropoff="great_world",
    legs=[("drive", ["novena_sq", (1.3150,103.8400), (1.3050,103.8350), "great_world"], 19, 4.6)],
    opt_km=4.5, opt_min=11.0, surge=2.2,
    claim=claim, cp=cp, contested=None, rule=noact, clauses=["POL-RD-01","POL-RD-02"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} trace {T['dist']} km against optimal {T['opt']} km: excess {T['excess']} km, no deviation under POL-RD-01. EV-FARE-{T['c']:05d} records surge_multiplier 2.2, the field POL-RD-02 reads for any recomputation; with no deviation the clause does not run and there is no refund to compute; the disclosed surge is part of the fare, not an overcharge. "
        f"The noon fare the rider compares against is not an artifact in the pool. NO_ACTION."))
