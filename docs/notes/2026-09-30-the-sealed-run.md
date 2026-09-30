# The sealed set's single run

**2026-09-30.** The sealed set was run once, by the owner, outside this sandbox,
from the commit tagged `freeze-2026-09-30`. The output is committed exactly as
produced at `2e527d6`, 131 files under `runs/wild/deepseek-deepseek-flash/`, and
**no model call was made in this repository** to produce or to read it. This note
reads every figure out of the committed files and the set's own key.

Nothing in this note changes a ruling, a prompt, a policy, a case file or the
key. It records what the run did, what it missed, and why.

## What was run

The owner's command, from `d275ef8` with a clean tree and
`git diff --quiet freeze-2026-09-30 -- tribunal prompts policy` holding:

    python3 -m eval.development_sets --set wild --concurrency 2 --timeout 900

| | |
|---|---|
| commit | `d275ef82f518c1d560086d955d2f136d84a0a35a` |
| working tree | clean — the first invocation records `working_tree_clean: true`; the second records `null`, which is "git could not be asked" and not "dirty" |
| model | `deepseek/deepseek-flash` |
| configuration | judge votes 4, verifier off, precedents off, no ablation, policy version 1 |
| `--timeout` / `--concurrency` | 900 s / 2 |
| case deadline | the default, 2400 s |
| prompts digest | `5b8510cd900aa9da58e06fd2a865f94df5ede1bdb3c73006077576411858ea61` |
| answer-key digest | `1bbe020c68325f92f92e43a1ec3093e6e297d3fff9703d7dbb29e20d5722b234` |
| interpreter | 3.11.14 |

Two invocations are recorded in `invocations.json`:

- `20260930T050425.226039+0000-36637` — 05:04:25 to 08:43:54 UTC (13:04–16:46 SGT).
  It asked for all 64 cases and produced a ruling for 62.
- `20260930T084907.602624+0000-82794` — 08:48:57 to 09:06:09 UTC (16:48–17:06 SGT).
  It asked for all 64, reused 62 from the cache, and re-ran the two that had failed.
  It produced no new ruling.

**62 of the 64 cases produced a ruling.** `run.json` records
`cases.failed: [533, 517]`, both `failed_agent: JUDGE`, both `failure_kind: SHAPE`,
and `stop_reason: completed` on both invocations.

## The deviation from the freeze note's protocol

The freeze note's protocol line is: *"A case that fails is retried with the same
command until every case has a result."* That did not happen, and this is
recorded as a deviation rather than presented as compliance.

517 and 533 were retried **once** with the same command and failed the same way,
and were not retried again. The reason is that the failure is not a fault to
recover from. In both cases the draft check `DRAFT_AMOUNT_NOT_READ_OFF` rejected
**all four** judge drafts, because each draft computed an amount the brief's
money block does not publish — and the drafts were right about the money (see
below). Retrying would re-sample the judge until one draft happened to pass a
check that is wrong about this case. That is choosing a result, not recovering
from a fault, so the run stops with two cases unresolved and says so.

## (a) The figures

Every figure below is read from the committed `case-*.json` files and the key
`eval/answers/wild/ground_truth.json`, through `eval.grade`, and cross-checked
against the committed `report.md`.

### Four-field exact, and each field alone

| | |
|---|---|
| Four-field exact, of the 62 cases that produced a ruling | **55/62 = 88.7%** |
| Four-field exact, of the 64 cases in the set (517 and 533 as misses) | **55/64 = 85.9%** |

The second line is the honest one to report: two cases the system could not
decide are not two cases it decided correctly.

| field | of the 62 produced | of the 64 in the set |
|---|---|---|
| `ruling` | **56/62 = 90.3%** | 56/64 = 87.5% |
| `amount_sgd` | **56/62 = 90.3%** | 56/64 = 87.5% |
| `driver_compensation_sgd` | **62/62 = 100.0%** | 62/64 = 96.9% |
| `referrals` | **60/62 = 96.8%** | 60/64 = 93.8% |

