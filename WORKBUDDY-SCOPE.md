# WorkBuddy file scope

This directory is the complete permitted workspace for WorkBuddy.

Allowed development-time data references:

- `data/cases/`
- `data/external/`
- `data/index.json`
- `data/PUBLIC-CONTRACT.md`
- `policy/`

`data/PUBLIC-CONTRACT.md` is the answer-free implementation contract for this workspace. It may be read during development, but it may not be copied into, attached to, or serialised inside an Agent runtime bundle.

Allowed project files:

- `README.md`, `START-HERE.md`, `WORKBUDDY-HANDOFF.md`, this file, `.gitignore`, `requirements.txt`
- `tribunal/`, `prompts/`, `tests/`, `eval/`, `ui/`, `runs/`, `precedents/`
- `docs/buddy-log/`, `docs/notes/`, `docs/submission/`

The following material is physically outside this workspace and must never be requested, copied, indexed, attached, or used in a runtime prompt: corpus generation sources, historical case analyses, prior manuals, old PDFs, render outputs, private virtual environments, and any offline grading harness or scoring index that is not part of this repository. The evaluation answer key is no longer on this list: it lives at `eval/answers/` and is committed, under the controls stated in the section below.

Runtime Agents receive the public content of one selected case file and the selected policy files only. They never receive `data/PUBLIC-CONTRACT.md`, `data/index.json`, the answer key at `eval/answers/`, generated source corpus, case study, offline grader, or developer handoff containing expected outcomes.

The forbidden-key safety assertion applies recursively to the final serialised Agent runtime bundle, not to development-time documentation. Path restrictions protect against corpus-generation sources and historical analyses; forbidden-key assertions protect against answer fields leaking into a runtime bundle. These are separate controls.

## Evaluation answer key (amended 2026-09-21)

The evaluation answer key lives at `eval/answers/` and **is committed**. This repository is published as the submitted source, and an accuracy claim a judge cannot reproduce is worth nothing, so the key travels with the code it measures. This is the one narrow respect in which the original blanket rule against answer keys has been relaxed, and it is relaxed for exactly this one directory. Nothing else in the paragraph above is relaxed.

Four statements hold. The path controls are kept distinct from the forbidden-key control, as they are above:

- **Path, relaxed for one directory.** The key lives at `eval/answers/` and is committed. No sibling or ancestor directory is affected by this relaxation.
- **Path, tightened.** Nothing under `tribunal/` may read anything under `eval/`. The package that builds the runtime bundle has no business in the answer key, whichever directory that key sits in.
- **Forbidden keys, unchanged and still the stronger control.** No answer field may appear in any Agent runtime bundle. This control holds wherever an answer came from, including a case file that was edited by hand, so it is the one that actually protects the run.
- **Path restrictions, unchanged elsewhere.** Corpus generation sources, historical analyses, prior manuals, old PDFs and render outputs remain outside the workspace and are still never referenced.

`tests/test_answer_isolation.py` asserts both path and content controls, and proves the content check is capable of failing.

## External material (amended 2026-09-23)

The organisers supplied a sample case to every team. It lives at
`eval/external/` and it is **answer-bearing**: it states an expected ruling and
carries an argument for one side. It therefore sits under the same boundary as
`eval/answers/`, for the same reason and with the same force.

Four statements, kept distinct as above:

- **Path.** `eval/external/` holds answer-bearing external material. Nothing
  under `tribunal/` may read anything under `eval/`, and that includes
  `eval/external/`. The material is not agent input and must never be attached
  to, copied into, or serialised inside a runtime bundle.
- **Converted cases.** `data/external/` holds cases converted from that
  material. They are **answer-free** and agent-visible under the same contract
  as `data/cases/`: a converted case carries no expected ruling, no answer
  field, and no argument for either side. Only the source's own case facts
  cross the boundary.
- **One direction.** Conversion runs `eval/external/` to `data/external/` and
  never the other way. Nothing writes into `eval/`, and the frozen answer key
  at `eval/answers/` is not a conversion target.
- **Where the converter lives.** The converter sits under `eval/external/`,
  beside the source it must read. It cannot sit under `tribunal/`, because a
  module in the package that names a path under `eval/` is exactly what
  `tests/test_answer_isolation.py` forbids.

