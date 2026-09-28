# Provenance, currency, and the three defects found on the way

2026-09-28. Queue 2026-09-28, task 1. No model call was made.

## 1a. The run's configuration, recorded on every artifact

`judge_votes` and `verify_drafts` appeared only on the `invocation_start` event, which is a line in an
append-only log. A case file could not say how many drafts its judge was asked for, and a reader of
one case file had to open the invocation that produced it to find out.

Every artifact a run writes now carries one `configuration` object with five fields: `judge_votes`,
`verify_drafts`, `ablation`, `precedents` and `policy_version`. It is on `run.json`, on each entry of
`invocations.json` and on each `case-*.json`. `ablation` and `precedents` are written as `null` and
`policy_version` as `1` today, so the object's shape does not move when tasks 3 to 6 add the switches
that give those three a value.

`run_benchmark.configuration_document` builds it and `run_benchmark.configuration_of` reads it back,
two ways:

- for staleness, replay and reports, a file with no `configuration` counts as what it in fact was: no
  ablation, no precedents, policy version 1;
- for display its `judge_votes` and `verify_drafts` are `None`, which is unknown rather than a
  default. Nothing in such a file says either one, and reporting a default there would invent a fact
  about the run.

**No committed file was rewritten to add the object.** The 44 cached results and the two run
directories still hold the bytes they held, and a reader meets the object only on results produced
from here on. The one test that pins the case file's key set was extended deliberately, with a
comment beside the new key saying why.

## 1b. The corpus could not run into its own directory

`development_sets.run_set` passed `label="corpus"`. The guard in `run_benchmark.run_benchmark`
refuses a labelled run whose destination is `run_directory(RUNS_DIR, model)` — the directory the
corpus *is*. So `python3 -m eval.development_sets --set corpus` and `--set all` raised before a case
ran, and the set that owns `runs/<model>/` was the one set that could not write into it.

The corpus is now run unlabelled. It goes through the same runner, with the same cases, key, loader
and runs directory, and its case files record `development_set: null` — what
`python3 -m eval.run_benchmark` records. The guard itself is unchanged and still refuses a labelled
run aimed at the corpus directory, which is what keeps a second set's results out of the reported
directory.

The tests take the refusal and the fix without touching the repository's own `runs/`:

- `RUNS_DIR` is patched to a scratch root with `mock.patch.object`, and that same path is passed as
  `runs_dir`, so the check is exercised on a destination that is not the repository's;
- both headline directories (`runs/deepseek-deepseek-flash/` and
  `runs/codex/deepseek-deepseek-flash/`) are hashed before and after every refusal test, so a refusal
  that quietly wrote something would be caught rather than assumed away.

## 1c. The report shows currency

`--report` printed the counts and the per-case table but never said whether the results still belong
to this code. It now prints, per set:

```
Currency, each set checked with its own loader and its own briefs:

  corpus   current  29, stale_brief   0, stale_prompts   0, unknown   0
  codex    current  15, stale_brief   0, stale_prompts   0, unknown   0
```

Each set is checked with **its own loader**, through
`run_benchmark.BriefStaleness(run_benchmark.brief_digest_for(S.load_case), run_dir=…)`. Handing a
development set the corpus loader would make every one of its cases read `unknown`: the manifest
cannot name a case it does not list, so no brief is rebuilt and nothing is established. Both sets
read all current, and the two stale counts are the two channels and are never merged into one.

## 1d. The buddy-log table did not render

Rows of `docs/buddy-log/README.md` were separated by blank lines from line 38 onward, and on GitHub a
blank line ends a table: everything after the first one rendered as paragraphs. The 24 blank lines
between rows were removed and nothing else was touched — `git diff` over the file is 24 deletions and
no insertions. The blank line between the last row and the closing paragraph stays, because it
separates the table from the prose rather than splitting the table.

## 1e. Two defects recorded, and neither fixed

**The judge prompt names the referee's output twice over.** `prompts/v1/judge.system.md` calls it
`referee_ledger` on line 24 and `referee_flags` on lines 25 and 43. The judge's user message does not
carry those names: `pipeline._judge_user_message` builds `"referee": {"ledger": […], "flags": […]}`.
The prompt is describing a key path that does not exist.

Not fixed, deliberately. The judge prompt is the one file whose every change is decided separately,
together with the rest of it, before the 6 October freeze — and a prompt edit is not a documentation
edit: it changes what every agent is told to do and stales every cached result.

**`runs/external/ryde/case-00901.json` no longer matches a rebuilt brief.** It is a schema-1 file: it
records `schema_version: 1`, no `vote_agreement` and no `configuration`. Its recorded `brief_sha256`
is `db5b6b955954b4d814053ab13f94e3f37d3de23084dd1f7b4ace7556838b979d`, and the brief this code builds
for the converted case now hashes to
`794030926059b07ba3a9a33544a13d2095b1c0bad5fb4e7633b1cfaeb8b38925`. The external case was amended
after that run — it gained the source's own account of how the arrival marker was made — so the
digest moved and the result is stale on the brief channel.

Not re-run. The owner will re-run it, and a re-run from here would spend tokens on a case that is not
scored and would overwrite the evidence of what the earlier run did.

## 1f. `runs/README.md`

The directory table listed three committed subdirectories and had been overtaken by four more. It now
names every **tracked top-level entry** — `deepseek-deepseek-flash/`, `codex/`,
`deepseek-v4.1-flash/`, `external/`, `_icloud-incident-2026-09-27/`, `hy3/` and `hy4-preview/` — each
with what it is and how to read it. The sentence above the table said "Three subdirectories are
committed deliberately … A fourth, `external/`", which was no longer true and would have contradicted
the table; it now says that every subdirectory named in the table is committed deliberately. The
untracked suite logs are still described as untracked. Each later task that creates a directory adds
its own row.

## Verification

- `python3 -m ui.build --check` — identical to a fresh build, 2,371,908 bytes.
- The nine test modules that import either changed module (`test_run_benchmark`,
  `test_development_sets`, `test_verify_drafts`, `test_external_case`, `test_ui_build`,
  `test_answer_isolation`, `test_events`, `test_grade`, `test_rationale_consistency`):
  `Ran 700 tests in 1194.197s` / `OK (skipped=3)`.
- Discovery count: 1156 collected against 1156 `^\s+def test_` over `tests/*.py`, so no test was
  swallowed by a class body.
- `python3 -m eval.development_sets --report` — corpus 29/29, second set 14/15, combined 43/44, and
  both sets all current.
- Credential scan over the changed files with `sk-[A-Za-z0-9_-]{8,}`: 0 matches, a positive control
  that fires, and the house fake `tok-live-FAKEKEY-…` that does not.
