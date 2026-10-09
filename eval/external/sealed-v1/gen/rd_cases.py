"""ROUTE_DEVIATION sealed cases 301-312."""
import random
from datetime import timedelta
from core import *
from places import pt, lab

def _std_profiles(case, rider_id, driver_id, snap, region, vehicle="RYDE_X", **kw):
    r = rider_profile(rider_id, snap, kw.get("r_age",900), kw.get("r_trips",300), kw.get("r_rating",4.80),
                      kw.get("r_filed",1), kw.get("r_upheld",0), kw.get("r_cancel",0.040), kw.get("r_ns",0),
                      dev60=kw.get("r_dev60",0), dev60_sub=kw.get("r_dev60_sub",0))
    d = driver_profile(driver_id, snap, kw.get("d_age",1000), kw.get("d_trips",1500), kw.get("d_rating",4.85),
                       kw.get("d_filed",1), kw.get("d_upheld",0), kw.get("d_cancel",0.035), kw.get("d_ns",0),
                       kw.get("d_devlife",0), kw.get("d_accept",0.90), vehicle, region,
                       dev90=kw.get("d_dev90",0), trips90=kw.get("d_trips90",260))
    return r, d

def _assemble(case, disp_kw, trip, gps, chatp, fare, rp, dp, advs, gen, assessed, adm_over=None):
    tid = f"TRP-{case:05d}"
    adm_over = adm_over or {}
    def A(tok, default_notes):
        return adm_over.get(tok) or adm("COMPLETE", default_notes, assessed)
    ev = [
      envelope(evid(case,"TRIP"), "TRIP_RECORD", tid, "PLATFORM_TELEMETRY", gen, A("TRIP","Completed trip record, causally ordered."), trip),
      envelope(evid(case,"GPS"), "GPS_TRACE", tid, "PLATFORM_TELEMETRY", gen, A("GPS", "Driver device telemetry at 10 s cadence across the active window."), gps),
      envelope(evid(case,"CHAT"), "CHAT_LOG", tid, "PLATFORM_TELEMETRY", gen, A("CHAT", "In-app chat export for the trip."), chatp),
      envelope(evid(case,"FARE"), "FARE_BREAKDOWN", tid, "PAYMENTS_LEDGER", gen, A("FARE", "Ledger line items for the trip."), fare),
      envelope(evid(case,"RPROF"), "RIDER_PROFILE", tid, "PLATFORM_TELEMETRY", gen, A("RPROF", ""), rp),
      envelope(evid(case,"DPROF"), "DRIVER_PROFILE", tid, "PLATFORM_TELEMETRY", gen, A("DPROF", ""), dp),
    ]
    for k, (src, a, payload) in enumerate(advs, 1):
        ev.append(envelope(evid(case,"ADVIS",k), "TRAFFIC_ADVISORY", tid, src, gen, a, payload))
    ids = [e["evidence_id"] for e in ev]
    disp = dispute(case, "ROUTE_DEVIATION", disp_kw["by"], disp_kw["at"], disp_kw["claim"], disp_kw["contested"], ids, disp_kw.get("cp"))
    return case_file(case, disp, ev)

def _missing_adv(road, assessed):
    return adm("MISSING", "Artifact absent. The identifier is minted so that the absence itself is citable.", assessed,
               [{"code":"MISSING_ARTIFACT","detail":f"No advisory covers {road} in this window."}])

