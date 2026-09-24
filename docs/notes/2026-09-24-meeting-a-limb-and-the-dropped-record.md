# Meeting a limb is not carrying a fact, and the record the converter dropped

Date: 2026-09-24. Commit: the one that adds this file.

Two changes, both prerequisites for re-running the benchmark. **No model call was made and nothing
was re-run.** The run in `runs/external/ryde/` is the record of what the system did before either
change and is not touched by them.

---

# Part 1 — the converter dropped a source record

## What was dropped

`eval/external/ryde/DISP-002.md` records the source platform's own `driver_arrived` event, at
08:43:00:

> Driver GPS within 10m of pickup point. Speed 0 km/h. Auto-arrival confirmed.

That text reached neither `data/external/ryde/case-00901.json` nor `mapping.json`. The converter's
own contract — stated in its module docstring — is that every item in the source is either carried
into the converted case or recorded in the mapping with the reason it is not. This one was neither,
which made that contract a claim rather than a check.

It matters beyond bookkeeping. It is the one record in the source that says *how the arrival marker
was made*, and what it says is that the marker and the trace are not two measurements.

## The audit

Every leaf of the fenced block was enumerated and compared with every path the mapping names. The
comparison is mechanical:

* `source_items` names every item. Scalars inside `gps_telemetry` and `chat_logs` are named once with
  a wildcard selector, because the conversion carries every element of those arrays through one code
  path. `app_events` is named **event by event**, by its own `event_type`, because the conversion
  reads named events and a wildcard would hide one nobody read.
* `named_items` collects every path any mapping entry names, splitting an entry's `source` on commas
  because one value may be drawn from two places.
* `unrecorded_items` is the difference.

The source holds **86 items** and the mapping named **53** of them. **38 were named by nothing** —
28 of them fields of the ten app events, and ten others:

| item | why nothing named it |
|---|---|
| `app_events[*].details`, all ten events | the details text was never read |
| `app_events[*].event_type`, all ten | the type was used as a key, never recorded |
| `app_events[*].timestamp`, eight of ten | only two were carried as payload fields |
| `cancellation_policy.free_wait_time_min` | addressed in `policy_divergences`, never named |
| `cancellation_policy.cancellation_fee_after_wait` | same |
| `cancellation_policy.no_show_threshold_min` | same |
| `cancellation_policy.fee_goes_to` | same |
| `chat_logs[*].type` | used to separate message from call, never recorded |
| `rider_profile.fraud_flag_details` | quoted inside a reason, never named as a path |
| `driver_profile.name` | the rider's name was recorded as dropped; the driver's was not |
| `driver_profile.dispute_history.rejected` | same asymmetry |
| `trip_data.driver_wait_start` | used in the wait arithmetic, recorded as a source of nothing |
| `trip_data.scheduled_time` | quoted in a divergence, named nowhere |

## What was done with each

**The dropped record is carried, in the one place the schema has for it.** The corpus trip-record
payload has no free-text field — one key set, 35 keys, across all 29 cases — so there is no payload
field that could hold a sentence. The artifact's own admissibility notes are the faithful place: they
are prose about how the record was produced, and they already carried a derived claim about the
arrival marker. The source's sentence is now in them, **verbatim and labelled**:

> The source's own driver_arrived event reads 'Driver GPS within 10m of pickup point. Speed 0 km/h.
> Auto-arrival confirmed.': the marker was auto-confirmed from a GPS measurement, so under POL-GEN-02
> the marker and the trace are one carrier rather than two, and the ten-metre figure is the platform's
> distance claim rather than a reported horizontal accuracy, so no fix here is measurable under
> POL-NS-02 and none establishes arrival.

It did **not** become a GPS fix and did **not** become an `accuracy_m`. "Within 10m" is a distance the
platform reports between two things it measured; a reported horizontal accuracy is what a device says
about its own reading, and POL-NS-02 tests the second. Writing the first into the second would have
invented the very value that clause filters on, and would have made these fixes establish an arrival
the source does not support. The converted case still carries eight fixes, each with exactly
`lat`, `lng`, `speed_kph` and `ts`, and no accuracy. There is a test for each half.