`data/external/` is **not** in `data/index.json`. The manifest indexes the
29-case corpus the benchmark measures, and adding a converted case to it would
change that corpus. An external case is loaded through its own explicit path,
under every constraint that does not depend on a manifest entry.

Every place the conversion had to judge rather than copy is recorded in a
mapping record committed beside the converted case, so a reader can see the
choices and not only their results.

## Second development set (amended 2026-09-25)

A second development set was added: fifteen cases drafted by OpenAI Codex on
2026-09-24, copied in by the owner. Two new paths, and they sit on opposite
sides of the boundary above.

- **`data/external/codex/` — agent-visible, answer-free.** Fifteen case files
  (`case-09101.json` to `case-09115.json`) and the set's own `index.json`. The
  cases are answer-free under the same contract as `data/cases/`: no expected
  ruling, no answer field, and no argument for either side. The set's index is
  **not** `data/index.json` and is never merged into it — `data/index.json` still
  indexes the 29-case corpus the benchmark reports, and adding a case to it
  would change that corpus. The set is loaded by number through
  `tribunal.loader.load_external_set_case`, which enforces the same constraints
  that do not depend on the corpus manifest, and additionally holds each file to
  the digest its index entry records.
- **`eval/answers/codex/ground_truth.json` — answer-bearing.** The set's own
  key, under the same boundary as `eval/answers/ground_truth.json`, for the same
  reason and with the same force. It is a second answer key and therefore a
  second way for an answer to reach a brief, so nothing under `tribunal/` may
  read it; `tests/test_answer_isolation.py` asserts that over this key as well
  as over the corpus key.

The two keys are separate files and are never merged. A run of the second set is
graded against its own key, records that key's digest as its provenance, and is
written under `runs/codex/` — never into `runs/<model>/`, which holds the corpus
result the submission reports. Both checks are made rather than intended.

The set's own stated expectation, if it ever has one, belongs at
`eval/external/codex/expected.json`. The organisers' sample case keeps its own
at `eval/external/ryde/expected.json`, and a case is printed beside the
expectation belonging to it and never beside another case's.

## Precedent library (amended 2026-09-28)

A precedent library was added: `precedents/precedents.jsonl`, an append-only,
hash-chained store of decisions a human reviewer has closed. It is not an answer
key and it is not policy.

- **Path.** `precedents/` joins the allowed project files above. It holds a store
  built from closures a person made, and nothing in it is derived from `eval/`.
- **What changes at runtime, and only when asked.** With `--precedents` on, the
  judge's user message carries one more key, `precedents`: a fixed note and up to
  three items, each naming a `precedent_id`, a `category`, clause ids and a
  ruling. **No amount and no summary travel in the block.** With the switch off
  the key is absent entirely and the judge's message is the message it always
  was.
- **What does not change.** No answer field reaches the block. An entry may carry
  no field name from `loader.FORBIDDEN_KEYS` and none of `rationale`,
  `difficulty`, `governing_clauses`, `matched`, `expected` or `grade`; the check
  is recursive and runs before anything is written, and the same walk is applied
  to the parsed judge message at runtime whenever the key is present.

## Policy-gap loop (amended 2026-09-29)

A loop was added that finds the cases the policy could not decide, groups them,
and — for a group a person has closed at least twice — asks a model to draft one
clause that would decide them. It is the only thing in this repository that can
add to the policy, and it can do so only through a person.

- **Path.** `policy/proposals/` holds drafts; `policy/amendments/` holds the
  approved ones. Both sit under `policy/`, which is already an allowed
  development-time reference, and that is deliberate: an approved amendment is
  *meant* to change what every later brief says, so it must be agent-visible
  and it must be committed. A **proposal** is not applied by anything — no
  loader reads `policy/proposals/`, and the drafter's answer changes no run
  until a person runs `approve`.
- **What crosses the boundary, and in one direction.** `eval/policy_gaps.py` is
  a module under `eval/`, so it may read `eval/answers/`; the scope rule that
  binds `tribunal/` does not bind it. Exactly one of its commands reads the
  frozen key, `diff`, and it reads it to grade each development-set case before
  and after and says so in its own output. Nothing in it writes to `eval/`, and
  the key is never edited. `report` and `draft` are shown to work with the key
  loader made to fail.
