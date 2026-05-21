from __future__ import annotations

import re
from dataclasses import dataclass, replace
from fractions import Fraction
from math import inf, log2

import numpy as np
from scipy.linalg import null_space
from scipy.optimize import linprog, minimize

from rtt.dimensions import get_d
from rtt.domain_basis import get_domain_basis
from rtt.dual import dual
from rtt.math_utils import pad_vectors_with_zeros_up_to_d, quotient_to_pcv
from rtt.parsing import parse_quotient_list
from rtt.target_intervals import process_old, process_tilt
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
    held_intervals: str | None = None  # trait 0: intervals tuned exactly justly


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


# Historical tuning-scheme names, each expressed as the equivalent systematic name.
# (POTE/POTOP/Weil/Kees etc. await destretching and the size-factor complexity.)
_ORIGINAL_NAME_SCHEMES = {
    "minimax": "held-octave OLD minimax-U",
    "least squares": "held-octave OLD miniRMS-U",
    "TOP": "minimax-S",
    "TIPTOP": "minimax-S",
    "T1": "minimax-S",
    "TOP-max": "minimax-S",
    "Tenney": "minimax-S",
    "TE": "minimax-ES",
    "Tenney-Euclidean": "minimax-ES",
    "T2": "minimax-ES",
    "TOP-RMS": "minimax-ES",
    "CTE": "held-octave minimax-ES",
    "Constrained Tenney-Euclidean": "held-octave minimax-ES",
}


def tuning_scheme_from_systematic_name(name: str) -> TuningSchemeSpec:
    """Build a spec from a systematic tuning-scheme name like ``"{2/1, ...} minimax-E-copfr-S"``:
    the ``mini{max,RMS,average}`` prefix gives the optimization power, an optional ``{...}``
    gives the target intervals, and the trailing ``U``/``S``/``C`` plus complexity tokens
    give the damage weighting. An optional ``held-<interval(s)>`` prefix names intervals
    to tune justly."""
    held = None
    held_match = re.match(r"\s*held-(\{[^}]*\}|[\w/]+)\s+(.*)", name)
    if held_match:
        held, name = held_match.group(1), held_match.group(2)
    power = inf if "minimax" in name else (2 if "miniRMS" in name else 1)
    target_match = re.search(
        r"\{[\d/,\s]*\}|\d*-?TILT|\d*-?OLD|primes", name
    )
    target = target_match.group(0) if target_match else None
    if target is None and ("all-interval" in name or ("minimax" in name and "S" in name)):
        target = "{}"  # all-interval scheme (e.g. minimax-S = TOP, minimax-ES = TE)
    return TuningSchemeSpec(
        optimization_power=power,
        target_intervals=target,
        damage_weight_slope=_SLOPE_BY_LETTER[name.strip()[-1]],
        held_intervals=held,
        **_complexity_traits_from_name(name),
    )


def optimize_generator_tuning_map(
    t: Temperament, spec: TuningSchemeSpec | str
) -> tuple[float, ...]:
    """The generator tuning map minimizing target-interval damage under the scheme.

    ``spec`` may be a :class:`TuningSchemeSpec`, a systematic tuning-scheme name string,
    or a historical scheme name (e.g. ``"TOP"``, ``"TE"``, ``"CTE"``)."""
    if isinstance(spec, str):
        spec = tuning_scheme_from_systematic_name(_ORIGINAL_NAME_SCHEMES.get(spec, spec))
    d = get_d(t)
    mapping = np.array(_mapping_matrix(t), dtype=float)  # r x d
    just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)  # d

    held_generators, held_null = _held_constraint(spec, mapping, just_tuning_map, d)
    if held_null is not None and held_null.shape[1] == 0:
        return tuple(float(g) for g in held_generators)  # held intervals pin the tuning

    monzos, weights, power = _optimization_setup(t, spec, d)
    targets = np.array(monzos, dtype=float)  # k x d
    tempered = (targets @ mapping.T) * weights[:, None]  # k x r
    just = (targets @ just_tuning_map) * weights  # k

    if held_null is not None:
        # g = held_generators + held_null @ y, optimizing only the held-justly subspace
        free = _solve_optimum(
            tempered @ held_null,
            just - tempered @ held_generators,
            power,
            held_null.shape[1],
        )
        generators = held_generators + held_null @ free
    else:
        generators = _solve_optimum(tempered, just, power, mapping.shape[0])
    return tuple(float(g) for g in generators)


def _optimization_setup(
    t: Temperament, spec: TuningSchemeSpec, d: int
) -> tuple[tuple[tuple[int, ...], ...], np.ndarray, float]:
    """The (target monzos, per-target damage weights, optimization power) for the scheme.

    An all-interval scheme (empty target set) instead optimizes over the primes with
    simplicity weighting, at the dual of the interval-complexity norm power — minimax
    over every interval is, by duality, this optimization over the primes."""
    if spec.target_intervals is not None and spec.target_intervals.strip() in ("{}", ""):
        primes = tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
        weights = _damage_weights(primes, t, replace(spec, damage_weight_slope="simplicityWeight"))
        return primes, weights, get_dual_power(spec.complexity_norm_power)
    monzos = _resolve_target_intervals(spec.target_intervals, t, d)
    return monzos, _damage_weights(monzos, t, spec), spec.optimization_power


def optimize_tuning_map(t: Temperament, spec: TuningSchemeSpec | str) -> tuple[float, ...]:
    """The optimum tuning map (the generators applied to the mapping) under the scheme."""
    generators = np.array(optimize_generator_tuning_map(t, spec), dtype=float)
    mapping = np.array(_mapping_matrix(t), dtype=float)
    return tuple(float(x) for x in generators @ mapping)


def _resolve_target_intervals(
    target_spec: str, t: Temperament, d: int
) -> tuple[tuple[int, ...], ...]:
    """Resolve a target-interval spec to monzos: an explicit ``{...}`` quotient list, a
    TILT/OLD named scheme, or ``"primes"`` (the identity)."""
    if "TILT" in target_spec or "truncated integer limit triangle" in target_spec:
        quotients = process_tilt(target_spec, get_domain_basis(t))
    elif "OLD" in target_spec or "odd limit diamond" in target_spec:
        quotients = process_old(target_spec, get_domain_basis(t))
    elif target_spec == "primes":
        return tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
    else:
        return parse_quotient_list(target_spec, d)
    return pad_vectors_with_zeros_up_to_d(
        tuple(quotient_to_pcv(q) for q in quotients), d
    )


def _parse_interval_spec(text: str, d: int) -> tuple[tuple[int, ...], ...]:
    """Parse an interval-set spec (``"octave"``, ``"2"``, ``"2/1"``, ``"{2/1, 3/2}"``) into monzos."""
    return parse_quotient_list(text.replace("octave", "2"), d)


def _held_constraint(
    spec: TuningSchemeSpec, mapping: np.ndarray, just_tuning_map: np.ndarray, d: int
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """For held intervals (tuned exactly justly), a particular generator map satisfying
    those equalities and an orthonormal basis for the remaining free directions; both
    ``None`` if the scheme holds no intervals."""
    if not spec.held_intervals:
        return None, None
    held = np.array(_parse_interval_spec(spec.held_intervals, d), dtype=float)
    tempered_side = held @ mapping.T  # n_held x r: each held interval's tempered size
    just_side = held @ just_tuning_map  # its just size
    generators, *_ = np.linalg.lstsq(tempered_side, just_side, rcond=None)
    return generators, null_space(tempered_side)


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
