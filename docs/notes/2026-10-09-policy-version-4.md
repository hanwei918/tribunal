# Policy version 4: Ji Guofang's POL-NS-11 on base 3, and the waiting-time fee as a published figure (2026-10-09)

## What version 4 is

Version 4 is **base 3 plus the first amendment on base 3**. Base 3 is Ji
Guofang's platform-aligned policy, kept at `policy/v3/` since 2026-10-08; the
amendment is `policy/v3/amendments/0001-pol-ns-11.json`, and the clause it adds
is **`POL-NS-11` ("Undecidable rider presence")**. The no-show policy therefore
carries **11 clauses**, and its `version` string reads
`3.0.0+amendment.0001` -- the suffix the amendment machinery has always written,
naming the highest amendment that reached the file.

The bundle `~/Desktop/Tencent /guofang-ui-v2/tribunal-amendment-0001-pol-ns-11.zip`,
sha256 `56262db647a29bb80230ac62d4921ee01508cc9d37dfe94b34e8b64ce698fbaa`, was
checked against that digest and unpacked outside the repository. Its top-level
Chinese note is left out, as the language rule requires. It holds the proposal and
the amendment; both are installed, at the paths the next section gives.

## Why it is an amendment on base 3, and not on base 1

Her note was written for a layout in which `policy/` is replaced wholesale and
`policy/amendments/` holds only a README. **That is not this repository**, and two
things follow from the difference.

* `policy/amendments/0001-pol-rd-13.json` must stay where it is. It is what
  **version 2** is, and the second sealed set was measured at version 2.
* Her file cannot be put beside it. It would duplicate number `0001`, and it would
  compute version 3 on base 1 -- a collision with the separate base `policy/v3/`,
  which `policy_versions.refuse_a_taken_version` exists to refuse.

So a **separate base now carries its own amendment sequence**, under exactly the
rules the base-1 sequence obeys: one clause per file, `NNNN-<slug>.json` numbered
from `0001`, the clause's id the next free number for its prefix, and add-only.
They live at `policy/v3/amendments/`, and the numbering is:

* **version 3 is the base alone** -- its own three files, no amendment of its own;
* **version 3 + k applies the base-3 amendments `0001` to k**, so the first
  amendment on base 3 makes **version 4**.

Every version has one owner. Base 1 owns 1 and 2, and its sequence can never grow
past `0001` -- `0002` there would compute 3, which base 3 owns, and
`refuse_a_taken_version` refuses it. Base 3 owns 3 and up. An amendment is refused
when the version it would compute belongs to a **different** base, and allowed
when it belongs to its own, which is what lets base 3's own first amendment
compute 4. `current_version` still names the base-1 sequence and is still **2**;
`highest_available_version` is now **4**.

**Base 1 is untouched.** `policy/general.json`, `policy/no_show.json`,
`policy/route_deviation.json`, `policy/amendments/` and the three
`policy/v3/*.json` files are byte-identical to `b124e5f`, so versions 1, 2 and 3
build exactly the briefs and the rulings they built -- which
`tests.test_policy_versions`' pinned loaded-policy digests and 44 recorded
`brief_sha256` values hold, and which the offline replay shows.

`--policy-version 4` is accepted, and a run at it goes to `runs/policy-v4/<model>/`
by the naming rule that was already there. **No run has been made at it.**

### The two files, and the four edits to hers

| path | what it is |
|---|---|
| `policy/v3/proposals/0001-pol-ns-11.json` | her proposal, byte for byte; sha256 `e1691fdd614649e1777d25d6a938f9f1b51ec2860c6281120ad5acfa4237db71`, which is the `proposal_sha256` her amendment records |
| `policy/v3/amendments/0001-pol-ns-11.json` | her amendment, with the four edits below and her `clause` object byte for byte |

* `base_version` is **3**, because her "base 2" is this repository's version 3;
* `proposal_file` is `policy/v3/proposals/0001-pol-ns-11.json`;
* `report_file` and `report_sha256` are **null**, with a `note` saying why: the
  key owner approved the clause directly after the 2026-10-08 development run on
  cases 1734 and 2734, without a `policy_gaps` report, which the instructions for
  that run allow ("or place it in `amendments/` by hand");
