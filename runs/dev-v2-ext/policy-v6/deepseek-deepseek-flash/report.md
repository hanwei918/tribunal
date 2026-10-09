# Benchmark report — deepseek/deepseek-flash — development set dev-v2-ext

Produced by `eval/grade.py`. Regenerate with `python -m eval.grade`. The answer key is `eval/answers/dev-v2-ext/ground_truth.json`; the five ruling values are read from POL-GEN-03 on the loaded general policy.

## Summary

| | |
|---|---|
| Cases graded | 120 |
| Rulings produced | 120 |
| **Four-field exact match** | **115/120 = 95.8%** **(mixed set — not one measurement)** |

| `ruling` | 115/120 = 95.8% |
| `amount_sgd` | 116/120 = 96.7% |
| `driver_compensation_sgd` | 119/120 = 99.2% |
| `referrals` | 119/120 = 99.2% |

### Cached results

A cached result is evidence about the code that produced it and about nothing else. Each result records the digest of the exact brief bytes its agents were handed and the digest of the prompts they were given, so both are rebuilt now and compared with what was recorded. This does not say a stale result is wrong; it says it is not a measurement of this code.

The prompts digest was not recorded for 2 of 120 results, so whether the prompts they were given are the ones this code ships cannot be established for them at all.

Staleness could not be established for: 2735, 2759. A brief that cannot be rebuilt is not a brief that still matches.

**A mixed set is not one run.** The 115/120 exact-match figure above spans results produced by more than one version of the brief or the prompts, so it is not a single measurement of any one version of this code.

A ruling counts only when **all four** fields agree. The per-field figures above are there so a reader can see which field a model actually fails on; they are not alternative scores.

