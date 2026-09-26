# The full re-run, with the policy's arithmetic in the brief

**2026-09-27** (the run itself finished 00:32 SGT on the 27th; it started at 22:05
SGT on the 26th). The previous session put the policy's arithmetic into the brief
as derived money facts, computed by code, and made every one of the 44 briefs
stale. The two development sets have now been re-run in full against those
briefs, and this note records what came out, verified from the files under
`runs/`.

## What was run

At `efbc15a` (`git_commit` in both `run.json` files), judge prompt digest
`324d5613275d27963b713b3adef9576007b97801794551a8d0719b52e5eebd80`, on the
owner's balance, weekend off-peak, `--concurrency 2`, four judge drafts per case,
and **no replay**: `replay` is `null` in both invocations, so the advocates were
re-run in full and saw the new brief too.

```
python3 -m eval.run_benchmark --force --concurrency 2
python3 -m eval.development_sets --set codex --force --concurrency 2
```

The corpus invocation ran 14:05:05 to 15:48:36 UTC (1 h 43 m 31 s); the second
set's ran 15:48:37 to 16:32:31 UTC (43 m 55 s). Both completed with no failures
and no timeouts.

## The grade, read off the reports

| | cases | four-field exact | fails on |
|---|---|---|---|
| corpus | 29 | **28/29 = 96.6%** | 211 (`ruling`, `amount_sgd`) |
| second set | 15 | **14/15 = 93.3%** | 9111 (`ruling`, `amount_sgd`, `referrals`) |
| **combined** | **44** | **42/44 = 95.5%** | |

That is the same grade as the previous voting run, on the same two cases. The
per-field figures are the same shape as before: `driver_compensation_sgd` 29/29
and 15/15; `referrals` 29/29 and 14/15.

The corpus report's escalation calibration is unchanged in substance: 6 produced
escalations against 5 expected, precision 5 of 6, recall 1.0, and the four
INDETERMINATE cases (110, 112, 210, 213) escalated 4 of 4. The one over-escalation
is still 211.

## Per case, against the previous voting run

The previous voting run is the one committed at `7a0836f`. "Change" compares the
outcome, the vote, the ruling and the money; the referral **prose** is free text
and is compared as the clause references the vote extracts from it, which is what
the vote itself compares.

