# Tribunal — submission description

## 1. Overview

Tribunal arbitrates one ride-hail dispute and writes down why. The scenario is
Ryde's two everyday cases: a route-deviation fare, where the rider says the
driver took a longer way, and a no-show fee, where the driver says the rider
never turned up. The users are a support team and the two parties: the team
works a queue, each party may appeal once. The value is a
first decision in the minutes a case takes to run, carrying its evidence and its
clause, and handed to a person with the money held when it cannot decide.

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
held. After it a party may appeal once within 30 days under `POL-GEN-04`, and a
reviewer may open an evidence window to both parties under `POL-GEN-06(4)`. The
48-hour first-review commitment is operations rule `OPS-EW-01`, not a clause of
the frozen policy (README, Business value). Support staff can also ask WorkBuddy
about a case through a read-only connector, `integrations/workbuddy/`, which
answers from the committed records.

**The architecture.** `docs/architecture.svg`, written out in
`docs/architecture.md`: one brief, handed byte-identical to two advocates
differing only in stance; a referee that discards a claim citing no evidence id,
no clause id, an unresolvable citation, undisclosed impaired evidence, or a
context-only profile field as a ground; a judge that rules four times, the
majority deciding; and a confidence floor of 0.70, below which it goes to a
human (README, What Tribunal is). At version 6 a scope gate routes a safety-
or complaint-flagged dispute to a human before any prompt is rendered, and an
optional record-integrity gate holds the record to `POL-RD-10`'s limbs (README,
After the sealed run).

**How the prompts drive it.** `prompts/v1/advocate.system.md` is one template,
rendered twice by substituting `prompts/v1/stance.rider.md` and
`prompts/v1/stance.driver.md` at a single placeholder, the code asserting the
two rendered prompts differ only inside that block (`tribunal/pipeline.py`).
`prompts/v1/judge.system.md` tells the judge to test the claims against the
record and cap its confidence by the weights of the artifacts the deciding fact
rests on. The policy the agents must cite is three JSON files whose clauses carry
`id`, `title`, `category`, `rule`, `requires`, `licenses`, `favours` and
`notes`; a clause id that does not resolve is not citable. The code checks that
reject a draft — the `DRAFT_*` codes in `tribunal/pipeline.py` — include an
unresolved clause, a money field that does not mirror, and an amount not read
off the brief.

## 4. Quantifiable business value

Read by `python3 -m eval.business_value --report` over the four version-6 runs'
151 disputes (README, Business value): the median time to a decision is 160.4 s
and the 90th percentile 286.9 s; the median cost per case is 0.0579 USD; 112 of
151 = 74.2% are decided automatically and 39 of 151 = 25.8% go to a human. Every
human-lane case carries the 48-hour first-review commitment, operations rule
`OPS-EW-01`. The third sealed set, `sealed-v1`, has a four-field **agreement**
against its key of 21/24 = 87.5%, Wilson 95% [69.0%, 95.7%] (README,
sealed-v1 table; `python3 -m eval.sealed_report --set sealed-v1`) — one
sealed set, never pooled. On fairness over both version-6 runs the errors lean
towards the rider 0, towards the driver 1 and to an escalation 5, and the
position-swapped draft agrees with the sampled majority on all four graded
fields in 136 of 141 = 96.5% (README, fairness rows; `python3 -m
eval.fairness --report`). What is not measured: real Ryde data — every case
except the organisers' sample 901 is synthetic or semi-synthetic (README,
Limitations).
