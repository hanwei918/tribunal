# Stale cached results: the check that was missing, and what it found

Date: 2026-09-22. Commit: the one that adds this file.

The counts in "What the check found" were corrected on the same day, after the first version of
this note was found to state a figure measured under the wrong interpreter. What was wrong, and
why, is recorded below under "Why the earlier version of this note was wrong", together with the
defect in the brief that the wrong count uncovered — a defect that has since been fixed, the fix
being recorded under "The brief is not stable across Python versions". The defect this note is
about, the three causes and the change are unaffected.

**The block was corrected a second time, later the same day, when the check gained a second
channel.** It now compares the recorded *prompts* digest as well as the recorded brief digest, and
it names which of the two moved, because "the facts changed" and "the instructions changed" are
different findings that call for different responses. The entries written before the field existed
record no prompts digest, so the prompt half of the check cannot be made for them: those results are
reported `unknown`, not `current`. **That is the new channel working, and it is the reason the block
stopped reading `current=17`.** What the brief channel found is unchanged, and the three causes, the
changes and the defect this note is about are unaffected.

**The block was corrected a third time when the judge prompt was amended**, which moved the prompt
directory's digest from `457c896b07b3da23…` to `b131e63f046aecc6…`. That turned the three results
which had recorded the older one — the only three whose prompt channel can be answered at all —
from `current` into `**STALE (prompt)**`, so the block now reads `current=0 stale=15 unknown=14`.
Nothing in the cache moved and nothing about the brief channel changed: editing a prompt is supposed
to do this, and the channel reported it.

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

The check reads **two** recorded digests, and the block below is its own output. What each channel
answers has to be said first, because the two are not the same finding and the block no longer lets
them be read as one.

- **The brief channel** — the digest of the exact bytes the agents were handed. This is the channel
  this note is about, and its answer is unchanged: **twelve results were produced by a brief this
  code no longer builds, and they are 201 through 212.**
- **The prompt channel** — the digest of the prompt directory. This channel is new, so the entries
  that predate it record nothing: **fourteen of the twenty-nine cannot have the prompt half of the
  check made at all.** The other three were rewritten after the field existed and can, and all three
  now read `**STALE (prompt)**`: they recorded a digest of the prompt directory as it stood then,
  and the judge prompt has been amended since.

A result whose prompt half cannot be checked is not stale for it — nothing moved — and it is not
current either. It is **unknown**, the third answer, deliberately not a synonym for the first. That
is why the block reads `current=0` where the brief channel alone would say seventeen: those
seventeen have a brief this code still builds, and fourteen of them cannot say which prompts
produced them. Seventeen is still the brief channel's answer, and it is stated above in those terms
rather than as a verdict.

The block, measured under Python 3.9.6 — the interpreter that produced this cache:

```
deepseek-deepseek-flash   cached=29  current=0   stale=15  unknown=14
  stale:   101, 102, 103, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212
  unknown: 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 213, 214
hy4-preview               cached=1   current=0   stale=0   unknown=1
  unknown: 109
```

**Nothing is current any more, and the last three moved for a different reason.** Cases 101, 102 and
103 were the only results whose prompt channel could be answered: they were rewritten by the
29-case re-run of 2026-09-22, twenty-one minutes after this block was first written, and that run's
code recorded a prompts digest. It recorded `457c896b07b3da23…`, which is what the prompt directory
hashed to then and not what it hashes to now, so those three read `**STALE (prompt)**`. Nothing
about them changed in the cache; the judge prompt did. The block above is re-derived from the cache
rather than edited by hand.

Fifteen of twenty-nine results are stale, and they are stale for two different reasons that the
report keeps apart. **Twelve are stale on the brief channel** — cases 201 through 212, every one of
them a NO_SHOW_CHARGE case carrying a GPS trace. **Three are stale on the prompt channel** — cases
101, 102 and 103, whose briefs this code still builds. The remaining fourteen are `unknown`, which
is not `current`.

