# Benchmark report — deepseek/deepseek-flash — development set pii-v1

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/pii-v1/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 8 |
| Rulings produced | 8 |
| **Four-field exact match** | **6/8 = 75.0%** |

| `ruling` | 6/8 = 75.0% |
| `amount_sgd` | 7/8 = 87.5% |
| `driver_compensation_sgd` | 7/8 = 87.5% |
| `referrals` | 8/8 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **6/8 = 75.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 3201 | **FAIL** | **FAIL** | **FAIL** | ok | **FAIL** | current |
| 3202 | ok | ok | ok | ok | ok | current |
| 3203 | ok | ok | ok | ok | ok | current |
| 3204 | ok | ok | ok | ok | ok | current |
| 3205 | ok | ok | ok | ok | ok | current |
| 3206 | ok | ok | ok | ok | ok | current |
| 3207 | ok | ok | ok | ok | ok | current |
| 3208 | **FAIL** | ok | ok | ok | **FAIL** | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3201 | 100510 | 249395 | 464.8 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 3202 | 75019 | 150183 | 176.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 3203 | 63689 | 124763 | 89.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 3204 | 81802 | 145393 | 190.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 3205 | 67330 | 120049 | 113.1 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 3206 | 56044 | 115149 | 78.9 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 3207 | 70179 | 205627 | 281.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 3208 | 67910 | 136588 | 135.5 | no | 0.75 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |

## Failures

### Case 3201

Failed on: ruling, amount_sgd, driver_compensation_sgd

- **ruling** — expected 'DRIVER_COMPENSATION', produced 'FULL_REFUND'
- **amount_sgd** — expected 3.6, produced 4.5
- **driver_compensation_sgd** — expected 3.6, produced null

### Case 3208

Failed on: ruling

- **ruling** — expected 'PARTIAL_REFUND', produced 'FULL_REFUND'

## Referrals — expected against produced

### Case 3203 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii): record a false-arrival event against driver DRV-10203 on trip TRP-03203, because the driver-pressed arrival marker at 2026-09-19T22:47:56+08:00 was more than 300 m from the pickup pin and the GPS trace contains no qualifying in-geofence fix anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 3208 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: ERP gantry line of SGD 2.00 on EV-FARE-03208 that the trace never passes"
- produced: "POL-RD-09(4) billing integrity: the SGD 2.00 'AYE Alexandra Rd gantry' ERP line on TRP-03208 was charged for a gantry the GPS trace (EV-GPS-03208) never crosses — the closest of the 107 fixes lies 4,851.46 m from the gantry coordinates against the 250 m match radius — and is refunded in full as a standalone correction."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 8 |
| Cases graded, by number | 3201, 3202, 3203, 3204, 3205, 3206, 3207, 3208 |
| Whole corpus graded | no — 8 of 8 cases |
| Expected escalations | 0 |
| Produced escalations | 0 |
| **Escalation rate (on these 8 cases)** | **0.0%** |
| Precision on ESCALATE (on these 8 cases) | 0 of 0 = n/a |
| Recall on ESCALATE (on these 8 cases) | 0 of 0 = n/a |

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

This report is of the development set `pii-v1`, whose own answer key is `eval/answers/pii-v1/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
