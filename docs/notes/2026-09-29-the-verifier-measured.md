# The verifier, measured on both development sets

The draft verifier and its measurement harness were built on 2026-09-28 and
described in `docs/notes/2026-09-28-the-draft-verifier-and-how-it-is-measured.md`.
That note ends by saying the pass "has not yet been run" over either set and
claims no figure for one. This session is that run. **No model call was made
here**: the two commands below were run by the owner outside the sandbox, their
output is committed unchanged, and everything below is read out of the committed
files.

    python3 -m eval.run_benchmark --verify-recorded-drafts runs/deepseek-deepseek-flash
    python3 -m eval.development_sets --set codex --verify-recorded-drafts runs/codex/deepseek-deepseek-flash

They wrote `runs/verify-recorded-drafts/deepseek-deepseek-flash/` and
`runs/codex/verify-recorded-drafts/deepseek-deepseek-flash/` — three files each,
`events.jsonl`, `verify-recorded.json`, `verify-recorded.md` — and both
directories are committed as `43766b6`, byte for byte as produced. The verifier
and its prompt are untouched.

## 1. What each set produced

| set | cases | usable | statements | judged | contradicted | material | not material | tokens |
|---|---|---|---|---|---|---|---|---|
| corpus | 29 | 27 | 2,292 | 2,144 | 19 | 8 | 11 | 1,479,451 |
| codex | 15 | 15 | 1,035 | 1,035 | 38 | 7 | 31 | 752,852 |
| both | 44 | 42 | 3,327 | 3,179 | 57 | 15 | 42 | 2,232,303 |

`statements` is what `extract_factual_statements` took out of the valid drafts;
`judged` is what the verifier returned a verdict for. The two differ only on the
two unusable cases, which is section 5.

The token totals are the verifier's own — the advocate and judge calls were the
source runs' and cost nothing here — and they equal the per-case sums in both
files. The `invocation_end` events agree with the JSON independently: corpus
`verified_cases 29`, `contradicted_statements 19`, `material_statements 8`,
`changed_cases [102, 108, 110]`, `tokens_consumed 1479451`; codex `15`, `38`,
`7`, `[9102, 9104]`, `752852`.

**The reconstruction is faithful.** `matches_recorded` is true on all 42 usable
cases in both sets, so the "without the verifier" reading is the source run's own
vote re-derived from its own drafts, and the difference reported below is the
verifier's and not a resampling of the judge.

**Two cases produced no verification at all, and the corpus command exited 1
because of it.** Case 203 and case 211 each made one call — `status 200`,
`attempts 1`, `parse_outcome MALFORMED`, `shape NoneType` — and the body was not
a JSON object: 203's answer is 7,554 characters and fails at character 4,230
(`Expecting ',' delimiter`), 211's is 6,371 characters and fails at character
6,359 (`Unterminated string`). 211's completion is 65,535 tokens, 63,581 of them
reasoning, which is the ceiling. The two together cost 122,316 tokens. The
designed fallback applied: both drafts' votes are kept, `usable` is false, and
the reason recorded is `the verifier did not return a JSON object`. `refused` is
**empty** in both files — nothing was refused by the provenance check — so the
exit status is `report.ok` being false, and `main()` returns `0 if report.ok
else 1`. An exit 1 here means two cases were unusable, not that the command
failed.

**The first invocation in each log has no end.** Each `events.jsonl` opens with
an `invocation_start` at 19:05 — corpus `20260929T110523.650092+0000`, codex
`20260929T110542.245212+0000` — and the second start at 19:06:31 is the one with
a matching `invocation_end`. The 19:05 attempts were killed by the shell before
any call completed. They are kept as they are.

## 2. Three readings, and what each rule would have moved

One verifier call produces three readings of the same drafts, so a difference
between them is the rule and nothing else. `without` is the vote with no
verification; `any_contradiction` lets every contradiction stop its draft, which
is what the pass did before materiality existed; `material_only` lets only a
contradiction that could change a conclusion stop a draft, which is what the
pipeline does.

