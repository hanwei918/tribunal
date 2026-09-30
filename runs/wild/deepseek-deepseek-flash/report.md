# Benchmark report — deepseek/deepseek-flash — development set wild

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/wild/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 62 |
| Rulings produced | 62 |
| **Four-field exact match** | **55/62 = 88.7%** |

| `ruling` | 56/62 = 90.3% |
| `amount_sgd` | 56/62 = 90.3% |
| `driver_compensation_sgd` | 62/62 = 100.0% |
| `referrals` | 60/62 = 96.8% |

Every graded case was produced by the brief and the prompts this code builds now, so the exact-match figure above is one measurement.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **56/62 = 90.3%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 501 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 502 | ok | ok | ok | ok | ok | current |
| 503 | ok | ok | ok | ok | ok | current |
| 504 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 505 | ok | ok | ok | ok | ok | current |
| 506 | ok | ok | ok | ok | ok | current |
| 507 | ok | ok | ok | ok | ok | current |
| 508 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 509 | ok | ok | ok | ok | ok | current |
| 510 | ok | ok | ok | ok | ok | current |
| 511 | ok | ok | ok | ok | ok | current |
| 512 | ok | ok | ok | ok | ok | current |
| 513 | ok | ok | ok | ok | ok | current |
| 514 | ok | ok | ok | ok | ok | current |
| 515 | ok | ok | ok | ok | ok | current |
| 516 | ok | ok | ok | ok | ok | current |
| 518 | ok | ok | ok | ok | ok | current |
| 519 | ok | ok | ok | ok | ok | current |
| 520 | ok | ok | ok | ok | ok | current |
| 521 | ok | ok | ok | ok | ok | current |
| 522 | ok | ok | ok | ok | ok | current |
| 523 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 524 | ok | ok | ok | ok | ok | current |
| 525 | ok | ok | ok | ok | ok | current |
| 526 | ok | ok | ok | ok | ok | current |
| 527 | ok | ok | ok | ok | ok | current |
| 528 | ok | ok | ok | ok | ok | current |
| 529 | ok | ok | ok | ok | ok | current |
| 530 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 531 | ok | ok | ok | ok | ok | current |
| 532 | ok | ok | ok | ok | ok | current |
| 534 | ok | ok | ok | ok | ok | current |
| 535 | ok | ok | ok | ok | ok | current |
| 536 | ok | ok | ok | ok | ok | current |
| 537 | ok | ok | ok | ok | ok | current |
| 601 | ok | ok | ok | ok | ok | current |
| 602 | ok | ok | ok | ok | ok | current |
| 603 | ok | ok | ok | ok | ok | current |
| 604 | ok | ok | ok | ok | ok | current |
| 605 | ok | ok | ok | ok | ok | current |
| 606 | ok | ok | ok | ok | ok | current |
| 607 | ok | ok | ok | ok | ok | current |
| 608 | ok | ok | ok | ok | ok | current |
| 609 | ok | ok | ok | ok | ok | current |
| 610 | ok | ok | ok | ok | ok | current |
| 611 | ok | ok | ok | ok | ok | current |
| 612 | ok | ok | ok | ok | ok | current |
| 613 | ok | ok | ok | ok | ok | current |
| 614 | ok | ok | ok | ok | ok | current |
| 615 | ok | ok | ok | ok | ok | current |
| 616 | ok | ok | ok | ok | ok | current |
| 617 | ok | ok | ok | ok | ok | current |
| 618 | ok | ok | ok | ok | ok | current |
| 619 | ok | ok | ok | ok | ok | current |
| 620 | ok | ok | ok | ok | ok | current |
| 621 | ok | ok | ok | ok | ok | current |
| 622 | ok | ok | ok | **FAIL** | **FAIL** | current |
| 623 | ok | ok | ok | ok | ok | current |
| 624 | ok | ok | ok | ok | ok | current |
| 625 | ok | ok | ok | ok | ok | current |
| 626 | ok | ok | ok | ok | ok | current |
| 627 | **FAIL** | **FAIL** | ok | **FAIL** | **FAIL** | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 501 | 70925 | 315186 | 1028.6 | yes | 0.25 | n/a | n/a | no | no | no | no |
| 502 | 60143 | 241640 | 798.5 | no | 0.75 | charged_total.value | n/a | yes | yes | yes | yes |
| 503 | 57058 | 101825 | 203.9 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 504 | 45540 | 260627 | 859.6 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 505 | 54084 | 306291 | 1003.7 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 506 | 59153 | 99461 | 271.6 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 507 | 62166 | 107393 | 257.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 508 | 58161 | 336994 | 1141.2 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 509 | 49438 | 99344 | 168.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 510 | 57964 | 106625 | 258.7 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 511 | 55575 | 116274 | 274.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 512 | 57692 | 188904 | 566.8 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 513 | 60163 | 111929 | 264.1 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 514 | 53862 | 119684 | 290.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 515 | 68888 | 141111 | 375.1 | no | 1.00 | charged_total.value | n/a | yes | yes | no | yes |
| 516 | 65346 | 122007 | 325.9 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 518 | 61763 | 177188 | 463.5 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 519 | 64532 | 113454 | 319.2 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 520 | 58742 | 216805 | 632.4 | no | 1.00 | unverifiable: not structured | unverifiable: not structured | yes | yes | no | yes |
| 521 | 53951 | 110467 | 269.6 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 522 | 56160 | 208760 | 713.5 | no | 0.75 | n/a | n/a | yes | yes | no | no |
| 523 | 61791 | 233093 | 797.6 | no | 0.75 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 524 | 51799 | 105171 | 251.8 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 525 | 65603 | 120122 | 299.6 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 526 | 61511 | 141707 | 428.3 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 527 | 66685 | 101246 | 254.3 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 528 | 77695 | 117780 | 398.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 529 | 64017 | 125596 | 374.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 530 | 58267 | 207391 | 929.2 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 531 | 52055 | 153401 | 475.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 532 | 58643 | 116641 | 306.4 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 534 | 52691 | 106469 | 214.9 | no | 1.00 | refund.refund_before_rounding.value | n/a | yes | yes | yes | yes |
| 535 | 72275 | 103415 | 285.3 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 536 | 59040 | 291751 | 958.5 | no | 0.75 | n/a | n/a | yes | yes | no | yes |
| 537 | 60770 | 104068 | 261.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 601 | 60647 | 94728 | 221.1 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 602 | 59503 | 104177 | 254.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 603 | 54760 | 96158 | 202.8 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 604 | 67423 | 117689 | 323.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 605 | 66968 | 111108 | 279.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 606 | 60914 | 105230 | 244.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 607 | 59047 | 111366 | 287.4 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 608 | 55750 | 96822 | 214.3 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 609 | 53945 | 99303 | 215.4 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 610 | 45951 | 92728 | 161.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 611 | 59468 | 100978 | 234.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 612 | 71954 | 117028 | 353.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 613 | 74536 | 102565 | 303.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 614 | 67757 | 99875 | 279.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 615 | 65549 | 98622 | 256.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 616 | 65785 | 186823 | 597.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 617 | 59379 | 92866 | 220.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 618 | 63685 | 103202 | 273.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 619 | 70094 | 194807 | 658.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 620 | 58406 | 108799 | 263.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 621 | 71400 | 123182 | 363.7 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 622 | 60746 | 156361 | 486.1 | yes | 1.00 | n/a | n/a | no | yes | no | no |
| 623 | 59076 | 126163 | 316.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 624 | 57086 | 115464 | 280.9 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 625 | 68228 | 108086 | 297.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 626 | 52551 | 136670 | 380.5 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 627 | 60452 | 147929 | 386.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |

## Failures

### Case 501

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 14.5, produced null

### Case 504

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 17.6, produced null

### Case 508

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 6.0, produced null

### Case 523

Failed on: ruling, amount_sgd

- **ruling** — expected 'NO_ACTION', produced 'FULL_REFUND'
- **amount_sgd** — expected null, produced 4.0

### Case 530

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 5.8, produced null

### Case 622

Failed on: referrals

- **referrals** — a referral was produced where the key expects none: POL-NS-07

### Case 627

Failed on: ruling, amount_sgd, referrals

- **ruling** — expected 'ESCALATE', produced 'FULL_REFUND'
- **amount_sgd** — expected null, produced 6.0
- **referrals** — a referral was produced where the key expects none: POL-NS-05(ii)

## Referrals — expected against produced

### Case 502 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) — refer driver DRV-20334 to driver-conduct review: POL-RD-01 records a MATERIAL deviation on TRP-00502 and POL-RD-06 establishes a repeat-deviation pattern (driver_profile.deviation_flags_90d 4 against 210 completed trips in 90 days)."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-01, POL-RD-06, POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: POL-RD-01, POL-RD-06
- additional clause(s) offered: POL-RD-01, POL-RD-06

### Case 515 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c): refer the driver to driver-conduct review — a MATERIAL, substantiated deviation on trip TRP-00515 combined with an established repeat-deviation pattern (driver_profile.deviation_flags_90d = 3) requires conduct review, and this referral rides with the monetary ruling without delaying it."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 516 — clause match

- expected: "POL-RD-09(4) billing integrity"
- produced: "POL-RD-09(4) — billing-integrity finding: the SGD 3.00 ERP line for the 'AYE (Alexandra Rd towards City)' gantry has no trace crossing within POL-RD-09's 250 m match radius (the gantry carries coordinates; the nearest fix is 2,608.77 m away) and has been refunded to the rider in full as a standalone correction; refer for billing-integrity review of this gantry charge."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09, POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: POL-RD-09
- additional clause(s) offered: POL-RD-09

### Case 521 — clause match

- expected: "POL-RD-09(4) billing integrity"
- produced: "POL-RD-09(4) billing integrity: the fare breakdown charges SGD 2.00 for the "CTE (Braddell Rd towards City)" gantry at 1.342, 103.86, but the GPS trace (100% coverage, 73 fixes at a 10 s cadence, no gaps) never comes within 6,778 m of that gantry, so the line is a phantom charge; refunded in full as a standalone correction and referred for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 532 — clause match

