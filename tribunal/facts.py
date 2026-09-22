"""Turn a raw GPS trace into the small numbers the policy clauses threshold on.

A GPS trace is the largest object in a case: roughly three quarters of the
bytes, and over a hundred coordinates for a single party. A language model
cannot be handed raw coordinates, and it cannot compute haversine distance
reliably, so this module does that arithmetic in code and hands the agents the
handful of figures a clause actually tests.

DESIGN RULE
-----------
This module contains **no policy number**. Every radius, dwell minimum,
accuracy filter and distance threshold is a parameter, supplied by the caller
from the loaded policy: ``policy/no_show.json`` under ``fee_schedule``
(``arrival_radius_m``, ``rider_presence_radius_m``, ``minimum_dwell_sec``,
``gps_accuracy_filter_m``) and ``policy/route_deviation.json`` under
``fare_model``. If a value came from a clause, it belongs in the caller.

The literals here are ``EARTH_RADIUS_M``, a geodetic constant of the
haversine formula, and ``MIN_RUN_FIXES``, the two ends an interval needs.
Neither is a policy value. POL-NS-06(i)'s leash and its four admissible
``traffic_advisory.type`` values, and POL-NS-05's line between holding
position and being in motion, all arrive as parameters for that reason.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Mean Earth radius in metres. A geodetic constant, not a policy threshold.
EARTH_RADIUS_M = 6371000.0

# The three values ``deviation_status`` can return, named once so callers and
# tests do not repeat the strings.
NO_DEVIATION = "no deviation"
ESTABLISHED = "established"
MATERIAL = "material"

# Percentage scale for expressing a ratio. Not a policy threshold: POL-RD-01's
# own 20 % and 50 % lines arrive as parameters.
PERCENT = 100

# The fewest fixes that can describe an interval. A single fix is an instant
# with zero duration: it contributes no dwell and POL-NS-06(i) has no interval
# to accumulate. Not a policy number, the definition of a run.
MIN_RUN_FIXES = 2

# The conditions POL-NS-06(i) requires before separate in-geofence intervals may
# be summed, named once so the caller and the tests do not repeat the strings.
# They are conjunctive, so more than one can fail at the same time and every
# failure is reported: a judge told only the first reason may spend its argument
# on a condition the other side then answers, when a different one decides the
# limb outright.
NO_SECOND_INTERVAL = "no_second_interval"
EXCURSION_UNMEASURABLE = "excursion_unmeasurable"
EXCURSION_BEYOND_LEASH = "excursion_beyond_leash"
ADVISORY_MISSING = "advisory_missing"
ADVISORY_TYPE_NOT_ADMISSIBLE = "advisory_type_not_admissible"
ADVISORY_ROUTE_NOT_COVERED = "advisory_route_not_covered"
ADVISORY_WINDOW_NOT_COVERED = "advisory_window_not_covered"


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def distances_to_point(points: Optional[Sequence[Dict[str, Any]]], lat: float, lng: float) -> List[float]:
    """Distance in metres from each fix to ``(lat, lng)``, one per fix, same order."""
    return [haversine_m(fix["lat"], fix["lng"], lat, lng) for fix in points or []]


def _is_qualifying(fix: Dict[str, Any], lat: float, lng: float, radius_m: float, accuracy_max_m: float) -> bool:
    """True when a fix is inside the radius and carries usable accuracy.

    A fix whose ``accuracy_m`` is missing or worse than the filter is evidence
    of neither presence nor absence, so it is not qualifying. It is not
    treated as a fix outside the radius either.
    """
    accuracy = fix.get("accuracy_m")
    if accuracy is None or accuracy > accuracy_max_m:
        return False
    return haversine_m(fix["lat"], fix["lng"], lat, lng) <= radius_m


def qualifying_fixes(
    points: Optional[Sequence[Dict[str, Any]]],
    lat: float,
    lng: float,
    radius_m: float,
    accuracy_max_m: float,
) -> List[Dict[str, Any]]:
    """The fixes within ``radius_m`` of the point whose accuracy passes the filter."""
    return [
        fix
        for fix in points or []
        if _is_qualifying(fix, lat, lng, radius_m, accuracy_max_m)
    ]


def elapsed_seconds(start_ts: Optional[str], end_ts: Optional[str]) -> float:
    """Seconds from ``start_ts`` to ``end_ts``, as a float, unrounded."""
    if start_ts is None or end_ts is None:
        return 0.0
    return (datetime.fromisoformat(end_ts) - datetime.fromisoformat(start_ts)).total_seconds()


def longest_qualifying_run(
    points: Optional[Sequence[Dict[str, Any]]],
    lat: float,
    lng: float,
    radius_m: float,
    accuracy_max_m: float,
) -> Dict[str, Any]:
    """The longest run of *consecutive* qualifying fixes in the trace's own order.

    A single non-qualifying fix breaks the run. Returns the run's first and
    last timestamp, its fix count, and its duration in seconds. With no
    qualifying fix at all, every field is empty and the duration is ``0.0``.
    """
    empty = {"first_ts": None, "last_ts": None, "fix_count": 0, "duration_sec": 0.0}

    best_start = best_length = 0
    current_start = current_length = 0

    for index, fix in enumerate(points or []):
        if _is_qualifying(fix, lat, lng, radius_m, accuracy_max_m):
            if current_length == 0:
                current_start = index
            current_length += 1
            if current_length > best_length:
                best_start, best_length = current_start, current_length
        else:
            current_length = 0

    if best_length == 0:
        return dict(empty)

    trace = list(points or [])
    first_ts = trace[best_start].get("ts")
    last_ts = trace[best_start + best_length - 1].get("ts")
    return {
        "first_ts": first_ts,
        "last_ts": last_ts,
        "fix_count": best_length,
        "duration_sec": elapsed_seconds(first_ts, last_ts),
    }


def _is_holding(
    fix: Dict[str, Any],
    lat: float,
    lng: float,
    radius_m: float,
    accuracy_max_m: float,
    motion_speed_kph: float,
) -> bool:
    """True when a fix shows the driver *holding position* inside the radius.

    POL-NS-01 limb (c) requires the driver to have "held position inside that
    geofence", and POL-NS-05 fixes the line between holding and moving at a
    named speed. A fix at or above that line is in motion, so it is not a
    holding fix even where it is inside the radius with good accuracy.

    A fix whose ``speed_kph`` is missing is not evidence of holding, for the
    same reason a fix with unusable accuracy is not evidence of presence: the
    trace does not show the fact, so the fact is not asserted.
    """
    if not _is_qualifying(fix, lat, lng, radius_m, accuracy_max_m):
        return False
    speed = fix.get("speed_kph")
    if speed is None:
        return False
    return speed < motion_speed_kph


def _run_index_ranges(
    trace: Sequence[Dict[str, Any]],
    lat: float,
    lng: float,
    radius_m: float,
    accuracy_max_m: float,
    motion_speed_kph: float,
    gap_resumes: Iterable[Any],
) -> List[Tuple[int, int]]:
    """Inclusive ``(start, end)`` index pairs of every run of holding fixes.

    A run ends at the first fix that is not a holding fix. It also ends at a
    fix whose timestamp is the end of a recorded gap: a hole in the trace is
    not evidence that the driver kept holding position, and counting the
    unobserved interval as dwell is how a 168 second outage becomes 168
    seconds of presence.

    A run of a single fix is dropped. An instant has no duration, contributes
    no dwell, and is not an interval for POL-NS-06(i) to accumulate.
    """
    resumes = set(gap_resumes)
    ranges: List[Tuple[int, int]] = []
    start: Optional[int] = None

    for index, fix in enumerate(trace):
        if not _is_holding(fix, lat, lng, radius_m, accuracy_max_m, motion_speed_kph):
            if start is not None:
                ranges.append((start, index - 1))
                start = None
            continue
        if start is None:
            start = index
        elif fix.get("ts") in resumes:
            ranges.append((start, index - 1))
            start = index

    if start is not None:
        ranges.append((start, len(trace) - 1))

    return [(start, end) for start, end in ranges if end - start + 1 >= MIN_RUN_FIXES]


def _run_summary(trace: Sequence[Dict[str, Any]], start: int, end: int) -> Dict[str, Any]:
    """One run as its endpoints, its fix count and its duration."""
    first_ts = trace[start].get("ts")
    last_ts = trace[end].get("ts")
    return {
        "first_ts": first_ts,
        "last_ts": last_ts,
        "fix_count": end - start + 1,
        "duration_sec": elapsed_seconds(first_ts, last_ts),
    }


def qualifying_runs(
    points: Optional[Sequence[Dict[str, Any]]],
    lat: float,
    lng: float,
    radius_m: float,
    accuracy_max_m: float,
    motion_speed_kph: float,
    gaps: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Every separate in-geofence interval in which the driver held position.

    This is ``longest_qualifying_run``'s plural form, with two differences the
    clause requires. A run is broken by a recorded gap in the trace as well as
    by a fix that is not a holding fix, because the trace cannot show presence
    across a hole; and a run of one fix is not a run.

    The runs come back in the trace's own order, so the caller can read the
    excursions between them.
    """
    trace = list(points or [])
    gap_list = [gap for gap in (gaps or []) if isinstance(gap, Mapping)]
    ranges = _run_index_ranges(
        trace,
        lat,
        lng,
        radius_m,
        accuracy_max_m,
        motion_speed_kph,
        (gap.get("to_ts") for gap in gap_list),
    )
    return [_run_summary(trace, start, end) for start, end in ranges]


