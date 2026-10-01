# A run under `runs/wild/` is the held-out set, and a run that analysed nothing says so

**2026-10-01, part A2 of the "use wild-v1 as a development set" task. No model
call was made.**

Two defects, one cause and one symptom, both exposed the moment `wild-v1` became
development data.

## The cause: the set was derived from the path, and only `codex` was named

`tribunal/precedents.py` derives a run's set from the run directory's own path,
because a schema-1 case file carries no `development_set` field and a closure
must still be able to say which set it came from. The rule named exactly one
directory:

```python
if following < len(parts) and parts[following] == SET_CODEX:
    return SET_CODEX
return SET_CORPUS
```

Everything that was not `codex` was the corpus — including `runs/wild/<model>/`.
Two things read that answer and both were wrong for a wild run:

| reader | what it did with a wild run |
|---|---|
| `eval/policy_gaps.py` `read_run` | loaded every case through `development_set.load_case`, i.e. the **corpus manifest**, which does not list cases 501–533 and 9111–9114 |
| `tribunal/precedents.py` `close` | same loader, so every closure of a wild run failed with `case 501 is not listed in data/index.json` |

## The fix

One table replaces the one-name rule:

```python
SET_CORPUS = "corpus"
SET_CODEX = "codex"
SET_WILD = "wild"
SET_WILD_DEV = "wild-dev"

EXTERNAL_SET_DIRS: Dict[str, str] = {
    SET_CODEX: SET_CODEX,
    SET_WILD: SET_WILD,
    SET_WILD_DEV: SET_WILD,
}
```

The **set name** and the **directory the cases are loaded from** are now two
things, because `wild-dev` and `wild` are two sets over one directory of cases:
`wild-dev` is filed under `wild`, so it records `wild-dev` as the set a closure
came from while loading the held-out set's own case files. That is the whole of
what "both map to `data/external/wild`" means in code.

`set_from_run_directory` returns the component itself when the component names a
set in that table and `corpus` otherwise — the corpus is the fallback rather than
a name looked up, because `runs/<model-slug>/` carries no component of its own.
`load_case_for_run` looks the set up in the same table and loads from the
manifest only when it finds nothing. Every other layout still reads as the
corpus: `runs/precedents/<model>/`, `runs/ablation/<name>/<model>/`,
`runs/policy-v2/<model>/`, `runs/amount-rule/<rule>/<model>/`.

`eval/policy_gaps.py` is **not** changed here beyond the wording below. It keeps
calling `precedents.set_from_run_directory` — one function, one rule, one place a
layout is stated in this package.

**Nothing from `eval/` is imported into `tribunal/`.** That leaves the table in
`tribunal/precedents.py` and the registry in `eval/development_sets.py` as two
statements of one layout, which is a drift risk rather than a design. A test
closes it: `SetFromRunDirectoryTests` derives every registered set from its own
`runs_subdir` and checks every set's `case_root` against the directory this table
files it under.

## The symptom: "no case was left undecided" when nothing had been read

With the cause in place, `policy_gaps report` over `runs/wild/...` failed to
rebuild all 62 cases' briefs and then printed:

```
**No case in the given runs was left undecided, so there is no cluster to report.**
```

That sentence is false in the way that matters. It says the policy decided
everything it was asked; the truth was that the report had no reading of the run
at all. The two are different findings and a reader must not be able to take one
for the other, so they are now different sentences:

| | said when |
|---|---|
| `nothing could be analysed` | the run analysed **zero** cases, for any reason — a brief that will not rebuild, a recorded digest that moved, a cache with no case file in it |
| `no case in the given runs was left undecided` | cases **were** analysed and none of them is a gap |

`analysed_cases(run)` is `len(run.cached_cases) - len(run.not_analysed)`: a case
is analysed when its brief rebuilds and its recorded digests have not moved, and
every other case is in `not_analysed` with its reason, so the two counts
partition the cache. The change reaches three places, and the per-run line, the
cluster line and stdout all use it:

```
- `runs/wild/deepseek-deepseek-flash` (wild) — 62 case(s) cached, and nothing could be analysed
```

## The tests

Three new tests, and each was **seen to fail first** on the unfixed tree,
`runs/wild-dev-a2-tests-fail-first.log`, exit 1, three failures:

| test | what it said before the fix |
|---|---|
| `test_policy_gaps.ReportTests.test_a_wild_shaped_run_is_read_as_the_held_out_set` | `AssertionError: 'wild' != 'corpus'` |
| `test_policy_gaps.ReportTests.test_a_run_that_analysed_nothing_says_so` | `AssertionError: 'nothing could be analysed' not found in ...` (the rendered report carried `No case in the given runs was left undecided`) |
| `test_precedents.CliCloseTests.test_a_wild_shaped_run_closes_against_the_held_out_sets_loader` | `AssertionError: 0 != 1 : FATAL: case 501 is not listed in data/index.json` |

The fixture is a run built by the rig under `runs/wild/<model-slug>/`, over two
of the held-out set's own cases and the held-out set's own key, drafted through
the scripted transport. It is a **temporary** run: nothing here reads, writes or
depends on the committed held-out run under `runs/wild/deepseek-deepseek-flash/`,
which stays the record of a single run. The second test's fixture is a run
directory holding one case file whose brief digest cannot be checked, so it
analyses nothing whatever the path says — which is what makes it a test of the
wording and not of the loader.

`SetFromRunDirectoryTests` adds five tests over the derivation itself: every
registered set derived from its own component; every set's `case_root` equal to
the directory this table files it under; five switched-run layouts reading as the
corpus; the two wild sets told apart while sharing one case directory; and a
wild-shaped run loading the held-out set's own case while a corpus-shaped run
loads the manifest.

**Seen to fail first**, in the same log, for the three behavioural tests. The
`SetFromRunDirectoryTests` assertions are new statements of a layout that did not
exist before, so they could not have passed.

## What this does not do

- It does not open `runs/wild/` for writing. `precedents close` now reads a wild
  run correctly, and the store it writes to is the precedent library, not the run
  directory. Part A3 is what closes every path *into* `runs/wild/`.
- It does not change `--report`, the grader, any recorded result or any
  committed figure. `policy_gaps` reads a run's cache; nothing in this part
  writes one.
