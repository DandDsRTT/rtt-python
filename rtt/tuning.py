from __future__ import annotations

from fractions import Fraction
from math import log2

import numpy as np

from rtt.domain_basis import get_domain_basis
from rtt.dual import dual
from rtt.temperament import Temperament, Variance


def get_complexity(
    pcv: tuple,
    t: Temperament,
    norm_power,  # trait 4
    log_prime_power,  # trait 5a
    prime_power,  # trait 5b
    size_factor,  # trait 5c
    nonprime_basis_approach: str,  # trait 7
) -> float:
    """An interval's complexity: a (pre-transformed) norm of its monzo."""
    if size_factor != 0:
        raise NotImplementedError("size-factor (Weil/lils) complexity not yet ported")
    diagonal = []
    for q in get_domain_basis(t):
        fraction = Fraction(q)
        base = (
            float(q)
            if nonprime_basis_approach == "nonprime-based"
            else float(fraction.numerator * fraction.denominator)
        )
        weight = 1.0
        if log_prime_power > 0:
            weight *= log2(base) ** log_prime_power
        if prime_power > 0:
            weight *= base**prime_power
        diagonal.append(weight)
    transformed = [w * x for w, x in zip(diagonal, pcv)]
    ord_ = np.inf if norm_power == float("inf") else norm_power
    return float(np.linalg.norm(transformed, ord_)) / (1 + size_factor)


def get_dual_power(power):
    """The Hölder-conjugate (dual) norm power: 1 <-> inf, 2 <-> 2."""
    if power == 1:
        return float("inf")
    return 1 / (1 - 1 / power)


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
