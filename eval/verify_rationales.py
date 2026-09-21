"""Audit the answer key's hand-written rationales against this package's arithmetic.

WHY THIS EXISTS
---------------
Each ``ground_truth`` block in ``eval/answers/ground_truth.json`` carries a long
``rationale`` written by hand and dense with derived numbers: distances,
percentages, fare line items, rounded refunds. Nothing checked them. The
dataset validator's 21 checks mention ``rationale`` exactly once, inside the
list of keys check 20 forbids from leaking, and never verify its contents.

This key is the project's only independent measurement, and it is about to be
frozen and used to score three models. A hand-written figure that is wrong, and
that led to a wrong ``expected_ruling``, would corrupt every accuracy number the
submission reports, silently. So the key is audited before it is frozen.

THE DIRECTION OF DEPENDENCY
---------------------------
``eval/`` may import from ``tribunal/``. Nothing under ``tribunal/`` may ever
read ``eval/``. That is the boundary ``WORKBUDDY-SCOPE.md`` sets, and this
module does not weaken it: it is a consumer of the package, never a dependency
of it.

TWO DIFFERENT KINDS OF CHECK, KEPT APART
----------------------------------------
**A. Internal consistency** — ``check_internal_consistency``. A rationale can be
checked against itself without knowing any external truth. Where it states an
explicit sum the terms must add to the stated total; where it says one figure
was rounded to another the pair must satisfy ``money.round_up_005``; and the
figure the rationale arrives at must be the block's own expected amount. A
failure here is unambiguous — a sum that does not add up is wrong regardless of
what the case data says. These are asserted by
``tests/test_rationale_consistency.py``.

**B. External reconciliation** — ``reconcile_case`` / ``render_report``. For
each case, derived quantities are computed independently through
``tribunal.facts`` and ``tribunal.money`` and reconciled against the numbers in
that case's prose, in both directions. This is a **report, not a test**, and it
deliberately does not parse every number out of the prose: the rationales are
natural language, and a regex that mis-attributes a figure would generate noise
that buries a real discrepancy. A person reads the report once and judges.

**A mismatch in part B does NOT establish which side is wrong.** The rationale
may be wrong, or this package's computation may be wrong, and the second would
be the more serious finding. The report says so at the top, and no code here
decides it.

ARITHMETIC
----------
Every figure this module computes, compares or evaluates is a ``Decimal``.
``tribunal.facts`` returns ``float`` (haversine geometry), so its output is
converted with ``Decimal(str(value))`` — never ``Decimal(float)``, which would
import binary noise, and never by computing in ``float`` here. A check that
itself computed ``4.800000000000001`` would report a false discrepancy.

NOTHING IS REPAIRED
-------------------
If a discrepancy is found, it is reported. No rationale is edited, no expected
value is edited, and no computation is adjusted to agree with the prose. The
freeze rule in ``START-HERE.md`` governs the key, and the same principle governs
the code: a disagreement between the two is a measurement, and repairing either
side before a human has adjudicated it destroys the measurement.

Usage::

    python -m eval.verify_rationales                 # write the report
    python -m eval.verify_rationales --stdout        # print it instead
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ``eval/`` is allowed to read the package. The reverse is forbidden.
from tribunal import facts, loader, money  # noqa: E402

ANSWER_KEY_PATH = PROJECT_ROOT / "eval" / "answers" / "ground_truth.json"
REPORT_PATH = PROJECT_ROOT / "docs" / "notes" / "2026-09-21-rationale-audit.md"

ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")

# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_answer_key() -> List[Dict[str, Any]]:
    """The answer key, as a list of records."""
    with ANSWER_KEY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def answer_key_by_case() -> Dict[int, Dict[str, Any]]:
    """The answer key keyed by ``case_no``."""
    return {record["case_no"]: record for record in load_answer_key()}


def case_numbers() -> List[int]:
    """Every case number the manifest lists, in manifest order."""
    with (PROJECT_ROOT / "data" / "index.json").open("r", encoding="utf-8") as handle:
        return [entry["case_no"] for entry in json.load(handle)]


def expected_figure(record: Dict[str, Any]) -> Optional[Decimal]:
    """The money figure the block says the ruling arrives at, or ``None``.

    ``expected_driver_compensation_sgd`` is the relevant figure where the ruling
    is DRIVER_COMPENSATION; ``expected_amount_sgd`` otherwise. Both are null for
    NO_ACTION and ESCALATE, which move no money.
    """
    block = record["ground_truth"]
    if block["expected_ruling"] == "DRIVER_COMPENSATION":
        value = block["expected_driver_compensation_sgd"]
    else:
        value = block["expected_amount_sgd"]
    return None if value is None else Decimal(str(value))


# --------------------------------------------------------------------------
# Decimal helpers
# --------------------------------------------------------------------------


def dec(value: Any) -> Decimal:
    """``Decimal`` from any value, never through binary float.

    ``Decimal(str(value))`` is what ``tribunal.money`` uses, and it is what keeps
    a haversine result of ``633.9164359792439`` from arriving as
    ``633.9164359792438999999...``.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def decimal_places(value: Decimal) -> int:
    """How many decimal places a Decimal literal carries."""
    exponent = value.as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0


def at_places(value: Decimal, places: int) -> Decimal:
    """``value`` rounded to ``places`` decimals, half away from zero."""
    return value.quantize(ONE.scaleb(-places), rounding=ROUND_HALF_UP)


def render(value: Decimal, places: int) -> str:
    """``value`` written with exactly ``places`` decimals."""
    return str(at_places(value, places))


