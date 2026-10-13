# Revisions, ROUTE_DEVIATION blueprint, round 2 (critique_rd_r2.json)

Internal. This file applies `build/critique_rd_r2.json` to `build/blueprint_rd.json` (cases 4001-4015).
Policy in force: version 6, meaning the three base files plus POL-NS-11, POL-RD-14 and POL-NS-12.

## 0. Outcome in one paragraph

**Every planned ruling, amount, driver compensation, referral, governing-clause list, difficulty and
escalation kind is unchanged in all 15 cases. No case needed a "nearest honest alternative", so
`build/plan.json` is not edited.** The critic returned one FIX verdict (4014). Checked against the
policy text, the critic is right, and the fix is applied as proposed: the note on the MISSING advisory
is reworded on all 13 RD cases that carry one, so that 4014's note is not unique. The case's mechanism
is the same, and so is its answer. Of the optional items:

- Applied: four (4005, 4008, 4010, 4015).
- Applied in part: 4013. The internal path description is corrected; the waypoint nudge is rejected.
- Applied: the optional rewording of 4014's claim.
- Rejected again: 4009's speed retune, with the same reasons as round 1.

Traces, fares (except one gantry's display name), trip records and contested amounts are unchanged in
all 15 cases. A script asserted this against the round-1 copy.

Changed records: all 13 cases with a MISSING advisory (4001, 4003-4011, 4013, 4014, 4015), plus the
extra edits listed below for 4005, 4008, 4010, 4013, 4014 and 4015.

## 1. Decision log

| Case | Critique item | Verdict on the critic | Decision |
|---|---|---|---|
| 4014 | FIX: the MISSING-advisory note "No traffic advisory was on file for this trip window." can be read as an affirmative record that no advisory existed, which would settle the deciding fact and turn an EVIDENCE escalation into a POLICY one | Right | APPLIED |
| 4014 | FIX: reword the note on all 13 RD MISSING advisories, not only 4014's (a unique note would be a tell) | Right | APPLIED (all 13, both copies of the note in each record) |
| 4014 | FIX: keep the claim's citation of EV-ADVIS-04014-01; optionally phrase it as read off the dispute page | Right / sound | APPLIED (citation kept; wording made more driver-like) |
| 4014 | FIX: no change to ruling, difficulty or escalation_kind | Right | FOLLOWED |
| 4005 | optional: MSG-04005-006 at about 16:21:40, "ok coming out now, paiseh" | Sound | APPLIED |
| 4008 | optional: MSG-04008-002 read_at 21:21:01 | Sound | APPLIED |
| 4010 | optional: MSG-04010-003 "I changing in the app now" | Sound | APPLIED |
| 4013 | optional: rename the internal path to Orchard Boulevard / Grange Rd westbound | Sound | APPLIED (internal description only) |
| 4013 | optional: nudge the waypoints onto Orchard Boulevard within (15.88, 15.94] | Valid, but not worth the risk | REJECTED (section 3) |
| 4015 | optional: rename ERP-G-051 to match its position | Sound | APPLIED ("CTE (northbound) after Bukit Timah Road") |
| 4009 | optional: raise the expressway speeds to 65-75 km/h and re-tune | Critic calls it optional only | REJECTED (same reasons as round 1) |
| 4001 | realism note on MSG-04001-004; critic: "none required" | - | NOT ACTED ON (no fix proposed; see section 3) |
| 4002, 4006 | realism notes on the riders' "usually ..." fare memories; critic: "none required", "harmless" | - | NOT ACTED ON |
| 4003, 4004, 4007, 4011, 4012 | OK, no issues raised | - | No change beyond the shared note in 4003, 4004, 4007 and 4011 |

## 2. FIX item: case 4014 (ESCALATE, driver, INDETERMINATE, EVIDENCE)

**Check against the policy.**

- The answer itself is not in question. The driver invokes POL-RD-03 and cites EV-ADVIS-04014-01 by
  its identifier. That artifact is MISSING. POL-RD-10(5) escalates where "an exculpatory clause is
  invoked against a cited artifact that is missing from the pool". POL-RD-13(1) says it "does not
  narrow POL-RD-10(5) where the party does cite the missing identifier; that case still escalates".
  ESCALATE is the only defensible answer, and the critic agrees.
- The label is what is at issue. BRIEF section 2 splits the seven ESCALATEs into five where "the
  evidence cannot settle the deciding fact" and two where "the policy itself requires a person even
  though the facts are clear". The deciding fact in 4014 is whether there was an incident or advisory
  on the booked PIE corridor in the trip window.
- The old note can be read two ways:
  1. "This bundle holds no advisory." This is the sense POL-RD-13 uses: "the bundle holds no
     traffic_advisory covering the trip window - the artifact's admissibility status is MISSING".
  2. "The platform recorded that no advisory existed for this trip window."

  Reading 2 settles the deciding fact against the driver. The escalation would then be policy-forced
  on clear facts, the POLICY kind (like 4007), and INDETERMINATE would be contestable.
- POL-GEN-02 already limits reading 2: "A MISSING artifact has weight 0.0, can carry no fact, and its
  absence is itself citable." Even so, the critic is right that the wording invites the reading, and
  the cure costs nothing. A note that reports only the retrieval result removes the ambiguity, rather
  than relying on a reader to apply GEN-02 to a note. BRIEF section 3 also asks that notes "state what
  the pre-pass measured ... and never the outcome of the dispute". Reading 2 comes close to stating an
  outcome-relevant fact.

**Change (all 13 MISSING advisories: 4001, 4003, 4004, 4005, 4006, 4007, 4008, 4009, 4010, 4011, 4013,
4014, 4015).**

- `traffic_advisories[].admissibility.notes` and `admissibility["EV-ADVIS-0NNNN-01"].notes` now both
  read: "Artifact absent: no traffic advisory payload was retrieved for this identifier when the bundle
  was assembled. The identifier is minted so that the absence itself can be cited."
- Status MISSING, issues [MISSING_ARTIFACT], weight 0.0 and payload null are unchanged.
- The wording follows the critic's suggestion with "traffic" added. It opens "Artifact absent", as
  `FOUNDATION.md`'s example and the NS blueprint's MISSING advisories do.
- The note is identical on all 13 cases, which a check asserts. It therefore points at no single case.
- The two COMPLETE advisories (4002, and both of 4012's) are untouched.

**Effect on the other cases: none on any answer.**

- POL-RD-13 keys on the MISSING status and weight 0.0, not on the note. 4015 (an ECP accident
  asserted with no advisory id) therefore still falls under POL-RD-13(1)-(2) and stays PARTIAL_REFUND
  15.75.
- 4015's intent still says the ruling records that "no advisory was on file". That is POL-RD-13(2)'s
  own phrase for the bundle holding none, and it remains true.
- A scan of every claim, counterparty statement and chat message found traffic assertions only in
  4002 and 4012 (COMPLETE advisories), 4014 (cited) and 4015 (uncited). No other case invokes an
  advisory, so POL-RD-10(5) cannot reach them.

**Claim wording (the optional part of the FIX).** It now reads: "Got accident on the PIE near Kallang
that afternoon. The dispute page show one LTA advisory for this trip, EV-ADVIS-04014-01, pls check. I
avoid it by KPE and TPE. Pls return the 6.05 deducted from my earnings."

- The identifier stays in the claim, which is what makes POL-RD-13(1)'s carve-out bite.
- The driver is reading the id off the dispute page. The page does list it: it is in
  `dispute.evidence_ids`.

**Intent text (the answer is unchanged).**

- Derivation step 5 now says the note records only a retrieval result. It is not a record that no
  advisory was issued, so the absence is a data gap and not a finding against the driver.
- `uniqueness` gains the same point. It notes that the wording is shared by every RD MISSING advisory,
  so this is an evidence escalation, not a policy-only one.
- The rationale gains one clause to the same effect. It is now 937 characters.

ruling, amount, compensation, referrals, governing_clauses ([POL-RD-10, POL-RD-13]), difficulty
(INDETERMINATE), escalation_kind (EVIDENCE), arithmetic, trap and what_would_resolve are all
unchanged.

**Set counts are unchanged.** The RD side still has four ESCALATEs: EVIDENCE 4003, 4010 and 4014, and
POLICY 4007.

## 3. Optional items

- **4005, MSG-04005-006: APPLIED.**
  - The text "ok coming back now, paiseh" becomes "ok coming out now, paiseh", typed from inside the
    mall.
  - The message moves from 16:22:10 to 16:21:40. delivered_at is 16:21:41 and read_at 16:21:52.
  - The car is stationary at the Northpoint stop from 16:16:26 to 16:22:26. It now leaves 46 s after
    the message, where before it left after 16 s.
  - chat_log.last_message_at and the chat admissibility note ("last 16:21:40") are updated. The
    largest interval stays 1165 s (MSG-004 at 16:00:05 to MSG-005 at 16:19:30).
  - Nothing deciding moves. The request is MSG-04005-003 at 15:59:50, before boarding, and its hint is
    55.0 m from the stop. Unbilled 20.570 - 14.20 = 6.370 km; 0.75 x 6.370 = 4.7775, rounded up to
    4.80.
- **4008, MSG-04008-002 read_at: APPLIED.**
  - read_at moves from 21:21:07 to 21:21:01. The order is now delivered 21:20:58, read 21:21:01, then
    the rider's "coming down" at 21:21:05.
  - Both are on the chat clock, so the CLOCK_SKEW (+47 s on the six SYSTEM mirrors) is untouched, and
    so is the chat's weight of 0.5. The chat decides nothing in this case (POL-RD-12).
- **4010, MSG-04010-003: APPLIED.**
  - The text "... I changed in the app already" becomes "... I changing in the app now". The message
    at 22:21:05 now precedes the destination_changed event (22:21:30) without contradicting it.
  - waypoint_hint stays null, and Paya Lebar Quarter was already named, so POL-RD-04's position is
    unchanged.
  - The amended_optimal fields stay null. ESCALATE under POL-RD-05 and POL-RD-10(5) is unchanged.
- **4013, internal path description: APPLIED.**
  - `gps_trace.path_description` is informational and is not written into the case file. It said
    "Orchard Rd west to Tanglin", which is plainly wrong because Orchard Rd is one-way eastbound.
  - It now says the trace runs "north-west and west through the Orchard area towards Tanglin (to be
    read as the westbound Grange Rd / Orchard Boulevard corridor ...)". It also says honestly that the
    fixes are placed from general knowledge, not snapped to a road, and that part of the westward
    stretch lies close to the Orchard Rd line. My own rough reckoning puts the 14:55-14:57 fixes
    (lat about 1.3055-1.3060) near the western Orchard Rd line, rather than 150-300 m off it.
- **4013, waypoint nudge onto Orchard Boulevard: REJECTED.** Four reasons:
  1. Every coordinate in this blueprint is placed from general knowledge, not surveyed. The offset at
     issue (100-300 m) is the same order as that placement error, so a nudge would swap one
     approximate alignment for another without being able to show it is right. My reckoning and the
     critic's already disagree on how far the fixes sit from Orchard Rd.
  2. The trace is frozen. A nudge moves trace_distance_km, the duration, ended_at, the
     trip_completed event, charged_at and the GPS and trip notes, and it puts 4013's REVERSAL
     arithmetic (5.78, rounded up to 5.80) back at risk.
  3. The critic itself rates it optional and says the case file alone is ambiguous.
  4. It has no policy effect: the deciding facts are the hint distance (3,058.9 m) and the 15.920 km
     trace.
- **4015, ERP-G-051 name: APPLIED.**
  - "CTE (northbound) after Moulmein Road" becomes "CTE (northbound) after Bukit Timah Road", which
    matches the gantry's stated position (1.3089, 103.84786) on the CTE near the Bukit Timah Rd end.
  - The id, coordinates, charged_at and the 2.00 amount are unchanged, so the nearest fix is still
    24.4 m and RD-09(1) is unchanged.
  - The internal path_description still says the route goes "north past Moulmein", which describes
    the trace, not the gantry. The design-notes table entry from the first build is superseded (design
    notes section 7).
- **4009, faster expressway speeds: REJECTED.** This is the same reasoning as round 1. A speed change
  moves the trace, duration, time_fare, total, contested amount and the FULL_REFUND figure, which must
  equal the contested amount. The critic marks it "optional only" and notes it would need re-tuning.
  Slow expressway legs also fit a meter-padding long-hauler.
- **4001, MSG-04001-004: NOT ACTED ON.** The critic proposed no fix and reads it as typed while walking
  up to the car (27 s before the car moves). The chat carries 4001's deciding fact (LANGUAGE_AMBIGUITY,
  weight 0.85). Editing it for a non-defect is not worth disturbing.