Reported as a contrast only, and not as a result: `ruling` and `amount_sgd` alone would give **115/120 = 95.8%**. Case 207 is `ESCALATE` with both money fields `null` and a referral instructing the reviewer to refund the rider's SGD 4.00 in full, so a two-field grader awards it full marks while a real rider does not get their money back. The gap between this line and the four-field line is the size of that mistake on this run.

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
| 2749 | **FAIL** | **FAIL** | **FAIL** | **FAIL** | **FAIL** | current |
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
| 2809 | **FAIL** | ok | ok | ok | **FAIL** | current |
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
| 2834 | ok | ok | ok | ok | ok | current |
| 2835 | ok | ok | ok | ok | ok | current |
| 2836 | ok | ok | ok | ok | ok | current |
| 2837 | ok | ok | ok | ok | ok | current |
| 2838 | ok | ok | ok | ok | ok | current |
| 2839 | ok | ok | ok | ok | ok | current |
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
| 2851 | ok | ok | ok | ok | ok | current |
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
| 2701 | 87857 | 140385 | 209.3 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2702 | 71674 | 135066 | 149.5 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2703 | 81048 | 143770 | 196.4 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2704 | 90814 | 152977 | 248.4 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2705 | 85049 | 125269 | 190.4 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2706 | 77994 | 176591 | 210.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2707 | 69689 | 133888 | 127.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2708 | 74911 | 138427 | 151.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2709 | 68511 | 120472 | 109.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2710 | 71209 | 129505 | 129.8 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2711 | 70813 | 173909 | 174.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2712 | 85014 | 160541 | 188.3 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2713 | 79976 | 237255 | 301.3 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 2714 | 83105 | 214389 | 241.4 | no | 1.00 | schedule_fee.value | goodwill.value | yes | yes | no | yes |
| 2715 | 69077 | 130314 | 115.8 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2716 | 106281 | 136816 | 265.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2717 | 70717 | 141874 | 146.7 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2718 | 83506 | 140352 | 183.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2719 | 82206 | 162607 | 197.9 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2720 | 91123 | 157524 | 214.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2721 | 80780 | 217292 | 405.5 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2722 | 75536 | 249757 | 300.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2723 | 79556 | 135466 | 148.8 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2724 | 72516 | 127388 | 111.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2725 | 86818 | 226811 | 277.7 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2726 | 90044 | 176572 | 219.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2727 | 77923 | 124886 | 129.8 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2728 | 93647 | 124915 | 225.5 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2729 | 99598 | 141109 | 263.1 | no | 1.00 | driver_compensation.value | driver_compensation.value | no | yes | no | no |
| 2730 | 69390 | 127659 | 130.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 2731 | 63487 | 141662 | 103.4 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2732 | 70201 | 217826 | 216.5 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2733 | 68830 | 120872 | 106.8 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2734 | 77464 | 123913 | 149.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2735 | - | - | 0.0 | yes | - | n/a | n/a | no | yes | no | no |
| 2736 | 76034 | 159104 | 188.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2737 | 65597 | 111117 | 101.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2738 | 81155 | 131320 | 164.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 2739 | 78966 | 136150 | 168.7 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2740 | 76054 | 123431 | 135.5 | no | 1.00 | waiting_time_fee.value | n/a | yes | yes | no | yes |
| 2741 | 69793 | 170293 | 162.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2742 | 74157 | 130056 | 147.1 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2743 | 79701 | 152604 | 210.2 | no | 0.75 | driver_compensation.value | driver_compensation.value | yes | yes | yes | yes |
| 2744 | 93399 | 166587 | 265.5 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2745 | 75980 | 129151 | 153.4 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2746 | 75815 | 175663 | 174.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | yes | yes |
| 2747 | 67842 | 127728 | 103.9 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2748 | 75147 | 131214 | 136.0 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2749 | 101366 | 200228 | 290.1 | yes | 0.50 | n/a | n/a | no | yes | no | no |
| 2750 | 89224 | 181971 | 247.1 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2751 | 67315 | 122853 | 90.4 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2752 | 72338 | 161717 | 148.3 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2753 | 75850 | 130743 | 148.2 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2754 | 72826 | 136500 | 144.6 | no | 1.00 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2755 | 79019 | 141656 | 166.7 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2756 | 72497 | 246198 | 288.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2757 | 68269 | 126175 | 117.3 | no | 0.75 | schedule_fee.value | n/a | yes | yes | no | yes |
| 2758 | 82227 | 124160 | 161.8 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2759 | - | - | 0.0 | yes | - | n/a | n/a | no | yes | no | no |
| 2760 | 78188 | 173935 | 196.3 | no | 1.00 | driver_compensation.value | driver_compensation.value | yes | yes | no | yes |
| 2801 | 70929 | 123564 | 152.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2802 | 63986 | 174941 | 205.9 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2803 | 65047 | 118677 | 108.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2804 | 61503 | 180556 | 180.7 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2805 | 70084 | 122687 | 127.3 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2806 | 58748 | 108424 | 81.8 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2807 | 61107 | 143719 | 104.6 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2808 | 63716 | 237038 | 258.1 | no | 1.00 | n/a | n/a | yes | yes | yes | no |
| 2809 | 70363 | 265895 | 326.4 | yes | 0.50 | n/a | n/a | no | no | no | no |
| 2810 | 68659 | 324576 | 335.6 | no | 0.75 | components.base_fare.value | n/a | yes | yes | yes | yes |
| 2811 | 70099 | 203862 | 220.8 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2812 | 64779 | 171565 | 186.9 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2813 | 59449 | 126220 | 100.1 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 2814 | 70849 | 110032 | 138.2 | no | 1.00 | charged_over_quote.value | n/a | yes | yes | no | yes |
| 2815 | 68249 | 125067 | 119.0 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 2816 | 72084 | 143928 | 157.2 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 2817 | 75295 | 120387 | 142.2 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2818 | 63748 | 136131 | 128.7 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2819 | 65883 | 125445 | 112.5 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2820 | 73007 | 114686 | 137.3 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2821 | 72421 | 119317 | 135.2 | no | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2822 | 65788 | 121101 | 112.8 | no | 0.75 | refund.refund_before_rounding.value | n/a | yes | yes | yes | yes |
| 2823 | 74116 | 196604 | 216.4 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 2824 | 67784 | 140812 | 149.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2825 | 68595 | 127750 | 144.7 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2826 | 75123 | 235810 | 246.7 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2827 | 75773 | 131405 | 179.9 | no | 1.00 | charged_total.value | n/a | yes | yes | no | yes |
| 2828 | 74613 | 141232 | 188.5 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2829 | 57836 | 112626 | 71.8 | yes | - | n/a | n/a | no | yes | no | no |
| 2830 | 64571 | 121791 | 108.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2831 | 86557 | 317018 | 411.9 | yes | 0.50 | n/a | n/a | no | yes | no | no |
| 2832 | 68362 | 117395 | 118.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2833 | 62896 | 127662 | 123.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2834 | 67425 | 266899 | 351.8 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2835 | 59153 | 133044 | 109.9 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2836 | 65515 | 115639 | 115.5 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2837 | 70311 | 170638 | 183.7 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2838 | 65167 | 150224 | 133.7 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2839 | 87667 | 231491 | 286.9 | no | 1.00 | erp_lines.lines[0].amount_sgd.value | n/a | yes | yes | no | yes |
| 2840 | 67278 | 399613 | 447.6 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2841 | 79368 | 119317 | 153.3 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2842 | 64822 | 139784 | 124.0 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2843 | 72119 | 115498 | 116.5 | no | 0.75 | n/a | n/a | yes | yes | no | yes |
| 2844 | 69529 | 174501 | 247.2 | no | 0.75 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2845 | 63549 | 121472 | 105.2 | no | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2846 | 60202 | 120826 | 105.6 | no | 1.00 | refund.refund_before_rounding.value | n/a | yes | yes | no | yes |
| 2847 | 61813 | 163119 | 133.7 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 2848 | 63613 | 151085 | 136.0 | no | 1.00 | refund.refund_before_rounding.value | n/a | yes | yes | no | yes |
| 2849 | 77611 | 147565 | 170.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2850 | 69149 | 226772 | 240.5 | yes | 1.00 | n/a | n/a | yes | yes | yes | yes |
| 2851 | 65783 | 262112 | 314.5 | no | 1.00 | charged_total.value | n/a | yes | yes | yes | yes |
| 2852 | 62645 | 124650 | 111.9 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2853 | 65836 | 168640 | 168.7 | yes | - | n/a | n/a | no | yes | no | no |
| 2854 | 62749 | 125224 | 121.8 | no | 1.00 | refund.payable.value | n/a | yes | yes | no | yes |
| 2855 | 64494 | 230298 | 276.2 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2856 | 70086 | 121664 | 125.7 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2857 | 69190 | 135437 | 160.4 | no | 1.00 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2858 | 61870 | 229984 | 312.3 | no | 0.75 | refund.payable.value | n/a | yes | yes | yes | yes |
| 2859 | 69077 | 118861 | 99.1 | yes | 1.00 | n/a | n/a | yes | yes | no | yes |
| 2860 | 68273 | 118227 | 121.6 | no | 1.00 | n/a | n/a | yes | yes | no | yes |

