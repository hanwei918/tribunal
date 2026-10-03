# Policy gaps

**No model call was made.** Every figure is read out of the recorded runs: each case's transcript vote block, its rebuilt brief, and the precedent library.

Of a case file this reads five fields -- `case_no`, `ruling`, `brief_sha256`, `development_set` and `configuration` -- and no others, and of a transcript it reads the vote and verification blocks only. It never reads `matched`, a grade event or the answer key.

The runs:

- `runs/deepseek-deepseek-flash` (corpus) — 29 case(s) cached, 5 of them undecided
- `runs/codex/deepseek-deepseek-flash` (codex) — 15 case(s) cached, 4 of them undecided
- `runs/wild/deepseek-deepseek-flash` (wild) — 62 case(s) cached, 7 of them undecided

A cluster is flagged when it holds at least 2 case(s).

Dropped from every signature, because each appears in at least 80% of the given runs' cases and so distinguishes none of them:

- `TRAFFIC_ADVISORY:MISSING_ARTIFACT`

## C1 — NO_SHOW_CHARGE / below_confidence_floor

4 case(s); level 1; flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `210` | corpus | ESCALATE | 0.25 | - | awaiting review |
| `213` | corpus | ESCALATE | 0.0 | - | awaiting review |
| `626` | wild | ESCALATE | 0.0 | - | awaiting review |
| `9109` | codex | ESCALATE | 0.0 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 210, 213, 626, 9109.

## C2 — NO_SHOW_CHARGE / clause:POL-NS-07

3 case(s); level 1; flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `207` | corpus | ESCALATE | 0.9 | POL-NS-07 | awaiting review |
| `622` | wild | ESCALATE | 0.9 | POL-NS-07 | awaiting review |
| `9108` | codex | ESCALATE | 0.95 | POL-NS-07 | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 207, 622, 9108.

## C3 — NO_SHOW_CHARGE / judge_no_clause

1 case(s); level 1; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `9110` | codex | ESCALATE | 0.9 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 9110.

## C4 — ROUTE_DEVIATION / below_confidence_floor

6 case(s); level 1; flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `110` | corpus | ESCALATE | 0.39 | - | awaiting review |
| `112` | corpus | ESCALATE | 0.4 | - | awaiting review |
| `508` | wild | ESCALATE | 0.6 | - | PARTIAL_REFUND (P-0001) |
| `512` | wild | ESCALATE | 0.39 | - | awaiting review |
| `530` | wild | ESCALATE | 0.0 | - | PARTIAL_REFUND (P-0002) |
| `9115` | codex | ESCALATE | 0.6 | - | awaiting review |

Human decisions: PARTIAL_REFUND x2.
Awaiting review: 110, 112, 512, 9115.

## C5 — ROUTE_DEVIATION / judge_no_clause

1 case(s); level 1; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `504` | wild | ESCALATE | 0.70 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 504.

## C6 — ROUTE_DEVIATION / too_few_valid_drafts

1 case(s); level 1; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `501` | wild | ESCALATE | 0.0 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 501.

## C7 — NO_SHOW_CHARGE / below_confidence_floor / CHAT_LOG:MISSING_ARTIFACT, GPS_TRACE:MISSING_ARTIFACT

1 case(s); level 2; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `213` | corpus | ESCALATE | 0.0 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 213.

## C8 — NO_SHOW_CHARGE / below_confidence_floor / CHAT_LOG:TRUNCATED_LOG, GPS_TRACE:CLOCK_SKEW, GPS_TRACE:GPS_GAP, GPS_TRACE:LOW_COVERAGE, GPS_TRACE:LOW_SAMPLE_RATE, GPS_TRACE:PARTIAL_RECORD, GPS_TRACE:TRUNCATED_LOG, TRIP_RECORD:CROSS_SOURCE_CONFLICT

1 case(s); level 2; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `210` | corpus | ESCALATE | 0.25 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 210.

## C9 — NO_SHOW_CHARGE / below_confidence_floor / GPS_TRACE:MISSING_ARTIFACT

2 case(s); level 2; flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `626` | wild | ESCALATE | 0.0 | - | awaiting review |
| `9109` | codex | ESCALATE | 0.0 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 626, 9109.

## C10 — ROUTE_DEVIATION / below_confidence_floor / CHAT_LOG:TRUNCATED_LOG, FARE_BREAKDOWN:PARTIAL_RECORD, GPS_TRACE:GPS_GAP, GPS_TRACE:LOW_COVERAGE

1 case(s); level 2; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `110` | corpus | ESCALATE | 0.39 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 110.

## C11 — ROUTE_DEVIATION / below_confidence_floor / GPS_TRACE:CROSS_SOURCE_CONFLICT, TRIP_RECORD:CROSS_SOURCE_CONFLICT

1 case(s); level 2; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `112` | corpus | ESCALATE | 0.4 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 112.

## C12 — ROUTE_DEVIATION / below_confidence_floor / GPS_TRACE:GPS_GAP

1 case(s); level 2; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `9115` | codex | ESCALATE | 0.6 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 9115.

## C13 — ROUTE_DEVIATION / below_confidence_floor / GPS_TRACE:GPS_GAP, GPS_TRACE:LOW_COVERAGE

1 case(s); level 2; not flagged.

| case | set | system outcome | confidence | leading referral clause | human closure |
|---|---|---|---|---|---|
| `512` | wild | ESCALATE | 0.39 | - | awaiting review |

Human decisions: none — the library holds no closure for these cases.
Awaiting review: 512.

Not analysed, and why:

- none

