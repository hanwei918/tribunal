"""Cross-field validation of the sealed set, mirroring SCHEMA.md §9 (the checks JSON Schema cannot do)."""
import os, sys, json, glob, re, math
sys.path.insert(0, os.path.dirname(__file__))
from core import W, SEV, SEV_RANK, haversine_km
from jsonschema import Draft202012Validator

# ROOT = the set's root (the folder holding data/ and eval/). When run from the generator folder it is the parent;
# override with WILD_ROOT. REPO = the Tribunal repo (for data/schema.json and policy/*.json), set TRIBUNAL_REPO.
_here = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("WILD_ROOT") or (os.path.join(_here, "..", "out") if os.path.isdir(os.path.join(_here, "..", "out")) else os.path.join(_here, ".."))
REPO = os.environ.get("TRIBUNAL_REPO", ROOT)
SCHEMA = json.load(open(os.path.join(REPO, "data", "schema.json")))
POL = {}
for f in ("general","no_show","route_deviation"):
    for c in json.load(open(os.path.join(REPO, "policy", f"{f}.json")))["clauses"]:
        POL[c["id"]] = c
GT = json.load(open(os.path.join(ROOT, "eval", "wild-v2", "ground_truth.json")))
FORBID = ("ground_truth","expected_ruling","expected_amount_sgd","expected_driver_compensation_sgd","expected_referrals","difficulty","governing_clauses","rationale")

sub = dict(SCHEMA); sub["$ref"] = "#/$defs/case_file"; V = Draft202012Validator(sub)
gsub = dict(SCHEMA); gsub["$ref"] = "#/$defs/ground_truth"; GV = Draft202012Validator(gsub)

fails = []
def F(c, k, msg): fails.append((c, k, msg))

from datetime import datetime
def P(s): return datetime.fromisoformat(s.replace("+08:00","+08:00"))

diff_counts = {}
paths = sorted(glob.glob(os.path.join(ROOT,"data","wild-v2","cases","*.json")))
manifest = json.load(open(os.path.join(ROOT,"data","wild-v2","index.json")))
if not isinstance(manifest,list) or len(manifest)!=len(paths) or len(GT)!=len(paths):
    F(0,1,"manifest/case/key cardinality mismatch")
