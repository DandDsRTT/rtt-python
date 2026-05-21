from __future__ import annotations

from fractions import Fraction

import sympy as sp

from rtt.dimensions import get_d
from rtt.math_utils import get_primes
from rtt.temperament import Temperament


def get_standard_prime_limit_domain_basis(t: Temperament) -> tuple[int, ...]:
    """The standard prime-limit basis for a temperament: its first d primes."""
    return get_primes(get_d(t))


def get_domain_basis(t: Temperament) -> tuple:
    """A temperament's domain basis, defaulting to the standard prime limit."""
    if t.domain_basis is not None:
        return t.domain_basis
    return get_standard_prime_limit_domain_basis(t)


def get_domain_basis_dimension(domain_basis: tuple) -> int:
    """The prime-count index of the largest prime appearing in the basis."""
    largest_prime = 1
    for element in domain_basis:
        fraction = Fraction(element)
        for value in (fraction.numerator, fraction.denominator):
            for prime in sp.factorint(value):
                if prime != 1:
                    largest_prime = max(largest_prime, int(prime))
    return max(1, int(sp.primepi(largest_prime)))
