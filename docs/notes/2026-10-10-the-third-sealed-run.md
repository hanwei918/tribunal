# The third sealed set's single run

**2026-10-10.** The third sealed set, `sealed-v1`, was run once, by the owner,
from the commit `feb7174`, whose `tribunal/`, `prompts/` and `policy/` trees
equal those at the freeze tagged `freeze-2026-10-09`. The output is committed
exactly as produced under `runs/sealed-v1/deepseek-deepseek-flash/` — 53 files,
recorded in `runs/sealed-v1-manifest.json` — with the console log of that one
invocation at `runs/sealed-v1-console.log`. The owner's run made the model calls;
none was made in this repository in committing or reading it. This note reads
every figure out of the committed files and the set's own key.

Nothing in this note changes a ruling, a prompt, a policy, a case file or the
key. It records what the run did, what it missed, and why. The key is frozen
from the moment it was imported, under the standing rule in `START-HERE.md`.

## The run, as the owner made it

The command, run by the owner outside this sandbox, one invocation:

    TRIBUNAL_SEALED_RUN=sealed-v1 python3 -m eval.development_sets --set sealed-v1 --parallel-calls --concurrency 2 --timeout 900

**When.** Started 2026-10-10 11:36:27 SGT and ended 12:21:38 SGT — a Saturday.

**From what.**

| | |
|---|---|
| commit | `feb71748c9f1c68c39c368b45e53151efdd03255` |
| working tree | clean — `run.json` records `working_tree_clean: true` |
| the freeze gate | `git diff --stat freeze-2026-10-09 feb7174 -- tribunal prompts policy` prints nothing |

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

**Outcome.** All 24 cases produced a ruling, and no case failed — `run.json`
records `failures: []`. Four judge answers were unusable and were re-asked inside
their own case by the pipeline's one in-call retry, which is not a protocol
retry: 304 once (draft 2), 403 twice (drafts 2 and 3) and 404 once (draft 3) —
four re-asks in all. 304's retry did not parse either, so that draft abstained;
the other three re-asks were answered. No protocol retry was made, so the
protocol's retry rules did not come into play. The event chain verifies.
**6,168,949 tokens** were consumed, of which 1,410,808 were cached and 2,550,932
of the output was reasoning — summed over the 148 `agent_call` events in
`events.jsonl`, which is the only complete record of the calls.

## The figures

From `python3 -m eval.sealed_report --set sealed-v1`:

```
Sealed set sealed-v1 — deepseek/deepseek-flash
Run: runs/sealed-v1/deepseek-deepseek-flash

Four-field exact
  over the 24 cases that produced a ruling: 21/24
  over the 24 cases in the set, a case with no ruling as a miss: 21/24

Ruling alone
  over the 24 cases that produced a ruling: 21/24
  over the 24 cases in the set: 21/24

Per category, from the set's own index.json
  NO_SHOW_CHARGE: 12 in the set, 12 produced; four-field 11/12 over produced and 11/12 over all; ruling 11/12 over produced and 11/12 over all
  ROUTE_DEVIATION: 12 in the set, 12 produced; four-field 10/12 over produced and 10/12 over all; ruling 10/12 over produced and 10/12 over all

Escalation
  over the 24 cases that produced a ruling: 5 produced, 4 expected, 3 true positives; precision 3/5, recall 3/4
  over the 24 cases in the set: 5 produced, 4 expected, 3 true positives; precision 3/5, recall 3/4

No ruling (0)
```

All 24 cases produced a ruling, so the two bases agree here: with no no-ruling
case there is nothing for "over the set" to count as a miss that "over produced"
does not. That is a property of this run and not of the two bases — they came
apart on `wild-v1`, whose two no-ruling cases moved one basis and not the other.

**The four fields separately,** from the set's row in
`python3 -m eval.development_sets --report`:

| field | figure |
|---|---|
| four-field exact | 21/24 |
| ruling | 21/24 |
| amount_sgd | 21/24 |
| driver_compensation_sgd | 24/24 |
| referrals | 23/24 |

A ruling counts only when **all four** fields agree, so the three misses below
are the three cases whose four-field cell is a miss: 304 and 312 fail on the
ruling and the amount together, and 410 fails on the ruling, the amount and the
referral.

