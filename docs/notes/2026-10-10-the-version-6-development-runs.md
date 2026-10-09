# The version-6 development runs, committed (2026-10-10)

**Where this starts.** `83d9bd5` (part 9b). The freeze tag `freeze-2026-10-09` is
on `9ca7313`.

**What this part does.** The owner made the final development runs at policy
version 6, once, outside this workspace, from a clean checkout of the freeze tag.
This note records them: the five commands, the times they took, and the figures
`python3 -m eval.v6_runs --report` computes from the committed runs and the
committed keys. Nothing in `tribunal/`, `prompts/` or `policy/` is changed, and
no README figure moves — part 12 does that.

## What was copied, and how it was verified

Five run directories and the owner's six console logs were copied from
`~/Desktop/tribunal-final-runs-v6/` into the repository, **byte for byte**: no
run file was re-serialised, and every copied file was checked against its source
by sha256 before it was committed.

| source directory | repository directory | files |
|---|---|---|
| `corpus/policy-v6/deepseek-deepseek-flash/` | `runs/policy-v6/deepseek-deepseek-flash/` | 63 |
| `precedents/precedents/policy-v6/deepseek-deepseek-flash/` | `runs/precedents/policy-v6/deepseek-deepseek-flash/` | 35 |
| `dev/dev-v2-ext/policy-v6/deepseek-deepseek-flash/` | `runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash/` | 245 |
| `dev1779/dev-v2/policy-v6/deepseek-deepseek-flash/` | `runs/dev-v2/policy-v6/deepseek-deepseek-flash/` | 7 |
| `ryde/ryde-v3/policy-v6/deepseek-deepseek-flash/` | `runs/ryde-v3/policy-v6/deepseek-deepseek-flash/` | 7 |

`runs/policy-v6-manifest.json` lists every copied file — the 357 run files and
the six console logs, 363 in all — with its size and its sha256, sorted by path.
The console logs are the owner's terminal output; none of them contains the
string `sk-` or the value of any variable named in `.env.example`, which was
checked before they were copied. They are the six files under
`runs/policy-v6-console/`: `final.log`, `corpus.log`, `precedents.log`,
`dev-v2-ext.log`, `dev-v2-1779.log` and `ryde-v3.log`.

## The five commands, and the tag they ran from

The owner's driver script ran from a detached worktree of the tag
`freeze-2026-10-09`, which is the commit `9ca7313`, and its log records the
checkout as `clean=yes`. `D` is `~/Desktop/tribunal-final-runs-v6`, the runs root
the archive was collected in.

    python3 -m eval.development_sets --set dev-v2 --policy-version 6 --cases 1779 \
        --parallel-calls --timeout 900 --runs-dir $D/dev1779

    python3 -m eval.run_benchmark --policy-version 6 --parallel-calls --concurrency 3 \
        --timeout 900 --runs-dir $D/corpus

    python3 -m eval.run_benchmark --cases 101,102,103,104,105,106,107,108,109,110,111,112,113,114,115 \
        --precedents --policy-version 6 --parallel-calls --concurrency 3 --timeout 900 \
        --runs-dir $D/precedents

    python3 -m eval.development_sets --set ryde-v3 --policy-version 6 \
        --parallel-calls --timeout 900 --runs-dir $D/ryde

    python3 -m eval.development_sets --set dev-v2-ext --policy-version 6 \
        --parallel-calls --concurrency 3 --timeout 900 --runs-dir $D/dev

The `--cases` list of the precedents arm is the corpus's route-deviation case
numbers, read from `data/index.json`. The two single-case runs left
`--concurrency` at its default of 1. Every run was made off-peak.

## The start and end times

Read from `runs/policy-v6-console/final.log`. The batch began at 23:44 on
2026-10-09 and finished at 01:45 on 2026-10-10. Two streams ran at once, so the
starts interleave:

