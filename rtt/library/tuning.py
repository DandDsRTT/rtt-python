from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from math import inf, log2

import numpy as np
from scipy.linalg import null_space

from rtt.library.change_basis import change_domain_basis_for_c
from rtt.library.dimensions import get_d
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    filter_target_intervals_for_nonstandard_domain_basis,
    get_domain_basis,
    get_simplest_prime_only_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.dual import dual, mapping_matrix
from rtt.library.math_utils import pad_vectors_with_zeros_up_to_d, pcv_to_quotient, quotient_to_pcv
from rtt.library.parsing import parse_quotients
from rtt.library.target_intervals import process_old, process_tilt
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning_scheme_names import TuningSchemeSpec, resolve_tuning_scheme
from rtt.library.tuning_solvers import solve_optimum


def _sanitized_prescaler_override(prescaler_override):
    if prescaler_override is None:
        return None
    arr = np.asarray(prescaler_override, dtype=float)
    if not np.all(np.isfinite(arr)):
        return None
    diagonal = np.diagonal(arr) if arr.ndim == 2 else arr
    if np.any(diagonal <= 0):
        return None
    if arr.ndim == 2 and not np.isfinite(np.linalg.cond(arr)):
        return None
    return prescaler_override


def _sanitized_weights_override(weights_override):
    if weights_override is None:
        return None
    arr = np.asarray(weights_override, dtype=float)
    if arr.ndim != 1 or arr.size == 0:
        return None
    if not np.all(np.isfinite(arr)) or np.any(arr <= 0):
        return None
    return weights_override


def optimize_generator_tuning_map(
    t: Temperament,
    spec: TuningSchemeSpec | str,
    prescaler_override=None,
    weights_override=None,
) -> tuple[float, ...]:
    prescaler_override = _sanitized_prescaler_override(prescaler_override)
    weights_override = _sanitized_weights_override(weights_override)
    spec = resolve_tuning_scheme(spec)
    _validate_powers(spec)
    if spec.destretched_interval and spec.held_intervals:
        raise ValueError(
            "destretching cannot be combined with held intervals: destretching the whole tuning "
            "after the optimization would break any held interval (tuning-fundamentals "
            "MUST-GET-RIGHT 13 — the two cannot be combined)"
        )

    prime_based = spec.nonprime_basis_approach == "prime-based" and not (
        is_standard_prime_limit_domain_basis(get_domain_basis(t))
    )
    solve_t = _change_to_simplest_prime_basis(t) if prime_based else t
    solve_spec = replace(spec, nonprime_basis_approach="") if prime_based else spec

    generators = _solve_generators(
        solve_t,
        solve_spec,
        prescaler_override=prescaler_override,
        weights_override=weights_override,
    )
    if prime_based:
        generators = _retrieve_prime_domain_basis_generators(generators, t, solve_t)
    generators = _default_free_generators_to_just(generators, t, spec, get_d(t))

    if spec.destretched_interval:
        mapping = np.array(mapping_matrix(t), dtype=float)
        just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)
        generators = _destretch(
            generators, spec.destretched_interval, t, mapping, just_tuning_map, get_d(t)
        )
    return tuple(float(g) for g in generators)


def _solve_generators(
    t: Temperament,
    spec: TuningSchemeSpec,
    prescaler_override=None,
    weights_override=None,
) -> np.ndarray:
    d = get_d(t)
    mapping = np.array(mapping_matrix(t), dtype=float)
    just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)
    if _is_all_interval(spec) and spec.complexity_size_factor != 0:
        return _optimize_augmented_all_interval(
            t,
            spec,
            mapping,
            just_tuning_map,
            d,
            prescaler_override=prescaler_override,
        )
    vectors, weights, power = _optimization_setup(
        t, spec, d, prescaler_override=prescaler_override, weights_override=weights_override
    )
    return _constrained_solve(
        mapping, just_tuning_map, vectors, weights, power, _held_vectors(spec, t, d)
    )