**The material rule moved the vote on 5 of the 42 usable cases, and changed no
ruling.** Corpus 102, 108 and 110; codex 9102 and 9104. Every one of the five
moved the *agreement* and left the *ruling* where it was: 1.0 to 0.75 on four of
them, and 1.0 to 0.25 on 110, where all three drafts wrote the same wrong figure
and all three abstained.

**The any rule would have moved 18 and changed 7 rulings.** It moved the vote on
corpus 101, 102, 106, 108, 109, 110, 112, 115, 208, 214 and codex 9102, 9104,
9106, 9107, 9108, 9109, 9111, 9114 — 18 cases — and it changed the ruling on 7
of them: 101, 115 and 214 from their monetary rulings to `ESCALATE`, 9111 from
`PARTIAL_REFUND` to `ESCALATE`, and 9107, 9108 and 9114 to no ruling at all,
because enough drafts stopped that fewer than three remained valid and the case
became `no_valid_drafts`. **Materiality is what keeps those seven rulings.**

The 13 cases materiality saved — where the strict rule would have moved the vote
and the pipeline's does not — are corpus 101, 106, 109, 112, 115, 208, 214 and
codex 9106, 9107, 9108, 9109, 9111, 9114. They are the cases the field exists
for: a correct draft that the stricter rule would have stopped.

A `not_in_evidence` verdict never stops a draft, and there are 48 such statements
in the corpus and 28 in the codex set.

### Corpus — 29 cases

| case | statements | contradicted | material | without | any | material |
|---|---|---|---|---|---|---|
| 101 | 67 | 2 | 0 | carried 1.0 | escalated 0.5 | carried 1.0 |
| 102 | 77 | 1 | 1 | carried 1.0 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 |
| 103 | 71 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 104 | 95 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 105 | 92 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 106 | 92 | 1 | 0 | carried 1.0 | carried_not_unanimous 0.75 | carried 1.0 |
| 107 | 95 | 3 | 3 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 |
| 108 | 78 | 1 | 1 | carried 1.0 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 |
| 109 | 75 | 1 | 0 | carried 1.0 | carried_not_unanimous 0.75 | carried 1.0 |
| 110 | 89 | 3 | 3 | carried 1.0 | escalated 0.25 | escalated 0.25 |
| 111 | 65 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 112 | 90 | 1 | 0 | carried 1.0 | carried_not_unanimous 0.75 | carried 1.0 |
| 113 | 90 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 114 | 89 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 115 | 63 | 2 | 0 | carried 1.0 | escalated 0.5 | carried 1.0 |
| 201 | 72 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 202 | 90 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 203 | 63 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 204 | 70 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 205 | 91 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 206 | 83 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 207 | 58 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 208 | 74 | 1 | 0 | carried 1.0 | carried_not_unanimous 0.75 | carried 1.0 |
| 209 | 64 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 210 | 79 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 211 | 85 | 0 | 0 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 |
| 212 | 81 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 213 | 73 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 214 | 81 | 3 | 0 | carried 1.0 | escalated 0.5 | carried 1.0 |

203 and 211 are the two unusable cases: their `judged` list is empty and their
`contradicted` count is therefore zero, so the three readings are the same vote
by construction and the row says nothing about the verifier.

### The second set — 15 cases

| case | statements | contradicted | material | without | any | material |
|---|---|---|---|---|---|---|
| 9101 | 69 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 9102 | 70 | 1 | 1 | carried 1.0 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 |
| 9103 | 65 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 9104 | 74 | 2 | 1 | carried 1.0 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 |
| 9105 | 77 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 9106 | 61 | 1 | 0 | carried 1.0 | carried_not_unanimous 0.75 | carried 1.0 |
| 9107 | 74 | 10 | 0 | carried 1.0 | no_valid_drafts none | carried 1.0 |
| 9108 | 63 | 10 | 0 | carried 1.0 | no_valid_drafts none | carried 1.0 |
| 9109 | 68 | 2 | 0 | carried 1.0 | escalated 0.5 | carried 1.0 |
| 9110 | 44 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 9111 | 71 | 2 | 0 | carried 1.0 | escalated 0.5 | carried 1.0 |
| 9112 | 76 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |
| 9113 | 89 | 5 | 5 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 | carried_not_unanimous 0.75 |
| 9114 | 65 | 5 | 0 | carried 1.0 | no_valid_drafts none | carried 1.0 |
| 9115 | 69 | 0 | 0 | carried 1.0 | carried 1.0 | carried 1.0 |

