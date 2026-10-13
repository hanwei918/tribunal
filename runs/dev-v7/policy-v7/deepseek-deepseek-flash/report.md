# Benchmark report — deepseek/deepseek-flash — development set dev-v7

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/dev-v7/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 40 |
| Rulings produced | 40 |
| **Four-field exact match** | **40/40 = 100.0%** **(mixed set — not one measurement)** |

| `ruling` | 40/40 = 100.0% |
| `amount_sgd` | 40/40 = 100.0% |
| `driver_compensation_sgd` | 40/40 = 100.0% |
| `referrals` | 40/40 = 100.0% |

### Cached results

A cached result is evidence about the code that produced it and about nothing else. Each result records the digest of the exact brief bytes its agents were handed and the digest of the prompts they were given, so both are rebuilt now and compared with what was recorded. This does not say a stale result is wrong; it says it is not a measurement of this code.

The prompts have moved for 40 of 40: 5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010, 5011, 5012, 5013, 5014, 5015, 5016, 5017, 5018, 5019, 5020, 5051, 5052, 5053, 5054, 5055, 5056, 5057, 5058, 5059, 5060, 5061, 5062, 5063, 5064, 5065, 5066, 5067, 5068, 5069, 5070. These agents were told to do something other than what this code now asks of them.

**A mixed set is not one run.** The 40/40 exact-match figure above spans results produced by more than one version of the brief or the prompts, so it is not a single measurement of any one version of this code.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **40/40 = 100.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 5001 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5002 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5003 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5004 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5005 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5006 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5007 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5008 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5009 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5010 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5011 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5012 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5013 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5014 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5015 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5016 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5017 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5018 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5019 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5020 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5051 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5052 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5053 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5054 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5055 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5056 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5057 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5058 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5059 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5060 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5061 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5062 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5063 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5064 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5065 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5066 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5067 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5068 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5069 | ok | ok | ok | ok | ok | **STALE (prompt)** |
| 5070 | ok | ok | ok | ok | ok | **STALE (prompt)** |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5001 | 43564 | 81938 | 76.0 | no | 1.00 | excess_distance_fare_sgd.value | n/a | no | yes | no | yes |
| 5002 | 60804 | 77780 | 174.4 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 5003 | 54801 | 168186 | 227.1 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 5004 | 52280 | 84172 | 113.8 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | yes |
| 5005 | 67219 | 115482 | 188.3 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | no |
| 5006 | 84062 | 98606 | 280.3 | no | 1.00 | n/a | n/a | no | yes | yes | no |
| 5007 | 59226 | 82946 | 174.7 | no | 1.00 | n/a | n/a | no | yes | no | yes |
| 5008 | 54743 | 118912 | 140.7 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5009 | 44044 | 164789 | 270.2 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 5010 | 44250 | 89170 | 69.9 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | yes | yes |
| 5011 | 74176 | 220674 | 342.4 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5012 | 54684 | 0 | 72.3 | yes | - | n/a | n/a | no | yes | no | no |
| 5013 | 50054 | 0 | 62.7 | yes | - | n/a | n/a | no | yes | no | no |
| 5014 | 57831 | 130613 | 163.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5015 | 50445 | 81558 | 107.2 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | yes |
| 5016 | 83284 | 102684 | 350.8 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 5017 | 48079 | 182264 | 249.3 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 5018 | 79711 | 81712 | 264.7 | no | 0.75 | n/a | n/a | yes | yes | no | no |
| 5019 | 54782 | 88998 | 140.7 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | yes |
| 5020 | 56182 | 91866 | 150.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5051 | 51232 | 216526 | 507.9 | no | 1.00 | fee_charged_sgd.value | fee_charged_sgd.value | yes | yes | no | yes |
| 5052 | 40127 | 86150 | 104.5 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5053 | 42373 | 74453 | 80.9 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5054 | 48619 | 130592 | 264.5 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5055 | 61095 | 92990 | 167.5 | no | 1.00 | fee_charged_sgd.value | n/a | no | yes | no | yes |
| 5056 | 55284 | 113911 | 182.6 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5057 | 55313 | 111646 | 153.8 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5058 | 52775 | 97915 | 131.3 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5059 | 46892 | 139346 | 233.0 | no | 1.00 | fee_charged_sgd.value | fee_charged_sgd.value | yes | yes | no | yes |
| 5060 | 49659 | 113748 | 166.7 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5061 | 51826 | 92810 | 143.1 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5062 | 65949 | 89069 | 189.4 | no | 1.00 | n/a | n/a | no | yes | no | yes |
| 5063 | 54771 | 83297 | 126.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5064 | 50986 | 135142 | 190.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5065 | 48555 | 109755 | 130.2 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5066 | 36314 | 160721 | 177.7 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5067 | 55433 | 145516 | 285.2 | no | 0.75 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | no | yes | no | no |
| 5068 | 44183 | 0 | 57.1 | yes | - | n/a | n/a | no | yes | no | no |
| 5069 | 53035 | 87573 | 172.5 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5070 | 47945 | 80442 | 106.8 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |

## Failures

No case failed. Every graded field of every case agrees with the key.

## Referrals — expected against produced

### Case 5056 — clause match

- expected: "POL-NS-24: credit the rider SGD 5.00 goodwill (driver did not reach the pickup by the scheduled time + 5 min and made no contact attempt)"
- produced: "POL-NS-24 — the driver both missed the 21:20:00 arrival deadline and made no contact attempt before the rider cancelled at 21:23:15, so the rider is due a 5.00 SGD goodwill credit."
- clause keys, expected: POL-NS-24
- clause keys, produced: POL-NS-24
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 5059 — clause match

- expected: "POL-NS-25: flag rider account R-17281 for Trust & Safety review (3 or more no-show cancellations in 30 days); the ruling on this trip is unchanged"
- produced: "POL-NS-25: flag the rider's account for review — rider_profile.no_show_cancellations_30d is 3 counting this trip where its fee stands, at or above the 3-in-30-days threshold (mandatory upfront payment; temporary suspension pending Trust & Safety review). This referral rides with the ruling and does not change it."
- clause keys, expected: POL-NS-25
- clause keys, produced: POL-NS-25
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 5060 — clause match

- expected: "POL-NS-22: fee-amount check - the record charged SGD 6.50, not the 5.00 no-show fee"
- produced: "POL-NS-22: refer the fee-amount discrepancy — the record charged 6.50 SGD where POL-NS-22 fixes the no-show fee at 5.00 SGD — for review; the money ruling acts on the amount actually charged."
- clause keys, expected: POL-NS-22
- clause keys, produced: POL-NS-22, POL-NS-22
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 40 |
| Cases graded, by number | 5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010, 5011, 5012, 5013, 5014, 5015, 5016, 5017, 5018, 5019, 5020, 5051, 5052, 5053, 5054, 5055, 5056, 5057, 5058, 5059, 5060, 5061, 5062, 5063, 5064, 5065, 5066, 5067, 5068, 5069, 5070 |
| Whole corpus graded | no — 40 of 40 cases |
| Expected escalations | 11 |
| Produced escalations | 11 |
| **Escalation rate (on these 40 cases)** | **27.5%** |
| Precision on ESCALATE (on these 40 cases) | 11 of 11 = 1.0 |
| Recall on ESCALATE (on these 40 cases) | 11 of 11 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 11 | 5008, 5009, 5011, 5012, 5013, 5014, 5017, 5064, 5065, 5066, 5068 |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 0 | _none_ |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 11 | 5008, 5009, 5011, 5012, 5013, 5014, 5017, 5064, 5065, 5066, 5068 |
| Produced escalations in this set | 11 | 5008, 5009, 5011, 5012, 5013, 5014, 5017, 5064, 5065, 5066, 5068 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 8 cases whose record genuinely does not settle the question, and 3 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 5008, 5009, 5011, 5014, 5017, 5064, 5065, 5066 |
| ... the run escalated | 8 of 8 |
| **... the run ruled confidently instead** | **0 of 8** |
| Substantive escalations the key makes | 5012, 5013, 5068 |
| ... the run escalated | 3 of 3 |

## How this was checked

This report is of the development set `answers`, whose own answer key is `eval/answers/dev-v7/answers/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
