# Before the third freeze: a confidence floor, a reason on every closure, complete call logs, and a readiness report (2026-10-07)

The task sheet dated 2026-10-07 asks for four things after a review of the
parallel-calls change: fix that change, add a confidence-floor gate to the judge
draft check, require a reason on every human closure, record four more fields on
every `agent_call` event with a per-case timeline, and produce a readiness
report. **No model call was made in any part, and no browser was launched.** Each
part is its own commit.

**What must not change**, and does not: no byte of any request sent to a model,
the prompts, the policy JSON files and the amendments, the brief, and `runs/`.
The proof is the offline replay from the parallel-calls sheet,
`tests/test_offline_replay.py`, which is run after every part and stays green.
The gate below is the one place where a change *could* have moved a recorded
answer, and part A measures that it does not.

## 0. The parallel-calls change, fixed

A review of `364877b`..`b129824` found seven things, each reproduced. They are
fixed in `6d542ac`; the buddy-log row for that commit records the evidence, and
the two documents that described the switch -- `README.md` and
`docs/notes/2026-10-06-parallel-calls.md` -- are corrected in it.

The one worth repeating here is the first, because it is the one a reader of this
note would otherwise get wrong. **The default path is the path that was there
before the switch.** The switch's first version routed the *sequential* path
through the same join the parallel path uses, which asked every call before
writing any of them and stored a failure instead of stopping on it. A probe with
four drafts and a first draft whose transport call raised made **six** requests
at that version where the commit before the switch, `3afd2f8`, made three. With
the switch off the pipeline calls `_call_agent` once per agent again, in order,
writing each call before the next request -- so the sequential transcript, the
events and the request count are `3afd2f8`'s, which is asserted by driving the
probe and comparing against a report taken from a worktree of that commit.

## A. `DRAFT_BELOW_FLOOR`

**The gate.** `check_judge_draft` gains a fifth check, after the four that were
there: a draft whose ruling is not an `ESCALATE` and whose own `confidence` is
below the policy's confidence floor abstains with the reason code
`DRAFT_BELOW_FLOOR`. It abstains for the same reason a malformed draft does -- the
floor is a policy instruction about what may be decided at all, and a ruling
below it is one the policy says must go to a human reviewer rather than be
carried.

**The floor is read, not typed.** It is stated in two clauses: `POL-RD-10(1)`,
"the Judge's own confidence in the ruling is below 0.70, which is the
platform-wide floor and is identical to `POL-NS-09(a)`", and `POL-NS-09(a)`,
"Judge confidence is below 0.70, which is the platform-wide floor and is
identical to `POL-RD-10(1)`". `pipeline.confidence_floor` reads the sentence out
of whichever of the two the brief carries -- a brief carries the policy for its
own category and the general one, so a no-show case carries `POL-NS-09` and a
route-deviation case `POL-RD-10` -- and refuses when neither is present or when
the sentence no longer parses. A number written into the pipeline would be the
silent override the policy's own notes describe: `policy/no_show.json` records
that the sentence which once let the Judge's configuration govern where the two
clauses diverge was deleted because "it authorised a hardcoded constant to
override written policy silently".

**After the vote.** A carried non-`ESCALATE` ruling whose confidence is below the
floor is published as an `ESCALATE` instead, with the vote recorded as
`escalated`, both amounts null and an explanation that names the floor and the
clause. This is **unreachable** through the pipeline: the gate abstains such a
draft, and an abstention is not part of a carried majority. It is kept because
"unreachable" is a claim about the checks in front of it and what it protects is
the thing that gets published, and it is tested with a synthetic draft set --
the draft built directly, with the check bypassed.

**The measurement, and the point of it.** The gate is a new check on a record
that already exists, so what matters is not that it fires but that it fires
nowhere that would have changed an answer. `tests/test_draft_below_floor.py`
rebuilds every recorded judge draft of the four sets the offline replay covers,
re-reduces every vote with the gate on, and holds every outcome against the one
the run recorded:

| set | recorded drafts | rebuilt | carrying a confidence | below the floor |
|---|---|---|---|---|
| corpus | 116 | 116 | 116 | 16 |
| codex | 60 | 60 | 60 | 8 |
| wild | 256 | 248 | 248 | 16 |
| wild-v2 | 80 | 80 | 80 | 4 |
| **total** | **512** | **504** | **504** | **44** |

