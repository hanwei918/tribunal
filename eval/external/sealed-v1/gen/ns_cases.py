"""NO_SHOW_CHARGE sealed cases 401-412."""
import random, math
from datetime import timedelta
from core import *
from places import pt, lab
from rd_cases import _missing_adv

def _offset(p, north_m=0.0, east_m=0.0):
    return (p[0] + north_m/111_000, p[1] + east_m/(111_000*math.cos(math.radians(p[0]))))

def _drive_then_dwell(c, origin, dwell_pt, acc, reach, cancel, rng, dwell_acc=(5.0,14.0), venue=None, approach_acc=(28.0,48.0)):
    """Driver en route from origin, reaches dwell_pt at `reach`, holds until `cancel`."""
    wps=[origin,_offset(dwell_pt,400,-300),dwell_pt]
    drive=interp_path(wps,acc,reach,rng=rng,acc=approach_acc)
    hold=dwell_points(dwell_pt,reach+timedelta(seconds=10),cancel,rng=rng,acc=dwell_acc,venue_id=venue)
    return drive+hold

def _rider_track(center, t0, t1, rng, acc=(4.0,16.0), venue=None):
    return dwell_points(center,t0,t1,cadence=9,rng=rng,acc=acc,jitter_m=4.0,venue_id=venue)

def _profiles(rid, did, snap, region, tier, **kw):
    r=rider_profile(rid,snap,kw.get("r_age",700),kw.get("r_trips",240),kw.get("r_rating",4.78),kw.get("r_filed",1),kw.get("r_upheld",0),
                    kw.get("r_cancel",0.045),kw.get("r_ns",0),ns30=kw.get("r_ns30",0),cp90=kw.get("cp90",0))
    d=driver_profile(did,snap,kw.get("d_age",1100),kw.get("d_trips",1900),kw.get("d_rating",4.88),kw.get("d_filed",1),kw.get("d_upheld",0),
                     kw.get("d_cancel",0.030),kw.get("d_ns",0),0,kw.get("d_accept",0.91),tier,region,
                     ns30=kw.get("d_ns30",1),trips30=kw.get("d_trips30",120),cp90=kw.get("cp90",0))
    return r,d

def _assemble(c, disp_kw, trip, gps, chatp, fare, rp, dp, advs, gen, assessed, adm_over=None, gps_missing=False):
    tid=f"TRP-{c:05d}"; adm_over=adm_over or {}
    def A(tok, default): return adm_over.get(tok) or adm("COMPLETE", default, assessed)
    ev=[envelope(evid(c,"TRIP"),"TRIP_RECORD",tid,"PLATFORM_TELEMETRY",gen,A("TRIP","Cancelled trip record, causally ordered."),trip),
        envelope(evid(c,"GPS"),"GPS_TRACE",tid,"PLATFORM_TELEMETRY",gen,A("GPS","Driver device telemetry at 10 s cadence from acceptance to cancellation."),gps),
        envelope(evid(c,"CHAT"),"CHAT_LOG",tid,"PLATFORM_TELEMETRY",gen,A("CHAT","In-app chat export for the trip."),chatp),
        envelope(evid(c,"FARE"),"FARE_BREAKDOWN",tid,"PAYMENTS_LEDGER",gen,A("FARE","Ledger line for the cancellation."),fare),
        envelope(evid(c,"RPROF"),"RIDER_PROFILE",tid,"PLATFORM_TELEMETRY",gen,A("RPROF",""),rp),
        envelope(evid(c,"DPROF"),"DRIVER_PROFILE",tid,"PLATFORM_TELEMETRY",gen,A("DPROF",""),dp)]
    for k,(src,a,payload) in enumerate(advs,1):
        ev.append(envelope(evid(c,"ADVIS",k),"TRAFFIC_ADVISORY",tid,src,gen,a,payload))
    ids=[e["evidence_id"] for e in ev]
    disp=dispute(c,"NO_SHOW_CHARGE",disp_kw["by"],disp_kw["at"],disp_kw["claim"],disp_kw["contested"],ids,disp_kw.get("cp"))
    return case_file(c,disp,ev)

def _card(tier): return {"RYDE_X":"RC-SG-2026Q3-RYDEX","RYDE_PLUS":"RC-SG-2026Q3-RYDEPLUS","RYDE_XL":"RC-SG-2026Q3-RYDEXL","RYDE_POOL":"RC-SG-2026Q3-RYDEPOOL","RYDE_TAXI":"RC-SG-2026Q3-RYDETAXI"}[tier]

