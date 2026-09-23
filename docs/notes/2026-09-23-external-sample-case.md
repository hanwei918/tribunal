# The organisers' sample case: what the ruling did

Date: 2026-09-23. Commit: the one that adds this file.

The organisers' sample case (DISP-002) has been converted and arbitrated once. This note records
what that ruling did, checks it against the transcript and the clause text, and names the part of
the judge prompt that let it be written. **No prompt was changed in this session**, for the reason
given at the end.

## The record, and where it is

`runs/external/ryde/` is committed **exactly as produced** at `b2556e8`, in its own commit, before
anything about it was changed. No file in it was edited and the case was not re-run.

| | |
|---|---|
| Produced at | `40e06a5`, prompts digest `b131e63f046aecc6`, Python 3.11.14 |
| Tokens billed | **152,367** (prompt 49,685 + completion 102,682; reasoning 96,721 is a breakdown of completion, cached 5,760) |
| Wall clock | **421.0 s** (`wall_seconds` 421.0437; the three calls took 89.58 s, 74.92 s and 256.52 s) |
| Transcript | `transcript_sha256` `fb8c27c4fc7e51f5c9a9376d0d43bfb0fb6077ef5e68c78932a54f94f8b136a2`, re-hashed from the committed file and equal |

The ruling: `PARTIAL_REFUND`, `amount_sgd` 1.00, `driver_compensation_sgd` 3.20, `confidence` 0.75,
`referrals` `[]`, no escalation. The organisers state **"Cancellation charge UPHELD"**, read from
`eval/external/ryde/expected.json` as a stated expectation and not as an answer.

One contract point from the record itself: the judge's ruling object carried a seventh field,
`referrals_note`, which POL-GEN-03 does not admit. The pipeline recorded it rather than corrected it
— `ruling_findings: [{"invariant": "six_pol_gen_03_fields", "detail": "unexpected field(s) in ruling",
"extra": ["referrals_note"]}]` — which is the behaviour that field exists for.

## 1. The summary printed `None` for every field but the ruling

`eval/run_benchmark.format_external_result` read `amount_sgd`, `driver_compensation_sgd`, `referrals`
and `confidence` off the object it was handed. The judge returns a **result object** —
`{"ruling": {...}, "discarded_claims": [...]}` — so all four are one level down and the outer object
has none of them. The printed block read:

```
  produced      : ruling {'amount_sgd': 1.0, 'confidence': 0.75, ...}
                  amount_sgd None   driver_compensation_sgd None
                  referrals None
                  confidence None
```

The four fields now come through `eval.grade.produced_from_mapping`, which is the unwrapping the
grader already scores with, so the printed fields and the graded fields cannot come from different
places. Against the committed artifact the block now reads `amount_sgd 1.0`,
`driver_compensation_sgd 3.2`, `referrals []`, `confidence 0.75`.

**The test that would have caught it** is
`ExternalRunTests.test_a_ruling_of_the_stored_shape_prints_its_own_four_fields` in
`tests/test_external_case.py`. It reads the four values out of `runs/external/ryde/case-00901.json`
and requires the summary to print each one, so both sides of the comparison come from the artifact
and cannot agree by both being wrong. The existing test beside it asserted only that the ruling word
appeared, and the ruling word appeared inside the nested object's repr — which is why the defect
survived a green suite. Checked against the old printer, the new test fails on five assertions.

## 2. The six points, checked against the transcript and the clause text

**None of the six is wrong.** Each is verified below, with the one place I would add precision.

### (a) Limb (b) is not carried — VERIFIED

`derived.arrival.qualifying_fix_count` is **0**, and so are `longest_qualifying_run.fix_count` and
`longest_qualifying_run.duration_sec`; `dwell_start_offset_sec` is `null`. Not one of the eight fixes
carries an accuracy figure, and POL-NS-02 admits only fixes "with reported horizontal accuracy of
25 m or better" inside the arrival radius, counting worse ones as "evidence of neither presence nor
absence". No fix therefore places the driver inside the geofence and POL-NS-01 limb (b) — "the
gps_trace places the driver inside the pickup geofence defined in POL-NS-02" — is not carried.