The brief channel is what the reasoning predicts, and the reasoning is worth stating because it is
what makes the count checkable rather than merely observed. `accumulated_dwell` is published
only on NO_SHOW traces, so the accumulated-dwell change can move the brief of a NO_SHOW case
and nothing else: cases 101 through 115 are ROUTE_DEVIATION and cannot be touched by it. Case
213 is NO_SHOW but its GPS artifact is `MISSING`, so no derived block exists and its brief is
unchanged. Case 214 was re-run after the shortfall-basis change, so its brief is current — and its
result still reads `unknown`, because the brief channel agreeing says nothing about which prompts
produced it. Twelve cases could move, and twelve are stale.

The prompt channel is not predicted by that reasoning and should not be. The digest is taken over
the whole directory, so editing any prompt moves every result that recorded one — including results
whose brief is untouched, which is exactly what happened to 101, 102 and 103. That is the channel
working, not a finding about those cases.

### How that was established

The claim "this digest does not match the current code" is only useful if it can be traced
to a version. Every commit from `774fc82` — the one that added the runner — through `d06d2ff`
was checked out with `git worktree add --detach`, and all 29 brief digests computed in each,
every one of them under Python 3.9.6. Only `95f0b74` and `d06d2ff` touch `tribunal/`; no commit
in the window touches `data/` or `policy/`.

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
- **The brief is deterministic within one interpreter.** `brief.build_brief` returns the same
  digest under 30 different `PYTHONHASHSEED` values, and `brief.brief_digest` is byte-identical
  to the pipeline's own `money.dumps_canonical` + SHA-256. No set iteration is involved. A
  float was: the mean distance to the pickup point travels unrounded, and `sum()`'s float
  semantics changed in Python 3.12, so the digest was a function of the interpreter as well as
  of the repository. That was the whole of the discrepancy recorded below, and it is why the
  accumulation is now pinned.

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
builds for it under 3.9.6 — and, checked out at that revision, `e880457d6c52…` under 3.13.12,
which is the second of the two values this note's first version could not place. That divergence
was a property of the revision rather than of the case: the accumulation is pinned now, so at the
current commit both interpreters build `fd64cd2b3920…` for it. Its `run.json` records
`git_commit: d06d2ff…`, `working_tree_clean: true`, `requested: [214]`, started 19:20:05 and
ended 19:23:53. It is a single-case re-run made after the shortfall-basis change landed, and it
is current. It is the only result in the cache that the current brief produced.

### Why the earlier version of this note was wrong

The first version of this note recorded `cached=29 current=8 stale=21`, with nineteen digests
said to match no committed version of the brief and case 214 recorded as inexplicable. All
three statements are false, and how they were produced is worth recording, because the note
was believed.

**Twenty-one is reachable, and it is what this same check reports under a different
interpreter.** Under the cache's own Python 3.9.6 the count is twelve. Under the Python 3.13.12
that `python3` resolves to on this machine it is twenty-one:

```
python3           3.13.12  ->  cached=29  current=8   stale=21
/usr/bin/python3  3.9.6    ->  cached=29  current=17  stale=12
```

So the twenty-one was not a broken worktree method and not a figure typed in by hand: it was
this check, run correctly, against a brief whose bytes depended on the interpreter. That the
cache was produced under 3.9.6 is settled by its own digests, since the entries recorded for
101, 213 and 214 are exactly what 3.9.6 builds and not what 3.13.12 builds. **Twelve is the
answer for this cache** — and since the accumulation was pinned it is the answer under either
interpreter, which is the property that was missing when this section was first written.

Under every committed revision from `774fc82` to `d06d2ff`, computed under 3.9.6, this cache
yields 1, 12 or 13 stale results:

```
774fc82  stale=1   [214]
bf1c8dd  stale=1   [214]
3931406  stale=1   [214]
a11285b  stale=1   [214]
95f0b74  stale=13  [201..212, 214]
d06d2ff  stale=12  [201..212]
```

And the earlier note's own table comes back exactly by running that same comparison under
3.13.12 instead of 3.9.6. Its three buckets are the three buckets 3.13 produces, to the case
number:

| cached digest matches | cases | count |
|---|---|---|
| every revision tested | 102, 103, 104, 110, 111, 113, 115, 213 | 8 |
| `a11285b` only | 204, 211 | 2 |
| **no committed revision** | 101, 105, 106, 107, 108, 109, 112, 114, 201, 202, 203, 205, 206, 207, 208, 209, 210, 212, 214 | 19 |

