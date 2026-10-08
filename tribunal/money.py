"""Money arithmetic for the Tribunal workspace.

``WORKBUDDY-HANDOFF.md`` fixes the representation: **amounts use ``Decimal``**.
Nothing here uses ``float``. Every value is converted with
``Decimal(str(value))`` so the decimal literal the caller wrote is the decimal
the arithmetic sees, rather than the nearest binary approximation of it.

The architecture rule that governs ``facts.py`` governs this module too: **no
policy number appears as a literal**. Every rate, fee, ratio and threshold is
supplied by the caller from the loaded policy — ``fare_model`` on
``policy/route_deviation.json`` carries the fare constants and the rounding
rule, and ``fee_schedule`` on ``policy/no_show.json`` carries the no-show ones.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Any, Dict, List, Mapping, Optional, Tuple

# POL-RD-02's rounding rule: "the payable figure is rounded UP to the nearest
# SGD 0.05". Exposed as a default so the one-argument call works, and as a
# parameter so a caller can pass the loaded policy's own quantum instead.
QUANTUM_005 = Decimal("0.05")

ZERO = Decimal("0")

# The three outcomes POL-RD-02 can produce.
OUTCOME_NO_ACTION = "NO_ACTION"
OUTCOME_PARTIAL_REFUND = "PARTIAL_REFUND"
OUTCOME_FULL_REFUND = "FULL_REFUND"


def _dec(value: Any) -> Decimal:
    """Convert a value to ``Decimal`` without ever going through ``float``.

    ``Decimal(str(value))`` preserves the decimal literal: ``_dec(0.8)`` is
    ``Decimal("0.8")``, not ``Decimal("0.8000000000000000444...")``.

    An absent optional component — ``None`` — contributes nothing to a sum, so
    it converts to zero. A ``Decimal`` is passed through unchanged.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def round_up_005(amount: Any, quantum: Any = QUANTUM_005) -> Decimal:
    """Round ``amount`` UP to the nearest ``quantum`` (POL-RD-02).

    POL-RD-02: "the payable figure is rounded UP to the nearest SGD 0.05;
    intermediate values are not rounded." This function rounds one figure; it
    is the caller's job to apply it only to a computed payable, and never to a
    full refund of an amount that was already charged.
    """
    step = _dec(quantum)
    return (_dec(amount) / step).to_integral_value(rounding=ROUND_CEILING) * step


def recompute_metered_fare(
    base_fare: Any,
    per_km: Any,
    per_min: Any,
    optimal_distance_km: Any,
    optimal_duration_min: Any,
    surge_multiplier: Any,
    platform_fee: Any,
    optimal_route_erp: Any,
    fixed_surcharges: Any,
    waiting_time_fee: Any,
    promo_discount: Any,
) -> Decimal:
    """POL-RD-02's ``recomputed_fare``, with every constant passed in.

    POL-RD-02 states the formula:

        "Compute recomputed_fare = ((3.80 + 0.75 x optimal_distance_km + 0.28 x
        optimal_duration_min) x the surge_multiplier recorded on the
        FARE_BREAKDOWN) + 0.80 platform fee + ERP and toll charges for gantries
        lying on the optimal route + any fixed surcharge already itemised in
        the fare_breakdown and properly chargeable ... + fare_breakdown
        waiting_time_fee - fare_breakdown.promo_discount."

    The four fare constants in that expression are read from the loaded
    policy's ``fare_model`` (``base_fare``, ``per_km``, ``per_min``,
    ``platform_fee``) and arrive here as arguments, as do the trip's own
    distance and duration and every fare component. This function applies no
    rounding: POL-RD-02 says intermediate values are not rounded.

    It is the total of :func:`metered_fare_components`, so the itemised
    breakdown a ruling must state and the single figure that breakdown totals
    to cannot drift apart: there is one expression, not two.
    """
    return metered_fare_components(
        base_fare,
        per_km,
        per_min,
        optimal_distance_km,
        optimal_duration_min,
        surge_multiplier,
        platform_fee,
        optimal_route_erp,
        fixed_surcharges,
        waiting_time_fee,
        promo_discount,
    )["recomputed_fare"]


