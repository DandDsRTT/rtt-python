from fractions import Fraction as F

import pytest

from rtt.library.domain_basis import (
    canonical_domain_basis,
    canonical_domain_basis_private,
    domain_basis_intersection,
    domain_basis_merge,
    get_basis_a,
    get_domain_basis,
    get_domain_basis_change_for_c,
    get_domain_basis_change_for_m,
    get_domain_basis_dimension,
    get_simplest_prime_only_basis,
    get_standard_prime_limit_domain_basis,
    is_denominator_factor,
    is_numerator_factor,
    is_standard_prime_limit_domain_basis,
    is_subspace_of,
    signs_match,
)
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL

DOMAIN_BASIS_MERGE = [
    (((2, 3, 5), (2, 9, 5)), (2, 3, 5)),
    (((2, 3, 5), (2, 9, 7)), (2, 3, 5, 7)),
    (((2, 3, 5), (2, 9, 7), (2, F(5, 7), 11)), (2, 3, 5, 7, 11)),
    (((4,), (16,)), (4,)),
    (((F(25, 9),), (F(5, 3),)), (F(5, 3),)),
    (((1,), (1,)), (1,)),
    (((2, 3, 5), (2, 3, 5)), (2, 3, 5)),
]

DOMAIN_BASIS_INTERSECTION = [
    (((2, 3, 5), (2, 9, 5)), (2, 9, 5)),
    (((2, F(5, 3), F(9, 7)), (2, 9, 5)), (2, F(25, 9))),
    (((2, F(5, 3)), (2, 9, 5)), (2, F(25, 9))),
    (((2, F(25, 9)), (2, 9, 5)), (2, F(25, 9))),
    (((2, 3, 5, 7), (2, 3, 5), (2, 5, 7)), (2, 5)),
    (((2, 3), (10, 15)), (F(3, 2),)),
    (((2, F(5, 3)), (2, 3, 5)), (2, F(5, 3))),
    (((2, F(9, 5)), (2, 9, 5)), (2, F(9, 5))),
    (((2, 3, 5), (2, 3, 5)), (2, 3, 5)),
    (((2, 9, F(7, 5)), (2, 3, F(7, 5))), (2, 9, F(7, 5))),
    (((4,), (8,)), (64,)),
    (((9,), (27,)), (729,)),
    (((2,), (3,)), (1,)),
    (((5,), (15,)), (1,)),
    (((4,), (18,)), (1,)),
    (((2,), (2,)), (2,)),
    (((4,), (4,)), (4,)),
    (((6,), (6,)), (6,)),
    (((12,), (12,)), (12,)),
    (((16, 18, 15), (4, 18, 5)), (16, 18, 2500)),
    (((4, 18), (8, 18)), (64, 18)),
    (((16, 18), (16, 18)), (16, 18)),
    (((4, 18, 5), (8, 18, 7)), (64, 18)),
]

IS_SUBSPACE_OF = [
    ((2, 9, 5), (2, 3, 5), True),
    ((2, 3, 5), (2, 3, 5, 7), True),
    ((2, 3, 5), (2, 9, 5), False),
    ((2, 3, 5, 7), (2, 3, 5), False),
    ((4,), (2,), True),
    ((8,), (4,), False),
    ((16,), (4,), True),
    ((3, 5, 7), (2, 11, 13), False),
    ((2, 3, 5), (2, 3, 7), False),
    ((2, 3, 7), (2, 3, 5), False),
    ((2, F(5, 3), 7), (2, 3, 5, 7), True),
    ((2, F(5, 3), F(7, 5)), (2, 3, 5, 7), True),
    ((2, F(7, 5)), (2, 5, 7), True),
    ((2, 5, 7), (2, F(7, 5)), False),
    ((2, 105, 11), (2, 15, 7, 11), True),
    ((2, F(25, 9), F(11, 7)), (2, F(5, 3), 7, 11), True),
    ((2, F(3, 2), F(5, 2), F(5, 3)), (2, 3, 5), True),
    ((2, F(9, 5), 3), (2, 3, 5), True),
]

