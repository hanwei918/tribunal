# Revisions r1: NO_SHOW_CHARGE blueprint (4051-4065), internal

Applies `build/critique_ns_r1.json` to `build/blueprint_ns.json`. Answer-bearing; stays under `build/`.

## 0. Outcome

- **Every planned ruling, amount rule, filer, channel and difficulty is unchanged.** No case needed an "honest
  alternative", so `build/plan.json` was **not edited**. Set tally unchanged: FULL_REFUND 4, NO_ACTION 3,
  DRIVER_COMPENSATION 5, ESCALATE 3 (2 evidence, 1 policy); EASY 4, HARD 6, REVERSAL 3, INDETERMINATE 2; DRIVER 7,
  RIDER 8.
- One amount changed with its facts, not its rule: **4061** payout is now 0.80 x 6.00 = **4.80** (was 0.80 x 5.00 =
  4.00), because the de-echoed net fee is 6.00. Ruling (DRIVER_COMPENSATION), difficulty (HARD) and mechanism
  (POL-NS-12 -> POL-NS-01 -> POL-NS-07) are unchanged.
- `build/blueprint_ns.json` sha256: before `214cd178da4f64998e6fc82418e8ac63f94e3a7aaa903da3b9cd3dd9d83d8b26`,
  after `6fa781b3c90b57eaa3c8389b82ab98a87f148914a65a1b5995c31e0d02be9e7a`.
- The blueprint is regenerated, not hand-edited: sources in `tmp/ns_r1/` (r0 copies in `tmp/ns_r1/bak/ns_r0/`), and
  the same r1 sources were synced into `tmp/ns/` so that re-running `tmp/ns/make_blueprint.py` reproduces the r1
  file byte for byte (checked) instead of silently restoring r0.

## 1. Decisions, item by item

### All cases carrying `platform_policy.source` PLATFORM-PUBLISHED-2026-10-07 (critic: 4051, 4052, 4053, 4054, 4055, 4060, 4062, 4063; optional)

**Applied** to all eight. PUBLIC-CONTRACT defines `PLATFORM-PUBLISHED-<date>` as "the defaults"; a record generated
in August/September citing a 2026-10-07 publication is an anachronism a reader can notice. `fee_schedule.resolution_rule`
reads `trip_record.platform_policy` whenever the record carries it, and only `AUTHORED-V1` changes how the figure is
interpreted (the greater-of rule); any other source means "the platform's own figure". So `RECORD-PLATFORM` changes no
figure, no limb and no outcome. Values in each block are unchanged. No text referred to the old source string.

### Approach into a BUTTON tap (critic: 4051, 4052, 4057; optional) - extended to 4053, 4059, 4060

**Critic right; applied, and extended to the same defect in three more cases.** The fix matched to the tap reported
0 km/h while the previous fix 10 s earlier was 50-62 m away (position-derived 18-22 km/h). With the reported speeds
(17-24 km/h) that distance cannot be covered and still stop, so the trace was physically implausible. POL-NS-05 reads
the single fix at the tap (0 km/h, under 300 m), so the clause's own test was never triggered; but a finite-difference
reader could call the marker false. In 4051 (NS-04 refund), 4052 (NS-10(g) payout) and 4057 (NS-01/NS-07 payout) that
reading would add an unplanned POL-NS-05(iii) false-arrival referral to a key whose referrals are []. In 4053
(ESCALATE), 4059 (corrected dwell short -> NS-05(i), which carries no referral) and 4060 (NS-10(a)) no outcome or
referral could move, which is why the critic did not list them; they were fixed anyway because the brief requires
plausible speeds and the defect is identical.

Mechanism (all six): the last 20 s before the tap became a 10 s slowing leg plus a 10 s, 20 m roll-in to the stop. The
tap fix keeps its time, position and 0 km/h; every stationary fix is unchanged (same seeded draws); only the approach
fixes move, because the approach route now ends 10 s earlier.

| case | position-derived speed into the tap fix (was -> now) | 10 s before that | roll-in fix (10 s before tap) |
|---|---|---|---|
| 4051 | 21.3 -> 6.8 km/h | 13.8 km/h | 08:06:50, 18.5 m from pin, 8 km/h |
| 4052 | 19.5 -> 5.5 km/h | 14.9 km/h | 19:30:50, 16.0 m, 5 km/h |
| 4053 | 21.3 -> 7.7 km/h | 15.6 km/h | 21:13:50, 24.9 m, 8 km/h |
| 4057 | 22.3 -> 7.9 km/h | 13.5 km/h | 07:16:50, 24.0 m, 9 km/h |
| 4059 | 18.1 -> 6.6 km/h | 11.5 km/h | 18:20:50, 27.1 m, 5 km/h |
| 4060 | 20.4 -> 6.4 km/h | 14.8 km/h | 07:43:45, 18.4 m, 7 km/h |

