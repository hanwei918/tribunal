# The second development set: what it is, and what it is not

**2026-09-25.** Fifteen cases, `9101`–`9115`, under `data/external/codex/`, with
their own answer key at `eval/answers/codex/ground_truth.json`. They are **the
second development set**. This note records where they came from, what was done
to the key, and — the part that matters — the limits the set has **as measured**,
because those limits are what the set may and may not be used to claim.

The rule that the set changed is recorded separately in
`docs/notes/2026-09-25-the-standing-rule-change.md`. That note is about the judge
prompt; this one is about the data.

## What it is not

It is **not a test set**. A test set has to be drafted without access to this
repository and seen beforehand by nobody who works on the prompt. This set fails
both tests: it was drafted against the same policy text and the same case
conventions, and it was read by whoever works on the prompt the day it arrived.
It is **development data**, exactly like the corpus, and it is used the same way
— to find failures to fix while the prompt may still change, until 6 October.

It is **not the generalisation figure**. That belongs to the sealed set, drafted
blind and run exactly once after the 10 October freeze. Nothing in this note, and
no number computed over this set, is that figure.

## Provenance

- **Drafted by a separate model.** The fifteen cases were written by OpenAI
  **Codex on 2026-09-24** and copied in by the owner into `data/external/codex/`
  as `case-09101.json` … `case-09115.json` plus `index.json`. They were committed
  **exactly as received** first (`98b7a3c`), so that every later change to them
  shows as its own diff. The index's `file` field recorded a `cases/` prefix that
  the flat copy does not have, and was corrected in its own commit (`2b20acd`);
  each entry's own `sha256` is the flat file's, so that was a correction and not
  a guess.
- **The key was checked by independent re-derivation**, and then by two
  independent adjudicators on the cases where the re-derivation and the key
  disagreed. Twelve of the fifteen agreed. **Three answers were corrected**
  (`ecf2df7`), each from the raw fixes with exact decimal arithmetic and no
  intermediate rounding, and each correction's evidence is in the commit message
  and in the key's own `rationale` field:

  | case | as received | corrected | evidence |
  |---|---|---|---|
  | `9111` | PARTIAL_REFUND 9.15, no referral | PARTIAL_REFUND **10.15**, one POL-RD-09(4) referral naming **both** lines | Pioneer Road inbound is **912.0 m** and Tuas South Avenue 8 loop **1645.7 m** from the nearest fix, against POL-RD-09(4)'s 250 m test. Both are billing-integrity failures. The SGD 1.00 line had been credited into the recomputed fare as on-optimal; removing it raises the refund by SGD 1.00. The SGD 2.00 line is **not** added on top — it was already excluded as off-optimal, and POL-RD-09(1) forbids counting it twice. |
  | `9113` | PARTIAL_REFUND 8.05, no referral | PARTIAL_REFUND **9.05**, one POL-RD-09(4) referral | The Pelton lawful diversion entry line is **834.2 m** from the nearest fix although flagged `on_optimal_route`; POL-RD-09(4) matches by coordinates and makes no exception for that flag. Corpus case **115** applies the same test to the same kind of line. |
  | `9114` | **PARTIAL_REFUND** 3.20 | **FULL_REFUND** 3.20 | The contested amount is 3.20 and all of it is returned, which POL-GEN-03 defines as FULL_REFUND. The amount, the null driver compensation and the referral are unchanged. |

  **The case files were not touched.** The answer follows the data.

## The limits, as measured

Everything below is computed from the files, not asserted. The measurement
script compares the fifteen against all 29 corpus cases.

**None of the fifteen is a literal copy.** Canonical-JSON equality over all
15 × 29 pairs: **zero** matches. They are new documents.