A case counts only when all four agree; the per-field figures say which field a
case actually failed on and are not alternative scores. `ruling` and
`amount_sgd` alone would give 56/62 = 90.3% — printed here only as the contrast
the grader requires, because two of the misses are cases whose key moves no money
and whose published ruling refunds it (523, 627), which a two-field grader partly
flatters.

### Per category

| category | in the set | produced a ruling | four-field exact |
|---|---|---|---|
| `ROUTE_DEVIATION` | 37 | 35 | **30/35 = 85.7%** |
| `NO_SHOW_CHARGE` | 27 | 27 | **25/27 = 92.6%** |

The two route-deviation cases that produced no ruling are 517 and 533, which is
why the denominator is 35 there and 27 for the no-show cases. The five
route-deviation misses are 501, 504, 508, 523 and 530; the two no-show misses are
622 and 627.

### Escalation

| | |
|---|---|
| Expected escalations in the set | 4 — 512, 622, 626, 627 |
| Produced escalations | 7 — 501, 504, 508, 512, 530, 622, 626 |
| True positives | 3 — 512, 622, 626 |
| **Precision on `ESCALATE`** | **3/7 = 0.429** |
| **Recall on `ESCALATE`** | **3/4 = 0.75** |
| Escalation rate (on these 62) | 7/62 = 11.3% |

| | count | cases |
|---|---|---|
| Over-escalations (run escalates, key does not) | 4 | **501, 504, 508, 530** |
| Under-escalation (key escalates, run does not) | 1 | **627** |

All four expected escalations in this set are `INDETERMINATE` — cases the record
genuinely does not settle — and the run escalated three of the four. The fourth,
627, was ruled confidently instead. Over-escalation and under-escalation are
different failures and are not summed.

### Tokens

Read from `runs/wild/deepseek-deepseek-flash/events.jsonl`, summing every
`agent_call` event — all agent calls, including the failed cases and their
retries, across both invocations.

| | |
|---|---|
| `agent_call` events | 404 |
| **Total tokens, all calls** | **13,536,023** |
| prompt | 7,240,911 |
| completion | 6,295,112 |
| — of which reasoning | 5,763,945 |
| cached | 3,291,129 |

| by invocation | tokens |
|---|---|
| first (full pass over 64 cases) | 13,009,786 |
| — of which the two failed cases | 466,029 |
| retry (517 and 533 only) | 526,237 |
| **total** | **13,536,023** |

| by role | tokens |
|---|---|
| `JUDGE` | 9,517,840 |
| `DRIVER_ADVOCATE` | 2,148,100 |
| `RIDER_ADVOCATE` | 1,870,083 |

The 404 calls are 55 cases at 6 calls (two advocates, four judge drafts), 7
cases at 7 calls (one draft was malformed and retried once: 501, 505, 508, 518,
520, 525, 536), 517 at 13 and 533 at 12 (a first pass of 6 or 7 calls each plus
the retry). The two failed cases cost 992,266 tokens between them, which is the
price of the retry the protocol asks for.

`run.json` records a smaller `total_for_the_case_set` (13,069,994) because the
second invocation counts the first invocation's *results* as reused and the
failed cases' calls separately; the events log is the complete record and is
what is quoted here.

## (b) The two cases that produced no ruling

### What the drafts said, against the key

The vote block records each draft's proposal as `null` with an `abstention`
carrying only the amount; each draft's ruling is in the raw response text kept in
the transcript. Both invocations produced the same picture, and the transcript
holds the retry's four drafts.

**517** — key: `PARTIAL_REFUND` **33.50**.

| draft | ruling | amount_sgd | abstention |
|---|---|---|---|
| 1 (sampled) | `PARTIAL_REFUND` | 31.50 | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 2 (sampled) | `PARTIAL_REFUND` | **33.50** | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 3 (sampled) | `PARTIAL_REFUND` | **33.50** | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 4 (position-swapped) | `PARTIAL_REFUND` | **33.50** | `DRAFT_AMOUNT_NOT_READ_OFF` |

Three of the four drafts gave the key's figure exactly. The first invocation
gave 33.50, 33.50, 33.50, 31.50 — the same three-to-one split.

**533** — key: `PARTIAL_REFUND` **19.30**.