**Everything else is recorded as read-and-not-carried or as dropped, with its reason.** The ten app
events get one entry each, so a reader can see where each went: the booking timestamp becomes
`requested_at`, the assignment timestamp becomes `accepted_at`, the call becomes
`in_app_calls[0]`, the fee event becomes `charged_at` and `cancellation_fee`, and the four events
with no field anywhere (`rider_notified`, the two timer events, `driver_released`) are dropped with
the reason stated. The source's policy block is recorded as dropped, each field pointing at the
divergence it belongs to. An app event type this converter has never seen is now **refused** rather
than dropped, so a source that grew an event cannot lose it quietly.

## The independence consequence

This is the part worth carrying forward. The source says the arrival marker was **auto-confirmed from
a GPS measurement**. So `trip_record.arrived_at` and the trace are the same measurement, and
POL-GEN-02's independence rule already governs them: *two records derived from the same measurement
are one carrier, not two*. The trip record's arrival marker cannot corroborate the trace, because it
is the trace.

That was true before this change and is now **stated in the case**, in the same notes paragraph. A
judge reading the marker as a second, independent carrier now has to read past a sentence that says
it is not one.

## The guard

`write_outputs` now calls `unrecorded_items` and **raises** rather than writing a mapping with a hole
in it. The check is at the write and not only in the suite, because a mapping that drops an item is
wrong the moment it is written.

`tests/test_external_case.py` gains `SourceCoverageTests`: the coverage check, a positive control on
the count so a broken walk cannot pass vacuously, a falsifiability check that removes every entry
naming the dropped path and requires the check to fire, a check that the writer refuses, and the
per-event and per-drop records. **The check is the converter's own function, not a second
implementation in the test** — a test that re-derived the answer could agree with a converter that
was wrong in the same way.

## A second defect the audit found

The trace's admissibility note said the source's intervals were such that **"three of the seven"**
exceeded POL-NS-08(b)'s 120 s limb. The intervals are 180, 240, 180, 120, 120, 180 and 180 seconds:
**five** exceed it, and `payload.gaps` held five. The note and the mapping's reason both carried the
typed figure, so the artifact contradicted itself.

This was not an item neither carried nor recorded, so it is not one of the two changes asked for; it
was found while auditing and is fixed here because leaving a false figure in a case artifact is worse
than not looking. Both counts are now derived from the same list of intervals, the note also states
how many fixes the waiting window holds (four, against the six that limb requires), and a test reads
the rendered artifact back to check that what the note says and what the payload carries agree.

The conclusion is unchanged either way — the trace was and is impaired for policy — so this is an
accuracy fix and not a change of outcome.

---

# Part 2 — the judge prompt: carrying a fact is not meeting a limb

> **Corrected by `docs/notes/2026-09-24-the-limb-procedure-revised.md`.** A read-only review of the
> amendment described here found wording that could move cases the answer key has right today, and
> wording that did not compel what this part claims for it. Four claims below are wrong: the 214
> walk credits the wrong phrase, the 112 walk credits a distinction that does not apply to that case
> because its trace is not impaired for policy under the route-deviation integrity limbs, the 107
> walk credits an admission exception that case does not need, and the 211 and 901 conclusions were
> not compelled by the text as committed. The text has since been revised and now runs as an ordered
> procedure. Everything else here — the converter work in Part 1, the digests, and the fact that
> Part 2's amendment was committed as `fb1af67` — stands.

## The defect

Step 2's "What can carry a deciding fact" was written on 2026-09-22 to stop the judge reading
"carrier" as instrument evidence only. It says a message can carry a fact, and bounds that with the
removal test. What it never said is that **carrying a fact is a different question from meeting a
limb**, and the run of the organisers' sample case read the silence as *yes*: the driver's own
messages — "I've arrived at the pickup point, I'm at the lobby area" — were taken as satisfying
POL-NS-01 limbs (b) and (c), on a trace where POL-NS-02 yields no qualifying fix at all, because no
fix carries a reported accuracy.

