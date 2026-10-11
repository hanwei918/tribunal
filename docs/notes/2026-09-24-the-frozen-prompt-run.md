# The frozen-prompt run

**2026-09-24.** The run that measures the judge prompt as it was frozen. Four invocations at commit
`c4c9a06c30bc630e52305a8bf09a14bda83771d5`, model `deepseek/deepseek-flash`, prompts directory digest
`829ccc8fe999b809be7d9fbbaaa70694aa9377f9f42f753f678bae9f29bae512` (`prompts/v1/judge.system.md` at
file digest `8eee6472c31e62eef627dbbf500f8fd6d0af701cc6e93b615443a8cb08fd2443`).

Nothing was re-run to write this note and no result file was edited: every figure below is read out of
`runs/deepseek-deepseek-flash/` and `runs/external/ryde/` as those directories stand, and the two
commits it is compared against are read out of git. The prompt was not changed and must not be: this
is the run the freeze is dated from, so what it shows is recorded and not repaired.

**How the quotations below are made.** Whitespace is collapsed, because the prompt and the result
files wrap at different columns; the prompt's own emphasis markers are not reproduced, though they are
present in the file; an elision is marked with "…"; and a quotation that begins or ends mid-sentence
stops at the source's own punctuation. Every quotation in this note was then checked programmatically
against its source — the prompt file, or the result file the judge's words came from — and **all
fifteen are literal**, none outstanding.

## 1. The four invocations, and what they cost

| # | command | cases | outcome | judge tokens paid | advocates borrowed | paid by |
|---|---|---|---|---|---|---|
| 1 | `--replay-advocates runs/deepseek-deepseek-flash --force --token-budget 900000` | 101–207 (22 of 29 requested) | stopped, `token budget reached` | 902,605 | 1,285,230 | Guofang's quota |
| 2 | `--replay-advocates runs/deepseek-deepseek-flash --force --cases 208,209,210,211,212,213,214` | 209–214 (6 of 7; 208 timed out) | `completed` | 260,619 | 389,686 | the owner's balance |
| 3 | `--replay-advocates runs/deepseek-deepseek-flash --force --cases 208` | 208 (1 of 1) | `completed` | 25,720 | 57,766 | Guofang's quota |
| 4 | `--external data/external/ryde/case-00901.json` | 901 | `completed` | 106,661 | — | Guofang's quota |

The session paid **1,295,605 tokens** and recorded **1,732,682 tokens** of advocates as borrowed —
exactly the figure `runs/README.md` gives for the advocates' share of the `493beea` run, which is what
a replay is supposed to reproduce rather than re-spend. Every invocation is at `c4c9a06` and every one
reused the `493beea` run's advocate outputs.

**The second invocation's 208 is a timeout, and it is recorded as one.** 600 s elapsed with no
response; `invocations.json` records the failure kind as `TIMEOUT` and its own failure-token split as
zero, so the run charged nothing for it. Whether the provider generated and billed an answer anyway is
not recorded by either file, and this note does not claim it either way. The third invocation re-ran
208 alone; it completed, and its result matches the key.

**A run was also interrupted with Ctrl-C before the fourth invocation, and the files do not record
it.** `invocations.json` gained exactly three entries for the corpus directory (the three above, one
per invocation) and one for the external directory, and no entry in either has a missing `ended_at` or
`stop_reason`. `calls.json` is not a history: it is rewritten by each invocation, and the corpus file
now holds one call — the third invocation's, at `2026-09-24T13:45:37.796597+00:00`, which is that
invocation's own `ended_at` to the millisecond — while the external file holds the fourth invocation's
three calls, at 13:48:07, 13:49:13 and 13:50:31. Nothing in either file falls in the 61 seconds between
the third invocation's end (13:45:37) and the fourth's start (13:46:38). That is the whole of what the
two files show about it: an interruption that wrote no invocation record and whose `calls.json` was
overwritten leaves no trace, and none is inferred here.

## 2. Verify from the files

**All 29 corpus results are current under `829ccc8f`.** Every case's recorded `prompts_sha256` is the
current directory digest, `brief_staleness` over the 29 reports 0 stale and 0 unknown on both channels,
and all 29 carry a `replay` block, so every one was produced by a judge-only call. The cache this
note describes has a fingerprint, recorded here so the claims can be checked against it rather than
taken on trust: `runner.cache_fingerprint` over `runs/deepseek-deepseek-flash` is
`cfd632af156413c0cb25591a2abd643cb3f2bfc000bc8310ad0b6b67be416a5b`.