* `approved_at` is `2026-10-08T22:53:27.432695+00:00` -- the sheet's "the commit
  time", taken at the instant the amendment was **written** rather than at the
  commit itself, so that the tree the full suite is run over is the tree that is
  committed. The commit that carries it follows the suite.

### The schema, widened for one base and not the other

`policy_versions.load_amendment` held an **exact** key set, and that exactness is
the mechanism by which "an amendment adds one clause and can never edit one" is
true rather than intended. Her amendment carries a `note`, so the schema is
widened -- **for base 3 only**. `AMENDMENT_NOTE_BASES` names the bases whose
amendments may carry one; `AMENDMENT_NOTE_FIELD` is `note`. A `note` is
**allowed** on base 3 and never required, and base 1's amendments may not carry
one at all, so widening one base's schema cannot widen the other's. The clause's
own eight fields are the same on both, and the null report fields need no
widening: the check has always been over the key set, not over the values.

`load_amendment` takes the base as a keyword with base 1 as its default, so every
existing caller reads what it always read.

## Her clause, quoted

`POL-NS-11`, "Undecidable rider presence", `NO_SHOW_CHARGE`, added because
`POL-NS-04` reads an absent `rider_track` as impaired while `POL-NS-08`'s closing
sentence escalates a case whose only evidence for the deciding fact is impaired.
Its `rule`, in full:

> Where POL-NS-04 limb (c) cannot be run - rider_track is absent from the
> gps_trace, or every fix in it is filtered out for accuracy - limb (c) is
> UNDECIDABLE: it is neither satisfied nor failed, POL-NS-04 cannot exonerate the
> rider, and the dispute is decided under the remaining clauses on the driver's
> own evidence. Notwithstanding POL-NS-08(b), the missing rider_track is not the
> evidence for any deciding fact of those clauses: it does not impair the gps_trace
> for the driver's arrival or dwell, does not by itself engage POL-NS-08(b) or
> POL-NS-09(e), and does not lower the POL-GEN-02 cap on a finding that rests on
> the driver's track. The Judge must say the test could not be run rather than
> inferring the rider was elsewhere. This clause licenses no ruling value.

It requires `gps_trace`, `chat_log` and `trip_record`, licenses **no** ruling
value, and favours **NEUTRAL**. Its own `notes` say where it is going: "At the next
base revision this clause folds into POL-NS-04's undecidable sentence and the
rider_track words come out of POL-NS-08(b)."

**This is the key owner's ruling on case 1734**, whose key expects
`DRIVER_COMPENSATION` 3.60 and which part 4 left alone waiting for exactly this
wording. The clause is in the version-4 policy and in a version-4 brief for 1734;
nothing about case 1734's key is changed by this part, and no case file, answer key
or prompt is touched.

## The waiting-time fee as a published figure (case 1740)

`dev-v2` 1740 is a completed trip charged a waiting-time line of SGD 5.00, and
`POL-NS-10(e)` refunds such a line in full where limb (d) does not support it. All
four drafts proposed **5.00** and every one was rejected with
`DRAFT_AMOUNT_NOT_READ_OFF`, because the no-show money block published the fee in
force only under `constants` -- and `constants` is deliberately not somewhere a
draft may read an amount from.

From version 3 on, the no-show money block publishes **two figures**:

| figure | value for 1740 | evidence id | clause |
|---|---|---|---|
| `waiting_time_fee` | 5.00, the line `fare_breakdown` charged | `EV-FARE-01740` | `POL-NS-10` |
| `waiting_fee_in_force` | 5.00, from `platform_policy_in_force` | `EV-TRIP-01740` | `POL-NS-10` |

`pipeline.published_money_figures` includes both, because it walks every numeric
leaf that is not under `constants` or `not_structured` and whose name is not one
of the quantities that are not amounts -- so the fee in force now appears twice,
once as the constant that says what the policy states and once as a figure a draft
can cite. An amount that was readable before is read off the same path it always
was: the two new figures are the last in the block, and the read-off returns the
first match, so the change can only turn a miss into a match. For 1740 at version
3, `5.00` now reads off `waiting_time_fee.value`.

