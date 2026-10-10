# Early majority: stop waiting once the panel has settled

**2026-10-10.** With `--parallel-calls` the judge's four drafts are asked
together and the case waits for the slowest. A majority of four is three, and
three drafts that have already agreed cannot be changed by a fourth that has not
answered, so the wait buys nothing. `--early-majority` is a new switch that
publishes the panel as soon as a majority has settled. It is **off by default**,
it needs `--parallel-calls`, and it is refused for every sealed set. With it off
nothing changes: every byte of every brief, request, result and vote block is
what it was.

The switch reaches the pipeline as one keyword through `run_set`,
`run_benchmark` and `run_case` (and `run_loaded_case` and `replay_case`, which
are the two bodies those delegate to), and it is recorded where
`parallel_calls` is recorded and nowhere else: the `invocation_start` event and
the run's `run.json`. It is deliberately **not** in a case's `configuration`
object, because no individual request body depends on it -- the same four drafts
are asked, with the same messages -- so a result produced with it on is the same
result.

The change touches no prompt, no policy and no case data: it is
`tribunal/pipeline.py`, `eval/run_benchmark.py`, `eval/development_sets.py`, the
new `eval/early_majority.py`, this note and two test modules. Nothing under
`runs/` was changed or staged -- the report below reads it read-only -- and
nothing under `tmp/` was committed.

## The rule

When it is on, the panel publishes as soon as **all** of these hold:

* the **position-swapped draft** has answered -- it is always waited for,
  because the fairness measurement of part 15 reads it;
* at least **two sampled drafts** have answered; and
* **three of the returned drafts** are valid -- they pass the ten code checks --
  and agree on all four graded fields together.

Otherwise it waits for all four, exactly as it did before. A draft the panel did
not wait for is recorded in the transcript and in the vote block as
`not_awaited`, it is excluded from the vote's `valid` count and from the
majority, and the vote block says `early_majority: true`. Its request may still
complete on the wire -- a `Future` cannot cancel a call that is already running
-- and it is written down if it had answered by the time the panel published,
but it does not count.

The rule is applied in exactly one place, `tribunal.pipeline._run_judge_vote`,
and the join that stops early is `tribunal.pipeline._join_calls_until`. The
draft checks and the four-field reduction are the pipeline's own, so "three
drafts agree" means what it means in the vote and not a second reading of the
same fields.

## What it would have saved, from the record

`python3 -m eval.early_majority --report` is read-only and makes no model call.
It replays the rule over every version-6 case with four judge drafts --
`runs/policy-v6/`, `runs/dev-v2-ext/policy-v6/` and `runs/sealed-v1/` -- using
each draft's own recorded `duration_seconds`, and it **asserts** that the
published ruling is the same either way. The whole report, pasted as it printed:

```
Early majority, replayed from the version-6 record
read from the committed runs under runs/; no model call, no browser

the rule: the position-swapped draft plus 2 sampled drafts back, and 3 of the returned drafts valid and agreeing on all four graded fields

== The cases ==
   corpus      29 cases, 29 with four judge drafts
   dev-v2-ext  120 cases, 118 with four judge drafts
   sealed-v1   24 cases, 24 with four judge drafts
   all         173 cases, 171 with four judge drafts

== The rule ==
   would stop early        105 of 171
   would wait for all four 66 of 171
   the published ruling is identical in every case: asserted over all 171 (the four graded fields; 105 would have stopped early)
   the explanation's vote sentence would differ in 102 of them: 101, 106, 109, 110, 111, 113, 114, 115, 202, 203, 205, 206, 207, 210, 212, 213, 214, 2701, 2702, 2703, 2709, 2711, 2712, 2713, 2714, 2716, 2717, 2718, 2719, 2720, 2722, 2725, 2726, 2727, 2729, 2730, 2731, 2732, 2734, 2736, 2737, 2738, 2739, 2740, 2741, 2746, 2747, 2751, 2753, 2755, 2801, 2802, 2804, 2805, 2806, 2807, 2808, 2812, 2813, 2815, 2816, 2817, 2818, 2824, 2826, 2827, 2828, 2830, 2832, 2833, 2835, 2837, 2839, 2840, 2841, 2842, 2846, 2847, 2849, 2851, 2852, 2854, 2856, 2857, 2859, 2860, 301, 303, 305, 307, 308, 309, 401, 403, 404, 405, 406, 408, 409, 410, 411 and 412
     the four graded fields are the same either way; the sentence reads '3 of the 4 agreed' where the whole panel would have read 'every draft agreed', because the draft the rule did not wait for would have agreed

== The judge stage, seconds (the slowest draft the panel waited for) ==
   with the rule       median    49.0   p90   176.6   max   506.1
   without it          median    56.2   p90   204.2   max   533.5
   saved               median     2.5   p90    26.7   max   253.3
   over the 105 the rule stops early on: median 8.1   p90 50.7   max 253.3
   the ideal bound -- always stopping at the third-fastest draft -- is median 44.8   p90 140.1   max 455.7

== The whole case, seconds (the slower advocate plus the judge stage) ==
   with the rule       median   153.1   p90   273.7   max   624.7
   without it          median   160.3   p90   290.0   max   699.1
   saved               median     2.5   p90    26.7   max   253.3

== These are replayed timings ==
   the durations are the ones the provider reported for calls that were all made together; a live run's panel is rate-limited by the same client and contends with the other cases' calls, and the draft the rule stops waiting for may in a live run be the fast one. A live run may differ.
   what is not a timing is the published ruling: it is asserted identical over every case above.
```

