# The fifth sealed set's run, stopped after 8 of its 30 cases

**2026-10-13.** The fifth sealed set, `sealed-v3`, was run once, by the owner,
from the commit `9b70387` (part 60), whose `tribunal/`, `prompts/` and `policy/`
trees equal those at the annotated tag `freeze-2026-10-11`. The run was started
at 17:50:26 SGT and **stopped at 18:44:08 SGT, after 8 of the set's 30 cases had
a ruling**. Its record is committed exactly as it was left under
`runs/sealed-v3/deepseek-deepseek-flash/` -- 19 files, recorded in
`runs/sealed-v3-manifest.json` -- with the console log of that one invocation at
`runs/sealed-v3-console.log`. The owner's run made the model calls; none was made
in this repository in committing or reading it. **No file of the run was edited,
re-serialised or regenerated.**

Nothing in this note changes a ruling, a prompt, a policy, a case file or the
key. It records what happened to the run.

## The run, and how it stopped

The command, run by the owner outside this sandbox, one invocation:

    TRIBUNAL_SEALED_RUN=sealed-v3 python3 -m eval.development_sets --set sealed-v3 --parallel-calls --concurrency 2 --timeout 900

| | |
|---|---|
| started | 2026-10-13 17:50:26 SGT (`run.json` `started_at` 09:50:26 UTC) |
| ended | 2026-10-13 18:44:08 SGT (`run.json` `ended_at` 10:44:08 UTC) |
| commit | `9b703876f7fcb9548dc76249a9e081669664011a` |
| tag the trees equal | `freeze-2026-10-11` -- `git diff --stat freeze-2026-10-11 9b70387 -- tribunal prompts policy` prints nothing |
| working tree | clean -- `run.json` records `working_tree_clean: true` |
| policy version | 6 (the version the set's registration fixes) |
| tokens | 1,780,022 consumed by the invocation |

Three things happened, in this order.

1. **The owner's network dropped shortly after 18:02.** Cases **4007 and 4008
   ended `TIMEOUT`** -- 901.1 s and 1007.5 s, 0 tokens each, "the client stopped
   waiting for a response" -- and the run went on.
2. **At 18:35 Ryde released its own Dispute Resolution Policy v2.1** to the
   track. The owner decided to adopt it as **policy version 7**, and **not to
   complete `sealed-v3`**, whose key was written under version 6.
3. **The run process ended at 18:44:08**, when the owner's session ended, with
   cases **4010 and 4012 in flight**. It was not restarted, and **it will not
   be**.

## What the record holds

| | |
|---|---|
| cases with a ruling | **8** -- 4001, 4002, 4003, 4004, 4005, 4006, 4009, 4011 |
| cases that failed | **2** -- 4007, 4008, both `TIMEOUT` |
| cases with no attempt that finished | **20** |
| cases in the set | **30** |

`run.json` records the invocation's own three lists: `cases.completed` is
`[4002, 4003, 4001, 4004, 4006, 4005, 4009, 4011]`, `cases.failed` is
`[4007, 4008]`, and `cases.requested` is the set's 30 cases.

Of the 8 cases that have a ruling, **7 agree with the key on all four graded
fields, and 1 -- case 4001 -- does not.** No value of the key or of a ruling is
stated here: the point is only that one of the eight differs.

**This is not a sealed result. Eight cases are not the thirty the set was built
to measure, and which eight finished was decided by the run order and the
outage, not chosen. The record is committed so that nothing about the set is
hidden; no figure from it is reported anywhere else.**

## What this changes

The set stays closed and its run is a stopped run, not a figure:

* `eval/development_sets.py`'s `SEALED_V3` summary now says the run was started
  once on 2026-10-13 and stopped after 8 of its 30 cases, and that it is not a
  sealed figure and is never run again.
* `eval/run_benchmark.py` names `sealed-v3` in `MADE_SEALED_RUNS_SUBDIRS`, so
  `runs/sealed-v3/` is closed outright like the other four sealed roots:
  `UNRUN_SEALED_RUNS_SUBDIRS` is empty again and no permit opens the root, so a
  plain run, a `--force`, an ablated run, a run at a later policy version and a
  report are all refused.
* `python3 -m eval.sealed_report --set sealed-v3` prints the stopped state
  plainly -- 8 of 30 with a ruling, 2 failed, 20 not run -- and **no agreement
  rate and no interval**: eight answers from a run that stopped are not the
  thirty the set was built to measure.
* `docs/record.md`'s provenance row for `sealed-v3` states the same, and links
  this note. No figure from the set is stated in the README, the site or the
  submission documents, and none must be.
