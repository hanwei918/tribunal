# Benchmark report — deepseek/deepseek-flash — development set dev-v2-ext

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/dev-v2-ext/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 120 |
| Rulings produced | 120 |
| **Four-field exact match** | **113/120 = 94.2%** **(mixed set — not one measurement)** |

| `ruling` | 114/120 = 95.0% |
| `amount_sgd` | 113/120 = 94.2% |
| `driver_compensation_sgd` | 120/120 = 100.0% |
| `referrals` | 119/120 = 99.2% |

### Cached results

A cached result is evidence about the code that produced it and about nothing else. Each result records the digest of the exact brief bytes its agents were handed and the digest of the prompts they were given, so both are rebuilt now and compared with what was recorded. This does not say a stale result is wrong; it says it is not a measurement of this code.

The prompts digest was not recorded for 2 of 120 results, so whether the prompts they were given are the ones this code ships cannot be established for them at all.

Staleness could not be established for: 2735, 2759. A brief that cannot be rebuilt is not a brief that still matches.

**A mixed set is not one run.** The 113/120 exact-match figure above spans results produced by more than one version of the brief or the prompts, so it is not a single measurement of any one version of this code.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **113/120 = 94.2%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

## Per case

| case | ruling | amount_sgd | driver_compensation_sgd | referrals | exact | cached |
|---|---|---|---|---|---|---|
| 2701 | ok | ok | ok | ok | ok | current |
| 2702 | ok | ok | ok | ok | ok | current |
| 2703 | ok | ok | ok | ok | ok | current |
| 2704 | ok | ok | ok | ok | ok | current |
| 2705 | ok | ok | ok | ok | ok | current |
| 2706 | ok | ok | ok | ok | ok | current |
| 2707 | ok | ok | ok | ok | ok | current |
| 2708 | ok | ok | ok | ok | ok | current |
| 2709 | ok | ok | ok | ok | ok | current |
| 2710 | ok | ok | ok | ok | ok | current |
| 2711 | ok | ok | ok | ok | ok | current |
| 2712 | ok | ok | ok | ok | ok | current |
| 2713 | ok | ok | ok | ok | ok | current |
| 2714 | ok | ok | ok | ok | ok | current |
| 2715 | ok | ok | ok | ok | ok | current |
| 2716 | ok | ok | ok | ok | ok | current |
| 2717 | ok | ok | ok | ok | ok | current |
| 2718 | ok | ok | ok | ok | ok | current |
| 2719 | ok | ok | ok | ok | ok | current |
| 2720 | ok | ok | ok | ok | ok | current |
| 2721 | ok | ok | ok | ok | ok | current |
| 2722 | ok | ok | ok | ok | ok | current |
| 2723 | ok | ok | ok | ok | ok | current |
| 2724 | ok | ok | ok | ok | ok | current |
| 2725 | ok | ok | ok | ok | ok | current |
| 2726 | ok | ok | ok | ok | ok | current |
| 2727 | ok | ok | ok | ok | ok | current |
| 2728 | ok | ok | ok | ok | ok | current |
| 2729 | ok | ok | ok | ok | ok | current |
| 2730 | ok | ok | ok | ok | ok | current |
| 2731 | ok | ok | ok | ok | ok | current |
| 2732 | ok | ok | ok | ok | ok | current |
| 2733 | ok | ok | ok | ok | ok | current |
| 2734 | ok | ok | ok | ok | ok | current |
| 2735 | ok | ok | ok | ok | ok | unknown |
| 2736 | ok | ok | ok | ok | ok | current |
| 2737 | ok | ok | ok | ok | ok | current |
| 2738 | ok | ok | ok | ok | ok | current |
| 2739 | ok | ok | ok | ok | ok | current |
| 2740 | ok | ok | ok | ok | ok | current |
| 2741 | ok | ok | ok | ok | ok | current |
| 2742 | ok | ok | ok | ok | ok | current |
| 2743 | ok | ok | ok | ok | ok | current |
| 2744 | ok | ok | ok | ok | ok | current |
| 2745 | ok | ok | ok | ok | ok | current |
| 2746 | ok | ok | ok | ok | ok | current |
| 2747 | ok | ok | ok | ok | ok | current |
| 2748 | ok | ok | ok | ok | ok | current |
| 2749 | ok | ok | ok | ok | ok | current |
| 2750 | ok | ok | ok | ok | ok | current |
| 2751 | ok | ok | ok | ok | ok | current |
| 2752 | ok | ok | ok | ok | ok | current |
| 2753 | ok | ok | ok | ok | ok | current |
| 2754 | ok | ok | ok | ok | ok | current |
| 2755 | ok | ok | ok | ok | ok | current |
| 2756 | ok | ok | ok | ok | ok | current |
| 2757 | ok | ok | ok | ok | ok | current |
| 2758 | ok | ok | ok | ok | ok | current |
| 2759 | ok | ok | ok | ok | ok | unknown |
| 2760 | ok | ok | ok | ok | ok | current |
| 2801 | ok | ok | ok | ok | ok | current |
| 2802 | ok | ok | ok | ok | ok | current |
| 2803 | ok | ok | ok | ok | ok | current |
| 2804 | ok | ok | ok | ok | ok | current |
| 2805 | ok | ok | ok | ok | ok | current |
| 2806 | ok | ok | ok | ok | ok | current |
| 2807 | ok | ok | ok | ok | ok | current |
| 2808 | ok | ok | ok | ok | ok | current |
| 2809 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 2810 | ok | ok | ok | ok | ok | current |
| 2811 | ok | ok | ok | ok | ok | current |
| 2812 | ok | ok | ok | ok | ok | current |
| 2813 | ok | ok | ok | ok | ok | current |
| 2814 | ok | ok | ok | ok | ok | current |
| 2815 | ok | ok | ok | ok | ok | current |
| 2816 | ok | ok | ok | ok | ok | current |
| 2817 | ok | ok | ok | ok | ok | current |
| 2818 | ok | ok | ok | ok | ok | current |
| 2819 | ok | ok | ok | ok | ok | current |
| 2820 | ok | ok | ok | ok | ok | current |
| 2821 | ok | ok | ok | ok | ok | current |
| 2822 | ok | ok | ok | ok | ok | current |
| 2823 | ok | ok | ok | ok | ok | current |
| 2824 | ok | ok | ok | ok | ok | current |
| 2825 | ok | ok | ok | ok | ok | current |
| 2826 | ok | ok | ok | ok | ok | current |
| 2827 | ok | ok | ok | ok | ok | current |
| 2828 | ok | ok | ok | ok | ok | current |
| 2829 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 2830 | ok | ok | ok | ok | ok | current |
| 2831 | ok | ok | ok | ok | ok | current |
| 2832 | ok | ok | ok | ok | ok | current |
| 2833 | ok | ok | ok | ok | ok | current |
| 2834 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 2835 | ok | ok | ok | ok | ok | current |
| 2836 | ok | ok | ok | ok | ok | current |
| 2837 | ok | ok | ok | ok | ok | current |
| 2838 | ok | ok | ok | ok | ok | current |
| 2839 | ok | **FAIL** | ok | ok | **FAIL** | current |
| 2840 | ok | ok | ok | ok | ok | current |
| 2841 | ok | ok | ok | ok | ok | current |
| 2842 | ok | ok | ok | ok | ok | current |
| 2843 | ok | ok | ok | ok | ok | current |
| 2844 | ok | ok | ok | ok | ok | current |
| 2845 | ok | ok | ok | ok | ok | current |
| 2846 | ok | ok | ok | ok | ok | current |
| 2847 | ok | ok | ok | ok | ok | current |
| 2848 | ok | ok | ok | ok | ok | current |
| 2849 | ok | ok | ok | ok | ok | current |
| 2850 | ok | ok | ok | ok | ok | current |
| 2851 | **FAIL** | **FAIL** | ok | **FAIL** | **FAIL** | current |
| 2852 | ok | ok | ok | ok | ok | current |
| 2853 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 2854 | ok | ok | ok | ok | ok | current |
| 2855 | ok | ok | ok | ok | ok | current |
| 2856 | ok | ok | ok | ok | ok | current |
| 2857 | ok | ok | ok | ok | ok | current |
| 2858 | **FAIL** | **FAIL** | ok | ok | **FAIL** | current |
| 2859 | ok | ok | ok | ok | ok | current |
| 2860 | ok | ok | ok | ok | ok | current |

