# The second development set's first run

**2026-09-25.** The fifteen cases `9101`–`9115` were run for the first time, at
commit `94a1c45`, through `python3 -m eval.development_sets --set codex`. The
directory is committed exactly as produced in `aa43d90`. This note records what
the run cost, what it scored, and — the part that matters — **what the two
failures are a failure of**, because both are the same error and neither is
about the cases.

The set itself is described in `docs/notes/2026-09-25-the-second-development-set.md`.
Nothing here changes that note's figures; this note is about one run of it.

## The run took two invocations

`invocations.json` records both, and neither is the whole run.

| | invocation 1 | invocation 2 |
|---|---|---|
| started | 12:01 | 13:16 |
| ended | 12:42 | 13:19 |
| command | `--set codex --token-budget 2200000` | `--set codex --cases 9115 --force` |
| balance | **the teammate's balance** | **the owner's balance** |
| requested | 9101–9115 | 9115 |
| completed | 9101–9114 | 9115 |
| `stop_reason` | `fatal error` | `completed` |
| billed | 1,234,679 | 84,404 |

The first invocation did not complete 9101–9115. It completed **9101–9114** —
twelve of the fourteen, since 9111 and 9113 came back wrong but came back — and
then **stopped** on 9115. The request against the teammate's balance was refused
with **HTTP 402, code 401006**: *"model `deepseek/deepseek-flash` is not
provisioned for this account; enable it at the TokenHub console, Service
invocation panel."* The runner records that as `failure_kind: TRANSPORT`, with
its own sentence that **retrying cannot help**.

That distinction is the reason this is written down rather than smoothed over.
9115 was not arbitrated and lost; the account never reached it. A run that
reports "14 of 15 with one failure" would be describing a case the model
answered badly, and this is not that.

The second invocation ran 9115 alone, on the owner's balance, and completed it.

## What the set reads

From the cache, by `python3 -m eval.development_sets --report`:

```
corpus   runs/deepseek-deepseek-flash             29/29      27/29   27/29  27/29  28/29  29/29
codex    runs/codex/deepseek-deepseek-flash       15/15      13/15   15/15  13/15  15/15  13/15
```

**Fifteen of fifteen produced, thirteen of fifteen exact.** The two failures are
**9111** and **9113**, and both fail on `amount_sgd` and on `referrals` only:

| case | ruling | amount_sgd | driver_compensation_sgd | referrals |
|---|---|---|---|---|
| `9111` | ok | **FAIL** — produced `9.15`, key `10.15` | ok | **FAIL** — produced none, key has one |
| `9113` | ok | **FAIL** — produced `8.05`, key `9.05` | ok | **FAIL** — produced none, key has one |

Both are short by exactly the **SGD 1.00** of one gantry line, and both name the
same mechanism. `ruling`, `driver_compensation_sgd` and `referrals` are otherwise
fifteen of fifteen.

Three cases the string comparison flags as referral "failures" — `9104`, `9108`,
`9114` — are not failures. Referrals are graded by the clause and limb they
name, not by their wording, so a differently-worded referral to the same clause
matches. Those three match.

## What the two failures are

**The key says, in its own words, what the missing fact is.** Its referral text
for the two cases reads:

- `9111`: *"POL-RD-09(4) billing-integrity referral: phantom ERP gantry lines on
  EV-FARE-09111, Pioneer Road inbound SGD 1.00 and Tuas South Avenue 8 loop
  SGD 2.00, **neither within 250 m of any GPS fix**"*
- `9113`: *"POL-RD-09(4) billing-integrity referral: phantom ERP gantry line on
  EV-FARE-09113, Pelton lawful diversion entry SGD 1.00, **not within 250 m of
  any GPS fix**"*

POL-RD-09(4) decides a gantry line **by geometry**: it matches a gantry to the
trace by comparing `erp_gantry.lat` and `erp_gantry.lng` against the trace,
treating any fix within **250 m** of the gantry as a crossing.

**The judge cannot run that test.** The brief replaces the trace's coordinates
with derived facts, and no derived fact says how close the trace came to any
gantry. So the judge reached for the nearest thing the brief does carry — the
`on_optimal_route` flag — and read it as though it were the geometric test.

On `9111` the judge's transcript says so outright:

