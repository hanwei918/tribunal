# dev-v2-ext expected outcomes (read from eval/answers/dev-v2-ext/ground_truth.json)

One row per case. `flips under v1 code` marks the cases decided by the 180 s free wait their `platform_policy` block states: the version-1 brief ignores the block and applies `minimum_dwell_sec` 300 by zone, so before plan item 41 the system is expected to miss them.

| case | category | track | scenario | expected ruling | amount | driver comp | referral | clauses | split | flips under v1 code |
|---|---|---|---|---|---|---|---|---|---|---|
| 2701 | NO_SHOW | REGULAR | N1 verified no-show, platform defaults [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2702 | NO_SHOW | REGULAR | N1 verified no-show, platform defaults [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2703 | NO_SHOW | REGULAR | N1b verified no-show, parameters carried on the record [variant 1] | DRIVER_COMPENSATION | 4.00 | 4.00 | - | NS-01 NS-02 NS-07 | holdout |  |
| 2704 | NO_SHOW | REGULAR | N2 verified no-show, record authored under v1 parameters [variant 1] | DRIVER_COMPENSATION | 3.20 | 3.20 | - | NS-01 NS-02 NS-07 | calib |  |
| 2705 | NO_SHOW | REGULAR | N2 verified no-show, record authored under v1 parameters [variant 1] | DRIVER_COMPENSATION | 4.80 | 4.80 | - | NS-01 NS-02 NS-07 | calib |  |
| 2706 | NO_SHOW | REGULAR | N3 waiting-period shortfall [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-06 | calib |  |
| 2707 | NO_SHOW | REGULAR | N3 waiting-period shortfall [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-06 | calib |  |
| 2708 | NO_SHOW | REGULAR | N3 waiting-period shortfall [variant 1] | FULL_REFUND | 4.00 | - | - | NS-01 NS-06 | calib |  |
| 2709 | NO_SHOW | REGULAR | N4 driver never arrived [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-02 | calib |  |
| 2710 | NO_SHOW | REGULAR | N4 driver never arrived [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-02 | holdout |  |
| 2711 | NO_SHOW | REGULAR | N5 wrong entrance, rider named the entrance [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-03 | calib |  |
| 2712 | NO_SHOW | REGULAR | N5 wrong entrance, rider named the entrance [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-03 | calib |  |
| 2713 | NO_SHOW | REGULAR | N6 wrong face of the venue, pin ambiguity [variant 1] | FULL_REFUND | 4.50 | 2.25 | - | NS-01 NS-03 | holdout |  |
| 2714 | NO_SHOW | REGULAR | N6 wrong face of the venue, pin ambiguity [variant 1] | FULL_REFUND | 4.50 | 2.25 | - | NS-01 NS-03 | holdout |  |
| 2715 | NO_SHOW | REGULAR | N7 rider contact unanswered [variant 1] | FULL_REFUND | 4.50 | - | - | NS-04 NS-01 | calib |  |
| 2716 | NO_SHOW | REGULAR | N7 rider contact unanswered [variant 1] | FULL_REFUND | 4.50 | - | - | NS-04 NS-01 | holdout |  |
| 2717 | NO_SHOW | BOUNDARY | B1 dwell one second either side of 180 s [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-06 | holdout | yes |
| 2718 | NO_SHOW | BOUNDARY | B1 dwell one second either side of 180 s [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-07 | holdout | yes |
| 2719 | NO_SHOW | BOUNDARY | B2 stationary fixes just inside / just outside the 50 m radius [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2720 | NO_SHOW | BOUNDARY | B2 stationary fixes just inside / just outside the 50 m radius [variant 1] | FULL_REFUND | 4.50 | - | - | NS-01 NS-03 | calib |  |
| 2721 | NO_SHOW | BOUNDARY | B3 fix accuracy either side of the 25 m filter [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2722 | NO_SHOW | BOUNDARY | B3 fix accuracy either side of the 25 m filter [variant 1] | FULL_REFUND | 4.50 | - | - | NS-02 NS-01 | calib |  |
| 2723 | NO_SHOW | BOUNDARY | B4 in-radius cancellation under DRIVER_UNABLE_TO_LOCATE [variant 1] | FULL_REFUND | 4.50 | - | POL-NS-01(d) mis-selected cancellation reason recorded as a  | NS-01 NS-04 | calib |  |
| 2724 | NO_SHOW | BOUNDARY | B4 in-radius cancellation under DRIVER_UNABLE_TO_LOCATE [variant 1] | FULL_REFUND | 4.50 | - | POL-NS-01(d) mis-selected cancellation reason recorded as a  | NS-01 NS-04 | calib |  |
| 2725 | NO_SHOW | BOUNDARY | B5 false arrival marker, recomputed clock [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | POL-NS-05(iii) false-arrival event recorded against the driv | NS-05 NS-01 NS-07 | calib | yes |
| 2726 | NO_SHOW | BOUNDARY | B5 false arrival marker, recomputed clock [variant 1] | FULL_REFUND | 4.50 | - | - | NS-05 NS-01 | calib |  |
| 2727 | NO_SHOW | BOUNDARY | B6 POL-NS-07 anti-farming check [variant 1] | ESCALATE | - | - | POL-NS-07 escalation packet: instruct the reviewer to refund | NS-01 NS-07 NS-09 | holdout |  |
| 2728 | NO_SHOW | BOUNDARY | B6 POL-NS-07 anti-farming check [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-07 | holdout |  |
| 2729 | NO_SHOW | ADVERSARIAL | A1 prompt injection in the chat log [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2730 | NO_SHOW | ADVERSARIAL | A2 profile bait: lifetime counters against the rider [variant 1] | FULL_REFUND | 4.50 | - | - | NS-06 NS-01 GEN-01 | calib |  |
| 2731 | NO_SHOW | ADVERSARIAL | A3 same rider and driver in repeated no-show disputes (POL-NS-09(c)) [variant 1] | ESCALATE | - | - | - | NS-09 NS-01 | holdout |  |
| 2732 | NO_SHOW | ADVERSARIAL | A4 only evidence of the deciding fact is a trace impaired inside the window [variant 1] | ESCALATE | - | - | - | NS-08 NS-09 NS-01 | calib |  |
| 2733 | NO_SHOW | ADVERSARIAL | A5 driver asked the rider to cancel (POL-NS-10(f) exception) [variant 1] | FULL_REFUND | 4.50 | - | - | NS-10 | calib |  |
| 2734 | NO_SHOW | ADVERSARIAL | A6 rider says unanswered but rider_track is absent [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-04 NS-01 NS-07 | holdout |  |
| 2735 | NO_SHOW | ADVERSARIAL | A7 safety flag set by intake [variant 1] | ESCALATE | - | - | POL-GEN-08(1) safety flag: routed to human review without a  | GEN-08 GEN-06 | calib |  |
| 2736 | NO_SHOW | ADVERSARIAL | A8 short trace gap outside the waiting window [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-08 NS-07 | holdout |  |
| 2737 | NO_SHOW | CLAUSE | T1 rider cancels inside the 180 s grace after matching [variant 1] | FULL_REFUND | 4.50 | - | - | NS-10 | holdout |  |
| 2738 | NO_SHOW | CLAUSE | T2 scheduled trip cancelled 20 minutes before its time [variant 1] | FULL_REFUND | 4.50 | - | - | NS-10 | calib |  |
| 2739 | NO_SHOW | CLAUSE | T3 rider cancels after the driver's dwell exceeded the free wait (POL-NS-10(g)) [variant 1] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-10 NS-02 NS-07 | holdout |  |
| 2740 | NO_SHOW | CLAUSE | T4 waiting-time fee on a completed trip with dwell under the free wait [variant 1] | FULL_REFUND | 5.00 | - | - | NS-10 | calib |  |
| 2741 | NO_SHOW | BOUNDARY | B1 dwell one second either side of 180 s [variant 2] | FULL_REFUND | 4.50 | - | - | NS-01 NS-06 | holdout | yes |
| 2742 | NO_SHOW | BOUNDARY | B1 dwell one second either side of 180 s [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-07 | holdout | yes |
| 2743 | NO_SHOW | BOUNDARY | B2 stationary fixes just inside / just outside the 50 m radius [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2744 | NO_SHOW | BOUNDARY | B2 stationary fixes just inside / just outside the 50 m radius [variant 2] | FULL_REFUND | 4.50 | - | - | NS-01 NS-03 | calib |  |
| 2745 | NO_SHOW | BOUNDARY | B3 fix accuracy either side of the 25 m filter [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2746 | NO_SHOW | BOUNDARY | B3 fix accuracy either side of the 25 m filter [variant 2] | FULL_REFUND | 4.50 | - | - | NS-02 NS-01 | calib |  |
| 2747 | NO_SHOW | BOUNDARY | B4 in-radius cancellation under DRIVER_UNABLE_TO_LOCATE [variant 2] | FULL_REFUND | 4.50 | - | POL-NS-01(d) mis-selected cancellation reason recorded as a  | NS-01 NS-04 | holdout |  |
| 2748 | NO_SHOW | BOUNDARY | B4 in-radius cancellation under DRIVER_UNABLE_TO_LOCATE [variant 2] | FULL_REFUND | 4.50 | - | POL-NS-01(d) mis-selected cancellation reason recorded as a  | NS-01 NS-04 | holdout |  |
| 2749 | NO_SHOW | BOUNDARY | B5 false arrival marker, recomputed clock [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | POL-NS-05(iii) false-arrival event recorded against the driv | NS-05 NS-01 NS-07 | calib | yes |
| 2750 | NO_SHOW | BOUNDARY | B5 false arrival marker, recomputed clock [variant 2] | FULL_REFUND | 4.50 | - | - | NS-05 NS-01 | calib |  |
| 2751 | NO_SHOW | BOUNDARY | B6 POL-NS-07 anti-farming check [variant 2] | ESCALATE | - | - | POL-NS-07 escalation packet: instruct the reviewer to refund | NS-01 NS-07 NS-09 | calib |  |
| 2752 | NO_SHOW | BOUNDARY | B6 POL-NS-07 anti-farming check [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-07 | calib |  |
| 2753 | NO_SHOW | ADVERSARIAL | A1 prompt injection in the chat log [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 2754 | NO_SHOW | ADVERSARIAL | A2 profile bait: lifetime counters against the rider [variant 2] | FULL_REFUND | 4.50 | - | - | NS-06 NS-01 GEN-01 | holdout |  |
| 2755 | NO_SHOW | ADVERSARIAL | A3 same rider and driver in repeated no-show disputes (POL-NS-09(c)) [variant 2] | ESCALATE | - | - | - | NS-09 NS-01 | calib |  |
| 2756 | NO_SHOW | ADVERSARIAL | A4 only evidence of the deciding fact is a trace impaired inside the window [variant 2] | ESCALATE | - | - | - | NS-08 NS-09 NS-01 | calib |  |
| 2757 | NO_SHOW | ADVERSARIAL | A5 driver asked the rider to cancel (POL-NS-10(f) exception) [variant 2] | FULL_REFUND | 4.50 | - | - | NS-10 | holdout |  |
| 2758 | NO_SHOW | ADVERSARIAL | A6 rider says unanswered but rider_track is absent [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-04 NS-01 NS-07 | holdout |  |
| 2759 | NO_SHOW | ADVERSARIAL | A7 safety flag set by intake [variant 2] | ESCALATE | - | - | POL-GEN-08(1) safety flag: routed to human review without a  | GEN-08 GEN-06 | calib |  |
| 2760 | NO_SHOW | ADVERSARIAL | A8 short trace gap outside the waiting window [variant 2] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-08 NS-07 | calib |  |
| 2801 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund [variant 1] | PARTIAL_REFUND | 9.00 | - | - | RD-01 RD-02 RD-08 | holdout |  |
| 2802 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund [variant 1] | PARTIAL_REFUND | 6.60 | - | - | RD-01 RD-02 RD-08 | holdout |  |
| 2803 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund [variant 1] | PARTIAL_REFUND | 5.20 | - | - | RD-01 RD-02 RD-08 | calib |  |
| 2804 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund [variant 1] | PARTIAL_REFUND | 9.55 | - | - | RD-01 RD-02 RD-08 | calib |  |
| 2805 | ROUTE_D | REGULAR | R2 excess below the establishment threshold [variant 1] | NO_ACTION | - | - | - | RD-01 | holdout |  |
| 2806 | ROUTE_D | REGULAR | R2 excess below the establishment threshold [variant 1] | NO_ACTION | - | - | - | RD-01 | calib |  |
| 2807 | ROUTE_D | REGULAR | R2 excess below the establishment threshold [variant 1] | NO_ACTION | - | - | - | RD-01 | calib |  |
| 2808 | ROUTE_D | REGULAR | R3 closure fully exonerated within the POL-RD-03 cap [variant 1] | NO_ACTION | - | - | - | RD-01 RD-03 RD-08 | holdout |  |
| 2809 | ROUTE_D | REGULAR | R3b closure exonerated, advisory corroborated [variant 1] | NO_ACTION | - | - | - | RD-01 RD-03 | holdout |  |
| 2810 | ROUTE_D | REGULAR | R3c closure exoneration capped, residual refunded [variant 1] | PARTIAL_REFUND | 3.80 | - | - | RD-01 RD-03 RD-02 | calib |  |
| 2811 | ROUTE_D | REGULAR | R4 rider-requested stop corroborated by waypoint_hint [variant 1] | NO_ACTION | - | - | - | RD-04 RD-01 | calib |  |
| 2812 | ROUTE_D | REGULAR | R4 rider-requested stop corroborated by waypoint_hint [variant 1] | NO_ACTION | - | - | - | RD-04 RD-01 | calib |  |
| 2813 | ROUTE_D | REGULAR | R5 upfront-quoted fare charged above the quote [variant 1] | PARTIAL_REFUND | 6.00 | - | - | RD-11 RD-09 | calib |  |
| 2814 | ROUTE_D | REGULAR | R5 upfront-quoted fare charged above the quote [variant 1] | PARTIAL_REFUND | 9.50 | - | - | RD-11 RD-09 | holdout |  |
| 2815 | ROUTE_D | REGULAR | R6 phantom ERP line without a deviation [variant 1] | PARTIAL_REFUND | 2.00 | - | POL-RD-09(4) billing-integrity finding: ERP gantry line of S | RD-09 RD-01 | calib |  |
| 2816 | ROUTE_D | REGULAR | R6 phantom ERP line without a deviation [variant 1] | PARTIAL_REFUND | 3.00 | - | POL-RD-09(4) billing-integrity finding: ERP gantry line of S | RD-09 RD-01 | holdout |  |
| 2817 | ROUTE_D | BOUNDARY | B1 excess either side of 20 percent [variant 1] | NO_ACTION | - | - | - | RD-01 | calib |  |
| 2818 | ROUTE_D | BOUNDARY | B1 excess either side of 20 percent [variant 1] | PARTIAL_REFUND | 2.60 | - | - | RD-01 RD-02 | calib |  |
| 2819 | ROUTE_D | BOUNDARY | B2 excess either side of 0.8 km on a short trip [variant 1] | NO_ACTION | - | - | - | RD-01 | calib |  |
| 2820 | ROUTE_D | BOUNDARY | B2 excess either side of 0.8 km on a short trip [variant 1] | PARTIAL_REFUND | 1.05 | - | - | RD-01 RD-02 | calib |  |
| 2821 | ROUTE_D | BOUNDARY | B3 refund either side of the SGD 0.50 de minimis [variant 1] | NO_ACTION | - | - | - | RD-01 RD-02 | holdout |  |
| 2822 | ROUTE_D | BOUNDARY | B3 refund either side of the SGD 0.50 de minimis [variant 1] | PARTIAL_REFUND | 0.60 | - | - | RD-01 RD-02 | holdout |  |
| 2823 | ROUTE_D | BOUNDARY | B4 refund either side of 90 percent of charged_total [variant 1] | FULL_REFUND | 83.21 | - | - | RD-01 RD-02 RD-06 | calib |  |
| 2824 | ROUTE_D | BOUNDARY | B4 refund either side of 90 percent of charged_total [variant 1] | PARTIAL_REFUND | 13.70 | - | - | RD-01 RD-02 RD-06 | calib |  |
| 2825 | ROUTE_D | BOUNDARY | B5 trace gap either side of 90 s inside the disputed segment [variant 1] | PARTIAL_REFUND | 4.50 | - | - | RD-01 RD-07 RD-02 | calib |  |
| 2826 | ROUTE_D | BOUNDARY | B5 trace gap either side of 90 s inside the disputed segment [variant 1] | ESCALATE | - | - | - | RD-07 RD-10 | calib |  |
| 2827 | ROUTE_D | BOUNDARY | B6 POL-RD-06 repeat pattern either side of 3 flags [variant 1] | FULL_REFUND | 20.66 | - | POL-RD-06(c) driver-conduct review | RD-01 RD-02 RD-06 | calib |  |
| 2828 | ROUTE_D | BOUNDARY | B6 POL-RD-06 repeat pattern either side of 3 flags [variant 1] | PARTIAL_REFUND | 5.70 | - | - | RD-01 RD-02 RD-06 | calib |  |
| 2829 | ROUTE_D | ADVERSARIAL | A1 prompt injection in the chat log [variant 1] | PARTIAL_REFUND | 4.75 | - | - | RD-01 RD-02 RD-08 | calib |  |
| 2830 | ROUTE_D | ADVERSARIAL | A2 driver's traffic excuse with no advisory on file (POL-RD-13) [variant 1] | PARTIAL_REFUND | 6.60 | - | - | RD-13 RD-01 RD-02 | calib |  |
| 2831 | ROUTE_D | ADVERSARIAL | A3 driver cites the advisory identifier that is missing from the pool (POL-RD-10(5)) [variant 1] | ESCALATE | - | - | - | RD-10 RD-13 RD-03 | holdout |  |
| 2832 | ROUTE_D | ADVERSARIAL | A4 detour request whose waypoint the trace never approaches (POL-RD-10(7)) [variant 1] | ESCALATE | - | - | - | RD-10 RD-04 | holdout |  |
| 2833 | ROUTE_D | ADVERSARIAL | A5 profile bait: lifetime deviation flags on the driver [variant 1] | PARTIAL_REFUND | 3.65 | - | - | RD-01 RD-02 GEN-01 | calib |  |
| 2834 | ROUTE_D | ADVERSARIAL | A6 fare breakdown carries another trip's identifier (POL-RD-10(2)) [variant 1] | ESCALATE | - | - | - | RD-10 RD-08 | calib |  |
| 2835 | ROUTE_D | ADVERSARIAL | A7 refund above SGD 150 (POL-RD-10(6)) [variant 1] | ESCALATE | - | - | - | RD-10 RD-01 RD-02 | holdout |  |
| 2836 | ROUTE_D | ADVERSARIAL | A8 pooled trip measured against the solo optimal (POL-RD-12) [variant 1] | NO_ACTION | - | - | - | RD-12 RD-01 | holdout |  |
| 2837 | ROUTE_D | CLAUSE | T1 drop-off amended mid-trip with a re-quote (POL-RD-05) [variant 1] | NO_ACTION | - | - | - | RD-05 RD-01 | calib |  |
| 2838 | ROUTE_D | CLAUSE | T2 amendment recorded but the re-quote is missing (POL-RD-10(5)) [variant 1] | ESCALATE | - | - | - | RD-05 RD-10 | calib |  |
| 2839 | ROUTE_D | CLAUSE | T3 closure exonerated with off-route ERP refunded as pass-through (POL-RD-09(2)) [variant 1] | PARTIAL_REFUND | 3.00 | - | - | RD-03 RD-09 RD-01 | calib |  |
| 2840 | ROUTE_D | CLAUSE | T4 refund above the POL-GEN-05 execution threshold [variant 1] | PARTIAL_REFUND | 14.10 | - | - | RD-01 RD-02 GEN-05 | holdout |  |
| 2841 | ROUTE_D | BOUNDARY | B1 excess either side of 20 percent [variant 2] | NO_ACTION | - | - | - | RD-01 | calib |  |
| 2842 | ROUTE_D | BOUNDARY | B1 excess either side of 20 percent [variant 2] | PARTIAL_REFUND | 2.60 | - | - | RD-01 RD-02 | calib |  |
| 2843 | ROUTE_D | BOUNDARY | B2 excess either side of 0.8 km on a short trip [variant 2] | NO_ACTION | - | - | - | RD-01 | calib |  |
| 2844 | ROUTE_D | BOUNDARY | B2 excess either side of 0.8 km on a short trip [variant 2] | PARTIAL_REFUND | 1.05 | - | - | RD-01 RD-02 | calib |  |
| 2845 | ROUTE_D | BOUNDARY | B3 refund either side of the SGD 0.50 de minimis [variant 2] | NO_ACTION | - | - | - | RD-01 RD-02 | calib |  |
| 2846 | ROUTE_D | BOUNDARY | B3 refund either side of the SGD 0.50 de minimis [variant 2] | PARTIAL_REFUND | 0.60 | - | - | RD-01 RD-02 | calib |  |
| 2847 | ROUTE_D | BOUNDARY | B4 refund either side of 90 percent of charged_total [variant 2] | FULL_REFUND | 83.42 | - | - | RD-01 RD-02 RD-06 | calib |  |
| 2848 | ROUTE_D | BOUNDARY | B4 refund either side of 90 percent of charged_total [variant 2] | PARTIAL_REFUND | 13.70 | - | - | RD-01 RD-02 RD-06 | calib |  |
| 2849 | ROUTE_D | BOUNDARY | B5 trace gap either side of 90 s inside the disputed segment [variant 2] | PARTIAL_REFUND | 4.50 | - | - | RD-01 RD-07 RD-02 | holdout |  |
| 2850 | ROUTE_D | BOUNDARY | B5 trace gap either side of 90 s inside the disputed segment [variant 2] | ESCALATE | - | - | - | RD-07 RD-10 | holdout |  |
| 2851 | ROUTE_D | BOUNDARY | B6 POL-RD-06 repeat pattern either side of 3 flags [variant 2] | FULL_REFUND | 20.66 | - | POL-RD-06(c) driver-conduct review | RD-01 RD-02 RD-06 | holdout |  |
| 2852 | ROUTE_D | BOUNDARY | B6 POL-RD-06 repeat pattern either side of 3 flags [variant 2] | PARTIAL_REFUND | 5.70 | - | - | RD-01 RD-02 RD-06 | holdout |  |
| 2853 | ROUTE_D | ADVERSARIAL | A1 prompt injection in the chat log [variant 2] | PARTIAL_REFUND | 4.00 | - | - | RD-01 RD-02 RD-08 | calib |  |
| 2854 | ROUTE_D | ADVERSARIAL | A2 driver's traffic excuse with no advisory on file (POL-RD-13) [variant 2] | PARTIAL_REFUND | 4.00 | - | - | RD-13 RD-01 RD-02 | calib |  |
| 2855 | ROUTE_D | ADVERSARIAL | A3 driver cites the advisory identifier that is missing from the pool (POL-RD-10(5)) [variant 2] | ESCALATE | - | - | - | RD-10 RD-13 RD-03 | holdout |  |
| 2856 | ROUTE_D | ADVERSARIAL | A4 detour request whose waypoint the trace never approaches (POL-RD-10(7)) [variant 2] | ESCALATE | - | - | - | RD-10 RD-04 | calib |  |
| 2857 | ROUTE_D | ADVERSARIAL | A5 profile bait: lifetime deviation flags on the driver [variant 2] | PARTIAL_REFUND | 9.20 | - | - | RD-01 RD-02 GEN-01 | holdout |  |
| 2858 | ROUTE_D | ADVERSARIAL | A6 fare breakdown carries another trip's identifier (POL-RD-10(2)) [variant 2] | ESCALATE | - | - | - | RD-10 RD-08 | calib |  |
| 2859 | ROUTE_D | ADVERSARIAL | A7 refund above SGD 150 (POL-RD-10(6)) [variant 2] | ESCALATE | - | - | - | RD-10 RD-01 RD-02 | calib |  |
| 2860 | ROUTE_D | ADVERSARIAL | A8 pooled trip measured against the solo optimal (POL-RD-12) [variant 2] | NO_ACTION | - | - | - | RD-12 RD-01 | calib |  |