- **4002 and 4006, the riders' "usually ..." figures: NOT ACTED ON.** These are rider memory, which the
  record does not decide. The critic calls them harmless.

**Observation outside this task (no edit made).** The NS blueprint's MISSING advisories use a different
wording: "Artifact absent: no traffic advisory was returned for the pickup road and the trip window. ..."

- The wording is uniform within each category, so it is not a per-case tell.
- No NS claim or counterparty statement cites an advisory id (checked read-only).
- Harmonising the two categories' wording is the NS owner's call.

## 4. Re-verification (run after the changes)

The scripts are in `tmp/rd_r2/`. The round-1 inputs are backed up in `tmp/rd_r2/bak/`.

1. `python3 tmp/rd_r2/apply.py` rebuilds `build/blueprint_rd.json` from
   `tmp/rd_r2/bak/blueprint_rd.r1.json`. Every edit asserts the old value first, so it cannot
   double-apply.
2. `python3 tmp/rdbp/proto_gen.py tmp/rd_r2/out` rebuilt all 15 cases. It asserts every trace
   measurement, runs `common.make_case` (validate_case and lint_case) and runs `common.validate_key`.
   All 15 built. The same command on the round-1 blueprint built the baseline in
   `tmp/rd_r2/base_out`.
3. `python3 ref/check_set.py tmp/rd_r2/out/cases tmp/rd_r2/out/gt.json --range 4001 4065` reported
   only the expected "both categories are required" failure, because one category was built. That
   covers ASCII, forbidden words, fare and ERP sums (Decimal-exact in the blueprint), haversine trace
   distances, timestamps and key format.
