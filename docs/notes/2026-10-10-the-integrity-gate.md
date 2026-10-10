# The record-integrity gate: `POL-RD-10(2)` and `(4)`

**2026-10-10.** Two of `POL-RD-10`'s escalation triggers are conditions code can
test with no model, and the judge read past both at version 6
([`2026-10-10-what-went-wrong-at-version-6.md`](2026-10-10-what-went-wrong-at-version-6.md)).
`--integrity-gate` is a new switch that holds the assembled record to them and
escalates a record that fails, with no advocate, judge or verifier call at all.
It is **off by default**, so every recorded run replays exactly as it did, and it
is refused for every sealed set, whose single run is one measurement and is not
re-taken.

The switch reaches the pipeline as one keyword through `run_set`,
`run_benchmark` and `run_case` (and `run_loaded_case` and `replay_case`, the two
bodies those delegate to), and it is recorded where `parallel_calls` is recorded
and nowhere else: the `invocation_start` event and the run's `run.json`. It is
deliberately **not** in a case's `configuration` object, because a gated case
sends no request at all and every other case's requests are byte-identical, so a
result produced with it on is the same result.

The change touches no prompt, no policy and no case data: it is
`tribunal/pipeline.py`, `tribunal/events.py`, `eval/run_benchmark.py`,
`eval/development_sets.py`, the new `eval/integrity_gate.py`, this note and one
test module. Nothing under `runs/` was read, changed or staged by hand -- the
report below reads it through the repository's own reader -- and nothing under
`tmp/` was committed.

## The gate

`POL-RD-10` says the judge must not issue a final ruling, and must escalate,
whenever any of eight things holds. Two of them are decidable on the record:

* **limb (2)** -- "the trip identifiers on trip_record, gps_trace and
  fare_breakdown do not all match, or the trip_record is absent from the pool";
* **limb (4)** -- "pickup or dropoff timestamps on two admitted artifacts
  disagree by more than 10 minutes, or any artifact's timestamps run
  backwards".

The gate runs in `tribunal.pipeline.run_loaded_case`, in the same place the
`POL-GEN-08(1)` scope gate sits -- after the brief is built, before a prompt is
rendered and before any call -- and **after** it, so a flagged dispute keeps the
scope gate's own record. When the switch is on and the dispute is a
`ROUTE_DEVIATION`, `record_integrity_limbs` tests the assembled record and, if it
trips either limb, `record_integrity_ruling` publishes an `ESCALATE` with the
reason code `RD10_RECORD_INTEGRITY`, confidence 0, both money fields `null`, an
empty referral list and an explanation naming the limb. A `record_integrity`
block is written into the case file beside `scope_gate`, naming the limbs, the
clause, the reason code and `calls: 0`; a `record_integrity` event is appended to
the run's log. The policy is read only when the switch is on, so a run without it
builds the bytes it always built.

**Exactly which fields are compared, and why each is a pickup or dropoff
timestamp.** Limb (4) compares two pairs:

* `trip_record.started_at` against `gps_trace.first_fix_at` -- the **pickup**
  pair. `started_at` is when the trip, and its meter, began at the pickup point;
  `first_fix_at` is the first position the trace records for the trip. Both are
  the trip's beginning, which is the pickup event, and case 112 is the 13
  minutes 30 seconds between them.
* `trip_record.ended_at` against `gps_trace.last_fix_at` -- the **dropoff**
  pair, by the same reading at the other end: `ended_at` is when the trip
  finished at the dropoff point and `last_fix_at` is the trace's final fix.

"Run backwards" is each artifact's own pair: `started_at` after `ended_at` on the
trip record, or `first_fix_at` after `last_fix_at` on the trace. The wider
ordering (`requested_at` to `ended_at`) holds in every case this repository
carries and is deliberately **not** part of the gate: the limb names the pickup
and dropoff timestamps, and those are the pairs above.

**The minutes are read, not copied.** `record_integrity_minutes` matches limb
(4)'s sentence word for word in the loaded clause and takes the number out of it.
A policy whose sentence has moved is **refused** with a `PipelineError` naming
the sentence, rather than measured against a figure the module carries. The
sentence is identical at versions 1 and 6, so the gate applies at every version
when it is asked for.

