# Tribunal architecture

The drawings are the policy owner's. **Ji Guofang** drew this set of four views
from the code at the final freeze, `freeze-2026-10-11`, which is policy version
6, and they are read in the order this page walks them. The **system context**
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

## 1. System context: who uses it, and what it needs

**Rider or driver.** A person files a dispute about a Ryde trip. The app itself
is drawn outside the repository on purpose -- what crosses into the system is
the case record and nothing else.

**Operator.** The developer, who runs every set from the command line: there is
no always-on service. `eval/run_benchmark.py` and `eval/development_sets.py` are
the commands, and the operator is also the person who approved amendment `0003`
and made both stored closures.

**Policy owner.** The person who owns the policy and most of the answer keys.
She wrote the dev-v2 and sealed-v2 keys and re-derived sealed-v1, approved
amendments `0001` and `0002`, and confirmed `0003`; the note that records the
confirmation is
`docs/notes/2026-10-10-ns-12-confirmed-by-policy-owner.md`.

**Ryde platform.** The external system the dispute comes from: trips, GPS, chat,
fares and profiles. Here it is **mocked**, and what stands in for its export is
the committed case files under `data/`, whose shape `data/PUBLIC-CONTRACT.md`
fixes at contract version 1.2.0.

**Tribunal.** The system itself: Python 3.9 to 3.13, standard library only. It
decides one ride dispute against a versioned policy -- two advocates argue from
one brief, a four-draft judge panel votes, and deterministic checks gate every
draft -- and a case it may not decide is escalated to a person. Every step is
written to a hash-chained record.

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
per judge draft: six calls a case at version 6.

**Ryde platform.** The committed case files again, supplying the record the run
is made from.

**Policy owner.** Writes clauses and answer keys by hand, and approves an
amendment, through `eval/policy_gaps.py approve` or by editing `policy/`.

**EdgeOne Pages.** Where the replay's pages are uploaded.

**Evaluation and grading.** `eval/run_benchmark.py` runs a set and writes its
records; `eval/development_sets.py` does the same for a named set; and
`eval/grade.py` scores a run -- the ruling and both amounts exactly, and the
referral clauses by recall.

**Answer keys.** The expected rulings per set, under `eval/answers/`, the sealed
sets among them. Nothing under `tribunal/` may read them.

**Evaluation replay build.** `ui/build.py` writes the static replay under
`/replay/`: the version-1 corpus run, codex, wild, wild-v2 and case 901, each
agent's words beside the answer key.

**Arbitration pipeline.** `tribunal/` decides one case: one brief, two
advocates, a citation referee, four judge drafts, the ten `DRAFT_*` checks and a
3-of-4 vote against the 0.70 floor. It returns a ruling or `ESCALATE` to its
caller, and it makes six model calls a case. The switches the container names are
the command line's, and every one is off by default: `--policy-version N`
(default 1, and the product runs use 6), `--parallel-calls`, `--integrity-gate`,
`--verify-drafts`, `--precedents`, `--early-majority`, `--advocate-effort`,
`--amount-rule`, `--ablate` and `--judge-votes`.

**Case store.** `data/`: the 29-case corpus and its `index.json`, 7 or 8
artifacts each, plus the sets under `data/external/`. No answers.

**Policy store.** `policy/`: versions 1 to 6. Version 6 is `policy/v3/` plus the
three amendments under `policy/v3/amendments/`, 34 clauses in all.

**Prompt templates.** `prompts/v1/`: the advocate, the two stances, the judge,
the verifier and the policy drafter.

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

**Policy owner.** Owns the policy, approved amendments `0001` and `0002`, and
confirmed `0003`.

**Policy store.** `policy/`: version 6 is `policy/v3/` plus `0001` to `0003`,
placed by hand, with no policy-gap report behind any of them; `0003` was
approved by Zhou Hanwei and then confirmed by the policy owner.

**Policy-gap tool.** `eval/policy_gaps.py`: `report` groups the cases the policy
could not decide and makes no model call; `draft` asks a model for one clause
for a flagged cluster; `approve` and `reject` are a named person's alone;
`rerun` runs the affected cases at the new version, and `diff` compares before
and after, making no model call either. The drafter's prompt is
`prompts/v1/policy_drafter.system.md`.

**Precedent store.** `precedents/precedents.jsonl`: `P-0001` and `P-0002` were
appended by `tribunal/precedents.py close`, and `ops/review.py` is the wrapper a
reviewer closes a case through.

**Prompt templates.** `prompts/v1/policy_drafter.system.md` is the draft step's
prompt.

**Run records.** Every case's ruling or `ESCALATE`, its brief digest, its
transcript and its grade, read by the queue.

