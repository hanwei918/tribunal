# Rationale audit — 2026-09-21

Every `rationale` in `eval/answers/ground_truth.json` audited against this
package's own arithmetic, before the key is frozen and used to score models.
Produced by `eval/verify_rationales.py`; regenerate with
`python -m eval.verify_rationales`.

## Summary

| | |
|---|---|
| Cases in the key | 29 |
| Cases with an explicit stated sum | 8 |
| Stated sums checked | 13 |
| Cases with a stated round-up pair | 7 |
| Round-up pairs checked | 7 |
| Cases with an expected figure | 19 |
| Expected-figure checks | 25 |
| **Internal-consistency failures** | **0** |

**Part A (internal consistency) is CLEAN.** A stated sum that does not add
up is wrong regardless of what the case data says, so a failure here would
have been unambiguous. There are none.

**Part B (external reconciliation) is a report, not a test.** A mismatch below
does **not** establish which side is wrong. The rationale may be wrong, or this
package's computation may be wrong — and the second would be the more serious
finding, because it would mean the code three models are measured against is
itself incorrect. Nothing in this audit has been repaired on either side.

## Part A — internal consistency

### A1. Stated sums

An equality counts as a stated sum when its left side carries at least two
numbers and at least one operator or `min` call. The stated figure must be the
exact value rounded to the number of decimals the figure is written with, which
is the tolerance any rounding convention at that precision needs. All arithmetic
is `Decimal`.

| Case | Claim | Exact | Stated | Verdict |
|---|---|---|---|---|
| 101 | `3.80 + 15.75 + 7.28 + 0.80 = 27.63` | 27.63 | 27.63 | ok |
| 103 | `1.30 x (10.60 - 8.20) + 1.00 = 4.12` | 4.1200 | 4.12 | ok |
| 104 | `1.30 x (30.10 - 27.10) + 1.00 = 4.90` | 4.9000 | 4.90 | ok |
| 104 | `27.10 + 4.90 = 32.00` | 32.00 | 32.00 | ok |
| 104 | `34.0 x 32.00 / 27.10 = 40.1` | 40.14760147601476014760147601 | 40.1 | ok |
| 104 | `3.80 + 24.00 + 11.23 + 0.80 = 39.83` | 39.83 | 39.83 | ok |
| 105 | `3.80 + 27.00 + 11.76 + 0.80 = 43.36` | 43.36 | 43.36 | ok |
| 106 | `3.80 + 5.40 + 5.32 + 0.80 = 15.32` | 15.32 | 15.32 | ok |
| 106 | `26.04 - 15.32 = 10.72` | 10.72 | 10.72 | ok |
| 107 | `(3.80 + 10.50 + 6.72) x 1.35 + 0.80 = 29.18` | 29.1770 | 29.18 | ok |
| 111 | `1.30 x (29.20 - 24.00) + 1.00 = 7.76` | 7.7600 | 7.76 | ok |
| 114 | `(3.80 + 13.50 + 8.40) x 1.60 = 41.12` | 41.1200 | 41.12 | ok |
| 114 | `41.12 + 0.80 + 2.50 = 44.42` | 44.42 | 44.42 | ok |

### A2. Stated round-ups

Checked against `money.round_up_005`, the rule POL-RD-02, POL-RD-04, POL-RD-09
and POL-RD-11 all invoke. A rationale that merely describes a *rounded copy* on
the trip record states a different operation and is not matched here.

| Case | Claim | round_up_005(before) | Verdict |
|---|---|---|---|
| 101 | 8.01 rounded up to 8.05 | 8.05 | ok |
| 104 | 3.58 rounded up to 3.60 | 3.60 | ok |
| 105 | 21.77 rounded up to 21.80 | 21.80 | ok |
| 106 | 10.72 rounded up to 10.75 | 10.75 | ok |
| 107 | 7.42 rounded up to 7.45 | 7.45 | ok |
| 109 | 3.12 rounded up to 3.15 | 3.15 | ok |
| 114 | 13.68 rounded up to 13.70 | 13.70 | ok |

