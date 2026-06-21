from __future__ import annotations

from rtt.library.dual import dual
from rtt.library.matrix_utils import inverse, matrix_multiply, transpose
from rtt.library.temperament import Temperament, Variance


def get_tempering_projection(mapping: Temperament, held: Temperament):
    return matrix_multiply(
        get_generator_embedding(mapping, held), _matrix_as(mapping, Variance.ROW)
    )


def get_generator_embedding(mapping: Temperament, held: Temperament):
    m = _matrix_as(mapping, Variance.ROW)
    h = transpose(_matrix_as(held, Variance.COL))
    return matrix_multiply(h, inverse(matrix_multiply(m, h)))


def _matrix_as(t: Temperament, variance: Variance):
    return t.matrix if t.variance is variance else dual(t).matrix
