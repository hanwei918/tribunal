# `runs/` — what the benchmark wrote

This directory is the benchmark's own output. Every subdirectory named in the table below is
**committed deliberately**, either as a measurement or as evidence for a finding recorded under
`docs/notes/`. Everything else here — the suite logs — is untracked.

## Which directory holds what

| Directory | What it is | Read it as |
|---|---|---|
| `ablation/` | An ablated run — `ablation/<name>/<model>/`, and `codex/ablation/<name>/<model>/` under the second set's root. **Both ablations are committed here**: the `admissibility` one over both development sets (`35eead2`, 2026-09-29) and the `clause-notes` one over both (`89c616e`, 2026-09-29). The directory has its own section below. | A different measurement from the headline: the `admissibility` briefs had that object removed from every artifact and the `clause-notes` briefs had every clause's drafting notes removed, so a figure here answers a question about a brief the pipeline does not otherwise build. Never merged into a model's run directory. |
| `amount-rule/` | The **measurement** of the amount read-off rule — `runs/amount-rule/report.md` and `runs/amount-rule/amount-rule.json` — and, one level down, where a **run** judged by a non-default rule goes: `amount-rule/<rule>/<model>/`, and `codex/amount-rule/<rule>/<model>/` under the second set's root. It has its own section below. | The measurement is **not a run and not a score**: it re-reduces the judge drafts three recorded runs already hold, under two rules, and makes no model call. A run under `amount-rule/signed/` is a different measurement from the headline, judged by a rule the headline was not. |
| `baselines/` | The baselines scored off the recorded runs — `python3 -m eval.baselines --set all`. Two files, `report.md` and `baselines.json`, and it has its own section below. | A comparison that says what the headline figure is worth. Not a measurement of the model, and not a generalisation figure. |
| `codex/` | The second development set's runs. `codex/deepseek-deepseek-flash/` holds the fifteen-case set's own run, keyed by `eval/answers/codex/ground_truth.json`; `codex/deepseek-v4.1-flash/` holds that probe's event log alone. | A measurement of the fifteen cases, never of the corpus. Never merged into `deepseek-deepseek-flash/`. |
| `deepseek-v4.1-flash/` | A probe of a different model — case 105 at `b25b743`, which stopped after one of the two cases it requested — committed as it was left. | Not a measurement of the submission's model, and no corpus figure is computed from it. |
| `external/` | Where a converted external case is written, one directory per case. It has its own section below. | Evidence of what those runs did. There is no answer-key entry for it, so it is not a score. |
| `_icloud-incident-2026-09-27/` | The run-level files (`events.jsonl`, `invocations.json`, `run.json`) recovered from the three places iCloud's Desktop & Documents move left them, committed exactly as found. | Evidence for the incident recorded in `docs/notes/2026-09-27-the-replays-the-icloud-move-and-the-probe.md`. Not a run. |
| **`deepseek-deepseek-flash/`** | **The headline run**, and on top of it **five judge-only re-runs** of that same run. Seven invocations: two full runs (`97dbb9c`, `493beea`) and five replays that reused `493beea`'s advocates and called only the judge — two measuring the prompt after its first amendment, three measuring the frozen prompt. Every cached result is current on both channels and all 29 carry a `replay` block; the graded figure over the 29 is **27/29**, failing 105 and 211, and that figure is the frozen prompt's. The runtime model decision rests on the `493beea` measurement. | A measurement, and a replay of one. Read each result's `replay` block before reading its tokens. |
| `hy3/` | Produced under an invalidated configuration. | Evidence for a defect. No number in it is usable. |
| `hy4-preview/` | Produced under the same invalidated configuration. | Evidence for a defect. No number in it is usable. |
| `policy-v<N>/` | Where a run at a later policy version goes: `policy-v<N>/<model>/`, and `codex/policy-v<N>/<model>/` under the second set's root. **The repository is at version 2** — the amendment `0001-pol-rd-13` is approved — and the version-2 re-run of the 57 affected development cases is committed at `39a8a36` under `policy-v2/`, `codex/policy-v2/` and `wild-dev/policy-v2/`, with `rerun.json`, `diff.json` and `diff.md`. `wild-v2` is the only **sealed** run at version 2, and it writes into `runs/wild-v2/<model>/` and never into a `policy-v<N>/` directory. It has its own section below. | A different measurement from the headline: the headline was measured at version 1, so a figure here answers a question about the committed policy that the headline does not. |
| `policy-gaps/` | The policy-gap loop's report — `python3 -m eval.policy_gaps report --run-dir … --run-dir …`. Two files, `report.json` and `report.md`, and it has its own section below. | **Not a run and not a score.** It names the cases the policy could not decide and groups them, read off the recorded runs. No model call is made to produce it, and nothing in it changes the policy. |
| `precedents/` | Where a run with `--precedents` on goes: `precedents/<model>/`, and `codex/precedents/<model>/` under the second set's root. No such run is committed here. It has its own section below. | A different measurement from the headline, and not comparable to it: the precedent library is built from closures made by people who have seen these development sets. |
| `rerun-2026-09-29/` | A runs root of its own, holding one re-run of the organisers' sample case: `rerun-2026-09-29/external/ryde/`, committed as `23589e1`. It went to its own root so that the committed `external/ryde/` result, which `docs/notes/2026-09-23-external-sample-case.md` is about, stayed as it was. It has its own section below. | Evidence of what that run did, not a score — there is no answer-key entry for 901. It is an external case like any other, so it is refused outside `runs/external/` and must never be merged into a model's run directory. |
| `wild/` | **The single run of the held-out set (`wild-v1`)**, committed at `2e527d6`: `wild/deepseek-deepseek-flash/`, 131 files, run once by the owner from the commit tagged `freeze-2026-09-30` and committed byte for byte as produced. **62 of the 64 cases produced a ruling** — 517 and 533 failed with `SHAPE` and are recorded as misses — and the four-field figure is **55/62 = 88.7%** over the cases that produced a ruling, **55/64 = 85.9%** over the set. It has its own section below. | One of the submission's **two generalisation figures**, and never a development figure. It is never merged into a model's run directory, never summed with the corpus, second-set or `wild-v2` figures, and never produced by `--set all`. |
| `wild-dev/` | The held-out set's own 64 cases and key as **development data** — `wild-dev/<model-slug>/`, and the one directory committed under it is the version-2 re-run, `wild-dev/policy-v2/deepseek-deepseek-flash/`, 79 files, from `39a8a36`. From 2026-10-01 those answers may be read and the system changed to fix what they exposed, so it is the one directory in this table that may be **run again**; `sealed=False` is the whole of what allows that. It is in neither the set `--set all` runs nor the set the recorded-drafts measurement reads. | A **development** measurement, and never a generalisation figure. It holds the same 64 cases as `wild/`, but it is not that run: it is never merged with `wild/`, with `wild-v2/` or with the development sets, and no figure here is the submission's. |
| `wild-v2/` | **The second sealed set's single run**, made once by the owner on 2026-10-04 from `6cc2682`: `wild-v2/deepseek-deepseek-flash/`, **45 files**, committed byte for byte at `9f4abee`. The set is 20 cases, 701–720, keyed by `eval/answers/wild-v2/ground_truth.json`, and the four-field figure is **18/20 = 90.0%** over the set; the manifest is `docs/notes/2026-10-04-wild-v2-run-manifest.txt`. It has its own section below. | One of the submission's **two generalisation figures**, and never a development figure. It is never merged into a model's run directory, never summed with the corpus, second-set or `wild-v1` figures, and never produced by `--set all`. The root is closed outright, like `wild/`. |

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
conversion made recorded in `data/external/ryde/mapping.json` — and arbitrated **three times**.
`external/ryde/` holds all three invocations, each committed **exactly as produced**: the first at
`b2556e8`, whose PARTIAL_REFUND 1.00 is the record of what the system did before anything about it was
changed; the second at `74881db`, after both the converted case and the judge prompt had moved; and the
third at `c4c9a06`, under the frozen prompt, which escalated again at confidence 0.6. No file in the
directory has been edited. Read it as evidence of what those runs did, not as a score — there is no
answer-key entry for it.

