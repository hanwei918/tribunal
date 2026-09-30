"""NO_SHOW_CHARGE wild cases 601+."""
from core import ts, m2
from places import pt
from wild import off
from specs_rd import st

NS = []
def add(**s): NS.append(s)

def full(F): return "FULL_REFUND", F["fee"], None
def noact(F): return "NO_ACTION", None, None
def esc(F): return "ESCALATE", None, None
def dcomp(F): a = m2(F["fee"]*0.8); return "DRIVER_COMPENSATION", a, a

def approach(origin, pick, mins, dwell_off=(8,6), stop_off=None):
    """drive from origin to a dwell point near pick (offset metres north/east)."""
    d = off(pick, *dwell_off) if stop_off is None else off(pick, *stop_off)
    return [("drive", [origin, off(pick, 400, -300), d], mins)]

# 601 <- EN-NS-01 arrives, 55 s, leaves with other passengers; SYSTEM cancels; rider messaged, no reply
claim, cp = st("EN-NS-01")
P = pt("gardens_bay")
add(no=601, seed="EN-NS-01", req=ts(2026,9,1,21,40,0), zone="LARGE_VENUE", tier="RYDE_X", pick="gardens_bay", drop="hougang_mall", rider="RDR-30601", driver="DRV-30117", region="Central (Marina)",
    legs=approach("suntec", P, 6) + [("dwell", off(P,8,6), 55), ("drive", [off(P,8,6), off(P,200,300), off(P,900,1400)], 5)],
    arr_s=6*60+15, cancel_s=6*60+10+55+300, by_cancel="SYSTEM", reason="SYSTEM_TIMEOUT",
    rider_track=(12,-9, 6*60, 6*60+10+55+300), msgs=[("SYSTEM","Your driver has arrived",6*60+16),("RIDER","I'm at the Bayfront pickup, is the black Vios you? you are driving off!",6*60+70,"IN_APP",None)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-06","POL-NS-01","POL-NS-04","POL-NS-02"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d} shows cancelled_by SYSTEM with SYSTEM_TIMEOUT, so POL-NS-01(d) - termination by the driver with a no-show code at or after the required dwell - already fails and the fee is not chargeable under that clause. "
        f"EV-GPS-{T['c']:05d} does contain a qualifying arrival (first in-radius fix at {T['q']}, LARGE_VENUE radius {T['R']} m), but the vehicle leaves the geofence after {T['dwellc']} s and is more than 1 km away at cancellation: the continuous in-geofence dwell is {T['dwellc']} s against the {T['min']} s minimum, so POL-NS-06 refunds the fee in full with no driver compensation. "
        f"POL-NS-04 also holds: the rider's message at 21:47 on EV-CHAT-{T['c']:05d} is a locating message, EV-TRIP-{T['c']:05d}.in_app_calls is empty and no reply followed, and rider_track keeps the rider within the 150 m presence radius (mean {T['rider_d']} m). FULL_REFUND {T['fee']}."))

# 602 <- EN-NS-02 driver never approaches, talks rider into cancelling
claim, cp = st("EN-NS-02")
P = pt("jurong_blk")
add(no=602, seed="EN-NS-02", req=ts(2026,9,2,19,5,0), zone="STANDARD", tier="RYDE_X", pick="jurong_blk", drop="punggol_hdb", rider="RDR-30602", driver="DRV-30204", region="West (Jurong)",
    legs=[("drive", ["jurong_condo", off(P,-1500,-1100)], 3), ("dwell", off(P,-1500,-1100), 9*60)],
    arr_s=None, cancel_s=11*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND",
    rider_track=(10,5, 3*60, 11*60), msgs=[("DRIVER","you are not at the pin",4*60),("DRIVER","battery almost 0, cannot do 22 km",5*60),("DRIVER","can you cancel? if I cancel I kena suspend",6*60),("RIDER","ok fine",10*60+30)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-02","POL-NS-01"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d} has arrived_at null and cancelled_by RIDER, so POL-NS-01(a) and (d) both fail. EV-GPS-{T['c']:05d} places the driver stationary about {T['d_tail']} m from the pin from 19:09 to cancellation at {T['cancel']}; the nearest fix in the whole trace is {T['d_min']} m, "
        f"so there is no qualifying in-radius fix (STANDARD radius {T['R']} m) in the 15 minutes preceding cancellation and POL-NS-02 says the driver never arrived: full refund. EV-CHAT-{T['c']:05d} shows the cancellation was requested by the driver, which explains but is not needed for the outcome. No driver compensation. FULL_REFUND {T['fee']}."))

# 603 <- EN-NS-03 'two minutes': dwell 140 s then driver cancels
claim, cp = st("EN-NS-03")
P = pt("bishan_condo")
add(no=603, seed="EN-NS-03", req=ts(2026,9,3,8,5,0), zone="LARGE_VENUE", tier="RYDE_X", pick="bishan_condo", drop="raffles_place", rider="RDR-30603", driver="DRV-30311", region="Central (Bishan)",
    legs=approach("junction8", P, 5) + [("dwell", off(P,8,6), 140)],
    arr_s=5*60+12, cancel_s=5*60+10+140, by_cancel="DRIVER", reason="RIDER_NO_SHOW",
    calls=[("DRIVER", 5*60+20, 22, True)], rider_track=(30,20, 5*60, 5*60+10+140),
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-06","POL-NS-01","POL-NS-02"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} shows a qualifying arrival at {T['q']} within the LARGE_VENUE radius of {T['R']} m, and EV-TRIP-{T['c']:05d} records the driver terminating with RIDER_NO_SHOW at {T['cancel']}: a dwell of {T['dwell']} s against the {T['min']} s minimum in POL-NS-01(c). "
        f"POL-NS-06 is strict liability on the shortfall: the fee is not chargeable and is refunded in full whether or not the rider was present, and no driver compensation is payable. The answered 22 s in-app call on EV-TRIP-{T['c']:05d} defeats POL-NS-04 but does not repair the dwell. EV-FARE-{T['c']:05d} cancellation_fee {T['fee']} reconciles with the schedule. FULL_REFUND {T['fee']}."))

