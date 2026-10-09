# Benchmark report — deepseek/deepseek-flash

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 15 |
| Rulings produced | 15 |
| **Four-field exact match** | **15/15 = 100.0%** |

| `ruling` | 15/15 = 100.0% |
| `amount_sgd` | 15/15 = 100.0% |
| `driver_compensation_sgd` | 15/15 = 100.0% |
| `referrals` | 15/15 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **15/15 = 100.0%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 101 | ok | ok | ok | ok | ok | current |
| 102 | ok | ok | ok | ok | ok | current |
| 103 | ok | ok | ok | ok | ok | current |
| 104 | ok | ok | ok | ok | ok | current |
| 105 | ok | ok | ok | ok | ok | current |
| 106 | ok | ok | ok | ok | ok | current |
| 107 | ok | ok | ok | ok | ok | current |
| 108 | ok | ok | ok | ok | ok | current |
| 109 | ok | ok | ok | ok | ok | current |
| 110 | ok | ok | ok | ok | ok | current |
| 111 | ok | ok | ok | ok | ok | current |
| 112 | ok | ok | ok | ok | ok | current |
| 113 | ok | ok | ok | ok | ok | current |
| 114 | ok | ok | ok | ok | ok | current |
| 115 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 58274 | 112052 | 67.5 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 102 | 67674 | 119556 | 125.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 103 | 83300 | 236613 | 262.6 | no | 1.00 | erp_lines.off_optimal_route_total.value | n/a | yes | yes | no | yes |
| 104 | 74231 | 208878 | 234.6 | no | 1.00 | closure[0].refund.payable.value | n/a | yes | yes | yes | yes |
| 105 | 70113 | 146417 | 161.8 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 106 | 66813 | 129934 | 112.3 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 107 | 68383 | 203962 | 215.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 108 | 83525 | 137848 | 209.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 109 | 71936 | 160027 | 178.3 | no | 1.00 | unverifiable: not structured | unverifiable: not structured | yes | yes | no | yes |
| 110 | 89428 | 158251 | 216.2 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 111 | 82169 | 160281 | 185.3 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 112 | 107525 | 253684 | 380.6 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 113 | 69354 | 114186 | 128.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 114 | 62727 | 118957 | 90.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 115 | 62160 | 129721 | 82.8 | no | 1.00 | erp_lines.lines[1].amount_sgd.value | n/a | yes | yes | no | yes |

## Failures

No case failed. Every graded field of every case agrees with the key.

## Referrals — expected against produced

### Case 105 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c): refer the case to driver-conduct review — a repeat deviation pattern (driver_profile.deviation_flags_90d = 4 on EV-DPROF-00105) is established alongside a material, substantiated deviation on this trip (EV-GPS-00105). The referral rides with the refund and does not displace or delay it."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 115 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: phantom AYE Alexandra Road gantry line of SGD 2.00 on EV-FARE-00115 that the trace never approaches"
- produced: "POL-RD-09(4) billing-integrity review: the AYE (Alexandra Rd towards Tuas) gantry line of SGD 2.00 on EV-FARE-00115 charged for a gantry the GPS trace (EV-GPS-00115) never crossed (closest approach 5,419 m), refunded in full as a standalone billing-integrity correction; the ledger entry should be reviewed and corrected."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 15 |
| Cases graded, by number | 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115 |
| Whole corpus graded | no — 15 of 29 cases |
| Expected escalations | 2 |
| Produced escalations | 2 |
| **Escalation rate (on these 15 cases)** | **13.3%** |
| Precision on ESCALATE (on these 15 cases) | 2 of 2 = 1.0 |
| Recall on ESCALATE (on these 15 cases) | 2 of 2 = 1.0 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 2 | 110, 112 |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
| Over-escalations (= false positives) | 0 | _none_ |
| Under-escalations (= false negatives) | 0 | _none_ |
| Expected escalations in this set | 2 | 110, 112 |
| Produced escalations in this set | 2 | 110, 112 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 0 | _none_ |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 2 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 110, 112 |
| ... the run escalated | 2 of 2 |
| **... the run ruled confidently instead** | **0 of 2** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

## How this was checked

`tests/test_grade.py` feeds each case's own `ground_truth` block back in as though a perfect judge had produced it and requires 29/29 on every field, five escalations, a rate of 17.2%, and precision and recall of 1.0. It then perturbs one field at a time — a ruling, an amount by 0.05, a `null` driver compensation replaced by 0, case 207's referral dropped, a referral added where the key expects none — and requires each perturbation to fail on its own field and on the four-field match, without disturbing the other fields' counts. No model is involved at any point.

## Precedents

Figures with precedents on are not comparable to the headline figure. The precedent library is built from closures made by people who have seen these development sets, so a case the library holds a closure for is material the system has been shown before.

No covered case is the source of a library entry, so every figure above is over the whole covered set. The incomparability stands all the same: the library was built by people who have seen this set.