| case | previous voting run | this run | change |
|---|---|---|---|
| 101 | carried 4/4 · PARTIAL_REFUND 8.05 | carried 4/4 · PARTIAL_REFUND 8.05 | — |
| 102 | carried 4/4 · NO_ACTION - | carried 4/4 · NO_ACTION - | — |
| 103 | carried 4/4 · PARTIAL_REFUND 4.0 | carried 4/4 · PARTIAL_REFUND 4.0 | — |
| 104 | carried 4/4 · PARTIAL_REFUND 3.6 | carried 4/4 · PARTIAL_REFUND 3.6 | — |
| 105 | carried 4/4 · FULL_REFUND 65.13 | carried_not_unanimous 3/4 · FULL_REFUND 65.13 | vote 4/4 → 3/4 |
| 106 | carried 4/4 · PARTIAL_REFUND 10.75 | carried 4/4 · PARTIAL_REFUND 10.75 | — |
| 107 | carried_not_unanimous 3/4 · PARTIAL_REFUND 7.45 | carried_not_unanimous 3/4 · PARTIAL_REFUND 7.45 | — |
| 108 | carried 4/4 · NO_ACTION - | carried 4/4 · NO_ACTION - | — |
| 109 | carried 4/4 · DRIVER_COMPENSATION 3.15/3.15 | carried 4/4 · DRIVER_COMPENSATION 3.15/3.15 | — |
| 110 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |
| 111 | carried 4/4 · NO_ACTION - | carried 4/4 · NO_ACTION - | — |
| 112 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |
| 113 | carried 4/4 · NO_ACTION - | carried 4/4 · NO_ACTION - | — |
| 114 | carried 4/4 · PARTIAL_REFUND 13.7 | carried 4/4 · PARTIAL_REFUND 13.7 | — |
| 115 | carried 4/4 · PARTIAL_REFUND 2.0 | carried 4/4 · PARTIAL_REFUND 2.0 | — |
| 201 | carried 4/4 · FULL_REFUND 4.0 | carried 4/4 · FULL_REFUND 4.0 | — |
| 202 | carried 4/4 · DRIVER_COMPENSATION 4.8/4.8 | carried 4/4 · DRIVER_COMPENSATION 4.8/4.8 | — |
| 203 | carried 4/4 · FULL_REFUND 4.0 | carried 4/4 · FULL_REFUND 4.0 | — |
| 204 | carried 4/4 · FULL_REFUND 4.0 | carried 4/4 · FULL_REFUND 4.0 | — |
| 205 | carried 4/4 · FULL_REFUND 4.0 | carried 4/4 · FULL_REFUND 4.0 | — |
| 206 | carried 4/4 · FULL_REFUND 4.0/2.0 | carried 4/4 · FULL_REFUND 4.0/2.0 | — |
| 207 | carried_not_unanimous 3/4 · ESCALATE - | carried_not_unanimous 3/4 · ESCALATE - | — |
| 208 | carried 4/4 · DRIVER_COMPENSATION 6.4/6.4 | carried 4/4 · DRIVER_COMPENSATION 6.4/6.4 | — |
| 209 | carried 4/4 · NO_ACTION - | carried 4/4 · NO_ACTION - | — |
| 210 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |
| 211 | escalated 2/4 · ESCALATE - | escalated 2/4 · ESCALATE - | — |
| 212 | carried 4/4 · FULL_REFUND 4.0 | carried 4/4 · FULL_REFUND 4.0 | — |
| 213 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |
| 214 | carried 4/4 · DRIVER_COMPENSATION 3.2/3.2 | carried 4/4 · DRIVER_COMPENSATION 3.2/3.2 | — |
| | **second development set** | | |
| 9101 | carried 4/4 · DRIVER_COMPENSATION 3.2/3.2 | carried 4/4 · DRIVER_COMPENSATION 3.2/3.2 | — |
| 9102 | carried 4/4 · DRIVER_COMPENSATION 4.8/4.8 | carried 4/4 · DRIVER_COMPENSATION 4.8/4.8 | — |
| 9103 | carried 4/4 · FULL_REFUND 8.0 | carried 4/4 · FULL_REFUND 8.0 | — |
| 9104 | carried 4/4 · FULL_REFUND 4.0 | carried 4/4 · FULL_REFUND 4.0 | — |
| 9105 | carried 4/4 · FULL_REFUND 4.0 | carried 4/4 · FULL_REFUND 4.0 | — |
| 9106 | carried 4/4 · FULL_REFUND 6.0 | carried 4/4 · FULL_REFUND 6.0 | — |
| 9107 | carried 4/4 · DRIVER_COMPENSATION 3.2/3.2 | carried 4/4 · DRIVER_COMPENSATION 3.2/3.2 | — |
| 9108 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |
| 9109 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |
| 9110 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |
| 9111 | carried_not_unanimous 3/4 · PARTIAL_REFUND 9.15 | escalated 2/4 · ESCALATE - | **PARTIAL_REFUND 9.15 → ESCALATE -** |
| 9112 | carried 4/4 · NO_ACTION - | carried 4/4 · NO_ACTION - | — |
| 9113 | carried 4/4 · PARTIAL_REFUND 9.05 | carried_not_unanimous 3/4 · PARTIAL_REFUND 9.05 | vote 4/4 → 3/4 |
| 9114 | carried 4/4 · FULL_REFUND 3.2 | carried 4/4 · FULL_REFUND 3.2 | — |
| 9115 | carried 4/4 · ESCALATE - | carried 4/4 · ESCALATE - | — |

**41 of 44 are identical.** Three moved, and only one of them changed what the
run answered:

- **105** lost unanimity and nothing else. Its dissent is the position-swapped
  draft, and it proposes the same ruling and the same money: `FULL_REFUND 65.13`.
- **9113** lost unanimity and nothing else. Its ruling and amount are still
  `PARTIAL_REFUND 9.05`.
- **9111** lost its majority and escalated. This is the only case whose answer
  changed, and it was already wrong: the key is `PARTIAL_REFUND 10.15` and the
  previous run carried `PARTIAL_REFUND 9.15`.

So the money facts moved the **vote** on three cases and the **answer** on one,
and the grade did not move at all.

## The vote

| | cases |
|---|---|
| unanimous (4 of 4) | **38** |
| 3 of 4, carried | 105, 107, 207, 9113 — all four **carried and correct** |
| 2 of 4, no majority, escalated | 211, 9111 |

The four 3-of-4 cases are worth splitting, because they are not the same kind of
disagreement. The dissent in each:

| case | dissent | what the dissent proposes |
|---|---|---|
| 105 | draft 4, position-swapped | `FULL_REFUND 65.13` — the same ruling and the same money |
| 107 | draft 2, seed 202 | `ESCALATE` against `PARTIAL_REFUND 7.45` — a substantive disagreement |
| 207 | draft 4, position-swapped | `ESCALATE` — the same ruling, and no money either way |
| 9113 | draft 1, seed 101 | `PARTIAL_REFUND 8.05` against `9.05` — a substantive disagreement |

Two of the four are not disagreements about the answer at all, and the next two
sections say why.

## 9113: are the money facts why three drafts reach 9.05?

**No, and the run says the opposite of what that question expects.** The previous
voting run reached the key's 9.05 **unanimously, four drafts of four**. Three of
four now reach it. The money facts did not make 9.05 reachable; it was already
reached.

What the drafts that reach 9.05 say is that they read the block. Draft 2:

> Refund = 31.42 charged less 23.416 = 8.004, payable 8.05. … Separately, the
> 1.00 charged at the 'Pelton lawful diversion entry' gantry is a
> billing-integrity failure: the closest fix on the trace is 834 m from that
> gantry, outside the 250 m match radius, so the trace never passes it. Under
> POL-RD-09(4) that line is refunded in full as a standalone correction … The
> total refund is therefore 8.05 + 1.00 = 9.05.

Draft 3 is explicit that the block is what it is reading:

> POL-RD-09(4) makes that a billing-integrity failure: the SGD 1.00 is refunded
> in full as a standalone correction and is referred below. **This is why the
> total is SGD 9.05 rather than the SGD 8.05 claimed.**

Both operands it names are the block's: `closure[0].refund.payable` is published
as `8.05` and the Pelton line's `amount_sgd` as `1.00`.

The dissenting draft is the one that reads the block and stops. Draft 1
(seed 101, the same seed that reached 9.05 in the previous run):

> The 1.00 Pelton gantry is the platform-classified **on-optimal-route** line and
> is carried inside the recomputed fare.

The block publishes exactly that classification, next to a distance that
contradicts it under the clause: for the Pelton line it carries
`on_optimal_route: true` **and** `trace_proximity.nearest_fix.distance_m`
`834.181…`. Draft 1 read the flag and not the distance; drafts 2, 3 and 4 read
the distance. The previous run's draft 1 read the distance too, and said so:

> The SGD 1.00 'Pelton lawful diversion entry' line is different: the nearest
> trace fix is 834.18 m, outside the 250 m radius, so the trace never passes that
> gantry. POL-RD-09(4) makes that a billing-integrity failure, refunded in full
> as a standalone SGD 1.00 correction …

The 834 m figure was already in the brief before this session: at `7a0836f` the
trace already carried `erp_gantry_proximity`. What the money block added is the
ERP **line** — its `amount_sgd` and its `on_optimal_route` flag — beside that
distance, and the closure-adjusted payable.