## Per case — cost, provenance and explanation tags

Computed by code from each case's own artifacts: the token split summed off its transcript by role, the wall clock and the vote agreement read off its cache entry, the amount provenance computed from the brief this code builds, and the four tags matched over the ruling's explanation by regular expression and keyword. No model is involved. A dash means the artifact does not record the figure. The patterns, and what each is known to miss and to mistake, are documented in `docs/notes/2026-09-27-the-event-log-and-the-report-columns.md`.

`vote agreement` is the share of the judge's drafts that agreed on the published ruling -- `1.00` for a unanimous panel, `0.75` for three of four, and a dash for a run that asked the judge once and so held no vote. It is not the judge's own `confidence`, and the two are never folded together.

| case | advocate tokens | judge tokens | wall s | escalated | vote agreement | amount_sgd from | driver_compensation_sgd from | cites evidence | cites clause | shows arithmetic | names a gap |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2701 | 44881 | 135758 | 55.4 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2702 | 44780 | 147293 | 76.1 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2703 | 44774 | 139168 | 60.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2704 | 43966 | 128410 | 48.1 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2705 | 44012 | 134243 | 61.0 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2706 | 44552 | 142694 | 62.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2707 | 44153 | 135807 | 53.8 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2708 | 44549 | 152850 | 91.1 | no | 0.75 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 2709 | 44325 | 137092 | 64.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2710 | 43519 | 138501 | 59.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2711 | 43729 | 294606 | 257.6 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2712 | 44342 | 178060 | 103.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2713 | 44812 | 224152 | 146.2 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 2714 | 45591 | 214509 | 169.2 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 2715 | 44721 | 142189 | 67.4 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2716 | 45036 | 169099 | 95.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 2717 | 44312 | 137589 | 56.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2718 | 44313 | 141509 | 65.6 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2719 | 44789 | 149460 | 81.2 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | yes | yes |
| 2720 | 44409 | 177469 | 110.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2721 | 44415 | 172495 | 100.1 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2722 | 44653 | 242309 | 226.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2723 | 44327 | 144100 | 68.1 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2724 | 44340 | 139482 | 58.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2725 | 44966 | 174375 | 117.3 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | yes | yes |
| 2726 | 44155 | 179505 | 107.4 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2727 | 44886 | 141771 | 58.4 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2728 | 44470 | 142884 | 65.0 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2729 | 44503 | 126526 | 46.7 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2730 | 44294 | 144729 | 74.8 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2731 | 44877 | 152494 | 70.4 | yes | 1.00 | n/a | n/a | no | yes | no | no |
| 2732 | 44347 | 201784 | 123.6 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 2733 | 44003 | 137259 | 54.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2734 | 44879 | 135950 | 57.3 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2735 | - | - | 0.0 | yes | - | n/a | n/a | no | yes | no | no |
| 2736 | 45388 | 168825 | 101.9 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2737 | 44638 | 121525 | 38.2 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2738 | 44232 | 132000 | 51.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2739 | 45435 | 143825 | 66.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | no | yes | yes | yes |
| 2740 | 45344 | 132605 | 48.3 | no | 1.00 | waiting_time_fee.value | n/a | yes | yes | no | yes |
| 2741 | 44271 | 135147 | 55.3 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2742 | 44464 | 129862 | 48.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2743 | 44627 | 137427 | 59.7 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2744 | 44368 | 179234 | 96.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2745 | 44926 | 143373 | 80.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2746 | 44214 | 201553 | 163.5 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2747 | 44421 | 129490 | 42.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2748 | 44732 | 158451 | 78.4 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2749 | 45014 | 196054 | 155.9 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2750 | 44673 | 177807 | 116.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2751 | 44477 | 126278 | 50.2 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2752 | 44742 | 135938 | 65.9 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2753 | 44908 | 136809 | 54.9 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | yes | yes |
| 2754 | 44696 | 148261 | 67.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2755 | 45333 | 165782 | 96.2 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2756 | 44274 | 202105 | 120.7 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2757 | 43843 | 125274 | 46.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2758 | 43860 | 133437 | 56.8 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2759 | - | - | 0.0 | yes | - | n/a | n/a | no | yes | no | no |
| 2760 | 44952 | 169471 | 94.8 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | yes | yes |
| 2801 | 42948 | 132575 | 64.9 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2802 | 42345 | 119675 | 42.4 | no | 0.75 | refund.payable.value | n/a | yes | yes | no | yes |
| 2803 | 44257 | 126208 | 37.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2804 | 44918 | 178120 | 117.1 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2805 | 42314 | 123266 | 42.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2806 | 41647 | 113359 | 34.1 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2807 | 42651 | 116943 | 33.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2808 | 45382 | 284534 | 239.9 | no | 0.75 | n/a | n/a | yes | yes | yes | no |
| 2809 | 45445 | 201879 | 164.0 | no | 0.75 | refund.payable.value | n/a | no | yes | yes | no |
| 2810 | 45297 | 393760 | 581.2 | no | 0.75 | components.base_fare.value | n/a | yes | yes | yes | yes |
| 2811 | 42793 | 175730 | 98.4 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2812 | 42161 | 168303 | 97.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2813 | 41441 | 125307 | 53.4 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 2814 | 40470 | 119419 | 49.0 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 2815 | 42735 | 137504 | 65.7 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 2816 | 43076 | 129174 | 49.2 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | no |
| 2817 | 42609 | 136118 | 55.4 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2818 | 42638 | 132407 | 53.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2819 | 42418 | 127122 | 50.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2820 | 41839 | 126423 | 75.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2821 | 41724 | 128349 | 51.3 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2822 | 41298 | 119247 | 45.6 | no | 1.00 | refund.refund_before_rounding.value | n/a | yes | yes | yes | yes |
| 2823 | 42334 | 149600 | 75.5 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 2824 | 41743 | 124627 | 47.4 | no | 0.75 | refund.payable.value | n/a | yes | yes | no | yes |
| 2825 | 42772 | 137596 | 55.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2826 | 43336 | 227291 | 208.3 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 2827 | 43002 | 154886 | 80.1 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 2828 | 42678 | 128693 | 46.5 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2829 | 42962 | 158779 | 63.8 | yes | - | n/a | n/a | no | yes | no | no |
| 2830 | 41954 | 125917 | 47.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2831 | 42470 | 242018 | 199.4 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2832 | 43333 | 124098 | 45.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2833 | 42622 | 123459 | 40.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2834 | 42588 | 204398 | 266.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2835 | 43181 | 120442 | 39.9 | yes | 0.75 | n/a | n/a | yes | yes | no | yes |
| 2836 | 41693 | 112100 | 34.6 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2837 | 41729 | 149781 | 88.8 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2838 | 42428 | 146393 | 72.5 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2839 | 47078 | 340644 | 507.3 | no | 0.75 | refund.refund_before_rounding.value | n/a | yes | yes | no | yes |
| 2840 | 42225 | 122255 | 40.7 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2841 | 42341 | 132532 | 55.7 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2842 | 43059 | 133726 | 56.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2843 | 41751 | 120737 | 45.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2844 | 41913 | 126927 | 45.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2845 | 41761 | 125485 | 54.8 | no | 0.75 | n/a | n/a | yes | yes | yes | yes |
| 2846 | 41871 | 120846 | 39.9 | no | 1.00 | refund.refund_before_rounding.value | n/a | yes | yes | no | yes |
| 2847 | 41873 | 137368 | 77.9 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 2848 | 41893 | 123956 | 46.3 | no | 1.00 | refund.refund_before_rounding.value | n/a | yes | yes | yes | yes |
| 2849 | 42997 | 141081 | 63.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2850 | 43049 | 181381 | 103.2 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2851 | 42987 | 170501 | 97.1 | yes | 0.25 | n/a | n/a | no | yes | no | no |
| 2852 | 41987 | 126804 | 62.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2853 | 43128 | 128961 | 50.8 | yes | - | n/a | n/a | no | yes | no | no |
| 2854 | 42400 | 121405 | 48.2 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2855 | 41895 | 203767 | 162.5 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2856 | 43631 | 128079 | 47.1 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2857 | 42855 | 122225 | 42.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2858 | 43305 | 144838 | 101.9 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2859 | 43330 | 133005 | 56.9 | yes | 0.75 | n/a | n/a | yes | yes | yes | yes |
| 2860 | 42216 | 122918 | 48.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |

## Failures

### Case 2809

Failed on: ruling, amount_sgd

- **ruling** — expected 'NO_ACTION', produced 'PARTIAL_REFUND'
- **amount_sgd** — expected null, produced 5.55

### Case 2829

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 5.75, produced null

### Case 2834

Failed on: ruling, amount_sgd

- **ruling** — expected 'ESCALATE', produced 'PARTIAL_REFUND'
- **amount_sgd** — expected null, produced 7.65

### Case 2839

Failed on: amount_sgd

- **amount_sgd** — expected 3.0, produced 7.85

### Case 2851

Failed on: ruling, amount_sgd, referrals

- **ruling** — expected 'FULL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 20.66, produced null
- **referrals** — expected referral not produced: POL-RD-06(c)

### Case 2853

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 3.75, produced null

### Case 2858

Failed on: ruling, amount_sgd

- **ruling** — expected 'ESCALATE', produced 'PARTIAL_REFUND'
- **amount_sgd** — expected null, produced 6.9

## Referrals — expected against produced

### Case 2709 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii): record a false-arrival event against driver DRV-09709 on trip TRP-02709 — the 'I'm Here' tap at 07:38:35 was made while the driver's GPS trace (EV-GPS-02709) placed him 647.3 m from the pickup pin, and no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2710 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii) false-arrival record: record trip TRP-02710 against driver DRV-09710 as a false-arrival event — the 22:48:55 'arrived' marker is false (the trace places the driver at least 517.4 m from the pickup pin and shows him moving at 28.8–63.0 km/h) and no qualifying in-geofence fix exists anywhere in the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2723 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01: driver-education item — the cancellation was recorded under reason code DRIVER_UNABLE_TO_LOCATE, which is not one of the three recognised no-show codes (RIDER_NO_SHOW, RIDER_UNREACHABLE, EXCESSIVE_WAIT); the mis-selected reason code is referred for driver education."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2724 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01: driver-education item — trip TRP-02724 was terminated under cancellation_reason_code DRIVER_UNABLE_TO_LOCATE although the driver had arrived at the pickup pin and served the free waiting period; the mis-selected reason code is recorded for driver review."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2725 — clause match

