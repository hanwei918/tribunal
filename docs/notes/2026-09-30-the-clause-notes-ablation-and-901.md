# The clause-notes ablation, and the organisers' sample case re-run

The `clause-notes` ablation was built on 2026-09-28 as task 3 of that day's
queue, alongside `admissibility`: `--ablate clause-notes` builds the brief with
`include_clause_notes=False`, so every clause's drafting `notes` is removed from
the brief's `policies`. The clause ids, the `rule` text and the structured fields
are unchanged — a limb still reads as it read; what is gone is the commentary
around it. It applies only in `build_brief_for_case`, is off by default, and is
refused with every replay flag. The `admissibility` ablation was measured and
committed on 2026-09-29 (`35eead2`,
`docs/notes/2026-09-29-the-admissibility-ablation.md`); the `clause-notes` one
had no figure until now. This session is that run over both development sets,
plus a re-run of the organisers' sample case under the current pipeline.

**No model call was made here.** The owner ran the three commands below outside
the sandbox, off-peak on 2026-09-29 from 23:3x SGT; their output is committed
byte for byte, and every figure below is read out of the committed files or out
of the headline runs they are compared against.

    python3 -m eval.run_benchmark --ablate clause-notes --concurrency 2 --timeout 900
    python3 -m eval.development_sets --set codex --ablate clause-notes --concurrency 2 --timeout 900
    python3 -m eval.run_benchmark --external data/external/ryde/case-00901.json \
        --runs-dir runs/rerun-2026-09-29 --timeout 900

**All 44 ablation cases completed on the first pass.** Unlike the admissibility
ablation, neither directory holds a retry: each `run.json` records
`stop_reason completed`, `failed` empty and one invocation only.

Three directories are committed:

| directory | files | commit | what it is |
|---|---|---|---|
| `runs/ablation/clause-notes/deepseek-deepseek-flash/` | 63 | `89c616e` | the corpus, 29 cases |
| `runs/codex/ablation/clause-notes/deepseek-deepseek-flash/` | 35 | `89c616e` | the second set, 15 cases |
| `runs/rerun-2026-09-29/external/ryde/` | 6 | `23589e1` | the sample case, re-run |

The first two are the ablation, committed unchanged in one commit; the third is
the sample-case re-run, committed unchanged in another. The re-run went to its
own runs root so that the committed `runs/external/ryde/` result — the one
`docs/notes/2026-09-23-external-sample-case.md` is about — stays as it is.
Nothing in `tribunal/`, `prompts/` or `policy/` moved, and the answer key is
untouched.

| run | invocation | started (Z) | ended (Z) | commit | python | schema |
|---|---|---|---|---|---|---|
| corpus | `20260929T154957.277781+0000-82356` | 15:49:57.233326 | 17:39:14.240983 | `cccc2e3` | 3.11.14 | 2 |
| codex | `20260929T154957.277751+0000-82358` | 15:49:57.234002 | 16:34:56.514553 | `cccc2e3` | 3.11.14 | 2 |
| 901 | `20260929T154957.277907+0000-82359` | 15:49:57.277730 | 15:57:11.469041 | `cccc2e3` | 3.11.14 | 2 |

The external run's `run.json` records no `ended_at`, so the 901 figure in the
last column of that row is its case file's `recorded_at`, which is when the
ruling was written.

All three recorded `configuration` with `ablation` `clause-notes` (the two
ablation runs) or `null` (901), `judge_votes` 4, `policy_version` 1, `precedents`
`null` and `verify_drafts` false. Each event log verifies intact:
`eval.events --path … --verify` reads 913 lines in the corpus log, 474 in the
codex log and 34 in 901's.

## 1. The four-field score under all three conditions

Neither headline `report.md` carries a whole-directory figure: each was
overwritten by a later invocation and now grades a single case at 1/1 = 100.0%
(the corpus directory holds 19 invocations, the codex one 11). So the headline
numbers come from `run_benchmark.grade_run` over each directory, which is the
only reading that covers every case. The ablated numbers agree with each
committed `report.md`.

| set | run | four-field | `ruling` | `amount_sgd` | `driver_compensation_sgd` | `referrals` |
|---|---|---|---|---|---|---|
| corpus | headline | **29/29** | 29/29 | 29/29 | 29/29 | 29/29 |
| corpus | admissibility | **26/29 = 89.7%** | 26/29 | 26/29 | 28/29 | 29/29 |
| corpus | clause-notes | **27/29 = 93.1%** | 27/29 | 27/29 | 28/29 | 29/29 |
| codex | headline | **14/15** | 15/15 | 14/15 | 15/15 | 15/15 |
| codex | admissibility | **14/15** | 14/15 | 14/15 | 15/15 | 14/15 |
| codex | clause-notes | **14/15 = 93.3%** | 14/15 | 14/15 | 15/15 | 14/15 |

