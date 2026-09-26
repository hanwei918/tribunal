# The policy's arithmetic, in the brief

**2026-09-26.** The first principle of this repository is that money comes from a
calculator, not from the model. `tribunal/money.py` has held one since the
beginning -- `recompute_metered_fare`, `refund_for`, `round_up_005`,
`refund_outcome` -- but until now only its tests called it. Every amount the
judge produced was worked out by the judge.

This note records the calculator extended and published in the brief as derived
money facts: what it computes, what it refuses to decide, whether both answer
keys can be read off its figures, and what the change makes stale.

**No model call was made, and no prompt was changed.** The change is on the brief
channel only.

## Where the money facts live

The block is attached to the **FARE_BREAKDOWN** artifact, under
`payload.derived.money`, exactly as the derived geometry is attached to the
trace. The fare breakdown is the artifact the money was charged on, so it is the
artifact a figure belongs beside. A case with no fare breakdown gets no block,
because there is nothing to compute on.

`tribunal.brief` assembles it through `_money_block`, which dispatches on the
dispute category to `_route_deviation_money` or `_no_show_money`. Every figure is
written by one wrapper, `_money(value, evidence_id, policy_id, clause_id=None,
structured=None)`, so every figure in the block carries the artifact it was read
from and the policy it was computed under -- the same discipline the other
derived facts follow, and an advocate can cite any of them.

Payable figures -- a refund, a fee, a compensation, a goodwill -- are decimal
strings with two places, written by `money.payable_string`. The intermediate fare
arithmetic is not: POL-RD-02 says intermediate values are not rounded, so the
recomputed fare keeps the decimals the calculator produced.

## What the calculator reads, and what it refuses

Two policy files carry structured fields and they are the only two sources of a
number:

- `policy/route_deviation.json`'s `fare_model` -- `base_fare` 3.80, `per_km`
  0.75, `per_min` 0.28, `platform_fee` 0.80, `de_minimis_refund` 0.50;
- `policy/no_show.json`'s `fee_schedule` -- `zone_class_fee_sgd`,
  `vehicle_tier_fee_sgd`, `driver_compensation_rate` 0.8,
  `pin_ambiguity_goodwill_rate` 0.5.

Everything else the clauses state is **prose only**, and the block says so rather
than guessing. `NOT_STRUCTURED_MONEY` names four figures and computes nothing for
them:

| clause | figure | what is not done |
|---|---|---|
| POL-RD-04 | `driver_compensation_per_unbilled_km` | no per-kilometre compensation is computed, and its cap is not applied |
| POL-RD-09(2) | `off_route_erp_refund_cap` | the ERP totals are published uncapped |
| POL-RD-09(4) | `gantry_match_radius_m` | the ERP figures report amounts and distances and decide no match |
| POL-RD-10(6) | `escalation_refund_ceiling` | no escalation is tested |

Each note says in words that the figure "is not a structured field", and a test
holds that phrase in every one of the four.

Two figures the calculator *does* need are prose-only and are read out of the
loaded clause text rather than typed in: POL-RD-02's full-refund share (90%) and
POL-RD-03's cap ratio (130%) and tolerance (1.0 km). `_money_prose_constants`
does that with `re.findall` over the loaded clause's own `rule` string and raises
`loader.LoaderError` when a line is absent, which is the route
`_deviation_thresholds` (POL-RD-01) and `_no_show_thresholds` (POL-NS-06/05)
already take. A test moves the clause text and watches the published figure move
with it.

**No policy number is a literal anywhere in the money path.** The fare constants
come from `fare_model`, the fees from `fee_schedule`, and the two prose figures
from the clause text; the tests that refuse a list of policy numbers as literals
in `facts.py` and `brief.py` still pass unchanged.

## Route deviation, metered trips

`_route_deviation_money` publishes, for a `METERED` trip:

- **`charged_total`**, and the fare model and payment status it was charged under.
- **The POL-RD-02 recomputed fare on the booked optimal route**, itemised.
  `money.metered_fare_components` returns the base fare, the distance and time
  charges, the surge multiplier read from `fare_breakdown.surge_multiplier`, the
  platform fee, the ERP lines lying on the optimal route, the surcharges
  itemised on the fare, the waiting fee and the promo, and their total. Every
  component is published beside the total, so the arithmetic is inspectable.
