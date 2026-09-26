"""Turn a loaded case into the evidence package the two advocate agents read.

WHY THIS EXISTS
---------------
A GPS trace dominates a case. ``loader.build_bundle(208)`` serialises to about
18,900 tokens, of which the GPS artifact alone is about 8,000 tokens of raw
latitude and longitude. A language model cannot use those coordinates: it
cannot compute haversine distance reliably, and a coordinate pair carries no
meaning to it. ``tribunal.facts`` already computes the scalars the policy
clauses threshold on, so this module puts those scalars into the package and
takes the raw points out.

LOCKED DESIGN RULE
------------------
Both advocates receive the **byte-identical** brief. Their only difference is
stance, and stance is applied later, when the prompt is rendered. This module
therefore produces exactly one object per case: there is no side or stance
parameter, and there is no rider or driver variant.

Policy values are read from the loaded policy and passed into ``facts``. No
policy number appears as a literal here, exactly as in ``facts.py``.
"""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import facts, loader, money

# The five evaluation-only keys the contract forbids anywhere in a bundle.
FORBIDDEN_KEYS = loader.FORBIDDEN_KEYS

GPS_EVIDENCE_TYPE = "GPS_TRACE"
TRIP_EVIDENCE_TYPE = "TRIP_RECORD"

# GPS payload fields that are already small summaries; they travel unchanged.
GPS_SUMMARY_FIELDS = (
    "trip_id",
    "point_count",
    "coverage_pct",
    "trace_distance_km",
    "sample_interval_sec",
    "expected_interval_sec",
    "first_fix_at",
    "last_fix_at",
    "gaps",
    "max_gap_sec",
)

# Raw coordinate arrays. These are the fields this module exists to remove.
GPS_RAW_FIELDS = ("points", "rider_track")

DRIVER_BLOCK = "driver_track"
RIDER_BLOCK = "rider_presence"
ARRIVAL_BLOCK = "arrival"
DERIVED_KEY = "derived"

# POL-RD-01's excess and status. Emitted for ROUTE_DEVIATION cases only.
DEVIATION_BLOCK = "deviation"
ROUTE_DEVIATION_CATEGORY = "ROUTE_DEVIATION"
POL_RD_01 = "POL-RD-01"

NO_DEVIATION_INPUTS_REASON = (
    "gps_trace.trace_distance_km and trip_record.optimal_distance_km are both required to "
    "measure the excess, and at least one of them is absent or not positive here"
)

NO_PICKUP_REASON = "trip_record.pickup is unavailable, so distances to the pickup point cannot be computed"
NO_ZONE_REASON = (
    "trip_record.pickup_zone_class is null, so the zone-dependent thresholds cannot be "
    "selected; no zone was substituted and no zone-dependent fact was computed"
)
NO_RIDER_TRACK_REASON = "the source trace carries no rider track, so there is nothing to summarise"
INCOMPLETE_POLICY_REASON = (
    "the loaded policy does not carry every zone-dependent threshold for this zone class, "
    "so no zone-dependent fact was computed"
)

# POL-RD-09(4): how close the trace came to each ERP gantry line on the fare
# breakdown. The block is emitted only where the fare breakdown carries gantry
# lines, the same way the deviation block is emitted for ROUTE_DEVIATION cases
# only. The clause's radius is a threshold and stays in the clause, so the
# block carries distances and decides no match.
ERP_GANTRY_PROXIMITY_KEY = "erp_gantry_proximity"
FARE_EVIDENCE_TYPE = "FARE_BREAKDOWN"
POL_RD_09 = "POL-RD-09"

NO_GANTRY_COORDINATES_REASON = (
    "this erp_gantry carries no coordinates, so how close the trace came to it is not "
    "computable from the record; POL-RD-09(4) provides that where an erp_gantry carries no "
    "coordinates the match is undecidable on the record and the line is treated as matched"
)
NO_TRACE_FIXES_REASON = (
    "the gps_trace carries no fixes, so how close the trace came to any gantry line is not "
    "computable from the record"
)

# POL-NS-06(i) and the two clauses it borrows a threshold from. The block below
# is emitted for NO_SHOW_CHARGE cases only, the same way the deviation block is
# emitted for ROUTE_DEVIATION cases only.
ACCUMULATED_DWELL_KEY = "accumulated_dwell"
LIMB_KEY = "limb"
POL_NS_05 = "POL-NS-05"
POL_NS_06 = "POL-NS-06"
TRAFFIC_ADVISORY_EVIDENCE_TYPE = "TRAFFIC_ADVISORY"

# The two dwell figures a shortfall can be measured against, named by the field
# each one is. Which of them is lawful is decided by limb (i) and is not the
# reader's to infer: POL-NS-06(i) is what permits the intervals to be summed, so
# where it is unavailable the operative dwell is the longest continuous run.
# A shortfall quoted off the sum on such a case reads negative and says "no
# shortfall" where the driver is in fact short — the arithmetic is right and the
# number is wrong, because it was computed on a basis the policy does not permit.
SHORTFALL_BASIS_KEY = "shortfall_basis"
BASIS_ACCUMULATED = "accumulated_sec"
BASIS_LONGEST_RUN = "longest_run_sec"

# Why limb (i) is or is not available, in the clause's own terms. A judge told
# "355 seconds" without being told why summing was permitted cannot cite the
# clause properly, and a judge told nothing at all repeats case 214.
NO_SECOND_INTERVAL_REASON = (
    "the trace shows {0} in-geofence interval(s) in which the driver held position, so there "
    "is no second interval for POL-NS-06(i) to add to the first"
)
EXCURSION_UNMEASURABLE_REASON = (
    "a recorded gap in the trace overlaps the stretch between the intervals, so the trace "
    "cannot show the driver leaving and re-entering the arrival radius without at any point "
    "travelling beyond the leash; the observed maximum is a lower bound and does not certify it"
)
EXCURSION_BEYOND_LEASH_REASON = (
    "the driver reached {0} m from the pin between the intervals, beyond the {1} m leash "
    "POL-NS-06(i) imposes"
)
ADVISORY_MISSING_REASON = (
    "{0} is MISSING, and POL-NS-06(i) requires a traffic_advisory that is present and "
    "populated: a MISSING traffic_advisory makes limb (i) unavailable, and asserting it "
    "against a MISSING artifact triggers POL-NS-09 rather than exonerating anyone"
)
ADVISORY_TYPE_NOT_ADMISSIBLE_REASON = (
    "no present traffic_advisory carries one of the type values POL-NS-06(i) names: {0}"
)
ADVISORY_ROUTE_NOT_COVERED_REASON = (
    "no present traffic_advisory has a geometry covering the pickup road "
    "(traffic_advisory.intersects_route is not true)"
)
ADVISORY_WINDOW_NOT_COVERED_REASON = (
    "no present traffic_advisory has an active window covering the waiting period "
    "(traffic_advisory.overlaps_trip_window is not true)"
)
LIMB_AVAILABLE_REASON = (
    "POL-NS-06(i) permits these intervals to be summed: {0} is present and populated with type "
    "{1}, its geometry covers the pickup road and its active window covers the waiting period, "
    "and the driver's furthest point between the intervals was {2} m, inside the {3} m leash"
)


def _sourced(value: Any, evidence_id: str) -> Dict[str, Any]:
    """Wrap one derived value with the evidence_id it was derived from.

    Every derived value carries its own source, so an advocate can always cite
    what it is reading. The source is never stated once for a whole block.
    """
    return {"value": value, "evidence_id": evidence_id}


def _threshold(value: Any, policy_id: str, zone_class: Optional[str]) -> Dict[str, Any]:
    """Wrap one policy threshold with the policy it was read from."""
    return {"value": value, "policy_id": policy_id, "zone_class": zone_class}


def _clause_threshold(value: Any, policy_id: str, clause_id: str) -> Dict[str, Any]:
    """Wrap a threshold that comes from a named clause rather than a zone class."""
    return {"value": value, "policy_id": policy_id, "clause_id": clause_id}


