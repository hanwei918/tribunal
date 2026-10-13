# Revisions, ROUTE_DEVIATION blueprint, round 1 (critique_rd_r1.json)

Internal. This file applies `build/critique_rd_r1.json` to `build/blueprint_rd.json` (cases 4001-4015).
Policy in force: version 6, meaning the three base files plus POL-NS-11, POL-RD-14 and POL-NS-12.

## 0. Outcome in one paragraph

**Every planned ruling, amount, referral, governing-clause list and difficulty is unchanged.** No case
needed a "nearest honest alternative". The critic's two FIX verdicts (4006 and 4012) are both correct
against the policy text, and both are applied:

- 4006: only the claim text changes.
- 4012: the advisory facts change, so the mechanism changes. The answer does not.

Of the optional realism and robustness suggestions, five are applied and three are rejected (see
section 3).

Traces, fares, contested amounts and set counts are untouched in all 15 cases. A script asserted this
against the pre-revision copy.

Changed records: 4001, 4003, 4005, 4006, 4012, 4013, 4014.

## 1. Decision log

| Case | Critique item | Verdict on the critic | Decision |
|---|---|---|---|
| 4006 | FIX: REVERSAL not earned (nothing in the record contradicts either party) | Right | APPLIED (claim text) |
| 4006 | FIX: update derivation step 1 and the rationale | Right | APPLIED |
| 4012 | FIX: POL-RD-10(5) "does not cover the trip window" can escalate the expired closure the driver invokes, which gives two defensible answers | Right | APPLIED, with the changes listed in section 2.2 |
| 4012 | FIX: second RD-10(5) hook, shortest_lawful_alternative_km null ("lacks the field the clause requires") | Right | APPLIED (14.6 on both advisories) |
| 4012 | FIX: populate the field on advisory 02, or drop that advisory | Right | APPLIED (populated, kept as a distractor) |
| 4012 | FIX: keep the driver's and rider's statements; update setting, measurements and intent | Mostly right | APPLIED. The rider's wording is adjusted slightly (section 2.2) |
| 4012 | Avoid the "opposite carriageway at Eunos" variant | Right | FOLLOWED |
| 4001 | optional: move the stop request and reply before boarding | Sound | APPLIED, with different times |
| 4001 | optional: claim mentions the stop as "on the way" | Valid alternative | REJECTED |
| 4003 | optional: tie the meter to the exported trace in trip_completed | Sound | APPLIED |
| 4005 | optional: request and reply before boarding; MSG-005 typed from inside the mall | Sound | APPLIED |
| 4009 | optional: faster expressway speeds | Critic itself says leave otherwise | REJECTED |
| 4013 | optional: request before boarding; drop or quick-reply MSG-006 | Sound | APPLIED (MSG-006 dropped) |
| 4013 | optional: re-route the Orchard leg onto Orchard Boulevard | Critic: "only if the trace is retuned anyway" | REJECTED (trace not retuned) |
| 4014 | optional: phrase the evidence id as read off the dispute page | Sound | APPLIED |

## 2. FIX items

### 2.1 Case 4006 (PARTIAL_REFUND 2.00, rider, REVERSAL): applied

**Check against the policy and BRIEF.** BRIEF section 2 defines REVERSAL as "a party's story is
contradicted by the record". The old claim had four parts. The trace and record confirm each one:

- "long route": true. The route is 1.140 km longer than booked. That is only below the POL-RD-01 20 %
  test, which is not a contradiction.
- "CTE ERP but we never went on the CTE": true.
- "he used Upper Thomson": true.
- "usually 12-13": the record does not decide this either way.

The driver's statement is consistent with the trace. The critic is right that the label was not
earned.

**Change.** Only `dispute.claim_text` changes. It now reads: "Driver took a long way this morning,
went round by Yio Chu Kang, must be 4-5km extra. And my receipt got a CTE ERP 2 dollars but we never
went on the CTE at all, he used Upper Thomson. 18.74 for AMK to Novena, usually 12-13 only. Pls
refund 6."

