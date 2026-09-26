# The voting run

**2026-09-26.** The judge now drafts its ruling four times and the majority
decides (the vote landed in `10bd023`). This note records the run that measured
that change, exactly as produced. Nothing was re-run to write this up: every
figure is read out of `runs/`, the invocation history and git, and no model
call was made in this session.

## What ran

Judge-only replay, `--replay-advocates … --force`, at commit `c922ed2`, on the
owner's balance, on judge digest `324d5613…`. Four drafts per case: three
sampled at temperature 0.7 with seeds 101, 202 and 303, and one
position-swapped draft run at the client's own settings (temperature 0.0, seed
42).

| attempt | started (SGT) | asked | outcome |
|---|---|---|---|
| smoke | 15:44 | corpus 208 | 1 of 1 completed |
| 1 | 15:46 | corpus, the other 28 | 28 of 28 completed |
| 2 | 17:48 | second set 9101–9115 | 15 of 15 completed |

`--force` is required because each target directory already held the
single-draft results; without it the cached case is reused instead of replayed.

## Result

| set | exact | failing |
|---|---:|---|
| corpus | **28/29** | 211 (`ruling`, `amount_sgd`) |
| second set | **14/15** | 9111 (`amount_sgd`, `referrals`) |
| **combined** | **42/44** | |

This is the **same four-field grade as the single-draft referee run** recorded
in `docs/notes/2026-09-25-the-referee-prompt-run.md` — the same two cases miss,
on the same fields. The vote changed how the answer is reached, not what it is.

All 44 results are current on both channels: `stale_brief = ()`,
`stale_prompts = ()` and `unknown = ()` for both sets, and every record's own
`prompts_sha256` is `324d5613…` at `c922ed2a`.

## The agreement distribution

| agreement | cases | set |
|---|---|---|
| **4 of 4 (unanimous)** | **40 of 44** | corpus 26, second set 14 |
| 3 of 4 | 3 | 107, 207 (corpus); 9111 (second set) |
| 2 of 4 | 1 | 211 (corpus) |

The three at 3 of 4 carry, and are marked *carried, not unanimous*; the one at
2 of 4 has no majority and escalates. So of 44 cases the vote had to work for
four of them, and on the other forty every draft agreed.

## The four cases that were not unanimous

The vote is on the four graded fields **together** — ruling, `amount_sgd`,
`driver_compensation_sgd` and the set of referral clause references — so a
draft that agrees on the ruling but differs on a referral has not agreed.

### 107 — carried, not unanimous (3 of 4)

| draft | kind | seed | temp | proposal | verdict |
|---|---|---|---|---|---|
| 1 | sampled | 101 | 0.7 | `ESCALATE` | **dissented** |
| 2 | sampled | 202 | 0.7 | `PARTIAL_REFUND 7.45` | agreed |
| 3 | sampled | 303 | 0.7 | `PARTIAL_REFUND 7.45` | agreed |
| 4 | position-swapped | 42 | 0.0 | `PARTIAL_REFUND 7.45` | agreed |

**One sampled draft proposed `ESCALATE` and was outvoted.** This is the flip
seen across earlier prompt versions — 107 has read both ways between runs whose
prompts differed in ways unrelated to it — now **contained by the vote**: the
same instability is still visible in the drafts, but it no longer decides the
case, because three drafts held the key's answer and one did not. The ruling
published is the majority's, and its explanation says the vote was 3 of 4.

### 207 — carried, not unanimous (3 of 4)

| draft | kind | seed | temp | proposal | verdict |
|---|---|---|---|---|---|
| 1 | sampled | 101 | 0.7 | `ESCALATE`, referrals `[POL-NS-07]` | agreed |
| 2 | sampled | 202 | 0.7 | `ESCALATE`, referrals `[POL-NS-07]` | agreed |
| 3 | sampled | 303 | 0.7 | `ESCALATE`, referrals `[POL-NS-07]` | agreed |
| 4 | position-swapped | 42 | 0.0 | `ESCALATE`, referrals `[POL-NS-07, POL-NS-09(d)]` | **dissented** |