| draft | ruling | amount_sgd | abstention |
|---|---|---|---|
| 1 (sampled) | `PARTIAL_REFUND` | **19.30** | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 2 (sampled) | `PARTIAL_REFUND` | **19.30** | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 3 (sampled) | `PARTIAL_REFUND` | **19.30** | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 4 (position-swapped) | `PARTIAL_REFUND` | **19.30** | `DRAFT_AMOUNT_NOT_READ_OFF` |

All four drafts gave the key's figure exactly. `run.json` quotes the first
draft's abstention in each case: `amount_sgd=31.5` for 517 and `amount_sgd=19.3`
for 533.

So the system was not wrong about either case. It computed the right refund and
then refused to publish it, because its own draft check would not accept a
figure the brief does not print.

### Why the check rejected them

`pipeline.check_judge_draft` accepts an amount only if it is a single figure the
brief's money block publishes, or the sum of two or three of them
(`amount_reads_off`). The block for 517 publishes:

| path | value |
|---|---|
| `charged_total.value` | 67.50 |
| `quoted_fare.value` | 28.00 |
| `charged_over_quote.value` | 39.50 |
| `erp_lines.on_optimal_route_total.value` | 0.00 |
| `erp_lines.off_optimal_route_total.value` | 0.00 |
| `erp_lines.total.value` | 0.00 |

The key's arithmetic is `67.50 - 28.00 - 6.00 = 33.50`, where the 6.00 is the
airport surcharge the fare breakdown bills on a trip that originates at Changi
(`EV-FARE-00517.airport_surcharge: 6.0`, properly chargeable under POL-RD-11(a)).
That 6.00 is on the ledger but is **not** a figure the block publishes, so 33.50
is not a published figure and not a sum of published figures, and the check
rejects it.

The block for 533 publishes:

| path | value |
|---|---|
| `charged_total.value` | 51.30 |
| `quoted_fare.value` | 29.00 |
| `charged_over_quote.value` | 22.30 |
| `erp_lines.lines[0].amount_sgd.value` | 3.00 |
| `erp_lines.on_optimal_route_total.value` | 3.00 |
| `erp_lines.total.value` | 3.00 |

Here the key's arithmetic is `51.30 - 29.00 - 3.00 = 19.30`, and both operands
**are** published — 22.30 and 3.00. But 19.30 is their **difference**, and the
read-off rule allows a published figure or the **sum** of two or three of them,
not a difference. So 19.30 is rejected as well.

The failure is therefore not a tolerance the drafts exceeded; it is the shape of
the check. On an upfront-quoted fare the rider's remedy under POL-RD-11(a) is
`charged_total` less the quote less the properly chargeable pass-throughs — a
difference by construction — and the money block's model of an amount (one
figure, or two or three added together) cannot express it.

### Where the money block did not generalise

The money block and this check were built around the two development sets. Over
those 44 keys (29 corpus + 15 second set), **43 of 44 key amounts read off the
block**: 28 of 29 on the corpus and 15 of 15 on the second set. The single
exception is corpus 109, whose driver compensation is a POL-RD-04 figure the
policy states only in prose — and the check knows that case by name: where the
ruling is `DRIVER_COMPENSATION` and the block publishes no such figure but names
it in `not_structured`, the amount is recorded as unverifiable instead of
rejected. So across all 44 development keys the check never once had to reject
an amount the key itself states.

The shape that is missing from the development sets is narrower than "an
upfront-quoted trip". There are only **two** upfront-quote route-deviation cases
across the 44 development keys — corpus 115 and second-set 9114 — and in both the
key's refund happens to coincide with a single published figure:

- 115's `PARTIAL_REFUND` 2.00 is the phantom gantry's own line amount, and reads
  off `erp_lines.lines[1].amount_sgd.value`;
- 9114's `FULL_REFUND` 3.20 is exactly `charged_over_quote.value`.

Neither is the excess over the quote **less** a properly chargeable pass-through,
which is the shape POL-RD-11(a) gives when a pass-through is chargeable and the
refund is therefore a difference. The check never met that shape before the
sealed run.