### A3. The expected figure

The block's own `expected_amount_sgd`, or `expected_driver_compensation_sgd`
where the ruling is DRIVER_COMPENSATION, must be a figure the rationale
arrives at. Where the rationale states a round-up target and the ruling is not
a full refund, that target is the arrived-at figure and must equal the block's.
A FULL_REFUND rationale arrives at two figures on purpose — the computed
partial and the ordered full refund — and is exempt from the second check.

| Case | Ruling | Expected | Check | Verdict |
|---|---|---|---|---|
| 101 | PARTIAL_REFUND | 8.05 | 8.05 in the rationale | ok |
| 101 | PARTIAL_REFUND | 8.05 | round-up target(s) 8.05 | ok |
| 103 | PARTIAL_REFUND | 4.0 | 4.0 in the rationale | ok |
| 104 | PARTIAL_REFUND | 3.6 | 3.6 in the rationale | ok |
| 104 | PARTIAL_REFUND | 3.6 | round-up target(s) 3.60 | ok |
| 105 | FULL_REFUND | 65.13 | 65.13 in the rationale | ok |
| 106 | PARTIAL_REFUND | 10.75 | 10.75 in the rationale | ok |
| 106 | PARTIAL_REFUND | 10.75 | round-up target(s) 10.75 | ok |
| 107 | PARTIAL_REFUND | 7.45 | 7.45 in the rationale | ok |
| 107 | PARTIAL_REFUND | 7.45 | round-up target(s) 7.45 | ok |
| 109 | DRIVER_COMPENSATION | 3.15 | 3.15 in the rationale | ok |
| 109 | DRIVER_COMPENSATION | 3.15 | round-up target(s) 3.15 | ok |
| 114 | PARTIAL_REFUND | 13.7 | 13.7 in the rationale | ok |
| 114 | PARTIAL_REFUND | 13.7 | round-up target(s) 13.70 | ok |
| 115 | PARTIAL_REFUND | 2.0 | 2.0 in the rationale | ok |
| 201 | FULL_REFUND | 4.0 | 4.0 in the rationale | ok |
| 202 | DRIVER_COMPENSATION | 4.8 | 4.8 in the rationale | ok |
| 203 | FULL_REFUND | 4.0 | 4.0 in the rationale | ok |
| 204 | FULL_REFUND | 4.0 | 4.0 in the rationale | ok |
| 205 | FULL_REFUND | 4.0 | 4.0 in the rationale | ok |
| 206 | FULL_REFUND | 4.0 | 4.0 in the rationale | ok |
| 208 | DRIVER_COMPENSATION | 6.4 | 6.4 in the rationale | ok |
| 211 | PARTIAL_REFUND | 2.0 | 2.0 in the rationale | ok |
| 212 | FULL_REFUND | 4.0 | 4.0 in the rationale | ok |
| 214 | DRIVER_COMPENSATION | 3.2 | 3.2 in the rationale | ok |

### A1–A3 verdict

No internal-consistency failure. Every stated sum adds up, every stated
round-up pair satisfies `money.round_up_005`, and every block's expected
figure is a figure its rationale arrives at.

Cases carrying no check of a given kind are not passes: A1 covers 101, 103, 104, 105, 106, 107, 111, 114, A2
covers 101, 104, 105, 106, 107, 109, 114, and A3 covers the 19 cases whose ruling carries money.

## Part B — external reconciliation

Derived quantities computed independently through `tribunal/facts.py` and
`tribunal/money.py`, then reconciled against the prose in both directions:
a computed value with no counterpart in the prose, and a two-decimal prose
figure nothing computed accounts for. Quantities are matched against the
prose at the precision the prose states them.

Only **decision-bearing** quantities are judged — a figure a clause thresholds
on, or a figure the ruling's own money is computed from. Inputs, raw fix
counts, policy constants, rounded copies and zero values are listed as
**informational** and carry no verdict: a rationale is not expected to quote
every one, and treating those omissions as findings would bury the one
discrepancy that matters. A zero decision-bearing value is informational too,
because the prose states an absence in words rather than as a figure.