4. `tmp/rdbp/verify_cases.py`, run before and after: identical output for all 15 cases. That covers
   excess, thresholds, materiality, the RD-02 figure, gantry and hint distances and rulings.
5. `python3 tmp/rd_r2/verify_r2.py tmp/rd_r2/base_out tmp/rd_r2/out` ran 88 independent checks from
   the case files only, with Decimal money and haversine at R = 6371.0088. All 88 pass.
   - All 13 MISSING advisories: status, issues, weight and payload, the exact new note, no "on file",
     one identical note across all 13, and the COMPLETE advisories untouched.
   - 4014:
     - the claim still cites the id;
     - 17.880 - 12.8 = 5.080 km, 39.69 %, established and not material;
     - the trace is policy-clean;
     - the contrast RD-02 figure is 19.52, and 25.57 - 19.52 = 6.05, which equals refund_issued and
       the contested amount.
   - 4005:
     - chat order and delivered/read order;
     - MSG-006 is sent while the car is stationary, at least 30 s before it leaves;
     - the note's last time and largest interval match;
     - RD-04: the request comes before boarding and the hint is within 200 m. 0.75 x 6.370 rounds up
       to 4.80.
   - 4008: read_at is before the reply, the +47 s skew is intact, and the chat is still IMPAIRED at
     0.5.
   - 4010: the message precedes destination_changed, the hint is null, and the re-quote fields are
     null.
   - 4015: the name is updated, both gantries are within 250 m, tolls are 3.50, and RD-02 gives
     27.3005, so the refund is 15.75.
   - A structural diff of every case file (base against after) shows that only the intended fields
     changed. 4013's case file is byte-for-byte unchanged apart from the shared note.
