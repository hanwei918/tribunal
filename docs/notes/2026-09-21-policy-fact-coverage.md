# Policy fact coverage — 2026-09-21

What deterministic facts would a judge need in order to apply each of the 24 policy clauses, and
which of those does the pipeline produce today?

This document is a survey. It changes no code.

## Method and status definitions

Every claim below was checked against the real files with Python; nothing is asserted from reading
alone. The 24 clause rules were read in full from `policy/general.json` (3), `policy/no_show.json`
(9) and `policy/route_deviation.json` (12). The pipeline's current output was read from
`tribunal/facts.py` and `tribunal/brief.py`, and the corpus inputs were counted directly.

| Status | Meaning |
|---|---|
| **AVAILABLE** | `facts.py` already computes it and the brief carries it, **or** it is a plain payload field a judge can read directly and no computation is needed. |
| **DERIVABLE** | The inputs exist in the corpus, but nothing computes the fact yet. The payload fields the computation would read are named. |
| **UNSUPPORTED** | The corpus does not carry the inputs at all. No amount of computation fixes this. |

**A clause's status is the least-satisfied status among the facts it needs.** If any input it
requires is absent, the clause is UNSUPPORTED; otherwise, if any fact it needs is not yet computed,
it is DERIVABLE; otherwise AVAILABLE.

`facts.py` today exposes `haversine_m`, `distances_to_point`, `qualifying_fixes`,
`longest_qualifying_run`, `track_summary`, `elapsed_seconds`, `driver_points` and `rider_points`.
`brief.py` emits exactly three derived blocks — `driver_track`, `rider_presence`, `arrival` — and the
same three for every case, ROUTE_DEVIATION included.

## 1. Clause-by-clause coverage