**The set is not new material.** The policy has 24 clauses and the corpus's
governing clauses are **all 24** of them. The fifteen's governing clauses are
**19 of those 24**, and **none is new** — every clause any of the fifteen leans on
is one the corpus already leans on. Its exact governing-clause *set* matches a
corpus case's in **1 of 15** — `9101`, whose `POL-NS-01/POL-NS-02/POL-NS-07` is
corpus `202`'s — which is the measure that understates the overlap. The measure
that does not is the device: **every one of the fifteen pairs with a corpus case
built around the same deciding device**, with new places and numbers:

| set | corpus | the device both are built around |
|---|---|---|
| `9101` | `202` | POL-NS-07 pays 80% of the fee and the anti-farming check does not trip |
| `9102` | `212`, `205`, `214` | POL-NS-04 limb (b): a reply inside 120 s takes the case out of the clause |
| `9103` | `203`, `211` | POL-NS-06 strict-liability shortfall on the effective dwell |
| `9104` | `201` | POL-NS-05(ii) false-arrival event, refund **plus** a referral |
| `9105` | `205`, `206` | POL-NS-03's 400 m wrong-entrance ceiling; the rider named the right place |
| `9106` | `204` | POL-NS-04's three limbs displacing a POL-NS-01 win |
| `9107` | `214`, mirrored by `211` | POL-NS-06(i) summing of in-radius holds under a **populated** advisory |
| `9108` | `207` | POL-NS-07 anti-farming on both conjunctive limbs → terminal escalation, plus the escalation-packet referral |
| `9109` | `213` | POL-NS-09(e): the sole evidence for the deciding fact is unavailable |
| `9110` | `213` | POL-NS-09(c): `disputes_with_counterparty_90d` of 2 on both profiles |
| `9111` | `115`, `114`, `106` | POL-RD-09(4) phantom gantry **and** POL-RD-09(1)'s no-double-counting rule |
| `9112` | `102`, `113` | POL-RD-01's limbs are conjunctive: the absolute clears, the proportional fails |
| `9113` | `103`, `104`, `111` | the POL-RD-03 cap binding, beside a genuine and a phantom gantry |
| `9114` | `115` | POL-RD-11: an UPFRONT_QUOTE trip disapplies POL-RD-02 |
| `9115` | `110`, `107` | POL-RD-07(ii): the fare ledger is a copy of the trace, not independent corroboration |

Three of these pairings are close enough to say so plainly. `9104`'s referral and
`9108`'s referral are **verbatim** corpus `201`'s and `207`'s respectively, and
`9108`'s anti-farming figures are the same shape as `207`'s (7 terminations;
11.5% there, 10.0% here). `9110`'s repeat-pairing counter is **the same field at
the same value** as `213`'s.

**Thirteen of the fifteen also carry the corpus's absent-advisory device.** The
`EV-ADVIS-*-01` entry exists in all fifteen, but in thirteen of them its
`admissibility.status` is `MISSING`, its `weight_multiplier` is `0.0` and its
`payload` is `null` — the same shape as 24 of the 29 corpus cases. `9107` and
`9113` are the two with a populated advisory, and they are the two whose answers
depend on it.

The figure the instruction for this note gave was *thirteen of fifteen re-test a
trap the corpus already tests*. Thirteen is what the absent-advisory count comes
to. The device pairing above is the stricter measure and comes to **fifteen of
fifteen**, and it is the one recorded here, because the table is the evidence for
it and because the stricter figure makes the limitation larger, not smaller.

**`9107` is a near-copy of corpus `214`.** Both are a mall bay under a
kerb-closure advisory, one loop, two in-radius stretches summed under
POL-NS-06(i): `214` is ION Orchard with a KERB_RESTRICTION advisory and holds of
170 s and 185 s summing to 355 s against a 300 s minimum; `9107` is Orchard
Central with a CLOSURE advisory and holds of 170 s and 160 s summing to 330 s.
Same category, same ruling, same amount (3.20), same clause mechanism; different
venue, different advisory type, different durations, and a clause set that drops
POL-NS-02. It is not a copy and it is not an independent test of the same idea.

