# The advocate-effort switch

*Post-sealed work, 2026-10-10. Part 30. Nothing here re-runs, re-reads or
re-scores a sealed run, and no sealed figure moves.*

## Why

The two advocates are the slowest part of a case. Over the 171 version-6 cases
with four drafts, the slower advocate call has **median 91 s** and **90th
percentile 140 s**, against the whole case's 160 s and 290 s. The judge's panel
is slower per call than either advocate, but the panel's cost is the point of the
vote; the advocates' reasoning is where a saving would be, if the rulings survive
it.

`tribunal/llm.py` already supports `reasoning_effort`: omitted leaves reasoning
on, and the explicit string `"none"` suppresses it. Both facts are measurements,
recorded with how they were taken in
[`2026-09-21-tokenhub-api-facts.md`](2026-09-21-tokenhub-api-facts.md).

**This part adds the switch and the report. It makes no paid run.** Whether
turning reasoning off for the advocates keeps the rulings and saves time is the
owner's to measure, with a paid run, on a set the owner chooses.

## The switch

`--advocate-effort {default,none}` on `eval.run_benchmark` and
`eval.development_sets`, threaded as one keyword through `run_set`,
`run_benchmark`, `run_one_case` and `run_case`/`run_loaded_case`.

- **`default`** -- the default -- leaves every request exactly as it is today.
  `default` maps to the same sentinel `temperature` and `seed` already use, so
  the two advocate bodies are byte for byte the bodies every run before the
  switch sent, and a run with the switch off is the run it was.
- **`none`** makes the **two advocate requests** carry
  `"reasoning_effort": "none"`. The judge's drafts and the verifier are
  untouched: they name no `reasoning_effort` at all, so a case's four drafts and
  its verifier call are the requests they always were.

The per-call override is the client's: `LLMClient.complete` and
`LLMClient._request_body` gained a `reasoning_effort` argument beside
`temperature` and `seed`, and the client's own setting is not modified by a call
that overrides it.

**It is a switch that changes what a run measures**, so it follows the rule the
ablation follows rather than the rule `--parallel-calls`, `--early-majority` and
`--integrity-gate` follow:

- it is written into the `configuration` every artifact carries -- and only when
  it is not the default, so a plain run's artifacts are byte for byte what they
  always were -- as well as into the `invocation_start` event and into the run's
  `run.json`;
- a run under it goes to a root of its own,
  `runs/advocate-effort-<effort>/<set>/[policy-v<N>/]<model>/`, at the **top** of
  the runs tree, with the set's own subdirectory under it -- so
  `runs/advocate-effort-none/policy-v6/<model>/` for the corpus and
  `runs/advocate-effort-none/codex/policy-v6/<model>/` for the second set -- and
  the destination is checked in code rather than merely chosen;
- it is refused beside the other switches that change what a run measures
  (`--ablate`, `--precedents`, `--amount-rule`) and beside a replay, which calls
  no advocate for the switch to reach;
- it **may** be given with `--policy-version`: the version's directory sits under
  the switch's own root, so the two do not confound each other. That is the
  second allowed pair, `--precedents` with `--policy-version` being the first;
- it is refused for **every sealed set** by the set's own name. Unlike the three
  switches above, this refusal is not left to the destination guard: the switched
  run goes to a root of its own, outside the sealed root, so no destination guard
  would notice it.

## The report

`python3 -m eval.advocate_effort --report --baseline <run dir> --candidate <run dir>`

reads two run directories of one set -- the committed version-6 run as the
baseline and the switched run as the candidate -- and prints, over the cases both
runs have:

- the four-field exact figure against the key for each run, with Wilson 95%
  intervals, and each of the four graded fields separately;
- the cases whose ruling changed, with both sides' four graded fields and the
  direction the change went in (improved, regressed, or moved between two
  misses);
- the claims each advocate produced and the claims the referee discarded, per
  run, read off each case's own `referee` ledger;
- the advocate stage's time (the slower of the two calls), the judge stage's and
  the whole case's wall clock, as a median and a 90th percentile, per run; and
- the tokens and the cost per case at the owner's prices.

The key is the **baseline's** set's, resolved from where the baseline sits under
`runs/`; `--key` names one explicitly, which is what a run directory outside
`runs/` needs. The module makes no model call, launches no browser and writes
nothing.

## What was verified, and what was not

**No test was run**, per the sheet: the owner runs every test outside the
sandbox. The behaviour was verified from the record instead, with a scratch
script outside the repository that drove the real `run_loaded_case` and the real
`run_benchmark` over a fake transport:

- with the switch at `default`, every request body carries exactly the five keys
  it carried before the switch existed -- `model`, `messages`, `temperature`,
  `seed`, `response_format` -- for the two advocates, the four drafts and the
  verifier alike;
- with the switch at `none`, exactly the two advocate bodies carry the sixth key
  and every other body is unchanged, and each switched body is its default body
  plus that one key;
- a switched run lands at
  `runs/advocate-effort-none/<model-slug>/`, at
  `runs/advocate-effort-none/policy-v6/<model-slug>/` with `--policy-version 6`,
  and a default run lands where it always did, with no `advocate_effort` key in
  any artifact;
- the switch is refused beside `--ablate`, `--precedents`, `--amount-rule`,
  `--compare`, `--replay-advocates`, `--replay-check`, `--verify-recorded-drafts`
  and `--external`, and refused for `wild`, `wild-v2` and `sealed-v1` by the
  set's own name, at `run_set` and at the command line;
- `eval.sealed_roots.refuse_a_sealed_destination` still refuses all three sealed
  roots and does not refuse the switch's own root; and
- the report over two run directories built for it computes the figures it
  promises: three of three exact for the baseline, two of three for the
  candidate, one case regressed and two unchanged, the cost equal to the case
  file's own tokens at the owner's prices, and one claim per advocate with none
  discarded.

`tests/test_advocate_effort.py` holds the same claims. It reads nothing under
`runs/`: both run directories it measures over are built in a temporary
directory.

**Not measured here.** Whether `none` keeps the rulings, and what it saves, on
the real cases. That is a paid run and the owner's to make.