Consequence, stated in every affected text: the roll-in fix lies inside the 50 m STANDARD radius with accuracy under
25 m, so the first qualifying in-geofence fix (POL-NS-02 run of three) is now 10 s before the tap, and dwell measured
as POL-NS-01(c) measures it grows by 10 s. Margins checked against the policy for each case:

- 4051: dwell 250 -> 260 s vs free_wait 180 (NS-01 would hold; NS-04 still displaces it). FULL_REFUND 6.61 unchanged.
- 4052: dwell at the rider's cancellation 270 -> 280 s > 180, so NS-10(g) applies as before. Payout 3.60 unchanged.
  The advisory note's "driver speeds on Hougang Ave 8" window now ends at 19:30:30 (the 19:30:40/50 fixes are inside
  the drop-off); the range is still 11-21 km/h.
- 4053: observed in-radius span 21:13:50-21:15:00 = 70 s (8 fixes; was 60 s, 7 fixes from the marker); first
  qualifying fix to termination 210 s, of which the 140 s after 21:15:00 are inside the 170 s gap straddling the
  cancellation. NS-08(b) and NS-09(e) fire exactly as before; ESCALATE unchanged.
- 4057: dwell 420 -> 430 s vs 240. Payout 3.20 unchanged.
- 4059: first in-radius run 18:20:50-18:21:50 = 60 s (was 50 s), second 75 s to termination; NS-06(i) sum 135 s vs
  180 (short by 45 s); the most generous boundary reading is 80 + 85 = 165 s, still short. NO_ACTION unchanged. (The
  r0 notes chose 50 s to keep the generous reading at 155 s; 165 s is still unambiguously short at a 10 s cadence and
  equals the plan's own 60 + 75.)
- 4060: dwell at the rider's cancellation 70 -> 80 s, still under 180, so NS-10(g) cannot apply; NS-10(a) decides as
  before. FULL_REFUND 6.61 unchanged.
- trace_distance_km (recomputed by `common.gps_trace`, re-checked with check_set's km): 4051 1.572 -> 1.571, 4052
  2.558 -> 2.554, 4053 3.307 (unchanged), 4057 3.308 -> 3.309, 4059 2.890 -> 2.889, 4060 0.564 -> 0.559. Highest
  position-derived speed anywhere in the six changed traces: 39.4 km/h (4051, Tampines Ave 4); 4060 37.5 km/h.
- Each GPS_TRACE note now also states the fix before the marker (time, distance, speed), as a pre-pass measurement.

### 4055 (FIX): rider claims knowledge of the driver's no-show flags

**Critic right; applied.** A rider cannot see a driver's internal profile counters. claim_text now ends "Also please
check this driver, I think he does this to other passengers also." The POL-GEN-01 / POL-NS-07 trap is unchanged:
driver_profile.prior_no_show_flags 9 (lifetime, context only) against no_show_terminations_30d 2 / completed_trips_30d
121. Rationale and derivation 7 now say the request to check the driver cannot be answered from the lifetime counter
and only the NS-07 counters may be read. DRIVER_COMPENSATION 3.60 unchanged.

### 4058 (FIX): "payout ... on hold" unexplained by the record

**Critic right; applied.** Nothing in EV-TRIP-04058 / EV-FARE-04058 records a hold (CHARGED, refund 0.00), and "on
hold" echoes the fee-held outcome of POL-NS-07's anti-farming branch and POL-NS-09. claim_text now reads "... but it is
not in my earnings yet. Please credit my 6.00."; the internal `amount_represents` was reworded to match. No record field
changed; the escalation rests only on the counters (5 >= 4 and 5/54 = 0.0926 > 0.08). ESCALATE (policy) unchanged.

### 4061 (FIX), item 1: POL-NS-08(a) edge on the export's span

**Critic right; applied.** NS-08(a) impairs an artifact where "trip_record and gps_trace disagree on trip start or trip
termination time by more than 90 seconds". The export's first fix was exactly 90 s after acceptance and its last fix
100 s after the termination, so a reader could find a termination disagreement; NS-08(a) does not say which artifact
is impaired, and if the trip_record (the NS-12 carrier) were read as impaired, the impaired export would be the only
evidence and NS-08's closing sentence / NS-09(e) would escalate - a second defensible outcome. Now: first fix 12:58:45
(35 s after acceptance 12:58:10), last fix 13:14:50 (40 s after the 13:14:10 termination; 260.7 m from the pin at
30 km/h, on the departure leg, outside the waiting window and the radius). The 13:12:40 -> 13:14:50 interval (130 s)
keeps NS-08(b) engaged on the export as designed; every export interval is now 130-245 s. The three window fixes are
unchanged (13:06:20, 13:09:30, 13:12:40; 5.6/17.8/8.0 m; 0 km/h). Nearest fix to the arrival event still 20 s.

### 4061 (FIX), item 2: figures echo the organisers' sample

**Critic right; applied with the critic's figures.** Checked against ref/case-00901.json: the sample's platform_policy
has cancellation_fee 5.00, free_wait 300, threshold 480, GPS_AUTO; its trace is a DRIVER_DEVICE export with no accuracy,
LOW_SAMPLE_RATE + PARTIAL_RECORD = 0.6, empty rider_track, and one unanswered driver call. 4061 had 5.00 and 300 s
(threshold 420). New platform_policy (RECORD-PLATFORM): cancellation_fee_sgd 6.00, rider_gross_cancellation_fee_sgd 8.81
(6.00 at the published gross/net ratio 6.61/4.50 = 8.8133, written 8.81), free_wait_sec 240, no_show_threshold_sec 360.
Events: wait_timer_started 13:06:05, wait_timer_expired 13:10:05 (240 s), no_show_threshold_reached 13:12:00 (360 s
after the 13:06:00 arrival), termination 13:14:10 (490 s >= 360), fee 8.81 charged and refunded. Fare line,
total_charged and refund_issued_sgd 8.81 (= the gross figure, so NS-08(d) is not engaged); amount_contested_sgd 6.00
(the net fee the driver lost); payout 0.80 x 6.00 = 4.80 in Decimal, a multiple of 0.05 (trap: 0.80 x 8.81 = 7.048).
Also de-echoed: the single unanswered call became two unanswered calls (13:08:20, 25 s; 13:11:15, 30 s) in
in_app_calls, the event log and the claim ("called the rider two times"). Kept, because POL-NS-12 is the case's
subject and needs them: GPS_AUTO, a sparse accuracy-less export, the platform's own arrival and timer events.

### 4061 (FIX), item 3 (optional): the export's code pair gives the sample's 0.6

**Goal applied; the critic's route rejected.** The suggested route (add accuracy-filtered rider fixes so PARTIAL_RECORD
drops) was rejected: a file exported from the driver's device cannot plausibly hold the rider's device fixes, and this
set tags an empty rider_track PARTIAL_RECORD everywhere else (4053, 4055, 4062). Instead the export now also carries
UNVERIFIED_SOURCE (a driver-device file not reconciled against platform telemetry - true of this artifact), weight
0.8 x 0.75 x 0.5 = 0.30. It decides nothing: under NS-12 the export is weighed only for contradiction, the deciding
fact is carried by EV-TRIP-04061 at 1.0, and the GEN-02(2) cap is the maximum of the carriers, 1.0. LOW_SAMPLE_RATE is
kept (4061 is the only case in the set carrying it, and the brief requires it once). UNVERIFIED_SOURCE was not used
anywhere in the set before. Rationale, derivation 8 and deciding_facts carry the 0.3 weight.

### 4063 (FIX): driver message read as promising three more free minutes

**Critic right; applied.** MSG-04063-005 (DRIVER, 08:05:40) now reads "still waiting ya, already more than 3 min,
waiting fee start liao" - true on the record (200 s after the first qualifying fix 08:02:20, 220 s after the tap).
Sender, time and read_at unchanged. NO_ACTION under POL-NS-10(d) unchanged (dwell 385 s > 180).

### 4065 (FIX): driver's excuse asserts NS-06 limb (i) against a MISSING advisory

**Critic right; recommended option applied, alternative rejected.** NS-06(i) says "asserting it against a MISSING
artifact triggers POL-NS-09". The driver's "buses and cars ... honking, I could not hold my position" and "bay very
crowded" assert limb (i)'s premise while EV-ADVIS-04065-01 is MISSING. The better reading (limb (i) only sums separate
in-geofence intervals; he never left) wins, but an EASY case must not depend on winning it. counterparty_statement now:
"She said walking over 5 min, when I reached she still say 2 more min. Peak hour I cannot keep waiting for one
passenger, so I cancelled." (consistent with MSG-002 18:09:00 and MSG-005 18:13:20); MSG-04065-006: "still 2 min ah? I
cannot wait so long leh". Rationale and trap rewritten (impatience is no ground: NS-06 is strict liability; limb (i)
only sums separate intervals; nobody relies on an advisory). The alternative (a present CONGESTION advisory) was
rejected as unnecessary and as adding an advisory-type reading to an EASY case. FULL_REFUND 8.00 unchanged (dwell 95 s
vs 300).

