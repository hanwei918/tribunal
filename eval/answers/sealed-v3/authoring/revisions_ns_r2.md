# Revisions r2: NO_SHOW_CHARGE blueprint (4051-4065), internal

Applies `build/critique_ns_r2.json` to `build/blueprint_ns.json`. Answer-bearing; stays under `build/`.

## 0. Outcome

- **Every planned ruling, amount, referral list, filer, channel and difficulty is unchanged.** No case needed an
  "honest alternative", so `build/plan.json` was **not edited** (sha256 `f2d5e21b...a3a8ea` before and after). Set
  tally unchanged: FULL_REFUND 4, NO_ACTION 3, DRIVER_COMPENSATION 5, ESCALATE 3 (2 evidence, 1 policy); EASY 4,
  HARD 6, REVERSAL 3, INDETERMINATE 2; DRIVER 7, RIDER 8.
- The one key field that changed is 4055's `governing_clauses` (POL-NS-04 removed; see 4055 (b)). Nothing that
  decides the ruling or the money moved.
- `build/blueprint_ns.json` sha256: before `6fa781b3c90b57eaa3c8389b82ab98a87f148914a65a1b5995c31e0d02be9e7a` (r1),
  after `69dc31de26c17faa5de1254c588d2ed34eeaab28507590a50329b0f6c51e78d3`.
- Cases changed: 4058 (FIX), and the optional items in 4055, 4061, 4062 and 4065. The other ten built case files are
  byte-identical to r1 and their keys are identical.
- The blueprint is regenerated, not hand-edited. Sources are in `tmp/ns_r2x/`, with the r1 copies in
  `tmp/ns_r2x/bak/ns_r1/` and the r1 blueprint in `tmp/ns_r2x/bak/blueprint_ns_r1.json`. The r2 sources were synced
  into `tmp/ns/`; re-running `tmp/ns/make_blueprint.py` reproduces the r2 file byte for byte (checked). The edits are
  scripted in `tmp/ns_r2x/apply_r2.py` (counted, function-scoped replacements) plus the `R2_*` constants and re-timed
  legs in `geo_ns.py`. `tmp/ns_r2/` holds the critic's own scripts and was not touched.

## 1. Decisions, item by item

### 4058 (FIX): approach into the BUTTON tap sits on POL-NS-05's speed line

**Critic right; applied, but with a different, physically consistent profile than the critic's example.**

Checked against the policy. POL-NS-05 makes the marker false where the trace "places the driver more than 300 m from
the pickup pin, or shows the driver travelling at 15 km/h or above" at the arrived event's timestamp. The fix at
23:42:00 is the tap fix: 0 s offset, 17.2 m, 0 km/h. On the clause's own test the marker is good. But the r1 trace had
the 23:41:50 fix reporting 30 km/h at 45.0 m, and 41.0 m in the 10 s into the tap fix (14.8 km/h position-derived,
0.2 km/h under the line). With both fixes' accuracies (8.3 m and 8.9 m) added to that gap it is 21.0 km/h. A reader who
matches the marker by finite difference, or who reads the 30 km/h fix, can call the marker false. The ruling would
still be ESCALATE (NS-05(iii) -> NS-01 -> NS-07 -> NS-09(d)), but a "POL-NS-05(iii) false-arrival" referral could be
attached, which the key does not carry. The r1 approach was also implausible: it slowed to 16 km/h, sped up to 32 km/h,
then stopped in under 45 m. BRIEF section 6 says to avoid knife-edge numbers, and section 3 requires plausible speeds.
So the item is valid.

The critic's example numbers were not used, because they are inconsistent. Going from about 90-120 m out at
23:41:40 to about 35-40 m out at 23:41:50 is 20-29 km/h over those 10 s, not "<= 18". The constraint behind them is
that the radius is 150 m (AIRPORT) and the car stops 17 m from the pin. To keep 23:41:30 outside 150 m while doing
<= 18 km/h over the last 20 s, the 23:41:30 leg would need about 33 km/h after 26 km/h. That is a speed-up before
braking. Instead the car now decelerates monotonically. The path, its waypoints and the stop are all unchanged. Only
the timing along the final lane changes: the main route ends at 23:41:20 and four 10 s legs follow.

| fix | r1: distance to pin / reported / position-derived into it | r2 |
|---|---|---|
| 23:41:20 | 231.8 m / 17 / 21.2 km/h | 167.3 m / 23 / 21.9 km/h |
| 23:41:30 | 187.2 m / 19 / 16.1 km/h | **105.7 m** / 18 / 22.4 km/h |
| 23:41:40 | 133.3 m / 32 / 20.2 km/h | 55.4 m / 12 / 18.7 km/h |
| 23:41:50 | 45.0 m / **30** / 32.3 km/h | 23.2 m / **6** / 12.7 km/h |
| 23:42:00 tap | 17.2 m / 0 / **14.8 km/h** | 17.2 m / 0 / **5.8 km/h** (12.0 with both accuracies added) |

