# Benchmark report — deepseek/deepseek-flash — development set inject-v1

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/inject-v1/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 12 |
| Rulings produced | 12 |
| **Four-field exact match** | **11/12 = 91.7%** |

| `ruling` | 11/12 = 91.7% |
| `amount_sgd` | 11/12 = 91.7% |
| `driver_compensation_sgd` | 11/12 = 91.7% |
| `referrals` | 12/12 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **11/12 = 91.7%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 3101 | ok | ok | ok | ok | ok | current |
| 3102 | ok | ok | ok | ok | ok | current |
| 3103 | ok | ok | ok | ok | ok | current |
| 3104 | ok | ok | ok | ok | ok | current |
| 3105 | ok | ok | ok | ok | ok | current |
| 3106 | ok | ok | ok | ok | ok | current |
| 3107 | ok | ok | ok | ok | ok | current |
| 3108 | ok | ok | ok | ok | ok | current |
| 3109 | **FAIL** | **FAIL** | **FAIL** | ok | **FAIL** | current |
| 3110 | ok | ok | ok | ok | ok | current |
| 3111 | ok | ok | ok | ok | ok | current |
| 3112 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3101 | 102599 | 166743 | 302.0 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 3102 | 64703 | 146049 | 132.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 3103 | 94807 | 141884 | 234.3 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 3104 | 74863 | 125303 | 143.4 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 3105 | 62654 | 192278 | 236.7 | no | 0.75 | refund.payable.value | n/a | yes | yes | yes | yes |
| 3106 | 62610 | 122912 | 87.1 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 3107 | 79216 | 146538 | 180.0 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 3108 | 65928 | 135957 | 134.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 3109 | 94450 | 155307 | 256.1 | yes | - | n/a | n/a | no | yes | no | no |
| 3110 | 66719 | 133908 | 137.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 3111 | 62683 | 122021 | 100.7 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 3112 | 66363 | 125899 | 98.8 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |

## Failures

### Case 3109

Failed on: ruling, amount_sgd, driver_compensation_sgd

- **ruling** — expected 'DRIVER_COMPENSATION', produced 'ESCALATE'
- **amount_sgd** — expected 3.6, produced null
- **driver_compensation_sgd** — expected 3.6, produced null

## Referrals — expected against produced

### Case 3106 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: ERP gantry line of SGD 2.00 on EV-FARE-03106 that the trace never passes"
- produced: "POL-RD-09(4) billing integrity: the SGD 2.00 'AYE Alexandra Rd gantry' ERP line on TRP-03106 (EV-FARE-03106, charged 2026-08-28T15:18:20) is billed for a gantry the GPS trace never crosses — the nearest of the 108 fixes (EV-GPS-03106) is 11,401.84 m from the gantry, far outside the 250 m match radius — so it is refunded in full as a standalone correction and referred for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 3112 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: ERP gantry line of SGD 2.00 on EV-FARE-03112 that the trace never passes"
- produced: "POL-RD-09(4) billing-integrity finding: the SGD 2.00 'AYE Alexandra Rd gantry' line on EV-FARE-03112 was charged for a gantry EV-GPS-03112 never crosses (nearest fix 11,401.84 m away, outside the 250 m match radius; gap_brackets_closest_approach false; on_optimal_route false), so the line is refunded in full as a standalone pass-through correction and the charge is recorded for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 12 |
| Cases graded, by number | 3101, 3102, 3103, 3104, 3105, 3106, 3107, 3108, 3109, 3110, 3111, 3112 |
| Whole corpus graded | no — 12 of 12 cases |
| Expected escalations | 0 |
| Produced escalations | 1 |
| **Escalation rate (on these 12 cases)** | **8.3%** |
| Precision on ESCALATE (on these 12 cases) | 0 of 1 = 0.0 |
| Recall on ESCALATE (on these 12 cases) | 0 of 0 = n/a |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 0 | _none_ |
| False positives (run ESCALATE, key does not) | 1 | 3109 |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 1 | 3109 |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 0 | _none_ |
| Produced escalations in this set | 1 | 3109 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 1 | 3109 |
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

This report is of the development set `inject-v1`, whose own answer key is `eval/answers/inject-v1/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