**The four-field grade over all 29 is 27/29**, failing **105** and **211**. Per field: `ruling` 27/29,
`amount_sgd` 27/29, `driver_compensation_sgd` 28/29, `referrals` 29/29. The per-invocation figures are
smaller and answer a different question: the first invocation's 22 cases are 21/22 (105 the miss), the
second's six are 5/6 (211), the third's one is 1/1. `runs/deepseek-deepseek-flash/report.md` is
`run.json`'s sibling and belongs to the **last** invocation, so the committed report is a **one-case**
report reading 1/1 and marked "(advocates replayed)". Read its case count before comparing it with the
29-case figure.

**901's result is as stated in §6**: `ESCALATE`, confidence 0.6, no amount, no driver compensation, no
referral, `matched` `null` (it is never scored). Both its channels are current — its brief rebuilds to
`db5b6b955954b4d814053ab13f94e3f37d3de23084dd1f7b4ace7556838b979d`, the digest it recorded, and its
recorded `prompts_sha256` is the current `829ccc8f`.

## 3. The same 29 cases under three judge prompts

Every corpus result is graded the same way — the four POL-GEN-03 fields against
`eval/answers/ground_truth.json` — so the three columns are the same measurement of three prompts. The
`b131e63f` and `eece65ee` columns are graded from the run directories those commits left
(`f6e72da:runs/deepseek-deepseek-flash` and `HEAD:runs/deepseek-deepseek-flash`), read out of git and
never checked out over the working tree.

| case | key (`ruling` + `amount_sgd`) | `b131e63f` | `eece65ee` | `829ccc8f` |
|---|---|---|---|---|
| 101–104, 106, 108–115 | — | ok | ok | ok |
| **105** | FULL_REFUND 65.13 | ok | ok | **FAIL** (ruling, amount) |
| **107** | PARTIAL_REFUND 7.45 | ok | **FAIL** (ruling, amount) | ok |
| 201–210, 212–214 | — | ok | ok | ok |
| **211** | PARTIAL_REFUND 2.0 | **FAIL** (ruling, amount) | **FAIL** (ruling, amount) | **FAIL** (ruling, amount, comp) |
| | **exact** | **28/29** | **27/29** | **27/29** |

| prompts digest | commit whose run it is | exact |
|---|---|---|
| `b131e63f046aecc68471631df8c04f9e0fde88d3383775028f8da058474bc3d3` | `493beea`, results committed at `f6e72da` | 28/29 |
| `eece65ee58ab78de1ace84079e63c8a4de3bb63e3f4b2adc12b7a2a3d8bd6397` | `74881db`, results committed at `110633f` | 27/29 |
| `829ccc8fe999b809be7d9fbbaaa70694aa9377f9f42f753f678bae9f29bae512` | `c4c9a06`, this run | 27/29 |

Three cases ever differ, and each of the three moved for its own reason. 107 was over-escalated by the
account sentence and the removal fixed it. 105 and 211 are this run's misses, and §4 and §5 take them
one at a time.

## 4. 105 — a borderline reading, and it moved the other way

The judge's deciding sentence, from `runs/deepseek-deepseek-flash/case-00105.json`:

> Under POL-RD-10(5), an exculpatory clause invoked against an absent required artifact is a mandatory
> escalation.

The prompt bullet it applied — unchanged by the last change, and present in both prompts:

> An exculpatory clause invoked with nothing behind it is not an untested limb. An assertion citing no
> evidence is discarded under the clause that places the burden; a clause invoked against an artifact
> that is absent escalates on that clause's own terms.

The key reads 105 as `FULL_REFUND 65.13`; this run escalates and holds the disputed SGD 65.13. The
driver's exculpation is an uncited assertion that traffic was heavy on the PIE, and the advisory
artifact that would support it, `EV-ADVIS-00105-01`, is `MISSING` at weight 0.0. The sentence above has
two halves and the case sits exactly between them: an assertion citing no evidence is a burden matter,
and a clause invoked against an absent artifact escalates.

