# Concurrent calls, and the replay that proves nothing sent to a model changed (2026-10-06)

The task sheet dated 2026-10-06 asked for four things: make the advocates and the
judge's drafts run concurrently behind an opt-in switch, prove with an offline
replay that no byte of any request changed, correct three documents, and add a
no-leakage guard. **No model call was made in any part, and no browser was
launched.** Each part is its own commit.

Why it was worth doing: a case takes about seven minutes today -- the mean over
`wild-v2` was 429.6 s -- and the two advocates and the four judge drafts are
called one after another although none of them depends on another. The rider and
the driver read the same brief; the three sampled drafts and the
position-swapped draft read the same referee result.

## A. Concurrent calls, opt-in

**The switch, and where it is not.** `--parallel-calls` was added to
`eval.run_benchmark` and `eval.development_sets`, and a `parallel_calls` keyword
runs through `run_set` and `run_benchmark` into `run_case`. The default is the
sequential path, so every existing test keeps its meaning. The setting is
recorded in the run's `invocation_start` event and in `run.json`, and it is
deliberately **not** part of a case's `configuration` object: it is not a
property of a case, it is not a staleness key and it is not a cache key, because
it changes no request. Three tests hold that: the configuration object does not
carry it, `run.json` and the `invocation_start` event name it only when it is on,
and two parallel runs write the same call order.

**The pipeline was split, not rewritten.** `_call_agent` became two parts. The
worker part runs the two-attempt loop, the deadline check and `client.complete`,
touches neither the transcript nor the event log, and returns each attempt's
result with its own timestamp, the final value and reason, and any exception --
caught and stored. The main-thread part writes each attempt to the transcript and
the `agent_call` event in attempt order, exactly as before, and then returns or
re-raises the stored exception. `_call_agent` is the two parts run in sequence,
so every existing caller is unchanged.

The advocates run in a pool **private to that call site**, two workers wide, and
both are waited on before either answer is written down. The judge's draft
messages are built in position order in the main thread and then asked in a pool
private to the vote, `votes` workers wide, and all of them are waited on before
any is recorded. Neither ever submits to, or waits on, the pool that holds the
cases: submitting a call to that one from inside a case would deadlock the moment
every worker was already inside a case.

**The order is the case's order, not the network's.** Every answer is written to
the transcript and its `agent_call` or `judge_draft` event recorded in the case's
own order -- rider before driver, drafts in position order. `Transcript.add` and
`record` gained an optional `timestamp=` so an entry keeps the time its call
finished rather than the time it was written. The verifier, the vote reduction
and the `vote` event stay sequential and unchanged, and so does the K = 1 judge
path. `calls.json` is now sorted into a deterministic order -- case, then role,
then draft -- where before it was in completion order.

**The one behaviour change, and it is deliberate.** When the two advocates run
concurrently and the rider's call fails, the driver is still called and its
answer is still recorded, so the cost the run reports is the cost it actually
incurred; the case still names the rider as `failed_agent`. Sequentially, a failed
rider stops the driver from ever being asked. This is the only intended
difference between the two modes.

**Rate limiting is untouched.** The per-client limiter keeps capacity 1, its one
request a second, and the same names and shape (`_respect_rate_limit`,
`_last_request_at`, `_minimum_interval`); no process-wide registry keyed by model
was added, because test clients use virtual clocks and reuse model names and such
a registry would leak state between tests. With `--concurrency N` up to `N × 4`
requests queue behind the limiter at one a second.

**Tests, shown red first.** A routed transport answers by request -- role, seed,
temperature and the draft's sides -- with a per-key FIFO for shape retries; the
older positional tests stay sequential. Four behaviours are asserted by driving
the pipeline: the two advocates overlap and are still written rider then driver,
under real overlap (the rider's answer is held until the driver's request has
arrived); the advocate events are rider then driver; the drafts overlap and are
written in position order; a worker exception propagates after the join with the
earlier attempts written; and a failed rider no longer stops the driver, with
`failed_agent` still the rider. Both new classes were shown red before the
production change existed -- `run_case` and `run_benchmark` refused the keyword,
8 errors and 5 errors -- and both pass with it. The ordering guards were then
shown to bite by mutating `run_loaded_case` to write the driver first and
`_run_judge_vote` to iterate the drafts reversed: three failures, with
`pipeline.py` restored byte-identical afterwards.

## B. The proof: the offline replay