**What each ruling did, and where the first departs from this repository's own policy, is recorded in
`docs/notes/2026-09-23-external-sample-case.md` and
`docs/notes/2026-09-24-judge-only-rerun-and-the-external-case.md`.** The first note checks each point
against the transcript and the clause text, records the tokens billed and the wall clock, and names the
part of `prompts/v1/judge.system.md` that let the ruling be written as it was. The second records the
re-run, which produced **ESCALATE at confidence 0.6** — the ruling this repository's policy text
supports, because the deciding fact's only evidence is the trace impaired under POL-NS-08(b) and
POL-NS-09(e) holds the fee. No prompt was changed in the re-run. The credential rule below applies to
both unchanged.

**901's two channels are both current, and its last invocation is the frozen prompt's.** The converted
case was amended after the first run — it gained the source's own account of how the arrival marker was
made — and `judge.system.md` has moved three times since: first gaining the rule that carrying a fact is
not the same as meeting a limb, then having that rule revised into an ordered procedure after a
read-only review found wording in it that could move cases the answer key has right today, and then
losing the account sentence, which that review had found read as "it may carry the limb". All three
moves are recorded in `docs/notes/2026-09-24-meeting-a-limb-and-the-dropped-record.md`,
`docs/notes/2026-09-24-the-limb-procedure-revised.md` and
`docs/notes/2026-09-24-removing-the-account-sentence.md`. The first run's files still read as they were
produced and are stale on both channels. **Corrected 2026-09-30:** this paragraph used to add that the
second and third invocations' `brief_sha256` rebuilds identically and that the third records the current
`prompts_sha256`, so it was current on both. That was true when it was written on 2026-09-24 and is not
true now — rebuilding 901's brief from the committed converted case hashes to `79403092…` where the third
invocation recorded `db5b6b95…`, and the code renders `5b8510cd…` where the third recorded `829ccc8f…`.
So the third invocation is stale on both channels too, and the re-run under
`rerun-2026-09-29/` is what was taken against the current ones. One caution
when checking any of them: the staleness report can see only the prompt half for an external case,
because it rebuilds *corpus* briefs by case number and 901 is not a corpus case — so its brief half
reads `unknown`, which is "cannot tell" and not "unmoved".

## `rerun-2026-09-29/` — the sample case re-run, in a root of its own

`rerun-2026-09-29/external/ryde/` holds the output of

    python3 -m eval.run_benchmark --external data/external/ryde/case-00901.json \
        --runs-dir runs/rerun-2026-09-29 --timeout 900

run by the owner off-peak on 2026-09-29 and committed as `23589e1`, six files,
byte for byte as produced. It is a re-run of the same converted case the section
above is about, under the pipeline as it now stands.