def _refund_decision(
    charged_total: Any,
    recomputed_fare: Any,
    de_minimis: Any,
    full_refund_ratio: Any,
) -> Tuple[Decimal, str]:
    """Return ``(payable_refund, outcome)`` for POL-RD-02.

    POL-RD-02: "Refund = charged_total - recomputed_fare, floored at zero, and
    the payable figure is rounded UP to the nearest SGD 0.05 ... If the refund
    is below SGD 0.50 the outcome is NO_ACTION as de minimis. If the refund is
    90% or more of charged_total, issue FULL_REFUND instead of a partial."

    The two rules act on different things, and this is where they are easy to
    get wrong:

    * the round-UP rule applies to a **computed payable** — a partial refund;
    * a **full refund of an amount already charged** is not a computed payable.
      It is the charge itself, returned. Rounding it up would invent money:
      a charged total of 65.13 must come back as 65.13, never as 65.15.
    """
    charged = _dec(charged_total)
    refund = charged - _dec(recomputed_fare)
    if refund < ZERO:
        refund = ZERO

    if refund < _dec(de_minimis):
        return ZERO, OUTCOME_NO_ACTION

    if refund >= _dec(full_refund_ratio) * charged:
        return charged, OUTCOME_FULL_REFUND

    return round_up_005(refund), OUTCOME_PARTIAL_REFUND


def refund_for(
    charged_total: Any,
    recomputed_fare: Any,
    de_minimis: Any,
    full_refund_ratio: Any,
) -> Decimal:
    """The payable refund, floored at zero, with both POL-RD-02 rules applied.

    Returns the amount only. Use ``refund_outcome`` for the ruling value that
    goes with it.
    """
    return _refund_decision(charged_total, recomputed_fare, de_minimis, full_refund_ratio)[0]


def refund_outcome(
    charged_total: Any,
    recomputed_fare: Any,
    de_minimis: Any,
    full_refund_ratio: Any,
) -> str:
    """The ruling value POL-RD-02 produces: NO_ACTION, PARTIAL_REFUND or FULL_REFUND."""
    return _refund_decision(charged_total, recomputed_fare, de_minimis, full_refund_ratio)[1]


# --------------------------------------------------------------------------
# POL-RD-02: the metered recomputation, itemised
#
# The clause states the formula as a sum of named lines and then compares the
# total with what was charged, and it requires the ruling to "state
# charged_total, recomputed_fare and the refund on separate lines". A single
# total answers "what is the fare"; a ruling that must show its working needs
# the lines as well, which is what this section returns. Every rate and fee
# still arrives as an argument.
# --------------------------------------------------------------------------

# Two places. Not a policy number: it is the number of decimal places the
# currency is written to, and it is used only to write a figure the policy
# does not route through the round-UP rule.
PLACES = Decimal("0.01")


def metered_fare_components(
    base_fare: Any,
    per_km: Any,
    per_min: Any,
    optimal_distance_km: Any,
    optimal_duration_min: Any,
    surge_multiplier: Any,
    platform_fee: Any,
    optimal_route_erp: Any,
    fixed_surcharges: Any,
    waiting_time_fee: Any,
    promo_discount: Any,
) -> Dict[str, Decimal]:
    """POL-RD-02's recomputed fare, with every line of the expression itemised.

    Same arithmetic as :func:`recompute_metered_fare`, which is now this
    function's total, so there is one implementation rather than two.

    The surge multiplies the base fare, the distance charge and the time charge
    and nothing else -- ``fare_model.surge_multiplier_applies_to`` names exactly
    those three lines, and the ERP is a pass-through that is never surged. The
    breakdown therefore reports the un-surged sum, the uplift and the surged
    sum separately, so a reader can see that the ERP and the surcharges entered
    outside the multiplier.

    No rounding is applied: POL-RD-02 says intermediate values are not rounded.
    """
    base = _dec(base_fare)
    distance_charge = _dec(per_km) * _dec(optimal_distance_km)
    time_charge = _dec(per_min) * _dec(optimal_duration_min)
    distance_and_time = base + distance_charge + time_charge

    surge = _dec(surge_multiplier)
    surged = distance_and_time * surge

    platform = _dec(platform_fee)
    erp = _dec(optimal_route_erp)
    surcharges = _dec(fixed_surcharges)
    waiting = _dec(waiting_time_fee)
    promo = _dec(promo_discount)

    return {
        "base_fare": base,
        "distance_charge": distance_charge,
        "time_charge": time_charge,
        "distance_and_time": distance_and_time,
        "surge_multiplier": surge,
        "surge_uplift": surged - distance_and_time,
        "surged_distance_and_time": surged,
        "platform_fee": platform,
        "optimal_route_erp": erp,
        "fixed_surcharges": surcharges,
        "waiting_time_fee": waiting,
        "promo_discount": promo,
        "recomputed_fare": surged + platform + erp + surcharges + waiting - promo,
    }