`facts.py` computes haversine geometry in `float`; every value it returns is
converted here with `Decimal(str(value))`, so a false discrepancy cannot come
from this module's own arithmetic.

### Case 101 — ROUTE_DEVIATION, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 6.18 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 29.4 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 27.63 | money.recompute_metered_fare | in the prose |
| POL-RD-02 refund | 8.05 | money.refund_for | in the prose |
| answer key expected figure | 8.05 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 27.18, `trip.optimal_distance_km` = 21.00, `trip.actual_distance_km` = 27.20, `trip.deviation_pct` = 29.5, `fare.total_charged` = 35.64, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00.

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 102 — ROUTE_DEVIATION, NO_ACTION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 1.39 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 6.8 | facts.deviation_excess | in the prose |

Informational, not judged: `gps.trace_distance_km` = 21.79, `trip.optimal_distance_km` = 20.40, `trip.actual_distance_km` = 21.80, `trip.deviation_pct` = 6.9, `fare.total_charged` = 29.91, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00, `POL-RD-02 recomputed_fare` = 27.46, `POL-RD-02 refund` = 2.45.

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 103 — ROUTE_DEVIATION, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 2.98 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 36.3 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 16.63 | money.recompute_metered_fare | **no counterpart** |
| POL-RD-02 refund | 8.50 | money.refund_for | **no counterpart** |
| answer key expected figure | 4.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 11.18, `trip.optimal_distance_km` = 8.20, `trip.actual_distance_km` = 11.20, `trip.deviation_pct` = 36.6, `fare.total_charged` = 25.12, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`12.00`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 104 — ROUTE_DEVIATION, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 7.07 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 26.1 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 34.45 | money.recompute_metered_fare | **no counterpart** |
| POL-RD-02 refund | 9.00 | money.refund_for | **no counterpart** |
| answer key expected figure | 3.60 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 34.17, `trip.optimal_distance_km` = 27.10, `trip.actual_distance_km` = 34.20, `trip.deviation_pct` = 26.2, `fare.total_charged` = 43.41, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`2.17`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 105 — ROUTE_DEVIATION, FULL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 18.16 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 50.4 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 43.36 | money.recompute_metered_fare | in the prose |
| POL-RD-02 refund | 21.80 | money.refund_for | in the prose |
| answer key expected figure | 65.13 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 54.16, `trip.optimal_distance_km` = 36.00, `trip.actual_distance_km` = 54.20, `trip.deviation_pct` = 50.6, `fare.total_charged` = 65.13, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00.

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 106 — ROUTE_DEVIATION, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 3.58 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 49.7 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 15.32 | money.recompute_metered_fare | in the prose |
| POL-RD-02 refund | 10.75 | money.refund_for | in the prose |
| answer key expected figure | 10.75 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 10.78, `trip.optimal_distance_km` = 7.20, `trip.actual_distance_km` = 10.80, `trip.deviation_pct` = 50.0, `fare.total_charged` = 26.04, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`5.50`, `16.25`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 107 — ROUTE_DEVIATION, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 3.57 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 25.5 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 29.18 | money.recompute_metered_fare | in the prose |
| POL-RD-02 refund | 7.45 | money.refund_for | in the prose |
| answer key expected figure | 7.45 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 17.57, `trip.optimal_distance_km` = 14.00, `trip.actual_distance_km` = 17.60, `trip.deviation_pct` = 25.7, `fare.total_charged` = 36.60, `fare.surge_multiplier` = 1.35, `trip.optimal_route_erp_sgd` = 0.00.

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 108 — ROUTE_DEVIATION, NO_ACTION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 5.17 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 24.6 | facts.deviation_excess | in the prose |

