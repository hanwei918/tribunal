English translation of the archive's `DESIGN.md` (sha256 `3341b4423fa45e9198c347e9db4723d1548789c012638ae6190e2adf9f8e24a4`); the original, in Chinese, stays outside the repository.

# Sealed set design table (24 cases)

Case numbers: RD 301–312, NS 401–412. Date 2026-08. rider/driver ids use the 1xxxx range, which does not overlap the dev set.

| case | category | expected ruling | amount | difficulty | trap | deciding clause |
|---|---|---|---|---|---|---|
| 301 | RD | NO_ACTION | — | EASY | verbosity decoy (rider) | RD-01 below 20% |
| 302 | RD | PARTIAL_REFUND | computed | HARD | double-counted ERP | RD-01/02/09(1), surge 1.2 |
| 303 | RD | PARTIAL_REFUND | computed | REVERSAL | threshold edge, trace 20.3% vs trip 20.0% | RD-01, trace preferred |
| 304 | RD | PARTIAL_REFUND | 1.00 | HARD | fully exonerated but the ERP refunded singly | RD-03 cap + RD-09(2) |
| 305 | RD | DRIVER_COMPENSATION | 1.30 | REVERSAL | the rider asks for the detour + under-charging | RD-04 |
| 306 | RD | FULL_REFUND | total | HARD | repeat pattern escalates + referral | RD-01 material + RD-06(b)(c) |
| 307 | RD | ESCALATE | — | INDET | missing decisive evidence (tunnel 240 s gap) | RD-07(a)(iii) + RD-10(3) |
| 308 | RD | NO_ACTION | — | HARD | verbosity decoy + upfront | RD-11 |
| 309 | RD | NO_ACTION | — | HARD | wrong field, solo_optimal | RD-12 |
| 310 | RD | PARTIAL_REFUND | 3.00 | HARD | phantom gantry + no deviation | RD-09(4) referral |
| 311 | RD | ESCALATE | — | HARD | contradictory evidence: the chat's request vs a trace that never approached | RD-10(7) |
| 312 | RD | PARTIAL_REFUND | computed | HARD | profile decoy: the rider's 60d shows 5 complaints but this one is right | RD-05 + RD-08 + RD-02 |
| 401 | NS | DRIVER_COMPENSATION | 4.80 | EASY | verbosity decoy (rider); airport 480 s | NS-01 + NS-07 |
| 402 | NS | FULL_REFUND | 4.00 | HARD | the driver's statement is precise but the arrival is false | NS-05(i) |
| 403 | NS | FULL_REFUND | 4.00 | EASY | the rider names the entrance | NS-03(i) |
| 404 | NS | FULL_REFUND + comp 2.00 | 4.00/2.00 | HARD | compound ruling | NS-03(ii) |
| 405 | NS | FULL_REFUND | 4.00 | EASY | the driver satisfies NS-01 but NS-04 displaces it | NS-04 |
| 406 | NS | DRIVER_COMPENSATION | 3.20 | HARD | reading only the chat misses an in_app_call | NS-04(b) fails → NS-01 |
| 407 | NS | FULL_REFUND | 6.00 | HARD | the 298 s edge; the rider is absent and it is refunded anyway | NS-06 |
| 408 | NS | NO_ACTION | — | HARD | the driver appeals, the fee is already refunded, a NO_ACTION counterparty | GEN-03 + NS-06 |
| 409 | NS | ESCALATE + referral | — | HARD | near-synonym fields: lifetime 1 vs 30d 5 | NS-07 anti-farming |
| 410 | NS | ESCALATE | — | INDET | the trip and the GPS contradict each other directly | NS-09(b) |
| 411 | NS | ESCALATE | — | INDET | GPS MISSING | GEN-02(2) → NS-09(a) |
| 412 | NS | FULL_REFUND | 4.00 | REVERSAL | profile decoy: the rider's lifetime is poor but the 30d is clean | NS-06 |

Distribution: EASY 4 / HARD 14 / REVERSAL 3 / INDET 3 (all within the schema's bounds).
Rulings: NO_ACTION 4 / PARTIAL 6 / FULL 7 / DRIVER_COMP 3 / ESCALATE 5 (the NS set's three ESCALATEs each use a different mechanism).

Design discipline:

- The dev set's 29 cases' content was not consulted; only the schema + the policy were used
- `admissibility.notes` only describes and does not judge (deliberately unlike the dev set)
- The answer key is a file of its own; the case files carry no answer key at all
