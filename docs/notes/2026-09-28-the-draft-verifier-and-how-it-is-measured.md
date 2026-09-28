# The draft verifier, and how it is measured

A judge draft can state a fact the brief does not support. Until now nothing
checked that: the referee reads the advocates' **claims**, and the judge's own
drafts were never read against the brief at all. This session adds a pass that
does, behind a switch, and a way to measure it on drafts a run has already
recorded without resampling the judge.

Two things were built, and one of them is a measurement harness rather than a
feature. The verifier is off by default; a run that does not ask for it is the
run it was before, byte for byte.

**Two corrections were made on the same day, before this pass was measured on
either development set, and they supersede parts of this note.** A
`contradicted` verdict now carries a required boolean `material`, and only a
contradiction that could change a conclusion a statement draws stops its draft;
the recorded-drafts report therefore shows **three** readings of one vote rather
than two. And the prompt channel of the staleness check no longer compares the
digest of the prompt **directory**; it compares, per role, the digests the
recorded calls carry against what this code renders now. Section 6 records both,
and sections 1, 2 and 4 are to be read with it. Section 5 is unaffected.

## 1. The verifier

**One call per case.** `--verify-drafts` on either entry point. The call happens
after the case's drafts have passed the code checks and before the vote is
reduced, and it is **one call per case** — not one per draft and not one per
statement. That is the whole point of the design: the drafts are pooled into a
single numbered list and the verifier answers the list, so a case with four
drafts costs one call and so does a case with two.

**Code extracts the statements, not the model.** `pipeline.extract_factual_statements`
splits each valid draft's `ruling.ruling.explanation` into sentences and keeps
the ones carrying a **number, a time, a distance, a money figure or an evidence
id**. Which sentences are sent is therefore reproducible from the text alone and
does not depend on a model's judgement about what matters. A sentence with none
of those is never sent. The numbering is **global across the case** — `1..n`
over every valid draft in order — so a verdict names exactly one statement, and
each numbered entry carries the draft it came from so a contradiction can be
charged to the draft that stated it. A draft that already abstained contributes
nothing: it is not an answer the panel is weighing.

**The brief is the judge's own bytes.** `verifier_user_message` splices
`brief_json` rather than re-serialising it, so the verifier reads the same
characters the judge read. Only the number, the draft and the text travel; the
statement kinds are this package's own bookkeeping and are not part of what the
model is asked.

**Three verdicts, and only one of them stops a draft.**

- `contradicted` — the draft **abstains**, with reason
  `CONTRADICTED_BY_EVIDENCE: "<the statement>"`, so a reader sees which fact was
  rejected and not merely that something was.
- `not_in_evidence` — recorded and flagged on the draft, and the draft **keeps
  its vote**. The brief being silent is not the same as the brief disagreeing.
- `supported` — recorded, nothing else.

If fewer than three drafts remain valid the ruling is `ESCALATE`, which is the
existing rule and was not changed.

**An unusable answer is no verification, not a partial one.** `_verifier_call`
makes exactly one attempt and **never retries** — that is the difference between
this agent and every other one in the pipeline. A body that is not a JSON
object, that has no `verdicts` list, or whose entries do not each carry an
integer `statement`, one of the three verdicts and a string `evidence` is
treated as **no verification at all**: every draft keeps its vote, and the
record says so with a reason. A verdict set with a hole in it is not a check, so
a set that does not cover every statement exactly once is rejected the same way,
by the message `the verifier answered statements [...] where [...] were asked`.
The rule is that a broken verifier must not be able to change a ruling, in
either direction.

**The prompt is a new file and it is deliberately narrow.**
`prompts/v1/verifier.system.md` says the verifier judges statements and never
the ruling: "A statement may be false while the ruling that contains it is
correct; your finding is about the statement alone." It ships one worked JSON
example, as every agent prompt in this repository does.

**The tokens are its own.** The call is recorded on the transcript under
`ROLE_VERIFIER` and on the event log as an `agent_call` with `role=VERIFIER`,
plus one `verification` event per case. The transcript's totals report the
verifier's usage under its own role, so a reader can see its share without
subtracting the judge's. It is also in the case's bill, because the call was
made: `VerifierTokenTests` pins both halves — the judges' own total does not
carry the verifier's, and the case's prompt-token figure is larger by exactly
the verifier's call.

### Off has to be byte-identical, and it was not

`JudgeDraft.as_dict` originally wrote `"verification": self.verification`
unconditionally, so **every** draft record carried `"verification": null` even
with the switch off. That changed the JSON shape of every recorded transcript
and would have moved the shape of the committed run's own files. "The verifier
read this draft's facts and found nothing wrong" and "the verifier was never
asked" are different findings, so the key is written **only when the verifier
ran**. Checked against the committed transcript: the off payload's draft key set
is now exactly the one `runs/deepseek-deepseek-flash/case-00101.transcript.json`
carries, and the off payload's top-level keys are `entries`, `referee`, `vote`.

