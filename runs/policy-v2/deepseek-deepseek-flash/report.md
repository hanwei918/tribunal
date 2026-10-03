# Benchmark report — deepseek/deepseek-flash

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 15 |
| Rulings produced | 15 |
| **Four-field exact match** | **14/15 = 93.3%** |

| `ruling` | 14/15 = 93.3% |
| `amount_sgd` | 14/15 = 93.3% |
| `driver_compensation_sgd` | 15/15 = 100.0% |
| `referrals` | 15/15 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **14/15 = 93.3%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 101 | ok | ok | ok | ok | ok | current |
| 102 | ok | ok | ok | ok | ok | current |
| 103 | ok | ok | ok | ok | ok | current |
| 104 | ok | ok | ok | ok | ok | current |
| 105 | ok | ok | ok | ok | ok | current |
| 106 | ok | ok | ok | ok | ok | current |
| 107 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 108 | ok | ok | ok | ok | ok | current |
| 109 | ok | ok | ok | ok | ok | current |
| 110 | ok | ok | ok | ok | ok | current |
| 111 | ok | ok | ok | ok | ok | current |
| 112 | ok | ok | ok | ok | ok | current |
| 113 | ok | ok | ok | ok | ok | current |
| 114 | ok | ok | ok | ok | ok | current |
| 115 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 51245 | 103158 | 168.1 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 102 | 53548 | 110521 | 230.9 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 103 | 73823 | 135413 | 332.4 | no | 1.00 | erp_lines.off_optimal_route_total.value | n/a | no | yes | no | yes |
| 104 | 68277 | 119309 | 256.7 | no | 1.00 | closure[0].refund.payable.value | n/a | yes | yes | no | yes |
| 105 | 57666 | 123500 | 267.5 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 106 | 57245 | 108613 | 174.1 | no | 0.75 | refund.payable.value | n/a | yes | yes | no | yes |
| 107 | 67303 | 370443 | 1239.8 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 108 | 89294 | 114098 | 360.3 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 109 | 71371 | 149754 | 429.7 | no | 1.00 | unverifiable: not structured | unverifiable: not structured | yes | yes | no | yes |
| 110 | 64453 | 135853 | 320.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 111 | 71739 | 165658 | 502.9 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 112 | 104525 | 280268 | 1049.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 113 | 60511 | 110350 | 230.3 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 114 | 62259 | 122155 | 228.9 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 115 | 67650 | 143365 | 276.8 | no | 1.00 | erp_lines.lines[1].amount_sgd.value | n/a | yes | yes | no | yes |

## Failures

### Case 107

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 7.45, produced null

## Referrals — expected against produced

### Case 105 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review: refer DRV-00932 to driver-conduct review on the established repeat-deviation pattern (deviation_flags_90d = 4 over completed_trips_90d = 344, against a threshold of 3 flags), on a trip found to be a MATERIAL deviation of 18.16 km on its own telemetry."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 115 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: phantom AYE Alexandra Road gantry line of SGD 2.00 on EV-FARE-00115 that the trace never approaches"
- produced: "POL-RD-09(4) billing integrity — the AYE (Alexandra Rd towards Tuas) gantry line of SGD 2.00 on EV-FARE-00115 was charged although the GPS trace EV-GPS-00115 never came within 5,419 m of that gantry and the gantry is not on the optimal route. Refund it as a standalone pass-through correction and log this phantom charge line for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 15 |
| Cases graded, by number | 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115 |
| Whole corpus graded | no — 15 of 29 cases |
| Expected escalations | 2 |
| Produced escalations | 3 |
| **Escalation rate (on these 15 cases)** | **20.0%** |
| Precision on ESCALATE (on these 15 cases) | 2 of 3 = 0.667 |
| Recall on ESCALATE (on these 15 cases) | 2 of 2 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 2 | 110, 112 |
| False positives (run ESCALATE, key does not) | 1 | 107 |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 1 | 107 |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 2 | 110, 112 |
| Produced escalations in this set | 3 | 107, 110, 112 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 1 | 107 |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 2 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 110, 112 |
| ... the run escalated | 2 of 2 |
| **... the run ruled confidently instead** | **0 of 2** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

## How this was checked

This report is of the development set `answers`, whose own answer key is `eval/answers/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
