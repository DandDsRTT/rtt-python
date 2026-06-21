from __future__ import annotations

from rtt.library.canonicalization import canonical_form
from rtt.library.domain_basis import (
    get_domain_basis,
    get_domain_basis_change_for_c,
    get_domain_basis_change_for_m,
    is_subspace_of,
)
from rtt.library.matrix_utils import matrix_multiply, transpose
from rtt.library.temperament import Temperament, Variance


def change_domain_basis(t: Temperament, target_domain_basis: tuple) -> Temperament:
    if t.variance is Variance.COL:
        return change_domain_basis_for_c(t, target_domain_basis)
    return change_domain_basis_for_m(t, target_domain_basis)


def change_domain_basis_for_m(m: Temperament, target_subspace: tuple) -> Temperament:
    target = tuple(target_subspace)
    if get_domain_basis(m) == target:
        return m
    if is_subspace_of(get_domain_basis(m), target):
        raise ValueError("target domain basis must be a sub-basis of the mapping's")
    change = get_domain_basis_change_for_m(get_domain_basis(m), target)
    matrix = matrix_multiply(m.matrix, transpose(change))
    return canonical_form(Temperament(matrix, Variance.ROW, target))


def change_domain_basis_for_c(c: Temperament, target_superspace: tuple) -> Temperament:
    target = tuple(target_superspace)
    if get_domain_basis(c) == target:
        return c
    if not is_subspace_of(get_domain_basis(c), target):
        raise ValueError("target domain basis must be a super-basis of the comma basis's")
    change = get_domain_basis_change_for_c(get_domain_basis(c), target)
    matrix = transpose(matrix_multiply(transpose(change), transpose(c.matrix)))
    return canonical_form(Temperament(matrix, Variance.COL, target))
