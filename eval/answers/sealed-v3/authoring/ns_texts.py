"""Text templates for build/cases_ns.py: each {name} is filled by cases_ns.values() from the case as
written (measured figures, policy figures, key figures). Generated from the blueprint texts by an
authoring tool, then reviewed; cases_ns asserts that every filled template equals the blueprint text."""
TEMPLATES = {4051: {'claim': 'I was already downstairs at the void deck of blk 823 by the letterbox. I messaged the driver twice '
                 'asking where he was, he never reply and never call me, then he cancel and mark me no-show. Kena '
                 'charged {fee_line} for nothing. Please refund.',
        'cp': 'I reached on time and waited more than 4 minutes at the drop-off porch. I called her twice, nobody '
              'answer. This rider always like that, never come down, check her record.',
        'ev:0': 'Rider R-5126 booked TRP-04051 (RYDE_X), pickup Blk 823 Tampines St 81, drop-off Tampines Hub. '
                'On-demand trip.',
        'ev:1': 'Driver D-7342 assigned, grey Toyota Corolla Altis. ETA 4 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:6': 'Cancellation fee SGD {fee_line} charged to rider payment method (SGD {fee_net} net to driver).',
        'msg:1': 'ok omw, abt 3 min',
        'msg:2': 'hi i at the void deck beside the letterbox already, where are u?',
        'msg:3': 'uncle cannot see ur car leh, which side u park?',
        'msg:4': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls holds no '
                           "record. chat_message_count {chat_count} equals the chat_log's message count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Arrival marker to cancellation '
                         '({t_arrived}-{t_cancelled}): {m_w_fixes} fixes, max interval {m_w_max_interval_s} s, '
                         '{m_w_dist_to_pin_m_min}-{m_w_dist_to_pin_m_max} m from the pickup pin, speed '
                         '{win_speed_max}. rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}; '
                         '{m_r_filtered_over_25m} report accuracy worse than {acc_filter} m '
                         '({m_r_filtered_accuracy_m_0}, {m_r_acc_all_max} m); the other {m_r_qualifying} lie '
                         '{m_r_qualifying_dist_m_min}-{m_r_qualifying_dist_m_max} m from the pin. The fix before the '
                         'arrival marker ({m_pre_tap_ts}) lies {m_pre_tap_d} m from the pickup pin at {m_pre_tap_v} '
                         'km/h.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04051-001 to -004, sequential; the count equals '
                        'trip_record.chat_message_count. MSG-04051-002 and MSG-04051-003 (RIDER, {msg2_sent} and '
                        '{msg3_sent}) show delivered_at {msg2_deliv} and {msg3_deliv} and no read_at. Largest '
                        'interval between messages {chat_big_s} s ({chat_big_from} to {chat_big_to}).',
        'det:CHAT_LOG:0': 'Two RIDER messages delivered, never marked read by the recipient.',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}; lifetime prior_no_show_flags '
                             '{rp_prior_no_show_flags}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-04 decides. Rider R-5126 filed against a {fee_line} no-show line. EV-CHAT-04051 (weight '
                     "{w_CHAT}, UNREAD_MESSAGE: the rider's messages were delivered and not read; NS-04 does not "
                     'require them to be read) holds two rider messages inside the waiting window '
                     '{t_arrived}-{t_cancelled}: {msg2_sent} giving her position at the void deck by the letterbox '
                     'and asking where the driver is, and {msg3_sent} saying she cannot see the car. NS-04(b): the '
                     'driver posted nothing after {k_last_driver_post} and EV-TRIP-04051 in_app_calls is empty, so '
                     'there is no reply within {reply_s} s and no in-app call before the RIDER_NO_SHOW termination; '
                     "the driver's 'called twice' has no record. NS-04(c): EV-GPS-04051 rider_track holds {m_r_n} "
                     'fixes in the window, {m_r_filtered_over_25m} filtered at {m_r_filtered_accuracy_m_0} and '
                     '{m_r_acc_all_max} m accuracy; of the {m_r_qualifying} qualifying fixes '
                     '{m_r_qualifying_within_presence_radius} lie within the {presence} m STANDARD presence radius '
                     '({r_within_dmin}-{r_within_dmax} m) and {r_outside_n} at {m_r_qualifying_dist_m_max} m, a '
                     "majority. The driver's own trace would satisfy POL-NS-01 (qualifying fixes inside {radius} m "
                     'from {m_fq_ts}, {fq_lead_s} s before the {t_arrived} marker; a {m_dwell_fq_s} s dwell to the '
                     'termination against free_wait {free_wait}), but NS-04 displaces NS-01 and POL-NS-07, so the '
                     'fee is refunded in full with no driver compensation: FULL_REFUND {k_amount}, the gross line '
                     "EV-FARE-04051 charged and the amount contested. POL-GEN-01: the driver's appeal to the rider's "
                     'record rests on prior_no_show_flags {rp_prior_no_show_flags}, a lifetime counter, and is '
                     'discarded; the citable no_show_disputes_30d is {rp_no_show_disputes_30d}, so POL-NS-09(d) is '
                     'not engaged. Confidence is capped at {w_CHAT} by EV-CHAT-04051, above the {floor} floor; no '
                     'POL-NS-08 limb is engaged.'},
 4052: {'claim': 'I reached the pickup on time at 7.31pm and waited more than 4 min at the drop off point, then the '
                 'rider cancelled. The app charged her the cancellation fee but support refunded her and now I get '
                 'nothing for the trip. I did my part, please give me back my cancellation fee.',
        'cp': 'Paiseh, I decided to walk out to the main road and catch a taxi there instead, so I cancelled the '
              'booking. Support already refunded me and I do not think I should pay.',
        'ev:0': 'Rider R-5389 booked TRP-04052 (RYDE_X), pickup Blk 617 Hougang Ave 8, drop-off Serangoon NEX. '
                'On-demand trip.',
        'ev:1': 'Driver D-6015 assigned, white Toyota Prius. ETA 7 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': "Trip cancelled by rider after the driver's arrival.",
        'ev:6': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'ev:7': 'Cancellation fee SGD {fee_line} refunded to rider by support after a rider complaint.',
        'msg:1': 'ok coming',
        'msg:2': 'how long more?',
        'msg:3': 'abt 2 min, jam at the junction',
        'msg:4': 'reached, at the drop off point downstairs',
        'msg:5': 'Trip cancelled by rider. Cancellation fee SGD {fee_line} applies.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_RIDER). The arrival marker coincides '
                           'with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, {m_arr_v} km/h). '
                           '{n_events} events, all PLATFORM_TELEMETRY; driver_assigned shows ETA {eta_min} min. '
                           "in_app_calls holds no record. chat_message_count {chat_count} equals the chat_log's "
                           'count.',
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         "interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Arrival marker to the rider's "
                         'cancellation ({t_arrived}-{t_cancelled}): {m_w_fixes} fixes, max interval '
                         '{m_w_max_interval_s} s, {m_w_dist_to_pin_m_min}-{m_w_dist_to_pin_m_max} m from the pickup '
                         'pin, speed {win_speed_max}. rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}, accuracy '
                         '{m_r_acc_all_min}-{m_r_acc_all_max} m; from {t_arrived} every rider fix lies '
                         '{m_r_qualifying_dist_m_min}-{r_from_arrival_dmax} m from the pin. The fix before the '
                         'arrival marker ({m_pre_tap_ts}) lies {m_pre_tap_d} m from the pickup pin at {m_pre_tap_v} '
                         'km/h.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04052-001 to -005, sequential; the count equals '
                        'trip_record.chat_message_count. Largest interval {chat_big_s} s ({msg1_sent} to '
                        '{msg2_sent}); the interval containing the arrival marker is {chat_span_s} s '
                        '({chat_span_from} to {chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}; payment_status '
                              'REFUNDED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'CONGESTION notice for Hougang Ave 8, valid {adv01_from}-{adv01_to}, issued '
                                   '{adv01_issued}. No second feed reports congestion on this road in that window; '
                                   "the driver's fixes on Hougang Ave 8 from {ave8_from} to {ave8_to} report "
                                   '{ave8_vmin}-{ave8_vmax} km/h.',
        'det:TRAFFIC_ADVISORY-01:0': 'Single-feed congestion notice; not corroborated by a second source.',
        'rationale': 'POL-NS-10(g) with POL-NS-07. Driver D-6015 filed after support reversed the {fee_line} fee '
                     '(EV-FARE-04052: line {fee_line}, REFUNDED {refund}). EV-TRIP-04052 shows the rider cancelled '
                     'at {t_cancelled}, {k_after_accept} s after accepted_at {t_accepted}, so the POL-NS-10(a) grace '
                     'of {grace} s does not apply. EV-GPS-04052 places the driver inside the {radius} m STANDARD '
                     'radius from {m_fq_ts}, rolling to a stop {fq_lead_s} s before the {t_arrived} arrival marker, '
                     'with qualifying fixes (accuracy {m_dw_acc_min}-{m_dw_acc_max} m, {m_dw_dmin}-{m_dw_dmax} m '
                     'from the pin) continuously to the cancellation: the POL-NS-02 arrival holds and the '
                     'in-geofence dwell measured as POL-NS-01(c) measures it was {m_dwell_fq_s} s, past '
                     'free_wait_sec {free_wait}. Under NS-10(g) the fee stands at '
                     'platform_policy.cancellation_fee_sgd {fee_net} as if the driver had terminated for a no-show, '
                     "limb (f)'s exceptions do not apply (and none is on the record: en route at "
                     '{ev_driver_en_route}, arrival on the {eta_min} min ETA, no request to cancel, vehicle as '
                     'booked), and POL-NS-07 fixes the payout. Anti-farming check on EV-DPROF-04052: '
                     'no_show_terminations_30d {dp_no_show_terminations_30d} of completed_trips_30d '
                     '{dp_completed_trips_30d}, below both limbs. Compensation = {comp_rate} x {fee_net} = '
                     '{k_payout} (net figure). Ruling DRIVER_COMPENSATION, amount_sgd {k_amount} = '
                     'driver_compensation_sgd {k_amount} per POL-GEN-03. EV-ADVIS-04052-01 (weight {w_ADVIS-01}, '
                     'ADVISORY_UNCORROBORATED) decides nothing: POL-NS-06(i) is not in play and a congestion notice '
                     'does not excuse anything. Deciding artifacts are at weight {w_TRIP}.'},
 4053: {'claim': 'I reached blk 435 at 9.14pm and waited more than 3 minutes, also called the rider but no answer. '
                 'Only then I cancelled as no-show. Support reversed my fee because the rider complained. I waited '
                 'properly, please return my {contested}.',
        'cp': 'I told him I was coming down. The lift was very slow and by the time I reached the ground floor the '
              'trip was already cancelled. He cancelled almost immediately.',
        'ev:0': 'Rider R-6241 booked TRP-04053 (RYDE_X), pickup Blk 435 Ang Mo Kio Ave 10, drop-off Bishan Junction '
                '8. On-demand trip.',
        'ev:1': 'Driver D-8127 assigned, silver Honda Shuttle. ETA 8 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'In-app call from driver to rider, rang {call1_dur} s, not answered.',
        'ev:6': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:7': 'Cancellation fee SGD {fee_line} charged to rider payment method (SGD {fee_net} net to driver).',
        'ev:8': 'Cancellation fee SGD {fee_line} refunded to rider by support after a rider complaint.',
        'msg:1': 'omw',
        'msg:2': 'ok coming down',
        'msg:3': 'reached, at the drop off',
        'msg:4': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls: one DRIVER '
                           'call {call1_at}, not answered, {call1_dur} s. chat_message_count {chat_count} equals the '
                           "chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}; every interval is {cadence} s except '
                         'one of {m_gap_s} s, from {m_gap_from} to {m_gap_to}, inside which the trip_record '
                         'cancellation ({t_cancelled}) falls. From the arrival marker ({t_arrived}) to the '
                         'cancellation the trace holds {m_w_fixes} fixes, all between {t_arrived} and {m_gap_from}, '
                         '{m_arr_d}-{m_w_dist_to_pin_m_max} m from the pickup pin, accuracy '
                         '{m_acc_min}-{m_w_accuracy_m_max} m, speed {win_speed_max}; {k_unobserved_s} s of that '
                         '{m_dwell_tap_s} s window lies inside the gap. The first fix after the gap ({m_gap_to}) is '
                         '{m_post_gap_d} m from the pin at {m_pre_tap_v} km/h. rider_track is empty. The fix before '
                         'the arrival marker ({m_pre_tap_ts}) lies {m_pre_tap_d} m from the pickup pin at '
                         '{m_pre_tap_v} km/h.',
        'det:GPS_TRACE:0': '{m_gap_s} s without a fix, {m_gap_from} to {m_gap_to}, spanning the {t_cancelled} '
                           'cancellation.',
        'det:GPS_TRACE:1': "rider_track empty: no fixes from the rider's device.",
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04053-001 to -004, sequential; the count equals '
                        'trip_record.chat_message_count. Largest interval {chat_big_s} s ({chat_big_from} to '
                        '{chat_big_to}); the interval containing the arrival marker is {chat_span_s} s '
                        '({chat_span_from} to {chat_span_to}). No RIDER message between {t_arrived} and '
                        '{t_cancelled}.',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}; payment_status '
                              'REFUNDED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'ESCALATE under POL-NS-08 and POL-NS-09(e), with POL-GEN-02(2) and POL-NS-09(a). Driver D-8127 '
                     'contests {contested} after support refunded the {fee_line} line (EV-FARE-04053). The fee needs '
                     'POL-NS-01(c): a continuous in-geofence dwell of free_wait_sec {free_wait} before the '
                     "{t_cancelled} RIDER_NO_SHOW termination. The only carrier of the driver's position is "
                     'EV-GPS-04053 (weight {w_GPS}: GPS_GAP straddling the cancellation {wf_GPS_GPS_GAP} x '
                     'PARTIAL_RECORD {wf_GPS_PARTIAL_RECORD}). It shows the driver rolling into the {radius} m '
                     'radius at {m_fq_ts}, {fq_lead_s} s before the {t_arrived} arrival marker, and qualifying fixes '
                     'to {m_gap_from} (eight fixes, {k_observed_s} s), then no fix for {m_gap_s} s until {m_gap_to}, '
                     'a gap that contains the cancellation; {k_unobserved_s} s of the {m_dwell_fq_s} s from the '
                     'first qualifying fix to the cancellation is unobserved. That is a sampling gap over '
                     '{gap_policy} s inside the waiting window, so the trace is impaired under POL-NS-08(b), and it '
                     'is the sole evidence for the deciding fact: the arrival marker is BUTTON (POL-NS-12 does not '
                     "apply), and the {call1_at} call in EV-TRIP-04053 and the chat place nobody. POL-NS-08's "
                     'closing sentence and POL-NS-09(e) send the case to a person; the gap factor alone '
                     '({wf_GPS_GPS_GAP}) also caps confidence below {floor} (POL-GEN-02(2), POL-NS-09(a)); POL-NS-11 '
                     'removes only the rider_track factor from that cap. Neither the {k_hypo_payout} payout '
                     '(continuity read across the gap) nor a short-dwell finding against the driver (a claim on an '
                     'impaired artifact cannot alone support a ruling against the party it disfavours) can issue. '
                     'The open question for the reviewer: where was the driver between {m_gap_from} and '
                     '{t_cancelled}. The fee is held; no money moves.'},
 4054: {'claim': 'I booked a taxi at 12.39pm and the car icon kept moving away from me in the other direction. After '
                 '6 minutes it was still nowhere near so I cancelled, still kena charged {fee_line}. Not my fault '
                 'the driver went the wrong way, please refund.',
        'cp': 'When I accepted I was driving the other way on the main road, I had to U-turn at the junction which '
              'took less than a minute. After that I was coming straight to her and I was still within the ETA when '
              'she cancelled.',
        'ev:0': 'Rider R-5703 booked TRP-04054 (RYDE_TAXI), pickup Blk 206 Toa Payoh Lorong 8, drop-off Novena '
                'Square. On-demand trip.',
        'ev:1': 'Driver D-9056 assigned, blue Hyundai Ioniq taxi. ETA 9 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Trip cancelled by rider before the driver's arrival.",
        'ev:4': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'msg:1': 'hi uncle where are u? app show ur car going the other way',
        'msg:2': 'sorry need to u-turn at the junction just now, coming already',
        'msg:3': 'so long ah... nvm',
        'msg:4': 'Trip cancelled by rider. Cancellation fee SGD {fee_line} applies.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, cancelled '
                           '{t_cancelled} (CANCELLED_BY_RIDER); arrived_at null. {n_events} events, all '
                           'PLATFORM_TELEMETRY; driver_assigned shows ETA {eta_min} min; driver_en_route at '
                           '{ev_driver_en_route}. in_app_calls holds no record. chat_message_count {chat_count} '
                           "equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {t_accepted}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Distance to the pickup pin: '
                         '{m_d_accept} m at {t_accepted}, rising to {m_peak_d} m at {m_peak_ts}, then falling at '
                         'every fix to {m_d_grace_end} m at {m_grace_end} and {m_d_cancel} m at {t_cancelled}. No '
                         'fix within {radius} m of the pin. rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}, '
                         'accuracy {m_r_acc_all_min}-{m_r_acc_all_max} m, '
                         '{m_r_qualifying_dist_m_min}-{m_r_qualifying_dist_m_max} m from the pin.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04054-001 to -004, sequential; the count equals '
                        'trip_record.chat_message_count. The trip has no arrival marker.',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_TAXI as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-10(f) decides; NO_ACTION. Rider R-5703 cancelled at {t_cancelled} (EV-TRIP-04054, '
                     'CANCELLED_BY_RIDER), {k_after_accept} s after accepted_at {t_accepted}, so the {grace} s grace '
                     "of POL-NS-10(a) had run out; scheduled_at is null. Under NS-10(f) a rider's own cancellation "
                     "after the grace is chargeable at platform_policy.cancellation_fee_sgd 'whether or not the "
                     "driver had arrived', and stands unless the record shows one of four exceptions; none is shown. "
                     '(1) Movement toward the pickup within the grace: EV-TRIP-04054 driver_en_route '
                     '{ev_driver_en_route}, and EV-GPS-04054 shows the taxi heading away only until the U-turn (peak '
                     '{m_peak_d} m at {m_peak_ts}), then closer at every fix: {m_d_accept} m at acceptance, '
                     '{m_d_grace_end} m at {m_grace_end} when the grace ended, {m_d_cancel} m at the cancellation. '
                     "(2) The first ETA shown was {eta_min} min ({k_eta_at}), so 'not arrived within {eta_slack} s "
                     "of the first ETA' could not have occurred by {t_cancelled}. (3) EV-CHAT-04054 has no request "
                     'to cancel; the driver explained the U-turn and said he was coming. (4) Vehicle and driver '
                     'match the booking. The fee stands; the {fee_gross} line (EV-FARE-04054) is the gross figure '
                     'and reconciles under POL-NS-08(d). POL-NS-07 pays only under POL-NS-01 or NS-10(g), neither of '
                     "which applies, so there is no driver compensation: the rider's claim is not supported and the "
                     "charge stays as it is. The rider's 'moving away' account is true only of the first {k_away_s} "
                     "s. POL-NS-02's never-arrived refund concerns the no-show fee on a driver termination (it is "
                     "framed as POL-NS-01(b) failing); NS-10(f) expressly makes the rider's late cancellation "
                     'chargeable without arrival. All deciding artifacts are at weight {w_TRIP}.'},
 4055: {'claim': 'I was waiting at Lobby B and messaged the driver to ask where he was. He never replied and still '
                 'cancelled me as no-show, charged {fee_line}. Also please check this driver, I think he does this '
                 'to other passengers also.',
        'cp': 'I waited at the guardhouse drop-off, which is where the pin was, for more than 5 minutes. The rider '
              'never came to the guardhouse.',
        'ev:0': 'Rider R-7718 booked TRP-04055 (RYDE_X), pickup Simei St 4 condominium guardhouse, drop-off Changi '
                'Business Park Central 1. On-demand trip.',
        'ev:1': 'Driver D-6630 assigned, dark grey Kia Niro. ETA 9 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:6': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'msg:1': 'on the way',
        'msg:2': 'nearly there, 3 min',
        'msg:3': 'Reached, at the guardhouse drop off',
        'msg:4': "I'm at Lobby B, where are you?",
        'msg:5': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls holds no '
                           "record. chat_message_count {chat_count} equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Arrival marker to cancellation '
                         '({t_arrived}-{t_cancelled}): {m_w_fixes} fixes, max interval {m_w_max_interval_s} s, '
                         '{m_w_dist_to_pin_m_min}-{m_w_dist_to_pin_m_max} m from the pickup pin, speed '
                         '{win_speed_max}; the first fix within {radius} m of the pin is {m_fq_ts} ({m_fq_d} m). '
                         'rider_track is empty. The fix before the arrival marker ({m_pre_tap_ts}) lies '
                         '{m_pre_tap_d} m from the pickup pin at {m_pre_tap_v} km/h.',
        'det:GPS_TRACE:0': "rider_track empty: no fixes from the rider's device.",
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04055-001 to -005, sequential; the count equals '
                        'trip_record.chat_message_count. MSG-04055-004 (RIDER, {msg4_sent}) read {msg4_read}; no '
                        'later DRIVER message. Largest interval {chat_big_s} s ({chat_big_from} to {chat_big_to}); '
                        'the interval containing the arrival marker is {chat_span_s} s ({chat_span_from} to '
                        '{chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; lifetime '
                              'prior_no_show_flags {dp_prior_no_show_flags}; vehicle_type RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-11 (amendment 0001) decides, with POL-NS-01 and POL-NS-07. Rider R-7718 contests the '
                     '{fee_line} fee (EV-FARE-04055). POL-NS-04 limbs (a) and (b) hold on EV-CHAT-04055 and '
                     "EV-TRIP-04055: her {msg4_sent} message ('I'm at Lobby B, where are you?') is locating, and the "
                     'driver neither replied nor placed an in-app call. But EV-GPS-04055 carries no rider_track, so '
                     'limb (c) cannot be run: under POL-NS-11 it is undecidable, NS-04 cannot exonerate the rider, '
                     "and the dispute is decided on the driver's own evidence; the missing rider_track does not "
                     "impair the trace for the driver's arrival or dwell, does not engage POL-NS-08(b) or "
                     "POL-NS-09(e) and does not lower the cap (the trace's {w_GPS} PARTIAL_RECORD weight, disclosed, "
                     "is above {floor} in any case). The driver's evidence satisfies POL-NS-01: qualifying fixes "
                     'inside the {radius} m LARGE_VENUE radius from {m_fq_ts}, before the {t_arrived} arrival marker '
                     '(NS-02, limb b); at the guardhouse pin {m_w_dist_to_pin_m_min}-{m_w_dist_to_pin_m_max} m away, '
                     'speed {win_speed_max}, at a {cadence} s cadence to the {t_cancelled} cancellation, a '
                     '{m_dwell_tap_s} s dwell from the marker ({m_dwell_fq_s} s from the first qualifying fix) '
                     'against free_wait_sec {free_wait} (limb c); RIDER_NO_SHOW after the dwell (limb d). The driver '
                     'was inside the radius, so POL-NS-03 has nothing to decide; no clause from NS-03 to NS-06 '
                     'displaces NS-01. POL-NS-07 anti-farming on EV-DPROF-04055: no_show_terminations_30d '
                     '{dp_no_show_terminations_30d} of completed_trips_30d {dp_completed_trips_30d}, neither limb '
                     'tripped; payout {comp_rate} x {fee_net} = {k_payout}. Ruling DRIVER_COMPENSATION {k_amount} '
                     "(amount_sgd = driver_compensation_sgd, POL-GEN-03); the rider's charge stands. POL-GEN-01: the "
                     "rider's request to 'check this driver' cannot be answered from "
                     'driver_profile.prior_no_show_flags {dp_prior_no_show_flags}, a lifetime counter that is '
                     'context only; the citable trailing-window counters are the NS-07 figures above '
                     '({dp_no_show_terminations_30d} of {dp_completed_trips_30d}).'},
 4056: {'claim': 'Dear Ryde Support, I booked a ride from Northpoint City on 3 Oct at about 3pm. I waited at the '
                 'pickup point shown in the app, but the driver never came to me. We messaged each other and he kept '
                 'saying he was at the pickup point, but there was no white car where I was standing. After about 6 '
                 'minutes he cancelled and I was charged a {fee_line} no-show fee. I was there the whole time, so I '
                 'should not have to pay. Please refund the {fee_line}.',
        'cp': 'I went to the pickup point the app showed for Northpoint City and waited more than 6 minutes there. I '
              'told her in the chat that I was at the pickup point with my hazard lights on. She never came to the '
              'car.',
        'ev:0': 'Rider R-8204 booked TRP-04056 (RYDE_X), pickup Northpoint City, drop-off Sun Plaza Sembawang. '
                'On-demand trip.',
        'ev:1': 'Driver D-5471 assigned, white Toyota Corolla Altis. ETA 10 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:6': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'msg:1': 'about 3 min more',
        'msg:2': "Hi I'm here already, where are you?",
        'msg:3': "I'm at the pickup point already, white Corolla, hazard lights on",
        'msg:4': "I don't see any white car here leh",
        'msg:5': "I'm at the pin location, still waiting for you",
        'msg:6': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). pickup venue_id VEN-YS-0031; registered_pickup_points {rpp}. {n_events} '
                           'events, all PLATFORM_TELEMETRY. in_app_calls holds no record. chat_message_count '
                           "{chat_count} equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. From {t_arrived} to '
                         '{t_cancelled}: {m_w_fixes} fixes, speed {win_speed_max}, {m_stat_dmin}-{m_stat_dmax} m '
                         'from the pickup pin, each carrying venue_id VEN-YS-0031. Nearest approach to the pin in '
                         'the {lookback_min} minutes before {t_cancelled}: {m_stat_dmin} m; no fix within {radius} '
                         'm. rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}, accuracy '
                         '{m_r_acc_all_min}-{m_r_acc_all_max} m, '
                         '{m_r_qualifying_dist_m_min}-{m_r_qualifying_dist_m_max} m from the pin.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04056-001 to -006, sequential; the count equals '
                        'trip_record.chat_message_count. RIDER messages at {msg2_sent} and {msg4_sent} are followed '
                        'by DRIVER messages {reply_after_2} s and {reply_after_4} s later. Largest interval '
                        '{chat_big_s} s ({chat_big_from} to {chat_big_to}), which contains the arrival marker.',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net}; rider_gross_cancellation_fee_sgd null.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-03(ii), a compound ruling, with POL-NS-02. Rider R-8204 contests the {fee_line} fee '
                     '(EV-FARE-04056). EV-GPS-04056 shows the driver stationary (speed {win_speed_max}) from the '
                     '{t_arrived} arrival marker to the {t_cancelled} RIDER_NO_SHOW termination, {m_dwell_tap_s} s '
                     'against free_wait_sec {free_wait} (EV-TRIP-04056 platform_policy), at a point '
                     '{m_stat_dmin}-{m_stat_dmax} m from the Northpoint City pin: outside the {radius} m LARGE_VENUE '
                     'arrival radius, inside the {ceiling} m ceiling; no fix in the {lookback_min} minutes before '
                     'the cancellation comes within {radius} m. POL-NS-02 therefore yields to POL-NS-03: '
                     'POL-NS-01(b) fails and the fee is refunded to the rider in full, {k_amount}, the amount '
                     'contested. POL-NS-05 does not apply: the marker was pressed while stationary within {false_d} '
                     "m. The stationary fixes carry venue_id VEN-YS-0031, the pickup's own, corroborating a wrong "
                     "face of the same venue. Fault for the driver's compensation is read from EV-CHAT-04056: each "
                     'rider message was answered within {reply_s} s ({reply_after_2} s and {reply_after_4} s), so '
                     "POL-NS-04 does not apply, and neither party named an entrance, wing, block or bay ('I'm here', "
                     "'at the pickup point', 'at the pin location'), so limb (i) does not apply; EV-TRIP-04056 "
                     'registered_pickup_points is {rpp}, so under limb (ii) the mislocation is pin ambiguity and the '
                     'driver receives a platform-funded goodwill payment of {goodwill_pct} % x {fee_net} = '
                     '{k_goodwill}, never recovered from the rider. POL-GEN-03: the two payments are independent and '
                     "not netted; the ruling value names the filing party's outcome, FULL_REFUND, amount_sgd "
                     '{k_amount}, driver_compensation_sgd {k_dc}. No POL-NS-07 payout arises (NS-01 fails). All '
                     'deciding artifacts are at weight {w_TRIP}.'},
 4057: {'claim': 'I waited at the pickup for 7 minutes and called the rider 2 times, no answer, then I cancelled as '
                 'no-show. Support refunded the rider the {fee_line} cancellation fee and I got nothing. Please '
                 'review, I followed the rules.',
        'cp': 'Sorry, I overslept and only came down after the driver had cancelled. Support already refunded me.',
        'ev:0': 'Rider R-6052 booked TRP-04057 (RYDE_X), pickup Blk 664 Jurong West St 64, drop-off Jurong East MRT. '
                'On-demand trip.',
        'ev:1': 'Driver D-7869 assigned, silver Honda Vezel. ETA 8 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'In-app call from driver to rider, rang {call1_dur} s, not answered.',
        'ev:6': 'In-app call from driver to rider, rang {call2_dur} s, not answered.',
        'ev:7': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:8': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'ev:9': 'Cancellation fee SGD {fee_line} refunded to rider by support after a rider request.',
        'msg:1': 'Morning, omw',
        'msg:2': 'abt 4 min',
        'msg:3': 'Reached blk 664 drop off point, silver Honda Vezel',
        'msg:4': "Hello? I'm downstairs waiting",
        'msg:5': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls: two DRIVER '
                           'calls, {call1_at} and {call2_at}, not answered, {call1_dur} s each. chat_message_count '
                           "{chat_count} equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Arrival marker to cancellation '
                         '({t_arrived}-{t_cancelled}): {m_w_fixes} fixes, max interval {m_w_max_interval_s} s, '
                         '{m_w_dist_to_pin_m_min}-{m_w_dist_to_pin_m_max} m from the pickup pin, speed '
                         '{win_speed_max}. rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}, all reporting accuracy '
                         'worse than {acc_filter} m ({m_r_filtered_accuracy_m_0}, {m_r_filtered_accuracy_m_1}, '
                         '{m_r_acc_all_min}, {m_r_acc_all_max} m). The fix before the arrival marker '
                         '({m_pre_tap_ts}) lies {m_pre_tap_d} m from the pickup pin at {m_pre_tap_v} km/h.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04057-001 to -005, sequential; the count equals '
                        'trip_record.chat_message_count. No RIDER message. Largest interval {chat_big_s} s '
                        '({chat_big_from} to {chat_big_to}); the interval containing the arrival marker is '
                        '{chat_span_s} s ({chat_span_from} to {chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}; payment_status '
                              'REFUNDED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net}; rider_gross_cancellation_fee_sgd null.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-01 and POL-NS-07. Driver D-7869 contests the {fee_line} fee that support refunded '
                     '(EV-FARE-04057: line {fee_line}, REFUNDED {refund}). EV-TRIP-04057 platform_policy '
                     '(RECORD-PLATFORM) sets free_wait_sec {free_wait} and cancellation_fee_sgd {fee_net}. (a) The '
                     'trip_record has the {t_arrived} arrival. (b) EV-GPS-04057 has qualifying fixes (accuracy under '
                     '{m_fq_v} m) inside the {radius} m STANDARD radius from {m_fq_ts}, as the car rolled to a stop '
                     '{fq_lead_s} s before the marker, and from the marker '
                     '{m_w_dist_to_pin_m_min}-{m_w_dist_to_pin_m_max} m from the pin. (c) The driver held the radius '
                     'at a {cadence} s cadence for {m_dwell_fq_s} s to the {t_cancelled} cancellation, against '
                     '{free_wait} s. (d) RIDER_NO_SHOW, no boarding, after the dwell. Two unanswered in-app calls '
                     '({call1_at}, {call2_at}) are recorded. No clause from POL-NS-03 to POL-NS-06 displaces NS-01: '
                     'the driver was in the radius, the marker fix was at the pin at {m_arr_v} km/h, the dwell is '
                     'long, and POL-NS-04 has no rider message to start from (her four device fixes are all filtered '
                     'at {m_r_acc_all_min}-{m_r_acc_all_max} m accuracy, which would leave limb (c) undecidable in '
                     'any case). The rider admits she overslept. POL-NS-07 anti-farming on EV-DPROF-04057: '
                     'no_show_terminations_30d {dp_no_show_terminations_30d} of completed_trips_30d '
                     '{dp_completed_trips_30d}, neither limb tripped. Payout {comp_rate} x {fee_net} = {k_payout}. '
                     'Ruling DRIVER_COMPENSATION, amount_sgd {k_amount} = driver_compensation_sgd {k_amount} '
                     '(POL-GEN-03). All deciding artifacts are at weight {w_TRIP}.'},
 4058: {'claim': 'Dear Ryde Support, on the night of 13 Aug I took a booking at Changi T3 arrival. I reached the '
                 'pickup point at 11.42pm and waited more than 9 minutes, called the passenger twice with no answer, '
                 'and she only said she was still at the belt. I cancelled as no-show after 9 minutes. The '
                 '{fee_line} no-show fee was charged to the passenger but it is not in my earnings yet. Please '
                 'credit my {fee_line}.',
        'cp': 'My flight landed late and the luggage took very long to come out. I told the driver I needed more '
              'time. I do not think I should pay a no-show fee when I was inside the airport the whole time.',
        'ev:0': 'Rider R-9137 booked TRP-04058 (RYDE_PLUS), pickup Changi Airport T3 Arrival private-hire pickup '
                'point, drop-off Rivervale Mall. On-demand trip.',
        'ev:1': 'Driver D-5928 assigned, black Toyota Camry. ETA 3 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'In-app call from driver to rider, rang {call1_dur} s, not answered.',
        'ev:6': 'In-app call from driver to rider, rang {call2_dur} s, not answered.',
        'ev:7': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:8': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'msg:1': 'On the way to T3 arrival pickup',
        'msg:2': "Hi I'm at the T3 arrival pickup point, black Toyota Camry",
        'msg:3': 'still waiting for my luggage at the belt, 10 more min',
        'msg:4': 'Sorry cannot wait so long at the pickup, pls come out asap',
        'msg:5': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls: two DRIVER '
                           'calls, {call1_at} and {call2_at}, not answered, {call1_dur} s each. chat_message_count '
                           "{chat_count} equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Arrival marker to cancellation '
                         '({t_arrived}-{t_cancelled}): {m_w_fixes} fixes, max interval {m_w_max_interval_s} s, '
                         '{m_w_dist_to_pin_m_min}-{m_w_dist_to_pin_m_max} m from the pickup pin, speed '
                         '{win_speed_max}; the first fix within {radius} m is {m_fq_ts} ({m_fq_d} m). rider_track: '
                         '{m_r_n} fixes {m_r_first}-{m_r_last}, accuracy {m_r_acc_all_min}-{m_r_acc_all_max} m, '
                         '{m_r_qualifying_dist_m_min}-{m_r_qualifying_dist_m_max} m from the pin. The fix before the '
                         'arrival marker ({m_pre_tap_ts}) lies {m_pre_tap_d} m from the pickup pin at {m_pre_tap_v} '
                         'km/h.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04058-001 to -005, sequential; the count equals '
                        'trip_record.chat_message_count. MSG-04058-003 (RIDER, {msg3_sent}) is followed by a DRIVER '
                        'message at {msg4_sent}. The interval containing the arrival marker is {chat_span_s} s '
                        '({chat_span_from} to {chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net}; rider_gross_cancellation_fee_sgd null.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; lifetime '
                              'prior_no_show_flags {dp_prior_no_show_flags}; vehicle_type RYDE_PLUS as on '
                              'trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': "ESCALATE under POL-NS-07's anti-farming check and POL-NS-09(d); the facts are clear and the "
                     'policy requires a person. Driver D-5928 asks for his payout on the {fee_net} fee '
                     '(EV-FARE-04058, CHARGED). POL-NS-01 is satisfied: EV-GPS-04058 places him inside the {radius} '
                     'm AIRPORT radius at the T3 arrival pickup from before the {t_arrived} marker (qualifying fixes '
                     'from {m_fq_ts}, {m_fq_d} m out and slowing) and holding position at a {cadence} s cadence to '
                     'the {t_cancelled} RIDER_NO_SHOW termination, {m_dwell_tap_s} s from the marker against '
                     'free_wait_sec {free_wait}, the cancellation also past no_show_threshold_sec {threshold} '
                     '(EV-TRIP-04058 platform_policy); two unanswered in-app calls are recorded. POL-NS-04 does not '
                     "apply: the rider's {msg3_sent} message was answered at {msg4_sent}, and her device stayed "
                     '{m_r_qualifying_dist_m_min_r0}-{m_r_qualifying_dist_m_max_r0} m away. No clause from NS-03 to '
                     "NS-06 displaces NS-01. POL-NS-07's check on EV-DPROF-04058: no_show_terminations_30d "
                     '{dp_no_show_terminations_30d} (>= {farm_n}) and {dp_no_show_terminations_30d} / '
                     'completed_trips_30d {dp_completed_trips_30d} = {k_farm_rate} (> {farm_rate}): both limbs trip, '
                     'so compensation is withheld and the case escalates under POL-NS-09(d), the packet directing '
                     "the reviewer to refund the rider's {fee_net} in full; the automated pipeline pays nothing and "
                     'refunds nothing, the fee is held (POL-GEN-03: ESCALATE replaces the ruling, null money). '
                     'POL-GEN-01: the lifetime prior_no_show_flags {dp_prior_no_show_flags} is not the counter and '
                     'cannot clear the driver. A DRIVER_COMPENSATION of {comp_rate} x {fee_net} = {k_withheld} is '
                     'exactly what NS-07 withholds.'},
 4059: {'claim': 'I reached the pickup at 6.21pm and waited for the rider 5 minutes. Serangoon Road has a bus lane '
                 'so I cannot stop there long, I went one round and came back to the same place, still she never '
                 'came down so I cancelled. Support reversed my fee. I waited the full time, the bus lane is not my '
                 'fault. Please return my {contested}.',
        'cp': 'I came down to the road and the car was not there. Then the app showed the trip was cancelled. '
              'Support already refunded me.',
        'ev:0': 'Rider R-7465 booked TRP-04059 (RYDE_X), pickup Serangoon Road shophouse, Little India, drop-off '
                'Bugis Junction. On-demand trip.',
        'ev:1': 'Driver D-8394 assigned, white Toyota Sienta. ETA 9 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'In-app call from driver to rider, rang {call1_dur} s, not answered.',
        'ev:6': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:7': 'Cancellation fee SGD {fee_line} charged to rider payment method (SGD {fee_net} net to driver).',
        'ev:8': 'Cancellation fee SGD {fee_line} refunded to rider by support after a rider complaint.',
        'msg:1': 'on the way',
        'msg:2': 'abt 3 min',
        'msg:3': 'reach already, outside the shop. bus lane cannot wait long ah',
        'msg:4': 'go one round come back',
        'msg:5': 'ok coming down now',
        'msg:6': "ok I'm back in front",
        'msg:7': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls: one DRIVER '
                           'call {call1_at}, not answered, {call1_dur} s. chat_message_count {chat_count} equals the '
                           "chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Arrival marker to cancellation '
                         '({t_arrived}-{t_cancelled}): {m_w_fixes} fixes, max interval {m_w_max_interval_s} s, '
                         '{m_w_dist_to_pin_m_min}-{m_loop_max_d} m from the pickup pin. Fixes within {radius} m of '
                         'the pin: {m_fq_ts}-{m_in_radius_intervals_0_1} and {m_in_radius_intervals_1_0}-{win_last}; '
                         'from {loop_first} to {loop_last} every fix is outside {radius} m, the farthest '
                         '{m_loop_max_d} m from the pin. rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}; the '
                         '{r_bad_n} up to {r_bad_last_ts} report accuracy worse than {acc_filter} m; {r_qual0_ts} '
                         'and {r_qual1_ts} report {r_qual0_acc} m and {r_qual1_acc} m accuracy, {r_qual0_d} m and '
                         '{r_qual1_d} m from the pin. The fix before the arrival marker ({m_pre_tap_ts}) lies '
                         '{m_pre_tap_d} m from the pickup pin at {m_pre_tap_v} km/h.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04059-001 to -007, sequential; the count equals '
                        'trip_record.chat_message_count. MSG-04059-005 (RIDER, {msg5_sent}) is followed by a DRIVER '
                        'message at {msg6_sent}. Largest interval {chat_big_s} s ({chat_big_from} to {chat_big_to}); '
                        'the interval containing the arrival marker is {chat_span_s} s ({chat_span_from} to '
                        '{chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}; payment_status '
                              'REFUNDED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}. '
                              'driver_profile.vehicle_type RYDE_XL; trip_record.vehicle_type for this trip RYDE_X.',
        'det:DRIVER_PROFILE:0': 'vehicle_type RYDE_XL on the profile against RYDE_X on the trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'KERB_RESTRICTION (full-day bus lane) on Serangoon Road, geometry a {adv01_len10} '
                                   'm stretch whose line passes {m_advisory_pin_offset_m} m from the pickup pin; '
                                   'valid {adv01_from}-{adv01_to} on 2026-09-25, covering {t_arrived}-{t_cancelled}; '
                                   'issued {adv01_issued} the same day.',
        'rationale': 'POL-NS-06, limbs (i) and (ii); NO_ACTION. Driver D-8394 contests {contested} after support '
                     'refunded the {fee_line} line (EV-FARE-04059). Free wait in force is {free_wait} s '
                     '(EV-TRIP-04059 platform_policy). EV-GPS-04059 places the driver inside the {radius} m STANDARD '
                     'radius only from {m_fq_ts} (rolling to the kerb {fq_lead_s} s before the {t_arrived} arrival '
                     'marker) to {m_in_radius_intervals_0_1} ({m_i1} s) and from {m_in_radius_intervals_1_0} to the '
                     '{t_cancelled} RIDER_NO_SHOW termination ({m_i2} s); between, he drove round the block, every '
                     'fix outside {radius} m and none farther than {m_loop_max_d} m from the pin. EV-ADVIS-04059-01 '
                     'is a KERB_RESTRICTION (full-day bus lane) whose geometry covers the Serangoon Road frontage '
                     'and whose window {adv01_from}-{adv01_to} covers the wait, so NS-06(i) lets the two intervals '
                     'be summed: {m_i1} + {m_i2} = {k_sum_s} s, short of {free_wait} by {k_short_s} s (even bracketing '
                     'each run from the last outside fix before it to the first outside fix after it or the '
                     'termination, whichever comes first - {gen1_from}-{gen1_to} = {m_i1_generous} s and '
                     '{gen2_from}-{t_cancelled} = {m_i2_generous} s - the total is {k_generous_s} s; the in-radius '
                     'fixes at {post_in0} and {post_in1} come after the termination and are not waiting). '
                     'NS-06(ii): the advisory never reduces the minimum or excuses the shortfall. The fee is therefore not chargeable and belongs refunded to the rider; '
                     'no driver compensation is payable, and POL-NS-07 cannot run because POL-NS-01(c) fails. The '
                     "driver's claim to his {fee_net} is unsupported; NO_ACTION, which on this driver-filed dispute "
                     'leaves the rider refunded (POL-GEN-03; it never restores the charge). The {k_elapsed_min} min '
                     '{k_elapsed_sec} s that elapsed between the arrival marker and the cancellation is not '
                     "in-geofence dwell. POL-NS-04 plays no part (the rider's message was answered in "
                     '{reply_after_5} s and an in-app call is recorded). EV-DPROF-04059 (weight {w_DPROF}, '
                     'CROSS_SOURCE_CONFLICT on vehicle_type) carries nothing this ruling rests on. Deciding '
                     'artifacts are at {w_TRIP}.'},
 4060: {'claim': 'I cancelled the booking about 2 minutes after the driver accepted because my plans changed. The '
                 'app says cancellation is free within 3 minutes but I was still charged {fee_line}. Please refund.',
        'cp': 'I was already downstairs waiting when she cancelled. I came very fast, I should get the fee.',
        'ev:0': 'Rider R-5951 booked TRP-04060 (RYDE_X), pickup Blk 175 Punggol Field, drop-off Sengkang MRT. '
                'On-demand trip.',
        'ev:1': 'Driver D-6702 assigned, grey Hyundai Avante. ETA 2 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'Trip cancelled by rider.',
        'ev:6': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'msg:1': 'Hi coming, 2 min',
        'msg:2': 'reached downstairs',
        'msg:3': 'sorry need to cancel, plans changed',
        'msg:4': 'Trip cancelled by rider. Cancellation fee SGD {fee_line} applies.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_RIDER). The arrival marker coincides '
                           'with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, {m_arr_v} km/h). '
                           '{n_events} events, all PLATFORM_TELEMETRY. in_app_calls holds no record. '
                           "chat_message_count {chat_count} equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         "interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. Arrival marker to the rider's "
                         'cancellation ({t_arrived}-{t_cancelled}): {m_w_fixes} fixes, '
                         '{m_arr_d}-{m_w_dist_to_pin_m_max} m from the pickup pin, speed {win_speed_max}. '
                         'rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}, all reporting accuracy worse than '
                         '{acc_filter} m. The fix before the arrival marker ({m_pre_tap_ts}) lies {m_pre_tap_d} m '
                         'from the pickup pin at {m_pre_tap_v} km/h.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04060-001 to -004, sequential; the count equals '
                        'trip_record.chat_message_count. Largest interval {chat_big_s} s ({chat_big_from} to '
                        '{chat_big_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net}, rider_gross_cancellation_fee_sgd {fee_gross}, '
                              'grace_after_match_sec {grace}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-10(a) and (c); FULL_REFUND {k_amount}. Rider R-5951 cancelled at {t_cancelled} '
                     '(EV-TRIP-04060, CANCELLED_BY_RIDER), {k_after_accept} s after accepted_at {t_accepted}, inside '
                     'grace_after_match_sec {grace} (platform_policy). Under NS-10(a) that cancellation is not '
                     "chargeable 'whatever the driver's position', and a driver's early arrival does not shorten the "
                     "grace: the {t_arrived} arrival marker and the driver's fixes at the pin (EV-GPS-04060) change "
                     'nothing. NS-10(g) cannot apply either: the in-geofence dwell at the cancellation, from the '
                     'first qualifying fix at {m_fq_ts} ({fq_lead_s} s before the marker), was {m_dwell_fq_s} s, not '
                     'past free_wait_sec {free_wait}. NS-10(c): the fee charged on a non-chargeable cancellation is '
                     'refunded in full with no driver compensation: the {k_amount} line (EV-FARE-04060, the gross '
                     'figure) = the amount contested. The grace runs from accepted_at, not from requested_at '
                     '{t_requested} (which would give {k_after_request} s). All deciding artifacts are at weight '
                     '{w_TRIP}.'},
 4061: {'claim': 'The app itself confirmed my arrival at Bukit Panjang Plaza and ran the wait timer. I waited more '
                 'than 8 minutes and called the rider two times, and only cancelled after the no-show threshold. '
                 "Support reversed my fee saying my GPS only had a few points. The app's own arrival record shows I "
                 'was there. Please give back my {contested}.',
        'cp': 'When I came down to the plaza the driver was not there. Support already refunded me.',
        'ev:0': 'Rider R-8530 booked TRP-04061 (RYDE_X), pickup Bukit Panjang Plaza (Jelebu Road side), drop-off Lot '
                'One, Choa Chu Kang. On-demand trip.',
        'ev:1': 'Driver D-9213 assigned, blue Toyota C-HR. ETA 8 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': 'Platform geofence check passed: driver {platform_geofence_m} m from the pickup point, speed '
                '{m_arr_v} km/h. Arrival marked automatically.',
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'Free waiting period {free_wait} s running (to {ev_wait_timer_expired}).',
        'ev:6': 'In-app call from driver to rider, rang {call1_dur} s, not answered.',
        'ev:7': 'Free waiting period ended at {ev_wait_timer_expired}; no boarding recorded.',
        'ev:8': 'In-app call from driver to rider, rang {call2_dur} s, not answered.',
        'ev:9': 'No-show threshold of {threshold} s from arrival reached. Driver may cancel for rider no-show.',
        'ev:10': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:11': 'Cancellation fee SGD {fee_line} charged to rider payment method (SGD {fee_net} net to driver).',
        'ev:12': "Cancellation fee SGD {fee_line} refunded to rider by support after review of the driver's GPS "
                 'export.',
        'msg:1': 'On the way',
        'msg:2': 'nearly there',
        'msg:3': "Hi, I'm at the Jelebu Road side drop off of the plaza, blue C-HR",
        'msg:4': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). '
                           'arrival_marker GPS_AUTO. {n_events} events, all PLATFORM_TELEMETRY: driver_arrived '
                           '{t_arrived} states its geofence check ({platform_geofence_m} m from the pickup point, '
                           '{m_arr_v} km/h); wait_timer_started {ev_wait_timer_started}; wait_timer_expired '
                           '{ev_wait_timer_expired}; no_show_threshold_reached {ev_no_show_threshold_reached}; '
                           'trip_cancelled {t_cancelled}. The nearest gps_trace fix to the arrival event is '
                           '{m_arr_dt} s from it. in_app_calls: two DRIVER calls, {call1_at} and {call2_at}, not '
                           'answered, {call1_dur} s and {call2_dur} s. chat_message_count {chat_count} equals the '
                           "chat_log's count.",
        'adm:GPS_TRACE': 'Driver-device export: {m_n_fixes} fixes {m_first_fix}-{m_last_fix}, intervals '
                         '{m_intervals_0}, {m_intervals_1}, {m_intervals_2}, {m_intervals_3}, {m_intervals_4} s; no '
                         'fix reports accuracy_m. The first fix is {m_first_after_accept_s} s after accepted_at and '
                         'the last {m_last_after_term_s} s after the trip_record cancellation. Between the arrival '
                         'event ({t_arrived}) and the cancellation ({t_cancelled}) the export holds {m_w_fixes} '
                         'fixes ({m_win_fixes_detail_0_0}, {m_win_fixes_detail_1_0}, {m_win_fixes_detail_2_0}), each '
                         'speed {win_speed_max} and '
                         '{m_win_fixes_detail_0_1}/{m_win_fixes_detail_1_1}/{m_win_fixes_detail_2_1} m from the '
                         'pickup pin; every interval in that window exceeds {gap_policy} s. The fix before the '
                         'window ({m_pre_tap_ts}) is {m_pre_tap_d} m from the pin at {m_pre_tap_v} km/h; the fix '
                         'after it ({m_last_fix}) {m_after_term_0} m at {m_after_term_1} km/h. rider_track is empty. '
                         "The file was exported from the driver's own device and is not reconciled against platform "
                         'telemetry.',
        'det:GPS_TRACE:0': 'Export sampled every {m_intervals_4}-{m_intervals_0} s; no accuracy field.',
        'det:GPS_TRACE:1': "rider_track empty: no fixes from the rider's device.",
        'det:GPS_TRACE:2': "File exported from the driver's own device; not reconciled against platform telemetry.",
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04061-001 to -004, sequential; the count equals '
                        'trip_record.chat_message_count. No RIDER message. Largest interval {chat_big_s} s '
                        '({chat_big_from} to {chat_big_to}); the interval containing the arrival event is '
                        '{chat_span_s} s ({chat_span_from} to {chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}; payment_status '
                              'REFUNDED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-12 (amendment 0003) supplies the carrier; POL-NS-01 and POL-NS-07 decide. Driver D-9213 '
                     'contests the {fee_net} net fee after support refunded the {fee_line} gross line '
                     '(EV-FARE-04061). EV-TRIP-04061 platform_policy states arrival_marker GPS_AUTO, free_wait_sec '
                     '{free_wait}, no_show_threshold_sec {threshold}, cancellation_fee_sgd {fee_net}, gross '
                     "{fee_gross}. Its PLATFORM_TELEMETRY events hold the platform's own arrival event at "
                     '{t_arrived} stating the geofence test ({platform_geofence_m} m from the pickup point, '
                     '{m_arr_v} km/h), wait_timer_started {ev_wait_timer_started} and wait_timer_expired '
                     '{ev_wait_timer_expired}, both before the {t_cancelled} RIDER_NO_SHOW termination, which is '
                     '{m_dwell_tap_s} s after arrival and so past the {threshold} s threshold. Under NS-12 these '
                     'events are an independent carrier for POL-NS-01(b) and (c): arrival is established at '
                     '{t_arrived} and the free waiting period is established as served. The exported EV-GPS-04061 '
                     '(weight {w_GPS}: LOW_SAMPLE_RATE x PARTIAL_RECORD x UNVERIFIED_SOURCE; impaired under '
                     'POL-NS-08(b): three fixes about {cadence} s apart in the window, no accuracy field) does not '
                     'impair the events and is weighed only for contradiction: its window fixes '
                     '{m_win_fixes_detail_0_0}, {m_win_fixes_detail_1_0} and {m_win_fixes_detail_2_0} lie '
                     '{m_win_fixes_detail_0_1}/{m_win_fixes_detail_1_1}/{m_win_fixes_detail_2_1} m from the pin at '
                     "{m_arr_v} km/h, inside the {radius} m radius, so nothing contradicts the platform. NS-08's "
                     'escalation sentence does not apply because the impaired export is not the only evidence, and '
                     'NS-08(a) is not engaged (nearest fix {m_arr_dt} s from the arrival event; the export runs from '
                     '{m_first_after_accept_s} s after acceptance to {m_last_after_term_s} s after the termination). '
                     'NS-01(d) holds. POL-NS-04 has no rider message to start from. POL-NS-07 anti-farming on '
                     'EV-DPROF-04061: {dp_no_show_terminations_30d} of {dp_completed_trips_30d}, clean. Payout = '
                     '{comp_rate} x the NET {fee_net} = {k_amount} (never {comp_rate} x {fee_gross}). Ruling '
                     'DRIVER_COMPENSATION, amount_sgd {k_amount} = driver_compensation_sgd {k_amount} (POL-GEN-03). '
                     'Confidence rests on EV-TRIP-04061 at {w_TRIP} (POL-GEN-02(2)).'},
 4062: {'claim': 'I was standing at the pickup point beside the MRT exit at Raffles Place the whole time and the car '
                 'never came. The driver kept saying he was at the pickup but there was no black car. Then he '
                 'cancelled and I was charged {fee_line} for no-show. Please refund.',
        'cp': 'I was at the pickup point the whole time from 12.33, I even replied to her message. She was not '
              'there. In the CBD the GPS always jumps around, but I never moved my car.',
        'ev:0': 'Rider R-6875 booked TRP-04062 (RYDE_X), pickup Raffles Place beside the MRT exit near One Raffles '
                'Place, drop-off Outram Park MRT. On-demand trip.',
        'ev:1': 'Driver D-5146 assigned, black Mazda 6. ETA 8 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:6': 'Cancellation fee SGD {fee_line} charged to rider payment method (SGD {fee_net} net to driver).',
        'msg:1': 'omw',
        'msg:2': '2 min',
        'msg:3': "Hi I'm at the pickup by the MRT exit, where are you?",
        'msg:4': "I'm at the pickup point already, black Mazda with hazard lights",
        'msg:5': 'dont see any black car here leh',
        'msg:6': 'still here at the pin, pls look around',
        'msg:7': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). '
                           'arrival_marker BUTTON; the marker coincides with a gps_trace fix ({m_arr_dt} s; '
                           '{m_arr_d} m from the pickup pin, {m_arr_v} km/h). {n_events} events, all '
                           'PLATFORM_TELEMETRY; none states a geofence test. in_app_calls holds no record. '
                           "registered_pickup_points {rpp}. chat_message_count {chat_count} equals the chat_log's "
                           'count.',
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix} at a {cadence} s cadence, max interval '
                         '{m_max_gap} s. From the arrival marker ({t_arrived}) to the cancellation ({t_cancelled}): '
                         '{m_w_fixes} fixes, every one reporting speed {win_speed_max} and accuracy '
                         '{m_w_accuracy_m_min}-{m_w_accuracy_m_max} m, while their positions lie '
                         '{m_w_dist_to_pin_m_min}-{m_far_max} m from the pickup pin: {m_win_near} within {radius} m '
                         '(at most {m_near_max} m) and {m_win_far} at {m_far_min}-{m_far_max} m; {m_jumps_ge_80} of '
                         'the {m_jump_pairs} consecutive pairs are {m_jumps_ge_80_min}-{m_jump_max} m apart. The '
                         'longest run of consecutive fixes within {radius} m in that window is {m_longest_near_run}. '
                         'From {canyon_from} the approach fixes report accuracy '
                         '{canyon_acc_min_r0}-{canyon_acc_max_r0} m and jump in the same way. rider_track is empty.',
        'det:GPS_TRACE:0': 'Stationary ({m_arr_v} km/h) fixes jumping {jump_floor_m}-{jump_max_r10} m between '
                           'consecutive readings although each reports {canyon_acc_min_r0}-{canyon_acc_max_r0} m '
                           'accuracy.',
        'det:GPS_TRACE:1': "rider_track empty: no fixes from the rider's device.",
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04062-001 to -007, sequential; the count equals '
                        'trip_record.chat_message_count. RIDER messages at {msg3_sent} and {msg5_sent} are followed '
                        'by DRIVER messages {reply_after_3} s and {reply_after_5} s later. Largest interval '
                        '{chat_big_s} s ({chat_big_from} to {chat_big_to}); the interval containing the arrival '
                        'marker is {chat_span_s} s ({chat_span_from} to {chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net} and rider_gross_cancellation_fee_sgd {fee_gross}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'ESCALATE under POL-GEN-02(2) and POL-NS-09(a). Rider R-6875 contests the {fee_line} fee '
                     '(EV-FARE-04062). Every possible ruling turns on where the driver was from the {t_arrived} '
                     'marker to the {t_cancelled} RIDER_NO_SHOW termination: inside the {radius} m radius for '
                     '{free_wait} s (POL-NS-01, DRIVER_COMPENSATION {k_hypo_payout}), stationary outside {radius} m '
                     'but within {ceiling} m (POL-NS-03, full refund, goodwill depending on the chat), or never '
                     'arrived (POL-NS-02). The only carrier is EV-GPS-04062, weight {w_GPS} (GPS_DRIFT '
                     '{wf_GPS_GPS_DRIFT} x PARTIAL_RECORD {wf_GPS_PARTIAL_RECORD}): in that window its {m_w_fixes} '
                     'fixes all report speed {win_speed_max} and accuracy {m_w_accuracy_m_min_r0}-{m_acc_max_r0} m, '
                     'yet sit in two clusters, {m_win_near} within {radius} m and {m_win_far} at '
                     '{m_far_min_r0}-{m_far_max_r0} m to the north-east, with consecutive readings jumping up to '
                     '{m_jump_max_r0} m; no run within {radius} m is longer than {m_longest_near_run} fixes. The '
                     'marker is BUTTON, so POL-NS-12 gives no platform carrier; EV-TRIP-04062 records only the tap; '
                     "EV-CHAT-04062 holds two competing assertions ('at the pickup by the MRT exit', 'at the pin'); "
                     'rider_track is empty. None of POL-NS-08(a)-(d) is engaged ({cadence} s cadence, no gap, marker '
                     'on a fix, chat complete, fee reconciles), so this is not an NS-08 escalation, but '
                     'POL-GEN-02(2) caps confidence at the weight of the artifact carrying the deciding fact: '
                     '{w_GPS}, or {wf_GPS_GPS_DRIFT} if the rider_track factor is set aside under POL-NS-11, below '
                     'the {floor} floor either way, and POL-NS-09(a) escalates. POL-NS-04 cannot rescue the rider: '
                     "the driver answered within {reply_after_3} s. The reviewer must establish the vehicle's "
                     'position {t_arrived}-{t_cancelled} from a non-drifting source. No money moves; the fee is '
                     'held.'},
 4063: {'claim': 'The driver only reached at about 8.06am and I came down straight away, but I was charged a '
                 '{fare_waiting_time_fee} waiting fee. I did not make him wait, please remove the waiting fee.',
        'cp': 'I reached at 8.02am and waited more than 6 minutes at the drop-off porch. I messaged her and even '
              'called her in the app.',
        'ev:0': 'Rider R-9402 booked TRP-04063 (RYDE_X), pickup Blk 858 Woodlands Drive 50, drop-off Woodlands Civic '
                'Centre. On-demand trip.',
        'ev:1': 'Driver D-7580 assigned, silver Toyota Corolla Altis. ETA 8 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'In-app call from driver to rider, answered, {call1_dur} s.',
        'ev:6': 'Rider boarded; trip started.',
        'ev:7': 'Waiting-time fee SGD {fare_waiting_time_fee} added to the fare.',
        'ev:8': 'Trip completed at Woodlands Civic Centre.',
        'msg:1': 'Morning, on the way',
        'msg:2': 'abt 4 min',
        'msg:3': 'Reached, at the drop off porch blk 858',
        'msg:4': 'ok wait ah, coming down',
        'msg:5': 'still waiting ya, already more than 3 min, waiting fee start liao',
        'msg:6': 'can call me at [REDACTED]',
        'msg:7': 'pls use the in app call, I call u now',
        'msg:8': 'coming coming',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, started {t_started}, ended {t_ended} (COMPLETED). The arrival marker '
                           'coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, {m_arr_v} '
                           'km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls: one DRIVER call '
                           '{call1_at}, answered, {call1_dur} s. actual_distance_km {trip_actual_distance_km} is the '
                           'trace distance from {t_started} to {t_ended} ({m_trip_km} km) rounded. '
                           "chat_message_count {chat_count} equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. The fixes at {t_arrived} and '
                         '{m_pre_fq_ts} lie {m_arr_d} m and {m_pre_fq_d} m from the pickup pin; from {m_fq_ts} to '
                         '{t_started} every fix lies within {radius} m ({m_dwell_fixes} fixes, max interval '
                         '{m_w_max_interval_s} s). rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}; the first '
                         '{r_bad_n} report accuracy worse than {acc_filter} m; {r_qual0_ts} reports {r_qual0_acc} m '
                         'accuracy, {r_qual0_d} m from the pin.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04063-001 to -008, sequential; the count equals '
                        'trip_record.chat_message_count. MSG-04063-006 (RIDER, {msg6_sent}) is flagged redacted: a '
                        'contact number was masked by the data-minimisation filter. The interval containing the '
                        'arrival marker is {chat_span_s} s ({chat_span_from} to {chat_span_to}).',
        'det:CHAT_LOG:0': 'One RIDER message masked for a contact number.',
        'adm:FARE_BREAKDOWN': 'METERED completed fare: base_fare {fare_base_fare}, distance_fare '
                              '{fare_distance_fare} ({billed_km} km at {per_km}), time_fare {fare_time_fare} '
                              '({billed_min} min at {per_min}), platform_fee {fare_platform_fee}, waiting_time_fee '
                              '{fare_waiting_time_fee}; lines sum to total_charged {total}; surge {surge_mult}; no '
                              'ERP gantries; CHARGED, refund {refund}. trip_record.platform_policy states '
                              'waiting_fee_sgd {waiting_fee} and free_wait_sec {free_wait}.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-10(d); NO_ACTION. Rider R-9402 contests the {contested} waiting_time_fee on a completed '
                     'trip (EV-FARE-04063: base {fare_base_fare} + distance {fare_distance_fare} + time '
                     '{fare_time_fare} + platform {fare_platform_fee} + waiting {fare_waiting_time_fee} = {total}). '
                     'NS-10(d) makes the waiting fee (platform_policy.waiting_fee_sgd {waiting_fee}, EV-TRIP-04063) '
                     "chargeable where the trip was completed and the driver's in-geofence dwell before boarding, "
                     'measured as POL-NS-01(c) measures it (from the first qualifying in-geofence fix, not the '
                     'arrival tap), exceeded free_wait_sec {free_wait}. EV-GPS-04063: the first fix within the '
                     '{radius} m STANDARD radius with accuracy under {acc_filter} m is {m_fq_ts} ({m_fq_d} m), and '
                     'every fix from then to boarding at {t_started} (EV-TRIP-04063 started_at) is inside the radius '
                     'at a {cadence} s cadence: {m_dwell_fq_s} s, which exceeds {free_wait}. The trip was completed '
                     '(ended {t_ended}) and no cancellation fee is on it, so the one-fee rule is respected. The '
                     "waiting line stands and NS-10(e) has nothing to refund. The rider's 'he only reached at about "
                     "{claimed_arrival_dot}' is contradicted by the trace (and her own {msg4_sent} chat 'ok wait ah, "
                     "coming down'); from {claimed_arrival_hm} the wait would have been {k_claimed_wait_s} s. "
                     'EV-CHAT-04063 (weight {w_CHAT}, CONTENT_REDACTED: a contact number masked) decides nothing. '
                     'Deciding artifacts are at weight {w_TRIP}.'},
 4064: {'claim': 'I reached the house and waited more than 5 minutes outside the gate, and called the rider but no '
                 'answer. Then I cancelled as no-show. Support reversed my {fee_line} because the rider said I '
                 'pressed arrived early. Ok I pressed it a bit early while still on Bukit Timah Road, but I still '
                 'waited the full time at the house. Please return my fee.',
        'cp': 'The driver marked arrived when he was still far away on Bukit Timah Road. I should not have to pay '
              'for a fake arrival.',
        'ev:0': 'Rider R-7096 booked TRP-04064 (RYDE_X), pickup Sixth Avenue landed estate, drop-off Holland '
                'Village. On-demand trip.',
        'ev:1': 'Driver D-8861 assigned, white Honda Freed. ETA 8 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'In-app call from driver to rider, rang {call1_dur} s, not answered.',
        'ev:6': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:7': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'ev:8': 'Cancellation fee SGD {fee_line} refunded to rider by support after a rider complaint.',
        'msg:1': 'On the way, ETA 8 min',
        'msg:3': 'app says you arrived? where are you',
        'msg:4': 'turning in now, 1 min',
        'msg:5': "I'm outside the house now, white Honda Freed",
        'msg:6': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). {n_events} events, all PLATFORM_TELEMETRY. in_app_calls: one DRIVER '
                           'call {call1_at}, not answered, {call1_dur} s. chat_message_count {chat_count}; the '
                           'chat_log holds {chat_held}.',
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. The fix at the arrival marker '
                         '({t_arrived}) is {m_arr_d} m from the pickup pin at {m_arr_v} km/h. The first fix within '
                         '{radius} m is {m_fq_ts} ({m_fq_d} m; the {m_pre_fq_ts} fix is {m_pre_fq_d} m); from '
                         '{m_fq_ts} to {t_cancelled} every fix lies within {radius} m ({m_dwell_fixes} fixes, max '
                         'interval {m_w_max_interval_s} s). rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}, '
                         'accuracy {m_r_acc_all_min}-{m_r_acc_all_max} m, '
                         '{m_r_qualifying_dist_m_min}-{m_r_qualifying_dist_m_max} m from the pin.',
        'adm:CHAT_LOG': '{chat_held} messages held with ids MSG-04064-001, -003, -004, -005, -006: -002 is absent, '
                        'and trip_record.chat_message_count is {chat_count}. The interval from MSG-04064-001 '
                        '({msg1_sent}) to MSG-04064-003 ({msg3_sent}) is {chat_big_s} s and contains the arrival '
                        'marker ({t_arrived}). MSG-04064-003 (RIDER) is followed by a DRIVER message {reply_after_3} '
                        's later.',
        'det:CHAT_LOG:0': 'One message missing from the export (sequence gap at -002).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}; payment_status '
                              'REFUNDED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net}; rider_gross_cancellation_fee_sgd null.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_X as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-05(iii), then POL-NS-01 and POL-NS-07; DRIVER_COMPENSATION {k_amount} with a '
                     'false-arrival referral. Driver D-8861 contests the {fee_line} fee support refunded '
                     '(EV-FARE-04064). The {t_arrived} arrival tap (EV-TRIP-04064) matches an EV-GPS-04064 fix at '
                     'the same second placing him {m_arr_d} m from the pin at {m_arr_v} km/h on Bukit Timah Road: '
                     'more than {false_d} m and at {false_v} km/h or above, so the marker is false and the clock is '
                     'recomputed from the first qualifying in-geofence fix, {m_fq_ts} ({m_fq_d} m, inside the '
                     '{radius} m radius; the {m_pre_fq_ts} fix was {m_pre_fq_d} m). From {m_fq_ts} every fix is '
                     'inside {radius} m at a {cadence} s cadence to the {t_cancelled} RIDER_NO_SHOW termination: a '
                     'corrected dwell of {m_dwell_fq_s} s against free_wait_sec {free_wait}. Limb (iii): the false '
                     'marker does not by itself defeat the fee; POL-NS-01 holds on the recomputed clock (limb b as '
                     'NS-01 now states, limb c {m_dwell_fq_s} s, limb d after the dwell), and POL-NS-07 fixes the '
                     'payout; the false-arrival event is recorded in referrals. POL-NS-04 cannot exonerate the '
                     'rider: an in-app call at {call1_at} is recorded (limb b) and her rider_track lies '
                     '{k_rt_min_km}-{k_rt_max_km} km away (limb c), so the TRUNCATED_LOG on EV-CHAT-04064 (weight '
                     '{w_CHAT}, MSG-04064-002 missing, POL-NS-08(c)) touches no deciding fact. Anti-farming on '
                     'EV-DPROF-04064: {dp_no_show_terminations_30d} of {dp_completed_trips_30d}, clean. Payout '
                     '{comp_rate} x {fee_net} = {k_payout}. Ruling DRIVER_COMPENSATION, amount_sgd {k_amount} = '
                     "driver_compensation_sgd {k_amount}, referral 'POL-NS-05(iii): false-arrival event recorded "
                     "against the driver' (a referral, not an escalation; it does not suppress the money). Deciding "
                     'artifacts are at weight {w_TRIP}.'},
 4065: {'claim': 'Dear Ryde Support, I booked an XL at Bedok Interchange on 18 Sep around 6pm. I told the driver I '
                 'was walking over. He cancelled after barely a minute and a half at the pickup bay and marked me as '
                 'a no-show, and I was charged {fee_line}. He did not even wait. Please refund the {fee_line}.',
        'cp': 'She said walking over 5 min, when I reached she still say 2 more min. Peak hour I cannot keep waiting '
              'for one passenger, so I cancelled.',
        'ev:0': 'Rider R-8318 booked TRP-04065 (RYDE_XL), pickup Bedok Bus Interchange private-hire pickup bay, '
                'drop-off Pasir Ris Mall. On-demand trip.',
        'ev:1': 'Driver D-6447 assigned, black Toyota Noah. ETA 8 min shown to rider.',
        'ev:2': 'Driver started navigating to the pickup point.',
        'ev:3': "Driver tapped I'm Here. Arrival marked by the driver.",
        'ev:4': 'Push notification sent to rider: your driver has arrived.',
        'ev:5': 'Trip cancelled by driver. Reason code RIDER_NO_SHOW.',
        'ev:6': 'Cancellation fee SGD {fee_line} charged to rider payment method.',
        'msg:1': 'omw',
        'msg:2': 'walking over now, about 5 min',
        'msg:3': 'ok',
        'msg:4': "I'm at the private hire bay, black Toyota Noah",
        'msg:5': '2 min, almost there',
        'msg:6': 'still 2 min ah? I cannot wait so long leh',
        'msg:7': 'Trip cancelled by driver. Reason: rider no-show. Cancellation fee SGD {fee_line} applied.',
        'adm:TRIP_RECORD': 'Timestamps run forward: requested {t_requested}, accepted {t_accepted}, arrived '
                           '{t_arrived}, cancelled {t_cancelled} (CANCELLED_BY_DRIVER, RIDER_NO_SHOW). The arrival '
                           'marker coincides with a gps_trace fix ({m_arr_dt} s; {m_arr_d} m from the pickup pin, '
                           '{m_arr_v} km/h). platform_policy source AUTHORED-V1: cancellation_fee_sgd {fee_net}, '
                           'free_wait_sec {free_wait}. {n_events} events, all PLATFORM_TELEMETRY. in_app_calls holds '
                           "no record. chat_message_count {chat_count} equals the chat_log's count.",
        'adm:GPS_TRACE': '{m_n_fixes} driver fixes {m_first_fix}-{m_last_fix}, median interval {m_median_s} s, max '
                         'interval {m_max_gap} s, accuracy {m_acc_min}-{m_acc_max} m. The first fix within {radius} '
                         'm of the pickup pin is {m_fq_ts} ({m_fq_d} m, {m_fq_v} km/h; the previous fix {m_pre_fq_d} '
                         'm); from {m_fq_ts} to the cancellation ({t_cancelled}) every fix lies within {radius} m '
                         '({m_w_fixes} fixes). rider_track: {m_r_n} fixes {m_r_first}-{m_r_last}, accuracy '
                         '{m_r_acc_all_min}-{m_r_acc_all_max} m, {m_r_qualifying_dist_m_min}-{m_r_all_dist_max} m '
                         'from the pin. The fix before the arrival marker ({m_pre_tap_ts}) lies {m_pre_tap_d} m from '
                         'the pickup pin at {m_pre_tap_v} km/h.',
        'adm:CHAT_LOG': '{chat_held} messages, MSG-04065-001 to -007, sequential; the count equals '
                        'trip_record.chat_message_count. MSG-04065-005 (RIDER, {msg5_sent}) is followed by a DRIVER '
                        'message at {msg6_sent}. The interval containing the arrival marker is {chat_span_s} s '
                        '({chat_span_from} to {chat_span_to}).',
        'adm:FARE_BREAKDOWN': 'One ledger line: cancellation_fee {fee_line} = total_charged {total}, payment_status '
                              'CHARGED, refund_issued_sgd {refund}. trip_record.platform_policy states '
                              'cancellation_fee_sgd {fee_net}; rider_gross_cancellation_fee_sgd null.',
        'adm:RIDER_PROFILE': 'Rider counters complete at the snapshot: no_show_disputes_30d '
                             '{rp_no_show_disputes_30d}, disputes_with_counterparty_90d '
                             '{rp_disputes_with_counterparty_90d}.',
        'adm:DRIVER_PROFILE': 'Driver counters complete at the snapshot: no_show_terminations_30d '
                              '{dp_no_show_terminations_30d}, completed_trips_30d {dp_completed_trips_30d}, '
                              'disputes_with_counterparty_90d {dp_disputes_with_counterparty_90d}; vehicle_type '
                              'RYDE_XL as on trip_record.',
        'adm:TRAFFIC_ADVISORY-01': 'Artifact absent: no traffic advisory was returned for the pickup road and the '
                                   'trip window. The identifier is minted so that the absence itself can be cited.',
        'rationale': 'POL-NS-06 with POL-NS-01(c); FULL_REFUND {k_amount}. Rider R-8318 contests the {fee_line} fee '
                     '(EV-FARE-04065). The figures in force come from EV-TRIP-04065 platform_policy '
                     '(fee_schedule.resolution_rule), an AUTHORED-V1 record for a RYDE_XL at a TRANSPORT_HUB: '
                     'cancellation_fee_sgd {fee_net} (the greater of zone {k_zone_fee} and tier {k_tier_fee}) and '
                     "free_wait_sec {free_wait}. EV-GPS-04065 places the driver's first fix inside the {radius} m "
                     'hub radius at {m_fq_ts} ({m_fq_d} m, accuracy under {cadence} m; the {m_pre_fq_ts} fix was '
                     '{m_pre_fq_d} m), stopping in the bay at the {t_arrived} tap, and he cancelled RIDER_NO_SHOW at '
                     '{t_cancelled}: an in-geofence dwell of {m_dwell_fq_s} s, short of {free_wait} s (and of the '
                     '{default_free_wait} s default). POL-NS-06: the fee is not chargeable and is refunded in full, '
                     "{k_amount}, with no driver compensation, whether or not the rider was present. The driver's "
                     'reason, that at peak hour he would not keep waiting for one passenger, is no ground: NS-06 is '
                     'strict liability; its limb (i) only lets separate in-geofence intervals be summed, and he held '
                     'the bay once without leaving and re-entering; nobody relies on a traffic advisory '
                     "(EV-ADVIS-04065-01 is MISSING). POL-NS-04 is not the route (the rider's {msg5_sent} message "
                     'was answered at {msg6_sent}; her track was '
                     '{m_r_qualifying_dist_m_min_r0}-{m_r_all_dist_max_r0} m away); POL-NS-07 cannot run. All '
                     'deciding artifacts are at weight {w_TRIP}.'}}
