from __future__ import annotations

from math import log2

import numpy as np

from rtt.domain_basis import get_domain_basis
from rtt.dual import dual
from rtt.temperament import Temperament, Variance


def get_just_tuning_map(t: Temperament) -> tuple[float, ...]:
    """The just tuning map: the size in cents (1200·log2) of each basis element."""
    return tuple(1200.0 * log2(float(q)) for q in get_domain_basis(t))


def generator_tuning_map_from_t_and_tuning_map(
    t: Temperament, tuning_map: tuple
) -> tuple[float, ...]:
    """Recover the generator tuning map from a temperament and a tuning map,
    via a right-inverse of the mapping (the tuning map is generators · mapping)."""
    mapping = np.array(_mapping_matrix(t), dtype=float)
    generators = np.array(tuning_map, dtype=float) @ np.linalg.pinv(mapping)
    return tuple(float(x) for x in generators)


def _mapping_matrix(t: Temperament) -> tuple:
    return t.matrix if t.variance is Variance.ROW else dual(t).matrix
