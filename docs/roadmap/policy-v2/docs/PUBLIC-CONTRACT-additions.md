# PUBLIC-CONTRACT additions for policy base version 2 (additive; `schema_version` stays 1.2.0)

Paste into `data/PUBLIC-CONTRACT.md`. Every field below is optional; a case without it loads exactly as before.

## `trip_record.platform_policy` (object, optional)

The platform parameters in force for this trip. When present, `fee_schedule.resolution_rule` and POL-NS-01(c) read it before `fee_schedule.defaults`.

| field | type | meaning |
|---|---|---|
| `grace_after_match_sec` | int | free cancellation window after matching |
| `advance_grace_before_scheduled_sec` | int | free cancellation window before a scheduled trip's time |
| `free_wait_sec` | int | free waiting period after arrival; the minimum dwell for a chargeable no-show |
| `no_show_threshold_sec` | int or null | a longer platform threshold the cancellation must also reach; null = same as `free_wait_sec` |
| `cancellation_fee_sgd` | number | the cancellation / no-show fee, net to the driver |
| `rider_gross_cancellation_fee_sgd` | number or null | the rider-side figure incl. GST and payment fees, for POL-NS-08(d) reconciliation only |
| `waiting_fee_sgd` | number or null | the waiting-time fee on a completed trip |
| `fee_goes_to` | `"DRIVER"` or `"PLATFORM"` | who receives the fee |
| `arrival_marker` | `"BUTTON"` or `"GPS_AUTO"` | how the platform marks arrival |
| `source` | string | an opaque code for where the block came from - `RECORD-PLATFORM` (carried on the record), `PLATFORM-PUBLISHED-<date>` (the defaults), `AUTHORED-V1` (backfilled) - never a name or a sentence, because the block reaches the model |

## `trip_record.scheduled_at` (timestamp, optional, null for on-demand trips)

Read by POL-NS-10(b).

## `trip_record.events[]` (array, optional)

The platform's own event log for the trip. Each item: `event_type` (string), `at` (timestamp), `detail` (string), `source` (one of the evidence `source` values, normally `PLATFORM_TELEMETRY`). An arrival or wait-timer event here is an independent carrier of the dwell for POL-GEN-02(2).

## `trip_record.accepted_at`

Already present on every case; now cited by POL-NS-10(a).

## GPS points: `accuracy_m` may be null

A point with no reported accuracy is of unknown accuracy for POL-NS-02 (`integrity.accuracy_missing_treatment`): neither counted nor excluded by the 25 m filter.

## `dispute.safety_flag`, `dispute.complaint_flag` (boolean, optional)

Set by intake. Cited by POL-GEN-05 (never executed automatically) and POL-GEN-06(1) (entry to human review). They route the case; they are not evidence and carry no weight.

## Policy files

`policy/general.json` carries 8 clauses and the top-level keys `execution_threshold_sgd` and `policy_sources`; `policy/no_show.json` carries 10 clauses and the top-level key `integrity`; `policy/route_deviation.json` carries 13 clauses (31 in total). Update the clause-count table and the "one extra key each" sentence accordingly.
