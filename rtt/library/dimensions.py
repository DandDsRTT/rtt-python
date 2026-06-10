from __future__ import annotations

import sympy as sp

from rtt.library.temperament import Temperament, Variance


def get_d(t: Temperament) -> int:
    """Dimensionality: the number of columns (primes in the domain basis)."""
    return len(t.matrix[0]) if t.matrix else 0


def get_r(t: Temperament) -> int:
    """Rank: independent generators (mapping rows) the temperament tempers to."""
    rank = sp.Matrix(t.matrix).rank()
    return rank if t.variance is Variance.ROW else get_d(t) - rank


def get_n(t: Temperament) -> int:
    """Nullity: independent commas (comma-basis rows) the temperament tempers out."""
    return get_d(t) - get_r(t)
