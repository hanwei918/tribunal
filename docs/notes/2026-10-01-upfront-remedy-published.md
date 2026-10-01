# POL-RD-11's remedy, published from policy version 2

**2026-10-01, part B of the "use wild-v1 as a development set" task. No model
call was made.**

## The defect

`wild-v1` was run once, from `freeze-2026-09-30`. Two of its 64 cases produced
no ruling at all: 517 and 533. Their drafts were not wrong — three of 517's four
reached the key's 33.50 and all of 533's reached 19.30 — and every one of them
was refused by `DRAFT_AMOUNT_NOT_READ_OFF`, because the money block published no
figure the amount could be read off. An upfront-quoted trip's block published
the quote, the charge and the difference, and nothing that an amount could be
read from under the amount rule the runs use.

A second finding from the same reading is what this part does **not** do. The
`signed` amount rule was measured over the three recorded runs and is **not
adopted**: on 501 it turns a safe `ESCALATE` into a published 8.50, read as
`14.50 - 6.00` of two figures that are both on the block and that have nothing
to do with each other. The default rule stays `published`.

## The figure

POL-RD-11 limits the rider's remedies on an upfront-quoted trip to "(a) any
amount by which charged_total exceeds quoted_fare_sgd plus the pass-through and
statutory lines properly chargeable under POL-RD-09 … which is refunded in
full; and (b) a pass-through correction under POL-RD-09 for off-route or phantom
gantries". Part B publishes limb (a) as a figure:

```
pol_rd_11_remedy = max(0, charged_total - quoted_fare_sgd - properly_chargeable)
```

rounded UP to the nearest SGD 0.05, with `properly_chargeable` published beside
it as its own components. `properly_chargeable` is the sum of

- **each ERP line that is on the optimal route and crossed.** A line is crossed
  when its nearest fix lies within the `POL-RD-09` radius, **parsed from the
  clause's own prose** — "treating any fix within 250 m of the gantry as a
  crossing" — and also when it carries no coordinates, and also when a gap
  brackets its closest approach and the across-gap distance lies within the
  radius. Off-route lines and phantom lines are excluded;
- **the itemised airport surcharge, at the amount charged**, when the trip's
  pickup is at an airport the clause's `applies_to` names. It is never
  recomputed from the peak or off-peak rate;
- **the waiting-time fee**, always.

`POL-RD-11(b)` is not added on top of `(a)`: an off-route or phantom line is
already excluded from `properly_chargeable`, and the clause's own note says
limb (1) of POL-RD-09 exists to stop exactly that double count.

A null `quoted_fare_sgd` publishes no figure and the reason instead, because the
clause turns on the quote and there is nothing to measure the charge against.

The block's note says the two things a reader has to know: that the figure
assumes no rider-caused exoneration under `POL-RD-09(3)`, and that "crossed" is
the reading of every key on the 13 upfront cases and is narrower than the
clause's literal words, which match a gantry to the trace by coordinates alone.

## The 13 upfront cases

Every one of them reads its remedy off the money block, and every one equals the
key's amount:

| case | set | charged | quoted | `properly_chargeable` | `pol_rd_11_remedy` | key |
|---|---|---|---|---|---|---|
| 115 | corpus | 39.00 | 34.50 | 2.50 — KPE Defu Flyover, on-route, 44.5 m | 2.00 | 2.00 |
| 9114 | codex | 25.20 | 22.00 | 0.00 — its one line is off-route, 7,482 m | 3.20 | 3.20 |
| 501 | wild | 39.00 | 24.50 | 0.00 — both ECP lines are off-route | 14.50 | 14.50 |
| 506 | wild | 55.20 | 45.00 | 0.00 — no ERP line | 10.20 | 10.20 |
| 510 | wild | 25.80 | 15.80 | 0.00 — no ERP line | 10.00 | 10.00 |
| 516 | wild | 46.10 | 43.10 | 0.00 — its line is off-route, 2,609 m | 3.00 | 3.00 |
| 517 | wild | 67.50 | 28.00 | 6.00 — the Changi surcharge, at the amount charged | 33.50 | 33.50 |
| 521 | wild | 12.00 | 10.00 | 0.00 — its line is off-route, 6,778 m | 2.00 | 2.00 |
| 524 | wild | 16.10 | 12.90 | 0.00 — no ERP line | 3.20 | 3.20 |
| 525 | wild | 17.50 | 13.00 | 0.00 — no ERP line | 4.50 | 4.50 |
| 531 | wild | 27.90 | 27.90 | 0.00 — no ERP line; surcharge charged 0.00 | 0.00 | *(null)* |
| 532 | wild | 81.00 | 75.00 | 0.00 — on-route line **not crossed**, 1,159 m | 6.00 | 6.00 |
| 533 | wild | 51.30 | 29.00 | 3.00 — CTE Ang Mo Kio, on-route, 0 m | 19.30 | 19.30 |

