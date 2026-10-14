Development procedure for the WorkBuddy sessions that built this repository. The project is described in README.md.

# Start here — WorkBuddy operating procedure

This is the standing procedure for running a WorkBuddy task on this project. It is not day-one
onboarding, and there is no prompt to copy.

## Working directory

Every task runs in the repository root — the directory holding this file, `.` — and **every task
begins by reporting the actual working directory**. If the reported directory is not the repository
root, stop and say so instead of continuing.

## Before acting

1. Read `WORKBUDDY-SCOPE.md` first, on every task. It is the read boundary.
2. State the file paths you plan to open, before opening anything.

## The shape of a task

- **One acceptance-ready module per round.** Finish and verify one module; do not regenerate the
  whole project.
- **Read only the files listed for that round.** Do not scan the workspace recursively, and do not
  read anything outside it.
- **Report what actually happened**: the files created or changed, the commands actually run, and
  the real verification output, copied as-is.
- **Never describe work that was not done.** If something was not run, say plainly that it was not
  run.

## Testing

- Run the tests and paste the real output, including the test count.
- **A failing test is reported as a failure.** Never work around a failure by weakening, deleting or
  loosening the test to make it pass. If a test encodes a wrong expectation, say so and show the
  value you computed instead.

### Never prove a structural property with a string search

This corpus is mostly natural language. Policy clauses, admissibility notes and party statements
discuss field names, punctuation and numbers as ordinary text. **Never use a string or substring
search to prove a structural property. Assert on the parsed structure instead.** Two tests have
already failed this way: asserting the absence of `": "` tripped on policy prose that contains
colons, and asserting the absence of `rider_track` tripped on a clause that discusses the field by
name.

### The answer key is frozen

The answer key is frozen. If an agent's ruling disagrees with
`eval/answers/ground_truth.json`, the answer does not change. Investigate
the agent, the prompt, the policy or the brief. Editing the expected result
so a run scores better destroys the only independent measurement this
project has, and it will be destroyed quietly, under deadline pressure, by
someone who believes they have found a genuine error in the key. If the key
really is wrong, the correction is a separate commit that changes only the
key, states the evidence in its message, and is made before the run it would
affect — never after.

### A verdict is not evidence

A verdict is not evidence. When a run reports a failure, read what the model actually returned and
what the answer key actually says before believing the label. Three defects in one day were invisible
in the verdict and obvious one level down. The same applies to a number that looks bad: check what set
it was computed on before drawing a conclusion from it.

All three were ours rather than the model's, and each was visible in exactly one place:

- the `json_object` contradiction that made the advocate contract impossible to satisfy — visible in
  the raw `response_text`, where 27 fully cited claims had been discarded for their wrapper alone;
- the referral rule that scored a correct answer to case 207 as a MISS — visible in the key's own
  rationale for that case, which names the clause the model was penalised for adding;
- the escalation rate printed beside a corpus target it could not be compared to — visible in the size
  of the graded set, which the report never stated.

A fourth kind is worth naming separately, because the verdict gives no hint of it: **a fact the brief
never computed**. `deepseek/deepseek-flash` ruled FULL_REFUND on case 214 where the answer is
DRIVER_COMPENSATION, and every number it was given was correct — it was simply never told that
POL-NS-06(i) permits two separate holds to be added. The model could not see what we never calculated.
When a case is missed, check what the brief *omitted* as well as what the model did with what it had.

See `docs/notes/2026-09-22-advocate-output-contract.md`,
`docs/notes/2026-09-22-evaluation-layer-two-defects.md` and
`docs/notes/2026-09-22-accumulated-dwell.md`.

### A cached result is evidence about the code that produced it

Every cached case records the digest of the exact brief bytes its agents were handed, so it can be
checked against the brief the code builds now. **That check is now made whenever a cached result is
read, and it is not decoration.** The cache under `runs/` held results produced by more than one
version of the brief and nothing said so: `--compare` tabulated all of them as one run, and a
single-case re-run had replaced the 29-case run's own `run.json`, so the commit and the case list
that produced those results existed nowhere afterwards.

Two rules follow, and both are enforced in code:

- **A result the code has moved past is labelled, not discarded.** It is a real measurement and it is
  evidence — of what an earlier version of the brief did. Deleting it destroys the record of the
  change.
- **Provenance that lives only in a file the next invocation overwrites is not provenance.** Each
  case file carries its own commit, prompts digest and interpreter; each invocation's record is
  appended to `invocations.json`.

Run over the cache, the **brief** channel reports **12 of 29 results stale** — cases 201 through
212, the NO_SHOW cases carrying a GPS trace, which are exactly the ones the two brief changes could
move. The whole 29-case set was produced at one commit, `a11285b`, between 15:48 and 17:19;
`95f0b74` landed at 17:45 and `d06d2ff` at 18:57, so the code moved on underneath a finished run
rather than while it ran. Every cached digest matches a committed version of the brief.