**Versions 1 and 2 do not move.** They build no platform-policy block, so neither
figure is published and the money block is byte-identical to what it was; the
publication is gated on `policy_version >= 3`.

## The tests

`tests/test_policy_versions.BaseThreeAmendmentTests` (11 tests) holds the new
numbering and the schema: the installed amendment's digest and the proposal digest
it records, the `note` allowed on base 3 and refused on base 1, version 4 loading
with 11 no-show clauses and `3.0.0+amendment.0001`, the amendment moving only the
file its clause joins, a version-4 brief carrying `POL-NS-11` and no `sources`, a
second `0001` on base 3 refused, a clause that would rewrite `POL-NS-04` refused,
a next-free clause really added, and a version above base 3 refused with base 3 in
the message. `tests/test_brief.VersionThreePlatformPolicyTests` gains three tests
for the two published figures, the read-off and the unchanged earlier versions, and
`tests/test_policy_gaps.ApproveTests` gains two: approve at base 3 writes under
`policy/v3/amendments/` and makes version 4, and base 1's refusal of a second
amendment stays.

Three existing tests moved because the version they called "the one the repository
does not have" is no longer 4: `highest_available_version` is now 4,
`refuse_a_taken_version(4)` is now refused **on base 1** (and allowed on base 3),
and the two command-line refusals now name version 5. `LOADED_POLICY_DIGESTS`
gains both version-4 entries; the route-deviation one equals version 3's, because
a no-show clause leaves that file alone.

Every new test was shown **red first**, against `b124e5f`'s code with the new
tests and the new policy files in place:

| module | red |
|---|---|
| `tests.test_policy_versions` | `Ran 87 tests` / `FAILED (failures=4, errors=49)` -- all eleven `BaseThreeAmendmentTests` tests (ten errors on the machinery the module does not yet have, one failure on the version-above-base-3 message), plus the three updated pinned tests |
| `tests.test_brief.VersionThreePlatformPolicyTests` | `Ran 14 tests` / `FAILED (failures=1, errors=3)` -- the two new figures absent and `5.00` not readable |
| `tests.test_policy_gaps.ApproveTests` | `Ran 16 tests` / `FAILED (errors=1)` -- `approve_proposal` has no `base_version` |

With the change in place the three modules read `OK` (87, 14 and 16 tests). One of
the new tests is green on both sides and is meant to be:
`test_the_waiting_fee_is_not_published_at_versions_one_and_two` asserts the
*absence* of the two figures at versions 1 and 2, which is a regression guard on
behaviour this part does not touch -- and
`test_approve_on_base_one_still_refuses_a_second_amendment` is the same kind of
guard on the refusal the sheet leaves in place.

## What has not been measured

**No run exists at policy version 4.** Nothing in this repository has briefed a
case at version 4 for a recorded run, no model call was made while adding it, and
no figure anywhere was produced under it. The default policy version is still 1.

What *is* measured, and holds today: versions 1, 2 and 3 build exactly the briefs
they built. The 44 recorded `brief_sha256` values rebuild, the loaded-policy
digests at each version are pinned and unchanged, and the offline replay is green
for all 128 cases.

## Part 7: the `POL-GEN-08(1)` scope gate, later versions for the base-3 sets, precedents at a version, the revised keys, and version 5 (2026-10-09)

Part 7 adds the scope gate the clause has always stated, lets the sets written for
base 3 run at any version on that base, allows the precedents block and a policy
version to be measured together, installs the key owner's revised keys, and adds
`POL-RD-14` as the second amendment on base 3 -- so the highest version is now
**5**. Versions 1, 2 and 3 are untouched, and version 4 is unchanged.

### 1. `POL-GEN-08(1)`: a flagged dispute is never adjudicated automatically

`POL-GEN-08(1)` (version 3 and later) says a dispute carrying
`dispute.safety_flag` or `dispute.complaint_flag` "is never adjudicated
automatically: it is routed to human review under POL-GEN-06 with the record
assembled but no draft ruling issued". The pipeline did not obey it: it asked the
advocates and the judge and let the judge decide whether to escalate.

