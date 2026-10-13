# Design notes: NO_SHOW_CHARGE blueprint (4051-4065), internal

Companion to `build/blueprint_ns.json`. Answer-bearing; stays under `build/`.

## 1. How the blueprint was made and checked

- Source scripts (throwaway, `tmp/ns/`): `geo_ns.py` (timed paths, resolved fixes), `content_a/b/c.py` (payload
  facts, admissibility, intent), `measure_ns.py`, `make_blueprint.py` (assembler + checks), `proto_build.py`
  (independent rebuild from the JSON alone). Since revision r2 these are the r2 sources (also in `tmp/ns_r2x/`, with
  the r1 copies in `tmp/ns_r2x/bak/ns_r1/` and the r0 copies in `tmp/ns_r1/bak/ns_r0/`); see sections 6 and 7.
- Every artifact in the blueprint was built through `build/common.py` (`trip_record`, `gps_trace`, `chat_log`,
  `fare_breakdown`, profiles, `advisory`, `adm_*`, `artifact`, `make_case`, `key_record`) and passed
  `validate_case`, `lint_case` and `validate_key` with zero problems.
- `tmp/ns/proto_build.py` reads only `build/blueprint_ns.json`, rebuilds all 15 cases and keys, writes them to
  `tmp/ns/proto_out`, and runs `ref/check_set.py --range 4051 4065`: 15 cases, the only failure is the expected
  "both categories are required" (single-category run).
- 337 design checks pass (232 at r0, 313 at r1; r1 and r2 additions in sections 6 and 7): per-case policy facts (dwell seconds, distances, radius membership, limb conditions),
  the POL-NS-08 limbs measured from the built case (engaged only where designed: 4053 (b), 4061 (b) on the export,
  4064 (c)), Decimal recomputation of every payout (NS-07 80 % of the net fee, NS-03(ii) 50 %), fee-line
  reconciliation, plan agreement (ruling, difficulty, filer, channel), party-id ranges and uniqueness, and a
  cross-check that every one-decimal figure quoted in a rationale or derivation is a measured value.
- The checks were shown to fail: mutations (4059 loop fixes moved to the pin; 4053 gap filled; a sub-location word
  in 4056's chat; 4061 fee line 7.00; 4058 ruling changed; 4061 payout on the gross line; 4056 goodwill 3.60; a
  rationale distance altered) each produced a PROBLEM line; a tampered built file (trace distance, total) made
  check_set fail.
- Regeneration is byte-identical under different `PYTHONHASHSEED` values (sha256 recorded at build time).
- Set tally (matches plan.json): FULL_REFUND 4, NO_ACTION 3, DRIVER_COMPENSATION 5, ESCALATE 3 (2 evidence, 1
  policy); EASY 4, HARD 6, REVERSAL 3, INDETERMINATE 2; DRIVER filer 7, RIDER 8.

## 2. Blueprint conventions for the generator

- `facts.trip_record.fields` -> `common.trip_record(case_no, **fields)` (platform_policy already the ten-key dict).
- `facts.gps_trace.points` / `rider_track` are authoritative; build with `common.gps_trace(case_no, points,
  rider_track=..., **build)` (`expected_interval_sec`, `gap_threshold_s`, `coverage_pct`); `payload_summary` is
  what the call must return. `design` holds the timed legs, emission parameters (cadence, accuracy ranges, jitter,
  overrides, rng salts) and named points, for the record.
- `facts.chat_log.messages` -> `common.msg(..., k=k)`; `truncated` as given.
- `facts.fare_breakdown.fields` -> `common.fare_breakdown(case_no, **fields)`; money as Decimal strings.
- Profiles: `common.rider_profile(party_id, snapshot_at, **fields)` / `driver_profile(...)`.
- Advisories: `{"seq", "missing": true}` or `{"seq", "source", "payload"}` with `common.advisory(...)` arguments.
- `facts.admissibility` keyed TRIP_RECORD ... TRAFFIC_ADVISORY-01: status, issues, gps_gap_grade, notes, optional
  issue_details, and the weight `common.weight_for` must return.
- `artifact_meta`: generated_at = filed_at, assessed_at = filed_at + 5 s, sources per artifact (4061's GPS_TRACE is
  DRIVER_DEVICE).
- `intent.key_rationale` is ready for `common.key_record`; amounts are strings.
- `waypoint_hint` is null on every NS message (no message names a place the platform would resolve, and no NS
  clause reads it). venue_id format `VEN-YS-0031` (4056 only).

## 3. Changes from plan.json (rulings and difficulties unchanged)