# =====================================================================
def case_301():
    """EASY / NO_ACTION. Verbosity bait. Excess 16.2% < 20%."""
    c=301; rng=random.Random(c)
    req=ts(2026,8,3,8,2,10); acc=req+timedelta(seconds=41); arr=acc+timedelta(minutes=6,seconds=20)
    start=arr+timedelta(seconds=75); end=start+timedelta(minutes=27,seconds=40)
    opt_km, opt_min = 14.2, 21.0
    wps=[pt("bukit_batok_mrt"),(1.3405,103.7620),(1.3260,103.7900),(1.3050,103.8300),(1.2900,103.8470),pt("raffles_place")]
    wps=fit_path(wps, 16.50)
    pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end)
    actual=round(dist,1)
    trip=trip_rd(c,"RDR-10231","DRV-10402",req,acc,arr,start,end,geo(lab("bukit_batok_mrt"),*pt("bukit_batok_mrt")),
                 geo(lab("raffles_place"),*pt("raffles_place")),opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 08:02; optimal is PIE then CTE)")
    chatp=chat(trip["trip_id"],[])
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],charged_at=end+timedelta(seconds=22))
    gen=ts(2026,8,4,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_std_profiles(c,"RDR-10231","DRV-10402",snap,"West (Jurong / Bukit Batok)",r_filed=2,r_upheld=1)
    advs=[("THIRD_PARTY_LTA",_missing_adv("the PIE or CTE",ass),None)]
    claim=("I have been taking this exact trip to work for three years and it is NEVER more than 14 or 15 km. Today the driver went some strange way "
           "through the back roads near Bukit Timah, I saw the meter climbing and climbing, and when I asked him he just said traffic. There was no traffic, "
           "it was a normal Monday. I ended up paying $25.63 when my usual is about $22 or $23. This is not the first time a Ryde driver has done this to me and I am "
           "honestly getting tired of having to fight for every dollar. I want the extra refunded and I want this driver flagged. Thank you.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=2,minutes=10),"claim":claim,"contested":3.50,
                    "cp":("Went PIE then CTE like normal. Small jam near Toa Payoh so I took the Braddell exit, maybe one or two km more. Nothing special.","DRIVER",gen-timedelta(hours=1))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00301 trace_distance_km is {dist:.2f} against an optimal of {opt_km} km on EV-TRIP-00301, an excess of {dist-opt_km:.2f} km or "
         f"{(dist-opt_km)/opt_km*100:.1f}%. POL-RD-01 establishes a deviation only where the excess exceeds BOTH 20% AND 0.8 km; the absolute test passes "
         f"but the percentage test fails, so no deviation exists. The rider's claim_text is long and confident but names no evidence, and POL-RD-08 gives it no weight. "
         f"All six singleton artifacts are COMPLETE at weight 1.0 and EV-ADVIS-00301-01 is MISSING, which is neutral. Outcome NO_ACTION; the charge on EV-FARE-00301 stands.")
    return cf, gt("NO_ACTION",None,["POL-RD-01","POL-RD-08"],"EASY",rat)

def case_302():
    """HARD / PARTIAL_REFUND. Off-route ERP already inside POL-RD-02 refund; surge 1.2."""
    c=302; rng=random.Random(c)
    req=ts(2026,8,4,7,48,30); acc=req+timedelta(seconds=55); arr=acc+timedelta(minutes=4,seconds=10)
    start=arr+timedelta(seconds=50); end=start+timedelta(minutes=39,seconds=0)
    opt_km,opt_min=22.0,28.0
    wps=[pt("woodlands_mrt"),(1.4150,103.7950),(1.3900,103.8100),(1.3700,103.8250),(1.3550,103.8300),(1.3350,103.8480),(1.3150,103.8600),(1.2950,103.8620),pt("mbfc")]
    wps=fit_path(wps,28.20); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    # gantries: one on optimal route, two off-route (driver's CTE routing)
    g_on = {"gantry_name":"BKE (Woodlands towards PIE)","charged_at":fmt(start+timedelta(minutes=6)),"amount_sgd":1.50,"on_optimal_route":True,
            "lat":pts[int(len(pts)*0.15)]["lat"],"lng":pts[int(len(pts)*0.15)]["lng"]}
    g_off1={"gantry_name":"CTE (Braddell Rd towards City)","charged_at":fmt(start+timedelta(minutes=20)),"amount_sgd":2.00,"on_optimal_route":False,
            "lat":pts[int(len(pts)*0.52)]["lat"],"lng":pts[int(len(pts)*0.52)]["lng"]}
    g_off2={"gantry_name":"CTE (Moulmein Rd towards City)","charged_at":fmt(start+timedelta(minutes=26)),"amount_sgd":1.00,"on_optimal_route":False,
            "lat":pts[int(len(pts)*0.68)]["lat"],"lng":pts[int(len(pts)*0.68)]["lng"]}
    trip=trip_rd(c,"RDR-10877","DRV-10115",req,acc,arr,start,end,geo(lab("woodlands_mrt"),*pt("woodlands_mrt")),geo(lab("mbfc"),*pt("mbfc")),
                 opt_km,opt_min,actual,erp_opt=1.50,src="routing-engine-v3.2 (LTA traffic snapshot 07:48; optimal is SLE then CTE to Moulmein, exiting before Braddell)")
    chatp=chat(trip["trip_id"],[])
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],surge=1.2,gantries=[g_on,g_off1,g_off2],charged_at=end+timedelta(seconds=19))
    gen=ts(2026,8,5,10,0,0); ass=gen+timedelta(seconds=11); snap=gen
    rp,dp=_std_profiles(c,"RDR-10877","DRV-10115",snap,"North (Woodlands / Yishun)",d_devlife=1,d_dev90=1)
    advs=[("THIRD_PARTY_LTA",_missing_adv("the SLE or CTE",ass),None)]
    rec=recomputed_fare(opt_km,opt_min,1.2,1.50)
    refund=round_up_05(fare["total_charged"]-rec)
    claim=(f"Charged ${fare['total_charged']:.2f} for Woodlands to MBFC. Usually around $32. Driver went all the way round via the CTE and I paid ERP three times. "
           "I want the extra distance and the extra ERP back.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=3),"claim":claim,"contested":15.00,
                    "cp":("SLE was heavy at the CTE merge so I stayed on CTE all the way down. Surge was on, that is why it is more.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00302 trace_distance_km {dist:.2f} km against optimal {opt_km} km on EV-TRIP-00302: excess {dist-opt_km:.2f} km, {(dist-opt_km)/opt_km*100:.1f}%, "
         f"which passes both POL-RD-01 limbs and is not MATERIAL (below 50% and below 8.0 km), so POL-RD-06 is not engaged. No advisory exists (EV-ADVIS-00302-01 MISSING) "
         f"and the chat is empty, so nothing under POL-RD-03/04/05 excuses the excess. EV-FARE-00302 is METERED with surge_multiplier 1.2, read from the fare artifact as POL-RD-02 requires. "
         f"recomputed_fare = ((3.80 + 0.75x{opt_km} + 0.28x{opt_min}) x 1.2) + 0.80 + 1.50 on-route BKE gantry = {rec:.3f}; charged_total {fare['total_charged']:.2f}; "
         f"refund {fare['total_charged']-rec:.3f} rounded up to {refund:.2f}. The two CTE gantries (2.00 + 1.00) are off the optimal route and are ALREADY inside that figure under POL-RD-09(1); "
         f"adding them again would wrongly produce {refund+3.00:.2f}. PARTIAL_REFUND {refund:.2f}.")
    return cf, gt("PARTIAL_REFUND",refund,["POL-RD-01","POL-RD-02","POL-RD-09"],"HARD",rat)

def case_303():
    """REVERSAL / PARTIAL_REFUND. trace 20.3% vs trip.actual rounded 20.0%; trace governs."""
    c=303; rng=random.Random(c)
    req=ts(2026,8,5,19,12,0); acc=req+timedelta(seconds=38); arr=acc+timedelta(minutes=3,seconds=30)
    start=arr+timedelta(seconds=40); end=start+timedelta(minutes=17,seconds=30)
    opt_km,opt_min=9.5,13.0
    wps=[pt("hougang_mall"),(1.3660,103.8880),(1.3560,103.8760),(1.3450,103.8620),(1.3330,103.8560),pt("novena_sq")]
    wps=fit_path(wps,11.43); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end)
    # force trace to land at 11.43 (fit_path is exact to ~1e-3 after jitter; nudge by regenerating if off)
    actual=round(dist,1)  # -> 11.4
    trip=trip_rd(c,"RDR-10044","DRV-10630",req,acc,arr,start,end,geo(lab("hougang_mall"),*pt("hougang_mall")),geo(lab("novena_sq"),*pt("novena_sq")),
                 opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 19:12; optimal is Upper Serangoon Rd then Bendemeer)")
    chatp=chat(trip["trip_id"],[])
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],charged_at=end+timedelta(seconds=25))
    gen=ts(2026,8,6,10,0,0); ass=gen+timedelta(seconds=8); snap=gen
    rp,dp=_std_profiles(c,"RDR-10044","DRV-10630",snap,"North-East (Hougang / Serangoon)")
    advs=[("THIRD_PARTY_LTA",_missing_adv("Upper Serangoon Rd",ass),None)]
    rec=recomputed_fare(opt_km,opt_min,1.0,0.0); refund=round_up_05(fare["total_charged"]-rec)
    claim=("felt longer than usual, driver went past the turn i think. not sure. can check?")
    cp=(f"Trip record says {actual} km on a 9.5 km estimate. That is 1.9 km more, exactly 20 percent, and your own policy says a deviation needs MORE than 20 percent. "
        "So there is no deviation. I took Upper Serangoon then Bendemeer as normal.","DRIVER",gen-timedelta(hours=3))
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=1,minutes=5),"claim":claim,"contested":4.00,"cp":cp},trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"The driver's counterparty_statement is precise and reads persuasively but it cites the wrong field. POL-RD-01 states that gps_trace.trace_distance_km governs and "
         f"trip_record.actual_distance_km is a rounded copy that may NOT be cited for the threshold test. EV-GPS-00303 trace_distance_km is {dist:.2f} km: excess {dist-opt_km:.2f} km, "
         f"{(dist-opt_km)/opt_km*100:.2f}%, which is greater than 20% and greater than 0.8 km, so a deviation IS established. On the rounded EV-TRIP-00303 figure of {actual} km the excess is exactly 20.0%, "
         f"which would fail the strict inequality, and that is the trap. No exculpatory artifact exists. POL-RD-02: recomputed_fare {rec:.3f}, charged_total {fare['total_charged']:.2f}, "
         f"refund {fare['total_charged']-rec:.3f} rounded up to {refund:.2f}, above the 0.50 de minimis. PARTIAL_REFUND {refund:.2f}.")
    return cf, gt("PARTIAL_REFUND",refund,["POL-RD-01","POL-RD-02","POL-RD-08"],"REVERSAL",rat)

