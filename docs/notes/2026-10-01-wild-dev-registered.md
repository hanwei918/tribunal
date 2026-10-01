# `wild-v1` registered as development data (`wild-dev`)

**2026-10-01, part A1 of the "use wild-v1 as a development set" task. No model
call was made.**

`wild-v1` was run once, from `freeze-2026-09-30`. That run is in `runs/wild/` and
is the held-out record: it is never written again. From 2026-10-01 the same 64
cases are development data — their answers may be read, and the system may be
changed to fix what they exposed — and a new sealed set will be run once after
the next freeze, at policy version 2.

Reading the answers is only half of that. Development data has to be **run
again**, and until this part the only registered home for those 64 cases was a
set marked `sealed`, which every re-running switch refuses by name. This part
registers the same cases a second time as `wild-dev`, so that re-running is
possible without touching the single run the freeze names.

## What was added

| | |
|---|---|
| the set | `development_sets.WILD_DEV`, name `wild-dev` |
| its cases | the held-out set's own 64 cases, the same tuple |
| its key | the held-out set's own key, `eval/answers/wild/ground_truth.json` |
| its case root | the held-out set's own, `data/external/wild/` |
| its runs | `runs/wild-dev/<model-slug>/` |
| `sealed` | `False` |

`sealed=False` is the whole of what makes re-running, `--force` and the advocate
replay allowed for it. Each of those is refused by `assert_not_sealed`, which
refuses by name and only for the set marked sealed, so leaving `wild-dev`
unmarked is what opens the three switches — no new switch logic was needed and
none was added.

## What it is kept out of

Four aggregations read a tuple rather than the name table, and `wild-dev` is in
none of those tuples:

| aggregation | reads | holds `wild-dev`? |
|---|---|---|
| `--set all` | `DEVELOPMENT_SETS` | no |
| the combined figure (`combined_figures`) | `DEVELOPMENT_SETS` | no |
| the recorded-drafts measurement (`amount_rule.MEASURED_SETS`) | `ALL_SETS` | no |
| the held-out section of `--report` | `SEALED_SETS` | no |

It is registered instead in a new tuple, `RERUN_SETS`, and `BY_NAME` is built
from `ALL_SETS + RERUN_SETS`, so `--set wild-dev` resolves by name while the four
aggregations above cannot see it. `SET_RUNS_SUBDIRS` is unchanged at
`("codex", "wild")`: `runs/wild-dev/<model>/` is deliberately **not** a headline
directory, because a run belongs there.

`runs/wild-dev/` and `runs/wild/` are different directories, which is what keeps
a re-run from replacing the held-out record. Part A3 closes every other path
into `runs/wild/` in code.

## The report

`python3 -m eval.development_sets --report` gained a section of its own, after the
held-out set's and before the standing development-data caveat:

```
The re-runnable set, on its own, never in the combined figure and never in the held-out set's section:

  set      run directory                            cases      exact  ruling amount driver   refs
  wild-dev runs/wild-dev/deepseek-deepseek-flash     0/64    not run

Currency, checked with the set's own loader and its own briefs:

  wild-dev current   0, stale_brief   0, stale_prompts   0, unknown   0
```

followed by `RERUN_SET_CAVEAT`, which says what a figure there is: a reading of a
set the system has now seen, graded against the held-out set's own key, in a
directory that is not the held-out set's. It is printed in a section of its own
for the same reason the held-out set is — and one more that only it has: its
cases *are* the held-out set's cases, so a reader who found its figure beside the
held-out set's could take a second reading of one set for a second measurement
of it.

Every figure in the report is unchanged. `--report` still prints corpus 29/29,
codex 15/15, combined 43/44, held-out 62/64 with 55/62 exact and currency
62 current, and the new row is `0/64 not run`.

## The tests

`tests/test_sealed_set.py`, deliberately, in two places:

- **the registry-shape assertions** (`test_it_is_not_one_of_the_development_sets`
  and `test_it_has_its_own_case_root_key_and_loader`) now state the new shape:
  `RERUN_SETS` is `("wild-dev",)`, `BY_NAME` is exactly the registered sets, and
  `wild-dev` is in neither `DEVELOPMENT_SETS` nor `ALL_SETS` nor `SEALED_SETS`.
  The second of the two also records the one sharing that is deliberate —
  `wild-dev` shares the held-out set's key, case root and case list, and shares
  neither its runs subdirectory nor its run directory.
- **one new test**,
  `test_wild_dev_is_excluded_from_the_combined_figure_and_from_set_all`, which
  puts a case file in a scratch `runs/wild-dev/<model>/` and shows the set's own
  reading seeing it while `combined_figures` returns `(0, None)`; it then runs
  `--set all --cases 501` with `tribunal.llm.LLMClient` patched to raise, and
  shows no case ran and nothing was written under `runs/wild/`.

**Seen to fail first.** With `DEVELOPMENT_SETS` rebound in memory to include
`wild-dev`, the new test fails with
`AssertionError: --set all built a client, so it ran a case it must not` — the
selection reached case 501 through `--set all`, which is exactly what the test
exists to catch. `runs/wild-dev-a1-sabotage.log`, exit 1. Green on the
unpatched tree, exit 0.

No model is called by any test in the module, and the `LLMClient` patch is what
guarantees that the failing case fails here rather than making a paid call.
