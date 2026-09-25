# The mechanical citation referee

**2026-09-25.** This is a no-model-call audit of the referee over the latest recorded advocate outputs in both development sets. It was run before any new benchmark invocation.

## Agreement

| set | claim decisions agreeing | total claim decisions | agreement |
|---|---:|---:|---:|
| corpus | 464 | 502 | 92.4% |
| codex | 237 | 246 | 96.3% |
| **overall** | **701** | **748** | **93.7%** |

There are **47 difference groups**. Duplicate claim text is counted by occurrence; the agreement denominator is the 748 referee-ledger entries, not the number of unique claim strings.

Of the 46 differences adjudicated REFEREE RIGHT, **23** are `IMPAIRMENT_UNDISCLOSED` on an artifact whose status is `MISSING`: the claim's text says the artifact is missing, carrying the word "missing" but never the code `MISSING_ARTIFACT`.

## Differences

The referee and judge decisions below are shown with both reasons. `KEPT` means the side has no recorded discard for that claim. The adjudication applies the stated mechanical boundary: the referee checks the structured evidence citations and `relies_on`; the judge may still add a semantic discard that code cannot check.

### 1. corpus case 101 — RIDER

**Claim:**

> No closure excuses any of this detour. The traffic advisory artifact for this trip, EV-ADVIS-00101-01, is MISSING with weight 0.0: no LTA advisory was issued for the AYE/MCE/ECP corridor in the 10:14-10:59 window. With no advisory there is no road named, no validity window and no shortest_lawful_alternative_km, so POL-RD-03 cannot be run and none of the 6.18 km excess is exonerated. The absence is itself the citable fact.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00101-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 2. corpus case 105 — RIDER

**Claim:**

> The driver's only possible exculpation — heavy traffic on the PIE — depends on a traffic advisory. The sole advisory artifact, EV-ADVIS-00105-01, is MISSING: it has no payload and carries weight 0.0. No advisory names a road the optimal route traverses, so POL-RD-03 exoneration is unavailable, and the driver's unsupported assertion does not discharge his burden under POL-RD-08.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00105-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 3. corpus case 105 — DRIVER

**Claim:**

> The driver's rating (4.31), cancellation rate, acceptance rate, lifetime_trips and lifetime prior_deviation_flags (6) are context only under POL-GEN-01 and may never ground an adverse finding against him; only deviation_flags_90d and completed_trips_90d may be used, and only for the POL-RD-06 test. Any reasoning from the driver's reputation rather than from this trip's own trace must be discarded.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-DPROF-00105 at weight_multiplier 0.75 but does not name its issue code(s): STALE_SNAPSHOT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 4. corpus case 107 — RIDER

**Claim:**

> No closure or advisory exoneration is available. The only traffic advisory in the bundle, EV-ADVIS-00107-01, is MISSING at weight 0.0: no congestion advisory was issued for the CTE on the evening of 18 July 2026, and the driver's assertion that CTE was jammed names no artifact. POL-RD-03 requires an advisory that names a road or segment the optimal route traverses and carries a validity window overlapping the pass; there is none, so no excess is exonerated and no closure-adjusted optimal route may be constructed.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00107-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 5. corpus case 107 — RIDER

**Claim:**

> The burden has shifted to the driver and he has not discharged it. POL-RD-08 requires the driver, once the rider has shown the excess, to point to a specific artifact and a specific clause to excuse it, and it states expressly that a general assertion that traffic was bad, unsupported by a traffic_advisory ID, does not discharge that burden. The driver's chat reply and his counterparty statement both assert a jam, but cite no advisory, and the advisory artifact EV-ADVIS-00107-01 is missing from the record. The 3.57 km excess therefore stands unexplained.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00107-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 6. corpus case 108 — RIDER

**Claim:**

> No traffic advisory covers this trip: EV-ADVIS-00108-01 is MISSING and carries weight 0.0, so POL-RD-03 exonerates not a metre — there is no named road, no validity window and no shortest_lawful_alternative_km on which to run its cap formula. The rider cites the absence itself, which is a legitimate argument on this bundle.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00108-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 7. corpus case 110 — RIDER