The intent changes to match:

- Derivation step 1 now quotes the claimed 4-5 km against the measured 1.140 km.
- The arithmetic gains that comparison.
- The trap names the uncited 4-5 km.
- The other_clauses entry for POL-RD-08 is updated.
- The rationale says the 4-5 km claim is contradicted by the trace.

Yio Chu Kang is safe to name because the trace does use Yio Chu Kang Rd: it runs north to lat >
1.383 before turning west.

**Answer unchanged.** POL-RD-01 fails: 9.840 - 8.7 = 1.140 km, which is 13.10 %. POL-RD-09(4) refunds
the phantom ERP-G-046 line of 2.00 (nearest fix 1,843.9 m away). The POL-RD-10(8) carve-out applies.
The ruling stays PARTIAL_REFUND 2.00 with the billing-integrity referral.

### 2.2 Case 4012 (NO_ACTION, driver, REVERSAL): applied with changes

**Check against the policy.** POL-RD-10(5) escalates where "an exculpatory clause is invoked against a
cited artifact that is missing from the pool, or does not cover the trip window, or lacks the field the
clause requires".

The driver invokes POL-RD-03 ("PIE was closed at Eunos, got LTA notice"). The old EV-ADVIS-04012-01
was valid from 23:59 to 05:00, so it did not cover the 07:51-08:19 trip window. The limb therefore
reads directly onto the facts.

POL-RD-13 does not resolve this: it deals only with a MISSING advisory. POL-RD-03's own failure on
limb (b) does not displace RD-10(5) either. A careful reader could rule NO_ACTION or ESCALATE, which
breaks BRIEF section 6 ("exactly one defensible answer"; no case built on an unresolved tension
between clauses). The null shortest_lawful_alternative_km was a second RD-10(5) hook. The critic is
right on both counts.

**New facts (deciding).** EV-ADVIS-04012-01 is now:

- Type CLOSURE, road PIE.
- Segment: "PIE (towards Tuas) between the Adam Road exit and the Eng Neo Avenue exit, all lanes
  closed for expansion joint replacement; traffic diverted at the Adam Road exit".
- Geometry (1.3297, 103.815) to (1.3328, 103.8068).
- Valid 2026-10-04T05:00 to 11:00, issued 2026-10-01T15:00.
- shortest_lawful_alternative_km 14.6. The booked route never uses the closed section, so the shortest
  lawful alternative between the booked endpoints is the booked route itself.
- Same advisory_id and source_ref as before.

EV-ADVIS-04012-02 (TPE roadworks) is unchanged except that shortest_lawful_alternative_km is now 14.6.

