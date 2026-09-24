# Removing the account sentence, and the freeze

**2026-09-24.** One change, to `prompts/v1/judge.system.md`, and nothing else. No model was called and
nothing was re-run: this note is a text edit plus a reading of it.

## 1. The change

**Removed**, verbatim, from the Step 2 carrier subsection:

> A party's message about where anyone was is that party's account, not a measurement: it may carry a
> fact for the cap, but it does not satisfy a limb whose test is a measurement.

**Added:** nothing. **Words removed: 34. Words added: 0.**

| | before | after |
|---|---|---|
| `prompts/v1/judge.system.md` | `6d15627eebdab00f42c3a19aaf958af179432485f558cda08dc3879ea70ee67f` | `8eee6472c31e62eef627dbbf500f8fd6d0af701cc6e93b615443a8cb08fd2443` |
| prompts directory | `eece65ee58ab78de1ace84079e63c8a4de3bb63e3f4b2adc12b7a2a3d8bd6397` | `829ccc8fe999b809be7d9fbbaaa70694aa9377f9f42f753f678bae9f29bae512` |

The rest of the paragraph is re-wrapped and its words are untouched. `git diff --numstat` reads `4 6`:
four lines added, six removed, all of it this sentence and the wrapping it leaves behind.

**Why it goes.** The sentence said two things, and neither one earns its place. The second — that an
account does not satisfy a limb whose test is a measurement — is what the sentence after it already
says: *"an account decides a limb only where the clause reads the log or the statement as its own
test, or the policy names it as what may stand in."* The first — "it may carry a fact for the cap" —
is not redundant but is a hazard. The read-only review that produced `3f6f213` found it read as "it
may carry the limb", and on case 901 that reading let a driver's own messages lift the cap on an
impaired trace, defeating the clause that makes the trace the only evidence. A clause that restates a
neighbouring sentence, and that has already been read in the direction that escalates less, is worth
less than the risk it carries.

## 2. Why nothing was added

I was to add at most one sentence, and only if the removal left a gap: a sentence saying that whether
a record is a measurement bears on deciding a limb and never on the cap or the only-evidence question,
where the bridging and stand-in paragraphs govern.

**The removal alone suffices, so nothing was added.** Every function the removed sentence performed is
performed elsewhere in the same subsection. Quoted from the file as it now stands:

- **The carrier half** — that what a party said can carry the deciding fact, which is what the
  sentence's own "it may carry a fact for the cap" was protecting: *"Every artifact in `case.evidence`
  is a candidate carrier, not only the instrument evidence. ... What a party said is evidence like any
  other, and it can carry the deciding fact."*
- **The limb half:** *"an account decides a limb only where the clause reads the log or the statement
  as its own test, or the policy names it as what may stand in."*
- **The cap, and the only-evidence question, where the record lies between admitted readings:**
  *"A contemporaneous record from inside a stretch the test left unobserved, lying between readings
  the test admitted, counts for the cap and for any question whether something is the only evidence."*
- **The cap, and the only-evidence question, where the test admitted no reading at all:** *"Where the
  test admitted no reading at all, an account offered in its place is standing in for the test: it
  neither lifts the cap nor stops the impaired artifact being the only evidence, unless the policy
  names it."*

The candidate sentence is true, but it is not a rule the prompt is missing. The cap is decided by the
carrier grant, the removal test, the independence rule and those two paragraphs; the limb is decided
by the limb's own clause and the account rule. A general sentence restating the boundary would be a
fifth statement of it, placed in the middle of the paragraph that decides limbs — and the failure this
amendment has produced, in the eight places the review named, is exactly a sentence true of one
question read as a rule about another. The smaller change is the safer one.

**One thing the removal does take away is the label.** The sentence was the only place the prompt said
in so many words that a party's message about where anyone was *is* that party's account. The word
survives — in the account rule, in the stand-in sentence, and in the contradiction paragraph — but
none of those defines it; the definition has to be read out of the status sentence beside it, which
sets what a party sets against what the platform generates. That is the trade this change makes, and
it is why the carrier grant and the account rule are asserted *present* in
`DecidingFactCarrierTests` rather than assumed: with the label gone, the two halves it named are only
as safe as the sentences that now carry them.

