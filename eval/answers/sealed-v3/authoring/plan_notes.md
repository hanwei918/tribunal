# Plan notes: tribunal-sealed-v3 (internal)

Companion to `build/plan.json`. Policy in force is version 6: the three base files plus
POL-NS-11 (0001), POL-RD-14 (0002) and POL-NS-12 (0003). Every outcome below was derived
from that text alone. Arithmetic was run with `decimal.Decimal` in `tmp/plan_calc.py`;
the set counts were checked with `tmp/count_plan.py build/plan.json` (TOTALS_MATCH True).

## 1. Set totals as planned

| | ROUTE_DEVIATION (4001-4015) | NO_SHOW_CHARGE (4051-4065) | Total | Target |
|---|---|---|---|---|
| FULL_REFUND | 2 (4004, 4009) | 4 (4051, 4056, 4060, 4065) | 6 | 6 |
| PARTIAL_REFUND | 5 (4002, 4006, 4011, 4013, 4015) | 0 | 5 | 5 |
| NO_ACTION | 3 (4001, 4008, 4012) | 3 (4054, 4059, 4063) | 6 | 6 |
| DRIVER_COMPENSATION | 1 (4005) | 5 (4052, 4055, 4057, 4061, 4064) | 6 | 6 |
| ESCALATE | 4 (4003, 4007, 4010, 4014) | 3 (4053, 4058, 4062) | 7 | 7 |
| of which EVIDENCE | 3 (4003, 4010, 4014) | 2 (4053, 4062) | 5 | 5 |
| of which POLICY | 1 (4007) | 1 (4058) | 2 | 2 |
| EASY | 3 (4004, 4008, 4011) | 4 (4052, 4057, 4060, 4065) | 7 | 7 |
| HARD | 5 (4002, 4005, 4007, 4009, 4015) | 6 (4055, 4056, 4058, 4059, 4061, 4064) | 11 | 11 |
| REVERSAL | 4 (4001, 4006, 4012, 4013) | 3 (4051, 4054, 4063) | 7 | 7 |
| INDETERMINATE | 3 (4003, 4010, 4014) | 2 (4053, 4062) | 5 | 5 |
| DRIVER filer | 4 (4005, 4010, 4012, 4014) | 7 (4052, 4053, 4057, 4058, 4059, 4061, 4064) | 11 | >= 10 |

Why no PARTIAL_REFUND in NO_SHOW_CHARGE: the only no-show clause that licenses PARTIAL_REFUND is
POL-NS-08, and the same sentence that mentions it sends the case to POL-NS-09, which is terminal.
A no-show PARTIAL_REFUND would therefore rest on an unresolved tension, so all five partials are
route-deviation cases (POL-RD-02 arithmetic in five different settings).

Ordering: within each category no two adjacent cases share a ruling, and no difficulty runs
longer than two, so the case number carries no signal.

Coverage: every clause of both category files is named as deciding or as the trap
(POL-RD-01..14, POL-NS-01..12). Amendments decide 4013 (POL-RD-14), 4055 (POL-NS-11) and
4061 (POL-NS-12); in each, the base text alone would have escalated. POL-GEN-01 near-synonym
traps: 4015 (prior_deviation_flags), 4013 (prior_disputes_filed), 4051 (rider
prior_no_show_flags), 4055 (driver prior_no_show_flags), 4058 (reverse trap: the lifetime
counter looks clean while the 30-day counter trips). POL-GEN-02 caps decide 4003, 4053, 4062
and are deliberately kept harmless (>= 0.75 on deciding artifacts) everywhere else.
POL-GEN-08(1) is not used: no case naturally alleges damage, harassment or discrimination.

Issue codes planned: GPS_GAP (4003 long inside, 4009 short outside, 4053 straddling),
LOW_SAMPLE_RATE (4061), GPS_DRIFT (4062), CLOCK_SKEW (4008, chat vs trip_record),
TRUNCATED_LOG (4064), MISSING chat log (4009), STALE_SNAPSHOT (4015), CROSS_SOURCE_CONFLICT
(4059), ADVISORY_UNCORROBORATED (4052), plus UNREAD_MESSAGE (4051), LANGUAGE_AMBIGUITY (4001),
CONTENT_REDACTED (4063), PARTIAL_RECORD (4010, 4053, 4055, 4061, 4062).

## 2. Rules every builder must keep