*Precision:* in the brief each derived value is wrapped with the `evidence_id` it came from, so the
path reads `derived.arrival.qualifying_fix_count.value`.

### (b) Limb (c) is measured from the wrong end — VERIFIED

POL-NS-01 limb (c) reads: "the dwell being measured from the first qualifying in-geofence GPS fix
and not from the 'arrived' event". The judge's explanation reads: "The trip record shows the driver
marking 'arrived' at 08:43:00 and terminating at 08:51:00 with reason RIDER_NO_SHOW — an eight-minute
hold against the 300-second (five-minute) STANDARD-zone minimum." That is the arrival marker to the
termination, which is the measurement the limb names and forbids.

### (c) The rider made this argument and it was not answered — VERIFIED

The rider's fourth claim (`asserted_weight` 1.0, `POL-NS-01`, `EV-CHAT-00901` and `EV-TRIP-00901`)
reads in part:

> "The driver's chat cannot fill that gap. POL-NS-01 limb (c) runs the clock from GPS entry into the
> geofence, not from the arrival tap and not from messages, and POL-NS-01 is conjunctive."

It is **not** among the five discarded claims. Those five are three DRIVER claims and two RIDER
claims — the POL-NS-06(i) accumulation claim and the POL-NS-09(e) claim — and this is neither. The
explanation does not answer it either: it asserts that the chat log "shows the same thing
independently" and never addresses the argument that the limb's clock is a GPS measurement.

### (d) Every message the judge relied on was the driver's — VERIFIED

The chat log's six entries are five `DRIVER` and one `SYSTEM`; the rider sent none. The four the
explanation names — the lobby message at 08:43:00, the car and plate at 08:45:20, the unanswered
call at 08:47:05, and the warning at 08:50:45 — are all driver-sent. The explanation's own sentence
records it: "the rider sent no message and did not answer the call."

### (e) On this policy's text the deciding fact rests on the impaired artifact — VERIFIED

Limbs (b) and (c) are, by their own wording, tests of the `gps_trace`. The only GPS evidence is
`EV-GPS-00901`. It reports no accuracy on any fix, so no fix qualifies and no dwell can be measured
at all. It is also impaired for policy under POL-NS-08(b): three of its seven intervals exceed 120 s,
two of those fall inside the 08:43–08:51 waiting window, and the window carries four fixes where the
limb requires six.

POL-NS-08 then says in terms: "Where the ONLY evidence for the deciding fact is impaired UNDER LIMBS
(a) TO (d) OF THIS CLAUSE, the ruling may not exceed PARTIAL_REFUND and the case escalates under
POL-NS-09", and POL-NS-09(e) is "The sole evidence for the deciding fact is impaired under limbs (a)
to (d) of POL-NS-08". Escalation under POL-NS-09 is terminal: no monetary ruling issues and the fee
is held rather than collected or refunded.

*The counter-argument, and why it does not hold.* The judge's move was to treat the trip record's
marker and the driver's chat messages as independent carriers, which would lift the cap to 1.0 and
take the case out of POL-NS-09(e). But the clause defines its own evidence: limb (b) asks whether
*the gps_trace* places the driver in the geofence, and limb (c) fixes the dwell as a measurement
*from the first qualifying in-geofence GPS fix*. A carrier that the clause does not name cannot
satisfy the limb the clause states, and limb (c) says expressly that the clock does not run from the
'arrived' event. It is also worth recording the other direction: POL-NS-02's opening sentence would
read "no qualifying in-radius fix" as a full refund, and POL-NS-02's own note says a trace too sparse
to establish three consecutive in-radius readings "is impaired under POL-NS-08(b) rather than proof
of absence". The trace can prove neither presence nor absence; POL-NS-08's cap sentence is what
resolves that, and it resolves it toward escalation rather than toward either monetary ruling.

### (f) The 1.00 refund is the schedule's 4.00 against the 5.00 charged — VERIFIED

`data/external/ryde/mapping.json` records it under `policy_divergences[0]`, **committed before the
run** (commit `be42ab0`, 2026-09-23 20:17:09 +08:00; the run started 23:28:34 +08:00, 3 h 11 m
later):

