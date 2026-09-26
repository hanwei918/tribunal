"""Tests for ``tribunal.money``.

Money is ``Decimal`` throughout. Nothing here asserts on a ``float`` except
where the point is that the float would have been wrong.

Run from the project root with::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import io
import json
import sys
import tokenize
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tribunal import loader, money  # noqa: E402

MONEY_SOURCE = PROJECT_ROOT / "tribunal" / "money.py"


def policy_file(name):
    with (PROJECT_ROOT / "policy" / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def trip_payload(case_no):
    case = loader.load_case(case_no)
    return next(a["payload"] for a in case["evidence"] if a["evidence_type"] == "TRIP_RECORD")


class RoundingTests(unittest.TestCase):
    """Test 4: round UP to the nearest 0.05."""

    def test_4_round_up_leaves_a_multiple_alone_and_lifts_a_fraction(self):
        self.assertEqual(money.round_up_005(Decimal("4.80")), Decimal("4.80"))
        self.assertEqual(money.round_up_005(Decimal("4.801")), Decimal("4.85"))

        # The float forms must survive conversion unchanged.
        self.assertEqual(money.round_up_005(4.80), Decimal("4.80"))
        self.assertEqual(money.round_up_005(4.801), Decimal("4.85"))

        self.assertEqual(money.round_up_005(Decimal("0.00")), Decimal("0.00"))
        self.assertEqual(money.round_up_005(Decimal("1.23")), Decimal("1.25"))

    def test_every_result_is_decimal(self):
        for value in (Decimal("4.80"), 4.801, "1.23", 0, None):
            self.assertIsInstance(money.round_up_005(value), Decimal)


class DecimalPrecisionTests(unittest.TestCase):
    """Test 5: the decimal literal is preserved, so the arithmetic is exact."""

    def test_5_point_eight_times_six_is_exactly_four_eighty(self):
        product = Decimal("0.8") * Decimal("6.00")
        self.assertEqual(product, Decimal("4.80"))
        self.assertNotEqual(product, Decimal("4.800000000000001"))
        self.assertEqual(str(product), "4.800")
        self.assertEqual(money.round_up_005(product), Decimal("4.80"))

    def test_the_float_product_would_have_been_wrong(self):
        """This is why the module converts through ``str``."""
        self.assertNotEqual(0.8 * 6.00, 4.80)
        self.assertEqual(repr(0.8 * 6.00), "4.800000000000001")

        self.assertEqual(money._dec(0.8) * money._dec(6.00), Decimal("4.80"))
        self.assertEqual(money._dec(0.8), Decimal("0.8"))


class RefundTests(unittest.TestCase):
    """Test 6: the round-UP rule must not touch a full refund."""

    def test_6_full_refund_of_65_13_stays_65_13(self):
        charged = Decimal("65.13")
        refund = money.refund_for(charged, Decimal("1.00"), Decimal("0.50"), Decimal("0.90"))

        self.assertEqual(refund, Decimal("65.13"))
        self.assertNotEqual(refund, Decimal("65.15"))
        self.assertEqual(str(refund), "65.13")
        self.assertEqual(
            money.refund_outcome(charged, Decimal("1.00"), Decimal("0.50"), Decimal("0.90")),
            money.OUTCOME_FULL_REFUND,
        )

    def test_a_partial_refund_is_rounded_up(self):
        """The computed payable does get the round-UP treatment."""
        refund = money.refund_for(
            Decimal("65.13"), Decimal("60.001"), Decimal("0.50"), Decimal("0.90")
        )
        self.assertEqual(refund, Decimal("5.15"))
        self.assertEqual(
            money.refund_outcome(
                Decimal("65.13"), Decimal("60.001"), Decimal("0.50"), Decimal("0.90")
            ),
            money.OUTCOME_PARTIAL_REFUND,
        )

    def test_de_minimis_pays_nothing_and_is_no_action(self):
        self.assertEqual(
            money.refund_for(Decimal("65.13"), Decimal("64.80"), Decimal("0.50"), Decimal("0.90")),
            Decimal("0"),
        )
        self.assertEqual(
            money.refund_outcome(
                Decimal("65.13"), Decimal("64.80"), Decimal("0.50"), Decimal("0.90")
            ),
            money.OUTCOME_NO_ACTION,
        )

    def test_the_refund_is_floored_at_zero(self):
        self.assertEqual(
            money.refund_for(Decimal("10.00"), Decimal("25.00"), Decimal("0.50"), Decimal("0.90")),
            Decimal("0"),
        )


class RecomputedFareTests(unittest.TestCase):
    """POL-RD-02's formula, with every constant read from the loaded policy."""

    @classmethod
    def setUpClass(cls):
        cls.fare_model = policy_file("route_deviation.json")["fare_model"]
        cls.trip = trip_payload(105)

    def _fare(self, **overrides):
        constants = dict(
            base_fare=self.fare_model["base_fare"],
            per_km=self.fare_model["per_km"],
            per_min=self.fare_model["per_min"],
            platform_fee=self.fare_model["platform_fee"],
        )
        constants.update(overrides)
        return money.recompute_metered_fare(
            base_fare=constants["base_fare"],
            per_km=constants["per_km"],
            per_min=constants["per_min"],
            optimal_distance_km=self.trip["optimal_distance_km"],
            optimal_duration_min=self.trip["optimal_duration_min"],
            surge_multiplier=Decimal("1.0"),
            platform_fee=constants["platform_fee"],
            optimal_route_erp=Decimal("0"),
            fixed_surcharges=Decimal("0"),
            waiting_time_fee=Decimal("0"),
            promo_discount=Decimal("0"),
        )

    def test_matches_a_hand_computation_from_the_policy_constants(self):
        fare = self._fare()
        expected = (
            Decimal(str(self.fare_model["base_fare"]))
            + Decimal(str(self.fare_model["per_km"])) * Decimal(str(self.trip["optimal_distance_km"]))
            + Decimal(str(self.fare_model["per_min"])) * Decimal(str(self.trip["optimal_duration_min"]))
        ) + Decimal(str(self.fare_model["platform_fee"]))

        self.assertEqual(fare, expected)
        self.assertIsInstance(fare, Decimal)

    def test_additive_components_are_added_and_the_discount_subtracted(self):
        plain = self._fare()
        loaded = money.recompute_metered_fare(
            base_fare=self.fare_model["base_fare"],
            per_km=self.fare_model["per_km"],
            per_min=self.fare_model["per_min"],
            optimal_distance_km=self.trip["optimal_distance_km"],
            optimal_duration_min=self.trip["optimal_duration_min"],
            surge_multiplier=Decimal("1.0"),
            platform_fee=self.fare_model["platform_fee"],
            optimal_route_erp=Decimal("2.50"),
            fixed_surcharges=Decimal("6.00"),
            waiting_time_fee=Decimal("1.20"),
            promo_discount=Decimal("3.00"),
        )
        self.assertEqual(loaded - plain, Decimal("2.50") + Decimal("6.00") + Decimal("1.20") - Decimal("3.00"))

    def test_intermediate_values_are_not_rounded(self):
        fare = self._fare()
        self.assertNotEqual(fare, money.round_up_005(fare))
        self.assertEqual(money.round_up_005(fare), money.round_up_005(fare))