# =====================================================================
def case_401():
    """EASY / DRIVER_COMPENSATION 4.80. AIRPORT 480 s; driver dwells 490 s; rider verbosity bait; rider_track 1.2 km away."""
    c=401; rng=random.Random(c); zone,tier="AIRPORT","RYDE_PLUS"; fee=ns_fee(zone,tier)
    pick=pt("changi_t1_arr"); req=ts(2026,8,16,21,10,0); acc=req+timedelta(seconds=50)
    reach=acc+timedelta(minutes=9); arr=reach+timedelta(seconds=15); cancel=reach+timedelta(seconds=10+490)
    pts=_drive_then_dwell(c,pt("expo"),_offset(pick,20,15),acc,reach,cancel,rng)
    rider=_rider_track(_offset(pick,-900,800),arr,cancel,rng)  # rider at T2 pick-up, ~1.2 km away
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=rider)
    calls=[("DRIVER",arr+timedelta(minutes=4),25,False)]
    trip=trip_ns(c,"RDR-11020","DRV-11305",req,acc,arr,cancel,geo(lab("changi_t1_arr"),*pick,"VEN-CHANGI-T1"),geo(lab("tampines_hub"),*pt("tampines_hub")),
                 19.5,24.0,zone,tier,reg_points=4,calls=calls,chat_count=4)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=40)),
       msg(c,2,"DRIVER","hi im at T1 arrival bay 3, silver Camry SMX3310K",arr+timedelta(seconds=20),read=arr+timedelta(seconds=45)),
       msg(c,3,"DRIVER","sir are you coming? waiting at bay 3",arr+timedelta(minutes=3),read=arr+timedelta(minutes=3,seconds=30)),
       msg(c,4,"DRIVER","Voice call placed by driver, 0:25, unanswered",arr+timedelta(minutes=4),read=arr+timedelta(minutes=4),channel="VOICE_CALL_LOG")]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=20),_card(tier))
    gen=ts(2026,8,17,10,0,0); ass=gen+timedelta(seconds=8); snap=gen
    rp,dp=_profiles("RDR-11020","DRV-11305",snap,"East (Changi / Tampines)",tier,r_filed=2,r_upheld=1)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Airport Boulevard",ass),None)]
    claim=("I had just landed after a 13 hour flight from London and I was exhausted. I came out to the pick up point as fast as I could, my bag was delayed at the belt which is not my fault. "
           "When I got to the pick up area I looked everywhere for a silver Camry and there was nothing. I walked up and down. Then I get a notification the trip is cancelled and $6 is taken from me. "
           "I have been a Ryde customer since 2021 and I use it every single time I travel. This is a terrible way to treat a loyal customer who just wants to get home after a long flight. "
           "I want the $6 back and I want an apology.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=10),"claim":claim,"contested":fee,
                    "cp":("Waited at T1 arrival bay 3 for over eight minutes as required for airport. Messaged twice, called once, no answer. Rider never appeared.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    comp=m2(fee*0.8)
    dw,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    rd=sum(haversine_km((p['lat'],p['lng']),pick) for p in rider)/len(rider)*1000
    rat=(f"EV-TRIP-00401 records arrived_at, cancellation_reason_code RIDER_NO_SHOW by the driver, pickup_zone_class AIRPORT and vehicle RYDE_PLUS; fee_schedule gives max(6.00 airport, 6.00 plus) = 6.00, "
         f"reconciling with EV-FARE-00401 so POL-NS-08(d) is clean. EV-GPS-00401 shows the driver stationary within the 150 m airport radius with sub-25 m accuracy from the first qualifying fix at {q['ts'].strftime('%H:%M:%S')} through cancellation, a dwell of {dw:.0f} s, "
         f"above the 480 s AIRPORT minimum in POL-NS-01(c); limbs (a)-(d) all hold. EV-CHAT-00401 carries two driver messages delivered and read and a VOICE_CALL_LOG line, mirrored by trip_record.in_app_calls, so POL-NS-04(b) cannot be met; "
         f"and rider_track places the rider's device about {rd:.0f} m away throughout, so POL-NS-04(c) fails affirmatively. The rider's long claim_text is sympathetic but names no evidence. POL-NS-07: EV-DPROF-00401 no_show_terminations_30d 1 of 120 completed, "
         f"no farming pattern. DRIVER_COMPENSATION {comp:.2f} (80% of 6.00); amount_sgd mirrors it and the fee stands.")
    return cf, gt("DRIVER_COMPENSATION",comp,["POL-NS-01","POL-NS-07","POL-NS-02","POL-NS-04"],"EASY",rat,driver_comp=comp)

def case_402():
    """HARD / FULL_REFUND 4.00. False arrival marker: tapped at 48 kph 1.6 km out (POL-NS-05); corrected dwell 210 s. Driver statement is polished."""
    c=402; rng=random.Random(c); zone,tier="STANDARD","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("toa_payoh_blk"); req=ts(2026,8,17,7,33,0); acc=req+timedelta(seconds=30)
    arr=acc+timedelta(minutes=8,seconds=10)                      # tapped while still on PIE
    reach=arr+timedelta(minutes=3,seconds=20)                    # first in-geofence fix 07:44:30-ish
    cancel=reach+timedelta(seconds=10+210)                        # corrected dwell 210 s
    pts=_drive_then_dwell(c,pt("serangoon_blk"),_offset(pick,8,6),acc,reach,cancel,rng)
    # ensure fix at arr timestamp is ~1.6 km away, moving: interp does constant speed; check distance later in rationale
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=_rider_track(_offset(pick,15,-10),arr,cancel,rng))
    trip=trip_ns(c,"RDR-11144","DRV-11072",req,acc,arr,cancel,geo(lab("toa_payoh_blk"),*pick),geo(lab("raffles_place"),*pt("raffles_place")),8.2,15.0,zone,tier,reg_points=1,chat_count=2)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=30)),
       msg(c,2,"DRIVER","here",arr+timedelta(seconds=10),read=arr+timedelta(seconds=35))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=18),_card(tier))
    gen=ts(2026,8,18,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_profiles("RDR-11144","DRV-11072",snap,"Central (Toa Payoh / Bishan)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Toa Payoh Central",ass),None)]
    # find the fix nearest arr and report its distance/speed
    near=min(pts,key=lambda p: abs((p["ts"]-arr).total_seconds()))
    dist_at_arr=haversine_km((near["lat"],near["lng"]),pick)*1000
    claim=("driver cancel on me and charge $4. i was downstairs at 7.44 like the app said. he was not there. refund pls")
    cp=(f"I marked arrived at 07:41:10 on reaching the estate and waited at Blk 79 for the full five minutes and more before cancelling at {cancel.strftime('%H:%M:%S')}. "
        "Rider did not board. I followed the process exactly and the fee is correct.","DRIVER",gen-timedelta(hours=3))
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=1),"claim":claim,"contested":fee,"cp":cp},trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    corrected,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    rat=(f"The driver's statement is precise and confident, but EV-GPS-00402 at the arrived_at timestamp ({arr.strftime('%H:%M:%S')}) places the vehicle about {dist_at_arr:.0f} m from the pin travelling at {near['speed_kph']} km/h: "
         f"both POL-NS-05 triggers fire (over 300 m, at or above 15 km/h), so the arrival marker is FALSE and does not start the waiting clock. The clock is recomputed from the first qualifying in-geofence fix under POL-NS-02, "
         f"which is at {q['ts'].strftime('%H:%M:%S')}; from there to cancellation is {corrected:.0f} s, short of the 300 s STANDARD minimum. POL-NS-05(i) applies: full refund, no driver compensation. "
         f"POL-NS-01(c) fails on the same arithmetic. EV-FARE-00402 cancellation_fee 4.00 reconciles with the schedule. The rider's own presence (rider_track within 100 m) is not required for this outcome. FULL_REFUND 4.00.")
    return cf, gt("FULL_REFUND",fee,["POL-NS-05","POL-NS-02","POL-NS-01","POL-NS-06"],"HARD",rat)

