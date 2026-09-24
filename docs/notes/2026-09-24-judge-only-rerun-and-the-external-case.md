# The judge-only re-run, and the external case

**2026-09-24.** Three invocations at commit `74881db`, prompts
`eece65ee58ab78de1ace84079e63c8a4de3bb63e3f4b2adc12b7a2a3d8bd6397`, runtime model
`deepseek/deepseek-flash`. Nothing was re-run to write this note and no result file was edited: every
figure below is read out of `runs/deepseek-deepseek-flash/` and `runs/external/ryde/` as those
directories stand.

The point of the exercise was to measure the amended judge prompt through the judge alone. The
advocates' outputs and every corpus brief are byte-identical to the headline run, so
`--replay-advocates runs/deepseek-deepseek-flash` borrows the two advocates from that run's
transcripts and calls only the judge. The source run is the one at commit `493beea`
(`493beeaf94953943116a25cb74353b3dd2279499`), whose 29 results were the 28/29 measurement this one
is compared against.

## 1. The three invocations, and what they cost

| # | command | cases | outcome | judge tokens paid | advocates borrowed | paid by |
|---|---|---|---|---|---|---|
| 1 | `--replay-advocates runs/deepseek-deepseek-flash --force --token-budget 850000` | 101–210 (25 of 29 requested) | stopped, `token budget reached` | 879,903 | 1,481,916 | the teammate's quota |
| 2 | `--replay-advocates runs/deepseek-deepseek-flash --force --cases 211,212,213,214` | 211–214 (4 of 4) | `completed` | 217,897 | 250,766 | the owner's balance |
| 3 | `--external data/external/ryde/case-00901.json` | 901 | `completed` | 115,855 | — | the owner's balance |

The two replay invocations paid **1,097,800 tokens** for the judge's calls and recorded
**1,732,682 tokens** of advocates as borrowed. That second figure is exactly the advocates' share of
the source run's 2,804,061 tokens — **61.8 %**, the share the replay mode exists to avoid
re-spending. With the external case the session paid **1,213,655 tokens** in total. The judge alone
took 2,278.2 s (38.0 min) of wall clock over the 29 corpus cases and 275.3 s over 901.

## 2. What the record shows

**All 29 corpus results are current on both channels.** `brief_staleness` over the 29 reports 0 stale
and 0 unknown by brief, and every result's recorded `prompts_sha256` equals the current
`eece65ee58ab…` digest. Every one of the 29 carries a `replay` block, so all 29 were produced by a
judge-only call. `invocations.json` holds four entries — the two earlier full runs and the two replay
invocations above — and the two replay entries carry `replay.run_dir`, `replayed_cases` and the
borrowed-token figures.

**The four-field grade over all 29 is 27/29**, failing **107** and **211**, both on `ruling` and
`amount_sgd`, both over-escalations: the judge escalated where the key rules a monetary outcome. Case
901's result is as stated in §5.

### Two defects the verification found

**A wrong count in the run summary.** The first invocation printed `29 of 25 cases reused them` on a
25-case run — more cases reused than were run. The numerator was the acceptance check's
`replayed_cases`, which is every case the pre-run check *accepted*; a run stopped on its budget never
reaches the rest. The corrected count comes off the run's own outcomes
(`RunSummary.replayed_cases`), through one `replay_block` used by all three readers — the run's
metadata file, the printed summary and the viewer's footer — because the same over-count had reached
`run.json` and therefore the page. Two tests in `test_run_benchmark.py` reproduce the original
condition, and both fire against the old line (it prints `3 of 1 cases reused them` on the fixture).

**A wrong source commit for four cases.** Cases 211–214 record
`replay.git_commit = 74881db…`; the other 25 record `493beea…`. `74881db` is the commit of the replay
that *copied* the advocates, not the run that *made* them. `run.json` is the last invocation's file,
and a replay into the directory it reads from rewrites it before the next replay reads it: the second
of two replays into one directory therefore read the first's commit. The advocates for 211–214 came
from the `493beea` results, which invocation 1 never touched. `source_advocate_commit` now reads the
append-only invocation history and answers with the last invocation that completed the case *without*
replaying; a test drives two replays into one directory and asserts both name the commit that made
the advocates. The four recorded files are left exactly as produced.

**One caution, and not a defect.** `runs/deepseek-deepseek-flash/report.md` is graded over the cases
the invocation that wrote it handled, and the fourth invocation handled four. The committed report
therefore reads **3/4 = 75.0 %** and is marked "(advocates replayed)", while the directory-wide figure
is 27/29. Both are true and they answer different questions — the report is a measurement of what that
invocation ran, the 27/29 is what grading all 29 cached results gives — and `run.json` is the last
invocation's file for the same reason. Read the report's case count before comparing it with anything.
Neither file was edited; both are what the runner wrote.

