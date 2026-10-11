# How we built it

One page, written for the last minute of the submission video: the workflow, and
four things the tools taught us that a figure stands behind. Everything here is
read from the repository's own records -- the buddy log
([`../buddy-log/README.md`](../buddy-log/README.md)), the dated notes under
[`../notes/`](../notes/), and [`../../README.md`](../../README.md) -- and nothing
is added to them.

## The workflow

**One task specification per part, one session per part, one row per session.**
The owner wrote a specification for each part and handed it over whole; WorkBuddy
carried that part out in one session and committed it with a row in the buddy log
naming the task, the files it touched, what was verified and how, and the commit.
At `2731adc` -- the commit before this part -- `git log` holds **324 commits** and
the buddy log holds **187 dated rows**, one per task session. The two numbers are
not the same because one session may make several commits (24 rows list more than
one) and some sessions committed nothing (15 rows list none). The session records
themselves are submitted to the organisers separately, because they carry
directory listings of the owner's machine.

**The owner ran the tests and the paid runs, and read every report.** The full
test suite and every run that made a model call were run by the owner outside
WorkBuddy's sandbox, and each report was read against the real output before it
was committed. WorkBuddy wrote and committed the code, the tests and these
documents, and made no model call for any committed run. The runs' own provenance
says the same thing: every case file records the commit, the prompts digest and
the interpreter that produced it.

## Four tips, each a measured lesson

**1. Run the tests outside the agent's sandbox.** The sandbox's file broker
interposes on writes, and it both slows them and sometimes refuses them. The
refusals are recorded as failures rather than explained away:
`PermissionError: Brokered host mkdir requires an available runtime file rule`,
raised from `path.parent.mkdir(parents=True, exist_ok=True)` inside
`_write_text_atomic`, and a `FileNotFoundError` on a `case-00101.json.part`
inside the sandbox's own `os.replace` broker, in a test that passes outside it
([`../notes/2026-09-29-the-review-fixes.md`](../notes/2026-09-29-the-review-fixes.md)).
The cost is recorded too, though not as one paired measurement: WorkBuddy's own
whole-suite run inside the sandbox read `Ran 2053 tests in 3722.752s` -- 1.8
seconds a test -- and its related-module runs 1.6 to 4.9 seconds a test, while
the owner's whole-suite runs outside read `Ran 2580 tests in 133.339s` on 3.11
and `Ran 2580 tests in 102.216s` on 3.9, 0.05 and 0.04 seconds a test
([`../notes/2026-10-06-before-public.md`](../notes/2026-10-06-before-public.md),
[`../notes/2026-10-09-policy-version-4.md`](../notes/2026-10-09-policy-version-4.md)).
The two sides are different trees and different test counts, so no single ratio
is claimed; the practice is what follows from them, and every buddy-log row says
the suite was not run inside the sandbox.

**2. One task per session keeps the context small.** Each part is handed over as
its own specification, so a session reads that part's files and little else: the
buddy log's rows each name a handful of files, and the parts that touch many
modules are the ones that took longest. The repository records **no token count
for a session's own context**, so none is given here -- the token figures in it
(a median of 226,125 billed tokens per case, for instance) measure the benchmark's
model calls and not the conversation that wrote the code.

**3. An agent's "all green" is checked against the real output, and a new test is
first shown to fail.** Both rules are in
[`../../START-HERE.md`](../../START-HERE.md). The first is why the owner re-runs
the suite: the owner's own run of part 37 read `Ran 3042 tests ... FAILED
(failures=61, errors=1, skipped=5)`, with every failure and the one error inside
the tests that part had just added -- which is exactly what an agent's own
summary of its work cannot be trusted to have found. The second is that a guard
nobody has seen fail is not evidence:
`tests/test_sealed_roots_closed.py` pins one test per call site and shows each one
red with its call removed, and the viewer's `appendChild` guard was seen to fail
on the committed page -- `FAILED (failures=3)`, naming the three broken call
sites -- before the fix made it pass.

**4. Import a sealed set without reading its answers, and run it once from a
tag.** A sealed set is the only independent measurement the submission has, so
the import is arranged so that nobody on the development side can read the
answers: the cases are loaded by path and by number and each file is held to the
digest its index records, while the key is extracted straight into place and
**never opened** -- only `unzip -l` names and `shasum` digests are used, and no
file of it is printed, read or summarised. The run is then made **once**, by the
owner, from a commit whose `tribunal/`, `prompts/` and `policy/` trees equal a
freeze tag, and the command needs an opt-in variable that nothing in the
repository sets (`TRIBUNAL_SEALED_RUN=sealed-v2`). Afterwards the root is closed
to everything, another plain run included, and every committed file under it is
checked against a manifest of its sha256 -- so a write that got past a guard would
be **caught, not prevented**. Four sets are held this way, and their four figures
are never pooled.

The rest of the account -- what each set is, who made it, and what the runs
scored -- is in `README.md` (Results) and in the dated notes under `docs/notes/`.