CANONICAL_DOMAIN_BASIS = [
    ((2, 7, 9), (2, 9, 7)),  # order by prime limit
    ((2, F(9, 7), 5), (2, 5, F(9, 7))),
    ((2, F(9, 7), F(5, 3)), (2, F(5, 3), F(9, 7))),
    ((2, 3, 9), (2, 3)),  # consolidate redundancies
    ((2, 3, 15), (2, 3, 5)),
    ((2, 3, F(5, 3)), (2, 3, 5)),
    ((2, F(5, 3), F(7, 5)), (2, F(5, 3), F(7, 3))),  # tricky
    ((1, 1), (1,)),
    ((2, 3, 7), (2, 3, 7)),  # already-canonical subgroups
    ((2, 5, 7), (2, 5, 7)),
    ((2, 3, F(7, 5)), (2, 3, F(7, 5))),
    ((2, F(5, 3), 7), (2, F(5, 3), 7)),
    ((2, 5, F(7, 3)), (2, 5, F(7, 3))),
    ((2, F(5, 3), F(7, 3)), (2, F(5, 3), F(7, 3))),
    ((2, F(27, 25), F(7, 3)), (2, F(27, 25), F(7, 3))),
    ((2, F(9, 5), F(9, 7)), (2, F(9, 5), F(9, 7))),
    ((2, 3, 11), (2, 3, 11)),
    ((2, 5, 11), (2, 5, 11)),
    ((2, 7, 11), (2, 7, 11)),
    ((2, 3, 5, 11), (2, 3, 5, 11)),
    ((2, 3, 7, 11), (2, 3, 7, 11)),
    ((2, 5, 7, 11), (2, 5, 7, 11)),
    ((2, F(5, 3), F(7, 3), F(11, 3)), (2, F(5, 3), F(7, 3), F(11, 3))),
    ((2, 3, 13), (2, 3, 13)),
    ((2, 3, 5, 13), (2, 3, 5, 13)),
    ((2, 3, 7, 13), (2, 3, 7, 13)),
    ((2, 5, 7, 13), (2, 5, 7, 13)),
    ((2, 5, 7, 11, 13), (2, 5, 7, 11, 13)),
    ((2, 3, F(13, 5)), (2, 3, F(13, 5))),
    ((2, 3, F(11, 5), F(13, 5)), (2, 3, F(11, 5), F(13, 5))),
    ((2, 3, F(11, 7), F(13, 7)), (2, 3, F(11, 7), F(13, 7))),
    ((2, F(7, 5), F(11, 5), F(13, 5)), (2, F(7, 5), F(11, 5), F(13, 5))),
    ((1,), (1,)),
    ((0,), (1,)),
]


def test_get_standard_prime_limit_domain_basis():
    t = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
    assert get_standard_prime_limit_domain_basis(t) == (2, 3, 5)


def test_get_domain_basis_standard():
    t = Temperament(((1, 0, -4), (0, 1, 4)), ROW)
    assert get_domain_basis(t) == (2, 3, 5)


def test_get_domain_basis_custom():
    t = Temperament(((11, 35, 31),), ROW, (2, 9, 7))
    assert get_domain_basis(t) == (2, 9, 7)


@pytest.mark.parametrize("domain_basis, expected", [((2, 9, 7), 4), ((1,), 1)])
def test_get_domain_basis_dimension(domain_basis, expected):
    assert get_domain_basis_dimension(domain_basis) == expected


@pytest.mark.parametrize("domain_basis, expected", CANONICAL_DOMAIN_BASIS)
def test_canonical_domain_basis_private(domain_basis, expected):
    assert canonical_domain_basis_private(domain_basis) == expected


def test_canonical_domain_basis():
    assert canonical_domain_basis("2.7.9") == (2, 9, 7)


@pytest.mark.parametrize(
    "domain_basis, expected",
    [((2, 3, 5, 7, 11), True), ((2, 3, 7, 5, 11), True), ((2, 3, 5, 9, 11), False)],
)
def test_is_standard_prime_limit_domain_basis(domain_basis, expected):
    assert is_standard_prime_limit_domain_basis(domain_basis) is expected


@pytest.mark.parametrize("bases, expected", DOMAIN_BASIS_MERGE)
def test_domain_basis_merge(bases, expected):
    assert domain_basis_merge(*bases) == expected


