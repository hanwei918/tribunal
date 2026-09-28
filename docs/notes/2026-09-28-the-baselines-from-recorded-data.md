# The baselines, computed from recorded data with no model call

2026-09-28. Queue 2026-09-28, task 2. No model call was made.

## Why a baseline file exists at all

A score on its own says very little. If a rule that reads no case — "always
ESCALATE" — scored the same as the panel, the panel would be doing nothing that
the rule is not doing, and the figure would be no evidence at all. The baselines
are what a reader compares the headline figure against, and they are the reason
the comparison can be made rather than asserted.

The file costs nothing to produce, which is the property that makes it worth
having: every row is computed from what a run has already recorded — the judge
drafts on its transcripts and the rulings it published — so it reads the cache,
calls nothing, and can be regenerated after any run without paying for that run
again.

## Where it lives, and how it is run

    python3 -m eval.baselines [--set corpus|codex|all]

It writes `runs/baselines/report.md` and `runs/baselines/baselines.json`, and
`--out-dir` moves both. It lives under `eval/` because it reads the answer keys,
which nothing under `tribunal/` may do.

The directory is named `baselines/` and not after a model, so "these are not that
run's figures" is a property of the path rather than a promise. It is enforced
anyway, before anything is written:

- the current model's own run directory is refused by name, whether or not it
  exists yet;
- everything under `runs/external/` is refused, because every directory there is
  a headline directory;
- and every directory from the destination up to the runs root is refused if it
  holds a run's own `run.json` or any `case-*.json` — so another model's run
  directory is refused too, and so is a destination *inside* one. That last check
  is structural rather than a list of names, because a list of names would be
  wrong the first time somebody added a set.

## Drafts are rebuilt one way, and it is the recorded way

`eval/baselines.py` builds a case's panel with
`verify_drafts.recorded_drafts_for_case` followed by
`pipeline.recorded_judge_drafts`, which is the same reconstruction the
recorded-drafts measurement uses. So a row here and a row there count the same
drafts, and a row here cannot quietly become a second sampling of the judge.

Two tests hold that down rather than a promise:

- one parses the module with `ast` and asserts that the names
  `verify_recorded_case`, `verify_recorded_run`, `_default_client_factory` and
  `LLMClient` never appear as a name, attribute or import alias. The docstrings
  mention two of them, and a docstring is a constant rather than a name, which is
  the point: the check is on what the module *reads*, not on what it says.
- the other patches `tribunal.llm.LLMClient` to raise and then runs
  `eval.baselines.main`. A module that built a client would fail there instead of
  spending the owner's balance.

## A case that cannot be scored is refused, not counted as a miss

Three things take a case out of every figure:

- its cached result is **stale** on either channel, or **unknown** — checked with
  its **own set's loader**, because a development set handed the corpus loader
  reads `unknown` on every one of its cases and would be refused for the wrong
  reason;
- its run holds **no panel of drafts** — the judge was asked once, so there is
  nothing to score a single draft from;
- its recorded drafts were produced under a **different judge prompt** from the
  one this code holds.

Each refusal is listed with its reason in both files, and the case is left out of
every denominator rather than counted as a miss. That distinction is the whole
difference between "the panel got this wrong" and "this could not be measured
here", and the two must not be added together.

A row measured over no case renders `-`, not `0/0`. "Not measured" and
"measured, and zero" are different findings.

**One limitation this creates, stated rather than hidden:** a run with
`--judge-votes 1` records no panel, so every one of its cases is refused and no
baseline can be computed from it at all. That is the queue's rule — a case with
no vote block is refused — and it is the right rule, but it does mean the
baselines are only available for runs made with the vote on.

## The rows

| Row | What it answers |
|---|---|
| Always ESCALATE | Null amounts and no referrals, on every case. |
| Majority ruling | The ruling the section's cases most often require, with null amounts and no referrals. |
| Single draft × 4 | Each of the four recorded drafts scored alone: seeds 101, 202 and 303, and the position-swapped draft. An abstained or invalid draft counts as a miss. |
| Single draft, mean | The arithmetic mean of the four rows above it. |
| At least one draft right | Per case, the best of its drafts. An upper bound for any rule that publishes one of the drafts' answers; a no-majority escalation can exceed it. |
| The carried vote | What the run actually published. |

