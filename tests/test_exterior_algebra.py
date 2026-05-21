import pytest

from rtt.exterior_algebra import (
    Multivector,
    ea_canonical_form,
    ea_dual,
    ea_get_d,
    ea_get_n,
    ea_get_r,
    interior_product,
    left_interior_product,
    matrix_to_multivector,
    multivector_to_matrix,
    progressive_product,
    regressive_product,
    right_interior_product,
)
from rtt.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

# Named multivectors for the product tests (tests.m 1737-1959).
D2G1CO1 = Multivector((12, 19), 1, ROW)
D2G1CO2 = Multivector((19, 30), 1, ROW)
D2JICO = Multivector((1,), 2, ROW)
D3G1CO1 = Multivector((12, 19, 28), 1, ROW)
D3G1CO2 = Multivector((19, 30, 44), 1, ROW)
D3G1CO3 = Multivector((22, 35, 51), 1, ROW)
D3G2CO1 = Multivector((1, 4, 4), 2, ROW)
D3G2CO2 = Multivector((3, 5, 1), 2, ROW)
D3JICO = Multivector((1,), 3, ROW)
D3UNISONCO = Multivector((1,), 0, ROW, 3)
D3G1CONTRA1 = Multivector((4, -4, 1), 1, COL)
D3G1CONTRA2 = Multivector((-10, -1, 5), 1, COL)
D3G1CONTRA3 = Multivector((1, -5, 3), 1, COL)
D3G2CONTRA1 = Multivector((44, -30, 19), 2, COL)
D3G2CONTRA2 = Multivector((28, -19, 12), 2, COL)
D3G2CONTRA3 = Multivector((51, -35, 22), 2, COL)
D3JICONTRA = Multivector((1,), 0, COL, 3)
D3UNISONCONTRA = Multivector((1,), 3, COL)
D5G1CO = Multivector((31, 49, 72, 87, 107), 1, ROW)
D5G2CO1 = Multivector((-9, -5, 3, -7, 13, 30, 20, 21, 1, -30), 2, ROW)
D5G2CO2 = Multivector((1, 4, -2, -6, 4, -6, -13, -16, -28, -10), 2, ROW)
D5G2CO3 = Multivector((6, -7, -2, 15, -25, -20, 3, 15, 59, 49), 2, ROW)
D5G3CO = Multivector((1, 2, -3, -2, 1, -4, -5, 12, 9, -19), 3, ROW)
D5G4CO = Multivector((1, 2, 1, 2, 3), 4, ROW)
D5G1CONTRA = Multivector((-3, 2, -1, 2, -1), 1, COL)
D5G2CONTRA = Multivector((5, 11, -7, -4, -9, 8, 1, 5, -5, 5), 2, COL)
D5G3CONTRA = Multivector((19, -33, 14, -46, 46, -46, 29, -29, 29, 0), 3, COL)

ET5_MM = matrix_to_multivector(Temperament(((5, 8, 12),), ROW))
ET7_MM = matrix_to_multivector(Temperament(((7, 11, 16),), ROW))
MEANTONE_MC = matrix_to_multivector(Temperament(((4, -4, 1),), COL))
PORCUPINE_MC = matrix_to_multivector(Temperament(((1, -5, 3),), COL))
ET7_MC = matrix_to_multivector(Temperament(((-11, 7, 0), (-7, 3, 1)), COL))
MEANTONE_MM11 = matrix_to_multivector(
    Temperament(((1, 0, -4, -13, -25), (0, 1, 4, 10, 18)), ROW)
)
MEANPOP_MM11 = matrix_to_multivector(
    Temperament(((1, 0, -4, -13, 24), (0, 1, 4, 10, -13)), ROW)
)

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
    "u, expected",
    [
        (CANONICAL_MC, CANONICAL_MM),
        (Multivector((-107, 87, -72, 49, -31), 4, COL), CANONICAL_MM),
        (CANONICAL_MM, CANONICAL_MC),
        (Multivector((-31, -49, -72, -87, -107), 1, ROW), CANONICAL_MC),
        (Multivector((1,), 0, COL, 3), Multivector((1,), 3, ROW)),
        (Multivector((1,), 0, ROW, 5), Multivector((1,), 5, COL)),
        (Multivector((1, 0, 1), 2, ROW), Multivector((1, 0, 1), 1, COL)),
        (MEANTONE_MM, Multivector((4, -4, 1), 1, COL)),
    ],
)
def test_ea_dual(u, expected):
    assert ea_dual(u) == expected


