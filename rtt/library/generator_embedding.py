from __future__ import annotations

from rtt.library.dual import dual
from rtt.library.matrix_utils import inverse, matrix_multiply, transpose
from rtt.library.temperament import Temperament, Variance


def get_tempering_projection(mapping: Temperament, held: Temperament):
    """The rational projection P that tempers just intonation onto the tuning
    holding ``held`` justly (``j·P = t``), idempotent with the commas in its
    kernel. ``P = G·M`` for the rational generator embedding ``G`` (a right
    inverse of the mapping whose image is spanned by the held intervals)."""
    return matrix_multiply(
        get_generator_embedding(mapping, held), _matrix_as(mapping, Variance.ROW)
    )


def get_generator_embedding(mapping: Temperament, held: Temperament):
    """The rational right inverse ``G = H·(M·H)⁻¹`` of the mapping ``M`` whose
    columns are the generators expressed (as fractional vectors) in the just
    domain — the embedding that holds the ``held`` intervals justly."""
    m = _matrix_as(mapping, Variance.ROW)
    h = transpose(_matrix_as(held, Variance.COL))  # d x r: held intervals as columns
    return matrix_multiply(h, inverse(matrix_multiply(m, h)))


def _matrix_as(t: Temperament, variance: Variance):
    """``t``'s matrix as rows of the given variance (dualizing if it is stored
    the other way)."""
    return t.matrix if t.variance is variance else dual(t).matrix
