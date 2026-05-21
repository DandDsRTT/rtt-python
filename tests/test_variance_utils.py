from rtt.temperament import Temperament, Variance
from rtt.variance_utils import add_t, is_cols, is_rows, scale, subtract_t, transpose

ROW, COL = Variance.ROW, Variance.COL
M = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
ONES = Temperament(((1, 1, 1), (1, 1, 1)), ROW)
MAP = Temperament(((12, 19, 28),), ROW)
ONES_MAP = Temperament(((1, 1, 1),), ROW)


def test_is_cols():
    assert is_cols(Temperament(M.matrix, COL)) is True
    assert is_cols(M) is False
    assert is_cols(Temperament(M.matrix, Variance.from_string("comma basis"))) is True


def test_is_rows():
    assert is_rows(M) is True
    assert is_rows(Temperament(M.matrix, COL)) is False
    assert is_rows(Temperament(M.matrix, Variance.from_string("comma basis"))) is False


def test_scale():
    assert scale(M, 2) == Temperament(((2, 0, -8), (0, 2, 8)), ROW)
    assert scale(MAP, 2) == Temperament(((24, 38, 56),), ROW)


def test_add_t():
    assert add_t(M, ONES) == Temperament(((2, 1, -3), (1, 2, 5)), ROW)
    assert add_t(MAP, ONES_MAP) == Temperament(((13, 20, 29),), ROW)


def test_subtract_t():
    assert subtract_t(M, ONES) == Temperament(((0, -1, -5), (-1, 0, 3)), ROW)
    assert subtract_t(MAP, ONES_MAP) == Temperament(((11, 18, 27),), ROW)


def test_transpose():
    assert transpose(Temperament(((1, 2, 3), (4, 5, 6)), ROW)) == Temperament(
        ((1, 2, 3), (4, 5, 6)), COL
    )
    assert transpose(Temperament(((1, 2, 3), (4, 5, 6)), COL)) == Temperament(
        ((1, 2, 3), (4, 5, 6)), ROW
    )
    assert transpose(Temperament(((1, 2, 3),), ROW)) == Temperament(((1, 2, 3),), COL)
    assert transpose(Temperament(((1, 2, 3),), COL)) == Temperament(((1, 2, 3),), ROW)
