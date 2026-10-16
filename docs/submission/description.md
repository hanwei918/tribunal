Digital Native Track - Multi-Agent Autonomous Dispute Resolution System (Ryde)

### 1. Project Overview: Target Scenarios, Users, and Value Proposition

Tribunal arbitrates one ride-hail dispute and writes down why. The scenario is
Ryde's two everyday cases: a route-deviation fare (`ROUTE_DEVIATION`), where the
rider says the driver took a longer way, and a no-show charge (`NO_SHOW_CHARGE`),
where the driver says the rider never turned up. Two of the brief's four:
property damage "requires image analysis" is a stretch goal; a safety incident
goes to a person. <!-- brief -->

Fare and surge disputes (v2.1 Section 3, the organisers' DISP-003) are out of
this prototype's scope by our choice; v2.1 itself lets the AI rule them, and
they are on the roadmap. <!-- v2.1; README -->

The users are Ryde's support team and the two parties. An agent works the queue;
a reviewer takes an escalation packet and opens an evidence window; both read
the records through the read-only WorkBuddy connector. A decision is written to
both sides: each ruling produces a notice text for both parties (shown on the
case page; the prototype sends nothing), naming the evidence and the clause it
rests on. Version 8 has no appeal clause yet; the version-6 operations layer
offers one appeal within 30 days, and bringing it to version 8 is on the roadmap.
<!-- README -->

The value is three sentences: a decision arrives in minutes, not days; it
carries the evidence and the clause it rests on, written to both parties; and a
case the panel cannot decide goes to a person with the money held. <!-- README -->

The live demo is https://tribunal.edgeone.dev/ - no account, no key. What it
shows now is version 8: the organisers' own two samples at
https://tribunal.edgeone.dev/cases.html#ryde, all 42 version-8 cases at
https://tribunal.edgeone.dev/v8-cases.html, and case 5051 at
https://tribunal.edgeone.dev/v8-05051.html, where the panel agrees on all four
graded fields 4 of 4 at a confidence of 0.95 and the driver is paid SGD 5.00. The
version-6 pages are history: case 208 at
https://tribunal.edgeone.dev/case-00208.html and the organisers' sample case 901
at https://tribunal.edgeone.dev/case-00901.html. The source is
https://github.com/hanwei918/tribunal. Every dispute on the site is synthetic
except the organisers' samples. <!-- README -->

### 2. Real World Scenario Insights: Source of Pain Points, Target Audience and Core Problem Solved

The pain points are Ryde's own, from the track's challenge statement: "High
operational costs - millions spent annually on human support hours"; "Slow
resolution times - typically 24-72 hours per dispute"; "Inconsistent rulings -
different agents reach different conclusions on similar cases"; "User churn -
customers who feel unfairly treated leave the platform". The sponsor's
statement, quoted as such, not a claim about Ryde's internal data.
<!-- challenge statement -->

The audience is those three groups: the agents and reviewers, and the rider and
the driver.

- **Slow.** At version 8 a decision takes a median of 153.1 s a case and 299.4 s
  at the 90th percentile from filing, over the 40 cases of `dev-v8` (development
  data); the 12 cases sent to a person are not automatic decisions. At version 6
  a decision took a median of 160.4 seconds and a p90 of 286.9 seconds over the
  151 version-6 disputes. <!-- eval.v8_report; eval.business_value -->
- **Inconsistent.** The judge rules four times, once with the positions swapped:
  at version 8 the swapped draft agreed with the panel on all four graded fields
  in 33 of 34 cases (`dev-v8`). <!-- eval.v8_report -->
- **Opaque.** Each ruling is a notice naming the evidence and the clause it
  rests on; the case page carries the six steps. <!-- README -->
- **Unfair outcomes stuck.** A case the panel cannot decide goes to a person with
  the money held. Version 8 has no appeal clause yet; the version-6 operations
  layer offers one appeal within 30 days under `POL-GEN-04`, and bringing it to
  version 8 is on the roadmap. <!-- README -->

### 3. Comprehensive Solution Design: business and technical architecture, and how prompts drive the AI generation

**The three agents, by the brief's names.** One brief, built from the public
case content and the loaded policy, is handed **byte-identical to two
advocates**, the **Rider Advocate Agent** and the **Driver Advocate Agent**,
differing only in stance; `tribunal/pipeline.py` asserts the rendered prompts
differ only inside the stance block. The **Judge Agent** rules four times and
the majority decides. The brief is built by **code from the case record** and
handed byte-identical to both advocates, not each advocate fetching its own, so
neither side can see evidence the other cannot; `ops/evidence.py` is a
**deterministic stand-alone tool**, not wired into the pipeline, that shows the
case record can be assembled from the source systems without a model, its output
equal to the case file's evidence array - a deliberate departure from the brief. <!-- README -->

**The guards.**

- **The authority gate** (`POL-GEN-21`, `POL-GEN-22`, `POL-RD-25`) - a safety
  flag, a value over SGD 50 or a route deviation over 2 km goes to a person after
  the lawyers have prepared the case file and before the judge is asked: 5
  stopped by a v2.1 rule before the judge of the 40 `dev-v8` cases (2 on the 2 km
  limit, 1 on the value, 2 on a safety flag). <!-- eval.v8_report -->
- **The confidence bar** (`POL-GEN-22`) - v2.1 asks 0.80, and 0.95 where a party
  carries a fraud flag; below the bar, or when the drafts split, no ruling is
  issued and the money is held. At version 6 the floor was 0.70 under `POL-RD-10`.
  <!-- README -->
- **Admissibility pre-check** - impaired evidence is carried at its weight, not
  trusted (107's GPS trace, weight 0.30); removing the pre-check scores 40/44
  (policy version 1, 2026-09-29; corpus and codex sets, whose corpus notes the
  ablation also removed). <!-- README -->
- **Citation referee** - discards an uncited, unresolvable or
  undisclosed-impairment claim, or one resting on a context-only profile field
  (104). <!-- README -->
- **Four drafts and the vote** - one sample cannot decide: at version 8, 6 the
  panel sent on and 1 without a majority of the 40 `dev-v8` cases. At version 6,
  107, 2749 and 2809 split and escalated. <!-- eval.v8_report -->
- **The draft checks** (`DRAFT_*`) - a draft not read off the brief, or naming a
  clause that does not resolve, is voided (1779; 517, 533). <!-- README -->

**What the brief asks for.** The MVP is complete: the three agents by name, two
categories, observable inter-agent communication (the case page's "How it was
decided" and the replay), a confidence score, a recommended action and amount,
an explanation to both parties. The stretch goals: Escalation Protocol (the core
pipeline); Fraud & Bad-Faith Detection, SLA & Routing, Evidence Collection
(deterministic services beside the pipeline); Policy & Precedent (built, off by
default, measured once, 15/15 against 13/15; the difference is not attributed
to the precedents - the store holds two, and neither changed ruling mentions
one - so it is reported, not claimed); Learning Feedback Loop (the
policy-gap loop, a person approves every clause); Image Analysis (not done, on
purpose). Two departures are deliberate: risk signals go to the human reviewer,
not the judge (`POL-GEN-01`), and the advocates do not gather their own
evidence. <!-- README -->

**How the prompts drive it.** `prompts/v2/advocate.system.md` is one template
rendered twice from the two stance files, which the code asserts. The judge
prompt (`prompts/v2/judge.system.md`) tests the claims against the record and
caps confidence by the deciding fact's weights. The policy is three JSON files;
an unresolvable clause id is not citable, and the `DRAFT_*` codes reject a draft
with an unresolved clause, a money field that does not mirror, or an amount not
read off the brief. <!-- prompts/v2 -->

**Built on Tencent Cloud.** Built in WorkBuddy (a row per session in
`docs/buddy-log/README.md`); every model call goes to Tencent Cloud MaaS
(TokenHub, endpoint measured in
`docs/notes/2026-09-21-tokenhub-api-facts.md`) serving DeepSeek; the site is
hosted on Tencent EdgeOne Pages; support staff reach the records through the
read-only connector `integrations/workbuddy/`. The code, the tests and these
documents were written in WorkBuddy session by session. <!-- buddy-log -->

**Responsible AI.** A person decides every case the panel cannot, and the money
is held; a human can switch automatic rulings off with `auto_rulings_enabled` in
the version-6 operations layer; and version 8 has no appeal clause yet, so the
one appeal within 30 days is the version-6 layer's too. Masking covers
registration marks, telephone numbers and e-mail addresses, not names. A planted
clause in the record of case 1779 was refused by all four drafts, and the code
check that voided those drafts sent the case to a person. On fairness, over the
version-6 runs the errors lean towards the rider 0, towards the driver 1, to an
escalation 5 and away from one 2 - the under-escalations 112 and 2858. The
limits: every case except the organisers' samples is synthetic; `POL-GEN-08(1)`
covers its two structured flags only, so a free-text allegation is not detected;
and a judge that quotes an invented clause id voids its own drafts, so a party
can force a case out of automation with a non-existent clause id. <!-- README -->

**Usability and accessibility.** Each case page opens with the outcome, the
money and who decided, and gives both parties the same notice in plain words
with the clause codes in brackets. The site has light and dark themes, its
tables sort and scroll from the keyboard, and every stated text contrast is at
least 4.5:1 and is recomputed by the test suite; an axe-core 4.8.2 scan of the
live queue and case pages 107 and 208, in both themes, found no violations on
2026-10-12. <!-- test_ui_v2; docs/notes/2026-10-12-accessibility-scan.md -->

### 4. Business Value: Quantifiable metrics or clearly defined impact

Read by `python3 -m eval.v8_report --report` over the 40 cases of `dev-v8`, which
is **development data** the team tuned against: a median of 153.1 s a case and
299.4 s at the 90th percentile from filing to a decision, 28 of 40 ruled by the
AI with no person needed, and a median model cost of 0.0390 USD a case. The
baseline is the brief's: a human review takes 24 to 72 hours, so minutes are that
work. **At version 6**, the team's own policy frozen on 2026-10-11,
`python3 -m eval.business_value --report` reads the 151 disputes of the four
version-6 runs: the median time to a decision of 160.4 seconds and the 90th percentile of 286.9
seconds, and the median cost per case is 0.0579 USD. Of the 151, 112 are decided
and executed (74.2%), 13 are decided with the amount held above `POL-GEN-05`'s SGD
8.00 threshold (8.6%), and 26 sent to a reviewer with no ruling (17.2%) - the
three figures the live site's tiles carry. The version-8 and version-6 figures
are never added together. <!-- eval.v8_report; eval.business_value -->

**The brief's four pain points, against what this system measured.** The brief
names them in its challenge statement; each row below is read from the file in
its last column, version 8 first and version 6 labelled.
<!-- challenge statement; eval.v8_report; eval.business_value; eval.fairness -->

| Pain point (the brief) | What the record shows | Read from |
|---|---|---|
| Cost | a median model cost of 0.0390 USD a case at version 8 (`dev-v8`, development data); 0.0579 USD a case at version 6 | `python3 -m eval.v8_report --report` |
| Speed | a median of 153.1 s a case and 299.4 s at the 90th percentile at version 8 (`dev-v8`); 160.4 s and 286.9 s at version 6 | `python3 -m eval.v8_report --report` |
| Inconsistency | at version 8 the swapped draft agreed with the panel on all four graded fields in 33 of 34 cases (`dev-v8`); at version 6 it agreed on all four graded fields in 136 of 141 cases | `python3 -m eval.v8_report --report` |
| User churn | both parties get the same notice in plain words; version 8 has no appeal clause yet, and the version-6 operations layer offers one appeal within 30 days | `docs/record.md` |

**The policy it applies, and the sealed sets.** The system applies **Ryde's own
Dispute Resolution Policy v2.1 with Ryde's answers of 2026-10-14** as policy
version 8. Its sealed figure is at version 7: `sealed-v4` - 30 cases written for
v2.1 by Claude Opus 5.5 in a fresh claude.ai chat with no project folder or
repository access, from Ryde's v2.1, the version-7 policy files, the public
contract, a format checker and the organisers' sample case; that model is also
the team's development assistant and helped write the version-7 policy files, and
no person reviewed its key - agrees on all four graded fields in
30/30 = 100.0%, Wilson 95% [88.6%, 100.0%], run once on 2026-10-14 from the tag
`freeze-2026-10-14`. A sealed set is run once, and version 8 changes its key on
one case (6009, 2.4 km), which version 8's 2 km gate escalates before the judge
is asked, while the other 29 were not run at version 8. 30 cases is a small
sample, and the figure says the system applies the version-7 files as that
author reads them rather than that it is independently correct. `ryde-v8`, the
organisers' own two samples converted for v2.1 and keyed by Ryde's stated
outcome as amended by Ryde's answer of 2026-10-14, is 1 of 2: 902 escalated by
version 8's 2 km gate, which is what Ryde answered, and 903 escalated on the
0.95 bar Tribunal reads v2.1 6.3 as setting on a no-show (C15), which Ryde's
sample does not share: two drafts escalated, one upheld the fee and one was
voided for citing a clause version 8 does not have; three must agree. **At
version 6**, the team's own policy frozen on 2026-10-11:
`sealed-v2` - 12 cases made by the policy owner with OpenAI Codex (model stated
by her as GPT-6; not recorded by the tool) from the version-6 policy text and the
public contract, no repository code, its answers seen by nobody on the
development side - agrees on all four graded fields in 12/12 = 100.0%, Wilson 95%
[75.8%, 100.0%]; 12 cases is a small sample. `sealed-v1` - 24 cases made by a
team member with Claude, with a copy of the schema and the policy - agrees in 21/24 = 87.5%, Wilson 95%
[69.0%, 95.7%], and is 20/24 under the key as imported,
because case 311's key changed to `PARTIAL_REFUND 7.05` under an amendment the
policy owner wrote after the system ruled that way on development case 1782. The
version-8 and version-6 figures are never added together; the development figures
are separate: `dev-v8` 39/40 and `dev-v7` 40/40 (development data), the corpus
26/29 at version 6
and `dev-v2-ext` 115/120. <!-- eval.sealed_report; eval.development_sets -->

**Beyond the hackathon.** Ryde's own format is converted by
`eval/external/ryde/convert.py`, proven on `DISP-002`. A production feed needs
either GPS fixes of about 10 to 30 seconds with a horizontal accuracy (Ryde's
sample carries 2 to 4 minute fixes and none) or the platform's own arrival and
wait-timer events, which is how 901 was decided. A rollout would start in shadow
mode with `auto_rulings_enabled` false, then switch on `POL-GEN-05`'s SGD 8.00
threshold. Throughput is bounded by the provider's measured limits of 1,000,000
tokens and 60 requests a minute per model; a case is billed a median of 226,125
tokens, 58,364 of them cached prompt (`python3 -m eval.v6_runs --report`), so
the token limit binds first: the arithmetic ceiling is about 4.4 cases a minute
per model if cached tokens count against the limit and about 6 if they do not,
while the request limit - ten cases a minute, at six model calls a case - does
not bind. The endpoint note does not record which way cached tokens count, so
that is not known. Computed, not measured.
<!-- tokenhub-api-facts -->

What is not measured: real Ryde data. Every case except the organisers' samples
901, 902 and 903 is synthetic or semi-synthetic. <!-- README -->
