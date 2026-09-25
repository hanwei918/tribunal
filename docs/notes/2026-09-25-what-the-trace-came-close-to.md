# What the trace came close to

**2026-09-25.** POL-RD-09(4) decides a gantry line **by geometry**, and the
brief did not carry the geometry. This note records the fact that was added to
close that gap, what it does and does not decide, the figures it produces on the
real cases, and what it makes stale.

It follows `docs/notes/2026-09-25-the-second-development-sets-first-run.md`,
which records the run whose two misses this fact is the fix for.

## The failure

Both of the second development set's misses are one error. POL-RD-09(4) says:

> A gantry is matched to the trace by comparing `erp_gantry.lat` and
> `erp_gantry.lng` against the trace, treating any fix within 250 m of the
> gantry as a crossing; where an `erp_gantry` carries no coordinates the match
> is undecidable on the record, the line is treated as matched, and the ruling
> must say so.

The clause tests a **distance**. The brief replaced the trace's coordinates with
derived facts, and no derived fact said how close the trace came to any gantry.
So the judge reached for the nearest thing the brief did carry — the
`on_optimal_route` flag — and read it as though it were the geometric test.

On `9111` the judge wrote that the SGD 2.00 line *"is not a phantom line — the
vehicle crossed it on the detour"*, an assertion about the trace's geometry with
nothing in the brief to support it; the line is **912.0 m** from the nearest fix.
On `9113` the judge took `on_optimal_route: true` as a match and never examined
the Pelton line at all; it is **834.2 m** from the nearest fix.

This is the same failure as the accumulated dwell on corpus case `214`: the
model could not see the fact because it was never computed. Corpus `115` and dev
`9114` were decided correctly only because the driver conceded he never went
there, so the model never had to do the geometry. The remedy is not a prompt
change; it is to compute the fact and put it in the brief.

## The fact

`tribunal.facts.gantry_proximity` takes the trace's fixes, a fare breakdown's
`erp_gantries` lines, and the trace's recorded `gaps`, and returns one record per
line. `tribunal.brief` publishes it as `erp_gantry_proximity` inside the GPS
trace's `derived` facts, beside `driver_track`, `rider_presence`, `arrival` and
`deviation`, in the same `_sourced` form: every value carries the `evidence_id`
it came from.

For every `erp_gantries` line:

- **The nearest fix.** Its index in the trace's own order, its `ts`, and the
  distance in metres from the gantry to it — computed with `facts.haversine_m`,
  the same function the other derived facts use.
- **Whether a sampling gap brackets the closest approach**, and the closest
  distance from the gantry to the straight line across any such gap. A crossing
  that happened inside a gap must not read as a gantry the trace never passed.
- **Where the line carries no coordinates**, the block says so and computes
  nothing, because the clause treats such a line as matched.

A gap brackets the closest approach under either of two conditions, both of
which mean the trace cannot bound how close the vehicle came:

1. **The nearest observed fix is one of the gap's two bounding fixes.** The
   observed minimum then sits at the edge of a hole, so it is not a bound on the
   continuous path.
2. **The straight segment across the gap passes at least as close to the gantry
   as the nearest observed fix does.** The unobserved stretch could contain an
   approach at least as close as any fix shows.

Both are reported; `across_gap_distance_m` is the smallest chord distance over
the gaps that qualify, and `bracketing_gaps` names each one with its `from_ts`,
`to_ts`, `duration_sec` and chord distance.

The chord distance is taken on the sphere, in `facts.point_to_segment_m`, not on
a local flat projection, so the figure is the same one `haversine_m` gives for a
point that happens to lie on the segment. Where the perpendicular falls beyond an
end, the nearest point is that end.

## What it does not do

**It reports distances and decides nothing.** There is no `crossed` field, no
`matched` field, and no verdict of any kind — `test_8` pins the block's key set
so that adding one would fail a test.

**No threshold appears in the code.** POL-RD-09(4)'s radius is the clause's, and
the judge applies the clause. `tests/test_facts.py` already refuses a list of
policy numbers as literals in `facts.py`; **250 was added to that list**, and
`test_12` refuses it in `brief.py` as well.

**No policy file and no prompt was changed.** The clause text is as it was; the
prompt set is untouched, so this change moves the **brief channel only**.

## The figures, on the real cases

Every figure below is the brief's own published value, and every one was checked
against an independent haversine over the raw fixes — the `atan2` form, written
out in the test rather than imported, so the check is arithmetic the test does
itself.

| case | line | nearest fix | `on_optimal_route` | distance |
|---|---|---|---|---|
| `115` | KPE (Defu Flyover towards ECP) | fix 136 | true | **44.5 m** |
| `115` | AYE (Alexandra Rd towards Tuas) | fix 0 | false | **5419.3 m** |
| `103` | CTE (Braddell Rd towards City) | fix 33 | false | **0.0 m** |
| `103` | CTE (Moulmein Rd towards City) | fix 74 | false | **40.2 m** |
| `106` | CTE (Braddell Rd towards City) | fix 34 | false | **0.0 m** |
| `106` | CTE (Chin Swee Rd tunnel, towards City) | fix 105 | false | **24.1 m** |
| `114` | PIE (Kim Keat Link towards Tuas) | fix 93 | **true** | **0.0 m** |
| `114` | PIE (Adam Rd towards Tuas) | fix 152 | false | **8.8 m** |
| `9111` | Pioneer Road inbound | fix 15 | **true** | **912.0 m** |
| `9111` | Tuas South Avenue 8 loop | fix 40 | false | **1645.7 m** |
| `9113` | Pelton lawful diversion entry | fix 13 | **true** | **834.2 m** |
| `9113` | Industrial loop exit | fix 71 | false | **223.2 m** |
| `9114` | Bukit Merah Central westbound | fix 65 | false | **7482.1 m** |