**Claim:**

> The dropout is not an incidental gap at the edge of the trip. It runs from the Defu Flyover portal fix to the Kallang portal fix, a 6.90 km straight line, and so covers the entire KPE tunnel stretch that the rider actually disputes. The one part of the route whose length decides this case is precisely the part this trace cannot measure, which is why the straight-line reconstruction is the driver-favourable reading POL-RD-07(i) mandates and not a finding about what was driven.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00110 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 8. corpus case 110 — RIDER

**Claim:**

> With the trace impaired under POL-RD-07(a) to (c) and no POL-RD-07(ii) corroboration anywhere in the bundle, POL-RD-07(iii) directs ESCALATE rather than NO_ACTION: absence of proof on a broken trace is a data failure, not a finding for the driver. POL-RD-10(3) makes escalation mandatory on the same facts. Under POL-GEN-03 an escalated amount is held rather than collected, so escalation is the outcome that leaves the rider not carrying the disputed charge.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00110 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 9. corpus case 110 — RIDER

**Claim:**

> Independently of any corroboration question, the fact that decides this case is carried by an artifact at weight 0.39. Under POL-GEN-02(2) confidence may not exceed the weight of the artifact carrying the deciding fact, and the discount is not rescued by the trip record, because that artifact is derived from the same trace and is therefore not independent. A cap of 0.39 is below the 0.70 platform floor, so POL-RD-10(1) requires escalation on that ground alone.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00110 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 10. corpus case 110 — RIDER

**Claim:**

> The threshold question itself is undecided on this record and the case cannot be closed out. Measured the driver-favourable way that POL-RD-07(i) requires - the straight line across the gap - the trip is 21.20 km against an optimal of 18.40 km, an excess of 2.80 km and 15.2%, just under POL-RD-01's 20% establishment gate. The admissibility assessment on the same artifact records that a surface route between the same two portals would put the trip at 25.50 km and over that gate. Nothing in the bundle distinguishes the two readings, so a NO_ACTION that treats 21.2 km as settled fact would be resting on the very reconstruction the gap makes unreliable.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00110 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 11. corpus case 110 — RIDER

**Claim:**

> The driver has pointed to no clause and no artifact to exculpate the route. His assertion that he 'took the KPE like always' is a general assertion about the road he used, and POL-RD-08 requires a specific artifact and a specific clause; a general assertion unsupported by a traffic_advisory ID does not discharge the driver's burden. The only traffic advisory in the bundle, EV-ADVIS-00110-01, is MISSING at weight 0.0 - no LTA advisory covers the KPE or the ECP in the 18:19-19:02 window - so POL-RD-03 closure exoneration has nothing behind it and cannot run.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00110-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 12. corpus case 110 — RIDER

**Claim:**

> No clause in this policy licenses 'my phone loses signal in the tunnel' as a reason to stand over the distance and time charged. The lost signal may explain the gap in the trace; it does not explain 2.80 km of driving beyond the platform's own optimal route, and it is not an exoneration under POL-RD-03, POL-RD-04, POL-RD-05 or POL-RD-12. It is relevant here only because it confirms the trace, not the route, is the thing that failed.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00110 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 13. corpus case 110 — DRIVER

**Claim:**

> The rider carries the initial burden under POL-RD-08 and must show an excess meeting the POL-RD-01 threshold measured from an unimpaired gps_trace or, where the trace is impaired under POL-RD-07(a) to (c), from an independent source named in POL-RD-07(ii). The trace is impaired - a 428.0 s gap and coverage of 81.7% - and no source in POL-RD-07(ii)'s list exists on this record. The second limb of the rider's burden is therefore not discharged and the driver is never put to an exculpatory clause at all.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00110 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 14. corpus case 113 — RIDER

**Claim:**

