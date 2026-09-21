# Grader self-test

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 29 |
| Rulings produced | 29 |
| **Four-field exact match** | **29/29 = 100.0%** |

| `ruling` | 29/29 = 100.0% |
| `amount_sgd` | 29/29 = 100.0% |
| `driver_compensation_sgd` | 29/29 = 100.0% |
| `referrals` | 29/29 = 100.0% |

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **29/29 = 100.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact |
|---|---|---|---|---|---|
| 101 | ok | ok | ok | ok | ok |
| 102 | ok | ok | ok | ok | ok |
| 103 | ok | ok | ok | ok | ok |
| 104 | ok | ok | ok | ok | ok |
| 105 | ok | ok | ok | ok | ok |
| 106 | ok | ok | ok | ok | ok |
| 107 | ok | ok | ok | ok | ok |
| 108 | ok | ok | ok | ok | ok |
| 109 | ok | ok | ok | ok | ok |
| 110 | ok | ok | ok | ok | ok |
| 111 | ok | ok | ok | ok | ok |
| 112 | ok | ok | ok | ok | ok |
| 113 | ok | ok | ok | ok | ok |
| 114 | ok | ok | ok | ok | ok |
| 115 | ok | ok | ok | ok | ok |
| 201 | ok | ok | ok | ok | ok |
| 202 | ok | ok | ok | ok | ok |
| 203 | ok | ok | ok | ok | ok |
| 204 | ok | ok | ok | ok | ok |
| 205 | ok | ok | ok | ok | ok |
| 206 | ok | ok | ok | ok | ok |
| 207 | ok | ok | ok | ok | ok |
| 208 | ok | ok | ok | ok | ok |
| 209 | ok | ok | ok | ok | ok |
| 210 | ok | ok | ok | ok | ok |
| 211 | ok | ok | ok | ok | ok |
| 212 | ok | ok | ok | ok | ok |
| 213 | ok | ok | ok | ok | ok |
| 214 | ok | ok | ok | ok | ok |

## Failures

No case failed. Every graded field of every case agrees with the key.

## Referrals — expected against produced

### Case 105 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review"
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)

### Case 201 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii) false-arrival event recorded against the driver"
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)

### Case 207 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.00 cancellation fee in full"
- produced: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.00 cancellation fee in full"
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07

## Escalation calibration

| | |
|---|---|
| Cases graded | 29 |
| Expected escalations | 5 |
| Produced escalations | 5 |
| **Escalation rate** | **17.2%** |
| Target | 17.2% |
| Off target | no |
| Precision on ESCALATE | 5 of 5 = 1.0 |
| Recall on ESCALATE | 5 of 5 = 1.0 |

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
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
