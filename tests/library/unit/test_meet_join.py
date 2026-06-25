"""Backfill of the Meet & Join page examples (tests.m 695-885): dual + merge
on named 7/11-limit temperaments. Mechanical; exercises dual/map_merge/
comma_merge on larger inputs."""

import pytest

from rtt.library.canonicalization import canonical_form
from rtt.library.dual import dual
from rtt.library.exterior_algebra import Multivector, matrix_to_multivector, progressive_product
from rtt.library.merging import comma_merge, map_merge
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL


def _identity(n):
    return tuple(tuple(int(i == j) for j in range(n)) for i in range(n))


MEANTONE_C7 = (-4, 4, -1, 0)
STARLING_C7 = (1, 2, -3, 1)
SEPTIMAL_C7 = (6, -2, 0, -1)
PORCUPINE_C7 = (1, -5, 3, 0)
MARVEL_C7 = (-5, 2, 2, -1)
GAMELISMA7 = (-10, 1, 0, 3)
SENSAMAGIC_C7 = (0, -5, 1, 2)
MEANTONE_C11 = (-4, 4, -1, 0, 0)
STARLING_C11 = (1, 2, -3, 1, 0)
KEENANISMA11 = (-7, -1, 1, 1, 1)
MARVEL_C11 = (-5, 2, 2, -1, 0)
SEPTIMAL_C11 = (6, -2, 0, -1, 0)
PTOLEMISMA11 = (2, -2, 2, 0, -1)
TELEPATHMA11 = (-1, -3, 1, 0, 1)
MOTHWELLSMA11 = (-1, 2, 0, -2, 1)
RASTMA11 = (-1, 5, 0, 0, -2)
SENSAMAGIC_C11 = (0, -5, 1, 2, 0)
WERCKISMA11 = (-3, 2, -1, 2, -1)
VALINORSMA11 = (4, 0, -2, -1, 1)