> No exculpatory clause other than POL-RD-12 is open to the driver on this record, so the remaining excess beyond the matched itinerary is unexplained by any clause he can invoke. EV-ADVIS-00113-01 is MISSING, carries no payload and has an admissibility weight of 0.0 - the impairment is disclosed here as POL-GEN-02 requires - so there is no traffic advisory naming the Punggol, Hougang or CTE corridor in the 18:41-19:23 window and no POL-RD-03 closure exoneration is available. The three messages in EV-CHAT-00113 contain no rider instruction to detour and every waypoint_hint is null, so POL-RD-04 cannot be run on this record. The trip_record shows no amended pickup or dropoff and no amended optimal distance, so POL-RD-05 has nothing to re-quote.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00113-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 15. corpus case 113 — DRIVER

**Claim:**

> No traffic advisory covers the Punggol, Hougang or CTE corridors in this window — EV-ADVIS-00113-01 is MISSING and carries weight 0.0 — and the driver does not need one. The exoneration relied on is POL-RD-12, the platform's own matched pooled-itinerary baseline, not POL-RD-03. No closure is asserted, so the absence of an advisory costs this defence nothing; it is cited only so the absence is on the record.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00113-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 16. corpus case 202 — DRIVER

**Claim:**

> POL-NS-06's premature-cancellation refund is not triggered: the effective in-geofence dwell of 620 seconds exceeds the 480-second AIRPORT minimum, so there is no shortfall to refund. Because the plain dwell already suffices, the driver does not need the limb (i) advisory-accumulation route, and the MISSING traffic advisory EV-ADVIS-00202-01 — which carries weight 0.0 — is immaterial to the outcome either way. That absence is citable but nothing turns on it here.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00202-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 17. corpus case 202 — DRIVER

**Claim:**

> The ruling this record supports is DRIVER_COMPENSATION, not NO_ACTION. POL-NS-07 pays the driver, and under POL-GEN-03 the emitted ruling is DRIVER_COMPENSATION with amount_sgd mirroring driver_compensation_sgd at SGD 4.80, while the filing rider's own charge stands as it presently is. The driver's counterparty statement — that he waited past ten minutes at Door 5 and lost the airport queue — is corroborated by the trace, not merely asserted.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-DPROF-00202 at weight_multiplier 0.9 but does not name its issue code(s): SCHEMA_VERSION_MISMATCH

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 18. corpus case 203 — RIDER

**Claim:**

> The driver cannot repair the shortfall by accumulating separate in-geofence intervals. There is only one such interval on this trace (run_count 1, longest run 195 seconds), and POL-NS-06 limb (i) in any event requires a traffic advisory that is present and populated with a type of KERB_RESTRICTION, ENFORCEMENT, CLOSURE or ACCIDENT. EV-ADVIS-00203-01 is MISSING — its weight is 0.0 and the absence is itself citable — so no advisory covers this pickup road in this window, limb (i) is unavailable, and the 195-second measurement stands as the effective dwell.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00203-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 19. corpus case 206 — RIDER

**Claim:**

> The trace's schema-level impairment is not a policy-level impairment and should not push this case to a reviewer. No limb of POL-NS-08 bites: the largest sampling interval is 26 s against the 120 s gap threshold and the gaps list is empty; the trace holds 52 fixes against the 6-fix minimum and 31 rider fixes; the chat log's 2 messages match trip_record.chat_message_count of 2 with contiguous msg_ids; and the 4.00 cancellation fee reconciles with the LARGE_VENUE zone fee and the RYDE_X tier fee, so there is no fare defect. POL-GEN-02's confidence cap is therefore not dragged below the 0.70 floor, and in any event the deciding fact is carried on two independent artifacts - the GPS trace at 0.8 and the trip record at 1.0 - so the cap is the maximum, 1.0. No limb of POL-NS-09 is engaged and the case is decidable on the papers.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00206 at weight_multiplier 0.8 but does not name its issue code(s): LOW_SAMPLE_RATE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 20. corpus case 209 — RIDER

**Claim:**