That is the first version of this note's table exactly, including the nineteen it could not
account for and the eight it took for unchanged. Every figure in that version follows from the
interpreter and from nothing else, which is why the candidates below are not merely unproven —
they are not needed.

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

What survives from the earlier note is the shape of its method — a worktree per commit — which,
run with the module path asserted and under the cache's own interpreter, reproduces the figures
above. Its lesson survives too, and this correction sharpens rather than weakens it: **a number
written in a note is a claim like any other, and nothing here was comparing it to the code.**
Two figures in the earlier version were wrong, one of them because the note never said which
interpreter had produced it. So the note says now, and the numbers are held against the code by
`NoteCouplingTests` in `tests/test_run_benchmark.py`: that test reads the block and compares it
with `grade_run` over the same directories, and separately runs the command the note quotes and
compares its output with the block. The cache under `runs/` is untracked, so where a run directory
is absent the comparison is skipped and the skip says so. The count itself is no longer
interpreter-sensitive: that was the defect below, and it is fixed.

### The brief is not stable across Python versions

This is the defect the wrong count uncovered, and it was the more serious of the two findings. It
is now fixed. What follows is the measurement that found it and the repair.

`facts.track_summary` computed the mean distance from a trace to the pickup point as
`sum(distances) / len(distances)`. **Python 3.12 changed `sum()` for floats to use Neumaier
compensated summation**, so the same distances averaged to a different last bit under 3.9 and
under 3.13. Case 101, whose trace carries 229 fixes:

```
                       sum()                  mean
3.9.6    1945172.0261218469     8494.200987431646
3.13.12  1945172.0261218462     8494.200987431643
```

A left-to-right accumulation returns `1945172.0261218469` under both interpreters, and all 229
individual distances are bit-identical under both — so the difference is `sum()`'s, not the
data's.

Comparing the canonical brief of all 29 cases across the two interpreters: **19 of the 29
differed**, the only field that ever differed was a `mean_distance_m` — specifically
`derived.driver_track.mean_distance_m.value` in 17 cases and
`derived.rider_presence.mean_distance_m.value` in 5 — and in 9 of those 19 it flipped the
staleness verdict. Nine is exactly the excess of twenty-one over twelve.

The consequence was general, and it was not confined to this cache. **`brief_sha256` is meant to
be the digest of the bytes the agents were handed, and those bytes were not determined by the
repository alone.**

**The repair is one function.** `facts._sum_in_order` accumulates left to right with no
compensation — the accumulation CPython performed before 3.12 — and both float `sum()` calls in
the module now go through it. `math.fsum` was considered and rejected: it is correctly rounded, so
it would produce a *third* value and invalidate all 29 cached results. The naive loop is right
precisely because it reproduces what 3.9's `sum()` already did.

**The repair was measured before it was made.** Shadowing the module-global `sum` with a plain
loop, without editing anything:

```
interpreter                        3.9.6        3.13.12
the builtin, as it was            17 current     8 current
a left-to-right loop              17 current    17 current
canonical briefs the loop changes        0 of 29   (under 3.9.6)
```

Under 3.9.6 the loop changes **no** brief, so no cached result changes meaning and the cache stays
byte-for-byte valid. Under 3.13.12 it turns nine from stale to current — 101, 105, 106, 107, 108,
109, 112, 114, 214 — loses none, and converges the check onto the cache's own answer. The twelve
that remain are genuine code drift. `accumulated_sec` was checked too: it is the other float
`sum()` in the module, it never differed across the corpus, and it was changed anyway so that the
class is closed rather than the instance. The integer sums in `transcript.py` are exact under
either rule and were left alone. `mean_latency_seconds` in the comparison table is also a float
`sum()`, but it is a rendered latency formatted to one decimal and reaches no digest, so it is
left as it is and recorded here rather than silently changed.

**The interpreter is now recorded as provenance**, beside `git_commit` and `prompts_sha256`, in
every cache entry and in the run's own `run.json`. It is provenance and not a gate: the brief no
longer varies with the interpreter, so a mismatch does not make two digests incomparable — it says
which of them came from where. The comparison table names both interpreters when they differ, so a
digest that disagrees can be read against the interpreter that produced it instead of being called
code drift by default. A cache that predates the field reports nothing rather than guessing.

### Re-deriving these numbers

