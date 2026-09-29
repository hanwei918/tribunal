Draft verification on recorded drafts — deepseek/deepseek-flash

  source        runs/deepseek-deepseek-flash
  source commit b25b74333dc63761de107a4c43de5d215dd329f9
  results       /Users/hanweizhou/Desktop/Tribunal/runs/verify-recorded-drafts/deepseek-deepseek-flash
  prompts       5b8510cd900aa9da

Per case — three readings of the vote, on the same drafts and the same
verdicts: without the verifier, abstaining on any contradiction, and
abstaining on material contradictions only (what the pipeline does).

  case 101
    without the verifier:              carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on any contradiction:   escalated (agreement 0.5, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, PARTIAL_REFUND)
    contradicted (draft 2, not material): "That is above the 0.50 de minimis and 22.6% of the charge, far below the 90% full-refund share, so the outcome is PARTIAL_REFUND." [EV-FARE-00101 (derived.money.refund.refund_share_of_charged 0.2247474)]
      the brief holds: "refund_share_of_charged = 0.2247 (~22.5% of charged)"
    contradicted (draft 3, not material): "That is 22.6% of the charge, below the 90% full-refund share and above the 0.50 de minimis, so the outcome is a partial refund." [EV-FARE-00101 (derived.money.refund.refund_share_of_charged 0.2247474)]
      the brief holds: "refund_share_of_charged = 0.2247 (~22.5% of charged)"
  case 102
    without the verifier:              carried (agreement 1.0, NO_ACTION)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, NO_ACTION)
    abstaining on material only:       carried_not_unanimous (agreement 0.75, NO_ACTION)
    abstained on a material contradiction: draft(s) 2
    contradicted (draft 2, material): "On the money: the fare reconciles to the cent — $3.80 base + $15.30 distance + $7.56 time + $0.80 platform fee = $29.91, with surge 1.0 read from fare_breakdown.surge_multiplier." [EV-FARE-00102]
      the brief holds: "distance_fare 16.35 + time_fare 8.96 + base_fare 3.80 + platform_fee 0.80 = 29.91; the 15.30 and 7.56 figures are the derived optimal-route components (recomputed_fare 27.46), not the charged reconciliation"
  case 103
    without the verifier:              carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on material only:       carried (agreement 1.0, PARTIAL_REFUND)
    contradicted: none
  case 104
    without the verifier:              carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on material only:       carried (agreement 1.0, PARTIAL_REFUND)
    contradicted: none
  case 105
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 106
    without the verifier:              carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstaining on material only:       carried (agreement 1.0, PARTIAL_REFUND)
    contradicted (draft 2, not material): "That is 41.3% of the charge, below the 90% full-refund share, so the outcome is PARTIAL_REFUND and the rider's demand for the full 26.04 is not reached." [EV-FARE-00106 derived.money.refund.refund_share_of_charged]
      the brief holds: "0.4116743471582181259600614439 (41.2%, not 41.3%)"
  case 107
    without the verifier:              carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstaining on material only:       carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstained on a material contradiction: draft(s) 2
    contradicted (draft 2, material): "POL-GEN-02(2) caps my confidence at the weight of the artifacts that actually carry the deciding fact, and here that fact — the excess distance — is measured from the trace alone, at 0.30." [POL-GEN-02(2)]
      the brief holds: "the deciding route fact is also carried independently by EV-CHAT-00107 at weight 1.00, so the cap is the maximum of the independent carriers (1.00), not the trace's 0.30"
    contradicted (draft 2, material): "The cap is therefore 0.30, below the platform-wide floor of 0.70." [POL-GEN-02(2)]
      the brief holds: "cap 1.00 (independent carrier EV-CHAT-00107, weight 1.00), which is above the 0.70 platform floor"
    contradicted (draft 2, material): "POL-RD-10(1) makes the outcome ESCALATE." [POL-RD-10(1)]
      the brief holds: "no POL-RD-10(1) trigger fires; the outcome is a POL-RD-02 PARTIAL_REFUND of SGD 7.45"
  case 108
    without the verifier:              carried (agreement 1.0, NO_ACTION)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, NO_ACTION)
    abstaining on material only:       carried_not_unanimous (agreement 0.75, NO_ACTION)
    abstained on a material contradiction: draft(s) 1
    contradicted (draft 1, material): "(3) The rider's account of roughly five minutes circling at T3 is the kind of distance POL-RD-05 also excludes from excess, and it points the same way, but it is not needed because the excess is already below both gates." [EV-GPS-00108 (derived.deviation.thresholds.threshold_km 0.8); POL-RD-01]
      the brief holds: "the 1.57 km excess is above the 0.8 km absolute gate — only the 20% percentage gate fails"
  case 109
    without the verifier:              carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, DRIVER_COMPENSATION)
    abstaining on material only:       carried (agreement 1.0, DRIVER_COMPENSATION)
    contradicted (draft 3, not material): "need to grab something 5 min' at 18:22:06, about a minute after the trip began, and the driver agreed thirteen seconds later." [EV-CHAT-00109 MSG-00109-001 sent_at 18:22:06 and MSG-00109-002 sent_at 18:22:31]
      the brief holds: "the driver's reply MSG-00109-002 was sent 25 seconds after the rider's message, not thirteen seconds"
  case 110
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   escalated (agreement 0.25, ESCALATE)
    abstaining on material only:       escalated (agreement 0.25, ESCALATE)
    abstained on a material contradiction: draft(s) 1, 2, 3
    contradicted (draft 1, material): "No refund is issued and no charge is confirmed while that review is pending; the disputed $34.42 is held rather than collected or refunded." [case.dispute.amount_contested_sgd]
      the brief holds: "SGD 10.00 (the disputed/contested amount; the SGD 34.42 is the total charged, EV-FARE-00110 total_charged)"
    contradicted (draft 2, material): "The disputed $34.42 is held, not collected and not refunded, and a human reviewer will look at the case." [case.dispute.amount_contested_sgd]
      the brief holds: "SGD 10.00 (the disputed amount; SGD 34.42 is the total charged)"
    contradicted (draft 3, material): "Both parties: this case turns on one stretch of road the evidence cannot see, so it goes to a human reviewer and the disputed $34.42 is held rather than collected or refunded." [case.dispute.amount_contested_sgd]
      the brief holds: "SGD 10.00 (the disputed amount held; SGD 34.42 is the total charged)"
  case 111
    without the verifier:              carried (agreement 1.0, NO_ACTION)
    abstaining on any contradiction:   carried (agreement 1.0, NO_ACTION)
    abstaining on material only:       carried (agreement 1.0, NO_ACTION)
    contradicted: none
  case 112
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted (draft 4, not material): "The interpretation also decides the driver's unbilled-distance claim: on the whole-trace reading the fare bills 20.00 km against 22.40 km (a 2.40 km shortfall worth 2.40 x 0.75 = SGD 1.80); on the recorded-window reading there is no shortfall at all." [EV-GPS-00112 (admissibility issue detail: 20.02 km driven vs EV-FARE-00112 distance_charged_km 20.00)]
      the brief holds: "on the recorded-window reading there is a 0.02 km shortfall (20.02 km driven against 20.00 km billed), below the 1.0 km POL-RD-04 threshold"
  case 113
    without the verifier:              carried (agreement 1.0, NO_ACTION)
    abstaining on any contradiction:   carried (agreement 1.0, NO_ACTION)
    abstaining on material only:       carried (agreement 1.0, NO_ACTION)
    contradicted: none
  case 114
    without the verifier:              carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on material only:       carried (agreement 1.0, PARTIAL_REFUND)
    contradicted: none
  case 115
    without the verifier:              carried (agreement 1.0, PARTIAL_REFUND)
    abstaining on any contradiction:   escalated (agreement 0.5, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, PARTIAL_REFUND)
    contradicted (draft 1, not material): "The other does not: 'AYE (Alexandra Rd towards Tuas)' at $2.00, not on the optimal route, and the closest the trace ever comes to that gantry is 5,419 m — sixteen times the match radius." [EV-GPS-00115 erp_gantry_proximity AYE (nearest_fix distance_m 5419.288856295679)]
      the brief holds: "nearest fix is 5,419.29 m, about 21.7 times the 250 m match radius — not sixteen"
    contradicted (draft 2, not material): "The AYE (Alexandra Rd towards Tuas) charge of $2.00 does not stand: the gantry is not on the optimal route and the closest the trace ever came to it was 5,419 m, roughly sixteen times the match radius, so the vehicle never crossed it." [EV-GPS-00115 erp_gantry_proximity AYE (nearest_fix distance_m 5419.288856295679)]
      the brief holds: "nearest fix is 5,419.29 m, about 21.7 times the 250 m match radius — not 'roughly sixteen'"
  case 201
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 202
    without the verifier:              carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on any contradiction:   carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on material only:       carried (agreement 1.0, DRIVER_COMPENSATION)
    contradicted: none
  case 203
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    verification not usable: the verifier did not return a JSON object
    contradicted: none
  case 204
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 205
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 206
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 207
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   carried (agreement 1.0, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted: none
  case 208
    without the verifier:              carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, DRIVER_COMPENSATION)
    abstaining on material only:       carried (agreement 1.0, DRIVER_COMPENSATION)
    contradicted (draft 2, not material): "No escalation ground is available: no admissible artifacts contradict one another (POL-NS-09(b)); disputes_with_counterparty_90d is 0 on both profiles (POL-NS-09(c)); the anti-farming check does not trip (POL-NS-09(d)); and no deciding artifact is impaired under POL-NS-08 (clock skew is 15 seconds, well under 90; the trace has no gap; the chat has all 6 messages the trip record counts; the fare reconciles), so POL-NS-09(e) is not engaged either." [EV-TRIP-00208 arrived_at 2026-07-30T16:02:25; EV-GPS-00208 10 s fix cadence (derived.arrival.longest_qualifying_run first_ts 16:02:10)]
      the brief holds: "the arrived marker's nearest GPS fix is about 5 seconds away on the 10-second cadence (and termination agrees exactly: cancelled_at 16:12:10 = last_fix_at 16:12:10), not 15 seconds"
  case 209
    without the verifier:              carried (agreement 1.0, NO_ACTION)
    abstaining on any contradiction:   carried (agreement 1.0, NO_ACTION)
    abstaining on material only:       carried (agreement 1.0, NO_ACTION)
    contradicted: none
  case 210
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   carried (agreement 1.0, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted: none
  case 211
    without the verifier:              carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstaining on any contradiction:   carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    abstaining on material only:       carried_not_unanimous (agreement 0.75, PARTIAL_REFUND)
    verification not usable: the verifier did not return a JSON object
    contradicted: none
  case 212
    without the verifier:              carried (agreement 1.0, FULL_REFUND)
    abstaining on any contradiction:   carried (agreement 1.0, FULL_REFUND)
    abstaining on material only:       carried (agreement 1.0, FULL_REFUND)
    contradicted: none
  case 213
    without the verifier:              carried (agreement 1.0, ESCALATE)
    abstaining on any contradiction:   carried (agreement 1.0, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, ESCALATE)
    contradicted: none
  case 214
    without the verifier:              carried (agreement 1.0, DRIVER_COMPENSATION)
    abstaining on any contradiction:   escalated (agreement 0.5, ESCALATE)
    abstaining on material only:       carried (agreement 1.0, DRIVER_COMPENSATION)
    contradicted (draft 1, not material): "That is within one sampling interval, and it is not a false arrival - the driver was not more than 300 m away and not travelling at 15 km/h or more." [EV-GPS-00214.sample_interval_sec 10.0 with EV-TRIP-00214.arrived_at 18:44:30 and first in-geofence fix 18:44:45]
      the brief holds: "the gap from the 18:44:30 marker to the first in-geofence fix at 18:44:45 is 15 seconds, i.e. one and a half of the trace's 10-second sampling intervals"
    contradicted (draft 3, not material): "The first in-radius fix is at 18:44:45, one 10-second sampling interval after the 18:44:30 marker." [EV-GPS-00214.sample_interval_sec 10.0 with EV-TRIP-00214.arrived_at 18:44:30 and first in-radius fix 18:44:45]
      the brief holds: "the first in-radius fix at 18:44:45 is 15 seconds - one and a half 10-second sampling intervals - after the 18:44:30 marker"
    contradicted (draft 3, not material): "That sub-interval difference does not make the marker false: POL-NS-05, the clause that polices premature arrival taps, fires only where the driver is more than 300 m from the pin or moving at 15 km/h or above at the marker, and neither holds (the driver's furthest point anywhere in the pickup is 178.95 m)." [EV-GPS-00214.sample_interval_sec 10.0 with EV-TRIP-00214.arrived_at 18:44:30 and first in-geofence fix 18:44:45]
      the brief holds: "the 15-second gap is one and a half of the trace's 10-second sampling intervals, not a sub-interval difference"

  29 case(s) verified, 0 refused, 19 contradicted statement(s) (8 material, 11 not), 1479451 verifier token(s).
  the verifier moved the vote on: 102, 108, 110
  abstaining on any contradiction would have moved: 101, 102, 106, 108, 109, 110, 112, 115, 208, 214
  materiality alone keeps the vote on: 101, 106, 109, 112, 115, 208, 214

All three readings are of the source run's own drafts and of one set of verdicts, so a difference between them is the rule and not a second sampling of the judge.