# The amount read-off rule, measured on the recorded drafts

Model: deepseek/deepseek-flash. **No model call was made.** Every figure below is computed from the judge drafts three runs already recorded: their transcripts hold the drafts and the vote each was counted in, and the two rules are two reductions of those same drafts.

`published` is the rule every run so far was judged by: an amount is a figure the brief's money block publishes, or the **sum** of two or three of them. `signed` is the same rule with a sign on every term after the first: a difference of two or three published figures, leading term positive, result above zero. **The default is unchanged.** This file measures; it adopts nothing.

`published` is the reading re-derived from the recorded drafts, and it is reported beside the ruling the run itself published: where the two disagree the panel is not the one the run counted, and the difference between the rules would be a difference between two reconstructions rather than the effect of the rule.

Both development sets are development data, and neither is a test set. The corpus figure is the figure the submission reports; the combined figure is a sum over two sets that were drafted differently and share one template, so it is not a generalisation figure and does not replace the corpus number. The generalisation figures the submission reports belong to the two sealed sets, each run exactly once: the held-out set's, drafted without access to this repository, from the commit tagged freeze-2026-09-30; and the second sealed set's, prepared by OpenAI Codex -- whether Codex could read this repository while preparing it is not recorded -- from a commit whose tribunal/, prompts/ and policy/ trees equal those at freeze-2026-10-03. Neither figure here is either of them, and the two are never added to each other either.

The held-out set is one of the three runs measured here and is not a development set. It is read, never written: nothing in this measurement goes near a run directory.

## corpus — runs/deepseek-deepseek-flash

Read over 29 of the 29 cases in the set; 0 refused. The run directory's own last recorded commit is b25b74333dc6 -- per-case provenance is the commit each case's advocates were made under, and a directory several invocations have written to names the last of them here.

| case | published | signed | key | movement |
|---|---|---|---|---|
| 101 | PARTIAL_REFUND 8.05 | PARTIAL_REFUND 8.05 | PARTIAL_REFUND 8.05 | matching both ways |
| 102 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 103 | PARTIAL_REFUND 4.00 | PARTIAL_REFUND 4.00 | PARTIAL_REFUND 4.0 | matching both ways |
| 104 | PARTIAL_REFUND 3.60 | PARTIAL_REFUND 3.60 | PARTIAL_REFUND 3.6 | matching both ways |
| 105 | FULL_REFUND 65.13 | FULL_REFUND 65.13 | FULL_REFUND 65.13 | matching both ways |
| 106 | PARTIAL_REFUND 10.75 | PARTIAL_REFUND 10.75 | PARTIAL_REFUND 10.75 | matching both ways |
| 107 | PARTIAL_REFUND 7.45 | PARTIAL_REFUND 7.45 | PARTIAL_REFUND 7.45 | matching both ways |
| 108 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 109 | DRIVER_COMPENSATION 3.15 | DRIVER_COMPENSATION 3.15 | DRIVER_COMPENSATION 3.15 | matching both ways |
| 110 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 111 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 112 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 113 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 114 | PARTIAL_REFUND 13.70 | PARTIAL_REFUND 13.70 | PARTIAL_REFUND 13.7 | matching both ways |
| 115 | PARTIAL_REFUND 2.00 | PARTIAL_REFUND 2.00 | PARTIAL_REFUND 2.0 | matching both ways |
| 201 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 202 | DRIVER_COMPENSATION 4.80 | DRIVER_COMPENSATION 4.80 | DRIVER_COMPENSATION 4.8 | matching both ways |
| 203 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 204 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 205 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 206 | FULL_REFUND 4.00 | FULL_REFUND 4.00 | FULL_REFUND 4.0 | matching both ways |
| 207 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 208 | DRIVER_COMPENSATION 6.4 | DRIVER_COMPENSATION 6.4 | DRIVER_COMPENSATION 6.4 | matching both ways |
| 209 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 210 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 211 | PARTIAL_REFUND 2.0 | PARTIAL_REFUND 2.0 | PARTIAL_REFUND 2.0 | matching both ways |
| 212 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 213 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 214 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | matching both ways |

