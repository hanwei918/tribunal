# `runs/` — what the benchmark wrote

This directory is the benchmark's own output. Three subdirectories are **committed deliberately**, as
evidence for two findings recorded under `docs/notes/`. Everything else here — the suite logs — is
untracked.

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
