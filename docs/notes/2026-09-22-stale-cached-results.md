# Stale cached results: the check that was missing, and what it found

Date: 2026-09-22. Commit: the one that adds this file.

The counts in "What the check found" were corrected on the same day, after the first version of
this note was found to state a figure the implementation cannot produce. What was wrong, and
why, is recorded below under "Why the earlier version of this note was wrong". The defect, the
three causes and the change are unaffected.

## The defect

Three things were wrong with how a cached benchmark result was read, and only the third
was known before this work started.

1. **Nothing checked whether a cached result still corresponded to the code.** `facts.py`
   gained the POL-NS-06(i) accumulated-dwell fact and `brief.py` then gained
   `shortfall_basis`; both change the brief for every NO_SHOW case carrying a GPS trace.
   Case 214 was re-run after the second change. The other results in the cache were not.
   Nothing recorded this and nothing detected it, so `--compare` would tabulate every
   result in the directory as one run.

2. **Provenance lived only in a file the next invocation overwrites.** A cache entry
   recorded the digest of the brief its agents were handed, and nothing else about what
   produced it. The commit and the prompts digest existed only in `run.json`.

3. **`run.json` was overwritten by every invocation, and then misread.** The single-case
   re-run of case 214 replaced the 29-case run's own record — its commit, its token total,
   its case list. What survived said `requested [214]` while sitting in a directory of
   twenty-nine results: true of the invocation, misleading about the directory, and the
   only record left.

The detection was already in the data. `brief_sha256` is the SHA-256 of the exact bytes the
agents received, so rebuilding that case's brief and comparing the two digests settles
whether the result still belongs to the current code. What was missing was not information.
It was the act of checking.

## What the check found

The expectation going in was **17 current and 12 stale, the stale ones being 201 through
212**. That is what the cache holds. Measured:

```
deepseek-deepseek-flash   cached=29  current=17  stale=12  unknown=0
  current: 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 213, 214
  stale:   201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212
hy4-preview               cached=1   current=1   stale=0   unknown=0
  current: 109
```

Twelve of twenty-nine results are stale, and every one of them is a NO_SHOW_CHARGE case
carrying a GPS trace. Cases 201 through 212 are stale, exactly as expected; nothing else is.

That is also what the reasoning predicts, and the reasoning is worth stating because it is
what makes the count checkable rather than merely observed. `accumulated_dwell` is published
only on NO_SHOW traces, so the accumulated-dwell change can move the brief of a NO_SHOW case
and nothing else: cases 101 through 115 are ROUTE_DEVIATION and cannot be touched by it. Case
213 is NO_SHOW but its GPS artifact is `MISSING`, so no derived block exists and its brief is
unchanged. Case 214 was re-run after the shortfall-basis change, so its result is current.
Twelve cases could move, and twelve are stale.

### How that was established

The claim "this digest does not match the current code" is only useful if it can be traced
to a version. Every commit from `774fc82` — the one that added the runner — through `d06d2ff`
was checked out with `git worktree add --detach`, and all 29 brief digests computed in each.
Only `95f0b74` and `d06d2ff` touch `tribunal/`; no commit in the window touches `data/` or
`policy/`.

**The method is only sound if the `tribunal` package imported in each worktree is that
worktree's own.** `loader.PROJECT_ROOT` is `Path(__file__).resolve().parents[1]`, so `data/`,
`policy/` and `tribunal/` are resolved from the location of the module actually imported and
always come from the same checkout — they cannot be split. The script therefore prints
`brief.__file__` and `loader.PROJECT_ROOT` and they must point inside the worktree; nothing is
assumed about which one `sys.path` chose. Each cached digest was then matched against all six
revisions:

| cached digest matches | cases | count |
|---|---|---|
| every revision tested — the brief never changed for these | 101–115, 213 | 16 |
| the four revisions before `95f0b74` | 201–212 | 12 |
| `d06d2ff` only | 214 | 1 |
| **no committed revision** | — | 0 |

Two independent checks confirm the field means what it is taken to mean:

- **The transcript agrees.** For case 214 the transcript records `user_sha256` for both
  advocates as `fd64cd2b3920…`, identical to the cache entry's `brief_sha256`. The field is
  the digest of what was sent, not a second computation of it.
- **The brief is deterministic.** `brief.build_brief` returns the same digest under 30
  different `PYTHONHASHSEED` values, and `brief.brief_digest` is byte-identical to the
  pipeline's own `money.dumps_canonical` + SHA-256. No set iteration or float round-trip is
  involved.

### What this means

**The cache holds two versions of the brief, not four.** Twenty-eight of the twenty-nine
results were produced by the brief as it stood at `a11285b`; the twenty-ninth, case 214, by
the brief as it stands now.

The 29-case run began at 15:48 and wrote its last case at 17:19:49. `95f0b74` was committed at
17:45:41 — after the run had already passed every NO_SHOW case — and `d06d2ff` at 18:57:59.
So the whole 29-case set predates both changes, and the only stale results are the NO_SHOW
cases whose brief those changes moved. Case 214 was then re-run on its own at 19:23:53, after
`d06d2ff`, and is current.

Nothing here required the tree to be dirty. The run was made at `a11285b` and the code moved
on underneath it afterwards, which is the ordinary way a cache goes stale and precisely why
the check belongs in the code rather than in a note.

### Case 214

Case 214 is not an anomaly. Its cache entry records `fd64cd2b3920…`, which is what `d06d2ff`
builds for it; its `run.json` records `git_commit: d06d2ff…`, `working_tree_clean: true`,
`requested: [214]`, started 19:20:05 and ended 19:23:53. It is a single-case re-run made after
the shortfall-basis change landed, and it is current. It is the only result in the cache that
the current brief produced.

