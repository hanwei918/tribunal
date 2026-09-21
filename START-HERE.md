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

## Policy values

- **Policy values are read from the loaded policy and never hardcoded in application code.** No
  radius, dwell minimum, accuracy filter, distance threshold, fee or rate may appear as a literal in
  `tribunal/`. Thresholds are passed in by the caller, from `policy/no_show.json` under
  `fee_schedule` and `policy/route_deviation.json` under `fare_model`.

## Session records

- Screenshot each session into `docs/buddy-log/` and record it as a row in the table in
  `docs/buddy-log/README.md`.
- Name screenshots with the pattern already in use: `YYYY-MM-DD-hanwei-NN-<slug>.png`, where `NN`
  continues that day's sequence.

## Where the current state is recorded

- Sessions and screenshots: `docs/buddy-log/README.md`
- Credits: `docs/notes/CREDITS.md`
- Data contract: `data/PUBLIC-CONTRACT.md`