The eight that cannot be rebuilt are the four drafts each of the two held-out
cases that produced no ruling, 517 and 533, which `check_replay` refuses because
there is no result for their advocates to be replayed against. All 512 recorded
drafts carry a confidence. Of the 44 below the floor, **43 already proposed an
`ESCALATE`** -- which is what the floor asks for, so the gate has nothing to add
-- and **1 was already invalid**, so it never voted. Every re-reduced outcome,
agreement, valid count, threshold and ruling equals the recorded one: the gate
changes no recorded outcome, which is asserted rather than asserted-about.

**Wording.** The reason text and the vote explanation name the floor and the
clause that states it. **Nothing in `prompts/` changes**, which is what keeps
every request byte for byte what it was.

## B. A reason on every human closure

`python3 -m tribunal.precedents close` records a human reviewer's decision on an
escalated case, and it recorded the decision and not the thinking behind it. It
now requires both.

**The reason is required, and required three times over.** `--reason` is a
required argument, so a closure with no reason is refused by the parser before a
run directory, a case file or a transcript is opened. It must be at least twenty
characters. And it must cite **at least one evidence id of this case** -- read
off the rebuilt brief's own evidence list, so another case's evidence id is
refused rather than accepted for looking the same -- and **at least one clause id
the loaded policy carries**, the limb allowed and the base id required to
resolve. A closure is the only record of what a person decided and why; a reason
that cites neither this case's evidence nor the policy's clauses is not a record
of a decision, it is a note that one was made. Every refusal happens before
anything is written, so a refused closure leaves the store exactly as it found it.

**The override flag is computed, not asked for.** The case's **transcript** is
read -- and only its recorded vote -- because the case file carries the ruling
the vote *produced* and not the proposals it was produced from, so a comparison
against the case file would be a comparison against the system's own answer. The
panel's **best-supported proposal** is the plurality proposal among the valid
drafts, grouped by its canonical serialisation and tied to the proposal whose
first draft came earliest: the same rule `_reduce_vote` uses to carry a ruling,
stated over proposals instead of draft keys. `override` is `true` when the
reviewer's own four graded fields differ from it, `false` when they agree, and
**`null`** when there is no proposal to compare against -- a one-draft run
records no vote at all -- because "the reviewer agreed with the panel" and "there
was no panel answer" are different facts and a boolean cannot hold both. Both
sides go through the pipeline's own `vote_key`, so a referral is compared as the
clause references it leads with rather than as prose, which is the only
comparison that can be made between two free-text referral lists. The proposal
compared against is recorded beside the flag.

**The reason is an event, not a field of the entry.** It is written as a
`human_decision` event on the same chain, **after** the closure, carrying the
reviewer, the decision, the reason and the override flag. It is deliberately not
part of the entry: the block the judge is shown is built from the entry alone, so
putting the reason there would send prose about one case to the judge of another.
The two events go through one `EventLog`, so the chain is continued once and the
decision's line chains onto the closure's own line.

**The store's schema version is bumped for new entries**, which now carry
`schema_version: 2`, `override` and `override_proposal`. The two entries the
owner closed before this -- `P-0001` and `P-0002` -- carry none of them and are
**not rewritten**: the store is append-only, so they read as version 1, which is
what they are, and they still verify. `precedents/README.md` and the shipped
store are untouched by this part.

## C. Complete call logs, and a timeline per case

**Four fields on every `agent_call` event.** `model` -- the model that answered,
read off the result rather than assumed. `policy_version` -- the version the case
was briefed at, threaded down from `run_loaded_case`. `brief_sha256` -- the
digest of the brief the agent was handed. And `body_sha256` -- the digest of the
whole HTTP request body, which the client already computes and the run's
`calls.json` already records. A reader of one line should not have to open
another file to learn what the line was produced under. The verifier's call
carries them too, because it is a model call like any other.

**`request_sha256` is misnamed, and it stays.** It is the digest of the *user
message*, not of the request, and it is kept exactly as it was: the name is in
every committed event log, and a rename would make two generations of line mean
different things under one key. `body_sha256` is the field that actually is the
request body's digest, and a test asserts the two are never equal.

**Effect on the record.** Events are not part of any request, so **nothing the
offline replay checks moves**: the same requests are sent, the same answers are
written and the same rulings come out. Old run directories keep their old events
-- a line written before this has no `body_sha256` and is not rewritten, which is
what an append-only log means -- and every committed log still verifies, because
the new fields are payload and the chain is built over whatever the payload is.

