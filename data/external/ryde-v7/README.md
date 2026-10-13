# `ryde-v7` — the organisers' two samples, converted for policy version 7

Two cases, converted from the organisers' own sample material by
`eval/external/ryde/convert.py --policy-version 7`. The set exists so that Ryde's
Dispute Resolution Policy v2.1 — the policy at `policy/v7/` — can be run against
the only cases the organisers supplied, at the version that policy is written
for.

| case | source | section of the source | category | what it is |
|---|---|---|---|---|
| `case-00902.json` | `DISP-001.md` | Section 1, Route Deviation Policy | `ROUTE_DEVIATION` | a reroute from the recommended PIE route that the driver did not notify |
| `case-00903.json` | `DISP-002.md` | Section 2, No-Show & Cancellation Policy | `NO_SHOW_CHARGE` | a no-show cancellation fee charged after the free wait |

`index.json` is the set's own index. It is **not** `data/index.json` and is never
merged into it: the corpus manifest still indexes the 29-case corpus the
benchmark measures, and adding a converted case to it would change that corpus.
The set is loaded by number through `tribunal.loader.load_external_set_case`,
which holds each case file to the sha256 its index entry records.

## The source files are the organisers' material, and are not committed in full

`DISP-001.md` and `DISP-002.md` are the organisers' own sample documents. They
are **answer-bearing**: each states an expected ruling and argues for one side.
They are not agent input and they are not committed here in full.

What is committed is the converted case, which is answer-free, and the mapping
record beside it, which lists every field of the conversion and why. The
organisers' words do not travel: `DISP-002.md` sits under `eval/external/ryde/`,
which is under the same boundary as the answer key, and `DISP-001.md` was
supplied in the owner's scratch directory, which is not in a clean clone. The
converter reads them where they are and writes only into `data/external/`.

The two mappings are `mapping-00902.json` and `mapping-00903.json`. Each records
every source item the conversion read, whether it was copied or judged, and — for
every item that was **not** carried — the reason it was not. A mapping with a
hole in it is refused rather than written: the converter runs the coverage check
before it writes anything.

## `DISP-003` is not converted, and here is why

The organisers supplied a third sample, `DISP-003.md`: a fare dispute, of the
kind v2.1 Section 3 governs. It is **not** converted, and it is not in this set.

The reason is the schema and not the policy. This repository's case format
carries two dispute categories — `ROUTE_DEVIATION` and `NO_SHOW_CHARGE` — and
`tribunal.loader.CATEGORY_POLICY_FILES` maps each to the policy file it selects.
A fare dispute has no category to declare and no policy file to select, so a
converted case declaring one would be refused by the loader rather than loaded.
The category that would carry it, `FARE_DISPUTE`, does not exist here.

That is consistent with what v2.1 says about the dispute: POL-GEN-24 states that
fare and surge disputes are "not adjudicated by the AI in this version" and are
routed to human review with the section that governs them named in the case file.
A case the policy sends to a person is a case the pipeline is not asked to rule
on, so there is nothing for a conversion to feed.

## What each case carries

Both cases are converted for policy version 7 and both carry the version-7
brief's inputs:

- `case-00902.json` (DISP-001) carries both of the platform's recorded distances
  on the trip record — 24.8 km actual against 20.5 km on the recommended route —
  the per-kilometre rate POL-RD-24 multiplies by, read out of the fare
  breakdown's own note, and one `TRAFFIC_ADVISORY` per traffic condition in the
  source. The contested amount is the rider's own requested refund, the excess
  fare of 6.50, which is what POL-GEN-22 reads to pick its band.
- `case-00903.json` (DISP-002) carries the scheduled time and the arrival time
  POL-NS-21's free wait runs between, the chat log POL-NS-23's contact reading
  counts, and the source's own `fraud_flags` counter on both profiles, which is
  the field POL-GEN-22 reads where it raises the bar to 0.95.

Each case's own mapping records every judgement behind those figures, including
the three the route-deviation conversion had to make: which traffic conditions
intersect the recommended route, that the pickup's zone class and the vehicle's
tier are stated assumptions rather than readings, and that the source's traffic
condition types are the source's own words rather than this corpus's vocabulary.

## The key

`eval/answers/ryde-v7/ground_truth.json` holds Ryde's own expected outcomes for
the two samples, in this repository's fields: 902 is `PARTIAL_REFUND` of 3.44
with no driver compensation, and 903 is `DRIVER_COMPENSATION` of 5.00 to the
driver, which is what v2.1 2.2 makes of the fee the record charged. It is a
second answer key under the same boundary as `eval/answers/ground_truth.json` and
nothing under `tribunal/` may read it.

The set is **development data**. It is registered in
`eval/development_sets.py` with `policy_base=7` and `policy_version=7`, and it is
outside `DEVELOPMENT_SETS` and outside `ALL_SETS`: `--set all` does not run it,
the combined figure does not sum it, and it is never a generalisation figure.
