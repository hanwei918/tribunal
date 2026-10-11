# Reviewer handoff

These are AI-generated reference answers for Ji Guofang to check, not completed human-reviewed answers. Do not run the sealed evaluation until the review and model-identity disclosure are complete. No Tribunal runtime was executed.

## Source handling

The seven reference files consist of three base policy JSON files, three amendment JSON files, and one public contract. Apply the rules in the six JSON files as cumulative policy version 6. The public contract retains historical descriptions of older versions: root policy paths, 24-clause counts, five-field corpus indexes and eleven-key disputes. For this external set, the updated instructions prescribe version 6, 34 clauses, six-field indexes including SHA-256, and two additional false intake flags. These are additive version differences, not substitutes for policy rules. No case was copied from a development sample.

The authorized policy files themselves contain historical development references in notes or metadata. These were encountered only inside supplied files; no referenced development file, run result or internal implementation was opened.

All telemetry and platform events are synthetic. Place and road labels refer to Singapore; coordinate polylines approximate the named corridors and are not map-matched real vehicle exports. The task does not establish real road closures or real customer disputes. There are no actual traffic advisories in these cases; each has the required missing placeholder.

The source instructions require exact model name/version. This session exposes only the OpenAI Codex / GPT-based assistant identity. MANIFEST records that limitation explicitly. Do not replace it with an assumed version. Obtain the exact identity from a trustworthy session record if available. reviewed_by names the intended reviewer, and review_status remains PENDING until actual review.

## Numeric conventions

Billed monetary lines are supplied ledger facts in SGD cents. Those existing charge lines use ordinary half-up cent rounding. Policy recomputed_fare and differences use Decimal without intermediate rounding; only final payable corrections are rounded upward to 0.05. FULL_REFUND equals the entire contested charge. Coverage is exported fix count divided by the expected 10-second inclusive fix count. sample_interval_sec is the nominal/modal 10-second interval; max_gap_sec and gaps expose missing exports. Route distance is a spherical polyline using Earth radius 6371.0088 km, rounded to two decimals.

## Package use

Package A contains exactly 12 cases, index.json, CANARY.txt and README.md. Keep this reviewer guide, the answer key, manifest and all audit material in package B. Do not concatenate package B into an agent bundle. Imported case files must retain their original bytes. The directory-level import digest is intentionally not supplied.

The unmodified checker was extracted from the updated DOCX and is byte-for-byte identical after trimming outer whitespace to the ZIP checker. Its output is included. The additional audit checks arithmetic and selected policy predicates, not a second human review. Passing either script does not certify legal correctness or independence. These are benchmark policy rules, not assertions about real Singapore law.

## Per-case review

### Case 801

Proposed ruling: PARTIAL_REFUND. Amount: 1.45. Driver compensation: None.

Referrals: None.

EV-GPS-00801 measures 4.08 km against 3.15 km on EV-TRIP-00801: excess 0.93 km (29.52%), exceeding both POL-RD-01 tests. The intact 10-second track supports the finding. POL-RD-02 applies to EV-FARE-00801 METERED pricing. charged_total = 11.63; recomputed_fare = (3.80 + 0.75 * 3.15 + 0.28 * 9.0) * 1.15 + 0.80 - 0.6 = 10.184875; refund = ceil((11.63 - 10.184875) / 0.05) * 0.05 = 1.45. This is at least 0.50 and below 90% of charged_total. No exemption is asserted and no independent pass-through correction exists. EV-ADVIS-00801-01 is missing but carries no deciding fact; its weight does not cap confidence. No profile pattern or referral is established.

Governing rules: POL-RD-01, POL-RD-02, POL-GEN-02.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 802

Proposed ruling: FULL_REFUND. Amount: 19.65. Driver compensation: None.

Referrals: POL-RD-06(c) driver-conduct review

EV-GPS-00802 shows 10.06 km versus 1.10 km on EV-TRIP-00802, an excess of 8.96 km and 814.55%, independently establishing a MATERIAL deviation under POL-RD-01. EV-DPROF-00802 has deviation_flags_90d=3, meeting POL-RD-06 without needing the ratio limb. charged_total = 19.65; recomputed_fare = (3.80 + 0.75 * 1.1 + 0.28 * 4.0) * 1.0 + 0.80 - 0.0 = 6.5450; refund = ceil((19.65 - 6.5450) / 0.05) * 0.05 = 13.15. POL-RD-06(b) uplifts that ordinary refund of 13.15 to the entire charged_total 19.65. EV-FARE-00802 contains no ERP, toll or airport line to exclude from the uplift. The refund equals the contested total under POL-GEN-03. POL-RD-06(c) adds conduct review without replacing the monetary ruling. The profile establishes only the pattern, not this trip deviation.

Governing rules: POL-RD-01, POL-RD-02, POL-RD-06, POL-GEN-03.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 803

Proposed ruling: PARTIAL_REFUND. Amount: 6.0. Driver compensation: None.

Referrals: POL-RD-09(4) billing-integrity finding: SGD 6.00 airport surcharge on EV-FARE-00803 for a trip originating at Bugis

EV-FARE-00803 records UPFRONT_QUOTE=18.00 and charged_total=24.00. POL-RD-11 excludes POL-RD-02: recomputed_fare is not applicable and no metered distance/time recalculation is payable. EV-TRIP-00803 starts at Bugis, not an airport, and EV-GPS-00803 supports that pickup. The SGD 6.00 airport line is improper under POL-RD-09(4). The quote excess 24.00 - 18.00 = 6.00 is this same line, not a second refund. Refund = ceil(6.00 / 0.05) * 0.05 = 6.00, less than the contested 24.00, hence PARTIAL_REFUND. Record a billing-integrity referral under POL-RD-09(4); its explicit exception prevents POL-RD-10(8) escalation. No driver payment is due.

Governing rules: POL-RD-11, POL-RD-09.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 804

Proposed ruling: NO_ACTION. Amount: None. Driver compensation: None.

Referrals: None.