So the honest reading is: the money facts put both operands and the distance in
front of every draft, which is what makes 9.05 a reading rather than a
calculation; but they also put a platform classification beside a contradicting
distance, and one draft of four took the classification as the answer. The block
deliberately publishes no `crossed` verdict, so the 250 m radius is still the
judge's to apply — and one draft did not apply it. That is evidence for the next
session, not a defect to fix now.

## 9111: what the vote compares for referrals

All four drafts agree on the ruling and the amount: `PARTIAL_REFUND 9.15`, with
`driver_compensation_sgd` null. They differ only in what the vote extracts from
their referrals:

| draft | seed | referral strings | clause references the vote extracts |
|---|---|---|---|
| 1 | 101 | **1** | `POL-RD-09(4)` |
| 2 | 202 | **1** | `POL-RD-02`, `POL-RD-09(4)` |
| 3 | 303 | **1** | `POL-RD-02`, `POL-RD-09`, `POL-RD-09(4)` |
| 4 | 42 (position-swapped) | **1** | `POL-RD-02`, `POL-RD-09`, `POL-RD-09(4)` |

**The four proposals do not differ in the number of referrals.** Every draft
proposes exactly **one** referral, and in all four it leads with `POL-RD-09(4)`
and asks for the same thing — the SGD 2.00 'Tuas South Avenue 8 loop' line to be
recorded as a billing-integrity finding. What differs is the set of clause
references the vote pulls out of that one referral's **prose**:

- draft 1 mentions only `POL-RD-09(4)`;
- draft 2 also writes "…the amount is returned once, inside the **POL-RD-02**
  figure…";
- drafts 3 and 4 also write "outside **POL-RD-09**'s 250 m crossing radius" and
  "comprehended in the **POL-RD-02** refund".

So the answer to the question is: they differ **in clause references as the vote
extracts them**, and those differences are entirely incidental mentions of other
clauses in the explanatory prose, not additional referrals. A reader comparing
the four referrals as referrals would call them the same referral.

### What the vote compares today, exactly

`tribunal.pipeline.referral_clause_references` is the whole of it. For each
string in the draft's `referrals` list it runs

```
REFERRAL_CLAUSE_RE = re.compile(r"POL-[A-Z]{2,4}-\d{2}(?:\([a-z0-9]+\))?")
```

over the text, unions every match into a **set**, and sorts it. Order is dropped
and duplicates collapse — deliberately, since a referral is free prose and two of
them cannot be compared as strings. The limb is kept, because a referral to the
right clause with the wrong limb is a different referral. The four fields are
then voted on **as one unit** (`vote_key`), so a draft that agrees on the ruling
and the amount but differs on this set is counted as not agreeing at all.

What that set does **not** distinguish: how many referrals there are, which
referral a reference came from, what any referral asks for, and whether a
reference is the subject of a referral or a clause mentioned in passing while
explaining it. Every `POL-…` string in the prose counts, wherever it sits.

### What this costs, and what it does not

9111 escalates on a panel that substantively agreed, and the two other cases
show the same mechanism doing less damage:

- **105**'s dissent is one referral led by `POL-RD-06(c)` in both the agreeing
  and the dissenting draft. The dissenting draft's prose adds "against the
  `POL-RD-06` threshold of 3", so the extracted set gains the parent clause and
  the draft is counted as disagreeing.
- **207**'s dissent is one referral led by `POL-NS-07` in both. The dissenting
  draft's prose adds "held under `POL-NS-09` pending that review", so its set
  gains `POL-NS-09` and it is counted as disagreeing.

So three of the six non-unanimous cases — 105, 207 and 9111 — are non-unanimous
**only** because of this extraction, and one of them escalated for it. In the
previous voting run the same mechanism produced 105 and 207's splits too, and
207's dissenting draft added `POL-NS-09(d)` where it now adds `POL-NS-09`.

**This is evidence, not a change.** Nothing about the referral comparison was
altered in this session.

