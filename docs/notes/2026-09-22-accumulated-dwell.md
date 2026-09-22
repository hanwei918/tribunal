# POL-NS-06(i) — the accumulated dwell the brief never computed — 2026-09-22

## Summary

A benchmark run got case 214 wrong because the brief did not carry the fact the case turns on.
`deepseek/deepseek-flash` ruled **FULL_REFUND 4.00** where the answer is **DRIVER_COMPENSATION 3.20**,
and it was not a model failure: the brief gave it a longest continuous hold of **185 seconds against a
300 second minimum**, which refunds as strict liability under POL-NS-06, and never told it that
POL-NS-06(i) permits the two holds to be added. **170 + 185 = 355**, and there is no shortfall.

The defect was recorded before it was fixed, in the wrong words. `eval/verify_rationales.py` says, of
its own reconciliation:

```
POL-NS-06(i) interval summing and POL-NS-05's marker correction are not applied here,
so a case that depends on either will not reconcile.
```

That reads as a caveat on a checker. It was a description of a hole in the evidence the agents
receive, and case 214 falls through it. The checker's sentence is still true of the checker; what has
changed is that the agents now receive the fact.

## What the clause requires

POL-NS-06(i) permits dwell to be accumulated across separate in-geofence intervals within one pickup
attempt where:

1. the trace shows the driver leaving and re-entering the arrival radius without at any point
   travelling more than the stated distance from the pin;
2. **and** a `traffic_advisory` whose geometry covers the pickup road and whose active window covers
   the waiting period carries a `type` of `KERB_RESTRICTION`, `ENFORCEMENT`, `CLOSURE` or `ACCIDENT`;
3. **and** that advisory is present and populated — a MISSING `traffic_advisory` makes limb (i)
   unavailable, and asserting it against a MISSING artifact triggers POL-NS-09 rather than exonerating
   anyone.

Limb (ii) is the limit: an advisory never reduces the required minimum and never excuses a shortfall on
its own. It only permits the intervals to be summed.

The conditions are conjunctive, so more than one can fail at once and **every** failure is reported. A
judge told only the first reason may spend its argument answering a condition the other side then
concedes, when a different one decides the limb outright.

## What the answer key says, and what the code now computes

Both cases were read from `eval/answers/ground_truth.json` before any code was written, and the
computed facts match the key's own numbers exactly.

| | case 214 (limb applies) | case 211 (limb does not) |
|---|---|---|
| key | "stationary ... 18:44:45 to 18:47:35, **eighteen fixes** ... **170 seconds**; and 18:49:35 to 18:52:40, **twenty fixes** ... **185 seconds**. Between them he drove one loop of Orchard Turn, reaching **179.0 m** from the pin at most. ... Summed, the two intervals give **355 seconds**" | "two runs of **220 and 112 seconds**, the longer 80 seconds short of the minimum; and they may not be summed to **332**, because ... **EV-ADVIS-00211-01 is MISSING**" |
| computed | runs 170 s (18 fixes) and 185 s (20 fixes), accumulated **355.0**, excursion **178.95 m**, limb **available** | runs 220 s (23 fixes) and 112 s (12 fixes), accumulated **332.0**, limb **unavailable**, reasons `excursion_unmeasurable` and `advisory_missing` |

Case 214's excursion is 178.95 m, which is the key's 179.0 m to one decimal place. It sits inside the
300 m leash, which is read out of POL-NS-06's own prose, not typed in.

## The measurement that decided the run predicate

This is the part worth recording, because it was not obvious and the clause does not say it outright.

`longest_qualifying_run` counts a run of *in-geofence* fixes. Under that definition case 214's first
hold runs from 18:44:45 to **18:47:45** and is **180 seconds**, not 170, and the sum is 365, not 355.

The fix at 18:47:45 is 53.6 m from the pin at 22.7 m accuracy. It passes the radius test and the
accuracy filter both. It is excluded because the trace reports the driver at **42.6 km/h**. The
18:47:35 boundary is a *speed* boundary, and the key's word for these runs is "**stationary**".

