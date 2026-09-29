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

## Language rule (standing)

Every document in this repository is written in English, and every prompt pasted into WorkBuddy is written in English. No Chinese characters in any tracked text file.

Before every task, WorkBuddy must read this file and state the file paths it plans to open. It must not recursively scan the workspace or refer to sibling directories.
