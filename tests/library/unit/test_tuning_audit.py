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


# nonstandard-superspace-1 / render-fiddle-1: a held nonprime element over a nonstandard domain
# must be expressed in the domain basis (vector (0,0,1) over 2.3.13/5), not over the prime series
# (a length-6 vector that crashes held @ mapping.T). The held interval comes out exactly just.
def test_held_nonprime_element_over_nonstandard_domain_does_not_crash():
    barbados = parse_temperament_data("2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}")
    spec = TuningSchemeSpec(
        optimization_power=float("inf"), target_intervals="TILT",
        damage_weight_slope="unityWeight", held_intervals="13/5",
    )
    generators = optimize_generator_tuning_map(barbados, spec)
    # 13/5 is the third basis element → vector (0, 0, 1); it must be held exactly just.
    from fractions import Fraction
    just = 1200.0 * np.log2(float(Fraction(13, 5)))
    assert _interval_size(barbados, generators, (0, 0, 1)) == pytest.approx(just, abs=TOL)


def test_held_9_over_2_9_7_means_9_over_8_not_81_over_8():
    # Over 2.9.7, holding 9/8 must mean 2⁻³·9¹ = (−3, 1, 0), not the prime-series (0,3,0) = 81/8.
    # On this rank-2 temperament the prime-series reading silently held 81/8 and left 9/8 ~11.7¢ off.
    t = parse_temperament_data("2.9.7 [⟨1 0 6] ⟨0 1 -1]}")
    spec = TuningSchemeSpec(
        optimization_power=float("inf"), target_intervals="TILT",
        damage_weight_slope="unityWeight", held_intervals="9/8",
    )
    generators = optimize_generator_tuning_map(t, spec)
    just_9_8 = 1200.0 * np.log2(9 / 8)
    assert _interval_size(t, generators, (-3, 1, 0)) == pytest.approx(just_9_8, abs=TOL)


def test_satisfiable_held_constraint_still_solves():
    # the control: independent, consistent held intervals (here exactly r of them) pin the tuning,
    # and both come out exactly just (the held contract) — no refusal.
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


# tuning-core-5: destretching and holding cannot be combined (the destretch un-holds the interval).
def test_destretch_plus_held_is_refused():
    meantone = parse_temperament_data(MEANTONE)
    spec = TuningSchemeSpec(
        optimization_power=float("inf"), target_intervals="{}",
        damage_weight_slope="simplicityWeight", complexity_norm_power=2,
        destretched_interval="octave", held_intervals="3/2",
    )
    with pytest.raises(ValueError):
        optimize_generator_tuning_map(meantone, spec)


# tuning-core-12: destretching by an interval the temperament tempers out (tempered size ≈ 0) is
# refused, not turned into ~1e16-cent garbage.
def test_destretch_by_a_tempered_out_interval_is_refused():
    meantone = parse_temperament_data(MEANTONE)  # tempers out 81/80
    with pytest.raises(ValueError):
        optimize_generator_tuning_map(meantone, "destretched-81/80 minimax-ES")


def test_destretch_octave_still_works():
    # the control: destretching by a non-tempered-out interval (the octave) is fine.
    meantone = parse_temperament_data(MEANTONE)
    assert optimize_tuning_map(meantone, "destretched-octave minimax-ES")[0] == pytest.approx(
        1200.0, abs=TOL
    )


# all-interval-alt-complexity-11/12: optimization and complexity norm powers are bounded to [1, ∞];
# sub-1 powers (which diverge to ~1e308 cents) are refused.
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
def test_sub_one_powers_are_refused(spec):
    meantone = parse_temperament_data(MEANTONE)
    with pytest.raises(ValueError):
        optimize_generator_tuning_map(meantone, spec)


# tuning-core-9: the mean damage of a held-only spec (no targets) is 0.0, not a numpy ValueError.
def test_held_only_mean_damage_is_zero():
    meantone = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
    spec = TuningSchemeSpec(
        optimization_power=float("inf"), target_intervals=None, held_intervals="{2/1, 5/4}"
    )
    assert get_tuning_map_mean_damage(meantone, (1200.0, 1896.578, 2786.314), spec) == 0.0


# tuning-core-7: a crash-inducing complexity-prescaler override (a 0 / negative diagonal, or an
# inf/nan entry) must not reach scipy linprog. A complexity is a norm, so a 0 diagonal makes a
# prime's complexity 0 and, under a simplicity-weight scheme, its weight infinite — which linprog
# rejects with an opaque "A_ub must not contain values inf, nan, or None" raised BEFORE returning
# (so a .success check can't catch it). The solve sanitizes such an override away, falling back to
# the scheme's own prescaler, so no code path (a persisted bad document, a direct API call) crashes.
@pytest.mark.parametrize(
    "bad_prescaler",
    [
        (0.0, 1.585, 2.322),          # a 0 diagonal -> complexity 0 -> inf simplicity weight
        (-1.0, 1.585, 2.322),         # a negative "complexity" is meaningless
        (float("inf"), 1.585, 2.322),  # a non-finite entry
        (float("nan"), 1.585, 2.322),
        ((0.0, 0.0, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322)),  # singular matrix override
    ],
)
def test_crash_inducing_prescaler_override_falls_back_to_the_scheme(bad_prescaler):
    meantone = parse_temperament_data(MEANTONE)
    spec = "minimax-S"  # simplicity-weight: the slope that turns a 0 complexity into an inf weight
    expected = optimize_generator_tuning_map(meantone, spec)  # the scheme's own prescaler
    got = optimize_generator_tuning_map(meantone, spec, prescaler_override=bad_prescaler)
    assert np.allclose(got, expected, atol=TOL)


def test_valid_prescaler_override_still_drives_the_solve():
    # the guard only drops crash-inducing overrides — a legitimate diagonal still changes the optimum
    meantone = parse_temperament_data(MEANTONE)
    spec = "minimax-S"
    baseline = optimize_generator_tuning_map(meantone, spec)
    tweaked = optimize_generator_tuning_map(meantone, spec, prescaler_override=(1.0, 5.0, 1.0))
    assert not np.allclose(tweaked, baseline, atol=TOL)