1. **Weights** are the product of `no_show.json` `integrity.weights` for the codes on the
   artifact (both categories): e.g. GPS_GAP straddling 0.6 x PARTIAL_RECORD 0.75 = 0.45;
   GPS_DRIFT 0.5 x PARTIAL_RECORD 0.75 = 0.375, written 0.38 because `common.weight_for` rounds
   to 2 dp; LOW_SAMPLE_RATE 0.8 x PARTIAL_RECORD 0.75 = 0.6.
2. **rider_track tagging rule (no-show only).** An empty `rider_track` on a NO_SHOW_CHARGE trace
   is tagged PARTIAL_RECORD (the pre-pass reports the NS-08(b) rider_track limb). It is empty
   exactly in 4053, 4055, 4061, 4062; every other no-show case carries a non-empty rider_track as
   described in its targets. Route-deviation traces carry `rider_track: []` with no tag.
3. **Profile counters are never null** where a clause reads them: deviation_flags_90d,
   completed_trips_90d, deviation_claims_60d(_substantiated) on every RD case;
   no_show_terminations_30d, completed_trips_30d, no_show_disputes_30d and both
   disputes_with_counterparty_90d (set 0) on every NS case. A null anti-farming counter would make
   POL-NS-07 undecidable and break every DRIVER_COMPENSATION.
4. **Fare cents.** Billed distances in the plan are multiples of 0.04 km and minutes are whole,
   so distance_fare and time_fare are exact to the cent (`common.metered_lines` gives the same
   lines); total_charged is the Decimal sum of the lines. trip_record.actual_distance_km is the
   trace figure rounded to 1 dp (a copy), and fare distance_charged_km is the trace figure rounded
   to 2 dp (a copy), so tune each route until round(trace_distance_km, 2) equals the planned
   billed_km - except 4005, whose billed 14.20 is the quote basis and whose trace has the hard
   window (20.534, 20.600]. If a figure must move, recompute everything that depends on it and
   keep these invariants: 4004's excess over the quote is a multiple of 0.05 and equals the
   contested amount; 4009's total is a multiple of 0.05 and equals the contested amount; 4012's
   refund_issued_sgd equals the recomputed POL-RD-02 payable; every PARTIAL stays below the
   contested amount and below 90% of charged_total; every threshold margin named in section 3
   survives.
5. **Rounding and FULL_REFUND.** fare_model rounds every payable RD amount UP to 0.05, including
   RD-11 amounts. Every planned FULL_REFUND amount (6.50, 27.50, and the no-show fee lines) is
   either already a multiple of 0.05 or is a no-show fee refunded "in full" (6.61), so the
   rounding rule and "amount == amount_contested_sgd" never collide.
6. **Advisories.** A MISSING advisory is minted with an id in every case that has no real one.
   Only 4014 cites the missing id; nobody else mentions an id, so POL-RD-10(5) is engaged only in
   4014. 4002, 4012 (two) and 4059 carry COMPLETE advisories that matter; 4052's is IMPAIRED and
   irrelevant.
7. **No names, phones or plates** (POL-GEN-08(4)). Cars by colour and model. In 4063 the rider
   types a phone number and the record shows it masked (CONTENT_REDACTED) - do not write digits.
8. **Forbidden words** in case text include "difficulty", "rationale", "sealed", "canary"; write
   "trouble finding you", never "difficulty finding you".
9. Trip timestamps are SGT (+08:00) and causally ordered. No case uses CLOCK_SKEW on a
   TRIP_RECORD.

## 3. Case by case

### Route deviation

**4001 - NO_ACTION (rider, REVERSAL).** POL-RD-04: the rider's message (Malay "singgah ... kejap",
waypoint_hint = Jurong Point) is from the rider, sent before leaving the corridor, and names a
place; the trace passes within about 40 m and stops 3 min. The detour is an out-and-back spur that
leaves and rejoins at one junction, so the excluded excess is the spur's own measured length
(1.90 km) and needs no geocoding. Raw excess 2.16 km (29.2%) would establish a deviation; after
exclusion about 0.26 km remains, failing both RD-01 tests. Unique: RD-01 fails on the adjusted
figure, so RD-02 never runs; RD-09(3) bars ERP refunds on a rider-caused detour (none charged);
metered billing covered the full trace, so RD-04's compensation limb (shortfall > 1.0 km) is not
met. The LANGUAGE_AMBIGUITY tag (0.85) is above the floor and the place is fixed by the field.
Invariant: the trace outside the spur may exceed the optimal by at most 0.5 km.

