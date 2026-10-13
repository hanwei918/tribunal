# Why a debate, and what it buys

Tribunal settles a dispute by argument rather than by one model's opinion. Five
mechanisms do the work, and each of them is in the code beside this file.

## Two advocates, one brief

[`tribunal/brief.py`](../tribunal/brief.py) builds the evidence package **once**
and canonicalises it once. The same bytes go to both advocates and to the judge,
and the brief's sha256 is recorded on the result, so a reader can confirm which
brief a ruling was made from. `prompts/v1/advocate.system.md` is one template
rendered twice, from `prompts/v1/stance.rider.md` and
`prompts/v1/stance.driver.md`, substituted at the `{{STANCE}}` placeholder.
[`tribunal/pipeline.py`](../tribunal/pipeline.py) asserts that the two rendered
prompts differ **only** inside the stance block.

That assertion is the project's central claim: the two advocates read
byte-identical evidence and differ only in whose side they are on, and the code
checks it before any call is made.

## The citation referee

[`tribunal/referee.py`](../tribunal/referee.py) is a deterministic referee that
runs before the judge and is deliberately narrower than it. It discards a claim
for citing no evidence id,
for citing no clause id, for citing something that does not resolve, for resting
on impaired evidence without disclosing the impairment, and for treating a
context-only profile field as a ground. It never decides the merits.

An uncited claim therefore does not reach the judge at all. The referee removes
what cannot be checked; it does not pick a winner.

## Four drafts, one of them swapped

`prompts/v1/judge.system.md` is asked four times on the same inputs: three
sampled, and one with the parties' positions swapped. The majority decides. The
drafts are reduced over all four graded fields together, because a panel that
agreed on the label while disagreeing on the money has not agreed on anything.

The swap is the check that a panel is not merely reading the side the filing
happens to favour. Of the 141 cases whose swapped draft and at least one sampled
draft are valid, the swapped draft agrees with the sampled majority on all four
graded fields in 136 and on the ruling alone in 139
([the full record](record.md), "Fairness and calibration";
`python3 -m eval.fairness --report`).

## Frozen evaluation

Each sealed set was run **once**, by the owner, from its own freeze tag, and the
output is committed as produced: `wild-v2` from `freeze-2026-10-03`, `sealed-v1`
from `freeze-2026-10-09` and `sealed-v2` from `freeze-2026-10-11`. Each is
reported as the **agreement** against its own key, and the three are never
pooled or summed ([the full record](record.md), "Results").

A set that has been run is never re-run, so no figure here is the best of
several attempts.

## The tamper-evident event log

Every run writes `events.jsonl`: one JSON object per line, one line per event,
appended and never rewritten. Each line carries `prev`, the SHA-256 of the
previous line's canonical body, and `hash`, the SHA-256 of its own, so a line
that is deleted, inserted or reordered breaks the chain at the first line that
no longer agrees with its predecessor.

As [`tribunal/events.py`](../tribunal/events.py) says in its own words, **the
chain is not a signature**.
It cannot prove the file was never rewritten by someone who rewrote all of it;
it can only prove that the file a reader holds is the file the run wrote, which
is the question worth being able to answer.

## The reference this design comes from

Khan, Hughes, Valentine, Ruis, Sachan, Radhakrishnan, Grefenstette, Bowman,
Rocktäschel and Perez, "Debating with More Persuasive LLMs Leads to More
Truthful Answers", arXiv:2402.06782 (v4, 25 Jul 2024).

In their setting the task is reading comprehension, the judge **cannot** see the
passage and the debaters can, and debate raised non-expert model judges to 76%
and human judges to 88%, against naive baselines of 48% and 60% (the abstract).

Tribunal's setting differs, and the difference is the point: **its judge does
see the evidence** — the same brief the two advocates argue from — so the paper
motivates the design rather than measuring it. No figure in this repository is
the paper's.