Informational, not judged: `gps.trace_distance_km` = 26.17, `trip.optimal_distance_km` = 21.00, `trip.actual_distance_km` = 26.20, `trip.deviation_pct` = 24.8, `fare.total_charged` = 33.77, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00, `POL-RD-02 recomputed_fare` = 27.63, `POL-RD-02 refund` = 6.15.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`24.60`, `1.57`, `1.10`, `0.47`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 109 — ROUTE_DEVIATION, DRIVER_COMPENSATION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 7.36 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 115.0 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 13.32 | money.recompute_metered_fare | **no counterpart** |
| POL-RD-02 refund | 8.00 | money.refund_for | **no counterpart** |
| answer key expected figure | 3.15 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 13.76, `trip.optimal_distance_km` = 6.40, `trip.actual_distance_km` = 13.80, `trip.deviation_pct` = 115.6, `fare.total_charged` = 21.32, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`7.20`, `0.16`, `9.60`, `4.16`, `0.05`, `15.00`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 110 — ROUTE_DEVIATION, ESCALATE

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 2.80 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 15.2 | facts.deviation_excess | in the prose |

Informational, not judged: `gps.trace_distance_km` = 21.20, `trip.optimal_distance_km` = 18.40, `trip.actual_distance_km` = 21.20, `trip.deviation_pct` = 15.2, `fare.total_charged` = 34.42, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 3.00, `POL-RD-02 recomputed_fare` = 28.68, `POL-RD-02 refund` = 5.75.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`6.90`, `25.50`, `0.68`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 111 — ROUTE_DEVIATION, NO_ACTION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 5.98 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 24.9 | facts.deviation_excess | in the prose |

Informational, not judged: `gps.trace_distance_km` = 29.98, `trip.optimal_distance_km` = 24.00, `trip.actual_distance_km` = 30.00, `trip.deviation_pct` = 25.0, `fare.total_charged` = 37.74, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00, `POL-RD-02 recomputed_fare` = 31.00, `POL-RD-02 refund` = 6.75.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`4.00`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 112 — ROUTE_DEVIATION, ESCALATE

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 4.80 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 27.3 | facts.deviation_excess | in the prose |

Informational, not judged: `gps.trace_distance_km` = 22.40, `trip.optimal_distance_km` = 17.60, `trip.actual_distance_km` = 20.00, `trip.deviation_pct` = 13.6, `fare.total_charged` = 25.26, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00, `POL-RD-02 recomputed_fare` = 25.64, `POL-RD-02 refund` = 0.00.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`2.40`, `20.02`, `2.42`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is NO_ACTION; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 113 — ROUTE_DEVIATION, NO_ACTION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 0.78 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 4.0 | facts.deviation_excess | in the prose |

Informational, not judged: `gps.trace_distance_km` = 20.18, `trip.optimal_distance_km` = 19.40, `trip.actual_distance_km` = 20.20, `trip.deviation_pct` = 4.1, `fare.total_charged` = 26.83, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 0.00, `POL-RD-02 recomputed_fare` = 25.67, `POL-RD-02 refund` = 1.20.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`15.80`, `4.38`, `3.00`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 114 — ROUTE_DEVIATION, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 5.97 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 33.2 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 44.42 | money.recompute_metered_fare | in the prose |
| POL-RD-02 refund | 13.70 | money.refund_for | in the prose |
| answer key expected figure | 13.70 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 23.97, `trip.optimal_distance_km` = 18.00, `trip.actual_distance_km` = 24.00, `trip.deviation_pct` = 33.3, `fare.total_charged` = 58.10, `fare.surge_multiplier` = 1.60, `trip.optimal_route_erp_sgd` = 2.50.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`2.00`, `15.70`, `27.94`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 115 — ROUTE_DEVIATION, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| POL-RD-01 excess_km | 5.78 | facts.deviation_excess | in the prose |
| POL-RD-01 excess_pct | 25.8 | facts.deviation_excess | in the prose |
| POL-RD-02 recomputed_fare | 32.30 | money.recompute_metered_fare | **no counterpart** |
| POL-RD-02 refund | 6.70 | money.refund_for | **no counterpart** |
| answer key expected figure | 2.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `gps.trace_distance_km` = 28.18, `trip.optimal_distance_km` = 22.40, `trip.actual_distance_km` = 28.20, `trip.deviation_pct` = 25.9, `fare.total_charged` = 39.00, `fare.surge_multiplier` = 1.00, `trip.optimal_route_erp_sgd` = 2.50.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`34.50`, `4.50`

