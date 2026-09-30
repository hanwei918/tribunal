# The amount read-off rule

**2026-09-30, part B of the after-held-out-run task. No model call was made.**

Two of the held-out set's 64 cases produced no ruling, and the reason was not the
judge. In 517 and 533 the judge computed the right refund and the pipeline's own
draft check refused to publish it: `DRAFT_AMOUNT_NOT_READ_OFF` rejected **all
four** drafts of each case. The check holds a draft's amount to the brief's money
block, and the rule it reads the block by accepts a figure the block publishes or
the **sum** of two or three of them — and never a **difference**. On an
upfront-quoted fare the remedy POL-RD-11(a) gives is a difference by
construction. 533's key amount, 19.30, is `22.30 − 3.00` of two figures the block
publishes, so the rule could not read it and the case died with `SHAPE`.

This part adds a second rule, measures what it would have made of the drafts the
three runs already recorded, and **changes no default**. `--amount-rule signed`
is off; every committed run was judged by the published rule and still is.

## The two rules

| rule | an amount is |
|---|---|
| `published` — the default, and what every run so far used | a figure the brief's money block publishes, or the **sum** of two or three of them |
| `signed` | the same, or a **signed combination** of two or three published figures: the leading term positive, the rest carrying either sign, the result above zero |

The sum is searched before the difference, so an amount both rules accept is
reported with the same reading under either. The leading term is fixed positive,
so `51.30 − 29.00` is a reading and `29.00 − 51.30` is not: a rule that accepted
both would report a negative reading of a positive amount as though the block
published it. An amount at or below zero is never read off under either rule.

The refusal names the rule it was made under — "nor the sum of two or three of
them" against "nor a signed combination of two or three of them" — so a signed
run's record says which rule rejected a draft rather than leaving a reader to
infer it from a directory name.

## The measurement

    python3 -m eval.amount_rule

re-reduces the drafts the three runs already recorded — the corpus's 29 cases,
the second development set's 15 and the held-out set's 64 — under both rules, and
writes `runs/amount-rule/report.md` and `runs/amount-rule/amount-rule.json`. It
makes no model call. The drafts come off the transcripts through the same
reconstruction `eval/verify_drafts.py` and `eval/baselines.py` use, so the two
readings differ in the rule and in nothing else; re-running the judge instead
would have made any difference a difference between two panels rather than the
effect of the rule.

All 108 recorded panels were rebuilt and **no case was refused**. The published
reading reproduces the ruling each run itself published for every one of them, so
the two rules are being compared on the runs' own panels and not on two
reconstructions of them.

| | |
|---|---|
| cases read | **108** (29 + 15 + 64), 0 refused |
| matching both ways | **98** |
| matching → missing | **0** |
| missing → matching | **1** — 533 |
| missing both ways | **9** |
| a safe outcome turned into a monetary ruling that differs from the key | **1** — 501 |

Per set:

| set | run directory | cases read | matching both ways | missing → matching | missing both ways |
|---|---|---|---|---|---|
| corpus | `runs/deepseek-deepseek-flash/` | 29 of 29 | 29 | 0 | 0 |
| codex | `runs/codex/deepseek-deepseek-flash/` | 15 of 15 | 14 | 0 | 1 — 9111 |
| held-out | `runs/wild/deepseek-deepseek-flash/` | 64 of 64 | 55 | 1 — 533 | 8 — 501, 504, 508, 517, 523, 530, 622, 627 |

The held-out row cross-checks against the run's own figure: 55 cases match under
both rules, which is the 55/64 four-field figure the sealed run reported, and 517
and 533 are the two cases it counted as misses. Nothing here recomputes that
figure; it is read from the same committed run and it comes out the same.

Two cases have a transcript and no cached result — 517 and 533, the two the run
failed — so there is no cache entry to carry the brief digest a replay is checked
against. For those two the digest is read from the transcript's own advocate
entries, which record it beside the call it was handed to; every other condition
the replay check makes is unchanged, and a case whose recorded digest is not the
brief this code builds is still refused and reported with its reason. No case was.

## The two cases it changes

### 533 — from no ruling to the key's own figure

| | |
|---|---|
| published rule | no ruling (all four drafts rejected) |
| signed rule | `PARTIAL_REFUND` **19.30** |
| key | `PARTIAL_REFUND` **19.30** |