- the source's cancellation fee of SGD 5.00 "matches no entry in `fee_schedule`";
- `zone_class_fee_sgd` for STANDARD is 4.00 and `vehicle_tier_fee_sgd` for RYDE_X is 4.00, so the
  greater under `resolution_rule` is 4.00, and "no combination of zone class and vehicle tier in the
  schedule produces 5.00";
- the converted case carries the source's 5.00 unchanged "because changing it would be editing the
  evidence", so POL-NS-08(d) is engaged on the converted case;
- `depends_on_assumptions` is exactly `["pickup zone class is STANDARD", "vehicle tier is RYDE_X"]`,
  the two entries in the file's `assumptions` list, which is where the zone class and the vehicle
  tier the run read come from.

So the SGD 1.00 is 5.00 − 4.00, and both sides of that subtraction rest on the two recorded
assumptions rather than on anything the source states.

## 3. Which part of the judge prompt allowed it

`prompts/v1/judge.system.md`, **Step 2, the subsection "### What can carry a deciding fact"** (lines
47–74). It reads, in the relevant part:

> **Every artifact in `case.evidence` is a candidate carrier, not only the instrument evidence.** A GPS
> trace, a trip record and a fare breakdown are artifacts; so is a chat log, and so is a counterparty
> statement. What a party said is evidence like any other, and it can carry the deciding fact. Its
> weight is its own `weight_multiplier`, read from the artifact exactly as for any other. A cap
> computed as though the instruments were the only things able to carry a fact escalates cases that are
> decidable.

> Two patterns qualify. They are illustrations of one principle, not a list to match against:
>
> - **An admission against the speaker's own interest.** A party does not concede what helps the other
>   side without reason, so the concession is evidence of the thing conceded.
> - **A contemporaneous record made from inside the disputed window.** It is evidence of what was
>   happening then because it was made then, by someone who was there.

> A message that merely exists is not a carrier, and neither is one that only repeats what the
> instruments already say. **The test is whether it would still support the finding if the instrument
> evidence were removed.** If it would not, it is a restatement of the instruments rather than an
> independent carrier, and the cap does not move.

That is the section the judge used: its explanation says the arrival and waiting facts "are carried
independently by the trip record and the chat log, each at full weight", which is the second pattern
applied to the driver's own messages.

**Why it reaches limbs (b) and (c) at all is the part that is wrong, and it is a gap rather than a
contradiction.** The subsection sits under Step 2, whose subject is the *confidence cap*
(POL-GEN-02(2)); it answers "what can carry a deciding fact" for the purpose of that arithmetic. It
never says that where a clause states its own evidentiary test — limb (b)'s "*the gps_trace* places
the driver inside the pickup geofence", limb (c)'s dwell measured "from the first qualifying
in-geofence GPS fix" — no other artifact can stand in for that test. Reading "carrier" as "whatever
satisfies the limb" is what turned the trace from a failed test into "silent, not contrary" and moved
the cap from 0.60 to 1.0. The removal test does not stop it: the driver's messages would survive the
removal of the instruments, and they are contemporaneous, so they pass both of the patterns offered.

It is worth naming that this subsection was **added on 2026-09-22 to fix the opposite failure** —
over-escalation, recorded in `docs/notes/2026-09-22-deciding-fact-carriers.md`. That note warns that
loosening Step 2 "trades the safe failure for the dangerous one". This case is the dangerous one:
a monetary ruling on a fact that only an impaired instrument could establish.

## 4. What was not done

- **No prompt was changed.** Editing `prompts/v1/judge.system.md` moves the prompts digest and makes
  every one of the 29 cached corpus results stale on the prompt channel. That decision comes after
  this note exists, and this note is the evidence for it.
- **No cached result was touched**, no case was re-run, and the answer key was not edited.
- The converted case, the mapping record and the organisers' expectation were read, not changed.

## Verification

- `ExternalRunTests.test_a_ruling_of_the_stored_shape_prints_its_own_four_fields` passes against the
  fixed printer and fails on five assertions against the old one.
- The committed transcript re-hashes to the digest recorded beside it in `case-00901.json`.
- Every figure above is read from `runs/external/ryde/`, `data/external/ryde/mapping.json`,
  `policy/no_show.json` or the rider's and judge's own `response_text` in the transcript.
