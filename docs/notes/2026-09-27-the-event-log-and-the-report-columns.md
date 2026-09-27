# The event log, and the report's per-case columns

**2026-09-27.** Two additions that make a run auditable after the fact.

The first is `runs/<run directory>/events.jsonl`: an append-only, hash-chained
log of everything an invocation did, one JSON object per line. The second is a
per-case block in the report — cost split by role, wall clock, whether the case
escalated, the vote agreement, where each amount came from, and four yes/no tags
describing the ruling's explanation — every value computed by code.

**No model call was made, and no prompt was changed.** Nothing in either addition
consults a model.

The log exists because of a failure on this date. A judge-only replay was started
at 13:03 and died at once: the model was not provisioned for the account
(`HTTP 402`, code `401006`), the first two cases failed, the run raised, and it
was over in 1.1 seconds. No tokens were billed and no result changed. Its only
record is the pair of entries it wrote into `invocations.json` — because the log
that would have recorded it did not exist yet. It does now.

## 1. The event log

### What it is for

`runs/<model>/` already holds four kinds of record, and none of them answers the
question this one answers.

| file | what it holds | why it is not enough |
|---|---|---|
| `case-<n>.transcript.json` | every call for one case, in full | per case, and rewritten whenever that case is re-run |
| `case-<n>.json` | that case's ruling and provenance | the result, not the process |
| `run.json` | **the last invocation** | overwritten by the next invocation |
| `invocations.json` | every invocation's summary | totals only — no ordering inside a case |
| `calls.json` | the last invocation's calls | a dict keyed `calls`, not a history |

`run.json` is the reason the log is needed. It is the conventional path a reader
looks at, and it describes exactly one invocation — the one that wrote it last.
The append-only history in `invocations.json` survives, but it is a summary: it
cannot say which case came before which, or what a draft proposed. The event log
is the one artifact that is cumulative **and** ordered.

### The append rule

Every invocation appends. Nothing in `tribunal/events.py` truncates, rewrites or
reorders the file, and **`--force` does not change that**: forcing a re-run skips
the cache, it does not clear the log. A test drives two invocations into one
directory and asserts that the first invocation's lines are still a byte-for-byte
prefix of the file, and a second asserts the same with `--force`.

The chain is continued rather than restarted: `EventLog` reads the last line's
`hash` and `seq` **off disk** when it opens, so a second invocation appends to the
first one's chain. A reader can therefore treat every line as a fact that was
true when it was written.

`record` holds a lock around the read-modify-append, because a run's cases are
worked by several threads and two threads appending at once would produce two
lines claiming the same `prev`.

### What a line carries

Every line carries its own context, not a header at the top of the file:

```
seq         0-based, dense, and continuous across invocations
ts          ISO-8601 UTC
event       one of the ten names below
invocation  the id of the invocation that wrote the line
case        the case number, or null for the invocation's own events
commit      the git commit the invocation ran at
prompts     the digest of the prompt directory it ran under
prev        the sha256 of the previous line's canonical body
hash        the sha256 of this line's canonical body
```

The context travels per line because a log that named its invocation only at its
head could not answer the question once a second invocation had appended to it.

The events, and what each carries beyond the context:

| event | payload |
|---|---|
| `invocation_start` | model, cases requested, concurrency, both limits, budget, `K`, development set, replay source |
| `invocation_end` | stop reason, cases graded, exact matches, and the three token ledgers named separately |
| `case_start` | position, total, and `cached` |
| `agent_call` | role, attempt, the request's digest, the usage split, seconds, the parse outcome |
| `referee_decision` | side (`RIDER`/`DRIVER`), status, reason code, detail |
| `judge_draft` | draft number, kind, seed, temperature, sides, the proposal, **every** draft check, abstention, `valid` |
| `vote` | votes, threshold, valid count, agreement, outcome, unanimity, the proposals that counted |
| `ruling` | the six POL-GEN-03 fields, or the failure that stopped the case |
| `case_failed` | failure kind, failed agent, detail |
| `grade` | expected and produced ruling, the four field verdicts, the four-field match |