**The set's protocol asks for agreement, not accuracy.** Its README says to
report the rate against its key as an **agreement** rate — its word for it, and
not an "accuracy" — and to split it by the four fields; that is what the block
above does. This is not a distinction without a difference: an agreement is a
measurement against one frozen key, and it is not a claim that the key is right.

### The interval

Twenty-one of twenty-four is a single figure over a small set, so it is reported
with an interval rather than alone.

| | figure | Wilson 95% interval |
|---|---|---|
| `sealed-v1` (this run) | 21/24 = 87.5% | **0.690 to 0.957** |
| `wild-v2` (the second sealed set) | 18/20 = 90.0% | **0.699 to 0.972** |
| `wild-v1` (the held-out set) | 55/64 = 85.9% | **0.754 to 0.924** |

The intervals are the Wilson score interval for a binomial proportion at 95%,
computed from the counts by code in `tests/test_third_sealed_run_note.py`, which
reads the three figures out of the committed runs and recomputes all three
intervals — **no bound above is typed into the test**.

**The three are never summed or pooled.** Each is its own generalisation figure,
from its own freeze, over its own set: `sealed-v1`'s over 24 cases from
`freeze-2026-10-09`, `wild-v2`'s over 20 cases from `freeze-2026-10-03` and
`wild-v1`'s over 64 cases from `freeze-2026-09-30`. One figure over 24 cases plus
another over 20 plus a third over 64 is not a measurement of 108 cases, and the
intervals above overlap precisely because no one of the three sets is large
enough to separate it from the others. Nothing in the repository adds them.

### k-consistency

The set's README asks for the run to report k-consistency and says the run is
made with k equal to 3, but **it does not define k**, and its own manifest
records `k` 3 beside `runs_allowed` 1. The run is therefore made once, with the
frozen configuration — judge votes **4**, the configuration of the two earlier
sealed runs — and not three times, and k-consistency is read as the agreement
among those four votes. Over the 24 cases:

| agreement among the four votes | cases |
|---|---|
| 1.00 — all four agreed | 21 |
| 0.75 — three of four (311) | 1 |
| 0.50 — two of four (304) | 1 |
| none — no valid draft (312) | 1 |

Twenty-one of twenty-four panels were unanimous. The three that were not are
exactly the three cases the run does not get right, which is not a coincidence:
a panel that does not agree is a panel the case did not settle.

### Per category

From the set's own `index.json`, as the block above prints it:

| category | in the set | four-field exact | ruling alone |
|---|---|---|---|
| `NO_SHOW_CHARGE` | 12 | 11/12 | 11/12 |
| `ROUTE_DEVIATION` | 12 | 10/12 | 10/12 |

The route-deviation half is where the two hard cases live: 304 is a split panel
and 312 is the read-off case read below. The no-show half loses one case, 410, to
a missed escalation trigger.

## The three misses

Each is given with the key against the produced ruling, the vote, and a cause
read off the vote block. The causes are the ones
`docs/notes/2026-10-10-what-went-wrong-at-version-6.md` uses for the version-6
development misses: **split**, **no valid draft**, **missed trigger** and
**other**.

### 304 — a split panel, and an over-escalation

**Key:** `PARTIAL_REFUND` 1.00. **Produced:** `ESCALATE`, no money.

304 is a route-deviation case whose deviation is exonerated under `POL-RD-03`
but which still refunds one off-route ERP line under `POL-RD-09(2)`: the trace
is 28.90 km against an amended optimal of 24.0 km, the excess is 4.90 km and
20.4%, and a complete `LTA_DATAMALL` closure covers the PIE segment, so the
cap absorbs the whole excess and nothing is due on distance or time. The one
`ECP` gantry on `EV-FARE-00304`, 1.00, is `on_optimal_route: false` and is
refunded standalone. The key's own rationale names the shape: a judge that runs
`POL-RD-02` over-refunds; one that stops at exoneration under-refunds.

The vote did not carry:

| draft | kind | proposed | abstention |
|---|---|---|---|
| 1 | sampled | `PARTIAL_REFUND` 2.40 | — |
| 2 | sampled | — | `the judge did not return a JSON object` |
| 3 | sampled | `PARTIAL_REFUND` 2.40 | — |
| 4 | position-swapped | `PARTIAL_REFUND` 1.00 | — |

