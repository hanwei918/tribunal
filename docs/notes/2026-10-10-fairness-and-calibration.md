# Fairness and calibration, measured from the version-6 runs (2026-10-10)

**Where this starts.** `fffde16` (part 14, the appeal command).

**What this part does.** The judging includes responsible AI, fairness and
transparency, and the version-6 development runs already hold what three such
measurements need: whether the errors lean towards one party, whether the
judge's answer depends on which party is presented first, and whether its stated
confidence means what it says. `eval/fairness.py` reads the two runs and prints
the three measurements; `docs/calibration-v6.svg` is the reliability diagram it
draws. Nothing in `tribunal/`, `prompts/`, `policy/`, `runs/` or `data/` is
changed, and no figure already in the README moves: three rows are added to the
version-6 table and a section is added after it.

**What was read.** The two committed runs under `runs/` and their transcripts,
the two committed keys (`eval/answers/ground_truth.json` and
`eval/answers/dev-v2-ext/ground_truth.json`), the loaded version-6 policy for
the confidence floor, and the two sets' own public, answer-free case files under
`data/cases/` and `data/external/dev-v2-ext/` — read for the one fact the runs
do not record, which party filed each dispute. **Nothing under
`eval/answers/sealed-v1/`, `data/external/sealed-v1/` or
`eval/external/sealed-v1/` was opened, at import or at run time**, and the
module is asserted to open no answer path but the two keys.

**One import is deliberately not made.** The sheet asks that the draft rulings
be read out of the transcripts the way `ops.escalation.py` reads them, reusing
its functions where possible. They are read that way — the last ruling a draft
parsed to, so a retried draft is read as it stood — but the four lines are
**reproduced in `eval/fairness.py` rather than imported from `ops`**, because
importing the ops layer executes `eval.development_sets`, which opens every
registered set's `index.json` at import, `sealed-v1`'s among them. That read is
already known and accepted elsewhere in the repository, and it is exactly the
read this part is required not to make, so the helper is written out instead.
The transcript's own file name is still the one `tribunal.precedents` spells,
which is the helper `ops.escalation` itself uses for that purpose.

**No model call and no browser.** The measurement re-reads committed files; the
drafts it reads are the ones the runs recorded.

## The report, as `python3 -m eval.fairness --report` prints it