> The driver's second message at 07:44:20 - 'boss? cannot wait very long here, this bay cannot park' - is not a substitute for the advisory POL-NS-06(i) requires. A kerb or bay restriction asserted only in free text, against a traffic_advisory artifact that is MISSING, cannot extend or excuse the required dwell. I disclose that the chat log is impaired: weight 0.85, issue UNREAD_MESSAGE (both driver messages and the system arrival notice carry read_at null), which is why I rest this point on the policy's demand for a populated advisory rather than on the message alone.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00209-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 21. corpus case 209 — DRIVER

**Claim:**

> EV-ADVIS-00209-01 is MISSING with weight 0.0 — no advisory records a kerb restriction, enforcement, closure or accident at this bay in this window — so POL-NS-06(i) interval summing is unavailable on this record, and in any event a single in-geofence interval (run_count 1, excursions empty) gives limb (i) nothing to add. I state the absence and do not assert the limb against a missing artifact.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00209-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 22. corpus case 210 — RIDER

**Claim:**

> No time can be added to that dwell. POL-NS-06 limb (i) permits separate in-geofence intervals to be summed only where a present and populated traffic_advisory of type KERB_RESTRICTION, ENFORCEMENT, CLOSURE or ACCIDENT covers the pickup road. The advisory artifact for this trip, EV-ADVIS-00210-01, is MISSING - no payload, weight 0.0 - so limb (i) is unavailable, no advisory can extend the driver's clock, and the derived facts record no second in-geofence interval to add in any event. The absence of any advisory covering the Changi T1 arrival kerb is itself citable, and it works against this charge rather than rescuing it.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00210-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 23. corpus case 210 — RIDER

**Claim:**

> If the panel cannot close on a full refund because the two sources contradict each other, the case still cannot close as a charge against the rider. The trace is impaired under POL-NS-08(b) - a 186-second gap straddling entry, fewer than six fixes across the waiting window, and rider_track omitted - and under POL-NS-08(a) on the 228-second clock skew; the chat log is impaired under POL-NS-08(c), carrying 2 of the 4 messages the trip record records for the 23:42-23:49 window (weight 0.60, TRUNCATED_LOG). The deciding fact is therefore carried only by artifacts of weight 0.25 and 0.40, so under POL-GEN-02 rule (2) confidence cannot exceed 0.40, below the 0.70 floor, and POL-NS-09 limbs (a), (b) and (e) all engage. Escalation holds the fee rather than collecting it - EV-FARE-00210 shows payment_status PENDING and refund_issued_sgd 0.00 - so on that footing too the rider does not carry the disputed charge.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-TRIP-00210 at weight_multiplier 0.4 but does not name its issue code(s): CROSS_SOURCE_CONFLICT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 24. corpus case 210 — DRIVER

**Claim:**

> The driver reached the pickup geofence. EV-GPS-00210's derived driver_track puts his nearest approach at 96.01 m from the pickup pin at Changi Terminal 1 — inside the 150 m arrival radius POL-NS-02 sets for the AIRPORT zone class — and the derived arrival block records 5 consecutive qualifying in-geofence fixes against the 3 consecutive in-radius fixes POL-NS-02 requires. I disclose that EV-GPS-00210 is IMPAIRED at weight 0.25 on CLOCK_SKEW, GPS_GAP, LOW_COVERAGE, TRUNCATED_LOG, LOW_SAMPLE_RATE and PARTIAL_RECORD; the proximity and fix-count findings survive the discount because clock skew and truncation displace timestamps, not measured distances between fixes and the pin.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-TRIP-00210 at weight_multiplier 0.4 but does not name its issue code(s): CROSS_SOURCE_CONFLICT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 25. corpus case 210 — DRIVER

**Claim:**

> POL-NS-01 limb (b) is satisfied, or at worst undecidable — it is not affirmatively failed. The record's arrived event is 23:42:10 and the first qualifying in-geofence fix is 23:42:21, an eleven-second offset. EV-GPS-00210's own admissibility report measures a device clock skew of 228 seconds, twenty times that offset, so eleven seconds cannot establish that the driver was outside the geofence when he marked arrival. Read with the skew correction the same fix maps to 23:38:33 server time, some three and a half minutes before the marker. I rely on derived.arrival.dwell_start_offset_sec, which is precisely the field the skew contaminates, and I disclose that both artifacts are impaired: EV-TRIP-00210 at weight 0.4 on CROSS_SOURCE_CONFLICT and EV-GPS-00210 at weight 0.25 on the six codes set out above.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00210 at weight_multiplier 0.25 but does not name its issue code(s): CLOCK_SKEW, GPS_GAP, LOW_COVERAGE, TRUNCATED_LOG, LOW_SAMPLE_RATE, PARTIAL_RECORD

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 26. corpus case 210 — DRIVER