The clause names its own instrument. POL-NS-01(b) requires "the gps_trace places the driver inside
the pickup geofence", and (c) measures the dwell "from the first qualifying in-geofence GPS fix and
not from the 'arrived' event". A chat message is not that test, and nothing in POL-NS-01 says
anything may stand in for it. The prompt's carrier subsection is a **confidence-cap** rule; it never
said a limb could be met by something other than the thing its clause names.

## The three ways the draft was wrong

An independent read-only review tested a draft fix against all 29 answer-key rationales before
anything was written. The draft was wrong in three ways, and each is now a check:

1. **It said a message never records where anyone was.** That would have removed the two admissions
   that carry case 107 — the driver's "cte very jam tonight boss" and his counterparty statement
   admitting he routed by Newton and Kim Seng. So the amendment says an account is not a measurement
   *and* that an account decides a limb where it concedes against the speaker's own interest.
2. **It would have made case 211's failing reasoning a rule.** The failing run's words were "it says
   nothing about where he was, so it cannot carry that fact". A message that says nothing about
   position can still carry a fact for the cap; what it cannot do is satisfy a measurement test. The
   amendment separates those two sentences so the first cannot be read into the second.
3. **It treated a limb whose test could not be run as a failed limb.** That pushes impaired-trace
   no-show cases to FULL_REFUND, and it broke case 214, whose summing rule comes from a *different*
   clause (POL-NS-06(i)). So a limb's test is "including a test the clause takes from another clause",
   an untested limb is neither met nor failed, and — the converse, which is the harder half — a test
   that runs and finds nothing qualifying **has run**.

## What the amendment says

Seven principles. (a)–(e) and the bridging rule go into the Step 2 subsection, immediately before
"The escalation floor is the", which is where the section extraction stops; (f) is a correction to a
sentence already there; (g) goes into Step 3, beside `ruling.explanation`.

* **(a)** A limb is decided by the test its own clause states for it — an artifact, a measurement, or
  both, including a test the clause takes from another clause — and by that test alone, in either
  direction, unless the policy names what may stand in for it.
* **(b)** A party's message about where anyone was is that party's account, not a measurement: it may
  carry a fact for the cap, but it does not satisfy a limb whose test is a measurement. A status a
  party sets records only that the party set it; a record the platform generates is the platform's
  record. An account decides a limb only where it concedes against the speaker's own interest, or
  where the clause reads the log or the statement as its own test.
* **(c)** A limb whose stated test cannot be run is neither met nor failed — where the artifact is
  missing, or impaired for policy under the category's own integrity limbs rather than merely flagged
  by the pre-pass. Say so and apply what the policy says follows. A test that runs and finds nothing
  qualifying has run.
* **(d)** Bridging is not substituting. A contemporaneous record from inside a stretch the test left
  unobserved, lying between readings the test admitted, can carry the fact — for the cap and for any
  question about whether something is the only evidence. Where the test admitted no reading at all,
  an account offered in its place is standing in for the test.
* **(e)** A contradiction the policy names as its own ground for escalation stays a contradiction.
* **(f)** The sentence saying a counterparty statement's weight is its own `weight_multiplier` is
  corrected. It is not an artifact and sits in `case.dispute` rather than `case.evidence`: it is read
  as evidence, but it carries no `weight_multiplier`, so the cap is computed from the artifacts that
  carry the fact and this is not one of them. POL-RD-07(ii) names a `counterparty_statement` as
  independent corroboration, so it must stay readable; what it cannot be given is a weight field it
  does not have.
* **(g)** Every claim that survived Step 1 and would, if accepted, change the ruling, an amount, the
  driver's compensation or a referral is answered in `ruling.explanation` — accepted but outweighed,
  saying by what, or rejected, saying why. Claims on the same point are answered together. Rejecting
  a claim on its merits is not a Step 1 discard and does not go in `discarded_claims`. It adds no
  field.

### Where the bridging principle came from

It is not invented here. It is the answer key's own rationale for case 211, which reasons about the
same facts twice: the chat message sent from inside the outage carries the deciding fact, and *"on a
trace whose outage swallowed the whole dwell they are ESCALATE"*. The first is bridging; the second
is the absence of anything to bridge between. The principle is in the prompt; the case it came from
is not, and the prompt names no case at all.

