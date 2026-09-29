# The ablation switch

2026-09-28. Queue 2026-09-28, task 3. No model call was made.

## What an ablation is

An **ablation** builds one case's brief with one thing removed, so a run with it
on measures the pipeline without that thing. It is the only way to say what a
part of the brief is worth: the headline figure is a figure for the whole brief,
and a part that changes nothing has not been shown to matter.

Two exist, and they are **names rather than flags**:

- `clause-notes` builds the brief with `include_clause_notes=False`. That flag
  already existed; the switch gives it a name a run can record and a directory a
  result can live in.
- `admissibility` removes the `admissibility` object from every artifact.

The name is a path component as well as a record: `runs/ablation/<name>/<model>/`
holds one ablation's results for one model, so two ablations of one model are two
directories and neither can be read as the other's.

## The two ablations, exactly

### `clause-notes`

Every clause's drafting `notes` is removed from the brief's policies. The clause
ids, the `rule` text and the structured fields are unchanged, so a limb still
reads as it read; what is gone is the commentary around it. The ablation is the
existing flag, not a second implementation of it: one test asserts that
`ablate="clause-notes"` and `include_clause_notes=False` produce the same bytes.

### `admissibility`

The `admissibility` object is removed from **every** artifact in the brief, and
nothing else about the artifact changes.

Three things follow, and all three are stated because the tempting summary —
"the ablated brief carries no admissibility information" — is **false**:

- A MISSING artifact keeps its `evidence_id` and its null payload. The ablation
  removes what was *assessed* about an artifact, not the artifact.
- The referee reads an artifact with no `admissibility` object as one with no
  impairment, because it checks with `isinstance`. So a claim that cites an
  impaired artifact without disclosing the impairment is **discarded** on the
  plain brief and **kept** on the ablated one. That is the ablation's effect, and
  it is the thing a run with this switch on is measuring.
- Derived text computed from a null payload still says MISSING. In case 201 the
  limb's own reason reads `EV-ADVIS-00201-01 is MISSING`, and it is computed
  before the strip and survives it.

So the correct statement is: the ablated brief carries no admissibility
**object**, which is not the same as carrying no admissibility information. Both
the note here and `runs/README.md` say it that way, and a test asserts the
module's own note does too.

## It is applied in one place

`tribunal.brief.build_brief_for_case` takes a keyword-only `ablate`, defaulting
to `None`, and applies it there and nowhere else. There is one brief and one
builder: an ablated run is that brief built without part of it, not a second
builder that could drift from the first. `build_brief`'s signature is pinned by a
test and takes no ablation, so it still builds the bytes it always built — and
one test asserts that the two entry points agree.

`clause-notes` is applied by setting the flag the function already had;
`admissibility` is applied **last**, over the assembled evidence rather than
inside any one block, so every artifact is treated the same way whether it came
through the GPS transform, through the money block's attachment, or untouched.

The pipeline threads the name through `run_case` → `run_loaded_case`, which
validates it before the first call and applies it at the single call to the
builder. The brief is still serialised once and those same bytes are still handed
to both advocates and embedded in the judge's message.

## Where an ablated run writes, and why the path is checked

    runs/ablation/<name>/<model>/            the corpus
    runs/codex/ablation/<name>/<model>/      the second development set

The rule is one rule applied to whatever runs root the run was given: an ablated
run goes under `<runs root>/ablation/<name>/<model>/`. `runs/<model>/` holds the
29-case figure the submission reports, and an ablated result is a different
measurement; one written there would change what that directory means while
leaving every file a reader looks at apparently intact.

**The destination is checked, not merely chosen.**
`run_benchmark.assert_ablation_destination` refuses a directory that is not under
`<runs root>/ablation/`, so a name that resolved outside it — `..`, an absolute
path, an empty string — cannot put an ablated result where an unablated one
lives. The test is seen to fail on a deliberately dirty fixture (the plain run
directory, and a name of `..`) before it is seen to pass on the real one.

**Correction, 2026-09-29.** The path above is the path the *runner* chooses, and
for a while the runner was never asked. `eval.run_benchmark`'s `main()` parsed
`--ablate` and never passed it to `run_benchmark(...)`, so
`python3 -m eval.run_benchmark --ablate clause-notes` built **unablated** briefs
and wrote them into `runs/<model>/` — the one directory this section says an
ablated result may never reach, and exactly what the destination assertion above
exists to prevent. The `--precedents` path was the same. Both are named at the
call site now (`2be9ec6`). A run started through `eval.development_sets` was
never affected: it forwards its switches through `run_set(**kwargs)`.

## What an ablated run records

The ablation is written into the `configuration` object of `run.json`, of every
`invocations.json` entry and of every case file — the object task 1 added, which
already had an `ablation` field waiting to be filled. A run without an ablation
still writes `null` there, so the object's shape does not move.

The `invocation_start` event line names the ablation **only when there is one**,
on the same rule the verifier's flag already used: a plain run appends the line
it always appended. A test asserts that the plain line does not contain the word,
and that the ablated one does.

