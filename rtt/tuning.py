from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import log2

import numpy as np
from scipy.optimize import linprog

from rtt.dimensions import get_d
from rtt.domain_basis import get_domain_basis
from rtt.dual import dual
from rtt.parsing import parse_quotient_list
from rtt.temperament import Temperament, Variance


@dataclass(frozen=True)
class TuningSchemeSpec:
    """A tuning scheme's traits: how the optimum generator tuning is chosen.

    ``target_intervals`` is a quotient-list string (the intervals whose mistuning
    is minimized); the complexity traits describe the norm used to weight damage.
    """

    optimization_power: float  # trait 2: inf = minimax, 2 = miniRMS, 1 = miniaverage
    target_intervals: str | None = None  # trait 1
    damage_weight_slope: str = "unityWeight"  # trait 3
    complexity_norm_power: float = 1  # trait 4
    complexity_log_prime_power: float = 1  # trait 5a
    complexity_prime_power: float = 0  # trait 5b
    complexity_size_factor: float = 0  # trait 5c
    nonprime_basis_approach: str = ""  # trait 7


def optimize_generator_tuning_map(
    t: Temperament, spec: TuningSchemeSpec
) -> tuple[float, ...]:
    """The generator tuning map minimizing target-interval damage under the scheme."""
    mapping = np.array(_mapping_matrix(t), dtype=float)  # r x d
    just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)  # d
    monzos = parse_quotient_list(spec.target_intervals, get_d(t))  # k monzos
    targets = np.array(monzos, dtype=float)  # k x d
    weights = _damage_weights(monzos, t, spec)  # k

    tempered = (targets @ mapping.T) * weights[:, None]  # k x r
    just = (targets @ just_tuning_map) * weights  # k
    rank = mapping.shape[0]
    generators = _solve_optimum(tempered, just, spec.optimization_power, rank)
    return tuple(float(g) for g in generators)


def _damage_weights(
    monzos: tuple[tuple[int, ...], ...], t: Temperament, spec: TuningSchemeSpec
) -> np.ndarray:
    """The per-target damage weights: 1 (unity), complexity, or 1/complexity."""
    if spec.damage_weight_slope == "unityWeight":
        return np.ones(len(monzos))
    complexities = np.array(
        [
            get_complexity(
                monzo,
                t,
                spec.complexity_norm_power,
                spec.complexity_log_prime_power,
                spec.complexity_prime_power,
                spec.complexity_size_factor,
                spec.nonprime_basis_approach,
            )
            for monzo in monzos
        ]
    )
    if spec.damage_weight_slope == "complexityWeight":
        return complexities
    if spec.damage_weight_slope == "simplicityWeight":
        return 1.0 / complexities
    raise ValueError(f"unknown damage weight slope: {spec.damage_weight_slope!r}")


def _solve_optimum(
    tempered: np.ndarray, just: np.ndarray, power: float, rank: int
) -> np.ndarray:
    """Solve for the generators minimizing the ``power``-norm of (tempered·g − just)."""
    if power == 2:
        generators, *_ = np.linalg.lstsq(tempered, just, rcond=None)
        return generators
    if power == float("inf"):
        return _minimax(tempered, just, rank)
    if power == 1:
        return _minisum(tempered, just, rank)
    raise NotImplementedError(f"optimization power {power} not yet ported")


def _minimax(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    """Minimize the largest absolute damage via a linear program (one slack δ)."""
    k = len(just)
    cost = np.concatenate([np.zeros(rank), [1.0]])  # minimize δ
    slack = -np.ones((k, 1))
    a_ub = np.vstack([np.hstack([tempered, slack]), np.hstack([-tempered, slack])])
    b_ub = np.concatenate([just, -just])
    bounds = [(None, None)] * rank + [(0, None)]
    result = linprog(cost, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
    return result.x[:rank]


def _minisum(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    """Minimize the sum of absolute damages via a linear program (a slack per target)."""
    k = len(just)
    cost = np.concatenate([np.zeros(rank), np.ones(k)])  # minimize Σ slack
    identity = np.eye(k)
    a_ub = np.vstack(
        [np.hstack([tempered, -identity]), np.hstack([-tempered, -identity])]
    )
    b_ub = np.concatenate([just, -just])
    bounds = [(None, None)] * rank + [(0, None)] * k
    result = linprog(cost, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
    return result.x[:rank]


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
