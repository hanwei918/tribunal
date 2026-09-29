# The precedent library

2026-09-28. Queue 2026-09-28, task 4. No model call was made.

## What a precedent is, and why it is kept apart

A human reviewer reads a run and closes some of its cases. A **closure** is that
decision: the ruling the person decided, the clause ids they rested it on, and a
short note for whoever reads it next. The library keeps closures, and when a run
asks for it the judge is shown up to three of them that share clauses with the
case in front of it.

**The block is not evidence and it is not policy.** It decides nothing and it adds
no clause; the note that travels with it says so in its own words, and a test
asserts the note is fixed text in code rather than something a run composes.

The reason this material is kept apart from the headline figure is not modesty.
The library is built from closures made by people who have **seen these
development sets**, so a case the library holds a closure for is material the
system has been shown before. A run with the block on is therefore a different
measurement, and every place its figures are printed says so.

## The store

`precedents/precedents.jsonl`, in a new top-level directory beside `runs/` and
`policy/`. It is **append-only and hash-chained**, and it reuses
`tribunal.events.EventLog` rather than growing a second append-only format: that
class already reads its tail off disk when it opens, so a second closure
continues the chain instead of restarting it, and `events.verify_chain` already
names the first line that was touched. One `closure` event per entry.

The path is a **parameter with the repository's own path as its default**, per
the queue's rule 7. `precedents.store_path(store=None)` resolves the repository's
directory; `Library.load(store)` and the CLI's `--store` take another. Every test
points it at a temporary directory.

An entry carries eleven fields:

- `precedent_id` — `P-0001`, `P-0002`, … Four digits, because a library that
  needed a fifth would already be a different kind of artefact.
- `source` — the set, the `case_no`, the `dispute_id`, the repository-relative
  run directory and the sha256 of the closed case file. The **set is derived from
  the run directory's own path**, not from the case file's `development_set`,
  because a schema-1 file has no such field and a closure must still be able to
  say which set it came from.
- `category`, `clause_ids`, `amount_contested_sgd`.
- `system_outcome` — the four graded fields the system produced.
- `decision` — the four graded fields the human decided.
- `summary` — at most 300 characters. A summary is a note to a human, not a
  ruling.
