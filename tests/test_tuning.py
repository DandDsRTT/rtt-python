from math import inf, log2, sqrt

import pytest

from rtt.parsing import parse_temperament_data
from rtt.tuning import (
    TuningSchemeSpec,
    generator_tuning_map_from_t_and_tuning_map,
    get_complexity,
    get_dual_power,
    get_just_tuning_map,
    optimize_generator_tuning_map,
)
from rtt.temperament import Temperament, Variance

ROW = Variance.ROW
TOL = 1e-3

MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"
SIX_TILT = "{2/1, 3/1, 3/2, 4/3, 5/2, 5/3, 5/4, 6/5}"

# (optimization_power, damage_weight_slope, log_prime_power [5a], norm_power [4], expected)
# Mirrors tests.m 2588-2624: meantone optimized over the sixTilt target-interval set
# across all three powers, three damage-weight slopes, and complexity-trait variants.
EXPLICIT_CASES = [
    (inf, "unityWeight", 1, 1, (1200.000, 696.578)),
    (inf, "simplicityWeight", 0, 1, (1202.390, 697.176)),
    (inf, "simplicityWeight", 0, 2, (1202.728, 697.260)),
    (inf, "simplicityWeight", 1, 1, (1201.699, 697.564)),
    (inf, "simplicityWeight", 1, 2, (1201.600, 697.531)),
    (inf, "complexityWeight", 0, 1, (1197.610, 694.786)),
    (inf, "complexityWeight", 0, 2, (1197.435, 694.976)),
    (inf, "complexityWeight", 1, 1, (1197.979, 694.711)),
    (inf, "complexityWeight", 1, 2, (1198.423, 695.209)),
    (2, "unityWeight", 1, 1, (1202.081, 697.099)),
    (2, "simplicityWeight", 0, 1, (1202.609, 697.329)),
    (2, "simplicityWeight", 0, 2, (1202.729, 697.210)),
    (2, "simplicityWeight", 1, 1, (1201.617, 697.379)),
    (2, "simplicityWeight", 1, 2, (1201.718, 697.214)),
    (2, "complexityWeight", 0, 1, (1200.813, 696.570)),
    (2, "complexityWeight", 0, 2, (1200.522, 696.591)),
    (2, "complexityWeight", 1, 1, (1201.489, 696.662)),
    (2, "complexityWeight", 1, 2, (1201.535, 696.760)),
    (1, "unityWeight", 1, 1, (1204.301, 697.654)),
    (1, "simplicityWeight", 0, 1, (1204.301, 697.654)),
    (1, "simplicityWeight", 0, 2, (1204.301, 697.654)),
    (1, "simplicityWeight", 1, 1, (1200.000, 696.578)),
    (1, "simplicityWeight", 1, 2, (1200.000, 696.578)),
    (1, "complexityWeight", 0, 1, (1200.000, 696.578)),
    (1, "complexityWeight", 0, 2, (1200.000, 696.578)),
    (1, "complexityWeight", 1, 1, (1204.301, 697.654)),
    (1, "complexityWeight", 1, 2, (1204.301, 697.654)),
]


@pytest.mark.parametrize("power, slope, log_prime_power, norm_power, expected", EXPLICIT_CASES)
def test_optimize_generator_tuning_map_explicit(
    power, slope, log_prime_power, norm_power, expected
):
    t = parse_temperament_data(MEANTONE)
    spec = TuningSchemeSpec(
        optimization_power=power,
        target_intervals=SIX_TILT,
        damage_weight_slope=slope,
        complexity_log_prime_power=log_prime_power,
        complexity_norm_power=norm_power,
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


def test_get_just_tuning_map_standard():
    t = Temperament(((12, 19, 28),), ROW, (2, 3, 5))
    expected = (1200 * log2(2), 1200 * log2(3), 1200 * log2(5))
    assert get_just_tuning_map(t) == pytest.approx(expected, abs=TOL)


def test_get_just_tuning_map_nonstandard_basis():
    t = Temperament(((1, 0, -4, 0), (0, 1, 2, 0), (0, 0, 0, 1)), ROW, (2, 9, 5, 21))
    expected = (1200 * log2(2), 1200 * log2(9), 1200 * log2(5), 1200 * log2(21))
    assert get_just_tuning_map(t) == pytest.approx(expected, abs=TOL)


@pytest.mark.parametrize(
    "norm_power, log_prime_power, expected",
    [
        (1, 0, 3),
        (2, 0, sqrt(3)),
        (1, 1, 1 + log2(3) + log2(5)),
    ],
)
def test_get_complexity(norm_power, log_prime_power, expected):
    dummy = Temperament(((1, 2, 3), (0, 5, 6)), ROW)
    result = get_complexity((1, 1, -1), dummy, norm_power, log_prime_power, 0, 0, "")
    assert result == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize(
    "power, expected", [(1, float("inf")), (2, 2), (float("inf"), 1)]
)
def test_get_dual_power(power, expected):
    assert get_dual_power(power) == expected


def test_generator_tuning_map_from_t_and_tuning_map():
    meantone_m = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
    quarter_comma_tuning_map = (1200.000, 1896.578, 2786.314)
    result = generator_tuning_map_from_t_and_tuning_map(
        meantone_m, quarter_comma_tuning_map
    )
    assert result == pytest.approx((1200.000, 696.578), abs=TOL)