def test_ea_dual_nondecomposable_errors():
    with pytest.raises(ValueError):
        ea_dual(NONDECOMPOSABLE)


@pytest.mark.parametrize(
    "t",
    [
        Temperament(((1, 0, -4), (0, 1, 4)), ROW),
        Temperament(((4, -4, 1),), COL),
        Temperament(((12, 19, 28),), ROW),
        Temperament(((1, 0, -4, -13), (0, 1, 4, 10)), ROW),
        Temperament(((5, 8, 12), (7, 11, 16)), ROW),
        Temperament(((1, 1),), ROW),
        Temperament(((1, 0, 0), (0, 1, 0), (0, 0, 1)), ROW),
    ],
)
def test_ea_dual_is_an_involution(t):
    u = matrix_to_multivector(t)
    assert ea_dual(ea_dual(u)) == u


@pytest.mark.parametrize(
    "op, u1, u2, expected",
    [
        (progressive_product, D2G1CO1, D2G1CO2, D2JICO),
        (progressive_product, D3G1CO1, D3G1CO1, Multivector((0, 0, 0), 2, ROW)),
        (progressive_product, D5G2CO1, D5G2CO2, D5G4CO),
        (progressive_product, D3G2CONTRA1, D3G1CONTRA3, D3UNISONCONTRA),
        (progressive_product, D3G2CO1, D3G1CO3, D3JICO),
        (progressive_product, ET5_MM, ET7_MM, matrix_to_multivector(MEANTONE_M)),
        (progressive_product, MEANTONE_MC, PORCUPINE_MC, ET7_MC),
        (progressive_product, MEANTONE_MM11, MEANPOP_MM11, Multivector((0, 0, 0, 0, 0), 4, ROW)),
        (regressive_product, D3G2CONTRA1, D3G2CONTRA2, D3G1CONTRA1),
        (regressive_product, D3G1CONTRA1, D3G2CONTRA3, D3JICONTRA),
        (regressive_product, D3G1CO1, D3G2CO2, D3UNISONCO),
        (right_interior_product, D5G3CO, D5G1CONTRA, D5G2CO3),
        (left_interior_product, D5G1CONTRA, D5G3CO, D5G2CO3),
        (interior_product, D5G1CONTRA, D5G3CO, D5G2CO3),
        (interior_product, D5G3CO, D5G1CONTRA, D5G2CO3),
        (right_interior_product, D5G3CONTRA, D5G1CO, D5G2CONTRA),
        (left_interior_product, D5G1CO, D5G3CONTRA, D5G2CONTRA),
        (interior_product, D5G1CO, D5G3CONTRA, D5G2CONTRA),
        (interior_product, D5G3CONTRA, D5G1CO, D5G2CONTRA),
    ],
)
def test_ea_products(op, u1, u2, expected):
    assert op(u1, u2) == expected


@pytest.mark.parametrize(
    "op, u1, u2",
    [
        (progressive_product, D3G2CONTRA1, D3G2CONTRA2),  # grade exceeds d
        (progressive_product, D3G2CO1, D3G2CO2),
        (regressive_product, D3G1CONTRA1, D3G1CONTRA2),  # grade below 0
        (regressive_product, D3G1CO1, D3G1CO2),
        (right_interior_product, D5G1CONTRA, D5G3CO),
        (left_interior_product, D5G3CO, D5G1CONTRA),
        (right_interior_product, D5G1CO, D5G3CONTRA),
        (left_interior_product, D5G3CONTRA, D5G1CO),
        (progressive_product, D5G1CONTRA, D5G3CO),  # mixed variance
        (regressive_product, D5G1CONTRA, D5G3CO),
        (right_interior_product, D5G2CO1, D5G2CO2),  # two multimaps
        (left_interior_product, D5G2CO1, D5G2CO2),
        (interior_product, D5G2CO1, D5G2CO2),
        (right_interior_product, D3G2CONTRA1, D3G2CONTRA2),  # two multicommas
        (left_interior_product, D3G2CONTRA1, D3G2CONTRA2),
        (interior_product, D3G2CONTRA1, D3G2CONTRA2),
        (progressive_product, matrix_to_multivector(Temperament(((-8, 5, 0), (-4, 1, 1)), COL)),
         ET7_MC),  # et5Mc ^ et7Mc: grade 4 > 3
        (progressive_product, matrix_to_multivector(MEANTONE_M),
         matrix_to_multivector(Temperament(((1, 2, 3), (0, 3, 5)), ROW))),  # grade 4 > 3
    ],
)
def test_ea_product_errors(op, u1, u2):
    with pytest.raises(ValueError):
        op(u1, u2)


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
