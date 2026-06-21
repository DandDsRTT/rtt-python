from __future__ import annotations

import sympy as sp

from rtt.library.temperament import Temperament, Variance


def get_d(t: Temperament) -> int:
    return len(t.matrix[0]) if t.matrix else 0


def get_r(t: Temperament) -> int:
    rank = sp.Matrix(t.matrix).rank()
    return rank if t.variance is Variance.ROW else get_d(t) - rank


def get_n(t: Temperament) -> int:
    return get_d(t) - get_r(t)