- expected: "POL-RD-09(4) billing integrity"
- produced: "POL-RD-09(4): billing-integrity finding — the SGD 6.00 ERP line for the CTE (Ang Mo Kio Ave 1 towards City) gantry on EV-FARE-00532 was charged although the trip's GPS trace (EV-GPS-00532) never came within the 250 m match radius of that gantry (closest fix 1,159.02 m); the line is refunded in full as a standalone pass-through correction and is referred for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 606 — clause match

- expected: "POL-NS-05(ii) false-arrival record"
- produced: "POL-NS-05(ii) — record a false-arrival event against driver DRV-30640 for trip TRP-00606 (arrival marker set at 23:15:20 while the driver was 448.97 m from the pin and moving at 23.3–39.0 km/h, and no qualifying in-geofence fix exists anywhere in the trip)."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 612 — clause match

- expected: "POL-NS-05(ii) false-arrival record"
- produced: "POL-NS-05(ii): record TRP-00612 as a false-arrival event against driver DRV-31205 — the 'arrived at pickup' marker timestamped 2026-09-12T08:34:52 was set while the driver's nearest GPS fix (EV-GPS-00612) was 350.79 m from the pickup pin, beyond the 300 m threshold, and no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 614 — clause match

- expected: "POL-NS-05(ii) false-arrival record"
- produced: "POL-NS-05(ii): record TRP-00614 as a false-arrival event against driver DRV-31422, the 'arrived' marker at 16:14:40 having been struck while no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 616 — clause match

- expected: "POL-NS-05(ii) false-arrival record"
- produced: "POL-NS-05(ii): record a false-arrival event against driver DRV-31649 for trip TRP-00616 — the driver's 'arrived' marker at 2026-09-16T11:33:52+08:00 was set while the GPS trace places him no closer than 358.15 m from the pickup pin (more than the 300 m threshold), and the trace contains no qualifying in-geofence fix anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 622 — **no clause match**

- expected: _(none)_
- produced: "POL-NS-07: direct the human reviewer to refund the rider's cancellation fee of SGD 4.00 in full."
- clause keys, expected: _(none)_
- clause keys, produced: POL-NS-07
- expected clauses matched: 0 of 0
- additional clauses offered: POL-NS-07
- additional clause(s) offered: POL-NS-07
- a referral was produced where the key expects none: POL-NS-07

### Case 625 — clause match

- expected: "POL-NS-05(ii) false-arrival record"
- produced: "POL-NS-05(ii) false-arrival record: record a false-arrival event against driver DRV-32539 on trip TRP-00625 — the 'arrived' marker at 2026-09-25T18:04:00+08:00 places the driver 377.4 m from the pickup pin while travelling above 40 km/h, and no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 627 — **no clause match**

- expected: _(none)_
- produced: "POL-NS-05(ii): record trip TRP-00627 as a false-arrival event against driver DRV-32752 — the 'arrived' marker at 2026-09-27T23:15:10+08:00 was set while the GPS trace places the vehicle 623.57 m or more from the pin and moving at 28.1-30.6 km/h, and no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: _(none)_
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 0 of 0
- additional clauses offered: POL-NS-05(ii)
- additional clause(s) offered: POL-NS-05(ii)
- a referral was produced where the key expects none: POL-NS-05(ii)

## Escalation calibration

| | |
|---|---|
| Cases graded | 62 |
| Cases graded, by number | 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 518, 519, 520, 521, 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532, 534, 535, 536, 537, 601, 602, 603, 604, 605, 606, 607, 608, 609, 610, 611, 612, 613, 614, 615, 616, 617, 618, 619, 620, 621, 622, 623, 624, 625, 626, 627 |
| Whole corpus graded | no — 62 of 64 cases |
| Expected escalations | 4 |
| Produced escalations | 7 |
| **Escalation rate (on these 62 cases)** | **11.3%** |
| Precision on ESCALATE (on these 62 cases) | 3 of 7 = 0.429 |
| Recall on ESCALATE (on these 62 cases) | 3 of 4 = 0.75 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 3 | 512, 622, 626 |
| False positives (run ESCALATE, key does not) | 4 | 501, 504, 508, 530 |
| False negatives (key ESCALATE, run does not) | 1 | 627 |
| Over-escalations (= false positives) | 4 | 501, 504, 508, 530 |
| Under-escalations (= false negatives) | 1 | 627 |
| Expected escalations in this set | 4 | 512, 622, 626, 627 |
| Produced escalations in this set | 7 | 501, 504, 508, 512, 530, 622, 626 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 4 | 501, 504, 508, 530 |
| Under-escalations (key ESCALATE, produced does not) | 1 | 627 |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 4 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 512, 622, 626, 627 |
| ... the run escalated | 3 of 4 |
| **... the run ruled confidently instead** | **1 of 4** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

Cases ruled confidently where the record does not settle the question: 627.

## How this was checked

This report is of the development set `wild`, whose own answer key is `eval/answers/wild/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
