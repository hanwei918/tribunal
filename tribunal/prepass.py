"""Deterministic prepass for the Tribunal workspace.

Two jobs, both deliberately narrow:

``weight_for(issue_codes)``
    Reproduce the corpus's own weight arithmetic: given the issue codes the
    corpus attaches to an artifact, return the ``weight_multiplier`` the corpus
    declares for it. This does not replace the corpus's ``admissibility``
    object; it derives the same numbers from the codes.

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

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List

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

ISSUE_SEVERITIES: Dict[str, str] = {
    "MISSING_ARTIFACT": "BLOCKING",
    "ADVISORY_UNCORROBORATED": "MAJOR",
    "CLOCK_SKEW": "MAJOR",
    "CROSS_SOURCE_CONFLICT": "MAJOR",
    "GPS_DRIFT": "MAJOR",
    "GPS_GAP": "MAJOR",
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


def weight_for(issue_codes: Iterable[str]) -> float:
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
    """
    codes = list(issue_codes)
    if not codes:
        return FULL_WEIGHT

    weights: List[Decimal] = []
    for code in codes:
        try:
            weights.append(Decimal(str(CODE_WEIGHTS[code])))
        except KeyError as exc:
            raise UnknownIssueCodeError(
                "issue code {0!r} has never been observed in this corpus, so its "
                "weight is unknown".format(code)
            ) from exc

    # BLOCKING dominates. No artifact in the corpus combines MISSING_ARTIFACT
    # with another code, so this branch is unobserved; it is the only reading
    # consistent with a missing artifact weighing 0.0.
    if any(weight == 0 for weight in weights):
        return 0.0

    product = Decimal(1)
    for weight in weights:
        product *= weight
    product = product.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return float(max(Decimal(str(FLOOR)), product))


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