**An admitted artifact** is one present in the record with a payload. That is the
same test as `admissibility.status != "MISSING"` on every case in this
repository -- a `MISSING` artifact's payload is `null`, checked over all of them
-- and it is the test that survives the `admissibility` ablation, which removes
the status object but never the payload. The identifier compared is each
artifact's payload `trip_id`, falling back to the identifier it was filed under;
an artifact that is absent is not compared, so a record holding only one of the
three has nothing to disagree with.

## The no-show question: `POL-NS-09` carries no limb of the same kind

The sheet asks whether `POL-NS-09` carries a limb of the same kind for no-show
disputes, and to apply it the same way if it does. **It does not, and the gate is
therefore `ROUTE_DEVIATION` only.** `POL-NS-09`'s five triggers are:

* **(a)** a judge-confidence floor;
* **(b)** two admissible artifacts contradicting each other directly on arrival,
  dwell or rider presence **and no clause resolving the conflict**;
* **(c)** a counterparty dispute history between the same rider and driver;
* **(d)** the `POL-NS-07` anti-farming check, or a rider abuse count;
* **(e)** the sole evidence for the deciding fact impaired under `POL-NS-08`.

None of them is a deterministic record-integrity test. There is **no
identifier-matching limb** anywhere in the clause and **no backwards-timestamp
limb**. The nearest, (b), is expressly the case where a clause does *not* resolve
the conflict, which is the opposite of a test code can make on the record alone;
and its subject matter -- arrival, dwell, rider presence -- is exactly what
`POL-NS-01` to `POL-NS-07` exist to resolve. `POL-NS-08(a)` does compare trip
record and trace times, but it is an impairment rule that down-weights a claim
and reads **90 seconds**, not an escalation trigger, and it is not in
`POL-NS-09`. Applying a threshold to (b) that the clause does not state would be
inventing policy, which is the one thing this gate must not do. A no-show dispute
therefore reaches the judge exactly as it did, and the report below says so in
its own words.

## What it would have done, from the record

`python3 -m eval.integrity_gate --report` is read-only and makes no model call.
It rebuilds each case's version-6 brief and runs the pipeline's own
`record_integrity_limbs` over it, for every committed case that has a run at
policy version 6 -- the corpus, `dev-v2-ext`, `dev-v2` 1779, the organisers'
sample 901, `sealed-v1`, and the three functional sets -- and compares the
limbs with the key's ruling and with the ruling the run recorded. The whole
report, pasted as it printed:

```
The record-integrity gate, replayed from the version-6 record
read from the committed runs under runs/, the committed case files and the committed keys; no model call

the gate: POL-RD-10's limbs (2) and (4), on ROUTE_DEVIATION disputes only, off by default.
   POL-RD-10(2)  the trip identifiers on trip_record, gps_trace and fare_breakdown do not all match, or the trip_record is absent from the pool
   POL-RD-10(4)  pickup or dropoff timestamps on two admitted artifacts disagree by more than the clause's own minutes, or an artifact's timestamps run backwards

== The runs ==
   corpus             29 cases   the 29-case corpus
   dev-v2-ext        120 cases   the 120-case extension set
   dev-v2               1 case   case 1779 alone, the prompt-injection case
   ryde-v3              1 case   the organisers' sample, case 901
   sealed-v1          24 cases   the third sealed set's single run
   inject-v1          12 cases   a functional set, run once by the owner
   pii-v1              8 cases   a functional set, run once by the owner
   collusion-v1        8 cases   a functional set, run once by the owner
   all               203 cases   every committed case with a run at version 6

== The gate ==
   would escalate   3 of 203
   by limb          POL-RD-10(2) 2, POL-RD-10(4) 1
   112    corpus       POL-RD-10(4)              key ESCALATE                      run NO_ACTION
   2834   dev-v2-ext   POL-RD-10(2)              key ESCALATE                      run ESCALATE
   2858   dev-v2-ext   POL-RD-10(2)              key ESCALATE                      run PARTIAL_REFUND

   would fix        2   112 (corpus) and 2858 (dev-v2-ext)
     the key is ESCALATE and the run ruled something else
   would leave      1   2834 (dev-v2-ext)
     the run already escalated, so the gate changes nothing a reader acts on
   would break      0   none
     the key is not ESCALATE, so the gate would escalate a case it decides

== What the gate does not touch ==
   a NO_SHOW_CHARGE dispute is not held to any of this. POL-NS-09 carries no limb of the same kind: none of its five triggers is a deterministic record-integrity test, and its nearest, (b), is expressly the case where a clause does not resolve the conflict. See tribunal.pipeline.record_integrity_limbs.
   the gate is off by default, so a run without --integrity-gate is byte for byte the run it was.
```