def case_403():
    """EASY / FULL_REFUND 4.00. Wrong entrance at a mall (LARGE_VENUE, 120 m): driver 260 m away, rider named the entrance -> POL-NS-03(i), no compensation."""
    c=403; rng=random.Random(c); zone,tier="LARGE_VENUE","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("westgate"); req=ts(2026,8,18,13,20,0); acc=req+timedelta(seconds=40)
    reach=acc+timedelta(minutes=6); arr=reach+timedelta(seconds=12); cancel=reach+timedelta(seconds=10+350)
    dwell_pt=_offset(pick,-230,120)   # ~260 m
    pts=_drive_then_dwell(c,pt("clementi_mall"),dwell_pt,acc,reach,cancel,rng,venue="VEN-WESTGATE")
    rider=_rider_track(_offset(pick,10,-5),arr,cancel,rng,venue="VEN-WESTGATE")
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=rider)
    trip=trip_ns(c,"RDR-11377","DRV-11190",req,acc,arr,cancel,geo(lab("westgate")+", Taxi Stand Tower B B1",*pick,"VEN-WESTGATE"),geo(lab("one_north"),*pt("one_north")),
                 9.1,16.0,zone,tier,reason="DRIVER_UNABLE_TO_LOCATE",reg_points=3,chat_count=4)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=20)),
       msg(c,2,"RIDER","im at the taxi stand outside tower b basement 1, u where?",arr+timedelta(seconds=40),read=arr+timedelta(seconds=52)),
       msg(c,3,"DRIVER","im at the pickup bay near jem side, come over",arr+timedelta(seconds=75),read=arr+timedelta(seconds=90)),
       msg(c,4,"DRIVER","still waiting",arr+timedelta(minutes=4),read=arr+timedelta(minutes=4,seconds=20))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=15),_card(tier))
    gen=ts(2026,8,19,10,0,0); ass=gen+timedelta(seconds=10); snap=gen
    rp,dp=_profiles("RDR-11377","DRV-11190",snap,"West (Jurong / Clementi)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Gateway Dr",ass),None)]
    dd=haversine_km(dwell_pt,pick)*1000
    claim=("I told him exactly where I was, taxi stand Tower B basement 1. He stayed at the other side and cancelled. Charged $4 for nothing.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=2),"claim":claim,"contested":fee,
                    "cp":("Westgate has many entrances. I was at the private hire bay which is the normal place. She should have come to me.","DRIVER",gen-timedelta(hours=1))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-TRIP-00403 pickup_zone_class LARGE_VENUE gives a 120 m arrival radius under POL-NS-02. EV-GPS-00403 shows the driver stationary for about 350 s at a point roughly {dd:.0f} m from the pin: outside the radius, "
         f"inside 400 m, with gps_point.venue_id VEN-WESTGATE matching trip_record.pickup.venue_id, so POL-NS-03 governs and confirms a wrong-face-of-the-same-venue case. cancellation_reason_code DRIVER_UNABLE_TO_LOCATE "
         f"is the driver's own admission and cannot satisfy POL-NS-01(d). The fee is not chargeable and is refunded in full. Fault for compensation: EV-CHAT-00403 MSG-00403-002 is the rider naming the exact sub-location, and the trace shows the driver never moved; "
         f"POL-NS-03(i) applies and no compensation is payable. The driver did reply within 120 s so POL-NS-04 is not engaged. FULL_REFUND 4.00.")
    return cf, gt("FULL_REFUND",fee,["POL-NS-03","POL-NS-02","POL-NS-01"],"EASY",rat)

