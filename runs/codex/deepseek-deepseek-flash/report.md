# Benchmark report — deepseek/deepseek-flash — development set codex

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/codex/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 3 |
| Rulings produced | 3 |
| **Four-field exact match** | **2/3 = 66.7%** |

| `ruling` | 3/3 = 100.0% |
| `amount_sgd` | 2/3 = 66.7% |
| `driver_compensation_sgd` | 3/3 = 100.0% |
| `referrals` | 3/3 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **2/3 = 66.7%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 9111 | ok | **FAIL** | ok | ok | **FAIL** | current |
| 9113 | ok | ok | ok | ok | ok | current |
| 9114 | ok | ok | ok | ok | ok | current |

## Failures

### Case 9111

Failed on: amount_sgd

- **amount_sgd** — expected 10.15, produced 9.15

## Referrals — expected against produced

### Case 9111 — clause match

- expected: "POL-RD-09(4) billing-integrity referral: phantom ERP gantry lines on EV-FARE-09111, Pioneer Road inbound SGD 1.00 and Tuas South Avenue 8 loop SGD 2.00, neither within 250 m of any GPS fix"
- produced: "POL-RD-09(4) billing integrity: the SGD 2.00 "Tuas South Avenue 8 loop" ERP line on TRP-09111 is charged for a gantry the GPS trace never passes (nearest fix 1,646 m, well outside the 250 m crossing test in POL-RD-09); the line is refunded within the SGD 9.15 and is referred for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09, POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: POL-RD-09
- additional clause(s) offered: POL-RD-09

### Case 9113 — clause match

- expected: "POL-RD-09(4) billing-integrity referral: phantom ERP gantry line on EV-FARE-09113, Pelton lawful diversion entry SGD 1.00, not within 250 m of any GPS fix"
- produced: "POL-RD-09(4) billing integrity: the SGD 1.00 'Pelton lawful diversion entry' ERP line charges a gantry the GPS trace never passes (nearest fix 834.18 m, outside the 250 m crossing radius); refund it in full as a standalone correction and review the fare build."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 9114 — clause match

- expected: "POL-RD-09(4) billing-integrity referral for a phantom ERP gantry line"
- produced: "POL-RD-09(4) billing integrity — refund the phantom SGD 3.20 'Bukit Merah Central westbound' ERP line in full as a standalone pass-through correction and record the billing defect for review; the trace's nearest fix to the gantry is 7,482 m, far outside the 250 m crossing radius, and the fare ledger marks the gantry on_optimal_route = false."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 3 |
| Cases graded, by number | 9111, 9113, 9114 |
| Whole corpus graded | no — 3 of 15 cases |
| Expected escalations | 0 |
| Produced escalations | 0 |
| **Escalation rate (on these 3 cases)** | **0.0%** |
| Precision on ESCALATE (on these 3 cases) | 0 of 0 = n/a |
| Recall on ESCALATE (on these 3 cases) | 0 of 0 = n/a |

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

This report is of the development set `codex`, whose own answer key is `eval/answers/codex/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