**4002 - PARTIAL_REFUND 6.15 (rider, HARD).** POL-RD-03 limbs (a) segment on the optimal route,
(b) validity 23:30-05:00 covers 00:40, (c) trace leaves before and rejoins after, all hold. Cap
= min(9.40, 1.30 x (15.2 - 13.0) + 1.00) = 3.86 km, so adjusted optimal 16.86 km, duration
17 x 16.86 / 13.0 = 22.048 -> 22.0 min. Remaining 5.54 km = 32.9% of 16.86 and > 0.8 km:
deviation established on the adjusted optimal (no RD-03/RD-01 tension, because the remaining
excess clearly passes RD-01). Not material (32.9% < 50%, 5.54 < 8.0). RD-02: 29.52 - 23.405 =
6.115 -> 6.15 < 12.00 contested and < 90% of charged. No ERP (night), so RD-09(1)/(2) have
nothing to settle. Unique: the only exoneration on file is capped by its own formula.

**4003 - ESCALATE, EVIDENCE (rider, INDETERMINATE).** POL-RD-07(a) and (b) fire inside the
disputed segment (450 s gap; about 7 km straight-line jump). Even the driver-favourable bridged
reading (17.60 vs 13.5 km, 30.4%) cannot establish the deviation alone (RD-07(ii)), and none of
the four independent corroborators exists: no driver admission (counterparty_statement null,
chat routine), no ERP charged (Sunday), no counterparty admission, actual_distance_km and billed
distance are copies of the trace. RD-07(iii) and RD-10(3) fire; RD-10(1) also fires (cap 0.6).
No rescue: RD-13 says in terms it does not displace RD-07. Trigger: RD-10(3). The deciding fact
(the route through the tunnels) cannot be settled on the record.

**4004 - FULL_REFUND 6.50 (rider, EASY).** UPFRONT_QUOTE with quoted_fare_sgd 17.90 and charged
24.40 (platform re-rated after the route change); no ERP, airport or waiting line. RD-11(a)
refunds the excess 6.50 in full = contested 6.50; RD-02 is barred on upfront fares. Unique:
RD-11 is the only clause that runs on this fare model; the excess is exact to 0.05. The careless
RD-02 path gives 5.15 (PARTIAL), so the case discriminates.

**4005 - DRIVER_COMPENSATION 4.80 (driver, HARD).** Rider-requested, corroborated detour
(waypoint within 50 m, request before leaving the corridor) on an UPFRONT_QUOTE trip. RD-11 says
the rider-requested detour "is compensated under POL-RD-04" (mandatory, so RD-04's "may" is not
discretionary here). RD-04: billed 14.20 km vs trace 20.57 km, shortfall 6.37 > 1.0 km;
0.75 x 6.37 = 4.7775 -> 4.80, under the 15.00 cap. amount_sgd = driver_compensation_sgd = 4.80
(POL-GEN-03). Unique: no rider refund is possible (upfront, quote charged exactly) and no
other clause licenses DRIVER_COMPENSATION. Build window: trace in (20.534, 20.600].

**4006 - PARTIAL_REFUND 2.00 (rider, REVERSAL).** RD-01 fails on the trace: 1.15 km is > 0.8 km
but 13.2% < 20%. RD-01 itself preserves an RD-09(4) refund; the ERP line "CTE (southbound) after
Braddell Road" 2.00 is more than 250 m (planned: > 1 km) from every fix, so it is a gantry the
trace never passes: refunded in full, 2.00 (already a multiple of 0.05), with a billing-integrity
referral. RD-10(8) expressly excludes a line refunded under RD-09(4). Rider profile:
deviation_claims_60d 1, so RD-08's extra-corroboration factor is not engaged. Unique: the only
money the text produces is the phantom line.

**4007 - ESCALATE, POLICY (rider, HARD).** A cancellation_fee 4.50 line sits on a completed trip;
trip_record has no cancellation (status COMPLETED, cancelled_at and reason code null, no event).
RD-09(4) covers only gantry and airport-surcharge lines, so RD-10(8)'s exception does not apply
and the Judge "must NOT issue a final ruling". Facts are clear; the text requires a person.
Interpretive note: base, distance, time, surge and platform-fee lines are not "unmatched" - their
counterpart is the completed trip itself (RD-02 runs on them every day); only an event-type line
(cancellation, waiting, gantry, surcharge) can lack a counterpart. The deviation (46.8%, not
material) is clean so that the careless answer is a tidy RD-02 partial of 9.25.

