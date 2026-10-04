# The second sealed set's single run

**2026-10-04.** The second sealed set, `wild-v2`, was run once, by the owner,
from a commit whose `tribunal/`, `prompts/` and `policy/` trees equal those at
`freeze-2026-10-03`. The output is committed exactly as produced under
`runs/wild-v2/deepseek-deepseek-flash/` — 45 files, recorded in
`docs/notes/2026-10-04-wild-v2-run-manifest.txt`. The owner's run made the model
calls; none was made in this repository in committing or reading it. This note
reads every figure out of the committed files and the set's own key.

Nothing in this note changes a ruling, a prompt, a policy, a case file or the
key. It records what the run did, what it missed, and why. The key is frozen
from the moment it was imported, under the standing rule in `START-HERE.md`.

## The run, as the owner made it

The command, run by the owner outside this sandbox, one invocation:

    TRIBUNAL_SEALED_RUN=wild-v2 python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900

**When.** Started 2026-10-04 02:11:46 SGT and ended 03:25:32 SGT — a Sunday.

**From what.**

| | |
|---|---|
| commit | `6cc268298ac079807ddc6682b7776824371648c2` |
| working tree | clean — `run.json` records `working_tree_clean: true` |
| the freeze gate | `git diff --quiet freeze-2026-10-03 -- tribunal prompts policy` exited 0, as the owner recorded it |

**Configuration,** as `run.json` records it:

| setting | value |
|---|---|
| policy version | 2 |
| judge votes | 4 |
| verifier | off |
| precedents | off |
| ablation | off |
| `--timeout` | 900 s |
| `--concurrency` | 2 |
| case deadline | 2400 s |
| token budget | none |
| interpreter | 3.11.14 |

**Before the run.**

- One ping through the runtime client answered 200, as the owner recorded it.
- `--check` printed `would run (20): 701 ... 720`, with nothing not run and no
  attempt that did not count, as the owner recorded it.

**Outcome.** All 20 cases produced a ruling, and no case failed — `run.json`
records `failures: []`. Four judge answers were unusable and were re-asked inside
their own case by the pipeline's one in-call retry, which is not a protocol
retry: 701 twice (drafts 1 and 3), 708 once (draft 1) and 718 once (draft 1) —
four re-asks in all, each of which the model then answered. No protocol retry was
made, so the protocol's retry rules did not come into play. The event chain
verifies. 4,339,077 tokens were consumed, of which 1,044,223 were cached.

**The invocation cap.** The owner recorded one reading before the run. The
protocol addendum's section 4 says "at most two invocations", and the code
applies a per-case cap that does not count a killed attempt. The two can
disagree only after a killed invocation. The addendum itself says the code is
what the run follows, so the per-case rule would have governed. The situation
did not arise: there was one invocation and no case failed.

## The figures

From `python3 -m eval.sealed_report --set wild-v2`:

```
Four-field exact
  over the 20 cases that produced a ruling: 18/20
  over the 20 cases in the set, a case with no ruling as a miss: 18/20
Ruling alone
  over the 20 cases that produced a ruling: 18/20
  over the 20 cases in the set: 18/20
Per category, from the set's own index.json
  NO_SHOW_CHARGE: 8 in the set, 8 produced; four-field 8/8 over produced and 8/8 over all; ruling 8/8 over produced and 8/8 over all
  ROUTE_DEVIATION: 12 in the set, 12 produced; four-field 10/12 over produced and 10/12 over all; ruling 10/12 over produced and 10/12 over all
Escalation
  over the 20 cases that produced a ruling: 5 produced, 5 expected, 4 true positives; precision 4/5, recall 4/5
  over the 20 cases in the set: 5 produced, 5 expected, 4 true positives; precision 4/5, recall 4/5
No ruling (0)
```

All 20 cases produced a ruling, so the two bases agree here: with no no-ruling
case there is nothing for "over the set" to count as a miss that "over the
produced" does not. That is a property of this run and not of the two bases —
they came apart on `wild-v1`, whose two no-ruling cases moved one basis and not
the other.

**Escalation.** Five escalations were produced and five expected, with four true
positives: precision 4/5 and recall 4/5. The one over-escalation is **702** and
the one under-escalation is **716**; both are read below.

### The interval

Eighteen of twenty is a single figure over a small set, so it is reported with an
interval rather than alone.

| | figure | Wilson 95% interval |
|---|---|---|
| `wild-v2` (this run) | 18/20 = 90.0% | **0.699 to 0.972** |
| `wild-v1` (the held-out set) | 55/64 = 85.9% | **0.754 to 0.924** |

