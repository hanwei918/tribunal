# The advocates' reasoning off: what one development run measured

**2026-10-11.** The owner ran `dev-v2-ext` once at policy version 6 with
`--advocate-effort none` -- the switch that makes the **two advocate requests**
carry `"reasoning_effort": "none"` and leaves the judge's drafts and the verifier
untouched. The run is committed exactly as produced at
`runs/advocate-effort-none/dev-v2-ext/policy-v6/deepseek-deepseek-flash/`, 120
cases, and this note reads it against the committed version-6 run of the same set
with

    python3 -m eval.advocate_effort --report \
        --baseline runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash \
        --candidate runs/advocate-effort-none/dev-v2-ext/policy-v6/deepseek-deepseek-flash

Both runs are read; nothing is written, no model is called and no browser is
launched. The report below is that command's output, pasted as it printed.

## What the comparison counts, and the bug that was fixed first

`ComparedCase.four_fields_changed` compared `(ruling_word, ruling)` -- the ruling
word and the **whole ruling object** -- so a case whose explanation or confidence
differed counted as a change even when every field the grading reads was the
same, and amounts were compared as written, so `5.9` and `5.90` would have been
two amounts. The report said "changed 118 of 120" on this run when most of those
cases are exact on both runs.

It now compares only the four graded fields, each the way the grading reads it:
the ruling word exactly, the two amounts as `Decimal`, and the referrals by
clause reference with the grader's own recall rule. The "moved between two
misses" count is renamed **"miss on both, changed"**, and it now counts only
cases that are a miss on both runs *and* whose graded fields differ. Nothing else
in the report moved: the four-field figures, the times, the claims and the cost
are the same lines they were.

Five cases changed a graded field, not 118. Four of them changed their four-field
verdict -- 2749 improved, 2834, 2839 and 2851 regressed -- and the fifth, 2809,
changed its ruling word (`ESCALATE` to `PARTIAL_REFUND 5.55`) while remaining a
miss on both runs, which is the one case in the renamed bucket. The other 115
cases agree on all four graded fields, and the 113 cases the old comparison
counted among them differ only in fields the grading never reads: the
explanation, the confidence, and referral prose that names the same clause.

## The report