## Failures

### Case 2749

Failed on: ruling, amount_sgd, driver_compensation_sgd, referrals

- **ruling** — expected 'DRIVER_COMPENSATION', produced 'ESCALATE'
- **amount_sgd** — expected 3.6, produced null
- **driver_compensation_sgd** — expected 3.6, produced null
- **referrals** — expected referral not produced: POL-NS-05(iii)

### Case 2809

Failed on: ruling

- **ruling** — expected 'NO_ACTION', produced 'ESCALATE'

### Case 2829

Failed on: ruling, amount_sgd

- **ruling** — expected 'PARTIAL_REFUND', produced 'ESCALATE'
- **amount_sgd** — expected 5.75, produced null

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
- produced: "POL-NS-05(ii): record a false-arrival event against driver DRV-09709 — the 'I'm Here' marker tapped at 2026-09-11T07:38:35 was set while the GPS trace placed the vehicle at least 647.3 m from the pickup pin, and no qualifying in-geofence fix exists anywhere on the trip."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2710 — clause match

- expected: "POL-NS-05(ii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(ii) false-arrival record: the driver's 'arrived' marker at 2026-08-19T22:48:55+08:00 on TRP-02710 was placed while the trace's closest approach to the pickup pin was 517.41 m (threshold 300 m) and no qualifying in-geofence fix exists anywhere in the trip — record a false-arrival event against driver DRV-09710."
- clause keys, expected: POL-NS-05(ii)
- clause keys, produced: POL-NS-05(ii)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2723 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01 — driver-education item: the cancellation on TRP-02723 was recorded under reason code DRIVER_UNABLE_TO_LOCATE, which is not one of the three codes limb (d) recognises. Record the mis-selected reason code against DRV-09723 for driver education."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2724 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01: driver-education item — the trip was terminated under the mis-selected reason code DRIVER_UNABLE_TO_LOCATE while the driver's stationary fixes lay inside the POL-NS-02 arrival radius; record the mis-selected reason code against driver DRV-09724 for driver education."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01, POL-NS-02
- expected clauses matched: 1 of 1
- additional clauses offered: POL-NS-02
- additional clause(s) offered: POL-NS-02

### Case 2725 — clause match