# (comma basis, canonical mapping) dual pairs
meantone_m11 = Temperament(((1, 0, -4, -13, -25), (0, 1, 4, 10, 18)), ROW)
meantone_c11 = Temperament((MEANTONE_C11, STARLING_C11, MOTHWELLSMA11), COL)
meanpop_m11 = Temperament(((1, 0, -4, -13, 24), (0, 1, 4, 10, -13)), ROW)
meanpop_c11 = Temperament((MEANTONE_C11, STARLING_C11, KEENANISMA11), COL)
marvel_m11 = Temperament(((1, 0, 0, -5, 12), (0, 1, 0, 2, -1), (0, 0, 1, 2, -3)), ROW)
marvel_c11 = Temperament((MARVEL_C11, KEENANISMA11), COL)
porcupine_m11 = Temperament(((1, 2, 3, 2, 4), (0, 3, 5, -6, 4)), ROW)
porcupine_c11 = Temperament((TELEPATHMA11, SEPTIMAL_C11, PTOLEMISMA11), COL)
et31_m11 = Temperament(((31, 49, 72, 87, 107),), ROW)
et31_c11 = Temperament(
    ((-49, 31, 0, 0, 0), (-45, 27, 1, 0, 0), (-36, 21, 0, 1, 0), (-24, 13, 0, 0, 1)), COL
)
meantone_m7 = Temperament(((1, 0, -4, -13), (0, 1, 4, 10)), ROW)
meantone_c7 = Temperament((MEANTONE_C7, STARLING_C7), COL)
porcupine_m7 = Temperament(((1, 2, 3, 2), (0, 3, 5, -6)), ROW)
porcupine_c7 = Temperament((SEPTIMAL_C7, PORCUPINE_C7), COL)
miracle_m11 = Temperament(((1, 1, 3, 3, 2), (0, 6, -7, -2, 15)), ROW)
miracle_c11 = Temperament((MARVEL_C11, RASTMA11, KEENANISMA11), COL)
magic_m11 = Temperament(((1, 0, 2, -1, 6), (0, 5, 1, 12, -8)), ROW)
magic_c11 = Temperament((MARVEL_C11, SENSAMAGIC_C11, PTOLEMISMA11), COL)
et41_m11 = Temperament(((41, 65, 95, 115, 142),), ROW)
et41_c11 = Temperament(
    ((-65, 41, 0, 0, 0), (-15, 8, 1, 0, 0), (-25, 14, 0, 1, 0), (-32, 18, 0, 0, 1)), COL
)
miracle_m7 = Temperament(((1, 1, 3, 3), (0, 6, -7, -2)), ROW)
miracle_c7 = Temperament((MARVEL_C7, GAMELISMA7), COL)
magic_m7 = Temperament(((1, 0, 2, -1), (0, 5, 1, 12)), ROW)
magic_c7 = Temperament((MARVEL_C7, SENSAMAGIC_C7), COL)
et41_m7 = Temperament(((41, 65, 95, 115),), ROW)
et41_c7 = Temperament(((-65, 41, 0, 0), (-15, 8, 1, 0), (-25, 14, 0, 1)), COL)
mothra_m11 = Temperament(((1, 1, 0, 3, 5), (0, 3, 12, -1, -8)), ROW)
mothra_c11 = Temperament((MEANTONE_C11, MOTHWELLSMA11, KEENANISMA11), COL)
mothra_m7 = Temperament(((1, 1, 0, 3), (0, 3, 12, -1)), ROW)
mothra_c7 = Temperament((MEANTONE_C7, GAMELISMA7), COL)
portent_m11 = Temperament(((1, 1, 0, 3, 5), (0, 3, 0, -1, 4), (0, 0, 1, 0, -1)), ROW)
portent_c11 = Temperament((KEENANISMA11, WERCKISMA11), COL)
gamelan_m7 = Temperament(((1, 1, 0, 3), (0, 3, 0, -1), (0, 0, 1, 0)), ROW)
gamelan_c7 = Temperament((GAMELISMA7,), COL)
marvel_m7 = Temperament(((1, 0, 0, -5), (0, 1, 0, 2), (0, 0, 1, 2)), ROW)
marvel_c7 = Temperament((MARVEL_C7,), COL)

DUAL_PAIRS = [
    (meantone_c11, meantone_m11),
    (meanpop_c11, meanpop_m11),
    (marvel_c11, marvel_m11),
    (porcupine_c11, porcupine_m11),
    (et31_c11, et31_m11),
    (meantone_c7, meantone_m7),
    (porcupine_c7, porcupine_m7),
    (miracle_c11, miracle_m11),
    (magic_c11, magic_m11),
    (et41_c11, et41_m11),
    (miracle_c7, miracle_m7),
    (magic_c7, magic_m7),
    (et41_c7, et41_m7),
    (mothra_c11, mothra_m11),
    (mothra_c7, mothra_m7),
    (portent_c11, portent_m11),
    (gamelan_c7, gamelan_m7),
    (marvel_c7, marvel_m7),
]


@pytest.mark.parametrize("comma_basis, mapping", DUAL_PAIRS)
def test_dual_of_meet_join_temperaments(comma_basis, mapping):
    assert dual(comma_basis) == mapping


