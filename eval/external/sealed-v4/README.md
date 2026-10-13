# tribunal-sealed-v4 (cases)

A held-out test set for the Tribunal dispute-arbitration system, written against
Ryde Dispute Resolution Policy v2.1 as encoded in policy version 7
(general.json, route_deviation.json, no_show.json). It is meant for a single run.

- 30 case files: case-06001.json to case-06015.json (ROUTE_DEVIATION) and
  case-06051.json to case-06065.json (NO_SHOW_CHARGE).
- Shape: the public case-file contract (schema_version 1.2.0; four top-level keys;
  eight-key evidence artifacts in the order TRIP_RECORD, GPS_TRACE, CHAT_LOG,
  FARE_BREAKDOWN, RIDER_PROFILE, DRIVER_PROFILE, TRAFFIC_ADVISORY x1-2).
- Version-7 optional fields used: rider_profile.fraud_flags, driver_profile.fraud_flags,
  rider_profile.no_show_cancellations_30d, trip_record.in_app_calls
  ({placed_by, placed_at, duration_sec, answered}), VOICE_CALL_LOG chat entries
  (channel), dispute.safety_flag. No-show trip records carry no platform_policy.
- Extra payload fields: trip_record.optimal_route_via / actual_route_via (road lists),
  GPS points carry accuracy_m (and a map-matched road on route cases), traffic
  advisories carry road, direction, valid_from / valid_to and an LTA-style message.
- index.json lists every case with its SHA-256. CANARY.txt holds this set's marker string.

The reference answers are not in this folder.