### Items marked OK with no issue

4056, 4059, 4064: no critic items (4059 was changed only by the approach extension above).

## 2. Verification (all re-run after the last change)

- `tmp/ns_r1/make_blueprint.py`: 15 cases, **313 checks, 0 problems**, forbidden words in facts 0. New checks: per
  smoothed case, position-derived speed into the tap fix <= 10 km/h with the tap fix at 0 km/h, and first qualifying
  fix = roll-in fix 10 s before the tap; exact dwell values; 4061 timer = free_wait 240, termination 490 s >= 360,
  export start/end within 45 s of acceptance/termination, no sample figure reused (fee, free wait, threshold, weight),
  gross = net x 6.61/4.50, payout 4.80; 4059 runs measured from the first qualifying fix (60 + 75); an r1 regression
  guard that fails if any pre-r1 phrase survives in a case's facts or intent (old dwell figures, old 4061 figures and
  times, "on hold", "no-show flags on his record", "will start after", "crowd", "PLATFORM-PUBLISHED"); and a guard that
  each smoothed case states its dwell from the first qualifying fix. The one-decimal "quoted figure" check now also
  admits the case's own admissibility weights (needed for 4061's 0.3).
- Mutations, each shown to fail (`tmp/ns_r1/mutate.py`): roll-in at approach speed (ROLL_M 55) -> 32 problems; 4061
  export back to 12:59:40/13:15:50 -> NS-08(a) check and stale guard; 4061 fee 5.00 / free wait 300 -> timer, de-echo
  and payout checks; 4061 key left at 4.00 -> payout check and stale guard; 4061 export weight 0.6 -> de-echo check;
  4059 runs measured from the marker -> run checks and stale guard; 4052 rationale dwell left at 270 -> stale guard.