- **The refund**: `refund_before_rounding`, the `payable` figure rounded **up** to
  SGD 0.05 by `money.round_up_005`, the rounding `quantum`, whether the refund
  falls **below the de minimis** figure, the refund's share of `charged_total`,
  and whether it **reaches the full-refund share**.
- **Each ERP line's amount beside the trace's own proximity figures**, described
  below.
- **Where a traffic advisory is present and populated**: the POL-RD-03 cap
  (`cap_km` and the `justified_excess_km` that sits inside it), the
  closure-adjusted optimal distance and duration with the source the duration was
  taken from, and the recomputed fare and payable against that adjusted route.
  An advisory that is missing, or present but with no
  `shortest_lawful_alternative_km`, produces no entry rather than a fabricated
  one.

Two of these are worth naming because they are the ones a model cannot be
trusted to do in its head. Case **104**'s cap is
`1.30 x (30.10 - 27.10) + 1.00 = 4.90 km`; the measured excess of 7.07 km is
capped to 4.90, the adjusted optimal route is 32.00 km and 40.1 minutes, and the
payable against it is **3.60** -- which is the key. Case **9113**'s cap is
3.60 km, its adjusted route 13.60 km and 27.2 minutes, and its payable **8.05**.

The duration of an adjusted route comes from `amended_optimal_duration_min` when
the booked trip records one, and is otherwise scaled from the booked optimal; the
figure published says which, in `duration_source`. A booked optimal of zero
distance yields `undetermined` rather than a division by zero.

## Route deviation, upfront-quote trips

Where `fare_model` is `UPFRONT_QUOTE` the block publishes the quoted fare, the
charged total, and the difference between them, and **computes no distance
refund**: POL-RD-11 disapplies POL-RD-02 on such a trip, and running it would
refund money the rider never lost. The block carries a `note` saying so, and the
ERP lines, so the pass-through is still visible. Case **115** publishes 34.50
quoted against 39.00 charged, a 4.50 excess over the quote. Case **9114**
publishes 22.00 against 25.20, a 3.20 excess.

## No-show charges

`_no_show_money` publishes:

- the **schedule fee** -- `money.schedule_fee` takes the greater of the zone
  class fee and the vehicle tier fee and names **which dimension produced it**
  (`zone_class`, `vehicle_tier`, or `tie` when they are equal). Case **202** is
  `zone_class` at 6.00 and case **208** is `vehicle_tier` at 8.00; the corpus's
  other no-show cases either tie at 4.00 (201, 203-207, 211, 212, 214) or are won
  by the zone class at 6.00 (209, 210, 213);
- the **fee charged**, and the **difference** between the two;
- **driver compensation** at `driver_compensation_rate` -- 80% of the fee, so
  3.20 on a 4.00 fee and 6.40 on an 8.00 fee;
- **goodwill** at `pin_ambiguity_goodwill_rate` -- 50% of the fee, so 2.00 and
  4.00.

Both rates are read from the loaded `fee_schedule`, and the zone and tier tables
are published in `constants` beside them, so a reader can check the arithmetic
without the policy file open.

## What it does not do

**It computes figures and decides nothing.** There is no `refund_due` field, no
`deviation_established`, no verdict of any kind. Whether a deviation exists
(POL-RD-01), whether an advisory exonerates it (POL-RD-03), whether a full refund
is upgraded (POL-RD-06(b)), whether an off-route line is a pass-through
(POL-RD-09) and whether the driver conduct referral applies all remain the
judge's. The block exists so the judge reasons about figures instead of producing
them, not so the code decides the case.

**The ERP proximity figures decide no match either.** POL-RD-09(4)'s 250 m radius
is the clause's, is named in `not_structured`, and is refused as a literal. The
block reports how close the trace came and the judge applies the radius.

## Each ERP line's amount, beside the geometry that decides it