Three details are worth stating because they are decisions rather than
transcriptions.

**`case_start` is written for a cached case too**, with `cached: true`. A run
whose cases are all cached does no work, but it was still asked for those cases
and it still decided to reuse them; a reader following one case through such a
run should not find a grade with nothing in front of it. The flag is what keeps
"this invocation began the case" apart from "this invocation did work".

**`agent_call` is written inside `_call_agent`**, once per attempt, so a retried
call is two events rather than one — the distinction the transcript has always
drawn. Its request digest is read off the transcript entry the attempt just
wrote, so the event is checked against what was sent rather than against an
intention.

**The pre-vote draft checks are recorded at `K ≥ 2` and are `null` at `K = 1`.**
At `K = 1` there is no panel for a malformed draft to abstain from, so the checks
are not a property of that draft. `null` says the check did not run; reporting
every code as passed would claim a check that was never made.

**A replay does not record advocate calls.** It did not make them. It records the
referee's decisions, because it ran the referee over the same claims, and the
drafts, the vote and the ruling, because it made those.

### What a line never carries

No credential, no request header, and no raw prompt. A line carries digests,
roles, token counts, durations, reason codes and the ruling. `tests/test_events.py`
scans a produced log for the house credential and for `sk-`, and — because a scan
that cannot fail proves nothing — includes a positive control that writes the
credential into a log and shows the same needles find it.

### Tamper evidence

Each line carries `prev`, the sha256 of the previous line's canonical body, and
`hash`, the sha256 of its own. Serialisation goes through
`money.dumps_canonical`, so the digest is taken over the exact bytes written.

`python3 -m eval.events --verify` walks the chain and reports the **first** break,
exiting non-zero when there is one. Three kinds:

* **`content`** — the line's own hash does not match its content. An edit is
  therefore reported **at the line that was edited**, not at the one after it.
  This is the check that runs first, and the order is deliberate.
* **`chain`** — `prev` does not name the previous line. A deleted, inserted or
  reordered line is reported at the first line that no longer agrees with its
  predecessor.
* **`malformed`** — the line is not a JSON object carrying every reserved field.

A tamperer who edits a line **and** recomputes its `hash` is still caught, one
line later, by the next line's `prev`. The first line carries `prev` equal to a
sentinel of 64 zeros, which no digest can take, so a first line that was moved
down the file cannot pass itself off as the beginning of the chain.

The chain is not a signature. It cannot prove the file was never rewritten by
someone who rewrote all of it; it can prove that the file a reader holds is the
file the run wrote.

### The two commands

```
python3 -m eval.events --case 211          # one case's full history, in order
python3 -m eval.events --case 211 --json   # the same, as raw JSON payloads
python3 -m eval.events --verify            # check the chain, name the first break
```

`--path` names a log directly; otherwise `--run-dir`, or `--model` with `--set`,
resolves the conventional location. Both commands are read-only: no model call,
no write, no cache entry touched.

The log of the cached re-run described in §2 prints, for case 211:

```
case 211 — 2 event(s) in .../events.jsonl
2026-09-27T08:25:38.436466+00:00  case_start            case 211  cached=True
2026-09-27T08:25:49.718634+00:00  grade                 case 211  matched=False
```

## 2. The report's per-case columns

`runs/<model>/report.md` and the development-sets report now carry one row per
case:

| column | where the value comes from |
|---|---|
| `advocate tokens` | summed off the case's transcript, by role |
| `judge tokens` | summed off the case's transcript, by role |
| `wall s` | the cache entry's own wall clock, not the sum of its calls |
| `escalated` | whether the produced ruling is `ESCALATE` |
| `vote agreement` | the cache entry's `vote_agreement`; a dash at `K = 1` |
| `amount_sgd from` | the money-block figure it reads off, or the figures it sums |
| `driver_compensation_sgd from` | as above |
| `cites evidence` | pattern over the explanation |
| `cites clause` | pattern over the explanation |
| `shows arithmetic` | pattern over the explanation |
| `names a gap` | pattern over the explanation |

