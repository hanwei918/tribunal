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

## Language rule (standing)

Every document in this repository is written in English, and every prompt pasted into WorkBuddy is written in English. No Chinese characters in any tracked text file.

Before every task, WorkBuddy must read this file and state the file paths it plans to open. It must not recursively scan the workspace or refer to sibling directories.