## 3. Check by reading: 107, 211 and 901

Read-only. The judge's words are quoted from the result files; the prompt sentences are quoted from
`prompts/v1/judge.system.md` as it now stands. Nothing was run.

### 107 — the threshold fact is a magnitude, and the cap stays on the trace

The judge's decisive sentence:

> The driver's chat and counterparty statement admit the route and satisfy the POL-RD-08 corroboration
> requirement, but **they are not a measurement of the excess and cannot carry the threshold fact**.

The remaining sentences that decide it:

- **The carrier grant, which is why the admission is a carrier at all:** *"What a party said is
  evidence like any other, and it can carry the deciding fact."*
- **The removal test, which is what stops it carrying this fact:** *"The test is whether it would still
  support the finding if the instrument evidence were removed. If it would not, it is a restatement of
  the instruments rather than an independent carrier, and the cap does not move."*
- **The independence rule, which disposes of the trip record and the fare breakdown:** *"Two records
  derived from the same measurement are one carrier, not two, however many artifacts they arrive in: a
  trip record and a fare ledger computed from the same trace corroborate nothing."*
- **The cap and the floor:** *"the cap is the MINIMUM `weight_multiplier` among the artifacts that
  carry the deciding fact"*, and *"Below that floor the ruling is `ESCALATE`."*

So 107's escalation still stands on the remaining text, and only its wording moves. The judge wrote
"not a measurement"; the same conclusion is reached one sentence over by the removal test, which is
where it belongs — the threshold fact is a magnitude, the chat concedes the route and carries no
distance, so remove the trace and nothing left supports it.

### 211 — the limb is right on the remaining text, the cap still is not

The judge's sentence:

> **It is his account, not a measurement** and fixes no position; it therefore cannot satisfy a limb
> whose test is the GPS measurement, and **it does not stop the impaired trace being the only
> measurement evidence of the dwell**.

- **The limb half** rests on the surviving account rule: *"an account decides a limb only where the
  clause reads the log or the statement as its own test, or the policy names it as what may stand
  in."* Limb (c)'s test is the GPS measurement, so the driver's 12:35:10 message does not decide it.
- **The cap half** is the same misapplication of the bridging paragraph the previous note records, and
  the paragraph is unchanged: the trace admitted readings either side of the 168 s gap, so the message
  lies *between* readings and the first sentence governs it — *"counts for the cap and for any
  question whether something is the only evidence."*

Removing the account sentence neither fixes nor worsens 211: its cap error was made against the
bridging paragraph, which the removal does not touch.

### 901 — each step of the committed escalation still has its sentence

1. **The limb is undecided because the test's input is impaired** — the judge: *"That artifact is
   impaired: weight_multiplier 0.6 ... The test those limbs require therefore could not be run: limbs
   (b) and (c) are UNDECIDED over the waiting window, not failed."* Supported by the ordered
   procedure: *"Is what the test reads impaired over the stretch the defect covers? ... Impaired means
   under the category's own integrity limbs, not merely flagged by the pre-pass."* and *"If it is
   impaired, the limb is undecided over that stretch. An undecided limb supports neither a payment
   that needs the clause to hold nor a refund that needs it to fail."*
2. **The arrival marker is one carrier with the trace** — the judge: *"the trip record's arrival
   marker is auto-confirmed from the same GPS measurement, so marker and trace are one carrier and not
   two."* Supported by the independence rule, which names that pair: *"Two records derived from the
   same measurement are one carrier, not two ... a trip record and a fare ledger computed from the
   same trace corroborate nothing."*
3. **The driver's messages stand in where the test admitted no reading at all** — the judge: *"the
   chat log is the driver's own account, which may not stand in for a measurement the test never
   admitted."* Supported by the stand-in sentence: *"Where the test admitted no reading at all, an
   account offered in its place is standing in for the test: it neither lifts the cap nor stops the
   impaired artifact being the only evidence, unless the policy names it."*