`tests/test_offline_replay.py` makes no model call. It loads every recorded run
committed under `runs/` and serves each recorded `response_text` back through a
transport, in a synthetic envelope carrying the recorded usage numbers, so a full
arbitration runs again with no provider in the loop.

The transport keys a request by `(sha256(system), sha256(user), temperature,
seed)`. The two settings are the draft's own for the entries a draft occupies --
read from `vote.drafts[].temperature`, `seed` and `entries` -- and the client's
defaults, 0.0 and 42, for every other entry. Recordings are read with
`parse_float=Decimal`, so a draft's temperature comes back as `Decimal("0.7")`
while the same setting inside a request body is the float `0.7`; the key puts
both through their own shortest decimal text, because `Decimal("0.7") != 0.7` in
Python and a key that compared them as they stand would find no recording for any
sampled draft at all.

All four recorded sets are replayed: the corpus's 29 cases, the second
development set's 15, the held-out set's 64 -- the two cases that produced no
ruling among them, which must still fail at the judge with the same vote -- and
the second sealed set's 20, at its own policy version 2. Each case runs twice,
sequentially and with `parallel_calls` on, under a pinned `now` and a clock
pinned at zero.

The assertions are: every transcript entry equals the recording, field for field,
with only `timestamp`, `duration_seconds` and the replay note normalised; the
ruling, the vote, the referee ledger and the brief digest equal the recording; no
request goes unanswered and no recorded answer is left unused; the request-body
digests the replay computes include every digest in each run's `calls.json`; and
the parallel run's `events.jsonl` is byte-identical to the sequential run's.

Three negative controls show the check biting: advocates written in completion
order (driver first), the seeds of drafts 1 and 2 exchanged, and the judge's
temperature moved off 0.7. Each is a test that fails if the replay stops
reporting the change.

Two things had to be got right while writing it, and both are the kind of thing
that makes a comparison silently wrong. The first is the `Decimal`/`float`
boundary: a value this run computes in memory can hold a `float` where the same
value, read back from a recording, holds a `Decimal` -- the vote's `agreement` is
one, because the pipeline divides two integers -- so both sides of the vote, the
ruling and the referee comparisons are put through the canonical serialiser and
read back the way a recording is read. The second is that a comparison is not
allowed to be about the wrong thing: the no-ruling cases' votes are normalised
the same way rather than compared raw.

## C. The documents

**The README** gains a `## Concurrency` section between "How it works" and the
repository map. It says what overlaps, that the switch is opt-in and where the
setting is and is not recorded, that every answer is still written in the case's
own order, that the rate limiter is unchanged and up to `concurrency × 4`
requests queue at one a second, the one behaviour change from part A, and what
the offline replay proves. It also carries the estimate, labelled as an estimate:
from the recorded durations a case should drop from roughly the sum of its calls
to roughly the longest advocate call plus the longest draft. The estimate is not
a measurement; the owner will measure it. The repository map's `precedents/` row
said the library was "empty until a reviewer closes one", which stopped being
true when P-0001 and P-0002 were closed, and now says what it holds.

**`policy/amendments/README.md`** said the directory "ships **empty**" and that
"the policy as committed is version 1". Both were true until 2026-10-01 and
neither is now: the directory holds `0001-pol-rd-13` and the repository is at
**policy version 2**. The file now says so, and adds the thing a reader needs to
know about it: **this README is not read by the loader.**
`policy_versions.amendment_files` skips `README.md` by name before it applies the
`NNNN-<slug>.json` rule, so the version a run measures is decided by the
amendment files alone -- which is why correcting this file changes no brief
digest and no recorded `brief_sha256`. `git diff --stat freeze-2026-10-03 HEAD --
prompts policy` shows this file and nothing else, which is the same statement made
against the freeze.

**`precedents/README.md`** said "This directory holds no entries today." It holds
two: `P-0001` closes case 508 on a `PARTIAL_REFUND` of 6.00 and `P-0002` closes
case 530 on a `PARTIAL_REFUND` of 5.80, both read from the held-out set's run and
both under `POL-RD-01`, `POL-RD-02` and `POL-RD-08`. The file now says so.

**`prompts/v1/judge.system.md` was not edited.** Its `referee_ledger` /
`referee_flags` naming stays a known defect, because changing the prompt would
change every request, and no byte sent to a model may move.

## D. The no-leakage guard

