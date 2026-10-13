# Benchmark report — deepseek/deepseek-flash — development set sealed-v4

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/sealed-v4/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 30 |
| Rulings produced | 30 |
| **Four-field exact match** | **30/30 = 100.0%** **(mixed set — not one measurement)** |

| `ruling` | 30/30 = 100.0% |
| `amount_sgd` | 30/30 = 100.0% |
| `driver_compensation_sgd` | 30/30 = 100.0% |
| `referrals` | 30/30 = 100.0% |

### Cached results

A cached result is evidence about the code that produced it and about nothing else. Each result records the digest of the exact brief bytes its agents were handed and the digest of the prompts they were given, so both are rebuilt now and compared with what was recorded. This does not say a stale result is wrong; it says it is not a measurement of this code.

The prompts have moved for 30 of 30: 6001, 6002, 6003, 6004, 6005, 6006, 6007, 6008, 6009, 6010, 6011, 6012, 6013, 6014, 6015, 6051, 6052, 6053, 6054, 6055, 6056, 6057, 6058, 6059, 6060, 6061, 6062, 6063, 6064, 6065. These agents were told to do something other than what this code now asks of them.

**A mixed set is not one run.** The 30/30 exact-match figure above spans results produced by more than one version of the brief or the prompts, so it is not a single measurement of any one version of this code.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **30/30 = 100.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 6001 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6002 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6003 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6004 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6005 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6006 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6007 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6008 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6009 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6010 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6011 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6012 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6013 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6014 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6015 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6051 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6052 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6053 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6054 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6055 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6056 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6057 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6058 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6059 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6060 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6061 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6062 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6063 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6064 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 6065 | ok | ok | ok | ok | ok | **STALE (prompt)** |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6001 | 45461 | 80583 | 122.9 | no | 1.00 | excess_distance_fare_sgd.value | n/a | no | yes | no | yes |
| 6002 | 57398 | 72018 | 160.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 6003 | 52299 | 121922 | 153.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 6004 | 56082 | 97081 | 128.6 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | yes | no |
| 6005 | 55117 | 170805 | 274.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 6006 | 48555 | 94767 | 115.7 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | no |
| 6007 | 54716 | 117571 | 142.3 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 6008 | 47886 | 192144 | 262.5 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 6009 | 54460 | 104285 | 97.4 | no | 1.00 | excess_distance_fare_sgd.value | n/a | no | yes | no | yes |
| 6010 | 56643 | 0 | 58.0 | yes | - | n/a | n/a | no | yes | no | no |
| 6011 | 46296 | 0 | 52.5 | yes | - | n/a | n/a | no | yes | no | no |
| 6012 | 55626 | 359528 | 663.7 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 6013 | 42021 | 85708 | 62.9 | no | 1.00 | excess_distance_fare_sgd.value | n/a | no | yes | no | yes |
| 6014 | 75834 | 105781 | 243.5 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 6015 | 55581 | 78052 | 148.6 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 6051 | 50645 | 137082 | 293.6 | no | 1.00 | fee_charged_sgd.value | fee_charged_sgd.value | yes | yes | no | yes |
| 6052 | 40669 | 75439 | 78.8 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | no |
| 6053 | 41648 | 80929 | 94.7 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 6054 | 52499 | 87122 | 135.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 6055 | 64073 | 96011 | 200.7 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 6056 | 62077 | 108641 | 183.4 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 6057 | 60960 | 85044 | 182.6 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 6058 | 73227 | 97963 | 258.6 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 6059 | 45448 | 87529 | 125.8 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 6060 | 52078 | 87341 | 137.2 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 6061 | 47248 | 126344 | 153.1 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 6062 | 49690 | 143661 | 184.0 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 6063 | 39397 | 0 | 38.3 | yes | - | n/a | n/a | no | yes | no | no |
| 6064 | 39933 | 81286 | 83.1 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 6065 | 46737 | 112702 | 122.3 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |

## Failures

No case failed. Every graded field of every case agrees with the key.

## Referrals — expected against produced

### Case 6056 — clause match

- expected: "POL-NS-24: credit the rider SGD 5.00 goodwill (driver did not reach the pickup by the scheduled time + 5 min and made no contact attempt)"
- produced: "POL-NS-24: record the 5.00 SGD goodwill credit to the rider, the driver having both failed to reach the pickup point and failed to attempt contact (EV-FARE-06056, goodwill_credit_sgd = 5.00)."
- clause keys, expected: POL-NS-24
- clause keys, produced: POL-NS-24
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 6058 — clause match

- expected: "POL-NS-25: flag rider account R-80737 for Trust & Safety review (3 or more no-show cancellations in 30 days); the ruling on this trip is unchanged"
- produced: "POL-NS-25: flag the rider's account for review — rider_profile.no_show_cancellations_30d is 4, at or above the threshold of 3 counting this trip whose fee stands; mandatory upfront payment and temporary suspension pending Trust & Safety review."
- clause keys, expected: POL-NS-25
- clause keys, produced: POL-NS-25
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 6059 — clause match

- expected: "POL-NS-22: fee-amount check - the record charged SGD 4.00, not the 5.00 no-show fee"
- produced: "POL-NS-22: the record charged 4.00 SGD for the no-show rather than the 5.00 SGD the policy fixes; the ruling acts on the 4.00 SGD actually charged and the 1.00 SGD discrepancy is referred for review."
- clause keys, expected: POL-NS-22
- clause keys, produced: POL-NS-22
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 30 |
| Cases graded, by number | 6001, 6002, 6003, 6004, 6005, 6006, 6007, 6008, 6009, 6010, 6011, 6012, 6013, 6014, 6015, 6051, 6052, 6053, 6054, 6055, 6056, 6057, 6058, 6059, 6060, 6061, 6062, 6063, 6064, 6065 |
| Whole corpus graded | no — 30 of 30 cases |
| Expected escalations | 9 |
| Produced escalations | 9 |
| **Escalation rate (on these 30 cases)** | **30.0%** |
| Precision on ESCALATE (on these 30 cases) | 9 of 9 = 1.0 |
| Recall on ESCALATE (on these 30 cases) | 9 of 9 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 9 | 6007, 6008, 6010, 6011, 6012, 6061, 6062, 6063, 6065 |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 0 | _none_ |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 9 | 6007, 6008, 6010, 6011, 6012, 6061, 6062, 6063, 6065 |
| Produced escalations in this set | 9 | 6007, 6008, 6010, 6011, 6012, 6061, 6062, 6063, 6065 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 6 cases whose record genuinely does not settle the question, and 3 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 6007, 6008, 6012, 6061, 6062, 6065 |
| ... the run escalated | 6 of 6 |
| **... the run ruled confidently instead** | **0 of 6** |
| Substantive escalations the key makes | 6010, 6011, 6063 |
| ... the run escalated | 3 of 3 |

## How this was checked

This report is of the development set `answers`, whose own answer key is `eval/answers/sealed-v4/answers/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
