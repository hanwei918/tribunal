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
