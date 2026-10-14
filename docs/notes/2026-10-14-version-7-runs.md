# The version-7 runs, and version 7 told as the result

**2026-10-14.** Ryde released its own **Dispute Resolution Policy v2.1** to the
track on 2026-10-13 at 18:35, and the owner adopted it the same evening as
**policy version 7**: `policy/v7/` holds the three policy files, `prompts/v2/`
holds the prompt set that pairs with them, and the readings version 7 needs
where v2.1 is silent are written down in
[`2026-10-13-policy-v7.md`](2026-10-13-policy-v7.md).

**Version 6 and every run at it are unchanged.** `policy/v1`-`policy/v6` and
`prompts/v1` are byte-identical to what they were, and every version-1-6 brief
still builds byte for byte: the 194 recorded version-6 case digests are rebuilt
and compared by `tests/test_brief_v7.py`, and the corpus, `dev-v2-ext`,
`dev-v2`, `ryde-v3` and the precedents arm all read exactly as they read before
this evening. Nothing in this note moves a version-6 figure.

Six runs were made for version 7, all of them by the owner outside this
sandbox, at `deepseek/deepseek-flash`, four judge votes, the draft verifier off,
a 900-second timeout, concurrency 2, `--parallel-calls` and
`--prompts-dir prompts/v2`, each in a clean worktree detached at the commit
named below with the repository's `.env` copied in. **No model call was made in
this repository.** This session copied the runs in byte for byte, closed the
root the sixth of them closes, and read them; the console logs are committed as
they were written, and the one line in each of them that is wrong is item 2
below.

## 1. Decided without Ryde's replies

Four questions were posted to Ryde in the track group on 2026-10-13 -- the
note's own "Questions for Ryde" section -- and **were not answered before these
runs**. The owner decided to apply v2.1 as written and to take Tribunal's
documented readings where v2.1 is silent. The four are C1, C2, C3 and C5, and
each is recorded with its reasoning in
[`2026-10-13-policy-v7.md`](2026-10-13-policy-v7.md):

- **C1 -- the 2 km limb.** v2.1 6.2 escalates any deviation over 2 km, and
  Ryde's own DISP-001 rules a **4.30 km** deviation itself and expects an AI
  partial refund of 3.44. Tribunal **holds the limb off** and rules the sample
  the way the sample does; the conflict is recorded, and the limb switches on if
  Ryde says so. `sealed-v4`'s key was written that way, so the sixth sealed set
  is a measurement of this reading as much as of the rest of v2.1.
- **C2 -- the free wait starts.** From `trip_record.scheduled_at` where the trip
  is scheduled **and** the driver arrived at or before it; otherwise from the
  driver's arrival. DISP-002 arrives at 08:43, ahead of its 08:45 schedule, so
  the free wait runs from the schedule to 08:50.
- **C3 -- no surge on the excess distance fare.** The excess distance fare is
  deviation km x `fare_breakdown.per_km_rate_sgd`, with no surge multiplier
  (DISP-001: 4.30 x 0.80 = 3.44).
- **C5 -- what "partial" and "full" refund pay.** Both rows pay the **whole**
  excess distance fare; "partial" describes the trip fare, of which only part
  comes back, and "full" describes the excess distance fare. The ruling label is
  `PARTIAL_REFUND` in both.

Correction, 2026-10-14: three were posted -- C1, C2 and C3; C5 was not. Ryde
answered on 2026-10-14: see
[`2026-10-14-policy-v8.md`](2026-10-14-policy-v8.md).

## 2. The one wrong line in every version-7 console log

Every version-7 console log ends its figure with *"cached 30 of 30 results this
code cannot vouch for / prompts moved: ..."* -- 40 of 40 for `dev-v7` and 2 of 2
for `ryde-v7` -- and the development-sets report printed *"sealed-v4 current 0,
stale_brief 0, stale_prompts 30, unknown 0"*.

**Both are a checker error, not a property of the runs.** The currency check
compares each case's recorded prompt digests with a **directory**, and it was
handed `prompts/v1` (`run_benchmark.PROMPTS_DIR`) rather than the directory the
run used. A version-7 run must use `prompts/v2` -- `eval.run_benchmark` refuses
the pair the other way round before a client is built -- so the check compared
every case of three correct runs against a prompt set no call of them was ever
given. The checker now reads the prompts directory the set's own registration
names, and for a set that names none (development data like `ryde-v7`) the one
its policy version pairs with, which is the pairing the runner itself enforces.
Re-checked with `eval.development_sets.currency_for`:

| set | currency |
|---|---|
| `sealed-v4` | 30 current, stale_brief 0, stale_prompts 0, unknown 0 |
| `dev-v7` | 40 current, stale_brief 0, stale_prompts 0, unknown 0 |
| `ryde-v7` | 2 current, stale_brief 0, stale_prompts 0, unknown 0 |

Versions 1-6 are run with `prompts/v1`, so their readings do not move: `codex`
15 current, the corpus 29 current, `wild` 62, `wild-v2` 20, `sealed-v1` 24,
`sealed-v2` 12, `sealed-v3` 8, `wild-dev` 0 -- every one of them as it was.

The runs themselves are unaffected: no case file, transcript, event log or
`run.json` was edited, re-serialised or regenerated, and no figure below changes.

## 3. The six runs

| run | directory | commit | console log |
|---|---|---|---|
| `dev-v7` attempt 1 | `runs/dev-v7-attempt-1/` | `ebcb753` (part 76) | `runs/dev-v7-attempt-1/dev-v7-console.log` |
| `dev-v7` attempt 2, stopped | `runs/dev-v7-attempt-2-stopped/` | `3fd5ef8` (part 79) | `runs/dev-v7-attempt-2-stopped/dev-v7-console.log` |
| `ryde-v7` attempt 1 | `runs/ryde-v7-attempt-1/` | `3fd5ef8` (part 79) | `runs/ryde-v7-attempt-1/ryde-v7-console.log` |
| `dev-v7`, final | `runs/dev-v7/policy-v7/` | `8157af8` (part 79c) | `runs/dev-v7-console.log` |
| `ryde-v7` | `runs/ryde-v7/policy-v7/` | `8157af8` (part 79c) | `runs/ryde-v7-console.log` |
| `sealed-v4` | `runs/sealed-v4/` | `8157af8` = `freeze-2026-10-14` | `runs/sealed-v4-console.log` |

The three attempts are kept as **records, not as figures**: each is the whole of
its own folder, byte for byte, and none of them is a generalisation figure.
`dev-v7` and `ryde-v7` are development data the team tuned against, so no figure
from them is one either. The one figure is `sealed-v4`'s, section 6.

The owner's own `README.txt` is committed unchanged beside them as
`runs/v7-runs-README.txt`, and `runs/sealed-v4-manifest.json` records every file
under `runs/sealed-v4/` with its size and sha256, sorted by path.

On 2026-10-14 the absolute path of the temporary checkout each run was launched
from was replaced by `<checkout>` in the run records; no other byte of a run
changed (docs/notes/2026-10-14-local-paths.md).

## 4. `dev-v7`, the first attempt (2026-10-13 23:45 - 2026-10-14 00:48, `ebcb753`)

**35 of 40.** The report's figure, graded against the set's own key.

The five misses are **one shape**, and it is a shape part 79 was written for: a
**driver-filed** dispute over money the platform had already moved.

| case | category | filed by | already refunded to the rider | the key | what the system ruled |
|---|---|---|---|---|---|
| 5006 | `ROUTE_DEVIATION` | DRIVER | 1.37 (`fare_adjusted`) | `NO_ACTION` | `PARTIAL_REFUND` 1.37 |
| 5016 | `ROUTE_DEVIATION` | DRIVER | 1.68 (`fare_adjusted`) | `NO_ACTION` | `PARTIAL_REFUND` 1.68 |
| 5020 | `ROUTE_DEVIATION` | DRIVER | 1.30 (`fare_adjusted`) | `NO_ACTION` | `ESCALATE` (2-2 split) |
| 5062 | `NO_SHOW_CHARGE` | DRIVER | 5.00 (`fee_reversed`) | `NO_ACTION` | `FULL_REFUND` 5.00 |
| 5063 | `NO_SHOW_CHARGE` | DRIVER | 5.00 (`fee_reversed`) | `NO_ACTION` | `ESCALATE` (2-2 split) |