## The constraints it was written under

* **A principle, not a checklist.** No case numbers, no figures, no place names, nothing naming the
  organisers' sample. The subsection is checked for all of those, and it contains **no digit at all**
  — the escalation floor is read from the loaded policy and restating it here is the failure the
  check exists for.
* **Placed before "The escalation floor is the".** The existing section extraction stops at that
  sentence, so text after it would be outside the subsection the checks read.
* **Words added: 383.** 321 in the carrier subsection (306 → 627 words) and 62 in Step 3 (183 → 245).
  Of the 321, 38 are the (f) correction to a sentence that was already there; the five new paragraphs
  are 283 words for six principles. The file goes from 1 177 to 1 560 words.

## The checks

`carrier_section` now collapses whitespace the way `referral_section` does, so a re-wrapped line is
not read as a change of instruction. `DecidingFactCarrierTests` gains nine checks: a positive check
for each of (a)–(f), the no-digit check, the sample-term check, and the whitespace check. A new class,
`ExplanationAnswersTheSurvivingClaimsTests`, reads the Step 3 section and checks (g) — including that
the instruction *follows* the `ruling.explanation` bullet it is about, and that it adds no field.

Every one of the sixteen new assertions was run against the pre-amendment prompt and fires on it.

`tests/test_pipeline.py` now counts **four** text checks rather than three, and both docstrings that
counted them say so.

---

# The eight cases, read through the amended text

Read by reading only. No model was called, nothing was scored, and the seven corpus cases are
statements about what the amended text should now produce — not measurements of what any run
produces. **Case 901 has no answer-key entry and none may be created**: what follows for it is a
reading of this repository's policy, and it is not a grade.

## 107 — ROUTE_DEVIATION, PARTIAL_REFUND 7.45. **Unchanged, and now reachable.**

`EV-GPS-00107` is impaired at 0.30 on `GPS_DRIFT` and `IMPLAUSIBLE_SPEED`, but **not** impaired for
policy: POL-RD-07's limbs are a gap over 90 s, a jump over 500 m and a sustained interval over 30 s,
and the record shows max_gap 0, a maximum jump of 331.8 m and a 10.0 s median. That is exactly (c)'s
"merely flagged by the pre-pass" — the trace is down-weighted under POL-GEN-02 and its test still
runs.

POL-RD-08's serial-claimant test then requires corroboration beyond the trace. Under (b) it exists:
"cte very jam tonight boss" concedes the driver did not take the CTE the optimal route uses, which is
a concession against the speaker's own interest, and his counterparty statement admits the route by
name. Under (f) the statement is read as evidence while contributing no weight of its own, so the cap
is the chat artifact's 1.00 and clears the floor. Before the correction a judge following the old
sentence would have looked for a `weight_multiplier` the statement does not have.

## 108 — ROUTE_DEVIATION, NO_ACTION. **Unchanged, and now protected.**

The trap is reading `deviation_pct` off the trip record and stopping. POL-RD-05 re-applies POL-RD-01
against `amended_optimal_distance_km` and `amended_optimal_duration_min`, and says in terms that the
Judge "must not derive a substitute figure". (a) is the sentence that holds: a limb is decided by the
test its own clause states for it, and by that test alone, in either direction, unless the policy
names what may stand in for it. POL-RD-05 names those two fields and nothing else. Against 24.60 km
the excess is 1.57 km, below the 20 % limb, and no deviation survives.

The rider's own message and the driver's acknowledgement corroborate the amendment, but they are not
what decides it: the amendment is recorded on the trip record, which is the platform's record and the
artifact POL-RD-05 reads. That is (b)'s second half, and it is why the clause's own test governs.

## 110 — ROUTE_DEVIATION, ESCALATE. **Unchanged, and the amendment is what keeps it there.**

The trace has a 428 s dropout covering exactly the segment in dispute — over POL-RD-07's 90 s limb, so
impaired for policy. POL-RD-07(ii) then requires corroboration from a named list, and the list is
empty: the fare ledger bills 21.20 km, the trace figure, which that limb expressly excludes as a copy
rather than a second measurement; `erp_gantries` is null; the chat is `TRUNCATED_LOG` at 0.60 with no
driver admission; and the counterparty statement asserts the KPE without conceding any route detail.