def _deviation_thresholds(policy: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """The four POL-RD-01 lines, read from the loaded clause text.

    POL-RD-01 is the one clause whose numbers the policy carries as **prose**.
    ``fare_model`` holds the fare constants, but nothing in the policy holds the
    deviation lines as a field — verified against
    ``policy/route_deviation.json``. They are therefore read out of the loaded
    clause's own ``rule`` string, so the values still come from the loaded
    policy and never from a literal here.

    Returns ``None`` when the policy has no POL-RD-01 clause, which is how a
    NO_SHOW_CHARGE case is recognised.
    """
    for clause in policy.get("clauses", []) or []:
        if clause.get("id") != POL_RD_01:
            continue
        rule = clause.get("rule", "")
        percents = re.findall(r"greater than\s+(\d+(?:\.\d+)?)\s*%", rule)
        kilometres = re.findall(r"greater than\s+(\d+(?:\.\d+)?)\s*km", rule)
        if len(percents) < 2 or len(kilometres) < 2:
            raise loader.LoaderError(
                "POL-RD-01's rule does not state both establishment and both "
                "materiality thresholds: found {0} percentage and {1} km "
                "lines".format(len(percents), len(kilometres))
            )
        return {
            "threshold_pct": float(percents[0]),
            "threshold_km": float(kilometres[0]),
            "material_pct": float(percents[1]),
            "material_km": float(kilometres[1]),
        }
    return None


def _no_show_thresholds(policy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """POL-NS-06(i)'s leash and advisory types, and POL-NS-05's motion line.

    Three values the policy carries as **prose** and nowhere as a field,
    verified against ``policy/no_show.json``:

    * the leash, from POL-NS-06's "without at any point travelling more than
      300 m from the pin";
    * the four admissible ``traffic_advisory.type`` values, from POL-NS-06's own
      list of them;
    * the speed at which this policy treats a driver as in motion rather than
      holding position, from POL-NS-05's "travelling at 15 km/h or above".

    They are read out of the loaded clause text, which is the route
    ``_deviation_thresholds`` already takes for POL-RD-01, and for the same
    reason: a value that came from a clause belongs in the loaded policy, and a
    silent default here would be a policy number hard-coded in ``tribunal/``.
    Where a line cannot be found this raises rather than falling back.

    Returns ``None`` when the policy has no POL-NS-06 clause, which is how a
    ROUTE_DEVIATION case is recognised.
    """
    clauses = {
        clause.get("id"): clause
        for clause in policy.get("clauses", []) or []
        if isinstance(clause, dict)
    }

    no_show = clauses.get(POL_NS_06)
    if no_show is None:
        return None

    rule = no_show.get("rule", "")
    leash = re.findall(r"travelling more than\s+(\d+(?:\.\d+)?)\s*m\b", rule)
    if len(leash) != 1:
        raise loader.LoaderError(
            "POL-NS-06's rule does not state the distance the driver may not "
            "exceed between intervals: found {0} such lines".format(len(leash))
        )

    listed = re.search(r"traffic_advisory\.type of\s+(.*?),\s*such that", rule, re.S)
    types = re.findall(r"\b[A-Z][A-Z_]{2,}\b", listed.group(1)) if listed else []
    if not types:
        raise loader.LoaderError(
            "POL-NS-06's rule does not state the admissible traffic_advisory.type "
            "values, so limb (i) cannot be tested without retyping them"
        )

    motion_rule = clauses.get(POL_NS_05, {}).get("rule", "")
    motion = re.findall(r"travelling at\s+(\d+(?:\.\d+)?)\s*km/h or above", motion_rule)
    if len(motion) != 1:
        raise loader.LoaderError(
            "POL-NS-05's rule does not state the speed at which the driver is in "
            "motion rather than holding position: found {0} such lines".format(len(motion))
        )

    return {
        "leash_m": float(leash[0]),
        "admissible_types": types,
        "motion_speed_kph": float(motion[0]),
    }


def _limb_reasons(
    result: Dict[str, Any],
    thresholds: Dict[str, Any],
    missing_ids: List[str],
) -> List[Dict[str, str]]:
    """One prose reason per failed POL-NS-06(i) condition, in a stable order.

    The conditions are conjunctive, so a case can fail several at once and all
    of them are stated. A judge told only the first may spend its argument on a
    condition the other side concedes, when a different one decides the limb.
    """
    reasons: List[Dict[str, str]] = []

    for condition in result["unavailable_reasons"]:
        if condition == facts.NO_SECOND_INTERVAL:
            text = NO_SECOND_INTERVAL_REASON.format(result["run_count"])
        elif condition == facts.EXCURSION_UNMEASURABLE:
            text = EXCURSION_UNMEASURABLE_REASON
        elif condition == facts.EXCURSION_BEYOND_LEASH:
            text = EXCURSION_BEYOND_LEASH_REASON.format(
                round(result["max_excursion_m"], 1), thresholds["leash_m"]
            )
        elif condition == facts.ADVISORY_MISSING:
            text = ADVISORY_MISSING_REASON.format(
                " and ".join(missing_ids) if missing_ids else "the traffic_advisory"
            )
        elif condition == facts.ADVISORY_TYPE_NOT_ADMISSIBLE:
            text = ADVISORY_TYPE_NOT_ADMISSIBLE_REASON.format(
                ", ".join(thresholds["admissible_types"])
            )
        elif condition == facts.ADVISORY_ROUTE_NOT_COVERED:
            text = ADVISORY_ROUTE_NOT_COVERED_REASON
        else:
            text = ADVISORY_WINDOW_NOT_COVERED_REASON
        reasons.append({"condition": condition, "reason": text})

    return reasons


def _accumulated_dwell_block(
    gps_payload: Dict[str, Any],
    driver: List[Dict[str, Any]],
    lat: float,
    lng: float,
    arrival_radius: float,
    accuracy_max: float,
    minimum_dwell: float,
    zone: str,
    thresholds: Dict[str, Any],
    advisories: Optional[List[Dict[str, Any]]],
    policy_id: str,
    gps_evidence_id: str,
) -> Dict[str, Any]:
    """POL-NS-06(i): the separate holds, the excursions, and whether they may be summed.

    Every derived value carries the ``evidence_id`` it came from and every
    threshold the ``policy_id`` and ``clause_id`` it came from, exactly as the
    derived facts around it do. Computing the accumulation without publishing
    it would leave case 214's defect exactly where it was: the model was given
    a 185 second hold against a 300 second minimum and never told that the
    clause permits 170 and 185 to be added.

    ``shortfall_sec`` is measured against the dwell the limb actually permits,
    and the basis it used is published beside it. Where limb (i) is available
    that is the accumulated figure; where it is not, the intervals may not be
    summed and it is the longest continuous run. Both dwell figures stay in the
    block either way, because an advocate may legitimately argue about whether
    the limb should have been available, and a refused sum is still worth
    showing. What must not happen is the shortfall being quoted off a basis the
    policy disallows.
    """
    result = facts.accumulated_dwell(
        driver,
        lat,
        lng,
        arrival_radius,
        accuracy_max,
        thresholds["motion_speed_kph"],
        thresholds["leash_m"],
        thresholds["admissible_types"],
        advisories=advisories,
        gaps=gps_payload.get("gaps"),
    )

    missing_ids = [
        advisory.get("evidence_id")
        for advisory in advisories or []
        if not isinstance(advisory.get("payload"), dict) or not advisory.get("payload")
    ]

    if result["available"]:
        basis = BASIS_ACCUMULATED
        operative_dwell = result["accumulated_sec"]
    else:
        basis = BASIS_LONGEST_RUN
        operative_dwell = result["longest_run_sec"]

    block: Dict[str, Any] = {
        "accumulated_sec": _sourced(result["accumulated_sec"], gps_evidence_id),
        "longest_run_sec": _sourced(result["longest_run_sec"], gps_evidence_id),
        "run_count": _sourced(result["run_count"], gps_evidence_id),
        "shortfall_sec": _sourced(minimum_dwell - operative_dwell, gps_evidence_id),
        SHORTFALL_BASIS_KEY: _sourced(basis, gps_evidence_id),
        "max_excursion_m": _sourced(result["max_excursion_m"], gps_evidence_id),
        "runs": [
            {
                "first_ts": _sourced(run["first_ts"], gps_evidence_id),
                "last_ts": _sourced(run["last_ts"], gps_evidence_id),
                "fix_count": _sourced(run["fix_count"], gps_evidence_id),
                "duration_sec": _sourced(run["duration_sec"], gps_evidence_id),
            }
            for run in result["runs"]
        ],
        "excursions": [
            {
                "from_ts": _sourced(span["from_ts"], gps_evidence_id),
                "to_ts": _sourced(span["to_ts"], gps_evidence_id),
                "fix_count": _sourced(span["fix_count"], gps_evidence_id),
                "max_distance_m": _sourced(span["max_distance_m"], gps_evidence_id),
                "gap_in_interval": _sourced(span["gap_in_interval"], gps_evidence_id),
            }
            for span in result["excursions"]
        ],
        "advisory_candidates": [
            {
                "evidence_id": candidate["evidence_id"],
                "type": _sourced(candidate["type"], candidate["evidence_id"] or ""),
                "failed_conditions": candidate["failed_conditions"],
            }
            for candidate in result["advisory_candidates"]
        ],
        "thresholds": {
            "leash_m": _clause_threshold(thresholds["leash_m"], policy_id, POL_NS_06),
            "admissible_advisory_types": _clause_threshold(
                thresholds["admissible_types"], policy_id, POL_NS_06
            ),
            "motion_speed_kph": _clause_threshold(
                thresholds["motion_speed_kph"], policy_id, POL_NS_05
            ),
            "minimum_dwell_sec": _threshold(minimum_dwell, policy_id, zone),
        },
    }

    if result["available"]:
        qualifying = next(
            candidate
            for candidate in result["advisory_candidates"]
            if not candidate["failed_conditions"]
        )
        block[LIMB_KEY] = {
            "limb": "i",
            "available": True,
            "policy_id": policy_id,
            "clause_id": POL_NS_06,
            "reason": LIMB_AVAILABLE_REASON.format(
                qualifying["evidence_id"],
                qualifying["type"],
                round(result["max_excursion_m"], 1),
                thresholds["leash_m"],
            ),
        }
    else:
        block[LIMB_KEY] = {
            "limb": "i",
            "available": False,
            "policy_id": policy_id,
            "clause_id": POL_NS_06,
            "unavailable": _limb_reasons(result, thresholds, missing_ids),
        }

    return block


def _deviation_block(
    gps_payload: Dict[str, Any],
    gps_evidence_id: str,
    trip_payload: Optional[Dict[str, Any]],
    trip_evidence_id: Optional[str],
    thresholds: Dict[str, float],
    policy_id: str,
) -> Dict[str, Any]:
    """The POL-RD-01 excess and status, every value tagged with its source."""
    trace_km = gps_payload.get("trace_distance_km")
    optimal_km = trip_payload.get("optimal_distance_km") if isinstance(trip_payload, dict) else None

    block: Dict[str, Any] = {
        "trace_distance_km": _sourced(trace_km, gps_evidence_id),
        "optimal_distance_km": _sourced(optimal_km, trip_evidence_id or ""),
    }

    if trace_km is None or optimal_km is None or optimal_km <= 0:
        block["available"] = False
        block["reason"] = NO_DEVIATION_INPUTS_REASON
        return block

    excess_km, excess_pct = facts.deviation_excess(trace_km, optimal_km)
    status = facts.deviation_status(excess_km, excess_pct, **thresholds)

    block["available"] = True
    block["excess_km"] = _sourced(excess_km, gps_evidence_id)
    block["excess_pct"] = _sourced(excess_pct, gps_evidence_id)
    block["status"] = _sourced(status, gps_evidence_id)
    block["thresholds"] = {
        name: _clause_threshold(value, policy_id, POL_RD_01)
        for name, value in sorted(thresholds.items())
    }
    return block


def _track_block(
    points: List[Dict[str, Any]],
    lat: Optional[float],
    lng: Optional[float],
    evidence_id: str,
) -> Dict[str, Any]:
    """A distance/speed summary of one track, every value tagged with its source."""
    if lat is None or lng is None:
        return {
            "fix_count": _sourced(len(points), evidence_id),
            "min_distance_m": _sourced(None, evidence_id),
            "max_distance_m": _sourced(None, evidence_id),
            "mean_distance_m": _sourced(None, evidence_id),
            "distinct_speeds_kph": _sourced(
                sorted({p["speed_kph"] for p in points if p.get("speed_kph") is not None}),
                evidence_id,
            ),
            "first_ts": _sourced(points[0].get("ts") if points else None, evidence_id),
            "last_ts": _sourced(points[-1].get("ts") if points else None, evidence_id),
            "distance_unavailable_reason": NO_PICKUP_REASON,
        }

    summary = facts.track_summary(points, lat, lng)
    return {
        "fix_count": _sourced(summary["fix_count"], evidence_id),
        "min_distance_m": _sourced(summary["min_distance_m"], evidence_id),
        "max_distance_m": _sourced(summary["max_distance_m"], evidence_id),
        "mean_distance_m": _sourced(summary["mean_distance_m"], evidence_id),
        "distinct_speeds_kph": _sourced(summary["distinct_speeds_kph"], evidence_id),
        "first_ts": _sourced(summary["first_ts"], evidence_id),
        "last_ts": _sourced(summary["last_ts"], evidence_id),
    }


def _rider_block(
    gps_payload: Dict[str, Any],
    lat: Optional[float],
    lng: Optional[float],
    evidence_id: str,
) -> Dict[str, Any]:
    """The rider track summary, or an explicit statement that there is none."""
    rider = facts.rider_points(gps_payload)
    if not rider:
        return {
            "available": False,
            "reason": NO_RIDER_TRACK_REASON,
            "fix_count": _sourced(0, evidence_id),
        }
    block = _track_block(rider, lat, lng, evidence_id)
    block["available"] = True
    return block


def _arrival_block(
    gps_payload: Dict[str, Any],
    gps_evidence_id: str,
    trip_payload: Optional[Dict[str, Any]],
    trip_evidence_id: Optional[str],
    fee_schedule: Dict[str, Any],
    policy_id: str,
    no_show_thresholds: Optional[Dict[str, Any]] = None,
    advisories: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """The zone-dependent no-show facts, or an explicit statement of why not.

    Where ``pickup_zone_class`` is null the zone-dependent facts cannot be
    computed. They are omitted and the brief says so; no default zone is
    substituted and nothing is guessed.

    Where the loaded policy carries a POL-NS-06 clause, the block also carries
    the accumulated-dwell facts, which are what decide a shortfall case where
    the driver left the radius and came back.
    """
    if not isinstance(trip_payload, dict):
        return {
            "available": False,
            "reason": "trip_record payload is absent, so the pickup point and zone class are unknown",
            "pickup_zone_class": _sourced(None, trip_evidence_id or ""),
        }

    zone = trip_payload.get("pickup_zone_class")
    pickup = trip_payload.get("pickup")
    block: Dict[str, Any] = {"pickup_zone_class": _sourced(zone, trip_evidence_id or "")}

    if zone is None:
        block["available"] = False
        block["reason"] = NO_ZONE_REASON
        return block

    if not isinstance(pickup, dict) or pickup.get("lat") is None or pickup.get("lng") is None:
        block["available"] = False
        block["reason"] = NO_PICKUP_REASON
        return block

    lat, lng = pickup["lat"], pickup["lng"]

    arrival_radius = (fee_schedule.get("arrival_radius_m") or {}).get(zone)
    rider_radius = (fee_schedule.get("rider_presence_radius_m") or {}).get(zone)
    dwell_seconds = (fee_schedule.get("minimum_dwell_sec") or {}).get(zone)
    accuracy_max = fee_schedule.get("gps_accuracy_filter_m")

    if None in (arrival_radius, rider_radius, dwell_seconds, accuracy_max):
        block["available"] = False
        block["reason"] = INCOMPLETE_POLICY_REASON
        return block

    driver = facts.driver_points(gps_payload)
    rider = facts.rider_points(gps_payload)

    run = facts.longest_qualifying_run(driver, lat, lng, arrival_radius, accuracy_max)
    arrived_at = trip_payload.get("arrived_at")

    block["available"] = True
    block["thresholds"] = {
        "arrival_radius_m": _threshold(arrival_radius, policy_id, zone),
        "rider_presence_radius_m": _threshold(rider_radius, policy_id, zone),
        "minimum_dwell_sec": _threshold(dwell_seconds, policy_id, zone),
        "gps_accuracy_filter_m": _threshold(accuracy_max, policy_id, None),
    }
    block["driver_fix_count"] = _sourced(len(driver), gps_evidence_id)
    block["qualifying_fix_count"] = _sourced(
        len(facts.qualifying_fixes(driver, lat, lng, arrival_radius, accuracy_max)), gps_evidence_id
    )
    block["longest_qualifying_run"] = {
        "fix_count": _sourced(run["fix_count"], gps_evidence_id),
        "first_ts": _sourced(run["first_ts"], gps_evidence_id),
        "last_ts": _sourced(run["last_ts"], gps_evidence_id),
        "duration_sec": _sourced(run["duration_sec"], gps_evidence_id),
    }
    if no_show_thresholds:
        block[ACCUMULATED_DWELL_KEY] = _accumulated_dwell_block(
            gps_payload,
            driver,
            lat,
            lng,
            arrival_radius,
            accuracy_max,
            dwell_seconds,
            zone,
            no_show_thresholds,
            advisories,
            policy_id,
            gps_evidence_id,
        )
    block["arrived_at"] = _sourced(arrived_at, trip_evidence_id or "")
    block["dwell_start_offset_sec"] = _sourced(
        facts.elapsed_seconds(run["first_ts"], arrived_at) if run["first_ts"] else None,
        gps_evidence_id,
    )
    block["rider_fix_count"] = _sourced(len(rider), gps_evidence_id)
    block["rider_qualifying_fix_count"] = _sourced(
        len(facts.qualifying_fixes(rider, lat, lng, rider_radius, accuracy_max)), gps_evidence_id
    )
    return block


def _gantry_proximity_line(
    record: Dict[str, Any],
    gps_evidence_id: str,
    fare_evidence_id: str,
) -> Dict[str, Any]:
    """One ERP line's proximity record, every value tagged with its source.

    The line's own fields come from the fare breakdown and the distances come
    from the trace, so both evidence ids appear in the one record: an advocate
    has to be able to cite the artifact behind each figure it quotes.
    """
    line: Dict[str, Any] = {
        "gantry_name": record["gantry_name"],
        "amount_sgd": _sourced(record["amount_sgd"], fare_evidence_id),
        "charged_at": _sourced(record["charged_at"], fare_evidence_id),
        "on_optimal_route": _sourced(record["on_optimal_route"], fare_evidence_id),
        "coordinates": _sourced(record["coordinates"], fare_evidence_id),
    }

    if record["coordinates"] is None:
        line["available"] = False
        line["reason"] = NO_GANTRY_COORDINATES_REASON
        return line

    if record["nearest_fix"] is None:
        line["available"] = False
        line["reason"] = NO_TRACE_FIXES_REASON
        return line

    line["available"] = True
    line["nearest_fix"] = {
        "index": _sourced(record["nearest_fix"]["index"], gps_evidence_id),
        "ts": _sourced(record["nearest_fix"]["ts"], gps_evidence_id),
        "distance_m": _sourced(record["nearest_fix"]["distance_m"], gps_evidence_id),
    }
    line["gap_brackets_closest_approach"] = _sourced(
        record["gap_brackets_closest_approach"], gps_evidence_id
    )
    line["across_gap_distance_m"] = _sourced(record["across_gap_distance_m"], gps_evidence_id)
    line["bracketing_gaps"] = [
        {
            "from_ts": _sourced(gap["from_ts"], gps_evidence_id),
            "to_ts": _sourced(gap["to_ts"], gps_evidence_id),
            "duration_sec": _sourced(gap["duration_sec"], gps_evidence_id),
            "distance_m": _sourced(gap["distance_m"], gps_evidence_id),
        }
        for gap in record["bracketing_gaps"]
    ]
    return line


def _gantry_proximity_block(
    gps_payload: Dict[str, Any],
    gps_evidence_id: str,
    gantry_lines: Any,
    fare_evidence_id: str,
    policy_id: str,
) -> Dict[str, Any]:
    """POL-RD-09(4): how close the trace came to each ERP gantry line.

    The clause matches a gantry to the trace by comparing coordinates, and this
    module replaces the trace's coordinates with derived facts. Without this
    block the judge holds the gantry's coordinates and no way to measure them
    against the trace, which is how case 9111's judge came to assert a crossing
    the record could not show. Nothing here decides a match: the clause's
    radius is the clause's, and the block reports distances.
    """
    records = facts.gantry_proximity(
        facts.driver_points(gps_payload),
        gantry_lines,
        gps_payload.get("gaps"),
    )
    return {
        "policy_id": policy_id,
        "clause_id": POL_RD_09,
        "lines": [
            _gantry_proximity_line(record, gps_evidence_id, fare_evidence_id)
            for record in records
        ],
    }


# --------------------------------------------------------------------------
# The money block
#
# The first principle is that money comes from a calculator, not from the
# model. ``tribunal.money`` does the arithmetic; this block publishes what it
# computed so the judge reasons about figures instead of producing them, the
# same way the dwell and gantry facts are published. It is attached to the
# **fare breakdown**, the artifact the money was charged on, as the derived
# geometry is attached to the trace.
#
# The block computes figures. It does not decide which clause applies: whether
# a deviation is established, whether a refund is ordered, whether an
# exoneration caps it and whether a pass-through correction is due all remain
# the judge's. Every figure carries the artifact it was read from and the
# policy it was computed under, so the judge can cite it.
#
# No policy number is a literal here. The fare constants come from the loaded
# policy's ``fare_model``, the no-show fees from its ``fee_schedule``, and the
# two figures the policy states only in prose -- POL-RD-02's full-refund share
# and POL-RD-03's cap ratio and tolerance -- are read out of the loaded clause
# text, the route ``_deviation_thresholds`` already takes for POL-RD-01.
# --------------------------------------------------------------------------

MONEY_KEY = "money"
POL_RD_02 = "POL-RD-02"
POL_RD_03 = "POL-RD-03"
POL_RD_04 = "POL-RD-04"
POL_RD_10 = "POL-RD-10"
POL_RD_11 = "POL-RD-11"
POL_NS_01 = "POL-NS-01"
POL_NS_03 = "POL-NS-03"
POL_NS_07 = "POL-NS-07"

METERED_MODEL = "METERED"
UPFRONT_QUOTE_MODEL = "UPFRONT_QUOTE"

# The clause-prose constants the money arithmetic needs, named as the keys
# ``_money_prose_constants`` returns them.
FULL_REFUND_SHARE = "full_refund_share"
CAP_RATIO = "cap_ratio"
TOLERANCE_KM = "tolerance_km"

NO_FARE_MODEL_REASON = (
    "the fare breakdown carries no recognised fare_model, so whether POL-RD-02 or POL-RD-11 "
    "governs is unknown and neither the metered recomputation nor the quote comparison was run"
)
NO_OPTIMAL_ROUTE_REASON = (
    "trip_record.optimal_distance_km or optimal_duration_min is absent, so the POL-RD-02 "
    "recomputation has no booked route to run against and was not run"
)
NO_FEE_SCHEDULE_REASON = (
    "the trip's pickup_zone_class or vehicle_type is absent from the loaded fee_schedule, so "
    "the chargeable no-show fee cannot be selected; no fee was substituted"
)
UPFRONT_QUOTE_NOTE = (
    "this is an UPFRONT_QUOTE trip: POL-RD-02 does not run and no distance-or-time refund is "
    "computed. What is published is the quoted fare against the charged total and the ERP lines"
)

# Prose-only policy figures the money arithmetic could reach for and this module
# deliberately does not compute with, each named with the clause that states it.
# Saying so is the point: a figure the policy states only in prose is not a
# structured field, so the calculator computes nothing for it and the judge is
# told why it is missing.
NOT_STRUCTURED_MONEY = (
    {
        "clause_id": POL_RD_04,
        "figure": "driver_compensation_per_unbilled_km",
        "note": "POL-RD-04 states the per-kilometre driver compensation and its cap only in prose: "
                "the rate is not a structured field and neither is the cap, so no compensation is "
                "computed here",
    },
    {
        "clause_id": POL_RD_09,
        "figure": "off_route_erp_refund_cap",
        "note": "POL-RD-09(2) states the off-route ERP pass-through cap only in prose: the cap is "
                "not a structured field, so no cap is applied to the ERP totals published here",
    },
    {
        "clause_id": POL_RD_09,
        "figure": "gantry_match_radius_m",
        "note": "POL-RD-09(4) states the gantry match radius only in prose: the radius is not a "
                "structured field, so the ERP figures report amounts and distances and decide no "
                "match",
    },
    {
        "clause_id": POL_RD_10,
        "figure": "escalation_refund_ceiling",
        "note": "POL-RD-10(6) states the escalation ceiling only in prose: the ceiling is not a "
                "structured field, so no escalation is tested here",
    },
)


def _money(
    value: Any,
    evidence_id: Optional[str],
    policy_id: str,
    clause_id: Optional[str] = None,
    structured: Optional[bool] = None,
) -> Dict[str, Any]:
    """One money figure, tagged with the artifact it came from and its policy.

    Every figure carries its source so an advocate can cite what it is reading.
    A figure read from an artifact carries that artifact's ``evidence_id``; a
    policy constant carries the ``policy_id`` and, where it is a value the
    clause states only in prose, the ``clause_id`` and ``structured: false``.
    """
    figure: Dict[str, Any] = {"value": value, "evidence_id": evidence_id, "policy_id": policy_id}
    if clause_id is not None:
        figure["clause_id"] = clause_id
    if structured is not None:
        figure["structured"] = structured
    return figure


def _money_prose_constants(policy: Dict[str, Any]) -> Dict[str, Any]:
    """POL-RD-02's full-refund share and POL-RD-03's cap, read from clause prose.

    Three values this policy carries as **prose** and nowhere as a field,
    verified against ``policy/route_deviation.json``:

    * the share of ``charged_total`` at which POL-RD-02 orders a full refund
      instead of a partial, from "90% or more of charged_total";
    * POL-RD-03's cap ratio, from "130% of the ADDITIONAL distance of the
      shortest lawful alternative over the booked optimal route";
    * POL-RD-03's tolerance, from "plus 1.0 km of tolerance".

    They are read out of the loaded clause's own ``rule`` string, which is the
    route ``_deviation_thresholds`` already takes for POL-RD-01 and for the
    same reason: a value that came from a clause belongs in the loaded policy,
    and a literal here would be a policy number hard-coded in ``tribunal/``.
    Where a line cannot be found this raises rather than falling back.
    """
    clauses = {
        clause.get("id"): clause
        for clause in policy.get("clauses", []) or []
        if isinstance(clause, dict)
    }
    rule02 = clauses.get(POL_RD_02, {}).get("rule", "")
    rule03 = clauses.get(POL_RD_03, {}).get("rule", "")

    share = re.findall(r"(\d+(?:\.\d+)?)%\s+or more of charged_total", rule02)
    ratio = re.findall(r"(\d+(?:\.\d+)?)%\s+of the ADDITIONAL distance", rule03)
    tolerance = re.findall(r"plus\s+(\d+(?:\.\d+)?)\s*km of tolerance", rule03)

    if len(share) != 1 or len(ratio) != 1 or len(tolerance) != 1:
        raise loader.LoaderError(
            "the money arithmetic needs POL-RD-02's full-refund share and POL-RD-03's cap "
            "ratio and tolerance, which this policy states only in prose: found {0}, {1} and "
            "{2} such lines".format(len(share), len(ratio), len(tolerance))
        )
    return {
        FULL_REFUND_SHARE: money._dec(share[0]) / facts.PERCENT,
        CAP_RATIO: money._dec(ratio[0]) / facts.PERCENT,
        TOLERANCE_KM: money._dec(tolerance[0]),
    }


def _proximity_figure(node: Dict[str, Any], policy_id: str) -> Dict[str, Any]:
    """One of the trace's proximity figures, in this block's own shape.

    The value and the ``evidence_id`` are the trace's own, taken from the node
    the trace published; the ``policy_id`` is added because every figure in the
    money block carries the policy it is published under, and an advocate
    quoting this one has to be able to cite both.
    """
    return _money(node["value"], node["evidence_id"], policy_id)


def _proximity_figures(
    record: Optional[Dict[str, Any]], policy_id: str
) -> Optional[Dict[str, Any]]:
    """One ERP line's proximity, read out of the trace's own record.

    The trace publishes how close it came to each gantry under
    ``erp_gantry_proximity``; this carries the same figures beside the line's
    amount, so that the money a line was charged at and the geometry POL-RD-09(4)
    decides its match on are readable together instead of in two artifacts.

    Nothing is recomputed here -- every value is the trace's -- and
    ``tests/test_brief.py`` holds them equal to the trace's record line for line.
    ``None`` where the trace published no record for the line at all, and
    ``available: false`` with the trace's own reason where the record carries no
    geometry, so "no coordinates" stays distinguishable from "no trace".
    """
    if not isinstance(record, dict):
        return None
    if not record.get("available"):
        return {"available": False, "reason": record.get("reason")}

    nearest = record["nearest_fix"]
    return {
        "available": True,
        "nearest_fix": {
            "index": _proximity_figure(nearest["index"], policy_id),
            "ts": _proximity_figure(nearest["ts"], policy_id),
            "distance_m": _proximity_figure(nearest["distance_m"], policy_id),
        },
        "gap_brackets_closest_approach": _proximity_figure(
            record["gap_brackets_closest_approach"], policy_id
        ),
        "across_gap_distance_m": _proximity_figure(
            record["across_gap_distance_m"], policy_id
        ),
    }


def _erp_lines(
    fare_payload: Dict[str, Any],
    fare_evidence_id: str,
    policy_id: str,
    proximity: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """The fare's ERP lines itemised, with each amount beside its route flag.

    POL-RD-02 adds only the gantries lying on the optimal route, so the total
    that enters the recomputation is the on-optimal one and the off-optimal
    lines are totalled separately: they are the pass-through POL-RD-09 speaks
    to, and a ruling that must not count them twice still has to name them.

    ``proximity`` is the trace's own per-line record -- how close the trace came
    to each gantry -- carried here so that a line's **amount** and the geometry
    POL-RD-09(4) decides the match on sit in one place, instead of a reader
    having to join the fare breakdown to the trace to find out whether a charged
    line was ever passed. It is read out of the trace's record and never
    recomputed, and ``tests/test_brief.py`` holds the two equal figure for
    figure. A line the trace published no record for carries ``None`` rather
    than an absent key, so "no geometry" is distinguishable from "this code
    forgot to carry it".
    """
    itemised = money.erp_lines(fare_payload.get("erp_gantries"))
    records = list(proximity or [])
    return {
        "policy_id": policy_id,
        "clause_id": POL_RD_09,
        "lines": [
            {
                "gantry_name": line["gantry_name"],
                "amount_sgd": _money(
                    money.payable_string(line["amount_sgd"]), fare_evidence_id, policy_id
                ),
                "on_optimal_route": _money(line["on_optimal_route"], fare_evidence_id, policy_id),
                "trace_proximity": _proximity_figures(
                    records[index] if index < len(records) else None, policy_id
                ),
            }
            for index, line in enumerate(itemised["lines"])
        ],
        "on_optimal_route_total": _money(
            money.payable_string(itemised["on_optimal_route_total"]), fare_evidence_id, policy_id
        ),
        "off_optimal_route_total": _money(
            money.payable_string(itemised["off_optimal_route_total"]), fare_evidence_id, policy_id
        ),
        "total": _money(money.payable_string(itemised["total"]), fare_evidence_id, policy_id),
    }


def _metered_components(
    fare_payload: Dict[str, Any],
    constants: Dict[str, Any],
    optimal_distance: Any,
    optimal_duration: Any,
    on_optimal_erp: Any,
) -> Dict[str, Any]:
    """POL-RD-02's recomputation for one optimal route, itemised by ``money``."""
    return money.metered_fare_components(
        base_fare=constants.get("base_fare"),
        per_km=constants.get("per_km"),
        per_min=constants.get("per_min"),
        optimal_distance_km=optimal_distance,
        optimal_duration_min=optimal_duration,
        surge_multiplier=fare_payload.get("surge_multiplier"),
        platform_fee=constants.get("platform_fee"),
        optimal_route_erp=on_optimal_erp,
        fixed_surcharges=fare_payload.get("airport_surcharge"),
        waiting_time_fee=fare_payload.get("waiting_time_fee"),
        promo_discount=fare_payload.get("promo_discount"),
    )


def _refund_figures(
    charged_total: Any,
    recomputed_fare: Any,
    de_minimis: Any,
    full_refund_share: Any,
    evidence_id: str,
    policy_id: str,
) -> Dict[str, Any]:
    """POL-RD-02's refund, with every intermediate the ruling must state."""
    working = money.refund_working(charged_total, recomputed_fare, de_minimis)
    share = working["refund_share_of_charged"]
    reaches = None if share is None else share >= money._dec(full_refund_share)
    return {
        "refund_before_rounding": _money(working["refund_before_rounding"], evidence_id, policy_id),
        "de_minimis": _money(working["de_minimis"], evidence_id, policy_id),
        "below_de_minimis": _money(working["below_de_minimis"], evidence_id, policy_id),
        "refund_share_of_charged": _money(share, evidence_id, policy_id),
        "full_refund_share": _money(full_refund_share, evidence_id, policy_id),
        "reaches_full_refund_share": _money(reaches, evidence_id, policy_id),
        "quantum": _money(working["quantum"], evidence_id, policy_id),
        "payable": _money(money.payable_string(working["payable"]), evidence_id, policy_id),
        "full_refund": _money(money.payable_string(working["full_refund"]), evidence_id, policy_id),
    }


def _closure_figures(
    fare_payload: Dict[str, Any],
    fare_evidence_id: str,
    trip_payload: Dict[str, Any],
    trip_evidence_id: Optional[str],
    gps_payload: Dict[str, Any],
    gps_evidence_id: Optional[str],
    advisories: List[Dict[str, Any]],
    constants: Dict[str, Any],
    prose: Dict[str, Any],
    policy_id: str,
) -> List[Dict[str, Any]]:
    """POL-RD-03: the cap and the closure-adjusted route, per populated advisory.

    POL-RD-03 writes its cap and its duration derivation out in full "because
    the Judge cannot reproduce the adjusted optimal without them and must not
    invent one", so the figures are computed here. The block does not decide
    whether an advisory exonerates: it reports the advisory's own coverage
    flags and the arithmetic, and the judge applies the clause.

    Only an advisory that is present and populated with a shortest lawful
    alternative is computed against; the measured excess is POL-RD-01's own
    excess, so it is read from the same fields the deviation block reads.
    """
    trace = gps_payload.get("trace_distance_km") if isinstance(gps_payload, dict) else None
    optimal = trip_payload.get("optimal_distance_km")
    if trace is None or optimal is None or money._dec(optimal) <= 0:
        return []

    measured = money._dec(trace) - money._dec(optimal)
    figures: List[Dict[str, Any]] = []
    for advisory in advisories:
        payload = advisory.get("payload")
        if not isinstance(payload, dict) or payload.get("shortest_lawful_alternative_km") is None:
            continue

        cap = money.justified_excess(
            measured,
            payload["shortest_lawful_alternative_km"],
            optimal,
            prose[CAP_RATIO],
            prose[TOLERANCE_KM],
        )
        route = money.closure_adjusted_route(
            optimal,
            trip_payload.get("optimal_duration_min"),
            cap["justified_excess_km"],
            trip_payload.get("amended_optimal_duration_min"),
        )
        on_optimal_erp = money.erp_lines(fare_payload.get("erp_gantries"))[
            "on_optimal_route_total"
        ]
        recomputed = _metered_components(
            fare_payload,
            constants,
            route["adjusted_optimal_distance_km"],
            route["adjusted_optimal_duration_min"],
            on_optimal_erp,
        )
        figures.append(
            {
                "evidence_id": advisory["evidence_id"],
                "road_name": _money(payload.get("road_name"), advisory["evidence_id"], policy_id),
                "type": _money(payload.get("type"), advisory["evidence_id"], policy_id),
                "intersects_route": _money(
                    payload.get("intersects_route"), advisory["evidence_id"], policy_id
                ),
                "overlaps_trip_window": _money(
                    payload.get("overlaps_trip_window"), advisory["evidence_id"], policy_id
                ),
                "shortest_lawful_alternative_km": _money(
                    payload["shortest_lawful_alternative_km"], advisory["evidence_id"], policy_id
                ),
                "measured_excess_km": _money(measured, gps_evidence_id or "", policy_id),
                "additional_distance_km": _money(
                    cap["additional_distance_km"], advisory["evidence_id"], policy_id
                ),
                "cap_ratio": _money(
                    prose[CAP_RATIO], None, policy_id, clause_id=POL_RD_03, structured=False
                ),
                "tolerance_km": _money(
                    prose[TOLERANCE_KM], None, policy_id, clause_id=POL_RD_03, structured=False
                ),
                "cap_km": _money(cap["cap_km"], advisory["evidence_id"], policy_id),
                "justified_excess_km": _money(
                    cap["justified_excess_km"], advisory["evidence_id"], policy_id
                ),
                "adjusted_optimal_distance_km": _money(
                    route["adjusted_optimal_distance_km"], trip_evidence_id or "", policy_id
                ),
                "adjusted_optimal_duration_min": _money(
                    route["adjusted_optimal_duration_min"], trip_evidence_id or "", policy_id
                ),
                "duration_source": _money(route["duration_source"], trip_evidence_id or "", policy_id),
                "recomputed_fare": _money(
                    recomputed["recomputed_fare"], fare_evidence_id, policy_id
                ),
                "refund": _refund_figures(
                    fare_payload.get("total_charged"),
                    recomputed["recomputed_fare"],
                    constants.get("de_minimis_refund"),
                    prose[FULL_REFUND_SHARE],
                    fare_evidence_id,
                    policy_id,
                ),
            }
        )
    return figures


def _route_deviation_money(
    fare_payload: Dict[str, Any],
    fare_evidence_id: str,
    trip_payload: Optional[Dict[str, Any]],
    trip_evidence_id: Optional[str],
    gps_payload: Optional[Dict[str, Any]],
    gps_evidence_id: Optional[str],
    advisories: List[Dict[str, Any]],
    policy: Dict[str, Any],
    policy_id: str,
    prose: Dict[str, Any],
) -> Dict[str, Any]:
    """The money arithmetic for a ROUTE_DEVIATION case, itemised."""
    trip = trip_payload if isinstance(trip_payload, dict) else {}
    constants = policy.get("fare_model") or {}
    fare_model = fare_payload.get("fare_model")
    charged_total = fare_payload.get("total_charged")
    erp = money.erp_lines(fare_payload.get("erp_gantries"))

    # The trace's own proximity records, read from the trace's published block
    # rather than recomputed, so that each ERP line's amount can be published
    # beside the geometry POL-RD-09(4) decides its match on. The trace payload
    # arrives already transformed, which is what puts the block there; a trace
    # with no published block leaves the lines carrying ``None``.
    proximity = None
    if isinstance(gps_payload, dict):
        trace_derived = gps_payload.get(DERIVED_KEY) or {}
        proximity = (trace_derived.get(ERP_GANTRY_PROXIMITY_KEY) or {}).get("lines")

    block: Dict[str, Any] = {
        "policy_id": policy_id,
        "category": ROUTE_DEVIATION_CATEGORY,
        "currency": _money(fare_payload.get("currency"), fare_evidence_id, policy_id),
        "fare_model": _money(fare_model, fare_evidence_id, policy_id),
        "payment_status": _money(fare_payload.get("payment_status"), fare_evidence_id, policy_id),
        "charged_total": _money(money.payable_string(charged_total), fare_evidence_id, policy_id),
        "erp_lines": _erp_lines(fare_payload, fare_evidence_id, policy_id, proximity),
        "not_structured": list(NOT_STRUCTURED_MONEY),
    }

    if fare_model == UPFRONT_QUOTE_MODEL:
        comparison = money.upfront_quote_comparison(
            charged_total, fare_payload.get("quoted_fare_sgd")
        )
        block["available"] = True
        block["quoted_fare"] = _money(
            money.payable_string(comparison["quoted_fare"]), fare_evidence_id, policy_id
        )
        block["charged_over_quote"] = _money(
            money.payable_string(comparison["difference"]), fare_evidence_id, policy_id
        )
        block["note"] = UPFRONT_QUOTE_NOTE
        return block

    if fare_model != METERED_MODEL:
        block["available"] = False
        block["reason"] = NO_FARE_MODEL_REASON
        return block

    optimal_distance = trip.get("optimal_distance_km")
    optimal_duration = trip.get("optimal_duration_min")
    if optimal_distance is None or optimal_duration is None:
        block["available"] = False
        block["reason"] = NO_OPTIMAL_ROUTE_REASON
        return block

    components = _metered_components(
        fare_payload, constants, optimal_distance, optimal_duration, erp["on_optimal_route_total"]
    )
    block["available"] = True
    block["optimal_distance_km"] = _money(optimal_distance, trip_evidence_id or "", policy_id)
    block["optimal_duration_min"] = _money(optimal_duration, trip_evidence_id or "", policy_id)
    block["surge_multiplier"] = _money(
        fare_payload.get("surge_multiplier"), fare_evidence_id, policy_id
    )
    block["components"] = {
        name: _money(value, fare_evidence_id, policy_id) for name, value in components.items()
    }
    block["recomputed_fare"] = _money(components["recomputed_fare"], fare_evidence_id, policy_id)
    block["constants"] = {
        "base_fare": _money(constants.get("base_fare"), None, policy_id, structured=True),
        "per_km": _money(constants.get("per_km"), None, policy_id, structured=True),
        "per_min": _money(constants.get("per_min"), None, policy_id, structured=True),
        "platform_fee": _money(constants.get("platform_fee"), None, policy_id, structured=True),
        "de_minimis_refund": _money(
            constants.get("de_minimis_refund"), None, policy_id, structured=True
        ),
        FULL_REFUND_SHARE: _money(
            prose[FULL_REFUND_SHARE], None, policy_id, clause_id=POL_RD_02, structured=False
        ),
        CAP_RATIO: _money(prose[CAP_RATIO], None, policy_id, clause_id=POL_RD_03, structured=False),
        TOLERANCE_KM: _money(
            prose[TOLERANCE_KM], None, policy_id, clause_id=POL_RD_03, structured=False
        ),
    }
    block["refund"] = _refund_figures(
        charged_total,
        components["recomputed_fare"],
        constants.get("de_minimis_refund"),
        prose[FULL_REFUND_SHARE],
        fare_evidence_id,
        policy_id,
    )
    block["closure"] = _closure_figures(
        fare_payload,
        fare_evidence_id,
        trip,
        trip_evidence_id,
        gps_payload if isinstance(gps_payload, dict) else {},
        gps_evidence_id,
        advisories,
        constants,
        prose,
        policy_id,
    )
    return block


def _no_show_money(
    fare_payload: Dict[str, Any],
    fare_evidence_id: str,
    trip_payload: Optional[Dict[str, Any]],
    trip_evidence_id: Optional[str],
    fee_schedule: Dict[str, Any],
    policy_id: str,
) -> Dict[str, Any]:
    """POL-NS-01 and POL-NS-07: the no-show fee and the two payments on it."""
    trip = trip_payload if isinstance(trip_payload, dict) else {}
    zone = trip.get("pickup_zone_class")
    vehicle = trip.get("vehicle_type")
    zone_fee = (fee_schedule.get("zone_class_fee_sgd") or {}).get(zone)
    tier_fee = (fee_schedule.get("vehicle_tier_fee_sgd") or {}).get(vehicle)

    block: Dict[str, Any] = {
        "policy_id": policy_id,
        "category": "NO_SHOW_CHARGE",
        "currency": _money(fare_payload.get("currency"), fare_evidence_id, policy_id),
        "payment_status": _money(fare_payload.get("payment_status"), fare_evidence_id, policy_id),
        "pickup_zone_class": _money(zone, trip_evidence_id or "", policy_id),
        "vehicle_type": _money(vehicle, trip_evidence_id or "", policy_id),
        "not_structured": list(NOT_STRUCTURED_MONEY),
    }

    if zone_fee is None or tier_fee is None:
        block["available"] = False
        block["reason"] = NO_FEE_SCHEDULE_REASON
        return block

    amount, dimension = money.schedule_fee(zone_fee, tier_fee)
    arithmetic = money.fee_arithmetic(
        amount,
        fare_payload.get("cancellation_fee"),
        fee_schedule.get("driver_compensation_rate"),
        fee_schedule.get("pin_ambiguity_goodwill_rate"),
    )

    block["available"] = True
    block["schedule_fee"] = _money(money.payable_string(amount), None, policy_id, clause_id=POL_NS_01)
    block["schedule_fee_dimension"] = _money(dimension, None, policy_id, clause_id=POL_NS_01)
    block["fee_charged"] = _money(
        money.payable_string(arithmetic["fee_charged"]), fare_evidence_id, policy_id
    )
    block["difference"] = _money(
        money.payable_string(arithmetic["difference"]), fare_evidence_id, policy_id
    )
    block["driver_compensation"] = _money(
        money.payable_string(arithmetic["driver_compensation"]), fare_evidence_id, policy_id,
        clause_id=POL_NS_07,
    )
    block["goodwill"] = _money(
        money.payable_string(arithmetic["goodwill"]), fare_evidence_id, policy_id,
        clause_id=POL_NS_03,
    )
    block["constants"] = {
        "zone_class_fee": _money(zone_fee, None, policy_id, structured=True),
        "vehicle_tier_fee": _money(tier_fee, None, policy_id, structured=True),
        "driver_compensation_rate": _money(
            fee_schedule.get("driver_compensation_rate"), None, policy_id, structured=True
        ),
        "pin_ambiguity_goodwill_rate": _money(
            fee_schedule.get("pin_ambiguity_goodwill_rate"), None, policy_id, structured=True
        ),
    }
    return block


def _money_block(
    category: str,
    category_policy: Dict[str, Any],
    policy_id: str,
    fare_payload: Optional[Dict[str, Any]],
    fare_evidence_id: Optional[str],
    trip_payload: Optional[Dict[str, Any]],
    trip_evidence_id: Optional[str],
    gps_payload: Optional[Dict[str, Any]],
    gps_evidence_id: Optional[str],
    advisories: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """The money block for one case, or ``None`` where there is no fare to compute on."""
    if not isinstance(fare_payload, dict) or fare_evidence_id is None:
        return None
    if category == ROUTE_DEVIATION_CATEGORY:
        return _route_deviation_money(
            fare_payload,
            fare_evidence_id,
            trip_payload,
            trip_evidence_id,
            gps_payload,
            gps_evidence_id,
            advisories,
            category_policy,
            policy_id,
            _money_prose_constants(category_policy),
        )
    return _no_show_money(
        fare_payload,
        fare_evidence_id,
        trip_payload,
        trip_evidence_id,
        category_policy.get("fee_schedule") or {},
        policy_id,
    )


def _attach_derived(artifact: Dict[str, Any], key: str, block: Any) -> Dict[str, Any]:
    """Return a copy of ``artifact`` with ``block`` under ``payload.derived[key]``."""
    payload = dict(artifact.get("payload") or {})
    derived = dict(payload.get(DERIVED_KEY) or {})
    derived[key] = block
    payload[DERIVED_KEY] = derived
    new_artifact = dict(artifact)
    new_artifact["payload"] = payload
    return new_artifact


def _transform_gps_payload(
    artifact: Dict[str, Any],
    trip_payload: Optional[Dict[str, Any]],
    trip_evidence_id: Optional[str],
    fee_schedule: Dict[str, Any],
    policy_id: str,
    deviation_thresholds: Optional[Dict[str, float]] = None,
    no_show_thresholds: Optional[Dict[str, Any]] = None,
    advisories: Optional[List[Dict[str, Any]]] = None,
    gantry_lines: Any = None,
    fare_evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Replace one GPS payload's raw point arrays with derived facts."""
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        # A MISSING artifact keeps its evidence_id and admissibility; there is
        # nothing to derive from a payload that is not there.
        return artifact

    evidence_id = artifact["evidence_id"]
    pickup = trip_payload.get("pickup") if isinstance(trip_payload, dict) else None
    if isinstance(pickup, dict) and pickup.get("lat") is not None:
        lat, lng = pickup["lat"], pickup["lng"]
    else:
        lat = lng = None

    transformed = {field: payload[field] for field in GPS_SUMMARY_FIELDS if field in payload}
    derived = {
        DRIVER_BLOCK: _track_block(facts.driver_points(payload), lat, lng, evidence_id),
        RIDER_BLOCK: _rider_block(payload, lat, lng, evidence_id),
        ARRIVAL_BLOCK: _arrival_block(
            payload,
            evidence_id,
            trip_payload,
            trip_evidence_id,
            fee_schedule,
            policy_id,
            no_show_thresholds,
            advisories,
        ),
    }
    if deviation_thresholds:
        derived[DEVIATION_BLOCK] = _deviation_block(
            payload, evidence_id, trip_payload, trip_evidence_id, deviation_thresholds, policy_id
        )
    if gantry_lines:
        derived[ERP_GANTRY_PROXIMITY_KEY] = _gantry_proximity_block(
            payload, evidence_id, gantry_lines, fare_evidence_id or "", policy_id
        )
    transformed[DERIVED_KEY] = derived

    new_artifact = dict(artifact)
    new_artifact["payload"] = transformed
    return new_artifact


def _assert_no_forbidden_keys(node: Any, where: str = "brief") -> None:
    """Recursively reject the contract's evaluation-only keys."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_KEYS:
                raise loader.ForbiddenKeyError("forbidden key {0!r} at {1}".format(key, where))
            _assert_no_forbidden_keys(value, "{0}.{1}".format(where, key))
    elif isinstance(node, list):
        for position, value in enumerate(node):
            _assert_no_forbidden_keys(value, "{0}[{1}]".format(where, position))


def _policies_without_notes(policies: Dict[str, Any]) -> Dict[str, Any]:
    """Return the policies with every clause's ``notes`` removed."""
    trimmed = copy.deepcopy(policies)
    for policy in trimmed.values():
        if not isinstance(policy, dict):
            continue
        for clause in policy.get("clauses", []) or []:
            if isinstance(clause, dict):
                clause.pop("notes", None)
    return trimmed


def build_brief(case_no: int, include_clause_notes: bool = True) -> Dict[str, Any]:
    """Return the evidence package for one case.

    One object per case, identical for both advocates. ``include_clause_notes``
    controls whether each clause's drafting commentary is carried; it is a flag
    so the cost can be measured later rather than decided here.
    """
    return build_brief_for_case(
        loader.load_case(case_no), include_clause_notes=include_clause_notes
    )


def build_brief_for_case(
    case: Dict[str, Any], include_clause_notes: bool = True
) -> Dict[str, Any]:
    """The same brief, from a case already in hand.

    Split out so a case that is not in the manifest can be briefed without
    being added to ``data/index.json``. A converted external case is loaded
    through its own explicit path by ``loader.load_external_case``, and adding
    it to the manifest would change the 29-case corpus the benchmark measures.

    Everything below is the body :func:`build_brief` has always had, moved
    rather than copied, so the two entry points cannot drift apart: there is
    only one of them.
    """
    category = case["dispute"].get("category")
    policies = loader.load_policies(category)

    category_policy = policies["category"]
    policy_id = category_policy.get("policy_id", "")
    fee_schedule = category_policy.get("fee_schedule") or {}

    # POL-RD-01's excess is a ROUTE_DEVIATION fact, so a NO_SHOW_CHARGE case
    # gets no deviation block at all.
    deviation_thresholds = (
        _deviation_thresholds(category_policy) if category == ROUTE_DEVIATION_CATEGORY else None
    )

    # POL-NS-06(i) is the mirror image: a NO_SHOW_CHARGE fact, and the
    # route-deviation policy carries no such clause, so it returns None there.
    no_show_thresholds = _no_show_thresholds(category_policy)

    trip_payload = None
    trip_evidence_id = None
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == TRIP_EVIDENCE_TYPE:
            trip_payload = artifact.get("payload")
            trip_evidence_id = artifact["evidence_id"]
            break

    # POL-RD-09(4) measures each ERP gantry line against the trace, so the fare
    # breakdown's lines travel into the GPS trace's derived facts. A case whose
    # fare breakdown carries no gantry line gets no block at all, which is what
    # keeps every other brief byte-identical.
    #
    # The whole fare payload is kept as well, because the money block is
    # computed on it and published beside it.
    gantry_lines = None
    fare_payload = None
    fare_evidence_id = None
    for artifact in case["evidence"]:
        if artifact["evidence_type"] != FARE_EVIDENCE_TYPE:
            continue
        payload = artifact.get("payload")
        if isinstance(payload, dict):
            fare_payload = payload
            fare_evidence_id = artifact["evidence_id"]
            if payload.get("erp_gantries"):
                gantry_lines = payload["erp_gantries"]
        break

    # POL-RD-03's measured excess is the trace's own excess, so the GPS payload
    # is captured too: the money block needs its distance to run the cap.
    gps_payload = None
    gps_evidence_id = None
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == GPS_EVIDENCE_TYPE:
            gps_payload = artifact.get("payload")
            gps_evidence_id = artifact["evidence_id"]
            break

    # Every advisory travels, including a MISSING one: limb (i) turns on
    # whether the artifact is present and populated, so the block has to be
    # able to name the one that is not.
    advisories = [
        {"evidence_id": artifact["evidence_id"], "payload": artifact.get("payload")}
        for artifact in case["evidence"]
        if artifact["evidence_type"] == TRAFFIC_ADVISORY_EVIDENCE_TYPE
    ]

    evidence = [
        _transform_gps_payload(
            artifact,
            trip_payload,
            trip_evidence_id,
            fee_schedule,
            policy_id,
            deviation_thresholds,
            no_show_thresholds,
            advisories,
            gantry_lines,
            fare_evidence_id,
        )
        if artifact["evidence_type"] == GPS_EVIDENCE_TYPE
        else artifact
        for artifact in case["evidence"]
    ]

    # The money block hangs off the fare breakdown, the artifact the money was
    # charged on, exactly as the derived geometry hangs off the trace. A case
    # with no fare breakdown gets no money block, because there is nothing to
    # compute on.
    #
    # The trace travels in its **transformed** form rather than the raw payload
    # captured above: the money block publishes each ERP line's amount beside
    # the trace's own proximity record for that line, and that record exists
    # only once the trace has been derived. The raw payload stays as the
    # fallback, for a trace with no payload to derive from.
    derived_trace = next(
        (
            artifact.get("payload")
            for artifact in evidence
            if artifact["evidence_type"] == GPS_EVIDENCE_TYPE
        ),
        None,
    )
    money_block = _money_block(
        category,
        category_policy,
        policy_id,
        fare_payload,
        fare_evidence_id,
        trip_payload,
        trip_evidence_id,
        derived_trace if isinstance(derived_trace, dict) else gps_payload,
        gps_evidence_id,
        advisories,
    )
    if money_block is not None:
        evidence = [
            _attach_derived(artifact, MONEY_KEY, money_block)
            if artifact["evidence_id"] == fare_evidence_id
            else artifact
            for artifact in evidence
        ]

    brief = {
        "case": {
            "case_no": case["case_no"],
            "schema_version": case["schema_version"],
            "dispute": case["dispute"],
            "evidence": evidence,
        },
        "policies": policies if include_clause_notes else _policies_without_notes(policies),
    }

    _assert_no_forbidden_keys(brief)
    return brief


def brief_digest(brief: Dict[str, Any]) -> Tuple[str, str]:
    """Return ``(canonical_json_str, sha256_hex)`` for ``brief``.

    Serialisation is fixed by the contract: UTF-8 JSON with
    ``ensure_ascii=False``, ``sort_keys=True`` and ``separators=(",", ":")``.

    The work is done by ``money.dumps_canonical``, because a brief now carries
    ``Decimal`` amounts and plain ``json.dumps`` cannot write those. Decimals
    are emitted as JSON numbers carrying their own literal, so the canonical
    bytes stay stable and reproducible run to run.
    """
    canonical = money.dumps_canonical(brief)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, digest
