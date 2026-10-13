# Authoring brief: tribunal-sealed-v3 (internal, not shipped with the cases)

This brief restates the owner's request for every authoring agent. The reference
files in `ref/` are the only sources of truth; where this brief and a policy file
disagree, the policy file wins and you should note the disagreement.

## 1. What is being made

An independent, sealed test set for an AI system that arbitrates ride-hail
disputes on a Singapore platform. The authors have never seen the system, its
code, prompts, results or any other test set, and must not try to.

- **30 cases**: `4001`-`4015` are `ROUTE_DEVIATION` (15), `4051`-`4065` are
  `NO_SHOW_CHARGE` (15).
- `dispute_id` = `DSP-0NNNN`, `trip_id` = `TRP-0NNNN` (five digits, e.g.
  `DSP-04001`, `TRP-04051`). Evidence ids `EV-<TOK>-0NNNN` with TOK in
  TRIP, GPS, CHAT, FARE, RPROF, DPROF, ADVIS; advisories are
  `EV-ADVIS-0NNNN-01` (and `-02` when there are two). Chat message ids
  `MSG-0NNNN-001`, `-002`, ... in order.
- Policy in force: **version 6** = the three base files (`general.json`,
  `no_show.json`, `route_deviation.json`) plus the three amendments
  (`0001-pol-ns-11.json`, `0002-pol-rd-14.json`, `0003-pol-ns-12.json`) applied
  on top. The amendments add POL-NS-11, POL-RD-14 and POL-NS-12; where an
  amendment says it displaces base text ("notwithstanding", "this is not the
  contradiction ... describes"), the amendment governs.
- `ref/case-00901.json` shows the file shape only. Never reuse its story,
  places, people or numbers.

### Output layout (written by `build/generate.py --out <DIR>`)

```
<DIR>/cases/case-04001.json ... case-04065.json   (30 files)
<DIR>/cases/index.json      array of {case_no, dispute_id, trip_id, category, file, sha256}
                            file = "case-0NNNN.json"; sha256 of the file bytes
<DIR>/cases/CANARY.txt      one fresh uuid4 string and nothing else (no newline)
<DIR>/cases/README.md       what the set is; no answers, no per-case outcomes
<DIR>/answers/ground_truth.json
```

## 2. Set targets (totals across all 30; the split between the categories is the planner's choice)

- `filed_by`: at least **10 DRIVER**; the rest RIDER.
- `expected_ruling`: **6 FULL_REFUND, 5 PARTIAL_REFUND, 6 NO_ACTION,
  6 DRIVER_COMPENSATION, 7 ESCALATE**.
  Of the 7 ESCALATE: **5 because the evidence cannot settle the deciding fact**
  and **2 because the policy itself requires a person** even though the facts
  are clear.
- `difficulty`: **7 EASY, 11 HARD, 7 REVERSAL** (a party's story is
  contradicted by the record), **5 INDETERMINATE** (must be ESCALATE; these are
  the five evidence-cannot-settle escalations).
- Never force a ruling the policy does not support. If the version-6 text
  yields something else on the facts, change the facts, not the answer.
- Both categories need variety of outcome, filer and difficulty.

## 3. Realism

- Singapore ride-hail as it actually looks: real neighbourhoods, malls, HDB
  estates, MRT/bus interchanges, Changi terminals, expressways (PIE, CTE, AYE,
  ECP, KPE, TPE, SLE, BKE, MCE), ERP gantries, CBD kerb rules, condo guardhouses,
  multi-entrance malls, pooled rides. Plausible coordinates (lat ~1.24-1.47,
  lng ~103.6-104.0), plausible speeds and durations, plausible dates
  (trips between 2026-08-01 and 2026-10-05, disputes filed within 30 days).
  Products: RYDE_X, RYDE_XL, RYDE_POOL, RYDE_TAXI, RYDE_PLUS.
- Chat in the voice of Singapore riders and drivers: Singlish and
  code-switching (Malay, Hokkien, Tamil words romanised) are welcome, **in
  English letters only (ASCII)**. Typos, abbreviations ("omw", "wait ah",
  "can or not", "alamak", "paiseh", "lobang", "liao", "sia", "dabao") as people
  really type.
- Data minimisation (POL-GEN-08(4)): no personal names, phone numbers or
  vehicle registration plates anywhere. Parties are `R-xxxx` / `D-xxxx`; cars
  are described by colour and model only.
- Messy evidence where realistic, using only the contract's issue codes.
  Across the set include at least once each: GPS_GAP, LOW_SAMPLE_RATE,
  GPS_DRIFT, CLOCK_SKEW (between sources), TRUNCATED_LOG, a MISSING chat log,
  STALE_SNAPSHOT, CROSS_SOURCE_CONFLICT, ADVISORY_UNCORROBORATED. Others welcome
  (UNREAD_MESSAGE, LANGUAGE_AMBIGUITY, PARTIAL_RECORD, UNVERIFIED_SOURCE,
  IMPLAUSIBLE_SPEED, LOW_COVERAGE, CONTENT_REDACTED, SCHEMA_VERSION_MISMATCH).
  Mix clean and messy cases; messiness is not decoration - decide for every
  defect whether it touches a deciding fact.
- Admissibility blocks: status COMPLETE (issues [], weight 1.0, payload
  present) / IMPAIRED (>= 1 non-missing code, payload present) / MISSING
  (issues ["MISSING_ARTIFACT"], weight 0.0, payload null). The weight of an
  IMPAIRED artifact is the **product** of the `integrity.weights` in
  `no_show.json` for its codes (the sample: LOW_SAMPLE_RATE 0.8 x
  PARTIAL_RECORD 0.75 = 0.6), with GPS_GAP graded by its three integrity
  variants (short or outside window 0.85; long inside window 0.6; straddling
  cancellation 0.6). Use the same table for both categories. `notes` state
  what the pre-pass measured (gap lengths, fix counts, skew seconds, which
  fields are null) and never the outcome of the dispute. Optional
  `issue_details` = [{code, severity, detail}].

## 4. Consistency rules (from ref/check_set.py and the arithmetic)

- Top-level keys exactly `schema_version` ("1.2.0"), `case_no`, `dispute`,
  `evidence`. Filename `case-0NNNN.json`.
- `dispute`: exactly the eleven contract keys (`case_no`, `dispute_id`,
  `trip_id`, `category`, `filed_at`, `filed_by`, `channel`,
  `amount_contested_sgd`, `claim_text`, `counterparty_statement`,
  `evidence_ids`), optionally `safety_flag` / `complaint_flag`.
  `counterparty_statement` is null or exactly {text, submitted_by,
  submitted_at}. `evidence_ids` lists every evidence_id in file order.
  `channel`: IN_APP_SUPPORT or EMAIL.
- Evidence in canonical order TRIP_RECORD, GPS_TRACE, CHAT_LOG,
  FARE_BREAKDOWN, RIDER_PROFILE, DRIVER_PROFILE, TRAFFIC_ADVISORY (one or two).
  Each artifact has exactly the eight keys. Sources only PLATFORM_TELEMETRY,
  PAYMENTS_LEDGER, THIRD_PARTY_LTA, DRIVER_DEVICE, USER_SUBMITTED.
  TRIP_RECORD and FARE_BREAKDOWN are never MISSING.
- Every NO_SHOW_CHARGE trip_record carries `platform_policy` with exactly its
  ten keys. Route-deviation trip_records may carry `platform_policy: null`.
- Trip timestamps requested <= accepted <= arrived <= started <= ended <=
  cancelled (non-null ones), unless the TRIP_RECORD carries CLOCK_SKEW.
- Fare: base_fare + distance_fare + time_fare + surge_amount + tolls_erp +
  airport_surcharge + platform_fee + cancellation_fee + waiting_time_fee -
  promo_discount = total_charged (to the cent; compute with Decimal).
  tolls_erp = sum of erp_gantries[].amount_sgd. 0 < amount_contested_sgd <=
  total_charged.
- GPS: point_count = len(points); timestamps strictly increasing;
  trace_distance_km = haversine sum over all points with R = 6371.0088 km
  (exactly check_set's km()), written rounded to 3 dp - the key is computed
  from the value as written. Every GPS_TRACE payload (no-show too) carries a
  numeric trace_distance_km.
- Chat: message_count = len(messages); msg ids sequential unless the CHAT_LOG
  carries TRUNCATED_LOG.
- Text: ASCII only. These words must not appear anywhere in a case file or
  index.json, in any letter case: ground_truth, expected_ruling,
  expected_amount_sgd, expected_driver_compensation_sgd, expected_referrals,
  governing_clauses, difficulty, rationale, canary, sealed. ("I had
  difficulty finding you" fails the check - write it another way.)
- Payload shapes: keep the sample's full key set for trip_record, gps_trace,
  chat_log, fare_breakdown, rider_profile and driver_profile on every case
  (null where not applicable), so all 30 cases share one shape. GPS points
  {lat, lng, ts, speed_kph, accuracy_m} (+ optional venue_id); rider_track
  points {lat, lng, ts, accuracy_m}. ERP gantry {gantry_id, name, lat, lng,
  charged_at, amount_sgd}. Traffic advisory payload {advisory_id, type
  (CLOSURE, ACCIDENT, KERB_RESTRICTION, ENFORCEMENT, ROADWORKS, CONGESTION),
  road, segment, geometry {from {lat,lng}, to {lat,lng}}, valid_from,
  valid_to, issued_at, shortest_lawful_alternative_km (null where not
  stated), source_ref}.

## 5. Answer key (`answers/ground_truth.json`)

An array, one record per case, sorted by case_no:

```
{"case_no": 4001, "dispute_id": "DSP-04001",
 "ground_truth": {"expected_ruling": ..., "expected_amount_sgd": ...,
   "expected_driver_compensation_sgd": ..., "expected_referrals": [...],
   "governing_clauses": [...], "difficulty": ..., "rationale": "..."}}
```

- Derived from the version-6 policy text alone.
- FULL_REFUND: amount == amount_contested_sgd exactly (so set the contested
  amount to what the filer actually disputes). PARTIAL_REFUND: 0 < amount <
  contested, a multiple of 0.05. DRIVER_COMPENSATION: amount ==
  driver_compensation > 0, a multiple of 0.05. NO_ACTION / ESCALATE: both
  null. A FULL_REFUND or PARTIAL_REFUND may also carry a driver_compensation
  (> 0) where the policy produces both (e.g. POL-NS-03(ii)); otherwise null.
- `expected_referrals`: strings, each naming the clause that produces it
  (e.g. "POL-RD-06(c): driver-conduct review"); [] where none. A referral is
  never an escalation.
- `governing_clauses`: bare clause ids (`POL-NS-07`, not `POL-NS-07(a)`)
  from the version-6 set, at least one of which licenses the ruling per its
  `licenses` array (check_set's LIC table mirrors them; POL-GEN-08 is accepted
  for a POL-GEN-08(1) routing). Do not lean on POL-GEN-03's universal licence
  to make a ruling pass - list the clauses that actually decide the case.
- `rationale`: 120-2500 characters, ASCII; names this case's evidence ids and
  the deciding clause ids, states the deciding numbers and the arithmetic.

## 6. General policy-reading reminders (not case-specific)

- POL-GEN-03: NO_ACTION is party-relative and never "restore the charge";
  ESCALATE is terminal, replaces the ruling, null money; a referral never
  suppresses money; on DRIVER_COMPENSATION amount_sgd mirrors
  driver_compensation_sgd; a verified no-show with compensation paid is
  DRIVER_COMPENSATION, not NO_ACTION (POL-NS-07).
- POL-GEN-02(2): confidence is capped by the weight of the artifacts carrying
  the deciding fact (min across artifacts needed; max where two independent
  artifacts carry the same fact), and the floor is 0.70. A deciding fact
  carried solely by an artifact under 0.70 cannot support a ruling. In cases
  meant to produce money or NO_ACTION, keep every deciding artifact at >= 0.70
  (prefer >= 0.75); put heavier defects on artifacts that decide nothing, or
  make the defect the reason the case escalates.
- Schema-level vs policy-level impairment: POL-RD-07(a)-(c) (gap > 90 s, jump
  > 500 m, sustained interval > 30 s inside the disputed segment) and
  POL-NS-08(a)-(d) have their own thresholds. An artifact may be tagged by the
  pre-pass and still be policy-clean, and vice versa; design deliberately and
  never trip a limb by accident (e.g. a 20 s cadence at 100 km/h is a 556 m
  jump).
- Fee figures come from trip_record.platform_policy where present
  (fee_schedule.resolution_rule). POL-NS-07 pays 80 % of the NET fee; POL-NS-03(ii)
  goodwill is 50 % of the fee.
- Route-deviation money: POL-RD-02 recomputation as written (surge from
  fare_breakdown.surge_multiplier; only on-optimal-route ERP, which the
  trip_record states as optimal_route_erp_sgd; payable rounded UP to 0.05;
  de minimis below 0.50; >= 90 % of charged_total becomes FULL_REFUND);
  POL-RD-09 anti-double-count; POL-RD-11 for UPFRONT_QUOTE fares.
- POL-GEN-01: only the listed trailing-window counters may decide anything;
  lifetime near-synonyms are context only.
- POL-GEN-04/05/06 are procedural and never change a ruling value; POL-GEN-08(1)
  routes flagged or allegation cases to a person with no draft ruling.
- Each non-ESCALATE case must have exactly one defensible answer. Each
  ESCALATE must have a trigger a careful reader would agree fires, with no
  other clause rescuing the case. Do not build a case on an unresolved tension
  between clauses, or on a figure the record does not determine; avoid
  knife-edge numbers unless the case is deliberately an arithmetic edge test
  that stays unambiguous at the precision written to the file.

## 7. Confidentiality

People on the development side read the chat that launched this work and must
not learn the answers. Agents' final replies return only what their schema
asks (counts, ok flags, verdict codes). All stories, rulings, amounts,
clauses, difficulties and rationales live only in files under build/, out/
and review/.
