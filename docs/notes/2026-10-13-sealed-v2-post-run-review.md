# The fourth sealed set, reviewed case by case after its run (2026-10-13)

**This review was made after the run.** `sealed-v2` was run once, on 2026-10-11
at 16:12 SGT, and scored 12/12. The manifest's first release gate asked for a
case-by-case sign-off *before* the run, and that did not happen
([provenance note](2026-10-12-sealed-v2-provenance.md), section 2). This note is
that review, done late. It cannot meet the gate, and it does not claim to.

**No answer was changed.** Nothing under `eval/answers/sealed-v2/`, `data/`,
`runs/`, `tribunal/`, `prompts/` or `policy/` was edited. The key reviewed is the
one the run was scored against:

    sha256  d3a09c08f06c8eb328e251e618cba7b035fdb54c7614b041781fd6d564fe3e6f
            eval/answers/sealed-v2/ground_truth.json

Had the review found a wrong answer, the answer would still stand as written and
the disagreement would be recorded here. A key corrected after the score is
known is a key fitted to the score.

## Who did it, and what they knew

- Done on 2026-10-13 by Claude (Anthropic), the policy owner's AI assistant, at
  the request of the policy owner, Ji Guofang. Whether she adopts it as her own
  sign-off is her decision; this note does not sign for her.
- **The reviewer knew the result.** The 12/12 score was known before the
  review started. Each answer was therefore checked only against the version-6
  policy text and the case file. The model's rulings were not used as evidence
  for or against any answer.
- The statement elsewhere that nobody on the development side has seen the
  set's answers was true up to and including the run. Reading the key for this
  review ends it. The set has been run once and is not run again, so the
  reading cannot reach its score.

## How each case was checked

For every case:

1. The case file was read field by field: trip record, GPS trace (fix count,
   gaps, accuracy, distance from the pickup pin, speeds), chat log, fare lines
   and both profiles.
2. The policy text was loaded as the run loaded it,
   `tribunal.loader.load_policies(category, 6)`, and each clause the key cites
   was read in full, together with the clauses that could displace it.
3. The facts the code computes were rebuilt with
   `tribunal.brief.build_brief_for_case(case, policy_version=6)` and compared
   with the figures in the key's rationale.
4. The key's ruling, both amounts and its referrals were worked out again from
   steps 1 to 3 and compared field by field.

## Result

**All 12 answers are consistent with the version-6 policy text. No case was
found where a second reading of the text leads to a different ruling, amount or
referral.** Six points are worth recording; none changes an answer. They are
listed after the table.