## 3. Every material contradiction, checked against the brief

Fifteen statements were judged contradicted *and* material. They fall on seven
cases: 102, 107 (three), 108, 110 (three), 9102, 9104 and 9113 (five). All seven
briefs were rebuilt here from the committed case files and every one reproduces
its recorded `brief_sha256` exactly, so the comparison below is against the bytes
the agents were handed. The headings say whether the draft's statement is a real
error on those bytes.

### 102 — a real error

Draft 2, statement 32:

> On the money: the fare reconciles to the cent — $3.80 base + $15.30 distance +
> $7.56 time + $0.80 platform fee = $29.91, with surge 1.0 read from
> fare_breakdown.surge_multiplier.

The verifier's value: *distance_fare 16.35 + time_fare 8.96 + base_fare 3.80 +
platform_fee 0.80 = 29.91; the 15.30 and 7.56 figures are the derived
optimal-route components (recomputed_fare 27.46), not the charged reconciliation.*

The brief's `EV-FARE-00102` carries both sets of figures. Its charged
reconciliation is `distance_fare 16.35`, `time_fare 8.96`, `base_fare 3.80`,
`platform_fee 0.80`, `total_charged 29.91`. Its `derived.money.components` carry
`distance_charge 15.30`, `time_charge 7.56` and `recomputed_fare 27.46`, which is
what the *optimal* route would have cost. The draft's own addends —
3.80 + 15.30 + 7.56 + 0.80 — come to **27.46**, not 29.91. The total it quotes is
the charged total and the components it quotes are the recomputed ones: the
sentence says "reconciles to the cent" about arithmetic that does not reconcile.
Real error, and it is the kind a reader can check from the brief alone.

### 107 — see section 4

Draft 2, statements 36, 40 and 41, all three charged against `POL-GEN-02(2)` and
the first two against no figure the brief prints. They are the section that
follows.

### 108 — a real error, and the verifier's figure is its own arithmetic

Draft 1, statement 9:

> (3) The rider's account of roughly five minutes circling at T3 is the kind of
> distance POL-RD-05 also excludes from excess, and it points the same way, but
> it is not needed because the excess is already below both gates.

The verifier's value: *the 1.57 km excess is above the 0.8 km absolute gate —
only the 20% percentage gate fails.*

The brief's `EV-GPS-00108` `derived.deviation` carries `trace_distance_km 26.17`,
`optimal_distance_km 21.0`, `excess_km 5.17`, `excess_pct 24.62`, and the two
POL-RD-01 thresholds `threshold_km 0.8` and `threshold_pct 20.0`, with
`status established`. `EV-TRIP-00108` also carries `amended_optimal_distance_km
24.6`.

The draft's claim is false on the brief's own numbers: the excess the brief
publishes is 5.17 km against a 0.8 km gate and 24.6% against a 20% gate, so it is
above *both* gates, not below them. Real error.

One qualification about the verifier's figure. **1.57 km is nowhere in the
brief** — it is `26.17 - 24.60`, which is the excess re-measured against the
amended optimal distance, i.e. POL-RD-05 applied to two figures the brief does
print. The verifier did that arithmetic itself and reported its result as what
the brief holds. Here the arithmetic is right and the conclusion is the same
either way (1.57 km is still above the 0.8 km gate), so the finding stands; but
the quoted value is a derivation and not a field, and a reader looking for 1.57
in the brief will not find it.