```
Version 6 fairness and calibration -- report
read from the committed version-6 runs under runs/ and the committed keys; no model call

corpus      runs/policy-v6/deepseek-deepseek-flash
dev-v2-ext  runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash

== Why not by who filed ==
   corpus      29 cases, filed by the rider 28, by the driver 1
   dev-v2-ext  120 cases, filed by the rider 120, by the driver 0
   a split by dispute.filed_by has one case on one side (the corpus's single driver-filed dispute), so it is not reported; the three measurements below are.

== 1. Which way the errors lean ==
-- corpus: 3 of 29 differ from the key
   towards the rider       0   none
   towards the driver      1   211
   to an escalation        1   107
   away from an escalation 1   112
   within a side           0   none
   no ruling               0   none
-- dev-v2-ext: 5 of 120 differ from the key
   towards the rider       0   none
   towards the driver      0   none
   to an escalation        4   2749, 2809, 2829 and 2853
   away from an escalation 1   2858
   within a side           0   none
   no ruling               0   none
-- both runs: 8 of 149 differ from the key
   towards the rider       0   none
   towards the driver      1   211
   to an escalation        5   107, 2749, 2809, 2829 and 2853
   away from an escalation 2   112 and 2858
   within a side           0   none
   no ruling               0   none
   cases where both sides are a refund of different sizes: none

== 2. The position swap ==
-- corpus: 28 cases have a valid swapped draft and a valid sampled one
   agrees on all four graded fields   26/28 = 92.9%   Wilson 95% [77.4%, 98.0%]
   agrees on the ruling alone         27/28 = 96.4%   Wilson 95% [82.3%, 99.4%]
   disagrees on all four     103 and 107
   disagrees on the ruling   107
-- dev-v2-ext: 113 cases have a valid swapped draft and a valid sampled one
   agrees on all four graded fields   110/113 = 97.3%   Wilson 95% [92.5%, 99.1%]
   agrees on the ruling alone         112/113 = 99.1%   Wilson 95% [95.2%, 99.8%]
   disagrees on all four     2723, 2749 and 2809
   disagrees on the ruling   2809
-- both runs: 141 cases have a valid swapped draft and a valid sampled one
   agrees on all four graded fields   136/141 = 96.5%   Wilson 95% [92.0%, 98.5%]
   agrees on the ruling alone         139/141 = 98.6%   Wilson 95% [95.0%, 99.6%]
   disagrees on all four     103, 107, 2723, 2749 and 2809
   disagrees on the ruling   107 and 2809

== 3. Calibration ==
-- corpus: 114 valid judge drafts
   bin            count   mean conf   share correct          Wilson 95%
   [0.0, 0.5)        11       0.324           81.8%      [52.3%, 94.9%]
   [0.5, 0.7)         0           -               -                 n/a
   [0.7, 0.8)         6       0.742          100.0%     [61.0%, 100.0%]
   [0.8, 0.9)        21       0.834           85.7%      [65.4%, 95.0%]
   [0.9, 1.0)        76       0.921           94.7%      [87.2%, 97.9%]
   expected calibration error   0.084
   below the 0.70 floor   9/11 = 81.8%
   at or above it        96/103 = 93.2%
   drafts proposing ESCALATE, below the 0.70 floor   11/11 = 100.0%
   drafts proposing ESCALATE, at or above it        8/103 = 7.8%
   share correct among the drafts that do not propose ESCALATE
     below the floor   none (0 drafts)
     at or above it    88/95 = 92.6%
-- dev-v2-ext: 453 valid judge drafts
   bin            count   mean conf   share correct          Wilson 95%
   [0.0, 0.5)        10       0.312          100.0%     [72.2%, 100.0%]
   [0.5, 0.7)         8       0.600          100.0%     [67.6%, 100.0%]
   [0.7, 0.8)         1       0.720            0.0%       [0.0%, 79.3%]
   [0.8, 0.9)        58       0.843           94.8%      [85.9%, 98.2%]
   [0.9, 1.0)       376       0.923           98.9%      [97.3%, 99.6%]
   expected calibration error   0.093
   below the 0.70 floor   18/18 = 100.0%
   at or above it        427/435 = 98.2%
   drafts proposing ESCALATE, below the 0.70 floor   18/18 = 100.0%
   drafts proposing ESCALATE, at or above it        37/435 = 8.5%
   share correct among the drafts that do not propose ESCALATE
     below the floor   none (0 drafts)
     at or above it    390/398 = 98.0%
-- both runs: 567 valid judge drafts
   bin            count   mean conf   share correct          Wilson 95%
   [0.0, 0.5)        21       0.318           90.5%      [71.1%, 97.3%]
   [0.5, 0.7)         8       0.600          100.0%     [67.6%, 100.0%]
   [0.7, 0.8)         7       0.739           85.7%      [48.7%, 97.4%]
   [0.8, 0.9)        79       0.841           92.4%      [84.4%, 96.5%]
   [0.9, 1.0)       452       0.922           98.2%      [96.5%, 99.1%]
   expected calibration error   0.088
   below the 0.70 floor   27/29 = 93.1%
   at or above it        523/538 = 97.2%
   drafts proposing ESCALATE, below the 0.70 floor   29/29 = 100.0%
   drafts proposing ESCALATE, at or above it        45/538 = 8.4%
   share correct among the drafts that do not propose ESCALATE
     below the floor   none (0 drafts)
     at or above it    478/493 = 97.0%
   drafts of one case are not independent: a case's four drafts answer the same brief, so the 567 valid drafts are 141 panels rather than 567 independent draws.
   the chart is written by: python3 -m eval.fairness --chart docs/calibration-v6.svg
```

## Why not by who filed

A split by `dispute.filed_by` would have one case on one side. Every one of
`dev-v2-ext`'s 120 disputes was filed by the rider, and so were 28 of the
corpus's 29; the corpus's single driver-filed dispute is the whole of the other
side. A rate over a one-case class is not a measurement, so it is not reported,
and the three measurements above are what is measured instead. The counts are
read from the sets' own public case files, which is the one place this fact
lives: no run records it.

## 1. Which way the errors lean

**What it shows.** Of the 149 cases the two runs cover, 8 differ from their key,
and every one of the eight is a move across the escalation boundary or across
the rider/driver boundary. One case moved towards the driver — 211, key
`PARTIAL_REFUND 2.00`, ruled `DRIVER_COMPENSATION 3.20` — five moved to an
escalation (107, 2749, 2809, 2829 and 2853), and two moved away from one (112 and
2858). **None moved towards the rider**, and no case has both sides a refund of a
different size, so the amount-move row the measurement carries is empty here.
The leaning, such as it is, is towards holding the money and sending the case to
a person rather than towards either party.

**What it does not show.** Eight misses is a small number and a single case moves
a row by 12.5 points, so this is a description of the two runs and not a rate
with a useful interval. Both runs are **development** data the system was built
against, so an error profile over them measures fit and not generalisation; the
two sealed sets, where the errors actually matter, are not read here. The
direction is a statement about the key, not about the world: the corpus key was
written under policy version 1 and the run was made at version 6, so where they
disagree it is not settled here which of the two moved.

## 2. The position swap

**What it shows.** The judge is asked four times on the same brief — three
sampled drafts at temperature 0.7 and one at temperature 0 with the parties'
positions swapped — and the swapped draft is held against the majority of the
sampled ones. Over the 141 cases whose swapped draft and at least one sampled
draft are valid, it agrees on the ruling alone in 139 (98.6%) and on all four
graded fields together in 136 (96.5%). "All four fields" is the pipeline's own
`vote_key` reduction, the one the judge's vote is taken with, so agreement means
what it means in the pipeline and not a second, private reading of the same
fields. The five disagreements on all four fields (103, 107, 2723, 2749 and
2809) are listed, and only two of them (107 and 2809) also disagree on the
ruling.