**It went to its own root on purpose.** A run directory is named after the model
id, so re-running 901 into `external/ryde/` would have overwritten the committed
schema-1 result that `docs/notes/2026-09-23-external-sample-case.md` reads. A
separate root keeps that result as it was and gives the new one its own
`invocations.json`. The directory is still an external case directory:
`assert_external_run_directory` requires the destination to sit under
`<runs root>/external/`, and with `--runs-dir runs/rerun-2026-09-29` that root is
`runs/rerun-2026-09-29/external/`, so the case landed in its own
`rerun-2026-09-29/external/ryde/` rather than in a model's run directory. It
holds no `report.md` and no score, and it must never be merged into a model's run
directory.

**What it produced.** `ESCALATE`, both money fields `null`, at confidence 0.6,
with a unanimous four-draft panel (4 of 4 valid, threshold 3, `carried`,
`vote_agreement` 1.00) and 226,880 tokens over 434.1 seconds of call time. The
committed schema-1 result published the same `ESCALATE` at the same confidence
0.6, asking the judge once, for 106,661 tokens over 232.7 seconds. The ruling is
stable; what has moved is everything around it. The re-run's brief rebuilds from
the committed converted case to `79403092…`, while the schema-1 result recorded
`db5b6b95…` and does not rebuild, so `tribunal/brief.py` has moved since
2026-09-24; and the re-run records the current `prompts_sha256 5b8510cd…` where
the schema-1 result recorded `829ccc8f…`. The committed result is therefore stale
on both channels. The re-run's own brief channel reads `unknown`, because the
staleness check rebuilds *corpus* briefs by case number and 901 is not a corpus
case.

**The organisers' stated expectation is printed beside the ruling and is not an
answer.** `eval/external/ryde/expected.json` records "Cancellation charge
UPHELD" and says in its own text that it is not part of the key, not merged into
it, not an input to any agent, and that "UPHELD" is the source's word rather than
a token this system emits. `docs/notes/2026-09-30-the-clause-notes-ablation-and-901.md`
compares the two runs against each other and against that expectation.

## `verify-recorded-drafts/` — where the verifier is measured, not the model

`verify-recorded-drafts/<model>/` holds the output of

    python -m eval.run_benchmark --verify-recorded-drafts RUN_DIR

with the same thing available on a development set through
`python -m eval.development_sets --verify-recorded-drafts RUN_DIR`, which writes
`runs/<set>/verify-recorded-drafts/<model>/`. It is where the **draft verifier**
is measured: the source run's recorded judge drafts are rebuilt exactly as they
were, and only the verifier is called over them, so the same drafts are read
with the pass off and on and the difference between the two readings is the
verifier's and not a second sampling of the judge.

The directory name is not the model id, and that is the point: "never the
headline directory" is then a property of the path rather than a promise. A
destination that is a model's own run directory is refused in code before
anything is written, and so is a case whose recorded drafts answer a different
brief, a different set of advocate prompts or a different judge prompt — the
same four conditions `--replay-advocates` enforces, plus the judge side, because
this mode reads the judge's drafts as well. A source run that asked the judge
once has no panel to verify and is refused too.

Three files are written, and the files a model's run directory carries are not
among them. There is no `run.json`, no `invocations.json` and no `case-*.json`,
because this is not a measurement of the model: the advocate and judge calls
were made by the source run and cost nothing here, so the only token figures
recorded are the verifier's own.

| File | What it holds |
|---|---|
| `verify-recorded.json` | One entry per case: the vote's outcome and agreement **without** the verifier, read from the source run, and the same two **with** it, beside every statement the verifier judged `contradicted` and the reason the call was unusable if it was. |
| `verify-recorded.md` | The same thing rendered for reading, one case per block. |
| `events.jsonl` | The run's event log, in the same append-only hash-chained form as any other run's — `agent_call` entries for the verifier's calls and one `verification` event per case. |

**Both sets have now been measured, and both directories are committed.**
`runs/verify-recorded-drafts/deepseek-deepseek-flash/` and
`runs/codex/verify-recorded-drafts/deepseek-deepseek-flash/` were produced by the
two commands above against `runs/deepseek-deepseek-flash/` and
`runs/codex/deepseek-deepseek-flash/` and are committed as produced, under the
first two rows of the table below. Read them with
`docs/notes/2026-09-29-the-verifier-measured.md`, which is where the figures are
checked against the briefs. Nothing in this directory may be merged into a
model's run directory for the reason `external/` may not: those figures would
then read as that run's.

| Set | Source run | Cases | Usable | Contradicted | Material | Tokens |
|---|---|---|---|---|---|---|
| corpus | `runs/deepseek-deepseek-flash/` | 29 | 27 | 19 | 8 | 1,479,451 |
| second set | `runs/codex/deepseek-deepseek-flash/` | 15 | 15 | 38 | 7 | 752,852 |

Two corpus cases, 203 and 211, produced no usable answer — the verifier returned
no JSON object, so every draft kept its vote and the case is recorded unusable
with a reason. That is the designed fallback, and it is why the corpus command
exits 1: `report.ok` is false when any case is unusable.

## `baselines/` — what a score is worth

`baselines/` holds the output of

    python3 -m eval.baselines --set all

and it is not a run. A baseline is a rule that answers every case without reading
it, and the file exists to say what the headline figure is worth: a number no
better than "always ESCALATE" is not evidence that the panel is doing anything.
Every row is computed from what a run already recorded — the judge drafts on its
transcripts and the rulings it published — so producing this file calls no model
at all and costs nothing.

