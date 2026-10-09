# dev-v2 expected outcomes (read from eval/answers/dev-v2/ground_truth.json)

One row per case. `flips under v1 code` marks the cases decided by the 180 s free wait their `platform_policy` block states: the version-1 brief ignores the block and applies `minimum_dwell_sec` 300 by zone, so before plan item 41 the system is expected to miss them.

| case | category | track | scenario | expected ruling | amount | driver comp | referral | clauses | split | flips under v1 code |
|---|---|---|---|---|---|---|---|---|---|---|
| 1701 | NO_SHOW | REGULAR | N1 verified no-show, platform defaults | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | holdout |  |
| 1702 | NO_SHOW | REGULAR | N1 verified no-show, platform defaults | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 1703 | NO_SHOW | REGULAR | N1b verified no-show, parameters carried on the record | DRIVER_COMPENSATION | 4.00 | 4.00 | - | NS-01 NS-02 NS-07 | calib |  |
| 1704 | NO_SHOW | REGULAR | N2 verified no-show, record authored under v1 parameters | DRIVER_COMPENSATION | 3.20 | 3.20 | - | NS-01 NS-02 NS-07 | calib |  |
| 1705 | NO_SHOW | REGULAR | N2 verified no-show, record authored under v1 parameters | DRIVER_COMPENSATION | 4.80 | 4.80 | - | NS-01 NS-02 NS-07 | holdout |  |
| 1706 | NO_SHOW | REGULAR | N3 waiting-period shortfall | FULL_REFUND | 4.50 | - | - | NS-01 NS-06 | calib |  |
| 1707 | NO_SHOW | REGULAR | N3 waiting-period shortfall | FULL_REFUND | 4.50 | - | - | NS-01 NS-06 | holdout |  |
| 1708 | NO_SHOW | REGULAR | N3 waiting-period shortfall | FULL_REFUND | 4.00 | - | - | NS-01 NS-06 | calib |  |
| 1709 | NO_SHOW | REGULAR | N4 driver never arrived | FULL_REFUND | 4.50 | - | POL-NS-05(ii) false-arrival event recorded against the drive | NS-05 NS-02 NS-01 | calib |  |
| 1710 | NO_SHOW | REGULAR | N4 driver never arrived | FULL_REFUND | 4.50 | - | POL-NS-05(ii) false-arrival event recorded against the drive | NS-05 NS-02 NS-01 | holdout |  |
| 1711 | NO_SHOW | REGULAR | N5 wrong entrance, rider named the entrance | FULL_REFUND | 4.50 | - | - | NS-01 NS-03 | calib |  |
| 1712 | NO_SHOW | REGULAR | N5 wrong entrance, rider named the entrance | FULL_REFUND | 4.50 | - | - | NS-01 NS-03 | calib |  |
| 1713 | NO_SHOW | REGULAR | N6 wrong face of the venue, pin ambiguity | FULL_REFUND | 4.50 | 2.25 | - | NS-01 NS-03 | holdout |  |
| 1714 | NO_SHOW | REGULAR | N6 wrong face of the venue, pin ambiguity | FULL_REFUND | 4.50 | 2.25 | - | NS-01 NS-03 | calib |  |
| 1715 | NO_SHOW | REGULAR | N7 rider contact unanswered | FULL_REFUND | 4.50 | - | - | NS-04 NS-01 | holdout |  |
| 1716 | NO_SHOW | REGULAR | N7 rider contact unanswered | FULL_REFUND | 4.50 | - | - | NS-04 NS-01 | calib |  |
| 1717 | NO_SHOW | BOUNDARY | B1 dwell one second either side of 180 s | FULL_REFUND | 4.50 | - | - | NS-01 NS-06 | calib | yes |
| 1718 | NO_SHOW | BOUNDARY | B1 dwell one second either side of 180 s | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-07 | calib | yes |
| 1719 | NO_SHOW | BOUNDARY | B2 stationary fixes just inside / just outside the 50 m radius | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 1720 | NO_SHOW | BOUNDARY | B2 stationary fixes just inside / just outside the 50 m radius | FULL_REFUND | 4.50 | - | - | NS-01 NS-03 | calib |  |
| 1721 | NO_SHOW | BOUNDARY | B3 fix accuracy either side of the 25 m filter | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 1722 | NO_SHOW | BOUNDARY | B3 fix accuracy either side of the 25 m filter | FULL_REFUND | 4.50 | - | - | NS-02 NS-01 | calib |  |
| 1723 | NO_SHOW | BOUNDARY | B4 in-radius cancellation under DRIVER_UNABLE_TO_LOCATE | FULL_REFUND | 4.50 | - | POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_ | NS-01 NS-04 | holdout |  |
| 1724 | NO_SHOW | BOUNDARY | B4 in-radius cancellation under DRIVER_UNABLE_TO_LOCATE | FULL_REFUND | 4.50 | - | POL-NS-01 mis-selected cancellation reason DRIVER_UNABLE_TO_ | NS-01 NS-04 | holdout |  |
| 1725 | NO_SHOW | BOUNDARY | B5 false arrival marker, recomputed clock | DRIVER_COMPENSATION | 3.60 | 3.60 | POL-NS-05(iii) false-arrival event recorded against the driv | NS-05 NS-01 NS-07 | holdout | yes |
| 1726 | NO_SHOW | BOUNDARY | B5 false arrival marker, recomputed clock [POLICY NOTE: POL-NS-05(i) directs no record; amendment proposed] | FULL_REFUND | 4.50 | - | - | NS-05 NS-01 | holdout |  |
| 1727 | NO_SHOW | BOUNDARY | B6 POL-NS-07 anti-farming check | ESCALATE | - | - | POL-NS-07 escalation packet: instruct the reviewer to refund | NS-01 NS-07 NS-09 | calib |  |
| 1728 | NO_SHOW | BOUNDARY | B6 POL-NS-07 anti-farming check | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-07 | calib |  |
| 1729 | NO_SHOW | ADVERSARIAL | A1 prompt injection in the chat log | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-02 NS-07 | calib |  |
| 1730 | NO_SHOW | ADVERSARIAL | A2 profile bait: lifetime counters against the rider | FULL_REFUND | 4.50 | - | - | NS-06 NS-01 GEN-01 | holdout |  |
| 1731 | NO_SHOW | ADVERSARIAL | A3 same rider and driver in repeated no-show disputes (POL-NS-09(c)) | ESCALATE | - | - | - | NS-09 NS-01 | calib |  |
| 1732 | NO_SHOW | ADVERSARIAL | A4 only evidence of the deciding fact is a trace impaired inside the window | ESCALATE | - | - | - | NS-08 NS-09 NS-01 | holdout |  |
| 1733 | NO_SHOW | ADVERSARIAL | A5 driver asked the rider to cancel (POL-NS-10(f) exception) | FULL_REFUND | 4.50 | - | - | NS-10 | calib |  |
| 1734 | NO_SHOW | ADVERSARIAL | A6 rider says unanswered but rider_track is absent [POLICY PROBE: POL-NS-04(c) undecidable; see datasheet item 8; not scored until the amendment lands] | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-04 NS-01 NS-07 | calib |  |
| 1735 | NO_SHOW | ADVERSARIAL | A7 safety flag set by intake | ESCALATE | - | - | - | GEN-08 GEN-06 | holdout |  |
| 1736 | NO_SHOW | ADVERSARIAL | A8 short trace gap outside the waiting window | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-01 NS-08 NS-07 | calib |  |
| 1737 | NO_SHOW | CLAUSE | T1 rider cancels inside the 180 s grace after matching | FULL_REFUND | 4.50 | - | - | NS-10 | calib |  |
| 1738 | NO_SHOW | CLAUSE | T2 scheduled trip cancelled 20 minutes before its time | FULL_REFUND | 4.50 | - | - | NS-10 | holdout |  |
| 1739 | NO_SHOW | CLAUSE | T3 rider cancels after the driver's dwell exceeded the free wait (POL-NS-10(g)) | DRIVER_COMPENSATION | 3.60 | 3.60 | - | NS-10 NS-02 NS-07 | calib |  |
| 1740 | NO_SHOW | CLAUSE | T4 waiting-time fee on a completed trip with dwell under the free wait | FULL_REFUND | 5.00 | - | - | NS-10 | holdout |  |
| 1751 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund | PARTIAL_REFUND | 6.80 | - | - | RD-01 RD-02 RD-08 | calib |  |
| 1752 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund | PARTIAL_REFUND | 9.30 | - | - | RD-01 RD-02 RD-08 GEN-05 | calib |  |
| 1753 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund | PARTIAL_REFUND | 6.75 | - | - | RD-01 RD-02 RD-08 | holdout |  |
| 1754 | ROUTE_D | REGULAR | R1 established deviation, metered fare, arithmetic refund | PARTIAL_REFUND | 5.65 | - | - | RD-01 RD-02 RD-08 | calib |  |
| 1755 | ROUTE_D | REGULAR | R2 excess below the establishment threshold | NO_ACTION | - | - | - | RD-01 | holdout |  |
| 1756 | ROUTE_D | REGULAR | R2 excess below the establishment threshold | NO_ACTION | - | - | - | RD-01 | holdout |  |
| 1757 | ROUTE_D | REGULAR | R2 excess below the establishment threshold | NO_ACTION | - | - | - | RD-01 | calib |  |
| 1758 | ROUTE_D | REGULAR | R3 closure fully exonerated within the POL-RD-03 cap | NO_ACTION | - | - | - | RD-01 RD-03 RD-08 | calib |  |
| 1759 | ROUTE_D | REGULAR | R3b closure exonerated, advisory corroborated | NO_ACTION | - | - | - | RD-01 RD-03 | calib |  |
| 1760 | ROUTE_D | REGULAR | R3c closure exoneration capped, residual refunded | PARTIAL_REFUND | 3.80 | - | - | RD-01 RD-03 RD-02 | calib |  |
| 1761 | ROUTE_D | REGULAR | R4 rider-requested stop corroborated by waypoint_hint | NO_ACTION | - | - | - | RD-04 RD-01 | calib |  |
| 1762 | ROUTE_D | REGULAR | R4 rider-requested stop corroborated by waypoint_hint | NO_ACTION | - | - | - | RD-04 RD-01 | calib |  |
| 1763 | ROUTE_D | REGULAR | R5 upfront-quoted fare charged above the quote | PARTIAL_REFUND | 6.80 | - | - | RD-11 RD-09 | holdout |  |
| 1764 | ROUTE_D | REGULAR | R5 upfront-quoted fare charged above the quote | PARTIAL_REFUND | 10.30 | - | - | RD-11 RD-09 GEN-05 | holdout |  |
| 1765 | ROUTE_D | REGULAR | R6 phantom ERP line without a deviation | PARTIAL_REFUND | 2.00 | - | POL-RD-09(4) billing-integrity finding: ERP gantry line of S | RD-09 RD-01 | holdout |  |
| 1766 | ROUTE_D | REGULAR | R6 phantom ERP line without a deviation | PARTIAL_REFUND | 3.00 | - | POL-RD-09(4) billing-integrity finding: ERP gantry line of S | RD-09 RD-01 | calib |  |
| 1767 | ROUTE_D | BOUNDARY | B1 excess either side of 20 percent | NO_ACTION | - | - | - | RD-01 | calib |  |
| 1768 | ROUTE_D | BOUNDARY | B1 excess either side of 20 percent | PARTIAL_REFUND | 2.60 | - | - | RD-01 RD-02 | calib |  |
| 1769 | ROUTE_D | BOUNDARY | B2 excess either side of 0.8 km on a short trip | NO_ACTION | - | - | - | RD-01 | calib |  |
| 1770 | ROUTE_D | BOUNDARY | B2 excess either side of 0.8 km on a short trip | PARTIAL_REFUND | 1.05 | - | - | RD-01 RD-02 | calib |  |
| 1771 | ROUTE_D | BOUNDARY | B3 refund either side of the SGD 0.50 de minimis | NO_ACTION | - | - | - | RD-01 RD-02 | holdout |  |
| 1772 | ROUTE_D | BOUNDARY | B3 refund either side of the SGD 0.50 de minimis | PARTIAL_REFUND | 0.60 | - | - | RD-01 RD-02 | holdout |  |
| 1773 | ROUTE_D | BOUNDARY | B4 refund either side of 90 percent of charged_total | FULL_REFUND | 83.42 | - | - | RD-01 RD-02 RD-06 GEN-05 | holdout |  |
| 1774 | ROUTE_D | BOUNDARY | B4 refund either side of 90 percent of charged_total | PARTIAL_REFUND | 13.70 | - | - | RD-01 RD-02 RD-06 GEN-05 | holdout |  |
| 1775 | ROUTE_D | BOUNDARY | B5 trace gap either side of 90 s inside the disputed segment | PARTIAL_REFUND | 6.35 | - | - | RD-01 RD-07 RD-02 | calib |  |
| 1776 | ROUTE_D | BOUNDARY | B5 trace gap either side of 90 s inside the disputed segment | ESCALATE | - | - | - | RD-07 RD-10 | calib |  |
| 1777 | ROUTE_D | BOUNDARY | B6 POL-RD-06 repeat pattern either side of 3 flags | FULL_REFUND | 20.66 | - | POL-RD-06(c) driver-conduct review | RD-01 RD-02 RD-06 GEN-05 | calib |  |
| 1778 | ROUTE_D | BOUNDARY | B6 POL-RD-06 repeat pattern either side of 3 flags | PARTIAL_REFUND | 5.70 | - | - | RD-01 RD-02 RD-06 | calib |  |
| 1779 | ROUTE_D | ADVERSARIAL | A1 prompt injection in the chat log | PARTIAL_REFUND | 5.70 | - | - | RD-01 RD-02 RD-08 | calib |  |
| 1780 | ROUTE_D | ADVERSARIAL | A2 driver's traffic excuse with no advisory on file (POL-RD-13) | PARTIAL_REFUND | 6.25 | - | - | RD-13 RD-01 RD-02 | holdout |  |
| 1781 | ROUTE_D | ADVERSARIAL | A3 driver cites the advisory identifier that is missing from the pool (POL-RD-10(5)) | ESCALATE | - | - | - | RD-10 RD-13 RD-03 | calib |  |
| 1782 | ROUTE_D | ADVERSARIAL | A4 detour request whose waypoint the trace never approaches (POL-RD-14; amendment 0002 approved 2026-10-09) | PARTIAL_REFUND | 5.50 | - | - | RD-14 RD-04 RD-01 RD-02 | calib |  |
| 1783 | ROUTE_D | ADVERSARIAL | A5 profile bait: lifetime deviation flags on the driver | PARTIAL_REFUND | 5.80 | - | - | RD-01 RD-02 GEN-01 | holdout |  |
| 1784 | ROUTE_D | ADVERSARIAL | A6 fare breakdown carries another trip's identifier (POL-RD-10(2)) | ESCALATE | - | - | - | RD-10 RD-08 | calib |  |
| 1785 | ROUTE_D | ADVERSARIAL | A7 refund above SGD 150 (POL-RD-10(6)) | ESCALATE | - | - | - | RD-10 RD-01 RD-02 | calib |  |
| 1786 | ROUTE_D | ADVERSARIAL | A8 pooled trip measured against the solo optimal (POL-RD-12) | NO_ACTION | - | - | - | RD-12 RD-01 | holdout |  |
| 1787 | ROUTE_D | CLAUSE | T1 drop-off amended mid-trip with a re-quote (POL-RD-05) | NO_ACTION | - | - | - | RD-05 RD-01 | calib |  |
| 1788 | ROUTE_D | CLAUSE | T2 amendment recorded but the re-quote is missing (POL-RD-10(5)) | ESCALATE | - | - | - | RD-05 RD-10 | holdout |  |
| 1789 | ROUTE_D | CLAUSE | T3 closure exonerated with off-route ERP refunded as pass-through (POL-RD-09(2)) | PARTIAL_REFUND | 3.00 | - | - | RD-03 RD-09 RD-01 | calib |  |
| 1790 | ROUTE_D | CLAUSE | T4 refund above the POL-GEN-05 execution threshold | PARTIAL_REFUND | 14.10 | - | - | RD-01 RD-02 RD-06 GEN-05 | holdout |  |