## 2. Measuring it on drafts already recorded

Re-running the judge would resample it, and the difference between the two runs
would then be a difference between two panels rather than the effect of the
verifier. `eval/verify_drafts.py` therefore holds the drafts still: it reads a
run's **recorded** judge drafts out of its transcript, rebuilds them through the
same assembly and the same code checks a live draft goes through, and calls only
the verifier. The same drafts are read with the pass off and on.

    python3 -m eval.run_benchmark --verify-recorded-drafts RUN_DIR
    python3 -m eval.development_sets --verify-recorded-drafts RUN_DIR

**What is refused.** The first four conditions are `run_benchmark.check_replay`'s,
reused rather than restated: no transcript for the case, or a transcript that no
longer hashes to what the run recorded; a brief that is not the brief the
recorded agents were handed; advocate prompts that are not the ones the recorded
calls recorded; a recorded call made on another model. This mode adds the
**judge side**, which a replay of the advocates cannot answer: the recorded judge
entries' own `system_sha256` must equal the digest of the judge prompt this code
renders now, and a run that asked the judge once has no panel to verify and is
refused too. A case refused this way is recorded with its reason and makes no
call.

**Where the results go, and where they may not.** `runs/verify-recorded-drafts/<model>/`,
and for a development set `runs/<set>/verify-recorded-drafts/<model>/`. The
subdirectory is a name of its own and not the model id, which makes "never the
headline directory" a property of the path rather than a promise, and
`verify_recorded_run` refuses a destination equal to the model's own run
directory before anything is written. The destination is created **after** the
provenance check, so an invocation that refuses every case leaves no directory
behind.

Three files are written — `verify-recorded.json`, `verify-recorded.md` and
`events.jsonl` — and none of them is a file a model's run directory carries.
There is no `run.json`, no `invocations.json` and no `case-*.json`, because this
is not a measurement of the model: the advocate and judge calls were the source
run's and cost nothing here, so the only token figures recorded are the
verifier's.

**What the report shows.** Per case: the vote's outcome, agreement and ruling
**without** the verifier and the same three **with** it, on the same drafts, and
then every statement judged `contradicted`, quoted, with the draft it came from
and the evidence it was checked against. The vote without is re-derived from the
recorded drafts rather than read from the source run's own conclusion, and
`matches_recorded` says whether the two agree — which is how a reader can tell
that the reconstruction is faithful before reading the difference.

## 3. The tests

All scripted-transport, no network. `tests/test_pipeline.py` gains eight classes
(39 tests): one call per case at two, three and four drafts, and no call at all
when the valid drafts state no checkable fact; the brief slices between the two
agents' user messages are equal; a contradicted statement abstains its draft and
a `not_in_evidence` statement does not; five kinds of unusable answer each keep
every draft's vote; the extraction picks up numbers, times, distances, money and
evidence ids and ignores a sentence with none; tokens counted apart; and the
switch off adding exactly one key, one vote-record key and one draft-record key
when on, with the off entries an exact prefix of the on entries.

`tests/test_verify_drafts.py` is new (18 tests) and builds a **real** source run
over a scripted transport, so the measurement is exercised against a transcript
of the shape it will actually read: the same drafts read twice, one call per
case, the destination never the headline directory, a mismatched judge prompt
refused, and a case refused before any client is asked to make a call.

## 4. What was run, and one thing that was not asked for

The full suite, quiet form, under both interpreters:

    python -m unittest discover -s tests

    Ran 1141 tests in 2845.840s
    OK (skipped=4)

    Ran 1141 tests in 2824.749s
    OK (skipped=4)

The four skips are all conditional and each names its own reason: the live
TokenHub call (`TRIBUNAL_LLM_NETWORK_TESTS` unset), the whole-run refusal test
(the committed run is current, so there is nothing to refuse), and two
`NoteCouplingTests` comparisons withheld because the cache under
`runs/deepseek-deepseek-flash` has moved on from the fingerprint a note records.
None of the four is caused by this change: `cache_fingerprint` reads the cached
files' own recorded provenance, not the prompts directory, so adding
`verifier.system.md` cannot move it. The committed viewer page is unmoved —
`python -m ui.build --check` reports it identical to a fresh build at 2,371,908
bytes — because the viewer displays the recorded prompts digest and never
recomputes staleness.