def _change_to_simplest_prime_basis(t: Temperament) -> Temperament:
    comma_basis = t if t.variance is Variance.COL else dual(t)
    prime_basis = get_simplest_prime_only_basis(get_domain_basis(t))
    return dual(change_domain_basis_for_c(comma_basis, prime_basis))


def _retrieve_prime_domain_basis_generators(
    generators: np.ndarray, original_t: Temperament, prime_t: Temperament
) -> np.ndarray:
    prime_mapping = np.array(mapping_matrix(prime_t), dtype=float)
    tuning_over_primes = np.asarray(generators) @ prime_mapping
    basis_change = np.array(
        express_quotients_in_domain_basis(get_domain_basis(original_t), get_domain_basis(prime_t)),
        dtype=float,
    )
    tuning_over_original = tuning_over_primes @ basis_change.T
    return np.array(
        generator_tuning_map_from_t_and_tuning_map(original_t, tuple(tuning_over_original))
    )


def _is_all_interval(spec: TuningSchemeSpec) -> bool:
    return spec.target_intervals is not None and spec.target_intervals.strip() in ("{}", "")


def _constrained_solve(
    mapping: np.ndarray,
    just_tuning_map: np.ndarray,
    vectors: tuple[tuple[int, ...], ...],
    weights: np.ndarray,
    power: float,
    held_vectors: np.ndarray | None,
) -> np.ndarray:
    targets = np.array(vectors, dtype=float).reshape(-1, mapping.shape[1])
    tempered = (targets @ mapping.T) * weights[:, None]
    just = (targets @ just_tuning_map) * weights
    if held_vectors is None:
        return solve_optimum(tempered, just, power, mapping.shape[0])
    tempered_side = held_vectors @ mapping.T
    held_generators, *_ = np.linalg.lstsq(tempered_side, held_vectors @ just_tuning_map, rcond=None)
    held_null = null_space(tempered_side)
    if held_null.shape[1] == 0:
        return held_generators
    free = solve_optimum(
        tempered @ held_null, just - tempered @ held_generators, power, held_null.shape[1]
    )
    return held_generators + held_null @ free


def _default_free_generators_to_just(
    generators: np.ndarray, t: Temperament, spec: TuningSchemeSpec, d: int
) -> np.ndarray:
    mapping = np.array(mapping_matrix(t), dtype=float)
    rank = mapping.shape[0]
    rows = []
    held = _held_vectors(spec, t, d)
    if held is not None and held.size:
        rows.append(held @ mapping.T)
    if spec.target_intervals is not None:
        if spec.target_intervals.strip() in ("{}", ""):
            target_vectors = np.eye(d)
        else:
            target_vectors = np.array(
                resolve_target_intervals(spec.target_intervals, t, d), dtype=float
            ).reshape(-1, d)
        if target_vectors.size:
            rows.append(target_vectors @ mapping.T)
    determining = np.vstack(rows) if rows else np.zeros((0, rank))
    free = null_space(determining)
    if free.shape[1] == 0:
        return generators
    just_generators = np.array(get_just_tuning_map(t), dtype=float) @ np.linalg.pinv(mapping)
    g = np.array(generators, dtype=float)
    return g + free @ (free.T @ (just_generators - g))


