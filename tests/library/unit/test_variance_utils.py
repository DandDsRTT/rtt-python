import pytest

from rtt.library.temperament import Temperament, Variance
from rtt.library.variance_utils import (
    add_t,
    is_cols,
    is_rows,
    multiply,
    reinterpret_as_dual_variance,
    scale,
    subtract_t,
)

ROW, COL = Variance.ROW, Variance.COL
M = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
ONES = Temperament(((1, 1, 1), (1, 1, 1)), ROW)
MAP = Temperament(((12, 19, 28),), ROW)
ONES_MAP = Temperament(((1, 1, 1),), ROW)


MAP_1X3 = Temperament(((1, 1, 1),), ROW)
MAP_2X3 = Temperament(((1, 1, 1), (1, 1, 1)), ROW)
COMMAS_1 = Temperament(((1, 1, 1),), COL)
COMMAS_2 = Temperament(((1, 1, 1), (1, 1, 1)), COL)


class TestVarianceUtils:
    def test_is_cols(self):
        assert is_cols(Temperament(M.matrix, COL)) is True
        assert is_cols(M) is False
        assert is_cols(Temperament(M.matrix, Variance.from_string("comma basis"))) is True

    def test_is_rows(self):
        assert is_rows(M) is True
        assert is_rows(Temperament(M.matrix, COL)) is False
        assert is_rows(Temperament(M.matrix, Variance.from_string("comma basis"))) is False

    def test_scale(self):
        assert scale(M, 2) == Temperament(((2, 0, -8), (0, 2, 8)), ROW)
        assert scale(MAP, 2) == Temperament(((24, 38, 56),), ROW)

    def test_add_t(self):
        assert add_t(M, ONES) == Temperament(((2, 1, -3), (1, 2, 5)), ROW)
        assert add_t(MAP, ONES_MAP) == Temperament(((13, 20, 29),), ROW)

    def test_subtract_t(self):
        assert subtract_t(M, ONES) == Temperament(((0, -1, -5), (-1, 0, 3)), ROW)
        assert subtract_t(MAP, ONES_MAP) == Temperament(((11, 18, 27),), ROW)

    @pytest.mark.parametrize(
        "factors, variance, expected",
        [
            ([MAP_1X3, COMMAS_1], ROW, 3),
            ([MAP_1X3, COMMAS_2], ROW, Temperament(((3, 3),), ROW)),
            ([MAP_2X3, COMMAS_1], ROW, Temperament(((3,), (3,)), ROW)),
            ([MAP_2X3, COMMAS_2], ROW, Temperament(((3, 3), (3, 3)), ROW)),
            ([MAP_1X3, COMMAS_1], COL, 3),
            ([MAP_1X3, COMMAS_2], COL, Temperament(((3, 3),), COL)),
            ([MAP_2X3, COMMAS_1], COL, Temperament(((3, 3),), COL)),
            ([MAP_2X3, COMMAS_2], COL, Temperament(((3, 3), (3, 3)), COL)),
        ],
    )
    def test_multiply(self, factors, variance, expected):
        assert multiply(factors, variance) == expected

    def test_reinterpret_as_dual_variance(self):
        assert reinterpret_as_dual_variance(
            Temperament(((1, 2, 3), (4, 5, 6)), ROW)
        ) == Temperament(((1, 2, 3), (4, 5, 6)), COL)
        assert reinterpret_as_dual_variance(
            Temperament(((1, 2, 3), (4, 5, 6)), COL)
        ) == Temperament(((1, 2, 3), (4, 5, 6)), ROW)
        assert reinterpret_as_dual_variance(Temperament(((1, 2, 3),), ROW)) == Temperament(
            ((1, 2, 3),), COL
        )
        assert reinterpret_as_dual_variance(Temperament(((1, 2, 3),), COL)) == Temperament(
            ((1, 2, 3),), ROW
        )
