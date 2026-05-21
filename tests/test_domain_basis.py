import pytest

from rtt.domain_basis import (
    get_domain_basis,
    get_domain_basis_dimension,
    get_standard_prime_limit_domain_basis,
)
from rtt.temperament import Temperament, Variance

ROW = Variance.ROW


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