- **What the drafter is given.** The loaded policy, a cluster's cases with each
  artifact's `evidence_id`, `evidence_type`, `admissibility` and `derived`
  facts, and the human closures on those cases. No raw payload, no `matched`, no
  grade event, no answer key. The same recursive forbidden-field check the
  precedent library applies to an entry is applied to the assembled document
  before it leaves the module, so the control is one function in one place.
- **What a draft may not do.** It carries one clause of exactly the eight clause
  fields, an id that is the next free number for its prefix, a category that
  agrees with both the prefix's file and the cluster, `licenses` within what
  POL-GEN-03 licenses, and clause references that all resolve in the loaded
  policy. An amendment adds one clause and can never edit or remove one — the
  key set is exact, so there is nowhere to write one. A draft that fails any
  check is recorded as `REJECTED_BY_CODE` beside its transcript and never
  becomes an amendment.
- **Where its figures go.** `runs/policy-gaps/` holds the report; a re-run at a
  new version goes to `runs/policy-v<N>/` like any other version-N run. The
  report's destination is refused if it is a run directory or lies under one,
  and a run directory under `runs/external/` is refused as a source.

## Viewer (amended 2026-09-29)

The viewer — `ui/build.py` and the page it commits at `ui/dist/index.html` — is
unchanged in what it may read, and two rules about it are now written down.

- **Money is formatted at display time and only there.** The data block keeps
  the literals the run recorded, as strings, and the page's own script turns
  them into two decimals when it renders them. `eval.grade.render_money` is
  unchanged, and so is every money value in the document; a change that moved
  the rounding into Python would be a change to the data and is not what the
  page's rule is.
- **It reads no new file.** The viewer newly shows two blocks that already
  travel on a case file under `runs/`: the vote's `verification` (present only
  when the draft verifier ran) and the case's `precedents_shown` (present only
  when the precedents switch was on). The precedents panel shows the ids the run
  recorded it put in front of the judge; the viewer does **not** read
  `precedents/precedents.jsonl`, and nothing in `ui/` reaches it. Both panels
  are drawn only when their block is present, so a run with either switch off
  shows neither.

## Review fixes (amended 2026-09-29)

An independent review at `db1846c` traced five groups of defects through the
code and tried, and failed, to refute them. All five are fixed. **The review
changed no path this workspace may read**, and the four statements below are
about where a result may be written, which is the part of the boundary that is
held by code rather than by convention.

- **The headline run directory stays the headline.** `runs/<model>/` holds the
  result the submission reports, and three ways in were closed. A replay now
  refuses a source briefed at a policy version other than the new run's, in both
  command lines and in `check_replay` — before this, replaying a version-2 source
  into a plain run briefed the judge at version 2, wrote into `runs/<model>/` and
  recorded version 1. A baselines destination is now checked against the runs
  root it was given **and** the repository's own, because `--runs-dir` and
  `--out-dir` are separate arguments and a scratch root made the repository's
  `runs/` look safe. And `--policy-version` below 1 is refused while the command
  line is read, so a version that names nothing never reaches a client or a
  destination.
- **A switch that is on says so.** With `--precedents` on and nothing matched,
  the transcript omitted `precedents_shown` while the case file wrote `[]`. Both
  records now carry the empty list. `None` still means the switch was off, and
  the judge's message is unchanged — with nothing matching there is no
  `precedents` key on it, exactly as with the switch off.
- **The viewer reads no new file.** Reaffirmed: the fix to its Judge step adds
  one helper that appends only a real node. It still reads nothing but a case
  file under `runs/`, and it still does not read `precedents/precedents.jsonl`.
- **No test writes under `runs/`.** The standing rule, restated because this
  work broke it: the two command-line tests holding the `--policy-version`
  refusal ran without `--runs-dir`, so with that guard removed they created
  `runs/policy-v0/<model>/` in the repository. Both now pass a scratch root.

Nothing under `tribunal/` reads anything under `eval/`; that control is
unchanged by all of this.

## The verifier measurement (amended 2026-09-29)

The draft verifier was measured on both development sets and the output is
committed. **No path this workspace may read was added**, and the answer key is
untouched.