**Both readings are in this run's own output.** Case 107, in the same invocation under the same prompt,
was reasoned the other way by the same judge:

> POL-RD-10(5) does not fire either: an assertion that cites no advisory is a burden matter under
> POL-RD-08, not a clause invoked against an absent artifact.

And the run before the last change read 105 the same way 107 was read here — from `eece65ee`'s
`case-00105.json`:

> I considered whether POL-RD-10(5) forces escalation — an exculpatory clause invoked against an
> artifact missing from the pool. It does not fire here: the driver cited no advisory and asserted no
> road closure; he made an uncited general assertion of congestion, which POL-RD-08 resolves on the
> merits rather than treating as a data gap.

**So this is run-to-run instability on a borderline reading, not an effect of the last change.** Three
things support that and none of them is a guess. The bullet that decides 105 is untouched by the
change. The sentence the change removed is about *a party's message about where anyone was* and about
what may carry a fact *for the cap*; 105's escalation is triggered by an absent artifact, and the judge
says so in terms — its confidence is 0.0 "because the only artifact directly behind the escalation
trigger is the missing advisory". And neither 105 explanation mentions an account, a measurement or a
limb. What moved is which half of one unchanged sentence the judge took, and the run holds both
readings at once. The limit is stated in §9: one sample per prompt cannot *prove* the difference is
variance, and it is recorded as a miss rather than fixed.

## 5. 211 — money paid on an undecided limb, and the first known limitation

The judge's deciding sentences, from `runs/deepseek-deepseek-flash/case-00211.json`:

> Chat message MSG-00211-004, 'boss still here waiting ah, cannot see you', was sent at 12:35:10 - from
> inside the hole - and is a contemporaneous record made from within the very stretch the trace leaves
> unobserved, lying between fixes the trace admitted on both sides of it, and coming from a different
> source. It therefore counts, and it means the impaired trace is not the only evidence of what was
> happening in those 168 seconds.

> Taken together - in-geofence fixes before the hole, the driver's own message from inside it,
> in-geofence fixes after it - the driver held the pickup continuously from 12:30:00 to 12:38:20, 500
> seconds against the 300-second STANDARD minimum. Limb (c) is met, and POL-NS-06 has no shortfall to
> refund.

The ruling is `DRIVER_COMPENSATION` with `amount_sgd` and `driver_compensation_sgd` both 3.20 at
confidence 0.85 — money moved to the driver. The key reads `PARTIAL_REFUND 2.0`.

**The cap half is right, and it is the bridging paragraph applied correctly.** The trace admitted
readings on both sides of the 168 s hole, so the message lies *between* admitted readings and the
paragraph's first sentence governs it:

> A contemporaneous record from inside a stretch the test left unobserved, lying between readings the
> test admitted, counts for the cap and for any question whether something is the only evidence.

The judge says exactly that — "the independent chat record carries the same fact, so the discounted
trace neither caps my confidence below the platform floor nor makes this a case in which an impaired
artifact is the only evidence" — and it is the reading the paragraph's own words require.

**The limb half is the dangerous one.** The message was then used to *find limb (c) met*, and the
payment follows from that finding. The bullet that forbids it is untouched:

> If it is impaired, the limb is undecided over that stretch. An undecided limb supports neither a
> payment that needs the clause to hold nor a refund that needs it to fail: say so, and apply what the
> integrity and escalation clauses give for uncertainty, including how they say an impaired stretch is
> read.

A contemporaneous record counts *for the cap* and *for the only-evidence question*. It does not run the
limb's test, and limb (c)'s test is a measurement the trace could not make across the hole. The
paragraph's first sentence was read as a licence for the second: because the message counted, the limb
was treated as met, and the case was paid.

**This is the dangerous direction and it is the system's first known limitation.** The run before the
last change got this case wrong the safe way — it escalated, which is a case the key would have decided
but a human can put right, and it cost the rider nothing. This run gets it wrong the other way: it pays
SGD 3.20 to the driver on a limb its own findings leave undecided, and it does so at confidence 0.85
with no referral. Under §7 of `docs/notes/2026-09-24-removing-the-account-sentence.md` the removal
"neither fixes nor worsens 211", and that holds — the cap error was made against the bridging
paragraph, which the removal does not touch — but the case's failure mode has changed from a withheld
payment to a made one, and that is a new fact about the system rather than a restatement of an old one.