The published reading reproduces the ruling this run published for every case above, so the two rules are being compared on the run's own panel.

## codex — runs/codex/deepseek-deepseek-flash

Read over 15 of the 15 cases in the set; 0 refused. The run directory's own last recorded commit is b25b74333dc6 -- per-case provenance is the commit each case's advocates were made under, and a directory several invocations have written to names the last of them here.

| case | published | signed | key | movement |
|---|---|---|---|---|
| 9101 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | matching both ways |
| 9102 | DRIVER_COMPENSATION 4.8 | DRIVER_COMPENSATION 4.8 | DRIVER_COMPENSATION 4.8 | matching both ways |
| 9103 | FULL_REFUND 8.0 | FULL_REFUND 8.0 | FULL_REFUND 8.0 | matching both ways |
| 9104 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 9105 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 9106 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | matching both ways |
| 9107 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | matching both ways |
| 9108 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 9109 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 9110 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 9111 | PARTIAL_REFUND 9.15 | PARTIAL_REFUND 9.15 | PARTIAL_REFUND 10.15 | missing both ways |
| 9112 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 9113 | PARTIAL_REFUND 9.05 | PARTIAL_REFUND 9.05 | PARTIAL_REFUND 9.05 | matching both ways |
| 9114 | FULL_REFUND 3.2 | FULL_REFUND 3.2 | FULL_REFUND 3.2 | matching both ways |
| 9115 | ESCALATE | ESCALATE | ESCALATE | matching both ways |

The published reading reproduces the ruling this run published for every case above, so the two rules are being compared on the run's own panel.

## wild — runs/wild/deepseek-deepseek-flash

Read over 64 of the 64 cases in the set; 0 refused. The run directory's own last recorded commit is d275ef82f518 -- per-case provenance is the commit each case's advocates were made under, and a directory several invocations have written to names the last of them here.

The run published no ruling for 517 and 533, so they are read from the transcript alone: there is no cached result to carry the brief digest, and the digest the transcript's own advocate entries record is used instead.

