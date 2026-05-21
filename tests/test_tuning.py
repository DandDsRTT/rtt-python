from math import log2, sqrt

import pytest

from rtt.parsing import parse_temperament_data
from rtt.tuning import (
    generator_tuning_map_from_t_and_tuning_map,
    get_complexity,
    get_dual_power,
    get_just_tuning_map,
)
from rtt.temperament import Temperament, Variance

ROW = Variance.ROW
TOL = 1e-3


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
