# Benchmark report — deepseek/deepseek-flash — ablation clause-notes

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 29 |
| Rulings produced | 29 |
| **Four-field exact match** | **27/29 = 93.1%** |

| `ruling` | 27/29 = 93.1% |
| `amount_sgd` | 27/29 = 93.1% |
| `driver_compensation_sgd` | 28/29 = 96.6% |
| `referrals` | 29/29 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **27/29 = 93.1%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 101 | ok | ok | ok | ok | ok | current |
| 102 | ok | ok | ok | ok | ok | current |
| 103 | ok | ok | ok | ok | ok | current |
| 104 | ok | ok | ok | ok | ok | current |
| 105 | ok | ok | ok | ok | ok | current |
| 106 | ok | ok | ok | ok | ok | current |
| 107 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 108 | ok | ok | ok | ok | ok | current |
| 109 | ok | ok | ok | ok | ok | current |
| 110 | ok | ok | ok | ok | ok | current |
| 111 | ok | ok | ok | ok | ok | current |
| 112 | ok | ok | ok | ok | ok | current |
| 113 | ok | ok | ok | ok | ok | current |
| 114 | ok | ok | ok | ok | ok | current |
| 115 | ok | ok | ok | ok | ok | current |
| 201 | ok | ok | ok | ok | ok | current |
| 202 | ok | ok | ok | ok | ok | current |
| 203 | ok | ok | ok | ok | ok | current |
| 204 | ok | ok | ok | ok | ok | current |
| 205 | ok | ok | ok | ok | ok | current |
| 206 | ok | ok | ok | ok | ok | current |
| 207 | ok | ok | ok | ok | ok | current |
| 208 | ok | ok | ok | ok | ok | current |
| 209 | ok | ok | ok | ok | ok | current |
| 210 | ok | ok | ok | ok | ok | current |
| 211 | **FAIL** | **FAIL** | **FAIL** | ok | **FAIL** | current |
| 212 | ok | ok | ok | ok | ok | current |
| 213 | ok | ok | ok | ok | ok | current |
| 214 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 48655 | 88477 | 155.4 | no | 1.00 | refund.payable.value | n/a | no | yes | no | no |
| 102 | 55968 | 119766 | 333.4 | no | 0.75 | n/a | n/a | yes | yes | no | yes |
| 103 | 59194 | 132125 | 292.8 | no | 1.00 | erp_lines.off_optimal_route_total.value | n/a | no | yes | no | no |
| 104 | 71937 | 165340 | 510.3 | no | 1.00 | closure[0].refund.payable.value | n/a | yes | yes | yes | yes |
| 105 | 50691 | 189390 | 556.3 | no | 0.75 | charged_total.value | n/a | yes | yes | yes | yes |
| 106 | 53060 | 107228 | 210.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 107 | 61828 | 241331 | 798.2 | yes | 0.50 | n/a | n/a | no | yes | no | no |
| 108 | 67819 | 111348 | 313.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 109 | 58321 | 142646 | 387.4 | no | 1.00 | unverifiable: not structured | unverifiable: not structured | yes | yes | no | yes |
| 110 | 61448 | 141662 | 379.8 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 111 | 63541 | 251834 | 786.4 | no | 1.00 | n/a | n/a | no | yes | yes | no |
| 112 | 79874 | 211886 | 726.2 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 113 | 64547 | 96244 | 254.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 114 | 55311 | 268404 | 776.1 | no | 1.00 | refund.payable.value | n/a | no | yes | yes | yes |
| 115 | 47020 | 113717 | 241.4 | no | 1.00 | erp_lines.lines[1].amount_sgd.value | n/a | yes | yes | no | yes |
| 201 | 53379 | 101752 | 253.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 202 | 59319 | 134577 | 397.8 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 203 | 61125 | 85362 | 220.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 204 | 63968 | 94361 | 264.2 | no | 0.75 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 205 | 69900 | 145686 | 490.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 206 | 64136 | 144226 | 451.6 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 207 | 47988 | 89864 | 187.4 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 208 | 67580 | 100864 | 292.5 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 209 | 67219 | 114065 | 348.6 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 210 | 57507 | 134962 | 347.3 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 211 | 72904 | 510844 | 1691.2 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | yes | yes |
| 212 | 64153 | 173487 | 587.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 213 | 47718 | 113046 | 303.5 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 214 | 61278 | 112521 | 313.8 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |

## Failures

### Case 107

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 7.45, produced null

### Case 211

Failed on: ruling, amount_sgd, driver_compensation_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'DRIVER_COMPENSATION'
- **amount_sgd** — expected 2.0, produced 3.20
- **driver_compensation_sgd** — expected null, produced 3.20

## Referrals — expected against produced

### Case 105 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review: refer driver DRV-00932 to conduct review. A repeat-deviation pattern is established on EV-DPROF-00105 (weight 0.75, issue code STALE_SNAPSHOT; deviation_flags_90d 4 against the clause's threshold of 3) alongside a MATERIAL deviation substantiated on this trip's own evidence (EV-GPS-00105, EV-TRIP-00105). Per POL-GEN-03 this referral does not displace or delay the monetary ruling."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-GEN-03, POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: POL-GEN-03
- additional clause(s) offered: POL-GEN-03

### Case 115 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: phantom AYE Alexandra Road gantry line of SGD 2.00 on EV-FARE-00115 that the trace never approaches"
- produced: "POL-RD-09(4) billing integrity: the SGD 2.00 AYE (Alexandra Rd towards Tuas) gantry line was charged although the GPS trace never came within 250 m of that gantry (nearest fix 5,419 m at 21:10:00). Refund it in full as a standalone pass-through correction and record this billing-integrity finding."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 201 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii): record trip TRP-00201 as a false-arrival event against driver DRV-01590, no qualifying in-geofence fix existing anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 207 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.00 cancellation fee in full"
- produced: "POL-NS-07: direct the human reviewer to refund the rider's cancellation fee of SGD 4.00 in full; the disputed fee remains held rather than collected or refunded by the automated pipeline while review is pending."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

## Escalation calibration

| | |
|---|---|
| Cases graded | 29 |
| Cases graded, by number | 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214 |
| Whole corpus graded | yes — all 29 cases |
| Expected escalations | 5 |
| Produced escalations | 6 |
| **Escalation rate** | **20.7%** |
| Target | 17.2% |
| Off target | yes |
| Precision on ESCALATE | 5 of 6 = 0.833 |
| Recall on ESCALATE | 5 of 5 = 1.0 |

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 1 | 107 |
| Under-escalations (key ESCALATE, produced does not) | 0 | _none_ |

### The INDETERMINATE cases, kept out of the rate

The key escalates 4 cases whose record genuinely does not settle the question, and 1 case on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 110, 112, 210, 213 |
| ... the run escalated | 4 of 4 |
| **... the run ruled confidently instead** | **0 of 4** |
| Substantive escalations the key makes | 207 |
| ... the run escalated | 1 of 1 |

## How this was checked

`tests/test_grade.py` feeds each case's own `ground_truth` block back in as though a perfect judge had produced it and requires 29/29 on every field, five escalations, a rate of 17.2%, and precision and recall of 1.0. It then perturbs one field at a time — a ruling, an amount by 0.05, a `null` driver compensation replaced by 0, case 207's referral dropped, a referral added where the key expects none — and requires each perturbation to fail on its own field and on the four-field match, without disturbing the other fields' counts. No model is involved at any point.

## Ablation

clause-notes

every clause's drafting `notes` has been removed from the brief's policies. The clause ids, the `rule` text and the structured fields are unchanged, so a limb still reads as it read; what is gone is the commentary around it.
