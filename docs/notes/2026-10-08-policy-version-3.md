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

## What part 5 changed

Two items, from the owner's second sheet. As in part 4, every change is gated so
that **versions 1 and 2 build exactly the briefs and the rulings they built**; no
case file or key of any other set, no prompt and no `policy/*.json` file changed.

### 1. A route-deviation `GPS_GAP` is graded by POL-RD-07's own limbs

Part 2 graded every route-deviation gap by the no-show waiting window, which
turned it into a *short* gap and **raised** its weight; part 3 left every
route-deviation gap ungraded at version 1's 0.6. The key owner ruled both wrong
for case 1775: the clause that owns a route-deviation trace is **POL-RD-07**, and
its own limbs grade the gap.

At version 3, for `ROUTE_DEVIATION` only, the tag is now graded:

* **short** — `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW`, weight 0.85 — when **every** gap
  between consecutive fixes in the trace is within limb (a)'s limit **and** no
  straight-line jump between consecutive fixes exceeds limb (b)'s;
* **long** — `GPS_GAP_LONG_INSIDE_WINDOW`, weight 0.6 — otherwise. That is
  version 1's weight for the tag.

Both limits are **read out of POL-RD-07's own sentence** ("a gap of more than 90
seconds between consecutive fixes", "a straight-line jump of more than 500 m
between consecutive fixes") the way `brief._waypoint_threshold` reads POL-RD-04's
200 m, and both weights are read from `integrity.weights`. Nothing is typed, and
a clause whose sentence has moved is a **refusal** (`LoaderError`), not a default:
a limit written into `tribunal/` would be a policy number hard-coded there, and a
silent default would grade every gap short. The reading is taken over the **whole
trace** — the record does not mark the "disputed segment" — so every interval
between consecutive fixes is read; the gaps and the jumps are computed from the
trace's own points, with the recorded `gaps` summary as the fallback.

A **no-show** case is untouched: it keeps part 2's grading by the waiting window
and POL-NS-08(b)'s own 120 s threshold. The two readings cannot cross, because the
route-deviation limits are read only for a `ROUTE_DEVIATION` case.

**The tests.** `tests/test_brief.VersionThreeGapGradingTests` (12 tests) holds the
rule. Shown red against `dac357f`'s `tribunal/` — `FAILED (failures=4, errors=9)`,
the four failures on the four route-deviation artifacts still carrying the
ungraded tag and the nine errors on the tests that name `POL_RD_07`, the limits
reader and the graded variant — and green with the change in place.

Where it shows:

| set | case | category | evidence id | reading | gap | jump | weight |
|---|---|---|---|---|---|---|---|
| dev-v2 | 1732 | NO_SHOW | `EV-GPS-01732` | `GPS_GAP_LONG_INSIDE_WINDOW` | 199.0 s | — | 0.39 |
| dev-v2 | 1736 | NO_SHOW | `EV-GPS-01736` | `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` | 60.0 s | — | 0.85 |
| dev-v2 | 1775 | ROUTE_D | `EV-GPS-01775` | `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` | 40.0 s | 0.40 km | 0.85 |
| dev-v2 | 1776 | ROUTE_D | `EV-GPS-01776` | `GPS_GAP_LONG_INSIDE_WINDOW` | 100.0 s | 1.00 km | 0.60 |
| dev-v2-ext | 2732 | NO_SHOW | `EV-GPS-02732` | `GPS_GAP_LONG_INSIDE_WINDOW` | 195.0 s | — | 0.39 |
| dev-v2-ext | 2736 | NO_SHOW | `EV-GPS-02736` | `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` | 60.0 s | — | 0.85 |
| dev-v2-ext | 2756 | NO_SHOW | `EV-GPS-02756` | `GPS_GAP_LONG_INSIDE_WINDOW` | 197.0 s | — | 0.39 |
| dev-v2-ext | 2760 | NO_SHOW | `EV-GPS-02760` | `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` | 60.0 s | — | 0.85 |
| dev-v2-ext | 2825 | ROUTE_D | `EV-GPS-02825` | `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` | 40.0 s | 0.40 km | 0.85 |
| dev-v2-ext | 2826 | ROUTE_D | `EV-GPS-02826` | `GPS_GAP_LONG_INSIDE_WINDOW` | 100.0 s | 1.01 km | 0.60 |
| dev-v2-ext | 2849 | ROUTE_D | `EV-GPS-02849` | `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` | 40.0 s | 0.40 km | 0.85 |
| dev-v2-ext | 2850 | ROUTE_D | `EV-GPS-02850` | `GPS_GAP_LONG_INSIDE_WINDOW` | 100.0 s | 1.00 km | 0.60 |

