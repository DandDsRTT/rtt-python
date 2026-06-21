from __future__ import annotations

from rtt.library.matrix_utils import matrix_multiply
from rtt.library.matrix_utils import transpose as _transpose_matrix
from rtt.library.temperament import Temperament, Variance


def multiply(temperaments: list[Temperament], variance: Variance):
    matrices = [
        _transpose_matrix(t.matrix) if t.variance is Variance.COL else t.matrix
        for t in temperaments
    ]
    product = matrices[0]
    for nxt in matrices[1:]:
        product = matrix_multiply(product, nxt)
    if len(product) == 1 and len(product[0]) == 1:
        return product[0][0]
    if variance is Variance.ROW or len(product) == 1:
        return Temperament(product, variance)
    return Temperament(_transpose_matrix(product), variance)


def is_cols(t: Temperament) -> bool:
    return t.variance is Variance.COL


def is_rows(t: Temperament) -> bool:
    return t.variance is Variance.ROW


def scale(t: Temperament, scalar) -> Temperament:
    matrix = tuple(tuple(scalar * x for x in row) for row in t.matrix)
    return Temperament(matrix, t.variance, t.domain_basis)


def add_t(t1: Temperament, t2: Temperament) -> Temperament:
    matrix = tuple(
        tuple(a + b for a, b in zip(r1, r2, strict=False))
        for r1, r2 in zip(t1.matrix, t2.matrix, strict=False)
    )
    return Temperament(matrix, t1.variance, t1.domain_basis)


def subtract_t(t1: Temperament, t2: Temperament) -> Temperament:
    matrix = tuple(
        tuple(a - b for a, b in zip(r1, r2, strict=False))
        for r1, r2 in zip(t1.matrix, t2.matrix, strict=False)
    )
    return Temperament(matrix, t1.variance, t1.domain_basis)


def reinterpret_as_dual_variance(t: Temperament) -> Temperament:
    flipped = Variance.COL if t.variance is Variance.ROW else Variance.ROW
    return Temperament(t.matrix, flipped, t.domain_basis)