def case_304():
    """HARD / PARTIAL_REFUND 1.00. POL-RD-03 fully exonerates distance; off-route ERP refunded standalone under POL-RD-09(2)."""
    c=304; rng=random.Random(c)
    req=ts(2026,8,6,18,20,15); acc=req+timedelta(seconds=44); arr=acc+timedelta(minutes=5)
    start=arr+timedelta(seconds=60); end=start+timedelta(minutes=41)
    opt_km,opt_min=24.0,30.0
    # optimal: PIE eastbound. Driver diverts at Eunos onto ECP due to PIE closure.
    wps=[pt("jurong_east_mrt"),(1.3330,103.7700),(1.3320,103.8000),(1.3300,103.8400),(1.3230,103.8800),(1.3050,103.9050),(1.3100,103.9450),(1.3400,103.9700),pt("changi_t3")]
    wps=fit_path(wps,28.90); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    g_off={"gantry_name":"ECP (Fort Rd towards Changi)","charged_at":fmt(start+timedelta(minutes=27)),"amount_sgd":1.00,"on_optimal_route":False,
           "lat":pts[int(len(pts)*0.62)]["lat"],"lng":pts[int(len(pts)*0.62)]["lng"]}
    trip=trip_rd(c,"RDR-10512","DRV-10088",req,acc,arr,start,end,geo(lab("jurong_east_mrt"),*pt("jurong_east_mrt")),geo(lab("changi_t3"),*pt("changi_t3")),
                 opt_km,opt_min,actual,erp_opt=0.0,src="routing-engine-v3.2 (LTA traffic snapshot 18:20; optimal is PIE eastbound throughout)")
    m=[msg(c,1,"DRIVER","PIE closed after Eunos, i take ECP ok",start+timedelta(minutes=13),read=start+timedelta(minutes=13,seconds=20)),
       msg(c,2,"RIDER","ok",start+timedelta(minutes=13,seconds=50),read=start+timedelta(minutes=14))]
    chatp=chat(trip["trip_id"],m); trip["chat_message_count"]=2
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],gantries=[g_off],charged_at=end+timedelta(seconds=30))
    gen=ts(2026,8,7,10,0,0); ass=gen+timedelta(seconds=12); snap=gen
    rp,dp=_std_profiles(c,"RDR-10512","DRV-10088",snap,"West (Jurong / Clementi)")
    box=(1.3180,103.8750,1.3330,103.9000)
    advp=advisory("ADV-20260806-031","Pan Island Expressway (PIE) towards Changi, Eunos Link to Bedok North Ave 4","CLOSURE",
                  ts(2026,8,6,17,40),ts(2026,8,6,21,0),box,"HIGH","Full closure both carriageways for overturned trailer recovery. Divert via ECP.",
                  "LTA_DATAMALL",pts,start,end,alt_km=27.5)
    adva=adm("COMPLETE","LTA DataMall closure on the PIE corridor the optimal route uses; window covers the trip.",ass)
    advs=[("THIRD_PARTY_LTA",adva,advp)]
    cap=1.30*(27.5-opt_km)+1.00; excess=dist-opt_km; justified=min(excess,cap)
    claim=(f"Paid ${fare['total_charged']:.2f} to the airport, quote in the app was around $33. Driver took the ECP instead of PIE and I paid ERP. Refund the difference.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=4),"claim":claim,"contested":6.00,
                    "cp":("PIE was shut at Eunos, LTA advisory, I told the rider in chat and she said ok. ECP was the only way.","DRIVER",gen-timedelta(hours=1))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00304 trace {dist:.2f} km vs optimal {opt_km} km: excess {excess:.2f} km ({excess/opt_km*100:.1f}%), established under POL-RD-01. EV-ADVIS-00304-01 is a COMPLETE LTA_DATAMALL "
         f"CLOSURE on the PIE segment the optimal route traverses, intersects_route true, overlaps the trip window by {advp['overlap_minutes']} min, and the trace leaves the PIE corridor "
         f"before Eunos and rejoins toward Changi, so POL-RD-03(a)(b)(c) are met. Cap = min(excess, 1.30 x (27.5 - {opt_km}) + 1.00) = min({excess:.2f}, {cap:.2f}) = {justified:.2f}: "
         f"the whole excess is justified and no residual deviation survives, so POL-RD-02 issues nothing on distance or time. But POL-RD-09(2) is explicit: where the deviation is exonerated "
         f"under POL-RD-03, off-route ERP is still refunded to the rider standalone. EV-FARE-00304 carries one ECP gantry, 1.00, on_optimal_route false. PARTIAL_REFUND 1.00. "
         f"A Judge that runs POL-RD-02 here over-refunds; one that stops at exoneration under-refunds.")
    return cf, gt("PARTIAL_REFUND",1.00,["POL-RD-01","POL-RD-03","POL-RD-09"],"HARD",rat)