**The check reads two digests and reports which of the two moved.** A moved *brief* means the facts
the agents were handed changed; a moved *prompt* means their instructions changed. They call for
different responses, so no report merges them into one word: the per-case cell reads
`**STALE (brief)**` or `**STALE (prompt)**`, and the progress line names the digest that moved. The
**prompt** channel can be answered for three of the cached results — cases 101, 102 and 103, which
the 2026-09-22 re-run rewrote after the field existed — and the other twenty-six are `unknown`
there rather than `current`. `unknown` is not `current`, and `current` is not a standing property
either: the note's block read `current=3` while those three agreed with the directory, and it reads
`current=0` now that the judge prompt has been amended. Fifteen results are stale — twelve on the
brief channel and three on the prompt channel. The prompt set has in fact already moved three times:
the run records carry two different digests, three per-case entries carry a third, and none of them
is what the directory hashes to now.

**That count is the same under any interpreter now, and it was not always.** The brief carries an
unrounded mean distance, and `sum()`'s float semantics changed in Python 3.12, so the same cache
used to read as 12 stale under the 3.9.6 that produced it and 21 under 3.13.12 —
**`brief_sha256` was not a function of the repository alone.** `facts._sum_in_order` now sums left
to right with no compensation, which is what 3.9's `sum()` already did, so the brief is
interpreter-stable and the check agrees with itself wherever it runs. The repair was measured
before it was made and changes no byte of the existing cache under 3.9.6. The interpreter is
recorded per case beside the commit and the prompts digest, and the comparison table names it when
it differs, so a digest that disagrees can be read against the interpreter that produced it.

An earlier version of this section reported 21 stale and nineteen digests matching no committed
version. The nineteen was simply wrong. The 21 was this same check run under the wrong
interpreter — which is why it turned out to be reproducible once the interpreter was suspected,
and why "unreproducible" was the wrong thing to write about it.

See `docs/notes/2026-09-22-stale-cached-results.md`.

## Policy values

- **Policy values are read from the loaded policy and never hardcoded in application code.** No
  radius, dwell minimum, accuracy filter, distance threshold, fee or rate may appear as a literal in
  `tribunal/`. Thresholds are passed in by the caller, from `policy/no_show.json` under
  `fee_schedule` and `policy/route_deviation.json` under `fare_model`.
- **A policy value that exists only as clause prose is still a policy value.** POL-RD-01's four
  deviation lines, POL-NS-06's leash and its four admissible `traffic_advisory.type` values, and
  POL-NS-05's motion line are all stated in a clause's `rule` text and nowhere as a field. They are
  read out of the loaded clause and the reader **raises** if a line cannot be found. A fallback
  constant would be a policy number hard-coded in `tribunal/`, which is the thing this rule forbids.

## Bounds on time

Two limits are in force and they are not the same limit. Neither existed before 2026-09-22, and the
defect was found by measurement rather than by reading: a real run wrote its last case at 07:25 and
was still alive at 09:13 with no output, 1 h 48 m, while a direct probe of the endpoint answered
HTTP 200 in 0.95 s.

- **`llm.DEFAULT_TOTAL_DEADLINE_SECONDS` = 1200 s** bounds one **call**: every attempt and all
  backoff. `llm.DEFAULT_TIMEOUT_SECONDS` = 600 s bounds one **attempt**, and `max_attempts` = 4
  multiplies it, so without the second limit the product is about 40 minutes for a single call.
- **`pipeline.DEFAULT_CASE_DEADLINE_SECONDS` = 2400 s** bounds one **case**: all three agent calls
  and any shape retry. Without it the worst case is 6 calls x 40 minutes — the 241 minutes that let
  the run sit silent for nearly two hours while it was inside its limits the whole time.

Both are checked **before** the work they bound, not after it. An attempt needs a whole
`timeout_seconds` of remaining budget, so one that cannot finish is refused rather than begun. That
ordering is what keeps a deadline tellable apart from a timeout: beginning an attempt that overruns
would surface as a `TimeoutError`, which is a different event with different advice. Both defaults
are derived from measurement — 1200 s is two full attempts, because the 605.8-second TIMEOUT failure
shows a real attempt does consume the whole per-attempt timeout; 2400 s clears the slowest case
actually seen (978.8 s) and the three-full-timeout bound (1818 s) while bounding the 241-minute
worst case at 40. The derivation is asserted in the tests rather than the number.

A deadline is its **own failure kind**, `FAILURE_DEADLINE`, beside TIMEOUT, TRANSPORT and SHAPE.
`failure_kind_for` is the single classification point and maps both deadline exceptions to it — the
one raised by the client and the one raised by the case. A case that exceeds its deadline is
recorded as a failed case, named with its elapsed time, and the run continues to the next one. Both
limits are recorded in the run metadata and printed on the summary block, because a `DEADLINE`
failure is only interpretable against the limit that produced it.

**A hang must be visible while it happens.** Each case prints a line when it *starts*, emitted from
the thread that owns the queue and before the work is submitted, so the last line on the terminal
always names what is in flight. The original run's last line named a case that had already
finished, which is why nothing on screen could distinguish a hung case from a long one and the
process had to be probed by hand to find out.

See `docs/notes/2026-09-22-bounded-call-and-case-deadlines.md`.

## Session records

- Screenshot each session into `docs/buddy-log/` and record it as a row in the table in
  `docs/buddy-log/README.md`.
- Name screenshots with the pattern already in use: `YYYY-MM-DD-hanwei-NN-<slug>.png`, where `NN`
  continues that day's sequence.

## Where the current state is recorded

- Sessions and screenshots: `docs/buddy-log/README.md`
- Credits: `docs/notes/CREDITS.md`
- Data contract: `data/PUBLIC-CONTRACT.md`