# 604 <- EN-NS-04 driver 220 m away on the main road, refuses to come to the block; rider named the block; rider cancels
claim, cp = st("EN-NS-04")
P = pt("toa_payoh_bay")
add(no=604, seed="EN-NS-04", req=ts(2026,9,4,9,40,0), zone="STANDARD", tier="RYDE_X", pick="toa_payoh_bay", drop="novena_sq", rider="RDR-30604", driver="DRV-30422", region="Central (Toa Payoh)",
    legs=[("drive", ["toa_payoh_blk", off(P,180,120)], 4), ("dwell", off(P,180,120), 7*60)],
    arr_s=4*60+12, cancel_s=4*60+10+7*60, by_cancel="RIDER", reason="WRONG_PICKUP_LOCATION",
    rider_track=(6,4, 4*60, 11*60+10), msgs=[("DRIVER","come to main road",4*60+30),("RIDER","my dad cannot walk, pls come to the block pickup bay Blk 185",4*60+70),("DRIVER","cannot",4*60+100)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-03","POL-NS-02","POL-NS-01"], difficulty="HARD",
    rationale=lambda F,T: (f"At the arrived_at timestamp EV-GPS-{T['c']:05d} places the driver about {T['d_at_arr']} m from the pin, stationary; that is outside the 50 m STANDARD radius but within 300 m, so POL-NS-05 is not engaged and POL-NS-03 governs. "
        f"The driver then holds that position for the whole seven minutes (median distance over the last minute {T['d_tail']} m, under the 400 m ceiling), so this is a wrong-position arrival: POL-NS-01(b) fails and the fee is refunded in full. "
        f"Fault for compensation is allocated from EV-CHAT-{T['c']:05d}: the rider stated the correct sub-location ('block pickup bay Blk 185') and the driver did not move before the trip ended, so POL-NS-03(i) applies and no driver payment issues. rider_track keeps the rider at the bay. FULL_REFUND {T['fee']}."))

# 605 <- EN-NS-05 driver 3.1 km away for 22 min, four unanswered calls, rider cancels
claim, cp = st("EN-NS-05")
P = pt("geylang_hdb")
add(no=605, seed="EN-NS-05", req=ts(2026,9,5,18,30,0), zone="STANDARD", tier="RYDE_X", pick="geylang_hdb", drop="paya_lebar_sq", rider="RDR-30605", driver="DRV-30536", region="East (Geylang)",
    legs=[("drive", ["kallang_blk", off(P,-2200,-2200)], 2), ("dwell", off(P,-2200,-2200), 22*60)],
    arr_s=None, cancel_s=24*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND",
    calls=[("RIDER",6*60,20,False),("RIDER",10*60,25,False),("RIDER",15*60,20,False),("RIDER",20*60,30,False)], rider_track=(8,6, 2*60, 24*60),
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-02","POL-NS-01"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d}: arrived_at null, cancelled_by RIDER after 24 minutes. EV-GPS-{T['c']:05d} shows the driver stationary about {T['d_tail']} m from the pin for the entire window (nearest fix {T['d_min']} m), so there is no qualifying in-radius fix in the 15 minutes before cancellation and POL-NS-02 directs a full refund: the driver never arrived and POL-NS-01(a)-(b) fail. "
        f"The four unanswered rider-placed calls on EV-TRIP-{T['c']:05d}.in_app_calls are consistent but not decisive. The rider's remorse in the claim_text is not a fact about the trip. No driver compensation. FULL_REFUND {T['fee']}."))