### The amount provenance

Four answers, kept apart rather than folded together:

* **a path** — the money-block figure the amount equals
  (`refund.payable.value`), or the paths of the figures it sums
  (`fare_breakdown.platform_fee + fare_breakdown.erp_gantries`);
* **`unverifiable: not structured`** — the figure governing the amount is one
  the block marks as prose-only, so there is nothing to read it off;
* **`n/a`** — the field carries no amount at all, which is what `ESCALATE` and
  `NO_ACTION` both do;
* **`not a published figure`** — the amount is a number and reads off nothing.
  This is not one of the three answers the request named, and it is the one that
  matters most: it is a draft's own number.

A fifth answer appears when the brief cannot be rebuilt at all: **`brief not
available`**. It is named rather than left blank, because "the brief could not be
rebuilt" and "the ruling carried no amount" are different findings.

This is computed in `eval/run_benchmark.py`, not in `eval/grade.py`, and the
reason is a boundary the grader keeps: its whole dependency on `tribunal` is the
ruling vocabulary, so that no key value can ever reach a prompt, a brief or a
transcript. Reading the money block means importing the package that builds one,
which the grader may not do. The four tags stay in the grader because deciding
one needs nothing but a regular expression.

### A dash is not a zero

Every column prints `-` when the artifact does not record the figure, and `None`
travels all the way from the artifact to the renderer. A case with no transcript
has **no token split**, not a split of `0 / 0`; a case that produced nothing has
no row at all in the graded set. `wall_seconds` and `vote_agreement` are carried
as `Decimal` rather than as the binary numbers the cache holds, because the
grader never handles a binary value: the caller converts through the same
`Decimal(str(value))` every other number in the report arrives by.

### The columns are filled by the caller, and printed only when they were

`grade.grade(..., facts=...)` takes them; a report built from rulings alone
carries none and prints no block for them. That is the same rule the `cached`
column follows, and it is what keeps the grader's own committed self-test report
byte-identical.

## 3. The four patterns

Every tag is a claim about the **text**, decided by a regular expression or a
keyword list and never by a model. The patterns are in `eval/grade.py`, next to
the names and the renderer, and are documented here because a pattern with
undocumented edges is a number a reader cannot use.

### What they are

```
EVIDENCE_ID_RE     \bEV-[A-Z]{2,8}-\d{3,6}(?:-\d{1,3})?\b
CLAUSE_REFERENCE_RE \bPOL-[A-Z]{2,4}-\d{2}(?:\([a-z0-9]+\))?
ARITHMETIC_RE      (?<![\w.])\d+(?:\.\d+)?(?:\s*(?:[+\-*/×x÷])\s*\d+(?:\.\d+)?)+\s*=\s*-?\d+(?:\.\d+)?
GAP_RE             \b(gap|missing|absent|unavailable|unresolved|undisclosed|impaired|
                      insufficient|incomplete|not recorded|no record|never recorded|
                      no evidence|not in the record|silent|limitation|does not settle|
                      indeterminate|cannot be (?:verified|established|determined)|
                      no qualifying)\b                              (IGNORECASE)
```

### Measured over the 44 cached rulings

| tag | fires | misses |
|---|---|---|
| `cites_evidence` | 40 / 44 | 211, 9103, 9107, 9111 |
| `cites_clause` | 43 / 44 | 211 |
| `shows_arithmetic` | 7 / 44 | — |
| `names_gap` | 41 / 44 | 202, 211, 9111 |

### `cites_evidence` and `cites_clause`: exact on this corpus

Every distinct token the corpus's explanations contain — **93** `EV-…` ids and
**78** `POL-…` references — is matched by its pattern, and there are no bare
"clause 9" references without the `POL-` prefix. So neither pattern has an
observed false positive or false negative on this data.

The four misses are **not** pattern failures. 211 and 9111 are the
vote-escalation rulings, whose explanation is the vote's own text and cites
nothing. 9103 and 9107 reason from artifacts in prose — "the driver's GPS trace
shows a single continuous stationary hold…" — and name no id. Both are correctly
untagged by the tag's own definition, which is about the **form** of the text.
The limitation is worth stating: a ruling that reasons from evidence without
naming it reads as `no`, so this tag measures citation, not reasoning.

