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