The `route_planned` event now says the booked route leaves the PIE for Toa Payoh Lor 6 ("leaving the
PIE for Toa Payoh Lor 6"). The roads, 14.6 km, 21 min and ERP 0.00 are unchanged.

The admissibility notes for both advisories state the new validity and the stated field. The setting
and `extra_measurements` are rewritten.

**Where this differs from the critic's suggestion, and why:**

- **Exit names.** I used "Adam Road exit to Eng Neo Avenue exit" rather than "Adam Road exit to Bukit
  Timah Road exit". The PIE's Bukit Timah Road junction is far to the west, near Jalan Anak Bukit, so
  it would not fit coordinates about 1 km west of Adam Road. Eng Neo Avenue is the next junction west.
  As with every coordinate in this blueprint, this is placed from general knowledge, not surveyed.
- **Validity window.** I used 05:00-11:00 rather than 06:00-12:00. Both cover the trip with wide
  margins (04:45-11:15 with the 15-minute buffers, against 07:51:10-08:19:13). An early start reads
  more plausibly for a Sunday-morning full closure.
- **Type.** I used CLOSURE rather than ROADWORKS, so that a driver mistaking the notice for an "Eunos"
  closure is believable.
- **Rider's statement.** It now reads "The PIE from Tampines was open that morning, I take it every
  Sunday. Support already refunded me the extra." The original "The PIE was open that morning" would
  itself be partly contradicted now that a PIE closure is on file. The REVERSAL must fall on the
  driver alone.

**Reading the new facts (intent rewritten):**

- **POL-RD-01:** 19.320 - 14.6 = 4.720 km, which is 32.33 %. The deviation is established and not
  material. Unchanged.
- **POL-RD-03(a) fails.** The advisory names no segment or junction the optimal route traverses. The
  booked route leaves the PIE for Toa Payoh. The closed section's nearest point is 3,975.2 m from the
  dropoff, west of it. It is 3,331.4 m from every fix. The trace's westmost fix is at lng 103.843573;
  the advisory lies west of lng 103.815. RD-03's last sentence applies: "covering a corridor the
  optimal route never uses, does not exonerate anything".
- **POL-RD-03(b) and (c).** Limb (b) has no time at which the booked route would reach the closed
  section. Limb (c) fails: the actual TPE/CTE route never passes the closed section or rejoins the
  booked corridor after it.
- **Driver's account contradicted.** Nothing on file closes the PIE at Eunos. The only PIE notice
  concerns a section about 4 km beyond the booked exit.
- **EV-ADVIS-04012-02:** on the driver's own TPE road (nearest fix 0.3 m), not the booked route. It
  exonerates nothing. Unchanged.
- **POL-RD-10(5) not engaged.** The notice the driver relies on is present (COMPLETE, weight 1.0),
  covers the trip window, and carries every field RD-03 uses. Advisory 02 likewise.
- **POL-RD-13** does not apply: no advisory is MISSING.
- **POL-RD-10(7)** is not engaged: the notice supports no closure on the booked route.
- **POL-RD-02 (Decimal):** recomputed 3.80 + 0.75 x 14.6 + 0.28 x 21 + 0.80 = 21.43. The refund is
  26.93 - 21.43 = 5.50, which equals refund_issued_sgd and the contested 5.50.
- **Ruling:** NO_ACTION. On this driver-filed dispute it leaves the rider refunded (POL-GEN-03).
  governing_clauses stay [POL-RD-03, POL-RD-02, POL-RD-01].

**Residual reading risk, and why it does not give a second answer.** The advisory's `road` field is
"PIE", and the optimal route does use the PIE. A literal reader might say RD-03(a) passes on the road
name. That reading does not survive the rest of the clause:

- RD-03's own example ("a PIE closure at the Jalan Anak Bukit exit") and its last sentence make the
  location of the affected segment decisive.
- Limb (b) is keyed to when the vehicle "would have reached that segment", which never happens.
- Limb (c) requires the actual route to rejoin the optimal corridor "after" the affected segment,
  which never happens.

So the alternative is an error, not a second defensible answer. It is recorded as the trap, with its
figure. Misapplying RD-03 gives a justified excess of min(4.720, 1.30 x (14.6 - 14.6) + 1.00) = 1.00
km. The adjusted route is 15.6 km in 22.4 min (21 x 15.6 / 14.6 = 22.44, rounded to 22.4). Recomputed
3.80 + 11.70 + 6.272 + 0.80 = 22.572, so the refund would be 4.358, rounded up to 4.40. That would
wrongly return 1.10 to the driver.

The opposite-carriageway-at-Eunos variant was avoided, as the critic advised.

## 3. Optional items

- **4001, request before boarding: APPLIED, with different times.**
  - MSG-04001-002 is now sent at 10:11:40 and the driver's reply MSG-04001-003 at 10:12:00. Both fall
    after driver_arrived (10:11:20) and before trip_started (10:12:40).
  - The critic's 10:10:30 and 10:10:50 fell before the driver arrived, which would have had the driver
    typing while driving.
  - The text gains "later", so it reads "uncle later can singgah Jurong Point kejap? ...". The
    Malay words that carry the LANGUAGE_AMBIGUITY tag (singgah, kejap) are kept, along with the weight
    of 0.85.
  - POL-RD-04(b) is still met: the request comes 243 s before the J inbound fix at 10:15:43 (it was
    148 s).
  - Updated: the chat note's largest interval (525 s), derivation step 4, the rationale and
    `extra_measurements`.
- **4001, claim calls the stop "on the way": REJECTED.** The current claim follows the reversal that
  POL-RD-04's notes call the commonest: the rider asked in chat and has forgotten. The test is whether
  the system finds the omitted instruction. The current claim already contradicts the record, and the
  critic rates the change optional.
- **4003, trip_completed detail: APPLIED.** It now reads "Metered fare from the driver-app GPS trace
  for this trip (the exported trace): 17.60 km, 26 min." The trace source is DRIVER_DEVICE. This
  closes the argument that the platform's actual_distance_km is an independent POL-RD-07(ii)
  corroborator. Derivation step 4 is updated. The ruling stays ESCALATE (EVIDENCE, INDETERMINATE).
- **4005, request before boarding and MSG-005 from the mall: APPLIED.**
  - MSG-04005-003 (the rider's request, waypoint_hint unchanged) is now at 15:59:50 and the driver's
    "ok can" at 16:00:05. Both are before trip_started (16:00:20).
  - MSG-04005-005 is now "uncle queue abit long, 2 more min ah" at 16:19:30. The car is stationary at
    Northpoint then (16:16:26-16:22:26, speed 0).
  - MSG-006 is unchanged.
  - The request now comes 707 s before the J fix at 16:11:37 (it was 632 s). The chat note's largest
    interval is 1165 s.
  - DRIVER_COMPENSATION is unaffected: 0.75 x (20.570 - 14.20) = 4.7775, rounded up to 4.80.
- **4009, faster expressway speeds: REJECTED.** Any speed change moves the trace, duration, time_fare,
  total and contested amount, and the FULL_REFUND must equal the contested amount. The critic itself
  says to leave the case as it is otherwise. Speeds of 46-47 km/h fit a meter-padding long-hauler.
- **4013, request before boarding: APPLIED.**
  - The rider's request is now MSG-04013-002 at 14:33:40 ("ok coming. uncle can go by Bukit Timah
    Plaza first? ...", waypoint_hint unchanged). The driver's "ok" is MSG-04013-003 at 14:34:00.
  - The rider's 14:45:10 AYE question becomes MSG-04013-004.
  - The driver's 14:45:35 "missed the turn" message, typed at 48-56 km/h, is dropped.
  - message_count and chat_message_count are now 4, with ids contiguous.
  - The intent no longer relies on the dropped message. It now notes that the rider's 14:45:10 message
    matches the trace.
  - POL-RD-04(b) is met trivially, since the request precedes departure. POL-RD-14 is unaffected: the
    nearest fix is 3,058.9 m from the hint. The answer stays PARTIAL_REFUND 5.80.
- **4013, Orchard Rd alignment: REJECTED.** Moving the three Orchard waypoints changes the frozen trace
  (15.920 km), the duration and every dependent timestamp and figure. The critic makes it conditional
  on a retune that is not otherwise happening. The coordinates are approximate placements anyway; the
  design notes say every policy test runs on the fixes, not the road names. Known limitation: the
  westbound leg is drawn on the Orchard Rd alignment, whereas real westbound traffic would use Orchard
  Boulevard, about 150-200 m south. It has no policy effect.
- **4014, evidence id: APPLIED.** The claim now reads "please check the LTA advisory listed on this
  trip, EV-ADVIS-04014-01". The id stays, so the POL-RD-13 carve-out and POL-RD-10(5) still apply.
- **Not acted on:**
  - 4010: the driver's "ok noted" sent at 46 km/h. The critic proposed no fix; it reads as a
    quick-reply.
  - 4008: MSG-04008-007, sent at 28 km/h while pulling away. Not flagged.

## 4. Re-verification (run after the changes)

The scripts are in `tmp/rd_r1/` and the backups of the pre-revision files are in `tmp/rd_r1/bak/`.

1. `python3 tmp/rd_r1/apply.py` rebuilds `build/blueprint_rd.json` from the backup plus this round's
   changes.
2. `python3 tmp/rdbp/proto_gen.py tmp/rd_r1/out` rebuilt all 15 cases from the blueprint. It asserts
   every trace measurement and runs `common.make_case` (validate_case and lint_case) and
   `common.validate_key`. All 15 built.
3. `python3 ref/check_set.py tmp/rd_r1/out/cases tmp/rd_r1/out/gt.json --range 4001 4065` reported
   only the expected "both categories are required" failure (one category built).
4. `tmp/rdbp/verify_cases.py` recomputed every case from the case files alone, before and after the
   revision. The output is identical except for 4013's hint-carrying message id (MSG-04013-003 is now
   MSG-04013-002). All excesses, POL-RD-02 figures, gantry and hint distances and rulings are
   unchanged.
5. `python3 tmp/rd_r1/verify_r1.py tmp/rd_r1/out` ran 48 independent checks on the changed cases, from
   the case files only, with Decimal money and haversine at R = 6371.0088. All 48 pass. They cover:
   - 4012: window coverage with buffers, non-null RD-03 fields, the geometry distances and side of the
     trace, the route_planned wording, the POL-RD-02 figure equal to refund_issued equal to contested,
     and the trap figure.
   - 4001, 4005, 4013: chat order, request before boarding, gaps to the J fix, the notes' largest
     intervals and first/last times, and no driver message typed at speed.
   - 4013: the hint is never approached.
   - 4006, 4003, 4014: the texts.
6. Negative controls: each check fails when its fact is broken.
   - 4012 window ending 07:00: 1 failure.
   - 4012 shortest_lawful_alternative_km null: 2 failures.
   - 4012 geometry moved back to Eunos: 2 failures.
   - 4001 request moved to 10:19: 5 failures.
7. `python3 -I tmp/count_plan.py build/plan.json` gives output identical to the pre-revision plan
   ("problems: none", totals match). The 4012 mechanism was kept within the planner's 3-6 sentence
   rule.
8. Invariant check against the backup: for all 15 cases the following are identical:
   - expected_ruling, amount, driver compensation, referrals, governing_clauses, difficulty and
     escalation_kind;
   - amount_contested_sgd, gps build_recipe and fare_breakdown.

The prototype output (`tmp/rd_r1/out`, `tmp/rd_r1/base_out`) and the recomputation printouts were
deleted after the run, so that no second answer key lies in the workspace. The commands above recreate
them.

## 5. Files changed

- `build/blueprint_rd.json`: records 4001, 4003, 4005, 4006, 4012, 4013 and 4014.
- `build/plan.json`: only the 4006 and 4012 entries.
  - 4006: filer_story, and one clause of the mechanism.
  - 4012: mechanism, messy_evidence[].why, counterparty_story and targets.advisory_01_valid.
  - Ruling, difficulty, filer, channel and amounts are unchanged. The NS entries were checked
    byte-identical and the file was written atomically.
- `build/design_notes_rd.md`: section 6 appended.
- `build/plan_notes.md`: not edited. Its 4012 paragraph (the expired-closure mechanism) and its 4006
  "long detour" wording are superseded by this file and by `plan.json`.

**Warning for later rounds.** `build/blueprint_rd.json` is now the source of truth. Re-running
`tmp/rdbp/make_blueprint.py` regenerates from the old specs and would silently revert this round. To
rebuild, run `tmp/rd_r1/apply.py`, which starts from the pre-revision backup.
