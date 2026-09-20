# WorkBuddy file scope

This directory is the complete permitted workspace for WorkBuddy.

Allowed development-time data references:

- `data/cases/`
- `data/index.json`
- `data/PUBLIC-CONTRACT.md`
- `policy/`

`data/PUBLIC-CONTRACT.md` is the answer-free implementation contract for this workspace. It may be read during development, but it may not be copied into, attached to, or serialised inside an Agent runtime bundle.

Allowed project files:

- `README.md`, `START-HERE.md`, `WORKBUDDY-HANDOFF.md`, this file, `.gitignore`, `requirements.txt`
- `tribunal/`, `prompts/`, `tests/`, `eval/`, `ui/`, `runs/`
- `docs/buddy-log/`, `docs/notes/`, `docs/submission/`

The following material is physically outside this workspace and must never be requested, copied, indexed, attached, or used in a runtime prompt: answer keys, offline grading, corpus generation, historical case analyses, prior manuals, old PDFs, render outputs, and private virtual environments.

Runtime Agents receive the public content of one selected case file and the selected policy files only. They never receive `data/PUBLIC-CONTRACT.md`, `data/index.json`, any answer key, generated source corpus, case study, offline grader, or developer handoff containing expected outcomes.

The forbidden-key safety assertion applies recursively to the final serialised Agent runtime bundle, not to development-time documentation. Path restrictions protect against corpus-generation sources and historical analyses; forbidden-key assertions protect against answer fields leaking into a runtime bundle. These are separate controls.

Before every task, WorkBuddy must read this file and state the file paths it plans to open. It must not recursively scan the workspace or refer to sibling directories.
