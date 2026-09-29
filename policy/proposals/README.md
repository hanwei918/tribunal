# Policy proposals

One file per proposal, named `NNNN-<slug>.json`, numbered the same way the
amendments are. This directory ships **empty**.

A proposal is what the policy-gap loop produces when the policy runs out: a
cluster of cases the policy could not decide, and a clause drafted to decide
them. It is written by an **offline tool a human runs** — not by a run and not
by a runtime agent — and it decides nothing on its own.

## A proposal is not an amendment

Nothing in this directory changes a brief. A proposal becomes policy only when a
person reads it and runs `approve`, which writes the amendment to
`policy/amendments/` and records who approved it and when. Until then the
clause it drafts is not in the policy, not in any brief, and not in any figure.

That separation is the whole point of the two directories. The drafter may be
shown the cases, the votes and the precedent library, so its output is a
suggestion about what the policy should say; a clause that a model wrote is not
policy, and only a human can make it one.

## Naming

`NNNN` continues the same sequence the amendments use, so a proposal and the
amendment it becomes can be named after each other and the chain from a cluster
of cases to a clause in a brief stays readable.