def _optimize_augmented_all_interval(
    t: Temperament,
    spec: TuningSchemeSpec,
    mapping: np.ndarray,
    just_tuning_map: np.ndarray,
    d: int,
    prescaler_override=None,
) -> np.ndarray:
    rank = mapping.shape[0]
    size_factor = spec.complexity_size_factor
    prescaler = np.asarray(
        get_complexity_prescaler(
            t,
            spec.complexity_log_prime_power,
            spec.complexity_prime_power,
            spec.nonprime_basis_approach,
            override=prescaler_override,
        ),
        dtype=float,
    )
    size_coeffs = prescaler.sum(axis=0) if prescaler.ndim == 2 else prescaler

    aug_mapping = np.zeros((rank + 1, d + 1))
    aug_mapping[:rank, :d] = mapping
    aug_mapping[rank, :d] = size_factor * size_coeffs
    aug_mapping[rank, d] = -1.0
    aug_just = np.append(just_tuning_map, 0.0)

    primes, prime_weights, power = _optimization_setup(
        t,
        replace(spec, complexity_size_factor=0),
        d,
        prescaler_override=prescaler_override,
    )
    aug_vectors = np.eye(d + 1)
    weights = np.append(prime_weights, 1.0)

    held = _held_vectors(spec, t, d)
    aug_held = (
        None if held is None else np.hstack([held, size_factor * (held @ size_coeffs)[:, None]])
    )

    generators = _constrained_solve(aug_mapping, aug_just, aug_vectors, weights, power, aug_held)
    return generators[:rank]


def _destretch(
    generators: np.ndarray,
    destretched_interval: str,
    t: Temperament,
    mapping: np.ndarray,
    just_tuning_map: np.ndarray,
    d: int,
) -> np.ndarray:
    interval = np.array(_interval_spec_vectors(destretched_interval, t, d)[0], dtype=float)
    just_size = just_tuning_map @ interval
    tempered_size = (generators @ mapping) @ interval
    if abs(tempered_size) < 1e-6:
        raise ValueError(
            "cannot destretch by an interval the temperament tempers out: its tempered size "
            "is 0, so just/tempered is undefined (tuning-fundamentals MUST-GET-RIGHT 13)"
        )
    return generators * (just_size / tempered_size)


def _optimization_setup(
    t: Temperament,
    spec: TuningSchemeSpec,
    d: int,
    prescaler_override=None,
    weights_override=None,
) -> tuple[tuple[tuple[int, ...], ...], np.ndarray, float]:
    if spec.target_intervals is None:
        return (), np.array([]), spec.optimization_power
    if spec.target_intervals.strip() in ("{}", ""):
        if prescaler_override is not None and np.ndim(prescaler_override) == 2:
            inverse_columns = np.linalg.inv(np.asarray(prescaler_override, dtype=float)).T
            return (
                tuple(map(tuple, inverse_columns)),
                np.ones(d),
                get_dual_power(spec.complexity_norm_power),
            )
        primes = tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
        weights = damage_weights(
            primes,
            t,
            replace(spec, damage_weight_slope="simplicityWeight", complexity_rough=0),
            prescaler_override=prescaler_override,
        )
        return primes, weights, get_dual_power(spec.complexity_norm_power)
    vectors = resolve_target_intervals(spec.target_intervals, t, d)
    return (
        vectors,
        damage_weights(
            vectors,
            t,
            spec,
            prescaler_override=prescaler_override,
            weights_override=weights_override,
        ),
        spec.optimization_power,
    )


def optimize_tuning_map(
    t: Temperament,
    spec: TuningSchemeSpec | str,
    prescaler_override=None,
    weights_override=None,
) -> tuple[float, ...]:
    generators = np.array(
        optimize_generator_tuning_map(
            t, spec, prescaler_override=prescaler_override, weights_override=weights_override
        ),
        dtype=float,
    )
    mapping = np.array(mapping_matrix(t), dtype=float)
    return tuple(float(x) for x in generators @ mapping)


def get_tuning_map_damages(t: Temperament, tuning_map: tuple, spec: TuningSchemeSpec | str) -> dict:
    vectors, damages, _ = _evaluate_damages(t, tuning_map, spec)
    return {
        pcv_to_quotient(vector): float(damage)
        for vector, damage in zip(vectors, damages, strict=False)
    }


def get_generator_tuning_map_damages(
    t: Temperament, generator_tuning_map: tuple, spec: TuningSchemeSpec | str
) -> dict:
    return get_tuning_map_damages(t, tuning_map_from_generators(t, generator_tuning_map), spec)