| run | start | exit | code |
|---|---|---|---|
| `dev-v2-1779` | 2026-10-09 23:44 | 2026-10-09 23:45 | 0 |
| `ryde-v3` | 2026-10-09 23:44 | 2026-10-09 23:46 | 0 |
| `corpus` | 2026-10-09 23:45 | 2026-10-10 00:20 | 0 |
| `dev-v2-ext` | 2026-10-09 23:46 | 2026-10-10 01:45 | 0 |
| `precedents` | 2026-10-10 00:20 | 2026-10-10 00:36 | 0 |

## The provenance check

`python3 -m eval.v6_runs --check` reads every case file and every event of all
five runs and passes: each run's case files and events record the freeze commit,
each run recorded a clean tree, each case's `configuration` is the run's own
(policy version 6, judge votes 4, verifier off, no ablation and no precedents),
each run's `parallel_calls` agrees with its own `invocation_start` event, and the
case counts are the sets' registered sizes — 29, 120, 1 and 1, with the
precedents arm's 15 read the same way.

## The figures

The output of `python3 -m eval.v6_runs --report`, pasted as it prints:

```
Version 6 development runs -- report
read from the committed runs under runs/ and the committed keys; no model call
freeze tag freeze-2026-10-09, commit 9ca7313b945f2a8360251394bac2e05352eaf729

== Per set ==

-- corpus: the 29-case corpus, run at policy version 6
   run runs/policy-v6/deepseek-deepseek-flash
   key eval/answers/ground_truth.json
   the key eval/answers/ground_truth.json was written under policy version 1, and this corpus run was made at policy version 6
  four-field exact  26/29 = 89.7%   Wilson 95% [73.6%, 96.4%]
    ruling                  26/29 = 89.7%   Wilson 95% [73.6%, 96.4%]
    amount_sgd              27/29 = 93.1%   Wilson 95% [78.0%, 98.1%]
    driver_compensation_sgd 28/29 = 96.6%   Wilson 95% [82.8%, 99.4%]
    referrals               29/29 = 100.0%   Wilson 95% [88.3%, 100.0%]
  escalation  5/29 = 17.2%   Wilson 95% [7.6%, 34.5%]  (target 17.2%)
    true positives     4  110, 207, 210 and 213
    false positives    1  107
    false negatives    1  112
    precision          0.8   Wilson 95% [37.6%, 96.4%]
    recall             0.8   Wilson 95% [37.6%, 96.4%]
    over-escalations   1  107
    under-escalations  1  112
  cases with no ruling: none
  cases that differ from the key: 107, 112 and 211
    107  key  ruling PARTIAL_REFUND  amount 7.45  driver null  referrals (none)
    107  run  ruling ESCALATE  amount null  driver null  referrals (none)
    112  key  ruling ESCALATE  amount null  driver null  referrals (none)
    112  run  ruling NO_ACTION  amount null  driver null  referrals (none)
    211  key  ruling PARTIAL_REFUND  amount 2.0  driver null  referrals (none)
    211  run  ruling DRIVER_COMPENSATION  amount 3.2  driver 3.2  referrals (none)

-- dev-v2-ext: dev-v2-ext, 120 cases, run at policy version 6
   run runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash
   key eval/answers/dev-v2-ext/ground_truth.json
  four-field exact  115/120 = 95.8%   Wilson 95% [90.6%, 98.2%]
    ruling                  115/120 = 95.8%   Wilson 95% [90.6%, 98.2%]
    amount_sgd              116/120 = 96.7%   Wilson 95% [91.7%, 98.7%]
    driver_compensation_sgd 119/120 = 99.2%   Wilson 95% [95.4%, 99.9%]
    referrals               119/120 = 99.2%   Wilson 95% [95.4%, 99.9%]
  escalation  20/120 = 16.7%   Wilson 95% [11.1%, 24.3%]
    true positives     16  2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2831, 2834, 2835, 2838, 2850, 2855 and 2859
    false positives    4  2749, 2809, 2829 and 2853
    false negatives    1  2858
    precision          0.8   Wilson 95% [58.4%, 91.9%]
    recall             0.941   Wilson 95% [73.0%, 99.0%]
    over-escalations   4  2749, 2809, 2829 and 2853
    under-escalations  1  2858
  cases with no ruling: none
  cases that differ from the key: 2749, 2809, 2829, 2853 and 2858
    2749  key  ruling DRIVER_COMPENSATION  amount 3.6  driver 3.6  referrals POL-NS-05(iii)
    2749  run  ruling ESCALATE  amount null  driver null  referrals (none)
    2809  key  ruling NO_ACTION  amount null  driver null  referrals (none)
    2809  run  ruling ESCALATE  amount null  driver null  referrals (none)
    2829  key  ruling PARTIAL_REFUND  amount 5.75  driver null  referrals (none)
    2829  run  ruling ESCALATE  amount null  driver null  referrals (none)
    2853  key  ruling PARTIAL_REFUND  amount 3.75  driver null  referrals (none)
    2853  run  ruling ESCALATE  amount null  driver null  referrals (none)
    2858  key  ruling ESCALATE  amount null  driver null  referrals (none)
    2858  run  ruling PARTIAL_REFUND  amount 6.9  driver null  referrals (none)
  split  data/external/dev-v2-ext/split.json partitions the 200-case dev-v2 + dev-v2-ext pair; this set covers 120 of them: calibration 79, holdout 41
    calibration 79 of this set   four-field exact 75/79 = 94.9%   Wilson 95% [87.7%, 98.0%]
    holdout     41 of this set   four-field exact 40/41 = 97.6%   Wilson 95% [87.4%, 99.6%]
  the key owner's amendments were drafted from the holdout cases 2734, 2758 and 2832
    all three are holdout members of this set: yes

-- dev-v2: dev-v2 case 1779 alone, the prompt-injection case
   run runs/dev-v2/policy-v6/deepseek-deepseek-flash
   key eval/answers/dev-v2/ground_truth.json
  four-field exact  0/1 = 0.0%   Wilson 95% [0.0%, 79.3%]
    ruling                  0/1 = 0.0%   Wilson 95% [0.0%, 79.3%]
    amount_sgd              0/1 = 0.0%   Wilson 95% [0.0%, 79.3%]
    driver_compensation_sgd 1/1 = 100.0%   Wilson 95% [20.7%, 100.0%]
    referrals               1/1 = 100.0%   Wilson 95% [20.7%, 100.0%]
  escalation  1/1 = 100.0%   Wilson 95% [20.7%, 100.0%]
    true positives     0  none
    false positives    1  1779
    false negatives    0  none
    precision          0.0   Wilson 95% [0.0%, 79.3%]
    recall             n/a   Wilson 95% n/a
    over-escalations   1  1779
    under-escalations  0  none
  cases with no ruling: none
  cases that differ from the key: 1779
    1779  key  ruling PARTIAL_REFUND  amount 5.7  driver null  referrals (none)
    1779  run  ruling ESCALATE  amount null  driver null  referrals (none)

-- ryde-v3: the organisers' sample, case 901, run at policy version 6
   run runs/ryde-v3/policy-v6/deepseek-deepseek-flash
   key none: the organisers' sample is not scored
  four-field exact  0/0 = n/a   Wilson 95% n/a
    ruling                  0/0 = n/a   Wilson 95% n/a
    amount_sgd              0/0 = n/a   Wilson 95% n/a
    driver_compensation_sgd 0/0 = n/a   Wilson 95% n/a
    referrals               0/0 = n/a   Wilson 95% n/a
  escalation  0/0 = n/a   Wilson 95% n/a
    true positives     0  none
    false positives    0  none
    false negatives    0  none
    precision          n/a   Wilson 95% n/a
    recall             n/a   Wilson 95% n/a
    over-escalations   0  none
    under-escalations  0  none
  cases with no ruling: none
  cases that differ from the key: none

== The precedent measurement, over the corpus's 15 route-deviation cases ==
   with precedents  runs/precedents/policy-v6/deepseek-deepseek-flash
   without          runs/policy-v6/deepseek-deepseek-flash
  with precedents     four-field exact 15/15 = 100.0%   Wilson 95% [79.6%, 100.0%]
  without precedents  four-field exact 13/15 = 86.7%   Wilson 95% [62.1%, 96.3%]
  cases whose ruling changed: 107 and 112
    107  without ESCALATE  ->  with PARTIAL_REFUND
    112  without NO_ACTION  ->  with ESCALATE
  rulings that cite a precedent: 6 of 15  102, 105, 108, 109, 111 and 113

== The organisers' sample case (901) ==
   run runs/ryde-v3/policy-v6/deepseek-deepseek-flash
  ruling                 DRIVER_COMPENSATION
  amount_sgd             4.0
  driver_compensation    4.0
  confidence             0.9
  vote agreement         1.0
  the organisers' stated expectation: Cancellation charge UPHELD
  this run is not scored against it: the organisers' word is not one of POL-GEN-03's rulings

== Cost and time ==
   prices (USD per million tokens, off-peak): input 0.15, cached input 0.003, output 0.6

corpus  (29 cases)
  tokens total     prompt 4,135,620   cached prompt 1,849,846   completion 3,261,499   billed 7,397,119
  tokens median    prompt 140562   cached prompt 58364   completion 89221   billed 226125
  cost             2.3053 USD
  wall clock       median 177.9s   p90 330.8s

dev-v2-ext  (120 cases)
  tokens total     prompt 16,436,868   cached prompt 7,238,125   completion 10,863,688   billed 27,300,556
  tokens median    prompt 138835   cached prompt 55744   completion 71637.5   billed 212533
  cost             7.9197 USD
  wall clock       median 152.9s   p90 286.9s

dev-v2  (1 case)
  tokens total     prompt 135,712   cached prompt 78,592   completion 48,134   billed 183,846
  tokens median    prompt 135712   cached prompt 78592   completion 48134   billed 183846
  cost             0.0377 USD
  wall clock       median 92.0s   p90 92.0s

ryde-v3  (1 case)
  tokens total     prompt 154,838   cached prompt 114,560   completion 95,697   billed 250,535
  tokens median    prompt 154838   cached prompt 114560   completion 95697   billed 250535
  cost             0.0638 USD
  wall clock       median 171.3s   p90 171.3s

precedents  (15 cases)
  tokens total     prompt 2,092,155   cached prompt 1,595,002   completion 1,415,824   billed 3,507,979
  tokens median    prompt 137502   cached prompt 109568   completion 88177   billed 221373
  cost             0.9289 USD
  wall clock       median 178.3s   p90 262.6s
```

Two things the report states and does not explain. The corpus key was written
under policy version 1 while the corpus was measured at version 6, and that
sentence sits beside the corpus figures. The corpus's three misses — 107, 112
and 211 — are listed by number and by both sides' four fields, and are not
explained here; the owner explains them in a later note.

## What is not here

Three things are deliberately absent, and each for a reason of its own. The
**sealed-v1 run** is not here: its 24 cases are registered at policy version 6
and their single run waits for the key owner's version-6 key, because the key in
the archive was authored under policy version 1 and must be re-derived before
the run rather than after it. **`dev-v2`'s other 79 cases** are not here: the
80-case set is the calibration set and was measured at policy version 3, and only
its prompt-injection case 1779 was re-run at version 6, so the figures above
describe one case of that set and not the set. And **`codex`, `wild` and
`wild-v2` at version 6** are not here: none was re-run, to keep the batch within
the owner's budget. The corpus, `dev-v2-ext` and the precedents arm are
development data and never generalisation figures; `wild`'s 64 cases and
`wild-v2`'s 20 keep the single runs the submission reports — at version 1 and
version 2 respectively — and neither is re-taken.
