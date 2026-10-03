"""Private authoring tool. NEVER expose gen/ or eval/ to Tribunal agents.

Only unused source records are selected; no wild-v1 case, answer or run is read.
Expected outcomes below are the author's policy adjudication. semcheck.py does
not import this module, specs, author answers, or source-seed expectations.
"""
import json, zipfile, pathlib, copy
from datetime import timedelta
from wild import *

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARCHIVE = pathlib.Path('/Users/hanweizhou/Desktop/tribunal-wild-v1(1).zip')
source=ROOT/'eval/wild-v2/source-unused-seeds.jsonl'
if source.exists():
    unused={s['id']:s for s in (json.loads(l) for l in source.read_text().splitlines() if l.strip())}
else:
    with zipfile.ZipFile(ARCHIVE) as z:
        map_bytes=z.read('eval/wild/seed_map.json')
        used = {v.split('/')[0] for v in json.loads(map_bytes).values()}
        unused = {s['id']: s for s in (json.loads(l) for l in z.read('en/cases.jsonl').decode().splitlines() if l.strip()) if s['id'] not in used}
    source.parent.mkdir(parents=True,exist_ok=True)
    source.write_text(''.join(json.dumps(unused[k],ensure_ascii=False)+'\n' for k in sorted(unused)))
    (source.parent/'seed_selection.json').write_text(dumps({'total_seeds':84,'used_unique_seeds':62,
        'unused_seed_ids':sorted(unused),'used_seed_ids':sorted(used),'source_seed_map_sha256':sha(map_bytes),
        'method':'Subtract unique base seed IDs named by wild-v1 seed_map from en/cases.jsonl. No case shards, wild-v1 grading keys or run notes were read.'}))
assert len(unused) == 22

# Distinct synthetic Singapore pickup corridors. Coordinates, not external
# map knowledge, are the evidence. This is not a real-road navigation dataset.
A=(1.3190,103.7550,'West Grove pickup')
B=(1.3240,103.8000,'Canal View destination')
C=(1.3280,103.8475,'Central Gardens destination')
D=(1.3340,103.9000,'East Vale destination')
E=(1.3440,103.9300,'Airport-bound destination')
M=(1.3750,103.8700)

