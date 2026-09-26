# Benchmark report — deepseek/deepseek-flash — development set codex

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/codex/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 15 |
| Rulings produced | 15 |
| **Four-field exact match** | **14/15 = 93.3%** |

| `ruling` | 14/15 = 93.3% |
| `amount_sgd` | 14/15 = 93.3% |
| `driver_compensation_sgd` | 15/15 = 100.0% |
| `referrals` | 14/15 = 93.3% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **14/15 = 93.3%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 9101 | ok | ok | ok | ok | ok | current |
| 9102 | ok | ok | ok | ok | ok | current |
| 9103 | ok | ok | ok | ok | ok | current |
| 9104 | ok | ok | ok | ok | ok | current |
| 9105 | ok | ok | ok | ok | ok | current |
| 9106 | ok | ok | ok | ok | ok | current |
| 9107 | ok | ok | ok | ok | ok | current |
| 9108 | ok | ok | ok | ok | ok | current |
| 9109 | ok | ok | ok | ok | ok | current |
| 9110 | ok | ok | ok | ok | ok | current |
| 9111 | **FAIL** | **FAIL** | ok | **FAIL** | **FAIL** | current |
| 9112 | ok | ok | ok | ok | ok | current |
| 9113 | ok | ok | ok | ok | ok | current |
| 9114 | ok | ok | ok | ok | ok | current |
| 9115 | ok | ok | ok | ok | ok | current |

## Failures

### Case 9111

Failed on: ruling, amount_sgd, referrals

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 10.15, produced null
- **referrals** — expected referral not produced: POL-RD-09(4)

## Referrals — expected against produced

### Case 9104 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii): record trip TRP-09104 as a FALSE-ARRIVAL event against driver DRV-09104 — the 'arrived' marker was set at 2026-09-04T07:25:20+08:00 while EV-GPS-09104 placed the vehicle 559.37 m from the pickup pin, and no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 9108 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.00 cancellation fee in full"
- produced: "POL-NS-07: direct the human reviewer to refund the rider's SGD 4.00 cancellation fee in full; the disputed fee is held rather than collected or refunded while the review is pending."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 9111 — **no clause match**

- expected: "POL-RD-09(4) billing-integrity referral: phantom ERP gantry lines on EV-FARE-09111, Pioneer Road inbound SGD 1.00 and Tuas South Avenue 8 loop SGD 2.00, neither within 250 m of any GPS fix"
- produced: _(none)_
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: _(none)_
- expected clauses matched: 0 of 1
- additional clauses offered: _(none)_
- expected referral not produced: POL-RD-09(4)

### Case 9113 — clause match

- expected: "POL-RD-09(4) billing-integrity referral: phantom ERP gantry line on EV-FARE-09113, Pelton lawful diversion entry SGD 1.00, not within 250 m of any GPS fix"
- produced: "POL-RD-09(4) billing integrity — the SGD 1.00 'Pelton lawful diversion entry' ERP line is charged for a gantry the GPS trace never passes (closest fix 834 m, outside the 250 m match radius); refunded in full and referred for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 9114 — clause match

- expected: "POL-RD-09(4) billing-integrity referral for a phantom ERP gantry line"
- produced: "POL-RD-09(4) billing integrity: the SGD 3.20 'Bukit Merah Central westbound' ERP line was charged for a gantry the GPS trace never crossed (nearest fix 7,482.07 m away, outside the 250 m match radius) and is refunded in full as a phantom charge line."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 15 |
| Cases graded, by number | 9101, 9102, 9103, 9104, 9105, 9106, 9107, 9108, 9109, 9110, 9111, 9112, 9113, 9114, 9115 |
| Whole corpus graded | yes — all 15 cases |
| Expected escalations | 4 |
| Produced escalations | 5 |
| **Escalation rate** | **33.3%** |
| Target | 17.2% |
| Off target | yes |
| Precision on ESCALATE | 4 of 5 = 0.8 |
| Recall on ESCALATE | 4 of 4 = 1.0 |

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 1 | 9111 |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

The key escalates 1 case whose record genuinely does not settle the question, and 3 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 9115 |
| ... the run escalated | 1 of 1 |
| **... the run ruled confidently instead** | **0 of 1** |
| Substantive escalations the key makes | 9108, 9109, 9110 |
| ... the run escalated | 3 of 3 |

## How this was checked

This report is of the development set `codex`, whose own answer key is `eval/answers/codex/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
