# The limb procedure, revised

**A read-only review of the amendment committed as `fb1af67` applied it to all 29 corpus cases and
to case 901 as a literal-minded small model would read it. It found wording that could move cases
the answer key has right today, and wording that did not compel what the previous note claimed for
it. This note records the revision, corrects the four errors that review named, and re-walks eleven
cases through the revised text by reading alone. No model call was made and nothing was re-run.**

| | |
|---|---|
| Prompt file | `prompts/v1/judge.system.md` |
| File digest, before | `d89552d0af411e1b89cdf1c65ab66e3830032832369e39ff7a2ac3d32ac1d4c4` |
| File digest, after | `6d15627eebdab00f42c3a19aaf958af179432485f558cda08dc3879ea70ee67f` |
| Prompts digest, before | `8375d2bbf4f156c3308b5d61f9d4ce22130cdb7fd4a999e550d3220152e5b93a` |
| Prompts digest, after | `eece65ee58ab78de1ace84079e63c8a4de3bb63e3f4b2adc12b7a2a3d8bd6397` |
| Carrier subsection | 627 → 840 words |
| **Words added against `fb1af67`** | **213** |
| Step 3 | unchanged; the `(g)` paragraph stands as committed |

The previous note is `docs/notes/2026-09-24-meeting-a-limb-and-the-dropped-record.md`. It carries a
pointer to this one at the head of Part 2; nothing else in it was rewritten, because a dated note is
a record of what a session did and correcting it in place would destroy the evidence that it was
wrong.

---

# Why the shape changed

The committed amendment was five paragraphs of principle. Every one of the eight findings is the
same failure in a different place: a sentence that is **true of the confidence cap** was read as a
rule about **the limb**. "It may carry a fact for the cap" was read as "it may carry the limb". "The
test has not run" was read as "the limb is not met". "Stays a contradiction" was read as "no clause
may resolve it".

A paragraph cannot easily say which of the two questions it is answering at each clause. So the
amendment is now a short **ordered procedure per limb**: identify the test; ask whether the part of
the artifact the test reads is impaired over the stretch the defect covers; if not, the result
decides; if so, the limb is undecided and moves no money either way. The rules that are not about
the limb — accounts, bridging, contradictions, the counterparty statement — follow it as separate
paragraphs, so that no one of them can be read as a step in the procedure.

# The revised text

> **Deciding a limb is not carrying a fact.** A limb is decided by the test its own clause states
> for it, and by that test alone, in either direction. That test is the artifact it reads and the
> measurement it requires, plus any rule another clause gives about that limb — where the
> measurement starts, whether separate stretches are summed, how an early or false arrival marker is
> treated, and what follows from the result. Run it in that order:
>
> - **Is what the test reads impaired over the stretch the defect covers?** Absent is the limiting
>   case. Impaired means under the category's own integrity limbs, not merely flagged by the
>   pre-pass. Readings outside that stretch are still admitted — admitted meaning they passed the
>   clause's own filters, not merely that the artifact recorded them.
> - **If it is not impaired, the result decides, in either direction.** A test that runs and finds
>   nothing qualifying has run, unless its own clause makes that result undecidable.
> - **If it is impaired, the limb is undecided over that stretch.** An undecided limb supports
>   neither a payment that needs the clause to hold nor a refund that needs it to fail: say so, and
>   apply what the integrity and escalation clauses give for uncertainty, including how they say an
>   impaired stretch is read.
> - **An exculpatory clause invoked with nothing behind it is not an untested limb.** An assertion
>   citing no evidence is discarded under the clause that places the burden; a clause invoked
>   against an artifact that is absent escalates on that clause's own terms.

The paragraphs that follow it in the prompt, and that are not part of the procedure, are the account
rule (a message about position is an account, not a measurement; a status a party sets records only
that the party set it; either decides a limb where the clause reads it as its test; an account
decides a limb only where the clause reads the log or statement as its own test, or the policy names
it as what may stand in), the bridging rule, the contradiction rule, and the counterparty statement.

---

# The eight findings, and what confirms each

Each was checked against the policy files, the answer key and the case data before anything was
changed. None was found wrong; one earlier claim of this repository's own was.

