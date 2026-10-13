# Design notes: ROUTE_DEVIATION blueprint (cases 4001-4015)

Internal. Companion to `build/blueprint_rd.json` (15 records `{case_no, facts, intent}`).
Policy in force: version 6 (three base files + POL-NS-11, POL-RD-14, POL-NS-12).

## 1. What was kept from the plan

Every case keeps its planned `intended_ruling`, `difficulty`, filer, channel, mechanism and amount.
Set counts for this category are unchanged: FULL 2 (4004, 4009), PARTIAL 5 (4002, 4006, 4011, 4013,
4015), NO_ACTION 3 (4001, 4008, 4012), DRIVER_COMPENSATION 1 (4005), ESCALATE 4 (4003, 4007, 4010,
4014; EVIDENCE 4003/4010/4014, POLICY 4007); EASY 3, HARD 5, REVERSAL 4, INDETERMINATE 3; DRIVER
filers 4 (4005, 4010, 4012, 4014). Issue codes carried here as planned: GPS_GAP (4003 long, 4009
short), CLOCK_SKEW (4008 chat), MISSING chat (4009), STALE_SNAPSHOT (4015 rider profile),
LANGUAGE_AMBIGUITY (4001 chat), PARTIAL_RECORD (4010 trip record).

No case needed a different mechanism: on the planned facts the version-6 text yields the planned
ruling in all 15.

## 2. How the numbers were verified

All scripts are under `tmp/rdbp/` (throwaway):

- `engine.py`, `g40xx.py`, `routes_final.py`: every trace is built with `build/common.py`
  (`drive` / `dwell` / `concat` / `drop_between`, one `common.rng(n, 'trace')` per case, 10 s
  cadence, accuracy (3.0, 8.0) m, speed noise 1.5 km/h, no jitter). Waypoints were tuned so that
  `round(trace_distance_km, 2)` equals the billed km and the trip duration rounds to the billed
  minutes. The frozen recipes are copied verbatim into each record's `gps_trace.build_recipe`.
- `measure.py`, `calc.py`: every distance, gap, step, hint distance, gantry distance and every
  Decimal fare / POL-RD-02 / POL-RD-03 / POL-RD-04 figure written to the blueprint.
- `proto_gen.py`: a throwaway generator that reads only `build/blueprint_rd.json`, rebuilds each
  trace from its recipe, asserts the recorded measurements, assembles each case with
  `common.make_case` (validate_case + lint_case) and each key with `common.key_record` +
  `validate_key`. All 15 pass. `ref/check_set.py --range 4001 4065` on that prototype output
  reports only the expected "both categories are required" failure (one category built).
  Negative controls were run: changing one speed by 1 km/h changes 4001's trace to 9.561 and the
  assertion fails; a PARTIAL amount equal to the contested amount and a GPS_GAP without a grade are
  both rejected.
- `verify_cases.py`: recomputes, from the generated case files alone, excess %, thresholds,
  materiality, the naive RD-02 figure, gantry-to-trace distances and waypoint_hint distances.

Speeds and waypoints must be used exactly as recorded: the traces are sensitive at the 3rd
decimal (raising one segment speed of 4001 by 1 km/h moved its trace from 9.560 to 9.561).

## 3. Changes to facts relative to plan.json / plan_notes.md (mechanism unchanged)

