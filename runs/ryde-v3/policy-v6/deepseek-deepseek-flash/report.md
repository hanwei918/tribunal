# Benchmark report — deepseek/deepseek-flash — development set ryde-v3

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/external/ryde/expected.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 0 |
| Rulings produced | 0 |
| **Four-field exact match** | **0/0 = n/a** |

| `ruling` | 0/0 = n/a |
| `amount_sgd` | 0/0 = n/a |
| `driver_compensation_sgd` | 0/0 = n/a |
| `referrals` | 0/0 = n/a |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **0/0 = n/a**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|

## Failures

No case failed. Every graded field of every case agrees with the key.

## Referrals — expected against produced

No case carries a referral on either side.

## Escalation calibration

| | |
|---|---|
| Cases graded | 0 |
| Cases graded, by number | _none_ |
| Whole corpus graded | no — 0 of 0 cases |
| Expected escalations | 0 |
| Produced escalations | 0 |
| **Escalation rate (on these 0 cases)** | **n/a** |
| Precision on ESCALATE (on these 0 cases) | 0 of 0 = n/a |
| Recall on ESCALATE (on these 0 cases) | 0 of 0 = n/a |

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

This report is of the development set `ryde`, whose own answer key is `eval/external/ryde/expected.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