The four drafts agree on the ruling, both money fields (both `null`) and the
`POL-NS-07` referral; the dissent is a **second referral**, `POL-NS-09(d)`,
added by the position-swapped draft. Under the four-fields-together rule that
is a difference, and 207 is recorded as carried on 3 of 4. The published ruling
carries the majority's single referral.

### 211 — no majority, escalated (2 of 4)

| draft | kind | seed | temp | proposal | verdict |
|---|---|---|---|---|---|
| 1 | sampled | 101 | 0.7 | `PARTIAL_REFUND 2.00` | agreed |
| 2 | sampled | 202 | 0.7 | `PARTIAL_REFUND 2.00` | agreed |
| 3 | sampled | 303 | 0.7 | `ESCALATE` | **dissented** |
| 4 | position-swapped | 42 | 0.0 | `DRIVER_COMPENSATION 3.20` | **dissented** |

**Two drafts proposed the key's own answer (`PARTIAL_REFUND 2.00`), one
proposed `ESCALATE`, and the position-swapped draft proposed
`DRIVER_COMPENSATION 3.20`.** There was no majority, so the ruling is
`ESCALATE` with both money fields `null`: **the system declined to pick when its
own drafts disagreed, and the dangerous proposal did not carry.** The
`DRIVER_COMPENSATION 3.20` draft — the reading that pays the driver out on an
undecided limb, the direction recorded as this system's first known limitation
— was one of four and published nothing. The published explanation names all
four proposals.

### 9111 — carried, not unanimous (3 of 4)

| draft | kind | seed | temp | proposal | verdict |
|---|---|---|---|---|---|
| 1 | sampled | 101 | 0.7 | `PARTIAL_REFUND 9.15` | agreed |
| 2 | sampled | 202 | 0.7 | `PARTIAL_REFUND 9.15` | agreed |
| 3 | sampled | 303 | 0.7 | `PARTIAL_REFUND 9.15` | agreed |
| 4 | position-swapped | 42 | 0.0 | `PARTIAL_REFUND 9.15`, referrals `[POL-RD-02, POL-RD-09(4)]` | **dissented** |

The four agree on the ruling and the amount; the dissent is the referral set.
The case still misses the key on `amount_sgd` (9.15 against the corrected
10.15) and on `referrals`, and the vote did not change that — the majority
carried the same answer the single draft gave.

## The position-swapped draft, stated carefully

The position-swapped draft was the dissenter in **three of the four**
non-unanimous cases (207, 211, 9111). It was **not** the dissenter in 107,
where a sampled draft dissented.

This run **cannot** say that presenting the two sides in the opposite order
caused those dissents, and this note does not claim a position bias. The
position-swapped draft differs from the sampled drafts in **two** ways at once:

- the two sides' kept claims are presented in the opposite order; and
- it runs at the **client's own settings** (temperature 0.0, seed 42) where the
  sampled drafts run at temperature 0.7 with seeds 101/202/303 — so it is not
  sampled at all.

A difference in the answer is therefore confounded between order and sampling,
and four cases cannot separate them. Telling the two apart needs a run that
varies one of them while holding the other fixed, which this one does not.

## Cost

Charged to **the owner's balance**: **5,812,530 tokens** across the three
invocations —

| invocation | cases | charged |
|---|---:|---:|
| 15:44 corpus smoke (208) | 1 | 99,860 |
| 15:46 corpus (the other 28) | 28 | 3,968,825 |
| 17:48 second set (9101–9115) | 15 | 1,743,845 |
| **total** | **44** | **5,812,530** |