`tests/test_no_leakage.py` walks `prompts/` and `policy/` -- the only two trees
the agents are briefed from -- and looks for four kinds of case identifier: case
file stems `case-NNNNN`, `dispute_id` values, trip ids, and evidence ids of the
form `EV-<KIND>-<digits>`. The tokens are **built, not typed**: from the registry
(`eval.development_sets.BY_NAME`, every development, sealed and re-run set), and
from each set's own index, its own answer key and its own cases. Each kind is
asserted non-empty, so a harvest that silently stopped working fails instead of
passing by finding nothing to look for. Bare numbers do not count -- every pattern
carries its prefix, which is why the policy's own fees and the corpus's own case
numbers do not match.

A failure prints the file and the kind of token and nothing else, never the token
and never the line it sat on, because this module's output is committed. The
format is pinned by a test.

**The guard found a real leak.** The check is red on the committed tree, and not
because of a mistake in the check: the advocate template's worked example cites
`EV-GPS-00208`, which is a genuine evidence id of corpus case 208. The repository
has made this mistake once before and fixed it once -- the verifier prompt's
worked example was rewritten to invented placeholder ids (`EV-DEMO-00042`,
`EV-DEMO-00051`) precisely so that no real identifier appears in a prompt -- and
the advocate template was never brought into line.

It is **not fixed here**, for the same reason the judge prompt's naming defect is
not fixed: the advocate template is sent with every request, so editing it changes
every request, and the whole point of part A is that no byte sent to a model
moved. Instead the violation is named and pinned in the module: `KNOWN_VIOLATIONS`
holds exactly this one finding, one test asserts it is the *only* finding -- so a
new leak fails -- and another asserts it is *still there* -- so a fix cannot leave
the pin behind covering whatever comes next. Removing the pin is the first thing a
reader should do after the example is rewritten to an invented id. The check is
also shown red on a dirty fixture: a copy of the real tree with one identifier
spliced into one file is reported with that file and that kind.

## Finish

The ten modules the task names, run together on an idle machine:

    python3 -m unittest tests.test_pipeline tests.test_transcript tests.test_events \
      tests.test_llm tests.test_run_benchmark tests.test_development_sets \
      tests.test_offline_replay tests.test_no_leakage tests.test_readme_figures \
      tests.test_language

`Ran 685 tests in 2783.577s` — **`OK (skipped=3)`**. No test in it makes a model
call.

**The offline replay's per-set results**, both modes, 128 cases each replayed
twice. The two columns that matter are the last three: nothing left over, nothing
unanswered, and no digest in the run's own `calls.json` left unreproduced.

| set | cases | ruled | recorded answers served | left over | unanswered | `calls.json` digests not reproduced |
|---|---|---|---|---|---|---|
| corpus | 29 | 29 | 177 | 0 | 0 | 0 |
| codex | 15 | 15 | 91 | 0 | 0 | 0 |
| wild | 64 | 62 | 392 | 0 | 0 | 0 |
| wild-v2 | 20 | 20 | 124 | 0 | 0 | 0 |

Each row is identical in both modes, and the two `wild` cases that ruled nothing
are 517 and 533, still failing at the judge with the same vote.

**The viewer is untouched and rebuilds to the committed bytes.**
`python3 -m ui.build --check` reports each of the six pages identical to a fresh
build — 2414270, 1155598, 4243482, 1430248, 279546 and 31639 bytes — which is
what should happen when no recorded run changes.

**The trees a run reads.** `git diff --stat freeze-2026-10-03 HEAD -- prompts
policy` prints exactly one file, and it is the one this task was allowed to
correct:

    policy/amendments/README.md | 11 ++++++++++-
    1 file changed, 10 insertions(+), 1 deletion(-)

So no prompt moved and no policy JSON moved, and every recorded `brief_sha256`
still rebuilds. `git diff --stat freeze-2026-10-03 HEAD -- tribunal` shows
`tribunal/pipeline.py` and `tribunal/transcript.py`, which is where part A's work
is.

**The four commits**, each its own part, with its own buddy-log row beginning
`Parallel calls: <part>`:

| part | commit |
|---|---|
| A — concurrent calls, opt-in | `364877b` |
| B — the offline replay | `fcd68ea` |
| C — the documents | `283a89f` |
| D — the no-leakage guard | `c416dc6` |

**One deviation, recorded rather than smoothed over.** The task sheet says the
no-leakage check is "shown red on a dirty fixture", which reads as a clean tree
that the check passes. The tree is not clean: it holds one real violation, in a
frozen prompt, and part D pins it rather than fixing it. The check is therefore
green *with the pin* and red without it, and both states are shown above.