The six route-deviation rows that turn on the new limb are 1775, 2825 and 2849
(short) and 1776, 2826 and 2850 (long); each weight equals the one the case file
itself declares, so nothing the sets already recorded moves. Corpus 110, codex
9115, wild 512 and wild 517 keep the weights part 3 gave them, because every one
of their gaps exceeds 90 s. A fixture that keeps 1775's 40 s gap but moves one fix
600 m north of the fix before it grades **long** — limb (b) alone decides it.

### 2. The revised development sets

The bundle `~/Desktop/Tencent /guofang-ui-v2/tribunal-dev-v2-rev2.zip`, sha256
`f446acb20844e3102eb21f2feb472914f31ff112d39bb061a5f80b57afb2c2b4`, was checked
against that digest, unpacked outside the repository, and copied in. Its
top-level Chinese note is left out, as the language rule requires. **218 files
were installed byte for byte and every one was checked by sha256**; six files
carry the bundle's bytes **plus** the edit part 3 made and this sheet keeps:

| file | what was re-applied |
|---|---|
| `data/external/dev-v2/README.md` | "policy version 3 (drafted as base version 2)" for "policy base version 2" |
| `data/external/dev-v2-ext/README.md` | the same phrase |
| `eval/answers/dev-v2/DATASHEET.md` | the same phrase |
| `eval/answers/dev-v2-ext/DATASHEET.md` | the same phrase |
| `eval/answers/dev-v2/README.md` | the same phrase, twice |
| `tests/test_dev_v2.py` | part 3's guard classes (the bundle ships the base file without them) |

`tests/test_dev_v2.py` is therefore byte-identical to `dac357f`'s: the bundle's
first 208 lines are the same 208 lines, and the guards part 3 appended are kept.

**What the revision changes.**

* **Key corrections ruled by the key owner.** 1709 and 1710 (and their variants
  2709 and 2710) now expect the `POL-NS-05(ii)` false-arrival referral, which the
  system produced: the arrival marker is stamped more than 300 m from the pin and
  no in-geofence fix exists anywhere, so limb (ii) applies. 1775 is regenerated
  with a short gap and now expects `PARTIAL_REFUND` **6.35**, not 4.50.
* **Regeneration.** The generator was re-run (seed unchanged), so **137 case files
  changed in random detail**: `dev-v2` **1714** and **1775–1790**, and all **120**
  of `dev-v2-ext`. Some keys followed: 1779 now expects **5.70**, and 53
  `dev-v2-ext` keys changed. The set's `index.json` was updated with every
  regenerated file's digest, because a registered set is loaded through its own
  index and the loader holds each file to the digest its entry records.
* **`eval/synth/verify_dev_set.py`.** The bundle's checker is installed byte for
  byte, so part 3's `POLICY_VERSION = 3` constant is **not** carried over. That
  costs the check nothing here: the revised checker's derivation reads the
  record's own `platform_policy` block rather than the brief's in-force block, and
  it was measured at **both** the default version and version 3 before the choice
  was made — 80 of 80 and 120 of 120 either way. The bundle also brings the
  derivation the key owner added (the POL-NS-05(ii) referral and the
  `straight_line_km > 0.5` limb of the gap test), which part 3's copy did not have.

**A run made on the first revision is not comparable for those 137 cases.** Any
result produced against `tribunal-dev-v2-rev1.zip` reads a different case file for
each of them, so its per-case agreement is evidence about the old bytes and must
not be compared with a run made against these.

**The checks.**

```
cases agreeing with the key on all four fields: 80 of 80
cases agreeing with the key on all four fields: 120 of 120
```

`python3 -m unittest tests.test_dev_v2` reads **36 tests, OK**, and the same
figures come out under `/usr/bin/python3`.

### 3. Not in this sheet

* **Case 1734** still waits for the key owner's wording of a change to
  `POL-NS-04`; the key expects `DRIVER_COMPENSATION` 3.60 and the clause's second
  half leads the judge to escalate. `policy/v3/` is not edited here.
* **Case 1767** was a one-off judge slip and nothing changes for it.