| # | The finding | What confirms it |
|---|---|---|
| 1 | "Neither met nor failed … apply what the policy says follows" sends a literal reader to the conjunctive clause, whose unmet limb means the fee is not chargeable, so an untested limb becomes a full refund. And "a test that runs and finds nothing qualifying has run" collides with impaired traces that still return readings. | POL-NS-01 reads "ONLY IF all four conditions hold" and "Where any of (a) to (d) fails, the fee is not chargeable". Case 211 is the case it moves: the key has PARTIAL_REFUND 2.00, and the committed text reaches 4.00. |
| 2 | "It may carry a fact for the cap" still lets a driver's own messages lift the cap where the test admitted no reading, which defeats the clause that makes an impaired trace the only evidence. | POL-NS-08's closing sentence and POL-NS-09(e); the converted case 901, whose trace is impaired under POL-NS-08(b) and none of whose fixes carries `accuracy_m`. |
| 3 | "A test the clause takes from another clause" runs the wrong way: the rule that qualifies a dwell is a rule about **counting**, not a borrowed test. | POL-NS-06(i) permits separate in-geofence intervals to be summed; POL-NS-01(c) measures from the first qualifying fix and not from the arrival event. Case 214 is correct today and would move. |
| 4 | "An account decides a limb only where it concedes against the speaker's own interest" lets an admission replace a measured test. | POL-NS-02 is written "only where"; POL-RD-07(ii) names a driver admission in the chat_log and a counterparty statement admitting the route as corroboration — the policy naming them is what case 107 needs, not the interest exception. |
| 5 | "Where the artifact is missing … the test has not run" turns a driver's uncited traffic excuse into an untested limb, and then into an escalation. | POL-RD-08: "a general assertion that traffic was bad, unsupported by a traffic_advisory ID, does not discharge it"; "Assertions from either side that cite no evidence ID carry no weight and are discarded." The key for 105 and 114 says discarded, and 102 warns in terms that invoking a clause against a MISSING artifact forces escalation and would cost the driver a case he wins on the distance test alone. |
| 6 | "Stays a contradiction" is unqualified, and can block a clause that resolves the conflict. | POL-NS-09(b) itself asks "and no clause resolves the conflict". POL-NS-05 resolves 201 and 209 by recomputing the clock; POL-RD-04 cannot resolve 112 because the trace it would test is the artifact in dispute. |
| 7 | "This is not one of them" reads as "the statement does not carry the fact". | POL-RD-07(ii) names a counterparty statement as independent corroboration, so it is evidence; it has no `weight_multiplier`, so it can enter neither the minimum nor the maximum of the cap. |
| 8 | The status sentence, read alone, can make an arrival tap and a reason code look unproven. | POL-NS-01(a) reads the arrived event and (d) reads the cancellation reason code: they are exactly what those two limbs read. |

# The four errors in the earlier note

1. **214 credited the wrong phrase.** That note said `(a)`'s "a test the clause takes from another
   clause" was what carries 214. It is not. What carries 214 is a counting rule in another clause,
   and the phrase as written invites the opposite reading. Corrected in the revised text.
2. **112 credited the first half of `(c)`, which does not apply to it.** That note said the
   distinction "impaired for policy under the category's own integrity limbs rather than merely
   flagged by the pre-pass" was what produced 112's escalation. Checked against the artifact:
   `EV-GPS-00112` is `IMPAIRED` with `CROSS_SOURCE_CONFLICT` at 0.40, `max_gap_sec` is 0.0, coverage
   is 100%, and its own notes read "The trace is otherwise clean: no gap, 100% coverage of the
   recorded trip window, speed varying plausibly by road class. The defect is entirely one of
   alignment with the trip record." POL-RD-07's limbs are a gap, a jump and a sustained interval, so
   none is met, and POL-RD-07 says of exactly such an artifact that it "does not trigger the
   consequences below or POL-RD-10(3)". 112 escalates on POL-RD-10(4), (7) and (1). **The review is
   right and the earlier note was wrong.** The distinction is real and load-bearing — case 206 turns
   on it in the same direction — but it is not what decides 112.