manifest_by_no={i['case_no']:i for i in manifest}
if len(manifest_by_no)!=len(manifest): F(0,1,"duplicate manifest case number")
for path in sorted(glob.glob(os.path.join(ROOT,"data","wild-v2","cases","*.json"))):
    raw = open(path, encoding="utf-8").read()
    d = json.loads(raw); c = d["case_no"]
    if set(d)!={'schema_version','case_no','dispute','evidence'}: F(c,1,"PUBLIC-CONTRACT top-level shape")
    item=manifest_by_no.get(c)
    if not item or set(item)!={'case_no','dispute_id','trip_id','category','file'}: F(c,1,"PUBLIC-CONTRACT manifest shape")
    elif os.path.realpath(os.path.join(ROOT,'data','wild-v2',item['file']))!=os.path.realpath(path): F(c,1,"external-set manifest path must resolve relative to its own set root, as in wild-v1")
    if os.path.basename(path)!=f'case-{c:05d}.json': F(c,1,"filename mismatch")
    # 20/21: no answer keys in raw bytes
    for w in FORBID:
        if f'"{w}"' in raw: F(c, 21, f"forbidden key {w} present in case file")
    # 1-4 schema
    errs = list(V.iter_errors(d))
    if errs: F(c, 7, f"{len(errs)} schema errors: " + errs[0].message[:120])
    disp = d["dispute"]; ev = d["evidence"]
    if len(ev)!=7: F(c,6,"exactly seven artifacts required")
    if set(disp)!={'case_no','dispute_id','trip_id','category','filed_at','filed_by','channel','amount_contested_sgd','claim_text','counterparty_statement','evidence_ids'}: F(c,1,"PUBLIC-CONTRACT dispute shape")
    if item and any(item[k]!=disp[k] for k in ('case_no','dispute_id','trip_id','category')): F(c,1,"manifest metadata mismatch")
    for e in ev:
        if set(e)!={'evidence_id','evidence_type','admissibility','payload','schema_version','source','trip_id','generated_at'}: F(c,1,"PUBLIC-CONTRACT artifact shape")
    ids = [e["evidence_id"] for e in ev]
    # 5 case number consistency
    for e in ev:
        if not e["evidence_id"].split("-")[2] == f"{c:05d}": F(c,5,f"evidence id case mismatch {e['evidence_id']}")
        if e["trip_id"] != f"TRP-{c:05d}": F(c,5,f"trip_id mismatch on {e['evidence_id']}")
    if disp["dispute_id"] != f"DSP-{c:05d}" or disp["trip_id"] != f"TRP-{c:05d}": F(c,5,"dispute id mismatch")
    # 6 six singletons exactly once; 7 advisory ordinals dense
    toks = [i.split("-")[1] for i in ids]
    for t in ("TRIP","GPS","CHAT","FARE","RPROF","DPROF"):
        if toks.count(t) != 1: F(c,6,f"singleton {t} count {toks.count(t)}")
    adv = sorted(int(i.split("-")[3]) for i in ids if i.split("-")[1]=="ADVIS")
    if adv != list(range(1,len(adv)+1)) or not adv: F(c,7,f"advisory ordinals {adv}")
    # 13 dispute.evidence_ids == set, sorted order
    if disp["evidence_ids"] != ids: F(c,13,"dispute.evidence_ids != evidence order")
    order = {"TRIP":0,"GPS":1,"CHAT":2,"FARE":3,"RPROF":4,"DPROF":5,"ADVIS":6}
    if [order[t] for t in toks] != sorted(order[t] for t in toks): F(c,13,"evidence not in canonical order")
    # 8-12 admissibility invariants
    by = {e["evidence_id"]: e for e in ev}
    for e in ev:
        a = e["admissibility"]; st=a["status"]; iss=a["issues"]; w=a["weight_multiplier"]
        if st=="COMPLETE" and (iss or w!=1.0 or e["payload"] is None): F(c,8,f"{e['evidence_id']} COMPLETE invariant")
        if st=="MISSING" and (iss!=["MISSING_ARTIFACT"] or w!=0.0 or e["payload"] is not None): F(c,8,f"{e['evidence_id']} MISSING invariant")
        if st=="IMPAIRED":
            if not iss or "MISSING_ARTIFACT" in iss or e["payload"] is None: F(c,8,f"{e['evidence_id']} IMPAIRED invariant")
            prod=1.0
            for k in iss: prod*=W[k]
            if abs(w-max(0.25,round(prod,2)))>1e-9: F(c,12,f"{e['evidence_id']} weight {w} != recomputed {max(0.25,round(prod,2))}")
        for k in iss:
            if k not in W: F(c,9,f"unknown issue code {k}")
        if iss != sorted(iss,key=lambda k:(SEV_RANK[SEV[k]],k)): F(c,9,f"{e['evidence_id']} issues not severity-ordered")
        for dd in a.get("issue_details",[]):
            if dd["code"] not in iss: F(c,10,f"{e['evidence_id']} detail code {dd['code']} not in issues")
            if dd["code"] in ("CROSS_SOURCE_CONFLICT","FARE_RECOMPUTE_MISMATCH","DISTANCE_MISMATCH","ADVISORY_UNCORROBORATED"):
                rel=dd.get("related_evidence_ids") or []
                if not rel: F(c,11,f"{e['evidence_id']} family E without related_evidence_ids")
                for r in rel:
                    if r not in by: F(c,11,f"{e['evidence_id']} related id {r} unresolvable")
    trip=by[f"EV-TRIP-{c:05d}"]["payload"]; gps=by[f"EV-GPS-{c:05d}"]["payload"]; fare=by[f"EV-FARE-{c:05d}"]["payload"]
    # 17 fare identity
    tot = (fare["base_fare"]+fare["distance_fare"]+fare["time_fare"]+fare["surge_amount"]+fare["tolls_erp"]+fare["airport_surcharge"]
           +fare["platform_fee"]+fare["cancellation_fee"]+fare["waiting_time_fee"]-fare["promo_discount"])
    if abs(tot-fare["total_charged"])>0.05 and "FARE_RECOMPUTE_MISMATCH" not in by[f"EV-FARE-{c:05d}"]["admissibility"]["issues"]:
        F(c,17,f"fare identity off by {tot-fare['total_charged']:.3f}")
    if abs(fare["tolls_erp"]-sum(g["amount_sgd"] for g in (fare.get("erp_gantries") or [])))>0.005: F(c,17,"tolls_erp != sum gantries")
    # 18 trip causality
    seq=[trip[k] for k in ("requested_at","accepted_at","arrived_at","started_at","ended_at","cancelled_at") if trip[k]]
    if any(P(seq[i])>P(seq[i+1]) for i in range(len(seq)-1)) and "TIMESTAMP_INCONSISTENT" not in by[f"EV-TRIP-{c:05d}"]["admissibility"]["issues"]:
        F(c,18,"trip timestamps not causal")
    # 19 derived fields
    if trip["actual_distance_km"] is not None:
        dp=round((trip["actual_distance_km"]-trip["optimal_distance_km"])/trip["optimal_distance_km"]*100,1)
        if abs(dp-trip["deviation_pct"])>0.05: F(c,19,f"deviation_pct {trip['deviation_pct']} != {dp}")
    if trip["arrived_at"]:
        term = trip["started_at"] or trip["cancelled_at"]
        wt=round((P(term)-P(trip["arrived_at"])).total_seconds()/60,1)
        if abs(wt-trip["wait_time_min"])>0.05: F(c,19,f"wait_time_min {trip['wait_time_min']} != {wt}")
    if gps:
        pts=gps["points"]
        if any('accuracy_m' not in p for p in pts+(gps.get('rider_track') or [])): F(c,19,"accuracy_m required on every GPS point")
        if gps["point_count"]!=len(pts): F(c,19,"point_count")
        tss=[P(p["ts"]) for p in pts]
        if any(tss[i]>=tss[i+1] for i in range(len(tss)-1)): F(c,19,"gps ts not strictly monotonic")
        dist=round(sum(haversine_km((pts[i-1]["lat"],pts[i-1]["lng"]),(pts[i]["lat"],pts[i]["lng"])) for i in range(1,len(pts))),2)
        if abs(dist-gps["trace_distance_km"])>0.011: F(c,19,f"trace_distance {gps['trace_distance_km']} != {dist}")
        gaps=[(tss[i]-tss[i-1]).total_seconds() for i in range(1,len(tss)) if (tss[i]-tss[i-1]).total_seconds()>30]
        if len(gaps)!=len(gps["gaps"]): F(c,19,f"gaps count {len(gps['gaps'])} != {len(gaps)}")
        anchor=P(trip["started_at"] or trip["accepted_at"]); terminal=P(trip["ended_at"] or trip["cancelled_at"])
        aw=(terminal-anchor).total_seconds(); cov=round(max(0,min(100,100*(aw-sum(gaps))/aw)),1)
        if abs(cov-gps["coverage_pct"])>0.05: F(c,19,f"coverage {gps['coverage_pct']} != {cov}")
        if gaps and "GPS_GAP" not in by[f"EV-GPS-{c:05d}"]["admissibility"]["issues"]: F(c,19,"gap present but GPS_GAP not declared")
        if cov<90 and "LOW_COVERAGE" not in by[f"EV-GPS-{c:05d}"]["admissibility"]["issues"]: F(c,19,"coverage<90 but LOW_COVERAGE not declared")
        # speed plausibility
        mx=max(p["speed_kph"] for p in pts)
        if mx>130 and "IMPLAUSIBLE_SPEED" not in by[f"EV-GPS-{c:05d}"]["admissibility"]["issues"]: F(c,19,f"max speed {mx} undeclared")
        # distance mismatch
        if trip["actual_distance_km"] is not None and abs(gps["trace_distance_km"]-trip["actual_distance_km"])/gps["trace_distance_km"]>0.10 \
           and "DISTANCE_MISMATCH" not in by[f"EV-GPS-{c:05d}"]["admissibility"]["issues"]: F(c,19,"distance mismatch >10% undeclared")
        # advisory intersects_route recompute
        for e in ev:
            if e["evidence_type"]=="TRAFFIC_ADVISORY" and e["payload"]:
                g=e["payload"]["geometry"]
                inter=any(g["min_lat"]<=p["lat"]<=g["max_lat"] and g["min_lng"]<=p["lng"]<=g["max_lng"] for p in pts)
                if inter!=e["payload"]["intersects_route"]: F(c,19,f"{e['evidence_id']} intersects_route")
    # chat
    ch=by[f"EV-CHAT-{c:05d}"]["payload"]
    if ch:
        if ch["message_count"]!=len(ch["messages"]): F(c,19,"message_count")
        if trip["chat_message_count"]!=len(ch["messages"]): F(c,19,f"trip.chat_message_count {trip['chat_message_count']} != {len(ch['messages'])}")
        for k,m in enumerate(ch["messages"],1):
            if m["msg_id"]!=f"MSG-{c:05d}-{k:03d}": F(c,19,f"msg_id sequence {m['msg_id']}")
    # 20 amount_contested
    if not (0<disp["amount_contested_sgd"]<=fare["total_charged"]): F(c,20,f"amount_contested {disp['amount_contested_sgd']} vs total {fare['total_charged']}")
    # profiles snapshot within 72h of filed_at
    for tok in ("RPROF","DPROF"):
        pr=by[f"EV-{tok}-{c:05d}"]
        if pr["payload"]:
            dt=abs((P(pr["payload"]["snapshot_at"])-P(disp["filed_at"])).total_seconds())/3600
            if dt>72 and "STALE_SNAPSHOT" not in pr["admissibility"]["issues"]: F(c,19,f"{tok} snapshot {dt:.0f}h from filed_at, STALE_SNAPSHOT undeclared")
    # ---- ground truth ----
    g=GT[str(c)]
    gerr=list(GV.iter_errors(g))
    if gerr: F(c,14,"gt schema: "+gerr[0].message[:120])
    r=g["expected_ruling"]; a=g["expected_amount_sgd"]; dc=g["expected_driver_compensation_sgd"]
    if r=="FULL_REFUND" and abs(a-disp["amount_contested_sgd"])>1e-9: F(c,14,f"FULL_REFUND amount {a} != contested {disp['amount_contested_sgd']}")
    if r=="PARTIAL_REFUND" and not (0<a<disp["amount_contested_sgd"]): F(c,14,f"PARTIAL amount {a} not in (0,{disp['amount_contested_sgd']})")
    if r in ("NO_ACTION","ESCALATE") and (a is not None or (r=="ESCALATE" and dc is not None)): F(c,14,"NO_ACTION/ESCALATE amount invariant")
    if r=="DRIVER_COMPENSATION" and (a is None or a<=0 or dc!=a): F(c,14,"DRIVER_COMPENSATION amount==comp invariant")
    if g["difficulty"]=="INDETERMINATE" and r!="ESCALATE": F(c,15,"INDETERMINATE must ESCALATE")
    for cl in g["governing_clauses"]:
        if not re.match(r"^POL-[A-Z]{2,4}-\d{2}$",cl) or cl not in POL: F(c,16,f"clause {cl} malformed or not in corpus")
    if not g["governing_clauses"]: F(c,16,"no governing clauses")
    if not (120<=len(g["rationale"])<=2500): F(c,14,f"rationale length {len(g['rationale'])}")
    # rationale should name at least one evidence id and one clause
    if not re.search(rf"EV-[A-Z]+-{c:05d}",g["rationale"]): F(c,14,"rationale names no evidence id of this case")
    if not re.search(r"POL-[A-Z]+-\d\d",g["rationale"]): F(c,14,"rationale names no clause")
    # ruling must be licensed by some governing clause
    lic=set(); [lic.update(POL[cl]["licenses"]) for cl in g["governing_clauses"]]
    if r not in lic: F(c,16,f"ruling {r} not licensed by any governing clause {g['governing_clauses']}")
    diff_counts[g["difficulty"]]=diff_counts.get(g["difficulty"],0)+1

n=len(GT)
print("difficulty:",diff_counts,{k:f"{v/n:.2f}" for k,v in diff_counts.items()})
bounds={"EASY":(0.15,0.50),"HARD":(0.20,0.60),"REVERSAL":(0.10,0.35),"INDETERMINATE":(0.05,0.25)}
for k,(lo,hi) in bounds.items():
    fr=diff_counts.get(k,0)/n
    if not (lo<=fr<=hi): F(0,5,f"difficulty {k} fraction {fr:.2f} outside [{lo},{hi}]")
if fails:
    for c,k,m in fails: print(f"FAIL case {c} check {k}: {m}")
    print(f"\n{len(fails)} failure(s)"); sys.exit(1)
print("ALL CHECKS PASSED")
