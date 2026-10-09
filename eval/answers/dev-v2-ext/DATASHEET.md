# Datasheet: dev-v2-ext (after Gebru et al., "Datasheets for Datasets")

This is the 120-case extension of dev-v2 (2701-2760 NO_SHOW_CHARGE, 2801-2860 ROUTE_DEVIATION): variants of the same 80 scenarios with the movable parameters moved (place, time, geometry, profiles; dwell moved only in the direction that cannot change the outcome; surge and excess factor on the arithmetic-refund scenarios). Every BOUNDARY and ADVERSARIAL scenario has two variants, every other scenario one. dev-v2 and dev-v2-ext together are the 200-case set: tracks REGULAR 64 / BOUNDARY 72 / ADVERSARIAL 48 / CLAUSE 16, rulings FULL_REFUND 58 / PARTIAL_REFUND 49 / DRIVER_COMPENSATION 36 / ESCALATE 29 / NO_ACTION 28, split calibration 133 / holdout 67 over all 200 (19 ESCALATE cases in calibration), 33 directional pairs and 5 invariance pairs in all, nine flip cases (1717, 1718, 1725, 2717, 2718, 2725, 2741, 2742, 2749). No identifier is shared with dev-v2. Run dev-v2 first and read its misses: the variants are parameter noise around the same scenarios, so their value is in the thresholds they let you choose, not in new failure modes. Everything below is the dev-v2 datasheet and applies to the variants unchanged.


## Motivation

**Why was it created?** Policy version 3 (drafted as base version 2) added or changed eleven clauses and three record fields. No existing set
exercises them, the escalation threshold needs a calibration set that is separate from the set it is reported on, and the
regression gate needs minimal pairs whose expected relation is known. The sealed sets cannot serve any of these purposes
without ceasing to be sealed.

**Who created it, for whom?** Created on 2026-10-07 by the project's policy author for the Tribunal development team. Not
a product of WorkBuddy, not supplied by the organisers.

## Composition

- 80 cases: 40 NO_SHOW_CHARGE (1701-1740), 40 ROUTE_DEVIATION (1751-1790). Each case: one dispute object and 7 evidence
  artifacts of the corpus's 7 types; every TRAFFIC_ADVISORY that the scenario does not need is a MISSING artifact with
  weight 0.0, as in the corpus.
- Tracks: REGULAR 32, BOUNDARY 24, ADVERSARIAL 16, CLAUSE 8. Expected rulings: FULL_REFUND 24, PARTIAL_REFUND 20,
  DRIVER_COMPENSATION 14, NO_ACTION 12, ESCALATE 10. The share of ESCALATE (12.5 percent) was chosen so that the
  escalation precision and recall figures in `eval.readiness` have something to measure.
- Platform parameters: every no-show record carries `trip_record.platform_policy`. 36 carry the published figures
  (PLATFORM-PUBLISHED-2026-10-07: 180 s, SGD 4.50 net / 6.61 gross), 1 carries a record block (RECORD-PLATFORM: 300 s /
  480 s / SGD 5.00, the shape of the organisers' sample), 3 carry the version-1 authored parameters (AUTHORED-V1: 300 s
  or 480 s, greater-of fee). The figure in force is therefore always on the record; the set does not rely on the
  fallback for a missing block. All 80 disputes are rider-filed; the driver-filed
  path is not covered here (see Limitations).
- Labels: four graded fields plus governing clauses, difficulty and a rationale that cites evidence ids and clause ids,
  in the shape of the other keys in `eval/answers/`.
- Relationships: 12 directional minimal pairs and 5 invariance pairs (`pairs.json`, beside this file).
- Splits: calibration 50 / holdout 30, stratified by (category, track), pairs kept together (`split.json`).
- Sensitive content: none. Party identifiers are synthetic (`RDR-07xxx`, `DRV-07xxx`); there are no names, telephone
  numbers or vehicle registrations. One case (1735) contains a synthetic threatening chat message, written to trigger the
  safety route, and nothing more graphic than that.

## Collection and generation process

- Every case is rendered by `eval/synth/make_dev_set.py` from a scenario specification. Expected outcomes were fixed first
  from the policy text; the evidence was then generated to carry those facts: GPS traces by geometry (Singapore
  coordinates, 10 s sampling, accuracy drawn from the ranges the scenario needs), fares by the policy's own rate card and
  rounding rule, chat by templates, profiles by plausible ranges with the clause-cited counters set deliberately.
- Seed 20261007. Re-running the script reproduces every byte, including `index.json` digests.
- The key was checked by a second derivation (`eval/synth/verify_dev_set.py`) that reads the deciding figures from the
  repository's own brief and applies the clause rules; 80 of 80 agree. Where the generator's arithmetic and the
  repository's `money.py` could have diverged (POL-RD-02, POL-RD-03 closure adjustment, POL-RD-11), the repository's
  figure was taken as the reference and the key was found equal to it.
- No real complaint, no real trip and no real person was used. The scenarios draw on the published cancellation and
  waiting policies of Ryde and its Singapore peers for parameter values and on the policy text for everything else.

## Preprocessing, cleaning, labelling

- `admissibility.notes` are descriptive (coverage, track presence, message count) and never name a clause or a distance,
  unlike the corpus; this is deliberate because the notes reach the model.
- Issue codes and `weight_multiplier` follow the version-1 pre-pass rule (product of code weights, two places, floor
  0.25). Three cases carry a GPS gap; none of their keys depends on the weight.

## Uses

- Intended: calibration of the escalation threshold; regression gating with `eval.gate`; coverage of the version-2
  clauses; error attribution; demonstration of minimal-pair behaviour.
