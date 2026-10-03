"""Independent, bounded policy re-derivation from PUBLIC case bytes.

No imports from core, wild, build_v2 or authoring specs. The key is read only
after every outcome has been computed. Scope is the mechanisms exercised by
this set, not a claim of implementing every possible policy fact pattern.
"""
import json, math, pathlib, os, sys
from datetime import datetime
from decimal import Decimal, ROUND_CEILING

ROOT=pathlib.Path(os.environ.get('WILD_ROOT',pathlib.Path(__file__).resolve().parent.parent))
NS=json.loads((ROOT/'policy/no_show.json').read_text())
RD=json.loads((ROOT/'policy/route_deviation.json').read_text())
GEN=json.loads((ROOT/'policy/general.json').read_text())
FLOOR=GEN['confidence_floor']

def at(v): return datetime.fromisoformat(v)
def km(p,q):
    a,b=math.radians(p['lat']),math.radians(q['lat'])
    da=a-b; db=math.radians(p['lng']-q['lng'])
    h=math.sin(da/2)**2+math.cos(a)*math.cos(b)*math.sin(db/2)**2
    return 6371.0088*2*math.atan2(math.sqrt(h),math.sqrt(max(0,1-h)))
def ceil05(x):
    # Small epsilon removes binary float noise, not monetary intermediate rounding.
    return float(((Decimal(str(x))-Decimal('0.000000001'))*20).quantize(Decimal('1'),rounding=ROUND_CEILING)/20)
def output(r='NO_ACTION',a=None,dc=None,refs=None):
    return dict(expected_ruling=r,expected_amount_sgd=a,expected_driver_compensation_sgd=dc,expected_referrals=refs or [])
def refund(value,dispute,refs=None,dc=None):
    payable=ceil05(value)
    if payable<=0: return output(refs=refs)
    if payable>dispute['amount_contested_sgd']+1e-8:
        raise ValueError('Refund exceeds contested scope; independent manual review required')
    return output('FULL_REFUND' if abs(payable-dispute['amount_contested_sgd'])<1e-8 else 'PARTIAL_REFUND',payable,dc,refs)

