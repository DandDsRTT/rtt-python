"""Robustness fixes from the functionality audit: held intervals over a nonstandard domain,
unsatisfiable/underdetermined held constraints, destretch guards, power bounds, and the held-only
mean-damage edge. Each test reproduces an audit repro and asserts the corrected value or refusal."""

import numpy as np
import pytest

from rtt.library.dual import mapping_matrix
from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import (
    get_tuning_map_mean_damage,
    optimize_generator_tuning_map,
    optimize_tuning_map,
)
from rtt.library.tuning_scheme_names import TuningSchemeSpec

TOL = 1e-3
MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"


def _interval_size(t, generators, vector):
    """The tempered size in cents of ``vector`` under the generator tuning ``generators``."""
    tuning_map = np.array(generators, dtype=float) @ np.array(mapping_matrix(t), dtype=float)
    return float(tuning_map @ np.array(vector, dtype=float))


class TestTuningAudit:
    def test_held_nonprime_element_over_nonstandard_domain_does_not_crash(self):
        barbados = parse_temperament_data("2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}")
        spec = TuningSchemeSpec(
            optimization_power=float("inf"), target_intervals="TILT",
            damage_weight_slope="unityWeight", held_intervals="13/5",
        )
        generators = optimize_generator_tuning_map(barbados, spec)
        from fractions import Fraction
        just = 1200.0 * np.log2(float(Fraction(13, 5)))
        assert _interval_size(barbados, generators, (0, 0, 1)) == pytest.approx(just, abs=TOL)

    def test_held_9_over_2_9_7_means_9_over_8_not_81_over_8(self):
        t = parse_temperament_data("2.9.7 [⟨1 0 6] ⟨0 1 -1]}")
        spec = TuningSchemeSpec(
            optimization_power=float("inf"), target_intervals="TILT",
            damage_weight_slope="unityWeight", held_intervals="9/8",
        )
        generators = optimize_generator_tuning_map(t, spec)
        just_9_8 = 1200.0 * np.log2(9 / 8)
        assert _interval_size(t, generators, (-3, 1, 0)) == pytest.approx(just_9_8, abs=TOL)

    def test_satisfiable_held_constraint_still_solves(self):
        magic = parse_temperament_data("[⟨1 0 2] ⟨0 5 1]}")
        spec = TuningSchemeSpec(
            optimization_power=float("inf"), target_intervals="TILT",
            damage_weight_slope="unityWeight", held_intervals="{2/1, 5/4}",
        )
        generators = optimize_generator_tuning_map(magic, spec)
        assert _interval_size(magic, generators, (1, 0, 0)) == pytest.approx(1200.0, abs=TOL)
        assert _interval_size(magic, generators, (-2, 0, 1)) == pytest.approx(
            1200.0 * np.log2(5 / 4), abs=TOL
        )

    def test_destretch_plus_held_is_refused(self):
        meantone = parse_temperament_data(MEANTONE)
        spec = TuningSchemeSpec(
            optimization_power=float("inf"), target_intervals="{}",
            damage_weight_slope="simplicityWeight", complexity_norm_power=2,
            destretched_interval="octave", held_intervals="3/2",
        )
        with pytest.raises(ValueError):
            optimize_generator_tuning_map(meantone, spec)

    def test_destretch_by_a_tempered_out_interval_is_refused(self):
        meantone = parse_temperament_data(MEANTONE)
        with pytest.raises(ValueError):
            optimize_generator_tuning_map(meantone, "destretched-81/80 minimax-ES")

    def test_destretch_octave_still_works(self):
        meantone = parse_temperament_data(MEANTONE)
        assert optimize_tuning_map(meantone, "destretched-octave minimax-ES")[0] == pytest.approx(
            1200.0, abs=TOL
        )

    @pytest.mark.parametrize(
        "spec",
        [
            TuningSchemeSpec(optimization_power=0.5, target_intervals="{2/1, 3/1, 5/4}"),
            TuningSchemeSpec(
                optimization_power=float("inf"), target_intervals="{}",
                damage_weight_slope="simplicityWeight", complexity_norm_power=0.5,
            ),
        ],
    )
    def test_sub_one_powers_are_refused(self, spec):
        meantone = parse_temperament_data(MEANTONE)
        with pytest.raises(ValueError):
            optimize_generator_tuning_map(meantone, spec)

    def test_held_only_mean_damage_is_zero(self):
        meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
        spec = TuningSchemeSpec(
            optimization_power=float("inf"), target_intervals=None, held_intervals="{2/1, 5/4}"
        )
        assert get_tuning_map_mean_damage(meantone, (1200.0, 1896.578, 2786.314), spec) == 0.0

    @pytest.mark.parametrize(
        "bad_prescaler",
        [
            (0.0, 1.585, 2.322),
            (-1.0, 1.585, 2.322),
            (float("inf"), 1.585, 2.322),
            (float("nan"), 1.585, 2.322),
            ((0.0, 0.0, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322)),
        ],
    )
    def test_crash_inducing_prescaler_override_falls_back_to_the_scheme(self, bad_prescaler):
        meantone = parse_temperament_data(MEANTONE)
        spec = "minimax-S"
        expected = optimize_generator_tuning_map(meantone, spec)
        got = optimize_generator_tuning_map(meantone, spec, prescaler_override=bad_prescaler)
        assert np.allclose(got, expected, atol=TOL)

    def test_valid_prescaler_override_still_drives_the_solve(self):
        meantone = parse_temperament_data(MEANTONE)
        spec = "minimax-S"
        baseline = optimize_generator_tuning_map(meantone, spec)
        tweaked = optimize_generator_tuning_map(meantone, spec, prescaler_override=(1.0, 5.0, 1.0))
        assert not np.allclose(tweaked, baseline, atol=TOL)
