# Benchmark report — deepseek/deepseek-flash — development set wild-dev

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/wild/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 37 |
| Rulings produced | 37 |
| **Four-field exact match** | **35/37 = 94.6%** |

| `ruling` | 35/37 = 94.6% |
| `amount_sgd` | 36/37 = 97.3% |
| `driver_compensation_sgd` | 37/37 = 100.0% |
| `referrals` | 37/37 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **35/37 = 94.6%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 501 | ok | ok | ok | ok | ok | current |
| 502 | ok | ok | ok | ok | ok | current |
| 503 | ok | ok | ok | ok | ok | current |
| 504 | ok | ok | ok | ok | ok | current |
| 505 | ok | ok | ok | ok | ok | current |
| 506 | ok | ok | ok | ok | ok | current |
| 507 | ok | ok | ok | ok | ok | current |
| 508 | ok | ok | ok | ok | ok | current |
| 509 | ok | ok | ok | ok | ok | current |
| 510 | ok | ok | ok | ok | ok | current |
| 511 | ok | ok | ok | ok | ok | current |
| 512 | ok | ok | ok | ok | ok | current |
| 513 | ok | ok | ok | ok | ok | current |
| 514 | ok | ok | ok | ok | ok | current |
| 515 | ok | ok | ok | ok | ok | current |
| 516 | ok | ok | ok | ok | ok | current |
| 517 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 518 | ok | ok | ok | ok | ok | current |
| 519 | ok | ok | ok | ok | ok | current |
| 520 | ok | ok | ok | ok | ok | current |
| 521 | ok | ok | ok | ok | ok | current |
| 522 | ok | ok | ok | ok | ok | current |
| 523 | **FAIL** | ok | ok | ok | **FAIL** | current |
| 524 | ok | ok | ok | ok | ok | current |
| 525 | ok | ok | ok | ok | ok | current |
| 526 | ok | ok | ok | ok | ok | current |
| 527 | ok | ok | ok | ok | ok | current |
| 528 | ok | ok | ok | ok | ok | current |
| 529 | ok | ok | ok | ok | ok | current |
| 530 | ok | ok | ok | ok | ok | current |
| 531 | ok | ok | ok | ok | ok | current |
| 532 | ok | ok | ok | ok | ok | current |
| 533 | ok | ok | ok | ok | ok | current |
| 534 | ok | ok | ok | ok | ok | current |
| 535 | ok | ok | ok | ok | ok | current |
| 536 | ok | ok | ok | ok | ok | current |
| 537 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 501 | 71534 | 124385 | 310.7 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | yes | yes |
| 502 | 63422 | 117615 | 262.4 | no | 1.00 | charged_total.value | n/a | yes | yes | no | yes |
| 503 | 60790 | 108721 | 231.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 504 | 51487 | 97444 | 151.5 | no | 0.75 | refund.refund_before_rounding.value | n/a | yes | yes | no | yes |
| 505 | 55329 | 102966 | 172.5 | no | 0.75 | refund.payable.value | n/a | yes | yes | no | yes |
| 506 | 60480 | 116644 | 275.0 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 507 | 61149 | 110279 | 228.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 508 | 50314 | 98530 | 151.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 509 | 62271 | 192424 | 563.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 510 | 51646 | 105149 | 181.3 | no | 0.75 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 511 | 77460 | 123681 | 363.6 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 512 | 56759 | 195926 | 532.7 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 513 | 58525 | 124345 | 276.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 514 | 67390 | 121068 | 314.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 515 | 75570 | 135103 | 344.1 | no | 1.00 | charged_total.value | n/a | yes | yes | no | yes |
| 516 | 61574 | 118876 | 251.9 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 517 | 69052 | 332527 | 1069.4 | yes | 0.25 | n/a | n/a | no | no | no | no |
| 518 | 60403 | 111575 | 239.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 519 | 57117 | 99801 | 192.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 520 | 74074 | 151959 | 448.3 | no | 1.00 | unverifiable: not structured | unverifiable: not structured | yes | yes | no | yes |
| 521 | 52290 | 110780 | 199.7 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 522 | 60773 | 186577 | 563.2 | no | 0.75 | n/a | n/a | yes | yes | no | yes |
| 523 | 59070 | 195758 | 565.1 | yes | 0.50 | n/a | n/a | no | yes | no | no |
| 524 | 55838 | 100326 | 204.2 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 525 | 54100 | 98910 | 191.7 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 526 | 71476 | 145359 | 425.4 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 527 | 59871 | 105075 | 213.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 528 | 63087 | 101846 | 223.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 529 | 65766 | 125533 | 314.4 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 530 | 54454 | 101901 | 179.3 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 531 | 66809 | 166011 | 527.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 532 | 71921 | 107849 | 273.3 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 533 | 58959 | 103791 | 201.2 | no | 1.00 | not a published figure | n/a | yes | yes | no | yes |
| 534 | 53050 | 105291 | 181.4 | no | 1.00 | refund.refund_before_rounding.value | n/a | yes | yes | yes | yes |
| 535 | 77766 | 101967 | 277.6 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 536 | 61941 | 121745 | 291.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 537 | 55735 | 124712 | 211.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |

## Failures

### Case 517

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 33.5, produced null

### Case 523

Failed on: ruling

- **ruling** — expected 'NO_ACTION', produced 'ESCALATE'

## Referrals — expected against produced

### Case 502 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review: the repeat-deviation pattern is established on driver_profile.deviation_flags_90d = 4 against 210 completed trips in 90 days, so this driver's conduct on TRP-00502 is referred to driver-conduct review. The referral does not displace or delay the monetary ruling."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 515 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c): refer driver DRV-21377 to driver-conduct review — a repeat deviation pattern is established (deviation_flags_90d = 3 against completed_trips_90d = 180), which requires the referral independently of the monetary outcome."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 516 — clause match

- expected: "POL-RD-09(4) billing integrity"
- produced: "POL-RD-09(4) billing-integrity review: refund the SGD 3.00 AYE (Alexandra Rd towards City) ERP line charged for a gantry the GPS trace never crossed (nearest fix 2,608.77 m, outside the 250 m match radius); record the billing-integrity finding."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 521 — clause match

- expected: "POL-RD-09(4) billing integrity"
- produced: "POL-RD-09(4) billing integrity: the SGD 2.00 ERP line for gantry 'CTE (Braddell Rd towards City)' on TRP-00521 was charged for a line the GPS trace never crossed, so it is a phantom charge. It has been refunded in full as a standalone pass-through correction; review the ERP selection on this trip (the driver's statement records a possible mistaken selection) as a billing-integrity matter."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 532 — clause match

- expected: "POL-RD-09(4) billing integrity"
- produced: "POL-RD-09(4) billing integrity: the SGD 6.00 CTE (Ang Mo Kio Ave 1 towards City) ERP line was charged for a gantry the GPS trace never passed (nearest fix 1,159.02 m, outside the 250 m crossing radius) and has been refunded in full as a standalone pass-through correction."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 37 |
| Cases graded, by number | 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532, 533, 534, 535, 536, 537 |
| Whole corpus graded | no — 37 of 64 cases |
| Expected escalations | 1 |
| Produced escalations | 3 |
| **Escalation rate (on these 37 cases)** | **8.1%** |
| Precision on ESCALATE (on these 37 cases) | 1 of 3 = 0.333 |
| Recall on ESCALATE (on these 37 cases) | 1 of 1 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 1 | 512 |
| False positives (run ESCALATE, key does not) | 2 | 517, 523 |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 2 | 517, 523 |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 1 | 512 |
| Produced escalations in this set | 3 | 512, 517, 523 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 2 | 517, 523 |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 1 case whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 512 |
| ... the run escalated | 1 of 1 |
| **... the run ruled confidently instead** | **0 of 1** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

## How this was checked

This report is of the development set `wild`, whose own answer key is `eval/answers/wild/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