From version 3, when either flag is `true`, `tribunal.pipeline.run_loaded_case`
now **builds the brief** -- "the record assembled" -- and then makes **no** call:
not the two advocates, not the judge, not the verifier. It publishes an
`ESCALATE` with `confidence` 0, both money fields `null`, the reason code
`GEN08_SCOPE` and **no referral**, with an explanation naming the flag and the
clause. A `scope_gate` event is written to `events.jsonl`, and the case file
carries a `scope_gate` block recording `calls` 0, so the file says in its own
words that no model call was made. `ops.escalation` builds a packet for the case
and its timeline holds no call. The gate is checked against the loaded version, so
versions 1 and 2 ask the model exactly as they always did; and the three flagged
development cases -- `dev-v2` 1735 and `dev-v2-ext` 2735 and 2759 -- are the only
cases in the repository that carry either flag.

The revised keys (item 4) expect `ESCALATE` with an **empty** referral list for
all three, so the gate publishes no referral. The earlier keys expected the
referral text; that expectation was the key owner's and it has changed.

`ops.queue` routes both flags, whatever the category: a `safety_flag` dispute to
`SAFETY_FAST_TRACK` (reason `GEN08_SAFETY`) and a `complaint_flag` dispute to
`HUMAN_REVIEW` (reason `GEN08_COMPLAINT`). The flag is checked before the
category, because the clause overrides the category.

### 2. Version 4 and 5 for the sets written for base 3

`dev-v2`, `dev-v2-ext` and `ryde-v3` fixed policy version 3 in their registration,
so `--set dev-v2 --policy-version 4` was refused with "fixes policy version 3 in
its registration". They are written for a **base**, not for one version, so a
`DevelopmentSet` now carries a `policy_base` alongside `policy_version`:
`policy_base` 3 for these three, `None` for every other set.

- They accept any version on base 3 -- 3, 4, 5, ... -- and refuse one that belongs
  to another base, so `--policy-version 2` is refused by name and
  `--policy-version 4` and `--policy-version 5` are accepted.
- With no `--policy-version` they run at the **latest** version on base 3, which
  is now **5**.
- The run records the version it used, and the version moves the run one level
  down under the set's own root: `runs/<set>/policy-v<N>/<model>/`.
- Every set registered before version 3 keeps what it fixes: `wild-v2` is still
  version 2 by registration and still runs into `runs/wild-v2/<model>/`; the
  corpus, the second set and both sealed sets are unchanged.

The refusals that pair a policy version with another switch are keyed on the
version the **command line** named, not on the version a set resolves to. That is
what keeps every set registered before version 3 exactly as it was: `wild-v2`
resolves to version 2, but `--set wild-v2 --report` and `--set wild-v2
--replay-check` are still allowed and `--set wild-v2 --ablate X` is still refused
by `wild-v2`'s own sealed-root message rather than by the version block.

`main` therefore hands `run_set` the **command line's** version -- version 1, the
default, when it named none -- and `run_set` is the layer that replaces it with
the registration, because that is the layer that knows the registration. Version
1 means "not named", and it can, because no set written for a base may take it.

A first attempt keyed those refusals on the **resolved** version and passed
`run_set` an "explicit or `None`" flag instead, and turned nine of
`tests.test_sealed_set_wild_v2` red: `--set wild-v2 --report` and `--set wild-v2
--replay-check` were refused, `--set wild-v2 --ablate X` was refused by the
version block instead of by `wild-v2`'s own sealed-root refusal, and `run_set`
handed the runner a version the runner could not compare. All nine are green with
the predicate narrowed back to the command line's version.

`--set dev-v2 --precedents --policy-version 4` is accepted (item 3);
`--set dev-v2 --ablate X --policy-version 4` is refused.

### 3. Precedents at a policy version