| case | published | signed | key | movement |
|---|---|---|---|---|
| 501 | ESCALATE | PARTIAL_REFUND 8.5 | PARTIAL_REFUND 14.5 | missing both ways |
| 502 | FULL_REFUND 17.92 | FULL_REFUND 17.92 | FULL_REFUND 17.92 | matching both ways |
| 503 | PARTIAL_REFUND 8.00 | PARTIAL_REFUND 8.00 | PARTIAL_REFUND 8.0 | matching both ways |
| 504 | ESCALATE | ESCALATE | PARTIAL_REFUND 17.6 | missing both ways |
| 505 | PARTIAL_REFUND 9.15 | PARTIAL_REFUND 9.15 | PARTIAL_REFUND 9.15 | matching both ways |
| 506 | PARTIAL_REFUND 10.20 | PARTIAL_REFUND 10.20 | PARTIAL_REFUND 10.2 | matching both ways |
| 507 | PARTIAL_REFUND 9.8 | PARTIAL_REFUND 9.8 | PARTIAL_REFUND 9.8 | matching both ways |
| 508 | ESCALATE | ESCALATE | PARTIAL_REFUND 6.0 | missing both ways |
| 509 | PARTIAL_REFUND 10.7 | PARTIAL_REFUND 10.7 | PARTIAL_REFUND 10.7 | matching both ways |
| 510 | PARTIAL_REFUND 10.0 | PARTIAL_REFUND 10.0 | PARTIAL_REFUND 10.0 | matching both ways |
| 511 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 512 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 513 | PARTIAL_REFUND 13.20 | PARTIAL_REFUND 13.20 | PARTIAL_REFUND 13.2 | matching both ways |
| 514 | PARTIAL_REFUND 8.70 | PARTIAL_REFUND 8.70 | PARTIAL_REFUND 8.7 | matching both ways |
| 515 | FULL_REFUND 62.28 | FULL_REFUND 62.28 | FULL_REFUND 62.28 | matching both ways |
| 516 | PARTIAL_REFUND 3.0 | PARTIAL_REFUND 3.0 | PARTIAL_REFUND 3.0 | matching both ways |
| 517 | no ruling | no ruling | PARTIAL_REFUND 33.5 | missing both ways |
| 518 | PARTIAL_REFUND 3.95 | PARTIAL_REFUND 3.95 | PARTIAL_REFUND 3.95 | matching both ways |
| 519 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 520 | DRIVER_COMPENSATION 1.9 | DRIVER_COMPENSATION 1.9 | DRIVER_COMPENSATION 1.9 | matching both ways |
| 521 | FULL_REFUND 2.0 | FULL_REFUND 2.0 | FULL_REFUND 2.0 | matching both ways |
| 522 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 523 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | NO_ACTION | missing both ways |
| 524 | PARTIAL_REFUND 3.2 | PARTIAL_REFUND 3.2 | PARTIAL_REFUND 3.2 | matching both ways |
| 525 | PARTIAL_REFUND 4.5 | PARTIAL_REFUND 4.5 | PARTIAL_REFUND 4.5 | matching both ways |
| 526 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 527 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 528 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 529 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 530 | ESCALATE | ESCALATE | PARTIAL_REFUND 5.8 | missing both ways |
| 531 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 532 | PARTIAL_REFUND 6.0 | PARTIAL_REFUND 6.0 | PARTIAL_REFUND 6.0 | matching both ways |
| 533 | no ruling | PARTIAL_REFUND 19.3 | PARTIAL_REFUND 19.3 | missing -> matching |
| 534 | PARTIAL_REFUND 5.95 | PARTIAL_REFUND 5.95 | PARTIAL_REFUND 5.95 | matching both ways |
| 535 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 536 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 537 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 601 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 602 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 603 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 604 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 605 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 606 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | matching both ways |
| 607 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 608 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 609 | FULL_REFUND 8.0 | FULL_REFUND 8.0 | FULL_REFUND 8.0 | matching both ways |
| 610 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 611 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 612 | FULL_REFUND 4.00 | FULL_REFUND 4.00 | FULL_REFUND 4.0 | matching both ways |
| 613 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 614 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | matching both ways |
| 615 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | matching both ways |
| 616 | FULL_REFUND 8.0 | FULL_REFUND 8.0 | FULL_REFUND 8.0 | matching both ways |
| 617 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 618 | NO_ACTION | NO_ACTION | NO_ACTION | matching both ways |
| 619 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 620 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 621 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | matching both ways |
| 622 | ESCALATE | ESCALATE | ESCALATE | missing both ways |
| 623 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | matching both ways |
| 624 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | matching both ways |
| 625 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | matching both ways |
| 626 | ESCALATE | ESCALATE | ESCALATE | matching both ways |
| 627 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | ESCALATE | missing both ways |

The published reading reproduces the ruling this run published for every case above, so the two rules are being compared on the run's own panel.

## What the signed rule changes

Counted over the 108 cases read, across all three sets.

| movement | cases |
|---|---|
| matching both ways | 98 |
| matching -> missing | 0 |
| missing -> matching | 1 |
| missing both ways | 9 |

Matching and missing are the four graded fields: the ruling, both amounts and the sorted referral clause references.

**Turns a match into a miss: no case.**

**Turns a miss into a match: 533.**

**Turns a safe outcome into a monetary ruling that differs from the key: 501.** A safe outcome is one the published rule left moving no money -- an `ESCALATE`, a `NO_ACTION`, or no ruling at all, which is what a panel whose every draft was rejected produces. Those are the cases where the signed rule decides a case that was previously left alone, and decides it wrongly.

- `501` — published `ESCALATE`, signed `PARTIAL_REFUND 8.5`, key `PARTIAL_REFUND 14.5`

No case was refused: every recorded panel was rebuilt.

Prompts digest 5b8510cd900aa9da. The measurement reads only; it writes report.md and amount-rule.json and nothing else.