@pytest.mark.parametrize("bases, expected", DOMAIN_BASIS_INTERSECTION)
def test_domain_basis_intersection(bases, expected):
    assert domain_basis_intersection(*bases) == expected


@pytest.mark.parametrize("subspace, superspace, expected", IS_SUBSPACE_OF)
def test_is_subspace_of(subspace, superspace, expected):
    assert is_subspace_of(subspace, superspace) is expected


def test_get_basis_a():
    t = Temperament(((11, 35, 31),), ROW, (2, 9, 7))
    assert get_basis_a(t) == Temperament(
        ((1, 0, 0, 0), (0, 2, 0, 0), (0, 0, 0, 1)), COL
    )


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (3, 5, True),
        (-3, -5, True),
        (-3, 5, False),
        (3, -5, False),
        (3, 0, True),
        (0, 5, True),
        (-3, 0, True),
        (0, -5, True),
    ],
)
def test_signs_match(a, b, expected):
    assert signs_match(a, b) is expected


@pytest.mark.parametrize(
    "subspace, superspace, expected",
    [
        ((1, 0, 0), (1, 0, 0), True),
        ((2, 0, 0), (1, 0, 0), True),
        ((1, 1, 0), (1, 0, 0), True),
        ((1, 1, 0), (1, 1, 0), True),
        ((2, 1, 0), (1, 1, 0), True),
        ((1, 1, 0), (1, 2, 0), False),
        ((1, 0, 0), (0, 0, 1), False),
    ],
)
def test_is_numerator_factor(subspace, superspace, expected):
    assert is_numerator_factor(subspace, superspace) is expected


@pytest.mark.parametrize(
    "subspace, superspace, expected",
    [
        ((1, 0, 0), (1, 0, 0), False),
        ((1, -1, 0), (1, 0, 0), False),
        ((1, -1, 0), (0, 1, 0), True),
    ],
)
def test_is_denominator_factor(subspace, superspace, expected):
    assert is_denominator_factor(subspace, superspace) is expected


@pytest.mark.parametrize(
    "original, target, expected",
    [
        ((2, 3, 5, 7), (2, 3, 5), ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0))),
        ((2, 3, 7), (2, 9, 7), ((1, 0, 0), (0, 2, 0), (0, 0, 1))),
        ((2, 3, 5, 7), (2, F(9, 7), F(5, 3)), ((1, 0, 0, 0), (0, 2, 0, -1), (0, -1, 1, 0))),
    ],
)
def test_get_domain_basis_change_for_m(original, target, expected):
    assert get_domain_basis_change_for_m(original, target) == expected


@pytest.mark.parametrize(
    "original, target, expected",
    [
        ((2, 3, 5), (2, 3, 5, 7), ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0))),
        ((2, 9, 7), (2, 3, 7), ((1, 0, 0), (0, 2, 0), (0, 0, 1))),
        ((2, F(9, 7), F(5, 3)), (2, 3, 5, 7), ((1, 0, 0, 0), (0, 2, 0, -1), (0, -1, 1, 0))),
    ],
)
def test_get_domain_basis_change_for_c(original, target, expected):
    assert get_domain_basis_change_for_c(original, target) == expected


@pytest.mark.parametrize(
    "original, target, expected",
    [
        (("2", "1", "5"), ("2", "3", "5"), ((1, 0, 0), (0, 0, 0), (0, 0, 1))),
        (("2", "3", "5"), ("2", "1", "5"), ((1, 0, 0), (0, 0, 0), (0, 0, 1))),
    ],
)
def test_get_domain_basis_change_terminates_with_unison_basis_element(
    original, target, expected
):
    assert get_domain_basis_change_for_m(original, target) == expected
    assert get_domain_basis_change_for_c(original, target) == expected


@pytest.mark.parametrize(
    "domain_basis, expected",
    [
        ((2, F(5, 3), F(9, 7)), (2, 3, 5, 7)),  # tests.m 4102
        ((2, 3, 5), (2, 3, 5)),
        ((4, 3, 5), (2, 3, 5)),
        ((2, F(13, 5)), (2, 5, 13)),
    ],
)
def test_get_simplest_prime_only_basis(domain_basis, expected):
    assert get_simplest_prime_only_basis(domain_basis) == expected
