"""Independent re-derivation of every ruling from the emitted case files (not from the generator's spec)."""
import json, glob, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from core import haversine_km, round_up_05, NS_ARR_R, NS_MIN_DWELL
_here=os.path.dirname(os.path.abspath(__file__))
ROOT=os.environ.get("WILD_ROOT") or (os.path.join(_here,"..","out") if os.path.isdir(os.path.join(_here,"..","out")) else os.path.join(_here,".."))
GT=json.load(open(os.path.join(ROOT,'eval/wild/ground_truth.json')))
def P(s): return datetime.fromisoformat(s)
bad=0
for path in sorted(glob.glob(os.path.join(ROOT,'data/wild/cases/*.json'))):
    d=json.load(open(path)); c=d['case_no']; g=GT[str(c)]; by={e['evidence_type']:e for e in d['evidence']}
    trip=by['TRIP_RECORD']['payload']; gps=by['GPS_TRACE']['payload']; fare=by['FARE_BREAKDOWN']['payload']; disp=d['dispute']
    pts=gps['points'] if gps else []
    if disp['category']=='ROUTE_DEVIATION':
        dist=gps['trace_distance_km']; opt=trip['optimal_distance_km']; ex=dist-opt
        dev = ex>0.2*opt and ex>0.8
        # gantry matching
        onroute=0.0; phantom=0.0; offroute=0.0
        for gy in fare['erp_gantries']:
            near=min(haversine_km((p['lat'],p['lng']),(gy['lat'],gy['lng'])) for p in pts)*1000 if pts else 9e9
            if near>250: phantom+=gy['amount_sgd']
            elif gy['on_optimal_route']: onroute+=gy['amount_sgd']
            else: offroute+=gy['amount_sgd']
        gap=max([x['duration_sec'] for x in gps['gaps']] or [0])
        if fare['fare_model']=='UPFRONT_QUOTE':
            proper=onroute+fare['airport_surcharge']+fare['waiting_time_fee']
            refund=round_up_05(max(0,fare['total_charged']-fare['quoted_fare_sgd']-proper))
            exp=('NO_ACTION',None) if refund<0.5 else (('FULL_REFUND' if abs(refund-disp['amount_contested_sgd'])<1e-9 else 'PARTIAL_REFUND'),refund)
            note=f"UPFRONT q={fare['quoted_fare_sgd']} proper={proper:.2f} phantom={phantom:.2f} refund={refund}"
        else:
            rec=(3.8+0.75*opt+0.28*trip['optimal_duration_min'])*fare['surge_multiplier']+0.8+onroute+fare['airport_surcharge']+fare['waiting_time_fee']-fare['promo_discount']
            refund=round_up_05(max(0,fare['total_charged']-rec))
            if gap>90 and not by['CHAT_LOG']['payload']['messages'] and not fare['erp_gantries']: exp=('ESCALATE',None)
            elif not dev: exp=('NO_ACTION',None)
            elif refund<0.5: exp=('NO_ACTION',None)
            elif refund>=0.9*fare['total_charged']: exp=('FULL_REFUND',fare['total_charged'])
            else: exp=('PARTIAL_REFUND',refund)
            note=f"METERED dev={dev} pct={ex/opt*100:.1f} rec={rec:.3f} refund={refund} gap={gap:.0f} dev90={by['DRIVER_PROFILE']['payload']['deviation_flags_90d']}"
    else:
        zone=trip['pickup_zone_class']; R=NS_ARR_R[zone]; mind=NS_MIN_DWELL[zone]; pick=(trip['pickup']['lat'],trip['pickup']['lng'])
        fee=fare['cancellation_fee']; cancel=P(trip['cancelled_at']) if trip['cancelled_at'] else None
        q=None
        for i in range(len(pts)-2):
            if all(pts[j].get('accuracy_m',99)<=25 and haversine_km((pts[j]['lat'],pts[j]['lng']),pick)*1000<=R for j in (i,i+1,i+2)): q=pts[i]; break
        dw=None
        if q and cancel:
            after=[p for p in pts if P(p['ts'])>P(q['ts'])]
            leave=next((p for p in after if haversine_km((p['lat'],p['lng']),pick)*1000>R),None)
            dw=((P(leave['ts']) if leave else cancel)-P(q['ts'])).total_seconds()
        d_arr=None
        if trip['arrived_at'] and pts:
            near=min(pts,key=lambda p: abs((P(p['ts'])-P(trip['arrived_at'])).total_seconds()))
            d_arr=haversine_km((near['lat'],near['lng']),pick)*1000; v_arr=near['speed_kph']
        dp=by['DRIVER_PROFILE']['payload']; rp=by['RIDER_PROFILE']['payload']
        farming = dp['no_show_terminations_30d']>=4 and dp['no_show_terminations_30d']/dp['completed_trips_30d']>0.08
        if gps is None or 'CROSS_SOURCE_CONFLICT' in by['TRIP_RECORD']['admissibility']['issues'] or farming or rp['no_show_disputes_30d']>=3: exp=('ESCALATE',None)
        elif trip['status']=='COMPLETED': exp=('NO_ACTION',None)
        elif trip['cancelled_by']!='DRIVER' or trip['cancellation_reason_code'] not in ('RIDER_NO_SHOW','RIDER_UNREACHABLE','EXCESSIVE_WAIT'):
            exp=('NO_ACTION',None) if disp['filed_by']=='DRIVER' else ('FULL_REFUND',fee)
        elif trip['arrived_at'] is None or q is None: exp=('FULL_REFUND',fee)
        elif d_arr is not None and (d_arr>300 or v_arr>=15) and dw is not None and dw<mind: exp=('FULL_REFUND',fee)
        elif dw<mind: exp=('FULL_REFUND',fee)
        else: exp=('DRIVER_COMPENSATION',round(fee*0.8,2))
        note=f"NS zone={zone} q={'yes' if q else 'no'} dwell={dw} d_arr={None if d_arr is None else round(d_arr)} by={trip['cancelled_by']}/{trip['cancellation_reason_code']} farming={farming}"
    got=(g['expected_ruling'],g['expected_amount_sgd'])
    ok = got[0]==exp[0] and (exp[1] is None or abs((got[1] or 0)-exp[1])<0.011)
    if not ok: bad+=1
    print(('OK  ' if ok else 'DIFF'), c, got, 'derived', exp, '|', note)
print('mismatches:',bad)