**Claim:**

> The rider's POL-NS-06 shortfall case cannot be run on this trace, so no shortfall is established. EV-GPS-00210 covers 22.8% of the active window, holds a 186-second sampling gap sitting directly across the moment of geofence entry (23:39:15 to 23:42:21), and stops at 23:46:36 — 149 seconds before the cancellation at 23:49:05, over the 120-second truncation tolerance. Any dwell figure read off it is a floor rather than a measurement, and POL-NS-02 and POL-NS-08(b) say expressly that fixes too sparse to carry the test are impairment, not proof of absence. The artifact is IMPAIRED at weight 0.25 on CLOCK_SKEW, GPS_GAP, LOW_COVERAGE, TRUNCATED_LOG, LOW_SAMPLE_RATE and PARTIAL_RECORD.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-TRIP-00210 at weight_multiplier 0.4 but does not name its issue code(s): CROSS_SOURCE_CONFLICT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 27. corpus case 210 — DRIVER

**Claim:**

> The trip record's own wait_time_min of 6.9 does not establish a shortfall either. That figure is arrived_at 23:42:10 to cancelled_at 23:49:05, and arrived_at is the very event the trace contradicts; the artifact is IMPAIRED at weight 0.4 on CROSS_SOURCE_CONFLICT for exactly that reason. I do not ask the bench to convert the driver's own 'more than eight minutes' into 480 seconds on his say-so — I ask only that a number resting on a contested timestamp be given no weight in either direction.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00210 at weight_multiplier 0.25 but does not name its issue code(s): CLOCK_SKEW, GPS_GAP, LOW_COVERAGE, TRUNCATED_LOG, LOW_SAMPLE_RATE, PARTIAL_RECORD

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 28. corpus case 210 — DRIVER

**Claim:**

> The rider cannot be exonerated under POL-NS-04, which requires all three of its limbs. Limb (a) needs a locating or coordinating message during the waiting window; the only rider message on the export is MSG-00210-004 at 23:49:40, thirty-five seconds after the driver terminated the trip at 23:49:05. Limb (c) cannot be satisfied at all: EV-GPS-00210 carries no rider_track, so the presence test is undecidable, and POL-NS-04's own text makes an undecidable limb (c) neutral — neutral is not satisfied, and a clause requiring all three limbs exonerates nobody on two. EV-CHAT-00210 is IMPAIRED at weight 0.6 on TRUNCATED_LOG, messages 002 and 003 being absent from the 23:42 to 23:49 window, so the export is not a complete picture; but it is the only chat evidence in the bundle, and on it limb (a) is not made out.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-TRIP-00210 at weight_multiplier 0.4 but does not name its issue code(s): CROSS_SOURCE_CONFLICT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 29. corpus case 210 — DRIVER

**Claim:**

> EV-TRIP-00210 and EV-GPS-00210 are two admissible artifacts that contradict each other directly on arrival and on dwell — 23:42:10 with a 6.9-minute wait on one side, a first qualifying in-geofence fix at 23:42:21 with a 255-second qualifying run and 22.8% coverage on the other — and no clause in this policy resolves which is right. The sole evidence for the deciding fact is impaired under POL-NS-08 limbs (a) and (b), which on that clause's own terms caps the ruling and sends the case to a reviewer under POL-NS-09. Escalation holds the SGD 6.00 fee on its present PENDING status rather than refunding it, which is the disposition the evidence actually supports.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-TRIP-00210 at weight_multiplier 0.4 but does not name its issue code(s): CROSS_SOURCE_CONFLICT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 30. corpus case 210 — DRIVER

