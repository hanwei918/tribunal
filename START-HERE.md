# Start here — WorkBuddy operating procedure

This is the standing procedure for running a WorkBuddy task on this project. It is not day-one
onboarding, and there is no prompt to copy.

## Working directory

Every task runs in `/Users/hanweizhou/Desktop/Tribunal`, and **every task begins by reporting the
actual working directory**. If the reported directory is not that path, stop and say so instead of
continuing.

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
  case file carries its own commit and prompts digest; each invocation's record is appended to
  `invocations.json`.

Run over the cache, the check reports **12 of 29 results stale** — cases 201 through 212, the
NO_SHOW cases carrying a GPS trace, which are exactly the ones the two brief changes could move.
The whole 29-case set was produced at one commit, `a11285b`, between 15:48 and 17:19; `95f0b74`
landed at 17:45 and `d06d2ff` at 18:57, so the code moved on underneath a finished run rather than
while it ran. Every cached digest matches a committed version of the brief.

**That count holds only under the interpreter that produced the cache — Python 3.9.6 here.** The
brief carries an unrounded mean distance, and `sum()`'s float semantics changed in Python 3.12, so
the same cache reads as 12 stale under 3.9.6 and 21 under 3.13.12. **`brief_sha256` is therefore
not a function of the repository alone**, and the check is only sound when run under the
interpreter that produced the result. Recorded as an open defect in the note and not fixed there:
making the float version-stable changes the brief, and so changes what every cached result means.

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

## Session records

- Screenshot each session into `docs/buddy-log/` and record it as a row in the table in
  `docs/buddy-log/README.md`.
- Name screenshots with the pattern already in use: `YYYY-MM-DD-hanwei-NN-<slug>.png`, where `NN`
  continues that day's sequence.

## Where the current state is recorded

- Sessions and screenshots: `docs/buddy-log/README.md`
- Credits: `docs/notes/CREDITS.md`
- Data contract: `data/PUBLIC-CONTRACT.md`
