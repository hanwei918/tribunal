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
) -> Dict[str, Any]:
    """The zone-dependent no-show facts, or an explicit statement of why not.

    Where ``pickup_zone_class`` is null the zone-dependent facts cannot be
    computed. They are omitted and the brief says so; no default zone is
    substituted and nothing is guessed.
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


def _transform_gps_payload(
    artifact: Dict[str, Any],
    trip_payload: Optional[Dict[str, Any]],
    trip_evidence_id: Optional[str],
    fee_schedule: Dict[str, Any],
    policy_id: str,
    deviation_thresholds: Optional[Dict[str, float]] = None,
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
            payload, evidence_id, trip_payload, trip_evidence_id, fee_schedule, policy_id
        ),
    }
    if deviation_thresholds:
        derived[DEVIATION_BLOCK] = _deviation_block(
            payload, evidence_id, trip_payload, trip_evidence_id, deviation_thresholds, policy_id
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
    case = loader.load_case(case_no)
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

    trip_payload = None
    trip_evidence_id = None
    for artifact in case["evidence"]:
        if artifact["evidence_type"] == TRIP_EVIDENCE_TYPE:
            trip_payload = artifact.get("payload")
            trip_evidence_id = artifact["evidence_id"]
            break

    evidence = [
        _transform_gps_payload(
            artifact, trip_payload, trip_evidence_id, fee_schedule, policy_id, deviation_thresholds
        )
        if artifact["evidence_type"] == GPS_EVIDENCE_TYPE
        else artifact
        for artifact in case["evidence"]
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
