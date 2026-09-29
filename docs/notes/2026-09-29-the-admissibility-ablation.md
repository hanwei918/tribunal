# The admissibility ablation, measured on both development sets

The `admissibility` ablation was built on 2026-09-28 as task 3 of that day's
queue: `--ablate admissibility` removes the `admissibility` object from every
artifact in the brief, applied only in `build_brief_for_case`, off by default and
refused with every replay flag. It had been checked by hand on single cases — the
2026-09-28 note reads case 201's ablated brief to show that derived text computed
from a null payload still says MISSING — and had no figure. This session is the
run over both development sets.

**No model call was made here.** The owner ran the four commands below outside
the sandbox, off-peak on 2026-09-29; their output is committed byte for byte, and
every figure below is read out of the committed files or out of the headline
runs they are compared against.

    python3 -m eval.run_benchmark --ablate admissibility --concurrency 2
    python3 -m eval.development_sets --set codex --ablate admissibility --concurrency 2

The first pass at the default 600-second timeout lost seven cases on the corpus
and three on the second set. Each failure was re-run with the same command plus
`--timeout 900`, and every case has a result:

    python3 -m eval.run_benchmark --ablate admissibility --concurrency 2 --timeout 900
    python3 -m eval.development_sets --set codex --ablate admissibility --concurrency 2 --timeout 900

The two directories — `runs/ablation/admissibility/deepseek-deepseek-flash/`
(63 files: 29 cases, their transcripts, `calls.json`, `events.jsonl`,
`invocations.json`, `report.md`, `run.json`) and
`runs/codex/ablation/admissibility/deepseek-deepseek-flash/` (35 files: 15 cases
and the same six run-level files) — are committed as `35eead2`, 98 files, 2,045
insertions, unchanged. Nothing in `tribunal/`, `prompts/` or `policy/` moved.

## 1. The two invocations in each directory

`invocations.json` is append-only and holds both passes; `run.json` describes
only the last one, which is why its `cases.completed` lists the seven corpus
cases (and the three codex cases) that were retried while `cases.cached` lists
the twenty-two (and twelve) that were not re-asked.

| set | pass | started | ended | timeout | commit | completed | failed | tokens |
|---|---|---|---|---|---|---|---|---|
| corpus | 1 | 12:10:05Z | 14:02:44Z | 600 s | `43766b6` | 22 | 7 | 4,705,230 |
| corpus | 2 | 15:01:59Z | 15:31:36Z | 900 s | `cccc2e3` | 7 | 0 | 1,490,233 |
| codex | 1 | 12:10:05Z | 13:01:41Z | 600 s | `43766b6` | 12 | 3 | 2,104,040 |
| codex | 2 | 13:11:25Z | 13:31:06Z | 900 s | `cccc2e3` | 3 | 0 | 708,480 |

The corpus first pass lost 101, 102, 212, 213 and 214 to `TRANSPORT`
(`RemoteDisconnected: Remote end closed connection without response`) and 109 and
110 to `TIMEOUT` (`TimeoutError: The read operation timed out`); the second set
lost 9101 and 9102 to `TRANSPORT` and 9111 to `TIMEOUT`. Those seven and three
`case_failed` events are still in the event logs, alongside the 29 and 15
`ruling` events the two passes produced between them — 1,052 events in the corpus
log, 524 in the codex log, two `invocation_start`/`invocation_end` pairs in each.

The timeout was raised rather than the case re-asked at 600 s for the reason the
failure text gives: a `TIMEOUT` means the client stopped waiting and the provider
may have generated the answer anyway, so the tokens are billed either way. The
retry is a longer wait, not a second sample.

## 2. The four-field score, with and without the precheck

Neither headline `report.md` carries these figures: each was overwritten by its
own retry invocation and now grades a single case (corpus 207, codex 9115). The
headline numbers below come from `run_benchmark.grade_run` over the whole
directory, which is the only reading that covers every case; the ablated numbers
agree with the committed `report.md` in both directories.