The block publishes `charged_over_quote.value` 22.30 and
`erp_lines.lines[0].amount_sgd.value` 3.00. `22.30 − 3.00` is 19.30, which is
exactly the key, and the published rule cannot read it because it is a
difference. Under the signed rule all four drafts vote, the panel carries, and
the case is decided correctly. This is the case the whole measurement exists for,
and it is the only one where the signed rule turns a miss into a match.

### 501 — from a safe escalation to a wrong monetary ruling

| | |
|---|---|
| published rule | `ESCALATE` |
| signed rule | `PARTIAL_REFUND` **8.50** |
| key | `PARTIAL_REFUND` **14.50** |

The block publishes `charged_over_quote.value` 14.50 and
`erp_lines.off_optimal_route_total.value` 6.00. `14.50 − 6.00` is 8.50, so under
the signed rule the three drafts that proposed 8.50 become readable and vote, and
the panel publishes 8.50 against a key of 14.50. This is the one case where the
signed rule decides a case that was previously left alone, and decides it
wrongly.

It is worth being precise about what makes it wrong, because the arithmetic is
not the fault. The published rule was **right** to refuse those three drafts:
POL-RD-11(a) reduces the excess over the quote by the pass-throughs that are
*properly chargeable*, the key takes those as 0.00, and the 6.00 the drafts
subtracted is a surcharge the fare ledger never billed
(`EV-FARE-00501.airport_surcharge: 0.0`) — the same finding
`docs/notes/2026-09-30-the-sealed-run.md` records. What the signed rule does is
make that subtraction readable, because the block *does* publish the 6.00. A rule
that reads an amount off the block's figures cannot tell a pass-through that is
properly chargeable from one that is merely published, and on 501 those two
answers are 14.50 and 8.50.

Note that 501 was already a miss under the published rule — it escalated where
the key refunds — so the signed rule does not cost the measured figure. It
changes what kind of miss it is: from a case the system declined to decide to a
case it decided, in the rider's disfavour, by 6.00.

## The case it does not change

**517** is read off by neither rule, and it is here so that "the signed rule fixes
the two cases the published one lost" is not the claim a reader takes away. Its
key is `PARTIAL_REFUND` 33.50 and its block publishes `charged_total.value` 67.50,
`quoted_fare.value` 28.00, `charged_over_quote.value` 39.50 and three ERP totals
of 0.00. The key's arithmetic is `67.50 − 28.00 − 6.00 = 33.50`, where the 6.00
is an airport surcharge that is on the ledger but is **not** a figure the block
publishes — so 33.50 is neither a published figure, nor a sum, nor a signed
combination of what the block holds, and no rule that reads the block can reach
it. Three of the four drafts gave 33.50 exactly and all four abstained.

That is the limit of what this switch buys. It closes the case where the
difference is between two figures the block publishes (533) and not the case
where one operand is missing from the block altogether (517). Closing 517 is a
different piece of work — the block's model of a refund would have to carry the
surcharge — and this part does not attempt it.

## What is not changed

- **The default rule.** `pipeline.DEFAULT_AMOUNT_RULE` is `published`, the
  command-line default is `published`, and a run that names `published` writes
  the same bytes it wrote before the switch existed — asserted by
  `tests/test_amount_rule.py`, which runs the same case twice with every clock
  the run stamps pinned and compares the whole run directory byte for byte.
- **No committed run.** Nothing under `runs/deepseek-deepseek-flash/`,
  `runs/codex/deepseek-deepseek-flash/` or `runs/wild/deepseek-deepseek-flash/`
  is edited, and the measurement refuses a destination that is one of them or
  lies inside one.
- **No figure.** The 55/64 generalisation figure is what it was. This
  measurement reads the run that produced it and adds nothing to it.
- **No ruling, prompt, policy or key.** Nothing in `prompts/`, `policy/` or
  `eval/answers/` is touched.

### The freeze check no longer holds, and that is a consequence of this part