- expected: "POL-NS-05(iii) false-arrival event recorded against the driver"
- produced: "POL-NS-05(iii): record a false-arrival event against driver DRV-09725 for the 'I'm Here' tap on trip TRP-02725 at 2026-08-22T18:15:10 — no qualifying in-geofence fix exists before 18:17:10 (dwell_start_offset_sec -120.0 s) and the vehicle was in motion outside the 50 m pickup radius — so that the pattern is visible to POL-NS-07 and to human review."
- clause keys, expected: POL-NS-05(iii)
- clause keys, produced: POL-NS-05(iii), POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: POL-NS-07
- additional clause(s) offered: POL-NS-07

### Case 2727 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.50 cancellation fee in full"
- produced: "POL-NS-07: the escalation packet must direct the human reviewer to refund the rider's SGD 4.50 cancellation fee in full; the amount is held rather than collected or refunded meanwhile, as POL-NS-09 requires."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07, POL-NS-09
- expected clauses matched: 1 of 1
- additional clauses offered: POL-NS-09
- additional clause(s) offered: POL-NS-09

### Case 2747 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01 — the cancellation was recorded under reason code DRIVER_UNABLE_TO_LOCATE although the driver's stationary fixes lay inside the arrival radius and the fee is refundable; the mis-selected reason code is referred as a driver-education item."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2748 — clause match

- expected: "POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_LOCATE recorded as a driver-education item"
- produced: "POL-NS-01 — driver education: the cancellation was recorded under reason code DRIVER_UNABLE_TO_LOCATE, which POL-NS-01(d) does not recognise for a no-show charge, while the driver's own stationary fixes were inside the pickup arrival radius. The code was mis-selected and should be corrected for this driver."
- clause keys, expected: POL-NS-01
- clause keys, produced: POL-NS-01, POL-NS-01(d)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2749 — **no clause match**

- expected: "POL-NS-05(iii) false-arrival event recorded against the driver"
- produced: _(none)_
- clause keys, expected: POL-NS-05(iii)
- clause keys, produced: _(none)_
- expected clauses matched: 0 of 1
- additional clauses offered: _(none)_
- expected referral not produced: POL-NS-05(iii)

### Case 2751 — clause match

- expected: "POL-NS-07 escalation packet: instruct the reviewer to refund the rider's SGD 4.50 cancellation fee in full"
- produced: "POL-NS-07: the escalation packet must direct the human reviewer to refund the rider's cancellation fee of SGD 4.50 in full."
- clause keys, expected: POL-NS-07
- clause keys, produced: POL-NS-07
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2815 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: ERP gantry line of SGD 2.00 on EV-FARE-02815 that the trace never passes"
- produced: "POL-RD-09(4) billing integrity: the 'AYE Alexandra Rd gantry' ERP line of $2.00 on TRP-02815 is charged for a gantry the GPS trace never crosses (nearest fix 6,130.08 m away, far outside the 250 m match radius); record it as a billing-integrity finding, refund it as a standalone pass-through correction, and review why the line was charged."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2816 — clause match