### Why the earlier version of this note was wrong

The first version of this note recorded `cached=29 current=8 stale=21`, with nineteen digests
said to match no committed version of the brief and case 214 recorded as inexplicable. All
three statements are false, and how they were produced is worth recording, because the note
was believed.

**Twenty-one is not reachable.** Under every committed revision from `774fc82` to `d06d2ff`,
this cache yields 1, 12 or 13 stale results — never 21, and never with case 101 among them:

```
774fc82  stale=1   [214]
bf1c8dd  stale=1   [214]
3931406  stale=1   [214]
a11285b  stale=1   [214]
95f0b74  stale=13  [201..212, 214]
d06d2ff  stale=12  [201..212]
```

To reach twenty-one, nine cases that are in fact unchanged — 101, 105, 106, 107, 108, 109,
112, 114 and 214 — would each have to have been built from something that is not any committed
brief. No commit produces that. So the twenty-one was not this check's output, and the
computation that produced it could not be reproduced from anything in the repository. It is
recorded as unreproducible rather than explained, which is the only honest thing to do with a
number that cannot be shown.

The mechanism suspected at the time was that the worktree digests had been computed with the
checked-out worktree's `data/` while the main tree's `tribunal/` was still on `sys.path`.
**That cannot happen**, for the reason given above: `PROJECT_ROOT` is derived from the imported
module, so the two cannot be split by `sys.path` at all. The 3×3 matrix of `tribunal/`
revision against `data/` and `policy/` revision confirms it — the data revision changes
nothing, and no cell reaches thirteen:

```
brief=a11285b  data=a11285b  stale=1   [214]
brief=a11285b  data=95f0b74  stale=1   [214]
brief=a11285b  data=d06d2ff  stale=1   [214]
brief=95f0b74  data=a11285b  stale=13  [201..212, 214]
brief=95f0b74  data=95f0b74  stale=13  [201..212, 214]
brief=95f0b74  data=d06d2ff  stale=13  [201..212, 214]
brief=d06d2ff  data=a11285b  stale=12  [201..212]
brief=d06d2ff  data=95f0b74  stale=12  [201..212]
brief=d06d2ff  data=d06d2ff  stale=12  [201..212]
```

The other candidate was a serializer mismatch — digests taken from `json.dumps` rather than
`money.dumps_canonical`. That is refuted too: it would report **all seventeen** current cases
as stale, not nine, because every brief in this corpus carries a decimal literal the two
serialisers render differently.

What survives from the earlier note is its method, which reproduces the figures above, and its
lesson, which the miscount sharpens rather than weakens: **a number written in a note is a
claim like any other, and nothing here was comparing it to the code.** The count in "What the
check found" is now checked against `grade_run` by `NoteCouplingTests` in
`tests/test_run_benchmark.py`, which reads that block and holds it against the same
directories. The cache under `runs/` is untracked, so where it is absent the comparison is
skipped and stated, and only the note's internal consistency is asserted.

### Re-deriving these numbers

One command, from the project root, no network, no model call:

```
python3 - <<'PY'
import sys, glob, os
sys.path[:0] = ["."]
from eval import run_benchmark as runner
d = "runs/deepseek-deepseek-flash"
cases = sorted(int(os.path.basename(p).split("-")[1].split(".")[0])
               for p in glob.glob(d + "/case-*.json") if not p.endswith(".transcript.json"))
s = runner.brief_staleness(d, cases)
print("cached=%d current=%d stale=%d unknown=%d" % (
    len(cases), len(cases) - len(s.stale) - len(s.unknown), len(s.stale), len(s.unknown)))
print("stale:", ", ".join(str(c) for c in s.stale))
PY
```

`python3 -m unittest tests.test_run_benchmark.NoteCouplingTests -v` re-derives the same numbers
and checks the note against them in one step.

## What was changed

1. **Staleness is checked whenever a cached result is read.** `grade_run` — and therefore
   `--compare`, which reads through it — rebuilds each cached case's brief with
   `brief.brief_digest`, compares the digest with the one the entry recorded, and marks any
   case whose brief has changed. A stale case is named and counted in the report, carries a
   `brief` column in the per-case table, appears in the comparison table's `stale` column,
   and is announced on its own progress line when the result is reused. A mixed set says on
   its face that its exact-match figure is not a single measurement.

   Three states, and the third is not the first: a brief that cannot be rebuilt is `unknown`,
   not current, for the same reason an unreadable working tree is not clean. A report that
   checked nothing prints nothing — silence rather than a reassuring zero.

2. **Per-case provenance.** Every cache entry now records `git_commit` and
   `prompts_sha256` beside the `brief_sha256` it already kept.

3. **The run record is no longer destroyed.** `run.json` still describes the invocation that
   wrote it — it is rewritten after every case, which is what keeps an interrupted run's
   totals correct — and it now carries a `directory` block saying what the directory actually
   holds. Every invocation's own record is appended to `invocations.json`, keyed by its start
   time and replaced in place, so an earlier invocation stays reconstructable after its
   `run.json` is gone.

## What was not done

Nothing was re-run and no model call was made. No stale result was deleted, moved or
rewritten: they are real measurements and they are the evidence for this finding. The
`report.md` files under `runs/` were not regenerated — they are the record of what the
earlier code printed, and rewriting them would destroy the comparison.

## Verification

- The full suite passes, no network.
- The new guard was mutated to make a changed brief read as current; 7 tests went RED. The
  file was restored and the suite re-run green.
- `--compare` over the real cache now names the stale case in each run directory instead of
  printing a bare accuracy.
- The figures in "What the check found" were re-derived in the three ways this note describes:
  through `grade_run`, through an independent `money.dumps_canonical` sweep, and through the
  six worktrees. All three agree on 17 current and 12 stale.