It is also worth recording that fixing it would not have rescued 9111: all four
drafts propose **9.15** and the key is **10.15**, because they hold that the
SGD 1.00 on-optimal ERP line is already comprehended in the POL-RD-02 figure
rather than added to it. A correct referral comparison would have carried
`PARTIAL_REFUND 9.15` — still wrong on the amount.

## Every carried ruling against the brief's money block

42 of the 44 cases carried a ruling (211 and 9111 escalated, so they have
nothing to check). For each, `amount_sgd` and `driver_compensation_sgd` were
asked whether they are one of the money figures the brief's money block
publishes, or the sum of two or three of them. A money figure means a numeric
leaf of the block that is not under `constants` or `not_structured` and is not a
named non-money quantity — kilometres, minutes, a multiplier, a share, a
quantum.

**Two money fields do not read off the block, and both are on case 109.**
`amount_sgd` and `driver_compensation_sgd` are both **3.15**, which is
POL-RD-04's closing limb: `0.75 × 4.16 km = 3.12`, rounded up to the nearest
0.05. POL-RD-04 states that rate and its cap only in prose, so the block names
the figure as not structured and computes no compensation for it. The draft got
3.15 by doing the clause's arithmetic itself, and got it right.

Everything else reads off, and the ways divide as they did in the key check:

- **Directly, one figure carries it.** 101, 104, 106, 107, 114 on
  `refund.payable` or `closure[0].refund.payable`; 202, 208, 214, 9101, 9102,
  9107 on `driver_compensation`; 206's compensation on `goodwill`.
- **Directly, two figures sharing the value.** 103, 105, 115, 201, 203, 204,
  205, 206, 212, 9103, 9104, 9105, 9106, 9114.
- **As a sum of two published figures.** **9113**: `closure[0].refund.payable`
  8.05 plus the Pelton line's `amount_sgd` 1.00 = **9.05**.

The block's own `refund.payable` for 9113 is **12.75**, the refund against the
unadjusted optimal route; 8.05 is the closure-adjusted figure and is what the
carried ruling uses. The sum is reproducible from two published operands even
though the sum itself is not a published figure — the same shape the answer key
has, which is what makes 9113 checkable at all.

## The cost

**9,121,722 tokens, written as the owner's balance.** Nothing was borrowed:
`billed_to_another_run` is **0** in both invocations and `replay` is `null`, so
the whole figure is this session's own spending.

| | prompt | completion | reasoning | cached | consumed |
|---|---|---|---|---|---|
| corpus | 3,364,259 | 2,874,875 | 2,617,136 | 1,729,271 | **6,239,134** |
| second set | 1,662,265 | 1,220,323 | 1,108,984 | 826,880 | **2,882,588** |
| total | 5,026,524 | 4,095,198 | 3,726,120 | 2,556,151 | **9,121,722** |

`consumed` is every token billed; `cached_tokens` is a breakdown of the prompt
and is not added to it; `reasoning_tokens` is a breakdown of the completion and
is not added either.

## The viewer, and the assertion that moved

The run is current again: every one of the 29 corpus briefs matches the brief
this code builds, so `ui.build.run_has_moved_on` is `False` and the seven
conditional skips in `tests/test_ui_build.py` lifted by themselves, with nothing
unskipped by hand — which is what that mechanism was built to do. The page was
rebuilt from the new run: **29 cases, 2,325,987 bytes**, and `python -m ui.build
--check` is identical to a fresh build under both 3.13.12 and 3.9.6.

One test needed re-expressing rather than updating.
`JudgeVoteTests.test_the_contested_cases_are_the_ones_the_run_marked` pinned the
contested set as the literal `[107, 207, 211]`, and the re-run contests 105, 107,
207 and 211. Its own docstring already said which cases those are is dated, so
the literal was replaced by the invariant it promised: the page's contested set
is exactly the cases the run's own record marks not unanimous, the run records at
least one, and a case is contested exactly when the run recorded an agreement
below 1 for it. That holds on both sides of a re-run, which a dated list cannot.
