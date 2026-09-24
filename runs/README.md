# `runs/` — what the benchmark wrote

This directory is the benchmark's own output. Three subdirectories are **committed deliberately**, as
evidence for two findings recorded under `docs/notes/`. A fourth, `external/`, is where a converted
external case is written, and one run of one converted case is committed there. Everything else here —
the suite logs — is untracked.

## Which directory holds what

| Directory | What it is | Read it as |
|---|---|---|
| **`deepseek-deepseek-flash/`** | **The headline run**, and on top of it a **judge-only re-run** of that same run. Four invocations: two full runs (`97dbb9c`, `493beea`) and two replays that reused `493beea`'s advocates and called only the judge. Every cached result is current on both channels and all 29 carry a `replay` block; the graded figure over the 29 is **27/29**, failing 107 and 211. The runtime model decision rests on the `493beea` measurement. | A measurement, and a replay of one. Read each result's `replay` block before reading its tokens. |
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

**One case is committed under `external/`, and it is the organisers' sample case.** The organisers'
sample case has been converted — `data/external/ryde/case-00901.json`, with every decision the
conversion made recorded in `data/external/ryde/mapping.json` — and arbitrated **twice**.
`external/ryde/` holds both invocations, each committed **exactly as produced**: the first at
`b2556e8`, whose PARTIAL_REFUND 1.00 is the record of what the system did before anything about it was
changed, and the second at `74881db`, after both the converted case and the judge prompt had moved. No
file in the directory has been edited. Read it as evidence of what those runs did, not as a score —
there is no answer-key entry for it.

**What each ruling did, and where the first departs from this repository's own policy, is recorded in
`docs/notes/2026-09-23-external-sample-case.md` and
`docs/notes/2026-09-24-judge-only-rerun-and-the-external-case.md`.** The first note checks each point
against the transcript and the clause text, records the tokens billed and the wall clock, and names the
part of `prompts/v1/judge.system.md` that let the ruling be written as it was. The second records the
re-run, which produced **ESCALATE at confidence 0.6** — the ruling this repository's policy text
supports, because the deciding fact's only evidence is the trace impaired under POL-NS-08(b) and
POL-NS-09(e) holds the fee. No prompt was changed in the re-run. The credential rule below applies to
both unchanged.

**901's brief channel is current and its prompt channel is not.** The converted case was amended after
the first run — it gained the source's own account of how the arrival marker was made — and
`judge.system.md` has moved three times since: first gaining the rule that carrying a fact is not the
same as meeting a limb, then having that rule revised into an ordered procedure after a read-only review
found wording in it that could move cases the answer key has right today, and then losing the account
sentence, which that review had found read as "it may carry the limb". All three moves are recorded in
`docs/notes/2026-09-24-meeting-a-limb-and-the-dropped-record.md`,
`docs/notes/2026-09-24-the-limb-procedure-revised.md` and
`docs/notes/2026-09-24-removing-the-account-sentence.md`. The first run's files still read as they were
produced and are stale on both channels; the second invocation's `brief_sha256` rebuilds identically,
and its `prompts_sha256` was the current one until the third move, so it is now stale on the prompt
channel alone. One caution when checking either: the staleness report can see only the prompt half for
an external case, because it rebuilds *corpus* briefs by case number and 901 is not a corpus case — so
its brief half reads `unknown`, which is "cannot tell" and not "unmoved".

## How to read one run directory

| File | What it holds |
|---|---|
| `run.json` | The metadata of the **last** invocation: its commit, clean-tree flag, prompts digest, answer key digest, interpreter, case list, failures and token figures. Overwritten by the next invocation. A `replay` block is added when this invocation reused another run's advocates instead of calling its own. |
| `invocations.json` | One entry per invocation, keyed by start time. **This is the file that survives.** `run.json` describes only the invocation that wrote it; this is the history, so an earlier invocation's commit and token totals are still there afterwards. |
| `case-<NNNNN>.json` | The cached result for one case: the ruling, its provenance (commit, prompts digest, interpreter, brief digest) and the token split. Written only for a case that produced a ruling. A `replay` block is added when that case's advocates were replayed rather than called here. |
| `case-<NNNNN>.transcript.json` | Every call made for that case, with the raw response body, the parse outcome, and the per-call token split. A replayed case carries its advocates' entries as they were recorded, each marked as replayed, and only the judge's entry is a call this run made. |
| `calls.json` | Every call this invocation made, in one file. |
| `report.md` | The graded result **for this invocation's cases only** — those it produced a ruling for, whether by calling or from the cache — rendered by `eval/grade.py`. Overwritten by the next invocation, like `run.json`, so a replay of four cases leaves a four-case report beside a twenty-nine-case directory. Read its case count first. |