**Operations CLI.** `ops/`, which makes no model call anywhere: `ops/queue.py`
sorts the disputes into the safety, human-review and auto lanes;
`ops/chat_signals.py` reads a chat log for a threat ahead of every other lane;
`ops/risk.py` orders review; the kill switch `auto_rulings_enabled` is in
`ops/config.json`; an amount above SGD 8.00 is listed for release; and the
end-to-end target is 48 hours. `ops/escalation.py` builds the packet, and
`ops/review.py` closes a case only against that packet's sha256;
`ops/evidence_window.py` is the 36-hour window that never pauses for a missing
piece of evidence; and `ops/appeal.py` checks an appeal against the clause's six
named checks. Every threshold the layer uses is read from the policy or from
`ops/config.json` rather than typed.

**Support site build.** `ui/v2/build.py`: the case pages, the queue and the
review form, drawn from the version-6 runs. It also reads `data/` and `policy/`.

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

**Evaluation and grading.** `eval/run_benchmark.py` calls the pipeline once per
case and writes what comes back. **Case store.** `data/cases/` and
`data/index.json`, read once. **Policy store.** Version 6: the integrity table,
34 clauses and the confidence floor of 0.70.

**1. Load the case.** `tribunal/loader.py` loads one case and refuses a
malformed record or a manifest mismatch.

**2. Weigh the evidence.** `tribunal/prepass.py`, called by `tribunal/brief.py`:
an artifact's issue codes become weights, read from the policy's integrity
table.

**3. Derive facts and money.** `tribunal/facts.py` and `tribunal/money.py`,
called by `tribunal/brief.py`: the geometry, the dwell and the fare arithmetic,
with no model anywhere in it.

**4. Build one brief.** `tribunal/brief.py`: one object, one sha256, a refusal
of any answer-key field, and version 6's masking of registration plates,
Singapore telephone numbers and e-mail addresses in the free text. Names are
deliberately not masked.

**5. Scope gate.** `tribunal/pipeline.py`: `POL-GEN-08(1)` from version 3 on, so
a safety or complaint flag stops here and no model is called. Beside it,
optional, is `--integrity-gate`: `POL-RD-10`'s limbs (2) and (4), route
deviation only.

**6. Two advocates.** `prompts/v1/advocate.system.md` with
`prompts/v1/stance.rider.md` and `prompts/v1/stance.driver.md`: the same brief
bytes on both sides, only the stance differing, and two model calls. An answer
that is unusable after one retry fails the case with no ruling.

**7. Citation referee.** `tribunal/referee.py`, deterministic and deciding no
merits: it discards a claim whose evidence or clause id is missing or
unresolved, a claim that cites an impaired artifact without naming its issue
code, and a claim grounded on a profile field.

**8. Judge panel.** `prompts/v1/judge.system.md`: four drafts, three sampled and
one position-swapped, four model calls. Optional `--verify-drafts` adds one more
call.

**9. Draft checks.** `tribunal/pipeline.py`: the ten `DRAFT_*` checks a draft
must pass, one of them `DRAFT_BELOW_FLOOR`. A draft that fails one abstains
rather than being counted.

**10. Vote and floor.** `tribunal/pipeline.py`: 3 of 4 must agree. No valid
draft, no majority, or a confidence below 0.70 is `ESCALATE`.

**11. Publish and record.** `tribunal/pipeline.py`, `tribunal/transcript.py` and
`tribunal/events.py`: the ruling, or `ESCALATE` with its reason, goes back to
`eval/run_benchmark.py`, which writes the case file and the transcript.

**Tencent Cloud TokenHub.** The model API the two advocate calls and the four
draft calls are made to. **Precedent store.** `precedents/precedents.jsonl`: up
to three closures, with no amounts in them, shown to the judge only and only
with `--precedents`. **Run records.** `runs/`, which the queue reads.

**The rule the dynamic view states about calls.** Six model calls a case, seven
with `--verify-drafts`, and none at all for a case the scope gate stops; an
unusable answer is retried once, and an HTTP 429 or 5xx response is attempted up
to four times.

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
`pages uploaded to`, `6 calls a case`, `loads one case`, `reads version N`,
`reads prompts`, `up to 3 closures`, `records events into the run's log`,
`reads via adapters, checks` and `supplies case records`. On **2b** they are
`approves or rejects a proposal`, `writes clauses, places amendments`, `drafts a
clause; rerun`, `writes an approved amendment`, `reads human closures`, `reads
the drafter prompt`, `reads runs; rerun writes new ones`, `appends a closure
(review.py)`, `reads rulings`, `rebuilds the packet from`, `works the queue`,
`reads`, `pages uploaded to`, `reads`, `runs ops.queue, ops.escalation`, `reads
the public case`, `asks about a case`, `calls the tools` and `reads case pages`.
On the **dynamic** view they are `run_case(N)`, `reads`, `case`, `weights`,
`facts`, `brief`, `integrity table (no_show.json)`, `reads version 6`, `not
flagged: the brief, to both sides`, `stopped: ESCALATE, no model`, `claims`,
`kept claims`, `drafts`, `valid drafts`, `ruling or ESCALATE`, `events into the
run's log; eval writes case-*.json and the transcript`, `2 calls`, `4 calls` and
`shown to the judge`.