EV-TRIP-00804 identifies RYDE_POOL and the matched itinerary, with optimal_distance_km=4.75 and solo_optimal_distance_km=3.10. POL-RD-12 selects 4.75, not the solo figure. EV-GPS-00804 measures 4.88 km, so the remaining excess is 0.13 km (2.74%), which fails the joint POL-RD-01 threshold. The co-rider stop is already included in the matched itinerary. charged_total = 11.9; recomputed_fare = not applicable because no deviation is established; refund = none (null). NO_ACTION leaves EV-FARE-00804 payment_status=CHARGED and refund_issued_sgd=0 unchanged. No pass-through defect or referral exists.

Governing rules: POL-RD-12, POL-RD-01, POL-GEN-03.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 805

Proposed ruling: PARTIAL_REFUND. Amount: 4.2. Driver compensation: None.

Referrals: None.

EV-CHAT-00805 contains a specific rider waypoint instruction before departure. However EV-GPS-00805 never approaches its waypoint_hint: nearest exported fix is 1592.1 m away, beyond 200 m, and no requested road is named. POL-RD-14 therefore excludes no distance and resolves the apparent conflict without POL-RD-10(7) escalation. The driver assertion does not establish execution of the request. The intact trace measures 5.5 km against 2.50 km on EV-TRIP-00805; both POL-RD-01 thresholds pass. charged_total = 12.87; recomputed_fare = (3.80 + 0.75 * 2.5 + 0.28 * 8.0) * 1.0 + 0.80 - 0.0 = 8.7150; refund = ceil((12.87 - 8.7150) / 0.05) * 0.05 = 4.20. This is below 90% of charged_total. The materiality check on EV-DPROF-00805 finds zero deviation_flags_90d, so POL-RD-06 provides no uplift or referral. The fare billed the whole trace distance; no unbilled-distance compensation is due.

Governing rules: POL-RD-14, POL-RD-01, POL-RD-02, POL-RD-06.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 806

Proposed ruling: ESCALATE. Amount: None. Driver compensation: None.

Referrals: None.

EV-GPS-00806 has a 160-second gap and is tagged GPS_GAP at weight 0.60. It meets POL-RD-07(a), irrespective of its aggregate distance 5.56 km. Its gap distance uses the straight line between bounding fixes. EV-TRIP-00806.actual_distance_km and EV-FARE-00806.distance_charged_km are explicitly copies of the same export, not independent corroboration. EV-CHAT-00806 has no admission, no counterparty admission is filed and there are no ERP corridor records. POL-RD-07(iii) and POL-RD-10(3) therefore require ESCALATE; POL-GEN-02 and POL-RD-10(1) also bar a sole-carrier finding at 0.60. charged_total = 13.03; recomputed_fare and refund = not issued because escalation is terminal; both amount fields are null. Obtain an independent platform route measurement or a contemporaneous admission to resolve the route. No separate monetary referral is directed.

Governing rules: POL-RD-07, POL-RD-10, POL-GEN-02.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 851

Proposed ruling: DRIVER_COMPENSATION. Amount: 3.6. Driver compensation: 3.6.

Referrals: None.

EV-TRIP-00851 records driver termination for RIDER_NO_SHOW without boarding. EV-GPS-00851 has 22 consecutive 8 m-accuracy fixes at the pickup pin over 210 seconds, satisfying the 150 m AIRPORT radius, three-fix test and platform_policy.free_wait_sec=180 under POL-NS-01/02. The legacy airport 480-second table is not used because platform_policy governs. EV-CHAT-00851 shows no unresolved coordination request. EV-DPROF-00851 has 1 no-show termination in 100 completed trips, so POL-NS-07 anti-farming does not apply. Net fee 4.50 * 0.80 = 3.60; both amount fields are 3.60 under POL-GEN-03. The rider charge stands, but the emitted ruling is DRIVER_COMPENSATION, not NO_ACTION. No referral is required.

Governing rules: POL-NS-01, POL-NS-02, POL-NS-07, POL-GEN-03.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 852

Proposed ruling: FULL_REFUND. Amount: 4.5. Driver compensation: None.

Referrals: None.

EV-TRIP-00852 records accepted_at=18:10:00 and the rider cancellation at 18:11:30, a 90-second interval. The explicit platform_policy.grace_after_match_sec is 180. POL-NS-10(a) therefore makes the cancellation free regardless of driver location or arrival. EV-FARE-00852 nevertheless charged 4.50 and shows no prior refund. Under POL-NS-10(c), refund the entire contested 4.50 with no driver compensation. EV-GPS-00852 location is immaterial to this grace-period finding, and no profile-triggered escalation applies. No referral is directed.

Governing rules: POL-NS-10, POL-GEN-03.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 853

Proposed ruling: DRIVER_COMPENSATION. Amount: 3.6. Driver compensation: 3.6.

Referrals: None.

EV-CHAT-00853 contains a rider locating message with no driver reply, and EV-TRIP-00853 has no in-app call. However EV-GPS-00853.rider_track is empty. POL-NS-11 makes POL-NS-04(c) UNDECIDABLE, not satisfied or failed; the missing rider track neither exonerates the rider nor impairs the independent driver-arrival finding. The driver track has 25 accurate fixes at the pin and 240 seconds continuous dwell, exceeding 180; termination is RIDER_NO_SHOW without boarding. POL-NS-01/02 and POL-NS-07 yield 4.50 * 0.80 = 3.60, mirrored in both amount fields by POL-GEN-03. Lifetime prior_no_show_flags=19/24 do not trigger POL-NS-09(d); the rider trailing count is 0 and the driver count is 1/100. POL-GEN-01 excludes those lifetime counters as outcome grounds. No referral is due.

Governing rules: POL-NS-11, POL-NS-01, POL-NS-02, POL-NS-07, POL-GEN-01, POL-GEN-03.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 854

Proposed ruling: FULL_REFUND. Amount: 4.5. Driver compensation: 2.25.

Referrals: None.

EV-GPS-00854 shows 240 seconds stationary 200.2 m from EV-TRIP-00854.pickup, outside the LARGE_VENUE radius of 120 m but within 400 m. Both locations carry venue_id=SUNTEC-CITY. POL-NS-02 yields to POL-NS-03, which refunds EV-FARE-00854 cancellation fee of 4.50 in full. EV-CHAT-00854 shows neither party specified an entrance, tower or bay; EV-TRIP-00854 has registered_pickup_points=3. POL-NS-03(ii) also grants platform-funded goodwill: 4.50 * 0.50 = 2.25. Under POL-GEN-03 the rider refund 4.50 and driver payment 2.25 are independent and are not netted. The marker was stationary within 300 m, so POL-NS-05 false-arrival treatment does not apply. The driver replied within 120 seconds, so POL-NS-04 does not displace the goodwill. No referral is directed.