The intervals are the Wilson score interval for a binomial proportion at 95%,
computed from the counts by code in `tests/test_second_sealed_run_note.py`, which
reads the two figures out of the committed runs and recomputes both intervals —
**neither bound above is typed into the test**.

**The two are never summed or pooled.** Each is its own generalisation figure,
from its own freeze, over its own set: `wild-v2`'s over 20 cases from
`freeze-2026-10-03`, `wild-v1`'s over 64 cases from `freeze-2026-09-30`. One
figure over 20 cases plus another over 64 is not a measurement of 84 cases, and
the intervals above overlap precisely because neither set is large enough to
separate them. Nothing in the repository adds them.

## The two misses

Both are ruling misses: the ruling field differs from the key. Each is given with
the key against the produced ruling, the vote, and a cause checked against the
case file, the brief and the transcript.

### 702 — over-escalation, and a safe miss

**Key:** `NO_ACTION`, no money. **Produced:** `ESCALATE`, no money.

702 is a route-deviation case on an **upfront-quoted** fare, and the charge
equals the governing quote. `EV-FARE-00702` records `fare_model UPFRONT_QUOTE`,
`quoted_fare_sgd 22.40` and `total_charged 22.40`, with no ERP and no airport
surcharge, so the charged-over-quote figure is 0.00 and the policy's remedy for
an upfront fare computes to 0.00. The trace is 10.99 km against an amended
baseline of 11.00 km. Nothing under the policy moves money, which is what the key
says.

The vote did not carry:

| draft | kind | proposed | abstention |
|---|---|---|---|
| 1 | sampled | `amount_sgd` 8.6 | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 2 | sampled | `amount_sgd` 8.60 | `DRAFT_AMOUNT_NOT_READ_OFF` |
| 3 | sampled | `NO_ACTION` | — |
| 4 | position-swapped | `ESCALATE` | — |

**The money block published the right figure.** It published `pol_rd_11_remedy`
0.00, with the charge equal to the governing `quoted_fare_sgd` of 22.40: no
distance-or-time refund is available on an upfront fare, and the clause's own
arithmetic gives 0.00. The brief that figure is read out of is the one the run
was given — rebuilding the brief from the case file and the policy at version 2
gives a sha256 equal to the `brief_sha256` the run recorded for 702.

**8.60 is in the record, not an inference.** It is the dispute's own
`amount_contested_sgd`, and the rider's claim and drafts 1 and 2 derive it the
same way: 22.40 less the **superseded** 13.80 quote in the chat log
(`EV-CHAT-00702`), read as "the fare fixed at booking" under `POL-RD-11(a)`. The
governing `quoted_fare_sgd` is 22.40, not 13.80, so that reading is the one the
key rejects — but the figure itself is on the case, not read into it.

**The four drafts.** Drafts 1 and 2 (both sampled) proposed `FULL_REFUND` 8.60
and were rejected by the draft check `DRAFT_AMOUNT_NOT_READ_OFF`, because 8.60 is
neither a figure the brief's money block publishes nor the sum of two or three of
them. Draft 3 (sampled) computed 0.00 and proposed `NO_ACTION`, which is correct.
The position-swapped draft 4 proposed `ESCALATE` under `POL-RD-10(7)`, on its
reading that the chat and the ledger are mutually contradictory evidence of
comparable strength.

**The quorum, not the read-off check, kept the refund from being paid.** The
threshold is 3, so `FULL_REFUND` at 2 of 4 would have escalated even if both 8.60
drafts had passed the check. With the two 8.60 drafts abstaining there were **2
valid drafts**, and a quorum of 3 agreeing drafts was needed; the two that
remained disagreed — `NO_ACTION` and `ESCALATE` — so the case escalated.

**The miss comes from a reading of `POL-RD-11(a)`, not from the read-off check.**
The check did not stop a correct answer; it stopped two drafts that read the
chat's 13.80 as the fare fixed at booking. A draft that had computed 0.00 the way
draft 3 did would have carried, and the case would have been decided the way the
key decides it. What went wrong is that the first two drafts read `POL-RD-11(a)`
the other way.

### 716 — under-escalation, the dangerous kind

**Key:** `ESCALATE`, no money, difficulty `INDETERMINATE`, under `POL-RD-10(4)`
and `POL-GEN-02`. **Produced:** `NO_ACTION`, confidence 0.85.

