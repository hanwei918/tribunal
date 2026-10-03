# The sealed protocol, addendum — four rules the first note did not state

**2026-10-03. This note makes no model call, and it is written before the sealed
run of `wild-v2`.** It is the addendum
`docs/notes/2026-10-03-the-sealed-protocol-made-executable.md` points at. That
note states the rule and the code that applies it; this one states four things
the rule implies, which the first note left to be worked out from the code.

Nothing here changes the rule. Each statement below is what
`eval/development_sets.py` already does when it decides which cases a second
invocation of a sealed set runs again, and each is written down because a reader
deciding whether to run the set should be able to read the rule rather than
infer it.

## 1. A SHAPE failure with zero agent calls is retried once

A `case_failed` with `failure_kind` `SHAPE` normally means the model answered and
every answer was rejected, which is why it is not retried: re-running it would
re-sample the judge. The verdict is not taken from the kind alone. It is taken
from the kind **and** the calls: the case is not retried only when every
`agent_call` of that case in that invocation was answered 200.

So **a SHAPE failure with zero agent calls is retried once**: the invocation
recorded the kind and no call at all, so there is no evidence the model was ever
asked, and the answer is to ask. The same clause covers a SHAPE failure whose
calls were answered with something other than 200 — a server error that exhausted
the client's own retries.

## 2. A `ruling` event with no case file is retried once

The protocol's rule is that a case with a **result** is never re-run, and the
result is the case file: `run_benchmark.load_cached` is what the runner itself
consults, and a case it can load is kept before the events are read at all.

That leaves one shape: an invocation that recorded a `ruling` event and wrote no
case file — killed between the two, or a write that failed. **A `ruling` event
with no case file is retried once.** The model did answer, so it is not re-sampled
twice; the second attempt is the cap, and a case that records a ruling and still
writes no file is a case with no ruling.

## 3. An unparseable last line makes that attempt one that does not count

A process stopped mid-write ends the file part-way through a record. The protocol
reads the run's own log, so it has to say what that line is, and it says two
things:

- **an unparseable last line makes that attempt one that does not count.** The
  partial line is left out of the reading, the attempt keeps its `agent_call`
  events and has no terminal event, and the rule for an attempt with no terminal
  event applies: it is printed, and it does not consume one of the case's two.
- **It is not a broken chain.** `tribunal.events.verify_chain` reports any line
  that is not a JSON object, and the protocol refuses to run at all on a broken
  chain — a log whose lines were edited is not a log to decide from. A **last**
  line that does not parse is the one exception, because it is an incomplete
  write rather than an edit: an edited line still parses, so nothing is tolerated
  but the truncation at the end of the file. The judgement is stated beside the
  code in `_refuse_a_broken_sealed_chain`.

## 4. The owner runs at most two invocations, plus as many `--check` runs as needed

**The owner runs at most two invocations, plus as many `--check` runs as needed.**
The cap is per case: no case gets a third attempt, and two attempts with no result
is no ruling. `--check` is not an invocation — it builds no client, writes
nothing, creates no directory, needs no opt-in and changes no case's count — so
the owner can look at the plan as often as they like before the run and between
the two.

## What this note is not

It is not a second rule. If any statement here disagrees with the code, the code
is what the run follows and this note is a defect to fix before the run, not after
it. It is not part of the frozen trees: it is a document under `docs/`, and
`git diff --quiet freeze-2026-10-03 -- tribunal prompts policy` is unaffected by
it.
