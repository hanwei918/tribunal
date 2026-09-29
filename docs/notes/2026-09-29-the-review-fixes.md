# The review fixes

An independent review at `db1846c` traced five groups of defects through the
code and tried, and failed, to refute them. This is what was done about them.

The work is five commits, one per group, in the order the fixes document gives:

| Group | Commit | What it fixed |
|---|---|---|
| 0 | `ede4720` | The viewer's Judge step rendered nothing, on all 29 cases. |
| A | `89cc392` | Four ways a path could reach a headline directory, and the switches the command line dropped. |
| B | `c36da52` | Two reports that did not say what they must. |
| C | `ae11d58` | Six correctness details. |
| D | `33b0b7d` | Two tests that could not fail, and four documents that were wrong. |

Every rule the work queue states for a task still applied: no model call of any
kind, tests in temporary directories and never under `runs/`, every new guard
seen to fail on a dirty fixture before it passes on the clean one, the changed
files scanned with `sk-[A-Za-z0-9_-]{8,}` before each commit, and only the
related modules run on 3.13.12 — the owner runs the full suite on both
interpreters outside the sandbox.

## 0. The viewer's Judge step was blank

**What broke.** `verifierPanel(caseDoc)` and `precedentsPanel(caseDoc)` return
`null` when the run recorded no data, and `missNote()` returns `null` when there
is no miss. Each was passed straight to `appendChild`, which throws on `null`:
`Uncaught TypeError: Failed to execute 'appendChild' on 'Node'`. So step 5 of
every case rendered nothing, and on the Overview `root.appendChild(missNote())`
threw before everything the Overview draws after the case grid. The comment
above the two panel appends claimed the guard was already there.

**The fix.** One helper, `appendNode(node, child)`, which returns without
appending when `child` is not a `Node`, used at the three call sites. The three
were found by the guard below rather than by reading: `missNote` on the
Overview, `verifierPanel` and `precedentsPanel` in the Judge step. `add`'s own
guard and `h`'s attribute guard were left as they were; neither is the defect.

**The guard.** `tests/test_ui_build.py` now parses the page's script — comments
and string literals blanked one character at a time so reported positions stay
true — and builds the set of functions whose own body can `return null`. Nested
function bodies are removed first, so a callback's `return null` is not charged
to its caller, and balanced argument lists are blanked, so
`return h("table", null, rows)` is not read as a returned `null`. It then fails
if any function in that set is passed directly to `appendChild`.

The scan found six nullable functions in the page — `byData`,
`clauseChipsInText`, `missNote`, `precedentsPanel`, `refusedBlock`,
`verifierPanel` — and exactly the three broken call sites, out of 227
`appendChild` calls. It was seen to fail first on the committed page:
`FAILED (failures=3)`, with
`[] != [(501, 'missNote'), (1155, 'verifierPanel'), (1156, 'precedentsPanel')]`
and the two tests that name the missing helper. After the rebuild the same six
tests printed `OK`.

**Why 1560 green tests missed it, which the review asked to be stated here.**
The unit tests never execute the page's script. They assert on the committed
bytes and on the parsed source, and a `TypeError` inside a browser is not
something a byte comparison can see. The defect was reachable only by loading
the page, and the corpus reaching 29/29 is what made it reachable — before that
there was a miss, `missNote()` returned a node, and the Overview survived to
draw its panels. `ui/dist/index.html` was rebuilt (2,381,834 bytes, sha256
`8451a77ff479623ce95d445982fdde814f5f8cce4731d4ee1c64bac6171154ed`) and
`python3 -m ui.build --check` reports it identical to a fresh build.
`tests.test_ui_build` ran `90 tests in 146.411s` / `OK (skipped=1)`.

## A. Paths into a headline directory