**4008 - NO_ACTION (rider, EASY).** RYDE_POOL; trip_record identifies the matched itinerary
(pool_matched event naming the co-rider stop; optimal_route_source MATCHED_POOL_ITINERARY;
optimal_distance_km 11.6), so RD-12's incomplete-record limb does not fire. Trace 12.12 km:
0.52 km (4.5%) over the matched baseline fails RD-01. The rider's 3.22 km is measured against
solo_optimal_distance_km and fails on that ground. CLOCK_SKEW on the chat (47 s) touches nothing
deciding and is far below RD-10(4)'s 10 minutes. Fare is METERED (pool discount as
promo_discount 2.50) so RD-12, not RD-11, is the deciding clause.

**4009 - FULL_REFUND 27.50 (rider, HARD).** Excess 8.66 km (84.1%) is established and MATERIAL
on both tests, so RD-06 is consulted; deviation_flags_90d = 4 >= 3 is a pattern; RD-06(b) then
licenses FULL_REFUND of charged_total, with no pass-through line to carve out (no ERP, toll or
airport line exists), so the amount is exactly 27.50 = contested; RD-06(c) referral. The ruling
states the RD-02 figure 10.45 beside it. GPS_GAP 75 s in the pickup carpark is outside the
disputed segment and below every RD-07 limb (weight 0.85 >= 0.70). The missing chat matters to
nothing: nobody asserts an instruction. Above 8.00, the amount is held for release under
POL-GEN-05 - an execution matter, not an escalation.

**4010 - ESCALATE, EVIDENCE (driver, INDETERMINATE).** dropoff_amended_at is set and both
amended_optimal fields are null. RD-05 says the clause cannot be run, RD-10(5) applies and no
substitute figure may be derived; RD-10(5)'s own example is exactly this. The deciding fact (the
optimal route between the amended endpoints) is absent from the record; measuring against the
booked optimal would charge the driver for a destination change the rider made. Trigger:
RD-10(5).

**4011 - PARTIAL_REFUND 4.60 (rider, EASY).** Plain RD-01/RD-02: 3.52 km (33.8%), not material;
no exculpatory clause invoked and no traffic cause asserted. 22.32 - 17.72 = 4.60 < 6.00.

**4012 - NO_ACTION (driver, REVERSAL).** The deviation (4.72 km, 32.3%) is established on a clean
trace. RD-03(b) fails: the closure's window ended 05:00 (05:15 with the buffer) and the vehicle
reached the segment around 07:50. The second advisory (ROADWORKS) is on a road the optimal route
never uses. RD-02 = 26.93 - 21.43 = 5.50, exactly the refund_issued_sgd. The driver's claim to
have the 5.50 returned is not supported: NO_ACTION, leaving the rider refunded (POL-GEN-03
party-relative). Unique because the platform's refund equals the policy figure, so the driver is
neither partly right nor owed anything.

**4013 - PARTIAL_REFUND 5.80 (rider, REVERSAL).** The instruction meets RD-04(a)-(c); the trace
never comes within 200 m of the waypoint (planned about 2 km) and never travels a requested road,
so POL-RD-14 applies: no exclusion, decided under RD-01/RD-02 on the trace as measured, and
RD-10(7) is not engaged (that is confined to partial corroboration). Base text (v5 without
0002) would have treated this as RD-10(7)'s own example and escalated; v6 rules. 24.66 - 18.88 =
5.78 -> 5.80 < 8.00. GEN-01: prior_disputes_filed 9 is context only; deviation_claims_60d 2.

**4014 - ESCALATE, EVIDENCE (driver, INDETERMINATE).** Deviation established (39.7%) on a clean
trace; the driver invokes RD-03 and cites EV-ADVIS-04014-01 by id; that artifact is MISSING.
RD-10(5) fires ("an exculpatory clause is invoked against a cited artifact that is missing"), and
RD-13(1) says in terms it does not narrow RD-10(5) where the party cites the missing identifier.
Contrast 4015, where the same kind of assertion is uncited and is simply discarded.