3. **107 does not need the admission exception.** What it needs is that the policy names the two
   things it relies on. POL-RD-07(ii) and POL-RD-08's serial-claimant limb both draw on a list that
   contains a driver admission in the chat_log and a counterparty statement admitting the route, and
   107 has both. The exception was never the mechanism, and it is now gone.
4. **The 211 and 901 conclusions were not compelled by the committed text.** 211 was reachable but
   not compelled: the same sentence that produces the split also licenses a full refund. 901's
   escalation was not compelled at all: the sentence that caps at PARTIAL_REFUND left the driver's
   own messages free to lift the cap. Both are now compelled, and the walk below says how.

---

# The eleven cases, read through the revised text

Read by hand, from the clause text and the answer key. "Unchanged" means the revised text reaches
the key's own outcome; it does not mean nothing moved, because in three of these the committed text
did not compel what the key requires.

## 102 — ROUTE_DEVIATION, NO_ACTION. **Unchanged, and the fourth step is what keeps it there.**

21.79 km against a 20.40 km optimal is 1.39 km and 6.8%, which clears the absolute limb and not the
proportional one, so no deviation is established and the burden never shifts. The driver's
congestion defence cites no advisory and `EV-ADVIS-00102-01` is MISSING. The committed text's "where
the artifact is missing … the test has not run" makes the exoneration test untested rather than
discarded, and an untested exculpatory clause is a route to escalation on a case the driver wins on
the distance test alone — which is the error the key names in terms. The revised fourth step says an
exculpatory clause invoked with nothing behind it is not an untested limb and an assertion citing no
evidence is discarded under the clause that places the burden. Discarded; NO_ACTION stands.

## 105 — ROUTE_DEVIATION, FULL_REFUND 65.13. **Unchanged.**

18.16 km and 50.4% is material, so the profile check is compelled. The defence is a bare assertion
citing no advisory and the advisory is MISSING, so under POL-RD-08 it is discarded — the same
mechanism as 102, and the same step of the revised text keeps it a discarded assertion rather than
an undecided limb. POL-RD-06(b) then upgrades a material, this-trip-substantiated deviation to a
full refund of the charged total, and POL-RD-06(c) adds the conduct referral alongside the money.

## 107 — ROUTE_DEVIATION, PARTIAL_REFUND 7.45. **Unchanged, and the policy naming the account is why.**

The trace is schema-IMPAIRED at 0.30 but not impaired for policy: `max_gap_sec` is 0, the largest
jump is 331.8 m against a 500 m limb, and the median interval is 10.0 s, so POL-RD-10(3) does not
fire. The corroboration requirement comes from POL-RD-08's serial-claimant limb, which draws on the
same list as POL-RD-07(ii): a driver admission in the chat_log, the charged gantries, a counterparty
statement admitting the route, or an independently derived distance. The driver's message conceding
he did not take the motorway the optimal route uses and his counterparty statement admitting the
routing are both on that list. The revised account rule decides the limb because **the policy names
it as what may stand in** — which is the whole of the correction here. The billed distance is
excluded as a copy of the trace, exactly as the limb says.

## 112 — ROUTE_DEVIATION, ESCALATE. **Unchanged, and its trace is not impaired for policy at all.**

Three triggers, any one terminal. The timestamps disagree by thirteen and a half minutes on when the
trip began, over the ten-minute limb, and that decides the case: 27.3% over the whole trace against
13.8% measured from the recorded start. The chat and the counterparty statement put a stop on the
route that the trace never approaches, both admissible and directly contradictory. And the cap is
0.40 on two artifacts naming each other, below the floor on its own. POL-RD-04 cannot resolve the
contradiction in either direction, because its corroboration limb needs the trace whose alignment is
the thing in dispute — which is what the revised contradiction step asks for when it says to answer
from the clause. The contradiction stays; the case escalates; the disputed amount is held.

## 114 — ROUTE_DEVIATION, PARTIAL_REFUND 13.70. **Unchanged.**

5.97 km and 33.2% is established and not material, so POL-RD-06 is not compelled. The congestion
defence cites no advisory and the advisory is MISSING, so POL-RD-08 discards it rather than
escalating it. The arithmetic is then untouched by the amendment: the surge is read from the fare
breakdown and not the trip record, and only the gantry lying on the optimal route enters the
recomputed fare, the other being already inside the refund and never added on top.