> POL-RD-02 recomputed_fare above uses the booked optimal distance and duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's waypoint adjustment and POL-RD-05's re-quote are not applied by this module, so a case that adjusts its baseline will not reconcile here.

> POL-RD-02 outcome on the unadjusted baseline is PARTIAL_REFUND; POL-RD-06's full-refund upgrade, POL-RD-09's pass-through corrections and POL-RD-11's quote model are not applied here.

### Case 201 — NO_SHOW_CHARGE, FULL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 779.9 | facts.distances_to_point | in the prose |
| answer key expected figure | 4.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.00, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 50, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 100, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 98, `closest driver approach_m (all fixes)` = 779.9, `qualifying in-radius fix count` = 0, `longest qualifying run fix count` = 0, `longest qualifying run duration_sec` = 0, `rider fix count` = 122, `closest rider approach_m` = 5.6, `farthest rider distance_m` = 24.9.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 202 — NO_SHOW_CHARGE, DRIVER_COMPENSATION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 22.4 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 620 | facts.longest_qualifying_run | in the prose |
| dwell to cancellation_sec | 635 | facts.elapsed_seconds | in the prose |
| answer key expected figure | 4.80 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 6.00, `fare.cancellation_fee` = 6.00, `fee_schedule.arrival_radius_m` = 150, `fee_schedule.minimum_dwell_sec` = 480, `fee_schedule.rider_presence_radius_m` = 200, `chargeable fee (greater of zone and tier)` = 6.00, `POL-NS-07 compensation at 80%` = 4.80, `POL-NS-03 goodwill at 50%` = 3.00, `driver fix count` = 116, `closest driver approach_m (all fixes)` = 22.4, `qualifying in-radius fix count` = 63, `longest qualifying run fix count` = 63, `rider fix count` = 88, `closest rider approach_m` = 2039.0, `farthest rider distance_m` = 2163.6.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 203 — NO_SHOW_CHARGE, FULL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 18.7 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 195 | facts.longest_qualifying_run | **no counterpart** |
| dwell to cancellation_sec | 200 | facts.elapsed_seconds | in the prose |
| answer key expected figure | 4.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.00, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 50, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 100, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 60, `closest driver approach_m (all fixes)` = 18.7, `qualifying in-radius fix count` = 21, `longest qualifying run fix count` = 21, `rider fix count` = 60, `closest rider approach_m` = 36.4, `farthest rider distance_m` = 51.6.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 204 — NO_SHOW_CHARGE, FULL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 94.9 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 340 | facts.longest_qualifying_run | in the prose |
| dwell to cancellation_sec | 340 | facts.elapsed_seconds | in the prose |
| answer key expected figure | 4.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.50, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 120, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 150, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 87, `closest driver approach_m (all fixes)` = 94.9, `qualifying in-radius fix count` = 35, `longest qualifying run fix count` = 35, `rider fix count` = 105, `closest rider approach_m` = 6.0, `farthest rider distance_m` = 39.9.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 205 — NO_SHOW_CHARGE, FULL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 259.9 | facts.distances_to_point | in the prose |
| answer key expected figure | 4.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.00, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 50, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 100, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 92, `closest driver approach_m (all fixes)` = 259.9, `qualifying in-radius fix count` = 0, `longest qualifying run fix count` = 0, `longest qualifying run duration_sec` = 0, `rider fix count` = 96, `closest rider approach_m` = 5.7, `farthest rider distance_m` = 22.8.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 206 — NO_SHOW_CHARGE, FULL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 285.0 | facts.distances_to_point | in the prose |
| answer key expected figure | 4.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.00, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 120, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 150, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 52, `closest driver approach_m (all fixes)` = 285.0, `qualifying in-radius fix count` = 0, `longest qualifying run fix count` = 0, `longest qualifying run duration_sec` = 0, `rider fix count` = 31, `closest rider approach_m` = 7.6, `farthest rider distance_m` = 22.5.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 207 — NO_SHOW_CHARGE, ESCALATE

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 14.5 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 507 | facts.longest_qualifying_run | in the prose |
| dwell to cancellation_sec | 507 | facts.elapsed_seconds | in the prose |

