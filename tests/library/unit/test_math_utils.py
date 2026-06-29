from fractions import Fraction

import pytest

from rtt.library.math_utils import (
    equave_reduce,
    get_primes,
    octave_reduce,
    pad_vectors_with_zeros_up_to_d,
    pcv_to_quotient,
    quotient_to_pcv,
    super_,
)


class TestMathUtils:
    @pytest.mark.parametrize(
        "quotient, expected",
        [
            (3, Fraction(3, 2)),
            (5, Fraction(5, 4)),
            (Fraction(2, 3), Fraction(4, 3)),
        ],
    )
    def test_octave_reduce(self, quotient, expected):
        assert octave_reduce(quotient) == expected

    @pytest.mark.parametrize(
        "quotient, equave, expected",
        [
            (Fraction(9, 4), 2, Fraction(9, 8)),
            (2, 2, Fraction(1)),
            (Fraction(2, 3), 2, Fraction(4, 3)),
            (Fraction(5, 4), 2, Fraction(5, 4)),
            (9, 3, Fraction(1)),
            (5, 3, Fraction(5, 3)),
            (7, 3, Fraction(7, 3)),
            (10, 3, Fraction(10, 9)),
        ],
    )
    def test_equave_reduce(self, quotient, equave, expected):
        assert equave_reduce(quotient, equave) == expected

    def test_octave_reduce_is_equave_reduce_by_two(self):
        for q in (3, 5, Fraction(2, 3), Fraction(9, 4), 7):
            assert octave_reduce(q) == equave_reduce(q, 2)

    def test_get_primes(self):
        assert get_primes(5) == (2, 3, 5, 7, 11)

    @pytest.mark.parametrize(
        "quotient, expected",
        [
            (Fraction(22, 5), (1, 0, -1, 0, 1)),
            (1, (0,)),
        ],
    )
    def test_quotient_to_pcv(self, quotient, expected):
        assert quotient_to_pcv(quotient) == expected

    @pytest.mark.parametrize(
        "pcv, expected",
        [
            ((1, 0, -1, 0, 1), Fraction(22, 5)),
            ((0,), Fraction(1)),
        ],
    )
    def test_pcv_to_quotient(self, pcv, expected):
        assert pcv_to_quotient(pcv) == expected

    @pytest.mark.parametrize(
        "quotient, expected",
        [
            (Fraction(5, 3), Fraction(5, 3)),
            (Fraction(3, 5), Fraction(5, 3)),
        ],
    )
    def test_super(self, quotient, expected):
        assert super_(quotient) == expected

    def test_pad_vectors_with_zeros_up_to_d(self):
        assert pad_vectors_with_zeros_up_to_d(((1, 2, 3), (4, 5, 6)), 5) == (
            (1, 2, 3, 0, 0),
            (4, 5, 6, 0, 0),
        )
