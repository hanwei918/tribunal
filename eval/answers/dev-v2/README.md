# dev-v2: the development set for policy version 3 (drafted as base version 2) (key-side notes)

This file and everything beside it describe outcomes, which is why they live under `eval/answers/` and not with the cases.

80 synthetic cases (40 `NO_SHOW_CHARGE`, cases 1701-1740; 40 `ROUTE_DEVIATION`, cases 1751-1790; no number, dispute id or
evidence id collides with any other set), with a frozen key in `ground_truth.json` beside this file. It is **development data**: the system is tuned against it, so a figure over it
measures fit, not generalisation, and it never appears in the README results table as a generalisation figure. The
generalisation figures remain the sealed sets, run once each from a tag.

## What it is for

- Calibration of the escalation threshold (plan items 10 and 48): `split.json` names a 50-case **calibration** part on
  which the threshold is chosen and a 30-case **holdout** part on which the chosen threshold's error rate is reported.
  Choosing and reporting on the same cases would overfit the threshold, so the two parts are fixed here and never swapped.
- Exercising every clause that is new or changed in policy version 3 (drafted as base version 2): POL-NS-10 (a)-(g), POL-NS-01(d), POL-NS-05(iii),
  POL-GEN-05, POL-GEN-08, `trip_record.platform_policy`, `trip_record.events[]`, `dispute.safety_flag`.
- Regression pairs (`pairs.json` beside this file): 12 directional minimal pairs (one unit either side of a threshold, the ruling must flip)
  and 5 invariance pairs (injected text, lifetime profile counters, a harmless trace gap: the ruling must not move).
  `eval.gate` can read them directly.
- Error attribution (plan item 51): every case carries a scenario label in `manifest-meta.json` beside this file, so a miss is already
  bucketed by track and clause.

## Composition

| track | NO_SHOW_CHARGE | ROUTE_DEVIATION | what it holds |
|---|---|---|---|
| REGULAR | 16 | 16 | clauses hit squarely: verified no-show (defaults, record-carried and version-1 parameters), shortfall, never arrived, wrong entrance, pin ambiguity, unanswered contact; arithmetic refunds, below-threshold, closure exoneration, rider-requested stop, upfront quote, phantom ERP |
| BOUNDARY | 12 | 12 | 179 / 181 s; 47 / 53 m; 24 / 27 m accuracy; DRIVER_UNABLE_TO_LOCATE in radius; false marker 210 / 150 s; anti-farming 4 / 3; 19.9 / 20.3 percent; 0.76 / 0.84 km; de minimis; 90 percent full-refund line; 80 / 100 s gap; 3 / 2 deviation flags |
| ADVERSARIAL | 8 | 8 | prompt injection, profile bait, contradictory artifacts, impaired sole evidence, driver asked rider to cancel, undecidable rider track, safety flag, harmless gap; injection, uncited traffic excuse (POL-RD-13), cited-but-missing advisory, waypoint never approached, trip-id mismatch, refund above 150, pooled trip |
| CLAUSE | 4 | 4 | POL-NS-10 (a) (b) (g) (e); POL-RD-05 with and without a re-quote, POL-RD-09(2), POL-GEN-05 |

Expected rulings: FULL_REFUND 24, PARTIAL_REFUND 20, DRIVER_COMPENSATION 14, NO_ACTION 12, ESCALATE 10.
Difficulty labels follow the corpus vocabulary: EASY 22, HARD 40, REVERSAL 8, INDETERMINATE 10.

## How it was made, and how the key was checked