Informational, not judged: `fare.total_charged` = 4.50, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 50, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 100, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 102, `closest driver approach_m (all fixes)` = 14.5, `qualifying in-radius fix count` = 52, `longest qualifying run fix count` = 52, `rider fix count` = 118, `closest rider approach_m` = 1894.1, `farthest rider distance_m` = 1906.6.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`0.86`, `4.19`, `0.23`

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 208 — NO_SHOW_CHARGE, DRIVER_COMPENSATION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 28.8 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 585 | facts.longest_qualifying_run | in the prose |
| dwell to cancellation_sec | 600 | facts.elapsed_seconds | in the prose |
| answer key expected figure | 6.40 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 8.00, `fare.cancellation_fee` = 8.00, `fee_schedule.arrival_radius_m` = 120, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 150, `chargeable fee (greater of zone and tier)` = 8.00, `POL-NS-07 compensation at 80%` = 6.40, `POL-NS-03 goodwill at 50%` = 4.00, `driver fix count` = 120, `closest driver approach_m (all fixes)` = 28.8, `qualifying in-radius fix count` = 60, `longest qualifying run fix count` = 60, `rider fix count` = 141, `closest rider approach_m` = 633.9, `farthest rider distance_m` = 646.4.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 209 — NO_SHOW_CHARGE, NO_ACTION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 62.0 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 236 | facts.longest_qualifying_run | in the prose |
| dwell to cancellation_sec | 236 | facts.elapsed_seconds | in the prose |

Informational, not judged: `fare.total_charged` = 6.00, `fare.cancellation_fee` = 6.00, `fee_schedule.arrival_radius_m` = 150, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 200, `chargeable fee (greater of zone and tier)` = 6.00, `POL-NS-07 compensation at 80%` = 4.80, `POL-NS-03 goodwill at 50%` = 3.00, `driver fix count` = 108, `closest driver approach_m (all fixes)` = 30.3, `qualifying in-radius fix count` = 25, `longest qualifying run fix count` = 25, `rider fix count` = 88, `closest rider approach_m` = 50.5, `farthest rider distance_m` = 91.7.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 210 — NO_SHOW_CHARGE, ESCALATE

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 96.0 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 255 | facts.longest_qualifying_run | **no counterpart** |
| dwell to cancellation_sec | 404 | facts.elapsed_seconds | in the prose |

Informational, not judged: `fare.total_charged` = 6.00, `fare.cancellation_fee` = 6.00, `fee_schedule.arrival_radius_m` = 150, `fee_schedule.minimum_dwell_sec` = 480, `fee_schedule.rider_presence_radius_m` = 200, `chargeable fee (greater of zone and tier)` = 6.00, `POL-NS-07 compensation at 80%` = 4.80, `POL-NS-03 goodwill at 50%` = 3.00, `driver fix count` = 9, `closest driver approach_m (all fixes)` = 96.0, `qualifying in-radius fix count` = 5, `longest qualifying run fix count` = 5.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`0.61`

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 211 — NO_SHOW_CHARGE, PARTIAL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 18.1 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 500 | facts.longest_qualifying_run | in the prose |
| dwell to cancellation_sec | 500 | facts.elapsed_seconds | in the prose |
| answer key expected figure | 2.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.00, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 50, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 100, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 92, `closest driver approach_m (all fixes)` = 18.1, `qualifying in-radius fix count` = 35, `longest qualifying run fix count` = 35, `rider fix count` = 55, `closest rider approach_m` = 24.6, `farthest rider distance_m` = 140.5.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`0.72`

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 212 — NO_SHOW_CHARGE, FULL_REFUND

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 147.8 | facts.distances_to_point | in the prose |
| answer key expected figure | 4.00 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.00, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 50, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 100, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 93, `closest driver approach_m (all fixes)` = 37.9, `qualifying in-radius fix count` = 0, `longest qualifying run fix count` = 0, `longest qualifying run duration_sec` = 0, `rider fix count` = 60, `closest rider approach_m` = 2.2, `farthest rider distance_m` = 40.4.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