The block under "What the check found" is not written by hand: it is the output of this command,
run from the project root. No network, no model call. It reads every directory the block names,
and because the accumulation is pinned it reproduces the block under any interpreter.

```
python3 - <<'PY'
import sys, glob, os
sys.path[:0] = ["."]
from eval import run_benchmark as runner
for name in ("deepseek-deepseek-flash", "hy4-preview"):
    run_dir = os.path.join("runs", name)
    cases = sorted(int(os.path.basename(p).split("-")[1].split(".")[0])
                   for p in glob.glob(run_dir + "/case-*.json")
                   if not p.endswith(".transcript.json"))
    staleness = runner.brief_staleness(run_dir, cases)
    stale, unknown = set(staleness.stale), set(staleness.unknown)
    current = [case for case in cases if case not in stale and case not in unknown]
    print(("%-25s cached=%-2d  current=%-2d  stale=%-2d  unknown=%-2d"
           % (name, len(cases), len(current), len(staleness.stale),
              len(staleness.unknown))).rstrip())
    for label, group in (("current", current), ("stale", list(staleness.stale)),
                         ("unknown", list(staleness.unknown))):
        if group:
            print("  %-8s %s" % (label + ":", ", ".join(str(case) for case in group)))
PY
```

Before the accumulation was pinned this command carried a version guard that stopped it under any
interpreter but 3.9.6, because under the `python3` on this machine's `PATH` it printed
twenty-one. The guard is gone because the reason for it is gone. `python3 -m unittest
tests.test_run_benchmark.NoteCouplingTests -v` re-derives the same numbers and checks the note
against them in one step.

## What was changed

1. **Staleness is checked whenever a cached result is read, on two channels.** `grade_run` — and
   therefore `--compare`, which reads through it — rebuilds each cached case's brief with
   `brief.brief_digest` and the prompt directory with `hash_directory`, compares both with what
   the entry recorded, and names which of the two moved. A stale case is named and counted in the
   report, carries a `cached` column in the per-case table reading `**STALE (brief)**` or
   `**STALE (prompt)**`, appears in the comparison table's `cached` column, and is announced on
   its own progress line when the result is reused — where the line says *which* digest moved, so
   the reader is sent to the brief or to the prompts rather than to whichever one the code
   happened to check first. A mixed set says on its face that its exact-match figure is not a
   single measurement.

   The two are never merged into one word, because they are not interchangeable: a moved brief is
   answered by re-reading the case, a moved prompt by re-reading what the agents were told to do
   with it.

   Three states, and the third is not the first. A brief that cannot be rebuilt is `unknown`, not
   current, for the same reason an unreadable working tree is not clean — and so is an entry that
   records no prompts digest, since a result whose instructions cannot be established is not a
   result this code can call current. A report that checked nothing prints nothing — silence
   rather than a reassuring zero.

2. **Per-case provenance.** Every cache entry now records `git_commit`, `prompts_sha256` and
   `python_version` beside the `brief_sha256` it already kept. The run's own `run.json` carries
   the interpreter too, so a run whose per-case entries have been lost still says what built
   its briefs. **The entries already under `runs/` predate the field**, which is why the prompt
   channel reports fourteen of them `unknown` rather than a regression. The three that do not are
   the three the 2026-09-22 re-run rewrote after the field existed, and they are the only ones the
   prompt channel can answer at all — and all three read `**STALE (prompt)**`, because the judge
   prompt has been amended since they were written.

3. **The run record is no longer destroyed.** `run.json` still describes the invocation that
   wrote it — it is rewritten after every case, which is what keeps an interrupted run's
   totals correct — and it now carries a `directory` block saying what the directory actually
   holds. Every invocation's own record is appended to `invocations.json`, keyed by its start
   time and replaced in place, so an earlier invocation stays reconstructable after its
   `run.json` is gone.

4. **The accumulation behind the brief is pinned.** `facts._sum_in_order` sums left to right
   with no compensation, and both float `sum()` calls in `facts.py` go through it. A brief is
   now a function of the repository alone, so this class of false staleness cannot arise. The
   repair was measured first: it changes no byte of the existing cache under 3.9.6, so no
   cached result changes meaning.