## 201 — NO_SHOW_CHARGE, FULL_REFUND 4.00, plus a false-arrival referral. **Unchanged.**

The trace is complete and the driver never comes closer than 779.9 m to a 50 m radius, so no
qualifying in-radius fix exists anywhere in the window, the proximity limb fails, and the fee is not
chargeable. The second route reaches the same place: the marker matches a fix 779.9 m away, over the
false-marker trigger, and with no qualifying fix anywhere the clause refunds in full and records the
false arrival against the driver. The driver's own account of having arrived is contradicted by a
complete artifact, so the measurement test runs and decides — the revised step two, in the direction
that goes against the party whose account it was. And the contradiction is resolved by a clause, so
the revised contradiction step's exception applies: the ground itself asks whether a clause resolves
the conflict, and this one does.

## 202 — NO_SHOW_CHARGE, DRIVER_COMPENSATION 4.80. **Unchanged, and the exception in step two is why.**

All four limbs are met on a complete trace, the dwell being measured from the first qualifying
in-geofence fix rather than from the tap. The rider-exonerating clause fails at its first limb for
the simple reason that the rider sent no message. Its third limb is UNDECIDABLE rather than failed,
because every rider-track fix reports 45 m to 80 m and is filtered out by the accuracy rule, which
that clause expressly makes neutral rather than adverse. The revised step two ends "unless its own
clause makes that result undecidable", and this is that clause. So the limb is undecided, moves no
money, the exonerating clause does not apply, and the fee stands with the compensation attached.

## 211 — NO_SHOW_CHARGE, PARTIAL_REFUND 2.00. **Unchanged, and the revised text is what produces it.**

The sampling outage runs inside the waiting window and over the 120 s limb, so the trace is impaired
for policy at 0.39 and not merely tagged. **Under the committed text this case moves to 4.00**: "the
test has not run" makes the dwell limb neither met nor failed, the anchor clause needs all four
conditions to hold, an unmet limb means the fee is not chargeable, and the shortfall clause refunds
in full. Under the revised text the impairment is judged over the stretch the defect covers, which
is the outage; the readings outside it are still admitted, and they are two runs of 220 and 112
seconds, neither of them the minimum; so the limb is undecided over that stretch and moves no money
either way. The only-evidence question is then answered by the bridging rule: the chat log at weight
1.00 holds a message sent by the driver **from inside the outage**, which is a contemporaneous record
from inside a stretch the test left unobserved lying between readings the test admitted, so it counts
for the cap and the impaired trace is not the only evidence. POL-NS-09(e) does not fire, the cap is
the maximum of the two weights, and confidence clears the floor. What is left is the split the
integrity clause's own notes describe: genuine uncertainty rather than a finding against either
party. PARTIAL_REFUND 2.00.

## 212 — NO_SHOW_CHARGE, FULL_REFUND 4.00. **Unchanged, and the "has run" sentence is why.**

The trace is complete, every schema detector is silent and nothing is down-weighted. The test runs
and finds nothing qualifying: every in-radius fix reports 44.7 m to 77.2 m and is ignored, and the
only admissible fixes on the trace are the approach fixes at 6.0 m to 14.0 m, the closest of them
147.8 m from the pin. So the proximity limb fails on the clause's own arithmetic and the fee is
refunded in full. The revised text's "a test that runs and finds nothing qualifying has run" is
exactly this, and "admitted meaning they passed the clause's own filters, not merely that the
artifact recorded them" is what stops the naive nearest-fix reading that would have given the driver
the case.

## 214 — NO_SHOW_CHARGE, DRIVER_COMPENSATION 3.20. **Unchanged, and the counting-rule wording is what protects it.**