| File | What it holds |
|---|---|
| `report.md` | One section per set, plus a combined section for `--set all`, each a table of rows with a note saying what the row is and where its figure comes from. Every refused case is listed with its reason. |
| `baselines.json` | The same figures as parsed values: per section, the cases analysed, the cases refused with their reasons, and every row's counts. |

The rows are: always ESCALATE; the majority ruling, which is the ruling the
section's cases most often require and is chosen on the set it is scored on; each
of the four recorded drafts scored alone, and their mean; the best single draft
per case, which is an upper bound for any rule that publishes one of the drafts'
answers and which a no-majority escalation can exceed; and the carried vote, for
comparison. A case that is stale, unknown or holds no panel of drafts is refused
with its reason and left out of every denominator rather than counted as a miss,
so each section's denominators are the cases that could be scored and not the
size of the set.

**It is never written into a model's run directory.** The destination is checked
in code before anything is written, and so is every directory above it: a
directory holding a run's own `run.json`, or its `case-*.json` files, is a run
directory whichever model it belongs to, and everything under `runs/external/` is
refused whole. Read a row here as a comparison for a figure, never as that figure.

## `ablation/` — where an ablated run goes

`ablation/<name>/<model>/` holds the output of

    python3 -m eval.run_benchmark --ablate clause-notes
    python3 -m eval.development_sets --set codex --ablate admissibility

one directory per ablation per model, under the runs root the run was given. So
an ablated corpus run goes to `runs/ablation/<name>/<model>/` and an ablated run
of the second set to `runs/codex/ablation/<name>/<model>/`. The files are the
ones any run directory carries, listed below; what changes is the brief the
agents were handed.

An **ablation** is one thing removed from every case's brief, so a run with it on
measures the pipeline without that thing. Two exist. `clause-notes` builds the
brief with `include_clause_notes=False` — the flag that already existed, given a
name a run can record. `admissibility` removes the `admissibility` object from
every artifact. The second one is worth stating carefully: the ablated brief
carries no admissibility **object**, which is not the same as carrying no
admissibility information. A MISSING artifact keeps its `evidence_id` and its
null payload, the referee reads an artifact with no admissibility object as one
with no impairment, and derived text computed from a null payload still says
MISSING.

**It is never written into a model's run directory.** The destination is chosen
under the runs root's `ablation/` directory and then checked in code before
anything is written, so a name that resolved outside it is refused rather than
merely discouraged; and `--ablate` is refused together with `--replay-advocates`,
`--replay-check`, `--verify-recorded-drafts` and `--external`, because every one
of those reads a run recorded without the ablation. The ablation is recorded in
the `configuration` object of `run.json`, of every `invocations.json` entry and
of every case file, and the staleness check rebuilds each case's brief the same
ablated way — otherwise every case of an ablated run would report its brief
moved.

**Both ablations are committed here.** `runs/ablation/admissibility/deepseek-deepseek-flash/`
holds the corpus run — 29 cases — and
`runs/codex/ablation/admissibility/deepseek-deepseek-flash/` the second set's 15,
both run by the owner outside the sandbox on 2026-09-29 and committed as
`35eead2`, byte for byte as produced. Each directory holds two invocations: the
first pass at the default 600-second timeout lost seven corpus cases and three
codex cases, and every failure was re-run with `--timeout 900`. The corpus scored
**26/29** against the headline's **29/29**; the second set **14/15** against
**14/15**. Four cases moved — 107, 112 and 211 on the corpus, 9111 on the second
set. The per-case figures, the failures, the tokens and what the ablated brief
still carries are in `docs/notes/2026-09-29-the-admissibility-ablation.md`.

**The `clause-notes` ablation is committed beside it**, as `89c616e`:
`runs/ablation/clause-notes/deepseek-deepseek-flash/` (63 files) and
`runs/codex/ablation/clause-notes/deepseek-deepseek-flash/` (35 files), the same
two commands with `--ablate clause-notes`, run by the owner off-peak on
2026-09-29. Each holds **one** invocation: all 44 cases completed on the first
pass, so there is no retry in either. The corpus scored **27/29** against the
headline's 29/29 and the admissibility ablation's 26/29; the second set **14/15**,
the same four-field figure as both others but not the same failure. Four cases
differ from the key — 107 and 211 on the corpus, 9111 on the second set — and 112
is the one case only the `admissibility` ablation moves.
`docs/notes/2026-09-30-the-clause-notes-ablation-and-901.md` reads the two
ablations side by side and says why 107 and 211 cannot separate either one from
sampling variation.

Nothing in this directory may be merged into a model's run directory for the
reason `external/` may not: an ablated result is a different measurement, and a
reader finding it beside an unablated one would read it as that run's.

## `amount-rule/` — where a run judged by another rule goes, and the measurement of the rule

`amount-rule/<rule>/<model>/` holds the output of

    python3 -m eval.run_benchmark --amount-rule signed
    python3 -m eval.development_sets --set wild --amount-rule signed

one directory per rule per model, under the runs root the run was given — so the
second set's go to `runs/codex/amount-rule/<rule>/<model>/`. The files are the
ones any run directory carries; what changes is the rule a draft's amount is held
to. `amount-rule/` itself holds the **measurement** of that rule, which is not a
run at all.

**An amount rule is how a draft's amount is read off the brief's money block.**
`published` is the default and what every run so far was judged by: a figure the
block publishes, or the **sum** of two or three of them. `signed` is the same
rule with a sign on every term after the first — a difference of two or three
published figures, leading term positive, result above zero. It exists because
two of the held-out set's cases produced no ruling when the drafts computed the
right refund and the published rule could not read it: on an upfront-quoted fare
the remedy POL-RD-11(a) gives is a difference by construction.

