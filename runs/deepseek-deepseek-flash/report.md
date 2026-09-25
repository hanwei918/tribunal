# Benchmark report — deepseek/deepseek-flash

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 4 |
| Rulings produced | 4 |
| **Four-field exact match** | **4/4 = 100.0%** |

| `ruling` | 4/4 = 100.0% |
| `amount_sgd` | 4/4 = 100.0% |
| `driver_compensation_sgd` | 4/4 = 100.0% |
| `referrals` | 4/4 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **4/4 = 100.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 103 | ok | ok | ok | ok | ok | current |
| 106 | ok | ok | ok | ok | ok | current |
| 114 | ok | ok | ok | ok | ok | current |
| 115 | ok | ok | ok | ok | ok | current |

## Failures

No case failed. Every graded field of every case agrees with the key.

## Referrals — expected against produced

### Case 115 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: phantom AYE Alexandra Road gantry line of SGD 2.00 on EV-FARE-00115 that the trace never approaches"
- produced: "POL-RD-09(4) billing integrity: the SGD 2.00 AYE (Alexandra Rd towards Tuas) gantry line on EV-FARE-00115 is a phantom charge — the GPS trace EV-GPS-00115 never comes within 250 m of that gantry (nearest fix 5,419 m, at the first fix of the trip) — and has been refunded as a standalone correction; the ledger's gantry tagging for this trip requires review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 4 |
| Cases graded, by number | 103, 106, 114, 115 |
| Whole corpus graded | no — 4 of 29 cases |
| Expected escalations | 0 |
| Produced escalations | 0 |
| **Escalation rate (on these 4 cases)** | **0.0%** |
| Precision on ESCALATE (on these 4 cases) | 0 of 0 = n/a |
| Recall on ESCALATE (on these 4 cases) | 0 of 0 = n/a |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 0 | _none_ |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 0 | _none_ |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 0 | _none_ |
| Produced escalations in this set | 0 | _none_ |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 0 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | _none_ |
| ... the run escalated | 0 of 0 |
| **... the run ruled confidently instead** | **0 of 0** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

## How this was checked

`tests/test_grade.py` feeds each case's own `ground_truth` block back in as though a perfect judge had produced it and requires 29/29 on every field, five escalations, a rate of 17.2%, and precision and recall of 1.0. It then perturbs one field at a time — a ruling, an amount by 0.05, a `null` driver compensation replaced by 0, case 207's referral dropped, a referral added where the key expects none — and requires each perturbation to fail on its own field and on the four-field match, without disturbing the other fields' counts. No model is involved at any point.
