Draft verification on recorded drafts — deepseek/deepseek-flash

  source        runs/codex/deepseek-deepseek-flash
  source commit b25b74333dc63761de107a4c43de5d215dd329f9
  results       /Users/hanweizhou/Desktop/Tribunal/runs/codex/verify-recorded-drafts/deepseek-deepseek-flash
  prompts       5b8510cd900aa9da

Per case — three readings of the vote, on the same drafts and the same
verdicts: without the verifier, abstaining on any contradiction, and
abstaining on material contradictions only (what the pipeline does).

  case 9101
    without the verifier:              carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on any contradiction:   carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on material only:       carried (agreement 1.0, DRIVER_COMPENSATION)
    contradicted: none
  case 9102
    without the verifier:              carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, DRIVER_COMPENSATION)
    abstaining on material only:       carried_not_unanimous (agreement 0.75, DRIVER_COMPENSATION)
    abstained on a material contradiction: draft(s) 2
    contradicted (draft 2, material): "The SGD 6.00 cancellation fee stands, and the driver is owed SGD 4.80 in compensation, which the platform pays." [POL-NS-07 / EV-FARE-09102 derived.money (fee_charged 6.00, driver_compensation 4.80)]
      the brief holds: "the driver's compensation is 80% of the cancellation fee charged to the rider, the residual 20% being retained as the platform service fee (fee-funded); a platform-funded payment is the POL-NS-03(ii) goodwill, which is charged to the platform"
  case 9103
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 9104
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, FULL_REFUND)
    abstaining on material only:       carried_not_unanimous (agreement 0.75, FULL_REFUND)
    abstained on a material contradiction: draft(s) 4
    contradicted (draft 4, not material): "No other POL-NS-09 trigger fires: confidence is above the 0.70 floor; no artifact carrying the deciding fact is impaired under POL-NS-08(a)–(d) (20-second marker/fix skew, no trace gap, 37 fixes, chat count matching trip_record.chat_message_count, fee reconciling at SGD 4.00 under the resolution rule); rider_profile.no_show_disputes_30d is 0 and both counterparty-dispute counters are 0; and the POL-NS-07 anti-farming check does not trip (no_show_terminations_30d 1 is below 4, and 1/120 = 0.008 is below 0.08)." [EV-GPS-09104 (first_fix_at 07:25:00, sample_interval_sec 10.0, arrived_at 07:25:20)]
      the brief holds: "0 seconds — the arrived timestamp 07:25:20 coincides with a GPS fix at 10 s cadence"
    contradicted (draft 4, material): "The driver's claims that SGD 4.00 is the correct amount (STANDARD zone-class fee SGD 4.00, RYDE_X vehicle-tier fee SGD 4.00, GREATER taken, no POL-NS-08(d) fare defect), that limbs (a) and (d) hold, that POL-NS-04 cannot run (no rider message in EV-CHAT-09104 and rider_qualifying_fix_count 0 at 519.46 m), and the driver's express concession that the fee is not chargeable on the GPS record are accepted; the first four do not change the outcome and the concession corroborates it." [counterparty_statement]
      the brief holds: "I marked arrival and waited before cancelling."
  case 9105
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 9106
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted (draft 3, not material): "Every artifact was admitted COMPLETE at weight 1.0, so the confidence cap is 1.0; no POL-NS-08 limb is engaged (clock skew is 20 seconds, there are no trace gaps and 34 driver fixes, the chat log's 3 messages match trip_record.chat_message_count, and the fee line reconciles); and no POL-NS-09 trigger fires - the anti-farming check reads driver_profile.no_show_terminations_30d of 1 (below 4) against 120 completed trips in the window, both parties' disputes_with_counterparty_90d are 0, and rider_profile.no_show_disputes_30d is 0." [EV-GPS-09106]
      the brief holds: "no clock skew (0 s) — the arrived event at 18:20:20 coincides with a GPS fix; the 20 s figure is the dwell start offset from the first in-geofence fix (dwell_start_offset_sec 20.0), not a clock skew"
  case 9107
    without the verifier:              carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on any contradiction:   no_valid_drafts (agreement None, no ruling)
    abstaining on material only:       carried (agreement 1.0, DRIVER_COMPENSATION)
    contradicted (draft 1, not material): "Both conditions hold: EV-ADVIS-09107-01 is a CLOSURE, present and populated, its geometry covers the pickup road and its active window (18:50–19:30) covers the wait; and the driver's furthest point between the intervals was 179.76 m, inside the 300 m leash." [EV-GPS-09107 payload.derived.arrival.max_excursion_m]
      the brief holds: "179.75579586275526 m"
    contradicted (draft 1, not material): "The trace is a 170-second hold (19:00:00–19:02:50), a 60-second circulation taken to 179.76 m, and a 160-second hold (19:03:50–19:06:30): 330 seconds in total, 30 seconds above the 300-second minimum." [EV-GPS-09107 payload.derived.arrival.max_excursion_m]
      the brief holds: "179.75579586275526 m"
    contradicted (draft 1, not material): "The rider-track figure of 519.37 m and the absence of any rider chat message do not assist either party here, because POL-NS-06 directs the dwell question to be decided independently of rider presence." [EV-GPS-09107 payload.derived.rider_presence.max_distance_m]
      the brief holds: "519.3686322020327 m"
    contradicted (draft 2, not material): "The trace shows two in-geofence holds — 170 seconds (19:00:00–19:02:50) and 160 seconds (19:03:50–19:06:30) — split by a 60-second circulation in which the driver never went further than 179.76 m from the pin, inside the 300 m leash." [EV-GPS-09107 payload.derived.arrival.max_excursion_m]
      the brief holds: "179.75579586275526 m"
    contradicted (draft 3, not material): "You are right about the underlying facts: the driver left the marked bay from 19:02:50 to 19:03:50, reaching 179.8 m from the pin, so his two holds inside the geofence were separate — 170 seconds (19:00:00 to 19:02:50) and 160 seconds (19:03:50 to 19:06:30) — and the longest single hold is far short of the 300-second minimum for this LARGE_VENUE pickup." [EV-GPS-09107 payload.derived.arrival.max_excursion_m]
      the brief holds: "179.75579586275526 m"
    contradicted (draft 3, not material): "The driver's furthest point during the 60-second circulation was 179.8 m, inside the 300 m leash, and LTA advisory EV-ADVIS-09107-01 is a CLOSURE covering the Orchard Central pickup road, active 18:50–19:30, which covers the whole waiting period." [EV-GPS-09107 payload.derived.arrival.max_excursion_m]
      the brief holds: "179.75579586275526 m"
    contradicted (draft 3, not material): "Your own position does not rescue the argument either: your device fixes sit 519 m from the pin (outside the 150 m rider-presence radius), but POL-NS-06 decides the fee 'whether or not the rider was present and whether or not the rider responded to messages', and POL-NS-04 cannot apply at all because no message in the chat log was sent by you." [EV-GPS-09107 payload.derived.rider_presence.max_distance_m]
      the brief holds: "519.3686322020327 m"
    contradicted (draft 4, not material): "You are right, rider, that the driver's longest unbroken in-geofence hold was only 170 seconds and that he then left the arrival radius for 60 seconds (19:02:50 to 19:03:50), reaching 179.8 m from the pin, exactly as his own 19:02:30 message said." [EV-GPS-09107 payload.derived.arrival.max_excursion_m]
      the brief holds: "179.75579586275526 m"
    contradicted (draft 4, not material): "But POL-NS-06(i) allows those two in-geofence intervals to be summed: the LTA advisory EV-ADVIS-09107-01 is present and populated with type CLOSURE, its geometry covers the pickup road and its active window 18:50 to 19:30 covers the waiting period, so holding position was not lawfully possible, and the driver's furthest point, 179.8 m, is well inside the 300 m leash." [EV-GPS-09107 payload.derived.arrival.max_excursion_m]
      the brief holds: "179.75579586275526 m"
    contradicted (draft 4, not material): "Rider presence does not change this arithmetic: POL-NS-06 decides the fee whether or not the rider was at the pin or replied, so the rider-track evidence (519.4 m from the pin) and the rider's silence are not grounds against the fee." [EV-GPS-09107 payload.derived.rider_presence.max_distance_m]
      the brief holds: "519.3686322020327 m"
  case 9108
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   no_valid_drafts (agreement None, no ruling)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted (draft 1, not material): "(b) The GPS trace places the driver 24.0 m from the pickup pin, well inside the 120 m LARGE_VENUE arrival radius, from the first fix at 09:30:00 — before the arrived event." [EV-GPS-09108.derived.driver_track.max_distance_m]
      the brief holds: "24.01175553061849 m"
    contradicted (draft 1, not material): "POL-NS-03 is about a driver stationary outside the arrival radius but within 400 m; here the driver was inside the radius at 24.0 m, so the wrong-entrance route is not engaged." [EV-GPS-09108.derived.driver_track.max_distance_m]
      the brief holds: "24.01175553061849 m"
    contradicted (draft 1, not material): "POL-NS-04 cannot exonerate the rider: limb (a) fails because the chat log holds only the SYSTEM arrival notice and the driver's own 'Waiting at PLQ 3 pickup bay', nothing locating or coordinating from the rider, and limb (c) fails affirmatively — the rider track's 16 fixes sit at a mean 519 m from the pin, outside the 150 m LARGE_VENUE presence radius, with 0 qualifying fixes." [EV-GPS-09108.derived.rider_presence.mean_distance_m]
      the brief holds: "519.3653788844131 m"
    contradicted (draft 1, not material): "POL-NS-05 does not bite: at the arrived timestamp the driver was 24.0 m from the pin (not over 300 m) and the trace records a single distinct speed of 0.0 km/h (not 15 km/h or more), so the arrival marker is genuine." [EV-GPS-09108.derived.driver_track.max_distance_m]
      the brief holds: "24.01175553061849 m"
    contradicted (draft 2, not material): "The arrival marker was genuine (24 m from the pin at 0 km/h, so POL-NS-05 does not bite), and because the driver was inside the arrival radius, POL-NS-03's wrong-entrance route does not apply." [EV-GPS-09108.derived.driver_track.max_distance_m]
      the brief holds: "24.01175553061849 m"
    contradicted (draft 3, not material): "(b) The GPS trace places the driver 24.0 m from the pickup pin — well inside the 120 m LARGE_VENUE arrival radius — from the first fix at 09:30:00, i.e." [EV-GPS-09108.derived.driver_track.max_distance_m]
      the brief holds: "24.01175553061849 m"
    contradicted (draft 3, not material): "POL-NS-05 does not bite: at the arrival timestamp the driver was 24.0 m from the pin and the trace records a single distinct speed of 0.0 km/h, so the marker is genuine and the waiting clock is not recomputed." [EV-GPS-09108.derived.driver_track.max_distance_m]
      the brief holds: "24.01175553061849 m"
    contradicted (draft 3, not material): "POL-NS-04 does not exonerate you: the chat log holds only two messages — the SYSTEM arrival notice and the driver's own 'Waiting at PLQ 3 pickup bay' — so you sent nothing locating or coordinating (limb (a) fails), and your rider track holds 16 fixes at a mean 519 m from the pin with 0 qualifying fixes inside the 150 m rider-presence radius (limb (c) fails affirmatively)." [EV-GPS-09108.derived.rider_presence.mean_distance_m]
      the brief holds: "519.3653788844131 m"
    contradicted (draft 4, not material): "The GPS trace (EV-GPS-09108) places the driver's vehicle 24.0 m from the PLQ 3 pickup pin for one continuous hold of 330 seconds (09:30:00 to 09:35:30), inside the 120 m arrival radius for this LARGE_VENUE pickup, at a recorded speed of 0.0 km/h." [EV-GPS-09108.derived.driver_track.max_distance_m]
      the brief holds: "24.01175553061849 m"
    contradicted (draft 4, not material): "That satisfies all four limbs of POL-NS-01, and no clause in POL-NS-03 to POL-NS-06 displaces the fee: the driver was inside the arrival radius rather than at a wrong entrance (POL-NS-03); the arrival marker was genuine, not a false early tap (POL-NS-05); the 330-second hold exceeds the 300-second LARGE_VENUE minimum, so there is no waiting-period shortfall (POL-NS-06); and the rider sent no locating or coordinating message and her device sat 519 m from the pin, so POL-NS-04 does not apply." [EV-GPS-09108.derived.rider_presence.mean_distance_m]
      the brief holds: "519.3653788844131 m"
  case 9109
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   escalated (agreement 0.5, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted (draft 1, not material): "Equally, the driver's request for SGD 4.80 compensation under POL-NS-07 is refused because that clause pays only where POL-NS-01 is satisfied in full, which it is not; the anti-farming check (no_show_terminations_30d of 1, and 1 ÷ 120 = 0.008) is not the reason it fails." [driver_profile.no_show_terminations_30d / driver_profile.completed_trips_30d]
      the brief holds: "1 ÷ 120 = 0.00833 (not 0.008)"
    contradicted (draft 3, not material): "No referral is produced: the POL-NS-07 anti-farming check does not trip (no_show_terminations_30d 1 is below 4, and 1 ÷ completed_trips_30d 120 = 0.008 is below 0.08), so no compensation is ordered and no escalation instruction is directed into the packet; POL-NS-05(ii) is unavailable because the false-arrival test cannot be run; and no POL-NS-09(c) or (d) profile trigger fires (both disputes_with_counterparty_90d are 0; no_show_disputes_30d is 0)." [driver_profile.no_show_terminations_30d / driver_profile.completed_trips_30d]
      the brief holds: "1 ÷ 120 = 0.00833 (not 0.008)"
  case 9110
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   carried (agreement 1.0, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted: none
  case 9111
    without the verifier:              carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on any contradiction:   escalated (agreement 0.5, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, PARTIAL_REFUND)
    contradicted (draft 3, not material): "POL-RD-04 is unavailable: the chat log holds two messages, neither with a waypoint_hint and neither naming a road or place, and the rider's own message asked the driver to return to the booked route — so there was no rider-requested detour." [EV-CHAT-09111]
      the brief holds: "the rider's 08:12 message names "Pioneer Road""
    contradicted (draft 4, not material): "No excuse applies: the only traffic advisory is missing from the bundle so no closure can be shown; the chat log contains no rider detour instruction (the rider's 08:12 message asked the driver to return to the booked route, and neither message carries a waypoint or names a road, so POL-RD-04 cannot be run); no endpoint was amended (POL-RD-05); the trip is not pooled (POL-RD-12); and the fare is metered, not upfront (POL-RD-11)." [EV-CHAT-09111]
      the brief holds: "the rider's 08:12 message names "Pioneer Road""
  case 9112
    without the verifier:              carried (agreement 1.0, NO_ACTION)
    abstaining on any contradiction:   carried (agreement 1.0, NO_ACTION)
    abstaining on material only:       carried (agreement 1.0, NO_ACTION)
    contradicted: none
  case 9113
    without the verifier:              carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstaining on material only:       carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstained on a material contradiction: draft(s) 2
    contradicted (draft 2, material): "That is above the 0.50 de-minimis floor and is 25.5% of charged_total, far below the 90% full-refund threshold, so the outcome is a PARTIAL_REFUND of 8.05 to the rider." [derived.money.closure.refund (8.05) plus POL-RD-09(4) 1.00]
      the brief holds: "total refund 9.05 (POL-RD-02 refund 8.05 + POL-RD-09(4) correction 1.00), not 8.05"
    contradicted (draft 2, material): "Under POL-RD-09(1) it must not be added on top; the rider's recovery is 8.05, not 10.85." [derived.money.closure.refund (8.05) plus POL-RD-09(4) 1.00]
      the brief holds: "the rider's recovery is 9.05, not 8.05"
    contradicted (draft 2, material): "Both gantries were actually crossed (nearest fixes 834 m and 223 m), so no billing-integrity defect and no POL-RD-09(4) referral." [EV-GPS-09113 derived.erp_gantry_proximity 'Pelton lawful diversion entry' nearest_fix 834.18 m; POL-RD-09 250 m radius]
      the brief holds: "the Pelton line is 834.18 m from the nearest fix, outside the 250 m match radius, so it is not crossed and is a POL-RD-09(4) billing-integrity failure"
    contradicted (draft 2, material): "No POL-RD-10 trigger fires: the trip identifiers match across all three artifacts, the timestamps agree, the trace is unimpaired, the advisory is present and covers the window, every charge line is matched, and the refund is below both the 150.00 ceiling and charged_total." [EV-GPS-09113 derived.erp_gantry_proximity nearest_fix 834.18 m]
      the brief holds: "the 'Pelton lawful diversion entry' charge line is unmatched (nearest fix 834.18 m, outside the 250 m radius)"
    contradicted (draft 2, material): "Ruling: PARTIAL_REFUND of 8.05 to the rider; no driver compensation; no referrals." [derived.money.closure.refund plus POL-RD-09(4); POL-RD-09(4) billing-integrity referral]
      the brief holds: "PARTIAL_REFUND of 9.05 and a POL-RD-09(4) billing-integrity referral"
  case 9114
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   no_valid_drafts (agreement None, no ruling)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted (draft 1, not material): "Its derived ERP proximity check places the vehicle's nearest fix 7,482.07 m from that gantry's coordinates." [EV-GPS-09114 derived.erp_gantry_proximity.lines[0].nearest_fix.distance_m]
      the brief holds: "7482.065855290174 m"
    contradicted (draft 1, not material): "POL-RD-09 treats a gantry as crossed only where a fix comes within 250 m; 7,482 m is about thirty times that radius, and the derived block reports gap_brackets_closest_approach false with no bracketing gaps." [EV-GPS-09114 derived.erp_gantry_proximity.lines[0].nearest_fix.distance_m]
      the brief holds: "7482.065855290174 m"
    contradicted (draft 2, not material): "The GPS trace (EV-GPS-09114) is complete and unimpaired — 169 fixes at a 10-second interval, 100% coverage, no gaps, maximum gap 0.0 s — and the platform's own proximity check puts the nearest fix 7,482.07 m from that gantry, roughly thirty times outside the 250 m crossing radius POL-RD-09 applies." [EV-GPS-09114 derived.erp_gantry_proximity.lines[0].nearest_fix.distance_m]
      the brief holds: "7482.065855290174 m"
    contradicted (draft 3, not material): "The platform's own derived check against the GPS trace places the vehicle's nearest fix 7,482 m from the gantry coordinates — about thirty times the 250 m radius used to match a gantry to a trace — and reports no bracketing gaps and a false gap-bracketed closest approach, so the car does not cross it on any reading." [EV-GPS-09114 derived.erp_gantry_proximity.lines[0].nearest_fix.distance_m]
      the brief holds: "7482.065855290174 m"
    contradicted (draft 4, not material): "POL-RD-09 matches a gantry to the trace by treating any fix within 250 m as a crossing; the derived check puts the nearest of the trace's 169 fixes 7,482.07 m from the gantry coordinates, with no bracketing gaps and gap_brackets_closest_approach false." [EV-GPS-09114 derived.erp_gantry_proximity.lines[0].nearest_fix.distance_m]
      the brief holds: "7482.065855290174 m"
  case 9115
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   carried (agreement 1.0, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted: none

  15 case(s) verified, 0 refused, 38 contradicted statement(s) (7 material, 31 not), 752852 verifier token(s).
  the verifier moved the vote on: 9102, 9104
  abstaining on any contradiction would have moved: 9102, 9104, 9106, 9107, 9108, 9109, 9111, 9114
  materiality alone keeps the vote on: 9106, 9107, 9108, 9109, 9111, 9114

All three readings are of the source run's own drafts and of one set of verdicts, so a difference between them is the rule and not a second sampling of the judge.