def erp_lines(lines: Any) -> Dict[str, Any]:
    """Itemise the fare's ERP gantry lines and total them by route.

    POL-RD-02 adds "ERP and toll charges for gantries lying on the optimal
    route" and nothing else, so the total that enters the recomputation is the
    on-optimal one. The off-optimal lines are totalled separately rather than
    dropped, because they are the pass-through POL-RD-09 speaks to and a ruling
    that must not count them twice still has to be able to name them.

    ``on_optimal_route`` is read as a flag: a line counts as on the optimal
    route only when the fare breakdown says so in terms. A line whose flag is
    absent or null is not silently promoted to the optimal route.
    """
    itemised: List[Dict[str, Any]] = []
    on_optimal = ZERO
    off_optimal = ZERO

    for line in lines or []:
        if not isinstance(line, Mapping):
            continue
        amount = _dec(line.get("amount_sgd"))
        flag = line.get("on_optimal_route") is True
        if flag:
            on_optimal += amount
        else:
            off_optimal += amount
        itemised.append({
            "gantry_name": line.get("gantry_name"),
            "amount_sgd": amount,
            "on_optimal_route": flag,
        })

    return {
        "lines": itemised,
        "on_optimal_route_total": on_optimal,
        "off_optimal_route_total": off_optimal,
        "total": on_optimal + off_optimal,
    }


def refund_working(
    charged_total: Any,
    recomputed_fare: Any,
    de_minimis: Any,
    quantum: Any = QUANTUM_005,
) -> Dict[str, Any]:
    """POL-RD-02's refund, with every intermediate figure the ruling must state.

    Returns the charge, the recomputed fare, the refund **before** rounding,
    whether that refund is below the de-minimis figure, the refund as a share of
    the charge, and the payable figure the round-UP rule produces for a partial
    refund.

    Three things it deliberately does not do:

    * It does not apply the full-refund share. That share is stated in
      POL-RD-02's prose and is not a structured field of the loaded policy, so
      the caller publishes it as not structured and the share computed here is
      the input for a reader who applies the clause; nothing here decides it.
    * It does not round a full refund, because a full refund is not a computed
      payable -- see :func:`_refund_decision`. ``full_refund`` reports the
      charge itself, unrounded, for that case.
    * It does not decide which clause applies. A refund the arithmetic produces
      is not a refund the policy orders.
    """
    charged = _dec(charged_total)
    fare = _dec(recomputed_fare)

    before = charged - fare
    if before < ZERO:
        before = ZERO

    threshold = _dec(de_minimis)
    below = before < threshold
    share = None if charged == ZERO else before / charged

    return {
        "charged_total": charged,
        "recomputed_fare": fare,
        "refund_before_rounding": before,
        "de_minimis": threshold,
        "below_de_minimis": below,
        "refund_share_of_charged": share,
        "quantum": _dec(quantum),
        "payable": ZERO if below else round_up_005(before, quantum),
        "full_refund": charged,
    }