def case_305():
    """REVERSAL / DRIVER_COMPENSATION. Rider asked in chat to stop at Pasir Ris MRT (off-corridor); trace = leg1 + leg2 with no residual; meter under-billed >1 km."""
    c=305; rng=random.Random(c)
    req=ts(2026,8,7,12,5,0); acc=req+timedelta(seconds=35); arr=acc+timedelta(minutes=3)
    start=arr+timedelta(seconds=45); end=start+timedelta(minutes=29)
    stop=pt("pasir_ris_mrt"); A=pt("tampines_hub"); B=pt("paya_lebar_sq")
    # natural geometry, no fitting: leg1 A->stop, leg2 stop->B, each with one intermediate bend
    leg1=[A,(1.3640,103.9460),stop]; leg2=[stop,(1.3500,103.9250),(1.3300,103.9050),B]
    L1=polyline_km(leg1); L2=polyline_km(leg2)
    opt_km=round(haversine_km(A,B)*1.15,1); opt_min=14.0        # direct corridor via PIE
    leg1_opt=round(haversine_km(A,stop)*1.15,2); leg2_opt=round(haversine_km(stop,B)*1.15,2)
    wps=leg1+leg2[1:]
    pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    billed=round(actual-1.72,1)
    trip=trip_rd(c,"RDR-10390","DRV-10777",req,acc,arr,start,end,geo(lab("tampines_hub"),*A),geo(lab("paya_lebar_sq"),*B),
                 opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 12:05; optimal is Tampines Ave 10 then PIE westbound)")
    m=[msg(c,1,"RIDER","uncle can go pasir ris mrt first? my sister pass me something, 5 min only",start+timedelta(seconds=40),
           read=start+timedelta(seconds=55),wp=geo(lab("pasir_ris_mrt"),*stop)),
       msg(c,2,"DRIVER","ok can",start+timedelta(seconds=70),read=start+timedelta(seconds=80))]
    chatp=chat(trip["trip_id"],m); trip["chat_message_count"]=2
    fare=fare_metered(trip["trip_id"],billed,trip["actual_duration_min"],charged_at=end+timedelta(seconds=20))
    gen=ts(2026,8,8,10,0,0); ass=gen+timedelta(seconds=10); snap=gen
    rp,dp=_std_profiles(c,"RDR-10390","DRV-10777",snap,"East (Tampines / Pasir Ris)")
    advs=[("THIRD_PARTY_LTA",_missing_adv("Tampines Ave 10 or the PIE",ass),None)]
    comp=round_up_05((actual-billed)*0.75)
    mind=min(haversine_km((p["lat"],p["lng"]),stop) for p in pts)*1000
    claim=(f"Trip was {actual} km for a route that should be 7 or 8 km. Driver went all the way up to Pasir Ris and around before getting on the PIE. "
           "I was on the phone the whole time so I didn't notice until I saw the receipt. Refund the detour.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=6),"claim":claim,"contested":6.00,
                    "cp":("She asked me in chat to go Pasir Ris MRT first. I stopped, she went in, came back, then we went. Check the chat.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"The claim_text reads as a straightforward detour complaint, but EV-CHAT-00305 MSG-00305-001 is a rider instruction 40 s after started_at, before the vehicle left the corridor, naming Pasir Ris MRT with a populated "
         f"waypoint_hint; EV-GPS-00305 passes within {mind:.0f} m of that coordinate, so POL-RD-04(a)(b)(c) are met and the trace corroborates. The trip decomposes into two legs: Tampines Hub to Pasir Ris MRT, {L1:.2f} km traced against "
         f"a corridor estimate of about {leg1_opt} km, and Pasir Ris MRT to Paya Lebar Square, {L2:.2f} km against about {leg2_opt} km; neither leg carries an excess meeting POL-RD-01, so once the rider-requested stop is excluded "
         f"no deviation exists against the booked {opt_km} km optimal and no refund is due. Separately, EV-FARE-00305 distance_charged_km is {billed} against a trace of {dist:.2f} km, a shortfall of {actual-billed:.2f} km exceeding 1.0 km; "
         f"POL-RD-04's compensation limb pays 0.75 per unbilled km rounded UP to 0.05: {(actual-billed)*0.75:.4f} -> {comp:.2f}, under the 15.00 cap. DRIVER_COMPENSATION {comp:.2f}; per POL-GEN-03 amount_sgd mirrors it and the rider's charge stands.")
    return cf, gt("DRIVER_COMPENSATION",comp,["POL-RD-04","POL-RD-01","POL-RD-08"],"REVERSAL",rat,driver_comp=comp)

def case_306():
    """HARD / FULL_REFUND of charged_total + POL-RD-06(c) referral. Material 59% + driver pattern (deviation_flags_90d=3)."""
    c=306; rng=random.Random(c)
    req=ts(2026,8,8,22,30,0); acc=req+timedelta(seconds=50); arr=acc+timedelta(minutes=4)
    start=arr+timedelta(seconds=30); end=start+timedelta(minutes=44)
    opt_km,opt_min=21.0,27.0
    wps=[pt("yishun_mrt"),(1.4330,103.8000),(1.4300,103.7750),(1.4050,103.7650),(1.3800,103.7600),(1.3600,103.7650),(1.3450,103.7750),
         (1.3350,103.7900),(1.3250,103.8050),(1.3150,103.8200),(1.3050,103.8350),(1.2950,103.8450),pt("raffles_place")]
    wps=fit_path(wps,33.50); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    trip=trip_rd(c,"RDR-10658","DRV-10921",req,acc,arr,start,end,geo(lab("yishun_mrt"),*pt("yishun_mrt")),geo(lab("raffles_place"),*pt("raffles_place")),
                 opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 22:30; optimal is SLE then CTE)")
    chatp=chat(trip["trip_id"],[])
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],charged_at=end+timedelta(seconds=15))
    gen=ts(2026,8,9,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_std_profiles(c,"RDR-10658","DRV-10921",snap,"North (Yishun / Sembawang)",d_devlife=7,d_dev90=3,d_trips90=118,d_rating=4.41,d_filed=5,d_upheld=3)
    advs=[("THIRD_PARTY_LTA",_missing_adv("the SLE or CTE",ass),None)]
    rec=recomputed_fare(opt_km,opt_min,1.0,0.0); partial=round_up_05(fare["total_charged"]-rec); total=fare["total_charged"]
    claim=(f"{actual} km from Yishun to Raffles Place at 10.30 at night with empty roads. He went west through Woodlands and Bukit Timah, nowhere near the CTE. "
           f"I refuse to pay ${total:.2f} for this, refund the whole trip.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=9),"claim":claim,"contested":total,
                    "cp":("There was a police roadblock on the SLE so I went BKE. Nothing wrong.","DRIVER",gen-timedelta(hours=1))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00306 trace {dist:.2f} km vs optimal {opt_km} km: excess {dist-opt_km:.2f} km, {(dist-opt_km)/opt_km*100:.1f}%, established and MATERIAL under POL-RD-01 (over 50% and over 8.0 km). "
         f"The driver's roadblock assertion is unsupported by any advisory (EV-ADVIS-00306-01 MISSING) and POL-RD-08 discards it. POL-RD-06 requires the driver_profile check on a material deviation: "
         f"EV-DPROF-00306 deviation_flags_90d is 3, meeting the count limb; prior_deviation_flags of 7 is the lifetime counter and is not the field the clause reads, though here both point the same way. "
         f"Pattern established. Limb (b): the deviation is material AND substantiated on this trip's own trace, so FULL_REFUND of charged_total is licensed in place of the POL-RD-02 partial; "
         f"POL-RD-02 would give charged_total {total:.2f} minus recomputed {rec:.3f} = {partial:.2f}, and the uplifted figure is {total:.2f}; both are stated so the uplift is auditable. No pass-through lines exist to carve out under POL-RD-09. "
         f"Limb (c) refers the driver to conduct review, a REFERRAL not an escalation, so money still moves. amount_contested equals charged_total. FULL_REFUND {total:.2f}.")
    return cf, gt("FULL_REFUND",total,["POL-RD-01","POL-RD-06","POL-RD-02","POL-RD-08"],"HARD",rat,referrals=["POL-RD-06(c) driver-conduct review"])

def case_307():
    """INDETERMINATE / ESCALATE. 240 s tunnel gap in disputed segment (POL-RD-07(a)), no corroboration -> POL-RD-10(3)."""
    c=307; rng=random.Random(c)
    req=ts(2026,8,9,17,55,0); acc=req+timedelta(seconds=42); arr=acc+timedelta(minutes=5)
    start=arr+timedelta(seconds=35); end=start+timedelta(minutes=30)
    opt_km,opt_min=18.0,24.0
    wps=[pt("sengkang_mrt"),(1.3800,103.8950),(1.3600,103.8930),(1.3400,103.8880),(1.3200,103.8750),(1.3050,103.8650),pt("suntec")]
    wps=fit_path(wps,22.60); pts=interp_path(wps,start,end,rng=rng)
    # remove 240 s of fixes in the KPE tunnel stretch (middle)
    mid=len(pts)//2; cut_from=pts[mid]["ts"]; cut_to=cut_from+timedelta(seconds=240)
    pts=[p for p in pts if not (cut_from < p["ts"] < cut_to)]
    gps,dist,gaps,cov=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    trip=trip_rd(c,"RDR-10203","DRV-10344",req,acc,arr,start,end,geo(lab("sengkang_mrt"),*pt("sengkang_mrt")),geo(lab("suntec"),*pt("suntec")),
                 opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 17:55; optimal is KPE southbound)")
    chatp=chat(trip["trip_id"],[])
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],charged_at=end+timedelta(seconds=18))
    gen=ts(2026,8,10,10,0,0); ass=gen+timedelta(seconds=13); snap=gen
    rp,dp=_std_profiles(c,"RDR-10203","DRV-10344",snap,"North-East (Sengkang / Punggol)")
    g=gaps[0]
    gps_adm=adm("IMPAIRED",f"Telemetry drops for {g['duration_sec']:.0f} s inside the KPE tunnel section; coverage {cov}%.",ass,
                [{"code":"GPS_GAP","detail":f"One gap of {g['duration_sec']:.0f} s from {g['from_ts']} to {g['to_ts']}, straight line {g['straight_line_km']} km, in the KPE tunnel."},
                 {"code":"LOW_COVERAGE","detail":f"coverage_pct {cov}: {g['duration_sec']:.0f} s of gap across a {int((end-start).total_seconds())} s active window, below the 90.0 threshold."}])
    advs=[("THIRD_PARTY_LTA",_missing_adv("the KPE",ass),None)]
    claim=("Sengkang to Suntec is 18 km on every app. Meter said 22 km. Something happened in the tunnel, he must have exited and come back on. Refund the extra.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=2),"claim":claim,"contested":5.00,
                    "cp":("KPE straight down, no exit. GPS always drops in the tunnel.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass,adm_over={"GPS":gps_adm})
    rat=(f"EV-GPS-00307 is IMPAIRED: a single {g['duration_sec']:.0f} s gap in the KPE tunnel, which is the very segment the rider disputes, with coverage {cov}% and schema weight 0.39. "
         f"The gap exceeds 90 s, so the trace is impaired FOR POLICY PURPOSES under POL-RD-07(a), not merely schema-impaired. Under POL-RD-07(i) the excess across the gap is the straight line between the bounding fixes, "
         f"and under (ii) a deviation may not be established on this trace alone. No independent corroboration of the kind POL-RD-07(ii) names exists: EV-CHAT-00307 is empty, EV-FARE-00307 carries no ERP, "
         f"the counterparty_statement denies the route, and EV-TRIP-00307 actual_distance_km is the rounded copy of this same trace. POL-RD-07(iii) and POL-RD-10(3) therefore require ESCALATE, not NO_ACTION: "
         f"the absence of proof here is a data failure, not a finding for the driver. Under POL-GEN-02(2) the deciding fact rests solely on an artifact at weight 0.39, below the 0.70 floor, which independently triggers POL-RD-10(1). "
         f"The reviewer should seek the KPE gantry or tunnel-camera record for the gap window.")
    return cf, gt("ESCALATE",None,["POL-RD-07","POL-RD-10","POL-GEN-02"],"INDETERMINATE",rat)

def case_308():
    """HARD / NO_ACTION. UPFRONT_QUOTE, 35% excess, charged == quoted, no pass-through lines. Verbosity bait."""
    c=308; rng=random.Random(c)
    req=ts(2026,8,10,14,10,0); acc=req+timedelta(seconds=30); arr=acc+timedelta(minutes=3,seconds=20)
    start=arr+timedelta(seconds=50); end=start+timedelta(minutes=21)
    opt_km,opt_min=9.0,14.0
    wps=[pt("bishan_mrt"),(1.3450,103.8400),(1.3350,103.8300),(1.3250,103.8250),(1.3100,103.8280),pt("great_world")]
    wps=fit_path(wps,12.20); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    trip=trip_rd(c,"RDR-10119","DRV-10556",req,acc,arr,start,end,geo(lab("bishan_mrt"),*pt("bishan_mrt")),geo(lab("great_world"),*pt("great_world")),
                 opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 14:10; optimal is CTE then Bukit Timah Rd)")
    chatp=chat(trip["trip_id"],[])
    fare=fare_metered(trip["trip_id"],opt_km,opt_min,charged_at=end+timedelta(seconds=20))
    fare["fare_model"]="UPFRONT_QUOTE"; fare["quoted_fare_sgd"]=fare["total_charged"]
    fare["distance_charged_km"]=opt_km; fare["time_charged_min"]=opt_min
    gen=ts(2026,8,11,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_std_profiles(c,"RDR-10119","DRV-10556",snap,"Central (Bishan / Toa Payoh)")
    advs=[("THIRD_PARTY_LTA",_missing_adv("the CTE or Bukit Timah Rd",ass),None)]
    claim=("I am writing to formally dispute this fare. I booked Bishan to Great World and was shown a price. The driver then proceeded to take what I can only describe as a scenic tour, "
           "going down Thomson Road, past Novena, and looping around before finally heading to River Valley. I timed it: 21 minutes for a trip that Google says is 14. I have screenshots. "
           "This is a clear case of a driver padding the trip, and I expect Ryde to take it seriously. I would like a refund proportionate to the extra distance, and I would like to know "
           "what action will be taken against the driver. I have been a loyal customer and this experience has been very disappointing.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=1),"claim":claim,"contested":5.00,
                    "cp":("Fixed price trip. Whatever route, she paid what she was quoted.","DRIVER",gen-timedelta(hours=4))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00308 trace {dist:.2f} km vs optimal {opt_km} km is an excess of {(dist-opt_km)/opt_km*100:.1f}%, so a deviation is established under POL-RD-01 but is not MATERIAL, and POL-RD-06 is not engaged. "
         f"EV-FARE-00308 fare_model is UPFRONT_QUOTE with quoted_fare_sgd {fare['quoted_fare_sgd']:.2f} equal to total_charged; POL-RD-11 governs and POL-RD-02 does NOT run. The rider's remedies under POL-RD-11 are "
         f"(a) any excess of charged_total over the quote plus properly chargeable pass-through lines, which is zero, and (b) a POL-RD-09 correction for off-route or phantom lines, of which there are none "
         f"(tolls_erp 0.00, airport_surcharge 0.00). The rider is already whole on distance and time; the loss of the extra {dist-opt_km:.2f} km falls on the driver. The long claim_text carries no evidence ID and POL-RD-08 gives it no weight. "
         f"NO_ACTION.")
    return cf, gt("NO_ACTION",None,["POL-RD-11","POL-RD-01","POL-RD-08"],"HARD",rat)

def case_309():
    """HARD / NO_ACTION. RYDE_POOL: excess vs matched optimal 4.6%; vs solo_optimal 33% (wrong field)."""
    c=309; rng=random.Random(c)
    req=ts(2026,8,11,8,40,0); acc=req+timedelta(seconds=60); arr=acc+timedelta(minutes=6)
    start=arr+timedelta(seconds=40); end=start+timedelta(minutes=38)
    solo,matched,opt_min=15.2,19.4,30.0
    wps=[pt("punggol_mrt"),(1.3950,103.9000),(1.3800,103.8960),pt("hougang_mall"),(1.3600,103.8800),(1.3450,103.8650),(1.3300,103.8520),pt("novena_sq")]
    wps=fit_path(wps,20.30); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    trip=trip_rd(c,"RDR-10733","DRV-10201",req,acc,arr,start,end,geo(lab("punggol_mrt"),*pt("punggol_mrt")),geo(lab("novena_sq"),*pt("novena_sq")),
                 matched,opt_min,actual,vehicle="RYDE_POOL",solo_km=solo,
                 src="routing-engine-v3.2 (LTA traffic snapshot 08:40; matched itinerary POOL-8840-2 with co-rider pickup at Hougang Mall)")
    m=[msg(c,1,"SYSTEM","Your co-rider will board at Hougang Mall.",start+timedelta(seconds=5),read=start+timedelta(seconds=30))]
    chatp=chat(trip["trip_id"],m); trip["chat_message_count"]=1
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],charged_at=end+timedelta(seconds=22),rate_card="RC-SG-2026Q3-RYDEPOOL")
    gen=ts(2026,8,12,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_std_profiles(c,"RDR-10733","DRV-10201",snap,"North-East (Punggol / Sengkang)",vehicle="RYDE_POOL")
    advs=[("THIRD_PARTY_LTA",_missing_adv("the TPE or CTE",ass),None)]
    claim=(f"Booked a pool from Punggol. App said my route is 15 km. Trip was {actual} km because he went to Hougang to pick someone up and then all the way round. "
           "That is 5 km extra I paid for someone else's trip.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=5),"claim":claim,"contested":6.00,
                    "cp":("Pool trip. Co-rider at Hougang was on the itinerary the app gave me.","DRIVER",gen-timedelta(hours=1))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-TRIP-00309 vehicle_type is RYDE_POOL, so POL-RD-12 applies: the POL-RD-01 baseline is the MATCHED-ITINERARY optimal_distance_km of {matched} km, not solo_optimal_distance_km of {solo} km, "
         f"which is carried for reference only. EV-GPS-00309 trace {dist:.2f} km: excess over the matched figure is {dist-matched:.2f} km, {(dist-matched)/matched*100:.1f}%, failing the 20% limb; no deviation. "
         f"Measured against the solo figure the excess would be {(dist-solo)/solo*100:.1f}%, and a claim built on that has cited the wrong field and fails on that ground alone. The Hougang detour is the platform-matched "
         f"co-rider pickup, confirmed by MSG-00309-001, and is excluded from excess by POL-RD-12 before POL-RD-01 runs. NO_ACTION.")
    return cf, gt("NO_ACTION",None,["POL-RD-12","POL-RD-01"],"HARD",rat)

def case_310():
    """HARD / PARTIAL_REFUND 3.00 + billing-integrity referral. Phantom CTE gantry; no deviation (5%)."""
    c=310; rng=random.Random(c)
    req=ts(2026,8,12,8,15,0); acc=req+timedelta(seconds=40); arr=acc+timedelta(minutes=4)
    start=arr+timedelta(seconds=45); end=start+timedelta(minutes=26)
    opt_km,opt_min=13.0,19.0
    wps=[pt("bedok_mall"),(1.3150,103.9200),(1.3050,103.9000),(1.2980,103.8750),(1.2950,103.8550),(1.3000,103.8400),pt("ion_orchard")]
    wps=fit_path(wps,13.70); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    g_real={"gantry_name":"ECP (Fort Rd towards City)","charged_at":fmt(start+timedelta(minutes=9)),"amount_sgd":2.00,"on_optimal_route":True,
            "lat":pts[int(len(pts)*0.35)]["lat"],"lng":pts[int(len(pts)*0.35)]["lng"]}
    g_phantom={"gantry_name":"CTE (Braddell Rd towards City)","charged_at":fmt(start+timedelta(minutes=14)),"amount_sgd":3.00,"on_optimal_route":False,
               "lat":1.341800,"lng":103.848900}
    trip=trip_rd(c,"RDR-10466","DRV-10693",req,acc,arr,start,end,geo(lab("bedok_mall"),*pt("bedok_mall")),geo(lab("ion_orchard"),*pt("ion_orchard")),
                 opt_km,opt_min,actual,erp_opt=2.00,src="routing-engine-v3.2 (LTA traffic snapshot 08:15; optimal is ECP then Nicoll Hwy)")
    chatp=chat(trip["trip_id"],[])
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],gantries=[g_real,g_phantom],promo=2.00,charged_at=end+timedelta(seconds=17))
    gen=ts(2026,8,13,10,0,0); ass=gen+timedelta(seconds=10); snap=gen
    rp,dp=_std_profiles(c,"RDR-10466","DRV-10693",snap,"East (Bedok / Marine Parade)")
    advs=[("THIRD_PARTY_LTA",_missing_adv("the ECP",ass),None)]
    claim=(f"ERP shows $5.00 on my receipt. We took ECP and I know that gantry is $2. There is a CTE Braddell charge but we never went anywhere near Braddell. "
           "Also I think he went a longer way than needed. Refund the ERP and the extra.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=1,minutes=30),"claim":claim,"contested":8.00,
                    "cp":("ERP is automatic from the IU, I cannot control it. Route was normal ECP.","DRIVER",gen-timedelta(hours=3))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"Two separate questions. First, deviation: EV-GPS-00310 trace {dist:.2f} km vs optimal {opt_km} km is {(dist-opt_km)/opt_km*100:.1f}%, failing POL-RD-01's 20% limb, so no deviation and no POL-RD-02 refund; "
         f"the rider's 'longer way' assertion is not made out. Second, billing integrity under POL-RD-09(4): EV-FARE-00310 itemises a CTE Braddell gantry at 3.00 with coordinates 1.341800, 103.848900; "
         f"no fix in EV-GPS-00310 lies within 250 m of that point at any time, so the line is a phantom and is refunded in full as a standalone correction, available whether or not a deviation exists. "
         f"The ECP Fort Rd gantry at 2.00 is matched to the trace and on the optimal route, and stands. The 2.00 promo_discount is unaffected. The phantom line is recorded as a billing-integrity referral; "
         f"POL-RD-10(8) is not triggered because the only unmatched line is the one refunded here. PARTIAL_REFUND 3.00 of the 8.00 contested.")
    return cf, gt("PARTIAL_REFUND",3.00,["POL-RD-09","POL-RD-01"],"HARD",rat,referrals=["POL-RD-09(4) billing integrity"])