The runner allowed at most one of `--ablate`, `--precedents`,
`--policy-version N>=2` and `--amount-rule`, so the precedent library could be
measured only at version 1. The precedents block is the same whatever the policy
version, so `--precedents` may now be given **together with** `--policy-version`.
Their run writes to `runs/precedents/policy-vN/<model>/`, a root of its own that
collides with neither `runs/precedents/<model>/` nor
`runs/policy-vN/<model>/`, guarded by `assert_precedents_policy_v_destination`
against this version's directory specifically. Every other pairing keeps its
refusal, `--ablate` with `--policy-version` included, and
`eval.sealed_roots.refuse_a_sealed_destination` still refuses every sealed root.

### 4. The key owner's revised keys (bundle rev3)

The bundle `~/Desktop/Tencent /guofang-ui-v2/tribunal-dev-v2-rev3.zip`, sha256
`d70e6f1198dbd473250e2725c94d9751be266120d464556890a429c9e94bf675`, was checked
against that digest and unpacked outside the repository. **No case file changed**:
every `data/external/dev-v2*/case-*` file and both `index.json` are byte-identical
to rev2, checked file by file. Only the keys, `EXPECTED.md`, `manifest-meta.json`
and `DATASHEET.md` under `eval/answers/dev-v2*/` changed, and
`eval/synth/make_dev_set.py` and `eval/synth/verify_dev_set.py`. Part 3's
README and datasheet wording edits are kept. The checker reads `80 of 80` and
`120 of 120`, and `tests.test_dev_v2` passes.

Every changed key, with the ruling it follows:

| case(s) | was | now | the ruling it follows |
|---|---|---|---|
| 1763, 1764, 2813, 2814 | `PARTIAL_REFUND` 6.00 and 9.50 | `PARTIAL_REFUND` 6.80 and 10.30 | The 0.80 platform fee is not "properly chargeable" under `POL-RD-11(a)`, which lists the lines chargeable above the quote exhaustively; the fee is refunded with the rest. |
| 1782, 2832, 2856 | `ESCALATE` | `PARTIAL_REFUND` 5.50, 5.00, 5.90 | `POL-RD-14` (item 5): a rider stop request the trace never corroborates did not cause the excess, so `POL-RD-04` does not apply and the deviation is decided under `POL-RD-01` and `POL-RD-02`. This is not the `POL-RD-10(7)` contradiction. |
| 1723, 1724, 2723, 2724, 2747, 2748 | referral leads with `POL-NS-01(d)` | referral leads with `POL-NS-01` | The sentence that directs the record follows limb (d) in the clause body rather than sitting inside it, so the referral cites the clause and not a limb. |
| 1735, 2735, 2759 | `ESCALATE` with a `POL-GEN-08(1)` referral | `ESCALATE` with no referral | An escalation replaces the ruling under `POL-GEN-03` and the trigger is stated in the explanation; the gate (item 1) issues no draft ruling and so carries no referral. |

### 5. Amendment 0002 on base 3: `POL-RD-14`, and version 5

The bundle `~/Desktop/Tencent /guofang-ui-v2/tribunal-amendments-base2.zip`, sha256
`af53cfee9d7d5e9b5fb8af650845fdda41b6eee4676bf854072ddee3f48884a5`, was checked
against that digest and unpacked outside the repository; its Chinese note is left
out, as the language rule requires. It holds:

- **`0002-pol-rd-14`**, proposal and amendment. `POL-RD-14` is "Uncorroborated
  rider instruction". Where a rider instruction in the `chat_log` meets
  `POL-RD-04(a)` to (c) but the `gps_trace` never passes within 200 m of the
  waypoint and never travels the requested road, the instruction did not cause the
  measured excess: `POL-RD-04` does not apply, no distance is excluded, and the
  deviation is decided under `POL-RD-01` and `POL-RD-02` on the trace as
  measured. It is not the contradiction `POL-RD-10(7)` describes, which is
  engaged only where the trace corroborates the instruction in part. It licenses
  `PARTIAL_REFUND`, `FULL_REFUND` and `NO_ACTION` and favours `RIDER`. This is the
  key owner's ruling on 1782.