def payable_string(value: Any, places: Any = PLACES) -> str:
    """A money amount written as a decimal string with two places.

    A ruling states money in SGD to two places, and the brief publishes the
    figures a ruling can order in exactly that form. This is not the round-UP
    rule: ``round_up_005`` rounds a computed payable UP to a quantum, while
    this writes an amount that is already a currency amount to the places the
    currency is written to. Nothing here is a policy number; ``places`` is a
    representation precision.
    """
    return str(_dec(value).quantize(_dec(places), rounding=ROUND_HALF_UP))


def upfront_quote_comparison(charged_total: Any, quoted_fare: Any) -> Dict[str, Decimal]:
    """POL-RD-11: the quoted fare against what was charged, and the difference.

    On an upfront-quoted trip POL-RD-02 does not run and no distance-or-time
    refund is available, so this module computes none: the only arithmetic the
    clause states is what was charged over what was quoted, and that is what
    this returns.

    POL-RD-11(a) compares the charge against the quote **plus** the pass-through
    and statutory lines properly chargeable under POL-RD-09, and "properly
    chargeable" is a question about which lines belong there. That question is
    the judge's, so the difference here is the plain one and the lines travel
    beside it.
    """
    charged = _dec(charged_total)
    quoted = _dec(quoted_fare)
    return {
        "quoted_fare": quoted,
        "charged_total": charged,
        "difference": charged - quoted,
    }


# --------------------------------------------------------------------------
# POL-RD-03: the closure-adjusted optimal route
#
# The clause states the cap and the duration derivation as prose, and says why
# it writes them out: "the Judge cannot reproduce the adjusted optimal without
# them and must not invent one". The cap is therefore computed here, with the
# cap ratio and the tolerance supplied by the caller from the loaded clause
# text -- the same route ``_deviation_thresholds`` and ``_no_show_thresholds``
# already take for POL-RD-01 and POL-NS-06. Neither constant is a literal in
# this module.
# --------------------------------------------------------------------------

# One decimal place for a derived duration. Not a policy number: it is the
# precision POL-RD-03 writes the scaled duration to, used only to write a
# figure the policy does not route through the round-UP rule.
DURATION_PLACES = Decimal("0.1")

# Where the adjusted duration came from. The clause names two sources and
# prefers the stored one.
DURATION_SCALED = "scaled_from_booked_optimal"
DURATION_AMENDED = "amended_optimal_duration_min"
DURATION_UNKNOWN = "undetermined"


def justified_excess(
    measured_excess_km: Any,
    shortest_lawful_alternative_km: Any,
    optimal_distance_km: Any,
    cap_ratio: Any,
    tolerance_km: Any,
) -> Dict[str, Any]:
    """POL-RD-03's cap on the excess a road closure exonerates.

    POL-RD-03: "The justified excess is the lesser of the measured excess, or
    130% of the ADDITIONAL distance of the shortest lawful alternative over the
    booked optimal route, plus 1.0 km of tolerance - that is,
    min(measured_excess_km, 1.30 x (shortest_lawful_alternative_km -
    optimal_distance_km) + 1.00)".

    The cap is on ADDITIONAL distance, not on route length: the additional
    distance is the alternative minus the booked optimal, and the ratio and the
    tolerance are the clause's own prose values, passed in by the caller. Both
    are exposed in the result so a reader can see the cap the clause produced
    rather than only the excess that survived it.

    The expression is returned exactly as the clause writes it. The clause
    states no floor on the additional distance, so none is applied here; where
    the alternative is not longer than the booked optimal the cap the clause's
    own expression yields is reported, and ``additional_distance_km`` shows the
    reader why.
    """
    measured = _dec(measured_excess_km)
    alternative = _dec(shortest_lawful_alternative_km)
    optimal = _dec(optimal_distance_km)

    additional = alternative - optimal
    cap = _dec(cap_ratio) * additional + _dec(tolerance_km)
    justified = measured if measured < cap else cap

    return {
        "measured_excess_km": measured,
        "shortest_lawful_alternative_km": alternative,
        "optimal_distance_km": optimal,
        "additional_distance_km": additional,
        "cap_ratio": _dec(cap_ratio),
        "tolerance_km": _dec(tolerance_km),
        "cap_km": cap,
        "justified_excess_km": justified,
    }