| set | run | four-field | `ruling` | `amount_sgd` | `driver_compensation_sgd` | `referrals` |
|---|---|---|---|---|---|---|
| corpus | headline | **29/29** | 29/29 | 29/29 | 29/29 | 29/29 |
| corpus | ablated | **26/29 = 89.7%** | 26/29 | 26/29 | 28/29 | 29/29 |
| codex | headline | **14/15** | 15/15 | 14/15 | 15/15 | 15/15 |
| codex | ablated | **14/15 = 93.3%** | 14/15 | 14/15 | 15/15 | 14/15 |

The second set's four-field figure is unchanged, so on this pair of runs the
ablation costs three cases on the corpus and none on the second set. It is not
the same 14/15: the headline fails 9111 on `amount_sgd` alone (`expected 10.15,
produced 9.15`), and the ablated run fails 9111 on `ruling`, `amount_sgd` and
`referrals`.

Escalation calibration moves with it. The corpus produces six escalations where
the key expects five — rate 20.7% against a 17.2% target, precision 4 of 6,
recall 4 of 5 — with over-escalations 107 and 211 and the under-escalation 112.
The second set produces five where the key expects four, the over-escalation
being 9111. The INDETERMINATE cases are counted separately and are where the
damage is worst: the corpus escalates 3 of the 4 the key escalates, so 112 is
ruled confidently on a record that does not settle the question.

Each case file records `matched`, which is the ruling's agreement with the key
rather than anything about the brief: true on 26 of the 29 corpus ablated cases
and 14 of the 15 codex ablated cases, the same counts as the `ruling` field. The
brief digest is recorded separately, in `brief_sha256`.

## 3. The four cases whose outcome differs

Four cases move: 107, 112 and 211 on the corpus, 9111 on the second set. In each,
the headline's brief carried an `admissibility` object on all seven artifacts and
the ablated brief carries none.

| case | key | headline | ablated |
|---|---|---|---|
| 107 | `PARTIAL_REFUND` 7.45 (HARD) | `PARTIAL_REFUND` 7.45, conf 0.90, vote 0.75 | `ESCALATE`, conf 0.00, vote 0.50 |
| 112 | `ESCALATE` (INDETERMINATE) | `ESCALATE`, conf 0.40, vote 1.00 | `DRIVER_COMPENSATION` 1.80, conf 0.85, vote 1.00 |
| 211 | `PARTIAL_REFUND` 2.00 (HARD) | `PARTIAL_REFUND` 2.00, conf 0.80, vote 0.75 | `ESCALATE`, conf 0.00, vote 0.50 |
| 9111 | `PARTIAL_REFUND` 10.15 + POL-RD-09(4) referral (HARD) | `PARTIAL_REFUND` 9.15 with the referral, conf 0.90, vote 1.00 | `ESCALATE`, conf 0.00, vote 0.50 |

### 107 — an over-escalation

Impaired and missing artifacts: `EV-GPS-00107` `GPS_TRACE`, weight **0.3**,
`IMPAIRED`, issues `GPS_DRIFT` and `IMPLAUSIBLE_SPEED`; `EV-ADVIS-00107-01`
`TRAFFIC_ADVISORY`, weight **0.0**, `MISSING`, issue `MISSING_ARTIFACT`.

The headline's referee decided 14 claims: 10 `KEPT` and four `DISCARDED` under
`IMPAIRMENT_UNDISCLOSED`, and `discarded_claims` lists eight entries covering
those four distinct texts, each recorded twice. The ablated referee saw the same
14 claims and kept all 14; `discarded_claims` is 0. The four discarded claims are
exactly the ones that carry this case — that the trace's schema impairment is not
a policy impairment under POL-RD-07, that the excess is 3.57 km and 25.5% and so
below both POL-RD-01 materiality gates, that the excess can only be measured on
`gps_trace.trace_distance_km`, and that no advisory covers the driver's
diverted corridor. Removing the disclosure requirement un-discards all four, and
the panel then splits: drafts 1 and 4 escalate, drafts 2 and 3 carry
`PARTIAL_REFUND` 7.45. Two of four is below the three needed, so nothing is
published and the dispute is escalated.

### 112 — a unanimous escalation turned into a unanimous answer

