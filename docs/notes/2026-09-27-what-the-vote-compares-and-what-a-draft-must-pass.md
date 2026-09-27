# What the vote compares, and what a draft must pass

**2026-09-27.** Three changes to how judge drafts are checked and counted.

**No model call was made.** Every figure below is read from the committed runs of
2026-09-27 and from the code as it now stands. The changes are on two channels:
the vote's referral comparison and a new set of code checks live in
`tribunal/pipeline.py`, and **one sentence** was added to Step 3 of
`prompts/v1/judge.system.md`.

## 1. A referral is compared by the clause it leads with

`referral_clause_references` used to return the **union of every `POL-` string in
the referral's prose**:

```python
found.update(REFERRAL_CLAUSE_RE.findall(item))
```

A referral is free prose, so the vote has always compared clause references
rather than strings. The union counted a clause named *in passing* as part of
the referral, and yesterday's note is what showed the cost: 9111's four drafts
each propose exactly one referral, the same one, led by `POL-RD-09(4)`, and the
vote split them **2-2** because two of the four write "inside the `POL-RD-02`
figure".

It now returns **one value per referral string**: the clause reference that
string leads with, which is the one `judge.system.md` already requires a referral
to lead with ("**Every referral leads with the clause reference that produces
it.**"). The limb stays part of the value, because a referral to the right clause
with the wrong limb is a different referral.

A string that leads with **no** clause reference answers
`NO_LEADING_CLAUSE = "(no leading clause reference)"` rather than contributing
nothing. That is a value, not an absence, so a draft whose referral leads with
nothing can never silently match a draft whose referral leads with a clause.

**The constant's own comment already described this.** `REFERRAL_CLAUSE_RE` has
said since it was written that "the machine-checkable part of it is the clause
reference it leads with". The function did not implement it. This change makes
the code agree with the comment that was already there.

## 2. A draft must pass code checks before it may vote

`check_judge_draft(ruling, brief)` runs before the vote counts a draft, in
`_run_judge_vote`. A draft that fails **any** check becomes an abstention with a
reason code, exactly like an unparseable one, and the quorum is taken over the
drafts that remain. `_reduce_vote` needed no change at all: a draft with no key
was already an abstention, and "fewer than three valid drafts escalates" was
already `agreeing >= threshold and len(valid) >= threshold`.

The checks, in the order they run:

| code | what it checks |
|---|---|
| `DRAFT_RULING_NOT_AN_OBJECT` | `ruling` is a POL-GEN-03 object at all |
| `DRAFT_UNKNOWN_RULING` | the value is one of the five |
| `DRAFT_ESCALATE_WITH_MONEY` | ESCALATE carries both amounts null |
| `DRAFT_AMOUNT_FIELD_ABSENT` | POL-GEN-03's two amount fields are both present |
| `DRAFT_AMOUNT_REQUIRED_MISSING` | the ruling's own required amount is non-null |
| `DRAFT_AMOUNT_DOES_NOT_MIRROR` | on DRIVER_COMPENSATION the two amounts agree |
| `DRAFT_CLAUSE_MALFORMED` | every clause reference matches the strict id form |
| `DRAFT_CLAUSE_UNRESOLVED` | every clause reference resolves in the loaded policy |
| `DRAFT_AMOUNT_NOT_READ_OFF` | each non-null amount is a published figure, or a sum of two or three |

Three points about how these were read, because each one is a decision:

**The clause check reads the referrals and the explanation.** The referrals are
where a ruling states a clause as an instruction and the explanation is where it
states one as a reason. The loose form is found first
(`POL-[A-Za-z]{1,6}-\d+`) so that a *malformed* reference is reported rather than
silently not seen; resolution uses `referee.CLAUSE_ID_RE` and the clause map the
referee's own claim check uses, which is why `referee._policy_clauses` became
public as `referee.policy_clauses`. One consequence is worth stating: a referral
to a clause **outside the case's category** does not resolve, so a no-show draft
that sends a reviewer to `POL-RD-09(4)` abstains. No recorded draft does that
(0 of 176), and the two test fixtures that did have been moved onto their own
case's policy.

**A prose-only governing figure is recorded, not rejected.** Case 109's
`amount_sgd` and `driver_compensation_sgd` are both **3.15**, which is POL-RD-04's
closing limb (`0.75 × 4.16 km = 3.12`, rounded up to the nearest 0.05). POL-RD-04
states that rate and its cap only in prose, so the block computes nothing for it
and publishes no figure to hold the amount against. The draft is recorded as
`"unverifiable: not structured"` and **still votes**.

The exemption is deliberately narrow, and it is compensation-only. It fires only
where the block publishes **no** driver-compensation figure **and** names one in
`not_structured`. A refund is never unverifiable: the calculator computes the
refunds it publishes, and the figures the policy states only in prose around a
refund are the caps and the ceiling that *bound* one, not the refund itself. This
mattered: the first cut keyed the exemption on a "refund" prefix, which excused
**every** unreadable refund on a no-show case, because a no-show block publishes
no figure whose path contains "refund". Four tests caught it, and it is the
reason `unverifiable_amount_reason` takes the ruling value and not the field name.

**The money reading is the answer-key check's.** A figure is a numeric leaf of
the block that is not under `constants` (the policy's own numbers, copied rather
than computed) and is not a named non-money quantity; payables are parsed as
two-place decimal strings; three is the bound on a sum, because a figure needing
four published operands is not a figure the block publishes. One name was added
to the non-money list — `distance_m`, beside the kilometre names — because a
distance in metres is the same class as a kilometre and a fix index is not an
amount at all. It changes no verdict on the recorded drafts (0 amounts), which
was measured both ways before it was kept.

**K = 1 is untouched.** The single-draft path does not call the checks, so a
single-draft run is still byte for byte what it was. The checks are part of the
vote, and a vote of one has no panel to protect.

## 3. The prompt says where amounts come from

One sentence, added to Step 3 of `prompts/v1/judge.system.md`, immediately after
the field list:

> Every amount you state is read off the brief's money block, or given as a stated
> sum of its figures, and `ruling.explanation` names the figures you used.

A draft's money is now checked against the brief's own calculator, so the prompt
has to say where the calculator publishes its figures. Otherwise the judge is
held to a standard it was never told about — the failure mode this repository has
already paid for once, and the reason the sentence is in the prompt rather than
only in the code.

| | before | after |
|---|---|---|
| `prompts/v1/judge.system.md` | `2d8dff12…e273bb` | `73961ae5…db86a9` |
| the `prompts/` directory | `324d5613…eebd80` | `83a74310…a9ac0` |

The change is permitted until 6 October. Nothing else in the prompt moved: the
output contract, Step 1, Step 2 and the referral paragraph are untouched, and the
prompt tests that pin them still pass.

## Does the vote now differ from the grader?

**Yes, in two ways, and they should differ.** The grader's referral comparison is
`eval/grade.py`'s `match_referrals`, which collects **every** clause reference the
produced referrals carry and tests **recall** against the key's, reporting extras
as `additional_clauses` that do not by themselves fail the field. The vote now
compares drafts **to each other**, by the **set of leading references**, exactly.

- **Recall versus equality.** Making the vote recall-based would let two drafts
  that instruct the reviewer to do *different things* count as agreeing: a draft
  proposing only `POL-RD-09(4)` and a draft proposing `POL-RD-09(4)` **and**
  `POL-NS-05(ii)` would "agree" because one set contains the other. A panel that
  disagrees about the subject of a referral has not agreed, and the vote is the
  instrument that says so.
- **Against the key versus against each other.** They answer different questions.
  The grader asks whether the answer is *right*; the vote asks whether the panel
  *agreed*. The grader's own note (2026-09-22) records why an extra clause must
  not fail the field automatically: a model that reaches the expected clause and
  adds another is answering the question about the case. That reasoning is about
  rightness, and it does not transfer to agreement.

So the two now differ, and that is acceptable: each is measuring the thing it is
for. What would not be acceptable is making the grader equality-based, which
would re-break 207 — the case the 2026-09-22 change was made for.

Two smaller differences remain and are harmless: the grader's clause regex has no
limb inline and attaches it separately, and it takes the expected side as setting
the limb's precision, where the vote's value always includes the limb it was
written with.

## The check against the record

Both changes were applied to **every recorded draft of the latest run in both
development sets — 44 cases, 4 drafts each, 176 drafts — with no model call**.
Each draft's own ruling was read out of its transcript entry and put through
`pipeline.check_judge_draft` and the new `pipeline.referral_clause_references`,
and the vote was reduced again the way `_reduce_vote` reduces it.

### How many drafts would now abstain: **none**

**0 of 176 drafts abstain**, and the checks were exercised rather than skipped:

- **the ruling value**: all 176 are one of the five POL-GEN-03 values;
- **the amount fields**: every draft carries both, no ESCALATE carries money, and
  the 29 DRIVER_COMPENSATION drafts all mirror their two amounts;
- **the clause references**: **42** references in the referrals and **2,527** in
  the explanations, across **174 of the 176 drafts** — **0 malformed and 0
  unresolved**;
- **the money**: **148** non-null amounts. **137** read off a single published
  figure, **3** read off as a sum of two, **8** are recorded unverifiable, and
  **0** are unreadable.

The 3 sums are 9113's 9.05, on three drafts:

```
erp_lines.lines[0].amount_sgd.value + closure[0].refund.payable.value
1.00 + 8.05 = 9.05
```

The 8 unverifiable amounts are case 109's four drafts × two fields, both 3.15,
recorded as `"unverifiable: not structured"` and still voting — which is why 109
stays **carried, 4/4, DRIVER_COMPENSATION 3.15** exactly as it was.

### How many referral splits disappear: **3**

| case | union extraction | leading-reference extraction |
|---|---|---|
| 105 | **3/4** — draft 4's prose adds the parent `POL-RD-06` ("against the `POL-RD-06` threshold of 3") | **4/4** — all four lead `POL-RD-06(c)` |
| 207 | **3/4** — draft 4's prose adds `POL-NS-09` ("held under `POL-NS-09` pending that review") | **4/4** — all four lead `POL-NS-07` |
| 9111 | **2/4** — drafts 2, 3 and 4 add `POL-RD-02`; draft 3 also adds the parent `POL-RD-09` | **4/4** — all four lead `POL-RD-09(4)` |

**No other case's agreement moves at all.** 9113 keeps its 3/4, and correctly: its
seed-101 draft proposes **8.05 with no referral** where the other three propose
**9.05 with a `POL-RD-09(4)` referral**. That is a real disagreement about the
money, not an extraction artefact, and the vote still reports it as one.

### Which carried rulings would change: **three, and none of them the grade**

| case | recorded | after both changes |
|---|---|---|
| 105 | `carried_not_unanimous` 0.75 | **`carried` 1.0** — the same FULL_REFUND 65.13 and the same referral |
| 207 | `carried_not_unanimous` 0.75 | **`carried` 1.0** — the same ESCALATE and the same referral |
| 9111 | **`escalated` 0.5** | **`carried` 1.0** — ESCALATE is replaced by PARTIAL_REFUND **9.15** with the `POL-RD-09(4)` referral |

For 105 and 207 the published ruling is otherwise identical: the same amount, the
same referrals, the same confidence; only the sentence the vote appends to the
explanation changes from "carried, not unanimous" to "carried unanimously".

**9111 is the one that moves substantively**, and it still fails. The drafts all
propose **9.15** and the key is **10.15**: they hold that the SGD 1.00
on-optimal-route ERP line is already comprehended in the POL-RD-02 figure rather
than added to it. So the case would go from *escalated* — failing on `ruling`,
`amount_sgd` and `referrals` — to *carried but wrong on the amount* — failing on
`amount_sgd` alone, with `ruling` and `referrals` now matching. A case fails if
any graded field fails, so **9111 still fails, the corpus is still 28/29, the
second set is still 14/15, and the combined figure is still 42/44.** These three
changes cost the benchmark nothing and buy the panel three unanimous rulings
where it previously reported disagreement.

**No case moves from carried to not-carried, and none moves to `no_valid_drafts`.**

### Two test fixtures had to move, and why

Both are consequences of the checks, not of the changes to them:

- `tests/test_pipeline.py`'s `vote_ruling` fixture used an arbitrary **4.35**,
  which case 208's block does not publish and which is not a sum of two or three
  of its figures. Under the new check the fixture would abstain, and every vote
  test would have been measuring the check instead of the vote. It is now **4.0**,
  the POL-NS-03(ii) pin-ambiguity goodwill the block publishes, and a test holds
  the fixture's amount and the block's figures together so the two cannot drift.
- `tests/test_external_case.py`'s scripted ruling was a DRIVER_COMPENSATION with
  `amount_sgd: None` and `driver_compensation_sgd: 4.0`. That violates POL-GEN-03's
  mirror rule, which `validate_ruling_shape` had always **recorded** and never
  acted on; now that a check acts on it, the scripted CLI run produced four
  abstentions and exited 1. It is now 4.0 on both fields, which is also a figure
  case 901's block publishes. This is the change finding a real defect in a
  fixture that had been passing for weeks.

The two referral fixtures that cited `POL-RD-09(4)` on a no-show case were moved
onto that case's own policy, as described above.

## What this makes stale

The brief did not move. The prompt did, so **every cached result is now stale on
the prompt channel**:

| | `stale_brief` | `stale_prompts` | `unknown` |
|---|---|---|---|
| `runs/deepseek-deepseek-flash` | **0** | **29** | 0 |
| `runs/codex/deepseek-deepseek-flash` | **0** | **15** | 0 |

The two channels are not merged, so the record says which one moved: the facts
are the same and the instructions are not. The viewer is unaffected — the page
compares briefs, not prompts, and `ui/dist/index.html` is byte for byte what it
was (`python -m ui.build --check` identical under both interpreters, 69 tests OK).

## Re-running the judge alone

Both are advocate replays: the advocates' recorded claims are reused and only the
judge is called. Add `--force` when the target directory already holds the
results, which it does here.

```
python3 -m eval.run_benchmark --replay-advocates runs/deepseek-deepseek-flash --force
```

```
python3 -m eval.development_sets --set codex --replay-advocates runs/codex/deepseek-deepseek-flash --force
```

Both refuse `--external` and `--compare`, and `--replay-check` reports whether a
replay would accept each case without making a call.

**Neither has been run.** They would cost the owner's balance and they are the
next session's decision, not this one's: the point of this session was to find
out what the changes do to the record *before* spending anything on them.
