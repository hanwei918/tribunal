# Benchmark report — deepseek/deepseek-flash — development set dev-v8

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/dev-v8/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 40 |
| Rulings produced | 40 |
| **Four-field exact match** | **39/40 = 97.5%** |

| `ruling` | 39/40 = 97.5% |
| `amount_sgd` | 40/40 = 100.0% |
| `driver_compensation_sgd` | 40/40 = 100.0% |
| `referrals` | 40/40 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **39/40 = 97.5%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 5001 | ok | ok | ok | ok | ok | current |
| 5002 | ok | ok | ok | ok | ok | current |
| 5003 | ok | ok | ok | ok | ok | current |
| 5004 | ok | ok | ok | ok | ok | current |
| 5005 | ok | ok | ok | ok | ok | current |
| 5006 | ok | ok | ok | ok | ok | current |
| 5007 | ok | ok | ok | ok | ok | current |
| 5008 | ok | ok | ok | ok | ok | current |
| 5009 | ok | ok | ok | ok | ok | current |
| 5010 | ok | ok | ok | ok | ok | current |
| 5011 | ok | ok | ok | ok | ok | current |
| 5012 | ok | ok | ok | ok | ok | current |
| 5013 | ok | ok | ok | ok | ok | current |
| 5014 | ok | ok | ok | ok | ok | current |
| 5015 | ok | ok | ok | ok | ok | current |
| 5016 | ok | ok | ok | ok | ok | current |
| 5017 | **FAIL** | ok | ok | ok | **FAIL** | current |
| 5018 | ok | ok | ok | ok | ok | current |
| 5019 | ok | ok | ok | ok | ok | current |
| 5020 | ok | ok | ok | ok | ok | current |
| 5051 | ok | ok | ok | ok | ok | current |
| 5052 | ok | ok | ok | ok | ok | current |
| 5053 | ok | ok | ok | ok | ok | current |
| 5054 | ok | ok | ok | ok | ok | current |
| 5055 | ok | ok | ok | ok | ok | current |
| 5056 | ok | ok | ok | ok | ok | current |
| 5057 | ok | ok | ok | ok | ok | current |
| 5058 | ok | ok | ok | ok | ok | current |
| 5059 | ok | ok | ok | ok | ok | current |
| 5060 | ok | ok | ok | ok | ok | current |
| 5061 | ok | ok | ok | ok | ok | current |
| 5062 | ok | ok | ok | ok | ok | current |
| 5063 | ok | ok | ok | ok | ok | current |
| 5064 | ok | ok | ok | ok | ok | current |
| 5065 | ok | ok | ok | ok | ok | current |
| 5066 | ok | ok | ok | ok | ok | current |
| 5067 | ok | ok | ok | ok | ok | current |
| 5068 | ok | ok | ok | ok | ok | current |
| 5069 | ok | ok | ok | ok | ok | current |
| 5070 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5001 | 38844 | 102957 | 65.8 | no | 1.00 | excess_distance_fare_sgd.value | n/a | no | yes | no | no |
| 5002 | 45943 | 76377 | 114.7 | no | 1.00 | n/a | n/a | no | yes | no | no |
| 5003 | 47941 | 128548 | 162.7 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 5004 | 44404 | 87570 | 87.8 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | no |
| 5005 | 45659 | 132730 | 169.4 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | no |
| 5006 | 60015 | 97730 | 154.5 | no | 0.75 | n/a | n/a | yes | yes | no | yes |
| 5007 | 44902 | 83735 | 94.9 | no | 1.00 | n/a | n/a | yes | yes | no | no |
| 5008 | 51191 | 111217 | 131.0 | yes | 1.00 | n/a | n/a | yes | yes | no | no |
| 5009 | 46855 | 196867 | 299.4 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 5010 | 45380 | 0 | 46.3 | yes | - | n/a | n/a | no | yes | no | no |
| 5011 | 60460 | 171984 | 240.4 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5012 | 47051 | 0 | 43.2 | yes | - | n/a | n/a | no | yes | no | no |
| 5013 | 50053 | 0 | 68.7 | yes | - | n/a | n/a | no | yes | no | no |
| 5014 | 57137 | 138367 | 172.7 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5015 | 47844 | 0 | 60.8 | yes | - | n/a | n/a | no | yes | no | no |
| 5016 | 60147 | 101375 | 168.6 | no | 1.00 | n/a | n/a | no | yes | no | yes |
| 5017 | 65022 | 187774 | 322.1 | no | 0.75 | n/a | n/a | no | yes | no | yes |
| 5018 | 54208 | 83759 | 140.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5019 | 48551 | 109415 | 111.7 | no | 1.00 | excess_distance_fare_sgd.value | n/a | yes | yes | no | yes |
| 5020 | 53688 | 96299 | 104.4 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5051 | 52327 | 137318 | 254.8 | no | 1.00 | fee_charged_sgd.value | fee_charged_sgd.value | yes | yes | no | yes |
| 5052 | 45089 | 79915 | 99.5 | no | 1.00 | fee_charged_sgd.value | n/a | no | yes | no | yes |
| 5053 | 52134 | 80306 | 131.6 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5054 | 51752 | 83298 | 155.2 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5055 | 64209 | 88180 | 173.0 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5056 | 59701 | 95592 | 218.8 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |
| 5057 | 54467 | 100173 | 154.5 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | no |
| 5058 | 59148 | 92723 | 184.7 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5059 | 49991 | 200228 | 378.0 | no | 0.75 | fee_charged_sgd.value | fee_charged_sgd.value | yes | yes | no | yes |
| 5060 | 56372 | 180253 | 333.2 | no | 0.75 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5061 | 49942 | 107805 | 174.4 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5062 | 52810 | 89692 | 132.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5063 | 54392 | 85986 | 140.9 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5064 | 43938 | 170912 | 301.2 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5065 | 48717 | 126818 | 151.6 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5066 | 43238 | 165388 | 266.8 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 5067 | 68784 | 112297 | 248.5 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5068 | 43744 | 0 | 58.7 | yes | - | n/a | n/a | no | yes | no | no |
| 5069 | 45391 | 83881 | 109.6 | no | 1.00 | refund_already_issued_sgd.value | refund_already_issued_sgd.value | yes | yes | no | yes |
| 5070 | 51878 | 81439 | 150.4 | no | 1.00 | fee_charged_sgd.value | n/a | yes | yes | no | yes |