POL-NS-01 limb (c) requires the driver to have "held position inside that geofence", and POL-NS-05
fixes the line between holding and moving at a named speed. So a holding fix is in-radius, within the
accuracy filter, and below that line. The line is read from POL-NS-05's prose for the same reason the
leash is read from POL-NS-06's: a silent default would be a policy number hard-coded in `tribunal/`.

On this corpus the distinction is safe. Every fix inside any arrival radius is either at zero reported
speed or at 12.0 km/h or above, and **13 of the 14 NO_SHOW_CHARGE cases produce the identical answer
under either rule**. Only case 214 differs, and that difference is the whole point of the case. A test
asserts the corpus-wide agreement, so a future case that separates the two readings fails loudly
rather than silently picking one.

## What was added

**`tribunal/facts.py`** — `qualifying_runs`, `_run_index_ranges`, `_run_summary`, `_excursion_spans`,
`_gap_overlaps`, `_advisory_failures`, `_advisory_candidates`, `_unavailable_accumulation`, and
`accumulated_dwell`. Seven condition constants name the ways limb (i) can fail. No policy number
appears as a literal: the leash, the four type values and the motion line are all parameters, and the
literal test now also forbids the motion line.

Two decisions inside the algorithm:

- **A hole in the trace is a transition into a new run.** Case 211's two holds are separated by the
  trace's own recorded 168 second `gaps` entry, not by a fix outside the 50 m radius. Both fixes at
  the boundary are in radius with usable accuracy. Without the split the hole is bridged and the same
  trace reports **one 500 second hold**, which clears the minimum outright. This falls out of
  `GPS_TRACE.gaps`, a summary field already carried in the brief, and "the run is broken by a hole" is
  the clause's own "separate intervals" language.
- **A run of one fix is not an interval.** Case 214 has a lone stationary in-radius fix at 18:44:05
  before the driver settles. It has zero duration, contributes zero dwell, and is not something
  limb (i) can accumulate. Without this, case 214 reports three runs rather than two.

**`tribunal/brief.py`** — `_no_show_thresholds` reads the three prose-only values out of the loaded
clause text and **raises** if any of them cannot be found, exactly as `_deviation_thresholds` does for
POL-RD-01; it returns `None` for a policy with no POL-NS-06 clause, which is how a ROUTE_DEVIATION case
is recognised. The `accumulated_dwell` sub-block lands in the existing `arrival` block, every derived
value tagged with its `evidence_id` and every threshold with its `policy_id` and `clause_id`.

It publishes, for case 214, not only `accumulated_sec: 355` but `longest_run_sec: 185`, both runs with
their own timestamps and fix counts, the excursion with its 179.0 m, and a `limb` object that says
**why** summing is permitted — naming `EV-ADVIS-00214-01`, its type and the leash. A judge told 355
without the reason cannot cite the clause. For case 211 the block still reports the 332 second sum and
then refuses it, with the reason naming `EV-ADVIS-00211-01` as MISSING.

The block is not free, and the cost is worth stating: it adds **1,661 characters (~415 tokens)** to
case 208's brief, **2,221 (~555)** to case 214's and **2,379 (~595)** to case 211's. Case 208's brief
is 48,143 characters, so the fact costs about 3.5 % of the package, on the one case category that has
a POL-NS-06 clause at all. ROUTE_DEVIATION cases pay nothing: their policy has no such clause and the
extractor returns `None`.

## Tests

Twenty-five new tests, all against the real files. Suite **476 → 501 tests**, `OK (skipped=1)`.

- case 214: both hold lengths asserted individually, not only their sum; 18 and 20 fixes; 355 against a
  300 second minimum; the longest hold alone short of it; the excursion at 179.0 m inside the 300 m
  leash; the limb available on the real advisory; the advisory's `intersects_route` and
  `overlaps_trip_window` read from the artifact.
- case 211: 220 and 112, summing to 332 and refused; the reason names the missing advisory; the hole is
  reported and the excursion is `null` rather than filled in with a default.