On the corpus the two ablations are one case apart — 27/29 against 26/29 — and
the second set reads 14/15 in all three conditions. **The codex 14/15 is not the
same 14/15 each time.** The headline fails 9111 on `amount_sgd` alone
(`expected 10.15, produced 9.15`); both ablations fail it on `ruling`,
`amount_sgd` and `referrals`, which is what makes the ablated codex `ruling`
tally 14/15 where the headline's is 15/15.

Escalation calibration moves with the corpus figure. The headline produces
exactly the five escalations the key expects. The `clause-notes` run produces six
— `107, 110, 112, 207, 210, 213` — a rate of 20.7% against the 17.2% target,
precision 5 of 6 = 0.833, recall 5 of 5 = 1.0, with one over-escalation (107) and
no under-escalation. The `admissibility` run also produces six, but not the same
six: it over-escalates 107 **and** 211 and under-escalates 112. That difference
is the clearest single line between the two ablations: the precheck's removal
costs an INDETERMINATE case its escalation, and the clause-notes removal does
not.

## 2. The three corpus cases, and the one the precheck alone moves

Four cases differ from the key somewhere in this table. Confidence and vote
agreement are the run's own recorded fields; `vote` is the share of the judge's
four drafts that agreed on the published ruling, and it is not the confidence.

| case | key | headline | admissibility | clause-notes |
|---|---|---|---|---|
| 107 | `PARTIAL_REFUND` 7.45 (HARD) | `PARTIAL_REFUND` 7.45, conf 0.90, vote 0.75 | `ESCALATE`, conf 0.00, vote 0.50 | `ESCALATE`, conf 0.00, vote 0.50 |
| 112 | `ESCALATE` (INDETERMINATE) | `ESCALATE`, conf 0.40, vote 1.00 | `DRIVER_COMPENSATION` 1.80, conf 0.85, vote 1.00 | `ESCALATE`, conf 0.40, vote 1.00 |
| 211 | `PARTIAL_REFUND` 2.00 (HARD) | `PARTIAL_REFUND` 2.00, conf 0.80, vote 0.75 | `ESCALATE`, conf 0.00, vote 0.50 | `DRIVER_COMPENSATION` 3.20, conf 0.85, vote 0.75 |
| 9111 | `PARTIAL_REFUND` 10.15 + POL-RD-09(4) (HARD, second set) | `PARTIAL_REFUND` 9.15 with the referral, conf 0.90, vote 1.00 | `ESCALATE`, conf 0.00, vote 0.50 | `ESCALATE`, conf 0.00, vote 0.50 |

### 107 — the same miss, by a different route

107 misses under both ablations and for reasons that are not the same. Under
`admissibility` the referee kept all 14 claims and the panel split 2-2 on the
merits. Under `clause-notes` the referee discarded 2 of 17 claims and the panel
lost a draft to an **abstention**: the recorded explanation says draft 3
"abstained -- DRAFT_CLAUSE_UNRESOLVED: 'POL-NS-05' does not resolve in the
loaded policy; DRAFT_CLAUSE_UNRESOLVED: 'POL-NS-07' does not resolve in the
loaded policy", leaving drafts 1 and 4 on `ESCALATE` and draft 2 alone on
`PARTIAL_REFUND` 7.45. The explanation's own arithmetic: "At most 2 of 3 valid
drafts agreed and 3 were needed."

So on this run 107 is escalated because a draft abstained, not because the panel
divided on the merits. The clause ids are not changed by this ablation, so
whether the removal of the notes caused that citation is not something one run
can show; what is recorded is the abstention and the vote it produced.

### 112 — it misses only when the precheck is removed

112 is the cleanest result in this session and it belongs to the other ablation.
It is `matched` in the headline and `matched` again under `clause-notes` — both
runs publish `ESCALATE`, the ruling the key requires, at confidence 0.40 with a
unanimous panel. Only the `admissibility` run answers it, with
`DRIVER_COMPENSATION` 1.80 at confidence 0.85 and vote 1.00. Under
`clause-notes` the referee discarded more (8 of 21 claims against the headline's
0 of 19) and the ruling did not move: the panel still escalated, unanimously, for
the two reasons the explanation gives — POL-RD-10(1) caps confidence at the 0.4
weight of the artifacts carrying the deciding facts, and POL-RD-10(4) fires on
two admitted artifacts whose pickup timestamps disagree by more than ten
minutes.