# --------------------------------------------------------------------------
# Prose numbers
# --------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def prose_numbers(text: str) -> List[Decimal]:
    """Every number in a rationale, as ``Decimal``, in order of appearance."""
    return [Decimal(match.group(0)) for match in _NUMBER_RE.finditer(text)]


def figures_at(text: str, places: int) -> List[Decimal]:
    """Prose numbers written with exactly ``places`` decimals, deduplicated."""
    seen: List[Decimal] = []
    for value in prose_numbers(text):
        if decimal_places(value) == places and value not in seen:
            seen.append(value)
    return seen


def figure_appears(text: str, value: Decimal, places: int) -> bool:
    """True when ``value`` is written in ``text`` at ``places`` decimals or its own.

    A token matches only when it carries the declared precision, or the
    precision the value's own literal carries. That is what lets a computed
    ``585.0`` second dwell be found in a prose "585 second dwell" and a computed
    ``779.9323`` metre approach be found in "779.9 m".

    A looser rule — any token of *fewer* decimals — was tried and rejected: it
    let the computed refund ``8.50`` in case 103 match the "9" of "POL-RD-09(2)",
    which reported a real divergence as a match. Matching a figure at a coarser
    precision than the figure itself is not evidence of a counterpart.
    """
    for token in prose_numbers(text):
        token_places = decimal_places(token)
        if token_places not in (places, decimal_places(value)):
            continue
        if at_places(value, token_places) == token:
            return True
    return False


# --------------------------------------------------------------------------
# Part A1 — stated sums
# --------------------------------------------------------------------------

# Characters that may appear in an arithmetic expression this module evaluates.
_EXPRESSION_CHARS = set("0123456789.+-x*/() ")


class ExpressionError(ValueError):
    """An expression that is not arithmetic this module is willing to evaluate."""


def _span(text: str, index: int, step: int, absorb_min: bool) -> str:
    """The arithmetic text touching ``index``, walking in direction ``step``.

    The walk stops at the first character that cannot be part of an expression,
    so words end it naturally. ``min`` is the one identifier absorbed, because
    ``min(5.98, 1.30 x (29.20 - 24.00) + 1.00) = 5.98`` is a stated figure. The
    walk resumes after absorbing it, so ``= min(5.98, 7.76)`` reaches the
    ``7.76`` on the far side of the call.
    """
    if step < 0:
        start = index
        while start > 0 and text[start - 1] in _EXPRESSION_CHARS:
            start -= 1
        if absorb_min and text[max(0, start - 3):start] == "min":
            start -= 3
        return text[start:index]

    end = index
    while True:
        while end < len(text) and text[end] in _EXPRESSION_CHARS:
            end += 1
        probe = end
        while probe < len(text) and text[probe] == " ":
            probe += 1
        if absorb_min and text[probe:probe + 3] == "min":
            end = probe + 3
            continue
        # Inside a ``min(a, b)`` call's first argument the walk stops at the
        # comma; step over it so the second argument is reached.
        if absorb_min and _MIN_FIRST_ARG_RE.match(text[index:end]):
            end += 1
            continue
        return text[index:end]


def _unwrap_min_argument(text: str, start: int, span: str) -> str:
    """Drop the closing paren of an enclosing ``min(a, ...)`` call.

    Walking left from the ``=`` in ``min(5.98, 1.30 x (29.20 - 24.00) + 1.00) =
    ...`` stops at the comma, so the span arrives with one unmatched ``)``. The
    claim being stated is about the expression, so the wrapper is removed — and
    only when the text just before the span really is a ``min(a,`` call, so an
    ordinary unbalanced expression is still rejected rather than repaired.
    """
    while span.count(")") > span.count("(") and span.rstrip().endswith(")"):
        if not text[:start].rstrip().endswith(","):
            break
        if not re.search(r"min\s*\(\s*\d+(?:\.\d+)?\s*,\s*$", text[:start]):
            break
        span = span.rstrip()[:-1]
    return span


# ``min`` is absorbed on the right so ``= min(a, b)`` states the claim ``= b``.
_MIN_FIRST_ARG_RE = re.compile(r"^\s*min\s*\(\s*\d+(?:\.\d+)?\s*$")
_MIN_RIGHT_RE = re.compile(r"^min\s*\(\s*\d+(?:\.\d+)?\s*,\s*")


@dataclass(frozen=True)
class SumClaim:
    """One stated equality: the left expression must equal the right figure."""

    left: str
    right: Decimal
    right_places: int

    @property
    def text(self) -> str:
        return "{0} = {1}".format(self.left, self.right)

    @property
    def exact(self) -> Decimal:
        return evaluate(self.left)

    @property
    def agrees(self) -> bool:
        """True when the stated figure is the exact value at its own precision.

        The prose writes rounded intermediates — ``34.0 x 32.00 / 27.10`` is
        stated as ``40.1`` — so the test is that the stated figure is the exact
        value rounded to the number of decimals the figure itself is written
        with. Half a unit in the last place is the tolerance that accepts any
        rounding convention at that precision.
        """
        tolerance = ONE.scaleb(-self.right_places) / TWO
        return abs(self.exact - self.right) <= tolerance


