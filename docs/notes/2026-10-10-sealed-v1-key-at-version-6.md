# sealed-v1's key, re-derived at policy version 6 (2026-10-10)

The import note (`2026-10-09-sealed-v1-imported.md`, "The key will be re-derived before the run") said the key
written under policy version 1 would be re-derived by the key owner under the frozen version 6, without seeing any
system output on the set, and replaced in a later commit that records the old and new digests. This is that commit.
No run of sealed-v1 exists; none was consulted.

## What changed

One record: case 311. The other 23 are byte-identical in content.

| | version-1 key | version-6 key |
|---|---|---|
| expected_ruling | ESCALATE | PARTIAL_REFUND |
| expected_amount_sgd | null | 7.05 |
| expected_driver_compensation_sgd | null | null |
| expected_referrals | [] | [] |
| governing clause | POL-RD-10(7) | POL-RD-14 (amendment 0002), POL-RD-01, POL-RD-02, POL-RD-06, POL-RD-08 |

Why: the rider's waypoint request in the chat log is never approached by the trace (nearest fix 2595 m), which is
exactly the case POL-RD-14 decides: the request did not cause the excess, POL-RD-04 does not apply, and POL-RD-10(7)
is not engaged. The excess (4.90 km, 65.3 percent, material, no POL-RD-06 pattern) is refunded under POL-RD-02:
recomputed fare 13.585, refund 20.62 - 13.585 = 7.035, rounded up to 7.05. The full rationale is in the key record.

## Every version 1 -> 6 change, checked against every case

POL-RD-14 (reaches 305 and 311, the two cases with a populated waypoint_hint; only 311 changes); POL-RD-13 (301, 304,
306; unchanged); POL-RD-06(b) wording (306, no pass-through line; unchanged); POL-GEN-05 threshold (302, 306: amount
unchanged, payment held); integrity weights and GPS_GAP grading (307: weight 0.39 at version 6, ESCALATE unchanged);
platform_policy derivation (every no-show case: AUTHORED-V1, the same figures); POL-NS-01(d) (403, 404: drivers
outside the radius, POL-NS-03 governs; unchanged); POL-NS-05(iii) referral (402 is limb (i); unchanged); POL-NS-10,
POL-NS-11, POL-NS-12, POL-GEN-08 scope (reach no case). All 24 cases build a version-6 brief without error.

Disclosed and not edited: 410 is the example POL-NS-09(b) gives and also meets POL-NS-05's 300 m limb; both clauses
read the same at versions 1 and 6, so its ESCALATE key stands.

## Digests

| file | before | after |
|---|---|---|
| `eval/answers/sealed-v1/ground_truth.json` (as committed) | `7529d925e9defa6a93576661cda22f553e5337bad8662d87e813bc5b3fc74640` | `f430f6c017e109bd0feee86e3eac611dab7b087dee51ec5f644eb2eb9880b353` |
| the key in the archive's own serialisation | `412d60bdf207b2be7f66986f40dc4d517b084df7e45dc4c12b566686cddd7f6d` | `da19f120492420616d9cba98e32598f7f76bfc01b393697c9c48b131c8267244` |

`eval/external/sealed-v1/eval_index.json` and `MANIFEST.json` are kept as the archive's record and are not edited;
no code reads `eval_index.json`, and its 311 row still shows the version-1 value. The case files and
`case_set_sha256` (`5ae22377...`) are unchanged.