In each one the facts and the money were right -- the rider is owed exactly the
amount already refunded, and the system computed exactly that -- and the
**ruling word** was wrong. `POL-GEN-03` makes the ruling party-relative: the
driver's claim fails and the present state stands, so the answer is `NO_ACTION`.
The system ruled `PARTIAL_REFUND` / `FULL_REFUND` of the same amount, or split
2-2 between that and `ESCALATE`. Fixed by **part 79** (the filing frame in the
version-7 brief and one paragraph in `prompts/v2`).

Every other case of the set agreed with its key on all four graded fields.

## 5. `dev-v7`, the second attempt and the final run (2026-10-14, `3fd5ef8` then `8157af8`)

**Attempt 2 was stopped by the owner's side after 6 cases**, 4 of them matching.
The two misses were **5001** and **5003**, both rider-filed **route
deviations**: two of the four judge drafts were voided with
`DRAFT_CLAUSE_UNRESOLVED` -- the frame part 79 had added gave a rider filer the
no-show sentence citing `POL-NS-22` on every case, and a route-deviation brief
loads no no-show clause -- so only two valid drafts remained and a majority of
three could not be reached. Fixed by **part 79c** (a category-aware frame, a
referral paragraph per category in `prompts/v2`, and a guard that every clause
id outside `policies` resolves in the brief's own policies). The stopped run is
a record and reports no figure.

**The final run is 40 of 40** (`runs/dev-v7/policy-v7/deepseek-deepseek-flash/`,
2026-10-14 01:31:44 - 02:31:47 SGT, `8157af8`). Every case agrees with its key on
all four graded fields, and no case of it produced no ruling.

**Say it plainly: this is development data the team tuned against.** Three
attempts and two fixes sit between the first figure and this one, the set's
author is the same model that helped write the version-7 policy files, and the
team reads it. 40 of 40 here is what a development set looks like after it has
been tuned against; it is not a generalisation figure, and it is never pooled
with a sealed set's.

## 6. `ryde-v7`, the organisers' two samples (2026-10-14 01:3x - 01:43:20, `8157af8`)

Ryde's own stated outcomes are this set's key, so each sample is scored against
the answer Ryde gave rather than against a reading of the policy.

| case | sample | Ryde's stated outcome | what the system ruled | |
|---|---|---|---|---|
| 902 | DISP-001, route deviation | `PARTIAL_REFUND` 3.44 | `PARTIAL_REFUND` 3.44, confidence 0.85, unanimous 4 of 4 | **match** |
| 903 | DISP-002, no-show | `DRIVER_COMPENSATION` 5.00, the fee upheld | `ESCALATE` -- the panel split 2-2 | **miss** |

**902 is the sample the version-7 readings were checked against**, and it is
carried: the 4.30 km deviation from the recorded distances, the PIE vehicle fire
and the congestion both justifying the reroute, the rider not informed, POL-RD-24
row (b), the excess distance fare 4.30 x 0.80 = 3.44 with no surge (C3), and the
2 km limb held off (C1). The first run of it had every one of those facts right
and escalated at confidence 0.75, below POL-RD-25's 0.80: the 0.75 was the fare
record's weight, because the converter had marked Ryde's fare breakdown a
`PARTIAL_RECORD` for not itemising base, time and platform-fee lines. Version 7
reads only the per-kilometre rate and the excess figures, and the record states
both, so that gap is a difference of format rather than an impairment. **Part
79b** is that change; the GPS records keep their codes, and 902's escalation
went away without the money moving.

**903 is reported as a known divergence, and it is not a defect.** The key is
`DRIVER_COMPENSATION` 5.00 -- the fee upheld. The system escalated: two drafts
proposed `DRIVER_COMPENSATION` 5.00 and two proposed `ESCALATE`, three of four
were needed, so no ruling was carried. The reason the two escalated is the
policy working as written: the rider's profile carries a fraud flag, so
POL-GEN-22 raises the bar to 0.95, and the arrival rests on eight GPS fixes two
to four minutes apart -- which cannot carry 0.95. That is the system declining
to rule on evidence it does not have, and the case goes to a person with the fee
held.

The first attempt at this set escalated both samples, at 0.75 and 0.6; it is
kept as `runs/ryde-v7-attempt-1/` and reports no figure.

## 7. `sealed-v4`, the sixth sealed set

**The command**, run once by the owner:

```
TRIBUNAL_SEALED_RUN=sealed-v4 python3 -m eval.development_sets --set sealed-v4 --parallel-calls --concurrency 2 --timeout 900 --prompts-dir prompts/v2
```

| | |
|---|---|
| started | 2026-10-14 02:32:37 SGT |
| ended | 2026-10-14 03:14:51 SGT |
| commit | `8157af8`, the commit the annotated tag **`freeze-2026-10-14`** points at |
| worktree | clean, detached at the tag |
| prompts | `prompts/v2`, directory digest `22632cd34844…` |
| cases | 30 completed, 0 cached, 0 failed |
| nobody on the development side read its answers before this run | |

The tag's own message: *"Freeze 5: tribunal/, prompts/ and policy/ at policy
version 7 (Ryde Dispute Resolution Policy v2.1) final; sealed-v4 runs once from
here"*.

### The four-field agreement

| | |
|---|---|
| four-field exact, all 30 cases | **30/30** |
| Wilson 95% interval (`eval.v6_runs.wilson`) | **[88.6%, 100.0%]** |
| `ruling` | 30/30 |
| `amount_sgd` | 30/30 |
| `driver_compensation_sgd` | 30/30 |
| `referrals` | 30/30 |
| ruling alone | 30/30 |
| route deviations (6001-6015) | 15/15 |
| no-show charges (6051-6065) | 15/15 |

### Escalation, cost and time

| | |
|---|---|
| escalation | 9 produced, 9 expected, 9 true positives -- precision **9/9**, recall **9/9** |
| wall clock | median **139.8 s**, 90th percentile **262.5 s** |
| tokens | 4,657,643 billed (2,719,854 in, of which 1,127,674 cached; 1,937,789 out) |
| cost at the repository's prices (`eval/v6_runs.py`) | median **0.0398 USD** a case, **1.40 USD** for the set |

### The per-case table

Every case agrees on all four graded fields. Amounts are as the run recorded
them; `--` is a null field.

| case | category | the key | what the run ruled |
|---|---|---|---|
| 6001 | `ROUTE_DEVIATION` | `PARTIAL_REFUND` 1.10 | `PARTIAL_REFUND` 1.10 |
| 6002 | `ROUTE_DEVIATION` | `NO_ACTION` | `NO_ACTION` |
| 6003 | `ROUTE_DEVIATION` | `NO_ACTION` | `NO_ACTION` |
| 6004 | `ROUTE_DEVIATION` | `PARTIAL_REFUND` 1.22 | `PARTIAL_REFUND` 1.22 |
| 6005 | `ROUTE_DEVIATION` | `NO_ACTION` | `NO_ACTION` |
| 6006 | `ROUTE_DEVIATION` | `PARTIAL_REFUND` 1.15 | `PARTIAL_REFUND` 1.15 |
| 6007 | `ROUTE_DEVIATION` | `ESCALATE` | `ESCALATE` |
| 6008 | `ROUTE_DEVIATION` | `ESCALATE` | `ESCALATE` |
| 6009 | `ROUTE_DEVIATION` | `PARTIAL_REFUND` 2.21 | `PARTIAL_REFUND` 2.21 |
| 6010 | `ROUTE_DEVIATION` | `ESCALATE` | `ESCALATE` |
| 6011 | `ROUTE_DEVIATION` | `ESCALATE` | `ESCALATE` |
| 6012 | `ROUTE_DEVIATION` | `ESCALATE` | `ESCALATE` |
| 6013 | `ROUTE_DEVIATION` | `PARTIAL_REFUND` 0.79 | `PARTIAL_REFUND` 0.79 |
| 6014 | `ROUTE_DEVIATION` | `NO_ACTION` | `NO_ACTION` |
| 6015 | `ROUTE_DEVIATION` | `NO_ACTION` | `NO_ACTION` |
| 6051 | `NO_SHOW_CHARGE` | `DRIVER_COMPENSATION` 5.00 | `DRIVER_COMPENSATION` 5.00 |
| 6052 | `NO_SHOW_CHARGE` | `FULL_REFUND` 5.00 | `FULL_REFUND` 5.00 |
| 6053 | `NO_SHOW_CHARGE` | `FULL_REFUND` 5.00 | `FULL_REFUND` 5.00 |
| 6054 | `NO_SHOW_CHARGE` | `NO_ACTION` | `NO_ACTION` |
| 6055 | `NO_SHOW_CHARGE` | `FULL_REFUND` 5.00 | `FULL_REFUND` 5.00 |
| 6056 | `NO_SHOW_CHARGE` | `FULL_REFUND` 5.00 | `FULL_REFUND` 5.00 |
| 6057 | `NO_SHOW_CHARGE` | `DRIVER_COMPENSATION` 5.00 | `DRIVER_COMPENSATION` 5.00 |
| 6058 | `NO_SHOW_CHARGE` | `DRIVER_COMPENSATION` 5.00 | `DRIVER_COMPENSATION` 5.00 |
| 6059 | `NO_SHOW_CHARGE` | `FULL_REFUND` 4.00 | `FULL_REFUND` 4.00 |
| 6060 | `NO_SHOW_CHARGE` | `DRIVER_COMPENSATION` 5.00 | `DRIVER_COMPENSATION` 5.00 |
| 6061 | `NO_SHOW_CHARGE` | `ESCALATE` | `ESCALATE` |
| 6062 | `NO_SHOW_CHARGE` | `ESCALATE` | `ESCALATE` |
| 6063 | `NO_SHOW_CHARGE` | `ESCALATE` | `ESCALATE` |
| 6064 | `NO_SHOW_CHARGE` | `FULL_REFUND` 5.00 | `FULL_REFUND` 5.00 |
| 6065 | `NO_SHOW_CHARGE` | `ESCALATE` | `ESCALATE` |

`driver_compensation_sgd` is 5.00 on the four `DRIVER_COMPENSATION` cases
(6051, 6057, 6058, 6060) and null on the other 26. Three cases carry a referral
and agree with the key on it -- 6056 (`POL-NS-24`, the 5.00 goodwill credit),
6058 (`POL-NS-25`, the rider's repeat no-shows) and 6059 (`POL-NS-22`, the
record's 4.00 fee against the policy's 5.00) -- and the nine escalations carry
no amount and no referral, as an escalation does.

### Provenance, and what 30 of 30 does and does not show

The set was written by **Claude Opus 5.5 in a fresh claude.ai chat with no
project folder and no repository access**, from the owner's prompt, Ryde's
Dispute Resolution Policy v2.1, the three version-7 policy files,
`data/PUBLIC-CONTRACT.md`, a format checker and the organisers' public sample
case. It was imported unread on 2026-10-13 and nobody on the development side
read its answers before this run. **That model is the team's own development
assistant, and it helped write the version-7 policy files; the key was not
reviewed by a person.**

So, plainly: **30 of 30 says that the system applies the version-7 files as that
author reads them.** It is **not** an independent benchmark -- the author is
inside the team's tooling, and the reading it encodes is the reading the policy
files were written with. And **30 cases is a small sample**: the Wilson 95%
lower bound on 30 of 30 is **88.6%**, so the figure is consistent with anything
from 88.6% up, and a single case would move it by 3.3 points. What it does show
is that on a set the system was not tuned against, written for Ryde's own policy
by the same model that wrote the policy files, the system agreed with every one
of the 30 keys on all four graded fields -- including the nine escalations the
author expected.

## 8. What was closed

`runs/sealed-v4/` is now the sixth sealed root whose single run has been made,
so it is **closed outright** like the other five: no plain run, no `--force`, no
ablated run, no run at a later policy version and no report is created under it
again, and `run_benchmark.UNRUN_SEALED_RUNS_SUBDIRS` is empty -- no root accepts
even the guarded plain run any more. The set's own summary, the guard's refusal
for its root and the sealed-root helper's docstring all say so, and
`python3 -m eval.sealed_report --set sealed-v4` now prints its figures rather
than "has not been run".

Nothing under `tribunal/`, `prompts/` or `policy/` changed in committing any of
this: `git diff --stat freeze-2026-10-14 HEAD -- tribunal prompts policy` prints
nothing.