**Claim:**

> No traffic advisory covers the Changi Terminal 1 arrival kerb in this window. EV-ADVIS-00210-01 is MISSING, keeps its identifier and carries weight 0.0, and the absence is itself citable. It means the record discloses no kerbside restriction, enforcement operation, closure or accident on the pickup road — nothing on the ground that would explain a driver unable to hold at the pin, and nothing that displaces the driver's account of waiting at Door 6.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-00210-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 31. corpus case 211 — RIDER

**Claim:**

> The admissibility pre-pass on EV-GPS-00211 records a 168 s outage from 12:33:40 to 12:36:28 falling inside the waiting window, and states in terms that whether the driver stayed put across those 168 seconds is not established by this trace. A sampling gap over 120 s inside the waiting window is a trace defect under POL-NS-08(b), so any dwell finding that depends on reading the outage as presence is down-weighted under POL-GEN-02 as well as at schema level. The rider's shortfall point does not depend on the gap at all: it stands on the two intervals that were actually measured.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00211 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 32. corpus case 211 — RIDER

**Claim:**

> The driver's 12:35:10 message, 'boss still here waiting ah, cannot see you', shows he was still working the pickup during the outage, but it is his own unsworn assertion and carries no coordinates. POL-NS-01(c) requires the gps_trace to hold the driver inside the geofence for the dwell, and the chat log records nothing about position; a chat message cannot bridge a 168 second trace gap that the trace itself cannot bridge, and it is in any event a statement about his own conduct rather than a fix. The chat log is otherwise clean - five entries, matching trip_record.chat_message_count of 5, weight 1.0 - so the driver has no chat-side defect to complain of either.

**Decision counts:** referee discarded 0 of 1 occurrence(s); judge discarded 1.

**Referee reason(s):**
- `KEPT` — all mechanical referee checks passed.

**Judge reason(s):**
- Cites EV-GPS-00211, whose weight_multiplier is 0.39 (issue codes GPS_GAP and LOW_COVERAGE), without disclosing the impairment or naming the issue codes. Discarded under POL-GEN-02(1).

**Adjudication:** JUDGE RIGHT: the judge identified a further semantic ground that the mechanical referee cannot infer from evidence_ids alone; the claim's prose relies on an impaired artifact it did not cite, so the judge may add this discard after the referee.

### 33. corpus case 211 — RIDER

**Claim:**

> The rider was at the pickup and not absent: her device logged 36 of 55 fixes inside the 100 m STANDARD presence radius (mean 81.8 m, closest 24.6 m), and she messaged 'coming down now, 2 min' at 12:31:02, read by the driver at 12:31:15. I disclose that those positions come from EV-GPS-00211, impaired at weight 0.39. Her conduct is in any event not the test: POL-NS-06 refunds the fee whether or not the rider was present and whether or not she responded to messages. I note candidly that POL-NS-04 is not available to her, because the driver did reply at 12:31:20, inside the 120 second window that limb (b) of that clause requires.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00211 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 34. corpus case 211 — RIDER

**Claim:**

> If the judge prefers the driver's reading and treats the 168 s outage as presence, the deciding fact - whether the driver held the geofence across that interval - is then carried by no usable evidence at all: the only artifact bearing on it is EV-GPS-00211, impaired under POL-NS-08(b) at weight 0.39, which caps confidence below the 0.70 platform floor under POL-GEN-02(2), requires under POL-NS-08 that the ruling not exceed PARTIAL_REFUND, and escalates under POL-NS-09 with the disputed $4.00 held rather than collected or refunded while review is pending. On no reading of this record does the rider end up funding this charge.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00211 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 35. corpus case 211 — DRIVER

**Claim:**

