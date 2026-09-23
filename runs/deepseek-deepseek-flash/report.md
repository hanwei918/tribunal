# Benchmark report — deepseek/deepseek-flash

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 29 |
| Rulings produced | 29 |
| **Four-field exact match** | **28/29 = 96.6%** |

| `ruling` | 28/29 = 96.6% |
| `amount_sgd` | 28/29 = 96.6% |
| `driver_compensation_sgd` | 29/29 = 100.0% |
| `referrals` | 29/29 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **28/29 = 96.6%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 101 | ok | ok | ok | ok | ok | current |
| 102 | ok | ok | ok | ok | ok | current |
| 103 | ok | ok | ok | ok | ok | current |
| 104 | ok | ok | ok | ok | ok | current |
| 105 | ok | ok | ok | ok | ok | current |
| 106 | ok | ok | ok | ok | ok | current |
| 107 | ok | ok | ok | ok | ok | current |
| 108 | ok | ok | ok | ok | ok | current |
| 109 | ok | ok | ok | ok | ok | current |
| 110 | ok | ok | ok | ok | ok | current |
| 111 | ok | ok | ok | ok | ok | current |
| 112 | ok | ok | ok | ok | ok | current |
| 113 | ok | ok | ok | ok | ok | current |
| 114 | ok | ok | ok | ok | ok | current |
| 115 | ok | ok | ok | ok | ok | current |
| 201 | ok | ok | ok | ok | ok | current |
| 202 | ok | ok | ok | ok | ok | current |
| 203 | ok | ok | ok | ok | ok | current |
| 204 | ok | ok | ok | ok | ok | current |
| 205 | ok | ok | ok | ok | ok | current |
| 206 | ok | ok | ok | ok | ok | current |
| 207 | ok | ok | ok | ok | ok | current |
| 208 | ok | ok | ok | ok | ok | current |
| 209 | ok | ok | ok | ok | ok | current |
| 210 | ok | ok | ok | ok | ok | current |
| 211 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 212 | ok | ok | ok | ok | ok | current |
| 213 | ok | ok | ok | ok | ok | current |
| 214 | ok | ok | ok | ok | ok | current |

## Failures

### Case 211

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 2.0, produced null

## Referrals — expected against produced

### Case 105 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review"
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 115 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: phantom AYE Alexandra Road gantry line of SGD 2.00 on EV-FARE-00115 that the trace never approaches"
- produced: "POL-RD-09(4) billing integrity: the SGD 2.00 'AYE (Alexandra Rd towards Tuas)' gantry line on EV-FARE-00115 is charged for a gantry that EV-GPS-00115 never crosses (closest approach 5.4 km, against the 250 m crossing test). Refund the line in full and record the phantom charge line for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 201 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii): record trip TRP-00201 as a FALSE-ARRIVAL event against driver DRV-01590 — his 'arrived' marker at 2026-07-23T08:02:14+08:00 was placed while his own GPS trace put him at least 779.9 m from the pickup pin, and the trace contains no qualifying in-geofence fix anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 207 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.00 cancellation fee in full"
- produced: "POL-NS-07: the escalation packet must direct the human reviewer to refund the rider's cancellation fee of SGD 4.00 in full."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 29 |
| Cases graded, by number | 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214 |
| Whole corpus graded | yes — all 29 cases |
| Expected escalations | 5 |
| Produced escalations | 6 |
| **Escalation rate** | **20.7%** |
| Target | 17.2% |
| Off target | yes |
| Precision on ESCALATE | 5 of 6 = 0.833 |
| Recall on ESCALATE | 5 of 5 = 1.0 |

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 1 | 211 |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

The key escalates 4 cases whose record genuinely does not settle the question, and 1 case on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 110, 112, 210, 213 |
| ... the run escalated | 4 of 4 |
| **... the run ruled confidently instead** | **0 of 4** |
| Substantive escalations the key makes | 207 |
| ... the run escalated | 1 of 1 |

## How this was checked

`tests/test_grade.py` feeds each case's own `ground_truth` block back in as though a perfect judge had produced it and requires 29/29 on every field, five escalations, a rate of 17.2%, and precision and recall of 1.0. It then perturbs one field at a time — a ruling, an amount by 0.05, a `null` driver compensation replaced by 0, case 207's referral dropped, a referral added where the key expects none — and requires each perturbation to fail on its own field and on the four-field match, without disturbing the other fields' counts. No model is involved at any point.
