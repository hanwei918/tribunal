# Stale cached results: the check that was missing, and what it found

Date: 2026-09-22. Commit: the one that adds this file.

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
212**. That is not what the cache holds. Measured:

```
deepseek-deepseek-flash   cached=29  current=8  stale=21  unknown=0
  current: 102, 103, 104, 110, 111, 113, 115, 213
  stale:   101, 105, 106, 107, 108, 109, 112, 114, 201, 202, 203, 204, 205, 206, 207,
           208, 209, 210, 211, 212, 214
hy4-preview               cached=1   current=0  stale=1   unknown=0
  stale:   109
```

Cases 201 through 212 are stale, as expected. Nine more are: eight route-deviation cases
and case 214.

### How that was established

The claim "this digest does not match the current code" is only useful if it can be traced
to a version. Three worktrees were checked out at the three commits that could have changed
the brief — `a11285b`, `95f0b74`, `d06d2ff` — and all 29 brief digests computed in each.
Only `95f0b74` and `d06d2ff` touch `tribunal/`; no commit in the window touches `data/` or
`policy/`. That gives exactly three possible briefs per case, and each cached digest was
matched against all three:

| cached digest matches | cases | count |
|---|---|---|
| all three commits (the brief never changed) | 102, 103, 104, 110, 111, 113, 115, 213 | 8 |
| `a11285b` only | 204, 211 | 2 |
| **no committed version at all** | 101, 105, 106, 107, 108, 109, 112, 114, 201, 202, 203, 205, 206, 207, 208, 209, 210, 212, 214 | 19 |

Two independent checks confirm the field means what it is taken to mean:

- **The transcript agrees.** For case 214 the transcript records `user_sha256` for both
  advocates as `fd64cd2b3920…`, identical to the cache entry's `brief_sha256`. The field is
  the digest of what was sent, not a second computation of it.
- **The brief is deterministic.** `brief.build_brief(214)` returns the same digest under 30
  different `PYTHONHASHSEED` values, and `brief.brief_digest` is byte-identical to the
  pipeline's own `money.dumps_canonical` + SHA-256. No set iteration or float round-trip is
  involved.

### What this means

**The cache is not a mix of two versions of the brief. It is a mix of at least four**, and
nineteen of its digests match no committed version of the code at all. The 29-case run began
at 15:48 Beijing and finished at 19:19; `95f0b74` was committed at 17:45 and `d06d2ff` at
18:57. The run therefore overlapped the development of the accumulated-dwell work, and the
results cached at different minutes came from different working-tree states. The run's own
`run.json` — which would have said the tree was dirty — was destroyed by the case-214 re-run,
so this can no longer be established directly. It can only be inferred from the digests,
which is exactly why per-case provenance is the second half of this change.

### What could not be explained

Case 214's re-run is the one case that does not fit. Its `run.json` records commit
`d06d2ff` and `working_tree_clean: true`; `tribunal/brief.py` has not been written since
18:56:05, a minute before that commit, and no tracked file under `tribunal/`, `data/`,
`policy/` or `prompts/` has a modification time inside the run window. A clean tree at
`d06d2ff` produces `e880457d6c52…` for case 214. The result that was cached, and that the
transcript confirms was sent, is `fd64cd2b3920…`.

Ruled out by measurement, not by argument:

- the runner's clean-tree pathspec works — `git status --porcelain -- . ':(exclude)runs'`
  reports a modified tracked file, tested directly;
- there are no `skip-worktree` or `assume-unchanged` index flags and no `.git/info/exclude`
  entries;
- `brief.build_brief` is deterministic across hash seeds, and its digest matches the
  pipeline's own computation exactly;
- the recorded digest is not a mid-edit variant of the `shortfall_basis` fix: dropping the
  field reproduces `95f0b74` exactly (`16c71a7d3a24…`), and the six other variants tried
  match nothing.

**This is recorded as unresolved rather than explained away.** It is also the strongest
argument for change 2: with the commit and prompts digest written into the case file itself,
this question would have been answerable from the artifact instead of from forensics on
mtime.

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

- 526 tests pass (24 new), no network.
- The new guard was mutated to make a changed brief read as current; 7 tests went RED. The
  file was restored and the suite re-run green.
- `--compare` over the real cache now names the stale case in each run directory instead of
  printing a bare accuracy.