**A timeline per case.** `python3 -m eval.events --run-dir <dir> --case N` now
prints a timeline rather than a line of key-value pairs: one row per event, in
the order it happened, with seven columns -- the time, the event, the role or the
draft it was, the status the provider returned, what it cost in tokens, how long
it took and how its answer parsed -- and a dash in a column an event has nothing
to say about, because a referee decision that spends no tokens is not a call that
cost nothing. The last two lines are the **vote** and the **ruling**, which are
what the calls were for; a case that produced neither says so instead of printing
a row of dashes. It reads the log and writes nothing.

## D. The readiness report

`python3 -m eval.readiness` prints a report and writes nothing; `--out` writes
it, and must name a file under `docs/notes/`. Every number in it is **computed**
-- from the repository's committed runs, from the frozen answer keys, from the
loaded policy, from the tests that already measure the thing, and from one
measurement run named with `--speed-run`. Nothing is typed in.

**The measurement run is named without a path.** An absolute path may not go into
`docs/`, so the report identifies it by the invocation that produced it, the
commit it ran at, whether `--parallel-calls` was on and at what concurrency, and
the sha256 of its own `run.json`. It is read and never written; it is not copied
into the repository and it is not re-run.

**The prices, and the tier.** `--price-in-per-m`, `--price-out-per-m` and an
optional `--price-cached-in-per-m`. When a cached-input price is given, the
cached tokens are priced at it and **the rest of** `prompt_tokens` at the input
price; `completion_tokens` already includes the reasoning tokens, so output is
priced once. The arithmetic is `Decimal`, and one test states why as a case:
sixty-four prompt and 2,234 completion tokens at 0.15 and 0.6 cost exactly
0.00135 USD, which rounds to 0.0014 in `Decimal` and to 0.0013 in `float`,
because 0.00135 is not a binary fraction. The report states which of the owner's
two bands it priced at, computed from the instant the run recorded: peak is
Monday to Friday, 09:00-12:00 and 14:00-18:00 Singapore time, and the speed run
began at 20:42 SGT on a Tuesday, which is ordinary.

**The comparison with a sequential run is like for like.** It is against
`runs/policy-v2/<model>/` -- the same 15 corpus cases at the same policy version,
one call at a time -- and over the case numbers the two share. It is deliberately
**not** against `runs/<model>/`: 28 of that run's 29 cases replayed their
advocates from an earlier run, so its `call_seconds` is judge time only, and the
report refuses a baseline whose cases carry a non-null `replay` rather than
printing a ratio between a partial measurement and a whole one. If it shows the
recorded `wild-v2` mean it labels it as a different case set at a different
policy version and **not** as a baseline.

**What each dimension measures.**

1. **Quality** -- the offline replay's result per set, run through the module
   that owns the replay rather than a second implementation of it; the
   confidence gate's effect on every recorded judge draft; and the speed run's
   four-field score against the key.
2. **Speed** -- the median and p90 of `wall_seconds` and of `call_seconds` (the
   sum of a case's call durations, which is what one call at a time would have
   taken), the ratio of the two medians, the median and p90 tokens per case, and
   the cost per case.
3. **Reproducibility** -- `ui.build --check` across every page, both sealed-set
   manifest tests, the offline replay, and the freeze gate's exit status against
   `freeze-2026-10-03`.
4. **Human management** -- every `ESCALATE` in every committed run, with the
   votes that produced them counted by outcome and the reason codes they rest on
   counted; and that `precedents close` refuses a command with no `--reason` and
   `policy_gaps approve` one with no `--approved-by`.
5. **Logs** -- `verify_chain` over every committed **run's** log, the share of
   the speed run's `agent_call` events carrying all four new fields, and the
   timeline over a speed-run case.

Each dimension gets a PASS or FAIL line, and the report ends with the five of
them and whether every one passed.

**One honest finding, and one criterion that cannot be met.** The logs dimension
reports `runs/codex/<model>/events.jsonl` as not verifying, at line 343, where
`prev` does not name the previous line -- a break in a committed log that
predates this task and that nothing here repaired. And the criterion that the
speed run's `agent_call` events carry all four new fields **cannot** be met by
that run: it was made at `b129824`, before part C added them. The report says
exactly that rather than reporting a zero as a defect in the code that writes
them, and it is met by every run made since.



