# Benchmark report — deepseek/deepseek-flash — development set codex

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/codex/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 5 |
| Rulings produced | 5 |
| **Four-field exact match** | **4/5 = 80.0%** |

| `ruling` | 5/5 = 100.0% |
| `amount_sgd` | 4/5 = 80.0% |
| `driver_compensation_sgd` | 5/5 = 100.0% |
| `referrals` | 4/5 = 80.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **4/5 = 80.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 9111 | ok | **FAIL** | ok | **FAIL** | **FAIL** | current |
| 9112 | ok | ok | ok | ok | ok | current |
| 9113 | ok | ok | ok | ok | ok | current |
| 9114 | ok | ok | ok | ok | ok | current |
| 9115 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 9111 | 47278 | 208863 | 565.2 | no | 0.75 | refund.payable.value | n/a | yes | yes | yes | yes |
| 9112 | 55503 | 95798 | 173.0 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 9113 | 73135 | 365241 | 1195.3 | no | 0.75 | erp_lines.lines[0].amount_sgd.value + closure[0].refund.payable.value | n/a | yes | yes | yes | yes |
| 9114 | 59328 | 115044 | 245.5 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | no |
| 9115 | 57890 | 148521 | 353.4 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |

## Failures

### Case 9111

Failed on: amount_sgd, referrals

- **amount_sgd** — expected 10.15, produced 9.15
- **referrals** — expected referral not produced: POL-RD-09(4)

## Referrals — expected against produced

### Case 9111 — **no clause match**

- expected: "POL-RD-09(4) billing-integrity referral: phantom ERP gantry lines on EV-FARE-09111, Pioneer Road inbound SGD 1.00 and Tuas South Avenue 8 loop SGD 2.00, neither within 250 m of any GPS fix"
- produced: _(none)_
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: _(none)_
- expected clauses matched: 0 of 1
- additional clauses offered: _(none)_
- expected referral not produced: POL-RD-09(4)

### Case 9113 — clause match

- expected: "POL-RD-09(4) billing-integrity referral: phantom ERP gantry line on EV-FARE-09113, Pelton lawful diversion entry SGD 1.00, not within 250 m of any GPS fix"
- produced: "POL-RD-09(4) billing integrity: the SGD 1.00 'Pelton lawful diversion entry' ERP line charges a gantry this trip's gps_trace never passes (nearest of the 205 fixes is 834.18 m from the gantry, outside POL-RD-09(4)'s 250 m match radius); the line has been refunded in full as a standalone pass-through correction and is referred for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4), POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 9114 — clause match

- expected: "POL-RD-09(4) billing-integrity referral for a phantom ERP gantry line"
- produced: "POL-RD-09(4): billing-integrity review — the fare_breakdown (EV-FARE-09114) charged SGD 3.20 for the 'Bukit Merah Central westbound' ERP gantry, which the GPS trace (EV-GPS-09114) never crossed (closest fix 7,482.07 m away, on_optimal_route false); the line was refunded in full as a standalone pass-through correction."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 5 |
| Cases graded, by number | 9111, 9112, 9113, 9114, 9115 |
| Whole corpus graded | no — 5 of 15 cases |
| Expected escalations | 1 |
| Produced escalations | 1 |
| **Escalation rate (on these 5 cases)** | **20.0%** |
| Precision on ESCALATE (on these 5 cases) | 1 of 1 = 1.0 |
| Recall on ESCALATE (on these 5 cases) | 1 of 1 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 1 | 9115 |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 0 | _none_ |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 1 | 9115 |
| Produced escalations in this set | 1 | 9115 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 1 case whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 9115 |
| ... the run escalated | 1 of 1 |
| **... the run ruled confidently instead** | **0 of 1** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

## How this was checked

This report is of the development set `codex`, whose own answer key is `eval/answers/codex/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
