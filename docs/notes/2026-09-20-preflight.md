# Preflight Note — 2026-09-20

Project: Tribunal — Tencent Cloud AI Singapore Hackathon 2026, Digital Native track, challenge set by Ryde.
Task: read-only preflight verification. No application code was written in this task.

## Files read in this task (exact paths)

1. `/Users/hanweizhou/Desktop/Tribunal/WORKBUDDY-SCOPE.md` (read boundary for this project)
2. `/Users/hanweizhou/Desktop/Tribunal/README.md`
3. `/Users/hanweizhou/Desktop/Tribunal/WORKBUDDY-HANDOFF.md`
4. `/Users/hanweizhou/Desktop/Tribunal/requirements.txt` (read to report contents verbatim)

## Actual working directory

```
/Users/hanweizhou/Desktop/Tribunal
```

Confirmed by running `pwd`, which returned `/Users/hanweizhou/Desktop/Tribunal`.

## Real top-level listing

Output of `ls -1A` (top level only, no recursion):

```
.DS_Store
.gitignore
README.md
START-HERE.md
WORKBUDDY-HANDOFF.md
WORKBUDDY-SCOPE.md
data
docs
eval
policy
prompts
requirements.txt
runs
tests
tribunal
ui
```

No recursive scan was performed.

## Real Python version

```
Python 3.13.12
```

(managed runtime at `/Users/hanweizhou/.workbuddy-ai/binaries/python/versions/3.13.12/bin/python3`)

The system fallback on this machine reports `Python 3.9.6`.

## Exact current contents of requirements.txt

File: `/Users/hanweizhou/Desktop/Tribunal/requirements.txt` — 2 lines, 155 bytes.

```
# The initial loader and policy modules use the Python standard library only.
# Add runtime dependencies only when a later, accepted module requires them.
```

This is the entire file. Both lines are comments. **Confirmed: requirements.txt declares no dependencies.** No dependency was added, installed, or invented in this task, and no virtual environment was created.

## Application implementation status

The application is not implemented yet. This workspace currently contains:

- no agent code,
- no runtime model integration, and
- no user interface.

The directories `tribunal/`, `prompts/`, `tests/`, `eval/`, `ui/`, and `runs/` exist as empty scaffolding. Per `README.md` and `WORKBUDDY-HANDOFF.md`, the planned application (a Python package `tribunal/` with a Streamlit UI and a single model adapter) has not been built.

## Commands actually executed in this task

```
pwd
ls -1A
/Users/hanweizhou/.workbuddy-ai/binaries/python/versions/3.13.12/bin/python3 --version
/usr/bin/python3 --version
wc -l -c requirements.txt
ls -d docs/notes
```

## Files created or changed in this task

Only this note: `docs/notes/2026-09-20-preflight.md`.

No other file was created, modified, or deleted. No git repository was initialised or published. No paid model API was called.