| Case | Change | Why |
|---|---|---|
| all | Added a `route_planned` trip event naming the booked corridor's roads, distance, minutes and on-route ERP | POL-RD-03(a) and POL-RD-14 need to know which roads the optimal route uses; the event is consistent with the optimal_* fields |
| all | `trip_completed` event says the metered distance is taken from the trip GPS trace | makes RD-01's "convenience copy" and RD-07(ii)'s "not independent" readable on the record (decisive in 4003) |
| 4001 | governing_clauses `[POL-RD-04, POL-RD-01]` (plan also listed POL-RD-09) | RD-09(3) is noted in the derivation but decides nothing (no ERP line exists); BRIEF asks for the clauses that decide |
| 4001 | Stop 49.8 m from the hint (plan "about 40 m"); spur 1.900 km measured between the two junction fixes; residual 0.260 km | geometry as built; robust: even excluding only 2 x 771.5 m straight line leaves 0.617 km (8.34 %) |
| 4003 | Gap 14:11:30-14:19:00 (plan 14:08:40-14:16:10), still 450 s; jump 8.49 km (plan "about 7 km") | the tunnel falls there on the tuned trace; all thresholds unaffected |
| 4005 | Stop moved from Sembawang Shopping Centre to Northpoint City, Yishun (spur up Yishun Ave 2 from the SLE) | a natural out-and-back of about 6.35 km off the SLE corridor; trace 20.570 inside the planned window (20.534, 20.600]; non-spur 14.220 so a reader who counts only the spur (6.350) also gets 4.80 |
| 4006 | Trace 9.840 (plan said 9.85 while billing 9.84) | plan was internally inconsistent; billed 9.84 is now the 2-dp copy; excess 1.140 km = 13.10 % (fails 20 %) |
| 4006 | Referral text names the gantry id and amount | same clause, more specific |
| 4008 | Co-rider set down at Sengkang General Hospital; pickup at Hougang Ave 1 | the plan left the set-down open; itinerary named in a `pool_matched` event |
| 4009 | Carpark gap 70 s (plan 75 s), bounding fixes 194.6 m apart | 10 s cadence; 20 s margin under RD-07(a), 305 m under (b) |
| 4010 | waypoint_hint on the rider's destination-change message is null | keeps POL-RD-04 unavailable (its corroboration test cannot run with a null hint and no road), so the destination change is decided only under POL-RD-05, as the plan intends |
| 4010 | Added `destination_changed` and `route_requote_failed` events | explain the null re-quote without supplying a figure |
| 4013 | Nearest fix 3,058.9 m from the hint (plan "about 2 km") | geometry as built |
| 4014 | Destination Bishan St 22 (plan Bishan St 13); route via KPE / TPE / CTE (plan "Eunos and Upper Paya Lebar"); rider statement updated | makes the 12.8 km booked route and 17.88 km trace plausible; mechanism unchanged |
| 4015 | Trace written as 21.601 (3 dp); billed 21.60 is its 2-dp copy; excess 7.701 km = 55.40 % | 6-dp coordinate rounding; materiality margin 5.4 points; RD-02 does not use the trace figure |
| 4015 | CTE gantry named "CTE (northbound) after Moulmein Road" (plan "after Braddell Road") | the route leaves the CTE for the PIE south of Braddell; both gantries sit about 24 m from a fix |

Coordinates are plausible Singapore positions placed from general knowledge (roads, malls, MRT
stations), not surveyed; road names attached to waypoints in `path_description` are approximate.
Every policy test is run on the fixes themselves, never on the names.

## 4. Readings a reviewer may question

- **4005**: POL-RD-04's compensation limb says "may be granted"; it is reached through POL-RD-11's
  mandatory "is compensated under POL-RD-04 instead". Unbilled km = trace 20.570 - billed 14.20.
