from __future__ import annotations

from functools import reduce
from math import lcm

import sympy as sp

from rtt.canonicalization import Matrix, canonical_ca, canonical_ma
from rtt.temperament import Temperament, Variance


def dual(t: Temperament) -> Temperament:
    """The dual temperament: a mapping's comma basis, or vice versa."""
    null_space = _integer_null_space(t.matrix)
    if null_space:
        canonicalize = canonical_ma if t.variance is Variance.COL else canonical_ca
        matrix = canonicalize(null_space)
    else:
        matrix = ((0,) * len(t.matrix[0]),)
    flipped = Variance.ROW if t.variance is Variance.COL else Variance.COL
    return Temperament(matrix, flipped, t.domain_basis)


def mapping_matrix(t: Temperament) -> Matrix:
    """The temperament's mapping as a row matrix (the maps as rows): its stored matrix
    when row-variance, else the dual's. Callers wanting a float array ``np.array`` it."""
    return t.matrix if t.variance is Variance.ROW else dual(t).matrix


def _integer_null_space(matrix: Matrix) -> Matrix:
    """Null-space basis as integer row vectors (denominators cleared)."""
    result = []
    for vector in sp.Matrix(matrix).nullspace():
        multiplier = reduce(lcm, (int(entry.q) for entry in vector), 1)
        result.append(tuple(int(entry * multiplier) for entry in vector))
    return tuple(result)