5. **The prompt digest is compared too, and the two findings are kept apart.** The prompts digest
   is taken over the whole directory — `prompts/v1/` — because what an agent was given is the
   prompt set: the advocate template, both stances and the judge prompt. Editing any of them
   changes what an agent was told to do, so every cached result reports stale on the prompt
   channel. `Staleness` carries `stale_brief`, `stale_prompts` and `unchecked_prompts` beside the
   `stale` union, and every surface that reports staleness — the report, the per-case table, the
   comparison table and the progress line — reports the channel rather than the union. An entry
   that records no prompts digest is `unknown` for that channel, and `unknown` is not `current`.

## What was not done

Nothing was re-run and no model call was made. No stale result was deleted, moved or
rewritten: they are real measurements and they are the evidence for this finding, and the
twelve stay stale because the code they measured really has moved. The `report.md` files under
`runs/` were not regenerated — they are the record of what the earlier code printed, and
rewriting them would destroy the comparison.

Two things were deliberately left alone, each recorded above with its reason: `math.fsum` was
not used, because it would invalidate all 29 cached results rather than reproduce them; and
`mean_latency_seconds` in the comparison table was not changed, because it reaches no digest.

## Verification

- The full suite passes under both interpreters, no network.
- The new guard was mutated to make a changed brief read as current; 7 tests went RED. The
  file was restored and the suite re-run green.
- `--compare` over the real cache now names the stale case in each run directory instead of
  printing a bare accuracy.
- The figures in "What the check found" were re-derived four ways: through `grade_run`, through
  an independent `money.dumps_canonical` sweep, through the six worktrees, and by running the
  command this note quotes and diffing its output against the block. All four agree on the brief
  channel: 17 results whose brief this code still builds, 12 of them stale.
- `NoteCouplingTests` was mutated twice to prove it bites. Restoring the old `8/21` block turns
  the cache comparison RED, and dropping one directory from the quoted command turns the
  command comparison RED. Both files were restored from copies and the suite re-run green.
- The interpreter dependence was measured rather than inferred: 19 of the 29 canonical briefs
  differ between 3.9.6 and 3.13.12; the only field that ever differs is a `mean_distance_m`; all
  229 individual distances for case 101 are bit-identical under both interpreters; and a
  left-to-right accumulation reproduces the 3.9 value under both, which places the change in
  `sum()` rather than in the data.
- **The repair was measured before it was made**, by shadowing the module-global `sum` with a
  plain loop rather than editing the file: under 3.9.6 it changes 0 of 29 canonical briefs, and
  under 3.13.12 it turns nine from stale to current and loses none. The check was then run for
  real under both interpreters and gives the same brief-channel answer under each — 17 with a brief
  this code still builds, 12 stale — where before it reported 12 under one and 21 under the other.
- **The accumulation guard was mutated to prove it bites.** Pointing `_sum_in_order` at the
  builtin turns five tests RED under 3.13.12 — and one under 3.9.6, the source-level test, which
  is the guard that does not depend on which interpreter runs the suite. The file was restored
  from a copy, confirmed byte-identical, and the suite re-run green.
- **The comparison-table surface was mutated too.** Making the interpreter note unreachable
  turns `test_the_comparison_table_names_the_interpreter_when_it_differs` RED. Restored and
  re-run green.
- `NoteCouplingTests` no longer skips: all seven run under 3.9.6 and under 3.13.12. The two
  comparisons used to be skipped under any interpreter but the cache's own, which is what the
  repair removed.
- **Both new guards were mutated to prove they bite.** Five mutations were made one at a time, each
  restored from a copy and confirmed byte-identical afterwards.

  | mutation | what went RED |
  |---|---|
  | `prompts_moved` answers "nothing moved" | `test_a_prompt_that_moved_reports_stale_and_names_the_prompt`, `test_a_run_where_both_digests_moved_reports_both` |
  | `status_of` drops the uncheckable-prompt clause | `test_an_entry_with_no_prompts_digest_reports_unknown_not_current`, `test_a_prompts_digest_that_cannot_be_taken_is_unknown_not_current` |
  | the per-case cell prints a bare `**STALE**` | all three channel-naming tests |
  | the removal-test sentence is deleted from the judge prompt | `test_the_removal_test_bounds_the_principle` |
  | the judge prompt is turned into a list naming case 211 | `test_the_prompt_does_not_name_the_two_cases_it_was_written_for` |

  No mutation turned anything else red, and no file was left changed.