> It is not a phantom line — the vehicle crossed it on the detour — so no
> billing-integrity referral arises.

That is an assertion about the trace's geometry, made with nothing in the brief
to support it, and it is wrong: the line is **912.0 m** from the nearest fix.

On `9113` the judge does not even reach the Pelton line. It takes
`on_optimal_route: true` as a match and never examines it; the line is
**834.2 m** from the nearest fix.

The same error is what the set's author made before the key was corrected — see
the corrections table in the set's own note, where `9111`'s answer moved from
9.15 to 10.15 and `9113`'s from 8.05 to 9.05 for exactly this reason. Corpus case
`115` and dev case `9114` were decided correctly only because the driver conceded
he never went there; the model never had to do the geometry.

This is the same failure as the accumulated dwell on corpus case `214`: **the
model could not see the fact because it was never computed.** The remedy is not
a prompt change; it is to compute the fact and put it in the brief. That is what
`docs/notes/2026-09-25-what-the-trace-came-close-to.md` records.

## What the run cost

**1,319,083 billed tokens** over the fifteen cases — 1,234,679 in the first
invocation and 84,404 in the second. `billed` is prompt + completion; reasoning
is a breakdown of completion and is never added to it.

| case | prompt | completion | of which reasoning | billed |
|---|---|---|---|---|
| 9101 | 47,092 | 45,612 | 41,509 | 92,704 |
| 9102 | 47,862 | 54,055 | 49,386 | 101,917 |
| 9103 | 47,345 | 26,994 | 23,274 | 74,339 |
| 9104 | 45,892 | 40,646 | 36,682 | 86,538 |
| 9105 | 47,335 | 41,049 | 36,743 | 88,384 |
| 9106 | 47,319 | 43,774 | 39,593 | 91,093 |
| 9107 | 47,917 | 29,957 | 26,235 | 77,874 |
| 9108 | 46,672 | 36,887 | 32,739 | 83,559 |
| 9109 | 43,465 | 49,861 | 45,345 | 93,326 |
| 9110 | 46,972 | 41,063 | 37,313 | 88,035 |
| 9111 | 44,990 | 72,257 | 68,604 | 117,247 |
| 9112 | 44,307 | 29,791 | 25,892 | 74,098 |
| 9113 | 46,151 | 29,938 | 25,606 | 76,089 |
| 9114 | 44,477 | 44,999 | 41,005 | 89,476 |
| 9115 | 45,020 | 39,384 | 34,916 | 84,404 |
| **total** | | | | **1,319,083** |

The two failures are also the two most expensive cases: `9111` at 117,247 is the
ceiling and `9113` at 76,089 is above the median. `9111` spent 68,604 tokens
reasoning — more than any other case — working out an answer it could not ground.

## Three files, and what each belongs to

`run.json`, `report.md` and `calls.json` **describe the last invocation, not the
run.** This is the runner's own rule and it shows here:

- `run.json` carries invocation 2's `cases.requested: [9115]`, its
  `git_commit: 94a1c45`, and `directory.cached_case_count: 15`.
- `report.md` grades **one** case — 9115, `ESCALATE`, a four-field match — and
  its escalation table says `Whole corpus graded | no — 1 of 15 cases`. Read
  alone it is a report of a one-case run, because that is what the last
  invocation was.
- `calls.json` holds invocation 2's **three** calls — two advocates and a judge
  — and their token sum is that invocation's 84,404 billed exactly. It is not a
  history: it is the last invocation's calls.

The set's figure is read **from the cache** by `--report`, which makes no model
call. `invocations.json` is the only file that is a history.

## Naming the balances

The two invocations were billed to **the teammate's balance** and **the owner's
balance** respectively. No key is written here, or anywhere in the run
directory, and none is needed to read the figures above.

## Hygiene

- **Credential scan** over the 34 committed files: no `sk-` match, the positive
  control fires, and both `TOKENHUB_API_KEY` and `TOKENHUB_API_KEY_TEAMMATE` are
  unset in this environment.
- `run.json` and `invocations.json` name the user in an absolute path
  (`run_dir`, `prompts_dir`). They are committed **as produced**, which is how
  the six already-committed run records look, including the corpus's own.
- The directory was committed in its own commit (`aa43d90`), before any change
  in this session, so the run and the work done about it are separable diffs.
