import math
from fractions import Fraction

import pytest

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings
from rtt.app.service import core_vectors, parse, text_format


class TestTuning:
    def test_tuning_from_generators_applies_a_manual_generator_tuning(self):
        tuning_map = service.tuning_from_generators([[1, 1, 0], [0, 1, 4]], (1200.0, 701.955))
        assert tuning_map.generator_map == (1200.0, 701.955)
        assert abs(tuning_map.tuning_map[0] - 1200.0) < 1e-6
        assert abs(tuning_map.tuning_map[1] - 1901.955) < 1e-6
        assert abs(tuning_map.tuning_map[2] - 4 * 701.955) < 1e-6

    def test_tuning_holds_user_specified_intervals_just(self):
        tuning_map = service.tuning([[1, 1, 0], [0, 1, 4]], held=("3/2",))
        fifth = (-1, 1, 0)
        tempered = sum(tuning_map.tuning_map[p] * fifth[p] for p in range(3))
        just = sum(tuning_map.just_map[p] * fifth[p] for p in range(3))
        assert abs(tempered - just) < 1e-6
        free = service.tuning([[1, 1, 0], [0, 1, 4]])
        assert abs(sum(free.tuning_map[p] * fifth[p] for p in range(3))
                   - sum(free.just_map[p] * fifth[p] for p in range(3))) > 1e-6

    def test_held_intervals_come_from_the_tuning_scheme(self):
        assert service.held_intervals("minimax-S", 3) == ()
        assert service.held_intervals() == ()
        assert service.held_intervals("held-octave minimax-ES", 3) == ("2/1",)

    def test_tuning_maps_under_top(self):
        import pytest

        t = service.tuning([[1, 1, 0], [0, 1, 4]])
        assert t.generator_map == pytest.approx((1201.699, 697.564), abs=1e-2)
        assert t.tuning_map == pytest.approx((1201.699, 1899.263, 2790.258), abs=1e-2)
        assert t.just_map == pytest.approx((1200.0, 1901.955, 2786.314), abs=1e-2)
        assert t.retuning_map == pytest.approx((1.699, -2.692, 3.944), abs=1e-2)

    def test_tuning_threads_an_explicit_standard_basis_like_the_default(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert (
            service.tuning(state.mapping, domain_basis=state.domain_basis).generator_map
            == service.tuning(state.mapping).generator_map
        )

    def test_tuning_over_a_nonstandard_domain_uses_the_basis_elements(self):
        import pytest

        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        t = service.tuning(state.mapping, domain_basis=state.domain_basis)
        assert len(t.generator_map) == state.rank and len(t.tuning_map) == state.dimensionality
        assert t.just_map == pytest.approx(
            (1200.0, 1901.955, 1200.0 * math.log2(13 / 5)), abs=1e-2
        )

    def test_tuning_mode_changes_the_nonstandard_optimum(self):
        import pytest

        state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
        neutral = service.tuning(state.mapping, "TILT minimax-C", domain_basis=state.domain_basis)
        nonprime = service.tuning(
            state.mapping, "TILT minimax-C", domain_basis=state.domain_basis,
            nonprime_approach="nonprime-based",
        )
        assert neutral.generator_map == pytest.approx((1191.880, 133.594), abs=1e-2)
        assert nonprime.generator_map == pytest.approx((1192.399, 133.768), abs=1e-2)

    def test_tuning_optimizes_over_an_explicit_target_override(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        base = service.tuning(mapping, "TILT minimax-U")
        targeted = service.tuning(mapping, "TILT minimax-U", targets=("2/1", "3/2"))
        assert targeted.generator_map != base.generator_map
        assert targeted.generator_map == pytest.approx((1200.0, 701.955), abs=1e-2)

    def test_tuning_exposes_diamond_generator_ranges(self):
        import pytest

        t = service.tuning([[1, 1, 0], [0, 1, 4]])
        assert t.tradeoff_generator_range[0] == pytest.approx((1200.0, 1200.0), abs=1e-6)
        assert t.tradeoff_generator_range[1] == pytest.approx((694.786, 701.955), abs=1e-2)
        assert t.monotone_generator_range[1] == pytest.approx((685.714, 720.0), abs=1e-2)

    def test_generator_tuning_range_is_well_defined_for_a_fractional_spelling_of_a_prime_subgroup(self):
        state = service.from_mapping(((1, 1, 0, 0), (0, 1, 4, 0), (0, 0, 0, 1)),
                                     domain_basis=(2, 3, 5, Fraction(13, 5)))
        t = service.tuning(state.mapping, service.DEFAULT_TUNING_SCHEME, state.domain_basis)
        assert t.monotone_generator_range is not None and t.tradeoff_generator_range is not None
        assert all(x == x for x in t.tuning_map)

    def test_tuning_honors_an_explicit_empty_target_override(self):
        m = ((1, 1, 0), (0, 1, 4))
        assert service.tuning(m, "TILT minimax-U", targets=()).generator_map \
            == service.tuning(m, "1-TILT minimax-U").generator_map
        assert service.tuning(m, "OLD minimax-U", targets=()).generator_map \
            == service.tuning(m, "1-OLD minimax-U").generator_map
        assert service.tuning(m, "TILT minimax-U", targets=None).generator_map \
            != service.tuning(m, "TILT minimax-U", targets=()).generator_map
        assert service.tuning(m, "TILT minimax-U", targets=("3/2",)).generator_map[1] == pytest.approx(701.955, abs=1e-2)
        assert service.tuning(m, "minimax-S", targets=()).generator_map \
            == service.tuning(m, "minimax-S").generator_map


class TestIntervalSizes:
    def test_interval_sizes_project_a_set_through_the_tuning(self):
        import pytest

        t = service.tuning([[1, 1, 0], [0, 1, 4]])
        s = service.interval_sizes(t, ("2/1", "3/2", "5/4", "6/5"))
        assert s.tempered == pytest.approx((1201.699, 697.564, 386.861, 310.704), abs=1e-2)
        assert s.just == pytest.approx((1200.0, 701.955, 386.314, 315.641), abs=1e-2)
        assert s.errors == pytest.approx((1.699, -4.391, 0.547, -4.937), abs=1e-2)
        assert s.damage == pytest.approx((1.699, 4.391, 0.547, 4.937), abs=1e-2)
        assert all(d >= 0 for d in s.damage)

    def test_interval_sizes_weights_scale_damage_into_the_scheme_weighted_form(self):
        import pytest

        state = service.from_mapping([[1, 0, -4], [0, 1, 4]])
        tuning_map = service.tuning(state.mapping, "TILT minimax-U")
        targets = service.displayed_targets(state, "TILT minimax-C")
        weights = service.interval_weights(state.mapping, "TILT minimax-C", targets)
        s = service.interval_sizes(tuning_map, targets, weights=weights)
        by_ratio = dict(zip(targets, s.damage))
        assert by_ratio["3/2"] == pytest.approx(13.898, abs=1e-2)
        assert by_ratio["4/3"] == pytest.approx(19.275, abs=1e-2)
        assert by_ratio["6/5"] == pytest.approx(26.382, abs=1e-2)
        unweighted = service.interval_sizes(tuning_map, targets)
        assert unweighted.damage == pytest.approx(tuple(abs(e) for e in s.errors), abs=1e-9)

    def test_interval_sizes_over_a_nonstandard_domain_express_intervals_in_the_basis(self):
        import pytest

        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        tuning_map = service.tuning(state.mapping, domain_basis=state.domain_basis)
        s = service.interval_sizes(tuning_map, ("2/1", "3/1", "13/5"), domain_basis=state.domain_basis)
        assert s.tempered == pytest.approx(tuning_map.tuning_map, abs=1e-6)
        assert s.just == pytest.approx(tuning_map.just_map, abs=1e-6)

    def test_interval_sizes_of_the_empty_set_are_empty(self):
        t = service.tuning([[1, 1, 0], [0, 1, 4]])
        s = service.interval_sizes(t, ())
        assert (s.tempered, s.just, s.errors, s.damage) == ((), (), (), ())


class TestIntervalWeights:
    def test_interval_weights_follow_the_schemes_damage_slope(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        ratios = ("2/1", "3/2", "5/4")
        complexities = (1.0, 2.585, 4.322)
        assert service.interval_weights(mapping, "minimax-U", ratios) == pytest.approx((1.0, 1.0, 1.0))
        assert service.interval_weights(mapping, "minimax-C", ratios) == pytest.approx(complexities, abs=1e-3)
        assert service.interval_weights(mapping, "minimax-S", ratios) == pytest.approx(
            tuple(1 / c for c in complexities), abs=1e-3
        )

    def test_interval_weights_of_the_empty_set_are_empty(self):
        assert service.interval_weights([[1, 1, 0], [0, 1, 4]], "minimax-S", ()) == ()

    def test_interval_weight_uses_the_full_domain_basis_vector(self):
        import pytest

        mapping = [[1, 2, 2], [0, -2, -3]]
        db = (2, 3, Fraction(13, 5))
        got = service.interval_weights(mapping, "minimax-S", ("13/5",), domain_basis=db)[0]
        assert got == pytest.approx(1 / math.log2(13 * 5), abs=1e-6)

    def test_interval_weights_use_the_prescaler_override(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        targets = ("3/2", "5/4", "5/3")
        overridden = service.interval_weights(
            mapping, "minimax-S", targets, prescaler_override=(2.0, 3.0, 5.0))
        sopfr = service.interval_weights(mapping, "minimax-sopfr-S", targets)
        assert overridden == pytest.approx(sopfr, abs=1e-6)

    def test_interval_weights_return_the_weights_override_verbatim(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        targets = ("3/2", "5/4", "5/3")
        got = service.interval_weights(mapping, "minimax-C", targets, weights_override=(1.0, 2.0, 5.0))
        assert got == pytest.approx((1.0, 2.0, 5.0))


class TestIntervalComplexities:
    def test_interval_complexities_norm_each_intervals_prescaled_vector(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        ratios = ("2/1", "3/2", "5/4")
        expected = (1.0, 2.585, 4.322)
        assert service.interval_complexities(mapping, "minimax-S", ratios) == pytest.approx(expected, abs=1e-3)
        assert service.interval_complexities(mapping, "minimax-C", ratios) == pytest.approx(expected, abs=1e-3)

    def test_interval_complexities_of_the_empty_set_are_empty(self):
        assert service.interval_complexities([[1, 1, 0], [0, 1, 4]], "minimax-S", ()) == ()

    def test_interval_complexity_uses_the_full_domain_basis_vector(self):
        import pytest

        mapping = [[1, 2, 2], [0, -2, -3]]
        db = (2, 3, Fraction(13, 5))
        got = service.interval_complexities(mapping, "minimax-S", ("13/5",), domain_basis=db)[0]
        assert got == pytest.approx(math.log2(13 * 5), abs=1e-6)

    def test_interval_complexities_use_the_prescaler_override(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        ratios = ("3/2", "5/4")
        overridden = service.interval_complexities(
            mapping, "minimax-S", ratios, prescaler_override=(2.0, 3.0, 5.0))
        sopfr = service.interval_complexities(mapping, "minimax-sopfr-S", ratios)
        assert overridden == pytest.approx(sopfr, abs=1e-6)

    def test_interval_complexities_accept_a_full_matrix_pretransformer(self):
        import numpy as np
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        X = ((1.0, 0.5, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 3.0))
        comps = service.interval_complexities(mapping, "minimax-S", ("3/2", "5/4"), prescaler_override=X)
        for got, vector in zip(comps, ([-1, 1, 0], [-2, 0, 1])):
            assert got == pytest.approx(float(np.linalg.norm(np.array(X) @ np.array(vector), 1)))


class TestTuningOverrides:
    def test_tuning_uses_the_prescaler_override(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        overridden = service.tuning(mapping, "minimax-S", prescaler_override=(2.0, 3.0, 5.0))
        sopfr = service.tuning(mapping, "minimax-sopfr-S")
        assert overridden.tuning_map == pytest.approx(sopfr.tuning_map, abs=1e-6)
        assert overridden.generator_map == pytest.approx(sopfr.generator_map, abs=1e-6)

    def test_tuning_uses_the_weights_override_and_the_cache_distinguishes_it(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        scheme, targets = "TILT minimax-C", ("3/2", "5/4", "5/3")
        a = service.tuning(mapping, scheme, targets=targets, weights_override=(1.0, 1.0, 1.0))
        b = service.tuning(mapping, scheme, targets=targets, weights_override=(1.0, 50.0, 50.0))
        assert a.generator_map != pytest.approx(b.generator_map, abs=1e-3)
        unity = service.tuning(mapping, "TILT minimax-U", targets=targets)
        assert a.generator_map == pytest.approx(unity.generator_map, abs=1e-3)

    def test_all_interval_tuning_ignores_the_weights_override(self):
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        plain = service.tuning(mapping, "minimax-S")
        overridden = service.tuning(mapping, "minimax-S", weights_override=(9.0, 0.1, 7.0))
        assert overridden.generator_map == pytest.approx(plain.generator_map, abs=1e-3)

    def test_all_interval_solver_handles_a_non_diagonal_pretransformer(self):
        import numpy as np
        import pytest

        mapping = [[1, 1, 0], [0, 1, 4]]
        diag = (1.0, 1.585, 2.322)
        diag_2d = tuple(tuple(diag[i] if i == k else 0.0 for k in range(3)) for i in range(3))
        t1 = service.tuning(mapping, "minimax-S", prescaler_override=diag)
        t2 = service.tuning(mapping, "minimax-S", prescaler_override=diag_2d)
        assert t2.tuning_map == pytest.approx(t1.tuning_map, abs=1e-4)
        nondiag = ((1.0, 0.5, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322))
        t3 = service.tuning(mapping, "minimax-S", prescaler_override=nondiag)
        M, j = np.array(mapping, float), np.array(t3.just_map)
        Xinv = np.linalg.inv(np.array(nondiag))
        magnitude = lambda g: float(np.max(np.abs((np.array(g) @ M - j) @ Xinv)))
        g0 = np.array(t3.generator_map)
        base = magnitude(g0)
        for dg in ([0.5, 0], [0, 0.5], [-0.5, 0], [0, -0.5], [0.3, 0.3], [-0.3, 0.3]):
            assert magnitude(g0 + np.array(dg)) >= base - 1e-6


class TestTuningProjection:
    def test_tuning_projection_is_dashed_for_an_under_held_tuning(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.tuning_projection(state) is None
        assert service.tuning_projection(state, ("2/1",)) is None

    def test_tuning_projection_of_just_intonation_is_the_identity(self):
        state = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert service.tuning_projection(state) == (
            ("1", "0", "0"),
            ("0", "1", "0"),
            ("0", "0", "1"),
        )

    def test_tuning_projection_for_a_full_rational_held_basis_quarter_comma(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.tuning_projection(state, ("2/1", "5/4")) == (
            ("1", "1", "0"),
            ("0", "0", "0"),
            ("0", "1/4", "1"),
        )

    def test_tuning_projection_third_comma(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.tuning_projection(state, ("2/1", "6/5")) == (
            ("1", "4/3", "4/3"),
            ("0", "-1/3", "-4/3"),
            ("0", "1/3", "4/3"),
        )

    def test_tuning_projection_pythagorean(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.tuning_projection(state, ("2/1", "3/2")) == (
            ("1", "0", "-4"),
            ("0", "1", "4"),
            ("0", "0", "0"),
        )

    def test_projection_matrix_rationals_returns_the_rational_p(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.projection_matrix_rationals(state, ("2/1", "5/4")) == (
            (Fraction(1), Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(0)),
            (Fraction(0), Fraction(1, 4), Fraction(1)),
        )

    def test_projection_matrix_rationals_is_none_for_an_under_held_tuning(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.projection_matrix_rationals(state) is None
        assert service.projection_matrix_rationals(state, ("2/1",)) is None

    def test_tuning_projection_and_embedding_drop_a_degenerate_held_basis(self):
        state = service.from_mapping(((2, 3, 5, 6), (0, 1, -2, -2)))
        assert service.tuning_projection(state, ("2/1", "7/5")) is None
        assert service.tuning_embedding(state, ("2/1", "7/5")) is None


class TestTuningEmbedding:
    def test_tuning_embedding_for_a_full_rational_held_basis(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.tuning_embedding(state, ("2/1", "5/4")) == (
            ("1", "0"),
            ("0", "0"),
            ("0", "1/4"),
        )

    def test_tuning_embedding_third_comma(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.tuning_embedding(state, ("2/1", "6/5")) == (
            ("1", "1/3"),
            ("0", "-1/3"),
            ("0", "1/3"),
        )

    def test_tuning_embedding_is_dashed_when_the_projection_is(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.tuning_embedding(state) is None
        assert service.tuning_embedding(state, ("2/1",)) is None

    def test_tuning_embedding_of_just_intonation_is_the_identity(self):
        state = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert service.tuning_embedding(state) == (
            ("1", "0", "0"),
            ("0", "1", "0"),
            ("0", "0", "1"),
        )


class TestUnchangedInterval:
    def test_unchanged_ratios_of_tuning_reads_the_held_intervals_off_the_tuning(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        candidates = ("2/1", "5/4", "6/5", "3/2", "9/8")
        default = service.tuning(state.mapping, service.DEFAULT_DOCUMENT_SCHEME)
        assert service.unchanged_ratios_of_tuning(state, default.retuning_map, candidates) == ("2/1", "5/4")
        minimax_s = service.tuning(state.mapping, "minimax-S")
        assert service.unchanged_ratios_of_tuning(state, minimax_s.retuning_map, candidates) == ()

    def test_project_vectors_is_empty_without_a_projection(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        p = service.projection_matrix_rationals(state, ("2/1", "5/4"))
        assert service.project_vectors(None, ((1, 0, 0),)) == ()
        assert service.project_vectors(p, ()) == ()

    def test_unchanged_basis_from_projection_recovers_U_and_rejects_invalid(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        p13 = service.tuning_projection(state, ("2/1", "6/5"))
        U = service.unchanged_basis_from_projection(state, p13)
        assert U is not None and service.tuning_projection(state, service.comma_ratios(U)) == p13
        assert service.unchanged_basis_from_projection(state, (("1", "1", "0"), ("0", "1", "0"), ("0", "0", "1"))) is None
        assert service.unchanged_basis_from_projection(state, (("2", "0", "0"), ("0", "1", "0"), ("0", "0", "1"))) is None

    def test_unchanged_basis_from_embedding_recovers_U_and_rejects_invalid(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        g13 = service.tuning_embedding(state, ("2/1", "6/5"))
        U = service.unchanged_basis_from_embedding(state, g13)
        assert U is not None and service.tuning_embedding(state, service.comma_ratios(U)) == g13
        assert service.unchanged_basis_from_embedding(state, (("2", "0"), ("0", "0"), ("0", "1/4"))) is None

    def test_unchanged_interval_basis_is_all_dashes_for_an_under_held_tuning(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.unchanged_interval_basis(state) == (None, None)
        assert service.unchanged_interval_ratios(state) == ()

    def test_unchanged_interval_basis_pads_a_partial_hold_with_a_dash(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.unchanged_interval_basis(state, ("2/1",)) == ((1, 0, 0), None)
        assert service.unchanged_interval_ratios(state, ("2/1",)) == ("2/1",)

    def test_unchanged_interval_basis_is_the_held_basis_when_full_rank(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.unchanged_interval_basis(state, ("2/1", "5/4")) == ((1, 0, 0), (-2, 0, 1))
        assert service.unchanged_interval_ratios(state, ("2/1", "5/4")) == ("2/1", "5/4")
        assert service.unchanged_interval_basis(state, ("2/1", "6/5")) == ((1, 0, 0), (1, 1, -1))

    def test_unchanged_interval_basis_of_just_intonation_is_every_prime(self):
        state = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        assert service.unchanged_interval_basis(state) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        assert service.unchanged_interval_ratios(state) == ("2/1", "3/1", "5/1")

    def test_unchanged_interval_basis_always_has_r_columns(self):
        state = service.from_mapping(((2, 3, 5, 6), (0, 1, -2, -2)))
        assert service.unchanged_interval_basis(state) == (None, None)
        assert len(service.unchanged_interval_basis(state)) == state.rank == state.dimensionality - state.nullity
        assert service.unchanged_interval_basis(state, ("2/1", "7/1")) == ((1, 0, 0, 0), (0, 0, 0, 1))

    def test_held_basis_vectors_keeps_only_independent_in_domain_intervals(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.held_basis_vectors(state, ("2/1", "4/1")) == ((1, 0, 0),)
        assert service.held_basis_vectors(state, ("2/1", "5/4", "3/2")) == ((1, 0, 0), (-2, 0, 1))

    def test_unchanged_interval_data_dashes_the_directions_an_under_held_tuning_leaves_free(self):
        from rtt.app.service.projection import unchanged_interval_data
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        tuning_map = service.tuning(state.mapping, "minimax-S", state.domain_basis)
        data = unchanged_interval_data(state, ("2/1",), tuning_map, "minimax-S", state.domain_basis)
        assert data.basis == ((1, 0, 0), None)
        assert data.ratios == ("2/1", None)
        assert data.mapped == ((1, None), (0, None))
        assert data.complexities[1] is None and data.complexities[0] is not None


class TestProjectionEmbeddingParsing:
    def test_projection_and_embedding_ebk_match_the_mockup_and_round_trip(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        P = service.tuning_projection(state, ("2/1", "5/4"))
        G = service.tuning_embedding(state, ("2/1", "5/4"))
        assert service.projection_ebk(P, 3) == "[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩"
        assert service.embedding_ebk(G, 3, 2) == "{[1 0 0⟩ [0 0 1/4⟩]"
        assert service.parse_projection(service.projection_ebk(P, 3)) == P
        assert service.parse_embedding(service.embedding_ebk(G, 3, 2), 3, 2) == G
        assert service.projection_ebk(None, 3) == "[⟨— — —]⟨— — —]⟨— — —]⟩"
        assert service.embedding_ebk(None, 3, 2) == "{[— — —⟩ [— — —⟩]"

    def test_projection_and_embedding_parsers_reject_bad_input(self):
        assert service.parse_projection("[[1 0 0⟩[0 1 0⟩[0 0 1⟩]") is None, "COL variance (a vector list), not a map"
        assert service.parse_projection("[⟨1.5 0 0]⟨0 1 0]⟨0 0 1]⟩") is None
        assert service.parse_projection("garbage") is None
        assert service.parse_embedding("[⟨1 1 0]⟨0 1 4]}", 3, 2) is None, "ROW variance (a map), not a vector list"
        assert service.parse_embedding("[[1 0 0⟩[0 0 1/4⟩[0 0 0⟩]", 3, 2) is None
        assert service.parse_embedding("[[1 0⟩[0 1⟩]", 3, 2) is None

    def test_rational_matrix_or_none_accepts_fractions_rejects_floats_and_ragged(self):
        from fractions import Fraction
        assert parse._rational_matrix_or_none(((1, Fraction(1, 4)), (0, -1))) == (("1", "1/4"), ("0", "-1"))
        assert parse._rational_matrix_or_none(((1.5, 0), (0, 1))) is None
        assert parse._rational_matrix_or_none(((True, 0), (0, 1))) is None
        assert parse._rational_matrix_or_none(((1, 0), (0,))) is None
        assert parse._rational_matrix_or_none(()) is None

    def test_int_matrix_or_none_rejects_empty_and_ragged_matrices(self):
        from rtt.app.service.parse import _int_matrix_or_none

        assert _int_matrix_or_none(()) is None
        assert _int_matrix_or_none(((),)) is None
        assert _int_matrix_or_none(((1, 2), (3,))) is None

    def test_parse_embedding_returns_none_on_unparseable_text(self):
        assert service.parse_embedding("not a matrix !!", 3, 2) is None