Governing rules: POL-NS-02, POL-NS-03, POL-GEN-03.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 855

Proposed ruling: DRIVER_COMPENSATION. Amount: 3.6. Driver compensation: 3.6.

Referrals: None.

EV-GPS-00855 has only three fixes, a 160-second waiting-window gap and unknown accuracy; GPS_GAP gives weight 0.60 and POL-NS-08(b) applies to this export. But EV-TRIP-00855 has GPS_AUTO, a platform arrival event at 18:10:00 stating distance=0 m and speed=0 km/h, wait_timer_started and wait_timer_expired at 18:13:00, before termination at 18:14:00. POL-NS-12 makes these full-resolution events an independent weight-1.00 carrier of arrival and served dwell under POL-GEN-02. No admissible exported fix contradicts them; unknown accuracy does not prove absence. POL-NS-09(e) does not apply because the sparse export is not the sole carrier. POL-NS-01 and POL-NS-07 give 4.50 * 0.80 = 3.60; both amount fields are 3.60 under POL-GEN-03. Driver anti-farming is 1/100 and no referral is required.

Governing rules: POL-NS-12, POL-NS-01, POL-NS-07, POL-GEN-02, POL-GEN-03.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

### Case 856

Proposed ruling: ESCALATE. Amount: None. Driver compensation: None.

Referrals: POL-NS-07 escalation packet: instruct the reviewer to refund the rider cancellation fee of SGD 4.50 in full

EV-GPS-00856 supplies 25 accurate fixes at the pickup pin over 240 seconds; EV-TRIP-00856 records RIDER_NO_SHOW without boarding, so the basic POL-NS-01/02 requirements hold. However EV-DPROF-00856 has no_show_terminations_30d=5 and completed_trips_30d=50: 5 >= 4 and 5/50 = 0.10 > 0.08. POL-NS-07 anti-farming and POL-NS-09(d) require terminal ESCALATE, withholding the otherwise 4.50 * 0.80 = 3.60 payout. Both automated amount fields are null; neither the refund nor compensation is issued. POL-NS-07 additionally directs the reviewer to refund the full 4.50 cancellation fee on EV-FARE-00856; that instruction is a referral, not an automated refund. The reviewer must investigate the flagged termination pattern and dispose of the held fee. Lifetime counters are not the trigger.

Governing rules: POL-NS-07, POL-NS-09.

- [ ] Check evidence and actual policy rule text.
- [ ] Recompute amounts and confirm null versus numeric fields.
- [ ] Confirm all referrals and subclauses.
- [ ] Confirm no unresolved alternative outcome.
- [ ] Record reviewer, date and decision.

## Clause text for review

The following rule strings are copied exactly from the supplied policy JSON files, with no rewriting. The hashed reference files remain authoritative.

### POL-GEN-01

A rider_profile or driver_profile may inform how closely a party's assertions are scrutinised. It may never, on its own or in combination with another profile, establish a fact about THIS trip or carry an adverse finding against either party. Only the following profile fields may be cited as a ground of decision, and only for the tests that name them: driver_profile.deviation_flags_90d and driver_profile.completed_trips_90d (POL-RD-06); rider_profile.deviation_claims_60d and rider_profile.deviation_claims_60d_substantiated (POL-RD-08); driver_profile.no_show_terminations_30d and driver_profile.completed_trips_30d (POL-NS-07); rider_profile.no_show_disputes_30d (POL-NS-09(d)); rider_profile.disputes_with_counterparty_90d and driver_profile.disputes_with_counterparty_90d (POL-NS-09(c)). Every other field on either profile - rating, account_age_days, lifetime_trips, cancellation_rate, prior_disputes_filed, prior_disputes_upheld, prior_no_show_flags, prior_deviation_flags, acceptance_rate, active_region - is CONTEXT ONLY. A claim that cites one of those fields as a reason for the outcome is discarded by the Judge on the same footing as an uncited claim, and the Judge must say in the reasoning that it was discarded and why. Several of those fields are deliberate near-synonyms of the citable counters (prior_no_show_flags against no_show_disputes_30d; prior_deviation_flags against deviation_flags_90d): reading the lifetime counter where a clause names the trailing-window counter is the commonest way an adverse finding gets built on reputation without anyone noticing.

### POL-GEN-02

Every evidence artifact carries admissibility.weight_multiplier in [0.0, 1.0], produced by the pre-pass before the debate opens. It has three effects and no others. (1) DISCLOSURE. An advocate citing an artifact whose weight_multiplier is below 1.0 must state, in the same claim, that the artifact is impaired and which issue codes fired. A claim that cites an impaired artifact without disclosing the impairment is discarded by the Judge on the same footing as an uncited claim. (2) CONFIDENCE. The Judge's confidence in a ruling is capped by the evidence the ruling actually rests on: confidence must not exceed the minimum weight_multiplier among the artifacts that carry the deciding fact, and where two or more independent artifacts carry it, that cap is the maximum of their weight_multipliers rather than the minimum. bundle_integrity_score, the mean weight across the bundle, is context for the reader and is NOT the cap. Because the platform-wide escalation floor is 0.70, a deciding fact carried solely by an artifact at weight 0.65 or below escalates automatically under POL-RD-10(1) or POL-NS-09(a). (3) NARRATION. Any ruling that relies on an artifact below weight 1.0 must name the artifact, its weight and its issue codes in the written explanation, and say whether the finding survives the discount and why. A MISSING artifact has weight 0.0, can carry no fact, and its absence is itself citable. Schema-level impairment is not the same as policy-level impairment: POL-RD-07 and POL-NS-08 set their own, looser thresholds, and an artifact may be down-weighted here while remaining fully usable there. The Judge must say both things.

### POL-GEN-03