def case_404():
    """HARD / FULL_REFUND 4.00 + driver goodwill 2.00. Condo with two guardhouses (registered_pickup_points 2); neither party named one -> POL-NS-03(ii)."""
    c=404; rng=random.Random(c); zone,tier="LARGE_VENUE","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("bayshore_park"); req=ts(2026,8,19,18,45,0); acc=req+timedelta(seconds=45)
    reach=acc+timedelta(minutes=5,seconds=30); arr=reach+timedelta(seconds=10); cancel=reach+timedelta(seconds=10+330)
    dwell_pt=_offset(pick,-280,90)   # guardhouse B ~300 m
    pts=_drive_then_dwell(c,pt("marine_parade"),dwell_pt,acc,reach,cancel,rng,venue="VEN-BAYSHORE-PARK")
    rider=_rider_track(_offset(pick,5,5),arr,cancel,rng,venue="VEN-BAYSHORE-PARK")
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=rider)
    trip=trip_ns(c,"RDR-11508","DRV-11463",req,acc,arr,cancel,geo(lab("bayshore_park"),*pick,"VEN-BAYSHORE-PARK"),geo(lab("suntec"),*pt("suntec")),
                 12.0,18.0,zone,tier,reason="DRIVER_UNABLE_TO_LOCATE",reg_points=2,chat_count=4)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=25)),
       msg(c,2,"DRIVER","arrived",arr+timedelta(seconds=15),read=arr+timedelta(seconds=30)),
       msg(c,3,"RIDER","coming",arr+timedelta(seconds=50),read=arr+timedelta(seconds=60)),
       msg(c,4,"DRIVER","?",arr+timedelta(minutes=4),read=arr+timedelta(minutes=4,seconds=15))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=15),_card(tier))
    gen=ts(2026,8,20,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_profiles("RDR-11508","DRV-11463",snap,"East (Bedok / Marine Parade)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Bayshore Rd",ass),None)]
    dd=haversine_km(dwell_pt,pick)*1000
    claim=("I was at guardhouse A which is where the pin is. He was at the other guardhouse. Nobody said which one. Refund the $4.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=3),"claim":claim,"contested":fee,
                    "cp":("Bayshore has two guardhouses. Pin showed the condo, not which gate. I waited five and a half minutes.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00404 places the driver stationary about {dd:.0f} m from the pin for roughly 330 s, outside the 120 m LARGE_VENUE radius and inside 400 m, with venue_id VEN-BAYSHORE-PARK on both the fixes and the pin, "
         f"so POL-NS-03 governs: POL-NS-01(b) fails and the fee is refunded in full. Fault allocation from EV-CHAT-00404: 'arrived', 'coming', '?' - neither party specified a guardhouse, and EV-TRIP-00404 registered_pickup_points is 2, "
         f"so POL-NS-03(ii) attributes the mislocation to pin ambiguity and pays the driver a platform-funded goodwill payment of 50% of the fee, 2.00, never recovered from the rider. Per POL-GEN-03 the two figures are independent and both fields are populated; "
         f"the ruling value names the FILING party's outcome. FULL_REFUND 4.00 with driver_compensation_sgd 2.00.")
    return cf, gt("FULL_REFUND",fee,["POL-NS-03","POL-NS-02","POL-GEN-03"],"HARD",rat,driver_comp=2.00)

def _ns04_common(c, call, rng):
    zone,tier="STANDARD","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("bedok_blk12"); req=ts(2026,8,20,9,5,0); acc=req+timedelta(seconds=35)
    reach=acc+timedelta(minutes=5); arr=reach+timedelta(seconds=10); cancel=reach+timedelta(seconds=10+320)
    pts=_drive_then_dwell(c,pt("bedok_mall"),_offset(pick,6,4),acc,reach,cancel,rng)
    rider=_rider_track(_offset(pick,35,-20),arr,cancel,rng)
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=rider)
    calls=[("DRIVER",arr+timedelta(seconds=90),18,False)] if call else []
    trip=trip_ns(c,f"RDR-116{c%100:02d}",f"DRV-117{c%100:02d}",req,acc,arr,cancel,geo(lab("bedok_blk12"),*pick),geo(lab("paya_lebar_sq"),*pt("paya_lebar_sq")),
                 6.4,12.0,zone,tier,reg_points=1,calls=calls,chat_count=3 if call else 2)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=15)),
       msg(c,2,"RIDER","im at blk 12 void deck, cant see any car, where r u?",arr+timedelta(seconds=55),read=arr+timedelta(seconds=70))]
    if call: m.append(msg(c,3,"DRIVER","Voice call placed by driver, 0:18, unanswered",arr+timedelta(seconds=90),read=arr+timedelta(seconds=90),channel="VOICE_CALL_LOG"))
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=15),_card(tier))
    return zone,tier,fee,pick,arr,cancel,gps,trip,chatp,fare,pts

def case_405():
    """EASY / FULL_REFUND 4.00. Rider messaged; driver neither replied nor called; rider present -> POL-NS-04."""
    c=405; rng=random.Random(c)
    zone,tier,fee,pick,arr,cancel,gps,trip,chatp,fare,pts=_ns04_common(c,False,rng)
    dw,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    gen=ts(2026,8,21,10,0,0); ass=gen+timedelta(seconds=8); snap=gen
    rp,dp=_profiles(trip["rider_id"],trip["driver_id"],snap,"East (Bedok / Tampines)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Bedok South Rd",ass),None)]
    claim=("i messaged him i'm at the void deck and asked where he is. no reply. then cancelled and charged me. i was standing there.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=1),"claim":claim,"contested":fee,
                    "cp":("I was at the block for over five minutes. She never came down.","DRIVER",gen-timedelta(hours=2))},trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    rat=(f"EV-GPS-00405 shows the driver correctly inside the 50 m STANDARD radius with a dwell of {dw:.0f} s from the first qualifying fix at {q['ts'].strftime('%H:%M:%S')}, so POL-NS-01(a)-(d) are satisfied on their own terms. But POL-NS-04 displaces them: (a) EV-CHAT-00405 MSG-00405-002 is a rider message "
         f"in the waiting window stating her position and asking the driver's, delivered and read; (b) the driver posted no reply within 120 s or at all, and EV-TRIP-00405 in_app_calls is empty; (c) rider_track places the rider's device within the 100 m "
         f"presence radius with sub-25 m accuracy for the majority of fixes. All three limbs hold, the rider is exonerated, and no driver compensation is payable. FULL_REFUND 4.00.")
    return cf, gt("FULL_REFUND",fee,["POL-NS-04","POL-NS-01","POL-NS-02"],"EASY",rat)

