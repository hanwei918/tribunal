# The fourth sealed set's single run

**2026-10-11.** The fourth sealed set, `sealed-v2`, was run once, by the owner,
from the commit `19c7e5a`, which is the commit the annotated tag
`freeze-2026-10-11` points at — so the run's `tribunal/`, `prompts/` and
`policy/` trees equal those at the freeze. The output is committed exactly as
produced under `runs/sealed-v2/deepseek-deepseek-flash/` — 29 files, recorded in
`runs/sealed-v2-manifest.json` — with the console log of that one invocation at
`runs/sealed-v2-console.log`. The owner's run made the model calls; none was made
in this repository in committing or reading it. This note reads every figure out
of the committed files and the set's own key.

Nothing in this note changes a ruling, a prompt, a policy, a case file or the
key. It records what the run did and what it got right. The key is frozen from
the moment it was imported, under the standing rule in `START-HERE.md`.

## The run, as the owner made it

The command, run by the owner outside this sandbox, one invocation:

    TRIBUNAL_SEALED_RUN=sealed-v2 python3 -m eval.development_sets --set sealed-v2 --parallel-calls --concurrency 2 --timeout 900

**When.** Started 2026-10-11 16:12:39 SGT and ended 16:26:02 SGT — a Sunday.

**From what.**

| | |
|---|---|
| commit | `19c7e5a3646b2da018dd9bebc9d5f19260773da7` |
| tag | `freeze-2026-10-11` — the annotated tag points at that commit |
| working tree | clean — `run.json` records `working_tree_clean: true` |
| the freeze gate | `git diff --stat freeze-2026-10-11 19c7e5a -- tribunal prompts policy` prints nothing |

**Configuration,** as `run.json` records it:

| setting | value |
|---|---|
| policy version | 6 |
| judge votes | 4 |
| verifier | off |
| precedents | off |
| ablation | off |
| `--parallel-calls` | on |
| `--timeout` | 900 s |
| `--concurrency` | 2 |
| case deadline | 2400 s |
| token budget | none |
| interpreter | 3.11.14 |

**Before the run.** The console log opens with the invocation's own first line,
so no ping and no `--check` reading is recorded for it. The import note's
`--check` — what one plain invocation would run — is how the set was looked at
before the run was made; it prints the closure now, because the run exists.

**Outcome.** All 12 cases produced a ruling, and no case failed — `run.json`
records `failures: []`. Every one of the 72 model calls was answered on its
**first** attempt, with HTTP 200 and a JSON object that parsed, so no draft was
re-asked inside its case and no protocol retry was made. The event chain
verifies. **2,353,450 tokens** were consumed, of which 607,104 were cached and
618,017 of the output was reasoning — summed over the 72 `agent_call` events in
`events.jsonl`, which is the only complete record of the calls. At the owner's
prices that is **0.5900 USD** for the run and **0.0492 USD per case**.

## The figures

From `python3 -m eval.sealed_report --set sealed-v2`:

```
Sealed set sealed-v2 — deepseek/deepseek-flash
Run: runs/sealed-v2/deepseek-deepseek-flash

Four-field exact
  over the 12 cases that produced a ruling: 12/12
  over the 12 cases in the set, a case with no ruling as a miss: 12/12

Ruling alone
  over the 12 cases that produced a ruling: 12/12
  over the 12 cases in the set: 12/12

Per category, from the set's own index.json
  NO_SHOW_CHARGE: 6 in the set, 6 produced; four-field 6/6 over produced and 6/6 over all; ruling 6/6 over produced and 6/6 over all
  ROUTE_DEVIATION: 6 in the set, 6 produced; four-field 6/6 over produced and 6/6 over all; ruling 6/6 over produced and 6/6 over all

Escalation
  over the 12 cases that produced a ruling: 2 produced, 2 expected, 2 true positives; precision 2/2, recall 2/2
  over the 12 cases in the set: 2 produced, 2 expected, 2 true positives; precision 2/2, recall 2/2

No ruling (0)
```

All 12 cases produced a ruling, so the two bases agree here: with no no-ruling
case there is nothing for "over the set" to count as a miss that "over produced"
does not. That is a property of this run and not of the two bases — they came
apart on `wild-v1`, whose two no-ruling cases moved one basis and not the other.

**The four fields separately,** from the set's row in
`python3 -m eval.development_sets --report`:

| field | figure |
|---|---|
| four-field exact | 12/12 |
| ruling | 12/12 |
| amount_sgd | 12/12 |
| driver_compensation_sgd | 12/12 |
| referrals | 12/12 |

A ruling counts only when **all four** fields agree, so the four-field cell and
each field's cell are the same count on this run: every graded field of every
case agrees with the key.

**The figure is reported as an agreement.** It is the rate against the set's one
frozen key and nothing else, and it is not a claim that the key is right — an
agreement is a measurement against one answer. The word is used here and in
`README.md` for that reason, and the figure is never described as an accuracy.

