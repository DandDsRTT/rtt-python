from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from rtt.app.service.core_vectors import _interval_vectors, _over, _to_matrix
from rtt.library.addition import _get_greatest_factor
from rtt.library.dimensions import get_dimensionality, get_rank
from rtt.library.domain_basis import is_standard_prime_limit_domain_basis
from rtt.library.math_utils import get_primes
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import (
    damage_weights,
    get_complexity,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    tuning_map_from_generators,
)
from rtt.library.tuning_ranges import get_generator_tuning_range as _get_generator_tuning_range
from rtt.library.tuning_scheme_names import resolve_tuning_scheme


def get_generator_tuning_range(t, mode):
    try:
        return _get_generator_tuning_range(t, mode)
    except (ValueError, IndexError):
        return None


DEFAULT_TUNING_SCHEME = "minimax-S"
DEFAULT_TARGET_SPEC = "TILT"
DEFAULT_DOCUMENT_SCHEME = f"{DEFAULT_TARGET_SPEC} minimax-U"


@dataclass(frozen=True)
class Tuning:
    generator_map: tuple[float, ...]
    tuning_map: tuple[float, ...]
    just_map: tuple[float, ...]
    retuning_map: tuple[float, ...]
    monotone_generator_range: tuple[tuple[float, float], ...] | None
    tradeoff_generator_range: tuple[tuple[float, float], ...] | None


@dataclass(frozen=True)
class IntervalSizes:
    tempered: tuple[float, ...]
    just: tuple[float, ...]
    errors: tuple[float, ...]
    damage: tuple[float, ...]


def _hashable(value):
    if value is None:
        return None
    return tuple(tuple(row) if isinstance(row, (tuple, list)) else row for row in value)


def _is_matrix(x) -> bool:
    return bool(x) and isinstance(x[0], (tuple, list))


def standard_primes(d: int) -> tuple[int, ...]:
    return get_primes(d)


def is_standard_domain(domain_basis) -> bool:
    return is_standard_prime_limit_domain_basis(tuple(domain_basis))


def domain_has_nonprimes(domain_basis) -> bool:
    for element in domain_basis:
        fraction = Fraction(element)
        if fraction.denominator != 1 or not sp.isprime(fraction.numerator):
            return True
    return False


def is_proper_temperament(mapping) -> bool:
    rows = _to_matrix(mapping)
    if not rows or not rows[0]:
        return False
    rank = get_rank(Temperament(rows, Variance.ROW))
    if rank < len(rows):
        return False
    return all(any(row[p] for row in rows) for p in range(len(rows[0])))


def greatest_factor(mapping) -> int:
    rows = _to_matrix(mapping)
    if not rows or not rows[0] or get_rank(Temperament(rows, Variance.ROW)) < len(rows):
        return 1
    return abs(_get_greatest_factor(rows))


def is_enfactored(mapping) -> bool:
    return greatest_factor(mapping) > 1


def tuning(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    domain_basis=None,
    nonprime_approach: str = "",
    held=(),
    prescaler_override=None,
    targets=None,
    weights_override=None,
) -> Tuning:
    return _cached_tuning(
        _to_matrix(mapping),
        scheme,
        _hashable(domain_basis),
        nonprime_approach,
        tuple(held),
        _hashable(prescaler_override),
        _hashable(targets),
        _hashable(weights_override),
    )


@lru_cache(maxsize=256)
def _cached_tuning(
    mapping,
    scheme,
    domain_basis,
    nonprime_approach,
    held,
    prescaler_override,
    targets,
    weights_override,
) -> Tuning:
    t = Temperament(mapping, Variance.ROW, domain_basis)
    spec = resolve_tuning_scheme(scheme)
    if targets is not None and (spec.target_intervals or "").strip() not in ("{}", ""):
        if targets:
            spec = replace(spec, target_intervals="{" + ", ".join(targets) + "}")
        else:
            spec = replace(
                spec,
                target_intervals="1-OLD" if "OLD" in (spec.target_intervals or "") else "1-TILT",
            )
    if nonprime_approach:
        spec = replace(spec, nonprime_basis_approach=nonprime_approach)
    if held:
        own = (spec.held_intervals or "").strip().strip("{}").strip()
        parts = ([own] if own else []) + list(held)
        spec = replace(spec, held_intervals="{" + ", ".join(parts) + "}")
    gmap = optimize_generator_tuning_map(
        t, spec, prescaler_override=prescaler_override, weights_override=weights_override
    )
    tempered = tuple(float(x) for x in tuning_map_from_generators(t, gmap))
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=gmap,
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just, strict=False)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def tuning_from_generators(mapping, generators, domain_basis=None) -> Tuning:
    return _cached_tuning_from_generators(
        _to_matrix(mapping), tuple(float(g) for g in generators), _hashable(domain_basis)
    )


@lru_cache(maxsize=256)
def _cached_tuning_from_generators(mapping, generators, domain_basis) -> Tuning:
    t = Temperament(mapping, Variance.ROW, domain_basis)
    tempered = tuple(float(x) for x in tuning_map_from_generators(t, generators))
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=tuple(generators),
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just, strict=False)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def interval_sizes(tuning_map: Tuning, ratios, domain_basis=None, weights=None) -> IntervalSizes:
    vectors = _interval_vectors(ratios, domain_basis, len(tuning_map.tuning_map))
    tempered = tuple(_over(tuning_map.tuning_map, m) for m in vectors)
    just = tuple(_over(tuning_map.just_map, m) for m in vectors)
    errors = tuple(t_ - j for t_, j in zip(tempered, just, strict=False))
    if weights is None:
        damage = tuple(abs(e) for e in errors)
    else:
        damage = tuple(abs(e) * w for e, w in zip(errors, weights, strict=False))
    return IntervalSizes(tempered, just, errors, damage)


def _temperament_spec_vectors(mapping, scheme, ratios, domain_basis=None):
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    return (
        t,
        resolve_tuning_scheme(scheme),
        _interval_vectors(ratios, domain_basis, get_dimensionality(t)),
    )


def interval_complexities(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    ratios=(),
    prescaler_override=None,
    domain_basis=None,
) -> tuple[float, ...]:
    t, spec, vectors = _temperament_spec_vectors(mapping, scheme, ratios, domain_basis)
    return tuple(
        get_complexity(
            m, t, replace(spec.complexity, rough=0), prescaler_override=prescaler_override
        )
        for m in vectors
    )


def weights_deviate(custom, slope) -> bool:
    if custom is None:
        return False
    if len(custom) != len(slope):
        return True
    return any(round(a, 3) != round(b, 3) for a, b in zip(custom, slope, strict=True))


def interval_weights(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    ratios=(),
    prescaler_override=None,
    domain_basis=None,
    weights_override=None,
) -> tuple[float, ...]:
    t, spec, vectors = _temperament_spec_vectors(mapping, scheme, ratios, domain_basis)
    return tuple(
        float(w)
        for w in damage_weights(
            vectors,
            t,
            spec,
            prescaler_override=prescaler_override,
            weights_override=weights_override,
        )
    )