This is the miss to read carefully, because it goes the other way: the system
decided confidently a case the key says is not decidable.

The record is impaired on both sides of the disputed fact:

| artifact | weight | issue codes |
|---|---|---|
| `EV-TRIP-00716` (trip record) | 0.30 | `STALE_SNAPSHOT`, `CROSS_SOURCE_CONFLICT` |
| `EV-GPS-00716` (GPS trace) | 0.25 | `TIMESTAMP_OUT_OF_RANGE`, `CROSS_SOURCE_CONFLICT` |

The trip record's stale snapshot carries a cancellation at 13:27:40, and the
trace runs to a terminal fix at 13:43:40 — **16 minutes later**. So the record
holds a cancellation and a trace that continues past it, and the two disagree
about what happened.

**The judge and the key differ about what the deciding fact is.** The judge took
it to be the fare at its quote, carried by `EV-FARE-00716` at weight 1.0. The key
takes it to be whether a **billable trip ran** at all, a fact that rests only on
the 0.30 and 0.25 artifacts. The key's rationale rests on `POL-RD-10(4)` and
`POL-GEN-02` and on nothing else: `POL-RD-10(4)` "independently mandates terminal
escalation" and `POL-GEN-02` "forbids treating either discounted revision as
decisive proof for a monetary award". It does not rest on `POL-RD-10(1)` or on a
0.25 cap; that route is the dissent's, read below.

The judge carried `NO_ACTION` with three of four drafts (agreement 0.75,
`carried_not_unanimous`), and its explanation says exactly why:

> (4) the 16-minute divergence flagged by the pre-pass is between a cancellation
> event and the trace's terminal fix, not between pickup or dropoff timestamps -
> pickup agrees at 13:18:40 on both artifacts and ended_at is null - so (4) is
> not engaged.

That is a **literal** reading of `POL-RD-10(4)`: the limb is about a disagreement
between *pickup or dropoff timestamps*, and a cancellation-to-final-fix gap is
neither. On that reading the limb does not fire, and the judge then rested the
ruling on the fare record:

> The fact the ruling actually rests on, that this is an upfront fare charged
> exactly at its quote with no chargeable pass-throughs, is carried by
> EV-FARE-00716 at weight 1.0.

So the ruling stands on one artifact at weight 1.0 while the two artifacts that
carry the dispute are at 0.30 and 0.25. **`POL-GEN-02(2)`, whole, as
`policy/general.json` writes it:** "The Judge's confidence in a ruling is capped
by the evidence the ruling actually rests on: confidence must not exceed the
minimum weight_multiplier among the artifacts that carry the deciding fact, and
where two or more independent artifacts carry it, that cap is the maximum of
their weight_multipliers rather than the minimum. bundle_integrity_score, the
mean weight across the bundle, is context for the reader and is NOT the cap.
Because the platform-wide escalation floor is 0.70, a deciding fact carried
solely by an artifact at weight 0.65 or below escalates automatically under
POL-RD-10(1) or POL-NS-09(a)." The judge's answer is that the fare record is what
carries the decision, so its cap is 1.0. The key's rationale for this case
rejects that move in its own words: `POL-GEN-02` "forbids treating either
discounted revision as decisive proof for a monetary award". That phrase is the
rationale's, not the clause's.

**Even the maximum is below the floor.** The two impaired artifacts are not
independent carriers — one says the trip ran and the other says it was cancelled,
and the trip record's distance is a copy of the same measurement — so the maximum
clause does not lift the cap here. Even if it did, the maximum of 0.30 and 0.25 is
**0.30**, and 0.30 is itself below the 0.70 floor, so escalation would be
mandatory on either reading.

**The dissent was sampled draft 2.** It proposed `ESCALATE` under `POL-GEN-02(2)`
and `POL-RD-10(1)`, holding that

> The fact that decides this case - whether a billable trip was performed - is
> carried only by that impaired telemetry.

so that its confidence "cannot exceed the minimum weight among its carriers,
0.25", which is below the 0.70 floor. **That minimum reading is draft 2's
argument, not the key's:** the two impaired artifacts are not independent
carriers, and the key's rationale rests on `POL-RD-10(4)` and `POL-GEN-02` rather
than on the 0.25 cap or on `POL-RD-10(1)`. The position-swapped **draft 4 voted
with the `NO_ACTION` majority**, so the split was three to one, not four to zero.