**But the new prompt file does move the prompt channel, and that is a real
consequence of this session.** `current_prompts_sha256()` hashes the `prompts/`
**directory**, so adding a file to it moves the digest:

    current_prompts_sha256()            a101e07cedef2c4b781e86fa511818c88f4c0345127ad2d3fbc4056b05b7f813
    recorded by all 44 cached results   83a7431029da37e216d82b75f91349c610e02a314ed9cff22c4a5e4fa59a9ac0

Measured with `runner.brief_staleness` over both caches, every result now reads
stale on the **prompt** channel and none on the brief channel — corpus 29 of 29
stale (`stale_prompts` 29, `stale_brief` 0, `unknown` 0), second set 15 of 15.
The label is broad on purpose and the comparison that matters is not: nothing
about the **judge's** instruction changed, and the narrower per-agent checks
still accept — `check_replay` compares the rendered *advocate* prompts and
`verify_drafts` compares the recorded judge entries' own `system_sha256`, and
both pass on all 44. So the cached results remain usable as evidence and the
staleness label now says "a prompt file in this directory is not the one this
run recorded", which is true, rather than "the judge was told something else",
which is not. Anyone reading a staleness report after this commit should read
the channel and not the word.

**No model call was intended in this session, and one was made.** While checking
that `--verify-recorded-drafts` reported a missing run directory as a refusal
rather than a traceback, the probe was pointed at a **real** run directory
(`runs/deepseek-deepseek-flash --cases 101`) instead of a path that does not
exist. The client authenticated from the untracked `.env` at the project root
and one live verifier call went out: case 101, `status 200`, `PARSED`, 38,093
tokens (17,923 prompt / 20,170 completion), 67 statements, 65 supported and 2
contradicted. It was not repeated. Nothing from it is staged — the output went to
`/tmp/verify-smoke/`, which is ignored — and it is disclosed here and in the
session row rather than left out. It incidentally confirmed the flag works
end to end against a real recorded run.

The commands above were **not** run over either development set: they are
transcribed and checked for argument validity, and they are the ones that would
produce the measurement. No figure for either set is claimed in this note.

## 5. Limits

- The verifier reads the brief and the statements. It cannot see the policy
  files, the case file or the transcript, so `supported` means "the brief
  states or entails this" and nothing more.
- The extraction is narrow on purpose. A sentence with no number, time,
  distance, money figure or evidence id is never sent, so a false statement
  made entirely in words is not checked. That is a real gap, and it is the
  price of a rule that a reader can reproduce from the text.
- A `contradicted` verdict is a model's reading of the brief, not a code check.
  It can abstain a draft that was right. The measurement mode exists because
  that has to be looked at on drafts that were not resampled, and the on/off
  comparison over both development sets has not yet been run.

## 6. Two corrections, before either set was measured

Both were made on 2026-09-28, after this note was written and before the
recorded-drafts pass was run on either development set. **No model call was made
in either session, not even a probe**: the refusal paths were exercised against
a directory that does not exist and through scripted transports. Nothing here
changes what the verifier is for, and nothing here was run over a development
set.

### 6.1 Only a material contradiction stops a draft

The one live verifier call this work had made — case 101, disclosed in section 4
— showed the rule was too strict. Two of that case's drafts wrote a share as
`22.6%` where the brief's own block carries `22.47%`; both were recorded
`contradicted`, both abstained, and a unanimous and correct ruling became
`ESCALATE`. The rounding changed no conclusion those statements drew: the share
is below the 90% test either way, and the refund is above SGD 0.50 either way.

So a `contradicted` verdict now carries two more fields, one of them required:

- `material` — a **boolean**, and required. It is `true` when the brief's value
  would change a conclusion the statement draws: which side of a threshold a
  figure falls, an amount in the ruling, whether an event happened, who did it,
  or the order of events. It is `false` when the difference changes none of
  those, which is what a difference of rounding or precision does.
- `brief_value` — what the brief holds instead, as text. Recorded rather than
  required, because a contradiction whose evidence is a derived-fact path may
  have no single value to quote.

`normalise_verifier_result` refuses a `contradicted` verdict whose `material` is
absent **or is not a real boolean**. `isinstance(True, int)` is true in Python,
so `"material": 1` is an answer that does not say whether the difference matters,
and it is treated exactly like leaving the field out. A refused verdict set is
still no verification at all: every draft keeps its vote and the record says so
with a reason. The rule that a broken verifier cannot change a ruling, in either
direction, is unchanged.

The prompt is updated to match, and its worked example is **invented**: it names
placeholder ids (`EV-DEMO-00042`, `EV-DEMO-00051`) and a placeholder path
(`demo_totals.billable_units`), and none of those appears in either development
set or anywhere else in the repository. The example carries one non-material
contradiction and one material one, so the distinction the rule turns on is in
the example and not only in the prose.

