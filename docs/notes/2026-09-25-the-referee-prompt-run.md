# The referee prompt run

**2026-09-25.** The judge prompt now hands the judge the mechanical referee's
kept claims, its ledger and its flags (directory digest `324d5613…`). This note
records the run that measured that change, exactly as produced. Nothing was
re-run to write this up: every figure is read out of `runs/`, the invocation
history and git, and no model call was made in this session.

## What ran

`--replay-advocates runs/deepseek-deepseek-flash --force`, at commit `093711b`,
on the owner's balance. Two attempts, because the machine went to sleep in
between.

| attempt | started (SGT) | asked | outcome |
|---|---|---|---|
| 1 | 18:01 | corpus 101–214 | 101–107 completed; **108 `TIMEOUT`**; 109–214 every call `TRANSPORT` — `could not reach the endpoint: [Errno 8] nodename nor servname provided, or not known` |
| 1b | 18:21 | second set 9101–9115 | all fifteen `TRANSPORT`, the same error; **0 tokens charged**, because no request reached the endpoint |
| 2 | 19:37 | corpus 108–214 | 22 of 22 completed |
| 2b | 19:59 | second set 9101–9115 | 15 of 15 completed |

The attempt-1 failures are **network** failures, not model failures: the machine
had gone to sleep, and `nodename nor servname provided` is DNS resolution
failing, not the provider refusing. Case 108 is the one exception in kind — a
`TIMEOUT`, recorded with zero failure tokens — and it was re-run in attempt 2
with the rest. Every failed case was re-run; none was left failed.

## Result

| set | exact | failing |
|---|---:|---|
| corpus | **28/29** | 211 (`ruling`, `amount_sgd`) |
| second set | **14/15** | 9111 (`amount_sgd`, `referrals`) |
| **combined** | **42/44** | |

All 44 results are current under `324d5613…`: `stale_brief = ()`,
`stale_prompts = ()` and `unknown = ()` for both sets, and every record's own
`prompts_sha256` is the current directory digest. Under the previous prompt
(`829ccc8f…`) the same code read **27/29** on the corpus and 14/15 on the second
set — 41/44 combined. Two cases moved, and both were among the three (105, 107,
211) that have flipped between runs whose prompts differed in ways unrelated to
them; 107 did not move this time.

- **105** moved from `ESCALATE` to **`FULL_REFUND 65.13`**, which is the key's
  answer — the case the earlier runs read both ways.
- **211** moved from `DRIVER_COMPENSATION 3.2` to **`ESCALATE`**, still not the
  key's `PARTIAL_REFUND 2.00`, but now in the safe direction: it holds the fee
  rather than paying it out.

## Per case, against the previous prompt

### Corpus (101–214)

| case | `829ccc8f` | `324d5613` | verdict |
|---|---|---|---|
| 101 | PARTIAL_REFUND 8.05 | PARTIAL_REFUND 8.05 | exact |
| 102 | NO_ACTION | NO_ACTION | exact |
| 103 | PARTIAL_REFUND 4.0 | PARTIAL_REFUND 4.0 | exact |
| 104 | PARTIAL_REFUND 3.6 | PARTIAL_REFUND 3.6 | exact |
| 105 | ESCALATE | FULL_REFUND 65.13 | exact *(moved)* |
| 106 | PARTIAL_REFUND 10.75 | PARTIAL_REFUND 10.75 | exact |
| 107 | PARTIAL_REFUND 7.45 | PARTIAL_REFUND 7.45 | exact |
| 108 | NO_ACTION | NO_ACTION | exact |
| 109 | DRIVER_COMPENSATION 3.15 | DRIVER_COMPENSATION 3.15 | exact |
| 110 | ESCALATE | ESCALATE | exact |
| 111 | NO_ACTION | NO_ACTION | exact |
| 112 | ESCALATE | ESCALATE | exact |
| 113 | NO_ACTION | NO_ACTION | exact |
| 114 | PARTIAL_REFUND 13.7 | PARTIAL_REFUND 13.7 | exact |
| 115 | PARTIAL_REFUND 2.0 | PARTIAL_REFUND 2.0 | exact |
| 201 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 202 | DRIVER_COMPENSATION 4.8 | DRIVER_COMPENSATION 4.8 | exact |
| 203 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 204 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 205 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 206 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 207 | ESCALATE | ESCALATE | exact |
| 208 | DRIVER_COMPENSATION 6.4 | DRIVER_COMPENSATION 6.4 | exact |
| 209 | NO_ACTION | NO_ACTION | exact |
| 210 | ESCALATE | ESCALATE | exact |
| 211 | DRIVER_COMPENSATION 3.2 | ESCALATE | **ruling, amount_sgd** *(moved)* |
| 212 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 213 | ESCALATE | ESCALATE | exact |
| 214 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | exact |