(d) is what stops the chat bridging: it requires a record *from inside* the stretch the test left
unobserved and *between readings the test admitted*. The bounding fixes admit two routes of 6.90 km
and 11.2 km and nothing in the bundle chooses between them, so the stretch is unbridged. (b) is what
stops the statement deciding: it concedes nothing, so it stays an account. And (c)'s second half is
what stops the empty corroboration list being read as "the test could not run" — POL-RD-07(ii)'s test
ran and found nothing, and POL-RD-07(iii) makes that ESCALATE rather than NO_ACTION.

## 112 — ROUTE_DEVIATION, ESCALATE. **Unchanged, and (e) is why.**

Two POL-RD-10 triggers fire and either alone is terminal. POL-RD-10(4): `started_at` 18:32:10 against
`first_fix_at` 18:18:40, a disagreement of 13 m 30 s on when the trip began, over the clause's 10 m
limb — and it decides the case, because across the whole trace the excess is 27.3 % and from
`started_at` only it is 13.8 %. POL-RD-10(7): the chat request and the driver's statement on one
side, the trace on the other, both admissible, directly contradictory on a material fact, and no
clause resolves it.

(e) says in as many words that the amendment does not resolve it. POL-RD-10(7) names that fact
pattern as its own ground for escalation, and a rule that let an account decide the limb would
dissolve the contradiction the clause exists to send to a human. POL-RD-04 cannot be run either way
for the same reason — its corroboration limb needs the trace to place the vehicle within 200 m of the
waypoint, and the trace is the artifact whose alignment is in dispute — which is (c)'s first half.

## 211 — NO_SHOW_CHARGE, PARTIAL_REFUND 2.00. **Unchanged, and (b), (c) and (d) together are what produce it.**

The trace holds the driver inside the 50 m radius across thirty-five qualifying fixes — and 168
seconds of it were never observed, an outage from 12:33:40 to 12:36:28 that is inside the waiting
window and over POL-NS-08(b)'s 120 s limb. So the trace is impaired for policy, and (c) applies: the
dwell limb is **neither met nor failed**, and what the policy says follows is POL-NS-08's own cap
sentence and its prohibition on resolving the gap either way on this artifact alone.

(d) then decides the cap. `MSG-00211-004` was sent by the driver at 12:35:10 **from inside the
outage** and read at 12:35:26 — a contemporaneous record from inside the stretch the test left
unobserved, lying between readings the test admitted. It bridges, so it carries the fact, the cap is
the MAXIMUM of the two weights rather than the minimum, 0.72 clears the 0.70 floor and POL-NS-09(a)
does not fire.

And (b) is what keeps the answer honest: the message is the driver's account and does not satisfy a
measurement, so it cannot show **where** he was standing. The limb stays neither met nor failed and
the outcome is the split — PARTIAL_REFUND of 2.00 of the 4.00, no driver compensation. Remove (b) and
this case reads as NO_ACTION with 3.20 to the driver; remove (d) and it reads as ESCALATE. The
amendment has to carry both.

## 212 — NO_SHOW_CHARGE, FULL_REFUND 4.00. **Unchanged, and (c)'s last sentence is why.**

`EV-GPS-00212` is COMPLETE: no gap, no drift, no skew, 100 % coverage, every schema detector silent.
Its impairment is not a defect at all — every in-radius fix reports 44.7 m to 77.2 m horizontal
accuracy, and POL-NS-02 says fixes worse than 25 m "are ignored for this test and count as evidence of
neither presence nor absence". Filter as the clause requires and the position inverts: the closest
admissible fix is 147.8 m from the pin.

So the test **runs**, and finds nothing qualifying. That is (c)'s last sentence — *a test that runs and
finds nothing qualifying has run* — and it is the half the draft got wrong. Treat this as untested and
the limb is neither met nor failed, and a fee stands on a record that establishes nothing. It is the
case that shows (c) needs both halves: the first half keeps case 211's gap open, the second closes
case 212's.