### `shows_arithmetic`: the largest false negative

The corpus contains **17** occurrences of `= <number>`. The pattern finds **7**:

```
104   43.41 - 39.828 = 3.582
108   26.17 - 24.60 = 1.57
111   24.0 + 5.98 = 29.98
114   58.10 - 44.42 = 13.68
9109  1/120 = 0.008
9110  1/120 = 0.008
9113  8.05 + 1.00 = 9.05
```

The 10 it misses are the shape the model mostly writes. Every one is anchored,
parenthesised or named, and the pattern requires a bare number on the left:

```
103   min(measured 2.98 km, 1.30 x (10.6 − 8.2) + 1.00 = 4.12 km) = 2.98 km
104   min(7.07, 1.30 x (30.1 - 27.1) + 1.00) = 4.90
105   …surge_multiplier) + 0.80 platform fee = 43.36
111   min(5.98, 7.76) = 5.98
9113  gps_trace.trace_distance_km = 18.0
9113  min(8.0, 1.30 × (12.0 − 10.0) + 1.0) = 3.60
9113  … + 1.00 on-optimal-route ERP = 23.416
9113  Refund = 31.42 charged less 23.416 = 8.004
```

Four distinct causes, all documented rather than fixed:

* **a parenthesis on either side** (103, 104, 111, 9113) — the pattern's operator
  run is broken by `(` or `)`;
* **a word or unit glued to a number** (105, 9113) — `platform fee = 43.36`;
* **named operands** (9113) — `trace_distance_km = 18.0`, `Refund = 31.42`;
* **the U+2212 minus sign** (103, 9113) — the pattern accepts `-` but not `−`.

Requiring the `=` is what keeps a sentence that merely contains several numbers
out, and it is the reason the tag is a floor rather than a count. A reader should
read `shows_arithmetic: no` as "no bare worked sum was found", not "the ruling
shows no arithmetic".

**No false positive was observed on this corpus.** The `(?<![\w.])` guard and the
requirement of a digit on the left are what keep metavariable sentences out:
`trace_distance_km = 18.0` and `Refund = 31.42` are not matched. The theoretical
false positive is a numeric equality that is not a worked sum — `0.75 = 3/4`, a
version number, a ratio — and none appears in this corpus.

### `names_gap`: the largest false positive

The pattern fires on the vocabulary of a gap and **cannot see a negation in front
of it**. The corpus denies a gap in at least 24 places, and each of these is
tagged as naming one:

```
105   no gap
111   no gap
112   NOT impaired under POL-RD-07 — there is no gap
205   no sequence gap
208   no sampling gap
212   not impaired under POL-NS-08(a)–(d): no gap
213   never uploaded - it is MISSING
9101  no trace gap
9102  no gaps (51 fixes, max gap …)
9105  no msg_id gap
9112  not a data gap
9113  no gap
```

Three further causes of a false positive are visible in the same list: `absent`
used as a noun ("the absent…"), `impaired` appearing only inside "not impaired",
and `MISSING` used to say an artifact is missing when that is the *finding*
rather than a limitation. So `names_gap: yes` means "the vocabulary of a gap is
present", which is not the same as "a gap is asserted".

The three misses are the other side of the same coin:

* **202** decides on the platform's own records and names no gap — correctly
  untagged;
* **211 and 9111** are the vote-escalation rulings. The panel could not agree,
  which is a limitation of the *process* rather than of the evidence, and the
  pattern's vocabulary does not reach it. This is a genuine false negative: a
  ruling that says "the drafts did not agree" is naming a limitation and reads as
  `no`.

### Why the tags are kept despite the edges

Because each one is reproducible from the ruling text alone, and because the
edges are now written down. A reader who wants "did this ruling show its work"
gets a floor they can check by hand; a reader who wants "did this ruling assert a
gap" is told to read the explanation. The alternative — asking a model to tag the
text — would be unfalsifiable, which is the property these columns exist to avoid.

