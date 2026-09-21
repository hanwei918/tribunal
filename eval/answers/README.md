# eval/answers/ — evaluation answer key

This directory holds the expected outcome for every case in the corpus. It is
committed to the repository on purpose: this repository is the submitted source,
and an accuracy claim that a judge cannot reproduce is worth nothing. The key is
the only independent measurement of the arbitration system, so it travels with
the code it measures.

## Files

`ground_truth.json` — the full ground-truth block per case, keyed by `case_no`,
`rationale` included.

There is no second file. `eval_index.json` used to sit beside this one, holding
the same answers with `rationale` removed. It was deleted on 2026-09-21, after
being checked field by field against this file: the same 29 cases, no field on
which the two disagreed, and no field in the index that was absent from the
ground truth. Two files carrying the same answers, with nothing keeping them in
step, is a second source of truth that drifts the first time one is edited and the
other is not — and a silently drifted answer key is the worst failure this
repository can have. `ground_truth.json` is the single source.

## Where this came from

The answer key was produced by a deterministic generator before the hackathon
kick-off on 2026-09-16. The expected rulings inside it were authored by hand, not
generated. The corpus under `data/` and this key came from the same seeded run, so
each expected value here corresponds to the case file carrying the same `case_no`.

The arbitration system — the agents, the pipeline, the transcript and the
evaluation — is what was built in WorkBuddy from 2026-09-16 onward. The dataset is
not a WorkBuddy product and must not be described as one.

## The isolation rule

Nothing under `tribunal/` may read anything under `eval/`, and no answer field may
appear in any Agent runtime bundle. The second control is the stronger of the two:
it holds wherever an answer came from, including a case file edited by hand.

Both controls are asserted by `tests/test_answer_isolation.py`, which also proves
the content check is capable of failing.

The answer key is frozen. If a run disagrees with `ground_truth.json`, the answer
does not change; see the freeze rule in `START-HERE.md`.