Impaired and missing artifacts: `EV-TRIP-00112` `TRIP_RECORD`, weight **0.4**,
`IMPAIRED`, issue `CROSS_SOURCE_CONFLICT`; `EV-GPS-00112` `GPS_TRACE`, weight
**0.4**, `IMPAIRED`, the same issue; `EV-ADVIS-00112-01` `TRAFFIC_ADVISORY`,
weight **0.0**, `MISSING`, issue `MISSING_ARTIFACT`.

This is the one case the discard mechanism does not explain. Both runs discarded
nothing — 19 claims kept in the headline, 12 in the ablated run, `discarded_claims`
0 in both — and both panels were unanimous, vote 1.00. What changed is what the
advocates argued: without an impairment to disclose and discount, they made seven
fewer claims and stopped arguing about weight, and the judge then found for the
driver on the merits. The ablated ruling holds the deviation established on the
governing trace figure of 22.4 km against the trip record's rounded 20.0 km, finds
no distance refund payable (the recomputed fare of 25.64 exceeds the 25.26
charged), and compensates the driver for the 2.4 km the fare did not bill at 0.75
per kilometre: **1.80**, on the 0.05 grid, at confidence 0.85 and vote 1.00.

The key escalates 112 because the record does not settle it. The ablated run
answered it, unanimously and confidently, which the report counts as the failure
that matters most.

### 211 — an over-escalation

Impaired and missing artifacts: `EV-GPS-00211` `GPS_TRACE`, weight **0.39**,
`IMPAIRED`, issues `GPS_GAP` and `LOW_COVERAGE`; `EV-ADVIS-00211-01`
`TRAFFIC_ADVISORY`, weight **0.0**, `MISSING`, issue `MISSING_ARTIFACT`.

As on 107, the headline's referee decided 19 claims: 14 `KEPT` and five
`DISCARDED` under `IMPAIRMENT_UNDISCLOSED`, with ten `discarded_claims` entries
covering those five distinct texts; the ablated referee kept all 19 and discarded
nothing. The discarded claims are the five that turn on the trace's 0.39 weight
and on the missing advisory: that POL-NS-06(i) is unavailable because the advisory
is missing, that the chat log does not make up the 168-second outage, that the
disputed $4.00 cannot be left collected even if the shortfall is not found, that
the 0.39 weight does not cap the ruling below the 0.70 floor, and that the driver
does not rely on limb (i). Un-discarded, the panel splits three ways: drafts 1 and
4 `DRIVER_COMPENSATION` 3.20, draft 2 `FULL_REFUND` 4.00, draft 3 `PARTIAL_REFUND`
2.00. Nothing carries and the case escalates.

### 9111 — the money was already wrong

Impaired and missing artifacts: `EV-ADVIS-09111-01` `TRAFFIC_ADVISORY`, weight
**0.0**, `MISSING`, issue `MISSING_ARTIFACT`. Every other artifact in the case is
`COMPLETE` at 1.0, and the GPS trace is not impaired.

The headline's referee decided 19 claims: 18 `KEPT` and one `DISCARDED` under
`IMPAIRMENT_UNDISCLOSED` — the claim that no exculpatory closure can be raised
because the only advisory is missing, listed twice in `discarded_claims`. The
ablated referee kept 17 and discarded nothing.

The ablation did not change the money here. All four ablated drafts propose
`PARTIAL_REFUND` 9.15, exactly what the headline published; the key wants 10.15,
so the headline already failed this case on `amount_sgd`. What the ablation
changed is the referral: in the headline all four drafts carried the POL-RD-09(4)
billing-integrity finding, and in the ablated run only drafts 3 and 4 do. The vote
is taken on the four graded fields together, so a referral carried by half the
panel costs the panel its quorum: at most 2 of 4 agreed, nothing is published, and
a unanimous 9.15 becomes an `ESCALATE`. The ablation moved 9111 from failing on
one field to failing on three, but the underlying amount was wrong in both runs.

## 4. What 107 and 211 can and cannot show

On 107 and 211 the headline panel was **already split**: both were carried 3 of 4
on `PARTIAL_REFUND`, and the third agreeing draft is what carried them. In the
ablated run the panels are split the other way — 2 of 4 on `ESCALATE`, the other
two still on `PARTIAL_REFUND` 7.45 on 107 — and three were needed. Both conditions
sit one draft either side of the threshold.