Every artifact in this repository that carries the corpus's `GPS_GAP` tag, with
how policy version 3 reads it, the gap that reading turned on, where that gap
sits, and the artifact's weight before and after.

**Which clause grades a gap turns on the category, and there are two.** POL-NS-08(b)
is a no-show limb about the waiting window, and the `integrity` block (which
carries every weight) lives in `no_show.json`. POL-RD-07 is the route-deviation
clause about the trace's own integrity, and **its own limbs (a) and (b)** grade a
route-deviation gap — the reading the key owner ruled for case 1775, and the one
part 5 put in place. Part 2 graded every gap by the no-show window, which turned
a route-deviation gap into a *short* one and **raised** its weight; part 3 left
every route-deviation gap ungraded at version 1's 0.6. Both readings were wrong,
and each is replaced below by the clause that owns the case.

The **waiting window** is the one POL-NS-01(c) measures dwell over — from the
trip's arrival marker to its cancellation — so a trip that was never cancelled
has no window and no gap can be inside it. A gap counts as inside when it
overlaps that interval; it *straddles the cancellation* when it contains the
cancellation itself. For a no-show case a gap is "long" when its duration is
strictly greater than `integrity.gps_gap_policy_threshold_sec` (120 s). For a
route-deviation case a gap is "long" when any gap between consecutive fixes
exceeds 90 s **or** any straight-line jump between consecutive fixes exceeds
500 m — both limits read out of POL-RD-07's own sentence, and neither typed. The
route-deviation reading is taken over the **whole trace**, because the record
does not mark the "disputed segment".

| set | case | evidence id | how version 3 reads it | gap | position | old weight | new weight |
|---|---|---|---|---|---|---|---|
| corpus | 110 | `EV-GPS-00110` | `GPS_GAP_LONG_INSIDE_WINDOW` (POL-RD-07) | 428.0 s | 18:35:00 → 18:42:08 | 0.39 | 0.39 |
| corpus | 210 | `EV-GPS-00210` | `GPS_GAP_LONG_INSIDE_WINDOW` (POL-NS-08(b)) | 186.0 s | 23:39:15 → 23:42:21 | 0.25 | 0.25 |
| corpus | 211 | `EV-GPS-00211` | `GPS_GAP_LONG_INSIDE_WINDOW` (POL-NS-08(b)) | 168.0 s | 12:33:40 → 12:36:28 | 0.39 | 0.39 |
| codex | 9115 | `EV-GPS-09115` | `GPS_GAP_LONG_INSIDE_WINDOW` (POL-RD-07) | 160.0 s | 20:03:10 → 20:05:50 | 0.60 | 0.60 |
| wild | 512 | `EV-GPS-00512` | `GPS_GAP_LONG_INSIDE_WINDOW` (POL-RD-07) | 860.0 s | 19:23:30 → 19:37:50 | 0.39 | 0.39 |
| wild | 517 | `EV-GPS-00517` | `GPS_GAP_LONG_INSIDE_WINDOW` (POL-RD-07) | 620.0 s | 22:26:30 → 22:36:50 | 0.39 | 0.39 |

The two no-show rows are graded by the waiting window, and their weights do not
move: both gaps are longer than 120 s and both windows exist, so both grade
`GPS_GAP_LONG_INSIDE_WINDOW` at 0.6 — the same figure the version-1 table gives
the ungraded tag. The four route-deviation rows are now graded by POL-RD-07, and
every one of their gaps exceeds 90 s, so all four grade long and keep the weight
part 3 gave them. **No weight in this table changes between version 1 and version
3**, and no weight moved when part 5 replaced the ungraded reading.

The two development sets carry twelve more tagged artifacts, and four of them
turn on the new limb — the short/long route pair and its variants. Their reading
and weight are in the part-5 section below.

That is the correction part 3 made to part 2, and part 5's correction to part 3.
Part 2 graded every `GPS_GAP`, which meant a route-deviation gap — a gap in a
trip with no waiting window — fell into `GPS_GAP_SHORT_OR_OUTSIDE_WINDOW` and its
weight rose (110 and 512 and 517 to 0.55, 9115 to 0.85). That reading applied a
no-show limb to a route-deviation case. Part 3 then left those gaps ungraded
altogether. Neither is the policy's reading: a route-deviation trace is impaired
for policy purposes under **POL-RD-07**, whose limbs state their own two limits,
and that is what grades it now.

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
