# Benchmark report — deepseek/deepseek-flash — development set sealed-v1

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/sealed-v1/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 24 |
| Rulings produced | 24 |
| **Four-field exact match** | **21/24 = 87.5%** |

| `ruling` | 21/24 = 87.5% |
| `amount_sgd` | 21/24 = 87.5% |
| `driver_compensation_sgd` | 24/24 = 100.0% |
| `referrals` | 23/24 = 95.8% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **21/24 = 87.5%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 301 | ok | ok | ok | ok | ok | current |
| 302 | ok | ok | ok | ok | ok | current |
| 303 | ok | ok | ok | ok | ok | current |
| 304 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 305 | ok | ok | ok | ok | ok | current |
| 306 | ok | ok | ok | ok | ok | current |
| 307 | ok | ok | ok | ok | ok | current |
| 308 | ok | ok | ok | ok | ok | current |
| 309 | ok | ok | ok | ok | ok | current |
| 310 | ok | ok | ok | ok | ok | current |
| 311 | ok | ok | ok | ok | ok | current |
| 312 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 401 | ok | ok | ok | ok | ok | current |
| 402 | ok | ok | ok | ok | ok | current |
| 403 | ok | ok | ok | ok | ok | current |
| 404 | ok | ok | ok | ok | ok | current |
| 405 | ok | ok | ok | ok | ok | current |
| 406 | ok | ok | ok | ok | ok | current |
| 407 | ok | ok | ok | ok | ok | current |
| 408 | ok | ok | ok | ok | ok | current |
| 409 | ok | ok | ok | ok | ok | current |
| 410 | **FAIL** | **FAIL** | ok | **FAIL** | **FAIL** | current |
| 411 | ok | ok | ok | ok | ok | current |
| 412 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 301 | 69775 | 132473 | 152.3 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 302 | 70509 | 139873 | 152.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 303 | 65715 | 119522 | 112.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 304 | 87020 | 394754 | 601.5 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 305 | 83036 | 172762 | 241.3 | no | 1.00 | components.platform_fee.value + refund.de_minimis.value | components.platform_fee.value + refund.de_minimis.value | yes | yes | no | yes |
| 306 | 72019 | 135502 | 178.9 | no | 1.00 | charged_total.value | n/a | yes | yes | no | yes |
| 307 | 68734 | 143316 | 123.4 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 308 | 62291 | 164469 | 148.4 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 309 | 69010 | 109762 | 118.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 310 | 61316 | 120824 | 79.4 | no | 1.00 | erp_lines.lines[1].amount_sgd.value | n/a | yes | yes | no | yes |
| 311 | 71250 | 247394 | 328.0 | no | 0.75 | refund.payable.value | n/a | yes | yes | yes | yes |
| 312 | 73897 | 139139 | 122.6 | yes | - | n/a | n/a | no | no | no | no |
| 401 | 84909 | 139899 | 213.8 | no | 1.00 | driver_compensation.value | driver_compensation.value | no | yes | no | yes |
| 402 | 86483 | 150569 | 220.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 403 | 97132 | 446179 | 699.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 404 | 81875 | 379640 | 576.2 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 405 | 85665 | 146562 | 200.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 406 | 84217 | 147245 | 211.0 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 407 | 65410 | 135760 | 113.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 408 | 77137 | 143137 | 147.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 409 | 68518 | 132450 | 105.8 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 410 | 76071 | 167103 | 159.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 411 | 67705 | 219311 | 230.0 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 412 | 70310 | 141300 | 140.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |

## Failures

### Case 304

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 1.0, produced null

### Case 312

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 4.1, produced null

### Case 410

Failed on: ruling, amount_sgd, referrals

- **ruling** — expected 'ESCALATE', produced 'FULL_REFUND'
- **amount_sgd** — expected null, produced 4.0
- **referrals** — a referral was produced where the key expects none: POL-NS-05(ii)

## Referrals — expected against produced

### Case 306 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review — refer DRV-10921's conduct on trip TRP-00306 to driver-conduct review: a repeat deviation pattern is established (driver_profile.deviation_flags_90d = 3 against completed_trips_90d = 118) and this trip's deviation is both MATERIAL and substantiated on its own trace."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 310 — clause match

- expected: "POL-RD-09(4) billing integrity"
- produced: "POL-RD-09(4): billing-integrity finding — the $3.00 CTE (Braddell Rd towards City) gantry line on EV-FARE-00310 was charged although the trace (EV-GPS-00310) never came within 250 m of that gantry (nearest fix 5,551 m); refunded in full as a standalone pass-through correction and recorded for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 409 — clause match

- expected: "POL-NS-07 instruction: refund the rider's cancellation fee in full"
- produced: "POL-NS-07 (anti-farming branch, escalation packet): direct the human reviewer to refund the rider's cancellation fee of SGD 4.00 in full; the SGD 4.00 stays held — neither collected nor refunded by the automated pipeline — while that review is pending."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 410 — **no clause match**

- expected: _(none)_
- produced: "POL-NS-05(ii) — record trip TRP-00410 as a false-arrival event against driver DRV-11417: the 2026-08-24T09:10:00+08:00 button-pressed arrival marker was set while the driver's own GPS trace placed him about 850 m from the pickup pin, and no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: _(none)_
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 0 of 0
- additional clauses offered: POL-NS-05(ii)
- additional clause(s) offered: POL-NS-05(ii)
- a referral was produced where the key expects none: POL-NS-05(ii)

## Escalation calibration

| | |
|---|---|
| Cases graded | 24 |
| Cases graded, by number | 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412 |
| Whole corpus graded | no — 24 of 24 cases |
| Expected escalations | 4 |
| Produced escalations | 5 |
| **Escalation rate (on these 24 cases)** | **20.8%** |
| Precision on ESCALATE (on these 24 cases) | 3 of 5 = 0.6 |
| Recall on ESCALATE (on these 24 cases) | 3 of 4 = 0.75 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 3 | 307, 409, 411 |
| False positives (run ESCALATE, key does not) | 2 | 304, 312 |
| False negatives (key ESCALATE, run does not) | 1 | 410 |
| Over-escalations (= false positives) | 2 | 304, 312 |
| Under-escalations (= false negatives) | 1 | 410 |
| Expected escalations in this set | 4 | 307, 409, 410, 411 |
| Produced escalations in this set | 5 | 304, 307, 312, 409, 411 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 2 | 304, 312 |
| Under-escalations (key ESCALATE, produced does not) | 1 | 410 |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 3 cases whose record genuinely does not settle the question, and 1 case on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 307, 410, 411 |
| ... the run escalated | 2 of 3 |
| **... the run ruled confidently instead** | **1 of 3** |
| Substantive escalations the key makes | 409 |
| ... the run escalated | 1 of 1 |

Cases ruled confidently where the record does not settle the question: 410.

## How this was checked

This report is of the development set `sealed-v1`, whose own answer key is `eval/answers/sealed-v1/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
