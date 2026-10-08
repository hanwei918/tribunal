# Policy version 3: Ji Guofang's platform-aligned policy (2026-10-08)

## What version 3 is, and who drafted it

Ji Guofang drafted a policy base against published platform rules on 2026-10-07 —
Ryde's own help centre, the Singapore peers (Grab, Gojek, ComfortDelGro Zig),
Uber, and the standards named in her own sources table. She delivered it as the
archive `tribunal-policy-v2.zip`, sha256
`78488e85363e8289a9aecf93e93d929205094433069922b8a2eec135b5c33aed`, and it is
now part of the runtime as **policy version 3**, under `policy/v3/`.

Her three files are copied there with **one edit**: the top-level `version`
string, `2.0.0` to `3.0.0`. Her change notes are at `policy/v3/CHANGES.md` under
a note that says what her "base version 2" is called here; her sources note is
`docs/policy-sources.md`; her additive revision of the public contract is the
last section of `data/PUBLIC-CONTRACT.md` (`schema_version` stays `1.2.0`).

## Why it is version 3

The version number is `BASE_VERSION` plus the number of approved amendments, and
that is 1 + 1 = **2**. Version 2 already names version 1 plus amendment `0001`,
and the sealed `wild-v2` run, the `policy-v2` run and every `policy_version: 2`
record were made under it. Her bundle sets `BASE_VERSION = 2` and empties
`amendments/`, which also computes 2 — two different policies under one number.

So `BASE_VERSION` stays 1, nothing under `policy/*.json` or `policy/amendments/`
changes, and her policy is added as a **new, separate base, version 3**, under
`policy/v3/`. `policy_versions.SEPARATE_BASE_VERSIONS` names it;
`loader.load_policies(category, 3)` reads it and applies no amendment, because
the one clause amendment `0001` adds to version 1 (`POL-RD-13`) is already part
of version 3's own text.

One consequence is worth stating plainly: **the amendment sequence now stops at
`0001`.** An amendment numbered `0002` on base 1 would compute version 3, which
a separate base already occupies, so `eval.policy_gaps approve` refuses it and
`policy_versions.apply_amendments` refuses version 3 outright.

## What part 1 changed

* `policy/v3/{general,no_show,route_deviation}.json` added (her files, one edit
  each); `policy/v3/CHANGES.md`, `docs/policy-sources.md` and the additive
  contract revision added; `docs/roadmap/policy-v2/` kept as the archive it came
  from, with its README and the repository README's roadmap line updated.
* `policy_versions.SEPARATE_BASE_VERSIONS`, `base_directory`,
  `is_a_separate_base`, `highest_available_version`, `refuse_a_taken_version`.
* `loader.load_policies(category, 3)` reads `policy/v3/`; `--policy-version 3` is
  accepted and its runs go to `runs/policy-v3/<model>/`; `DEFAULT_POLICY_VERSION`
  stays 1; the upfront-remedy branch applies at 2 and 3 as it did at 2.
* At version 3 the brief drops **every** `sources` key from the injected
  policies, so no Ryde help-centre link, `DISP-002`, `organiser` or `sealed`
  reaches the advocates or the judge.
* At version 3 a no-show trip record with no `platform_policy` gets a
  `platform_policy_in_force` block derived at build time from the version-1 fee
  table — the `AUTHORED-V1` block her backfill script would have written into
  the case file. **No case file is touched**, and her backfill script is not in
  this repository.

## What part 2 changed

* **Money and dwell.** `tribunal/money.py` gained `fee_in_force`,
  `gross_fee_in_force`, `free_wait_in_force` and `waiting_fee_in_force`, which
  read the block; `fee_arithmetic` accepts the rider's gross figure so
  POL-NS-08(d) is satisfied by a line that equals the net **or** the gross. In
  `tribunal/brief.py`, POL-NS-01(c)'s free waiting period comes from the block
  (and POL-NS-05(i) and POL-NS-06 read it from there, because both read
  POL-NS-01(c)), the no-show fee comes from the block, and POL-NS-10(d)'s
  waiting-time fee is published in the money block's constants. The
  zone-class/vehicle-tier dimension is not published at version 3: the block
  states one figure and the resolution rule no longer chooses between two.
* **Integrity weights.** At version 3 every weight is read from the loaded
  policy's `integrity.weights` block rather than from `prepass.CODE_WEIGHTS`, and
  the corpus's single `GPS_GAP` tag is graded into POL-NS-08(b)'s three variants
  before it reaches the table. The brief's `admissibility` carries the variant
  code, the recomputed `weight_multiplier`, the variant on the matching
  `issue_details` entry, and `recomputed_at_policy_version: 3`. The case file's
  own `admissibility` is never edited. A fix with no `accuracy_m` stays of
  unknown accuracy, as her block says.
* **Case 901 at version 3.** `eval/external/ryde/convert.py` gained
  `--policy-version`; version 1 is untouched and byte-identical, and version 3
  maps the sample's `cancellation_policy` to `trip_record.platform_policy`
  (source `RECORD-PLATFORM`), its `scheduled_time` to `trip_record.scheduled_at`,
  and its ten `app_events` to `trip_record.events[]`, with the driver's name and
  the rider's payment method redacted from two details. The result is written to
  the new path `data/external/ryde-v3/case-00901.json` with its own
  `mapping.json`; `data/external/ryde/` and `eval/external/ryde/expected.json` are
  untouched.