### The interval

Twelve of twelve is a single figure over a very small set, so it is reported with
an interval rather than alone.

| | figure | Wilson 95% interval |
|---|---|---|
| `sealed-v2` (this run) | 12/12 = 100.0% | **0.758 to 1.000** |
| `sealed-v1` (the third sealed set) | 21/24 = 87.5% | **0.690 to 0.957** |
| `wild-v2` (the second sealed set) | 18/20 = 90.0% | **0.699 to 0.972** |
| `wild-v1` (the held-out set) | 55/64 = 85.9% | **0.754 to 0.924** |

The intervals are the Wilson score interval for a binomial proportion at 95%,
computed from the counts by the repository's own function,
`eval.v6_runs.wilson` — the same one the README's sealed blocks and
`tests/test_readme_figures.py` recompute their interval rows with. For 12 of 12
the lower bound is 0.7575, so the interval is **[75.8%, 100.0%]** and no upper
bound is informative: twelve cases cannot distinguish a perfect system from one
that is right three times in four.

**The four are never summed or pooled.** Each is its own generalisation figure,
from its own freeze, over its own set: `sealed-v2`'s over 12 cases from
`freeze-2026-10-11`, `sealed-v1`'s over 24 cases from `freeze-2026-10-09`,
`wild-v2`'s over 20 cases from `freeze-2026-10-03` and `wild-v1`'s over 64 cases
from `freeze-2026-09-30`. One figure over 12 cases plus another over 24 plus a
third over 20 plus a fourth over 64 is not a measurement of 120 cases, and the
intervals above overlap because no one of the four sets is large enough to
separate it from the others. Nothing in the repository adds them.

### The agreement among the four votes

The run is made once, with the frozen configuration — judge votes **4**, the
configuration of the three earlier sealed runs — and the agreement among those
four votes is reported beside the figure because it says how settled each case
was. Over the 12 cases:

| agreement among the four votes | cases |
|---|---|
| 1.00 — all four agreed | 11 |
| 0.75 — three of four (806) | 1 |
| 0.50 — two of four | 0 |
| none — no valid draft | 0 |

Eleven of twelve panels were unanimous. The one that was not is 806, and its
disagreement is about a clause, not about the ruling: draft 1 quoted
`POL-NS-05` and `POL-NS-07`, two no-show clauses that do not resolve in the
loaded policy for a route-deviation case, so the code check
`DRAFT_CLAUSE_UNRESOLVED` voided it, and the other three drafts each proposed
`ESCALATE`, which is the key's ruling. A panel that does not agree is a panel the
case did not settle; here it settled anyway, because the three that were valid
agreed with each other and with the key.

### Per category

From the set's own `index.json`, as the block above prints it:

| category | in the set | four-field exact | ruling alone |
|---|---|---|---|
| `ROUTE_DEVIATION` | 6 | 6/6 | 6/6 |
| `NO_SHOW_CHARGE` | 6 | 6/6 | 6/6 |

## The per-case table

Every case's four graded fields, read from the run's own `report.md`. A ruling
counts only when all four fields agree, so the `exact` column is the four-field
cell.

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact |
|---|---|---|---|---|---|
| 801 | ok | ok | ok | ok | ok |
| 802 | ok | ok | ok | ok | ok |
| 803 | ok | ok | ok | ok | ok |
| 804 | ok | ok | ok | ok | ok |
| 805 | ok | ok | ok | ok | ok |
| 806 | ok | ok | ok | ok | ok |
| 851 | ok | ok | ok | ok | ok |
| 852 | ok | ok | ok | ok | ok |
| 853 | ok | ok | ok | ok | ok |
| 854 | ok | ok | ok | ok | ok |
| 855 | ok | ok | ok | ok | ok |
| 856 | ok | ok | ok | ok | ok |

**The two escalations are the two the key expects.** The key escalates 806 and
856, both `INDETERMINATE`, and the run escalated both — no over-escalation and
no under-escalation. 806 is a route-deviation case whose GPS trace carries a
160-second gap tagged `GPS_GAP` at weight 0.60: `POL-RD-07(iii)` and
`POL-RD-10(3)` require an escalation, and `POL-GEN-02` and `POL-RD-10(1)` bar a
sole-carrier finding at that weight. 856 is a no-show case whose driver profile
shows `no_show_terminations_30d` 5 against `completed_trips_30d` 50 — a rate of
0.10 against `POL-NS-07`'s 0.08 ceiling — so the anti-farming clause and
`POL-NS-09(d)` require an escalation with the payout withheld. 806's escalation
was carried three of four (the abstention above); 856's was unanimous.