def case_406():
    """HARD / DRIVER_COMPENSATION 3.20. Same facts as 405 but driver placed an unanswered in-app call -> POL-NS-04(b) fails -> POL-NS-01 + NS-07."""
    c=406; rng=random.Random(c)
    zone,tier,fee,pick,arr,cancel,gps,trip,chatp,fare,pts=_ns04_common(c,True,rng)
    dw,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    gen=ts(2026,8,22,10,0,0); ass=gen+timedelta(seconds=8); snap=gen
    rp,dp=_profiles(trip["rider_id"],trip["driver_id"],snap,"East (Bedok / Tampines)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Bedok South Rd",ass),None)]
    claim=("messaged him where i was, he never replied in the chat. cancelled on me. refund.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=1),"claim":claim,"contested":fee,
                    "cp":("I called her when I saw the message, she did not pick up. Waited the full time.","DRIVER",gen-timedelta(hours=2))},trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    comp=m2(fee*0.8)
    rat=(f"The rider's message (MSG-00406-002) and presence would satisfy POL-NS-04(a) and (c), but limb (b) requires that the driver NEITHER replied in chat within 120 s NOR placed an in-app voice call before terminating. "
         f"EV-TRIP-00406 in_app_calls records a DRIVER call at {arr.strftime('%H:%M:%S')}+90 s, 18 s, unanswered, mirrored by the VOICE_CALL_LOG line MSG-00406-003; POL-NS-04's own notes say this defeats the clause even where the chat shows nothing. "
         f"POL-NS-04 does not apply and the dispute is decided under POL-NS-01: arrived, in-radius with sub-25 m fixes, dwell {dw:.0f} s over the 300 s minimum, RIDER_NO_SHOW by the driver. Anti-farming under POL-NS-07 is clean "
         f"(no_show_terminations_30d 1). DRIVER_COMPENSATION {comp:.2f}; the rider's fee stands. A Judge that reads only the chat and misses trip_record.in_app_calls reverses this case.")
    return cf, gt("DRIVER_COMPENSATION",comp,["POL-NS-04","POL-NS-01","POL-NS-07"],"HARD",rat,driver_comp=comp)