**All fifteen share one template.** Measured:

- **Rider profile** (`EV-RPROF-*`, ignoring `party_id` and `snapshot_at`): **2
  distinct values across the fifteen**, and the common one in **14 of 15**. The
  single variation is `disputes_with_counterparty_90d`, in `9110`, which is the
  field that case's own answer turns on. Across the corpus the same measure gives
  **29 distinct of 29**.
- **Driver profile** (`EV-DPROF-*`, same exclusions): **13 distinct values across
  the fifteen**, differing only in `active_region` — a context-only field — and,
  in `9108`, in `no_show_terminations_30d`/`completed_trips_30d`, which is the
  field its own answer turns on. Every other field is identical in all fifteen:
  `account_age_days` 880, `lifetime_trips` 2140, `rating` 4.89,
  `prior_no_show_flags` 2, `prior_deviation_flags` 0, `acceptance_rate` 0.94,
  `completed_trips_90d` 610, `no_show_terminations_30d` 1,
  `completed_trips_30d` 120. Across the corpus the same measure gives **29
  distinct of 29**.
- **Timing offsets.** `requested_at → accepted_at` is **60 s in all fifteen**;
  the corpus's equivalent takes ten different values between 36 s and 53 s. Arrival
  is `accepted_at + 680 s` in the ten NO_SHOW_CHARGE cases and
  `accepted_at + 360 s` in the five ROUTE_DEVIATION cases; the first fix sits 20 s
  before arrival, or at the trip start. The only offset that varies from case to
  case is the **last** one — the length of the hold or of the trip — which is the
  quantity the case is about. The corpus takes 29 distinct offset tuples out of
  29; the set takes 11 out of 15, and the eleven differ only in that last offset.
- **Planned route.** All ten NO_SHOW_CHARGE cases carry the same booked optimum,
  **7.4 km / 19.0 min**, whatever the pickup is. The corpus's optima take 27
  distinct values across its 29 cases.

## What this limits

The set can show that a change to the judge prompt **does not break** the
corpus's ideas when the places, numbers, distances and amounts are new. That is
real: it is what the new standing rule asks a prompt change to be regression-run
against, and it is why adding the set was worth doing.

It cannot show **generalisation**. Every one of the fifteen re-instantiates a
device the corpus already contains, and one of them (`9107`) re-instantiates a
whole corpus case. All fifteen are generated from one template whose profiles,
planned route and timing offsets barely vary — against a corpus whose every case
differs in each of those. A model that has learned this corpus's trap taxonomy
will score well here for the same reason it scores well on the corpus, and a
figure computed over both sets is a sum of two measurements of the same thing,
not a second, independent one. The combined line in the report says so in as many
words.

The honest reading is the one the new standing rule already takes: this set buys
a **second, differently-drafted sample of the same ideas** to guard a prompt
change against over-fitting, and the sealed set is still the only thing that can
speak to generalisation.

## Running it

The set goes through **the same runner the corpus goes through** —
`eval.run_benchmark.run_benchmark` — so the cache, the provenance, both
deadlines, the token budget and the advocate replay are not reimplemented and
cannot drift from the corpus's. Its four graded fields are compared against
**its own key**, never the corpus's.

```
python3 -m eval.development_sets --set codex
```

That runs all fifteen into `runs/codex/<model>/`, which is its own directory:
nothing of this set is ever written into `runs/<model>/`, where the 29-case
corpus result lives. `--report` prints the two sets separately and combined from
cached runs and makes no model call. `--cases`, `--force`, `--token-budget`,
`--concurrency`, `--timeout`, `--case-deadline`, `--replay-advocates` and
`--replay-check` all behave as they do for the corpus.

**No model call was made when this set was added.** `runs/codex/` does not exist
in the repository, and `python3 -m eval.development_sets --report` prints the
second set as `0/15  not run`.