**The repository was verified on both interpreters and from a fresh clone.** The suite is 839 tests,
OK (skipped=3) under Python 3.13.12 and under 3.9.6, and a fresh clone of `e4608a5` — the commit this
note is written against — runs it green as well, with one extra skip because `.env` is gitignored and
exists only in the author's working tree. In that clone `python -m ui.build --check` reports the
committed page identical to a fresh build at 1,619,262 bytes, so the page this run rebuilt is a
function of the repository rather than of the checkout it was built in.

**The cache this note describes has a fingerprint, and it is recorded here so the claims above can be
checked against it rather than taken on trust.** `runner.cache_fingerprint` over
`runs/deepseek-deepseek-flash` is `e2231efb0cbcd1434582320445d75f0479422d02316959397a7c5df18a079356`
— the set of per-case brief and prompts digests, which is provenance and not a count — and over that
cache the staleness report reads **29 cached, 29 current, 0 stale, 0 unknown** on the brief channel,
with every case's recorded `prompts_sha256` equal to the current `eece65ee…` on the prompt channel.
That is the same fingerprint the suite's skip messages name as the cache present.

**Two checks in `test_run_benchmark.py` are currently inert, and it is worth knowing why.** They
compare `docs/notes/2026-09-22-stale-cached-results.md`'s counts against the live cache, and skip while
that note's fingerprint does not match; they have been skipping since 2026-09-23, when this cache
moved. That is the behaviour the note's own design asks for — a count about one cache held against
another measures the calendar — so it is not a defect and nothing here changes it. It does mean the
suite's `skipped=3` reads as one number for three different reasons — one opt-in network test and these
two structural skips — and the fresh clone's `skipped=4` adds the gitignored-`.env` test on top of
them. Re-arming the two is a change of design rather than a repair: it needs a note carrying that block
format and `STALE_NOTE` pointed at it, which is the owner's call and not this session's.

## 3. Every case, before and after

Before is the headline run's result at `493beea` (28/29 exact, 211 the single miss). Now is this run.
"vs key" compares `ruling` and `amount_sgd` against `eval/answers/ground_truth.json`.

| case | key | before | now | moved | vs key |
|---|---|---|---|---|---|
| 101 | PARTIAL_REFUND 8.05 | PARTIAL_REFUND 8.05 | PARTIAL_REFUND 8.05 | – | ok → ok |
| 102 | NO_ACTION | NO_ACTION | NO_ACTION | – | ok → ok |
| 103 | PARTIAL_REFUND 4.0 | PARTIAL_REFUND 4.0 | PARTIAL_REFUND 4.0 | – | ok → ok |
| 104 | PARTIAL_REFUND 3.6 | PARTIAL_REFUND 3.6 | PARTIAL_REFUND 3.6 | – | ok → ok |
| 105 | FULL_REFUND 65.13 | FULL_REFUND 65.13 | FULL_REFUND 65.13 | – | ok → ok |
| 106 | PARTIAL_REFUND 10.75 | PARTIAL_REFUND 10.75 | PARTIAL_REFUND 10.75 | – | ok → ok |
| **107** | PARTIAL_REFUND 7.45 | PARTIAL_REFUND 7.45 | **ESCALATE** | **moved** | **ok → MISS** |
| 108 | NO_ACTION | NO_ACTION | NO_ACTION | – | ok → ok |
| 109 | DRIVER_COMPENSATION 3.15 (comp 3.15) | DRIVER_COMPENSATION 3.15 (comp 3.15) | DRIVER_COMPENSATION 3.15 (comp 3.15) | – | ok → ok |
| 110 | ESCALATE | ESCALATE | ESCALATE | – | ok → ok |
| 111 | NO_ACTION | NO_ACTION | NO_ACTION | – | ok → ok |
| 112 | ESCALATE | ESCALATE | ESCALATE | – | ok → ok |
| 113 | NO_ACTION | NO_ACTION | NO_ACTION | – | ok → ok |
| 114 | PARTIAL_REFUND 13.7 | PARTIAL_REFUND 13.7 | PARTIAL_REFUND 13.7 | – | ok → ok |
| 115 | PARTIAL_REFUND 2.0 | PARTIAL_REFUND 2.0 | PARTIAL_REFUND 2.0 | – | ok → ok |
| 201 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | – | ok → ok |
| 202 | DRIVER_COMPENSATION 4.8 (comp 4.8) | DRIVER_COMPENSATION 4.8 (comp 4.8) | DRIVER_COMPENSATION 4.8 (comp 4.8) | – | ok → ok |
| 203 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | – | ok → ok |
| 204 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | – | ok → ok |
| 205 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | – | ok → ok |
| 206 | FULL_REFUND 4.0 (comp 2.0) | FULL_REFUND 4.0 (comp 2.0) | FULL_REFUND 4.0 (comp 2.0) | – | ok → ok |
| 207 | ESCALATE | ESCALATE | ESCALATE | – | ok → ok |
| 208 | DRIVER_COMPENSATION 6.4 (comp 6.4) | DRIVER_COMPENSATION 6.4 (comp 6.4) | DRIVER_COMPENSATION 6.4 (comp 6.4) | – | ok → ok |
| 209 | NO_ACTION | NO_ACTION | NO_ACTION | – | ok → ok |
| 210 | ESCALATE | ESCALATE | ESCALATE | – | ok → ok |
| **211** | PARTIAL_REFUND 2.0 | ESCALATE | ESCALATE | – | **MISS → MISS** |
| 212 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | FULL_REFUND 4.0 | – | ok → ok |
| 213 | ESCALATE | ESCALATE | ESCALATE | – | ok → ok |
| 214 | DRIVER_COMPENSATION 3.2 (comp 3.2) | DRIVER_COMPENSATION 3.2 (comp 3.2) | DRIVER_COMPENSATION 3.2 (comp 3.2) | – | ok → ok |