**4015 - PARTIAL_REFUND 15.75 (rider, HARD).** Material (55.4%) so RD-06 runs: 1 flag in 90 days,
0.24% of 412 trips - no pattern (prior_deviation_flags 7 is the lifetime near-synonym, POL-GEN-01).
The driver's ECP accident is uncited and the advisory is MISSING: RD-13(2), deviation stands,
no RD-10(5). RD-02 with surge 1.3 from fare_breakdown and 0.00 on-route ERP: recomputed
27.3005, refund 43.04 - 27.3005 = 15.7395 -> 15.75 < 18.00 and < 90%. The 3.50 off-route ERP is
inside that figure (RD-09(1)). Wrong paths land elsewhere: no surge 21.90, ERP added 19.25 (both
exceed the contested 18.00), uplift 43.04, or ESCALATE. STALE_SNAPSHOT is on the rider profile,
which decides nothing (excess above 30%).

### No-show

**4051 - FULL_REFUND 6.61 (rider, REVERSAL).** NS-04: (a) two locating messages in the window;
(b) no driver post within 120 s of either and in_app_calls empty (the driver's "I called twice" is
contradicted); (c) 7 of 8 qualifying rider fixes within 100 m. NS-04 displaces NS-01/07 (NS-07:
"no clause from NS-03 to NS-06 displaces it"), and the refund carries no compensation. NS-09(d)
reads no_show_disputes_30d (1), not prior_no_show_flags (5). UNREAD_MESSAGE 0.85 stays above the
floor; NS-04 does not require the message to be read.

**4052 - DRIVER_COMPENSATION 3.60 (driver, EASY).** NS-10(g): the rider cancelled at 270 s of an
in-geofence dwell, past free_wait 180; the fee stands and NS-07 pays 80% of 4.50. (f)'s exceptions
are excluded by (g). The IMPAIRED congestion advisory is irrelevant (NS-06(i) is not in play).

**4053 - ESCALATE, EVIDENCE (driver, INDETERMINATE).** The dwell to the cancellation (200 s vs
180 s) can be proved only by continuity across a 170 s gap that straddles the cancellation:
NS-08(b) policy-impairs the sole carrier, so NS-08's closing sentence and NS-09(e) escalate; the
0.45 weight also trips NS-09(a). No rescue: BUTTON marker (NS-12 needs GPS_AUTO), no other
position carrier (a call record and a chat line place nobody). The deciding fact is genuinely
unknown, not merely discounted.

**4054 - NO_ACTION (rider, REVERSAL).** NS-10(f): a rider cancellation after grace is chargeable
"whether or not the driver had arrived" unless an exception is on the record; all four are
checked and none is met (movement toward pickup within grace after a 40 s U-turn; the ETA+180 s
limb cannot have elapsed at 6 min 10 s of a 9 min ETA; no request to cancel; vehicle as booked).
NS-07 applies only under NS-01 or NS-10(g), so there is no compensation and the ruling is NO_ACTION.

**4055 - DRIVER_COMPENSATION 3.60 (rider, HARD).** NS-04 (a) and (b) hold but rider_track is
empty, so (c) is undecidable; POL-NS-11 says NS-04 cannot exonerate, the empty track neither
impairs the driver's trace nor engages NS-08(b)/NS-09(e), and the case is decided on the
driver's evidence: in radius at the pin, 340 s >= 180 s, RIDER_NO_SHOW after the dwell. NS-01
holds, no clause NS-03..06 displaces it (driver inside the radius, so NS-03 is out), anti-farming
clean (2 of 121), NS-07 pays 3.60. Ruling DRIVER_COMPENSATION, not NO_ACTION (GEN-03, NS-07).
Base text: NS-04 would label the trace NS-08(b)-impaired and the case could escalate.

**4056 - FULL_REFUND 4.50 + driver_compensation 2.25 (rider, HARD).** Stationary 380 s at about
210 m from the pin: outside the 120 m radius, inside 400 m, dwell >= free_wait 300, so NS-02
yields to NS-03 and the fee is refunded in full. Every locating message was answered within
120 s (NS-04 out), nobody named an entrance, wing or block, and registered_pickup_points = 3:
NS-03(ii) goodwill 50% x 4.50 = 2.25, platform-funded, independent and not netted (GEN-03).
venue_id match corroborates same-venue; the 400 m test decides alone anyway.

**4057 - DRIVER_COMPENSATION 3.20 (driver, EASY).** Clean NS-01: 420 s in radius against the
record's free_wait 240, two unanswered calls, no rider message, RIDER_NO_SHOW; anti-farming 1 of
168. NS-07: 80% of 4.00 = 3.20.