- expected: "POL-NS-05(iii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(iii) false-arrival record: driver DRV-09725 tapped 'I'm Here' at 18:15:10 while still in motion (32.2 km/h) and more than 300 m from the pickup pin (EV-GPS-02725); the waiting clock is recomputed from the first qualifying in-geofence fix at 18:17:10. The corrected dwell of 210 s still met the 180 s minimum, so the fee is unaffected, but the false-arrival event is recorded against the driver for POL-NS-07 and human review."
- clause keys, expected: POL-NS-05(iii)
- clause keys, produced: POL-NS-05(iii), POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: POL-NS-07
- additional clause(s) offered: POL-NS-07

### Case 2727 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.50 cancellation fee in full"
- produced: "POL-NS-07 (anti-farming branch): the escalation packet directs the reviewer to refund the rider's cancellation fee of SGD 4.50 in full, the fee being held meanwhile under POL-NS-09."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07, POL-NS-09
- expected clauses matched: 1 of 1
- additional clauses offered: POL-NS-09
- additional clause(s) offered: POL-NS-09

### Case 2747 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01: driver-education item — the trip was terminated under cancellation reason code DRIVER_UNABLE_TO_LOCATE, which is not one of the three codes (RIDER_NO_SHOW, RIDER_UNREACHABLE, EXCESSIVE_WAIT) that can support a no-show fee; the driver should be reminded to record the correct code."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2748 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01: record a driver-education item against driver DRV-09748 for the mis-selected cancellation reason code DRIVER_UNABLE_TO_LOCATE on trip TRP-02748 - the no-show fee was refunded in full and no driver compensation is payable."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2749 — clause match