- General, BUTTON cases: trip_record.events carry no wait_timer events. Only 4061 (GPS_AUTO) has them.
  PUBLIC-CONTRACT says "an arrival or wait-timer event is an independent carrier of the dwell"; POL-NS-12 restricts
  that to GPS_AUTO with a stated geofence test. Putting button-started timers in 4053/4059/4062 would have built
  those cases on a contract-versus-policy tension; leaving them out removes it.
- General: every chat has a message within 300 s on each side of the arrival marker, so POL-NS-08(c)'s gap limb is
  not tripped by accident (added: 4055 09:19:20, 4056 15:09:30, 4057 07:13:30, 4059 18:18:30, 4061 13:04:00,
  4062 12:31:30, 4063 07:58:30). 4064 keeps its 470 s interval (the truncation is the designed defect).
- General: holds run 5 s past the termination so the fix at the cancellation reports 0 km/h; the
  "first qualifying in-geofence fix" is measured and recorded for every case. In 120/150 m zones it precedes the
  tap (4055 09:21:40, 4058 23:41:30 since r2 (r1: 23:41:40), 4065 18:12:30); both figures are in the intent. Since r1
  it also precedes the tap by 10 s (the roll-in fix) in 4051, 4052, 4053, 4057, 4059 and 4060.
- 4053: the first fix after the gap (21:17:50) is 21.9 m from the pin moving 8 km/h (departing), not a stationary
  in-radius fix.
- 4054: the taxi moves away until the U-turn peak at 12:39:40 (3077.9 m), then closes at every fix (2887.5 m at
  acceptance, 2124.0 m at grace end, 898.0 m at the cancellation). Route moved to lat about 1.337 so the start lies on
  plausible roads.
- 4056: pre-arrival driver message added (above). Stationary point 211.7-217.4 m; nearest approach in the last 15
  minutes 211.7 m (no fix within 120 m).
- 4059: in-geofence intervals 60 s (18:20:50-18:21:50, since r1; r0 had 50 s) + 75 s = 135 s, as in the plan; the
  most generous boundary reading (last outside fix before each run to the first outside fix after it or the
  termination, whichever comes first; r1: run 2's next outside fix 18:26:30 follows two post-termination in-radius
  fixes) is 80 + 85 = 165 s, still below 180. Loop maximum 182.6 m (plan
  about 260 m; the 300 m leash is not near). Bus-lane advisory hours 07:30-23:00 (the full-day bus-lane hours)
  instead of 07:30-20:00; both cover the wait. A recorded driver call (18:23:20) and an answered rider message keep
  POL-NS-04 out on limb (b).
- 4061: export fixes in the window are 5.6/17.8/8.0 m (plan 15-35 m). Since r1 the export runs 12:58:45-13:14:50
  (35 s after acceptance, 40 s after the termination; r0's 90 s / 100 s were POL-NS-08(a) edges) and the figures
  are de-echoed from the organisers' sample: fee 6.00 net / 8.81 gross, free wait 240, threshold 360 (event
  `no_show_threshold_reached` 13:12:00), payout 4.80, two unanswered calls, export weight 0.3 (LOW_SAMPLE_RATE x
  PARTIAL_RECORD x UNVERIFIED_SOURCE). The approach fix is 825.5 m at 22 km/h.
- 4062: the canyon drift also affects the approach from 12:31:00, so the approach cannot anchor the car's position.
  Window: 16 fixes within 50 m (max 29.8 m), 16 at 93.1-137.9 m, 13 of 31 consecutive jumps 84.1-146.8 m, longest
  in-radius run 3.
- 4063: trip 08:08:45-08:14:45 (plan ended 08:21:30) for a realistic 1.56 km local run; billed 1.56 km (a multiple
  of 0.04, so 0.75/km is exact: 1.17); total 12.45. The tap fix (08:02:00) is 96.2 m away with reported 12 km/h and
  position-derived 10-12 km/h, so neither POL-NS-05 trigger fires by accident.
- 4064: the rider walks from 1.25 km to 1.0 km away (plan "1.1 km throughout").
- 4065: date moved from 2026-08-14 to 2026-09-18 so the AUTHORED-V1 free_wait_sec 300 for a TRANSPORT_HUB postdates
  the fee_schedule changelog (480 -> 300 on 2026-09-03). The tap is at 18:12:50 when stopped in the bay: a tap at the
  first in-radius fix (18:12:30, moving 27 km/h; 20 km/h since r2) would have made the marker false under POL-NS-05's
  15 km/h trigger.
  The dwell from the first qualifying fix stays 95 s as planned. The rider no longer walks "from Bedok MRT" (the MRT
  adjoins the interchange; her track is 299-438 m away); she writes "walking over now".

## 4. Policy readings that needed care