The sealed set is where it stops holding. Over its 64 keys, 61 read off. The
three that do not are 517, 533 and 520. 520 is the same prose-only
`DRIVER_COMPENSATION` case as corpus 109 and is skipped the same way — its four
drafts gave `DRIVER_COMPENSATION` 1.90 and all four were accepted. 517 and 533
are `PARTIAL_REFUND` cases, for which there is no skip, so the check rejected
every draft and the cases produced nothing.

That is the whole of it: a guard whose two carve-outs were both exercised by the
development sets, meeting a case shape the development sets did not contain. The
other nine upfront-quote route cases in the sealed set (501, 506, 510, 516, 521,
524, 525, 532 and, at 0.00, 531) read off, because in each of them the refund
again lands on a published figure — the excess over the quote, or a single gantry
line. Only the two where a properly chargeable pass-through has to be subtracted
from that excess fall outside the block's arithmetic.

### The same check rejected three wrong 8.50 drafts in 501

501 is the mirror image, and it is worth setting beside 517 and 533 because the
check was **right** there. The key is `PARTIAL_REFUND` 14.50. Three of the four
drafts proposed 8.50, and one proposed 14.50:

- the 14.50 draft read the block's `charged_over_quote.value` and passed;
- the three 8.50 drafts deducted an **airport surcharge of 6.00 that was never
  billed** — `EV-FARE-00501.airport_surcharge` is `0.0` — on the argument that
  POL-RD-11(a) "counts a properly chargeable surcharge, not merely a charged
  one". Their own words: `Refund = 39.00 - (24.50 + 6.00) = SGD 8.50`.

8.50 is not a published figure and not a sum of two or three of them, so all
three were rejected. With only one usable draft and a quorum of three, the vote
could not carry and 501 escalated. The check worked: it stopped three drafts
from publishing a refund the rider is not owed.

## (c) The seven misses

Seven cases produced a ruling that does not match the key. (517 and 533 are
counted separately, as cases with no ruling.) Each is given with the key against
the published ruling, the vote, and a cause checked against the brief, the
transcript and the policy text. The owner's review proposed a cause for each;
every one is verified below, and where the record differs from the review the
difference is stated.

| case | category | key | produced | vote agreement | confidence |
|---|---|---|---|---|---|
| 501 | ROUTE_DEVIATION | `PARTIAL_REFUND` 14.50 | `ESCALATE` null | 0.25 (1 of 4 usable) | 0.00 |
| 504 | ROUTE_DEVIATION | `PARTIAL_REFUND` 17.60 | `ESCALATE` null | 1.00 | 0.70 |
| 508 | ROUTE_DEVIATION | `PARTIAL_REFUND` 6.00 | `ESCALATE` null | 0.75 | 0.60 |
| 523 | ROUTE_DEVIATION | `NO_ACTION` null | `FULL_REFUND` 4.00 | 0.75 | 0.85 |
| 530 | ROUTE_DEVIATION | `PARTIAL_REFUND` 5.80 | `ESCALATE` null | 1.00 | 0.00 |
| 622 | NO_SHOW_CHARGE | `ESCALATE` null | `ESCALATE` null | 1.00 | 0.90 |
| 627 | NO_SHOW_CHARGE | `ESCALATE` null | `FULL_REFUND` 6.00 | 1.00 | 0.90 |

### 501 — the drafts deducted an unbilled airport surcharge

**Verified.** The cause is in 501's own drafts, not in the check that rejected
them. Three of the four drafts reduced the refund by a 6.00 airport surcharge the
ledger never charged (`airport_surcharge: 0.0` on `EV-FARE-00501`), reading
POL-RD-11(a)'s "a properly chargeable airport surcharge" as licensing a deduction
for a surcharge that was merely chargeable rather than charged. The key takes the
pass-throughs properly chargeable as 0.00 — the two ECP gantries are
`on_optimal_route: false` and the optimal corridor carries no ERP — and gives
`39.00 - 24.50 - 0.00 = 14.50`. The one draft that gave 14.50 read it straight
off `charged_over_quote.value` and was the only draft that voted; with a quorum
of three the case escalated. **Cause as stated in the review, confirmed.**

### 504 and 530 — POL-RD-10(5) against POL-RD-08 on an uncited closure claim