def sum_claims(text: str) -> List[SumClaim]:
    """Every explicit arithmetic equality in a rationale.

    An equality counts as a *stated sum* when its left side carries at least two
    numbers and at least one operator or ``min`` call. A bare ``4.0 = 4.0`` does
    not qualify, and neither does prose that merely places a number after a
    colon.
    """
    claims: List[SumClaim] = []
    for match in re.finditer(r"=", text):
        index = match.start()
        start = index - len(_span(text, index, -1, absorb_min=True))
        left = _span(text, index, -1, absorb_min=True)
        left = _unwrap_min_argument(text, start, left).strip()
        right = _span(text, index + 1, 1, absorb_min=True).strip()

        if not left or not right:
            continue
        if len(_NUMBER_RE.findall(left)) < 2:
            continue
        if not re.search(r"[+\-*/x]|min", left):
            continue

        right = _MIN_RIGHT_RE.sub("", right)
        right_match = _NUMBER_RE.match(right)
        if right_match is None or right_match.start() != 0:
            continue
        figure = Decimal(right_match.group(0))
        try:
            evaluate(left)
        except ExpressionError:
            continue
        claims.append(SumClaim(left=left, right=figure, right_places=decimal_places(figure)))
    return claims


def _tokenise(expression: str) -> List[str]:
    """Split an expression into numbers, operators and parentheses."""
    tokens: List[str] = []
    position = 0
    while position < len(expression):
        character = expression[position]
        if character == " ":
            position += 1
            continue
        if character.isdigit() or character == ".":
            match = _NUMBER_RE.match(expression, position)
            if match is None:
                raise ExpressionError("bad number at {0}".format(position))
            tokens.append(match.group(0))
            position = match.end()
            continue
        if character in "+-*/()":
            tokens.append(character)
            position += 1
            continue
        if character == "x":
            tokens.append("*")
            position += 1
            continue
        raise ExpressionError("unexpected character {0!r}".format(character))
    return tokens


def evaluate(expression: str) -> Decimal:
    """Evaluate a small arithmetic expression in ``Decimal``.

    Supports ``+ - * /``, parentheses and ``min(a, b)``. There is no ``eval``
    here and no ``float``: a term written ``0.8`` contributes exactly
    ``Decimal("0.8")``, so a false discrepancy cannot come from this module's
    own arithmetic.
    """
    tokens = _tokenise(expression)
    if not tokens:
        raise ExpressionError("empty expression")

    position = 0

    def parse_expression() -> Decimal:
        nonlocal position
        value = parse_term()
        while position < len(tokens) and tokens[position] in "+-":
            operator = tokens[position]
            position += 1
            operand = parse_term()
            value = value + operand if operator == "+" else value - operand
        return value

    def parse_term() -> Decimal:
        nonlocal position
        value = parse_factor()
        while position < len(tokens) and tokens[position] in "*/":
            operator = tokens[position]
            position += 1
            operand = parse_factor()
            value = value * operand if operator == "*" else value / operand
        return value

    def parse_factor() -> Decimal:
        nonlocal position
        if position < len(tokens) and tokens[position] == "-":
            position += 1
            return -parse_factor()
        if position < len(tokens) and tokens[position] == "(":
            position += 1
            value = parse_expression()
            if position >= len(tokens) or tokens[position] != ")":
                raise ExpressionError("unbalanced parentheses")
            position += 1
            return value
        if position < len(tokens) and tokens[position] == "min":
            position += 1
            if position >= len(tokens) or tokens[position] != "(":
                raise ExpressionError("min without arguments")
            position += 1
            first = parse_expression()
            if position >= len(tokens) or tokens[position] != ",":
                raise ExpressionError("min needs two arguments")
            position += 1
            second = parse_expression()
            if position >= len(tokens) or tokens[position] != ")":
                raise ExpressionError("min not closed")
            position += 1
            return first if first <= second else second
        if position >= len(tokens) or tokens[position] in ")+-*/,":
            raise ExpressionError("expected a number")
        value = Decimal(tokens[position])
        position += 1
        return value

    result = parse_expression()
    if position != len(tokens):
        raise ExpressionError("trailing tokens: {0}".format(tokens[position:]))
    return result


# Part A2 — stated roundings
# --------------------------------------------------------------------------

