import math
from fractions import Fraction

import pytest

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings
from rtt.app.service import core_vectors, parse, text_format


class TestSchemeName:
    def test_base_scheme_name_strips_the_target_prefix(self):
        assert service.base_scheme_name("minimax-S") == "minimax-S"
        assert service.base_scheme_name("TILT minimax-S") == "minimax-S"
        assert service.base_scheme_name("9-TILT minimax-ES") == "minimax-ES"
        assert service.base_scheme_name("held-octave OLD minimax-ES") == "held-octave minimax-ES", "the prefix is dropped structurally (forcing all-interval and rendering), so a target embedded # after a held- prefix is stripped too, not just a leading one"
        assert service.base_scheme_name(service.resolve_tuning_scheme("minimax-S")) == "minimax-S"
        assert service.base_scheme_name(service.scheme_with_complexity_norm_power("minimax-S", 2.0)) == "minimax-ES"
        assert service.base_scheme_name(service.scheme_with_power("minimax-S", 1.5)) is None

    def test_optimization_power_is_the_schemes_lp_norm_order(self):
        assert service.optimization_power("minimax-S") == math.inf, "the optimization power p is trait 2 of the tuning scheme: the order of the # Lp norm minimized over the damages. minimax-S (the canonical scheme) is a minimax # scheme, so p = ∞; miniRMS is p = 2; miniaverage is p = 1"
        assert service.optimization_power() == math.inf
        assert service.optimization_power("miniRMS-U") == 2
        assert service.optimization_power("miniaverage-U") == 1


class TestCustomPrescalerEntry:
    def test_custom_prescaler_entry_accepts_a_finite_number(self):
        out = service.custom_prescaler_entry("2.5", on_diagonal=True)
        assert out.effect is service.Effect.ACCEPT
        assert out.value == 2.5

    def test_custom_prescaler_entry_skips_a_blank_or_partial_field(self):
        assert service.custom_prescaler_entry("", on_diagonal=True).effect is service.Effect.IGNORE
        assert service.custom_prescaler_entry(None, on_diagonal=False).effect is service.Effect.IGNORE
        assert service.custom_prescaler_entry("1.2.3", on_diagonal=True).effect is service.Effect.IGNORE

    def test_custom_prescaler_entry_rejects_a_nonpositive_diagonal_but_allows_it_off_diagonal(self):
        assert service.custom_prescaler_entry("0", on_diagonal=True).effect is service.Effect.REJECT, "the prescaler's diagonal scales a coordinate, so it must be positive; an off-diagonal shear # entry may be zero or negative"
        assert service.custom_prescaler_entry("-1", on_diagonal=True).effect is service.Effect.REJECT
        assert service.custom_prescaler_entry("-1", on_diagonal=False).value == -1.0
        assert service.custom_prescaler_entry("inf", on_diagonal=False).effect is service.Effect.REJECT


class TestCustomWeights:
    def test_custom_weights_collects_a_full_row_of_positive_numbers(self):
        out = service.custom_weights(["1", "2.5", "3"])
        assert out.effect is service.Effect.ACCEPT
        assert out.value == (1.0, 2.5, 3.0)

    def test_custom_weights_skips_until_every_field_is_filled(self):
        assert service.custom_weights(["1", "", "3"]).effect is service.Effect.IGNORE
        assert service.custom_weights(["1", "2x", "3"]).effect is service.Effect.IGNORE

    def test_custom_weights_rejects_a_nonpositive_or_nonfinite_weight(self):
        assert service.custom_weights(["1", "0", "3"]).effect is service.Effect.REJECT, "a damage weight must be a positive finite number"
        assert service.custom_weights(["1", "-2", "3"]).effect is service.Effect.REJECT
        assert service.custom_weights(["1", "nan", "3"]).effect is service.Effect.REJECT