**Verified.** Both cases have a driver account of an external event, and in both
the only advisory artifact is `MISSING` at weight 0.0: `EV-ADVIS-00504-01` (a
car flashing its headlights, read as an accident ahead) and `EV-ADVIS-00530-01`
(a bus breakdown). Both drafts escalate, and both name the trigger:

- 504: "POL-RD-10(5) names precisely this situation — a closure asserted with no
  traffic_advisory — as one in which no final monetary ruling may issue."
- 530: "POL-RD-10(5) makes a closure asserted with no traffic_advisory a
  mandatory escalation."

The keys go the other way and decide on the merits: 504's key says "The 'car
flashing me' story is not an advisory: EV-ADVIS-00504-01 is MISSING, so POL-RD-03
cannot be run", and 530's says "The 'bus breakdown' has no advisory
(EV-ADVIS-00530-01 MISSING)". The mechanism the keys apply is POL-RD-08's rule
that an assertion citing no evidence ID carries no weight — stated by name in the
corpus key for **105**, which is the same shape: "it cites no advisory and
EV-ADVIS-00105-01 is MISSING, so under POL-RD-08 the claim is discarded and the
shifted burden is not discharged."

So the borderline is real and it is a genuine ambiguity in the policy text:
POL-RD-10(5)'s example ("a closure asserted with no traffic_advisory") can be
read as "no advisory is present", which is what 504 and 530 did, or as
"a closure is asserted that the record does not carry", which is what the keys
read and what POL-RD-08's discarding rule supports. **Cause as stated in the
review, confirmed; the same borderline as development case 105.**

### 508 — the same pattern, with the concession made out loud

**Verified, and stronger than the review states.** 508 escalates on the same
POL-RD-10(5) reading, and its explanation concedes the POL-RD-08 point in terms
before escalating anyway:

> "The driver's bare account in the counterparty statement cites no evidence ID
> and would in any event carry no weight under POL-RD-08; but the defence cannot
> be tested, and escalation under POL-RD-10 is terminal."

The key for 508 is `PARTIAL_REFUND` 6.00: the deviation is established (25.5%,
above the 20% gate, below the material gates), and the driver's "CTE queue"
assertion has no advisory, so it is discarded and the arithmetic runs. The run
agrees on every fact and on the arithmetic — it prints the 6.00 as the figure the
reviewer should apply — and then holds the money instead. **Cause as stated in
the review, confirmed.**

### 523 — the one dangerous miss

**Verified.** 523 is the only miss that pays out on a claim the key says is not
supported, and the judge's own findings contradict the payout. The key is
`NO_ACTION`: the excess is 6.7%, below POL-RD-01's 20% limb, so no deviation is
established; the ECP gantry line is crossed within POL-RD-09's 250 m radius and
is not phantom; the 6.00 airport surcharge is proper on a trip originating at
Changi; POL-RD-09(1) refunds off-route ERP only inside a POL-RD-02 recomputation
and POL-RD-02 does not run, POL-RD-09(2) needs a POL-RD-03 exoneration, and the
fare is `METERED` so POL-RD-11(b) is unavailable. "There is no clause under which
this gantry is refundable, and the cash the rider handed over is not in the
pool."

The run refunds 4.00. Its reasoning: the trace does cross the gantry and the
line is not a POL-RD-09(4) defect — the judge says so explicitly — but the
driver's own statement admits he collected the toll in cash and offers "refund
him the app one", so the app line is duplicative and "is corrected as a
standalone pass-through under POL-RD-09, available whether or not a deviation
exists". That last phrase belongs to POL-RD-09(4), the limb the judge had just
ruled out. The policy text gives no route for a cash duplicate, and the rider's
cash payment is not in the pool. So the run invented a clause route, on a
finding its own explanation had already refused, and moved 4.00 the policy does
not move. **Cause as stated in the review, confirmed. This is the one miss that
pays money the policy does not authorise, and it is the one to fix first.**

### 622 — the policy requires a referral the key omits

**Verified.** 622's ruling and both money fields match the key exactly —
`ESCALATE`, both null — and the only difference is one referral:

- produced: "POL-NS-07: direct the human reviewer to refund the rider's
  cancellation fee of SGD 4.00 in full."
- key: no referrals at all.