## The staleness check rebuilds the ablated brief

This is the part that would go quietly wrong. The staleness check compares a
cached result's recorded `brief_sha256` against the digest of the brief this code
builds for that case now. An ablated result recorded the digest of an **ablated**
brief, so a check that rebuilt the plain brief would report every case of that
run as stale — a false finding about the run rather than a statement about the
code.

So `current_brief_sha256` and `brief_digest_for` both take the ablation, and
`run_benchmark` builds its checker with it. Both default to `None`, and
`brief_digest_for()` still returns `None` — "use the built-in corpus digest" —
when neither a loader nor an ablation is named, so the plain path is unchanged.

Two tests hold it: one checks the same run directory with the ablated digest
(every case current) and with the plain one (every case stale), which is the
dirty fixture; the other runs an ablated set twice and asserts that the second
invocation reuses the cache and asks the transport for nothing.

## Why replay is refused

`pipeline.replay_verdict` builds the case's brief with no ablation — it must,
because the advocates it reuses were given the unablated brief. A replay of an
ablated run would therefore accept the headline advocates and hand the judge a
brief that is not the one the run is measuring, and the result would look like an
ablated run while being neither one thing nor the other.

So `--ablate` is refused with `--replay-advocates`, `--replay-check` and
`--verify-recorded-drafts` on **both** command lines, each with a test. Two more
refusals belong to one command line each, because each flag exists on one:
`--compare` and `--external` on `eval.run_benchmark`, and `--report` on
`eval.development_sets`, which has neither of those two. Every one of them reads
a run recorded without the ablation. The runner refuses the combination as well,
before it computes the run directory, because that is the layer that would
otherwise create a directory for a run that cannot be honest; and `run_one_case`
refuses it a third time, because that is the layer that would otherwise make the
wrong call.

The refusal happens at the argument layer, before anything is read or written. In
`eval.run_benchmark` that is `parser.error`, which is how every refusal in that
file is made. In `eval.development_sets` it is the `FATAL: …` line and a non-zero
return that file's existing `--report` refusals already use — the same reading of
the queue's rule, applied in the idiom each file already has, and both before any
call.

## What is not done yet, and why

The queue's rule 6 also says that at most one of `--ablate`, `--precedents` and
`--policy-version N≥2` may be given per invocation. Two of those three switches
do not exist yet — they arrive with tasks 4 and 5 — so the mutual exclusion is
only half-built here: `--ablate` refuses the modes it can refuse today. Whoever
adds `--precedents` or `--policy-version` adds the third leg, and the comment
above each refusal block is where it goes.

## What was run

- `python3 -m unittest tests.test_ablation` — `Ran 49 tests in 204.029s` / `OK`.
- Every module importing a changed module — `tests.test_ablation`,
  `tests.test_answer_isolation`, `tests.test_baselines`, `tests.test_brief`,
  `tests.test_development_sets`, `tests.test_events`, `tests.test_external_case`,
  `tests.test_facts`, `tests.test_grade`, `tests.test_llm`, `tests.test_loader`,
  `tests.test_money`, `tests.test_pipeline`, `tests.test_prepass`,
  `tests.test_rationale_consistency`, `tests.test_referee`,
  `tests.test_run_benchmark`, `tests.test_transcript`, `tests.test_ui_build`,
  `tests.test_verify_drafts` — `Ran 1239 tests in 5834.608s` / `OK (skipped=4)`
  on 3.13.12 and `Ran 1239 tests in 8843.829s` / `OK (skipped=4)` on 3.9.6. The
  four skips are the workspace's own: `NetworkTests`, `RunCurrencyTests` and two
  `NoteCouplingTests`. `tests.test_model` is the one module left out, and it
  imports nothing that changed.
- Discovery count `1249` against `1249` occurrences of `^\s+def test_` over
  `tests/*.py` — up from 1200 — which is the only guard against a test that never
  runs. The new module contributes 49.
- `python3 -m ui.build --check` — identical to a fresh build at 2371908 bytes.
  The switch changes no brief with the ablation off, so the committed page is
  unchanged.
- Credential scan of the six changed and new files with the pattern
  `sk-[A-Za-z0-9_-]{8,}`: no match, with a positive control that fires on a
  fabricated `sk-` string and the house fake `tok-live-FAKEKEY-…` that does not.
  A CJK scan of the same files found none, with a control that fires.
  `TOKENHUB_API_KEY`, `TOKENHUB_API_KEY_TEAMMATE` and
  `TRIBUNAL_LLM_NETWORK_TESTS` are all unset in the shell that ran the scan, so
  the literal-value half of the check was not made there and is not claimed here.

No ablation was run over either development set, so `runs/ablation/` does not
exist and nothing is committed there. The full suite runs once, in the final
check.

## Why this task stops here, with its commit owed

The work above is complete and its tests passed, but **it is not committed and
this task is not finished**, because a second writer is editing this repository
at the same time.

What happened, in the order it happened:

1. This task's changes were made in `tribunal/brief.py`, `tribunal/pipeline.py`,
   `eval/run_benchmark.py`, `eval/development_sets.py`, `runs/README.md`,
   `tests/test_ablation.py` and this note, and `tests.test_ablation` passed
   (`Ran 49 tests in 204.029s` / `OK`) at 22:54 local.
2. While the two long suite runs were in progress, **between 23:32 and 00:23**,
   files this session never wrote appeared or changed: `tribunal/precedents.py`
   (new), `tests/test_precedents.py` (new), `precedents/README.md` (new),
   `eval/grade.py`, `tribunal/events.py`, `tribunal/transcript.py`,
   `tests/test_answer_isolation.py`, `WORKBUDDY-HANDOFF.md`,
   `WORKBUDDY-SCOPE.md` and `data/PUBLIC-CONTRACT.md` — and, in the four files
   this task also edits, a complete `--precedents` implementation threaded
   through the same functions the ablation switch threads through. That is queue
   task 4's work, and it is not this session's.
3. `git add` was given this task's seven paths and `git commit` was made. **The
   commit therefore contained the other session's in-progress task 4 hunks in
   `eval/run_benchmark.py`, `eval/development_sets.py`, `tribunal/pipeline.py`
   and `runs/README.md`** — while `tribunal/precedents.py`, which the committed
   `eval/run_benchmark.py` imports at line 166, was left untracked. The committed
   tree could not be imported.
4. That commit was **undone** with `git reset --mixed HEAD~1`. Nothing was lost:
   the working tree is byte-for-byte what it was, the other session's files are
   untouched, and `HEAD` is back at `70191ca`, which is `origin/main`.

`HEAD` is therefore consistent and pushed, and this task's work sits in the
working tree beside the other session's. Nothing was pushed.

**Why it was not fixed by committing harder.** The two tasks' changes are
interleaved inside the same functions — `eval/development_sets.py`'s refusal
block now holds both this task's `--ablate` refusals and task 4's `--precedents`
one, and task 4's code calls this task's `--ablate` flag. Separating them would
mean hand-reverting task 4's hunks to produce a file that does not exist on disk,
committing that, and restoring the real file — with the risk of committing
something that cannot import, which is the failure this reset exists to undo.
Committing task 4's files to make the tree whole was rejected too: its own tests
were failing when this session looked (`Ran 84 tests in 568.811s` /
`FAILED (failures=2)`), and publishing another session's unfinished work is not
this task's to do.

**One caveat about the figures above.** Both long runs began before the other
session's first edit and import their modules when they start, so they measured
this task's code — but the tree was being written to while they ran, so they are
not a measurement of a frozen tree. `tests.test_ablation`'s own run is clean: it
finished before the other session's first edit.

**What a later session should do.** When the other writer has finished and the
tree is quiet again, re-run the suite on the frozen tree, then commit this task's
seven paths and put the hash in the row's commit cell. Rule 1's "finished" test
is not met yet, and the row says so.

## How it was finished

The next session found the other writer gone by 00:23 and the tree quiet from
00:37. It did the three things asked above.

**The separation was rebuilt, not re-guessed.** The four files this task shares
with task 4 were reconstructed from the tree as it stood, by deleting task 4's
hunks and nothing else. The result was then checked against `HEAD`: every
remaining change is one of this task's, and none of task 4's identifiers —
`precedents_library`, `precedents_run_directory`, `MOVED_PRECEDENTS`,
`precedents_moved`, `precedents_excluded`, `--precedents` — appears anywhere in
it. `tribunal/brief.py` and `tests/test_ablation.py` were confirmed byte-identical
to the working tree, so the commit carries exactly what this task wrote. No
`git checkout -- <file>` was used, per the standing rule: the files were restored
from copies.

**The commit landed.** Seven paths, committed as `8a1cdc0`, and the row's commit
cell now names it.

**The frozen-tree run.** The full suite was run on 3.13.12 against a tree that
was not written to while it ran: `Ran 1343 tests in 3710.620s` /
`FAILED (failures=1, errors=1, skipped=4)`. **Both results are the sandbox this
session runs in and not the code** — a refused `mkdir` in WorkBuddy's
`sitecustomize` shim, `PermissionError: Brokered mkdir refused by resolved path
policy: deny`, raised inside `EventLog.record` at `tribunal/events.py:335`. The
two are
`tests.test_run_benchmark.ReplayTests.test_the_report_says_the_advocates_were_replayed_and_from_where`
and
`tests.test_run_benchmark.ResumptionTests.test_a_case_not_yet_cached_is_the_only_one_run`;
outside the sandbox both modules pass — 38 tests — on 3.11.14 and 3.13.12, and
no code was changed for either. The full account is in
`docs/notes/2026-09-28-the-precedent-library.md`, which is the note whose task
ran the suite and which quotes the error line.

The two long runs recorded earlier in this note are therefore superseded: this
one imported its modules against a tree nobody was writing to, and its 1341
remaining results are clean.