**112 misses only when the admissibility precheck is removed.** That is a
statement about these two runs and not a claim that the precheck is worth a
corpus case; see section 3.

### 211 — a confident monetary ruling under the clause-notes ablation

Under `clause-notes` the panel finds for the driver on the merits:
**`DRIVER_COMPENSATION` 3.20 at confidence 0.85**, carried 3 of 4 (vote 0.75),
where the headline published `PARTIAL_REFUND` 2.00 and the admissibility run
escalated. This is not the admissibility mechanism at work — the referee here
discarded 4 of 23 claims, so the impairment disclosure was present and used.

The explanation names the impairment it relied on and works the clause: the trace
`EV-GPS-00211` is impaired with `GPS_GAP` and `LOW_COVERAGE`, a 168-second outage
from 12:33:40 to 12:36:28 inside the waiting window, coverage 84.3%, weight
**0.39**. On its own that splits the hold into runs of 220 s and 112 s, an
80-second shortfall. The driver's contemporaneous message at 12:35:10 —
`EV-CHAT-00211`, weight 1.0, unimpaired — lies inside the outage and bridges it,
so the hold runs 500 seconds from the first qualifying fix at 12:30:00 to the
12:38:20 cancellation, past the 300-second STANDARD minimum. Because the bridging
record is independent of the trace, POL-GEN-02(2)'s cap is the **maximum** of
0.39 and 1.0 rather than the minimum, POL-NS-08's sole-evidence sentence and
POL-NS-09(e) do not engage, and the 0.70 floor is cleared. POL-NS-07's
anti-farming check passes (`no_show_terminations_30d` 2, 2/146 = 1.4%), so the
SGD 4.00 fee stands and SGD 3.20 of it is paid to the driver, SGD 0.80 retained.

The amount is wrong against the key, which wants `PARTIAL_REFUND` 2.00, so the
case still fails — but it fails as a confident monetary ruling, not as an
escalation.

### 9111 — unchanged money, and now an escalation

9111 fails identically under both ablations: `ESCALATE` at confidence 0.00 with
a 2-2 panel. The headline had already got the money wrong (9.15 against the key's
10.15) while publishing `PARTIAL_REFUND`, so this is not damage the clause-notes
ablation did. Under `clause-notes` the referee discarded 1 of 17 claims — the
same count as the headline's 1 of 19, though not the same claim: the headline
discarded the rider's argument that no exculpatory closure can be raised because
the only advisory is missing, and the clause-notes run discarded the rider's
argument that the driver's statement does not discharge the shifted burden. In
neither run is the referral the key expects produced.

## 3. What 107 and 211 can and cannot show

**107 and 211 miss under both ablations, and both were carried 3 of 4 in the
headline, so one run per condition cannot separate either ablation's effect from
sampling variation on them.**

In the headline each was carried on `PARTIAL_REFUND` by three of four drafts,
sitting one draft above the quorum. In the ablated runs the panels are split the
other way or on another question, and the third agreeing draft is what is
missing. A single changed draft would have carried or lost the ruling either
way, so the corpus figures — 29/29, 26/29, 27/29 — cannot be read as "the
precheck costs three cases and the notes cost two". What they support is weaker
and still useful: the precheck's removal moves 112 cleanly and unanimously, the
notes' removal moves 211 to a confident but wrong monetary ruling, and 107 fails
under both for two different reasons. A claim that either ablation is worth a
specific number of corpus cases would need more than one sample per condition.

## 4. The organisers' sample case under the current pipeline

901 is the organisers' own sample case, converted into `data/external/ryde/` and
never scored: it has no entry in `eval/answers/ground_truth.json` and the runner
prints `graded: false`. The re-run asked the judge four times under the current
prompt and published:

| | re-run (`23589e1`) | committed `runs/external/ryde/` (third invocation, `c4c9a06`) |
|---|---|---|
| `ruling` | `ESCALATE` | `ESCALATE` |
| `amount_sgd` / `driver_compensation_sgd` | `null` / `null` | `null` / `null` |
| `confidence` | 0.6 | 0.6 |
| `vote_agreement` | 1.00 (4 of 4 valid, unanimous, threshold 3, carried) | `null` — the judge was asked once, so no vote block |
| `prompts_sha256` | `5b8510cd…` (the current prompts) | `829ccc8f…` |
| `brief_sha256` | `79403092…` | `db5b6b95…` |
| `schema_version` | 2 | 1 |
| `configuration` | the five switches, `ablation` null | `null` |
| tokens | 226,880 | 106,661 |
| `call_seconds` | 434.1 | 232.7 |

