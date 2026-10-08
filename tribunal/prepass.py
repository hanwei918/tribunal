"""Deterministic prepass for the Tribunal workspace.

Two jobs, both deliberately narrow:

``weight_for(issue_codes)``
    Reproduce the corpus's own weight arithmetic: given the issue codes the
    corpus attaches to an artifact, return the ``weight_multiplier`` the corpus
    declares for it. This does not replace the corpus's ``admissibility``
    object; it derives the same numbers from the codes. From policy version 3
    the table is passed in from the loaded policy's ``integrity`` block --
    ``weight_for(codes, weights=weights_from_policy(policy))`` -- and the single
    ``GPS_GAP`` tag is graded into POL-NS-08(b)'s three variants by
    :func:`gps_gap_variant` before it reaches the table.

``detect_schema_version_mismatch(case)``
    The one detector this workspace can justify. It compares an artifact's own
    ``schema_version`` against the case file's top-level value, which is the
    rule ``data/PUBLIC-CONTRACT.md`` states.

Nothing else is detected here. The firing rules for the other issue codes are
not documented anywhere in this workspace, and most codes fire once or twice,
so they cannot be inferred. Guessing them would silently corrupt the corpus's
own assessments. See
``docs/notes/2026-09-20-prepass-open-questions.md`` for the list of codes with
no derivable rule and the evidence each would need.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Weight arithmetic, derived empirically from the 204 artifacts.
#
# 10 of these values are read directly off artifacts that carry exactly one
# issue code, so they are observed, not chosen. The other 7 codes never appear
# alone; their values are constrained only by the products they form inside
# multi-code artifacts (0.39, 0.3, and a product that lands on the floor).
# Those 7 are marked INFERRED and are the reason the combination rule below is
# stated as a hypothesis rather than a certainty.
# --------------------------------------------------------------------------
CODE_WEIGHTS: Dict[str, float] = {
    # --- observed directly on single-code artifacts -------------------------
    "MISSING_ARTIFACT": 0.0,            # EV-ADVIS-00101-01 (case 101), 27 artifacts
    "CROSS_SOURCE_CONFLICT": 0.4,       # EV-TRIP-00112 (case 112), 3 artifacts
    "TRUNCATED_LOG": 0.6,               # EV-CHAT-00110 (case 110), 2 artifacts
    "PARTIAL_RECORD": 0.75,             # EV-FARE-00110 (case 110)
    "STALE_SNAPSHOT": 0.75,             # EV-DPROF-00105 (case 105)
    "CONTENT_REDACTED": 0.8,            # EV-CHAT-00205 (case 205)
    "LOW_SAMPLE_RATE": 0.8,             # EV-GPS-00206 (case 206)
    "LANGUAGE_AMBIGUITY": 0.85,         # EV-CHAT-00203 (case 203)
    "UNREAD_MESSAGE": 0.85,             # EV-CHAT-00202 (case 202), 2 artifacts
    "SCHEMA_VERSION_MISMATCH": 0.9,     # EV-DPROF-00202 (case 202)

    # --- INFERRED: never seen alone, fixed only by the products below -------
    "GPS_GAP": 0.6,                     # GPS_GAP * LOW_COVERAGE = 0.39
    "LOW_COVERAGE": 0.65,
    "GPS_DRIFT": 0.5,                   # GPS_DRIFT * IMPLAUSIBLE_SPEED = 0.3
    "IMPLAUSIBLE_SPEED": 0.6,
    "ADVISORY_UNCORROBORATED": 0.5,     # product lands on the floor
    "UNVERIFIED_SOURCE": 0.5,
    "CLOCK_SKEW": 0.5,                  # unconstrained by any observed product
}

# The lowest non-zero weight anywhere in the corpus is 0.25, and it appears
# only on multi-code artifacts, which is what a floor looks like.
FLOOR = 0.25

# A COMPLETE artifact carries no issues and keeps full weight.
FULL_WEIGHT = 1.0

# --------------------------------------------------------------------------
# The weights the policy carries (policy version 3)
#
# From version 3 on the pre-pass reads its weights from the loaded policy's
# ``integrity.weights`` block rather than from ``CODE_WEIGHTS`` above. The block
# holds the whole version-1 table plus the one change her notes describe: the
# single ``GPS_GAP`` tag is replaced by the three variants POL-NS-08(b) grades a
# gap into, so ``GPS_GAP`` itself is **not** a code the policy's table knows. A
# tag that reaches :func:`weight_for` with the policy's weights must therefore
# have been classified first, by :func:`gps_gap_variant`.
# --------------------------------------------------------------------------
INTEGRITY_KEY = "integrity"
INTEGRITY_WEIGHTS_KEY = "weights"
GPS_GAP_POLICY_THRESHOLD_KEY = "gps_gap_policy_threshold_sec"

# The tag the corpus uses for any sampling gap, and the three the policy grades
# it into.
GPS_GAP_CODE = "GPS_GAP"
GPS_GAP_SHORT_OR_OUTSIDE_WINDOW = "GPS_GAP_SHORT_OR_OUTSIDE_WINDOW"
GPS_GAP_LONG_INSIDE_WINDOW = "GPS_GAP_LONG_INSIDE_WINDOW"
GPS_GAP_STRADDLING_CANCELLATION = "GPS_GAP_STRADDLING_CANCELLATION"
GPS_GAP_VARIANTS = (
    GPS_GAP_SHORT_OR_OUTSIDE_WINDOW,
    GPS_GAP_LONG_INSIDE_WINDOW,
    GPS_GAP_STRADDLING_CANCELLATION,
)

# The field names a recorded gap carries. Named here so the classifier reads a
# gap by name rather than by position.
GAP_FROM_KEY = "from_ts"
GAP_TO_KEY = "to_ts"
GAP_DURATION_KEY = "duration_sec"
POINT_TIMESTAMP_KEY = "ts"

ISSUE_SEVERITIES: Dict[str, str] = {
    "MISSING_ARTIFACT": "BLOCKING",
    "ADVISORY_UNCORROBORATED": "MAJOR",
    "CLOCK_SKEW": "MAJOR",
    "CROSS_SOURCE_CONFLICT": "MAJOR",
    "GPS_DRIFT": "MAJOR",
    "GPS_GAP": "MAJOR",
    "GPS_GAP_SHORT_OR_OUTSIDE_WINDOW": "MAJOR",
    "GPS_GAP_LONG_INSIDE_WINDOW": "MAJOR",
    "GPS_GAP_STRADDLING_CANCELLATION": "MAJOR",
    "IMPLAUSIBLE_SPEED": "MAJOR",
    "LOW_COVERAGE": "MAJOR",
    "TRUNCATED_LOG": "MAJOR",
    "UNVERIFIED_SOURCE": "MAJOR",
    "CONTENT_REDACTED": "MINOR",
    "LANGUAGE_AMBIGUITY": "MINOR",
    "LOW_SAMPLE_RATE": "MINOR",
    "PARTIAL_RECORD": "MINOR",
    "SCHEMA_VERSION_MISMATCH": "MINOR",
    "STALE_SNAPSHOT": "MINOR",
    "UNREAD_MESSAGE": "MINOR",
}


class PrepassError(Exception):
    """Base class for prepass failures."""


class UnknownIssueCodeError(PrepassError):
    """A code was seen that this workspace has never observed.

    Its weight is unknown, so no weight is invented for it.
    """


# The corpus writes every weight to two decimal places. The product is computed
# in Decimal and quantised to the same convention, because the binary product is
# not the corpus's number: 0.8 * 0.75 is 0.6000000000000001 as a float, and a
# weight of 0.6000000000000001 would reach a brief, and a ruling, as if it were
# a measurement. This is the same defect as 0.8 * 6.00 == 4.800000000000001.
TWO_PLACES = Decimal("0.01")


def weight_for(
    issue_codes: Iterable[str], weights: Optional[Mapping[str, Any]] = None
) -> float:
    """Return the weight multiplier the corpus assigns to these issue codes.

    Derived rule, which reproduces all 45 non-COMPLETE artifacts exactly:

    * no codes -> ``1.0`` (the 159 COMPLETE artifacts);
    * a single code -> that code's own weight;
    * several codes -> the product of their weights, quantised to two decimal
      places and floored at ``0.25``;
    * a ``BLOCKING`` code (only ``MISSING_ARTIFACT``, weight ``0.0``) returns
      ``0.0`` without being floored.

    The product is taken in :class:`decimal.Decimal`, not in binary floating
    point. Every multi-code weight the corpus declares is a clean two-decimal
    figure -- 0.39, 0.3, 0.25 -- and the float product reproduces them only
    because none of those particular combinations happens to leave a residue.
    ``0.8 * 0.75`` does: it returns ``0.6000000000000001``, which is not the
    corpus's number and was not a number the corpus would ever have written.
    Quantising to the corpus's own two places removes the residue without
    moving any figure the corpus already declares.

    ``weights`` overrides the module's own table, and is how policy version 3
    reads every weight from the loaded policy: ``weight_for(codes,
    weights=weights_from_policy(policy))``. With no ``weights`` the behaviour is
    exactly what it was, so versions 1 and 2 are untouched.
    """
    codes = list(issue_codes)
    if not codes:
        return FULL_WEIGHT

    table = CODE_WEIGHTS if weights is None else weights
    weights_by_code: List[Decimal] = []
    for code in codes:
        if code not in table:
            raise UnknownIssueCodeError(
                "issue code {0!r} has no weight in {1}, so its weight is "
                "unknown".format(
                    code,
                    "this corpus" if weights is None else "the loaded policy's table",
                )
            )
        weights_by_code.append(Decimal(str(table[code])))

    # BLOCKING dominates. No artifact in the corpus combines MISSING_ARTIFACT
    # with another code, so this branch is unobserved; it is the only reading
    # consistent with a missing artifact weighing 0.0.
    if any(weight == 0 for weight in weights_by_code):
        return 0.0

    product = Decimal(1)
    for weight in weights_by_code:
        product *= weight
    product = product.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return float(max(Decimal(str(FLOOR)), product))


# --------------------------------------------------------------------------
# The policy's own weight table, and the GPS_GAP variants
# --------------------------------------------------------------------------
def weights_from_policy(policy: Mapping[str, Any]) -> Dict[str, Decimal]:
    """The weight table the loaded policy's ``integrity`` block carries.

    The block is POL-NS-08's own statement of every weight the pre-pass applies,
    so a version-3 brief reads its arithmetic from the policy rather than from
    the table above. The values are returned as ``Decimal`` so the caller's
    product is taken in decimal, exactly as :func:`weight_for` takes it.

    A policy with no ``integrity`` block, or one whose block carries no
    ``weights``, raises rather than falling back: a silent fallback to
    ``CODE_WEIGHTS`` would be the version-1 table wearing the version-3 policy's
    name.
    """
    integrity = policy.get(INTEGRITY_KEY)
    if not isinstance(integrity, Mapping):
        raise UnknownIssueCodeError(
            "the loaded policy carries no {0!r} block, so it states no weight "
            "table".format(INTEGRITY_KEY)
        )
    weights = integrity.get(INTEGRITY_WEIGHTS_KEY)
    if not isinstance(weights, Mapping) or not weights:
        raise UnknownIssueCodeError(
            "the loaded policy's {0!r} block carries no {1!r}".format(
                INTEGRITY_KEY, INTEGRITY_WEIGHTS_KEY
            )
        )
    return {str(code): Decimal(str(value)) for code, value in weights.items()}


def gps_gap_threshold_from_policy(policy: Mapping[str, Any]) -> Optional[int]:
    """``integrity.gps_gap_policy_threshold_sec``, or ``None`` where absent."""
    integrity = policy.get(INTEGRITY_KEY)
    if not isinstance(integrity, Mapping):
        return None
    value = integrity.get(GPS_GAP_POLICY_THRESHOLD_KEY)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _moment(stamp: Any) -> Optional[datetime]:
    """One timestamp, or ``None`` when it is absent or unreadable."""
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:
        return None


def gaps_from_points(points: Any) -> List[Dict[str, Any]]:
    """Every gap between consecutive fixes, computed from the trace's own points.

    A gap is one interval between two consecutive fixes, carrying its bounding
    timestamps and its length in seconds. Every interval is returned, not only
    the ones over a schema threshold, because the classifier that follows grades
    them itself. An interval whose endpoints cannot be read is skipped rather
    than guessed at.
    """
    if not isinstance(points, Sequence):
        return []
    stamps = [
        _moment(point.get(POINT_TIMESTAMP_KEY))
        for point in points
        if isinstance(point, Mapping)
    ]
    found: List[Dict[str, Any]] = []
    for earlier, later in zip(stamps, stamps[1:]):
        if earlier is None or later is None:
            continue
        found.append(
            {
                GAP_FROM_KEY: earlier.isoformat(),
                GAP_TO_KEY: later.isoformat(),
                GAP_DURATION_KEY: (later - earlier).total_seconds(),
            }
        )
    return found


def gps_gap_variant(
    gaps: Any, window: Optional[Tuple[Any, Any]], threshold_sec: Optional[int]
) -> str:
    """Which of POL-NS-08(b)'s three variants a trace's gaps fall into.

    ``window`` is the waiting window, ``(from_ts, to_ts)``, or ``None`` where the
    record fixes none -- which is a completed trip: the window runs from the
    arrival marker to the cancellation, so a trip that was never cancelled has
    no waiting window and no gap can be inside it.

    The three readings, in the order POL-NS-08(b) states them:

    * a gap of at most ``threshold_sec``, or one outside the window, is
      ``GPS_GAP_SHORT_OR_OUTSIDE_WINDOW`` -- POL-NS-08(b) makes a *long gap
      inside the waiting window* the policy impairment, so neither a short gap
      nor a gap elsewhere is one;
    * a longer gap that overlaps the window is ``GPS_GAP_LONG_INSIDE_WINDOW``;
    * a longer gap that contains the cancellation itself is
      ``GPS_GAP_STRADDLING_CANCELLATION``.

    A gap is "longer" when its duration is strictly greater than the threshold,
    which is how POL-NS-08(b) states it ("longer than 120 seconds"). A trace
    with no readable gap is short-or-outside: there is nothing that engages the
    limb.
    """
    limit = 120 if threshold_sec is None else int(threshold_sec)
    records = [gap for gap in (gaps or []) if isinstance(gap, Mapping)]
    start = end = None
    if window is not None:
        start, end = _moment(window[0]), _moment(window[1])
        if start is None or end is None:
            start = end = None

    long_and_inside = False
    for gap in records:
        duration = gap.get(GAP_DURATION_KEY)
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            continue
        if duration <= limit:
            continue
        from_ts = _moment(gap.get(GAP_FROM_KEY))
        to_ts = _moment(gap.get(GAP_TO_KEY))
        if from_ts is None or to_ts is None:
            continue
        if start is not None and from_ts <= end and to_ts >= start:
            # The gap overlaps the waiting window, so POL-NS-08(b) reaches it.
            if from_ts <= end <= to_ts:
                return GPS_GAP_STRADDLING_CANCELLATION
            long_and_inside = True

    return GPS_GAP_LONG_INSIDE_WINDOW if long_and_inside else GPS_GAP_SHORT_OR_OUTSIDE_WINDOW


def detect_schema_version_mismatch(case: Dict[str, Any]) -> List[str]:
    """Return the ids of artifacts whose own ``schema_version`` differs.

    The comparison is against the case file's top-level ``schema_version``,
    which is the one firing rule ``data/PUBLIC-CONTRACT.md`` states.
    """
    expected = case.get("schema_version")
    return [
        artifact["evidence_id"]
        for artifact in case.get("evidence", [])
        if artifact.get("schema_version") != expected
    ]


def issue_codes_of(artifact: Dict[str, Any]) -> List[str]:
    """Return an artifact's declared issue codes, or ``[]``."""
    admissibility = artifact.get("admissibility") or {}
    codes = admissibility.get("issues")
    return list(codes) if isinstance(codes, list) else []