# 606 <- EN-NS-06 'arrived' while circling 450 m out; never a qualifying fix; SYSTEM cancels -> NS-05(ii)
claim, cp = st("EN-NS-06")
P = pt("clarke_quay"); L = [off(P,450,0), off(P,450,500), off(P,900,500), off(P,900,0), off(P,450,0)]
add(no=606, seed="EN-NS-06", req=ts(2026,9,6,23,10,0), zone="LARGE_VENUE", tier="RYDE_PLUS", pick="clarke_quay", drop="bedok_blk12", rider="RDR-30606", driver="DRV-30640", region="Central (River Valley)",
    legs=[("drive", ["great_world", L[0]], 4), ("drive", L+L[1:]+L[1:], 9)], acc_range=(6.0,14.0),
    arr_s=4*60+40, cancel_s=13*60, by_cancel="SYSTEM", reason="SYSTEM_TIMEOUT",
    calls=[("RIDER",5*60,40,True)], rider_track=(10,8, 4*60, 13*60), msgs=[("DRIVER","car problem, you cancel",5*60+50),("RIDER","no, you cancel",6*60)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-05","POL-NS-02","POL-NS-01"], difficulty="HARD", referrals=["POL-NS-05(ii) false-arrival record"],
    rationale=lambda F,T: (f"At the arrived_at timestamp {T['arr']} EV-GPS-{T['c']:05d} places the vehicle about {T['d_at_arr']} m from the pin travelling at {T['v_at_arr']} km/h: POL-NS-05 fires on the distance limb (over 300 m), and the arrival marker is FALSE. "
        f"Recomputing the clock under POL-NS-02: the trace never contains three consecutive sub-25 m fixes inside the {T['R']} m LARGE_VENUE radius - the nearest fix is {T['d_min']} m - because the car circled a block north of the pin for nine minutes. POL-NS-05(ii): fee refunded in full, no driver compensation, and the trip is recorded as a false-arrival event against the driver in the referrals. "
        f"The SYSTEM cancellation also fails POL-NS-01(d). EV-CHAT-{T['c']:05d} corroborates the story but is not needed. FULL_REFUND {T['fee']}."))

# 607 <- EN-NS-07 drives off as rider opens the door; 35 s dwell; DRIVER cancels no-show
claim, cp = st("EN-NS-07")
P = pt("tampines_mall_cp")
add(no=607, seed="EN-NS-07", req=ts(2026,9,7,8,10,0), zone="LARGE_VENUE", tier="RYDE_X", pick="tampines_mall_cp", drop="changi_t3", rider="RDR-30607", driver="DRV-30751", region="East (Tampines)",
    legs=approach("tampines_hub", P, 11) + [("dwell", off(P,8,6), 35), ("drive", [off(P,8,6), off(P,300,400), off(P,600,900)], 2)],
    arr_s=11*60+12, cancel_s=11*60+10+40, by_cancel="DRIVER", reason="RIDER_NO_SHOW",
    calls=[("DRIVER",3*60,50,True),("DRIVER",7*60,30,True)], rider_track=(9,7, 10*60, 11*60+60), msgs=[("DRIVER","car park entrance closed, cancel pls",3*60+60),("RIDER","you cancel, not me",3*60+120)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-06","POL-NS-01","POL-NS-02"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} has a qualifying arrival at {T['q']} inside the {T['R']} m radius, but the vehicle departs after {T['dwellc']} s and EV-TRIP-{T['c']:05d} records RIDER_NO_SHOW at {T['cancel']}: effective dwell {T['dwell']} s from first qualifying fix to cancellation, of which only {T['dwellc']} s were inside the geofence, against {T['min']} s. "
        f"POL-NS-06 refunds the fee in full on that shortfall alone. rider_track places the rider within metres of the car at departure (mean {T['rider_d']} m from the pin), which also makes the no-show reason code untrue, and the two earlier answered calls on EV-TRIP-{T['c']:05d}.in_app_calls change nothing. No driver compensation. FULL_REFUND {T['fee']}."))

# 608 <- EN-NS-08 driver-filed: waited 16 min, rider cancelled, platform already refunded the fee -> NS-01(d) fails -> NO_ACTION (party-relative)
claim, cp = st("EN-NS-08", by="DRIVER")
P = pt("punggol_hdb")
add(no=608, seed="EN-NS-08", req=ts(2026,9,8,7,20,0), by="DRIVER", zone="STANDARD", tier="RYDE_POOL", pick="punggol_hdb", drop="one_north", rider="RDR-30608", driver="DRV-30862", region="North-East (Punggol)",
    legs=approach("sengkang_mrt", P, 6) + [("dwell", off(P,6,5), 16*60)],
    arr_s=6*60+12, cancel_s=6*60+10+16*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND", fee_status="REFUNDED", refunded=4.0, contested=3.20,
    calls=[("RIDER",17*60,70,True)], rider_track=(700,600, 6*60, 22*60), msgs=[("RIDER","ok go",18*60)],
    claim=claim, cp=cp, rule=noact, clauses=["POL-NS-01","POL-NS-07","POL-GEN-03"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"Driver-filed for compensation. EV-GPS-{T['c']:05d} shows a qualifying arrival at {T['q']} and a dwell of {T['dwell']} s, well over the {T['min']} s minimum, and rider_track keeps the rider about {T['rider_d']} m away, so limbs (a)-(c) of POL-NS-01 are satisfied. "
        f"Limb (d) is not: EV-TRIP-{T['c']:05d} shows the trip terminated by the RIDER with RIDER_CHANGED_MIND, not by the driver with RIDER_NO_SHOW, RIDER_UNREACHABLE or EXCESSIVE_WAIT. POL-NS-07 pays compensation only where POL-NS-01 is satisfied in full, so no payment can issue. "
        f"EV-FARE-{T['c']:05d} shows payment_status REFUNDED with refund_issued_sgd 4.00: under POL-GEN-03 NO_ACTION is party-relative and on a driver-filed claim over an already-reversed fee it leaves the rider refunded. NO_ACTION."))

# 609 <- EN-NS-09 XL airport, driver 12 km away, demands cash top-up, rider cancels; fee 8 (XL governs over AIRPORT 6)
claim, cp = st("EN-NS-09")
P = pt("changi_t1_arr")
add(no=609, seed="EN-NS-09", req=ts(2026,9,9,14,0,0), zone="AIRPORT", tier="RYDE_XL", pick="changi_t1_arr", drop="bukit_batok_blk", rider="RDR-30609", driver="DRV-30977", region="East (Changi)",
    legs=[("drive", ["tampines_hub", off(P,-3000,-11500)], 8), ("dwell", off(P,-3000,-11500), 14*60)],
    arr_s=None, cancel_s=8*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND", reg_points=4,
    rider_track=(15,10, 2*60, 8*60), msgs=[("DRIVER","fare is 120 now, cash, or you cancel",3*60),("RIDER","no. cancelling.",7*60)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-02","POL-NS-01"], difficulty="EASY",
    rationale=lambda F,T: (f"fee_schedule resolution: AIRPORT zone 6.00 against RYDE_XL tier 8.00, the greater governs, so the chargeable fee is 8.00 and EV-FARE-{T['c']:05d} cancellation_fee {T['fee']} reconciles (POL-NS-08(d) clean). "
        f"EV-TRIP-{T['c']:05d} has arrived_at null and the rider cancelled at {T['cancel']}; EV-GPS-{T['c']:05d} shows the driver about {T['d_tail']} m from the pin throughout, no qualifying fix within the {T['R']} m airport radius. POL-NS-02: the driver never arrived, POL-NS-01(a)-(b) fail, full refund. "
        f"EV-CHAT-{T['c']:05d} records the driver's cash demand; it is context. No driver compensation. FULL_REFUND {T['fee']}."))

# 610 <- EN-NS-10 'accident, you cancel'
claim, cp = st("EN-NS-10")
P = pt("queenstown_blk")
add(no=610, seed="EN-NS-10", req=ts(2026,9,10,17,45,0), zone="STANDARD", tier="RYDE_X", pick="queenstown_blk", drop="buona_vista", rider="RDR-30610", driver="DRV-31083", region="West (Queenstown)",
    legs=[("drive", ["harbourfront", off(P,-1700,-1700)], 3), ("dwell", off(P,-1700,-1700), 10*60)],
    arr_s=None, cancel_s=9*60, by_cancel="RIDER", reason="OTHER",
    calls=[("DRIVER",4*60,55,True)], rider_track=(10,6, 3*60, 9*60), msgs=[("DRIVER","accident, cannot come, pls cancel from your side",5*60)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-02","POL-NS-01"], difficulty="HARD",
    rationale=lambda F,T: (f"The driver's reason is sympathetic and the tribunal does not need to doubt it: the question is only whether the fee is chargeable. EV-TRIP-{T['c']:05d}: arrived_at null, cancelled_by RIDER at {T['cancel']}, after the driver's message on EV-CHAT-{T['c']:05d} asking her to cancel. "
        f"EV-GPS-{T['c']:05d} shows the driver stationary about {T['d_tail']} m from the pin from 17:49 onwards, no qualifying fix within {T['R']} m at any point. POL-NS-02: the driver never arrived and POL-NS-01(a)-(b) fail, so the fee is refunded in full with no driver compensation. Nothing in the policy penalises the driver for the breakdown. FULL_REFUND {T['fee']}."))

# 611 <- EN-NS-12 approaches, turns away, 'I was offline'
claim, cp = st("EN-NS-12")
P = pt("yishun_blk")
add(no=611, seed="EN-NS-12", req=ts(2026,9,11,12,20,0), zone="STANDARD", tier="RYDE_X", pick="yishun_blk", drop="amk_hub", rider="RDR-30611", driver="DRV-31190", region="North (Yishun)",
    legs=[("drive", ["yishun_mrt", off(P,-900,-800)], 3), ("drive", [off(P,-900,-800), off(P,-2000,-2000)], 3), ("dwell", off(P,-2000,-2000), 9*60)],
    arr_s=None, cancel_s=15*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND",
    calls=[("RIDER",5*60,20,False),("DRIVER",12*60,40,True)], rider_track=(8,5, 3*60, 15*60),
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-02","POL-NS-01"], difficulty="HARD",
    rationale=lambda F,T: (f"Whether the platform kept the driver online is a question this pool cannot answer, and it does not have to. EV-TRIP-{T['c']:05d} has arrived_at null; EV-GPS-{T['c']:05d} shows the vehicle approach to about 1.2 km, turn away, and sit about {T['d_tail']} m from the pin until the rider cancelled at {T['cancel']}. "
        f"No fix is within the {T['R']} m radius (nearest {T['d_min']} m), so POL-NS-02 says the driver never arrived and POL-NS-01(a)-(b) fail: full refund, no compensation. The driver's answered call at 12:32 is context. FULL_REFUND {T['fee']}."))

# 612 <- EN-NS-14 'arrived' 350 m away, long open call, SYSTEM no-show -> NS-05(ii)
claim, cp = st("EN-NS-14")
P = pt("kallang_blk")
add(no=612, seed="EN-NS-14", req=ts(2026,9,12,8,30,0), zone="STANDARD", tier="RYDE_X", pick="kallang_blk", drop="raffles_place", rider="RDR-30612", driver="DRV-31205", region="Central (Kallang)",
    legs=[("drive", ["geylang_blk", off(P,250,250)], 4), ("dwell", off(P,250,250), 16*60)],
    arr_s=4*60+12, cancel_s=4*60+10+15*60, by_cancel="SYSTEM", reason="RIDER_NO_SHOW",
    calls=[("DRIVER",5*60,400,True)], rider_track=(7,5, 4*60, 19*60),
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-05","POL-NS-02","POL-NS-01"], difficulty="HARD", referrals=["POL-NS-05(ii) false-arrival record"],
    rationale=lambda F,T: (f"At arrived_at {T['arr']} EV-GPS-{T['c']:05d} places the driver about {T['d_at_arr']} m from the pin, more than 300 m, so the arrival marker is FALSE under POL-NS-05 and starts no clock. The driver never moves closer (median {T['d_tail']} m over the last minute; nearest fix {T['d_min']} m), "
        f"so there is no qualifying fix anywhere in the trip within the {T['R']} m STANDARD radius: POL-NS-05(ii) refunds the fee in full, pays no compensation and records a false-arrival event in the referrals. The 400 s answered call on EV-TRIP-{T['c']:05d}.in_app_calls shows contact, which defeats POL-NS-04 but does not create an arrival. The SYSTEM termination also fails POL-NS-01(d). FULL_REFUND {T['fee']}."))

# 613 <- EN-NS-15 hides 400 m away 30 min, then arrives, 240 s, cancels
claim, cp = st("EN-NS-15")
P = pt("bedok_blk12")
add(no=613, seed="EN-NS-15", req=ts(2026,9,13,19,0,0), zone="STANDARD", tier="RYDE_X", pick="bedok_blk12", drop="marine_parade", rider="RDR-30613", driver="DRV-31318", region="East (Bedok)",
    legs=[("drive", ["bedok_mall", off(P,300,260)], 2), ("dwell", off(P,300,260), 30*60), ("drive", [off(P,300,260), off(P,8,6)], 1), ("dwell", off(P,8,6), 240)],
    arr_s=33*60+15, cancel_s=33*60+10+240, by_cancel="DRIVER", reason="RIDER_NO_SHOW",
    calls=[("RIDER",5*60,20,False),("RIDER",12*60,20,False),("RIDER",25*60,25,False)], rider_track=(8,6, 2*60, 31*60), msgs=[("RIDER","where are you? I'm at Blk 12 pickup point",8*60,"IN_APP",None)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-06","POL-NS-01","POL-NS-02"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} shows the driver stationary about 400 m from the pin for thirty minutes, then a qualifying arrival at {T['q']} inside the {T['R']} m radius; EV-TRIP-{T['c']:05d} records RIDER_NO_SHOW at {T['cancel']}, a dwell of {T['dwell']} s against the {T['min']} s minimum. "
        f"POL-NS-06: the fee is refunded in full on the shortfall regardless of the rider's presence, and rider_track (which ends at 19:31, when the rider gave up) is not needed. Three unanswered rider calls and an unanswered locating message on EV-CHAT-{T['c']:05d} are consistent. No driver compensation. FULL_REFUND {T['fee']}."))

# 614 <- EN-NS-17 T4 holding car park 850 m, marks arrived, spells out the trick; rider cancels
claim, cp = st("EN-NS-17")
P = pt("changi_t4")
add(no=614, seed="EN-NS-17", req=ts(2026,9,14,16,10,0), zone="AIRPORT", tier="RYDE_X", pick="changi_t4", drop="tampines_hub", rider="RDR-30614", driver="DRV-31422", region="East (Changi)",
    legs=[("drive", ["airport_blvd", "changi_t4_hold"], 3), ("dwell", "changi_t4_hold", 12*60)],
    arr_s=4*60, cancel_s=13*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND", reg_points=2, prof={"d_ns30":2,"d_trips30":95},
    rider_track=(12,9, 3*60, 13*60), msgs=[("RIDER","where are you? I'm at the T4 pickup door",5*60),("DRIVER","not yet",5*60+40),("DRIVER","if wait too long app charge you not me",8*60)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-05","POL-NS-02","POL-NS-01"], difficulty="HARD", referrals=["POL-NS-05(ii) false-arrival record"],
    rationale=lambda F,T: (f"At arrived_at {T['arr']} EV-GPS-{T['c']:05d} places the vehicle about {T['d_at_arr']} m from the pin in the holding car park, more than 300 m, so POL-NS-05 makes the marker FALSE. The trace never enters the {T['R']} m AIRPORT radius (nearest fix {T['d_min']} m), so POL-NS-05(ii) applies: full refund, no compensation, false-arrival record in the referrals. "
        f"The driver's own message on EV-CHAT-{T['c']:05d} that the app would charge the rider is context. EV-DPROF-{T['c']:05d} no_show_terminations_30d 2 of 95 does not trip the POL-NS-07 check, so POL-NS-09(d) is not engaged. FULL_REFUND {T['fee']}."))

# 615 <- EN-NS-21 'not coming, cancel yourself', drives away
claim, cp = st("EN-NS-21")
P = pt("yew_tee_blk")
add(no=615, seed="EN-NS-21", req=ts(2026,9,15,5,50,0), zone="STANDARD", tier="RYDE_PLUS", pick="yew_tee_blk", drop="changi_t3", rider="RDR-30615", driver="DRV-31537", region="West (Choa Chu Kang)",
    legs=[("drive", ["bukit_batok_blk", off(P,-2500,-1500)], 4), ("drive", [off(P,-2500,-1500), off(P,-5000,-3000)], 6), ("dwell", off(P,-5000,-3000), 3*60)],
    arr_s=None, cancel_s=12*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND", prof={"d_ns30":3,"d_trips30":88},
    calls=[("DRIVER",60,30,True)], rider_track=(8,6, 4*60, 12*60), msgs=[("DRIVER","not coming, cancel yourself",10*60)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-02","POL-NS-01"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d}: arrived_at null, cancelled_by RIDER at {T['cancel']} after the driver's message on EV-CHAT-{T['c']:05d}. EV-GPS-{T['c']:05d} shows the vehicle moving away and ending about {T['d_tail']} m from the pin, never within {T['R']} m. "
        f"POL-NS-02: no qualifying fix in the 15 minutes before cancellation, the driver never arrived, POL-NS-01(a)-(b) fail, full refund and no compensation. EV-DPROF-{T['c']:05d} no_show_terminations_30d 3 is below the POL-NS-07 anti-farming threshold, so POL-NS-09(d) does not fire. FULL_REFUND {T['fee']}."))

# 616 <- EN-NS-22 XL at T1, driver at departures 380 m, 8 min, cancels no-show -> NS-05(ii) (over 300 m)
claim, cp = st("EN-NS-22")
P = pt("changi_t1_arr")
add(no=616, seed="EN-NS-22", req=ts(2026,9,16,11,30,0), zone="AIRPORT", tier="RYDE_XL", pick="changi_t1_arr", drop="bt_condo", rider="RDR-30616", driver="DRV-31649", region="East (Changi)",
    legs=[("drive", ["airport_blvd", off(P,260,-280)], 3), ("dwell", off(P,260,-280), 8*60)],
    arr_s=3*60+12, cancel_s=3*60+10+8*60, by_cancel="DRIVER", reason="RIDER_NO_SHOW", reg_points=4,
    rider_track=(10,8, 3*60, 11*60+10), msgs=[("DRIVER","come up to departures",3*60+40),("RIDER","we have 4 suitcases, pin is arrival door 4, please come down",4*60)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-05","POL-NS-02","POL-NS-01"], difficulty="HARD", referrals=["POL-NS-05(ii) false-arrival record"],
    rationale=lambda F,T: (f"fee_schedule: AIRPORT 6.00 against RYDE_XL 8.00, the greater governs, EV-FARE-{T['c']:05d} shows 8.00. At arrived_at {T['arr']} EV-GPS-{T['c']:05d} places the driver about {T['d_at_arr']} m from the arrival-bay pin, more than 300 m, so POL-NS-05 makes the marker FALSE; the driver stays at departures (median {T['d_tail']} m) and never records a fix inside the {T['R']} m radius. "
        f"POL-NS-05(ii): full refund, no compensation, false-arrival record. Had the distance been 300 m or less, POL-NS-03 would have reached the same refund with the rider having named 'arrival door 4' on EV-CHAT-{T['c']:05d}. FULL_REFUND {T['fee']}."))

# 617 <- EN-NS-23 phone-digit argument, 240 s dwell, driver cancels
claim, cp = st("EN-NS-23")
P = pt("punggol_school")
add(no=617, seed="EN-NS-23", req=ts(2026,9,17,7,10,0), zone="STANDARD", tier="RYDE_X", pick="punggol_school", drop="punggol_mrt", rider="RDR-30617", driver="DRV-31751", region="North-East (Punggol)",
    legs=approach("punggol_hdb", P, 5) + [("dwell", off(P,7,5), 240)],
    arr_s=5*60+12, cancel_s=5*60+10+240, by_cancel="DRIVER", reason="RIDER_NO_SHOW",
    rider_track=(6,4, 5*60, 9*60+10),
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-06","POL-NS-01","POL-NS-02"], difficulty="HARD",
    rationale=lambda F,T: (f"The verification argument in both statements is a distraction. EV-GPS-{T['c']:05d}: qualifying arrival at {T['q']} within {T['R']} m; EV-TRIP-{T['c']:05d}: RIDER_NO_SHOW at {T['cancel']}; dwell {T['dwell']} s against the {T['min']} s minimum. POL-NS-06 refunds the fee in full with no driver compensation. "
        f"rider_track (mean {T['rider_d']} m from the pin) shows the rider beside the car, which makes the reason code untrue but is not required for the outcome. FULL_REFUND {T['fee']}."))

# 618 <- EN-NS-24 driver-filed after a COMPLETED airport trip: waited 9 min, no calls -> NO_ACTION
claim, cp = st("EN-NS-24", by="DRIVER")
P = pt("changi_t3")
add(no=618, seed="EN-NS-24", req=ts(2026,9,18,15,0,0), by="DRIVER", zone="AIRPORT", tier="RYDE_X", pick="changi_t3", drop="paya_lebar_sq", rider="RDR-30618", driver="DRV-31866", region="East (Changi)", reg_points=4, airport=6.0,
    legs=[("drive", ["airport_blvd", off(P,9,7)], 3), ("dwell", off(P,9,7), 540), ("drive", [off(P,9,7), (1.3450,103.9750), (1.3300,103.9400), (1.3220,103.9100), "paya_lebar_sq"], 22, 15.8)],
    completed={"board_s": 3*60+10+540}, arr_s=3*60+12, opt_km=15.5, opt_min=20.0, contested=4.80,
    rider_track=(240,80, 3*60, 9*60),
    claim=claim, cp=cp, rule=noact, clauses=["POL-NS-01","POL-NS-07","POL-GEN-03"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"Driver-filed for compensation after a COMPLETED trip. EV-TRIP-{T['c']:05d} has started_at and ended_at populated, cancelled_at null and no cancellation reason; EV-FARE-{T['c']:05d} carries a full metered fare with cancellation_fee 0.00. "
        f"POL-NS-01(d) requires a trip terminated by the driver with a no-show code and no boarding event; here the rider boarded, so the clause fails and POL-NS-07 has no fee to pay 80 percent of. EV-GPS-{T['c']:05d} does show a qualifying arrival at {T['q']} and a wait of about nine minutes, above the 480 s AIRPORT minimum, but waiting that ends in boarding is not a chargeable event in this corpus. "
        f"in_app_calls is empty, which would also have mattered under POL-NS-04 had the rider filed. Under POL-GEN-03 the present state stands. NO_ACTION."))

# 619 <- EN-NS-25 'I'm at your pin' from 290 m; rider named the gate -> NS-03(i)
claim, cp = st("EN-NS-25")
P = pt("bt_condo")
add(no=619, seed="EN-NS-25", req=ts(2026,9,19,6,30,0), zone="LARGE_VENUE", tier="RYDE_X", pick="bt_condo", drop="woodlands_cp", rider="RDR-30619", driver="DRV-31972", region="Central (Bukit Timah)",
    legs=[("drive", ["king_albert_park", off(P,200,210)], 4), ("dwell", off(P,200,210), 7*60)],
    arr_s=4*60+12, cancel_s=4*60+10+7*60, by_cancel="DRIVER", reason="RIDER_NO_SHOW", reg_points=2,
    calls=[("DRIVER",5*60,110,True)], rider_track=(6,4, 4*60, 11*60+10), msgs=[("RIDER","I'm at the front gate, the pin is the guardhouse, I can see the road and you're not here",5*60+30),("DRIVER","I am at your location, walk here",6*60)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-03","POL-NS-02","POL-NS-01"], difficulty="HARD",
    rationale=lambda F,T: (f"At arrived_at {T['arr']} EV-GPS-{T['c']:05d} places the driver about {T['d_at_arr']} m from the guardhouse pin with sub-25 m accuracy: outside the {T['R']} m LARGE_VENUE radius but not more than 300 m, so POL-NS-05 does not apply and POL-NS-03 governs. "
        f"The driver holds that spot for the full seven minutes (median {T['d_tail']} m, under the 400 m ceiling): POL-NS-01(b) fails and the fee is refunded in full. Compensation: the rider named the sub-location ('the guardhouse') on EV-CHAT-{T['c']:05d} and the driver did not move before cancelling, so POL-NS-03(i) applies and no payment issues, notwithstanding registered_pickup_points 2. "
        f"The 'GPS is bad here' explanation is contradicted by the accuracy_m values in the trace. FULL_REFUND {T['fee']}."))

# 620 <- EN-NS-26 'your pin is wrong', 180 m, abuse
claim, cp = st("EN-NS-26")
P = pt("bt_condo")
add(no=620, seed="EN-NS-26", req=ts(2026,9,20,9,15,0), zone="LARGE_VENUE", tier="RYDE_X", pick="bt_condo", drop="one_north", rider="RDR-30620", driver="DRV-32080", region="Central (Bukit Timah)",
    legs=[("drive", ["bt_main_rd", off(P,150,100)], 2), ("dwell", off(P,150,100), 6*60)],
    arr_s=2*60+12, cancel_s=2*60+10+6*60, by_cancel="DRIVER", reason="RIDER_NO_SHOW", reg_points=1,
    calls=[("DRIVER",3*60,65,True)], rider_track=(5,4, 2*60, 8*60+10), msgs=[("DRIVER","walk out lah, your pin wrong",4*60),("RIDER","pin is the guardhouse where every driver stops. please come in",4*60+40)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-03","POL-NS-02","POL-NS-01"], difficulty="EASY",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} places the driver about {T['d_at_arr']} m from the pin at arrived_at and stationary there for six minutes (median {T['d_tail']} m): outside the {T['R']} m radius, within 400 m, so POL-NS-03 applies and POL-NS-01(b) fails - full refund. "
        f"On EV-CHAT-{T['c']:05d} the rider named the guardhouse and the driver did not move, so POL-NS-03(i) allocates the loss to the driver and no compensation issues. The tone of the driver's message is not a ground any clause prices. FULL_REFUND {T['fee']}."))

# 621 <- EN-NS-27 48 m qualifying arrival, 360 s, driver replied, rider present -> policy pays the driver (REVERSAL)
claim, cp = st("EN-NS-27")
P = pt("geylang_hdb")
add(no=621, seed="EN-NS-27", req=ts(2026,9,21,17,30,0), zone="STANDARD", tier="RYDE_X", pick="geylang_hdb", drop="suntec", rider="RDR-30621", driver="DRV-32195", region="East (Geylang)",
    legs=[("drive", ["kallang_blk", off(P,30,30)], 4), ("dwell", off(P,30,30), 360)],
    arr_s=4*60+12, cancel_s=4*60+10+360, by_cancel="DRIVER", reason="RIDER_NO_SHOW", prof={"d_ns30":1,"d_trips30":120},
    rider_track=(5,4, 4*60, 10*60+10), msgs=[("RIDER","please drive to the shelter, it's pouring",5*60),("DRIVER","you walk",5*60+40),("RIDER","50 metres in this rain?",6*60),("DRIVER","you walk",6*60+30)],
    claim=claim, cp=cp, rule=dcomp, clauses=["POL-NS-01","POL-NS-07","POL-NS-02","POL-NS-04"], difficulty="REVERSAL",
    rationale=lambda F,T: (f"This is the rule's edge and the policy decides it for the driver. EV-GPS-{T['c']:05d}: three consecutive sub-25 m fixes about {T['d_at_arr']} m from the pin, inside the {T['R']} m STANDARD radius, so POL-NS-02 deems the driver ARRIVED; first qualifying fix {T['q']}; EV-TRIP-{T['c']:05d} RIDER_NO_SHOW at {T['cancel']}, dwell {T['dwell']} s, over the {T['min']} s minimum. "
        f"POL-NS-01(a)-(d) all hold. POL-NS-03 needs a position outside the radius, which this is not. POL-NS-04 fails at limb (b): the driver replied on EV-CHAT-{T['c']:05d} within 120 s, and the clause says it then does not apply regardless of the content of the reply. POL-NS-06 needs a shortfall and there is none. "
        f"rider_track shows the rider under the shelter {T['rider_d']} m from the pin, but presence alone displaces nothing once the driver arrived, waited and replied. POL-NS-07: EV-DPROF-{T['c']:05d} no_show_terminations_30d 1 of 120, no farming; compensation 80% of {T['fee']} = {T['comp']}. Ruling DRIVER_COMPENSATION {T['comp']} with amount_sgd mirroring it per POL-GEN-03; the fee stands."))

# 622 <- EN-NS-29 driver never approaches, tells rider to cancel; driver no_show_terminations_30d 11/60 trips the anti-farming check -> NS-09(d) ESCALATE
claim, cp = st("EN-NS-29")
P = pt("hougang_blk")
add(no=622, seed="EN-NS-29", req=ts(2026,9,22,20,0,0), zone="STANDARD", tier="RYDE_X", pick="hougang_blk", drop="sengkang_mrt", rider="RDR-30622", driver="DRV-32206", region="North-East (Hougang)",
    legs=[("drive", ["serangoon_blk", off(P,-1400,-1400)], 2), ("dwell", off(P,-1400,-1400), 18*60)],
    arr_s=None, cancel_s=18*60, by_cancel="RIDER", reason="RIDER_CHANGED_MIND", prof={"d_ns30":11,"d_trips30":60,"d_ns":25},
    calls=[("RIDER",9*60,25,True)], rider_track=(8,6, 2*60, 18*60), msgs=[("DRIVER","cancel lah, I busy",10*60)],
    claim=claim, cp=cp, rule=esc, clauses=["POL-NS-09","POL-NS-07","POL-NS-02"], difficulty="INDETERMINATE",
    rationale=lambda F,T: (f"On the trip facts the rider is plainly right: EV-TRIP-{T['c']:05d} arrived_at null, EV-GPS-{T['c']:05d} stationary about {T['d_tail']} m away throughout, POL-NS-02 would refund in full. But POL-NS-09(d) escalates whenever the POL-NS-07 anti-farming check trips, and EV-DPROF-{T['c']:05d} shows no_show_terminations_30d 11 with completed_trips_30d 60: 11 >= 4 and 11/60 = 0.18 > 0.08, both limbs. "
        f"That trigger is not conditional on the driver winning the fee; it is a pattern flag on either side and the clause says the case is escalated where ANY trigger holds. The lifetime prior_no_show_flags 25 is not the field read (POL-GEN-01). ESCALATE: no monetary ruling, the fee is held, and the packet must state that POL-NS-02 would refund the rider on this record so the reviewer can act on the pattern."))

# 623 <- EN-NS-30 'thank-you fee', driver cancels no-show from 1.4 km
claim, cp = st("EN-NS-30")
P = pt("bedok_int")
add(no=623, seed="EN-NS-30", req=ts(2026,9,23,6,20,0), zone="TRANSPORT_HUB", tier="RYDE_X", pick="bedok_int", drop="changi_t2", rider="RDR-30623", driver="DRV-32317", region="East (Bedok)",
    legs=[("drive", ["marine_parade", off(P,-1000,-1000)], 3), ("dwell", off(P,-1000,-1000), 9*60)],
    arr_s=None, cancel_s=11*60, by_cancel="DRIVER", reason="RIDER_NO_SHOW",
    rider_track=(12,8, 3*60, 11*60), msgs=[("RIDER","I'm at the private-hire bay, where are you?",4*60,"IN_APP",None),("RIDER","hello?",6*60,"IN_APP",None),("RIDER","are you coming",8*60,"IN_APP",None),("DRIVER","can add $10 thank you fee?",9*60),("RIDER","no",9*60+30)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-02","POL-NS-01","POL-NS-04"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d} records the driver terminating with RIDER_NO_SHOW but arrived_at is null: POL-NS-01(a) fails on the record itself. EV-GPS-{T['c']:05d} shows the vehicle about {T['d_tail']} m from the interchange bay for the whole window, no fix within the {T['R']} m TRANSPORT_HUB radius, so POL-NS-02 says the driver never arrived and the fee is refunded in full. "
        f"POL-NS-04 holds independently: three locating messages from the rider on EV-CHAT-{T['c']:05d}, the driver's first reply five minutes later and no in-app call, rider_track within the 200 m presence radius (mean {T['rider_d']} m). No driver compensation. FULL_REFUND {T['fee']}."))

# 624 <- EN-DR-03 rider-filed against a fee the driver earned; rider disputes counter below the NS-09(d) line -> DRIVER_COMPENSATION
claim, cp = st("EN-DR-03")
P = pt("hougang_blk")
add(no=624, seed="EN-DR-03", req=ts(2026,9,24,12,40,0), zone="STANDARD", tier="RYDE_X", pick="hougang_blk", drop="amk_hub", rider="RDR-30624", driver="DRV-32428", region="North-East (Hougang)",
    legs=approach("serangoon_blk", P, 5) + [("dwell", off(P,7,5), 360)],
    arr_s=5*60+12, cancel_s=5*60+10+360, by_cancel="DRIVER", reason="RIDER_NO_SHOW", prof={"r_ns30":2,"r_filed":14,"r_upheld":9,"r_ns":6,"d_ns30":1,"d_trips30":118},
    calls=[("DRIVER",6*60,20,False),("DRIVER",9*60,25,False)], rider_track=(500,480, 5*60, 11*60+10),
    claim=claim, cp=cp, rule=dcomp, clauses=["POL-NS-01","POL-NS-07","POL-NS-02","POL-GEN-01"], difficulty="HARD",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d}: qualifying arrival at {T['q']} inside the {T['R']} m radius; EV-TRIP-{T['c']:05d}: RIDER_NO_SHOW at {T['cancel']}, dwell {T['dwell']} s over the {T['min']} s minimum; two unanswered driver-placed calls on in_app_calls; rider_track about {T['rider_d']} m from the pin throughout, so POL-NS-04(c) fails affirmatively. POL-NS-01(a)-(d) hold and nothing in POL-NS-03 to POL-NS-06 displaces them. "
        f"POL-NS-09(d): EV-RPROF-{T['c']:05d} no_show_disputes_30d is 2, below the 'three or more' line; prior_disputes_filed 14 and prior_no_show_flags 6 are lifetime fields that POL-GEN-01 forbids reading for this test. POL-NS-07: EV-DPROF-{T['c']:05d} 1 of 118, no farming; compensation 80% of {T['fee']} = {T['comp']}. "
        f"Ruling DRIVER_COMPENSATION {T['comp']}, amount_sgd mirroring it per POL-GEN-03; the rider's claim is not supported and the fee stands."))

# 625 <- EN-SC-02 rider inside a moving car, driver never confirms boarding, SYSTEM no-show, cash ERP demand -> NS-05(ii)
claim, cp = st("EN-SC-02")
P = pt("clementi_blk")
add(no=625, seed="EN-SC-02", req=ts(2026,9,25,18,0,0), zone="STANDARD", tier="RYDE_X", pick="clementi_blk", drop="raffles_place", rider="RDR-30625", driver="DRV-32539", region="West (Clementi)",
    legs=[("drive", ["buona_vista", off(P,320,200)], 3), ("drive", [off(P,320,200), off(P,900,1200), off(P,1200,2600), off(P,900,4200)], 6)],
    arr_s=3*60+20, cancel_s=9*60, by_cancel="SYSTEM", reason="RIDER_NO_SHOW",
    rider_track=(320,0, 3*60, 3*60+50), msgs=[("DRIVER","ERP 25 each cash",6*60),("RIDER","what? no. I'm getting out at the petrol station",6*60+40)],
    claim=claim, cp=cp, rule=full, clauses=["POL-NS-05","POL-NS-02","POL-NS-01"], difficulty="HARD", referrals=["POL-NS-05(ii) false-arrival record"],
    rationale=lambda F,T: (f"At arrived_at {T['arr']} EV-GPS-{T['c']:05d} shows the vehicle about {T['d_at_arr']} m from the pin and moving at {T['v_at_arr']} km/h; on the distance limb (over 300 m) POL-NS-05 makes the marker FALSE. The trace then accelerates away and never records three consecutive sub-25 m fixes inside the {T['R']} m radius (nearest {T['d_min']} m), so POL-NS-05(ii): full refund, no compensation, false-arrival record. "
        f"The SYSTEM termination also fails POL-NS-01(d). rider_track is short and ends near the pickup; it is not needed. The cash ERP demand on EV-CHAT-{T['c']:05d} and the second passenger are outside every monetary clause in this corpus and are noted for the reviewer only. FULL_REFUND {T['fee']}."))

# 626 <- variant of EN-NS-12 with the driver trace MISSING -> NS-08(b)/NS-09(e) ESCALATE
claim, cp = st("EN-NS-12")
P = pt("yishun_blk")
add(no=626, seed="EN-NS-12/gps-missing", req=ts(2026,9,26,12,20,0), zone="STANDARD", tier="RYDE_X", pick="yishun_blk", drop="amk_hub", rider="RDR-30626", driver="DRV-32641", region="North (Yishun)",
    legs=[("drive", ["yishun_mrt", off(P,-900,-800)], 3), ("dwell", off(P,-900,-800), 12*60)], gps_missing=True,
    arr_s=6*60, cancel_s=15*60, by_cancel="DRIVER", reason="RIDER_NO_SHOW",
    calls=[("RIDER",5*60,20,False),("DRIVER",12*60,40,True)],
    claim=claim, cp=cp, rule=esc, clauses=["POL-NS-09","POL-NS-08","POL-NS-02"], difficulty="INDETERMINATE",
    rationale=lambda F,T: (f"EV-GPS-{T['c']:05d} is MISSING (weight 0.0, MISSING_ARTIFACT): no driver trace and no rider_track were retained. EV-TRIP-{T['c']:05d} asserts arrived_at {T['arr']} and RIDER_NO_SHOW at {T['cancel']}, a 9-minute wait on paper, and the rider says the driver never came. "
        f"Every clause that could decide the fee - POL-NS-01(b)-(c), POL-NS-02, POL-NS-03, POL-NS-05, POL-NS-06 - reads the gps_trace, and POL-NS-08(b) makes the trip record's arrival unusable as sole evidence where the trace is absent. Under POL-GEN-02 a MISSING artifact can carry no fact, so the deciding fact rests on nothing above the 0.70 floor. "
        f"POL-NS-09(a) and (e) both fire. ESCALATE; the 4.00 fee is held. The reviewer needs the driver's device log or the platform's dispatch position feed."))

# 627 <- variant of EN-NS-06 with the trip record in CROSS_SOURCE_CONFLICT (like sealed 410) -> NS-09(b) ESCALATE
claim, cp = st("EN-NS-06")
P = pt("clarke_quay")
add(no=627, seed="EN-NS-06/conflict", req=ts(2026,9,27,23,10,0), zone="LARGE_VENUE", tier="RYDE_PLUS", pick="clarke_quay", drop="bedok_blk12", rider="RDR-30627", driver="DRV-32752", region="Central (River Valley)",
    legs=[("drive", ["great_world", off(P,700,300)], 4), ("dwell", off(P,700,300), 9*60)],
    arr_s=4*60+30, cancel_s=13*60+30, by_cancel="DRIVER", reason="RIDER_NO_SHOW",
    trip_override={"wait_time_min": 9.0},
    adm={"TRIP": ("IMPAIRED", "Trip record reports a 9-minute in-geofence wait; the driver trace places the vehicle about 750 m from the pin for the same interval.",
                  [{"code":"CROSS_SOURCE_CONFLICT","detail":"trip_record.arrived_at and wait_time_min are contradicted by gps_trace positions over the same interval.","related_evidence_ids":["EV-GPS-00627"]}])},
    calls=[("RIDER",5*60,40,True)], rider_track=(10,8, 4*60, 13*60+30), msgs=[("DRIVER","car problem, you cancel",5*60+50),("RIDER","no, you cancel",6*60)],
    claim=claim, cp=cp, rule=esc, clauses=["POL-NS-09","POL-NS-08","POL-GEN-02"], difficulty="INDETERMINATE",
    rationale=lambda F,T: (f"EV-TRIP-{T['c']:05d} records arrival at {T['arr']} and a nine-minute wait ending in RIDER_NO_SHOW; EV-GPS-{T['c']:05d} places the vehicle about {T['d_tail']} m from the pin, stationary, for the same interval, with no fix inside the {T['R']} m radius. "
        f"The pre-pass has tagged the trip record CROSS_SOURCE_CONFLICT (weight 0.40) against the trace. Two admissible artifacts contradict each other directly on arrival and dwell, which is the example POL-NS-09(b) itself gives, and the trip record cannot be the sole evidence for either side under POL-NS-08. "
        f"POL-GEN-02 caps confidence at the deciding artifact's weight; 0.40 is below the 0.70 floor, so POL-NS-09(a) fires as well. ESCALATE; the 6.00 fee is held. The open question for the reviewer is which record is corrupt."))