**The literal reading is arguable.** `POL-RD-10(4)`'s words are what the judge
says they are. But the clause exists so that a case like this one — a record that
contradicts itself about whether the trip was cancelled, and an impaired trace
for the interval that matters — is not ruled confidently. Reading it so that it
never fires on a cancellation is reading it out of the cases it was written for.
**The miss is the system's, and the disagreement is recorded rather than
corrected: the key is not changed.** What the key says should have happened is
that the disputed amount was held; the run paid nothing and decided the case, so
the amount was not held.

## Honest limits

- **n = 20.** The interval is wide — 0.699 to 0.972 — and it is wider than
  `wild-v1`'s over its 64 cases. A single figure over 20 cases cannot separate
  this system from a substantially better or worse one.
- **The set shares its generator with `wild-v1`.** Three of the eight generator
  files are byte-identical to `wild-v1`'s — `core.py`, `places.py` and
  `wild.py` — and `wild-v2` was authored against the same policy files.
  `wild-v1` became development data on 2026-10-01, and two changes were made
  because of what it showed: `POL-RD-13`, the missing-advisory route-deviation
  clause, and the `POL-RD-11` upfront-quote remedy. So `wild-v2` is **not**
  independent of the data the system was last tuned on, and its figure may be
  optimistic for data from another source. This is the strongest reason to read
  18/20 as an upper estimate rather than as an expectation.
- **Codex's access to this repository** while it built the set is not recorded.
  The set was prepared by OpenAI Codex for the owner; whether Codex could read
  the repository's prompts, policy or prior runs while doing so is not something
  the repository can answer.
- **The partial run of 14:14.** On 2026-10-03 an interrupted probe left an
  `events.jsonl` under `runs/wild-v2/` with two cases started and no terminal
  event; the file was deleted at 14:19:36, and the owner decided the same day
  that the set stayed sealed and that the attempt does not count under the
  protocol. It is recorded in full in
  `docs/notes/2026-10-03-the-sealed-protocol-made-executable.md`, under *The
  partial run of 14:14, and the owner's decision*.

## What this run does not change

- **No ruling in the key changes.** Both misses are recorded against the key as
  it stands. `eval/answers/wild-v2/ground_truth.json` is frozen from the moment
  it was imported. Editing an expected result so a run scores better destroys
  the only independent measurement this project has.
- **No code, prompt or policy changes.** `git diff --quiet freeze-2026-10-03 --
  tribunal prompts policy` still exits 0 after this work, as it did before the
  run. Nothing in this note edits `tribunal/`, `prompts/` or `policy/`.
- **The set is not development data.** Its cases are not run again, are not
  briefed to a model, and are not read by the policy-gap loop or the precedents
  block. The run is a sealed record, and the root it lives under is closed:
  nothing is created under `runs/wild-v2/` again, the plain sealed run included.

**Any fix belongs to a later version, with a new sealed set.** 716 names a real
question — whether `POL-RD-10(4)` reaches a cancellation-to-final-fix
divergence — and 702 names a reading of `POL-RD-11(a)` that takes a superseded
quote as the fare fixed at booking. Both are the kind of change that would move
rulings. Making either now would mean the run reported as the second
generalisation figure was produced by a system that is no longer the system. The
repair, when it is made, is measured on the development sets, and the
generalisation figure is taken again from a set that has not been read. This run
is closed as it stands.

## Where to read it

- **The run:** `runs/wild-v2/deepseek-deepseek-flash/` — `run.json` for the
  configuration and provenance, `case-*.json` and `case-*.transcript.json` for
  each case, `report.md` for the per-case table.
- **The manifest:** `docs/notes/2026-10-04-wild-v2-run-manifest.txt` — the digest
  of every one of the 45 files, checked by `tests/test_wild_v2_run_manifest.py`.
- **The figures:** `python3 -m eval.sealed_report --set wild-v2`, reproduced
  whole by `tests/test_sealed_report.py`.
- **The freeze:** `docs/notes/2026-10-03-the-second-freeze.md` — the tag
  `freeze-2026-10-03` and the arguments the run is fixed at.
- **The protocol:** `docs/notes/2026-10-03-the-sealed-protocol-made-executable.md`
  and `docs/notes/2026-10-03-the-sealed-protocol-addendum.md` — the rules the run
  follows, including the partial run of 14:14.
- **The import:** `docs/notes/2026-10-03-wild-v2-imported.md` — what the set is,
  where it came from, and the digest of every imported file.
- **The held-out set's own run, beside it:**
  `docs/notes/2026-09-30-the-sealed-run.md`.