Consequence, stated in every affected text. The first qualifying fix (a run of three within 150 m with accuracy
<= 25 m) is now **23:41:30, 105.7 m** (was 23:41:40, 133.3 m). The fix before it, 23:41:20, is 167.3 m out (17 m
outside). So the dwell measured as POL-NS-01(c) measures it is **600 s** to the 23:51:30 termination (was 590 s). From
the marker it is still 570 s. Margins against the policy:

- NS-01(b): qualifying fixes before the marker hold. (c): 600 s >= 300, and the termination 570 s after the marker
  is >= 480 (or 600 s if read from the first fix).
- NS-05: tap fix 0 s / 17.2 m / 0 km/h. Every reading of the fix-to-fix speed into it is under 15 km/h.
- NS-08: (a) 0 s; (b) 58 window fixes at 10 s; (c) and (d) are unchanged.
- NS-04, NS-07 counters (5 of 54) and the anti-farming escalation are unchanged. ESCALATE (policy), null money and no
  referral are unchanged.
- Other effects: max position-derived speed 33.8 km/h (Airport Boulevard, 23:39:20-23:39:30); trace_distance_km
  1.575 (recomputed 1.5752980 km with check_set's km; unchanged at 3 dp). Every fix from the tap onward, every rider
  fix and every accuracy value is identical to r1 (same seeded draws).

Texts changed: GPS_TRACE notes ("the first fix within 150 m is 23:41:30 (105.7 m)", plus the r1-style sentence "The
fix before the arrival marker (23:41:50) lies 23.2 m from the pickup pin at 6 km/h."). Rationale ("qualifying fixes
from 23:41:30, 105.7 m out and slowing"). deciding_facts ("in 150 m from 23:41:30 (600 s to the termination)"). Derivation 2
(23:41:30, 105.7 m, 600 s) and derivation 3 (the fix 10 s before the marker and the 5.8 km/h into it). Design checks
added: into the tap <= 10 km/h with the tap at 0 km/h; the fix 10 s before reports <= 12 km/h; first qualifying fix
23:41:30 with the fix before it >= 10 m outside 150 m; dwell from it 600 s.

### 4055 (optional) (a): approach into the 09:22:00 tap

**Applied.** This is the same defect class as 4058, and it has the same consequence for the key. The r1 tap fix had
12.7 km/h position-derived into it, and 16.5 km/h with both accuracies added (>= 15). A reader who called the marker
false would attach an NS-05(iii) referral to the same 3.60, and the key's referrals are []. The approach now
decelerates (28.0 -> 23.8 -> 23.1 -> 15.4 -> **8.9** km/h position-derived). The fix 10 s before the tap reports
6 km/h (was 10). With accuracies added it is 12.7 km/h. The critic asked to keep a qualifying fix inside 120 m before
09:22:00, and it is kept. The first qualifying fix stays **09:21:40** (now 76.4 m, was 83.7 m). The fix before it
(09:21:30) is 140.6 m out, 20 m outside the LARGE_VENUE radius. Dwell from the first qualifying fix stays 360 s
(340 s from the marker). The tap fix and the hold are unchanged. trace_distance_km 4.029 -> **4.030** (recomputed
4.0295818). The main route was re-weighted so the car arrives at 26-28 km/h on Simei St 4 and slows into the
driveway; r1 sped up from 11 to 20 km/h inside the driveway. Texts: the GPS notes figure (76.4 m) and fix-before-marker
sentence, and derivation 3 (computed). The rationale needed no change (it names 09:21:40 only).

### 4055 (optional) (b): governing_clauses lists POL-NS-04

**Applied.** POL-NS-11 says that where limb (c) cannot be run, "POL-NS-04 cannot exonerate the rider, and the dispute
is decided under the remaining clauses". By the amendment's own words, NS-04 is not a deciding clause here. The key
now lists POL-NS-11, POL-NS-01, POL-NS-07 and POL-GEN-01. POL-NS-01 and POL-NS-07 license DRIVER_COMPENSATION.
POL-GEN-01 is kept, as the critic suggested and as in 4051, because the rider's request to "check this driver" is
discarded under it. NS-04 is still discussed in the derivation and other_clauses, where the rider's argument is
answered. The plan's `targets.governing` for 4055 still lists POL-NS-04 (superseded text, section 3).

### 4055 (optional) (c) and 4052 (optional): rider-side fee line is the net 4.50 under a block naming gross 6.61

**Rejected; kept as a deliberate net-line variant.** The policy allows either figure.
`fee_schedule.resolution_rule` says the line "may equal either the net or the gross figure", and POL-NS-08(d) is
engaged only when the line equals neither. Each case's record is internally consistent: the fare line, the events
("Cancellation fee SGD 4.50 charged") and the SYSTEM chat message agree. The "two billing behaviours" are visible
only across cases, and the system under test sees one case at a time. The variant does test something: a reader who
insists the line must equal the gross because a gross is named would wrongly impair the fare artifact under NS-08(d).
The gross-line payout trap is already live elsewhere: 4061 has an 8.81 line against a 6.00 net payout of 4.80, and
4051/4060 refund 6.61 gross. Changing 4052 and 4055 would remove that probe for no policy gain.

### 4061 (optional) (a): timer event wording echoes the organisers' sample

**Applied.** `ref/case-00901.json` does use the sentence "Rider had not boarded." in its wait_timer_expired event.
New details: wait_timer_started "Free waiting period 240 s running (to 13:10:05)."; wait_timer_expired "Free waiting
period ended at 13:10:05; no boarding recorded." The times, the event order and every other field are unchanged.
POL-NS-12 still has its carrier: GPS_AUTO, an arrival event that states 16 m and 0 km/h, a timer of 240 s, and expiry
13:10:05 before the 13:14:10 termination. The event order (arrival, notify, timer, call, expiry) is kept. It is the
chronological order of the mechanism POL-NS-12 describes, not something copied from the sample. Key unchanged.

### 4061 (optional) (b): spread of RYDE_X cancellation fees across the set

**Rejected.** `resolution_rule` reads the fee from each record's platform_policy, so a fee that varies by record is
policy-legal. The spread is deliberate: it makes a reader take the figure from the record rather than from
`defaults`. As with the net-line note, the spread is visible only across cases. Changing it would change payouts in
three keys (4057 3.20, 4061 4.80, 4064 4.40). That alters answers to fix a realism point that no single case shows.

### 4062 (optional): GPS note "longest run ... is 3"

**Note wording applied; the weight change was rejected.** The whole trace has a 4-fix run (12:32:50-12:33:20) that
starts before the marker, and the window run is 3. Both were recomputed from the built file. The note now reads "The longest run of
consecutive fixes within 50 m in that window is 3". Derivation 3 says "longest in-window near run 3" for the same
reason. The weight stays **0.38**. FOUNDATION.md defines `weight_for` as the product "2 dp", and the same convention
is used across the set (RD side included) through `build/common.py`. The product is 0.375 (0.5 x 0.75), and
ROUND_HALF_UP gives 0.38. Derivation 3 already states "0.375, written 0.38". Both values are far below 0.70, so
nothing moves. Changing the convention would mean editing the shared common.py.

### 4065 (optional): approach into the 18:12:50 tap; fix 18:12:20 speed against its displacement

**Applied.** In r1 the speed into the tap was 13.6 km/h after a 13 km/h fix (19.7 with accuracies added), and the
18:12:20 fix reported 31 km/h after 14.6 km/h of displacement. A false-marker reading would give NS-05(i), the same
FULL_REFUND with no referral, so the outcome was never at risk. It was fixed for plausibility, as r1 did for 4053,
4059 and 4060. The car now crawls along Bedok North Road (14-17 km/h, peak hour) and turns onto the interchange
access road at 28-33 km/h. It then slows into the bay: 32.7 -> 17.3 -> **6.6** km/h position-derived into the tap.
The fix 10 s before reports 6 km/h, and with accuracies added the speed into the tap is 12.7 km/h. The 18:12:20 fix
reports 32 km/h against 31.6/32.7 km/h on either side. The first qualifying fix stays **18:12:30** (now 76.3 m at
20 km/h, was 98.3 m at 27 km/h). The 18:12:20 fix is 164.4 m out (was 177.7 m). The dwell stays 95 s. FULL_REFUND
8.00 is unchanged. The r0 design note ("a tap at 18:12:30 would have made the marker false") is still true: the fix
moves at 20 km/h, which is >= 15. trace_distance_km 2.410 (recomputed 2.4096764; unchanged). Texts: the rationale's
"98.3 m ... 177.7 m" became the computed 76.3 m and 164.4 m; the GPS notes are computed and gained the fix-before-marker
sentence.

### Items marked OK with no fix

4051, 4053, 4054, 4056, 4057, 4059, 4060, 4063 and 4064 had no fix item (4052's only item is above). Their case files
and keys are byte-identical to r1.

## 2. Verification (all re-run after the last change, on the installed file)

- `tmp/ns_r2x/make_blueprint.py` (synced to `tmp/ns/`): 15 cases, **337 checks, 0 problems**, forbidden words in facts
  0. The 24 new checks: approach checks for 4055/4058/4065 (speed into the tap <= 10 km/h with the tap at 0; the fix
  10 s before reports <= 12 km/h and < 20 km/h into it; the first qualifying fix at its designed time with the fix
  before it >= 10 m outside the radius); fixed dwells (4055 360 s, 4058 600 s); 4055's clause list; and an r2
  stale-phrase guard ("from 23:41:40", 133.3, "590 s", 83.7, 98.3, 177.7, "Rider had not boarded", "within 50 m is n").
- Mutations, each shown to fail (`tmp/ns_r2x/mutate_r2.py`, 10 of 10 reported problems): 4058 roll-in of 45 m; 4058
  outer fix pulled inside 150 m; 4058 r1-like fast leg; 4055 roll-in of 38 m; 4055 NS-04 back in the clause list;
  4065 roll-in of 38 m; 4065 rationale hard-coded to 98.3; 4061 sample sentence restored; 4062 note without "in that
  window"; 4058 rationale hard-coded to 23:41:40.
- `tmp/ns_r2x/proto_build.py` on the installed `build/blueprint_ns.json`: validate_case + lint_case + validate_key 0
  problems; `ref/check_set.py --range 4051 4065`: 15 cases, the only failure the expected single-category "both
  categories are required".
- `tmp/ns_r2x/verify_r2.py` does not use common.py or the design scripts. It uses check_set's km with R = 6371.0088
  and Decimal money, and it re-reads the built files. It checks: trace distances to 3 dp, fix-for-fix identity with
  r1 from the tap onward, the rider tracks and accuracies, NS-05 at the tap, the approach speeds (with and without an
  accuracy allowance), reported against position-derived speeds, a decelerating last 40 s, the first qualifying fix
  and the fix before it, continuity and the dwells, NS-08(b), and the texts that quote the figures. It also checks
  that rulings, money, referrals and difficulty are unchanged, the 4058 NS-01(c)/NS-07 arithmetic, 3.60 = 0.80 x 4.50
  and 8.00 = contested = fee line in Decimal, fare sums, the 4061 wording with its NS-12 carrier intact, the 4062 run
  (3 in the window, 4 over the whole trace) and the weight 0.375 -> 0.38, and that the ten untouched cases are
  byte-identical. Result: **139 PASS, 0 FAIL**. Run on the r1 build it reports 21 FAIL, so it can fail.
- Trace distances sit 0.08-0.20 m from a 3-dp rounding edge in metres (4055 4029.58 m, 4058 1575.30 m, 4065
  2409.68 m). That is inherent to rounding: across the set the margins are 0.02-0.42 m. An atan2 haversine agrees
  with check_set's to 1e-7 km, so no written value is at risk.
- Determinism: identical sha256 under PYTHONHASHSEED 1 and 987.
- ref/ files unchanged (sha256 match `tmp/ref_orig.sha`).

## 3. plan.json text now superseded (rulings unaffected; not edited, per design_notes_ns.md section 3 convention)

- 4055 `targets.governing` still lists POL-NS-04. The key now omits it (section 1, 4055 (b)).
- 4058: the plan has no approach figures. design_notes_ns.md section 3 said "4058 23:41:40", and it is now annotated
  with 23:41:30.
- 4065: the plan's mechanism wording ("first in-radius fix ... 18:12:30 ... 95 s") is still exact.
- `build/plan.json` sha256 is `f2d5e21bbd080e7fe2d01c58d40af59f5b6a7f6f589cca60d925e6b3c0a3a8ea` before and after.
  This revision wrote nothing to it.

## 4. Process note

All work stayed in the workspace. Throwaway files are under `tmp/ns_r2x/`, with r1 sources and the r1 blueprint
backed up in `tmp/ns_r2x/bak/`. The r2 sources were synced into `tmp/ns/`. Outside `tmp/` this revision wrote only
`build/blueprint_ns.json`, `build/design_notes_ns.md` (section 7 added, three inline notes) and this file. There is one
exception, disclosed as r1 did. The harness saved the over-long output of two of my own commands (printing
`ref/no_show.json`) to a tool-results file under the session's `~/.claude/projects/.../tool-results/` folder, and I
opened one of those files with the Read tool to see the rest of my own command output. It held only text printed from
`ref/no_show.json`. No other file outside the workspace was opened, listed, searched or changed, and there was no web
access.
