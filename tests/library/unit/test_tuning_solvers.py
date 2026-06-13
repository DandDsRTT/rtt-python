"""Low-level solver behavior: the p = 1 (miniaverage) tie-break and the underdetermined-tuning
refusal. These guard the audit fixes for tuning-core-1 (underdetermined target sets) and
tuning-core-4 (the p → 1⁺ limit of a tied miniaverage optimum)."""

import numpy as np
import pytest

from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import optimize_generator_tuning_map
from rtt.library.tuning_scheme_names import TuningSchemeSpec, damage_name_traits
from rtt.library.tuning_solvers import solve_optimum

TOL = 1e-3

MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"
MAGIC = "[⟨1 0 2] ⟨0 5 1]}"
SRUTAL = "[⟨2 0 11] ⟨0 1 -2]}"
SIX_TILT = "{2/1, 3/1, 3/2, 4/3, 5/2, 5/3, 5/4, 6/5}"


# tuning-core-4: a tied p = 1 optimum is resolved to the true p → 1⁺ limit (an interior point of
# the tied range), independently confirmed by the power-limit method, not an arbitrary LP vertex.
def test_miniaverage_tied_optimum_is_the_power_limit_not_an_endpoint():
    magic = parse_temperament_data(MAGIC)
    # The tied range runs over the octave 1200..1202.961 (third fixed); the LP lands on the 1200
    # endpoint, but the true p → 1 optimum is the interior 1201.974.
    assert optimize_generator_tuning_map(magic, "TILT miniaverage-U") == pytest.approx(
        (1201.974, 380.391), abs=2e-3
    )


def test_miniaverage_tied_srutal_copfr_resolves_to_interior_limit():
    srutal = parse_temperament_data(SRUTAL)
    spec = TuningSchemeSpec(
        optimization_power=1, target_intervals=SIX_TILT, **damage_name_traits("copfr-S-damage")
    )
    assert optimize_generator_tuning_map(srutal, spec) == pytest.approx(
        (599.052, 1901.955), abs=2e-3
    )


def test_miniaverage_unique_optimum_is_the_exact_lp_vertex():
    # When the optimum is unique the LP vertex is returned untouched (no power-limit drift): the
    # uniqueness gate must leave well-determined miniaverage tunings exactly as before.
    meantone = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(meantone, f"{SIX_TILT} miniaverage-S") == pytest.approx(
        (1200.000, 696.578), abs=TOL
    )


def test_miniaverage_result_is_deterministic_across_repeats():
    # The tie-break must give a STABLE result regardless of the (LP-based, load-sensitive)
    # uniqueness fast-path: a tied optimum always lands on its interior p→1⁺ limit and a
    # determined one always lands on its exact vertex, on every call. (Regression for a uniqueness
    # gate that could transiently misfire under heavy parallel load before the snap-back.)
    magic = parse_temperament_data(MAGIC)
    meantone = parse_temperament_data(MEANTONE)
    for _ in range(5):
        assert optimize_generator_tuning_map(magic, "TILT miniaverage-U") == pytest.approx(
            (1201.974, 380.391), abs=2e-3
        )
        assert optimize_generator_tuning_map(
            meantone, f"{SIX_TILT} miniaverage-S"
        ) == pytest.approx((1200.000, 696.578), abs=TOL)


# tuning-core-1: an underdetermined target set (a free generator) no longer leaves that generator
# at a silent 0 cents — it defaults toward the just tuning (digest O24: 'a human would default to
# tuning the unrepresented prime justly'). The fifth comes out a sensible ~696.7¢, never 0.
def test_underdetermined_free_generator_defaults_toward_just_not_zero():
    meantone = parse_temperament_data(MEANTONE)
    # 1-OLD = targets {2/1} alone: the octave is pinned, the fifth generator is free.
    octave, fifth = optimize_generator_tuning_map(meantone, "1-OLD minimax-U")
    assert octave == pytest.approx(1200.0, abs=TOL)
    assert fifth == pytest.approx(696.741, abs=1e-2)  # toward just, NOT 0¢


def test_empty_target_set_defaults_toward_just_not_zero():
    meantone = parse_temperament_data(MEANTONE)
    # 1-TILT = an empty target set: both generators free → the whole tuning defaults toward just.
    generators = optimize_generator_tuning_map(meantone, "1-TILT minimax-U")
    assert generators == pytest.approx((1202.607, 696.741), abs=1e-2)
    assert all(abs(g) > 1.0 for g in generators)  # nothing silently 0


def test_underdetermined_missing_prime_tunes_that_prime_justly():
    # 5-limit JI (rank 3) with no 5-bearing target → prime 5 is unrepresented; instead of 0¢ it
    # comes out exactly just (its prime axis is the free direction defaulted to just).
    ji = parse_temperament_data("[⟨1 0 0] ⟨0 1 0] ⟨0 0 1]}")
    spec = TuningSchemeSpec(
        optimization_power=float("inf"),
        target_intervals="{2/1, 3/1, 3/2, 4/3, 8/3, 9/4}",  # no factor of 5 (digest O24)
        damage_weight_slope="unityWeight",
    )
    generators = optimize_generator_tuning_map(ji, spec)
    prime_5_cents = generators[2]  # JI: the 3rd generator IS prime 5's tuning
    assert prime_5_cents == pytest.approx(1200.0 * np.log2(5), abs=TOL)  # just, not 0


def test_well_determined_target_set_is_a_no_op_for_the_just_default():
    # the control: a full, all-primes-represented set has no free directions, so the just-default
    # leaves the optimum exactly unchanged.
    meantone = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(meantone, "TILT minimax-U") == pytest.approx(
        (1200.000, 696.578), abs=TOL
    )


def test_solve_optimum_power_two_still_solves_lstsq():
    # solve_optimum's normal paths are unchanged (regression guard for the refactor).
    tempered = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    just = np.array([100.0, 200.0, 305.0])
    result = solve_optimum(tempered, just, 2, 2)
    assert result == pytest.approx(np.linalg.lstsq(tempered, just, rcond=None)[0], abs=1e-9)