### 110 — a real error in all three drafts

Draft 1 statement 1, draft 2 statement 26 and draft 3 statement 45 all say the
disputed amount is `$34.42`:

> No refund is issued and no charge is confirmed while that review is pending;
> the disputed $34.42 is held rather than collected or refunded.
>
> The disputed $34.42 is held, not collected and not refunded, and a human
> reviewer will look at the case.
>
> Both parties: this case turns on one stretch of road the evidence cannot see,
> so it goes to a human reviewer and the disputed $34.42 is held rather than
> collected or refunded.

The verifier's value, on all three: *SGD 10.00 (the disputed/contested amount;
the SGD 34.42 is the total charged, EV-FARE-00110 total_charged).*

The brief's `case.dispute.amount_contested_sgd` is **10.00** and
`EV-FARE-00110.total_charged` is **34.42**. Every draft substituted the total
charged for the contested amount in the one sentence that says what is being
held. Real error, and the reason all three drafts stopped: the agreement fell
from 1.0 to 0.25 and the case escalated, which is the one place the material rule
and the strict rule agree.

### 9102 — a real error

Draft 2, statement 21:

> The SGD 6.00 cancellation fee stands, and the driver is owed SGD 4.80 in
> compensation, which the platform pays.

The verifier's value: *the driver's compensation is 80% of the cancellation fee
charged to the rider, the residual 20% being retained as the platform service fee
(fee-funded); a platform-funded payment is the POL-NS-03(ii) goodwill, which is
charged to the platform.*

`POL-NS-07`'s rule says the driver "is compensated at 80 percent of the
cancellation fee itemised in fare_breakdown - SGD 3.20 of SGD 4.00, SGD 4.80 of
SGD 6.00, SGD 6.40 of SGD 8.00 - the residual 20 percent being retained as the
platform service fee." The brief's `EV-FARE-09102` carries `fee_charged 6.00`,
`driver_compensation 4.80` (clause `POL-NS-07`) and, separately, `goodwill 3.00`
(clause `POL-NS-03`). The draft's amount is right and its funding is wrong: the
4.80 is funded out of the fee the rider paid, and "which the platform pays" is
the goodwill branch, which is a different figure under a different clause. Real
error.

### 9104 — a real error

Draft 4, statement 72:

> The driver's claims that SGD 4.00 is the correct amount (STANDARD zone-class
> fee SGD 4.00, RYDE_X vehicle-tier fee SGD 4.00, GREATER taken, no POL-NS-08(d)
> fare defect), that limbs (a) and (d) hold, that POL-NS-04 cannot run (no rider
> message in EV-CHAT-09104 and rider_qualifying_fix_count 0 at 519.46 m), and
> the driver's express concession that the fee is not chargeable on the GPS
> record are accepted; the first four do not change the outcome and the
> concession corroborates it.

The verifier's value: *I marked arrival and waited before cancelling.*

That is the whole of `case.dispute.counterparty_statement.text` for 9104. The
statement asserts arrival and waiting; it contains **no concession** that the fee
is not chargeable, and the two places "not chargeable" appears in the brief are
both policy prose (`POL-NS-01`, `POL-NS-06`), not the driver's words. The rest of
the draft's sentence does check out — `rider_qualifying_fix_count 0` and
`519.46` m are both in `EV-GPS-09104` — which is what makes the invented
attribution the more dangerous: a true clause wrapped around a fabricated one.
Real error.

### 9113 — a real error, and the verifier's total is its own composition

Draft 2, statements 40, 46, 47, 50 and 52. The load-bearing ones:

> That is above the 0.50 de-minimis floor and is 25.5% of charged_total, far
> below the 90% full-refund threshold, so the outcome is a PARTIAL_REFUND of 8.05
> to the rider.
>
> Both gantries were actually crossed (nearest fixes 834 m and 223 m), so no
> billing-integrity defect and no POL-RD-09(4) referral.
>
> Ruling: PARTIAL_REFUND of 8.05 to the rider; no driver compensation; no
> referrals.