```
Advocate effort, read from two runs of one set
set        dev-v2-ext
baseline   runs/dev-v2-ext/policy-v6/deepseek-deepseek-flash
candidate  runs/advocate-effort-none/dev-v2-ext/policy-v6/deepseek-deepseek-flash
key        eval/answers/dev-v2-ext/ground_truth.json

cases both runs have: 120
  baseline only: none
  candidate only: none

== Four-field exact against the key ==
   baseline  115/120 = 95.8%   Wilson 95% [90.6%, 98.2%]
     ruling                  115/120 = 95.8%   Wilson 95% [90.6%, 98.2%]
     amount_sgd              116/120 = 96.7%   Wilson 95% [91.7%, 98.7%]
     driver_compensation_sgd 119/120 = 99.2%   Wilson 95% [95.4%, 99.9%]
     referrals               119/120 = 99.2%   Wilson 95% [95.4%, 99.9%]
   candidate 113/120 = 94.2%   Wilson 95% [88.4%, 97.1%]
     ruling                  114/120 = 95.0%   Wilson 95% [89.5%, 97.7%]
     amount_sgd              113/120 = 94.2%   Wilson 95% [88.4%, 97.1%]
     driver_compensation_sgd 120/120 = 100.0%   Wilson 95% [96.9%, 100.0%]
     referrals               119/120 = 99.2%   Wilson 95% [95.4%, 99.9%]

== The cases whose ruling changed ==
   changed            5 of 120   2749, 2809, 2834, 2839 and 2851
   direction          improved 1   regressed 3   miss on both, changed 1   unchanged 115
   2749  improved
     baseline  ruling ESCALATE  amount null  driver null  referrals (none)
     candidate ruling DRIVER_COMPENSATION  amount 3.6  driver 3.6  referrals POL-NS-05(iii), POL-NS-07
     four-field verdict miss -> exact
   2809  moved
     baseline  ruling ESCALATE  amount null  driver null  referrals (none)
     candidate ruling PARTIAL_REFUND  amount 5.55  driver null  referrals (none)
     four-field verdict miss -> miss
   2834  regressed
     baseline  ruling ESCALATE  amount null  driver null  referrals (none)
     candidate ruling PARTIAL_REFUND  amount 7.65  driver null  referrals (none)
     four-field verdict exact -> miss
   2839  regressed
     baseline  ruling PARTIAL_REFUND  amount 3.0  driver null  referrals (none)
     candidate ruling PARTIAL_REFUND  amount 7.85  driver null  referrals (none)
     four-field verdict exact -> miss
   2851  regressed
     baseline  ruling FULL_REFUND  amount 20.66  driver null  referrals POL-RD-06(c), POL-RD-06, POL-RD-01
     candidate ruling ESCALATE  amount null  driver null  referrals (none)
     four-field verdict exact -> miss

== Claims ==
   baseline  rider 1053   driver  970   referee discarded   71
     per case: rider median 8   driver median 7   discarded median 0
   candidate rider 1287   driver 1279   referee discarded  300
     per case: rider median 10   driver median 10   discarded median 2

== Time, seconds ==
   baseline
   advocates       median    91.1   p90   134.4
   judge           median    49.4   p90   200.2
   whole case      median   152.9   p90   286.9
   candidate
   advocates       median     9.1   p90    10.8
   judge           median    53.3   p90   146.2
   whole case      median    61.7   p90   155.9
   saved per case  median    85.0   p90   162.4   (baseline minus candidate; positive is a saving)

== Tokens and cost, at the owner's prices ==
   prices (USD per million tokens, off-peak): input 0.15, cached input 0.003, output 0.6
   baseline
     tokens per case   prompt median 138835   completion median 71638   reasoning median 63894
     cost per case     median 0.0555 USD   total 7.9197 USD over 120 cases
   candidate
     tokens per case   prompt median 138196   completion median 43554   reasoning median 34694
     cost per case     median 0.0339 USD   total 5.0596 USD over 120 cases
```

## What it says, and what it does not

**One development set, one run each.** This is `dev-v2-ext`, a set the system was
built against, and each side of the comparison is a single run. The two-case drop
in four-field agreement -- 115/120 to 113/120 -- sits inside both Wilson
intervals ([90.6%, 98.2%] and [88.4%, 97.1%]), and with one run per setting
nothing here separates the switch from sampling variation. **The 2-case drop is
therefore not shown to be a real loss, and it is not shown to be a real tie
either.** No figure in this note is a generalisation figure and none is pooled
with a sealed one.

**The referee discarded about four times as many claims.** 71 of 2,023 discarded
becomes 300 of 2,566, and the median discarded per case goes from 0 to 2. The
citation check is doing its job -- the referee discards a claim that cites no
evidence id, no clause id, an unresolvable citation, undisclosed impaired
evidence, or a context-only profile field as a ground -- and a discarded claim is
one the judge never sees. It is also a sign that **the advocates write worse
claims without their reasoning**: they filed 27% more claims and a much larger
share of them did not survive the check. The saving in time is real, and part of
what it buys is a weaker advocate stage.

**The default stays `default`.** Nothing that was measured, sealed or submitted
changes: the four version-6 runs, the three sealed runs and the business-value
figures are all at `default`, and `--advocate-effort none` remains opt-in and
refused for every sealed set. Whether to switch is the team's decision, and a
switch would need a **sealed run on the switched setting** before any figure
could be claimed for it.

**No sealed set was run with this switch.** `wild-v1`, `wild-v2` and `sealed-v1`
were each run exactly once, at `default`, from their own frozen trees; the switch
is refused for all three in code, and this measurement is the development set
only.
