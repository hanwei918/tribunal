English translation of the archive's `README.md` (sha256 `ad4826f9bd81c6a0997d8fd2c7d5e44739b9d69ce37db021a540b4484c50a7dd`); the original, in Chinese, stays outside the repository.

# Tribunal sealed test set v1 (24 cases)

**Purpose**: the final evaluation set, run only once after the freeze. The case files carry no answer of any kind; the answer key lives at `eval/sealed/`, isomorphic to the dev set's `data/answers/`.

**Authoring independence**: the author had no contact with the dev set's prompts, missed cases or tuning process; the set was authored from `data/SCHEMA.md`, `data/schema.json` and `policy/*.json` alone. No case's content is rewritten from the existing 29 cases.

## Contents

```
data/sealed/
  index.json               the list the agent may read (identity fields only)
  cases/case-003xx.json    ROUTE_DEVIATION x12
  cases/case-004xx.json    NO_SHOW_CHARGE  x12
eval/sealed/
  ground_truth.json        the full answer key (expected_ruling / amount / driver_comp / referrals / governing_clauses / difficulty / rationale)
  eval_index.json          the reduced index used for grading
  MANIFEST.json            hashes + distribution + the sealed protocol
```

`case_set_sha256`  `5ae223770b880bb4add85b474da1274b46a853ecaed6ee7c968776c4838ce5f2`
`answer_key_sha256` `412d60bdf207b2be7f66986f40dc4d517b084df7e45dc4c12b566686cddd7f6d`

## Validation status

- 24/24 pass `data/schema.json` (`$defs/case_file`)
- 24/24 pass every cross-check in SCHEMA.md §9: case-number agreement, the six singletons plus dense advisory numbering, the admissibility invariants (status ↔ issues ↔ payload ↔ weight recomputation), the Family E related ids, the fare identity, timestamp causality, the recomputed derived fields (deviation_pct / wait_time_min / coverage_pct / trace_distance_km / intersects_route), dense msg_id, the `amount_contested` bounds, the answer key's amount invariants, INDETERMINATE ⇒ ESCALATE, the clauses existing and licensing the ruling values, and the difficulty distribution within the schema's bounds
- The case files' and index.json's raw bytes carry none of `ground_truth` / `expected_*` / `difficulty` / `governing_clauses` / `rationale`
- Each case's ruling figures (the trace's excess percentage, the POL-RD-02 recomputation, the dwell seconds at the first qualifying fix, and the distance and speed at the arrival marker) have been independently recomputed from the generated data and checked against the rationale

## Distribution

| | RD | NS | total |
|---|---|---|---|
| NO_ACTION | 3 | 1 | 4 |
| PARTIAL_REFUND | 5 | 0 | 5 |
| FULL_REFUND | 1 | 6 | 7 |
| DRIVER_COMPENSATION | 1 | 2 | 3 |
| ESCALATE | 2 | 3 | 5 |

Difficulty: EASY 4 · HARD 14 · REVERSAL 3 · INDETERMINATE 3

## Trap coverage

| trap | case |
|---|---|
| Profile decoy (the lifetime fields are poor but this case is justified; near-synonym fields) | 312, 412, 409 |
| Verbosity decoy (the longer and more emotional party is the one that is wrong) | 301, 308 (rider); 402, 412 (driver-side statement) |
| Threshold edge | 303 (trace 20.3% vs trip 20.0%), 407 (298 s), 401 (490 vs 480 s) |
| Contradictory evidence → escalation | 311 (RD-10(7)), 410 (NS-09(b)) |
| Missing decisive evidence | 307 (tunnel 240 s gap), 411 (GPS MISSING) |
| Double-counted ERP | 302 |
| ERP refunded singly after exoneration | 304 |
| Phantom gantry | 310 |
| upfront / pool, wrong model | 308, 309 |
| Compound ruling (refund the rider + compensate the driver) | 404 |
| Counterparty NO_ACTION (the driver appeals, the fee is already refunded) | 408 |
| Reading only the chat misses an in_app_calls | 406 |

One deliberate difference from the dev set: **`admissibility.notes` only describes and does not judge** (for example it does not write "driver holds the guardhouse for 585 s"). The dev set's notes carry judgemental hints, which is why the note-stripping ablation's result on dev can be compared with this set.

## Protocol of use

1. Before the model, the prompt and the policy are frozen, do not run the set and do not look at the case content
2. Before running, verify `case_set_sha256`
3. Run only once, k=3
4. Reporting convention: the **agreement** rate against this answer key (not called an "accuracy"), split by the four fields, with a 95% confidence interval, k-consistency, and a classification of the misses
5. The official Ryde sample is reported on a line of its own
6. After the run, any change turns this set into a dev set — no going back to tune, no re-running

## Suggested: a blind-labelled subset

Ask someone who took no part in authoring the set and no part in tuning the prompt to label the following 8 cases independently, **without looking at** `ground_truth.json` (4 from each category, covering all four difficulties): 303, 304, 307, 310, 402, 404, 408, 410. The agreement between the two sets of answers is reported as the "human ceiling" line.

## Known limitations

- The GPS traces are polyline interpolations, not snapped to the road network; `schema.json` checks only the bounding box, and `validate_dataset.py` does not check road geometry
- The ERP gantries' time bands and directions are set by the narrative and are not checked against the real ERP timetable
- Juror/human-in-the-loop, multi-party carpooling and image evidence are outside this set's scope
- This set was never run through `tools/validate_dataset.py` (that tool is outside the workspace); the set's own `gen/validate.py` reproduces every one of §9's 21 rules that can be executed offline
