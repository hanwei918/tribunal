# The policy-gap loop is ready for the owner, and nothing was run

2026-10-01, part D of *Use wild-v1 as a development set and fix what it exposed*.

`wild-v1` was run once, from `freeze-2026-09-30`, and that run in `runs/wild/` is
the held-out record. From 2026-10-01 its 64 cases are development data: its
answers may be read, and the system may be changed to fix what it exposed. Part
D makes the policy-gap loop able to work over those cases **without writing a
byte under `runs/wild/`**, and then stops.

Nothing in part D was executed against the loop. No `report` was written into
`runs/policy-gaps/`, no closure was appended to the precedent library, no
proposal was drafted, no amendment was approved, no rerun was run and no diff
was written. The one command that was run was `report` with `--out-dir` pointed
at a temporary directory, which is the override this sheet gives for that
command; `runs/policy-gaps/` is exactly as it was.

## D1. Five fixes, each with a scripted test that failed first

The tests live in `tests/test_policy_gaps_wild.py` (new, 18 tests). They were
run against the unfixed code first and **failed as designed** -- `Ran 18 tests in
1267.198s / FAILED (failures=7, errors=7)`, every one of the fourteen for the
reason its test is about:

| test | what it saw before the fix |
|---|---|
| `WildSourceRerunTests.test_the_plan_reads_a_wild_source_as_the_re_runnable_set` | `'wild-dev' != 'wild'` -- a `wild` source was planned as `wild` |
| `TranscriptOnlyCaseTests.test_the_case_is_affected_even_though_it_has_no_case_file` | `506 not found in []` -- a case with only a transcript was not an affected case |
| `TranscriptOnlyCaseTests.test_its_cost_comes_from_the_transcript_and_the_plan_says_so` | `KeyError: 'recorded_tokens_from'` |
| `BothWildSetsTests.test_a_report_over_both_is_refused` | `PolicyGapError not raised` |
| `BothWildSetsTests.test_a_rerun_over_both_is_refused` | `PolicyGapError not raised` |
| `BothWildSetsTests.test_a_diff_whose_record_names_both_is_refused` | `PolicyGapError not raised` |
| `MissingDestinationTests.test_the_missing_case_is_marked_and_the_present_one_is_not` | `KeyError: 'new_no_ruling'` |
| `MissingDestinationTests.test_the_missing_case_counts_as_newly_missing` | `False is not None` -- a missing destination graded as nothing |
| `MissingDestinationTests.test_the_rendered_row_says_no_ruling` | `'no ruling' not found` in the row for 112 |
| `VersionTwoNoteTests.test_the_document_carries_the_note` | `AttributeError: module 'eval.policy_gaps' has no attribute 'VERSION_TWO_NOTE'` |
| `VersionTwoNoteTests.test_the_note_says_the_gains_are_not_the_amendment_s_alone` | `KeyError: 'version_note'` |
| `WildSourceRerunTests.test_nothing_is_created_under_the_held_out_sets_root` | the version guard: the amendment was under a temporary root and the repository is at version 1 |
| `WildSourceRerunTests.test_the_record_names_the_mapping_and_the_destination` | the same guard |
| `WildSourceRerunTests.test_the_run_lands_under_the_re_runnable_sets_root` | the same guard |

The last three are the same guard, and the fixture was wrong rather than the
code: a version-2 rerun is only reachable when `policy/amendments/` holds the
amendment, and `policy_versions.amendments_dir` is the one place that path is
computed. `LoopCase` now patches that function for the length of each test, the
way `tests/test_policy_gaps.RerunTests` already does, and asserts on cleanup
that `policy/amendments/` still holds nothing but its `README.md`.

### The rerun source

`RERUN_SET_FOR` names the mapping once: `wild` is re-run as `wild-dev`.
`plan_rerun` reads the source's set off the path, maps it, and records **both**
halves in every source -- `set` is the set the run will be written as,
`source_set` is the set it was read as. `rerun.json` therefore says which run
directory a figure came from and which set it was run as, and `destinations` is
keyed by the set the run lands in. `runs/wild-dev/policy-v<N>/<model>/` is where
a version-N rerun of the held-out cases goes, and
`WildSourceRerunTests.test_nothing_is_created_under_the_held_out_sets_root`
proves by tree digest that `runs/wild/` is byte-for-byte what it was.

### The affected cases