## 214 — NO_SHOW_CHARGE, DRIVER_COMPENSATION 3.20. **Unchanged, and (a) is why.**

POL-NS-01(c) needs a 300 s dwell. The driver's longest continuous hold is 185 s, 115 short. POL-NS-06
would refund in full — except limb (i) permits separate in-geofence intervals to be summed where a
present, populated advisory records a kerb restriction, and `EV-ADVIS-00214-01` is COMPLETE with type
`KERB_RESTRICTION`, geometry covering the route and window overlapping. Summed, the two holds give
355 s and no shortfall exists.

That summing rule is POL-NS-06(i), not POL-NS-01(c). (a) is the phrase that keeps it: *including a
test the clause takes from another clause*. A rule that said only a limb's own clause decides it would
have refused the summing and refunded the fee — which is the third way the draft was wrong. (d) is
here too: `MSG-00214-004` at 18:47:50, sent from inside the loop between the two observed holds,
records in the moment that the marshal was moving him on.

## 901 — the converted sample case. **It should now escalate, and the committed run says PARTIAL_REFUND.**

No answer-key entry exists for this case and none may be created. What follows is a reading of
`policy/` against the converted case as it now stands.

No fix in the converted trace carries a reported accuracy — and none is invented. Under POL-NS-02
every one of them is therefore evidence of neither presence nor absence, so **no fix qualifies** and
the test admits no reading at all. The trace is also impaired for policy under POL-NS-08(b) on two
limbs of its own: one interval inside the waiting window exceeds 120 s, and the window holds four
fixes against the six that limb requires. It omits the rider track as well.

The judge took the driver's messages — "I've arrived at the pickup point, I'm at the lobby area" — as
satisfying POL-NS-01 limbs (b) and (c). Under the amended text they cannot. (b): a party's message
about where anyone was is that party's account, not a measurement, and it does not satisfy a limb
whose test is a measurement; the message is not a concession against the speaker's own interest — it
asserts the very thing he wants established — and POL-NS-01 does not read the chat log as its own
test. (a): POL-NS-01(b) names the gps_trace and (c) measures from "the first qualifying in-geofence
GPS fix", and nothing in the policy says anything may stand in for either.

(d) is the sentence that names what happened: where the test admitted **no reading at all**, an
account offered in its place is standing in for the test rather than bridging it. The messages are
not a record from inside an unobserved stretch between admitted readings; there are no admitted
readings for them to lie between.

What follows is what the policy says follows. The deciding fact's only evidence is a trace impaired
under POL-NS-08(b), so that clause's own cap sentence applies — the ruling may not exceed
PARTIAL_REFUND and the case escalates under POL-NS-09 — and POL-NS-09(e) makes the escalation
terminal, with the disputed fee held rather than collected or refunded. The trip record's arrival
marker does not help the driver here, and the converted case now says so in its own notes: it was
auto-confirmed from the same GPS measurement as the trace, so under POL-GEN-02 it is one carrier and
not two.

**So the reading is ESCALATE, no money, fee held.** The committed run produced PARTIAL_REFUND of 1.00
with compensation of 3.20 and confidence 0.75. That run is the record of what the system did before
either change, and it is not rewritten.

---

# What this invalidates

The prompts digest moved, so **all 29 cached corpus results are now stale on the prompt channel**.
They are not merely unchecked: each records the previous digest and the check compares it.

```
b131e63f046aecc68471631df8c04f9e0fde88d3383775028f8da058474bc3d3   prompts, before
8375d2bbf4f156c3308b5d61f9d4ce22130cdb7fd4a999e550d3220152e5b93a   prompts, after

b43bdac98dd56b520e70bc8594dd12f8754a6dc1b0799f3d58220303450b4310   judge.system.md, before
d89552d0af411e1b89cdf1c65ab66e3830032832369e39ff7a2ac3d32ac1d4c4   judge.system.md, after
```

Their briefs are untouched — no corpus case file was edited — so the corpus results read `STALE
(prompt)` and not `STALE (brief)`.

