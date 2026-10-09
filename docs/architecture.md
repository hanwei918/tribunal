# Tribunal architecture

The diagram is the whole arbitration system as it stands at the freeze tag
`freeze-2026-10-09`, which is policy version 6; every box names the file that
implements it, every arrow is directed, and every arrow that carries something
says what it carries.

![Tribunal architecture](architecture.svg)

## Band A - the case path

**1. Dispute and evidence.** `data/PUBLIC-CONTRACT.md` defines the case: a trip
record, a GPS trace, a chat log, a fare breakdown, the two party profiles and
one or two traffic advisories. `tribunal/loader.py` loads one case and refuses
one whose manifest entry, filename and declared number disagree. A reader can
check the four shape checks and the recursive scan that rejects an
evaluation-only key.

**2. Scope gate.** `tribunal/pipeline.py` holds the gate, `POL-GEN-08(1)`, and
the reason code `GEN08_SCOPE`. From policy version 3 a dispute whose
`safety_flag` or `complaint_flag` is true is never adjudicated: the record is
assembled and no advocate, judge or verifier is called. A reader can check
`scope_gate_flags`, `scope_gate_ruling` and that the branch fires before any
prompt is rendered.

**3. Admissibility precheck.** `tribunal/prepass.py` turns an artifact's issue
codes into the weight multiplier the corpus declares: one code takes its own
weight, several take the decimal product floored at 0.25, and a blocking code is
0.0. From version 3 the table is read from the loaded policy's `integrity`
block. A reader can check `weight_for` and the GPS-gap classifier.

**4. Derived facts.** `tribunal/facts.py` does the geometry a language model
cannot: haversine distances, the excess over the optimal route, dwell, gaps,
waypoint (ERP gantry) approach and the trip record's own pickup and dropoff
events. It holds no policy number; every threshold arrives as a parameter. A
reader can check that no clause number appears as a literal in the module.

**5. One brief.** `tribunal/brief.py` builds exactly one object per case,
canonicalises it and records its sha256, and both advocates read those same
bytes. From version 6 it also masks Singapore vehicle registration marks in a
chat message's `text`, a trip record's event details and the dispute's two
free-text fields. A reader can check that the module has no side or stance
parameter.

**6. Two advocates.** `prompts/v1/advocate.system.md` is one template; the only
difference between the two advocates is the stance block,
`prompts/v1/stance.rider.md` or `prompts/v1/stance.driver.md`. They run in
parallel on the same brief. A reader can check `check_stance_only_difference`
and that the rendered prompts differ in one region and nowhere else.

**7. Citation referee.** `tribunal/referee.py` is deterministic and decides no
merits. It discards a claim whose evidence ids or clause ids do not resolve in
the loaded brief, a claim that cites an impaired artifact without naming its
issue code, and a claim grounded on a context-only profile field. A reader can
check `_check_claim` and the closed set of reason codes.

**8. Judge.** `prompts/v1/judge.system.md` is the prompt and
`tribunal/pipeline.py` runs the panel. Four drafts are taken: three sampled at
temperature 0.7 with distinct seeds and one position-swapped draft, and the
majority is taken over all four graded fields together - the ruling, both
amounts and the referral clause references. A reader can check
`DEFAULT_JUDGE_VOTES`, `vote_key` and `_reduce_vote`.

**9. Confidence floor and policy triggers.** `tribunal/pipeline.py` reads the
floor from the policy (0.70) and never types it as a number. Below the floor, a
tie, no valid draft, or a policy escalation condition goes to a human;
otherwise the ruling is `FULL_REFUND`, `PARTIAL_REFUND`, `NO_ACTION` or
`DRIVER_COMPENSATION`, with amounts read off the brief's published money block.
A reader can check `confidence_floor` and `REQUIRED_AMOUNTS`.

**Every call recorded.** The grey strip is the record. `tribunal/transcript.py`
writes one entry per call with the prompt digests and the raw response, and
`tribunal/events.py` writes a hash-chained event log in which every line carries
the previous line's digest. `tribunal/model.py` is the one place the runtime
model is named, through `RUNTIME_MODEL`, `MODEL_PROVIDER` and `MODEL_REGION`. A
reader can check `verify_chain` and that no module sets a model default.

## Band B - the human and operations layer

The band reads the pipeline's records and never feeds a brief or a prompt.

**Risk signals.** `ops/risk.py` runs the five policy tests (`POL-RD-06`,
`POL-RD-08`, `POL-NS-07`, `POL-NS-09(c)`, `POL-NS-09(d)`) and quotes each
threshold out of the loaded policy. Its signals go to the reviewer and the queue
and never to the judge. A reader can check that the lifetime counters are never
read.

**Evidence collection.** `ops/sources.py` builds one index over a case root and
exposes six adapters; `ops/evidence.py` is given only the dispute and returns the
artifacts in the order every case file files them. A reader can check that the
collector never reads `dispute.evidence_ids` to decide what to fetch.

**Queue, SLA and routing.** `ops/queue.py` sorts the disputes of a run into the
safety, human-review and auto lanes, and `ops/config.json` holds the team's SLA
targets and the kill switch `auto_rulings_enabled`. A reader can check that no
threshold comes from the policy and that the kill switch moves an auto case into
human review.

**Escalation packet.** `ops/escalation.py` builds what a reviewer is handed: the
record, both claim sets, the referee's ledger, the admissibility report and all
four drafts. A reader can check that no `expected` and no `matched` field reaches
a packet.

**Review and closure.** `ops/review.py` wraps `tribunal/precedents.py`'s `close`
with one more requirement, a `--packet-sha256` that must equal the packet rebuilt
now, and the closure carries the reviewer's reason citing evidence and clause
ids. A reader can check that a stale digest is refused.

## Band C - learning

**Precedent store.** `precedents/precedents.jsonl` is an append-only,
hash-chained store of human closures. With `--precedents` on the judge is shown
up to three of them that share clauses with the case; with it off the key is
absent. A reader can check that no amount and no summary travel in the block.

**Policy-gap loop.** `eval/policy_gaps.py` finds the cases the policy could not
decide, groups them, and asks a model to draft one clause for a group a person
has closed at least twice. A draft is a proposal until a person approves it. A
reader can check that `approve` is the only writer of an amendments directory.

**Policy versions.** `tribunal/policy_versions.py` builds the policy a case is
briefed against. Base 1 is version 1 and its amendment `0001` makes version 2;
base 3 is version 3 and its three amendments - `POL-NS-11`, `POL-RD-14` and
`POL-NS-12` - make version 6, which is the version this diagram is drawn at and
the version the freeze tag fixes. A reader can check `highest_available_version`
and `owner_of_version`.

## Measured, not claimed

The development sets, the two sealed sets run once each from a freeze tag, and
the offline replay of every recorded run all live under `eval/`. A reader can
check the recorded runs under `runs/` and the committed keys under `eval/`.
