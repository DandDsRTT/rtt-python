from __future__ import annotations

import sympy as sp

from rtt.matrix_utils import (
    Matrix,
    all_zeros,
    hnf,
    hnf_with_transform,
    remove_unneeded_zero_lists,
    rotate_180,
    transpose,
)
from rtt.temperament import Temperament, Variance


def canonical_form(t: Temperament) -> Temperament:
    """Canonical form of a temperament, by its mapping or comma-basis variance."""
    canonicalize = canonical_ca if t.variance is Variance.COL else canonical_ma
    return Temperament(canonicalize(t.matrix), t.variance, t.domain_basis)


def canonical_ma(matrix: Matrix) -> Matrix:
    """Canonical form of a mapping: defactored, then Hermite Normal Form."""
    inner = matrix if all_zeros(matrix) else hnf(col_hermite_defactor(matrix))
    return remove_unneeded_zero_lists(inner)


def canonical_ca(matrix: Matrix) -> Matrix:
    """Canonical form of a comma basis: canonical_ma between two 180° rotations."""
    return rotate_180(canonical_ma(rotate_180(matrix)))


def col_hermite_defactor(matrix: Matrix) -> Matrix:
    """A saturated (defactored) basis spanning the same rational row space."""
    rank = sp.Matrix(matrix).rank()
    inverse = sp.Matrix(hermite_right_unimodular(matrix)).inv().tolist()
    return tuple(tuple(int(x) for x in inverse[i]) for i in range(rank))


def hermite_right_unimodular(matrix: Matrix) -> Matrix:
    transform, _ = hnf_with_transform(transpose(matrix))
    return transpose(transform)