The verifier's values: *total refund 9.05 (POL-RD-02 refund 8.05 + POL-RD-09(4)
correction 1.00), not 8.05*; *the Pelton line is 834.18 m from the nearest fix,
outside the 250 m match radius, so it is not crossed and is a POL-RD-09(4)
billing-integrity failure*; *PARTIAL_REFUND of 9.05 and a POL-RD-09(4)
billing-integrity referral.*

The brief's `EV-FARE-09113` carries `refund.payable 12.75` and
`refund.refund_before_rounding 12.72`, against `charged_total 31.42`, and
`case.dispute.amount_contested_sgd` is **8.05**. So the draft's 8.05 is the
contested amount, not the refund the brief computes, and the draft's ruling
quotes the wrong money. Real error.

The ERP half is real too. `derived.money.erp_lines.lines` carries the Pelton
line at `nearest_fix 834.18` m and the Industrial loop exit at `223.17` m, and
POL-RD-09(4)'s match radius is 250 m. The draft's "both gantries were actually
crossed" is true of the second line and false of the first, and it is the first
that POL-RD-09(4) makes a billing-integrity failure — a standalone correction
refunded in full and recorded in the referrals list. Real error.

The verifier's own 9.05 is **not a brief figure**: "9.05" appears nowhere in the
brief, and the brief's computed refund is 12.75. The verifier composed
8.05 + 1.00 and reported the sum as what the brief holds. That does not make the
draft right — the draft's 8.05 is wrong either way — but as with 108 the quoted
value is the verifier's arithmetic rather than a field, and this one lands
nowhere near the brief's own payable.

## 4. Case 107: the verifier judging the ruling

This is the case to read before trusting a material verdict, and it is worth its
own section because the finding is not a fact about the draft.

The case is a rider-filed route-deviation dispute. The brief's admissibility
weights are the whole of it: `EV-GPS-00107` — the trace the excess distance is
measured from — is `IMPAIRED` at weight **0.30** (its own note says the trace is
"down-weighted for admissibility to 0.30 but is NOT impaired for policy"), and
`EV-CHAT-00107` is `COMPLETE` at weight **1.00**. `POL-GEN-02(2)` states the
rule:

> confidence must not exceed the minimum weight_multiplier among the artifacts
> that carry the deciding fact, and where two or more independent artifacts carry
> it, that cap is the maximum of their weight_multipliers rather than the
> minimum.

Draft 2 read that clause one way and wrote (statement 36):

> POL-GEN-02(2) caps my confidence at the weight of the artifacts that actually
> carry the deciding fact, and here that fact — the excess distance — is measured
> from the trace alone, at 0.30.

and drew the consequence (statement 40):

> The cap is therefore 0.30, below the platform-wide floor of 0.70.

and (statement 41):

> POL-RD-10(1) makes the outcome ESCALATE.

The verifier contradicted all three, and its `brief_value` for the first is:

> the deciding route fact is also carried independently by EV-CHAT-00107 at
> weight 1.00, so the cap is the maximum of the independent carriers (1.00), not
> the trace's 0.30

**No field in the brief says that.** The brief states the rule and it states the
two weights; it does not state which artifacts carry the deciding fact, and it
certainly does not say the chat does. The chat's own content is two messages —
the rider asking "why exit at whitley? CTE goes straight down what" and the
driver answering "cte very jam tonight boss" — neither of which states a distance
or a route measurement. Whether that chat is an **independent artifact carrying
the deciding fact**, so that the cap becomes the *maximum* of the carriers rather
than the trace's 0.30, is the second limb of `POL-GEN-02(2)`, and applying it is
a judgement about how the case should be ruled. The verifier was handed a rule
and asked to compare a statement with the brief; it answered by reading the rule
against the evidence and deciding the cap itself.