**A1. Replaying a version-2 source into a plain run.** `replay_verdict` rebuilds
each case's brief at the version its *source* recorded, and the only refusal
compared the version the *new* run was given. So
`--replay-advocates runs/policy-v2/<model>` with the default version handed the
judge a version-2 brief, wrote into `runs/<model>/` — the headline directory —
and recorded `policy_version: 1`. `check_replay` now takes the new run's version
and refuses when it differs from the source's, in both command lines and in the
function itself. It is a whole-replay refusal, on the same argument a missing
source directory already used. `None` means "the caller is not producing a run
of its own", which is why `eval.baselines` and `eval.verify_drafts` deliberately
pass nothing: both are read-only analyses of a run that already exists.

**A2. The switches the command line dropped.** Tasks 3 and 4 shipped a `main()`
that parsed `--ablate` and `--precedents` and never passed them to
`run_benchmark(...)`. `2be9ec6` fixed it and nothing held it.
`SwitchForwardingTests` holds it now with two tests, each running all three
switches as subtests: the first asserts the keyword reaches `run_benchmark`, at
the boundary where it would be lost; the second asserts from the outside that
the files land under the directory the switch's help text names and that nothing
lands in the headline directory. The review asked for the failing-first proof to
be recorded here, so: with the three forwarding lines removed, `Ran 2 tests in
4.990s` / `FAILED (failures=6)` — three subtests in each test — being
`AssertionError: 'policy_version' not found in {...}` for the keyword half and
`AssertionError: False is not true` on `(landed / "case-00101.json").is_file()`
for all three switches in the destination half. The file was restored and its
digest matched the backup exactly, after which the same two tests printed `OK`.

**A3. The baselines destination guard.** It checked the destination only against
the `--runs-dir` it was given, and `--runs-dir` and `--out-dir` are separate
arguments, so a scratch runs root made a destination inside the repository's own
`runs/` look safe. It now walks two roots — the one it was given and the
repository's own — by run directory name, by each root's `external/` subtree,
and by every ancestor up to the root, looking for a `run.json` or a
`case-*.json`. One test shows the refusal, with `baselines.RUNS_DIR` patched to
a temporary second root so the test never resolves a destination under the
repository's own `runs/`.

**A4. A test that used the real `runs/`.** The `development_sets` refusal test in
`tests/test_policy_versions.py` resolved its destination under the repository's
own runs root. It was moved onto a scratch root.

`tests.test_policy_versions tests.test_baselines tests.test_ablation
tests.test_precedents tests.test_development_sets tests.test_verify_drafts` ran
`299 tests in 927.105s` / `OK`.

## B. Reports that do not say what they must

**B1. The precedents channel never reached the report.** `brief_staleness`
collected the brief and prompt channels and never filled `stale_precedents`, so
`grade.Staleness` carried `()` for it however far the library had moved. The
field was already read by `moved_for` and `status_of`, `grade.render_report`
already printed `The precedent library has moved for N of M`, and
`print_summary` already printed `library moved:` — all of it unreachable. The
channel is filled now, and one test walks a case whose only change is the
library through `report.md`, the printed summary and the cache: it is listed on
that channel and it is **reused, not re-run**.

**B2. An ablated run's report looked like a headline report.** The title now
names the ablation and the report prints `brief.ablation_note(name)`, which had
no caller at all. For `admissibility` that note carries the sentence that
derived text computed from a null payload still says MISSING — the difference
between the ablated brief carrying no admissibility *object* and carrying no
admissibility *information*. Two tests: one asserts the title and the note for
each ablation, one asserts a plain report says nothing about an ablation.

Both fixes were shown failing first: with the precedents append replaced by
`pass` and the title and note removed, the two guards printed
`FAILED (failures=3)`, the title reading `# Benchmark report — hy4-preview`
where `# Benchmark report — hy4-preview — ablation clause-notes` was required.
`tests.test_ablation tests.test_precedents tests.test_run_benchmark
tests.test_development_sets` ran `461 tests in 2254.155s` / `OK (skipped=2)`.

## C. Correctness details

