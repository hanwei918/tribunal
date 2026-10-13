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
haversine formula, ``MIN_RUN_FIXES``, the two ends an interval needs, and the
``[-1, 1]`` bounds of a sine, which is the domain of ``math.asin``. None is a
policy value. POL-NS-06(i)'s leash and its four admissible
``traffic_advisory.type`` values, and POL-NS-05's line between holding
position and being in motion, all arrive as parameters for that reason. So does
POL-RD-09(4)'s radius: :func:`gantry_proximity` reports distances and decides
no match, because the threshold that turns a distance into a match is the
clause's.

The **version-7** facts -- POL-NS-21 to POL-NS-24 (a no-show) and POL-RD-21 to
POL-RD-25 (a route deviation) -- are computed here under the same rule. The free
wait, the late-after-schedule allowance, the arrival window, the arrival radius,
the accuracy filter, the deviation tolerance and v2.1 6.2's ceiling with its
switch all arrive as parameters, read from the loaded policy by the caller.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import money

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


def _unit(value: float) -> float:
    """A sine held inside ``[-1, 1]``, where floating point can put it just outside.

    ``math.asin`` raises on an argument outside its domain, and a sine that
    should be exactly 1 comes back as 1 + 1e-16 on a degenerate segment. The
    two bounds are the range of the sine, not a policy value.
    """
    return max(-1.0, min(1.0, value))