| Clause | Title | Deterministic facts it needs | Status of each | Clause |
|---|---|---|---|---|
| POL-GEN-01 | Party profiles are credibility weighting only | The nine whitelisted profile counters, and the near-synonym pairs `prior_no_show_flags` / `prior_deviation_flags` distinguished from the trailing-window counters | AVAILABLE — all are scalar fields on the `RIDER_PROFILE` and `DRIVER_PROFILE` payloads (present on 29/29 each); no computation needed | **AVAILABLE** |
| POL-GEN-02 | Admissibility weight, disclosure, and how impairment enters confidence | Per-artifact `weight_multiplier` and `issues`; `bundle_integrity_score` = the **mean** weight across the bundle; the min/max weight among the artifacts carrying the deciding fact | weights AVAILABLE; issues AVAILABLE; **mean weight NOT computed** (`admissibility.weight_multiplier` on every artifact); min/max over the deciding set AVAILABLE once the set is chosen | **DERIVABLE** |
| POL-GEN-03 | Ruling vocabulary, party-relative outcomes and compound rulings | `fare_breakdown.payment_status` and `refund_issued_sgd` (the present state); `dispute.amount_contested_sgd`; the ruling value itself | AVAILABLE — all plain payload fields; no computation needed | **AVAILABLE** |
| POL-NS-01 | Baseline chargeable no-show | (a) the arrived event time; (b) the first qualifying in-geofence fix relative to it; (c) the continuous dwell vs `minimum_dwell_sec`; (d) `cancellation_reason_code` in the permitted set and no boarding event; the fee = **GREATER** of the zone-class fee and the vehicle-tier fee | (a) AVAILABLE (`trip_record.arrived_at`); (b) AVAILABLE (`derived.arrival.dwell_start_offset_sec`); (c) AVAILABLE (`longest_qualifying_run.duration_sec` vs the policy threshold); (d) AVAILABLE (`cancellation_reason_code`, `started_at`); **the GREATER-of fee NOT computed** (`trip_record.pickup_zone_class`, `trip_record.vehicle_type`, `fee_schedule.zone_class_fee_sgd`, `fee_schedule.vehicle_tier_fee_sgd`) | **DERIVABLE** |
| POL-NS-02 | Arrival geofence and GPS proximity test | At least 3 consecutive qualifying fixes; the count of qualifying in-radius fixes in the 15 minutes **preceding the cancellation**; a stationary run within 400 m of the pin | ≥3 consecutive AVAILABLE (`longest_qualifying_run.fix_count`); **15-minute windowed count NOT computed** (gps `points[].ts`, `trip_record.cancelled_at`, the arrival radius and accuracy filter); **400 m run NOT computed** (the primitive is radius-parameterised but the pipeline only ever runs it at the arrival radius) | **DERIVABLE** |
| POL-NS-03 | Wrong-entrance and wrong-block arrival | A stationary run at ≤400 m from the pin but **outside** the arrival radius; the venue_id corroboration; `registered_pickup_points`; the 50 % goodwill = rate × cancellation fee; chat-based fault allocation | **400 m run NOT computed** (gps `points`, `trip_record.pickup`); venue_id AVAILABLE — fixes carry `venue_id` on 228 fixes in 6 cases (109, 201, 205, 206, 209, 214) and `trip_record.pickup.venue_id` is set in 9 of 29 cases, with the clause's own rule for the null case; `registered_pickup_points` AVAILABLE; **goodwill arithmetic NOT computed** (`fee_schedule.pin_ambiguity_goodwill_rate`, `fare_breakdown.cancellation_fee`); chat AVAILABLE (`chat_log.messages`) | **DERIVABLE** |
| POL-NS-04 | Rider contact unanswered by driver | A rider locating/coordinating message during the waiting window; the driver's reply gap vs 120 s; an in-app call; rider fixes inside the presence radius for the **majority** of qualifying fixes across the window | rider message AVAILABLE (`chat_log.messages[].sent_at/sender/text`); **120 s reply gap NOT computed** (`messages[].sent_at`, `trip_record.in_app_calls[].placed_at`); in-app calls AVAILABLE; **windowed majority NOT computed** (rider track `points[].ts`, `trip_record.cancelled_at`, the presence radius) | **DERIVABLE** |
| POL-NS-05 | False arrival marker | The driver's distance from the pin **at the arrived_at timestamp**; the speed at that moment; the recomputed clock from the first qualifying in-geofence fix; whether any qualifying fix exists | **nearest-fix lookup NOT computed** (gps `points[].ts`, `trip_record.arrived_at`, `points[].speed_kph`); recomputed clock AVAILABLE (`longest_qualifying_run.first_ts`); existence AVAILABLE (`qualifying_fix_count`) | **DERIVABLE** |
| POL-NS-06 | Waiting-period shortfall and premature cancellation | The effective dwell vs the minimum; dwell accumulated across separate in-geofence intervals with the driver never more than 300 m from the pin; an advisory whose geometry covers the pickup road and whose window covers the waiting period | dwell AVAILABLE (`duration_sec` vs the threshold); **multi-interval accumulation NOT computed** (gps `points[].ts`, distances to the pin); advisory AVAILABLE where populated — `intersects_route`, `overlaps_trip_window`, `overlap_minutes`, `geometry` (a bounding box) are precomputed, and the clause's own rule covers a MISSING advisory | **DERIVABLE** |
| POL-NS-07 | Driver compensation on a verified rider no-show | POL-NS-01 satisfied; compensation = rate × cancellation fee; the anti-farming ratio `no_show_terminations_30d` / `completed_trips_30d` with the ≥4 and >0.08 tests | POL-NS-01 blockers inherit; **compensation arithmetic NOT computed** (`fee_schedule.driver_compensation_rate`, `fare_breakdown.cancellation_fee`); **the ratio NOT computed** (`driver_profile.no_show_terminations_30d`, `driver_profile.completed_trips_30d`) | **DERIVABLE** |
| POL-NS-08 | Evidence integrity: clock skew, trace gaps and truncated chat | Clock skew = \|arrived_at − nearest fix\| > 90 s; start/termination agreement within 90 s; a sampling gap > 120 s inside the waiting window; fewer than 6 fixes in that window; an omitted rider track; chat `msg_id` sequence gaps and a >5 min gap spanning the arrival marker; message count vs `chat_message_count`; the fare defect test | **skew and cross-artifact agreement NOT computed** (gps `first_fix_at`/`last_fix_at`, `trip_record.arrived_at`/`started_at`/`ended_at`); **windowed gap and count NOT computed** (gps `points[].ts`; note the payload's own `gaps` list is non-empty in only 3 cases and its threshold is undocumented); rider-track omission AVAILABLE (`rider_presence.available`); **chat integrity NOT computed** (`messages[].msg_id`/`sent_at`, `chat_log.message_count`, `trip_record.chat_message_count`); **fare defect NOT computed** (the GREATER-of arithmetic) | **DERIVABLE** |
| POL-NS-09 | Escalation to human review | Confidence vs the policy floor; direct contradiction between admissible artifacts; the sum of the two `disputes_with_counterparty_90d` counters ≥ 2; the anti-farming ratio, or `no_show_disputes_30d` ≥ 3; sole-evidence impairment under POL-NS-08 | confidence AVAILABLE (`confidence_floor`); contradiction judge-side, values AVAILABLE; **the sum NOT computed** (`rider_profile.disputes_with_counterparty_90d`, `driver_profile.disputes_with_counterparty_90d`); the ratio NOT computed; `no_show_disputes_30d` AVAILABLE; impairment inherits POL-NS-08 | **DERIVABLE** |
| POL-RD-01 | Route Deviation Threshold | `excess = gps_trace.trace_distance_km − trip_record.optimal_distance_km`; the 20 %-and-0.8 km establishment tests; the 50 %-or-8.0 km materiality test | inputs AVAILABLE (both fields populated on 15/15 route-deviation cases — see §3); **the excess and both tests NOT computed** | **DERIVABLE** |
| POL-RD-02 | Optimal-Route Fare Recomputation | `recomputed_fare` = ((base + per_km × optimal_distance + per_min × optimal_duration) × surge) + platform fee + optimal-route ERP + fixed surcharges + waiting fee − promo discount; `refund = charged_total − recomputed_fare` floored at zero; round UP to 0.05; de minimis below 0.50; FULL_REFUND at ≥90 % | inputs AVAILABLE (`fare_model` constants, `trip_record.optimal_distance_km`/`optimal_duration_min`, `fare_breakdown.surge_multiplier`/`platform_fee`/`waiting_time_fee`/`promo_discount`/`total_charged`, `trip_record.optimal_route_erp_sgd`, and `erp_gantries[].on_optimal_route` — present on all 8 gantry entries); **all of the arithmetic NOT computed** | **DERIVABLE** |
| POL-RD-03 | Road Closure or Traffic Advisory Exoneration | (a) the advisory names a road the optimal route traverses; (b) its window overlaps when the vehicle would have reached that segment, ±15 min; **(c) an actual route that leaves the optimal corridor before the affected segment and rejoins it after**; the capped justified excess | (a) AVAILABLE (`intersects_route`, `road_name`); (b) AVAILABLE (`active_from`, `active_to`, `overlaps_trip_window`, `overlap_minutes`); **(c) UNSUPPORTED — the corpus carries no optimal-route geometry**; the cap needs `shortest_lawful_alternative_km`, which is null on the one KERB_RESTRICTION advisory | **UNSUPPORTED** |
| POL-RD-04 | Rider-Requested Detour or Additional Stop | A rider instruction with a timestamp; `chat_message.waypoint_hint`; the vehicle passing within 200 m of the waypoint; **the excess between leaving and rejoining the optimal corridor**; the unbilled-km shortfall and the 0.75/km compensation capped at 15.00 | instruction AVAILABLE (`messages[].sender`/`sent_at`/`text`); `waypoint_hint` populated on only 2 of 81 messages (both with lat/lng/venue_id), null on 79 — the clause's own rule covers the null case; **the 200 m test NOT computed**; **the corridor excess UNSUPPORTED**; **the compensation arithmetic NOT computed** (`gps_trace.trace_distance_km`, `fare_breakdown.distance_charged_km`) | **UNSUPPORTED** |
| POL-RD-05 | Pickup or Dropoff Point Relocation | The amendment timestamps; `amended_optimal_distance_km` / `amended_optimal_duration_min`; a re-applied POL-RD-01 excess; circling within 400 m for >4 min; distance driven **before** the amendment timestamp | amendment inputs AVAILABLE (1 case carries each); **the re-applied excess NOT computed**; **the circling run NOT computed**; **distance-over-a-window NOT computed** (gps `points[].ts`, `points[].lat/lng`) | **DERIVABLE** |
| POL-RD-06 | Repeat Deviation Pattern | `deviation_flags_90d` ≥ 3, or the ratio ≥ 0.05 with `completed_trips_90d` ≥ 40; a MATERIAL deviation from POL-RD-01; the uplift = the POL-RD-02 figure vs the FULL_REFUND figure side by side | profile fields AVAILABLE; **the ratio NOT computed** (`driver_profile.deviation_flags_90d`, `completed_trips_90d`); **materiality NOT computed** (inherits POL-RD-01); **the uplift NOT computed** (inherits POL-RD-02) | **DERIVABLE** |
| POL-RD-07 | GPS Trace Integrity and Gap Handling | A gap > 90 s between consecutive fixes; a straight-line jump > 500 m between consecutive fixes; a sustained sampling interval > 30 s; the impaired-stretch straight line; independent corroboration | **all three tests NOT computed** (gps `points[].ts`, `points[].lat/lng`, `sample_interval_sec`, `expected_interval_sec`; note `gaps` is non-empty in only 3 cases and its firing threshold is undocumented, so the test must be computed from the fixes); corroboration options AVAILABLE (`messages`, `erp_gantries[].on_optimal_route`, `dispute.counterparty_statement`, `trip_record.actual_distance_km`) | **DERIVABLE** |
| POL-RD-08 | Burden of Proof and Shifting | Matching trip identifiers and pickup timestamps across three artifacts; an excess meeting the POL-RD-01 threshold; `deviation_claims_60d` ≥ 4 with `deviation_claims_60d_substantiated` ≤ 1; the <30 % corroboration trigger | identity AVAILABLE (`trip_id`, `requested_at`/`first_fix_at`/`charged_at`); **the excess NOT computed**; profile fields AVAILABLE; **the <30 % trigger NOT computed** (inherits POL-RD-01) | **DERIVABLE** |
| POL-RD-09 | ERP, Toll and Surcharge Pass-Through | A gantry-to-trace match within 250 m; `erp_gantry.on_optimal_route`; the 12.00 cap and the standalone correction; an airport surcharge on a trip that does not originate at an airport | **the 250 m match NOT computed** (8 gantry entries, all 8 carrying `lat`/`lng`, against gps `points[].lat/lng`); `on_optimal_route` AVAILABLE; **the arithmetic NOT computed**; the airport-origin test AVAILABLE (`pickup_zone_class` = AIRPORT in 2 cases, plus `trip_record.pickup`) | **DERIVABLE** |
| POL-RD-10 | Mandatory Escalation, No Ruling | Confidence vs the floor; trip-id matching; POL-RD-07 impairment with no corroboration; cross-artifact timestamp disagreement > 10 min or running backwards; an exculpatory clause invoked against a missing or field-less artifact; a refund above 150.00 or above `charged_total`; contradictory admissible evidence; an unmatched charge line | confidence, trip ids, missing/field-less artifacts AVAILABLE; POL-RD-07 inherits; **cross-artifact timestamp comparison NOT computed** (`requested_at`, `arrived_at`, `first_fix_at`, `charged_at`); **the refund threshold NOT computed** (inherits POL-RD-02); contradiction judge-side; **the unmatched line NOT computed** (inherits POL-RD-09) | **DERIVABLE** |
| POL-RD-11 | Upfront-Quoted Fares | `fare_model` and `quoted_fare_sgd`; the arithmetic `charged_total − (quoted_fare + properly chargeable pass-through lines)` | inputs AVAILABLE (1 case is UPFRONT_QUOTE, case 115, quoted 34.5 against charged 39.0); **the arithmetic NOT computed** | **DERIVABLE** |
| POL-RD-12 | Pooled and Shared Trips | `vehicle_type` = RYDE_POOL; the matched-itinerary optimal vs `solo_optimal_distance_km`; the excess against the matched itinerary; **the distance attributable to collecting or setting down a co-rider, excluded from excess** | inputs AVAILABLE (1 case is RYDE_POOL, case 113, matched 19.4 km against solo 15.8 km); **the excess NOT computed**; **the co-rider exclusion UNSUPPORTED — the corpus carries no co-rider, pooled-stop or passenger-count data; the trip record's only rider field is `rider_id`** | **UNSUPPORTED** |

**Table row count: 24** — one per clause, matching the 24 clauses in the three policy files.

## 2. UNSUPPORTED clauses — the honest scope boundary

Three clauses cannot be applied on this corpus, because an input they require does not exist here.
They are not DERIVABLE and no amount of new code changes that.

- **POL-RD-03 — Road Closure or Traffic Advisory Exoneration.** Limb (c) requires "an actual route
  that leaves the optimal corridor before the affected segment and rejoins it after", and the corpus
  carries **no optimal-route geometry** — only `optimal_distance_km`, `optimal_duration_min`,
  `optimal_route_source` (a string), `optimal_route_erp_sgd` (a scalar) and the precomputed
  `intersects_route` flag. Without the corridor, the leave-and-rejoin pattern cannot be tested.
- **POL-RD-04 — Rider-Requested Detour or Additional Stop.** The exonerated amount is "the excess
  distance between leaving and rejoining the optimal corridor", which needs the same missing
  geometry. Its other limbs are workable, but the clause's central computation is not.
- **POL-RD-12 — Pooled and Shared Trips.** The clause requires "distance attributable to collecting
  or setting down a co-rider" to be excluded from excess, and the corpus carries no co-rider,
  pooled-stop or passenger-count field. Case 113 is the one RYDE_POOL trip and its trip record's
  only rider-related field is `rider_id`.

Nothing else is UNSUPPORTED. In particular two things that look like they might be are not:
`gps_point.venue_id` **does** exist (228 fixes across 6 cases), so POL-NS-03 stands; and
`erp_gantry.on_optimal_route` **is** precomputed on all 8 gantry entries, so POL-RD-02's
optimal-route ERP term stands.

## 3. ROUTE_DEVIATION specifically

POL-RD-01 thresholds on the excess:

> Excess = actual_distance_km − optimal_distance_km. A route deviation is ESTABLISHED only when the
> excess is greater than 20% of optimal_distance_km AND greater than 0.8 km in absolute terms; both
> tests must pass. An excess greater than 50% of optimal_distance_km, or greater than 8.0 km
> absolute, is additionally a MATERIAL deviation.

**Both fields are populated on all 15 route-deviation cases.** `gps_trace.trace_distance_km` is
present on every GPS payload in the corpus (28 of 28 populated traces; the 29th, case 213, has a
MISSING trace), and `trip_record.optimal_distance_km` is present on all 29 trip records.

| Case | trace_distance_km | optimal_distance_km | excess km | excess % | POL-RD-01 |
|---|---|---|---|---|---|
| 101 | 27.18 | 21.0 | 6.18 | 29.43 | established |
| 102 | 21.79 | 20.4 | 1.39 | 6.81 | no deviation |
| 103 | 11.18 | 8.2 | 2.98 | 36.34 | established |
| 104 | 34.17 | 27.1 | 7.07 | 26.09 | established |
| 105 | 54.16 | 36.0 | 18.16 | 50.44 | **MATERIAL** |
| 106 | 10.78 | 7.2 | 3.58 | 49.72 | established |
| 107 | 17.57 | 14.0 | 3.57 | 25.50 | established |
| 108 | 26.17 | 21.0 | 5.17 | 24.62 | established |
| 109 | 13.76 | 6.4 | 7.36 | 115.00 | **MATERIAL** |
| 110 | 21.2 | 18.4 | 2.80 | 15.22 | no deviation |
| 111 | 29.98 | 24.0 | 5.98 | 24.92 | established |
| 112 | 22.4 | 17.6 | 4.80 | 27.27 | established |
| 113 | 20.18 | 19.4 | 0.78 | 4.02 | no deviation |
| 114 | 23.97 | 18.0 | 5.97 | 33.17 | established |
| 115 | 28.18 | 22.4 | 5.78 | 25.80 | established |

Ten cases are established, two of them MATERIAL (105 and 109), and three show no deviation at all.

**Nothing in the current pipeline computes any of this.** `facts.py` has no distance-minus-optimal
primitive, `brief.py` emits no excess figure, and neither the 20 %/0.8 km establishment test nor the
50 %/8.0 km materiality test exists anywhere in `tribunal/`.

**The three derived blocks are also largely meaningless on these cases.** For ROUTE_DEVIATION,
`trip_record.pickup_zone_class` is null in all 15 cases, so `derived.arrival.available` is `false`
and every zone-dependent fact is omitted. The rider track is null in all 15 as well, so
`derived.rider_presence.available` is `false` too. On a route-deviation case the derived block
therefore carries only `driver_track` — distances and speeds around a pickup point that the
route-deviation clauses never test — while the one figure they do test, the excess, is absent.

## 4. Prioritised build order

Ordered by how many clauses the fact unblocks. A clause is counted here only if it is currently
DERIVABLE and this fact is one of its blockers; the three UNSUPPORTED clauses are excluded, because
no computation unblocks them.

| # | New fact to compute | Inputs it reads | Clauses unblocked | Count |
|---|---|---|---|---|
| 1 | Excess distance + the POL-RD-01 establishment and materiality tests | `gps_trace.trace_distance_km`, `trip_record.optimal_distance_km` (and `amended_optimal_distance_km` for POL-RD-05) | POL-RD-01, POL-RD-02, POL-RD-05, POL-RD-06, POL-RD-08 | **5** |
| 2 | Fare arithmetic: `recomputed_fare`, `refund`, round-UP-to-0.05, de minimis, the 90 % FULL_REFUND test | `fare_model` constants, `trip_record.optimal_distance_km`/`optimal_duration_min`/`optimal_route_erp_sgd`, `fare_breakdown.surge_multiplier`/`platform_fee`/`waiting_time_fee`/`promo_discount`/`total_charged`/`quoted_fare_sgd`, `erp_gantries[]` | POL-RD-02, POL-RD-06, POL-RD-10, POL-RD-11 | **4** |
| 3 | Runs at a caller-chosen radius (300 m / 400 m), not only the arrival radius | gps `points[].lat/lng/ts/accuracy_m`, `trip_record.pickup` | POL-NS-02, POL-NS-03, POL-NS-05, POL-RD-05 | **4** |
| 4 | Windowed GPS facts: counts and runs inside a named time window | gps `points[].ts`, `trip_record.cancelled_at`, `trip_record.arrived_at` | POL-NS-02, POL-NS-04, POL-NS-08 | **3** |
| 5 | The GREATER-of cancellation fee from `fee_schedule.resolution_rule` | `trip_record.pickup_zone_class`, `trip_record.vehicle_type`, `fee_schedule.zone_class_fee_sgd`, `fee_schedule.vehicle_tier_fee_sgd`, `fare_breakdown.cancellation_fee` | POL-NS-01, POL-NS-07, POL-NS-08 | **3** |
| 6 | Nearest-fix lookup at a timestamp, and the clock-skew delta | gps `points[].ts`, `trip_record.arrived_at`/`started_at`/`ended_at`, gps `first_fix_at`/`last_fix_at` | POL-NS-05, POL-NS-08 | **2** |
| 7 | Anti-farming ratio and the driver-compensation arithmetic | `driver_profile.no_show_terminations_30d`, `driver_profile.completed_trips_30d`, `fee_schedule.driver_compensation_rate`, `fare_breakdown.cancellation_fee` | POL-NS-07, POL-NS-09 | **2** |
| 8 | Consecutive-fix gap, jump and sampling-interval analysis | gps `points[].ts`/`lat`/`lng`, `sample_interval_sec`, `expected_interval_sec` | POL-RD-07, POL-RD-10 | **2** |
| 9 | Gantry-to-trace match within 250 m | `erp_gantries[].lat`/`lng`, gps `points[].lat`/`lng` | POL-RD-09, POL-RD-10 | **2** |
| 10 | Chat timing: reply gap, `msg_id` sequence gaps, a >5 min gap spanning the arrival marker | `chat_log.messages[].msg_id`/`sent_at`/`sender`, `chat_log.message_count`, `trip_record.chat_message_count` | POL-NS-04, POL-NS-08 | **2** |
| 11 | Multi-interval dwell accumulation bounded at 300 m from the pin | gps `points[].lat/lng/ts`, `trip_record.pickup` | POL-NS-06 | **1** |
| 12 | `bundle_integrity_score` — the mean `weight_multiplier` across the bundle | `evidence[].admissibility.weight_multiplier` | POL-GEN-02 | **1** |
| 13 | The sum of the two `disputes_with_counterparty_90d` counters | `rider_profile.disputes_with_counterparty_90d`, `driver_profile.disputes_with_counterparty_90d` | POL-NS-09 | **1** |
| 14 | Cross-artifact timestamp agreement (>10 min apart, or running backwards) | `requested_at`, `arrived_at`, `first_fix_at`, `charged_at` across trip, trace and fare artifacts | POL-RD-10 | **1** |
| 15 | Distance driven over a time window (before an amendment timestamp) | gps `points[].ts`/`lat`/`lng`, `trip_record.pickup_amended_at`/`dropoff_amended_at` | POL-RD-05 | **1** |

Items 1 and 2 together unblock the whole route-deviation money path, which is the largest single
gap: 9 of the 15 route-deviation cases currently produce a derived block that says nothing about the
only figure the route clauses test.

## Clause status summary

| Status | Clauses | Count |
|---|---|---|
| AVAILABLE | POL-GEN-01, POL-GEN-03 | **2** |
| DERIVABLE | POL-GEN-02, POL-NS-01 … POL-NS-09 (9), POL-RD-01, POL-RD-02, POL-RD-05, POL-RD-06, POL-RD-07, POL-RD-08, POL-RD-09, POL-RD-10, POL-RD-11 (9) | **19** |
| UNSUPPORTED | POL-RD-03, POL-RD-04, POL-RD-12 | **3** |
| **Total** | | **24** |
