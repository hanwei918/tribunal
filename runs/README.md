# `runs/` — what the benchmark wrote

This directory is the benchmark's own output. Three subdirectories are **committed deliberately**, as
evidence for two findings recorded under `docs/notes/`. A fourth, `external/`, is where a converted
external case is written, and one run of one converted case is committed there. Everything else here —
the suite logs — is untracked.

## Which directory holds what

| Directory | What it is | Read it as |
|---|---|---|
| **`deepseek-deepseek-flash/`** | **The headline run.** 29 of 29 cases, 0 failed, every cached result current. This is the run the runtime model decision rests on. | A measurement. |
| `hy3/` | Produced under an invalidated configuration. | Evidence for a defect. No number in it is usable. |
| `hy4-preview/` | Produced under the same invalidated configuration. | Evidence for a defect. No number in it is usable. |

**These are snapshots, and a later run moves them.** A run directory is named after the model id, so
a future run of the same model writes into the same directory and rewrites these files case by case.
What is committed is the state at the commit, not a live measurement — which is why every
`case-*.json` records the commit, the prompts digest and the interpreter it was produced under, and
why `invocations.json` keeps one entry per invocation rather than only the last. Read a number here
against those fields, not against the date the file was opened.

**The runtime model decision is recorded in `tribunal/model.py` and argued in
`docs/notes/2026-09-23-runtime-model-decision.md`.** That note carries the accuracy figures, the
measured cost, the alternatives and the limits of each comparison. This file does not repeat them.

**The two invalidated directories are the evidence for `docs/notes/2026-09-22-advocate-output-contract.md`**,
which found that the pipeline forced `response_format: {"type": "json_object"}` while the advocate
prompt asked for a JSON array — two requirements no model can satisfy at once. Every advocate answer
was rejected and every case failed. Those two directories are the transcripts that prove it, and they
are committed so the per-attempt table in that note can be checked against the recorded
`response_text` rather than taken on trust.

## `external/` — where a converted external case runs

`external/<name>/` holds the output of

    python -m eval.run_benchmark --external data/external/ryde/case-00901.json

one directory per converted case, named after the case's own directory, so the above writes into
`external/ryde/`. The files are the ones listed in the next section, with one difference: there is
**no `report.md` and no score**. An external case has no entry in `eval/answers/ground_truth.json` and
is not graded against one — giving it an entry would put a case into the frozen key that the key does
not measure. What the run prints instead is the produced ruling beside the organisers' own stated
expectation, read from `eval/external/ryde/expected.json` and labelled as a stated expectation rather
than a verified answer.

**It is not a model's run directory, and must never be merged into one.** A run directory is named
after the model id and holds the corpus the submission reports; `deepseek-deepseek-flash/` is 29
cases. An external case is not one of the 29, so writing it there would change what that directory
means while leaving every file a reader looks at apparently intact. `assert_external_run_directory`
refuses any destination outside `runs/external/` before a single call is made, so this is checked
rather than merely intended.

**One run is committed under `external/`, and it is the organisers' sample case.** The organisers'
sample case has been converted — `data/external/ryde/case-00901.json`, with every decision the
conversion made recorded in `data/external/ryde/mapping.json` — and arbitrated once.
`external/ryde/` holds that one run, committed at `b2556e8` **exactly as produced**: it is the record
of what the system did before anything about it was changed, so no file in it has been edited and the
case has not been re-run. Read it as evidence of what that run did, not as a score — there is no
answer-key entry for it.

**What that ruling did, and where it departs from this repository's own policy, is recorded in
`docs/notes/2026-09-23-external-sample-case.md`.** That note checks each point against the transcript
and the clause text, records the tokens billed and the wall clock, and names the part of
`prompts/v1/judge.system.md` that let the ruling be written as it was. No prompt was changed. The
credential rule below applies to this run unchanged.