- **`0001-pol-ns-11`**, revised. The clause object is **byte-identical** to the
  one installed in part 6, confirmed against it; its `cases` now add 2758, so the
  proposal's sha256 is
  `27ffb0758cca510e9c9e27ed4b5581df166c8890a00bd9e7cdca77a4cf4a4be3`.

The proposals are installed byte for byte under `policy/v3/proposals/`, and each
is checked against the `proposal_sha256` in its amendment. The amendments are
under `policy/v3/amendments/` with part 6's edits: `base_version` 3, the
`proposal_file` path, `approved_at` (0001 keeps part 6's time; 0002 carries the
time this part was written), and null report fields with a `note` saying why --
for 0002, that the key owner approved it on 2026-10-09 after the development runs
of 2026-10-08 and 2026-10-09. Every `clause` object is byte for byte the bundle's.

Version 5 is base 3 with 0001 and 0002, so a version-5 route-deviation policy
carries **14 clauses** and its `version` reads `3.0.0+amendment.0002`; the no-show
file is untouched by 0002 and still reads `3.0.0+amendment.0001`. Version 4 stays
base 3 with 0001 only, and a version-4 route-deviation brief for case 101 is
pinned at
`1faec3653b2f07d0051a33f5be1e80d683144de59aafbcc93e867cd5961c6beb`, the digest it
had before this part. A version-5 route-deviation brief carries `POL-RD-14` and no
`sources` **key** -- asserted structurally, because a clause's own prose contains
the word "sources" and a substring search would report a key where there is only a
sentence.

### The tests

`tests/test_policy_v3_scope_gate.py` (16 tests) holds the gate: a scripted run of
1735, 2735 and 2759 at version 3 sends **zero** requests and ends `ESCALATE` with
no referral; a complaint-flag fixture is gated the same way; the same fixture at
version 2 goes to the model; the event, the case file and the escalation packet
are all checked; and the queue routes both flags.

`tests/test_development_sets.BaseThreeSetRegistrationTests` (8 tests) holds the
versions: `--policy-version 4` and `5` are accepted and recorded for each of the
three sets, the default is the latest base-3 version, `--policy-version 2` is
refused by name, and the corpus and the sealed sets are unchanged.

`tests/test_precedents_at_a_version.py` (10 tests) holds the one allowed pairing,
its own root, the three non-colliding roots, the destination guard, the sealed
refusal that stays, and the refusals that stay (`--ablate` with a version,
precedents with an ablation, the amount rule with a version).

`tests/test_policy_versions.py` gained version 5 to the pinned loaded-policy
digests, the two installed base-3 amendment digests, the version-4 brief digest,
and the 14-clause version-5 route-deviation load. `tests/test_policy_versions`
reads 90 tests OK.

Every new test was shown **red first**, against `7c3cf93`'s code in a worktree at
that commit with the new tests copied in:

| module | red |
|---|---|
| `tests.test_policy_v3_scope_gate` | `Ran 9 tests` / `FAILED (failures=1, errors=8)` |
| `tests.test_precedents_at_a_version` | `Ran 10 tests` / `FAILED (errors=5)` |
| `tests.test_development_sets.BaseThreeSetRegistrationTests` | `Ran 8 tests` / `FAILED (failures=25, errors=8)` |
| `tests.test_policy_versions` | `Ran 90 tests` / `FAILED (failures=3, errors=5)` |

The gate's own first red run, made in the working tree before the change, read
`Ran 9 tests` / `FAILED (failures=1, errors=8)` with the premise visible in the
failure: `AssertionError: 0 != 3`, the three calls the pipeline made today for
1735.

The full suite was run once at the end on both interpreters, over the tree this
part carries: `python3` (3.11) `Ran 2580 tests in 133.339s` / `OK (skipped=4)`,
and `/usr/bin/python3` (3.9) `Ran 2580 tests in 102.216s` / `OK (skipped=4)`.

One regression the suite caught and this part fixed is recorded above: keying the
version-pairing refusals on a set's **resolved** version instead of the command
line's turned nine of `tests.test_sealed_set_wild_v2` red, because `wild-v2` is a
set registered before version 3 and had to behave exactly as it did at `7c3cf93`.

