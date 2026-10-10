# Benchmark report — deepseek/deepseek-flash — development set collusion-v1

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/collusion-v1/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 8 |
| Rulings produced | 8 |
| **Four-field exact match** | **8/8 = 100.0%** |

| `ruling` | 8/8 = 100.0% |
| `amount_sgd` | 8/8 = 100.0% |
| `driver_compensation_sgd` | 8/8 = 100.0% |
| `referrals` | 8/8 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **8/8 = 100.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 3301 | ok | ok | ok | ok | ok | current |
| 3302 | ok | ok | ok | ok | ok | current |
| 3303 | ok | ok | ok | ok | ok | current |
| 3304 | ok | ok | ok | ok | ok | current |
| 3305 | ok | ok | ok | ok | ok | current |
| 3306 | ok | ok | ok | ok | ok | current |
| 3307 | ok | ok | ok | ok | ok | current |
| 3308 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3301 | 78111 | 146889 | 188.0 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 3302 | 93023 | 155678 | 280.4 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 3303 | 75966 | 239206 | 365.9 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 3304 | 84156 | 136634 | 154.3 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 3305 | 93370 | 142624 | 251.3 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 3306 | 78213 | 167637 | 157.6 | yes | 1.00 | n/a | n/a | yes | yes | no | no |
| 3307 | 84775 | 155133 | 212.1 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 3308 | 68133 | 157759 | 190.2 | no | 1.00 | charged_total.value | n/a | yes | yes | no | yes |

## Failures

No case failed. Every graded field of every case agrees with the key.

## Referrals — expected against produced

### Case 3304 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.50 cancellation fee in full"
- produced: "POL-NS-07: direct the human reviewer to refund the rider's cancellation fee of SGD 4.50 in full — the anti-farming check on this driver has tripped, so the driver's compensation is withheld and the escalation packet must instruct the reviewer to make the rider whole."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 3308 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review — driver DRV-08830's trailing-90-day deviation counter (deviation_flags_90d = 3) meets the POL-RD-06 pattern test and this trip's deviation is material and substantiated on its own trace."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06, POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: POL-RD-06
- additional clause(s) offered: POL-RD-06

## Escalation calibration

| | |
|---|---|
| Cases graded | 8 |
| Cases graded, by number | 3301, 3302, 3303, 3304, 3305, 3306, 3307, 3308 |
| Whole corpus graded | no — 8 of 8 cases |
| Expected escalations | 3 |
| Produced escalations | 3 |
| **Escalation rate (on these 8 cases)** | **37.5%** |
| Precision on ESCALATE (on these 8 cases) | 3 of 3 = 1.0 |
| Recall on ESCALATE (on these 8 cases) | 3 of 3 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 3 | 3303, 3304, 3306 |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 0 | _none_ |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 3 | 3303, 3304, 3306 |
| Produced escalations in this set | 3 | 3303, 3304, 3306 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 3 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 3303, 3304, 3306 |
| ... the run escalated | 3 of 3 |
| **... the run ruled confidently instead** | **0 of 3** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

## How this was checked

This report is of the development set `collusion-v1`, whose own answer key is `eval/answers/collusion-v1/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