class TestParsePower:
    def test_parse_power_reads_the_minimax_keywords_as_infinity(self):
        for word in ("∞", "inf", "max", "minimax", "MiniMax", " INF "):
            assert service.parse_power(word) == float("inf")

    def test_parse_power_accepts_a_positive_finite_number(self):
        assert service.parse_power("2") == 2.0
        assert service.parse_power("0.5") == 0.5

    def test_parse_power_rejects_nonpositive_nonfinite_or_unparseable(self):
        assert service.parse_power("0") is None
        assert service.parse_power("-1") is None
        assert service.parse_power("nan") is None
        assert service.parse_power("abc") is None
        assert service.parse_power("") is None

    def test_parse_power_enforces_a_minimum_for_the_complexity_norm(self):
        assert service.parse_power("0.5", minimum=1.0) is None, "the complexity norm power q must be >= 1; the minimax keyword still passes (infinity >= 1)"
        assert service.parse_power("1", minimum=1.0) == 1.0
        assert service.parse_power("minimax", minimum=1.0) == float("inf")


class TestSchemePrescaler:
    def test_scheme_with_prescaler_swaps_the_prescaler_preserving_the_rest(self):
        import pytest

        m = [[1, 1, 0], [0, 1, 4]]
        assert service.complexity_prescaler(m, service.scheme_with_prescaler("minimax-S", "prime")) == pytest.approx((2.0, 3.0, 5.0))
        assert service.complexity_prescaler(m, service.scheme_with_prescaler("minimax-S", "identity")) == pytest.approx((1.0, 1.0, 1.0))
        assert service.complexity_prescaler(m, service.scheme_with_prescaler("minimax-S", "log-prime")) == pytest.approx((1.0, 1.585, 2.322), abs=1e-3)
        assert service.damage_weight_slope(service.scheme_with_prescaler("miniRMS-C", "prime")) == "complexityWeight"
        assert service.optimization_power(service.scheme_with_prescaler("miniRMS-C", "prime")) == 2
        same = service.scheme_with_prescaler("minimax-S", "log-prime")
        assert service.tuning(m, same).tuning_map == pytest.approx(service.tuning(m, "minimax-S").tuning_map, abs=1e-6)

    def test_scheme_with_prescaler_preserves_the_size_factor(self):
        lils = service.scheme_with_diminuator("minimax-S", True)
        assert service.diminuator_replaced(lils) is True
        swapped = service.scheme_with_prescaler(lils, "prime")
        assert service.diminuator_replaced(swapped) is True
        assert service.prescaler_of(swapped) == "prime"
        assert service.diminuator_replaced(service.scheme_with_prescaler(lils, "log-prime")) is True

    def test_complexity_prescaler_is_the_diagonal_of_per_prime_weights(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        assert service.complexity_prescaler(mapping, "minimax-S") == pytest.approx((1.0, 1.585, 2.322), abs=1e-3)
        assert service.complexity_prescaler(mapping, "minimax-sopfr-S") == pytest.approx((2.0, 3.0, 5.0), abs=1e-3)

    def test_complexity_prescaler_override_short_circuits_the_schemes_diagonal(self):
        mapping = [[1, 1, 0], [0, 1, 4]]
        custom = (2.0, 3.0, 5.0)
        assert service.complexity_prescaler(mapping, "minimax-S", override=custom) == custom
        assert service.complexity_prescaler(mapping, "minimax-S", override=None) == \
            service.complexity_prescaler(mapping, "minimax-S")

    def test_complexity_prescaler_runs_over_the_domain_basis_not_standard_primes(self):
        diag = service.complexity_prescaler(((1, 1, 3), (0, 3, -1)), "minimax-C", domain_basis=(2, 3, 7))
        assert diag == pytest.approx((1.0, math.log2(3), math.log2(7)), abs=1e-9)
        elems = ("2/1", "3/1", "7/1")
        comps = service.interval_complexities(((1, 1, 3), (0, 3, -1)), "minimax-C", elems, domain_basis=(2, 3, 7))
        assert service.cents(diag[2]) == service.cents(comps[2])

    def test_complexity_prescaler_honors_the_nonprime_based_approach(self):
        db = (2, 3, Fraction(13, 5))
        neutral = service.complexity_prescaler(((1, 0, -1), (0, 2, 3)), "minimax-C", domain_basis=db)
        nonprime = service.complexity_prescaler(((1, 0, -1), (0, 2, 3)), "minimax-C", domain_basis=db,
                                                nonprime_approach="nonprime-based")
        assert neutral[2] == pytest.approx(math.log2(13 * 5), abs=1e-9)
        assert nonprime[2] == pytest.approx(math.log2(Fraction(13, 5)), abs=1e-9)


class TestSchemeComplexity:
    def test_scheme_with_complexity_norm_power_sets_the_norm_and_its_dual(self):
        import pytest

        m = [[1, 1, 0], [0, 1, 4]]
        assert service.complexity_norm_power("minimax-S") == 1
        assert service.interval_complexities(m, "minimax-S", ("3/2",))[0] == pytest.approx(2.585, abs=1e-3)
        eucl = service.scheme_with_complexity_norm_power("minimax-S", 2)
        assert service.complexity_norm_power(eucl) == 2
        assert service.interval_complexities(m, eucl, ("3/2",))[0] == pytest.approx(1.874, abs=1e-3)
        assert service.prescaler_of(eucl) == "log-prime"
        assert service.damage_weight_slope(eucl) == "simplicityWeight"
        assert service.dual_norm_power("minimax-S") == float("inf")
        assert service.dual_norm_power(eucl) == pytest.approx(2.0)

    def test_is_euclidean_reports_the_complexity_norm_power(self):
        assert service.is_euclidean("minimax-S") is False
        assert service.is_euclidean("minimax-ES") is True
        assert service.is_euclidean(service.scheme_with_complexity_norm_power("minimax-S", 2)) is True

    def test_scheme_with_complexity_sets_the_prescaler_norm_and_size_factor(self):
        copfr = service.scheme_with_complexity("minimax-S", "copfr")
        assert service.prescaler_of(copfr) == "identity" and service.is_euclidean(copfr) is False
        assert service.prescaler_of(service.scheme_with_complexity("minimax-S", "sopfr")) == "prime"
        lpe = service.scheme_with_complexity("minimax-S", "lp-E")
        assert service.prescaler_of(lpe) == "log-prime" and service.is_euclidean(lpe) is True
        assert service.optimization_power(service.scheme_with_complexity("miniRMS-C", "copfr")) == 2
        assert service.damage_weight_slope(service.scheme_with_complexity("miniRMS-C", "copfr")) == "complexityWeight"

    def test_scheme_with_complexity_held_octave_handling(self):
        assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lols")) == ("2/1",)
        assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lols-E")) == ("2/1",)
        assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lils")) == (), "lils does NOT hold the octave"
        swapped = service.scheme_with_complexity("held-octave minimax-ES", "sopfr")
        assert service.held_intervals(swapped) == ("2/1",)
        assert service.base_scheme_name(swapped) == "held-octave minimax-sopfr-S"
        assert service.held_intervals(service.scheme_with_complexity("minimax-lols-S", "lp")) == (), "but a held octave that was the OLD complexity's OWN internal fold (lols/ols) is cleared when # swapping to a non-held complexity — that octave belonged to the complexity, not the scheme"

    def test_complexity_name_of_reports_the_named_complexity_else_custom(self):
        assert service.complexity_name_of("minimax-S") == "lp"
        assert service.complexity_name_of("minimax-ES") == "lp-E"
        assert service.complexity_name_of("minimax-copfr-S") == "copfr"
        assert service.complexity_name_of("minimax-sopfr-S") == "sopfr"
        assert service.complexity_name_of("minimax-lils-S") == "lils"
        assert service.complexity_name_of("minimax-lols-S") == "lols"
        assert service.complexity_name_of(service.scheme_with_complexity("minimax-S", "sopfr-E")) == "sopfr-E"
        assert service.complexity_name_of("held-octave minimax-ES") == "lp-E", "a SCHEME-level held octave is a scheme modifier, NOT part of the complexity identity, so it # must not push the chooser to 'custom': held-octave minimax-ES still names its complexity lp-E, # held-octave minimax-S still names lp (all-interval-alt-complexity-7)"
        assert service.complexity_name_of("held-octave minimax-S") == "lp"
        assert service.complexity_name_of(service.scheme_with_complexity_norm_power("minimax-S", 3.0)) == "custom", "a complexity whose norm power is neither 1 (taxicab) nor 2 (Euclidean) matches none of the # named complexities, so the chooser falls back to 'custom'"

    def test_scheme_with_diminuator_toggles_the_size_factor_between_lp_and_lils(self):
        assert service.diminuator_replaced("minimax-S") is False
        replaced = service.scheme_with_diminuator("minimax-S", True)
        assert service.diminuator_replaced(replaced) is True
        assert service.complexity_name_of(replaced) == "lils"
        kept = service.scheme_with_diminuator("minimax-lils-S", False)
        assert service.diminuator_replaced(kept) is False and service.complexity_name_of(kept) == "lp"
        on_sopfr = service.scheme_with_diminuator("minimax-sopfr-ES", True)
        assert service.prescaler_of(on_sopfr) == "prime" and service.is_euclidean(on_sopfr) is True

    def test_complexity_size_factor_reports_the_schemes_size_factor(self):
        assert service.complexity_size_factor("minimax-S") == 0
        assert service.complexity_size_factor("minimax-lils-S") == 1
        assert service.complexity_size_factor("TILT minimax-lils-S") == 1


class TestAnnotations:
    def test_weight_annotation_codes_the_complexity_slope_and_euclideanization(self):
        assert service.weight_annotation("minimax-U") == "U"
        assert service.weight_annotation("minimax-C") == "C"
        assert service.weight_annotation("minimax-S") == "S"
        assert service.weight_annotation("minimax-EC") == "EC"
        assert service.weight_annotation("minimax-ES") == "ES"
        assert service.weight_annotation("minimax-sopfr-S") == "sopfr-S", "a named alternative complexity slots its family in — E prefixes the family, not the slope"
        assert service.weight_annotation("minimax-E-sopfr-S") == "E-sopfr-S"
        assert service.weight_annotation("minimax-copfr-C") == "copfr-C"
        assert service.weight_annotation("minimax-lils-S") == "lils-S"
        assert service.weight_annotation("minimax-lols-S") == "lols-S"
        assert service.weight_annotation(service.scheme_with_weight_slope("minimax-E-sopfr-S", "unity-weight")) == "U"

    def test_complexity_annotation_codes_the_family_and_euclideanization(self):
        assert service.complexity_annotation("minimax-S") == "C"
        assert service.complexity_annotation("minimax-ES") == "EC"
        assert service.complexity_annotation("minimax-sopfr-S") == "sopfr-C"
        assert service.complexity_annotation("minimax-E-sopfr-S") == "E-sopfr-C"
        assert service.complexity_annotation("minimax-copfr-C") == "copfr-C"
        assert service.complexity_annotation("minimax-lils-S") == "lils-C"
        assert service.complexity_annotation("minimax-lols-S") == "lols-C"


class TestPrescalerName:
    def test_prescaler_of_reports_the_schemes_current_prescaler(self):
        assert service.prescaler_of("minimax-S") == "log-prime"
        assert service.prescaler_of("minimax-sopfr-S") == "prime"
        assert service.prescaler_of("minimax-copfr-S") == "identity"
        assert service.prescaler_of(service.scheme_with_prescaler("minimax-S", "prime")) == "prime"

    def test_displayed_prescaler_name_falls_back_to_none_on_a_deviating_override(self):
        mapping = ((1, 1, 0), (0, 1, 4))
        assert service.displayed_prescaler_name(mapping, "minimax-S") == "log-prime"
        assert service.displayed_prescaler_name(mapping, "minimax-sopfr-S") == "prime"
        same = service.complexity_prescaler(mapping, "minimax-S")
        assert service.displayed_prescaler_name(mapping, "minimax-S", same) == "log-prime"
        assert service.displayed_prescaler_name(mapping, "minimax-S", (1.0, 9.9, 2.322)) is None

    def test_displayed_prescaler_name_recognizes_a_rounded_return_to_the_scheme_diagonal(self):
        mapping = ((1, 1, 0), (0, 1, 4))
        computed = service.complexity_prescaler(mapping, "minimax-S")
        shown = tuple(float(service.prescale_text(v)) for v in computed)
        assert shown != computed
        assert service.displayed_prescaler_name(mapping, "minimax-S", shown) == "log-prime"


class TestWeightSlope:
    def test_scheme_with_weight_slope_swaps_the_damage_slope_preserving_the_rest(self):
        assert service.damage_weight_slope(service.scheme_with_weight_slope("minimax-S", "unity-weight")) == "unityWeight"
        assert service.damage_weight_slope(service.scheme_with_weight_slope("minimax-S", "complexity-weight")) == "complexityWeight"
        assert service.damage_weight_slope(service.scheme_with_weight_slope("minimax-U", "simplicity-weight")) == "simplicityWeight"
        swapped = service.scheme_with_weight_slope("minimax-sopfr-ES", "unity-weight")
        assert service.prescaler_of(swapped) == "prime"
        assert service.is_euclidean(swapped) is True
        assert service.optimization_power(swapped) == math.inf

    def test_weight_slope_of_reports_the_schemes_current_slope(self):
        assert service.weight_slope_of("minimax-S") == "simplicity-weight"
        assert service.weight_slope_of("minimax-U") == "unity-weight"
        assert service.weight_slope_of("minimax-C") == "complexity-weight"
        assert service.weight_slope_of(service.scheme_with_weight_slope("minimax-S", "unity-weight")) == "unity-weight"

    def test_weight_slope_variants_offers_three_with_weighting_and_only_unity_without(self):
        assert service.weight_slope_variants("minimax-S", True) == ("minimax-S", "minimax-U", "minimax-C")
        assert service.weight_slope_variants("minimax-S", False) == ("minimax-U",)


class TestParsePrescalerDiagonal:
    def test_parse_prescaler_diagonal_reads_the_matrix_form_and_extracts_the_diagonal(self):
        assert service.parse_prescaler_diagonal(
            "[⟨1 0 0] ⟨0 1.585 0] ⟨0 0 2.322]⟩", 3) == (1.0, 1.585, 2.322)
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
        assert service.parse_prescaler_diagonal(pt[("prescaling", "primes")], 3) == (1.0, 1.585, 2.322)
        assert service.parse_prescaler_diagonal(
            "[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322]⟩", 3) == (1.0, 4.0, 2.322)

    def test_parse_prescaler_diagonal_rejects_unparseable_or_non_diagonal_or_wrong_size(self):
        assert service.parse_prescaler_diagonal("garbage", 3) is None, "rejects: unparseable, the wrong matrix size, a non-zero off-diagonal (𝐿 is diagonal), # a vector (col variance) instead of a matrix of covectors, or empty input. None lets # the caller flag the input without mangling the override"
        assert service.parse_prescaler_diagonal("", 3) is None
        assert service.parse_prescaler_diagonal("[⟨1 0] ⟨0 2]⟩", 3) is None
        assert service.parse_prescaler_diagonal("[⟨1 0.5 0] ⟨0 1 0] ⟨0 0 1]⟩", 3) is None, "a nonzero off-diagonal: 𝐿 is diagonal, so a 0.5 outside the diagonal is malformed"
        assert service.parse_prescaler_diagonal("⟨1 1.585 2.322]", 3) is None
        assert service.parse_prescaler_diagonal("[⟨1 0 0] ⟨0 1 0] ⟨0 0 1]⟩", 2) is None, "a 3-wide matrix read as d == 2 clears the row-count gate (3 ∈ {2, 3}) but every row is too # wide for d == 2, so the per-row width check rejects it"
        assert service.parse_prescaler_diagonal("[⟨1/2 0 0] ⟨0 1 0] ⟨0 0 1]⟩", 3) is None, "a fractional diagonal entry is not a real (float) scaling factor — 𝐿's diagonal is sizes"

    def test_parse_prescaler_diagonal_accepts_the_optional_size_row(self):
        assert service.parse_prescaler_diagonal(
            "[⟨1 0 0] ⟨0 1.585 0] ⟨0 0 2.322] ⟨1 1.585 2.322]⟩", 3) == (1.0, 1.585, 2.322)
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), scheme="TILT minimax-lils-S")
        assert service.parse_prescaler_diagonal(pt[("prescaling", "primes")], 3) == (1.0, 1.585, 2.322)
        assert service.parse_prescaler_diagonal(
            "[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322] ⟨9 9 9]⟩", 3) == (1.0, 4.0, 2.322)


class TestSchemeTargets:
    def test_scheme_with_targets_flips_between_all_interval_and_target_based(self):
        assert service.is_all_interval(service.scheme_with_targets("minimax-S", "{}"))
        assert not service.is_all_interval(service.scheme_with_targets("minimax-S", "TILT"))

    def test_scheme_json_round_trips_through_the_inf_optimization_power_sentinel(self):
        encoded = service.scheme_to_json("minimax-S")
        assert encoded["optimization_power"] == "inf"
        assert service.optimization_power(service.scheme_from_json(encoded)) == float("inf")