**No step loses its support**, so the check did not stop. Step 3 is the one the removed sentence came
closest to carrying — its "does not satisfy a limb whose test is a measurement" is a second route to
the same conclusion — but the stand-in sentence carries it on its own, and the account rule carries
the limb half.

## 4. The previous note's quotation, corrected

`docs/notes/2026-09-24-judge-only-rerun-and-the-external-case.md` quoted the account sentence as:

> "a party's message about position is an account, not a measurement, unless it concedes against
> interest or the clause reads it as its own test"

That is not the text of `prompts/v1/judge.system.md` at prompts digest `eece65ee…`. The
admission-against-interest exception was removed in `3f6f213`, and the sentence as it stood carried no
exception at all. The note now quotes it exactly as it stood, and the same error's second appearance —
a clause in the 107 section crediting the sentence with that exception — is corrected to say what the
sentence actually carried.

**Every other quotation of the prompt in that note was checked against the file**, whitespace-collapsed
because the note re-wraps what it quotes:

| quotation | where | checked against |
|---|---|---|
| the account sentence (corrected) | §4, 107 | exact, `git show HEAD:prompts/v1/judge.system.md` — file digest `6d15627e…`, the file at prompts `eece65ee…` |
| "The test is whether it would still support the finding if the instrument evidence were removed." | §4, 107 | exact, current file |
| "Where the test admitted no reading at all, an account offered in its place is standing in for the test: it neither lifts the cap nor stops the impaired artifact being the only evidence, unless the policy names it." | §4, 211 | exact, current file |
| "A contemporaneous record from inside a stretch the test left unobserved, lying between readings the test admitted, counts for the cap and for any question whether something is the only evidence." | §4, 211 | exact, current file |

The block quotations in that note's §5 are the 901 result's own explanation rather than the prompt,
and were not touched.

**The sentence is still quoted, accurately for their own dates, in two earlier notes.**
`2026-09-24-meeting-a-limb-and-the-dropped-record.md` (which introduced it) and
`2026-09-24-the-limb-procedure-revised.md` (which kept it through the ordered-procedure rewrite) record
the prompt as it stood when each was written. They are left as they stand: each is a record of its own
digest, and this note is where the removal is recorded.

## 5. What the change costs the record

- **The brief channel is untouched: 0 of 29 moved.** The removal changes instructions, not facts,
  which is the separation `BriefStaleness` exists to keep.
- **The prompt channel moved all 29.** Every cached corpus result now records `eece65ee…` against a
  current `829ccc8f…`, so all 29 are stale for that one reason. Nothing was re-run to clear it, and
  clearing it is a run, not an edit.
- **Case 901 is the same shape.** Its brief channel is still current (`db5b6b95…` rebuilds
  identically) and its prompt channel is now stale. The converted case was not touched.
- **The viewer needed no rebuild, and that was checked rather than assumed.** `python -m ui.build
  --check` reports the committed page identical to a fresh build at 1,619,262 bytes: the page reads
  `prompts_sha256` from each run's provenance rather than embedding the current digest, so a prompt
  change does not reach it.

## 6. The standing rule

**This is the last change to `prompts/v1/judge.system.md` before the 10 October freeze, whatever the
next run shows.** After that run the prompt is frozen: misses are recorded, not fixed.

## 7. What this does not establish

It does not measure the change. No model was called, so nothing here says whether 107, 211 or 901
would move under the amended text; the next run is what measures that, and this note is the statement
of what the text now says that the next run can be read against. It also does not show the sentence was
harmless — it was removed as redundant and hazardous, not as proven to have moved a case, and the one
run that showed it moving a case (901, before `3f6f213`) moved it in the direction that escalates
less. And the tests pin the text, not the behaviour: `DecidingFactCarrierTests` can show the sentence
is gone and that both of its halves survive elsewhere, and cannot show what a judge does with the rest.
