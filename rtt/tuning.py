from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from math import inf, log2

import numpy as np
from scipy.optimize import linprog, minimize

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


_SLOPE_BY_LETTER = {
    "U": "unityWeight",
    "S": "simplicityWeight",
    "C": "complexityWeight",
}


def _complexity_traits_from_name(name: str) -> dict:
    """The complexity traits (4, 5a, 5b) a scheme/damage/complexity name encodes:
    "E" = Euclidean norm, "copfr" = unweighted (count of prime factors w/ repetition),
    otherwise the default log-prime (Tenney) weighting."""
    copfr = "copfr" in name
    return {
        "complexity_norm_power": 2 if "E" in name else 1,
        "complexity_log_prime_power": 0 if copfr else 1,
        "complexity_prime_power": 0,
    }


def damage_name_traits(name: str) -> dict:
    """Traits a damage systematic name encodes, e.g. ``"E-copfr-S-damage"``: the slope
    (final letter) plus the complexity traits."""
    core = name.replace("-damage", "")
    return {
        "damage_weight_slope": _SLOPE_BY_LETTER[core[-1]],
        **_complexity_traits_from_name(core),
    }


def complexity_name_traits(name: str) -> dict:
    """Traits an interval-complexity systematic name encodes, e.g. ``"copfr-E-complexity"``."""
    return _complexity_traits_from_name(name)


def tuning_scheme_from_systematic_name(name: str) -> TuningSchemeSpec:
    """Build a spec from a systematic tuning-scheme name like ``"{2/1, ...} minimax-E-copfr-S"``:
    the ``mini{max,RMS,average}`` prefix gives the optimization power, an optional ``{...}``
    gives the target intervals, and the trailing ``U``/``S``/``C`` plus complexity tokens
    give the damage weighting."""
    power = inf if "minimax" in name else (2 if "miniRMS" in name else 1)
    target_match = re.search(r"\{[\d/,\s]*\}", name)
    return TuningSchemeSpec(
        optimization_power=power,
        target_intervals=target_match.group(0) if target_match else None,
        damage_weight_slope=_SLOPE_BY_LETTER[name.strip()[-1]],
        **_complexity_traits_from_name(name),
    )


def optimize_generator_tuning_map(
    t: Temperament, spec: TuningSchemeSpec | str
) -> tuple[float, ...]:
    """The generator tuning map minimizing target-interval damage under the scheme.

    ``spec`` may be a :class:`TuningSchemeSpec` or a systematic tuning-scheme name string."""
    if isinstance(spec, str):
        spec = tuning_scheme_from_systematic_name(spec)
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
    return _power_sum(tempered, just, power)


def _power_sum(tempered: np.ndarray, just: np.ndarray, power: float) -> np.ndarray:
    """Minimize the sum of damages raised to ``power`` (the optimum for a finite power
    other than 1, 2, or ∞), starting from the least-squares solution."""
    initial = np.linalg.lstsq(tempered, just, rcond=None)[0]
    result = minimize(
        lambda generators: np.sum(np.abs(tempered @ generators - just) ** power),
        initial,
        method="Nelder-Mead",
        options={"xatol": 1e-9, "fatol": 1e-12, "maxiter": 100000},
    )
    return result.x


def _minimax(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    """Nested (lexicographic) minimax: minimize the largest absolute damage, then the
    next-largest, and so on, until the generators are uniquely pinned down.

    A plain minimax leaves the generators under-determined whenever several targets
    can share the maximum damage. We resolve that the way Wolfram's coinciding-damage
    method does: solve for the minimax level δ, freeze every target whose damage is
    forced to ±δ across the whole optimal set, then re-minimax the rest below δ.
    """
    active = list(range(len(just)))
    frozen_rows: list[np.ndarray] = []  # tempered rows pinned to an exact damage
    frozen_values: list[float] = []  # the value each pinned row's tempering must hit
    generators = np.zeros(rank)
    while active:
        delta, generators = _capped_minimax(
            tempered, just, rank, active, frozen_rows, frozen_values
        )
        locked = _targets_locked_at_delta(
            tempered, just, rank, active, frozen_rows, frozen_values, delta
        )
        if not locked:
            break
        for index, value in locked:
            frozen_rows.append(tempered[index])
            frozen_values.append(value)
            active.remove(index)
        if np.linalg.matrix_rank(np.vstack(frozen_rows)) >= rank:
            break
    return generators


def _capped_minimax(
    tempered: np.ndarray,
    just: np.ndarray,
    rank: int,
    active: list[int],
    frozen_rows: list[np.ndarray],
    frozen_values: list[float],
) -> tuple[float, np.ndarray]:
    """Minimize δ (variables ``[generators, δ]``) so every active target's damage is
    ≤ δ while the already-frozen targets stay pinned to their exact damage."""
    cost = np.concatenate([np.zeros(rank), [1.0]])
    a_ub, b_ub = [], []
    for i in active:
        a_ub.append(np.concatenate([tempered[i], [-1.0]]))
        b_ub.append(just[i])
        a_ub.append(np.concatenate([-tempered[i], [-1.0]]))
        b_ub.append(-just[i])
    a_eq = [np.concatenate([row, [0.0]]) for row in frozen_rows] or None
    bounds = [(None, None)] * rank + [(0, None)]
    result = linprog(
        cost,
        A_ub=np.array(a_ub),
        b_ub=np.array(b_ub),
        A_eq=np.array(a_eq) if a_eq else None,
        b_eq=np.array(frozen_values) if frozen_values else None,
        bounds=bounds,
    )
    return result.x[-1], result.x[:rank]


def _targets_locked_at_delta(
    tempered: np.ndarray,
    just: np.ndarray,
    rank: int,
    active: list[int],
    frozen_rows: list[np.ndarray],
    frozen_values: list[float],
    delta: float,
    tol: float = 1e-7,
) -> list[tuple[int, float]]:
    """Which active targets have damage forced to exactly ±δ across the whole optimal
    set (and so must be frozen there before re-minimaxing the rest). Returns each such
    target's index paired with the tempering value its row must hit."""
    a_ub, b_ub = [], []
    for j in active:
        a_ub.append(tempered[j])
        b_ub.append(just[j] + delta)
        a_ub.append(-tempered[j])
        b_ub.append(-just[j] + delta)
    a_ub, b_ub = np.array(a_ub), np.array(b_ub)
    a_eq = np.array(frozen_rows) if frozen_rows else None
    b_eq = np.array(frozen_values) if frozen_values else None
    bounds = [(None, None)] * rank
    scale = max(1.0, abs(delta))
    locked = []
    for i in active:
        low = linprog(tempered[i], A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)
        if abs((tempered[i] @ low.x - just[i]) - delta) <= tol * scale:
            locked.append((i, just[i] + delta))
            continue
        high = linprog(-tempered[i], A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)
        if abs((tempered[i] @ high.x - just[i]) + delta) <= tol * scale:
            locked.append((i, just[i] - delta))
    return locked


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