- Not intended: any accuracy claim about generalisation. An 80-case set gives roughly a +/- 9 percentage-point 95 percent
  interval at 80 percent accuracy (n = z^2 p(1-p) / e^2); it is sized for development, not for a headline figure.
- Not intended: training or fine-tuning of any model. `CANARY.txt` exists so that leakage into a model or a prompt can be
  detected.

## Distribution and maintenance

- Cases live under `data/external/dev-v2/`; the key and every outcome-describing file (this one included) under `eval/answers/dev-v2-ext/`, under the same isolation tests as the
  other keys. The key is frozen: a run that disagrees with it does not change it; a key found wrong is corrected by a
  dated note and a new seed-reproducible regeneration, never by editing one figure.
- A case whose key is challenged goes through the same process as a sealed-set miss: the rationale is checked against the
  clause text, the derivation script is run, and the finding is written down before anything moves.

## Limitations (stated so that nobody over-reads the set)

1. Synthetic data is easier than human-authored data on average; the BOUNDARY and ADVERSARIAL tracks exist to counter
   this, but a model that scores well here has not been shown to handle real complaints.
2. Chat text is templated and short. Natural complaint language, mixed languages and long threads are not represented.
3. Every dispute is rider-filed; the driver-filed path and the party-relative reading of NO_ACTION are not exercised.
4. The three GPS_GAP cases carry version-1 weights; the version-2 pre-pass will derive different ones for one of them.
5. The geometry is schematic: corridors are smooth curves with a lateral bulge, not road networks; place labels are
   flavour and do not geocode to the coordinates.
6. Three cases (1717, 1718, 1725) are decided by the 180 s free wait their record states; until plan item 41 makes the
   code read `platform_policy`, the version-1 brief applies 300 s by zone and the system is expected to miss two of them.

7. Platform convenience fields are present as they are in the corpus: `trip_record.deviation_pct`, `wait_time_min` and
   `erp_gantries[].on_optimal_route` restate facts the clauses derive from the trace. They are platform data, not
   answers, and POL-RD-01 / POL-NS-01 name the governing fields; but a model that reads them instead of the trace will
   score higher here than its reasoning deserves. `dispute.amount_contested_sgd` is the rider's own rough figure and is
   never the clause arithmetic.
8. One key rests on a reading the policy text leaves open: 1734 (POL-NS-04 limb (c) undecidable because rider_track is
   absent). The key reads NS-04 as "neither satisfied nor failed, decide under POL-NS-01"; a literal reading of the
   NS-08(b) sentence NS-04 invokes could instead escalate. The reading is stated in the rationale; the clause should be
   tightened in the next policy revision.
9. Two clauses collide on one fact pattern and should be amended: POL-NS-09(b)'s worked example (a trip record showing a
   dwell while the trace puts the driver 800 m away) is also the trigger of POL-NS-05 (a false arrival marker, which
   limb (ii) resolves by a full refund). No case in this set rests on that pattern any more; the next policy revision
   should say which clause yields. Likewise POL-NS-04 should state that an undecidable limb (c) sends the case to
   POL-NS-01 without engaging POL-NS-08's escalation sentence (item 8).
10. First-run findings (2026-10-08, dev-v2 run by the developer) and what changed: (a) the "never arrived" cases
    (1709, 1710 and variants) stamp the arrival marker more than 300 m from the pin, which engages POL-NS-05 and its
    limb (ii) referral; the key had the right ruling and amount but omitted the referral - added. (b) The 80 s-gap
    route case (1775 and variants) carried the version-1 GPS_GAP weight 0.6, which on its own forces escalation under
    POL-GEN-02 (0.6 is at or below 0.65); the version-2 integrity grading for a gap that POL-RD-07 does not treat as
    impaired is 0.85, now written on the artifact. Route-deviation gaps are to be graded by the 90 s limb of POL-RD-07
    exactly as no-show gaps are graded by the 120 s limb of POL-NS-08. (c) 1734 (and 2734) remain a policy probe and are
    excluded from the score until POL-NS-04 is amended (item 8).
11. Second-round review (26 more keys re-adjudicated independently): POL-NS-05 limb (i) as written directs no record of
    the false marker, so the short-dwell false-marker cases (1726 and variants) expect no referral; an amendment adding
    the record to limb (i) is proposed, because the clause's purpose is that the pattern stays visible. Every refund
    above execution_threshold_sgd 8.00 now cites POL-GEN-05; every MATERIAL deviation (including the 8.0 km absolute
    limb) cites POL-RD-06; a FULL_REFUND route case contests charged_total, so GEN-03's "whole contested amount" and
    RD-02's charged_total coincide; the short-gap route pair runs at 36 km/h so that its 40 s gap stays under the 500 m
    jump of POL-RD-07(b).
12. Second-run findings (2026-10-08 evening) and what changed: (a) the DRIVER_UNABLE_TO_LOCATE referral now cites
    POL-NS-01 without a limb - the sentence that directs the record follows limb (d) in the clause body rather than
    sitting inside it; (b) the safety-flag case expects no referral: an escalation replaces the ruling (POL-GEN-03) and
    the trigger is stated in the explanation; (c) the upfront-quote cases (1763, 1764 and variants) now refund the
    0.80 platform fee as well - POL-RD-11(a) lists the lines properly chargeable above the quote exhaustively and the
    platform fee is not among them, so the key was wrong and the judge was right; (d) amendment 0002 (POL-RD-14) was approved on 2026-10-09, so 1782 and its variants are keyed PARTIAL_REFUND at the
    POL-RD-02 figure: an instruction the trace never followed excludes nothing. Two pipeline defects the run exposed are code items, not key items: the vote
    reduces referrals by raw text rather than by clause reference (1725), and the no-show money block does not
    enumerate the waiting-time fee as a refund option (1740).