**The switch is off, and off is byte-identical.** A run that names `published`
writes the same bytes it wrote before the switch existed, and `published` is not
counted as one of the switches that change what a run measures. `--amount-rule
signed` is refused together with `--ablate`, `--precedents`, `--policy-version
N>=2`, `--report`, `--compare`, `--replay-check`, `--verify-recorded-drafts` and
`--external`, each because it reads or produces a run judged by the published
rule. `--replay-advocates` is deliberately **not** refused: a replay calls only
the judge, and the rule is what a draft's amount is held to, so it is a request
the pipeline can honour rather than one it would drop.

**It is never written into a model's run directory.** The destination is chosen
under the runs root's `amount-rule/<rule>/` directory and then checked in code
before anything is written, against *that rule's* directory rather than against
`amount-rule/*`, so a signed run cannot land in the published one's.

**The measurement is committed, and it is not a run.**

    python3 -m eval.amount_rule

re-reduces the drafts three recorded runs already hold — the corpus's 29 cases,
the second set's 15 and the held-out set's 64 — under both rules, through the
same reconstruction `eval/verify_drafts.py` and `eval/baselines.py` use, and
writes the two files below. **No model call is made.** All 108 panels were
rebuilt, no case was refused, and the published reading reproduces the ruling
each run itself published for every one of them.

| File | What it holds |
|---|---|
| `report.md` | The per-case table for all three runs — the published reading, the signed reading and the key, with the direction each case moved — then the movement counts, then every case the signed rule changes or newly decides wrongly. |
| `amount-rule.json` | The same figures as parsed values: per set the cases read, the refused cases with their reasons, the movement counts, the cases with no cached result, and the cases whose published reading is not the run's own. |

| | |
|---|---|
| cases read | **108** (29 + 15 + 64), 0 refused |
| matching both ways | **98** |
| matching → missing | **0** |
| missing → matching | **1** — 533 |
| missing both ways | **9** |
| a safe outcome turned into a monetary ruling that differs from the key | **1** — 501 |