def case_407():
    """HARD / FULL_REFUND 6.00. TRANSPORT_HUB (fee 6.00); dwell 298 s < 300; rider was not present - POL-NS-06 strict liability."""
    c=407; rng=random.Random(c); zone,tier="TRANSPORT_HUB","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("je_interchange"); req=ts(2026,8,21,17,0,0); acc=req+timedelta(seconds=40)
    reach=acc+timedelta(minutes=1,seconds=30); arr=reach+timedelta(seconds=10); cancel=reach+timedelta(seconds=10+298)
    pts=_drive_then_dwell(c,pt("westgate"),_offset(pick,10,8),acc,reach,cancel,rng)
    rider=_rider_track(_offset(pick,650,-620),arr,cancel,rng)   # ~900 m away
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=rider)
    trip=trip_ns(c,"RDR-11815","DRV-11242",req,acc,arr,cancel,geo(lab("je_interchange"),*pick,"VEN-JE-INTERCHANGE"),geo(lab("bukit_batok_mrt"),*pt("bukit_batok_mrt")),
                 4.1,9.0,zone,tier,reason="EXCESSIVE_WAIT",reg_points=1,chat_count=2)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=90)),
       msg(c,2,"DRIVER","at the PHV bay, cannot wait long here",arr+timedelta(minutes=2),read=arr+timedelta(minutes=2,seconds=30))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=12),_card(tier))
    gen=ts(2026,8,22,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_profiles("RDR-11815","DRV-11242",snap,"West (Jurong / Bukit Batok)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("the Jurong East interchange bay",ass),None)]
    claim=("charged $6 for a cancel at jurong east. i was still coming out from the mrt. he didn't even wait the 5 min.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(minutes=40),"claim":claim,"contested":fee,
                    "cp":("Interchange bay, enforcement officers chase you after five minutes. I waited five minutes. Rider was nowhere.","DRIVER",gen-timedelta(hours=2))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    dw,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    rat=(f"EV-TRIP-00407 pickup_zone_class TRANSPORT_HUB and vehicle RYDE_X: fee_schedule gives max(6.00 hub, 4.00 tier) = 6.00, matching EV-FARE-00407. POL-NS-01(c) requires a continuous in-geofence dwell of at least 300 s measured from the first "
         f"qualifying fix. EV-GPS-00407: first qualifying in-radius fix at {q['ts'].strftime('%H:%M:%S')}, cancellation at {cancel.strftime('%H:%M:%S')}, dwell {dw:.0f} s, a {300-dw:.0f} s shortfall. POL-NS-06 is strict liability: "
         f"the fee is not chargeable and is refunded in full whether or not the rider was present, and rider_track showing the rider about 900 m away does not change that. No advisory supports POL-NS-06(i) interval summing. FULL_REFUND 6.00, no compensation.")
    return cf, gt("FULL_REFUND",fee,["POL-NS-06","POL-NS-01","POL-NS-02"],"HARD",rat)

def case_408():
    """HARD / NO_ACTION. DRIVER-filed over an already-reversed fee; dwell 240 s so his claim is unsupported; NO_ACTION leaves the rider refunded (POL-GEN-03)."""
    c=408; rng=random.Random(c); zone,tier="STANDARD","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("yew_tee_blk"); req=ts(2026,8,22,6,50,0); acc=req+timedelta(seconds=30)
    reach=acc+timedelta(minutes=4); arr=reach+timedelta(seconds=10); cancel=reach+timedelta(seconds=10+240)
    pts=_drive_then_dwell(c,pt("bukit_batok_mrt"),_offset(pick,5,7),acc,reach,cancel,rng)
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=_rider_track(_offset(pick,400,300),arr,cancel,rng))
    trip=trip_ns(c,"RDR-11930","DRV-11618",req,acc,arr,cancel,geo(lab("yew_tee_blk"),*pick),geo(lab("jurong_east_mrt"),*pt("jurong_east_mrt")),7.8,13.0,zone,tier,reg_points=1,chat_count=2)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=None,delivered=arr+timedelta(seconds=1)),
       msg(c,2,"DRIVER","here at blk 621",arr+timedelta(seconds=20),read=None,delivered=arr+timedelta(seconds=21))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=15),_card(tier),status="REFUNDED",refunded=fee)
    gen=ts(2026,8,24,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_profiles("RDR-11930","DRV-11618",snap,"West (Choa Chu Kang / Bukit Batok)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Choa Chu Kang St 62",ass),None)]
    chat_adm=adm("IMPAIRED","Both entries delivered; neither shows a read receipt.",ass,
                 [{"code":"UNREAD_MESSAGE","detail":"MSG-00408-001 and MSG-00408-002 have read_at null; delivered_at is populated for both."}])
    claim=("Support reversed my $4 no-show fee two days ago after the rider complained. I drove to Yew Tee at 7am, marked arrived, waited, rider never came. I want the fee reinstated and paid to me.")
    cf=_assemble(c,{"by":"DRIVER","at":gen-timedelta(hours=20),"claim":claim,"contested":fee,
                    "cp":("I came down and the car was gone. He didn't wait five minutes.","RIDER",gen-timedelta(hours=5))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass,adm_over={"CHAT":chat_adm})
    dw,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    rat=(f"This dispute is filed by the DRIVER over a fee EV-FARE-00408 shows as payment_status REFUNDED with refund_issued_sgd 4.00. The question is whether the driver's claim that the fee was properly chargeable is made out. "
         f"EV-GPS-00408: first qualifying in-radius fix at {q['ts'].strftime('%H:%M:%S')}, cancellation at {cancel.strftime('%H:%M:%S')}, dwell {dw:.0f} s, {300-dw:.0f} s short of the STANDARD minimum. POL-NS-01(c) fails and POL-NS-06 says the fee is not chargeable. "
         f"The driver's claim is therefore not supported. Under POL-GEN-03, NO_ACTION is PARTY-RELATIVE: the filing party did not make out their claim and the present state stands, which here means the rider remains refunded. "
         f"A literal reading of POL-NS-06's 'refunded in full' would emit FULL_REFUND, but the fee has already been reversed and the filing party is the driver; the correct value is NO_ACTION with amount null. "
         f"EV-CHAT-00408 is IMPAIRED (UNREAD_MESSAGE, weight 0.85) but the deciding fact rests on the trace and trip record at weight 1.0, so confidence is uncapped.")
    return cf, gt("NO_ACTION",None,["POL-GEN-03","POL-NS-06","POL-NS-01"],"HARD",rat)

def case_409():
    """HARD / ESCALATE + POL-NS-07 instruction. Clean no-show facts; driver anti-farming trips (5 of 40 in 30 d); lifetime counter is 1 (near-synonym trap)."""
    c=409; rng=random.Random(c); zone,tier="STANDARD","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("kallang_blk"); req=ts(2026,8,23,23,30,0); acc=req+timedelta(seconds=40)
    reach=acc+timedelta(minutes=5,seconds=30); arr=reach+timedelta(seconds=10); cancel=reach+timedelta(seconds=10+330)
    pts=_drive_then_dwell(c,pt("geylang_blk"),_offset(pick,7,5),acc,reach,cancel,rng)
    rider=_rider_track(_offset(pick,500,400),arr,cancel,rng)
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=rider)
    calls=[("DRIVER",arr+timedelta(minutes=3),20,False)]
    trip=trip_ns(c,"RDR-11256","DRV-11884",req,acc,arr,cancel,geo(lab("kallang_blk"),*pick),geo(lab("changi_t3"),*pt("changi_t3")),16.5,21.0,zone,tier,reg_points=1,calls=calls,chat_count=3)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=30)),
       msg(c,2,"DRIVER","arrived blk 27",arr+timedelta(seconds=15),read=arr+timedelta(seconds=40)),
       msg(c,3,"DRIVER","Voice call placed by driver, 0:20, unanswered",arr+timedelta(minutes=3),read=arr+timedelta(minutes=3),channel="VOICE_CALL_LOG")]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=15),_card(tier))
    gen=ts(2026,8,24,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_profiles("RDR-11256","DRV-11884",snap,"Central (Kallang / Geylang)",tier,d_ns=1,d_ns30=5,d_trips30=40,d_accept=0.62,d_cancel=0.11)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Kallang Bahru",ass),None)]
    claim=("I booked to the airport at 11.30pm and came down within a few minutes. Driver cancelled and charged $4. I had to book again.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=9),"claim":claim,"contested":fee,
                    "cp":("Arrived, waited over five minutes, called, no answer. Standard no-show.","DRIVER",gen-timedelta(hours=1))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    dw,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    rat=(f"On this trip's evidence POL-NS-01 is satisfied: EV-GPS-00409 in-radius dwell {dw:.0f} s with sub-25 m fixes, EV-TRIP-00409 RIDER_NO_SHOW by the driver, a message and an unanswered call, rider_track about 640 m away. "
         f"POL-NS-07 would then pay the driver 3.20, but it is subject to the anti-farming check on the exact fields it names: EV-DPROF-00409 no_show_terminations_30d is 5 (at least 4) and 5 / completed_trips_30d 40 = 0.125, greater than 0.08. "
         f"Both limbs trip. prior_no_show_flags is 1, but that is the lifetime counter, is NOT the field POL-NS-07 or POL-NS-09(d) reads, and reading it instead would miss the pattern. Compensation is WITHHELD and the case escalates under POL-NS-09(d); "
         f"the fee is held rather than collected or refunded, and the escalation packet must carry POL-NS-07's instruction directing the reviewer to refund the rider's fee in full. ESCALATE, amount null, with that referral recorded.")
    return cf, gt("ESCALATE",None,["POL-NS-07","POL-NS-09","POL-NS-01","POL-GEN-01"],"HARD",rat,
                  referrals=["POL-NS-07 instruction: refund the rider's cancellation fee in full"])

def case_410():
    """INDETERMINATE / ESCALATE. trip_record says 6.5 min dwell; GPS places driver 850 m away throughout with good accuracy -> POL-NS-09(b)."""
    c=410; rng=random.Random(c); zone,tier="STANDARD","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("serangoon_blk"); req=ts(2026,8,24,9,2,0); acc=req+timedelta(seconds=35)
    reach=acc+timedelta(minutes=6,seconds=55); arr=ts(2026,8,24,9,10,0); cancel=ts(2026,8,24,9,16,30)
    far=_offset(pick,-600,600)   # ~850 m
    pts=_drive_then_dwell(c,pt("hougang_mall"),far,acc,reach,cancel,rng,dwell_acc=(5.0,11.0))
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=_rider_track(_offset(pick,12,-8),arr,cancel,rng))
    trip=trip_ns(c,"RDR-11692","DRV-11417",req,acc,arr,cancel,geo(lab("serangoon_blk"),*pick),geo(lab("farrer_park"),*pt("farrer_park")),6.9,13.0,zone,tier,reg_points=1,chat_count=2)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=20)),
       msg(c,2,"RIDER","where are you? im at the block",arr+timedelta(minutes=2),read=arr+timedelta(minutes=2,seconds=10))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=14),_card(tier))
    gen=ts(2026,8,25,10,0,0); ass=gen+timedelta(seconds=10); snap=gen
    rp,dp=_profiles("RDR-11692","DRV-11417",snap,"North-East (Serangoon / Hougang)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Serangoon Ave 3",ass),None)]
    dd=haversine_km(far,pick)*1000
    trip_adm=adm("IMPAIRED",f"The arrival marker and cancellation imply a 6.5 min wait at the pin; the trace does not agree.",ass,
                 [{"code":"CROSS_SOURCE_CONFLICT","detail":f"trip_record arrived_at {fmt(arr)} through cancelled_at {fmt(cancel)} implies presence at the pin, but EV-GPS-00410 holds every fix in that interval about {dd:.0f} m from the pin at 5-11 m accuracy.",
                   "related_evidence_ids":["EV-GPS-00410"]}])
    claim=("he never came to my block. app said arrived but no car. i even messaged. then charged $4.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=2),"claim":claim,"contested":fee,
                    "cp":("I was at Blk 231 for six minutes. Rider did not come down.","DRIVER",gen-timedelta(hours=3))},
                 trip,gps,chatp,fare,rp,dp,advs,gen,ass,adm_over={"TRIP":trip_adm})
    rat=(f"EV-TRIP-00410 records arrived_at 09:10:00 and cancelled_at 09:16:30, a 6.5 min dwell at the pin. EV-GPS-00410, COMPLETE at weight 1.0 with 5-11 m accuracy, places the driver stationary about {dd:.0f} m from the pin for that entire interval, "
         f"outside the 50 m radius, outside 300 m (so not POL-NS-05's false-marker case, which concerns a moving driver) and outside 400 m (so not POL-NS-03's wrong-entrance case). Two admissible artifacts contradict each other directly on arrival and dwell "
         f"and no clause resolves the conflict; the trip record is tagged CROSS_SOURCE_CONFLICT at weight 0.40, but the conflict itself is the finding. This is POL-NS-09(b) in terms. The tribunal declines to pick a side: ESCALATE, fee held. "
         f"The reviewer should obtain the driver's device log or the platform's arrival-marker source to determine which record is corrupt.")
    return cf, gt("ESCALATE",None,["POL-NS-09","POL-NS-02","POL-NS-01"],"INDETERMINATE",rat)