- **What was read.** `runs/deepseek-deepseek-flash/` and
  `runs/codex/deepseek-deepseek-flash/` — the source runs' own recorded
  transcripts — plus the case files, `policy/` and `prompts/`. Nothing under
  `eval/` was read: the measurement compares a draft against the **brief** it was
  handed, which is a runtime artifact, and never against `eval/answers/`. The key
  stays frozen.
- **What was written.** Only
  `runs/verify-recorded-drafts/<model>/` and
  `runs/<set>/verify-recorded-drafts/<model>/`, three files each. The headline
  run directories were not written to, and the destination check that makes that
  a property of the path is unchanged.
- **What the committed files are.** The verifier's own output, committed exactly
  as produced, with the one killed invocation left in each `events.jsonl` as it
  was found. No case file, policy file or prompt was changed by this work, and
  the verifier and its prompt are unchanged.
- **One recorded figure is not the brief's.** The verifier's `brief_value` is
  what the *verifier* holds the brief to say, and three of the fifteen material
  contradictions quote a value the brief does not contain. Reading them as
  quotations of the brief is wrong; `docs/notes/2026-09-29-the-verifier-measured.md`
  says which and why.

## The admissibility ablation measurement (amended 2026-09-29)

The `admissibility` ablation was measured on both development sets and the output
is committed. **No path this workspace may read was added**, and the answer key is
untouched.

- **What was read.** The two committed ablation directories themselves
  (`runs/ablation/admissibility/deepseek-deepseek-flash/` and
  `runs/codex/ablation/admissibility/deepseek-deepseek-flash/`), the two headline
  runs they are compared against, `data/cases/` and `data/external/codex/` for the
  impaired and missing artifacts, `policy/`, and `tribunal/brief.py` to rebuild
  each case's brief. The answer key was read **only** through
  `eval.grade.load_answer_key`, for grading the four run directories and for
  quoting each differing case's expected ruling. Nothing under `tribunal/` reads
  `eval/`, and the key stays frozen.
- **What was written.** `runs/ablation/admissibility/<model>/` and
  `runs/codex/ablation/admissibility/<model>/` — written by the owner outside this
  workspace, not by it — plus the note and this section. No case file, policy file
  or prompt was changed by this work, and the ablation switch itself is unchanged:
  it applies only in `build_brief_for_case`, is off by default, and is refused
  together with every replay flag.
- **What the committed files are.** The owner's output, committed exactly as
  produced: two invocations per directory, with the first pass's failures left in
  each `events.jsonl` and the 900-second retry beside them.
- **One figure the note refuses to over-read.** The corpus drop from 29/29 to
  26/29 is three cases, but only 112 moved unanimously. On 107 and 211 the
  headline panel was already split 3 of 4, so one sampled run per condition cannot
  separate the ablation's effect from sampling variation on those two, and 9111's
  amount was already wrong before the ablation ran.
  `docs/notes/2026-09-29-the-admissibility-ablation.md` says so in its own words.

## The clause-notes ablation and the sample-case re-run (amended 2026-09-30)

The `clause-notes` ablation was measured on both development sets, and the
organisers' sample case was re-run under the current pipeline. Both outputs are
committed. **No path this workspace may read was added**, and the answer key is
untouched.

- **What was read.** The three committed directories themselves
  (`runs/ablation/clause-notes/deepseek-deepseek-flash/`,
  `runs/codex/ablation/clause-notes/deepseek-deepseek-flash/` and
  `runs/rerun-2026-09-29/external/ryde/`), the four runs they are compared
  against, `data/external/ryde/case-00901.json`, `policy/`, `prompts/`, and
  `tribunal/brief.py` to rebuild each case's brief. The answer key was read
  **only** through `eval.grade.load_answer_key`, for grading the six directories
  and for quoting each differing case's expected ruling. Nothing under
  `tribunal/` reads `eval/`, and the key stays frozen.
- **What was written.** The two `runs/ablation/clause-notes/<model>/`
  directories and `runs/rerun-2026-09-29/external/ryde/` — written by the owner
  outside this workspace, not by it — plus the note and this section. No case
  file, policy file or prompt was changed by this work, and the ablation switch
  itself is unchanged.
- **What the committed files are.** The owner's output, committed exactly as
  produced: one invocation per directory, all 44 ablation cases completed on the
  first pass, and the sample case re-run in a runs root of its own so the
  committed schema-1 result stayed as it was.
