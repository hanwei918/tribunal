# What can carry a deciding fact

Date: 2026-09-22. Commit: the one that adds this file.

## The defect

`prompts/v1/judge.system.md` Step 2 states the confidence rule, and states it correctly:

- the cap is the **MINIMUM** `weight_multiplier` among the artifacts that carry the deciding fact;
- the cap is the **MAXIMUM** of their weights where two or more **INDEPENDENT** artifacts carry
  that same fact.

It never said **what kind of artifact can carry a fact**. A real run shows the judge reading that
silence as a restriction to instrument evidence — GPS traces, trip records, fare breakdowns — and
excluding what the parties said. Nothing in the prompt said that; nothing in the prompt said
otherwise. Two cases were decided on the narrow reading, and both were escalated that should not
have been.

### Case 211

The judge wrote that "the deciding fact … therefore rests on the impaired trace alone", capped the
ruling at 0.39 and escalated.

The record does not support that. The deciding fact is not carried solely by the impaired trace:
`EV-CHAT-00211` is COMPLETE at weight 1.00, and `MSG-00211-004` is a message the driver sent at
12:35:10 — from inside the outage — which was read at 12:35:26, and which shows him still working
the pickup through the middle of the gap. Two independent carriers of the same fact means
POL-GEN-02 caps at the MAXIMUM of the two weights, so the cap is 0.72, and 0.72 clears the 0.70
floor.

### Case 107

Here the judge's reasoning is right and must not be disturbed. It ruled out the trip record and the
fare ledger as rounded copies of the same trace, which is what they are: two records derived from
one measurement are one carrier, not two.

It then found nothing else in the record and escalated at 0.30. What it had not counted is the
driver's own account. `MSG-00107-002` — "cte very jam tonight boss" — is the driver conceding that
he did not take the CTE, which is the route the optimal path uses; and a counterparty statement
admits that he routed "by Newton and Kim Seng". Two independent admissions carry the finding.

## The change

Step 2 gained a subsection, **"What can carry a deciding fact"**, between the confidence bullets and
the escalation floor. It says four things:

1. **Every artifact in `case.evidence` is a candidate carrier, not only the instrument evidence.**
   A chat log is an artifact; so is a counterparty statement. What a party said is evidence like any
   other, its weight is its own `weight_multiplier`, and a cap computed as though the instruments
   were the only things able to carry a fact escalates cases that are decidable.
2. **Two patterns qualify**, offered as illustrations of one principle rather than a list to match
   against: an admission against the speaker's own interest, and a contemporaneous record made from
   inside the disputed window.
3. **The removal test bounds it.** *Would the message still support the finding if the instrument
   evidence were removed?* A message that merely exists is not a carrier, and neither is one that
   only repeats what the instruments already say — a restatement is not an independent carrier and
   the cap does not move.
4. **The independence test is unchanged and still governs.** Two records derived from the same
   measurement are one carrier, not two, however many artifacts they arrive in.

### Why it is written as a principle and not as a list

The two cases are what produced the change. They are not the rule, and the prompt does not name
them: a model handed the case numbers would match on those and stop, and the next case shaped like
them would escalate exactly as before. The 0.70 floor is not restated in the prompt either — it is
read from the loaded policy, as it always was.

**The prompt says so itself, because the dangerous direction is the other one.** The failure being
fixed is over-escalation, which is the safe failure: a case sent to a human that did not need one.
Loosening Step 2 carelessly trades it for a confident ruling on a fact that nothing independent
supports, which is the failure this project exists to avoid. So the subsection states the removal
test *before* it can be applied, and says in as many words that it is not licence to escalate less.

## What this invalidates

Editing `judge.system.md` changes the prompts digest:

```
faa3da27c5fbd75052ef7cea11f09de6282f63b522183bf1de49a2fcc892de0b   before
457c896b07b3da23d2b00d957713d005a63514bc321cb77ceb414a44b49daba8   after
```

Every cached result was produced under an earlier prompt set, so every one of them is now stale on
the prompt channel. That is correct and expected, and it is the whole point of the prompt channel
existing: before this, editing a prompt changed what the agents were told to do while every cached
result continued to report as current.

**What the cache actually reports for that channel is `unknown`, not `stale`.** No per-case entry
records a prompts digest at all — the field was added after those results were written — so the
prompt half of the check cannot be made for any of them. See
`docs/notes/2026-09-22-stale-cached-results.md`, whose quoted block now reads `current=0`.

The run-level records do carry a prompts digest, and they disagree with the directory:

| record | prompts digest |
|---|---|
| `runs/hy3/run.json` | `5c1f58a3cb00a30b…` |
| `runs/hy4-preview/run.json` | `5c1f58a3cb00a30b…` |
| `runs/deepseek-deepseek-flash/run.json` | `faa3da27c5fbd750…` |
| the directory now | `457c896b07b3da23…` |

**Three values, so the prompt set has already moved twice, and until now nothing said so.** That is
the defect the prompt channel closes, and this change is the first movement it can report.

## What was not done

Nothing was re-run and no model call was made. No cached result was deleted, moved or rewritten: the
twenty-nine results are real measurements, and the reason every one of them now reads `unknown` on
the prompt channel is a property of the cache rather than of the code.

The change was made to the prompt and to the check that can see it. It was **not** made to the
recorded results, and the answer key was not touched.

## Verification

- **The prompt contract still holds for every agent.** The amended prompt ships exactly one ```` ```json ````
  example, the example parses, and the shape it asks for is one the request permits — asserted for
  all three roles, and again for the judge specifically.
- **The subsection is checked by reading it.** `DecidingFactCarrierTests` in `tests/test_pipeline.py`
  reads the Step 2 subsection out of the prompt and requires the principle, both patterns, the
  removal test, the non-qualifying message and the surviving independence rule. It also requires the
  subsection *not* to name cases 211 or 107 and not to restate the 0.70 floor, because a checklist
  is the failure mode this change could introduce.
- That class is a text check, and the file now says there are exactly two of them and why. The other
  is the existing guard against asking for a JSON array under `json_object`.
- **The two channels are checked apart.** `TwoChannelStalenessTests` in
  `tests/test_run_benchmark.py` moves the prompts digest alone and requires the report to say the
  prompts moved and not the brief; moves the brief digest alone and requires the converse; moves both
  and requires both; and removes an entry's prompts digest and requires `unknown` rather than
  `current`.
- No network, no credential, no model call, in any of the above.