def closure_adjusted_route(
    optimal_distance_km: Any,
    optimal_duration_min: Any,
    justified_excess_km: Any,
    amended_optimal_duration_min: Any = None,
) -> Dict[str, Any]:
    """POL-RD-03's closure-adjusted optimal distance and duration.

    POL-RD-03: "The closure-adjusted optimal distance is
    trip_record.optimal_distance_km + justified_excess_km. Its duration is
    trip_record.optimal_duration_min scaled by the ratio of the adjusted
    optimal distance to the booked optimal distance, rounded to 1 decimal
    place; where trip_record.amended_optimal_duration_min is non-null that
    stored figure governs instead."

    The stored figure wins where it is present, because the clause says so: a
    duration the record already carries must not be replaced by one re-derived
    here. The scaling runs only where there is a booked optimal distance to
    scale by; a zero booked distance leaves the duration undetermined rather
    than dividing by zero, and ``duration_source`` says which of the three
    cases produced the figure.
    """
    optimal = _dec(optimal_distance_km)
    adjusted_distance = optimal + _dec(justified_excess_km)

    if amended_optimal_duration_min is not None:
        adjusted_duration = _dec(amended_optimal_duration_min)
        source = DURATION_AMENDED
    elif optimal == ZERO:
        adjusted_duration = None
        source = DURATION_UNKNOWN
    else:
        adjusted_duration = (
            _dec(optimal_duration_min) * adjusted_distance / optimal
        ).quantize(DURATION_PLACES, rounding=ROUND_HALF_UP)
        source = DURATION_SCALED

    return {
        "optimal_distance_km": optimal,
        "optimal_duration_min": _dec(optimal_duration_min),
        "justified_excess_km": _dec(justified_excess_km),
        "adjusted_optimal_distance_km": adjusted_distance,
        "adjusted_optimal_duration_min": adjusted_duration,
        "duration_source": source,
    }


# --------------------------------------------------------------------------
# POL-NS-01 and POL-NS-07: the no-show fee and who receives what
# --------------------------------------------------------------------------

# The dimension that produced a schedule fee. A tie is named as a tie rather
# than resolved to one of the two dimensions: POL-NS-01 requires the ruling to
# say which dimension produced the figure, and where the two prescribe the
# same amount neither is the greater.
DIMENSION_ZONE_CLASS = "zone_class"
DIMENSION_VEHICLE_TIER = "vehicle_tier"
DIMENSION_TIE = "tie"


def schedule_fee(zone_class_fee: Any, vehicle_tier_fee: Any) -> Tuple[Decimal, str]:
    """POL-NS-01's chargeable fee: the GREATER of the two, and which one it was.

    ``fee_schedule.resolution_rule``: "The chargeable cancellation fee is the
    GREATER of the zone-class fee and the vehicle-tier fee. Where the two
    prescribe different amounts, neither is ignored: the higher governs, and
    the ruling must say which dimension produced it."

    Both fees are read from ``fee_schedule`` by the caller, for the trip's own
    ``pickup_zone_class`` and ``vehicle_type``. Neither is a literal here, and
    neither is a default: an absent fee is the caller's problem, not something
    to substitute.
    """
    zone = _dec(zone_class_fee)
    tier = _dec(vehicle_tier_fee)
    if zone > tier:
        return zone, DIMENSION_ZONE_CLASS
    if tier > zone:
        return tier, DIMENSION_VEHICLE_TIER
    return zone, DIMENSION_TIE