- **One figure the note refuses to over-read.** The corpus drop from 29/29 to
  27/29 is two cases, and both were already carried 3 of 4 in the headline, so
  one run per condition cannot separate the clause-notes ablation's effect from
  sampling variation on 107 and 211. Only 112 moves cleanly, and it moves under
  the *other* ablation — it misses only when the admissibility precheck is
  removed. `docs/notes/2026-09-30-the-clause-notes-ablation-and-901.md` says so
  in its own words.

## The held-out set (`wild-v1`) (amended 2026-09-30)

A held-out set was added: 64 cases under `data/external/wild/`, keyed by
`eval/answers/wild/ground_truth.json`. It is **not** a third development set. It
was drafted without access to this repository, it is run **exactly once** from
the commit tagged `freeze-2026-09-30`, and that single run is the only
generalisation figure the submission reports.

- **`data/external/wild/` — agent-visible, answer-free.** Sixty-four case files,
  `case-00501.json` to `case-00627.json` and not contiguous, plus the set's own
  `index.json`. Answer-free under the same contract as `data/cases/`: no expected
  ruling, no answer field, and no argument for either side. The set's index is
  **not** `data/index.json` and is never merged into it — the manifest still
  indexes the 29-case corpus the benchmark reports. The set is loaded by number
  through `tribunal.loader.load_external_set_case`, the loader the second
  development set already uses.
- **`eval/answers/wild/ground_truth.json` — answer-bearing.** The set's own key,
  under the same boundary as `eval/answers/ground_truth.json` and
  `eval/answers/codex/ground_truth.json`, for the same reason and with the same
  force. It is a third answer key and therefore a third way for an answer to
  reach a brief, so nothing under `tribunal/` may read it.
- **`eval/external/wild/` — answer-bearing.** The set's own generator, its
  manifest, its evaluation index, its seed map, its summary table and its
  author's README. Nothing under `tribunal/` may read any of it. It is
  answer-bearing at case level: the README names cases and the outcome the
  policy gives for each.
- **One direction.** Nothing writes into `eval/`. The key is frozen from the
  moment it is imported, under the standing rule in `START-HERE.md`.
- **Where its run goes.** `runs/wild/<model-slug>/` — never `runs/<model-slug>/`
  and never `runs/codex/<model-slug>/`. All six destinations that must not write
  into a reported result refuse it: the ablation, the precedents block, a later
  policy version, the baselines, the policy-gap report and the recorded-drafts
  measurement. `--force`, `--replay-advocates`, `--replay-check` and
  `--verify-recorded-drafts` are refused for this set in code, because a case
  that has a result must never be re-run.
- **A conflict, recorded rather than resolved.** The archive's own README calls
  this 64-case set a development and regression set, and names a **different,
  24-case** set as the sealed one. `docs/notes/2026-09-30-the-freeze-and-the-sealed-run.md`
  records that in its own words, and it is the owner's to settle before any
  figure from the run is reported as generalisation. That README arrived in
  Chinese and was for a time the eleventh tracked file holding Chinese
  characters; on 2026-09-30 it was **translated into English**, and the standing
  language rule below now governs every tracked text file outside `runs/`. The
  author's original bytes are kept in the repository's history at `3cb059a` and
  hash to
  `8761344077eb9ef2a238c047a18b71b0f6b8f1855d1baeb63ab0ba89e1c9befb`.

## The second sealed set (`wild-v2`) (amended 2026-10-03)

A second sealed set was imported on 2026-10-03: 20 cases under
`data/external/wild-v2/`, keyed by `eval/answers/wild-v2/ground_truth.json`. It is
**not** a third development set and **not** the held-out set. It was prepared by
OpenAI Codex for the owner and imported from the archive whose sha256
`docs/notes/2026-10-03-the-second-freeze.md` records; it is run **exactly once**
from a commit whose `tribunal/`, `prompts/` and `policy/` trees equal those at
`freeze-2026-10-03` — which need not be the tagged commit itself, and the run's
own events record the commit it was made from. That single run is the
submission's generalisation figure. Its registration fixes policy version 2.