**The cause is a split.** Two valid drafts proposed 2.40 and one proposed 1.00,
with one draft abstaining and the threshold at 3, so `agreement` is 0.50 and no
proposal reached it. Draft 4 is the position-swapped one and it is the draft
that got the key's figure: it read `EV-FARE-00304`'s `fare_model METERED` and
refunded the ERP line alone. Drafts 1 and 3 ran `POL-RD-02` over the exonerated
deviation and arrived at 2.40. The panel split on the same question the key's
rationale warns about, and the case escalated because of it.

### 312 — no valid draft, and the read-off rule refusing the key's own figure

**Key:** `PARTIAL_REFUND` 4.10. **Produced:** `ESCALATE`, no money.

312 is a route-deviation case on amended endpoints: `dropoff_amended_at` is
non-null and `amended_optimal_distance_km` is 14.0 km, so `POL-RD-05` re-applies
`POL-RD-01` against the amended endpoints. The trace is 17.57 km, an excess of
3.57 km and 25.5%, established and not material; the rider's 60-day profile
shows 5 deviation claims with 0 substantiated, and `POL-RD-08` raises the bar for
an excess below 30% — which the driver's own chat admission of missing the
Braddell exit satisfies. The recomputed fare is 20.420 against a
`charged_total` of 24.52, and the refund is 24.52 less 20.420 = 4.10.

Every draft agreed with the key:

| draft | kind | proposed | abstention |
|---|---|---|---|
| 1 | sampled | `amount_sgd` 4.10 | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 2 | sampled | `amount_sgd` 4.1 | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 3 | sampled | `amount_sgd` 4.10 | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 4 | position-swapped | `amount_sgd` 4.1 | `DRAFT_AMOUNT_NOT_READ_OFF` |

**The cause is no valid draft.** All four drafts proposed the key's own 4.10 and
all four were rejected by the draft check, with `outcome: no_valid_drafts` and
no `agreement` at all — a vote with nothing valid in it publishes an `ESCALATE`
with confidence 0 and the reason code, naming each draft's abstention, rather
than ending the case as a failure.

**This is the held-out run's shape, met again.** The read-off rule accepts a
figure the brief's money block publishes, or the **sum** of two or three of them,
and never a **difference** — and 4.10 is `charged_total − recomputed fare`, a
difference by construction. The held-out run's two no-ruling cases, 517 and 533,
were rejected for exactly this reason. This is a real defect in the draft check
and it is deliberately **not** fixed here: fixing it would change the system that
produced this figure, so the repair belongs to a later version, measured on a
fresh sealed set.

### 410 — a missed trigger, the dangerous kind

**Key:** `ESCALATE`, no money, difficulty `INDETERMINATE`, under `POL-NS-09(b)`.
**Produced:** `FULL_REFUND` 4.00 with a `POL-NS-05(ii)` referral, confidence 0.9.

This is the miss to read carefully, because it goes the other way: the system
decided confidently a case the key says is not decidable. It is the one
under-escalation in the run.