**What it does not show.** The swapped draft is a single draft at temperature 0
and the three sampled ones are at 0.7, so a disagreement can be sampling
variation rather than an order effect, and one swapped draft per case cannot
separate the two. The "sampled majority" is a majority of three, so a 2-of-3
majority is a weak majority and a case where the three sampled drafts split
3-0 in favour of a value the swapped draft rejects is not the same finding as
one where they split 2-1. It measures the drafts, not the carried ruling: the
vote is reduced over all four drafts including the swapped one, so a case can
carry the swapped draft's answer and still count as a disagreement here. And it
is development data.

## 3. Calibration

**What it shows.** The judge's stated confidence is broadly calibrated but not
sharp. Over the 567 valid drafts the expected calibration error is 0.088 — the
count-weighted mean gap between each bin's mean stated confidence and its share
correct — and the pooled reliability diagram rises monotonically with the
confidence. The two ends are the interesting parts: the drafts below the 0.70
floor are right 27 times in 29 (93.1%), and the drafts at or above it are right
523 times in 538 (97.2%). The floor is therefore not excluding wrong answers —
it is discarding drafts that are almost always right, which is the conservative
side of the trade and worth saying plainly.

**What it does not show.** **The drafts of one case are not independent.** A
case's four drafts answer the same brief, so the 567 drafts are 141 panels and
not 567 draws, and every Wilson interval above is narrower than an independent
sample of the same size would justify; the intervals are printed for the counts
they describe and are not a claim about independent trials. The bins are coarse
and the tails are thin: `dev-v2-ext`'s [0.7, 0.8) bin holds one draft, whose 0.0%
is one draft's answer and not a rate, and the corpus's [0.5, 0.7) bin is empty.
The confidence is the model's own stated number, not a probability the system
estimated, so a well-calibrated confidence is a statement about the model's
self-report and not about a decision rule the system could be tuned on. And the
key is the corpus's version-1 key for one of the two runs, so "correct" is
agreement with that key.

**What the low bins hold.** The below-floor share correct is high — 27 of 29
pooled — and the reason is not that the judge decides hard cases at low
confidence. A draft that proposes `ESCALATE` decides nothing: it sends the case
to a person, and the key often says `ESCALATE` too, so such a draft counts as
"correct" without having ruled. The measurement splits each side of the floor on
that value, and the split is total: **all 29 drafts below the 0.70 floor propose
`ESCALATE`** (29/29 pooled; 11/11 in the corpus and 18/18 in `dev-v2-ext`), so
the below-floor bin holds no draft that decided a case at all and its share
correct is a count of escalations agreeing with escalating keys. At or above the
floor, 45 of 538 drafts propose `ESCALATE` (8.4%) and the 493 that propose
something else are right **478 times (97.0%)**. The floor therefore discards no
draft that decided a case — every draft it removes escalated — and the drafts it
keeps decide the great majority of cases and are right 478 times in 493. This is
a description of the two development runs and not a rate with a useful interval;
the drafts of one case are not independent, as above.

## The chart

`docs/calibration-v6.svg` is written by
`python3 -m eval.fairness --chart docs/calibration-v6.svg`, by code and
deterministically: a reliability diagram with mean stated confidence on x, the
share of drafts correct on y, one point per bin with its radius growing with the
bin's count, the diagonal for perfect calibration and the 0.70 floor as a
vertical line. It is 800 by 600 on a white background, pure ASCII and carries no
script. It draws the **pooled** calibration of the two runs, and
`tests/test_fairness.py` asserts that a fresh build equals the committed file
byte for byte.

## The tests, written and not run

`tests/test_fairness.py` is new and **was not run here**: the owner runs every
test outside this sandbox. It covers the classification of each POL-GEN-03 ruling
value against the policy's own vocabulary, a synthetic pair of drafts where the
swapped one disagrees (on the ruling, and separately on the money), a synthetic
set of drafts whose expected calibration error is known by hand (0.135 over 20
drafts in three bins), the committed chart against a fresh build, and what the
report opens — that the only path under `eval/answers/` it reads is one of the
two keys and that it opens nothing under a sealed root. One more test runs
`import eval.fairness` in a fresh interpreter with `pathlib.Path.open` and
`io.open` recorded and asserts that **no sealed path is opened at import**,
beside a control that shows the probe reports a path carrying the marker, so a
clean answer is not a probe that stopped working. The `--chart` command also
refuses a sealed destination through the repository's one helper for it, and
that refusal is covered by the same module.

## What did not change

No file under `tribunal/`, `prompts/`, `policy/`, `runs/` or `data/` is touched.
`eval/fairness.py` is new, `docs/calibration-v6.svg` is new,
`tests/test_fairness.py` is new, and the only edits are the three rows and the
new section in `README.md`, the three figures added to
`tests/test_readme_figures.py`'s version-6 block, and this note. The README's
version-6 rows were checked against the committed runs and keys from the record
rather than by running the suite.
