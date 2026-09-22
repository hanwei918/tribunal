# Two defects in the evaluation layer — 2026-09-22

## Summary

Both were found by reading what a model actually returned and what the answer key actually says,
rather than by trusting the verdict the grader printed. **Neither was a model failure.** One cost a
correct answer its mark; the other printed a comparison that invited the wrong conclusion.

The run they were found in is `runs/deepseek-deepseek-flash/`, made at commit `3931406` against the
corrected prompts (`prompts_sha256` `faa3da27…`), three cases requested and three completed, with
`calls.json` and `report.md` present. It is the first run made under the fixed advocate contract, and
it genuinely ran to the end.

## Defect 1 — the referral comparison produced false failures

`deepseek/deepseek-flash` on case 207 was scored **MISS on `referrals`**. It was right and the grader
was wrong.

The key's expected referral names one clause:

```
POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.00 cancellation fee in full
```

The model produced two entries. The first:

```
Escalation packet (POL-NS-09(d), reached via the POL-NS-07 anti-farming check): direct the human
reviewer to refund the rider's SGD 4.00 cancellation fee in full, per POL-NS-07; the fee is held
meanwhile and is not collected or refunded by the automated pipeline.
```

Same instruction, and it carries POL-NS-07. It adds POL-NS-09(d) — and **the key's own rationale for
this case reads "Compensation is withheld and the case escalates under POL-NS-09(d)"**. The model
named the fuller legal path the key itself describes, and exact set equality scored that as a failure.

What the old report actually printed for that case, quoted from `runs/deepseek-deepseek-flash/report.md`
as it stands:

```
- **referrals** — spurious referral: POL-NS-07, POL-NS-09(d); referral names no clause reference,
  so it cannot be matched: Human review should also examine DRV-01948's trailing-30-day no-show
  termination pattern (7 terminations across 61 completed trips, 11.5%).
```

Read that line carefully. It called **POL-NS-07 spurious** — the one clause the key demanded. The
model had named it twice, once inside the parenthetical and once after `per`, so one occurrence
satisfied the key and the leftover was reported as an invention. A report that tells a reader the
model invented the clause the key required is worse than a wrong boolean: it is actively misleading,
and it is the reason the addition count below is a set difference rather than a count of leftovers.

### The rule now

| Expected set | Produced set | Verdict |
|---|---|---|
| empty | empty | PASS |
| empty | anything at all | **FAIL** — unchanged. A referral invented where none belongs is still a defect: a referral sends a case to a human. |
| non-empty | every expected clause present | **PASS** — recall against the expected clauses is the test |
| non-empty | a clause missing | **FAIL** |
| non-empty | expected clauses present plus others | **PASS**, and the others are **REPORTED** |

`ruling`, `amount_sgd` and `driver_compensation_sgd` keep exact comparison. Nothing about `Decimal`
money or `null`-versus-zero changed. The loosening is for referral clause sets alone, and the reason
is stated in a comment above it in `eval/grade.py`.

Two counts are recorded per case and printed in the report: **expected clauses matched** and
**additional clauses offered**. The second is a set difference — clauses the key does not name at
all — not the references left over after matching, for the reason the quoted line above demonstrates.

A referral entry that names no clause at all is reported and not failed when the expected side is
non-empty, because recall is the test and the clause it was checked against is named. It is not
silently dropped: the report prints it under the additions.

## Defect 2 — the escalation rate was reported against a target it could not be compared to

The three-case run printed:

```
| **Escalation rate** | **66.7%** |
| Target | 17.2% |
| Off target | yes |
```

17.2 % is the base rate of the full 29-case corpus. That run graded three cases chosen deliberately,
two of which are ESCALATE. Comparing a hand-picked subset's rate to the corpus base rate is
meaningless, and printed side by side it invites exactly the wrong conclusion — that the system
over-escalates, when the subset was selected to contain escalations. `Off target | yes` states the
false conclusion outright.

Every rate in the calibration block has this property, precision and recall included: all of them move
with the base rate of whatever set was graded. Only the raw counts survive subsetting intact.

### The rule now

The report states which cases were graded and whether that is the full corpus, in both cases:

```
| Cases graded, by number | 109, 207, 210 |
| Whole corpus graded | no — 3 of 29 cases |
```

When the graded set is **not** the full corpus:

* the raw counts are printed, each with the case numbers behind it — true positives, false positives,
  false negatives, over-escalations, under-escalations, and the expected and produced escalations in
  the set;
