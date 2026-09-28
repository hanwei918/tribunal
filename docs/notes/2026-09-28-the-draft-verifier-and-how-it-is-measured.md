# The draft verifier, and how it is measured

A judge draft can state a fact the brief does not support. Until now nothing
checked that: the referee reads the advocates' **claims**, and the judge's own
drafts were never read against the brief at all. This session adds a pass that
does, behind a switch, and a way to measure it on drafts a run has already
recorded without resampling the judge.

Two things were built, and one of them is a measurement harness rather than a
feature. The verifier is off by default; a run that does not ask for it is the
run it was before, byte for byte.

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