**Three cases carry a referral, and each matches the key's clause.** 802 cites
`POL-RD-06(c)` for a material, substantiated deviation with an established repeat
pattern; 803 cites `POL-RD-09(4)` for an airport surcharge applied to a trip that
originated at Bugis; and 856 cites `POL-NS-07` for the anti-farming check. In
each the clause keys the key names and the clause keys the run offered are the
same one.

## Honest limits

- **n = 12.** The interval is wide — 0.758 to 1.000 — and a perfect figure over
  12 cases is consistent with a true agreement anywhere from about 76% upward. A
  single run over 12 cases cannot separate this system from a substantially worse
  one, and 12/12 is the *least* informative kind of perfect score: it is the
  figure most easily produced by a set that is too easy.
- **The set is small, and it was made by the policy owner with GPT-6.** Twelve
  cases, from a written brief, the version-6 policy text and the public contract,
  with no repository code, prompts or run results; nobody on the development side
  has seen its answers. The set was made by the same side that wrote the policy
  it is graded against, which is a real limit on what a figure over it can say,
  and it is stated rather than corrected.
- **The answers were seen by nobody on the development side.** Archive B — the
  key and the files that travel with it — was extracted straight into
  `eval/answers/sealed-v2/` with `unzip` and was never opened: only `unzip -l`
  names and `shasum` digests were used. The key's digest is recorded in
  `docs/notes/2026-10-11-sealed-v2-imported.md`.
- **The set's own manifest records a release gate that is not met.** Its
  `review_status` is `PENDING`, and its first release gate is that the designated
  reviewer, Ji Guofang, "must review and sign all 12 cases against original policy
  text before the sealed run". No sign-off is recorded, and this repository
  cannot tell whether the review happened without being written down. The second
  gate — obtain the exact model name and version from a trustworthy session
  record — is likewise unfulfilled: `model_identity_status` is `UNVERIFIED`, and
  the manifest's `author` names an OpenAI Codex assistant whose exact model
  version its session did not expose. Both are recorded rather than resolved, and
  neither moves a figure: the run was made, and its output is committed exactly
  as produced.
- **The provenance is the registration's sentence, and the set's own files word
  it differently.** The registration says the set was made with GPT-6 by the
  policy owner; archive A's `README.md` and archive B's `MANIFEST.json` each
  state a provenance of their own, which
  `docs/notes/2026-10-11-sealed-v2-imported.md` declines to quote. Whether either
  account held while the set was built is not something this repository can
  answer.

## What this run does not change

- **No ruling in the key changes.** There is no miss to record against it:
  `eval/answers/sealed-v2/ground_truth.json` is frozen from the moment it was
  imported, and it was not touched by this run or by committing it.
- **No code, prompt or policy changes.** `git diff --stat freeze-2026-10-11
  HEAD -- tribunal prompts policy` still prints nothing after this work. Nothing
  in this note edits `tribunal/`, `prompts/` or `policy/`.
- **The set is not development data.** Its cases are not run again, are not
  briefed to a model, and are not read by the policy-gap loop or the precedents
  block. The run is a sealed record, and the root it lives under is closed:
  nothing is created under `runs/sealed-v2/` again, the plain sealed run
  included.
- **The figure is not a repair of anything.** It is a fourth measurement, from a
  fourth freeze, over a fourth set. The defect `sealed-v1`'s 312 exposed — an
  amount the policy computes as a difference is unreadable by the draft check —
  is not touched by it and is not fixed here: fixing it would change the system
  that produced all four figures.

## Where to read it

- **The run:** `runs/sealed-v2/deepseek-deepseek-flash/` — `run.json` for the
  configuration and provenance, `case-*.json` and `case-*.transcript.json` for
  each case, `report.md` for the per-case table.
- **The manifest:** `runs/sealed-v2-manifest.json` — the size and sha256 of every
  one of the 29 files, checked by `tests/test_sealed_v2_run_manifest.py`.
- **The console log:** `runs/sealed-v2-console.log` — the owner's terminal
  output for the one invocation.
- **The figures:** `python3 -m eval.sealed_report --set sealed-v2`, reproduced by
  `tests/test_readme_figures.py`'s sealed-v2 rows.
- **The key:** `eval/answers/sealed-v2/ground_truth.json`, imported on
  2026-10-11 and unchanged since.
- **The freeze:** the annotated tag `freeze-2026-10-11`, which points at the
  commit `19c7e5a` the run was made from. This freeze has no note of its own:
  the import note above records the trees, the command and the configuration,
  and the tag is the owner's record of the trees the run is fixed at.
- **The import:** `docs/notes/2026-10-11-sealed-v2-imported.md` — what the set
  is, where it came from, and the digest of every imported file.
- **The three earlier sealed runs:**
  `docs/notes/2026-09-30-the-sealed-run.md`,
  `docs/notes/2026-10-04-the-second-sealed-run.md` and
  `docs/notes/2026-10-10-the-third-sealed-run.md`.