def get_tuning_map_mean_damage(
    t: Temperament, tuning_map: tuple, spec: TuningSchemeSpec | str
) -> float:
    _, damages, power = _evaluate_damages(t, tuning_map, spec)
    if len(damages) == 0:
        return 0.0
    if power == inf:
        return float(np.max(damages))
    return float((np.sum(damages**power) / len(damages)) ** (1 / power))


def get_generator_tuning_map_mean_damage(
    t: Temperament, generator_tuning_map: tuple, spec: TuningSchemeSpec | str
) -> float:
    return get_tuning_map_mean_damage(t, tuning_map_from_generators(t, generator_tuning_map), spec)


def tuning_map_from_generators(t: Temperament, generator_tuning_map: tuple) -> np.ndarray:
    return np.array(generator_tuning_map, dtype=float) @ np.array(mapping_matrix(t), dtype=float)


def _evaluate_damages(
    t: Temperament, tuning_map: tuple, spec: TuningSchemeSpec | str
) -> tuple[tuple[tuple[int, ...], ...], np.ndarray, float]:
    spec = resolve_tuning_scheme(spec)
    d = get_d(t)
    just_tuning_map = np.array(get_just_tuning_map(t), dtype=float)
    vectors, weights, power = _optimization_setup(t, spec, d)
    targets = np.array(vectors, dtype=float).reshape(-1, d)
    tempered = np.array(tuning_map, dtype=float)
    damages = np.abs(targets @ tempered - targets @ just_tuning_map) * weights
    return vectors, damages, power


def resolve_target_intervals(
    target_spec: str, t: Temperament, d: int
) -> tuple[tuple[int, ...], ...]:
    domain_basis = get_domain_basis(t)
    if target_spec == "primes":
        return tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
    if "TILT" in target_spec or "truncated integer limit triangle" in target_spec:
        quotients = process_tilt(target_spec, domain_basis)
    elif "OLD" in target_spec or "odd limit diamond" in target_spec:
        quotients = process_old(target_spec, domain_basis)
    else:
        quotients = parse_quotients(target_spec)
    if is_standard_prime_limit_domain_basis(domain_basis):
        pcvs = [v for v in (quotient_to_pcv(q) for q in quotients) if len(v) <= d]
        vectors = pad_vectors_with_zeros_up_to_d(tuple(pcvs), d)
    else:
        in_basis = filter_target_intervals_for_nonstandard_domain_basis(quotients, domain_basis)
        vectors = express_quotients_in_domain_basis(in_basis, domain_basis)
    return tuple(v for v in vectors if any(v))


def _interval_spec_vectors(text: str, t: Temperament, d: int) -> tuple[tuple[int, ...], ...]:
    quotients = parse_quotients(text.replace("octave", "2"))
    domain_basis = get_domain_basis(t)
    if is_standard_prime_limit_domain_basis(domain_basis):
        return pad_vectors_with_zeros_up_to_d(tuple(quotient_to_pcv(q) for q in quotients), d)
    return express_quotients_in_domain_basis(quotients, domain_basis)


def _held_vectors(spec: TuningSchemeSpec, t: Temperament, d: int) -> np.ndarray | None:
    if not spec.held_intervals:
        return None
    return np.array(_interval_spec_vectors(spec.held_intervals, t, d), dtype=float)


def damage_weights(
    vectors: tuple[tuple[int, ...], ...],
    t: Temperament,
    spec: TuningSchemeSpec,
    prescaler_override=None,
    weights_override=None,
) -> np.ndarray:
    if weights_override is not None and len(weights_override) == len(vectors):
        weights = np.asarray(weights_override, dtype=float)
        if np.all(np.isfinite(weights)) and np.all(weights > 0):
            return weights
    if spec.damage_weight_slope == "unityWeight":
        return np.ones(len(vectors))
    complexities = np.array(
        [
            get_complexity(
                vector,
                t,
                spec.complexity_norm_power,
                spec.complexity_log_prime_power,
                spec.complexity_prime_power,
                spec.complexity_size_factor,
                spec.nonprime_basis_approach,
                complexity_rough=spec.complexity_rough,
                prescaler_override=prescaler_override,
            )
            for vector in vectors
        ]
    )
    if spec.damage_weight_slope == "complexityWeight":
        return complexities
    if spec.damage_weight_slope == "simplicityWeight":
        return 1.0 / complexities
    raise ValueError(f"unknown damage weight slope: {spec.damage_weight_slope!r}")


