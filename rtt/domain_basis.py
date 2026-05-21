from __future__ import annotations

from fractions import Fraction

import sympy as sp

from rtt.dimensions import get_d
from rtt.math_utils import (
    get_primes,
    pad_vectors_with_zeros_up_to_d,
    pcv_to_quotient,
    quotient_to_pcv,
    super_,
)
from rtt.matrix_utils import hnf, remove_all_zero_lists, rotate_180
from rtt.parsing import parse_domain_basis
from rtt.temperament import Temperament, Variance


def canonical_domain_basis(unparsed_domain_basis: str) -> tuple:
    """Canonicalize a dot-separated domain basis string (e.g. ``2.7.9``)."""
    return canonical_domain_basis_private(parse_domain_basis(unparsed_domain_basis))


def is_standard_prime_limit_domain_basis(domain_basis: tuple) -> bool:
    """Whether the basis is (a reordering of) the first n primes."""
    return canonical_domain_basis_private(domain_basis) == get_primes(len(domain_basis))


def domain_basis_merge(*bases: tuple) -> tuple:
    """The join (smallest containing subgroup) of the given domain bases."""
    concatenated = tuple(element for basis in bases for element in basis)
    return canonical_domain_basis_private(concatenated)


def domain_basis_intersection(*bases: tuple) -> tuple:
    """The meet (largest common subgroup) of the given domain bases."""
    intersected = bases[0]
    for basis in bases[1:]:
        intersected = _domain_basis_intersection_binary(intersected, basis)
    return canonical_domain_basis_private(intersected)


def _domain_basis_intersection_binary(basis1: tuple, basis2: tuple) -> tuple:
    # Zassenhaus: stack [A1|A1; A2|0], take HNF; rows with a zero left half have
    # a right half spanning the intersection lattice.
    dimension = max(get_domain_basis_dimension(basis1), get_domain_basis_dimension(basis2))
    a1 = pad_vectors_with_zeros_up_to_d(tuple(quotient_to_pcv(q) for q in basis1), dimension)
    a2 = pad_vectors_with_zeros_up_to_d(tuple(quotient_to_pcv(q) for q in basis2), dimension)
    block = hnf(
        tuple(row + row for row in a1) + tuple(row + (0,) * dimension for row in a2)
    )
    intersected = [
        row[dimension:] for row in block if all(x == 0 for x in row[:dimension])
    ]
    if not intersected:
        intersected = [(0,) * dimension]
    return canonical_domain_basis_private(tuple(pcv_to_quotient(row) for row in intersected))


def is_subspace_of(subspace: tuple, superspace: tuple) -> bool:
    """Whether ``subspace`` is a subgroup of ``superspace``."""
    return domain_basis_merge(subspace, superspace) == tuple(superspace)


def get_basis_a(t: Temperament) -> Temperament:
    """A temperament's domain basis as a comma-basis matrix of monzos."""
    domain_basis = get_domain_basis(t)
    matrix = pad_vectors_with_zeros_up_to_d(
        tuple(quotient_to_pcv(q) for q in domain_basis),
        get_domain_basis_dimension(domain_basis),
    )
    return Temperament(matrix, Variance.COL)


def canonical_domain_basis_private(domain_basis: tuple) -> tuple:
    """Canonicalize a domain basis: order by prime limit, drop redundancies.

    Treats each generator as a monzo, canonicalizes the lattice (the rotate-180/
    HNF sandwich), then reads the rows back as "super" quotients (>= 1).
    """
    dimension = get_domain_basis_dimension(domain_basis)
    basis_change = pad_vectors_with_zeros_up_to_d(
        tuple(quotient_to_pcv(q) for q in domain_basis), dimension
    )
    canonical = rotate_180(remove_all_zero_lists(hnf(rotate_180(basis_change))))
    if len(canonical) == 0:
        return (1,)
    return tuple(_supered_quotient(pcv_to_quotient(row)) for row in canonical)


def _supered_quotient(quotient: Fraction):
    result = super_(quotient)
    return int(result) if result.denominator == 1 else result


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
            if value == 0:
                continue
            for prime in sp.factorint(value):
                if prime != 1:
                    largest_prime = max(largest_prime, int(prime))
    return max(1, int(sp.primepi(largest_prime)))