**The converted case has since been amended, so this run's `brief_sha256` no longer matches the brief
this repository rebuilds for it, and the prompts digest has moved twice.** All three moves are
expected, and are recorded in `docs/notes/2026-09-24-meeting-a-limb-and-the-dropped-record.md` and
`docs/notes/2026-09-24-the-limb-procedure-revised.md`: the converted case gained the source's own
account of how the arrival marker was made, `judge.system.md` gained the rule that carrying a fact is
not the same as meeting a limb, and that rule was then revised into an ordered procedure after a
read-only review found wording in it that could move cases the answer key has right today. The run
itself is untouched and still reads as it was produced. One caution when checking it: the staleness
report can see only the prompt half for an external case, because it rebuilds *corpus* briefs by case
number and 901 is not a corpus case — so its brief half reads `unknown`, which is "cannot tell" and
not "unmoved".

## How to read one run directory

| File | What it holds |
|---|---|
| `run.json` | The metadata of the **last** invocation: its commit, clean-tree flag, prompts digest, answer key digest, interpreter, case list, failures and token figures. Overwritten by the next invocation. |
| `invocations.json` | One entry per invocation, keyed by start time. **This is the file that survives.** `run.json` describes only the invocation that wrote it; this is the history, so an earlier invocation's commit and token totals are still there afterwards. |
| `case-<NNNNN>.json` | The cached result for one case: the ruling, its provenance (commit, prompts digest, interpreter, brief digest) and the token split. Written only for a case that produced a ruling. |
| `case-<NNNNN>.transcript.json` | Every call made for that case, with the raw response body, the parse outcome, and the per-call token split. |
| `calls.json` | Every call this invocation made, in one file. |
| `report.md` | The graded result, produced by `eval/grade.py`. |

## Two cautions about the invalidated runs

- **Their token totals are wrong.** `hy3/run.json` records `spent_this_invocation: 0` for a run whose
  transcripts carry 83,412 billed tokens, and `hy4-preview/run.json` records 142,247 where the
  transcripts sum to 247,239. This was caused by the same defect described next: a run charges only
  the completed cases, and a case that failed after its calls were made was billed for them all the
  same. The invocation record now distinguishes the two figures — see
  `docs/notes/2026-09-23-runtime-model-decision.md`, *How the figures came to be recorded at all*.
- **`"completed": true` in those two files does not mean the run completed.** `state["stop_reason"]`
  starts at `completed` and the metadata is rewritten after every case, so a process killed by SIGTERM
  leaves the last-written file claiming a finish it never reached. Both of these runs stopped early:
  `hy3/` requested 8 cases and reached 2, `hy4-preview/` requested 3 and reached 2. The reliable
  evidence that a run finished its loop is the presence of `report.md` and `calls.json`, which are
  written only after the loop ends.

The headline run carries two invocations, and only the second is a measurement. The first
(`97dbb9c`, 2026-09-22) was stopped after 5 of its 29 cases; its two case failures are among the
findings recorded in `docs/notes/`. `run.json` and `report.md` describe the second
(`493beea`, 2026-09-23), which completed all 29.

## The rule for putting anything here

**No file enters this directory until it has been checked for a credential.** The repository is
private now and goes public before submission, so a file showing an `sk-`-prefixed key would publish
it. The check is: any `sk-` followed by eight or more identifier characters, and the values of
`TOKENHUB_API_KEY` and `TOKENHUB_API_KEY_TEAMMATE`.

A byte scan of a PNG cannot see rendered text, so for an image the check has to be of the image
itself — open it and read it — not only of its bytes. Nothing in this directory is an image.

The scan that cleared these three directories covered all 81 files under `runs/` and found no match.

The one committed external run was scanned the same way as it entered the directory. The `sk-`
pattern was run over all 5 files under `runs/external/` and matched none, with a positive control
that fires on a fabricated `sk-` string. **The two environment variables were not set in the shell
that ran the scan, so the literal-value half of the check could not be made there and is not claimed
here.** The pattern half is the half that catches a key the file itself carries, which is how a
credential would arrive in a run record; the literal half is a belt on top of it.