- 4054: POL-NS-02 says a driver with no in-radius fix in the 15 minutes before the cancellation "never arrived" and
  the rider is entitled to a full refund; POL-NS-10(f) says a rider's own late cancellation is chargeable "whether
  or not the driver had arrived". Read together: NS-02's refund is framed as POL-NS-01(b) failing, and NS-01 is the
  driver-terminated no-show test (limb d); NS-10 is the clause for a fee the rider's own cancellation triggered and
  its words expressly cover the non-arrival case. The derivation states this.
- POL-GEN-02(2) with POL-NS-11 (4053, 4062): NS-11 says the missing rider_track does not lower the cap on a finding
  resting on the driver's track. Discounting the PARTIAL_RECORD factor leaves 0.6 (4053) and 0.5 (4062), both
  below 0.70, so the escalations do not depend on the rider_track factor.
- 4061: NS-08(b) is engaged on the export, but NS-12 makes the platform's events an independent, unimpaired carrier;
  NS-08's closing sentence needs the impaired artifact to be the ONLY evidence, so it does not fire.
- 4064: NS-08(c) is engaged on the chat by design; the chat carries no deciding fact (NS-04 fails on the call record
  and the rider_track whatever the missing message said).
- No brief statement disagrees with the policy files.

## 5. Process note

During checking, one backup copy of `blueprint_ns.json` was written to the session temp directory outside the
workspace by a `cp` command. It was deleted within the same session; no other file outside the workspace was
created, read or changed.

## 6. Revision r1 (build/critique_ns_r1.json)

Full log, item by item, with the policy reasoning and verification: `build/revisions_ns_r1.md`. In short, with every
ruling and difficulty unchanged:

- `platform_policy.source` PLATFORM-PUBLISHED-2026-10-07 -> RECORD-PLATFORM in 4051-4055, 4060, 4062, 4063 (no figure
  changes; the old string postdated the trips).
- BUTTON approaches smoothed in 4051, 4052, 4053, 4057, 4059, 4060: a 10 s slowing leg and a 10 s, 20 m roll-in before
  the tap, so the position-derived speed into the 0 km/h tap fix is 5.5-7.9 km/h (was 18-22). First qualifying fix
  10 s earlier; dwells +10 s (260, 280, 210, 430, 4059 runs 60 + 75, 80).
- Text: 4055 rider no longer claims to know the driver's flags; 4058 no "on hold"; 4063 MSG-005 says the free wait is
  over; 4065 driver's excuse is impatience, not a kerb condition (NS-06(i) / MISSING advisory).
- 4061 export span and figures as in section 3.
- New checks: approach speed into the tap, first-qualifying-fix position, exact r1 dwell values, 4061 NS-08(a) span,
  de-echo and payout, 4059 runs from the first qualifying fix, and a regression guard against pre-r1 phrases; seven
  mutations shown to fail. Independent re-check `tmp/ns_r1/verify_r1.py` (check_set's km, Decimal): 0 failures.

## 7. Revision r2 (build/critique_ns_r2.json)

Full log, item by item, with the policy reasoning and verification: `build/revisions_ns_r2.md`. In short, with every
ruling, amount, referral list and difficulty unchanged:

- 4058 (the only FIX): the final approach now decelerates over 40 s (position-derived 21.9 -> 22.4 -> 18.7 -> 12.7 ->
  5.8 km/h into the tap; the fix 10 s before the tap reports 6 km/h, was 30). First qualifying fix 23:41:30 (105.7 m;
  the 23:41:20 fix is 167.3 m out), so the dwell from it is 600 s (was 590 s from 23:41:40). Texts updated.
- Optional items applied: the same deceleration and roll-in for 4055 (fq 09:21:40 kept, now 76.4 m; dwell 360 s kept)
  and 4065 (fq 18:12:30 kept, now 76.3 m; previous fix 164.4 m; dwell 95 s kept); 4055 governing_clauses without
  POL-NS-04 (POL-NS-11: "decided under the remaining clauses"); 4061 timer event wording no longer echoes the sample;
  4062 GPS note says the 3-fix run is the longest "in that window".
- Optional items rejected: rider-side net fee line in 4052/4055, RYDE_X fee spread, 4062 weight 0.375 (reasons in the
  revisions log).
- Every fix from the tap onward, every rider fix and every accuracy value is unchanged in the three re-timed traces
  (same seeded draws); trace_distance_km 4055 4.029 -> 4.030, 4058 1.575, 4065 2.410 (recomputed from the written
  points with check_set's km).
- New checks (337 in all): approach into the tap for 4055/4058/4065, the fix before the first qualifying fix >= 10 m
  outside the radius, the fixed dwells, 4055's clause list, and an r2 stale-phrase guard; ten mutations shown to fail.
  Independent re-check `tmp/ns_r2x/verify_r2.py` (check_set's km, Decimal): 139 PASS, 0 FAIL on the r2 build; 21 FAIL
  on the r1 build.