- expected: "POL-NS-05(iii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(iii): false-arrival record against driver DRV-09749 — the 'I'm Here' marker was tapped at 2026-09-06T09:39:14, 120 s before the first qualifying in-geofence fix at 09:41:14; the corrected 210 s dwell still met the 180 s free waiting period, so the fee is unaffected, but the false-arrival event is recorded for POL-NS-07 and for human review."
- clause keys, expected: POL-NS-05(iii)
- clause keys, produced: POL-NS-05(iii), POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: POL-NS-07
- additional clause(s) offered: POL-NS-07

### Case 2751 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.50 cancellation fee in full"
- produced: "[POL-NS-07] Direct the human reviewer, on escalation under POL-NS-09, to refund the rider's cancellation fee of SGD 4.50 in full; the fee is held rather than collected or refunded by the automated pipeline pending that review."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07, POL-NS-09
- expected clauses matched: 1 of 1
- additional clauses offered: POL-NS-09
- additional clause(s) offered: POL-NS-09

### Case 2815 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: ERP gantry line of SGD 2.00 on EV-FARE-02815 that the trace never passes"
- produced: "POL-RD-09(4): billing-integrity finding — the 'AYE Alexandra Rd gantry' ERP line of SGD 2.00 on EV-FARE-02815 was charged although the GPS trace EV-GPS-02815 never comes within the 250 m gantry match radius (nearest fix 6,130.08 m, no bracketing fixes); refunded in full as a standalone correction."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2816 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: ERP gantry line of SGD 3.00 on EV-FARE-02816 that the trace never passes"
- produced: "POL-RD-09(4) billing integrity: the $3.00 'AYE Alexandra Rd gantry' ERP line on trip TRP-02816 is unmatched by the GPS trace (nearest fix 330.73 m, outside the 250 m crossing radius) and is refunded as a standalone billing-integrity correction; record this as a billing-integrity finding."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2827 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c) driver-conduct review: refer driver DRV-09827 for conduct review on the established repeat-deviation pattern (deviation_flags_90d = 3 against completed_trips_90d = 180 in the trailing 90 days) together with this trip's material 5.4 km / 60.0% deviation; the referral does not displace or delay the refund."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2851 — **no clause match**

