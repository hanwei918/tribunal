# Tribunal — submission description

## 1. Overview

Tribunal arbitrates one ride-hail dispute and writes down why. The scenario is
Ryde's two everyday cases: a route-deviation fare, where the rider says the
driver took a longer way, and a no-show fee, where the driver says the rider
never turned up. The users are a support team and the two parties: the team
works a queue, each party may appeal once. The value is a
first decision in the minutes a case takes to run, carrying its evidence and its
clause, and handed to a person with the money held when it cannot decide.

The live demo is at <https://tribunal.edgeone.dev/> — no account, no key. Case
208 (`/case-00208.html`): the rider's three claims answered by GPS, her own
phone's trace and a connected call, the driver compensated SGD 6.40. Case 901
(`/case-00901.html`): the organisers' own sample. Source: the GitHub repository,
`<repository URL>`.

## 2. The pain point

A dispute reviewed by hand is slow, and its outcome depends on who reads it. The
team's understanding is that the same facts can be weighed two ways on two days,
that the reasoning is rarely written down, and that the parties see only the
outcome. That is the understanding this project is built on, not a claim about
Ryde's own figures.

## 3. The solution

**The flow.** A case comes in as public content and the loaded policy. Out comes
a ruling; an escalation to a human with the fee held; or, above `POL-GEN-05`'s
execution threshold (SGD 8.00, `docs/architecture.md`), a ruling whose amount is
held. A party may appeal once within 30 days under `POL-GEN-04`; a reviewer may
open an evidence window under `POL-GEN-06(4)`.

**The architecture.** `docs/architecture.svg`, written out in
`docs/architecture.md`: one brief, handed byte-identical to two advocates, one
for the rider and one for the driver, differing only in stance; a referee that
discards a claim citing no evidence id, no clause id, an unresolvable citation,
undisclosed impaired evidence, or a context-only profile field; a judge that
rules four times, the majority deciding; and a confidence floor of 0.70, below
which it goes to a human (README, What Tribunal is). At version 6 a scope gate
routes a safety- or complaint-flagged dispute to a human before any prompt is
rendered, and an optional record-integrity gate holds the record to
`POL-RD-10`'s limbs (README, After the sealed run).

**How the prompts drive it.** `prompts/v1/advocate.system.md` is one template
rendered twice from the two stance files, which the code asserts
(`tribunal/pipeline.py`). `prompts/v1/judge.system.md` tells the judge to test
the claims against the record and cap its confidence by the weights of the
deciding fact's artifacts. The policy is three JSON files; an unresolvable
clause id is not citable. The `DRAFT_*` codes reject a draft with an unresolved
clause, a money field that does not mirror, or an amount not read off the brief.

**Built on Tencent Cloud.** Built in WorkBuddy (a row per session in
`docs/buddy-log/README.md`); every model call goes to Tencent Cloud MaaS
(TokenHub, endpoint measured in
`docs/notes/2026-09-21-tokenhub-api-facts.md`) serving DeepSeek; the site is
hosted on Tencent EdgeOne Pages; support staff reach the records through the
read-only connector `integrations/workbuddy/`.

## 4. Quantifiable business value

Read by `python3 -m eval.business_value --report` over the four version-6 runs'
151 disputes (README, Business value): the median time to a decision is 160.4 s
and the 90th percentile 286.9 s; the median cost per case is 0.0579 USD; 112 of
151 = 74.2% are decided automatically and 39 of 151 = 25.8% go to a human. Every
human-lane case carries the 48-hour first-review commitment, operations rule
`OPS-EW-01`. The sealed sets are each reported as an **agreement** against their
own key, and are never pooled. The third sealed set, `sealed-v1` — made by a team
member with Claude, with a copy of the schema and the policy — has a four-field
agreement of 21/24 = 87.5%, Wilson 95% [69.0%, 95.7%], and is 20/24 under the key
as imported (README, sealed-v1 table; `python3 -m eval.sealed_report --set
sealed-v1`). The fourth sealed set, `sealed-v2` — made by the policy owner with
GPT-6 from the version-6 policy text and the public contract, with no repository
code, its answers seen by nobody on the development side — has a four-field
agreement of 12/12 = 100.0%, Wilson 95% [75.8%, 100.0%] (README, sealed-v2
table; `python3 -m eval.sealed_report --set sealed-v2`). The two figures are
never added together. On fairness over both version-6 runs the errors lean
towards the rider 0, towards the driver 1 and to an escalation 5, and the
position-swapped draft agrees with the sampled majority on all four graded
fields in 136 of 141 = 96.5% (README, fairness rows; `python3 -m
eval.fairness --report`). What is not measured: real Ryde data — every case
except the organisers' sample 901 is synthetic or semi-synthetic (README,
Limitations).