- the boundary is pinned by evidence, not by comment: the 18:47:45 fix is asserted to pass both the
  radius and accuracy tests and to be excluded on speed; the lone 18:44:05 fix is asserted stationary
  and not an interval.
- the corpus: every case computes, `accumulated_sec` equals `longest_run_sec` whenever there is one
  hold, the two facts agree for every gapped-free case with one hold, and **only case 214 offers the
  limb**.
- the extractor raises rather than defaulting, once per missing line, and the four type values do not
  appear in `brief.py`'s source at all.

Five mutations, each RED with the suite green beforehand, every file restored and verified
byte-identical by checksum:

| Mutation | Result |
|---|---|
| availability always `True` | 11 failures/errors |
| runs never split at a recorded gap | 3 failures |
| a moving fix counts as holding position | 5 failures |
| the leash comparison inverted | 9 failures |
| a one-fix run counts as an interval | 4 failures |

## Left alone, and why

- **The judge prompt is untouched.** Cases 107 and 211 also missed, for a different reason — the judge
  does not treat a party's own admission as an independent carrier of a deciding fact. That is a
  separate change, and case 211 is expected to remain wrong until it is made.
- **`longest_qualifying_run` still bridges a hole.** It reports **500 seconds** for case 211 where the
  key says the longer observed run is **220**, and 255 seconds for case 210 where the trace's own gaps
  separate every fix. It is the same defect class as the one fixed here, and it now sits beside a block
  that contradicts it. It is not fixed in this session because it is a change to an existing published
  fact, it moves two cases rather than one, and a correction to an existing fact deserves its own
  commit. **This is the next change to make.**
- **`eval/verify_rationales.py` still says POL-NS-06(i) is not applied.** The sentence remains true of
  that tool, which computes its own two dwell quantities; it could now reconcile case 214, and the
  caveat is the record of why it could not before.
- **`runs/*/report.md` was not rewritten.** Those files are the evidence of what the run printed. No
  benchmark was executed in this session and no model was called.

## Follow-up, same day — the shortfall was measured on a basis the limb refuses

One field, in `tribunal/brief.py` only. Nothing else in the object was touched.

`shortfall_sec` was computed unconditionally as `minimum_dwell - accumulated_sec`. That basis is
lawful only where limb (i) is available. Case 211 published:

| field | before | after |
|---|---|---|
| `accumulated_sec` | 332.0 | 332.0 — unchanged, so the refused sum stays visible |
| `longest_run_sec` | 220.0 | 220.0 |
| `shortfall_sec` | **-32.0** | **+80.0** |
| `shortfall_basis` | *(absent)* | `longest_run_sec` |
| `limb.available` | false | false |

A negative shortfall reads as "no shortfall" where the driver is in fact **80 seconds short**, and it
sat in the block's most directly usable field beside an availability flag saying the sum was refused.
The arithmetic was right and the number was wrong, because it was computed on a basis the policy does
not permit — the failure the escalation-rate lesson already records, one layer down.

The shortfall is now measured from the dwell the limb permits, and the basis is published beside the
number, named by the field it came from: `accumulated_sec` where limb (i) is available,
`longest_run_sec` where it is not. Both dwell figures stay in the block either way, because an
advocate may legitimately argue about whether the limb should have been available.

Case 214 is unchanged: `shortfall_sec` **-55.0** on the `accumulated_sec` basis.

The corpus invariant is now asserted, and its absence is why the suite was green: for every case
carrying the block, `limb.available` decides which figure the shortfall is measured from, and the
number equals the minimum minus that figure. Case 211's shortfall is asserted at +80 on the
longest-run basis, case 214's at -55 on the accumulated basis.

Two mutations, each RED with the suite green beforehand, the file restored and verified
byte-identical by checksum: the shortfall measured off the sum unconditionally (2 failures), and the
basis always the accumulated figure (2). Suite **501 → 502 tests**, `OK (skipped=1)`. No model was
called.
