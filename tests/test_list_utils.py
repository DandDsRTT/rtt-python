from fractions import Fraction

import pytest

from rtt.list_utils import (
    all_zeros_l,
    divide_out_gcd,
    leading_entry,
    mult_by_lcd,
    trailing_entry,
)


@pytest.mark.parametrize(
    "values, expected",
    [
        ((0, -6, 9), (0, -2, 3)),
        ((-1, -2, -3), (-1, -2, -3)),
        ((0, 0, 0), (0, 0, 0)),
    ],
)
def test_divide_out_gcd(values, expected):
    assert divide_out_gcd(values) == expected


def test_mult_by_lcd():
    assert mult_by_lcd((Fraction(1, 3), 1, Fraction(2, 5))) == (5, 15, 6)


def test_leading_entry():
    assert leading_entry((0, -6, 9, 0)) == -6


def test_trailing_entry():
    assert trailing_entry((0, -6, 9, 0)) == 9


@pytest.mark.parametrize("values, expected", [((0, -6, 9), False), ((0, 0, 0), True)])
def test_all_zeros_l(values, expected):
    assert all_zeros_l(values) == expected
