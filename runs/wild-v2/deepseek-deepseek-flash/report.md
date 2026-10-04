# Benchmark report — deepseek/deepseek-flash — development set wild-v2

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/wild-v2/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 20 |
| Rulings produced | 20 |
| **Four-field exact match** | **18/20 = 90.0%** |

| `ruling` | 18/20 = 90.0% |
| `amount_sgd` | 20/20 = 100.0% |
| `driver_compensation_sgd` | 20/20 = 100.0% |
| `referrals` | 20/20 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **18/20 = 90.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 701 | ok | ok | ok | ok | ok | current |
| 702 | **FAIL** | ok | ok | ok | **FAIL** | current |
| 703 | ok | ok | ok | ok | ok | current |
| 704 | ok | ok | ok | ok | ok | current |
| 705 | ok | ok | ok | ok | ok | current |
| 706 | ok | ok | ok | ok | ok | current |
| 707 | ok | ok | ok | ok | ok | current |
| 708 | ok | ok | ok | ok | ok | current |
| 709 | ok | ok | ok | ok | ok | current |
| 710 | ok | ok | ok | ok | ok | current |
| 711 | ok | ok | ok | ok | ok | current |
| 712 | ok | ok | ok | ok | ok | current |
| 713 | ok | ok | ok | ok | ok | current |
| 714 | ok | ok | ok | ok | ok | current |
| 715 | ok | ok | ok | ok | ok | current |
| 716 | **FAIL** | ok | ok | ok | **FAIL** | current |
| 717 | ok | ok | ok | ok | ok | current |
| 718 | ok | ok | ok | ok | ok | current |
| 719 | ok | ok | ok | ok | ok | current |
| 720 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 701 | 61024 | 168440 | 329.9 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 702 | 60232 | 228581 | 734.3 | yes | 0.25 | n/a | n/a | no | no | no | no |
| 703 | 55640 | 97225 | 207.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 704 | 71119 | 174643 | 576.0 | no | 1.00 | n/a | n/a | no | yes | no | yes |
| 705 | 63567 | 105964 | 274.9 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 706 | 58578 | 99505 | 219.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 707 | 50572 | 103568 | 215.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 708 | 66037 | 276755 | 901.0 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 709 | 81280 | 109406 | 327.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 710 | 54976 | 115355 | 237.9 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 711 | 65003 | 139618 | 378.5 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 712 | 58702 | 105459 | 171.0 | no | 1.00 | erp_lines.lines[2].amount_sgd.value | n/a | yes | yes | no | yes |
| 713 | 61125 | 204258 | 645.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 714 | 67033 | 174186 | 546.2 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 715 | 68125 | 158999 | 509.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 716 | 62684 | 199274 | 620.6 | no | 0.75 | n/a | n/a | yes | yes | no | yes |
| 717 | 63804 | 181341 | 567.3 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 718 | 57259 | 125109 | 196.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 719 | 68172 | 148786 | 432.0 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 720 | 55214 | 172459 | 502.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |

## Failures

### Case 702

Failed on: ruling

- **ruling** — expected 'NO_ACTION', produced 'ESCALATE'

### Case 716

Failed on: ruling

- **ruling** — expected 'ESCALATE', produced 'NO_ACTION'

## Referrals — expected against produced

### Case 712 — clause match

- expected: "POL-RD-09(4) billing-integrity review: North service-loop ERP (SGD 8.00) never passed"
- produced: "POL-RD-09(4) billing integrity: the SGD 8.00 'North service-loop ERP' line was charged for a gantry the GPS trace never crossed (closest approach 16,784.57 m against the 250 m match radius). Record the phantom-line charge as a billing-integrity finding and review the gantry matching for trip TRP-00712."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 20 |
| Cases graded, by number | 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715, 716, 717, 718, 719, 720 |
| Whole corpus graded | no — 20 of 20 cases |
| Expected escalations | 5 |
| Produced escalations | 5 |
| **Escalation rate (on these 20 cases)** | **25.0%** |
| Precision on ESCALATE (on these 20 cases) | 4 of 5 = 0.8 |
| Recall on ESCALATE (on these 20 cases) | 4 of 5 = 0.8 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 4 | 708, 711, 714, 719 |
| False positives (run ESCALATE, key does not) | 1 | 702 |
| False negatives (key ESCALATE, run does not) | 1 | 716 |
| Over-escalations (= false positives) | 1 | 702 |
| Under-escalations (= false negatives) | 1 | 716 |
| Expected escalations in this set | 5 | 708, 711, 714, 716, 719 |
| Produced escalations in this set | 5 | 702, 708, 711, 714, 719 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 1 | 702 |
| Under-escalations (key ESCALATE, produced does not) | 1 | 716 |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 5 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 708, 711, 714, 716, 719 |
| ... the run escalated | 4 of 5 |
| **... the run ruled confidently instead** | **1 of 5** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

Cases ruled confidently where the record does not settle the question: 716.

## How this was checked

This report is of the development set `wild-v2`, whose own answer key is `eval/answers/wild-v2/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