The record contradicts itself directly. `EV-TRIP-00410` records `arrived_at`
09:10:00 and `cancelled_at` 09:16:30 — a 6.5-minute dwell at the pin — and the
trip record is tagged `CROSS_SOURCE_CONFLICT` at weight 0.40. `EV-GPS-00410` is
`COMPLETE` at weight 1.0 with 5–11 m accuracy and places the driver stationary
about 850 m from the pin for that entire interval: outside the 50 m radius,
outside 300 m (so not `POL-NS-05`'s false-marker case, which concerns a moving
driver) and outside 400 m (so not `POL-NS-03`'s wrong-entrance case). Two
admissible artifacts contradict each other directly on arrival and dwell, and no
clause resolves the conflict. That is `POL-NS-09(b)` in terms.

The vote carried unanimously:

| draft | kind | proposed | abstention |
|---|---|---|---|
| 1 | sampled | `FULL_REFUND` 4.00 | — |
| 2 | sampled | `FULL_REFUND` 4.00 | — |
| 3 | sampled | `FULL_REFUND` 4.00 | — |
| 4 | position-swapped | `FULL_REFUND` 4.00 | — |

**The cause is a missed trigger.** The key escalates on a `POL-NS-09` limb and
the run decided the merits instead, with `agreement` 1.00 — a unanimous panel
that read the conflict as a false-arrival finding against the driver and refunded
the 4.00 fee, referring `POL-NS-05(ii)`. `POL-NS-09(b)` is exactly the limb that
exists so a record that contradicts itself about whether the driver was at the
pin is not ruled confidently, and the panel ruled it confidently.

**What the key says should have happened is that the fee was held.** The run
refunded it, so the amount was not held. The disagreement is recorded rather than
corrected: the key is not changed.

## Honest limits

- **n = 24.** The interval is wide — 0.690 to 0.957 — and a single figure over
  24 cases cannot separate this system from a substantially better or worse one.
- **The set was opened before the freeze.** Before the 2026-10-09 freeze the
  policy owner's AI assistant opened `sealed-v1`'s cases and key. By the policy
  owner's account no policy changed because of it, and one case's key and one
  derived fact (case 311) reached the development side at 23:11, after the frozen
  trees were committed at 22:42. The run is reported as it came out; the
  disclosure is stated in `README.md` and in
  `docs/governance/incidents.md`.
- **The author's independence is the author's own statement.** The archive's
  manifest records the set as prepared by
  `Claude (independent of prompt tuning; never saw dev-set misses or prompts)`.
  Whether that held while the set was built is not something this repository can
  answer.
- **`k` is undefined.** The set's README asks for k-consistency with k = 3 and
  does not define k; the run is made once with judge votes 4, and the agreement
  among the four votes is what is reported.

## What this run does not change

- **No ruling in the key changes.** All three misses are recorded against the key
  as it stands. `eval/answers/sealed-v1/ground_truth.json` is frozen from the
  moment it was imported. Editing an expected result so a run scores better
  destroys the measurement.
- **No code, prompt or policy changes.** `git diff --stat freeze-2026-10-09
  HEAD -- tribunal prompts policy` still prints nothing after this work. Nothing
  in this note edits `tribunal/`, `prompts/` or `policy/`.
- **The set is not development data.** Its cases are not run again, are not
  briefed to a model, and are not read by the policy-gap loop or the precedents
  block. The run is a sealed record, and the root it lives under is closed:
  nothing is created under `runs/sealed-v1/` again, the plain sealed run
  included.

**Any fix belongs to a later version, with a new sealed set.** 312 names a real
defect in the draft check — an amount the policy computes as a difference is
unreadable by construction — and 304 and 410 name readings the panel got wrong.
All three are the kind of change that would move rulings. Making any of them now
would mean the run reported as the third generalisation figure was produced by a
system that is no longer the system. The repair, when it is made, is measured on
the development sets, and the generalisation figure is taken again from a set
that has not been read. This run is closed as it stands.

## Where to read it

- **The run:** `runs/sealed-v1/deepseek-deepseek-flash/` — `run.json` for the
  configuration and provenance, `case-*.json` and `case-*.transcript.json` for
  each case, `report.md` for the per-case table.
- **The manifest:** `runs/sealed-v1-manifest.json` — the size and sha256 of every
  one of the 53 files, checked by `tests/test_sealed_v1_run_manifest.py`.
- **The console log:** `runs/sealed-v1-console.log` — the owner's terminal
  output for the one invocation.
- **The figures:** `python3 -m eval.sealed_report --set sealed-v1`, reproduced by
  `tests/test_sealed_report.py` and `tests/test_third_sealed_run_note.py`.
- **The key:** `eval/answers/sealed-v1/ground_truth.json` — re-derived at version
  6 by the key owner before the run; the note on the re-derivation is
  `docs/notes/2026-10-10-sealed-v1-key-at-version-6.md`.
- **The freeze:** `docs/notes/2026-10-09-the-third-freeze.md` — the tag
  `freeze-2026-10-09` and the arguments the run is fixed at.
- **The import:** `docs/notes/2026-10-09-sealed-v1-imported.md` — what the set
  is, where it came from, and the digest of every imported file.
- **The version-6 misses beside it:**
  `docs/notes/2026-10-10-what-went-wrong-at-version-6.md` — the causes this note
  uses are that note's.
- **The two earlier sealed runs:**
  `docs/notes/2026-09-30-the-sealed-run.md` and
  `docs/notes/2026-10-04-the-second-sealed-run.md`.