**C1. `precedents close` and policy versions.** `close` rebuilt every brief at
version 1 and then checked the digest against the one the case file records, so
every case of a run briefed at a later version rebuilt to a different digest and
was refused — no closure could be made from such a run at all. It rebuilds at
the version the case file's `configuration` records, which is the same rule
`replay_verdict` follows for a replayed case.

**C2. Matching step 4.** The step is written as "everything whose clause ids all
resolve in this case's brief", and the code dropped an id that did not parse and
kept the entry. A shortened clause list is a different entry from the one a
human closed, and a different score, because the score is how many of an entry's
ids a kept claim cites. The entry is now excluded whole — and so is an entry
resting on no clause id at all, which was already the behaviour.

**C3. The tie-break "by the earlier entry".** The code used the entry's index in
the list of latest-entries-per-source, which is the order the source *cases*
first appear. That is not what the words say. The tie-break is now the chosen
entry's own position in the log — the line the latest closure for its source
case was written on — and the docstring says so in the step it belongs to.

**C4. Recording `precedents_shown`.** With the switch on and nothing matched,
the transcript omitted the key while the case file wrote `[]`: two records of
one case disagreeing about whether the question had been asked. The transcript
now writes the empty list too. The judge's message is unchanged, and that is
asserted as bytes: with nothing matching there is no `precedents` key on it,
exactly as with the switch off. This is the one place where a test's claim had
to move with the fix — the old test asserted the two *transcripts* were
byte-identical, which the review's own correction makes false. The assertion
that matters, the judge's message, is now asserted directly and more strongly.

**C5. `--policy-version` below 1.** It was carried on the namespace like any
other integer and refused later, by the runner, after a client had been built.
Both command lines now hand `argparse` a `type` that refuses a version below 1
while the line is being read, so the value never exists as a namespace field.
`--policy-version 2` on a repository at version 1 is still a runner refusal with
a message naming the version the repository is at; only a version that names
nothing at all is a parse error.

**C6. Reading amendment files.** `load_amendment` read the file with the default
float parse. The amendment's clause is copied straight into the brief the agents
are handed, so a number in that file would have been the one place a policy
number reached the brief as a binary float. It reads with
`parse_float=Decimal`, the hook every other JSON read in this repository uses.

**The guards were seen to fail first.** Seven sabotages, one per fix, each
applied to a backed-up file and restored in a `finally`: `close` rebuilding at
version 1 again; an unparseable clause id dropped again; the deduplicated list
index used as the tie-break again; the transcript omitting the key again; each
command line parsing the version as a plain `int` again; the amendment reader
using the default float parse again. Every one exited non-zero with a real
message — including `AssertionError: a model was called` for both C5 cases,
which is the defect itself: without the parse-time refusal the run reached a
client before saying no — and every file's digest matched its backup afterwards.

## D. Tests that cannot fail, and documents that are wrong

**D1. The "never reads `events.jsonl`" test.** It asserted that the string
appears in the module's source. It does — in the docstring that says the module
never reads one — so it could not have failed on a module that read one. A
substring search cannot see a read. It is replaced by a test that runs a real
closure with `Path.read_text` patched to raise on any file called
`events.jsonl`, over a run directory that really holds one.

**D2. Task 5's test gaps.** Three changes in `tests/test_policy_versions.py`.
The test that could not fail asserted `CORPUS_CASES + CODEX_CASES == 44` — two
constants defined in the test file added to a third literal, which reads no part
of the repository. It now takes the counts off the two run directories, asserts
they are disjoint so the 44 is not 29 counted twice, and asserts every one of
them carries a 64-character digest for the comparison test to have compared. A
switch-off byte-identity test was added: the brief built with the argument
absent and the brief built at version 1 are the same canonical bytes, and both
are the bytes the recorded runs digested, over cases from both development sets.
And one version-2 run end to end on a scripted transport asserts that the
amendment's clause really is in the brief the run recorded — the run lands in
its own directory, its case file records version 2, the added clause resolves in
the policy that case was briefed against, and the recorded `brief_sha256` is the
digest of that brief.