Two stationary holds of 170 and 185 seconds, the longest continuous one 115 short of the minimum.
The summing rule in the shortfall clause permits them to be added, and every condition for it is on
the record: a present, populated advisory of the kerb-restriction type whose geometry contains the
trace and whose window covers the trip, and a driver who left and re-entered without exceeding the
300 m leash. Summed they give 355 seconds, no shortfall exists, all four limbs hold, and the
compensation clause pays. **Under the committed text this case is at risk**: "a test the clause takes
from another clause" invites the reading that the dwell limb borrows its test from the summing
clause, so an absent advisory would make the limb's test un-runnable rather than merely unsummable.
The revised text says the rule is about counting — where the measurement starts, whether separate
stretches are summed, how an early or false arrival marker is treated — which is what it is. And the
rider advocate's argument that the driver's own admission that he left decides the limb against him
no longer has anything to stand on: the interest exception is gone, and the clause does not read the
log as the dwell test.

## 901 — the converted sample case. **ESCALATE, with the fee held. No answer key exists, and none was created.**

The trace is impaired for policy under the no-show category's own integrity limbs: its notes record
five of seven intervals over the 120 s gap limb, four fixes in the waiting window against the six
that limb requires, and the absent rider-track limb as well. No fix carries `accuracy_m`, so under
the proximity clause every one of them is evidence of neither presence nor absence. The test
therefore **admitted no reading at all**.

That is the whole of the difference from the committed run. Under the committed text the driver's own
messages could still lift the cap, because the account rule said an account "may carry a fact for the
cap" and the bridging sentence spoke only to the limb. Under the revised text, where the test admitted
no reading at all, an account offered in its place is standing in for the test: it neither lifts the
cap nor stops the impaired artifact being the only evidence. So the deciding fact's only evidence is
the impaired trace, which is exactly the state the integrity clause's closing sentence describes —
the ruling may not exceed a partial refund **and** the case escalates — and escalation is terminal,
so no monetary ruling issues and the fee is held rather than collected or refunded.

The committed run at `b2556e8` says PARTIAL_REFUND 1.00, compensation 3.20, confidence 0.75. That is
the cap without the escalation the same sentence orders. The run is untouched and still reads as it
was produced; it is the record of what the system did before any of this was changed.

---

# What this invalidates

- **All 29 cached corpus results are stale on the prompt channel, for the second session running.**
  The prompts digest moved from `8375d2bb…` to `eece65ee…`, and every one of the 29 recorded
  `b131e63f…`. This is expected and is the point of recording the digest: the instructions changed,
  so the measurements no longer belong to this code.
- **Case 901 is stale on both channels.** The converted case gained the source's own account of how
  the arrival marker was made, so its brief moved; and the prompt moved. `current_brief_sha256(901)`
  is `None`, because the staleness report rebuilds *corpus* briefs by case number and 901 is not a
  corpus case — so the report sees only the prompt half and reads `unknown` for the brief half, which
  is "cannot tell" and not "unmoved".
- **The viewer needed no rebuild, and that was checked rather than assumed.** The page reads
  `prompts_sha256` out of each cached run's own provenance and records the prompts *directory*; it
  does not embed the digest of the prompt bytes, so editing a prompt does not move it. Rebuilding it
  produced a byte-identical file, and `python -m ui.build --check` reports the committed page
  identical to a fresh build.

# What was not done

- No model call, and no case re-run. `runs/external/ryde/` is untouched.
- Step 3's `(g)` paragraph is unchanged. Nothing in the eight findings required it: the contradiction
  step now carries the qualifier, so the requirement that the explanation answer every surviving
  claim already lands where it should.
- No answer-key entry was created for case 901, and none may be.

# Verification

The two text-check classes were run on their own first, because they are the ones the edit is aimed
at:

    python -m unittest tests.test_pipeline.DecidingFactCarrierTests \
        tests.test_pipeline.ExplanationAnswersTheSurvivingClaimsTests
    Ran 35 tests in 0.013s

    OK

`DecidingFactCarrierTests` now holds 27 checks against 20 before: the second-amendment block went
from six methods to thirteen and lost none. Every assertion string was verified against the rendered
section before the checks were written, so that a check cannot pass by asserting a sentence that is
not there; and the four sentences the review found defective are asserted **absent**, so a later edit
cannot put one back unnoticed.

The full suite, unedited, is in the session log under `runs/`. No file entered `runs/` before the
credential scan.