def initial_bearing_rad(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """The initial great-circle bearing, in radians, from the first point to the second."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lng2 - lng1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.atan2(y, x)


def point_to_segment_m(
    lat: float, lng: float, lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Closest distance in metres from a point to the great-circle segment A -> B.

    This is the distance from a gantry to the straight line a trace would have
    followed across a hole in it: the two ends are the fixes either side of the
    gap, and the path between them is not recorded.

    The perpendicular is taken on the sphere rather than on a local flat
    projection, so the figure is the same one :func:`haversine_m` gives for a
    point that happens to lie on the segment. Where the foot falls beyond an
    end, the nearest point is that end and the distance is the haversine to it.
    """
    span = haversine_m(lat1, lng1, lat2, lng2)
    to_a = haversine_m(lat1, lng1, lat, lng)
    to_b = haversine_m(lat2, lng2, lat, lng)

    if span == 0.0:
        return to_a
    if to_a == 0.0:
        return 0.0

    offset = initial_bearing_rad(lat1, lng1, lat, lng) - initial_bearing_rad(lat1, lng1, lat2, lng2)
    along = to_a * math.cos(offset)
    if along <= 0.0:
        return to_a
    if along >= span:
        return to_b

    return abs(math.asin(_unit(math.sin(to_a / EARTH_RADIUS_M) * math.sin(offset))) * EARTH_RADIUS_M)


def gantry_proximity(
    points: Optional[Sequence[Dict[str, Any]]],
    lines: Optional[Sequence[Mapping[str, Any]]],
    gaps: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """How close a trace came to each ERP gantry line on a fare breakdown.

    POL-RD-09(4) matches a gantry to the trace by comparing the gantry's
    coordinates against the trace, and it treats a line with no coordinates as
    matched. The clause's radius is a threshold and stays in the clause, so
    nothing here decides whether a gantry was crossed: this returns distances
    only, and the judge applies the clause.

    One record per line, in the order given:

    * ``nearest_fix`` -- the fix closest to the gantry, its index in the
      trace's own order, its ``ts``, and the distance in metres, computed with
      :func:`haversine_m`, the same function the other derived facts use.
    * ``gap_brackets_closest_approach`` and ``across_gap_distance_m`` -- whether
      a recorded gap in the trace brackets the closest approach, and the
      closest distance from the gantry to the straight line across any such
      gap. A crossing that happened inside a gap must not read as a gantry the
      trace never passed.
    * ``coordinates`` -- ``None`` where the line carries no coordinates, in
      which case nothing is derived from it.

    A gap brackets the closest approach under either of two conditions, both of
    which mean the trace cannot bound how close the vehicle came: the nearest
    observed fix is one of the gap's two bounding fixes, so the observed
    minimum sits at the edge of a hole; or the straight segment across the gap
    passes at least as close to the gantry as the nearest observed fix does, so
    the unobserved stretch could contain an approach at least as close.
    """
    trace = list(points or [])
    gap_list = [gap for gap in (gaps or []) if isinstance(gap, Mapping)]
    fix_by_ts = {fix.get("ts"): fix for fix in trace}

    records: List[Dict[str, Any]] = []
    for line in lines or []:
        if not isinstance(line, Mapping):
            continue

        lat, lng = line.get("lat"), line.get("lng")
        located = lat is not None and lng is not None

        record: Dict[str, Any] = {
            "gantry_name": line.get("gantry_name"),
            "amount_sgd": line.get("amount_sgd"),
            "charged_at": line.get("charged_at"),
            "on_optimal_route": line.get("on_optimal_route"),
            "coordinates": {"lat": lat, "lng": lng} if located else None,
            "nearest_fix": None,
            "gap_brackets_closest_approach": False,
            "across_gap_distance_m": None,
            "bracketing_gaps": [],
        }

        if not located or not trace:
            records.append(record)
            continue

        distances = distances_to_point(trace, lat, lng)
        nearest = min(range(len(distances)), key=distances.__getitem__)
        nearest_ts = trace[nearest].get("ts")
        record["nearest_fix"] = {
            "index": nearest,
            "ts": nearest_ts,
            "distance_m": distances[nearest],
        }

        bracketing: List[Dict[str, Any]] = []
        for gap in gap_list:
            from_ts, to_ts = gap.get("from_ts"), gap.get("to_ts")
            start, end = fix_by_ts.get(from_ts), fix_by_ts.get(to_ts)
            if start is None or end is None:
                continue
            across = point_to_segment_m(lat, lng, start["lat"], start["lng"], end["lat"], end["lng"])
            if nearest_ts not in (from_ts, to_ts) and across > distances[nearest]:
                continue
            bracketing.append({
                "from_ts": from_ts,
                "to_ts": to_ts,
                "duration_sec": gap.get("duration_sec"),
                "distance_m": across,
            })

        if bracketing:
            record["gap_brackets_closest_approach"] = True
            record["across_gap_distance_m"] = min(item["distance_m"] for item in bracketing)
            record["bracketing_gaps"] = bracketing

        records.append(record)

    return records


def bounding_box_approach(
    points: Optional[Sequence[Dict[str, Any]]],
    min_lat: float,
    min_lng: float,
    max_lat: float,
    max_lng: float,
) -> Dict[str, Any]:
    """How a trace stands against an axis-aligned latitude/longitude box.

    A traffic advisory's ``geometry`` is a bounding box -- ``min_lat``,
    ``min_lng``, ``max_lat`` and ``max_lng`` -- and the optimal route's own
    polyline is not in the record at all. So how the trace stands against that
    box is the closest test of whether the trace entered the advisory's area
    that the record allows, and it is the figure POL-RD-03(c)'s limb (c) is
    weighed against.

    Returns ``{"fix_count": n, "fixes_inside": k, "minimum_distance_m": d}``,
    where ``d`` is the distance in metres from the nearest fix to the box --
    ``0.0`` when a fix lies inside it, because the nearest point of the box is
    the fix itself -- and ``None`` when the trace carries no fix with both
    coordinates. Nothing here decides that the trace entered anything: the
    figures are published and the clause is the judge's to apply.
    """
    trace = [fix for fix in points or [] if isinstance(fix, Mapping)]
    inside = 0
    nearest = None
    for fix in trace:
        lat, lng = fix.get("lat"), fix.get("lng")
        if lat is None or lng is None:
            continue
        # The case files are read with ``parse_float=Decimal``, so a coordinate
        # arrives as a ``Decimal``; the arithmetic here is float, the way
        # :func:`haversine_m` and the rest of this module's geometry is.
        lat, lng = float(lat), float(lng)
        # The nearest point of an axis-aligned box is the point clamped into it,
        # which is the fix itself when the fix is inside. One expression for
        # both cases, so a fix on the boundary counts as inside and reads 0 m.
        closest_lat = min(max(lat, min_lat), max_lat)
        closest_lng = min(max(lng, min_lng), max_lng)
        if closest_lat == lat and closest_lng == lng:
            inside += 1
            distance = 0.0
        else:
            distance = haversine_m(lat, lng, closest_lat, closest_lng)
        if nearest is None or distance < nearest:
            nearest = distance
    return {
        "fix_count": len(trace),
        "fixes_inside": inside,
        "minimum_distance_m": nearest,
    }


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
        "accumulated_sec": _sum_in_order(run["duration_sec"] for run in runs),
        "excursions": spans,
        "max_excursion_m": max(measured) if measured else None,
        "excursions_measurable": all(span["max_distance_m"] is not None for span in spans),
        "available": not reasons,
        "unavailable_reasons": reasons,
        "advisory_candidates": candidates,
    }


def _sum_in_order(values: Iterable[float]) -> float:
    """Sum left to right, in the order given, with no compensation.

    Deliberately not the builtin. Python 3.12 changed ``sum()`` for floats to
    Neumaier compensated summation, so the same distances average to a different
    last bit under 3.9 and under 3.13. A mean travels unrounded into the brief,
    so with the builtin the brief's bytes — and therefore ``brief_sha256`` —
    would depend on the interpreter that built it, and a cached result would be
    reported stale purely because the check ran under a different Python.

    This is the accumulation CPython performed before 3.12, so it reproduces the
    value every brief already cached was built from instead of introducing a
    third one. ``math.fsum`` is correctly rounded and is the wrong repair here
    for exactly that reason: it is not what the cache encodes.

    Integers are exact under either rule, so a caller summing counts does not
    need this. Only a float total does.
    """
    total = 0.0
    for value in values:
        total = total + value
    return total


def track_summary(
    points: Optional[Sequence[Dict[str, Any]]],
    lat: float,
    lng: float,
) -> Dict[str, Any]:
    """Min, max and mean distance to the point, fix count, distinct speeds and the time span.

    An empty or missing trace yields an empty summary rather than raising.
    Distances and the time span are unrounded.

    The mean goes through :func:`_sum_in_order` rather than ``sum()`` so that it
    does not depend on the interpreter. See that function for why.
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
        "mean_distance_m": _sum_in_order(distances) / len(distances),
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


# --------------------------------------------------------------------------
# Policy version 7: the facts Ryde's Dispute Resolution Policy v2.1 tests
# --------------------------------------------------------------------------
# POL-NS-21 to POL-NS-24 (a no-show) and POL-RD-21 to POL-RD-25 (a route
# deviation) test facts the version-6 brief never computed: where the free wait
# started and ended, whether the driver messaged **and** called before
# cancelling, whether the driver reached the pickup by the deadline, the
# deviation between the **recorded** distances and its excess distance fare,
# whether a traffic advisory justifies the reroute, and the confidence a ruling
# needs. Every one of them is computed here, from plain values, so the brief
# publishes figures and decides nothing.
#
# The module's design rule is unchanged and every threshold still arrives as a
# parameter: the free wait, the late-after-schedule allowance, the arrival
# window and radius, the accuracy filter, the deviation tolerance, v2.1 6.2's
# ceiling with its switch, and the kinds of traffic event POL-RD-23 names.

# The two readings POL-NS-21's structured ``free_wait_starts`` field names, and
# the value that says which one produced a reading.
FREE_WAIT_FROM_SCHEDULE = "scheduled_at"
FREE_WAIT_FROM_ARRIVAL = "arrived_at"

# POL-NS-24's own words for the record that fixes no deadline. Not a policy
# value: it is the reason a figure is absent, and it says which limb applies.
ON_DEMAND_REASON = "on-demand trip: no scheduled time"

# POL-NS-23 reads a placed call from ``trip_record.in_app_calls`` **or** from a
# voice-call entry in the chat log, and the record holds the first in either of
# two shapes. These are the record's own field names, not the policy's; the two
# source labels say which record a counted call came from, so a reader can see
# that a call logged in both places was counted once.
CALL_LOG_CHANNEL = "VOICE_CALL_LOG"
DRIVER_ROLE = "DRIVER"
RIDER_ROLE = "RIDER"
CALL_ACTOR_FIELDS = (("placed_by", "placed_at"), ("initiated_by", "initiated_at"))
CALLS_SOURCE = "in_app_calls"
CHAT_CALL_SOURCE = "chat_log"

# Why POL-RD-22's deviation cannot be established. The clause's own words: the
# deviation is the difference between the platform's recorded distances, so a
# missing or impaired record leaves nothing to subtract.
DEVIATION_NOT_MEASURABLE_REASON = (
    "either recorded distance is missing or the trip record is impaired, so the "
    "deviation cannot be established (POL-RD-22, POL-GEN-26)"
)

# Why a traffic advisory justifies nothing: there is no advisory at all.
ADVISORY_ARTIFACT_MISSING_REASON = (
    "{0} is MISSING, and a MISSING artifact carries no fact (POL-GEN-02), so "
    "POL-RD-23 has no traffic data to read"
)


def _instant(stamp: Any) -> Optional[datetime]:
    """One ISO-8601 timestamp as a ``datetime``, or ``None`` when it is not one."""
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:
        return None


def _after_seconds(stamp: Any, seconds: Any) -> Optional[str]:
    """``stamp`` plus ``seconds``, written back in the same ISO-8601 form.

    The offset the record wrote is carried through unchanged, so an instant
    derived from a ``+08:00`` stamp is a ``+08:00`` stamp: a reader comparing
    two of them compares two instants, not two spellings.
    """
    instant = _instant(stamp)
    if instant is None or seconds is None:
        return None
    return (instant + timedelta(seconds=int(seconds))).isoformat()


def _between_seconds(start: Any, end: Any) -> Optional[float]:
    """Seconds from ``start`` to ``end``, or ``None`` when either is unreadable."""
    if _instant(start) is None or _instant(end) is None:
        return None
    return elapsed_seconds(start, end)


def _number(value: Any) -> Optional[float]:
    """One recorded figure as a float, or ``None`` when it is not a figure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def free_wait(
    arrived_at: Any,
    scheduled_at: Any,
    free_wait_sec: Any,
    cancelled_at: Any,
) -> Dict[str, Any]:
    """POL-NS-21: where the free wait starts and ends, and whether the cancellation fell after it.

    POL-NS-21: "The driver waits a free wait time of 5 minutes (300 s) from the
    scheduled pickup time; after it, the driver may cancel the trip as a rider
    no-show. For an on-demand trip, or a scheduled trip where the driver arrived
    after the scheduled time, the free wait runs from the driver's arrival."

    The policy's structured ``free_wait_starts`` field states the same reading
    as a rule: the clock starts at ``trip_record.scheduled_at`` where the trip is
    scheduled **and** the driver arrived at or before it, and at
    ``trip_record.arrived_at`` otherwise. ``starts_from`` names which of the two
    produced the reading, so a judge can see why the clock started where it did
    rather than inferring it.

    A cancellation **at** ``ends_at`` is after the free wait. The clause says
    the driver may cancel "after it", and the wait is satisfied at the moment it
    elapses -- which is how POL-NS-01 limb (d) reads the same clock ("at or
    after the moment the required dwell elapsed"). One second before it is
    before it.
    """
    arrived = _instant(arrived_at)
    scheduled = _instant(scheduled_at)
    if scheduled is not None and arrived is not None and arrived <= scheduled:
        starts_at, starts_from = scheduled_at, FREE_WAIT_FROM_SCHEDULE
    else:
        starts_at, starts_from = arrived_at, FREE_WAIT_FROM_ARRIVAL

    ends_at = _after_seconds(starts_at, free_wait_sec)
    cancelled = _instant(cancelled_at)
    ends = _instant(ends_at)
    return {
        "arrived_at": arrived_at,
        "scheduled_at": scheduled_at,
        "starts_at": starts_at,
        "starts_from": starts_from,
        "ends_at": ends_at,
        "cancelled_at": cancelled_at,
        "cancelled_after_free_wait": (
            None if cancelled is None or ends is None else cancelled >= ends
        ),
        "seconds_from_start_to_cancel": _between_seconds(starts_at, cancelled_at),
    }


def driver_deadline(
    scheduled_at: Any,
    arrived_at: Any,
    driver_late_after_scheduled_sec: Any,
) -> Dict[str, Any]:
    """POL-NS-24: the moment the driver had to be at the pickup by, and whether he was.

    POL-NS-24: "If the driver fails to arrive at the pickup location by the
    scheduled pickup time plus 5 minutes, the rider may cancel at no charge."
    The addition is the policy's own ``driver_late_after_scheduled_sec``.

    An on-demand trip has no scheduled time, so the record fixes no deadline and
    none is invented: the block says so, names the limb in its reason, and
    POL-GEN-26 applies. Where the trip is scheduled, an arrival after the
    deadline is a failure to arrive by it; no arrival at all is a failure too,
    which is why ``arrived_by_deadline`` is false rather than absent.
    """
    if _instant(scheduled_at) is None:
        return {"deadline": None, "reason": ON_DEMAND_REASON}

    deadline = _after_seconds(scheduled_at, driver_late_after_scheduled_sec)
    arrived = _instant(arrived_at)
    limit = _instant(deadline)
    return {
        "deadline": deadline,
        "arrived_by_deadline": bool(
            arrived is not None and limit is not None and arrived <= limit
        ),
    }


def contact_before_cancel(
    messages: Any,
    in_app_calls: Any,
    cancelled_at: Any,
    chat_log_complete: bool = True,
) -> Dict[str, Any]:
    """POL-NS-23: whether the driver messaged **and** called before cancelling.

    POL-NS-23: "Before cancelling for no-show, the driver must have sent at
    least one in-app chat message to the rider AND placed at least one in-app
    call to the rider (trip_record.in_app_calls, or a voice-call entry in the
    chat log), both before trip_record.cancelled_at."

    Four things the record makes easy to get wrong, and this function gets
    right:

    * the two call shapes. ``in_app_calls`` holds a call as
      ``placed_by``/``placed_at`` or as ``initiated_by``/``initiated_at``, and
      both are read;
    * the same call recorded twice. A call can sit in ``in_app_calls`` **and**
      appear as a ``VOICE_CALL_LOG`` entry in the chat log; the two are counted
      once, keyed on the second they were placed in, so a driver who called once
      has one call;
    * the channel. A ``VOICE_CALL_LOG`` entry is a call, not a message, so it is
      never counted as one -- and a message is a message whatever else it is;
    * the clock. A message or a call sent at or after ``cancelled_at`` is not
      "before cancelling" and is not counted.

    ``chat_log_complete`` is the caller's reading of the chat log's own
    admissibility. A MISSING or TRUNCATED log establishes nothing, and a count
    of zero read off it would be a fact the record does not carry: the block
    says ``complete: false`` and the counts travel beside it for what they are
    worth rather than as the answer.
    """
    cancel = _instant(cancelled_at)

    def _before(stamp: Any) -> bool:
        moment = _instant(stamp)
        return moment is not None and cancel is not None and moment < cancel

    def _second(stamp: Any) -> Optional[str]:
        moment = _instant(stamp)
        return None if moment is None else moment.replace(microsecond=0).isoformat()

    sent = [
        {"msg_id": message.get("msg_id"), "sent_at": message.get("sent_at")}
        for message in messages or []
        if isinstance(message, Mapping)
        and message.get("sender") == DRIVER_ROLE
        and message.get("channel") != CALL_LOG_CHANNEL
        and _before(message.get("sent_at"))
    ]

    calls: List[Dict[str, Any]] = []
    counted: set = set()
    for record in in_app_calls or []:
        if not isinstance(record, Mapping):
            continue
        actor = moment = None
        for who, when in CALL_ACTOR_FIELDS:
            if record.get(who) is not None and record.get(when) is not None:
                actor, moment = record.get(who), record.get(when)
                break
        if actor != DRIVER_ROLE or not _before(moment):
            continue
        key = _second(moment)
        if key in counted:
            continue
        counted.add(key)
        calls.append({
            "placed_at": moment,
            "answered": record.get("answered"),
            "duration_sec": record.get("duration_sec"),
            "source": CALLS_SOURCE,
        })

    for message in messages or []:
        if not isinstance(message, Mapping):
            continue
        if message.get("channel") != CALL_LOG_CHANNEL:
            continue
        if message.get("sender") != DRIVER_ROLE or not _before(message.get("sent_at")):
            continue
        key = _second(message.get("sent_at"))
        if key in counted:
            continue
        counted.add(key)
        calls.append({
            "placed_at": message.get("sent_at"),
            "answered": message.get("answered"),
            "duration_sec": message.get("duration_sec"),
            "source": CHAT_CALL_SOURCE,
        })

    return {
        "messages": sent,
        "calls": calls,
        "message_count": len(sent),
        "call_count": len(calls),
        "obligation_met": bool(sent) and bool(calls),
        "complete": bool(chat_log_complete) and isinstance(messages, list),
    }


def deviation(
    actual_distance_km: Any,
    optimal_distance_km: Any,
    tolerance_km: Any,
    ai_limit_km: Any,
    ai_limit_applied: Any,
    impaired: bool = False,
) -> Dict[str, Any]:
    """POL-RD-22 and POL-RD-25: the deviation between the recorded distances.

    POL-RD-22: "The deviation distance is the actual route distance minus the
    recommended route distance, in km: trip_record.actual_distance_km minus
    trip_record.optimal_distance_km, the platform's recorded distances. The GPS
    trace shows which route was taken and when; it is not used to re-measure the
    distance, because a sparse trace understates a route's length. A deviation
    of 1.0 km or less is within tolerance. Where either recorded distance is
    missing or impaired, the deviation cannot be established (POL-GEN-26)."

    Three readings the clause fixes:

    * the **recorded** distances govern, never the trace's own length;
    * the tolerance is inclusive -- "1.0 km or less is within tolerance" -- so a
      deviation of exactly the tolerance is within it;
    * a null distance, or an impaired record, leaves the deviation
      **unestablished**: the block says so and publishes no figure, because a
      deviation computed on an impaired record is the number the clause refuses
      to establish rather than a weaker version of it.

    POL-RD-25's own limb is v2.1 6.2's ceiling on the deviation, and the policy
    holds it in ``ai_ruling_max_deviation_applied``: the ceiling and whether the
    deviation crosses it are reported, and ``ai_limit_applied`` says whether the
    limb is switched on, so the reading travels beside the switch rather than
    being decided by it.

    The difference is taken in ``Decimal`` and written to two places, so
    ``24.8`` minus ``20.5`` is ``4.30`` and not ``4.300000000000001``.
    """
    if impaired or actual_distance_km is None or optimal_distance_km is None:
        return {"available": False, "reason": DEVIATION_NOT_MEASURABLE_REASON}

    actual = money._dec(actual_distance_km)
    optimal = money._dec(optimal_distance_km)
    difference = (actual - optimal).quantize(money.PLACES, rounding=ROUND_HALF_UP)
    tolerance = money._dec(tolerance_km)
    limit = money._dec(ai_limit_km)
    return {
        "available": True,
        "actual_distance_km": actual,
        "optimal_distance_km": optimal,
        "deviation_km": difference,
        "tolerance_km": tolerance,
        "within_tolerance": difference <= tolerance,
        "ai_limit_km": limit,
        "ai_limit_applied": bool(ai_limit_applied),
        "over_ai_limit": difference > limit,
    }


def messages_during_trip(
    messages: Any,
    started_at: Any,
    ended_at: Any,
) -> List[Dict[str, Any]]:
    """POL-RD-21: the in-app messages the two parties exchanged while the trip ran.

    POL-RD-21 requires the driver to inform the rider of a deviation "before or
    at the point of deviation", so *when* a message was sent is what the clause
    tests and the text is not: the texts stay in the chat log, and this is the
    index of who sent what, and when, between ``started_at`` and ``ended_at``.
    Both ends are inclusive -- a message at the moment the trip started or ended
    is during it -- and a call-log entry is not a message.
    """
    start = _instant(started_at)
    end = _instant(ended_at)
    if start is None or end is None:
        return []

    during: List[Dict[str, Any]] = []
    for message in messages or []:
        if not isinstance(message, Mapping):
            continue
        if message.get("channel") == CALL_LOG_CHANNEL:
            continue
        if message.get("sender") not in (DRIVER_ROLE, RIDER_ROLE):
            continue
        moment = _instant(message.get("sent_at"))
        if moment is None or moment < start or moment > end:
            continue
        during.append({
            "msg_id": message.get("msg_id"),
            "sender": message.get("sender"),
            "sent_at": message.get("sent_at"),
        })
    return during


def trace_summary(payload: Any) -> Dict[str, Any]:
    """POL-RD-22's informative trace figures, taken from the trace's own summary.

    POL-RD-22: "The GPS trace shows which route was taken and when; it is not
    used to re-measure the distance, because a sparse trace understates a
    route's length." The figures are therefore the trace's own recorded summary
    where it carries one -- ``point_count``, ``first_fix_at``, ``last_fix_at``,
    ``max_gap_sec`` and ``trace_distance_km`` -- and are derived from its points
    where it does not, so a brief built from a partial trace still says what the
    trace holds instead of inventing a distance. Nothing here decides anything;
    the deviation POL-RD-22 tests is measured from the trip record's recorded
    distances, not from this.
    """
    trace = payload if isinstance(payload, Mapping) else {}
    points = [fix for fix in (trace.get("points") or []) if isinstance(fix, Mapping)]
    gaps = [gap for gap in (trace.get("gaps") or []) if isinstance(gap, Mapping)]

    try:
        point_count = int(trace.get("point_count"))
    except (TypeError, ValueError):
        point_count = len(points)

    recorded_gap = _number(trace.get("max_gap_sec"))
    if recorded_gap is None:
        durations = [
            duration
            for duration in (_number(gap.get("duration_sec")) for gap in gaps)
            if duration is not None
        ]
        recorded_gap = max(durations) if durations else (0.0 if points else None)

    return {
        "point_count": point_count,
        "first_fix_at": trace.get("first_fix_at") or (points[0].get("ts") if points else None),
        "last_fix_at": trace.get("last_fix_at") or (points[-1].get("ts") if points else None),
        "max_gap_sec": recorded_gap,
        "trace_distance_km": trace.get("trace_distance_km"),
    }


def arrival_check(
    points: Any,
    pickup: Any,
    arrived_at: Any,
    window_sec: Any,
    radius_m: Any,
    accuracy_max_m: Any,
) -> Dict[str, Any]:
    """POL-NS-21's arrival test: whether the trace corroborates the arrival marker.

    The policy's own ``arrival_test`` block: "The driver is at the pickup when
    the trip record's arrival event is corroborated by the GPS trace within the
    arrival radius below." The test reads one fix: the one **nearest the pickup**
    among the fixes within ``window_sec`` of the arrival marker. It corroborates
    the marker when that fix lies inside the zone's arrival radius **and** its
    own reported accuracy passes the policy's filter.

    The filter applies **only to a fix that reports an accuracy** -- the
    policy's own ``arrival_test.accuracy_filter_applies`` sentence, which the
    caller reads and the brief publishes beside this reading. A fix that reports
    none is of unknown accuracy, and it is used at its **reported position**
    rather than dropped: dropping it would treat "no accuracy stated" as
    "inaccurate", which the policy does not say. The reading says which it was,
    so a corroboration that rests on an unreported accuracy is legible rather
    than silent.

    Where the marker, the pickup point, the window, the radius or the filter is
    absent, nothing is tested and the block says so by carrying no fix: the fact
    is unestablished rather than disproved, and POL-GEN-26 is the clause that
    decides what follows.
    """
    marker = _instant(arrived_at)
    located = (
        isinstance(pickup, Mapping)
        and pickup.get("lat") is not None
        and pickup.get("lng") is not None
    )
    if marker is None or not located or None in (window_sec, radius_m, accuracy_max_m):
        return {
            "arrived_at": arrived_at,
            "window_sec": window_sec,
            "arrival_radius_m": radius_m,
            "gps_accuracy_filter_m": accuracy_max_m,
            "nearest_fix": None,
            "accuracy_reported": None,
            "corroborated": False,
        }

    lat, lng = float(pickup["lat"]), float(pickup["lng"])
    limit = float(window_sec)
    best: Optional[Tuple[float, int, Mapping[str, Any]]] = None
    for index, fix in enumerate(points or []):
        if not isinstance(fix, Mapping):
            continue
        if fix.get("lat") is None or fix.get("lng") is None:
            continue
        moment = _instant(fix.get("ts"))
        if moment is None or abs((moment - marker).total_seconds()) > limit:
            continue
        distance = haversine_m(float(fix["lat"]), float(fix["lng"]), lat, lng)
        if best is None or distance < best[0]:
            best = (distance, index, fix)

    nearest = None
    accuracy_reported = None
    corroborated = False
    if best is not None:
        distance, index, fix = best
        accuracy = _number(fix.get("accuracy_m"))
        accuracy_reported = accuracy is not None
        nearest = {
            "index": index,
            "ts": fix.get("ts"),
            "distance_m": distance,
            "accuracy_m": accuracy,
        }
        corroborated = distance <= float(radius_m) and (
            accuracy is None or accuracy <= float(accuracy_max_m)
        )

    return {
        "arrived_at": arrived_at,
        "window_sec": window_sec,
        "arrival_radius_m": radius_m,
        "gps_accuracy_filter_m": accuracy_max_m,
        "nearest_fix": nearest,
        "accuracy_reported": accuracy_reported,
        "corroborated": corroborated,
    }


def justification_kind(advisory_type: Any, types_by_kind: Any) -> Optional[str]:
    """The kind of traffic event an advisory's ``type`` names, or ``None``.

    POL-RD-23 names three kinds in words -- "congestion, an incident or a
    closure" -- and the policy states which recorded ``traffic_advisory.type``
    values belong to each in ``thresholds.traffic_justification_types``. The
    advisory's type is compared with those values **exactly**, in upper case:
    both sides are the schema's own tokens, so a type the policy does not list
    names no kind and is reported as such rather than folded onto a word it
    merely resembles.

    What it does **not** do is decide that two different words mean the same
    thing. A type is a kind because the policy's map lists it under that kind,
    and a type the map does not carry is not one of the kinds the policy names;
    the block publishes both the type and the map so a reader can see the
    comparison the boolean rests on.

    ``types_by_kind`` is the policy's own mapping, handed in by the caller --
    this module still holds no policy value. An entry whose value is not a list
    of strings is skipped, which is how the mapping's own ``note`` is passed
    over without the note's key being named here.
    """
    if not isinstance(advisory_type, str):
        return None
    token = advisory_type.strip().upper()
    if not token or not isinstance(types_by_kind, Mapping):
        return None
    for kind, listed in types_by_kind.items():
        if not isinstance(listed, (list, tuple)):
            continue
        if any(
            isinstance(candidate, str) and candidate.strip().upper() == token
            for candidate in listed
        ):
            return kind
    return None


def advisory_justification(
    evidence_id: Any,
    payload: Any,
    types_by_kind: Any,
) -> Dict[str, Any]:
    """POL-RD-23: whether one traffic advisory justifies the reroute.

    POL-RD-23: "A reroute is traffic-justified only where traffic data for the
    recommended route segment at the trip time shows congestion, an incident or
    a closure: a TRAFFIC_ADVISORY that intersects the recommended route and
    overlaps the trip window. A driver's assertion of traffic with no such data
    does not justify the reroute."

    Three conditions, all of them required: the advisory intersects the
    recommended route, its window overlaps the trip, and its type is one of the
    recorded types the policy's ``traffic_justification_types`` map admits.
    ``types_by_kind`` is that map, read from the loaded policy by the caller --
    this module still holds no policy value -- and the kind the type matched is
    reported beside the boolean.

    A MISSING advisory has no payload at all, which is not the same as an
    advisory that fails the test: the block says which it is.
    """
    kinds = types_by_kind if isinstance(types_by_kind, Mapping) else {}
    if not isinstance(payload, Mapping) or not payload:
        return {
            "available": False,
            "reason": ADVISORY_ARTIFACT_MISSING_REASON.format(evidence_id),
            "justifies_reroute": False,
        }

    kind = payload.get("type")
    matched = justification_kind(kind, kinds)
    return {
        "available": True,
        "intersects_route": payload.get("intersects_route"),
        "overlaps_trip_window": payload.get("overlaps_trip_window"),
        "type": kind,
        "severity": payload.get("severity"),
        "admissible_types": kinds,
        "justification_kind": matched,
        "justifies_reroute": (
            payload.get("intersects_route") is True
            and payload.get("overlaps_trip_window") is True
            and matched is not None
        ),
    }