## 6. 901 — the organisers' sample case

`--external data/external/ryde/case-00901.json` produced **`ESCALATE`, confidence 0.6**, no amount, no
driver compensation, no referral, in 232.7 s and 106,661 tokens. `matched` is `null`: the case has no
entry in `eval/answers/ground_truth.json` and is not scored. The organisers' stated expectation for
their own sample is "Cancellation charge UPHELD"; it is printed beside the ruling and is not an answer.

The ruling's own explanation, quoted:

> This dispute turns on one question — did the driver reach the Tiong Bahru Plaza pickup point and hold
> position there for the required five minutes? — and the only evidence that can answer it is not
> reliable enough to decide the case. That is why I am sending it to a human reviewer rather than
> ruling for either of you, and why the $5.00 stays on hold, neither collected nor refunded, while that
> review is pending.

> the GPS trace from the driver's device is impaired for policy purposes under POL-NS-08(b). Inside the
> waiting window it has sampling gaps of 180 and 240 seconds (the limit is 120), it holds only four
> position fixes (the minimum is six), and it carries no rider track where POL-NS-04 needs rider
> position. It also puts no accuracy figure on any fix, so under POL-NS-02 no fix can establish arrival
> — but equally no fix can establish that the driver was elsewhere. That is absence of measurement, not
> proof of absence.

> Those are your own account of arrival, and the arrival marker on the trip record was auto-confirmed
> from the same GPS measurement, so the marker and the trace are one carrier, not two. Where the GPS
> test admits no qualifying reading, an account offered in its place stands in for the test: it does
> not lift the confidence this ruling can carry, and the trace stays the only evidence of the deciding
> fact.

> Because the only evidence for the deciding fact is the impaired trace (weight 0.6), POL-NS-08's
> closing sentence and POL-NS-09(e) apply: the ruling may not exceed a partial refund and the case goes
> to human review. My confidence is capped at the trace's 0.6, below the 0.70 floor, which is a second,
> independent ground for escalation under POL-NS-09(a). Escalation is terminal and replaces any money
> outcome.

This is the ruling the repository's own policy text supports, and it is the same one the previous
judge-only re-run produced — the deciding fact's only measurement is impaired under POL-NS-08(b), and
POL-NS-09(e) makes the escalation terminal and holds the fee. The amendment that removed the account
sentence closed the reading that had let a driver's own messages lift the cap here, and 901 is the case
where that reading was found.

## 7. The advocate provenance: verified, and then corrected

**Verified byte-for-byte.** Every replayed advocate entry was compared against
`f6e72da:runs/deepseek-deepseek-flash/case-NNNNN.transcript.json`, the commit that committed the
`493beea` run's results. All **58** advocate entries (29 cases × 2 roles) are identical field for
field — `role`, `model`, `system_sha256`, `user_sha256`, `response_text`, `parsed`, `parse_outcome`,
`shape`, `status`, `attempts`, `prompt_tokens`, `completion_tokens`, `reasoning_tokens`,
`cached_tokens`, `duration_seconds` and `timestamp` — with one exception: the `note` field, which the
copying code writes to mark the entry as replayed, and which here nests the source entry's own note.
Nothing else differs. The judge's entries differ, as they must: that is the call this run made.

**The recorded provenance did not say so, and now does.** The summary printed

    replay      advocates from runs/deepseek-deepseek-flash (commit c4c9a06c30bc): 29 of 29 cases reused them and only the judge was called

and the run-level `replay` block carried `git_commit: c4c9a06…` — the commit the *source directory*
recorded, which for a replay into that very directory is the run that **copied** the advocates, not the
run that made them. The commit that made them travels per case (each entry's `replay.git_commit` is
`493beeaf…`), so the run-level block had only the copying run's name and a reader of the summary would
conclude the advocates were re-run at `c4c9a06`.

The fix names both. `CaseOutcome` now carries `replayed_made_at` per case, read from the entry the
advocates came from; `replay_block` collects those into `advocate_commits` over the same outcomes the
case list is built from, so a run stopped on its budget names no commit for a case it never reached;
and the summary prints two lines:

    replay      advocates from runs/deepseek-deepseek-flash: 29 of 29 cases reused them and only the judge was called
                those advocates were made at commit 493beeaf9495; the directory they were copied from records commit c4c9a06c30bc