**Each case now costs about four judge calls**, so about four times the
single-draft run's 1,408,309 tokens: 5,812,530 / 1,408,309 = **4.13×**. The
figure is a little over 4× rather than exactly 4× because the four drafts share
one prompt and one brief, so a large part of the input is served from the
provider's cache — the three invocations record 2,391,673 cached tokens in
total (53,120 + 1,554,431 + 784,122).

The replayed advocates' own tokens — 57,766 + 1,676,061 + 871,792 =
**2,605,619** — were billed to the earlier run that produced them and are
recorded as `billed_to_another_run`; they are not part of the figure above. The
total is identical to the previous session's borrowed figure, because the
advocates are the same calls replayed.

## Provenance gap: the run record does not say how many drafts

The invocation history records the commit, the prompts digest, the model, the
replay source and the tokens, but **not the number of judge drafts**. Neither
`run.json` nor `invocations.json` carries a `judge_votes` field, so a reader of
the record alone cannot tell this run's four-draft result from a single-draft
one; only the `vote` block inside each transcript does. This is reported and
**not** fixed here — the run is committed exactly as produced, and the runner
was not changed in this session.

## The viewer

The vote is invisible in a result object: a unanimous ruling and one that
carried 3 of 4 are the same shape. So the viewer was extended to show it, from
the run's own records and from nothing else.

**The judge step of one case** now ends with *How the judge's drafts voted* —
one box per draft giving its kind (`sampled` or `position-swapped`), its seed
and temperature, the four graded fields it proposed, and whether it `agreed`,
`dissented` or `abstained`; then the vote result, naming the outcome
(`carried`, `carried_not_unanimous` or `escalated`), the agreeing count, the
`vote_agreement`, and whether the vote was unanimous.

**The overview** gains a `Vote` column on the all-cases grid, giving each case
its agreeing count and, where the vote was not unanimous, the outcome as a
`contested` badge; a *Where the judge's drafts disagreed* table above the grid,
listing the non-unanimous cases with the drafts that did not agree and the whole
four-field proposal each of them made; and a **Contested only** toggle on the
grid that narrows it to those cases.

The dissent line names all four graded fields rather than the ruling alone,
because on this run 207's four drafts all proposed `ESCALATE` and still
disagreed — on a referral. A line showing only the ruling would have called that
vote unanimous.

Three things are deliberate:

- **The page derives no vote.** Each draft's verdict is read from the run's own
  `valid` and `agrees` booleans; the outcome, the agreement and the unanimous
  flag are the run's own fields. A page that recomputed the vote could agree
  with itself while disagreeing with the run, and the two would then be
  indistinguishable from the page alone.
- **The filter is view state, not part of the link.** It stays out of the hash,
  so a shared link opens the same run and whoever follows it decides for
  themselves whether to narrow the grid.
- **The colours are keyed by the outcome string itself**
  (`.vote-result.carried`, `.vote-result.carried_not_unanimous`,
  `.vote-result.escalated`), and a test pins those three against
  `pipeline.VOTE_CARRIED`, `pipeline.VOTE_CARRIED_NOT_UNANIMOUS` and
  `pipeline.VOTE_ESCALATED`, so the stylesheet cannot drift away from the words
  the pipeline can emit.

**How it was checked.** The committed page is verified from
`tests/test_ui_build.py`'s `JudgeVoteTests`, which read the vote out of
`runs/deepseek-deepseek-flash/case-NNNNN.transcript.json` and require the page's
document to carry exactly that, draft by draft, and from a static read of the
built `ui/dist/index.html` — its script, its data block and its stylesheet —
with `python -m ui.build --check` confirming the committed bytes equal a fresh
build. Ten tests were added. On this run the vote reaches the page for all 29
corpus cases, and the three contested ones are 107, 207 and 211.

One rendering was also opened once in a headless browser during the session,
before the check was narrowed to the built page and the tests; it drew case
211's four drafts and its `escalated` result as recorded above. No browser is
part of the verification the repository relies on.
