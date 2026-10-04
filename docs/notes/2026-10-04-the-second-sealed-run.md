# The second sealed set's single run

**2026-10-04.** The second sealed set, `wild-v2`, was run once, by the owner,
from a commit whose `tribunal/`, `prompts/` and `policy/` trees equal those at
`freeze-2026-10-03`. The output is committed exactly as produced under
`runs/wild-v2/deepseek-deepseek-flash/` — 45 files, recorded in
`docs/notes/2026-10-04-wild-v2-run-manifest.txt` — and **no model call was made
in this repository** to produce or to read it. This note reads every figure out
of the committed files and the set's own key.

Nothing in this note changes a ruling, a prompt, a policy, a case file or the
key. It records what the run did, what it missed, and why. The key is frozen
from the moment it was imported, under the standing rule in `START-HERE.md`.

## The run, as the owner made it

The command, run by the owner outside this sandbox, one invocation:

    TRIBUNAL_SEALED_RUN=wild-v2 python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900

**When.** Started 2026-10-04 02:11:46 SGT and ended 03:25:32 SGT — a Sunday, and
off-peak.

**From what.**

| | |
|---|---|
| commit | `6cc268298ac079807ddc6682b7776824371648c2` |
| working tree | clean — `run.json` records `working_tree_clean: true` |
| the freeze gate | `git diff --quiet freeze-2026-10-03 -- tribunal prompts policy` exited 0 |

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

- One ping through the runtime client answered 200.
- `--check` printed `would run (20): 701 ... 720`, with nothing not run and no
  attempt that did not count.

**Outcome.** All 20 cases produced a ruling, with no failure of any kind. So no
retry was made, and the protocol's retry rules did not come into play. The event
chain verifies. 4,339,077 tokens were consumed, of which 1,044,223 were cached.

**The invocation cap.** The owner recorded one reading before the run. The
protocol addendum's section 4 says "at most two invocations", and the code
applies a per-case cap that does not count a killed attempt. The two can
disagree only after a killed invocation. The addendum itself says the code is
what the run follows, so the per-case rule would have governed. The situation
did not arise: there was one invocation and no failure.

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

Two drafts proposed a refund of 8.60 and the draft check
`DRAFT_AMOUNT_NOT_READ_OFF` rejected both, because 8.60 is neither a figure the
brief's money block publishes nor the sum of two or three of them. That left two
usable drafts that disagreed — `NO_ACTION` and `ESCALATE` — so agreement was
0.25, below the quorum of 3, and the case escalated.

**What 8.60 most likely is.** The case shows an earlier quote and a superseding
amendment: the in-app chat (`EV-CHAT-00702`) has the rider writing *"I changed it
and the app now says 22.40, not 13.80"*, and the trip record's
`dropoff_amended_at` is set with the original pin recorded. 22.40 − 13.80 = 8.60.
So 8.60 is most likely the charge less the **earlier, superseded** quote — the
amendment's difference, not the excess over the governing fare, which is 0.00.
**This is an inference from the case's own figures and not a claim the record
states.**

The miss is safe in the way that matters: the check kept a wrong refund from
being paid. A draft that had computed 0.00 would have passed and the case would
have been decided, so what went wrong is that no draft found the right figure —
not that the system published a wrong one.

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

The judge carried `NO_ACTION` with three of four drafts (agreement 0.75,
`carried_not_unanimous`), and its explanation says exactly why:

> (4) the 16-minute divergence flagged by the pre-pass is between a cancellation
> event and the trace's terminal fix, not between pickup or dropoff timestamps —
> pickup agrees at 13:18:40 on both artifacts and `ended_at` is null — so (4) is
> not engaged.

That is a **literal** reading of `POL-RD-10(4)`: the limb is about a disagreement
between *pickup or dropoff timestamps*, and a cancellation-to-final-fix gap is
neither. On that reading the limb does not fire, and the judge then rested the
ruling on the fare record:

> The fact the ruling actually rests on, that this is an upfront fare charged
> exactly at its quote with no chargeable pass-throughs, is carried by
> `EV-FARE-00716` at weight 1.0.

So the ruling stands on one artifact at weight 1.0 while the two artifacts that
carry the dispute are at 0.30 and 0.25 — and `POL-GEN-02` is what forbids exactly
that: a discounted revision may not be treated as decisive proof for a monetary
award.

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
  briefed, and are not read by the policy-gap loop or the precedents block. The
  run is a sealed record, and the root it lives under is closed: nothing is
  created under `runs/wild-v2/` again, the plain sealed run included.

**Any fix belongs to a later version, with a new sealed set.** 716 names a real
question — whether `POL-RD-10(4)` reaches a cancellation-to-final-fix
divergence — and 702 names a draft check that could not express the right figure.
Both are the kind of change that would move rulings. Making either now would mean
the run reported as the second generalisation figure was produced by a system
that is no longer the system. The repair, when it is made, is measured on the
development sets, and the generalisation figure is taken again from a set that
has not been read. This run is closed as it stands.

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