def case_411():
    """INDETERMINATE / ESCALATE. GPS_TRACE MISSING; deciding fact rests on nothing at weight > 0 -> POL-GEN-02(2) cap 0.0 -> POL-NS-09(a)."""
    c=411; rng=random.Random(c); zone,tier="STANDARD","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("geylang_blk"); req=ts(2026,8,25,20,15,0); acc=req+timedelta(seconds=45)
    arr=acc+timedelta(minutes=6); cancel=arr+timedelta(minutes=6)
    trip=trip_ns(c,"RDR-11071","DRV-11529",req,acc,arr,cancel,geo(lab("geylang_blk"),*pick),geo(lab("harbourfront"),*pt("harbourfront")),11.2,18.0,zone,tier,reg_points=1,chat_count=3)
    m=[msg(c,1,"DRIVER","here",arr+timedelta(seconds=20),read=arr+timedelta(seconds=50)),
       msg(c,2,"RIDER","where? i dont see",arr+timedelta(minutes=1,seconds=30),read=arr+timedelta(minutes=1,seconds=40)),
       msg(c,3,"DRIVER","at the block",arr+timedelta(minutes=1,seconds=55),read=arr+timedelta(minutes=2,seconds=10))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=16),_card(tier))
    gen=ts(2026,8,26,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_profiles("RDR-11071","DRV-11529",snap,"Central (Geylang / Kallang)",tier)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Geylang Bahru",ass),None)]
    gps_adm=adm("MISSING","Artifact absent. The identifier is minted so that the absence itself is citable.",ass,
                [{"code":"MISSING_ARTIFACT","detail":"No telemetry was received from the driver device for this trip; the platform holds no GPS record between acceptance and cancellation."}])
    claim=("driver said 'here' but there was no car at my block. i asked where, he just said 'at the block'. then cancel and $4 gone.")
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(hours=1),"claim":claim,"contested":fee,
                    "cp":("I was at Blk 51. My phone GPS was acting up that day. Waited six minutes.","DRIVER",gen-timedelta(hours=2))},
                 trip,None,chatp,fare,rp,dp,advs,gen,ass,adm_over={"GPS":gps_adm})
    rat=(f"EV-GPS-00411 is MISSING at weight 0.0. Every clause that could decide this case - POL-NS-01(b)(c), POL-NS-02, POL-NS-03, POL-NS-05, POL-NS-06 - requires the gps_trace, and POL-GEN-02 states a MISSING artifact can carry no fact; "
         f"its absence is citable, its contents are not. The only evidence of the driver's presence is EV-TRIP-00411 arrived_at, which is the driver's own tap, and EV-CHAT-00411, which records both parties asserting positions the record cannot verify. "
         f"Under POL-GEN-02(2) the deciding fact rests solely on an artifact at weight 0.0, so confidence is capped at 0.0, below the 0.70 floor, and POL-NS-09(a) requires escalation. Neither party's account is preferred: the fee is neither chargeable nor refundable on this record. "
         f"ESCALATE with the fee held; the reviewer should seek the driver's device-side location history or any venue CCTV for the window.")
    return cf, gt("ESCALATE",None,["POL-GEN-02","POL-NS-09","POL-NS-01"],"INDETERMINATE",rat)