> Even on the reading most favourable to the rider, this case cannot produce a rider refund. The dwell finding is carried by a single artifact, EV-GPS-00211, and that artifact is impaired under POL-NS-08(b) itself, not merely at schema level: a 168 second sampling gap inside the waiting window exceeds the 120 second limb, which is the same defect the pre-pass tagged at weight 0.39. Where the sole evidence for the deciding fact is impaired under limbs (a) to (d), the ruling may not exceed PARTIAL_REFUND and the case escalates under POL-NS-09; escalation holds the disputed SGD 4.00 rather than collecting or refunding it, so the charge is not reversed while the human reviewer settles whether the driver held the kerb across the outage.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00211 at weight_multiplier 0.39 but does not name its issue code(s): GPS_GAP, LOW_COVERAGE

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 36. corpus case 213 — RIDER

**Claim:**

> Under POL-NS-02 the arrival question is arithmetic rather than impressionistic: where the gps_trace contains no qualifying in-radius fix in the 15 minutes preceding the cancellation, the driver never arrived, limb (b) fails, and the rider is entitled to a full refund of the cancellation fee. EV-GPS-00213 contains no fix at all — it is absent and carries weight 0.0 — so it cannot contain a qualifying in-radius fix, and the $6.00 cancellation-fee line itemised on EV-FARE-00213 must be refunded in full to the rider.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00213 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 37. corpus case 213 — RIDER

**Claim:**

> The facts that decide this case — arrival, dwell and rider presence — are carried solely by EV-GPS-00213 and EV-CHAT-00213, each at weight 0.0. Under POL-GEN-02(2) the Judge's confidence may not exceed the weight of the artifacts that carry the deciding fact, so it is capped at 0.0, far below the 0.70 platform floor that POL-NS-09(a) enforces. Escalation — which holds the fee rather than collecting a sum no admissible evidence supports — is the correct disposition.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00213 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 38. corpus case 213 — DRIVER

**Claim:**

> The rider's presence at the pin is equally unestablished. With no trace at all there is no rider_track, and POL-NS-04(c) itself provides that where rider_track is absent limb (c) is UNDECIDABLE and neutral, the artifact being impaired, and that the tribunal must say the test could not be run rather than inferring the rider was elsewhere — or, by the same logic, that she was there. Her account of standing at the bay from 5.45 is corroborated by nothing in this bundle.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-00213 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 39. codex case 9101 — DRIVER

**Claim:**

> POL-NS-06 does not engage, and no shortfall exists to excuse. The effective in-geofence dwell computed under POL-NS-02 is 320 seconds against a 300 second STANDARD minimum, a surplus of 20 seconds on the derived shortfall figure. Because the minimum was met without accumulation, limb (i) is never reached. Consistently with that, the driver does not rely on the traffic advisory limb: EV-ADVIS-09101-01 is MISSING with weight 0.0, and it is immaterial here precisely because no accumulation is claimed.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-09101-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 40. codex case 9104 — RIDER

**Claim:**

> No traffic advisory covers this pickup road and waiting window. EV-ADVIS-09104-01 is MISSING at weight 0.0, so its absence is itself citable: there is no KERB_RESTRICTION, ENFORCEMENT, CLOSURE or ACCIDENT on file, and nothing in the record explains the driver's 559 m standoff from the pickup point as a lawful reason to hold off the kerb.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-09104-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 41. codex case 9109 — RIDER

**Claim:**

> POL-NS-02 deems the driver to have ARRIVED only where the gps_trace contains at least three consecutive fixes accurate to 25 m or better inside the 150 m arrival radius for this TRANSPORT_HUB pickup pin at Woodlands MRT. With EV-GPS-09109 MISSING at weight 0.0 there is not a single qualifying in-radius fix on this record, so no deemed arrival exists and POL-NS-01(b) fails on POL-NS-02's own terms. I do not overstate this: an absent trace is not proof the driver was elsewhere. But the condition is drafted conjunctively and the required artifact is the driver's to produce; absence of the very evidence the clause names cannot discharge that limb.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-09109 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 42. codex case 9109 — RIDER

**Claim:**