## Failures

### Case 5017

Failed on: ruling

- **ruling** — expected 'ESCALATE', produced 'NO_ACTION'

## Referrals — expected against produced

### Case 5056 — clause match

- expected: "POL-NS-24: credit the rider SGD 5.00 goodwill (driver did not reach the pickup by the scheduled time + 5 min and made no contact attempt)"
- produced: "POL-NS-24: the driver failed to reach the pickup by the scheduled time plus 5 minutes (21:20:00) and also failed to attempt any contact (0 in-app messages, 0 calls), so the rider R-42544 is due a 5.00 SGD goodwill credit."
- clause keys, expected: POL-NS-24
- clause keys, produced: POL-NS-24
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 5059 — clause match

- expected: "POL-NS-25: flag rider account R-17281 for Trust & Safety review (3 or more no-show cancellations in 30 days); the ruling on this trip is unchanged"
- produced: "POL-NS-25: rider_profile.no_show_cancellations_30d stands at 3, and with this trip counted the count is 3 or more — flag the rider's account for review (mandatory upfront payment; temporary suspension pending Trust & Safety review). This referral does not change the ruling on the trip."
- clause keys, expected: POL-NS-25
- clause keys, produced: POL-NS-25
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 5060 — clause match

- expected: "POL-NS-22: fee-amount check - the record charged SGD 6.50, not the 5.00 no-show fee"
- produced: "POL-NS-22: the record charged a 6.50 SGD no-show fee (EV-FARE-05060, fee_matches_policy false), an amount other than the 5.00 SGD the schedule fixes; the platform should review the fee amount charged to the rider."
- clause keys, expected: POL-NS-22
- clause keys, produced: POL-NS-22
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 40 |
| Cases graded, by number | 5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010, 5011, 5012, 5013, 5014, 5015, 5016, 5017, 5018, 5019, 5020, 5051, 5052, 5053, 5054, 5055, 5056, 5057, 5058, 5059, 5060, 5061, 5062, 5063, 5064, 5065, 5066, 5067, 5068, 5069, 5070 |
| Whole corpus graded | no — 40 of 40 cases |
| Expected escalations | 13 |
| Produced escalations | 12 |
| **Escalation rate (on these 40 cases)** | **30.0%** |
| Precision on ESCALATE (on these 40 cases) | 12 of 12 = 1.0 |
| Recall on ESCALATE (on these 40 cases) | 12 of 13 = 0.923 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 12 | 5008, 5009, 5010, 5011, 5012, 5013, 5014, 5015, 5064, 5065, 5066, 5068 |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 1 | 5017 |
| Over-escalations (= false positives) | 0 | _none_ |
| Under-escalations (= false negatives) | 1 | 5017 |
| Expected escalations in this set | 13 | 5008, 5009, 5010, 5011, 5012, 5013, 5014, 5015, 5017, 5064, 5065, 5066, 5068 |
| Produced escalations in this set | 12 | 5008, 5009, 5010, 5011, 5012, 5013, 5014, 5015, 5064, 5065, 5066, 5068 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
| Under-escalations (key ESCALATE, produced does not) | 1 | 5017 |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 8 cases whose record genuinely does not settle the question, and 5 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 5008, 5009, 5011, 5014, 5017, 5064, 5065, 5066 |
| ... the run escalated | 7 of 8 |
| **... the run ruled confidently instead** | **1 of 8** |
| Substantive escalations the key makes | 5010, 5012, 5013, 5015, 5068 |
| ... the run escalated | 5 of 5 |

Cases ruled confidently where the record does not settle the question: 5017.

## How this was checked

This report is of the development set `dev-v8`, whose own answer key is `eval/answers/dev-v8/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