def _gap_overlaps(
    gaps: Sequence[Mapping[str, Any]],
    from_ts: Optional[str],
    to_ts: Optional[str],
) -> bool:
    """True when a recorded gap overlaps the interval ``(from_ts, to_ts)``."""
    if from_ts is None or to_ts is None:
        return False
    start = datetime.fromisoformat(from_ts)
    end = datetime.fromisoformat(to_ts)
    for gap in gaps:
        gap_start = gap.get("from_ts")
        gap_end = gap.get("to_ts")
        if gap_start is None or gap_end is None:
            continue
        if datetime.fromisoformat(gap_start) < end and datetime.fromisoformat(gap_end) > start:
            return True
    return False


def _excursion_spans(
    trace: Sequence[Dict[str, Any]],
    ranges: Sequence[Tuple[int, int]],
    lat: float,
    lng: float,
    gaps: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """The excursion between each pair of consecutive runs.

    ``max_distance_m`` is the furthest the driver was from the pin over the
    fixes strictly between the two runs, and it is ``None`` where a recorded
    gap overlaps that stretch. ``None`` is not a missing value to be filled in
    with a default: the observed maximum over a trace with a hole is a lower
    bound, and a lower bound cannot certify a leash.
    """
    spans: List[Dict[str, Any]] = []

    for (_, end), (start, _) in zip(ranges, ranges[1:]):
        from_ts = trace[end].get("ts")
        to_ts = trace[start].get("ts")
        inner = list(trace[end + 1:start])
        hole = _gap_overlaps(gaps, from_ts, to_ts)
        spans.append({
            "from_ts": from_ts,
            "to_ts": to_ts,
            "fix_count": len(inner),
            "max_distance_m": None if hole else (
                max(distances_to_point(inner, lat, lng)) if inner else 0.0
            ),
            "gap_in_interval": hole,
        })

    return spans


def _advisory_failures(
    payload: Mapping[str, Any],
    admissible_types: Sequence[str],
) -> List[str]:
    """The POL-NS-06(i) advisory conditions one candidate fails.

    The four are checked independently rather than short-circuited, so a
    candidate that fails two of them reports two.
    """
    failures: List[str] = []
    if payload.get("type") not in admissible_types:
        failures.append(ADVISORY_TYPE_NOT_ADMISSIBLE)
    if payload.get("intersects_route") is not True:
        failures.append(ADVISORY_ROUTE_NOT_COVERED)
    if payload.get("overlaps_trip_window") is not True:
        failures.append(ADVISORY_WINDOW_NOT_COVERED)
    return failures


def _advisory_candidates(
    advisories: Optional[Sequence[Mapping[str, Any]]],
    admissible_types: Sequence[str],
) -> List[Dict[str, Any]]:
    """Every advisory that is present and populated, with what it fails.

    ``evidence_id`` is echoed, not interpreted: this module does not know what
    an artifact is, but a reason a reader cannot trace to an artifact is not a
    reason. A MISSING advisory has ``payload: null`` and does not appear here
    at all; the caller reports it by name.
    """
    candidates: List[Dict[str, Any]] = []
    for advisory in advisories or []:
        payload = advisory.get("payload")
        if not isinstance(payload, Mapping) or not payload:
            continue
        candidates.append({
            "evidence_id": advisory.get("evidence_id"),
            "type": payload.get("type"),
            "failed_conditions": _advisory_failures(payload, admissible_types),
        })
    return candidates


def _unavailable_accumulation(
    runs: Sequence[Mapping[str, Any]],
    spans: Sequence[Mapping[str, Any]],
    leash_m: float,
    candidates: Sequence[Mapping[str, Any]],
) -> List[str]:
    """Every POL-NS-06(i) condition that fails, not only the first.

    The conditions are conjunctive, so more than one can fail at once. A judge
    told only the first reason may spend its argument answering a condition the
    other side then concedes, when a different one decides the limb outright.
    The reasons come back in the module's declared order, so the list is stable
    between runs.
    """
    reasons: List[str] = []

    if len(runs) < 2:
        reasons.append(NO_SECOND_INTERVAL)

    if any(span.get("gap_in_interval") for span in spans):
        reasons.append(EXCURSION_UNMEASURABLE)

    if any(
        span.get("max_distance_m") is not None and span["max_distance_m"] > leash_m
        for span in spans
    ):
        reasons.append(EXCURSION_BEYOND_LEASH)

    if not candidates:
        reasons.append(ADVISORY_MISSING)
    else:
        # A condition is reported flat only when no candidate satisfies it.
        # Each candidate's own failures travel beside this list, so a case
        # where two candidates fail different conditions is still legible.
        for condition in (
            ADVISORY_TYPE_NOT_ADMISSIBLE,
            ADVISORY_ROUTE_NOT_COVERED,
            ADVISORY_WINDOW_NOT_COVERED,
        ):
            if all(condition in candidate["failed_conditions"] for candidate in candidates):
                reasons.append(condition)

    return reasons


def accumulated_dwell(
    points: Optional[Sequence[Dict[str, Any]]],
    lat: float,
    lng: float,
    radius_m: float,
    accuracy_max_m: float,
    motion_speed_kph: float,
    leash_m: float,
    admissible_types: Sequence[str],
    advisories: Optional[Sequence[Mapping[str, Any]]] = None,
    gaps: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """POL-NS-06(i): whether separate in-geofence intervals may be summed.

    The clause permits dwell to be accumulated across separate in-geofence
    intervals within one pickup attempt where the trace shows the driver
    leaving and re-entering the arrival radius without at any point travelling
    more than a stated distance from the pin, AND a present, populated
    traffic_advisory of an admissible type covers the pickup road over the
    waiting period. Limb (ii) is the limit: an advisory never reduces the
    required minimum and never excuses a shortfall on its own, it only permits
    the intervals to be summed.

    Every threshold arrives as a parameter, including the leash and the four
    advisory type values, which the caller reads out of the clause's own prose.
    None is a literal here.

    Returns the runs, the excursion between each pair, the accumulated total,
    ``available``, and ``unavailable_reasons`` naming **every** condition that
    failed. With one run or none, ``accumulated_sec`` equals ``longest_run_sec``
    rather than being absent, so a caller never has to special-case the shape.
    """
    trace = list(points or [])
    gap_list = [gap for gap in (gaps or []) if isinstance(gap, Mapping)]

    ranges = _run_index_ranges(
        trace,
        lat,
        lng,
        radius_m,
        accuracy_max_m,
        motion_speed_kph,
        (gap.get("to_ts") for gap in gap_list),
    )
    runs = [_run_summary(trace, start, end) for start, end in ranges]
    spans = _excursion_spans(trace, ranges, lat, lng, gap_list)
    candidates = _advisory_candidates(advisories, admissible_types)
    reasons = _unavailable_accumulation(runs, spans, leash_m, candidates)

    measured = [span["max_distance_m"] for span in spans if span["max_distance_m"] is not None]

    return {
        "runs": runs,
        "run_count": len(runs),
        "longest_run_sec": max([run["duration_sec"] for run in runs], default=0.0),
        "accumulated_sec": sum(run["duration_sec"] for run in runs),
        "excursions": spans,
        "max_excursion_m": max(measured) if measured else None,
        "excursions_measurable": all(span["max_distance_m"] is not None for span in spans),
        "available": not reasons,
        "unavailable_reasons": reasons,
        "advisory_candidates": candidates,
    }


def track_summary(
    points: Optional[Sequence[Dict[str, Any]]],
    lat: float,
    lng: float,
) -> Dict[str, Any]:
    """Min, max and mean distance to the point, fix count, distinct speeds and the time span.

    An empty or missing trace yields an empty summary rather than raising.
    Distances and the time span are unrounded.
    """
    trace = list(points or [])
    if not trace:
        return {
            "fix_count": 0,
            "min_distance_m": None,
            "max_distance_m": None,
            "mean_distance_m": None,
            "distinct_speeds_kph": [],
            "first_ts": None,
            "last_ts": None,
        }

    distances = distances_to_point(trace, lat, lng)
    speeds = sorted({fix["speed_kph"] for fix in trace if fix.get("speed_kph") is not None})
    return {
        "fix_count": len(trace),
        "min_distance_m": min(distances),
        "max_distance_m": max(distances),
        "mean_distance_m": sum(distances) / len(distances),
        "distinct_speeds_kph": speeds,
        "first_ts": trace[0].get("ts"),
        "last_ts": trace[-1].get("ts"),
    }


def driver_points(gps_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The driver's fixes from a GPS payload, or ``[]``.

    Tolerates a missing payload (a MISSING artifact has ``payload: null``).
    """
    if not isinstance(gps_payload, dict):
        return []
    points = gps_payload.get("points")
    return list(points) if isinstance(points, list) else []


def rider_points(gps_payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The rider's fixes from a GPS payload, or ``[]``.

    Tolerates a missing payload and a ``rider_track`` that is ``null``, which
    is how the corpus records a case with no rider track at all.
    """
    if not isinstance(gps_payload, dict):
        return []
    track = gps_payload.get("rider_track")
    return list(track) if isinstance(track, list) else []


def deviation_excess(trace_distance_km: float, optimal_distance_km: float):
    """Return ``(excess_km, excess_pct)`` for POL-RD-01.

    POL-RD-01 states the measurement and the arithmetic:

        "Measure actual_distance_km as the length of the gps_trace polyline
        between the recorded pickup event and the recorded dropoff event; the
        governing field is gps_trace.trace_distance_km. ... Measure
        optimal_distance_km as the platform route estimate stored on the
        trip_record at booking ... Excess = actual_distance_km -
        optimal_distance_km."

    The governing measurement is ``gps_trace.trace_distance_km``, which the
    clause says must be used in preference to the trip record's rounded copy.
    Neither the excess nor the percentage is rounded here; the clause's own
    thresholds decide what they mean.

    Raises ``ValueError`` when ``optimal_distance_km`` is absent or not
    positive, because the percentage test is undefined without it.
    """
    if optimal_distance_km is None or optimal_distance_km <= 0:
        raise ValueError(
            "optimal_distance_km must be present and positive to express the "
            "excess as a percentage; got {0!r}".format(optimal_distance_km)
        )

    excess_km = trace_distance_km - optimal_distance_km
    excess_pct = (excess_km / optimal_distance_km) * PERCENT
    return excess_km, excess_pct


def deviation_status(
    excess_km: float,
    excess_pct: float,
    threshold_pct: float,
    threshold_km: float,
    material_pct: float,
    material_km: float,
) -> str:
    """Classify an excess under POL-RD-01 as one of three values.

    POL-RD-01 states both tests:

        "A route deviation is ESTABLISHED only when the excess is greater than
        20% of optimal_distance_km AND greater than 0.8 km in absolute terms;
        both tests must pass. An excess greater than 50% of optimal_distance_km,
        or greater than 8.0 km absolute, is additionally a MATERIAL deviation
        and requires the driver_profile check in POL-RD-06."

    Two things the wording fixes:

    * **Establishment requires BOTH tests**, not either. An excess that clears
      the percentage line but not the absolute line is no deviation at all.
    * **Both comparisons are strict.** "greater than" excludes equality, so an
      excess exactly on a line does not clear it. This is what separates case
      106, at 49.72 % against a 50 % line, from case 105 at 50.44 %.

    All four thresholds are parameters; none is a literal here.
    """
    if excess_pct is None:
        raise ValueError("excess_pct is required to apply the percentage tests")

    established = excess_pct > threshold_pct and excess_km > threshold_km
    if not established:
        return NO_DEVIATION

    if excess_pct > material_pct or excess_km > material_km:
        return MATERIAL
    return ESTABLISHED
