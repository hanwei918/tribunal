# The version-8 measurements: the position swap, calibration, the automatic share, the clock and the cost

**2026-10-14.** The front page and the README still lead with figures measured on
the **version-6** runs -- the position swap `136/141`, the expected calibration
error `0.088`, and `112 of 151` decided with no person. Those cannot be turned
into version-8 figures by editing: the 151 cases were keyed by the team's
version-6 rules, and a figure re-labelled rather than re-measured is a figure
that measures nothing. The version-8 runs already hold everything the same
measurements need, so they are measured **there**, by the same functions, with
**no model call**.

`eval/v8_report.py` is the reader. It reads the two committed version-8 runs
(`runs/dev-v8/policy-v8/deepseek-deepseek-flash` and
`runs/ryde-v8/policy-v8/deepseek-deepseek-flash`), their two committed keys, and
the two sets' own public, answer-free case files. It writes nothing, and nothing
under `tribunal/`, `prompts/`, `policy/`, `data/`, `runs/` or `eval/answers/`
moved for it.

The two sets are read **separately and never pooled**: one figure over 40 cases
plus another over 2 is not a measurement of 42, and neither is added to the
version-6 figures or to any sealed set's.

## The measurements

| | dev-v8 | ryde-v8 |
|---|---|---|
| four-field agreement | 39/40 | 1/2 |
| escalation produced / expected / true positive | 12 / 13 / 12 | 2 / 1 / 1 |
| decided with no person | 28 of 40 | 0 of 2 |
| wall median, p90 | 153.1 s, 299.4 s | 256.2 s, 418.0 s |
| cost median, total | 0.0390 USD, 1.823 USD | 0.0632 USD, 0.126 USD |
| position swap, all four fields | 33 of 34 (5009 differs; 5006, 5010, 5012, 5013, 5015 and 5068 do not qualify) | 0 of 0 (902: no judge was asked; 903: its swapped draft was voided) |
| valid drafts, ECE | 139, 0.097 | 3 (too few) |
| below 0.80 / at or above 0.80, correct | 14 of 14 (all 14 propose ESCALATE) / 118 of 125 | 0 of 2 (all 2 propose ESCALATE) / 1 of 1 |
| errors | one: 5017, away from an escalation | one: 903, to an escalation |

Every figure above is printed by one command:

    python3 -m eval.v8_report --report

The report prints the table, then each set's own section with the bins, the
Wilson intervals and the direction every differing case moved, then the note it
ends with.

## What each measurement means

**Four-field agreement.** The share of cases whose produced ruling equals the
key on all four graded fields, through the same grader the version-6 fairness
report uses, so "agrees on all four graded fields" means what it means in the
pipeline rather than a second, private reading of the same fields.

**Escalation.** The cases the run sent to a person, the cases the key sends, the
cases both do, and the precision and recall of the first against the second. On
`dev-v8` all 12 the run escalated are escalations the key asks for (precision
1.0) and one the key asks for was ruled instead (recall 0.923); on `ryde-v8` two
were escalated, one of them the key's.

**Decided with no person.** The cases whose published ruling is not `ESCALATE`,
over the cases. A case sent to a person is a case the system did not decide,
which is why this count is the escalation count's complement: 40 less 12 on
`dev-v8`, 2 less 2 on `ryde-v8`.

**The clock and the cost.** The wall clock's median and 90th percentile, read
with the version-6 report's own median and percentile functions, and the model
cost's median and total at the repository's published prices -- prompt minus
cached at the input price, cached at the cached-input price, completion at the
output price, over a million. The cost is what one run of the system was charged
for the cases it ran.

**The position swap.** Each case's swapped draft is held against its sampled
majority -- the most common four-field key among the valid sampled drafts -- on
all four graded fields together and on the ruling alone, over every case whose
swapped draft and at least one sampled draft are valid. That denominator is 34
of `dev-v8`'s 40 cases and 0 of `ryde-v8`'s 2.

**Calibration.** Every valid judge draft carries a confidence; a draft is marked
correct when its four fields equal the case's key, and the drafts are grouped
into the five confidence bins, with each bin's count, mean confidence, share
correct and a Wilson 95% interval, and the expected calibration error over all
drafts. The **floor split is taken at 0.80**, the version-8 bar (POL-RD-25 and
POL-GEN-22's middle band), rather than at version 6's 0.70 -- which is the one
thing `eval.fairness.calibrate` gained a `floor` keyword for. The bins
themselves do not move, and with the default the version-6 output is
byte-identical.

**Which way the errors lean.** Every ruling value and every key value is
classified as rider-favouring, driver-favouring or neither, and every case that
differs from its key is reported by the direction its ruling moved: towards the
rider, towards the driver, to an escalation, or away from one. `dev-v8` has one
differing case, 5017, which moved away from an escalation; `ryde-v8` has one,
903, which moved to one.

## The swap's absent cases, and why

A case that does not qualify is not a case the swap passed, and it is not one it
failed either, so each is named with its reason.

- **`dev-v8`**: 5006's swapped draft was voided -- it cited `POL-NS-24`,
  `POL-NS-25` and `POL-NS-22`, none of which resolves in version 8 -- so it
  holds no valid swapped draft; and 5010, 5012, 5013, 5015 and 5068 hold no
  judge draft at all, because no judge was asked. The one case that does
  qualify and differs is 5009.
- **`ryde-v8`**: 902 was escalated at the gate before any draft was asked for,
  and 903's swapped draft was voided for citing `POL-NS-08`, which version 8
  does not have.

## Three sentences

1. These figures are from **development data** the team tuned against, and none
   of them is a generalisation figure.
2. The version-6 figures -- the position swap `136/141`, the expected
   calibration error `0.088` and `112 of 151` decided with no person -- are
   measurements of the **version-6 system on version-6 keys** and stay as
   history.
3. The **injection, PII and collusion sets were not run at version 8**, so
   nothing here says anything about them.
