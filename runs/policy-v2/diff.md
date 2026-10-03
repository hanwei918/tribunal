# Policy-gap diff — amendment 0001 (policy version 2)

Model: deepseek/deepseek-flash. Cluster: C4.

**A change under a new policy is not necessarily an error.** The new version says something the old one did not, and a case that moved may have moved because the new clause is right.

**The amendment was drafted from closures on these same sets, so the newly matching counts are in-sample and are not comparable to the headline.**

`changed` compares the four graded fields: money as a decimal, so `4.0` and `4.00` are the same money and `null` is never zero, and each referral by the clause reference it leads with, which is how the grader compares it. A referral whose wording moved while its clause reference did not is therefore not a change, and the `old` and `new` columns show the references rather than the wording.

This command reads the frozen version-1 answer key, to grade each development-set case before and after. No other command in this module reads it, and the keys are never edited.

**This diff is at policy version 2, which carries two changes.** Version 2 holds this amendment and part B's POL-RD-11 upfront-quote remedy, which changes the money block of every UPFRONT_QUOTE fare's brief. A case that moved between version 1 and version 2 may have moved for either reason, so these gains cannot be attributed to the amendment alone.

| case | set | changed | old | new |
|---|---|---|---|---|
| `101` | corpus | no | PARTIAL_REFUND / 8.05 / null / - | PARTIAL_REFUND / 8.05 / null / - |
| `102` | corpus | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `103` | corpus | no | PARTIAL_REFUND / 4.00 / null / - | PARTIAL_REFUND / 4.00 / null / - |
| `104` | corpus | no | PARTIAL_REFUND / 3.60 / null / - | PARTIAL_REFUND / 3.60 / null / - |
| `105` | corpus | no | FULL_REFUND / 65.13 / null / POL-RD-06(c) | FULL_REFUND / 65.13 / null / POL-RD-06(c) |
| `106` | corpus | no | PARTIAL_REFUND / 10.75 / null / - | PARTIAL_REFUND / 10.75 / null / - |
| `107` | corpus | yes | PARTIAL_REFUND / 7.45 / null / - | ESCALATE / null / null / - |
| `108` | corpus | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `109` | corpus | no | DRIVER_COMPENSATION / 3.15 / 3.15 / - | DRIVER_COMPENSATION / 3.15 / 3.15 / - |
| `110` | corpus | no | ESCALATE / null / null / - | ESCALATE / null / null / - |
| `111` | corpus | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `112` | corpus | no | ESCALATE / null / null / - | ESCALATE / null / null / - |
| `113` | corpus | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `114` | corpus | no | PARTIAL_REFUND / 13.70 / null / - | PARTIAL_REFUND / 13.70 / null / - |
| `115` | corpus | no | PARTIAL_REFUND / 2.00 / null / POL-RD-09(4) | PARTIAL_REFUND / 2.00 / null / POL-RD-09(4) |
| `501` | wild-dev | yes | ESCALATE / null / null / - | PARTIAL_REFUND / 14.50 / null / - |
| `502` | wild-dev | no | FULL_REFUND / 17.92 / null / POL-RD-06(c) | FULL_REFUND / 17.92 / null / POL-RD-06(c) |
| `503` | wild-dev | no | PARTIAL_REFUND / 8.00 / null / - | PARTIAL_REFUND / 8.00 / null / - |
| `504` | wild-dev | yes | ESCALATE / null / null / - | PARTIAL_REFUND / 17.60 / null / - |
| `505` | wild-dev | no | PARTIAL_REFUND / 9.15 / null / - | PARTIAL_REFUND / 9.15 / null / - |
| `506` | wild-dev | no | PARTIAL_REFUND / 10.20 / null / - | PARTIAL_REFUND / 10.20 / null / - |
| `507` | wild-dev | no | PARTIAL_REFUND / 9.80 / null / - | PARTIAL_REFUND / 9.80 / null / - |
| `508` | wild-dev | yes | ESCALATE / null / null / - | PARTIAL_REFUND / 6.00 / null / - |
| `509` | wild-dev | no | PARTIAL_REFUND / 10.70 / null / - | PARTIAL_REFUND / 10.70 / null / - |
| `510` | wild-dev | no | PARTIAL_REFUND / 10.00 / null / - | PARTIAL_REFUND / 10.00 / null / - |
| `511` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `512` | wild-dev | no | ESCALATE / null / null / - | ESCALATE / null / null / - |
| `513` | wild-dev | no | PARTIAL_REFUND / 13.20 / null / - | PARTIAL_REFUND / 13.20 / null / - |
| `514` | wild-dev | no | PARTIAL_REFUND / 8.70 / null / - | PARTIAL_REFUND / 8.70 / null / - |
| `515` | wild-dev | no | FULL_REFUND / 62.28 / null / POL-RD-06(c) | FULL_REFUND / 62.28 / null / POL-RD-06(c) |
| `516` | wild-dev | no | PARTIAL_REFUND / 3.00 / null / POL-RD-09(4) | PARTIAL_REFUND / 3.00 / null / POL-RD-09(4) |
| `517` | wild-dev | yes | None / null / null / - | ESCALATE / null / null / - |
| `518` | wild-dev | no | PARTIAL_REFUND / 3.95 / null / - | PARTIAL_REFUND / 3.95 / null / - |
| `519` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `520` | wild-dev | no | DRIVER_COMPENSATION / 1.90 / 1.90 / - | DRIVER_COMPENSATION / 1.90 / 1.90 / - |
| `521` | wild-dev | no | FULL_REFUND / 2.00 / null / POL-RD-09(4) | FULL_REFUND / 2.00 / null / POL-RD-09(4) |
| `522` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `523` | wild-dev | yes | FULL_REFUND / 4.00 / null / - | ESCALATE / null / null / - |
| `524` | wild-dev | no | PARTIAL_REFUND / 3.20 / null / - | PARTIAL_REFUND / 3.20 / null / - |
| `525` | wild-dev | no | PARTIAL_REFUND / 4.50 / null / - | PARTIAL_REFUND / 4.50 / null / - |
| `526` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `527` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `528` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `529` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `530` | wild-dev | yes | ESCALATE / null / null / - | PARTIAL_REFUND / 5.80 / null / - |
| `531` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `532` | wild-dev | no | PARTIAL_REFUND / 6.00 / null / POL-RD-09(4) | PARTIAL_REFUND / 6.00 / null / POL-RD-09(4) |
| `533` | wild-dev | yes | None / null / null / - | PARTIAL_REFUND / 19.30 / null / - |
| `534` | wild-dev | no | PARTIAL_REFUND / 5.95 / null / - | PARTIAL_REFUND / 5.95 / null / - |
| `535` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `536` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `537` | wild-dev | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `9111` | codex | yes | PARTIAL_REFUND / 9.15 / null / POL-RD-09(4) | PARTIAL_REFUND / 9.15 / null / - |
| `9112` | codex | no | NO_ACTION / null / null / - | NO_ACTION / null / null / - |
| `9113` | codex | no | PARTIAL_REFUND / 9.05 / null / POL-RD-09(4) | PARTIAL_REFUND / 9.05 / null / POL-RD-09(4) |
| `9114` | codex | no | FULL_REFUND / 3.20 / null / POL-RD-09(4) | FULL_REFUND / 3.20 / null / POL-RD-09(4) |
| `9115` | codex | no | ESCALATE / null / null / - | ESCALATE / null / null / - |

## All affected cases

- cases: 57 (55 graded against the key)
- changed: 9
- newly matching: 4
- newly missing: 1
- escalations before: 8; after: 7

## Affected cases with the cluster's own cases excluded

- cases: 51 (49 graded against the key)
- changed: 7
- newly matching: 2
- newly missing: 1
- escalations before: 2; after: 3