**These are replayed timings and a live run may differ.** The durations are the
ones the provider reported for calls that were all made together. A live run's
panel is rate-limited by the same client, its drafts contend with the other
cases' calls, and which draft is slow is the network's business: the draft the
rule stops waiting for in a live run may be the fast one. What is *not* a timing
is the published ruling, and that is asserted rather than assumed -- over all 171
cases, not only the 105 the rule stops early on.

Three things the figures say. **The rule fires on 105 of 171 cases (61 %).** The
66 it does not fire on are cases where the swapped draft, or the third agreeing
draft, was not back when three had answered. **The saving is smaller than the
switch's own motivation suggests, and for a reason worth stating:** the ideal
bound -- always stopping at the third-fastest draft, whatever it is -- is median
44.8 s / p90 140.1 s, and the rule's own figure is median 49.0 s / p90 176.6 s,
because the position-swapped draft is always waited for and a panel whose three
fastest drafts are all sampled must wait for it. **The four graded fields are
identical in every case; the vote sentence is not.** In 102 of the 105 the draft
the rule did not wait for would have agreed, so the whole panel would have
reported "every draft agreed ... carried unanimously" where the early panel
reports "3 of the 4 drafts agreed ... carried, not unanimous". The explanation
text therefore differs in those cases; the ruling a reader acts on does not.

## What is refused

* **`--early-majority` without `--parallel-calls`.** Refused at both command
  lines and again in `run_benchmark` and `run_set`, because what the rule stops
  waiting for is a call already in flight and a sequential panel has none.
* **`--early-majority` for a sealed set.** Refused by the set's own name through
  `assert_not_sealed`, in the same list `--force` is refused in, and again in
  `run_set`. A sealed set's single run is one measurement and is not re-taken;
  its registration does not fix this switch, and this switch cannot move it.
* **`--early-majority` with `--verify-drafts`.** Refused at both command lines
  and in `run_benchmark`. The verifier runs over every valid draft *after* the
  panel has been checked, and a contradiction can take a vote away, so a panel
  that published at three could publish a ruling the full panel would not have
  carried. The two switches are not merely incompatible; the rule is unsound
  under the verifier, and refusing says so.

On a panel of fewer than four drafts the rule cannot fire -- three drafts cannot
be returned without the fourth -- so the switch has no effect there. That is
stated in the help text rather than refused, because it is a property of the
panel size and not a switch that was dropped.

## What the vote block says, and one deliberate reading

A run whose switch is off writes the vote block it always wrote. A panel that
stopped early adds two things and changes no field's meaning:

* each draft it did not wait for carries `not_awaited: true`, and its `valid` is
  `false` -- not because its answer failed a check, but because it does not
  count. Its raw answer, if it arrived, is still on the transcript.
* the vote block carries `early_majority: true`.

`votes` stays the panel -- four, how many times the judge was asked -- and
`valid` counts the drafts that counted, three. **`agreement` is the share of the
panel that agreed**, `agreeing / votes`, which is what the field has always
meant, so it reads 0.75 here and the vote sentence says "3 of the 4 drafts
agreed". The un-awaited draft contributes to neither the numerator nor the
`valid` count; it is in the denominator because the judge *was* asked four times.
The four graded fields are the winning draft's own and are the same ones the full
panel would have published -- that is the assertion above -- so the reading
costs nothing a reader acts on.

## The one thing the implementation does not wait for

`_join_calls_until` shuts its pool down with `wait=False`: the calls still in
flight are exactly the ones the panel decided not to wait for, and joining them
would give back the time the rule saves. A request already on the wire cannot be
cancelled, so such a call may still complete and still reaches the client's own
call record; it is written into the case's transcript only if it had answered by
the time the panel published, which is why `not_awaited` is a fact about the
panel and not a claim that the request never happened.

## Tests

`tests/test_early_majority.py` covers the rule with a transport that answers each
draft after a **fixed delay**, so the order the drafts come back in is the
script's and not the network's, and it records which drafts had answered when
the panel published: three agreeing drafts first with the swapped draft among
them stops early, with the same four graded fields the whole panel publishes; the
swapped draft slowest waits for it; a dissent among the first three waits for all
four; an invalid draft among the first three does not count; the switch off
writes the block it always wrote, and ignores a script that would have stopped
it. The refusals are covered there too -- the pipeline, the runner and both
command lines, for `--parallel-calls` and for `--verify-drafts`, and the sealed
set by its own name.

`tests/test_run_benchmark.py` adds three checks that the switch is recorded where
the parallel one is and nowhere else: not in a case's `configuration`, named in
`run.json` and in the `invocation_start` event only when it is on.

**They were not run here.** The owner runs every test outside this sandbox. What
the session executed is the report above, a byte-compile of every changed module,
and one throwaway script outside the repository that drove the rule over a fake
transport to see it fire; the test modules themselves were never run.