**Every exception, explained.**

- **115, 533 — a crossed on-route line counts.** 115's KPE line is 44.5 m from
  the nearest fix and 533's CTE line is 0 m; both are within the clause's
  radius and both are on the optimal route, so both are properly chargeable.
- **532 — an on-route line that is not crossed does not count.** 532's CTE line
  is the same gantry as 533's, on the optimal route, and the nearest fix is
  1,159 m away — well outside 250 m. It is a phantom line, and the key's 6.00 is
  the plain charge over the quote. This is the pair that separates the two tests
  the clause applies, and it is the reason "crossed" is not simply
  `on_optimal_route`.
- **501, 9114, 516, 521 — an off-route line does not count, however close the
  trace came.** 501's two ECP lines are *crossed* (0 m) and still excluded, on
  the route flag alone.
- **517 — the airport surcharge counts at the amount charged.** 517 originates
  at Changi Terminal 3 and the fare itemises 6.00.
- **531 — a surcharge that was not charged is not recomputed.** 531 also
  originates at Changi (Terminal 2) and the fare itemises 0.00. The clause
  surcharges a trip that originates at the airport, so the line is properly
  chargeable; the figure counted is the amount the fare charged, never the
  peak or off-peak rate.
- **531 — a null key amount is 0.00.** The key's ruling is `NO_ACTION` with no
  amount, and the arithmetic agrees: the charge equals the quote.

## The gate

The figure is published **only when the brief is built at policy version 2 or
later** (`UPFRONT_REMEDY_VERSION = policy_versions.BASE_VERSION + 1`). At
version 1 every brief is byte-identical, so every recorded `brief_sha256` in
every run stays current — checked over all 106 recorded briefs in the three
sets.

Brief generation 2 ships with policy version 2, so the version-2 re-run carries
**both** this change and the amendment: the amendment is not the only thing
different about a version-2 brief, and part D's diff note says so.

Only the `UPFRONT_QUOTE` branch of the route-deviation money block changed.
`NOT_STRUCTURED_MONEY`, `_erp_lines`, `facts.py` and the metered constants are
untouched — including `NOT_STRUCTURED_MONEY`'s `gantry_match_radius_m` entry,
which still says the radius is prose-only and that the ERP figures decide no
match. That entry is about the *published ERP figures*, which still decide no
match; the remedy is a new figure that does decide one, and it publishes the
radius it read under `gantry_match_radius.distance_m`.

Naming, so nothing collides: `pol_rd_11_remedy` and not a key containing
`refund` (POL-RD-11(a) is an overcharge, not a fare handed back); `crossed` and
never `matched`; and the non-money numbers go under names already in
`NOT_MONEY_FIGURES` — `distance_m` for the radius and each line's nearest-fix
distance, `across_gap_distance_m`, `on_optimal_route`.

## The tests

`tests/test_upfront_remedy.py`, 14 tests, `Ran 14 tests … OK`
(`runs/b-upfront-remedy-tests.log`, exit 0).

| class | what it holds |
|---|---|
| `VersionOneIsUnchangedTests` | all 106 recorded briefs rebuild byte-identically at version 1; a version-1 upfront block carries no remedy key and the old note |
| `UpfrontRemedyTests` | the remedy equals the key on all 13 upfront cases; the radius is the clause's 250 m read from prose; 533's crossed line counts and 532's uncrossed one does not; 501's crossed-but-off-route lines do not; 517's surcharge counts at 6.00 and 531's at 0.00; a null quote publishes the reason and no figure; no key anywhere in the block contains "refund" |
| `RoundingTests` | 25.83 charged against a 22.00 quote is 3.83 before rounding and **3.85** after; a charge below the quote is floored at 0.00 |
| `NonUpfrontTests` | at version 2, every case that is not an upfront one has identical evidence, an identical general policy, and a category policy that differs from version 1 by the amendment's clause and the version marker alone — and a no-show brief is byte-identical |

The version-2 briefs are built against a **temporary** amendments directory,
patched in at `policy_versions.amendments_dir`, because `loader.load_policies`
takes no root. The repository's own policy version stays 1 and no committed run
is read for writing.

**Seen to fail.** `runs/_b_sabotage_gate.py` sets `UPFRONT_REMEDY_VERSION` back
to the base version in-process and runs `VersionOneIsUnchangedTests`:
`FAILED (failures=2)` (`runs/b-sabotage-gate.log`). The identity test fails on
corpus case 115 with two different digests, and the "no remedy at version 1"
test finds `pol_rd_11_remedy` in the version-1 block. With the gate in place the
same module is green.

## What this does not do

- It does not change what any recorded run did. Nothing at version 1 moves.
- It does not adopt the `signed` amount rule, and it does not change the default
  one.
- It does not touch the metered recomputation, the no-show arithmetic, or the
  policy files.