def case_311():
    """HARD / ESCALATE under POL-RD-10(7): rider requested Clementi Mall stop; trace never approaches it, goes via Bukit Timah instead."""
    c=311; rng=random.Random(c)
    req=ts(2026,8,13,16,0,0); acc=req+timedelta(seconds=35); arr=acc+timedelta(minutes=4)
    start=arr+timedelta(seconds=40); end=start+timedelta(minutes=24)
    opt_km,opt_min=7.5,12.0
    wps=[pt("jurong_east_mrt"),(1.3380,103.7600),(1.3400,103.7750),pt("king_albert_park"),(1.3250,103.7900),(1.3150,103.7920),pt("buona_vista")]
    wps=fit_path(wps,12.40); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    trip=trip_rd(c,"RDR-10982","DRV-10310",req,acc,arr,start,end,geo(lab("jurong_east_mrt"),*pt("jurong_east_mrt")),geo(lab("buona_vista"),*pt("buona_vista")),
                 opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 16:00; optimal is AYE eastbound)")
    m=[msg(c,1,"RIDER","eh can stop at clementi mall first? need collect parcel from the locker",start+timedelta(seconds=50),read=start+timedelta(seconds=65),
           wp=geo(lab("clementi_mall"),*pt("clementi_mall"))),
       msg(c,2,"DRIVER","ok",start+timedelta(seconds=80),read=start+timedelta(seconds=90))]
    chatp=chat(trip["trip_id"],m); trip["chat_message_count"]=2
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],charged_at=end+timedelta(seconds=20))
    gen=ts(2026,8,14,10,0,0); ass=gen+timedelta(seconds=11); snap=gen
    rp,dp=_std_profiles(c,"RDR-10982","DRV-10310",snap,"West (Jurong / Clementi)")
    advs=[("THIRD_PARTY_LTA",_missing_adv("the AYE",ass),None)]
    mind=min(haversine_km((p["lat"],p["lng"]),pt("clementi_mall")) for p in pts)
    claim=(f"{actual} km for Jurong East to Buona Vista?? It is 7 km on the AYE. He went up to Bukit Timah for no reason. I did ask to stop at Clementi Mall but he never even went there, "
           "we just ended up at Buona Vista after a big loop. Refund.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=2),"claim":claim,"contested":5.00,
                    "cp":("She asked me to stop at Clementi. I went the Clementi way. Then she said never mind go straight. Check the chat, she asked.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00311 trace {dist:.2f} km vs optimal {opt_km} km: excess {(dist-opt_km)/opt_km*100:.1f}%, established and MATERIAL under POL-RD-01; EV-DPROF-00311 deviation_flags_90d is 0 so POL-RD-06 finds no pattern. "
         f"EV-CHAT-00311 MSG-00311-001 is a genuine rider detour request naming Clementi Mall with a populated waypoint_hint, timestamped 50 s into the trip, satisfying POL-RD-04(a)(b)(c) on its face. "
         f"But the corroboration test fails: the nearest trace fix to the Clementi Mall waypoint is {mind*1000:.0f} m away, far outside 200 m, and the trace instead runs north to King Albert Park. "
         f"The record therefore holds admissible evidence that the rider asked for a detour and admissible evidence that the driver drove a different one; the driver's statement that the rider then cancelled the stop "
         f"has no chat support. This is the situation POL-RD-10(7) names in terms: a chat_log detour request whose waypoint the gps_trace never approaches. ESCALATE. The reviewer must settle whether the Bukit Timah "
         f"routing was the rider's second instruction or the driver's choice; a voice-call record or the rider's own account of the aborted stop would resolve it.")
    return cf, gt("ESCALATE",None,["POL-RD-10","POL-RD-04","POL-RD-01"],"HARD",rat)

def case_312():
    """HARD / PARTIAL_REFUND. Dropoff amended (POL-RD-05); residual 25.7% vs amended optimal; rider has 5 unsubstantiated claims (POL-RD-08 bar) but driver admission in chat corroborates."""
    c=312; rng=random.Random(c)
    req=ts(2026,8,14,20,5,0); acc=req+timedelta(seconds=48); arr=acc+timedelta(minutes=5)
    start=arr+timedelta(seconds=55); end=start+timedelta(minutes=24)
    opt_km,opt_min=12.5,17.0; amend_km,amend_min=14.0,19.0
    amend_at=start+timedelta(minutes=3)
    wps=[pt("woodlands_mrt"),(1.4250,103.8000),(1.4050,103.8150),(1.3900,103.8300),(1.3750,103.8450),(1.3650,103.8600),(1.3580,103.8550),pt("junction8")]
    wps=fit_path(wps,17.60); pts=interp_path(wps,start,end,rng=rng)
    gps,dist,_,_=build_gps(f"TRP-{c:05d}",pts,start,end); actual=round(dist,1)
    trip=trip_rd(c,"RDR-10147","DRV-10829",req,acc,arr,start,end,geo(lab("woodlands_mrt"),*pt("woodlands_mrt")),geo(lab("junction8"),*pt("junction8")),
                 opt_km,opt_min,actual,src="routing-engine-v3.2 (LTA traffic snapshot 20:05; optimal is SLE then CTE, re-quoted to Junction 8 at 20:14)",
                 drop_amended=amend_at,orig_drop=geo(lab("amk_hub"),*pt("amk_hub")),amend_km=amend_km,amend_min=amend_min)
    m=[msg(c,1,"RIDER","sorry uncle change to bishan junction 8 instead of amk hub, i updated the pin",start+timedelta(minutes=2,seconds=50),read=start+timedelta(minutes=3)),
       msg(c,2,"DRIVER","ok",start+timedelta(minutes=3,seconds=10),read=start+timedelta(minutes=3,seconds=20)),
       msg(c,3,"DRIVER","sorry sorry i miss the exit at braddell, go one big round come back",start+timedelta(minutes=15),read=start+timedelta(minutes=15,seconds=30)),
       msg(c,4,"RIDER","...ok",start+timedelta(minutes=15,seconds=40),read=start+timedelta(minutes=16))]
    chatp=chat(trip["trip_id"],m); trip["chat_message_count"]=4
    fare=fare_metered(trip["trip_id"],actual,trip["actual_duration_min"],charged_at=end+timedelta(seconds=16))
    gen=ts(2026,8,15,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_std_profiles(c,"RDR-10147","DRV-10829",snap,"North (Woodlands / Sembawang)",r_filed=9,r_upheld=1,r_rating=4.12,r_dev60=5,r_dev60_sub=0)
    advs=[("THIRD_PARTY_LTA",_missing_adv("the SLE or CTE",ass),None)]
    rec=recomputed_fare(amend_km,amend_min,1.0,0.0); refund=round_up_05(fare["total_charged"]-rec)
    claim=("changed my drop to junction 8 mid way. driver missed the exit and went a big round, he even said sorry in chat. 17.6 km for a trip that should be 14. want the extra back.")
    cf=_assemble(c,{"by":"RIDER","at":end+timedelta(hours=1),"claim":claim,"contested":6.00,
                    "cp":("She changed the destination halfway. Route is different when destination changes. And this rider complains every week, check her record.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-TRIP-00312 dropoff_amended_at is non-null and amended_optimal_distance_km is {amend_km} km, so POL-RD-05 re-applies POL-RD-01 against the AMENDED endpoints and that stored figure, not the booked {opt_km} km. "
         f"EV-GPS-00312 trace {dist:.2f} km: excess {dist-amend_km:.2f} km, {(dist-amend_km)/amend_km*100:.1f}%, established and not material. EV-RPROF-00312 shows deviation_claims_60d 5 with 0 substantiated, "
         f"so POL-RD-08 raises the bar: an excess below 30% needs corroboration beyond the gps_trace. That corroboration exists in EV-CHAT-00312 MSG-00312-003, a driver admission of missing the Braddell exit, "
         f"one of the sources POL-RD-07(ii) names. POL-RD-08 states the profile factor may never deny a claim otherwise proven, and POL-GEN-01 makes the driver's invitation to 'check her record' a discarded ground. "
         f"POL-RD-02 against the amended optimal: recomputed {rec:.3f}, charged_total {fare['total_charged']:.2f}, refund {fare['total_charged']-rec:.3f} rounded up to {refund:.2f}. PARTIAL_REFUND {refund:.2f}.")
    return cf, gt("PARTIAL_REFUND",refund,["POL-RD-05","POL-RD-01","POL-RD-08","POL-RD-02","POL-GEN-01"],"HARD",rat)

RD_CASES=[case_301,case_302,case_303,case_304,case_305,case_306,case_307,case_308,case_309,case_310,case_311,case_312]