**It breaks no case.** The gate would escalate three of the 203 cases with a
version-6 run, and every one of the three has `ESCALATE` as its key. Two of them
are the two misses the note of 2026-10-10 names: **112**, where the trace begins
13 minutes 30 seconds before the trip record says the trip started (limb (4)),
and **2858**, where the fare ledger is filed under `TRP-02758` while the trip
record and the trace are `TRP-02858` (limb (2)). The third is **2834**, the same
identifier defect one case earlier in `dev-v2-ext`: the key is `ESCALATE` and the
run had already escalated it, so the gate changes nothing a reader acts on.

Nothing is broken and so nothing is narrowed. The rule was not tuned to the
cases it fires on: the two limbs are the clause's own sentences, the minutes come
out of the clause, and the identifier read is the artifact's own `trip_id` field.
The only repository-wide check that mattered was the reverse one -- that no case
whose key is a monetary ruling trips a limb -- and none does: three cases in the
whole repository carry a mismatched fare-ledger identifier (2834, 2858 and
`dev-v2` 1784, which has no version-6 run and is therefore not in this report),
and one case, 112, carries a timestamp disagreement over ten minutes.

**The gate is a measurement, not an adoption.** It is off unless asked for, so no
figure in the README's results tables moves. What the report says is what the
switch *would* do on the runs that were actually made.

## What is refused

* **`--integrity-gate` for a sealed set.** Refused by the set's own name through
  `assert_not_sealed`, in the same list `--force` and `--early-majority` are
  refused in, and again in `run_set`. A sealed set's single run is one
  measurement, and a switch that would have escalated a record without asking the
  model is a different measurement.
* **A record whose clause has moved.** Not a switch refusal but a refusal
  nonetheless: if `POL-RD-10`'s limb (4) sentence is not in the loaded clause,
  `record_integrity_minutes` raises rather than measure against a number this
  module carries.

`--integrity-gate` is **not** one of the four switches that change what a run
measures -- a gated case sends no request, and every other case's requests are
byte-identical -- so it is not refused beside them and it moves no run directory,
exactly as `--parallel-calls` and `--early-majority` do not.

## Tests

`tests/test_integrity_gate.py` drives the real `run_loaded_case` over the rig's
scripted transport, on a corpus route-deviation case whose three artifacts carry
the same identifier and whose trace begins and ends at the trip record's own
timestamps, mutated one way at a time: the unaltered record reaches the model
with no block; a fare ledger filed under another trip's identifier escalates by
(2) with **no request sent**, an `ESCALATE`, confidence 0, no money, no referral
and an empty transcript; an 11-minute pickup disagreement escalates by (4); a
9-minute one reaches the model; a no-show case is not held to these limbs; the
reason code, the clause and the limb are recorded on the result and named in the
explanation. A moved clause sentence is refused, both at
`record_integrity_minutes` and end to end. With the switch off the model is
asked, no block is written and the requests are byte-identical to a run whose
gate did not fire. The switch is not in a case's `configuration`, is named in
`run.json` and in the `invocation_start` event only when it is on, and the
committed corpus run's `brief_sha256` still rebuilds. The sealed set is refused
by its own name at `run_set` and at the command line, with the same invocation
without the switch as the control.

**They were not run here.** The owner runs every test outside this sandbox. What
the session executed is the report above, a byte-compile of every changed module,
and one throwaway script outside the repository that drove the same fixtures
through the same public functions to see each behaviour fire; the test module
itself was never run.
