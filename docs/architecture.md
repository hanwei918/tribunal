# Tribunal architecture

The four views are drawn by `tools/c4_diagrams.py`, written in WorkBuddy, from
the layout specifications in `docs/architecture/spec/` -- one JSON file per
view, each a transcription of a drawing and nothing else. Those specifications
transcribe the C4 set the policy owner, **Ji Guofang**, designed, redrawn for
the policy the submission applies: **version 8**, Ryde's own Dispute Resolution
Policy v2.1 with Ryde's answers of 2026-10-14. The `tribunal/`, `prompts/` and
`policy/` trees the views are drawn from are the annotated tag
`freeze-2026-10-14-v8` (commit `af2b5ca`), and the views are read in the order
this page walks them. One correction was made, and it is the only difference
between her drawings and these: the evidence collector's box says what
`ops/evidence.py` does -- it is given the dispute and reads that dispute's trip
id -- where the drawing said it was given only a trip id. The **system context**
says who uses Tribunal and what it depends on. The two **container** views open
the system itself: 2a for deciding and measuring, 2b for what happens after a
ruling. The **dynamic** view follows one dispute down the pipeline, step by
step. Every element names the file that implements it, and every arrow is
directed and labelled with what it carries.

![Tribunal architecture](architecture.svg)

The diagram above is the **dynamic** view: `docs/architecture.svg` is a
byte-for-byte copy of `docs/architecture/3-dynamic-one-dispute.svg`, and it is
the view the README embeds. The other three sit beside it under
`docs/architecture/`, and all four are linked from the queue's own links row on
the support site.

**How to read them.** A blue box is deterministic code, a purple badge is a call
to a language model, orange is a person, grey is data or a record or an external
system, and a **dashed** line or box is something optional that is off by
default. Each drawing's own legend names its swatches, and the colours are the
C4-PlantUML defaults. Nothing in the set is a link, a script or an embedded
image: each file stands alone.