- **`data/external/wild-v2/` — agent-visible, answer-free.** Twenty case files,
  `case-00701.json` to `case-00720.json`, plus the set's own `index.json`. The
  twenty case files are byte-identical to the ones the archive shipped and are
  answer-free under the same contract as `data/cases/`: no expected ruling, no
  answer field and no argument for either side. `index.json` is not: it changed
  in its `file` field only, which names the flat layout `wild-v1` uses. The index
  is **not** `data/index.json` and is never merged into it. The set is loaded by
  number through `tribunal.loader.load_external_set_case`.
- **`eval/answers/wild-v2/ground_truth.json` — answer-bearing.** The set's own
  key, under the same boundary as the other three, for the same reason and with
  the same force. It is a fourth answer key and therefore a fourth way for an
  answer to reach a brief, so nothing under `tribunal/` may read it. It arrived
  as an object keyed by case number and was re-wrapped into the array the grader
  reads in a commit of its own; every record's four graded fields and its
  difficulty were compared, parsed, before and after.
- **`eval/external/wild-v2/` — answer-bearing.** The author's README and
  manifest, the seed map and seed selection, the semantic check and its legacy
  companion, the validation output and the generator. Nothing under `tribunal/`
  may read any of it. It is answer-bearing at case level: the seed map carries
  each case's author ruling, the semantic check carries a derivation and a
  calculation for each of the 20, and the legacy difference report names the
  five cases it differs on. The README itself names only the case range.
- **One direction.** Nothing writes into `eval/`. The key is frozen from the
  moment it is imported, under the standing rule in `START-HERE.md`.
- **Where its run goes.** `runs/wild-v2/<model-slug>/`, and **never** a
  `policy-v2` directory inside it: its registration fixes policy version 2, so
  the version briefs every case at version 2 without moving the run one level
  down. `--policy-version` is refused for this set in code, as are `--force`,
  `--replay-advocates`, `--replay-check`, `--verify-recorded-drafts`,
  `--ablate`, `--precedents` and `--amount-rule`. The component-wise path guard
  closes `runs/wild-v2/` to everything but the plain sealed run's own directory,
  so nothing else can be created under it.
- **Four headline directories now, not three.** `SET_RUNS_SUBDIRS` names
  `codex`, `wild` and `wild-v2`, so `runs/wild-v2/<model-slug>/` is refused by
  every destination that must not write into a reported result — the ablation,
  the precedents block, a later policy version, the baselines, the policy-gap
  report and the recorded-drafts measurement — exactly as the other three are.
- **It is never combined.** It is not in `DEVELOPMENT_SETS`, so `--set all` does
  not run it and the combined figure does not sum it; it is not in `ALL_SETS`, so
  the recorded-drafts measurement does not read it, because it has not been run.
  It is printed in a section of its own, beside the held-out set's and never
  inside it.

## The new rule that comes first (amended 2026-10-03)

**Nobody runs the sealed set.** It is run once, by the owner, outside this
workspace, and that single run is the figure the submission reports. Everything
below is what keeps that true rather than intended.

- **The command needs an opt-in.** A `--set wild-v2` invocation that would run
  anything is refused unless `TRIBUNAL_SEALED_RUN=wild-v2` is in its environment.
  The check comes after every other refusal, so an invocation that names a
  refused switch is told about the switch, and before any client is built and
  before any directory is created. The message names the variable and says the
  run is made by the owner only. **Nothing in this repository sets that
  variable**, and the owner sets it for that one command:
  `TRIBUNAL_SEALED_RUN=wild-v2 python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900`.
- **`--check` is how anyone else looks at it.** It applies every refusal and
  every frozen-argument check, then applies the sealed protocol to the existing
  `events.jsonl` if there is one and prints the cases a plain invocation would
  run and the cases it would not, each with its reason. It exits 0, builds no
  client, writes nothing, creates no directory and needs no opt-in:
  `python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900 --check`.
- **No probe and no test may reach the network for it.** A test may reach the
  command line only with `LLMClient` patched to raise, or a raising
  `client_factory` passed, and only over a temporary runs root. The tests that
  invoke it do so through one helper that patches the class, so a test that
  would build a client fails instead of calling a model.
- **The one partial run is recorded.** A probe started the run for real on
  2026-10-03 at 14:14, was stopped at 14:17:31, and its `events.jsonl` was
  deleted. The facts, the deletion and the owner's decision that `wild-v2` stays
  the sealed set are in
  `docs/notes/2026-10-03-the-sealed-protocol-made-executable.md`, under *The
  partial run of 14:14, and the owner's decision*. Under the sealed protocol that
  attempt does not count, because it ended with no terminal event.