The five ruling values mean the following, and nothing else. FULL_REFUND: the filing party is entirely right and the whole contested amount is returned. PARTIAL_REFUND: part of the contested amount is returned. NO_ACTION: THE FILING PARTY'S CLAIM IS NOT SUPPORTED BY THE EVIDENCE AND THE PRESENT STATE STANDS - specifically, fare_breakdown.payment_status and fare_breakdown.refund_issued_sgd are left as they are. NO_ACTION is therefore PARTY-RELATIVE: on a rider-filed dispute it leaves a charge in place, and on a driver-filed dispute over a fee the platform has already reversed it leaves the rider refunded. It never means 'restore the charge'. DRIVER_COMPENSATION: the driver is owed money. ESCALATE: the case goes to a human reviewer, no monetary outcome issues, and the disputed amount is held rather than collected or refunded. ESCALATE is always TERMINAL and always REPLACES the ruling; a clause that adds something to a monetary ruling - POL-RD-06(c) driver-conduct review, POL-RD-09(4) billing integrity, POL-NS-05(ii) false-arrival record - produces a REFERRAL, not an escalation, and referrals never suppress the money. A ruling object carries: ruling (one of the five), amount_sgd (the refund to the filing party, null where none), driver_compensation_sgd (a platform-funded or fee-funded payment to the driver, null where none), referrals (an array of referral strings, empty where none), confidence, and the written explanation. Where a case produces both a rider refund and a driver payment - POL-NS-03(ii) pin-ambiguity goodwill is the standard instance - both fields are populated, the two are INDEPENDENT and are never netted against each other, and the ruling value names the outcome for the FILING party. ONE EXCEPTION, and it is the only one: where the ruling is DRIVER_COMPENSATION, amount_sgd carries the SAME figure as driver_compensation_sgd. It is the amount of money the ruling moves, not a second payment and not a refund to the filing party - on such a ruling the filing party's own charge stands, which POL-NS-07 states as 'the ruling on the fee is NO_ACTION'. The ruling VALUE is DRIVER_COMPENSATION because that is the outcome the case produces. Aggregate reporting must avoid double-counting driver payments: sum amount_sgd as a filing-party refund only across FULL_REFUND and PARTIAL_REFUND rulings.

### POL-NS-01

