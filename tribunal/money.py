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
from decimal import Decimal, ROUND_CEILING
from typing import Any, Dict, Tuple

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
    """
    distance_and_time = (
        _dec(base_fare)
        + _dec(per_km) * _dec(optimal_distance_km)
        + _dec(per_min) * _dec(optimal_duration_min)
    )

    return (
        distance_and_time * _dec(surge_multiplier)
        + _dec(platform_fee)
        + _dec(optimal_route_erp)
        + _dec(fixed_surcharges)
        + _dec(waiting_time_fee)
        - _dec(promo_discount)
    )


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