## The second sealed set's run (amended 2026-10-04)

The second sealed set was **run once, by the owner, on 2026-10-04**, from a commit
whose `tribunal/`, `prompts/` and `policy/` trees equal those at
`freeze-2026-10-03`, and its 45 output files are committed at
`runs/wild-v2/deepseek-deepseek-flash/`. That run is the second generalisation
figure the submission reports. This section supersedes the statements above that
the second sealed set has not been run, that the held-out set's run is the only
generalisation figure and that the second sealed set's run is the submission's
generalisation figure; and it supersedes the statement that the component-wise
path guard closes `runs/wild-v2/` to everything but the plain sealed run's own
directory — the root is closed to that too, and nothing is created under it
again.

- **The run was made, and it is the owner's.** One invocation, one pass over the
  20 cases, no case failed:
  `TRIBUNAL_SEALED_RUN=wild-v2 python3 -m eval.development_sets --set wild-v2 --concurrency 2 --timeout 900`.
  The owner's run made the model calls; none was made in this repository in
  committing or reading it. The run was not re-run, edited or regenerated by
  anything here.
  `docs/notes/2026-10-04-the-second-sealed-run.md` reads it, and
  `docs/notes/2026-10-04-wild-v2-run-manifest.txt` records the digest of every one
  of the 45 files, checked by `tests/test_wild_v2_run_manifest.py`.
- **The root is closed outright.** `runs/wild-v2/` is in
  `MADE_SEALED_RUNS_SUBDIRS`, exactly as `runs/wild/` is, so no permit opens it:
  nothing is created under it again, the plain sealed run included, and every
  destination that must not write into a reported result refuses it.
- **There are two generalisation figures, and they are never pooled.**
  `wild-v1`'s 55/64 and `wild-v2`'s 18/20 are each their own figure, from their own
  freeze, over their own set. One figure over 64 cases plus another over 20 is not
  a measurement of 84 cases, and neither figure is ever added to a development
  figure, to the other, or to the combined line. **`wild-v1` is not "the only
  generalisation figure"**, and neither is `wild-v2`.
- **`wild-v2` stays out of `ALL_SETS` because it is a sealed record.** It is
  absent from `ALL_SETS` — what the amount-rule and recorded-drafts measurements
  read — not because a run was pending: both measurements have committed figures
  over the other three runs. It is still not in `DEVELOPMENT_SETS`, so `--set all`
  does not run it and the combined figure does not sum it. `SEALED_SETS` now names
  both sealed sets, and `headline_run_directories` names four directories.
- **One interrupted attempt does not count.** The probe of 2026-10-03 at 14:14
  partly called cases 701 and 702; its record was deleted and the owner ruled
  before the run that the attempt does not count under the sealed protocol. It is
  recorded under *The partial run of 14:14, and the owner's decision* in
  `docs/notes/2026-10-03-the-sealed-protocol-made-executable.md`.

## The amount read-off rule (amended 2026-09-30)

An amount in a draft is read off a brief when it is a figure the brief's money
block publishes, or the **sum** of two or three of them. That rule is why two
cases of the held-out run produced no ruling at all: 517 and 533 each drafted the
key's amount as a **difference** — `51.30 - 29.00 - 3.00` for 533 — so
`DRAFT_AMOUNT_NOT_READ_OFF` rejected every draft and the panel had nothing left to
reduce.

- **The second rule.** `--amount-rule signed` accepts a published figure or a
  **signed** combination of two or three: the leading term positive, the result
  above zero, two-term differences tried before three-term combinations. It is a
  second reading of the same drafts, not a second policy. `AMOUNT_RULE_PUBLISHED`
  is the default; `AMOUNT_RULE_SIGNED` is opt-in and `AMOUNT_RULES` names both.
- **Off is byte-identical.** A run without the switch writes exactly what it wrote
  before, file for file. The rule reaches the artifacts only as a sixth key of the
  configuration document, and only when it is not the default.
