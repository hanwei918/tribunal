# tribunal-dev-v7: working notes

## Second reading result

40 cases read by 40 fresh readers. First round: 39 agreed with the key on ruling, amount, driver compensation and referral clauses. Case 5009 did not: the reader read POL-RD-23's last sentence as the rule that infers 'not justified' from a MISSING advisory and gave a partial refund. The key's reading (POL-GEN-26, which names this fact) was kept, and the case file's missing-advisory note was clarified to say the traffic-feed request failed, so the record is silent rather than negative. The same wording went into the shared engine before the sealed set was read. A fresh reader then read the clarified case 5009 and agreed with the key; its first-round answer is kept in notes/second_reading/round1/. Key changes: 0. Case-file clarifications: 1.

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
| 5001 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 1.15 | None | - | EASY | POL-RD-24, POL-RD-22, POL-RD-23 |
| 5002 | ROUTE_DEVIATION | RIDER | NO_ACTION | None | None | - | EASY | POL-RD-24, POL-RD-22, POL-RD-23 |
| 5003 | ROUTE_DEVIATION | RIDER | NO_ACTION | None | None | - | EASY | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21 |
| 5004 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 1.01 | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-23 |
| 5005 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 1.56 | None | - | REVERSAL | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-23 |
| 5006 | ROUTE_DEVIATION | DRIVER | NO_ACTION | None | None | - | REVERSAL | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-03 |
| 5007 | ROUTE_DEVIATION | RIDER | NO_ACTION | None | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23 |
| 5008 | ROUTE_DEVIATION | DRIVER | ESCALATE | None | None | - | INDETERMINATE | POL-RD-24, POL-GEN-26, POL-RD-21, POL-RD-23 |
| 5009 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-RD-24, POL-RD-23, POL-GEN-02 |
| 5010 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 2.12 | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-25, POL-GEN-22 |
| 5011 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-RD-24, POL-RD-21, POL-GEN-02 |
| 5012 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | EASY | POL-GEN-22, POL-RD-25 |
| 5013 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | EASY | POL-GEN-21 |
| 5014 | ROUTE_DEVIATION | RIDER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-RD-24, POL-RD-21, POL-GEN-02, POL-GEN-22, POL-GEN-01 |
| 5015 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 1.87 | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-25 |
| 5016 | ROUTE_DEVIATION | DRIVER | NO_ACTION | None | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-23, POL-GEN-03 |
| 5017 | ROUTE_DEVIATION | DRIVER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-RD-24, POL-RD-21 |
| 5018 | ROUTE_DEVIATION | RIDER | NO_ACTION | None | None | - | REVERSAL | POL-RD-24, POL-RD-22, POL-RD-23, POL-GEN-01 |
| 5019 | ROUTE_DEVIATION | RIDER | PARTIAL_REFUND | 0.94 | None | - | HARD | POL-RD-24, POL-RD-22, POL-RD-23 |
| 5020 | ROUTE_DEVIATION | DRIVER | NO_ACTION | None | None | - | REVERSAL | POL-RD-24, POL-RD-22, POL-RD-23, POL-RD-21, POL-GEN-03 |
| 5051 | NO_SHOW_CHARGE | RIDER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | EASY | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 5052 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | EASY | POL-NS-23, POL-GEN-23, POL-NS-26 |
| 5053 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | EASY | POL-NS-23, POL-GEN-23, POL-NS-26 |
| 5054 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | HARD | POL-NS-21, POL-NS-22, POL-GEN-03, POL-NS-26 |
| 5055 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | EASY | POL-NS-24, POL-NS-26 |
| 5056 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | POL-NS-24 | HARD | POL-NS-24, POL-NS-26 |
| 5057 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | REVERSAL | POL-NS-24, POL-NS-26 |
| 5058 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | HARD | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 5059 | NO_SHOW_CHARGE | RIDER | DRIVER_COMPENSATION | 5.0 | 5.0 | POL-NS-25 | HARD | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-25, POL-GEN-01, POL-GEN-02, POL-NS-26 |
| 5060 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 6.5 | 6.5 | POL-NS-22 | HARD | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 5061 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | REVERSAL | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 5062 | NO_SHOW_CHARGE | DRIVER | NO_ACTION | None | None | - | REVERSAL | POL-NS-23, POL-GEN-23, POL-NS-26, POL-NS-22, POL-GEN-03 |
| 5063 | NO_SHOW_CHARGE | DRIVER | NO_ACTION | None | None | - | REVERSAL | POL-NS-23, POL-GEN-23, POL-NS-26, POL-NS-22, POL-GEN-03 |
| 5064 | NO_SHOW_CHARGE | DRIVER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-NS-26, POL-NS-21, POL-GEN-02 |
| 5065 | NO_SHOW_CHARGE | DRIVER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-26, POL-NS-26, POL-NS-23, POL-GEN-02 |
| 5066 | NO_SHOW_CHARGE | RIDER | ESCALATE | None | None | - | INDETERMINATE | POL-GEN-22, POL-NS-26, POL-GEN-02, POL-GEN-01 |
| 5067 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | HARD | POL-NS-22, POL-NS-21, POL-NS-23, POL-GEN-22, POL-NS-26, POL-GEN-01 |
| 5068 | NO_SHOW_CHARGE | RIDER | ESCALATE | None | None | - | EASY | POL-GEN-21, POL-NS-26 |
| 5069 | NO_SHOW_CHARGE | DRIVER | DRIVER_COMPENSATION | 5.0 | 5.0 | - | HARD | POL-NS-22, POL-NS-21, POL-NS-23, POL-NS-26 |
| 5070 | NO_SHOW_CHARGE | RIDER | FULL_REFUND | 5.0 | None | - | HARD | POL-NS-23, POL-GEN-23, POL-NS-26 |
