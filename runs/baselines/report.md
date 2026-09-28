# Baselines from recorded data

Model: deepseek/deepseek-flash. **No model call was made.** Every figure is computed from what each run already recorded: the judge drafts on its transcripts and the rulings it published.

Both development sets are development data, and neither is a test set. The corpus figure is the figure the submission reports; the combined figure is a sum over two sets that were drafted differently and share one template, so it is not a generalisation figure and does not replace the corpus number. The only generalisation figure the submission reports belongs to the sealed set, drafted without access to this repository and run exactly once after the 10 October freeze. Neither figure here is that figure.

A row is scored over the cases its section analysed. A case that is stale, unknown, or holds no panel of drafts is refused with its reason and left out of every figure rather than counted as a miss, so a section's denominators are the cases that could be scored and not the size of the set.

`exact (four fields)` counts a case only when the ruling, both amounts and the sorted referral clause references all agree. The four columns after it count one field each, `ruling alone` first.

## corpus — runs/deepseek-deepseek-flash

Scored over 29 of the 29 cases in the set; 0 refused.

| row | exact (four fields) | ruling alone | amount | driver | referrals |
|---|---|---|---|---|---|
| Always ESCALATE | 4/29 | 5/29 | 10/29 | 24/29 | 25/29 |
| Majority ruling: PARTIAL_REFUND | 0/29 | 8/29 | 10/29 | 24/29 | 25/29 |
| Single draft: seed 101 | 29/29 | 29/29 | 29/29 | 29/29 | 29/29 |
| Single draft: seed 202 | 27/29 | 27/29 | 27/29 | 29/29 | 29/29 |
| Single draft: seed 303 | 29/29 | 29/29 | 29/29 | 29/29 | 29/29 |
| Single draft: position-swapped | 29/29 | 29/29 | 29/29 | 29/29 | 29/29 |
| Single draft: mean of the four | 28.50/29 | 28.50/29 | 28.50/29 | 29.00/29 | 29.00/29 |
| At least one draft right | 29/29 | 29/29 | 29/29 | 29/29 | 29/29 |
| The carried vote | 29/29 | 29/29 | 29/29 | 29/29 | 29/29 |

- **Always ESCALATE** — Null amounts and no referrals, on every case.
- **Majority ruling: PARTIAL_REFUND** — The ruling this section's cases most often require, with null amounts and no referrals. Chosen on the set it is scored on, so it is an in-sample figure and not a prediction.
- **Single draft: seed 101** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: seed 202** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: seed 303** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: position-swapped** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: mean of the four** — The arithmetic mean of the four rows above.
- **At least one draft right** — an upper bound for any rule that publishes one of the drafts' answers; a no-majority escalation can exceed it
- **The carried vote** — What the run published for each case, for comparison.

No case was refused.

## codex — runs/codex/deepseek-deepseek-flash

Scored over 15 of the 15 cases in the set; 0 refused.

| row | exact (four fields) | ruling alone | amount | driver | referrals |
|---|---|---|---|---|---|
| Always ESCALATE | 3/15 | 4/15 | 5/15 | 12/15 | 10/15 |
| Majority ruling: FULL_REFUND | 0/15 | 5/15 | 5/15 | 12/15 | 10/15 |
| Single draft: seed 101 | 14/15 | 15/15 | 14/15 | 15/15 | 15/15 |
| Single draft: seed 202 | 13/15 | 15/15 | 13/15 | 15/15 | 14/15 |
| Single draft: seed 303 | 14/15 | 15/15 | 14/15 | 15/15 | 15/15 |
| Single draft: position-swapped | 14/15 | 15/15 | 14/15 | 15/15 | 15/15 |
| Single draft: mean of the four | 13.75/15 | 15.00/15 | 13.75/15 | 15.00/15 | 14.75/15 |
| At least one draft right | 14/15 | 15/15 | 14/15 | 15/15 | 15/15 |
| The carried vote | 14/15 | 15/15 | 14/15 | 15/15 | 15/15 |

- **Always ESCALATE** — Null amounts and no referrals, on every case.
- **Majority ruling: FULL_REFUND** — The ruling this section's cases most often require, with null amounts and no referrals. Chosen on the set it is scored on, so it is an in-sample figure and not a prediction.
- **Single draft: seed 101** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: seed 202** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: seed 303** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: position-swapped** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: mean of the four** — The arithmetic mean of the four rows above.
- **At least one draft right** — an upper bound for any rule that publishes one of the drafts' answers; a no-majority escalation can exceed it
- **The carried vote** — What the run published for each case, for comparison.

No case was refused.

## combined — runs

Scored over 44 of the 44 cases in the set; 0 refused.

| row | exact (four fields) | ruling alone | amount | driver | referrals |
|---|---|---|---|---|---|
| Always ESCALATE | 7/44 | 9/44 | 15/44 | 36/44 | 35/44 |
| Majority ruling: FULL_REFUND | 0/44 | 12/44 | 15/44 | 36/44 | 35/44 |
| Single draft: seed 101 | 43/44 | 44/44 | 43/44 | 44/44 | 44/44 |
| Single draft: seed 202 | 40/44 | 42/44 | 40/44 | 44/44 | 43/44 |
| Single draft: seed 303 | 43/44 | 44/44 | 43/44 | 44/44 | 44/44 |
| Single draft: position-swapped | 43/44 | 44/44 | 43/44 | 44/44 | 44/44 |
| Single draft: mean of the four | 42.25/44 | 43.50/44 | 42.25/44 | 44.00/44 | 43.75/44 |
| At least one draft right | 43/44 | 44/44 | 43/44 | 44/44 | 44/44 |
| The carried vote | 43/44 | 44/44 | 43/44 | 44/44 | 44/44 |

- **Always ESCALATE** — Null amounts and no referrals, on every case.
- **Majority ruling: FULL_REFUND** — The ruling this section's cases most often require, with null amounts and no referrals. Chosen on the set it is scored on, so it is an in-sample figure and not a prediction.
- **Single draft: seed 101** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: seed 202** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: seed 303** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: position-swapped** — That one draft's answer on every analysed case. An abstained or invalid draft counts as a miss.
- **Single draft: mean of the four** — The arithmetic mean of the four rows above.
- **At least one draft right** — an upper bound for any rule that publishes one of the drafts' answers; a no-majority escalation can exceed it
- **The carried vote** — What the run published for each case, for comparison.

No case was refused.

The single-draft rows are the same four drafts the vote counts: three sampled at temperature 0.7 under seeds 101, 202 and 303, and one position-swapped. The mean of the four is an arithmetic mean of the four rows above it and not a measurement of its own.