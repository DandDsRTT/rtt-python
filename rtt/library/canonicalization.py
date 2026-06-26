from __future__ import annotations

import sympy as sp

from rtt.library.domain_basis import is_standard_prime_limit_domain_basis
from rtt.library.matrix_utils import (
    Matrix,
    all_zeros,
    hnf,
    hnf_with_transform,
    remove_unneeded_zero_lists,
    rotate_180,
    transpose,
)
from rtt.library.temperament import Temperament, Variance


def canonical_form(t: Temperament) -> Temperament:
    canonicalize = canonical_ca if t.variance is Variance.COL else canonical_ma
    domain_basis = t.domain_basis
    if domain_basis is not None and is_standard_prime_limit_domain_basis(domain_basis):
        domain_basis = None
    return Temperament(canonicalize(t.matrix), t.variance, domain_basis)


def canonical_ma(matrix: Matrix) -> Matrix:
    inner = matrix if all_zeros(matrix) else hnf(col_hermite_defactor(matrix))
    return remove_unneeded_zero_lists(inner)


def canonical_ca(matrix: Matrix) -> Matrix:
    return rotate_180(canonical_ma(rotate_180(matrix)))


def col_hermite_defactor(matrix: Matrix) -> Matrix:
    rank = sp.Matrix(matrix).rank()
    inverse = sp.Matrix(_hermite_right_unimodular(matrix)).inv().tolist()
    return tuple(tuple(int(x) for x in inverse[i]) for i in range(rank))


def _hermite_right_unimodular(matrix: Matrix) -> Matrix:
    transform, _ = hnf_with_transform(transpose(matrix))
    return transpose(transform)