So one sampled run per condition cannot separate the ablation's effect from
sampling variation on those two cases. It is possible to read the corpus drop as
"three cases lost"; the honest reading is one case lost cleanly (112), two cases
where a single changed draft would have carried or lost the ruling either way
(107 and 211), and one case whose money was already wrong before the ablation ran
(9111). A claim that the precheck is worth three corpus cases would need more
than one sample per condition.

112 is the opposite and needs no such caveat: unanimous `ESCALATE` became
unanimous `DRIVER_COMPENSATION` 1.80, every draft moved, and the ablation is the
only thing that changed between them.

## 5. What the ablated brief still carries

The ablation is real and reproducible: rebuilding the brief from the loaded case
with `brief.build_brief_for_case(case, ablate="admissibility")` reproduces the
recorded digest in both conditions, for all four cases.

| case | plain digest | headline `brief_sha256` | ablated digest | ablated `brief_sha256` | `admissibility` objects |
|---|---|---|---|---|---|
| 107 | `fef53c924442c2da…` | same | `ec1ddba78a520f5d…` | same | 7 of 7 → 0 of 7 |
| 112 | `e5ba8b93c559e529…` | same | `f68cdc24a14765c0…` | same | 7 of 7 → 0 of 7 |
| 9111 | `7ff86e5262e7fc0b…` | same | `5f7e1d5a489edfcf…` | same | 7 of 7 → 0 of 7 |

A `MISSING` artifact keeps its `evidence_id` and its null payload in both. The
advisory's key set in the plain brief is `admissibility`, `evidence_id`,
`evidence_type`, `generated_at`, `payload`, `schema_version`, `source`, `trip_id`;
in the ablated brief it is the same list without `admissibility`.

What the ablated brief still carries is text that says `MISSING`:

- The general policy clause the referee reads, `.policies.general.clauses[1].rule`,
  still defines the term — "A MISSING artifact has weight 0.0, can carry no fact,
  and its absence is itself citable" — in all four cases.
- Case 211's trace still carries derived text computed from the pool, at
  `.case.evidence[1].payload.derived.arrival.accumulated_dwell.limb.unavailable[1]`,
  which says "EV-ADVIS-00211-01 is MISSING, and POL-NS-06(i) requires a
  traffic_advisory that is present and populated: a MISSING traffic_advisory makes
  limb (i) unavailable, and asserting it against a MISSING artifact triggers
  POL-NS-09 rather than exonerating anyone". 211's ablated brief also still
  carries the category clause `.policies.category.clauses[5].rule`.

Counting the word across the whole canonical brief: 107, 112 and 9111 go from
four occurrences to one, 211 from nine to six. On 107, 112 and 9111 the one that
remains is the general policy clause. On 211 the six are that clause, twice in the
category clause, and three times in the derived reason quoted above.

So the ablated brief carries no admissibility **object**, which is not the same as
carrying no admissibility information. The referee that reads it has no
per-artifact weight to discount, but it is still told what a missing artifact is
and, on 211, that one is missing. This is the boundary of what the ablation
measures: it measures the effect of removing the disclosed weights, not the effect
of hiding the impairment.

## 6. Tokens

| set | first pass | retry | for the case set |
|---|---|---|---|
| corpus | 4,705,230 | 1,490,233 | 6,195,463 |
| codex | 2,104,040 | 708,480 | 2,812,520 |
| both | 6,809,270 | 2,198,713 | 9,007,983 |

`reused_from_cache` in each retry equals the first pass's `consumed_this_invocation`
exactly (4,705,230 and 2,104,040), which is how the retry records that it re-read
the cached cases rather than re-asking for them. `billed_to_another_run` is 0 in
both directories, unlike the codex headline, which carries 55,306 for the
advocates replayed into it.

## 7. What this is and is not

This is **one run per set on development data**, four judge drafts per case, taken
on 2026-09-29 at `prompts_sha256 5b8510cd…`. It is not the sealed figure and it is
not a generalisation result. The judge prompt is not frozen: it may still change
until 6 October 2026, and then only for failures that reproduce on both
development sets, with every change regression-run across all of them. The
generalisation figure is a fresh sealed set, drafted blind, run once after the
10 October freeze. Nothing here speaks to that set, and the corpus and codex
figures are not averaged into one number.