## Replaying the advocates

`--replay-advocates RUN_DIR` reads a case's two advocate outputs out of an earlier run's transcript and
calls **only the judge**. It exists because a prompt change that touches one agent should not be
measured through two agents' sampling variance: in the headline run the two advocates billed
1,732,682 of the run's 2,804,061 tokens, 61.8 %, so re-running them would regenerate inputs the judge
already has and pay about 62 % of the run for the privilege.

It is not a shortcut around the checks. A case is **refused** — recorded as a failure with its reason,
no model call, no cache entry — unless all four hold: the brief this repository builds now hashes to
the digest the result recorded; each advocate's system prompt as rendered now hashes to what that run
recorded for that role; the model is the same; and the recorded answer parsed. The judge's own input
is then built by the same code path a full run uses, not by a second copy of it.

Two figures are kept apart and neither is folded into the other. The cache entry and `run.json` record
what the borrowed calls cost the run that made them — reported, because a reader has to see what the
replayed half of the case cost, and named `billed_to_another_run` so that no reader adds it to a total
— and the result's own token figures are the judge's alone. Wherever the figures appear, the report and
the viewer say the advocates were replayed and from which run.

**An external case is never replayed.** `--replay-advocates` and `--external` together are refused, and
so is `--compare`, because a run whose advocates came from elsewhere is not the same measurement and a
comparison must not silently mix the two. `--replay-check RUN_DIR` answers the question without
running anything: it reads the source and reports, per case, whether a replay would be accepted and
why not. A replay **into** a directory that already holds a case's result needs `--force`: without it
the cached result is reused rather than replayed, which is the runner's ordinary rule and not a
special case of replay. See `docs/notes/2026-09-24-replaying-the-advocates.md`.

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

The headline run directory now carries four invocations, and only the second is a full measurement.
The first (`97dbb9c`, 2026-09-22) was stopped after 5 of its 29 cases; its two case failures are among
the findings recorded in `docs/notes/`. The second (`493beea`, 2026-09-23) completed all 29 and is the
measurement the runtime model decision rests on. The third and fourth (`74881db`, 2026-09-24) are the
judge-only re-run: each reused the second's advocates and called only the judge — the third stopped on
its token budget after 25 of 29 cases, the fourth took the four it had not reached — and both are
recorded in `docs/notes/2026-09-24-judge-only-rerun-and-the-external-case.md`.

**`run.json` and `report.md` describe the last invocation, and after this run that is the fourth.** The
report is graded over the cases *that invocation* handled, by design, so the committed `report.md` is a
four-case report reading 3/4 = 75.0% and marked "(advocates replayed)"; the directory-wide figure,
**27/29**, is what grading all 29 cached results gives and is the one the viewer shows. Read the
report's case count before comparing it with anything.

## The rule for putting anything here

**No file enters this directory until it has been checked for a credential.** The repository is
private now and goes public before submission, so a file showing an `sk-`-prefixed key would publish
it. The check is: any `sk-` followed by eight or more identifier characters, and the values of
`TOKENHUB_API_KEY` and `TOKENHUB_API_KEY_TEAMMATE`.

A byte scan of a PNG cannot see rendered text, so for an image the check has to be of the image
itself — open it and read it — not only of its bytes. Nothing in this directory is an image.

The scan that cleared these directories covered all 125 files under `runs/` at this commit — the three
committed run directories, `external/`, and the untracked suite logs — and found no match, with a
positive control that fires on a fabricated `sk-` string.

The one committed external run was scanned the same way as it entered the directory. The `sk-`
pattern was run over all 5 files under `runs/external/` and matched none, with a positive control
that fires on a fabricated `sk-` string. **The two environment variables were not set in the shell
that ran the scan, so the literal-value half of the check could not be made there and is not claimed
here.** The pattern half is the half that catches a key the file itself carries, which is how a
credential would arrive in a run record; the literal half is a belt on top of it.