`recorded_cases` walks **the set's own case list**, not the case files on disk.
A case the run recorded only a transcript for is still a case the run produced,
and the held-out set has two of them -- 517 and 533 -- which a listing taken
from `case-*.json` leaves out of a rerun entirely. A case the set does not hold
is never included, whichever file happens to be in the directory.

The cost of such a case is summed out of its transcript's entries
(`prompt_tokens + completion_tokens`, the same sum a case file's
`tokens.total_tokens` is, through `run_benchmark.billed_tokens`), and the plan
says which of the two the number came from: every affected case carries
`recorded_tokens_from`, either `case_file` or `transcript`, and `rerun` prints
it. `TranscriptOnlyCaseTests` deletes a case file and asserts the case is still
affected, that its cost equals the transcript's sum, and that a case with a file
reports `case_file`.

### Wild and wild-dev together

`_refuse_both_wild_sets` refuses a command given both. `build_report` and
`plan_rerun` read the set off each run directory; `build_diff` reads it off the
run directories the rerun record names. The message names both sets and says
they are the same 64 cases, so a reader is told what the refusal is about rather
than only that something was refused. `BothWildSetsTests` shows each of the
three refusing, and shows either set alone still accepted.

### `diff`

* A destination case file that is not there is a **miss**, not a blank. The case
  carries `new_no_ruling: true`, `new_exact` is `False` rather than `None`, it is
  counted in `newly_missing`, and its row renders as `no ruling`. Reading it as
  "nothing to compare" would hide exactly what the diff exists to find.
* A version-2 diff carries `version_note`, and `render_diff` prints it under the
  key note. `VERSION_TWO_NOTE` says that version 2 holds **both** this amendment
  and part B's POL-RD-11 upfront-quote remedy, that both change the brief a case
  is read from, and that these gains therefore cannot be attributed to the
  amendment alone. It is emitted at version 2 and nowhere else: a later diff
  says what *it* carries when it is written, rather than borrowing this note.

### No-show briefs at version 2

A no-show brief at version 2, with a `POL-RD` amendment approved, is
byte-identical to the same brief at version 1. `loader.load_policies` takes no
root, so the test patches the amendments directory and compares the two
digests; the repository's own `policy/amendments/` is never written to. This is
the property that makes the loop safe to run at all: approving a route-deviation
amendment does not move a no-show case's brief, so a version-1 run of that
category still reads as current.

## D2. The report over the three runs

Run once, with `--out-dir` pointed at a temporary directory:

```
python3 -m eval.policy_gaps report \
  --run-dir runs/deepseek-deepseek-flash \
  --run-dir runs/codex/deepseek-deepseek-flash \
  --run-dir runs/wild/deepseek-deepseek-flash \
  --min-cases 2 \
  --out-dir "$TMPDIR/d2-policy-gaps-report"
```

It read all three runs and analysed every cached case in each:

```
runs/deepseek-deepseek-flash (corpus): 29 cached, 5 undecided
runs/codex/deepseek-deepseek-flash (codex): 15 cached, 4 undecided
runs/wild/deepseek-deepseek-flash (wild): 62 cached, 7 undecided
```

