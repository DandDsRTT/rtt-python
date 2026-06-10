from fractions import Fraction

import pytest

from rtt.library.math_utils import (
    get_primes,
    octave_reduce,
    pad_vectors_with_zeros_up_to_d,
    pcv_to_quotient,
    quotient_to_pcv,
    super_,
)


@pytest.mark.parametrize(
    "quotient, expected",
    [
        (3, Fraction(3, 2)),
        (5, Fraction(5, 4)),
        (Fraction(2, 3), Fraction(4, 3)),
    ],
)
def test_octave_reduce(quotient, expected):
    assert octave_reduce(quotient) == expected


def test_get_primes():
    assert get_primes(5) == (2, 3, 5, 7, 11)


@pytest.mark.parametrize(
    "quotient, expected",
    [
        (Fraction(22, 5), (1, 0, -1, 0, 1)),
        (1, (0,)),
    ],
)
def test_quotient_to_pcv(quotient, expected):
    assert quotient_to_pcv(quotient) == expected


@pytest.mark.parametrize(
    "pcv, expected",
    [
        ((1, 0, -1, 0, 1), Fraction(22, 5)),
        ((0,), Fraction(1)),
    ],
)
def test_pcv_to_quotient(pcv, expected):
    assert pcv_to_quotient(pcv) == expected


@pytest.mark.parametrize(
    "quotient, expected",
    [
        (Fraction(5, 3), Fraction(5, 3)),
        (Fraction(3, 5), Fraction(5, 3)),
    ],
)
def test_super(quotient, expected):
    assert super_(quotient) == expected


def test_pad_vectors_with_zeros_up_to_d():
    assert pad_vectors_with_zeros_up_to_d(((1, 2, 3), (4, 5, 6)), 5) == (
        (1, 2, 3, 0, 0),
        (4, 5, 6, 0, 0),
    )