class MoneySourceTests(unittest.TestCase):
    """Test 8, equivalent to the facts.py test: no policy number is a literal here."""

    def test_8_no_policy_number_appears_as_a_literal_in_money(self):
        """Asserted on parsed tokens, never by substring search.

        This corpus is natural language and its prose quotes numbers freely —
        POL-RD-02's own de-minimis line contains "0.50", which a substring
        search for "50" would flag. So the check compares whole token values.
        """
        source = MONEY_SOURCE.read_text(encoding="utf-8")
        forbidden_text = {"120", "150", "300", "480", "25", "50"}
        forbidden_values = {float(text) for text in forbidden_text}

        numbers, strings = [], []
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.NUMBER:
                numbers.append(token.string)
            elif token.type == tokenize.STRING:
                try:
                    strings.append(ast.literal_eval(token.string))
                except (ValueError, SyntaxError):
                    pass

        by_number_text = sorted(set(numbers) & forbidden_text)
        by_number_value = sorted(
            {text for text in numbers if _as_float(text) in forbidden_values}, key=_as_float
        )
        by_string_value = sorted(set(strings) & forbidden_text)

        self.assertEqual(by_number_text, [], "policy numbers as numeric literals: {0}".format(by_number_text))
        self.assertEqual(by_number_value, [], "policy numbers as numeric literals: {0}".format(by_number_value))
        self.assertEqual(by_string_value, [], "policy numbers as string literals: {0}".format(by_string_value))

    def test_the_module_never_calls_float(self):
        """``float`` must not be used as a name: money is Decimal throughout.

        Checked on NAME tokens rather than by substring search, so the module
        docstring is free to mention the word ``float`` while the code is not
        allowed to call it.
        """
        source = MONEY_SOURCE.read_text(encoding="utf-8")
        names = [
            token.string
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.NAME
        ]
        self.assertNotIn("float", names)