`Not analysed, and why:` is `none` -- the held-out run reads as current, so none
of its cases is stale and none is unreadable. (It holds 62 case files and 64
transcripts: 517 and 533 produced only a transcript, which is why the report
says 62 cached and the rerun's case list says 64.)

**508 and 530 are in `C4`, `ROUTE_DEVIATION / below_confidence_floor`, level 1,
flagged, 6 cases.** The other four are **110** and **112** (corpus), **512**
(wild) and **9115** (codex). All six are `ESCALATE` on the confidence floor,
with confidences 0.39, 0.40, 0.60, 0.39, 0.0 and 0.60 respectively, and none
carries a leading referral clause.

**504 sits elsewhere: it is alone in `C5`, `ROUTE_DEVIATION / judge_no_clause`,
level 1, not flagged.** It is `ESCALATE` at confidence 0.70 with no referral
clause, which is a different trigger from the floor -- so it is not a case the
same clause would decide, and it is not in the cluster the owner is asked to
close.

The other clusters, for orientation: `C1` (`NO_SHOW_CHARGE /
below_confidence_floor`, 4 cases, flagged) holds 210, 213, 626 and 9109; `C2`
(`NO_SHOW_CHARGE / clause:POL-NS-07`, 3 cases, flagged) holds 207, 622 and 9108;
`C3` holds 9110 alone; `C6` holds 501 alone; and `C7`-`C13` are the level-2
clusters, one or two cases each. One signature pair,
`TRAFFIC_ADVISORY:MISSING_ARTIFACT`, was dropped as noise: it appears in at
least 80% of the given runs' cases and so distinguishes none of them.

## The owner's commands, none of them run

Every decision value below is a **placeholder**. No value is taken from the
sheet or from `eval/`: `<RULING> <AMOUNT> <DRIVER_COMP> <REFERRAL>
<CLAUSE_ID> <NAME> <TEXT>` are the owner's to fill in, and the loop reads none
of them until the owner writes them.

**1. Close 508 and 530.** One command per case. This is the only step that
appends to the precedent library, and the library is append-only and
hash-chained.

```
python3 -m tribunal.precedents close \
  --run-dir runs/wild/deepseek-deepseek-flash \
  --case 508 \
  --ruling '<RULING>' \
  --amount '<AMOUNT>' \
  --driver-compensation '<DRIVER_COMP>' \
  --referral '<REFERRAL>' \
  --clause '<CLAUSE_ID>' \
  --closed-by '<NAME>' \
  --summary '<TEXT>'

python3 -m tribunal.precedents close \
  --run-dir runs/wild/deepseek-deepseek-flash \
  --case 530 \
  --ruling '<RULING>' \
  --amount '<AMOUNT>' \
  --driver-compensation '<DRIVER_COMP>' \
  --referral '<REFERRAL>' \
  --clause '<CLAUSE_ID>' \
  --closed-by '<NAME>' \
  --summary '<TEXT>'
```

**2. Report.** No model call. `--out-dir` is the owner's to choose; the
repository's own `runs/policy-gaps/` is written only if the owner leaves it out.
The cluster to draft from is `C4` in the report built above.

```
python3 -m eval.policy_gaps report \
  --run-dir runs/deepseek-deepseek-flash \
  --run-dir runs/codex/deepseek-deepseek-flash \
  --run-dir runs/wild/deepseek-deepseek-flash \
  --min-cases 2 \
  --out-dir <OUT_DIR>
```

**3. Draft.** One model call, and the only one in the sequence. It refuses
unless the cluster has at least two human closures, which is what step 1 is for.

```
python3 -m eval.policy_gaps draft \
  --report <REPORT> \
  --cluster <CLUSTER_ID>
```

**4. Approve.** The only writer of `policy/amendments/`.

```
python3 -m eval.policy_gaps approve \
  --proposal policy/proposals/<NNNN-slug>.json \
  --approved-by <NAME>
```

**5. Rerun.** First without `--yes`, so the owner sees the plan and the
estimate and nothing is called; then the same command with `--yes`. The `wild`
source is re-run as `wild-dev`, into `runs/wild-dev/policy-v<N>/<model>/`, and
nothing is created under `runs/wild/`.

```
python3 -m eval.policy_gaps rerun \
  --amendment <NNNN> \
  --run-dir runs/deepseek-deepseek-flash \
  --run-dir runs/codex/deepseek-deepseek-flash \
  --run-dir runs/wild/deepseek-deepseek-flash

python3 -m eval.policy_gaps rerun \
  --amendment <NNNN> \
  --run-dir runs/deepseek-deepseek-flash \
  --run-dir runs/codex/deepseek-deepseek-flash \
  --run-dir runs/wild/deepseek-deepseek-flash \
  --yes
```

**6. Diff.** The one command that reads the frozen version-1 key, and its output
says so.

```
python3 -m eval.policy_gaps diff --amendment <NNNN>
```

## What this does not do

* It does not close anything, draft anything, approve anything, rerun anything
  or diff anything. Every command above is the owner's to run.
* It does not overwrite `runs/policy-gaps/`. The one report that was built went
  to a temporary directory.
* It does not decide 508 or 530. Which cluster holds them is a fact about the
  recorded runs; what they should have been ruled is the owner's.
* It does not make a `wild` and a `wild-dev` run readable together, in any
  command. That is a refusal, not a gap to be closed later.
* It does not change what `report`, `draft`, `approve`, `reject` or `rerun` do
  for the corpus or the second set. The only behavioural changes are the five
  above, and each is gated on a `wild`/`wild-dev` run being in play or on a
  version-2 diff.