# --------------------------------------------------------------------------
# The platform parameters in force (policy version 3)
#
# From version 3 on, the no-show fee, the free waiting period and the
# waiting-time fee are read from ``trip_record.platform_policy`` -- the block
# the brief publishes as ``platform_policy_in_force`` -- rather than from the
# version-1 ``fee_schedule`` tables. POL-NS-01: "the cancellation fee stands, in
# the net amount fixed by ``fee_schedule.resolution_rule``:
# ``platform_policy.cancellation_fee_sgd`` where the record carries it". The
# accessors below are the only place that shape is known, so no other module has
# to spell the field names out.
#
# Each returns ``None`` when the block does not carry the field, so a caller
# falls back to the loaded policy's own default rather than to a literal here.
# --------------------------------------------------------------------------
PLATFORM_POLICY_KEY = "platform_policy"
CANCELLATION_FEE_KEY = "cancellation_fee_sgd"
RIDER_GROSS_FEE_KEY = "rider_gross_cancellation_fee_sgd"
FREE_WAIT_KEY = "free_wait_sec"
WAITING_FEE_KEY = "waiting_fee_sgd"


def _block_field(platform_policy: Any, key: str) -> Any:
    """One field of a platform-policy block, or ``None`` for anything else."""
    if not isinstance(platform_policy, Mapping):
        return None
    return platform_policy.get(key)


def fee_in_force(platform_policy: Any) -> Optional[Decimal]:
    """The net cancellation fee the block states, or ``None``.

    POL-NS-01's fee limb. ``None`` means the block names no fee, which is the
    caller's cue to fall back to ``fee_schedule.defaults``; no figure is
    substituted here.
    """
    value = _block_field(platform_policy, CANCELLATION_FEE_KEY)
    return None if value is None else _dec(value)


def gross_fee_in_force(platform_policy: Any) -> Optional[Decimal]:
    """The rider-side gross figure the block names, for POL-NS-08(d), or ``None``.

    POL-NS-08(d): the ``fare_breakdown`` cancellation-fee line may equal the net
    or, where the block names one, the gross. The gross figure is used for that
    reconciliation only -- POL-NS-07 compensates on the net, never on this.
    """
    value = _block_field(platform_policy, RIDER_GROSS_FEE_KEY)
    return None if value is None else _dec(value)


def free_wait_in_force(platform_policy: Any) -> Optional[int]:
    """POL-NS-01(c)'s free waiting period: the block's ``free_wait_sec``.

    ``None`` when the block names none, so the caller uses
    ``fee_schedule.defaults.free_wait_sec``. POL-NS-05(i) and POL-NS-06 read the
    waiting period from POL-NS-01(c), so both take their figure from here.
    """
    value = _block_field(platform_policy, FREE_WAIT_KEY)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def waiting_fee_in_force(platform_policy: Any) -> Optional[Decimal]:
    """POL-NS-10(d)'s waiting-time fee: the block's ``waiting_fee_sgd``, or None."""
    value = _block_field(platform_policy, WAITING_FEE_KEY)
    return None if value is None else _dec(value)


def fee_arithmetic(
    schedule_fee_amount: Any,
    fee_charged: Any,
    driver_compensation_rate: Any,
    goodwill_rate: Any,
    gross_fee: Any = None,
) -> Dict[str, Decimal]:
    """The no-show fee, the fee charged, and the two payments computed on it.

    POL-NS-07 compensates the driver at a share of "the cancellation fee
    itemised in fare_breakdown", and POL-NS-03(ii) pays platform goodwill at a
    share of the fee as well, so both are computed on the **charged** figure
    rather than on the schedule figure. The difference between the two is
    reported beside them: where the schedule fee and the itemised line disagree
    that disagreement is a finding in its own right (POL-NS-08(d)), and a
    reader cannot see it if only one of them is published.

    ``gross_fee`` is POL-NS-08(d)'s other accepted figure. Where it is given and
    the charged line equals it, the difference is zero: the clause says the line
    "may equal either the net or ... the gross amount", so a gross line is a
    reconciled line and not a discrepancy. A gross line does not change either
    payment -- POL-NS-07 computes on the net in force and never on the rider's
    gross figure.

    Neither payment is put through the round-UP rule. ``fare_model.rounding``
    names POL-RD-02, POL-RD-09, POL-RD-04 and POL-RD-11, and neither of these
    two is any of those; both are written to two places instead.
    """
    schedule = _dec(schedule_fee_amount)
    charged = _dec(fee_charged)
    difference = charged - schedule
    if gross_fee is not None and charged == _dec(gross_fee):
        difference = ZERO
    return {
        "schedule_fee": schedule,
        "fee_charged": charged,
        "difference": difference,
        "driver_compensation": (_dec(driver_compensation_rate) * charged).quantize(
            PLACES, rounding=ROUND_HALF_UP
        ),
        "goodwill": (_dec(goodwill_rate) * charged).quantize(PLACES, rounding=ROUND_HALF_UP),
    }