Three things this table shows that the flag could not.

**The flag does not track the geometry.** `114`'s crossed line is flagged
`on_optimal_route: true`; `103`'s and `106`'s crossed lines are flagged `false`.
`9111`'s two phantom lines are flagged `true` and `false` respectively. The flag
separates the right answers on `9111` only by luck, and on `9113` it points the
wrong way: the line the key calls phantom is the one flagged `true`.

**`9113`'s other line is close.** The Industrial loop exit line is 223.2 m from
the nearest fix, so the clause's test matches it — and it is still not refunded,
because POL-RD-09(1) makes it already comprehended as an off-optimal line. The
block lets a reader tell those two apart; the flag does not.

**The distances are large where the key says phantom.** 912.0 m, 834.2 m and
7482.1 m, against 44.5 m, 0.0 m and 8.8 m where the trace passes.

## The gap path is not exercised by the real data

**No case that carries an `erp_gantries` line also carries a sampling gap.** The
corpus's gaps are in `110`, `210` and `211`; the second set's is in `9115`. None
of those four has a gantry line. So on the real cases
`gap_brackets_closest_approach` is `false` and `across_gap_distance_m` is `null`
throughout, and the gap code is exercised by `test_11`, which supplies a trace
with a hole rather than relying on one existing.

That is stated rather than glossed because it is a limit on the evidence: the
gap path is correct by construction and by test, and it is **not** validated by
any real case in either development set.

## What this makes stale

The block is emitted **only where the fare breakdown carries a gantry line**, so
a case without one gets no block and its brief is untouched. Read from the code —
`DevelopmentSet.load_case`, then the artifact's `erp_gantries` — the affected
cases are:

- **corpus** (`eval/answers/ground_truth.json`, `runs/deepseek-deepseek-flash/`):
  **`103`, `106`, `114`, `115`** — 4 of 29
- **second set** (`eval/answers/codex/ground_truth.json`,
  `runs/codex/deepseek-deepseek-flash/`): **`9111`, `9113`, `9114`** — 3 of 15

Confirmed two ways, both from the code:

1. **By digest.** Every brief was built from the committed tree and from the
   working tree and the two digests compared. **Seven of the forty-four changed,
   and they are exactly those seven; the other thirty-seven are byte-identical.**
2. **By the cached runs.** The runner records `brief_sha256` per case, so each
   cached result can be asked whether it still belongs to this code. The corpus
   run now reads **25 of 29 current, stale `103`/`106`/`114`/`115`**; the second
   set's run reads **12 of 15 current, stale `9111`/`9113`/`9114`**. No case
   reports `unknown`.

These seven are **stale on the brief channel only**. The prompts are untouched,
so every other recorded figure stands and the corpus headline is unchanged.

**They cannot be replayed.** `--replay-advocates` reuses the advocate outputs a
run recorded and calls only the judge. Those outputs were produced from the old
brief, so they are answers to a question the advocates are no longer asked; a
replay of one of these seven would be refused by `--replay-check`, because the
recorded `brief_sha256` no longer matches. The advocates must see the new fact,
which means a **full re-run of the seven**.

The commands, one per development set. **They were not run for this note.**

```
python3 -m eval.run_benchmark --cases 103,106,114,115 --force
python3 -m eval.development_sets --set codex --cases 9111,9113,9114 --force
```

`--force` is what makes them a re-run rather than a no-op: without it the runner
reuses each cached case and makes no call. The corpus command writes to
`runs/<model>/`; the second set's writes to `runs/codex/<model>/`, and never to
`runs/<model>/`.

## The viewer, and three assertions that had to be re-expressed

The viewer rebuilds each case's brief and **refuses a case whose rebuilt digest
is not the digest its result recorded**, rather than drawing a regenerated brief
that merely resembles the one those agents were handed. So the four stale corpus
cases cannot be shown, and `ui/dist/index.html` — which is committed and whose
bytes must equal a fresh build — had to be rebuilt. It now carries **25 cases**
and names `103`, `106`, `114` and `115` in its refusal list. A re-run of those
four restores all 29.

Three assertions in `tests/test_ui_build.py` were written against the state the
repository was in *before* this change, and are now re-expressed as invariants
that hold on both sides of the re-run:

- `test_every_case_in_the_run_is_present` → `..._is_either_shown_or_refused`.
  It no longer asserts that nothing is refused. It asserts that the refused set
  is **exactly** the set whose recorded `brief_sha256` no longer matches the
  brief this code builds — so a builder that refused a case whose brief had not
  moved still fails it, and after the re-run it asserts an empty refusal set.
- `test_every_case_carries_a_proof` asserted `29` embedded cases. It now asserts
  that the embedded cases are the document's own, which is the property that
  actually mattered: a refusal cannot silently shrink the set the proofs are
  checked over.
- `test_every_claim_carries_a_citation_the_viewer_can_open` pinned the run's
  total claim count at `500`. It now asserts that both advocates of every
  admitted case spoke and that the count is non-zero. Pinning the total made a
  refusal look like a missing claim.

No other assertion in the suite reads the corpus run's briefs, and the corpus
figures themselves are untouched: the run's recorded results are what they were.