**The ruling and the confidence are the same.** The re-run escalates at 0.6, and
so does the committed schema-1 result; all four drafts propose `ESCALATE` with
both money fields `null` and no referrals, unanimously at agreement 1.00. The
2026-09-24 note already recorded the third invocation as ESCALATE at 0.6 and
argued that this is the ruling the repository's policy text supports, because the
deciding fact's only evidence is the trace impaired under POL-NS-08(b) and
POL-NS-09(e) holds the fee. Nothing in this re-run disturbs that reading.

Two things have moved around that stable ruling. Its **brief** no longer rebuilds
to its recorded digest: rebuilding 901's brief from the committed converted case
today hashes to `79403092…`, which is the re-run's digest and not `db5b6b95…`, so
`tribunal/brief.py` has moved since 2026-09-24 (the policy arithmetic, the gantry
geometry, the ablation switch and the policy versions all landed after it). And
its **prompt** channel has moved too: the committed result records
`829ccc8f…` where the code now renders `5b8510cd…`. The committed schema-1 result
is therefore stale on both channels; the re-run is current on the prompt channel
and `unknown` on the brief channel, because the staleness check rebuilds *corpus*
briefs by case number and 901 is not a corpus case.

**The organisers' stated expectation is not an answer.** `eval/external/ryde/expected.json`
records the source's outcome — "Cancellation charge UPHELD", with the four stated
reasons — and says in its own text that it is not part of the key, is not merged
into it, is not an input to any agent, and that "UPHELD" is the source's word
rather than a token this system emits. It is printed beside the produced ruling
and is not scored. So the honest comparison is: the organisers state that the
charge is upheld; this pipeline, on the same facts, declines to decide and sends
the case to a human reviewer at confidence 0.6, in both the committed run and
this one. Whether that is a disagreement about the facts or about the policy's
confidence floor is not settled by either run, and the stated expectation cannot
be used to settle it.

## 5. Tokens

| run | prompt | completion | reasoning | cached | consumed | billed elsewhere | failed |
|---|---|---|---|---|---|---|---|
| corpus clause-notes | 3,043,217 | 3,151,186 | 2,897,379 | 1,876,352 | **6,194,403** | 0 | 0 |
| codex clause-notes | 1,445,878 | 1,256,806 | 1,137,948 | 861,184 | **2,702,684** | 0 | 0 |
| both ablations | | | | | **8,897,087** | | |
| 901 re-run | 117,952 | 108,928 | 97,194 | 52,736 | **226,880** | — | 0 |
| 901 committed schema-1 | 50,607 | 56,054 | 51,016 | 17,664 | **106,661** | — | — |

Each ablation run made one invocation, so `consumed_this_invocation` and
`total_for_the_case_set` are the same figure and `reused_from_cache` is 0.
`billed_to_another_run` is 0 in both ablation directories. For comparison, the
admissibility ablation consumed 6,195,463 and 2,812,520 — 9,007,983 for the pair,
1,060 more on the corpus and 109,836 more on the second set than the
clause-notes pair, which is the cost of the ten retried cases rather than
anything about the ablation.

The 901 re-run cost 226,880 against the committed run's 106,661. The difference
is the vote: four judge calls where the committed run made one, on a larger
prompt (117,952 against 50,607), which is also why it took 434.1 seconds of call
time against 232.7.

## 6. What this is and is not

This is **one run per set on development data** for each ablation, and **one
re-run** of the sample case, four judge drafts per case, taken on 2026-09-29 at
`prompts_sha256 5b8510cd…`. It is not the sealed figure and it is not a
generalisation result. The judge prompt is not frozen: it may still change until
6 October 2026, and then only for failures that reproduce on both development
sets, with every change regression-run across all of them. The generalisation
figure is a fresh sealed set, drafted blind, run once after the 10 October
freeze. Nothing here speaks to that set. The corpus and codex figures are not
averaged into one number, and the sample case is not a score at all.

## 7. How to re-derive these figures

    from eval import grade, run_benchmark
    ck = grade.load_answer_key()                                  # corpus
    xk = grade.load_answer_key(Path("eval/answers/codex/ground_truth.json"))
    run_benchmark.grade_run(Path("runs/ablation/clause-notes/deepseek-deepseek-flash"), key=ck)

`grade_run` grades the cases the directory covers and returns `total`,
`exact_matches`, `field_tally(field)` and `calibration`. Rebuild a case's brief
from the **loaded** case (`loader.load_case(n)`,
`loader.load_external_case(Path("data/external/ryde/case-00901.json"))`) and hash
it with `brief.brief_digest`; hashing the raw JSON gives a different digest. The
event logs are checked with `python3 -m eval.events --path <log> --verify`, not
with `--runs-dir`, which looks one level lower under `<root>/<model>`.