def base(no, seed, diff, claim, cp):
    assert seed in unused
    return dict(no=no,seed=seed,rider=f'RDR-{no:05d}',driver=f'DRV-{no:05d}',
        req=ts(2026,9,22+(no-701)//5,7+(no%10),12),difficulty=diff,claim=claim,cp=cp,
        clauses=['POL-GEN-03'],rationale=lambda f,n: 'placeholder ' * 15,
        rule=lambda f: ('NO_ACTION',None,None))

def rd(no,seed,diff,claim,cp,dist=11.0,opt=10.8,mins=19,optmin=18,quote=22.4,pick=A,drop=C):
    s=base(no,seed,diff,claim,cp)
    s.update(pickup=pick,dropoff=drop,opt_km=opt,opt_min=optmin,
        legs=[('drive',[pick,M,drop],mins,dist)],quote=quote)
    return s

def ns(no,seed,diff,claim,cp,pick=A,drop=B,completed=True,quote=16.0,prewait=60,dist=5.5,mins=13):
    s=base(no,seed,diff,claim,cp)
    s.update(pick=pick,drop=drop,zone='STANDARD',tier='RYDE_X',arr_s=0,acc_range=(5.0,12.0),
        legs=[('dwell',pick,prewait),('drive',[pick,(1.3400,103.7800),drop],mins,dist)],
        opt_km=max(dist,6.0),opt_min=14,completed={'board_s':prewait} if completed else None)
    s['_quote']=quote
    return s

S=[]
S.append(rd(701,'EN-RD-06','HARD',
    'I paid the app fare and also say I handed over SGD 40 cash to avoid sharing. The driver still stopped for another passenger. Refund my entire platform fare; the cash allegation is additional context.',
    'She agreed to share. I deny coercion. The app fare was the booked upfront quote.',dist=26.8,opt=20.7,mins=41,optmin=31,quote=27.4,drop=E))
S[-1]['msgs']=[('RIDER','I paid you 40 cash and you said no detour; why are we collecting someone?',840)]
Q=(1.3400,103.8500)
S[-1]['legs']=[('drive',[A,(1.3700,103.8000),Q],18,13.4),('dwell',Q,240),('drive',[Q,(1.3700,103.9000),E],19,13.4)]
S.append(rd(702,'EN-RD-18','HARD',
    'The driver told me moving the destination pin to the next block would not change the price. The app re-quoted from SGD 13.80 to SGD 22.40. Refund the difference in the platform fare.',
    'The rider edited the destination herself. I followed the amended route; the platform issued the new quote.',dist=11,opt=11,optmin=19,mins=19,quote=22.4))
S[-1].update(amend={'at_s':540,'orig':(C[0],C[1]-0.00072,'Original back-gate pin'),'km':11.0,'min':19.0},contested=8.6,
    msgs=[('DRIVER','Just move the pin to Block B, same price.',490),('RIDER','I changed it and the app now says 22.40, not 13.80.',545)])
S.append(ns(703,'EN-NS-11','EASY',
    'This was a scheduled pickup at 05:30. I cancelled when the driver was still far away. Refund the SGD 6 platform cancellation fee.',
    'I overslept and had not reached the pickup when she cancelled.',completed=False))
S[-1].update(tier='RYDE_PLUS',arr_s=None,by_cancel='RIDER',cancel_s=240,fee=6,contested=6,
    req=ts(2026,9,23,5,29,20),legs=[('drive',[(1.4150,103.9000),(1.4140,103.8990)],4)],
    notes={'TRIP':'Scheduled pickup was 05:30 according to the booking statement; scheduling is not an extra schema field.'})
S.append(ns(704,'EN-NS-18','HARD',
    'I walked to the car in the rain. Later the driver made me leave before my intended destination because of flooding, but charged the whole SGD 14.20 platform fare. I selected no-show because the app offered no better category.',
    'The road ahead was flooded. The rider got out and I ended the trip; there was no cancellation fee.',quote=14.2,dist=5.8))
S[-1]['msgs']=[('RIDER','Why are you making me get out before the destination?',700),('DRIVER','Water too deep; I will end here.',730)]
S[-1]['legs']=[('dwell',off(A,0,300),60),('drive',[off(A,0,300),(1.3400,103.7800),B],13,5.8)]
S[-1]['_flood']=True
S.append(ns(705,'EN-NS-19','REVERSAL',
    'We stopped at my waypoint. The driver demanded cash to wait and I left. The app nevertheless charged SGD 9.40; refund that platform fare. No separate cash waiting payment was made.',
    'She left at the waypoint. The platform calculated the fare; I did not collect a cancellation fee.',quote=9.4,prewait=60,dist=3.4,mins=11))
S[-1].update(drop=(1.3260,103.7700,'Registered home waypoint'),opt_km=4.0,opt_min=12,
    legs=[('dwell',A,60),('drive',[A,(1.3300,103.7620),(1.3260,103.7700)],7,2.2),('dwell',(1.3260,103.7700),300)])
S.append(ns(706,'EN-NS-20','HARD',
    'The pool driver kept the doors locked until another booking joined. I refused to wait longer, cancelled myself and was charged SGD 4. Refund that fee.',
    'The base fare was low. I asked her to wait for another match; she cancelled.',completed=False))
S[-1].update(tier='RYDE_POOL',legs=[('dwell',A,250)],cancel_s=250,by_cancel='RIDER',fee=4,contested=4,
    rider_track=(0,10,10,250),msgs=[('DRIVER','Wait for a match; the base fare is too low.',40),('RIDER','I stopped matching. Please unlock and go.',80)])
S.append(ns(707,'EN-NS-28','EASY',
    'The trip completed, but the car smelled and the driver did not help with my suitcase. Refund the SGD 15.60 platform fare through the no-show complaint channel.',
    'I arrived one minute before her. The ride completed normally; no cancellation fee was charged.',quote=15.6))
S.append(ns(708,'EN-NS-31','INDETERMINATE',
    'My parents never boarded, yet the app marked the ride completed and took SGD 26. Refund this platform charge. I only have a manually transcribed payment screen, not a verified ledger export.',
    'The passengers were confused and walked away. I dispute whether this payment screen is the final ledger.',quote=26,prewait=240,dist=1.2,mins=4,drop=(1.3290,103.7550,'Short departure endpoint')))
S[-1]['msgs']=[('RIDER','My parents are still at the pickup. Did anyone board?',250)]
S[-1]['_unverified_fare']=True
S.append(rd(709,'EN-BL-03','HARD',
    'The rider amended the destination after I crossed the SGD 3 gantry. The platform left the payment pending. Release that SGD 3 to me; the fare correctly bills all driven distance.',
    'I changed my destination after the gantry. I dispute who should absorb the ERP.',dist=11,opt=11.2,mins=20,optmin=20,quote=23))
S[-1].update(by='DRIVER',contested=3,gantries=[{'name':'Canal Corridor entry','frac':0.3,'amount':3,'on_opt':True}],
    amend={'at_s':540,'orig':(1.3350,103.8500,'Earlier destination pin'),'km':11.2,'min':20.0},fare_override={'payment_status':'PENDING'},
    msgs=[('RIDER','I changed the destination in the app.',540),('DRIVER','We passed the ERP entry before you changed it.',550)])
S.append(rd(710,'EN-BL-04','HARD',
    'Our pool booking said ERP shared, but SGD 6 was assigned to me. Another rider was aboard. Refund part of this SGD 6 platform ERP line.',
    'I allocated the ERP to this booking. The gantry was crossed on the matched itinerary.',dist=12,opt=12.2,mins=24,optmin=24,quote=25))
S[-1].update(tier='RYDE_POOL',solo_km=8.5,contested=6,src='routing-engine-v3.2; platform matched pooled itinerary',
    gantries=[{'name':'Matched itinerary gantry','frac':0.5,'amount':6,'on_opt':True}],
    msgs=[('RIDER','Booking says ERP shared. Why all six dollars on mine?',600),('DRIVER','Pay the full ERP on this booking.',625)])
S.append(rd(711,'EN-BL-15','INDETERMINATE',
    'The car broke down. I say I transferred SGD 500 privately to be allowed to leave and was later asked for SGD 1,800. The app also charged SGD 14.90. My formal dispute contests only that platform fare, not SGD 500.',
    'There was a breakdown and the endpoint was changed to the stopping place. The private payment was voluntary.',dist=5.5,opt=11,mins=25,optmin=20,quote=14.9,drop=B))
S[-1].update(amend={'at_s':480,'orig':C,'km':None,'min':None},
    legs=[('drive',[A,(1.3350,103.7780),B],3,5.5),('dwell',B,1320)],
    msgs=[('DRIVER','Send 500 first then you go.',500),('RIDER','The app has also charged 14.90. I want that platform fare reviewed.',900),('DRIVER','Repair 1800 you pay.',1300)])
S.append(rd(712,'EN-BL-16','EASY',
    'The solo XL driver talked about pooling and an air-pollution fee. The app actually billed SGD 14 ERP even though the route supports only SGD 6. I dispute the SGD 14 platform ERP charge; no pollution fee was paid.',
    'I mentioned extra costs. The app invoice carries the ERP entries.',dist=12,opt=12.2,mins=24,optmin=24,quote=28))
S[-1].update(tier='RYDE_XL',contested=14,gantries=[
    {'name':'West link entry','frac':0.28,'amount':3,'on_opt':True},
    {'name':'Canal link exit','frac':0.72,'amount':3,'on_opt':True},
    {'name':'North service-loop ERP','at':(1.4500,103.6800),'min':12,'amount':8,'on_opt':True,'phantom':True}],
    msgs=[('DRIVER','ERP fourteen total. Air pollution fee sixty extra.',200),('RIDER','I am only paying the app invoice.',240)])
S.append(rd(713,'EN-SC-01','REVERSAL',
    'I booked a solo ride; the driver collected others and told me to get out before the destination. The app took SGD 18.60. Refund the entire platform fare under route deviation.',
    'She refused to share and got out. The trip ended there with the agreed upfront fare.',dist=6.8,opt=10.8,mins=17,optmin=22,quote=18.6,drop=B))
S[-1]['msgs']=[('RIDER','This is a solo booking.',400),('DRIVER','Then get out; I will end here.',430)]
S[-1]['legs']=[('drive',[A,(1.3270,103.7650),(1.3350,103.7800)],7.5,3.4),('dwell',(1.3350,103.7800),60),
    ('drive',[(1.3350,103.7800),(1.3280,103.7920),B],7.5,3.4),('dwell',B,60)]
S.append(rd(714,'EN-SC-04','INDETERMINATE',
    'The driver demanded SGD 15 for my companion. We left after about 1.2 km, but the ride later completed empty and SGD 16.80 was charged. Refund this platform fare.',
    'They left early. The booking endpoint was changed at that point, but the app continued recording my car.',dist=10.8,opt=10.8,mins=20,optmin=20,quote=16.8))
S[-1].update(amend={'at_s':150,'orig':(1.3280,103.8468,'Original destination gate'),'km':None,'min':None},
    msgs=[('DRIVER','Add fifteen for the second person or get down.',90),('RIDER','We are getting out here. End our booking at this stop.',150)])
S[-1]['_rider_exits']=True
S.append(rd(715,'EN-SC-05','REVERSAL',
    'The driver refused to continue to the hospital and said he would refund me. The app charged SGD 7.20 for the driven portion. Refund that platform charge through route deviation.',
    'The recorded receipt endpoint is the shelter where she got out. The charged portion followed its direct route.',dist=3.4,opt=6.4,mins=9,optmin=16,quote=7.2,drop=(1.3190,103.7800,'Shelter where service ended')))
S[-1]['msgs']=[('DRIVER','Hospital too far in this jam. I will end here and refund you.',420)]
S.append(rd(716,'EN-SC-08','INDETERMINATE',
    'The app snapshot says cancelled, while the payment export shows SGD 21.40. The driver went to the wrong destination and let me out far away. Determine whether this platform charge belongs to the recorded trip.',
    'The trip ended much earlier than the payment screen suggests. The snapshot and trace may be from different lifecycle revisions.',dist=8,opt=11,mins=25,optmin=23,quote=21.4,drop=B))
S[-1]['_stale_terminal']=True
S.append(ns(717,'EN-SG-01','HARD',
    'The driver told me to walk to an alternative address in rain. The completed ride cost SGD 25 plus SGD 3 waiting. Refund only the SGD 3 waiting line using the no-show complaint channel.',
    'The pickup road was no-stopping. She walked over and boarded; there was no cancellation.',quote=25,prewait=420,dist=2.6,mins=9))
S[-1].update(contested=3,legs=[('dwell',off(A,0,300),420),('drive',[off(A,0,300),(1.3300,103.7700),(1.3200,103.7750)],9,2.6)],
    drop=(1.3200,103.7750,'Completed short-trip destination'),
    msgs=[('DRIVER','Meet me at the alternative entrance shown here, not the booked pin.',0)])
S[-1]['_waiting']=3
S[-1]['_rider_walk']=True
S.append(rd(718,'EN-RD-06','EASY',
    'A solo metered trip collected an extra passenger despite my objection. I also allege SGD 40 cash was demanded. Refund the excessive platform distance/time charge, not the alleged cash.',
    'I collected another passenger. The meter copied this GPS trace; I have no traffic advisory or rider instruction excusing that route.',dist=26.8,opt=20.7,mins=41,optmin=31,quote=None,drop=E))
S[-1]['msgs']=[('DRIVER','I took the longer route to collect the other passenger.',850)]
S[-1]['legs']=copy.deepcopy(S[0]['legs'])
S.append(copy.deepcopy(S[1]))
S[-1].update(no=719,rider='RDR-00719',driver='DRV-00719',req=ts(2026,9,27,11,12),difficulty='INDETERMINATE')
S[-1]['amend'].update(km=None,min=None)
S[-1]['claim']='After the induced 80 m pin move the platform charged 22.40 rather than 13.80. I dispute 8.60. The amendment timestamp is retained but the amended route estimate is absent.'
S.append(ns(720,'EN-SG-01','REVERSAL',
    'The driver made me walk toward his alternative entrance. This time I never boarded; he cancelled and the app charged SGD 4. Refund the fee.',
    'I waited at the alternative entrance because of a no-stopping restriction; the rider never reached me.',completed=False))
S[-1].update(legs=[('dwell',off(A,0,290),420)],cancel_s=420,fee=4,contested=4,reg_points=2,
    rider_track=(0,0,10,410),msgs=[('DRIVER','Meet me at the service entrance 290 m east of the pin.',0)])

DROPPED={
 'EN-NS-13':'Zero platform fare/fee and only a request for punishment; adding a charge would remove the central no-money fact.',
 'EN-NS-16':'Original-driver abandoned pickup is reassigned with no fee. The canonical single-trip/driver schema cannot retain both driver histories and a positive contested charge without changing the core.',
 'EN-BL-17':'Separate parking reimbursement/reversal and receipt image are not canonical fare lines or artifact types. Relabelling parking as airport surcharge would falsify the billing evidence.',
 'EN-DR-01':'Separate driver discipline deduction and booked-seat history are not representable canonical monetary/booking fields; replacing them with cancellation fees changes the dispute.',
 'EN-DR-02':'Service-quality deduction and audio recording are not canonical fare lines or artifact types. A positive rider charge would not represent the driver deduction.'}
assert set(s['seed'] for s in S)|set(DROPPED)==set(unused)
assert not set(s['seed'] for s in S)&set(DROPPED)

for folder in ('data/wild-v2/cases','eval/wild-v2'):
    (ROOT/folder).mkdir(parents=True,exist_ok=True)
keys={}; index=[]; provenance={}
for s in S:
    n=s['no']; cf,_,facts=(build_rd(s) if 'pickup' in s else build_ns(s))
    cf['dispute']['channel']='IN_APP_SUPPORT'
    ev={e['evidence_type']:e for e in cf['evidence']}
    t=ev['TRIP_RECORD']['payload']; f=ev['FARE_BREAKDOWN']['payload']; g=ev['GPS_TRACE']['payload']
    if cf['dispute']['category']=='NO_SHOW_CHARGE' and s.get('completed'):
        quote=s['_quote']; f.update(fare_model='UPFRONT_QUOTE',quoted_fare_sgd=quote,
            base_fare=3.8,time_fare=m2(quote*.25),distance_fare=m2(quote-4.6-m2(quote*.25)),
            surge_multiplier=1.0,surge_amount=0.0,total_charged=m2(quote+s.get('_waiting',0)),waiting_time_fee=s.get('_waiting',0))
        cf['dispute']['amount_contested_sgd']=s.get('contested',f['total_charged'])
        # completed-trip traces used for NS tests begin at acceptance, but the
        # canonical coverage window begins at boarding. Keep the trace distance
        # (approach + dwell + journey) and compute coverage on the actual window.
        g['coverage_pct']=100.0
    if s.get('_unverified_fare'):
        ev['FARE_BREAKDOWN']['source']='USER_SUBMITTED'
        assessed=datetime.fromisoformat(ev['FARE_BREAKDOWN']['admissibility']['assessed_at'])
        ev['FARE_BREAKDOWN']['admissibility']=adm('IMPAIRED','Manually transcribed rider payment screen, not verified against the payments ledger.',assessed,
            [{'code':'UNVERIFIED_SOURCE','detail':'No independent platform export corroborates the cancellation-fee or charge fields.'}])
    if s.get('_flood'):
        start=datetime.fromisoformat(t['started_at']); end=datetime.fromisoformat(t['ended_at'])
        pp=[dict(p,ts=datetime.fromisoformat(p['ts'])) for p in g['points']]
        payload=advisory('ADV-20260922-704','Canal-side access road','CLOSURE',start-timedelta(minutes=30),end+timedelta(minutes=30),
            (1.30,103.75,1.36,103.81),'HIGH','Access road closed due to flash flooding.','LTA_DATAMALL',pp,start,end)
        ae=ev['TRAFFIC_ADVISORY']; ae['payload']=payload
        ae['admissibility']=adm('COMPLETE','LTA flood-related road closure snapshot.',datetime.fromisoformat(ae['admissibility']['assessed_at']))
    if s.get('_rider_exits'):
        start=datetime.fromisoformat(t['started_at']); end=datetime.fromisoformat(t['ended_at'])
        p=min(g['points'],key=lambda p:abs((datetime.fromisoformat(p['ts'])-start).total_seconds()-150))
        g['rider_track']=serialize_points(dwell_points((p['lat'],p['lng']),start+timedelta(seconds=150),end,rng=random.Random(n+10000)))
    if s.get('_rider_walk'):
        begin=datetime.fromisoformat(t['accepted_at']); board=datetime.fromisoformat(t['started_at'])
        walk=interp_path([A[:2],off(A,0,300)],begin,begin+timedelta(seconds=300),rng=random.Random(n+10000))
        wait=dwell_points(off(A,0,300),begin+timedelta(seconds=310),board,rng=random.Random(n+11000))
        g['rider_track']=serialize_points(walk+wait)
    if s.get('_stale_terminal'):
        # A stale snapshot records cancellation 16 minutes before the telemetry
        # terminates. The distinct revisions are explicit, never silently fused.
        oldend=datetime.fromisoformat(t['ended_at'])-timedelta(minutes=16)
        t.update(ended_at=None,cancelled_at=fmt(oldend),status='CANCELLED_BY_DRIVER',cancelled_by='DRIVER',
            cancellation_reason_code='DRIVER_UNABLE_TO_LOCATE',actual_duration_min=9.0)
        anchor=datetime.fromisoformat(t['started_at']); g['coverage_pct']=100.0
        assessed=datetime.fromisoformat(ev['TRIP_RECORD']['admissibility']['assessed_at'])
        ev['TRIP_RECORD']['admissibility']=adm('IMPAIRED','Stale lifecycle snapshot; terminal timestamp conflicts with driver telemetry by 16 minutes.',assessed,
            [{'code':'STALE_SNAPSHOT','detail':'Record exported from an older trip lifecycle revision.'},
             {'code':'CROSS_SOURCE_CONFLICT','detail':'Recorded cancellation precedes the GPS terminal fix by 16 minutes.', 'related_evidence_ids':[evid(n,'GPS')]}])
        ev['GPS_TRACE']['admissibility']=adm('IMPAIRED','Telemetry runs after the stale trip snapshot cancellation; disputed lifecycle revision.',assessed,
            [{'code':'TIMESTAMP_OUT_OF_RANGE','detail':'Fixes extend 16 minutes beyond the trip snapshot terminal event.'},
             {'code':'CROSS_SOURCE_CONFLICT','detail':'Last fix conflicts with recorded trip termination.', 'related_evidence_ids':[evid(n,'TRIP')]}])
    amount=None; comp=None; referrals=[]; ruling='NO_ACTION'; clauses=['POL-GEN-03']
    explanation=''
    if n in (711,714,719):
        ruling='ESCALATE'; clauses+=['POL-RD-05','POL-RD-10']
        explanation=f"EV-TRIP-{n:05d} retains a dropoff amendment but amended_optimal_distance_km and duration are null. POL-RD-05 cannot be run; POL-RD-10(5) makes escalation terminal. The reviewer must obtain the stored amended route/requote, not invent it from text or GPS. No automatic refund or driver payment issues and no conduct/billing referral is licensed merely by these allegations."
    elif n==716:
        ruling='ESCALATE'; clauses+=['POL-GEN-02','POL-RD-10']
        explanation=f"EV-TRIP-{n:05d} is impaired with STALE_SNAPSHOT and CROSS_SOURCE_CONFLICT at weight 0.30. EV-GPS-{n:05d} is impaired with TIMESTAMP_OUT_OF_RANGE and CROSS_SOURCE_CONFLICT at weight 0.25. Cancellation is 16 minutes earlier than its final fix; POL-RD-10(4) independently mandates terminal escalation and POL-GEN-02 forbids treating either discounted revision as decisive proof for a monetary award. The discrepancy is not resolved by the positive charge in EV-FARE-{n:05d}. Obtain aligned trip, GPS and payment revisions; hold the disputed amount."
    elif n==708:
        ruling='ESCALATE'; clauses+=['POL-GEN-02','POL-NS-09']
        explanation=f"EV-FARE-{n:05d} is USER_SUBMITTED, impaired by UNVERIFIED_SOURCE at 0.60. It alone supplies the disputed SGD 26 charge and zero cancellation-fee line; the trip and chat are not independent payment records. Under POL-GEN-02 the deciding monetary fact caps confidence at 0.60, below 0.70, so POL-NS-09(a) requires terminal escalation. Obtain the canonical payment ledger before determining the fee or service-charge disposition; no refund/payment or additional referral is issued."
    elif n==703:
        ruling='FULL_REFUND'; amount=6.0; clauses+=['POL-NS-01','POL-NS-02']
        explanation=f"EV-TRIP-{n:05d} has no arrival marker or boarding and the rider cancelled. EV-GPS-{n:05d} provides no three consecutive qualifying fixes within the 50 m STANDARD radius, and every fix is well beyond 400 m. POL-NS-02 therefore refunds the full SGD 6 cancellation line in EV-FARE-{n:05d}; no driver compensation is due. Scheduling is context, not a new late-pickup rule. No false-arrival referral is due because no arrival was marked."
    elif n==706:
        ruling='FULL_REFUND'; amount=4.0; clauses+=['POL-NS-01','POL-NS-02','POL-NS-06']
        explanation=f"EV-GPS-{n:05d} begins qualifying dwell 10 seconds after acceptance and ends at 250 seconds, yielding 240 seconds, below STANDARD's 300 seconds. POL-NS-06 refunds the full SGD 4 cancellation fee from EV-FARE-{n:05d}, regardless of presence or the fact that the rider cancelled. POL-NS-07 is not a refusal-of-service clause and does not supply this remedy. No driver payment or generic conduct referral is licensed here."
    elif n==720:
        ruling='FULL_REFUND'; amount=4.0; clauses+=['POL-NS-02','POL-NS-03']
        explanation=f"EV-GPS-{n:05d} shows stationary waiting outside the 50 m radius but within 400 m for over 300 seconds. POL-NS-03 refunds the SGD 4 line in EV-FARE-{n:05d}. EV-CHAT-{n:05d} has the driver's explicit service-entrance instruction, so neither-party-specified-sub-location is false even though registered_pickup_points is 2: the 50% goodwill limb does not apply. No driver payment or false-arrival referral is owed. The absent advisory is not deciding evidence for this stationary wrong-entrance ruling."
    elif n==712:
        ruling='PARTIAL_REFUND'; amount=8.0; clauses+=['POL-RD-01','POL-RD-09','POL-RD-11']
        referrals=['POL-RD-09(4) billing-integrity review: North service-loop ERP (SGD 8.00) never passed']
        near=min(haversine_km((p['lat'],p['lng']),(1.45,103.68))*1000 for p in g['points'])
        explanation=f"EV-GPS-{n:05d} has trace distance {g['trace_distance_km']:.2f} km below the 12.2 km optimal: no route deviation. The two SGD 3 gantries match actual fixes; the North service-loop ERP line in EV-FARE-{n:05d} is {near:.1f} m from the nearest fix, beyond 250 m despite on_optimal_route=true. POL-RD-09(4) independently returns SGD 8.00 of contested SGD 14.00 and requires the named billing-integrity referral. POL-RD-11 does not refund the quoted distance/time fare. No unpaid off-platform demand is added."
    elif n==718:
        ruling='PARTIAL_REFUND'; clauses+=['POL-RD-01','POL-RD-02','POL-RD-08']
        rec=(3.8+.75*20.7+.28*31)*f['surge_multiplier']+.8
        amount=round_up_05(f['total_charged']-rec)
        explanation=f"EV-GPS-{n:05d} records {g['trace_distance_km']:.2f} km against EV-TRIP-{n:05d}'s 20.7 km optimal: excess {g['trace_distance_km']-20.7:.2f} km exceeds both 20% and 0.8 km, but is not MATERIAL. EV-CHAT-{n:05d} admits the unauthorized collection; no exonerating clause applies. POL-RD-02: charged_total={f['total_charged']:.2f}; recomputed_fare=(3.80+0.75*20.7+0.28*31)*1+0.80={rec:.3f}; final refund=ceil05({f['total_charged']-rec:.3f})={amount:.2f}. No intermediate recomputation rounding, cash repayment, compensation or referral applies."
    elif n in (701,702,709,710,713,715):
        clauses+=['POL-RD-01','POL-RD-11']
        if n in (702,709): clauses+=['POL-RD-05']
        if n==710: clauses+=['POL-RD-09','POL-RD-12']
        explanation=f"EV-FARE-{n:05d} is UPFRONT_QUOTE; charged {f['total_charged']:.2f} equals quote {f['quoted_fare_sgd']:.2f} plus properly crossed ERP {f['tolls_erp']:.2f}. POL-RD-11 supplies no distance/time refund and POL-GEN-03 leaves the present payment state ({f['payment_status']}) unchanged. EV-GPS-{n:05d} has {g['trace_distance_km']:.2f} km; the booked/stored amended baseline is {t['optimal_distance_km']:.2f} km. All ERP coordinates match within 250 m, and no material residual deviation or qualifying repeat-driver pattern licenses POL-RD-06(c)."
        if n==709: explanation+=' POL-RD-04 has no distance shortfall over 1 km and POL-RD-09 is not a licence to release ERP as driver compensation; pending is not restored/paid by NO_ACTION.'
        if n==710: explanation+=' The matched itinerary, not solo optimal 8.5 km, governs. POL-RD-12 contains no split-per-rider ERP formula; inventing a half-share or penalty is forbidden.'
        if n in (713,715): explanation+=' This resolves only the format-supported route/fare claim, not whether partial service or abandonment deserves a separate remedy; no policy prices such damages.'
        if n==702: explanation+=' The amendment has both stored estimates; the earlier quote is not the governing final quoted_fare_sgd, and no unsupported conduct or repricing-review referral is invented.'
    else:
        clauses+=['POL-NS-01']
        explanation=f"EV-TRIP-{n:05d} records a completed trip with boarding; EV-FARE-{n:05d} records cancellation_fee=0 and a verified platform fare. POL-NS-01 concerns unboarded driver-terminated pickup attempts, not a completed-trip refund. The claimant's cancellation-fee remedy is unsupported, so POL-GEN-03 leaves the payment state unchanged with no refund or driver payment. No frozen clause licenses a generic service-conduct referral, pro-rata partial-service refund, or refund of a waiting_time_fee through the no-show fee schedule."
    assert len(explanation)<=2500
    keys[str(n)]=gt(ruling,amount,list(dict.fromkeys(clauses)),s['difficulty'],explanation,comp,referrals)
    file=f'cases/case-{n:05d}.json'
    (ROOT/'data/wild-v2'/file).write_text(dumps(cf))
    index.append(dict(case_no=n,dispute_id=cf['dispute']['dispute_id'],trip_id=cf['dispute']['trip_id'],category=cf['dispute']['category'],file=file))
    provenance[str(n)]={'seed_id':s['seed'],'source_seed':unused[s['seed']]['seed'],'variant':n>=718,
        'seed_suggestion':unused[s['seed']]['expected_ruling'],'author_ruling':ruling,
        'note':'Only source-unused seed was read; seed proposed outcomes are non-authoritative. See ground_truth rationale for exact frozen-policy adjudication.'}
(ROOT/'data/wild-v2/index.json').write_text(dumps(index))
(ROOT/'eval/wild-v2/ground_truth.json').write_text(dumps(keys))
(ROOT/'eval/wild-v2/seed_map.json').write_text(dumps(provenance))
(ROOT/'eval/wild-v2/omitted_seeds.json').write_text(dumps(DROPPED))
print(f'Generated {len(S)} cases from {len(set(s["seed"] for s in S))} unused seeds; omitted {len(DROPPED)}.')
