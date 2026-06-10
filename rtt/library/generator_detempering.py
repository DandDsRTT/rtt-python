from __future__ import annotations

from rtt.library.dual import dual
from rtt.library.matrix_utils import (
    matrix_multiply,
    smith_normal_form_with_transforms,
    transpose,
)
from rtt.library.temperament import Temperament, Variance


def get_generator_detempering(t: Temperament) -> Temperament:
    """For each generator, one JI interval that tempers to it (a right-inverse
    of the mapping, via the Smith decomposition)."""
    mapping = t if t.variance is Variance.ROW else dual(t)
    left, snf, right = smith_normal_form_with_transforms(mapping.matrix)
    detempering = matrix_multiply(matrix_multiply(right, transpose(snf)), left)
    return Temperament(transpose(detempering), Variance.COL)