> Independently of arrival, POL-NS-01(c) measures the TRANSPORT_HUB minimum dwell of 300 seconds from the FIRST qualifying in-geofence GPS fix, not from the driver's 'arrived' tap, and POL-NS-06 defines the effective in-geofence dwell the same way. The 5.3 minutes recorded in trip_record.wait_time_min is the driver's own marker and runs from his arrival tap; it is not an in-geofence measurement. With EV-GPS-09109 missing there is no in-geofence interval from which an effective dwell can be computed, so limb (c) is as unevidenced as limb (b), and POL-NS-06 cannot be satisfied on this record either.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-09109 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 43. codex case 9109 — RIDER

**Claim:**

> If the Judge prefers to treat the absent trace as leaving arrival merely undecided rather than failed, POL-GEN-02(2) still caps confidence at the weight of the artifact carrying the deciding fact - 0.0 for EV-GPS-09109 - which is far below the platform-wide 0.70 floor, so POL-NS-09(a) requires escalation to a human reviewer. Escalation is terminal and holds the SGD 6.00 rather than collecting or refunding it, so even on that reading the rider is not made to carry a charge the platform has not substantiated, and the reviewer can settle it by obtaining the missing GPS export.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-09109 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 44. codex case 9109 — DRIVER

**Claim:**

> POL-NS-03 (wrong-entrance) is likewise unavailable. It requires the gps_trace to show the driver stationary for the required dwell at a point outside the POL-NS-02 arrival radius but not more than 400 m from the pin, and the trace is MISSING (weight 0.0). Its venue-identity corroboration needs a gps_point.venue_id and a trip_record.pickup venue_id, and no GPS fixes exist. The rider cannot convert 'I cannot see your car' into a refund without the trace.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-09109 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 45. codex case 9109 — DRIVER

**Claim:**

> The present payment state should stand. fare_breakdown shows payment_status PENDING, refund_issued_sgd SGD 0.00 and total_charged SGD 6.00, and the rider has carried no refund route: POL-NS-02, POL-NS-03, POL-NS-04, POL-NS-05 and POL-NS-06 each require a gps_trace fact this record does not contain, the trace at EV-GPS-09109 being MISSING at weight 0.0. Under POL-GEN-03 that is precisely the disposition NO_ACTION describes - the filing party's claim unsupported by the evidence and the charge left as it presently is. If the judge instead finds the geofence and dwell question undetermined because the sole artifact that could carry it is absent, the correct disposition is escalation under POL-NS-09, not a refund: escalation holds the disputed fee rather than refunding it and so does not vindicate the rider's claim.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-GPS-09109 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 46. codex case 9110 — DRIVER

**Claim:**

> POL-NS-06 gives the rider nothing. The effective in-geofence dwell is 330 seconds against the 300-second STANDARD minimum — a surplus of 30 seconds, with the shortfall field reading negative — so the waiting-period shortfall condition is simply absent and no full refund follows from it. The MISSING traffic advisory (EV-ADVIS-09110-01, weight 0.0) never becomes relevant, because no accumulation of separate intervals is needed when a single run already meets the minimum.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-09110-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

### 47. codex case 9110 — DRIVER

**Claim:**

> Nothing on this record is impaired for policy purposes under POL-NS-08: the arrival event at 06:50:20 falls on the trace's 10-second cadence with no skew, the trace has zero gaps and 34 fixes across the waiting window against a 6-fix floor, the chat log's 4 messages match trip_record.chat_message_count with no missing msg_id and no five-minute gap across the arrival marker, and the fare reconciles. The single MISSING artifact is the traffic advisory, which carries weight 0.0, can carry no fact, and is relied on by no claim on either side.

**Decision counts:** referee discarded 1 of 1 occurrence(s); judge discarded 0.

**Referee reason(s):**
- `IMPAIRMENT_UNDISCLOSED` — the claim cites impaired artifact EV-ADVIS-09110-01 at weight_multiplier 0.0 but does not name its issue code(s): MISSING_ARTIFACT

**Judge reason(s):**
- `KEPT` — no judge discard was recorded.

**Adjudication:** REFEREE RIGHT: the mechanical rule requires a claim citing an artifact with weight_multiplier below 1.0 to name at least one of that artifact's issue codes; the recorded judge kept this claim without enforcing that check.