- expected: "POL-RD-09(4) billing-integrity finding: ERP gantry line of SGD 3.00 on EV-FARE-02816 that the trace never passes"
- produced: "POL-RD-09(4) billing-integrity referral: the AYE Alexandra Rd gantry ERP line of SGD 3.00 itemised on EV-FARE-02816 was charged for a gantry the EV-GPS-02816 trace never passes (nearest of 162 fixes 330.73 m, outside the 250 m match radius, trace complete at 100.0% coverage and a steady 10 s interval); the line is refunded as a standalone pass-through correction and the gantry charge on TRP-02816 is flagged for billing-integrity review."
- clause keys, expected: POL-RD-09(4)
- clause keys, produced: POL-RD-09(4)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2827 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c): refer driver DRV-09827 to driver-conduct review — a repeat deviation pattern is established (deviation_flags_90d 3 against completed_trips_90d 180, meeting the clause's '3 or more' limb) and the deviation on TRP-02827 is both MATERIAL (60.0% excess) and substantiated on this trip's own GPS trace."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: _(none)_

### Case 2851 — clause match

- expected: "POL-RD-06(c) driver-conduct review"
- produced: "POL-RD-06(c): refer driver DRV-09851 to driver-conduct review — a repeat-deviation pattern is established on driver_profile.deviation_flags_90d = 3 (POL-RD-06) and the deviation on this trip is MATERIAL (60.0%, POL-RD-01). The review rides with this ruling and does not delay or displace the refund."
- clause keys, expected: POL-RD-06(c)
- clause keys, produced: POL-RD-01, POL-RD-06, POL-RD-06(c)
- expected clauses matched: 1 of 1
- additional clauses offered: POL-RD-01, POL-RD-06
- additional clause(s) offered: POL-RD-01, POL-RD-06

## Escalation calibration

| | |
|---|---|
| Cases graded | 120 |
| Cases graded, by number | 2701, 2702, 2703, 2704, 2705, 2706, 2707, 2708, 2709, 2710, 2711, 2712, 2713, 2714, 2715, 2716, 2717, 2718, 2719, 2720, 2721, 2722, 2723, 2724, 2725, 2726, 2727, 2728, 2729, 2730, 2731, 2732, 2733, 2734, 2735, 2736, 2737, 2738, 2739, 2740, 2741, 2742, 2743, 2744, 2745, 2746, 2747, 2748, 2749, 2750, 2751, 2752, 2753, 2754, 2755, 2756, 2757, 2758, 2759, 2760, 2801, 2802, 2803, 2804, 2805, 2806, 2807, 2808, 2809, 2810, 2811, 2812, 2813, 2814, 2815, 2816, 2817, 2818, 2819, 2820, 2821, 2822, 2823, 2824, 2825, 2826, 2827, 2828, 2829, 2830, 2831, 2832, 2833, 2834, 2835, 2836, 2837, 2838, 2839, 2840, 2841, 2842, 2843, 2844, 2845, 2846, 2847, 2848, 2849, 2850, 2851, 2852, 2853, 2854, 2855, 2856, 2857, 2858, 2859, 2860 |
| Whole corpus graded | no — 120 of 120 cases |
| Expected escalations | 17 |
| Produced escalations | 20 |
| **Escalation rate (on these 120 cases)** | **16.7%** |
| Precision on ESCALATE (on these 120 cases) | 16 of 20 = 0.8 |
| Recall on ESCALATE (on these 120 cases) | 16 of 17 = 0.941 |

### Raw counts — these are what survive subsetting

Rates move with the base rate of the set they were computed on, precision and recall included. On a selected subset they are not comparable to the corpus base rate. The counts below do not move.

| | count | cases |
|---|---|---|
| True positives (key and run both ESCALATE) | 16 | 2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2831, 2834, 2835, 2838, 2850, 2855, 2859 |
| False positives (run ESCALATE, key does not) | 4 | 2749, 2809, 2829, 2853 |
| False negatives (key ESCALATE, run does not) | 1 | 2858 |
| Over-escalations (= false positives) | 4 | 2749, 2809, 2829, 2853 |
| Under-escalations (= false negatives) | 1 | 2858 |
| Expected escalations in this set | 17 | 2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2831, 2834, 2835, 2838, 2850, 2855, 2858, 2859 |
| Produced escalations in this set | 20 | 2727, 2731, 2732, 2735, 2749, 2751, 2755, 2756, 2759, 2809, 2826, 2829, 2831, 2834, 2835, 2838, 2850, 2853, 2855, 2859 |

Rates on a selected subset are not comparable to the corpus base rate, so the corpus target is deliberately not printed beside them.

### Over-escalation and under-escalation, counted separately

These are different failures and are never summed into one figure. Over-escalation is a case the run sent to a human that did not need one; under-escalation is a case it decided that a human should have decided.

| | count | cases |
|---|---|---|
| Over-escalations (produced ESCALATE, key does not) | 4 | 2749, 2809, 2829, 2853 |
| Under-escalations (key ESCALATE, produced does not) | 1 | 2858 |

### The INDETERMINATE cases, kept out of the rate

In this set the key escalates 17 cases whose record genuinely does not settle the question, and 0 cases on substantive grounds. A run that answers an INDETERMINATE case instead of escalating it has not been decisive; it has invented an answer, and that is the failure that matters most. It is counted here rather than averaged into the escalation rate.

| | |
|---|---|
| INDETERMINATE cases the key escalates | 2727, 2731, 2732, 2735, 2751, 2755, 2756, 2759, 2826, 2831, 2834, 2835, 2838, 2850, 2855, 2858, 2859 |
| ... the run escalated | 16 of 17 |
| **... the run ruled confidently instead** | **1 of 17** |
| Substantive escalations the key makes | _none_ |
| ... the run escalated | 0 of 0 |

Cases ruled confidently where the record does not settle the question: 2858.

## How this was checked

This report is of the development set `dev-v2-ext`, whose own answer key is `eval/answers/dev-v2-ext/ground_truth.json`. The grader's self-test is written against the corpus key and does not cover this set, so the figures above are a measurement against this set's own key and of nothing else. No model is involved in the grading at any point.