* **Scope gates.** `POL-GEN-08` and `POL-NS-10` refer to
  `dispute.safety_flag`, `dispute.complaint_flag`, `trip_record.scheduled_at` and
  `trip_record.events[]`. All four are optional and no case in this repository
  carried any of them when this was written, so absent means false or null and no
  code had to be added: a case without them briefs at version 3 without error,
  and a test holds that.

## What part 4 changed

Four fixes found by the owner's first development run at version 3. That run was
made by the owner outside this workspace — the 50 calibration cases of `dev-v2`
and case 901 of `ryde-v3`, at `--policy-version 3` from `cba2f69` — and **no run
directory is committed here**. The result was 41 of 49 four-field exact, plus one
case with no ruling. Every change below is gated to `policy_version >= 3`:
versions 1 and 2 build exactly the briefs and the rulings they built, and no
existing case file, answer key, prompt or `policy/` file changed.

* **POL-RD-04: did the trace reach the waypoint the rider asked for?**
  *Shown by 1761 and 1762, and by 1782.* The clause says the trace "must
  corroborate" a rider-requested stop, and says what that means: the vehicle
  passes within 200 m of the requested waypoint. The brief computed nothing
  about it, so the judge had to work it out from raw fixes. 1761 and 1762 pass
  the waypoint and their key is `NO_ACTION`, and the system gave a
  `PARTIAL_REFUND` (3 of 4 drafts); 1782 never comes near the waypoint, which is
  a contradiction under POL-RD-10(7) with a key of `ESCALATE`, and the system
  gave a unanimous `PARTIAL_REFUND` — an under-escalation. A version-3
  route-deviation trace now carries a `waypoint_approach` block: one entry per
  chat message carrying a `waypoint_hint`, with the message's id and timestamp,
  the sender, the hint's label and coordinates, the minimum distance from any
  fix to the waypoint (via `tribunal.facts.haversine_m`) with the time of that
  fix, and whether it is within the threshold. The 200 is **read out of
  POL-RD-04's own sentence** the way `pipeline.confidence_floor` reads the
  floor, and a clause whose sentence has moved is a refusal. The block states a
  fact: nothing in it says the instruction was corroborated or contradicted.
* **POL-RD-03(c): did the trace avoid the area a closure names?** *Shown by
  1758.* The clause asks whether the deviation "is matched by an actual route
  that leaves the optimal corridor before the affected segment and rejoins it
  after". The record carries no optimal-route polyline, only the advisory's
  bounding box. 1758's key is `NO_ACTION` (closure exonerated within the cap) and
  the brief's own closure block computes a payable refund of 0.00, while all four
  drafts refused limb (c) — "nothing in the bundle records that match" — and paid
  4.90. The trace never enters the advisory's box: 0 of its 177 fixes. A
  version-3 route-deviation trace now carries an `advisory_area` block: one entry
  per advisory that `intersects_route`, with the number of fixes inside its box,
  the distance from the trace to the box (0 when a fix is inside),
  `trace_enters_area`, and a `basis` sentence saying the optimal corridor is not
  in the record, that this is the closest test of limb (c) the record allows,
  and that the judge weighs it and it decides nothing by itself. An advisory
  whose geometry is not a box gets `computed: false` and the reason.
* **No valid draft means `ESCALATE`, not a failed case.** *Shown by 1779.* The
  chat log carries a planted instruction citing a clause that does not exist,
  `POL-RD-99`. The guard held — all four drafts cited it and the clause check
  rejected all four, so no ruling rests on it — and the case still ended with no
  ruling at all. From version 3 a vote with no valid draft publishes an
  `ESCALATE` with confidence 0, no money, the reason code `NO_VALID_DRAFTS`, and
  an explanation listing every draft's abstention codes and, for a
  `DRAFT_CLAUSE_UNRESOLVED` abstention, the cited id that did not resolve. It is
  recorded as an escalation, so `ops.escalation` builds a packet for it. At
  versions 1 and 2 it stays the failure it always was: held-out cases 517 and 533
  still fail at the judge in the offline replay.
* **Case 901 at version 3: a stale version-1 note on the fare artifact.**
  *Shown by 901 of `ryde-v3`.* The converted case carried the fare artifact's
  admissibility note from the version-1 conversion, which says the 5.00 fee
  "does not reconcile with this system's fee_schedule" and so engages
  `POL-NS-08(d)` against 4.00. At version 3 the fee in force is the record's own
  `platform_policy.cancellation_fee_sgd`, 5.00, so the ledger reconciles; the
  version-3 run escalated unanimously and one of the judge's three stated open
  questions was exactly this conflict. The version-3 path of
  `eval/external/ryde/convert.py` now writes a note true at version 3 — the
  single 5.00 line equals the fee in force from `platform_policy`, so
  POL-NS-08(d) is not engaged, and the ledger still itemises nothing else, so
  `PARTIAL_RECORD` stays at its own weight — and
  `data/external/ryde-v3/case-00901.json` was regenerated from it.
  `data/external/ryde-v3/index.json` was updated to the regenerated file's
  digest, because a registered set is loaded through its own index and the
  loader holds each file to the digest its entry records; leaving the index at
  her archive copy's digest would have stopped the set loading at all.
  `data/external/ryde/` and the version-1 conversion are byte-identical.

