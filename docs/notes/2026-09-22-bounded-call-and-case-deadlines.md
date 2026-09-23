# Bounded: a total deadline for one call, and one for a case

Date: 2026-09-22. Recorded because both numbers are derivations, not choices,
and the derivation is the thing that has to survive.

## What happened

A real benchmark run wrote its last case at 07:25 and then produced nothing. At
09:13 the process was still alive. A direct probe of the endpoint answered
HTTP 200 in 0.95 s, so the provider was healthy: nothing was wrong with the
service, the run had simply stopped making progress and nothing said so.

One hour and forty-eight minutes of wall clock, no output, no case written.

## Why

Two limits existed and their product was not one.

| Limit | Where | What it bounds |
| --- | --- | --- |
| `timeout_seconds` = 600 | `tribunal/llm.py` | **one attempt** |
| `max_attempts` = 4 | `tribunal/llm.py` | how many attempts |

`timeout_seconds` was read as though it bounded a call. It bounds an attempt.
The arithmetic that follows:

- **One call, worst case.** 4 attempts x 600 s + backoff (1 + 2 + 4 s) = 2407 s,
  about 40 minutes.
- **One case, worst case.** Three agents, each retried once on shape: 6 calls x
  2407 s = 14 442 s, which is 240.7 minutes — the "241 minutes" this change was
  asked for. That is the figure that explains a run sitting silent for nearly
  two hours: it was inside its limits the whole time.

There was no total deadline anywhere in `tribunal/llm.py` or
`tribunal/pipeline.py`. Two cases in that run also failed at zero recorded
tokens — one TRANSPORT (`RemoteDisconnected`) and one TIMEOUT at 605.8 s — so an
unbounded retry loop spends money as well as time.

## What was measured

Two sweeps, and they disagree. The disagreement is the point, so both are here.

**Per call, from the run transcripts (n = 100).** Minimum 23.1 s, median 58.2 s,
p90 154.6 s, maximum **305.7 s**. Twenty calls at or above 100 s, two at or above
300 s, none at or above 500 s. The slowest four:

| Seconds | Agent | Case |
| --- | --- | --- |
| 305.7 | RIDER_ADVOCATE | 207 |
| 302.7 | DRIVER_ADVOCATE | 109 |
| 275.1 | JUDGE | 107 |
| 256.6 | RIDER_ADVOCATE | 109 |

**Per case, from the same transcripts (n = 30).** Slowest **978.8 s**
(`case-00109` on `hy4-preview`), then 553.3 s (`case-00107`) and 305.1 s
(`case-00112`).

**Per call, as observed in the failed run.** 96 s to 606 s, including a TIMEOUT
failure at 605.8 s and one TRANSPORT failure at zero tokens.

**The two per-call sweeps do not agree, and the transcript sweep is the one that
understates.** A call that times out or hangs raises before a `PipelineResult`
exists, so it leaves no completed cache entry and no transcript: the cache can
only ever contain calls that finished. Its maximum of 305.7 s is therefore a
maximum over the calls that succeeded, not over the calls that happened. The
failed run's 606 s is the figure a limit has to be set against, because a real
attempt does run into the per-attempt timeout, and that is precisely the
situation `max_attempts` exists for.

The hung run's own record, from
`runs/deepseek-deepseek-flash/invocations.json`: one invocation, started
`2026-09-22T13:46:55.938865+00:00`, `ended_at` `2026-09-22T23:25:05.437808+00:00`
(= 07:25:05 SGT, the last case written), `stop_reason` `completed`,
`timeout_seconds` 600.0, 29 cases in the directory. `ended_at` records the last
`write_metadata`, not the end of the process — which is exactly why the run's own
record could not tell anyone it had hung.

## The two defaults, and how each was derived

**`DEFAULT_TOTAL_DEADLINE_SECONDS = 1200.0`** — the bound on one call, every
attempt and all backoff included.

Two full attempts is the floor rather than a round number. The 605.8-second
TIMEOUT shows a real attempt does consume the whole per-attempt timeout, and a
retry after such an attempt is the one thing `max_attempts` exists for, so a
deadline below 2 x 600 s would remove a capability rather than bound a risk.
1200 s bounds one call at 20 minutes instead of 40, while still leaving the
slowest call anyone has seen (305.7 s) four times its own duration.

**`DEFAULT_CASE_DEADLINE_SECONDS = 2400.0`** — the bound on one case, all three
agent calls and any shape retry included.

Three constraints hold at once, and each one is a measurement:

1. It must clear the slowest case actually seen. The slowest is 978.8 s, so a
   limit at or below that would fail the slowest thing the corpus contains —
   the opposite defect, and the reason 1200 s was rejected for this bound.
2. It must accommodate three calls each running into the per-attempt timeout:
   3 x 606 s = 1818 s. 2400 s covers that with margin.
3. It must bound the 241-minute worst case. 2400 s is 40 minutes, so the case
   bound is a 6.0x reduction on the product it replaces, and tighter still than
   the 6 x 1200 s = 120 minutes the per-call deadline alone would allow.

## What the code does now

**`tribunal/llm.py`.** `DEFAULT_TOTAL_DEADLINE_SECONDS`, a
`total_deadline_seconds` constructor argument, and `DeadlineExceededError`. The
check runs **before each attempt**: an attempt needs a whole `timeout_seconds`
of remaining budget, so one that cannot finish is refused rather than begun.
That ordering is what keeps the two failures distinguishable — beginning an
attempt that overruns would surface as a `TimeoutError`, which is a different
event with different advice. A deadline below one attempt is refused at
construction rather than clamped, because clamping would silently turn every
call into a single-attempt one.

**`tribunal/pipeline.py`.** `DEFAULT_CASE_DEADLINE_SECONDS`, a `case_deadline`
argument on `run_case`, and `CaseDeadlineExceeded`. The check runs before each
agent call **and before each shape retry**, since the retry is a call like any
other. The failure carries the elapsed seconds, so the record names the figure
the limit was measured against rather than only the limit.

**`eval/run_benchmark.py`.** `FAILURE_DEADLINE`, a fourth kind beside TIMEOUT,
TRANSPORT and SHAPE. `failure_kind_for` is the single classification point, and
both deadline exceptions map to it — they are raised from different layers but a
reader acts on them the same way. `--case-deadline` mirrors `--timeout` so the
bound can be moved without editing code, and both are recorded in the run
metadata and printed on the summary block, because a `DEADLINE` failure is only
interpretable against the limit that produced it.

**`format_start`.** A line printed when a case **starts**, emitted from the
thread that owns the queue and before the work is submitted, so the last line on
the terminal always names what is in flight. This is the part that would have
made the original hang visible in its first minute instead of its hundred and
eighth: the run's last line before it went silent named a case that had already
finished.

## Not re-measured

No benchmark was re-run to produce this note. The figures above come from
transcripts and invocation records already on disk. The provider was in peak
pricing during Singapore working hours, and the 29-case re-run will be restarted
deliberately, under both new limits, as a separate act.
