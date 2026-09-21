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

The one literal here is ``EARTH_RADIUS_M``, a geodetic constant of the
haversine formula, not a policy value.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

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