derived={}; detail={}
for path in sorted((ROOT/'data/wild-v2/cases').glob('case-*.json')):
    c=json.loads(path.read_text()); no=c['case_no']; d=c['dispute']
    e={x['evidence_type']:x for x in c['evidence']}
    t=e['TRIP_RECORD']['payload']; f=e['FARE_BREAKDOWN']['payload']; gps=e['GPS_TRACE']['payload']
    pts=gps['points'] if gps else []
    raw=sum(km(p,q) for p,q in zip(pts,pts[1:]))
    distance=round(raw,2)
    if gps and abs(distance-gps['trace_distance_km'])>.011: raise ValueError('Bad stored polyline length')
    rationale=dict(raw_polyline_km=raw,governing_trace_distance_km=distance)
    if d['category']=='ROUTE_DEVIATION':
        amended=bool(t['pickup_amended_at'] or t['dropoff_amended_at'])
        terminal=t['ended_at'] or t['cancelled_at']
        delta=abs((at(pts[-1]['ts'])-at(terminal)).total_seconds()) if pts else None
        rationale.update(amended=amended,terminal_discrepancy_sec=delta)
        if amended and (t['amended_optimal_distance_km'] is None or t['amended_optimal_duration_min'] is None):
            o=output('ESCALATE'); rationale['trigger']='POL-RD-05 / POL-RD-10(5): missing stored amended baseline'
        elif delta is not None and delta>600:
            o=output('ESCALATE'); rationale['trigger']='POL-RD-10(4): endpoint timestamps differ by more than ten minutes'
        else:
            opt=t['amended_optimal_distance_km'] if amended else t['optimal_distance_km']
            mins=t['amended_optimal_duration_min'] if amended else t['optimal_duration_min']
            excess=distance-opt
            deviation=excess>.2*opt and excess>.8
            material=excess>.5*opt or excess>8
            matched=[]; phantom=[]; distances={}
            for line in f['erp_gantries']:
                nearest=min(km(p,line)*1000 for p in pts) if line.get('lat') is not None and line.get('lng') is not None and pts else None
                distances[line['gantry_name']]=nearest
                (phantom if nearest is not None and nearest>250 else matched).append(line)
            refs=[]
            if phantom:
                names='; '.join(f"{p['gantry_name']} (SGD {p['amount_sgd']:.2f})" for p in phantom)
                refs.append('POL-RD-09(4) billing-integrity review: '+names+' never passed')
            rationale.update(optimal_km=opt,excess_km=excess,deviation_established=deviation,material=material,gantry_nearest_fix_m=distances)
            prof=e['DRIVER_PROFILE']['payload']
            pattern=prof['deviation_flags_90d']>=3 or (prof['completed_trips_90d']>=40 and prof['deviation_flags_90d']/prof['completed_trips_90d']>=.05)
            if material and pattern:
                raise ValueError('Repeat-pattern uplift needs separate independent review; not exercised by this set')
            if f['fare_model']=='UPFRONT_QUOTE':
                proper=sum(p['amount_sgd'] for p in matched)+f['airport_surcharge']+f['waiting_time_fee']
                value=max(0,f['total_charged']-f['quoted_fare_sgd']-proper)
                rationale.update(quoted_fare=f['quoted_fare_sgd'],proper_pass_through=proper,unrounded_refund=value)
                o=refund(value,d,refs)
            else:
                model=RD['fare_model']
                onroute=sum(p['amount_sgd'] for p in matched if p['on_optimal_route'])
                rec=(model['base_fare']+model['per_km']*opt+model['per_min']*mins)*f['surge_multiplier']+model['platform_fee']+onroute+f['airport_surcharge']+f['waiting_time_fee']-f['promo_discount']
                value=max(0,f['total_charged']-rec)
                rationale.update(charged_total=f['total_charged'],recomputed_fare_unrounded=rec,unrounded_refund=value)
                if deviation:
                    o=output(refs=refs) if ceil05(value)<model['de_minimis_refund'] else refund(value,d,refs)
                else:
                    o=refund(sum(p['amount_sgd'] for p in phantom),d,refs)
            if d['filed_by']=='DRIVER' and o['expected_ruling']=='NO_ACTION':
                rationale['payment_state']='Unchanged, not released or reinstated: '+f['payment_status']
    else:
        schedule=NS['fee_schedule']; fee=f['cancellation_fee']; zone=t['pickup_zone_class']
        if e['FARE_BREAKDOWN']['admissibility']['weight_multiplier']<FLOOR:
            o=output('ESCALATE'); rationale['trigger']='POL-GEN-02 / POL-NS-09(a): sole canonical charge/fee representation below confidence floor'
        elif t['status']=='COMPLETED':
            assert fee==0
            o=output(); rationale['trigger']='Completed service-charge/waiting dispute is not a cancellation-fee remedy; POL-GEN-03 leaves present state unchanged'
        else:
            pick=t['pickup']; radius=schedule['arrival_radius_m'][zone]; minimum=schedule['minimum_dwell_sec'][zone]
            cancel=at(t['cancelled_at'])
            good=lambda p: p['accuracy_m']<=schedule['gps_accuracy_filter_m']
            q=next((i for i in range(len(pts)-2) if all(good(p) and km(p,pick)*1000<=radius for p in pts[i:i+3])),None)
            dwell=0
            if q is not None:
                leave=next((p for p in pts[q+1:] if km(p,pick)*1000>radius),None)
                dwell=((at(leave['ts']) if leave else cancel)-at(pts[q]['ts'])).total_seconds()
            distances=[km(p,pick)*1000 for p in pts if good(p)]
            stationary=bool(pts) and all(p['speed_kph']<1 for p in pts)
            stationary_seconds=(cancel-at(pts[0]['ts'])).total_seconds() if stationary else 0
            rationale.update(qualifying_start_index=q,continuous_dwell_sec=dwell,minimum_sec=minimum,
                nearest_pin_m=min(distances) if distances else None,furthest_pin_m=max(distances) if distances else None,stationary_sec=stationary_seconds)
            if q is None and stationary and stationary_seconds>=minimum and distances and max(distances)<=schedule['wrong_entrance_ceiling_m']:
                messages=e['CHAT_LOG']['payload']['messages']
                specified=any(any(x in m['text'].lower() for x in ('entrance','block','tower','bay')) for m in messages)
                dc=fee*schedule['pin_ambiguity_goodwill_rate'] if t['registered_pickup_points']>=2 and not specified else None
                o=refund(fee,d,dc=dc); rationale['trigger']='POL-NS-03 wrong entrance; explicit sub-location='+str(specified)
            elif q is None or dwell<minimum:
                o=refund(fee,d); rationale['trigger']='POL-NS-02 no arrival or POL-NS-06 dwell shortfall'
                if q is None and t['arrived_at']:
                    near=min(pts,key=lambda p:abs((at(p['ts'])-at(t['arrived_at'])).total_seconds()))
                    if km(near,pick)*1000>300 or near['speed_kph']>=15:
                        o['expected_referrals']=['POL-NS-05(ii) false-arrival event against driver']
            else:
                raise ValueError('Verified-no-show compensation branch not exercised; independent review required')
    derived[str(no)]=o; detail[str(no)]=rationale

# No author key was loaded during the above derivation.
key=json.loads((ROOT/'eval/wild-v2/ground_truth.json').read_text())
fields=('expected_ruling','expected_amount_sgd','expected_driver_compensation_sgd','expected_referrals')
differences=[]
for no,o in derived.items():
    for field in fields:
        a,b=o[field],key[no][field]
        if isinstance(a,(int,float)) and isinstance(b,(int,float)): ok=abs(a-b)<1e-8
        elif isinstance(a,list) and isinstance(b,list): ok=sorted(a)==sorted(b)
        else: ok=a==b
        if not ok: differences.append(dict(case_no=int(no),field=field,derived=a,author=b))
if set(derived)!=set(key): raise ValueError('Case/key membership differs')
report=dict(method='Independent case-only re-derivation; separate geo, rounding and policy expressions; no source expectations or authoring code imported',
    cases=len(derived),graded_fields_per_case=4,differences=differences,derived=derived,calculations=detail,
    limitations=['This checker covers only the mechanisms exercised here. It is not an exhaustive interpreter of the full natural-language policy.',
                 'Completed-trip NO_ACTION dispositions resolve only the admitted category-specific monetary claim; they are not endorsements of service quality or abandonment.'])
(ROOT/'eval/wild-v2/semantic_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'Independent re-derivation: {len(derived)} cases, {len(derived)*4} fields, {len(differences)} differences.')
if differences: sys.exit(1)
