# Benchmark report — deepseek/deepseek-flash — development set ryde-v7

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ryde-v7/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 2 |
| Rulings produced | 2 |
| **Four-field exact match** | **0/2 = 0.0%** **(mixed set — not one measurement)** |

| `ruling` | 0/2 = 0.0% |
| `amount_sgd` | 0/2 = 0.0% |
| `driver_compensation_sgd` | 1/2 = 50.0% |
| `referrals` | 2/2 = 100.0% |

### Cached results

A cached result is evidence about the code that produced it and about nothing else. Each result records the digest of the exact brief bytes its agents were handed and the digest of the prompts they were given, so both are rebuilt now and compared with what was recorded. This does not say a stale result is wrong; it says it is not a measurement of this code.

The prompts have moved for 2 of 2: 902, 903. These agents were told to do something other than what this code now asks of them.

**A mixed set is not one run.** The 0/2 exact-match figure above spans results produced by more than one version of the brief or the prompts, so it is not a single measurement of any one version of this code.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **0/2 = 0.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 902 | **FAIL** | **FAIL** | ok | ok | **FAIL** | **STALE (prompt)** |
| 903 | **FAIL** | **FAIL** | **FAIL** | ok | **FAIL** | **STALE (prompt)** |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 902 | 55884 | 112587 | 159.6 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 903 | 65074 | 187621 | 323.8 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |

## Failures

### Case 902

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 3.44, produced null

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
| Expected escalations | 0 |
| Produced escalations | 2 |
| **Escalation rate (on these 2 cases)** | **100.0%** |
| Precision on ESCALATE (on these 2 cases) | 0 of 2 = 0.0 |
| Recall on ESCALATE (on these 2 cases) | 0 of 0 = n/a |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 0 | _none_ |
| False positives (run ESCALATE, key does not) | 2 | 902, 903 |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 2 | 902, 903 |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 0 | _none_ |
| Produced escalations in this set | 2 | 902, 903 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 2 | 902, 903 |
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

This report is of the development set `ryde-v7`, whose own answer key is `eval/answers/ryde-v7/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