## Part 8: `POL-NS-12` and the registration mask `POL-GEN-08(4)` (2026-10-09)

Part 8 adds the owner's clause `POL-NS-12` ("Platform-confirmed arrival and
waiting") as the third amendment on base 3 -- so the highest version is now **6**
-- and makes the two things it turns on visible in a version-6 brief: the
platform's own arrival and wait-timer events, and, under `POL-GEN-08(4)`, a
registration mask over the free text the model reads.

### What version 6 is

Version 6 is **base 3 plus the three amendments on base 3**. Base 3 is Ji
Guofang's platform-aligned policy at `policy/v3/`; the amendments are
`0001-pol-ns-11.json` (`POL-NS-11`), `0002-pol-rd-14.json` (`POL-RD-14`) and
`0003-pol-ns-12.json` (`POL-NS-12`). The no-show policy therefore carries **12
clauses**, and its `version` string reads `3.0.0+amendment.0003`; the
route-deviation file is untouched by the new clause and still reads
`3.0.0+amendment.0002`. Version 4 is base 3 with `0001` only and version 5 is it
with `0001` and `0002`; both are unchanged, and a version-4 and a version-5 brief
for case 101 are pinned at the digests they had before this part.

The input was `~/Desktop/tribunal-amendment-0003-pol-ns-12/0003-pol-ns-12.proposal.json`,
sha256 `105fa95280d54f660d075cd9ee49b75c5db3fd2c987812d58ab6abc446d407b6`, checked
against that digest before anything was copied. It is installed byte for byte at
`policy/v3/proposals/0003-pol-ns-12.json`, and the amendment at
`policy/v3/amendments/0003-pol-ns-12.json` carries the proposal's `clause` object
**byte for byte** (the two clause blocks were compared as bytes), `base_version`
3, `proposal_file` and `proposal_sha256` as above, `report_file` and
`report_sha256` null, `cluster_id` null, `cases` `[901]`, `approved_by` `Zhou
Hanwei`, `approved_at` the instant the file was written, and a `note`.

`--policy-version 6` is accepted and a run at it would go to
`runs/policy-v6/<model>/`; the sets written for base 3 (`dev-v2`, `dev-v2-ext`,
`ryde-v3`) now default to the latest base-3 version, which is **6**, and their
versioned runs land under `runs/<set>/policy-v6/<model>/`.

### The clause, quoted

`POL-NS-12`, "Platform-confirmed arrival and waiting", `NO_SHOW_CHARGE`. Its
`rule`, in full:

> Where trip_record.platform_policy.arrival_marker is GPS_AUTO and
> trip_record.events carries the platform's own arrival event stating its
> geofence test (the distance to the pickup point and the speed at the arrival
> time), together with wait_timer_started and wait_timer_expired events, those
> events are PLATFORM_TELEMETRY records of the platform's full-resolution
> measurement. They are a carrier independent of the exported gps_trace for
> POL-NS-01 limbs (b) and (c) and for POL-GEN-02(2): arrival is established at
> the arrival event's time, and the free waiting period is established as served
> when wait_timer_expired precedes the termination, unless an admissible fix in
> the exported trace affirmatively places the driver outside the arrival radius,
> or moving at 15 km/h or more, during the window (POL-NS-05). A sparse or
> accuracy-less export trace does not impair these events; it is weighed only for
> contradiction. A driver-pressed arrival marker (BUTTON) is not covered by this
> clause. This clause licenses no ruling value.

The wording was revised on 2026-10-09 at the request of Ji Guofang, the policy
owner, so that the rule states the geofence test in general terms rather than
quoting the sample's event text; her confirmation follows this wording.

It requires `trip_record` and `gps_trace`, licenses **no** ruling value, and
favours **NEUTRAL**. A driver-pressed marker stays under `POL-NS-02` and
`POL-NS-05`.

### Why the owner approved it