_ROUNDING_RE = re.compile(
    r"(?P<before>\d+(?:\.\d+)?)\s*,?\s*round(?:ed)?\s+"
    r"(?:UP|up)\s+to\s+(?:the\s+nearest\s+\d+(?:\.\d+)?[^.]*?)??"
    r"(?:giving\s+)?(?P<after>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RoundingClaim:
    """One stated round-up pair: ``before`` rounded up must be ``after``."""

    before: Decimal
    after: Decimal

    @property
    def text(self) -> str:
        return "{0} rounded up to {1}".format(self.before, self.after)

    @property
    def agrees(self) -> bool:
        """True when ``money.round_up_005`` turns ``before`` into ``after``."""
        return money.round_up_005(self.before) == self.after


def rounding_claims(text: str) -> List[RoundingClaim]:
    """Every explicit "rounded up to" pair in a rationale.

    Only the round-UP rule is read, because that is the rule ``money.py``
    implements and the rule POL-RD-02, POL-RD-04, POL-RD-09 and POL-RD-11 all
    invoke. A rationale that merely describes a *rounded copy* on the trip
    record — a one-decimal restatement of a trace figure — states a different
    operation and is deliberately not matched here.
    """
    claims: List[RoundingClaim] = []
    for match in _ROUNDING_RE.finditer(text):
        before = Decimal(match.group("before"))
        after = Decimal(match.group("after"))
        if before == after:
            continue
        claims.append(RoundingClaim(before=before, after=after))
    return claims


# --------------------------------------------------------------------------
# Part A — the whole internal-consistency pass
# --------------------------------------------------------------------------


@dataclass
class InternalFinding:
    """One internal-consistency check's outcome for one case."""

    case_no: int
    check: str
    subject: str
    agrees: bool
    detail: str


def check_internal_consistency() -> List[InternalFinding]:
    """Every internal-consistency finding, over the whole key.

    Three checks per case, each recorded whether it passed or failed:

    ``sum``     every explicit arithmetic equality holds;
    ``rounding`` every stated round-up pair satisfies ``money.round_up_005``;
    ``expected`` the figure the rationale arrives at is the block's own figure.

    A case with nothing to check records nothing — absence of a check is not a
    pass, and the report says which cases carried which.
    """
    findings: List[InternalFinding] = []

    for record in load_answer_key():
        case_no = record["case_no"]
        block = record["ground_truth"]
        rationale = block["rationale"]

        for claim in sum_claims(rationale):
            findings.append(
                InternalFinding(
                    case_no=case_no,
                    check="sum",
                    subject=claim.text,
                    agrees=claim.agrees,
                    detail="exact {0}, stated {1}".format(
                        claim.exact, claim.right
                    ),
                )
            )

        for claim in rounding_claims(rationale):
            findings.append(
                InternalFinding(
                    case_no=case_no,
                    check="rounding",
                    subject=claim.text,
                    agrees=claim.agrees,
                    detail="round_up_005({0}) is {1}".format(
                        claim.before, money.round_up_005(claim.before)
                    ),
                )
            )

        figure = expected_figure(record)
        if figure is not None:
            findings.append(
                InternalFinding(
                    case_no=case_no,
                    check="expected",
                    subject="{0} in the rationale".format(figure),
                    agrees=figure in prose_numbers(rationale),
                    detail="expected {0} for {1}".format(figure, block["expected_ruling"]),
                )
            )

            # Where the rationale states a round-up target and the ruling is not
            # a full refund, that target is the figure the rationale arrived at,
            # so it must be the block's figure. A FULL_REFUND rationale arrives
            # at two figures on purpose — the computed partial and the ordered
            # full refund — and is exempt.
            if block["expected_ruling"] in ("PARTIAL_REFUND", "DRIVER_COMPENSATION"):
                targets = [claim.after for claim in rounding_claims(rationale)]
                if targets:
                    findings.append(
                        InternalFinding(
                            case_no=case_no,
                            check="expected",
                            subject="round-up target(s) {0}".format(
                                ", ".join(str(target) for target in targets)
                            ),
                            agrees=figure in targets,
                            detail="expected {0} for {1}".format(
                                figure, block["expected_ruling"]
                            ),
                        )
                    )

    return findings


def internal_failures() -> List[InternalFinding]:
    """Only the findings that disagree."""
    return [finding for finding in check_internal_consistency() if not finding.agrees]


# --------------------------------------------------------------------------
# Part B — external reconciliation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Quantity:
    """One independently computed quantity, and the prose precision it is stated at.

    ``relevant`` marks a *decision-bearing* quantity: a figure a clause
    thresholds on, or a figure the ruling's own money is computed from. Only
    those are judged. Everything else is computed for completeness and printed
    without a verdict, because a rationale is not expected to quote every raw
    count, every policy constant, every input and every rounded copy it used —
    and treating those omissions as findings is how a report becomes noise that
    buries the one discrepancy that matters.

    ``matched`` records whether the prose carries a counterpart for the value.
    It is filled in by ``reconcile_case``; the value itself is computed before
    the rationale is ever read.
    """

    name: str
    value: Decimal
    places: int
    source: str
    relevant: bool = False
    matched: bool = True


@dataclass
class CaseReconciliation:
    """The reconciliation for one case."""

    case_no: int
    category: str
    expected_ruling: str
    quantities: List[Quantity] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def decision_bearing(self) -> List[Quantity]:
        """The quantities a clause thresholds on, or the ruling's money derives from."""
        return [item for item in self.quantities if item.relevant]

    def informational(self) -> List[Quantity]:
        """Quantities printed for completeness and deliberately not judged."""
        return [item for item in self.quantities if not item.relevant]

    def unmatched_relevant(self) -> List[Quantity]:
        """Decision-bearing quantities the prose does not carry a counterpart for."""
        return [item for item in self.quantities if item.relevant and not item.matched]


def _payloads(case: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """``{evidence_type: payload}`` for every artifact that has a payload."""
    found: Dict[str, Dict[str, Any]] = {}
    for artifact in case["evidence"]:
        payload = artifact.get("payload")
        if isinstance(payload, dict):
            found[artifact["evidence_type"]] = payload
    return found


def computed_quantities(case_no: int) -> Tuple[str, str, List[Quantity], List[str]]:
    """Independently computed quantities for one case.

    Returns ``(category, expected_ruling, quantities, notes)``. Every value is
    computed by ``tribunal.facts`` or ``tribunal.money``; nothing here reads the
    rationale to decide what to compute.
    """
    case = loader.load_case(case_no)
    category = case["dispute"]["category"]
    ruling = answer_key_by_case()[case_no]["ground_truth"]["expected_ruling"]
    payloads = _payloads(case)
    trip = payloads.get("TRIP_RECORD", {})
    fare = payloads.get("FARE_BREAKDOWN", {})
    gps = payloads.get("GPS_TRACE")
    policies = loader.load_policies(category)
    notes: List[str] = []
    quantities: List[Quantity] = []

    def add(name: str, value: Any, places: int, source: str, relevant: bool = False) -> None:
        if value is None:
            notes.append("{0}: not computable ({1})".format(name, source))
            return
        # A zero decision-bearing value is reported by the prose in words
        # ("no qualifying in-radius fix anywhere"), never as a figure, so it
        # cannot be reconciled as one and is printed without a verdict.
        if relevant and dec(value) == ZERO:
            relevant = False
        quantities.append(
            Quantity(
                name=name,
                value=dec(value),
                places=places,
                source=source,
                relevant=relevant,
            )
        )

    if category == "ROUTE_DEVIATION":
        model = policies["category"]["fare_model"]
        add("gps.trace_distance_km", (gps or {}).get("trace_distance_km"), 2, "GPS_TRACE payload")
        add("trip.optimal_distance_km", trip.get("optimal_distance_km"), 2, "TRIP_RECORD payload")
        add("trip.actual_distance_km", trip.get("actual_distance_km"), 2, "TRIP_RECORD payload")
        add("trip.deviation_pct", trip.get("deviation_pct"), 1, "TRIP_RECORD payload")
        add("fare.total_charged", fare.get("total_charged"), 2, "FARE_BREAKDOWN payload")
        add("fare.surge_multiplier", fare.get("surge_multiplier"), 2, "FARE_BREAKDOWN payload")
        add("trip.optimal_route_erp_sgd", trip.get("optimal_route_erp_sgd"), 2, "TRIP_RECORD payload")

        if gps and trip.get("optimal_distance_km"):
            excess, pct = facts.deviation_excess(
                gps["trace_distance_km"], trip["optimal_distance_km"]
            )
            # POL-RD-01's two limbs threshold on exactly these two figures.
            add("POL-RD-01 excess_km", excess, 2, "facts.deviation_excess", relevant=True)
            add("POL-RD-01 excess_pct", pct, 1, "facts.deviation_excess", relevant=True)

        if gps and trip.get("optimal_distance_km") and fare:
            recomputed = money.recompute_metered_fare(
                base_fare=model["base_fare"],
                per_km=model["per_km"],
                per_min=model["per_min"],
                optimal_distance_km=trip["optimal_distance_km"],
                optimal_duration_min=trip["optimal_duration_min"],
                surge_multiplier=fare["surge_multiplier"],
                platform_fee=model["platform_fee"],
                optimal_route_erp=trip.get("optimal_route_erp_sgd"),
                fixed_surcharges=ZERO,
                waiting_time_fee=fare.get("waiting_time_fee"),
                promo_discount=fare.get("promo_discount"),
            )
            # The ruling's own money is computed from these two, so they are
            # decision-bearing exactly when the ruling carries money.
            carries_money = ruling in ("PARTIAL_REFUND", "FULL_REFUND", "DRIVER_COMPENSATION")
            add(
                "POL-RD-02 recomputed_fare",
                recomputed,
                2,
                "money.recompute_metered_fare",
                relevant=carries_money,
            )
            notes.append(
                "POL-RD-02 recomputed_fare above uses the booked optimal distance and "
                "duration as they stand. POL-RD-03's closure adjustment, POL-RD-04's "
                "waypoint adjustment and POL-RD-05's re-quote are not applied by this "
                "module, so a case that adjusts its baseline will not reconcile here."
            )
            outcome = money.refund_outcome(
                fare["total_charged"],
                recomputed,
                model["de_minimis_refund"],
                Decimal("0.9"),
            )
            refund = money.refund_for(
                fare["total_charged"],
                recomputed,
                model["de_minimis_refund"],
                Decimal("0.9"),
            )
            add("POL-RD-02 refund", refund, 2, "money.refund_for", relevant=carries_money)
            notes.append(
                "POL-RD-02 outcome on the unadjusted baseline is {0}; POL-RD-06's "
                "full-refund upgrade, POL-RD-09's pass-through corrections and "
                "POL-RD-11's quote model are not applied here.".format(outcome)
            )

    else:
        schedule = policies["category"]["fee_schedule"]
        zone = trip.get("pickup_zone_class")
        pickup = trip.get("pickup") or {}
        add("fare.total_charged", fare.get("total_charged"), 2, "FARE_BREAKDOWN payload")
        add("fare.cancellation_fee", fare.get("cancellation_fee"), 2, "FARE_BREAKDOWN payload")

        if zone is None:
            notes.append("pickup_zone_class is null, so no zone-dependent quantity was computed")
        else:
            radius = schedule["arrival_radius_m"][zone]
            dwell_min = schedule["minimum_dwell_sec"][zone]
            presence = schedule["rider_presence_radius_m"][zone]
            accuracy = schedule["gps_accuracy_filter_m"]
            zone_fee = dec(schedule["zone_class_fee_sgd"][zone])
            tier_fee = dec(schedule["vehicle_tier_fee_sgd"][trip["vehicle_type"]])
            chargeable = zone_fee if zone_fee > tier_fee else tier_fee
            add("fee_schedule.arrival_radius_m", radius, 0, "policy fee_schedule")
            add("fee_schedule.minimum_dwell_sec", dwell_min, 0, "policy fee_schedule")
            add("fee_schedule.rider_presence_radius_m", presence, 0, "policy fee_schedule")
            add("chargeable fee (greater of zone and tier)", chargeable, 2, "policy fee_schedule")
            add(
                "POL-NS-07 compensation at 80%",
                chargeable * dec(schedule["driver_compensation_rate"]),
                2,
                "policy fee_schedule",
            )
            add(
                "POL-NS-03 goodwill at 50%",
                chargeable * dec(schedule["pin_ambiguity_goodwill_rate"]),
                2,
                "policy fee_schedule",
            )

            if isinstance(gps, dict) and pickup.get("lat") is not None:
                driver = facts.driver_points(gps)
                rider = facts.rider_points(gps)
                lat, lng = pickup["lat"], pickup["lng"]
                add("driver fix count", len(driver), 0, "facts.driver_points")
                distances = facts.distances_to_point(driver, lat, lng)
                if distances:
                    add(
                        "closest driver approach_m (all fixes)",
                        min(distances),
                        1,
                        "facts.distances_to_point",
                    )
                    # POL-NS-02 makes a fix worse than the accuracy filter
                    # evidence of neither presence nor absence, so the clause
                    # thresholds on the closest *admissible* fix, not on the
                    # closest fix outright. Both readings are computed; only
                    # this one is judged.
                    admissible = [
                        distance
                        for fix, distance in zip(driver, distances)
                        if fix.get("accuracy_m") is not None
                        and fix["accuracy_m"] <= accuracy
                    ]
                    if admissible:
                        add(
                            "closest admissible driver approach_m",
                            min(admissible),
                            1,
                            "facts.distances_to_point",
                            relevant=True,
                        )
                    else:
                        notes.append(
                            "no driver fix passes the {0} m accuracy filter, so there is "
                            "no admissible closest approach".format(accuracy)
                        )
                qualifying = facts.qualifying_fixes(driver, lat, lng, radius, accuracy)
                add("qualifying in-radius fix count", len(qualifying), 0, "facts.qualifying_fixes")
                run = facts.longest_qualifying_run(driver, lat, lng, radius, accuracy)
                add("longest qualifying run fix count", run["fix_count"], 0, "facts.longest_qualifying_run")
                # POL-NS-01(c) thresholds on the dwell duration.
                add(
                    "longest qualifying run duration_sec",
                    run["duration_sec"],
                    0,
                    "facts.longest_qualifying_run",
                    relevant=True,
                )
                if run["first_ts"] and trip.get("cancelled_at"):
                    add(
                        "dwell to cancellation_sec",
                        facts.elapsed_seconds(run["first_ts"], trip["cancelled_at"]),
                        0,
                        "facts.elapsed_seconds",
                        relevant=True,
                    )
                if rider:
                    rider_distances = facts.distances_to_point(rider, lat, lng)
                    add("rider fix count", len(rider), 0, "facts.rider_points")
                    add(
                        "closest rider approach_m",
                        min(rider_distances),
                        1,
                        "facts.distances_to_point",
                    )
                    add(
                        "farthest rider distance_m",
                        max(rider_distances),
                        1,
                        "facts.distances_to_point",
                    )
                notes.append(
                    "Two dwell readings are computed and both are decision-bearing. "
                    "`longest qualifying run duration_sec` is first fix to last fix "
                    "within the run; `dwell to cancellation_sec` is first fix to the "
                    "trip's cancelled_at. The rationales quote one or the other "
                    "depending on the sentence — case 202 quotes both — so a case can "
                    "carry a counterpart for one and not the other without either side "
                    "being wrong. POL-NS-06(i) interval summing and POL-NS-05's marker "
                    "correction are not applied here, so a case that depends on either "
                    "will not reconcile."
                )
            else:
                notes.append("no GPS payload, so no trace-derived quantity was computed")

    return category, ruling, quantities, notes


def reconcile_case(case_no: int) -> CaseReconciliation:
    """The reconciliation for one case, with each quantity's prose presence resolved."""
    category, ruling, quantities, notes = computed_quantities(case_no)
    record = answer_key_by_case()[case_no]
    rationale = record["ground_truth"]["rationale"]

    resolved: List[Quantity] = []
    for quantity in quantities:
        present = figure_appears(rationale, quantity.value, quantity.places)
        resolved.append(
            Quantity(
                name=quantity.name,
                value=quantity.value,
                places=quantity.places,
                source=quantity.source,
                relevant=quantity.relevant,
                matched=present,
            )
        )

    figure = expected_figure(record)
    if figure is not None:
        resolved.append(
            Quantity(
                name="answer key expected figure",
                value=figure,
                places=2,
                source="eval/answers/ground_truth.json",
                relevant=True,
                matched=figure in prose_numbers(rationale),
            )
        )

    return CaseReconciliation(
        case_no=case_no,
        category=category,
        expected_ruling=ruling,
        quantities=resolved,
        notes=notes,
    )


def _numeric_leaves(node: Any, out: set) -> None:
    """Collect every number in a document, including nested ones.

    ``Decimal`` is included because the loader parses every JSON number written
    with a decimal point as a ``Decimal``. Omitting it silently collected
    nothing from the policy files, which quietly turned a real accounting of the
    constants into no accounting at all.

    ``float`` is deliberately absent. Every document reaching this function has
    already been through the loader, so a ``float`` leaf could only mean a value
    that escaped ``parse_float=Decimal``. Converting it would be the one path by
    which binary noise could re-enter this module's arithmetic, and the module is
    meant to be a check on that noise rather than another source of it.
    """
    if isinstance(node, dict):
        for value in node.values():
            _numeric_leaves(value, out)
    elif isinstance(node, list):
        for value in node:
            _numeric_leaves(value, out)
    elif isinstance(node, Decimal):
        out.add(node)
    elif isinstance(node, int) and not isinstance(node, bool):
        out.add(Decimal(node))


def policy_constants(case_no: int) -> set:
    """Every number the case's own policy carries.

    Policy constants are inputs, not derived figures. A rationale quotes them
    because it is explaining the rule, so they belong in the accounted set
    rather than in the list of figures nothing explains.
    """
    case = loader.load_case(case_no)
    policies = loader.load_policies(case["dispute"]["category"])
    numbers: set = set()
    for policy in policies.values():
        if isinstance(policy, dict):
            for key, value in policy.items():
                if key != "clauses":
                    _numeric_leaves(value, numbers)
    return numbers


def declared_admissibility_weights(case_no: int) -> set:
    """Every ``weight_multiplier`` the case's artifacts declare.

    ``tribunal.prepass.weight_for`` reproduces these, so they are inputs the
    package already reads. The rationales quote them whenever they discuss
    confidence, and they are not derived figures.
    """
    numbers: set = set()
    for artifact in loader.load_case(case_no)["evidence"]:
        admissibility = artifact.get("admissibility") or {}
        value = admissibility.get("weight_multiplier")
        if value is not None:
            numbers.add(dec(value))
    return numbers


def unmatched_prose_figures(case_no: int, places: int = 2) -> List[Decimal]:
    """Two-decimal figures in the prose that nothing in this module accounts for.

    This is the second direction of the reconciliation, and it is deliberately
    bounded twice over. Only figures written at ``places`` decimals are
    considered, and figures already accounted for are excluded: the terms of a
    stated sum, the operands of a stated round-up, every computed quantity, the
    block's expected figure, and every policy constant the case draws on. What
    is left is the set of derived-looking figures the rationale asserts that
    this package neither computes nor uses as a term — which is exactly the set
    worth reading.
    """
    record = answer_key_by_case()[case_no]
    rationale = record["ground_truth"]["rationale"]

    accounted = {at_places(quantity.value, places) for quantity in computed_quantities(case_no)[2]}
    for claim in sum_claims(rationale):
        accounted.update(
            at_places(Decimal(token), places) for token in _NUMBER_RE.findall(claim.left)
        )
        accounted.add(at_places(claim.right, places))
    for claim in rounding_claims(rationale):
        accounted.add(at_places(claim.before, places))
        accounted.add(at_places(claim.after, places))
    figure = expected_figure(record)
    if figure is not None:
        accounted.add(at_places(figure, places))
    accounted.update(
        at_places(constant, places) for constant in policy_constants(case_no)
    )
    accounted.update(
        at_places(weight, places) for weight in declared_admissibility_weights(case_no)
    )

    return [value for value in figures_at(rationale, places) if value not in accounted]


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def render_report() -> str:
    """The whole audit, as Markdown."""
    key = load_answer_key()
    findings = check_internal_consistency()
    failures = [finding for finding in findings if not finding.agrees]

    sum_cases = sorted({f.case_no for f in findings if f.check == "sum"})
    rounding_cases = sorted({f.case_no for f in findings if f.check == "rounding"})
    expected_cases = sorted({f.case_no for f in findings if f.check == "expected"})

    lines: List[str] = []
    add = lines.append

    add("# Rationale audit — 2026-09-21")
    add("")
    add("Every `rationale` in `eval/answers/ground_truth.json` audited against this")
    add("package's own arithmetic, before the key is frozen and used to score models.")
    add("Produced by `eval/verify_rationales.py`; regenerate with")
    add("`python -m eval.verify_rationales`.")
    add("")
    add("## Summary")
    add("")
    add("| | |")
    add("|---|---|")
    add("| Cases in the key | {0} |".format(len(key)))
    add("| Cases with an explicit stated sum | {0} |".format(len(sum_cases)))
    add("| Stated sums checked | {0} |".format(len([f for f in findings if f.check == 'sum'])))
    add("| Cases with a stated round-up pair | {0} |".format(len(rounding_cases)))
    add("| Round-up pairs checked | {0} |".format(len([f for f in findings if f.check == 'rounding'])))
    add("| Cases with an expected figure | {0} |".format(len(expected_cases)))
    add("| Expected-figure checks | {0} |".format(len([f for f in findings if f.check == 'expected'])))
    add("| **Internal-consistency failures** | **{0}** |".format(len(failures)))
    add("")
    verdict = "CLEAN" if not failures else "NOT CLEAN"
    add("**Part A (internal consistency) is {0}.** A stated sum that does not add".format(verdict))
    add("up is wrong regardless of what the case data says, so a failure here would")
    add("have been unambiguous. {0}".format(
        "There are none." if not failures else "See the failures below."))
    add("")
    add("**Part B (external reconciliation) is a report, not a test.** A mismatch below")
    add("does **not** establish which side is wrong. The rationale may be wrong, or this")
    add("package's computation may be wrong — and the second would be the more serious")
    add("finding, because it would mean the code three models are measured against is")
    add("itself incorrect. Nothing in this audit has been repaired on either side.")
    add("")

    add("## Part A — internal consistency")
    add("")
    add("### A1. Stated sums")
    add("")
    add("An equality counts as a stated sum when its left side carries at least two")
    add("numbers and at least one operator or `min` call. The stated figure must be the")
    add("exact value rounded to the number of decimals the figure is written with, which")
    add("is the tolerance any rounding convention at that precision needs. All arithmetic")
    add("is `Decimal`.")
    add("")
    add("| Case | Claim | Exact | Stated | Verdict |")
    add("|---|---|---|---|---|")
    for finding in findings:
        if finding.check != "sum":
            continue
        exact, _, stated = finding.detail.partition(", stated ")
        add("| {0} | `{1}` | {2} | {3} | {4} |".format(
            finding.case_no, finding.subject, exact.replace("exact ", ""), stated,
            "ok" if finding.agrees else "**FAIL**"))
    add("")

    add("### A2. Stated round-ups")
    add("")
    add("Checked against `money.round_up_005`, the rule POL-RD-02, POL-RD-04, POL-RD-09")
    add("and POL-RD-11 all invoke. A rationale that merely describes a *rounded copy* on")
    add("the trip record states a different operation and is not matched here.")
    add("")
    add("| Case | Claim | round_up_005(before) | Verdict |")
    add("|---|---|---|---|")
    for finding in findings:
        if finding.check != "rounding":
            continue
        before = finding.subject.split(" rounded up to ")[0]
        add("| {0} | {1} | {2} | {3} |".format(
            finding.case_no, finding.subject, finding.detail.replace("round_up_005({0}) is ".format(before), ""),
            "ok" if finding.agrees else "**FAIL**"))
    add("")

    add("### A3. The expected figure")
    add("")
    add("The block's own `expected_amount_sgd`, or `expected_driver_compensation_sgd`")
    add("where the ruling is DRIVER_COMPENSATION, must be a figure the rationale")
    add("arrives at. Where the rationale states a round-up target and the ruling is not")
    add("a full refund, that target is the arrived-at figure and must equal the block's.")
    add("A FULL_REFUND rationale arrives at two figures on purpose — the computed")
    add("partial and the ordered full refund — and is exempt from the second check.")
    add("")
    add("| Case | Ruling | Expected | Check | Verdict |")
    add("|---|---|---|---|---|")
    for finding in findings:
        if finding.check != "expected":
            continue
        ruling = finding.detail.split("for ")[-1]
        expected = finding.detail.split(" ")[1]
        add("| {0} | {1} | {2} | {3} | {4} |".format(
            finding.case_no, ruling, expected, finding.subject,
            "ok" if finding.agrees else "**FAIL**"))
    add("")
    add("### A1–A3 verdict")
    add("")
    if failures:
        add("**{0} internal-consistency failure(s).**".format(len(failures)))
        for finding in failures:
            add("")
            add("- case {0}, {1}: {2} — {3}".format(
                finding.case_no, finding.check, finding.subject, finding.detail))
    else:
        add("No internal-consistency failure. Every stated sum adds up, every stated")
        add("round-up pair satisfies `money.round_up_005`, and every block's expected")
        add("figure is a figure its rationale arrives at.")
    add("")
    add("Cases carrying no check of a given kind are not passes: A1 covers {0}, A2".format(
        ", ".join(str(case) for case in sum_cases)))
    add("covers {0}, and A3 covers the {1} cases whose ruling carries money.".format(
        ", ".join(str(case) for case in rounding_cases), len(expected_cases)))
    add("")

    add("## Part B — external reconciliation")
    add("")
    add("Derived quantities computed independently through `tribunal/facts.py` and")
    add("`tribunal/money.py`, then reconciled against the prose in both directions:")
    add("a computed value with no counterpart in the prose, and a two-decimal prose")
    add("figure nothing computed accounts for. Quantities are matched against the")
    add("prose at the precision the prose states them.")
    add("")
    add("Only **decision-bearing** quantities are judged — a figure a clause thresholds")
    add("on, or a figure the ruling's own money is computed from. Inputs, raw fix")
    add("counts, policy constants, rounded copies and zero values are listed as")
    add("**informational** and carry no verdict: a rationale is not expected to quote")
    add("every one, and treating those omissions as findings would bury the one")
    add("discrepancy that matters. A zero decision-bearing value is informational too,")
    add("because the prose states an absence in words rather than as a figure.")
    add("")
    add("`facts.py` computes haversine geometry in `float`; every value it returns is")
    add("converted here with `Decimal(str(value))`, so a false discrepancy cannot come")
    add("from this module's own arithmetic.")
    add("")

    flagged: List[int] = []
    for case_no in case_numbers():
        reconciliation = reconcile_case(case_no)
        missing = reconciliation.unmatched_relevant()
        if missing:
            flagged.append(case_no)

        add("### Case {0} — {1}, {2}".format(
            case_no, reconciliation.category, reconciliation.expected_ruling))
        add("")
        add("| Decision-bearing quantity | Computed | Source | Verdict |")
        add("|---|---|---|---|")
        for quantity in reconciliation.decision_bearing():
            add("| {0} | {1} | {2} | {3} |".format(
                quantity.name,
                render(quantity.value, quantity.places),
                quantity.source,
                "in the prose" if quantity.matched else "**no counterpart**",
            ))
        add("")

        informational = reconciliation.informational()
        if informational:
            add("Informational, not judged: {0}.".format(
                ", ".join(
                    "`{0}` = {1}".format(item.name, render(item.value, item.places))
                    for item in informational
                )
            ))
            add("")

        leftovers = unmatched_prose_figures(case_no)
        if leftovers:
            add("Two-decimal figures in the prose that neither a computed quantity nor")
            add("the rationale's own arithmetic accounts for — each is either an input")
            add("this package does not model, or a discrepancy:")
            add("")
            add("`{0}`".format("`, `".join(str(value) for value in leftovers)))
            add("")

        for note in reconciliation.notes:
            add("> {0}".format(note))
            add("")

    add("## Cases needing a human")
    add("")
    if flagged:
        add("These cases have a decision-bearing quantity with no counterpart in the")
        add("prose. **This does not establish which side is wrong.** Each needs a person")
        add("to read the rationale and the computation together:")
        add("")
        for case_no in flagged:
            reconciliation = reconcile_case(case_no)
            add("- **case {0}** ({1}): {2}".format(
                case_no,
                reconciliation.expected_ruling,
                "; ".join(
                    "{0} computed {1}, not stated".format(
                        item.name, render(item.value, item.places)
                    )
                    for item in reconciliation.unmatched_relevant()
                ),
            ))
    else:
        add("None. Every decision-bearing quantity has a counterpart in the prose it")
        add("belongs to.")
    add("")
    add("Every other case reconciles: each decision-bearing quantity this package")
    add("computes appears in the case's own rationale, and no expected figure is")
    add("contradicted by the prose.")
    add("")

    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Write the report, or print it with ``--stdout``."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    report = render_report()
    if "--stdout" in arguments:
        sys.stdout.write(report)
        return 0
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    sys.stdout.write("wrote {0} ({1} bytes)\n".format(REPORT_PATH, len(report)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
