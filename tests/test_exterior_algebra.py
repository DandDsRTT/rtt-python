import pytest

from rtt.exterior_algebra import (
    Multivector,
    ea_canonical_form,
    ea_get_d,
    ea_get_n,
    ea_get_r,
    matrix_to_multivector,
    multivector_to_matrix,
)
from rtt.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

MEANTONE_MM = Multivector((1, 4, 4), 2, ROW)
MEANTONE_M = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
CANONICAL_MC = Multivector((107, -87, 72, -49, 31), 4, COL)
CANONICAL_MM = Multivector((31, 49, 72, 87, 107), 1, ROW)
NONDECOMPOSABLE = Multivector((2, -4, 8, -9, 7, 2), 2, ROW)


def test_ea_dimensions():
    assert ea_get_d(MEANTONE_MM) == 3
    assert ea_get_r(MEANTONE_MM) == 2
    assert ea_get_n(MEANTONE_MM) == 1


@pytest.mark.parametrize(
    "u, expected",
    [
        (CANONICAL_MC, CANONICAL_MC),
        (Multivector((-107, 87, -72, 49, -31), 4, COL), CANONICAL_MC),
        (CANONICAL_MM, CANONICAL_MM),
        (Multivector((-31, -49, -72, -87, -107), 1, ROW), CANONICAL_MM),
        (Multivector((4,), 0, ROW, 3), Multivector((1,), 0, ROW, 3)),
        (Multivector((1, 0, 1), 2, ROW), Multivector((1, 0, 1), 2, ROW)),
        (Multivector((0, 0, 0, 0, 0, 0), 2, ROW), Multivector((0, 0, 0, 0, 0, 0), 2, ROW)),
    ],
)
def test_ea_canonical_form(u, expected):
    assert ea_canonical_form(u) == expected


def test_ea_canonical_form_nondecomposable_errors():
    with pytest.raises(ValueError):
        ea_canonical_form(NONDECOMPOSABLE)


@pytest.mark.parametrize(
    "u, expected",
    [
        (Multivector((1,), 0, COL, 1), Temperament(((0,),), COL)),
        (Multivector((1,), 0, ROW, 1), Temperament(((0,),), ROW)),
        (Multivector((1,), 0, COL, 3), Temperament(((0, 0, 0),), COL)),
        (Multivector((1,), 0, ROW, 3), Temperament(((0, 0, 0),), ROW)),
        (MEANTONE_MM, MEANTONE_M),
    ],
)
def test_multivector_to_matrix(u, expected):
    assert multivector_to_matrix(u) == expected


@pytest.mark.parametrize(
    "u",
    [NONDECOMPOSABLE, Multivector((0, 0, 0, 0, 0), 4, ROW)],
)
def test_multivector_to_matrix_errors(u):
    with pytest.raises(ValueError):
        multivector_to_matrix(u)


@pytest.mark.parametrize(
    "t, expected",
    [
        (Temperament(((0,),), COL), Multivector((1,), 0, COL, 1)),
        (Temperament(((0,),), ROW), Multivector((1,), 0, ROW, 1)),
        (Temperament(((0, 0, 0),), COL), Multivector((1,), 0, COL, 3)),
        (Temperament(((0, 0, 0),), ROW), Multivector((1,), 0, ROW, 3)),
        (Temperament(((1, 0), (0, 1)), ROW), Multivector((1,), 2, ROW)),
        (Temperament(((1, 1),), ROW), Multivector((1, 1), 1, ROW)),
        (MEANTONE_M, MEANTONE_MM),
    ],
)
def test_matrix_to_multivector(t, expected):
    assert matrix_to_multivector(t) == expected