def case_412():
    """REVERSAL / FULL_REFUND 4.00. Rider's lifetime profile is poor and driver's is spotless; but the driver cancelled at 200 s (POL-NS-06)."""
    c=412; rng=random.Random(c); zone,tier="STANDARD","RYDE_X"; fee=ns_fee(zone,tier)
    pick=pt("sembawang_mrt"); req=ts(2026,8,26,12,40,0); acc=req+timedelta(seconds=30)
    reach=acc+timedelta(minutes=4,seconds=40); arr=reach+timedelta(seconds=10); cancel=reach+timedelta(seconds=10+200)
    pts=_drive_then_dwell(c,pt("yishun_mrt"),_offset(pick,6,-4),acc,reach,cancel,rng)
    rider=_rider_track(_offset(pick,60,40),arr,cancel,rng)
    gps,_,_,_=build_gps(f"TRP-{c:05d}",pts,acc,cancel,rider_track=rider)
    trip=trip_ns(c,"RDR-11348","DRV-11760",req,acc,arr,cancel,geo(lab("sembawang_mrt"),*pick),geo(lab("woodlands_mrt"),*pt("woodlands_mrt")),4.6,8.0,zone,tier,reg_points=1,chat_count=2)
    m=[msg(c,1,"SYSTEM","Your driver has arrived",arr+timedelta(seconds=1),read=arr+timedelta(seconds=12)),
       msg(c,2,"DRIVER","exit A",arr+timedelta(seconds=25),read=arr+timedelta(seconds=40))]
    chatp=chat(trip["trip_id"],m)
    fare=fare_cancel(trip["trip_id"],fee,cancel+timedelta(seconds=15),_card(tier))
    gen=ts(2026,8,27,10,0,0); ass=gen+timedelta(seconds=9); snap=gen
    rp,dp=_profiles("RDR-11348","DRV-11760",snap,"North (Sembawang / Yishun)",tier,
                    r_rating=3.82,r_filed=9,r_upheld=1,r_cancel=0.190,r_ns=6,r_ns30=1,
                    d_rating=4.97,d_filed=0,d_upheld=0,d_cancel=0.010,d_ns=0,d_trips=4200,d_age=2100)
    advs=[("THIRD_PARTY_LTA",_missing_adv("Canberra Rd",ass),None)]
    claim=("cancelled on me AGAIN. $4. this is a joke. refund.")
    cp=("Arrived at Sembawang MRT Exit A on time, messaged the rider, no reply. This rider's history speaks for itself. I have driven 4,200 trips with a 4.97 rating and have never had a fee reversed. "
        "I ask that the fee stand.","DRIVER",gen-timedelta(hours=2))
    cf=_assemble(c,{"by":"RIDER","at":cancel+timedelta(minutes=30),"claim":claim,"contested":fee,"cp":cp},trip,gps,chatp,fare,rp,dp,advs,gen,ass)
    dw,q=dwell_sec(pts,pick,NS_ARR_R[zone],cancel)
    rat=(f"EV-RPROF-00412 shows a poor lifetime record (rating 3.82, 9 disputes filed, 6 prior_no_show_flags) and EV-DPROF-00412 an exemplary one, and the driver's statement invites the tribunal to decide on that basis. POL-GEN-01 forbids it: "
         f"every one of those fields is CONTEXT ONLY, and the only citable rider counter, no_show_disputes_30d, is 1, below POL-NS-09(d)'s threshold of 3. The case is decided on this trip's evidence. EV-GPS-00412: first qualifying in-radius fix at "
         f"{q['ts'].strftime('%H:%M:%S')}, cancellation at {cancel.strftime('%H:%M:%S')}, dwell {dw:.0f} s, {300-dw:.0f} s short of the STANDARD minimum. POL-NS-01(c) fails and POL-NS-06 refunds the fee in full regardless of the rider's response. "
         f"rider_track incidentally places the rider within 100 m. FULL_REFUND 4.00, no compensation. A Judge that weights the profiles reverses this case.")
    return cf, gt("FULL_REFUND",fee,["POL-NS-06","POL-NS-01","POL-GEN-01"],"REVERSAL",rat)

NS_CASES=[case_401,case_402,case_403,case_404,case_405,case_406,case_407,case_408,case_409,case_410,case_411,case_412]