**4058 - ESCALATE, POLICY (driver, HARD).** NS-01 is satisfied on clear facts (570 s in the
150 m airport radius, threshold 480 met, the rider's message answered within 50 s, rider 350 m
away). NS-07's anti-farming check trips on both limbs (5 >= 4; 5/54 = 0.093 > 0.08), so
compensation is withheld and NS-09(d) escalates with an instruction to refund the rider; the
pipeline moves no money. This is policy, not evidence. The lifetime prior_no_show_flags = 1 must
not be read instead.

**4059 - NO_ACTION (driver, HARD).** NS-06(i): KERB_RESTRICTION advisory (COMPLETE, covering
road and window) lets the 60 s and 75 s in-geofence intervals be summed (driver never beyond
about 260 m); 135 s < 180 s (even generous boundary counting stays below 160 s). NS-06(ii): the
advisory never excuses the shortfall. Fee not chargeable; the driver's claim fails; NO_ACTION
leaves the rider refunded. CROSS_SOURCE_CONFLICT (0.4) is on the driver profile, which decides
nothing in this outcome.

**4060 - FULL_REFUND 6.61 (rider, EASY).** NS-10(a): 165 s after accepted_at, inside the 180 s
grace, "whatever the driver's position"; NS-10(c) refunds the fee charged in full (the gross
line), no compensation.

**4061 - DRIVER_COMPENSATION 4.00 (driver, HARD).** POL-NS-12: GPS_AUTO, platform arrival event
stating its geofence test, wait_timer_started and wait_timer_expired before termination; the
termination is past no_show_threshold 420. The sparse, accuracy-less export (0.6) is weighed only
for contradiction and has no fix outside 120 m or moving during the window. NS-01 holds; NS-07
pays 80% of the NET 5.00 (resolution_rule; never the 7.35 gross) = 4.00. Base text would have
escalated under NS-08(b)/NS-09(e).

**4062 - ESCALATE, EVIDENCE (rider, INDETERMINATE).** NS-08(a)-(d) are not engaged, so this is
not an NS-08 escalation; but GEN-02(2) caps confidence at the deciding carrier's weight, 0.38,
and every possible ruling (arrival and dwell, NS-03 wrong face, NS-02 never arrived) rests on that
one drifting trace. Below 0.70: NS-09(a). No rescue: BUTTON marker, NS-04 out (reply in 40 s),
no rider_track.

**4063 - NO_ACTION (rider, REVERSAL).** NS-10(d): completed trip, dwell before boarding measured
from the first qualifying fix 08:02:20 to boarding 08:08:45 = 385 s > 180 s; the waiting line
stands. No cancellation fee on the trip. CONTENT_REDACTED (0.8) sits on a chat that decides
nothing.

**4064 - DRIVER_COMPENSATION 4.40 + referral (driver, HARD).** NS-05: at the arrival tap the
matching fix (no skew) is 650 m away at 38 km/h - false on both triggers. Recomputed clock from
19:07:50 gives 310 s >= 180 s, so limb (iii): the false marker does not defeat the fee, NS-01 is
read on the recomputed clock and holds, NS-07 pays 80% of 5.50 = 4.40, and the false-arrival
event is recorded in referrals. NS-04 fails on (b) (recorded call) and (c) (rider 1.1 km away),
so the truncated chat (0.6, NS-08(c)) cannot change anything.

**4065 - FULL_REFUND 8.00 (rider, EASY).** Fee and free wait from platform_policy (AUTHORED-V1:
8.00, 300 s). Dwell 95 s, short of 300 (and of any default): NS-06 strict liability, full refund,
no compensation. The driver's crowding excuse cites no advisory and NS-06(ii) would not excuse a
shortfall anyway.

## 4. Points where the brief and the policy text needed care

- None of the brief's statements disagree with the policy files. Two readings the builders must
  hold to: (1) the fare_model's round-up rule covers RD-11 and RD-06 amounts too, which is why
  every planned FULL_REFUND is a multiple of 0.05 or a no-show fee refunded in full; (2) for a
  driver filer whom the policy proves right, GEN-03 offers two vocabularies (FULL_REFUND of the
  contested deduction versus DRIVER_COMPENSATION), so no driver-filed case is planned where the
  driver is simply right about a deduction; driver filers win only through a clause that names
  DRIVER_COMPENSATION (RD-04, NS-07, NS-10(g)).
- POL-RD-04's compensation limb says "may be granted"; 4005 reaches it through RD-11's
  mandatory "is compensated under POL-RD-04 instead", so the outcome is not discretionary.