## 4. The sample table

Rendered from the corpus cache by a **cached re-run** — every case reused, no
model call, 0 tokens charged and 6,239,134 reused. The full table for the 29
corpus cases, and the equivalent one for the fifteen-case second set:

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 52586 | 95656 | 175.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 102 | 63190 | 125379 | 344.6 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 103 | 71175 | 127804 | 301.3 | no | 1.00 | erp_lines.off_optimal_route_total.value | n/a | yes | yes | no | yes |
| 104 | 76100 | 174853 | 538.0 | no | 1.00 | closure[0].refund.payable.value | n/a | yes | yes | yes | yes |
| 105 | 62180 | 305549 | 971.1 | no | 0.75 | charged_total.value | n/a | yes | yes | no | yes |
| 106 | 53363 | 126215 | 184.5 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 107 | 62146 | 240365 | 771.9 | no | 0.75 | refund.payable.value | n/a | yes | yes | no | yes |
| 108 | 67582 | 116317 | 300.7 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 109 | 62818 | 129362 | 333.4 | no | 1.00 | unverifiable: not structured | unverifiable: not structured | yes | yes | no | yes |
| 110 | 61918 | 169376 | 463.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 111 | 73290 | 157819 | 490.5 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 112 | 75727 | 209637 | 694.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 113 | 55655 | 111804 | 233.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 114 | 63426 | 160431 | 403.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 115 | 55099 | 109343 | 217.7 | no | 1.00 | erp_lines.lines[1].amount_sgd.value | n/a | yes | yes | no | yes |
| 201 | 55400 | 100635 | 219.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 202 | 77920 | 116648 | 348.1 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | no |
| 203 | 62811 | 94123 | 219.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 204 | 62362 | 96725 | 214.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 205 | 75787 | 152999 | 493.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 206 | 56567 | 165801 | 460.4 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 207 | 79075 | 103456 | 253.9 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 208 | 80664 | 103456 | 329.5 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 209 | 100260 | 118057 | 463.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 210 | 65213 | 139286 | 365.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 211 | 75479 | 252364 | 888.6 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 212 | 70471 | 137660 | 406.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 213 | 58262 | 196795 | 557.7 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 214 | 72943 | 151750 | 462.6 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |

211 is the case the corpus misses. Its `0.50` is a two-two split, which is the
quorum rule's escalation; its `no` in all four tag columns is the escalation text
described in §3.

## 5. What was deliberately not done

**The committed `runs/*/report.md` files were not rewritten.** They are the record
of the run that produced them — every commit that has ever touched one says
"exactly as produced" — and regenerating one would rewrite a committed result
file, which `docs/notes/2026-09-22-stale-cached-results.md` and
`docs/notes/2026-09-24-the-frozen-prompt-run.md` both refuse. The columns are
rendered by the code; the next invocation that writes a report will carry them.
The table quoted above is that rendering, taken from the cache into a scratch
copy rather than over the committed file.

For the same reason nothing was run into `runs/`. A cached re-run makes no model
call, but it also rewrites `calls.json` (the corpus's 178 recorded calls become
0, because this invocation made none), rewrites `run.json` and appends to
`invocations.json`. That is a real cost with no benefit here: the report is a
rendering, and the rendering was already checked.

**`ui/dist/index.html` was rebuilt**, and that is the one committed artifact that
did change. The failed 13:03 replay wrote `run.json` and `invocations.json`, the
viewer reads both for its run-level provenance, and the test that pins the page
against a fresh build therefore went red. The rebuild moves `ended_at`,
`git_commit` and `invocation_count` (13 → 14) and the invocation history; the 29
cases are drawn identically, because the viewer reads the per-case entries for
case data rather than `run.json`.

**No prompt was changed and no model was called.** Nothing here reaches the
judge, so the judge prompt's freeze and the sealed set are untouched.

## 6. The suite

`python -m unittest discover -s tests`, under both interpreters, with the count
in the row for this session in `docs/buddy-log/README.md`.
