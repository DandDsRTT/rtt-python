from __future__ import annotations

import sympy as sp

from rtt.library.temperament import Temperament, Variance


def get_dimensionality(t: Temperament) -> int:
    return len(t.matrix[0]) if t.matrix else 0


def get_rank(t: Temperament) -> int:
    rank = sp.Matrix(t.matrix).rank()
    return rank if t.variance is Variance.ROW else get_dimensionality(t) - rank


def get_nullity(t: Temperament) -> int:
    return get_dimensionality(t) - get_rank(t)