**Case 901 is stale on both channels, and the brief half of that cannot be seen by the usual
check.** Its recorded `brief_sha256` no longer matches the brief this repository now builds for it,
because the converted case gained the auto-arrival paragraph and the corrected gap count:

```
89e812ae8bde5a34fa05fea04098f399551e31a07446f8dc287fb7bdcb4426cd   brief_sha256, as recorded by the run
db5b6b955954b4d814053ab13f94e3f37d3de23084dd1f7b4ace7556838b979d   brief_sha256, as rebuilt now
```

`BriefStaleness` reports only the prompt channel for it, and that is a limit of the instrument rather
than a fact about the case: it rebuilds *corpus* briefs by case number, and 901 is not a corpus case,
so `current_brief_sha256(901)` returns `None` and the brief half reads `unknown`. The brief move is
recorded here by measuring the rebuilt external brief directly. A reader should not take the tool's
`unknown` for "unmoved".

**This is expected.** It is what the two-channel design is for: the prompt channel exists so that
editing what the agents are told cannot leave cached results reporting as current, and the brief
channel so that changing the facts cannot either. Every cached result is now a measurement made under
instructions that have since changed, which is exactly what a re-run is for.

Converted-case digests, so a reader can tell whether the case in front of them is this one:

```
eval/external/ryde/convert.py        c887ec8041605d98fa4d410c59bd3c94028db1adc4b64c689f70e5b24140d717
data/external/ryde/case-00901.json   53bb999d9190e5a5c194c4f7d6ccd5405eed2b5de1e0895b3aa43a5347adda2b
data/external/ryde/mapping.json      2d6964f3ebab381e606d5e6da4328a29b96593111e11ab44f77b5efd06c92197
eval/external/ryde/expected.json     f4b93ccff494a8909650585ca65dec9982d511012a64948714b9b872c287d9d4  (unchanged)
```

The mapping record now holds 263 entries — 78 copied, 185 judged — up from 243, the 20 added being
the per-event audit and the drop records.

# What was not done

* **No model call, and nothing re-run.** `runs/external/ryde/` is untouched, and the transcript still
  re-hashes to the digest recorded when it was committed.
* **No cached result was deleted, moved or rewritten.** The 29 are real measurements; what changed is
  what they are measurements *of*.
* **No answer-key entry was created for case 901**, and `eval/answers/ground_truth.json` still holds
  29 records. The organisers' stated outcome stays under `eval/`, in `expected.json`, where it was.
* **No corpus case file and no policy file was edited.** The converted case is under `data/external/`,
  which is not in `data/index.json`.
* **The viewer was not rebuilt.** `ui/build.py` renders the corpus runs and the two advocate system
  prompts, none of which moved; `python -m ui.build --check` reports the committed page identical to a
  fresh build, and the committed bytes are unchanged.
* **The untracked suite logs under `runs/` were not committed**, as before.

# Verification

* **The coverage check is falsifiable.** With every entry naming `app_events[driver_arrived].details`
  removed, `unrecorded_items` reports it; with the real mapping it reports nothing. The walk is
  pinned to 86 items so a walk that found nothing cannot pass.
* **The writer refuses.** A mapping with an empty `fields` list makes `write_outputs` raise before it
  creates the output directory, so the test writes nothing.
* **The carried text is the source's own.** The test asserts the source's `details` string is in the
  trip record's notes, rather than asserting a paraphrase.
* **The claim did not become evidence.** The point count still equals the source's fix count and no
  point carries an `accuracy_m`.
* **The counts agree.** The note's fraction and `payload.gaps` are read back off the rendered case and
  compared.
* **Every new prompt assertion was run against the pre-amendment prompt and fires on it**, sentence
  by sentence rather than by trusting that the phrase was new.
* **The prompt contract holds for every agent after the edit**: one ```` ```json ```` example per
  prompt, the example parses, and the shape it asks for is one the request permits, asserted for all
  three roles.
* **The conversion is idempotent** and leaves the corpus, the manifest and the answer key
  byte-identical.
* Full suite: **796 tests, OK (skipped=3)**, up from 765 — 31 new checks, 14 of them on the converter
  and its record and 17 over the prompt.
* No network, no credential, no model call, in any of the above.