POL-NS-07 requires it in terms: where the anti-farming check trips, "the
escalation packet must DIRECT THE REVIEWER to refund the rider's cancellation
fee in full". The check trips on 622 (11 no-show terminations in 30 days, 11/60 =
0.183 > 0.08), and the key's own rationale says "the packet must state that
POL-NS-02 would refund the rider on this record" — while the key's referral list
is empty. The grader fails the field because a referral was produced where the
key expects none; that rule is correct in general and wrong here. **Cause as
stated in the review, confirmed: the run is right and the key omits the referral
the policy requires — the generator's default.**

### 627 — whether the conflict tag impairs the deciding fact

**Verified in substance, with one correction to the review.** The pre-pass tagged
`EV-TRIP-00627` `CROSS_SOURCE_CONFLICT`, weight 0.40, on the ground that
`trip_record.arrived_at` and `wait_time_min` are contradicted by the trace over
the same interval. The key escalates on two grounds: POL-NS-09(b), because two
admissible artifacts contradict each other directly on arrival and dwell, and
POL-NS-09(a), because POL-GEN-02(2) caps confidence at the deciding artifact's
weight of 0.40, below the 0.70 floor. The run ruled `FULL_REFUND` 6.00, holding
that the deciding fact — that the driver never entered the geofence — is carried
by `EV-GPS-00627` at weight 1.0, so the cap is 1.0, and that POL-NS-01(b) and
POL-NS-02 resolve the conflict in one direction so POL-NS-09(b) does not fire.
The case turns on whether the conflict tag impairs the deciding fact.

The review's supporting point — "development case 201 was decided the other way"
— is true in outcome but needs stating precisely, because the difference is the
tag. 201 is the development case with the same substantive shape: the trip
record's `arrived_at` marker at 08:02:14 matches a fix 779.9 m from the pin, the
key rules `FULL_REFUND` 4.00 on the merits, and it records a POL-NS-05(ii)
false-arrival referral — exactly the referral the run emitted on 627. But 201's
trip record carries **no** conflict tag (weight 1.0; its only issue is the
missing advisory), and the driver there was stationary at the wrong venue rather
than moving. In the two development cases the pre-pass **did** tag
`CROSS_SOURCE_CONFLICT` — 112 and 210, both weight 0.40 — the keys escalate, the
same way as 627's. So the development set contains both dispositions and the tag
is the line between them, which is precisely the question 627 turns on. **Cause
as stated in the review, confirmed; the reference to 201 holds, with the
qualification that 201 is untagged and 112/210 are the tagged precedents.**

## (d) What this run does not change

- **No ruling in the key changes.** Every miss above is recorded against the key
  as it stands, including the two where the key itself looks wrong. 622 is the
  clearest of those: the policy requires a referral the key omits, and the run is
  penalised for producing it. None of that is acted on here —
  `eval/answers/wild/ground_truth.json` is frozen from the moment it was
  imported, under the standing rule in `START-HERE.md`. Editing the expected
  result so a run scores better destroys the only independent measurement this
  project has.
- **No code, prompt or policy changes.** `git diff --quiet freeze-2026-09-30 --
  tribunal prompts policy` still holds after this work, as it held before the
  run. Nothing in this note edits `tribunal/`, `prompts/` or `policy/`.
- **The 55/64 figure is the submission's only generalisation figure**, reported
  beside the development figures and never summed with them. One figure over 64
  cases plus another over 44 is not a measurement of 108 cases.
- **The conflict in the set's own README is still unresolved.** The archive's
  `README.md` calls this 64-case set a development and regression set and names a
  different, 24-case set as the sealed one
  (`docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md`). This run does not
  settle it, and the owner must, before this figure is reported as
  generalisation.

**Any fix belongs to a later version, with a new sealed set.** The draft check
that rejected 517 and 533 is a real defect — the money block cannot express a
difference, which is what an upfront-quote refund is — and it is the kind of
change that would move rulings. Changing it now would mean the run reported as
the generalisation figure was produced by a system that is no longer the system.
The repair, when it is made, is measured on the development sets, and the
generalisation figure is taken again from a set that has not been read. This run
is closed as it stands.
