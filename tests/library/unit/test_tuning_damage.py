"""Mean damage and per-interval damages of a *given* tuning (tests.m 3958-3997). Unlike the
optimizers, these evaluate how much a supplied tuning mistunes the target intervals: each
damage is the scheme-weighted absolute error, and the mean damage is their power-mean at the
optimization power (max for minimax, RMS for miniRMS, arithmetic mean for miniaverage, ...)."""

from fractions import Fraction
from math import inf

import pytest

from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import (
    get_generator_tuning_map_damages,
    get_generator_tuning_map_mean_damage,
    get_tuning_map_damages,
    get_tuning_map_mean_damage,
)
from rtt.library.tuning_scheme_names import TuningSchemeSpec

TOL = 1e-3
MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"
FIVE_OLD = "{2/1, 3/2, 4/3, 5/4, 8/5, 5/3, 6/5}"
SIX_TILT = "{2/1, 3/1, 3/2, 4/3, 5/2, 5/3, 5/4, 6/5}"
PRIMES_235 = TuningSchemeSpec(
    optimization_power=inf, target_intervals="{2/1, 3/1, 5/1}", damage_weight_slope="unityWeight"
)


# getGeneratorTuningMapMeanDamage (tests.m 3962-3970): same tuning, different schemes -> the
# mean varies with the optimization power (sum / sos / sop / max).
GENERATOR_MEAN_DAMAGE = [
    ((1201.70, 697.564), "minimax-S", 1.700),
    ((1199.02, 695.601), f"held-octave {FIVE_OLD} miniRMS-U", 3.893),
    ((1200.00, 696.578), f"held-octave {FIVE_OLD} minimax-U", 5.377),
    ((1200.00, 696.594), "TILT miniRMS-S", 1.625),
    ((1200.00, 696.594), "TILT miniaverage-S", 1.185),
    ((1200.00, 696.594), "TILT mini-3-mean-S", 1.901),
    ((1200.00, 696.594), "TILT minimax-S", 3.382),
]


@pytest.mark.parametrize("generators, scheme, expected", GENERATOR_MEAN_DAMAGE)
def test_generator_tuning_map_mean_damage(generators, scheme, expected):
    t = parse_temperament_data(MEANTONE)
    assert get_generator_tuning_map_mean_damage(t, generators, scheme) == pytest.approx(
        expected, abs=TOL
    )


# getTuningMapMeanDamage (tests.m 3973-3975): a given full tuning map.
def test_tuning_map_mean_damage():
    meantone = parse_temperament_data(MEANTONE)
    assert get_tuning_map_mean_damage(
        meantone, (1200.000, 1897.564, 2786.314), PRIMES_235
    ) == pytest.approx(4.391, abs=TOL)
    et = parse_temperament_data("⟨12 29 28]")
    assert get_tuning_map_mean_damage(
        et, (1200, 1900, 2800), f"{SIX_TILT} miniRMS-U"
    ) == pytest.approx(10.461, abs=TOL)
    assert get_tuning_map_mean_damage(
        et, (1200, 1900, 2800), f"{SIX_TILT} miniaverage-U"
    ) == pytest.approx(8.065, abs=TOL)


def _assert_damages(actual: dict, expected: dict):
    assert {Fraction(k) for k in actual} == {Fraction(k) for k in expected}
    for quotient, damage in expected.items():
        assert actual[Fraction(quotient)] == pytest.approx(damage, abs=TOL)


# getGeneratorTuningMapDamages (tests.m 3991-3993).
def test_generator_tuning_map_damages():
    meantone = parse_temperament_data(MEANTONE)
    _assert_damages(
        get_generator_tuning_map_damages(meantone, (1201.7, 697.564), "minimax-S"),
        {2: 1.700, 3: 1.698, 5: 1.698},
    )
    _assert_damages(
        get_generator_tuning_map_damages(meantone, (1199.02, 695.601), "TILT miniRMS-U"),
        {"2/1": 0.980, "3/1": 7.334, "3/2": 6.354, "4/3": 5.374,
         "5/2": 2.930, "5/3": 3.424, "5/4": 1.950, "6/5": 4.404},
    )
    _assert_damages(
        get_generator_tuning_map_damages(meantone, (1200.0, 696.578), "TILT minimax-U"),
        {"2/1": 0.000, "3/1": 5.377, "3/2": 5.377, "4/3": 5.377,
         "5/2": 0.002, "5/3": 5.375, "5/4": 0.002, "6/5": 5.375},
    )


# getTuningMapDamages (tests.m 3996-3997).
def test_tuning_map_damages():
    meantone = parse_temperament_data(MEANTONE)
    _assert_damages(
        get_tuning_map_damages(meantone, (1200.000, 1897.564, 2786.314), PRIMES_235),
        {2: 0.000, 3: 4.391, 5: 0.000},
    )
    et = parse_temperament_data("⟨12 29 28]")
    _assert_damages(
        get_tuning_map_damages(et, (1200, 1900, 2800), f"{SIX_TILT} miniRMS-U"),
        {"2/1": 0.000, "3/1": 1.955, "3/2": 1.955, "4/3": 1.955,
         "5/2": 13.686, "5/3": 15.641, "5/4": 13.686, "6/5": 15.641},
    )
