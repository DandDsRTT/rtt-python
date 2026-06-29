from __future__ import annotations

from fractions import Fraction

import sympy as sp

from rtt.library.dimensions import get_dimensionality
from rtt.library.list_utils import all_zeros_l
from rtt.library.math_utils import (
    get_primes,
    pad_vectors_with_zeros_up_to_d,
    pcv_to_quotient,
    quotient_to_pcv,
    super_,
)
from rtt.library.matrix_utils import hnf, remove_all_zero_lists, rotate_180
from rtt.library.parsing import parse_domain_basis
from rtt.library.temperament import Temperament, Variance


def canonical_domain_basis(unparsed_domain_basis: str) -> tuple:
    return canonical_domain_basis_private(parse_domain_basis(unparsed_domain_basis))


def is_standard_prime_limit_domain_basis(domain_basis: tuple) -> bool:
    return canonical_domain_basis_private(domain_basis) == get_primes(len(domain_basis))


def domain_basis_merge(*bases: tuple) -> tuple:
    concatenated = tuple(element for basis in bases for element in basis)
    return canonical_domain_basis_private(concatenated)


def domain_basis_intersection(*bases: tuple) -> tuple:
    intersected = bases[0]
    for basis in bases[1:]:
        intersected = _domain_basis_intersection_binary(intersected, basis)
    return canonical_domain_basis_private(intersected)


def _domain_basis_intersection_binary(basis1: tuple, basis2: tuple) -> tuple:
    dimension = max(get_domain_basis_dimension(basis1), get_domain_basis_dimension(basis2))
    a1 = pad_vectors_with_zeros_up_to_d(tuple(quotient_to_pcv(q) for q in basis1), dimension)
    a2 = pad_vectors_with_zeros_up_to_d(tuple(quotient_to_pcv(q) for q in basis2), dimension)
    block = hnf(tuple(row + row for row in a1) + tuple(row + (0,) * dimension for row in a2))
    intersected = [row[dimension:] for row in block if all(x == 0 for x in row[:dimension])]
    if not intersected:
        intersected = [(0,) * dimension]
    return canonical_domain_basis_private(tuple(pcv_to_quotient(row) for row in intersected))


def is_subspace_of(subspace: tuple, superspace: tuple) -> bool:
    return domain_basis_merge(subspace, superspace) == canonical_domain_basis_private(superspace)


def signs_match(a: int, b: int) -> bool:
    return _sign(a) == 0 or _sign(b) == 0 or _sign(a) == _sign(b)


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


def _factorization_acceptable(a: int, b: int) -> bool:
    return abs(a) >= abs(b) and signs_match(a, b)


def is_numerator_factor(subspace_entry: tuple, superspace_entry: tuple) -> bool:
    return all(
        _factorization_acceptable(s, s - sup)
        for s, sup in zip(subspace_entry, superspace_entry, strict=False)
    )


def is_denominator_factor(subspace_entry: tuple, superspace_entry: tuple) -> bool:
    return all(
        _factorization_acceptable(s, s + sup)
        for s, sup in zip(subspace_entry, superspace_entry, strict=False)
    )


def get_domain_basis_change_for_m(original_superspace: tuple, target_subspace: tuple) -> tuple:
    dimension = get_domain_basis_dimension(tuple(original_superspace) + tuple(target_subspace))
    target_a = pad_vectors_with_zeros_up_to_d(
        tuple(quotient_to_pcv(q) for q in target_subspace), dimension
    )
    superspace_a = pad_vectors_with_zeros_up_to_d(
        tuple(quotient_to_pcv(q) for q in original_superspace), dimension
    )
    change = []
    for target_entry in target_a:
        column = []
        remaining = list(target_entry)
        for superspace_entry in superspace_a:
            count = 0
            if not all_zeros_l(superspace_entry):
                while is_numerator_factor(remaining, superspace_entry):
                    count += 1
                    remaining = [r - s for r, s in zip(remaining, superspace_entry, strict=False)]
                while is_denominator_factor(remaining, superspace_entry):
                    count -= 1
                    remaining = [r + s for r, s in zip(remaining, superspace_entry, strict=False)]
            column.append(count)
        change.append(tuple(column))
    return tuple(change)


def get_domain_basis_change_for_c(original_subspace: tuple, target_superspace: tuple) -> tuple:
    return get_domain_basis_change_for_m(target_superspace, original_subspace)


def filter_target_intervals_for_nonstandard_domain_basis(
    quotients: tuple, domain_basis: tuple
) -> tuple:
    return tuple(quotient for quotient in quotients if is_subspace_of((quotient,), domain_basis))


def get_simplest_prime_only_basis(domain_basis: tuple) -> tuple[int, ...]:
    primes = set()
    for element in domain_basis:
        fraction = Fraction(element)
        for value in (fraction.numerator, fraction.denominator):
            primes.update(int(prime) for prime in sp.factorint(value) if prime != 1)
    return tuple(sorted(primes))


def express_quotients_in_domain_basis(quotients: tuple, domain_basis: tuple) -> tuple:
    dimension = get_domain_basis_dimension(domain_basis)
    basis_a = sp.Matrix(
        pad_vectors_with_zeros_up_to_d(tuple(quotient_to_pcv(b) for b in domain_basis), dimension)
    )
    gram = basis_a * basis_a.T
    vectors = []
    for quotient in quotients:
        prime_vector = sp.Matrix(
            pad_vectors_with_zeros_up_to_d((quotient_to_pcv(quotient),), dimension)[0]
        )
        solution = gram.solve(basis_a * prime_vector)
        vectors.append(tuple(int(value) for value in solution))
    return tuple(vectors)


def get_basis_a(t: Temperament) -> Temperament:
    domain_basis = get_domain_basis(t)
    matrix = pad_vectors_with_zeros_up_to_d(
        tuple(quotient_to_pcv(q) for q in domain_basis),
        get_domain_basis_dimension(domain_basis),
    )
    return Temperament(matrix, Variance.COL)


def canonical_domain_basis_private(domain_basis: tuple) -> tuple:
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
    return get_primes(get_dimensionality(t))


def get_domain_basis(t: Temperament) -> tuple:
    if t.domain_basis is not None:
        return t.domain_basis
    return get_standard_prime_limit_domain_basis(t)


def get_domain_basis_dimension(domain_basis: tuple) -> int:
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