**The default rule is unchanged, and nothing here adopts the signed one.** The
figures, the cases and the recommendation are in
`docs/notes/2026-09-30-the-amount-read-off-rule.md`. One consequence is recorded
there in full: the owner's check `git diff --quiet freeze-2026-09-30 -- tribunal
prompts policy` no longer holds, because the second rule lives in
`tribunal/pipeline.py`. The held-out run is committed as produced and the switch
is off, so the 55/64 figure is what it was — but `wild-v1` is run once and cannot
be run again to price the change.

The measurement is refused a destination that is a run directory or lies inside
one, for the reason `external/` is: a reader finding these figures beside a run's
own would read them as that run's.

## `precedents/` — where a run whose judge was shown earlier closures goes

`precedents/<model>/` holds the output of

    python3 -m eval.run_benchmark --precedents
    python3 -m eval.development_sets --set codex --precedents

one directory per model, under the runs root the run was given — so the second
set's go to `runs/codex/precedents/<model>/`. The files are the ones any run
directory carries; what changes is what the judge was given.

With the switch on, the judge's user message carries a `precedents` key: a fixed
note and up to three items chosen from `precedents/precedents.jsonl`, each naming
a `precedent_id`, a `category`, clause ids and a ruling. **No amount and no
summary travel in it.** The ids shown for a case are recorded at the top level of
that case's transcript and of its case file, and the library's chain head and
note digest are recorded in the run's `configuration` — so a cached result
produced against an earlier library is recognisable as such: it reads stale on a
third channel, its progress line names the library as what moved, and `report.md`
lists the cases. Stale is a finding and not an action — the result is still
reused, exactly as a moved brief or a moved prompt is, and `--force` is what runs
it again.

**The figures are not comparable to the headline.** The library is built from
closures made by people who have seen these development sets, so a case the
library holds a closure for is material the system has been shown before. Those
cases are left out of every figure in `report.md` and named there, and the
printed summary and the `invocation_end` event name them too.

**It is never written into a model's run directory.** The destination is chosen
under the runs root's `precedents/` directory and then checked in code before
anything is written, so a name that resolved outside it is refused rather than
merely discouraged. `--precedents` is refused together with `--ablate` -- each
changes what the agents are given, and a run with both on measures neither --
and with `--compare`, `--replay-advocates`, `--replay-check`,
`--verify-recorded-drafts` and `--external`, because every one of those reads or
produces a run whose judge saw no block.

**No such directory is committed here.** No run has been made with the block on,
so there is nothing to commit, and the commands above are the ones that would
produce it.

## `policy-gaps/` — where the policy ran out

`policy-gaps/` holds the output of

    python3 -m eval.policy_gaps report --run-dir runs/deepseek-deepseek-flash \
        --run-dir runs/codex/deepseek-deepseek-flash

and it is not a run. The loop finds the cases the policy could not decide,
groups them into clusters, and — for a cluster a person has closed at least
twice — asks a model to draft one clause that would decide them. Nothing it
drafts takes effect on its own.

**The report is computed and calls no model.** Every figure is read out of the
recorded runs: each case's transcript **vote block**, its rebuilt brief, and the
precedent library. Of a case file it reads five fields and no others —
`case_no`, `ruling`, `brief_sha256`, `development_set` and `configuration` —
which are exactly the five `tribunal/precedents.py` reads, through that module's
own reader. It never reads `matched`, a grade event or the answer key, and the
report says so in its own text.

| File | What it holds |
|---|---|
| `report.md` | One section per cluster, each a table of its cases with the ruling the system produced, the confidence, the clause its first referral leads with, and the human closure if the library holds one. Then the pairs dropped as noise, and the cases that could not be analysed with the reason. |
| `report.json` | The same figures as parsed values: per run the cases cached and the cases that were gaps; the dropped signature pairs; every case that could not be analysed with its reason; and every cluster with its cases, its level, its flag and its per-case detail. |

A case is a **gap** when the policy left it undecided, and the trigger names
which way: `no_majority` (the vote escalated with a quorum of valid drafts),
`too_few_valid_drafts` and `too_few_valid_drafts:verifier` (it escalated without
one), `below_confidence_floor` (it escalated at a confidence under the floor the
loaded policy states), `clause:<id>` (it escalated at or above the floor with a
referral), and `judge_no_clause` (it escalated at or above the floor with no
referral). A file with no vote block — one the judge was asked once for — is
classified by the last three rows and its trigger is prefixed `single_draft:`.
A confidence that was **not recorded** counts as under the floor: "not recorded"
is not "at or above".

Clusters form at two levels, `(category, trigger)` and `(category, trigger,
signature)`, where a signature is the sorted `type:issue` pairs of the artifacts
the brief holds as `IMPAIRED` or `MISSING`. A pair present on at least 80 % of
the given runs' cases is dropped from **every** signature first: it
distinguishes none of them, and leaving it in would cluster the whole set
together. A fine cluster whose signature is empty is not emitted, because it
holds exactly its coarse cluster's cases and would name one set of cases twice.

**A cluster is flagged at three cases, and only a flagged cluster can be
drafted.** The threshold is a parameter, `--min-cases`, and the report states
the value it used. A cluster is drafted from only when the library holds at
least two closures on its cases, so the report's per-case closure column is what
says whether a cluster is ready.

**It is never written into a model's run directory.** The destination is checked
in code before anything is written, and so is every directory above it: a
directory holding a run's own `run.json`, or its `case-*.json` files, is a run
directory whichever model it belongs to, and everything under `runs/external/`
is refused whole. A cluster's own cases are still named by the run they came
from, and a case whose set cannot be established is refused rather than guessed.

## `policy-v<N>/` — where a run at a later policy version goes

`policy-v<N>/<model>/` holds the output of

    python3 -m eval.run_benchmark --policy-version 2
    python3 -m eval.development_sets --set codex --policy-version 2

one directory per version per model, under the runs root the run was given — so
the second set's go to `runs/codex/policy-v<N>/<model>/`. The files are the ones
any run directory carries; what changes is the policy the briefs were built from.

A **policy version** is an integer. Version 1 is the three files in `policy/`
exactly as committed, and it is what every run before the switch used, so
version 1 writes to the ordinary run directory and never here. Version N is
those files with the amendments `0001` through `N-1` from `policy/amendments/`
applied — one added clause each, never an edit and never a removal. The version
is recorded in the `configuration` object of `run.json`, of every
`invocations.json` entry and of every case file, and the staleness check rebuilds
each case's brief at the same version — otherwise every case of such a run would
report its brief moved.

**It is never written into a model's run directory.** The destination is chosen
under the runs root's `policy-v<N>/` directory and then checked in code before
anything is written, against *that version's* directory rather than against
`policy-v*`, so a version-2 run cannot land in version 3's. `--policy-version
N>=2` is refused together with `--ablate`, `--precedents`, `--report`,
`--replay-advocates`, `--replay-check` and `--verify-recorded-drafts`.

**One such directory is committed, and it is the version-2 re-run.** The
repository is at **version 2** — the amendment `0001-pol-rd-13` is approved — so
there is no later version to run, and the commands above are the ones that would
produce the output once one has been. The 57 development cases the amendment
could touch were re-run at version 2 and committed at `39a8a36` under
`runs/policy-v2/`, `runs/codex/policy-v2/` and `runs/wild-dev/policy-v2/`, with
`rerun.json`, `diff.json` and `diff.md` beside the first. Of the 57, 9 changed,
4 newly match the key and 1 newly misses it. `wild-v2` is the only **sealed** run
at version 2, and it lives under `runs/wild-v2/<model>/`.

## `wild/` — the single run of the held-out set (`wild-v1`)

`wild/<model>/` holds the output of

    python3 -m eval.development_sets --set wild --concurrency 2 --timeout 900

one directory per model, under the runs root the run was given. The files are the
ones any run directory carries, and its `report.md` is graded against
`eval/answers/wild/ground_truth.json` — the set's own key, which is neither
development key.

**The directory is committed, and it is the run this section named before it
existed.** `runs/wild/deepseek-deepseek-flash/` is the output of that command,
run by the owner outside this sandbox from `d275ef8`, with a clean tree and
`git diff --quiet freeze-2026-09-30 -- tribunal prompts policy` holding, between
13:04 and 16:46 SGT on 2026-09-30. Two invocations are recorded: a full pass over
the 64 cases and one retry of the two that failed. All 131 files are committed
byte for byte as produced at `2e527d6`; **the owner's run made the model calls;
none was made in this repository** in committing or reading them.

**62 of the 64 cases produced a ruling; 517 and 533 produced none.** Both failed
with `SHAPE`: the draft check `DRAFT_AMOUNT_NOT_READ_OFF` rejected all four judge
drafts in each, because the drafts computed an amount the brief's money block
does not publish — and the drafts were right about the money. Both were retried
once with the same command and failed the same way. That is a deviation from the
protocol below ("retried until every case has a result"), recorded with its
reason in `docs/notes/2026-09-30-the-sealed-run.md`: the failure is not
transient, and a further retry would re-sample the judge until one draft passed,
which is choosing a result rather than recovering from a fault.

**The figures.** Four-field exact **55/62 = 88.7%** over the cases that produced
a ruling and **55/64 = 85.9%** over the set. Per field, over the 62: `ruling`
56/62, `amount_sgd` 56/62, `driver_compensation_sgd` 62/62, `referrals` 60/62.
Per category: `ROUTE_DEVIATION` 30/35 produced (37 in the set) and
`NO_SHOW_CHARGE` 25/27. Escalation precision 3/7 = 0.429 and recall 3/4 = 0.75,
with over-escalations 501, 504, 508 and 530 and under-escalation 627.
13,536,023 tokens over 404 agent calls across both invocations, read from
`events.jsonl`. Every figure, and the cause of each miss, is in
`docs/notes/2026-09-30-the-sealed-run.md`.

**It is one of the two generalisation figures, and it is never added to anything.** The
corpus figure and the second set's figure are development figures: they were
produced by people who had seen those cases. The held-out set was not, which is the
whole of what makes its run a measurement of generalisation — so a sum of it and
a development figure would be neither. `--report` prints it in a section of its
own and never inside the combined line, `--set all` does not run it, and
`runs/wild/<model>/` is refused by every destination that must not write into a
reported result: the ablation, the precedents block, a later policy version, the
baselines, the policy-gap report and the recorded-drafts measurement.

**A case that has a result is never re-run.** `--force` is refused for this set
inside `run_set`, so it cannot be added to the command above; and
`--replay-advocates`, `--replay-check` and `--verify-recorded-drafts` are
refused for it while the command line is read, because every one of those
produces a result from a run already recorded. A case that fails is retried with
the same command until every case has a result, as the protocol in
`docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md` says. A failure here is
`TRANSPORT`, `TIMEOUT`, `DEADLINE` or `SHAPE`.

**One thing still to settle, and the run did not settle it.** The set's own
README, committed at `eval/external/wild/README.md`, calls this 64-case set a
development and regression set and names a different, 24-case set as the sealed
one. `docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md` records that
conflict in full. Nothing was changed on the strength of it — not by the import
and not by the run — and it is still the owner's to settle before the 55/64
figure above is reported as generalisation.

## `wild-v2/` — the second sealed set's single run

`wild-v2/<model>/` holds the output of

    TRIBUNAL_SEALED_RUN=wild-v2 python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900

one directory per model, under the runs root the run was given. The files are the
ones any run directory carries, and its `report.md` is graded against
`eval/answers/wild-v2/ground_truth.json` — the set's own key, which is neither
development key.

**The directory is committed, and it is the run this section named before it
existed.** `runs/wild-v2/deepseek-deepseek-flash/` is the output of that command,
run by the owner outside this sandbox **once, on 2026-10-04** — one invocation,
from `6cc268298ac079807ddc6682b7776824371648c2`, with a clean tree and the freeze
gate `git diff --quiet freeze-2026-10-03 -- tribunal prompts policy` exiting 0,
**as the owner recorded it**. All **45 files** are committed byte for byte as
produced at `9f4abee`, and `docs/notes/2026-10-04-wild-v2-run-manifest.txt`
records the digest of every one of them, checked by
`tests/test_wild_v2_run_manifest.py`. **The owner's run made the model calls;
none was made in this repository** in committing or reading them.

**The figures.** All 20 cases produced a ruling and no case failed. Four-field
exact **18/20 = 90.0%** — the same over the cases that produced a ruling and over
the set, because there is no no-ruling case to move the basis; ruling alone
18/20; per category `NO_SHOW_CHARGE` 8/8 and `ROUTE_DEVIATION` 10/12; escalation
precision 4/5 and recall 4/5, with the over-escalation at 702 and the
under-escalation at 716. Every figure, the interval, and the cause of each miss
is in `docs/notes/2026-10-04-the-second-sealed-run.md`.

**The opt-in is what makes the run the owner's.** Without
`TRIBUNAL_SEALED_RUN=wild-v2` in the environment the invocation is refused before
any client is built and before any directory is created, and nothing in this
repository sets that variable. `--check` prints the plan without running
anything, needs no opt-in, and creates nothing:

    python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900 --check

**One partial run was made and deleted, and it does not count.** On 2026-10-03 at
14:14 a probe started the command above with a real client, and it was stopped at
14:17:31; its `events.jsonl` (22,722 bytes) was removed with
`git clean -fd runs/wild-v2` at 14:19:36, and the owner decided that `wild-v2`
stays the sealed set and that the attempt does not count under the sealed
protocol.
`docs/notes/2026-10-03-the-sealed-protocol-made-executable.md` records the facts
and the decision under *The partial run of 14:14, and the owner's decision*.

**The set is 20 cases, numbered 701 to 720**, held under
`data/external/wild-v2/` with its own `index.json`. Twelve are
`ROUTE_DEVIATION` and eight `NO_SHOW_CHARGE`. `docs/notes/2026-10-03-wild-v2-imported.md`
records the import, the digest of every imported file, and the registration.

**The registration fixes the policy version at 2.** The amendment
`0001-pol-rd-13` is approved, so the repository is at version 2, and this set is
the one that measures it: `--set wild-v2` uses version 2 with no flag and still
writes into `runs/wild-v2/<model>/`, never into a `policy-v2` directory. An
explicit `--policy-version` on this set is refused, because the version is part
of what the set is rather than a switch on top of it.

**It is the second generalisation figure, and it is never added to anything.**
It is reported beside the corpus, the second set and the held-out set's figures
and never inside the combined line, `--set all` does not run it, and
`runs/wild-v2/<model>/` is refused by every destination that must not write into
a reported result: the ablation, the precedents block, a later policy version,
the amount-rule measurement, the baselines, the policy-gap report and the
recorded-drafts measurement. **Four headline directories now, not three.**

**Nothing is created under its root again.** The held-out set's root is closed
outright, and so is this one: `runs/wild-v2/` is in
`MADE_SEALED_RUNS_SUBDIRS`, so no permit opens it and nothing is created under it
again, the plain sealed run included. The refusal is now made with the run
committed, so the guard is what keeps the record the record.

**Every command that writes to a path a user names refuses a sealed root.** Both
sealed roots and all four headline directories are refused by one helper,
`eval.sealed_roots.refuse_a_sealed_destination`, before anything is created or
written. The commands it guards are `run_benchmark --external` (in
`assert_external_run_directory`), `eval.grade --out`, `ui.build --out`,
`policy_gaps draft --proposals-dir` and `policy_gaps approve --amendments-dir`, and
the four guards the earlier cleanup added — the recorded-drafts measurement, the
baselines, the amount-rule measurement and the policy-gap report — are routed
through the same helper. Each of those is pinned by a test in
`tests/test_sealed_roots_closed.py`, for both sealed roots. **`tribunal.precedents
--store` is the one write path that is not guarded**: `tribunal/` imports nothing
from `eval/`, so the evaluated system stays byte-identical to the tag.

**A case that has a result is never re-run.** `--force` is refused for this set
inside `run_set`, and `--replay-advocates`, `--replay-check` and
`--verify-recorded-drafts` are refused while the command line is read, because
every one of those produces a result from a run already recorded.

## How to read one run directory

| File | What it holds |
|---|---|
| `run.json` | The metadata of the **last** invocation: its commit, clean-tree flag, prompts digest, answer key digest, interpreter, case list, failures and token figures. Overwritten by the next invocation. A `replay` block is added when this invocation reused another run's advocates instead of calling its own. |
| `invocations.json` | One entry per invocation, keyed by start time. **This is the file that survives.** `run.json` describes only the invocation that wrote it; this is the history, so an earlier invocation's commit and token totals are still there afterwards. |
| `case-<NNNNN>.json` | The cached result for one case: the ruling, its provenance (commit, prompts digest, interpreter, brief digest) and the token split. Written only for a case that produced a ruling. A `replay` block is added when that case's advocates were replayed rather than called here. Three further blocks are written only when the run recorded them: `configuration` (the switches the invocation ran with), `verification` (the draft verifier's findings, present only when the verifier ran) and `precedents_shown` (the closure ids the judge was handed, present only when the precedents switch was on). The viewer shows the last two, each panel drawn only when its block is there. |
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

**A replay is refused whole, not per case, when the source was briefed at another policy version.**
Each brief is rebuilt at the version its *source* recorded, so replaying a version-2 source into a run
at version 1 would hand the judge a version-2 brief and then write the result into the version-1 run's
directory — the headline one — recording version 1. The refusal is made in both command lines and in
`check_replay`, and it covers the whole replay on the same argument a missing source directory does.

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

The headline run directory now carries seven invocations, and only the second is a full measurement.
The first (`97dbb9c`, 2026-09-22) was stopped after 5 of its 29 cases; its two case failures are among
the findings recorded in `docs/notes/`. The second (`493beea`, 2026-09-23) completed all 29 and is the
measurement the runtime model decision rests on. The third and fourth (`74881db`, 2026-09-24) are the
first judge-only re-run, measured through the judge alone against the second's advocates — the third
stopped on its token budget after 25 of 29 cases, the fourth took the four it had not reached — and
both are recorded in `docs/notes/2026-09-24-judge-only-rerun-and-the-external-case.md`. The fifth,
sixth and seventh (`c4c9a06`, 2026-09-24) are the second: the same replay against the frozen prompt,
the fifth stopped on its budget after 22 of 29 cases, the sixth taking six of the seven it had not
reached and timing out on 208, the seventh re-running 208 alone. They are recorded in
`docs/notes/2026-09-24-the-frozen-prompt-run.md`, which is where the frozen prompt's corpus figure
lives.

**`run.json` and `report.md` describe the last invocation, and after this run that is the seventh.** The
report is graded over the cases *that invocation* handled, by design, so the committed `report.md` is a
one-case report reading 1/1 = 100.0% and marked "(advocates replayed)"; the directory-wide figure,
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

**The held-out run was scanned the same way as it entered the directory (2026-09-30).** The `sk-`
pattern and the literal `TOKENHUB_API_KEY` were run over all **131** files under `runs/wild/` and
matched none, a positive control fired on a fabricated `sk-` string, and the same scan found **no
character outside ASCII** in any of them. Both environment variables were unset in the shell that ran
the scan, so the literal-value half of the check could not be made there and is not claimed here; the
pattern half — the half that catches a key a file itself carries — is the half that was made.

The one committed external run was scanned the same way as it entered the directory. The `sk-`
pattern was run over all 5 files under `runs/external/` and matched none, with a positive control
that fires on a fabricated `sk-` string. **The two environment variables were not set in the shell
that ran the scan, so the literal-value half of the check could not be made there and is not claimed
here.** The pattern half is the half that catches a key the file itself carries, which is how a
credential would arrive in a run record; the literal half is a belt on top of it.