**Where a part is still version 6.** The views draw version 8, and three parts
of the system are deliberately still version 6: the **operations layer** -- the
queue, the escalation packet, the review, the appeal and the risk signals under
`ops/`, which read the version-6 runs; the **try-it page**, a phone demo that
replays recorded version-8 runs; and the **151 version-6 case pages**, which are
history: each is written in English and Chinese in the site's own design
(`case-<NNNNN>.html` and `case-<NNNNN>.zh.html`, 302 files), and each links to
the reviewer's page (`review-<NNNNN>.html`) with every step of the decision, the
escalation packet and the review form. The README says so in its own words,
one line each, in [Roadmap and known limits](../README.md#roadmap-and-known-limits).

## 1. System context: who uses it, and what it needs

**Rider or driver.** A person files a dispute about a Ryde trip. The app itself
is drawn outside the repository on purpose -- what crosses into the system is
the case record and nothing else.

**Operator.** The developer, **Zhou Hanwei**, who runs every set from the
command line: there is no always-on service. `eval/run_benchmark.py` and
`eval/development_sets.py` are the commands, and the operator is also the
person who approved amendment `0003` and made both stored closures, adopted
Ryde's v2.1 as version 7 on 2026-10-13, asked Ryde the team's three questions,
and adopted Ryde's answers as version 8 on 2026-10-14.

**Policy owner.** The person who owned version 6's policy and wrote most of its
answer keys. She wrote the dev-v2 and sealed-v2 keys and re-derived sealed-v1,
approved amendments `0001` and `0002`, and confirmed `0003`; the note that
records the confirmation is
`docs/notes/2026-10-10-ns-12-confirmed-by-policy-owner.md`. The policy in force
at version 8 is Ryde's, not hers: what version 7 and version 8 change is in
[the version-7 note](notes/2026-10-13-policy-v7.md) and
[the version-8 note](notes/2026-10-14-policy-v8.md).

**Ryde platform.** The external system the dispute comes from: trips, GPS, chat,
fares and profiles. Here it is **mocked**, and what stands in for its export is
the committed case files under `data/`, whose shape `data/PUBLIC-CONTRACT.md`
fixes at contract version 1.2.0.

**Tribunal.** The system itself: Python 3.9 to 3.13, standard library only. It
decides one ride dispute against a versioned policy -- at version 8, Ryde's
v2.1 with Ryde's answers of 2026-10-14 -- two advocates argue from one brief, a
four-draft judge panel votes, and deterministic checks gate every draft -- and a
case it may not decide, whether by a code check or by v2.1's own authority gate,
is escalated to a person. Every step is written to a hash-chained record.

**Tencent Cloud TokenHub.** The model provider: its API in Singapore, serving
`deepseek/deepseek-flash`. The request is JSON over HTTPS, and `tribunal/llm.py`
is what sends it.

**Tencent EdgeOne Pages.** Static hosting for the support site and the replay
beside it, at the address the README publishes. Nothing in the repository
deploys to it: the pages are uploaded by hand.

**WorkBuddy.** The AI work assistant the connector runs under. It starts the
server under `integrations/workbuddy/` from its own `mcp.json` and asks it about
a case, the queue or a packet.

**Support reviewer.** The person who decides every escalated case, clears held
money and checks appeals, through the commands under `ops/`.

## 2a. Containers: deciding and measuring

**Operator.** The developer again, on this view: runs a set and grades it, from
`eval/run_benchmark.py`, or from `eval/development_sets.py` for a named set.

**Tencent Cloud TokenHub.** The model API, reached once per advocate and once
per judge draft: two, six or seven calls a case, and at version 8 that is six
calls a case for 34 of the 42 cases, seven for 2 and two for 6.

**Ryde platform.** The committed case files again, supplying the record the run
is made from.

**Policy owner.** Writes clauses and answer keys by hand, and approves an
amendment, through `eval/policy_gaps.py approve` or by editing `policy/`.

**EdgeOne Pages.** Where the pages are uploaded by hand: the product site
`ui/site/build.py` builds, the 42 version-8 case pages `ui/v8/build.py` builds,
the version-6 queue and case pages `ui/v2/build.py` builds, and the replay
`ui/build.py` builds.

**Evaluation and grading.** `eval/run_benchmark.py` runs a set and writes its
records; `eval/development_sets.py` does the same for a named set; and
`eval/grade.py` scores a run -- the ruling and both amounts exactly, and the
referral clauses by recall.

**Answer keys.** The expected rulings per set, under `eval/answers/`, the sealed
sets among them. The version-6 keys are mostly the policy owner's; `dev-v7`,
`dev-v8` and `sealed-v4` were written by Claude Opus 5.5, in a fresh claude.ai
chat with no project folder or repository access; `ryde-v7` and `ryde-v8` are
Ryde's two samples. Nothing under `tribunal/` may read them.

**Evaluation replay build.** `ui/build.py` writes the static replay under
`/replay/`: the version-1 corpus run, codex, wild, wild-v2 and case 901, each
agent's words beside the answer key.

**Arbitration pipeline.** `tribunal/` decides one case: one brief, two
advocates, v2.1's authority gate, a citation referee, four judge drafts, the ten
`DRAFT_*` checks and a 3-of-4 vote against the bar v2.1 states -- `POL-GEN-22`
and `POL-RD-25`, not a single floor. It returns a ruling or `ESCALATE` to its
caller, and it makes two, six or seven model calls a case: at version 8, six for
34 of the 42 cases, seven for 2 and two for 6. The switches the container names
are the command line's, and every one is off by default: `--policy-version N`
(default 1, and the product runs use 8), `--parallel-calls`, `--verify-drafts`,
`--precedents`, `--early-majority`, `--advocate-effort`, `--amount-rule`,
`--ablate` and `--judge-votes`. `--prompts-dir prompts/v2` is the one a
version-8 run needs, and the default it replaces is `prompts/v1`.
`--integrity-gate` is not among them: it is the version-6 record-integrity gate,
and version 8's policy carries no `POL-RD-10` for it to read.

**Case store.** `data/`: the 29-case corpus and its `index.json`, 7 or 8
artifacts each, plus the sets under `data/external/`. No answers.

**Policy store.** `policy/`: versions 1 to 8, in three separate bases.
Versions 1 to 6 are the team's own policy, version 6 being the `v3` base plus
the three amendments under `policy/v3/amendments/`, 34 clauses in all. Version 7
is Ryde's v2.1 under `policy/v7/`, and version 8 -- the one the product runs
read -- is `policy/v8/`, v2.1 with the fifteen JSON paths Ryde's answers of
2026-10-14 move. Versions 1 to 6 stay byte-identical, which is what lets the
recorded version-6 case digests rebuild unchanged.

**Prompt templates.** `prompts/v2/`: the version-8 set -- the advocate, the two
stances, the judge, the verifier and the policy drafter. `prompts/v1/` is the
version-6 set, unchanged, and a version-8 run that is handed it is refused.

**Precedent store.** `precedents/precedents.jsonl`: closures a person made,
append-only and hash-chained. It is written on sheet 2b.

**Evidence collector.** `ops/evidence.py`: a **standalone CLI, not wired into
the pipeline**. Given a case, it reads that dispute's `trip_id` and nothing else
from the dispute, collects through the mock adapters in `ops/sources.py`, and
then checks the result against the case's own artifact list.

**Run records.** `runs/`: per case a `case-*.json` carrying the brief's sha256,
the prompts' sha256, the git commit and `matched`, the grade against the key,
and a transcript of every call; per run an `events.jsonl` hash chain,
`run.json`, `calls.json` and `report.md`.

## 2b. Containers: after a ruling

**Policy owner.** Owned version 6's policy, approved amendments `0001` and
`0002`, and confirmed `0003`.

**Policy store.** `policy/`: version 6 is the `v3` base plus `0001` to `0003`,
placed by hand, with no policy-gap report behind any of them; `0003` was
approved by Zhou Hanwei and then confirmed by the policy owner. Version 8, which
the runs read, is `policy/v8/` -- see 2a.

**Policy-gap tool.** `eval/policy_gaps.py`: `report` groups the cases the policy
could not decide and makes no model call; `draft` asks a model for one clause
for a flagged cluster; `approve` and `reject` are a named person's alone;
`rerun` runs the affected cases at the new version, and `diff` compares before
and after, making no model call either. The drafter's prompt is
`prompts/v2/policy_drafter.system.md`.

**Precedent store.** `precedents/precedents.jsonl`: `P-0001` and `P-0002` were
appended by `tribunal/precedents.py close`, and `ops/review.py` is the wrapper a
reviewer closes a case through.

**Prompt templates.** `prompts/v2/policy_drafter.system.md` is the draft step's
prompt.

**Run records.** Every case's ruling or `ESCALATE`, its brief digest, its
transcript and its grade, read by the queue.

**Operations CLI.** `ops/`, which makes no model call anywhere -- and which is
still the **version-6** layer, reading the version-6 runs: `ops/queue.py` sorts
the disputes into the safety, human-review and auto lanes;
`ops/chat_signals.py` reads a chat log for a threat ahead of every other lane;
`ops/risk.py` orders review; the kill switch `auto_rulings_enabled` is in
`ops/config.json`; an amount above SGD 8.00 is listed for release; and the
end-to-end target is 48 hours. `ops/escalation.py` builds the packet, and
`ops/review.py` closes a case only against that packet's sha256;
`ops/evidence_window.py` is the 36-hour window that never pauses for a missing
piece of evidence; and `ops/appeal.py` checks an appeal against the clause's six
named checks. Every threshold the layer uses is read from the policy or from
`ops/config.json` rather than typed. Version 8's own appeal clause does not
exist yet: this layer is on the roadmap.

**Site builders.** Four of them write the static HTML a reviewer reads.
`ui/site/build.py` writes the product site, every page in English and Chinese.
`ui/v8/build.py` writes the 42 version-8 cases, two languages each, and their
index, `ui/dist/v8-cases.html`: these are what a reviewer reads for a version-8
run, 86 files in all, built from the committed version-8 runs. `ui/v6/build.py`
writes the 151 version-6 case pages, each in English and Chinese in the site's
own design (`case-<NNNNN>.html` and `case-<NNNNN>.zh.html`, 302 files), each
linking to the reviewer's page with every step of the decision, the escalation
packet and the review form. `ui/v2/build.py` writes the version-6 queue, that
reviewer's page (`review-<NNNNN>.html`) and the review form, drawn from the
version-6 runs. Between them they read `data/`, `policy/` and the
committed runs.

**WorkBuddy connector.** `integrations/workbuddy/`: a read-only MCP server whose
tools are `tribunal_case`, `tribunal_queue` and `tribunal_packet`. It refuses
the sealed sets, and it reads the policy through the product view's own readers.

**Case store.** `data/`: the public cases the packets and the connector are
rebuilt from.

**Support reviewer.** Decides escalated cases, clears held money -- no command
in the repository records a release -- and checks appeals, through `ops/`.

**WorkBuddy.** Starts the connector from its own `mcp.json` and calls its tools.

**EdgeOne Pages.** Hosts the pages the reviewer reads.

## 3. Dynamic: one dispute, step by step

The dynamic view draws one call of `run_case()` at `--policy-version 8`, and its
eleven boxes are numbered in the order the pipeline runs them:

1. **Load the case.** `tribunal/loader.py` loads one case and refuses a
   malformed record or a manifest mismatch.
2. **Weigh the evidence.** `tribunal/prepass.py`, called by `tribunal/brief.py`:
   an artifact's issue codes become weights, read from the policy's integrity
   table.
3. **Derive facts and money.** `tribunal/facts.py` and `tribunal/money.py`,
   called by `tribunal/brief.py`: the geometry, the dwell and the fare
   arithmetic, with no model anywhere in it.
4. **Build one brief.** `tribunal/brief.py`: one object, one sha256, a refusal
   of any answer-key field, and the masking of registration plates, Singapore
   telephone numbers and e-mail addresses in the free text. Names are
   deliberately not masked.
5. **Two advocates.** `prompts/v2/advocate.system.md` with
   `prompts/v2/stance.rider.md` and `prompts/v2/stance.driver.md`: the same
   brief bytes on both sides, only the stance differing, and two model calls. An
   answer that is unusable after one retry fails the case with no ruling.
6. **Authority gate.** `tribunal/pipeline.py`: v2.1's own gate, and it fires
   **after** the advocates and **before** the judge, so the case file is
   prepared and no ruling is issued. Three limbs, in the order of the clauses: a
   safety or complaint flag is a person's whatever the value (`POL-GEN-21`); a
   contested value above SGD 50 is a person's whatever the category
   (`POL-GEN-22`); and a route deviation over 2 km is outside what an AI ruling
   may carry (`POL-RD-25`). The judge is not asked at all, so a stopped case has
   had two calls and no more.
7. **Citation referee.** `tribunal/referee.py`, deterministic and deciding no
   merits: it discards a claim whose evidence or clause id is missing or
   unresolved, a claim that cites an impaired artifact without naming its issue
   code, and a claim grounded on a profile field.
8. **Judge panel.** `prompts/v2/judge.system.md`: four drafts, three sampled and
   one position-swapped, four model calls. Optional `--verify-drafts` adds one
   more call.
9. **Draft checks.** `tribunal/pipeline.py`: the ten `DRAFT_*` checks a draft
   must pass, one of them `DRAFT_BELOW_FLOOR`. A draft that fails one abstains
   rather than being counted.
10. **Vote and the bar.** `tribunal/pipeline.py`: 3 of 4 must agree. No valid
    draft, no majority, or a confidence below the bar v2.1 asks -- 0.80 from
    10.00 to 50.00 SGD, 0.95 where a party carries a fraud flag, 0.80 for a
    route deviation, and none below the first band -- is `ESCALATE`. The bar is
    read off the brief's authority block rather than typed here.
11. **Publish and record.** `tribunal/pipeline.py`, `tribunal/transcript.py` and
    `tribunal/events.py`: the ruling, or `ESCALATE` with its reason, goes back
    to `eval/run_benchmark.py`, which writes the case file and the transcript.

**Evaluation and grading.** `eval/run_benchmark.py` calls the pipeline once per
case and writes what comes back. **Case store.** `data/cases/` and
`data/index.json`, read once. **Policy store.** Version 8: the integrity table,
v2.1's clauses and the bar the brief carries.

**Tencent Cloud TokenHub.** The model API the two advocate calls and the four
draft calls are made to. **Precedent store.** `precedents/precedents.jsonl`: up
to three closures, with no amounts in them, shown to the judge only and only
with `--precedents`. **Run records.** `runs/`, which the queue reads.

**The rule the dynamic view states about calls.** Six model calls a case, seven
with `--verify-drafts` or when an unusable answer is retried, and **two** for a
case the authority gate stops, because the gate sits after the advocates. At
version 8 that is 34, 2 and 6 of the 42 cases; an HTTP 429 or 5xx response is
attempted up to four times.

## What the arrows carry

Every arrow is labelled with what it carries, so the labels are the contract
between the boxes. On the **system context** they are `files a dispute`,
`supplies the case record`, `runs a case set and grades it`, `writes clauses and
answer keys; approves amendments`, `asks the advocates and the judge`, `static
pages uploaded to`, `asks about a case`, `reads cases, the queue, packets`,
`works the queue, closes escalated cases, checks appeals`, `reads case pages`,
and one dashed arrow that is deliberately **not** built: `notice of the ruling:
generated, not sent`. On **2a** they are `runs a set, grades it`, `writes keys`,
`compares with`, `runs each case`, `writes the records, grades`, `reads`,
`pages uploaded to`, `2, 6 or 7 calls a case`, `loads one case`,
`reads version N`, `reads prompts`, `up to 3 closures`, `records events into the
run's log`, `reads via adapters, checks` and `supplies case records`. On **2b**
they are `approves or rejects a proposal`, `writes clauses, places amendments`,
`drafts a clause; rerun`, `writes an approved amendment`, `reads human
closures`, `reads the drafter prompt`, `reads runs; rerun writes new ones`,
`appends a closure (review.py)`, `reads rulings`, `rebuilds the packet from`,
`works the queue`, `reads`, `pages uploaded to`, `reads`, `runs ops.queue,
ops.escalation`, `reads the public case`, `asks about a case`, `calls the
tools` and `reads case pages`.
On the **dynamic** view they are `run_case(N)`, `reads`, `case`, `weights`,
`facts`, `brief`, `integrity table (no_show.json)`, `reads version 8`, `both
advocates ran: the brief, to the gate`, `stopped: ESCALATE after the advocates`,
`claims`, `kept claims`, `drafts`, `valid drafts`, `ruling or ESCALATE`, `events
into the run's log; eval writes case-*.json and the transcript`, `2 calls`,
`4 calls` and `shown to the judge`.