- **Where a signed run goes.** `runs/amount-rule/<rule>/<model-slug>/`, by
  `run_benchmark.amount_rule_run_directory`, guarded by
  `assert_amount_rule_destination`, which checks the destination against *this
  rule's* root rather than against `amount-rule/*` so that a signed run cannot land
  in the published one's. The three directories that hold the reported figures —
  `runs/<model-slug>/`, `runs/codex/<model-slug>/` and `runs/wild/<model-slug>/` —
  are refused, as they are for the ablation, the precedent block and a later policy
  version. `--compare`, `--replay-check`, `--verify-recorded-drafts` and
  `--external` are refused beside the switch in code, and it is mutually exclusive
  with `--ablate`, `--precedents` and `--policy-version N>=2`.
- **The measurement.** `eval/amount_rule.py` re-reduces each run's **recorded**
  drafts under both rules with no model call, reusing the assembly
  `eval/verify_drafts.py` and `eval/baselines.py` already use. Its output is
  committed at `runs/amount-rule/report.md` and `runs/amount-rule/amount-rule.json`,
  and `runs/README.md` describes the directory. Over the 108 cases read across the
  three runs, 0 refused: 98 match the key under both rules, **no case** is turned
  from a match into a miss, 533 is turned from a miss into a match, and **501 is a
  safe outcome turned into a monetary ruling that differs from the key** —
  `ESCALATE` under the published rule, `PARTIAL_REFUND 8.5` under the signed one,
  against a key of `PARTIAL_REFUND 14.5`.
- **What the freeze check now says.** The owner's check
  `git diff --quiet freeze-2026-09-30 -- tribunal prompts policy` no longer comes
  back clean, because the second rule lives in `tribunal/pipeline.py`. The tag is
  unchanged and the run recorded from it stands; what has moved is the working tree
  beneath it. `prompts/` and `policy/` are untouched, and the default path is
  byte-identical by test, so a run made from the tree and the run made from the tag
  agree on every case the default rule reaches.
- **The default is not changed.** `docs/notes/2026-09-30-the-amount-read-off-rule.md`
  gives the table and the recommendation: adopt `signed` in a later policy version,
  but close the 501 shape first and then re-measure on a fresh held-out set. Nothing
  in this repository adopts it yet.

## Every named destination refuses a sealed root (amended 2026-10-04)

Both sealed roots — `runs/wild/` and `runs/wild-v2/` — and all four headline
directories are now refused by **every command that writes to a path a user
names**, through one helper, `eval.sealed_roots.refuse_a_sealed_destination(path,
runs_dir)`. It refuses any path under a sealed root, comparing path components
case-folded, against both the runs root it was given and the repository's own; it
refuses any headline directory; and its message names the path only.

- **The commands it guards.** `run_benchmark --external` (inside
  `assert_external_run_directory`), `eval.grade --out`, `ui.build --out`,
  `policy_gaps draft --proposals-dir` and `policy_gaps approve --amendments-dir`.
  Each refuses before anything is created or written, and `eval.grade --out` in
  particular can no longer overwrite a committed `report.md` in either sealed root.
- **The four routed guards.** The recorded-drafts measurement, the baselines, the
  amount-rule measurement and the policy-gap report now call the same helper and
  re-raise their own error type around it, so each command's own refusal sentence
  is unchanged while the rule lives in one place.
- **The tests.** `tests/test_sealed_roots_closed.py` pins one test per call site,
  for both sealed roots, over a scratch root, and shows each red with the call
  removed; a `grade --out <scratch>/wild-v2/<slug>/report.md` is refused and the
  committed report is left byte-identical.
- **One write path is not guarded.** `tribunal.precedents --store` is named as the
  one place a person can still write a sealed root's path: `tribunal/` imports
  nothing from `eval/`, so the evaluated system stays byte-identical to the tag and
  the store is left to whoever names it.

## Language rule (standing)

Every document in this repository is written in English, and every prompt pasted into WorkBuddy is written in English. No Chinese characters in any tracked text file.

*Amended 2026-09-30.* The rule governs every tracked text file **outside `runs/`**. Nine files under `runs/` carry one Han character, `U+7684`, because it sits in the macOS path the machine recorded when it wrote them. Those files are records produced by a run and are left unedited: rewriting one so that a scan comes back clean would be editing the evidence. `tests/test_language.py` enforces the rule outside `runs/` and names `runs/` as the one exemption.

Before every task, WorkBuddy must read this file and state the file paths it plans to open. It must not recursively scan the workspace or refer to sibling directories.