- expected: "POL-RD-06(c) driver-conduct review"
- produced: _(none)_
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: _(none)_
- expected clauses matched: 0 of 1
- additional clauses offered: _(none)_
- expected referral not produced: POL-RD-06(c)

## Escalation calibration

| | |
|---|---|
| Cases graded | 120 |
| Cases graded, by number | 2701, 2702, 2703, 2704, 2705, 2706, 2707, 2708, 2709, 2710, 2711, 2712, 2713, 2714, 2715, 2716, 2717, 2718, 2719, 2720, 2721, 2722, 2723, 2724, 2725, 2726, 2727, 2728, 2729, 2730, 2731, 2732, 2733, 2734, 2735, 2736, 2737, 2738, 2739, 2740, 2741, 2742, 2743, 2744, 2745, 2746, 2747, 2748, 2749, 2750, 2751, 2752, 2753, 2754, 2755, 2756, 2757, 2758, 2759, 2760, 2801, 2802, 2803, 2804, 2805, 2806, 2807, 2808, 2809, 2810, 2811, 2812, 2813, 2814, 2815, 2816, 2817, 2818, 2819, 2820, 2821, 2822, 2823, 2824, 2825, 2826, 2827, 2828, 2829, 2830, 2831, 2832, 2833, 2834, 2835, 2836, 2837, 2838, 2839, 2840, 2841, 2842, 2843, 2844, 2845, 2846, 2847, 2848, 2849, 2850, 2851, 2852, 2853, 2854, 2855, 2856, 2857, 2858, 2859, 2860 |
| Whole corpus graded | no — 120 of 120 cases |
| Expected escalations | 17 |
| Produced escalations | 18 |
| **Escalation rate (on these 120 cases)** | **15.0%** |
| Precision on ESCALATE (on these 120 cases) | 15 of 18 = 0.833 |
| Recall on ESCALATE (on these 120 cases) | 15 of 17 = 0.882 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 15 | 2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2831, 2835, 2838, 2850, 2855, 2859 |
| False positives (run ESCALATE, key does not) | 3 | 2829, 2851, 2853 |
| False negatives (key ESCALATE, run does not) | 2 | 2834, 2858 |
| Over-escalations (= false positives) | 3 | 2829, 2851, 2853 |
| Under-escalations (= false negatives) | 2 | 2834, 2858 |
| Expected escalations in this set | 17 | 2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2831, 2834, 2835, 2838, 2850, 2855, 2858, 2859 |
| Produced escalations in this set | 18 | 2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2829, 2831, 2835, 2838, 2850, 2851, 2853, 2855, 2859 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 3 | 2829, 2851, 2853 |
| Under-escalations (key ESCALATE, produced does not) | 2 | 2834, 2858 |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 17 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2831, 2834, 2835, 2838, 2850, 2855, 2858, 2859 |
| ... the run escalated | 15 of 17 |
| **... the run ruled confidently instead** | **2 of 17** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

Cases ruled confidently where the record does not settle the question: 2834, 2858.

## How this was checked

This report is of the development set `dev-v2-ext`, whose own answer key is `eval/answers/dev-v2-ext/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
