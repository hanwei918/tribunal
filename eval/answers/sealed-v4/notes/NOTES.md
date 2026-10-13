# tribunal-sealed-v4: working notes

## Second reading result

30 cases read by 30 fresh readers; all 30 agreed with the key on ruling, amount, driver compensation and referral clauses on the first reading. Key changes: 0. (Before this reading the shared engine's wording for a MISSING traffic advisory had been clarified after a disagreement in the development set; the sealed case files were built with that wording.)

## How the set was built

1. `generator/` holds a standard-library Python generator: `tribunal_engine.py` (shared engine, no
   cases), the set's own specs module, and `generate.py`. Each case spec states the facts of one trip
   (places, route, timings, chat, calls, fares, profiles, impairments, the parties' statements). The
   engine builds the case file from them with a fixed seed per case and derives the expected answer
   from the version-7 clauses in `derive_rd()` / `derive_ns()`. Money is `decimal.Decimal` throughout;
   the excess distance fare is deviation km x `per_km_rate_sgd`, no surge, rounded half up to the cent.
2. `check_set_v7.py` (unedited, SHA-256 as received) was run on the set until it reported 0 failures;
   its final output is `answers/check_set_output.txt`.
3. Second reading: one fresh sub-agent per case, given a folder holding only that case file and the
   four policy files (v2.1 and the three version-7 clause files), told not to open anything else, and
   asked to write its own answer. It never saw the key, the generator or the other cases. Its answers
   are in `notes/second_reading/`; `generator/compare_second_reading.py` compares them with the key on
   ruling, amount, driver compensation and the clauses named in referrals.

Regenerate with `python3 generator/generate.py <specs module> <out_dir> --canary <canary from MANIFEST>`
(run from inside `generator/`); the case files come out byte-identical.

## Readings taken where version 7 leaves room (applied the same way in both sets)

- **Missing advisory.** A TRAFFIC_ADVISORY that is MISSING is evidence that would carry "whether
  traffic justified the reroute" (named in POL-GEN-26), so where that fact decides the row the case is
  escalated under POL-GEN-26. An advisory that is present and reports no congestion is data showing
  none, so POL-RD-23's last sentence applies and the reroute is not justified. The missing-artifact
  note says the traffic feed request failed, so the record is silent rather than negative. Where the
  rider was not informed, rows (b) and (d) pay the same amount and a missing advisory does not decide.
- **Rows of POL-RD-24.** "Informed" means notice before or at the point of deviation (POL-RD-21); a
  later notice counts as not informed. Exactly 1.0 km is within tolerance ("1.0 km or less").
  Traffic-justified + informed + not agreed (objection) fits no row and is escalated, as the clause
  says. The literal gap "traffic-justified, informed and agreed, 1 km or less" is never built.
- **Verbal notice.** A driver's claim of verbal notice with no call recording "cannot be established
  (POL-GEN-26)" (POL-RD-21); built only where it decides between row (a) and row (b), so the case
  escalates; where the row is (d) it changes nothing.
- **Driver-filed route disputes** are built only where the platform's interim recovery from the
  driver equals the excess distance fare the rider is owed (the driver's claim fails: NO_ACTION, which
  POL-GEN-03 makes party-relative) or where the case escalates. A driver-wins route case would need a
  DRIVER_COMPENSATION that no route clause licenses, so none is built.
- **Driver-filed no-show disputes**: the fee was charged, then reversed to the rider on an interim
  basis. If the fee stands the ruling is DRIVER_COMPENSATION of the fee (POL-NS-22); if it does not,
  the driver's claim fails and the present state stands: NO_ACTION (POL-GEN-03), not a second refund.
- **Free wait for a scheduled trip with an early driver.** The clause text (and
  `thresholds.free_wait_starts`) runs it from the scheduled time; note C2 runs it from arrival. Every
  early-driver case is timed so that both readings give the same answer.
- **POL-NS-25 count** ("counting this trip if its fee stands"): values are chosen so the answer is the
  same whether or not the profile snapshot already counts this trip (fee stands: 0-1 or >= 3; fee
  voided: 0-2 or >= 4). Escalated cases carry no referrals.
- **Contact obligation (POL-NS-23)**: only DRIVER-placed calls count (a call placed by the rider does
  not); an unanswered call counts as placed; a VOICE_CALL_LOG entry in the chat counts; SYSTEM messages
  are not driver messages; anything at or after `cancelled_at` does not count. No case turns on a
  driver message sent before arrival.
- **Driver no-show (POL-NS-24)** is built only on scheduled trips (an on-demand trip has no deadline);
  arrival is the arrival_test (trip-record arrival corroborated by GPS fixes within the zone radius,
  accuracy within 25 m). A scheduled driver arriving later than scheduled + 5 min and then cancelling
  is never built. The goodwill referral is added only where the driver neither messaged nor called.
- **Confidence (POL-GEN-02(2))** is capped by the lowest weight among the artifacts that carry a
  deciding fact; a fact is deciding when changing it would change the outcome. Route rulings need 0.80
  (POL-RD-25); a fraud flag (either party, `fraud_flags` >= 1) raises it to 0.95 (POL-GEN-22,
  POL-NS-26). Fraud-flag cases escalate where a deciding artifact weighs less than 0.95, and stand
  where every deciding artifact is COMPLETE. An impaired artifact that carries no deciding fact does
  not stop a ruling.
- **Over 2 km**: `ai_ruling_max_deviation_applied` is false, so the AI ruling stands; each such
  rationale says the answer depends on that field.
- **Fee other than 5.00**: the ruling acts on the amount charged and a POL-NS-22 referral is added.
- Rider-filed partial refunds are always below `amount_contested_sgd` (no checker warning).

## Known limits

- Geography is approximate: real Singapore places and road names, hand-placed waypoints, and a
  synthetic detour point between the junction and the rejoin; GPS fixes are interpolated along the
  waypoints every 30 s. Trace distances therefore understate the recorded distances, which is what
  POL-RD-22 expects and why the recorded distances decide.
- Fares use a synthetic Ryde rate card per vehicle class; ERP and airport surcharges are plausible
  values, not looked up.
- No human review. The reference answers are the author's, checked only by the second reading above.


## Cases and reference answers

| case | category | filed_by | ruling | amount | driver comp | referrals | difficulty | governing clauses |
|---|---|---|---|---|---|---|---|---|
| 6001 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 1.1 | None | - | EASY | POL-RD-24, POL-RD-22, POL-RD-23 |
| 6002 | ROUTE_DEVIATION | RIDER | NO_ACTION | None | None | - | EASY | POL-RD-24, POL-RD-22, POL-RD-23 |
| 6003 | ROUTE_DEVIATION | RIDER | NO_ACTION | None | None | - | EASY | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21 |
| 6004 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 1.22 | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-23 |
| 6005 | ROUTE_DEVIATION | DRIVER | NO_ACTION | None | None | - | REVERSAL | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-23, POL-GEN-03 |
| 6006 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 1.15 | None | - | REVERSAL | POL-RD-24, POL-RD-22, POL-RD-23 |
| 6007 | ROUTE_DEVIATION | DRIVER | ESCALATE | None | None | - | INDETERMINATE | POL-RD-24, POL-GEN-26, POL-RD-21, POL-RD-23 |
| 6008 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-RD-24, POL-RD-23, POL-GEN-02 |
| 6009 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 2.21 | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-23, POL-RD-25, POL-GEN-22 |
| 6010 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | EASY | POL-GEN-22, POL-RD-25 |
| 6011 | ROUTE_DEVIATION | DRIVER | ESCALATE | None | None | - | EASY | POL-GEN-21 |
| 6012 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-02, POL-RD-25, POL-GEN-22, POL-GEN-01 |
| 6013 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 0.79 | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-GEN-22 |
| 6014 | ROUTE_DEVIATION | DRIVER | NO_ACTION | None | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-23, POL-GEN-03 |
| 6015 | ROUTE_DEVIATION | RIDER | NO_ACTION | None | None | - | REVERSAL | POL-RD-24, POL-RD-22, POL-RD-23 |
| 6051 | NO_SHOW_CHARGE | RIDER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | EASY | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 6052 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | EASY | POL-NS-23, POL-GEN-23, POL-NS-26 |
| 6053 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | REVERSAL | POL-NS-23, POL-GEN-23, POL-NS-26 |
| 6054 | NO_SHOW_CHARGE | DRIVER | NO_ACTION | None | None | - | HARD | POL-NS-21, POL-NS-22, POL-GEN-03, POL-NS-26 |
| 6055 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | HARD | POL-NS-24, POL-NS-26 |
| 6056 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | POL-NS-24 | REVERSAL | POL-NS-24, POL-NS-26 |
| 6057 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | HARD | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 6058 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 5.0 | 5.0 | POL-NS-25 | HARD | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-25, POL-GEN-01, POL-NS-26 |
| 6059 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 4.0 | None | POL-NS-22 | HARD | POL-NS-23, POL-GEN-23, POL-NS-22, POL-NS-26 |
| 6060 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | REVERSAL | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 6061 | NO_SHOW_CHARGE | RIDER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-NS-26, POL-NS-21, POL-GEN-02 |
| 6062 | NO_SHOW_CHARGE | DRIVER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-22, POL-NS-26, POL-GEN-02, POL-GEN-01 |
| 6063 | NO_SHOW_CHARGE | RIDER | ESCALATE | None | None | - | EASY | POL-GEN-21, POL-NS-26 |
| 6064 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | HARD | POL-NS-23, POL-GEN-23, POL-GEN-22, POL-NS-26, POL-GEN-01 |
| 6065 | NO_SHOW_CHARGE | DRIVER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-NS-26, POL-NS-23, POL-GEN-02 |