`apply_verification` takes an `abstain_on` switch. The pipeline's own value is
`ABSTAIN_ON_MATERIAL`; `ABSTAIN_ON_ANY` is the stricter reading, kept so that one
set of verdicts can be read both ways without a second call.

### 6.2 The report shows three readings of one vote

`CaseVerification` now carries three `VoteReading`s — `without`,
`any_contradiction` and `material_only` — and **one measurement run produces all
three**, because two of them are reductions of the same verdicts and the third is
the recorded vote itself. `changed` is `without` against `material_only`, which is
what the pipeline does; `strict_changed` is `without` against
`any_contradiction`, which is what this pass did before materiality existed; and
`saved_cases` names the cases where the second is true and the first is not — the
cases materiality exists for.

A case with no usable verdicts has nothing to re-apply, so all three readings are
then the same vote. That is stated rather than papered over: the three-reading
feature is only meaningful when a verdict set exists.

### 6.3 The prompt channel compares what the calls were given

`BriefStaleness`'s prompt channel used to compare the recorded `prompts_sha256` —
the digest of the whole prompt **directory** — against the directory as it stands
now. Adding `verifier.system.md` to that directory moved it, so every cached
result read stale on the prompt channel although no agent's instructions had
changed.

The channel now compares, **per role**, the `system_sha256` (and, for the
advocates, the `user_sha256`) that the recorded calls carry against what this
code renders now, through the same comparison `check_replay` makes for the
advocates and this module's own judge-side check makes for the judge. A prompt
file no recorded call used cannot make a result stale; a one-byte change to any
prompt a recorded call did use still does. The directory digest is still recorded
as `prompts_sha256`, for history, and `tests/test_run_benchmark.py` still asserts
that it is.

`unknown` is unchanged and still means what it meant: a result whose transcript
cannot be read, or whose calls carry no digest, is one this code cannot answer
for, and that is not `current`.

The consequence is measurable and was measured. **All 44 cached results read
current** — corpus 29 of 29 and second development set 15 of 15, each set with its
own loader — and the development-set report is unchanged at corpus 29/29, second
set 14/15, combined 43/44. The counts in section 4 above are superseded on this
point.

One qualification, recorded rather than fixed. `eval.development_sets.figures_for`
reaches a `GradeReport` through `grade_run`, which hands `case_loader` to the
per-case facts but leaves the staleness checker at its default — the corpus
loader — so its `staleness` object reports the second set's fifteen cases as
`unknown` on the brief channel where the run path reports them current. That is
pre-existing and unchanged here: at `b0f2948`, `brief_staleness` built
`BriefStaleness()` with the same default, so the same fifteen read `unknown`
before these corrections too. The measurement above uses each set's own loader,
which is what the run summary uses; `render_development_sets` renders no
staleness block, so no printed figure depends on the difference.

### 6.4 The tests

`tests/test_pipeline.py`'s scripted verifier now scripts materiality as well as
the verdict, and defaults it to the stricter reading so that the tests written
before the field existed still measure what they measured. Three tests were added:
a material contradiction stops its draft and a non-material one does not, on
otherwise identical verdicts; a non-material contradiction is recorded and flagged
with the value the brief holds; and a `contradicted` verdict with no boolean
`material` — absent, `1`, or a string — is no verification, with a positive
control on the same body carrying `true`.

`tests/test_verify_drafts.py` was migrated to the three readings: one set of
verdicts with one material and one immaterial contradiction yields three different
votes from the one call, and a case whose contradictions are all immaterial is
named in `saved_cases`, because the strict rule would have moved it and the
pipeline's rule does not.

`tests/test_run_benchmark.py`'s prompt-channel tests now move a **prompt** rather
than a cache field. A run is made against a byte-identical copy of the prompt set
and one byte of one file in that copy is then changed, so the shipped files are
never touched: a one-byte change to the judge prompt or to either stance file
makes the result stale, while adding a file that no recorded call used leaves it
current.

**One defect in this file was found only by counting, not by reading.** The two
module-level helpers above had been written **inside** `TwoChannelStalenessTests`,
between the class's last helper and its first test. A `def` at column zero ends the
class body, so `move_one_byte` became a module-level function whose body then
absorbed all eight `def test_` methods as nested functions: the class kept its five
helpers and no test at all, the eight were never collected, and the suite reported
`OK` at **1140 tests** where the file defines 1148. The helpers now sit below the
class and the eight tests are in it. One assertion was wrong once they ran: the
test changed one byte of the **shared** judge prompt file and expected one case
stale, where a file every case's judge call was given moves for all three — it now
reads `(101, 102, 103)` and `The prompts have moved for 3 of 3`. The count is the
guard: a suite cannot fail on a test it never collects, so a green run reporting
fewer tests than the files define is the failure mode to watch.