A cancellation (no-show) fee is legitimately chargeable to the rider ONLY IF all four conditions hold: (a) the trip_record contains a driver 'arrived' event for the trip; (b) the gps_trace places the driver inside the pickup geofence defined in POL-NS-02 at or before the timestamp of that event, OR, where POL-NS-05 finds the arrival marker false and recomputes the waiting clock, at the first qualifying in-geofence fix from which that recomputed clock runs; (c) the driver held position inside that geofence for a continuous dwell of at least the free waiting period in force for this trip - trip_record.platform_policy.free_wait_sec where the record carries it, and fee_schedule.defaults.free_wait_sec (180 seconds, Ryde's published 3 minutes) otherwise; where platform_policy.no_show_threshold_sec is set and longer, the cancellation in limb (d) must also fall at or after that threshold - the dwell being measured from the first qualifying in-geofence GPS fix and not from the 'arrived' event; and (d) the trip_record records no boarding event and shows the trip terminated by the driver with cancellation_reason_code RIDER_NO_SHOW, RIDER_UNREACHABLE or EXCESSIVE_WAIT, at or after the moment the required dwell elapsed. DRIVER_UNABLE_TO_LOCATE is the driver's own admission that he could not find the rider and does not satisfy limb (d). Where the driver's stationary fixes lie outside the POL-NS-02 arrival radius but not more than 400 m from the pickup pin, such a trip is decided under POL-NS-03; where they lie more than 400 m from the pin, the driver never arrived and POL-NS-02 governs; where they lie inside the radius, the fee is not chargeable, the ruling is FULL_REFUND of the cancellation fee with no driver compensation, and the mis-selected reason code is recorded in the ruling's referrals as a driver-education item. No Singapore platform's published policy allows a driver to collect a no-show fee on a cancellation recorded under any reason other than the rider's failure to appear. Where all four conditions hold and no clause from POL-NS-03 to POL-NS-06 displaces them, the cancellation fee stands, in the net amount fixed by fee_schedule.resolution_rule: platform_policy.cancellation_fee_sgd where the record carries it, otherwise fee_schedule.defaults.cancellation_fee_sgd; the fare_breakdown line may show that net figure or the rider's gross figure (POL-NS-08(d)). Where any of (a) to (d) fails, the fee is not chargeable under this clause and, save where limb (d) itself fixes the outcome, the Judge must decide the refund under POL-NS-02, POL-NS-03, POL-NS-05, POL-NS-06 or POL-NS-10 as applicable.

### POL-NS-02

The driver is deemed to have ARRIVED at the pickup point only where the gps_trace contains at least 3 consecutive position fixes, each with reported horizontal accuracy of 25 m or better, falling within the arrival radius of the pickup pin recorded in trip_record. The arrival radius is fee_schedule.arrival_radius_m for the zone class: 50 m for STANDARD, 120 m for LARGE_VENUE (shopping-mall and condominium pickup zones), and 150 m for TRANSPORT_HUB and AIRPORT (the kerbside bays at Changi Terminals 1 to 4, and interchange private-hire bays such as Jurong East, Woodlands and Tampines). Fixes reporting horizontal accuracy worse than 25 m are ignored for this test and count as evidence of neither presence nor absence. SUBJECT TO POL-NS-03, where the gps_trace contains no qualifying in-radius fix at any point in the 15 minutes preceding the cancellation, the driver never arrived, POL-NS-01 limb (b) fails, and the rider is entitled to a full refund of the cancellation fee. Where the driver was nonetheless stationary for the required dwell within 400 m of the pin, POL-NS-03 governs the outcome including the driver's compensation, and this clause yields to it. Where qualifying in-radius fixes exist, this clause is satisfied and the dispute turns on dwell duration under POL-NS-01 limb (c).

### POL-NS-03

Where the gps_trace shows the driver stationary for the required dwell at a point outside the POL-NS-02 arrival radius but not more than 400 m from the pickup pin, the driver did not arrive at the pickup point, POL-NS-01 limb (b) fails, and the cancellation fee is refunded to the rider in full. The 400 m ceiling is the whole test and is measured from trip_record.pickup; it is decidable from coordinates alone. Where the stationary fixes carry a gps_point.venue_id and trip_record.pickup carries one too, a match on venue_id corroborates that this is a wrong-face-of-the-same-venue case rather than a driver who was never at the venue, and a mismatch corroborates the opposite; where either venue_id is null the point is simply not established either way and the distance test governs alone. No advocate and no Judge may assert that two coordinates are the same venue, block or entrance on general geographic knowledge: that assertion must rest on venue_id or on a party statement in the chat_log. Fault is then allocated from the chat_log for the purpose of driver compensation only: (i) where the rider stated the correct entrance, block or tower in the chat_log and the driver did not move to it before cancelling, the driver bears the loss and receives no compensation; (ii) where neither party specified a sub-location and trip_record.registered_pickup_points is 2 or more, the mislocation is attributed to pin ambiguity rather than to either party, and the driver receives a platform-funded goodwill payment of 50 percent of the cancellation fee, which is charged to the platform and never recovered from the rider.

### POL-NS-04

The rider is exonerated and the cancellation fee refunded in full, with no driver compensation payable, where all three of the following hold: (a) the chat_log shows the rider sent at least one message during the waiting window whose content is locating or coordinating - their own position, an entrance, block, tower or bay identifier, a request for the driver's position, or a statement that they cannot see the vehicle; (b) the driver neither posted a reply in the chat_log within 120 seconds of that message nor placed an in-app voice call recorded in trip_record.in_app_calls, at any point before terminating the trip; and (c) the gps_trace rider_track places the rider's device within the fee_schedule.rider_presence_radius_m for the zone class - 100 m for STANDARD, 150 m for LARGE_VENUE, 200 m for TRANSPORT_HUB and AIRPORT - for the MAJORITY of qualifying fixes across the waiting window. Rider fixes reporting horizontal accuracy worse than 25 m are ignored for limb (c) exactly as driver fixes are under POL-NS-02, and count as evidence of neither presence nor absence. Where rider_track is absent, or every fix in it is filtered out for accuracy, limb (c) is UNDECIDABLE and neutral: it is neither satisfied nor failed, the artifact is impaired under POL-NS-08(b), and the Judge must say the test could not be run rather than inferring the rider was elsewhere. Where limbs (a) and (b) hold but limb (c) is affirmatively failed on admissible fixes, this clause does not apply and the dispute is decided under POL-NS-01. Where the driver did reply within 120 seconds, this clause does not apply regardless of the content of the reply, and any residual mislocation is decided under POL-NS-03.

### POL-NS-05

Where the trip_record 'arrived' event carries a timestamp at which the gps_trace places the driver more than 300 m from the pickup pin, or shows the driver travelling at 15 km/h or above (that is, still in motion on an expressway such as the PIE, CTE, AYE, ECP or KPE, or on an arterial road), the arrival marker is FALSE and does not start the waiting clock. The waiting clock is recomputed to run from the first qualifying in-geofence fix under POL-NS-02. On that recomputed basis: (i) if the corrected dwell is shorter than the free waiting period in force under POL-NS-01(c), the cancellation fee is refunded in full and no driver compensation is payable; (ii) if no qualifying in-geofence fix exists anywhere in the trip, the fee is refunded in full, no compensation is payable, and the trip is recorded as a false-arrival event against the driver in the ruling's referrals list; (iii) if the corrected dwell nonetheless meets the minimum, the false marker does not by itself defeat the fee, and POL-NS-01 governs the outcome - its limb (b) being read from the recomputed clock, as that limb now states - so that where POL-NS-01 is satisfied in full the fee stands and POL-NS-07 fixes the driver's payout; the false marker is nonetheless recorded in the ruling's referrals as a false-arrival event against the driver, as in limb (ii), so that the pattern is visible to POL-NS-07 and to human review without affecting the fee. A driver who is stationary within 300 m of the pin but outside the arrival radius when marking arrival is not caught by this clause and is decided under POL-NS-03.

### POL-NS-07

Where POL-NS-01 is satisfied in full and no clause from POL-NS-03 to POL-NS-06 displaces it, or where POL-NS-10(g) applies, the driver is compensated at 80 percent of the cancellation fee in force for the trip under POL-NS-01 (fee_schedule.resolution_rule; the net figure, never the rider's gross figure) - at the version-1 table SGD 3.20 of SGD 4.00, SGD 4.80 of SGD 6.00, SGD 6.40 of SGD 8.00 - the residual 20 percent being retained as the platform service fee. Compensation is subject to an anti-farming check on driver_profile: where driver_profile.no_show_terminations_30d is 4 or more AND driver_profile.no_show_terminations_30d divided by driver_profile.completed_trips_30d is greater than 0.08, compensation is WITHHELD and the case escalates under POL-NS-09; the escalation packet must DIRECT THE REVIEWER to refund the rider's cancellation fee in full, and the fee is held meanwhile rather than collected or refunded by the automated pipeline, so that the rider does not fund a dispute the platform has not resolved. No other profile field may be used for this check; driver_profile.prior_no_show_flags is a lifetime counter and is not the trailing-30-day figure. Where driver_profile shows no such pattern, compensation is paid and the ruling on the fee is NO_ACTION - meaning, per POL-GEN-03, that the rider's claim is not supported and the charge stands as it presently is. That sentence describes the disposition of the FEE, not the value of the ruling field: where compensation is paid the emitted ruling is DRIVER_COMPENSATION, with amount_sgd mirroring driver_compensation_sgd per POL-GEN-03. A Judge that emits NO_ACTION here has read this sentence as the ruling value and is wrong.

### POL-NS-08

An evidence artifact is IMPAIRED FOR POLICY PURPOSES under this clause where any of the following holds. (a) Clock skew: the trip_record 'arrived' event timestamp differs by more than 90 seconds from the nearest gps_trace fix timestamp, or trip_record and gps_trace disagree on trip start or trip termination time by more than 90 seconds. (b) Trace defect: the gps_trace contains a sampling gap longer than 120 seconds inside the waiting window, or fewer than 6 fixes across that window, or omits the rider_track where a clause under consideration relies on rider position. (c) Chat defect: the chat_log is missing messages implied by its own msg_id sequence numbering, contains a gap of more than 5 minutes spanning the driver's arrival marker, or holds fewer messages than trip_record.chat_message_count records for the trip. (d) Fare defect: the fare_breakdown cancellation-fee line equals neither the net nor, where platform_policy or fee_schedule.defaults names one, the gross amount produced by fee_schedule.resolution_rule for this trip. A claim resting on an artifact impaired under (a) to (d) is DOWN-WEIGHTED: it cannot alone support a ruling against the party it disfavours, and the Judge must name the impairment and its effect on the outcome in the written reasoning. Where the ONLY evidence for the deciding fact is impaired UNDER LIMBS (a) TO (d) OF THIS CLAUSE, the ruling may not exceed PARTIAL_REFUND and the case escalates under POL-NS-09. An artifact tagged IMPAIRED by the admissibility pre-pass but not meeting limbs (a) to (d) is down-weighted in the Judge's confidence under POL-GEN-02 only and does not engage this sentence.

### POL-NS-09

The case is escalated to a human reviewer, with a case summary comprising both advocate briefs, the admissibility pre-pass report, every clause ID relied on and the Judge's draft reasoning, where ANY of the following holds. (a) Judge confidence is below 0.70, which is the platform-wide floor and is identical to POL-RD-10(1). (b) Two admissible artifacts contradict each other directly on arrival, dwell or rider presence and no clause resolves the conflict - for example trip_record records a 6 minute dwell while gps_trace places the driver 800 m from the pin throughout the same interval. (c) rider_profile.disputes_with_counterparty_90d and driver_profile.disputes_with_counterparty_90d together show 2 or more no-show disputes between the same rider and driver in the trailing 90 days. (d) The POL-NS-07 anti-farming check trips, or rider_profile.no_show_disputes_30d is 3 or more, indicating possible abuse on either side; rider_profile.prior_no_show_flags is a lifetime counter, is NOT the field this limb reads, and may not be substituted for it. (e) The sole evidence for the deciding fact is impaired under limbs (a) to (d) of POL-NS-08. Escalation under this clause is TERMINAL for the automated pipeline: the Judge issues no monetary ruling, states the escalation trigger and the specific open question the reviewer must settle, records any instruction a displaced clause directs into the packet, and the disputed cancellation fee is placed on hold rather than collected or refunded while review is pending.

### POL-NS-10

(a) A rider's cancellation within platform_policy.grace_after_match_sec of the trip_record accepted_at timestamp (180 seconds by default) is not chargeable, whatever the driver's position; a driver's early arrival does not shorten the grace. (b) For a scheduled trip, a cancellation made more than platform_policy.advance_grace_before_scheduled_sec before trip_record.scheduled_at (900 seconds by default) is not chargeable; where the trip was accepted inside that window, limb (a) applies from accepted_at. (c) A cancellation fee charged on a cancellation that limb (a) or (b) makes non-chargeable is refunded in full with no driver compensation. (d) A waiting-time fee (platform_policy.waiting_fee_sgd, $5.00 by default) is chargeable only where the trip was completed and the driver's in-geofence dwell before the rider boarded, measured as POL-NS-01(c) measures it, exceeded platform_policy.free_wait_sec; a waiting-time fee and a cancellation fee are never both chargeable on one trip. (e) Where fare_breakdown carries a waiting-time line that limb (d) does not support, the line is refunded in full. (f) A rider's own cancellation after the grace in limb (a) or (b) is chargeable at platform_policy.cancellation_fee_sgd whether or not the driver had arrived, and the fee stands, EXCEPT that it is refunded in full where the record shows any of: the driver had not begun moving toward the pickup within the grace (trip_record.events or gps_trace); the driver had not arrived within 180 seconds of the first estimated arrival time shown to the rider (trip_record.events); the driver asked the rider to cancel (chat_log); or the vehicle or driver did not match the booking (trip_record, chat_log). (g) Where the rider cancels after the driver has arrived under POL-NS-02 and the in-geofence dwell under POL-NS-01(c) has already exceeded free_wait_sec, the fee stands at platform_policy.cancellation_fee_sgd under this clause as if the trip had been terminated by the driver for a no-show, and POL-NS-07 fixes the driver's payout; limb (f)'s exceptions do not apply, because the driver had performed. This clause licenses FULL_REFUND of the fee concerned, NO_ACTION, and - on limb (g) only, through POL-NS-07 - DRIVER_COMPENSATION.

### POL-NS-11

Where POL-NS-04 limb (c) cannot be run - rider_track is absent from the gps_trace, or every fix in it is filtered out for accuracy - limb (c) is UNDECIDABLE: it is neither satisfied nor failed, POL-NS-04 cannot exonerate the rider, and the dispute is decided under the remaining clauses on the driver's own evidence. Notwithstanding POL-NS-08(b), the missing rider_track is not the evidence for any deciding fact of those clauses: it does not impair the gps_trace for the driver's arrival or dwell, does not by itself engage POL-NS-08(b) or POL-NS-09(e), and does not lower the POL-GEN-02 cap on a finding that rests on the driver's track. The Judge must say the test could not be run rather than inferring the rider was elsewhere. This clause licenses no ruling value.

### POL-NS-12

Where trip_record.platform_policy.arrival_marker is GPS_AUTO and trip_record.events carries the platform's own arrival event stating its geofence test (the distance to the pickup point and the speed at the arrival time), together with wait_timer_started and wait_timer_expired events, those events are PLATFORM_TELEMETRY records of the platform's full-resolution measurement. They are a carrier independent of the exported gps_trace for POL-NS-01 limbs (b) and (c) and for POL-GEN-02(2): arrival is established at the arrival event's time, and the free waiting period is established as served when wait_timer_expired precedes the termination, unless an admissible fix in the exported trace affirmatively places the driver outside the arrival radius, or moving at 15 km/h or more, during the window (POL-NS-05). A sparse or accuracy-less export trace does not impair these events; it is weighed only for contradiction. A driver-pressed arrival marker (BUTTON) is not covered by this clause. This clause licenses no ruling value.

### POL-RD-01

Measure actual_distance_km as the length of the gps_trace polyline between the recorded pickup event and the recorded dropoff event; the governing field is gps_trace.trace_distance_km. Where gps_trace.trace_distance_km and trip_record.actual_distance_km disagree, gps_trace.trace_distance_km governs: trip_record.actual_distance_km is a rounded convenience copy of the same measurement and may NOT be cited for the threshold test. Measure optimal_distance_km as the platform route estimate stored on the trip_record at booking, or the adjusted optimal produced by POL-RD-03, POL-RD-04, POL-RD-05 or POL-RD-12 where one of those clauses applies. Excess = actual_distance_km - optimal_distance_km. A route deviation is ESTABLISHED only when the excess is greater than 20% of optimal_distance_km AND greater than 0.8 km in absolute terms; both tests must pass. An excess greater than 50% of optimal_distance_km, or greater than 8.0 km absolute, is additionally a MATERIAL deviation and requires the driver_profile check in POL-RD-06. Materiality is assessed on the excess REMAINING after any adjustment under POL-RD-03, POL-RD-04, POL-RD-05 or POL-RD-12, not on the excess as first measured. If either establishment test fails, no deviation exists and the outcome is NO_ACTION however the rider characterises the trip, save for a billing-integrity refund under POL-RD-09(4), which is available whether or not a deviation exists.

### POL-RD-02

Where a deviation is established under POL-RD-01 and no exculpatory clause fully excuses it, the refund is arithmetic, not discretionary. This clause applies only where fare_breakdown.fare_model is METERED; for UPFRONT_QUOTE trips POL-RD-11 governs instead. Compute recomputed_fare = ((3.80 + 0.75 x optimal_distance_km + 0.28 x optimal_duration_min) x the surge_multiplier recorded on the FARE_BREAKDOWN) + 0.80 platform fee + ERP and toll charges for gantries lying on the optimal route + any fixed surcharge already itemised in the fare_breakdown and properly chargeable (for example the Changi Airport surcharge on a trip ORIGINATING at the airport) + fare_breakdown.waiting_time_fee - fare_breakdown.promo_discount. Refund = charged_total - recomputed_fare, floored at zero, and the payable figure is rounded UP to the nearest SGD 0.05; intermediate values are not rounded. If the refund is below SGD 0.50 the outcome is NO_ACTION as de minimis. If the refund is 90% or more of charged_total, issue FULL_REFUND instead of a partial. Where POL-RD-03, POL-RD-04, POL-RD-05 or POL-RD-12 excuses part of the excess, run this computation against the adjusted optimal route rather than the booked one. The ruling must state charged_total, recomputed_fare and the refund on separate lines.

### POL-RD-04

A deviation is EXONERATED to the extent it is attributable to a rider instruction recorded in the chat_log. The instruction must (a) come from the rider, (b) be timestamped before the vehicle leaves the optimal corridor or no more than 3 minutes after, and (c) identify a place or road specifically enough to act on, such as 'stop at Jurong Point first' or 'take the AYE, not the PIE'. The gps_trace must corroborate it: the vehicle passes within 200 m of the requested waypoint, or travels the requested road. The waypoint coordinate is taken from chat_message.waypoint_hint, which the platform resolves from the message text at ingest; the Judge and both advocates must use that field and must not geocode a place name from general knowledge. Where waypoint_hint is null and no road is named, the corroboration test is undecidable on the record: the clause is unavailable, the case is decided on the remaining clauses, and the ruling must say the test could not be run. The excess distance between leaving and rejoining the optimal corridor is then excluded before POL-RD-01 and POL-RD-02 are applied. Vague messages such as 'go the fast way' or 'you know better' do not exonerate. Separately, where the fare_breakdown shows the rider was billed for less distance than the gps_trace records and the shortfall exceeds 1.0 km, the driver may be granted DRIVER_COMPENSATION at SGD 0.75 per unbilled kilometre, rounded UP to the nearest SGD 0.05 and capped at SGD 15.00 per trip.

### POL-RD-06

Consult the driver_profile whenever POL-RD-01 records a MATERIAL deviation, or the evidence is otherwise finely balanced. A pattern is ESTABLISHED when driver_profile.deviation_flags_90d is 3 or more, or driver_profile.deviation_flags_90d divided by driver_profile.completed_trips_90d is 0.05 or more with completed_trips_90d of at least 40. No other profile field may be used for this test; in particular driver_profile.prior_deviation_flags is a lifetime counter and is NOT the trailing-90-day figure this clause asks for. Where a pattern is established, and only these three effects follow: (a) if the evidence is genuinely balanced and the rider's claim is supported by at least one artifact other than the gps_trace, the balance is resolved in the rider's favour; (b) a deviation that is both MATERIAL and substantiated on this trip's own evidence licenses FULL_REFUND of charged_total rather than the POL-RD-02 partial, save that government-set and third-party pass-through lines (ERP, tolls, a properly chargeable airport surcharge) are settled under POL-RD-09 and are not uplifted by this limb, and the ruling must state the POL-RD-02 figure and the uplifted figure side by side so the size of the uplift is visible and auditable; (c) the case is additionally REFERRED to driver-conduct review, which is recorded in the ruling's referrals list and does not displace or delay the monetary ruling. A pattern may never be used to establish that this particular trip deviated; that finding must rest on POL-RD-01 evidence for this trip alone, and POL-GEN-01 applies to every use of this artifact.

### POL-RD-07

The gps_trace is IMPAIRED FOR POLICY PURPOSES under this clause if, within the disputed segment, it contains (a) a gap of more than 90 seconds between consecutive fixes, (b) a straight-line jump of more than 500 m between consecutive fixes, or (c) a sustained sampling interval above 30 seconds. An artifact tagged IMPAIRED by the admissibility pre-pass but NOT meeting limbs (a) to (c) of this clause is down-weighted in the Judge's confidence under POL-GEN-02 only, and does not trigger the consequences below or POL-RD-10(3). Where the trace is impaired under (a) to (c): (i) excess distance across the impaired stretch is measured as the straight line between the bounding fixes, which is the reading most favourable to the driver; (ii) a deviation may NOT be established on the gps_trace alone and must be corroborated by an INDEPENDENT source, which means one of - a driver admission in the chat_log; the set of erp_gantries actually charged in the fare_breakdown placing the vehicle on a corridor the optimal route does not use; a counterparty_statement admitting the route; or a trip_record.actual_distance_km the platform derived independently of this trace. The billed distance on the fare_breakdown is NOT independent corroboration where it is a copy of the trace figure, and the Judge must check whether it is before relying on it; (iii) if no corroboration exists, the claim is not sustained on the present record and the outcome is ESCALATE rather than NO_ACTION, because absence of proof here is a data failure and not a finding for the driver. Any ruling that touches an impaired trace must say so in its explanation and state which corroborating artifact carried it.

### POL-RD-09

Charges that merely pass through a third-party or government-set cost are settled separately from distance and time charges, and are never counted twice. (1) Where a deviation is refunded under POL-RD-02, off-route ERP is ALREADY COMPREHENDED in that refund, because the refund is charged_total less a recomputed fare that includes only on-optimal-route gantries. Such charges are itemised separately in the ruling for transparency but must NEVER be added on top of the POL-RD-02 figure. (2) Where the deviation is exonerated as an external event under POL-RD-03, the distance and time charges stand because the driver is not at fault, but off-route ERP charges are still refunded to the rider as a standalone pass-through correction, capped at SGD 12.00 per trip, since the rider did not cause the closure either. (3) Where the detour was rider-caused under POL-RD-04, POL-RD-05 or POL-RD-12, no ERP refund is due. (4) A charge line for a gantry the gps_trace never passes, or an airport surcharge on a trip that does not ORIGINATE at an airport, is a billing-integrity failure: it is refunded in full as a standalone correction, available whether or not a deviation exists, and recorded as a billing-integrity finding in the ruling's referrals list. POL-RD-10(8) is NOT thereby triggered where the only unmatched line is one refunded under this limb. A gantry is matched to the trace by comparing erp_gantry.lat and erp_gantry.lng against the trace, treating any fix within 250 m of the gantry as a crossing; where an erp_gantry carries no coordinates the match is undecidable on the record, the line is treated as matched, and the ruling must say so.

### POL-RD-10

The Judge must NOT issue a final ruling, and must instead ESCALATE to a human reviewer with the full case summary, both advocate briefs and the admissibility report, whenever any of the following holds: (1) the Judge's own confidence in the ruling is below 0.70, which is the platform-wide floor and is identical to POL-NS-09(a); (2) the trip identifiers on trip_record, gps_trace and fare_breakdown do not all match, or the trip_record is absent from the pool; (3) the gps_trace is impaired under limbs (a) to (c) of POL-RD-07 and no corroborating artifact of the kind POL-RD-07(ii) names exists; (4) pickup or dropoff timestamps on two admitted artifacts disagree by more than 10 minutes, or any artifact's timestamps run backwards; (5) an exculpatory clause is invoked against a cited artifact that is missing from the pool, or does not cover the trip window, or lacks the field the clause requires - for example a rider-requested detour asserted with no chat_log for the trip, a closure asserted with no traffic_advisory, or a POL-RD-05 amendment with amended_optimal_distance_km null; (6) the refund computed under POL-RD-02 exceeds SGD 150.00, or exceeds charged_total; (7) both sides are supported by admissible and mutually contradictory evidence of comparable strength, such as a chat_log detour request whose waypoint the gps_trace never approaches; (8) any charge line in the fare_breakdown has no counterpart anywhere in the gps_trace or trip_record, OTHER than a line refunded under POL-RD-09(4). Escalation under this clause is TERMINAL: it replaces the ruling, no monetary outcome issues, and the disputed amount is held rather than collected or refunded. The Judge must name the trigger that fired and state what evidence would resolve it. A referral under POL-RD-06(c) or POL-RD-09(4) is not an escalation and does not engage this clause.

### POL-RD-11

Where fare_breakdown.fare_model is UPFRONT_QUOTE and fare_breakdown.quoted_fare_sgd is non-null, the distance and time charges were fixed at booking and a detour costs the rider nothing on those lines; the loss falls on the driver. POL-RD-02 does not run and no distance-or-time refund is available to the rider however large the excess. The rider's remedies are limited to: (a) any amount by which charged_total exceeds quoted_fare_sgd plus the pass-through and statutory lines properly chargeable under POL-RD-09 - ERP and tolls actually crossed, a properly chargeable airport surcharge, and fare_breakdown.waiting_time_fee - which is refunded in full; and (b) a pass-through correction under POL-RD-09 for off-route or phantom gantries and for a surcharge wrongly applied. The driver's unrecovered cost on an unjustified detour is not recoverable from the rider under this clause; where the detour was rider-requested it is compensated under POL-RD-04 instead. A MATERIAL deviation on an upfront-quoted trip still requires the POL-RD-06 driver_profile check and still supports a POL-RD-06(c) conduct referral, because the conduct is the same even though the money is not.

### POL-RD-12

Where trip_record.vehicle_type is RYDE_POOL, the baseline for POL-RD-01 is the MATCHED-ITINERARY optimal recorded in trip_record.optimal_distance_km - the route the platform computed for the pooled itinerary at match time - and not the solo-rider optimal, which is carried separately as trip_record.solo_optimal_distance_km for reference only. Distance attributable to collecting or setting down a co-rider on a platform-matched pooled itinerary is never a deviation and is excluded from excess before POL-RD-01 is applied. A claim that measures excess against solo_optimal_distance_km has cited the wrong field and fails on that ground alone; the ruling must name both figures so the rider can see why. This clause does not excuse excess beyond the matched itinerary: where the trace exceeds the matched-itinerary optimal by more than the POL-RD-01 threshold, the deviation is established as usual and POL-RD-02 runs against the matched-itinerary figure. Where solo_optimal_distance_km is non-null but the trip_record does not identify the pooled itinerary, the record is incomplete and POL-RD-10(5) applies.

### POL-RD-14

Where a rider instruction in the chat_log meets POL-RD-04(a) to (c) but the gps_trace does not corroborate it - the vehicle never passes within 200 m of the waypoint named by chat_message.waypoint_hint and never travels the requested road - the instruction did not cause the measured excess: POL-RD-04 does not apply, no distance is excluded, and the deviation is decided under POL-RD-01 and POL-RD-02 on the trace as measured. This is not the contradiction POL-RD-10(7) describes: a request that was made and a route that did not follow it are consistent with each other, and the driver's reliance on the request is an assertion that fails on the trace, not evidence of comparable strength against it. POL-RD-10(7) is engaged only where the trace corroborates the instruction in part, so that the excess attributable to it cannot be separated from the rest. The ruling must state that the instruction was found and that the trace did not corroborate it.