The viewer's footer is the third reader of the same block and had the same defect — it printed
"replayed from runs/deepseek-deepseek-flash at c4c9a06c30bc" — so it now reads the commit that made the
advocates from the case entries, the way it already reads the source directories, and names both. Two
tests pin it: `ReplayTests.test_the_run_record_names_the_commit_that_made_the_advocates` drives two
replays into one directory and asserts the block and the summary name the run that made them, and
`ReplayTests.test_the_footer_names_the_run_that_made_the_advocates` asserts the page carries both.

**This run's own files are left exactly as produced**, `c4c9a06` and no `advocate_commits` in their
`replay` blocks, because a run record is evidence and editing one to match later code destroys what it
evidences. The correction is what the next run will record. The report `eval/grade.py` renders names
the source directory and no commit at all, so it cannot mislead about which run made the advocates, and
it is left unchanged — regenerating it would rewrite a committed result file.

## 8. The viewer

`python -m ui.build` rebuilt `ui/dist/index.html` over this run: **29 cases, 1,617,061 bytes** (it was
1,619,262 bytes over the `eece65ee` results), and `python -m ui.build --check` reports the committed
page identical to a fresh build at that size. The page's footer now carries both commits —
`git_commit` `c4c9a06c30bc…` and `advocate_commits` `["493beeaf9495…"]` — which is the third reader
fixed in §7.

## 9. The standing rule, and the figure the submission may use

**The judge prompt is frozen at prompts digest `829ccc8f…`.** This is the run it is frozen from. 105
and 211 are recorded here, not fixed: no prompt was changed after this run and none may be. A later
reader who thinks 105 or 211 was misread is disagreeing with the record, which is what the record is
for.

The figure the submission may quote is this one, verbatim:

> 27/29 on the development set under the frozen prompt, judge re-run on fixed advocate inputs; the
> organisers' sample escalated as this policy requires

**No other accuracy figure is current.** The 28/29 at `b131e63f` and the 27/29 at `eece65ee` are the
same corpus under earlier prompts and are historical; they belong to §3 and to the notes that recorded
them, not to the frozen prompt. The per-invocation figures (21/22, 5/6, 1/1) are those invocations'
own case sets and are not corpus figures at all.

**Amended 2026-09-25 — the rule above no longer holds.** Its premise was that
every further change could only be informed by the same 29 cases, and on
2026-09-25 that stopped being true: a second development set was added. The rule
that replaces it — the prompt may change until 6 October 2026 and only in
response to failures seen across both development sets, with every change
regression-run on all of them; it is frozen after 6 October; and a fresh sealed
set, drafted without access to this repository and run exactly once after the
10 October freeze, is the only figure the submission reports as generalisation —
is recorded in `docs/notes/2026-09-25-the-standing-rule-change.md`. This note is
left as it was written; it records the rule that was in force on 2026-09-24.

**Amended 2026-10-11 — one phrase in the rule it quotes is too strong.** The
sealed sets were not drafted without access to this repository: their own
validators read this repository's `data/schema.json` and `policy/*.json` from a
copy, and `sealed-v1`'s README says the set was authored from `data/SCHEMA.md`,
`data/schema.json` and `policy/*.json` alone. What they did not have is the
development prompts, the misses and the tuning process. The provenance table in
`README.md` (*Where the test sets came from*) sets out what each set's author
had.

## 10. What this does not establish

It does not measure the last change against the one before it on the corpus — 27/29 against 27/29, with
105 moving out and 107 moving in, and a single run per prompt cannot separate a one-case difference
from sampling variance. It does not show that 105's escalation is wrong as a reading of POL-RD-10(5):
the prompt's own bullet says an absent artifact escalates, and the key says otherwise, so the
disagreement is between the text and the key as much as between two runs. It does not score 901.
It does not show that 211's cap error is new — it is the same contested reading of POL-GEN-02(2) that
`c21379b` recorded — only that this run's version of it moves money. And it does not show the
provenance fix working on a real run: the test drives it on a fixture, and the first run that records
`advocate_commits` will be the next one.
