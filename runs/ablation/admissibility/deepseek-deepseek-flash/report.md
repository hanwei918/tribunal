# Benchmark report — deepseek/deepseek-flash — ablation admissibility

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 29 |
| Rulings produced | 29 |
| **Four-field exact match** | **26/29 = 89.7%** |

| `ruling` | 26/29 = 89.7% |
| `amount_sgd` | 26/29 = 89.7% |
| `driver_compensation_sgd` | 28/29 = 96.6% |
| `referrals` | 29/29 = 100.0% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **26/29 = 89.7%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

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
| 112 | **FAIL** | **FAIL** | **FAIL** | ok | **FAIL** | current |
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
| 211 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 212 | ok | ok | ok | ok | ok | current |
| 213 | ok | ok | ok | ok | ok | current |
| 214 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 46599 | 94069 | 155.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 102 | 54306 | 144097 | 401.8 | no | 0.75 | n/a | n/a | yes | yes | no | yes |
| 103 | 68727 | 118196 | 280.6 | no | 1.00 | erp_lines.off_optimal_route_total.value | n/a | yes | yes | yes | yes |
| 104 | 69986 | 147402 | 414.2 | no | 1.00 | closure[0].refund.payable.value | n/a | no | yes | yes | yes |
| 105 | 67024 | 184979 | 603.3 | no | 1.00 | charged_total.value | n/a | yes | yes | no | yes |
| 106 | 51918 | 101959 | 176.9 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 107 | 61491 | 242791 | 852.4 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 108 | 66980 | 107343 | 290.6 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 109 | 65056 | 194359 | 631.7 | no | 0.75 | unverifiable: not structured | unverifiable: not structured | yes | yes | no | yes |
| 110 | 66370 | 179613 | 564.3 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 111 | 59959 | 131166 | 369.8 | no | 1.00 | n/a | n/a | no | yes | yes | yes |
| 112 | 77064 | 195933 | 707.7 | no | 1.00 | unverifiable: not structured | unverifiable: not structured | yes | yes | yes | no |
| 113 | 57446 | 96731 | 225.3 | no | 1.00 | n/a | n/a | no | yes | no | no |
| 114 | 52701 | 220978 | 655.2 | no | 0.75 | refund.payable.value | n/a | yes | yes | yes | yes |
| 115 | 68597 | 113992 | 293.7 | no | 1.00 | erp_lines.lines[1].amount_sgd.value | n/a | yes | yes | yes | yes |
| 201 | 56190 | 104491 | 261.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 202 | 82429 | 106593 | 358.5 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 203 | 59065 | 99606 | 246.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 204 | 74699 | 111871 | 342.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 205 | 63205 | 128607 | 366.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 206 | 66491 | 186911 | 525.2 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 207 | 63574 | 133994 | 315.7 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 208 | 70393 | 126791 | 376.3 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | yes | yes |
| 209 | 88102 | 128650 | 469.8 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 210 | 71406 | 208415 | 712.7 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 211 | 66739 | 243645 | 778.2 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 212 | 75044 | 170149 | 595.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 213 | 52961 | 144342 | 433.5 | yes | 0.75 | n/a | n/a | yes | yes | yes | yes |
| 214 | 69455 | 133813 | 393.9 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |

## Failures

### Case 107

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 7.45, produced null

### Case 112

Failed on: ruling, amount_sgd, driver_compensation_sgd

- **ruling** — expected 'ESCALATE', produced 'DRIVER_COMPENSATION'
- **amount_sgd** — expected null, produced 1.8
- **driver_compensation_sgd** — expected null, produced 1.8

### Case 211

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 2.0, produced null

## Referrals — expected against produced

### Case 105 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c): refer driver DRV-00932 to driver-conduct review — the POL-RD-06 repeat-deviation pattern is established on EV-DPROF-00105 (deviation_flags_90d = 4, at or above the '3 or more' threshold, against completed_trips_90d = 344) and this trip's deviation is both MATERIAL and substantiated."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06, POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: POL-RD-06
- additional clause(s) offered: POL-RD-06

### Case 115 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: phantom AYE Alexandra Road gantry line of SGD 2.00 on EV-FARE-00115 that the trace never approaches"
- produced: "POL-RD-09(4) billing integrity: refund in full the SGD 2.00 'AYE (Alexandra Rd towards Tuas)' ERP line on EV-FARE-00115 — the GPS trace EV-GPS-00115 never comes within 250 m of that gantry (nearest fix 5,419.29 m, on no optimal-route corridor) — and review the phantom gantry line as a platform billing defect."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 201 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii): record trip TRP-00201 as a false-arrival event against driver DRV-01590 in the false-arrival record"
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 207 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.00 cancellation fee in full"
- produced: "POL-NS-07: the escalation packet must direct the human reviewer to refund the rider's cancellation fee of SGD 4.00 in full; the disputed fee is held on the ledger rather than collected or refunded while that review is pending."
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
| Precision on ESCALATE | 4 of 6 = 0.667 |
| Recall on ESCALATE | 4 of 5 = 0.8 |

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 2 | 107, 211 |
| Under-escalations (key ESCALATE, produced does not) | 1 | 112 |

### The INDETERMINATE cases, kept out of the rate

The key escalates 4 cases whose record genuinely does not settle the question, and 1 case on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 110, 112, 210, 213 |
| ... the run escalated | 3 of 4 |
| **... the run ruled confidently instead** | **1 of 4** |
| Substantive escalations the key makes | 207 |
| ... the run escalated | 1 of 1 |

Cases ruled confidently where the record does not settle the question: 112.

## How this was checked

`tests/test_grade.py` feeds each case's own `ground_truth` block back in as though a perfect judge had produced it and requires 29/29 on every field, five escalations, a rate of 17.2%, and precision and recall of 1.0. It then perturbs one field at a time — a ruling, an amount by 0.05, a `null` driver compensation replaced by 0, case 207's referral dropped, a referral added where the key expects none — and requires each perturbation to fail on its own field and on the four-field match, without disturbing the other fields' counts. No model is involved at any point.

## Ablation

admissibility

the `admissibility` object has been removed from every artifact in the brief. The referee reads an artifact with no admissibility object as one with no impairment, so no claim is discarded for citing an impaired artifact at a weight below 1. A MISSING artifact keeps its `evidence_id` and its null payload, and derived text computed from a null payload still says MISSING -- so the ablated brief carries no admissibility OBJECT, which is not the same as carrying no admissibility information.