MERGE_CASES = [
    (comma_merge, (meantone_c11, meanpop_c11), et31_c11),
    (
        map_merge,
        (meantone_m11, meanpop_m11),
        Temperament(((1, 0, -4, -13, 0), (0, 1, 4, 10, 0), (0, 0, 0, 0, 1)), ROW),
    ),
    (comma_merge, (meantone_c11, marvel_c11), et31_c11),
    (map_merge, (meantone_m11, marvel_m11), dual(Temperament((MARVEL_C11,), COL))),
    (comma_merge, (meantone_c11, porcupine_c11), Temperament(_identity(5), COL)),
    (map_merge, (meantone_m11, porcupine_m11), dual(Temperament((VALINORSMA11,), COL))),
    (comma_merge, (meantone_c7, porcupine_c7), Temperament(_identity(4), COL)),
    (map_merge, (meantone_m7, porcupine_m7), Temperament(_identity(4), ROW)),
    (comma_merge, (miracle_c11, magic_c11), et41_c11),
    (map_merge, (miracle_m11, magic_m11), marvel_m11),
    (comma_merge, (miracle_c7, magic_c7), et41_c7),
    (map_merge, (miracle_m7, magic_m7), marvel_m7),
    (comma_merge, (miracle_c11, mothra_c11), et31_c11),
    (map_merge, (miracle_m11, mothra_m11), portent_m11),
    (map_merge, (miracle_m7, mothra_m7), gamelan_m7),
    (comma_merge, (meantone_c11, magic_c11), Temperament(_identity(5), COL)),
    (map_merge, (meantone_m11, magic_m11), dual(Temperament((MARVEL_C11,), COL))),
]


@pytest.mark.parametrize("merge, factors, expected", MERGE_CASES)
def test_meet_join_merges(merge, factors, expected):
    assert merge(*factors) == expected


# The same examples as multivectors (the EA progressive product = join/meet via duals).
_mm = matrix_to_multivector
EA_PRODUCT_CASES = [
    (_mm(meantone_m11), _mm(meanpop_m11), Multivector((0, 0, 0, 0, 0), 4, ROW)),
    (_mm(meantone_c11), _mm(marvel_c11), Multivector((0,), 5, COL)),
    (_mm(meantone_m11), _mm(marvel_m11), Multivector((0,), 5, ROW)),
    (
        _mm(meantone_m11),
        _mm(porcupine_m11),
        _mm(dual(Temperament((VALINORSMA11,), COL))),
    ),
    (_mm(meantone_c7), _mm(porcupine_c7), _mm(Temperament(_identity(4), COL))),
    (_mm(meantone_m7), _mm(porcupine_m7), _mm(Temperament(_identity(4), ROW))),
    (_mm(miracle_m11), _mm(magic_m11), Multivector((0, 0, 0, 0, 0), 4, ROW)),
    (_mm(miracle_c7), _mm(magic_c7), Multivector((0,), 4, COL)),
    (_mm(miracle_m7), _mm(magic_m7), Multivector((0,), 4, ROW)),
    (_mm(miracle_m11), _mm(mothra_m11), Multivector((0, 0, 0, 0, 0), 4, ROW)),
    (_mm(miracle_m7), _mm(mothra_m7), Multivector((0,), 4, ROW)),
    (_mm(meantone_m11), _mm(magic_m11), _mm(dual(Temperament((MARVEL_C11,), COL)))),
]


@pytest.mark.parametrize("u1, u2, expected", EA_PRODUCT_CASES)
def test_ea_meet_join_products(u1, u2, expected):
    assert progressive_product(u1, u2) == expected


EA_PRODUCT_ERRORS = [
    (_mm(meantone_c11), _mm(meanpop_c11)),
    (_mm(meantone_c11), _mm(porcupine_c11)),
    (_mm(miracle_c11), _mm(magic_c11)),
    (_mm(miracle_c11), _mm(mothra_c11)),
    (_mm(meantone_c11), _mm(magic_c11)),
]


@pytest.mark.parametrize("u1, u2", EA_PRODUCT_ERRORS)
def test_ea_meet_join_product_errors(u1, u2):
    with pytest.raises(ValueError):
        progressive_product(u1, u2)


def test_dual_with_nonstandard_basis():
    m = Temperament(((1, 1, 3), (0, 3, -1)), ROW, (2, 3, 7))
    c = Temperament(((-10, 1, 3),), COL, (2, 3, 7))
    assert dual(m) == canonical_form(c)
    assert dual(c) == canonical_form(m)