Two choices the queue did not spell out, made and recorded here:

- **The majority ruling is the key's modal ruling, not the drafts'.** The other
  draft rows say "draft" explicitly; this one says "the section's most frequent
  ruling", and the modal class is what a rule that reads no case answers. It is
  computed over the cases that were analysed, which is the set it is scored on,
  and it is stated in the report as in-sample rather than a prediction.
- **A tie goes to the ruling that sorts first**, which is a rule rather than a
  preference: two runs of the same data have to pick the same one.

Every row is graded with `eval.grade` on all four fields at once — the ruling,
both amounts and the sorted referral clause references — and on the ruling alone.
The mean of the four single drafts is an arithmetic mean of four counts and not a
measurement of its own; the report says so beside it.

## The development-data caveat is carried, not rewritten

`eval/development_sets.DEVELOPMENT_DATA_CAVEAT` now holds the caveat that
module's report prints, and the baselines carry the same text. It is in one place
so the two cannot drift, and it keeps the two phrases a test pins: that the
corpus figure is the figure the submission reports, and that the sealed set is
the only generalisation figure. Neither a baseline nor the combined section is
that figure.

## The figures, and what they say

`python3 -m eval.baselines --set all`, 2026-09-28, over the committed runs. Exact
means all four fields agree.

| Row | corpus (29) | second set (15) | combined (44) |
|---|---|---|---|
| Always ESCALATE | 4/29 | 3/15 | 7/44 |
| Majority ruling | 0/29 | 0/15 | 0/44 |
| Single draft: seed 101 | 29/29 | 14/15 | 43/44 |
| Single draft: seed 202 | 27/29 | 13/15 | 40/44 |
| Single draft: seed 303 | 29/29 | 14/15 | 43/44 |
| Single draft: position-swapped | 29/29 | 14/15 | 43/44 |
| Single draft: mean | 28.50/29 | 13.75/15 | 42.25/44 |
| At least one draft right | 29/29 | 14/15 | 43/44 |
| **The carried vote** | **29/29** | **14/15** | **43/44** |

No case was refused on either set: both runs are current on both channels and
both hold a panel of four drafts.

Three things worth reading off it, none of which is a generalisation figure:

- **The headline figure is above every constant rule.** 29/29 against 4/29 for
  always ESCALATE and 0/29 for the modal ruling. The panel is not reproducing a
  rule that ignores the case.
- **On the corpus the vote adds nothing over the best single draft.** Seed 101,
  seed 303 and the position-swapped draft each score 29/29 alone, and the carried
  vote scores 29/29. The corpus is a set the panel has all four right on, so it
  cannot show what the vote is for. The second set can: there the carried vote
  reads 14/15 while three of the four single drafts also read 14/15 and seed 202
  reads 13/15, and the single case that moves is 9111, in `amount_sgd`.
- **The upper bound and the carried vote coincide at 43/44.** On this data the
  vote never loses a case that at least one of its drafts had right. That is a
  statement about these two sets and not about the vote.

## What was run

- `python3 -m unittest tests.test_baselines` — `Ran 44 tests in 190.081s` /
  `OK`.
- The three modules importing the changed code — `tests.test_baselines`,
  `tests.test_development_sets`, `tests.test_ui_build` — `Ran 157 tests in
  943.678s` / `OK (skipped=1)`. The skip is `RunCurrencyTests`: the run is
  current, so there is nothing for it to refuse.
- Discovery count `1200` against `1200` occurrences of `^\s+def test_` over
  `tests/*.py`, which is the only guard against a test that never runs.
- `python3 -m ui.build --check` — identical to a fresh build at 2371908 bytes.
- `python3 -m eval.baselines --set all` — the figures above, written to
  `runs/baselines/`.
- Credential scan of the four changed files with the pattern
  `sk-[A-Za-z0-9_-]{8,}`: no match, with a positive control that fires on a
  fabricated `sk-` string and the house fake `tok-live-FAKEKEY-…` that does not.
  `TOKENHUB_API_KEY` and `TOKENHUB_API_KEY_TEAMMATE` are both unset in the shell
  that ran the scan, so the literal-value half of the check was not made there
  and is not claimed here.

The full suite runs once, in the final check.