**One case moved: 107.** Every other result is byte-identical in `ruling`, `amount_sgd` and
`driver_compensation_sgd` to what `493beea` produced. A one-prompt change measured through one agent
moved one case, which is the isolation the replay mode was built to give.

## 4. The two over-escalations

Both are cases where the judge escalated and the key rules money. They are not the same failure: in
107 the judge applied the amended sentence as written and the text itself over-escalates; in 211 it
applied the wrong sentence.

### 107 — applied as written

The judge's own sentence:

> The driver's chat and counterparty statement admit the route and satisfy the POL-RD-08 corroboration
> requirement, but **they are not a measurement of the excess and cannot carry the threshold fact**.

The sentence of the amended prompt it was applying is the account/measurement rule added to Step 2,
quoted here exactly as it stood at `eece65ee…`:

> A party's message about where anyone was is that party's account, not a measurement: it may carry a
> fact for the cap, but it does not satisfy a limb whose test is a measurement.

It is read with the removal test that governs carrier status — *"The test is whether it would still
support the finding if the instrument evidence were removed."* This note records the prompt as this
run's judge was handed it; the account sentence was removed on 2026-09-24, after the run, in
`docs/notes/2026-09-24-removing-the-account-sentence.md`.

**Applied as written.** The POL-RD-01 threshold needs a magnitude: an excess greater than 20 % of
`optimal_distance_km` (14.0 km, so 2.8 km) *and* greater than 0.8 km. The measured excess is 3.57 km
and the only artifact that measures it is `EV-GPS-00107`, down-weighted to 0.30 by the pre-pass. The
driver's chat ("cte very jam tonight boss") and the counterparty statement ("I went by Newton and Kim
Seng to avoid it") are concessions, and the carrier section names an admission against the speaker's
own interest as a qualifying carrier — but the thing conceded is the *route*, and neither artifact
carries a distance. Remove the trace and nothing left supports the threshold finding, so under the
text the cap stays at the trace's 0.30 and POL-RD-10(1) escalates. The sentence carried no exception:
the admission-against-interest pattern is in the carrier subsection, and it is about what can carry a
fact, not about a limb. What the judge leaned on is the sentence's own "not a measurement", and the
removal test is what makes that reading stick here — the thing conceded is the route, and neither
artifact carries a distance.

The key reads the admission as an independent artifact carrying the deciding fact, which under
POL-GEN-02(2) would take the cap to the **maximum** of the weights (1.0) rather than the minimum, and
so to PARTIAL_REFUND 7.45 — the arithmetic the judge itself calls correct. That is the disagreement,
and it is a property of the amended text, not a slip in reading it.

### 211 — misapplied

The judge's own sentence:

> **It is his account, not a measurement** and fixes no position; it therefore cannot satisfy a limb
> whose test is the GPS measurement, and **it does not stop the impaired trace being the only
> measurement evidence of the dwell**.

The sentence it was applying is the second half of the bridging paragraph: *"Where the test admitted
no reading at all, an account offered in its place is standing in for the test: it neither lifts the
cap nor stops the impaired artifact being the only evidence, unless the policy names it."*