# --------------------------------------------------------------------------
# Canonical serialisation
#
# Once the loader parses JSON numbers with ``parse_float=Decimal``, a bundle or
# a brief holds Decimals, and ``json.dumps`` raises ``TypeError`` on them. The
# fix must not be to convert them back to ``float`` — that would undo the whole
# point of parsing them as Decimals in the first place, and would silently
# reintroduce binary rounding.
#
# So Decimals are emitted as JSON **numbers**, carrying their own literal.
# ``json.dumps`` cannot do that through ``default=``, because a value returned
# from ``default`` is then serialised normally (a ``str`` would be quoted, a
# ``float`` would round). Each Decimal is therefore swapped for a placeholder
# token before dumping, and the token — in exactly the escaped form
# ``json.dumps`` gave it — is replaced by the decimal literal afterwards. Every
# other type is serialised by ``json.dumps`` itself, so escaping, ordering and
# separators are unchanged.
# --------------------------------------------------------------------------
_TOKEN_PREFIX = "\u0000decimal\u0000"


def _decimal_literal(value: Decimal) -> str:
    """The JSON number literal for a Decimal.

    ``str`` gives the shortest exact literal the value was written with:
    ``Decimal("8.0")`` becomes ``8.0``, not ``8`` and not ``8.000000000000001``.
    """
    if not value.is_finite():
        raise ValueError("cannot serialise a non-finite Decimal: {0!r}".format(value))
    return str(value)


def _assert_prefix_unused(node: Any, prefix: str) -> None:
    """Refuse to serialise when real data already contains the token prefix."""
    if isinstance(node, str):
        if prefix in node:
            raise ValueError(
                "a string value contains the Decimal placeholder prefix {0!r}; "
                "canonical serialisation would corrupt it".format(prefix)
            )
    elif isinstance(node, dict):
        for key, value in node.items():
            _assert_prefix_unused(key, prefix)
            _assert_prefix_unused(value, prefix)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _assert_prefix_unused(value, prefix)


def _swap_decimals(node: Any, tokens: Dict[str, str], prefix: str) -> Any:
    """Return a copy of ``node`` with every Decimal replaced by a token string."""
    if isinstance(node, Decimal):
        token = "{0}{1}\u0000".format(prefix, len(tokens))
        tokens[token] = _decimal_literal(node)
        return token
    if isinstance(node, dict):
        return {key: _swap_decimals(value, tokens, prefix) for key, value in node.items()}
    if isinstance(node, (list, tuple)):
        return [_swap_decimals(value, tokens, prefix) for value in node]
    return node


def dumps_canonical(obj: Any) -> str:
    """Serialise ``obj`` exactly as the contract's Deterministic serialisation section requires.

    The contract fixes the parameters: UTF-8 JSON with ``ensure_ascii=False``,
    ``sort_keys=True`` and ``separators=(",", ":")``. The same inputs must
    produce the same bytes across repeated runs.

    Decimals are written as JSON numbers carrying their own literal, so a value
    that was written ``8.0`` in the corpus is serialised as ``8.0`` — not as
    ``"8.0"`` and not as a float.
    """
    _assert_prefix_unused(obj, _TOKEN_PREFIX)

    tokens: Dict[str, str] = {}
    prepared = _swap_decimals(obj, tokens, _TOKEN_PREFIX)
    text = json.dumps(prepared, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    for token, literal in tokens.items():
        text = text.replace(json.dumps(token), literal)
    return text


def canonical_sha256(obj: Any) -> str:
    """The SHA-256 hex digest of ``obj``'s canonical serialisation."""
    return hashlib.sha256(dumps_canonical(obj).encode("utf-8")).hexdigest()
