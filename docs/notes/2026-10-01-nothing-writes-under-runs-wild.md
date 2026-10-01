# Nothing is created under `runs/wild/` again

**2026-10-01, part A3 of the "use wild-v1 as a development set" task. No model
call was made.**

## The rule

`wild-v1` was run once, from the commit tagged `freeze-2026-09-30`. That run
under `runs/wild/` is the held-out record and the only generalisation figure the
submission reports. From 2026-10-01 the same 64 cases are *development data*,
and they may be run again — but **not there**. A second run beside the first
would leave every file a reader looks at apparently intact and change what the
directory means, which is the one failure mode a record cannot survive.

Until this part, the rule was held in six places at most, and each of them named
a *directory* rather than a *root*. `assert_not_a_headline_directory` refuses
the three reported run directories by name. That leaves everything one level
down: `runs/wild/<model>/ablation/…`, `runs/wild/<model>/precedents/…`, a policy
version directory, an amount-rule directory, a policy-gap report, a run at a
later policy version. Every one of those is a way of writing under `runs/wild/`
without touching the run directory itself.

## The one guard

```python
WILD_DEV_RUNS_SUBDIR = "wild-dev"

HELD_OUT_REMEDY = (
    "The same cases are runnable as development data: --set wild-dev writes "
    "under runs/wild-dev/, which is a different directory."
)

def held_out_runs_root(runs_root=RUNS_DIR):
    return Path(runs_root) / SEALED_SET_RUNS_SUBDIR

def assert_not_under_the_held_out_root(destination, runs_root=RUNS_DIR, *, remedy=None):
    root = held_out_runs_root(runs_root).resolve()
    resolved = Path(destination).resolve()
    if resolved == root or root in resolved.parents:
        raise BenchmarkError(...)
    return Path(destination)
```

The comparison is on **path components**, not on the string: `resolved.parents`
walks the resolved destination's ancestors and compares each with the resolved
root. `runs/wild-dev/` is a different component from `runs/wild/`, so the guard
does not catch it — and it must not, because `runs/wild-dev/` is exactly where a
re-run of the same 64 cases is meant to go. A prefix test on the string would
refuse the only place a re-run may go, which is why the half that matters is
asserted in a test rather than described here.

The guard returns the destination unchanged when it is outside, so a caller can
build a path and check it in one expression.

## Where it applies

| call site | what it closes |
|---|---|
| `run_benchmark.run_benchmark` | the run itself, before `run_dir.mkdir(parents=True, exist_ok=True)`. A new `held_out_root` parameter carries the runs root this invocation was asked for, so a scratch runs root is guarded by its own root and not by the repository's; `development_sets.run_set` passes it. |
| `development_sets.main` | `--set wild` combined with any of `--ablate`, `--precedents`, `--policy-version` or `--amount-rule`. Each of the four moves a set's run one level down under the set's own root, so each would write under `runs/wild/`. The message names the switch and points at `--set wild-dev`. |
| `policy_gaps.assert_not_a_run_directory` | `report` and `rerun`, which take a run directory and write beside it. The rule itself is the runner's, so both refuse the same paths; only the closing sentence is the command's own. |
| `policy_gaps.write_diff` | `diff`, whose output directory is `runs/policy-v<N>/` — a version directory beside the run would change what the root means. |

The guard is defined once and called from all four, so there is one statement of
the rule rather than six that can drift apart.

## The tests

`HeldOutRootGuardTests` in `tests/test_sealed_set.py`, five tests.

| test | what it holds |
|---|---|
| `test_every_destination_under_the_held_out_root_is_refused` | eight layouts under `runs/wild/` — the root itself, a model run, an ablation, a precedents directory, a policy-version directory, an amount-rule directory, `verify-recorded-drafts/<model>`, and an arbitrary deep path. Each refusal carries the closing sentence and the `--set wild-dev` remedy. |
| `test_the_re_runnable_sets_root_is_not_caught` | three layouts under `runs/wild-dev/`, returned unchanged |
| `test_every_other_destination_is_not_caught` | seven layouts elsewhere under the runs root |
| `test_the_run_refuses_a_destination_under_the_held_out_root` | `sets.run_set(SEALED, …)` against a **dirty fixture** — a scratch runs root that already holds the held-out set's result. The client factory raises if it is ever called, so a refusal that came after a client was built would fail the test rather than pass silently; the sentinel file is compared byte for byte afterwards and the run directory must have gained nothing. |
| `test_the_command_line_refuses_set_wild_with_each_switch` | the real command line, `--set wild` with each of the four switches, on the same dirty fixture. `run_benchmark.llm.LLMClient` is patched to raise, so a switch that got past the refusal would fail the test instead of making a paid call. |

**Seen to fail first.** Before the guard existed, the same five tests were run
against the unfixed tree: `runs/wild-dev-a3-tests-fail-first.log`,
`Ran 5 tests … FAILED (failures=5, errors=16)`, exit 1. The command-line test
failed with

```
AssertionError: --set wild built a client, so it accepted a switch it must not
```

which is the point of the fixture: without the guard, `--set wild --ablate
clause-notes` really would have run a paid case and written it under
`runs/wild/`. After the guard, `tests/test_sealed_set.py` is
`Ran 32 tests in 38.451s … OK` (`runs/wild-dev-a3-sealed-set-module.log`,
exit 0).

One assertion was corrected while adding the guard: the test first asserted the
phrase `never written again`, which the message does not carry, and the nine
assertions that depended on it failed even though the guard fired. The tests now
assert the phrase the message actually carries.

## What this does not do

- It does not write anything. Every refusal happens before any directory is
  created, and the fixtures are scratch roots under a temporary directory.
- It does not change `--set all`, the registry, the report, the grader or any
  recorded figure.
- It does not close `runs/wild-dev/`. That is where the same cases are meant to
  be run again, and the guard is written so that it is not caught.