The owner's check was `git diff --quiet freeze-2026-09-30 -- tribunal prompts
policy`: the code that produced the held-out figure had not moved. It now
fails, because `tribunal/pipeline.py` carries the second rule. That is the switch
this part was asked for and not an accident, and it is recorded here because it
is a real change to what that check certifies.

It does not change the figure. The run is committed as produced, the frozen code
produced it, and the switch is off — so the bytes of `runs/wild/` are still the
bytes of a run judged by the published rule. What it does mean is that the
repository is no longer the repository `freeze-2026-09-30` names, and the
held-out set is run **once**. `wild-v1` cannot be run again to price the change,
and the next generalisation figure has to come from a set that has not been read.

## The recommendation

**Adopt `signed`, in a later version, and take the generalisation figure again
from a fresh held-out set — but not before the 501 shape is closed.**

The measurement is one-sided on the recorded data. One case moves from missing to
matching and no case moves the other way, so the figure the submission reports
would go from 55/64 to 56/64, and the corpus and second-set figures would not
move at all. The one case it newly decides wrongly, 501, was already a miss, so
on the four-field metric the rule is free.

That is not the whole argument, and it is why this is a recommendation rather
than a change. The reason 533's 19.30 becomes readable is the reason 501's 8.50
becomes readable: the block publishes both operands. For 533 that is right — the
key's refund *is* that difference. For 501 it is not — the key says the
subtracted figure is not properly chargeable, and the block publishing it is not
evidence that the rider is owed the reduction. The rule cannot tell the two
apart, and no rule that reads a draft's amount off the money block alone can.
Without a check on *which* published figures a refund may be reduced by, adopting
`signed` buys 533 and starts publishing 8.50 where the rider is owed 14.50.

So the order is: close the 501 shape first, then adopt `signed`, then measure both
together on a held-out set nobody has read. Adopting the rule now would be
choosing 533 at the price of deciding 501 wrongly, and the price is paid in
money the policy does not authorise.

**Nothing here adopts it.** The switch is off, the default is the rule every
committed run was judged by, and whether to turn it on is the owner's decision
after reading the table above.

## Where the output lives

| path | what it is |
|---|---|
| `runs/amount-rule/report.md` | The per-case table for all three runs, the movement counts, and every case the signed rule changes or newly decides wrongly. |
| `runs/amount-rule/amount-rule.json` | The same figures as parsed values: per set the cases read, the refused cases with their reasons, the movement counts, the cases with no cached result, and the cases whose published reading is not the run's own. |
| `runs/amount-rule/<rule>/<model>/` | Where a **run** under a non-default rule goes — `python3 -m eval.development_sets --set wild --amount-rule signed`. The rule is a path component, so two rules are two directories, and `--amount-rule` is refused together with `--ablate`, `--precedents`, `--policy-version N>=2`, `--report`, `--compare`, `--replay-check`, `--verify-recorded-drafts` and `--external`. `--replay-advocates` is deliberately **not** refused: a replay calls only the judge, and the rule is what a draft's amount is held to, so it is a request the pipeline can honour. No such run is committed. |

The measurement is never written into a run directory, and it refuses a
destination that is one — by name for the three headline directories, by what it
holds for any other directory carrying a run's own `run.json` or `case-*.json`,
and for everything under `runs/external/`.

## The tests

`tests/test_amount_rule.py`, 44 tests, all passing:

- the rule, on figures built by hand: a published figure, a sum of two and of
  three, a difference, the three-term signed forms, the leading term's sign, an
  amount at or below zero, the sum searched before the difference, and an unknown
  rule refused rather than defaulted;
- the draft check: a difference abstains under the published rule and votes under
  the signed one, the refusal names the rule it was made under, and an amount
  neither rule can read is refused by both;
- byte-identity with the switch off, over the whole run directory;
- the refusals on both command lines, including that `published` is not a switch
  and that `--replay-advocates` is not refused beside the rule;
- the destination guard, including that a scratch `--runs-dir` does not make a
  headline directory under the repository's own `runs/` writable;
- the measurement's assembly: a fixture run whose four drafts compute a
  difference publishes nothing under one rule and a ruling under the other, and
  the three held-out cases are read off the committed run — 501 turned unsafe,
  533 missing → matching, 517 read off by neither.

The three held-out cases are read from `runs/wild/deepseek-deepseek-flash/` and
not restated, so a case that moved would move the test rather than pass it. No
test in the file calls a model.