The organisers' own sample -- case 901, converted from `DISP-002` -- escalates at
version 3, and their stated expectation is that the charge is upheld. All four
drafts escalated. The judge's reasons were that the exported trace holds four
fixes in the waiting window, minutes apart and with no accuracy field, so the
`POL-NS-02` arrival test cannot run, and that the platform's "auto-arrival
confirmed" event is the same carrier as the trace, so it cannot corroborate it.
The owner approved a clause that treats a platform-confirmed (`GPS_AUTO`) arrival
and the platform's wait-timer events as their own carrier, because those events
are the platform's own full-resolution measurement rather than a copy of the
export. **Ji Guofang's confirmation as policy owner is pending**: the clause was
approved by the owner on 2026-10-09 and carries a `note` saying so, and the
amendment has null report fields because there is no `policy_gaps` report.

### The facts the clause turns on, and the mask

* **The platform events.** A version-6 no-show brief already passes the trip
  record's `events[]` array through, so **no new block was added**: the three
  events (`driver_arrived`, `wait_timer_started`, `wait_timer_expired`) travel
  with their times and the trip record's `evidence_id`. A test confirms the
  pass-through for case 901. Of the 200 `dev-v2` and `dev-v2-ext` cases, none
  carries the full trigger -- a `GPS_AUTO` marker, an arrival event and a
  `wait_timer_expired` event -- and only case 901 does; a test asserts both.
* **The registration mask.** `POL-GEN-08(4)` says the record shown to advocates,
  judge and reviewers "carries party identifiers, not names, telephone numbers or
  vehicle registration marks; those are masked before display". From **version 6
  only** the brief replaces every match of the Singapore registration pattern
  `S[A-Z]{1,2}\s?\d{1,4}\s?[A-Z]` (word-bounded) with
  `[vehicle registration masked]`, in a chat message's `text`, a trip record's
  `events[].detail`, and the dispute's `claim_text` and `counterparty_statement`.
  Ids, numbers and every other string are untouched, and no case file is changed:
  the mask is applied to the brief only. The marks it reaches are corpus 202
  (`SLA1234X`), 208 (`SJK8842P`) and 212 (`SLZ9931H`) in chat text, and case
  901's chat text and one of its `events[].detail` strings (`SGP 4521 M`) -- the
  sheet's scan described that mark as sitting in two `events[].detail` strings,
  and the committed case carries it in one event detail and one chat message, so
  the mask is written over every match wherever it appears rather than over a
  counted list. The scan found no telephone number in any set. Versions 1 to 5
  keep the bytes they had, so a version-5 brief for 208 still carries its mark.

### The tests

`tests/test_policy_v3_ns12.py` (7 tests) holds the facts: the trigger scan over
the 200 development cases and the second set, case 901 as the only case with the
trigger, the version-6 brief carrying `POL-NS-12` and the three platform events,
the policy text carrying none of `DISP-002`, `organiser` or `901` and no
`sources` key, the mask over the four version-6 briefs and a version-5 brief that
still carries its mark, the fixture message and dispute free text, and the ids
the mask leaves alone.

`tests/test_policy_versions.py` gained version 6 to the pinned loaded-policy
digests, the third amendment's digest and the proposal digest it records, the
12-clause version-6 no-show load, the pinned version-5 brief digest, and a third
amendment that rewrites an existing clause refused. The two tests that called
version 6 "the one the repository does not have" now name version 7, and
`tests/test_development_sets.py` reads the default base-3 version as 6.

**Run no tests at all.** Every new test was written against the pre-change tree
and is left for the owner to run outside the sandbox -- the owner runs each new
test against the code before this part (it must fail there) and the full suite on
both interpreters. The change was checked from the record instead: the 44
recorded `brief_sha256` values still rebuild, the loaded-policy digests at
versions 1 to 6 match their pins, the version-4 and version-5 brief digests for
101 are the ones they had before this part, the no-leakage scan reports the same
two known findings and no new one, and a version-6 brief for 901 carries the
clause and masks the marks.

### What has not been measured

**No run exists at policy version 6.** Nothing in this repository has briefed a
case at version 6 for a recorded run, no model call was made while adding it, and
no browser was launched. The default policy version is still 1. What *is*
measured, and holds today: versions 1 to 5 build exactly the briefs they built at
`541ac31`, and the offline replay is unchanged.