**Misapplied**, because the condition it turns on is false. The trace did admit readings: the judge
its own findings record a 168 s loss of fixes from 12:33:40 to 12:36:28 that "split the driver's
in-geofence presence into a 220 s run and a 112 s run". Readings on both sides of the gap is exactly
the case the *preceding* sentence governs — *"A contemporaneous record from inside a stretch the test
left unobserved, **lying between readings the test admitted**, counts for the cap and for any
question whether something is the only evidence."* The driver's 12:35:10 message lies in that gap, so
it counts for the cap, and the trace is not "the only measurement evidence" in the sense that
sentence means.

The judge's *limb* conclusion is right under the amendment: a message cannot satisfy a limb whose
test is a measurement, and limb (c)'s 300 s hold cannot be made out of the driver's own words. The
misapplication is on the **cap**, one step later — the bridging sentence that would have counted the
message for it was not applied. This is the same contested reading of POL-GEN-02(2) that `c21379b`
recorded for 211, now reached by a different route.

## 5. The external case, 901

`--external data/external/ryde/case-00901.json` produced **ESCALATE, confidence 0.6**, no amount, no
driver compensation, no referral — moving from the 1.00 PARTIAL_REFUND with 3.20 compensation the
previous invocation produced. Both channels are current for it (brief `db5b6b95…` rebuilt identically,
prompt `eece65ee58ab…`), and `matched` is `null`: it is never scored.

The ruling's own explanation, verbatim, is why:

> WHAT CANNOT BE DECIDED. POL-NS-01 limbs (b) and (c) must be proved from the GPS trace
> (EV-GPS-00901). That artifact is impaired: weight_multiplier 0.6, issue codes LOW_SAMPLE_RATE and
> PARTIAL_RECORD — sampling gaps of up to 240 seconds inside the waiting window, fewer than six fixes
> across it, the rider track omitted, and no horizontal-accuracy figure on any of its eight fixes.
> Under POL-NS-02 a fix reporting no accuracy is evidence of neither presence nor absence, so not one
> fix establishes arrival. The test those limbs require therefore could not be run: limbs (b) and (c)
> are UNDECIDED over the waiting window, not failed.

> It equally disposes of the driver's contrary argument (claims 3 and 10): the trip record's arrival
> marker is auto-confirmed from the same GPS measurement, so marker and trace are one carrier and not
> two, and the chat log is the driver's own account, which may not stand in for a measurement the
> test never admitted.

> CONSEQUENCE. The fact that decides this dispute — the driver's in-geofence presence and dwell — is
> carried only by an artifact impaired under POL-NS-08(b). POL-NS-08 therefore caps any monetary
> ruling at PARTIAL_REFUND and escalates the case under POL-NS-09; POL-NS-09(e) makes that escalation
> terminal, and POL-NS-09(a) applies independently because confidence is capped at 0.6, below the
> 0.70 floor. The SGD 5.00 is HELD — neither collected nor refunded — pending review.

This is the ruling the repository's own policy text supports. The case's deciding fact has one
measurement behind it and that measurement is impaired under POL-NS-08(b); POL-NS-09(e) makes the
escalation terminal and holds the fee. The previous run's PARTIAL_REFUND 1.00 rested on the
impaired trace, which is the departure
`docs/notes/2026-09-23-external-sample-case.md` recorded at the time. The amended prompt closes it.
The judge also keeps the fare point live for the reviewer: `EV-FARE-00901` charged SGD 5.00 where the
fee schedule yields SGD 4.00 for a STANDARD-zone RYDE_X trip, a POL-NS-08(d) integrity defect — but
no money moves while the case is escalated.

## 6. The net result

**901 moved to the ruling this policy's text supports; 107 moved away from the key; 211 is
unchanged.** Of 29 corpus cases, 28 held and one — 107 — moved, in the direction the key does not
want; 211 was already the single miss and stayed one. The external case moved from a monetary ruling
the policy does not permit to the escalation it requires. No prompt was changed in this session, and
no result file was edited.

## 7. What this does not establish

It does not score 901: `matched` is `null` and no answer key exists for it, so "the text supports this
ruling" is a reading of the policy, not a measurement against a key. It does not show that the
amended prompt is worse than the one before it on the corpus — 28/29 against 28/29, with a different
single-case failure in each, and one case moved — because a single run at one temperature cannot
separate a one-case difference from sampling noise. And it does not settle 107 or 211: both are
recorded here as contested readings of POL-GEN-02(2)'s cap, with the judge's sentence and the prompt
sentence it applied set side by side so the next reader can disagree with this note rather than
re-derive it.