6. Negative controls (`--mutate`). Each check fails when its fact is broken:

   | Mutation | Failures |
   |---|---|
   | 4014 old note restored | 4 |
   | 4014 id removed from claim | 1 |
   | 4005 MSG-006 at 16:22:40 | 6 |
   | 4008 read_at back to 21:21:07 | 2 |
   | 4010 "already" wording restored | 2 |
   | 4015 old gantry name | 2 |
   | 4015 gantry moved 1.1 km north (nearest fix 353.4 m) | 2 |

7. Invariant check against the round-1 blueprint. For all 15 records the following are identical:
   - expected_ruling, amount, driver compensation, referrals, governing_clauses, difficulty,
     escalation_kind, arithmetic, trap and other_clauses;
   - gps build_recipe and measurements, the trip_record and amount_contested_sgd;
   - fare_breakdown, apart from 4015's one gantry name.

   Of the answer key, only 4014's rationale text changed.
8. `python3 -I tmp/count_plan.py build/plan.json` reports "problems: none" and TOTALS_MATCH True.
   `build/plan.json` and every file in `ref/` have the same sha256 as before the round.

The prototype output (`tmp/rd_r2/out`, `tmp/rd_r2/base_out`) and the recomputation printouts were
deleted after the run, so that no second answer key lies in the workspace. The commands above recreate
them. The run order is 1, then 2 for both directories (base from the backup), then 3 to 5.

## 5. Files changed

- `build/blueprint_rd.json`: records 4001, 4003-4011, 4013, 4014 and 4015 (the shared note), plus the
  edits above in 4005, 4008, 4010, 4013 (internal only), 4014 and 4015.
- `build/design_notes_rd.md`: section 7 appended.
- `build/revisions_rd_r2.md`: this file.
- `build/plan.json`: **not edited**. No planned ruling, difficulty, filer, mechanism or amount
  changed. Its 4015 target still names the gantry from the first plan ("after Braddell Road"). Like
  the round-1 Moulmein name, that is superseded by the blueprint.

**Warning for later rounds.** `build/blueprint_rd.json` is the source of truth. Re-running
`tmp/rd_r1/apply.py` or `tmp/rdbp/make_blueprint.py` would revert this round. To rebuild this round,
run `tmp/rd_r2/apply.py`, which starts from the round-1 backup in `tmp/rd_r2/bak/`.