### Second development set (9101–9115)

| case | `829ccc8f` | `324d5613` | verdict |
|---|---|---|---|
| 9101 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | exact |
| 9102 | DRIVER_COMPENSATION 4.8 | DRIVER_COMPENSATION 4.8 | exact |
| 9103 | FULL_REFUND 8.0 | FULL_REFUND 8.0 | exact |
| 9104 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 9105 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | exact |
| 9106 | FULL_REFUND 6.0 | FULL_REFUND 6.0 | exact |
| 9107 | DRIVER_COMPENSATION 3.2 | DRIVER_COMPENSATION 3.2 | exact |
| 9108 | ESCALATE | ESCALATE | exact |
| 9109 | ESCALATE | ESCALATE | exact |
| 9110 | ESCALATE | ESCALATE | exact |
| 9111 | PARTIAL_REFUND 9.15 | PARTIAL_REFUND 9.15 | **amount_sgd, referrals** |
| 9112 | NO_ACTION | NO_ACTION | exact |
| 9113 | PARTIAL_REFUND 9.05 | PARTIAL_REFUND 9.05 | exact |
| 9114 | FULL_REFUND 3.2 | FULL_REFUND 3.2 | exact |
| 9115 | ESCALATE | ESCALATE | exact |

9111 is the known one: the key was corrected to `PARTIAL_REFUND 10.15` with one
POL-RD-09(4) referral, and the judge still returns `9.15` with none.

## 211's deciding sentences

The move is the judge changing its mind about whether a chat message can carry
the in-geofence fact across the trace's 168-second outage. It now says it
cannot. The sentences that decide the escalation, quoted from
`runs/deepseek-deepseek-flash/case-00211.json`:

> POL-NS-01(c) requires the driver to hold position inside the geofence for a
> continuous 300 seconds, measured from the first qualifying fix, not from the
> arrival event. EV-GPS-00211 shows two in-geofence runs — 220 s from 12:30:00
> and 112 s from 12:36:28 — split by a 168-second outage from 12:33:40 to
> 12:36:28, at 84.3% coverage. The 500-second "longest qualifying run" the
> driver relies on is a span drawn across that outage: its 35 fixes are exactly
> the 23 before it and the 12 after it, with none inside, so it is not
> demonstrated continuous presence.

> The driver's 12:35:10 message is contemporaneous and sits inside the outage,
> and it shows he was still working the pickup, but it records no position; it
> therefore does not carry the in-geofence fact and neither lifts the cap nor
> supplies a second carrier.

> On that basis POL-NS-08's closing sentence and POL-NS-09(e) apply — where the
> sole evidence for the deciding fact is impaired under POL-NS-08(a) to (d), the
> ruling may not exceed PARTIAL_REFUND and the case escalates — and my
> confidence is capped at 0.39, below the 0.70 floor, which escalates
> independently under POL-NS-09(a).

The previous run read the same message the other way — "It therefore counts, and
it means the impaired trace is not the only evidence of what was happening in
those 168 seconds" — and paid the driver `3.20` at confidence `0.85`. Same
inputs, same brief, same advocate transcripts; only the judge's instructions
moved. That flip, on a case where nothing about the case changed, is the
instability the voting work in the next commit exists to measure.

## Cost

Charged to **the owner's balance**: **1,408,309 tokens** across the four
invocations that reached the endpoint —

| invocation | charged |
|---|---:|
| 18:01 corpus attempt (101–107) | 229,950 |
| 18:21 second-set attempt (all failed, nothing reached the endpoint) | 0 |
| 19:37 corpus re-run (108–214) | 756,931 |
| 19:59 second-set re-run (9101–9115) | 421,428 |
| **total** | **1,408,309** |

The replayed advocates' own tokens — 370,767 + 1,363,060 + 871,792 =
**2,605,619** — were billed to the earlier run that produced them and are
recorded here as `billed_to_another_run`; they are not part of the figure above.