The D2 pair was shown failing first, and the first of them was shown *not* to be
failable in its old form: with the recorded digests truncated to a single case,
the old assertion `29 + 15 == 44` still printed `True`, while the new test
failed with `AssertionError: 29 != 1`. The other two sabotages — the brief
builder defaulting to version 2, and the amendment never being applied — failed
with `FAILED (errors=5)` and `AssertionError: 'POL-RD-13' not found in {...}`.
All three files were restored.

**D3. The buddy-log table.** The task 5 commit removed the blank line after the
table, so the closing paragraph rendered as a table row. Restored. The history
was checked rather than the premise taken on trust: the blank line is present at
`8ba90c1` (the task 4 row) and absent from `db1846c` (the task 5 row) onward
through `a0fd43e`, the last commit to touch the file. After the restore the table
is 54 data rows, every one carrying exactly 7 cells with none separated by a
blank line, and the closing paragraph is preceded by a blank line again.

**D4. `runs/README.md`.** The task 5 commit wrote the new `policy-v<N>/`
section's two closing paragraphs by rewriting the `precedents/` section's in
place, so the precedents section lost its isolation paragraph ("It is never
written into a model's run directory") and its "No such directory is committed
here" paragraph, and the version section gained them. Both are restored to the
precedents section, which keeps them alongside the version section's own, and
the restored isolation paragraph lists `--compare` as well, which the code
refuses and the paragraph had never named. The task 5 note's account of that
removal — that it removed a duplicated paragraph from the `policy-v<N>/`
section — is corrected beneath the bullet it appears in, without rewriting the
bullet.

**D5. Task 3's note and row.** Both claimed `--ablate` is refused with
`--compare` and `--external` "in both CLIs". `eval.development_sets` has neither
flag, and `eval.run_benchmark` has no `--report`, which the note also named.
Both now say what exists: `--replay-advocates`, `--replay-check` and
`--verify-recorded-drafts` on both command lines; `--compare` and `--external`
on `eval.run_benchmark`; `--report` on `eval.development_sets`. This is a
correction of the wording in place rather than a dated line, because it is a
claim about which flags exist and a reader would act on it.

**D6. False claims.** Two earlier records described output the code could not
produce, and both now carry a dated correction line beneath the claim, with the
claim left as it was written:

- The task 4 note said the printed summary "prints `library moved:` too". It
  could not: `print_summary` had the line, but `brief_staleness` never collected
  the channel, so neither it nor the report's line was reachable. This is B1.
- The task 3 note said an ablated run goes to `runs/ablation/<name>/<model>/`.
  For `python3 -m eval.run_benchmark --ablate ...` it could not, because the
  flag never reached the runner: it built unablated briefs and wrote them into
  `runs/<model>/`. This is A2. A run started through `eval.development_sets` was
  never affected, because it forwards its switches through `run_set(**kwargs)`.

**The guards were seen to fail first.** Four sabotages: `close` reading the
run's own event log; the forty-four count taken from a constant again; the brief
builder defaulting to a later version; the amendment never applied. Every one
exited non-zero — `AssertionError: a closure opened
.../runs/hy4-preview/events.jsonl`, `AssertionError: 29 != 1`, `FAILED
(errors=5)` and `AssertionError: 'POL-RD-13' not found in {...}` — and every
file was restored.

**Two additions, found while finishing this group.** Neither is one of the six,
and both are recorded because this group is where they are committed.

*The two C5 guards wrote into `runs/`.* The two command-line tests
that hold C5 ran their command line without `--runs-dir`, so with the guard
removed the run reached a client *after* it had named its destination and
written an `invocation_start` event. The C5 sabotage left the proof on disk:
`runs/policy-v0/hy4-preview/events.jsonl` and
`runs/policy-v0/deepseek-deepseek-flash/events.jsonl`, both recording commit
`c36da52` — a version-0 run directory under the repository's own `runs/`, which
is the one place the work queue says a test must never write. Both tests now
hand `--runs-dir` a `tempfile.TemporaryDirectory()`. That changes nothing while
the guard holds, because the refusal happens while the line is read and no
destination is ever named; it keeps the failure mode out of the repository when
it does not hold. Re-proved after the change, with `type=int` restored on both
command lines: `Ran 2 tests in 0.851s` / `FAILED (failures=2)`, both
`AssertionError: a model was called`, and `runs/policy-v*` afterwards is empty.
This is why the test file changed in this group rather than in C. The two
directories the earlier sabotage left were moved to
`/tmp/c5-sabotage-residue-2026-09-29/` rather than deleted, and are not
committed. The proof's own output is
`runs/unit-test-review-groupD-c5-scratch-root-sabotage-py3.13.12.log`.

*The `runs/` README did not name the whole-replay refusal.* A1 added a refusal
that covers a whole replay rather than a single case, and `runs/README.md` —
whose "Replaying the advocates" section lists the per-case conditions and every
other refusal — did not mention it. One paragraph was added there. That section
is where a reader learns what a replay refuses, so a refusal the code makes and
the README omits is a document that is wrong by omission, which is what D5 and
D6 are about.

## What was run

Only the related modules, on 3.13.12, one run per group, each into
`runs/unit-test-review-group*.log`:

| Group | Modules | Result |
|---|---|---|
| 0 | `tests.test_ui_build` | `Ran 90 tests in 146.411s` / `OK (skipped=1)` |
| A | `test_policy_versions test_baselines test_ablation test_precedents test_development_sets test_verify_drafts` | `Ran 299 tests in 927.105s` / `OK` |
| B | `test_ablation test_precedents test_run_benchmark test_development_sets` | `Ran 461 tests in 2254.155s` / `OK (skipped=2)` |
| C | `test_precedents test_policy_versions test_pipeline test_transcript test_ablation test_run_benchmark test_development_sets` | `Ran 749 tests in 2463.120s` / `FAILED (errors=1, skipped=2)` |
| D | `test_precedents test_policy_versions test_run_benchmark` | `Ran 434 tests in 1384.923s` / `OK (skipped=2)` |

**The one error in group C is this sandbox and not the code, and it is reported
as a failure rather than explained away.** It is
`PermissionError: Brokered host mkdir requires an available runtime file rule`,
raised from `path.parent.mkdir(parents=True, exist_ok=True)` inside
`_write_text_atomic` while `tests.test_development_sets.SetRunTests.
test_a_second_run_reuses_the_cache_and_makes_no_call` wrote an `invocations.json`
under its temporary directory — the traceback runs entirely through
`/Applications/WorkBuddy AI.app/.../cli/vendor/shim/sitecustomize.py`, the
sandbox's file broker, and no line of this repository raised it. Run on its own
afterwards, the same test printed `Ran 1 test in 46.007s` / `OK`. The full suite
on both interpreters is the owner's, outside the sandbox.

## The secret scan

Every commit's changed files were scanned with `sk-[A-Za-z0-9_-]{8,}`, with a
positive control that fires on a fabricated key, one that fires on
`TOKENHUB_API_KEY`/`TOKENHUB_API_KEY_TEAMMATE`, and one that fires on a CJK
character. All three controls fired and every file reported no key, no
credential variable and no CJK. The house fake `tok-live-FAKEKEY-…` is reported
as a note and not counted, because it is not `sk-`-prefixed. The two
`_CREDENTIAL_VARIABLES` names already present in `tests/test_ui_build.py` before
this work are on the pre-existing line that scans for them, and are unchanged.

Group D's scan is the one that reports rather than passes: four of its files
carry the two credential **variable names** as words, and they already did at
`HEAD` — `runs/README.md` once, `docs/buddy-log/README.md` thirteen times, and
the two task notes once each. No line this work added to any of them mentions
either name; checked with `git diff -U0` filtered to added lines. The one new
occurrence is in this note, in the sentence above that names them as the thing
the scan looks for. A variable name is not a value, and both variables are unset
in the environment the runs were made in.