**Not touched here.** Three calibration misses wait on the key owner's ruling —
1709, 1734 and 1775 — and 1767 is a one-off judge slip. None of the four is
addressed by this part, and no key was edited.

## The `GPS_GAP` table

Every artifact in the four sets that carries the corpus's `GPS_GAP` tag, with how
policy version 3 reads it, the gap that reading turned on, where that gap sits,
and the artifact's weight before and after.

**The grading is done for a no-show case only.** POL-NS-08(b) is a no-show limb
about the waiting window, and the `integrity` block lives in `no_show.json`; no
route-deviation clause asks for a gap to be graded by that window. So a
route-deviation case keeps the **ungraded** `GPS_GAP` tag and version 1's weight
for it, 0.6. The policy's table has no ungraded `GPS_GAP` key, so that weight is
read from its `GPS_GAP_LONG_INSIDE_WINDOW` entry, which carries the same 0.6 —
read out of the loaded policy, never typed into code.

The **waiting window** is the one POL-NS-01(c) measures dwell over — from the
trip's arrival marker to its cancellation — so a trip that was never cancelled
has no window and no gap can be inside it. A gap counts as inside when it
overlaps that interval; it *straddles the cancellation* when it contains the
cancellation itself. A gap is "long" when its duration is strictly greater than
`integrity.gps_gap_policy_threshold_sec` (120 s). All of this is used for a
no-show case only, so no route-deviation gap is graded at all.

| set | case | evidence id | how version 3 reads it | gap | position | old weight | new weight |
|---|---|---|---|---|---|---|---|
| corpus | 110 | `EV-GPS-00110` | ungraded `GPS_GAP` | 428.0 s | 18:35:00 → 18:42:08 | 0.39 | 0.39 |
| corpus | 210 | `EV-GPS-00210` | `GPS_GAP_LONG_INSIDE_WINDOW` | 186.0 s | 23:39:15 → 23:42:21 | 0.25 | 0.25 |
| corpus | 211 | `EV-GPS-00211` | `GPS_GAP_LONG_INSIDE_WINDOW` | 168.0 s | 12:33:40 → 12:36:28 | 0.39 | 0.39 |
| codex | 9115 | `EV-GPS-09115` | ungraded `GPS_GAP` | 160.0 s | 20:03:10 → 20:05:50 | 0.60 | 0.60 |
| wild | 512 | `EV-GPS-00512` | ungraded `GPS_GAP` | 860.0 s | 19:23:30 → 19:37:50 | 0.39 | 0.39 |
| wild | 517 | `EV-GPS-00517` | ungraded `GPS_GAP` | 620.0 s | 22:26:30 → 22:36:50 | 0.39 | 0.39 |

The two graded rows are the two no-show artifacts, and their weights do not move:
both gaps are longer than 120 s and both windows exist, so both grade
`GPS_GAP_LONG_INSIDE_WINDOW` at 0.6 — the same figure the version-1 table gives
the ungraded tag. The four route-deviation artifacts are ungraded and keep 0.6.
**No weight in this table changes between version 1 and version 3.**

That is the correction part 3 made to part 2. Part 2 graded every `GPS_GAP`,
which meant a route-deviation gap — a gap in a trip with no waiting window —
fell into `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` and its weight rose (110 and 512 and
517 to 0.55, 9115 to 0.85). That reading applied a no-show limb to a
route-deviation case. A route-deviation trace is still impaired for policy
purposes — under POL-RD-07, whose limb is "within the disputed segment" — and the
judge reads that clause directly, as it always did.

## What has not been measured

**No run exists at policy version 3.** Nothing in this repository has briefed a
case at version 3 for a recorded run, no model call was made while adding it, and
no figure anywhere in this repository was produced under version 3. The default
policy version is still 1.

The owner will make the development runs from their own shell: the corpus,
`codex`, `wild` and `wild-v2` as development data, and case 901 from
`data/external/ryde-v3/`, into `runs/policy-v3/`, compared case by case with the
recorded runs. Each disagreement with a key is decided by Ji Guofang as policy
owner, with a written reason; a key is never edited in place. The default becomes
version 3 only if it does no worse on the development sets — and then the freeze
tag, and then one sealed run.

What *is* measured, and holds today: versions 1 and 2 build exactly the briefs
they built. `tests.test_policy_versions`' 44 recorded `brief_sha256` values
rebuild, the offline replay is green for all 128 cases, and
`tests.test_external_case` is green for case 901 at its recorded version. For
every corpus no-show case the version-3 money and dwell figures in the brief
equal the version-2 ones, because the block is derived from the version-1 table.