POL-RD-09(4) matches a gantry to the trace by comparing coordinates, so the
amount a line was charged at is not enough to decide whether it is refundable --
a reader needs to know whether the trace went near it. Each line in the money
block's `erp_lines` therefore carries, beside `amount_sgd` and
`on_optimal_route`:

- **`trace_proximity`** -- the trace's own proximity figures for that line: the
  nearest fix's index, timestamp and distance in metres, whether a sampling gap
  brackets the closest approach, and the chord across any such gap.

The values are read out of the trace's published `erp_gantry_proximity` block and
**never recomputed**, so there is one computation and one answer; the figure
keeps the trace as its `evidence_id` and gains the policy id every figure in the
money block carries. A line the trace published no record for carries `None`, and
a record with no geometry carries `available: false` with the trace's own reason,
so "no coordinates" stays distinguishable from "this code forgot to carry it".

`tests/test_brief.py` holds every figure equal to the trace's record for the same
line, on all **8** ERP lines the corpus carries (cases 103, 106, 114 and 115; the
second set's 9111, 9113 and 9114 carry five more).

## The answer-key check

Every case in both development sets whose key has a non-null amount was checked
against the block the brief publishes: is the key's figure one of the
calculator's money figures, or the sum of two or three of them? A money figure
here means a numeric leaf of the block that is not under `constants` (the policy's
own numbers, copied rather than computed) and is not a named non-money quantity
(kilometres, minutes, multipliers, shares) -- adding kilometres to dollars is not
reading an amount off a calculator. **No key was changed.**

**One case cannot be read off: case 109, on both figures.** Its `amount_sgd` and
its `driver_compensation_sgd` are both **3.15**, which is POL-RD-04's closing
limb: `0.75 x 4.16 km = 3.12`, rounded up to the nearest 0.05. POL-RD-04 states
that rate and its 15.00 cap only in prose, so the block names the figure as not
structured and computes no compensation for it. The block's nearest figure is
`refund.payable` 8.00, which is a different thing.

Every other case can be read off, and the ways they divide are worth recording
because they are not all the same claim:

- **Directly, one figure carries it.** 101, 104, 106, 107 and 114 on
  `refund.payable`; 202, 208, 214, 9101, 9102 and 9107 on `driver_compensation`;
  206 and 211 on `goodwill`.
- **Directly, but two figures share the value.** 103 (4.00 is both
  `erp_lines.off_optimal_route_total` and `erp_lines.total`), 105 (65.13 is both
  `charged_total` and `refund.full_refund`), 115 (2.00 is the off-optimal ERP
  line and the off-optimal total), 9114 (3.20 is carried by four figures,
  including `charged_over_quote`), and the ten no-show cases whose fee is charged
  in full and so read `schedule_fee` = `fee_charged` = the key's amount.
- **As a sum of two published figures.** 9111: `refund.payable` 9.15 plus the
  first ERP line's 1.00 = **10.15**. 9113: `closure[0].refund.payable` 8.05 plus
  the first ERP line's 1.00 = **9.05**. In both, the line added is the one lying
  **on** the optimal route, which POL-RD-09(1) treats as already comprehended;
  the key's figure is the computed refund plus that line, and the block publishes
  both operands, so the sum is reproducible even though the sum itself is not a
  published figure.

## What this makes stale

The block is emitted for every case whose fare breakdown has a payload, which is
**every case in both sets**. Read from the code -- build every brief from the
committed tree and from the working tree and compare the digests -- **all 44
changed and none is unchanged**: the corpus's 29 and the second set's 15.

```
changed 44 of 44
unchanged []
```

That is the largest stale set this repository has had. The gantry-proximity
change moved 7 of 44; this one moves every brief, because every brief carries a
fare breakdown.

**They cannot be replayed.** `--replay-advocates` reuses advocate outputs produced
from the old brief, so those outputs answer a question the advocates are no longer
asked, and `--replay-check` refuses a case whose recorded `brief_sha256` has
moved. The advocates must see the new facts, which means a **full re-run of all
44**.

The commands, one per development set. **They were not run for this note.**

```
python3 -m eval.run_benchmark --force
python3 -m eval.development_sets --set codex --force
```

`--force` is what makes them a re-run rather than a no-op: without it the runner
reuses each cached case and makes no call. The corpus command writes to
`runs/<model>/`; the second set's writes to `runs/codex/<model>/`, and never to
`runs/<model>/`.

## The viewer, and seven classes that skip while the run is stale

The viewer rebuilds each case's brief and **refuses a case whose rebuilt digest is
not the digest its result recorded**, rather than drawing a regenerated brief that
merely resembles the one those agents were handed. It also has a guard: when
**every** cached case is refused it raises rather than draw an empty page, because
a viewer that silently shows nothing is indistinguishable from a run that never
had cases.

So this change does not shrink the page -- it makes the page unbuildable.
`ui/dist/index.html` is left exactly as it is: it is the last true view of the old
run, and it is rebuilt after the re-run. `python -m ui.build` raises
`BuildError: every cached case was refused` until then.

The tests that read the committed run cannot run while it is refused, and they now
say so instead of failing about a run that has not been re-made yet. Seven test
classes skip -- `CommittedPageTests`, `HeadlineTests`, `JudgeVoteTests`,
`PresentationTests`, `ProvenanceTests`, `StanceProofTests`, `TheRunTests` -- and
the skip reason, with both commands and the rebuild step, is printed as well as
raised, because a skipped test's reason is only shown by a verbose run and the
quiet form is the one that gets pasted.

Three things keep this from being a way of hiding a failure:

- **The skip is conditional on exactly this state.** `ui.build.run_has_moved_on`
  asks the run's own result files whether every cached brief digest has moved, and
  it is the same comparison `build_document` acts on, extracted so the two cannot
  disagree. One matching case makes it false, the page builds, and every test runs
  as before. Nothing is unskipped by hand: the re-run clears it.
- **The refusal mechanism is still tested.** The tests that build their own run
  directory keep running and keep passing -- `RefusalTests` (3), `ReplayTests` (8),
  `StanceProofRefusalTests` (3) -- including the test that a moved digest is
  refused and the test that an unaltered case beside it is still admitted, without
  which a builder that refused everything would pass.
- **The stale state is asserted, not only skipped around.** `RunCurrencyTests`
  asserts positively that a run whose briefs have all moved is refused whole and
  that no case still matches. It holds on both sides of the re-run: while the run
  is current there is nothing to refuse and the test skips, and while it is stale
  the guard must fire.

One fixture change was needed. `RefusalTests`, `ReplayTests` and
`StanceProofRefusalTests` copy two cases out of the committed run and rely on
their recorded digests matching this code. A fixture is not making a claim about
the headline run -- it is a run directory in the shape the runner writes -- so
`fixture_run_directory` now rewrites each copied result's `brief_sha256` and each
advocate transcript entry's `user_sha256` to the digest this code builds, which is
what the runner would have recorded had it run now. Without that, every
fixture-based test would have inherited this session's brief change instead of
testing the viewer. The three `setUpClass`-based classes are untouched and still
build the real run.

`ui/dist/index.html` is **not** rebuilt by this change, and the assertion that the
committed page equals a fresh build is among the skips.

## The suite

Green on both interpreters, with the seven conditional skips reported as skips and
the reason printed. Same count, same skips, same result on each:

```
Ran 926 tests in 1639.772s

OK (skipped=10)
```

```
Ran 926 tests in 1710.280s

OK (skipped=10)
```

The count needs accounting for, because it is **lower** than the last one the log
records even though this session adds tests. The last recorded figure is **937**,
measured at `7a0836f`; the tree at `HEAD` collects **947** (the viewer's vote panel
added ten after that number was taken), and this tree collects **980**, the 33 more
being the new tests -- `tests/test_brief.py` 15, `tests/test_money.py` 17,
`tests/test_ui_build.py` 1. From 980, subtract the **54** tests held by the seven
classes that skip in `setUpClass`: a class skipped there is reported **once** and
its tests are not counted at all, so 980 - 54 = **926**. The ten skips are those
seven plus the three individual skips the suite already had. The 15 tests that ran
in `tests/test_ui_build` all passed, including the new `RunCurrencyTests` case, and
`tests/test_brief.py` gained the ERP-proximity test.
