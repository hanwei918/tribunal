# Benchmark report — deepseek/deepseek-flash — development set ryde-v8

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ryde-v8/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 2 |
| Rulings produced | 2 |
| **Four-field exact match** | **1/2 = 50.0%** |

| `ruling` | 1/2 = 50.0% |
| `amount_sgd` | 1/2 = 50.0% |
| `driver_compensation_sgd` | 1/2 = 50.0% |
| `referrals` | 2/2 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **1/2 = 50.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 902 | ok | ok | ok | ok | ok | current |
| 903 | **FAIL** | **FAIL** | **FAIL** | ok | **FAIL** | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 902 | 58184 | 0 | 94.4 | yes | - | n/a | n/a | no | yes | no | no |
| 903 | 55953 | 202030 | 418.0 | yes | 0.50 | n/a | n/a | no | yes | no | no |

## Failures

### Case 903

Failed on: ruling, amount_sgd, driver_compensation_sgd

- **ruling** — expected 'DRIVER_COMPENSATION', produced 'ESCALATE'
- **amount_sgd** — expected 5.0, produced null
- **driver_compensation_sgd** — expected 5.0, produced null

## Referrals — expected against produced

No case carries a referral on either side.

## Escalation calibration

| | |
|---|---|
| Cases graded | 2 |
| Cases graded, by number | 902, 903 |
| Whole corpus graded | no — 2 of 2 cases |
| Expected escalations | 1 |
| Produced escalations | 2 |
| **Escalation rate (on these 2 cases)** | **100.0%** |
| Precision on ESCALATE (on these 2 cases) | 1 of 2 = 0.5 |
| Recall on ESCALATE (on these 2 cases) | 1 of 1 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 1 | 902 |
| False positives (run ESCALATE, key does not) | 1 | 903 |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 1 | 903 |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 1 | 902 |
| Produced escalations in this set | 2 | 902, 903 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 1 | 903 |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 0 cases whose record genuinely does not settle the question, and 1 case on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | _none_ |
| ... the run escalated | 0 of 0 |
| **... the run ruled confidently instead** | **0 of 0** |
| Substantive escalations the key makes | 902 |
| ... the run escalated | 1 of 1 |

## How this was checked

This report is of the development set `ryde-v8`, whose own answer key is `eval/answers/ryde-v8/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