def get_complexity_prescaler(
    t: Temperament,
    log_prime_power,
    prime_power,
    nonprime_basis_approach: str,
    override=None,
) -> list[float]:
    if override is not None:
        return override
    return _prescaler_diagonal(
        get_domain_basis(t), log_prime_power, prime_power, nonprime_basis_approach
    )


def _prescaler_diagonal(
    domain_basis, log_prime_power, prime_power, nonprime_basis_approach: str
) -> list[float]:
    diagonal = []
    for q in domain_basis:
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
    return diagonal


def get_complexity(
    pcv: tuple,
    t: Temperament,
    norm_power,
    log_prime_power,
    prime_power,
    size_factor,
    nonprime_basis_approach: str,
    complexity_rough: int = 0,
    prescaler_override=None,
) -> float:
    domain_basis = get_domain_basis(t)
    if (
        prescaler_override is None
        and nonprime_basis_approach != "nonprime-based"
        and len(pcv) == len(domain_basis)
        and not is_standard_prime_limit_domain_basis(domain_basis)
    ):
        prime_basis = get_simplest_prime_only_basis(domain_basis)
        if tuple(prime_basis) != tuple(domain_basis):
            lift = express_quotients_in_domain_basis(domain_basis, prime_basis)
            pcv = tuple(
                sum(pcv[e] * lift[e][p] for e in range(len(lift))) for p in range(len(prime_basis))
            )
            domain_basis = prime_basis
    if complexity_rough:
        pcv = tuple(
            0 if Fraction(q).denominator == 1 and Fraction(q).numerator < complexity_rough else x
            for q, x in zip(domain_basis, pcv, strict=False)
        )
    prescaler = (
        prescaler_override
        if prescaler_override is not None
        else _prescaler_diagonal(
            domain_basis, log_prime_power, prime_power, nonprime_basis_approach
        )
    )
    if np.ndim(prescaler) == 2:
        transformed = list(np.asarray(prescaler, dtype=float) @ np.asarray(pcv, dtype=float))
    else:
        transformed = [w * x for w, x in zip(prescaler, pcv, strict=False)]
    if size_factor != 0:
        transformed.append(size_factor * sum(transformed))
    ord_ = np.inf if norm_power == float("inf") else norm_power
    return float(np.linalg.norm(transformed, ord_)) / (1 + size_factor)


def get_dual_power(power):
    if power < 1:
        raise ValueError(f"a norm power must be ≥ 1; got {power}")
    if power == 1:
        return float("inf")
    return 1 / (1 - 1 / power)


def _validate_powers(spec: TuningSchemeSpec) -> None:
    if spec.optimization_power < 1:
        raise ValueError(f"optimization power must be ≥ 1; got {spec.optimization_power}")
    if spec.complexity_norm_power < 1:
        raise ValueError(f"complexity norm power must be ≥ 1; got {spec.complexity_norm_power}")


def get_just_tuning_map(t: Temperament) -> tuple[float, ...]:
    return tuple(1200.0 * log2(float(q)) for q in get_domain_basis(t))


def generator_tuning_map_from_t_and_tuning_map(
    t: Temperament, tuning_map: tuple
) -> tuple[float, ...]:
    mapping = np.array(mapping_matrix(t), dtype=float)
    generators = np.array(tuning_map, dtype=float) @ np.linalg.pinv(mapping)
    return tuple(float(x) for x in generators)