`eval/synth/make_dev_set.py` (standard library, seed 20261007, no model call) renders every case from a scenario whose
expected outcome is fixed first; the evidence is then generated to carry exactly those facts (GPS traces by geometry,
fares by the policy's own arithmetic, chat from templates). Re-running the script reproduces every byte.

`eval/synth/verify_dev_set.py` is the second derivation: it loads every case through `tribunal.loader`, builds the brief with
`tribunal.brief`, reads the deciding figures the brief derives (arrival run, qualifying fixes, rider presence, deviation
excess and status, the POL-RD-02 / POL-RD-03 / POL-RD-11 money figures) and applies the clause rules to them. The key is
accepted only where that derivation agrees on all four graded fields; at the time of writing it agrees on 80 of 80.

Generator, grader and prompt author are different things: the generator is a script, the grader is `eval/grade.py`
against this key, and no prompt was written with these cases in view.

## Three things to know before running it

1. **Every no-show record carries `trip_record.platform_policy`.** 36 records carry the published figures
   (`source` PLATFORM-PUBLISHED-2026-10-07: 180 s free wait, SGD 4.50 net / 6.61 gross), 1 carries a record block
   (RECORD-PLATFORM, the shape of the organisers' sample: 300 s / 480 s / SGD 5.00), 3 carry the version-1 authored
   parameters (AUTHORED-V1, 300 s or 480 s by zone, greater-of fee). The figure in force is always written on the record;
   nothing depends on how a missing block would be resolved.
2. **Three cases flip with the version-2 code change.** 1717, 1718 and 1725 are decided by the 180 s free wait their
   block states. The version-1 brief ignores the block and reads `minimum_dwell_sec` 300 by zone, so until plan item 41 is
   applied the system is expected to miss 1718 and 1725 and to get 1717 right for the wrong reason. `EXPECTED.md` marks them.
3. **GPS_GAP weights and admissibility notes.** The three cases with a trace gap carry the version-1 pre-pass weight
   (`GPS_GAP` 0.6, plus `LOW_COVERAGE` under 90 percent coverage); no key depends on the weight. No `admissibility.notes`
   string names a clause or a distance to the pin, unlike the corpus, because the notes reach the model.

## Independent review

Thirty-six keys (sixteen, then twenty more including four from the extension) were re-adjudicated by two reviewers who
had not seen the generator, from the clause text and the evidence alone. Two disagreements were found and fixed before
release: 1713 (the driver's silence after the rider's message engaged POL-NS-04, which pays no goodwill; the chat now
carries a driver reply, so POL-NS-03(ii) governs as intended) and the former 1731 (a trip record and a trace contradicting
each other on dwell is also the fact pattern POL-NS-05 resolves, so the key could be read either way; the scenario was
replaced by an unambiguous POL-NS-09(c) escalation). Leaks the reviewers found were closed: `amount_contested_sgd` had
equalled the POL-RD-02 arithmetic to the cent; an absent `events` block had been unique to one case; the boundary pair's
last fix sat off the sampling cadence; an upfront-quote ledger did not sum to its total; rider-cancelled records carried
a negative `wait_time_min`. Two readings the policy text leaves open are recorded in the datasheet (items 8 and 9).

## Isolation

`data/external/dev-v2/` holds only the cases, `index.json`, `split.json`, `CANARY.txt` and a short note;
`tests/test_dev_v2.py` asserts that no file there names a ruling value. `CANARY.txt` holds a marker string that must
never appear in `prompts/`, `tribunal/`, `policy/`, `precedents/` or in a run directory made from another set. The case
files carry none of the five evaluation-only keys, no CJK text and none of the sealed sets' vocabulary. This directory is
under the same isolation rule as every other key (`tests/test_answer_isolation.py`).

## Files

| file | holds |
|---|---|
| `ground_truth.json` | the key, one entry per case |
| `EXPECTED.md` | one row per case: expected ruling, amounts, referrals, clauses, split, flip flag |
| `pairs.json` | the minimal pairs and the relation each must satisfy |
| `manifest-meta.json` | seed, canary, per-case track / scenario / pair / derived figures |
| `DATASHEET.md` | the datasheet (motivation, composition, process, limitations, maintenance) |
| `data/external/dev-v2/case-01701.json` ... `case-01790.json` | the cases |
| `data/external/dev-v2/index.json`, `split.json`, `CANARY.txt` | manifest with sha256, calibration / holdout numbers, contamination marker |