| Case | Key | Deciding facts, rechecked | Conclusion |
|---|---|---|---|
| 801 | PARTIAL_REFUND 1.45 | Trace 4.08 km against an optimal 3.15 km: excess 0.93 km and 29.5%, so a deviation under POL-RD-01 (over 20% and over 0.8 km) but not a material one. Recomputed fare 10.184875; 11.63 − 10.184875 = 1.445125, rounded up to the 0.05 step = 1.45. Trace complete, largest gap 10 s. | Consistent |
| 802 | FULL_REFUND 19.65, referral POL-RD-06(c) | Trace 10.06 km against 1.10 km: excess 8.96 km, material. `deviation_flags_90d` = 3, which meets POL-RD-06's threshold of 3, so limb (b) lifts the POL-RD-02 figure (13.15) to the whole 19.65 and limb (c) adds the conduct referral. No ERP, toll or airport line to treat separately. | Consistent |
| 803 | PARTIAL_REFUND 6.00, referral POL-RD-09(4) | Upfront quote 18.00, charged 24.00. The fare lines add up: 3.80 + 6.00 + 7.40 + 0.80 = 18.00, plus a 6.00 airport surcharge. Pickup is Bugis, dropoff Suntec City: no airport. POL-RD-11 shuts out POL-RD-02. The quote excess under RD-11(a) and the wrong surcharge under RD-09(4) are the same 6.00 line, counted once. RD-09(4) requires the billing-integrity referral and states that it does not trigger POL-RD-10(8). Excess distance 0.73 km, below 0.8 km, so no deviation in any case. | Consistent |
| 804 | NO_ACTION | RYDE_POOL. POL-RD-12 measures against the matched-itinerary optimal, 4.75 km, not the solo 3.10 km. Trace 4.88 km: excess 0.13 km, no deviation. | Consistent |
| 805 | PARTIAL_REFUND 4.20 | The rider asked in chat for a stop at Golden Mile Tower, and the driver says he relied on it. The trace never comes closer than 1,592 m to that waypoint, more than the 200 m limit, so POL-RD-14 excuses no distance and leaves no conflict for POL-RD-10(7) to escalate. Trace 5.50 km against 2.50 km: excess 3.00 km and 120%, material. POL-RD-06 check: `deviation_flags_90d` = 0, so no pattern and no uplift. Recomputed fare 8.715; 12.87 − 8.715 = 4.155, rounded up = 4.20. | Consistent |
| 806 | ESCALATE | GPS trace IMPAIRED, weight 0.60, issue GPS_GAP: a 160 s gap, over POL-RD-07's 90 s. No counterparty statement, no ERP gantries. The trip record's distance and the billed distance repeat the trace, so they are not independent corroboration. POL-RD-07 and POL-RD-10(3) therefore make escalation terminal. The code would otherwise compute a 2.10 refund; escalation replaces it. | Consistent |
| 851 | DRIVER_COMPENSATION 3.60 / 3.60 | AIRPORT pickup, radius 150 m. 22 fixes at 0 m, accuracy 8 m, from 18:10:00 to 18:13:30: 210 s against `platform_policy.free_wait_sec` 180. The fee schedule's resolution rule reads `platform_policy` first, so the legacy 480 s airport dwell does not apply. Driver terminated at 18:13:30 with RIDER_NO_SHOW, after the dwell had elapsed at 18:13:00. Rider wrote "I cannot get there in time", which is not a locating message, so POL-NS-04 does not apply. Driver 1 no-show in 100 trips. 4.50 × 0.80 = 3.60, in both amount fields under POL-GEN-03. | Consistent |
| 852 | FULL_REFUND 4.50 | Accepted 18:10:00, rider cancelled 18:11:30: 90 s, inside the 180 s grace. POL-NS-10(a) makes it free whatever the driver's position (667 m away), and (c) refunds the 4.50 in full with no driver payment. | Consistent |
| 853 | DRIVER_COMPENSATION 3.60 / 3.60 | The rider's message at 18:10:20 ("cannot see you, where are you?") went unanswered and no call was made, so POL-NS-04 limbs (a) and (b) hold. But `rider_track` is empty, so limb (c) cannot be run. POL-NS-11 says the clause then cannot exonerate, and that the missing track does not impair the driver's evidence. Driver: 25 fixes at 0 m, 240 s against 180 s, RIDER_NO_SHOW after the dwell. The lifetime `prior_no_show_flags` (rider 19, driver 24) are context only under POL-GEN-01. The 30-day counters (rider 0, driver 1 in 100) trigger nothing. | Consistent |
| 854 | FULL_REFUND 4.50, driver 2.25 | LARGE_VENUE, radius 120 m. The driver was stationary for 240 s at 200.2 m, outside 120 m and inside 400 m: POL-NS-03, full refund. The venue_id is SUNTEC-CITY on both, which corroborates a wrong-entrance case. Nobody in the chat named an entrance or tower, and there are 3 registered pickup points, so limb (ii) goodwill = 4.50 × 0.50 = 2.25, not netted against the refund. The arrival mark at 200.2 m and 0 km/h is within 300 m, so POL-NS-05 does not apply. The driver replied within 10 s, so POL-NS-04 does not apply. | Consistent |
| 855 | DRIVER_COMPENSATION 3.60 / 3.60 | The exported trace is IMPAIRED: weight 0.60, 3 fixes, a 160 s gap, no accuracy reported. The code's own POL-NS-02 test finds 0 qualifying fixes. The marker is GPS_AUTO, though, and the trip record carries the platform's arrival event (0 m, 0 km/h), `wait_timer_started` at 18:10:00 and `wait_timer_expired` at 18:13:00, before the 18:14:00 termination. POL-NS-12 makes those an independent carrier, and no exported fix contradicts them. Rider "cannot get there in time". Driver 1 in 100. 3.60. | Consistent |
| 856 | ESCALATE, referral to refund 4.50 | The basic no-show holds: 25 fixes at 0 m, 240 s, RIDER_NO_SHOW. But `no_show_terminations_30d` = 5 and `completed_trips_30d` = 50: 5 ≥ 4 and 0.10 > 0.08. POL-NS-07 withholds the payout and POL-NS-09(d) escalates, with the instruction to refund 4.50 written into the packet as a referral, not paid. | Consistent |

## Points recorded, none changing an answer

1. **802 sits exactly on the threshold.** `deviation_flags_90d` = 3 meets
   POL-RD-06 at "3 or more". One flag fewer and the answer would be a
   PARTIAL_REFUND of 13.15 with no referral. The answer is right; the case is
   built on the edge on purpose.
2. **803 has one line, two routes to it.** POL-RD-11(a) and POL-RD-09(4) both
   reach the same 6.00 airport line. The key counts it once, which is what
   RD-09's opening sentence ("never counted twice") requires.
3. **806's distances are not corroboration.** The trip record's actual
   distance and the billed distance repeat the impaired trace. A reader who
   counted them as a second source would rule rather than escalate. The key
   does not.
4. **853 reads two clauses that pull apart.** POL-NS-04's own text calls a
   missing rider track an impairment under POL-NS-08(b). POL-NS-11, added
   later, overrides that by name ("Notwithstanding POL-NS-08(b)"). The key
   follows POL-NS-11, the later and more specific clause. POL-NS-11's own note
   says the two are to be folded together at the next base revision.
5. **855 depends wholly on POL-NS-12.** Without it, the export could not
   establish arrival: the sparse trace would be impaired under POL-NS-08(b), the
   only evidence for the deciding fact would be impaired, and the case would
   escalate under POL-NS-09(e). The answer is right because version 6 includes
   POL-NS-12, so this case tests whether the reader knows that clause exists.
6. **The set is small and built to type.** Each case isolates one clause. All
   12 profiles in the no-show cases share one template (740-day accounts, 830
   lifetime trips, rating 4.8); only a few counters change from case to case,
   the decisive ones and, in 853 and 856, the lifetime decoys. The set measures
   whether the system applies the clause each case was built for. It does not
   measure messy, real-world records. Twelve out of twelve gives a Wilson 95%
   interval of 75.8% to 100.0%.

## What this changes

- `MANIFEST.json` still reads `review_status: PENDING`. It sits in the answer
  archive, which this repository does not edit, so this note is where the late
  review is recorded.
- The reported figure does not change: 12/12, against the key as imported.

## Adopted (2026-10-13)

The policy owner, Ji Guofang, adopted this review as her case-by-case
sign-off on 2026-10-13, after the run. It was made with her AI assistant
(Claude), which knew the 12/12 result; it does not meet the MANIFEST's
pre-run release gate, and the key it reviewed is unchanged (sha256 above).