### Case 213 — NO_SHOW_CHARGE, ESCALATE

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|

Informational, not judged: `fare.total_charged` = 6.00, `fare.cancellation_fee` = 6.00, `fee_schedule.arrival_radius_m` = 150, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 200, `chargeable fee (greater of zone and tier)` = 6.00, `POL-NS-07 compensation at 80%` = 4.80, `POL-NS-03 goodwill at 50%` = 3.00.

Two-decimal figures in the prose that neither a computed quantity nor
the rationale's own arithmetic accounts for — each is either an input
this package does not model, or a discrepancy:

`0.57`

> no GPS payload, so no trace-derived quantity was computed

### Case 214 — NO_SHOW_CHARGE, DRIVER_COMPENSATION

| Decision-bearing quantity | Computed | Source | Verdict |
|---|---|---|---|
| closest admissible driver approach_m | 14.7 | facts.distances_to_point | in the prose |
| longest qualifying run duration_sec | 185 | facts.longest_qualifying_run | in the prose |
| dwell to cancellation_sec | 190 | facts.elapsed_seconds | **no counterpart** |
| answer key expected figure | 3.20 | eval/answers/ground_truth.json | in the prose |

Informational, not judged: `fare.total_charged` = 4.00, `fare.cancellation_fee` = 4.00, `fee_schedule.arrival_radius_m` = 120, `fee_schedule.minimum_dwell_sec` = 300, `fee_schedule.rider_presence_radius_m` = 150, `chargeable fee (greater of zone and tier)` = 4.00, `POL-NS-07 compensation at 80%` = 3.20, `POL-NS-03 goodwill at 50%` = 2.00, `driver fix count` = 83, `closest driver approach_m (all fixes)` = 0.0, `qualifying in-radius fix count` = 40, `longest qualifying run fix count` = 20, `rider fix count` = 70, `closest rider approach_m` = 690.7, `farthest rider distance_m` = 717.2.

> Two dwell readings are computed and both are decision-bearing. `longest qualifying run duration_sec` is first fix to last fix within the run; `dwell to cancellation_sec` is first fix to the trip's cancelled_at. The rationales quote one or the other depending on the sentence — case 202 quotes both — so a case can carry a counterpart for one and not the other without either side being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here, so a case that depends on either will not reconcile.

## Cases needing a human

These cases have a decision-bearing quantity with no counterpart in the
prose. **This does not establish which side is wrong.** Each needs a person
to read the rationale and the computation together:

- **case 103** (PARTIAL_REFUND): POL-RD-02 recomputed_fare computed 16.63, not stated; POL-RD-02 refund computed 8.50, not stated
- **case 104** (PARTIAL_REFUND): POL-RD-02 recomputed_fare computed 34.45, not stated; POL-RD-02 refund computed 9.00, not stated
- **case 109** (DRIVER_COMPENSATION): POL-RD-02 recomputed_fare computed 13.32, not stated; POL-RD-02 refund computed 8.00, not stated
- **case 115** (PARTIAL_REFUND): POL-RD-02 recomputed_fare computed 32.30, not stated; POL-RD-02 refund computed 6.70, not stated
- **case 203** (FULL_REFUND): longest qualifying run duration_sec computed 195, not stated
- **case 210** (ESCALATE): longest qualifying run duration_sec computed 255, not stated
- **case 214** (DRIVER_COMPENSATION): dwell to cancellation_sec computed 190, not stated

Every other case reconciles: each decision-bearing quantity this package
computes appears in the case's own rationale, and no expected figure is
contradicted by the prose.