- `tmp/ns_r1/proto_build.py` on the installed `build/blueprint_ns.json`: validate_case + lint_case + validate_key 0
  problems; `ref/check_set.py --range 4051 4065`: 15 cases, the only failure the expected single-category "both
  categories are required".
- `tmp/ns_r1/verify_r1.py`, independent of common.py (check_set's km with R = 6371.0088, Decimal money): trace
  distances to 3 dp, fare sums, impaired weights as integrity products, NS-07 payouts, FULL_REFUND = contested,
  approach speeds and first qualifying fixes, 4061 timer/threshold/export-span/fee arithmetic, 4059 runs, and the
  reworded texts in the built files: **89 PASS, 0 FAIL**. Run against a build of the r0 blueprint it reports 31 FAIL,
  so it can fail.
- Determinism: identical sha256 under PYTHONHASHSEED 1 and 987.
- ref/ files unchanged (sha256 match tmp/ref_orig.sha).

## 3. plan.json text now superseded (rulings unaffected; not edited, per the convention in design_notes_ns.md section 3)

- 4051 "held it 250 s" -> 260 s from 08:06:50. 4052 "270 s into the dwell" -> 280 s from 19:30:50. 4053 "seven in-radius
  fixes to 21:15:00 ... 200 s after arrival" -> eight fixes from 21:13:50 (70 s); 210 s from the first qualifying fix.
  4057 "held it 420 s" -> 430 s from 07:16:50. 4059 "60 s (18:21:00-18:22:00)" -> 60 s (18:20:50-18:21:50). 4060 tap
  unchanged; dwell at cancellation 80 s.
- 4055 "the rider's appeal to the driver's prior_no_show_flags = 9" -> the rider asks for the driver to be checked.
- 4058 filer_story "payout is being withheld" -> "not in my earnings yet".
- 4061 mechanism / messy_evidence / targets: fee 5.00 -> 6.00 net (8.81 gross), free wait 300 -> 240, threshold 420 ->
  360, timer expiry 13:11:05 -> 13:10:05, export weight 0.6 -> 0.3 (+ UNVERIFIED_SOURCE), payout 4.00 -> 4.80, two calls.
- 4065 counterparty_story "the bay was crowded" -> impatience at peak hour.
- platform_policy.source in plan targets for the eight cases above -> RECORD-PLATFORM.
- `build/plan.json` changed during this session in RD entries 4006 and 4012 only (another agent); NS entries were
  compared and are identical to the copy taken at the start. This revision wrote nothing to plan.json.

## 4. Process note

All work stayed in the workspace (throwaway files under `tmp/ns_r1/`; r0 sources backed up in `tmp/ns_r1/bak/`), with
one exception, disclosed here: the harness saved the over-long output of my own `python3 -c` print of
`ref/no_show.json` to a tool-results file under the session's `~/.claude/projects/.../tool-results/` folder, and I
opened that file with the Read tool to see the rest of my own command output. It held only text printed from
`ref/no_show.json`. No other file outside the workspace was opened, listed, searched or changed; no web access.