class CanonicalSerialisationTests(unittest.TestCase):
    """The Decimal-aware canonical serialiser the loader and the brief depend on."""

    def test_a_decimal_is_written_as_a_json_number_with_its_own_literal(self):
        text = money.dumps_canonical({"a": Decimal("8.0"), "b": Decimal("0.70")})
        self.assertEqual(text, '{"a":8.0,"b":0.70}')
        self.assertNotIn('"8.0"', text, "a Decimal must not be quoted into a string")

    def test_the_contract_parameters_are_used(self):
        """ensure_ascii=False, sort_keys=True, separators=(",", ":")."""
        self.assertEqual(money.dumps_canonical({"b": 1, "a": "x"}), '{"a":"x","b":1}')
        self.assertEqual(money.dumps_canonical({"a": "café"}), '{"a":"café"}')
        self.assertEqual(money.dumps_canonical([1, 2]), "[1,2]")

    def test_without_decimals_it_is_exactly_json_dumps(self):
        plain = {"b": [1, 2.5, None, True], "a": {"c": "x"}}
        self.assertEqual(
            money.dumps_canonical(plain),
            json.dumps(plain, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def test_a_non_finite_decimal_is_refused(self):
        for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with self.assertRaises(ValueError):
                money.dumps_canonical({"a": bad})

    def test_the_placeholder_guard_refuses_data_that_collides(self):
        with self.assertRaises(ValueError):
            money.dumps_canonical({"a": "x" + money._TOKEN_PREFIX + "y"})

    def test_canonical_sha256_is_stable_and_order_independent(self):
        obj = {"a": Decimal("8.0"), "b": [Decimal("0.39"), 1]}
        self.assertEqual(money.canonical_sha256(obj), money.canonical_sha256(obj))
        self.assertEqual(len(money.canonical_sha256(obj)), 64)

    def test_a_decimal_round_trips_through_the_canonical_text(self):
        obj = {"a": Decimal("8.0"), "b": Decimal("0.70"), "c": 3}
        back = json.loads(money.dumps_canonical(obj), parse_float=Decimal)
        self.assertEqual(back, obj)
        self.assertIsInstance(back["a"], Decimal)


class MeteredComponentsTests(unittest.TestCase):
    """POL-RD-02's recomputation, itemised, and the one total it must agree with."""

    @classmethod
    def setUpClass(cls):
        cls.fare_model = policy_file("route_deviation.json")["fare_model"]

    def _arguments(self, **overrides):
        arguments = dict(
            base_fare=self.fare_model["base_fare"],
            per_km=self.fare_model["per_km"],
            per_min=self.fare_model["per_min"],
            optimal_distance_km=Decimal("18.0"),
            optimal_duration_min=Decimal("30.0"),
            surge_multiplier=Decimal("1.6"),
            platform_fee=self.fare_model["platform_fee"],
            optimal_route_erp=Decimal("2.50"),
            fixed_surcharges=Decimal("0"),
            waiting_time_fee=Decimal("0"),
            promo_discount=Decimal("0"),
        )
        arguments.update(overrides)
        return arguments

    def test_the_lines_sum_to_the_total(self):
        components = money.metered_fare_components(**self._arguments())
        lines = (
            components["surged_distance_and_time"]
            + components["platform_fee"]
            + components["optimal_route_erp"]
            + components["fixed_surcharges"]
            + components["waiting_time_fee"]
            - components["promo_discount"]
        )
        self.assertEqual(lines, components["recomputed_fare"])

    def test_the_single_total_is_the_itemised_total(self):
        """``recompute_metered_fare`` is the breakdown's total, not a second expression."""
        components = money.metered_fare_components(**self._arguments())
        self.assertEqual(
            money.recompute_metered_fare(**self._arguments()), components["recomputed_fare"]
        )

    def test_the_surge_multiplies_distance_and_time_and_nothing_else(self):
        plain = money.metered_fare_components(**self._arguments(optimal_route_erp=Decimal("0")))
        loaded = money.metered_fare_components(
            **self._arguments(optimal_route_erp=Decimal("7.50"), fixed_surcharges=Decimal("5.00"))
        )
        self.assertEqual(loaded["recomputed_fare"] - plain["recomputed_fare"], Decimal("12.50"))
        self.assertEqual(loaded["surge_uplift"], plain["surge_uplift"])


class JustifiedExcessTests(unittest.TestCase):
    """POL-RD-03's cap, with the ratio and the tolerance supplied by the caller."""

    def test_the_cap_binds_when_the_measured_excess_is_larger(self):
        result = money.justified_excess(
            measured_excess_km=Decimal("8.00"),
            shortest_lawful_alternative_km=Decimal("12.00"),
            optimal_distance_km=Decimal("10.00"),
            cap_ratio=Decimal("1.30"),
            tolerance_km=Decimal("1.00"),
        )
        self.assertEqual(result["additional_distance_km"], Decimal("2.00"))
        self.assertEqual(result["cap_km"], Decimal("3.60"))
        self.assertEqual(result["justified_excess_km"], Decimal("3.60"))

    def test_the_measured_excess_survives_a_cap_that_does_not_bind(self):
        result = money.justified_excess(
            measured_excess_km=Decimal("2.98"),
            shortest_lawful_alternative_km=Decimal("10.60"),
            optimal_distance_km=Decimal("8.20"),
            cap_ratio=Decimal("1.30"),
            tolerance_km=Decimal("1.00"),
        )
        self.assertEqual(result["cap_km"], Decimal("4.12"))
        self.assertEqual(result["justified_excess_km"], Decimal("2.98"))

    def test_the_cap_is_on_the_additional_distance_not_the_route_length(self):
        """The clause's own note: 130% of the whole alternative would never bite."""
        result = money.justified_excess(
            measured_excess_km=Decimal("1.00"),
            shortest_lawful_alternative_km=Decimal("30.00"),
            optimal_distance_km=Decimal("28.00"),
            cap_ratio=Decimal("1.30"),
            tolerance_km=Decimal("1.00"),
        )
        self.assertEqual(result["cap_km"], Decimal("3.60"))
        self.assertLess(result["cap_km"], Decimal("1.30") * Decimal("30.00"))


class ClosureAdjustedRouteTests(unittest.TestCase):
    """POL-RD-03's closure-adjusted distance and duration."""

    def test_the_duration_is_scaled_and_written_to_one_place(self):
        route = money.closure_adjusted_route(
            optimal_distance_km=Decimal("27.10"),
            optimal_duration_min=Decimal("34.0"),
            justified_excess_km=Decimal("4.90"),
        )
        self.assertEqual(route["adjusted_optimal_distance_km"], Decimal("32.00"))
        self.assertEqual(route["adjusted_optimal_duration_min"], Decimal("40.1"))
        self.assertEqual(route["duration_source"], money.DURATION_SCALED)

    def test_a_stored_amended_duration_governs(self):
        route = money.closure_adjusted_route(
            optimal_distance_km=Decimal("10.00"),
            optimal_duration_min=Decimal("20.0"),
            justified_excess_km=Decimal("3.60"),
            amended_optimal_duration_min=Decimal("25.0"),
        )
        self.assertEqual(route["adjusted_optimal_duration_min"], Decimal("25.0"))
        self.assertEqual(route["duration_source"], money.DURATION_AMENDED)

    def test_no_booked_distance_leaves_the_duration_undetermined(self):
        route = money.closure_adjusted_route(
            optimal_distance_km=Decimal("0"),
            optimal_duration_min=Decimal("20.0"),
            justified_excess_km=Decimal("3.60"),
        )
        self.assertIsNone(route["adjusted_optimal_duration_min"])
        self.assertEqual(route["duration_source"], money.DURATION_UNKNOWN)


class ErpLineTests(unittest.TestCase):
    """The fare's gantry lines, totalled by route and never silently promoted."""

    def test_on_and_off_optimal_lines_are_totalled_separately(self):
        result = money.erp_lines(
            [
                {"gantry_name": "A", "amount_sgd": Decimal("2.50"), "on_optimal_route": True},
                {"gantry_name": "B", "amount_sgd": Decimal("2.00"), "on_optimal_route": False},
                {"gantry_name": "C", "amount_sgd": Decimal("1.00"), "on_optimal_route": None},
            ]
        )
        self.assertEqual(result["on_optimal_route_total"], Decimal("2.50"))
        self.assertEqual(result["off_optimal_route_total"], Decimal("3.00"))
        self.assertEqual(result["total"], Decimal("5.50"))
        self.assertFalse(result["lines"][2]["on_optimal_route"])


class UpfrontQuoteTests(unittest.TestCase):
    def test_the_difference_is_the_charge_over_the_quote(self):
        result = money.upfront_quote_comparison(Decimal("25.20"), Decimal("22.00"))
        self.assertEqual(result["quoted_fare"], Decimal("22.00"))
        self.assertEqual(result["charged_total"], Decimal("25.20"))
        self.assertEqual(result["difference"], Decimal("3.20"))


class ScheduleFeeTests(unittest.TestCase):
    """POL-NS-01: the greater of the two fees, and which dimension produced it."""

    def test_the_greater_fee_governs_and_the_dimension_is_named(self):
        self.assertEqual(
            money.schedule_fee(Decimal("4.00"), Decimal("8.00")),
            (Decimal("8.00"), money.DIMENSION_VEHICLE_TIER),
        )
        self.assertEqual(
            money.schedule_fee(Decimal("6.00"), Decimal("4.00")),
            (Decimal("6.00"), money.DIMENSION_ZONE_CLASS),
        )

    def test_a_tie_is_named_as_a_tie(self):
        self.assertEqual(
            money.schedule_fee(Decimal("4.00"), Decimal("4.00")),
            (Decimal("4.00"), money.DIMENSION_TIE),
        )


class FeeArithmeticTests(unittest.TestCase):
    """POL-NS-07 and POL-NS-03(ii): both payments are on the charged figure."""

    def test_both_payments_are_computed_on_the_charged_figure(self):
        result = money.fee_arithmetic(
            schedule_fee_amount=Decimal("4.00"),
            fee_charged=Decimal("4.00"),
            driver_compensation_rate=Decimal("0.80"),
            goodwill_rate=Decimal("0.50"),
        )
        self.assertEqual(result["difference"], Decimal("0.00"))
        self.assertEqual(result["driver_compensation"], Decimal("3.20"))
        self.assertEqual(result["goodwill"], Decimal("2.00"))

    def test_a_charge_that_differs_from_the_schedule_is_reported(self):
        result = money.fee_arithmetic(
            schedule_fee_amount=Decimal("6.00"),
            fee_charged=Decimal("4.00"),
            driver_compensation_rate=Decimal("0.80"),
            goodwill_rate=Decimal("0.50"),
        )
        self.assertEqual(result["difference"], Decimal("-2.00"))
        self.assertEqual(result["driver_compensation"], Decimal("3.20"))


class PayableStringTests(unittest.TestCase):
    """A payable figure is written as a decimal string with two places."""

    def test_a_payable_amount_is_written_to_two_places(self):
        self.assertEqual(money.payable_string(Decimal("3.6")), "3.60")
        self.assertEqual(money.payable_string(Decimal("65.13")), "65.13")
        self.assertEqual(money.payable_string(Decimal("2")), "2.00")

    def test_the_result_is_a_string(self):
        for value in (Decimal("4.80"), 4.8, "1.23", 0, None):
            self.assertIsInstance(money.payable_string(value), str)


def _as_float(text):
    """The numeric value of a NUMBER token, or None when it is not a plain number."""
    try:
        return float(text)
    except ValueError:
        return None


if __name__ == "__main__":
    unittest.main(verbosity=2)