- `closed_by`, `policy_version` (from the case file's `configuration`, or 1), and
  `supersedes`.

**A field name an entry may never carry** is any of `loader.FORBIDDEN_KEYS` plus
`rationale`, `difficulty`, `governing_clauses`, `matched`, `expected` and
`grade`. The walk is recursive, so the name is refused wherever it sits rather
than only at the top level — an entry cannot smuggle an answer into a store that
a later task might read back into a brief.

The repository ships `precedents/README.md` and **no entries**. There is no
`precedents.jsonl` in it, and a test asserts the directory holds the README and
nothing else.

## What the module may read

`tribunal/precedents.py` is a module under `tribunal/`, so it may name no path
under `eval/`. It reads a run's case file for **five fields and no others** —
`case_no`, `ruling`, `brief_sha256`, `development_set` and `configuration` — and
it never reads `matched` and never reads `events.jsonl`.

The category, the dispute id and the contested amount come from the **rebuilt
brief**, which is built from the case and the policy. So the answer-bearing half
of a run is never opened: a closure is made against the same brief the run was
measured on, and a brief that does not rebuild to the recorded `brief_sha256` is
refused rather than closed.

## Closing a case

    python3 -m tribunal.precedents close --run-dir DIR --case N --ruling R
      [--amount A] [--driver-compensation B] [--referral TEXT]...
      --clause ID [--clause ID]... --closed-by NAME --summary TEXT
      [--supersedes P-xxxx]

It refuses when the case file is absent; when the brief does not rebuild to
`brief_sha256`; when the ruling is not in the loaded POL-GEN-03 `licenses`; when
the ruling is `ESCALATE`, which is the absence of a decision rather than one;
when an amount is not a decimal with at most two places; when a clause id, or a
referral's leading clause, does not resolve in the case's policy; and when the
case already has a closure and `--supersedes` does not name that case's latest
entry. Each refusal has a test, and each names the case it refused.

`list` prints the entries and `verify` checks the chain. Both were run against
the shipped, empty store: `list` prints `the library is empty`, `verify` prints
`the chain is intact … (0 entries)`, both exit 0, and **neither creates the
file** — reading tolerates an absent chain.

## What the judge sees

`--precedents` is on both runners and off by default. When it is on and at least
one precedent matches, the judge's user message carries a `precedents` key, in
canonical position between `claims` and `referee`.

The key holds the fixed `note` and up to three `items`, and an item carries
**exactly four fields** — `precedent_id`, `category`, `clause_ids`, `ruling`.
**No amount and no summary travel in the block**: a figure in it would be a
figure to copy, and a summary is prose about a different case. Two tests hold the
shape, one of them asserting the four field names rather than counting them.

When nothing matches the key is **absent**, not empty, so a run whose library
matched nothing produces the judge message it would have produced with the switch
off — byte for byte, which a test asserts.

The judge's system prompt is **not edited**. What the block is, and what it is
not, is said in the block itself.

Whenever the key is present, the parsed judge message is walked for a forbidden
key at runtime. The library refuses its own names when it writes an entry, but
the judge's message is a bundle boundary and the control is asserted at it rather
than trusted to the writer.

## The matching rule, step by step

Matching is deterministic, and its rule is written down in `matches`'s docstring
so a reader can check each step against the code:

1. the latest entry per source case;
2. entries of the same category;
3. everything except the case being judged, matched by set and case number and,
   separately, by `dispute_id`;
4. entries whose clause ids **all** resolve in this case's brief — an entry
   resting on a clause this case's policy does not hold is not a precedent for
   it;
5. entries sharing at least one clause with a claim the referee **kept**, scored
   by how many. The kept set is sorted and de-duplicated, so the score is a
   function of the claims and not of the order they arrived in;
6. ties broken by the relative amount difference, `|a−b|/b` in `Decimal`, where
   `b` is this case's `amount_contested_sgd`; when `b` is zero or null, by
   `|a−b|`; then by the earlier entry;
7. the top three.

A clause reference is reduced to its **base id** before matching, so
`POL-RD-02(a)` and `POL-RD-02` are the same clause for this purpose. Each step is
exercised on its own, and the choice is asserted to be the same under a shuffled
store.

## Where a precedents run writes

    runs/precedents/<model>/            the corpus
    runs/codex/precedents/<model>/      the second development set

One rule applied to whatever runs root the run was given. `runs/<model>/` holds
the 29-case figure the submission reports, and a result whose judge saw a
precedents block is a different measurement; one written there would change what
that directory means while leaving every file a reader looks at apparently
intact. `run_benchmark.assert_precedents_destination` refuses a directory that is
not under `<runs root>/precedents/`, and the guard is seen to fail on a dirty
fixture before it is seen to pass.

`--precedents` is refused together with `--ablate` — the queue's rule 6, one
switch per invocation — and with `--replay-advocates`, `--replay-check`,
`--verify-recorded-drafts` and `--external`, because every one of those reads or
produces a run whose judge saw no block.

## The third staleness channel

A run with the switch on records the library in its `configuration`: the
**chain head** and the **sha256 of the fixed note**. The note digest is there
because the note is part of what the judge was told, and a change to it changes
what a result measures.

A cached case whose recorded chain head is not the current one is **stale**, on a
third channel named `precedents` beside `brief` and `prompt`. The channel is
silent rather than empty when the switch is off, which is what keeps a plain
run's staleness reading exactly what it was.

**Stale is a finding, not an action.** A stale cached result is reported and
**reused** — the same rule the brief and the prompt channels already follow — and
`--force` is what runs it again. The queue's line 426 says such a case "is stale
and is re-run"; the code does not re-run a stale cached case on any channel, and
three of this repository's own documents say that is deliberate:
`docs/notes/2026-09-28-the-ablation-switch.md` has an ablated set's second
invocation reusing the cache and asking the transport for nothing,
`docs/notes/2026-09-22-stale-cached-results.md` has the reused result's progress
line naming which digest moved, and
`docs/notes/2026-09-24-replaying-the-advocates.md` calls "a cached case is reused
rather than re-run" the ordinary rule. **This task joins that rule rather than
replacing it**, and the reading was put to the repository's owner and confirmed
before the test was written. The test asserts both halves: the case reads stale
and names the channel, and the re-run that follows it makes no call — with
`--force` shown to make the call instead.

## Reporting

`report.md` and the printed summary leave out **every case that is the source of
a library entry**, and list them. `invocation_end` records them. A source case is
material the library was built from, so a figure over it is not a figure about
this system on this case.

Both state that figures with precedents on are **not comparable to the
headline**, for the reason at the top of this note. A test asserts the sentence
is present in the report and in the printed summary.

## What finishing this task corrected

The implementation was in the working tree when this session picked it up, and
four things were wrong in it. All four are the same kind of mistake — a second
channel added to a place that knew two — and all four are now fixed:

1. **The runtime-boundary test used the wrong forbidden name.** It spliced
   `matched` into a block and expected the walk to refuse it. `matched` is a
   *precedent-vocabulary* name, refused by the library when it writes an entry;
   the walk at the judge's message knows the five `loader.FORBIDDEN_KEYS` and
   nothing else, so it passed the block through. The fixture now splices
   `ground_truth`, which is a name the boundary actually refuses.
2. **The progress line had no phrase for the third channel.** `_STALE_PHRASES`
   named the brief and the prompts, so a library-driven staleness fell through to
   the fallback — `produced by an earlier version of this code` — which is true
   of a moved brief and **false of a moved library, because the code did not move
   at all**. There is now a phrase for each of the three, and a test compares the
   whole set of `grade.MOVED_*` names against the phrase table, so a fourth
   channel cannot be added without one. The guard was seen to go red with the
   precedents phrase removed.
3. **The printed summary named two channels.** It printed `brief moved:` and
   `prompts moved:` and stopped. It prints `library moved:` too.
   **Correction, 2026-09-29.** The line could not print. `print_summary` had
   printed `library moved:` since it was written, but `brief_staleness` never
   collected the channel — `stale_precedents` was left `()` however far the
   library had moved — so neither that line nor the `The precedent library has
   moved for N of M` line in `report.md` was reachable. The field is filled now,
   and a test walks a case whose only change is the library through both.
4. **Two documents claimed a stale case is re-run.** `grade.py`'s comment on
   `MOVED_PRECEDENTS` said "the case is re-run", and `runs/README.md` said a
   cached result produced against an earlier library "is re-run rather than
   reused". Both now state the rule the code actually follows.

A fifth correction is in the test the queue asked for: it asserted a re-run, and
now asserts the staleness *and* the reuse, with `--force` as the re-run.

## What was run

- `python3 -m unittest discover -s tests` on 3.13.12, once, on a tree that was
  not written to while it ran — `Ran 1343 tests in 3710.620s` /
  `FAILED (failures=1, errors=1, skipped=4)`. **Both of those results are this
  session's sandbox and not the code**, they are quoted in the section below, and
  no code was changed for them.
- Discovery count `1343` against `1343` occurrences of `^\s+def test_` over
  `tests/*.py` — up from 1200, and up from the 1249 task 3 left. This is the only
  guard against a test that never runs.
- `python3 -m ui.build --check` — identical to a fresh build at 2371908 bytes.
  The switch changes no brief with the block off, so the committed page is
  unchanged.
- `python3 -m tribunal.precedents list` and `verify` against the shipped store —
  both exit 0, neither creates the file.
- Credential scan of the changed and new files with the pattern
  `sk-[A-Za-z0-9_-]{8,}`: no match, with a positive control that fires on a
  fabricated `sk-` string and the house fake `tok-live-FAKEKEY-…` that does not.
  A CJK scan of the same files found none, with a control that fires.
  `TOKENHUB_API_KEY` and `TOKENHUB_API_KEY_TEAMMATE` are both unset in the shell
  that ran the scan, so the literal-value half of the check was not made there
  and is not claimed here.

## The two results the sandbox caused

The run above reports one error and one failure, and **neither is the code's**.
Both are one refused write. This session's Python runs inside WorkBuddy's own
sandbox, whose `sitecustomize` shim brokers filesystem calls; a `mkdir` under a
temporary directory the shim's path policy denies is refused with

    PermissionError: Brokered mkdir refused by resolved path policy: deny

raised at `tribunal/events.py:335`, in `EventLog.record`'s

    self.path.parent.mkdir(parents=True, exist_ok=True)

by way of `sitecustomize._brokered_path_mkdir` and
`sitecustomize._broker_request_host_operation`. The two results both follow from
it, and neither is about the thing it names:

- **ERROR — `tests.test_run_benchmark.ReplayTests.test_the_report_says_the_advocates_were_replayed_and_from_where`.**
  The replay's run directory cannot be created, so the invocation ends on the
  refused `mkdir` rather than on anything it measured. The traceback runs
  `test_run_benchmark.py:4372` → `_replay` → `bench` → `run_benchmark` →
  `events_log.record` → `mkdir`.
- **FAILURE — `tests.test_run_benchmark.ResumptionTests.test_a_case_not_yet_cached_is_the_only_one_run`.**
  It asserts that a re-run retries exactly the case that failed, and reads
  `[102] != [101, 102]`. Case 101's result could not be written to the cache for
  the same refused `mkdir`, so the re-run finds two cases uncached and runs both.
  The assertion is about a cache that was never written, not about the resumption
  logic.

Run outside this sandbox, `tests.test_run_benchmark.ResumptionTests` and
`tests.test_run_benchmark.ReplayTests` — 38 tests — pass on both 3.11.14 and
3.13.12. **No code was changed for either result.** The remaining 1341 results of
this run are clean, four of them the workspace's own skips, so the run is
evidence for everything except the two tests above.

The 3.9.6 half of the pair was stopped rather than spending another hour
reproducing the same two sandbox results on a second interpreter: the full suite
is the owner's to run outside the sandbox, and from task 5 on the working check
is the related modules on 3.13.12.

## What is not done

**No precedents run was made**, so `runs/precedents/` does not exist and nothing
is committed there. The library ships empty, so a run made today would show the
judge a block for no case; the commands that would produce one are the two in
`runs/README.md`.

The queue's rule 6 says at most one of `--ablate`, `--precedents` and
`--policy-version N≥2` may be given per invocation. Task 3 built half of that
leg — `--ablate` refusing the modes it could see. This task builds the second:
`--ablate` and `--precedents` are refused together. The third leg arrives with
task 5.