- **4009**: POL-RD-06(b) "licenses FULL_REFUND of charged_total rather than the POL-RD-02 partial"
  is read as the effect that follows once a pattern is established ("only these three effects
  follow"). With no pass-through lines the figure is exactly 27.50 = contested.
- **4007**: base, distance, time and platform-fee lines are treated as having their counterpart in
  the completed trip; only an event-type line (cancellation, waiting, gantry, surcharge) can lack
  one. The cancellation line has none and POL-RD-09(4) does not cover it, so POL-RD-10(8) fires.
  No event or note mentions the 4.50 anywhere else.
- **4012**: NO_ACTION on a driver-filed dispute leaves the rider refunded (POL-GEN-03); the POL-RD-02
  figure equals refund_issued_sgd to the cent.
- **4014 vs 4015**: the same kind of traffic assertion; 4014 cites the MISSING advisory by id
  (POL-RD-10(5), POL-RD-13(1) carve-out), 4015 cites nothing (POL-RD-13(2)).
- **4003**: the straight-line reading already exceeds 20 %, but POL-RD-07(ii) forbids establishing
  on the trace alone and none of the four independent corroborators exists; RD-07(iii) names
  ESCALATE.
- **POL-GEN-02 caps**: deciding artifacts stay >= 0.85 in every money / NO_ACTION case (4001 chat
  0.85, 4009 trace 0.85); 0.5 (4008 chat) and 0.75 (4015 rider profile) sit on artifacts that decide
  nothing; 0.6 (4003 trace) and 0.75 (4010 trip record) are the escalation reasons.
- **POL-GEN-05**: 4009 (27.50) and 4015 (15.75) exceed 8.00 and are held for release; the ruling
  value is unchanged.

## 5. Re-running the checks

    python3 tmp/rdbp/proto_gen.py tmp/rdbp/out        # rebuild the 15 cases + key from the blueprint
    python3 ref/check_set.py tmp/rdbp/out/cases tmp/rdbp/out/gt.json --range 4001 4065
    python3 tmp/rdbp/verify_cases.py tmp/rdbp/out     # independent recomputation from the case files

The prototype output was deleted after the run so that no second answer key lies in the workspace;
the commands above recreate it.

## 6. Round 1 revisions (critique_rd_r1)

Full log: `build/revisions_rd_r1.md`. Rulings, amounts, referrals, governing clauses and difficulties are
unchanged in all 15 cases; traces, fares and contested amounts are unchanged.

| Case | Change |
|---|---|
| 4006 | claim_text now asserts "4-5km extra" via Yio Chu Kang; the measured 1.140 km contradicts it, so REVERSAL rests on the record |
| 4012 | EV-ADVIS-04012-01 is now a PIE (towards Tuas) closure between the Adam Road and Eng Neo Avenue exits, valid 05:00-11:00 (covers the trip), off the booked route; both advisories carry shortest_lawful_alternative_km 14.6; route_planned names the Toa Payoh exit; rider statement "The PIE from Tampines was open". RD-03 now fails on (a) and (c), not (b), and RD-10(5) has nothing to act on |
| 4001, 4005, 4013 | stop requests sent before boarding (4013's in-motion driver message dropped, ids renumbered; 4005 MSG-005 sent from inside the mall) |
| 4003 | trip_completed says the meter ran on the driver-app (exported) trace |
| 4014 | claim reads the advisory id off the dispute page |

Reading a reviewer may question (4012): the advisory's road field is "PIE", which the booked route
uses. RD-03's example and last sentence make the segment's location decisive, and limbs (b) and (c)
cannot be met for a section the booked route never reaches, so this is a trap, not a second answer.

`build/blueprint_rd.json` is now the source of truth: re-running `tmp/rdbp/make_blueprint.py` would
revert round 1; use `tmp/rd_r1/apply.py`.

## 7. Round 2 revisions (critique_rd_r2)

Full log: `build/revisions_rd_r2.md`. Rulings, amounts, referrals, governing clauses, difficulties and
escalation kinds are unchanged in all 15 cases. Traces, fares (bar one gantry display name), trip
records and contested amounts are unchanged. `plan.json` is not edited.

| Case | Change |
|---|---|
| 13 MISSING advisories (4001, 4003-4011, 4013-4015) | note now "Artifact absent: no traffic advisory payload was retrieved for this identifier when the bundle was assembled. The identifier is minted so that the absence itself can be cited." (was "No traffic advisory was on file for this trip window. ..."), identical on all 13 |
| 4014 | claim reads the id off the dispute page in driver Singlish (id kept); intent step 5, uniqueness and rationale say the MISSING note is a retrieval result, not a record that no advisory was issued |
| 4005 | MSG-006 "ok coming out now, paiseh" at 16:21:40 (car leaves 16:22:26); chat note last time updated |
| 4008 | MSG-002 read_at 21:21:01 (before the rider's 21:21:05 reply) |
| 4010 | MSG-003 "... I changing in the app now" (precedes the 22:21:30 destination_changed event) |
| 4013 | internal path_description only: the westward Orchard stretch is to be read as the Grange Rd / Orchard Boulevard corridor; fixes not moved |
| 4015 | ERP-G-051 named "CTE (northbound) after Bukit Timah Road" (supersedes the section 3 entry "after Moulmein Road"); position and amount unchanged |

Reading a reviewer may question (4014): the MISSING note no longer admits the reading "the platform
recorded that no advisory existed", so whether an incident existed on the booked corridor stays
undetermined on the record (an evidence escalation). POL-RD-13 keys on the MISSING status and weight,
not on the note, so 4015's uncited assertion is still discarded under POL-RD-13(1)-(2).

`build/blueprint_rd.json` is the source of truth; rebuild this round with `tmp/rd_r2/apply.py` (starts
from `tmp/rd_r2/bak/blueprint_rd.r1.json`).