That is the verifier doing the judge's work. The prompt it is given says the
opposite — `prompts/v1/verifier.system.md` states that a statement may be false
while the ruling that contains it is correct and that the finding is about the
statement alone — but nothing in the pipeline enforces it, because the pipeline
cannot tell a quoted fact from an applied rule. The consequence here is
invisible in the numbers, and that is the point: 107's vote is
`carried_not_unanimous 0.75` in all three readings, because the panel already had
a dissent, so `changed` is false and the case never appears in the list of cases
the verifier moved. **A material contradiction can be wrong and cost nothing, and
the report will not say so.** The third contradiction, statement 41, is the same
reading one step on: `POL-RD-10(1)` fires only if the confidence cap falls below
the 0.70 floor, so the verifier's view of the cap is what makes the escalation
false, and the brief's own `refund.payable 7.45` — which is what the verifier
quotes as the outcome — is a figure the brief does print.

Two things follow, and neither is a change to the verifier in this session:

- A `brief_value` is evidence about the *verifier*, not about the brief. Three of
  the fifteen material contradictions (108's 1.57 km, 9113's 9.05, and both of
  107's carrier claims) quote a value the brief does not contain; two are the
  verifier's own arithmetic on printed figures and one is its own reading of a
  clause. Reading a material contradiction as "the brief says X and the draft
  said Y" is wrong for those, and the honest reading is "the verifier believes
  the brief entails X".
- 107's three material contradictions were charged to one draft and stopped it,
  and the ruling did not move. The material rule's whole claim is that it stops
  only what could change a conclusion; here it stopped a draft over a conclusion
  the verifier reached itself.

## 5. Two things the committed files say that the code does not

**The unusable answer's note is stale.** Both malformed answers carry
`note: "response was not the shape the prompt asked for; retried once"`, and
`attempts` is `1` on both. `UNUSABLE_RESPONSE_NOTE` in `tribunal/pipeline.py` is
that sentence, and `_verifier_call`'s own docstring says "Exactly one call and no
retry… a malformed answer is treated as no verification rather than chased with a
second call." The note is a generic constant whose wording is true of the other
agents and not of this one. The recorded text is not changed here — the verifier
and its prompt are out of scope for this session — but the discrepancy is in the
committed files and should be fixed in the constant rather than in the record.

**`statements` counts what was extracted, not what was judged.** On 203 and 211
the field reads 63 and 85 while `judged` is empty, because the statements were
extracted before the call and the call returned nothing usable. So the corpus's
2,292 statements include 148 that no verdict ever covered, and the number of
statements actually judged in both sets is 3,179. The report renders the
distinction correctly (it prints "verification not usable" and no contradiction
list) but a reader adding up the `statements` column will get a figure the
verifier never answered for.

## 6. What was run

The related modules on 3.13.12, with the real output:

    python3 -m unittest tests.test_verify_drafts tests.test_pipeline \
        tests.test_run_benchmark tests.test_development_sets

    Ran 553 tests in 1900.322s
    OK (skipped=2)

Both skips are `tests.test_run_benchmark.NoteCouplingTests` —
`test_the_note_agrees_with_the_grader_over_the_real_cache` and
`test_the_block_the_note_quotes_is_the_output_of_its_own_command` — and each
names its own reason: the cache under `runs/deepseek-deepseek-flash` has moved on
from the fingerprint the 2026-09-22 note records, so the note's counts are a
dated statement about a cache they no longer describe. Neither is caused by this
work: nothing here writes inside a model's run directory, and the two committed
directories are new siblings under `runs/` and `runs/codex/`. Run alone, the
class reports `Ran 7 tests` / `OK (skipped=2)`, so the two are the whole of the
count. The log is `runs/unit-test-verifier-measured-py3.13.12.log`, which is not
tracked.

No model call was made in this session. The two commands at the top of this note
were run by the owner outside the sandbox and their output is committed exactly
as produced; this session read it, committed it, and wrote this note. The
verifier and `prompts/v1/verifier.system.md` are unchanged.