* every rate is labelled as computed on that subset — `**Escalation rate (on these 3 cases)**`,
  `Precision on ESCALATE (on these 3 cases)`, and so on;
* the corpus target is **not printed**, in any form, and one line says why: *"Rates on a selected
  subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed
  beside them."*

When the **full corpus** was graded the block is unchanged: the target row, the off-target row and the
unlabelled precision and recall rows are printed exactly as before.

The same rule reaches the two places the runner prints numbers: the terminal summary at the end of a
run, and the `--compare` table's footnote. Both withhold the target and name the graded set when it is
a subset. The comparison table's graded set is the intersection of the runs' cached cases, which is
almost never the whole corpus.

## Re-grading the cached runs, with no model call

Each run under `runs/` was re-graded with the corrected rules. The old verdict was recomputed from the
same cached rulings using the old expression, so the two columns describe the same data.

| Run | Cached rulings | Exact, old | Exact, new | What changed |
|---|---|---|---|---|
| `runs/deepseek-deepseek-flash/` | 3 (109, 207, 210) | 2/3 = 66.7 % | **3/3 = 100.0 %** | case 207 `referrals` FAIL → PASS |
| `runs/hy4-preview/` | 1 (109) | 1/1 = 100.0 % | 1/1 = 100.0 % | nothing |
| `runs/hy3/` | **0** | — | — | nothing to re-grade |

Case 207 in the deepseek run now reads:

```
expected clauses matched: 1 of 1; additional clauses offered: POL-NS-09(d)
```

The escalation block for that run now reads, in place of the target comparison:

```
| **Escalation rate (on these 3 cases)** | **66.7%** |
| True positives (key and run both ESCALATE) | 2 | 207, 210 |
| False positives (run ESCALATE, key does not) | 0 | _none_ |
| False negatives (key ESCALATE, run does not) | 0 | _none_ |
```

Two things this re-grade does **not** do, both deliberate:

* **It does not rewrite `runs/*/report.md`.** Those files are the evidence for defect 1 — the
  "spurious referral: POL-NS-07" line above only exists in the artifact the broken grader wrote.
  Overwriting them would delete the finding. The re-graded numbers are recorded here instead.
* **It does not re-run anything.** No model was called. `--compare` and `grade_run` read the cache.

`runs/hy3/` has no cached ruling at all: both cases it reached failed at the advocate stage, and a
failed case leaves no cache entry. There is nothing in it for either rule to change.

## The other half of the story, unchanged

The two rulings the earlier session's fix did not rescue are still not rescued, and this change does
not touch them:

* `runs/hy3/case-00109` attempt 1 returned the **case JSON echoed back** — `case_no`, `dispute`,
  `evidence`, `schema_version`. Not attributable to the `json_object` contradiction, and not a
  referral problem either. The advocate prompt still has more than one thing wrong with it.
* Both `runs/hy3/run.json` and `runs/hy4-preview/run.json` still claim `"completed": true` while
  neither run completed — `stop_reason` is initialised to `STOP_COMPLETED` and rewritten after every
  case, so a SIGTERM mid-run leaves the last file claiming success. Still out of scope, still
  recorded. The deepseek run is the one that genuinely completed, and its `calls.json` and
  `report.md` are the evidence.

## Falsifiability

Seven mutations, each shown RED with the suite green beforehand, every file restored and verified
byte-identical by checksum:

| Mutation | Result |
|---|---|
| exact set equality restored in `match_referrals` | 5 failures |
| the empty-expected case allowed to pass | 6 failures |
| `additional_clauses` reporting leftovers again | 2 failures |
| `grades_full_corpus` always `True` | 11 failures |
| the calibration block always printing the target | 9 failures |
| the runner grading a subset as though it were the corpus | 2 failures |
| the terminal printing the target for every set | 1 failure |

One of these runs was killed by the harness mid-flight and did not execute its restore; the file was
restored from the backup copy afterwards and verified by checksum and by parsing. Recorded because a
mutation harness that can leave a file mutated is worth knowing about.

## Numbers

Suite 456 → 476 tests, `OK (skipped=1)`. `eval/grade.py --self-test` exits 0: the key still grades
itself 29/29 on every field, five escalations, precision and recall 1.0, and with the full corpus
graded the target comparison still prints. `docs/notes/2026-09-21-grader-self-test.md` was regenerated,
and the diff is the two new counts per referral case plus the two new rows in the calibration table —
no existing number moved. No benchmark was executed in this session and no model was called.
