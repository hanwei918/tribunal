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
